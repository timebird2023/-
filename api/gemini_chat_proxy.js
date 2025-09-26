/**
 * هذا الملف هو بروكسي (Proxy) مصمم خصيصاً لخدمة الدردشة الذكية.
 * يتوقع أن يستقبل سجل المحادثة الكامل من العميل ويعيد توجيهه إلى نموذج Gemini
 * لتوليد رد يأخذ في الاعتبار سياق المحادثة.
 *
 * @param {object} req - كائن الطلب (Request object)
 * @param {object} res - كائن الرد (Response object)
 */

const fetch = require('node-fetch');

// مفتاح Gemini API - يمكنك استخدام المفتاح الخاص بك هنا
// بما أنك تستخدم API خارجية، فإن المفتاح يتم إدارته من قبل تلك الواجهة
const API_KEY = process.env.GEMINI_API_KEY || 'YOUR_API_KEY_HERE';

module.exports = async (req, res) => {
    // إعداد رؤوس CORS للسماح بالطلبات من أي مصدر
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    // التعامل مع طلبات OPTIONS (Preflight requests)
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    try {
        const { history, modelName } = req.body;

        if (!history || !Array.isArray(history) || history.length === 0) {
            return res.status(400).json({ error: 'سجل المحادثة (history) مطلوب في جسم الطلب.' });
        }

        const selectedModel = modelName || 'gemini-pro';
        const originalUrl = `https://sii3.top/api/gemini-dark.php`;

        // تحويل سجل المحادثة إلى تنسيق يتوافق مع Gemini API
        // النموذج الذي قدمته لا يدعم سجل المحادثة في جسم الطلب،
        // لذا سنرسل آخر رسالة فقط مع إشارة إلى السياق
        const lastUserMessage = history[history.length - 1].content;
        const fullPrompt = history.map(msg => `${msg.isUser ? 'أنا' : 'أنت'}: ${msg.content}`).join('\n') + `\n\nأجب على آخر رسالة فقط: ${lastUserMessage}`;

        const payload = {
            [selectedModel]: fullPrompt
        };

        const response = await fetch(originalUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'User-Agent': 'Node.js Proxy'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            return res.status(response.status).json({ error: `خطأ من الواجهة: ${errorText}` });
        }
        
        const responseData = await response.json();
        
        // التحقق من صحة الرد وإرساله
        if (responseData && typeof responseData.response === 'string') {
            return res.status(200).json({ response: responseData.response });
        } else {
            return res.status(500).json({ error: 'رد غير متوقع من الواجهة.' });
        }

    } catch (error) {
        return res.status(500).json({ error: 'خطأ عام في الخدمة: ' + error.message });
    }
};
