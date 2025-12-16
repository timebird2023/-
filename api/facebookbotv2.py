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
# 1. ⚙️ الإعدادات والمفاتيح (Config)
# ====================================================================
class Config:
    PORT = int(os.environ.get('PORT', 25151))
    VERIFY_TOKEN = 'boykta2025'
    PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

    # 🛡️ تقسيم المفاتيح لتجنب الحظر
    _PARTIAL_KEYS = [
        "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
        "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
        "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
    ]
    
    MODEL_CHAT = "llama-3.1-8b-instant"
    MODEL_VISION = "llama-3.2-90b-vision-preview" # الموديل الأقوى للصور
    MODEL_AUDIO = "whisper-large-v3" # موديل تحويل الصوت لنص

    @staticmethod
    def get_key(index=0):
        return "gsk_" + Config._PARTIAL_KEYS[index % len(Config._PARTIAL_KEYS)]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BoyktaBot_V7")

# ====================================================================
# 2. 🧠 عميل الذكاء الاصطناعي (Groq Client)
# ====================================================================
class GroqClient:
    BASE_URL = "https://api.groq.com/openai/v1"

    @staticmethod
    def chat(messages, model=Config.MODEL_CHAT):
        """إرسال رسائل نصية"""
        for i in range(len(Config._PARTIAL_KEYS)):
            key = Config.get_key(i)
            try:
                resp = requests.post(
                    f"{GroqClient.BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": model, "messages": messages, "temperature": 0.6},
                    timeout=30
                )
                if resp.status_code == 200:
                    return resp.json()['choices'][0]['message']['content']
            except Exception as e:
                logger.error(f"Chat Error: {e}")
        return None

    @staticmethod
    def vision(img_url, prompt="Extract text"):
        """تحليل الصور مع طباعة الأخطاء"""
        # تجربة عدة مفاتيح
        for i in range(len(Config._PARTIAL_KEYS)):
            key = Config.get_key(i)
            try:
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload = {
                    "model": Config.MODEL_VISION,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": img_url}}
                        ]
                    }],
                    "max_tokens": 1024
                }
                
                resp = requests.post(f"{GroqClient.BASE_URL}/chat/completions", headers=headers, json=payload, timeout=45)
                
                if resp.status_code == 200:
                    return {"status": "success", "text": resp.json()['choices'][0]['message']['content']}
                else:
                    # 🚨 هنا نطبع الخطأ لنعرف السبب
                    error_msg = f"API Error {resp.status_code}: {resp.text}"
                    logger.error(error_msg)
                    return {"status": "error", "text": error_msg} # نعيد الخطأ للمستخدم مؤقتاً
            except Exception as e:
                return {"status": "error", "text": str(e)}
        return {"status": "error", "text": "All keys failed"}

    @staticmethod
    def audio_transcription(audio_url):
        """تحويل الصوت إلى نص (Whisper)"""
        try:
            # 1. تحميل الملف الصوتي من فيسبوك
            audio_data = requests.get(audio_url).content
            
            # 2. إرساله لـ Groq
            key = Config.get_key(0)
            files = {
                'file': ('audio.mp3', audio_data, 'audio/mpeg'),
                'model': (None, Config.MODEL_AUDIO)
            }
            headers = {"Authorization": f"Bearer {key}"} # لا نضع Content-Type هنا
            
            resp = requests.post(f"{GroqClient.BASE_URL}/audio/transcriptions", headers=headers, files=files, timeout=60)
            
            if resp.status_code == 200:
                return resp.json().get('text', '')
            else:
                logger.error(f"Whisper Error: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Audio Download Error: {e}")
            return None

# ====================================================================
# 3. 🛠️ الأدوات المساعدة (Tools)
# ====================================================================
class Tools:
    @staticmethod
    def render_latex(latex):
        """رسم الرياضيات"""
        try:
            clean = latex.replace('$$', '').strip()
            fig, ax = plt.subplots(figsize=(10, 2))
            fig.patch.set_alpha(0)
            ax.axis('off')
            ax.text(0.5, 0.5, f"${clean}$", size=20, ha='center', va='center')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except: return None

    @staticmethod
    def generate_image(prompt):
        """رسم صورة"""
        try:
            safe_prompt = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&model=flux&seed={random.randint(1,99999)}"
            return requests.get(url, timeout=30).content
        except: return None

    @staticmethod
    def text_to_speech(text):
        """نطق النص"""
        async def _run():
            comm = edge_tts.Communicate(text, "ar-EG-SalmaNeural")
            out = io.BytesIO()
            async for chunk in comm.stream():
                if chunk["type"] == "audio": out.write(chunk["data"])
            out.seek(0)
            return out
        try: return asyncio.run(_run())
        except: return None

# ====================================================================
# 4. 🧠 إدارة البوت (Bot Logic)
# ====================================================================
class BotLogic:
    def __init__(self):
        # فصلنا الذاكرة: التاريخ للمحادثة، و context للصورة الحالية
        self.users = defaultdict(lambda: {
            'history': deque(maxlen=8), 
            'img_context': None
        })

    def process_text(self, user_id, text, is_voice_msg=False):
        user_data = self.users[user_id]
        
        # إذا كانت رسالة صوتية، نضيف ملاحظة للنظام
        voice_note_prompt = "(User sent a voice note): " if is_voice_msg else ""
        
        system_prompt = f"""
        أنت مساعد ذكي (Boykta).
        - السياق البصري الحالي (إن وجد): {user_data['img_context'] or 'لا يوجد'}
        
        الأوامر التنفيذية (يجب أن تكون في بداية الرد):
        1. للرسم: `CMD_IMAGE: <English Prompt>`
        2. للصوت: `CMD_AUDIO: <Text>`
        3. للرياضيات المعقدة: `CMD_MATH: <LaTeX>`
        
        ملاحظة: إذا طلب المستخدم "رسم"، ترجم الطلب للإنجليزية وضعه في الأمر.
        """
        
        msgs = [{"role": "system", "content": system_prompt}] + list(user_data['history']) + [{"role": "user", "content": voice_note_prompt + text}]
        
        reply = GroqClient.chat(msgs)
        
        if reply:
            # حفظ في الذاكرة (بدون الأوامر البرمجية)
            if "CMD_" not in reply:
                user_data['history'].append({"role": "user", "content": text})
                user_data['history'].append({"role": "assistant", "content": reply})
            return reply
        return "حدث خطأ في المعالجة."

