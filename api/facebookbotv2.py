import os
import json
import requests
import re
import time
from flask import Flask, request
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import logging

# 🚨 يجب أن يحتوي requirements.txt على: Flask, requests

# إعداد الـ Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ====================================================================
# 🔑 المتغيرات الأساسية والإعدادات 
# ====================================================================

# تُقرأ من Vercel Environment Variables
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'boykta2025')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN', 'EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9')

# معلومات المطور (التوقيع لا يحتوي على رابط)
DEVELOPER_NAME = "younes laldji"
AI_ASSISTANT_NAME = "بويكتا"

# واجهات الذكاء الاصطناعي
GROK_API_URL = 'https://sii3.top/api/grok4.php'
OCR_API = 'https://sii3.top/api/OCR.php'
NANO_BANANA_API = 'https://sii3.top/api/nano-banana.php' # لإنشاء وتحرير الصور

# الذاكرة المؤقتة لحالة المستخدم والسياق
user_state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {'state': None, 'first_time': True})
in_memory_conversations: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

app = Flask(__name__)

# ====================================================================
# 🛠️ دوال الشبكة وإرسال الرسائل (الفصل والإرسال)
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
            logger.error(f"❌ Failed to send API request: {response.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"❌ Exception sending API request: {e}")
        return False

def send_text_message(recipient_id: str, message_text: str):
    """إرسال رسالة نصية بسيطة مع توقيع المطور (بدون رابط)"""
    footer = f"\n\n🤖 {AI_ASSISTANT_NAME}، تصميم: {DEVELOPER_NAME}" 
    full_message = message_text + footer
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': full_message[:2000]}
    }
    send_api_request(payload)

def send_button_template(recipient_id: str, text: str, buttons: List[Dict[str, Any]]):
    """إرسال قالب أزرار (Button Template) - يُستخدم لإرسال القوائم"""
    payload = {
        'recipient': {'id': recipient_id},
        'message': {
            'attachment': {
                'type': "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": buttons
                }
            }
        }
    }
    send_api_request(payload)

def send_attachment(recipient_id: str, attachment_type: str, url: str):
    """إرسال مرفق (صورة)"""
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
    
    # إرسال القائمة بعد إرسال الصورة
    send_menu_after_action(recipient_id, "💡 تم إرسال الصورة بنجاح!")


def get_main_menu_buttons_template() -> List[Dict[str, Any]]:
    """بناء أزرار القائمة الرئيسية كـ Postbacks"""
    return [
        {"type": "postback", "title": "🎨 إنشاء صورة", "payload": "MENU_CREATE_IMAGE"},
        {"type": "postback", "title": "📝 تحليل الصور (OCR)", "payload": "MENU_OCR_START"},
        {"type": "postback", "title": "✏️ تحرير الصور", "payload": "MENU_EDIT_IMAGE"},
        {"type": "postback", "title": "🔙 قائمة الخدمات", "payload": "MENU_MAIN"}
    ]

def send_menu_after_action(recipient_id: str, prompt: str):
    """دالة موحدة لإرسال رسالة نصية تليها قائمة الأزرار الرئيسية"""
    send_text_message(recipient_id, prompt)
    send_button_template(recipient_id, "💡 اختر الخدمة التالية:", get_main_menu_buttons_template())


# ====================================================================
# 🧠 منطق الذكاء الاصطناعي والسياق
# ====================================================================

# ... (دوال السياق والمحادثة تبقى كما هي) ...

def call_grok4_ai(text: str, conversation_history: list = None) -> str:
    """استدعاء Grok-4 للمحادثة العامة مع سياق محسّن وتنظيف الرد"""
    prompt = text
    if conversation_history:
        context = "\n".join([f"المستخدم: {msg}\nالمساعد: {resp}" for msg, resp in conversation_history[-5:]])
        prompt = f"سياق المحادثة السابقة:\n{context}\n\nالسؤال الحالي: {text}"

    try:
        response = requests.post(GROK_API_URL, data={'text': prompt}, timeout=60)
        if response.ok:
            result = response.text
            
            # 💡 تنظيف الرد: إزالة حقول JSON المزعجة 
            try:
                json_data = json.loads(result)
                if isinstance(json_data, dict):
                    if 'response' in json_data:
                        result = json_data['response']
                    # إزالة حقول DATE و DEV
                    if 'date' in json_data:
                        del json_data['date']
                    if 'dev' in json_data:
                        del json_data['dev']
            except json.JSONDecodeError:
                pass
            
            # تنظيف النص الزائد (كما في كود التلغرام)
            result = re.sub(r'Don\'t forget to support.*', '', result, flags=re.IGNORECASE)
            result = re.sub(r'@\w+', '', result) 
            
            return result.strip()
        else:
            return f"⚠️ خطأ في Grok-4 API (رمز: {response.status_code})"

    except Exception:
        return "💥 عذراً، فشل الاتصال بنظام الذكاء الاصطناعي."

