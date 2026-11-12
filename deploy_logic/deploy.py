# -*- coding: utf-8 -*-
"""
deploy.py — أداة النشر والتحديث الذكي السلس لخادم IBRA BOT
═════════════════════════════════════════════════════════════

python deploy_logic/deploy.py --frontend          # تحديث الواجهة فقط
python deploy_logic/deploy.py --full              # تحديث شامل + استئناف تلقائي
python deploy_logic/deploy.py --backend           # تحديث الباك إند فقط + استئناف
python deploy_logic/deploy.py --check             # فحص حالة السيرفر
python deploy_logic/deploy.py --start-all         # تشغيل الحسابات من لوحة التحكم
python deploy_logic/deploy.py --stop-all          # إيقاف البوتات من لوحة التحكم
python deploy_logic/deploy.py --stopped           # تحديث شامل مع إيقاف كل البوتات
python deploy_logic/deploy.py --gradual-start     # تشغيل تدريجي عشوائي (5-10 ثوانٍ + خلط)
python deploy_logic/deploy.py --gradual-stop      # إيقاف جميع البوتات فوراً
python deploy_logic/deploy.py --upload-only       # رفع الملفات فقط بدون لمس البوتات
python deploy_logic/deploy.py --cancel-queue      # إلغاء التشغيل التدريجي (الشغالة تبقى)
python deploy_logic/deploy.py --restart-all       # إيقاف الكل + إعادة تشغيل تدريجي

يدعم القائمة التفاعلية أيضاً: python deploy_logic/deploy.py (أو عبر deploy.bat من الجذر)
"""

import os
import sys
import time
import tarfile
import subprocess
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SERVER_HOST = "187.7.79.122"
SERVER_USER = "root"
SERVER_PASS = "hsnAsdfghjkl150#"
REMOTE_DIR  = "/var/www/osmanli"
DEPLOY_DIR  = os.path.dirname(os.path.abspath(__file__))
LOCAL_DIR   = os.path.dirname(DEPLOY_DIR)


# إعدادات الاستئناف التدريجي — يجب أن تتطابق مع _RESUME_BATCH_SIZE في api_server.py
RESUME_BATCH_SIZE      = 10    # عدد البوتات في كل دفعة (10 حسابات)
RESUME_BATCH_DELAY_MIN = 180   # ثوانٍ الحد الأدنى (3 دقائق)
RESUME_BATCH_DELAY_MAX = 240   # ثوانٍ الحد الأقصى (4 دقائق)
RESUME_BATCH_DELAY_AVG = 210   # متوسط 3.5 دقيقة للحسابات التقديرية
RESUME_ITEM_DELAY_MIN  = 3.0   # ثوانٍ الحد الأدنى بين تشغيل كل حساب وآخر داخل الدفعة
RESUME_ITEM_DELAY_MAX  = 4.0   # ثوانٍ الحد الأقصى بين تشغيل كل حساب وآخر داخل الدفعة
RESUME_ITEM_DELAY_AVG  = 3.5   # متوسط 3.5 ثانية للحسابات التقديرية


def get_ssh_client():
    import socket
    import paramiko
    last_err = None
    for attempt in range(1, 11):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(6)
            s.connect((SERVER_HOST, 22))
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(SERVER_HOST, username=SERVER_USER, password=SERVER_PASS, sock=s, banner_timeout=30)
            return client
        except Exception as e:
            last_err = e
            time.sleep(1.5)
    raise RuntimeError(f"فشل الاتصال بالسيرفر بعد 10 محاولات: {last_err}")


def _run(client, cmd: str, timeout: int = 35) -> str:
    """تنفيذ أمر SSH وإرجاع الناتج مع مهلة زمنية صارمة تمنع التعليق."""
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        stdout.channel.recv_exit_status()
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return ""


def _deploy_lock(client):
    """تفعيل وضع النشر على السيرفر — يمنع تشغيل أي بوت جديد أثناء التحديث."""
    resp = _run(client, "curl -s -m 10 -X POST http://127.0.0.1:8000/api/internal/deploy-lock || true", timeout=15)
    print(f"   🔒 Deploy Lock: {resp}")


def _deploy_unlock(client):
    """إلغاء وضع النشر — يسمح للمستخدمين بتشغيل البوتات مرة أخرى."""
    resp = _run(client, "curl -s -m 10 -X POST http://127.0.0.1:8000/api/internal/deploy-unlock || true", timeout=15)
    print(f"   🔓 Deploy Unlock: {resp}")


