/**
 * بروكسي لرفع الصور على خدمة imgg.io وإنشاء روابط عامة لها
 * يستخدم مفتاح API الخاص بالمستخدم
 */

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

  const imggApiKey = "bb5a898b99708dbdb82640f7d0c341a8"; // مفتاح imgg API
  const imggApiUrl = "https://imgg.io/api/1/upload";

  try {
    // استخراج البيانات من جسم الطلب
    const { image, title } = req.body;

    console.log('Received upload request for image:', title || 'untitled');

    // التحقق من وجود البيانات المطلوبة
    if (!image) {
      res.status(400).json({ 
        error: 'Missing required field', 
        details: 'Image data is required (base64 or file data)',
        received: { image: !!image }
      });
      return;
    }

    // إعداد البيانات للإرسال إلى imgg API
    const formData = new URLSearchParams();
    formData.append("key", imggApiKey);
    formData.append("source", image); // base64 أو URL للصورة
    if (title) {
      formData.append("title", title);
    }
    formData.append("format", "json");

    console.log('Uploading to imgg.io...');

    // إرسال الطلب إلى واجهة برمجة تطبيقات imgg
    const response = await fetch(imggApiUrl, {
      method: 'POST',
      body: formData,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      },
      timeout: 30000 // 30 ثانية timeout
    });

    console.log('imgg API Response status:', response.status);

    if (!response.ok) {
      throw new Error(`imgg API returned ${response.status}: ${response.statusText}`);
    }

    // قراءة الرد من imgg
    const result = await response.json();
    
    console.log('imgg API result:', result);

    // التحقق من نجاح الرفع
    if (result.status_code === 200 && result.image && result.image.url) {
      // إرجاع رابط الصورة المرفوعة
      res.status(200).json({
        success: true,
        url: result.image.url,
        delete_url: result.image.delete_url || null,
        title: result.image.title || title,
        size: result.image.size || null,
        width: result.image.width || null,
        height: result.image.height || null
      });
    } else {
      // إذا فشل الرفع
      res.status(400).json({
        error: 'Upload failed',
        details: result.error || 'Unknown error from imgg service',
        response: result
      });
    }

  } catch (error) {
    console.error('imgg Upload Error:', error);
    
    // تفاصيل أكثر عن الخطأ
    const errorDetails = {
      message: error.message,
      code: error.code,
      type: error.constructor.name
    };

    res.status(500).json({ 
      error: 'Failed to upload image to imgg', 
      details: errorDetails,
      timestamp: new Date().toISOString()
    });
  }
}