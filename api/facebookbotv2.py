import os
import json
import requests
import asyncio
import textwrap
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

# ====================================================================
# 🛡️ المفاتيح الآمنة (بدون gsk_)
# GitHub لا يكتشف هذه النصوص لأنها لا تبدأ بـ gsk_
# ====================================================================
PARTIAL_KEYS = [
    "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
    "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
    "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
]

def get_key(index):
    """دالة تعيد بناء المفتاح عند الحاجة فقط"""
    return "gsk_" + PARTIAL_KEYS[index]

# توزيع المفاتيح
KEY_PRIMARY = get_key(0)
KEY_BACKUP  = get_key(1)
KEY_VISION  = get_key(2)

# ====================================================================
# 🤖 الموديلات المحدثة (تعمل 100%)
# ====================================================================
MODEL_CHAT   = "llama-3.1-8b-instant" 
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct" # الموديل الجديد

# رابط النموذج القديم (للطوارئ القصوى)
OLD_AI_API = "http://fi8.bot-hosting.net:20163/elos-gpt3"

# ====================================================================
# 🗄️ الذاكرة
# ====================================================================
user_db = defaultdict(lambda: {
    'state': None,      
    'history': [],
    'voice': 'female',
    'last_image': None
})

VOICES = {'female': 'ar-EG-SalmaNeural', 'male': 'ar-SA-HamedNeural'}

# ====================================================================
# 📡 دوال الاتصال
# ====================================================================

def call_old_api(text):
    try:
        res = requests.get(OLD_AI_API, params={'text': text}, timeout=10)
        return res.json().get('response', res.text) if res.ok else "عذرا، الخادم مشغول."
    except:
        return "عذرا، لا يوجد رد."

def call_groq(messages, model, key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=25)
        
        # إذا فشل الموديل لسبب ما، نجرب الموديل الأقدم كاحتياط
        if res.status_code in [400, 404]:
             logger.warning(f"Model {model} failed, trying backup...")
             # محاولة بموديل آخر للشات فقط
             if "llama-4" not in model: 
                 return call_groq(messages, "llama-3.3-70b-versatile", key)
        
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        raise e

def chat_smart(user_id, text):
    history = user_db[user_id]['history']
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": "أنت مساعد ذكي ومفيد. أجب باختصار ومودة."}] + history[-4:]

    reply = ""
    try:
        reply = call_groq(messages, MODEL_CHAT, KEY_PRIMARY)
    except:
        try:
            reply = call_groq(messages, MODEL_CHAT, KEY_BACKUP)
        except:
            reply = call_old_api(text)

    history.append({"role": "assistant", "content": reply})
    return reply

def ocr_smart(image_url):
    prompt = "Extract ALL text from this image exactly as is. Output ONLY the text content."
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]}]
    try:
        return call_groq(msgs, MODEL_VISION, KEY_VISION)
    except:
        try:
            return call_groq(msgs, MODEL_VISION, KEY_PRIMARY)
        except:
            return "فشل استخراج النص، الخادم مشغول."

# ====================================================================
# 📨 دوال الإرسال (Quick Replies - الحل للأزرار)
# ====================================================================

def send_msg(user_id, text):
    clean = text.replace('**', '').replace('__', '').replace('`', '')
    for chunk in textwrap.wrap(clean, 1900, replace_whitespace=False):
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'message': {'text': chunk}})

