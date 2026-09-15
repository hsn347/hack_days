# -*- coding: utf-8 -*-
"""
core/database.py — قاعدة بيانات SQLite محلية خفيفة وسريعة (castles.db)
════════════════════════════════════════════════════════════════════════
يوفر هذا الملف:
  1. إدارة كاش محلي فائق السرعة لحالات القلاع ومواردها جنباً إلى جنب مع Firebase.
  2. دعم نمط WAL (Write-Ahead Logging) لضمان القراءة والكتابة المتزامنة بدون أي أقفال أو تأخير.
  3. دوال Upsert بسيطة ومرنة ومحمية من أخطاء الاتصال أو استثناءات المعالجة.
  4. استعلامات سريعة لاسترجاع حالة قلعة معينة أو كافة القلاع بلمح البصر.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger("LocalDB")

# المسار الافتراضي لملف قاعدة البيانات في المجلد الرئيسي للمشروع
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "castles.db")

# قفل لمنع التضارب عند التهيئة المبدئية داخل نفس العملية
_init_lock = threading.Lock()
_db_initialized = False


def get_db_path(custom_path: Optional[str] = None) -> str:
    """الحصول على مسار ملف قاعدة البيانات المعتمد."""
    return custom_path or os.getenv("CASTLES_DB_PATH") or DEFAULT_DB_PATH


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
    """تهيئة وإنشاء جدول القلاع والفهارس إن لم تكن موجودة."""
    global _db_initialized
    with _init_lock:
        try:
            with get_connection(db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS castle_states (
                    castle_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    user_id TEXT,
                    lord_name TEXT,
                    lord_power INTEGER DEFAULT 0,
                    castle_level INTEGER DEFAULT 1,
                    walls_level INTEGER DEFAULT 0,
                    server_id INTEGER DEFAULT 1,
                    coord_x INTEGER DEFAULT 0,
                    coord_y INTEGER DEFAULT 0,
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
                conn.commit()
            _db_initialized = True
        except Exception as e:
            log.warning(f"⚠️ خطأ أثناء تهيئة قاعدة البيانات المحلية: {e}")


def _ensure_init(db_path: Optional[str] = None) -> None:
    """التأكد التلقائي من تهيئة قاعدة البيانات قبل أول عملية."""
    if not _db_initialized:
        init_db(db_path)


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
            cur = conn.execute(
                "DELETE FROM castle_states WHERE lower(email) = ? OR lower(castle_id) = ?",
                (clean_id, clean_id)
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء حذف القلعة محلياً ({identifier}): {e}")
        return False


def sync_from_firebase_to_db(service_account_path: Optional[str] = None, db_path: Optional[str] = None) -> int:
    """
    مزامنة فورية لجلب كافة القلاع وحالاتها ومواردها المسجلة في Firebase وحفظها محلياً في SQLite.
    تعيد عدد القلاع التي تمت مزامنتها بنجاح.
    """
    _ensure_init(db_path)
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fb_fs
        try:
            firebase_admin.get_app()
        except ValueError:
            sak = service_account_path or os.path.join(_BASE_DIR, "firebase_service_account.json")
            if os.path.exists(sak):
                firebase_admin.initialize_app(credentials.Certificate(sak))

        if not firebase_admin._apps:
            log.warning("⚠️ Firebase غير مهيأ، تعذر المزامنة")
            return 0

        db = fb_fs.client()
        count = 0
        for u in db.collection("users").stream():
            uid = u.id
            for c in u.reference.collection("castles").stream():
                c_data = c.to_dict() or {}
                cid = c.id
                email = str(c_data.get("email", "")).strip().lower()
                if not email:
                    continue

                bstatus = c_data.get("bot_status", {})
                res = c_data.get("resources", {})
                cinfo = c_data.get("castle_info", {})

                conn_state = bstatus.get("conn_state", bstatus.get("state", "idle"))
                msg = bstatus.get("conn_message", bstatus.get("last_run_message", ""))
                next_run = bstatus.get("next_run_time")

                upsert_castle_conn_state(
                    email=email,
                    conn_state=conn_state,
                    message=msg,
                    next_run_time=next_run,
                    user_id=uid,
                    castle_id=cid,
                    db_path=db_path
                )
                upsert_castle_resources(
                    email=email,
                    resources=res,
                    castle_info=cinfo,
                    user_id=uid,
                    castle_id=cid,
                    db_path=db_path
                )
                count += 1

        log.info(f"✅ تمت مزامنة {count} قلعة من Firebase إلى قاعدة البيانات المحلية بنجاح")
        return count
    except Exception as e:
        log.warning(f"⚠️ خطأ أثناء المزامنة من Firebase: {e}")
        return 0

