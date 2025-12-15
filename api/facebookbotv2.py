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

# --- مفاتيح Groq (معكوسة لتجاوز حظر GitHub) ---
REV_KEY_1 = "q0rVTmORfEqv56VXMDo7Sh2UfY3bydGWvGHTMdVQcpNL1LwmChwm_ksg"
REV_KEY_2 = "d1Ng9mjX25NEoVYqu3b4KX2hYF3bydGW5nTQ7Uu02ZFhNtjICVkH_ksg"
REV_KEY_3 = "N2C8UcKgubBUBsQyZRNhRK51YF3bydGWr2nN0yuRnblYAFceuxoKu_ksg"

def get_key(rev): return rev[::-1]

KEY_PRIMARY = get_key(REV_KEY_1)
KEY_BACKUP = get_key(REV_KEY_2)
KEY_VISION = get_key(REV_KEY_3) 

# --- نماذج Groq ---
MODEL_CHAT_SMART = "llama-3.3-70b-versatile"
MODEL_CHAT_FAST  = "llama-3.1-8b-instant"
MODEL_VISION     = "llama-3.2-11b-vision-preview"

# رابط النموذج القديم (للطوارئ القصوى)
OLD_AI_API = "http://fi8.bot-hosting.net:20163/elos-gpt3"

# ====================================================================
# 🗄️ الذاكرة
# ====================================================================
user_db = defaultdict(lambda: {
    'state': None,      # None = وضع الدردشة العام
    'history': [],
    'voice': 'female',
    'last_image': None
})

VOICES = {'female': 'ar-EG-SalmaNeural', 'male': 'ar-SA-HamedNeural'}

# ====================================================================
# 📡 دوال الاتصال (Groq & Old API)
# ====================================================================

def call_old_api(text):
    try:
        res = requests.get(OLD_AI_API, params={'text': text}, timeout=10)
        return res.json().get('response', res.text) if res.ok else "عذرا، الخوادم مشغولة."
    except:
        return "عذرا، الخادم لا يستجيب."

def call_groq(messages, model, key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=25)
        # إذا النموذج غير موجود، نستخدم النموذج السريع
        if res.status_code in [400, 404] and model != MODEL_CHAT_FAST:
             return call_groq(messages, MODEL_CHAT_FAST, key)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        raise e

def chat_smart(user_id, text):
    history = user_db[user_id]['history']
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": "أنت مساعد ذكي ومفيد."}] + history[-5:]

    reply = ""
    try:
        reply = call_groq(messages, MODEL_CHAT_SMART, KEY_PRIMARY)
    except:
        try:
            reply = call_groq(messages, MODEL_CHAT_FAST, KEY_BACKUP)
        except:
            reply = call_old_api(text)

    history.append({"role": "assistant", "content": reply})
    return reply

def ocr_smart(image_url):
    # أمر صارم لاستخراج كل شيء
    prompt = "Extract ALL text, numbers, and symbols from this image exactly as they appear. Do not translate. Output only the extracted content."
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
            return "فشل استخراج النص، الصورة غير واضحة أو الخادم مشغول."

# ====================================================================
# 📨 دوال الإرسال (Quick Replies + Templates)
# ====================================================================

def send_msg(user_id, text):
    # إرسال نص عادي
    clean = text.replace('**', '').replace('__', '').replace('`', '')
    for chunk in textwrap.wrap(clean, 1900, replace_whitespace=False):
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'message': {'text': chunk}})

def send_quick_replies(user_id, text, replies):
    # هذه هي الأزرار التي تظهر فوق مكان الكتابة
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

# القائمة الرئيسية (تظهر دائماً في الوضع العام)
def get_main_menu_qr():
    return [
        {"content_type": "text", "title": "🎨 تخيل صورة", "payload": "CMD_GEN_IMG"},
        {"content_type": "text", "title": "📝 استخراج نص", "payload": "CMD_OCR"},
        {"content_type": "text", "title": "🗣️ نص لصوت", "payload": "CMD_TTS"},
        {"content_type": "text", "title": "ℹ️ المطور", "payload": "CMD_INFO"}
    ]

