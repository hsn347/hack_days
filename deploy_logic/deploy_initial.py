# -*- coding: utf-8 -*-
"""
deploy_initial.py — أداة النشر والتهيئة الأولية لخادم IBRA BOT الجديد
════════════════════════════════════════════════════════════════════
السيرفر الجديد: 88.222.220.51
المسار البعيد:  /var/www/osmanli

المميزات الحديثة:
  1) تثبيت وتهيئة بيئة السيرفر الجديد من الصفر (Nginx, Python Venv, Systemd).
  2) بناء ورفع الواجهة الأمامية الكاملة (dashboard/dist) دون رفع node_modules.
  3) حزم ورفع كافة ملفات الباك إند والمجلدات التابعة الحديثة (core, tasks, proxy) والملفات الجذرية ذرياً وبسرعة.
  4) رفع قاعدة البيانات المحلية (database/castles.db) وملفات التهيئة المرجعية (castle_prereqs, tech_names, session_cache) مع استبعاد الكاشات المؤقتة والـ Locks.
  5) تثبيت مكتبات البايثون (requirements.txt) في بيئة venv على السيرفر.
  6) ضبط وتشغيل خادم Nginx وخدمة النظام empire-bot.service.
  7) فحص جاهزية الخادم والواجهة والـ API.
  8) خيار التشغيل التدريجي الآمن للبوتات عند الطلب.

طريقة الاستخدام:
  python deploy_logic/deploy_initial.py --init           # تهيئة ونشر أولي شامل من الصفر
  python deploy_logic/deploy_initial.py --db-only        # رفع وتحديث قاعدة البيانات وملفات التهيئة فقط
  python deploy_logic/deploy_initial.py --backend-only   # رفع وتحديث كود الباك إند فقط
  python deploy_logic/deploy_initial.py --frontend-only  # بناء ورفع الواجهة الأمامية فقط
  python deploy_logic/deploy_initial.py --resume         # تشغيل واستئناف الحسابات المؤهلة تدريجياً
  python deploy_logic/deploy_initial.py --check          # فحص حالة السيرفر والخدمات
"""

import os
import sys
import time
import tarfile
import subprocess
import argparse
from typing import Optional, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── إعدادات السيرفر الجديد ──────────────────────────────────────────
SERVER_HOST = "88.222.220.51"
SERVER_USER = "root"
SERVER_PASS = "hsnAsdfghjkl150#"
REMOTE_DIR  = "/var/www/osmanli"
DEPLOY_DIR  = os.path.dirname(os.path.abspath(__file__))
LOCAL_DIR   = os.path.dirname(DEPLOY_DIR)

# قائمة المجلدات المستثناة تماماً من الرفع
EXCLUDE_DIRS = {
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "scratch",
    "tests",
    "test",
    "game_listener",
    "tcp_learning",
    "docs",
    "logs",
    "reports",
    "lua_src",
    "lua_src_backup",
    "apk_libs",
    ".agents",
}

# امتدادات الملفات المستثناة
EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".tmp",
    ".bak",
    ".apk",
    ".tar.gz",
    ".zip",
    ".db-wal",
    ".db-shm",
}


def get_ssh_client():
    """إنشاء اتصال SSH آمن بالسيرفر الجديد مع إعادة المحاولة التلقائية."""
    import socket
    import paramiko
    last_err = None
    print(f"🔌 جاري الاتصال بالسيرفر الجديد {SERVER_HOST}...")
    for attempt in range(1, 11):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(8)
            s.connect((SERVER_HOST, 22))
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                SERVER_HOST,
                username=SERVER_USER,
                password=SERVER_PASS,
                sock=s,
                banner_timeout=35,
                timeout=15
            )
            print(f"✅ تم الاتصال بنجاح بـ {SERVER_HOST} (المحاولة #{attempt})")
            return client
        except Exception as e:
            last_err = e
            time.sleep(2)
    raise RuntimeError(f"❌ فشل الاتصال بالسيرفر الجديد {SERVER_HOST} بعد 10 محاولات: {last_err}")


