// استيراد مكتبة fetch لإجراء طلبات HTTP
const fetch = require('node-fetch');

// ----------------------------------------------------
// !!! أهم خطوة: قم بتغيير هذا الرابط إلى رابط مشروعك الفعلي على Replit
const TARGET_URL = 'https://replit.com/@timebird2015/EduBotAI'; 
// ----------------------------------------------------

/**
 * دالة Vercel Serverless Function الرئيسية
 * Vercel ستستدعي هذه الدالة عبر المسار /api/pinger بانتظام.
 */
module.exports = async (req, res) => {
    console.log(`[${new Date().toISOString()}] بدء عملية تنبيه مشروع Replit...`);

    try {
        // إرسال طلب GET بسيط إلى رابط Replit
        const response = await fetch(TARGET_URL);

        if (response.ok) {
            const statusMessage = `نجاح: تم تنبيه Replit بنجاح. حالة الاستجابة: ${response.status}`;
            console.log(statusMessage);
            
            // الرد على Vercel بأن العملية تمت بنجاح
            res.status(200).json({ 
                success: true, 
                message: statusMessage 
            });
        } else {
            const errorMessage = `فشل التنبيه: Replit استجاب بحالة خطأ: ${response.status}`;
            console.error(errorMessage);
            
            // الرد بحالة 500 في حال وجود خطأ في الخادم المستهدف
            res.status(500).json({ 
                success: false, 
                message: errorMessage 
            });
        }
    } catch (error) {
        const networkError = `خطأ شبكة/اتصال أثناء محاولة التنبيه: ${error.message}`;
        console.error(networkError);

        // الرد بحالة 500 لخطأ في الاتصال
        res.status(500).json({ 
            success: false, 
            message: networkError 
        });
    }
};
