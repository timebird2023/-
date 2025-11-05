import os
import json
import requests
import re
import time
from flask import Flask, request
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# ====================================================================
# 🔑 المتغيرات الأساسية والإعدادات
# ====================================================================

# ⚠️ التوكنات والرموز السرية (يجب تعيينها)
VERIFY_TOKEN = 'boykta2025'
PAGE_ACCESS_TOKEN = 'EAAYa4tM31ZAMBPZCOj8ZBQdn1kZBWkwIjJpYxodGAGHFGhos8ijFduQZAblZAMGNkGQZAQ5efK1bNsARqMHqWBlOvPmZC9pqsINZBRTP58jyclmqaaY3DuHxicesKMBChiDHYfXUNaF80iySjVxtkFntTUbGZANBC6eVGc2yeqeZAKlQwf2Dyj1ydSeM81EWlLcVfDGRvPD'

# معلومات المطور (لتضمينها في الردود)
DEVELOPER_NAME = "younes laldji"
DEVELOPER_FACEBOOK_URL = "https://www.facebook.com/2007younes"
AI_ASSISTANT_NAME = "بويكتا"

# واجهات الذكاء الاصطناعي (كما في ملف التليجرام)
GROK_API_URL = 'https://sii3.top/api/grok4.php'
NANO_BANANA_API = 'https://sii3.top/api/nano-banana.php'
SEARCH_API = 'https://sii3.top/api/s.php'
OCR_API = 'https://sii3.top/api/OCR.php'
DARKCODE_API = 'https://sii3.top/api/DarkCode.php'

# مجلد تخزين الملفات المؤقتة
TEMP_DIR = "fb_temp_storage"
os.makedirs(TEMP_DIR, exist_ok=True)

# الذاكرة المؤقتة لحالة المستخدم والسياق
# {sender_id: {'state': '...', 'temp_files': [], 'first_time': True, ...}}
user_state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {'state': None, 'temp_files': [], 'first_time': True})
in_memory_conversations: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

app = Flask(__name__)

# ====================================================================
# 🛠️ دوال المطور والأمان
# ====================================================================

def cleanup_temp_files(sender_id: str):
    """حذف جميع الملفات المؤقتة الخاصة بالمستخدم"""
    files_to_delete = user_state[sender_id]['temp_files']
    for file_path in files_to_delete:
        try:
            os.remove(file_path)
            print(f"🗑️ Deleted temp file: {file_path}")
        except:
            pass
    user_state[sender_id]['temp_files'] = []

def download_attachment(sender_id: str, attachment_url: str, file_extension: str = '.jpg') -> Optional[str]:
    """تحميل الملف المرفق وحفظه مؤقتاً"""
    try:
        # بناء مسار فريد للملف
        timestamp = int(time.time())
        file_path = os.path.join(TEMP_DIR, f"{sender_id}_{timestamp}{file_extension}")
        
        # التأكد من أن الرابط صالح (يمكن أن يكون Telegram file_path)
        if attachment_url.startswith('/'):
             full_url = f"https://api.telegram.org/file/bot{PAGE_ACCESS_TOKEN}{attachment_url}"
        else:
             full_url = attachment_url
        
        # محاولة التحميل
        response = requests.get(full_url, stream=True, timeout=30)
        
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            user_state[sender_id]['temp_files'].append(file_path)
            print(f"✅ File downloaded to: {file_path}")
            return file_path
        else:
            print(f"❌ Failed to download file. Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error during file download: {e}")
        return None

# ====================================================================
# 📡 دوال إرسال الرسائل والأزرار (Messenger API)
# ====================================================================

def send_api_request(payload: Dict[str, Any]) -> bool:
    """دالة عامة لإرسال طلب إلى Messenger Send API"""
    params = {'access_token': PAGE_ACCESS_TOKEN}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(
            'https://graph.facebook.com/v19.0/me/messages',
            params=params, json=payload, timeout=10
        )
        if response.status_code != 200:
            print(f"❌ Failed to send API request: {response.text}")
            return False
        return True
    except Exception as e:
        print(f"❌ Exception sending API request: {e}")
        return False