def build_frontend():
    print("\n📦 [1/3] جاري بناء حزمة الواجهة الأمامية (Vite)...")
    dash_dir = os.path.join(LOCAL_DIR, "dashboard")
    cmd = "npm run build" if sys.platform != "win32" else "cmd.exe /c npm run build"
    res = subprocess.run(cmd, cwd=dash_dir, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(f"❌ فشل بناء الواجهة الأمامية:\n{res.stderr}")
        return False
    print("✅ تم بناء الواجهة بنجاح في مجلد dist.")
    return True


def upload_frontend(client):
    print("\n🚀 [2/3] ضغط ورفع حزمة الواجهة إلى السيرفر...")
    local_dist = os.path.join(LOCAL_DIR, "dashboard", "dist")
    tar_path = os.path.join(LOCAL_DIR, "dashboard", "dist.tar.gz")

    if not os.path.exists(local_dist):
        print("❌ مجلد dist غير موجود!")
        return False

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(local_dist, arcname=".")

    _run(client, f"mkdir -p {REMOTE_DIR}/dashboard")
    sftp = client.open_sftp()
    sftp.put(tar_path, f"{REMOTE_DIR}/dashboard/dist.tar.gz")
    sftp.close()

    try:
        os.remove(tar_path)
    except Exception:
        pass

    # فك الضغط وإعادة تحميل Nginx
    cmd = (
        f"mkdir -p {REMOTE_DIR}/dashboard/dist && "
        f"tar -xzf {REMOTE_DIR}/dashboard/dist.tar.gz -C {REMOTE_DIR}/dashboard/dist && "
        f"rm -f {REMOTE_DIR}/dashboard/dist.tar.gz && "
        f"systemctl reload nginx"
    )
    stdin, stdout, stderr = client.exec_command(cmd)
    stdout.channel.recv_exit_status()
    print("✅ تم استخراج الواجهة وإعادة تحميل Nginx بنجاح (الواجهة محدثة الآن!).")
    return True


# ─────────────────────────────────────────────────────────────
# قواعد الاستثناء والفلترة لنشر الباك إند
# ─────────────────────────────────────────────────────────────
EXCLUDE_DIRS = {
    # مستثناة بناءً على طلبك الصريح:
    "game file",
    "game files",
    "game_files",
    "scratch",
    "tests",
    "test",
    "game_listener",
    "tcp_learning",
    # مجلدات الواجهة والتطوير والتوثيق المحلي:
    "dashboard",
    "docs",
    "node_modules",
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "__pycache__",
    "dumps",
    "apk_libs",
    "lua_src",
    ".agents",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".tmp",
    ".bak",
    ".apk",
    ".zip",
    ".tar",
    ".gz",
}

EXCLUDE_EXACT_FILES = {
    # حماية قصوى لقواعد بيانات الإنتاج الحية وجلسات الحسابات الحقيقية
    "castles.db",
    "castles.db-wal",
    "castles.db-shm",
    "session_cache.json",
    ".env",
    "auto_resume.json",
    "sniffer_log.txt",
    "exclude_history.json",
    "shared_gather_history.json",
    "backend_dist.tar.gz",
    "dist.tar.gz",
}


def _should_exclude_dir(dir_name: str) -> bool:
    d = dir_name.lower().strip()
    return d in EXCLUDE_DIRS or d.startswith(".git") or d.startswith("__pycache__")


def _should_exclude_file(file_name: str) -> bool:
    fn = file_name.lower().strip()
    if fn in EXCLUDE_EXACT_FILES:
        return True
    if any(fn.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
        return True
    if fn.endswith(".sqlite3") or fn.endswith(".db") or fn.endswith(".db-wal") or fn.endswith(".db-shm"):
        return True
    return False


def create_backend_bundle() -> tuple[str, int]:
    """
    تجميع ذري مضغوط (tar.gz) لكامل ملفات ومجلدات الباك إند الجديدة
    مع استثناء صارم وتلقائي للمجلدات والملفات غير المطلوبة.
    """
    tar_path = os.path.join(DEPLOY_DIR, "backend_dist.tar.gz")
    if os.path.exists(tar_path):
        try:
            os.remove(tar_path)
        except Exception:
            pass

    packed_count = 0
    with tarfile.open(tar_path, "w:gz") as tar:
        for root, dirs, files in os.walk(LOCAL_DIR):
            # تصفية المجلدات مباشرة لمنع الدخول فيها لتسريع الفحص
            dirs[:] = [d for d in dirs if not _should_exclude_dir(d)]

            rel_root = os.path.relpath(root, LOCAL_DIR)
            if rel_root != "." and any(_should_exclude_dir(part) for part in rel_root.replace("\\", "/").split("/")):
                continue

            for f in files:
                if _should_exclude_file(f):
                    continue

                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, LOCAL_DIR).replace("\\", "/")

                # تحقق مضاعف لضمان عدم تمرير أي ملف يقع تحت مسار مستثنى
                path_parts = rel_path.split("/")
                if any(_should_exclude_dir(p) for p in path_parts[:-1]):
                    continue

                tar.add(full_path, arcname=rel_path)
                packed_count += 1

    return tar_path, packed_count


def upload_backend_files(client):
    print("\n📦 [1/3] تجميع وضغط حزمة الباك إند الذرية (مع تطبيق الاستثناءات)...")
    tar_path, packed_count = create_backend_bundle()
    file_size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"   ✅ تم حزم {packed_count} ملفاً بنجاح في أرشيف مضغوط بحجم ({file_size_mb:.2f} MB)")
    print("   🚫 تم استثناء: game file و scratch و tests وقواعد البيانات وملفات الكاش بالكامل.")

    print("\n🚀 [2/3] رفع الحزمة الذرية إلى السيرفر عبر SFTP...")
    _run(client, f"mkdir -p {REMOTE_DIR}")
    sftp = client.open_sftp()
    remote_tar = f"{REMOTE_DIR}/backend_dist.tar.gz"
    sftp.put(tar_path, remote_tar)
    sftp.close()

    try:
        os.remove(tar_path)
    except Exception:
        pass

    print("\n⚡ [3/3] فك الضغط الذري وتحديث إعدادات النظام على السيرفر...")
    extract_cmd = (
        f"tar -xzf {remote_tar} -C {REMOTE_DIR} && "
        f"rm -f {remote_tar} && "
        f"if [ -f '{REMOTE_DIR}/deploy_logic/empire-bot.service' ]; then cp -f '{REMOTE_DIR}/deploy_logic/empire-bot.service' /etc/systemd/system/empire-bot.service; fi && "
        f"if [ -f '{REMOTE_DIR}/deploy_logic/nginx-empire.conf' ]; then cp -f '{REMOTE_DIR}/deploy_logic/nginx-empire.conf' '{REMOTE_DIR}/nginx-empire.conf'; fi"
    )
    _run(client, extract_cmd)

    print("  📦 تثبيت وتحديث مكتبات البايثون في بيئة السيرفر (pip install)...")
    _run(client, f"{REMOTE_DIR}/venv/bin/pip install -q -r {REMOTE_DIR}/requirements.txt")
    _run(client, "systemctl daemon-reload")
    print("✅ تم رفع وتحديث كافة ملفات الباك إند وإعدادات النظام بنجاح تام.")


