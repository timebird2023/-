/**
 * بروكسي مدمج لتحرير الصور - يقوم برفع الصورة على imgg ثم تحريرها
 * يستخدم مفتاح imgg API ثم يرسل الرابط لخدمة nano-banana
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
  const nanoBananaApiUrl = "https://sii3.moayman.top/api/nano-banana.php";

  try {
    // استخراج البيانات من جسم الطلب
    const { image, text, title } = req.body;

    console.log('Received integrated edit request:', { text, title, hasImage: !!image });

    // التحقق من وجود البيانات المطلوبة
    if (!image || !text) {
      res.status(400).json({ 
        error: 'Missing required fields', 
        details: 'Both image data and edit description are required',
        received: { image: !!image, text: !!text }
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

    console.log('Step 2: Sending to nano-banana for editing...');

    // الخطوة الثانية: إرسال رابط الصورة لخدمة nano-banana
    const nanoBananaFormData = new URLSearchParams();
    nanoBananaFormData.append("text", text.trim());
    nanoBananaFormData.append("links", imageUrl);

    const nanoBananaResponse = await fetch(nanoBananaApiUrl, {
      method: 'POST',
      body: nanoBananaFormData,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      },
      timeout: 60000 // وقت أطول للتحرير
    });

    console.log('nano-banana response status:', nanoBananaResponse.status);

    if (!nanoBananaResponse.ok) {
      throw new Error(`nano-banana API returned ${nanoBananaResponse.status}: ${nanoBananaResponse.statusText}`);
    }

    // قراءة النتيجة
    let editResult;
    const contentType = nanoBananaResponse.headers.get('content-type');
    
    if (contentType && contentType.includes('application/json')) {
      editResult = await nanoBananaResponse.json();
    } else {
      const textResult = await nanoBananaResponse.text();
      console.log('nano-banana text response:', textResult);
      
      try {
        editResult = JSON.parse(textResult);
      } catch (e) {
        if (textResult.startsWith('http')) {
          editResult = { output: textResult.trim() };
        } else {
          editResult = { error: 'Invalid response format', response: textResult };
        }
      }
    }

    console.log('Step 2 completed: Edit result:', editResult);

    // إرجاع النتيجة المدمجة
    res.status(200).json({
      success: true,
      original_image: imageUrl,
      edited_image: editResult.output || editResult.image || editResult,
      edit_description: text,
      upload_info: {
        url: imageUrl,
        delete_url: imggResult.image.delete_url || null,
        title: imggResult.image.title || title,
        size: imggResult.image.size || null
      }
    });

  } catch (error) {
    console.error('Integrated Edit Error:', error);
    
    const errorDetails = {
      message: error.message,
      code: error.code,
      type: error.constructor.name,
      step: error.message.includes('imgg') ? 'upload' : 'edit'
    };

    res.status(500).json({ 
      error: 'Failed to process integrated image edit', 
      details: errorDetails,
      timestamp: new Date().toISOString()
    });
  }
}