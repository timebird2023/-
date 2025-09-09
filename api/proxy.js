/**
 * هذا الملف هو وسيط (Proxy) لتوزيع الطلبات على Google Gemini API وواجهات برمجة تطبيقات أخرى.
 * يعمل كـ Serverless Function على منصات مثل Vercel.
 */

// استيراد مكتبة node-fetch لإجراء طلبات HTTP
const fetch = require('node-fetch');
const querystring = require('querystring');

// مفاتيح Google Gemini API
// قم بإضافة أو حذف المفاتيح هنا كما تريد
const API_KEYS = [
    'AIzaSyC50R6tiry_hqI9rHWNoAznu5mlv6-sELc',
    'AIzaSyAZxz9v-3y31ZT-uXPXIMJ3q7x-PlVi7PA',
    'AIzaSyBC2iW-AOcJsRMIFWPUS6_1-5ie-lOoMf8',
    'AIzaSyBgTcKmUg0XpmfdIMd0zs8CSSUFOa3QW4U',
    'AIzaSyCh7XGGIdJlmm8XoOM7W6xEbZF3JPnhbZI',
    'AIzaSyDh_bk184ese3v4c4bLOX9k1YqURVSArNM',
    'AIzaSyDLyjQlG1fa06pyy9AyOM1gHVRGKAzsaP8',
    'AIzaSyBO7mvPzeqJCx3k_VXpUWcLNU14FbmcV1E',
    'AIzaSyDTd6iud35iT9fvaZ7gq8UDTyiX9eT8woI',
    'AIzaSyBwCJUjJrJBoCM5HMPX83m1u271lC9ZapI'
];

// دالة لمعالجة طلبات Gemini API
const handleGeminiRequest = async (enhancedQuery, isArabic) => {
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
        return finalResponse;
    } else {
        if (lastError.includes('Quota Exceeded')) {
            return isArabic ? "عذراً، تجاوزت جميع المفاتيح الحد الأقصى. يرجى المحاولة غدًا." : "Sorry, all API keys have exceeded their daily limit. Please try again tomorrow.";
        } else {
            return isArabic ? "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى لاحقاً." : "Sorry, an error occurred. Please try again later.";
        }
    }
};

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
        const originalUrl = 'https://sii3.moayman.top/';
        let targetPath = req.query.api || (req.body && req.body.api);
        let method = req.method;
        let requestBody = req.body;

        if (!targetPath) {
            // Check if it's an old Gemini request
            const geminiQuery = req.query.q || (req.body && req.body.q);
            if (geminiQuery) {
                const isArabic = /[\u0600-\u06FF]/.test(geminiQuery);
                const languageInstruction = isArabic ? "أجب باللغة العربية فقط. " : "Please respond in English only. ";
                const enhancedQuery = languageInstruction + geminiQuery;
                const geminiResponse = await handleGeminiRequest(enhancedQuery, isArabic);
                res.status(200).send(geminiResponse);
                return;
            }

            res.status(400).json({ error: 'No API target specified.' });
            return;
        }
        
        let finalUrl;
        let fetchOptions = {
            method: method,
            headers: {}
        };
        
        // Handle Gemini requests from new HTML
        if (targetPath.startsWith('gemini')) {
            const isArabic = /[\u0600-\u06FF]/.test(requestBody.prompt);
            const languageInstruction = isArabic ? "أجب باللغة العربية فقط. " : "Please respond in English only. ";
            const enhancedQuery = languageInstruction + requestBody.prompt;
            const geminiResponse = await handleGeminiRequest(enhancedQuery, isArabic);
            res.status(200).send(geminiResponse);
            return;
        }

        // Handle other API requests
        if (targetPath === 'voice') {
            finalUrl = originalUrl + 'api/voice.php';
            if (method === 'GET') {
                 finalUrl += '?' + querystring.stringify(req.query);
            } else if (method === 'POST') {
                fetchOptions.headers['Content-Type'] = 'application/x-www-form-urlencoded';
                fetchOptions.body = querystring.stringify(requestBody);
            }
        } else if (targetPath === 'remove-bg') {
            finalUrl = originalUrl + 'api/remove-bg.php';
            if (method === 'GET') {
                finalUrl += '?' + querystring.stringify(req.query);
            } else if (method === 'POST') {
                fetchOptions.headers['Content-Type'] = 'application/x-www-form-urlencoded';
                fetchOptions.body = querystring.stringify(requestBody);
            }
        } else if (targetPath === 'veo') {
            finalUrl = originalUrl + 'api/veo3.php';
             if (method === 'GET') {
                finalUrl += '?' + querystring.stringify(req.query);
            } else if (method === 'POST') {
                fetchOptions.headers['Content-Type'] = 'application/x-www-form-urlencoded';
                fetchOptions.body = querystring.stringify(requestBody);
            }
        } else {
             res.status(400).json({ error: 'Invalid API target.' });
             return;
        }
        
        // Forward the request
        const response = await fetch(finalUrl, fetchOptions);

        if (!response.ok) {
            const errorText = await response.text();
            res.status(response.status).send(errorText);
            return;
        }

        const contentType = response.headers.get('content-type');
        if (contentType) {
            res.setHeader('Content-Type', contentType);
        }

        const responseBuffer = await response.buffer();
        res.status(response.status).send(responseBuffer);

    } catch (error) {
        res.status(500).json({ error: 'خطأ عام في الخدمة: ' + error.message });
    }
};
