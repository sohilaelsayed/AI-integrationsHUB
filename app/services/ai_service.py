import requests
import os
import json
from dotenv import load_dotenv
import pathlib
from app.core.config import OPENROUTER_API_KEY

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)



API_KEY = OPENROUTER_API_KEY

print("API KEY:", API_KEY)

# =========================
# 🧠 Prompt
# =========================
def build_prompt(donor, needs):
    return f"""
You are a strict matching and ranking engine.

Your task:
- Compare a donor organization with a list of charity needs.
- Return ALL charity needs from the input, but SORTED by relevance (highest first).

Ranking logic (strict priority order):
1. Semantic relevance (PRIMARY):
   - Match between donorOrganizationName / donorOrganizationDescription 
     and charity need productName / category.

2. Geographic proximity (SECONDARY):
   - Same city AND same governorate → highest priority
   - Same governorate only → medium priority
   - Different governorate → lower priority

IMPORTANT RULE (NO FILTERING):
- DO NOT remove any item from the input list.
- You MUST return ALL charityNeeds exactly as provided.
- Only change the ORDER of items based on relevance.

Validation rules (CRITICAL):
- Output MUST contain the SAME number of items as input charityNeeds.
- Each returned object must be EXACTLY identical to its original input object.
- DO NOT create, modify, or hallucinate any fields.
- DO NOT rename keys.
- Only reordering is allowed (no filtering, no deletion).

Output rules (STRICT):
- Return ONLY valid JSON.
- No explanation.
- No markdown.
- No extra text.

Response format:
{{
  "matchedCharityNeeds": [ ... ],
  "status": {{
    "successful": true,
    "message": "All inputs returned in sorted order successfully"
  }}
}}

Failure case:
{{
  "matchedCharityNeeds": [],
  "status": {{
    "successful": false,
    "message": "Unable to process request at this time"
  }}
}}

Input:
Donor:
{donor}

CharityNeeds:
{needs}
"""


# =========================
# 🔄 Fallback ذكي
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
        