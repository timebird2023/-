/**
 * Zefaaf.net - Client-side Application JavaScript
 * جميع العمليات تتم عبر server.js وليس مباشرة مع Supabase
 */

// API Configuration
const API_BASE_URL = window.location.origin.includes('localhost') 
    ? 'http://localhost:3000/api' 
    : '/api';

// Common headers for API requests
const getHeaders = (includeToken = true) => {
    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
    
    if (includeToken) {
        const token = localStorage.getItem('token') || getCookie('token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
    }
    
    return headers;
};

// Helper to get cookie value
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// Error handler
const handleApiError = async (response) => {
    if (!response.ok) {
        try {
            const error = await response.json();
            throw new Error(error.error || `HTTP ${response.status}: ${response.statusText}`);
        } catch (e) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
    }
    return response.json();
};

// User Authentication
class AuthService {
    // Check if user is logged in
    static isLoggedIn() {
        return !!localStorage.getItem('token') || !!getCookie('token');
    }

    // Get current user
    static getCurrentUser() {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    }

    // Login
    static async login(email, password) {
        try {
            const response = await fetch(`${API_BASE_URL}/login`, {
                method: 'POST',
                headers: getHeaders(false),
                body: JSON.stringify({ email, password }),
                credentials: 'include'
            });

            const data = await handleApiError(response);
            
            // Store user data
            localStorage.setItem('user', JSON.stringify(data.user));
            localStorage.setItem('token', data.token);
            
            return data;
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    }

    // Register
    static async register(userData) {
        try {
            const response = await fetch(`${API_BASE_URL}/register`, {
                method: 'POST',
                headers: getHeaders(false),
                body: JSON.stringify(userData),
                credentials: 'include'
            });

            const data = await handleApiError(response);
            
            // Store user data
            localStorage.setItem('user', JSON.stringify(data.user));
            localStorage.setItem('token', data.token);
            
            return data;
        } catch (error) {
            console.error('Registration error:', error);
            throw error;
        }
    }

    // Logout
    static async logout() {
        try {
            await fetch(`${API_BASE_URL}/logout`, {
                method: 'POST',
                headers: getHeaders(),
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            localStorage.removeItem('user');
            localStorage.removeItem('token');
            localStorage.removeItem('searchParams');
            window.location.href = 'index.html';
        }
    }

    // Get current user profile
    static async getProfile() {
        try {
            const response = await fetch(`${API_BASE_URL}/me`, {
                headers: getHeaders(),
                credentials: 'include'
            });

            return await handleApiError(response);
        } catch (error) {
            console.error('Get profile error:', error);
            throw error;
        }
    }
}

// Photo Service
class PhotoService {
    // Upload photo with modesty check
    static async uploadPhoto(file, isProfile = false) {
        try {
            const formData = new FormData();
            formData.append('photo', file);
            formData.append('is_profile', isProfile.toString());

            const response = await fetch(`${API_BASE_URL}/upload-photo`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: formData,
                credentials: 'include'
            });

            return await handleApiError(response);
        } catch (error) {
            console.error('Photo upload error:', error);
            throw error;
        }
    }

    // Request to view a photo
    static async requestView(photoId) {
        try {
            const response = await fetch(`${API_BASE_URL}/request-view`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({ photo_id: photoId }),
                credentials: 'include'
            });

            return await handleApiError(response);
        } catch (error) {
            console.error('View request error:', error);
            throw error;
        }
    }
}

// Match Service
class MatchService {
    // Get matches based on search criteria
    static async findMatches(searchCriteria) {
        try {
            const response = await fetch(`${API_BASE_URL}/match`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(searchCriteria),
                credentials: 'include'
            });

            return await handleApiError(response);
        } catch (error) {
            console.error('Match search error:', error);
            throw error;
        }
    }
}

// Notification Service
class NotificationService {
    // Get notifications
    static async getNotifications(limit = 20, offset = 0) {
        try {
            const response = await fetch(`${API_BASE_URL}/notifications?limit=${limit}&offset=${offset}`, {
                headers: getHeaders(),
                credentials: 'include'
            });

            return await handleApiError(response);
        } catch (error) {
            console.error('Get notifications error:', error);
            throw error;
        }
    }

    // Mark notifications as read
    static async markAsRead(notificationIds) {
        try {
            const response = await fetch(`${API_BASE_URL}/notifications/read`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({ notification_ids: notificationIds }),
                credentials: 'include'
            });

            return await handleApiError(response);
        } catch (error) {
            console.error('Mark notifications error:', error);
            throw error;
        }
    }
}

