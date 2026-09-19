# -*- coding: utf-8 -*-
"""
deploy.py — أداة النشر والتحديث الذكي السلس لخادم IBRA BOT
═════════════════════════════════════════════════════════════
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


def get_ssh_client():
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_HOST, username=SERVER_USER, password=SERVER_PASS, timeout=20)
    return client


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
    print("✅ تم رفع ملفات الباك إند بنجاح.")


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
    print("🔄 ميزة: تحديث البايثون والواجهة مع استئناف فوري لجميع البوتات الشغالة تلقائياً")
    print("=" * 65)

    if not build_frontend():
        return

    client = get_ssh_client()

    # 1. حفظ حالة جميع البوتات الشغالة الآن أياً كان عددها
    print("\n💾 [1/5] حفظ قائمة البوتات النشطة حالياً عبر ميزة Auto-Resume...")
    cmd_save = "curl -s -X POST http://127.0.0.1:8000/api/internal/save-running-state"
    stdin, stdout, stderr = client.exec_command(cmd_save)
    save_resp = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"   استجابة السيرفر: {save_resp}")

    # 2. رفع ملفات الباك إند
    print("\n⬆️  [2/5] رفع ملفات الباك إند...")
    upload_backend_files(client)

    # 3. رفع ملفات الواجهة الأمامية
    print("\n⬆️  [3/5] رفع حزمة الواجهة الأمامية وتحديث Nginx...")
    upload_frontend(client)

    # 4. إعادة تشغيل خدمة البايثون لاعتماد الكود الجديد
    print("\n🔄 [4/5] إعادة تشغيل خدمة البايثون (empire-bot.service)...")
    cmd_restart = "systemctl restart empire-bot.service; sleep 2; systemctl is-active empire-bot.service"
    stdin, stdout, stderr = client.exec_command(cmd_restart)
    status_resp = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"   حالة الخدمة الآن: {status_resp}")

    # 5. التحقق من صحة السيرفر والاستئناف التلقائي
    print("\n🔍 [5/5] فحص صحة الخدمة والاستئناف التلقائي...")
    time.sleep(3)
    cmd_health = "curl -s http://127.0.0.1:8000/api/health"
    stdin, stdout, stderr = client.exec_command(cmd_health)
    health_resp = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"   فحص الصحة: {health_resp}")

    client.close()
    print("\n" + "═" * 65)
    print("🎉 تم التحديث الشامل بنجاح! جاري استئناف البوتات تلقائياً في الخلفية.")
    print("═" * 65)


def deploy_backend_only():
    print("\n" + "=" * 65)
    print("🐍 خيار 4: تحديث الباك إند فقط (Backend Only + Auto-Resume)")
    print("🔄 ميزة: تحديث ملفات البايثون فوراً واستئناف البوتات النشطة تلقائياً")
    print("=" * 65)

    client = get_ssh_client()

    # 1. حفظ حالة جميع البوتات الشغالة الآن
    print("\n💾 [1/4] حفظ قائمة البوتات النشطة حالياً عبر Auto-Resume...")
    cmd_save = "curl -s -X POST http://127.0.0.1:8000/api/internal/save-running-state"
    stdin, stdout, stderr = client.exec_command(cmd_save)
    save_resp = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"   استجابة السيرفر: {save_resp}")

    # 2. رفع ملفات الباك إند
    print("\n⬆️  [2/4] رفع ملفات الباك إند المحدثة...")
    upload_backend_files(client)

    # 3. إعادة تشغيل خدمة البايثون
    print("\n🔄 [3/4] إعادة تشغيل خدمة البايثون (empire-bot.service)...")
    cmd_restart = "systemctl restart empire-bot.service; sleep 2; systemctl is-active empire-bot.service"
    stdin, stdout, stderr = client.exec_command(cmd_restart)
    status_resp = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"   حالة الخدمة الآن: {status_resp}")

    # 4. فحص الصحة والاستئناف
    print("\n🔍 [4/4] التحقق من صحة الخدمة بعد إعادة التشغيل...")
    time.sleep(3)
    cmd_health = "curl -s http://127.0.0.1:8000/api/health"
    stdin, stdout, stderr = client.exec_command(cmd_health)
    health_resp = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"   فحص الصحة: {health_resp}")

    client.close()
    print("\n" + "═" * 65)
    print("🎉 تم تحديث الباك إند بنجاح! جاري استئناف البوتات تلقائياً.")
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

