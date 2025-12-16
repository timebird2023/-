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
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request
from collections import defaultdict, deque
import edge_tts

# ====================================================================
# 1. ⚙️ الإعدادات (Config)
# ====================================================================
class Config:
    PORT = int(os.environ.get('PORT', 25151))
    VERIFY_TOKEN = 'boykta2025'
    PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

    _PARTIAL_KEYS = [
        "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
        "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
        "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
    ]
    
    MODEL_CHAT = "llama-3.1-8b-instant"
    # تغيير الموديل إلى 11b لسرعة واستقرار أكبر في قراءة النصوص
    MODEL_VISION = "llama-3.2-11b-vision-preview" 

    @staticmethod
    def get_api_key(index=0):
        return "gsk_" + Config._PARTIAL_KEYS[index % len(Config._PARTIAL_KEYS)]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("BoyktaBot_V4")

# ====================================================================
# 2. 🧹 المصحح (Content Parser)
# ====================================================================
class ContentParser:
    @staticmethod
    def parse(ai_response):
        if not ai_response: return {"type": "text", "content": "حدث خطأ بسيط، حاول مرة أخرى."}

        # استخراج أوامر الرسم
        img_match = re.search(r'CMD_IMAGE:\s*(.+)', ai_response, re.IGNORECASE)
        if img_match:
            return {"type": "command_image", "content": img_match.group(1).strip()}

        # استخراج أوامر الصوت
        audio_match = re.search(r'CMD_AUDIO:\s*(.+)', ai_response, re.IGNORECASE)
        if audio_match:
            return {"type": "command_audio", "content": audio_match.group(1).strip()}

        # استخراج الرياضيات
        if "CMD_MATH:" in ai_response:
            return {"type": "math_render", "content": ai_response.replace("CMD_MATH:", "").strip()}

        return {"type": "text", "content": ai_response.replace("CMD_IMAGE:", "").replace("CMD_AUDIO:", "").strip()}

# ====================================================================
# 3. 🎨 المحرك (Engine)
# ====================================================================
class MediaEngine:
    @staticmethod
    def download_image(prompt):
        """توليد الصورة وتحميلها"""
        try:
            # إضافة nologo و seed عشوائي لضمان تنوع الصور
            seed = random.randint(1, 1000000)
            safe_prompt = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&seed={seed}&model=flux&nologo=true"
            res = requests.get(url, timeout=20)
            if res.status_code == 200:
                return res.content
        except Exception as e:
            logger.error(f"Img Gen Error: {e}")
        return None

    @staticmethod
    def render_math(latex):
        """رسم الرياضيات"""
        try:
            fig, ax = plt.subplots(figsize=(10, 2.5)) # زيادة الارتفاع قليلاً
            ax.axis('off')
            clean_latex = f"${latex.replace('$', '')}$"
            ax.text(0.5, 0.5, clean_latex, ha='center', va='center', fontsize=18)
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except:
            return None

    @staticmethod
    def text_to_speech(text):
        """توليد الصوت"""
        async def _gen():
            communicate = edge_tts.Communicate(text, "ar-EG-SalmaNeural")
            out = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    out.write(chunk["data"])
            out.seek(0)
            return out
        try:
            return asyncio.run(_gen())
        except:
            return None

# ====================================================================
# 4. 🌐 فيسبوك (Facebook API)
# ====================================================================
class FacebookAPI:
    URL = "https://graph.facebook.com/v19.0/me/messages"
    
    @staticmethod
    def send_action(user_id, action='typing_on'):
        requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'sender_action': action})

    @staticmethod
    def send_text(user_id, text, quick_replies=None):
        if not text: return
        chunks = textwrap.wrap(text, 1900, replace_whitespace=False)
        for i, chunk in enumerate(chunks):
            payload = {'recipient': {'id': user_id}, 'message': {'text': chunk}}
            if i == len(chunks) - 1 and quick_replies:
                qr_list = [{"content_type": "text", "title": k, "payload": v} for k, v in quick_replies.items()]
                payload['message']['quick_replies'] = qr_list
            requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", json=payload)

    @staticmethod
    def send_file(user_id, data, type='image'):
        files = {'filedata': ('file.png' if type=='image' else 'audio.mp3', data, 'image/png' if type=='image' else 'audio/mpeg')}
        payload = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': type, 'payload': {}}})}
        requests.post(f"{FacebookAPI.URL}?access_token={Config.PAGE_ACCESS_TOKEN}", data=payload, files=files)

