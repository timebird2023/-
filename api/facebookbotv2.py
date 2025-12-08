import os
import json
import requests
from flask import Flask, request
import logging
from collections import defaultdict

# ====================================================================
# 📚 الإعدادات
# ====================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'boykta2025')
PAGE_ACCESS_TOKEN = "EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9"

# الروابط
AI_API_URL = "http://fi8.bot-hosting.net:20163/elos-gpt3"
OCR_API_URL = "https://api.ocr.space/parse/image"
OCR_API_KEY = "helloworld"

# ذاكرة
in_memory_conversations = defaultdict(list)

# ====================================================================
# 🛠️ دوال المساعدة
# ====================================================================

def send_api_request(payload):
    params = {'access_token': PAGE_ACCESS_TOKEN}
    try:
        requests.post('https://graph.facebook.com/v19.0/me/messages', params=params, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"❌ Error: {e}")

def send_text_message(recipient_id, text):
    payload = {'recipient': {'id': recipient_id}, 'message': {'text': text}}
    send_api_request(payload)

def send_image_url(recipient_id, image_url):
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

def is_like_or_sticker(message):
    """فحص ذكي للجام والستيكر"""
    if 'sticker_id' in message:
        return True
    if 'attachments' in message:
        for att in message['attachments']:
            if att.get('payload', {}).get('sticker_id'):
                return True
            # فحص إضافي للروابط المعروفة للستيكرز
            url = att.get('payload', {}).get('url', '')
            if 'sticker' in url or 'Sticker' in url:
                return True
    return False

# ====================================================================
# 🧠 المنطق (OCR المحسن + AI)
# ====================================================================

def process_ai_logic(user_id, user_text):
    system_instruction = (
        "Instructions: You are a smart assistant. "
        "If user asks to CREATE/DRAW image -> reply 'CMD_IMAGE: English description'. "
        "Else -> reply normally. "
        f"\nUser Request: {user_text}"
    )

    try:
        response = requests.get(AI_API_URL, params={'text': system_instruction}, timeout=45)
        if response.ok:
            ai_reply = response.text.strip()
            try:
                json_data = json.loads(ai_reply)
                if isinstance(json_data, dict):
                    ai_reply = json_data.get('response', json_data.get('reply', ai_reply))
            except:
                pass

            if "CMD_IMAGE:" in ai_reply:
                prompt = ai_reply.split("CMD_IMAGE:", 1)[1].strip().split('\n')[0]
                send_text_message(user_id, f"🎨 جاري الرسم: {prompt}")
                safe_prompt = requests.utils.quote(prompt)
                send_image_url(user_id, f"https://image.pollinations.ai/prompt/{safe_prompt}?nologo=true")
            else:
                in_memory_conversations[user_id].append(user_text)
                send_text_message(user_id, ai_reply)
        else:
            send_text_message(user_id, "⚠️ الخادم مشغول.")
    except:
        send_text_message(user_id, "خطأ في الاتصال.")

def process_ocr(user_id, image_url):
    """
    استخراج النص باستخدام المحرك 2 لدعم اللغات المختلطة
    """
    send_text_message(user_id, "🔍 جاري استخراج النص (عربي/فرنسي/إنجليزي)...")
    try:
        payload = {
            'apikey': OCR_API_KEY,
            'url': image_url,
            'language': 'ara',      # نبقي العربية كلغة أساسية
            'isOverlayRequired': False,
            'OCREngine': '2'        # 🌟 هام جداً: المحرك 2 أفضل بكثير للنصوص المختلطة واللاتينية
        }
        response = requests.post(OCR_API_URL, data=payload, timeout=25)
        
        if response.ok:
            result = response.json()
            if result.get('ParsedResults'):
                text = result['ParsedResults'][0].get('ParsedText', '').strip()
                if text:
                    # تقسيم النص إذا كان طويلاً جداً (قيود فيسبوك 2000 حرف)
                    if len(text) > 1900:
                        send_text_message(user_id, f"✅ النص المستخرج (جزء 1):\n\n{text[:1900]}")
                        send_text_message(user_id, f"تكملة:\n{text[1900:]}")
                    else:
                        send_text_message(user_id, f"✅ النص المستخرج:\n\n{text}")
                else:
                    send_text_message(user_id, "❓ الصورة واضحة ولكن لم أتمكن من قراءة النص (قد يكون الخط غير واضح).")
            else:
                send_text_message(user_id, "⚠️ فشل استخراج البيانات من الصورة.")
        else:
            send_text_message(user_id, "⚠️ خدمة الصور مشغولة حالياً.")
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        send_text_message(user_id, "خطأ غير متوقع.")

# ====================================================================
# 🌐 Webhook
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Error', 403

    elif request.method == 'POST':
        data = request.get_json()
        if data:
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    if 'delivery' in event or 'read' in event: continue
                    
                    message = event.get('message')
                    if not message: continue

                    # 1. فحص الستيكر/الجام
                    if is_like_or_sticker(message):
                        send_text_message(sender_id, "👍")
                        continue 

                    # 2. فحص الصور (OCR)
                    if message.get('attachments'):
                        for attachment in message['attachments']:
                            if attachment['type'] == 'image':
                                process_ocr(sender_id, attachment['payload']['url'])
                                break
                    
                    # 3. النصوص (AI)
                    elif message.get('text'):
                        text = message['text'].strip()
                        if text in ["👍", "👍🏻", "👍🏼"]:
                             send_text_message(sender_id, "👍")
                        else:
                            # إظهار مؤشر الكتابة
                            send_api_request({'recipient': {'id': sender_id}, 'sender_action': 'typing_on'})
                            process_ai_logic(sender_id, text)

        return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
