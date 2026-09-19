# -*- coding: utf-8 -*-
"""
api_server.py — خادم FastAPI لإدارة البوتات وحسابات القلاع والمستخدمين
══════════════════════════════════════════════════════════════════════
يستقبل أوامر من لوحة التحكم (React) ويشغّل/يوقف bot_manager.py.
يعتمد كلياً على SQLite المحلية (castles.db) لجميع العمليات والبيانات.
يستخدم Firebase Admin SDK حصراً للتحقق من هوية المستخدم (ID Token Auth).

يعمل محلياً على المنفذ 8000 — وعلى Hostinger VPS بنفس الكود.

التشغيل:
  python api_server.py
  python api_server.py --port 8000 --host 0.0.0.0
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import os, sys, json, time, logging, argparse, threading, asyncio, queue, signal, uuid
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
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

# ── Database imports (SQLite local layer) ─────────────────────────
import core.database as db

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

app = FastAPI(title="Empire Bot API", version="2.0.0")

# قراءة النطاقات المسموحة من متغيرات البيئة لدعم بيئات الإنتاج والـ VPS
_cors_origins_env = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,https://ibraabot.online")
_allowed_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins if "*" not in _allowed_origins else ["*"],
    allow_credentials=True if "*" not in _allowed_origins else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ══════════════════════════════════════════════════════════════════
# إدارة الـ Threads (Thread Pool Architecture)
# ══════════════════════════════════════════════════════════════════

_lock         = threading.RLock()
_threads:     Dict[str, threading.Thread] = {}   # castle_id → thread
_stop_events: Dict[str, threading.Event]  = {}   # castle_id → stop signal
_bot_managers: Dict[str, Any]             = {}   # castle_id → BotManager instance
_reserved:    Set[str]                    = set() # castle_ids محجوزة (بدأت لكن لم تُسجَّل بعد)
_log_qs:      Dict[str, "queue.Queue[str]"] = {}  # castle_id → queue للـ logs
_conn_states: Dict[str, str]              = {}    # castle_id → 'connected' | 'disconnected' | 'reconnecting' | 'waiting'
_user_stopped: Set[str]                   = set() # castle_ids التي تم إيقافها يدوياً من المستخدم
_castle_emails: Dict[str, str]            = {}    # castle_id → email
_castle_users:  Dict[str, str]            = {}    # castle_id → user_id

# ══════════════════════════════════════════════════════════════════
# إدارة تسجيل السجلات على القرص (تخفيف الحمل واستهلاك الموارد)
# ══════════════════════════════════════════════════════════════════
ALLOWED_LOG_USER_EMAIL = "shreher@gmail.com"


def _is_log_file_allowed(user_id: str, email: str) -> bool:
    """
    التحقق مما إذا كان مسموحاً بحفظ سجل البوت في ملف على القرص (bot_*.log).
    مسموح فقط لقلاع المستخدم صاحب البريد shreher@gmail.com لتخفيف الحمل واستهلاك موارد السيرفر.
    """
    target = ALLOWED_LOG_USER_EMAIL.strip().lower()
    # 1. فحص إيميل القلعة المباشر
    if email and email.strip().lower() == target:
        return True
    # 2. فحص معرف المستخدم (UID) أو إيميل مالك القلعة
    if user_id:
        if user_id.strip().lower() == target:
            return True
        try:
            u = db.get_user(user_id)
            if u and str(u.get("email", "")).strip().lower() == target:
                return True
        except Exception:
            pass
    return False


def cleanup_unauthorized_bot_logs():
    """
    تنظيف كافة ملفات bot_*.log القديمة غير المصرح بها على القرص لتخفيف الحمل وتوفير المساحة،
    مع الإبقاء فقط على سجلات قلاع المستخدم shreher@gmail.com وسجل الأخطاء العام bot_errors.log.
    """
    try:
        allowed_safe_names = {
            ALLOWED_LOG_USER_EMAIL.strip().lower().replace("@", "_").replace(".", "_")
        }
        try:
            with db.get_connection() as conn:
                cur = conn.execute("""
                    SELECT cs.email FROM castle_states cs
                    JOIN users u ON cs.user_id = u.uid
                    WHERE LOWER(u.email) = ?
                """, (ALLOWED_LOG_USER_EMAIL.strip().lower(),))
                for row in cur.fetchall():
                    if row["email"]:
                        allowed_safe_names.add(
                            row["email"].strip().lower().replace("@", "_").replace(".", "_")
                        )
        except Exception as e:
            log.warning(f"Error fetching allowed emails for logs: {e}")

        removed_count = 0
        for fname in os.listdir(_ROOT):
            if fname.startswith("bot_") and fname.endswith(".log") and fname != "bot_errors.log":
                safe_name = fname[4:-4].lower()
                if safe_name not in allowed_safe_names:
                    try:
                        os.remove(os.path.join(_ROOT, fname))
                        removed_count += 1
                    except Exception:
                        pass
        if removed_count > 0:
            log.info(f"🧹 تم حذف {removed_count} ملف log غير مصرح به لتخفيف الحمل على القرص.")
    except Exception as ex:
        log.warning(f"Error in cleanup_unauthorized_bot_logs: {ex}")


def _is_running(castle_id: str) -> bool:
    with _lock:
        if castle_id in _user_stopped:
            return False
        if castle_id in _reserved:
            return True
        t = _threads.get(castle_id)
        if t is not None and t.is_alive():
            return True
        prefix = f"bot-{castle_id[:10]}"
        for th in threading.enumerate():
            if th.name == prefix and th.is_alive():
                _threads[castle_id] = th
                return True
        return False


def _get_real_status(castle_id: str) -> str:
    """الحالة الحقيقية: الـ thread + حالة اتصال اللعبة معاً، فورية وبدون أي تأخير عند الإيقاف."""
    with _lock:
        if castle_id in _user_stopped:
            return 'idle'
        if castle_id in _reserved:
            return 'starting'
        t = _threads.get(castle_id)
        if t is None or not t.is_alive():
            prefix = f"bot-{castle_id[:10]}"
            found_t = None
            for th in threading.enumerate():
                if th.name == prefix and th.is_alive():
                    found_t = th
                    _threads[castle_id] = th
                    break
            if not found_t:
                return 'idle'
        conn = _conn_states.get(castle_id, 'connected')
        if conn == 'disconnected':
            return 'disconnected'
        if conn == 'reconnecting':
            return 'reconnecting'
        if conn == 'waiting':
            return 'waiting'
        return 'running'


# ══════════════════════════════════════════════════════════════════
# Pydantic Request & Response Models
# ══════════════════════════════════════════════════════════════════

class StartBotRequest(BaseModel):
    castle_id:     str
    user_id:       str
    email:         str
    password:      Optional[str] = None
    config:        Optional[Dict[str, Any]] = None
    loop_interval: int = 90

class StopBotRequest(BaseModel):
    castle_id: str

class ConnStateRequest(BaseModel):
    castle_id: str
    state: str

class UserRegisterRequest(BaseModel):
    uid:       str
    email:     str
    username:  Optional[str] = ""
    phone:     Optional[str] = ""

class UserProfileUpdateRequest(BaseModel):
    username:  Optional[str] = None
    phone:     Optional[str] = None

class CastleCreateRequest(BaseModel):
    castle_id:   Optional[str] = None
    email:       str
    password:    str = ""
    castle_name: Optional[str] = ""
    config:      Optional[Dict[str, Any]] = None

class CastleUpdateRequest(BaseModel):
    castle_name: Optional[str] = None
    config:      Optional[Dict[str, Any]] = None

class CastleCredentialsUpdateRequest(BaseModel):
    email:    str
    password: Optional[str] = ""

class CastleToggleActiveRequest(BaseModel):
    is_active: bool

class AdminSubscriptionUpdateRequest(BaseModel):
    plan_id:             str
    plan_name:           str
    subscription_status: str = "active"
    expires_at:          str
    max_castles_allowed: int = 1

class AdminBanUserRequest(BaseModel):
    is_banned: bool
    reason:    Optional[str] = ""

class AdminCastleActionRequest(BaseModel):
    reason: Optional[str] = ""

class AdminApproveUserRequest(BaseModel):
    days:        Optional[int] = 3
    max_castles: Optional[int] = 10


# ══════════════════════════════════════════════════════════════════
# Firebase Admin SDK (فقط للتحقق من ID Token)
# ══════════════════════════════════════════════════════════════════

_fb_init_lock = threading.Lock()

def _ensure_firebase():
    """تهيئة آمنة لـ Firebase Admin SDK لاستخدامه في التحقق من التوكن فقط."""
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

_ensure_firebase()


# ══════════════════════════════════════════════════════════════════
# دوال تحديث الحالة والموارد في SQLite المحلية (فورية وبدون شبكة)
# ══════════════════════════════════════════════════════════════════

def update_castle_status_db(user_id: str, castle_id: str, state: str, message: str = "", conn_state: Optional[str] = None, next_run_time: Optional[str] = None):
    """تحديث حالة البوت واتصاله محلياً في SQLite فوراً وبسرعة فائقة."""
    try:
        effective_conn = conn_state
        if effective_conn is None:
            if state in ("idle", "error"):
                effective_conn = state
            elif state == "running":
                effective_conn = "connected"
            elif state == "waiting":
                effective_conn = "waiting"

        effective_email = _castle_emails.get(castle_id) or castle_id
        db.upsert_castle_conn_state(
            email=effective_email,
            conn_state=effective_conn or state,
            message=message,
            next_run_time=next_run_time,
            user_id=user_id,
            castle_id=castle_id
        )
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء تحديث حالة القلعة محلياً: {e}")


def sync_castle_resources_db(email: str, data: dict, user_id: Optional[str] = None, castle_id: Optional[str] = None):
    """حفظ موارد القلعة ومعلوماتها في SQLite المحلية فوراً."""
    try:
        db.upsert_castle_resources(
            email=email,
            resources=data.get("resources", {}),
            castle_info=data.get("castle_info", {}),
            user_id=user_id,
            castle_id=castle_id
        )
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء حفظ موارد القلعة محلياً: {e}")


def _tail_file(filepath: str, n_lines: int = 100) -> List[str]:
    """قراءة آخر N أسطر من الملف بكفاءة عالية بدون تحميل الملف كاملاً في الذاكرة."""
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
# Authentication & RBAC Dependencies
# ══════════════════════════════════════════════════════════════════

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)) -> Dict[str, Any]:
    """
    التحقق من هوية المستخدم عبر Firebase ID Token المشفر.
    ثم قراءة بيانات المستخدم وصلاحيته من SQLite المحلية.
    إذا كان المستخدم جديداً ومسجلاً عبر Firebase، يتم إنشاء سجله تلقائياً في SQLite.
    """
    require_auth = os.environ.get("REQUIRE_AUTH", "0") == "1"

    if not credentials or not credentials.credentials:
        if require_auth:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        return {"uid": "local_dev", "role": "admin", "email": "dev@local", "username": "Local Admin"}

    token = credentials.credentials
    try:
        _ensure_firebase()
        import firebase_admin
        from firebase_admin import auth as fb_auth

        if not firebase_admin._apps:
            if not require_auth:
                return {"uid": "local_dev", "role": "admin", "email": "dev@local", "username": "Local Admin"}
            raise HTTPException(status_code=500, detail="Firebase Admin SDK is not initialized")

        decoded = fb_auth.verify_id_token(token)
        uid = decoded.get("uid", "")
        email = decoded.get("email", "")

        # قراءة بيانات المستخدم من SQLite
        user_record = db.get_user(uid)
        if not user_record and uid and email:
            # إنشاء سجل مبدئي للمستخدم في SQLite إن لم يكن موجوداً
            db.create_or_update_user(
                uid=uid,
                email=email,
                username=decoded.get("name", email.split("@")[0]),
                role="admin" if email in ("ibraboths@gmail.com", "fahed.k140@gmail.com") else "user"
            )
            user_record = db.get_user(uid)

        if user_record:
            if user_record.get("is_banned"):
                raise HTTPException(status_code=403, detail=f"تم حظر حسابك: {user_record.get('banned_reason') or 'مخالفة الشروط'}")
            return user_record

        return {"uid": uid, "email": email, "role": "user"}

    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"🔒 Token verification failed: {e}")
        if not require_auth:
            return {"uid": "local_dev", "role": "admin", "email": "dev@local"}
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {e}")


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """التأكد من أن المستخدم يتمتع بصلاحية المشرف (Admin) من SQLite."""
    uid = user.get("uid", "")
    if uid == "local_dev" or user.get("role") == "admin":
        return user
    raise HTTPException(status_code=403, detail="هذا الإجراء يتطلب صلاحية المشرف (Admin required)")


# ══════════════════════════════════════════════════════════════════
# تشغيل البوت مباشرةً كـ Thread خفيف
# ══════════════════════════════════════════════════════════════════

def _bot_thread(req: StartBotRequest):
    castle_id = req.castle_id
    user_id   = req.user_id
    email     = req.email

    # 1. إعداد queue للـ logs وإنشاء stop_event فوراً
    log_q: "queue.Queue[str]" = queue.Queue(maxsize=500)
    stop_event = threading.Event()
    with _lock:
        _threads[castle_id]     = threading.current_thread()
        _log_qs[castle_id]      = log_q
        _stop_events[castle_id] = stop_event
        _castle_emails[castle_id] = email
        _castle_users[castle_id]  = user_id
        _reserved.discard(castle_id)

    log.info(f"🚀 [{email}] بدء تشغيل البوت (Thread Pool)...")
    update_castle_status_db(user_id, castle_id, "running", "البوت يعمل الآن...")

    # 2. الحصول على كلمة المرور من الطلب أو من قاعدة البيانات المحلية
    password = req.password
    if not password:
        try:
            password = db.get_castle_password(castle_id, user_id)
        except Exception as e:
            log.warning(f"⚠️ خطأ أثناء جلب كلمة المرور: {e}")

    # 3. فحص session_cache.json أولاً ثم تسجيل الدخول وحفظ الجلسة تلقائياً
    try:
        from core.session_manager import SessionManager
        sm = SessionManager()
        account = sm.get_or_login(
            email=email,
            password=password,
            user_id=user_id,
            castle_id=castle_id,
        )
        if not account:
            err_msg = f"الحساب {email} غير موجود في الكاش وتعذر تسجيل دخوله (تأكد من صحة البريد وكلمة المرور)"
            log.error(f"❌ [{email}] {err_msg}")
            log_q.put(f"[{datetime.now():%H:%M:%S}] ❌ {err_msg}")
            update_castle_status_db(user_id, castle_id, "error", err_msg, conn_state="error")
            return
        else:
            log.info(f"✅ [{email}] تم تأكيد الجلسة بنجاح.")
    except Exception as e:
        log.error(f"💥 [{email}] خطأ أثناء التحقق من الجلسة: {e}")
        log_q.put(f"[{datetime.now():%H:%M:%S}] 💥 خطأ الجلسة: {e}")
        update_castle_status_db(user_id, castle_id, "error", str(e), conn_state="error")
        return

    # 4. ملف log البوت (مسموح فقط لقلاع المستخدم shreher@gmail.com لتخفيف الحمل واستهلاك القرص)
    bot_log_path = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
    _MAX_LOG_LINES = 300

    import re as _re
    _log_file_handle = None
    _log_line_counter = [0]  # عداد الأسطر المكتوبة في هذه الدورة (mutable list for closure)

    if _is_log_file_allowed(user_id, email):
        # قص الملف الموجود إلى آخر 300 سطر عند بداية الدورة
        try:
            if os.path.exists(bot_log_path):
                with open(bot_log_path, "r", encoding="utf-8", errors="replace") as f:
                    existing_lines = f.readlines()
                if len(existing_lines) > _MAX_LOG_LINES:
                    with open(bot_log_path, "w", encoding="utf-8", errors="replace") as f:
                        f.writelines(existing_lines[-_MAX_LOG_LINES:])
        except Exception:
            pass

        try:
            _log_file_handle = open(bot_log_path, "a", encoding="utf-8", errors="replace")
            _log_file_handle.write(f"\n{'='*60}\n[{datetime.now():%Y-%m-%d %H:%M:%S}] دورة جديدة\n{'='*60}\n")
            _log_file_handle.flush()
        except Exception:
            pass
    else:
        # حذف أي ملف log قديم لهذا الحساب غير المصرح به لتوفير مساحة القرص وتخفيف الحمل فورياً
        try:
            if os.path.exists(bot_log_path):
                os.remove(bot_log_path)
        except Exception:
            pass

    def _trim_log_file():
        """يقص ملف اللوق إلى آخر 300 سطر عند تجاوزه الحد."""
        nonlocal _log_file_handle
        if not _log_file_handle:
            return
        try:
            _log_file_handle.close()
            with open(bot_log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if len(lines) > _MAX_LOG_LINES:
                with open(bot_log_path, "w", encoding="utf-8", errors="replace") as f:
                    f.writelines(lines[-_MAX_LOG_LINES:])
            _log_file_handle = open(bot_log_path, "a", encoding="utf-8", errors="replace")
        except Exception:
            try:
                _log_file_handle = open(bot_log_path, "a", encoding="utf-8", errors="replace")
            except Exception:
                pass

    def _log_callback(line: str):
        if _log_file_handle:
            print(f"[{email}] {line}", flush=True)
            try:
                _log_file_handle.write(line + "\n")
                _log_file_handle.flush()
                _log_line_counter[0] += 1
                # كل 100 سطر نقص الملف إلى آخر 300 سطر
                if _log_line_counter[0] >= 100:
                    _log_line_counter[0] = 0
                    _trim_log_file()
            except Exception:
                pass
        stamped = f"[{datetime.now():%H:%M:%S}] {line}"
        try:
            log_q.put_nowait(stamped)
        except queue.Full:
            pass

        if stop_event.is_set():
            return

        # ── تحليل أحداث البوت الموجهة لتحديث الحالة ──
        if "[FIREBASE_EVENT]" in line or "[BOT_EVENT]" in line:
            try:
                tag = "[FIREBASE_EVENT]" if "[FIREBASE_EVENT]" in line else "[BOT_EVENT]"
                parts = line.split(tag, 1)[1].strip()
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
                        update_castle_status_db(user_id, castle_id, bs, ev_msg or line, ev_state, next_run_time=ev_nr)
            except Exception as ex:
                log.debug(f"Bot event parse error: {ex}")

        # ── تحليل أحداث مزامنة الموارد ──
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
                    sync_castle_resources_db(
                        email,
                        {"resources": r_data, "castle_info": c_data} if c_data else {"resources": r_data},
                        user_id=user_id,
                        castle_id=castle_id,
                    )
            except Exception as ex:
                log.debug(f"Resource sync parse error: {ex}")

    # 5. فحص الاشتراك دورياً محلياً من SQLite بدون أي استعلام شبكة
    forced_stop_reason = ""

    def _subscription_guard():
        nonlocal forced_stop_reason
        check_counter = 0
        while not stop_event.wait(timeout=5):
            check_counter += 1
            if check_counter % 6 == 0:  # كل 30 ثانية
                valid, reason = db.check_user_subscription_db(user_id)
                if not valid:
                    forced_stop_reason = reason
                    log.warning(f"🛑 [{email}] انتهاء اشتراك أو حظر محلياً: {reason}")
                    stop_event.set()
                    break
            if check_counter % 12 == 0:  # كل 60 ثانية
                # التحقق إذا قام المستخدم بتعطيل القلعة
                c = db.get_castle_by_id(castle_id, user_id)
                if c and not c.get("is_active", True):
                    forced_stop_reason = "تم تعطيل القلعة"
                    stop_event.set()
                    break

    guard_t = threading.Thread(target=_subscription_guard, daemon=True, name=f"guard-{castle_id[:10]}")
    guard_t.start()

    # 6. تشغيل BotManager
    try:
        import sys, importlib
        for mod_name in ("tasks.march_manager", "bot_manager"):
            if mod_name in sys.modules:
                try:
                    importlib.reload(sys.modules[mod_name])
                except Exception:
                    pass

        # جلب أحدث إعدادات القلعة مباشرة من قاعدة البيانات المحلية SQLite
        castle_rec = db.get_castle_by_id(castle_id, user_id) or db.get_castle(email)
        initial_cfg = (castle_rec.get("config") if castle_rec and isinstance(castle_rec.get("config"), dict) else {}) or req.config or {}

        from bot_manager import BotManager
        manager = BotManager(
            email,
            initial_cfg,
            reconnect_wait_seconds=60,
            user_id=user_id,
            castle_id=castle_id,
            stop_event=stop_event,
            log_callback=_log_callback,
        )
        with _lock:
            _bot_managers[castle_id] = manager
        asyncio.run(manager.run_loop(loop_interval_minutes=req.loop_interval))

    except Exception as e:
        log.error(f"💥 [{email}] خطأ في البوت: {e}", exc_info=True)
        log_q.put(f"[{datetime.now():%H:%M:%S}] 💥 خطأ: {e}")
        update_castle_status_db(user_id, castle_id, "error", str(e), conn_state="error")
    finally:
        stop_event.set()
        if _log_file_handle:
            try: _log_file_handle.close()
            except Exception: pass

        was_user_stopped = castle_id in _user_stopped
        with _lock:
            _threads.pop(castle_id, None)
            _stop_events.pop(castle_id, None)
            _bot_managers.pop(castle_id, None)
            _log_qs.pop(castle_id, None)
            _conn_states.pop(castle_id, None)
            _castle_users.pop(castle_id, None)
            _user_stopped.discard(castle_id)

    # 7. تحديث الحالة النهائية في SQLite
    if forced_stop_reason:
        log_q.put(f"[{datetime.now():%H:%M:%S}] 🛑 إيقاف إجباري: {forced_stop_reason}")
        log.info(f"🛑 [{email}] إيقاف إجباري: {forced_stop_reason}")
        update_castle_status_db(user_id, castle_id, "idle", f"متوقف إجبارياً: {forced_stop_reason}", conn_state="idle")
    elif was_user_stopped:
        log_q.put(f"[{datetime.now():%H:%M:%S}] ⏹️ تم إيقاف البوت بواسطة المستخدم")
        log.info(f"⏹️ [{email}] إيقاف يدوي")
        update_castle_status_db(user_id, castle_id, "idle", "تم إيقاف البوت بواسطة المستخدم", conn_state="idle")
    else:
        log.info(f"💤 [{email}] اكتمل البوت بشكل طبيعي")
        update_castle_status_db(user_id, castle_id, "idle", "اكتمل البوت", conn_state="idle")


# ══════════════════════════════════════════════════════════════════
# API Endpoints
# ══════════════════════════════════════════════════════════════════

@app.get("/")
@app.get("/api/health")
def root():
    return {"status": "online", "service": "Empire Bot API (SQLite Powered)", "time": datetime.now().isoformat()}


# ── 👤 User Endpoints ─────────────────────────────────────────────

@app.get("/api/user/profile")
def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """جلب الملف الشخصي للمستخدم الحالي من SQLite."""
    uid = current_user.get("uid", "")
    profile = db.get_user(uid)
    if not profile:
        profile = dict(current_user)
    if "subscription" not in profile or not isinstance(profile["subscription"], dict):
        profile["subscription"] = {
            "plan_id": profile.get("plan_id", "free"),
            "plan_name": profile.get("plan_name", "مجاني"),
            "status": profile.get("subscription_status", "active"),
            "started_at": profile.get("subscription_started_at", ""),
            "expires_at": profile.get("subscription_expires_at", ""),
            "max_castles_allowed": profile.get("max_castles_allowed", 1),
            "current_castles_count": profile.get("current_castles_count", 0),
            "pending_castles_count": profile.get("pending_castles_count", 0),
        }
    valid, reason = db.check_user_subscription_db(uid)
    profile["subscription_valid"] = valid
    profile["subscription_reason"] = reason
    return {"user": profile}


@app.post("/api/user/register")
def register_user(req: UserRegisterRequest):
    """تسجيل أو مزامنة مستخدم جديد في SQLite عند تسجيل حسابه في Firebase."""
    ok = db.create_or_update_user(
        uid=req.uid,
        email=req.email,
        username=req.username or req.email.split("@")[0],
        phone=req.phone or ""
    )
    if not ok:
        raise HTTPException(status_code=500, detail="تعذر حفظ بيانات المستخدم في قاعدة البيانات")
    user = db.get_user(req.uid)
    return {"status": "success", "user": user}


@app.put("/api/user/profile")
def update_profile(req: UserProfileUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تحديث الاسم أو الهاتف للمستخدم الحالي."""
    uid = current_user.get("uid", "")
    ok = db.update_user_profile(uid, username=req.username, phone=req.phone)
    if not ok:
        raise HTTPException(status_code=500, detail="تعذر تحديث الملف الشخصي")
    return {"status": "success", "user": db.get_user(uid)}


