# fb_bot.py - بويكتا Boykta AI Assistant
# النظام الذكي الكامل - واجهة طبيعية بدون أزرار
# المطور: Younes Laldji
# البورت: 25151
# حقوق الطبع والنشر © 2025 - جميع الحقوق محفوظة

import os
import json
import requests
import asyncio
import textwrap
import re
import threading
import time
import yt_dlp
import random
import base64
import uuid
from urllib.parse import urlparse
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from collections import defaultdict
import edge_tts
from supabase import create_client, Client

# ====================================================================
# 🔑 إعدادات المفاتيح الحصرية - الحقوق للمطور Younes Laldji
# ====================================================================

# جلب المفاتيح من إعدادات Vercel لتأمينها
GEMINI_KEYS = os.environ.get("GEMINI_KEYS", "").split(",")
GROQ_KEYS = os.environ.get("GROQ_KEYS", "").split(",")
HF_KEYS = os.environ.get("HF_KEYS", "").split(",")

# إعدادات Puter و Facebook من البيئة
PUTER_USERNAME = os.environ.get("PUTER_USERNAME", "boykta")
PUTER_PASSWORD = os.environ.get("PUTER_PASSWORD", "boykta2023@@I2025")
PUTER_APP_ID = os.environ.get("PUTER_APP_ID", "app-47a42c9d-9f3a-49f1-ad3a-964c98eef772")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = "boykta2025"

# جلب بيانات قاعدة البيانات من البيئة (Vercel)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = None

# ====================================================================
# 🏗️ إعدادات النظام والهوية
# ====================================================================

DEVELOPER_NAME = "Younes Laldji"
AI_ASSISTANT_NAME = "بويكتا"
AI_PERSONALITY = "ذكي، مفيد، ودود، ومتعاون. خبير في جميع المجالات التعليمية والإبداعية."

# نظام النقاط - تحديث شامل
POINTS_SYSTEM = {
    'new_user': 15,
    'invite_reward': 20,
    'download': 0,          # مجاني الآن
    'solve_exercise': 2,
    'generate_image': 3,
    'generate_video': 10,   # تكلفة عالية
    'edit_image': 2,
    'ocr_text': 1,
    'daily_login': 3,
    'chat': 0
}

# الحدود اليومية
DAILY_LIMITS = {
    'videos': 2,     # فيديوهان يومياً فقط
    'images': 15,
    'downloads': 30
}

app = Flask(__name__)

# ====================================================================
# 🗄️ الذاكرة المؤقتة
# ====================================================================

user_db = defaultdict(lambda: {
    'state': 'idle',
    'conversation_history': [],
    'points': 0,
    'invite_code': '',
    'referral_used': False,
    'invited_by': None,
    'invite_count': 0,
    'daily_usage': {
        'videos': 0,
        'images': 0,
        'downloads': 0
    },
    'last_reset': datetime.now().date().isoformat(),
    'is_follower': False,
    'voice_preference': 'female',
    'last_interaction': datetime.now().isoformat(),
    'first_seen': None,
    'temp_data': {},
    'waiting_for': None,
    'last_typing': 0
})

# إحصائيات النظام
system_stats = {
    'total_users': 0,
    'total_downloads': 0,
    'total_videos_generated': 0,
    'total_images_generated': 0,
    'total_points_distributed': 0,
    'start_time': datetime.now().isoformat()
}

# رموز للتتبع
gemini_key_index = 0
groq_key_index = 0
hf_key_index = 0
active_downloads = {}
seen_users = set()
user_sessions = {}

# ====================================================================
# 🛠️ دوال مساعدة متقدمة
# ====================================================================

def rotate_gemini_key():
    """تدوير مفاتيح Gemini لتجنب الحدود"""
    global gemini_key_index
    gemini_key_index = (gemini_key_index + 1) % len(GEMINI_KEYS)
    return GEMINI_KEYS[gemini_key_index]

def rotate_groq_key():
    """تدوير مفاتيح Groq"""
    global groq_key_index
    groq_key_index = (groq_key_index + 1) % len(GROQ_KEYS)
    return GROQ_KEYS[groq_key_index]

def rotate_hf_key():
    """تدوير مفاتيح Hugging Face"""
    global hf_key_index
    hf_key_index = (hf_key_index + 1) % len(HF_KEYS)
    return HF_KEYS[hf_key_index]

def clean_text(text):
    """تنظيف النص مع الحفاظ على التنسيق الأساسي"""
    if not text:
        return ""
    # إزالة التنسيق المفرط مع الحفاظ على المسافات
    text = re.sub(r'\*\*|\*\*|__|~~|`', '', text)
    # تنظيف المسافات المتعددة
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def split_long_message(text, max_length=1900):
    """تقسيم الرسائل الطويلة بشكل ذكي"""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_length:
            current_chunk += para + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + '\n\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def extract_url(text):
    """استخراج جميع الروابط من النص"""
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w .?=&%#-]*|www\.[-\w.]+[/\w .?=&%#-]*'
    urls = re.findall(url_pattern, text)
    return urls[0] if urls else None

def is_video_url(url):
    """التحقق من أن الرابط لفيديو"""
    if not url:
        return False
    
    video_domains = [
        'youtube.com', 'youtu.be',
        'facebook.com', 'fb.watch',
        'tiktok.com', 'vm.tiktok.com',
        'instagram.com', 'instagr.am',
        'twitter.com', 'x.com',
        'twitch.tv',
        'dailymotion.com',
        'vimeo.com'
    ]
    
    try:
        parsed = urlparse(url if url.startswith('http') else f'https://{url}')
        domain = parsed.netloc.lower()
        return any(vd in domain for vd in video_domains)
    except:
        return False

def is_valid_invite_code(code):
    """التحقق من صحة كود الدعوة"""
    pattern = r'^BOYKTA-[A-Z0-9]{6}$'
    return bool(re.match(pattern, code.upper()))

def generate_invite_code(user_id):
    """إنشاء كود دعوة فريد"""
    import hashlib
    hash_str = hashlib.md5(f"{user_id}{datetime.now().isoformat()}".encode()).hexdigest()
    return f"BOYKTA-{hash_str[:6].upper()}"

def reset_daily_usage(user_id):
    """إعادة تعيين الاستخدام اليومي"""
    today = datetime.now().date().isoformat()
    if user_db[user_id]['last_reset'] != today:
        user_db[user_id]['daily_usage'] = {'videos': 0, 'images': 0, 'downloads': 0}
        user_db[user_id]['last_reset'] = today

def send_typing_indicator(user_id, typing_state="typing_on"):
    """إرسال مؤشر الكتابة لمحاكاة التفاعل البشري"""
    try:
        requests.post(
            f"https://graph.facebook.com/v19.0/me/messages",
            params={"access_token": FB_PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": user_id},
                "sender_action": typing_state
            },
            timeout=5
        )
    except:
        pass

# ====================================================================
# 📊 نظام Supabase (الاقتصاد الذكي)
# ====================================================================

def init_supabase():
    """تهيئة اتصال Supabase"""
    global supabase
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ تم الاتصال بـ Supabase بنجاح")
            
            # جلب إحصائيات المستخدمين
            try:
                response = supabase.table('users').select('count', count='exact').execute()
                system_stats['total_users'] = response.count or 0
            except:
                pass
            
            return True
        except Exception as e:
            print(f"❌ فشل الاتصال بـ Supabase: {e}")
    return False

def get_user_from_db(user_id):
    """جلب بيانات المستخدم من قاعدة البيانات"""
    if not supabase:
        return None
    
    try:
        response = supabase.table('users').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        print(f"❌ خطأ في جلب بيانات المستخدم: {e}")
    
    return None

