import requests
import os
import json
import hashlib
import logging
import time
import re
from dotenv import load_dotenv
import pathlib
from redis import Redis
from app.core.config import OPENROUTER_API_KEY, REDIS_URL, REDIS_PREFIX
from app.models.schemas import ProductCategory, MeasurementUnit, CharityNeedPriority, CharityNeedStatus

# Setup logging
logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

API_KEY = OPENROUTER_API_KEY
CACHE_TTL_SECONDS = 7200

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


# =========================
#  Error Message Mapping
# =========================
def get_user_friendly_error(status_code):
    """Return safe, user-friendly error messages without sensitive details"""
    error_map = {
        400: "Invalid request format. Please check your input data.",
        401: "Authentication failed. Service is not properly configured.",
        429: "Service is temporarily busy. Please try again in a moment.",
        500: "Service encountered an error. Please try again later.",
        503: "Service is temporarily unavailable. Please try again soon.",
    }
    return error_map.get(status_code, "An unexpected error occurred. Please try again later.")


def extract_json_object(text):
    """Try to extract a top-level JSON object from a model response."""
    if not isinstance(text, str):
        return text
    text = text.strip()
    # Remove markdown fences if present
    text = text.replace("```json", "").replace("```", "").strip()
    # Extract the first JSON object block from the text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text


def normalize_enums_in_needs(needs_list):
    """Convert enum-like strings (e.g. '<ProductCategory.EDUCATION: 3>') or names into integer codes."""
    pattern = re.compile(r"<[^:]+:\s*(\d+)>")
    for need in needs_list:
        for field, enum_cls in (
            ("category", ProductCategory),
            ("unit", MeasurementUnit),
            ("priority", CharityNeedPriority),
            ("status", CharityNeedStatus),
        ):
            if field not in need:
                continue
            val = need.get(field)
            # If already an int, skip
            if isinstance(val, int):
                continue
            # If string like '<ProductCategory.EDUCATION: 3>'
            if isinstance(val, str):
                m = pattern.search(val)
                if m:
                    try:
                        need[field] = int(m.group(1))
                        continue
                    except Exception:
                        pass
                # If string like 'ProductCategory.EDUCATION' or 'EDUCATION'
                name = val.split('.')[-1].strip() if '.' in val else val.strip()
                try:
                    need[field] = enum_cls[name].value
                    continue
                except Exception:
                    pass
            # If the model returned an object with a numeric 'value' field
            if isinstance(val, dict) and 'value' in val:
                try:
                    need[field] = int(val.get('value'))
                    continue
                except Exception:
                    pass


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

Failure case:
{{"matchedCharityNeeds": [], "status": {{"successful": false, "message": "Unable to process request at this time"}}}}

IMPORTANT: If you cannot return valid JSON exactly as specified, reply only with the failure case JSON above.

Input:
Donor: {donor}

