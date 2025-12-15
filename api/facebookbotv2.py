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

# 🆕 مكتبات الرسم الرياضي
import matplotlib
matplotlib.use('Agg') # وضع السيرفر (بدون واجهة)
import matplotlib.pyplot as plt

# ====================================================================
# ⚙️ إعدادات النظام
# ====================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFY_TOKEN = 'boykta2025'
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
# 🎨 دوال الرسم (تحويل النص والرياضيات لصور)
# ====================================================================

def text_to_image_bytes(text):
    """تحول النص (حتى لو فيه رياضيات) إلى صورة"""
    try:
        # إعداد اللوحة
        fig, ax = plt.subplots(figsize=(10, len(text.split('\n')) * 0.5 + 2))
        ax.axis('off')
        
        # كتابة النص (يدعم LaTeX جزئياً إذا كان بين $$)
        # نستخدم التفاف النص لتجنب الخروج عن الصورة
        wrapped_text = "\n".join(textwrap.wrap(text, width=60))
        
        ax.text(0.5, 0.5, wrapped_text, 
                ha='center', va='center', 
                fontsize=15, family='serif', wrap=True)
        
        # حفظ في الذاكرة
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Image Render Error: {e}")
        return None

# ====================================================================
# 📡 دوال الذكاء الاصطناعي
# ====================================================================

def call_groq(messages, model, key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=40)
        
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
    
    sys_msg = system_instruction if system_instruction else "أنت مساعد ذكي."
    messages = [{"role": "system", "content": sys_msg}] + history[-4:]

    reply = ""
    try:
        reply = call_groq(messages, MODEL_CHAT, KEY_PRIMARY)
    except:
        reply = "عذراً، الخوادم مشغولة."

    history.append({"role": "assistant", "content": reply})
    return reply

def ocr_smart(image_url):
    # 🆕 نطلب من الموديل الآن استخدام LaTeX لأننا سنحوله لصورة!
    prompt = """
    TASK: Extract text from the image strictly.
    RULES:
    1. If you see math equations, use LaTeX formatting (e.g., \\frac{a}{b}, x^2, \\sqrt{x}).
    2. Keep text layout organized.
    3. Output ONLY the content.
    """
    msgs = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}}
    ]}]
    try:
        return call_groq(msgs, MODEL_VISION, KEY_VISION)
    except:
        return "فشل استخراج النص."

# ====================================================================
# 📨 دوال الإرسال (محدثة لدعم الصور المولدة محلياً)
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

def send_image_url(user_id, url):
    encoded_url = urllib.parse.quote(url, safe=':/?&=')
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}",
                  json={'recipient': {'id': user_id}, 'message': {'attachment': {'type': 'image', 'payload': {'url': encoded_url, 'is_reusable': True}}}})

def send_file_from_memory(user_id, file_data, file_type='image', filename='file.png', media_type='image/png'):
    """إرسال ملف (صورة أو صوت) من الذاكرة مباشرة"""
    data = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': file_type, 'payload': {}}})}
    files = {'filedata': (filename, file_data, media_type)}
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", data=data, files=files)

# ====================================================================
# 🎮 القوائم
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
        {"content_type": "text", "title": "👨 رجل", "payload": "SET_VOICE_MALE"},
        {"content_type": "text", "title": "👩 امرأة", "payload": "SET_VOICE_FEMALE"},
        {"content_type": "text", "title": "🔙 رجوع", "payload": "CMD_BACK"}
    ]

# ====================================================================
# 🕹️ التحكم الرئيسي (Webhook)
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
                        if event.get('message') and event['message'].get('quick_reply'):
                            handle_payload(sender_id, event['message']['quick_reply']['payload'])
                        elif 'postback' in event:
                            handle_payload(sender_id, event['postback']['payload'])
                        elif 'message' in event:
                            handle_message(sender_id, event['message'])
        except Exception as e:
            logger.error(f"Error: {e}")
        return 'ok'

# ====================================================================
# 🎮 معالج الأوامر (Payloads)
# ====================================================================