// Payment Service
class PaymentService {
    // Create Stripe checkout session
    static async createCheckoutSession(priceId, successUrl, cancelUrl) {
        try {
            const response = await fetch(`${API_BASE_URL}/create-checkout-session`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({
                    price_id: priceId,
                    success_url: successUrl,
                    cancel_url: cancelUrl
                }),
                credentials: 'include'
            });

            return await handleApiError(response);
        } catch (error) {
            console.error('Create checkout session error:', error);
            throw error;
        }
    }
}

// UI Helper Functions
class UIHelper {
    // Show notification
    static showNotification(message, type = 'info', duration = 5000) {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.zefaaf-notification');
        existingNotifications.forEach(notification => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        });

        const notification = document.createElement('div');
        notification.className = `zefaaf-notification fixed top-4 left-4 z-50 px-6 py-3 rounded-lg shadow-lg text-white transition-all duration-300 ${
            type === 'success' ? 'bg-green-500' :
            type === 'error' ? 'bg-red-500' :
            type === 'warning' ? 'bg-yellow-500' :
            'bg-blue-500'
        }`;
        notification.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${
                    type === 'success' ? 'fa-check-circle' :
                    type === 'error' ? 'fa-exclamation-circle' :
                    type === 'warning' ? 'fa-exclamation-triangle' :
                    'fa-info-circle'
                } ml-3"></i>
                <span>${message}</span>
                <button class="mr-auto text-white/80 hover:text-white" onclick="this.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        notification.style.maxWidth = '400px';
        notification.style.wordBreak = 'break-word';

        document.body.appendChild(notification);

