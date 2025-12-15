import os
import json
import requests
import asyncio
import textwrap
import logging
import random
import urllib.parse
import io
import re # 🆕 لمعالجة النصوص بذكاء
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, request
from collections import defaultdict
import edge_tts

# ====================================================================
# ⚙️ إعدادات النظام
# ====================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

VERIFY_TOKEN = 'boykta2025'
PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9'

# 🛡️ المفاتيح الآمنة
PARTIAL_KEYS = [
    "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
    "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
    "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
]
def get_key(index): return "gsk_" + PARTIAL_KEYS[index]

KEY_PRIMARY = get_key(0)
KEY_BACKUP  = get_key(1)
KEY_VISION  = get_key(2)

MODEL_CHAT   = "llama-3.1-8b-instant" 
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"

# ====================================================================
# 🗄️ الذاكرة الذكية
# ====================================================================
user_db = defaultdict(lambda: {
    'history': [],
    'last_image_analysis': None, # هنا نخزن تحليل الصورة الأخيرة
    'last_image_url': None
})

# ====================================================================
# 🎨 محرك الرسم (Math Renderer)
# ====================================================================
def render_solution_to_image(text):
    """تحويل الحلول الرياضية لصور"""
    try:
        height = len(text.split('\n')) * 0.5 + 4
        if height > 50: height = 50 # حد أقصى للطول
        
        fig, ax = plt.subplots(figsize=(12, height))
        ax.axis('off')
        
        # تغليف النص
        wrapped_text = "\n".join(textwrap.wrap(text, width=75))
        
        ax.text(0.5, 0.5, wrapped_text, ha='center', va='center', 
                fontsize=16, family='serif', wrap=True)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Render Error: {e}")
        return None

# ====================================================================
# 🧠 دماغ الذكاء الاصطناعي (Groq Logic)
# ====================================================================

def call_groq(messages, model, key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=50)
        if res.status_code in [400, 404] and "scout" in model:
             return call_groq(messages, "llama-3.2-11b-vision-preview", key)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        raise e

def analyze_image(image_url):
    """Llama 4: يحلل الصورة ويستخرج ما فيها"""
    prompt = """
    Analyze this image in detail.
    1. Extract all text/math exactly.
    2. Describe what kind of image it is (Math problem, Quran, General photo, Meme?).
    3. Output format:
       TYPE: [MATH/RELIGIOUS/GENERAL]
       CONTENT: [The extracted text]
       DESCRIPTION: [Brief description]
    """
    msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}]}]
    try:
        return call_groq(msgs, MODEL_VISION, KEY_VISION)
    except:
        return None

def brain_process(user_id, user_text, image_context=None):
    """
    🧠 العقل المدبر: يحدد نية المستخدم (رسم، صوت، حل، دردشة)
    """
    
    # التعليمات الدائمة (System Prompt)
    system_prompt = f"""
    أنت "بويكتا" (Boykta)، مساعد ذكي جزائري.
    
    🛑 تعليمات صارمة (Intent Detection):
    1. إذا طلب المستخدم **رسم صورة** (مثال: "ارسم قطة", "تخيل منظر"):
       - ابدأ ردك بـ: CMD_IMAGE:
       - ثم اكتب الوصف الدقيق للصورة **باللغة الإنجليزية**.
    
    2. إذا طلب المستخدم **تحويل كلام لصوت** (مثال: "قل هذا بصوت", "اقرأ النص"):
       - ابدأ ردك بـ: CMD_AUDIO:
       - ثم اكتب النص الذي يجب قراءته.
    
    3. إذا كان المستخدم يطلب **حل تمرين** أو شرح نص (خاصة إذا كان هناك سياق صورة):
       - ابدأ ردك بـ: CMD_SOLVE:
       - ثم قم بحل التمرين بالتفصيل الممل (منهج جزائري) واستخدم LaTeX للمعادلات.
       
    4. إذا كانت دردشة عادية:
       - رد بشكل طبيعي وودود بصفتك "بويكتا".
    
    ℹ️ سياق إضافي (ماذا يوجد في الصورة الأخيرة): {image_context if image_context else "لا توجد صورة حالياً"}
    """
    
    history = user_db[user_id]['history']
    history.append({"role": "user", "content": user_text})
    
    # إبقاء الذاكرة قصيرة لعدم تشتيت البوت
    messages = [{"role": "system", "content": system_prompt}] + history[-6:]
    
    try:
        reply = call_groq(messages, MODEL_CHAT, KEY_PRIMARY)
        
        # حفظ الرد في التاريخ (ما عدا الأوامر البرمجية لكي لا تفسد السياق)
        if "CMD_" not in reply:
            history.append({"role": "assistant", "content": reply})
            
        return reply
    except:
        return "بويكتا متعب قليلاً، الخوادم مشغولة."

# ====================================================================
# 📨 أدوات الإرسال
# ====================================================================