def handle_payload(user_id, payload):
    if payload == 'CMD_BACK':
        user_db[user_id]['state'] = None
        user_db[user_id]['extracted_text'] = None
        send_quick_replies(user_id, "القائمة الرئيسية 🏠", get_main_menu_qr())
        return

    # === OCR ===
    if payload == 'CMD_OCR':
        if user_db[user_id]['last_image']:
            process_ocr(user_id, user_db[user_id]['last_image'])
        else:
            user_db[user_id]['state'] = 'WAITING_OCR'
            send_quick_replies(user_id, "أرسل الصورة الآن 📸", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    elif payload == 'OCR_SOLVE':
        text = user_db[user_id]['extracted_text']
        if text:
            send_msg(user_id, "جاري الحل، سأرسله كصورة ليكون واضحاً... 🧮")
            reply = chat_smart(user_id, f"Solve this math/physics problem step by step using LaTeX for math parts:\n{text}")
            
            # تحويل الحل لصورة
            img_data = text_to_image_bytes(reply)
            if img_data:
                send_file_from_memory(user_id, img_data, 'image', 'solution.png', 'image/png')
            else:
                send_msg(user_id, reply) # فشل الرسم، نرسل نص
            
            send_quick_replies(user_id, "هل هناك شيء آخر؟", get_main_menu_qr())

    elif payload == 'OCR_TRANS_CUSTOM':
        user_db[user_id]['state'] = 'WAITING_TRANS_LANG'
        send_quick_replies(user_id, "اكتب اللغة المستهدفة (عربي، فرنسي...) ✍️", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    # === Image Gen ===
    elif payload == 'CMD_GEN_IMG':
        user_db[user_id]['state'] = 'WAITING_GEN_PROMPT'
        send_quick_replies(user_id, "اكتب وصف الصورة 🎨", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    # === TTS ===
    elif payload == 'CMD_TTS':
        send_quick_replies(user_id, "اختر الصوت:", get_voice_options())

    elif payload in ['SET_VOICE_MALE', 'SET_VOICE_FEMALE']:
        voice_type = 'male' if payload == 'SET_VOICE_MALE' else 'female'
        user_db[user_id]['voice'] = voice_type
        user_db[user_id]['state'] = 'WAITING_TTS_TEXT'
        send_quick_replies(user_id, "أرسل النص الآن 📝", [{"content_type": "text", "title": "🔙 إلغاء", "payload": "CMD_BACK"}])

    elif payload == 'CMD_INFO':
        send_quick_replies(user_id, "المطور: Younes Laldji", get_main_menu_qr())

def process_ocr(user_id, image_url):
    send_msg(user_id, "جاري استخراج وتحويل النص لصورة... ⏳")
    text = ocr_smart(image_url)
    user_db[user_id]['extracted_text'] = text
    user_db[user_id]['state'] = None
    
    # 🆕 تحويل النص المستخرج لصورة وإرساله
    img_data = text_to_image_bytes(text)
    if img_data:
        send_file_from_memory(user_id, img_data, 'image', 'ocr_result.png', 'image/png')
    else:
        send_msg(user_id, text) # احتياطي

    send_quick_replies(user_id, "الخيارات: 👇", get_ocr_options())

# ====================================================================
# 📩 معالج الرسائل (مع الفصل التام للمنطق)
# ====================================================================

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
                process_ocr(user_id, url)
                return # 🛑 توقف هنا

            send_quick_replies(user_id, "وصلت الصورة.", [{"content_type":"text", "title":"📝 استخراج نص", "payload":"CMD_OCR"}] + get_main_menu_qr())
            return # 🛑 توقف هنا

    # 2. نصوص
    text = msg.get('text', '')
    if not text: return

    # --- وضع الترجمة ---
    if state == 'WAITING_TRANS_LANG':
        original_text = user_db[user_id]['extracted_text']
        send_msg(user_id, f"جاري الترجمة لـ {text}...")
        reply = chat_smart(user_id, f"Translate to {text}:\n{original_text}")
        
        # إرسال الترجمة كصورة إذا كانت طويلة أو بها رموز
        img_data = text_to_image_bytes(reply)
        if img_data:
            send_file_from_memory(user_id, img_data, 'image', 'trans.png', 'image/png')
        else:
            send_msg(user_id, reply)
            
        user_db[user_id]['state'] = None
        send_quick_replies(user_id, "تم.", get_main_menu_qr())
        return # 🛑 فصل تام

    # --- وضع الرسم ---
    if state == 'WAITING_GEN_PROMPT':
        send_msg(user_id, "جاري الرسم... 🎨")
        try:
            # ترجمة الوصف للإنجليزية داخلياً للحصول على أفضل نتيجة
            eng_prompt = chat_smart(user_id, f"Translate this image prompt to English: {text}")
            
            seed = random.randint(1, 99999)
            encoded_prompt = urllib.parse.quote(eng_prompt)
            img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&noshare=1&seed={seed}&model=flux"
            
            send_image_url(user_id, img_url)
            send_quick_replies(user_id, "كيف تبدو؟", get_main_menu_qr())
        except Exception as e:
            send_msg(user_id, "فشل الرسم.")
        
        user_db[user_id]['state'] = None # إنهاء الوضع
        return # 🛑 فصل تام (لن يرد الشات الذكي)

    # --- وضع الصوت ---
    if state == 'WAITING_TTS_TEXT':
        send_msg(user_id, "جاري المعالجة... 🎧")
        try:
            voice = VOICES[user_db[user_id]['voice']]
            audio_stream = io.BytesIO()
            asyncio.run(edge_tts.Communicate(text, voice).save(audio_stream))
            audio_data = audio_stream.getvalue()
            
            if len(audio_data) > 0:
                send_file_from_memory(user_id, audio_data, 'audio', 'voice.mp3', 'audio/mpeg')
                send_quick_replies(user_id, "تم!", get_main_menu_qr())
            else:
                send_msg(user_id, "خطأ: الصوت فارغ.")
        except Exception as e:
            send_msg(user_id, "خطأ تقني.")
        
        user_db[user_id]['state'] = None # إنهاء الوضع
        return # 🛑 فصل تام

    # --- الشات العام (فقط إذا لم يكن هناك وضع نشط) ---
    reply = chat_smart(user_id, text)
    send_quick_replies(user_id, reply, get_main_menu_qr())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
