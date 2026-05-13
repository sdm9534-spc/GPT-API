from flask import Flask, request, Response
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
    "better-auth.last_used_login_method": "google",
    "_ga": "GA1.1.1232790527.1778523320",
    "_ga_B5H8G73JTN": "GS2.1.s1778707122$o2$g1$t1778707731$j56$l0$h0"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}

session = requests.Session()
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
    return text.replace('\\n', '\n').strip()

def parse_sse(resp):
    t = ""
    for c in resp.iter_content(chunk_size=512, decode_unicode=True):
        if c: t += c
    deltas = re.findall(r'"text-delta"[^}]*"delta":"([^"]*)"', t)
    return clean_text(fix_arabic(''.join(deltas)))

def call_deni(msgs):
    try:
        payload = {
            "id": "5e0ae8e9-2956-4399-a4aa-98e76b3fd50f",
            "model": "gpt-5.5",
            "webSearch": False,
            "reasoningEffort": "high",
            "deepResearch": False,
            "video": False,
            "image": False,
            "messages": msgs,
            "trigger": "submit-message"
        }
        resp = session.post(API_URL, headers=HEADERS, cookies=COOKIES, json=payload, stream=True, timeout=6)
        if resp.status_code == 200:
            return parse_sse(resp)
        return None
    except:
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
        # ⭐ نضيف رسالة المستخدم
        msgs.append({"parts": [{"type": "text", "text": data['message']}], "id": str(uuid.uuid4())[:16], "role": "user"})
        # ⭐ نبعت كل تاريخ المحادثة
        reply = call_deni(msgs)
        
        if reply:
            # ⭐ نضيف رد البوت
            msgs.append({"id": str(uuid.uuid4())[:16], "role": "assistant", "parts": [{"type": "step-start"}, {"type": "text", "text": reply, "state": "done"}]})
            return ok(reply)
        else:
            msgs.pop()
            return err("عذراً، حدث خطأ.", 502)
    except:
        return err("خطأ داخلي", 500)

@app.route('/ask')
def ask():
    try:
        msg = request.args.get('q', '')
        if not msg:
            return err("استخدم ?q=سؤالك")
        
        msgs = get_session()
        msgs.append({"parts": [{"type": "text", "text": msg}], "id": str(uuid.uuid4())[:16], "role": "user"})
        reply = call_deni(msgs)
        
        if reply:
            msgs.append({"id": str(uuid.uuid4())[:16], "role": "assistant", "parts": [{"type": "step-start"}, {"type": "text", "text": reply, "state": "done"}]})
            return ok(reply)
        else:
            msgs.pop()
            return err("عذراً، حدث خطأ", 502)
    except:
        return err("خطأ داخلي", 500)

@app.route('/reset', methods=['POST'])
def reset():
    uid = get_uid()
    if uid in user_memory:
        del user_memory[uid]
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