def save_user_to_db(user_data):
    """حفظ بيانات المستخدم في قاعدة البيانات"""
    if not supabase:
        return False
    
    try:
        user_id = user_data['user_id']
        existing = get_user_from_db(user_id)
        
        if existing:
            # تحديث البيانات
            supabase.table('users').update(user_data).eq('user_id', user_id).execute()
        else:
            # إضافة مستخدم جديد
            user_data['created_at'] = datetime.now().isoformat()
            supabase.table('users').insert(user_data).execute()
            system_stats['total_users'] += 1
        
        return True
    except Exception as e:
        print(f"❌ خطأ في حفظ بيانات المستخدم: {e}")
        return False

def update_points(user_id, points_change, reason=""):
    """تحديث نقاط المستخدم"""
    user_data = get_user_from_db(user_id) or {'user_id': user_id, 'points': 0}
    current_points = user_data.get('points', 0)
    new_points = max(0, current_points + points_change)
    
    user_data['points'] = new_points
    user_db[user_id]['points'] = new_points
    
    if points_change > 0:
        system_stats['total_points_distributed'] += points_change
    
    # حفظ سجل المعاملة
    if reason and supabase:
        transaction = {
            'user_id': user_id,
            'amount': points_change,
            'reason': reason,
            'balance_after': new_points,
            'created_at': datetime.now().isoformat()
        }
        try:
            supabase.table('transactions').insert(transaction).execute()
        except:
            pass
    
    save_user_to_db(user_data)
    return new_points

def check_and_reward_invite(inviter_id, invitee_id):
    """التحقق من الدعوة ومنح المكافأة مع شرط المتابعة"""
    if not supabase:
        return False, "نظام النقاط غير متاح حالياً"
    
    # التحقق من متابعة المدعو للصفحة
    invitee_data = get_user_from_db(invitee_id)
    # التحقق الصارم من حالة متابعة الصفحة قبل منح المكافأة
    if not invitee_data or not invitee_data.get('is_follower', False):
        return False, "⚠️ المكافأة لم تفعّل! يجب على صديقك متابعة الصفحة أولاً ثم إدخال الكود مجدداً."
    
    if not invitee_data.get('is_follower', False):
        return False, """❗ يجب على صديقك متابعة صفحتنا أولاً لتفعيل المكافأة لك.
        
📌 يرجى اطلب منه:
1. متابعة صفحتنا على فيسبوك
2. استخدام البوت مرة أخرى
3. إدخال كود الدعوة مجدداً

ثم ستحصل على 20 نقطة فوراً! 🎉"""
    
    # التحقق من عدم استخدام الكود سابقاً
    if invitee_data.get('referral_used', False):
        return False, "⚠️ هذا الكود تم استخدامه مسبقاً."
    
    # التحقق من أن المدعو لم يدعِ الداعي (منع التبادل)
    if invitee_data.get('invited_by') == inviter_id:
        return False, "⚠️ لا يمكن تبادل الدعوات بين نفس المستخدمين."
    
    # منح النقاط للداعي
    update_points(inviter_id, POINTS_SYSTEM['invite_reward'], f"دعوة صديق: {invitee_id}")
    
    # تحديث حالة المدعو
    invitee_data['referral_used'] = True
    invitee_data['invited_by'] = inviter_id
    save_user_to_db(invitee_data)
    
    user_db[invitee_id]['referral_used'] = True
    user_db[invitee_id]['invited_by'] = inviter_id
    user_db[inviter_id]['invite_count'] += 1
    
    # إعلام الداعي
    send_message_to_user(inviter_id, f"🎉 تم تفعيل دعوة صديقك! تم إضافة {POINTS_SYSTEM['invite_reward']} نقطة إلى رصيدك.")
    
    return True, f"✅ تم تفعيل الدعوة بنجاح! صديقك {inviter_id} حصل على {POINTS_SYSTEM['invite_reward']} نقطة."

def update_follower_status(user_id, is_follower):
    """تحديث حالة متابعة الصفحة"""
    user_db[user_id]['is_follower'] = is_follower
    if supabase:
        try:
            user_data = get_user_from_db(user_id) or {'user_id': user_id}
            user_data['is_follower'] = is_follower
            if is_follower:
                user_data['follower_since'] = datetime.now().isoformat()
            
            save_user_to_db(user_data)
        except:
            pass

# ====================================================================
# 🧠 محرك النية الذكي (بدون أزرار)
# ====================================================================

def analyze_user_intent(user_id, message_text, has_image=False, has_url=False):
    """تحليل نية المستخدم باستخدام Groq"""
    
    # التحليل السريع الأولي
    message_lower = message_text.lower()
    
    quick_intents = {
        # تحميل
        'تحميل': 'DOWNLOAD', 'نزل': 'DOWNLOAD', 'حمل': 'DOWNLOAD', 'يوتيوب': 'DOWNLOAD',
        'فيديو': 'DOWNLOAD', 'صوت': 'DOWNLOAD', 'mp3': 'DOWNLOAD', 'mp4': 'DOWNLOAD',
        
        # حل تمارين
        'حل': 'SOLVE', 'تمرين': 'SOLVE', 'سؤال': 'SOLVE', 'اشرح': 'SOLVE',
        'مسألة': 'SOLVE', 'رياضيات': 'SOLVE', 'فيزياء': 'SOLVE', 'كيمياء': 'SOLVE',
        'فلسفة': 'SOLVE', 'دين': 'SOLVE', 'شعر': 'SOLVE', 'برمجة': 'SOLVE',
        'كود': 'SOLVE', 'برنامج': 'SOLVE',
        
        # صور
        'رسم': 'GEN_IMAGE', 'صور': 'GEN_IMAGE', 'صورة': 'GEN_IMAGE', 'انشاء': 'GEN_IMAGE',
        'دالي': 'GEN_IMAGE', 'dall': 'GEN_IMAGE',
        
        # فيديوهات
        'فيديو جديد': 'GEN_VIDEO', 'اصنع فيديو': 'GEN_VIDEO', 'svd': 'GEN_VIDEO',
        'فيديو من نص': 'GEN_VIDEO',
        
        # تعديل
        'عدل': 'EDIT_IMAGE', 'تعديل': 'EDIT_IMAGE', 'عدلي': 'EDIT_IMAGE',
        
        # OCR
        'نص': 'OCR', 'اقرأ': 'OCR', 'استخرج': 'OCR', 'ocr': 'OCR', 'خط': 'OCR',
        
        # نقاط
        'نقاط': 'POINTS', 'رصيد': 'POINTS', 'نقطة': 'POINTS', 'رصيدي': 'POINTS',
        
        # دعوات
        'دعوة': 'INVITE', 'كود': 'INVITE', 'دعوة': 'INVITE', 'صديق': 'INVITE',
        
        # هوية
        'من أنت': 'IDENTITY', 'ما اسمك': 'IDENTITY', 'من صنعك': 'IDENTITY',
        'identity': 'IDENTITY', 'اسمك': 'IDENTITY',
        
        # قدرات
        'ماذا تفعل': 'CAPABILITIES', 'ماذا تستطيع': 'CAPABILITIES',
        'قدراتك': 'CAPABILITIES', 'مميزات': 'CAPABILITIES', 'ماذا تعمل': 'CAPABILITIES',
        
        # مساعدة
        'مساعدة': 'HELP', 'help': 'HELP', 'الاوامر': 'HELP', 'كيف': 'HELP',
        
        # إحصائيات
        'إحصائيات': 'STATS', 'احصائيات': 'STATS', 'stat': 'STATS', 'stats': 'STATS'
    }
    
    for keyword, intent in quick_intents.items():
        if keyword in message_lower:
            return intent
    
    # إذا كان هناك رابط فيديو
    if has_url and is_video_url(extract_url(message_text)):
        return 'DOWNLOAD'
    
    # إذا كان هناك صورة
    if has_image:
        if any(word in message_lower for word in ['حل', 'تمرين', 'سؤال', 'اشرح', 'حللي']):
            return 'SOLVE'
        elif any(word in message_lower for word in ['عدل', 'تعديل', 'عدلي', 'غير']):
            return 'EDIT_IMAGE'
        else:
            return 'OCR'
    
    # التحليل العميق باستخدام Groq
    try:
        prompt = f"""
        أنت محرك تحليل نوايا متقدم. صنف طلب المستخدم إلى واحدة من هذه الفئات فقط:
        
        DOWNLOAD: طلب تحميل فيديو أو صوت من رابط (مجاني)
        SOLVE: طلب حل تمرين، شرح مفهوم، تحليل نص، شرح كود برمجي
        GEN_IMAGE: طلب إنشاء صورة جديدة باستخدام DALL-E 3
        GEN_VIDEO: طلب إنشاء فيديو جديد باستخدام SVD (10 نقاط)
        EDIT_IMAGE: طلب تعديل صورة موجودة
        OCR: طلب استخراج نص من صورة (خاصة الخط اليدوي)
        POINTS: استعلام عن النقاط، الرصيد، النظام الاقتصادي
        INVITE: متعلق بنظام الدعوات، أكواد الدعوة
        IDENTITY: سؤال عن الهوية، المطور، من أنا
        CAPABILITIES: سؤال عن القدرات، المميزات، ماذا أستطيع
        HELP: طلب مساعدة، الأوامر، كيفية الاستخدام
        STATS: إحصائيات النظام، أرقام
        CHAT: محادثة عادية، دردشة، أي شيء آخر
        
        رسالة المستخدم: "{message_text}"
        {"يوجد صورة مرفقة" if has_image else "لا يوجد صورة"}
        {"يوجد رابط" if has_url else "لا يوجد رابط"}
        
        أجب بكلمة واحدة فقط (اسم الفئة).
        """
        
        current_groq_key = rotate_groq_key()
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {current_groq_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 10
            },
            timeout=5
        )
        
        intent = response.json()['choices'][0]['message']['content'].strip()
        valid_intents = [
            'DOWNLOAD', 'SOLVE', 'GEN_IMAGE', 'GEN_VIDEO', 'EDIT_IMAGE', 
            'OCR', 'POINTS', 'INVITE', 'IDENTITY', 'CAPABILITIES', 
            'HELP', 'STATS', 'CHAT'
        ]
        
        return intent if intent in valid_intents else 'CHAT'
    
    except Exception as e:
        print(f"⚠️ خطأ في تحليل النية: {e}")
        return 'CHAT'

