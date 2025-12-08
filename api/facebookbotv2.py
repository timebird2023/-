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

# 🔑 التوكنات (تأكد من وجودها في إعدادات Vercel)
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'boykta2025')
PAGE_ACCESS_TOKEN = "EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9"

# 🌐 رابط الذكاء الاصطناعي فقط
AI_API_URL = "http://fi8.bot-hosting.net:20163/elos-gpt3"

# ذاكرة بسيطة للمحادثة (لجعل البوت يتذكر سياق الحديث)
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
            logger.error(f"❌ Send Error: {response.text}")
    except Exception as e:
        logger.error(f"❌ Connection Error: {e}")

def send_text_message(recipient_id, text):
    """إرسال رسالة نصية"""
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': text[:2000]} # فيسبوك يقبل 2000 حرف كحد أقصى للرسالة الواحدة
    }
    send_api_request(payload)

def send_typing_on(recipient_id):
    """إظهار مؤشر 'جاري الكتابة...'"""
    payload = {
        'recipient': {'id': recipient_id},
        'sender_action': 'typing_on'
    }
    send_api_request(payload)

# ====================================================================
# 🧠 الذكاء الاصطناعي
# ====================================================================

def handle_ai_chat(user_id, user_text):
    """إرسال النص للذكاء الاصطناعي والرد"""
    
    # 1. تجهيز السياق (اختياري لتحسين المحادثة)
    # نأخذ آخر 3 ردود ليتذكر البوت عما نتحدث
    history = in_memory_conversations[user_id][-3:]
    full_prompt = user_text
    
    if history:
        context_str = "\n".join([f"User: {h[0]}\nBot: {h[1]}" for h in history])
        full_prompt = f"{context_str}\nUser: {user_text}\nBot:"

    try:
        # 2. استدعاء API
        response = requests.get(AI_API_URL, params={'text': full_prompt}, timeout=45)
        
        if response.ok:
            reply = response.text.strip()
            
            # تنظيف الرد إذا كان JSON (احتياطاً)
            try:
                json_data = json.loads(reply)
                if isinstance(json_data, dict):
                    reply = json_data.get('response', json_data.get('reply', reply))
            except:
                pass

            # 3. حفظ المحادثة
            in_memory_conversations[user_id].append((user_text, reply))
            # الحفاظ على حجم الذاكرة صغيراً
            if len(in_memory_conversations[user_id]) > 5:
                in_memory_conversations[user_id].pop(0)

            # 4. إرسال الرد
            send_text_message(user_id, reply)
        else:
            send_text_message(user_id, "عذراً، الخادم مشغول حالياً.")
            
    except Exception as e:
        logger.error(f"AI API Error: {e}")
        send_text_message(user_id, "حدث خطأ في الاتصال.")

# ====================================================================
# 🌐 Webhook (نقطة الاتصال مع فيسبوك)
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. التحقق من الرابط (Verify Token)
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Invalid Token', 403

    # 2. استقبال الرسائل
    elif request.method == 'POST':
        data = request.get_json()
        if data:
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    
                    # تجاهل رسائل التسليم والقراءة
                    if 'delivery' in event or 'read' in event:
                        continue
                    
                    # معالجة النصوص فقط
                    if event.get('message') and event['message'].get('text'):
                        user_text = event['message']['text'].strip()
                        
                        # إظهار "جاري الكتابة" لإعطاء طابع حيوي
                        send_typing_on(sender_id)
                        
                        # معالجة الرد
                        handle_ai_chat(sender_id, user_text)
                    
                    # إذا أرسل المستخدم مرفقاً (صورة/فيديو)، نتجاهله أو نرد برسالة بسيطة
                    elif event.get('message') and event['message'].get('attachments'):
                        send_text_message(sender_id, "عذراً، أنا أدعم المحادثات النصية فقط حالياً.")

        return 'OK', 200

# ====================================================================
# 🚀 التشغيل
# ====================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
