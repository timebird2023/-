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
# ضبط المكتبة لتعمل بدون شاشة (Server Mode)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request
from collections import defaultdict, deque
import edge_tts

# ====================================================================
# 1. 🛡️ التكوين والإعدادات (The Vault)
# ====================================================================
class Config:
    PORT = int(os.environ.get('PORT', 25151))
    VERIFY_TOKEN = 'boykta2025'
    PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

    # مفاتيح Groq (تدوير تلقائي لتجنب الحظر)
    _PARTIAL_KEYS = [
        "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
        "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
        "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
    ]
    
    MODEL_CHAT = "llama-3.1-8b-instant"
    MODEL_VISION = "llama-3.2-90b-vision-preview"

    @staticmethod
    def get_api_key(index=0):
        return "gsk_" + Config._PARTIAL_KEYS[index % len(Config._PARTIAL_KEYS)]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BoyktaBot_V3")

# ====================================================================
# 2. 🧹 المعالج والمنظف (The Parser & Cleaner)
# ====================================================================
class ContentParser:
    """
    مهمته: استلام رد الذكاء الاصطناعي الخام، وتنظيفه من الأوامر البرمجية
    لكي لا تظهر للمستخدم (مثل CMD_IMAGE).
    """
    @staticmethod
    def parse(ai_response):
        """
        يحلل الرد ويعيد قاموساً يحتوي على النوع والمحتوى
        """
        if not ai_response:
            return {"type": "text", "content": "عذراً، حدث خطأ في المعالجة."}

        # 1. فحص أوامر الرسم
        # يبحث عن CMD_IMAGE: متبوعاً بأي نص
        img_match = re.search(r'CMD_IMAGE:\s*(.+)', ai_response, re.IGNORECASE)
        if img_match:
            return {"type": "command_image", "content": img_match.group(1).strip()}

        # 2. فحص أوامر الصوت
        audio_match = re.search(r'CMD_AUDIO:\s*(.+)', ai_response, re.IGNORECASE)
        if audio_match:
            return {"type": "command_audio", "content": audio_match.group(1).strip()}

        # 3. فحص الرياضيات (لتحويلها لصورة)
        # إذا كان النص يحتوي على LaTeX معقد، نعتبره رياضيات
        # لكن نتأكد أنه ليس نصاً عربياً طويلاً لتجنب المربعات
        if "CMD_MATH:" in ai_response:
            math_content = ai_response.replace("CMD_MATH:", "").strip()
            return {"type": "math_render", "content": math_content}

        # 4. نص عادي (نحذف أي شوائب بقيت)
        clean_text = ai_response.replace("CMD_IMAGE:", "").replace("CMD_AUDIO:", "").replace("CMD_MATH:", "")
        return {"type": "text", "content": clean_text.strip()}

# ====================================================================
# 3. 🎨 محركات الوسائط (Media Engines)
# ====================================================================
class MediaEngine:
    @staticmethod
    def render_math_to_image(latex_text):
        """
        تحويل المعادلات الرياضية لصورة.
        لتجنب المربعات في العربية، سنستخدم خطاً افتراضياً للرياضيات فقط.
        """
        try:
            fig, ax = plt.subplots(figsize=(10, 2)) # حجم مضغوط
            ax.axis('off')
            
            # نستخدم render latex الخاص بـ matplotlib
            # نضع النص داخل $$ ليتم معاملته كرياضيات
            # نقوم بتنظيف النص قليلاً
            clean_latex = f"${latex_text.replace('$', '')}$"
            
            ax.text(0.5, 0.5, clean_latex, 
                    ha='center', va='center', fontsize=20, color='black')
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150, transparent=False)
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Render Error: {e}")
            return None

    @staticmethod
    def generate_voice(text):
        """توليد الصوت باستخدام Edge-TTS"""
        async def _run():
            # نستخدم صوت سلمى المصري فهو ممتاز
            communicate = edge_tts.Communicate(text, "ar-EG-SalmaNeural")
            out = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    out.write(chunk["data"])
            out.seek(0)
            return out
        try:
            return asyncio.run(_run())
        except:
            return None