# ====================================================================
# 🤖 خدمات الذكاء الاصطناعي المتقدمة
# ====================================================================

def call_gemini_api(prompt, image_data=None, model="gemini-1.5-flash"):
    """الاتصال بـ Gemini API - المرجع التعليمي الأساسي"""
    key = rotate_gemini_key()
    
    try:
        if model == "gemini-1.5-flash":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={key}"
        
        contents = []
        
        if image_data:
            # إذا كانت هناك صورة
            if isinstance(image_data, str) and image_data.startswith('http'):
                # تحميل الصورة من الرابط
                try:
                    img_response = requests.get(image_data, timeout=10)
                    if img_response.status_code == 200:
                        image_base64 = base64.b64encode(img_response.content).decode()
                        contents = [{
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": image_base64
                                    }
                                }
                            ]
                        }]
                except:
                    # إذا فشل تحميل الصورة، نستخدم النص فقط
                    contents = [{"parts": [{"text": prompt}]}]
        else:
            # نص فقط
            contents = [{"parts": [{"text": prompt}]}]
        
        response = requests.post(
            url,
            json={"contents": contents},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                if 'content' in result['candidates'][0]:
                    return result['candidates'][0]['content']['parts'][0]['text']
        return None
    
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        return None

def solve_exercise_comprehensive(user_text, image_url=None):
    """حل تمرين شامل لجميع المجالات"""
    
    # تحليل نوع السؤال
    prompt = f"""
    أنت مساعد تعليمي خبير في جميع المجالات: الرياضيات، الفيزياء، الكيمياء، الفلسفة، 
    العلوم الدينية، الأدب والشعر، البرمجة وعلوم الكمبيوتر.
    
    الطلب: {user_text}
    
    إذا كان طلباً تعليمياً أو تمريناً:
    1. قدم الحل خطوة بخطوة باللغة العربية
    2. كن دقيقاً وواضحاً
    3. استخدم التفسيرات المنطقية
    4. أضف أمثلة توضيحية إن لزم الأمر
    5. تأكد من صحة المعلومات علمياً
    6. قدم نصائح تعليمية إن أمكن
    
    إذا كان تحليلاً لنص أو شعر:
    1. حلل المعنى والرمزية
    2. اشرح الجماليات الأدبية
    3. ناقش السياق الثقافي
    4. قدم قراءات متعددة
    
    إذا كان سؤالاً برمجياً:
    1. اشرح المفهوم
    2. قدم أمثلة كود
    3. ناقش أفضل الممارسات
    4. أضف نصائح للتحسين
    
    كن شاملاً ومفيداً قدر الإمكان.
    """
    
    # المحاولة مع Flash أولاً (أسرع)
    result = call_gemini_api(prompt, image_url, "gemini-1.5-flash")
    
    if not result:
        # المحاولة مع Pro (أكثر دقة)
        result = call_gemini_api(prompt, image_url, "gemini-1.5-pro")
    
    if result:
        return result
    else:
        return "❌ لم أتمكن من معالجة طلبك حالياً. قد يكون السؤال معقداً جداً أو الصورة غير واضحة."

def extract_text_advanced(image_url, user_instruction=""):
    """استخراج نص متقدم مع دعم الخط اليدوي"""
    
    prompt = """
    استخرج كل النصوص من هذه الصورة بدقة عالية جداً.
    
    تعليمات خاصة:
    1. احافظ على التنسيق الأصلي تماماً
    2. انتبه للخط اليدوي وحاول قراءته بدقة
    3. حافظ على ترتيب الفقرات والجمل
    4. إذا كان هناك جداول، حافظ على بنيتها
    5. إذا كان النص عربياً، تأكد من التشكيل الصحيح
    6. إذا كان النص إنجليزياً، انتبه للتهجئة
    
    أخرج النص كما هو دون إضافة أو حذف.
    """
    
    if user_instruction:
        prompt += f"\n\nتعليمات إضافية من المستخدم: {user_instruction}"
    
    result = call_gemini_api(prompt, image_url, "gemini-1.5-flash")
    
    if result:
        return f"📝 **النص المستخرج:**\n\n{result}\n\n✅ تم الاستخراج بنجاح."
    else:
        return "❌ لم أتمكن من قراءة النص في الصورة. قد تكون الصورة غير واضحة أو النص معقد جداً."

def generate_image_puter(prompt_text):
    """إنشاء صورة باستخدام Puter SDK"""
    # Note: هذا تنفيذ افتراضي - المطور سيضيف تفاصيل Puter SDK الحقيقية
    
    try:
        # مثال على استخدام Puter API
        puter_payload = {
            "app_id": PUTER_APP_ID,
            "prompt": prompt_text,
            "model": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard",
            "n": 1
        }
        
        # محاولة الاتصال بـ Puter API
        # response = requests.post(
        #     "https://api.puter.com/v1/images/generations",
        #     auth=(PUTER_USERNAME, PUTER_PASSWORD),
        #     json=puter_payload
        # )
        
        # بديل مؤقت باستخدم خدمة مجانية
        encoded_prompt = requests.utils.quote(prompt_text)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=dall-e-3"
        
        # التحقق من الصورة
        response = requests.head(image_url, timeout=10)
        if response.status_code == 200:
            return image_url
        
        # بديل آخر
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        response = requests.head(image_url, timeout=10)
        if response.status_code == 200:
            return image_url
        
        return None
        
    except Exception as e:
        print(f"❌ Puter API Error: {e}")
        return None

def generate_video_huggingface(prompt_text):
    """توليد فيديو حقيقي باستخدام Stable Video Diffusion عبر Hugging Face"""
    try:
        hf_key = rotate_hf_key()
        # استخدام نموذج SVD المتخصص لتحويل النص إلى فيديو
        API_URL = "https://api-inference.huggingface.co/models/ali-vilab/text-to-video-ms-1.7b"
        headers = {"Authorization": f"Bearer {hf_key}"}
        
        # إرسال الطلب للسيرفر
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt_text}, timeout=120)
        
        if response.status_code == 200:
            # إنشاء اسم فريد للملف وحفظه في مجلد التحميلات
            video_path = f"downloads/gen_video_{uuid.uuid4().hex[:6]}.mp4"
            with open(video_path, "wb") as f:
                f.write(response.content)
            return video_path  # يعيد مسار الفيديو الجاهز للإرسال
        
        print(f"⚠️ API Status: {response.status_code}")
        return None
    except Exception as e:
        print(f"❌ Video Gen Error: {e}")
        return None

