import os
import requests
import json
from flask import Flask, request, jsonify
from google import genai
from google.genai import types
import datetime

app = Flask(__name__)

# ==========================================
# Environment Variables
# ==========================================
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "") # Meta Access Token
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "sabuj_secret_123") # Webhook Verify Token
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "") # Meta Phone Number ID
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
FIREBASE_URL = "https://sabuj-computers-default-rtdb.asia-southeast1.firebasedatabase.app"
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET", "")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "") # Admin WhatsApp Number (with country code e.g. 88017...)

def get_auth_param():
    return f"?auth={FIREBASE_SECRET}" if FIREBASE_SECRET else ""

# ==========================================
# AI ও ডাটাবেস সেটআপ
# ==========================================
def get_db(path):
    try:
        url = f"{FIREBASE_URL}/{path}.json{get_auth_param()}"
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Error reading DB: {e}")
    return None

def put_db(path, data):
    url = f"{FIREBASE_URL}/{path}.json{get_auth_param()}"
    res = requests.put(url, json=data)
    return res.json()
    
def patch_db(path, data):
    url = f"{FIREBASE_URL}/{path}.json{get_auth_param()}"
    res = requests.patch(url, json=data)
    return res.json()

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
    return response.json()

def send_whatsapp_interactive(to_number, text, buttons):
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    # For WhatsApp, max 3 buttons per interactive message.
    # Otherwise we use List message. Simple text fallback is best for large menus.
    pass

def send_main_menu(to_number):
    apps = get_db("sabuj/applications")
    total_students = len(apps) if apps and isinstance(apps, dict) else 1000
    
    bot_settings = get_db("sabuj/bot_settings") or {}
    custom_desc = bot_settings.get("welcome_text", "")
    
    if custom_desc:
        desc_text = custom_desc
    else:
        desc_text = f"✨ *৫+ বছরের অভিজ্ঞতা* | *{total_students}+ শিক্ষার্থী* | *১০০% সার্টিফিকেট গ্যারান্টি*"

    text = (
        "🌿 *সবুজ কম্পিউটার্সে আপনাকে স্বাগতম!*\n\n"
        "বাগাতিপাড়া, নাটোরের সেরা BTEB অনুমোদিত কম্পিউটার প্রশিক্ষণ কেন্দ্র।\n"
        f"{desc_text}\n\n"
        "আমি একটি স্মার্ট AI বট। আপনি যেকোনো প্রশ্ন টাইপ করে পাঠাতে পারেন অথবা নিচের কিওয়ার্ডগুলো লিখে সেন্ড করতে পারেন:\n\n"
        "🔖 *১.* কোর্সসমূহ (লিখুন `course`)\n"
        "💸 *২.* ফি তথ্য (লিখুন `fees`)\n"
        "📝 *৩.* ভর্তি তথ্য (লিখুন `admission`)\n"
        "🏆 *৪.* ফলাফল (লিখুন `results`)\n"
        "📢 *৫.* নোটিশ বোর্ড (লিখুন `notice`)\n"
        "📞 *৬.* যোগাযোগ (লিখুন `contact`)\n"
        "🔗 *৭.* অ্যাকাউন্ট লিঙ্ক করুন (লিখুন `link_account`)\n"
        "🎧 *৮.* অ্যাডমিনের সাথে কথা বলুন (লিখুন `talk_admin`)\n"
        "💰 *৯.* ফি স্ট্যাটাস দেখুন (লিখুন `due`)\n"
        "🧾 *১০.* রসিদ দেখুন (লিখুন `receipt`)\n"
        "📋 *১১.* হাজিরা দেখুন (লিখুন `attendance`)"
    )
    send_whatsapp_message(to_number, text)