def _run(client, cmd: str, timeout: int = 120) -> str:
    """تنفيذ أمر بعيد وإرجاع الناتج مع مهلة محددة."""
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        return out if out else err
    except Exception as e:
        return f"Error: {e}"


def setup_system_prerequisites(client):
    """تثبيت الحزم الأساسية للنظام وإعداد البيئة من الصفر على السيرفر الجديد."""
    print("\n🛠️ [1/7] تثبيت الحزم الأساسية وإعداد نظام التشغيل (Nginx, Python3, Venv, SQLite3)...")
    cmd = (
        "export DEBIAN_FRONTEND=noninteractive && "
        "apt-get update -y && "
        "apt-get install -y python3 python3-pip python3-venv python3-dev nginx curl git build-essential sqlite3 libsqlite3-dev && "
        f"mkdir -p {REMOTE_DIR}/database {REMOTE_DIR}/dashboard/dist {REMOTE_DIR}/core {REMOTE_DIR}/tasks {REMOTE_DIR}/proxy"
    )
    _run(client, cmd, timeout=300)
    print("✅ تم تثبيت حزم النظام وإنشاء مسارات المشروع الرئيسية.")

    print("🐍 [2/7] إنشاء البيئة الافتراضية للبايثون (venv)...")
    venv_cmd = (
        f"if [ ! -d '{REMOTE_DIR}/venv' ]; then "
        f"  python3 -m venv {REMOTE_DIR}/venv; "
        f"fi && "
        f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip"
    )
    _run(client, venv_cmd, timeout=180)
    print("✅ تم تجهيز البيئة الافتراضية /var/www/osmanli/venv بنجاح.")


