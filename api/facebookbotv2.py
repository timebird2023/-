import os
import json
import requests
import re
import time
import io
import tempfile
import threading
from flask import Flask, request
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import logging
import sqlite3
from datetime import datetime
# استيراد مكتبات معالجة الملفات والصيغ الرياضية
try:
    from PIL import Image
    import PyPDF2
    import docx
    import sympy as sp
    # لا يمكن استخدام scipy/numpy مباشرة في بيئة بسيطة مثل Flask على Vercel/Render
except ImportError as e:
    logging.warning(f"⚠️ مكتبات متقدمة مفقودة (PIL/PyPDF2/docx/sympy). قد تفشل بعض الميزات المتقدمة. {e}")


# ====================================================================
# 📚 الإعدادات الأساسية
# ====================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 🔑 رمز الوصول لصفحة فيسبوك (من الطلب السابق)
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'boykta2025')
PAGE_ACCESS_TOKEN = "EAAYa4tM31ZAMBPZBZBIKE5832L12MHi04tWJOFSv4SzTY21FZCgc6KSnNvkSFDZBZAbUzDGn7NDSxzxERKXx57ZAxTod7B0mIyqfwpKF1NH8vzxu2Ahn16o7OCLSZCG8SvaJ3eDyFJPiqYq6z1TXxSb0OxZAF4vMY3vO20khvq6ZB1nCW4S6se2sxTCVezt1YiGLEZAWeK9"

# معلومات المطور
DEVELOPER_NAME = "younes laldji"
AI_ASSISTANT_NAME = "بويكتا"

# واجهات الذكاء الاصطناعي
GROK_API_URL = 'https://sii3.top/api/grok4.php'
OCR_API = 'https://sii3.top/api/OCR.php'
NANO_BANANA_API = 'https://sii3.top/api/nano-banana.php' # لإنشاء وتحرير الصور
GPT_IMAGER_API = 'https://sii3.top/api/gpt-img.php' # لتحرير الصور
DARK_CODE_API = 'https://sii3.top/api/DarkCode.php' # للبرمجة

# الذاكرة المؤقتة وحالة المستخدم
user_state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {'state': None, 'first_time': True, 'pending_url': None, 'edit_prompt': None})
in_memory_conversations: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
memory_lock = threading.Lock()

app = Flask(__name__)

# ====================================================================
# 🗄️ إدارة قاعدة البيانات المصغرة (SQLite)
# ====================================================================