def send_text_message(recipient_id: str, message_text: str):
    """إرسال رسالة نصية بسيطة مع توقيع المطور"""
    footer = f"\n\n🤖 {AI_ASSISTANT_NAME}، تصميم: {DEVELOPER_NAME} | 🔗 {DEVELOPER_FACEBOOK_URL}"
    full_message = message_text + footer
    
    # فيسبوك تحدد 2000 حرف للرسالة النصية
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': full_message[:2000]}
    }
    send_api_request(payload)

def send_button_template(recipient_id: str, text: str, buttons: List[Dict[str, Any]]):
    """إرسال قالب أزرار (Button Template)"""
    payload = {
        'recipient': {'id': recipient_id},
        'message': {
            'attachment': {
                'type': 'template',
                'payload': {
                    'template_type': 'button',
                    'text': text,
                    'buttons': buttons
                }
            }
        }
    }
    send_api_request(payload)

def send_attachment(recipient_id: str, attachment_type: str, url: str):
    """إرسال مرفق (صورة، فيديو)"""
    payload = {
        'recipient': {'id': recipient_id},
        'message': {
            'attachment': {
                'type': attachment_type,
                'payload': {
                    'url': url,
                    'is_reusable': True
                }
            }
        }
    }
    send_api_request(payload)

def get_main_menu_buttons() -> List[Dict[str, Any]]:
    """بناء أزرار القائمة الرئيسية"""
    return [
        {"type": "postback", "title": "📚 مساعدة في الدراسة", "payload": "MENU_STUDY_HELP"},
        {"type": "postback", "title": "🎨 إنشاء صورة", "payload": "MENU_CREATE_IMAGE"},
        {"type": "postback", "title": "💻 مساعدة برمجة", "payload": "MENU_CODE_HELP"}
    ]

def get_menu_options_markup() -> List[Dict[str, Any]]:
    """بناء الأزرار الإضافية المطلوبة"""
    return [
        {"type": "postback", "title": "📝 استخراج نص (OCR)", "payload": "MENU_OCR_START"},
        {"type": "postback", "title": "✏️ تحرير صورة", "payload": "MENU_EDIT_IMAGE"},
        {"type": "postback", "title": "🔍 البحث في الويب", "payload": "MENU_SEARCH_WEB"}
    ]

# ====================================================================
# 🧠 منطق معالجة الصور والنصوص (الخدمات المتقدمة)
# ====================================================================

def call_ocr_api(image_url: str, instruction: str = "") -> str:
    """استخراج النص من الصورة باستخدام API"""
    try:
        response = requests.post(
            OCR_API,
            data={"text": instruction, "link": image_url},
            timeout=60
        )
        if response.ok:
            result = response.text
            try:
                json_data = json.loads(result)
                if 'response' in json_data:
                    result = json_data['response']
            except:
                pass
            return result.strip()
        return "❌ فشل استخراج النص."
    except Exception as e:
        print(f"OCR API Error: {e}")
        return "❌ خطأ في الاتصال بخدمة استخراج النص."

def create_image_ai(prompt: str) -> Optional[str]:
    """إنشاء صورة باستخدام Nano Banana"""
    try:
        response = requests.post(NANO_BANANA_API, data={'text': prompt}, timeout=60)
        if response.ok:
            result = response.text.strip()
            if result.startswith('http'):
                return result
    except:
        pass
    return None

def edit_image_ai(image_url: str, prompt: str) -> Optional[str]:
    """تحرير الصورة باستخدام Nano Banana"""
    try:
        response = requests.post(NANO_BANANA_API, data={'text': prompt, 'links': image_url}, timeout=60)
        if response.ok:
            result = response.text.strip()
            if result.startswith('http'):
                return result
    except:
        pass
    return None

# ====================================================================
# 🎯 منطق معالجة الرسائل والأحداث
# ====================================================================