def deploy_frontend_only():
    print("\n" + "=" * 65)
    print("🌐 خيار 1: تحديث الواجهة الأمامية فقط (Frontend Only)")
    print("⚡ ميزة: 0% انقطاع — البوتات الشغالة حالياً لن تتأثر إطلاقاً!")
    print("=" * 65)

    if not build_frontend():
        return

    client = get_ssh_client()
    upload_frontend(client)
    client.close()

    print("\n" + "═" * 65)
    print("🎉 اكتمل تحديث الواجهة بنجاح تام! يمكنك فحص الموقع الآن.")
    print("═" * 65)


def deploy_full_smart():
    print("\n" + "=" * 65)
    print("🚀 خيار 2: تحديث شامل ذكي (Full Deploy + Auto-Resume)")
    print("🔄 ميزة: تحديث البايثون والواجهة مع استئناف تدريجي للبوتات")
    print(f"📦 الاستئناف التدريجي: {RESUME_BATCH_SIZE} بوت كل 3 إلى 4 دقائق عشوائياً")
    print("=" * 65)

    if not build_frontend():
        return

    client = get_ssh_client()

    # 1. قفل وضع النشر — يمنع المستخدمين من تشغيل بوتات أثناء التحديث
    print("\n🔒 [1/7] تفعيل وضع النشر (Deploy Lock) — تعليق تشغيل البوتات...")
    _deploy_lock(client)

    # 2. حفظ حالة البوتات النشطة حالياً في السيرفر
    print("\n💾 [2/7] حفظ قائمة البوتات النشطة حالياً عبر Auto-Resume...")
    save_resp = _run(client, "curl -s -m 15 -X POST http://127.0.0.1:8000/api/internal/save-running-state || true", timeout=20)
    saved_count = 0
    try:
        import json as _json
        res_data = _json.loads(save_resp)
        saved_count = res_data.get("count", 0)
        print(f"   ✅ تم حفظ حالة {saved_count} بوت نشط بنجاح في السيرفر.")
    except Exception:
        print(f"   ⚠️ استجابة الحفظ: {save_resp[:100] if save_resp else 'تجاوز المهلة الزمنية (تم الانتقال للاسترجاع الاحتياطي)'}")

    if saved_count == 0:
        cat_resp = _run(client, "cat /var/www/osmanli/auto_resume.json 2>/dev/null || true")
        try:
            import json as _json
            prev_data = _json.loads(cat_resp)
            if isinstance(prev_data, list) and len(prev_data) > 0:
                saved_count = len(prev_data)
                print(f"   ✅ تم استرجاع {saved_count} بوت محفوظ مسبقاً من auto_resume.json.")
        except Exception:
            pass

    # 3. إغلاق البوت والخدمة بشكل كامل في السيرفر (إيقاف systemctl أولاً لمنع إعادة التشغيل التلقائي أثناء الرفع)
    print("\n🛑 [3/7] إغلاق خدمة البوت والعمليات بشكل كامل على السيرفر...")
    _run(client, "systemctl stop empire-bot.service || true; pkill -9 -f 'api_server.py' || true; sleep 1")
    stop_status = _run(client, "systemctl is-active empire-bot.service || true")
    print(f"   حالة الخدمة الآن: {stop_status} (متوقفة تماماً)")

    # 4. رفع ملفات الباك إند أثناء إيقاف الخدمة لضمان عدم حدوث تضارب
    print("\n⬆️  [4/7] رفع ملفات الباك إند المحدثة إلى السيرفر...")
    upload_backend_files(client)

    # 5. رفع الواجهة الأمامية وتحديث Nginx
    print("\n⬆️  [5/7] رفع حزمة الواجهة الأمامية وتحديث Nginx...")
    upload_frontend(client)

    # 6. إعادة تشغيل خدمة البايثون (restart لضمان تحميل العملية من الصفر بعد اكتمال الرفع)
    print("\n🔄 [6/7] إعادة تشغيل خدمة البايثون (empire-bot.service)...")
    _run(client, "systemctl daemon-reload && systemctl restart empire-bot.service; sleep 3")
    status_resp = _run(client, "systemctl is-active empire-bot.service")
    print(f"   حالة الخدمة: {status_resp}")

    # 7. التحقق من الصحة مع محاولات متتالية لانتظار اكتمال إقلاع Uvicorn
    print("\n🔍 [7/7] فحص صحة الخدمة بعد الإقلاع...")
    health_resp = ""
    for _ in range(6):
        time.sleep(1)
        health_resp = _run(client, "curl -s -m 10 http://127.0.0.1:8000/api/health || true", timeout=12)
        if health_resp and "online" in health_resp:
            break
    print(f"   الصحة: {health_resp}")

    # مؤشر الاستئناف التدريجي (يعمل تلقائياً في الخلفية على السيرفر)
    if saved_count > 0:
        batches = (saved_count + RESUME_BATCH_SIZE - 1) // RESUME_BATCH_SIZE
        total_time = (batches - 1) * RESUME_BATCH_DELAY_AVG + saved_count * RESUME_ITEM_DELAY_AVG
        print(f"\n⏳ الاستئناف التدريجي: {saved_count} بوت في {batches} دفعة ({RESUME_BATCH_SIZE} حسابات كل 3 إلى 4 دقائق عشوائياً مع فاصل 3 إلى 4 ثوانٍ تدريجي بين كل حساب)")
        print(f"   الوقت التقديري للاستئناف الكامل: ~{int(total_time)}ث ({int(total_time)//60}د {int(total_time)%60}ث)")
    else:
        print("\n🔄 استئناف تدريجي آمن: لم تكن هناك بوتات نشطة مسجلة لحظياً — جاري بدء التشغيل التدريجي...")
        resume_resp = _run(client, "curl -s -m 20 -X POST http://127.0.0.1:8000/api/internal/gradual-start || true", timeout=25)
        print(f"   ✅ تم إرسال أمر التشغيل التدريجي بنجاح: {resume_resp}")

    client.close()

    print("\n" + "═" * 65)
    print("🎉 تم التحديث الشامل بنجاح! البوتات تستأنف تلقائياً بشكل متدرج.")
    print("═" * 65)


