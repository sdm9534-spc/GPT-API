from flask import Flask, request, Response
from flask_compress import Compress
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uuid
import json
import re
from datetime import datetime, timedelta

app = Flask(__name__)
Compress(app)

BASE_URL = "https://deniai.app"
API_URL = f"{BASE_URL}/api/chat"

COOKIES = {
    "__Secure-better-auth.session_token": "rr35rsYZuZ2mSEAZscQjEl10qQkxhjez.LqPP%2Bg02TrGOi0snadyIi34qNtI3J8lkXuruq80tPf0%3D",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ⚡ السرعة القصوى: Connection Pooling
session = requests.Session()
retry_strategy = Retry(total=2, backoff_factor=0.1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=retry_strategy, pool_block=False)
session.mount("https://", adapter)

# 🛡️ الاستقرار
user_memory = {}
MAX_MSG = 300
MAX_AGE = timedelta(hours=24)

def get_uid():
    return f"user_{request.remote_addr or 'unknown'}"

def get_session():
    uid = get_uid()
    if uid not in user_memory:
        user_memory[uid] = []
    return user_memory[uid]

def fix_arabic(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def clean_text(text):
    return text.replace('\\n', '\n').replace('\\', '').strip()

def parse_sse(resp):
    t = ""
    for c in resp.iter_content(chunk_size=512, decode_unicode=True):
        if c: t += c
    deltas = re.findall(r'"text-delta"[^}]*"delta":"([^"]*)"', t)
    return clean_text(fix_arabic(''.join(deltas)))

def call_deni(msgs):
    payload = {
        "id": "417ae263-8147-4de9-9156-da577a284ba7",
        "model": "gpt-5.5",
        "webSearch": False,
        "reasoningEffort": "high",
        "video": False,
        "image": False,
        "deepResearch": False,
        "messages": msgs,
        "trigger": "submit-message"
    }
    resp = session.post(API_URL, headers=HEADERS, cookies=COOKIES, json=payload, stream=True, timeout=4)
    if resp.status_code == 200:
        return parse_sse(resp)
    return None

def ok(reply):
    return Response(
        json.dumps({"model_used": "GPT-5.5", "reply": reply, "status": "success"}, ensure_ascii=False, indent=2),
        mimetype='application/json; charset=utf-8'
    )

def err(msg, code=400):
    return Response(
        json.dumps({"model_used": "GPT-5.5", "reply": msg, "status": "error"}, ensure_ascii=False, indent=2),
        status=code, mimetype='application/json; charset=utf-8'
    )

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        if not data or 'message' not in data:
            return err("أرسل {'message':'نص'}")
        
        msgs = get_session()
        msgs.append({"parts": [{"type": "text", "text": data['message']}], "id": str(uuid.uuid4())[:16], "role": "user"})
        reply = call_deni(msgs)
        
        if reply:
            msgs.append({"parts": [{"type": "text", "text": reply}], "id": str(uuid.uuid4())[:16], "role": "assistant"})
            return ok(reply)
        else:
            msgs.pop()
            return err("عذراً، حدث خطأ.", 502)
    except:
        return err("خطأ داخلي", 500)

@app.route('/ask')
def ask():
    msg = request.args.get('q', '')
    if not msg: return err("استخدم ?q=سؤالك")
    
    msgs = get_session()
    msgs.append({"parts": [{"type": "text", "text": msg}], "id": str(uuid.uuid4())[:16], "role": "user"})
    reply = call_deni(msgs)
    
    if reply:
        msgs.append({"parts": [{"type": "text", "text": reply}], "id": str(uuid.uuid4())[:16], "role": "assistant"})
        return ok(reply)
    else:
        msgs.pop()
        return err("عذراً، حدث خطأ", 502)

@app.route('/reset', methods=['POST'])
def reset():
    uid = get_uid()
    if uid in user_memory: del user_memory[uid]
    return ok("تم مسح الذاكرة")

@app.route('/')
def home():
    return Response(json.dumps({
        "model_used": "GPT-5.5",
        "reply": "API GPT WORK",
        "status": "success"
    }, ensure_ascii=False, indent=2), mimetype='application/json; charset=utf-8')

if __name__ == "__main__":
    app.run(debug=True)