def handle_user_message(sender_id: str, message_text: str):
    """معالجة الرسائل النصية العامة"""
    
    # --- معالجة الحالات المعلقة ---
    current_state = user_state[sender_id]['state']
    
    if current_state == 'WAITING_IMAGE_PROMPT':
        user_state[sender_id]['state'] = None
        send_text_message(sender_id, "⏳ جاري إنشاء الصورة. قد يستغرق الأمر بعض الوقت...")
        
        image_url = create_image_ai(message_text)
        
        if image_url:
            send_attachment(sender_id, 'image', image_url)
        else:
            send_text_message(sender_id, "⚠️ عذراً، فشل إنشاء الصورة. يرجى المحاولة مرة أخرى أو تغيير الوصف.")
        
        send_text_message(sender_id, "💡 يمكنك الآن اختيار خدمة أخرى من القائمة الرئيسية.")
        return

    if current_state == 'WAITING_EDIT_PROMPT':
        image_url = user_state[sender_id]['pending_url']
        user_state[sender_id]['state'] = None
        user_state[sender_id]['pending_url'] = None
        
        send_text_message(sender_id, "⏳ جاري تحرير الصورة. قد يستغرق الأمر بعض الوقت...")
        
        edited_url = edit_image_ai(image_url, message_text)
        
        if edited_url:
            send_attachment(sender_id, 'image', edited_url)
        else:
            send_text_message(sender_id, "⚠️ عذراً، فشل تحرير الصورة. يرجى المحاولة مرة أخرى أو تغيير الوصف.")
        
        send_text_message(sender_id, "💡 يمكنك الآن اختيار خدمة أخرى من القائمة الرئيسية.")
        return
        
    # --- معالجة الأوامر المباشرة ---
    if message_text.lower().startswith("بحث"):
        query = message_text[3:].strip()
        if not query:
            send_text_message(sender_id, "❌ يرجى كتابة موضوع البحث بعد كلمة 'بحث'.")
            return
        send_text_message(sender_id, "🔍 جاري البحث في الويب...")
        search_results = search_web_ai(query)
        send_text_message(sender_id, search_results)
        return

    if message_text.lower().startswith("كود"):
        query = message_text[3:].strip()
        if not query:
            send_text_message(sender_id, "❌ يرجى كتابة سؤالك البرمجي بعد كلمة 'كود'.")
            return
        send_text_message(sender_id, "💻 جاري معالجة طلبك البرمجي...")
        
        try:
            response = requests.post(DARKCODE_API, json={'text': query}, timeout=45)
            if response.ok:
                result = response.text.strip()
                send_text_message(sender_id, f"💻 **الحل البرمجي:**\n\n{_clean_grok_response(result)}")
            else:
                send_text_message(sender_id, "❌ خطأ في مساعد البرمجة.")
        except:
            send_text_message(sender_id, "❌ خطأ في الاتصال بخدمة البرمجة.")
        return
        
    # --- الدردشة العامة بالذكاء الاصطناعي مع السياق ---
    history = get_conversation_history(sender_id)
    response = call_grok4_ai(message_text, history)
    
    send_text_message(sender_id, response)
    add_conversation_entry(sender_id, message_text, response)

def handle_attachment(sender_id: str, attachment: Dict[str, Any]):
    """معالجة المرفقات (صور، ملفات)"""
    
    # 1. التحقق من نوع المرفق (نريد الصور فقط)
    if attachment.get('type') != 'image':
        send_text_message(sender_id, "⚠️ لا أستطيع حالياً معالجة هذا النوع من المرفقات. أرسل صورة فقط.")
        return
    
    # 2. استخراج رابط الصورة
    image_url = attachment['payload']['url']
    
    # 3. التحقق من حالة المستخدم (OCR أو تحرير)
    current_state = user_state[sender_id]['state']

    if current_state == 'WAITING_OCR_IMAGE':
        user_state[sender_id]['state'] = None
        send_text_message(sender_id, "⏳ جاري استخراج النص من الصورة...")
        
        # استخدام OCR API مباشرة مع رابط الصورة
        extracted_text = call_ocr_api(image_url, instruction="استخرج جميع النصوص والمعادلات والأرقام الموجودة في الصورة بالعربية والإنجليزية. احتفظ بالتنسيق والترتيب الأصلي.")
        
        if len(extracted_text) > 2000:
            extracted_text = extracted_text[:1900] + "..."
            
        if extracted_text and extracted_text != "❌ فشل استخراج النص.":
            send_text_message(sender_id, f"✅ **النص المستخرج (OCR):**\n\n{extracted_text}")
        else:
            send_text_message(sender_id, "❌ عذراً، لم أتمكن من استخراج نص واضح من الصورة. يرجى التأكد من جودة الصورة.")
            
        send_text_message(sender_id, "💡 يمكنك الآن اختيار خدمة أخرى من القائمة الرئيسية.")
        return
    
    elif current_state == 'WAITING_EDIT_IMAGE':
        user_state[sender_id]['state'] = 'WAITING_EDIT_PROMPT'
        user_state[sender_id]['pending_url'] = image_url
        
        send_text_message(sender_id, "📸 تم استلام الصورة.\n\n✏️ **أرسل الآن وصف التعديل المطلوب.**")
        return

    else:
        # إذا أرسل المستخدم صورة دون طلب مسبق
        text = "📸 لقد أرسلت صورة. اختر ماذا تريد أن تفعل بها:"
        buttons = [
            {"type": "postback", "title": "📝 استخراج النص (OCR)", "payload": "MENU_OCR_START"},
            {"type": "postback", "title": "✏️ تحرير الصورة", "payload": "MENU_EDIT_IMAGE"}
        ]
        send_button_template(sender_id, text, buttons)