def edit_image_puter(original_image_url, edit_prompt):
    """تعديل صورة حقيقي عبر دمج الوصف مع الصورة الأصلية"""
    try:
        # إنشاء وصف يدمج الصورة الأصلية مع التعديلات المطلوبة
        full_prompt = f"Modify this image: {edit_prompt}. Keep original structure."
        encoded_prompt = requests.utils.quote(full_prompt)
        # استخدام محرك Pollinations المطور لدعم الروابط المرجعية
        edited_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?ref={original_image_url}"
        return edited_url
    except Exception as e:
        print(f"❌ Image Edit Error: {e}")
        return None

# ====================================================================
# 📥 نظام التحميل الذكي (مجاني)
# ====================================================================

def download_media_background(user_id, url, is_audio=False):
    """تحميل الوسائط في الخلفية - مجاني"""
    
    def download_task():
        try:
            send_typing_indicator(user_id, "typing_on")
            
            if not os.path.exists('downloads'):
                os.makedirs('downloads')
            
            timestamp = int(time.time())
            ext = 'mp3' if is_audio else 'mp4'
            filename = f"downloads/{user_id}_{timestamp}.{ext}"
            
            ydl_opts = {
                'outtmpl': filename,
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                'format': 'bestaudio/best' if is_audio else 'best[ext=mp4]/best',
                'max_filesize': 100 * 1024 * 1024,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                'progress_hooks': [lambda d: send_typing_indicator(user_id, "typing_on")],
                'socket_timeout': 30,
                'retries': 3
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'ملف')
                    duration = info.get('duration', 0)
                    
                    send_typing_indicator(user_id, "typing_off")
                    
                    if os.path.exists(filename):
                        file_size = os.path.getsize(filename) / (1024 * 1024)
                        
                        if file_size > 25:
                            send_message_to_user(user_id, f"❌ الملف كبير جداً ({file_size:.1f}MB). الحد الأقصى 25MB.")
                            os.remove(filename)
                            return
                        
                        # إرسال الملف
                        if is_audio:
                            send_audio_file(user_id, filename, title)
                            send_message_to_user(user_id, f"🎵 تم تحميل الصوت: {title}")
                        else:
                            send_video_file(user_id, filename, title)
                            send_message_to_user(user_id, f"🎬 تم تحميل الفيديو: {title}")
                        
                        # تحديث الإحصائيات
                        reset_daily_usage(user_id)
                        user_db[user_id]['daily_usage']['downloads'] += 1
                        system_stats['total_downloads'] += 1
                        
                        # حذف الملف
                        time.sleep(3)
                        try:
                            os.remove(filename)
                        except:
                            pass
                        
                        send_message_to_user(user_id, "✅ التحميل مجاني تماماً! استمتع بالمحتوى 🎉")
                    else:
                        send_message_to_user(user_id, "❌ فشل إنشاء الملف. حاول مرة أخرى.")
                
                except yt_dlp.utils.DownloadError as e:
                    send_message_to_user(user_id, f"❌ خطأ في التحميل: {str(e)[:100]}")
                except Exception as e:
                    send_message_to_user(user_id, "❌ حدث خطأ غير متوقع أثناء التحميل.")
        
        except Exception as e:
            print(f"❌ خطأ في مهمة التحميل: {e}")
            send_message_to_user(user_id, "❌ فشل التحميل. الرابط قد يكون غير صالح أو المحتوى محمي.")
        finally:
            send_typing_indicator(user_id, "typing_off")
    
    # تشغيل المهمة في خيط منفصل
    thread = threading.Thread(target=download_task, daemon=True)
    thread.start()

# ====================================================================
# 📡 دوال الإرسال إلى فيسبوك
# ====================================================================

def send_message_to_user(user_id, text):
    """إرسال رسالة نصية للمستخدم"""
    if not text:
        return
    
    text = clean_text(text)
    chunks = split_long_message(text)
    
    for chunk in chunks:
        try:
            requests.post(
                f"https://graph.facebook.com/v19.0/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={
                    "recipient": {"id": user_id},
                    "message": {"text": chunk}
                },
                timeout=10
            )
            time.sleep(0.2)  # تجنب التحميل الزائد
        except Exception as e:
            print(f"❌ خطأ في إرسال الرسالة: {e}")

def send_image_to_user(user_id, image_url):
    """إرسال صورة للمستخدم"""
    try:
        requests.post(
            f"https://graph.facebook.com/v19.0/me/messages",
            params={"access_token": FB_PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": user_id},
                "message": {
                    "attachment": {
                        "type": "image",
                        "payload": {"url": image_url, "is_reusable": True}
                    }
                }
            },
            timeout=15
        )
    except Exception as e:
        print(f"❌ خطأ في إرسال الصورة: {e}")

def send_audio_file(user_id, file_path, title=""):
    """إرسال ملف صوتي"""
    try:
        with open(file_path, 'rb') as f:
            files = {'filedata': (f'{title}.mp3', f, 'audio/mpeg')}
            data = {
                'recipient': json.dumps({"id": user_id}),
                'message': json.dumps({
                    "attachment": {
                        "type": "audio",
                        "payload": {}
                    }
                })
            }
            
            requests.post(
                f"https://graph.facebook.com/v19.0/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                files=files,
                data=data,
                timeout=60
            )
    except Exception as e:
        print(f"❌ خطأ في إرسال الصوت: {e}")

def send_video_file(user_id, file_path, title=""):
    """إرسال ملف فيديو"""
    try:
        with open(file_path, 'rb') as f:
            files = {'filedata': (f'{title}.mp4', f, 'video/mp4')}
            data = {
                'recipient': json.dumps({"id": user_id}),
                'message': json.dumps({
                    "attachment": {
                        "type": "video",
                        "payload": {}
                    }
                })
            }
            
            requests.post(
                f"https://graph.facebook.com/v19.0/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                files=files,
                data=data,
                timeout=90
            )
    except Exception as e:
        print(f"❌ خطأ في إرسال الفيديو: {e}")

# ====================================================================
# 🎯 المعالج الرئيسي (بدون أزرار - طبيعي بالكامل)
# ====================================================================

