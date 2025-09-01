<?php
// Simple PHP server - All AI processing handled by Puter.js in browser
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['message'])) {
    header('Content-Type: application/json');
    
    $message = trim($_POST['message']);
    
    if (empty($message)) {
        echo json_encode(['error' => 'لا يمكن أن تكون الرسالة فارغة']);
        exit;
    }
    
    // All processing handled by Puter.js in the browser
    echo json_encode(['use_puter' => true, 'message' => $message]);
    exit;
}
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>بويكتا شات - مساعد ذكي</title>
    <!-- Puter.js SDK for complete free ecosystem -->
    <script src="https://js.puter.com/v2/"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #00c6ff 0%, #0072ff 50%, #00d4aa 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            transition: all 0.3s ease;
        }

        body.dark-mode {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        }

        body.dark-mode .chat-container {
            background: #2d3748;
            color: #e2e8f0;
        }

        body.dark-mode .chat-messages {
            background: #2d3748;
        }

        body.dark-mode .message.bot .message-content {
            background: #4a5568;
            color: #e2e8f0;
            border: 1px solid #4a5568;
        }

        body.dark-mode .chat-input {
            background: #4a5568;
            border: 2px solid #4a5568;
            color: #e2e8f0;
        }

        body.dark-mode .chat-input:focus {
            border-color: #00c6ff;
        }

        body.dark-mode .service-tab {
            background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
            color: #e2e8f0;
        }

        body.dark-mode .side-menu {
            background: #2d3748;
        }

        body.dark-mode .menu-item {
            color: #e2e8f0;
            border-bottom: 1px solid #4a5568;
        }

        body.dark-mode .menu-item:hover {
            background-color: #4a5568;
        }

        .chat-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            width: 90%;
            max-width: 800px;
            height: 80vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .chat-header {
            background: linear-gradient(135deg, #00c6ff 0%, #0072ff 50%, #00d4aa 100%);
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 20px 20px 0 0;
            position: relative;
        }

        .theme-toggle {
            position: absolute;
            right: 20px;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: background-color 0.3s ease;
        }

        .theme-toggle:hover {
            background-color: rgba(255, 255, 255, 0.3);
        }

        .developer-info {
            position: absolute;
            right: 70px;
            top: 50%;
            transform: translateY(-50%);
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(255, 255, 255, 0.1);
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
        }

        .developer-avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }

        .menu-button {
            position: absolute;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            padding: 5px;
            border-radius: 5px;
            transition: background-color 0.3s ease;
        }

        .menu-button:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }

        .hamburger {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .hamburger span {
            width: 20px;
            height: 2px;
            background-color: white;
            border-radius: 1px;
            transition: all 0.3s ease;
        }

        .menu-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        }

        .menu-overlay.active {
            opacity: 1;
            visibility: visible;
        }

        .side-menu {
            position: fixed;
            left: -300px;
            top: 0;
            width: 280px;
            height: 100%;
            background: white;
            z-index: 1001;
            transition: left 0.3s ease;
            box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
        }

        .side-menu.active {
            left: 0;
        }

        .menu-header {
            background: linear-gradient(135deg, #00c6ff 0%, #0072ff 50%, #00d4aa 100%);
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 18px;
            font-weight: 600;
        }

        .menu-items {
            padding: 20px 0;
        }

        .menu-item {
            display: flex;
            align-items: center;
            padding: 15px 20px;
            color: #333;
            text-decoration: none;
            border-bottom: 1px solid #f0f0f0;
            transition: background-color 0.3s ease;
        }

        .menu-item:hover {
            background-color: #f8f9fa;
        }

        .menu-item i {
            font-size: 20px;
            margin-left: 15px;
            width: 25px;
            text-align: center;
        }

        .close-menu {
            position: absolute;
            top: 15px;
            right: 15px;
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            padding: 5px;
        }

        .chat-header h1 {
            font-size: 28px;
            font-weight: 600;
            margin: 0;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .chat-header p {
            font-size: 14px;
            opacity: 0.9;
            margin-top: 5px;
        }

        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f8f9fa;
        }

        .message {
            margin-bottom: 15px;
            animation: fadeIn 0.3s ease-in;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            text-align: right;
        }

        .message.bot {
            text-align: left;
        }

        .message-content {
            display: inline-block;
            padding: 12px 16px;
            border-radius: 18px;
            max-width: 70%;
            word-wrap: break-word;
            font-size: 14px;
            line-height: 1.4;
        }

        .message.user .message-content {
            background: linear-gradient(135deg, #00c6ff 0%, #0072ff 50%, #00d4aa 100%);
            color: white;
        }

        .message.bot .message-content {
            background: white;
            color: #333;
            border: 1px solid #e1e5e9;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }

        .chat-input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #e1e5e9;
        }

        .chat-input-form {
            display: flex;
            gap: 12px;
            align-items: flex-end;
        }

        .services-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
            overflow-x: auto;
            padding: 5px;
        }

        .service-tab {
            background: linear-gradient(135deg, #00c6ff 0%, #0072ff 50%, #00d4aa 100%);
            color: white;
            border: none;
            border-radius: 20px;
            padding: 8px 16px;
            font-size: 12px;
            cursor: pointer;
            transition: transform 0.2s ease;
            white-space: nowrap;
            min-width: 80px;
        }

        .service-tab:hover {
            transform: scale(1.05);
        }

        .service-tab.active {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        }

        .chat-input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 25px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.3s ease;
            resize: none;
            min-height: 44px;
            max-height: 120px;
            font-family: inherit;
        }

        .chat-input:focus {
            border-color: #00c6ff;
        }

        .send-button {
            background: linear-gradient(135deg, #00c6ff 0%, #0072ff 50%, #00d4aa 100%);
            color: white;
            border: none;
            border-radius: 50%;
            width: 44px;
            height: 44px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            font-size: 18px;
        }

        .send-button:hover:not(:disabled) {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 198, 255, 0.4);
        }

        .send-button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        .loading {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #666;
            font-style: italic;
        }

        .loading-dots {
            display: inline-flex;
            gap: 2px;
        }

        .loading-dots span {
            width: 4px;
            height: 4px;
            border-radius: 50%;
            background: #00c6ff;
            animation: loadingDots 1.4s infinite both;
        }

        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }

        @keyframes loadingDots {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        .error-message {
            background: #fee;
            color: #c33;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #c33;
        }

        .welcome-message {
            text-align: center;
            color: #666;
            font-style: italic;
            margin-top: 40px;
        }

        @media (max-width: 768px) {
            .chat-container {
                width: 95%;
                height: 90vh;
                border-radius: 15px;
            }

            .chat-header {
                padding: 15px;
                border-radius: 15px 15px 0 0;
            }

            .chat-header h1 {
                font-size: 24px;
            }

            .message-content {
                max-width: 85%;
            }
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <button class="menu-button" id="menuButton">
                <div class="hamburger">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </button>
            <button class="theme-toggle" id="themeToggle" title="تبديل الوضع الليلي/النهاري">
                🌙
            </button>
            <h1>بويكتا شات</h1>
            <p>مساعد ذكي مدعوم بالذكاء الاصطناعي</p>
        </div>
        
        <div class="chat-messages" id="chatMessages">
            <div class="welcome-message">
                أهلاً بك في بويكتا شات! ابدأ محادثة مع مساعدك الذكي المجاني.
            </div>
        </div>
        
        <div class="chat-input-container">
            <div class="services-tabs" id="servicesTabs">
                <button class="service-tab active" onclick="switchService('chat')">💬 دردشة ذكية</button>
                <button class="service-tab" onclick="switchService('imggen')">🎨 توليد صور</button>
                <button class="service-tab" onclick="switchService('qr')">📱 QR كود</button>
                <button class="service-tab" onclick="switchService('image')">🎨 تحرير صور</button>
                <button class="service-tab" onclick="switchService('files')">📁 إدارة ملفات</button>
            </div>
            
            <!-- Chat Service -->
            <form class="chat-input-form" id="chatForm" style="display: flex;">
                <textarea 
                    class="chat-input" 
                    id="messageInput" 
                    placeholder="اكتب رسالتك هنا..." 
                    rows="1"
                    required
                ></textarea>
                <button type="submit" class="send-button" id="sendButton">
                    ➤
                </button>
            </form>
            
            <!-- Image Editor Service -->
            <div id="imageService" style="display: none;">
                <input type="file" id="imageInput" accept="image/*" style="margin-bottom: 10px;">
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button onclick="applyImageFilter('blur')" class="service-tab">🌫️ ضبابي</button>
                    <button onclick="applyImageFilter('bright')" class="service-tab">☀️ مضيء</button>
                    <button onclick="applyImageFilter('dark')" class="service-tab">🌙 داكن</button>
                    <button onclick="applyImageFilter('sepia')" class="service-tab">🏜️ سيبيا</button>
                </div>
                <canvas id="imageCanvas" style="max-width: 100%; margin-top: 10px; border: 1px solid #ddd;"></canvas>
            </div>
            
            
            <!-- QR Code Service -->
            <div id="qrService" style="display: none;">
                <input type="text" id="qrInput" placeholder="أدخل النص أو الرابط لإنشاء QR كود..." style="width: 100%; padding: 10px; margin-bottom: 10px; border: 2px solid #e1e5e9; border-radius: 10px;">
                <button onclick="generateQR()" class="service-tab" style="width: 100%; margin-bottom: 10px;">🎯 إنشاء QR كود</button>
                <div id="qrResult" style="text-align: center;"></div>
            </div>
            
            <!-- File Manager Service -->
            <div id="filesService" style="display: none;">
                <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px;">
                    <button onclick="createNewFile()" class="service-tab">📄 ملف جديد</button>
                    <button onclick="listFiles()" class="service-tab">📋 عرض الملفات</button>
                    <button onclick="uploadFile()" class="service-tab">📤 رفع ملف</button>
                </div>
                <div id="filesList" style="max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 10px;"></div>
            </div>
            
            <!-- Image Generation Service -->
            <div id="imggenService" style="display: none;">
                <textarea id="imgPrompt" placeholder="اكتب وصف الصورة التي تريد توليدها..." style="width: 100%; height: 80px; margin-bottom: 10px; padding: 10px; border: 2px solid #e1e5e9; border-radius: 10px; resize: vertical;"></textarea>
                <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px;">
                    <button onclick="generateImage('realistic')" class="service-tab">📷 واقعي</button>
                    <button onclick="generateImage('artistic')" class="service-tab">🎨 فني</button>
                    <button onclick="generateImage('cartoon')" class="service-tab">🎭 كرتوني</button>
                    <button onclick="generateImage('abstract')" class="service-tab">🌈 تجريدي</button>
                </div>
                <div id="imageResult" style="text-align: center; padding: 20px; border: 2px dashed #ddd; border-radius: 10px;">
                    اكتب وصف الصورة واختر نمط التوليد
                </div>
            </div>
        </div>
    </div>

    <!-- Side Menu -->
    <div class="menu-overlay" id="menuOverlay"></div>
    <div class="side-menu" id="sideMenu">
        <div class="menu-header">
            <button class="close-menu" id="closeMenu">×</button>
            <div style="display: flex; align-items: center; gap: 10px; justify-content: center;">
                <img src="attached_assets/Picsart_25-05-27_18-18-40-609_1756731249491.png" alt="Younes Laldji" style="width: 40px; height: 40px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, 0.3);">
                <div>
                    <div style="font-size: 16px; font-weight: bold;">بويكتا شات</div>
                    <div style="font-size: 12px; opacity: 0.9;">by Younes Laldji</div>
                </div>
            </div>
        </div>
        <div class="menu-items">
            <a href="https://t.me/boyta28" target="_blank" class="menu-item">
                <i>📱</i>
                قناة تلغرام
            </a>
            <a href="#" onclick="showPrivacyPolicy()" class="menu-item">
                <i>📋</i>
                سياسة الاستخدام
            </a>
            <a href="#" onclick="showAbout()" class="menu-item">
                <i>ℹ️</i>
                معلومات عن الموقع
            </a>
            <a href="https://www.facebook.com/2007younes" target="_blank" class="menu-item">
                <i>🚀</i>
                حساب فيسبوك
            </a>
            <a href="#" onclick="showPuterFeatures()" class="menu-item">
                <i>🔧</i>
                أدوات Puter المجانية
            </a>
        </div>
    </div>

    <script src="https://js.puter.com/v2/"></script>
    <script>
        const chatForm = document.getElementById('chatForm');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const chatMessages = document.getElementById('chatMessages');
        const menuButton = document.getElementById('menuButton');
        const sideMenu = document.getElementById('sideMenu');
        const menuOverlay = document.getElementById('menuOverlay');
        const closeMenu = document.getElementById('closeMenu');
        const engineSelector = document.getElementById('engineSelector');

        // Auto-resize textarea
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        // Handle Enter key (send on Enter, new line on Shift+Enter)
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatForm.dispatchEvent(new Event('submit'));
            }
        });

        // Clear welcome message when first message is sent
        function clearWelcomeMessage() {
            const welcomeMsg = chatMessages.querySelector('.welcome-message');
            if (welcomeMsg) {
                welcomeMsg.remove();
            }
        }

        // Add message to chat
        function addMessage(content, isUser = false, isError = false) {
            clearWelcomeMessage();
            
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
            
            if (isError) {
                messageDiv.innerHTML = `<div class="error-message">${content}</div>`;
            } else {
                const messageContent = document.createElement('div');
                messageContent.className = 'message-content';
                messageContent.textContent = content;
                messageDiv.appendChild(messageContent);
            }
            
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Show loading indicator
        function showLoading() {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message bot loading';
            loadingDiv.id = 'loadingIndicator';
            loadingDiv.innerHTML = `
                <div class="message-content">
                    <span>الذكاء الاصطناعي يفكر</span>
                    <div class="loading-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            `;
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Remove loading indicator
        function hideLoading() {
            const loadingIndicator = document.getElementById('loadingIndicator');
            if (loadingIndicator) {
                loadingIndicator.remove();
            }
        }

        // Handle form submission
        chatForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const message = messageInput.value.trim();
            if (!message) return;
            
            // Add user message
            addMessage(message, true);
            
            // Clear input and reset height
            messageInput.value = '';
            messageInput.style.height = 'auto';
            
            // Disable form
            sendButton.disabled = true;
            messageInput.disabled = true;
            
            // Show loading
            showLoading();
            
            try {
                const formData = new FormData();
                formData.append('message', message);
                formData.append('engine', engineSelector.value);
                
                const response = await fetch('index.php', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                hideLoading();
                
                if (data.error) {
                    addMessage(data.error, false, true);
                } else if (data.use_puter) {
                    // استخدام Puter.js للمعالجة المجانية
                    try {
                        showLoading();
                        const systemPrompt = "أنت مساعد ذكي ومفيد. يجب أن ترد دائماً باللغة العربية. كن مهذباً ومساعداً في إجاباتك.";
                        const fullPrompt = systemPrompt + "\n\nالمستخدم: " + data.message;
                        
                        const puterResponse = await puter.ai.chat(fullPrompt);
                        hideLoading();
                        
                        // إضافة زر حساب الفيسبوك بدلاً من نص محرك Puter.js
                        const messageDiv = document.createElement('div');
                        messageDiv.className = 'message bot';
                        messageDiv.innerHTML = `
                            <div class="message-content">
                                ${puterResponse}
                                <div style="margin-top: 10px; text-align: center;">
                                    <a href="https://www.facebook.com/2007younes" target="_blank" 
                                       style="background: #1877f2; color: white; padding: 8px 16px; 
                                              border-radius: 20px; text-decoration: none; font-size: 12px;
                                              display: inline-block; transition: background 0.3s;">
                                        👤 حساب المستخدم
                                    </a>
                                </div>
                            </div>
                        `;
                        chatMessages.appendChild(messageDiv);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    } catch (puterError) {
                        hideLoading();
                        addMessage('خطأ في Puter.js: ' + puterError.message + '\n\nيرجى المحاولة مرة أخرى أو استخدام محرك آخر.', false, true);
                    }
                } else if (data.reply) {
                    addMessage(data.reply, false);
                } else {
                    addMessage('تنسيق الاستجابة غير متوقع', false, true);
                }
                
            } catch (error) {
                hideLoading();
                addMessage('خطأ في الشبكة: ' + error.message, false, true);
            } finally {
                // Re-enable form
                sendButton.disabled = false;
                messageInput.disabled = false;
                messageInput.focus();
            }
        });

        // Menu functionality
        function openMenu() {
            sideMenu.classList.add('active');
            menuOverlay.classList.add('active');
        }

        function closeMenuFn() {
            sideMenu.classList.remove('active');
            menuOverlay.classList.remove('active');
        }

        menuButton.addEventListener('click', openMenu);
        closeMenu.addEventListener('click', closeMenuFn);
        menuOverlay.addEventListener('click', closeMenuFn);

        // Modal functions
        function showPrivacyPolicy() {
            closeMenuFn();
            alert(`سياسة الاستخدام - محا شات

1. الغرض من الخدمة:
   - توفير مساعد ذكي للمحادثة والاستفسارات
   - خدمة مجانية لجميع المستخدمين

2. شروط الاستخدام:
   - عدم استخدام الخدمة لأغراض غير قانونية
   - احترام الآداب العامة في المحادثات
   - عدم مشاركة معلومات شخصية حساسة

3. الخصوصية:
   - نحن نحترم خصوصيتك
   - لا نحتفظ بسجل دائم للمحادثات
   - البيانات تستخدم فقط لتحسين الخدمة

4. إخلاء المسؤولية:
   - الخدمة مقدمة كما هي
   - لا نضمن دقة جميع الإجابات
   - المسؤولية تقع على المستخدم في كيفية استخدام المعلومات

للاستفسارات: تواصل معنا عبر قناة تلغرام`);
        }

        function showAbout() {
            closeMenuFn();
            alert(`معلومات عن محا شات

🤖 ما هو محا شات؟
محا شات هو مساعد ذكي مجاني يستخدم تقنيات الذكاء الاصطناعي لمساعدتك في الإجابة على أسئلتك وحل مشاكلك.

✨ المميزات:
• إجابات سريعة ودقيقة
• دعم اللغة العربية بشكل كامل
• واجهة بسيطة وسهلة الاستخدام
• مجاني تماماً

🎯 كيف تستفيد؟
• اطرح أي سؤال يخطر ببالك
• اطلب المساعدة في أي موضوع
• استخدمه كمساعد شخصي ذكي

📱 تابعنا:
للحصول على آخر التحديثات والنصائح، تابع قناتنا على تلغرام

💡 نصائح للاستخدام الأمثل:
• كن واضحاً في أسئلتك
• قدم تفاصيل كافية
• جرب أسئلة متنوعة

شكراً لاستخدامك بويكتا شات! 🙏`);
        }



        // وظائف Puter.js المتقدمة - مجانية 100%
        async function showPuterFeatures() {
            closeMenuFn();
            try {
                const userInfo = await puter.auth.getUser();
                alert(`🔧 أدوات Puter المجانية

👤 **معلومات المستخدم:**
الاسم: ${userInfo.username || 'غير معرف'}

🔥 **المميزات المتاحة:**
• نظام ملفات مجاني في السحابة
• تطبيقات ويب مجانية  
• ذكاء اصطناعي بدون قيود
• معالجة النصوص والصور
• مشاركة الملفات

🎆 **استفد من القائمة لتجربة المزيد!**`);
            } catch (error) {
                alert('🚀 نظام Puter مجاني 100% متاح في جميع المميزات!');
            }
        }

        async function createPuterFile() {
            closeMenuFn();
            try {
                const fileName = prompt('📝 أدخل اسم الملف (مجاني):', 'ملف-جديد.txt');
                if (fileName) {
                    const content = prompt('📝 محتوى الملف:', 'هذا ملف مجاني من بويكتا شات!');
                    
                    await puter.fs.write(fileName, content || 'ملف فارغ');
                    alert(`✅ تم إنشاء الملف "${fileName}" بنجاح!

🎆 يمكنك الوصول إليه من أي مكان عبر Puter!`);
                }
            } catch (error) {
                alert('❗ خطأ في إنشاء الملف: ' + error.message);
            }
        }

        function showFreeApps() {
            closeMenuFn();
            alert(`🎮 تطبيقات مجانية من Puter

💻 **محرر النصوص**
• محرر متقدم مجاني
• يدعم جميع صيغ الملفات

🎨 **محرر الصور**  
• تعديل صور مجاني
• فلاتر وتأثيرات

📁 **مدير الملفات**
• تنظيم الملفات في السحابة
• مشاركة آمنة

🎵 **مشغل الموسيقى**
• تشغيل ملفات الصوت
• قوائم تشغيل مجانية

🔄 **استفد من puter.com مباشرة للحصول على جميع التطبيقات!**`);
        }

        // إدارة الخدمات المتعددة
        let currentService = 'chat';
        
        function switchService(service) {
            // إخفاء جميع الخدمات
            document.getElementById('chatForm').style.display = 'none';
            document.getElementById('imageService').style.display = 'none';
            document.getElementById('qrService').style.display = 'none';
            document.getElementById('filesService').style.display = 'none';
            document.getElementById('imggenService').style.display = 'none';
            
            // إزالة التحديد من جميع الأزرار
            document.querySelectorAll('.service-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // عرض الخدمة المحددة
            currentService = service;
            switch(service) {
                case 'chat':
                    document.getElementById('chatForm').style.display = 'flex';
                    messageInput.focus();
                    break;
                case 'image':
                    document.getElementById('imageService').style.display = 'block';
                    break;
                case 'qr':
                    document.getElementById('qrService').style.display = 'block';
                    break;
                case 'files':
                    document.getElementById('filesService').style.display = 'block';
                    listFiles();
                    break;
                case 'imggen':
                    document.getElementById('imggenService').style.display = 'block';
                    break;
            }
            
            // تحديد الزر النشط
            event.target.classList.add('active');
        }
        
        // خدمة تحرير الصور
        function applyImageFilter(filterType) {
            const input = document.getElementById('imageInput');
            const canvas = document.getElementById('imageCanvas');
            const ctx = canvas.getContext('2d');
            
            if (!input.files[0]) {
                alert('يرجى اختيار صورة أولاً!');
                return;
            }
            
            const img = new Image();
            img.onload = function() {
                canvas.width = img.width;
                canvas.height = img.height;
                
                // تطبيق الفلتر
                switch(filterType) {
                    case 'blur':
                        ctx.filter = 'blur(5px)';
                        break;
                    case 'bright':
                        ctx.filter = 'brightness(150%)';
                        break;
                    case 'dark':
                        ctx.filter = 'brightness(50%)';
                        break;
                    case 'sepia':
                        ctx.filter = 'sepia(100%)';
                        break;
                    default:
                        ctx.filter = 'none';
                }
                
                ctx.drawImage(img, 0, 0);
                addMessage(`تم تطبيق فلتر ${filterType} على الصورة بنجاح! 🎨`);
            };
            
            img.src = URL.createObjectURL(input.files[0]);
        }
        
        
        
        // خدمة QR Code
        function generateQR() {
            const qrInput = document.getElementById('qrInput');
            const qrResult = document.getElementById('qrResult');
            const text = qrInput.value.trim();
            
            if (!text) {
                alert('يرجى إدخال نص أو رابط!');
                return;
            }
            
            // استخدام خدمة QR مجانية
            const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(text)}`;
            qrResult.innerHTML = `
                <img src="${qrUrl}" alt="QR Code" style="max-width: 200px;">
                <p>تم إنشاء QR كود بنجاح! 📱</p>
                <a href="${qrUrl}" download="qrcode.png" class="service-tab">💾 تحميل الصورة</a>
            `;
            addMessage(`✅ تم إنشاء QR كود للنص: "${text}"`);
        }
        
        // خدمة إدارة الملفات
        async function createNewFile() {
            try {
                const fileName = prompt('اسم الملف:', 'ملف-جديد.txt');
                if (fileName) {
                    const content = prompt('محتوى الملف:', 'مرحباً من بويكتا شات!');
                    await puter.fs.write(fileName, content || '');
                    addMessage(`📄 تم إنشاء الملف "${fileName}" بنجاح!`);
                    listFiles();
                }
            } catch (error) {
                addMessage(`❌ خطأ في إنشاء الملف: ${error.message}`);
            }
        }
        
        async function listFiles() {
            try {
                const files = await puter.fs.readdir('/');
                const filesList = document.getElementById('filesList');
                
                if (files.length === 0) {
                    filesList.innerHTML = '<p>لا توجد ملفات. قم بإنشاء ملف جديد!</p>';
                } else {
                    filesList.innerHTML = files.map(file => `
                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 5px; border-bottom: 1px solid #eee;">
                            <span>📄 ${file.name}</span>
                            <div>
                                <button onclick="readFile('${file.name}')" class="service-tab" style="font-size: 10px; padding: 4px 8px;">📖 قراءة</button>
                                <button onclick="deleteFile('${file.name}')" class="service-tab" style="font-size: 10px; padding: 4px 8px; background: #dc3545;">🗑️ حذف</button>
                            </div>
                        </div>
                    `).join('');
                }
            } catch (error) {
                document.getElementById('filesList').innerHTML = '<p>خطأ في تحميل الملفات</p>';
            }
        }
        
        async function readFile(fileName) {
            try {
                const content = await puter.fs.read(fileName);
                addMessage(`📖 محتوى الملف "${fileName}":\\n\\n${content}`);
            } catch (error) {
                addMessage(`❌ خطأ في قراءة الملف: ${error.message}`);
            }
        }
        
        async function deleteFile(fileName) {
            if (confirm(`هل تريد حذف الملف "${fileName}"؟`)) {
                try {
                    await puter.fs.delete(fileName);
                    addMessage(`🗑️ تم حذف الملف "${fileName}" بنجاح!`);
                    listFiles();
                } catch (error) {
                    addMessage(`❌ خطأ في حذف الملف: ${error.message}`);
                }
            }
        }
        
        function uploadFile() {
            const input = document.createElement('input');
            input.type = 'file';
            input.onchange = async function(e) {
                const file = e.target.files[0];
                if (file) {
                    try {
                        const content = await file.text();
                        await puter.fs.write(file.name, content);
                        addMessage(`📤 تم رفع الملف "${file.name}" بنجاح!`);
                        listFiles();
                    } catch (error) {
                        addMessage(`❌ خطأ في رفع الملف: ${error.message}`);
                    }
                }
            };
            input.click();
        }

        // خدمة توليد الصور من النص - مجانية 100%
        function generateImage(style) {
            const promptInput = document.getElementById('imgPrompt');
            const imageResult = document.getElementById('imageResult');
            const prompt = promptInput.value.trim();
            
            if (!prompt) {
                alert('يرجى إدخال وصف للصورة أولاً!');
                return;
            }
            
            // تحسين النص حسب النمط المختار
            let enhancedPrompt = prompt;
            switch(style) {
                case 'realistic':
                    enhancedPrompt = `realistic photo of ${prompt}, high quality, professional photography`;
                    break;
                case 'artistic':
                    enhancedPrompt = `artistic painting of ${prompt}, beautiful art style, detailed artwork`;
                    break;
                case 'cartoon':
                    enhancedPrompt = `cartoon illustration of ${prompt}, colorful, cute animation style`;
                    break;
                case 'abstract':
                    enhancedPrompt = `abstract art of ${prompt}, creative, modern art style`;
                    break;
            }
            
            // عرض حالة التحميل
            imageResult.innerHTML = `
                <div style="padding: 40px;">
                    <div style="margin-bottom: 20px;">🎨 جاري توليد الصورة...</div>
                    <div style="width: 100%; background: #f0f0f0; border-radius: 10px; overflow: hidden;">
                        <div style="width: 0%; height: 6px; background: linear-gradient(135deg, #00c6ff 0%, #0072ff 50%, #00d4aa 100%); transition: width 3s ease;" id="progressBar"></div>
                    </div>
                </div>
            `;
            
            // تحريك شريط التقدم
            setTimeout(() => {
                document.getElementById('progressBar').style.width = '100%';
            }, 100);
            
            // استخدام خدمة مجانية لتوليد الصور
            const imageUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(enhancedPrompt)}?width=512&height=512&seed=${Math.floor(Math.random() * 1000000)}`;
            
            setTimeout(() => {
                imageResult.innerHTML = `
                    <div style="text-align: center;">
                        <img src="${imageUrl}" alt="صورة مولدة" style="max-width: 100%; max-height: 400px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                        <div style="margin: 15px 0;">
                            <strong>🎯 الوصف:</strong> ${prompt}
                        </div>
                        <div style="margin: 10px 0;">
                            <strong>🎨 النمط:</strong> ${style === 'realistic' ? 'واقعي' : style === 'artistic' ? 'فني' : style === 'cartoon' ? 'كرتوني' : 'تجريدي'}
                        </div>
                        <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
                            <a href="${imageUrl}" download="generated_image.jpg" class="service-tab" style="text-decoration: none;">💾 تحميل الصورة</a>
                            <button onclick="generateImage('${style}')" class="service-tab">🔄 توليد أخرى</button>
                            <button onclick="shareImage('${imageUrl}', '${prompt}')" class="service-tab">📤 مشاركة</button>
                        </div>
                    </div>
                `;
                
                addMessage(`✅ تم توليد صورة "${prompt}" بنمط ${style === 'realistic' ? 'واقعي' : style === 'artistic' ? 'فني' : style === 'cartoon' ? 'كرتوني' : 'تجريدي'} بنجاح! 🎨`);
            }, 3000);
        }
        
        function shareImage(imageUrl, prompt) {
            if (navigator.share) {
                navigator.share({
                    title: 'صورة مولدة من بويكتا شات',
                    text: `صورة مولدة بالذكاء الاصطناعي: ${prompt}`,
                    url: imageUrl
                });
            } else {
                // نسخ الرابط للحافظة
                navigator.clipboard.writeText(imageUrl).then(() => {
                    alert('تم نسخ رابط الصورة للحافظة! 📋');
                });
            }
        }

        // Theme toggle functionality
        const themeToggle = document.getElementById('themeToggle');
        const body = document.body;
        
        // Load saved theme
        const savedTheme = localStorage.getItem('theme') || 'light';
        if (savedTheme === 'dark') {
            body.classList.add('dark-mode');
            themeToggle.innerHTML = '☀️';
        }
        
        themeToggle.addEventListener('click', function() {
            body.classList.toggle('dark-mode');
            
            if (body.classList.contains('dark-mode')) {
                themeToggle.innerHTML = '☀️';
                localStorage.setItem('theme', 'dark');
                addMessage('🌙 تم تفعيل الوضع الليلي');
            } else {
                themeToggle.innerHTML = '🌙';
                localStorage.setItem('theme', 'light');
                addMessage('☀️ تم تفعيل الوضع النهاري');
            }
        });

        // Focus on input when page loads
        window.addEventListener('load', async function() {
            messageInput.focus();
            
            // تهيئة Puter SDK
            try {
                await puter.auth.getUser();
                console.log('🚀 Puter SDK ready!');
            } catch (error) {
                console.log('🔄 Puter SDK initializing...');
            }
        });
    </script>
</body>
</html>
