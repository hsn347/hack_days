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

import os, sys, json, time, logging, argparse, threading, asyncio, queue, signal, uuid, re, random, copy
from datetime import datetime, timezone, timedelta
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
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Security, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

# ── Database imports (SQLite local layer) ─────────────────────────
import core.database as db
from core.tenants import (
    get_all_merchants,
    get_tenant_by_domain,
    get_tenant_by_admin_email,
    is_merchant_admin,
    is_super_admin,
    clean_domain,
    is_user_allowed_for_tenant_domain,
)

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api_server")
log.setLevel(logging.INFO)

# ── مسار مجلد السجلات (Logs Directory) ────────────────────────────
_LOGS_DIR = os.path.join(_ROOT, "logs")
os.makedirs(_LOGS_DIR, exist_ok=True)


def _get_bot_log_path(email: str) -> str:
    """الحصول على مسار ملف سجل البوت مع دعم التوافق العكسي."""
    safe_name = f"bot_{email.replace('@', '_').replace('.', '_')}.log"
    new_path = os.path.join(_LOGS_DIR, safe_name)
    if os.path.exists(new_path):
        return new_path
    legacy_path = os.path.join(_ROOT, safe_name)
    if os.path.exists(legacy_path):
        return legacy_path
    return new_path


# ══════════════════════════════════════════════════════════════════
# FastAPI App & Secure CORS
# ══════════════════════════════════════════════════════════════════

# تعطيل واجهة التوثيق /docs و /redoc و /openapi.json أمنياً في الإنتاج لمنع كشف مسارات الخادم
# يمكن تفعيلها مؤقتاً عند الحاجة فقط للتطوير المحلي عبر تعيين المتغير: ENABLE_DOCS=true
_enable_docs = os.environ.get("ENABLE_DOCS", "false").lower() in ("true", "1", "yes")

app = FastAPI(
    title="Empire Bot API",
    version="2.0.0",
    docs_url="/docs" if _enable_docs else None,
    redoc_url="/redoc" if _enable_docs else None,
    openapi_url="/openapi.json" if _enable_docs else None,
)

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

def _safe_log_put(q: Optional["queue.Queue[str]"], msg: str) -> None:
    """إرسال آمن لرسالة اللوق في الـ queue بدون أي تجميد للـ Thread (Non-blocking drop-oldest)."""
    if q is None:
        return
    try:
        q.put_nowait(msg)
    except queue.Full:
        try:
            q.get_nowait()
        except Exception:
            pass
        try:
            q.put_nowait(msg)
        except Exception:
            pass
    except Exception:
        pass


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
_deleted_castles: Set[str]                = set() # castle_ids المحذوفة لمنع الخيوط من إعادة حفظها في SQLite
_stalled_threads: Dict[str, Dict[str, Any]] = {} # castle_id → معلومات الخيوط المتعطلة للتشخيص
_user_status_cache: Dict[str, Dict[str, str]] = {} # user_id → {castle_id: status}
_user_status_versions: Dict[str, int] = {}         # user_id → version counter


def _notify_user_status_change(user_id: Optional[str] = None, castle_id: Optional[str] = None):
    """إشعار فوري بتغير حالة القلعة لتحديث كاش الذاكرة دون استنزاف SQLite."""
    with _lock:
        target_uid = user_id
        if not target_uid and castle_id:
            target_uid = _castle_users.get(castle_id)
        if target_uid:
            _user_status_versions[target_uid] = _user_status_versions.get(target_uid, 0) + 1

# وضع النشر (Deploy Mode) — يمنع تشغيل أي بوت جديد أثناء تحديث السيرفر
_deploy_mode: bool = False
# حجم الدفعة والتأخير للاستئناف التدريجي بعد النشر (كل 20 حساب يليهم انتظار 30 ثانية)
_RESUME_BATCH_SIZE: int = 20
_RESUME_BATCH_DELAY: float = 30.0

# ── التشغيل التدريجي العشوائي (Gradual Start) ────────────────────
_gradual_cancel = threading.Event()    # إشارة إلغاء التشغيل التدريجي
_gradual_running: bool = False         # هل تعمل عملية تشغيل تدريجي حالياً؟

# ══════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════
# إدارة تسجيل السجلات على القرص وحفظها لجميع الحسابات لمدة 24 ساعة (يوم كامل)
# ══════════════════════════════════════════════════════════════════
LOG_RETENTION_HOURS = 24
MAX_LOG_LINES_PER_FILE = 8000
_LOG_DATE_PATTERN = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def prune_log_file_24h(file_path: str, max_lines: int = MAX_LOG_LINES_PER_FILE) -> None:
    """
    تقليم ملف السجل بنظام التدفق المباشر (Streaming Tail/Truncate):
    - يتفادى تحميل كامل الملف في الذاكرة (بدون f.readlines()).
    - يقرأ من نهاية الملف مباشرة (seek) إذا كان حجم الملف كبيراً.
    - يحتفظ فقط بالأسطر خلال نافذة الـ 24 ساعة وبحد أقصى max_lines.
    - يستخدم استبدالاً ذرياً عبر ملف مؤقت لمنع تلف الملفات.
    """
    if not os.path.exists(file_path):
        return
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return

        cutoff = datetime.now() - timedelta(hours=LOG_RETENTION_HOURS)
        # تقدير نافذة القراءة: حد أقصى للأسطر * 350 بايت للسطر
        tail_bytes = min(file_size, max(65536, max_lines * 350))

        lines: List[str] = []
        with open(file_path, "rb") as f:
            if file_size > tail_bytes:
                f.seek(file_size - tail_bytes)
                # تجاهل أول سطر غير مكتمل بعد الـ seek
                f.readline()
            for line_bytes in f:
                try:
                    lines.append(line_bytes.decode("utf-8", errors="replace").replace("\r", ""))
                except Exception:
                    pass

        kept: List[str] = []
        include_current_block = True
        for line in lines:
            m = _LOG_DATE_PATTERN.match(line)
            if m:
                try:
                    dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                    include_current_block = (dt >= cutoff)
                except Exception:
                    include_current_block = True
            if include_current_block:
                kept.append(line)

        if len(kept) > max_lines:
            kept = kept[-max_lines:]

        with open(file_path, "w", encoding="utf-8", errors="replace") as f:
            f.writelines(kept)
    except Exception as e:
        log.warning(f"Error pruning log file {file_path}: {e}")


def cleanup_expired_bot_logs():
    """
    تنظيف دوري لملفات السجلات bot_*.log:
    1. حذف ملفات السجلات بالكامل إذا مر على آخر تعديل لها أكثر من 24 ساعة (للبوتات المتوقفة).
    2. تقليم ملفات السجلات الحالية بحذف الأسطر التي مر عليها أكثر من 24 ساعة.
    """
    try:
        now_ts = time.time()
        max_age_sec = LOG_RETENTION_HOURS * 3600
        removed_count = 0
        pruned_count = 0

        dirs_to_check = [_LOGS_DIR]
        if os.path.exists(_ROOT):
            dirs_to_check.append(_ROOT)

        for check_dir in dirs_to_check:
            if not os.path.exists(check_dir):
                continue
            for fname in os.listdir(check_dir):
                if fname.startswith("bot_") and fname.endswith(".log") and fname != "bot_errors.log":
                    full_p = os.path.join(check_dir, fname)
                    try:
                        mtime = os.path.getmtime(full_p)
                        # إذا كان الملف لم يُعدل منذ أكثر من 24 ساعة، احذفه بالكامل
                        if now_ts - mtime > max_age_sec:
                            os.remove(full_p)
                            removed_count += 1
                        else:
                            # تقليم الأسطر القديمة التي تجاوزت 24 ساعة
                            prune_log_file_24h(full_p)
                            pruned_count += 1
                    except Exception:
                        pass

        if removed_count > 0 or pruned_count > 0:
            log.info(f"🧹 [تنظيف السجلات] تم حذف {removed_count} ملفات قديمة تجاوزت 24 ساعة وتقليم {pruned_count} ملفات نشطة.")
    except Exception as ex:
        log.warning(f"Error in cleanup_expired_bot_logs: {ex}")


def _is_running(castle_id: str) -> bool:
    with _lock:
        if castle_id in _user_stopped:
            return False
        if castle_id in _reserved:
            return True
        ev = _stop_events.get(castle_id)
        if ev and ev.is_set():
            return False
        t = _threads.get(castle_id)
        if t is not None and t.is_alive():
            return True
        prefix = f"bot-{castle_id[:10]}"
        for th in threading.enumerate():
            if th.name == prefix and th.is_alive():
                if ev and ev.is_set():
                    return False
                _threads[castle_id] = th
                return True
        return False


def _get_real_status(castle_id: str) -> str:
    """الحالة الحقيقية: الـ thread + حالة اتصال اللعبة معاً، فورية وبدون أي ارتداد لحالة running."""
    with _lock:
        conn = _conn_states.get(castle_id)
        if conn == 'deploying':
            return 'deploying'

        if castle_id in _user_stopped:
            return 'idle'

        matched_cid = castle_id
        if castle_id not in _threads and castle_id not in _castle_users:
            for cid, em in _castle_emails.items():
                if em == castle_id or cid == castle_id:
                    matched_cid = cid
                    break

        if _conn_states.get(matched_cid) == 'deploying':
            return 'deploying'

        if matched_cid in _user_stopped:
            return 'idle'

        if castle_id in _reserved or matched_cid in _reserved:
            if _deploy_mode:
                return 'deploying'
            return 'starting'

        ev = _stop_events.get(matched_cid) or _stop_events.get(castle_id)
        if ev and ev.is_set():
            return 'idle'

        t = _threads.get(matched_cid) or _threads.get(castle_id)
        if t is None or not t.is_alive():
            prefix = f"bot-{matched_cid[:10]}"
            found_t = None
            for th in threading.enumerate():
                if th.name == prefix and th.is_alive():
                    found_t = th
                    break
            if not found_t:
                # إذا لم يكن هناك Thread شغال، نفحص هل القلعة مسجلة كحالة خطأ في قاعدة البيانات
                try:
                    c_rec = db.get_castle_by_id(matched_cid) or db.get_castle_by_id(castle_id)
                    if c_rec and (c_rec.get("conn_state") == "error" or c_rec.get("state") == "error"):
                        return 'error'
                except Exception:
                    pass
                return 'idle'
            if matched_cid in _user_stopped or castle_id in _user_stopped:
                return 'idle'
            _threads[matched_cid] = found_t

        conn = _conn_states.get(matched_cid) or _conn_states.get(castle_id, 'connected')
        if conn in ('disconnected', 'reconnecting', 'waiting', 'idle', 'deploying', 'error'):
            return conn
        return 'running'


def _stop_and_join_bot(castle_id: str, timeout: float = 3.0) -> bool:
    """
    إيقاف بوت بطريقة حتمية وضمان دورة حياة الخيوط:
    1. تفعيل إشارة الإيقاف ev.set() واستدعاء mgr.stop().
    2. خارج _lock، انتظار انتهاء الخيط عبر t.join(timeout=timeout).
    3. إذا لم ينتهِ الخيط خلال المهلة، نقله إلى _stalled_threads للتشخيص بدلاً من تركه كخيط شبح يتيم.
    4. تنظيف كافة مراجع التتبع بأمان.
    """
    with _lock:
        _user_stopped.add(castle_id)
        _reserved.discard(castle_id)
        ev = _stop_events.get(castle_id)
        mgr = _bot_managers.get(castle_id)
        t = _threads.get(castle_id)
        email = _castle_emails.get(castle_id, "")
        user_id = _castle_users.get(castle_id, "")

    # 1. إيقاف مدير البوت وإشارة الإيقاف
    if mgr:
        try:
            mgr.stop()
        except Exception as ex:
            log.debug(f"mgr.stop error for {castle_id}: {ex}")

    if ev:
        ev.set()

    # 2. انتظار الخيط خارج _lock
    joined = True
    if t is not None and t.is_alive() and t != threading.current_thread():
        t.join(timeout=timeout)
        if t.is_alive():
            joined = False
            log.warning(f"⚠️ [Thread-Join] القلعة {castle_id} استمر خيطها حياً بعد {timeout}s، جرى نقله إلى _stalled_threads.")
            with _lock:
                _stalled_threads[castle_id] = {
                    "thread": t,
                    "ident": t.ident,
                    "name": t.name,
                    "castle_id": castle_id,
                    "email": email,
                    "user_id": user_id,
                    "stalled_at": datetime.now(timezone.utc).isoformat(),
                }

    # 3. تنظيف المراجع العامة بأمان
    with _lock:
        _threads.pop(castle_id, None)
        _stop_events.pop(castle_id, None)
        _bot_managers.pop(castle_id, None)
        _reserved.discard(castle_id)
        _log_qs.pop(castle_id, None)
        _conn_states.pop(castle_id, None)
        if joined:
            _castle_emails.pop(castle_id, None)
            _castle_users.pop(castle_id, None)
            _deleted_castles.discard(castle_id)
            _user_stopped.discard(castle_id)

    _notify_user_status_change(user_id, castle_id)
    return joined


# ══════════════════════════════════════════════════════════════════
# Pydantic Request & Response Models
# ══════════════════════════════════════════════════════════════════

class StartBotRequest(BaseModel):
    castle_id:     str
    user_id:       str
    email:         str
    password:      Optional[str] = None
    config:        Optional[Any] = None
    loop_interval: int = 40

class StopBotRequest(BaseModel):
    castle_id: str

class ConnStateRequest(BaseModel):
    castle_id: str
    state: str

class UserRegisterRequest(BaseModel):
    uid:           str
    email:         str
    username:      Optional[str] = ""
    phone:         Optional[str] = ""
    tenant_domain: Optional[str] = ""

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
    castle_name:   Optional[str] = None
    config:        Optional[Dict[str, Any]] = None
    version:       Optional[int] = None
    loop_interval: Optional[int] = None

class CastlesLoopIntervalsRequest(BaseModel):
    intervals: Dict[str, int]

class CastleConfigUpdateRequest(BaseModel):
    config:  Dict[str, Any]
    version: Optional[int] = None

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
                sak = os.path.join(_ROOT, "database", "firebase_service_account.json")
                if not os.path.exists(sak):
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
    if castle_id in _deleted_castles:
        return
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
        _notify_user_status_change(user_id, castle_id)
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء تحديث حالة القلعة محلياً: {e}")


def sync_castle_resources_db(email: str, data: dict, user_id: Optional[str] = None, castle_id: Optional[str] = None):
    """حفظ موارد القلعة ومعلوماتها في SQLite المحلية فوراً."""
    if castle_id and castle_id in _deleted_castles:
        return
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

