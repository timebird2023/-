import os
import json
import requests
import asyncio
import textwrap
import logging
import random
import urllib.parse
import io
from flask import Flask, request
from collections import defaultdict
import edge_tts

# ====================================================================
# ⚙️ إعدادات النظام
# ====================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFY_TOKEN = 'boykta2025'

# ✅ التوكن الجديد
PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

# 🛡️ المفاتيح الآمنة
PARTIAL_KEYS = [
    "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
    "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
    "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
]
def get_key(index): return "gsk_" + PARTIAL_KEYS[index]

KEY_PRIMARY = get_key(0)
KEY_BACKUP  = get_key(1)
KEY_VISION  = get_key(2)

MODEL_CHAT   = "llama-3.1-8b-instant" 
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"

# ====================================================================
# 🗄️ الذاكرة
# ====================================================================
user_db = defaultdict(lambda: {
    'state': None,      
    'history': [],
    'voice': 'female',
    'last_image': None,
    'extracted_text': None,
    'trans_target': None # لتخزين اللغة التي يريدها المستخدم
})

VOICES = {
    'female': 'ar-EG-SalmaNeural', 
    'male': 'ar-SA-HamedNeural'
}

# ====================================================================
# 📡 دوال الذكاء الاصطناعي
# ====================================================================

def call_groq(messages, model, key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=30)
        
        # محاولة احتياطية لموديل الصور
        if res.status_code in [400, 404] and "scout" in model:
             return call_groq(messages, "llama-3.2-11b-vision-preview", key)

        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        raise e

def chat_smart(user_id, text, system_instruction=None):
    history = user_db[user_id]['history']
    history.append({"role": "user", "content": text})
    
    sys_msg = system_instruction if system_instruction else "أنت مساعد ذكي ومفيد. أجب باختصار."
    messages = [{"role": "system", "content": sys_msg}] + history[-4:]

    reply = ""
    try:
        reply = call_groq(messages, MODEL_CHAT, KEY_PRIMARY)
    except:
        reply = "عذراً، الخوادم مشغولة حالياً."

    history.append({"role": "assistant", "content": reply})
    return reply

def ocr_smart(image_url):
    # 🆕 Prompt شامل لكل شيء
    prompt = """
    TASK: Extract EVERYTHING visible in this image exactly as it appears.
    
    CRITICAL RULES:
    1. Extract ALL languages found (Arabic, English, French, Mixed...).
    2. Extract ALL mathematical symbols, fractions, and equations exactly as shown.
    3. Do NOT skip anything. If it's on the screen, write it down.
    4. Output ONLY the extracted content. No conversational filler like "Here is the text".
    5. Maintain the original layout (lines/paragraphs) as much as possible.
    """
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]}]
    try:
        return call_groq(msgs, MODEL_VISION, KEY_VISION)
    except:
        return "فشل استخراج النص، الصورة غير واضحة أو الخادم مشغول."

# ====================================================================
# 📨 دوال الإرسال
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
    encoded_url = urllib.parse.quote(url, safe=':/?&=')
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}",
                  json={'recipient': {'id': user_id}, 'message': {'attachment': {'type': 'image', 'payload': {'url': encoded_url, 'is_reusable': True}}}})

def send_audio_from_memory(user_id, audio_data):
    data = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': 'audio', 'payload': {}}})}
    files = {'filedata': ('voice.mp3', audio_data, 'audio/mpeg')}
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", data=data, files=files)

# ====================================================================
# 🎮 القوائم والتحكم
# ====================================================================

def get_main_menu_qr():
    return [
        {"content_type": "text", "title": "🎨 تخيل صورة", "payload": "CMD_GEN_IMG"},
        {"content_type": "text", "title": "📝 استخراج نص", "payload": "CMD_OCR"},
        {"content_type": "text", "title": "🗣️ نص لصوت", "payload": "CMD_TTS"},
        {"content_type": "text", "title": "ℹ️ المطور", "payload": "CMD_INFO"}
    ]

def get_ocr_options():
    return [
        {"content_type": "text", "title": "🧮 حل / شرح", "payload": "OCR_SOLVE"},
        {"content_type": "text", "title": "🌍 ترجمة", "payload": "OCR_TRANS_CUSTOM"},
        {"content_type": "text", "title": "🔙 خروج", "payload": "CMD_BACK"}
    ]

