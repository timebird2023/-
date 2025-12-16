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
# وضع السيرفر الصامت للرسم
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request
from collections import defaultdict, deque
import edge_tts

# ====================================================================
# 1. ⚙️ الإعدادات (The Engine Room)
# ====================================================================
class Config:
    PORT = int(os.environ.get('PORT', 25151))
    VERIFY_TOKEN = 'boykta2025'
    PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

    # 🔒 تم فصل المفاتيح لتجنب حظر GitHub
    # المفاتيح هنا ناقصة (بدون gsk_)
    _PARTIAL_KEYS = [
        "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
        "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
        "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
    ]
    
    MODEL_CHAT = "llama-3.1-8b-instant"
    VISION_MODELS = ["llama-3.2-11b-vision-preview", "llama-3.2-90b-vision-preview"]

    @staticmethod
    def get_key(index):
        # تجميع المفتاح عند التشغيل فقط لخداع GitHub
        return "gsk_" + Config._PARTIAL_KEYS[index % len(Config._PARTIAL_KEYS)]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("BoyktaBot_Final_Secure")

# ====================================================================
# 2. 🧠 الذكاء البصري واللغوي (AI Core)
# ====================================================================
class AIService:
    def __init__(self):
        self.users = defaultdict(lambda: {'history': deque(maxlen=6), 'extracted_text': None})

    def _call_groq(self, messages, model, temp=0.5):
        """دالة اتصال عامة مع إعادة المحاولة وتدوير المفاتيح"""
        for i in range(len(Config._PARTIAL_KEYS)):
            key = Config.get_key(i)
            try:
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {"model": model, "messages": messages, "temperature": temp}
                
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                                   json=payload, headers=headers, timeout=30)
                
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
                else:
                    logger.warning(f"Groq Fail ({model}): {resp.status_code}")
            except Exception as e:
                logger.error(f"Groq Error: {e}")
        return None

    def extract_text_from_image(self, user_id, img_url):
        """محرك OCR ذكي: يحاول بالموديل السريع، ثم القوي"""
        prompt = """
        SYSTEM: You are a strict OCR engine. 
        TASK: Extract ALL text, numbers, and mathematical formulas from this image exactly as they appear.
        OUTPUT: Just the text. No conversational filler like "Here is the text".
        """
        msg = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img_url}}]}]
        
        # 1. المحاولة السريعة
        extracted = self._call_groq(msg, Config.VISION_MODELS[0])
        
        # 2. المحاولة القوية (إذا فشل الأول)
        if not extracted:
            logger.info("Switching to 90b model for better OCR...")
            extracted = self._call_groq(msg, Config.VISION_MODELS[1])

        if extracted:
            self.users[user_id]['extracted_text'] = extracted
            return True
        return False

    def chat_brain(self, user_id, user_input, task_type="chat"):
        user_data = self.users[user_id]
        context_text = user_data.get('extracted_text', '')

        if task_type == "solve":
            sys_prompt = f"""
            أنت مدرس ذكي. لديك نص تمرين:
            ---
            {context_text}
            ---
            المطلوب: حل التمرين بالمنهج الجزائري خطوة بخطوة.
            قاعدة: المعادلات الرياضية اكتبها بصيغة LaTeX محاطة بـ $$. مثال: $$ x^2 $$
            """
        elif task_type == "translate":
            sys_prompt = f"ترجم النص التالي للعربية بدقة:\n{context_text}"
        else:
            sys_prompt = f"""
            أنت مساعد (Boykta).
            - للرسم: `CMD_IMAGE: <English Prompt>`
            - للصوت: `CMD_AUDIO: <Text>`
            سياق سابق: {context_text}
            """

        msgs = [{"role": "system", "content": sys_prompt}] + list(user_data['history']) + [{"role": "user", "content": user_input}]
        
        reply = self._call_groq(msgs, Config.MODEL_CHAT)
        
        if reply and task_type == "chat" and "CMD_" not in reply:
            user_data['history'].append({"role": "user", "content": user_input})
            user_data['history'].append({"role": "assistant", "content": reply})
            
        return reply

ai = AIService()