def handle_postback(sender_id: str, postback_payload: str):
    """معالجة ضغط الأزرار (Postback)"""
    
    # إلغاء أي عملية سابقة قبل البدء
    cleanup_temp_files(sender_id)
    user_state[sender_id]['state'] = None
    
    if postback_payload == 'GET_STARTED_PAYLOAD' or postback_payload == 'MENU_MAIN':
        # رسالة الترحيب الكاملة (للمرة الأولى فقط)
        if user_state[sender_id]['first_time'] or postback_payload == 'GET_STARTED_PAYLOAD':
            user_state[sender_id]['first_time'] = False
            
            welcome_text = (
                f"🎉 أهلاً بك! أنا **{AI_ASSISTANT_NAME}**، مساعدك الذكي في الدراسة والبرمجة.\n\n"
                f"✨ **ميزات البوت الكاملة:**\n"
                f"• 🧠 دردشة ذكية مع تذكر سياق المحادثة.\n"
                f"• 📸 استخراج النص وحل التمارين من الصور (OCR).\n"
                f"• 🎨 إنشاء وتحرير الصور بالذكاء الاصطناعي.\n"
                f"• 💻 مساعدة في كتابة وحل الأكواد البرمجية.\n"
                f"• 🔍 البحث في الويب (40 متصفح).\n\n"
                f"💡 **للبدء:** اختر خدمة من القائمة أدناه أو أرسل سؤالك مباشرة."
            )
            
            buttons = get_main_menu_buttons() + get_menu_options_markup()
            send_button_template(sender_id, welcome_text, buttons)
            return

        # رسالة القائمة العادية
        text = "📋 **القائمة الرئيسية**\nاختر الخدمة التي تريدها أو أرسل سؤالك مباشرة."
        buttons = get_main_menu_buttons() + get_menu_options_markup()
        send_button_template(sender_id, text, buttons)

    elif postback_payload == 'MENU_STUDY_HELP':
        text = "📚 **المساعدة في الدراسة**\nأرسل سؤالك مباشرة وسأجيبك بالتفصيل (رياضيات، فيزياء، لغات، إلخ)."
        buttons = [{"type": "postback", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"}]
        send_button_template(sender_id, text, buttons)

    elif postback_payload == 'MENU_CREATE_IMAGE':
        user_state[sender_id]['state'] = 'WAITING_IMAGE_PROMPT'
        text = "🎨 **إنشاء صورة بالذكاء الاصطناعي**\n"
        text += "أرسل الآن وصف الصورة التي تريد إنشاءها، وسأقوم بتحويلها لك.\n\n"
        text += "مثال: 'رسم توضيحي لخلية نباتية بجودة عالية'"
        buttons = [{"type": "postback", "title": "🔙 إلغاء والعودة", "payload": "MENU_MAIN"}]
        send_button_template(sender_id, text, buttons)

    elif postback_payload == 'MENU_CODE_HELP':
        text = "💻 **مساعدة في البرمجة**\n"
        text += "أرسل سؤالك البرمجي مباشرة مسبوقاً بـ 'كود' (مثال: كود كيف أكتب دالة في Python) وسأقدم لك الحل والشرح."
        buttons = [{"type": "postback", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"}]
        send_button_template(sender_id, text, buttons)

    elif postback_payload == 'MENU_SEARCH_WEB':
        text = "🔍 **البحث في الويب**\n"
        text += "أرسل الآن جملة تبدأ بكلمة 'بحث' (مثال: بحث ما هو قانون الجاذبية؟) وسأبحث لك في 40 متصفح."
        buttons = [{"type": "postback", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"}]
        send_button_template(sender_id, text, buttons)
        
    elif postback_payload == 'MENU_OCR_START':
        user_state[sender_id]['state'] = 'WAITING_OCR_IMAGE'
        text = "📝 **استخراج النص من الصورة**\n"
        text += "أرسل الآن الصورة التي تريد استخراج النص منها (تخزين مؤقت ثم حذف).\n\n"
        text += "💡 ملاحظة: يجب أن تكون الصورة واضحة الملامح."
        buttons = [{"type": "postback", "title": "🔙 إلغاء والعودة", "payload": "MENU_MAIN"}]
        send_button_template(sender_id, text, buttons)
        
    elif postback_payload == 'MENU_EDIT_IMAGE':
        user_state[sender_id]['state'] = 'WAITING_EDIT_IMAGE'
        text = "✏️ **تحرير الصورة**\n"
        text += "أرسل الآن الصورة التي تريد تحريرها. ثم سأطلب منك وصف التعديل."
        buttons = [{"type": "postback", "title": "🔙 إلغاء والعودة", "payload": "MENU_MAIN"}]
        send_button_template(sender_id, text, buttons)

# ====================================================================
# 🌐 Webhook Endpoint (نقطة النهاية الإلزامية)
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """معالجة جميع طلبات فيسبوك الواردة"""
    
    if request.method == 'GET':
        # التحقق من الويب هوك
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            print('✅ Webhook Verified Successfully!')
            return challenge, 200
        else:
            return 'Invalid Verification Token', 403

    elif request.method == 'POST':
        # استقبال رسائل المستخدمين والأحداث
        data = request.get_json()
        
        if data['object'] == 'page':
            for entry in data['entry']:
                if 'messaging' in entry:
                    for messaging_event in entry['messaging']:
                        sender_id = messaging_event['sender']['id']
                        
                        # معالجة الرسائل النصية
                        if messaging_event.get('message') and messaging_event['message'].get('text'):
                            handle_user_message(sender_id, messaging_event['message']['text'].strip())
                        
                        # معالجة المرفقات (صور، ملفات)
                        elif messaging_event.get('message') and messaging_event['message'].get('attachments'):
                            for attachment in messaging_event['message']['attachments']:
                                handle_attachment(sender_id, attachment)
                        
                        # معالجة ضغط الأزرار (Postback)
                        elif messaging_event.get('postback'):
                            handle_postback(sender_id, messaging_event['postback']['payload'])
                        
                        # تأكد من تنظيف الملفات بعد كل تفاعل كامل
                        cleanup_temp_files(sender_id)

        return 'OK', 200


if __name__ == '__main__':
    # لتشغيل التطبيق، يجب استخدام خادم إنتاج (مثل Gunicorn) على HidenCloud
    
    # اطبع رابط الـ Webhook (افتراضي) للمساعدة في الإعداد:
    import socket
    hostname = socket.gethostname()
    print("=" * 50)
    print("🚀 إرشادات Webhook:")
    print(f"✅ Webhook URL (محتمل): https://your-hidencloud-domain.com/webhook")
    print(f"🔑 Verify Token: {VERIFY_TOKEN}")
    print(f"👤 المطور: {DEVELOPER_NAME}")
    print(f"🤖 اسم الذكاء الاصطناعي: {AI_ASSISTANT_NAME}")
    print("=" * 50)
    
    # يجب استخدام Gunicorn/uWSGI للتشغيل على HidenCloud
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