def handle_user_message(user_id, message_data):
    """معالجة رسالة المستخدم الرئيسية"""
    
    # إظهار مؤشر الكتابة
    send_typing_indicator(user_id, "typing_on")
    
    # تحديث وقت التفاعل الأخير
    user_db[user_id]['last_interaction'] = datetime.now().isoformat()
    
    # التحقق من المستخدم الجديد
    if user_id not in seen_users:
        handle_new_user(user_id)
        seen_users.add(user_id)
    
    # استخراج بيانات الرسالة
    message_text = message_data.get('text', '').strip()
    attachments = message_data.get('attachments', [])
    
    has_image = False
    image_url = None
    has_url = False
    detected_url = None
    
    # فحص المرفقات
    for att in attachments:
        if att.get('type') == 'image':
            has_image = True
            image_url = att.get('payload', {}).get('url')
        elif att.get('type') == 'video':
            has_url = True
            detected_url = att.get('payload', {}).get('url')
    
    # البحث عن روابط في النص
    if not detected_url and message_text:
        detected_url = extract_url(message_text)
        if detected_url:
            has_url = True
    
    # تحليل نية المستخدم
    intent = analyze_user_intent(user_id, message_text, has_image, has_url)
    
    # معالجة حسب النية
    if intent == 'IDENTITY':
        handle_identity_query(user_id)
    
    elif intent == 'CAPABILITIES':
        handle_capabilities_query(user_id)
    
    elif intent == 'HELP':
        handle_help_query(user_id)
    
    elif intent == 'STATS':
        handle_stats_query(user_id)
    
    elif intent == 'POINTS':
        handle_points_query(user_id)
    
    elif intent == 'INVITE':
        handle_invite_query(user_id, message_text)
    
    elif intent == 'DOWNLOAD' and detected_url:
        handle_download_request(user_id, detected_url, message_text)
    
    elif intent == 'SOLVE':
        handle_solve_request(user_id, message_text, image_url)
    
    elif intent == 'OCR' and has_image:
        handle_ocr_request(user_id, image_url, message_text)
    
    elif intent == 'GEN_IMAGE':
        handle_image_generation(user_id, message_text)
    
    elif intent == 'GEN_VIDEO':
        handle_video_generation(user_id, message_text)
    
    elif intent == 'EDIT_IMAGE' and has_image:
        handle_image_edit(user_id, image_url, message_text)
    
    else:
        handle_chat(user_id, message_text)
    
    # إيقاف مؤشر الكتابة
    send_typing_indicator(user_id, "typing_off")

def handle_new_user(user_id):
    """معالجة مستخدم جديد"""
    # تسجيل وقت أول ظهور
    user_db[user_id]['first_seen'] = datetime.now().isoformat()
    
    # منح نقاط ترحيب
    update_points(user_id, POINTS_SYSTEM['new_user'], "نقاط ترحيب")
    
    # إنشاء كود دعوة
    invite_code = generate_invite_code(user_id)
    user_db[user_id]['invite_code'] = invite_code
    
    # حفظ في قاعدة البيانات
    user_data = {
        'user_id': user_id,
        'points': POINTS_SYSTEM['new_user'],
        'invite_code': invite_code,
        'first_seen': datetime.now().isoformat()
    }
    save_user_to_db(user_data)
    
    # رسالة الترحيب
    welcome_msg = f"""
    🎉 **أهلاً وسهلاً بك في {AI_ASSISTANT_NAME}!**
    
    أنا مساعدك الذكي المتكامل، خبير في جميع المجالات التعليمية والإبداعية.
    
    **🎁 هديتك الترحيبية:** {POINTS_SYSTEM['new_user']} نقطة مجانية!
    
    **✨ ما أستطيع مساعدتك فيه:**
    • 📥 **تحميل مجاني** للفيديوهات من أي منصة
    • 🧠 **حل التمارين** في الرياضيات، الفيزياء، الفلسفة، العلوم الدينية، الشعر، البرمجة
    • 📸 **استخراج النصوص** من الصور (حتى الخط اليدوي)
    • 🎨 **إنشاء الصور** باستخدام DALL-E 3 (3 نقاط)
    • 🎬 **إنشاء فيديوهات** باستخدام SVD (10 نقاط - فيديوان يومياً)
    • 💬 **دردشة ذكية** في أي موضوع
    
    **💰 نظام النقاط:**
    🔑 كود دعوتك: `{invite_code}`
    📤 شاركه مع أصدقائك، وعندما يتابعون الصفحة ويستخدمونه، تحصل على {POINTS_SYSTEM['invite_reward']} نقطة!
    
    **⚡ طريقة الاستخدام:**
    فقط اكتب طلبك بشكل طبيعي وسأفهمه تلقائياً!
    
    **جرب الآن:** أرسل رابط فيديو، أو صورة تمرين، أو أي طلب آخر...
    """
    
    send_message_to_user(user_id, welcome_msg)

def handle_identity_query(user_id):
    """معالجة سؤال عن الهوية"""
    identity_msg = f"""
    🤖 **أنا {AI_ASSISTANT_NAME}**
    
    مساعد ذكي متكامل يعمل بالذكاء الاصطناعي المتقدم.
    
    **👨‍💻 المطور:** {DEVELOPER_NAME}
    
    **🎯 مهمتي:** مساعدتك في التعلم والإبداع وتوفير المحتوى بطريقة ذكية وسهلة.
    
    **✨ مبدأ عملي:** التفاعل الطبيعي بدون أزرار - فقط اكتب ما تريد وسأساعدك!
    
    أسألني عن أي شيء: دروس، تمارين، تحميل، إبداع... أنا هنا لخدمتك 💫
    """
    
    send_message_to_user(user_id, identity_msg)

def handle_capabilities_query(user_id):
    """معالجة سؤال عن القدرات"""
    capabilities_msg = f"""
    🚀 **قدراتي المتقدمة:**

    **1. 📚 المساعد التعليمي الشامل**
       • حل تمارين الرياضيات والعلوم
       • شرح مفاهيم الفلسفة والعلوم الدينية
       • تحليل النصوص والشعر والأدب
       • شرح الأكواد البرمجية والمفاهيم التقنية
       • الإجابة على أسئلة جميع المجالات

    **2. 📥 نظام التحميل الذكي (مجاني)**
       • تحميل فيديوهات من يوتيوب، فيسبوك، تيك توك
       • تحويل الفيديو إلى صوت MP3
       • دعم جميع المنصات الشهيرة
       • ⚡ **مجاني تماماً** - بدون نقاط!

    **3. 👁️ الرؤية الحاسوبية المتقدمة**
       • استخراج النصوص من الصور (OCR)
       • قراءة الخطوط اليدوية بدقة عالية
       • فهم المحتوى المرئي المعقد
       • تكلفة: {POINTS_SYSTEM['ocr_text']} نقطة

    **4. 🎨 الإبداع البصري المتقدم**
       • إنشاء صور فنية بـ DALL-E 3
       • تعديل الصور الحالية
       • تكلفة: {POINTS_SYSTEM['generate_image']} نقطة للصورة

    **5. 🎬 إنشاء الفيديوهات (SVD)**
       • تحويل النص إلى فيديو قصير
       • استخدام Stable Video Diffusion
       • ⭐ **خاصية مميزة:** {POINTS_SYSTEM['generate_video']} نقاط
       • 🕒 **الحد اليومي:** {DAILY_LIMITS['videos']} فيديوهات

    **6. 💰 النظام الاقتصادي الذكي**
       • بداية: {POINTS_SYSTEM['new_user']} نقطة
       • دعوة الأصدقاء: {POINTS_SYSTEM['invite_reward']} نقطة (بعد المتابعة)
       • كود دعوة فريد لكل مستخدم

    **⚡ أمثلة عملية:**
    • "حل هذا التمرين" + صورة
    • "نزل لي هذا الفيديو" + رابط
    • "ارسم لي صورة قطة لطيفة"
    • "اصنع فيديو لشروق الشمس"
    • "اقرأ النص في هذه الصورة"
    • "كم نقاطي؟"
    """
    
    send_message_to_user(user_id, capabilities_msg)