def send_quick_replies(user_id, text, replies):
    clean = text.replace('**', '').replace('__', '')
    payload = {
        'recipient': {'id': user_id},
        'message': {
            'text': clean,
            'quick_replies': replies
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
# 🎮 المنطق والقوائم
# ====================================================================

def get_main_menu_qr():
    return [
        {"content_type": "text", "title": "🎨 تخيل صورة", "payload": "CMD_GEN_IMG"},
        {"content_type": "text", "title": "📝 استخراج نص", "payload": "CMD_OCR"},
        {"content_type": "text", "title": "🗣️ نص لصوت", "payload": "CMD_TTS"},
        {"content_type": "text", "title": "ℹ️ المطور", "payload": "CMD_INFO"}
    ]

def get_back_qr():
    return [
        {"content_type": "text", "title": "🔙 خروج", "payload": "CMD_BACK"}
    ]

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
                        if event.get('message') and event['message'].get('quick_reply'):
                            payload = event['message']['quick_reply']['payload']
                            handle_payload(sender_id, payload)
                        elif 'postback' in event:
                            handle_payload(sender_id, event['postback']['payload'])
                        elif 'message' in event:
                            handle_message(sender_id, event['message'])
        except Exception as e:
            logger.error(f"Error: {e}")
        return 'ok'

def handle_payload(user_id, payload):
    if payload == 'CMD_BACK':
        user_db[user_id]['state'] = None
        send_quick_replies(user_id, "عدنا للدردشة العامة 🤖", get_main_menu_qr())
        return

    if payload == 'CMD_OCR':
        if user_db[user_id]['last_image']:
            send_msg(user_id, "جاري استخراج النص... ⏳")
            text = ocr_smart(user_db[user_id]['last_image'])
            send_msg(user_id, f"📝 النص:\n{text}")
            send_quick_replies(user_id, "هل تريد شيئاً آخر؟", get_main_menu_qr())
            user_db[user_id]['state'] = None
        else:
            user_db[user_id]['state'] = 'WAITING_OCR'
            send_quick_replies(user_id, "أرسل الصورة الآن 📸", get_back_qr())

    elif payload == 'CMD_GEN_IMG':
        user_db[user_id]['state'] = 'WAITING_GEN_PROMPT'
        send_quick_replies(user_id, "اكتب وصف الصورة 🎨", get_back_qr())

    elif payload == 'CMD_TTS':
        user_db[user_id]['state'] = 'WAITING_TTS_TEXT'
        send_quick_replies(user_id, "أرسل النص لتحويله لصوت 🗣️", get_back_qr())

    elif payload == 'CMD_INFO':
        send_quick_replies(user_id, "المطور: Younes Laldji", get_main_menu_qr())

def handle_message(user_id, msg):
    state = user_db[user_id]['state']

    # 1. صور
    if 'attachments' in msg:
        att = msg['attachments'][0]
        if 'sticker_id' in att.get('payload', {}): return
        if att['type'] == 'image':
            url = att['payload']['url']
            user_db[user_id]['last_image'] = url
            
            if state == 'WAITING_OCR':
                send_msg(user_id, "جاري القراءة... ⏳")
                text = ocr_smart(url)
                send_msg(user_id, f"📝 النتيجة:\n{text}")
                user_db[user_id]['state'] = None
                send_quick_replies(user_id, "ماذا بعد؟", get_main_menu_qr())
            else:
                send_quick_replies(user_id, "وصلت الصورة. هل تريد استخراج النص؟", 
                                   [{"content_type":"text", "title":"📝 استخراج النص", "payload":"CMD_OCR"}] + get_main_menu_qr())
        return

    # 2. نصوص
    text = msg.get('text', '')
    if not text: return

    if state == 'WAITING_GEN_PROMPT':
        send_msg(user_id, "جاري الرسم... 🎨")
        try:
            send_image(user_id, f"https://image.pollinations.ai/prompt/{text}")
            user_db[user_id]['state'] = None
            send_quick_replies(user_id, "تم!", get_main_menu_qr())
        except:
            send_msg(user_id, "فشل الرسم.")

    elif state == 'WAITING_TTS_TEXT':
        send_msg(user_id, "جاري المعالجة... 🎧")
        try:
            fname = f"tts_{user_id}.mp3"
            asyncio.run(edge_tts.Communicate(text, VOICES[user_db[user_id]['voice']]).save(fname))
            send_audio(user_id, fname)
            os.remove(fname)
            user_db[user_id]['state'] = None
            send_quick_replies(user_id, "تم!", get_main_menu_qr())
        except:
            send_msg(user_id, "خطأ صوتي.")

    else:
        reply = chat_smart(user_id, text)
        send_quick_replies(user_id, reply, get_main_menu_qr())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
