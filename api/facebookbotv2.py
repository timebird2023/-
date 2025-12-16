import os
import json
import requests
import asyncio
import textwrap
import logging
import random
import urllib.parse
import io
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
    
    # ✅ التحديث الجديد: استخدام نموذج Llama 4 Scout
    MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"
    
    MODEL_AUDIO = "whisper-large-v3"
    TTS_VOICE = "ar-EG-ShakirNeural" 

    @staticmethod
    def get_key(index=0):
        return "gsk_" + Config._PARTIAL_KEYS[index % len(Config._PARTIAL_KEYS)]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BoyktaBot_V9_Scout")

# ====================================================================
# 2. 🧠 عميل الذكاء الاصطناعي (Groq Client)
# ====================================================================
class GroqClient:
    BASE_URL = "https://api.groq.com/openai/v1"

    @staticmethod
    def chat(messages, model=Config.MODEL_CHAT):
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
                logger.error(f"Chat Error {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Chat Ex: {e}")
        return None

    @staticmethod
    def vision(img_url, prompt="Analyze this image"):
        """تحليل الصورة باستخدام Llama 4 Scout"""
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
                    # طباعة الخطأ بوضوح إذا فشل النموذج الجديد أيضاً
                    error_msg = f"Vision Error ({Config.MODEL_VISION}): {resp.status_code} - {resp.text}"
                    logger.error(error_msg)
                    return {"status": "error", "text": error_msg}
            except Exception as e:
                return {"status": "error", "text": str(e)}
        return {"status": "error", "text": "All keys failed"}

    @staticmethod
    def audio_transcription(audio_url):
        try:
            audio_data = requests.get(audio_url).content
            key = Config.get_key(0)
            files = {
                'file': ('audio.mp3', audio_data, 'audio/mpeg'),
                'model': (None, Config.MODEL_AUDIO)
            }
            headers = {"Authorization": f"Bearer {key}"}
            resp = requests.post(f"{GroqClient.BASE_URL}/audio/transcriptions", headers=headers, files=files, timeout=60)
            if resp.status_code == 200:
                return resp.json().get('text', '')
            return None
        except:
            return None

# ====================================================================
# 3. 🛠️ الأدوات (Tools)
# ====================================================================
class Tools:
    @staticmethod
    def render_latex(latex):
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
        try:
            safe_prompt = urllib.parse.quote(prompt)
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&model=flux&seed={random.randint(1,99999)}"
            return requests.get(url, timeout=30).content
        except: return None

    @staticmethod
    def text_to_speech(text):
        async def _run():
            comm = edge_tts.Communicate(text, Config.TTS_VOICE)
            out = io.BytesIO()
            async for chunk in comm.stream():
                if chunk["type"] == "audio": out.write(chunk["data"])
            out.seek(0)
            return out
        try: return asyncio.run(_run())
        except: return None

# ====================================================================
# 4. 🧠 العقل المدبر (Smart Context Brain)
# ====================================================================
class BotLogic:
    def __init__(self):
        self.users = defaultdict(lambda: {
            'history': deque(maxlen=10),
            'img_context': None
        })

    def process_text(self, user_id, text, is_voice_msg=False):
        user_data = self.users[user_id]
        
        voice_hint = "[User sent a Voice Note]: " if is_voice_msg else ""
        
        # نظام التوجيه الذكي (Smart Prompting)
        system_prompt = f"""
        أنت (Boykta)، مساعد ذكي جزائري.
        
        تعليمات السياق:
        1. **الصور:** إذا طلب المستخدم الرسم دون وصف، اسأله "ماذا أرسم؟". عند توفر الوصف، استخدم `CMD_IMAGE: <English Description>`.
        2. **الصوت:** إذا طلب القراءة دون نص، اسأله عن النص. عند توفر النص، استخدم `CMD_AUDIO: <Text>`.
        3. **الرياضيات:** للمعادلات استخدم `CMD_MATH: <LaTeX>`.

        سياق الصورة الحالية: {user_data['img_context'] or 'لا يوجد'}
        """
        
        msgs = [{"role": "system", "content": system_prompt}] + list(user_data['history']) + [{"role": "user", "content": voice_hint + text}]
        
        reply = GroqClient.chat(msgs)
        
        if reply:
            if "CMD_" not in reply:
                user_data['history'].append({"role": "user", "content": text})
                user_data['history'].append({"role": "assistant", "content": reply})
            else:
                # حفظ طلب المستخدم فقط للحفاظ على السياق
                user_data['history'].append({"role": "user", "content": text})
            return reply
        return "حدث خطأ في الاتصال."

bot = BotLogic()

# ====================================================================
# 5. 🌐 خادم فيسبوك (Facebook Server)
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
    # اللايك
    if msg.get('sticker_id'):
        send_text(uid, "👍")
        return

    # المرفقات
    if 'attachments' in msg:
        atype = msg['attachments'][0]['type']
        url = msg['attachments'][0]['payload']['url']

        # 1. صور
        if atype == 'image':
            if msg.get('sticker_id'): return
            send_text(uid, "جاري قراءة الصورة... 👁️")
            
            # استخدام Llama 4 Scout
            res = GroqClient.vision(url, "Extract ALL text from this image accurately. If math, write LaTeX. If general, describe it.")
            
            if res['status'] == 'success':
                bot.users[uid]['img_context'] = res['text']
                btns = {"📝 حل": "حل هذا", "📄 استخراج": "استخرج النص", "🎨 وصف": "صف الصورة"}
                send_text(uid, "تم التحليل! ماذا أفعل؟", quick_replies=btns)
            else:
                send_text(uid, f"⚠️ خطأ: {res['text']}")
            return

        # 2. صوت
        elif atype == 'audio':
            send_text(uid, "أسمعك... 🎧")
            text_voice = GroqClient.audio_transcription(url)
            if text_voice:
                send_text(uid, f"🎤 {text_voice}")
                process_bot_response(uid, text_voice, is_voice=True)
            else:
                send_text(uid, "الصوت غير واضح.")
            return

    # نصوص
    text = msg.get('text')
    if text:
        process_bot_response(uid, text)

def process_bot_response(uid, text, is_voice=False):
    response = bot.process_text(uid, text, is_voice_msg=is_voice)

    if "CMD_IMAGE:" in response:
        prompt = response.split("CMD_IMAGE:")[1].strip()
        send_text(uid, f"جاري رسم: {prompt} 🎨")
        img = Tools.generate_image(prompt)
        if img: send_file(uid, img, 'image')
        else: send_text(uid, "فشل الرسم.")

    elif "CMD_AUDIO:" in response:
        txt = response.split("CMD_AUDIO:")[1].strip()
        send_text(uid, "جاري التحدث... 🗣️")
        aud = Tools.text_to_speech(txt)
        if aud: send_file(uid, aud, 'audio')
        else: send_text(uid, "فشل الصوت.")

    elif "CMD_MATH:" in response:
        latex = response.split("CMD_MATH:")[1].strip()
        img = Tools.render_latex(latex)
        if img: 
            send_text(uid, "الحل الرياضي:")
            send_file(uid, img, 'image')
        else: 
            send_text(uid, latex)

    else:
        send_text(uid, response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT)