def get_voice_options():
    return [
        {"content_type": "text", "title": "👨 صوت رجل", "payload": "SET_VOICE_MALE"},
        {"content_type": "text", "title": "👩 صوت امرأة", "payload": "SET_VOICE_FEMALE"},
        {"content_type": "text", "title": "🔙 رجوع", "payload": "CMD_BACK"}
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

    # === خدمة OCR ===
    if payload == 'CMD_OCR':
        if user_db[user_id]['last_image']:
            process_ocr(user_id, user_db[user_id]['last_image'])
        else:
            user_db[user_id]['state'] = 'WAITING_OCR'
            send_quick_replies(user_id, "أرسل الصورة الآن (بها أي لغة أو رموز) 📸", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    elif payload == 'OCR_SOLVE':
        text = user_db[user_id]['extracted_text']
        if text:
            send_msg(user_id, "جاري التفكير... 🧠")
            reply = chat_smart(user_id, f"قم بحل أو شرح هذا النص بدقة:\n{text}")
            send_quick_replies(user_id, reply, get_main_menu_qr())

    elif payload == 'OCR_TRANS_CUSTOM':
        # 🆕 هنا نسأل المستخدم عن اللغة
        user_db[user_id]['state'] = 'WAITING_TRANS_LANG'
        send_quick_replies(user_id, "اكتب اسم اللغة التي تريد الترجمة إليها (مثلاً: فرنسية، تركية، كورية...) ✍️", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    # === خدمة الصور ===
    elif payload == 'CMD_GEN_IMG':
        user_db[user_id]['state'] = 'WAITING_GEN_PROMPT'
        send_quick_replies(user_id, "اكتب وصف الصورة 🎨", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    # === خدمة الصوت ===
    elif payload == 'CMD_TTS':
        send_quick_replies(user_id, "اختر الصوت: 🗣️", get_voice_options())

    elif payload in ['SET_VOICE_MALE', 'SET_VOICE_FEMALE']:
        voice_type = 'male' if payload == 'SET_VOICE_MALE' else 'female'
        user_db[user_id]['voice'] = voice_type
        user_db[user_id]['state'] = 'WAITING_TTS_TEXT'
        voice_name = "حامد" if voice_type == 'male' else "سلمى"
        send_quick_replies(user_id, f"تم اختيار ({voice_name}). أرسل النص الآن 📝", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    elif payload == 'CMD_INFO':
        send_quick_replies(user_id, "المطور: Younes Laldji", get_main_menu_qr())

def process_ocr(user_id, image_url):
    send_msg(user_id, "جاري تحليل كل حرف ورمز في الصورة... ⏳")
    text = ocr_smart(image_url)
    
    user_db[user_id]['extracted_text'] = text
    user_db[user_id]['state'] = None
    
    send_msg(user_id, f"📝 النص المستخرج:\n\n{text}")
    send_quick_replies(user_id, "ماذا تريد أن أفعل بهذا النص؟ 👇", get_ocr_options())

def handle_message(user_id, msg):
    state = user_db[user_id]['state']

    # 1. معالجة الصور
    if 'attachments' in msg:
        att = msg['attachments'][0]
        if 'sticker_id' in att.get('payload', {}): return
        if att['type'] == 'image':
            url = att['payload']['url']
            user_db[user_id]['last_image'] = url
            
            if state == 'WAITING_OCR':
                process_ocr(user_id, url)
            else:
                send_quick_replies(user_id, "وصلت الصورة. هل أستخرج النص منها؟", 
                                   [{"content_type":"text", "title":"📝 استخراج شامل", "payload":"CMD_OCR"}] + get_main_menu_qr())
        return

    # 2. معالجة النصوص
    text = msg.get('text', '')
    if not text: return

    # --- الترجمة المخصصة (الجديدة) ---
    if state == 'WAITING_TRANS_LANG':
        target_lang = text # المستخدم كتب اللغة بنفسه
        original_text = user_db[user_id]['extracted_text']
        
        send_msg(user_id, f"جاري الترجمة إلى {target_lang}... 🌍")
        
        prompt = f"Translate the following text to {target_lang}. Provide ONLY the translation:\n\n{original_text}"
        reply = chat_smart(user_id, prompt)
        
        user_db[user_id]['state'] = None
        send_quick_replies(user_id, reply, get_main_menu_qr())

    # --- إنشاء صورة (مع طباعة الخطأ) ---
    elif state == 'WAITING_GEN_PROMPT':
        send_msg(user_id, "جاري الرسم... 🎨")
        try:
            seed = random.randint(1, 99999)
            encoded_prompt = urllib.parse.quote(text)
            img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&noshare=1&seed={seed}"
            
            send_image(user_id, img_url)
            user_db[user_id]['state'] = None
            send_quick_replies(user_id, "كيف تبدو؟ 😍", get_main_menu_qr())
        except Exception as e:
            # 🆕 طباعة الخطأ للمستخدم/المطور
            send_msg(user_id, f"❌ فشل إنشاء الصورة.\nالسبب التقني: {str(e)}")
            user_db[user_id]['state'] = None
            send_quick_replies(user_id, "حاول مرة أخرى.", get_main_menu_qr())

    # --- تحويل صوت ---
    elif state == 'WAITING_TTS_TEXT':
        send_msg(user_id, "جاري المعالجة... 🎧")
        try:
            selected_voice = VOICES[user_db[user_id]['voice']]
            audio_stream = io.BytesIO()
            asyncio.run(edge_tts.Communicate(text, selected_voice).save(audio_stream))
            audio_data = audio_stream.getvalue()
            
            if len(audio_data) > 0:
                send_audio_from_memory(user_id, audio_data)
                user_db[user_id]['state'] = None
                send_quick_replies(user_id, "استماع ممتع!", get_main_menu_qr())
            else:
                send_msg(user_id, "خطأ: الملف فارغ.")
        except Exception as e:
            send_msg(user_id, f"خطأ صوتي: {str(e)}")
            user_db[user_id]['state'] = None

    # --- شات عام ---
    else:
        reply = chat_smart(user_id, text)
        send_quick_replies(user_id, reply, get_main_menu_qr())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