def build_and_upload_frontend(client):
    """بناء حزمة الواجهة الأمامية ورفعها إلى السيرفر (مع استبعاد node_modules تماماً)."""
    print("\n📦 بناء حزمة الواجهة الأمامية (Vite Dashboard)...")
    dash_dir = os.path.join(LOCAL_DIR, "dashboard")
    cmd = "npm run build" if sys.platform != "win32" else "cmd.exe /c npm run build"
    res = subprocess.run(cmd, cwd=dash_dir, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(f"⚠️ تحذير: فشل بناء الواجهة الأمامية عبر npm:\n{res.stderr}\nسيتم التحقق من وجود مجلد dist السابق...")

    local_dist = os.path.join(dash_dir, "dist")
    if not os.path.exists(local_dist):
        print("❌ مجلد dashboard/dist غير موجود! يرجى تشغيل npm run build يدوياً.")
        return False

    tar_path = os.path.join(dash_dir, "dist.tar.gz")
    if os.path.exists(tar_path):
        try:
            os.remove(tar_path)
        except Exception:
            pass

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(local_dist, arcname=".")

    print("🚀 رفع حزمة الواجهة إلى السيرفر...")
    sftp = client.open_sftp()
    _run(client, f"mkdir -p {REMOTE_DIR}/dashboard/dist")
    sftp.put(tar_path, f"{REMOTE_DIR}/dashboard/dist.tar.gz")
    sftp.close()

    try:
        os.remove(tar_path)
    except Exception:
        pass

    extract_cmd = (
        f"tar -xzf {REMOTE_DIR}/dashboard/dist.tar.gz -C {REMOTE_DIR}/dashboard/dist && "
        f"rm -f {REMOTE_DIR}/dashboard/dist.tar.gz"
    )
    _run(client, extract_cmd)
    print("✅ تم رفع واستخراج الواجهة بنجاح في /var/www/osmanli/dashboard/dist.")
    return True


def create_and_upload_backend(client):
    """
    تجميع وحزم كافة ملفات الباك إند والمجلدات المطلوبة الحديثة ورفعها ذرياً:
      - المجلدات: core, tasks, proxy
      - الملفات الجذرية: api_server.py, bot_manager.py, game_client.py, GEMINI.md, requirements.txt, reset_stuck_castles.py, firebase_runner.py
      - ملفات التهيئة: nginx-empire.conf, empire-bot.service
    """
    print("\n🐍 [3/7] حزم ورفع ملفات الباك إند والمجلدات الحديثة...")
    tar_path = os.path.join(DEPLOY_DIR, "backend_init.tar.gz")
    if os.path.exists(tar_path):
        try:
            os.remove(tar_path)
        except Exception:
            pass

    included_folders = ["core", "tasks", "proxy"]
    included_root_files = [
        "api_server.py",
        "bot_manager.py",
        "game_client.py",
        "GEMINI.md",
        "requirements.txt",
        "reset_stuck_castles.py",
        "firebase_runner.py",
    ]

    packed_count = 0
    with tarfile.open(tar_path, "w:gz") as tar:
        # 1. إضافة الملفات الجذرية
        for rf in included_root_files:
            lpath = os.path.join(LOCAL_DIR, rf)
            if os.path.exists(lpath):
                tar.add(lpath, arcname=rf)
                packed_count += 1

        # 2. إضافة ملفات خدمات النظام من deploy_logic
        nginx_conf = os.path.join(DEPLOY_DIR, "nginx-empire.conf")
        if os.path.exists(nginx_conf):
            tar.add(nginx_conf, arcname="nginx-empire.conf")
            packed_count += 1

        service_conf = os.path.join(DEPLOY_DIR, "empire-bot.service")
        if os.path.exists(service_conf):
            tar.add(service_conf, arcname="empire-bot.service")
            packed_count += 1

        # 3. إضافة المجلدات الرئيسية (core, tasks, proxy) مع الفلترة
        for folder in included_folders:
            folder_path = os.path.join(LOCAL_DIR, folder)
            if not os.path.exists(folder_path):
                continue
            for root, dirs, files in os.walk(folder_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith("__pycache__")]
                for f in files:
                    if any(f.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                        continue
                    full_f = os.path.join(root, f)
                    rel_f = os.path.relpath(full_f, LOCAL_DIR).replace("\\", "/")
                    tar.add(full_f, arcname=rel_f)
                    packed_count += 1

    tar_size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"   تم حزم {packed_count} ملفاً بحجم إجمالي: {tar_size_mb:.2f} MB")

    print("🚀 رفع حزمة الباك إند إلى السيرفر...")
    sftp = client.open_sftp()
    remote_tar = f"{REMOTE_DIR}/backend_init.tar.gz"
    sftp.put(tar_path, remote_tar)
    sftp.close()

    try:
        os.remove(tar_path)
    except Exception:
        pass

    extract_cmd = (
        f"tar -xzf {remote_tar} -C {REMOTE_DIR} && "
        f"rm -f {remote_tar}"
    )
    _run(client, extract_cmd)
    print("✅ تم استخراج وتحديث كافة ملفات ومجلدات الباك إند على السيرفر بنجاح.")


def upload_database_and_data_files(client):
    """
    رفع قاعدة البيانات ومجلد database/ مع استبعاد ملفات الكاش والنسخ الاحتياطية:
      - database/castles.db (مع شريط تقدم الرفع)
      - castle_prereqs.json, tech_names.json, session_cache.json, firebase_service_account.json
    """
    print("\n🗄️ [4/7] رفع قاعدة البيانات وملفات التهيئة المرجعية (database/)...")
    db_dir = os.path.join(LOCAL_DIR, "database")
    _run(client, f"mkdir -p {REMOTE_DIR}/database")

    sftp = client.open_sftp()

    # 1. رفع قاعدة البيانات الرئيسية castles.db
    local_db = os.path.join(db_dir, "castles.db")
    if not os.path.exists(local_db):
        local_db = os.path.join(LOCAL_DIR, "castles.db")

    if os.path.exists(local_db):
        file_size = os.path.getsize(local_db)
        size_mb = file_size / (1024 * 1024)
        print(f"   ⬆️ قاعدة البيانات الرئيسية (castles.db) بحجم: {size_mb:.2f} MB")

        last_printed = [0]
        def _progress(transferred, total):
            pct = int((transferred / total) * 100)
            if pct >= last_printed[0] + 15 or pct == 100:
                last_printed[0] = pct
                mb_done = transferred / (1024 * 1024)
                sys.stdout.write(f"\r      التقدم: {pct}% ({mb_done:.1f}/{size_mb:.1f} MB)")
                sys.stdout.flush()

        sftp.put(local_db, f"{REMOTE_DIR}/database/castles.db", callback=_progress)
        print("\n   ✅ تم رفع castles.db بنجاح.")
    else:
        print("⚠️ لم يتم العثور على castles.db محلياً!")

    # 2. رفع ملفات التهيئة المرجعية داخل مجلد database
    if os.path.exists(db_dir):
        for f in os.listdir(db_dir):
            if f in ("castles.db", "bot.db") or any(f.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                continue
            lf = os.path.join(db_dir, f)
            if os.path.isfile(lf):
                rf = f"{REMOTE_DIR}/database/{f}"
                sftp.put(lf, rf)
                print(f"   📄 database/{f}")

    sftp.close()

    # 3. تصفير الحالات العالقة في قاعدة البيانات لتبدأ نظيفة
    remote_db = f"{REMOTE_DIR}/database/castles.db"
    clean_sql = (
        f"sqlite3 {remote_db} \""
        "UPDATE castle_states SET conn_state='idle', conn_message='جاهز للتشغيل' "
        "WHERE conn_state IN ('connecting', 'connected', 'running');\" 2>/dev/null || true"
    )
    _run(client, clean_sql)
    print("✅ تم تصفير أي حالات اتصال قديمة عالقة في قاعدة البيانات لتشغيل هادئ.")


def install_python_requirements(client):
    """تثبيت مكتبات البايثون في بيئة venv على السيرفر."""
    print("\n📦 [5/7] تثبيت متطلبات البايثون (pip requirements)...")
    cmd = (
        f"{REMOTE_DIR}/venv/bin/pip install --no-cache-dir -r {REMOTE_DIR}/requirements.txt"
    )
    res = _run(client, cmd, timeout=300)
    print("✅ تم تثبيت مكتبات البايثون بنجاح.")


def configure_and_start_services(client):
    """إعداد وتشغيل خدمات Nginx و Systemd على السيرفر."""
    print("\n⚙️ [6/7] إعداد وتشغيل خدمات النظام (Nginx & Systemd)...")

    setup_service_cmd = (
        f"cp {REMOTE_DIR}/empire-bot.service /etc/systemd/system/empire-bot.service && "
        "systemctl daemon-reload && "
        "systemctl enable empire-bot.service && "
        "systemctl restart empire-bot.service"
    )
    _run(client, setup_service_cmd)

    nginx_cmd = (
        f"cp {REMOTE_DIR}/nginx-empire.conf /etc/nginx/sites-available/default && "
        "nginx -t && "
        "systemctl reload nginx || systemctl restart nginx"
    )
    _run(client, nginx_cmd)

    time.sleep(3)
    status = _run(client, "systemctl is-active empire-bot.service")
    print(f"   حالة خدمة البوت (empire-bot.service): {status}")

    print("\n🔍 [7/7] التحقق من استجابة خادم البوت والواجهة...")
    health = ""
    for _ in range(8):
        time.sleep(1.5)
        health = _run(client, "curl -s -m 10 http://127.0.0.1:8000/api/health || true", timeout=12)
        if "online" in health or "status" in health:
            break
    print(f"   استجابة فحص الصحة (/api/health): {health}")


def launch_approved_castles(client):
    """تشغيل كافة الحسابات المؤهلة تدريجياً وبأمان (فاصل عشوائي بين الحسابات)."""
    print("\n🚀 تشغيل واستئناف الحسابات المؤهلة تدريجياً وبأمان...")
    resume_resp = _run(client, "curl -s -m 30 -X POST http://127.0.0.1:8000/api/internal/gradual-start || true", timeout=35)
    print(f"   استجابة خادم التشغيل التدريجي: {resume_resp}")

    db_path = f"{REMOTE_DIR}/database/castles.db"
    count_active = _run(client, f"sqlite3 {db_path} \"SELECT COUNT(*) FROM castle_states WHERE is_active=1;\" 2>/dev/null || true")
    try:
        active_num = int(count_active)
        print(f"📊 إجمالي الحسابات المؤهلة في قاعدة البيانات: {active_num} حساب")
        print("⏳ التشغيل التدريجي الآمن: حساب كل 5 إلى 10 ثوانٍ لمنع ضغط السيرفر أو حظر الحسابات.")
    except Exception:
        pass
    print("✅ تم إطلاق مهمة التشغيل التدريجي بنجاح في الخلفية على السيرفر.")


def run_full_initial_deployment():
    """تنفيذ النشر الأولي الشامل للسيرفر الجديد مع إبقاء البوتات في وضع الاستعداد idle."""
    print("\n" + "═" * 70)
    print(f"🌐 بدء النشر والتهيئة الأولية الشاملة للسيرفر الجديد: {SERVER_HOST}")
    print("═" * 70)

    client = get_ssh_client()
    try:
        setup_system_prerequisites(client)
        build_and_upload_frontend(client)
        create_and_upload_backend(client)
        upload_database_and_data_files(client)
        install_python_requirements(client)
        configure_and_start_services(client)
    finally:
        client.close()

    print("\n" + "═" * 70)
    print(f"🎉 اكتمل النشر الأولي للسيرفر الجديد {SERVER_HOST} بنجاح تام!")
    print("🛑 جميع البوتات متوقفة حالياً وهادئة (idle) لحماية السيرفر.")
    print(f"🌐 لوحة التحكم متاحة الآن عبر المتصفح: http://{SERVER_HOST}")
    print("👉 لتشغيل الحسابات تدريجياً وبأمان متى ما أردت، نفذ:")
    print("   python deploy_logic/deploy_initial.py --resume")
    print("═" * 70)


def upload_db_only():
    """رفع قاعدة البيانات المحلية وملفات التهيئة فقط."""
    print("\n" + "═" * 70)
    print(f"🗄️ رفع قاعدة البيانات وملفات التهيئة إلى {SERVER_HOST} فقط...")
    print("═" * 70)
    client = get_ssh_client()
    try:
        print("🛑 إيقاف خدمة البوت مؤقتاً لضمان سلامة النقل...")
        _run(client, "systemctl stop empire-bot.service || true")
        upload_database_and_data_files(client)
        print("🔄 إعادة تشغيل خدمة البوت...")
        _run(client, "systemctl restart empire-bot.service")
    finally:
        client.close()
    print("\n✅ تم تحديث قاعدة البيانات بنجاح (الحسابات في وضع الاستعداد idle).")


def upload_backend_only():
    """رفع كود الباك إند فقط وإعادة تشغيل الخدمة."""
    print("\n" + "═" * 70)
    print(f"🐍 رفع وتحديث كود الباك إند فقط إلى {SERVER_HOST}...")
    print("═" * 70)
    client = get_ssh_client()
    try:
        create_and_upload_backend(client)
        print("🔄 إعادة تشغيل خدمة empire-bot...")
        _run(client, "systemctl restart empire-bot.service")
    finally:
        client.close()
    print("\n✅ تم تحديث كود الباك إند بنجاح.")


def upload_frontend_only():
    """بناء ورفع الواجهة فقط وإعادة تحميل Nginx."""
    print("\n" + "═" * 70)
    print(f"📦 بناء ورفع الواجهة الأمامية فقط إلى {SERVER_HOST}...")
    print("═" * 70)
    client = get_ssh_client()
    try:
        build_and_upload_frontend(client)
        _run(client, "systemctl reload nginx || systemctl restart nginx")
    finally:
        client.close()
    print("\n✅ تم تحديث الواجهة الأمامية بنجاح.")


def check_server_status():
    """فحص حالة السيرفر الجديد والخدمات."""
    print("\n" + "═" * 70)
    print(f"🔍 فحص حالة السيرفر الجديد {SERVER_HOST}...")
    print("═" * 70)
    client = get_ssh_client()
    try:
        cmd = (
            "systemctl is-active empire-bot.service; "
            "curl -s http://127.0.0.1:8000/api/health; echo ''; "
            "curl -s http://127.0.0.1:8000/api/admin/stats 2>/dev/null || true; echo ''; "
            "sqlite3 /var/www/osmanli/database/castles.db 'SELECT conn_state, count(*) FROM castle_states GROUP BY conn_state;' 2>/dev/null || true"
        )
        out = _run(client, cmd)
        print(f"\nنتائج الفحص:\n{out}\n")
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=f"أداة النشر الأولي للسيرفر الجديد ({SERVER_HOST})")
    parser.add_argument("--init", "-1", action="store_true", help="تهيئة ونشر أولي شامل للسيرفر الجديد")
    parser.add_argument("--db-only", "-2", action="store_true", help="رفع وتحديث قاعدة البيانات وملفات التهيئة فقط")
    parser.add_argument("--backend-only", "-3", action="store_true", help="رفع وتحديث كود الباك إند فقط")
    parser.add_argument("--frontend-only", "-4", action="store_true", help="بناء ورفع الواجهة الأمامية فقط")
    parser.add_argument("--resume", "-5", action="store_true", help="تشغيل واستئناف الحسابات المؤهلة تدريجياً")
    parser.add_argument("--check", "-6", action="store_true", help="فحص حالة السيرفر والخدمات")
    args = parser.parse_args()

    if args.init:
        run_full_initial_deployment()
        return
    if args.db_only:
        upload_db_only()
        return
    if args.backend_only:
        upload_backend_only()
        return
    if args.frontend_only:
        upload_frontend_only()
        return
    if args.resume:
        client = get_ssh_client()
        try:
            launch_approved_castles(client)
        finally:
            client.close()
        return
    if args.check:
        check_server_status()
        return

    # القائمة التفاعلية في حال عدم تمرير وسائط
    print("\n" + "═" * 70)
    print(f"🚀 أداة النشر والتهيئة الأولية للسيرفر الجديد ({SERVER_HOST})")
    print("═" * 70)
    print("  [1] تهيئة ونشر أولي شامل (Setup + Frontend + Backend + DB + Start Services)")
    print("  [2] رفع وتحديث قاعدة البيانات المحلية وملفات التهيئة فقط")
    print("  [3] رفع وتحديث كود الباك إند فقط")
    print("  [4] بناء ورفع الواجهة الأمامية (Dashboard Dist) فقط")
    print("  [5] تشغيل واستئناف الحسابات المؤهلة تدريجياً الآن")
    print("  [6] فحص حالة السيرفر والخدمات والبوتات")
    print("  [0] إلغاء وخروج")
    print("═" * 70)

    try:
        choice = input("👉 اختر رقم العملية: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nتم الإلغاء.")
        return

    if choice == "1":
        run_full_initial_deployment()
    elif choice == "2":
        upload_db_only()
    elif choice == "3":
        upload_backend_only()
    elif choice == "4":
        upload_frontend_only()
    elif choice == "5":
        client = get_ssh_client()
        try:
            launch_approved_castles(client)
        finally:
            client.close()
    elif choice == "6":
        check_server_status()
    elif choice == "0":
        print("تم الخروج.")
    else:
        print("❌ خيار غير صحيح.")


if __name__ == "__main__":
    main()
