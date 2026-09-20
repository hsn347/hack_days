# -*- coding: utf-8 -*-
"""
core/database.py — قاعدة بيانات SQLite المحلية الرئيسية (castles.db)
════════════════════════════════════════════════════════════════════════
يوفر هذا الملف:
  1. إدارة كاملة لبيانات المستخدمين واشتراكاتهم (جدول users).
  2. إدارة القلاع وحالاتها ومواردها وإعداداتها (جدول castle_states).
  3. دعم نمط WAL (Write-Ahead Logging) للقراءة والكتابة المتزامنة.
  4. دوال CRUD شاملة ومحمية من أخطاء الاتصال والتضارب.
  5. التحقق من صلاحية الاشتراكات محلياً بدون أي اتصال بالشبكة.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("LocalDB")

# المسار الافتراضي لملف قاعدة البيانات في مجلد database/ المخصص
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(_BASE_DIR, "database")
DEFAULT_DB_PATH = os.path.join(DB_DIR, "castles.db")

# قفل لمنع التضارب عند التهيئة المبدئية داخل نفس العملية
_init_lock = threading.Lock()
_db_initialized = False


def get_db_path(custom_path: Optional[str] = None) -> str:
    """
    الحصول على مسار ملف قاعدة البيانات المعتمد:
    1. المسار المخصص (إن وُجد)
    2. متغير البيئة CASTLES_DB_PATH (إن وُجد)
    3. المسار الجديد داخل مجلد database/castles.db
    4. التوافق العكسي: إذا لم يُنقل الملف بعد وما زال في الجذر، يُستخدم القديم تلقائياً.
    """
    if custom_path:
        return custom_path
    if os.getenv("CASTLES_DB_PATH"):
        return os.environ["CASTLES_DB_PATH"]

    os.makedirs(DB_DIR, exist_ok=True)

    if os.path.exists(DEFAULT_DB_PATH):
        return DEFAULT_DB_PATH

    legacy_path = os.path.join(_BASE_DIR, "castles.db")
    if os.path.exists(legacy_path):
        return legacy_path

    return DEFAULT_DB_PATH


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    إنشاء اتصال بقاعدة بيانات SQLite مع تفعيل إعدادات السرعة والأمان التزامني (WAL).
    """
    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    
    # تفعيل وضع WAL لسرعة القراءة والكتابة المتزامنة وتفادي Database is locked
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """تهيئة وإنشاء جداول المستخدمين والقلاع والفهارس إن لم تكن موجودة."""
    global _db_initialized
    with _init_lock:
        try:
            with get_connection(db_path) as conn:
                # ── جدول المستخدمين ──
                conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    username TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    role TEXT DEFAULT 'user',
                    created_at TEXT,
                    is_banned INTEGER DEFAULT 0,
                    banned_reason TEXT DEFAULT '',
                    plan_id TEXT DEFAULT 'free',
                    plan_name TEXT DEFAULT 'مجاني',
                    subscription_status TEXT DEFAULT 'active',
                    subscription_started_at TEXT,
                    subscription_expires_at TEXT,
                    max_castles_allowed INTEGER DEFAULT 1,
                    current_castles_count INTEGER DEFAULT 0,
                    pending_castles_count INTEGER DEFAULT 0
                );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")

                # ── جدول القلاع ──
                conn.execute("""
                CREATE TABLE IF NOT EXISTS castle_states (
                    castle_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    user_id TEXT,
                    password TEXT DEFAULT '',
                    config TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    lord_name TEXT,
                    castle_name TEXT DEFAULT '',
                    lord_power INTEGER DEFAULT 0,
                    castle_level INTEGER DEFAULT 1,
                    walls_level INTEGER DEFAULT 0,
                    server_id INTEGER DEFAULT 1,
                    coord_x INTEGER DEFAULT 0,
                    coord_y INTEGER DEFAULT 0,
                    vip_level INTEGER DEFAULT 0,
                    alliance_name TEXT DEFAULT '',
                    state TEXT DEFAULT 'idle',
                    conn_state TEXT DEFAULT 'idle',
                    conn_message TEXT DEFAULT '',
                    next_run_time TEXT,
                    last_run_time TEXT,
                    last_run_message TEXT,
                    food INTEGER DEFAULT 0,
                    wood INTEGER DEFAULT 0,
                    iron INTEGER DEFAULT 0,
                    diamond INTEGER DEFAULT 0,
                    gold INTEGER DEFAULT 0,
                    stamina INTEGER DEFAULT 100,
                    last_updated TEXT,
                    raw_json TEXT
                );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_email ON castle_states(email);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_user ON castle_states(user_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_state ON castle_states(state);")

                # ── ترقية الجدول القديم (إزالة قيد UNIQUE من email إن وجد) ──
                tbl_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='castle_states'").fetchone()
                if tbl_row and "email TEXT UNIQUE" in tbl_row[0]:
                    log.info("تحديث جدول castle_states لإزالة قيد UNIQUE عن البريد الإلكتروني...")
                    conn.execute("ALTER TABLE castle_states RENAME TO castle_states_old;")
                    conn.execute("""
                    CREATE TABLE castle_states (
                        castle_id TEXT PRIMARY KEY,
                        email TEXT NOT NULL,
                        user_id TEXT,
                        password TEXT DEFAULT '',
                        config TEXT DEFAULT '{}',
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT,
                        lord_name TEXT,
                        castle_name TEXT DEFAULT '',
                        lord_power INTEGER DEFAULT 0,
                        castle_level INTEGER DEFAULT 1,
                        walls_level INTEGER DEFAULT 0,
                        server_id INTEGER DEFAULT 1,
                        coord_x INTEGER DEFAULT 0,
                        coord_y INTEGER DEFAULT 0,
                        vip_level INTEGER DEFAULT 0,
                        alliance_name TEXT DEFAULT '',
                        state TEXT DEFAULT 'idle',
                        conn_state TEXT DEFAULT 'idle',
                        conn_message TEXT DEFAULT '',
                        next_run_time TEXT,
                        last_run_time TEXT,
                        last_run_message TEXT,
                        food INTEGER DEFAULT 0,
                        wood INTEGER DEFAULT 0,
                        iron INTEGER DEFAULT 0,
                        diamond INTEGER DEFAULT 0,
                        gold INTEGER DEFAULT 0,
                        stamina INTEGER DEFAULT 100,
                        last_updated TEXT,
                        raw_json TEXT
                    );
                    """)
                    conn.execute("""
                    INSERT OR REPLACE INTO castle_states (
                        castle_id, email, user_id, password, config, is_active, created_at,
                        lord_name, castle_name, lord_power, castle_level, walls_level,
                        server_id, coord_x, coord_y, vip_level, alliance_name,
                        state, conn_state, conn_message, next_run_time, last_run_time,
                        last_run_message, food, wood, iron, diamond, gold, stamina,
                        last_updated, raw_json
                    )
                    SELECT 
                        castle_id, email, user_id, 
                        COALESCE(password, ''), COALESCE(config, '{}'), COALESCE(is_active, 1), created_at,
                        lord_name, COALESCE(castle_name, ''), lord_power, castle_level, walls_level,
                        server_id, coord_x, coord_y, COALESCE(vip_level, 0), COALESCE(alliance_name, ''),
                        state, conn_state, conn_message, next_run_time, last_run_time,
                        last_run_message, food, wood, iron, diamond, gold, stamina,
                        last_updated, raw_json
                    FROM castle_states_old;
                    """)
                    conn.execute("DROP TABLE castle_states_old;")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_email ON castle_states(email);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_user ON castle_states(user_id);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_state ON castle_states(state);")

                # ── ترقية الجدول القديم (إضافة أعمدة جديدة إن لم تكن موجودة) ──
                existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(castle_states)").fetchall()}
                new_cols = {
                    "password": "TEXT DEFAULT ''",
                    "config": "TEXT DEFAULT '{}'",
                    "is_active": "INTEGER DEFAULT 1",
                    "created_at": "TEXT",
                    "castle_name": "TEXT DEFAULT ''",
                    "alliance_name": "TEXT DEFAULT ''",
                    "vip_level": "INTEGER DEFAULT 0",
                }
                for col_name, col_def in new_cols.items():
                    if col_name not in existing_cols:
                        try:
                            conn.execute(f"ALTER TABLE castle_states ADD COLUMN {col_name} {col_def}")
                        except Exception:
                            pass

                conn.commit()
            _db_initialized = True
        except Exception as e:
            log.warning(f"⚠️ خطأ أثناء تهيئة قاعدة البيانات المحلية: {e}")


def _ensure_init(db_path: Optional[str] = None) -> None:
    """التأكد التلقائي من تهيئة قاعدة البيانات قبل أول عملية."""
    if not _db_initialized:
        init_db(db_path)


# ════════════════════════════════════════════════════════════════════
# 👤 دوال إدارة المستخدمين (Users CRUD)
# ════════════════════════════════════════════════════════════════════

def create_or_update_user(
    uid: str,
    email: str,
    username: str = "",
    phone: str = "",
    role: str = "user",
    is_banned: bool = False,
    banned_reason: str = "",
    created_at: str = "",
    plan_id: str = "pending_trial",
    plan_name: str = "بانتظار موافقة الإدارة",
    subscription_status: str = "pending_approval",
    subscription_started_at: str = "",
    subscription_expires_at: str = "",
    max_castles_allowed: int = 0,
    current_castles_count: int = 0,
    pending_castles_count: int = 0,
    db_path: Optional[str] = None,
) -> bool:
    """إنشاء أو تحديث مستخدم في قاعدة البيانات."""
    _ensure_init(db_path)
    if not uid or not email:
        return False
    clean_email = email.strip().lower()
    is_super = clean_email in ("ibraboths@gmail.com", "fahed.k140@gmail.com") or role == "admin"
    if is_super:
        role = "admin"
        plan_id = "super_admin_unlimited"
        plan_name = "باقة المشرف الأعلى (غير محدود)"
        subscription_status = "active"
        subscription_expires_at = "2099-01-01T00:00:00Z"
        max_castles_allowed = 999999

    now_created = created_at or datetime.now(timezone.utc).isoformat()
    try:
        with get_connection(db_path) as conn:
            conn.execute("""
            INSERT INTO users (
                uid, email, username, phone, role, created_at,
                is_banned, banned_reason, plan_id, plan_name,
                subscription_status, subscription_started_at, subscription_expires_at,
                max_castles_allowed, current_castles_count, pending_castles_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                email = excluded.email,
                username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END,
                phone = CASE WHEN excluded.phone != '' THEN excluded.phone ELSE users.phone END,
                role = CASE WHEN users.role = 'admin' THEN 'admin' ELSE excluded.role END,
                is_banned = excluded.is_banned,
                banned_reason = CASE WHEN excluded.banned_reason != '' THEN excluded.banned_reason ELSE users.banned_reason END
            """, (
                uid, clean_email, username, phone, role, now_created,
                1 if is_banned else 0, banned_reason, plan_id, plan_name,
                subscription_status, subscription_started_at, subscription_expires_at,
                max_castles_allowed, current_castles_count, pending_castles_count,
            ))
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر إنشاء/تحديث المستخدم ({uid}): {e}")
        return False


def get_user(uid: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """جلب بيانات مستخدم واحد."""
    _ensure_init(db_path)
    if not uid:
        return None
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute("SELECT * FROM users WHERE uid = ? LIMIT 1", (uid,))
            row = cur.fetchone()
            if row:
                d = dict(row)
                d["is_banned"] = bool(d.get("is_banned", 0))
                is_super = d.get("role") == "admin" or str(d.get("email", "")).strip().lower() in ("ibraboths@gmail.com", "fahed.k140@gmail.com")
                d["subscription"] = {
                    "plan_id": "super_admin_unlimited" if is_super else d.get("plan_id", "pending_trial"),
                    "plan_name": "باقة المشرف الأعلى (غير محدود)" if is_super else d.get("plan_name", "بانتظار موافقة الإدارة"),
                    "status": "active" if is_super else d.get("subscription_status", "pending_approval"),
                    "started_at": d.get("subscription_started_at", ""),
                    "expires_at": "2099-01-01T00:00:00Z" if is_super else d.get("subscription_expires_at", ""),
                    "max_castles_allowed": 999999 if is_super else d.get("max_castles_allowed", 0),
                    "current_castles_count": d.get("current_castles_count", 0),
                    "pending_castles_count": d.get("pending_castles_count", 0),
                }
                return d
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب المستخدم ({uid}): {e}")
    return None


def get_all_users(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """جلب جميع المستخدمين (للإدارة)."""
    _ensure_init(db_path)
    result: List[Dict[str, Any]] = []
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
            for row in cur.fetchall():
                d = dict(row)
                d["is_banned"] = bool(d.get("is_banned", 0))
                result.append(d)
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب المستخدمين: {e}")
    return result


def update_user_profile(uid: str, username: Optional[str] = None, phone: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """تحديث الملف الشخصي للمستخدم (الاسم ورقم الهاتف)."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            sets = []
            params = []
            if username is not None and username.strip():
                sets.append("username = ?")
                params.append(username.strip())
            if phone is not None:
                sets.append("phone = ?")
                params.append(phone.strip())
            if not sets:
                return True
            params.append(uid)
            conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE uid = ?", params)
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث الملف الشخصي ({uid}): {e}")
        return False


def update_user_subscription(
    uid: str,
    plan_id: str = "",
    plan_name: str = "",
    subscription_status: str = "",
    subscription_started_at: str = "",
    subscription_expires_at: str = "",
    max_castles_allowed: Optional[int] = None,
    db_path: Optional[str] = None,
    **kwargs: Any
) -> bool:
    """تحديث بيانات اشتراك مستخدم مع دعم المرونة في أسماء المعاملات."""
    _ensure_init(db_path)
    status = kwargs.get("status") or subscription_status
    exp_at = kwargs.get("expires_at") or subscription_expires_at
    max_c = kwargs.get("max_castles") if kwargs.get("max_castles") is not None else max_castles_allowed
    started_at = kwargs.get("started_at") or subscription_started_at

    try:
        with get_connection(db_path) as conn:
            sets = []
            params = []
            if plan_id:
                sets.append("plan_id = ?"); params.append(plan_id)
            if plan_name:
                sets.append("plan_name = ?"); params.append(plan_name)
            if status:
                sets.append("subscription_status = ?"); params.append(status)
            if started_at:
                sets.append("subscription_started_at = ?"); params.append(started_at)
            if exp_at:
                sets.append("subscription_expires_at = ?"); params.append(exp_at)
            if max_c is not None:
                sets.append("max_castles_allowed = ?"); params.append(max_c)
            if not sets:
                return True
            params.append(uid)
            conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE uid = ?", params)
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث اشتراك المستخدم ({uid}): {e}")
        return False


def approve_user_trial(
    uid: str,
    days: int = 3,
    max_castles: int = 10,
    db_path: Optional[str] = None
) -> bool:
    """الموافقة على المستخدم وتفعيل باقة التجربة (10 حسابات لمدة 3 أيام)."""
    _ensure_init(db_path)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    started_at = now.isoformat()
    expires_at = expires.isoformat()
    plan_id = f"{max_castles}_castles_{days}d"
    plan_name = f"{max_castles} حساب ({days} أيام)"

    return update_user_subscription(
        uid=uid,
        plan_id=plan_id,
        plan_name=plan_name,
        subscription_status="active",
        subscription_started_at=started_at,
        subscription_expires_at=expires_at,
        max_castles_allowed=max_castles,
        db_path=db_path
    )


def approve_all_pending_users(
    days: int = 3,
    max_castles: int = 10,
    db_path: Optional[str] = None
) -> int:
    """الموافقة على جميع المستخدمين المعلقين وتفعيل باقة التجربة لهم في معاملة واحدة."""
    _ensure_init(db_path)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    started_at = now.isoformat()
    expires_at = expires.isoformat()
    plan_id = f"{max_castles}_castles_{days}d"
    plan_name = f"{max_castles} حساب ({days} أيام)"

    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET plan_id = ?,
                    plan_name = ?,
                    subscription_status = 'active',
                    subscription_started_at = ?,
                    subscription_expires_at = ?,
                    max_castles_allowed = ?
                WHERE subscription_status = 'pending_approval'
                  AND (role IS NULL OR role != 'admin')
                """,
                (plan_id, plan_name, started_at, expires_at, max_castles)
            )
            count = cur.rowcount
            conn.commit()
            log.info(f"✅ تمت الموافقة الجماعية على {count} مستخدم معلق وتفعيل باقة ({max_castles} حساب / {days} أيام).")
            return count
    except Exception as e:
        log.warning(f"⚠️ تعذر الموافقة الجماعية على المستخدمين المعلقين: {e}")
        return 0


def ban_user(uid: str, ban: bool, reason: str = "", db_path: Optional[str] = None) -> bool:
    """حظر أو رفع حظر مستخدم."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            conn.execute(
                "UPDATE users SET is_banned = ?, banned_reason = ? WHERE uid = ?",
                (1 if ban else 0, reason, uid)
            )
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث حالة حظر المستخدم ({uid}): {e}")
        return False


def delete_user(uid: str, db_path: Optional[str] = None) -> bool:
    """حذف مستخدم وجميع قلاعه."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            conn.execute("DELETE FROM castle_states WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM users WHERE uid = ?", (uid,))
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر حذف المستخدم ({uid}): {e}")
        return False


def update_user_castle_counts(uid: str, db_path: Optional[str] = None) -> Tuple[int, int]:
    """إعادة حساب عدد القلاع النشطة والمعلقة وتحديثها في جدول المستخدمين."""
    _ensure_init(db_path)
    active = 0
    pending = 0
    try:
        with get_connection(db_path) as conn:
            row_a = conn.execute(
                "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND is_active = 1 AND state != 'pending'",
                (uid,)
            ).fetchone()
            row_p = conn.execute(
                "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND (is_active = 0 OR state = 'pending')",
                (uid,)
            ).fetchone()
            active = row_a["cnt"] if row_a else 0
            pending = row_p["cnt"] if row_p else 0
            conn.execute(
                "UPDATE users SET current_castles_count = ?, pending_castles_count = ? WHERE uid = ?",
                (active, pending, uid)
            )
            conn.commit()
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث عدد القلاع ({uid}): {e}")
    return active, pending


def check_user_subscription_db(uid: str, db_path: Optional[str] = None) -> Tuple[bool, str]:
    """التحقق من صلاحية اشتراك المستخدم وحالة الحظر محلياً من SQLite."""
    _ensure_init(db_path)
    user = get_user(uid, db_path)
    if not user:
        return False, "المستخدم غير موجود في النظام"

    # المشرف الأعلى
    if user.get("role") == "admin" or str(user.get("email", "")).strip().lower() in ("ibraboths@gmail.com", "fahed.k140@gmail.com"):
        return True, "المشرف الأعلى — صلاحية مطلقة"

    # حظر
    if user.get("is_banned"):
        return False, "الحساب محظور من قبل الإدارة"

    # حالة الاشتراك
    sub = user.get("subscription") or {}
    status = sub.get("status") or user.get("subscription_status", "expired")
    if status == "pending_approval":
        return False, "الحساب بانتظار موافقة الإدارة لتفعيل باقة التجربة (10 حسابات / 3 أيام)"

    if status != "active":
        return False, f"الاشتراك غير مفعل (الحالة: {status})"

    # تاريخ الانتهاء
    expires_raw = sub.get("expires_at") or user.get("subscription_expires_at", "")
    if expires_raw:
        try:
            d_str = str(expires_raw).strip().replace("Z", "+00:00")
            expires_at = datetime.fromisoformat(d_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now > expires_at:
                return False, f"انتهت صلاحية الاشتراك بتاريخ: {expires_at.strftime('%Y-%m-%d %H:%M')}"
        except Exception as e:
            return False, f"صيغة تاريخ انتهاء الاشتراك غير صالحة: {e}"

    return True, "الاشتراك نشط وصالح"


# ════════════════════════════════════════════════════════════════════
# 🏰 دوال إدارة القلاع (Castles CRUD)
# ════════════════════════════════════════════════════════════════════

def save_castle(
    user_id_or_data: Any,
    castle_id: Optional[str] = None,
    email: Optional[str] = None,
    password: str = "",
    config: Any = "{}",
    is_active: int = 1,
    created_at: str = "",
    db_path: Optional[str] = None,
    **extra: Any
) -> bool:
    """إنشاء أو تحديث قلعة في قاعدة البيانات مع دعم تمرير قاموس أو معاملات منفردة."""
    _ensure_init(db_path)
    
    if isinstance(user_id_or_data, dict):
        d = user_id_or_data
        uid = str(d.get("user_id") or "")
        cid = str(d.get("castle_id") or "")
        em = str(d.get("email") or "")
        pwd = str(d.get("password") or "")
        cfg = d.get("config", "{}")
        act = 1 if d.get("is_active", True) else 0
        c_at = str(d.get("created_at") or "")
        st = d.get("state") or ("idle" if act else "pending")
        c_st = d.get("conn_state") or ("idle" if act else "pending")
        c_msg = d.get("conn_message") or ("جاهز للتشغيل" if act else "بانتظار موافقة الإدارة")
    else:
        uid = str(user_id_or_data or "")
        cid = str(castle_id or "")
        em = str(email or "")
        pwd = str(password or "")
        cfg = config
        act = 1 if is_active else 0
        c_at = str(created_at or "")
        st = "idle" if act else "pending"
        c_st = "idle" if act else "pending"
        c_msg = "جاهز للتشغيل" if act else "بانتظار موافقة الإدارة"

    if not cid or not em:
        return False

    clean_email = em.strip().lower()
    now_created = c_at or datetime.now(timezone.utc).isoformat()
    config_json = json.dumps(cfg, ensure_ascii=False) if isinstance(cfg, dict) else str(cfg or "{}")

    try:
        with get_connection(db_path) as conn:
            conn.execute("""
            INSERT INTO castle_states (
                castle_id, email, user_id, password, config, is_active, created_at, state, conn_state, conn_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(castle_id) DO UPDATE SET
                email = excluded.email,
                user_id = CASE WHEN excluded.user_id != '' THEN excluded.user_id ELSE castle_states.user_id END,
                password = CASE WHEN excluded.password != '' THEN excluded.password ELSE castle_states.password END,
                config = CASE WHEN excluded.config != '{}' THEN excluded.config ELSE castle_states.config END,
                is_active = excluded.is_active,
                created_at = CASE WHEN excluded.created_at != '' THEN excluded.created_at ELSE castle_states.created_at END,
                state = CASE WHEN castle_states.state = 'pending' AND excluded.is_active = 1 THEN 'idle' ELSE castle_states.state END,
                conn_state = CASE WHEN castle_states.conn_state = 'pending' AND excluded.is_active = 1 THEN 'idle' ELSE castle_states.conn_state END
            """, (cid, clean_email, uid, pwd, config_json, act, now_created, st, c_st, c_msg))
            conn.commit()
            if uid:
                update_user_castle_counts(uid, db_path)
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر حفظ القلعة ({cid}): {e}")
        return False


def get_user_castles(user_id: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """جلب جميع قلاع مستخدم معين مع كافة البيانات (بدون كلمة المرور)."""
    _ensure_init(db_path)
    result: List[Dict[str, Any]] = []
    if not user_id:
        return result
    clean_uid = str(user_id).strip()
    try:
        with get_connection(db_path) as conn:
            # البحث عن المستخدم لمعرفة الـ UID والبريد معاً للبحث بهما
            u_row = conn.execute(
                "SELECT uid, email FROM users WHERE uid = ? OR lower(email) = ? LIMIT 1",
                (clean_uid, clean_uid.lower())
            ).fetchone()

            if u_row:
                uid_val = u_row["uid"]
                email_val = str(u_row["email"]).strip().lower()
                cur = conn.execute(
                    "SELECT * FROM castle_states WHERE user_id = ? OR lower(user_id) = ? ORDER BY created_at DESC",
                    (uid_val, email_val)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM castle_states WHERE user_id = ? OR lower(user_id) = ? ORDER BY created_at DESC",
                    (clean_uid, clean_uid.lower())
                )
            for row in cur.fetchall():
                d = dict(row)
                d.pop("password", None)  # لا نرسل كلمة المرور للعميل
                d.pop("raw_json", None)
                # تحويل config من JSON text إلى dict
                try:
                    d["config"] = json.loads(d.get("config") or "{}")
                except Exception:
                    d["config"] = {}
                d["is_active"] = bool(d.get("is_active", 1))
                result.append(d)
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب قلاع المستخدم ({user_id}): {e}")
    return result


def get_castle_by_id(castle_id: str, user_id: Optional[str] = None, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """جلب بيانات قلعة محددة (بدون كلمة المرور)."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            if user_id:
                cur = conn.execute(
                    "SELECT * FROM castle_states WHERE castle_id = ? AND user_id = ? LIMIT 1",
                    (castle_id, user_id)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM castle_states WHERE castle_id = ? LIMIT 1",
                    (castle_id,)
                )
            row = cur.fetchone()
            if row:
                d = dict(row)
                d.pop("password", None)
                d.pop("raw_json", None)
                try:
                    d["config"] = json.loads(d.get("config") or "{}")
                except Exception:
                    d["config"] = {}
                d["is_active"] = bool(d.get("is_active", 1))
                return d
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب القلعة ({castle_id}): {e}")
    return None


def _deep_merge_dict(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """دمج تكراري (Deep Merge) لقواميس الإعدادات للحفاظ على كافة الأقسام والمهام دون مسحها."""
    result = copy.deepcopy(base) if base else {}
    for k, v in update.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge_dict(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def update_castle_config(castle_id: str, config_dict: Dict[str, Any], user_id: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """تحديث إعدادات المهام لقلعة محددة مع الدمج التكراري (Deep Merge) لحماية بقية المهام من المسح."""
    _ensure_init(db_path)
    if not castle_id or config_dict is None:
        return False
    try:
        with get_connection(db_path) as conn:
            # 1. جلب الإعدادات المخزنة حالياً للقلعة لدمج التعديلات فوقها
            cur = conn.execute("SELECT config FROM castle_states WHERE castle_id = ?", (castle_id,))
            row = cur.fetchone()
            current_config: Dict[str, Any] = {}
            if row and row["config"]:
                try:
                    loaded = json.loads(row["config"])
                    if isinstance(loaded, dict):
                        current_config = loaded
                except Exception:
                    current_config = {}

            # 2. دمج التعديلات الجديدة فوق الإعدادات الحالية بشكل عميق
            merged_config = _deep_merge_dict(current_config, config_dict)
            config_json = json.dumps(merged_config, ensure_ascii=False)

            if user_id:
                conn.execute(
                    "UPDATE castle_states SET config = ?, last_updated = ? WHERE castle_id = ? AND user_id = ?",
                    (config_json, datetime.now(timezone.utc).isoformat(), castle_id, user_id)
                )
            else:
                conn.execute(
                    "UPDATE castle_states SET config = ?, last_updated = ? WHERE castle_id = ?",
                    (config_json, datetime.now(timezone.utc).isoformat(), castle_id)
                )
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث إعدادات القلعة ({castle_id}): {e}")
        return False


def update_castle_credentials(castle_id: str, email: str, password: str = "", user_id: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """تحديث بيانات دخول قلعة (البريد وكلمة المرور)."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            sets = ["email = ?"]
            params = [email.strip().lower()]
            if password and password.strip():
                sets.append("password = ?")
                params.append(password.strip())
            params.append(castle_id)
            where = "castle_id = ?"
            if user_id:
                where += " AND user_id = ?"
                params.append(user_id)
            conn.execute(f"UPDATE castle_states SET {', '.join(sets)} WHERE {where}", params)
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث بيانات دخول القلعة ({castle_id}): {e}")
        return False


def get_castle_password(castle_id_or_user: str, castle_id: Optional[str] = None, db_path: Optional[str] = None) -> Optional[str]:
    """جلب كلمة مرور قلعة محددة (للاستخدام الداخلي فقط) مع دعم كل صيغ الاستدعاء."""
    if not castle_id_or_user:
        return None
    _ensure_init(db_path)
    clean_a = str(castle_id_or_user).strip()
    clean_b = str(castle_id).strip() if castle_id else None

    try:
        with get_connection(db_path) as conn:
            if clean_b:
                cur = conn.execute(
                    "SELECT password FROM castle_states "
                    "WHERE (castle_id = ? OR lower(email) = ? OR castle_id = ? OR lower(email) = ?) "
                    "AND password != '' LIMIT 1",
                    (clean_a, clean_a.lower(), clean_b, clean_b.lower())
                )
            else:
                cur = conn.execute(
                    "SELECT password FROM castle_states "
                    "WHERE (castle_id = ? OR lower(email) = ?) AND password != '' LIMIT 1",
                    (clean_a, clean_a.lower())
                )
            row = cur.fetchone()
            if row and row["password"]:
                return str(row["password"]).strip()
    except Exception as e:
        log.warning(f"⚠️ تعذر جلب كلمة مرور القلعة ({castle_id_or_user}): {e}")
    return None


def count_user_castles(user_id: str, db_path: Optional[str] = None) -> Tuple[int, int]:
    """عد القلاع النشطة والمعلقة لمستخدم معين."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            row_a = conn.execute(
                "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND is_active = 1 AND state != 'pending'",
                (user_id,)
            ).fetchone()
            row_p = conn.execute(
                "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND (is_active = 0 OR state = 'pending')",
                (user_id,)
            ).fetchone()
            active = row_a["cnt"] if row_a else 0
            pending = row_p["cnt"] if row_p else 0
            return active, pending
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء عد القلاع ({user_id}): {e}")
        return 0, 0


def approve_castle(castle_id: str, user_id: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """الموافقة على قلعة معلقة (تفعيلها وتغيير حالتها من pending إلى idle)."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            uid = user_id
            if not uid:
                row = conn.execute("SELECT user_id FROM castle_states WHERE castle_id = ? LIMIT 1", (castle_id,)).fetchone()
                if row:
                    uid = row["user_id"]

            conn.execute(
                "UPDATE castle_states SET is_active = 1, state = 'idle', conn_state = 'idle', "
                "conn_message = 'جاهز للتشغيل (تمت الموافقة من الإدارة)', "
                "last_run_message = 'جاهز للتشغيل' WHERE castle_id = ?",
                (castle_id,)
            )
            conn.commit()
            if uid:
                update_user_castle_counts(uid, db_path)
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر الموافقة على القلعة ({castle_id}): {e}")
        return False


def reject_castle(castle_id: str, user_id_or_reason: Optional[str] = None, reason: str = "", db_path: Optional[str] = None) -> bool:
    """رفض وحذف قلعة معلقة."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            row = conn.execute("SELECT user_id FROM castle_states WHERE castle_id = ? LIMIT 1", (castle_id,)).fetchone()
            uid = row["user_id"] if row else None

            conn.execute("DELETE FROM castle_states WHERE castle_id = ?", (castle_id,))
            conn.commit()
            if uid:
                update_user_castle_counts(uid, db_path)
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر رفض القلعة ({castle_id}): {e}")
        return False


# ════════════════════════════════════════════════════════════════════
# 🔄 دوال تحديث الحالة والموارد (الموجودة سابقاً — مُحسّنة)
# ════════════════════════════════════════════════════════════════════

def upsert_castle_conn_state(
    email: str,
    conn_state: str,
    message: str = "",
    next_run_time: Optional[str] = None,
    user_id: Optional[str] = None,
    castle_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """
    تحديث أو إدراج حالة اتصال ونشاط القلعة (State + Connection State + Message + Next Run).
    """
    if not email:
        return False

    _ensure_init(db_path)
    clean_email = email.strip().lower()
    cid = str(castle_id or clean_email)
    now_iso = datetime.now(timezone.utc).isoformat()

    # تحديد الحالة التشغيلية العامة (running / idle)
    general_state = "idle"
    if conn_state in ("connected", "reconnecting", "disconnected", "waiting"):
        general_state = "running"
    elif conn_state == "idle":
        general_state = "idle"

    last_run_time = now_iso if conn_state == "connected" else None

    try:
        with get_connection(db_path) as conn:
            # 1. فحص وجود القلعة سواء عبر castle_id أو email (بشكل غير حساس لحالة الأحرف)
            cur = conn.execute(
                "SELECT castle_id, user_id, last_run_time FROM castle_states "
                "WHERE castle_id = ? OR lower(castle_id) = ? OR lower(email) = ? LIMIT 1",
                (cid, cid.lower(), clean_email)
            )
            row = cur.fetchone()

            if row:
                target_cid = row["castle_id"]
                effective_last_run = last_run_time or row["last_run_time"]
                conn.execute("""
                UPDATE castle_states
                SET state = ?,
                    conn_state = ?,
                    conn_message = ?,
                    next_run_time = COALESCE(?, next_run_time),
                    last_run_time = COALESCE(?, last_run_time),
                    last_run_message = CASE WHEN ? != '' THEN ? ELSE last_run_message END,
                    user_id = COALESCE(?, user_id),
                    last_updated = ?
                WHERE castle_id = ?
                """, (
                    general_state,
                    conn_state,
                    message,
                    next_run_time,
                    effective_last_run,
                    message,
                    message,
                    user_id,
                    now_iso,
                    target_cid
                ))
            else:
                conn.execute("""
                INSERT INTO castle_states (
                    castle_id, email, user_id, state, conn_state, conn_message,
                    next_run_time, last_run_time, last_run_message, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cid,
                    clean_email,
                    user_id,
                    general_state,
                    conn_state,
                    message,
                    next_run_time,
                    last_run_time,
                    message,
                    now_iso
                ))
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث حالة القلعة محلياً ({clean_email}): {e}")
        return False


def upsert_castle_resources(
    email: str,
    resources: Dict[str, Any],
    castle_info: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    castle_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """
    تحديث أو إدراج موارد القلعة ومعلومات اللورد في قاعدة البيانات المحلية ذرّياً.
    """
    if not email:
        return False

    _ensure_init(db_path)
    clean_email = email.strip().lower()
    cid = str(castle_id or clean_email)
    now_iso = datetime.now(timezone.utc).isoformat()
    cinfo = castle_info or {}

    food = int(resources.get("food", 0) or 0)
    wood = int(resources.get("wood", 0) or 0)
    iron = int(resources.get("iron", 0) or 0)
    diamond = int(resources.get("diamond", 0) or 0)
    gold = int(resources.get("gold", 0) or 0)
    stamina = int(resources.get("stamina", 100) or 100)

    lord_name = str(cinfo.get("lord_name", "")) if cinfo.get("lord_name") else None
    lord_power = int(cinfo.get("lord_power", 0) or 0)
    castle_level = int(cinfo.get("castle_level", 1) or 1)
    walls_level = int(cinfo.get("walls_level", 0) or 0)
    server_id = int(cinfo.get("server_id", 1) or 1)
    coords = cinfo.get("coordinates") or {}
    coord_x = int(coords.get("x", 0) or 0) if isinstance(coords, dict) else 0
    coord_y = int(coords.get("y", 0) or 0) if isinstance(coords, dict) else 0

    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT castle_id FROM castle_states "
                "WHERE castle_id = ? OR lower(castle_id) = ? OR lower(email) = ? LIMIT 1",
                (cid, cid.lower(), clean_email)
            )
            row = cur.fetchone()

            if row:
                target_cid = row["castle_id"]
                conn.execute("""
                UPDATE castle_states
                SET food = ?,
                    wood = ?,
                    iron = ?,
                    diamond = ?,
                    gold = ?,
                    stamina = ?,
                    lord_name = COALESCE(?, lord_name),
                    lord_power = CASE WHEN ? > 0 THEN ? ELSE lord_power END,
                    castle_level = CASE WHEN ? > 1 THEN ? ELSE castle_level END,
                    walls_level = CASE WHEN ? > 0 THEN ? ELSE walls_level END,
                    server_id = CASE WHEN ? > 0 THEN ? ELSE server_id END,
                    coord_x = CASE WHEN ? > 0 THEN ? ELSE coord_x END,
                    coord_y = CASE WHEN ? > 0 THEN ? ELSE coord_y END,
                    user_id = COALESCE(?, user_id),
                    last_updated = ?
                WHERE castle_id = ?
                """, (
                    food, wood, iron, diamond, gold, stamina,
                    lord_name,
                    lord_power, lord_power,
                    castle_level, castle_level,
                    walls_level, walls_level,
                    server_id, server_id,
                    coord_x, coord_x,
                    coord_y, coord_y,
                    user_id,
                    now_iso,
                    target_cid
                ))
            else:
                conn.execute("""
                INSERT INTO castle_states (
                    castle_id, email, user_id, lord_name, lord_power,
                    castle_level, walls_level, server_id, coord_x, coord_y,
                    food, wood, iron, diamond, gold, stamina, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cid, clean_email, user_id, lord_name, lord_power,
                    castle_level, walls_level, server_id, coord_x, coord_y,
                    food, wood, iron, diamond, gold, stamina, now_iso
                ))
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث موارد القلعة محلياً ({clean_email}): {e}")
        return False


def get_castle(identifier: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    استرجاع بيانات قلعة معينة كقاموس باستخدام البريد الإلكتروني أو معرف القلعة (غير حساس لحالة الأحرف).
    """
    if not identifier:
        return None

    _ensure_init(db_path)
    clean_id = identifier.strip().lower()

    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT * FROM castle_states WHERE lower(email) = ? OR lower(castle_id) = ? LIMIT 1",
                (clean_id, clean_id)
            )
            row = cur.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء استرجاع القلعة محلياً ({identifier}): {e}")
    return None


def castle_exists_by_email(email: str, exclude_castle_id: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """التحقق مما إذا كان بريد القلعة مسجلاً مسبقاً في النظام (غير حساس لحالة الأحرف)."""
    if not email:
        return False
    _ensure_init(db_path)
    clean_em = email.strip().lower()
    try:
        with get_connection(db_path) as conn:
            if exclude_castle_id:
                cur = conn.execute(
                    "SELECT 1 FROM castle_states WHERE lower(email) = ? AND castle_id != ? LIMIT 1",
                    (clean_em, exclude_castle_id)
                )
            else:
                cur = conn.execute(
                    "SELECT 1 FROM castle_states WHERE lower(email) = ? LIMIT 1",
                    (clean_em,)
                )
            return cur.fetchone() is not None
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء فحص وجود بريد القلعة ({email}): {e}")
        return False


def get_all_castles(user_id: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    استرجاع قائمة بكافة القلاع وحالاتها المخزنة محلياً (مع إمكانية الفلترة حسب المستخدم).
    """
    _ensure_init(db_path)
    result: List[Dict[str, Any]] = []

    try:
        with get_connection(db_path) as conn:
            if user_id:
                cur = conn.execute("SELECT * FROM castle_states WHERE user_id = ? ORDER BY email ASC", (user_id,))
            else:
                cur = conn.execute("SELECT * FROM castle_states ORDER BY email ASC")
            for row in cur.fetchall():
                result.append(dict(row))
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء استرجاع القلاع محلياً: {e}")
    return result


def delete_castle(identifier: str, db_path: Optional[str] = None) -> bool:
    """حذف سجل قلعة معينة من قاعدة البيانات المحلية (غير حساس لحالة الأحرف)."""
    if not identifier:
        return False

    _ensure_init(db_path)
    clean_id = identifier.strip().lower()

    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT user_id FROM castle_states WHERE lower(email) = ? OR lower(castle_id) = ? LIMIT 1",
                (clean_id, clean_id)
            ).fetchone()
            uid = row["user_id"] if row else None

            cur = conn.execute(
                "DELETE FROM castle_states WHERE lower(email) = ? OR lower(castle_id) = ?",
                (clean_id, clean_id)
            )
            conn.commit()
            success = cur.rowcount > 0
            if success and uid:
                update_user_castle_counts(uid, db_path)
            return success
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء حذف القلعة محلياً ({identifier}): {e}")
        return False


def delete_castle_by_id(castle_id: str, user_id: str, db_path: Optional[str] = None) -> bool:
    """حذف قلعة محددة بمعرفها ومعرف مالكها."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "DELETE FROM castle_states WHERE castle_id = ? AND user_id = ?",
                (castle_id, user_id)
            )
            conn.commit()
            if cur.rowcount > 0:
                update_user_castle_counts(user_id, db_path)
                return True
            return False
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء حذف القلعة ({castle_id}): {e}")
        return False


def get_admin_stats(db_path: Optional[str] = None) -> Dict[str, int]:
    """إحصائيات لوحة الإدارة."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            total_users = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE role != 'admin'"
            ).fetchone()["cnt"]
            active_subs = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE subscription_status = 'active' AND role != 'admin'"
            ).fetchone()["cnt"]
            pending_users = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE subscription_status = 'pending_approval' AND role != 'admin'"
            ).fetchone()["cnt"]
            total_castles = conn.execute(
                "SELECT COUNT(*) as cnt FROM castle_states WHERE is_active = 1 AND state != 'pending'"
            ).fetchone()["cnt"]
            return {
                "totalUsers": total_users,
                "activeSubscriptions": active_subs,
                "pendingUsers": pending_users,
                "totalCastles": total_castles,
            }
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب الإحصائيات: {e}")
        return {"totalUsers": 0, "activeSubscriptions": 0, "pendingUsers": 0, "totalCastles": 0}


def get_all_users_with_castles(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """جلب جميع المستخدمين مع عدد قلاعهم الفعلي (للإدارة)."""
    _ensure_init(db_path)
    users = get_all_users(db_path)
    try:
        with get_connection(db_path) as conn:
            for u in users:
                uid = u["uid"]
                row_a = conn.execute(
                    "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND is_active = 1 AND state != 'pending'",
                    (uid,)
                ).fetchone()
                row_p = conn.execute(
                    "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND (is_active = 0 OR state = 'pending')",
                    (uid,)
                ).fetchone()
                row_t = conn.execute(
                    "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ?",
                    (uid,)
                ).fetchone()
                u["current_castles_count"] = row_a["cnt"] if row_a else 0
                u["pending_castles_count"] = row_p["cnt"] if row_p else 0
                u["total_castles_count"] = row_t["cnt"] if row_t else 0
                is_super = u.get("role") == "admin" or str(u.get("email", "")).strip().lower() in ("ibraboths@gmail.com", "fahed.k140@gmail.com")
                u["subscription"] = {
                    "plan_id": "super_admin_unlimited" if is_super else u.get("plan_id", "pending_trial"),
                    "plan_name": "باقة المشرف الأعلى (غير محدود)" if is_super else u.get("plan_name", "بانتظار موافقة الإدارة"),
                    "status": "active" if is_super else u.get("subscription_status", "pending_approval"),
                    "started_at": u.get("subscription_started_at", ""),
                    "expires_at": "2099-01-01T00:00:00Z" if is_super else u.get("subscription_expires_at", ""),
                    "max_castles_allowed": 999999 if is_super else u.get("max_castles_allowed", 0),
                    "current_castles_count": u["current_castles_count"],
                    "pending_castles_count": u["pending_castles_count"],
                    "total_castles_count": u["total_castles_count"],
                }
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب عدد القلاع: {e}")
    return users


def reset_stuck_castles_db(exclude_castle_ids: Optional[List[str]] = None, db_path: Optional[str] = None) -> int:
    """إعادة ضبط أي قلعة ليست في حالة idle إلى idle عند إقلاع السيرفر أو تصفير الحالات (مع استثناء القلاع الجاري استئنافها)."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            if exclude_castle_ids and len(exclude_castle_ids) > 0:
                placeholders = ",".join("?" for _ in exclude_castle_ids)
                cur = conn.execute(f"""
                    UPDATE castle_states 
                    SET state = 'idle', conn_state = 'idle', conn_message = 'جاهز للتشغيل (أعيد ضبط الحالة بأمان)'
                    WHERE (state != 'idle' OR conn_state != 'idle')
                      AND castle_id NOT IN ({placeholders})
                """, exclude_castle_ids)
            else:
                cur = conn.execute("""
                    UPDATE castle_states 
                    SET state = 'idle', conn_state = 'idle', conn_message = 'جاهز للتشغيل (أعيد ضبط الحالة بأمان)'
                    WHERE state != 'idle' OR conn_state != 'idle'
                """)
            conn.commit()
            return cur.rowcount
    except Exception as e:
        log.error(f"خطأ أثناء إعادة ضبط القلاع العالقة: {e}")
        return 0


def find_castles_by_id_prefix(prefix: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """البحث عن قلاع تبدأ معرفاتها ببادئة محددة."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT castle_id, user_id, email, is_active FROM castle_states WHERE castle_id LIKE ?",
                (f"{prefix}%",)
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        log.warning(f"Error finding castle by prefix {prefix}: {e}")
        return []



def toggle_castle_active(castle_id: str, is_active: bool, user_id: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """تفعيل أو تعطيل قلعة."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            val = 1 if is_active else 0
            if user_id:
                cur = conn.execute(
                    "UPDATE castle_states SET is_active = ?, last_updated = ? WHERE castle_id = ? AND user_id = ?",
                    (val, datetime.now(timezone.utc).isoformat(), castle_id, user_id)
                )
            else:
                cur = conn.execute(
                    "UPDATE castle_states SET is_active = ?, last_updated = ? WHERE castle_id = ?",
                    (val, datetime.now(timezone.utc).isoformat(), castle_id)
                )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        log.warning(f"⚠️ تعذر تغيير حالة تفعيل القلعة ({castle_id}): {e}")
        return False

