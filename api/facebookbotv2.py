import os
import json
import requests
import asyncio
import textwrap
import socket
import logging
from flask import Flask, request
from collections import defaultdict
import edge_tts

# ====================================================================
# ⚙️ إعدادات وتوكنات
# ====================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFY_TOKEN = 'boykta2025'
PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

# --- مفاتيح Groq (معكوسة للتمويه) ---
REV_KEY_1 = "49geXD6qqRr4xfUdUlVSeeVWYF3bydGWSmUinop7KTuMzUIHmIEi_ksg"
REV_KEY_2 = "N2C8UcKgubBUBsQyZRNhRK51YF3bydGWr2nN0yuRnblYAFceuxoKu_ksg"
REV_KEY_3 = "d1Ng9mjX25NEoVYqu3b4KX2hYF3bydGW5nTQ7Uu02ZFhNtjICVkH_ksg"

def get_key(rev): return rev[::-1]

KEY_PRIMARY = get_key(REV_KEY_1)
KEY_BACKUP = get_key(REV_KEY_3)
KEY_VISION = get_key(REV_KEY_2)

# --- رابط النموذج القديم (الاحتياطي الأخير) ---
OLD_AI_API = "http://fi8.bot-hosting.net:20163/elos-gpt3"

DEVELOPER_NAME = "Younes Laldji"
AI_NAME = "بويكتا"

# ====================================================================
# 🗄️ الذاكرة (تمت إضافة ذاكرة للصورة الأخيرة)
# ====================================================================
user_db = defaultdict(lambda: {
    'state': None,
    'history': [],
    'voice': 'female',
    'last_image': None  # 👈 هنا نحفظ رابط آخر صورة
})

VOICES = {'female': 'ar-EG-SalmaNeural', 'male': 'ar-SA-HamedNeural'}

# ====================================================================
# 📡 دوال الاتصال (Groq + Old API)
# ====================================================================

def call_old_api(text):
    """استدعاء النموذج القديم كخط دفاع أخير"""
    try:
        res = requests.get(OLD_AI_API, params={'text': text}, timeout=10)
        if res.ok:
            # محاولة استخراج الرد من JSON أو النص مباشرة
            try: return res.json().get('response', res.text)
            except: return res.text
    except Exception as e:
        logger.error(f"Old API Error: {e}")
    return "عذرا، حدث خطأ في جميع الخوادم."

def call_groq(messages, model, key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=20)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        raise e

def chat_smart(user_id, text):
    """نظام الرد الذكي: أساسي -> احتياطي -> قديم"""
    history = user_db[user_id]['history']
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": "أنت مساعد مفيد، جاوب بالعربية بدون تنسيقات معقدة."}] + history[-6:]

    reply = ""
    try:
        # 1. محاولة Groq الأساسي
        reply = call_groq(messages, "llama-3.3-70b-versatile", KEY_PRIMARY)
    except:
        try:
            # 2. محاولة Groq الاحتياطي
            reply = call_groq(messages, "llama3-8b-8192", KEY_BACKUP)
        except:
            # 3. استخدام النموذج القديم
            reply = call_old_api(text)

    history.append({"role": "assistant", "content": reply})
    return reply

def ocr_smart(image_url):
    """استخراج النص"""
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": "Extract text from image in Arabic/English cleanly."},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]}]
    try:
        return call_groq(msgs, "llama-3.2-11b-vision-preview", KEY_VISION)
    except:
        try:
            return call_groq(msgs, "llama-3.2-11b-vision-preview", KEY_BACKUP)
        except:
            return "فشل استخراج النص، الخوادم مشغولة."

# ====================================================================
# 📨 دوال الإرسال (فيسبوك)
# ====================================================================

def send_msg(user_id, text):
    # تنظيف النص من الماركداون الذي يكرهه فيسبوك لايت
    clean = text.replace('**', '').replace('__', '').replace('`', '')
    for chunk in textwrap.wrap(clean, 1900, replace_whitespace=False):
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'message': {'text': chunk}})

def send_buttons(user_id, text, buttons):
    # استخدام generic template أحياناً أفضل للايت
    payload = {
        'recipient': {'id': user_id},
        'message': {
            'attachment': {
                'type': 'template',
                'payload': {
                    'template_type': 'button',
                    'text': text.replace('**', ''),
                    'buttons': buttons
                }
            }
        }
    }
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", json=payload)

def send_image(user_id, url):
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}",
                  json={'recipient': {'id': user_id}, 'message': {'attachment': {'type': 'image', 'payload': {'url': url, 'is_reusable': True}}}})

