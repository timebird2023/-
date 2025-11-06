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

# واجهات الذكاء الاصطناعي الخارجية (المعتمدة على requests)
GROK_API_URL = 'https://sii3.top/api/grok4.php'
OCR_API = 'https://sii3.top/api/OCR.php'
NANO_BANANA_API = 'https://sii3.top/api/nano-banana.php' # لإنشاء وتحرير الصور (المحاولة الثانية للتحرير)
FLUX_MAX_API = 'https://sii3.top/api/flux-max.php' # لتحرير الصور (المحاولة الأولى)

# الذاكرة المؤقتة وحالة المستخدم (بديل SQLite)
user_state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {'state': None, 'first_time': True, 'pending_url': None, 'last_extracted_text': None})
# يخزن آخر 10 رسائل لكل مستخدم (كحد أقصى)
in_memory_conversations: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

app = Flask(__name__)

# ====================================================================
# 🛠️ دوال الشبكة وإرسال الرسائل
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

def get_main_menu_quick_replies() -> List[Dict[str, Any]]:
    """بناء أزرار القائمة الرئيسية كـ Quick Replies"""
    return [
        {"content_type": "text", "title": "💬 محادثة جديدة", "payload": "MENU_NEW_CHAT"},
        {"content_type": "text", "title": "🎨 إنشاء صورة", "payload": "MENU_CREATE_IMAGE"},
        {"content_type": "text", "title": "📝 تحليل الصور", "payload": "MENU_OCR_START"},
        {"content_type": "text", "title": "✏️ تحرير الصور", "payload": "MENU_EDIT_IMAGE"},
        {"content_type": "text", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"}
    ]

def send_menu_after_action(recipient_id: str, prompt: str):
    """دالة موحدة لإرسال رسالة نصية تليها قائمة الردود السريعة الرئيسية"""
    send_quick_replies(recipient_id, prompt, get_main_menu_quick_replies())

# ====================================================================
# 🧠 منطق الذكاء الاصطناعي والخدمات
# ====================================================================

# دوال السياق (تستخدم الذاكرة المؤقتة فقط)
def get_conversation_history(user_id: str, limit: int = 5) -> List[Tuple[str, str]]:
    """استرجاع سجل المحادثة (آخر 5 رسائل)"""
    history = in_memory_conversations.get(user_id, [])
    # يتم استرجاع آخر limit عنصر
    return history[-limit:] if history else []

def add_conversation_entry(user_id: str, message: str, response: str):
    """إضافة رسالة ورد إلى سجل المحادثة (الذاكرة المؤقتة)"""
    in_memory_conversations[user_id].append((message, response))
    # الحفاظ على حجم السجل بحد أقصى 10
    if len(in_memory_conversations[user_id]) > 10:
        in_memory_conversations[user_id] = in_memory_conversations[user_id][-10:]

# دوال الخدمات
class AIModels:
    @staticmethod
    def _clean_response(text: str) -> str:
        """تنظيف الردود من JSON والرموز غير المرغوب فيها"""
        try:
            try:
                json_data = json.loads(text)
                if isinstance(json_data, dict) and 'response' in json_data:
                    text = json_data['response']
            except json.JSONDecodeError:
                pass
            
            text = re.sub(r'Don\'t forget to support.*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'@\w+', '', text) 
            text = re.sub(r'\\n', '\n', text)
            text = re.sub(r'\\t', '\t', text)
            text = re.sub(r'\\"', '"', text)
            return text.strip()
        except Exception:
            return text.strip()

    @staticmethod
    def grok4(text: str, conversation_history: list = None) -> str:
        """استدعاء Grok-4 للمحادثة العامة مع سياق محسّن"""
        prompt = text
        if conversation_history:
            # يتم بناء سياق المحادثة من آخر 5 مدخلات
            context = "\n".join([f"المستخدم: {msg}\nالمساعد: {resp}" for msg, resp in conversation_history[-5:]])
            prompt = f"سياق المحادثة السابقة:\n{context}\n\nالسؤال الحالي: {text}"

        try:
            # GROK API uses 'data' (form-urlencoded)
            response = requests.post(GROK_API_URL, data={'text': prompt}, timeout=60)
            if response.ok:
                return AIModels._clean_response(response.text)
            else:
                return f"⚠️ خطأ في Grok-4 API (رمز: {response.status_code})"
        except Exception:
            return "💥 عذراً، فشل الاتصال بنظام الذكاء الاصطناعي."

    @staticmethod
    def call_ocr_api(image_url: str, instruction: str = "") -> str:
        """استدعاء OCR API لاستخراج النص من الصورة فقط (تم التعديل لاستخدام json)"""
        try:
            payload = {"link": image_url, "text": instruction}
            # *** التعديل: استخدام json=payload بدلاً من data=payload ***
            response = requests.post(OCR_API, json=payload, timeout=60)
            if response.ok:
                try:
                    result_json = response.json()
                except json.JSONDecodeError:
                    # قد يكون الرد ليس JSON صالحاً، نتعامل معه كنص عادي
                    extracted_text = response.text
                else:
                    extracted_text = result_json.get('response', '')
                
                # --- [التصحيح المطبق: معالجة رسالة الخطأ المحددة] ---
                error_message = "Something went wrong. Please try again."
                if extracted_text and error_message in extracted_text:
                    logger.error(f"OCR API returned specific error: {extracted_text}")
                    # إرسال رسالة خطأ واضحة بدلاً من النص غير المرغوب فيه
                    return f"❌ فشلت خدمة استخراج النص (OCR). يرجى التأكد من جودة الصورة أو محاولة صورة أخرى. (الخطأ: {error_message})"
                # ----------------------------------------------------
                
                if not extracted_text:
                    return "❌ فشل استخراج النص: لا يوجد نص في الرد."
                return extracted_text.replace('\\n', '\n').strip()
            else:
                return f"❌ خطأ في OCR API (رمز: {response.status_code})"
        except Exception as e:
            logger.error(f"OCR Exception: {e}")
            return "❌ فشل الاتصال بخدمة OCR."

    @staticmethod
    def create_image_ai(prompt: str) -> Optional[str]:
        """استدعاء API لإنشاء الصور (Nano-Banana) مع ترجمة الوصف (تم التعديل لاستخدام json)"""
        try:
            english_prompt = AIModels._translate_to_english(prompt)
            payload = {'text': english_prompt}
            # *** التعديل: استخدام json=payload بدلاً من data=payload ***
            response = requests.post(NANO_BANANA_API, json=payload, timeout=90) 
            
            if response.ok:
                try:
                    data = response.json()
                    # بحث مرن عن الرابط
                    image_url = data.get('url') or data.get('image') 
                    
                    if image_url and 'http' in image_url: # التأكد من أنه رابط صالح
                        return image_url
                    
                    logger.error(f"Nano-Banana Create Failed: No valid URL found in response data: {data}")
                    return None
                except json.JSONDecodeError:
                    logger.error(f"Nano-Banana Create Failed: Invalid JSON response: {response.text}")
                    return None
            else:
                logger.error(f"Nano-Banana Create API Error (Status: {response.status_code}): {response.text}")
                return None
        except Exception as e:
            logger.error(f"Image Create Exception: {e}")
            return None

    @staticmethod
    def edit_image_ai(image_url: str, edit_desc: str) -> Optional[str]:
        """استدعاء API لتحرير الصور (Flux-Max أولاً، ثم Nano-Banana) مع ترجمة الوصف (تم التعديل لاستخدام json)"""
        english_desc = AIModels._translate_to_english(edit_desc)

        # 1. محاولة Flux-Max (الخدمة المحدثة)
        try:
            payload = {'prompt': english_desc, 'image': image_url} 
            # *** التعديل: استخدام json=payload بدلاً من data=payload ***
            response = requests.post(FLUX_MAX_API, json=payload, timeout=90)
            if response.ok:
                try:
                    data = response.json()
                    flux_url = data.get('url')
                    if flux_url and 'http' in flux_url:
                        return flux_url
                except json.JSONDecodeError:
                    logger.warning(f"Flux-Max returned non-JSON/invalid response: {response.text}")
                    pass 
        except Exception:
            logger.warning("Flux-Max edit failed, falling back to Nano-Banana")
            
        # 2. محاولة Nano-Banana (المحاولة الاحتياطية)
        try:
            payload = {'text': english_desc, 'links': image_url}
            # *** التعديل: استخدام json=payload بدلاً من data=payload ***
            response = requests.post(NANO_BANANA_API, json=payload, timeout=90)
            if response.ok:
                try:
                    data = response.json()
                    nano_url = data.get('url') or data.get('image')
                    if nano_url and 'http' in nano_url:
                        return nano_url
                except json.JSONDecodeError:
                    logger.warning(f"Nano-Banana Edit returned non-JSON/invalid response: {response.text}")
                    pass
        except Exception as e:
            logger.error(f"Nano-Banana Edit Exception: {e}")
            return None
        
        return None

    @staticmethod
    def _translate_to_english(text: str) -> str:
        """ترجمة النص إلى الإنجليزية لتحسين دقة إنشاء/تحرير الصور"""
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

# ====================================================================
# 🎯 منطق معالجة الرسائل والأحداث
# ====================================================================

def get_user_first_name(sender_id: str) -> str:
    """الحصول على اسم المستخدم الأول من فيسبوك"""
    try:
        user_info = requests.get(
            f"https://graph.facebook.com/v19.0/{sender_id}",
            params={"access_token": PAGE_ACCESS_TOKEN, "fields": "first_name"}
        ).json()
        return user_info.get('first_name', 'مستخدم')
    except Exception:
        return 'مستخدم'


def send_welcome_and_guidance(recipient_id: str, first_name: str, show_full_menu=True):
    """إرسال رسالة ترحيب وشرح للمستخدم الجديد"""
    
    if user_state[recipient_id]['first_time']:
        welcome_text = f"""👋 أهلاً بك يا **{first_name}**! أنا {AI_ASSISTANT_NAME}.

🌟 **كيف أساعدك؟ (شرح الخدمات المتاحة):**
1.  **💬 محادثة مباشرة:** أرسل أي سؤال وسأجيبك بذكاء.
2.  **🎨 إنشاء/✏️ تحرير الصور:** أرسل وصفاً لإنشاء صورة، أو أرسل صورة ووصف تعديل لتحريرها.
3.  **📝 تحليل الصور (OCR):** أرسل صورة تحتوي على نص وسأقوم باستخراجه وتحليله.

**💡 ملاحظة حول المتابعة:**
*لتحقيق أقصى استفادة، يرجى متابعة صفحتنا على فيسبوك! (الدعم اختياري ولا يؤثر على عمل البوت)*

⬇️ **اختر خدمتك من الأزرار أدناه:**"""
    
        send_text_message(recipient_id, welcome_text)
        user_state[recipient_id]['first_time'] = False
    
    if show_full_menu:
        send_menu_after_action(recipient_id, "💡 اختر الخدمة التالية:")


def handle_user_message(sender_id: str, message_text: str):
    """معالجة الرسائل النصية العامة"""
    
    current_state = user_state[sender_id]['state']
    
    # 1. حالات انتظار الوصف (إنشاء/تحرير الصورة)
    if current_state == 'WAITING_IMAGE_PROMPT':
        user_state[sender_id]['state'] = None
        send_text_message(sender_id, "⏳ جاري إنشاء الصورة...")
        
        final_url = AIModels.create_image_ai(message_text)
            
        if final_url:
            send_attachment(sender_id, 'image', final_url)
            send_menu_after_action(sender_id, "✅ تم إنشاء الصورة بنجاح! اختر خدمتك التالية:")
        else:
            send_menu_after_action(sender_id, "⚠️ عذراً، فشل إنشاء الصورة. حاول بوصف آخر.")
        
        return
        
    elif current_state == 'WAITING_EDIT_DESC':
        image_url = user_state[sender_id].pop('pending_url', None)
        user_state[sender_id]['state'] = None
        
        if not image_url:
            send_menu_after_action(sender_id, "⚠️ عذراً، لم أجد رابط الصورة المراد تعديلها.")
            return

        send_text_message(sender_id, "⏳ جاري تحرير الصورة...")
        final_url = AIModels.edit_image_ai(image_url, message_text)
            
        if final_url:
            send_attachment(sender_id, 'image', final_url)
            send_menu_after_action(sender_id, "✅ تم تحرير الصورة بنجاح! اختر خدمتك التالية:")
        else:
            send_menu_after_action(sender_id, "⚠️ عذراً، فشل تحرير الصورة. حاول بوصف تعديل مختلف.")
        
        return
        
    # 2. الدردشة العامة بالذكاء الاصطناعي مع السياق
    history = get_conversation_history(sender_id)
    response = AIModels.grok4(message_text, history)
    
    # يتم إرسال رد الذكاء الاصطناعي متبوعاً بأزرار القائمة الرئيسية (Quick Replies)
    send_menu_after_action(sender_id, response)
    add_conversation_entry(sender_id, message_text, response)
    
def handle_attachment(sender_id: str, attachment: Dict[str, Any]):
    """معالجة المرفقات (صور)"""
    
    attachment_type = attachment.get('type')
    
    if attachment_type == 'image':
        image_url = attachment['payload']['url']
        current_state = user_state[sender_id]['state']

        if current_state == 'WAITING_EDIT_IMAGE':
            user_state[sender_id]['state'] = 'WAITING_EDIT_DESC'
            user_state[sender_id]['pending_url'] = image_url
            send_text_message(sender_id, "✏️ **أرسل وصف التعديل المطلوب الآن:**")
            return

        elif current_state == 'WAITING_OCR_IMAGE_FOR_ANALYSIS':
            user_state[sender_id]['state'] = None
            
            send_text_message(sender_id, "🔍 تم استلام الصورة. جاري استخراج النص...")
            
            extracted_text = AIModels.call_ocr_api(image_url)
            
            # في حالة الخطأ، تم بالفعل إعداد رسالة الخطأ الواضحة في دالة call_ocr_api
            if extracted_text.startswith("❌"): 
                send_menu_after_action(sender_id, extracted_text)
                return

            if extracted_text:
                user_state[sender_id]['last_extracted_text'] = extracted_text
                # يتم عرض الخيارات الثلاثة لـ OCR
                text = f"✅ **تم استخراج النص:**\n{extracted_text[:300]}...\n\n❓ **ماذا تريد أن تفعل بهذا النص؟**"
                
                # خيارات OCR (Button Template لعدم اختفائها)
                buttons = [
                    {"type": "postback", "title": "📝 النص المستخرج فقط", "payload": "OCR_SHOW_TEXT"}, 
                    {"type": "postback", "title": "🌐 ترجمة النص", "payload": "OCR_TRANSLATE"},
                    {"type": "postback", "title": "💡 شرح وتحليل", "payload": "OCR_ANALYZE"},
                ]
                send_button_template(sender_id, text, buttons)
            else:
                send_menu_after_action(sender_id, "❌ فشل استخراج النص من الصورة. حاول بصورة ذات جودة أفضل.")
            
            return
        
        else:
            # إذا أرسل المستخدم صورة دون طلب مسبق (عرض خيارات سريعة)
            text = "📸 لقد أرسلت صورة. اختر ماذا تريد أن تفعل بها:"
            buttons = [
                {"type": "postback", "title": "📝 استخراج النص (OCR)", "payload": "MENU_OCR_START"},
                {"type": "postback", "title": "✏️ تحرير هذه الصورة", "payload": "START_EDIT_FROM_IMG"},
                {"type": "postback", "title": "🔙 القائمة الرئيسية", "payload": "MENU_MAIN"}
            ]
            user_state[sender_id]['pending_url'] = image_url # حفظ الرابط للتحرير/التحليل
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

    # 2. إنشاء صورة
    elif postback_payload == 'MENU_CREATE_IMAGE':
        user_state[sender_id]['state'] = 'WAITING_IMAGE_PROMPT'
        send_text_message(sender_id, "🎨 **أرسل وصف الصورة التي تريد إنشاءها:**")

    # 3. بدء عملية OCR
    elif postback_payload == 'MENU_OCR_START':
        user_state[sender_id]['state'] = 'WAITING_OCR_IMAGE_FOR_ANALYSIS'
        send_text_message(sender_id, "📝 **أرسل الصورة التي تريد استخراج النص وتحليلها:**")
        
    # 4. بدء تحرير صورة من القائمة أو من زر سريع
    elif postback_payload in ['MENU_EDIT_IMAGE', 'START_EDIT_FROM_IMG']:
        image_url = user_state[sender_id].pop('pending_url', None)
        
        if image_url:
            user_state[sender_id]['state'] = 'WAITING_EDIT_DESC'
            user_state[sender_id]['pending_url'] = image_url
            send_text_message(sender_id, "✏️ **أرسل وصف التعديل المطلوب الآن:**")
        else:
            user_state[sender_id]['state'] = 'WAITING_EDIT_IMAGE'
            send_text_message(sender_id, "✏️ **أرسل الصورة التي تريد تحريرها الآن:**")

    # 5. خيارات OCR/التحليل بعد الاستخراج
    elif postback_payload.startswith('OCR_'):
        extracted_text = user_state[sender_id].get('last_extracted_text', '')
        if not extracted_text or extracted_text.startswith("❌"): # تحقق إضافي للخطأ
            send_menu_after_action(sender_id, "❌ انتهت صلاحية النص أو حدث خطأ مسبق. يرجى إرسال الصورة مجدداً.")
            return

        send_text_message(sender_id, "⏳ جاري المعالجة...")
        
        response_text = ""
        
        if postback_payload == 'OCR_SHOW_TEXT':
            # تنفيذ طلب المستخدم: استخراج النص فقط
            response_text = f"📝 **النص المستخرج كاملاً:**\n\n{extracted_text[:1800]}"
            
        elif postback_payload == 'OCR_TRANSLATE':
            # تحديد اللغة الهدف للترجمة بناءً على وجود الأحرف العربية
            is_arabic = any('\u0600' <= char <= '\u06FF' for char in extracted_text[:100])
            target_lang = "العربية" if not is_arabic else "الإنجليزية"
            
            prompt = f"ترجم النص التالي إلى {target_lang} بشكل دقيق:\n\n{extracted_text}"
            translation = AIModels.grok4(prompt)
            response_text = f"🌐 **الترجمة إلى {target_lang}:**\n\n{translation}"
            
        elif postback_payload == 'OCR_ANALYZE':
            prompt = f"""حلل النص التالي واشرح محتواه بالتفصيل: 
{extracted_text}
قدم شرحاً مبسطاً ومفيداً للطالب."""
            analysis = AIModels.grok4(prompt)
            response_text = f"💡 **تحليل وشرح النص:**\n\n{analysis}"
            
        send_menu_after_action(sender_id, response_text)

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
                
                # أ. معالجة الرسائل النصية
                if messaging_event.get('message') and messaging_event['message'].get('text'):
                    message = messaging_event['message']
                    
                    if message.get('quick_reply'):
                        handle_postback(sender_id, message['quick_reply']['payload'])
                    else:
                        handle_user_message(sender_id, message['text'].strip())
                
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
    # استخدام المنفذ 8080 افتراضياً، سيتم استبداله بـ Gunicorn في بيئة الإنتاج
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))
