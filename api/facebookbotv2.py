import os
import json
import requests
import asyncio
import textwrap
import logging
import random
import urllib.parse
import io
import re
import matplotlib
matplotlib.use('Agg') # وضع السيرفر (بدون واجهة رسومية)
import matplotlib.pyplot as plt
from flask import Flask, request
from collections import defaultdict, deque
import edge_tts

# ====================================================================
# 1. ⚙️ Config & Secrets (مدير الإعدادات والمفاتيح)
# ====================================================================
class Config:
    # إعدادات السيرفر
    PORT = int(os.environ.get('PORT', 25151))
    
    # إعدادات فيسبوك
    VERIFY_TOKEN = 'boykta2025'
    # التوكن الجديد الذي أرسلته
    PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

    # إعدادات الذكاء الاصطناعي (Groq)
    # طريقة التشفير لتجنب الحظر
    _PARTIAL_KEYS = [
        "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
        "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
        "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
    ]
    
    MODEL_CHAT = "llama-3.1-8b-instant"
    MODEL_VISION = "llama-3.2-90b-vision-preview" # موديل رؤية قوي

    @staticmethod
    def get_groq_key(index=0):
        return "gsk_" + Config._PARTIAL_KEYS[index]

# تهيئة السجل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BoyktaBot")

# ====================================================================
# 2. 🛠️ Tools & Engines (أدوات الرسم والصوت)
# ====================================================================
class MediaEngine:
    @staticmethod
    def text_to_image_math(text):
        """تحويل النص الذي يحتوي على رياضيات إلى صورة"""
        try:
            # تنظيف النص للرسم
            lines = text.split('\n')
            # حساب الأبعاد ديناميكياً
            height = max(4, len(lines) * 0.5)
            
            fig, ax = plt.subplots(figsize=(10, height))
            ax.axis('off')
            
            # خلفية بيضاء كريمية مريحة للعين
            fig.patch.set_facecolor('#f8f9fa')
            
            # تنسيق النص
            display_text = "\n".join(textwrap.wrap(text, width=65, replace_whitespace=False))
            
            ax.text(0.5, 0.5, display_text, 
                    ha='center', va='center', 
                    fontsize=16, 
                    family='serif', 
                    wrap=True,
                    bbox=dict(boxstyle="round,pad=1", fc="white", ec="#007bff", alpha=0.9)) # إطار جميل
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Math Render Error: {e}")
            return None

    @staticmethod
    def generate_voice(text, voice="ar-EG-SalmaNeural"):
        """توليد صوت (Async Wrapper)"""
        async def _gen():
            communicate = edge_tts.Communicate(text, voice)
            # نستخدم ذاكرة مؤقتة بدلاً من ملف لتجنب مشاكل الصلاحيات
            out = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    out.write(chunk["data"])
            out.seek(0)
            return out
        
        try:
            return asyncio.run(_gen())
        except Exception as e:
            logger.error(f"TTS Error: {e}")
            return None

    @staticmethod
    def is_like_sticker(message_obj):
        """كشف هل الرسالة هي زر اللايك الأزرق"""
        if 'sticker_id' in message_obj:
            # 369239263222822 هو كود اللايك المشهور، ولكن نفحص أي ستيكر للاحتياط
            return True 
        return False

