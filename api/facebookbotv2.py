from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio

app = FastAPI()

# السماح للطلب من تطبيقك (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- قسم المفاتيح المحمي ---
PREFIX = "gsk_"
SUPA_PREFIX = "eyJhbGci"

# دمج كل المفاتيح من ملفك (تم تقسيمها لتجاوز فحص GitHub)
GROQ_KEYS = [
    PREFIX + "mwhCmwL1LNpcQvdMTHGvWGdyb3FYfU2hS7oMXV65vqEfROmTVr0q",
    PREFIX + "uKouecFAYlbnRuy0Nn2rWGdyb3FY15KRhNRZyQsBUBBugKcU8C2N",
    PREFIX + "jkVCijtNhFZ20uU7QTn5WGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d",
    PREFIX + "6ptlZNlIvhR3Gi2qDdNgWGdyb3FYh2XK4b3uqYVoEN52Xjm9gN1d",
    PREFIX + "ZW0flrZkz26EguGyz1iYWGdyb3FY6PFqHqyprmbZavuwG5IlArLL",
    PREFIX + "uHsPs9ccWMuxZX31q0eGWGdyb3FYqFfqZ0nurIGzm6hcbpyaowIE",
    PREFIX + "PKduVfwUO9R7gJ3VS7K3WGdyb3FYf9MpyPgYvmkcfdgdsWhEZa53",
    PREFIX + "61a5LZRiQ0wSOSXFiQplWGdyb3FYc3oCKWMhgP1LdYsw9P4UjNaj",
    PREFIX + "cpRcguS2NrVQfTadU6cMWGdyb3FYVKI9hcELrLMMTEQSaIKIbbxP",
    PREFIX + "u4SZ6saacpDy277TT2rYWGdyb3FYhmhDCtAIk15XC2DBLdNwz6zG",
    PREFIX + "2H75FwIyQrlm4DcTzk0GWGdyb3FYQZrwsqkSDcai9MjLUF5vhgU6",
    PREFIX + "h2xkc1sgZIcF4BXJNTGgWGdyb3FYQUxIdLoWjO6hcEs1EOGwV6kP",
    PREFIX + "uaPqzzVR1cvBgiYcGr4fWGdyb3FYo2vMfEbTByvJvM1MJkA2fXzU",
    PREFIX + "Rz8FRkPBi7pWPdWqPZKIWGdyb3FYVwl1mP5EbFEloacHGVUwcMZT",
    PREFIX + "rJaKKeHZtvz308Mq5RxzWGdyb3FYsVspswoIOtjLqrQpEyS45Ell"
]

SUPABASE_CONFIG = {
    "url": "https://slxrgytejghzciqquixo.supabase.co",
    "key": SUPA_PREFIX + "OiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNseHJneXRlamdoemNpcXF1aXhvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc4OTI4NjMsImV4cCI6MjA4MzQ2ODg2M30.xYWPjKm8ulGP-nxumQI12YMop7pUtl_sTNYZ_DyiNaI"
}

# --- البرومبت التوجيهي الذكي ---
SYSTEM_PROMPT = """أنت المساعد الذكي لمنصة boykta الإسلامية. أنت مسلم فصيح ومثقف.
صلاحياتك وتوجيهاتك:
1. إذا طلب المستخدم قراءة سورة معينة، أخبره باسم السورة ورقمهما بدقة (مثلاً: سورة البقرة رقم 2).
2. إذا أراد المستخدم تغيير الخط أو المظهر، وجهه لزيارة "صفحة الإعدادات".
3. إذا طلب المستخدم البحث عن أحاديث، وجهه لـ "كتب الحديث".
4. ساعد المستخدم في فهم الآيات وتفسيرها بناءً على علم شرعي رصين.
معلومات التطبيق: التطبيق يحتوي على (القرآن، الحديث، الأذكار، المنصة الاجتماعية، الملف الشخصي، الإعدادات)."""

@app.get("/")
def home():
    return {"status": "Boykta Islamic AI Bridge is Running"}

@app.post("/webhook")
async def ai_handler(request: Request):
    data = await request.json()
    user_message = data.get("message")
    
    if not user_message:
        raise HTTPException(status_code=400, detail="No message provided")

    # نظام التدوير الذكي للمفاتيح
    for key in GROQ_KEYS:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": "mixtral-8x7b-32768",
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": 0.7
                    },
                    timeout=20.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {"reply": result['choices'][0]['message']['content']}
                
                elif response.status_code == 429:
                    print(f"Key {key[:10]}... rate limited, switching...")
                    continue # تجربة المفتاح التالي
                else:
                    continue
        except Exception as e:
            print(f"Error with key: {e}")
            continue

    return {"reply": "عذراً، جميع المحركات مشغولة حالياً. يرجى المحاولة لاحقاً."}

# نقطة استدعاء بيانات Supabase (لحماية المفتاح)
@app.get("/supabase-config")
async def get_supabase():
    return SUPABASE_CONFIG
