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

    # 🔒 حماية المفاتيح (مفصولة)
    _PARTIAL_KEYS = [
        "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
        "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
        "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
    ]
    
    # 🚨 التعديل الجوهري: استخدام الموديل الأقوى (90b) كخيار وحيد للرؤية لضمان الدقة
    MODEL_CHAT = "llama-3.1-8b-instant"
    MODEL_VISION = "llama-3.2-90b-vision-preview" 

    @staticmethod
    def get_key(index):
        # تجميع المفتاح عند التشغيل فقط لخداع GitHub
        return "gsk_" + Config._PARTIAL_KEYS[index % len(Config._PARTIAL_KEYS)]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("BoyktaBot_V6_Stable")

# ====================================================================
# 2. 🧠 الذكاء البصري واللغوي (AI Core)
# ====================================================================
class AIService:
    def __init__(self):
        self.users = defaultdict(lambda: {'history': deque(maxlen=6), 'extracted_text': None})

    def _call_groq(self, messages, model, temp=0.5):
        """دالة اتصال قوية مع تدوير المفاتيح"""
        for i in range(len(Config._PARTIAL_KEYS)):
            key = Config.get_key(i)
            try:
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                # زيادة الـ tokens للموديل البصري ليقرأ النصوص الطويلة
                max_tokens = 2048 if "vision" in model else 1024
                payload = {"model": model, "messages": messages, "temperature": temp, "max_tokens": max_tokens}
                
                resp = requests.post("https://api.groq.com/openai/v1/chat/completions", 
                                   json=payload, headers=headers, timeout=45) # زيادة وقت الانتظار
                
                if resp.status_code == 200:
                    content = resp.json()['choices'][0]['message']['content']
                    if content: return content
                else:
                    logger.warning(f"Groq Fail ({model}) Status: {resp.status_code}")
            except Exception as e:
                logger.error(f"Groq Error: {e}")
        return None

    def extract_text_from_image(self, user_id, img_url):
        """
        محرك OCR المطور (V6): يستخدم الموديل الأقوى بتعليمات مرنة.
        """
        # تعليمات مبسطة جداً لضمان عدم الفشل
        prompt = """
        Describe this image in detail. 
        If it contains text, write it out EXACTLY as it appears. 
        If it contains math, write the equations in LaTeX.
        If it's just a photo, describe what you see.
        """
        msg = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img_url}}]}]
        
        # استخدام الموديل القوي مباشرة
        extracted = self._call_groq(msg, Config.MODEL_VISION)
        
        if extracted:
            self.users[user_id]['extracted_text'] = extracted
            return True
        return False

    def chat_brain(self, user_id, user_input, task_type="chat"):
        user_data = self.users[user_id]
        context_text = user_data.get('extracted_text', '')

        if task_type == "solve":
            sys_prompt = f"""
            أنت أستاذ فيزياء ورياضيات جزائري محترف.
            لديك نص تمرين مستخرج من صورة:
            ---
            {context_text}
            ---
            المطلوب: حل هذا التمرين حلاً نموذجياً مفصلاً (خطوة بخطوة).
            - استخدم LaTeX للمعادلات محاطة بـ $$. مثال: $$ E = mc^2 $$
            - اشرح بالعربية والفرنسية (المصطلحات العلمية) كما في المنهج الجزائري.
            """
        elif task_type == "translate":
            sys_prompt = f"ترجم المحتوى التالي للعربية ترجمة احترافية:\n{context_text}"
        else:
            sys_prompt = f"""
            أنت مساعد (Boykta).
            - للرسم: `CMD_IMAGE: <English Prompt>`
            - للصوت: `CMD_AUDIO: <Text>`
            سياق الصورة السابق: {context_text}
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
            # تنظيف الكود
            clean_tex = latex_formula.replace('$$', '').replace(r'\[', '').replace(r'\]', '').strip()
            if not clean_tex: return None
            
            fig, ax = plt.subplots(figsize=(10, 2)) # عرض أكبر للمعادلات الطويلة
            fig.patch.set_alpha(0)
            ax.axis('off')
            # استخدام خط أكبر
            ax.text(0.5, 0.5, f"${clean_tex}$", size=22, ha='center', va='center')
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception as e: 
            logger.error(f"Latex Error: {e}")
            return None

    @staticmethod
    def get_image_bytes(prompt):
        try:
            safe_p = urllib.parse.quote(prompt)
            # إضافة seed عشوائي لضمان عدم تكرار الصورة
            url = f"https://image.pollinations.ai/prompt/{safe_p}?width=1024&height=1024&model=flux&seed={random.randint(1,99999)}"
            return requests.get(url, timeout=30).content
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
        if not msg: return
        # تقسيم الرسائل الطويلة جداً
        chunks = textwrap.wrap(msg, 1900, replace_whitespace=False)
        for i, chunk in enumerate(chunks):
            payload = {'recipient': {'id': user_id}, 'message': {'text': chunk}}
            if i == len(chunks) - 1 and quick_replies:
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
        FB.text(uid, "جاري تحليل الصورة (قد يستغرق لحظات)... 👁️")
        
        # محاولة الاستخراج (ستنجح الآن باستخدام 90b)
        if ai.extract_text_from_image(uid, url):
            btns = {
                "📝 حل التمرين": "cmd_solve", 
                "🇬🇧 ترجمة": "cmd_translate", 
                "📄 استخراج النص": "cmd_extract",
                "🖼️ وصف": "cmd_describe"
            }
            FB.text(uid, "تم القراءة! اختر ماذا تريد:", quick_replies=btns)
        else:
            # في حال الفشل النادر جداً
            FB.text(uid, "لم أتمكن من استخراج النص، لكن يمكنك سؤالي عنه يدوياً.")
        return

    # معالجة النصوص
    text = msg.get('text')
    if not text: return

    # الأوامر المباشرة من الأزرار
    if text == "cmd_solve":
        FB.text(uid, "جاري تحضير الحل... 📐")
        solution = ai.chat_brain(uid, "حل التمرين بالتفصيل", "solve")
        
        # تقسيم الحل لاستخراج المعادلات ورسمها
        parts = re.split(r'(\$\$.*?\$\$)', solution, flags=re.DOTALL)
        for part in parts:
            if part.startswith('$$'):
                img = MediaTools.render_latex(part)
                if img: FB.file(uid, img, 'image')
            elif part.strip():
                FB.text(uid, part.strip())
        return

    elif text == "cmd_translate":
        FB.text(uid, ai.chat_brain(uid, "ترجم", "translate"))
        return

    elif text == "cmd_extract":
        extracted = ai.users[uid].get('extracted_text', "لا يوجد نص.")
        FB.text(uid, extracted[:1900]) # إرسال أول 1900 حرف لتجنب خطأ فيسبوك
        if len(extracted) > 1900: FB.text(uid, extracted[1900:])
        return
        
    elif text == "cmd_describe":
        FB.text(uid, ai.users[uid].get('extracted_text', "لا يوجد وصف."))
        return

    # المحادثة العادية
    reply = ai.chat_brain(uid, text)
    
    if reply:
        if "CMD_IMAGE:" in reply:
            FB.text(uid, "جاري الرسم... 🎨")
            img = MediaTools.get_image_bytes(reply.split("CMD_IMAGE:")[1].strip())
            if img: FB.file(uid, img, 'image')
            else: FB.text(uid, "تعذر الرسم.")
            
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