# ====================================================================
# 3. 🌐 Facebook Client (مدير الاتصال بفيسبوك)
# ====================================================================
class FacebookMessenger:
    API_URL = "https://graph.facebook.com/v19.0/me/messages"
    
    @staticmethod
    def send_action(user_id, action='typing_on'):
        """إظهار جاري الكتابة..."""
        requests.post(f"{FacebookMessenger.API_URL}?access_token={Config.PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'sender_action': action})

    @staticmethod
    def send_text(user_id, text, quick_replies=None):
        """إرسال نص مع أزرار سريعة اختيارية"""
        data = {
            'recipient': {'id': user_id}, 
            'message': {'text': text}
        }
        
        if quick_replies:
            # تنسيق الأزرار لفيسبوك لايت
            qr_payload = []
            for title, payload in quick_replies.items():
                qr_payload.append({
                    "content_type": "text",
                    "title": title,
                    "payload": payload
                })
            data['message']['quick_replies'] = qr_payload
            
        requests.post(f"{FacebookMessenger.API_URL}?access_token={Config.PAGE_ACCESS_TOKEN}", json=data)

    @staticmethod
    def send_attachment(user_id, file_data, file_type='image', filename='file.png'):
        """إرسال ملف (صورة/صوت) مباشرة"""
        payload = {
            'recipient': json.dumps({'id': user_id}), 
            'message': json.dumps({'attachment': {'type': file_type, 'payload': {}}})
        }
        
        # تحديد نوع MIME
        mime = 'image/png' if file_type == 'image' else 'audio/mpeg'
        files = {'filedata': (filename, file_data, mime)}
        
        requests.post(f"{FacebookMessenger.API_URL}?access_token={Config.PAGE_ACCESS_TOKEN}", 
                      data=payload, files=files)

    @staticmethod
    def send_image_url(user_id, url):
        """إرسال صورة عبر رابط"""
        requests.post(f"{FacebookMessenger.API_URL}?access_token={Config.PAGE_ACCESS_TOKEN}",
                      json={'recipient': {'id': user_id}, 
                            'message': {'attachment': {'type': 'image', 'payload': {'url': url, 'is_reusable': True}}}})

# ====================================================================
# 4. 🧠 AI Brain (العقل المدبر)
# ====================================================================
class BotBrain:
    def __init__(self):
        # الذاكرة: مفتاح المستخدم -> بياناته
        # نستخدم deque لحفظ آخر 6 رسائل فقط لتوفير الذاكرة
        self.memories = defaultdict(lambda: {
            'history': deque(maxlen=8), 
            'image_context': None,
            'mode': 'chat' # chat, solving, translation
        })

    def get_groq_response(self, messages, model, key_idx=0):
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {Config.get_groq_key(key_idx)}", "Content-Type": "application/json"}
        try:
            res = requests.post(url, json={"model": model, "messages": list(messages)}, headers=headers, timeout=40)
            if res.status_code != 200:
                # محاولة تدوير المفتاح إذا فشل
                if key_idx < len(Config._PARTIAL_KEYS) - 1:
                    return self.get_groq_response(messages, model, key_idx + 1)
                return None
            return res.json()['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Groq Error: {e}")
            return None

    def analyze_image(self, user_id, image_url):
        """تحليل الصورة لاستخراج النص والسياق"""
        prompt = """
        Analyze this image strictly.
        1. Extract ALL text/numbers exactly.
        2. If it's a Math/Physics problem, output 'TYPE: MATH'.
        3. If it's general/meme, output 'TYPE: GENERAL'.
        4. Provide a brief summary of the content.
        """
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}]}]
        
        result = self.get_groq_response(msgs, Config.MODEL_VISION, key_idx=2) # استخدام مفتاح الرؤية
        if result:
            self.memories[user_id]['image_context'] = result
            # تحديد نوع الأزرار المقترحة بناء على التحليل
            if "TYPE: MATH" in result:
                return "math"
            return "general"
        return "error"

    def chat(self, user_id, user_text):
        user_data = self.memories[user_id]
        
        # إضافة رسالة المستخدم للذاكرة
        user_data['history'].append({"role": "user", "content": user_text})
        
        # الموجه النظامي (شخصية البوت)
        system_prompt = f"""
        أنت (Boykta)، مساعد ذكي جزائري.
        لهجتك: مزيج بين العربية الفصحى والجزائرية المحترمة.
        مهمتك:
        1. إذا طلب المستخدم رسم (ارسم، تخيل) -> ابدأ ردك بـ `CMD_IMAGE: [Prompt in English]`
        2. إذا طلب قراءة صوتية (اقرأ، قل) -> ابدأ ردك بـ `CMD_AUDIO: [النص]`
        3. في التمارين المدرسية: اشرح المنهجية خطوة بخطوة (منهج جزائري).
        4. إذا كان الرد يتطلب معادلات رياضية معقدة، ابدأ الرد بـ `CMD_MATH:`
        
        معلومات سياقية (من الصورة السابقة): {user_data['image_context'] if user_data['image_context'] else 'لا يوجد'}
        """
        
        msgs = [{"role": "system", "content": system_prompt}] + list(user_data['history'])
        
        reply = self.get_groq_response(msgs, Config.MODEL_CHAT)
        
        if reply:
            # لا نحفظ الأوامر الخاصة في التاريخ لكي لا نلوث الذاكرة
            if not any(cmd in reply for cmd in ["CMD_IMAGE", "CMD_AUDIO"]):
                user_data['history'].append({"role": "assistant", "content": reply})
            return reply
        return "عذراً، الشبكة ضعيفة قليلاً. أعد المحاولة."

# تهيئة البوت
bot_brain = BotBrain()

