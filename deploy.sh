#!/usr/bin/env bash
# ==============================================================================
#  Empire Bot — سكريبت التثبيت والنشر التلقائي على خادم Ubuntu 22.04 LTS
# ==============================================================================
set -e

echo ""
echo "======================================================"
echo "   🚀 بدء تثبيت ونشر مشروع Empire Bot على السيرفر"
echo "======================================================"
echo ""

# 1. التحقق من صلاحيات root
if [ "$EUID" -ne 0 ]; then
  echo "❌ يرجى تشغيل السكريبت بصلاحيات root: sudo bash deploy.sh"
  exit 1
fi

PROJECT_DIR="/var/www/osmanli"

# التحقق من وجود المجلد
if [ ! -d "$PROJECT_DIR" ]; then
  echo "⚠️ المجلد $PROJECT_DIR غير موجود، جاري إنشاؤه..."
  mkdir -p "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# 2. تحديث الحزم وتثبيت المتطلبات الأساسية
echo "📦 [1/6] تحديث حزم النظام وتثبيت الأساسيات..."
apt update -y
apt install -y python3 python3-pip python3-venv git nginx curl ufw

# 3. تثبيت Node.js 20 LTS إذا لم يكن مثبتاً أو قديماً
echo "🟢 [2/6] التحقق من بيئة Node.js..."
NODE_VER=$(node -v 2>/dev/null || echo "v0")
MAJOR_VER=$(echo "$NODE_VER" | cut -d'.' -f1 | sed 's/v//')
if [ "$MAJOR_VER" -lt 18 ]; then
  echo "📥 تثبيت Node.js 20 LTS..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
fi
echo "✅ Node.js: $(node -v) | npm: $(npm -v)"

# 4. إعداد بيئة بايثون الافتراضية
echo "🐍 [3/6] إعداد بيئة Python الافتراضية وتثبيت المكتبات..."
if [ ! -d "$PROJECT_DIR/venv" ]; then
  python3 -m venv "$PROJECT_DIR/venv"
fi
"$PROJECT_DIR/venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

# 5. بناء لوحة التحكم (Frontend - Dashboard)
echo "⚛️  [4/6] تثبيت مكتبات الواجهة وبناء Dashboard (Vite)..."
cd "$PROJECT_DIR/dashboard"

if [ ! -f "$PROJECT_DIR/dashboard/.env" ]; then
  echo "⚠️ ملف dashboard/.env غير موجود، جاري إنشاء ملف افتراضي..."
  cat << 'EOF' > "$PROJECT_DIR/dashboard/.env"
VITE_FIREBASE_API_KEY=AIzaSyCbTAyhucCKYHaQGY-rBNAsvAFq8vHr8Qw
VITE_FIREBASE_AUTH_DOMAIN=mnahel-7c8e5.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=mnahel-7c8e5
VITE_FIREBASE_STORAGE_BUCKET=mnahel-7c8e5.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=133569875152
VITE_FIREBASE_APP_ID=1:133569875152:web:8123c9ee4917f745a3e2d5
VITE_BOT_API_URL=
EOF
fi

npm install
npm run build
cd "$PROJECT_DIR"

# 6. إعداد خدمة Systemd لخادم البوت
echo "⚙️  [5/6] إعداد خدمة النظام (Systemd Service)..."
cp "$PROJECT_DIR/empire-bot.service" /etc/systemd/system/empire-bot.service
systemctl daemon-reload
systemctl enable empire-bot
systemctl restart empire-bot

# 7. إعداد Nginx
echo "🌐 [6/6] إعداد خادم Nginx..."
cp "$PROJECT_DIR/nginx-empire.conf" /etc/nginx/sites-available/empire-bot
ln -sf /etc/nginx/sites-available/empire-bot /etc/nginx/sites-enabled/empire-bot
rm -f /etc/nginx/sites-enabled/default

# فحص صحة إعدادات Nginx
nginx -t
systemctl restart nginx

# إعداد الجدار الناري
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 'Nginx Full' >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

echo ""
echo "======================================================"
echo "   🎉 تم اكتمال النشر بنجاح على خادم Ubuntu!"
echo "======================================================"
echo ""

# فحص وجود مفتاح Firebase السري
if [ ! -f "$PROJECT_DIR/firebase_service_account.json" ]; then
  echo "⚠️  تنبيه مهم جداً:"
  echo "    ملف [firebase_service_account.json] غير موجود في $PROJECT_DIR."
  echo "    يرجى رفع ملف المفتاح السري إلى السيرفر في هذا المسار:"
  echo "    /var/www/osmanli/firebase_service_account.json"
  echo "    ثم أعد تشغيل الخدمة بالأمر:"
  echo "    systemctl restart empire-bot"
  echo ""
else
  echo "✅ ملف firebase_service_account.json موجود ويعمل."
fi

echo "حالة الخدمة الآن:"
systemctl is-active empire-bot && echo "🟢 Empire Bot Service: شغال ومفعل" || echo "🔴 Empire Bot Service: يحتاج فحص"
echo ""
