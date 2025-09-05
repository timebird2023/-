/**
 * هذا الملف هو وسيط (Proxy) لتوزيع الطلبات على Google Gemini API.
 * يعمل كـ Serverless Function على منصات مثل Vercel.
 */

// استيراد مكتبة node-fetch لإجراء طلبات HTTP
const fetch = require('node-fetch');

// مفاتيح Google Gemini API
// قم بإضافة أو حذف المفاتيح هنا كما تريد
const API_KEYS = [
    'AIzaSyC50R6tiry_hqI9rHWNoAznu5mlv6-sELc',
    'AIzaSyAZxz9v-3y31ZT-uXPXIMJ3q7x-PlVi7PA',
    'AIzaSyBC2iW-AOcJsRMIFWPUS6_1-5ie-lOoMf8',
    'AIzaSyBgTcKmUg0XpmfdIMd0zs8CSSUFOa3QW4U',
    'AIzaSyCh7XGGIdJlmm8XoOM7W6xEbZF3JPnhbZI',
    'AIzaSyDh_bk184ese3v4c4bLOX9k1YqURVSArNM'
];

// الدالة الرئيسية التي يتم استدعاؤها من Vercel
module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    try {
        const query = req.query.q || (req.body && req.body.q);
        if (!query) {
            res.status(400).json({ error: 'No query (q) found in the request.' });
            return;
        }

        // تحديد اللغة
        // التحقق من وجود أحرف عربية
        const isArabic = /[\u0600-\u06FF]/.test(query);
        const languageInstruction = isArabic ? "أجب باللغة العربية فقط. " : "Please respond in English only. ";
        const enhancedQuery = languageInstruction + query;

        const maxAttempts = API_KEYS.length;
        let finalResponse = null;
        let lastError = '';

        for (let i = 0; i < maxAttempts; i++) {
            const currentKey = API_KEYS[i];
            
            try {
                const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${currentKey}`;
                
                const payload = {
                    contents: [{
                        parts: [{ text: enhancedQuery }]
                    }],
                    generationConfig: {
                        temperature: 0.7,
                        maxOutputTokens: 1000
                    }
                };

                const response = await fetch(geminiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.status === 429) {
                    throw new Error('API Key Quota Exceeded');
                }

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error(`HTTP Error: ${response.status} - ${errorText}`);
                }

                const data = await response.json();
                
                if (data && data.candidates && data.candidates[0] && data.candidates[0].content && data.candidates[0].content.parts) {
                    finalResponse = data.candidates[0].content.parts[0].text;
                    break;
                } else {
                    throw new Error('Invalid response format from Gemini API.');
                }
                
            } catch (error) {
                lastError = error.message;
            }
        }

        if (finalResponse) {
            res.status(200).send(finalResponse);
        } else {
            // التحقق مما إذا كان الخطأ هو تجاوز الحد الأقصى للمفاتيح
            if (lastError.includes('Quota Exceeded')) {
                const exhaustedMessage = isArabic ? "عذراً، تجاوزت جميع المفاتيح الحد الأقصى. يرجى المحاولة غدًا." : "Sorry, all API keys have exceeded their daily limit. Please try again tomorrow.";
                res.status(503).send(exhaustedMessage);
            } else {
                const genericError = isArabic ? "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى لاحقاً." : "Sorry, an error occurred. Please try again later.";
                res.status(500).send(genericError);
            }
        }

    } catch (error) {
        res.status(500).json({ error: 'خطأ عام في الخدمة: ' + error.message });
    }
};