        // Auto remove after duration
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, duration);

        return notification;
    }

    // Show loading overlay
    static showLoading(message = 'جاري التحميل...', options = {}) {
        const overlay = document.createElement('div');
        overlay.className = 'zefaaf-loading-overlay fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center';
        overlay.id = 'zefaaf-loading-overlay';

        overlay.innerHTML = `
            <div class="bg-white rounded-xl p-8 text-center max-w-sm mx-4">
                <div class="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4"></div>
                <p class="text-gray-700 font-semibold mb-2">${message}</p>
                ${options.subMessage ? `<p class="text-gray-600 text-sm">${options.subMessage}</p>` : ''}
            </div>
        `;

        document.body.appendChild(overlay);
        return overlay;
    }

    // Hide loading overlay
    static hideLoading() {
        const overlay = document.getElementById('zefaaf-loading-overlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
            }, 300);
        }
    }

    // Format date
    static formatDate(dateString) {
        if (!dateString) return 'غير محدد';
        const date = new Date(dateString);
        return date.toLocaleDateString('ar-SA', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // Calculate age from birth date
    static calculateAge(birthDate) {
        if (!birthDate) return null;
        
        const today = new Date();
        const birth = new Date(birthDate);
        let age = today.getFullYear() - birth.getFullYear();
        const monthDiff = today.getMonth() - birth.getMonth();
        
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
            age--;
        }
        
        return age;
    }

    // Validate email
    static validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    // Validate password strength
    static validatePassword(password) {
        const minLength = 8;
        const hasUpperCase = /[A-Z]/.test(password);
        const hasLowerCase = /[a-z]/.test(password);
        const hasNumbers = /\d/.test(password);

        return {
            isValid: password.length >= minLength && (hasUpperCase || hasLowerCase) && hasNumbers,
            minLength,
            hasUpperCase,
            hasLowerCase,
            hasNumbers
        };
    }

    // Debounce function for search
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Create confirmation dialog
    static confirmDialog(message, confirmText = 'تأكيد', cancelText = 'إلغاء') {
        return new Promise((resolve) => {
            const dialog = document.createElement('div');
            dialog.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
            dialog.innerHTML = `
                <div class="bg-white rounded-xl p-6 max-w-md w-full">
                    <div class="mb-6">
                        <h3 class="text-lg font-bold text-gray-800 mb-2">تأكيد الإجراء</h3>
                        <p class="text-gray-600">${message}</p>
                    </div>
                    <div class="flex space-x-3 space-x-reverse">
                        <button class="btn-secondary flex-1" id="cancelBtn">${cancelText}</button>
                        <button class="btn-primary flex-1" id="confirmBtn">${confirmText}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(dialog);

            dialog.querySelector('#confirmBtn').onclick = () => {
                document.body.removeChild(dialog);
                resolve(true);
            };

            dialog.querySelector('#cancelBtn').onclick = () => {
                document.body.removeChild(dialog);
                resolve(false);
            };

            // Close on background click
            dialog.onclick = (e) => {
                if (e.target === dialog) {
                    document.body.removeChild(dialog);
                    resolve(false);
                }
            };
        });
    }
}

// Form Validation
class FormValidator {
    static validateRegistrationForm(formData) {
        const errors = {};

        // Required fields
        const requiredFields = ['email', 'password', 'full_name', 'gender', 'country', 'city'];
        requiredFields.forEach(field => {
            if (!formData[field] || formData[field].trim() === '') {
                errors[field] = 'هذا الحقل مطلوب';
            }
        });

        // Email validation
        if (formData.email && !UIHelper.validateEmail(formData.email)) {
            errors.email = 'البريد الإلكتروني غير صالح';
        }

        // Password validation
        if (formData.password) {
            const passwordValidation = UIHelper.validatePassword(formData.password);
            if (!passwordValidation.isValid) {
                errors.password = 'كلمة المرور يجب أن تكون 8 أحرف على الأقل وتحتوي على أرقام وحروف';
            }
        }

        // Password confirmation
        if (formData.password !== formData.confirm_password) {
            errors.confirm_password = 'كلمات المرور غير متطابقة';
        }

        // Age validation
        if (formData.birth_date) {
            const age = UIHelper.calculateAge(formData.birth_date);
            if (age < 18) {
                errors.birth_date = 'يجب أن يكون العمر 18 سنة على الأقل';
            }
            if (age > 100) {
                errors.birth_date = 'العمر غير صالح';
            }
        }

        return {
            isValid: Object.keys(errors).length === 0,
            errors
        };
    }
}

// Local Storage Manager
class StorageManager {
    static setSearchParams(params) {
        localStorage.setItem('searchParams', JSON.stringify(params));
    }

    static getSearchParams() {
        const params = localStorage.getItem('searchParams');
        return params ? JSON.parse(params) : {};
    }

    static setUserPreferences(preferences) {
        localStorage.setItem('userPreferences', JSON.stringify(preferences));
    }

    static getUserPreferences() {
        const prefs = localStorage.getItem('userPreferences');
        return prefs ? JSON.parse(prefs) : {};
    }

    static clearAll() {
        localStorage.clear();
    }
}

// Image Helper
class ImageHelper {
    static createBlurredImage(src, alt = '') {
        const img = document.createElement('img');
        img.src = src;
        img.alt = alt;
        img.className = 'w-full h-full object-cover blur-photo';
        return img;
    }

    static async createImagePreview(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsDataURL(file);
        });
    }

    static validateImageFile(file) {
        const maxSize = 5 * 1024 * 1024; // 5MB
        const allowedTypes = ['image/jpeg', 'image/png', 'image/jpg', 'image/gif', 'image/webp'];

        if (!allowedTypes.includes(file.type)) {
            return {
                isValid: false,
                error: 'نوع الملف غير مسموح. المسموح: JPG, PNG, GIF, WebP'
            };
        }

        if (file.size > maxSize) {
            return {
                isValid: false,
                error: 'حجم الملف كبير جداً. الحد الأقصى: 5MB'
            };
        }

        return { isValid: true };
    }
}

// Event Bus for component communication
class EventBus {
    constructor() {
        this.events = {};
    }

    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    }

    off(event, callback) {
        if (!this.events[event]) return;
        this.events[event] = this.events[event].filter(cb => cb !== callback);
    }

    emit(event, data) {
        if (!this.events[event]) return;
        this.events[event].forEach(callback => callback(data));
    }
}

// Initialize global event bus
window.ZefaafEventBus = new EventBus();

// Export all services and helpers
window.Zefaaf = {
    AuthService,
    PhotoService,
    MatchService,
    NotificationService,
    PaymentService,
    UIHelper,
    FormValidator,
    StorageManager,
    ImageHelper,
    EventBus: window.ZefaafEventBus,
    
    // Convenience methods
    async init() {
        try {
            // Check authentication status
            if (AuthService.isLoggedIn()) {
                try {
                    const profile = await AuthService.getProfile();
                    if (profile && profile.user) {
                        localStorage.setItem('user', JSON.stringify(profile.user));
                        
                        // Update UI elements if needed
                        document.querySelectorAll('[data-user-name]').forEach(el => {
                            el.textContent = profile.user.full_name;
                        });
                        
                        console.log('User logged in:', profile.user.full_name);
                    }
                } catch (error) {
                    console.warn('Failed to fetch user profile:', error);
                    // Clear invalid session
                    localStorage.removeItem('token');
                    localStorage.removeItem('user');
                }
            }
            
            // Add global error handler
            window.addEventListener('unhandledrejection', event => {
                console.error('Unhandled promise rejection:', event.reason);
                UIHelper.showNotification('حدث خطأ غير متوقع', 'error');
            });
            
            // Handle offline/online status
            window.addEventListener('online', () => {
                UIHelper.showNotification('تم استعادة الاتصال بالإنترنت', 'success');
            });
            
            window.addEventListener('offline', () => {
                UIHelper.showNotification('فقدان الاتصال بالإنترنت', 'error');
            });
            
        } catch (error) {
            console.error('Zefaaf init error:', error);
        }
    },
    
    // Common event handlers
    async handleLogout() {
        const confirmed = await UIHelper.confirmDialog('هل أنت متأكد من تسجيل الخروج؟', 'تسجيل الخروج', 'إلغاء');
        if (confirmed) {
            UIHelper.showLoading('جاري تسجيل الخروج...');
            await AuthService.logout();
        }
    },
    
    handleSearch(event) {
        if (event) event.preventDefault();
        const form = event ? event.target : document.getElementById('searchForm');
        if (!form) return;
        
        const formData = new FormData(form);
        const searchParams = {};
        
        for (const [key, value] of formData.entries()) {
            if (value) {
                searchParams[key] = value;
            }
        }
        
        StorageManager.setSearchParams(searchParams);
        window.location.href = 'dashboard.html';
    },
    
    // Check server health
    async checkHealth() {
        try {
            const response = await fetch(`${API_BASE_URL}/health`);
            return await response.json();
        } catch (error) {
            return { status: 'offline', error: error.message };
        }
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (window.Zefaaf && typeof window.Zefaaf.init === 'function') {
        window.Zefaaf.init();
    }
    
    // Auto-hide notifications when clicked
    document.addEventListener('click', (e) => {
        if (e.target.closest('.zefaaf-notification')) {
            e.target.closest('.zefaaf-notification').remove();
        }
    });
    
    // Handle browser back/forward
    window.addEventListener('popstate', () => {
        if (window.location.pathname.includes('dashboard.html')) {
            ZefaafEventBus.emit('refresh-matches');
        }
    });
});

// تأكد من تحميل Zefaaf عند بدء التطبيق
// هذه إضافة احتياطية للتعامل مع حالات التحميل المتأخر
if (window) {
    window.Zefaaf = window.Zefaaf;
    
    window.addEventListener('load', () => {
        if (window.Zefaaf && typeof window.Zefaaf.init === 'function' && 
            !window.Zefaaf._initialized) {
            window.Zefaaf.init();
            window.Zefaaf._initialized = true;
        }
    });
}