@app.get("/api/user/subscription")
def get_user_subscription(current_user: Dict[str, Any] = Depends(get_current_user)):
    """معلومات اشتراك المستخدم وحدود القلاع من SQLite."""
    uid = current_user.get("uid", "")
    user = db.get_user(uid) or current_user
    valid, reason = db.check_user_subscription_db(uid)
    return {
        "valid": valid,
        "reason": reason,
        "plan_id": user.get("plan_id", "free"),
        "plan_name": user.get("plan_name", "مجاني"),
        "status": user.get("subscription_status", "active"),
        "expires_at": user.get("subscription_expires_at"),
        "max_castles_allowed": user.get("max_castles_allowed", 1),
        "current_castles_count": user.get("current_castles_count", 0),
        "pending_castles_count": user.get("pending_castles_count", 0),
    }


# ── 🏰 Castle Endpoints ───────────────────────────────────────────

@app.get("/api/castles")
def list_castles(
    user_id: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """جلب قلاع المستخدم الحالي أو مستخدم محدد (للمشرف) من SQLite مع حالات التشغيل الحقيقية."""
    caller_uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or caller_uid == "local_dev")

    if is_admin and user_id and user_id.strip():
        target_uid = user_id.strip()
        castles = db.get_user_castles(target_uid)
    elif is_admin and not caller_uid:
        castles = db.get_all_castles()
    else:
        target_uid = caller_uid
        castles = db.get_user_castles(target_uid)

    # دمج الحالة الحقيقية للـ thread
    for c in castles:
        cid = c.get("castle_id", "")
        real_st = _get_real_status(cid)
        c["state"] = real_st
        c["conn_state"] = real_st
        if real_st != "idle" and not c.get("conn_message"):
            c["conn_message"] = "البوت يعمل الآن..."
        elif real_st == "idle" and c.get("conn_message") in ("running", "connected", "waiting", "reconnecting"):
            c["conn_message"] = "جاهز للتشغيل"

    return {"castles": castles}


