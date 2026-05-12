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
    "_ga_B5H8G73JTN": "GS2.1.s1778523319$o1$g1$t1778523410$j52$l0$h0"
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

def clean_old():
    now = datetime.now()
    for uid in list(user_memory.keys()):
        if now - user_memory[uid].get("last", now) > MAX_AGE:
            del user_memory[uid]

def session():
    clean_old()
    uid = get_uid()
    if uid not in user_memory:
        user_memory[uid] = {"msg": [], "last": datetime.now()}
    else:
        user_memory[uid]["last"] = datetime.now()
    return user_memory[uid]["msg"]

def add_msg(role, text):
    msgs = session()
    msgs.append({
        "parts": [{"type": "text", "text": text}],
        "id": str(uuid.uuid4())[:16],
        "role": role
    })
    if len(msgs) > MAX_MSG:
        msgs.pop(0)
        msgs.pop(0)

def fix_arabic(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def clean_text(text):
    # استبدال \\n بسطر جديد فعلي
    text = text.replace('\\n', '\n')
    # تنظيف المسافات
    text = text.strip()
    return text

def parse_sse(resp):
    t = ""
    for c in resp.iter_content(chunk_size=1, decode_unicode=True):
        if c:
            t += c
    deltas = re.findall(r'"text-delta"[^}]*"delta":"([^"]*)"', t)
    result = fix_arabic(''.join(deltas))
    result = clean_text(result)
    return result

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

def json_response(data, status=200):
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        status=status,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    if not data or 'message' not in data:
        return json_response({
            "reply": "أرسل {'message': 'نص'}",
            "model": "gpt-5.5"
        }, 400)
    
    user_text = data['message']
    msgs = session()
    add_msg("user", user_text)
    reply = call_deni(msgs)
    
    if reply:
        add_msg("assistant", reply)
        return json_response({
            "reply": reply,
            "model": "gpt-5.5"
        })
    else:
        if msgs and msgs[-1]["role"] == "user":
            msgs.pop()
        return json_response({
            "reply": "عذراً، حدث خطأ.",
            "model": "gpt-5.5"
        }, 502)

@app.route('/ask')
def ask():
    msg = request.args.get('q', '')
    if not msg:
        return json_response({
            "reply": "استخدم ?q=سؤالك",
            "model": "gpt-5.5"
        })
    
    msgs = session()
    add_msg("user", msg)
    reply = call_deni(msgs)
    
    if reply:
        add_msg("assistant", reply)
        return json_response({
            "reply": reply,
            "model": "gpt-5.5"
        })
    else:
        return json_response({
            "reply": "عذراً، حدث خطأ",
            "model": "gpt-5.5"
        }, 502)

@app.route('/reset', methods=['POST'])
def reset():
    uid = get_uid()
    if uid in user_memory:
        del user_memory[uid]
    return json_response({
        "reply": "تم مسح الذاكرة",
        "model": "gpt-5.5"
    })

@app.route('/')
def home():
    return json_response({
        "reply": "Deni AI API",
        "model": "gpt-5.5",
        "endpoints": {
            "chat": "/chat (POST)",
            "ask": "/ask?q=سؤالك",
            "reset": "/reset (POST)"
        }
    })

if __name__ == "__main__":
    app.run(debug=True)
