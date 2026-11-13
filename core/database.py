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

import contextlib
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
_initialized_paths = set()


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


@contextlib.contextmanager
def get_connection(db_path: Optional[str] = None):
    """
    إنشاء اتصال بقاعدة بيانات SQLite مع تفعيل إعدادات السرعة والأمان التزامني (WAL)،
    وضمان إغلاق الاتصال وتحرير الـ File Descriptors فور انتهاء البلوك لمنع استنزاف موارد النظام.
    """
    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    
    # تفعيل وضع WAL لسرعة القراءة والكتابة المتزامنة وتفادي Database is locked
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


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
                    pending_castles_count INTEGER DEFAULT 0,
                    tenant_domain TEXT DEFAULT ''
                );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")
                try:
                    conn.execute("ALTER TABLE users ADD COLUMN tenant_domain TEXT DEFAULT '';")
                except Exception:
                    pass
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_domain);")

                # ── جدول القلاع ──
                conn.execute("""
                CREATE TABLE IF NOT EXISTS castle_states (
                    castle_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    user_id TEXT,
                    password TEXT DEFAULT '',
                    config TEXT DEFAULT '{}',
                    version INTEGER DEFAULT 1,
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
                    unprotected_food INTEGER DEFAULT 0,
                    unprotected_wood INTEGER DEFAULT 0,
                    unprotected_iron INTEGER DEFAULT 0,
                    unprotected_diamond INTEGER DEFAULT 0,
                    safe_food INTEGER DEFAULT 0,
                    safe_wood INTEGER DEFAULT 0,
                    safe_iron INTEGER DEFAULT 0,
                    safe_diamond INTEGER DEFAULT 0,
                    loop_interval INTEGER DEFAULT 40,
                    proxy_index INTEGER DEFAULT -1,
                    last_updated TEXT,
                    raw_json TEXT
                );
                """)
                for col in (
                    "unprotected_food", "unprotected_wood", "unprotected_iron", "unprotected_diamond",
                    "safe_food", "safe_wood", "safe_iron", "safe_diamond"
                ):
                    try:
                        conn.execute(f"ALTER TABLE castle_states ADD COLUMN {col} INTEGER DEFAULT 0;")
                    except Exception:
                        pass
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
                    "version": "INTEGER DEFAULT 1",
                    "is_active": "INTEGER DEFAULT 1",
                    "created_at": "TEXT",
                    "castle_name": "TEXT DEFAULT ''",
                    "alliance_name": "TEXT DEFAULT ''",
                    "vip_level": "INTEGER DEFAULT 0",
                    "avatar": "TEXT DEFAULT ''",
                    "image_id": "INTEGER DEFAULT 0",
                    "loop_interval": "INTEGER DEFAULT 40",
                    "proxy_index": "INTEGER DEFAULT -1",
                }
                for col_name, col_def in new_cols.items():
                    if col_name not in existing_cols:
                        try:
                            conn.execute(f"ALTER TABLE castle_states ADD COLUMN {col_name} {col_def}")
                        except Exception:
                            pass
                try:
                    conn.execute("UPDATE castle_states SET version = 1 WHERE version IS NULL;")
                except Exception:
                    pass

                # ── جدول إعدادات النظام العامة ──
                conn.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT
                );
                """)

                # إسقاط جدول التنبيهات الحرجة القديم تلقائياً لتنظيف قاعدة البيانات
                conn.execute("DROP TABLE IF EXISTS critical_alerts;")

                # ── فهارس تسريع الاستعلامات وتعبيرات LOWER و created_at (Milestone 1) ──
                conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_states_lower_email ON castle_states(LOWER(email));")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_states_lower_user ON castle_states(LOWER(user_id));")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_lower_email ON users(LOWER(email));")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_states_created_at ON castle_states(created_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_castle_states_proxy_index ON castle_states(proxy_index);")

                conn.commit()
            _db_initialized = True
            _initialized_paths.add(get_db_path(db_path))
        except Exception as e:
            log.warning(f"⚠️ خطأ أثناء تهيئة قاعدة البيانات المحلية: {e}")


def _ensure_init(db_path: Optional[str] = None) -> None:
    """التأكد التلقائي من تهيئة قاعدة البيانات قبل أول عملية."""
    path = get_db_path(db_path)
    if path not in _initialized_paths:
        init_db(db_path)


# ════════════════════════════════════════════════════════════════════
# ⚙️ إعدادات النظام العامة (System Settings)
# ════════════════════════════════════════════════════════════════════

def get_system_setting(key: str, default: str = "", db_path: Optional[str] = None) -> str:
    """استرجاع إعداد نظام معين من جدول system_settings."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
            if row and row["value"] is not None:
                return str(row["value"])
    except Exception as e:
        log.warning(f"⚠️ خطأ في قراءة إعداد النظام {key}: {e}")
    return default


def set_system_setting(key: str, value: str, db_path: Optional[str] = None) -> bool:
    """حفظ أو تحديث إعداد نظام في جدول system_settings."""
    _ensure_init(db_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, str(value), now)
            )
            conn.commit()
        return True
    except Exception as e:
        log.warning(f"⚠️ خطأ في حفظ إعداد النظام {key}: {e}")
        return False



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
    tenant_domain: str = "",
    db_path: Optional[str] = None,
) -> bool:
    """إنشاء أو تحديث مستخدم في قاعدة البيانات."""
    _ensure_init(db_path)
    if not uid or not email:
        return False
    clean_email = email.strip().lower()
    is_super = clean_email == "ibraboths@gmail.com"
    try:
        from core.tenants import is_merchant_admin
        is_merchant = is_merchant_admin(clean_email)
    except Exception:
        is_merchant = False

    if is_super:
        role = "admin"
        plan_id = "super_admin_unlimited"
        plan_name = "باقة المشرف الأعلى (غير محدود)"
        subscription_status = "active"
        subscription_expires_at = "2099-01-01T00:00:00Z"
        max_castles_allowed = 999999
    elif is_merchant:
        role = "merchant_admin"
        plan_id = "merchant_admin_unlimited"
        plan_name = "باقة مشرف التاجر (غير محدود)"
        subscription_status = "active"
        subscription_expires_at = "2099-01-01T00:00:00Z"
        max_castles_allowed = 999999
    else:
        role = "user"

    clean_tenant = tenant_domain.strip().lower()
    now_created = created_at or datetime.now(timezone.utc).isoformat()
    try:
        with get_connection(db_path) as conn:
            conn.execute("""
            INSERT INTO users (
                uid, email, username, phone, role, created_at,
                is_banned, banned_reason, plan_id, plan_name,
                subscription_status, subscription_started_at, subscription_expires_at,
                max_castles_allowed, current_castles_count, pending_castles_count,
                tenant_domain
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                email = excluded.email,
                username = CASE WHEN excluded.username != '' THEN excluded.username ELSE users.username END,
                phone = CASE WHEN excluded.phone != '' THEN excluded.phone ELSE users.phone END,
                role = CASE WHEN excluded.email = 'ibraboths@gmail.com' THEN 'admin' ELSE users.role END,
                is_banned = excluded.is_banned,
                tenant_domain = CASE WHEN users.tenant_domain != '' THEN users.tenant_domain ELSE excluded.tenant_domain END,
                banned_reason = CASE WHEN excluded.banned_reason != '' THEN excluded.banned_reason ELSE users.banned_reason END
            """, (
                uid, clean_email, username, phone, role, now_created,
                1 if is_banned else 0, banned_reason, plan_id, plan_name,
                subscription_status, subscription_started_at, subscription_expires_at,
                max_castles_allowed, current_castles_count, pending_castles_count,
                clean_tenant,
            ))
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر إنشاء/تحديث المستخدم ({uid}): {e}")
        return False


