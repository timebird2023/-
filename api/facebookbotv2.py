import os
import json
import requests
from flask import Flask, request
import logging
from collections import defaultdict

# ====================================================================
# 📚 الإعدادات الأساسية
# ====================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 🔑 التوكنات (تأكد من إضافتها في إعدادات Vercel)
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'boykta2025')
PAGE_ACCESS_TOKEN = "EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9"

# 🌐 الروابط
AI_API_URL = "http://fi8.bot-hosting.net:20163/elos-gpt3"
OCR_API_URL = "https://api.ocr.space/parse/image"
OCR_API_KEY = "helloworld" # مفتاح مجاني

# معرفات "الجام" (Like Sticker) في ماسنجر لتحديدها عند الاستقبال
LIKE_STICKER_IDS = [
    369239263222822, # صغير
    369239343222814, # وسط
    369239383222810, # كبير
]

# ذاكرة المحادثة
in_memory_conversations = defaultdict(list)

# ====================================================================
# 🛠️ دوال الإرسال
# ====================================================================

def send_api_request(payload):
    params = {'access_token': PAGE_ACCESS_TOKEN}
    try:
        response = requests.post(
            'https://graph.facebook.com/v19.0/me/messages',
            params=params, json=payload, timeout=10
        )
        if response.status_code != 200:
            logger.error(f"❌ FB API Error: {response.text}")
    except Exception as e:
        logger.error(f"❌ Connection Error: {e}")

def send_text_message(recipient_id, text):
    """إرسال رسالة نصية (أو إيموجي)"""
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': text}
    }
    send_api_request(payload)

def send_image_url(recipient_id, image_url):
    """إرسال صورة (لخدمة التوليد)"""
    payload = {
        'recipient': {'id': recipient_id},
        'message': {
            'attachment': {
                'type': 'image',
                'payload': {'url': image_url, 'is_reusable': True}
            }
        }
    }
    send_api_request(payload)

# ====================================================================
# 🧠 المنطق الذكي
# ====================================================================

def process_ai_logic(user_id, user_text):
    """الذكاء الاصطناعي يقرر: رسم أم محادثة"""
    
    # التعليمات للنموذج
    system_instruction = (
        "Instructions: You are a smart assistant. Check the user's request. "
        "If the user specifically asks to CREATE or DRAW an image, reply starting with 'CMD_IMAGE:' followed by the English description. "
        "Example: 'CMD_IMAGE: A flying car'. "
        "If it is a normal chat, reply normally in the user's language. "
        f"\nUser Request: {user_text}"
    )

    try:
        response = requests.get(AI_API_URL, params={'text': system_instruction}, timeout=45)
        if response.ok:
            ai_reply = response.text.strip()
            
            # تنظيف الرد
            try:
                json_data = json.loads(ai_reply)
                if isinstance(json_data, dict):
                    ai_reply = json_data.get('response', json_data.get('reply', ai_reply))
            except:
                pass

            # التحقق من النية
            if "CMD_IMAGE:" in ai_reply:
                # استخراج الوصف والرسم
                image_prompt = ai_reply.split("CMD_IMAGE:", 1)[1].strip().split('\n')[0]
                send_text_message(user_id, f"🎨 جاري الرسم: {image_prompt}")
                
                safe_prompt = requests.utils.quote(image_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?nologo=true"
                send_image_url(user_id, image_url)
            else:
                # محادثة عادية
                in_memory_conversations[user_id].append(user_text)
                send_text_message(user_id, ai_reply)
        else:
            send_text_message(user_id, "⚠️ الخادم مشغول، حاول لاحقاً.")
    except Exception as e:
        logger.error(f"AI Error: {e}")
        send_text_message(user_id, "حدث خطأ في الاتصال.")

def process_ocr(user_id, image_url):
    """تحليل الصورة (OCR)"""
    send_text_message(user_id, "🔍 جاري استخراج النص...")
    try:
        payload = {'apikey': OCR_API_KEY, 'url': image_url, 'language': 'ara', 'isOverlayRequired': False}
        response = requests.post(OCR_API_URL, data=payload, timeout=20)
        
        if response.ok:
            result = response.json()
            if result.get('ParsedResults'):
                text = result['ParsedResults'][0].get('ParsedText', '').strip()
                if text:
                    send_text_message(user_id, f"✅ النص المستخرج:\n\n{text}")
                else:
                    send_text_message(user_id, "❓ الصورة واضحة ولكن لا يوجد نص.")
            else:
                send_text_message(user_id, "⚠️ لم أنجح في قراءة النص.")
        else:
            send_text_message(user_id, "⚠️ خدمة الصور مشغولة.")
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        send_text_message(user_id, "خطأ غير متوقع.")

# ====================================================================
# 🌐 Webhook
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. التحقق (Verification)
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Error', 403

    # 2. الاستقبال (Processing)
    elif request.method == 'POST':
        data = request.get_json()
        if data:
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    if 'delivery' in event or 'read' in event: continue

                    # أ. التعامل مع "الجام" (Like Sticker)
                    if event.get('message') and 'sticker_id' in event['message']:
                        sticker_id = event['message']['sticker_id']
                        # تحقق إذا كان الستيكر هو أحد ملصقات اللايك المعروفة
                        if sticker_id in LIKE_STICKER_IDS:
                            # الرد بـ 👍 مباشرة
                            send_text_message(sender_id, "👍")
                        else:
                            # أي ستيكر آخر نرد عليه بـ لايك أيضاً للمجاملة
                            send_text_message(sender_id, "👍")
                        continue 

                    # ب. التعامل مع الصور المرفقة (OCR)
                    if event.get('message') and event['message'].get('attachments'):
                        for attachment in event['message']['attachments']:
                            if attachment['type'] == 'image':
                                # تأكد أنها ليست صورة ستيكر
                                if 'sticker_id' not in event['message']:
                                    process_ocr(sender_id, attachment['payload']['url'])
                                break

                    # ج. التعامل مع النصوص (AI Decision)
                    elif event.get('message') and event['message'].get('text'):
                        text = event['message']['text'].strip()
                        # إذا أرسل المستخدم إيموجي اللايك كنص، نرد عليه بالمثل
                        if text in ["👍", "👍🏻", "👍🏼", "👍🏽", "👍🏾", "👍🏿"]:
                             send_text_message(sender_id, "👍")
                        else:
                            send_api_request({'recipient': {'id': sender_id}, 'sender_action': 'typing_on'})
                            process_ai_logic(sender_id, text)

        return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