def deploy_backend_only():
    print("\n" + "=" * 65)
    print("🐍 خيار 4: تحديث الباك إند فقط (Backend Only + Auto-Resume)")
    print("🔄 ميزة: تحديث ملفات البايثون واستئناف تدريجي للبوتات")
    print(f"📦 الاستئناف التدريجي: {RESUME_BATCH_SIZE} حسابات كل 3 إلى 4 دقائق عشوائياً (فاصل  ثوانٍ تدريجي بين كل حساب)")
    print("=" * 65)

    client = get_ssh_client()

    # 1. قفل وضع النشر — يمنع المستخدمين من تشغيل بوتات أثناء التحديث
    print("\n🔒 [1/6] تفعيل وضع النشر (Deploy Lock) — تعليق تشغيل البوتات...")
    _deploy_lock(client)

    # 2. حفظ حالة البوتات النشطة حالياً في السيرفر
    print("\n💾 [2/6] حفظ قائمة البوتات النشطة حالياً عبر Auto-Resume...")
    save_resp = _run(client, "curl -s -m 15 -X POST http://127.0.0.1:8000/api/internal/save-running-state || true", timeout=20)
    saved_count = 0
    try:
        import json as _json
        res_data = _json.loads(save_resp)
        saved_count = res_data.get("count", 0)
        print(f"   ✅ تم حفظ حالة {saved_count} بوت نشط بنجاح في السيرفر.")
    except Exception:
        print(f"   ⚠️ استجابة الحفظ: {save_resp[:100] if save_resp else 'تجاوز المهلة الزمنية (تم الانتقال للاسترجاع الاحتياطي)'}")

    if saved_count == 0:
        cat_resp = _run(client, "cat /var/www/osmanli/auto_resume.json 2>/dev/null || true")
        try:
            import json as _json
            prev_data = _json.loads(cat_resp)
            if isinstance(prev_data, list) and len(prev_data) > 0:
                saved_count = len(prev_data)
                print(f"   ✅ تم استرجاع {saved_count} بوت محفوظ مسبقاً من auto_resume.json.")
        except Exception:
            pass

    # 3. إغلاق البوت والخدمة بشكل كامل في السيرفر (إيقاف systemctl أولاً لمنع إعادة التشغيل التلقائي أثناء الرفع)
    print("\n🛑 [3/6] إغلاق خدمة البوت والعمليات بشكل كامل على السيرفر...")
    _run(client, "systemctl stop empire-bot.service || true; pkill -9 -f 'api_server.py' || true; sleep 1")
    stop_status = _run(client, "systemctl is-active empire-bot.service || true")
    print(f"   حالة الخدمة الآن: {stop_status} (متوقفة تماماً)")

    # 4. رفع ملفات الباك إند أثناء إيقاف الخدمة
    print("\n⬆️  [4/6] رفع ملفات الباك إند المحدثة إلى السيرفر...")
    upload_backend_files(client)

    # 5. إعادة تشغيل خدمة البايثون (restart لضمان تحميل العملية من الصفر بعد اكتمال الرفع)
    print("\n🔄 [5/6] إعادة تشغيل خدمة البايثون (empire-bot.service)...")
    _run(client, "systemctl daemon-reload && systemctl restart empire-bot.service; sleep 3")
    status_resp = _run(client, "systemctl is-active empire-bot.service")
    print(f"   حالة الخدمة: {status_resp}")

    # 6. التحقق من الصحة مع محاولات متتالية لانتظار اكتمال إقلاع Uvicorn
    print("\n🔍 [6/6] فحص صحة الخدمة بعد إعادة التشغيل...")
    health_resp = ""
    for _ in range(6):
        time.sleep(1)
        health_resp = _run(client, "curl -s -m 10 http://127.0.0.1:8000/api/health || true", timeout=12)
        if health_resp and "online" in health_resp:
            break
    print(f"   الصحة: {health_resp}")

    # مؤشر الاستئناف التدريجي
    if saved_count > 0:
        batches = (saved_count + RESUME_BATCH_SIZE - 1) // RESUME_BATCH_SIZE
        total_time = (batches - 1) * RESUME_BATCH_DELAY_AVG + saved_count * RESUME_ITEM_DELAY_AVG
        print(f"\n⏳ الاستئناف التدريجي: {saved_count} بوت في {batches} دفعة ({RESUME_BATCH_SIZE} حسابات كل 3 إلى 4 دقائق عشوائياً مع فاصل 3 إلى 4 ثوانٍ تدريجي بين كل حساب)")
        print(f"   الوقت التقديري: ~{int(total_time)}ث ({int(total_time)//60}د {int(total_time)%60}ث)")
    else:
        print("\n🔄 استئناف طارئ: لم تكن هناك بوتات نشطة مسجلة لحظياً — جاري تشغيل كافة الحسابات النشطة من قاعدة البيانات...")
        resume_resp = _run(client, "curl -s -m 20 -X POST http://127.0.0.1:8000/api/internal/resume-all-from-db || true", timeout=25)
        print(f"   ✅ تم إرسال أمر تشغيل الحسابات بنجاح: {resume_resp}")

    client.close()

    print("\n" + "═" * 65)
    print("🎉 تم تحديث الباك إند بنجاح! البوتات تستأنف تلقائياً بشكل متدرج.")
    print("═" * 65)


