const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const cookieParser = require('cookie-parser');
const { body, validationResult } = require('express-validator');
const { createClient } = require('@supabase/supabase-js');
const multer = require('multer');
const bcrypt = require('bcrypt');
const { v4: uuidv4 } = require('uuid');
const jwt = require('jsonwebtoken');
const Stripe = require('stripe');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// ==================== الإعدادات الأساسية ====================
// Rate Limiting لحماية من الهجمات
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 دقيقة
    max: 100, // 100 طلب لكل IP
    message: 'لقد تجاوزت الحد المسموح من الطلبات. يرجى المحاولة لاحقاً.'
});

// Middleware
app.use(helmet());
app.use(limiter);
app.use(cors({
    origin: process.env.CORS_ORIGIN ? process.env.CORS_ORIGIN.split(',') : '*',
    credentials: true
}));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(cookieParser());
app.use(express.static('public'));

// ==================== إعدادات التوثيق ====================
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY;
const JWT_SECRET = process.env.JWT_SECRET || 'default_jwt_secret_change_in_production';

// إنشاء عملاء Supabase
const supabase = createClient(supabaseUrl, supabaseAnonKey);
const supabaseAdmin = createClient(supabaseUrl, supabaseServiceKey);

// ==================== إعدادات Cloudflare AI ====================
const CF_ACCOUNT_ID = process.env.CF_ACCOUNT_ID;
const CF_KEYS = process.env.CF_KEYS ? process.env.CF_KEYS.split(',') : [];

// نظام تدوير المفاتيح
let requestCount = 0;
function getCloudflareKey() {
    if (CF_KEYS.length === 0) {
        throw new Error('لم يتم تكوين مفاتيح Cloudflare');
    }
    
    // تدوير بين المفاتيح
    const keyIndex = requestCount % CF_KEYS.length;
    requestCount++;
    return CF_KEYS[keyIndex].trim();
}