@app.get("/api/castles/{castle_id}")
def get_castle_details(castle_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تفاصيل قلعة محددة من SQLite."""
    uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or uid == "local_dev")

    c = db.get_castle_by_id(castle_id, None if is_admin else uid)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")

    real_st = _get_real_status(castle_id)
    c["state"] = real_st
    c["conn_state"] = real_st
    if real_st == "idle" and c.get("conn_message") in ("running", "connected", "waiting", "reconnecting"):
        c["conn_message"] = "جاهز للتشغيل"

    return {"castle": c}


@app.post("/api/castles")
def add_castle(req: CastleCreateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """إضافة قلعة جديدة في SQLite مع التحقق من الحد المسموح للاشتراك."""
    uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or uid == "local_dev")

    # 1. التحقق من حد القلاع المسموح وحالة الموافقة
    is_within_quota = True
    if not is_admin:
        u = db.get_user(uid)
        if u:
            st = (u.get("subscription") or {}).get("status") or u.get("subscription_status")
            if st == "pending_approval":
                raise HTTPException(status_code=403, detail="الحساب بانتظار موافقة الإدارة أولاً لتفعيل باقة الـ 10 حسابات")
            active_cnt, _ = db.count_user_castles(uid)
            max_allowed = (u.get("subscription") or {}).get("max_castles_allowed") or u.get("max_castles_allowed", 0)
            if active_cnt >= max_allowed:
                is_within_quota = False

    castle_id = req.castle_id or f"c_{uuid.uuid4().hex[:12]}"
    clean_email = req.email.strip().lower()

    # التحقق من عدم تكرار البريد الإلكتروني للقلعة لأي مستخدم
    if db.castle_exists_by_email(clean_email):
        raise HTTPException(
            status_code=400,
            detail="البريد الإلكتروني لهذه القلعة مسجل بالفعل في النظام، لا يمكن إضافة نفس القلعة مرتين"
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    castle_data = {
        "castle_id": castle_id,
        "user_id": uid,
        "email": clean_email,
        "password": req.password or "",
        "castle_name": req.castle_name or clean_email.split("@")[0],
        "config": req.config or {},
        "is_active": 1 if is_within_quota else 0,
        "state": "idle" if is_within_quota else "pending",
        "conn_state": "idle" if is_within_quota else "pending",
        "conn_message": "جاهز للتشغيل" if is_within_quota else "بانتظار موافقة الإدارة (تم تجاوز الحد المسموح)",
        "created_at": now_iso,
        "last_updated": now_iso,
    }

    ok = db.save_castle(castle_data)
    if not ok:
        raise HTTPException(status_code=500, detail="تعذر حفظ القلعة في قاعدة البيانات")

    return {"status": "success", "castle": db.get_castle_by_id(castle_id, uid)}


@app.put("/api/castles/{castle_id}")
def update_castle(castle_id: str, req: CastleUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تحديث إعدادات أو اسم القلعة في SQLite."""
    uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or uid == "local_dev")

    c = db.get_castle_by_id(castle_id, None if is_admin else uid)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")

    if req.config is not None:
        db.update_castle_config(castle_id, req.config, None if is_admin else uid)

    if req.castle_name is not None:
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE castle_states SET castle_name = ?, last_updated = ? WHERE castle_id = ?",
                    (req.castle_name, datetime.now(timezone.utc).isoformat(), castle_id)
                )
                conn.commit()
        except Exception:
            pass

    return {"status": "success", "castle": db.get_castle_by_id(castle_id, None if is_admin else uid)}


