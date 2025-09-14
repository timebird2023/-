const express = require('express');
const cors = require('cors');
const fetch = require('node-fetch');
const FormData = require('form-data');
const multer = require('multer');

const app = express();
const PORT = process.env.PORT || 3001;

// إعداد CORS للسماح بالطلبات من جميع المصادر
app.use(cors({
    origin: '*',
    methods: ['GET', 'POST', 'PUT', 'DELETE'],
    allowedHeaders: ['Content-Type', 'Authorization']
}));

// إعداد multer لتحليل الملفات
const upload = multer({
    limits: {
        fileSize: 32 * 1024 * 1024 // 32MB حد أقصى لحجم الملف
    }
});

app.use(express.json({ limit: '32mb' }));
app.use(express.urlencoded({ extended: true, limit: '32mb' }));

// إضافة header للاستجابة
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
    if (req.method === 'OPTIONS') {
        res.sendStatus(200);
    } else {
        next();
    }
});

// دالة رفع الصورة إلى ImgBB
async function uploadToImgBB(imageData, isBase64 = false) {
    try {
        const apiKey = process.env.IMGBB_API_KEY;
        if (!apiKey) {
            throw new Error('IMGBB_API_KEY غير موجود في متغيرات البيئة');
        }

        const formData = new FormData();
        
        if (isBase64) {
            // إزالة البادئة من base64 إذا كانت موجودة
            const base64Data = imageData.replace(/^data:image\/[a-z]+;base64,/, '');
            formData.append('image', base64Data);
        } else {
            // في حالة الملف المباشر
            formData.append('image', imageData);
        }

        const response = await fetch(`https://api.imgbb.com/1/upload?key=${apiKey}`, {
            method: 'POST',
            body: formData,
            headers: formData.getHeaders()
        });

        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error?.message || 'فشل في رفع الصورة إلى ImgBB');
        }

        return {
            success: true,
            url: result.data.display_url,
            delete_url: result.data.delete_url,
            id: result.data.id
        };

    } catch (error) {
        console.error('خطأ في رفع الصورة إلى ImgBB:', error);
        throw error;
    }
}

// نقطة نهاية رفع الصورة
app.post('/api/upload-image', upload.single('image'), async (req, res) => {
    try {
        console.log('طلب رفع صورة جديد');
        
        let imageData;
        let isBase64 = false;

        // التحقق من وجود الصورة في الطلب
        if (req.file) {
            // الصورة كملف مرفوع
            imageData = req.file.buffer;
            console.log('تم استقبال صورة كملف، الحجم:', req.file.size);
        } else if (req.body.image) {
            // الصورة كـ base64
            imageData = req.body.image;
            isBase64 = true;
            console.log('تم استقبال صورة كـ base64');
        } else {
            return res.status(400).json({
                success: false,
                error: 'لم يتم العثور على صورة في الطلب'
            });
        }

        // رفع الصورة إلى ImgBB
        const uploadResult = await uploadToImgBB(imageData, isBase64);
        
        console.log('تم رفع الصورة بنجاح:', uploadResult.url);
        
        res.json({
            success: true,
            url: uploadResult.url,
            delete_url: uploadResult.delete_url,
            id: uploadResult.id,
            message: 'تم رفع الصورة بنجاح'
        });

    } catch (error) {
        console.error('خطأ في رفع الصورة:', error);
        res.status(500).json({
            success: false,
            error: error.message || 'حدث خطأ في رفع الصورة'
        });
    }
});

// نقطة نهاية للاختبار
app.get('/api/test', (req, res) => {
    res.json({
        success: true,
        message: 'خدمة رفع الصور تعمل بنجاح',
        timestamp: new Date().toISOString()
    });
});

app.listen(PORT, () => {
    console.log(`خدمة رفع الصور تعمل على المنفذ ${PORT}`);
});