# ... (دوال OCR والصور الأخرى تبقى كما هي) ...

# ====================================================================
# 🎯 منطق معالجة الرسائل والأحداث (الفصل الرئيسي)
# ====================================================================

def handle_user_message(sender_id: str, message_text: str):
    """معالجة الرسائل النصية العامة - تذهب للذكاء الاصطناعي فقط"""
    
    current_state = user_state[sender_id]['state']
    
    # 1. حالات انتظار الوصف (صورة أو تحرير)
    if current_state in ['WAITING_IMAGE_PROMPT', 'WAITING_EDIT_DESC']:
        # تفريغ حالة الانتظار
        is_edit = (current_state == 'WAITING_EDIT_DESC')
        user_state[sender_id]['state'] = None
        
        send_text_message(sender_id, f"⏳ جاري {'تحرير' if is_edit else 'إنشاء'} الصورة...")
        
        if is_edit:
            image_url = user_state[sender_id].pop('pending_edit_url', None)
            final_url = edit_image_ai(image_url, message_text)
        else:
            final_url = create_image_ai(message_text)
            
        if final_url:
            send_attachment(sender_id, 'image', final_url)
        else:
            send_menu_after_action(sender_id, f"⚠️ عذراً، فشل {'تحرير' if is_edit else 'إنشاء'} الصورة.")
        
        return

    # 2. الدردشة العامة بالذكاء الاصطناعي مع السياق
    history = get_conversation_history(sender_id)
    response = call_grok4_ai(message_text, history)
    
    send_menu_after_action(sender_id, response)
    add_conversation_entry(sender_id, message_text, response)
    
