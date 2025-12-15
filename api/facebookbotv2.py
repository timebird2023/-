import os
import json
import requests
import asyncio
import textwrap
import logging
import random
import urllib.parse
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
# ✅ التوكن
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
    'trans_target': None
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
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=40)
        
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
    
    sys_msg = system_instruction if system_instruction else "أنت مساعد ذكي. أجب بإختصار ومودة."
    messages = [{"role": "system", "content": sys_msg}] + history[-4:]

    reply = ""
    try:
        reply = call_groq(messages, MODEL_CHAT, KEY_PRIMARY)
    except:
        reply = "عذراً، الخوادم مشغولة حالياً."

    history.append({"role": "assistant", "content": reply})
    return reply

def translate_prompt_for_image(text):
    """دالة خاصة لترجمة وتحسين وصف الصورة للإنجليزية"""
    sys_msg = "You are an expert prompt engineer. Translate the user's description into a highly detailed English prompt for an AI image generator. Output ONLY the English prompt."
    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": text}
    ]
    try:
        return call_groq(messages, MODEL_CHAT, KEY_BACKUP)
    except:
        return text # في حال الفشل نستخدم النص الأصلي

def ocr_smart(image_url):
    # 🆕 Prompt معدل لمنع الرموز المعقدة
    prompt = """
    TASK: Transcribe the text in the image exactly as a student would write it in a notebook.
    
    STRICT RULES FOR MATH:
    1. Do NOT use LaTeX code (NO $$, NO \mathbb, NO \frac).
    2. Write symbols simply:
       - Instead of \mathbb{R}, write: R
       - Instead of \lim_{x \to \infty}, write: lim x->inf
       - Instead of \frac{a}{b}, write: a/b
       - Instead of x^2, write: x^2
    3. Keep Arabic text exactly as is.
    4. Maintain the layout (lines) of the document.
    5. Output ONLY the plain text content.
    """
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]}]
    try:
        return call_groq(msgs, MODEL_VISION, KEY_VISION)
    except:
        return "فشل استخراج النص، الصورة غير واضحة."

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

def send_audio_file(user_id, file_path):
    # إرسال ملف صوتي محفوظ على القرص
    data = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': 'audio', 'payload': {}}})}
    with open(file_path, 'rb') as f:
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", data=data, files={'filedata': (file_path, f, 'audio/mpeg')})

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
        user_db[user_id]['extracted_text'] = None
        send_quick_replies(user_id, "عدنا للدردشة العامة 🤖", get_main_menu_qr())
        return

    # === خدمة OCR ===
    if payload == 'CMD_OCR':
        if user_db[user_id]['last_image']:
            process_ocr(user_id, user_db[user_id]['last_image'])
        else:
            user_db[user_id]['state'] = 'WAITING_OCR'
            send_quick_replies(user_id, "أرسل الصورة الآن 📸", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    elif payload == 'OCR_SOLVE':
        text = user_db[user_id]['extracted_text']
        if text:
            send_msg(user_id, "جاري التفكير... 🧠")
            reply = chat_smart(user_id, f"اشرح أو حل هذا النص ببساطة ووضوح:\n{text}")
            send_quick_replies(user_id, reply, get_main_menu_qr())

    elif payload == 'OCR_TRANS_CUSTOM':
        user_db[user_id]['state'] = 'WAITING_TRANS_LANG'
        send_quick_replies(user_id, "اكتب اسم اللغة التي تريد الترجمة إليها (مثلاً: فرنسية، إنجليزية...) ✍️", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    # === خدمة الصور ===
    elif payload == 'CMD_GEN_IMG':
        user_db[user_id]['state'] = 'WAITING_GEN_PROMPT'
        send_quick_replies(user_id, "اكتب وصف الصورة (بالعربي أو أي لغة) 🎨", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

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
    send_msg(user_id, "جاري استخراج النص بدون رموز معقدة... ⏳")
    text = ocr_smart(image_url)
    
    user_db[user_id]['extracted_text'] = text
    user_db[user_id]['state'] = None
    
    send_msg(user_id, f"📝 النص المستخرج:\n\n{text}")
    send_quick_replies(user_id, "ماذا تريد أن أفعل بهذا النص؟ 👇", get_ocr_options())

def handle_message(user_id, msg):
    state = user_db[user_id]['state']

    if 'attachments' in msg:
        att = msg['attachments'][0]
        if 'sticker_id' in att.get('payload', {}): return
        if att['type'] == 'image':
            url = att['payload']['url']
            user_db[user_id]['last_image'] = url
            
            if state == 'WAITING_OCR':
                process_ocr(user_id, url)
            else:
                send_quick_replies(user_id, "وصلت الصورة. هل أستخرج النص؟", 
                                   [{"content_type":"text", "title":"📝 استخراج النص", "payload":"CMD_OCR"}] + get_main_menu_qr())
        return

    text = msg.get('text', '')
    if not text: return

    # --- الترجمة ---
    if state == 'WAITING_TRANS_LANG':
        target_lang = text
        original_text = user_db[user_id]['extracted_text']
        send_msg(user_id, f"جاري الترجمة إلى {target_lang}... 🌍")
        reply = chat_smart(user_id, f"Translate strictly to {target_lang}:\n\n{original_text}")
        user_db[user_id]['state'] = None
        send_quick_replies(user_id, reply, get_main_menu_qr())

    # --- إنشاء صورة (مع التحسين والترجمة الداخلية) ---
    elif state == 'WAITING_GEN_PROMPT':
        send_msg(user_id, "جاري تحسين الوصف ورسم الصورة... 🎨")
        try:
            # 1. ترجمة وتحسين الوصف
            enhanced_prompt = translate_prompt_for_image(text)
            logger.info(f"Image Prompt: {enhanced_prompt}")
            
            # 2. توليد الرابط
            seed = random.randint(1, 99999)
            encoded_prompt = urllib.parse.quote(enhanced_prompt)
            img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&noshare=1&seed={seed}&model=flux"
            
            send_image(user_id, img_url)
            user_db[user_id]['state'] = None
            send_quick_replies(user_id, "كيف تبدو؟ 😍", get_main_menu_qr())
        except Exception as e:
            send_msg(user_id, f"❌ خطأ: {str(e)}")
            user_db[user_id]['state'] = None

    # --- تحويل صوت (استخدام مجلد /tmp/) ---
    elif state == 'WAITING_TTS_TEXT':
        send_msg(user_id, "جاري المعالجة... 🎧")
        try:
            selected_voice = VOICES[user_db[user_id]['voice']]
            # ✅ استخدام مجلد /tmp/ لتجنب مشاكل الصلاحيات
            fname = f"/tmp/tts_{user_id}_{random.randint(1000,9999)}.mp3"
            
            asyncio.run(edge_tts.Communicate(text, selected_voice).save(fname))
            
            if os.path.exists(fname):
                send_audio_file(user_id, fname)
                os.remove(fname) # حذف الملف بعد الإرسال
                user_db[user_id]['state'] = None
                send_quick_replies(user_id, "تم الإرسال!", get_main_menu_qr())
            else:
                send_msg(user_id, "خطأ: لم يتم إنشاء الملف.")
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