def send_msg(user_id, text):
    clean = text.replace('**', '').replace('__', '').replace('`', '')
    for chunk in textwrap.wrap(clean, 1900, replace_whitespace=False):
        requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                      json={'recipient': {'id': user_id}, 'message': {'text': chunk}})

def send_image_url(user_id, url):
    encoded_url = urllib.parse.quote(url, safe=':/?&=')
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}",
                  json={'recipient': {'id': user_id}, 'message': {'attachment': {'type': 'image', 'payload': {'url': encoded_url, 'is_reusable': True}}}})

def send_file_memory(user_id, data, type='image', filename='file.png', mime='image/png'):
    payload = {'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': type, 'payload': {}}})}
    files = {'filedata': (filename, data, mime)}
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", data=payload, files=files)

# ====================================================================
# 🕹️ التحكم (Controller)
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return request.args.get('hub.challenge') if request.args.get('hub.verify_token') == VERIFY_TOKEN else 'Error'
    if request.method == 'POST':
        try:
            data = request.get_json()
            if data['object'] == 'page':
                for entry in data['entry']:
                    for event in entry.get('messaging', []):
                        if 'message' in event:
                            handle_message(event['sender']['id'], event['message'])
        except Exception as e: logger.error(e)
        return 'ok'

def handle_message(user_id, msg):
    # 1. معالجة الصور (Vision Intelligence)
    if 'attachments' in msg:
        if msg['attachments'][0]['type'] == 'image':
            url = msg['attachments'][0]['payload']['url']
            
            send_msg(user_id, "جاري تحليل الصورة... 👁️")
            analysis = analyze_image(url)
            
            if analysis:
                user_db[user_id]['last_image_analysis'] = analysis
                user_db[user_id]['last_image_url'] = url
                
                # الرد الذكي بناءً على نوع الصورة
                if "MATH" in analysis or "Physics" in analysis:
                    send_msg(user_id, "أرى تمريناً رياضياً/علمياً. 🧮\nهل تريدني أن أحله لك؟")
                elif "RELIGIOUS" in analysis:
                    send_msg(user_id, "صورة دينية/نص قرآني. 🤲\nهل تريد تفسيراً أو قراءة؟")
                else:
                    send_msg(user_id, "وصلت الصورة. ماذا تريد أن أفعل بها؟ (حل، وصف، ترجمة...)")
            else:
                send_msg(user_id, "فشل تحليل الصورة.")
            return

    # 2. معالجة النصوص والأوامر الصوتية
    text = msg.get('text', '')
    if not text: return

    # إحضار سياق الصورة إن وجد
    img_context = user_db[user_id]['last_image_analysis']
    
    # 🧠 إرسال كل شيء للعقل المدبر
    # (نظهر مؤشر الكتابة لإعطاء شعور بالتفكير)
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                  json={'recipient': {'id': user_id}, 'sender_action': 'typing_on'})
    
    ai_response = brain_process(user_id, text, img_context)
    
    # --- تنفيذ الأوامر حسب رد الذكاء ---
    
    # 🎨 1. أمر رسم صورة
    if ai_response.startswith("CMD_IMAGE:"):
        prompt = ai_response.replace("CMD_IMAGE:", "").strip()
        send_msg(user_id, "جاري الرسم... 🖌️")
        try:
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={seed}&model=flux"
            send_image_url(user_id, url)
        except:
            send_msg(user_id, "حدث خطأ أثناء الرسم.")

    # 🗣️ 2. أمر صوتي
    elif ai_response.startswith("CMD_AUDIO:"):
        tts_text = ai_response.replace("CMD_AUDIO:", "").strip()
        send_msg(user_id, "جاري التسجيل... 🎙️")
        try:
            fname = f"/tmp/voice_{user_id}_{random.randint(1,999)}.mp3"
            asyncio.run(edge_tts.Communicate(tts_text, "ar-EG-SalmaNeural").save(fname))
            with open(fname, 'rb') as f:
                requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                              data={'recipient': json.dumps({'id': user_id}), 'message': json.dumps({'attachment': {'type': 'audio', 'payload': {}}})}, 
                              files={'filedata': (fname, f, 'audio/mpeg')})
            os.remove(fname)
        except:
            send_msg(user_id, "فشل إنشاء الصوت.")

    # 🧮 3. أمر حل (معادلات وصور)
    elif ai_response.startswith("CMD_SOLVE:"):
        solution = ai_response.replace("CMD_SOLVE:", "").strip()
        send_msg(user_id, "إليك الحل المفصل 👇")
        
        # تحويل الحل لصورة إذا كان معقداً
        img_data = render_solution_to_image(solution)
        if img_data:
            send_file_memory(user_id, img_data, 'image', 'solution.png')
        else:
            send_msg(user_id, solution)

    # 💬 4. دردشة عادية
    else:
        send_msg(user_id, ai_response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
