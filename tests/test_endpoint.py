import json
import traceback
import requests
from fastapi.testclient import TestClient
from app.main import app

with open('test_payload.json', 'r', encoding='utf-8') as f:
    payload = json.load(f)

client = TestClient(app)

# Mock requests.post used by ai_service
orig_post = requests.post

def fake_post(*args, **kwargs):
    class Resp:
        status_code = 200
        def json(self):
            return {
                'choices': [
                    {'message': {'content': json.dumps({'matchedCharityNeeds': payload['charityNeeds'], 'status': {'successful': True, 'message': 'ok'}})}}
                ]
            }
    return Resp()

requests.post = fake_post

try:
    resp = client.post('/match', json=payload)
    print('STATUS CODE:', resp.status_code)
    print('RESPONSE:', resp.text)
except Exception:
    traceback.print_exc()
finally:
    requests.post = orig_post
