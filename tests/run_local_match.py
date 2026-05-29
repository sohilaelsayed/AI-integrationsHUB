import json
import traceback
import requests
from app.services.ai_service import match_with_ai

with open('test_payload.json', 'r', encoding='utf-8') as f:
    payload = json.load(f)

donor = payload['donor']
needs = payload['charityNeeds']

# Mock requests.post to return a well-formed AI response
orig_post = requests.post

def fake_post(*args, **kwargs):
    class Resp:
        status_code = 200
        def json(self):
            # Return the needs unchanged to simulate AI returning same list
            return {
                'choices': [
                    {'message': {'content': json.dumps({'matchedCharityNeeds': needs, 'status': {'successful': True, 'message': 'ok'}})}}
                ]
            }
    return Resp()

requests.post = fake_post

try:
    result, status = match_with_ai(donor, needs)
    print('STATUS:', status)
    print(json.dumps(result, indent=2))
except Exception:
    traceback.print_exc()
finally:
    requests.post = orig_post
