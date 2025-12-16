import os
import json
import requests
import textwrap
import time
from flask import Flask, request
from collections import defaultdict, deque

# ====================================================================
# 🏛️ إعدادات النظام والمفاتيح
# ====================================================================

VERIFY_TOKEN = 'boykta2025'
PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

# مفاتيح Groq (نظام التدوير لتفادي الحظر)
GROQ_KEYS = [
    'gsk_' + '34XBDQmFexlI6vO6eHlpWGdyb3FYlPKWUUM5njFhsahXQ2cgieJC',
    'gsk_' + 'FflkgKFaxSSSjPNeErnvWGdyb3FYinkYOIkZ5NArQ5kVRyWMWn1P',
    'gsk_' + 'w1V0n7g3g3DomcBJkLxfWGdyb3FYzStNZi5uJL7VlqvLO6vcDOYn'
]

MODELS = {
    'chat': "llama-3.3-70b-versatile",
    'vision': "llama-3.2-11b-vision-preview",
    'fast': "llama3-8b-8192"
}

# شخصية البوت (المدرس الجزائري + المساعد الذكي)
SYSTEM_PROMPT = """
أنت "بويكتا"، مساعد ذكي جزائري محترف.
1. السياق الدراسي: إذا كان السؤال تعليمياً، اشرح وحل وفق "المنهاج الجزائري" وبلهجة مفهومة أو عربية فصحى مبسطة.
2. الصور: إذا وصلك نص مستخرج، لا تحلله فوراً، انتظر سؤال المستخدم عنه.
3. الأسلوب: كن سريعاً، دقيقاً، واستخدم الإيموجي المناسب لتلطيف الجو.
"""

app = Flask(__name__)

# ====================================================================
# 🧠 الذاكرة وإدارة الجلسات
# ====================================================================

class UserSession:
    def __init__(self):
        self.mode = 'MAIN_MENU'
        self.history = deque(maxlen=8) # ذاكرة قصيرة للدردشة
        self.ocr_buffer = "" # مخزن النص المستخرج
        self.last_interaction = time.time()

user_db = defaultdict(UserSession)

# ====================================================================
# 🛠️ أدوات الاتصال (API & Utilities)
# ====================================================================

def send_facebook_request(payload):
    """إرسال طلب خام لفيسبوك"""
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"Facebook API Error: {e}")

def send_typing_on(user_id):
    """إظهار النقاط المتحركة (...) ليوحي البوت بالتفكير"""
    send_facebook_request({
        'recipient': {'id': user_id},
        'sender_action': 'typing_on'
    })

def send_text(user_id, text):
    """إرسال نص بسيط"""
    if not text: return
    chunks = textwrap.wrap(text, 1900, replace_whitespace=False)
    for chunk in chunks:
        send_facebook_request({'recipient': {'id': user_id}, 'message': {'text': chunk}})

def send_quick_replies(user_id, text, options):
    """
    إرسال أزرار الرد السريع (فوق لوحة المفاتيح)
    options = [{'title': 'نعم', 'payload': 'YES'}, ...]
    """
    quick_replies = []
    for opt in options:
        quick_replies.append({
            "content_type": "text",
            "title": opt['title'],
            "payload": opt['payload']
        })
    
    send_facebook_request({
        'recipient': {'id': user_id},
        'message': {
            'text': text,
            'quick_replies': quick_replies
        }
    })

def send_like(user_id):
    """رد بـ لايك 👍"""
    send_text(user_id, "👍")

def robust_groq_call(messages, model):
    """الاتصال بالذكاء الاصطناعي مع تدوير المفاتيح"""
    for key in GROQ_KEYS:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": messages, "temperature": 0.6},
                timeout=25
            )
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content']
        except:
            continue
    return "⚠️ الخوادم مشغولة حالياً، يرجى المحاولة بعد لحظات."

# ====================================================================
# 🎮 منطق المعالجة (Controller)
# ====================================================================