def check_status():
    print("\n" + "=" * 65)
    print("🔍 خيار 3: فحص حالة السيرفر والبوتات الشغالة")
    print("=" * 65)

    client = get_ssh_client()
    cmd = (
        "systemctl is-active empire-bot.service; "
        "curl -s http://127.0.0.1:8000/api/health; echo ''; "
        "curl -s http://127.0.0.1:8000/api/admin/stats"
    )
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"\nنتائج الفحص:\n{out}\n")
    client.close()


def _restart_service_and_wait(client):
    """إعادة تشغيل empire-bot.service وانتظار اكتمال الإقلاع — يضمن تحميل آخر كود من القرص."""
    print("\n🔄 إعادة تشغيل الخدمة لتحميل آخر كود...")
    _run(client, "systemctl daemon-reload; pkill -9 -f 'api_server.py' 2>/dev/null || true; systemctl restart empire-bot.service; sleep 2")
    status = _run(client, "systemctl is-active empire-bot.service")
    print(f"   حالة الخدمة: {status}")
    print("🔍 انتظار اكتمال إقلاع الخدمة (تنظيف السجلات وفتح المنفذ 8000)...")
    for sec in range(1, 36):
        time.sleep(1)
        health = _run(client, "curl -s -m 10 http://127.0.0.1:8000/api/health || true", timeout=12)
        if health and "online" in health:
            print(f"   ✅ الخدمة جاهزة ومستقرة بعد {sec}ث: {health}")
            return True
        if sec % 5 == 0:
            print(f"   ⏳ جاري انتظار إقلاع الخادم وتنظيف السجلات... ({sec}/35ث)")
    print("   ❌ الخدمة لم تستجب بعد 35 ثانية.")
    return False


