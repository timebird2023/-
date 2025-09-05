/**
 * هذا الملف يعمل كوسيط لتمرير الطلبات إلى Google Gemini API
 * يعمل على منصات مثل Vercel أو Netlify Functions.
 */

const fetch = require('node-fetch');

// مفاتيح Google Gemini API
const apiKeys = [
    'AIzaSyC50R6tiry_hqI9rHWNoAznu5mlv6-sELc',
    'AIzaSyAZxz9v-3y31ZT-uXPXIMJ3q7x-PlVi7PA', 
    'AIzaSyBC2iW-AOcJsRMIFWPUS6_1-5ie-lOoMf8',
    'AIzaSyBgTcKmUg0XpmfdIMd0zs8CSSUFOa3QW4U',
    'AIzaSyCh7XGGIdJlmm8XoOM7W6xEbZF3JPnhbZI',
    'AIzaSyDh_bk184ese3v4c4bLOX9k1YqURVSArNM'
];

let lastKeyIndex = 0;

/**
 * دالة لاختيار مفتاح API تلقائياً
 * تستخدم نظام Round Robin للتوزيع العادل
 */
function getNextApiKey() {
    const selectedKey = apiKeys[lastKeyIndex];
    lastKeyIndex = (lastKeyIndex + 1) % apiKeys.length;
    return selectedKey;
}

/**
 * الدالة الرئيسية التي تستقبل الطلب وتُعيده
 * (تُسمى handler في منصات Serverless)
 */
module.exports = async (req, res) => {
    // إعدادات CORS للسماح بالطلبات من أي مصدر
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    // التعامل مع طلبات OPTIONS (preflight)
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    try {
        let query;

        // التحقق من طريقة الطلب (GET أو POST) للحصول على السؤال
        if (req.method === 'GET' && req.query.q) {
            query = req.query.q;
        } else if (req.method === 'POST' && req.body && req.body.q) {
            query = req.body.q;
        } else {
            res.status(400).send('لا يوجد سؤال (q) في الطلب.');
            return;
        }

        if (typeof query !== 'string' || query.trim() === '') {
            res.status(400).send('السؤال فارغ أو بتنسيق غير صحيح.');
            return;
        }

        // إعدادات طلب Gemini API
        const apiKey = getNextApiKey();
        const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;
        const data = {
            contents: [{
                parts: [{ text: query }]
            }],
            generationConfig: {
                temperature: 0.7,
                maxOutputTokens: 1000,
            },
        };

        // إرسال الطلب إلى Gemini API
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        // قراءة الاستجابة كـ JSON
        const geminiResponse = await response.json();

        // استخراج النص من الاستجابة
        const text = geminiResponse?.candidates?.[0]?.content?.parts?.[0]?.text || '';
        
        if (text.trim() === '') {
            res.status(500).send('رد فارغ من Gemini API');
            return;
        }

        // إرجاع النص المستخرج
        res.status(200).setHeader('Content-Type', 'text/plain; charset=utf-8').send(text);

    } catch (error) {
        console.error('خطأ في الخدمة:', error);
        res.status(500).send(`عذراً، حدث خطأ في الخدمة: ${error.message}`);
    }
};
