/**
 * هذا الملف هو بروكسي (Proxy) مخصص لإعادة توجيه طلبات خدمة Voice API.
 * تم تصميمه للعمل Serverless Function على منصات مثل Vercel.
 */
const fetch = require('node-fetch');
const querystring = require('querystring');

module.exports = async (req, res) => {
    // إعداد رؤوس CORS للسماح بالطلبات من أي مصدر
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    // التعامل مع طلبات OPTIONS (Preflight requests)
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    try {
        const originalUrl = '[https://sii3.moayman.top/api/voice.php](https://sii3.moayman.top/api/voice.php)';
        let finalUrl = originalUrl;
        let fetchOptions = { method: req.method };

        // بناء الطلب حسب طريقة HTTP (GET أو POST)
        if (req.method === 'GET') {
            finalUrl += '?' + querystring.stringify(req.query);
        } else if (req.method === 'POST') {
            // التعامل مع البيانات المرسلة في جسم الطلب
            fetchOptions.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
            fetchOptions.body = querystring.stringify(req.body);
        }
        
        // إرسال الطلب إلى واجهة برمجة التطبيقات الأصلية
        const apiResponse = await fetch(finalUrl, fetchOptions);

        if (!apiResponse.ok) {
            const errorText = await apiResponse.text();
            res.status(apiResponse.status).send(errorText);
            return;
        }

        // إرجاع الرد بنفس نوع المحتوى (Content-Type)
        const contentType = apiResponse.headers.get('content-type');
        if (contentType) {
            res.setHeader('Content-Type', contentType);
        }
        
        // قراءة الرد كبيانات ثنائية (Buffer) وإرسالها مباشرة
        const responseBuffer = await apiResponse.buffer();
        res.status(apiResponse.status).send(responseBuffer);

    } catch (error) {
        res.status(500).json({ error: 'خطأ عام في الخدمة: ' + error.message });
    }
};