create_user = create_or_update_user


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
                is_super = d.get("role") == "admin" and str(d.get("email", "")).strip().lower() == "ibraboths@gmail.com"
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


def get_all_users(tenant_domains: Optional[List[str]] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """جلب المستخدمين (للإدارة، مع إمكانية الفلترة حسب نطاقات التاجر)."""
    _ensure_init(db_path)
    result: List[Dict[str, Any]] = []
    try:
        from core.tenants import get_all_merchants, DEFAULT_TENANT
        admin_emails = [DEFAULT_TENANT["admin_email"].strip().lower()]
        for m in get_all_merchants():
            ae = (m.get("admin_email") or "").strip().lower()
            if ae and ae not in admin_emails:
                admin_emails.append(ae)

        with get_connection(db_path) as conn:
            email_placeholders = ",".join("?" for _ in admin_emails)
            base_where = f"role NOT IN ('admin', 'merchant_admin') AND LOWER(email) NOT IN ({email_placeholders})"
            params = list(admin_emails)

            if tenant_domains and len(tenant_domains) > 0:
                clean_domains = [d.strip().lower() for d in tenant_domains if d.strip()]
                placeholders = ",".join("?" for _ in clean_domains)
                query = f"SELECT * FROM users WHERE {base_where} AND LOWER(tenant_domain) IN ({placeholders}) ORDER BY created_at DESC"
                params.extend(clean_domains)
            else:
                query = f"SELECT * FROM users WHERE {base_where} ORDER BY created_at DESC"

            cur = conn.execute(query, params)
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
        # مزامنة القلاع والحدود تلقائياً
        sync_user_castles_and_quota(uid, db_path)
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
    """الموافقة على جميع المستخدمين المعلقين وتفعيل باقة التجربة لهم ومزامنة قلاعهم تلقائياً."""
    _ensure_init(db_path)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    started_at = now.isoformat()
    expires_at = expires.isoformat()
    plan_id = f"{max_castles}_castles_{days}d"
    plan_name = f"{max_castles} حساب ({days} أيام)"

    try:
        pending_uids = []
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT uid FROM users WHERE subscription_status = 'pending_approval' AND (role IS NULL OR role != 'admin')"
            ).fetchall()
            pending_uids = [r["uid"] for r in rows]

            if not pending_uids:
                return 0

            placeholders = ",".join("?" for _ in pending_uids)
            cur = conn.execute(
                f"""
                UPDATE users
                SET plan_id = ?,
                    plan_name = ?,
                    subscription_status = 'active',
                    subscription_started_at = ?,
                    subscription_expires_at = ?,
                    max_castles_allowed = ?
                WHERE uid IN ({placeholders})
                """,
                [plan_id, plan_name, started_at, expires_at, max_castles] + pending_uids
            )
            count = cur.rowcount
            conn.commit()

        # مزامنة وتفعيل القلاع المعلقة لجميع المستخدمين الذين تمت الموافقة عليهم
        for p_uid in pending_uids:
            sync_user_castles_and_quota(p_uid, db_path)

        log.info(f"✅ تمت الموافقة الجماعية على {count} مستخدم معلق وتفعيل باقة ({max_castles} حساب / {days} أيام).")
        return count
    except Exception as e:
        log.warning(f"⚠️ تعذر الموافقة الجماعية على المستخدمين المعلقين: {e}")
        return 0


