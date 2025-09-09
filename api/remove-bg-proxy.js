/**
 * هذا الملف هو بروكسي (Proxy) مخصص لإعادة توجيه طلبات خدمة Remove-BG API.
 * تم تصميمه للعمل Serverless Function على منصات مثل Vercel.
 */
const fetch = require('node-fetch');
const querystring = require('querystring');

module.exports = async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    try {
        const originalApiUrl = 'https://sii3.moayman.top/api/remove-bg.php';
        let finalUrl = originalApiUrl;
        let fetchOptions = { method: req.method };

        let requestData;

        // تحليل البيانات بناءً على نوع الطلب
        if (req.method === 'GET') {
            requestData = req.query;
            finalUrl += '?' + querystring.stringify(requestData);
        } else if (req.method === 'POST') {
            // قراءة البيانات من جسم الطلب (خاصة بالملفات)
            const body = await new Promise((resolve, reject) => {
                let chunks = [];
                req.on('data', chunk => chunks.push(chunk));
                req.on('end', () => resolve(Buffer.concat(chunks)));
                req.on('error', reject);
            });
            
            try {
                requestData = JSON.parse(body.toString());
            } catch (error) {
                // محاولة تحليل البيانات كـ form-urlencoded إذا فشل JSON
                const bodyString = body.toString();
                requestData = querystring.parse(bodyString);
            }

            // إعادة توجيه البيانات كـ form-urlencoded إلى API الأصلي
            fetchOptions.headers = { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            };
            fetchOptions.body = querystring.stringify({
                url: requestData.image || requestData.image_base64 || requestData.url,
                format: requestData.format || 'png'
            });
        }
        
        // إرسال الطلب إلى واجهة برمجة التطبيقات الأصلية
        const apiResponse = await fetch(finalUrl, fetchOptions);

        if (!apiResponse.ok) {
            const errorText = await apiResponse.text();
            res.status(apiResponse.status).send(errorText);
            return;
        }
        
        const contentType = apiResponse.headers.get('content-type');
        if (contentType) {
            res.setHeader('Content-Type', contentType);
        }
        
        const responseBuffer = await apiResponse.buffer();
        res.status(apiResponse.status).send(responseBuffer);

    } catch (error) {
        res.status(500).json({ error: 'خطأ عام في الخدمة: ' + error.message });
    }
};
