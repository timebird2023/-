/**
 * بوابة API موحدة (API Gateway) لخدمات المساعد التعليمي.
 * هذا الملف مصمم للعمل كـ Serverless Function على منصات مثل Vercel.
 * يقوم بتوجيه الطلبات إلى واجهات الـ API الخارجية (Azkar, Deepseek, Search, Qwen)
 * لتفادي مشاكل CORS والاتصال المباشر.
 * يتطلب استخدام مكتبة node-fetch و querystring (عادةً ما تكون متوفرة في بيئة Vercel).
 */
const fetch = require('node-fetch');
const querystring = require('querystring');

// خريطة واجهات الـ API الأصلية
const API_MAP = {
    'azkar': 'https://sii3.top/api/azkar.php',
    'search': 'https://sii3.top/api/s.php',
    'deepseek': 'https://sii3.top/api/deepseek.php',
    'qwen': 'https://sii3.top/api/qwen.php',
};

// الدالة الرئيسية التي يتم استدعاؤها
module.exports = async (req, res) => {
    // 1. إعداد رؤوس CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Service-Target'); // X-Service-Target هو رأس مخصص
    
    // التعامل مع طلبات OPTIONS (Preflight requests)
    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    try {
        let service = req.query.service || req.headers['x-service-target'];

        // إذا كان الطلب POST، حاول قراءة الخدمة من جسم الطلب
        if (!service && req.method === 'POST') {
            // بما أن Vercel لا يفكك body بشكل تلقائي، نقوم بقراءة البيانات يدوياً
            let body = '';
            // قراءة البيانات من الـ stream
            req.on('data', chunk => { body += chunk.toString(); });
            await new Promise(resolve => req.on('end', resolve));

            try {
                // محاولة تحليل JSON أولاً
                req.body = JSON.parse(body);
            } catch (e) {
                // إذا فشل تحليل JSON، حاول تحليلها كـ form-urlencoded
                req.body = querystring.parse(body);
            }
            service = req.body.service;
        }

        // 2. التحقق من الخدمة المطلوبة
        if (!service || !API_MAP[service]) {
            res.status(400).json({ error: 'الرجاء تحديد خدمة صالحة في معلمة "service" أو رأس "X-Service-Target".', available_services: Object.keys(API_MAP) });
            return;
        }

        const targetUrl = API_MAP[service];
        let finalUrl = targetUrl;
        let fetchOptions = { method: req.method };
        let requestData = {}; // البيانات التي سيتم إرسالها للـ API الأصلية

        // 3. بناء البيانات المرسلة
        if (req.method === 'GET') {
            requestData = { ...req.query };
            delete requestData.service; // إزالة معلمة الخدمة
            finalUrl += '?' + querystring.stringify(requestData);
        } else if (req.method === 'POST') {
            requestData = { ...req.body };
            delete requestData.service;
            
            // تحضير البيانات لجسم الطلب POST (غالباً تكون form-urlencoded للـ API المستهدفة)
            fetchOptions.headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
            fetchOptions.body = querystring.stringify(requestData);
        }
        
        // 4. إرسال الطلب إلى واجهة برمجة التطبيقات الأصلية
        const apiResponse = await fetch(finalUrl, fetchOptions);

        if (!apiResponse.ok) {
            const errorText = await apiResponse.text();
            res.status(apiResponse.status).send(errorText);
            return;
        }

        // 5. إرجاع الرد بنفس نوع المحتوى
        const contentType = apiResponse.headers.get('content-type');
        if (contentType) {
            res.setHeader('Content-Type', contentType);
        }
        
        // قراءة الرد كـ Buffer وإرسالها مباشرة (للحفاظ على البيانات كما هي - نص، JSON، أو غيره)
        const responseBuffer = await apiResponse.buffer();
        res.status(apiResponse.status).send(responseBuffer);

    } catch (error) {
        console.error('General Proxy Error:', error);
        res.status(500).json({ error: 'خطأ عام في خدمة الوكيل: ' + error.message });
    }
};