def count_user_total_castles(uid: str, db_path: Optional[str] = None) -> int:
    """عد إجمالي القلاع لمستخدم معين (نشطة + معلقة)."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ?", (uid,)).fetchone()
            return row["cnt"] if row else 0
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء عد إجمالي القلاع ({uid}): {e}")
        return 0


def sync_user_castles_and_quota(uid: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    محرك المواءمة الذري: مزامنة قلاع المستخدم مع حد الباقة وحالة الحظر والاشتراك.
    - إذا كان الحساب محظوراً أو منتهي الصلاحية أو بانتظار الموافقة: تجميد كافة القلاع (is_active = 0).
    - إذا كان الاشتراك نشطاً:
        * في حال وجود مقاعد شاغرة (active < max_allowed) وقلاع معلقة:
          ترقية أقدم القلاع المعلقة دفعة واحدة (FIFO بحسب created_at ASC) لتصبح نشطة.
        * في حال تخفيض الباقة من قبل الإدارة (active > max_allowed):
          إيقاف أحدث القلاع النشطة الزائدة (LIFO بحسب created_at DESC) لتصبح معلقة.
    - تحديث إحصائيات current_castles_count و pending_castles_count في جدول users.
    """
    _ensure_init(db_path)
    res: Dict[str, Any] = {
        "active": 0,
        "pending": 0,
        "total": 0,
        "promoted_ids": [],
        "demoted_ids": [],
    }
    if not uid:
        return res

    try:
        with get_connection(db_path) as conn:
            user = get_user(uid, db_path)
            if not user:
                return res

            is_super = user.get("role") == "admin" and str(user.get("email", "")).strip().lower() == "ibraboths@gmail.com"
            is_banned = bool(user.get("is_banned", 0))
            sub_status = user.get("subscription_status", "pending_approval")

            # التحقق من صلاحية الاشتراك
            is_sub_valid = True
            invalid_reason = ""
            if is_super:
                is_sub_valid = True
                max_allowed = 999999
            elif is_banned:
                is_sub_valid = False
                invalid_reason = "تم إيقاف القلعة بسبب حظر الحساب من قبل الإدارة"
                max_allowed = 0
            elif sub_status == "pending_approval":
                is_sub_valid = False
                invalid_reason = "بانتظار موافقة الإدارة لتفعيل باقة التجربة"
                max_allowed = 0
            elif sub_status in ("expired", "suspended"):
                is_sub_valid = False
                invalid_reason = "تم إيقاف القلعة لانتهاء أو تعليق صلاحية الاشتراك"
                max_allowed = 0
            else:
                # التحقق من تاريخ الانتهاء
                exp_raw = user.get("subscription_expires_at", "")
                if exp_raw:
                    try:
                        d_str = str(exp_raw).strip().replace("Z", "+00:00")
                        exp_dt = datetime.fromisoformat(d_str)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) > exp_dt:
                            is_sub_valid = False
                            invalid_reason = "تم إيقاف القلعة لانتهاء صلاحية الاشتراك"
                    except Exception:
                        pass
                max_allowed = int(user.get("max_castles_allowed") or 0) if is_sub_valid else 0

            # جلب كافة قلاع المستخدم مرتبة من الأقدم إلى الأحدث
            cur = conn.execute(
                "SELECT castle_id, is_active, state, created_at FROM castle_states WHERE user_id = ? ORDER BY created_at ASC, rowid ASC",
                (uid,)
            )
            castles = [dict(r) for r in cur.fetchall()]
            res["total"] = len(castles)

            now_iso = datetime.now(timezone.utc).isoformat()

            # 1. إذا كان الاشتراك غير ساري أو الحساب محظور: تجميد كافة القلاع فوراً
            if not is_sub_valid:
                conn.execute(
                    """
                    UPDATE castle_states
                    SET is_active = 0,
                        state = CASE WHEN state != 'pending' THEN 'idle' ELSE state END,
                        conn_state = CASE WHEN conn_state != 'pending' THEN 'idle' ELSE conn_state END,
                        conn_message = ?,
                        last_updated = ?
                    WHERE user_id = ? AND is_active = 1
                    """,
                    (invalid_reason, now_iso, uid)
                )
                conn.execute(
                    "UPDATE users SET current_castles_count = 0, pending_castles_count = ? WHERE uid = ?",
                    (len(castles), uid)
                )
                conn.commit()
                res["active"] = 0
                res["pending"] = len(castles)
                return res

            # 2. الاشتراك ساري: فصل القلاع إلى نشطة ومعلقة
            active_castles = [c for c in castles if c.get("is_active") == 1 and c.get("state") != "pending"]
            pending_castles = [c for c in castles if c.get("is_active") == 0 or c.get("state") == "pending"]

            promoted = []
            demoted = []

            # 2.1 في حال وجود مقاعد شاغرة (active < max_allowed) وقلاع معلقة:
            # ترقية أقدم القلاع المعلقة دفعة واحدة (FIFO بحسب created_at ASC)
            if len(active_castles) < max_allowed and pending_castles:
                free_slots = max_allowed - len(active_castles)
                to_promote = pending_castles[:free_slots]
                for c in to_promote:
                    cid = c["castle_id"]
                    conn.execute(
                        """
                        UPDATE castle_states
                        SET is_active = 1,
                            state = 'idle',
                            conn_state = 'idle',
                            conn_message = 'جاهز للتشغيل',
                            last_run_message = 'جاهز للتشغيل',
                            last_updated = ?
                        WHERE castle_id = ?
                        """,
                        (now_iso, cid)
                    )
                    promoted.append(cid)

            # 2.2 في حال تخفيض الباقة من قبل الإدارة وتجاوز الحد (active > max_allowed):
            # إيقاف أحدث القلاع النشطة الزائدة (LIFO بحسب created_at DESC)
            elif len(active_castles) > max_allowed:
                excess_count = len(active_castles) - max_allowed
                rev_active = list(reversed(active_castles))
                to_demote = rev_active[:excess_count]
                for c in to_demote:
                    cid = c["castle_id"]
                    conn.execute(
                        """
                        UPDATE castle_states
                        SET is_active = 0,
                            state = 'pending',
                            conn_state = 'idle',
                            conn_message = 'تم الإيقاف لتجاوز الحد المسموح به في الباقة',
                            last_updated = ?
                        WHERE castle_id = ?
                        """,
                        (now_iso, cid)
                    )
                    demoted.append(cid)

            # إعادة عد القلاع الفعلية بعد التعديل وحفظها في users
            row_a = conn.execute(
                "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND is_active = 1 AND state != 'pending'",
                (uid,)
            ).fetchone()
            row_p = conn.execute(
                "SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND (is_active = 0 OR state = 'pending')",
                (uid,)
            ).fetchone()
            final_active = row_a["cnt"] if row_a else 0
            final_pending = row_p["cnt"] if row_p else 0

            conn.execute(
                "UPDATE users SET current_castles_count = ?, pending_castles_count = ? WHERE uid = ?",
                (final_active, final_pending, uid)
            )
            conn.commit()

            res["active"] = final_active
            res["pending"] = final_pending
            res["promoted_ids"] = promoted
            res["demoted_ids"] = demoted
            return res
    except Exception as e:
        log.warning(f"⚠️ تعذر مزامنة قلاع وحدود المستخدم ({uid}): {e}")
        return res


def update_user_castle_counts(uid: str, db_path: Optional[str] = None) -> Tuple[int, int]:
    """إعادة حساب عدد القلاع النشطة والمعلقة وتحديثها في جدول المستخدمين (مع دعم محرك المواءمة)."""
    sync_res = sync_user_castles_and_quota(uid, db_path)
    return sync_res.get("active", 0), sync_res.get("pending", 0)


def ban_user(uid: str, ban: bool, reason: str = "", db_path: Optional[str] = None) -> bool:
    """حظر أو رفع حظر مستخدم مع تجميد أو استعادة قلاعه تلقائياً ومزامنتها مع الباقة."""
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            if ban:
                conn.execute(
                    "UPDATE users SET is_banned = 1, banned_reason = ?, subscription_status = 'suspended' WHERE uid = ?",
                    (reason, uid)
                )
            else:
                user_row = conn.execute("SELECT subscription_expires_at FROM users WHERE uid = ?", (uid,)).fetchone()
                restored_status = "active"
                if user_row and user_row["subscription_expires_at"]:
                    try:
                        exp_raw = str(user_row["subscription_expires_at"]).strip().replace("Z", "+00:00")
                        exp_dt = datetime.fromisoformat(exp_raw)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) > exp_dt:
                            restored_status = "expired"
                    except Exception:
                        pass
                conn.execute(
                    "UPDATE users SET is_banned = 0, banned_reason = '', subscription_status = ? WHERE uid = ?",
                    (restored_status, uid)
                )
            conn.commit()

        # مزامنة القلاع والحدود فورياً
        sync_user_castles_and_quota(uid, db_path)
        return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحديث حالة حظر المستخدم ({uid}): {e}")
        return False


def delete_user(uid: str, db_path: Optional[str] = None) -> bool:
    """حذف مستخدم وجميع قلاعه وتنبيهاته تماماً من قاعدة البيانات."""
    _ensure_init(db_path)
    if not uid:
        return False
    clean_uid = uid.strip()

    try:
        with get_connection(db_path) as conn:
            # 1. استخراج بيانات المستخدم للبحث بـ uid والبريد معاً
            u_row = conn.execute(
                "SELECT uid, email FROM users WHERE uid = ? OR lower(email) = ? LIMIT 1",
                (clean_uid, clean_uid.lower())
            ).fetchone()

            user_uid = u_row["uid"] if u_row else clean_uid
            user_email = str(u_row["email"]).strip().lower() if (u_row and u_row["email"]) else ""

            # 2. العثور على جميع إيميلات قلاع هذا المستخدم لحذف تنبيهاتها
            c_rows = conn.execute("""
                SELECT email FROM castle_states 
                WHERE user_id = ? 
                   OR lower(user_id) = ? 
                   OR (length(?) > 0 AND (user_id = ? OR lower(user_id) = ?))
            """, (user_uid, user_uid.lower(), user_email, user_email, user_email)).fetchall()

            castle_emails = [str(r["email"]).strip().lower() for r in c_rows if r["email"]]



            # 4. حذف جميع قلاع المستخدم تماماً من castle_states
            conn.execute("""
                DELETE FROM castle_states 
                WHERE user_id = ? 
                   OR lower(user_id) = ? 
                   OR (length(?) > 0 AND (user_id = ? OR lower(user_id) = ?))
            """, (user_uid, user_uid.lower(), user_email, user_email, user_email))

            # 5. حذف المستخدم نفسه من users
            conn.execute(
                "DELETE FROM users WHERE uid = ? OR lower(email) = ? OR lower(uid) = ?",
                (user_uid, user_email if user_email else user_uid.lower(), clean_uid.lower())
            )

            conn.commit()
            log.info(f"🗑️ تم حذف المستخدم ({clean_uid}) وجميع قلاعه ({len(castle_emails)} قلعة) وتنبيهاته من SQLite.")
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر حذف المستخدم ({uid}): {e}")
        return False