@app.put("/api/castles/{castle_id}/credentials")
def update_castle_creds(castle_id: str, req: CastleCredentialsUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تحديث البريد وكلمة المرور للقلعة في SQLite."""
    uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or uid == "local_dev")

    c = db.get_castle_by_id(castle_id, None if is_admin else uid)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")

    clean_email = req.email.strip().lower()
    if db.castle_exists_by_email(clean_email, exclude_castle_id=castle_id):
        raise HTTPException(
            status_code=400,
            detail="البريد الإلكتروني لهذه القلعة مسجل بالفعل لقلعة أخرى"
        )

    ok = db.update_castle_credentials(castle_id, clean_email, req.password or "", None if is_admin else uid)
    if not ok:
        raise HTTPException(status_code=500, detail="تعذر تحديث بيانات تسجيل الدخول للقلعة")

    return {"status": "success", "message": "تم تحديث بيانات القلعة بنجاح"}


@app.post("/api/castles/{castle_id}/toggle-active")
def toggle_castle_active_endpoint(castle_id: str, req: CastleToggleActiveRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تفعيل أو تعطيل القلعة في SQLite."""
    uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or uid == "local_dev")

    ok = db.toggle_castle_active(castle_id, req.is_active, None if is_admin else uid)
    if not ok:
        raise HTTPException(status_code=404, detail="تعذر تغيير حالة تفعيل القلعة")

    # إذا تم تعطيل القلعة وهي قيد التشغيل، أوقفها فوراً
    if not req.is_active and _is_running(castle_id):
        with _lock:
            ev = _stop_events.get(castle_id)
            mgr = _bot_managers.get(castle_id)
            if mgr:
                try: mgr.stop()
                except Exception: pass
            if ev:
                ev.set()

    return {"status": "success", "is_active": req.is_active}


