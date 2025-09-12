/**
 * هذا الملف هو نقطة نهاية (endpoint) على Vercel يعمل كوسيط (proxy)
 * للتعامل مع طلبات CORS.
 *
 * يستقبل طلب POST من تطبيق الويب، ثم يمرره إلى واجهة برمجة تطبيقات
 * Nano Banana، ويعيد الرد إلى تطبيق الويب الأصلي.
 *
 * هذا الإصدار مخصص حصريًا لخدمة "تعديل صورة".
 */

import fetch from 'node-fetch';

export default async function (req, res) {
  // السماح بطلبات من أي مصدر (CORS)
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // معالجة طلبات OPTIONS (Preflight requests)
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  // التأكد من أن الطلب هو POST
  if (req.method !== 'POST') {
    res.status(405).send('Method Not Allowed');
    return;
  }

  const nanoBananaApiUrl = "https://sii3.moayman.top/api/nano-banana.php";

  try {
    // استخراج البيانات من جسم الطلب
    const { text, links } = req.body;

    if (!text || !links || !Array.isArray(links) || links.length === 0) {
      res.status(400).json({ error: 'Missing required fields for image editing: "text" and "links" (as a non-empty array)' });
      return;
    }

    // إعداد البيانات التي سيتم إرسالها إلى API
    const formData = new URLSearchParams();
    formData.append("text", text);
    formData.append("links", links.join(","));
    

    // إرسال الطلب إلى واجهة برمجة تطبيقات Nano Banana
    const response = await fetch(nanoBananaApiUrl, {
      method: 'POST',
      body: formData,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    // إعادة الرد من API إلى العميل
    const result = await response.json();
    res.status(response.status).json(result);
  } catch (error) {
    console.error('Proxy Error:', error);
    res.status(500).json({ error: 'Failed to process request', details: error.message });
  }
};
