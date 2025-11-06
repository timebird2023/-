import os
import json
import requests
import re
from flask import Flask, request
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import logging

# ====================================================================
# 📚 الإعدادات الأساسية
# ====================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# 🔑 رمز الوصول لصفحة فيسبوك
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'boykta2025')
PAGE_ACCESS_TOKEN = "EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9"

# معلومات المطور
DEVELOPER_NAME = "younes laldji"
AI_ASSISTANT_NAME = "بويكتا"

# 🌟 واجهات الذكاء الاصطناعي الخارجية (المتبقية) 🌟
GROK_API_URL = 'https://sii3.top/api/grok4.php'
OCR_API = 'https://sii3.top/api/OCR.php'
FLUX_MAX_API = 'https://sii3.top/api/flux-max.php' 
MUSIC_API = 'https://sii3.top/api/create-music.php' 

# الذاكرة المؤقتة وحالة المستخدم
user_state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
    'state': None, 
    'first_time': True, 
    'pending_url': None, 
    'last_extracted_text': None,
    'last_generated_url': None
})
in_memory_conversations: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

app = Flask(__name__)

# ====================================================================
# 🛠️ دوال الشبكة وإرسال الرسائل
# ... (بقية دوال الشبكة كما هي) ...
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
    """إرسال رسالة نصية بسيطة مع توقيع المطور"""
    footer = f"\n\n🤖 {AI_ASSISTANT_NAME}، تصميم: {DEVELOPER_NAME}" 
    full_message = message_text + footer
    payload = {
        'recipient': {'id': recipient_id},
        'message': {'text': full_message[:2000]}
    }
    send_api_request(payload)

def send_quick_replies(recipient_id: str, text: str, quick_replies: List[Dict]):
    """إرسال رسالة مع أزرار الرد السريع (Quick Replies)"""
    footer = f"\n\n🤖 {AI_ASSISTANT_NAME}، تصميم: {DEVELOPER_NAME}" 
    text_with_signature = text + footer
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "text": text_with_signature[:2000],
            "quick_replies": quick_replies
        }
    }
    send_api_request(data)


def send_button_template(recipient_id: str, text: str, buttons: List[Dict[str, Any]]):
    """إرسال قالب أزرار (Button Template) - يُستخدم للخيارات الثابتة"""
    footer = f"\n\n🤖 {AI_ASSISTANT_NAME}، تصميم: {DEVELOPER_NAME}" 
    text_with_signature = text + footer
    
    payload = {
        'recipient': {'id': recipient_id},
        'message': {
            'attachment': {
                'type': "template",
                "payload": {
                    "template_type": "button",
                    "text": text_with_signature[:640],
                    "buttons": buttons
                }
            }
        }
    }
    send_api_request(payload)

def send_attachment(recipient_id: str, attachment_type: str, url: str):
    """إرسال مرفق (صورة، فيديو، صوت)"""
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

def send_attachment_and_note(recipient_id: str, attachment_type: str, url: str, success_text: str):
    """**دالة جديدة: إرسال المرفق متبوعًا برسالة توضيحية**"""
    
    # 1. محاولة إرسال المرفق مباشرة
    send_attachment(recipient_id, attachment_type, url)
    
    # 2. إرسال رسالة النجاح والملاحظة
    if attachment_type != 'audio': 
        note = f"""
**ملاحظة حول العرض (فقط لتطبيق فيسبوك لايت):**
إذا لم تظهر الصورة/الفيديو، يرجى فتح الرسالة عبر **تطبيق فيسبوك ماسنجر** حيث تظهر المرفقات بشكل سليم.
"""
    else:
        note = ""
    
    send_menu_after_action(recipient_id, success_text + note)