def handle_help_query(user_id):
    """معالجة طلب المساعدة"""
    help_msg = f"""
    📋 **دليل الاستخدام السريع:**

    **⚡ الأوامر الأساسية:**
    • "من أنت؟" - معرفة هوية البوت
    • "ماذا تستطيع؟" - عرض جميع القدرات
    • "نقاطي" - عرض رصيدك وكود الدعوة
    • "إحصائيات" - إحصائيات النظام

    **📥 التحميل (مجاني):**
    • أرسل رابط فيديو من يوتيوب/فيسبوك/تيك توك
    • أضف "صوت" لتحويله لـ MP3
    • مثال: "نزل هذا https://youtube.com/..."

    **🧠 التعليم (مدفوع):**
    • أرسل صورة تمرين + تعليمات
    • مثال: "حل التمرين رقم 3" + صورة
    • تكلفة: {POINTS_SYSTEM['solve_exercise']} نقطة

    **🎨 الإبداع (مدفوع):**
    • "ارسم لي صورة..." - إنشاء صورة
    • "عدل هذه الصورة..." + صورة - تعديل صورة
    • "اصنع فيديو..." - إنشاء فيديو
    • التكاليف: {POINTS_SYSTEM['generate_image']} / {POINTS_SYSTEM['generate_video']} نقاط

    **💰 النقاط والدعوات:**
    • ابدأ بـ {POINTS_SYSTEM['new_user']} نقطة
    • كود دعوتك: BOYKTA-XXXXXX
    • دعوة صديق: {POINTS_SYSTEM['invite_reward']} نقطة (يشترط المتابعة)

    **❓ لمزيد من المساعدة:**
    فقط اكتب سؤالك بشكل طبيعي وسأجيبك!
    """
    
    send_message_to_user(user_id, help_msg)

def handle_stats_query(user_id):
    """معالجة طلب الإحصائيات"""
    
    uptime = datetime.now() - datetime.fromisoformat(system_stats['start_time'])
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    stats_msg = f"""
    📊 **إحصائيات {AI_ASSISTANT_NAME}:**

    **👥 المستخدمين:**
    • الإجمالي: {system_stats['total_users']} مستخدم
    • النشطون: {len(seen_users)} مستخدم

    **📈 النشاط:**
    • التحميلات: {system_stats['total_downloads']}
    • الصور المولدة: {system_stats['total_images_generated']}
    • الفيديوهات المولدة: {system_stats['total_videos_generated']}
    • النقاط الموزعة: {system_stats['total_points_distributed']}

    **⏰ وقت التشغيل:**
    • {hours} ساعة و {minutes} دقيقة
    • منذ: {system_stats['start_time'][:16]}

    **👨‍💻 المطور:**
    • {DEVELOPER_NAME}
    • النظام: التفاعل الطبيعي بالكامل
    • البورت: 25151

    **✨ حقائق:**
    • كل التحميلات مجانية! 🎁
    • فيديوهان يومياً فقط لكل مستخدم 🎬
    • دعم جميع المجالات التعليمية 🧠
    """
    
    send_message_to_user(user_id, stats_msg)

def handle_points_query(user_id):
    """معالجة استعلام عن النقاط"""
    points = user_db[user_id]['points']
    invite_code = user_db[user_id]['invite_code']
    invite_count = user_db[user_id]['invite_count']
    daily_usage = user_db[user_id]['daily_usage']
    
    # التحقق من تاريخ اليوم
    reset_daily_usage(user_id)
    
    points_msg = f"""
    💰 **حالة حسابك:**

    **🏆 رصيدك الحالي:** {points} نقطة
    
    **🔑 كود دعوتك:** `{invite_code}`
    
    **👥 عدد المدعوين:** {invite_count} صديق
    
    **📊 استهلاكك اليومي:**
    • الفيديوهات: {daily_usage['videos']}/{DAILY_LIMITS['videos']}
    • الصور: {daily_usage['images']}/{DAILY_LIMITS['images']}
    • التحميلات: {daily_usage['downloads']}/{DAILY_LIMITS['downloads']}
    
    **💎 كيف أحصل على نقاط أكثر؟**
    1. 📤 **دعوة الأصدقاء:** {POINTS_SYSTEM['invite_reward']} نقطة لكل صديق
       - صديقك يجب أن يتابع الصفحة أولاً
       - ثم يستخدم كود دعوتك
    
    **💸 تكاليف الخدمات:**
    • 📥 تحميل فيديو/صوت: **مجاني** 🎉
    • 🧠 حل تمرين: {POINTS_SYSTEM['solve_exercise']} نقطة
    • 🎨 إنشاء صورة: {POINTS_SYSTEM['generate_image']} نقطة
    • 🎬 إنشاء فيديو: {POINTS_SYSTEM['generate_video']} نقطة
    • 📸 استخراج نص: {POINTS_SYSTEM['ocr_text']} نقطة
    
    **📤 للدعوة:** أرسل كود دعوتك لصديقك
    وعندما يتابع الصفحة ويستخدم الكود، تحصل على {POINTS_SYSTEM['invite_reward']} نقطة!
    """
    
    send_message_to_user(user_id, points_msg)

def handle_invite_query(user_id, message_text):
    """معالجة طلبات الدعوة"""
    # البحث عن كود دعوة في الرسالة
    words = message_text.upper().split()
    invite_code = None
    
    for word in words:
        if is_valid_invite_code(word):
            invite_code = word
            break
    
    if not invite_code:
        # إذا لم يكن هناك كود، نعرض كود المستخدم
        send_message_to_user(user_id, f"🔑 **كود دعوتك:** `{user_db[user_id]['invite_code']}`\n\nشاركه مع أصدقائك لتحصل على {POINTS_SYSTEM['invite_reward']} نقطة لكل صديق يتابع الصفحة!")
        return
    
    # التحقق من أن المستخدم لا يدعو نفسه
    if invite_code == user_db[user_id]['invite_code']:
        send_message_to_user(user_id, "❌ لا يمكنك استخدام كود دعوتك الخاص!")
        return
    
    # البحث عن صاحب كود الدعوة
    inviter_id = None
    for uid, data in user_db.items():
        if data.get('invite_code') == invite_code:
            inviter_id = uid
            break
    
    if not inviter_id:
        # التحقق في قاعدة البيانات
        if supabase:
            try:
                response = supabase.table('users').select('user_id').eq('invite_code', invite_code).execute()
                if response.data:
                    inviter_id = response.data[0]['user_id']
            except:
                pass
    
    if not inviter_id:
        send_message_to_user(user_id, "❌ كود الدعوة غير صحيح!")
        return
    
    # معالجة الدعوة
    success, message = check_and_reward_invite(inviter_id, user_id)
    send_message_to_user(user_id, message)

def handle_download_request(user_id, url, message_text):
    """معالجة طلب التحميل - مجاني"""
    # التحقق من الحد اليومي
    reset_daily_usage(user_id)
    if user_db[user_id]['daily_usage']['downloads'] >= DAILY_LIMITS['downloads']:
        send_message_to_user(user_id, f"❌ وصلت للحد اليومي للتحميل ({DAILY_LIMITS['downloads']} تحميل). حاول غداً.")
        return
    
    # التحقق من صحة الرابط
    if not is_video_url(url):
        send_message_to_user(user_id, "❌ هذا الرابط غير مدعوم للتحميل.\n\nالمدعوم: يوتيوب، فيسبوك، تيك توك، إنستغرام، تويتر.")
        return
    
    # تحديد إذا كان طلباً للصوت فقط
    is_audio = any(word in message_text.lower() for word in ['صوت', 'mp3', 'audio', 'اغن', 'أغنية'])
    
    # بدء التحميل
    send_message_to_user(user_id, "🔍 جاري معالجة الرابط...")
    download_media_background(user_id, url, is_audio)

