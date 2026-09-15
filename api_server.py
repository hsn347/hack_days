# -*- coding: utf-8 -*-
"""
api_server.py — خادم FastAPI لإدارة البوتات
══════════════════════════════════════════════════════════════════════
يستقبل أوامر من لوحة التحكم (React) ويشغّل/يوقف bot_manager.py.

يعمل محلياً على المنفذ 8000 — وعلى Hostinger VPS بنفس الكود.

التشغيل:
  python api_server.py
  python api_server.py --port 8000 --host 0.0.0.0
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os, sys, json, time, logging, argparse, threading, asyncio, queue, signal
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── FastAPI & Security imports ────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api_server")
log.setLevel(logging.INFO)


# ══════════════════════════════════════════════════════════════════
# FastAPI App & Secure CORS
# ══════════════════════════════════════════════════════════════════

app = FastAPI(title="Empire Bot API", version="1.0.0")

# قراءة النطاقات المسموحة من متغيرات البيئة لدعم بيئات الإنتاج والـ VPS
_cors_origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
_allowed_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins if "*" not in _allowed_origins else ["*"],
    allow_credentials=True if "*" not in _allowed_origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════════
# إدارة الـ Threads (Thread Pool Architecture — بدل subprocess)
# كل قلعة = thread خفيف (~2MB) بدل subprocess ثقيل (~60MB)
# ══════════════════════════════════════════════════════════════════

_lock         = threading.Lock()
_threads:     Dict[str, threading.Thread] = {}   # castle_id → thread
_stop_events: Dict[str, threading.Event]  = {}   # castle_id → stop signal
_reserved:    Set[str]                    = set() # castle_ids محجوزة (بدأت لكن لم تُسجَّل بعد)
_log_qs:      Dict[str, "queue.Queue[str]"] = {}  # castle_id → queue للـ logs
_conn_states: Dict[str, str]              = {}    # castle_id → 'connected' | 'disconnected' | 'reconnecting' | 'waiting'
_user_stopped: Set[str]                   = set() # castle_ids التي تم إيقافها يدوياً من المستخدم
_castle_emails: Dict[str, str]            = {}    # castle_id → email
_castle_users:  Dict[str, str]            = {}    # castle_id → user_id


def _is_running(castle_id: str) -> bool:
    if castle_id in _reserved:
        return True
    t = _threads.get(castle_id)
    return t is not None and t.is_alive()


def _get_real_status(castle_id: str) -> str:
    """الحالة الحقيقية: الـ thread + حالة اتصال اللعبة معاً."""
    with _lock:
        if castle_id in _reserved:
            return 'starting'
        t = _threads.get(castle_id)
        if t is None or not t.is_alive():
            return 'idle'  # الـ thread متوقف
        # الـ thread شغال — هل الاتصال بالجيم سيرفر نشط؟
        conn = _conn_states.get(castle_id, 'connected')  # إذا لم يُبلَّغ بعد → نفترض متصل
        if conn == 'disconnected':
            return 'disconnected'  # شخص دخل من الجوال
        if conn == 'reconnecting':
            return 'reconnecting'
        if conn == 'waiting':
            return 'waiting'
        return 'running'


# ══════════════════════════════════════════════════════════════════
# Pydantic Models
# ══════════════════════════════════════════════════════════════════

class StartBotRequest(BaseModel):
    castle_id:  str
    user_id:    str
    email:      str
    password:   Optional[str] = None
    config:     Dict[str, Any] = {}
    loop_interval: int = 90   # دقيقة

class StopBotRequest(BaseModel):
    castle_id: str


# ══════════════════════════════════════════════════════════════════
# Firebase Singleton Manager
# ══════════════════════════════════════════════════════════════════

_fb_init_lock = threading.Lock()

def _ensure_firebase():
    """تهيئة آمنة وموحدة لـ Firebase Admin SDK لمرة واحدة فقط وبدون أي تداخل خيوط."""
    with _fb_init_lock:
        try:
            import firebase_admin
            from firebase_admin import credentials
            try:
                return firebase_admin.get_app()
            except ValueError:
                sak = os.path.join(_ROOT, "firebase_service_account.json")
                if os.path.exists(sak):
                    return firebase_admin.initialize_app(credentials.Certificate(sak))
        except Exception as e:
            log.debug(f"Firebase init error: {e}")
    return None

# تهيئة فورية عند بدء تشغيل الخادم
_ensure_firebase()


def _update_firebase_status(user_id: str, castle_id: str, state: str, message: str = "", conn_state: Optional[str] = None, next_run_time: Optional[str] = None):
    """يحدّث bot_status في Firestore (state + conn_state + message + next_run_time)."""
    try:
        _ensure_firebase()
        import firebase_admin
        from firebase_admin import firestore as fb_fs

        if firebase_admin._apps:
            db = fb_fs.client()
            ref = db.collection("users").document(user_id).collection("castles").document(castle_id)
            now_iso = datetime.now(timezone.utc).isoformat()
            updates: dict = {
                "bot_status.state":            state,
                "bot_status.last_run_message": message,
            }
            if next_run_time:
                updates["bot_status.next_run_time"] = next_run_time
            if conn_state is not None:
                updates["bot_status.conn_state"]   = conn_state
                updates["bot_status.conn_message"] = message
                updates["bot_status.conn_updated"] = now_iso
            elif state in ("idle", "error"):
                updates["bot_status.conn_state"]   = state
                updates["bot_status.conn_message"] = message
                updates["bot_status.conn_updated"] = now_iso
            elif state == "running":
                updates["bot_status.conn_state"]   = "connected"
                updates["bot_status.conn_message"] = message or "البوت متصل بالقلعة ويعمل الآن"
                updates["bot_status.last_run_time"] = now_iso
                updates["bot_status.conn_updated"] = now_iso
            elif state == "waiting":
                updates["bot_status.conn_state"]   = "waiting"
                updates["bot_status.conn_message"] = message or "بانتظار الدورة القادمة"
                updates["bot_status.conn_updated"] = now_iso

            ref.update(updates)

        # ── تحديث كاش قاعدة بيانات SQLite المحلية ──
        try:
            from core.database import upsert_castle_conn_state
            effective_conn = conn_state
            if effective_conn is None:
                if state in ("idle", "error"):
                    effective_conn = state
                elif state == "running":
                    effective_conn = "connected"
                elif state == "waiting":
                    effective_conn = "waiting"
            effective_email = _castle_emails.get(castle_id) or castle_id
            upsert_castle_conn_state(
                email=effective_email,
                conn_state=effective_conn or state,
                message=message,
                next_run_time=next_run_time,
                user_id=user_id,
                castle_id=castle_id
            )
        except Exception:
            pass
    except Exception as e:
        log.debug(f"Firebase status update skipped: {e}")


_fb_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fb-sync")
_fb_lock = threading.Lock()
_last_fb_updates: Dict[str, Tuple[float, str, Optional[str]]] = {}

def update_firebase_status_async(user_id: str, castle_id: str, state: str, message: str = "", conn_state: Optional[str] = None, force: bool = False, next_run_time: Optional[str] = None):
    """تحديث Firestore عبر ThreadPoolExecutor مع خنق (Throttling) لمنع إرهاق الخادم وتجاوز حدود الحصص."""
    now = time.time()
    with _fb_lock:
        last = _last_fb_updates.get(castle_id)
        if not force and last:
            last_time, last_state, last_conn = last
            # إذا لم تتغير الحالة الأساسية أو حالة الاتصال ومضى أقل من 10 ثوانٍ، نتجاوز الكتابة لحماية الموارد
            if last_state == state and last_conn == conn_state and (now - last_time < 10.0):
                return
        _last_fb_updates[castle_id] = (now, state, conn_state)

    _fb_executor.submit(_update_firebase_status, user_id, castle_id, state, message, conn_state, next_run_time)


def _sync_castle_to_firebase(email: str, data: dict, user_id: Optional[str] = None, castle_id: Optional[str] = None):
    """تحديث موارد وبيانات القلعة في Firestore فوراً وبطريقة سريعة باستخدام collection_group."""
    try:
        _ensure_firebase()
        import firebase_admin
        from firebase_admin import firestore as fb_fs
        if firebase_admin._apps:
            db = fb_fs.client()
            target_ref = None
            if user_id and castle_id:
                target_ref = db.collection("users").document(user_id).collection("castles").document(castle_id)
            else:
                try:
                    from google.cloud.firestore import FieldFilter
                    castles = db.collection_group("castles").where(filter=FieldFilter("email", "==", email.strip().lower())).limit(1).stream()
                except Exception:
                    castles = db.collection_group("castles").where("email", "==", email.strip().lower()).limit(1).stream()
                for c in castles:
                    target_ref = c.reference
                    break

            if target_ref:
                flat_data = {}
                for k, v in data.items():
                    if isinstance(v, dict):
                        for subk, subv in v.items():
                            flat_data[f"{k}.{subk}"] = subv
                    else:
                        flat_data[k] = v
                target_ref.update(flat_data)
                log.info(f"💾 [API Sync] تم تحديث موارد وبيانات القلعة {email} في Firestore بنجاح ✅")

        # ── تحديث كاش قاعدة بيانات SQLite المحلية ──
        try:
            from core.database import upsert_castle_resources
            upsert_castle_resources(
                email=email,
                resources=data.get("resources", {}),
                castle_info=data.get("castle_info", {}),
                user_id=user_id,
                castle_id=castle_id
            )
        except Exception:
            pass
    except Exception as e:
        log.warning(f"⚠️ [API Sync Warning]: {e}")


_user_sub_cache: Dict[str, Tuple[float, bool, str]] = {}
_user_sub_cache_lock = threading.Lock()

def _check_user_sub_cached(user_id: str, max_age: float = 60.0) -> Tuple[bool, str]:
    """التحقق من اشتراك وحظر المستخدم مع تخزين مؤقت (60s TTL) لمنع استنزاف حصة Firestore اليومية."""
    now = time.time()
    with _user_sub_cache_lock:
        cached = _user_sub_cache.get(user_id)
        if cached and (now - cached[0] < max_age):
            return cached[1], cached[2]

    try:
        _ensure_firebase()
        import firebase_admin
        from firebase_admin import firestore as fb_fs
        if firebase_admin._apps:
            db = fb_fs.client()
            snap = db.collection("users").document(user_id).get()
            if snap.exists:
                from core.firebase_schema import check_user_subscription
                valid, reason = check_user_subscription(snap.to_dict() or {})
                with _user_sub_cache_lock:
                    _user_sub_cache[user_id] = (now, valid, reason)
                return valid, reason
    except Exception as e:
        log.debug(f"Subscription cached check error: {e}")
    return True, "صالح افتراضياً"


def _tail_file(filepath: str, n_lines: int = 100) -> List[str]:
    """قراءة آخر N أسطر من الملف بكفاءة عالية بدون تحميل الملف كاملاً في الذاكرة (Memory-Safe Tail)."""
    if not os.path.exists(filepath):
        return []
    try:
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return []
        buffer_size = min(file_size, max(4096, n_lines * 300))
        with open(filepath, "rb") as f:
            f.seek(file_size - buffer_size)
            raw_bytes = f.read(buffer_size)
        text = raw_bytes.decode("utf-8", errors="replace")
        lines = [l.strip("\r") for l in text.split("\n")]
        if buffer_size < file_size and len(lines) > 1:
            lines = lines[1:]
        return [l for l in lines if l][-n_lines:]
    except Exception as e:
        log.debug(f"Tail file error on {filepath}: {e}")
        return []


# ══════════════════════════════════════════════════════════════════
# تشغيل البوت مباشرةً كـ Thread خفيف (Thread Pool Architecture)
# لا subprocess — كل قلعة تشغّل BotManager داخل نفس الـ process
# ══════════════════════════════════════════════════════════════════

def _bot_thread(req: StartBotRequest):
    castle_id = req.castle_id
    user_id   = req.user_id
    email     = req.email

    # 1. إعداد queue للـ logs وإنشاء stop_event فوراً
    log_q: "queue.Queue[str]" = queue.Queue(maxsize=500)
    stop_event = threading.Event()
    with _lock:
        _log_qs[castle_id]      = log_q
        _stop_events[castle_id] = stop_event  # تسجيل فوري ليُمكن stop_bot() من الوصول
        _castle_emails[castle_id] = email
        _castle_users[castle_id]  = user_id
        _reserved.discard(castle_id)

    log.info(f"🚀 [{email}] بدء تشغيل البوت (Thread Pool)...")
    _update_firebase_status(user_id, castle_id, "running", "البوت يعمل الآن...")

    # 2. تسجيل الدخول إذا لم تكن الجلسة موجودة
    password = req.password
    if not password:
        try:
            _ensure_firebase()
            import firebase_admin
            from firebase_admin import firestore as fb_fs
            if firebase_admin._apps:
                db = fb_fs.client()
                c_snap = db.collection("users").document(user_id).collection("castles").document(castle_id).get()
                if c_snap.exists:
                    password = (c_snap.to_dict() or {}).get("password")
        except Exception as ex:
            log.warning(f"⚠️ فشل جلب كلمة المرور من Firestore: {ex}")

    try:
        from core.session_manager import SessionManager
        sm = SessionManager()
        sessions = sm.load()
        if email not in sessions:
            if password:
                log.info(f"🔑 [{email}] تسجيل دخول جديد وحفظ الجلسة...")
                log_q.put(f"[{datetime.now():%H:%M:%S}] 🔑 جاري تسجيل الدخول وحفظ الجلسة...")
                sm.login_and_save(email, password)
                log_q.put(f"[{datetime.now():%H:%M:%S}] ✅ تم تسجيل الدخول بنجاح")
            else:
                err_msg = f"كلمة المرور غير مسجلة لحساب {email}. يرجى تعديل القلعة وحفظ كلمة المرور."
                log.error(f"❌ {err_msg}")
                log_q.put(f"[{datetime.now():%H:%M:%S}] ❌ {err_msg}")
                _update_firebase_status(user_id, castle_id, "error", err_msg, conn_state="error")
                return
    except Exception as e:
        err_str = str(e)
        log.warning(f"⚠️ [{email}] خطأ في تسجيل الدخول: {err_str}")
        log_q.put(f"[{datetime.now():%H:%M:%S}] ❌ خطأ تسجيل الدخول: {err_str}")
        _update_firebase_status(user_id, castle_id, "error", f"خطأ تسجيل الدخول: {err_str}", conn_state="error")
        return

    # 3. ملف log البوت مع التدوير التلقائي
    bot_log_path = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
    try:
        if os.path.exists(bot_log_path) and os.path.getsize(bot_log_path) > 10 * 1024 * 1024:
            bak_log = bot_log_path + ".1"
            if os.path.exists(bak_log):
                try: os.remove(bak_log)
                except Exception: pass
            try: os.replace(bot_log_path, bak_log)
            except Exception: pass
    except Exception:
        pass

    # 4. إعداد log_callback — يُرسل كل سطر إلى queue اللوحة وملف الـ log معاً
    import re as _re
    _log_file_handle = None
    try:
        _log_file_handle = open(bot_log_path, "a", encoding="utf-8", errors="replace")
        _log_file_handle.write(f"\n{'='*60}\n[{datetime.now():%Y-%m-%d %H:%M:%S}] دورة جديدة\n{'='*60}\n")
        _log_file_handle.flush()
    except Exception:
        pass

    def _log_callback(line: str):
        """يُعالج كل سطر من BotManager: يكتبه للـ log file ويُرسله للـ queue ويُحدّث conn_state."""
        if _log_file_handle:
            try:
                _log_file_handle.write(line + "\n")
                _log_file_handle.flush()
            except Exception:
                pass
        stamped = f"[{datetime.now():%H:%M:%S}] {line}"
        try:
            log_q.put_nowait(stamped)
        except queue.Full:
            pass

        if stop_event.is_set():
            return

        # ── تحليل [FIREBASE_EVENT] ──
        if "[FIREBASE_EVENT]" in line:
            try:
                parts = line.split("[FIREBASE_EVENT]", 1)[1].strip()
                m_st  = _re.search(r'conn_state=(\w+)', parts)
                m_nr  = _re.search(r'next_run_time=(\S+)', parts)
                m_msg = _re.search(r'message=(.+?)(?:\s+next_run_time=\S+)?$', parts)
                ev_state = m_st.group(1) if m_st else ""
                ev_msg   = m_msg.group(1).strip() if m_msg else ""
                ev_nr    = m_nr.group(1) if m_nr else None
                if ev_state:
                    with _lock:
                        prev_ev = _conn_states.get(castle_id)
                        _conn_states[castle_id] = ev_state
                    if prev_ev != ev_state:
                        bs = "idle" if ev_state == "idle" else ("waiting" if ev_state == "waiting" else "running")
                        update_firebase_status_async(user_id, castle_id, bs, ev_msg or line, ev_state, next_run_time=ev_nr)
            except Exception as ex:
                log.debug(f"Firebase event parse error: {ex}")

        # ── تحليل [RESOURCE_SYNC] ──
        elif "[RESOURCE_SYNC]" in line:
            try:
                parts = line.split("[RESOURCE_SYNC]", 1)[1].strip()
                rmap = {}
                for token in parts.split():
                    if "=" in token:
                        k, v = token.split("=", 1)
                        if v.lstrip("-").isdigit():
                            rmap[k] = int(v)
                if rmap:
                    now_iso = datetime.now(timezone.utc).isoformat()
                    r_data = {
                        "food":         rmap.get("food", 0),
                        "wood":         rmap.get("wood", 0),
                        "iron":         rmap.get("iron", 0),
                        "diamond":      rmap.get("diamond", 0),
                        "gold":         rmap.get("gold", 0),
                        "stamina":      rmap.get("stamina", 100),
                        "last_updated": now_iso,
                    }
                    c_data = {}
                    if "power" in rmap:
                        c_data["lord_power"] = rmap["power"]
                    _sync_castle_to_firebase(
                        email,
                        {"resources": r_data, "castle_info": c_data} if c_data else {"resources": r_data},
                        user_id=user_id,
                        castle_id=castle_id,
                    )
            except Exception as ex:
                log.debug(f"Resource sync parse error: {ex}")

    # 5. فحص الاشتراك دورياً في thread خفيف
    forced_stop_reason = ""

    def _subscription_guard():
        nonlocal forced_stop_reason
        check_counter = 0
        while not stop_event.wait(timeout=5):
            check_counter += 1
            if check_counter % 6 == 0:
                valid, reason = _check_user_sub_cached(user_id)
                if not valid:
                    forced_stop_reason = reason
                    log.warning(f"🛑 [{email}] انتهاء اشتراك أو حظر: {reason}")
                    stop_event.set()
                    break
            if check_counter % 12 == 0:
                try:
                    import firebase_admin
                    from firebase_admin import firestore as fb_fs
                    if firebase_admin._apps:
                        db = fb_fs.client()
                        c_snap = db.collection("users").document(user_id).collection("castles").document(castle_id).get()
                        if c_snap.exists:
                            c_state = (c_snap.to_dict() or {}).get("bot_status", {}).get("state", "idle")
                            if c_state in ("idle", "banned"):
                                log.info(f"⏹️ [{email}] طلب إيقاف من Firestore (state={c_state})")
                                stop_event.set()
                                break
                except Exception as ex:
                    log.debug(f"Castle guard exception: {ex}")

    guard_t = threading.Thread(target=_subscription_guard, daemon=True, name=f"guard-{castle_id[:10]}")
    guard_t.start()

    # 6. تشغيل BotManager مباشرةً داخل نفس الـ process
    try:
        # إعادة تحميل الوحدات لضمان تطبيق أي تعديلات برمجية جديدة تلقائياً
        import sys, importlib
        for mod_name in ("tasks.march_manager", "bot_manager"):
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception:
                    pass
        from bot_manager import BotManager
        manager = BotManager(
            email,
            req.config,
            reconnect_wait_seconds=60,
            user_id=user_id,
            castle_id=castle_id,
            stop_event=stop_event,
            log_callback=_log_callback,
        )
        asyncio.run(manager.run_loop(loop_interval_minutes=req.loop_interval))

    except Exception as e:
        log.error(f"💥 [{email}] خطأ في البوت: {e}", exc_info=True)
        log_q.put(f"[{datetime.now():%H:%M:%S}] 💥 خطأ: {e}")
        _update_firebase_status(user_id, castle_id, "error", str(e), conn_state="error")
    finally:
        stop_event.set()
        if _log_file_handle:
            try: _log_file_handle.close()
            except Exception: pass

        was_user_stopped = castle_id in _user_stopped
        with _lock:
            _threads.pop(castle_id, None)
            _stop_events.pop(castle_id, None)
            _log_qs.pop(castle_id, None)
            _conn_states.pop(castle_id, None)
            _castle_users.pop(castle_id, None)
            _user_stopped.discard(castle_id)

    # 7. تحديث الحالة النهائية
    if forced_stop_reason:
        log_q.put(f"[{datetime.now():%H:%M:%S}] 🛑 إيقاف إجباري: {forced_stop_reason}")
        log.info(f"🛑 [{email}] إيقاف إجباري: {forced_stop_reason}")
        _update_firebase_status(user_id, castle_id, "idle", f"متوقف إجبارياً: {forced_stop_reason}", conn_state="idle")
    elif was_user_stopped:
        log_q.put(f"[{datetime.now():%H:%M:%S}] ⏹️ تم إيقاف البوت بواسطة المستخدم")
        log.info(f"⏹️ [{email}] إيقاف يدوي")
        _update_firebase_status(user_id, castle_id, "idle", "تم إيقاف البوت بواسطة المستخدم", conn_state="idle")
    else:
        log.info(f"💤 [{email}] اكتمل البوت بشكل طبيعي")
        _update_firebase_status(user_id, castle_id, "idle", "اكتمل البوت", conn_state="idle")


# ══════════════════════════════════════════════════════════════════
# Authentication & RBAC Dependencies
# ══════════════════════════════════════════════════════════════════

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)) -> Dict[str, Any]:
    """
    التحقق من هوية المستخدم وصلاحيته عبر Firebase ID Token المشفر.
    في حال تفعيل REQUIRE_AUTH=1 (بيئة الإنتاج والـ VPS)، يُرفض أي طلب لا يحمل توكن سليم.
    في حال كان REQUIRE_AUTH=0 ولم يُرسل توكن، يُسمح بالوصول المحلي للتطوير والتجارب.
    """
    require_auth = os.environ.get("REQUIRE_AUTH", "0") == "1"

    if not credentials or not credentials.credentials:
        if require_auth:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        return {"uid": "local_dev", "role": "admin", "email": "dev@local"}

    token = credentials.credentials
    try:
        _ensure_firebase()
        import firebase_admin
        from firebase_admin import auth as fb_auth

        if not firebase_admin._apps:
            if not require_auth:
                return {"uid": "local_dev", "role": "admin", "email": "dev@local"}
            raise HTTPException(status_code=500, detail="Firebase Admin SDK is not initialized")

        decoded = fb_auth.verify_id_token(token)
        return decoded
    except Exception as e:
        log.warning(f"🔒 Token verification failed: {e}")
        if not require_auth:
            return {"uid": "local_dev", "role": "admin", "email": "dev@local"}
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {e}")


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """التأكد من أن المستخدم يتمتع بصلاحية المشرف (Admin)."""
    uid = user.get("uid", "")
    if uid == "local_dev":
        return user

    if user.get("admin") is True or user.get("role") == "admin":
        return user

    try:
        import firebase_admin
        from firebase_admin import firestore as fb_fs
        if firebase_admin._apps:
            db = fb_fs.client()
            snap = db.collection("users").document(uid).get()
            if snap.exists:
                role = (snap.to_dict() or {}).get("role", "user")
                if role == "admin":
                    return user
    except Exception as e:
        log.debug(f"Admin verification check error: {e}")

    raise HTTPException(status_code=403, detail="هذا الإجراء يتطلب صلاحية المشرف (Admin required)")


# ══════════════════════════════════════════════════════════════════
# API Endpoints
# ══════════════════════════════════════════════════════════════════

@app.get("/")
@app.get("/api/health")
def root():
    return {"status": "online", "service": "Empire Bot API", "time": datetime.now().isoformat()}


@app.post("/api/bot/start")
def start_bot(req: StartBotRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تشغيل بوت لقلعة معينة مع التحقق من هوية المستخدم وصلاحية الاشتراك."""
    caller_uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or caller_uid == "local_dev")

    # حظر تشغيل قلاع مستخدمين آخرين
    if not is_admin and caller_uid != req.user_id:
        raise HTTPException(status_code=403, detail="غير مصرح بتشغيل قلاع مستخدم آخر")

    # 1. التحقق من صلاحية الاشتراك وحظر الحساب (بحد زمني 4 ثوانٍ لضمان استجابة سريعة)
    try:
        _ensure_firebase()
        import firebase_admin
        from firebase_admin import firestore as fb_fs
        if firebase_admin._apps:
            db = fb_fs.client()
            user_snap = db.collection("users").document(req.user_id).get(timeout=4)
            if user_snap.exists:
                user_doc = user_snap.to_dict() or {}
                from core.firebase_schema import check_user_subscription
                valid, reason = check_user_subscription(user_doc)
                if not valid:
                    log.warning(f"🛑 [{req.email}] تم رفض بدء التشغيل: {reason}")
                    _update_firebase_status(req.user_id, req.castle_id, "idle", f"متوقف: {reason}")
                    raise HTTPException(status_code=403, detail=f"لا يمكن تشغيل البوت: {reason}")
    except HTTPException:
        raise
    except Exception as ex:
        log.warning(f"⚠️ تنبيه أثناء فحص الاشتراك في start_bot: {ex}")

    with _lock:
        if _is_running(req.castle_id):
            return {"status": "already_running", "castle_id": req.castle_id, "email": req.email}
        _reserved.add(req.castle_id)  # حجز فوري لمنع التكرار

    t = threading.Thread(target=_bot_thread, args=(req,), daemon=True, name=f"bot-{req.castle_id[:10]}")
    with _lock:
        _threads[req.castle_id] = t  # تسجيل فوري قبل الإطلاق
    t.start()
    log.info(f"▶️  [{req.email}] طلب تشغيل قُبل من {caller_uid}")
    return {"status": "starting", "castle_id": req.castle_id, "email": req.email}


