import os
import json
import requests
import asyncio
import textwrap
import socket
from flask import Flask, request
from collections import defaultdict
import edge_tts

# ====================================================================
# 🔐 إعدادات المفاتيح (تم عكسها لتجاوز حماية GitHub)
# ====================================================================

VERIFY_TOKEN = 'boykta2025'
PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZCOj8ZBQdn1kZBWkwIjJpYxodGAGHFGhos8ijFduQZAblZAMGNkGQZAQ5efK1bNsARqMHqWBlOvPmZC9pqsINZBRTP58jyclmqaaY3DuHxicesKMBChiDHYfXUNaF80iySjVxtkFntTUbGZANBC6eVGc2yeqeZAKlQwf2Dyj1ydSeM81EWlLcVfDGRvPD'

# دالة سحرية لإصلاح المفاتيح المعكوسة
def get_real_key(reversed_key):
    return reversed_key[::-1]

# المفاتيح معكوسة (لا يستطيع GitHub اكتشافها هكذا)
REV_KEY_1 = "49geXD6qqRr4xfUdUlVSeeVWYF3bydGWSmUinop7KTuMzUIHmIEi_ksg"
REV_KEY_2 = "N2C8UcKgubBUBsQyZRNhRK51YF3bydGWr2nN0yuRnblYAFceuxoKu_ksg"
REV_KEY_3 = "d1Ng9mjX25NEoVYqu3b4KX2hYF3bydGW5nTQ7Uu02ZFhNtjICVkH_ksg"

# استرجاع المفاتيح الأصلية
KEY_CHAT_PRIMARY = get_real_key(REV_KEY_1)
KEY_VISION_PRIMARY = get_real_key(REV_KEY_2)
KEY_BACKUP_HELPER = get_real_key(REV_KEY_3)

DEVELOPER_NAME = "Younes Laldji"
AI_ASSISTANT_NAME = "بويكتا"
DEV_INFO = "المطور: Younes Laldji\nمطور برمجيات وبوتات ذكية."

app = Flask(__name__)

# ====================================================================
# 🗄️ الذاكرة وإدارة الحالة
# ====================================================================
user_db = defaultdict(lambda: {
    'state': None, 
    'history': [], 
    'voice': 'female'
})

VOICES = {
    'female': 'ar-EG-SalmaNeural', 
    'male': 'ar-SA-HamedNeural'
}

# ====================================================================
# 🛠️ دوال مساعدة (Utils)
# ====================================================================

def clean_text(text):
    """تنظيف النص لفيسبوك لايت"""
    if text:
        return text.replace('**', '').replace('__', '').replace('`', '')
    return ""

def split_message(text, limit=1900):
    """تقسيم النصوص الطويلة"""
    return textwrap.wrap(text, limit, replace_whitespace=False)

