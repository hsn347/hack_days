# -*- coding: utf-8 -*-
"""
reset_stuck_castles.py — إعادة ضبط القلاع العالقة إلى idle
══════════════════════════════════════════════════════════
يُعيد ضبط أي قلعة بحالة running أو starting إلى idle في SQLite (castles.db).
يدعم التشغيل محلياً أو عن بُعد عبر SSH على السيرفر.
"""

import sys
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def reset_local():
    from core.database import reset_stuck_castles_db
    cnt = reset_stuck_castles_db()
    print(f"✅ [Local SQLite] تم إعادة ضبط {cnt} قلعة عالقة إلى idle بنجاح.")


def reset_remote():
    import paramiko

    SERVER_HOST = "187.124.163.163"
    SERVER_USER = "root"
    SERVER_PASS = "hsnAsdfghjkl150#"

    remote_code = '''
import sys
sys.path.insert(0, "/var/www/osmanli")
from core.database import reset_stuck_castles_db, get_db_path
cnt = reset_stuck_castles_db()
print(f"DONE: Reset {cnt} castles to idle in {get_db_path()}")
'''

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_HOST, username=SERVER_USER, password=SERVER_PASS, timeout=20)

    sftp = client.open_sftp()
    with sftp.file("/tmp/do_reset.py", "w") as f:
        f.write(remote_code)
    sftp.close()

    stdin, stdout, stderr = client.exec_command("/var/www/osmanli/venv/bin/python /tmp/do_reset.py")
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(f"Errors:\n{err}")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset stuck castles in SQLite")
    parser.add_argument("--remote", action="store_true", help="تشغيل على السيرفر البعيد عبر SSH")
    args = parser.parse_args()

    if args.remote:
        reset_remote()
    else:
        reset_local()
