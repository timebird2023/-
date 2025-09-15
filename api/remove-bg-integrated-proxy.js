/**
 * بروكسي مدمج لإزالة خلفية الصور - يقوم برفع الصورة على imgg ثم إزالة خلفيتها
 * يستخدم مفتاح imgg API ثم يرسل الرابط لخدمة remove-bg
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

  const imggApiKey = "bb5a898b99708dbdb82640f7d0c341a8";
  const imggApiUrl = "https://imgg.io/api/1/upload";
  const removeBgApiUrl = "https://sii3.moayman.top/api/remove-bg.php";

  try {
    // استخراج البيانات من جسم الطلب
    const { image, format, title } = req.body;

    console.log('Received integrated remove-bg request:', { format, title, hasImage: !!image });

    // التحقق من وجود البيانات المطلوبة
    if (!image) {
      res.status(400).json({ 
        error: 'Missing required field', 
        details: 'Image data is required',
        received: { image: !!image }
      });
      return;
    }

    console.log('Step 1: Uploading image to imgg...');

    // الخطوة الأولى: رفع الصورة على imgg
    const imggFormData = new URLSearchParams();
    imggFormData.append("key", imggApiKey);
    imggFormData.append("source", image);
    if (title) {
      imggFormData.append("title", title);
    }
    imggFormData.append("format", "json");

    const imggResponse = await fetch(imggApiUrl, {
      method: 'POST',
      body: imggFormData,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      },
      timeout: 30000
    });

    if (!imggResponse.ok) {
      throw new Error(`imgg upload failed: ${imggResponse.status} ${imggResponse.statusText}`);
    }

    const imggResult = await imggResponse.json();
    
    if (imggResult.status_code !== 200 || !imggResult.image || !imggResult.image.url) {
      throw new Error(`imgg upload error: ${imggResult.error || 'Unknown error'}`);
    }

    const imageUrl = imggResult.image.url;
    console.log('Step 1 completed: Image uploaded to:', imageUrl);

    console.log('Step 2: Sending to remove-bg service...');

    // الخطوة الثانية: إرسال رابط الصورة لخدمة إزالة الخلفية
    const removeBgFormData = new URLSearchParams();
    removeBgFormData.append("image_url", imageUrl);
    removeBgFormData.append("format", format || "png");

    const removeBgResponse = await fetch(removeBgApiUrl, {
      method: 'POST',
      body: removeBgFormData,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      },
      timeout: 60000 // وقت أطول للمعالجة
    });

    console.log('remove-bg response status:', removeBgResponse.status);

    if (!removeBgResponse.ok) {
      const errorText = await removeBgResponse.text();
      throw new Error(`remove-bg API returned ${removeBgResponse.status}: ${errorText}`);
    }

    // التحقق من نوع المحتوى المُرجع
    const contentType = removeBgResponse.headers.get('content-type');
    
    if (contentType && contentType.includes('application/json')) {
      // إذا كان JSON، قد يحتوي على خطأ أو رابط
      const jsonResult = await removeBgResponse.json();
      console.log('Step 2 completed: JSON result:', jsonResult);
      
      res.status(200).json({
        success: true,
        original_image: imageUrl,
        processed_image: jsonResult.output || jsonResult.url || jsonResult,
        format: format || "png",
        upload_info: {
          url: imageUrl,
          delete_url: imggResult.image.delete_url || null,
          title: imggResult.image.title || title,
          size: imggResult.image.size || null
        }
      });
    } else {
      // إذا كان الرد صورة مباشرة
      console.log('Step 2 completed: Image result received');
      
      // إرجاع الصورة مباشرة مع headers مناسبة
      const imageBuffer = await removeBgResponse.arrayBuffer();
      
      res.setHeader('Content-Type', contentType || 'image/png');
      res.setHeader('Content-Length', imageBuffer.byteLength);
      res.setHeader('X-Original-Image', imageUrl);
      res.setHeader('X-Upload-Info', JSON.stringify({
        url: imageUrl,
        delete_url: imggResult.image.delete_url || null,
        title: imggResult.image.title || title,
        size: imggResult.image.size || null
      }));
      
      res.status(200).send(Buffer.from(imageBuffer));
    }

  } catch (error) {
    console.error('Integrated Remove-BG Error:', error);
    
    const errorDetails = {
      message: error.message,
      code: error.code,
      type: error.constructor.name,
      step: error.message.includes('imgg') ? 'upload' : 'remove-bg'
    };

    res.status(500).json({ 
      error: 'Failed to process integrated background removal', 
      details: errorDetails,
      timestamp: new Date().toISOString()
    });
  }
}