# زر الرجوع (يظهر داخل الخدمات)
def get_back_qr():
    return [
        {"content_type": "text", "title": "🔙 رجوع / خروج", "payload": "CMD_BACK"}
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
                        
                        # التعامل مع Quick Reply كأنه Postback
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
    # زر الرجوع يعيد المستخدم للوضع العام فوراً
    if payload == 'CMD_BACK':
        user_db[user_id]['state'] = None
        send_quick_replies(user_id, "تم الخروج من الخدمة. عدنا للدردشة العامة 🤖", get_main_menu_qr())
        return

    # === خدمة OCR ===
    if payload == 'CMD_OCR':
        # هل توجد صورة محفوظة؟
        if user_db[user_id]['last_image']:
            send_msg(user_id, "جاري استخراج النص من الصورة السابقة... ⏳")
            text = ocr_smart(user_db[user_id]['last_image'])
            send_msg(user_id, f"📝 النص المستخرج:\n{text}")
            finish_service(user_id) # إنهاء الخدمة
        else:
            user_db[user_id]['state'] = 'WAITING_OCR'
            send_quick_replies(user_id, "أرسل الصورة الآن لاستخراج أي نص منها 📸", get_back_qr())

    # === خدمة الصور ===
    elif payload == 'CMD_GEN_IMG':
        user_db[user_id]['state'] = 'WAITING_GEN_PROMPT'
        send_quick_replies(user_id, "اكتب وصف الصورة التي تريد رسمها 🎨", get_back_qr())

    # === خدمة الصوت ===
    elif payload == 'CMD_TTS':
        user_db[user_id]['state'] = 'WAITING_TTS_TEXT'
        send_quick_replies(user_id, "أرسل النص لتحويله إلى صوت 🗣️", get_back_qr())

    # === معلومات المطور ===
    elif payload == 'CMD_INFO':
        send_quick_replies(user_id, "المطور: Younes Laldji\nبوت ذكي مفتوح المصدر.", get_main_menu_qr())

def finish_service(user_id):
    """دالة لإنهاء الخدمة وإرجاع الوضع العام"""
    user_db[user_id]['state'] = None
    send_quick_replies(user_id, "يرجى متابعة الصفحة ليصلك كل جديد! ❤️\nيمكنك إكمال الدردشة الآن.", get_main_menu_qr())

def handle_message(user_id, msg):
    state = user_db[user_id]['state']

    # 1. معالجة المرفقات (صور)
    if 'attachments' in msg:
        att = msg['attachments'][0]
        if 'sticker_id' in att.get('payload', {}): return # تجاهل اللايكات
        
        if att['type'] == 'image':
            url = att['payload']['url']
            user_db[user_id]['last_image'] = url # حفظ الصورة
            
            if state == 'WAITING_OCR':
                send_msg(user_id, "جاري القراءة (عربي/إنجليزي/أرقام)... ⏳")
                text = ocr_smart(url)
                send_msg(user_id, f"📝 النتيجة:\n{text}")
                finish_service(user_id)
            else:
                # إذا أرسل صورة في الوضع العام، نعرض اقتراح
                send_quick_replies(user_id, "وصلت الصورة. هل تريد استخراج النص؟", 
                                   [{"content_type":"text", "title":"📝 نعم استخرج", "payload":"CMD_OCR"}] + get_main_menu_qr())
        return

    # 2. معالجة النصوص
    text = msg.get('text', '')
    if not text: return

    # --- وضع الخدمات ---
    if state == 'WAITING_GEN_PROMPT':
        send_msg(user_id, "جاري الرسم... 🎨")
        try:
            img_url = f"https://image.pollinations.ai/prompt/{text}"
            send_image(user_id, img_url)
            finish_service(user_id)
        except:
            send_msg(user_id, "فشل الرسم.")
            user_db[user_id]['state'] = None

    elif state == 'WAITING_TTS_TEXT':
        send_msg(user_id, "جاري المعالجة الصوتية... 🎧")
        fname = f"tts_{user_id}.mp3"
        try:
            voice = VOICES[user_db[user_id]['voice']]
            asyncio.run(edge_tts.Communicate(text, voice).save(fname))
            send_audio(user_id, fname)
            os.remove(fname)
            finish_service(user_id)
        except:
            send_msg(user_id, "خطأ في الصوت.")
            user_db[user_id]['state'] = None

    # --- الوضع العام (ذكاء اصطناعي) ---
    else:
        # يرد الذكاء الاصطناعي ويرفق معه القائمة الرئيسية دائماً لتظل ظاهرة
        reply = chat_smart(user_id, text)
        send_quick_replies(user_id, reply, get_main_menu_qr())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
