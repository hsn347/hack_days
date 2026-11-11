# -*- coding: utf-8 -*-
"""
tasks/exclude_manager.py — مدير استبعاد الأهداف المركزي الآمن (Centralized Exclude Manager)
════════════════════════════════════════════════════════════════════════════════════════════════

يحل محل الدوال المكررة (_get_exclude / _add_exclude) المنتشرة في:
  - gather.py, stronghold.py, monster.py, ruins.py

الميزات:
  1. Reserve → Confirm → Release pattern:
     - reserve()  : يضيف الهدف للذاكرة المؤقتة فقط (قبل إرسال المسيرة)
     - confirm()  : يثبته في قاعدة البيانات (بعد نجاح الإرسال فعلاً)
     - release()  : يزيل الاستبعاد المؤقت عند الفشل (لإعادة إتاحة الهدف)

  2. threading.Lock لمنع Race Condition بين الحسابات المتعددة والخيوط المختلفة بأمان تام.

  3. SQLite WAL (Write-Ahead Logging) لأمان تام ضد تلف البيانات وتضارب العمليات.

  4. طول مصفوفة ثابت بدون انتهاء صلاحية:
     - جدول excluded_targets بحد أقصى 300 هدف للمملكة مرتبة من الأقدم للأحدث.
     - لا يوجد حذف مبني على الوقت (لا TTL).

  5. سقف أمان صارم للحزمة (Packet Safety Ceiling):
     - حصر الأهداف المعادة في get_exclude_map بحد أقصى (20 هدفاً - الأحدث أولاً)
       وضمن مسافة <= 120 من القلعة.
     - يضمن عدم تجاوز حجم حزمة بروتوكول اللعبة سقف 65,535 بايت ('H' format unsigned short).

  6. تصنيف أنواع الأهداف (target_type):
     - يُستنتج تلقائياً من صيغة target_id (X-Y-mapType-subType-serial).
     - يمكن تمريره صراحةً لأنواع خاصة (elf, elite_rebel).
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import math
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_DIR   = os.path.join(_ROOT_DIR, "database")
_DB_PATH  = os.path.join(_DB_DIR, "exclude_history.db")

# مواقع ملف JSON القديم للترحيل (تُفحص مرة واحدة عند الإقلاع)
_LEGACY_JSON_PATHS = [
    os.path.join(_DB_DIR, "exclude_history.json"),
    os.path.join(_ROOT_DIR, "exclude_history.json"),
]

log = logging.getLogger("exclude_manager")


class ExcludeManager:
    """
    مدير استبعاد الأهداف المركزي الآمن.

    - Singleton-like: يُستخدم instance واحد مشترك عبر get_manager().
    - قاعدة البيانات: database/exclude_history.db (SQLite WAL).
    - بحد أقصى 300 هدف لكل مملكة مرتبة من الأقدم للأحدث (يُحذف الأقدم عند الامتلاء).
    - الحجوزات المؤقتة (reserved) تبقى في الذاكرة RAM فقط وتُمسح عند إعادة التشغيل.
    """

    MAX_PER_KINGDOM       = 300        # الطول الثابت لجدول الأهداف لكل مملكة
    MAX_RESERVED_PER_POOL = 30         # الحد الأقصى للأهداف المحجوزة بالذاكرة المؤقتة لكل pool
    MAX_QUERY_EXCLUDES    = 20         # الحد الأقصى للأهداف المعادة في get_exclude_map
    MAX_QUERY_DISTANCE    = 120.0      # أقصى مسافة دائرية مقبولة عن موقع القلعة (x, y)

    def __init__(self, db_path: str | None = None):
        self._lock = threading.Lock()
        # pool_key → {target_id_str: timestamp} — محجوزة في الذاكرة فقط
        self._reserved: Dict[str, Dict[str, float]] = {}
        # uid_str → kingdom_key ("251") — كاش جلسة بسيط
        self._uid_kingdom: Dict[str, str] = {}

        self._db_path = db_path or _DB_PATH
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    # ────────────────────────────────────────────────────────────────
    #  اتصال SQLite WAL
    # ────────────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """فتح اتصال WAL جديد مع إعدادات الأداء والأمان."""
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _db_session(self):
        """مدير سياق آمن يفتح الاتصال ويغلقه تلقائياً لمنع أي تسريب File Handles."""
        conn = self._get_conn()
        try:
            with conn: # يدير الـ transaction (commit/rollback)
                yield conn
        finally:
            conn.close() # يضمن إغلاق الاتصال في كل الأحوال

    def _init_db(self):
        """إنشاء الجداول والفهارس وترحيل بيانات JSON القديمة (مرة واحدة عند الإقلاع)."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS excluded_targets (
                    kingdom_id   INTEGER NOT NULL,
                    target_id    TEXT    NOT NULL,
                    target_type  TEXT    NOT NULL DEFAULT 'unknown',
                    x            INTEGER,
                    y            INTEGER,
                    ts           REAL    NOT NULL,
                    PRIMARY KEY (kingdom_id, target_id)
                );
                CREATE INDEX IF NOT EXISTS idx_excl_kingdom_ts
                    ON excluded_targets (kingdom_id, ts DESC);
                CREATE INDEX IF NOT EXISTS idx_excl_kingdom_type_ts
                    ON excluded_targets (kingdom_id, target_type, ts DESC);
                CREATE TABLE IF NOT EXISTS exclude_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
        self._migrate_legacy_json()

    # ────────────────────────────────────────────────────────────────
    #  تصنيف نوع الهدف من صيغة target_id
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _infer_target_type(target_id: str) -> str:
        """
        استنتاج نوع الهدف من صيغة target_id: "X-Y-mapType-subType-serial"

        الأنواع المدعومة:
          mapType=5  → مورد: gold(1) | food(2) | wood(3) | iron(4) | silver(5)
          mapType=6  → invader (غازي)
          mapType=7  → ruins (أطلال)
          mapType=26 → stronghold (معقل)
          mapType=35 → rebel (متمرد)
          أخرى      → unknown
        """
        parts = str(target_id).split("-")
        if len(parts) < 5:
            return "unknown"
        try:
            map_type = int(parts[2])
            sub_type = int(parts[3])
        except (ValueError, IndexError):
            return "unknown"

        if map_type == 5:
            return {1: "gold", 2: "food", 3: "wood", 4: "iron", 5: "silver"}.get(sub_type, "resource")
        return {6: "invader", 7: "ruins", 26: "stronghold", 35: "rebel"}.get(map_type, "unknown")

    @staticmethod
    def _parse_coords(target_id: str):
        """استخراج إحداثيات (x, y) من target_id مع تطبيق إزاحة -1."""
        parts = str(target_id).split("-")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]) - 1, int(parts[1]) - 1
        return None, None

    @staticmethod
    def _normalize_query_type(target_type: Any) -> str | None:
        """
        تطبيع نوع الهدف للبحث: يقبل رقماً (subType=1..5 للموارد)، أو نصاً إنجليزياً أو عربياً، أو None.
        """
        if target_type is None:
            return None
        raw = str(target_type).strip()
        if not raw:
            return None
        if raw.isdigit():
            sub_id = int(raw)
            return {1: "gold", 2: "food", 3: "wood", 4: "iron", 5: "silver"}.get(sub_id, raw.lower())
        tt = raw.lower()
        ar_map = {
            "قمح": "food", "طعام": "food",
            "خشب": "wood",
            "حديد": "iron",
            "فضة": "silver", "الماس": "silver", "ألماس": "silver", "كوارنز": "silver", "ميثريل": "silver",
            "ذهب": "gold",
            "غازي": "invader", "وحش": "invader",
            "أطلال": "ruins", "اطلال": "ruins",
            "معقل": "stronghold",
            "متمرد": "rebel", "متمردين": "rebel",
            "عفريت": "elf",
            "نخبة": "elite_rebel", "نخبة المتمردين": "elite_rebel",
        }
        return ar_map.get(tt, tt)

    # ────────────────────────────────────────────────────────────────
    #  ترحيل JSON القديم (مرة واحدة)
    # ────────────────────────────────────────────────────────────────

    def _migrate_legacy_json(self):
        """استيراد exclude_history.json القديم إلى SQLite — يُنفَّذ مرة واحدة فقط."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM exclude_meta WHERE key='json_migrated_v1'"
            ).fetchone()
            if row:
                return

        # البحث عن الملف القديم
        json_path = None
        for candidate in _LEGACY_JSON_PATHS:
            if os.path.exists(candidate):
                json_path = candidate
                break

        if not json_path:
            # لا يوجد ملف قديم — سجّل الترحيل فقط
            with self._get_conn() as conn:
                conn.execute("INSERT OR IGNORE INTO exclude_meta VALUES ('json_migrated_v1','1')")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            log.warning(f"[ExcludeManager] تعذرت قراءة ملف JSON القديم: {e}")
            return

        rows = []
        for k_key_raw, entries in raw.items():
            kk = str(k_key_raw).strip()
            if kk.startswith("k_"):
                kk = kk[2:].strip()
            if not (kk.isdigit() and int(kk) > 0):
                continue
            kingdom_id = int(kk)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                tid = str(entry.get("id", "")).strip()
                if not tid:
                    continue
                try:
                    ts = float(entry.get("ts", 0))
                except (TypeError, ValueError):
                    ts = 0.0
                ttype = ExcludeManager._infer_target_type(tid)
                x, y = ExcludeManager._parse_coords(tid)
                rows.append((kingdom_id, tid, ttype, x, y, ts))

        if rows:
            with self._get_conn() as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO excluded_targets "
                    "(kingdom_id, target_id, target_type, x, y, ts) VALUES (?,?,?,?,?,?)",
                    rows
                )
                # تطبيق حد MAX_PER_KINGDOM على كل مملكة بعد الاستيراد
                kingdoms = set(r[0] for r in rows)
                for kid in kingdoms:
                    conn.execute("""
                        DELETE FROM excluded_targets
                        WHERE kingdom_id = ?
                          AND target_id NOT IN (
                              SELECT target_id FROM excluded_targets
                              WHERE kingdom_id = ?
                              ORDER BY ts DESC LIMIT ?
                          )
                    """, (kid, kid, self.MAX_PER_KINGDOM))
                conn.execute("INSERT OR IGNORE INTO exclude_meta VALUES ('json_migrated_v1','1')")

        # إعادة تسمية الملف القديم احتياطاً
        try:
            os.rename(json_path, json_path + ".migrated.bak")
        except Exception:
            pass
        log.info("[ExcludeManager] ✅ تم ترحيل بيانات JSON القديمة إلى SQLite بنجاح")

    # ────────────────────────────────────────────────────────────────
    #  مساعدات داخلية (kingdom key / reserved keys)
    # ────────────────────────────────────────────────────────────────

    def _normalize_kingdom_key(self, uid: Any = None, kingdom_id: Any = None) -> str | None:
        """استخراج رقم المملكة الصافي كمفتاح مثل \"251\" دون إنشاء أي مفاتيح UID في الملف."""
        uid_str = str(uid).strip() if uid not in (None, "", 0, "0") else ""
        if kingdom_id is not None:
            raw = str(kingdom_id).strip()
            if raw.startswith("k_"):
                raw = raw[2:].strip()
            if raw.isdigit() and int(raw) > 0:
                k_key = str(int(raw))
                if uid_str:
                    self._uid_kingdom[uid_str] = k_key
                return k_key
        if uid_str and uid_str in self._uid_kingdom:
            return self._uid_kingdom[uid_str]
        return None

    def _get_reserved_keys(self, uid: Any = None, kingdom_id: Any = None) -> List[str]:
        """تحديد مفاتيح الذاكرة المؤقتة: مفتاح المملكة أولاً، أو مفتاح مؤقت عند غياب المملكة."""
        k_key = self._normalize_kingdom_key(uid, kingdom_id)
        if k_key:
            return [k_key]
        uid_str = str(uid).strip() if uid not in (None, "", 0, "0") else ""
        return [f"_tmp_{uid_str}"] if uid_str else []

    # ────────────────────────────────────────────────────────────────
    #  الواجهة العامة: reserve / confirm / release / get_exclude_map
    # ────────────────────────────────────────────────────────────────

    async def reserve(self, uid: Any, target_id: Any, kingdom_id: Any = None,
                      target_type: str | None = None):
        """
        حجز هدف مؤقتاً في الذاكرة المشتركة للمملكة قبل إرسال المسيرة
        لمنع أي حساب آخر من استهدافه تزامناً.
        (target_type اختياري: للأنواع الخاصة مثل 'elf', 'elite_rebel')
        """
        tid_str = str(target_id).strip() if target_id is not None else ""
        if not tid_str:
            return
        now_ts = time.time()
        with self._lock:
            for pkey in self._get_reserved_keys(uid, kingdom_id):
                pool = self._reserved.setdefault(pkey, {})
                pool[tid_str] = now_ts
                # ضبط سقف الأهداف المحجوزة في الذاكرة لمنع أي تسريب
                if len(pool) > self.MAX_RESERVED_PER_POOL:
                    oldest_tid = min(pool, key=pool.get)
                    del pool[oldest_tid]

    async def confirm(self, uid: Any, target_id: Any, kingdom_id: Any = None,
                      target_type: str | None = None):
        """
        تثبيت الهدف في قاعدة البيانات بعد نجاح الإرسال أو تأكد الانشغال.
        يحافظ على طول ثابت (MAX_PER_KINGDOM) مع حذف الأقدم تلقائياً.
        (target_type اختياري: للأنواع الخاصة مثل 'elf', 'elite_rebel')
        """
        tid_str = str(target_id).strip() if target_id is not None else ""
        if not tid_str:
            return

        with self._lock:
            k_key = self._normalize_kingdom_key(uid, kingdom_id)
            uid_str = str(uid).strip() if uid not in (None, "", 0, "0") else ""
            # إزالة من الحجوزات المؤقتة (RAM)
            for rkey in ([k_key] if k_key else []) + ([f"_tmp_{uid_str}"] if uid_str else []):
                if rkey in self._reserved:
                    self._reserved[rkey].pop(tid_str, None)

            if not k_key:
                return

            kingdom_id_int = int(k_key)

        ttype = self._normalize_query_type(target_type) or self._infer_target_type(tid_str)
        x, y  = self._parse_coords(tid_str)
        now_ts = time.time()

        with self._db_session() as conn:
            # تنفيذ ذري متسلسل داخل معاملة واحدة آمنة
            conn.execute(
                "INSERT OR REPLACE INTO excluded_targets "
                "(kingdom_id, target_id, target_type, x, y, ts) VALUES (?,?,?,?,?,?)",
                (kingdom_id_int, tid_str, ttype, x, y, now_ts)
            )
            conn.execute("""
                DELETE FROM excluded_targets
                WHERE kingdom_id = ?
                  AND target_id NOT IN (
                      SELECT target_id FROM excluded_targets
                      WHERE kingdom_id = ?
                      ORDER BY ts DESC LIMIT ?
                  )
            """, (kingdom_id_int, kingdom_id_int, self.MAX_PER_KINGDOM))

    async def release(self, uid: Any, target_id: Any, kingdom_id: Any = None):
        """
        إزالة الاستبعاد المؤقت عند فشل الإرسال من الذاكرة المؤقتة.
        (لا تمس قاعدة البيانات)
        """
        tid_str = str(target_id).strip() if target_id is not None else ""
        if not tid_str:
            return
        with self._lock:
            k_key = self._normalize_kingdom_key(uid, kingdom_id)
            uid_str = str(uid).strip() if uid not in (None, "", 0, "0") else ""
            for rkey in ([k_key] if k_key else []) + ([f"_tmp_{uid_str}"] if uid_str else []):
                if rkey in self._reserved:
                    self._reserved[rkey].pop(tid_str, None)

    async def get_exclude_map(
        self,
        uid: Any,
        kingdom_id: Any = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        max_distance: float = MAX_QUERY_DISTANCE,
        target_type: Optional[Any] = None,
    ) -> Dict[str, bool]:
        """
        جلب خريطة الاستبعاد لمملكة الحساب (ضمن مسافة max_distance وبحد أقصى MAX_QUERY_EXCLUDES).
        يدعم الفلترة بنوع الهدف target_type (مثل 'food', 'wood', 2, 'elf', 'invader').
        الأحدث يأتي في نهاية القائمة (للاستخدام مع [-MAX_QUERY_EXCLUDES:]).
        """
        norm_type = self._normalize_query_type(target_type)

        with self._lock:
            k_key = self._normalize_kingdom_key(uid, kingdom_id)
            rkey  = k_key or (f"_tmp_{str(uid).strip()}" if uid not in (None, "", 0, "0") else None)
            reserved_pool: Dict[str, float] = {}
            if rkey:
                reserved_pool = dict(self._reserved.get(rkey, {}))

        db_ids: List[str] = []
        if k_key:
            kingdom_id_int = int(k_key)
            where_clauses = ["kingdom_id = ?"]
            params: List[Any] = [kingdom_id_int]

            if norm_type:
                where_clauses.append("target_type = ?")
                params.append(norm_type)

            if x is not None and y is not None:
                dist_sq = max_distance * max_distance
                where_clauses.append("(x IS NULL OR y IS NULL OR ((x - ?) * (x - ?) + (y - ?) * (y - ?)) <= ?)")
                params.extend([x, x, y, y, dist_sq])

            query = f"""
                SELECT target_id FROM excluded_targets
                WHERE {' AND '.join(where_clauses)}
                ORDER BY ts ASC
            """

            conn = self._get_conn()
            try:
                rows = conn.execute(query, params).fetchall()
                db_ids = [r[0] for r in rows]
            finally:
                conn.close()

        # دمج المحجوزات (RAM) — مع مطابقة نوع الهدف إن حُدد
        if reserved_pool:
            filtered_reserved: Dict[str, float] = {}
            for tid, r_ts in reserved_pool.items():
                if norm_type and self._infer_target_type(tid) != norm_type:
                    continue
                filtered_reserved[tid] = r_ts

            if filtered_reserved:
                db_ids = [tid for tid in db_ids if tid not in filtered_reserved]
                db_ids.extend(sorted(filtered_reserved, key=filtered_reserved.get))

        # آخر MAX_QUERY_EXCLUDES عنصراً (الأحدث)
        return {tid: True for tid in db_ids[-self.MAX_QUERY_EXCLUDES:]}


# ════════════════════════════════════════════════════════════════════
#  Singleton instance — يُستخدم عبر get_manager() في كل الملفات
# ════════════════════════════════════════════════════════════════════

_manager_instance: ExcludeManager | None = None
_manager_lock = threading.Lock()


def get_manager() -> ExcludeManager:
    """جلب المدير المركزي الوحيد (Singleton) بأمان تام عبر الخيوط المتعددة."""
    global _manager_instance
    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = ExcludeManager()
    return _manager_instance
