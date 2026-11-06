# -*- coding: utf-8 -*-
"""
deploy_initial.py — أداة النشر والتهيئة الأولية لخادم IBRA BOT الجديد
════════════════════════════════════════════════════════════════════
السيرفر الجديد: 187.7.79.122
المسار البعيد:  /var/www/osmanli

المميزات:
  1) تثبيت وتهيئة بيئة السيرفر الجديد من الصفر (Nginx, Python Venv, Systemd).
  2) بناء ورفع الواجهة الأمامية الكاملة (Dashboard Dist).
  3) رفع كافة ملفات الباك إند والمجلدات التابعة (core, tasks).
  4) رفع قاعدة البيانات المحلية الحالية (database/castles.db) بحجمها الكامل.
  5) تثبيت الاعتماديات (requirements.txt) في بيئة venv.
  6) تشغيل خدمة empire-bot.service وضبط Nginx.
  7) تشغيل واستئناف كافة الحسابات الموافق عليها والنشطة (Approved & Active) تدريجياً عبر السيرفر.

طريقة الاستخدام:
  python deploy_logic/deploy_initial.py --init           # تهيئة ورفع شامل من الصفر
  python deploy_logic/deploy_initial.py --db-only        # رفع وتحديث قاعدة البيانات المحلية فقط
  python deploy_logic/deploy_initial.py --resume         # تشغيل الحسابات الموافق عليها فقط
  python deploy_logic/deploy_initial.py --check          # فحص حالة السيرفر والخدمات
"""

import os
import sys
import time
import tarfile
import subprocess
import argparse
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── إعدادات السيرفر الجديد ──────────────────────────────────────────
SERVER_HOST = "187.7.79.122"
SERVER_USER = "root"
SERVER_PASS = "hsnAsdfghjkl150#"
REMOTE_DIR  = "/var/www/osmanli"
DEPLOY_DIR  = os.path.dirname(os.path.abspath(__file__))
LOCAL_DIR   = os.path.dirname(DEPLOY_DIR)

# إعدادات الاستئناف التدريجي
RESUME_BATCH_SIZE      = 10    # عدد البوتات في كل دفعة
RESUME_BATCH_DELAY_AVG = 210   # متوسط 3.5 دقيقة بين الدفعات
RESUME_ITEM_DELAY_AVG  = 3.5   # فاصل بين كل حساب وآخر


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
    print("\n🛠️ [1/8] تثبيت الحزم الأساسية وإعداد نظام التشغيل (Nginx, Python3, Venv)...")
    cmd = (
        "export DEBIAN_FRONTEND=noninteractive && "
        "apt-get update -y && "
        "apt-get install -y python3 python3-pip python3-venv python3-dev nginx curl git build-essential sqlite3 libsqlite3-dev && "
        f"mkdir -p {REMOTE_DIR}/database {REMOTE_DIR}/dashboard/dist {REMOTE_DIR}/core {REMOTE_DIR}/tasks"
    )
    res = _run(client, cmd, timeout=300)
    print("✅ تم تثبيت حزم النظام وإنشاء مسارات المشروع.")

    print("🐍 [2/8] إنشاء البيئة الافتراضية للبايثون (venv)...")
    venv_cmd = (
        f"if [ ! -d '{REMOTE_DIR}/venv' ]; then "
        f"  python3 -m venv {REMOTE_DIR}/venv; "
        f"fi && "
        f"{REMOTE_DIR}/venv/bin/pip install --upgrade pip"
    )
    _run(client, venv_cmd, timeout=180)
    print("✅ تم تجهيز البيئة الافتراضية /var/www/osmanli/venv.")