@app.post("/api/bot/stop/{castle_id}")
def stop_bot(castle_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """إيقاف بوت قلعة معينة بناءً على طلب المستخدم أو المشرف."""
    caller_uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or caller_uid == "local_dev")

    with _lock:
        owner_uid = _castle_users.get(castle_id)

    if not is_admin and owner_uid and owner_uid != caller_uid:
        raise HTTPException(status_code=403, detail="غير مصرح بإيقاف قلاع مستخدم آخر")

    with _lock:
        ev = _stop_events.get(castle_id)
        is_active = _is_running(castle_id)
        _user_stopped.add(castle_id)

    if is_active:
        if ev:
            ev.set()  # إشارة للـ BotManager يوقف نفسه بنظافة
        log.info(f"⏹️  إيقاف القلعة {castle_id[:16]} بواسطة {caller_uid}...")
        return {"status": "stopping", "castle_id": castle_id}

    return {"status": "not_running", "castle_id": castle_id}


@app.post("/api/bot/stop-user/{user_id}")
def stop_user_bots(user_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """إيقاف جميع بوتات المستخدم فوراً بالقوة (متاح للمشرف فقط وعند الحظر أو انتهاء الاشتراك)."""
    stopped = []
    with _lock:
        targets = [cid for cid, uid in _castle_users.items() if uid == user_id]
        for cid in targets:
            _user_stopped.add(cid)
            ev = _stop_events.get(cid)
            t  = _threads.get(cid)
            if t and t.is_alive():
                if ev:
                    ev.set()  # إيقاف نظيف عبر event
                stopped.append(cid)
    log.info(f"🛑 [Force Stop] تم إيقاف {len(stopped)} بوت جاري للمستخدم {user_id} بالقوة من المشرف {admin.get('uid')}")
    return {"status": "ok", "stopped_count": len(stopped), "stopped_castles": stopped}


@app.get("/api/bot/status")
def get_all_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """حالة جميع البوتات النشطة."""
    with _lock:
        result = {}
        for cid, t in _threads.items():
            result[cid] = "running" if t.is_alive() else "idle"
        for cid in _reserved:
            result[cid] = "starting"
    return {"bots": result, "count": len(result)}


@app.get("/api/bot/status/{castle_id}")
def get_status(castle_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """حالة بوت قلعة معينة."""
    return {"castle_id": castle_id, "status": _get_real_status(castle_id)}


# ── endpoint يستقبل حالة اتصال اللعبة من bot_manager مباشرةً ──────
class ConnStateRequest(BaseModel):
    castle_id: str
    state: str  # 'connected' | 'disconnected' | 'reconnecting'

@app.post("/api/bot/conn-state")
def update_conn_state(req: ConnStateRequest):
    """يُستدعى من bot_manager لإبلاغ الـ API عن حالة اتصال اللعبة الفعلية."""
    with _lock:
        if req.state in ('connected', 'disconnected', 'reconnecting'):
            _conn_states[req.castle_id] = req.state
        elif req.state == 'idle':
            _conn_states.pop(req.castle_id, None)
    log.info(f"📶 [{req.castle_id[:12]}] conn-state → {req.state}")
    return {"ok": True}


# ── endpoints سريعة لقراءة كاش القلاع من قاعدة بيانات SQLite المحلية ──
@app.get("/api/local/castles")
def get_local_castles(user_id: Optional[str] = None):
    """جلب قائمة بكافة القلاع وحالاتها المخزنة محلياً في SQLite بسرعة فائقة."""
    from core.database import get_all_castles
    return {"castles": get_all_castles(user_id=user_id)}


@app.get("/api/local/castles/{identifier}")
def get_local_castle(identifier: str):
    """استرجاع بيانات وحالة قلعة معينة من قاعدة بيانات SQLite المحلية بلمح البصر."""
    from core.database import get_castle
    c = get_castle(identifier)
    if not c:
        raise HTTPException(status_code=404, detail="Castle not found in local database")
    return {"castle": c}


@app.get("/api/castle-data/{email}")
async def get_castle_data(email: str, user_id: Optional[str] = None, castle_id: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    جلب بيانات القلعة والموارد الحية فوراً بالاتصال المباشر مع سيرفر اللعبة ومزامنتها مع Firestore.
    """
    try:
        from core.session_manager import SessionManager
        from game_client import GameConnection

        # 1. تحميل جلسة الحساب
        sm = SessionManager()
        sessions = sm.load()
        account = sessions.get(email)
        if not account:
            raise HTTPException(status_code=404, detail=f"الحساب {email} غير موجود في session_cache.json")

        # 2. الاتصال بالسيرفر
        conn = GameConnection(account)
        ok = await asyncio.wait_for(conn.connect(), timeout=15)
        if not ok:
            raise HTTPException(status_code=503, detail="تعذر الاتصال بسيرفر اللعبة")

        # 3. انتظار حزم التهيئة الأولية
        for _ in range(15):
            await asyncio.sleep(0.3)
            if len(conn.init_data) > 0:
                break

        # 4. استعلام مباني وموارد المدينة (1001/1)
        r_city = None
        try:
            r_city = await asyncio.wait_for(conn.query("1001", "1", {}, timeout=8), timeout=10)
        except Exception:
            pass

        city_data = r_city.get("data", {}) if r_city and isinstance(r_city, dict) else {}
        city_ctrl = conn.init_data.get("cityCtrl", {})
        reslist   = city_data.get("reslist") or city_ctrl.get("reslist", {})
        saferes   = city_data.get("saferes") or city_ctrl.get("saferes", {})
        blist     = city_data.get("blist") or city_ctrl.get("blist", [])

        # استعلام بيانات اللورد والقوة (1002/7) إذا لم تكن متوفرة في init_data
        lord_ctrl = conn.init_data.get("lordInfoCtrl", {})
        base_info = lord_ctrl.get("base", {}) if isinstance(lord_ctrl, dict) else {}
        fc_info   = lord_ctrl.get("fcInfo", {}) if isinstance(lord_ctrl, dict) else {}

        if not base_info or not fc_info:
            uid_val = getattr(conn, "uid", None) or getattr(account, "user_id", None)
            if uid_val:
                try:
                    uid_int = int(uid_val) if str(uid_val).isdigit() else uid_val
                    r_lord = await asyncio.wait_for(conn.query("1002", "7", {"uid": uid_int}, timeout=6), timeout=8)
                    if r_lord and isinstance(r_lord.get("data"), dict):
                        base_info = r_lord["data"].get("base", {}) or base_info
                        fc_info   = r_lord["data"].get("fcInfo", {}) or fc_info
                except Exception:
                    pass

        food    = int(float(reslist.get("1002", saferes.get("1002", 0))))
        wood    = int(float(reslist.get("1003", saferes.get("1003", 0))))
        iron    = int(float(reslist.get("1004", saferes.get("1004", 0))))
        diamond = int(float(reslist.get("1005", saferes.get("1005", 0))))
        gold    = int(float(base_info.get("gold", reslist.get("1006", saferes.get("1006", 0)))))
        stamina = int(float(base_info.get("health", 100)))
        pos     = base_info.get("sourcePos", {})
        coords  = {"x": int(pos.get("x", 0)), "y": int(pos.get("y", 0))}

        castle_lv  = 0
        walls_lv   = 0

        for b in blist:
            bid = int(b.get("bid", 0))
            lv  = int(b.get("lv", 0))
            if bid == 101:
                castle_lv = lv
            elif bid == 102:
                walls_lv  = lv

        now_iso = datetime.now(timezone.utc).isoformat()
        res_data = {
            "food":         food,
            "wood":         wood,
            "iron":         iron,
            "diamond":      diamond,
            "gold":         gold,
            "stamina":      stamina,
            "last_updated": now_iso,
        }
        cinfo_data = {
            "lord_name":    str(base_info.get("nickName", email.split("@")[0])),
            "lord_power":   int(fc_info.get("totalFc", 0)),
            "castle_level": max(1, castle_lv),
            "walls_level":  walls_lv,
            "server_id":    int(base_info.get("partition", 1)) if str(base_info.get("partition", "")).isdigit() else 1,
            "coordinates":  coords,
            "uid":          str(base_info.get("uid", getattr(account, "user_id", ""))),
        }

        # مزامنة فورية مع Firestore
        _sync_castle_to_firebase(email, {"resources": res_data, "castle_info": cinfo_data}, user_id=user_id, castle_id=castle_id)

        return {
            "success":      True,
            "email":        email,
            "lord_name":    cinfo_data["lord_name"],
            "lord_level":   int(base_info.get("level", 0)),
            "kingdom_id":   str(base_info.get("partition", "")),
            "gold":         gold,
            "total_power":  cinfo_data["lord_power"],
            "uid":          cinfo_data["uid"],
            "castle_level": castle_lv,
            "walls_level":  walls_lv,
            "coordinates":  coords,
            "resources":    res_data,
            "fetched_at":   now_iso,
        }

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="انتهت مهلة الاتصال بسيرفر اللعبة (timeout)")
    except Exception as e:
        log.error(f"❌ [castle-data] فشل جلب بيانات القلعة لـ {email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals() and conn:
            try:
                await conn.close()
            except Exception:
                pass


@app.get("/api/errors")
def get_error_log(lines: int = 100, admin: Dict[str, Any] = Depends(require_admin)):
    """
    قراءة آخر N سطر من سجل الأخطاء bot_errors.log لمراجعتها (خاص بالمشرف فقط).
    مثال: GET /api/errors?lines=50
    """
    log_path = os.path.join(_ROOT, "bot_errors.log")
    if not os.path.exists(log_path):
        return {"errors": [], "count": 0, "message": "لا توجد أخطاء مسجلة حتى الآن ✅"}

    last_lines = _tail_file(log_path, n_lines=lines)
    return {
        "errors": last_lines,
        "count":  len(last_lines),
        "showing": len(last_lines),
        "log_path": log_path,
    }


@app.get("/api/logs/{castle_id}")
def get_castle_logs(castle_id: str, lines: int = 100, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    قراءة آخر N سطر من ملف log الخاص بالقلعة محلياً من القرص دون أي اتصال بـ Firebase.
    مثال: GET /api/logs/{castle_id}?lines=50
    """
    caller_uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or caller_uid == "local_dev")

    with _lock:
        owner_uid = _castle_users.get(castle_id)
    if not is_admin and owner_uid and owner_uid != caller_uid:
        raise HTTPException(status_code=403, detail="غير مصرح بقراءة سجلات قلعة مستخدم آخر")
    email = _castle_emails.get(castle_id)
    log_path = None
    if email:
        p = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
        if os.path.exists(p):
            log_path = p

    if not log_path:
        candidates = [
            os.path.join(_ROOT, f) for f in os.listdir(_ROOT)
            if f.startswith("bot_") and f.endswith(".log") and f != "bot_errors.log"
        ]
        if candidates:
            log_path = max(candidates, key=os.path.getmtime)

    if not log_path or not os.path.exists(log_path):
        return {"logs": [], "count": 0, "message": "لا يوجد سجل محلي بعد"}

    last_lines = _tail_file(log_path, n_lines=lines)
    return {
        "logs": last_lines,
        "count": len(last_lines),
        "showing": len(last_lines),
        "file": os.path.basename(log_path),
    }


@app.websocket("/ws/logs/{castle_id}")
async def ws_logs(websocket: WebSocket, castle_id: str):
    """
    WebSocket للـ logs المباشرة لبوت قلعة معينة (محلياً 100% بدون أي اتصال بفايربيس).
    الاتصال: ws://localhost:8000/ws/logs/{castle_id}
    """
    await websocket.accept()
    log.info(f"📡 WebSocket logs connected: {castle_id[:16]}")

    # 1. إرسال أحدث 30 سطراً من ملف الـ log المحلي فور الاتصال
    email = _castle_emails.get(castle_id)
    log_path = None
    if email:
        p = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
        if os.path.exists(p):
            log_path = p
    if not log_path:
        candidates = [
            os.path.join(_ROOT, f) for f in os.listdir(_ROOT)
            if f.startswith("bot_") and f.endswith(".log") and f != "bot_errors.log"
        ]
        if candidates:
            log_path = max(candidates, key=os.path.getmtime)

    if log_path and os.path.exists(log_path):
        recent = _tail_file(log_path, n_lines=35)
        for r in recent:
            try:
                await websocket.send_text(r)
            except Exception:
                break

    # 2. البث المباشر لأي أسطر جديدة تخرج من البوت
    try:
        while True:
            with _lock:
                q = _log_qs.get(castle_id)

            if q:
                lines_sent = 0
                while lines_sent < 30:
                    try:
                        line = q.get_nowait()
                        await websocket.send_text(line)
                        lines_sent += 1
                    except queue.Empty:
                        break

            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        log.info(f"📡 WebSocket logs disconnected: {castle_id[:16]}")
    except Exception as e:
        log.debug(f"WebSocket error: {e}")


@app.websocket("/ws/status/{castle_id}")
async def ws_status(websocket: WebSocket, castle_id: str):
    """
    WebSocket خفيف لمراقبة حالة البوت الحقيقية في الوقت الفعلي.
    يُرسل الحالة فور الاتصال ثم فقط عند التغيير (لا polling على الشبكة).
    الحالات: running | starting | disconnected | reconnecting | idle | offline
    """
    await websocket.accept()

    last_status = _get_real_status(castle_id)
    await websocket.send_text(last_status)

    try:
        while True:
            await asyncio.sleep(1)  # فحص في الذاكرة فقط — بدون شبكة
            current = _get_real_status(castle_id)
            if current != last_status:
                last_status = current
                await websocket.send_text(current)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# الحارس الأمني والدوري لخادم API (Security & Subscription Watchdog)
# ══════════════════════════════════════════════════════════════════

def _watchdog_loop():
    """حارس دوري يفحص كل 45 ثانية جميع العمليات الجارية للتأكد من عدم وجود بوتات لحسابات محظورة أو منتهية."""
    while True:
        time.sleep(45)
        try:
            import firebase_admin
            from firebase_admin import firestore as fb_fs
            if not firebase_admin._apps:
                continue
            db = fb_fs.client()
            with _lock:
                active_items = list(_castle_users.items())
            
            for cid, uid in active_items:
                try:
                    valid, reason = _check_user_sub_cached(uid)
                    if not valid:
                        log.warning(f"🛡️ [Watchdog] كشف قلعة غير مصرح بها {cid[:10]} (المستخدم: {uid}): {reason}")
                        with _lock:
                            _user_stopped.add(cid)
                            ev = _stop_events.get(cid)
                            if ev:
                                ev.set()
                        _update_firebase_status(uid, cid, "idle", f"متوقف إجبارياً: {reason}", conn_state="idle")
                except Exception:
                    pass
        except Exception as ex:
            log.debug(f"Watchdog exception: {ex}")

# تشغيل الحارس في الخلفية
threading.Thread(target=_watchdog_loop, daemon=True, name="bot-watchdog").start()


def _reset_orphaned_running_states():
    """تنظيف القلاع العالقة في حالة running عند إقلاع الخادم بعد ريستارت أو كراش."""
    def _bg_reset():
        try:
            time.sleep(3)  # انتظار اكتمال تهيئة Firebase
            _ensure_firebase()
            import firebase_admin
            from firebase_admin import firestore as fb_fs
            if firebase_admin._apps:
                db = fb_fs.client()
                try:
                    from google.cloud.firestore import FieldFilter
                    castles = db.collection_group("castles").where(filter=FieldFilter("bot_status.state", "==", "running")).stream()
                except Exception:
                    castles = db.collection_group("castles").where("bot_status.state", "==", "running").stream()
                reset_count = 0
                for c in castles:
                    try:
                        c.reference.update({
                            "bot_status.state": "idle",
                            "bot_status.conn_state": "idle",
                            "bot_status.last_run_message": "جاهز للتشغيل (أعيد تشغيل السيرفر بأمان)",
                        })
                        reset_count += 1
                    except Exception:
                        pass
                if reset_count > 0:
                    log.info(f"🧹 [Startup Reset] تم إعادة ضبط {reset_count} قلعة عالقة من التشغيل السابق إلى idle بنجاح.")
        except Exception as e:
            log.debug(f"Startup reset warning: {e}")

    threading.Thread(target=_bg_reset, daemon=True, name="startup-reset").start()

# تشغيل تنظيف الحالات العالقة عند إقلاع السيرفر
_reset_orphaned_running_states()


# ══════════════════════════════════════════════════════════════════
# نقطة الدخول
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Empire Bot API Server")
    parser.add_argument("--host",  default="0.0.0.0",  help="عنوان الاستماع [0.0.0.0]")
    parser.add_argument("--port",  type=int, default=8000, help="المنفذ [8000]")
    parser.add_argument("--reload", action="store_true", help="إعادة تحميل تلقائي عند التعديل (تطوير)")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("🚀 Empire Bot API Server")
    print(f"   العنوان  : http://{args.host}:{args.port}")
    print(f"   الوثائق  : http://localhost:{args.port}/docs")
    print(f"   الوقت    : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("═" * 60 + "\n")

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="warning",  # نستخدم logging الخاص بنا
    )


if __name__ == "__main__":
    main()
