import os
import requests
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

# ==========================================
# Environment Variables (Railway তে সেট করতে হবে)
# ==========================================
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "") # Meta Access Token
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "sabuj_secret_123") # Webhook Verify Token
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "") # Meta Phone Number ID
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
FIREBASE_URL = "https://sabuj-computers-default-rtdb.asia-southeast1.firebasedatabase.app"
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET", "")

# ==========================================
# AI ও ডাটাবেস সেটআপ
# ==========================================
def get_auth_param():
    return f"?auth={FIREBASE_SECRET}" if FIREBASE_SECRET else ""

def get_db(path):
    try:
        url = f"{FIREBASE_URL}/{path}.json{get_auth_param()}"
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Error reading DB: {e}")
    return None

ai_client = None
if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Failed to init Gemini: {e}")

# ==========================================
# WhatsApp-এ মেসেজ পাঠানোর ফাংশন
# ==========================================
def send_whatsapp_message(to_number, text):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Error: WhatsApp Token or Phone ID is missing.")
        return

    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    
    response = requests.post(url, headers=headers, json=data)
    print("WhatsApp Response:", response.json())
    return response.json()

def process_and_reply(sender_num, message_text):
    # কমান্ড বা সাধারণ চ্যাটের জন্য (যেমন টেলিগ্রামে ছিল)
    bot_settings = get_db("sabuj/bot_settings") or {}
    custom_system_prompt = bot_settings.get("system_prompt", "")
    
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = (
            "You are a helpful AI assistant for 'Sabuj Computers Training Center', located in Bagatipara, Natore. "
            "You provide polite, human-like answers in Bengali. "
            "Always greet users with 'আসসালামু আলাইকুম'. "
            "Keep it short and formatted for WhatsApp."
        )

    # Gemini AI থেকে রিপ্লাই তৈরি করা
    if ai_client:
        try:
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=message_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3
                )
            )
            reply_text = response.text
        except Exception as e:
            print(f"AI Error: {e}")
            reply_text = "দুঃখিত, একটু সার্ভার ত্রুটি হচ্ছে। পরে আবার চেষ্টা করুন।"
    else:
        reply_text = "AI সিস্টেম এখন বন্ধ আছে।"

    # WhatsApp-এ পাঠিয়ে দেওয়া
    send_whatsapp_message(sender_num, reply_text)

# ==========================================
# Webhook এন্ডপয়েন্ট (Meta-র সাথে কানেক্ট করতে)
# ==========================================
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """Meta যখন Webhook কনফিগার করবে তখন এটি ভেরিফাই করবে"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return "Verification token mismatch", 403
    return "Hello from WhatsApp Bot", 200

@app.route('/webhook', methods=['POST'])
def handle_webhook_messages():
    """ইউজার যখন মেসেজ দেবে তখন এখানে রিসিভ হবে"""
    body = request.get_json()

    if body.get("object"):
        # মেসেজের ডিটেইলস পার্স করা
        if body.get("entry") and body["entry"][0].get("changes") and body["entry"][0]["changes"][0].get("value").get("messages"):
            message_data = body["entry"][0]["changes"][0]["value"]["messages"][0]
            
            sender_phone = message_data.get("from") # ইউজারের ফোন নাম্বার
            msg_type = message_data.get("type")

            if msg_type == "text":
                text_content = message_data["text"]["body"]
                print(f"Received from {sender_phone}: {text_content}")
                
                # প্রসেস ও রিপ্লাই
                process_and_reply(sender_phone, text_content)
                
        return "EVENT_RECEIVED", 200
    else:
        return "404 Not Found", 404

if __name__ == "__main__":
    # Railway-তে ডিফল্ট পোর্ট অনুযায়ী চলবে
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
