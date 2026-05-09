import requests
import os
import json
import hashlib
from dotenv import load_dotenv
import pathlib
from redis import Redis
from app.core.config import OPENROUTER_API_KEY, REDIS_URL, REDIS_PREFIX

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

API_KEY = OPENROUTER_API_KEY
CACHE_TTL_SECONDS = 3600

redis_client = None
if REDIS_URL:
    try:
        redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        print("Redis init failed:", e)


def make_cache_key(donor, needs):
    donor_id = str(donor.get("donorOrganizationId", "donor"))
    return f"{REDIS_PREFIX}:{donor_id}"


def get_cached_sorted_ids(cache_key):
    if redis_client is None:
        return None
    try:
        ids = redis_client.zrange(cache_key, 0, -1)
        return ids if ids else None
    except Exception as e:
        print("Redis read error:", e)
        return None


def cache_sorted_ids(cache_key, ids):
    if redis_client is None or not ids:
        return
    try:
        mapping = {str(value): score for score, value in enumerate(ids)}
        redis_client.zadd(cache_key, mapping)
        redis_client.expire(cache_key, CACHE_TTL_SECONDS)
    except Exception as e:
        print("Redis write error:", e)

print("API KEY:", API_KEY)

# =========================
# 🧠 Prompt
# =========================
def build_prompt(donor, needs):
    return f"""
You are a strict matching and ranking engine for charity needs.

Your task:
- Compare a donor organization with a list of charity needs.
- Return ALL charity needs from the input, but SORTED by relevance (highest first).
- DO NOT filter or remove any items - return the complete list in new order.

Ranking logic (strict priority order):
1. Semantic relevance (PRIMARY - most important):
   - Perfect match: donor provides food/clothing/medical/education and need is in same category
   - Good match: donor description mentions similar products or services
   - Poor match: unrelated categories

2. Geographic proximity (SECONDARY - tiebreaker):
   - Same city AND same governorate → highest priority
   - Same governorate only (different city) → medium priority
   - Different governorate → lower priority

3. Priority level (TERTIARY - final tiebreaker):
   - Urgent > High > Normal > Low

CRITICAL VALIDATION RULES:
- Output MUST contain the SAME number of items as input charityNeeds.
- Each returned object must be EXACTLY identical to its original input object.
- DO NOT modify, add, or remove any fields or values.
- DO NOT change data types or formats.
- Only reorder the items based on relevance.

Output rules (STRICT):
- Return ONLY valid JSON.
- No explanation, no markdown, no extra text.
- Format: {{"matchedCharityNeeds": [sorted original objects], "status": {{"successful": true, "message": "All inputs returned in sorted order successfully"}}}}

Failure case (only if parsing error):
{{"matchedCharityNeeds": [], "status": {{"successful": false, "message": "Unable to process request at this time"}}}}

Input:
Donor: {donor}

CharityNeeds: {needs}
"""


# =========================
# Fallback ذكي
# =========================
def smart_fallback(donor, needs):
    results = []

    for n in needs:
        score = 0

        # category match
        if n["category"].lower() in donor["donorOrganizationDescription"].lower():
            score += 0.4

        # city match
        if n["city"] == donor["city"]:
            score += 0.3
        elif n["governorate"] == donor["governorate"]:
            score += 0.2

        # priority
        if n["priority"].lower() == "high":
            score += 0.2
        elif n["priority"].lower() == "medium":
            score += 0.1

        score = round(min(score, 1), 2)

        results.append({
            "needId": n["charityNeedId"],
            "score": score,
            "reason": "Fallback smart matching"
        })

    # ترتيب تنازلي
    results.sort(key=lambda x: x["score"], reverse=True)

    return results


# =========================
# 🤖 AI + fallback
# =========================
def match_with_ai(donor, needs):
    cache_key = make_cache_key(donor, needs)
    cached_ids = get_cached_sorted_ids(cache_key)

    if cached_ids:
        lookup = {str(n["charityNeedId"]): n for n in needs}
        ordered = [lookup[id_] for id_ in cached_ids if id_ in lookup]
        if len(ordered) == len(needs):
            return {
                "matchedCharityNeeds": ordered,
                "status": {
                    "successful": True,
                    "message": "Returned sorted charity needs from cache"
                },
                "source": "cache"
            }

    try:
        prompt = build_prompt(donor, needs)

        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        )

        data = response.json()

        text = data["choices"][0]["message"]["content"]

        cleaned = text.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(cleaned)

        sorted_ids = [item["charityNeedId"] for item in parsed.get("matchedCharityNeeds", [])]
        if sorted_ids:
            cache_sorted_ids(cache_key, sorted_ids)
        
        return {
            "matchedCharityNeeds": parsed.get("matchedCharityNeeds", []),
            "status": parsed.get("status", {
                "successful": False,
                "message": "Invalid AI response"
            }),
            "source": "ai"
        }

    except Exception as e:
        return {
            "matchedCharityNeeds": [],
            "status": {
                "successful": False,
                "message": str(e)
            },
            "source": "fallback"
        }
        