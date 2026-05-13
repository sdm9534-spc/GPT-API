from flask import Flask, request, Response
import requests
import json
import urllib.parse

app = Flask(__name__)

API_URL = "http://de3.bot-hosting.net:21007/kilwa-chatgpt"

def ok(reply):
    return Response(
        json.dumps({
            "model_used": "GPT-5 Nano",
            "reply": reply,
            "status": "success"
        }, ensure_ascii=False, indent=2),
        mimetype='application/json; charset=utf-8'
    )

def err(msg):
    return Response(
        json.dumps({
            "model_used": "GPT-5 Nano",
            "reply": msg,
            "status": "error"
        }, ensure_ascii=False, indent=2),
        mimetype='application/json; charset=utf-8'
    )

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        if not data or 'message' not in data:
            return err("أرسل {'message':'نص'}")
        
        user_text = data['message']
        
        # ترميز النص العربي للـ URL
        encoded = urllib.parse.quote(user_text)
        
        # إرسال للـ API الوسيط
        resp = requests.get(f"{API_URL}?text={encoded}", timeout=5)
        result = resp.json()
        
        if result.get("status") == "success":
            return ok(result.get("reply", ""))
        else:
            return err("خطأ من الخادم")
    except:
        return err("خطأ داخلي")

@app.route('/ask')
def ask():
    try:
        msg = request.args.get('q', '')
        if not msg:
            return err("استخدم ?q=سؤالك")
        
        # ترميز النص
        encoded = urllib.parse.quote(msg)
        
        # إرسال
        resp = requests.get(f"{API_URL}?text={encoded}", timeout=5)
        result = resp.json()
        
        if result.get("status") == "success":
            return ok(result.get("reply", ""))
        else:
            return err("خطأ من الخادم")
    except:
        return err("خطأ داخلي")

@app.route('/')
def home():
    return ok("API GPT-5 Nano")

if __name__ == "__main__":
    app.run(debug=True)
