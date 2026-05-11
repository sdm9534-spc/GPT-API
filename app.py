from flask import Flask, request, jsonify
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

# ========== الذاكرة ==========
user_memory = {}
MAX_MESSAGES = 300
MAX_AGE = timedelta(hours=24)

def get_user_id():
    ip = request.remote_addr or "unknown"
    return f"user_{ip}"

def clean_old_sessions():
    now = datetime.now()
    to_delete = [uid for uid, data in user_memory.items() if now - data.get("last_active", now) > MAX_AGE]
    for uid in to_delete:
        del user_memory[uid]

def get_or_create_session():
    clean_old_sessions()
    user_id = get_user_id()
    
    if user_id not in user_memory:
        user_memory[user_id] = {
            "messages": [],
            "last_active": datetime.now()
        }
    else:
        user_memory[user_id]["last_active"] = datetime.now()
    
    return user_memory[user_id]["messages"]

def add_to_memory(role, text):
    messages = get_or_create_session()
    messages.append({
        "parts": [{"type": "text", "text": text}],
        "id": str(uuid.uuid4())[:16],
        "role": role
    })
    
    if len(messages) > MAX_MESSAGES:
        messages.pop(0)
        messages.pop(0)

def fix_arabic(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def parse_sse(response):
    text = ""
    for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
        if chunk:
            text += chunk
    deltas = re.findall(r'"text-delta"[^}]*"delta":"([^"]*)"', text)
    return fix_arabic(''.join(deltas))

def send_to_deni(messages):
    payload = {
        "id": "417ae263-8147-4de9-9156-da577a284ba7",
        "model": "gpt-5.5",
        "webSearch": False,
        "reasoningEffort": "high",
        "video": False,
        "image": False,
        "deepResearch": False,
        "messages": messages,
        "trigger": "submit-message"
    }
    
    resp = requests.post(API_URL, headers=HEADERS, cookies=COOKIES, json=payload, stream=True, timeout=30)
    if resp.status_code == 200:
        return parse_sse(resp)
    return None

# ========== نقطة النهاية ==========
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    if not data or 'message' not in data:
        return jsonify({"reply": "أرسل {'message': 'نص'}", "model": "gpt-5.5"}), 400
    
    user_text = data['message']
    messages = get_or_create_session()
    
    add_to_memory("user", user_text)
    reply = send_to_deni(messages)
    
    if reply:
        add_to_memory("assistant", reply)
        return jsonify({
            "reply": reply,
            "model": "gpt-5.5"
        })
    else:
        if messages and messages[-1]["role"] == "user":
            messages.pop()
        return jsonify({
            "reply": "عذراً، حدث خطأ. حاول مرة أخرى.",
            "model": "gpt-5.5"
        }), 502

# ========== مسح الذاكرة ==========
@app.route('/reset', methods=['POST'])
def reset():
    user_id = get_user_id()
    if user_id in user_memory:
        del user_memory[user_id]
        return jsonify({"reply": "تم مسح الذاكرة", "model": "system"})
    return jsonify({"reply": "لا توجد ذاكرة", "model": "system"})

# ========== الصفحة الرئيسية ==========
@app.route('/')
def home():
    return jsonify({
        "reply": "Deni AI API شغال! استخدم /chat",
        "model": "system"
    })

if __name__ == "__main__":
    app.run(debug=True)