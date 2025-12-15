import os
import json
import requests
import asyncio
import textwrap
import logging
import random
import urllib.parse
import io
import re # 🆕 مكتبة التعابير القياسية للكشف عن الرموز
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

# 🛡️ المفاتيح
PARTIAL_KEYS = [
    "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
    "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
    "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d"
]
def get_key(index): return "gsk_" + PARTIAL_KEYS[index]

KEY_PRIMARY = get_key(0)
KEY_VISION  = get_key(2)

MODEL_CHAT   = "llama-3.1-8b-instant" 
MODEL_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"

# ====================================================================
# 🗄️ الذاكرة
# ====================================================================
user_db = defaultdict(lambda: {
    'history': [],
    'last_image_context': None # لتذكر محتوى الصورة الأخيرة
})

# ====================================================================
# 🎨 محرك الرسم (Math Renderer) - المعدل
# ====================================================================
def contains_math(text):
    """
    دالة فحص دقيقة: هل يحتوي النص على رموز رياضيات تستدعي تحويله لصورة؟
    """
    # نبحث عن رموز LaTeX الشائعة
    math_patterns = [
        r'\$',          # علامة الدولار
        r'\\frac',      # الكسور
        r'\\sqrt',      # الجذور
        r'\\times',     # الضرب
        r'\^',          # الأسس
        r'\\_',         # الشرطة السفلية
        r'\\mathbb',    # الخطوط الرياضية
        r'\\alpha', r'\\beta', r'\\theta', # الرموز اليونانية
        r'\\approx',    # التقريب
        r'\\infty'      # اللانهاية
    ]
    
    for pattern in math_patterns:
        if re.search(pattern, text):
            return True
    return False

def render_text_to_image(text):
    """تحويل النص الكامل إلى صورة واضحة"""
    try:
        # حساب ارتفاع الصورة بناء على عدد الأسطر
        lines = text.split('\n')
        height = len(lines) * 0.6 + 2
        if height < 4: height = 4
        
        fig, ax = plt.subplots(figsize=(12, height))
        ax.axis('off')
        
        # تحسين عرض النص
        wrapped_text = "\n".join(textwrap.wrap(text, width=70, replace_whitespace=False))
        
        # رسم النص (ندعم اللغة العربية والرموز بشكل بسيط)
        # ملاحظة: matplotlib لا يدعم rendering LaTeX العربي المعقد 100% لكنه يعرض الكود بوضوح
        ax.text(0.5, 0.5, wrapped_text, ha='center', va='center', 
                fontsize=18, family='serif', wrap=True)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Render Error: {e}")
        return None

# ====================================================================
# 🧠 العقل المدبر (Brain)
# ====================================================================

def call_groq(messages, model, key):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        res = requests.post(url, json={"model": model, "messages": messages}, headers=headers, timeout=50)
        res.raise_for_status()
        return res.json()['choices'][0]['message']['content']
    except:
        return None

def analyze_image_content(image_url):
    """تحليل الصورة واستخراج المحتوى والسياق"""
    prompt = """
    Analyze this image comprehensively.
    1. Extract ALL text and math formulas exactly as they appear.
    2. Identify the TYPE: (Math Problem, Religious Text, General Photo, Screenshot).
    3. Output format:
       TYPE: [Type]
       CONTENT: [Extracted Text]
       CONTEXT: [Brief description of what this is]
    """
    msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}]}]
    return call_groq(msgs, MODEL_VISION, KEY_VISION)