@app.delete("/api/castles/{castle_id}")
def delete_castle_endpoint(castle_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """حذف القلعة نهائياً من SQLite."""
    uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or uid == "local_dev")

    # إيقاف البوت إن كان شغالاً
    if _is_running(castle_id):
        with _lock:
            ev = _stop_events.get(castle_id)
            mgr = _bot_managers.get(castle_id)
            if mgr:
                try: mgr.stop()
                except Exception: pass
            if ev:
                ev.set()

    ok = db.delete_castle_by_id(castle_id, uid) if not is_admin else db.delete_castle(castle_id)
    if not ok:
        raise HTTPException(status_code=404, detail="تعذر حذف القلعة")

    return {"status": "success", "message": "تم حذف القلعة بنجاح"}


# ── 👑 Admin Endpoints ────────────────────────────────────────────

@app.get("/api/admin/stats")
def get_admin_dashboard_stats(admin: Dict[str, Any] = Depends(require_admin)):
    """إحصائيات عامة للمشرف من SQLite."""
    stats = db.get_admin_stats()
    with _lock:
        active_cids = {cid for cid, t in _threads.items() if t.is_alive()}
        for t in threading.enumerate():
            if t.name.startswith("bot-") and t.is_alive():
                prefix = t.name[4:]
                for cm in db.find_castles_by_id_prefix(prefix):
                    if cm.get("castle_id"):
                        active_cids.add(cm["castle_id"])
        stats["activeBots"] = len(active_cids)
    return stats


@app.get("/api/admin/users")
def get_admin_users(admin: Dict[str, Any] = Depends(require_admin)):
    """جلب جميع المستخدمين وقلاعهم من SQLite."""
    users = db.get_all_users_with_castles()
    return {"users": users}