# ====================================================================
# 4. 🌐 واجهة فيسبوك (The Messenger Interface)
# ====================================================================
class FacebookAPI:
    URL = "https://graph.facebook.com/v19.0/me/messages"
    
    @staticmethod
    def send_typing(user_id):
        requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'sender_action': 'typing_on'})

    @staticmethod
    def send_text(user_id, text, quick_replies=None):
        if not text: return
        
        # تقسيم النص الطويل
        chunks = textwrap.wrap(text, 1900, replace_whitespace=False)
        
        for i, chunk in enumerate(chunks):
            payload = {'recipient': {'id': user_id}, 'message': {'text': chunk}}
            
            # نضيف الأزرار فقط مع آخر جزء من الرسالة
            if i == len(chunks) - 1 and quick_replies:
                qr_list = []
                for title, data in quick_replies.items():
                    qr_list.append({"content_type": "text", "title": title, "payload": data})
                payload['message']['quick_replies'] = qr_list
                
            requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", json=payload)

    @staticmethod
    def send_file(user_id, file_data, type='image'):
        files = {'filedata': ('file.png' if type=='image' else 'audio.mp3', file_data, 'image/png' if type=='image' else 'audio/mpeg')}
        payload = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': type, 'payload': {}}})}
        requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", data=payload, files=files)

    @staticmethod
    def send_image_url(user_id, url):
        requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}",
                      json={'recipient': {'id': user_id}, 'message': {'attachment': {'type': 'image', 'payload': {'url': url, 'is_reusable': True}}}})

# ====================================================================
# 5. 🧠 العقل المركزي (The Brain)
# ====================================================================
class BotBrain:
    def __init__(self):
        self.db = defaultdict(lambda: {'history': deque(maxlen=6), 'img_ctx': None})

    def ask_ai(self, messages, model, temp=0.7):
        """دالة موحدة للاتصال بـ Groq"""
        for attempt in range(3): # 3 محاولات بمفاتيح مختلفة
            key = Config.get_api_key(attempt)
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": model, "messages": messages, "temperature": temp},
                    timeout=30
                )
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
            except Exception as e:
                logger.error(f"AI Error ({attempt}): {e}")
        return None

    def process_image(self, user_id, img_url):
        """تحليل الصورة"""
        prompt = "Analyze this image. If it's math/physics, solve it. If text, extract it. If object, describe it. Return concise summary."
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img_url}}]}]
        analysis = self.ask_ai(msgs, Config.MODEL_VISION)
        if analysis:
            self.db[user_id]['img_ctx'] = analysis
            return analysis
        return None

    def chat(self, user_id, user_msg):
        """معالجة المحادثة"""
        user_data = self.db[user_id]
        
        # 1. تحضير السياق
        system_instruction = f"""
        أنت مساعد ذكي ومحترف.
        القواعد الصارمة جداً:
        1. إذا طلب المستخدم إنشاء صورة -> رد فقط بـ: CMD_IMAGE: <وصف بالانجليزية>
        2. إذا طلب قراءة نص -> رد فقط بـ: CMD_AUDIO: <النص>
        3. إذا كان الحل معادلة رياضية معقدة (LaTeX) -> رد فقط بـ: CMD_MATH: <LatexCode>
        4. في الحالات العادية، رد بنص عربي مهذب ومختصر ومفيد.
        
        سياق الصورة المرفقة سابقاً (إن وجد): {user_data['img_ctx'] or "لا يوجد"}
        """
        
        msgs = [{"role": "system", "content": system_instruction}] + list(user_data['history']) + [{"role": "user", "content": user_msg}]
        
        # 2. الحصول على الرد
        raw_reply = self.ask_ai(msgs, Config.MODEL_CHAT)
        
        # 3. حفظ في التاريخ (فقط النصوص العادية، لا نحفظ الأوامر البرمجية)
        if raw_reply and "CMD_" not in raw_reply:
            user_data['history'].append({"role": "user", "content": user_msg})
            user_data['history'].append({"role": "assistant", "content": raw_reply})
            
        return raw_reply