// دالة الاتصال بـ Cloudflare AI
async function callCloudflareAI(model, data) {
    try {
        const key = getCloudflareKey();
        const response = await fetch(
            `https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/ai/run/${model}`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${key}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            }
        );
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Cloudflare AI error response:', errorText);
            throw new Error(`Cloudflare AI error: ${response.status} ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Cloudflare AI Error:', error);
        throw new Error(`فشل الاتصال بـ Cloudflare AI: ${error.message}`);
    }
}

// ==================== إعدادات Stripe ====================
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, {
    apiVersion: '2023-10-16'
});

// ==================== إعدادات رفع الملفات ====================
const storage = multer.memoryStorage();
const upload = multer({
    storage: storage,
    limits: {
        fileSize: 5 * 1024 * 1024, // 5MB
        files: 1
    },
    fileFilter: (req, file, cb) => {
        const allowedTypes = ['image/jpeg', 'image/png', 'image/jpg', 'image/gif', 'image/webp'];
        if (allowedTypes.includes(file.mimetype)) {
            cb(null, true);
        } else {
            cb(new Error('نوع الملف غير مسموح. المسموح: JPG, PNG, GIF, WebP'));
        }
    }
});

// ==================== دوال مساعدة ====================

// توليد توكن JWT
function generateToken(user) {
    return jwt.sign(
        {
            id: user.id,
            email: user.email,
            full_name: user.full_name
        },
        JWT_SECRET,
        { expiresIn: '7d' }
    );
}

// التحقق من التوكن
function verifyToken(token) {
    try {
        return jwt.verify(token, JWT_SECRET);
    } catch (error) {
        return null;
    }
}

// Middleware للتحقق من المصادقة
function authenticate(req, res, next) {
    const token = req.cookies.token || req.headers.authorization?.split(' ')[1];
    
    if (!token) {
        return res.status(401).json({ error: 'غير مصرح بالوصول. يرجى تسجيل الدخول.' });
    }
    
    const decoded = verifyToken(token);
    if (!decoded) {
        return res.status(401).json({ error: 'توكن غير صالح أو منتهي الصلاحية.' });
    }
    
    req.user = decoded;
    next();
}

// تحويل النص إلى Vector
async function generateEmbedding(text) {
    try {
        if (!text || text.trim().length < 10) {
            return null;
        }
        
        const response = await callCloudflareAI('@cf/baai/bge-m3', {
            text: text.trim(),
            task: 'retrieval'
        });
        
        return response.result?.vector || response.result?.embeddings?.[0] || response.result;
    } catch (error) {
        console.error('فشل توليد الـ Embedding:', error);
        return null;
    }
}

// فحص الصور بالذكاء الاصطناعي
async function checkImageModesty(imageBuffer) {
    try {
        const base64Image = imageBuffer.toString('base64');
        
        // استخدام نموذج الرؤية
        const visionResponse = await callCloudflareAI('@cf/meta/llama-3.2-11b-vision-instruct', {
            messages: [
                {
                    role: "user",
                    content: [
                        {
                            type: "text",
                            text: "Analyze this image for an Islamic matrimonial platform. Check for modesty, appropriate clothing, and Islamic guidelines. Respond with ONLY 'APPROVED' or 'REJECTED' followed by a brief reason in Arabic."
                        },
                        {
                            type: "image",
                            image: base64Image
                        }
                    ]
                }
            ]
        });
        
        const result = visionResponse.result?.message?.content || '';
        const isModest = result.includes('APPROVED');
        
        return {
            approved: isModest,
            reason: result
        };
    } catch (error) {
        console.error('Vision model error:', error);
        
        // استخدام نموذج بديل
        try {
            const base64Image = imageBuffer.toString('base64');
            const resnetResponse = await callCloudflareAI('@cf/microsoft/resnet-50', {
                image: base64Image
            });
            
            const inappropriateLabels = ['nude', 'underwear', 'bikini', 'swimwear', 'revealing', 'lingerie'];
            const predictions = resnetResponse.result || [];
            
            const hasInappropriate = predictions.some(pred => 
                inappropriateLabels.some(label => 
                    pred.label?.toLowerCase().includes(label)
                )
            );
            
            return {
                approved: !hasInappropriate,
                reason: hasInappropriate ? 'تم اكتشاف محتوى غير لائق' : 'الصورة تبدو محتشمة'
            };
        } catch (fallbackError) {
            console.error('Fallback model error:', fallbackError);
            return {
                approved: false,
                reason: 'فشل فحص الصورة'
            };
        }
    }
}

// ==================== API Endpoints ====================

// 1. فحص حالة الخادم
app.get('/api/health', (req, res) => {
    res.json({
        status: 'active',
        timestamp: new Date().toISOString(),
        version: '1.0.0',
        services: {
            supabase: !!supabaseUrl,
            cloudflare: CF_KEYS.length > 0,
            stripe: !!process.env.STRIPE_SECRET_KEY
        }
    });
});

// 2. تسجيل مستخدم جديد
app.post('/api/register', [
    body('email').isEmail().normalizeEmail(),
    body('password').isLength({ min: 8 }),
    body('full_name').notEmpty().trim(),
    body('gender').isIn(['male', 'female']),
    body('country').notEmpty().trim(),
    body('city').notEmpty().trim()
], async (req, res) => {
    try {
        // التحقق من صحة البيانات
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        
        const {
            email,
            password,
            full_name,
            gender,
            birth_date,
            country,
            city,
            phone,
            marital_status,
            prayer_level,
            about_me
        } = req.body;
        
        // التحقق من عدم وجود مستخدم بنفس البريد
        const { data: existingUser } = await supabase
            .from('profiles')
            .select('email')
            .eq('email', email)
            .single();
        
        if (existingUser) {
            return res.status(409).json({ 
                error: 'البريد الإلكتروني مستخدم بالفعل' 
            });
        }
        
        // تشفير كلمة المرور
        const hashedPassword = await bcrypt.hash(password, 10);
        
        // توليد Embedding لـ about_me
        let embedding = null;
        if (about_me && about_me.trim().length > 10) {
            embedding = await generateEmbedding(about_me);
        }
        
        // إدراج المستخدم في قاعدة البيانات
        const { data: user, error: userError } = await supabase
            .from('profiles')
            .insert([{
                id: uuidv4(),
                email,
                password_hash: hashedPassword,
                full_name,
                gender,
                birth_date,
                country,
                city,
                phone,
                marital_status,
                prayer_level,
                about_me,
                about_me_embedding: embedding,
                is_active: true,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
            }])
            .select()
            .single();
        
        if (userError) {
            console.error('Supabase error:', userError);
            throw new Error(userError.message);
        }
        
        // إنشاء التوكن
        const token = generateToken(user);
        
        // إعداد الـ Cookie
        res.cookie('token', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            maxAge: 7 * 24 * 60 * 60 * 1000 // 7 أيام
        });
        
        // إرجاع الاستجابة
        res.status(201).json({
            message: 'تم التسجيل بنجاح',
            user: {
                id: user.id,
                email: user.email,
                full_name: user.full_name,
                gender: user.gender,
                country: user.country,
                city: user.city
            },
            token: token
        });
        
    } catch (error) {
        console.error('Registration error:', error);
        res.status(500).json({ 
            error: 'فشل التسجيل',
            details: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// 3. تسجيل الدخول
app.post('/api/login', [
    body('email').isEmail().normalizeEmail(),
    body('password').notEmpty()
], async (req, res) => {
    try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }
        
        const { email, password } = req.body;
        
        // البحث عن المستخدم
        const { data: user, error } = await supabase
            .from('profiles')
            .select('*')
            .eq('email', email)
            .eq('is_active', true)
            .single();
        
        if (error || !user) {
            return res.status(401).json({ error: 'البريد الإلكتروني أو كلمة المرور غير صحيحة' });
        }
        
        // التحقق من كلمة المرور
        const validPassword = await bcrypt.compare(password, user.password_hash);
        if (!validPassword) {
            return res.status(401).json({ error: 'البريد الإلكتروني أو كلمة المرور غير صحيحة' });
        }
        
        // تحديث آخر دخول
        await supabase
            .from('profiles')
            .update({ last_login: new Date().toISOString() })
            .eq('id', user.id);
        
        // توليد التوكن
        const token = generateToken(user);
        
        // إعداد الـ Cookie
        res.cookie('token', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            maxAge: 7 * 24 * 60 * 60 * 1000
        });
        
        // إرجاع الاستجابة
        res.json({
            message: 'تم تسجيل الدخول بنجاح',
            user: {
                id: user.id,
                email: user.email,
                full_name: user.full_name,
                gender: user.gender,
                country: user.country,
                city: user.city,
                is_premium: user.is_premium
            },
            token: token
        });
        
    } catch (error) {
        console.error('Login error:', error);
        res.status(500).json({ 
            error: 'فشل تسجيل الدخول',
            details: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// 4. تسجيل الخروج
app.post('/api/logout', (req, res) => {
    res.clearCookie('token');
    res.json({ message: 'تم تسجيل الخروج بنجاح' });
});

// 5. الحصول على بيانات المستخدم الحالي
app.get('/api/me', authenticate, async (req, res) => {
    try {
        const { data: user, error } = await supabase
            .from('profiles')
            .select(`
                *,
                photos (*),
                religious_info (*)
            `)
            .eq('id', req.user.id)
            .single();
        
        if (error) throw error;
        
        // إزالة البيانات الحساسة
        const { password_hash, ...userData } = user;
        
        res.json({ user: userData });
        
    } catch (error) {
        console.error('Get user error:', error);
        res.status(500).json({ error: 'فشل في الحصول على بيانات المستخدم' });
    }
});

// 6. رفع صورة مع فحص الذكاء الاصطناعي
app.post('/api/upload-photo', authenticate, upload.single('photo'), async (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: 'لم يتم رفع أي صورة' });
        }
        
        const { is_profile = false } = req.body;
        const userId = req.user.id;
        
        // فحص الصورة بالذكاء الاصطناعي
        const modestyCheck = await checkImageModesty(req.file.buffer);
        
        if (!modestyCheck.approved) {
            return res.status(400).json({
                error: 'الصورة لا تلتزم بمعايير الستر الإسلامي',
                reason: modestyCheck.reason
            });
        }
        
        // إنشاء اسم ملف فريد
        const fileExtension = req.file.originalname.split('.').pop();
        const fileName = `photos/${userId}/${uuidv4()}.${fileExtension}`;
        
        // رفع الصورة إلى Supabase Storage
        const { data: uploadData, error: uploadError } = await supabase.storage
            .from('user-photos')
            .upload(fileName, req.file.buffer, {
                contentType: req.file.mimetype,
                cacheControl: '3600',
                upsert: false
            });
        
        if (uploadError) {
            console.error('Upload error:', uploadError);
            throw new Error(uploadError.message);
        }
        
        // الحصول على الرابط العام
        const { data: { publicUrl } } = supabase.storage
            .from('user-photos')
            .getPublicUrl(fileName);
        
        // إذا كانت صورة الملف الشخصي، إلغاء أي صورة شخصية سابقة
        if (is_profile === 'true' || is_profile === true) {
            await supabase
                .from('photos')
                .update({ is_profile: false })
                .eq('user_id', userId)
                .eq('is_profile', true);
        }
        
        // حفظ بيانات الصورة في قاعدة البيانات
        const { data: photo, error: dbError } = await supabase
            .from('photos')
            .insert([{
                user_id: userId,
                url: publicUrl,
                storage_path: fileName,
                filename: req.file.originalname,
                file_size: req.file.size,
                mime_type: req.file.mimetype,
                is_profile: is_profile === 'true' || is_profile === true,
                is_approved: true,
                approval_reason: modestyCheck.reason,
                moderation_checked_at: new Date().toISOString()
            }])
            .select()
            .single();
        
        if (dbError) throw dbError;
        
        res.json({
            message: 'تم رفع الصورة بنجاح',
            photo: {
                id: photo.id,
                url: photo.url,
                is_profile: photo.is_profile,
                is_approved: photo.is_approved
            }
        });
        
    } catch (error) {
        console.error('Upload photo error:', error);
        res.status(500).json({ 
            error: 'فشل رفع الصورة',
            details: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// 7. البحث عن مطابقات
app.post('/api/match', authenticate, async (req, res) => {
    try {
        const {
            search_text = '',
            gender,
            country,
            age_min = 18,
            age_max = 100,
            marital_status,
            prayer_level,
            limit = 20
        } = req.body;
        
        let matches = [];
        const userId = req.user.id;
        
        // البحث الدلالي إذا كان هناك نص بحث
        if (search_text && search_text.trim().length > 10) {
            try {
                const queryEmbedding = await generateEmbedding(search_text);
                
                if (queryEmbedding) {
                    const { data: semanticMatches, error } = await supabase.rpc(
                        'match_profiles_by_embedding',
                        {
                            query_embedding: queryEmbedding,
                            match_threshold: 0.3,
                            match_count: limit,
                            filter_gender: gender,
                            filter_country: country,
                            filter_min_age: age_min,
                            filter_max_age: age_max,
                            filter_marital_status: marital_status,
                            filter_prayer_level: prayer_level
                        }
                    );
                    
                    if (!error && semanticMatches) {
                        matches = semanticMatches;
                    }
                }
            } catch (embeddingError) {
                console.warn('Semantic search failed:', embeddingError);
            }
        }
        
        // البحث التقليدي إذا لم يكن هناك نتائج دلالية
        if (matches.length === 0) {
            let query = supabase
                .from('profiles')
                .select(`
                    *,
                    religious_info (*),
                    photos!inner (*)
                `)
                .neq('id', userId)
                .eq('is_active', true)
                .eq('is_verified', true)
                .limit(limit);
            
            if (gender) query = query.eq('gender', gender);
            if (country) query = query.eq('country', country);
            if (marital_status) query = query.eq('marital_status', marital_status);
            if (age_min) query = query.gte('age', age_min);
            if (age_max) query = query.lte('age', age_max);
            
            const { data, error } = await query;
            
            if (error) throw error;
            matches = data || [];
        }
        
        // تصفية حسب مستوى الصلاة
        if (prayer_level) {
            matches = matches.filter(profile => {
                const userPrayerLevel = profile.religious_info?.[0]?.prayer_level;
                if (!userPrayerLevel) return false;
                
                const levels = {
                    'دائمًا في وقتها': 5,
                    'غالبًا في وقتها': 4,
                    'أحيانًا': 3,
                    'نادرًا': 2,
                    'لا أصلي': 1
                };
                
                const searchLevel = levels[prayer_level] || 1;
                const userLevel = levels[userPrayerLevel] || 1;
                
                return userLevel >= searchLevel;
            });
        }
        
        // تنسيق النتائج
        const formattedMatches = matches.map(profile => ({
            id: profile.id,
            full_name: profile.full_name,
            age: profile.age || (profile.birth_date ? 
                new Date().getFullYear() - new Date(profile.birth_date).getFullYear() : null),
            country: profile.country,
            city: profile.city,
            marital_status: profile.marital_status,
            about_me: profile.about_me,
            prayer_level: profile.religious_info?.[0]?.prayer_level,
            hijab_status: profile.religious_info?.[0]?.hijab_status,
            beard_status: profile.religious_info?.[0]?.beard_status,
            photos: (profile.photos || []).map(photo => ({
                id: photo.id,
                url: photo.is_approved ? photo.url : null,
                is_profile: photo.is_profile,
                is_approved: photo.is_approved,
                blur_preview: !photo.is_approved
            })).filter(photo => photo.url)
        }));
        
        res.json({
            count: formattedMatches.length,
            matches: formattedMatches
        });
        
    } catch (error) {
        console.error('Match search error:', error);
        res.status(500).json({ 
            error: 'فشل البحث',
            details: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// 8. طلب مشاهدة صورة
app.post('/api/request-view', authenticate, async (req, res) => {
    try {
        const { photo_id } = req.body;
        const requester_id = req.user.id;
        
        if (!photo_id) {
            return res.status(400).json({ error: 'معرف الصورة مطلوب' });
        }
        
        // التحقق من وجود الصورة
        const { data: photo, error: photoError } = await supabase
            .from('photos')
            .select('*, profiles!inner(*)')
            .eq('id', photo_id)
            .single();
        
        if (photoError || !photo) {
            return res.status(404).json({ error: 'الصورة غير موجودة' });
        }
        
        // التحقق من أن المستخدم لا يطلب مشاهدة صورته
        if (photo.user_id === requester_id) {
            return res.status(400).json({ error: 'لا يمكنك طلب مشاهدة صورتك الخاصة' });
        }
        
        // التحقق من وجود طلب سابق
        const { data: existingRequest } = await supabase
            .from('photo_requests')
            .select('*')
            .eq('requester_id', requester_id)
            .eq('photo_id', photo_id)
            .eq('status', 'pending')
            .single();
        
        if (existingRequest) {
            return res.json({ 
                message: 'طلب المشاهدة قيد الانتظار بالفعل',
                request_id: existingRequest.id
            });
        }
        
        // إنشاء طلب جديد
        const { data: request, error: requestError } = await supabase
            .from('photo_requests')
            .insert([{
                requester_id,
                photo_id,
                status: 'pending',
                requested_at: new Date().toISOString(),
                expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
            }])
            .select()
            .single();
        
        if (requestError) throw requestError;
        
        // زيادة عداد طلبات المشاهدة
        await supabase.rpc('increment_requested_views', { photo_uuid: photo_id });
        
        // إنشاء إشعار لصاحب الصورة
        await supabase
            .from('notifications')
            .insert([{
                user_id: photo.user_id,
                type: 'photo_view_request',
                title: 'طلب مشاهدة صورة جديدة',
                message: `${req.user.full_name} يطلب الإذن لمشاهدة صورتك`,
                data: { request_id: request.id, photo_id, requester_id: requester_id },
                created_at: new Date().toISOString()
            }]);
        
        res.status(201).json({
            message: 'تم إرسال طلب المشاهدة بنجاح',
            request_id: request.id
        });
        
    } catch (error) {
        console.error('Request view error:', error);
        res.status(500).json({ error: 'فشل في إرسال طلب المشاهدة' });
    }
});

// 9. إنشاء جلسة دفع Stripe
app.post('/api/create-checkout-session', authenticate, async (req, res) => {
    try {
        const { price_id, success_url, cancel_url } = req.body;
        
        if (!price_id) {
            return res.status(400).json({ error: 'معرف السعر مطلوب' });
        }
        
        const session = await stripe.checkout.sessions.create({
            payment_method_types: ['card'],
            line_items: [{
                price: price_id,
                quantity: 1,
            }],
            mode: 'subscription',
            success_url: success_url || `${req.headers.origin}/dashboard?payment=success`,
            cancel_url: cancel_url || `${req.headers.origin}/dashboard?payment=canceled`,
            customer_email: req.user.email,
            metadata: {
                user_id: req.user.id
            }
        });
        
        res.json({ sessionId: session.id, url: session.url });
        
    } catch (error) {
        console.error('Stripe error:', error);
        res.status(500).json({ error: 'فشل في إنشاء جلسة الدفع' });
    }
});

// 10. Webhook لـ Stripe
app.post('/api/stripe-webhook', express.raw({ type: 'application/json' }), async (req, res) => {
    const sig = req.headers['stripe-signature'];
    const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
    
    let event;
    
    try {
        event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
    } catch (err) {
        console.error('Webhook signature verification failed:', err.message);
        return res.status(400).send(`Webhook Error: ${err.message}`);
    }
    
    // التعامل مع الأحداث
    switch (event.type) {
        case 'checkout.session.completed':
            const session = event.data.object;
            const userId = session.metadata.user_id;
            
            if (userId) {
                // تحديث حالة المستخدم إلى Premium
                await supabase
                    .from('profiles')
                    .update({ is_premium: true })
                    .eq('id', userId);
                
                // تسجيل الاشتراك
                await supabase
                    .from('premium_subscriptions')
                    .insert([{
                        user_id: userId,
                        stripe_customer_id: session.customer,
                        stripe_subscription_id: session.subscription,
                        plan_type: 'monthly',
                        status: 'active',
                        current_period_start: new Date(session.created * 1000).toISOString(),
                        current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
                    }]);
            }
            break;
            
        case 'customer.subscription.deleted':
            const subscription = event.data.object;
            
            // تحديث حالة الاشتراك
            await supabase
                .from('premium_subscriptions')
                .update({ 
                    status: 'canceled',
                    canceled_at: new Date().toISOString()
                })
                .eq('stripe_subscription_id', subscription.id);
            break;
    }
    
    res.json({ received: true });
});

// 11. تحديث ملف المستخدم
app.put('/api/profile', authenticate, async (req, res) => {
    try {
        const userId = req.user.id;
        const updateData = req.body;
        
        // إزالة الحقول غير المسموح بها
        delete updateData.id;
        delete updateData.email;
        delete updateData.password_hash;
        delete updateData.created_at;
        
        // إذا كان هناك about_me جديد، توليد embedding
        if (updateData.about_me && updateData.about_me.trim().length > 10) {
            updateData.about_me_embedding = await generateEmbedding(updateData.about_me);
        }
        
        updateData.updated_at = new Date().toISOString();
        
        const { data: updatedUser, error } = await supabase
            .from('profiles')
            .update(updateData)
            .eq('id', userId)
            .select()
            .single();
        
        if (error) throw error;
        
        // إذا كانت هناك معلومات دينية، تحديثها
        if (req.body.prayer_level || req.body.hijab_status || req.body.beard_status) {
            const religiousUpdate = {
                prayer_level: req.body.prayer_level,
                hijab_status: req.body.hijab_status,
                beard_status: req.body.beard_status,
                updated_at: new Date().toISOString()
            };
            
            await supabase
                .from('religious_info')
                .upsert({
                    user_id: userId,
                    ...religiousUpdate
                });
        }
        
        res.json({
            message: 'تم تحديث الملف بنجاح',
            user: {
                id: updatedUser.id,
                full_name: updatedUser.full_name,
                email: updatedUser.email,
                gender: updatedUser.gender,
                country: updatedUser.country,
                city: updatedUser.city,
                about_me: updatedUser.about_me
            }
        });
        
    } catch (error) {
        console.error('Update profile error:', error);
        res.status(500).json({ error: 'فشل تحديث الملف' });
    }
});

// 12. الحصول على الإشعارات
app.get('/api/notifications', authenticate, async (req, res) => {
    try {
        const { limit = 20, offset = 0 } = req.query;
        
        const { data: notifications, error } = await supabase
            .from('notifications')
            .select('*')
            .eq('user_id', req.user.id)
            .order('created_at', { ascending: false })
            .range(offset, offset + limit - 1);
        
        if (error) throw error;
        
        res.json({ notifications });
        
    } catch (error) {
        console.error('Get notifications error:', error);
        res.status(500).json({ error: 'فشل في الحصول على الإشعارات' });
    }
});

// 13. وضع علامة على الإشعارات كمقروءة
app.post('/api/notifications/read', authenticate, async (req, res) => {
    try {
        const { notification_ids } = req.body;
        
        if (!notification_ids || !Array.isArray(notification_ids)) {
            return res.status(400).json({ error: 'معرفات الإشعارات مطلوبة' });
        }
        
        const { error } = await supabase
            .from('notifications')
            .update({ 
                is_read: true,
                read_at: new Date().toISOString()
            })
            .in('id', notification_ids)
            .eq('user_id', req.user.id);
        
        if (error) throw error;
        
        res.json({ message: 'تم تحديث حالة الإشعارات' });
        
    } catch (error) {
        console.error('Mark notifications as read error:', error);
        res.status(500).json({ error: 'فشل تحديث الإشعارات' });
    }
});

// 14. حذف حساب المستخدم
app.delete('/api/account', authenticate, async (req, res) => {
    try {
        const userId = req.user.id;
        
        // تحديث حالة الحساب إلى غير نشط بدلاً من الحذف
        const { error } = await supabase
            .from('profiles')
            .update({ 
                is_active: false,
                deleted_at: new Date().toISOString()
            })
            .eq('id', userId);
        
        if (error) throw error;
        
        // مسح الـ Cookie
        res.clearCookie('token');
        
        res.json({ message: 'تم إلغاء تنشيط حسابك بنجاح' });
        
    } catch (error) {
        console.error('Delete account error:', error);
        res.status(500).json({ error: 'فشل في إلغاء تنشيط الحساب' });
    }
});

// 15. تغيير كلمة المرور
app.post('/api/change-password', authenticate, async (req, res) => {
    try {
        const { current_password, new_password } = req.body;
        
        if (!current_password || !new_password) {
            return res.status(400).json({ error: 'كلمة المرور الحالية والجديدة مطلوبتان' });
        }
        
        if (new_password.length < 8) {
            return res.status(400).json({ error: 'كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل' });
        }
        
        // الحصول على كلمة المرور الحالية
        const { data: user, error: userError } = await supabase
            .from('profiles')
            .select('password_hash')
            .eq('id', req.user.id)
            .single();
        
        if (userError) throw userError;
        
        // التحقق من كلمة المرور الحالية
        const validPassword = await bcrypt.compare(current_password, user.password_hash);
        if (!validPassword) {
            return res.status(401).json({ error: 'كلمة المرور الحالية غير صحيحة' });
        }
        
        // تشفير كلمة المرور الجديدة
        const hashedPassword = await bcrypt.hash(new_password, 10);
        
        // تحديث كلمة المرور
        const { error: updateError } = await supabase
            .from('profiles')
            .update({ 
                password_hash: hashedPassword,
                updated_at: new Date().toISOString()
            })
            .eq('id', req.user.id);
        
        if (updateError) throw updateError;
        
        res.json({ message: 'تم تغيير كلمة المرور بنجاح' });
        
    } catch (error) {
        console.error('Change password error:', error);
        res.status(500).json({ error: 'فشل في تغيير كلمة المرور' });
    }
});

// ==================== معالجة الأخطاء ====================
app.use((err, req, res, next) => {
    console.error('Unhandled error:', err);
    
    if (err instanceof multer.MulterError) {
        if (err.code === 'LIMIT_FILE_SIZE') {
            return res.status(400).json({ error: 'حجم الملف كبير جداً. الحد الأقصى 5MB' });
        }
        return res.status(400).json({ error: 'خطأ في رفع الملف: ' + err.message });
    }
    
    res.status(500).json({ 
        error: 'حدث خطأ غير متوقع في الخادم',
        details: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
});

// ==================== بدء الخادم ====================
app.listen(PORT, () => {
    console.log(`
    🕌 منصة زفاف تعمل الآن!
    =========================
    🌐 العنوان: http://localhost:${PORT}
    📅 الوقت: ${new Date().toLocaleString('ar-SA')}
    ⚡ Cloudflare Keys: ${CF_KEYS.length} مفاتيح
    💳 Stripe: ${process.env.STRIPE_SECRET_KEY ? 'مفعل' : 'غير مفعل'}
    🗄️  Supabase: ${supabaseUrl ? 'متصل' : 'غير متصل'}
    
    ✅ API Endpoints:
    - POST   /api/register      - تسجيل مستخدم جديد
    - POST   /api/login         - تسجيل الدخول
    - POST   /api/logout        - تسجيل الخروج
    - GET    /api/me            - بيانات المستخدم الحالي
    - POST   /api/upload-photo  - رفع صورة مع فحص AI
    - POST   /api/match         - البحث عن مطابقات
    - POST   /api/request-view  - طلب مشاهدة صورة
    - PUT    /api/profile       - تحديث الملف الشخصي
    - GET    /api/notifications - الإشعارات
    - GET    /api/health        - فحص حالة الخادم
    `);
});

module.exports = app;