def check_user_subscription_db(uid: str, db_path: Optional[str] = None) -> Tuple[bool, str]:
    """التحقق من صلاحية اشتراك المستخدم وحالة الحظر محلياً من SQLite."""
    _ensure_init(db_path)
    user = get_user(uid, db_path)
    if not user:
        return False, "المستخدم غير موجود في النظام"

    # المشرف الأعلى
    if user.get("role") == "admin" and str(user.get("email", "")).strip().lower() == "ibraboths@gmail.com":
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
    if isinstance(cfg, dict):
        cfg = _sanitize_castle_config(cfg)
        config_json = json.dumps(cfg, ensure_ascii=False)
    else:
        config_json = str(cfg or "{}")

    try:
        with get_connection(db_path) as conn:
            conn.execute("""
            INSERT INTO castle_states (
                castle_id, email, user_id, password, config, is_active, created_at, state, conn_state, conn_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(castle_id) DO UPDATE SET
                email = excluded.email,
                user_id = castle_states.user_id,
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


def get_castle_proxy_index(email: str, db_path: Optional[str] = None) -> Optional[int]:
    """استرجاع مؤشر البروكسي (proxy_index) المحفوظ للقلعة في قاعدة البيانات."""
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return None
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT proxy_index FROM castle_states WHERE lower(email) = ? LIMIT 1",
                (clean_email,)
            ).fetchone()
            if row and row[0] is not None and row[0] >= 0:
                return int(row[0])
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء قراءة proxy_index للقلعة ({clean_email}): {e}")
    return None


def set_castle_proxy_index(email: str, proxy_index: int, db_path: Optional[str] = None) -> bool:
    """حفظ أو تحديث مؤشر البروكسي (proxy_index) للقلعة في قاعدة البيانات."""
    clean_email = (email or "").strip().lower()
    if not clean_email or proxy_index is None:
        return False
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "UPDATE castle_states SET proxy_index = ? WHERE lower(email) = ?",
                (int(proxy_index), clean_email)
            )
            if cur.rowcount == 0 and int(proxy_index) >= 0:
                conn.execute(
                    """
                    INSERT INTO castle_states (castle_id, email, proxy_index, created_at)
                    VALUES (?, ?, ?, datetime('now'))
                    ON CONFLICT(castle_id) DO UPDATE SET proxy_index = excluded.proxy_index
                    """,
                    (clean_email, clean_email, int(proxy_index))
                )
            conn.commit()
            return True
    except Exception as e:
        log.warning(f"⚠️ تعذر حفظ proxy_index للقلعة ({clean_email}): {e}")
        return False


def get_user_proxy_index(user_id: str, db_path: Optional[str] = None) -> Optional[int]:
    """استرجاع مؤشر البروكسي الخاص بأي قلعة تابعة لنفس المستخدم لتوحيد البروكسي بينهم."""
    clean_uid = (user_id or "").strip()
    if not clean_uid:
        return None
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT proxy_index FROM castle_states WHERE (user_id = ? OR lower(user_id) = ?) AND proxy_index >= 0 LIMIT 1",
                (clean_uid, clean_uid.lower())
            ).fetchone()
            if row and row[0] is not None and row[0] >= 0:
                return int(row[0])
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء قراءة proxy_index للمستخدم ({clean_uid}): {e}")
    return None


def get_all_castle_proxy_counts(total_proxies: int, db_path: Optional[str] = None) -> Dict[int, int]:
    """حساب عدد القلاع المربوطة بكل مؤشر بروكسي (0..total_proxies-1) لتحقيق توزيع متوازن."""
    counts = {i: 0 for i in range(total_proxies)}
    if total_proxies <= 0:
        return counts
    _ensure_init(db_path)
    try:
        with get_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT proxy_index, count(*) FROM castle_states WHERE proxy_index >= 0 GROUP BY proxy_index"
            ).fetchall()
            for r in rows:
                raw_idx = int(r[0])
                safe_idx = raw_idx % total_proxies
                counts[safe_idx] = counts.get(safe_idx, 0) + int(r[1])
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء حساب حمولة مؤشرات البروكسي: {e}")
    return counts


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


def get_castle_config(castle_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """جلب إعدادات قلعة محددة فقط عند الطلب (بدون بيانات حساسة)."""
    if not castle_id:
        return None
    _ensure_init(db_path)
    clean_cid = str(castle_id).strip()
    try:
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT castle_id, user_id, email, config, is_active, state, conn_state, conn_message, next_run_time FROM castle_states WHERE castle_id = ? OR lower(email) = ? LIMIT 1",
                (clean_cid, clean_cid.lower())
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["config"] = json.loads(d.get("config") or "{}") if isinstance(d.get("config"), str) else (d.get("config") or {})
            except Exception:
                d["config"] = {}
            return d
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب إعدادات القلعة ({castle_id}): {e}")
        return None


def get_admin_castles_paginated(
    page: Optional[int] = 1,
    page_size: Optional[int] = 25,
    search: str = "",
    filter_status: str = "all",
    tenant_domains: Optional[List[str]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    استعلام ترقيم متقدم لقلاع ومستخدمي لوحة الإدارة يعتمد LIMIT و OFFSET و COUNT(*)
    مع تصفية دقيقة حسب المستأجر (Tenant) وحالة القلاع والبحث النصي،
    مع استبعاد عمود config و raw_json الثقيلين لتسريع الاستجابة وخفض استهلاك الذاكرة.
    """
    _ensure_init(db_path)

    if hasattr(page, "default"):
        page = page.default
    if hasattr(page_size, "default"):
        page_size = page_size.default
    if hasattr(search, "default"):
        search = search.default
    if hasattr(filter_status, "default"):
        filter_status = filter_status.default

    # 1. ضبط قيم الترقيم
    is_paginated = False
    ps = None
    if page_size is not None:
        try:
            ps_val = int(page_size)
            if ps_val > 0:
                is_paginated = True
                ps = max(1, min(ps_val, 500))
        except (ValueError, TypeError):
            is_paginated = False

    p = 1
    if page is not None:
        try:
            p = max(1, int(page))
        except (ValueError, TypeError):
            p = 1

    offset = (p - 1) * ps if (is_paginated and ps) else 0

    clean_search = str(search or "").strip().lower()
    clean_filter = str(filter_status or "all").strip().lower()

    where_clauses: List[str] = []
    params: List[Any] = []

    # 2. عزل بيانات التجار (Tenant isolation)
    if tenant_domains is not None:
        valid_domains = [d.strip().lower() for d in tenant_domains if d and d.strip()]
        if valid_domains:
            placeholders = ", ".join("?" for _ in valid_domains)
            where_clauses.append(f"lower(coalesce(u.tenant_domain, '')) IN ({placeholders})")
            params.extend(valid_domains)
        else:
            where_clauses.append("1 = 0")

    # 3. شرط البحث النصي
    if clean_search:
        like_term = f"%{clean_search}%"
        search_sql = (
            "("
            "lower(u.email) LIKE ? OR "
            "lower(coalesce(u.username, '')) LIKE ? OR "
            "lower(u.uid) LIKE ? OR "
            "EXISTS ("
            "  SELECT 1 FROM castle_states cs_s "
            "  WHERE (cs_s.user_id = u.uid OR lower(cs_s.user_id) = lower(u.email)) "
            "    AND (lower(cs_s.email) LIKE ? OR lower(cs_s.castle_id) LIKE ? OR lower(coalesce(cs_s.castle_name, '')) LIKE ? OR lower(coalesce(cs_s.lord_name, '')) LIKE ?)"
            ")"
            ")"
        )
        where_clauses.append(search_sql)
        params.extend([like_term, like_term, like_term, like_term, like_term, like_term, like_term])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # 4. شرط الفلترة (HAVING clause على مستوى المستخدم بعد التجميع)
    having_clause = ""
    if clean_filter == "with_castles":
        having_clause = "HAVING count(distinct cs.castle_id) > 0"
    elif clean_filter == "no_castles":
        having_clause = "HAVING count(distinct cs.castle_id) = 0"
    elif clean_filter == "running":
        having_clause = "HAVING count(distinct case when cs.state in ('running', 'waiting', 'reconnecting', 'connected') or (cs.is_active = 1 and cs.state != 'idle' and cs.state != 'error') then cs.castle_id end) > 0"

    try:
        with get_connection(db_path) as conn:
            # أولاً: حساب إجمالي عدد المستخدمين المطابقين للشرط
            count_query = f"""
            SELECT count(*) AS total_count FROM (
                SELECT u.uid
                FROM users u
                LEFT JOIN castle_states cs ON (cs.user_id = u.uid OR lower(cs.user_id) = lower(u.email))
                {where_sql}
                GROUP BY u.uid
                {having_clause}
            )
            """
            cur_count = conn.execute(count_query, params)
            count_row = cur_count.fetchone()
            total_count = int(count_row["total_count"]) if count_row else 0

            # ثانياً: استعلام إحصائيات النظام الشاملة (Summary Stats)
            stats_params: List[Any] = []
            stats_where = ""
            if tenant_domains is not None:
                valid_domains = [d.strip().lower() for d in tenant_domains if d and d.strip()]
                if valid_domains:
                    ph = ", ".join("?" for _ in valid_domains)
                    stats_where = f"WHERE lower(coalesce(u.tenant_domain, '')) IN ({ph})"
                    stats_params.extend(valid_domains)
                else:
                    stats_where = "WHERE 1 = 0"

            stats_query = f"""
            SELECT
                count(distinct u.uid) as total_users,
                count(distinct cs.castle_id) as total_castles,
                count(distinct case when cs.state in ('running', 'waiting', 'reconnecting', 'connected') or (cs.is_active = 1 and cs.state != 'idle' and cs.state != 'error') then cs.castle_id end) as total_running
            FROM users u
            LEFT JOIN castle_states cs ON (cs.user_id = u.uid OR lower(cs.user_id) = lower(u.email))
            {stats_where}
            """
            cur_stats = conn.execute(stats_query, stats_params)
            stats_row = cur_stats.fetchone()
            summary_stats = {
                "total_users": int(stats_row["total_users"]) if stats_row and stats_row["total_users"] else 0,
                "total_castles": int(stats_row["total_castles"]) if stats_row and stats_row["total_castles"] else 0,
                "total_running": int(stats_row["total_running"]) if stats_row and stats_row["total_running"] else 0,
            }

            # ثالثاً: استعلام صفحة المستخدمين
            page_params = list(params)
            limit_clause = ""
            if is_paginated:
                limit_clause = "LIMIT ? OFFSET ?"
                page_params.extend([ps, offset])

            page_query = f"""
            SELECT 
                u.uid,
                u.email,
                u.username,
                u.phone,
                u.role,
                u.is_banned,
                u.created_at,
                u.tenant_domain,
                u.plan_id,
                u.plan_name,
                u.subscription_status,
                u.subscription_expires_at,
                u.max_castles_allowed,
                count(distinct cs.castle_id) as castles_count,
                count(distinct case when cs.state in ('running', 'waiting', 'reconnecting', 'connected') or (cs.is_active = 1 and cs.state != 'idle' and cs.state != 'error') then cs.castle_id end) as running_count,
                count(distinct case when cs.is_active = 0 or cs.state = 'pending' then cs.castle_id end) as pending_count
            FROM users u
            LEFT JOIN castle_states cs ON (cs.user_id = u.uid OR lower(cs.user_id) = lower(u.email))
            {where_sql}
            GROUP BY u.uid
            {having_clause}
            ORDER BY coalesce(u.created_at, '') DESC, u.uid DESC
            {limit_clause}
            """
            cur_page = conn.execute(page_query, page_params)
            user_rows = cur_page.fetchall()

            # رابعاً: جلب معاينات القلاع الخفيفة للمستخدمين في هذه الصفحة فقط
            target_uids = [row["uid"] for row in user_rows]
            target_emails = [str(row["email"]).lower() for row in user_rows if row["email"]]

            previews_by_user: Dict[str, List[Dict[str, Any]]] = {}
            if target_uids or target_emails:
                u_conds = []
                u_params = []
                if target_uids:
                    ph_uids = ", ".join("?" for _ in target_uids)
                    u_conds.append(f"user_id IN ({ph_uids})")
                    u_params.extend(target_uids)
                if target_emails:
                    ph_ems = ", ".join("?" for _ in target_emails)
                    u_conds.append(f"lower(user_id) IN ({ph_ems})")
                    u_params.extend(target_emails)

                preview_sql = f"""
                SELECT castle_id, user_id, email, is_active, state, conn_state, castle_name, lord_name
                FROM castle_states
                WHERE {" OR ".join(u_conds)}
                ORDER BY created_at DESC
                """
                cur_prev = conn.execute(preview_sql, u_params)
                for prow in cur_prev.fetchall():
                    cid = str(prow["castle_id"])
                    uid_val = str(prow["user_id"] or "").strip()
                    em_val = str(prow["email"] or "").strip().lower()
                    prev_entry = {
                        "id": cid,
                        "email": em_val,
                    }
                    if uid_val:
                        previews_by_user.setdefault(uid_val, []).append(prev_entry)
                    if em_val and em_val != uid_val:
                        previews_by_user.setdefault(em_val, []).append(prev_entry)

            # خامساً: تجميع النتيجة النهائية
            users_list: List[Dict[str, Any]] = []
            for u in user_rows:
                uid_str = str(u["uid"]).strip()
                email_str = str(u["email"] or "").strip()
                email_lower = email_str.lower()

                u_previews = previews_by_user.get(uid_str) or previews_by_user.get(email_lower) or []
                seen_cids = set()
                unique_previews = []
                for prev in u_previews:
                    cid = prev.get("id") or prev.get("castle_id")
                    if cid and cid not in seen_cids:
                        seen_cids.add(cid)
                        unique_previews.append(prev)

                is_super = (u["role"] == "admin" and email_lower == "ibraboths@gmail.com")
                is_banned = bool(u["is_banned"])
                c_cnt = int(u["castles_count"] or 0)
                r_cnt = int(u["running_count"] or 0)
                p_cnt = int(u["pending_count"] or 0)

                user_obj = {
                    "uid": uid_str,
                    "email": email_str,
                    "display_name": u["username"] or (email_str.split("@")[0] if email_str else "User"),
                    "role": u["role"] or "user",
                    "is_banned": is_banned,
                    "created_at": u["created_at"] or "",
                    "tenant_domain": u["tenant_domain"] or "",
                    "subscription": {
                        "plan_id": "super_admin_unlimited" if is_super else (u["plan_id"] or "basic"),
                        "plan_name": "باقة المشرف الأعلى" if is_super else (u["plan_name"] or "باقة أساسية"),
                        "status": "active" if is_super else ("suspended" if is_banned else (u["subscription_status"] or "active")),
                        "expires_at": "2099-01-01T00:00:00Z" if is_super else (u["subscription_expires_at"] or ""),
                        "max_castles_allowed": 999999 if is_super else (u["max_castles_allowed"] or 0),
                    },
                    "castle_count": c_cnt,
                    "castles_count": c_cnt,
                    "active_count": r_cnt,
                    "running_count": r_cnt,
                    "pending_count": p_cnt,
                    "castle_previews": unique_previews,
                }
                users_list.append(user_obj)

            total_pages = max(1, (total_count + ps - 1) // ps) if is_paginated and ps else 1
            has_more = (p < total_pages) if is_paginated else False

            return {
                "items": users_list,
                "users": users_list,
                "total": total_count,
                "total_count": total_count,
                "page": p,
                "page_size": ps if is_paginated else total_count,
                "total_pages": total_pages,
                "has_more": has_more,
                "summary_stats": summary_stats,
            }

    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء استعلام ترقيم قلاع المشرفين: {e}")
        return {
            "items": [],
            "users": [],
            "total": 0,
            "total_count": 0,
            "page": p,
            "page_size": ps or 25,
            "total_pages": 1,
            "has_more": False,
            "summary_stats": {"total_users": 0, "total_castles": 0, "total_running": 0},
        }


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


def _sanitize_castle_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """تعقيم وتطهير إعدادات القلعة لضمان سلامة القيم ومطابقتها لقواعد اللعبة الرسمية."""
    if not isinstance(cfg, dict):
        return cfg
    VALID_RUINS_EXPLORE_TIMES = (900, 3600, 14400, 28800)
    mm_cfg = cfg.get("march_manager")
    if isinstance(mm_cfg, dict):
        # 1. ترحيل إعدادات abra من المستوى العام إلى داخل march_manager إن وُجدت
        if "abra" in cfg:
            top_abra = cfg.pop("abra")
            if isinstance(top_abra, dict):
                if "abra" not in mm_cfg or not isinstance(mm_cfg.get("abra"), dict):
                    mm_cfg["abra"] = top_abra
                else:
                    for ak, av in top_abra.items():
                        if ak not in mm_cfg["abra"]:
                            mm_cfg["abra"][ak] = av

        # عزل إعدادات العفريت تماماً في جذر config وحذفها من march_manager
        if "elf" in mm_cfg:
            mm_elf = mm_cfg.pop("elf")
            if isinstance(mm_elf, dict) and "elf" not in cfg:
                cfg["elf"] = mm_elf

        ruins_cfg = mm_cfg.get("ruins")
        if isinstance(ruins_cfg, dict) and "explore_time" in ruins_cfg:
            try:
                raw_t = int(ruins_cfg["explore_time"])
                if raw_t not in VALID_RUINS_EXPLORE_TIMES:
                    ruins_cfg["explore_time"] = min(VALID_RUINS_EXPLORE_TIMES, key=lambda x: abs(x - raw_t))
            except (ValueError, TypeError):
                ruins_cfg["explore_time"] = 900

    sb_cfg = cfg.get("savings_bank")
    if isinstance(sb_cfg, dict) and "deposit" in sb_cfg:
        try:
            d_val = int(sb_cfg["deposit"])
            sb_cfg["deposit"] = max(100, min(6000, d_val))
        except (ValueError, TypeError):
            sb_cfg["deposit"] = 2000
    return cfg


class OCCResult(dict):
    """قاموس يدعم التقييم المنطقي boolean بناءً على نجاح العملية للتوافق العكسي الكامل."""
    def __bool__(self) -> bool:
        return bool(self.get("success", False))


def update_castle_config(
    castle_id: str,
    config_dict: Dict[str, Any],
    user_id: Optional[Any] = None,
    expected_version: Optional[int] = None,
    db_path: Optional[str] = None
) -> OCCResult:
    """
    تحديث إعدادات المهام لقلعة محددة مع الدمج التكراري (Deep Merge) والتحكم بالتعديلات المتزامنة (OCC).
    يستخدم معاملة ذرية BEGIN IMMEDIATE لمنع التضارب وضمان عدم فقدان أي تحديثات (Zero Lost Updates).
    إذا تم تقديم expected_version، يتم التحقق من تطابقه مع النسخة الحالية، وتُرفض العملية عند التعارض.
    """
    if isinstance(user_id, int) and expected_version is None:
        expected_version = user_id
        user_id = None

    _ensure_init(db_path)
    if not castle_id or config_dict is None:
        return OCCResult({"success": False, "error": "Invalid arguments: castle_id or config_dict missing"})

    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        conn.execute("BEGIN IMMEDIATE")

        # 1. جلب الإعدادات والنسخة الحالية للقلعة
        if user_id:
            cur = conn.execute(
                "SELECT config, version FROM castle_states WHERE castle_id = ? AND user_id = ?",
                (castle_id, user_id)
            )
        else:
            cur = conn.execute(
                "SELECT config, version FROM castle_states WHERE castle_id = ?",
                (castle_id,)
            )
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return OCCResult({"success": False, "error": f"Castle {castle_id} not found"})

        row_dict = dict(row)
        current_version = int(row_dict.get("version") or 1)

        # 2. فحص التعارض التزامني (Optimistic Concurrency Control)
        if expected_version is not None:
            if current_version != int(expected_version):
                conn.rollback()
                return OCCResult({
                    "success": False,
                    "conflict": True,
                    "current_version": current_version,
                    "expected_version": int(expected_version),
                    "error": f"Concurrency conflict: expected version {expected_version}, but current version is {current_version}"
                })

        # 3. دمج التعديلات وتطهيرها
        current_config: Dict[str, Any] = {}
        if row_dict.get("config"):
            try:
                loaded = json.loads(row_dict["config"])
                if isinstance(loaded, dict):
                    current_config = loaded
            except Exception:
                current_config = {}

        merged_config = _sanitize_castle_config(_deep_merge_dict(current_config, config_dict))
        config_json = json.dumps(merged_config, ensure_ascii=False)
        new_version = current_version + 1
        now_iso = datetime.now(timezone.utc).isoformat()

        # 4. تحديث ذري وزيادة رقم النسخة
        if user_id:
            conn.execute(
                "UPDATE castle_states SET config = ?, version = ?, last_updated = ? WHERE castle_id = ? AND user_id = ?",
                (config_json, new_version, now_iso, castle_id, user_id)
            )
        else:
            conn.execute(
                "UPDATE castle_states SET config = ?, version = ?, last_updated = ? WHERE castle_id = ?",
                (config_json, new_version, now_iso, castle_id)
            )

        conn.commit()
        return OCCResult({"success": True, "version": new_version, "config": merged_config})
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        log.warning(f"⚠️ تعذر تحديث إعدادات القلعة ({castle_id}): {e}")
        return OCCResult({"success": False, "error": str(e)})
    finally:
        conn.close()


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


def update_castles_loop_interval(updates: Dict[str, int], user_id: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """
    تحديث مدة دورة البوت (loop_interval) لمجموعة قلاع دفعة واحدة في معاملة ذرية.
    updates: {castle_id: interval_minutes} (محصور بين 30 و 180 دقيقة).
    """
    _ensure_init(db_path)
    if not updates:
        return True
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection(db_path) as conn:
            for cid, raw_interval in updates.items():
                try:
                    val = max(30, min(180, int(raw_interval)))
                except (ValueError, TypeError):
                    val = 40
                if user_id:
                    conn.execute(
                        "UPDATE castle_states SET loop_interval = ?, last_updated = ? WHERE castle_id = ? AND user_id = ?",
                        (val, now_iso, str(cid).strip(), str(user_id).strip())
                    )
                else:
                    conn.execute(
                        "UPDATE castle_states SET loop_interval = ?, last_updated = ? WHERE castle_id = ?",
                        (val, now_iso, str(cid).strip())
                    )
            conn.commit()
        return True
    except Exception as e:
        log.error(f"⚠️ خطأ أثناء تحديث loop_interval للقلاع: {e}")
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

    # تحديد الحالة التشغيلية العامة (running / idle / error)
    general_state = "idle"
    if conn_state in ("connected", "reconnecting", "disconnected", "waiting"):
        general_state = "running"
    elif conn_state == "idle":
        general_state = "idle"
    elif conn_state == "error":
        general_state = "error"

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
                    now_iso,
                    target_cid
                ))
            else:
                # القلعة غير موجودة أو محذوفة — تخطي التحديث لمنع إعادة إحياء القلاع المحذوفة
                log.debug(f"تخطي تحديث حالة قلعة غير موجودة أو محذوفة: {clean_email}")
                return False
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

    unprotected_food = int(resources.get("unprotected_food", 0) or 0)
    unprotected_wood = int(resources.get("unprotected_wood", 0) or 0)
    unprotected_iron = int(resources.get("unprotected_iron", 0) or 0)
    unprotected_diamond = int(resources.get("unprotected_diamond", 0) or 0)

    safe_food = int(resources.get("safe_food", 0) or 0)
    safe_wood = int(resources.get("safe_wood", 0) or 0)
    safe_iron = int(resources.get("safe_iron", 0) or 0)
    safe_diamond = int(resources.get("safe_diamond", 0) or 0)

    lord_name = str(cinfo.get("lord_name", "")) if cinfo.get("lord_name") else None
    lord_power = int(cinfo.get("lord_power", 0) or 0)
    castle_level = int(cinfo.get("castle_level", 1) or 1)
    walls_level = int(cinfo.get("walls_level", 0) or 0)
    server_id = int(cinfo.get("server_id", 1) or 1)
    coords = cinfo.get("coordinates") or {}
    coord_x = int(coords.get("x", 0) or 0) if isinstance(coords, dict) else 0
    coord_y = int(coords.get("y", 0) or 0) if isinstance(coords, dict) else 0
    avatar = str(cinfo.get("avatar", "") or "")
    image_id = int(cinfo.get("image_id", 0) or 0)

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
                    unprotected_food = ?,
                    unprotected_wood = ?,
                    unprotected_iron = ?,
                    unprotected_diamond = ?,
                    safe_food = ?,
                    safe_wood = ?,
                    safe_iron = ?,
                    safe_diamond = ?,
                    lord_name = COALESCE(?, lord_name),
                    lord_power = CASE WHEN ? > 0 THEN ? ELSE lord_power END,
                    castle_level = CASE WHEN ? > 1 THEN ? ELSE castle_level END,
                    walls_level = CASE WHEN ? > 0 THEN ? ELSE walls_level END,
                    server_id = CASE WHEN ? > 0 THEN ? ELSE server_id END,
                    coord_x = CASE WHEN ? > 0 THEN ? ELSE coord_x END,
                    coord_y = CASE WHEN ? > 0 THEN ? ELSE coord_y END,
                    avatar = CASE WHEN ? != '' THEN ? ELSE avatar END,
                    image_id = CASE WHEN ? > 0 THEN ? ELSE image_id END,
                    last_updated = ?
                WHERE castle_id = ?
                """, (
                    food, wood, iron, diamond, gold, stamina,
                    unprotected_food, unprotected_wood, unprotected_iron, unprotected_diamond,
                    safe_food, safe_wood, safe_iron, safe_diamond,
                    lord_name,
                    lord_power, lord_power,
                    castle_level, castle_level,
                    walls_level, walls_level,
                    server_id, server_id,
                    coord_x, coord_x,
                    coord_y, coord_y,
                    avatar, avatar,
                    image_id, image_id,
                    now_iso,
                    target_cid
                ))
            else:
                # القلعة غير موجودة أو محذوفة — تخطي التحديث لمنع إعادة إحياء القلاع المحذوفة
                log.debug(f"تخطي تحديث موارد قلعة غير موجودة أو محذوفة: {clean_email}")
                return False
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
                d = dict(row)
                d.pop("password", None)
                d.pop("raw_json", None)
                try:
                    d["config"] = json.loads(d.get("config") or "{}") if isinstance(d.get("config"), str) else (d.get("config") or {})
                except Exception:
                    d["config"] = {}
                d["is_active"] = bool(d.get("is_active", 1))
                result.append(d)
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


def get_admin_stats(tenant_domains: Optional[List[str]] = None, db_path: Optional[str] = None) -> Dict[str, int]:
    """إحصائيات لوحة الإدارة (مع دعم تصفية التاجر حسب الدومين)."""
    _ensure_init(db_path)
    try:
        from core.tenants import get_all_merchants, DEFAULT_TENANT
        admin_emails = [DEFAULT_TENANT["admin_email"].strip().lower()]
        for m in get_all_merchants():
            ae = (m.get("admin_email") or "").strip().lower()
            if ae and ae not in admin_emails:
                admin_emails.append(ae)

        with get_connection(db_path) as conn:
            email_placeholders = ",".join("?" for _ in admin_emails)
            user_where = f"role NOT IN ('admin', 'merchant_admin') AND LOWER(email) NOT IN ({email_placeholders})"
            user_params: List[Any] = list(admin_emails)
            castle_where = "is_active = 1 AND state != 'pending'"
            castle_params: List[Any] = []

            if tenant_domains is not None:
                cleaned_domains = [d.strip().lower() for d in tenant_domains if d.strip()]
                if cleaned_domains:
                    placeholders = ",".join("?" for _ in cleaned_domains)
                    user_where += f" AND LOWER(tenant_domain) IN ({placeholders})"
                    user_params.extend(cleaned_domains)
                    castle_where += f" AND user_id IN (SELECT uid FROM users WHERE LOWER(tenant_domain) IN ({placeholders}))"
                    castle_params.extend(cleaned_domains)
                else:
                    user_where += " AND 1=0"
                    castle_where += " AND 1=0"

            total_users = conn.execute(
                f"SELECT COUNT(*) as cnt FROM users WHERE {user_where}",
                user_params
            ).fetchone()["cnt"]

            active_subs_where = f"subscription_status = 'active' AND {user_where}"
            active_subs = conn.execute(
                f"SELECT COUNT(*) as cnt FROM users WHERE {active_subs_where}",
                user_params
            ).fetchone()["cnt"]

            pending_where = f"subscription_status = 'pending_approval' AND {user_where}"
            pending_users = conn.execute(
                f"SELECT COUNT(*) as cnt FROM users WHERE {pending_where}",
                user_params
            ).fetchone()["cnt"]

            total_castles = conn.execute(
                f"SELECT COUNT(*) as cnt FROM castle_states WHERE {castle_where}",
                castle_params
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


def get_all_users_with_castles(tenant_domains: Optional[List[str]] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """جلب المستخدمين مع عدد قلاعهم الفعلي (للإدارة، مع إمكانية الفلترة للتاجر) عبر استعلام SQL تجميعي واحد."""
    _ensure_init(db_path)
    result: List[Dict[str, Any]] = []
    try:
        from core.tenants import get_all_merchants, DEFAULT_TENANT
        admin_emails = [DEFAULT_TENANT["admin_email"].strip().lower()]
        for m in get_all_merchants():
            ae = (m.get("admin_email") or "").strip().lower()
            if ae and ae not in admin_emails:
                admin_emails.append(ae)

        with get_connection(db_path) as conn:
            email_placeholders = ",".join("?" for _ in admin_emails)
            base_where = f"u.role NOT IN ('admin', 'merchant_admin') AND LOWER(u.email) NOT IN ({email_placeholders})"
            params: List[Any] = list(admin_emails)

            clean_domains = [d.strip().lower() for d in tenant_domains if d and d.strip()] if tenant_domains else []
            if clean_domains:
                placeholders = ",".join("?" for _ in clean_domains)
                where_clause = f"WHERE {base_where} AND LOWER(u.tenant_domain) IN ({placeholders})"
                params.extend(clean_domains)
            else:
                where_clause = f"WHERE {base_where}"

            query = f"""
                SELECT 
                    u.*,
                    COALESCE(c.active_cnt, 0) as _agg_active,
                    COALESCE(c.pending_cnt, 0) as _agg_pending,
                    COALESCE(c.total_cnt, 0) as _agg_total
                FROM users u
                LEFT JOIN (
                    SELECT 
                        user_id,
                        SUM(CASE WHEN is_active = 1 AND (state != 'pending' OR state IS NULL) THEN 1 ELSE 0 END) as active_cnt,
                        SUM(CASE WHEN is_active = 0 OR state = 'pending' THEN 1 ELSE 0 END) as pending_cnt,
                        COUNT(*) as total_cnt
                    FROM castle_states
                    WHERE user_id IS NOT NULL AND user_id != ''
                    GROUP BY user_id
                ) c ON u.uid = c.user_id
                {where_clause}
                ORDER BY u.created_at DESC
            """
            cur = conn.execute(query, params)
            for row in cur.fetchall():
                d = dict(row)
                is_banned = bool(d.get("is_banned", 0))
                d["is_banned"] = is_banned

                active_cnt = int(d.pop("_agg_active", 0) or 0)
                pending_cnt = int(d.pop("_agg_pending", 0) or 0)
                total_cnt = int(d.pop("_agg_total", 0) or 0)

                d["current_castles_count"] = 0 if is_banned else active_cnt
                d["pending_castles_count"] = total_cnt if is_banned else pending_cnt
                d["total_castles_count"] = total_cnt

                # توفير المفاتيح البديلة للتوافقية الكاملة
                d["active_castles"] = d["current_castles_count"]
                d["pending_castles"] = d["pending_castles_count"]
                d["total_castles"] = d["total_castles_count"]

                is_super = d.get("role") == "admin" and str(d.get("email", "")).strip().lower() == "ibraboths@gmail.com"
                d["subscription"] = {
                    "plan_id": "super_admin_unlimited" if is_super else d.get("plan_id", "pending_trial"),
                    "plan_name": "باقة المشرف الأعلى (غير محدود)" if is_super else d.get("plan_name", "بانتظار موافقة الإدارة"),
                    "status": "active" if is_super else ("suspended" if is_banned else d.get("subscription_status", "pending_approval")),
                    "started_at": d.get("subscription_started_at", ""),
                    "expires_at": "2099-01-01T00:00:00Z" if is_super else d.get("subscription_expires_at", ""),
                    "max_castles_allowed": 999999 if is_super else d.get("max_castles_allowed", 0),
                    "current_castles_count": d["current_castles_count"],
                    "pending_castles_count": d["pending_castles_count"],
                    "total_castles_count": d["total_castles_count"],
                }
                result.append(d)
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء جلب عدد القلاع: {e}")
    return result


def get_merchants_overview_stats(merchants: List[Dict[str, Any]], db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """جلب إحصائيات التجار الشاملة (عدد المستخدمين، إجمالي القلاع، والقلاع الشغالة الآن)."""
    _ensure_init(db_path)
    overview = []
    try:
        with get_connection(db_path) as conn:
            for m in merchants:
                m_id = m.get("id", "")
                domains = [d.strip().lower() for d in m.get("domains", []) if d.strip()]
                if not domains:
                    continue
                placeholders = ",".join("?" for _ in domains)
                
                # 1. عدد المستخدمين التابعين لهذا الدومين (استبعاد حساب المشرف)
                admin_mail = m.get("admin_email", "").strip().lower()
                row_u = conn.execute(
                    f"SELECT COUNT(*) as u_cnt FROM users WHERE LOWER(tenant_domain) IN ({placeholders}) AND role NOT IN ('admin', 'merchant_admin') AND LOWER(email) != ?",
                    domains + [admin_mail]
                ).fetchone()
                user_count = row_u["u_cnt"] if row_u else 0

                # 2. إجمالي القلاع والقلاع الشغالة الآن
                row_c = conn.execute(
                    f"""
                    SELECT 
                        COUNT(c.castle_id) as total_castles,
                        COUNT(CASE WHEN c.state = 'running' OR c.conn_state = 'connected' THEN 1 END) as running_castles
                    FROM castle_states c
                    JOIN users u ON u.uid = c.user_id
                    WHERE LOWER(u.tenant_domain) IN ({placeholders})
                    """,
                    domains
                ).fetchone()
                total_castles = row_c["total_castles"] if row_c else 0
                running_castles = row_c["running_castles"] if row_c else 0

                overview.append({
                    "id": m_id,
                    "brand_name": m.get("brand_name", m.get("name", "")),
                    "domains": domains,
                    "primary_domain": domains[0] if domains else "",
                    "admin_email": m.get("admin_email", ""),
                    "primary_color": m.get("primary_color", "#10b981"),
                    "tagline": m.get("tagline", ""),
                    "total_users": user_count,
                    "total_castles": total_castles,
                    "running_castles": running_castles,
                })
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء حساب إحصائيات التجار: {e}")
    return overview


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