CharityNeeds: {needs}
"""


# =========================
#  AI Matching
# =========================
def match_with_ai(donor, needs, max_retries=2):
    cache_key = make_cache_key(donor, needs)
    cached_ids = get_cached_sorted_ids(cache_key)

    if cached_ids:
        lookup = {str(n["charityNeedId"]): n for n in needs}
        ordered = [lookup[id_] for id_ in cached_ids if id_ in lookup]
        if len(ordered) == len(needs):
            logger.info("Returned results from cache")
            return {
                "matchedCharityNeeds": ordered,
                "status": {
                    "successful": True,
                    "message": "Returned sorted charity needs from cache"
                }
            }, 200

    retry_count = 0
    while retry_count <= max_retries:
        try:
            prompt = build_prompt(donor, needs)

            # Use deterministic parameters to reduce output variability
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-3.5-turbo",
                    "temperature": 0,
                    "top_p": 1,
                    "frequency_penalty": 0,
                    "presence_penalty": 0,
                    "max_tokens": 2000,
                    "n": 1,
                    "messages": [
                        {"role": "system", "content": "You are a strict JSON-only matching assistant. Return only the requested JSON payload, no markdown, no explanation, and no extra fields."},
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=30
            )

            # Handle specific status codes
            if response.status_code == 200:
                # Validate response structure before parsing
                try:
                    data = response.json()
                    
                    # Validate required fields
                    if "choices" not in data or len(data["choices"]) == 0:
                        logger.error("Invalid AI response: missing 'choices' field")
                        return {
                            "matchedCharityNeeds": [],
                            "status": {
                                "successful": False,
                                "message": "Service returned invalid response format."
                            }
                        }, 500
                    
                    if "message" not in data["choices"][0]:
                        logger.error("Invalid AI response: missing message content")
                        return {
                            "matchedCharityNeeds": [],
                            "status": {
                                "successful": False,
                                "message": "Service returned invalid response format."
                            }
                        }, 500
                    
                    text = data["choices"][0]["message"]["content"]
                    cleaned = extract_json_object(text)
                    parsed = json.loads(cleaned)

                    # Normalize enum-like fields to numeric codes
                    normalize_enums_in_needs(parsed.get("matchedCharityNeeds", []))

                    sorted_ids = [item["charityNeedId"] for item in parsed.get("matchedCharityNeeds", [])]
                    if sorted_ids:
                        cache_sorted_ids(cache_key, sorted_ids)

                    logger.info(f"Successfully matched {len(sorted_ids)} charity needs")
                    return {
                        "matchedCharityNeeds": parsed.get("matchedCharityNeeds", []),
                        "status": parsed.get("status", {
                            "successful": True,
                            "message": "Matching completed successfully"
                        })
                    }, 200
                
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON parsing error: {str(json_err)}")
                    return {
                        "matchedCharityNeeds": [],
                        "status": {
                            "successful": False,
                            "message": "Service returned invalid data format."
                        }
                    }, 500
            
            # Retry for recoverable errors
            elif response.status_code in [429, 503]:
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.warning(f"Status {response.status_code}. Retrying in {wait_time} seconds (attempt {retry_count + 1}/{max_retries})")
                    time.sleep(wait_time)
                    retry_count += 1
                    continue
                else:
                    logger.error(f"Max retries reached for status {response.status_code}")
                    user_message = get_user_friendly_error(response.status_code)
                    return {
                        "matchedCharityNeeds": [],
                        "status": {
                            "successful": False,
                            "message": user_message
                        }
                    }, response.status_code
            
            # Handle other error status codes
            elif response.status_code in [400, 401]:
                logger.error(f"Client/Auth error {response.status_code}")
                user_message = get_user_friendly_error(response.status_code)
                return {
                    "matchedCharityNeeds": [],
                    "status": {
                        "successful": False,
                        "message": user_message
                    }
                }, response.status_code
            
            else:
                logger.error(f"Unexpected status code: {response.status_code}")
                return {
                    "matchedCharityNeeds": [],
                    "status": {
                        "successful": False,
                        "message": "An unexpected error occurred. Please try again later."
                    }
                }, response.status_code

        except requests.Timeout:
            logger.error("Request timeout")
            if retry_count < max_retries:
                retry_count += 1
                wait_time = 2 ** retry_count
                logger.warning(f"Timeout. Retrying in {wait_time} seconds")
                time.sleep(wait_time)
                continue
            else:
                return {
                    "matchedCharityNeeds": [],
                    "status": {
                        "successful": False,
                        "message": "Service request timed out. Please try again later."
                    }
                }, 504
        
        except requests.ConnectionError:
            logger.error("Connection error")
            return {
                "matchedCharityNeeds": [],
                "status": {
                    "successful": False,
                    "message": "Unable to connect to service. Please try again later."
                }
            }, 503
        
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
            return {
                "matchedCharityNeeds": [],
                "status": {
                    "successful": False,
                    "message": "An error occurred processing your request. Please try again later."
                }
            }, 500
        