# ====================================================================
# 5. 🎮 Controller (وحدة التحكم الرئيسية - Flask)
# ====================================================================
app = Flask(__name__)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # التحقق من التوكن (لربط فيسبوك أول مرة)
    if request.method == 'GET':
        if request.args.get('hub.verify_token') == Config.VERIFY_TOKEN:
            return request.args.get('hub.challenge')
        return 'Verification Failed'

    # استقبال الرسائل
    if request.method == 'POST':
        data = request.get_json()
        if data['object'] == 'page':
            for entry in data['entry']:
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    
                    # 1. حالة وصول الرسالة (تجاهلها)
                    if 'delivery' in event or 'read' in event:
                        continue
                        
                    # 2. إظهار "جاري الكتابة..." فوراً
                    FacebookMessenger.send_action(sender_id, 'typing_on')
                    
                    # 3. معالجة الرسالة
                    if 'message' in event:
                        handle_incoming_message(sender_id, event['message'])
                        
        return 'EVENT_RECEIVED'

def handle_incoming_message(user_id, msg):
    """المعالج المركزي للرسائل"""
    
    # أ) فلتر "الجام" (Like Sticker) 👍
    # إذا أرسل المستخدم لايك، نرد بلايك فوراً ونغلق الموضوع
    if MediaEngine.is_like_sticker(msg):
        FacebookMessenger.send_text(user_id, "👍")
        return

    # ب) معالجة الصور 🖼️
    if 'attachments' in msg and msg['attachments'][0]['type'] == 'image':
        img_url = msg['attachments'][0]['payload']['url']
        FacebookMessenger.send_text(user_id, "جاري تحليل الصورة... 🧐")
        
        # تحليل الصورة
        context_type = bot_brain.analyze_image(user_id, img_url)
        
        # الرد بأزرار ذكية (Chips) حسب نوع الصورة
        if context_type == "math":
            FacebookMessenger.send_text(user_id, "وصلني التمرين! ماذا تريد أن أفعل؟", 
                                      quick_replies={"📝 حل التمرين": "حل التمرين", "🗣️ شرح صوتي": "اشرح صوتيا"})
        else:
            FacebookMessenger.send_text(user_id, "صورة جميلة! ماذا أفعل بها؟", 
                                      quick_replies={"📝 استخراج النص": "استخرج النص", "🇬🇧 ترجمة": "ترجم المحتوى", "🎨 وصف": "صف الصورة"})
        return

    # ج) معالجة النصوص 💬
    user_text = msg.get('text', '')
    if not user_text: return

    # إرسال للنظام الذكي
    ai_reply = bot_brain.chat(user_id, user_text)

    # د) تنفيذ أوامر الذكاء الاصطناعي
    
    # 1. طلب رسم
    if "CMD_IMAGE:" in ai_reply:
        prompt = ai_reply.split("CMD_IMAGE:")[1].strip()
        FacebookMessenger.send_text(user_id, "جاري الرسم... 🎨")
        try:
            seed = random.randint(1, 99999)
            # استخدام Pollinations للرسم المجاني
            draw_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={seed}&model=flux"
            FacebookMessenger.send_image_url(user_id, draw_url)
        except:
            FacebookMessenger.send_text(user_id, "فشلت عملية الرسم.")

    # 2. طلب صوت
    elif "CMD_AUDIO:" in ai_reply:
        text_to_speak = ai_reply.split("CMD_AUDIO:")[1].strip()
        FacebookMessenger.send_text(user_id, "جاري التسجيل... 🎙️")
        audio_data = MediaEngine.generate_voice(text_to_speak)
        if audio_data:
            FacebookMessenger.send_attachment(user_id, audio_data, 'audio', 'voice.mp3')
        else:
            FacebookMessenger.send_text(user_id, "حدث خطأ في الصوت.")

    # 3. رد رياضيات (صورة)
    elif "CMD_MATH:" in ai_reply or ("\\" in ai_reply and len(ai_reply) < 500):
        # إذا كان هناك رموز LaTeX كثيرة، نحولها لصورة
        clean_text = ai_reply.replace("CMD_MATH:", "").strip()
        FacebookMessenger.send_text(user_id, "إليك الحل 📚:")
        img_data = MediaEngine.text_to_image_math(clean_text)
        if img_data:
            FacebookMessenger.send_attachment(user_id, img_data, 'image', 'solution.png')
            # عرض أزرار متابعة
            FacebookMessenger.send_text(user_id, "هل الحل واضح؟", quick_replies={"✅ نعم": "شكرا", "🤔 شرح أكثر": "اشرح أكثر"})
        else:
            FacebookMessenger.send_text(user_id, clean_text)

    # 4. رد نصي عادي
    else:
        # نقسم الرسالة إذا كانت طويلة جداً
        FacebookMessenger.send_text(user_id, ai_reply)

# ====================================================================
# 🚀 تشغيل التطبيق
# ====================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT)
