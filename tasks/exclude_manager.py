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

  4. TTL (مدة انتهاء صلاحية): الأهداف المستبعدة تنتهي صلاحيتها تلقائياً بعد 4 ساعات.

  5. سعة 80 هدف لكل UID بدلاً من 20 لمنع الحذف المبكر.

  6. get_exclude_map() يدمج الملف + الذاكرة المؤقتة ويحذف المنتهية.
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

HISTORY_FILE = os.path.join(_ROOT_DIR, "exclude_history.json")

log = logging.getLogger("exclude_manager")


class ExcludeManager:
    """
    مدير استبعاد الأهداف المركزي الآمن.

    - Singleton-like: يُستخدم instance واحد مشترك عبر get_manager().
    - كل UID يملك قائمة أهداف مستبعدة في الملف + ذاكرة مؤقتة (reserved).
    - الأهداف المثبتة (confirmed) تُحفظ في الملف مع timestamp.
    - الأهداف المحجوزة (reserved) تبقى في الذاكرة فقط حتى confirm أو release.
    """

    MAX_PER_UID      = 80          # الحد الأقصى للأهداف المحفوظة لكل حساب منفرد
    MAX_PER_KINGDOM  = 500         # الحد الأقصى للأهداف المشتركة على مستوى المملكة (Kingdom-wide)
    TTL_SECONDS      = 4 * 3600    # 4 ساعات — مدة صلاحية الاستبعاد

    def __init__(self):
        self._lock = threading.Lock()
        # pool_key → set of target_id_str (محجوزة في الذاكرة فقط)
        self._reserved: Dict[str, Set[str]] = {}
        # uid_str → kingdom_key ("k_170")
        self._uid_kingdom: Dict[str, str] = {}

    # ────────────────────────────────────────────────────────────────
    #  قراءة / كتابة الملف (Thread-safe via threading.Lock)
    # ────────────────────────────────────────────────────────────────

    def _read_file(self) -> dict:
        """قراءة ملف exclude_history.json بأمان."""
        if not os.path.exists(HISTORY_FILE):
            return {}
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            log.debug(f"تعذر قراءة {HISTORY_FILE}: {e}")
        return {}

    def _write_file(self, data: dict):
        """كتابة ذرية: ملف مؤقت → rename لمنع التلف."""
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
        تنظيف الأهداف المنتهية الصلاحية من قائمة UID واحد.
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
                # هذا يضمن تنظيف البيانات القديمة تدريجياً
                pass
        return cleaned

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
        حجز هدف مؤقتاً في الذاكرة المشتركة (لكل حسابات المملكة والـ UID).
        يُستخدم فور العثور على الهدف وقبل إرسال المسيرة لمنع أي حساب آخر من استهدافه تزامناً.
        """
        tid_str = str(target_id)
        with self._lock:
            for pkey in self._get_pool_keys(uid, kingdom_id):
                if pkey not in self._reserved:
                    self._reserved[pkey] = set()
                self._reserved[pkey].add(tid_str)

    async def confirm(self, uid: Any, target_id: Any, kingdom_id: Any = None):
        """
        تثبيت الهدف في الملف المشترك بعد نجاح الإرسال فعلاً.
        يُزال من الذاكرة المؤقتة ويُكتب في الملف مع timestamp في حوض المملكة وحوض UID.
        """
        tid_str = str(target_id)
        now_ts = time.time()
        with self._lock:
            pool_keys = self._get_pool_keys(uid, kingdom_id)
            # إزالة من الذاكرة المؤقتة
            for pkey in pool_keys:
                if pkey in self._reserved:
                    self._reserved[pkey].discard(tid_str)

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
                data[pkey] = arr

            self._write_file(data)

    async def release(self, uid: Any, target_id: Any, kingdom_id: Any = None):
        """
        إزالة الاستبعاد المؤقت عند فشل الإرسال من كافة الأحواض.
        """
        tid_str = str(target_id)
        with self._lock:
            for pkey in self._get_pool_keys(uid, kingdom_id):
                if pkey in self._reserved:
                    self._reserved[pkey].discard(tid_str)

    async def get_exclude_map(self, uid: Any, kingdom_id: Any = None) -> Dict[str, bool]:
        """
        جلب خريطة الاستبعاد الموحدة (ملف + ذاكرة مؤقتة) مدموجة لكل حسابات المملكة.
        يمنع أي حساب في نفس المملكة من مهاجمة هدف محجوز أو مستهدف مسبقاً من أي حساب آخر على السيرفر.
        """
        with self._lock:
            pool_keys = self._get_pool_keys(uid, kingdom_id)
            data = self._read_file()
            exclude_map: Dict[str, bool] = {}
            file_changed = False

            for pkey in pool_keys:
                arr = data.get(pkey, [])
                cleaned = self._cleanup_expired(arr)
                if len(cleaned) != len(arr):
                    data[pkey] = cleaned
                    file_changed = True

                for entry in cleaned:
                    tid = self._get_target_id_from_entry(entry)
                    if tid:
                        exclude_map[tid] = True

                for tid in self._reserved.get(pkey, set()):
                    if tid:
                        exclude_map[tid] = True

            if file_changed:
                self._write_file(data)

            return exclude_map


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
