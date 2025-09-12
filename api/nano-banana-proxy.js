
/**
 * هذا الملف هو نقطة نهاية (endpoint) على Vercel يعمل كوسيط (proxy)
 * للتعامل مع طلبات CORS لخدمة تحرير الصور بالذكاء الاصطناعي.
 *
 * يستقبل طلب POST من تطبيق الويب، ثم يمرره إلى واجهة برمجة تطبيقات
 * Nano Banana، ويعيد الرد إلى تطبيق الويب الأصلي.
 */

import fetch from 'node-fetch';

export default async function handler(req, res) {
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
    res.status(405).json({ error: 'Method Not Allowed' });
    return;
  }

  const nanoBananaApiUrl = "https://sii3.moayman.top/api/nano-banana.php";

  try {
    // استخراج البيانات من جسم الطلب
    const { text, links } = req.body;

    console.log('Received data:', { text, links });

    // التحقق من وجود البيانات المطلوبة
    if (!text || !links) {
      res.status(400).json({ 
        error: 'Missing required fields', 
        details: 'Both "text" and "links" are required',
        received: { text: !!text, links: !!links }
      });
      return;
    }

    // التأكد من أن links هو مصفوفة
