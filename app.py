from flask import Flask, request, Response
from flask_compress import Compress
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uuid
import json
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading

app = Flask(__name__)
Compress(app)

BASE_URL = "https://deniai.app"
API_URL = f"{BASE_URL}/api/chat"

COOKIES = {
    "__Secure-better-auth.session_token": "rr35rsYZuZ2mSEAZscQjEl10qQkxhjez.LqPP%2Bg02TrGOi0snadyIi34qNtI3J8lkXuruq80tPf0%3D",
    "better-auth.last_used_login_method": "google",
    "_ga": "GA1.1.1232790527.1778523320",
    "_ga_B5H8G73JTN": "GS2.1.s1778523319$o1$g1$t1778523410$j52$l0$h0"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

session = requests.Session()
retry_strategy = Retry(total=2, backoff_factor=0.1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=retry_strategy, pool_block=False)
session.mount("https://", adapter)

executor = ThreadPoolExecutor(max_workers=10)
memory_lock = threading.Lock()
user_memory = {}
MAX_MSG = 300
MAX_AGE = timedelta(hours=24)

MODELS = {
    "gpt-5.5": "GPT-5.5",
    "r1": "DeepSeek R1",
    "deepseek": "DeepSeek R1",
    "deepseek-r1": "DeepSeek R1",
}

request_counter = 0
counter_lock = threading.Lock()

def pick_model(data=None):
    global request_counter
    
    # لو المستخدم حدد model=r1
    if data and data.get("model") in MODELS:
        return data["model"]
    
    # تقسيم تلقائي: 60% R1, 40% GPT-5.5
    with counter_lock:
        request_counter += 1
        if request_counter % 10 < 6:
            return "r1"
        else:
            return "gpt-5.5"

def get_uid():
    try:
        return f"user_{request.remote_addr or 'unknown'}"
    except:
        return "user_unknown"

def get_session():
    uid = get_uid()
    with memory_lock:
        if uid not in user_memory:
            user_memory[uid] = {"msg": [], "last": datetime.now()}
        else:
            user_memory[uid]["last"] = datetime.now()
        return user_memory[uid]["msg"]

def add_msg(role, text):
    msgs = get_session()
    with memory_lock:
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
    try:
        return text.replace('\\n', '\n').replace('\\', '').strip()
    except:
        return text

def parse_sse(resp):
    try:
        t = ""
        for c in resp.iter_content(chunk_size=512, decode_unicode=True):
            if c: t += c
        deltas = re.findall(r'"text-delta"[^}]*"delta":"([^"]*)"', t)
        return clean_text(fix_arabic(''.join(deltas)))
    except:
        return None

def call_deni_sync(msgs, model):
    try:
        payload = {
            "id": "417ae263-8147-4de9-9156-da577a284ba7",
            "model": model,
            "webSearch": False,
            "reasoningEffort": "high",
            "video": False,
            "image": False,
            "deepResearch": False,
            "messages": msgs,
            "trigger": "submit-message"
        }
        resp = session.post(API_URL, headers=HEADERS, cookies=COOKIES, json=payload, stream=True, timeout=6)
        if resp.status_code == 200:
            return parse_sse(resp)
        return None
    except:
        return None

def call_deni(msgs, model):
    try:
        future = executor.submit(call_deni_sync, msgs, model)
        return future.result(timeout=7)
    except TimeoutError:
        return None
    except:
        return None

def ok(reply, model):
    data = {
        "model_used": MODELS.get(model, model),
        "reply": reply,
        "status": "success"
    }
    return Response(json.dumps(data, ensure_ascii=False, indent=2), mimetype='application/json; charset=utf-8')

def err(msg, code=400, model="gpt-5.5"):
    data = {
        "model_used": MODELS.get(model, model),
        "reply": msg,
        "status": "error"
    }
    return Response(json.dumps(data, ensure_ascii=False, indent=2), status=code, mimetype='application/json; charset=utf-8')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        if not data or 'message' not in data:
            return err("أرسل {'message':'نص'} أو {'message':'نص','model':'r1'}")
        
        user_text = data['message']
        model = pick_model(data)
        
        msgs = get_session()
        add_msg("user", user_text)
        reply = call_deni(msgs, model)
        
        if reply:
            add_msg("assistant", reply)
            return ok(reply, model)
        else:
            if msgs and msgs[-1]["role"] == "user":
                with memory_lock:
                    msgs.pop()
            return err("عذراً، حدث خطأ.", 502, model)
    except:
        return err("خطأ داخلي", 500)

@app.route('/ask')
def ask():
    try:
        msg = request.args.get('q', '')
        if not msg:
            return err("استخدم ?q=سؤالك")
        
        model = pick_model()
        
        msgs = get_session()
        add_msg("user", msg)
        reply = call_deni(msgs, model)
        
        if reply:
            add_msg("assistant", reply)
            return ok(reply, model)
        else:
            return err("عذراً، حدث خطأ", 502, model)
    except:
        return err("خطأ داخلي", 500)

@app.route('/reset', methods=['POST'])
def reset():
    uid = get_uid()
    with memory_lock:
        if uid in user_memory:
            del user_memory[uid]
    return ok("تم مسح الذاكرة", "gpt-5.5")

@app.route('/')
def home():
    return Response(json.dumps({
        "model_used": "System",
        "reply": "API AI WORK",
        "status": "success",
        "usage": "/chat أو /ask?q=...",
    }, ensure_ascii=False, indent=2), mimetype='application/json; charset=utf-8')

if __name__ == "__main__":
    app.run(debug=True)