@app.post("/api/admin/user/{uid}/subscription")
def update_user_sub(uid: str, req: AdminSubscriptionUpdateRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """تحديث باقة واشتراك المستخدم في SQLite."""
    ok = db.update_user_subscription(
        uid=uid,
        plan_id=req.plan_id,
        plan_name=req.plan_name,
        expires_at=req.expires_at,
        max_castles=req.max_castles_allowed,
        status=req.subscription_status
    )
    if not ok:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    return {"status": "success", "user": db.get_user(uid)}


@app.post("/api/admin/user/{uid}/approve")
def approve_user_endpoint(
    uid: str,
    req: Optional[AdminApproveUserRequest] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """الموافقة على المستخدم وتفعيل باقة الـ 10 حسابات لمدة 3 أيام من المشرف."""
    days = req.days if (req and req.days is not None) else 3
    max_c = req.max_castles if (req and req.max_castles is not None) else 10
    ok = db.approve_user_trial(uid=uid, days=days, max_castles=max_c)
    if not ok:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    return {
        "status": "success",
        "message": f"تمت الموافقة بنجاح وتفعيل باقة {max_c} حسابات لمدة {days} أيام",
        "user": db.get_user(uid)
    }


@app.post("/api/admin/users/approve-all")
def approve_all_users_endpoint(
    req: Optional[AdminApproveUserRequest] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """الموافقة على جميع المستخدمين المعلقين وتفعيل باقة التجربة لهم."""
    days = req.days if (req and req.days is not None) else 3
    max_c = req.max_castles if (req and req.max_castles is not None) else 10
    count = db.approve_all_pending_users(days=days, max_castles=max_c)
    return {
        "status": "success",
        "message": f"تمت الموافقة على {count} مستخدم بنجاح وتفعيل الباقة التجريبية",
        "approved_count": count
    }


@app.post("/api/admin/user/{uid}/ban")
def ban_user_endpoint(uid: str, req: AdminBanUserRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """حظر أو إلغاء حظر المستخدم في SQLite."""
    ok = db.ban_user(uid, req.is_banned, req.reason or "")
    if not ok:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    # إذا تم الحظر، إيقاف جميع بوتات المستخدم فوراً
    if req.is_banned:
        with _lock:
            targets = [cid for cid, u in _castle_users.items() if u == uid]
            for cid in targets:
                _user_stopped.add(cid)
                ev = _stop_events.get(cid)
                mgr = _bot_managers.get(cid)
                if mgr:
                    try: mgr.stop()
                    except Exception: pass
                if ev:
                    ev.set()

    return {"status": "success", "user": db.get_user(uid)}


@app.delete("/api/admin/user/{uid}")
def delete_user_endpoint(uid: str, admin: Dict[str, Any] = Depends(require_admin)):
    """حذف مستخدم وجميع قلاعه من SQLite."""
    # إيقاف جميع بوتاته الجارية أولاً
    with _lock:
        targets = [cid for cid, u in _castle_users.items() if u == uid]
        for cid in targets:
            _user_stopped.add(cid)
            ev = _stop_events.get(cid)
            mgr = _bot_managers.get(cid)
            if mgr:
                try: mgr.stop()
                except Exception: pass
            if ev:
                ev.set()

    ok = db.delete_user(uid)
    if not ok:
        raise HTTPException(status_code=404, detail="تعذر حذف المستخدم")
    return {"status": "success", "message": "تم حذف المستخدم وجميع قلاعه بنجاح"}


@app.post("/api/admin/castle/{castle_id}/approve")
def approve_castle_endpoint(castle_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """قبول وتفعيل قلعة معلقة في SQLite."""
    ok = db.approve_castle(castle_id)
    if not ok:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")
    return {"status": "success", "message": "تمت الموافقة على القلعة"}


@app.post("/api/admin/castle/{castle_id}/reject")
def reject_castle_endpoint(castle_id: str, req: AdminCastleActionRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """رفض قلعة في SQLite."""
    ok = db.reject_castle(castle_id, req.reason or "تم رفض القلعة من المشرف")
    if not ok:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")
    return {"status": "success", "message": "تم رفض القلعة"}


# ── 🤖 Bot Control Endpoints ──────────────────────────────────────

def _start_bot_internal(req: StartBotRequest) -> bool:
    """تشغيل داخلي للبوت يدعم الاستدعاء المباشر والاستئناف التلقائي (Auto-Resume)."""
    with _lock:
        _user_stopped.discard(req.castle_id)
        if _is_running(req.castle_id):
            return False
        _reserved.add(req.castle_id)

    t = threading.Thread(target=_bot_thread, args=(req,), daemon=True, name=f"bot-{req.castle_id[:10]}")
    with _lock:
        _threads[req.castle_id] = t
    t.start()
    return True


@app.post("/api/internal/save-running-state")
def save_running_state_endpoint():
    """حفظ قائمة جميع البوتات النشطة حالياً في auto_resume.json قبل عمل ريستارت للسيرفر."""
    active_cids = set()
    with _lock:
        for cid, t in _threads.items():
            if t.is_alive() and cid not in _user_stopped:
                active_cids.add(cid)
        for cid in list(_castle_users.keys()):
            if cid not in active_cids and cid not in _user_stopped:
                t = _threads.get(cid)
                if t and t.is_alive():
                    active_cids.add(cid)

    # فحص أي threads نشطة تبدأ بـ bot- في بايثون
    for t in threading.enumerate():
        if t.name.startswith("bot-") and t.is_alive():
            prefix = t.name[4:]
            castles_match = db.find_castles_by_id_prefix(prefix)
            for cm in castles_match:
                cid = cm.get("castle_id")
                if cid and cid not in _user_stopped:
                    active_cids.add(cid)

    saved_list = []
    for cid in active_cids:
        c = db.get_castle_by_id(cid)
        if c:
            saved_list.append({
                "castle_id": cid,
                "user_id": c.get("user_id", ""),
                "email": c.get("email", ""),
            })

    auto_resume_file = os.path.join(_ROOT, "auto_resume.json")
    with open(auto_resume_file, "w", encoding="utf-8") as f:
        json.dump(saved_list, f, ensure_ascii=False, indent=2)

    log.info(f"💾 [Auto-Resume Prep] تم حفظ حالة {len(saved_list)} بوت نشط لإعادة استئنافهم تلقائياً بعد الريستارت.")
    return {"status": "success", "count": len(saved_list), "castles": [x["castle_id"] for x in saved_list]}


@app.get("/api/internal/debug-state")
def debug_state():
    with _lock:
        return {
            "threads_len": len(_threads),
            "threads_keys": list(_threads.keys()),
            "threads_alive": {k: v.is_alive() for k, v in _threads.items()},
            "castle_users": _castle_users,
            "user_stopped": list(_user_stopped),
            "reserved": list(_reserved),
            "all_active_python_threads": [t.name for t in threading.enumerate()]
        }


@app.post("/api/bot/start")
def start_bot(req: StartBotRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تشغيل بوت لقلعة معينة مع التحقق من صلاحية الاشتراك محلياً في SQLite."""
    caller_uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or caller_uid == "local_dev")

    if not is_admin and caller_uid != req.user_id:
        raise HTTPException(status_code=403, detail="غير مصرح بتشغيل قلاع مستخدم آخر")

    # 1. التحقق من صلاحية الاشتراك وحظر الحساب محلياً في SQLite
    valid, reason = db.check_user_subscription_db(req.user_id)
    if not valid:
        log.warning(f"🛑 [{req.email}] تم رفض بدء التشغيل محلياً: {reason}")
        update_castle_status_db(req.user_id, req.castle_id, "idle", f"متوقف: {reason}")
        raise HTTPException(status_code=403, detail=f"لا يمكن تشغيل البوت: {reason}")

    started = _start_bot_internal(req)
    if not started:
        return {"status": "already_running", "castle_id": req.castle_id, "email": req.email}

    msg = f"▶️  [{req.email}] طلب تشغيل قُبل من {caller_uid} (castle_id={req.castle_id[:10]})"
    log.info(msg)
    return {"status": "starting", "castle_id": req.castle_id, "email": req.email}


@app.post("/api/bot/stop/{castle_id}")
def stop_bot(castle_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """إيقاف بوت قلعة معينة وتصفير حالتها في SQLite فوراً."""
    caller_uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or caller_uid == "local_dev")

    with _lock:
        owner_uid = _castle_users.get(castle_id)
        matched_cid = castle_id
        if castle_id not in _castle_users and castle_id not in _stop_events:
            for cid, em in _castle_emails.items():
                if em == castle_id or cid == castle_id:
                    matched_cid = cid
                    owner_uid = _castle_users.get(cid)
                    break

    if not is_admin and owner_uid and owner_uid != caller_uid:
        raise HTTPException(status_code=403, detail="غير مصرح بإيقاف قلاع مستخدم آخر")

    with _lock:
        ev = _stop_events.get(matched_cid)
        mgr = _bot_managers.get(matched_cid)
        _user_stopped.add(matched_cid)

    # 1. إيقاف مدير البوت فوراً وقطع مقبس الاتصال لحظياً
    if mgr:
        try:
            mgr.stop()
        except Exception as ex:
            log.debug(f"mgr.stop error: {ex}")

    # 2. تفعيل إشارة الإيقاف
    if ev:
        ev.set()

    # تصفير حالة القلعة دائماً في SQLite لضمان عدم بقائها عالقة
    try:
        email = _castle_emails.get(matched_cid) or matched_cid
        update_castle_status_db(caller_uid, matched_cid, "idle", "تم إيقاف البوت بواسطة المستخدم", conn_state="idle")
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء تصفير حالة القلعة محلياً: {e}")

    log.info(f"⏹️  تم إيقاف القلعة {matched_cid[:16]} بواسطة {caller_uid}")
    return {"status": "stopped", "castle_id": matched_cid}


@app.post("/api/bot/stop-user/{user_id}")
def stop_user_bots(user_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """إيقاف جميع بوتات المستخدم فوراً (خاص بالمشرف)."""
    stopped = []
    with _lock:
        targets = [cid for cid, uid in _castle_users.items() if uid == user_id]
        for cid in targets:
            _user_stopped.add(cid)
            ev = _stop_events.get(cid)
            mgr = _bot_managers.get(cid)
            if mgr:
                try:
                    mgr.stop()
                except Exception:
                    pass
            if ev:
                ev.set()
            stopped.append(cid)
            try:
                update_castle_status_db(user_id, cid, "idle", "تم إيقاف البوت بواسطة المشرف", conn_state="idle")
            except Exception:
                pass
    log.info(f"🛑 [Force Stop] تم إيقاف {len(stopped)} بوت للمستخدم {user_id}")
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
    return {"castles": db.get_all_castles(user_id=user_id)}


@app.get("/api/local/castles/{identifier}")
def get_local_castle(identifier: str):
    """استرجاع بيانات وحالة قلعة معينة من قاعدة بيانات SQLite المحلية بلمح البصر."""
    c = db.get_castle(identifier)
    if not c:
        raise HTTPException(status_code=404, detail="Castle not found in local database")
    return {"castle": c}


@app.get("/api/castle-data/{email}")
async def get_castle_data(email: str, user_id: Optional[str] = None, castle_id: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    جلب بيانات القلعة والموارد الحية بالاتصال بسيرفر اللعبة ومزامنتها مع SQLite المحلية.
    """
    try:
        from core.session_manager import SessionManager
        from game_client import GameConnection

        sm = SessionManager()
        account = sm.get_or_login(email=email, user_id=user_id, castle_id=castle_id)
        if not account:
            raise HTTPException(status_code=404, detail=f"تعذر العثور على جلسة الحساب {email} أو تسجيل دخوله")

        conn = GameConnection(account)
        ok = await asyncio.wait_for(conn.connect(), timeout=15)
        if not ok:
            raise HTTPException(status_code=503, detail="تعذر الاتصال بسيرفر اللعبة")

        for _ in range(15):
            await asyncio.sleep(0.3)
            if len(conn.init_data) > 0:
                break

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

        # مزامنة فورية في SQLite المحلية
        sync_castle_resources_db(email, {"resources": res_data, "castle_info": cinfo_data}, user_id=user_id, castle_id=castle_id)

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
    """قراءة آخر N سطر من سجل الأخطاء bot_errors.log (خاص بالمشرف)."""
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
    """قراءة آخر N سطر من ملف log الخاص بالقلعة محلياً من القرص."""
    caller_uid = current_user.get("uid", "")
    is_admin = (current_user.get("role") == "admin" or caller_uid == "local_dev")

    with _lock:
        owner_uid = _castle_users.get(castle_id)
    if not is_admin and owner_uid and owner_uid != caller_uid:
        raise HTTPException(status_code=403, detail="غير مصرح بقراءة سجلات قلعة مستخدم آخر")

    email = _castle_emails.get(castle_id)
    if not email:
        try:
            with db.get_connection() as conn:
                cur = conn.execute("SELECT email FROM castle_states WHERE castle_id = ? LIMIT 1", (castle_id,))
                row = cur.fetchone()
                if row:
                    email = row["email"]
        except Exception:
            pass

    log_path = None
    if email:
        p = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
        if os.path.exists(p):
            log_path = p

    if not log_path or not os.path.exists(log_path):
        return {"logs": [], "count": 0, "message": "حفظ السجلات في ملفات معطل لهذا الحساب لتخفيف الحمل"}

    last_lines = _tail_file(log_path, n_lines=lines)
    return {
        "logs": last_lines,
        "count": len(last_lines),
        "showing": len(last_lines),
        "file": os.path.basename(log_path),
    }


# ── WebSockets ────────────────────────────────────────────────────

@app.websocket("/ws/logs/{castle_id}")
async def ws_logs(websocket: WebSocket, castle_id: str):
    """WebSocket للـ logs المباشرة لبوت قلعة معينة."""
    await websocket.accept()
    log.info(f"📡 WebSocket logs connected: {castle_id[:16]}")

    email = _castle_emails.get(castle_id)
    if not email:
        try:
            with db.get_connection() as conn:
                cur = conn.execute("SELECT email FROM castle_states WHERE castle_id = ? LIMIT 1", (castle_id,))
                row = cur.fetchone()
                if row:
                    email = row["email"]
        except Exception:
            pass

    log_path = None
    if email:
        p = os.path.join(_ROOT, f"bot_{email.replace('@','_').replace('.','_')}.log")
        if os.path.exists(p):
            log_path = p

    if log_path and os.path.exists(log_path):
        recent = _tail_file(log_path, n_lines=35)
        for r in recent:
            try:
                await websocket.send_text(r)
            except Exception:
                break

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
    """WebSocket لمراقبة حالة البوت الحقيقية في الوقت الفعلي."""
    await websocket.accept()

    last_status = _get_real_status(castle_id)
    await websocket.send_text(last_status)

    try:
        while True:
            await asyncio.sleep(0.3)
            current = _get_real_status(castle_id)
            if current != last_status:
                last_status = current
                await websocket.send_text(current)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# الحارس الأمني والدوري لخادم API (Watchdog)
# ══════════════════════════════════════════════════════════════════

def _watchdog_loop():
    """حارس دوري يفحص كل 45 ثانية جميع العمليات الجارية للتأكد من عدم وجود بوتات لحسابات محظورة أو منتهية."""
    while True:
        time.sleep(45)
        try:
            with _lock:
                active_items = list(_castle_users.items())
            
            for cid, uid in active_items:
                try:
                    valid, reason = db.check_user_subscription_db(uid)
                    if not valid:
                        log.warning(f"🛡️ [Watchdog] كشف قلعة غير مصرح بها {cid[:10]} (المستخدم: {uid}): {reason}")
                        with _lock:
                            _user_stopped.add(cid)
                            ev = _stop_events.get(cid)
                            mgr = _bot_managers.get(cid)
                            if mgr:
                                try: mgr.stop()
                                except Exception: pass
                            if ev:
                                ev.set()
                        update_castle_status_db(uid, cid, "idle", f"متوقف إجبارياً: {reason}", conn_state="idle")
                except Exception:
                    pass
        except Exception as ex:
            log.debug(f"Watchdog exception: {ex}")

def _handle_auto_resume():
    """استئناف تشغيل البوتات التي كانت شغالة قبل إعادة تشغيل السيرفر تلقائياً وبدون أي وميض أو تأخير في الواجهة."""
    def _bg_resume():
        time.sleep(1)
        auto_resume_file = os.path.join(_ROOT, "auto_resume.json")
        to_resume: List[Dict[str, Any]] = []
        if os.path.exists(auto_resume_file):
            try:
                with open(auto_resume_file, "r", encoding="utf-8") as f:
                    to_resume = json.load(f)
                os.remove(auto_resume_file)
            except Exception as e:
                log.warning(f"⚠️ خطأ أثناء قراءة auto_resume.json: {e}")

        resume_cids = {x.get("castle_id") for x in to_resume if x.get("castle_id")}

        # إعادة ضبط الحالات العالقة في القاعدة مع استثناء القلاع التي سيتم استئنافها فوراً
        cnt = db.reset_stuck_castles_db(exclude_castle_ids=list(resume_cids) if resume_cids else None)
        if cnt > 0:
            log.info(f"🧹 [Startup Reset] تم تنظيف {cnt} قلعة عالقة من التشغيل السابق.")

        # استئناف البوتات التي كانت نشطة تلقائياً وبسلاسة
        if to_resume and isinstance(to_resume, list):
            log.info(f"🔄 [Auto-Resume] جاري استئناف تشغيل {len(to_resume)} بوت تلقائياً وبسلاسة...")
            for item in to_resume:
                cid = item.get("castle_id", "")
                uid = item.get("user_id", "")
                if not cid or not uid:
                    continue
                try:
                    valid, reason = db.check_user_subscription_db(uid)
                    if not valid:
                        log.warning(f"⏩ [Auto-Resume] تخطي القلعة {cid[:8]} لانتهاء اشتراك المستخدم: {reason}")
                        continue
                    c = db.get_castle_by_id(cid, uid)
                    if not c or not c.get("is_active", 1):
                        continue

                    # وضع حالة التشغيل فوراً في الذاكرة والقاعدة حتى تظهر في الواجهة كـ running فوراً دون أي ثانية تأخير
                    with _lock:
                        _conn_states[cid] = "connected"
                        _castle_users[cid] = uid
                        _castle_emails[cid] = c.get("email", item.get("email", ""))
                    update_castle_status_db(uid, cid, "running", "جاري الاتصال واستئناف العمل...", conn_state="connected")

                    req = StartBotRequest(
                        castle_id=cid,
                        user_id=uid,
                        email=c.get("email", item.get("email", "")),
                        config=c.get("config", {}),
                        loop_interval=55
                    )
                    _start_bot_internal(req)
                    log.info(f"✅ [Auto-Resume] استؤنف تشغيل البوت تلقائياً: {c.get('email')} ({cid[:8]})")
                    time.sleep(1.0)  # فاصل زمني لتوزيع الحمل بسلاسة
                except Exception as ex:
                    log.warning(f"⚠️ فشل استئناف البوت للقلعة {cid}: {ex}")

    threading.Thread(target=_bg_resume, daemon=True, name="auto-resume").start()


@app.on_event("startup")
def on_startup():
    """تهيئة خدمات السيرفر واستئناف البوتات عند إقلاع تطبيق FastAPI."""
    log.info("🚀 [Startup Event] بدء حارس العمليات واستئناف البوتات النشطة...")
    cleanup_unauthorized_bot_logs()
    threading.Thread(target=_watchdog_loop, daemon=True, name="bot-watchdog").start()
    _handle_auto_resume()


# ══════════════════════════════════════════════════════════════════
# نقطة الدخول
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Empire Bot API Server (SQLite Powered)")
    parser.add_argument("--host",   default="0.0.0.0",  help="عنوان الاستماع [0.0.0.0]")
    parser.add_argument("--port",   type=int, default=8000, help="المنفذ [8000]")
    parser.add_argument("--reload", action="store_true", help="إعادة تحميل تلقائي عند التعديل (تطوير)")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("🚀 Empire Bot API Server (SQLite Powered - Zero Firestore)")
    print(f"   المنفذ الداخلي (Nginx Reverse Proxy) : http://{args.host}:{args.port}")
    print("   الرابط العام المشفر (Production)     : https://ibraabot.online/api")
    print(f"   الوقت                                : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("═" * 60 + "\n")

    if args.reload:
        uvicorn.run(
            "api_server:app",
            host=args.host,
            port=args.port,
            reload=True,
            log_level="info",
        )
    else:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=False,
            log_level="info",
        )


if __name__ == "__main__":
    main()