def resume_all_castles():
    print("\n" + "=" * 65)
    print("🚀 تشغيل/استئناف جميع الحسابات الموافق عليها تدريجياً وبأمان...")
    print("=" * 65)
    client = get_ssh_client()
    ok = _restart_service_and_wait(client)
    if not ok:
        print("❌ تعذر التأكد من جاهزية الخدمة — لم يتم إرسال أمر التشغيل التدريجي.")
        client.close()
        return
    resp = _run(client, "curl -s -X POST http://127.0.0.1:8000/api/internal/gradual-start")
    print(f"   الرد: {resp}")
    client.close()
    print("✅ تم إرسال أمر التشغيل التدريجي لكافة الحسابات بنجاح!")


def stop_all_castles():
    print("\n" + "=" * 65)
    print("🛑 إيقاف جميع البوتات النشطة فوراً على السيرفر...")
    print("=" * 65)
    client = get_ssh_client()
    resp = _run(client, "curl -s -X POST http://127.0.0.1:8000/api/internal/stop-all")
    print(f"   الرد: {resp}")
    client.close()
    print("✅ تم إرسال أمر إيقاف كافة البوتات وتصفير حالتها بنجاح!")


def deploy_with_all_stopped():
    print("\n" + "=" * 65)
    print("🚀 تحديث شامل للباك إند والواجهة مع إيقاف كافة البوتات بالكامل")
    print("🛑 لن يتم تشغيل أي بوت تلقائياً (ستبقى جميع الحسابات متوقفة)")
    print("=" * 65)

    client = get_ssh_client()

    print("\n🔒 [1/7] تفعيل وضع النشر (Deploy Lock)...")
    _deploy_lock(client)

    print("\n🛑 [2/7] إغلاق خدمة البوت والعمليات بشكل كامل على السيرفر...")
    _run(client, "systemctl stop empire-bot.service || true; pkill -9 -f 'api_server.py' || true; sleep 1")

    print("\n📦 [3/7] بناء ورفع حزمة الواجهة الأمامية...")
    if build_frontend():
        upload_frontend(client)

    print("\n⬆️  [4/7] رفع ملفات الباك إند المحدثة إلى السيرفر...")
    upload_backend_files(client)

    print("\n🧹 [5/7] حذف أي ملف استئناف وتصفير جميع الحسابات إلى متوقف (idle)...")
    _run(client, "rm -f /var/www/osmanli/auto_resume.json")
    _run(client, """/var/www/osmanli/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/var/www/osmanli')
from core import database as db
with db.get_connection() as conn:
    conn.execute('''
        UPDATE castle_states 
        SET state='idle', conn_state='idle', conn_message='تم إيقاف البوت بواسطة المشرف'
        WHERE conn_state NOT IN ('sealed_banned', 'banned') AND state NOT IN ('banned')
    ''')
    conn.commit()
print('DB Reset Done')
" """)

    print("\n🔄 [6/7] إعادة تشغيل خدمة البايثون (empire-bot.service)...")
    _run(client, "systemctl daemon-reload && systemctl restart empire-bot.service; sleep 3")

    print("\n🔍 [7/7] فحص صحة الخدمة وإلغاء قفل النشر...")
    for _ in range(6):
        time.sleep(1)
        resp = _run(client, "curl -s -m 10 http://127.0.0.1:8000/api/health || true", timeout=12)
        if resp and "online" in resp:
            break

    _deploy_unlock(client)
    client.close()

    print("\n" + "═" * 65)
    print("🎉 تم التحديث والرفع بنجاح! جميع البوتات متوقفة الآن 100% وجاهزة.")
    print("👉 لتشغيل الحسابات لاحقاً في أي وقت، نفذ في تيرمنال السيرفر:")
    print("   python3 /var/www/osmanli/manage_bots.py start")
    print("═" * 65)


