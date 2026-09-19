# -*- coding: utf-8 -*-
"""
firebase_runner.py — خادم مراقبة Firebase وتشغيل البوتات تلقائياً
══════════════════════════════════════════════════════════════════════════════
يراقب Firestore بشكل مستمر ويشغّل bot_manager.py لكل قلعة.

التشغيل:
  python firebase_runner.py
  python firebase_runner.py --loop-interval 90
══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(_ROOT, "runner.log"), encoding="utf-8"),
    ]
)
log = logging.getLogger("firebase_runner")

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:
    log.error("❌ مكتبة firebase-admin غير مثبتة!")
    log.error("   شغّل: pip install firebase-admin")
    sys.exit(1)

SERVICE_ACCOUNT_KEY = os.path.join(_ROOT, "firebase_service_account.json")
PROJECT_ID = "mnahel-7c8e5"


def _kill_process_tree(proc: subprocess.Popen):
    """إنهاء العملية وشجرتها بالكامل فوراً بدون تعليق."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, capture_output=True)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# FirebaseRunner
# ══════════════════════════════════════════════════════════════════════

class FirebaseRunner:
    def __init__(self, project_id: str = PROJECT_ID, loop_interval: int = 90):
        self.project_id    = project_id
        self.loop_interval = loop_interval
        self.db: Any       = None

        # القفل يضمن أن start_bot يعمل بشكل ذري تماماً (thread-safe)
        self._lock = threading.Lock()

        # القلاع النشطة: castle_id → subprocess.Popen
        self._active_procs: Dict[str, subprocess.Popen] = {}

        # مجموعة castle_ids "محجوزة" حتى لو لم تبدأ العملية بعد
        self._reserved: Set[str] = set()

        self._listeners: list = []
        self._stop_event = threading.Event()

    # ──────────────────────────────────────────────────────────────────
    # تهيئة Firebase
    # ──────────────────────────────────────────────────────────────────

    def init_firebase(self) -> bool:
        try:
            if firebase_admin._apps:
                self.db = firestore.client()
                return True

            if os.path.exists(SERVICE_ACCOUNT_KEY):
                cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
                firebase_admin.initialize_app(cred, {"projectId": self.project_id})
                self.db = firestore.client()
                log.info(f"✅ Firebase مُهيَّأ عبر: {SERVICE_ACCOUNT_KEY}")
                return True

            log.error("❌ لم يُعثر على firebase_service_account.json")
            return False

        except Exception as e:
            log.error(f"❌ فشل تهيئة Firebase: {e}")
            return False

    # ──────────────────────────────────────────────────────────────────
    # تحديث bot_status في Firestore
    # ──────────────────────────────────────────────────────────────────

    def _update_status(self, user_id: str, castle_id: str, state: str, message: str = ""):
        try:
            ref = (self.db.collection("users").document(user_id)
                         .collection("castles").document(castle_id))
            now = datetime.now(timezone.utc).isoformat()
            upd: dict = {
                "bot_status.state":            state,
                "bot_status.last_run_message": message,
            }
            if state == "running":
                upd["bot_status.last_run_time"] = now
            ref.update(upd)
        except Exception as e:
            log.debug(f"تحذير status: {e}")

    # ──────────────────────────────────────────────────────────────────
    # فحص هل القلعة تعمل بالفعل
    # ──────────────────────────────────────────────────────────────────

    def _is_running(self, castle_id: str) -> bool:
        """يعيد True إذا كانت العملية نشطة أو محجوزة."""
        if castle_id in self._reserved:
            return True
        proc = self._active_procs.get(castle_id)
        return proc is not None and proc.poll() is None

    # ──────────────────────────────────────────────────────────────────
    # تشغيل بوت لقلعة
    # ──────────────────────────────────────────────────────────────────

    def start_bot(self, user_id: str, castle_id: str, castle_data: dict):
        """يشغّل بوت لقلعة واحدة — محمي بالكامل من التكرار بواسطة Lock."""
        with self._lock:
            if self._is_running(castle_id):
                return  # البوت يعمل بالفعل، تجاهل
            # احجز فوراً لمنع أي thread آخر من التشغيل المتوازي
            self._reserved.add(castle_id)

        # نفّذ التشغيل خارج اللوك (لا نريد حجب threads أخرى طويلاً)
        email    = castle_data.get("email", "")
        password = castle_data.get("password", "")
        config   = castle_data.get("config", {})

        if not email:
            log.error(f"❌ القلعة {castle_id}: لا يوجد بريد!")
            with self._lock:
                self._reserved.discard(castle_id)
            self._update_status(user_id, castle_id, "error", "لا يوجد بريد إلكتروني")
            return

        # فحص صلاحية الاشتراك وحالة الحظر
        try:
            user_snap = self.db.collection("users").document(user_id).get()
            if user_snap.exists:
                from core.firebase_schema import check_user_subscription
                valid, reason = check_user_subscription(user_snap.to_dict())
                if not valid:
                    log.warning(f"🛑 القلعة {castle_id} ({email}): تم رفض التشغيل: {reason}")
                    with self._lock:
                        self._reserved.discard(castle_id)
                    self._update_status(user_id, castle_id, "idle", f"متوقف: {reason}")
                    return
        except Exception as e:
            log.warning(f"⚠️ تنبيه أثناء التحقق من اشتراك المستخدم في runner: {e}")

        log.info(f"🚀 [{email}] تشغيل البوت...")
        self._update_status(user_id, castle_id, "running", "البوت يعمل الآن...")

        t = threading.Thread(
            target=self._bot_thread,
            args=(user_id, castle_id, email, password, config),
            daemon=True,
            name=f"bot-{castle_id[:12]}"
        )
        t.start()

    def _bot_thread(self, user_id: str, castle_id: str, email: str, password: str, config: dict):
        """ينفذ البوت ويتابعه حتى يستقر."""
        try:
            # تسجيل دخول إن لم تكن الجلسة موجودة
            if password:
                self._ensure_session(email, password)

            # كتابة ملف الإعدادات
            config_path = os.path.join(_ROOT, f".bot_cfg_{castle_id}.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False)

            cmd = [
                sys.executable,
                os.path.join(_ROOT, "bot_manager.py"),
                "--email", email,
                "--firebase-config", config_path,
                "--loop",
                "--loop-interval", str(self.loop_interval),
            ]

            log.info(f"▶️  [{email}] cmd: bot_manager.py --email {email} --firebase-config ... --loop")

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            # حفظ اللوق في ملف مسموح فقط للمستخدم shreher@gmail.com
            is_shreher = (email.strip().lower() == "shreher@gmail.com")
            if not is_shreher and user_id:
                try:
                    import core.database as db
                    u = db.get_user(user_id)
                    if u and str(u.get("email", "")).strip().lower() == "shreher@gmail.com":
                        is_shreher = True
                except Exception:
                    pass

            if is_shreher:
                log_path = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
                with open(log_path, "a", encoding="utf-8", errors="replace") as lf:
                    lf.write(f"\n{'='*60}\n[{datetime.now():%Y-%m-%d %H:%M:%S}] دورة جديدة\n{'='*60}\n")
                    lf.flush()
                    proc = subprocess.Popen(
                        cmd, cwd=_ROOT, env=env,
                        stdout=lf, stderr=lf,
                        text=True, encoding="utf-8", errors="replace"
                    )
            else:
                proc = subprocess.Popen(
                    cmd, cwd=_ROOT, env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    text=True, encoding="utf-8", errors="replace"
                )

            with self._lock:
                self._active_procs[castle_id] = proc
                self._reserved.discard(castle_id)

            # متابعة العملية مع فحص دوري مستمر للحظر وانتهاء الاشتراك والإيقاف
            forced_stop_reason = ""
            while proc.poll() is None:
                try:
                    # 1. فحص اشتراك المستخدم وحظر حسابه
                    user_snap = self.db.collection("users").document(user_id).get()
                    if user_snap.exists:
                        from core.firebase_schema import check_user_subscription
                        valid, reason = check_user_subscription(user_snap.to_dict() or {})
                        if not valid:
                            forced_stop_reason = reason
                            log.warning(f"🛑 [{email}] كشف حظر أو انتهاء اشتراك — إنهاء فوري للعملية: {reason}")
                            _kill_process_tree(proc)
                            self._update_status(user_id, castle_id, "idle", f"متوقف إجبارياً: {reason}")
                            break

                    # 2. فحص حالة مستند القلعة
                    doc = (self.db.collection("users").document(user_id)
                                  .collection("castles").document(castle_id).get())
                    if doc.exists:
                        state = doc.to_dict().get("bot_status", {}).get("state", "idle")
                        if state not in ("running",):
                            log.info(f"⏹️  [{email}] إيقاف مطلوب من لوحة التحكم (state={state})")
                            _kill_process_tree(proc)
                            break
                except Exception as ex:
                    log.debug(f"Runner guard exception: {ex}")
                time.sleep(15)

            ret = proc.returncode
            if forced_stop_reason:
                log.info(f"🛑 [{email}] توقف البوت إجبارياً: {forced_stop_reason}")
                self._update_status(user_id, castle_id, "idle", f"متوقف إجبارياً: {forced_stop_reason}")
            else:
                log.info(f"✅ [{email}] انتهى البوت (exit={ret})")
                self._update_status(user_id, castle_id, "idle",
                                    "انتهت الدورة بنجاح" if ret == 0 else f"توقف (كود={ret})")

        except Exception as e:
            log.error(f"💥 [{email}] خطأ: {e}")
            self._update_status(user_id, castle_id, "error", str(e))

        finally:
            with self._lock:
                self._active_procs.pop(castle_id, None)
                self._reserved.discard(castle_id)
            try:
                cfg = os.path.join(_ROOT, f".bot_cfg_{castle_id}.json")
                if os.path.exists(cfg):
                    os.remove(cfg)
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────
    # إيقاف بوت
    # ──────────────────────────────────────────────────────────────────

    def stop_bot(self, castle_id: str):
        with self._lock:
            proc = self._active_procs.get(castle_id)
        if proc and proc.poll() is None:
            _kill_process_tree(proc)
            log.info(f"⏹️  إيقاف القلعة {castle_id[:12]}...")

    # ──────────────────────────────────────────────────────────────────
    # تسجيل دخول وحفظ الجلسة
    # ──────────────────────────────────────────────────────────────────

    def _ensure_session(self, email: str, password: str):
        try:
            from core.session_manager import SessionManager
            sm = SessionManager()
            sessions = sm.load()
            if email not in sessions:
                log.info(f"🔑 [{email}] تسجيل دخول جديد...")
                sm.login_and_save(email, password)
        except Exception as e:
            log.warning(f"⚠️  [{email}] جلسة: {e}")

    # ──────────────────────────────────────────────────────────────────
    # مسح Firebase وتوزيع البوتات
    # ──────────────────────────────────────────────────────────────────

    def scan(self):
        log.info("🔍 مسح جميع القلاع...")
        try:
            running = idle = 0
            for user_doc in self.db.collection("users").stream():
                uid = user_doc.id
                udata = user_doc.to_dict() or {}
                from core.firebase_schema import check_user_subscription
                is_sub_valid, sub_reason = check_user_subscription(udata)

                for c in self.db.collection("users").document(uid).collection("castles").stream():
                    data  = c.to_dict() or {}
                    state = data.get("bot_status", {}).get("state", "idle")
                    email = data.get("email", "?")

                    if not is_sub_valid:
                        # المستخدم محظور أو منتهي الاشتراك — إيقاف فوري للعملية إن كانت جارية
                        if self._is_running(c.id):
                            log.warning(f"🛑 [{email}] إيقاف عملية قلعة لمستخدم غير مصرح له (الحظر/الاشتراك): {sub_reason}")
                            self.stop_bot(c.id)
                        if state != "idle":
                            self._update_status(uid, c.id, "idle", f"متوقف: {sub_reason}")
                        continue

                    if state == "running":
                        running += 1
                        if not self._is_running(c.id):
                            log.info(f"▶️  [{email}] جاهز للتشغيل (من مسح دوري)")
                            self.start_bot(uid, c.id, data)

                    elif state == "idle":
                        idle += 1
                        self.stop_bot(c.id)

            # تنظيف العمليات المنتهية
            with self._lock:
                dead = [cid for cid, p in self._active_procs.items() if p.poll() is not None]
                for cid in dead:
                    self._active_procs.pop(cid)

            log.info(f"📊 running={running} idle={idle} | بوتات نشطة: {len(self._active_procs)}")

        except Exception as e:
            log.error(f"❌ خطأ في المسح: {e}")

    # ──────────────────────────────────────────────────────────────────
    # نظام المراقبة الآنية
    # ──────────────────────────────────────────────────────────────────

    def setup_listeners(self):
        log.info("👂 إعداد المراقبة الآنية...")
        try:
            for user_doc in self.db.collection("users").stream():
                self._watch(user_doc.id)
        except Exception as e:
            log.error(f"❌ listeners: {e}")

    def _watch(self, user_id: str):
        ref = self.db.collection("users").document(user_id).collection("castles")

        def on_snap(col_snapshot, changes, read_time):
            for change in changes:
                if change.type.name not in ("ADDED", "MODIFIED"):
                    continue
                data  = change.document.to_dict() or {}
                cid   = change.document.id
                state = data.get("bot_status", {}).get("state", "idle")
                email = data.get("email", "?")

                if state == "running" and not self._is_running(cid):
                    log.info(f"🔔 [{email}] state→running")
                    self.start_bot(user_id, cid, data)

                elif state == "idle" and self._is_running(cid):
                    log.info(f"🔔 [{email}] state→idle")
                    self.stop_bot(cid)

        try:
            listener = ref.on_snapshot(on_snap)
            self._listeners.append(listener)
            log.info(f"👂 مراقبة: {user_id}")
        except Exception as e:
            log.warning(f"⚠️  listener {user_id}: {e}")

    # ──────────────────────────────────────────────────────────────────
    # الحلقة الرئيسية
    # ──────────────────────────────────────────────────────────────────

    def run(self):
        print("\n" + "═" * 60)
        print("🤖 Firebase Runner — خادم مراقبة وتشغيل بوتات Empire")
        print(f"   المشروع  : {self.project_id}")
        print(f"   فاصل الدورة: {self.loop_interval} دقيقة")
        print(f"   الوقت    : {datetime.now():%Y-%m-%d %H:%M:%S}")
        print("═" * 60 + "\n")

        if not self.init_firebase():
            sys.exit(1)

        # مسح أولي
        self.scan()

        # مراقبة آنية
        self.setup_listeners()

        log.info(f"🔁 حلقة رئيسية كل {self.loop_interval} دقيقة + onSnapshot")
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=self.loop_interval * 60)
                if not self._stop_event.is_set():
                    log.info("🔄 دورة دورية...")
                    self.scan()
        except KeyboardInterrupt:
            log.info("\n⛔ إيقاف بواسطة Ctrl+C")
        finally:
            self._stop_event.set()
            for lst in self._listeners:
                try: lst.unsubscribe()
                except Exception: pass
            with self._lock:
                for proc in self._active_procs.values():
                    try: proc.terminate()
                    except Exception: pass
            log.info("✅ تم الإيقاف")


# ══════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ══════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 60)
    print("⚠️  تم إيقاف وتشغيل firebase_runner.py القديم!")
    print("🚀 النظام يعمل الآن عبر خادم api_server.py فائق السرعة والمدعوم بـ SQLite.")
    print("   لتشغيل الخادم:")
    print("   python api_server.py")
    print("=" * 60 + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