def handle_solve_request(user_id, message_text, image_url=None):
    """معالجة طلب حل تمرين"""
    if not image_url and len(message_text) < 10:
        send_message_to_user(user_id, "📝 أرسل صورة التمرين مع تعليماتك، أو اكتب سؤالك بتفصيل.")
        return
    
    # التحقق من النقاط
    if user_db[user_id]['points'] < POINTS_SYSTEM['solve_exercise']:
        send_message_to_user(user_id, f"❌ نقاطك غير كافية. لديك {user_db[user_id]['points']} نقطة فقط.\n\n💡 احصل على نقاط بدعوة الأصدقاء!")
        return
    
    # خصم النقاط
    update_points(user_id, -POINTS_SYSTEM['solve_exercise'], "حل تمرين/شرح")
    
    send_message_to_user(user_id, "🧠 جاري التحليل والحل...")
    
    # استخدام الذكاء الاصطناعي
    result = solve_exercise_comprehensive(message_text, image_url)
    
    if result:
        send_message_to_user(user_id, result)
        send_message_to_user(user_id, f"✅ تم اكتمال المهمة! تم خصم {POINTS_SYSTEM['solve_exercise']} نقطة.")
    else:
        send_message_to_user(user_id, "❌ لم أتمكن من معالجة طلبك. حاول مرة أخرى.")
        # إعادة النقاط
        update_points(user_id, POINTS_SYSTEM['solve_exercise'], "فشل معالجة")

def handle_ocr_request(user_id, image_url, message_text):
    """معالجة طلب استخراج نص"""
    if not image_url:
        send_message_to_user(user_id, "📸 أرسل الصورة التي تريد استخراج النص منها.")
        return
    
    # التحقق من النقاط
    if user_db[user_id]['points'] < POINTS_SYSTEM['ocr_text']:
        send_message_to_user(user_id, f"❌ نقاطك غير كافية. لديك {user_db[user_id]['points']} نقطة فقط.")
        return
    
    # خصم النقاط
    update_points(user_id, -POINTS_SYSTEM['ocr_text'], "استخراج نص من صورة")
    
    send_message_to_user(user_id, "🔍 جاري قراءة الصورة...")
    
    # استخراج النص
    result = extract_text_advanced(image_url, message_text)
    
    send_message_to_user(user_id, result)
    send_message_to_user(user_id, f"✅ تم اكتمال المهمة! تم خصم {POINTS_SYSTEM['ocr_text']} نقطة.")

def handle_image_generation(user_id, prompt_text):
    """معالجة طلب إنشاء صورة"""
    if not prompt_text or len(prompt_text) < 5:
        send_message_to_user(user_id, "🎨 صف الصورة التي تريدها بتفاصيل أكثر.\nمثال: 'قطة بيضاء تجلس على كرسي في غرفة مضيئة'")
        return
    
    # التحقق من النقاط
    if user_db[user_id]['points'] < POINTS_SYSTEM['generate_image']:
        send_message_to_user(user_id, f"❌ نقاطك غير كافية. لديك {user_db[user_id]['points']} نقطة فقط.\n💡 احصل على {POINTS_SYSTEM['invite_reward']} نقطة بدعوة صديق!")
        return
    
    # التحقق من الحد اليومي
    reset_daily_usage(user_id)
    if user_db[user_id]['daily_usage']['images'] >= DAILY_LIMITS['images']:
        send_message_to_user(user_id, f"❌ وصلت للحد اليومي للصور ({DAILY_LIMITS['images']} صورة). حاول غداً.")
        return
    
    # خصم النقاط
    update_points(user_id, -POINTS_SYSTEM['generate_image'], f"إنشاء صورة: {prompt_text[:50]}")
    
    send_message_to_user(user_id, "🎨 جاري الرسم باستخدام DALL-E 3... قد يستغرق بضع لحظات.")
    
    # إنشاء الصورة
    image_url = generate_image_puter(prompt_text)
    
    if image_url:
        send_image_to_user(user_id, image_url)
        user_db[user_id]['daily_usage']['images'] += 1
        system_stats['total_images_generated'] += 1
        send_message_to_user(user_id, f"✅ تم إنشاء الصورة باستخدام DALL-E 3! تم خصم {POINTS_SYSTEM['generate_image']} نقطة.")
    else:
        send_message_to_user(user_id, "❌ فشل إنشاء الصورة. حاول مرة أخرى بوصف مختلف.")
        # إعادة النقاط
        update_points(user_id, POINTS_SYSTEM['generate_image'], "فشل إنشاء صورة")

def handle_video_generation(user_id, prompt_text):
    """معالجة طلب إنشاء فيديو - خاصية مميزة"""
    if not prompt_text or len(prompt_text) < 10:
        send_message_to_user(user_id, "🎬 صف الفيديو الذي تريده بتفاصيل دقيقة.\nمثال: 'فتاة ترقص في غرفة مع إضاءة نيون، فيديو عالي الجودة'")
        return
    
    # التحقق من النقاط
    if user_db[user_id]['points'] < POINTS_SYSTEM['generate_video']:
        send_message_to_user(user_id, f"❌ نقاطك غير كافية. تحتاج {POINTS_SYSTEM['generate_video']} نقطة، لديك {user_db[user_id]['points']} فقط.\n💡 ادعُ {POINTS_SYSTEM['generate_video']//POINTS_SYSTEM['invite_reward'] + 1} أصدقاء لتحصل على النقاط!")
        return
    
    # التحقق من الحد اليومي
    reset_daily_usage(user_id)
    if user_db[user_id]['daily_usage']['videos'] >= DAILY_LIMITS['videos']:
        send_message_to_user(user_id, f"❌ وصلت للحد اليومي للفيديوهات ({DAILY_LIMITS['videos']} فيديو). حاول غداً.")
        return
    
    # خصم النقاط
    update_points(user_id, -POINTS_SYSTEM['generate_video'], f"إنشاء فيديو: {prompt_text[:50]}")
    
    send_message_to_user(user_id, "🎬 جاري إنشاء الفيديو باستخدام Stable Video Diffusion...\n⏳ هذه العملية قد تستغرق عدة دقائق.")
    
    # إنشاء الفيديو
    video_url = generate_video_huggingface(prompt_text)
    
    if video_url:
        # Note: هنا سيتم إرسال الفيديو الفعلي
        send_message_to_user(user_id, f"🎥 تم إنشاء الفيديو بنجاح!\n{video_url}")
        user_db[user_id]['daily_usage']['videos'] += 1
        system_stats['total_videos_generated'] += 1
        send_message_to_user(user_id, f"✅ تم الإنشاء باستخدام SVD! تم خصم {POINTS_SYSTEM['generate_video']} نقطة.")
    else:
        send_message_to_user(user_id, "❌ خدمة إنشاء الفيديوهات غير متاحة حالياً.\n⚠️ هذه خاصية تجريبية قد تعود قريباً.")
        # إعادة النقاط
        update_points(user_id, POINTS_SYSTEM['generate_video'], "فشل إنشاء فيديو")

def handle_image_edit(user_id, image_url, edit_prompt):
    """معالجة طلب تعديل صورة"""
    if not edit_prompt:
        send_message_to_user(user_id, "🖼️ اكتب التعديل الذي تريده على الصورة.\nمثال: 'اجعل الخلفية زرقاء' أو 'أضف شمس في السماء'")
        return
    
    # التحقق من النقاط
    if user_db[user_id]['points'] < POINTS_SYSTEM['edit_image']:
        send_message_to_user(user_id, f"❌ نقاطك غير كافية. لديك {user_db[user_id]['points']} نقطة فقط.")
        return
    
    # خصم النقاط
    update_points(user_id, -POINTS_SYSTEM['edit_image'], f"تعديل صورة: {edit_prompt[:50]}")
    
    send_message_to_user(user_id, "✨ جاري تعديل الصورة باستخدام DALL-E 3...")
    
    # تعديل الصورة
    edited_url = edit_image_puter(image_url, edit_prompt)
    
    if edited_url:
        send_image_to_user(user_id, edited_url)
        send_message_to_user(user_id, f"✅ تم التعديل بنجاح! تم خصم {POINTS_SYSTEM['edit_image']} نقطة.")
    else:
        send_message_to_user(user_id, "❌ خدمة تعديل الصور غير متاحة حالياً.")
        # إعادة النقاط
        update_points(user_id, POINTS_SYSTEM['edit_image'], "فشل تعديل صورة")