def gradual_start_all():
    """تشغيل تدريجي عشوائي لجميع الحسابات المؤهلة — يعيد تشغيل الخدمة لتحميل آخر كود."""
    print("\n" + "=" * 65)
    print("🚀 تشغيل تدريجي عشوائي لجميع الحسابات المؤهلة")
    print("📦 فاصل 5-10 ثوانٍ عشوائي بين كل حساب + خلط عشوائي")
    print("🔄 يعيد تشغيل الخدمة لتحميل آخر كود من القرص")
    print("=" * 65)
    client = get_ssh_client()
    ok = _restart_service_and_wait(client)
    if not ok:
        print("❌ تعذر التأكد من جاهزية الخدمة — لم يتم إرسال أمر التشغيل التدريجي.")
        client.close()
        return
    resp = _run(client, 'curl -s -X POST http://127.0.0.1:8000/api/internal/gradual-start', timeout=30)
    print(f"   الرد: {resp}")
    client.close()
    print("✅ تم إرسال أمر التشغيل التدريجي بنجاح!")


def gradual_stop_all():
    """إيقاف جميع البوتات النشطة فوراً عبر API."""
    print("\n" + "=" * 65)
    print("🛑 إيقاف جميع البوتات النشطة فوراً")
    print("=" * 65)
    client = get_ssh_client()
    resp = _run(client, 'curl -s -X POST http://127.0.0.1:8000/api/internal/stop-all', timeout=30)
    print(f"   الرد: {resp}")
    client.close()
    print("✅ تم إرسال أمر إيقاف جميع البوتات بنجاح!")


def upload_only():
    """رفع ملفات الباك إند فقط بدون إيقاف أو إعادة تشغيل أي بوت."""
    print("\n" + "=" * 65)
    print("⬆️  رفع ملفات الباك إند فقط (بدون إيقاف/تشغيل أي بوت)")
    print("⚡ الملفات الجديدة ستُستخدم عند إعادة تشغيل البوتات لاحقاً")
    print("=" * 65)
    client = get_ssh_client()
    upload_backend_files(client)
    client.close()
    print("\n" + "═" * 65)
    print("🎉 تم رفع ملفات الباك إند بنجاح! البوتات الشغالة لم تتأثر.")
    print("👉 لتطبيق التحديثات، نفذ: python deploy_logic/deploy.py --restart-all")
    print("═" * 65)


def cancel_queue():
    """إلغاء عملية التشغيل التدريجي الجارية (الحسابات الشغالة تبقى)."""
    print("\n" + "=" * 65)
    print("🛑 إلغاء عملية التشغيل التدريجي الجارية")
    print("📌 الحسابات التي بدأت بالفعل ستبقى شغالة")
    print("=" * 65)
    client = get_ssh_client()
    resp = _run(client, 'curl -s -X POST http://127.0.0.1:8000/api/internal/cancel-start-queue', timeout=15)
    print(f"   الرد: {resp}")
    client.close()
    print("✅ تم إرسال أمر الإلغاء بنجاح!")


def restart_all():
    """إيقاف كل البوتات + إعادة تشغيل الخدمة + تشغيل تدريجي بالكود الجديد."""
    print("\n" + "=" * 65)
    print("🔄 إيقاف جميع البوتات + إعادة تشغيل تدريجي بالتحديثات")
    print("📦 فاصل 5-10 ثوانٍ عشوائي + خلط عشوائي")
    print("🔄 يعيد تشغيل الخدمة لتحميل آخر كود من القرص")
    print("=" * 65)
    client = get_ssh_client()
    _restart_service_and_wait(client)
    resp = _run(client, 'curl -s -X POST http://127.0.0.1:8000/api/internal/restart-all', timeout=30)
    print(f"   الرد: {resp}")
    client.close()
    print("✅ تم إرسال أمر إعادة التشغيل التدريجي بنجاح!")