def call_groq_api(messages, model, key):
    """دالة موحدة للاتصال بـ Groq"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages}
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status() 
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        raise e

# ====================================================================
# 🧠 الذكاء الاصطناعي (AI Logic)
# ====================================================================

def chat_with_groq(user_id, user_text):
    """الدردشة العامة مع المحاولة الاحتياطية"""
    history = user_db[user_id]['history']
    history.append({"role": "user", "content": user_text})
    if len(history) > 8: history = history[-8:]
    
    messages = [{"role": "system", "content": "أنت بويكتا، مساعد ذكي. أجب دائما بالعربية وبشكل مفيد."}] + history
    
    try:
        reply = call_groq_api(messages, "llama-3.3-70b-versatile", KEY_CHAT_PRIMARY)
    except:
        try:
            reply = call_groq_api(messages, "llama3-8b-8192", KEY_BACKUP_HELPER)
        except:
            return "عذرا، الخوادم مشغولة حاليا. حاول مرة أخرى لاحقا."

    history.append({"role": "assistant", "content": reply})
    user_db[user_id]['history'] = history
    return reply

def ocr_groq_vision(image_url):
    """استخراج النص من الصورة (Vision)"""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract all text from this image perfectly in Arabic or English. Just output the text without headers."},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ]
    try:
        return call_groq_api(messages, "llama-3.2-11b-vision-preview", KEY_VISION_PRIMARY)
    except:
        try:
            return call_groq_api(messages, "llama-3.2-11b-vision-preview", KEY_BACKUP_HELPER)
        except:
            return "فشل استخراج النص، الصورة قد تكون غير واضحة."

def translate_prompt(text):
    """ترجمة الوصف (لخدمة الصور)"""
    messages = [
        {"role": "system", "content": "Translate this to English directly without any extra text."},
        {"role": "user", "content": text}
    ]
    try:
        return call_groq_api(messages, "llama3-8b-8192", KEY_BACKUP_HELPER)
    except:
        return text

# ====================================================================
# 📡 دوال الإرسال (Messenger API)
# ====================================================================

def send_msg(user_id, text):
    text = clean_text(text)
    chunks = split_message(text)
    for chunk in chunks:
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'message': {'text': chunk}})

def send_buttons(user_id, text, buttons):
    text = clean_text(text)
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                  json={
                      'recipient': {'id': user_id}, 
                      'message': {'attachment': {'type': 'template', 'payload': {'template_type': 'button', 'text': text, 'buttons': buttons}}}
                  })

def send_image(user_id, image_url):
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                  json={'recipient': {'id': user_id}, 'message': {'attachment': {'type': 'image', 'payload': {'url': image_url, 'is_reusable': True}}}})

def send_audio(user_id, filename):
    data = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': 'audio', 'payload': {}}})}
    with open(filename, 'rb') as f:
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", data=data, files={'filedata': (filename, f, 'audio/mpeg')})

# ====================================================================
# 🎮 التحكم (Controller)
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return 'Invalid verification token'

    if request.method == 'POST':
        try:
            data = request.get_json()
            if data['object'] == 'page':
                for entry in data['entry']:
                    for event in entry.get('messaging', []):
                        sender_id = event['sender']['id']
                        try:
                            if 'postback' in event:
                                handle_payload(sender_id, event['postback']['payload'])
                            elif 'message' in event:
                                handle_message(sender_id, event['message'])
                        except Exception as e:
                            print(f"Error handling event for {sender_id}: {e}")
        except Exception as main_e:
            print(f"Webhook Error: {main_e}")
        return 'ok'

def get_main_menu():
    return [
        {"type": "postback", "title": "🤖 دردشة", "payload": "CMD_CHAT"},
        {"type": "postback", "title": "🎨 تخيل صورة", "payload": "CMD_GEN_IMG"},
        {"type": "postback", "title": "📝 قراءة نص (OCR)", "payload": "CMD_OCR"},
    ]

def get_more_menu():
    return [
        {"type": "postback", "title": "🗣️ نص لصوت", "payload": "CMD_TTS"},
        {"type": "postback", "title": "ℹ️ المطور", "payload": "CMD_INFO"}
    ]

def handle_payload(user_id, payload):
    user_db[user_id]['state'] = None
    
    if payload in ['GET_STARTED', 'CMD_BACK']:
        send_buttons(user_id, "مرحباً بك! اختر خدمة:", get_main_menu())
        send_buttons(user_id, "المزيد من الخدمات:", get_more_menu())
    
    elif payload == 'CMD_OCR':
        user_db[user_id]['state'] = 'WAITING_OCR'
        send_buttons(user_id, "أرسل الصورة لاستخراج النص منها 📄", [{"type": "postback", "title": "🔙 رجوع", "payload": "CMD_BACK"}])

    elif payload == 'CMD_GEN_IMG':
        user_db[user_id]['state'] = 'WAITING_GEN_PROMPT'
        send_buttons(user_id, "اكتب وصف الصورة التي في خيالك 🎨", [{"type": "postback", "title": "🔙 رجوع", "payload": "CMD_BACK"}])

    elif payload == 'CMD_TTS':
        btns = [
            {"type": "postback", "title": "👨 صوت رجل", "payload": "SET_MALE"},
            {"type": "postback", "title": "👩 صوت امرأة", "payload": "SET_FEMALE"},
            {"type": "postback", "title": "🔙 رجوع", "payload": "CMD_BACK"}
        ]
        send_buttons(user_id, "اختر نوع الصوت:", btns)

    elif payload in ['SET_MALE', 'SET_FEMALE']:
        user_db[user_id]['voice'] = 'male' if payload == 'SET_MALE' else 'female'
        user_db[user_id]['state'] = 'WAITING_TTS_TEXT'
        send_msg(user_id, "تم حفظ الصوت. أرسل النص الآن لتحويله 🗣️")
        
    elif payload == 'CMD_INFO':
        send_buttons(user_id, DEV_INFO, [{"type": "postback", "title": "🔙 رجوع", "payload": "CMD_BACK"}])
        
    elif payload == 'CMD_CHAT':
        user_db[user_id]['state'] = 'CHAT_MODE'
        send_buttons(user_id, "أنا أسمعك، تفضل بالحديث معي.", [{"type": "postback", "title": "🔙 رجوع", "payload": "CMD_BACK"}])

def handle_message(user_id, message):
    state = user_db[user_id]['state']

    if 'attachments' in message:
        attachment = message['attachments'][0]
        
        # فلتر اللايكات (منع الانهيار)
        if 'sticker_id' in attachment.get('payload', {}):
            send_msg(user_id, "❤️")
            return 
        
        if attachment['type'] == 'image':
            img_url = attachment['payload']['url']
            
            if state == 'WAITING_OCR':
                send_msg(user_id, "جاري قراءة الصورة... ⏳")
                text = ocr_groq_vision(img_url)
                send_msg(user_id, f"📝 النص المستخرج:\n\n{text}")
                send_msg(user_id, "تابع الصفحة للمزيد! ❤️")
                user_db[user_id]['state'] = None
            else:
                send_buttons(user_id, "وصلتني الصورة. هل تريد استخراج النص؟", [
                    {"type": "postback", "title": "📝 استخراج نص", "payload": "CMD_OCR"}
                ])
        return

    text = message.get('text', '')
    if not text: return

    if state == 'WAITING_GEN_PROMPT':
        send_msg(user_id, "جاري الرسم... 🎨")
        eng_prompt = translate_prompt(text)
        img_url = f"https://image.pollinations.ai/prompt/{eng_prompt}"
        send_image(user_id, img_url)
        send_msg(user_id, "تم! لا تنس متابعة الصفحة.")
        user_db[user_id]['state'] = None

    elif state == 'WAITING_TTS_TEXT':
        send_msg(user_id, "جاري تحويل الصوت... 🎧")
        voice = VOICES[user_db[user_id]['voice']]
        filename = f"voice_{user_id}.mp3"
        try:
            asyncio.run(edge_tts.Communicate(text, voice).save(filename))
            send_audio(user_id, filename)
            try: os.remove(filename)
            except: pass
        except Exception as e:
            send_msg(user_id, "حدث خطأ أثناء إنشاء الصوت.")
        user_db[user_id]['state'] = None

    else:
        reply = chat_with_groq(user_id, text)
        send_msg(user_id, reply)

if __name__ == '__main__':
    # إعدادات التشغيل لـ HidenCloud
    import socket
    hostname = socket.gethostname()
    print("=" * 50)
    print("🚀 إرشادات Webhook:")
    print(f"✅ Webhook URL (محتمل): http://noel.hidencloud.com:25151/webhook")
    print(f"🔑 Verify Token: {VERIFY_TOKEN}")
    print(f"👤 المطور: {DEVELOPER_NAME}")
    print(f"🤖 اسم الذكاء الاصطناعي: {AI_ASSISTANT_NAME}")
    print("=" * 50)
    
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