bot = BotBrain()

# ====================================================================
# 6. 🎮 نقطة التحكم (Main Controller)
# ====================================================================
app = Flask(__name__)

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return request.args.get('hub.challenge') if request.args.get('hub.verify_token') == Config.VERIFY_TOKEN else 'Error'

    if request.method == 'POST':
        data = request.get_json()
        if data['object'] == 'page':
            for entry in data['entry']:
                for event in entry.get('messaging', []):
                    if 'message' in event:
                        process_event(event['sender']['id'], event['message'])
        return 'OK'

def process_event(user_id, msg):
    # 1. إظهار "جاري الكتابة" فوراً لإعطاء شعور بالسرعة
    FacebookAPI.send_typing(user_id)

    # 🛑 2. تصفية "الجام" (Like Sticker)
    # اللايك له sticker_id محدد وغالباً يكون 369239263222822
    # لكن سنفحص وجود أي sticker_id لنتجنب معالجتها كصور
    if msg.get('sticker_id'):
        FacebookAPI.send_text(user_id, "👍") # رد سريع بنفس الحركة
        return

    # 🖼️ 3. معالجة الصور المرفقة
    if 'attachments' in msg and msg['attachments'][0]['type'] == 'image':
        # تأكد أنها ليست ستيكر (بعض الستيكرات تأتي كمرفق صورة)
        if msg.get('sticker_id'): 
            FacebookAPI.send_text(user_id, "❤️")
            return

        url = msg['attachments'][0]['payload']['url']
        FacebookAPI.send_text(user_id, "لحظة، أحلل الصورة... 🧐")
        
        analysis = bot.process_image(user_id, url)
        if analysis:
            # نقترح أزراراً بناءً على التحليل (بسيط)
            btns = {"📝 حل/شرح": "اشرح لي", "🎨 وصف": "صف الصورة"}
            FacebookAPI.send_text(user_id, "تم التحليل! ماذا تريد؟", quick_replies=btns)
        else:
            FacebookAPI.send_text(user_id, "لم أستطع قراءة الصورة بوضوح.")
        return

    # 💬 4. معالجة النصوص
    text = msg.get('text')
    if not text: return

    # استدعاء العقل المدبر
    raw_response = bot.chat(user_id, text)
    
    # تنظيف وتفسير الرد (هنا السحر ✨)
    parsed = ContentParser.parse(raw_response)

    # تنفيذ الأمر المناسب
    if parsed['type'] == 'command_image':
        FacebookAPI.send_text(user_id, "جاري الرسم... 🎨")
        # رابط Pollinations ممتاز ومجاني
        prompt_safe = urllib.parse.quote(parsed['content'])
        img_url = f"https://image.pollinations.ai/prompt/{prompt_safe}?width=1024&height=1024&model=flux&seed={random.randint(0,9999)}"
        FacebookAPI.send_image_url(user_id, img_url)

    elif parsed['type'] == 'command_audio':
        FacebookAPI.send_text(user_id, "جاري التسجيل... 🎙️")
        audio_data = MediaEngine.generate_voice(parsed['content'])
        if audio_data:
            FacebookAPI.send_file(user_id, audio_data, 'audio')
        else:
            FacebookAPI.send_text(user_id, "عذراً، حدث خطأ في الصوت.")

    elif parsed['type'] == 'math_render':
        # نحول المعادلة لصورة، ونرسلها
        FacebookAPI.send_text(user_id, "الحل الرياضي 📐:")
        img_data = MediaEngine.render_math_to_image(parsed['content'])
        if img_data:
            FacebookAPI.send_file(user_id, img_data, 'image')
        else:
            # فشل الرسم؟ أرسل النص كما هو كخطة بديلة
            FacebookAPI.send_text(user_id, parsed['content'])

    else: # type == text
        # رد نصي عادي مع أزرار مقترحة دائماً للحفاظ على التفاعل
        suggestions = {"🗣️ اسمعها": "اقرأ النص", "🎨 تخيلها": "ارسم لي صورة"}
        FacebookAPI.send_text(user_id, parsed['content'], quick_replies=suggestions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT)