def build_and_upload_frontend(client):
    """بناء حزمة الواجهة الأمامية ورفعها إلى السيرفر."""
    print("\n📦 [3/8] بناء حزمة الواجهة الأمامية (Vite Dashboard)...")
    dash_dir = os.path.join(LOCAL_DIR, "dashboard")
    cmd = "npm run build" if sys.platform != "win32" else "cmd.exe /c npm run build"
    res = subprocess.run(cmd, cwd=dash_dir, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(f"⚠️ فشل بناء الواجهة الأمامية عبر npm:\n{res.stderr}\nسيتم البحث عن dist الحالية...")

    local_dist = os.path.join(dash_dir, "dist")
    if not os.path.exists(local_dist):
        print("❌ مجلد dashboard/dist غير موجود! لا يمكن رفع الواجهة.")
        return False

    tar_path = os.path.join(dash_dir, "dist.tar.gz")
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


def upload_backend_code(client):
    """رفع كافة ملفات الباك إند والبايثون والمجلدات الفرعية."""
    print("\n🐍 [4/8] رفع ملفات الباك إند إلى السيرفر الجديد...")
    sftp = client.open_sftp()

    base_files = [
        ("api_server.py", "api_server.py"),
        ("game_client.py", "game_client.py"),
        ("bot_manager.py", "bot_manager.py"),
        ("reset_stuck_castles.py", "reset_stuck_castles.py"),
        ("firebase_runner.py", "firebase_runner.py"),
        ("database/castle_prereqs.json", "database/castle_prereqs.json"),
        ("database/castle_prereqs.json", "castle_prereqs.json"),
        ("check_building_upgrade.py", "check_building_upgrade.py"),
        ("database/tech_names.json", "database/tech_names.json"),
        ("database/tech_names.json", "tech_names.json"),
        ("get_march_capacity.py", "get_march_capacity.py"),
        ("check_online.py", "check_online.py"),
        ("check_optional_chests.py", "check_optional_chests.py"),
        ("requirements.txt", "requirements.txt"),
        ("deploy_logic/nginx-empire.conf", "nginx-empire.conf"),
        ("deploy_logic/empire-bot.service", "empire-bot.service"),
        ("database/session_cache.json", "database/session_cache.json"),
        ("database/session_cache.json", "session_cache.json"),
        ("database/firebase_service_account.json", "database/firebase_service_account.json"),
        ("database/firebase_service_account.json", "firebase_service_account.json"),
    ]

    for item in base_files:
        if isinstance(item, tuple):
            rel_local, rel_remote = item
        else:
            rel_local, rel_remote = item, item
        lpath = os.path.join(LOCAL_DIR, rel_local)
        if os.path.exists(lpath):
            rpath = f"{REMOTE_DIR}/{rel_remote}"
            sftp.put(lpath, rpath)
            print(f"  ⬆️ {rel_local} -> {rel_remote}")

    # رفع مجلد core
    core_dir = os.path.join(LOCAL_DIR, "core")
    if os.path.exists(core_dir):
        _run(client, f"mkdir -p {REMOTE_DIR}/core")
        for cf in os.listdir(core_dir):
            if cf.endswith(".py") or cf.endswith(".json"):
                sftp.put(os.path.join(core_dir, cf), f"{REMOTE_DIR}/core/{cf}")
                print(f"  ⬆️ core/{cf}")

    # رفع مجلد tasks
    tasks_dir = os.path.join(LOCAL_DIR, "tasks")
    if os.path.exists(tasks_dir):
        _run(client, f"mkdir -p {REMOTE_DIR}/tasks")
        for tf in os.listdir(tasks_dir):
            if tf.endswith(".py"):
                sftp.put(os.path.join(tasks_dir, tf), f"{REMOTE_DIR}/tasks/{tf}")
                print(f"  ⬆️ tasks/{tf}")

    # رفع مجلد proxy
    proxy_dir = os.path.join(LOCAL_DIR, "proxy")
    if os.path.exists(proxy_dir):
        _run(client, f"mkdir -p {REMOTE_DIR}/proxy")
        for pf in os.listdir(proxy_dir):
            if pf.endswith(".py") or pf.endswith(".json"):
                sftp.put(os.path.join(proxy_dir, pf), f"{REMOTE_DIR}/proxy/{pf}")
                print(f"  ⬆️ proxy/{pf}")

    sftp.close()
    print("✅ تم رفع كافة ملفات الباك إند بنجاح.")


def upload_local_database(client):
    """رفع قاعدة البيانات المحلية database/castles.db مع إظهار شريط التقدم."""
    print("\n🗄️ [5/8] رفع قاعدة البيانات المحلية (castles.db)...")
    local_db = os.path.join(LOCAL_DIR, "database", "castles.db")
    if not os.path.exists(local_db):
        local_db = os.path.join(LOCAL_DIR, "castles.db")

    if not os.path.exists(local_db):
        print("❌ لم يتم العثور على ملف قاعدة البيانات castles.db محلياً!")
        return False

    file_size = os.path.getsize(local_db)
    size_mb = file_size / (1024 * 1024)
    print(f"   حجم قاعدة البيانات: {size_mb:.2f} ميجابايت ({file_size:,} بايت)")

    _run(client, f"mkdir -p {REMOTE_DIR}/database")
    remote_db = f"{REMOTE_DIR}/database/castles.db"

    last_printed = [0]
    def _progress(transferred, total):
        pct = int((transferred / total) * 100)
        if pct >= last_printed[0] + 10 or pct == 100:
            last_printed[0] = pct
            mb_done = transferred / (1024 * 1024)
            sys.stdout.write(f"\r   ⬆️ جاري الرفع: {pct}% ({mb_done:.1f}/{size_mb:.1f} MB)")
            sys.stdout.flush()

    sftp = client.open_sftp()
    sftp.put(local_db, remote_db, callback=_progress)
    sftp.close()
    print("\n✅ تم رفع قاعدة البيانات المحلية بنجاح إلى /var/www/osmanli/database/castles.db")

    # تصفير أي حالات اتصال قديمة عالقة في قاعدة البيانات المرفوعة لتبدأ نظيفة
    clean_sql = (
        f"sqlite3 {remote_db} \""
        "UPDATE castle_states SET conn_state='idle', conn_message='جاهز للتشغيل' WHERE conn_state IN ('connecting', 'connected', 'running');\""
    )
    _run(client, clean_sql)
    return True


def install_python_requirements(client):
    """تثبيت مكتبات البايثون في بيئة venv على السيرفر."""
    print("\n📦 [6/8] تثبيت متطلبات البايثون (pip requirements)...")
    cmd = (
        f"{REMOTE_DIR}/venv/bin/pip install --no-cache-dir -r {REMOTE_DIR}/requirements.txt"
    )
    res = _run(client, cmd, timeout=300)
    print("✅ تم تثبيت متطلبات البايثون بنجاح.")


def configure_and_start_services(client):
    """إعداد وتشغيل خدمات Nginx و Systemd على السيرفر."""
    print("\n⚙️ [7/8] إعداد وتشغيل خدمات النظام (Nginx & Systemd)...")
    
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

    print("🔍 التحقق من جاهزية الخادم...")
    health = ""
    for _ in range(8):
        time.sleep(1.5)
        health = _run(client, "curl -s -m 10 http://127.0.0.1:8000/api/health || true", timeout=12)
        if "online" in health:
            break
    print(f"   استجابة الفحص: {health}")


def launch_approved_castles(client):
    """تشغيل كافة الحسابات المؤهلة تدريجياً وبأمان (فاصل 5-10 ثوانٍ عشوائي بين كل حساب)."""
    print("\n🚀 تشغيل واستئناف الحسابات المؤهلة تدريجياً وبأمان...")
    resume_resp = _run(client, "curl -s -m 30 -X POST http://127.0.0.1:8000/api/internal/gradual-start || true", timeout=35)
    print(f"   استجابة خادم التشغيل التدريجي: {resume_resp}")

    db_path = f"{REMOTE_DIR}/database/castles.db"
    count_active = _run(client, f"sqlite3 {db_path} \"SELECT COUNT(*) FROM castle_states WHERE is_active=1;\"")
    try:
        active_num = int(count_active)
        print(f"\n📊 إجمالي الحسابات المؤهلة في قاعدة البيانات: {active_num} حساب")
        print("⏳ التشغيل التدريجي الآمن: حساب كل 5 إلى 10 ثوانٍ مع خلط الحسابات لمنع ضغط السيرفر أو حظر الحسابات.")
    except Exception:
        pass
    print("✅ تم إطلاق مهمة التشغيل التدريجي بنجاح في الخلفية على السيرفر.")


def run_full_initial_deployment():
    """تنفيذ النشر الأولي الشامل للسيرفر الجديد مع إبقاء جميع البوتات متوقفة idle."""
    print("\n" + "═" * 70)
    print(f"🌐 بدء النشر والتهيئة الأولية للسيرفر الجديد: {SERVER_HOST}")
    print("═" * 70)

    client = get_ssh_client()
    try:
        setup_system_prerequisites(client)
        build_and_upload_frontend(client)
        upload_backend_code(client)
        upload_local_database(client)
        install_python_requirements(client)
        configure_and_start_services(client)
        # ملاحظة: تم إيقاف التشغيل التلقائي للبوتات لضمان هدوء السيرفر وعدم الضغط عليه
    finally:
        client.close()

    print("\n" + "═" * 70)
    print(f"🎉 اكتمل النشر الأولي للسيرفر الجديد {SERVER_HOST} بنجاح تام!")
    print("🛑 جميع البوتات متوقفة حالياً وهادئة (idle) بنجاح لحماية موارد السيرفر.")
    print(f"🌐 يمكنك الآن فتح لوحة التحكم عبر المتصفح: http://{SERVER_HOST}")
    print("👉 لتشغيل الحسابات تدريجياً وبأمان متى ما أردت، نفذ:")
    print("   python deploy_logic/deploy_initial.py --resume")
    print("   أو: python deploy_logic/deploy.py --gradual-start")
    print("═" * 70)


def upload_db_only():
    """رفع قاعدة البيانات المحلية فقط دون تشغيل تلقائي للبوتات."""
    print("\n" + "═" * 70)
    print(f"🗄️ رفع قاعدة البيانات المحلية إلى {SERVER_HOST} فقط...")
    print("═" * 70)
    client = get_ssh_client()
    try:
        print("🛑 إيقاف الخدمة مؤقتاً لضمان سلامة النقل...")
        _run(client, "systemctl stop empire-bot.service || true")
        upload_local_database(client)
        print("🔄 إعادة تشغيل الخدمة...")
        _run(client, "systemctl restart empire-bot.service")
    finally:
        client.close()
    print("\n✅ تم تحديث قاعدة البيانات بنجاح (جميع البوتات متوقفة idle).")
    print("👉 لتشغيل الحسابات تدريجياً وبأمان: python deploy_logic/deploy_initial.py --resume")


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
            "curl -s http://127.0.0.1:8000/api/admin/stats; echo ''; "
            "sqlite3 /var/www/osmanli/database/castles.db 'SELECT conn_state, count(*) FROM castle_states GROUP BY conn_state;' 2>/dev/null || true"
        )
        out = _run(client, cmd)
        print(f"\nنتائج الفحص:\n{out}\n")
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=f"أداة النشر الأولي للسيرفر الجديد ({SERVER_HOST})")
    parser.add_argument("--init", "-1", action="store_true", help="تهيئة ونشر أولي شامل للسيرفر الجديد")
    parser.add_argument("--db-only", "-2", action="store_true", help="رفع قاعدة البيانات المحلية وتحديث الحسابات فقط")
    parser.add_argument("--resume", "-3", action="store_true", help="تشغيل واستئناف الحسابات الموافق عليها فقط")
    parser.add_argument("--check", "-4", action="store_true", help="فحص حالة السيرفر الجديد")
    args = parser.parse_args()

    if args.init:
        run_full_initial_deployment()
        return
    if args.db_only:
        upload_db_only()
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
    print("  [1] تهيئة ونشر أولي شامل (Setup + Frontend + Backend + DB + Run Castles)")
    print("  [2] رفع وتحديث قاعدة البيانات المحلية فقط وتشغيل الحسابات")
    print("  [3] استئناف وتشغيل الحسابات الموافق عليها الآن")
    print("  [4] فحص حالة السيرفر الجديد والبوتات")
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
        client = get_ssh_client()
        try:
            launch_approved_castles(client)
        finally:
            client.close()
    elif choice == "4":
        check_server_status()
    elif choice == "0":
        print("تم الخروج.")
    else:
        print("❌ خيار غير صحيح.")


if __name__ == "__main__":
    main()