def is_super_admin(user_or_email: Any) -> bool:
    """التحقق الصارم والموحد من هوية المشرف الأعلى (ibraboths@gmail.com حصراً)."""
    if not user_or_email:
        return False
    if isinstance(user_or_email, dict):
        email = str(user_or_email.get("email", "")).strip().lower()
    else:
        email = str(user_or_email).strip().lower()
    return email == "ibraboths@gmail.com"

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> Dict[str, Any]:
    """
    التحقق الصارم من هوية المستخدم عبر Firebase ID Token المشفر.
    لا يمكن لأي مستخدم تجاوز المصادقة إطلاقاً بدون توكن صالح وصادر من Firebase.
    ويشمل الفحص العزل التام للمستخدمين بحيث يمنع دخول حسابات نطاق آخر.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header (Bearer token required)")

    token = credentials.credentials
    try:
        _ensure_firebase()
        import firebase_admin
        from firebase_admin import auth as fb_auth

        if not firebase_admin._apps:
            raise HTTPException(status_code=500, detail="Firebase Admin SDK is not initialized")

        decoded = fb_auth.verify_id_token(token)
        uid = str(decoded.get("uid", "")).strip()
        email = str(decoded.get("email", "")).strip().lower()

        if not uid or not email:
            raise HTTPException(status_code=401, detail="Invalid token payload: missing UID or email")

        # قراءة بيانات المستخدم من SQLite
        user_record = db.get_user(uid)
        is_super = is_super_admin(email)
        merchant_cfg = get_tenant_by_admin_email(email)
        is_merchant = merchant_cfg is not None
        assigned_role = "admin" if is_super else ("merchant_admin" if is_merchant else "user")

        if not user_record:
            req_host = request.headers.get("x-tenant-domain") or request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
            target_tenant = get_tenant_by_domain(clean_domain(req_host))
            fallback_tenant_domain = merchant_cfg["domains"][0] if is_merchant else (target_tenant["domains"][0] if target_tenant.get("id") != "main" else "")

            # إنشاء سجل مبدئي للمستخدم في SQLite إن لم يكن موجوداً
            db.create_or_update_user(
                uid=uid,
                email=email,
                username=decoded.get("name", email.split("@")[0]),
                role=assigned_role,
                tenant_domain=fallback_tenant_domain
            )
            user_record = db.get_user(uid)

        if user_record:
            if user_record.get("is_banned"):
                raise HTTPException(status_code=403, detail=f"تم حظر حسابك: {user_record.get('banned_reason') or 'مخالفة الشروط'}")
            user_dict = dict(user_record)
            user_dict["is_super_admin"] = is_super
            user_dict["is_merchant_admin"] = is_merchant
            user_dict["merchant_tenant"] = merchant_cfg
            if is_super:
                user_dict["role"] = "admin"
            elif is_merchant:
                user_dict["role"] = "merchant_admin"

            # 🛡️ الفحص الأمني الصارم لعزل النطاقات (Tenant Domain Isolation)
            req_domain = request.headers.get("x-tenant-domain") or request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
            if req_domain and not is_user_allowed_for_tenant_domain(user_dict, req_domain):
                raise HTTPException(
                    status_code=403,
                    detail="هذا الحساب غير مسجل في هذا النظام"
                )

            return user_dict

        return {
            "uid": uid,
            "email": email,
            "role": assigned_role,
            "is_super_admin": is_super,
            "is_merchant_admin": is_merchant,
            "merchant_tenant": merchant_cfg,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"🔒 Token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {e}")


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """يسمح بالمشرف الأعلى (ibraboths@gmail.com) أو مشرفي التجار المعتمدين."""
    if user.get("is_super_admin") or is_super_admin(user):
        user["is_super_admin"] = True
        user["is_merchant_admin"] = False
        return user

    email = str(user.get("email", "")).strip().lower()
    merchant_cfg = get_tenant_by_admin_email(email)
    if merchant_cfg or user.get("is_merchant_admin"):
        user["is_super_admin"] = False
        user["is_merchant_admin"] = True
        user["merchant_tenant"] = merchant_cfg or user.get("merchant_tenant")
        return user

    uid = user.get("uid", "")
    log.error(f"🚨 محاولة وصول غير مصرح بها لصفحة الإدارة من الحساب: {email} (UID: {uid})")
    raise HTTPException(status_code=403, detail="وصول مرفوض: لا تملك صلاحيات إدارة النظام")


def require_super_admin(user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    """التأكد الصارم من أن المستخدم هو المشرف الأعلى الحصري للمنصة (ibraboths@gmail.com)."""
    if user.get("is_super_admin") or is_super_admin(user):
        return user
    email = str(user.get("email", "")).strip().lower()
    log.error(f"🚨 محاولة وصول لصفحة المشرف الأعلى الحصرية من: {email}")
    raise HTTPException(status_code=403, detail="وصول مرفوض: هذه الميزة مخصصة حصرياً للمشرف الرئيسي")


get_admin_user = require_admin

INTERNAL_API_SECRET = os.environ.get("INTERNAL_API_SECRET", "ibra_internal_secret_key_2026")

def verify_internal_access(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> Dict[str, Any]:
    """
    حماية المسارات الداخلية الحساسة (/api/internal/* و /api/bot/conn-state):
    يُسمح بالوصول في إحدى الحالات التالية فقط:
    1. ترويسة X-Internal-Token تطابق التوكن السري المعتمد (INTERNAL_API_SECRET).
    2. الاتصال المحلي المباشر (Localhost / Loopback: 127.0.0.1 أو ::1) بدون ترويسات خارجية موجهة.
    3. مصادقة Bearer Token لمستخدم يحمل صلاحيات الإدارة (Admin / Merchant Admin).
    """
    # 1. فحص ترويسة X-Internal-Token
    internal_token = request.headers.get("x-internal-token")
    if internal_token and internal_token.strip() == INTERNAL_API_SECRET:
        return {"source": "internal_token", "authorized": True}

    # 2. فحص الاتصال المحلي المباشر (Loopback)
    client_host = getattr(request.client, "host", "") if request.client else ""
    x_real_ip = request.headers.get("x-real-ip")
    x_forwarded_for = request.headers.get("x-forwarded-for")

    is_direct_loopback = client_host in ("127.0.0.1", "::1", "localhost", "testclient")
    if is_direct_loopback and (not x_real_ip or x_real_ip in ("127.0.0.1", "::1", "localhost", "testclient")):
        return {"source": "loopback", "authorized": True}

    # 3. فحص صلاحيات المستخدم الإدارية عبر توكن المصادقة (إن وُجد)
    if credentials and credentials.credentials:
        try:
            user = get_current_user(request, credentials)
            if user.get("is_super_admin") or is_super_admin(user) or user.get("role") in ("admin", "merchant_admin"):
                return user
        except Exception:
            pass

    log.warning(f"🚨 محاولة وصول غير مصرح بها لمسار داخلي ({request.url.path}) من IP: {client_host}")
    raise HTTPException(
        status_code=403,
        detail="Forbidden: Internal endpoint requires admin role, internal token, or direct local loopback access"
    )


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
            from core.session_manager import get_last_auth_error
            err_msg = get_last_auth_error(email) or f"الحساب {email} تعذر تسجيل دخوله (تأكد من صحة البريد وكلمة المرور)"
            log.error(f"❌ [{email}] {err_msg}")
            _safe_log_put(log_q, f"[{datetime.now():%H:%M:%S}] ❌ {err_msg}")
            update_castle_status_db(user_id, castle_id, "error", err_msg, conn_state="error")
            with _lock:
                _threads.pop(castle_id, None)
                _stop_events.pop(castle_id, None)
                _log_qs.pop(castle_id, None)
                _conn_states.pop(castle_id, None)
                _castle_users.pop(castle_id, None)
                _castle_emails.pop(castle_id, None)
                _reserved.discard(castle_id)
                _deleted_castles.discard(castle_id)
            _notify_user_status_change(user_id, castle_id)
            return
        else:
            log.info(f"✅ [{email}] تم تأكيد الجلسة بنجاح.")
    except Exception as e:
        log.error(f"💥 [{email}] خطأ أثناء التحقق من الجلسة: {e}")
        _safe_log_put(log_q, f"[{datetime.now():%H:%M:%S}] 💥 خطأ الجلسة: {e}")
        update_castle_status_db(user_id, castle_id, "error", str(e), conn_state="error")
        with _lock:
            _threads.pop(castle_id, None)
            _stop_events.pop(castle_id, None)
            _log_qs.pop(castle_id, None)
            _conn_states.pop(castle_id, None)
            _castle_users.pop(castle_id, None)
            _castle_emails.pop(castle_id, None)
            _reserved.discard(castle_id)
            _deleted_castles.discard(castle_id)
        _notify_user_status_change(user_id, castle_id)
        return

    # 4. ملف log البوت (متاح لجميع الحسابات مع الاحتفاظ بسجلات 24 ساعة)
    bot_log_path = os.path.join(_LOGS_DIR, f"bot_{email.replace('@','_').replace('.','_')}.log")

    _log_file_handle = None
    _log_line_counter = [0]

    # تقليم السجل عند بداية كل دورة لحذف ما تجاوز 24 ساعة
    prune_log_file_24h(bot_log_path)

    try:
        _log_file_handle = open(bot_log_path, "a", encoding="utf-8", errors="replace")
        _log_file_handle.write(f"\n{'='*60}\n[{datetime.now():%Y-%m-%d %H:%M:%S}] دورة جديدة\n{'='*60}\n")
        _log_file_handle.flush()
    except Exception as e:
        log.warning(f"Failed to open bot log file {bot_log_path}: {e}")

    def _trim_log_file():
        """يقص ملف اللوق بحذف ما زاد عن 24 ساعة عند تجاوز السعة."""
        nonlocal _log_file_handle
        if not _log_file_handle:
            return
        try:
            _log_file_handle.close()
            prune_log_file_24h(bot_log_path)
            _log_file_handle = open(bot_log_path, "a", encoding="utf-8", errors="replace")
        except Exception:
            try:
                _log_file_handle = open(bot_log_path, "a", encoding="utf-8", errors="replace")
            except Exception:
                pass

    def _log_callback(line: str, already_printed: bool = False):
        # طباعة السجلات إلى الكونسول: السجلات الهامة فقط التي لم تُطبع مسبقاً عبر console_h
        if not already_printed:
            should_print = any(
                k in line for k in ("منسق", "مسيرة", "مسيرات", "فيالق", "فيلق", "جمع", "غزاة", "معقل", "أولوية", "🚨", "🎉", "⚠️", "❌", "🎖️", "⚔️", "🌾", "🏰", "🏗️", "البناء", "building", "march_manager", "gather", "monster", "stronghold", "✅", "⏭️", "نجاح", "فشل", "كود الخطأ", "🐉", "Abra", "وحش")
            )
            if should_print:
                print(f"[{email}] {line}", flush=True)

        if _log_file_handle:
            try:
                # كتابة السطر مع التاريخ والوقت كاملاً لدقة حساب مدة الـ 24 ساعة
                _log_file_handle.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {line}\n")
                _log_file_handle.flush()
                _log_line_counter[0] += 1
                # تقليم السجل كل 1000 سطر لتفادي ضغط الـ I/O على القرص
                if _log_line_counter[0] >= 1000:
                    _log_line_counter[0] = 0
                    _trim_log_file()
            except Exception:
                pass
        stamped = f"[{datetime.now():%H:%M:%S}] {line}"
        _safe_log_put(log_q, stamped)

        if stop_event.is_set():
            return

        # ── تحليل أحداث البوت الموجهة لتحديث الحالة ──
        if "[FIREBASE_EVENT]" in line or "[BOT_EVENT]" in line:
            try:
                tag = "[FIREBASE_EVENT]" if "[FIREBASE_EVENT]" in line else "[BOT_EVENT]"
                parts = line.split(tag, 1)[1].strip()
                m_st  = re.search(r'conn_state=(\w+)', parts)
                m_nr  = re.search(r'next_run_time=(\S+)', parts)
                m_msg = re.search(r'message=(.+?)(?:\s+next_run_time=\S+)?$', parts)
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
                        "food":                 rmap.get("food", 0),
                        "wood":                 rmap.get("wood", 0),
                        "iron":                 rmap.get("iron", 0),
                        "diamond":              rmap.get("diamond", 0),
                        "gold":                 rmap.get("gold", 0),
                        "stamina":              rmap.get("stamina", 100),
                        "unprotected_food":     rmap.get("unprotected_food", 0),
                        "unprotected_wood":     rmap.get("unprotected_wood", 0),
                        "unprotected_iron":     rmap.get("unprotected_iron", 0),
                        "unprotected_diamond":  rmap.get("unprotected_diamond", 0),
                        "safe_food":            rmap.get("safe_food", 0),
                        "safe_wood":            rmap.get("safe_wood", 0),
                        "safe_iron":            rmap.get("safe_iron", 0),
                        "safe_diamond":         rmap.get("safe_diamond", 0),
                        "last_updated":         now_iso,
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

    # 5. فحص الاشتراك يتم طبيعياً في بداية كل دورة داخل البوت نفسه بدون أي خيوط إضافية
    forced_stop_reason = ""

    # 6. تشغيل BotManager
    try:
        # جلب أحدث إعدادات القلعة مباشرة من قاعدة البيانات المحلية SQLite
        castle_rec = db.get_castle_by_id(castle_id, user_id) or db.get_castle(email)
        initial_cfg = (castle_rec.get("config") if castle_rec and isinstance(castle_rec.get("config"), dict) else {}) or req.config or {}

        # استخراج وقت دورة البوت المخصص للقلعة من قاعدة البيانات أو من الطلب مع فرض الحدود (30 إلى 180 دقيقة)
        custom_interval = (castle_rec.get("loop_interval") if castle_rec else None) or req.loop_interval or 40
        try:
            target_interval = max(30, min(180, int(custom_interval)))
        except (ValueError, TypeError):
            target_interval = 40

        from bot_manager import BotManager
        manager = BotManager(
            email,
            initial_cfg,
            reconnect_wait_seconds=250,
            user_id=user_id,
            castle_id=castle_id,
            stop_event=stop_event,
            log_callback=_log_callback,
        )
        with _lock:
            _bot_managers[castle_id] = manager
        asyncio.run(manager.run_loop(loop_interval_minutes=target_interval))

    except Exception as e:
        log.error(f"💥 [{email}] خطأ في البوت: {e}", exc_info=True)
        _safe_log_put(log_q, f"[{datetime.now():%H:%M:%S}] 💥 خطأ: {e}")
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
            _castle_emails.pop(castle_id, None)
            _reserved.discard(castle_id)
            _user_stopped.discard(castle_id)
            if castle_id in _deleted_castles:
                _deleted_castles.discard(castle_id)
        _notify_user_status_change(user_id, castle_id)

    # 7. تحديث الحالة النهائية في SQLite
    if castle_id in _deleted_castles:
        log.info(f"🗑️ [{email}] تم حذف القلعة، تخطي تحديث الحالة النهائية.")
        return

    c_final = db.get_castle_by_id(castle_id, user_id) or {}
    if not c_final:
        return
    is_already_error = (c_final.get("conn_state") == "error" or c_final.get("state") == "error")

    if is_already_error:
        # إذا كانت القلعة توقفت بسبب خطأ صريح (مثل خطأ كلمة المرور)، نحتفظ بالحالة كما هي ولا نمسحها بـ "اكتمل البوت"
        log.info(f"🛑 [{email}] الاحتفاظ بحالة الخطأ الصريحة في قاعدة البيانات: {c_final.get('conn_message')}")
    elif forced_stop_reason:
        _safe_log_put(log_q, f"[{datetime.now():%H:%M:%S}] 🛑 إيقاف إجباري: {forced_stop_reason}")
        log.info(f"🛑 [{email}] إيقاف إجباري: {forced_stop_reason}")
        update_castle_status_db(user_id, castle_id, "idle", f"متوقف إجبارياً: {forced_stop_reason}", conn_state="idle")
    elif was_user_stopped:
        _safe_log_put(log_q, f"[{datetime.now():%H:%M:%S}] ⏹️ تم إيقاف البوت بواسطة المستخدم")
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


@app.get("/manifest.json")
@app.get("/api/manifest.json")
def get_dynamic_manifest(request: Request):
    """توليد ملف manifest.json ديناميكياً بحسب الدومين لتثبيت التطبيق PWA بالاسم والشعار والألوان الخاصة بكل تاجر."""
    req_domain = request.headers.get("x-tenant-domain") or request.headers.get("host") or ""
    tenant = get_tenant_by_domain(req_domain)
    brand_name = tenant.get("brand_name", "IBRA BOT")
    primary_color = tenant.get("primary_color", "#10b981")
    logo = tenant.get("logo_url") or "/logo.png?v=2"
    if tenant.get("id") == "nurjan":
        logo = "/nurjan_logo.jpeg"

    mime_type = "image/png" if logo.lower().endswith(".png") else "image/jpeg"

    return {
        "name": brand_name,
        "short_name": brand_name,
        "description": f"{brand_name} — لوحة تحكم وإدارة البوت",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#0a0f0a",
        "theme_color": primary_color,
        "lang": "ar",
        "dir": "rtl",
        "categories": ["utilities", "games", "productivity"],
        "icons": [
            {
                "src": logo,
                "sizes": "192x192",
                "type": mime_type,
                "purpose": "any"
            },
            {
                "src": logo,
                "sizes": "512x512",
                "type": mime_type,
                "purpose": "any"
            },
            {
                "src": logo,
                "sizes": "192x192",
                "type": mime_type,
                "purpose": "maskable"
            },
            {
                "src": logo,
                "sizes": "512x512",
                "type": mime_type,
                "purpose": "maskable"
            }
        ]
    }



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
    """تسجيل أو مزامنة مستخدم جديد في SQLite عند تسجيل حسابه في Firebase مع ربطه بالدومين."""
    clean_tenant = clean_domain(req.tenant_domain or "")
    ok = db.create_or_update_user(
        uid=req.uid,
        email=req.email,
        username=req.username or req.email.split("@")[0],
        phone=req.phone or "",
        tenant_domain=clean_tenant,
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
    is_super = is_super_admin(current_user)
    is_merchant = current_user.get("is_merchant_admin") or is_merchant_admin(current_user.get("email", ""))

    if user_id and user_id.strip() and (is_super or is_merchant):
        target_uid = user_id.strip()
        if is_merchant:
            _verify_merchant_access_to_user(current_user, db.get_user(target_uid))
        castles = db.get_user_castles(target_uid)
    elif is_super and not caller_uid:
        castles = db.get_all_castles()
    else:
        target_uid = caller_uid
        castles = db.get_user_castles(target_uid)

    # دمج الحالة الحقيقية للـ thread مع الاحتفاظ بحالة الخطأ الصريحة
    for c in castles:
        cid = c.get("castle_id", "")
        real_st = _get_real_status(cid)
        if real_st == "error" or c.get("conn_state") == "error" or c.get("state") == "error":
            c["state"] = "error"
            c["conn_state"] = "error"
        else:
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
    is_admin = is_super_admin(current_user)

    c = db.get_castle_by_id(castle_id, None if is_admin else uid)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")

    real_st = _get_real_status(castle_id)
    if real_st == "error" or c.get("conn_state") == "error" or c.get("state") == "error":
        c["state"] = "error"
        c["conn_state"] = "error"
    else:
        c["state"] = real_st
        c["conn_state"] = real_st
        if real_st == "idle" and c.get("conn_message") in ("running", "connected", "waiting", "reconnecting"):
            c["conn_message"] = "جاهز للتشغيل"

    return {"castle": c}


@app.get("/api/castles/{castle_id}/avatar")
def get_castle_avatar(castle_id: str):
    """
    إرجاع الصورة الشخصية الحقيقية للقلعة (Avatar) عبر خادم ONEMT الرسمي أو SVG رمزي.
    """
    from fastapi.responses import RedirectResponse, Response
    c = db.get_castle_by_id(castle_id)
    if c:
        avatar_val = c.get("avatar") or (c.get("castle_info", {}).get("avatar") if isinstance(c.get("castle_info"), dict) else None)
        if avatar_val:
            avatar_str = str(avatar_val).strip()
            if avatar_str.startswith("http://") or avatar_str.startswith("https://"):
                return RedirectResponse(url=avatar_str)
            if "customAvatar" in avatar_str or avatar_str.startswith("/"):
                clean_path = avatar_str.lstrip("/")
                return RedirectResponse(url=f"https://hayyaimage.onemt.co/{clean_path}")

    # SVG افتراضي أنيق لشعار القلعة في حال لم يكن هناك صورة مخصصة بدلاً من 404
    svg_data = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
      <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#d4af37;stop-opacity:1" />
          <stop offset="100%" style="stop-color:#8b0000;stop-opacity:1" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#grad)" stroke="#fff" stroke-width="2"/>
      <path d="M50 20 L58 38 L78 38 L62 50 L68 70 L50 58 L32 70 L38 50 L22 38 L42 38 Z" fill="#fff"/>
    </svg>"""
    return Response(content=svg_data, media_type="image/svg+xml")


@app.post("/api/castles")
def add_castle(req: CastleCreateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """إضافة قلعة جديدة في SQLite مع التحقق من الحد المسموح للاشتراك."""
    uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)

    # 1. التحقق من حد القلاع المسموح وحالة الموافقة والحظر
    is_within_quota = True
    st = ""
    if not is_admin:
        u = db.get_user(uid)
        if u:
            # 1.1 فحص حظر الحساب
            if u.get("is_banned"):
                raise HTTPException(status_code=403, detail="حسابك محظور من قبل الإدارة، لا يمكنك إضافة قلاع جديدة")

            st = (u.get("subscription") or {}).get("status") or u.get("subscription_status")
            if st == "pending_approval":
                # سقف مفتوح تماماً: السماح بإضافة أي عدد يريده المستخدم من القلاع بانتظار موافقة الإدارة
                is_within_quota = False
            else:
                is_sub_valid, _ = db.check_user_subscription_db(uid)
                active_cnt, _ = db.count_user_castles(uid)
                max_allowed = (u.get("subscription") or {}).get("max_castles_allowed") or u.get("max_castles_allowed", 0)
                if not is_sub_valid or active_cnt >= max_allowed:
                    is_within_quota = False

    castle_id = f"c_{uuid.uuid4().hex[:12]}"
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
        "conn_message": "جاهز للتشغيل" if is_within_quota else (
            "بانتظار موافقة الإدارة لتفعيل باقة التجربة" if st == "pending_approval" else "بانتظار موافقة الإدارة (تم تجاوز الحد المسموح)"
        ),
        "created_at": now_iso,
        "last_updated": now_iso,
    }

    ok = db.save_castle(castle_data)
    if not ok:
        raise HTTPException(status_code=500, detail="تعذر حفظ القلعة في قاعدة البيانات")

    # مزامنة الحساب والحدود
    db.sync_user_castles_and_quota(uid)

    return {"status": "success", "castle": db.get_castle_by_id(castle_id, uid)}


@app.put("/api/castles/loop-intervals")
def update_castles_loop_intervals_endpoint(
    req: CastlesLoopIntervalsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """تحديث مدة دورة البوت (loop_interval) لمجموعة قلاع دفعة واحدة."""
    uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)

    if not req.intervals:
        return {"status": "success", "message": "لا توجد تعديلات"}

    target_uid = None if is_admin else uid
    ok = db.update_castles_loop_interval(req.intervals, user_id=target_uid)
    if not ok:
        raise HTTPException(status_code=500, detail="فشل تحديث أوقات دورات القلاع")

    return {"status": "success", "message": "تم تحديث أوقات دورات القلاع بنجاح"}


@app.put("/api/castles/{castle_id}")
def update_castle(castle_id: str, req: CastleUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تحديث إعدادات أو اسم القلعة في SQLite مع فحص النسخة التفاؤلي (OCC)."""
    uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)

    c = db.get_castle_by_id(castle_id, None if is_admin else uid)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")

    if req.config is not None:
        res = db.update_castle_config(
            castle_id,
            req.config,
            user_id=None if is_admin else uid,
            expected_version=req.version
        )
        if not res.get("success"):
            if res.get("conflict"):
                raise HTTPException(
                    status_code=409,
                    detail=f"Conflict: Castle config has been modified concurrently. Current version is {res.get('current_version')}"
                )
            raise HTTPException(status_code=500, detail=res.get("error", "Failed to update castle config"))

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

    if req.loop_interval is not None:
        try:
            val = max(30, min(180, int(req.loop_interval)))
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE castle_states SET loop_interval = ?, last_updated = ? WHERE castle_id = ?",
                    (val, datetime.now(timezone.utc).isoformat(), castle_id)
                )
                conn.commit()
        except Exception:
            pass

    return {"status": "success", "castle": db.get_castle_by_id(castle_id, None if is_admin else uid)}


@app.put("/api/castles/{castle_id}/config")
def update_castle_config_endpoint(castle_id: str, req: CastleConfigUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تحديث إعدادات القلعة المخصصة مع فحص النسخة التفاؤلي (OCC) وإرجاع 409 عند التضارب."""
    uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)

    c = db.get_castle_by_id(castle_id, None if is_admin else uid)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")

    res = db.update_castle_config(
        castle_id,
        req.config,
        user_id=None if is_admin else uid,
        expected_version=req.version
    )
    if not res.get("success"):
        if res.get("conflict"):
            raise HTTPException(
                status_code=409,
                detail=f"Conflict: Castle config has been modified concurrently. Current version is {res.get('current_version')}"
            )
        raise HTTPException(status_code=500, detail=res.get("error", "Failed to update castle config"))

    return {"success": True, "version": res.get("version"), "config": res.get("config")}


@app.put("/api/castles/{castle_id}/credentials")
def update_castle_creds(castle_id: str, req: CastleCredentialsUpdateRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تحديث البريد وكلمة المرور للقلعة في SQLite."""
    uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)

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
    """تفعيل أو تعطيل القلعة في SQLite مع التحقق من الباقة والحد الأقصى المسموح."""
    uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)

    if not is_admin:
        u = db.get_user(uid)
        if u:
            if u.get("is_banned"):
                raise HTTPException(status_code=403, detail="الحساب محظور من قبل الإدارة")

            st = (u.get("subscription") or {}).get("status") or u.get("subscription_status")
            if st == "pending_approval":
                raise HTTPException(status_code=403, detail="الحساب بانتظار موافقة الإدارة أولاً لتفعيل باقة التجربة")

            # إذا كان المستخدم يريد تفعيل القلعة
            if req.is_active:
                is_sub_valid, sub_msg = db.check_user_subscription_db(uid)
                if not is_sub_valid:
                    raise HTTPException(status_code=403, detail=sub_msg)

                active_cnt, _ = db.count_user_castles(uid)
                max_allowed = (u.get("subscription") or {}).get("max_castles_allowed") or u.get("max_castles_allowed", 0)
                c = db.get_castle_by_id(castle_id, uid)
                if c and not c.get("is_active"):
                    if active_cnt >= max_allowed:
                        raise HTTPException(
                            status_code=400,
                            detail=f"وصلت للحد الأقصى من القلاع المسموح بها في باقتك ({max_allowed}). يرجى إيقاف قلعة أخرى أولاً أو ترقية الباقة."
                        )

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

    # إذا تم تفعيلها، نحدث حالة الرسالة و state إلى idle
    if req.is_active:
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE castle_states SET state = 'idle', conn_state = 'idle', conn_message = 'جاهز للتشغيل' WHERE castle_id = ?",
                    (castle_id,)
                )
                conn.commit()
        except Exception:
            pass

    # مزامنة الحساب
    db.sync_user_castles_and_quota(uid)

    return {"status": "success", "is_active": req.is_active}


@app.delete("/api/castles/{castle_id}")
def delete_castle_endpoint(castle_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """حذف القلعة نهائياً من SQLite وتصفية عملياتها وسجلاتها."""
    uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)
    is_merchant = current_user.get("is_merchant_admin") or is_merchant_admin(current_user.get("email", ""))

    # معرفة إيميل القلعة قبل حذفها لتنظيف ملف اللوق والجلسة
    c_rec = db.get_castle(castle_id) or {}
    if is_merchant:
        _verify_merchant_access_to_user(current_user, db.get_user(c_rec.get("user_id", "")))

    c_email = str(c_rec.get("email", "")).strip().lower()

    # تسجيل القلعة فوراً في قائمة المحذوفات
    with _lock:
        _deleted_castles.add(castle_id)
        _user_stopped.add(castle_id)

    # إيقاف البوت وانتظار انتهائه بأمان مع مهلة زمنية خارج القفل العام
    _stop_and_join_bot(castle_id, timeout=3.0)

    # تنظيف ارتباط البروكسي للقلعة المحذوفة وحفظ التغييرات
    if c_email:
        try:
            from proxy.proxy_manager import remove_castle_proxy
            remove_castle_proxy(c_email)
        except Exception as ex:
            log.warning(f"⚠️ فشل تنظيف ارتباط البروكسي للقلعة {c_email}: {ex}")

    # تفريغ معرف القلعة من _deleted_castles و _user_stopped بعد اكتمال الموت وتحرير الموارد
    with _lock:
        _deleted_castles.discard(castle_id)
        _user_stopped.discard(castle_id)

    # تنظيف ملف اللوق الخاص بالقلعة من القرص
    if c_email:
        try:
            bot_log_path = os.path.join(_LOGS_DIR, f"bot_{c_email.replace('@','_').replace('.','_')}.log")
            if os.path.exists(bot_log_path):
                os.remove(bot_log_path)
        except Exception:
            pass

        # تنظيف الجلسة من session_cache.json
        try:
            from core.session_manager import SessionManager
            SessionManager().remove_session(c_email)
        except Exception:
            pass

    ok = db.delete_castle(castle_id) if (is_admin or is_merchant) else db.delete_castle_by_id(castle_id, uid)
    if not ok:
        raise HTTPException(status_code=404, detail="تعذر حذف القلعة")

    return {"status": "success", "message": "تم حذف القلعة بنجاح"}


# ── 👑 Admin Endpoints ────────────────────────────────────────────

@app.get("/api/admin/stats")
def get_admin_dashboard_stats(admin: Dict[str, Any] = Depends(require_admin)):
    """إحصائيات عامة للمشرف من SQLite (مفلترة للتاجر أو شاملة للمشرف الأعلى)."""
    if admin.get("is_merchant_admin"):
        tenant_domains = admin.get("merchant_tenant", {}).get("domains", [])
        stats = db.get_admin_stats(tenant_domains=tenant_domains)
        return stats

    stats = db.get_admin_stats()
    with _lock:
        active_cids = {cid for cid, t in _threads.items() if t.is_alive()}
        for t in threading.enumerate():
            if t.name.startswith("bot-") and t.is_alive():
                if t.name == "auto-resume" or t.name.startswith("sys-"):
                    continue
                prefix = t.name[4:]
                for cm in db.find_castles_by_id_prefix(prefix):
                    if cm.get("castle_id"):
                        active_cids.add(cm["castle_id"])
        stats["activeBots"] = len(active_cids)
    return stats


@app.get("/api/admin/live-processes")
def get_admin_live_processes(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query("all"),
    admin: Dict[str, Any] = Depends(require_super_admin)
):
    """
    ⚡ مراقبة العمليات الحية وترقيمها (Live Runtime Threads & Processes with Pagination):
    استعلام فوري ومباشر مع ترقيم صفحات حقيقي، بحث، وتصفية للحالات الست المعتمدة.
    - الحالات المسموح بها تنحصر حصراً في الحالات الست:
      1) running (شغالة فعلياً)
      2) waiting_next_cycle (بانتظار الدورة التالية)
      3) other_device_login (دخول من جهاز آخر)
      4) reconnecting (جاري إعادة الاتصال)
      5) waiting_relogin (بانتظار إعادة تسجيل الدخول)
      6) starting (جاري بدء التشغيل)
    - استبعاد القلاع المحذوفة أو المتوقفة يدوياً أو الخيوط غير المرتبطة.
    - عزل الخيوط العالقة أو المتعطلة في فئة تشخيصية منفصلة (stalled) لا تُحتسب ضمن total_active.
    """
    if hasattr(page, "default"):
        page = page.default
    if hasattr(page_size, "default"):
        page_size = page_size.default
    if hasattr(search, "default"):
        search = search.default
    if hasattr(status, "default"):
        status = status.default

    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 25)))

    active_list: List[Dict[str, Any]] = []
    stalled_list: List[Dict[str, Any]] = []
    registered_idents: Set[int] = set()

    # خريطة مساعدة سريعة لإيميلات المستخدمين أصحاب القلاع
    user_emails_cache: Dict[str, str] = {}

    def _resolve_user_email(uid: str) -> str:
        if not uid:
            return ""
        if uid in user_emails_cache:
            return user_emails_cache[uid]
        try:
            u = db.get_user(uid)
            em = str(u.get("email", "")) if u else ""
            user_emails_cache[uid] = em
            return em
        except Exception:
            return ""

    now = time.time()

    with _lock:
        # 1. فحص جميع القلاع المسجلة في _threads
        for cid, th in list(_threads.items()):
            if not th.is_alive():
                continue

            registered_idents.add(th.ident)

            # استبعاد القلاع المحذوفة من العمليات الحية تماماً
            if cid in _deleted_castles:
                continue

            mgr = _bot_managers.get(cid)
            conn_state = _conn_states.get(cid, "running")
            email = _castle_emails.get(cid, "")
            user_id = _castle_users.get(cid, "")
            stop_ev = _stop_events.get(cid)

            # إذا كانت القلعة في _user_stopped أو تم إرسال إشارة إيقاف
            if cid in _user_stopped or (stop_ev and stop_ev.is_set()):
                stalled_item = {
                    "castle_id": cid,
                    "email": email or cid,
                    "user_id": user_id,
                    "user_email": _resolve_user_email(user_id),
                    "thread_id": th.ident,
                    "thread_name": th.name,
                    "thread_alive": True,
                    "state": "stalled",
                    "live_category": "stalled",
                    "category_label": "خيط عالق / متعطل",
                    "status_message": "الخيط تلقى إشارة توقف ولم ينتهِ بعد",
                    "iteration": 0,
                    "loop_interval_minutes": 60,
                    "next_run_time": None,
                    "reconnect_attempt": 0,
                    "max_reconnect_attempts": 10,
                    "last_kick_reason": "",
                    "uptime_seconds": 0,
                    "is_connection_alive": False,
                    "is_stopped": True,
                    "is_stalled": True,
                    "start_time": now,
                }
                stalled_list.append(stalled_item)
                continue

            if mgr and hasattr(mgr, "get_live_info"):
                try:
                    info = mgr.get_live_info()
                except Exception as ex:
                    log.warning(f"Error getting live info from mgr for {cid}: {ex}")
                    info = {}
                info["castle_id"] = cid
                info["thread_id"] = th.ident
                info["thread_name"] = th.name
                info["thread_alive"] = True
                if not info.get("email"):
                    info["email"] = email or cid
                if not info.get("user_id"):
                    info["user_id"] = user_id
                info["user_email"] = _resolve_user_email(info.get("user_id", ""))

                # إذا كان الخيط متعطلاً وفق معايير mgr
                if info.get("is_stalled"):
                    stalled_list.append(info)
                    continue

                # إذا كان متوقفاً
                if info.get("is_stopped"):
                    continue

                active_list.append(info)
            else:
                # خيط بدون BotManager
                is_in_reserved = (cid in _reserved)
                if not is_in_reserved and conn_state != "starting":
                    stalled_list.append({
                        "castle_id": cid,
                        "email": email or cid,
                        "user_id": user_id,
                        "user_email": _resolve_user_email(user_id),
                        "thread_id": th.ident,
                        "thread_name": th.name,
                        "thread_alive": True,
                        "state": "stalled",
                        "live_category": "stalled",
                        "category_label": "خيط عالق / متعطل",
                        "status_message": "Thread بدون BotManager تجاوز مهلة البدء",
                        "iteration": 0,
                        "loop_interval_minutes": 60,
                        "next_run_time": None,
                        "reconnect_attempt": 0,
                        "max_reconnect_attempts": 10,
                        "last_kick_reason": "",
                        "uptime_seconds": 0,
                        "is_connection_alive": False,
                        "is_stopped": False,
                        "is_stalled": True,
                        "start_time": now,
                    })
                else:
                    # في مرحلة البدء الشرعية
                    active_list.append({
                        "castle_id": cid,
                        "email": email or cid,
                        "user_id": user_id,
                        "user_email": _resolve_user_email(user_id),
                        "thread_id": th.ident,
                        "thread_name": th.name,
                        "thread_alive": True,
                        "state": "starting",
                        "live_category": "starting",
                        "category_label": "جاري بدء التشغيل",
                        "current_step": "تهيئة الجلسة والاتصال",
                        "status_message": "جاري التحضير في الذاكرة...",
                        "iteration": 1,
                        "loop_interval_minutes": 60,
                        "next_run_time": None,
                        "reconnect_attempt": 0,
                        "max_reconnect_attempts": 10,
                        "last_kick_reason": "",
                        "uptime_seconds": 0,
                        "is_connection_alive": False,
                        "is_stopped": False,
                        "is_stalled": False,
                        "start_time": now,
                    })

        # 2. فحص أي Thread إضافي باسم bot- في الـ runtime لعزل الخيوط اليتيمة (Orphaned / Stalled Threads)
        for th in threading.enumerate():
            if th.name.startswith("bot-") and th.is_alive() and th.ident not in registered_idents:
                if th.name in ("bot-auto-resume", "auto-resume") or th.name.startswith("sys-"):
                    continue
                prefix = th.name[4:]
                registered_idents.add(th.ident)
                stalled_list.append({
                    "castle_id": prefix,
                    "email": prefix,
                    "user_id": "",
                    "user_email": "",
                    "thread_id": th.ident,
                    "thread_name": th.name,
                    "thread_alive": True,
                    "state": "stalled",
                    "live_category": "stalled",
                    "category_label": "خيط عالق / متعطل",
                    "status_message": "خيط غير مسجل في الذاكرة الحية (Orphaned Thread)",
                    "iteration": 0,
                    "loop_interval_minutes": 60,
                    "next_run_time": None,
                    "reconnect_attempt": 0,
                    "max_reconnect_attempts": 10,
                    "last_kick_reason": "",
                    "uptime_seconds": 0,
                    "is_connection_alive": False,
                    "is_stopped": False,
                    "is_stalled": True,
                    "start_time": now,
                })

        # 3. فحص الخيوط المحجورة في _stalled_threads
        for cid, st_info in list(_stalled_threads.items()):
            th = st_info.get("thread")
            if th and th.is_alive() and th.ident not in registered_idents:
                registered_idents.add(th.ident)
                stalled_list.append({
                    "castle_id": cid,
                    "email": st_info.get("email") or cid,
                    "user_id": st_info.get("user_id") or "",
                    "user_email": _resolve_user_email(st_info.get("user_id", "")),
                    "thread_id": th.ident,
                    "thread_name": th.name,
                    "thread_alive": True,
                    "state": "stalled",
                    "live_category": "stalled",
                    "category_label": "خيط عالق / متعطل",
                    "status_message": f"الخيط تجاوز مهلة الإيقاف ونُقل للحجر عند {st_info.get('stalled_at', '')}",
                    "iteration": 0,
                    "loop_interval_minutes": 60,
                    "next_run_time": None,
                    "reconnect_attempt": 0,
                    "max_reconnect_attempts": 10,
                    "last_kick_reason": "",
                    "uptime_seconds": 0,
                    "is_connection_alive": False,
                    "is_stopped": True,
                    "is_stalled": True,
                    "start_time": now,
                })

    # إحصائيات حية دقيقة
    total_active = len(active_list)
    running_cnt = sum(1 for p in active_list if p.get("live_category") == "running")
    waiting_cnt = sum(1 for p in active_list if p.get("live_category") == "waiting_next_cycle")
    other_login_cnt = sum(1 for p in active_list if p.get("live_category") == "other_device_login")
    reconnecting_cnt = sum(1 for p in active_list if p.get("live_category") == "reconnecting")
    waiting_relogin_cnt = sum(1 for p in active_list if p.get("live_category") == "waiting_relogin")
    starting_cnt = sum(1 for p in active_list if p.get("live_category") == "starting")
    stalled_cnt = len(stalled_list)

    summary = {
        "total_active": total_active,
        "running": running_cnt,
        "waiting_next_cycle": waiting_cnt,
        "other_device_login": other_login_cnt,
        "reconnecting": reconnecting_cnt,
        "waiting_relogin": waiting_relogin_cnt,
        "starting": starting_cnt,
        "stalled": stalled_cnt,
        "stalled_count": stalled_cnt,
        # Title-case aliases for DISPATCH.md specification
        "Running": running_cnt,
        "Waiting for Next Cycle": waiting_cnt,
        "Other Device Login": other_login_cnt,
        "Reconnecting": reconnecting_cnt,
        "Waiting for Re-login": waiting_relogin_cnt,
        "Starting": starting_cnt,
        # Backward compatibility aliases
        "waiting": waiting_cnt,
        "other_login": other_login_cnt,
    }

    # التصفية والبحث
    filtered_list = list(active_list)

    # 1. تصفية الحالة
    if status and str(status).strip().lower() not in ("all", ""):
        st_norm = str(status).strip().lower()
        if st_norm in ("waiting", "waiting_next_cycle"):
            filtered_list = [p for p in filtered_list if p.get("live_category") == "waiting_next_cycle"]
        elif st_norm in ("other_login", "other_device_login"):
            filtered_list = [p for p in filtered_list if p.get("live_category") == "other_device_login"]
        elif st_norm == "stalled":
            filtered_list = list(stalled_list)
        else:
            filtered_list = [p for p in filtered_list if p.get("live_category") == st_norm]

    # 2. البحث النصي
    if search and str(search).strip():
        q = str(search).strip().lower()
        filtered_list = [
            p for p in filtered_list
            if (
                q in str(p.get("email", "")).lower()
                or q in str(p.get("castle_id", "")).lower()
                or q in str(p.get("user_email", "")).lower()
                or q in str(p.get("user_id", "")).lower()
                or q in str(p.get("status_message", "")).lower()
                or q in str(p.get("current_step", "")).lower()
            )
        ]

    # ترتيب العمليات: العمليات المتأثرة بدخول آخر أولاً، ثم إعادة الاتصال، ثم الشغالة
    def _sort_priority(p: Dict[str, Any]) -> int:
        cat = p.get("live_category", "")
        if cat == "other_device_login":
            return 0
        if cat == "waiting_relogin":
            return 1
        if cat == "reconnecting":
            return 2
        if cat == "running":
            return 3
        if cat == "starting":
            return 4
        if cat == "waiting_next_cycle":
            return 5
        return 6

    filtered_list.sort(key=lambda p: (_sort_priority(p), -p.get("uptime_seconds", 0)))

    # الترقيم الحقيقي (Pagination Slice)
    total_count = len(filtered_list)
    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_processes = filtered_list[start_idx:end_idx]
    has_more = page < total_pages

    # ── فحص واستخراج الـ IP الحقيقي الفعلي للمقبس والعملية (Runtime Socket IP) لنتائج الصفحة الحالية فقط ──
    for p in paginated_processes:
        real_ip = p.get("real_ip")
        if not real_ip:
            try:
                from proxy import get_proxy_ip_for_email
                em = p.get("email") or ""
                real_ip = get_proxy_ip_for_email(em)
            except Exception:
                real_ip = "direct"
        p["proxy_ip"] = real_ip
        p["real_ip"] = real_ip

    return {
        "status": "success",
        "source": "live_threads_memory",
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "total_active": total_active,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_more": has_more,
        "processes": paginated_processes,
        "items": paginated_processes,
        "stalled_processes": stalled_list,
    }


# ── مسارات إدارة وفحص البروكسيات للمشرف ────────────────────────
@app.get("/api/admin/proxies")
def get_admin_proxies(admin: Dict[str, Any] = Depends(require_super_admin)):
    """استعلام قائمة البروكسيات مع عدد القلاع المربوطة بكل IP وتفاصيلها للمشرف."""
    from proxy import proxy_status
    return proxy_status()


@app.post("/api/admin/proxies/test")
async def test_admin_proxy(payload: Dict[str, str], admin: Dict[str, Any] = Depends(require_super_admin)):
    """فحص نفق SOCKS5 لعنوان IP معين وقياس البينج فورا."""
    proxy_url = payload.get("proxy_url", "")
    from proxy import test_single_proxy
    return await test_single_proxy(proxy_url)


@app.get("/api/admin/network-mode")
def get_admin_network_mode(admin: Dict[str, Any] = Depends(require_super_admin)):
    """استعلام نمط الشبكة المعتمد (residential أو free أو direct)."""
    from proxy import get_network_mode, is_proxy_enabled, proxy_status
    status = proxy_status()
    return {
        "status": "success",
        "network_mode": get_network_mode(),
        "enabled": is_proxy_enabled(),
        "total_proxies": status.get("total_proxies", 0),
        "residential_count": status.get("residential_count", 0),
        "free_count": status.get("free_count", 0),
        "active_pool_name": status.get("active_pool_name", ""),
        "total_bound_castles": status.get("total_bound_castles", 0),
        "total_bound_users": status.get("total_bound_users", 0),
    }


@app.post("/api/admin/network-mode/toggle")
def toggle_admin_network_mode(payload: Dict[str, Any], admin: Dict[str, Any] = Depends(require_super_admin)):
    """
    تبديل نمط الاتصال بين:
    - 'residential': بروكسيات سكنية مدفوعة معتمدة (Static Residential).
    - 'free': بروكسيات مجانية احتياطية (Free Datacenter).
    - 'direct': استخدام IP السيرفر مباشرة لكل الاتصالات.
    """
    mode = str(payload.get("mode", "")).strip().lower()
    if mode not in ("direct", "socks5", "residential", "free"):
        raise HTTPException(status_code=400, detail="نمط الشبكة غير صالح (يجب أن يكون residential أو free أو direct)")

    from proxy import set_network_mode
    active_mode = set_network_mode(mode)

    if active_mode == "residential":
        label = "البروكسيات السكنية المدفوعة (Static Residential)"
    elif active_mode == "free":
        label = "البروكسيات المجانية الاحتياطية (Free Datacenter)"
    else:
        label = "IP السيرفر المباشر"

    return {
        "status": "success",
        "network_mode": active_mode,
        "message": f"تم تفعيل نمط {label} بنجاح"
    }




def _verify_merchant_access_to_user(admin: Dict[str, Any], target_user: Optional[Dict[str, Any]]):
    """التحقق من أن التاجر لا يدير إلا مستخدمي الدومين التابع له فقط."""
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if admin.get("is_merchant_admin"):
        tenant_domains = [clean_domain(d) for d in admin.get("merchant_tenant", {}).get("domains", [])]
        user_domain = clean_domain(target_user.get("tenant_domain", ""))
        if user_domain not in tenant_domains:
            raise HTTPException(status_code=403, detail="غير مصرح لك بإدارة هذا المستخدم خارج نطاق دومينك")


@app.get("/api/admin/merchants/overview")
def get_admin_merchants_overview(admin: Dict[str, Any] = Depends(require_super_admin)):
    """جلب إحصائيات التجار الشاملة للمشرف الأعلى حصرياً."""
    merchants = get_all_merchants()
    overview = db.get_merchants_overview_stats(merchants)
    return {
        "status": "success",
        "merchants": overview
    }


@app.get("/api/admin/users")
def get_admin_users(admin: Dict[str, Any] = Depends(require_admin)):
    """جلب جميع المستخدمين وقلاعهم من SQLite (مع تصفية التاجر إن كان مشرف تاجر)."""
    if admin.get("is_merchant_admin"):
        tenant_domains = admin.get("merchant_tenant", {}).get("domains", [])
        users = db.get_all_users_with_castles(tenant_domains=tenant_domains)
    else:
        users = db.get_all_users_with_castles()
    return {"users": users}


@app.get("/api/admin/users-castles")
def get_admin_users_castles(admin: Dict[str, Any] = Depends(require_super_admin)):
    """جلب جميع المستخدمين مع كافة قلاعهم للمشرف الأعلى حصرياً على الدومين الرئيسي."""
    users = db.get_all_users()
    all_castles = db.get_all_castles()

    castles_by_user: Dict[str, List[Dict[str, Any]]] = {}
    for c in all_castles:
        cid = c.get("castle_id", "")
        uid = str(c.get("user_id", "")).strip()
        real_st = _get_real_status(cid)
        if real_st == "error" or c.get("conn_state") == "error" or c.get("state") == "error":
            c["state"] = "error"
            c["conn_state"] = "error"
        else:
            c["state"] = real_st
            c["conn_state"] = real_st
            if real_st != "idle" and not c.get("conn_message"):
                c["conn_message"] = "البوت يعمل الآن..."
            elif real_st == "idle" and c.get("conn_message") in ("running", "connected", "waiting", "reconnecting"):
                c["conn_message"] = "جاهز للتشغيل"

        if uid:
            if uid not in castles_by_user:
                castles_by_user[uid] = []
            castles_by_user[uid].append(c)

    result = []
    for u in users:
        uid = str(u.get("uid", "")).strip()
        u_email = str(u.get("email", "")).strip().lower()
        u_castles = castles_by_user.get(uid) or castles_by_user.get(u_email) or []

        seen_cids = set()
        unique_castles = []
        for c in u_castles:
            cid = c.get("castle_id")
            if cid and cid not in seen_cids:
                seen_cids.add(cid)
                unique_castles.append(c)

        is_super = u.get("role") == "admin" and u_email == "ibraboths@gmail.com"
        is_banned = bool(u.get("is_banned"))

        running_cnt = sum(1 for c in unique_castles if c.get("state") in ("running", "waiting", "reconnecting", "connected"))

        u_data = {
            "uid": uid,
            "email": u.get("email", ""),
            "display_name": u.get("display_name") or u.get("email", "").split("@")[0],
            "role": u.get("role", "user"),
            "is_banned": is_banned,
            "created_at": u.get("created_at", ""),
            "tenant_domain": u.get("tenant_domain", ""),
            "subscription": {
                "plan_id": "super_admin_unlimited" if is_super else u.get("plan_id", "basic"),
                "plan_name": "باقة المشرف الأعلى" if is_super else u.get("plan_name", "باقة أساسية"),
                "status": "active" if is_super else ("suspended" if is_banned else u.get("subscription_status", "active")),
                "expires_at": "2099-01-01T00:00:00Z" if is_super else u.get("subscription_expires_at", ""),
                "max_castles_allowed": 999999 if is_super else u.get("max_castles_allowed", 0),
            },
            "castles": unique_castles,
            "castles_count": len(unique_castles),
            "running_count": running_cnt,
        }
        result.append(u_data)

    return {"users": result}


@app.get("/api/admin/users-castles/summary")
def get_admin_users_castles_summary(page: Optional[int] = Query(None, ge=1), page_size: Optional[int] = Query(None, ge=1, le=500), search: Optional[str] = Query(None), filter_status: Optional[str] = Query(None), admin: Dict[str, Any] = Depends(require_admin)):
    """جلب ملخص مرقم وخفيف لجميع المستخدمين مع إحصائيات القلاع (<60 KB) لدعم Master-Detail Lazy Loading."""
    if hasattr(page, "default"):
        page = page.default
    if hasattr(page_size, "default"):
        page_size = page_size.default
    if hasattr(search, "default"):
        search = search.default
    if hasattr(filter_status, "default"):
        filter_status = filter_status.default

    tenant_domains = None
    if admin.get("is_merchant_admin"):
        tenant_domains = [d.lower() for d in admin.get("merchant_tenant", {}).get("domains", [])]

    is_paginated = (page is not None or page_size is not None)
    # جلب البيانات المرقمة من قاعدة البيانات مباشرة مع عزل التجار والبحث والتصفية
    res = db.get_admin_castles_paginated(
        page=page,
        page_size=page_size,
        search=search or "",
        filter_status=filter_status or "all",
        tenant_domains=tenant_domains,
    )

    users_list = res.get("items") or res.get("users") or []
    for u in users_list:
        previews = u.get("castle_previews") or []
        for prev in previews:
            cid = prev.get("id") or prev.get("castle_id")
            if cid:
                real_st = _get_real_status(cid)
                if real_st != "idle":
                    prev["state"] = real_st
                    prev["conn_state"] = real_st
        # تحديث running_count بالاعتماد على الحالة الحية إن وُجدت
        live_running = sum(1 for p in previews if p.get("state") in ("running", "waiting", "reconnecting", "connected"))
        if live_running > u.get("running_count", 0):
            u["running_count"] = live_running
            u["active_count"] = live_running

    response_data = {
        "status": "success",
        "users": users_list,
        "total": res.get("total", len(users_list)),
        "total_count": res.get("total_count", len(users_list)),
        "page": res.get("page", 1),
        "page_size": res.get("page_size", len(users_list)),
        "total_pages": res.get("total_pages", 1),
        "has_more": res.get("has_more", False),
        "summary_stats": res.get("summary_stats", {
            "total_users": len(users_list),
            "total_castles": sum(u.get("castles_count", 0) for u in users_list),
            "total_running": sum(u.get("running_count", 0) for u in users_list),
        }),
    }
    if is_paginated:
        response_data["items"] = users_list
    return response_data


@app.get("/api/admin/users/{uid}/castles")
def get_admin_user_castles(uid: str, admin: Dict[str, Any] = Depends(require_admin)):
    """جلب قلاع مستخدم محدد وإعداداتها الكاملة عند الطلب (Master-Detail Lazy Loading)."""
    target_user = db.get_user(uid)
    if not target_user:
        if admin.get("is_merchant_admin"):
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")
        return {"status": "success", "user_id": uid, "castles": []}
    _verify_merchant_access_to_user(admin, target_user)
    castles = db.get_user_castles(uid)
    for c in castles:
        cid = c.get("castle_id", "")
        real_st = _get_real_status(cid)
        if real_st == "error" or c.get("conn_state") == "error" or c.get("state") == "error":
            c["state"] = "error"
            c["conn_state"] = "error"
        else:
            c["state"] = real_st
            c["conn_state"] = real_st
            if real_st != "idle" and not c.get("conn_message"):
                c["conn_message"] = "البوت يعمل الآن..."
            elif real_st == "idle" and c.get("conn_message") in ("running", "connected", "waiting", "reconnecting"):
                c["conn_message"] = "جاهز للتشغيل"
    return {"status": "success", "user_id": uid, "castles": castles}


@app.post("/api/admin/castles/disable-elf-all")
def disable_elf_all_castles(admin: Dict[str, Any] = Depends(require_super_admin)):
    """إيقاف مهمة الهجوم على العفريت (جعلها False) لكافة القلاع في النظام عبر جميع الدومينات والتجار."""
    updated_count = 0
    total_castles = 0

    try:
        with db.get_connection() as conn:
            cur = conn.execute("SELECT castle_id, config FROM castle_states")
            rows = cur.fetchall()
            total_castles = len(rows)

            for row in rows:
                cid = row["castle_id"]
                raw_cfg = row["config"]
                cfg: Dict[str, Any] = {}
                if isinstance(raw_cfg, str) and raw_cfg.strip():
                    try:
                        cfg = json.loads(raw_cfg)
                    except Exception:
                        cfg = {}
                elif isinstance(raw_cfg, dict):
                    cfg = copy.deepcopy(raw_cfg)

                changed = False

                # 1. فحص march_manager
                mm = cfg.get("march_manager")
                if not isinstance(mm, dict):
                    mm = {}
                    cfg["march_manager"] = mm

                # تعطيل كائن elf
                if "elf" not in mm or not isinstance(mm["elf"], dict):
                    mm["elf"] = {"enabled": False, "formation_id": 1}
                    changed = True
                elif mm["elf"].get("enabled") is not False:
                    mm["elf"]["enabled"] = False
                    changed = True

                # تعطيل combat إذا كان الخيار المختار هو العفريت
                if "combat" in mm and isinstance(mm["combat"], dict):
                    if mm["combat"].get("choice") == "elf" and mm["combat"].get("enabled") is not False:
                        mm["combat"]["enabled"] = False
                        changed = True

                # 2. فحص أي مفاتيح عامة سابقة (legacy)
                if "elf" in cfg and isinstance(cfg["elf"], dict):
                    if cfg["elf"].get("enabled") is not False:
                        cfg["elf"]["enabled"] = False
                        changed = True
                if "elf_boss" in cfg and isinstance(cfg["elf_boss"], dict):
                    if cfg["elf_boss"].get("enabled") is not False:
                        cfg["elf_boss"]["enabled"] = False
                        changed = True

                if changed:
                    new_cfg_json = json.dumps(cfg, ensure_ascii=False)
                    now_str = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "UPDATE castle_states SET config = ?, last_updated = ? WHERE castle_id = ?",
                        (new_cfg_json, now_str, cid)
                    )
                    updated_count += 1

            conn.commit()
    except Exception as ex:
        log.error(f"❌ خطأ أثناء إيقاف مهمة العفريت لجميع القلاع: {ex}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"حدث خطأ في السيرفر: {str(ex)}")

    # 3. تحديث الكائنات الحية للبوتات في الذاكرة فوراً إن كانت تعمل حالياً
    with _lock:
        for cid, mgr in list(_bot_managers.items()):
            try:
                if hasattr(mgr, "config") and isinstance(mgr.config, dict):
                    mm = mgr.config.get("march_manager")
                    if isinstance(mm, dict):
                        if "elf" in mm and isinstance(mm["elf"], dict):
                            mm["elf"]["enabled"] = False
                        if "combat" in mm and isinstance(mm["combat"], dict):
                            if mm["combat"].get("choice") == "elf":
                                mm["combat"]["enabled"] = False
                    if "elf" in mgr.config and isinstance(mgr.config["elf"], dict):
                        mgr.config["elf"]["enabled"] = False
                    if "elf_boss" in mgr.config and isinstance(mgr.config["elf_boss"], dict):
                        mgr.config["elf_boss"]["enabled"] = False
            except Exception as e:
                log.warning(f"⚠️ تعذر تحديث إعدادات الذاكرة للقلعة ({cid}): {e}")

    log.info(f"✅ تم إيقاف مهمة العفريت بنجاح لـ {updated_count} قلعة من إجمالي {total_castles} قلعة.")
    return {
        "status": "success",
        "total_castles": total_castles,
        "updated_count": updated_count,
        "message": f"تم إيقاف مهمة الهجوم على العفريت لجميع القلاع بنجاح ({updated_count} قلعة تم تحديثها من أصل {total_castles})"
    }


@app.post("/api/admin/user/{uid}/subscription")
def update_user_sub(uid: str, req: AdminSubscriptionUpdateRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """تحديث باقة واشتراك المستخدم في SQLite وإيقاف أي قلاع جرى استبعادها بسبب تقليص الباقة."""
    target_user = db.get_user(uid)
    _verify_merchant_access_to_user(admin, target_user)

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

    # فحص وإيقاف أي قلاع جرى إيقافها إذا كانت تعمل حالياً
    sync_res = db.sync_user_castles_and_quota(uid)
    for d_cid in sync_res.get("demoted_ids", []):
        if _is_running(d_cid):
            with _lock:
                _user_stopped.add(d_cid)
                ev = _stop_events.get(d_cid)
                mgr = _bot_managers.get(d_cid)
                if mgr:
                    try: mgr.stop()
                    except Exception: pass
                if ev:
                    ev.set()

    return {"status": "success", "user": db.get_user(uid)}


@app.post("/api/admin/user/{uid}/approve")
def approve_user_endpoint(
    uid: str,
    req: Optional[AdminApproveUserRequest] = None,
    admin: Dict[str, Any] = Depends(require_admin)
):
    """الموافقة على المستخدم وتفعيل باقة الـ 10 حسابات لمدة 3 أيام من المشرف."""
    target_user = db.get_user(uid)
    _verify_merchant_access_to_user(admin, target_user)

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
    admin: Dict[str, Any] = Depends(require_super_admin)
):
    """الموافقة على جميع المستخدمين المعلقين وتفعيل باقة التجربة لهم (حصرياً للمشرف الأعلى)."""
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
    target_user = db.get_user(uid)
    _verify_merchant_access_to_user(admin, target_user)

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
    """حذف مستخدم وجميع قلاعه تماماً من النظام."""
    clean_uid = uid.strip()
    user = db.get_user(clean_uid)
    _verify_merchant_access_to_user(admin, user)
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    # حماية المشرف الأعلى من الحذف
    user_email = str(user.get("email", "")).strip().lower()
    if user.get("role") == "admin" or user_email == "ibraboths@gmail.com":
        if user_email == "ibraboths@gmail.com":
            raise HTTPException(status_code=400, detail="لا يمكن حذف حساب المشرف الأعلى")

    # 1. جلب جميع قلاع المستخدم من قاعدة البيانات
    user_castles = db.get_user_castles(clean_uid)
    target_cids = {c.get("castle_id") for c in user_castles if c.get("castle_id")}
    target_emails = {str(c.get("email", "")).strip().lower() for c in user_castles if c.get("email")}

    # إضافة أي قلاع في الذاكرة تابعة لهذا المستخدم (بالمعرف أو بالبريد)
    with _lock:
        for cid, u in list(_castle_users.items()):
            if u == clean_uid or (user_email and str(u).strip().lower() == user_email):
                target_cids.add(cid)
        for cid, em in list(_castle_emails.items()):
            if str(em).strip().lower() in target_emails:
                target_cids.add(cid)

    # 2. تسجيل القلاع فوراً في قائمة المحذوفات لمنع أي Thread جاري من إعادة تسجيلها أو حفظ حالتها
    with _lock:
        for cid in target_cids:
            _deleted_castles.add(cid)
            _user_stopped.add(cid)

    # 3. إيقاف وانتظار جميع بوتات المستخدم الجارية بمهل زمنية وتنظيف مراجعها
    for cid in target_cids:
        _stop_and_join_bot(cid, timeout=3.0)

    # 4. تنظيف ارتباطات البروكسي للمستخدم وقلاعه في الذاكرة وملف JSON الدائم
    try:
        from proxy.proxy_manager import remove_user_proxy_bindings
        remove_user_proxy_bindings(clean_uid, list(target_emails))
    except Exception as ex:
        log.warning(f"⚠️ تعذر تنظيف ارتباطات البروكسي للمستخدم {clean_uid}: {ex}")

    # تفريغ المعرفات من _deleted_castles و _user_stopped بعد اكتمال الموت
    with _lock:
        for cid in target_cids:
            _deleted_castles.discard(cid)
            _user_stopped.discard(cid)

    # 5. تنظيف ملفات السجلات bot_*.log على القرص
    for em in target_emails:
        try:
            bot_log_path = os.path.join(_LOGS_DIR, f"bot_{em.replace('@','_').replace('.','_')}.log")
            if os.path.exists(bot_log_path):
                os.remove(bot_log_path)
        except Exception as e:
            log.warning(f"⚠️ تعذر حذف ملف اللوق لـ {em}: {e}")

    # 6. تنظيف جلسات الحسابات من session_cache.json
    try:
        from core.session_manager import SessionManager
        sm = SessionManager()
        for em in target_emails:
            sm.remove_session(em)
    except Exception as e:
        log.warning(f"⚠️ تعذر تنظيف session_cache.json: {e}")

    # 7. حذف المستخدم وجميع قلاعه من SQLite
    ok = db.delete_user(clean_uid)
    if not ok:
        raise HTTPException(status_code=500, detail="تعذر حذف المستخدم وقلاعه من قاعدة البيانات")

    # 8. محاولة حذف المستخدم من Firebase Auth أيضاً (حتى لا يتمكن من تسجيل الدخول مجدداً)
    try:
        import firebase_admin
        from firebase_admin import auth as fb_auth
        if firebase_admin._apps:
            fb_auth.delete_user(clean_uid)
            log.info(f"✅ تم حذف المستخدم من Firebase Auth: {clean_uid}")
    except Exception as e:
        log.debug(f"تخطي حذف مستخدم Firebase Auth: {e}")

    return {
        "status": "success",
        "message": f"تم حذف المستخدم وجميع قلاعه ({len(target_cids)} قلعة) بنجاح"
    }


@app.post("/api/admin/castle/{castle_id}/approve")
def approve_castle_endpoint(castle_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """قبول وتفعيل قلعة معلقة في SQLite."""
    c = db.get_castle(castle_id)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")
    _verify_merchant_access_to_user(admin, db.get_user(c.get("user_id", "")))

    ok = db.approve_castle(castle_id)
    if not ok:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")
    return {"status": "success", "message": "تمت الموافقة على القلعة"}


@app.post("/api/admin/castle/{castle_id}/reject")
def reject_castle_endpoint(castle_id: str, req: AdminCastleActionRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """رفض قلعة في SQLite."""
    c = db.get_castle(castle_id)
    if not c:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")
    _verify_merchant_access_to_user(admin, db.get_user(c.get("user_id", "")))

    ok = db.reject_castle(castle_id, req.reason or "تم رفض القلعة من المشرف")
    if not ok:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")
    return {"status": "success", "message": "تم رفض القلعة"}





# ── 🤖 Bot Control Endpoints ──────────────────────────────────────

def _start_bot_internal(req: StartBotRequest) -> bool:
    """تشغيل داخلي للبوت يدعم الاستدعاء المباشر والاستئناف التلقائي (Auto-Resume) مع حجز ذري مانع للتكرار."""
    if isinstance(req.config, str):
        try:
            req.config = json.loads(req.config) if req.config.strip() else {}
        except Exception:
            req.config = {}
    elif not isinstance(req.config, dict):
        req.config = {}

    cid = str(req.castle_id).strip()
    email = str(req.email or "").strip().lower()

    with _lock:
        if cid in _deleted_castles:
            return False
        _user_stopped.discard(cid)
        if _is_running(cid):
            return False
        if cid in _reserved:
            return False
        if email:
            for act_cid, act_em in list(_castle_emails.items()):
                if act_em and act_em.strip().lower() == email:
                    if act_cid in _reserved or _is_running(act_cid):
                        log.warning(f"⚠️ [{email}] محاولة بدء تشغيل مكررة محظورة للحساب. القلعة {act_cid} نشطة بالفعل.")
                        return False

        old_th = _threads.get(cid)
        if old_th and old_th.is_alive():
            old_ev = _stop_events.get(cid)
            if old_ev:
                old_ev.set()

        _threads.pop(cid, None)
        _stop_events.pop(cid, None)
        _reserved.add(cid)
        _castle_emails[cid] = email

    t = threading.Thread(target=_bot_thread, args=(req,), daemon=True, name=f"bot-{cid[:10]}")
    with _lock:
        _threads[cid] = t
    t.start()
    return True


@app.post("/api/internal/save-running-state", dependencies=[Depends(verify_internal_access)])
def save_running_state_endpoint():
    """حفظ قائمة جميع البوتات النشطة حالياً في auto_resume.json قبل عمل ريستارت للسيرفر ووسمها بـ deploying."""
    global _deploy_mode
    _deploy_mode = True

    active_cids = set()
    with _lock:
        for cid, t in _threads.items():
            ev = _stop_events.get(cid)
            if t.is_alive() and cid not in _user_stopped and not (ev and ev.is_set()):
                active_cids.add(cid)
        for cid in list(_castle_users.keys()):
            if cid not in active_cids and cid not in _user_stopped:
                t = _threads.get(cid)
                ev = _stop_events.get(cid)
                if t and t.is_alive() and not (ev and ev.is_set()):
                    active_cids.add(cid)

    # فحص أي threads نشطة تبدأ بـ bot- في بايثون
    for t in threading.enumerate():
        if t.name.startswith("bot-") and t.is_alive():
            if t.name == "auto-resume" or t.name.startswith("sys-"):
                continue
            prefix = t.name[4:]
            castles_match = db.find_castles_by_id_prefix(prefix)
            for cm in castles_match:
                cid = cm.get("castle_id")
                ev = _stop_events.get(cid)
                if cid and cid not in _user_stopped and not (ev and ev.is_set()):
                    active_cids.add(cid)

    saved_list = []
    deploy_msg = "جاري رفع التغييرات إلى السيرفر... سيتم استئناف البوت تلقائياً"
    for cid in active_cids:
        c = db.get_castle_by_id(cid)
        if c:
            uid = c.get("user_id", "")
            saved_list.append({
                "castle_id": cid,
                "user_id": uid,
                "email": c.get("email", ""),
            })
            with _lock:
                _conn_states[cid] = "deploying"
                _reserved.add(cid)
            try:
                update_castle_status_db(uid, cid, "deploying", deploy_msg, conn_state="deploying")
            except Exception:
                pass

    # إيقاف مديري البوتات والمقابس بأمان
    with _lock:
        for cid in active_cids:
            mgr = _bot_managers.get(cid)
            ev = _stop_events.get(cid)
            if mgr:
                try: mgr.stop()
                except Exception: pass
            if ev:
                ev.set()

    auto_resume_file = os.path.join(_ROOT, "auto_resume.json")
    if saved_list:
        with open(auto_resume_file, "w", encoding="utf-8") as f:
            json.dump(saved_list, f, ensure_ascii=False, indent=2)
        log.info(f"💾 [Auto-Resume Prep] تم حفظ حالة {len(saved_list)} بوت نشط ووسمهم بـ deploying لإعادة استئنافهم تلقائياً بعد الريستارت.")
    elif os.path.exists(auto_resume_file):
        try:
            with open(auto_resume_file, "r", encoding="utf-8") as f:
                prev_list = json.load(f)
            if prev_list and isinstance(prev_list, list):
                saved_list = prev_list
                log.info(f"💾 [Auto-Resume Prep] تم الاحتفاظ بـ {len(saved_list)} بوت من ملف auto_resume.json السابق.")
        except Exception:
            pass
    return {"status": "success", "count": len(saved_list), "castles": [x["castle_id"] for x in saved_list]}



@app.get("/api/internal/debug-state", dependencies=[Depends(verify_internal_access)])
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


@app.post("/api/internal/deploy-lock", dependencies=[Depends(verify_internal_access)])
def deploy_lock():
    """
    قفل وضع النشر (Deploy Mode) — يمنع أي مستخدم من تشغيل بوت جديد.
    يُستدعى من deploy.py قبل رفع الملفات وإعادة تشغيل الخدمة.
    """
    global _deploy_mode
    _deploy_mode = True
    log.warning("🔒 [Deploy Lock] وضع النشر مُفعّل — تم تعليق تشغيل أي بوت جديد حتى انتهاء النشر.")
    return {"status": "locked", "deploy_mode": True}


@app.post("/api/internal/deploy-unlock", dependencies=[Depends(verify_internal_access)])
def deploy_unlock():
    """
    فتح وضع النشر (Deploy Mode) — يسمح للمستخدمين بتشغيل البوتات مرة أخرى.
    يُستدعى من deploy.py بعد إعادة تشغيل الخدمة وتأكيد الصحة.
    """
    global _deploy_mode
    _deploy_mode = False
    log.info("🔓 [Deploy Unlock] وضع النشر أُلغي — يمكن للمستخدمين تشغيل البوتات مجدداً.")
    return {"status": "unlocked", "deploy_mode": False}


@app.post("/api/internal/resume-all-from-db", dependencies=[Depends(verify_internal_access)])
def resume_all_from_db():
    """
    استئناف تدريجي آمن لجميع الحسابات المؤهلة:
    تم إلغاء حلقة 0.4 ثانية السريعة بالكامل وتفويض التنفيذ إلى التشغيل التدريجي الآمن (gradual_start)
    مع فاصل عشوائي 5-10 ثوانٍ وخلط الحسابات لمنع أي ضغط على السيرفر أو حظر.
    """
    log.info("🔄 [Resume-All] تم تفويض طلب الاستئناف إلى التشغيل التدريجي الآمن (gradual_start)...")
    return gradual_start()


# ── ══════════════════════════════════════════════════════════════════
# ── أوامر التشغيل/الإيقاف التدريجي الآمن (Gradual Start/Stop/Restart)
# ── ══════════════════════════════════════════════════════════════════

def _interleave_shuffle(castles: list) -> list:
    """
    خلط عشوائي ذكي: يضمن عدم تتالي حسابات نفس المستخدم.
    يجمع الحسابات حسب user_id، يخلط كل مجموعة، ثم يسحب Round-Robin.
    """
    from collections import defaultdict
    groups = defaultdict(list)
    for c in castles:
        groups[c.get("user_id", "unknown")].append(c)
    for g in groups.values():
        random.shuffle(g)
    queues = list(groups.values())
    random.shuffle(queues)
    result = []
    while queues:
        for q in queues:
            if q:
                result.append(q.pop(0))
        queues = [q for q in queues if q]
    return result


def _collect_eligible_castles() -> list:
    """جمع جميع الحسابات المؤهلة للتشغيل (موافق عليها + اشتراك صالح + نشطة + ليست محظورة)."""
    eligible = []
    try:
        all_users = db.get_all_users()
    except Exception as ex:
        log.error(f"❌ [Gradual] فشل جلب المستخدمين: {ex}")
        return eligible

    for user in all_users:
        uid = user.get("uid", "") or user.get("user_id", "")
        if not uid:
            continue
        valid, reason = db.check_user_subscription_db(uid)
        if not valid:
            continue
        try:
            castles = db.get_all_castles(user_id=uid)
        except Exception:
            continue
        for c in castles:
            cid = c.get("castle_id", "")
            if not cid or not c.get("is_active", 1):
                continue
            status = c.get("status", "")
            if status in ("pending", "rejected"):
                continue
            c_st = str(c.get("state", "")).lower()
            conn_st = str(c.get("conn_state", "")).lower()
            if "banned" in conn_st or "banned" in c_st or conn_st == "error":
                continue
            raw_config = c.get("config", {})
            if isinstance(raw_config, str):
                try:
                    raw_config = json.loads(raw_config) if raw_config else {}
                except Exception:
                    raw_config = {}
            eligible.append({
                "castle_id": cid,
                "user_id": uid,
                "email": c.get("email", ""),
                "config": raw_config,
                "loop_interval": c.get("loop_interval", 40)
            })
    return eligible


def _mark_deploying(castle_ids: list):
    """وسم مجموعة من الحسابات بـ deploying في قاعدة البيانات."""
    try:
        with db.get_connection() as conn:
            for cid in castle_ids:
                conn.execute("""
                    UPDATE castle_states
                    SET state = 'deploying', conn_state = 'deploying',
                        conn_message = 'جاري استئناف البوت تدريجياً... (وضع التحديث)'
                    WHERE castle_id = ?
                """, (cid,))
            conn.commit()
    except Exception as ex:
        log.warning(f"⚠️ [Gradual] خطأ أثناء وسم deploying: {ex}")


def _reset_deploying_to_idle():
    """تصفير الحسابات المتبقية في وضع deploying إلى idle."""
    try:
        with db.get_connection() as conn:
            conn.execute("""
                UPDATE castle_states
                SET state = 'idle', conn_state = 'idle',
                    conn_message = 'تم إلغاء التشغيل التدريجي'
                WHERE conn_state = 'deploying' OR state = 'deploying'
            """)
            conn.commit()
    except Exception as ex:
        log.warning(f"⚠️ [Gradual] خطأ أثناء تصفير deploying: {ex}")


def _gradual_start_worker(castles: list):
    """Worker thread: يشغل الحسابات واحداً تلو الآخر بفاصل عشوائي 5-10 ثوانٍ."""
    global _gradual_running, _deploy_mode
    started = 0
    skipped = 0
    try:
        total = len(castles)
        for i, c in enumerate(castles):
            if _gradual_cancel.is_set():
                log.info(f"🛑 [Gradual] تم إلغاء التشغيل التدريجي بعد {started} حساب (من أصل {total})")
                break

            cid = c["castle_id"]
            uid = c["user_id"]

            if _is_running(cid):
                skipped += 1
                continue

            with _lock:
                _user_stopped.discard(cid)

            try:
                raw_cfg = c.get("config", {})
                if isinstance(raw_cfg, str):
                    try:
                        raw_cfg = json.loads(raw_cfg) if raw_cfg else {}
                    except Exception:
                        raw_cfg = {}
                req_obj = StartBotRequest(
                    castle_id=cid,
                    user_id=uid,
                    email=c.get("email", ""),
                    config=raw_cfg,
                    loop_interval=c.get("loop_interval", 40)
                )
                ok = _start_bot_internal(req_obj)
                if ok:
                    started += 1
                    log.info(f"✅ [Gradual] ({started}/{total}) بدأ: {c.get('email', cid[:8])}")
                else:
                    skipped += 1
            except Exception as ex:
                log.warning(f"⚠️ [Gradual] فشل {cid}: {ex}")

            # انتظار عشوائي 5-10 ثوانٍ قبل الحساب التالي
            if i < total - 1 and not _gradual_cancel.is_set():
                delay = random.randint(5, 10)
                # نوم مجزأ ليستجيب للإلغاء بسرعة
                for _ in range(delay):
                    if _gradual_cancel.is_set():
                        break
                    time.sleep(1)

        log.info(f"🎉 [Gradual] اكتمل: {started} بوت شُغِّل، {skipped} تم تخطيه، من أصل {total}")
    finally:
        # ضمان فتح القفل وتصفير الحالة دائماً
        _gradual_running = False
        _deploy_mode = False
        _gradual_cancel.clear()
        log.info("🔓 [Gradual] تم فتح قفل النشر وإنهاء العملية التدريجية.")


@app.post("/api/internal/gradual-start", dependencies=[Depends(verify_internal_access)])
def gradual_start():
    """
    تشغيل تدريجي عشوائي لجميع الحسابات المؤهلة.
    - deploy_lock تلقائي
    - وسم deploying لكل حساب
    - خلط عشوائي (لا تتتالى حسابات نفس المستخدم)
    - 5-10 ثوانٍ عشوائية بين كل حساب
    """
    global _gradual_running, _deploy_mode

    if _gradual_running:
        return {"status": "rejected", "message": "عملية تشغيل تدريجي جارية بالفعل — انتظر انتهاءها أو ألغِها أولاً"}

    # جمع الحسابات المؤهلة
    eligible = _collect_eligible_castles()
    if not eligible:
        return {"status": "empty", "message": "لا توجد حسابات مؤهلة للتشغيل"}

    # تفعيل الحماية
    _gradual_running = True
    _deploy_mode = True
    _gradual_cancel.clear()

    # وسم deploying
    _mark_deploying([c["castle_id"] for c in eligible])

    # خلط عشوائي
    shuffled = _interleave_shuffle(eligible)

    # تشغيل في الخلفية
    threading.Thread(target=_gradual_start_worker, args=(shuffled,), daemon=True, name="gradual-start").start()

    return {
        "status": "started",
        "total": len(shuffled),
        "message": f"بدأ التشغيل التدريجي لـ {len(shuffled)} حساب (5-10 ثوانٍ بين كل حساب)"
    }


@app.post("/api/internal/stop-all", dependencies=[Depends(verify_internal_access)])
def stop_all_bots():
    """
    إيقاف جميع البوتات النشطة فوراً وتصفير حالتها.
    - يلغي أي تشغيل تدريجي جاري
    - يوقف كل البوتات
    - يصفر الكل في DB
    """
    global _gradual_running, _deploy_mode

    # إلغاء أي تشغيل تدريجي جاري
    _gradual_cancel.set()
    _gradual_running = False

    stopped_count = 0
    with _lock:
        all_cids = list(set(list(_threads.keys()) + list(_stop_events.keys()) + list(_bot_managers.keys())))

    for cid in all_cids:
        _stop_and_join_bot(cid, timeout=1.0)
        stopped_count += 1

    # تصفير الكل في DB
    try:
        with db.get_connection() as conn:
            conn.execute("""
                UPDATE castle_states
                SET state = 'idle', conn_state = 'idle',
                    conn_message = 'تم إيقاف البوت بواسطة المشرف'
                WHERE conn_state NOT IN ('sealed_banned', 'banned') AND state NOT IN ('banned')
            """)
            conn.commit()
    except Exception as ex:
        log.warning(f"⚠️ [Stop-All] خطأ DB: {ex}")

    _deploy_mode = False
    _gradual_cancel.clear()
    log.info(f"🛑 [Stop-All] تم إيقاف {stopped_count} بوت وتصفير قاعدة البيانات.")
    return {"status": "stopped", "count": stopped_count, "message": f"تم إيقاف {stopped_count} بوت بنجاح"}


@app.post("/api/internal/cancel-start-queue", dependencies=[Depends(verify_internal_access)])
def cancel_start_queue():
    """
    إلغاء التشغيل التدريجي الجاري — الحسابات التي بدأت تبقى شغالة.
    - يصفر الحسابات المتبقية في deploying إلى idle
    - يفتح قفل النشر
    """
    global _gradual_running, _deploy_mode

    was_running = _gradual_running
    _gradual_cancel.set()
    _gradual_running = False
    _deploy_mode = False

    # تصفير المتبقين
    _reset_deploying_to_idle()

    if was_running:
        log.info("🛑 [Cancel-Queue] تم إلغاء التشغيل التدريجي. الحسابات الشغالة مستمرة.")
        return {"status": "cancelled", "message": "تم إلغاء التشغيل التدريجي. الحسابات التي بدأت بالفعل مستمرة في العمل."}
    else:
        _reset_deploying_to_idle()
        log.info("ℹ️ [Cancel-Queue] لا توجد عملية تشغيل تدريجي جارية. تم تصفير أي حسابات deploying.")
        return {"status": "no_op", "message": "لا توجد عملية تشغيل تدريجي جارية حالياً. تم تصفير أي حسابات متبقية."}


@app.post("/api/internal/restart-all", dependencies=[Depends(verify_internal_access)])
def restart_all_bots():
    """
    إيقاف كل البوتات + إعادة تشغيل تدريجي بالتحديثات الجديدة.
    - يحفظ قائمة البوتات الشغالة
    - يوقفها جميعاً
    - يعيد تشغيلها تدريجياً (5-10 ثوانٍ + خلط عشوائي)
    """
    global _gradual_running, _deploy_mode

    if _gradual_running:
        return {"status": "rejected", "message": "عملية تشغيل تدريجي جارية بالفعل — انتظر انتهاءها أو ألغِها أولاً"}

    # جمع البوتات الشغالة حالياً
    running_castles = []
    with _lock:
        all_cids = list(set(list(_threads.keys()) + list(_stop_events.keys()) + list(_bot_managers.keys())))
    for cid in all_cids:
        if _is_running(cid):
            uid = _castle_users.get(cid, "")
            email = _castle_emails.get(cid, "")
            running_castles.append({
                "castle_id": cid,
                "user_id": uid,
                "email": email,
                "config": {},
                "loop_interval": 40
            })

    if not running_castles:
        return {"status": "empty", "message": "لا توجد بوتات شغالة حالياً لإعادة تشغيلها"}

    # تفعيل الحماية
    _gradual_running = True
    _deploy_mode = True
    _gradual_cancel.clear()

    # إيقاف الكل أولاً مع انتظار الخيوط
    for cid in all_cids:
        _stop_and_join_bot(cid, timeout=1.0)

    # إعادة قراءة config الحسابات من DB
    refreshed = []
    for rc in running_castles:
        cid = rc["castle_id"]
        uid = rc["user_id"]
        try:
            castles_db = db.get_all_castles(user_id=uid)
            for c in castles_db:
                if c.get("castle_id") == cid:
                    raw_cfg = c.get("config", {})
                    if isinstance(raw_cfg, str):
                        try:
                            raw_cfg = json.loads(raw_cfg) if raw_cfg.strip() else {}
                        except Exception:
                            raw_cfg = {}
                    refreshed.append({
                        "castle_id": cid,
                        "user_id": uid,
                        "email": c.get("email", rc["email"]),
                        "config": raw_cfg,
                        "loop_interval": c.get("loop_interval", 40)
                    })
                    break
            else:
                refreshed.append(rc)
        except Exception:
            refreshed.append(rc)

    # وسم deploying + انتظار قصير ليغلق البوتات
    _mark_deploying([c["castle_id"] for c in refreshed])

    def _restart_worker():
        # انتظار 5 ثوانٍ لإغلاق البوتات بالكامل
        time.sleep(5)
        # إزالة من _user_stopped لتشغيلها مرة أخرى
        with _lock:
            for c in refreshed:
                _user_stopped.discard(c["castle_id"])
        _gradual_start_worker(_interleave_shuffle(refreshed))

    threading.Thread(target=_restart_worker, daemon=True, name="gradual-restart").start()

    return {
        "status": "restarting",
        "total": len(refreshed),
        "message": f"جاري إعادة تشغيل {len(refreshed)} بوت تدريجياً (5-10 ثوانٍ بين كل حساب)"
    }


@app.post("/api/internal/direct-start", dependencies=[Depends(verify_internal_access)])
def internal_direct_start(req: StartBotRequest):
    """
    تشغيل مباشر للبوت بدون JWT — للاستخدام الداخلي فقط من سكريبتات الاستئناف الطارئ.
    يُقبل فقط من localhost (127.0.0.1) أو مع توكن داخلي صالح.
    """
    with _lock:
        _user_stopped.discard(req.castle_id)
    ok = _start_bot_internal(req)
    if ok:
        log.info(f"✅ [Direct-Start] {req.email} ({req.castle_id[:8]})")
        return {"status": "started", "castle_id": req.castle_id}
    else:
        return {"status": "already_running", "castle_id": req.castle_id}



@app.post("/api/bot/start")
def start_bot(req: StartBotRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    """تشغيل بوت لقلعة معينة مع التحقق من صلاحية الاشتراك محلياً في SQLite."""
    global _deploy_mode
    caller_uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)

    # 🔒 رفض أي تشغيل أثناء وضع النشر (Deploy Mode) — حماية من تشغيل مزدوج
    if _deploy_mode:
        raise HTTPException(
            status_code=503,
            detail="🚧 السيرفر في وضع التحديث حالياً. يرجى الانتظار قليلاً حتى يكتمل النشر وتستأنف البوتات تلقائياً."
        )

    if not is_admin and caller_uid != req.user_id:
        raise HTTPException(status_code=403, detail="غير مصرح بتشغيل قلاع مستخدم آخر")

    # 1. استخراج بيانات القلعة المعتمدة من SQLite وفرض البريد الحقيقي لمنع انتحال الجلسات
    c_info = db.get_castle_by_id(req.castle_id, None if is_admin else caller_uid)
    if not c_info:
        raise HTTPException(status_code=404, detail="القلعة غير موجودة")

    # 🛡️ P0 Security: استبدال بريد الحساب بالبريد المعتمد للقلعة من قاعدة البيانات فوراً
    if c_info.get("email"):
        req.email = c_info["email"]

    # 2. التحقق من صلاحية الاشتراك وحظر الحساب محلياً في SQLite
    valid, reason = db.check_user_subscription_db(req.user_id)
    if not valid:
        log.warning(f"🛑 [{req.email}] تم رفض بدء التشغيل محلياً: {reason}")
        db.toggle_castle_active(req.castle_id, is_active=False, user_id=req.user_id)
        update_castle_status_db(req.user_id, req.castle_id, "idle", f"متوقف: {reason}")
        raise HTTPException(status_code=403, detail=f"لا يمكن تشغيل البوت: {reason}")

    # 3. التحقق من أن القلعة مفعلة وليست معلقة أو مجمدة
    if not is_admin and (not c_info.get("is_active") or c_info.get("state") == "pending"):
        raise HTTPException(
            status_code=403,
            detail="لا يمكن تشغيل هذه القلعة لأنها معلقة أو غير مفعلة ضمن باقتك الحالية"
        )

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
    is_admin = is_super_admin(current_user)

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

    # إيقاف حتمي مع انتظار الخيط بمهلة زمنية وتنظيف المراجع
    _stop_and_join_bot(matched_cid, timeout=3.0)
    if matched_cid != castle_id:
        _stop_and_join_bot(castle_id, timeout=0.1)

    # تصفير حالة القلعة دائماً في SQLite لضمان عدم بقائها عالقة
    try:
        effective_uid = owner_uid or caller_uid
        update_castle_status_db(effective_uid, matched_cid, "idle", "تم إيقاف البوت بواسطة المستخدم", conn_state="idle")
        if matched_cid != castle_id:
            update_castle_status_db(effective_uid, castle_id, "idle", "تم إيقاف البوت بواسطة المستخدم", conn_state="idle")
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء تصفير حالة القلعة محلياً: {e}")

    log.info(f"⏹️  تم إيقاف القلعة {matched_cid[:16]} بواسطة {caller_uid}")
    return {"status": "stopped", "castle_id": matched_cid}


@app.post("/api/bot/stop-user/{user_id}")
def stop_user_bots(user_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """إيقاف جميع بوتات المستخدم فوراً دفعة واحدة (مسموح للمشرف وللمستخدم نفسه)."""
    caller_uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user)
    if not is_admin and caller_uid != user_id:
        raise HTTPException(status_code=403, detail="غير مصرح بإيقاف قلاع مستخدم آخر")

    stopped = []
    with _lock:
        targets = [cid for cid, uid in _castle_users.items() if uid == user_id]

    for cid in targets:
        _stop_and_join_bot(cid, timeout=3.0)
        stopped.append(cid)
        try:
            update_castle_status_db(user_id, cid, "idle", "تم إيقاف البوت بواسطة المستخدم", conn_state="idle")
        except Exception:
            pass

    try:
        user_castles = db.get_user_castles(user_id)
        for c in user_castles:
            cid = c.get("castle_id")
            if cid:
                with _lock:
                    _user_stopped.add(cid)
                update_castle_status_db(user_id, cid, "idle", "تم إيقاف البوت بواسطة المستخدم", conn_state="idle")
    except Exception as ex:
        log.debug(f"stop_user_bots db cleanup: {ex}")

    log.info(f"🛑 [Batch Stop] تم إيقاف جميع بوتات المستخدم {user_id} ({len(stopped)} نشط)")
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


@app.post("/api/bot/conn-state", dependencies=[Depends(verify_internal_access)])
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
def get_local_castle(identifier: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """استرجاع بيانات وحالة قلعة معينة من قاعدة بيانات SQLite المحلية بلمح البصر مع التحقق الأمني وتجريد كلمة المرور."""
    c = db.get_castle(identifier)
    if not c:
        raise HTTPException(status_code=404, detail="Castle not found in local database")

    # 🛡️ P0 Security: تجريد كلمة المرور والبيانات الخام دائماً وأبداً قبل أي معالجة أو إرجاع
    c.pop("password", None)
    c.pop("raw_json", None)

    caller_uid = current_user.get("uid", "")
    is_admin = is_super_admin(current_user) or current_user.get("role") in ("admin", "merchant_admin")
    if not is_admin and str(c.get("user_id", "")).strip() != str(caller_uid).strip():
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to access this castle")

    return {"castle": c}


@app.get("/api/castle-data/{email}")
async def get_castle_data(email: str, user_id: Optional[str] = None, castle_id: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    جلب بيانات القلعة والموارد الحية بالاتصال بسيرفر اللعبة ومزامنتها مع SQLite المحلية.
    """
    caller_uid = current_user.get("uid", "")
    caller_email = str(current_user.get("email", "")).strip().lower()
    target_email = str(email).strip().lower()
    is_admin = is_super_admin(current_user) or current_user.get("role") in ("admin", "merchant_admin")

    # 🛡️ P0 Security: حماية BOLA/IDOR — التحقق من أن الإيميل يملكه المستخدم أو يملك قلعته
    if not is_admin:
        matches_user_email = (target_email == caller_email)
        user_castles = db.get_user_castles(caller_uid)
        owns_castle_email = any(str(c.get("email", "")).strip().lower() == target_email for c in user_castles)

        if not matches_user_email and not owns_castle_email:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: You do not have permission to access data for castle '{email}'"
            )
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

        from core.resources_calc import calculate_unprotected_resources
        calc_res = calculate_unprotected_resources(reslist, saferes, blist)
        unprot = calc_res["unprotected"]
        safe   = calc_res["safe"]

        food    = int(float(reslist.get("1002", saferes.get("1002", 0))))
        wood    = int(float(reslist.get("1003", saferes.get("1003", 0))))
        iron    = int(float(reslist.get("1004", saferes.get("1004", 0))))
        diamond = int(float(reslist.get("1005", saferes.get("1005", 0))))
        gold    = int(float(base_info.get("gold", reslist.get("1006", saferes.get("1006", 0)))))
        stamina = int(float(base_info.get("health", 100)))
        # استخراج الإحداثيات المعتمدة للقلعة من cityCtrl.cinfo.pos كأولوية أولى مطابقة لسورس اللعبة
        cinfo_block = city_ctrl.get("cinfo", {}) if isinstance(city_ctrl, dict) else {}
        pos = cinfo_block.get("pos", {}) if isinstance(cinfo_block, dict) else {}
        if not pos or not pos.get("x"):
            pos = base_info.get("sourcePos", {}) if isinstance(base_info, dict) else {}
        coords  = {"x": int(pos.get("x", 0) or 0), "y": int(pos.get("y", 0) or 0)}

        avatar_raw = str(base_info.get("avatar", "") or "")
        image_id = int(base_info.get("imageId", 0) or 0)

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
            "food":                 food,
            "wood":                 wood,
            "iron":                 iron,
            "diamond":              diamond,
            "gold":                 gold,
            "stamina":              stamina,
            "unprotected_food":     unprot["food"],
            "unprotected_wood":     unprot["wood"],
            "unprotected_iron":     unprot["iron"],
            "unprotected_diamond":  unprot["diamond"],
            "safe_food":            safe["food"],
            "safe_wood":            safe["wood"],
            "safe_iron":            safe["iron"],
            "safe_diamond":         safe["diamond"],
            "last_updated":         now_iso,
        }
        cinfo_data = {
            "lord_name":    str(base_info.get("nickName", email.split("@")[0])),
            "lord_power":   int(fc_info.get("totalFc", 0)),
            "castle_level": max(1, castle_lv),
            "walls_level":  walls_lv,
            "server_id":    int(base_info.get("partition", 1)) if str(base_info.get("partition", "")).isdigit() else 1,
            "coordinates":  coords,
            "uid":          str(base_info.get("uid", getattr(account, "user_id", ""))),
            "avatar":       avatar_raw,
            "image_id":     image_id,
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
            "avatar":       avatar_raw,
            "image_id":     image_id,
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
    log_path = os.path.join(_LOGS_DIR, "bot_errors.log")
    if not os.path.exists(log_path):
        legacy = os.path.join(_ROOT, "bot_errors.log")
        if os.path.exists(legacy):
            log_path = legacy
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
    is_admin = is_super_admin(current_user)

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
        p = _get_bot_log_path(email)
        if os.path.exists(p):
            log_path = p

    if not log_path or not os.path.exists(log_path):
        return {"logs": [], "count": 0, "message": "لا توجد سجلات محفوظة لهذا الحساب بعد (يتم حفظ السجلات أثناء تشغيل البوت لمدة 24 ساعة)"}

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
    """WebSocket للـ logs المباشرة لبوت قلعة معينة مع كشف فوري لانقطاع العميل."""
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
        p = _get_bot_log_path(email)
        if os.path.exists(p):
            log_path = p

    if log_path and os.path.exists(log_path):
        recent = _tail_file(log_path, n_lines=35)
        for r in recent:
            try:
                await websocket.send_text(r)
            except Exception:
                return

    disconnect_task = asyncio.create_task(websocket.receive())
    try:
        while True:
            if disconnect_task.done():
                break

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

            if disconnect_task.done():
                break

            done, _ = await asyncio.wait([disconnect_task], timeout=0.3)
            if done:
                break
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        log.debug(f"WebSocket error: {e}")
    finally:
        if not disconnect_task.done():
            disconnect_task.cancel()
        log.info(f"📡 WebSocket logs disconnected: {castle_id[:16]}")


@app.websocket("/ws/status/{castle_id}")
async def ws_status(websocket: WebSocket, castle_id: str):
    """WebSocket لمراقبة حالة البوت الحقيقية في الوقت الفعلي مع كشف فوري لانقطاع العميل."""
    await websocket.accept()

    last_status = _get_real_status(castle_id)
    try:
        await websocket.send_text(last_status)
    except Exception:
        return

    disconnect_task = asyncio.create_task(websocket.receive())
    try:
        while True:
            if disconnect_task.done():
                break

            done, _ = await asyncio.wait([disconnect_task], timeout=0.8)
            if done:
                break

            current = _get_real_status(castle_id)
            if current != last_status:
                last_status = current
                await websocket.send_text(current)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        pass
    finally:
        if not disconnect_task.done():
            disconnect_task.cancel()


def _collect_user_statuses_snapshot(user_id: str, force_refresh_castles: bool = False) -> Dict[str, str]:
    """جمع حالات قلاع المستخدم مع كاش محلي لمعرفات القلاع لتفادي استنزاف SQLite."""
    res = {}
    with _lock:
        cached_cids = _user_status_cache.get(user_id)

    if cached_cids is None or force_refresh_castles:
        try:
            castles = db.get_user_castles(user_id)
            cached_cids = {c.get("castle_id"): "idle" for c in castles if c.get("castle_id")}
            with _lock:
                _user_status_cache[user_id] = cached_cids
        except Exception:
            cached_cids = cached_cids or {}

    for cid in list(cached_cids.keys()):
        res[cid] = _get_real_status(cid)
    return res


def _sync_collect_user_statuses(user_id: str) -> Dict[str, str]:
    """جمع حالات جميع قلاع المستخدم بشكل متزامن لنقلها بالكامل إلى Thread Pool."""
    return _collect_user_statuses_snapshot(user_id, force_refresh_castles=True)


@app.websocket("/ws/user-status/{user_id}")
async def ws_user_status(websocket: WebSocket, user_id: str):
    """
    WebSocket موحد لبث حالات جميع قلاع المستخدم:
    - كشف فوري لانقطاع الاتصال (Disconnect Detection) لإنهاء المهمة دون أي هدر.
    - استبدال حلقة الـ 0.8s SQLite Polling بفحص كاش الذاكرة (In-Memory Version Check) لنقل التحديثات فقط عند تغيرها.
    - صفر استعلامات SQLite في وضع الخمول وصفر استنزاف لـ ThreadPoolExecutor.
    """
    await websocket.accept()

    last_data = await asyncio.to_thread(_collect_user_statuses_snapshot, user_id, True)
    try:
        await websocket.send_json(last_data)
    except Exception:
        return

    with _lock:
        last_version = _user_status_versions.get(user_id, 0)

    disconnect_task = asyncio.create_task(websocket.receive())
    last_castles_refresh = time.time()
    try:
        while True:
            if disconnect_task.done():
                break

            done, _ = await asyncio.wait([disconnect_task], timeout=0.8)
            if done:
                break

            with _lock:
                curr_version = _user_status_versions.get(user_id, 0)

            now = time.time()
            force_db = (now - last_castles_refresh > 30.0)
            if curr_version != last_version or force_db:
                last_version = curr_version
                if force_db:
                    last_castles_refresh = now
                curr_data = _collect_user_statuses_snapshot(user_id, force_refresh_castles=force_db)
                if curr_data != last_data:
                    last_data = curr_data
                    await websocket.send_json(curr_data)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        log.debug(f"ws_user_status error: {e}")
    finally:
        if not disconnect_task.done():
            disconnect_task.cancel()


def _handle_auto_resume():
    """استئناف تشغيل البوتات التي كانت شغالة قبل إعادة تشغيل السيرفر تلقائياً وبدون أي وميض أو تأخير في الواجهة."""
    def _bg_resume():
        global _deploy_mode
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

        try:
            if resume_cids:
                _deploy_mode = True  # قفل وضع النشر طوال فترة الاستئناف
                with _lock:
                    for cid in resume_cids:
                        _reserved.add(cid)
                        _conn_states[cid] = "deploying"
                log.info(f"🔒 [Auto-Resume] تم حجز {len(resume_cids)} قلعة فوراً في _reserved — وضع النشر مُفعّل.")

            # إعادة ضبط الحالات العالقة في القاعدة مع استثناء القلاع التي سيتم استئنافها فوراً
            cnt = db.reset_stuck_castles_db(exclude_castle_ids=list(resume_cids) if resume_cids else None)
            if cnt > 0:
                log.info(f"🧹 [Startup Reset] تم تنظيف {cnt} قلعة عالقة من التشغيل السابق.")

            if to_resume and isinstance(to_resume, list):
                total = len(to_resume)
                log.info(f"🔄 [Auto-Resume] استئناف {total} بوت بشكل متدرج (5-10 ثوانٍ عشوائية + خلط عشوائي)...")

                # خلط عشوائي ذكي لمنع تتالي حسابات نفس المستخدم
                shuffled = _interleave_shuffle(to_resume)
                started = 0

                for i, item in enumerate(shuffled):
                    cid = item.get("castle_id", "")
                    uid = item.get("user_id", "")
                    if not cid or not uid:
                        continue
                    try:
                        valid, reason = db.check_user_subscription_db(uid)
                        if not valid:
                            log.warning(f"⏩ [Auto-Resume] تخطي {cid[:8]}: {reason}")
                            with _lock:
                                _reserved.discard(cid)
                                _conn_states.pop(cid, None)
                            update_castle_status_db(uid, cid, "idle", f"متوقف: {reason}", conn_state="idle")
                            continue
                        c = db.get_castle_by_id(cid, uid)
                        if not c or not c.get("is_active", 1):
                            with _lock:
                                _reserved.discard(cid)
                                _conn_states.pop(cid, None)
                            update_castle_status_db(uid, cid, "idle", "غير نشط", conn_state="idle")
                            continue

                        with _lock:
                            _conn_states[cid] = "connected"
                            _castle_users[cid] = uid
                            _castle_emails[cid] = c.get("email", item.get("email", ""))
                        update_castle_status_db(uid, cid, "running", "جاري الاتصال واستئناف العمل...", conn_state="connected")

                        raw_cfg = c.get("config", {})
                        if isinstance(raw_cfg, str):
                            try:
                                raw_cfg = json.loads(raw_cfg) if raw_cfg.strip() else {}
                            except Exception:
                                raw_cfg = {}
                        req = StartBotRequest(
                            castle_id=cid,
                            user_id=uid,
                            email=c.get("email", item.get("email", "")),
                            config=raw_cfg,
                            loop_interval=c.get("loop_interval", 40)
                        )
                        with _lock:
                            _reserved.discard(cid)
                        _start_bot_internal(req)
                        started += 1
                        log.info(f"✅ [Auto-Resume] ({started}/{total}) {c.get('email', cid[:8])}")

                        # فاصل عشوائي 5-10 ثوانٍ بين كل حساب
                        if i < total - 1:
                            delay = random.randint(5, 10)
                            time.sleep(delay)
                    except Exception as ex:
                        log.warning(f"⚠️ فشل استئناف البوت {cid}: {ex}")
                        with _lock:
                            _reserved.discard(cid)
                            _conn_states.pop(cid, None)

                log.info(f"🎉 [Auto-Resume] اكتمل استئناف {started} بوت من أصل {total} بنجاح.")
        finally:
            _deploy_mode = False
            with _lock:
                _reserved.clear()
            log.info("🔓 [Auto-Resume] انتهى الاستئناف التدريجي — وضع النشر أُلغي، البوتات متاحة للمستخدمين.")

    threading.Thread(target=_bg_resume, daemon=True, name="auto-resume").start()



@app.on_event("startup")
def on_startup():
    """تهيئة خدمات السيرفر واستئناف البوتات عند إقلاع تطبيق FastAPI."""
    log.info("🚀 [Startup Event] استئناف البوتات النشطة...")
    cleanup_expired_bot_logs()

    # تشغيل عامل تنظيف دوري في الخلفية لحذف السجلات المنتهية (> 24 ساعة) كل ساعة
    def _periodic_log_cleaner():
        while True:
            try:
                time.sleep(3600)
                cleanup_expired_bot_logs()
            except Exception:
                pass

    threading.Thread(target=_periodic_log_cleaner, daemon=True, name="sys-log-cleaner").start()

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
