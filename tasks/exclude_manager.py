# -*- coding: utf-8 -*-
"""
tasks/exclude_manager.py — مدير استبعاد الأهداف المركزي الآمن (Centralized Exclude Manager)
════════════════════════════════════════════════════════════════════════════════════════════════

يحل محل الدوال المكررة (_get_exclude / _add_exclude) المنتشرة في:
  - gather.py, stronghold.py, monster.py, ruins.py

الميزات:
  1. Reserve → Confirm → Release pattern:
     - reserve()  : يضيف الهدف للذاكرة المؤقتة فقط (قبل إرسال المسيرة)
     - confirm()  : يثبته في الملف (بعد نجاح الإرسال فعلاً)
     - release()  : يزيل الاستبعاد المؤقت عند الفشل (لإعادة إتاحة الهدف)

  2. threading.Lock لمنع Race Condition بين الحسابات المتعددة والخيوط المختلفة بأمان تام.

  3. كتابة ذرية (Atomic Write) عبر ملف مؤقت + rename لمنع تلف البيانات.

  4. TTL (مدة انتهاء صلاحية):
     - الأهداف المستبعدة في الملف تنتهي صلاحيتها تلقائياً بعد 4 ساعات.
     - الأهداف المحجوزة في الذاكرة (reserved) تنتهي تلقائياً بعد 5 دقائق لمنع التسريب.

  5. سقف أمان صارم للحزمة (Packet Safety Ceiling):
     - حصر الأهداف المعادة في get_exclude_map بحد أقصى (120 هدفاً كحد أقصى - الأحدث أولاً).
     - يضمن عدم تجاوز حجم حزمة بروتوكول اللعبة سقف 65,535 بايت ('H' format unsigned short).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import threading
import time
from typing import Any, Dict, List, Set

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DB_DIR = os.path.join(_ROOT_DIR, "database")
HISTORY_FILE = os.path.join(_DB_DIR, "exclude_history.json")
_LEGACY_HISTORY_FILE = os.path.join(_ROOT_DIR, "exclude_history.json")

log = logging.getLogger("exclude_manager")


class ExcludeManager:
    """
    مدير استبعاد الأهداف المركزي الآمن.

    - Singleton-like: يُستخدم instance واحد مشترك عبر get_manager().
    - كل UID يملك قائمة أهداف مستبعدة في الملف + ذاكرة مؤقتة (reserved).
    - الأهداف المثبتة (confirmed) تُحفظ في الملف مع timestamp.
    - الأهداف المحجوزة (reserved) تبقى في الذاكرة فقط مع timestamp وتنتهي صلاحيتها خلال 5 دقائق.
    - get_exclude_map يُرجع دائماً الأحدث ضمن سقف أمان يمنع أي تجاوز لحجم حزم الشبكة.
    """

    MAX_PER_UID           = 20          # الحد الأقصى للأهداف المحفوظة لكل حساب منفرد في الملف (يكفي أضعاف طوابير القلعة)
    MAX_PER_KINGDOM       = 60          # الحد الأقصى للأهداف المشتركة على مستوى المملكة في الملف
    TTL_SECONDS           = 4 * 3600    # 4 ساعات — مدة صلاحية الاستبعاد في الملف لتغطية مسيرات المناجم البعيدة
    RESERVED_TTL_SECONDS  = 180         # 3 دقائق — مدة صلاحية الحجز المؤقت في الذاكرة (كافية جداً لإطلاق المسيرة)
    MAX_RESERVED_PER_POOL = 30          # الحد الأقصى للأهداف المحجوزة بالذاكرة المؤقتة لكل حوض
    MAX_QUERY_EXCLUDES    = 40          # السقف الأمني الصارم للحزمة الواحدة (حجم الطلب لا يتجاوز 1 كيلوبايت)

    def __init__(self):
        self._lock = threading.Lock()
        # pool_key → dict of {target_id_str: timestamp} (محجوزة في الذاكرة فقط مع توقيت)
        self._reserved: Dict[str, Dict[str, float]] = {}
        # uid_str → kingdom_key ("k_170")
        self._uid_kingdom: Dict[str, str] = {}
        # كاش في الذاكرة لتفادي قراءة الملف المتكررة من القرص وتخفيف الحمل تماماً عن السيرفر
        self._cached_data: dict | None = None

    # ────────────────────────────────────────────────────────────────
    #  قراءة / كتابة الملف (Thread-safe via threading.Lock)
    # ────────────────────────────────────────────────────────────────

    def _read_file(self) -> dict:
        """قراءة سريعة من الكاش بالذاكرة، أو من الملف عند الإقلاع فقط بأمان."""
        if self._cached_data is not None:
            return self._cached_data
        if not os.path.exists(HISTORY_FILE) and os.path.exists(_LEGACY_HISTORY_FILE):
            try:
                os.makedirs(_DB_DIR, exist_ok=True)
                import shutil
                shutil.move(_LEGACY_HISTORY_FILE, HISTORY_FILE)
            except Exception:
                pass
        if not os.path.exists(HISTORY_FILE):
            self._cached_data = {}
            return self._cached_data
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._cached_data = data
                return self._cached_data
        except Exception as e:
            log.debug(f"تعذر قراءة {HISTORY_FILE}: {e}")
        self._cached_data = {}
        return self._cached_data

    def _write_file(self, data: dict):
        """كتابة ذرية: تحديث الكاش بالذاكرة أولاً ثم الحفظ في الملف."""
        self._cached_data = data
        try:
            dir_name = os.path.dirname(HISTORY_FILE)
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp", prefix="exclude_", dir=dir_name
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                os.close(fd)
                raise

            # على Windows، يجب حذف الملف الأصلي أولاً قبل rename
            if os.path.exists(HISTORY_FILE):
                try:
                    os.replace(tmp_path, HISTORY_FILE)
                except Exception:
                    # fallback: حذف ثم إعادة تسمية
                    try:
                        os.remove(HISTORY_FILE)
                    except Exception:
                        pass
                    os.rename(tmp_path, HISTORY_FILE)
            else:
                os.rename(tmp_path, HISTORY_FILE)

        except Exception as e:
            log.warning(f"تعذرت الكتابة الذرية لـ {HISTORY_FILE}: {e}")
            # خطة بديلة: كتابة مباشرة
            try:
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e2:
                log.error(f"فشلت الكتابة المباشرة أيضاً: {e2}")

    # ────────────────────────────────────────────────────────────────
    #  تنظيف الأهداف المنتهية الصلاحية (TTL Cleanup)
    # ────────────────────────────────────────────────────────────────

    def _cleanup_expired(self, uid_entries: list) -> list:
        """
        تنظيف الأهداف المنتهية الصلاحية من قائمة UID واحد في الملف.
        الصيغة الجديدة: {"id": "target_id", "ts": timestamp}
        التوافق مع الصيغة القديمة: "target_id" (string عادي بدون timestamp)
        """
        now = time.time()
        cleaned = []
        for entry in uid_entries:
            if isinstance(entry, dict):
                # الصيغة الجديدة مع timestamp
                ts = entry.get("ts", 0)
                if (now - ts) < self.TTL_SECONDS:
                    cleaned.append(entry)
                # else: منتهي الصلاحية → يُحذف
            elif isinstance(entry, str):
                # الصيغة القديمة (بدون timestamp) — نعتبرها منتهية ونحذفها
                pass
        return cleaned

    def _cleanup_reserved(self, pkey: str, now: float) -> None:
        """
        تنظيف الأهداف المحجوزة المنتهية الصلاحية في الذاكرة المؤقتة (مرور أكثر من 5 دقائق).
        يمنع تراكم الأهداف في الرام للأبد عند حدوث أخطاء أو انقطاع في المسيرة.
        """
        pool = self._reserved.get(pkey)
        if not pool:
            return
        expired = [tid for tid, ts in pool.items() if (now - ts) >= self.RESERVED_TTL_SECONDS]
        for tid in expired:
            del pool[tid]

    def _get_target_id_from_entry(self, entry) -> str:
        """استخراج target_id من الإدخال سواء كان قاموس أو نص."""
        if isinstance(entry, dict):
            return str(entry.get("id", ""))
        return str(entry)

    def _get_pool_keys(self, uid: Any, kingdom_id: Any = None) -> List[str]:
        """تحديد المفاتيح المعنية (على مستوى المملكة وعلى مستوى UID لضمان التوافق التام)."""
        uid_str = str(uid)
        keys = [uid_str]
        k_key = None
        if kingdom_id is not None and str(kingdom_id).isdigit() and int(kingdom_id) > 0:
            k_key = f"k_{int(kingdom_id)}"
            self._uid_kingdom[uid_str] = k_key
        elif uid_str in self._uid_kingdom:
            k_key = self._uid_kingdom[uid_str]

        if k_key and k_key not in keys:
            keys.append(k_key)
        return keys

    # ────────────────────────────────────────────────────────────────
    #  الواجهة العامة: reserve / confirm / release / get_exclude_map
    # ────────────────────────────────────────────────────────────────

    async def reserve(self, uid: Any, target_id: Any, kingdom_id: Any = None):
        """
        حجز هدف مؤقتاً في الذاكرة المشتركة (لكل حسابات المملكة والـ UID) مع توقيت صلاحية.
        يُستخدم فور العثور على الهدف وقبل إرسال المسيرة لمنع أي حساب آخر من استهدافه تزامناً.
        """
        tid_str = str(target_id).strip()
        if not tid_str:
            return
        now_ts = time.time()
        with self._lock:
            for pkey in self._get_pool_keys(uid, kingdom_id):
                if pkey not in self._reserved:
                    self._reserved[pkey] = {}
                self._cleanup_reserved(pkey, now_ts)
                pool = self._reserved[pkey]
                pool[tid_str] = now_ts
                # ضبط سقف الأهداف المحجوزة في الذاكرة لمنع أي تسريب
                if len(pool) > self.MAX_RESERVED_PER_POOL:
                    oldest_tid = min(pool, key=pool.get)
                    del pool[oldest_tid]

    async def confirm(self, uid: Any, target_id: Any, kingdom_id: Any = None):
        """
        تثبيت الهدف في الملف المشترك بعد نجاح الإرسال فعلاً.
        يُزال من الذاكرة المؤقتة ويُكتب في الملف مع timestamp في حوض المملكة وحوض UID.
        """
        tid_str = str(target_id).strip()
        if not tid_str:
            return
        now_ts = time.time()
        with self._lock:
            pool_keys = self._get_pool_keys(uid, kingdom_id)
            # إزالة من الذاكرة المؤقتة
            for pkey in pool_keys:
                if pkey in self._reserved:
                    self._reserved[pkey].pop(tid_str, None)

            data = self._read_file()
            for pkey in pool_keys:
                arr = data.get(pkey, [])
                arr = self._cleanup_expired(arr)
                existing_ids = {self._get_target_id_from_entry(e) for e in arr}
                if tid_str not in existing_ids:
                    arr.append({"id": tid_str, "ts": now_ts})
                max_cap = self.MAX_PER_KINGDOM if pkey.startswith("k_") else self.MAX_PER_UID
                while len(arr) > max_cap:
                    arr.pop(0)
                if arr:
                    data[pkey] = arr
                else:
                    data.pop(pkey, None)

            self._write_file(data)

    async def release(self, uid: Any, target_id: Any, kingdom_id: Any = None):
        """
        إزالة الاستبعاد المؤقت عند فشل الإرسال من كافة الأحواض.
        """
        tid_str = str(target_id).strip()
        if not tid_str:
            return
        with self._lock:
            for pkey in self._get_pool_keys(uid, kingdom_id):
                if pkey in self._reserved:
                    self._reserved[pkey].pop(tid_str, None)

    async def get_exclude_map(self, uid: Any, kingdom_id: Any = None) -> Dict[str, bool]:
        """
        جلب خريطة الاستبعاد الموحدة (ذاكرة مؤقتة) مدموجة لكل حسابات المملكة.
        يمنع أي حساب في نفس المملكة من استهداف هدف محجوز أو مستهدف مسبقاً.
        
        🛡️ حماية وسرعة فائقة:
        - قراءة فورية من الذاكرة (Memory Cache) بدون أي كتابة على القرص لتخفيف العبء عن السيرفر.
        - الأهداف تُرتب تنازلياً حسب توقيتها (الأحدث أولاً).
        - سقف أمان صارم (MAX_QUERY_EXCLUDES = 40) لمنع تجاوز حجم حزمة بروتوكول اللعبة.
        """
        with self._lock:
            now_ts = time.time()
            pool_keys = self._get_pool_keys(uid, kingdom_id)
            data = self._read_file()
            combined_targets: Dict[str, float] = {}

            for pkey in pool_keys:
                arr = data.get(pkey, [])
                cleaned = self._cleanup_expired(arr)

                for entry in cleaned:
                    tid = self._get_target_id_from_entry(entry)
                    if tid:
                        ts = entry.get("ts", 0) if isinstance(entry, dict) else now_ts
                        combined_targets[tid] = max(combined_targets.get(tid, 0), ts)

                # تنظيف وحقن المحجوز من الذاكرة
                self._cleanup_reserved(pkey, now_ts)
                for tid, ts in self._reserved.get(pkey, {}).items():
                    if tid:
                        combined_targets[tid] = max(combined_targets.get(tid, 0), ts)

            # 🛡️ السقف الأمني الصارم: ترتيب الأحدث واقتصار النتيجة على أحدث MAX_QUERY_EXCLUDES هدف
            sorted_tids = sorted(combined_targets.keys(), key=lambda k: combined_targets[k], reverse=True)
            safe_tids = sorted_tids[:self.MAX_QUERY_EXCLUDES]

            return {tid: True for tid in safe_tids}


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
