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
logger = logging.getLogger("BoyktaBot_Final")

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
        if not ai_response:
            return {"type": "text", "content": "عذراً، حدث خطأ في المعالجة."}

        # 1. فحص أوامر الرسم
        img_match = re.search(r'CMD_IMAGE:\s*(.+)', ai_response, re.IGNORECASE)
        if img_match:
            return {"type": "command_image", "content": img_match.group(1).strip()}

        # 2. فحص أوامر الصوت
        audio_match = re.search(r'CMD_AUDIO:\s*(.+)', ai_response, re.IGNORECASE)
        if audio_match:
            return {"type": "command_audio", "content": audio_match.group(1).strip()}

        # 3. فحص الرياضيات
        if "CMD_MATH:" in ai_response:
            math_content = ai_response.replace("CMD_MATH:", "").strip()
            return {"type": "math_render", "content": math_content}

        # 4. نص عادي
        clean_text = ai_response.replace("CMD_IMAGE:", "").replace("CMD_AUDIO:", "").replace("CMD_MATH:", "")
        return {"type": "text", "content": clean_text.strip()}

# ====================================================================
# 3. 🎨 محركات الوسائط (Media Engines)
# ====================================================================
class MediaEngine:
    @staticmethod
    def download_generated_image(prompt):
        """
        يقوم بتوليد الصورة وتحميلها كملف ثنائي (Binary) بدلاً من مجرد رابط
        """
        try:
            seed = random.randint(1, 999999)
            safe_prompt = urllib.parse.quote(prompt)
            # إضافة model=flux لجودة عالية
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
            
            # ننتظر التحميل (Timeout 20 ثانية)
            response = requests.get(url, timeout=25)
            if response.status_code == 200:
                return response.content # نرجع بيانات الصورة نفسها
            return None
        except Exception as e:
            logger.error(f"Image Gen Error: {e}")
            return None

    @staticmethod
    def render_math_to_image(latex_text):
        try:
            fig, ax = plt.subplots(figsize=(10, 2))
            ax.axis('off')
            # تنظيف النص
            clean_latex = f"${latex_text.replace('$', '')}$"
            ax.text(0.5, 0.5, clean_latex, ha='center', va='center', fontsize=20, color='black')
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except:
            return None

    @staticmethod
    def generate_voice(text):
        async def _run():
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
        chunks = textwrap.wrap(text, 1900, replace_whitespace=False)
        for i, chunk in enumerate(chunks):
            payload = {'recipient': {'id': user_id}, 'message': {'text': chunk}}
            if i == len(chunks) - 1 and quick_replies:
                qr_list = []
                for title, data in quick_replies.items():
                    qr_list.append({"content_type": "text", "title": title, "payload": data})
                payload['message']['quick_replies'] = qr_list
            requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", json=payload)

    @staticmethod
    def send_file(user_id, file_data, type='image'):
        """إرسال ملف (يقبل Binary Data)"""
        filename = 'image.png' if type == 'image' else 'audio.mp3'
        mime = 'image/png' if type == 'image' else 'audio/mpeg'
        
        files = {
            'filedata': (filename, file_data, mime)
        }
        payload = {
            'recipient': json.dumps({'id': user_id}), 
            'message': json.dumps({'attachment': {'type': type, 'payload': {}}})
        }
        requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", data=payload, files=files)

# ====================================================================
# 5. 🧠 العقل المركزي (The Brain)
# ====================================================================
class BotBrain:
    def __init__(self):
        self.db = defaultdict(lambda: {'history': deque(maxlen=6), 'img_ctx': None})

    def ask_ai(self, messages, model):
        for attempt in range(3):
            key = Config.get_api_key(attempt)
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": model, "messages": messages},
                    timeout=30
                )
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
            except:
                pass
        return None

    def process_image(self, user_id, img_url):
        prompt = "Analyze this image. If math, solve it. If text, extract it. If general, describe it. Return concise summary."
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img_url}}]}]
        analysis = self.ask_ai(msgs, Config.MODEL_VISION)
        if analysis:
            self.db[user_id]['img_ctx'] = analysis
            return analysis
        return None

    def chat(self, user_id, user_msg):
        user_data = self.db[user_id]
        system_instruction = f"""
        أنت مساعد ذكي.
        1. للرسم رد بـ: CMD_IMAGE: <English Prompt>
        2. للصوت رد بـ: CMD_AUDIO: <Text>
        3. للرياضيات المعقدة رد بـ: CMD_MATH: <Latex>
        4. غير ذلك: رد نصي مفيد ومختصر.
        سياق الصورة: {user_data['img_ctx'] or "لا يوجد"}
        """
        msgs = [{"role": "system", "content": system_instruction}] + list(user_data['history']) + [{"role": "user", "content": user_msg}]
        raw_reply = self.ask_ai(msgs, Config.MODEL_CHAT)
        
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
    FacebookAPI.send_typing(user_id)

    # فلتر اللايك 👍
    if msg.get('sticker_id'):
        FacebookAPI.send_text(user_id, "👍") 
        return

    # الصور المرفقة
    if 'attachments' in msg and msg['attachments'][0]['type'] == 'image':
        if msg.get('sticker_id'): 
            FacebookAPI.send_text(user_id, "❤️")
            return
        url = msg['attachments'][0]['payload']['url']
        FacebookAPI.send_text(user_id, "جاري تحليل الصورة... 🧐")
        analysis = bot.process_image(user_id, url)
        if analysis:
            FacebookAPI.send_text(user_id, "تم التحليل! ماذا تريد؟", quick_replies={"📝 حل/شرح": "اشرح لي", "🎨 وصف": "صف الصورة"})
        else:
            FacebookAPI.send_text(user_id, "لم أستطع قراءة الصورة.")
        return

    # النصوص
    text = msg.get('text')
    if not text: return

    raw_response = bot.chat(user_id, text)
    parsed = ContentParser.parse(raw_response)

    # 1. الرسم (تم الإصلاح هنا) 🎨
    if parsed['type'] == 'command_image':
        FacebookAPI.send_text(user_id, "جاري الرسم... 🎨")
        # التحميل أولاً
        img_data = MediaEngine.download_generated_image(parsed['content'])
        if img_data:
            FacebookAPI.send_file(user_id, img_data, 'image')
        else:
            FacebookAPI.send_text(user_id, "عذراً، السيرفر مشغول، حاول مرة أخرى.")

    # 2. الصوت 🎙️
    elif parsed['type'] == 'command_audio':
        FacebookAPI.send_text(user_id, "جاري التسجيل... 🎙️")
        audio_data = MediaEngine.generate_voice(parsed['content'])
        if audio_data:
            FacebookAPI.send_file(user_id, audio_data, 'audio')
        else:
            FacebookAPI.send_text(user_id, "فشل توليد الصوت.")

    # 3. الرياضيات 📐
    elif parsed['type'] == 'math_render':
        FacebookAPI.send_text(user_id, "الحل الرياضي:")
        img_data = MediaEngine.render_math_to_image(parsed['content'])
        if img_data:
            FacebookAPI.send_file(user_id, img_data, 'image')
        else:
            FacebookAPI.send_text(user_id, parsed['content'])

    # 4. نص عادي 💬
    else:
        suggestions = {"🗣️ اسمعها": "اقرأ النص", "🎨 تخيلها": "ارسم لي صورة"}
        FacebookAPI.send_text(user_id, parsed['content'], quick_replies=suggestions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT)
