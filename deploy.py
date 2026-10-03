# -*- coding: utf-8 -*-
"""
deploy.py — أداة النشر والتحديث الذكي السلس لخادم IBRA BOT
═════════════════════════════════════════════════════════════


python deploy.py --backend
python deploy.py --full
python deploy.py --frontend

يدعم:
  1) تحديث الواجهة فقط (Frontend) بدون إيقاف أي بوت (0% توقف).
  2) تحديث شامل ذكي (Full Deploy) مع استئناف فوري تلقائي لجميع البوتات الشغالة (Auto-Resume).
  3) فحص حالة السيرفر وعدد البوتات النشطة الآن.
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

SERVER_HOST = "187.124.163.163"
SERVER_USER = "root"
SERVER_PASS = "hsnAsdfghjkl150#"
REMOTE_DIR  = "/var/www/osmanli"
LOCAL_DIR   = os.path.dirname(os.path.abspath(__file__))


# إعدادات الاستئناف التدريجي — يجب أن تتطابق مع _RESUME_BATCH_SIZE في api_server.py
RESUME_BATCH_SIZE  = 20    # عدد البوتات في كل دفعة
RESUME_BATCH_DELAY = 30    # ثوانٍ بين الدفعات


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


def _run(client, cmd: str) -> str:
    """تنفيذ أمر SSH وإرجاع الناتج."""
    stdin, stdout, stderr = client.exec_command(cmd)
    stdout.channel.recv_exit_status()
    return stdout.read().decode("utf-8", errors="replace").strip()


def _deploy_lock(client):
    """تفعيل وضع النشر على السيرفر — يمنع تشغيل أي بوت جديد أثناء التحديث."""
    resp = _run(client, "curl -s -X POST http://127.0.0.1:8000/api/internal/deploy-lock")
    print(f"   🔒 Deploy Lock: {resp}")


def _deploy_unlock(client):
    """إلغاء وضع النشر — يسمح للمستخدمين بتشغيل البوتات مرة أخرى."""
    resp = _run(client, "curl -s -X POST http://127.0.0.1:8000/api/internal/deploy-unlock")
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


def upload_backend_files(client):
    print("\n🐍 رفع ملفات الباك إند المحدثة إلى السيرفر...")
    sftp = client.open_sftp()

    backend_files = [
        ("api_server.py", f"{REMOTE_DIR}/api_server.py"),
        ("game_client.py", f"{REMOTE_DIR}/game_client.py"),
        ("bot_manager.py", f"{REMOTE_DIR}/bot_manager.py"),
        ("reset_stuck_castles.py", f"{REMOTE_DIR}/reset_stuck_castles.py"),
        ("firebase_runner.py", f"{REMOTE_DIR}/firebase_runner.py"),
        ("core/database.py", f"{REMOTE_DIR}/core/database.py"),
        ("core/session_manager.py", f"{REMOTE_DIR}/core/session_manager.py"),
        ("core/firebase_schema.py", f"{REMOTE_DIR}/core/firebase_schema.py"),
        ("empire-bot.service", "/etc/systemd/system/empire-bot.service"),
    ]


    # رفع كافة ملفات مجلد tasks
    tasks_dir = os.path.join(LOCAL_DIR, "tasks")
    if os.path.exists(tasks_dir):
        for tf in os.listdir(tasks_dir):
            if tf.endswith(".py"):
                backend_files.append((f"tasks/{tf}", f"{REMOTE_DIR}/tasks/{tf}"))

    for rel_path, remote_path in backend_files:
        local_path = os.path.join(LOCAL_DIR, rel_path)
        if os.path.exists(local_path):
            sftp.put(local_path, remote_path)
            print(f"  ⬆️  {rel_path}")

    sftp.close()
    _run(client, "systemctl daemon-reload")
    print("✅ تم رفع ملفات الباك إند وتحديث إعدادات النظام بنجاح.")


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
    print(f"📦 الاستئناف التدريجي: {RESUME_BATCH_SIZE} بوت كل {RESUME_BATCH_DELAY} ثانية")
    print("=" * 65)

    if not build_frontend():
        return

    client = get_ssh_client()

    # 1. قفل وضع النشر — يمنع المستخدمين من تشغيل بوتات أثناء التحديث
    print("\n🔒 [1/6] تفعيل وضع النشر (Deploy Lock) — تعليق تشغيل البوتات...")
    _deploy_lock(client)

    # 2. حفظ حالة البوتات النشطة
    print("\n💾 [2/6] حفظ قائمة البوتات النشطة عبر Auto-Resume...")
    save_resp = _run(client, "curl -s -X POST http://127.0.0.1:8000/api/internal/save-running-state")
    try:
        import json as _json
        count = _json.loads(save_resp).get("count", "?")
        print(f"   تم حفظ {count} بوت شغّال.")
    except Exception:
        print(f"   {save_resp[:80]}")

    # 3. رفع ملفات الباك إند
    print("\n⬆️  [3/6] رفع ملفات الباك إند...")
    upload_backend_files(client)

    # 4. رفع الواجهة الأمامية
    print("\n⬆️  [4/6] رفع حزمة الواجهة الأمامية وتحديث Nginx...")
    upload_frontend(client)

    # 5. إعادة تشغيل خدمة البايثون
    print("\n🔄 [5/6] إعادة تشغيل خدمة البايثون (empire-bot.service)...")
    status_resp = _run(client, "systemctl restart empire-bot.service; sleep 3; systemctl is-active empire-bot.service")
    print(f"   حالة الخدمة: {status_resp}")

    # 6. التحقق من الصحة
    print("\n🔍 [6/6] فحص صحة الخدمة...")
    time.sleep(3)
    health_resp = _run(client, "curl -s http://127.0.0.1:8000/api/health")
    print(f"   الصحة: {health_resp}")

    client.close()

    # مؤشر الاستئناف التدريجي (يعمل تلقائياً في الخلفية على السيرفر)
    try:
        import json as _json
        bot_count = _json.loads(save_resp).get("count", 0)
        if bot_count > 0:
            batches = (bot_count + RESUME_BATCH_SIZE - 1) // RESUME_BATCH_SIZE
            total_time = (batches - 1) * RESUME_BATCH_DELAY
            print(f"\n⏳ الاستئناف التدريجي: {bot_count} بوت في {batches} دفعة")
            print(f"   الوقت التقديري للاستئناف الكامل: ~{total_time}ث ({total_time//60}د {total_time%60}ث)")
    except Exception:
        pass

    print("\n" + "═" * 65)
    print("🎉 تم التحديث الشامل بنجاح! البوتات تستأنف تلقائياً بشكل متدرج.")
    print("═" * 65)


def deploy_backend_only():
    print("\n" + "=" * 65)
    print("🐍 خيار 4: تحديث الباك إند فقط (Backend Only + Auto-Resume)")
    print("🔄 ميزة: تحديث ملفات البايثون واستئناف تدريجي للبوتات")
    print(f"📦 الاستئناف التدريجي: {RESUME_BATCH_SIZE} بوت كل {RESUME_BATCH_DELAY} ثانية")
    print("=" * 65)

    client = get_ssh_client()

    # 1. قفل وضع النشر — يمنع المستخدمين من تشغيل بوتات أثناء التحديث
    print("\n🔒 [1/5] تفعيل وضع النشر (Deploy Lock) — تعليق تشغيل البوتات...")
    _deploy_lock(client)

    # 2. حفظ حالة البوتات النشطة
    print("\n💾 [2/5] حفظ قائمة البوتات النشطة عبر Auto-Resume...")
    save_resp = _run(client, "curl -s -X POST http://127.0.0.1:8000/api/internal/save-running-state")
    try:
        import json as _json
        count = _json.loads(save_resp).get("count", "?")
        print(f"   تم حفظ {count} بوت شغّال.")
    except Exception:
        print(f"   {save_resp[:80]}")

    # 3. رفع ملفات الباك إند
    print("\n⬆️  [3/5] رفع ملفات الباك إند المحدثة...")
    upload_backend_files(client)

    # 4. إعادة تشغيل خدمة البايثون
    print("\n🔄 [4/5] إعادة تشغيل خدمة البايثون (empire-bot.service)...")
    status_resp = _run(client, "systemctl restart empire-bot.service; sleep 3; systemctl is-active empire-bot.service")
    print(f"   حالة الخدمة: {status_resp}")

    # 5. التحقق من الصحة
    print("\n🔍 [5/5] فحص صحة الخدمة بعد إعادة التشغيل...")
    time.sleep(3)
    health_resp = _run(client, "curl -s http://127.0.0.1:8000/api/health")
    print(f"   الصحة: {health_resp}")

    client.close()

    # مؤشر الاستئناف التدريجي
    try:
        import json as _json
        bot_count = _json.loads(save_resp).get("count", 0)
        if bot_count > 0:
            batches = (bot_count + RESUME_BATCH_SIZE - 1) // RESUME_BATCH_SIZE
            total_time = (batches - 1) * RESUME_BATCH_DELAY
            print(f"\n⏳ الاستئناف التدريجي: {bot_count} بوت في {batches} دفعة")
            print(f"   الوقت التقديري: ~{total_time}ث ({total_time//60}د {total_time%60}ث)")
    except Exception:
        pass

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


def main():
    parser = argparse.ArgumentParser(description="أداة النشر والتحديث الذكي لـ IBRA BOT")
    parser.add_argument("--frontend", "-1", action="store_true", help="تحديث الواجهة فقط بدون لمس البوتات")
    parser.add_argument("--full",     "-2", action="store_true", help="تحديث شامل مع استئناف ذكي للبوتات")
    parser.add_argument("--backend",  "-4", action="store_true", help="تحديث الباك إند فقط واستئناف البوتات")
    parser.add_argument("--check",    "-3", action="store_true", help="فحص حالة السيرفر والبوتات")
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

    # القائمة التفاعلية
    print("\n" + "═" * 65)
    print("🚀 نظام نشر وتحديث IBRA BOT (Zero-Downtime Smart Deployer)")
    print("═" * 65)
    print("  [1] تحديث الواجهة فقط (Frontend) - [0% انقطاع، لا يلمس البوتات نهائياً]")
    print("  [2] تحديث شامل ذكي (Full Deploy) - [يحدث البايثون والواجهة ويستأنف جميع البوتات]")
    print("  [3] فحص حالة السيرفر والبوتات النشطة الآن")
    print("  [4] تحديث الباك إند فقط (Backend Only) - [سريع جداً مع استئناف البوتات]")
    print("  [0] إلغاء وخروج")
    print("═" * 65)

    try:
        choice = input("👉 اختر رقم العملية (1 أو 2 أو 3 أو 4): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nتم الإلغاء.")
        return

    if choice == "1":
        deploy_frontend_only()
    elif choice == "2":
        deploy_full_smart()
    elif choice == "3":
        check_status()
    elif choice == "4":
        deploy_backend_only()
    elif choice == "0":
        print("تم الخروج.")
    else:
        print("❌ خيار غير صحيح.")


if __name__ == "__main__":
    main()

