from flask import Flask, request, jsonify, Response
import requests
import uuid
import json
import re
from datetime import datetime, timedelta

app = Flask(__name__)

BASE_URL = "https://deniai.app"
API_URL = f"{BASE_URL}/api/chat"

COOKIES = {
    "__Secure-better-auth.session_token": "rr35rsYZuZ2mSEAZscQjEl10qQkxhjez.LqPP%2Bg02TrGOi0snadyIi34qNtI3J8lkXuruq80tPf0%3D",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}

user_memory = {}
MAX_MSG = 300
MAX_AGE = timedelta(hours=24)

def get_uid():
    return f"user_{request.remote_addr or 'unknown'}"

def clean():
    now = datetime.now()
    for uid in list(user_memory.keys()):
        if now - user_memory[uid].get("last", now) > MAX_AGE:
            del user_memory[uid]

def session():
    clean()
    uid = get_uid()
    if uid not in user_memory:
        user_memory[uid] = {"msg": [], "last": datetime.now()}
    else:
        user_memory[uid]["last"] = datetime.now()
    return user_memory[uid]["msg"]

def add_msg(role, text):
    msgs = session()
    msgs.append({"parts": [{"type": "text", "text": text}], "id": str(uuid.uuid4())[:16], "role": role})
    if len(msgs) > MAX_MSG:
        msgs.pop(0)
        msgs.pop(0)

def fix_arabic(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def parse_sse(resp):
    t = ""
    for c in resp.iter_content(chunk_size=1, decode_unicode=True):
        if c: t += c
    deltas = re.findall(r'"text-delta"[^}]*"delta":"([^"]*)"', t)
    return fix_arabic(''.join(deltas))

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
    resp = requests.post(API_URL, headers=HEADERS, cookies=COOKIES, json=payload, stream=True, timeout=30)
    if resp.status_code == 200:
        return parse_sse(resp)
    return None

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    if not data or 'message' not in data:
        return Response(
            json.dumps({"reply": "أرسل {'message': 'نص'}", "model": "gpt-5.5"}, ensure_ascii=False),
            status=400,
            mimetype='application/json; charset=utf-8'
        )
    
    user_text = data['message']
    msgs = session()
    add_msg("user", user_text)
    reply = call_deni(msgs)
    
    if reply:
        add_msg("assistant", reply)
        return Response(
            json.dumps({"reply": reply, "model": "gpt-5.5"}, ensure_ascii=False),
            mimetype='application/json; charset=utf-8'
        )
    else:
        if msgs and msgs[-1]["role"] == "user":
            msgs.pop()
        return Response(
            json.dumps({"reply": "عذراً، حدث خطأ.", "model": "gpt-5.5"}, ensure_ascii=False),
            status=502,
            mimetype='application/json; charset=utf-8'
        )

@app.route('/reset', methods=['POST'])
def reset():
    uid = get_uid()
    if uid in user_memory:
        del user_memory[uid]
    return Response(
        json.dumps({"reply": "تم مسح الذاكرة", "model": "system"}, ensure_ascii=False),
        mimetype='application/json; charset=utf-8'
    )

@app.route('/')
def home():
    return Response(
        json.dumps({"reply": "Deni AI API شغال! استخدم /chat", "model": "system"}, ensure_ascii=False),
        mimetype='application/json; charset=utf-8'
    )

if __name__ == "__main__":
    app.run(debug=True)