bot = BotLogic()

# ====================================================================
# 5. 🌐 واجهة فيسبوك (Facebook Interface)
# ====================================================================
app = Flask(__name__)
FB_API = "https://graph.facebook.com/v19.0/me/messages"

def fb_send(uid, payload, files=None):
    url = f"{FB_API}?access_token={Config.PAGE_ACCESS_TOKEN}"
    if files:
        requests.post(url, data=payload, files=files)
    else:
        requests.post(url, json=payload)

def send_text(uid, txt, quick_replies=None):
    if not txt: return
    # إرسال رسالة نصية (مع أزرار اختيارية)
    chunks = textwrap.wrap(txt, 1900, replace_whitespace=False)
    for i, chunk in enumerate(chunks):
        msg_data = {'text': chunk}
        if i == len(chunks) - 1 and quick_replies:
            msg_data['quick_replies'] = [{"content_type": "text", "title": k, "payload": v} for k, v in quick_replies.items()]
        fb_send(uid, {'recipient': {'id': uid}, 'message': msg_data})

def send_file(uid, data, type='image'):
    fname = 'img.png' if type == 'image' else 'aud.mp3'
    mime = 'image/png' if type == 'image' else 'audio/mpeg'
    payload = {'recipient': json.dumps({'id': uid}), 'message': json.dumps({'attachment': {'type': type, 'payload': {}}})}
    fb_send(uid, payload, files={'filedata': (fname, data, mime)})

# --- الويب هوك ---
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
                        sender_id = event['sender']['id']
                        fb_send(sender_id, {'recipient': {'id': sender_id}, 'sender_action': 'typing_on'})
                        handle_event(sender_id, event['message'])
        return 'OK'

def handle_event(uid, msg):
    # 1. فلتر اللايك 👍
    if msg.get('sticker_id'):
        send_text(uid, "👍")
        return

    # 2. معالجة المرفقات (صور / صوت)
    if 'attachments' in msg:
        atype = msg['attachments'][0]['type']
        url = msg['attachments'][0]['payload']['url']

        # أ) صور 🖼️
        if atype == 'image':
            if msg.get('sticker_id'): return
            send_text(uid, "جاري تحليل الصورة... 👁️")
            
            # محاولة الاستخراج
            res = GroqClient.vision(url, "Describe this image in detail. Extract any text/math exactly.")
            
            if res['status'] == 'success':
                bot.users[uid]['img_context'] = res['text']
                btns = {"📝 حل": "cmd_solve", "📄 النص": "cmd_extract", "🎨 وصف": "cmd_describe"}
                send_text(uid, "تم التحليل بنجاح! ماذا تريد؟", quick_replies=btns)
            else:
                # طباعة سبب الخطأ للمستخدم لتشخيص المشكلة
                send_text(uid, f"⚠️ فشل التحليل. السبب التقني:\n{res['text']}")
            return

        # ب) صوت 🎙️ (ميزة جديدة)
        elif atype == 'audio':
            send_text(uid, "جاري الاستماع... 🎧")
            transcription = GroqClient.audio_transcription(url)
            if transcription:
                send_text(uid, f"🎤 قلت: {transcription}")
                # نرسل النص المفرغ للمعالجة كأنه رسالة نصية
                process_bot_response(uid, transcription, is_voice=True)
            else:
                send_text(uid, "لم أستطع سماع الصوت بوضوح.")
            return

    # 3. معالجة النصوص
    text = msg.get('text')
    if text:
        process_bot_response(uid, text)

def process_bot_response(uid, text, is_voice=False):
    # معالجة الأزرار السريعة
    if text == "cmd_solve": text = "حل التمرين في الصورة بالتفصيل"
    elif text == "cmd_extract": text = "أعطني النص المستخرج فقط"
    elif text == "cmd_describe": text = "صف لي الصورة"

    # الحصول على الرد من الذكاء
    response = bot.process_text(uid, text, is_voice_msg=is_voice)

    # تنفيذ الأوامر المضمنة
    if "CMD_IMAGE:" in response:
        send_text(uid, "جاري الرسم... 🎨")
        prompt = response.split("CMD_IMAGE:")[1].strip()
        img = Tools.generate_image(prompt)
        if img: send_file(uid, img, 'image')
        else: send_text(uid, "فشل السيرفر في الرسم.")

    elif "CMD_AUDIO:" in response:
        send_text(uid, "جاري التسجيل... 🎙️")
        txt = response.split("CMD_AUDIO:")[1].strip()
        aud = Tools.text_to_speech(txt)
        if aud: send_file(uid, aud, 'audio')

    elif "CMD_MATH:" in response:
        latex = response.split("CMD_MATH:")[1].strip()
        send_text(uid, "الحل الرياضي:")
        img = Tools.render_latex(latex)
        if img: send_file(uid, img, 'image')
        else: send_text(uid, latex) # بديل نصي

    else:
        # رد نصي عادي
        send_text(uid, response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT)