def send_audio(user_id, path):
    data = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': 'audio', 'payload': {}}})}
    with open(path, 'rb') as f:
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", data=data, files={'filedata': (path, f, 'audio/mpeg')})

# ====================================================================
# 🎮 التحكم والمنطق
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return request.args.get('hub.challenge') if request.args.get('hub.verify_token') == VERIFY_TOKEN else 'Error'

    if request.method == 'POST':
        try:
            data = request.get_json()
            if data['object'] == 'page':
                for entry in data['entry']:
                    for event in entry.get('messaging', []):
                        sender_id = event['sender']['id']
                        if 'postback' in event:
                            handle_payload(sender_id, event['postback']['payload'])
                        elif 'message' in event:
                            handle_message(sender_id, event['message'])
        except Exception as e:
            logger.error(f"Webhook Error: {e}")
        return 'ok'

def get_main_menu():
    return [
        {"type": "postback", "title": "الدردشة 🤖", "payload": "CMD_CHAT"},
        {"type": "postback", "title": "تخيل صورة 🎨", "payload": "CMD_GEN_IMG"},
        {"type": "postback", "title": "استخراج نص 📝", "payload": "CMD_OCR"},
    ]

def handle_payload(user_id, payload):
    user_db[user_id]['state'] = None

    if payload == 'CMD_OCR':
        # 💡 الذكاء هنا: التحقق هل توجد صورة سابقة؟
        last_img = user_db[user_id]['last_image']
        if last_img:
            send_msg(user_id, "جاري استخراج النص من الصورة السابقة... ⏳")
            text = ocr_smart(last_img)
            send_msg(user_id, f"📝 النص:\n{text}")
            send_buttons(user_id, "ماذا تريد الآن؟", get_main_menu())
        else:
            user_db[user_id]['state'] = 'WAITING_OCR'
            send_msg(user_id, "أرسل الصورة الآن لاستخراج النص منها 📄")

    elif payload == 'CMD_GEN_IMG':
        user_db[user_id]['state'] = 'WAITING_GEN_PROMPT'
        send_msg(user_id, "اكتب وصف الصورة التي تريدها 🎨")

    elif payload == 'CMD_TTS':
        user_db[user_id]['state'] = 'WAITING_TTS_TEXT'
        send_msg(user_id, "أرسل النص لتحويله لصوت 🗣️")
    
    elif payload == 'CMD_CHAT':
        send_msg(user_id, "تفضل، أنا أسمعك. يمكنك سؤالي عن أي شيء.")

    elif payload == 'CMD_BACK':
        send_buttons(user_id, "القائمة الرئيسية:", get_main_menu())

def handle_message(user_id, msg):
    state = user_db[user_id]['state']

    # 1. معالجة الصور
    if 'attachments' in msg:
        att = msg['attachments'][0]
        if 'sticker_id' in att.get('payload', {}): # تجاهل اللايكات
            return
        
        if att['type'] == 'image':
            url = att['payload']['url']
            user_db[user_id]['last_image'] = url # ✅ حفظ الصورة في الذاكرة
            
            if state == 'WAITING_OCR':
                send_msg(user_id, "جاري القراءة... ⏳")
                text = ocr_smart(url)
                send_msg(user_id, f"📝 النتيجة:\n{text}")
                user_db[user_id]['state'] = None
            else:
                # عرض زر استخراج النص مباشرة للصورة المرسلة
                send_buttons(user_id, "وصلت الصورة. اختر:", [
                    {"type": "postback", "title": "استخراج النص 📝", "payload": "CMD_OCR"},
                    {"type": "postback", "title": "إلغاء ❌", "payload": "CMD_BACK"}
                ])
        return

    # 2. معالجة النصوص
    text = msg.get('text', '')
    if not text: return

    if state == 'WAITING_GEN_PROMPT':
        send_msg(user_id, "جاري الرسم... 🎨")
        try:
            # استخدام الترجمة البسيطة أو المباشرة
            img_url = f"https://image.pollinations.ai/prompt/{text}"
            send_image(user_id, img_url)
        except:
            send_msg(user_id, "فشل إنشاء الصورة.")
        user_db[user_id]['state'] = None

    elif state == 'WAITING_TTS_TEXT':
        send_msg(user_id, "جاري التسجيل... 🎧")
        fname = f"tts_{user_id}.mp3"
        try:
            voice = VOICES[user_db[user_id]['voice']]
            asyncio.run(edge_tts.Communicate(text, voice).save(fname))
            send_audio(user_id, fname)
            os.remove(fname)
        except:
            send_msg(user_id, "حدث خطأ صوتي.")
        user_db[user_id]['state'] = None

    else:
        # شات عادي
        reply = chat_smart(user_id, text)
        send_msg(user_id, reply)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