class Database:
    def __init__(self):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect('messenger_bot.db', check_same_thread=False)
        self.create_tables()
        logger.info("✅ تم إعداد قاعدة البيانات لـ Messenger")

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                first_name TEXT,
                message_count INTEGER DEFAULT 0,
                joined_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                user_id TEXT,
                message TEXT,
                response TEXT,
                timestamp TEXT
            )
        ''')
        self.conn.commit()

    def add_or_update_user(self, user_id: str, first_name: str):
        try:
            with self.lock:
                cursor = self.conn.cursor()
                now = datetime.now().isoformat()
                cursor.execute('''
                    INSERT INTO users (user_id, first_name, joined_at, message_count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(user_id) DO UPDATE SET
                        first_name = excluded.first_name,
                        message_count = message_count + 1
                ''', (user_id, first_name, now))
                self.conn.commit()
        except Exception as e:
            logger.warning(f"DB user operation failed: {e}")

db = Database()

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
# 🧠 منطق الذكاء الاصطناعي والخدمات المتقدمة (مُعدّل من كود Telegram)
# ====================================================================

# دوال السياق (تستخدم الذاكرة المؤقتة فقط هنا لسهولة الدمج)
def get_conversation_history(user_id: str, limit: int = 5) -> List[Tuple[str, str]]:
    history = in_memory_conversations.get(user_id, [])
    return history[-limit:] if history else []

def add_conversation_entry(user_id: str, message: str, response: str):
    in_memory_conversations[user_id].append((message, response))
    if len(in_memory_conversations[user_id]) > 10:
        in_memory_conversations[user_id] = in_memory_conversations[user_id][-10:]
    # إضافة إلى قاعدة البيانات لضمان الثبات
    try:
        db.add_conversation(user_id, message, response)
    except Exception as e:
        logger.warning(f"DB conversation save failed: {e}")

# دوال الخدمات المتقدمة
class AIModels:
    @staticmethod
    def _clean_response(text: str) -> str:
        """تنظيف الردود من JSON والرموز غير المرغوب فيها (مُعاد من كود Telegram)"""
        try:
            # ... (منطق تنظيف الردود من كود Telegram)
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
        """استدعاء OCR API لاستخراج النص من الصورة"""
        try:
            payload = {"link": image_url, "text": instruction}
            response = requests.post(OCR_API, data=payload, timeout=60)
            if response.ok:
                result_json = response.json()
                extracted_text = result_json.get('response', '')
                if not extracted_text:
                    return ""
                return extracted_text.replace('\\n', '\n').strip()
            else:
                return f"❌ خطأ في OCR API (رمز: {response.status_code})"
        except Exception as e:
            logger.error(f"OCR Exception: {e}")
            return "❌ فشل الاتصال بخدمة OCR."

    @staticmethod
    def create_image_ai(prompt: str) -> Optional[str]:
        """استدعاء API لإنشاء الصور (Nano-Banana)"""
        try:
            english_prompt = AIModels._translate_to_english(prompt)
            payload = {'text': english_prompt}
            response = requests.post(NANO_BANANA_API, data=payload, timeout=60)
            if response.ok:
                data = response.json()
                return data.get('url') or data.get('image')
            else:
                logger.error(f"Image Create API Error: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Image Create Exception: {e}")
            return None

    @staticmethod
    def edit_image_ai(image_url: str, edit_desc: str) -> Optional[str]:
        """استدعاء API لتحرير الصور (Nano-Banana + GPT-Imager)"""
        english_desc = AIModels._translate_to_english(edit_desc)

        # 1. محاولة Nano-Banana أولاً (أسرع)
        try:
            payload = {'text': english_desc, 'links': image_url}
            response = requests.post(NANO_BANANA_API, data=payload, timeout=60)
            if response.ok:
                data = response.json()
                if data.get('url') or data.get('image'):
                    return data.get('url') or data.get('image')
        except Exception:
            logger.warning("Nano-Banana edit failed, falling back to GPT-Imager")
            
        # 2. محاولة GPT-Imager
        try:
            payload = {'text': english_desc, 'link': image_url}
            response = requests.post(GPT_IMAGER_API, data=payload, timeout=60)
            if response.ok:
                data = response.json()
                return data.get('image') or data.get('url')
        except Exception as e:
            logger.error(f"Image Edit Exception: {e}")
            return None
        
        return None

    @staticmethod
    def solve_math_problem(problem: str) -> str:
        """حل المسائل الرياضية باستخدام SymPy (مُعدّل)"""
        try:
            if 'sp' not in globals():
                return "⚠️ خدمة حل المعادلات غير متاحة بسبب نقص مكتبة SymPy."

            x = sp.Symbol('x')
            
            # محاولة حل المعادلة مباشرة عبر الذكاء الاصطناعي لضمان التنسيق
            ai_prompt = f"حل المعادلة أو التعبير الرياضي التالي خطوة بخطوة. اكتب الحل بتنسيق واضح ومفهوم (استخدم (a/b) بدلاً من الكسور و √ بدلاً من الجذر):\n\n{problem}"
            solution = AIModels.grok4(ai_prompt)
            
            return solution
        except Exception as e:
            logger.error(f"Math solving error: {e}")
            return "حدث خطأ أثناء معالجة المسألة الرياضية."

    @staticmethod
    def extract_text_from_file(file_content: bytes, file_name: str) -> str:
        """استخراج النص من الملفات (PDF/DOCX/TXT)"""
        try:
            if 'PyPDF2' not in globals() and 'docx' not in globals():
                 return "⚠️ خدمة استخراج النص من الملفات غير متاحة (نقص المكتبات)."
                 
            file_name = file_name.lower()
            file_stream = io.BytesIO(file_content)

            if file_name.endswith('.pdf'):
                pdf_reader = PyPDF2.PdfReader(file_stream)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            elif file_name.endswith('.docx') or file_name.endswith('.doc'):
                doc = docx.Document(file_stream)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
            elif file_name.endswith('.txt'):
                text = file_content.decode('utf-8', errors='ignore')
            else:
                return ""
            
            return text.strip()[:4000]
        except Exception as e:
            logger.error(f"File extraction error: {e}")
            return "❌ فشل استخراج النص من الملف."

    @staticmethod
    def call_dark_code(query: str) -> str:
        """استدعاء مساعد البرمجة DarkCode"""
        try:
            response = requests.post(DARK_CODE_API, json={'text': query}, timeout=45)
            if response.ok:
                return AIModels._clean_response(response.text)
            else:
                return f"❌ خطأ في DarkCode API (رمز: {response.status_code})"
        except Exception:
            return "💥 فشل الاتصال بخدمة البرمجة."

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
                if result and len(result) > 0 and len(result[0]) > 0:
                    return ''.join([item[0] for item in result[0] if item[0]])
        except Exception:
            pass
        return text

# ====================================================================
# 🎯 منطق معالجة الرسائل والأحداث
# ====================================================================

def send_welcome_and_guidance(recipient_id: str, first_name: str, show_full_menu=True):
    """إرسال رسالة ترحيب وشرح للمستخدم الجديد"""
    
    if user_state[recipient_id]['first_time']:
        # رسالة الترحيب والشرح (للمستخدم الجديد)
        welcome_text = f"""👋 أهلاً بك يا **{first_name}**! أنا {AI_ASSISTANT_NAME}.

🌟 **كيف أساعدك؟ (شرح الخدمات):**
1.  **💬 محادثة مباشرة:** أرسل أي سؤال وسأجيبك بذكاء (لأي مادة أو موضوع).
2.  **🎨 إنشاء/✏️ تحرير الصور:** أرسل وصفاً وسأنشئ صورة، أو أرسل صورة ووصف تعديل وسأقوم بتحريرها.
3.  **📝 تحليل الصور (OCR):** أرسل صورة تحتوي على نص وسأقوم باستخراجه وتحليله وحل أي مسائل رياضية به.
4.  **📄 معالجة الملفات:** أرسل ملف PDF/DOCX/TXT وسألخص محتواه أو أستخرج منه المعلومات.
5.  **🔢 حل المعادلات:** اكتب سؤالك الرياضي مباشرة (مثال: $2x+5=15$).
6.  **💻 مساعدة البرمجة:** اطلب مني كتابة أو شرح أي كود.

**💡 ملاحظة حول المتابعة:**
لتحقيق أقصى استفادة، يرجى متابعة صفحتنا على فيسبوك!
*رغم أنني لا أستطيع إجبارك على الإعجاب أو المتابعة قبل الاستخدام (لأن فيسبوك لا يسمح بذلك بشكل مباشر في هذا السياق)، إلا أن دعمك يساعدني في الاستمرار!*

⬇️ **اختر خدمتك من الأزرار أدناه:**"""
    
        send_text_message(recipient_id, welcome_text)
        user_state[recipient_id]['first_time'] = False
    
    if show_full_menu:
        # عرض القائمة الرئيسية (Quick Replies)
        send_menu_after_action(recipient_id, "💡 اختر الخدمة التالية:")


def handle_user_message(sender_id: str, message_text: str):
    """معالجة الرسائل النصية العامة"""
    
    current_state = user_state[sender_id]['state']
    
    # 1. حالات انتظار الوصف (صورة أو تحرير)
    if current_state == 'WAITING_IMAGE_PROMPT':
        user_state[sender_id]['state'] = None
        send_text_message(sender_id, "⏳ جاري إنشاء الصورة...")
        
        final_url = AIModels.create_image_ai(message_text)
            
        if final_url:
            send_attachment(sender_id, 'image', final_url)
            send_menu_after_action(sender_id, "✅ تم إنشاء الصورة بنجاح! اختر خدمتك التالية:")
        else:
            send_menu_after_action(sender_id, "⚠️ عذراً، فشل إنشاء الصورة.")
        
        return
        
    elif current_state == 'WAITING_EDIT_DESC':
        # حالة تحرير الصورة بعد استلام الرابط
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
            send_menu_after_action(sender_id, "⚠️ عذراً، فشل تحرير الصورة.")
        
        return

    # 2. تحليل الرسائل الخاصة (رياضيات، كود، محادثة)
    
    # محاولة حل المعادلات الرياضية مباشرة
    if any(op in message_text for op in ['=', '+', '-', '*', '/', 'x', 'y']) and any(c.isdigit() for c in message_text):
        response = AIModels.solve_math_problem(message_text)
        send_menu_after_action(sender_id, response)
        add_conversation_entry(sender_id, message_text, response)
        return

    # محاولة التعامل مع طلبات البرمجة
    if any(keyword in message_text.lower() for keyword in ['كود', 'python', 'java', 'html', 'برمجة', 'دالة']):
        response = AIModels.call_dark_code(message_text)
        send_menu_after_action(sender_id, response)
        add_conversation_entry(sender_id, message_text, response)
        return
        
    # 3. الدردشة العامة بالذكاء الاصطناعي مع السياق
    history = get_conversation_history(sender_id)
    response = AIModels.grok4(message_text, history)
    
    # يتم إرسال رد الذكاء الاصطناعي متبوعاً بأزرار القائمة الرئيسية (Quick Replies)
    send_menu_after_action(sender_id, response)
    add_conversation_entry(sender_id, message_text, response)
    
def handle_attachment(sender_id: str, attachment: Dict[str, Any]):
    """معالجة المرفقات (صور، ملفات)"""
    
    attachment_type = attachment.get('type')
    
    if attachment_type == 'image':
        image_url = attachment['payload']['url']
        current_state = user_state[sender_id]['state']

        if current_state == 'WAITING_EDIT_IMAGE':
            # حالة انتظار الصورة لتحريرها ثم طلب الوصف
            user_state[sender_id]['state'] = 'WAITING_EDIT_DESC'
            user_state[sender_id]['pending_url'] = image_url
            send_text_message(sender_id, "✏️ **أرسل وصف التعديل المطلوب الآن:**")
            return

        elif current_state == 'WAITING_OCR_IMAGE_FOR_ANALYSIS':
            # حالة تحليل الصورة بعد طلب OCR
            user_state[sender_id]['state'] = None
            
            send_text_message(sender_id, "🔍 تم استلام الصورة. جاري استخراج النص...")
            extracted_text = AIModels.call_ocr_api(image_url)
            
            if extracted_text and not extracted_text.startswith("❌"):
                user_state[sender_id]['last_extracted_text'] = extracted_text
                text = f"✅ **تم استخراج النص:**\n{extracted_text[:300]}...\n\n❓ **ماذا تريد أن تفعل بهذا النص؟**"
                
                # خيارات OCR (Button Template لعدم اختفائها)
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
            user_state[sender_id]['pending_url'] = image_url # حفظ الرابط للتحرير/التحليل
            send_button_template(sender_id, text, buttons)
            
    elif attachment_type == 'file':
        # معالجة الملفات (PDF, DOCX, TXT)
        file_url = attachment['payload']['url']
        file_name = attachment['title']
        
        # لا يمكننا تنزيل الملف مباشرة من الرابط دون إعدادات متقدمة/خادم، لكن سنحاكي الاستخراج هنا
        try:
            # محاولة تنزيل الملف (افتراضياً لن ينجح في بيئة سريعة)
            file_content = requests.get(file_url, timeout=30).content
            
            send_text_message(sender_id, "🔍 جاري استخراج النص من الملف...")
            extracted_text = AIModels.extract_text_from_file(file_content, file_name)
            
            if extracted_text and extracted_text.strip() != "❌ فشل استخراج النص من الملف.":
                user_state[sender_id]['last_extracted_text'] = extracted_text
                text = f"✅ **تم استخراج النص من الملف ({file_name}):**\n{extracted_text[:500]}...\n\n❓ **ماذا تريد أن تفعل بهذا النص؟**"
                
                buttons = [
                    {"type": "postback", "title": "💡 شرح وتحليل", "payload": "OCR_ANALYZE"},
                    {"type": "postback", "title": "📝 النص كاملاً", "payload": "OCR_SHOW_TEXT"},
                ]
                send_button_template(sender_id, text, buttons)
            else:
                send_menu_after_action(sender_id, f"❌ فشل استخراج النص من الملف: {file_name}")

        except Exception as e:
            logger.error(f"File handling error: {e}")
            send_menu_after_action(sender_id, "⚠️ عذراً، فشلت معالجة الملف (تأكد من نوع الملف وحجمه).")
    
    else:
        send_menu_after_action(sender_id, "⚠️ لا أستطيع حالياً معالجة هذا النوع من المرفقات. أرسل صورة أو ملف نصي/وثائقي فقط.")

def handle_postback(sender_id: str, postback_payload: str):
    """معالجة ضغط الأزرار (Postback)"""
    
    user_state[sender_id]['state'] = None
    
    # 1. القائمة الرئيسية/الترحيب
    if postback_payload in ['GET_STARTED_PAYLOAD', 'MENU_MAIN', 'MENU_NEW_CHAT']:
        # التحقق من اسم المستخدم لإرسال رسالة ترحيب مخصصة
        try:
            user_info = requests.get(
                f"https://graph.facebook.com/v19.0/{sender_id}",
                params={"access_token": PAGE_ACCESS_TOKEN, "fields": "first_name"}
            ).json()
            first_name = user_info.get('first_name', 'مستخدم')
            db.add_or_update_user(sender_id, first_name)
        except Exception:
            first_name = "مستخدم"
            
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
        image_url = user_state[sender_id].pop('pending_url', None) # قد يكون موجوداً إذا أرسل الصورة أولاً
        
        if image_url:
            # الصورة موجودة -> اطلب الوصف
            user_state[sender_id]['state'] = 'WAITING_EDIT_DESC'
            user_state[sender_id]['pending_url'] = image_url
            send_text_message(sender_id, "✏️ **أرسل وصف التعديل المطلوب الآن:**")
        else:
            # الصورة غير موجودة -> اطلب الصورة أولاً
            user_state[sender_id]['state'] = 'WAITING_EDIT_IMAGE'
            send_text_message(sender_id, "✏️ **أرسل الصورة التي تريد تحريرها الآن:**")

    # 5. خيارات OCR/التحليل بعد الاستخراج
    elif postback_payload.startswith('OCR_'):
        extracted_text = user_state[sender_id].get('last_extracted_text', '')
        if not extracted_text:
            send_menu_after_action(sender_id, "❌ انتهت صلاحية النص. يرجى إرسال الصورة/الملف مجدداً.")
            return

        send_text_message(sender_id, "⏳ جاري المعالجة...")
        
        response_text = ""
        
        if postback_payload == 'OCR_SHOW_TEXT':
            response_text = f"📝 **النص المستخرج كاملاً:**\n\n{extracted_text[:1800]}..."
            
        elif postback_payload == 'OCR_TRANSLATE':
            # تحديد لغة الترجمة (افتراضياً إلى العربية إذا كان النص إنجليزي/عربي)
            is_arabic = any('\u0600' <= char <= '\u06FF' for char in extracted_text[:100])
            target_lang = "العربية" if not is_arabic else "الإنجليزية"
            
            prompt = f"ترجم النص التالي إلى {target_lang} بشكل دقيق:\n\n{extracted_text}"
            translation = AIModels.grok4(prompt)
            response_text = f"🌐 **الترجمة إلى {target_lang}:**\n\n{translation}"
            
        elif postback_payload == 'OCR_ANALYZE':
            prompt = f"""حلل النص التالي واشرح محتواه بالتفصيل (إذا كان تمريناً فقدم الحل، وإذا كان نصاً فقدم شرحاً): 
{extracted_text}

**قواعد التنسيق الرياضي:**
✓ وضوح التنسيق: اكتب جميع المعادلات والنتائج بتنسيق واضح ومفهوم
✓ استخدم الرموز البديلة: (a/b) بدلاً من الكسور، و√x بدلاً من الجذر"""
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
                    message = messaging_event['message']
                    
                    # 💡 يتم هنا التعرف على Quick Reply ومعالجته كـ Postback
                    if message.get('quick_reply'):
                        handle_postback(sender_id, message['quick_reply']['payload'])
                    else:
                        handle_user_message(sender_id, message['text'].strip())
                
                # ب. معالجة المرفقات (Attachment)
                elif messaging_event.get('message') and messaging_event['message'].get('attachments'):
                    for attachment in messaging_event['message']['attachments']:
                        handle_attachment(sender_id, attachment)
                
                # ج. معالجة ضغط الأزرار (Postback) - لا يذهب للذكاء الاصطناعي
                elif messaging_event.get('postback'):
                    handle_postback(sender_id, messaging_event['postback']['payload'])
                
                # د. معالجة حدث البدء الأول (Get Started)
                elif messaging_event.get('postback', {}).get('payload') == 'GET_STARTED_PAYLOAD':
                    handle_postback(sender_id, 'GET_STARTED_PAYLOAD')

        return 'OK', 200

if __name__ == '__main__':
    # التأكد من عمل الدوال عند التشغيل
    try:
        from web_server import start_web_server
        start_web_server()
    except ImportError:
        logger.warning("Web server module not found, skipping.")
    except Exception as e:
        logger.warning(f"Failed to start web server: {e}")
        
    logger.info("🚀 بدء تشغيل بوت فيسبوك ماسنجر - بويكتا")
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 3000))