def handle_attachment(sender_id: str, attachment: Dict[str, Any]):
    """معالجة المرفقات (صور)"""
    
    if attachment.get('type') != 'image':
        send_menu_after_action(sender_id, "⚠️ لا أستطيع حالياً معالجة هذا النوع من المرفقات. أرسل صورة فقط.")
        return
    
    image_url = attachment['payload']['url']
    current_state = user_state[sender_id]['state']

    if current_state == 'WAITING_OCR_IMAGE_FOR_ANALYSIS':
        # حالة تحليل الصورة بعد طلب OCR
        user_state[sender_id]['state'] = None
        user_state[sender_id]['pending_ocr_url'] = image_url
        
        send_text_message(sender_id, "🔍 تم استلام الصورة. جاري استخراج النص...")
        
        extracted_text = call_ocr_api(image_url)
        
        if extracted_text and not extracted_text.startswith("❌"):
            user_state[sender_id]['last_extracted_text'] = extracted_text
            text = f"✅ **تم استخراج النص:**\n{extracted_text[:300]}...\n\n❓ **ماذا تريد أن تفعل بهذا النص؟**"
            
            buttons = [
                {"type": "postback", "title": "🌐 ترجمة", "payload": "OCR_TRANSLATE"},
                {"type": "postback", "title": "💡 شرح وتحليل", "payload": "OCR_ANALYZE"},
                {"type": "postback", "title": "📝 النص فقط", "payload": "OCR_SHOW_TEXT"},
            ]
            send_button_template(sender_id, text, buttons)
        else:
            send_menu_after_action(sender_id, f"❌ فشل استخراج النص من الصورة. {extracted_text}")
        
        return
    
    else:
        # إذا أرسل المستخدم صورة دون طلب مسبق (عرض خيارات سريعة)
        text = "📸 لقد أرسلت صورة. اختر ماذا تريد أن تفعل بها:"
        buttons = [
            {"type": "postback", "title": "📝 استخراج النص (OCR)", "payload": "MENU_OCR_START"},
            {"type": "postback", "title": "✏️ تحرير هذه الصورة", "payload": "START_EDIT_FROM_IMG"},
            {"type": "postback", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"}
        ]
        user_state[sender_id]['pending_quick_edit_url'] = image_url # حفظ الرابط للتحرير السريع
        send_button_template(sender_id, text, buttons)

def handle_postback(sender_id: str, postback_payload: str):
    """معالجة ضغط الأزرار (Postback) - لا يذهب للذكاء الاصطناعي"""
    
    user_state[sender_id]['state'] = None
    
    # 1. القائمة الرئيسية/الترحيب
    if postback_payload in ['GET_STARTED_PAYLOAD', 'MENU_MAIN']:
        text = f"👋 أهلاً بك! أنا {AI_ASSISTANT_NAME}. اختر خدمتك:"
        send_menu_after_action(sender_id, text)
        
    # 2. إنشاء صورة
    elif postback_payload == 'MENU_CREATE_IMAGE':
        user_state[sender_id]['state'] = 'WAITING_IMAGE_PROMPT'
        send_text_message(sender_id, "🎨 **أرسل وصف الصورة التي تريد إنشاءها:**")

    # 3. بدء عملية OCR
    elif postback_payload == 'MENU_OCR_START':
        user_state[sender_id]['state'] = 'WAITING_OCR_IMAGE_FOR_ANALYSIS'
        send_text_message(sender_id, "📝 **أرسل الصورة التي تريد استخراج النص وتحليلها:**")
        
    # 4. بدء تحرير صورة من قائمة الأزرار السريعة
    elif postback_payload == 'START_EDIT_FROM_IMG':
        # استخدام الرابط المحفوظ من الإرسال السريع للصورة (من دالة handle_attachment)
        image_url = user_state[sender_id].pop('pending_quick_edit_url', None)
        if image_url:
            user_state[sender_id]['state'] = 'WAITING_EDIT_DESC'
            user_state[sender_id]['pending_edit_url'] = image_url
            send_text_message(sender_id, "✏️ **أرسل وصف التعديل المطلوب الآن:**")
        else:
            send_text_message(sender_id, "⚠️ عذراً، الرابط غير موجود. يرجى إرسال الصورة مرة أخرى.")

    # 5. خيارات OCR بعد الاستخراج
    elif postback_payload.startswith('OCR_'):
        extracted_text = user_state[sender_id].get('last_extracted_text', '')
        if not extracted_text:
            send_text_message(sender_id, "❌ انتهت صلاحية النص. يرجى إرسال الصورة مجدداً.")
            return

        send_text_message(sender_id, "⏳ جاري المعالجة...")
        
        if postback_payload == 'OCR_SHOW_TEXT':
            send_text_message(sender_id, f"📝 **النص المستخرج كاملاً:**\n\n{extracted_text[:1800]}...")
            
        elif postback_payload == 'OCR_TRANSLATE':
            prompt = f"ترجم النص التالي إلى العربية:\n\n{extracted_text}"
            translation = call_grok4_ai(prompt)
            send_text_message(sender_id, f"🌐 **الترجمة إلى العربية:**\n\n{translation}")
            
        elif postback_payload == 'OCR_ANALYZE':
            prompt = f"حلل هذا النص واشرح محتواه بالتفصيل (إذا كان تمريناً فقدم الحل، وإذا كان نصاً فقدم شرحاً): \n\n{extracted_text}"
            analysis = call_grok4_ai(prompt)
            send_text_message(sender_id, f"💡 **تحليل وشرح النص:**\n\n{analysis}")
            
        send_menu_after_action(sender_id, "💡 اختر خدمة أخرى:")

# ====================================================================
# 🌐 Webhook Endpoint (نقطة النهاية الإلزامية)
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """معالجة جميع طلبات فيسبوك الواردة"""
    
    if request.method == 'GET':
        # 1. التحقق من الويب هوك (Verification)
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info('✅ Webhook Verified Successfully!')
            return challenge, 200
        else:
            logger.error('❌ Invalid Verification Token or Mode')
            return 'Invalid Verification Token', 403

    elif request.method == 'POST':
        # 2. استقبال الرسائل والأحداث (Messaging)
        data = request.get_json()

        for entry in data.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event['sender']['id']
                
                # أ. معالجة الرسائل النصية
                if messaging_event.get('message') and messaging_event['message'].get('text'):
                    handle_user_message(sender_id, messaging_event['message']['text'].strip())
                
                # ب. معالجة المرفقات (Attachment)
                elif messaging_event.get('message') and messaging_event['message'].get('attachments'):
                    for attachment in messaging_event['message']['attachments']:
                        if attachment['type'] == 'image':
                            handle_attachment(sender_id, attachment)
                
                # ج. معالجة ضغط الأزرار (Postback) - لا يذهب للذكاء الاصطناعي
                elif messaging_event.get('postback'):
                    handle_postback(sender_id, messaging_event['postback']['payload'])

        return 'OK', 200