# ==========================================
# মেসেজ প্রসেসিং
# ==========================================
def process_and_reply(sender_num, message_text):
    msg_lower = message_text.lower().strip()

    state_path = f"sabuj/whatsapp_users/{sender_num}/state"
    current_state = get_db(state_path)

    # 1. Answer specific states
    if current_state == "link_reg":
        apps = get_db("sabuj/applications") or {}
        found_key = None
        for key, details in apps.items():
            reg = details.get("regNo", "")
            phone = details.get("personal", {}).get("phone", "")
            if message_text == reg or message_text == phone:
                found_key = key
                break
        
        if found_key:
            patch_db(f"sabuj/whatsapp_users/{sender_num}", {"appId": found_key, "linkedAt": str(datetime.datetime.now()), "state": ""})
            text = (
                "✅ আপনার অ্যাকাউন্ট সফলভাবে লিঙ্ক হয়েছে! 🎉\n\n"
                "এখন আপনি নিচের অপশনগুলো ব্যবহার করতে পারবেন:\n"
                "🔹 `due` - বকেয়া ফি জানতে\n"
                "🔹 `attendance` - উপস্থিতির স্ট্যাটাস জানতে\n"
                "🔹 `receipt` - পেমেন্ট রসিদ পেতে"
            )
            send_whatsapp_message(sender_num, text)
        else:
            send_whatsapp_message(sender_num, "❌ কোনো তথ্য পাওয়া যায়নি। দয়া করে সঠিক ফোন বা রেজিস্ট্রেশন নম্বর দিয়ে পুনরায় চেষ্টা করুন:")
        return

    elif current_state == "talk_admin":
        patch_db(f"sabuj/whatsapp_users/{sender_num}", {"state": ""})
        if ADMIN_PHONE:
            try:
                # Notify admin
                admin_text = f"📨 *New Support Message from WhatsApp ({sender_num}):*\n\n{message_text}"
                send_whatsapp_message(ADMIN_PHONE, admin_text)
            except Exception as e:
                print(e)
        send_whatsapp_message(sender_num, "✅ আপনার মেসেজটি অ্যাডমিনের কাছে পাঠানো হয়েছে। রিপ্লাই পেলে এখানেই আপনার কাছে নোটিফিকেশন আসবে।")
        return

    # 2. Check keywords (Menu commands)
    if msg_lower in ["hi", "hello", "menu", "start"]:
        send_main_menu(sender_num)
        return
        
    elif msg_lower == "course" or msg_lower == "1":
        text = (
            "🎓 *আমাদের কোর্সসমূহ*\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ *ফাউন্ডেশন কোর্স*\n"
            "✅ মেয়াদ: ৬ মাস\n"
            "✅ সার্টিফিকেট: নিজস্ব সার্টিফিকেট\n\n"
            "2️⃣ *BTEB কোর্স*\n"
            "✅ মেয়াদ: ৬ মাস\n"
            "✅ সার্টিফিকেট: সরকারি (BTEB অনুমোদিত)\n\n"
            "📞 ভর্তির জন্য: 01724-084350"
        )
        send_whatsapp_message(sender_num, text)
        return
        
    elif msg_lower == "fees" or msg_lower == "2":
        text = (
            "💰 *ফি সংক্রান্ত তথ্য*\n\n"
            "🎓 *ফাউন্ডেশন কোর্স:* ৩৫০০ টাকা\n"
            "🏆 *BTEB কোর্স:* ৪৫০০ টাকা\n\n"
            "📞 যোগাযোগ: 01724-084350"
        )
        send_whatsapp_message(sender_num, text)
        return
        
    elif msg_lower == "admission" or msg_lower == "3":
        text = (
            "📝 *ভর্তি তথ্য*\n\n"
            "📋 ভর্তির জন্য যা লাগবে:\n"
            "• জাতীয় পরিচয়পত্র / জন্ম নিবন্ধন\n"
            "• ১ কপি পাসপোর্ট সাইজ ছবি\n\n"
            "⏰ অফিস সময়: সকাল ৯:০০ - দুপুর ১:৩০, বিকেল ৪:০০ - রাত ৮:৩০\n"
            "🔗 অনলাইন ভর্তি: https://sabujcomputers.pro.bd/admission-form.html"
        )
        send_whatsapp_message(sender_num, text)
        return
        
    elif msg_lower == "results" or msg_lower == "4":
        text = "🏆 *ফলাফল যাচাই*\n\nরেজাল্ট চেক করুন: https://sabujcomputers.pro.bd/verify.html"
        send_whatsapp_message(sender_num, text)
        return

    elif msg_lower == "notice" or msg_lower == "5":
        notices = get_db("sabuj/notices")
        text = "📢 *নোটিশ বোর্ড*\n\n"
        if notices and isinstance(notices, dict):
            sorted_notices = sorted(notices.items(), key=lambda x: x[1].get('date', ''), reverse=True)
            for i, (k, notice) in enumerate(sorted_notices[:3]):
                text += f"📌 *{notice.get('title', '')}* ({notice.get('date', '')})\n{notice.get('details', '')}\n\n"
        else:
            text += "বর্তমানে কোনো নোটিশ নেই।"
        send_whatsapp_message(sender_num, text)
        return
        
    elif msg_lower == "contact" or msg_lower == "6":
        text = "📞 *যোগাযোগ*\n\nফোন: 01724-084350\nইমেইল: sssabuj007@gmail.com\nঠিকানা: তমালতলা বাজার, বাগাতিপাড়া, নাটোর"
        send_whatsapp_message(sender_num, text)
        return

    elif msg_lower == "link_account" or msg_lower == "7":
        patch_db(f"sabuj/whatsapp_users/{sender_num}", {"state": "link_reg"})
        send_whatsapp_message(sender_num, "🔗 *অ্যাকাউন্ট লিঙ্ক করুন*\n\nআপনার ফোন নম্বর বা রেজিস্ট্রেশন নম্বর টাইপ করে সেন্ড করুন:")
        return

    elif msg_lower == "talk_admin" or msg_lower == "8":
        patch_db(f"sabuj/whatsapp_users/{sender_num}", {"state": "talk_admin"})
        send_whatsapp_message(sender_num, "🎧 *সরাসরি অ্যাডমিনের সাথে কথা বলুন*\n\nআপনার প্রশ্ন বা মেসেজটি এখন টাইপ করে সেন্ড করুন। অ্যাডমিন রিপ্লাই দেবেন।")
        return
        
    elif msg_lower == "due" or msg_lower == "9":
        linked = get_db(f"sabuj/whatsapp_users/{sender_num}")
        if linked and "appId" in linked:
            app_data = get_db(f"sabuj/applications/{linked['appId']}")
            if app_data:
                due = app_data.get("payment", {}).get("due", 0)
                paid = app_data.get("payment", {}).get("paid", 0)
                total = app_data.get("payment", {}).get("total", 0)
                text = f"💳 *ফি স্ট্যাটাস*\n\nমোট ফি: ৳{total}\nপরিশোধিত: ৳{paid}\n⚠️ *বকেয়া ফি: ৳{due}*"
                send_whatsapp_message(sender_num, text)
                return
        send_whatsapp_message(sender_num, "❌ আপনার অ্যাকাউন্টটি লিঙ্ক করা নেই। অনুগ্রহ করে 'link_account' লিখে সেন্ড করুন।")
        return
        
    elif msg_lower == "receipt" or msg_lower == "10":
        linked = get_db(f"sabuj/whatsapp_users/{sender_num}")
        if linked and "appId" in linked:
            app_data = get_db(f"sabuj/applications/{linked['appId']}")
            if app_data:
                name = app_data.get("personal", {}).get("nameEn", "শিক্ষার্থী")
                reg = app_data.get("regNo", "N/A")
                due = app_data.get("payment", {}).get("due", 0)
                paid = app_data.get("payment", {}).get("paid", 0)
                total = app_data.get("payment", {}).get("total", 0)
                text = f"🧾 *রসিদ*\n\nনাম: {name}\nরেজিস্ট্রেশন: {reg}\n\nমোট: ৳{total}\nপরিশোধিত: ৳{paid}\nবকেয়া: ৳{due}"
                send_whatsapp_message(sender_num, text)
                return
        send_whatsapp_message(sender_num, "❌ আপনার অ্যাকাউন্টটি লিঙ্ক করা নেই।")
        return

    elif msg_lower == "attendance" or msg_lower == "11":
        linked = get_db(f"sabuj/whatsapp_users/{sender_num}")
        if linked and "appId" in linked:
            app_data = get_db(f"sabuj/applications/{linked['appId']}")
            if app_data:
                name = app_data.get("personal", {}).get("nameBn", "শিক্ষার্থী")
                text = f"📋 *অ্যাটেনডেন্স - {name}*\n\nউপস্থিতির তথ্য ডাটাবেসে হালনাগাদ করা হচ্ছে। পোর্টালে দেখুন: https://sabujcomputers.pro.bd/portal.html"
                send_whatsapp_message(sender_num, text)
                return
        send_whatsapp_message(sender_num, "❌ আপনার অ্যাকাউন্টটি লিঙ্ক করা নেই।")
        return

    # Check if admin is replying to a target (Admin can do this directly from WhatsApp if they structure it)
    if sender_num == ADMIN_PHONE and msg_lower.startswith("/reply "):
        try:
            parts = message_text.split(" ", 2) # /reply phonenumber message
            target_num = parts[1]
            reply_text = parts[2]
            send_whatsapp_message(target_num, f"🎧 *অ্যাডমিনের রিপ্লাই:*\n\n{reply_text}")
            send_whatsapp_message(sender_num, f"✅ রিপ্লাই {target_num}-এ পাঠানো হয়েছে।")
            return
        except Exception:
            send_whatsapp_message(sender_num, "❌ Error in /reply format. Use: /reply +8801... message")
            return

    # 3. Smart AI Integration (Gemini)
    if ai_client:
        bot_settings = get_db("sabuj/bot_settings") or {}
        custom_system_prompt = bot_settings.get("system_prompt", "")
        
        system_prompt = custom_system_prompt if custom_system_prompt else (
            "You are a helpful AI assistant for 'Sabuj Computers Training Center', located in Bagatipara, Natore. "
            "You provide polite, human-like answers in Bengali. "
            "Always greet users with 'আসসালামু আলাইকুম'. "
            "Courses: Foundation (3500 BDT), BTEB (4500 BDT). Phone: 01724-084350."
            "If they want to know their fee/attendance, tell them to reply with the word 'due' or 'attendance'."
        )

        try:
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=message_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3
                )
            )
            send_whatsapp_message(sender_num, response.text)
        except Exception as e:
            print(f"AI Error: {e}")
            send_whatsapp_message(sender_num, "দুঃখিত, একটু সার্ভার ত্রুটি হচ্ছে। অনুগ্রহ করে মেনু দেখতে 'menu' লিখুন।")
    else:
        send_whatsapp_message(sender_num, "আমি বুঝতে পারিনি। অনুগ্রহ করে 'menu' লিখে সব অপশনগুলো দেখুন।")

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
    return "Hello from WhatsApp Bot Webhook Verification", 200

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
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