def get_main_menu_quick_replies() -> List[Dict[str, Any]]:
    """**بناء أزرار القائمة الرئيسية المحدثة**"""
    return [
        {"content_type": "text", "title": "💬 محادثة جديدة", "payload": "MENU_NEW_CHAT"},
        {"content_type": "text", "title": "🖼️ إنشاء صورة", "payload": "MENU_CREATE_IMAGE_MAX"},
        {"content_type": "text", "title": "🎵 إنشاء موسيقى", "payload": "MENU_MUSIC_START"},
        {"content_type": "text", "title": "📝 تحليل الصور (OCR)", "payload": "MENU_OCR_START"},
        {"content_type": "text", "title": "✏️ تحرير الصور", "payload": "MENU_EDIT_IMAGE"},
        {"content_type": "text", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"}
    ]

def send_menu_after_action(recipient_id: str, prompt: str):
    """دالة موحدة لإرسال رسالة نصية تليها قائمة الردود السريعة الرئيسية"""
    send_quick_replies(recipient_id, prompt, get_main_menu_quick_replies())

# ====================================================================
# 🧠 منطق الذكاء الاصطناعي والخدمات
# ====================================================================

# ... (دوال السياق) ...
def get_conversation_history(user_id: str, limit: int = 5) -> List[Tuple[str, str]]:
    history = in_memory_conversations.get(user_id, [])
    return history[-limit:] if history else []

def add_conversation_entry(user_id: str, message: str, response: str):
    in_memory_conversations[user_id].append((message, response))
    if len(in_memory_conversations[user_id]) > 10:
        in_memory_conversations[user_id] = in_memory_conversations[user_id][-10:]

# دوال الخدمات
class AIModels:
    @staticmethod
    def _clean_response(text: str) -> str:
        """تنظيف الردود من JSON والرموز غير المرغوب فيها وتصحيح البروتوكول"""
        try:
            # 1. محاولة تحميل JSON
            try:
                json_data = json.loads(text)
                if isinstance(json_data, dict):
                    text = json_data.get('response', json_data.get('url', json_data.get('image', text)))
            except json.JSONDecodeError:
                pass
            
            # 2. تنظيف الرموز النصية
            text = re.sub(r'Don\'t forget to support.*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'@\w+', '', text) 
            text = re.sub(r'\\n', '\n', text)
            text = re.sub(r'\\t', '\t', text)
            text = re.sub(r'\\"', '"', text)

            # إصلاح البروتوكول: فرض HTTPS للروابط الناتجة
            stripped_text = text.strip()
            if stripped_text.startswith('http://'):
                stripped_text = 'https://' + stripped_text[7:]
            
            # محاولة إزالة الاقتباسات إذا كان الرد رابطًا ملفوفًا
            if (stripped_text.startswith('"') and stripped_text.endswith('"')) or \
               (stripped_text.startswith("'") and stripped_text.endswith("'")):
               stripped_text = stripped_text[1:-1]

            return stripped_text
        except Exception:
            return text.strip()

    @staticmethod
    def _translate_to_english(text: str) -> str:
        # دالة الترجمة (تم الإبقاء عليها كما هي)
        try:
            response = requests.get(
                'https://translate.googleapis.com/translate_a/single',
                params={'client': 'gtx', 'sl': 'auto', 'tl': 'en', 'dt': 't', 'q': text},
                timeout=5
            )
            if response.ok:
                result = response.json()
                if result and isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
                    return ''.join([item[0] for item in result[0] if isinstance(item, list) and len(item) > 0 and item[0]])
        except Exception:
            pass
        return text

    @staticmethod
    def grok4(text: str, conversation_history: list = None) -> str:
        """استدعاء Grok-4 للمحادثة العامة (يستخدم data=)"""
        prompt = text
        if conversation_history:
            context = "\n".join([f"المستخدم: {msg}\nالمساعد: {resp}" for msg, resp in conversation_history[-5:]])
            prompt = f"سياق المحادثة السابقة:\n{context}\n\nالسؤال الحالي: {text}"
        try:
            response = requests.post(GROK_API_URL, data={'text': prompt}, timeout=60)
            if response.ok:
                return AIModels._clean_response(response.text)
            else:
                return f"⚠️ خطأ في Grok-4 API (رمز: {response.status_code})"
        except Exception:
            return "💥 عذراً، فشل الاتصال بنظام الذكاء الاصطناعي."

    @staticmethod
    def call_ocr_api(image_url: str, instruction: str = "") -> str:
        """**استدعاء OCR API (مع تنسيق الرابط كقائمة مفصولة بـ ", ")**"""
        try:
            # 📌 الحل: نرسل الروابط كقائمة مفصولة بـ ", " حتى لو كانت صورة واحدة
            link_string = ""
            if image_url:
                 # استخدام ", ".join لتغليف الرابط الواحد في التنسيق المطلوب
                link_string = ", ".join([image_url]) 
            
            payload = {"link": link_string, "text": instruction}
            
            # استخدام data=payload
            response = requests.post(OCR_API, data=payload, timeout=60)
            
            if response.ok:
                extracted_text = AIModels._clean_response(response.text)
                
                # معالجة رسائل الخطأ من الـ API
                if 'Something went wrong' in extracted_text or 'Enter text + image' in extracted_text:
                    return f"❌ فشلت خدمة استخراج النص (OCR). يرجى التأكد من جودة الصورة. (الخطأ: {extracted_text[:50]}...)"
                
                if not extracted_text:
                    return "❌ فشل استخراج النص: لا يوجد نص في الرد."
                return extracted_text
            else:
                return f"❌ خطأ في OCR API (رمز: {response.status_code})"
        except Exception as e:
            logger.error(f"OCR Exception: {e}")
            return "❌ فشل الاتصال بخدمة OCR."

    @staticmethod
    def create_image_ai(prompt: str) -> Optional[str]:
        """**إنشاء الصور (Flux Max فقط) (يستخدم data=)**"""
        try:
            english_prompt = AIModels._translate_to_english(prompt)
            payload = {'prompt': english_prompt} 
            response = requests.post(FLUX_MAX_API, data=payload, timeout=90) 
            
            if response.ok:
                image_url = AIModels._clean_response(response.text)
                if image_url and 'http' in image_url:
                    return image_url
            else:
                logger.error(f"Image Creation API Error (Status: {response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Image Creation Exception: {e}")
            return None

    @staticmethod
    def edit_image_ai(image_url: str, edit_desc: str) -> Optional[str]:
        """**تحرير الصور (يستخدم data=)**"""
        english_desc = AIModels._translate_to_english(edit_desc)
        try:
            payload = {'prompt': english_desc, 'image': image_url} 
            response = requests.post(FLUX_MAX_API, data=payload, timeout=90)
            if response.ok:
                flux_url = AIModels._clean_response(response.text)
                if flux_url and 'http' in flux_url:
                    return flux_url
        except Exception as e:
            logger.error(f"Flux-Max Edit Exception: {e}")
            return None
        return None
    
    @staticmethod
    def create_music_ai(prompt: str) -> Optional[str]:
        """**إنشاء موسيقى (يستخدم data=)**"""
        try:
            payload = {'text': prompt}
            response = requests.post(MUSIC_API, data=payload, timeout=90) 
            
            if response.ok:
                music_url = AIModels._clean_response(response.text)
                if music_url and 'http' in music_url and music_url.endswith(('.mp3', '.wav', '.ogg', 'mp3')):
                    return music_url
            else:
                logger.error(f"Music Creation API Error (Status: {response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Music Creation Exception: {e}")
            return None

# ====================================================================
# 🎯 منطق معالجة الرسائل والأحداث
# ====================================================================

# ... (دوال get_user_first_name, send_welcome_and_guidance, handle_user_message) ...
def get_user_first_name(sender_id: str) -> str:
    # دالة جلب الاسم (تم الإبقاء عليها كما هي)
    try:
        user_info = requests.get(
            f"https://graph.facebook.com/v19.0/{sender_id}",
            params={"access_token": PAGE_ACCESS_TOKEN, "fields": "first_name"}
        ).json()
        return user_info.get('first_name', 'مستخدم')
    except Exception:
        return 'مستخدم'

def send_welcome_and_guidance(recipient_id: str, first_name: str, show_full_menu=True):
    """إرسال رسالة ترحيب وشرح للمستخدم الجديد (تم التحديث)"""
    
    if user_state[recipient_id]['first_time']:
        welcome_text = f"""👋 أهلاً بك يا **{first_name}**! أنا {AI_ASSISTANT_NAME}.

🌟 **كيف أساعدك؟ (الخدمات المتاحة):**
* **🖼️ إنشاء صور:** (النموذج العادي) أرسل وصفك وسأحولهُ إلى صورة.
* **🎵 إنشاء موسيقى:** أنشئ مقطوعة موسيقية مدتها 15 ثانية بوصف بسيط (يعمل بشكل جيد ✅).
* **📝 تحليل الصور (OCR):** أرسل صورة تحتوي على نص وسأقوم باستخراجه وتحليله.
* **💬 محادثة مباشرة:** أرسل أي سؤال وسأجيبك بذكاء.

⬇️ **اختر خدمتك من الأزرار أدناه:**"""
    
        send_text_message(recipient_id, welcome_text)
        user_state[recipient_id]['first_time'] = False
    
    if show_full_menu:
        send_menu_after_action(recipient_id, "💡 اختر الخدمة التالية:")


def handle_user_message(sender_id: str, message_text: str):
    """معالجة الرسائل النصية العامة"""
    
    current_state = user_state[sender_id]['state']
    
    # 1. حالات انتظار الوصف (إنشاء الصور)
    if current_state == 'WAITING_IMAGE_PROMPT_MAX':
        user_state[sender_id]['state'] = None
        send_text_message(sender_id, f"⏳ جاري إنشاء الصورة (Flux Max)...")
        
        final_url = AIModels.create_image_ai(message_text)
            
        if final_url:
            send_attachment_and_note(sender_id, 'image', final_url, "✅ تم إنشاء الصورة بنجاح!")
        else:
            send_menu_after_action(sender_id, "⚠️ عذراً، فشل إنشاء الصورة. حاول بوصف آخر.")
        
        return
        
    # 2. حالة انتظار وصف تعديل الصورة
    elif current_state == 'WAITING_EDIT_DESC':
        image_url = user_state[sender_id].pop('pending_url', None)
        user_state[sender_id]['state'] = None
        
        if not image_url:
            send_menu_after_action(sender_id, "⚠️ عذراً، لم أجد رابط الصورة المراد تعديلها.")
            return

        send_text_message(sender_id, "⏳ جاري تحرير الصورة...")
        final_url = AIModels.edit_image_ai(image_url, message_text)
            
        if final_url:
            send_attachment_and_note(sender_id, 'image', final_url, "✅ تم تحرير الصورة بنجاح!")
        else:
            send_menu_after_action(sender_id, "⚠️ عذراً، فشل تحرير الصورة. حاول بوصف تعديل مختلف.")
        
        return
        
    # 3. حالة انتظار وصف الموسيقى
    elif current_state == 'WAITING_MUSIC_PROMPT':
        user_state[sender_id]['state'] = None
        send_text_message(sender_id, "⏳ جاري إنشاء المقطوعة الموسيقية (15 ثانية)...")
        
        final_url = AIModels.create_music_ai(message_text)
        
        if final_url:
            send_attachment_and_note(sender_id, 'audio', final_url, "✅ تم إنشاء الموسيقى بنجاح!")
        else:
            send_menu_after_action(sender_id, "⚠️ عذراً، فشل إنشاء المقطوعة الموسيقية.")
        
        return

    # 4. الدردشة العامة بالذكاء الاصطناعي مع السياق (الحالة الافتراضية)
    history = get_conversation_history(sender_id)
    response = AIModels.grok4(message_text, history)
    
    send_menu_after_action(sender_id, response)
    add_conversation_entry(sender_id, message_text, response)
    
def handle_attachment(sender_id: str, attachment: Dict[str, Any]):
    """معالجة المرفقات (صور)"""
    
    attachment_type = attachment.get('type')
    
    if attachment_type == 'image':
        
        # 📌 بناء الرابط المحسن بـ access_token (مطلوب لتمكين الـ OCR API من الوصول)
        image_url_for_api = f"{attachment['payload']['url']}&access_token={PAGE_ACCESS_TOKEN}"
        
        current_state = user_state[sender_id]['state']

        if current_state == 'WAITING_EDIT_IMAGE':
            user_state[sender_id]['state'] = 'WAITING_EDIT_DESC'
            user_state[sender_id]['pending_url'] = image_url_for_api 
            send_text_message(sender_id, "✏️ **أرسل وصف التعديل المطلوب الآن:**")
            return

        elif current_state == 'WAITING_OCR_IMAGE_FOR_ANALYSIS':
            # 📌 الإصلاح: نحفظ الرابط ونعرض الأزرار مباشرة
            user_state[sender_id]['state'] = 'WAITING_OCR_COMMAND' # حالة جديدة: انتظار أمر OCR
            user_state[sender_id]['pending_url'] = image_url_for_api # حفظ الرابط المحسن
            
            text = "✅ **تم استلام الصورة.** اختر الأمر المطلوب تنفيذه على النص الموجود بالصورة:"
            
            buttons = [
                {"type": "postback", "title": "📝 استخراج النص فقط", "payload": "OCR_SHOW_TEXT"}, 
                {"type": "postback", "title": "🌐 استخراج وترجمة", "payload": "OCR_TRANSLATE_EXEC"}, # تم تغيير الحمولة
                {"type": "postback", "title": "💡 استخراج وشرح/تحليل", "payload": "OCR_ANALYZE_EXEC"}, # تم تغيير الحمولة
            ]
            send_button_template(sender_id, text, buttons)
            
            return
        
        else:
            # إذا أرسل المستخدم صورة دون طلب مسبق (عرض خيارات سريعة)
            text = "📸 لقد أرسلت صورة. اختر ماذا تريد أن تفعل بها:"
            buttons = [
                {"type": "postback", "title": "📝 استخراج النص (OCR)", "payload": "MENU_OCR_START"},
                {"type": "postback", "title": "✏️ تحرير هذه الصورة", "payload": "START_EDIT_FROM_IMG"},
                {"type": "postback", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"},
            ]
            user_state[sender_id]['pending_url'] = image_url_for_api # حفظ الرابط المحسن
            send_button_template(sender_id, text, buttons)
            
    
    else:
        send_menu_after_action(sender_id, "⚠️ لا أستطيع معالجة هذا النوع من المرفقات. أرسل صورة فقط.")

def handle_postback(sender_id: str, postback_payload: str):
    """معالجة ضغط الأزرار (Postback)"""
    
    user_state[sender_id]['state'] = None
    first_name = get_user_first_name(sender_id)
    
    # 1. القائمة الرئيسية/الترحيب
    if postback_payload in ['GET_STARTED_PAYLOAD', 'MENU_MAIN', 'MENU_NEW_CHAT']:
        send_welcome_and_guidance(sender_id, first_name, show_full_menu=True)

    # 2. إنشاء صورة (تم التوحيد)
    elif postback_payload == 'MENU_CREATE_IMAGE_MAX':
        user_state[sender_id]['state'] = 'WAITING_IMAGE_PROMPT_MAX'
        send_text_message(sender_id, "🎨 **(Flux Max)** أرسل وصف الصورة التي تريد إنشاءها:")
        
    # 3. بدء تحرير صورة من القائمة أو من زر سريع
    elif postback_payload in ['MENU_EDIT_IMAGE', 'START_EDIT_FROM_IMG']:
        image_url = user_state[sender_id].pop('pending_url', None)
        
        if image_url:
            user_state[sender_id]['state'] = 'WAITING_EDIT_DESC'
            user_state[sender_id]['pending_url'] = image_url
            send_text_message(sender_id, "✏️ **أرسل وصف التعديل المطلوب الآن:**")
        else:
            user_state[sender_id]['state'] = 'WAITING_EDIT_IMAGE'
            send_text_message(sender_id, "✏️ **أرسل الصورة التي تريد تحريرها الآن:**")
            
    # 4. بدء إنشاء الموسيقى
    elif postback_payload == 'MENU_MUSIC_START':
        user_state[sender_id]['state'] = 'WAITING_MUSIC_PROMPT'
        send_text_message(sender_id, "🎵 **أرسل نوع الموسيقى أو الوصف المطلوب (مثال: 'love' أو 'rock'):**")

    # 5. بدء عملية OCR
    elif postback_payload == 'MENU_OCR_START':
        user_state[sender_id]['state'] = 'WAITING_OCR_IMAGE_FOR_ANALYSIS'
        send_text_message(sender_id, "📝 **أرسل الصورة التي تريد استخراج النص وتحليلها:**")

    # 6. خيارات OCR/التحليل (المعالجة الفورية)
    elif postback_payload in ['OCR_SHOW_TEXT', 'OCR_TRANSLATE_EXEC', 'OCR_ANALYZE_EXEC']:
        
        # 📌 الخطوة الحاسمة: المعالجة الفورية لـ OCR
        
        image_url = user_state[sender_id].pop('pending_url', None)
        if not image_url:
            send_menu_after_action(sender_id, "❌ انتهت صلاحية الصورة. يرجى إرسال الصورة مجدداً.")
            return

        send_text_message(sender_id, "⏳ جاري المعالجة بواسطة OCR API...")
        
        # تحديد التعليمات المطلوبة للـ OCR API بناءً على الزر
        if postback_payload == 'OCR_SHOW_TEXT':
            instruction = "استخرج النص فقط"
        elif postback_payload == 'OCR_TRANSLATE_EXEC':
            instruction = "ترجم النص إلى العربية والإنجليزية"
        elif postback_payload == 'OCR_ANALYZE_EXEC':
            instruction = "اشرح وحلل النص بالتفصيل"
        else:
            instruction = ""

        # إرسال طلب واحد إلى OCR API (الذي يقوم بالاستخراج والتنفيذ)
        response_text = AIModels.call_ocr_api(image_url, instruction)
        
        if response_text and not response_text.startswith("❌"):
            # يتم عرض نتيجة المعالجة مباشرة (استخراج، ترجمة، أو شرح)
            send_menu_after_action(sender_id, response_text)
        else:
            send_menu_after_action(sender_id, f"❌ فشلت عملية OCR والتحليل: {response_text}")

# ====================================================================
# 🌐 Webhook Endpoint 
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """معالجة جميع طلبات فيسبوك الواردة"""
    
    if request.method == 'GET':
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
        data = request.get_json()

        for entry in data.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event['sender']['id']
                
                # أ. معالجة الرسائل النصية (القائمة الرئيسية والمحادثة)
                if messaging_event.get('message') and messaging_event['message'].get('text'):
                    message = messaging_event['message']
                    message_text = message['text'].strip()
                    
                    if message.get('quick_reply'):
                        handle_postback(sender_id, message['quick_reply']['payload'])
                    else:
                        # لا توجد حالة انتظار نص هنا، كل شيء يعود للمحادثة العادية
                        handle_user_message(sender_id, message_text)
                
                # ب. معالجة المرفقات (Attachment)
                elif messaging_event.get('message') and messaging_event['message'].get('attachments'):
                    for attachment in messaging_event['message']['attachments']:
                        handle_attachment(sender_id, attachment)
                
                # ج. معالجة ضغط الأزرار (Postback)
                elif messaging_event.get('postback'):
                    handle_postback(sender_id, messaging_event['postback']['payload'])
                
                # د. معالجة حدث البدء الأول (Get Started)
                elif messaging_event.get('postback', {}).get('payload') == 'GET_STARTED_PAYLOAD':
                    handle_postback(sender_id, 'GET_STARTED_PAYLOAD')

        return 'OK', 200

# ====================================================================
# 🚀 تشغيل التطبيق (باستخدام Gunicorn عند النشر)
# ====================================================================

if __name__ == '__main__':
    logger.info("🚀 بدء تشغيل بوت فيسبوك ماسنجر (مكتبات أساسية)")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))