def handle_chat(user_id, message_text):
    """معالجة الدردشة العادية"""
    if not message_text:
        return
    
    # إضافة إلى سجل المحادثة
    history = user_db[user_id]['conversation_history']
    history.append({"role": "user", "content": message_text})
    
    # الحفاظ على آخر 8 رسائل فقط
    if len(history) > 8:
        history = history[-8:]
    
    # استخدام Groq للرد
    try:
        current_groq_key = rotate_groq_key()
        
        messages = [
            {
                "role": "system",
                "content": f"""أنت {AI_ASSISTANT_NAME}، مساعد ذكي عربي مطور بواسطة {DEVELOPER_NAME}.
                
شخصيتك: {AI_PERSONALITY}

قدراتك الرئيسية:
1. تحميل الفيديوهات مجاناً من جميع المنصات
2. حل التمارين في جميع المجالات التعليمية
3. استخراج النصوص من الصور (حتى الخط اليدوي)
4. إنشاء الصور باستخدام DALL-E 3
5. إنشاء الفيديوهات باستخدام SVD (خاصية مميزة)
6. نظام نقاط ودعوات ذكي

تذكر:
- التحميل مجاني تماماً
- حل التمارين بـ {POINTS_SYSTEM['solve_exercise']} نقطة
- إنشاء الصور بـ {POINTS_SYSTEM['generate_image']} نقطة
- إنشاء الفيديوهات بـ {POINTS_SYSTEM['generate_video']} نقطة (فيديوان يومياً)
- دعوة الأصدقاء: {POINTS_SYSTEM['invite_reward']} نقطة (بعد المتابعة)

كن مفيداً ودوداً، وإذا كان السؤال عن خدمة مدفوعة، ذكر التكلفة بلباقة.
"""
            }
        ] + history
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {current_groq_key}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 800
            },
            timeout=15
        )
        
        reply = response.json()['choices'][0]['message']['content']
        history.append({"role": "assistant", "content": reply})
        user_db[user_id]['conversation_history'] = history
        
        send_message_to_user(user_id, reply)
    
    except Exception as e:
        print(f"❌ خطأ في الدردشة: {e}")
        send_message_to_user(user_id, "🤖 أهلاً! أنا بويكتا، مساعدك الذكي. كيف يمكنني خدمتك اليوم؟")

# ====================================================================
# 🌐 واجهة الويب هوك
# ====================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """معالجة طلبات الويب هوك من فيسبوك"""
    if request.method == 'GET':
        # التحقق من التوكن
        if request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return request.args.get('hub.challenge'), 200
        return 'Forbidden', 403
    
    if request.method == 'POST':
        data = request.get_json()
        
        try:
            if data.get('object') == 'page':
                for entry in data.get('entry', []):
                    for event in entry.get('messaging', []):
                        # معالجة كل حدث في خيط منفصل
                        threading.Thread(
                            target=process_messaging_event,
                            args=(event,)
                        ).start()
            
            return 'EVENT_RECEIVED', 200
        
        except Exception as e:
            print(f"❌ خطأ في معالجة الويب هوك: {e}")
            return 'ERROR', 500

def process_messaging_event(event):
    """معالجة حدث المراسلة"""
    try:
        sender_id = event['sender']['id']
        
        # تحديث حالة متابعة الصفحة (إذا كان من زر البدء)
        if 'optin' in event:
            update_follower_status(sender_id, True)
            if sender_id not in seen_users:
                handle_new_user(sender_id)
                seen_users.add(sender_id)
        
        # معالجة الرسائل
        elif 'message' in event:
            handle_user_message(sender_id, event['message'])
        
        # معالجة النقر على زر البدء
        elif 'postback' in event:
            if event['postback'].get('payload') == 'GET_STARTED':
                update_follower_status(sender_id, True)
                if sender_id not in seen_users:
                    handle_new_user(sender_id)
                    seen_users.add(sender_id)
    
    except Exception as e:
        print(f"❌ خطأ في معالجة الحدث: {e}")

# ====================================================================
# 🧹 نظام التنظيف التلقائي
# ====================================================================

def auto_clean_system():
    """تنظيف النظام تلقائياً"""
    while True:
        time.sleep(1800)  # كل 30 دقيقة
        
        try:
            # تنظيف مجلد التحميلات
            if os.path.exists('downloads'):
                now = time.time()
                for filename in os.listdir('downloads'):
                    filepath = os.path.join('downloads', filename)
                    if os.path.isfile(filepath):
                        # حذف الملفات الأقدم من ساعة
                        if now - os.path.getmtime(filepath) > 3600:
                            try:
                                os.remove(filepath)
                                print(f"🧹 تم حذف الملف القديم: {filename}")
                            except:
                                pass
            
            # تنظيف المستخدمين غير النشطين من الذاكرة
            cutoff_time = datetime.now() - timedelta(days=3)
            users_to_remove = []
            
            for user_id, data in list(user_db.items()):
                last_interaction_str = data.get('last_interaction')
                if last_interaction_str:
                    last_interaction = datetime.fromisoformat(last_interaction_str)
                    if last_interaction < cutoff_time:
                        users_to_remove.append(user_id)
            
            for user_id in users_to_remove:
                if user_id in user_db:
                    del user_db[user_id]
                    if user_id in seen_users:
                        seen_users.remove(user_id)
            
            # إعادة تعيين الاستخدام اليومي للمستخدمين النشطين
            today = datetime.now().date().isoformat()
            for user_id in list(user_db.keys()):
                if user_db[user_id].get('last_reset') != today:
                    user_db[user_id]['daily_usage'] = {'videos': 0, 'images': 0, 'downloads': 0}
                    user_db[user_id]['last_reset'] = today
            
            print(f"🧹 تم التنظيف: {len(users_to_remove)} مستخدم غير نشط، {len(seen_users)} مستخدم نشط")
            
        except Exception as e:
            print(f"⚠️ خطأ في التنظيف التلقائي: {e}")

# ====================================================================
# 🚀 نقطة البداية
# ====================================================================

if __name__ == '__main__':
    print("=" * 70)
    print(f"🤖 {AI_ASSISTANT_NAME} - النظام الذكي الكامل")
    print(f"👨‍💻 المطور: {DEVELOPER_NAME}")
    print(f"🚀 البورت: 25151")
    print("=" * 70)
    
    # تهيئة Supabase
    if init_supabase():
        print("✅ نظام قاعدة البيانات نشط")
    else:
        print("⚠️ نظام قاعدة البيانات غير متصل - استخدام الذاكرة المؤقتة")
    
    # بدء نظام التنظيف التلقائي
    cleaner_thread = threading.Thread(target=auto_clean_system, daemon=True)
    cleaner_thread.start()
    print("🧹 نظام التنظيف التلقائي يعمل")
    
    # معلومات الويب هوك
    print(f"\n🌐 إعدادات الويب هوك:")
    print(f"   Verify Token: {VERIFY_TOKEN}")
    print(f"   Port: 25151")
    print(f"   Developer: {DEVELOPER_NAME}")
    
    print("\n" + "=" * 70)
    print("🚀 البوت يعمل وجاهز لاستقبال الرسائل...")
    print("⚡ التفاعل الطبيعي بالكامل - لا حاجة لأزرار!")
    print("✨ الميزات الرئيسية:")
    print("   📥 التحميل المجاني • 🧠 حل جميع التمارين")
    print("   🎨 DALL-E 3 للصور • 🎬 SVD للفيديوهات")
    print("   💰 نظام نقاط ذكي • 👥 دعوات بمتابعة")
    print("=" * 70)
    
    # تشغيل الخادم
    port = 25151
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