def handle_message_logic(user_id, message_data, session):
    # 1. تحديث وقت التفاعل
    session.last_interaction = time.time()

    # 2. كشف "اللايك" (Stickers/Likes)
    # عادة اللايك يكون له sticker_id محدد أو يأتي كمرفق
    is_sticker = False
    if 'sticker_id' in message_data: is_sticker = True
    if 'attachments' in message_data:
        for att in message_data['attachments']:
            if 'sticker_id' in att.get('payload', {}):
                is_sticker = True
    
    if is_sticker:
        return send_like(user_id) # رد فوراً بـ لايك وتجاهل الباقي

    # 3. معالجة الصور (OCR)
    if 'attachments' in message_data and message_data['attachments'][0]['type'] == 'image':
        img_url = message_data['attachments'][0]['payload']['url']
        
        send_typing_on(user_id) # إظهار جاري الكتابة...
        send_text(user_id, "🔍 جاري قراءة الصورة...")
        
        # استخراج النص
        ocr_msg = [{"role": "user", "content": [{"type": "text", "text": "Extract text only"}, {"type": "image_url", "image_url": {"url": img_url}}]}]
        text_result = robust_groq_call(ocr_msg, MODELS['vision'])
        
        # حفظ النص في الذاكرة المؤقتة
        session.ocr_buffer = text_result
        session.mode = 'WAITING_OCR_INSTRUCTION'
        
        send_text(user_id, f"📝 النص المستخرج:\n\n{text_result}")
        
        # إظهار أزرار سريعة (فوق الكيبورد)
        qrs = [
            {'title': 'حل التمرين 🎓', 'payload': 'DO_SOLVE'},
            {'title': 'ترجمة للعربية 🔤', 'payload': 'DO_TRANSLATE'},
            {'title': 'تلخيص 📄', 'payload': 'DO_SUMMARIZE'},
            {'title': 'إلغاء ❌', 'payload': 'RESET'}
        ]
        send_quick_replies(user_id, "ماذا أفعل بهذا النص؟ اختر أو اكتب سؤالك:", qrs)
        return

    # 4. معالجة النصوص
    user_text = message_data.get('text', '')
    
    # التعامل مع الأزرار السريعة (Payloads يتم إرسالها كنص في Quick Replies)
    # ملاحظة: في Quick Replies، الـ payload يأتي أحياناً في quick_reply object
    payload = None
    if 'quick_reply' in message_data:
        payload = message_data['quick_reply']['payload']
    
    # تحويل الـ Payloads إلى أوامر نصية للمعالجة
    if payload == 'DO_SOLVE': user_text = "حل هذا التمرين بالمنهاج الجزائري"
    elif payload == 'DO_TRANSLATE': user_text = "ترجم هذا النص للعربية"
    elif payload == 'DO_SUMMARIZE': user_text = "لخص هذا النص"
    elif payload == 'RESET': 
        session.mode = 'MAIN_MENU'
        session.ocr_buffer = ""
        send_quick_replies(user_id, "تم الإلغاء. ماذا تريد الآن؟", [
            {'title': 'دردشة 🤖', 'payload': 'MODE_CHAT'},
            {'title': 'تخيل صورة 🎨', 'payload': 'MODE_IMG'}
        ])
        return

    if not user_text: return

    # --- توجيه الرسالة حسب الوضع ---
    
    send_typing_on(user_id) # نقط...

    if session.mode == 'WAITING_OCR_INSTRUCTION':
        # دمج النص المخزن مع طلب المستخدم
        full_prompt = f"النص الأصلي:\n{session.ocr_buffer}\n\nطلب المستخدم:\n{user_text}\n\nنفذ الطلب بدقة."
        resp = robust_groq_call([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": full_prompt}], MODELS['chat'])
        send_text(user_id, resp)
        # تصفير الذاكرة المؤقتة
        session.mode = 'MAIN_MENU'
        session.ocr_buffer = ""
        send_quick_replies(user_id, "هل تحتاج شيئاً آخر؟", [{'title': 'نعم', 'payload': 'RESET'}, {'title': 'شكراً', 'payload': 'THANKS'}])

    elif session.mode == 'CHAT_MODE':
        if payload == 'EXIT_CHAT':
            session.mode = 'MAIN_MENU'
            send_text(user_id, "تم الخروج من المحادثة.")
            return

        session.history.append({"role": "user", "content": user_text})
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + list(session.history)
        resp = robust_groq_call(msgs, MODELS['chat'])
        session.history.append({"role": "assistant", "content": resp})
        send_text(user_id, resp)

    elif session.mode == 'IMG_WAIT_PROMPT':
        # ترجمة الوصف للإنجليزية وتوليد الصورة
        en_prompt = robust_groq_call([{"role": "user", "content": f"Translate to English prompt only: {user_text}"}], MODELS['fast'])
        img_url = f"https://image.pollinations.ai/prompt/{en_prompt}"
        
        # إرسال الصورة
        send_facebook_request({'recipient': {'id': user_id}, 'message': {'attachment': {'type': 'image', 'payload': {'url': img_url, 'is_reusable': True}}}})
        session.mode = 'MAIN_MENU'
        send_quick_replies(user_id, "كيف كانت الصورة؟", [{'title': 'رائعة', 'payload': 'GOOD'}, {'title': 'أريد أخرى', 'payload': 'MODE_IMG'}])

    else:
        # القائمة الرئيسية (الوضع الافتراضي)
        if payload == 'MODE_CHAT':
            session.mode = 'CHAT_MODE'
            session.history.clear()
            send_quick_replies(user_id, "أنا معك، تفضل بالحديث...", [{'title': 'خروج 🔙', 'payload': 'EXIT_CHAT'}])
        elif payload == 'MODE_IMG':
            session.mode = 'IMG_WAIT_PROMPT'
            send_text(user_id, "صف لي الصورة التي في خيالك 🎨")
        else:
            # رسالة ترحيبية بالقوائم السريعة
            btns = [
                {'title': 'دردشة/سؤال 🤖', 'payload': 'MODE_CHAT'},
                {'title': 'إنشاء صورة 🎨', 'payload': 'MODE_IMG'},
                {'title': 'مساعدة ℹ️', 'payload': 'HELP'}
            ]
            # ملاحظة: إذا أرسل صورة هنا سيتم التقاطها في كود الصور بالأعلى
            send_quick_replies(user_id, "مرحباً! أرسل صورة لاستخراج النص منها، أو اختر خدمة:", btns)

# ====================================================================
# 🌐 WEBHOOK
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return 'Err'

    if request.method == 'POST':
        try:
            data = request.get_json()
            if data['object'] == 'page':
                for entry in data['entry']:
                    for event in entry.get('messaging', []):
                        sender_id = event['sender']['id']
                        
                        # تجاهل رسائل التسليم والقراءة (Delivery & Read receipts)
                        if 'delivery' in event or 'read' in event: continue
                        
                        session = user_db[sender_id]
                        
                        # دمج الـ Postback مع الرسائل العادية لتبسيط المعالجة
                        if 'postback' in event:
                            # تحويل الـ Postback إلى رسالة تحتوي quick_reply وهمي للمعالجة الموحدة
                            msg = {'text': '', 'quick_reply': {'payload': event['postback']['payload']}}
                            handle_message_logic(sender_id, msg, session)
                        elif 'message' in event:
                            handle_message_logic(sender_id, event['message'], session)
                            
        except Exception as e:
            print(f"Main Loop Error: {e}")
        return 'ok'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