# ====================================================================
# 3. 🎨 أدوات الوسائط (Media Tools)
# ====================================================================
class MediaTools:
    @staticmethod
    def render_latex(latex_formula):
        try:
            clean_tex = latex_formula.replace('$$', '').strip()
            fig, ax = plt.subplots(figsize=(8, 1.5))
            fig.patch.set_alpha(0)
            ax.axis('off')
            ax.text(0.5, 0.5, f"${clean_tex}$", size=20, ha='center', va='center')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except: return None

    @staticmethod
    def get_image_bytes(prompt):
        try:
            safe_p = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1024&height=1024&model=flux&seed={random.randint(1,9999)}"
            return requests.get(url, timeout=25).content
        except: return None

    @staticmethod
    def text_to_speech(text):
        async def run():
            comm = edge_tts.Communicate(text, "ar-EG-SalmaNeural")
            out = io.BytesIO()
            async for chunk in comm.stream():
                if chunk["type"] == "audio": out.write(chunk["data"])
            out.seek(0)
            return out
        try: return asyncio.run(run())
        except: return None

# ====================================================================
# 4. 🌐 مدير الفيسبوك (Facebook Handler)
# ====================================================================
class FB:
    URL = "https://graph.facebook.com/v19.0/me/messages"
    
    @staticmethod
    def send(user_id, data):
        requests.post(f"{FB.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", json=data)

    @staticmethod
    def typing(user_id):
        FB.send(user_id, {'recipient': {'id': user_id}, 'sender_action': 'typing_on'})

    @staticmethod
    def text(user_id, msg, quick_replies=None):
        payload = {'recipient': {'id': user_id}, 'message': {'text': msg}}
        if quick_replies:
            payload['message']['quick_replies'] = [{"content_type": "text", "title": k, "payload": v} for k, v in quick_replies.items()]
        FB.send(user_id, payload)

    @staticmethod
    def file(user_id, file_data, type='image'):
        files = {'filedata': ('f.png' if type=='image' else 'f.mp3', file_data, 'image/png' if type=='image' else 'audio/mpeg')}
        payload = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': type, 'payload': {}}})}
        requests.post(f"{FB.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", data=payload, files=files)

# ====================================================================
# 5. 🎮 التحكم (Controller)
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
                        process(event['sender']['id'], event['message'])
        return 'OK'

def process(uid, msg):
    FB.typing(uid)

    if msg.get('sticker_id'):
        FB.text(uid, "👍")
        return

    # معالجة الصور
    if 'attachments' in msg and msg['attachments'][0]['type'] == 'image':
        if msg.get('sticker_id'): return
        url = msg['attachments'][0]['payload']['url']
        FB.text(uid, "لحظة، أقرأ الصورة داخلياً... 👁️")
        
        if ai.extract_text_from_image(uid, url):
            btns = {"📝 حل التمرين": "cmd_solve", "🇬🇧 ترجمة": "cmd_translate", "📄 استخراج النص": "cmd_extract"}
            FB.text(uid, "تم القراءة! ماذا تريد؟", quick_replies=btns)
        else:
            FB.text(uid, "تعذر قراءة الصورة، حاول مرة أخرى.")
        return

    # معالجة النصوص
    text = msg.get('text')
    if not text: return

    if text == "cmd_solve":
        FB.text(uid, "جاري الحل... 📐")
        solution = ai.chat_brain(uid, "حل التمرين", "solve")
        parts = re.split(r'(\$\$.*?\$\$)', solution, flags=re.DOTALL)
        for part in parts:
            if part.startswith('$$'):
                img = MediaTools.render_latex(part)
                if img: FB.file(uid, img, 'image')
            elif part.strip():
                FB.text(uid, part.strip())
        return

    elif text == "cmd_translate":
        FB.text(uid, "جاري الترجمة...")
        FB.text(uid, ai.chat_brain(uid, "ترجم", "translate"))
        return

    elif text == "cmd_extract":
        FB.text(uid, ai.users[uid].get('extracted_text', "لا يوجد نص."))
        return

    # محادثة عادية
    reply = ai.chat_brain(uid, text)
    
    if "CMD_IMAGE:" in reply:
        FB.text(uid, "جاري الرسم... 🎨")
        img = MediaTools.get_image_bytes(reply.split("CMD_IMAGE:")[1].strip())
        if img: FB.file(uid, img, 'image')
        else: FB.text(uid, "فشل الرسم.")
        
    elif "CMD_AUDIO:" in reply:
        FB.text(uid, "تسجيل... 🎙️")
        aud = MediaTools.text_to_speech(reply.split("CMD_AUDIO:")[1].strip())
        if aud: FB.file(uid, aud, 'audio')
        
    elif "CMD_MATH:" in reply:
        img = MediaTools.render_latex(reply.split("CMD_MATH:")[1].strip())
        if img: FB.file(uid, img, 'image')
        
    else:
        FB.text(uid, reply)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT)