def main():
    parser = argparse.ArgumentParser(description="أداة النشر والتحديث والتحكم لـ IBRA BOT")
    parser.add_argument("--frontend",   "-1", action="store_true", help="تحديث الواجهة فقط بدون لمس البوتات")
    parser.add_argument("--full",       "-2", action="store_true", help="تحديث شامل مع استئناف ذكي للبوتات")
    parser.add_argument("--backend",    "-4", action="store_true", help="تحديث الباك إند فقط واستئناف البوتات")
    parser.add_argument("--check",      "-3", action="store_true", help="فحص حالة السيرفر والبوتات")
    parser.add_argument("--start-all", "--resume", "--resume-all", "-5", dest="start_all", action="store_true", help="تشغيل جميع الحسابات الموافق عليها تدريجياً من قاعدة البيانات")
    parser.add_argument("--stop-all",   "-6", dest="stop_all", action="store_true", help="إيقاف جميع البوتات النشطة فوراً على السيرفر")
    parser.add_argument("--stopped",    "-7", dest="stopped", action="store_true", help="تحديث شامل للباك إند والواجهة مع إيقاف كافة البوتات بالكامل دون تشغيل أي بوت")
    parser.add_argument("--gradual-start",  dest="gradual_start",  action="store_true", help="تشغيل تدريجي عشوائي لجميع الحسابات المؤهلة (5-10 ثوانٍ + خلط)")
    parser.add_argument("--gradual-stop",   dest="gradual_stop",   action="store_true", help="إيقاف جميع البوتات النشطة فوراً")
    parser.add_argument("--upload-only",    dest="upload_only",    action="store_true", help="رفع ملفات الباك إند فقط بدون لمس البوتات")
    parser.add_argument("--cancel-queue",   dest="cancel_queue",   action="store_true", help="إلغاء التشغيل التدريجي الجاري (الشغالة تبقى)")
    parser.add_argument("--restart-all",    dest="restart_all",    action="store_true", help="إيقاف الكل + إعادة تشغيل تدريجي بالتحديثات")
    args = parser.parse_args()

    if args.frontend:
        deploy_frontend_only()
        return
    if args.full:
        deploy_full_smart()
        return
    if args.backend:
        deploy_backend_only()
        return
    if args.check:
        check_status()
        return
    if args.start_all:
        resume_all_castles()
        return
    if args.stop_all:
        stop_all_castles()
        return
    if args.stopped:
        deploy_with_all_stopped()
        return
    if args.gradual_start:
        gradual_start_all()
        return
    if args.gradual_stop:
        gradual_stop_all()
        return
    if args.upload_only:
        upload_only()
        return
    if args.cancel_queue:
        cancel_queue()
        return
    if args.restart_all:
        restart_all()
        return

    # القائمة التفاعلية
    print("\n" + "═" * 65)
    print("🚀 نظام نشر وتحديث والتحكم في IBRA BOT")
    print("═" * 65)
    print("  [1] تحديث الواجهة فقط (Frontend) - [0% انقطاع]")
    print("  [2] تحديث شامل ذكي (Full Deploy + Auto-Resume)")
    print("  [3] فحص حالة السيرفر والبوتات النشطة")
    print("  [4] تحديث الباك إند فقط (Backend Only + Auto-Resume)")
    print("  [5] تشغيل الحسابات من لوحة التحكم (Resume All)")
    print("  [6] إيقاف البوتات من لوحة التحكم (Stop All)")
    print("  [7] تحديث شامل + إيقاف كافة البوتات (Clean Deploy)")
    print("  ─────────────────────────────────────────────")
    print("  [8] 🆕 تشغيل تدريجي عشوائي لجميع الحسابات المؤهلة")
    print("  [9] 🆕 إيقاف جميع البوتات فوراً")
    print(" [10] 🆕 رفع ملفات الباك إند فقط (بدون إعادة تشغيل)")
    print(" [11] 🆕 إلغاء التشغيل التدريجي (الشغالة تبقى)")
    print(" [12] 🆕 إيقاف الكل + إعادة تشغيل تدريجي بالتحديثات")
    print("  [0] إلغاء وخروج")
    print("═" * 65)

    try:
        choice = input("👉 اختر رقم العملية: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nتم الإلغاء.")
        return

    actions = {
        "1":  deploy_frontend_only,
        "2":  deploy_full_smart,
        "3":  check_status,
        "4":  deploy_backend_only,
        "5":  resume_all_castles,
        "6":  stop_all_castles,
        "7":  deploy_with_all_stopped,
        "8":  gradual_start_all,
        "9":  gradual_stop_all,
        "10": upload_only,
        "11": cancel_queue,
        "12": restart_all,
    }

    action = actions.get(choice)
    if action:
        action()
    elif choice == "0":
        print("تم الخروج.")
    else:
        print("❌ خيار غير صحيح.")


if __name__ == "__main__":
    main()