# ====================================================================
# 5. 🧠 العقل (Brain)
# ====================================================================
class Brain:
    def __init__(self):
        self.db = defaultdict(lambda: {'history': deque(maxlen=8), 'img_context': None})

    def ask_groq(self, messages, model):
        # محاولة تدوير المفاتيح 3 مرات عند الفشل
        for i in range(3):
            key = Config.get_api_key(i)
            try:
                res = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": model, "messages": messages, "temperature": 0.6},
                    timeout=25 # زيادة المهلة قليلاً
                )
                if res.status_code == 200:
                    return res.json()['choices'][0]['message']['content']
                logger.warning(f"Groq error {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"Connection Error: {e}")
        return None

    def analyze_image(self, user_id, img_url):
        # برومبت دقيق جداً لاستخراج المحتوى بدقة
        prompt = """
        ACT AS A VISION OCR ENGINE.
        1. Extract ALL text/numbers from the image exactly as shown.
        2. Identify the content type: "MATH", "TEXT", or "GENERAL".
        3. Do NOT solve the problem yet. Just extract text and describe.
        """
        msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img_url}}]}]
        
        # نستخدم الموديل 11b لأنه أسرع وأدق في الـ OCR المجاني
        analysis = self.ask_groq(msgs, Config.MODEL_VISION)
        
        if analysis:
            self.db[user_id]['img_context'] = analysis
            return "math" if "MATH" in analysis else "general"
        return None

    def chat(self, user_id, text):
        user_data = self.db[user_id]
        
        # ⚠️ هنا حل مشكلة الرسم: إجبار البوت على الترجمة للإنجليزية داخل الأمر
        system_prompt = f"""
        أنت "بويكتا"، مساعد ذكي جزائري.
        
        🚨 قواعد صارمة:
        1. **الرسم:** إذا طلب المستخدم رسم شيء، يجب أن تترجم وصفه للإنجليزية وتضعه في الأمر.
           مثال: المستخدم: "ارسم قطة حمراء" -> أنت ترد: `CMD_IMAGE: A red cat`
        
        2. **الرياضيات:** - إذا طلب الحل، قم بحل التمرين المخزن في السياق خطوة بخطوة (Step-by-step).
           - إذا كانت المعادلة معقدة، استخدم `CMD_MATH: x^2...`.
        
        3. **الصوت:** للقراءة، استخدم `CMD_AUDIO: النص`.
        
        سياق الصورة المخزنة: {user_data['img_context'] or "لا يوجد"}
        """
        
        msgs = [{"role": "system", "content": system_prompt}] + list(user_data['history']) + [{"role": "user", "content": text}]
        
        reply = self.ask_groq(msgs, Config.MODEL_CHAT)
        
        if reply and "CMD_" not in reply:
            user_data['history'].append({"role": "user", "content": text})
            user_data['history'].append({"role": "assistant", "content": reply})
            
        return reply

bot = Brain()

# ====================================================================
# 6. 🎮 التحكم (Controller)
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
                        process_msg(event['sender']['id'], event['message'])
        return 'OK'

def process_msg(user_id, msg):
    FacebookAPI.send_action(user_id, 'typing_on')

    # 1. اللايك 👍
    if msg.get('sticker_id'):
        FacebookAPI.send_text(user_id, "👍")
        return

    # 2. الصور 🖼️
    if 'attachments' in msg and msg['attachments'][0]['type'] == 'image':
        if msg.get('sticker_id'): # تجاهل الستيكرات الكبيرة
            return
            
        url = msg['attachments'][0]['payload']['url']
        FacebookAPI.send_text(user_id, "جاري قراءة الصورة... 👁️")
        
        type_detected = bot.analyze_image(user_id, url)
        
        if type_detected == "math":
            btns = {"📝 حل التمرين": "حل التمرين بالتفصيل", "📄 استخراج النص": "استخراج النص فقط"}
            FacebookAPI.send_text(user_id, "تم استلام التمرين! 📐\nهل تريد الحل أم النص فقط؟", quick_replies=btns)
        elif type_detected == "general":
            btns = {"🎨 وصف الصورة": "وصف الصورة", "🇬🇧 ترجمة": "ترجم المحتوى"}
            FacebookAPI.send_text(user_id, "صورة واضحة! ماذا أفعل بها؟", quick_replies=btns)
        else:
            # إذا فشل الموديل في المرة الأولى، نطلب من المستخدم إعادة الإرسال بلطف
            FacebookAPI.send_text(user_id, "عذراً، الصورة لم تكن واضحة تماماً، هل يمكن إعادة إرسالها؟")
        return

    # 3. النصوص 💬
    text = msg.get('text')
    if not text: return

    raw = bot.chat(user_id, text)
    parsed = ContentParser.parse(raw)

    if parsed['type'] == 'command_image':
        FacebookAPI.send_text(user_id, "جاري الرسم... (قد يستغرق ثواني) 🎨")
        img_data = MediaEngine.download_image(parsed['content'])
        if img_data:
            FacebookAPI.send_file(user_id, img_data, 'image')
        else:
            FacebookAPI.send_text(user_id, "عذراً، السيرفر مشغول حالياً.")

    elif parsed['type'] == 'command_audio':
        FacebookAPI.send_text(user_id, "جاري التسجيل... 🎙️")
        audio_data = MediaEngine.text_to_speech(parsed['content'])
        if audio_data:
            FacebookAPI.send_file(user_id, audio_data, 'audio')

    elif parsed['type'] == 'math_render':
        FacebookAPI.send_text(user_id, "الحل الرياضي:")
        img_data = MediaEngine.render_math(parsed['content'])
        if img_data:
            FacebookAPI.send_file(user_id, img_data, 'image')
        else:
            FacebookAPI.send_text(user_id, parsed['content'])

    else:
        FacebookAPI.send_text(user_id, parsed['content'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT)