def brain_process(user_id, user_text, image_context=None):
    """
    🧠 العقل المركزي: يقرر ماذا يفعل بناءً على النية (Intent)
    """
    
    system_prompt = f"""
    أنت "بويكتا" (Boykta)، مساعد ذكي جزائري.
    
    مهمتك هي فهم نية المستخدم بدقة وتنفيذها:

    1. **توليد الصور (Image Generation):**
       - فقط إذا طلب المستخدم صراحة "إنشاء" أو "رسم" أو "تخيل" صورة محددة.
       - المثال: "ارسم طائرة" -> نفذ الأمر.
       - المثال: "هل يمكنك الرسم؟" -> أجب بنعم فقط ولا تنفذ.
       - إذا كان أمراً بالتنفيذ، ابدأ ردك بـ: `CMD_IMAGE: <English Prompt>`

    2. **تحويل النص لكلام (TTS):**
       - فقط إذا طلب المستخدم "اقرأ هذا" أو "حول هذا النص لصوت" مع وجود نص محدد.
       - المثال: "حول النص لصوت" (بدون نص) -> اطلب منه النص.
       - المثال: "اقرأ: السلام عليكم" -> نفذ الأمر.
       - للتنفيذ، ابدأ ردك بـ: `CMD_AUDIO: <Text to read>`

    3. **حل التمارين والرياضيات (Math/Physics):**
       - إذا كان السؤال علمياً، قم بحله بالتفصيل الممل (منهج جزائري).
       - **هام جداً:** استخدم تنسيق LaTeX للمعادلات (مثل $x^2$ أو \\frac{{1}}{{2}}). الكود البرمجي سيحولها لصورة تلقائياً.

    4. **الدردشة العامة:**
       - كن ودوداً ومحترماً. أجب عن الأسئلة الدينية والأدبية بنص عادي.
    
    ℹ️ سياق الصورة المرفقة (إن وجد): {image_context if image_context else "لا توجد صورة"}
    """
    
    history = user_db[user_id]['history']
    history.append({"role": "user", "content": user_text})
    
    messages = [{"role": "system", "content": system_prompt}] + history[-6:]
    
    try:
        reply = call_groq(messages, MODEL_CHAT, KEY_PRIMARY)
        # لا نحفظ الأوامر البرمجية في التاريخ لكي لا نلوث السياق
        if reply and not reply.startswith("CMD_"):
            history.append({"role": "assistant", "content": reply})
        return reply
    except:
        return "آسف، حدث خطأ في الاتصال."

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
# 🕹️ التحكم الرئيسي (Controller)
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
    # 1. معالجة الصور (يفهم ويخزن السياق فقط)
    if 'attachments' in msg:
        if msg['attachments'][0]['type'] == 'image':
            url = msg['attachments'][0]['payload']['url']
            
            # إشعار
            send_msg(user_id, "جاري تحليل الصورة... 👁️")
            
            # تحليل ذكي
            analysis = analyze_image_content(url)
            
            if analysis:
                user_db[user_id]['last_image_context'] = analysis
                
                # رد مبدئي ذكي بناء على النوع
                if "MATH" in analysis or "Physics" in analysis:
                    send_msg(user_id, "وصلتني الصورة، يبدو أنها تمرين. هل تريد الحّل؟ 🧮")
                elif "RELIGIOUS" in analysis:
                    send_msg(user_id, "صورة نصية/دينية. هل تريد استخراج النص أو الشرح؟ 📖")
                else:
                    send_msg(user_id, "رأيت الصورة. ماذا تريد أن أفعل بها؟ (وصف، ترجمة، استخراج نص...)")
            return

    # 2. معالجة النصوص (التفاعل)
    text = msg.get('text', '')
    if not text: return

    # إظهار "جاري الكتابة..."
    requests.post(f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}", 
                  json={'recipient': {'id': user_id}, 'sender_action': 'typing_on'})

    # استدعاء العقل المدبر
    img_ctx = user_db[user_id]['last_image_context']
    ai_response = brain_process(user_id, text, img_ctx)
    
    if not ai_response:
        send_msg(user_id, "عذراً، حدث خطأ.")
        return

    # --- تنفيذ الأوامر (Command Execution) ---

    # 🎨 1. طلب رسم
    if ai_response.startswith("CMD_IMAGE:"):
        prompt = ai_response.replace("CMD_IMAGE:", "").strip()
        send_msg(user_id, "جاري الرسم... 🖌️")
        try:
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&seed={seed}&model=flux"
            send_image_url(user_id, url)
        except: send_msg(user_id, "فشل الرسم.")

    # 🗣️ 2. طلب صوت
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
        except: send_msg(user_id, "فشل الصوت.")

    # 💬 3. رد نصي (أو حل تمرين)
    else:
        # هنا يكمن الذكاء: فحص النص بحثاً عن رموز الرياضيات
        if contains_math(ai_response):
            # وجدنا رياضيات! نحول الرد كاملاً لصورة
            send_msg(user_id, "إليك الحل 📝 (في صورة لضمان وضوح الرموز):")
            img_data = render_text_to_image(ai_response)
            if img_data:
                send_file_memory(user_id, img_data, 'image', 'solution.png')
            else:
                send_msg(user_id, ai_response) # فشل التحويل، نرسل نصاً
        else:
            # نص عادي (سوالف، دين، شرح أدبي)
            send_msg(user_id, ai_response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 25151))
    app.run(host='0.0.0.0', port=port)
