# -*- coding: utf-8 -*-
"""
tasks/march_manager.py — منسق الفيالق والمسيرات الخارجي الموحد (March Orchestrator)
════════════════════════════════════════════════════════════════════════════════════════════
يدير مسيرات خريطة المملكة وفق تسلسل أولويات دقيق مع تطبيق نظام الحالات الخمس الصارم:

  1. الحالة 1 (نفاذ الفيالق المتاحة):
     البقاء في نفس الأولوية والانتظار دقيقة كاملة (60 ثانية) ثم إعادة الفحص،
     في ضوء وقت المهمة الكامل (20 دقيقة).
  2. الحالة 2 (نقص جنود التشكيلة المحددة):
     الهجوم بأي جنود متوفرين بالقلعة بحيث يعادل أو يقارب مجموعهم القوة القتالية للتشكيلة.
  3. الحالة 3 (انعدام القوات بالقلعة كلياً):
     في حال عدم توفر قوات كافية حتى خارج التشكيلة، يخرج البوت من المهمة ككل فوراً.
  4. الحالة 4 (خطأ غير متوقع / فشل الهجوم):
     يحاول 3 مرات في الأولوية الحالية؛ وإذا استمر الخطأ 3 مرات ينتقل للأولوية التالية.
  5. الحالة 5 (اكتمال الأولويات):
     عند انتهاء الأولويات المفعلة يخرج البوت من المهمة بنجاح.

الأولويات المدعومة حالياً:
  [1] غزاة الهيبة (Prestige Invaders - CMD 4112004)
  [2] معقل الهيبة (Prestige Stronghold - CMD 4112030)
"""

from __future__ import annotations

import sys
import os
import asyncio
import copy
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# ── معرفات مهام الهيبة من السيرفر (meritoriousTaskCtrl) ───────────────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "invaders": 4112004,    # الهجوم على الغزاة في الخريطة (5 هجمات)
    "stronghold": 4112030,  # احتلال المعقل / الملجأ (مرتان)
}

# ── خريطة قوة الرتب التقديرية للجنود (Tier Combat Power) ──────────────
TIER_POWER_MAP: Dict[int, float] = {
    1: 1.0,
    2: 1.5,
    3: 2.1,
    4: 2.8,
    5: 3.6,
    6: 4.6,
    7: 5.7,
    8: 7.0,
    9: 8.5,
    10: 10.2,
    11: 12.2,
    12: 14.5,
}

# أدنى حد للجنود بالقلعة لإطلاق مسيرة (إذا كان المجموع أقل منه نعتبر القلعة خالية)
MIN_ATTACK_ARMY_COUNT = 300


def get_soldier_tier(soldier_id: int) -> int:
    """استخراج مستوى الرتبة للوحدة (Tier 1..12)."""
    return soldier_id % 100


def get_soldier_power(soldier_id: int) -> float:
    """إرجاع القوة القتالية التقديرية للجندي الواحد."""
    tier = get_soldier_tier(soldier_id)
    return TIER_POWER_MAP.get(tier, 3.0)


# ════════════════════════════════════════════════════════════════════
#  كلاس منسق الفيالق والمسيرات (MarchManagerTask)
# ════════════════════════════════════════════════════════════════════

class MarchManagerTask(BaseTask):
    """
    منسق الفيالق الموحد الجديد كلياً.
    """
    name = "march_manager"

    DEFAULT_PRIORITY_ORDER = [
        "prestige_invaders",
        "prestige_stronghold",
    ]

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config or {})
        self.max_queues = int(self.config.get("max_queues", 6))
        self.duration_minutes = float(self.config.get("duration_minutes", 20.0))
        self.priority_order = self.config.get("priority_order") or self.DEFAULT_PRIORITY_ORDER

        self.start_time: float = 0.0
        self.max_duration_seconds: float = self.duration_minutes * 60.0

        self._busy_heroes: Set[int] = set()
        self._used_army: Dict[int, int] = {}
        self._used_pets: Set[int] = set()
        self._excluded_targets: Set[str] = set()
        self._heroes: List[Dict[str, Any]] = []

    # ────────────────────────────────────────────────────────────────
    #  إدارة الوقت والمهلة الزمنية (20 دقيقة)
    # ────────────────────────────────────────────────────────────────

    def is_time_expired(self) -> bool:
        """فحص هل انتهت مدة الـ 20 دقيقة المخصصة للمهمة."""
        if self.start_time <= 0:
            return False
        return (time.time() - self.start_time) >= self.max_duration_seconds

    def time_remaining_seconds(self) -> float:
        """الوقت المتبقي من مدة المهمة بالثواني."""
        if self.start_time <= 0:
            return self.max_duration_seconds
        return max(0.0, self.max_duration_seconds - (time.time() - self.start_time))

    # ────────────────────────────────────────────────────────────────
    #  استعلامات الهيبة والمهام من الذاكرة (meritoriousTaskCtrl)
    # ────────────────────────────────────────────────────────────────

    async def _refresh_merit_data(self) -> bool:
        """تحديث بيانات الهيبة والمجد من السيرفر مباشرة."""
        try:
            r = await self.conn.query("1013", "1", {}, timeout=5)
            if r and isinstance(r, dict) and "data" in r:
                merit_data = r["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    return True
        except Exception:
            pass
        return False

    def get_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]:
        """
        فحص دقيق لحالة مهمة الهيبة من السيرفر (taskData / tasks).
        """
        qid = PRESTIGE_QUEST_IDS.get(str(quest_key_or_id), quest_key_or_id if isinstance(quest_key_or_id, int) else 0)
        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if not isinstance(merit, dict):
            return {"found": False, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

        # 1. القاموس الرئيسي taskData
        task_data = merit.get("taskData", {})
        if isinstance(task_data, dict) and str(qid) in task_data:
            t_obj = task_data[str(qid)]
            if isinstance(t_obj, dict):
                c_num = int(t_obj.get("cNum", t_obj.get("c_num", 0)))
                l_num = int(t_obj.get("lNum", t_obj.get("l_num", 0)))
                status = int(t_obj.get("status", 0))
                is_done = (status == 4) or (l_num > 0 and c_num >= l_num)
                remaining = max(0, l_num - c_num) if l_num > 0 else 0
                return {
                    "found": True,
                    "task_id": qid,
                    "c_num": c_num,
                    "l_num": l_num,
                    "is_done": is_done,
                    "remaining": remaining,
                }

        # 2. القائمة البديلة tasks
        tasks = merit.get("tasks", [])
        if isinstance(tasks, dict):
            tasks = list(tasks.values())
        if isinstance(tasks, list):
            for t in tasks:
                if not isinstance(t, dict):
                    continue
                t_id = t.get("taskId") or t.get("id")
                if t_id and int(t_id) == qid:
                    c_num = int(t.get("c_num", t.get("cNum", 0)))
                    l_num = int(t.get("l_num", t.get("lNum", 0)))
                    is_finish = int(t.get("is_finish", t.get("isFinish", 0)))
                    is_done = (is_finish == 1) or (l_num > 0 and c_num >= l_num)
                    remaining = max(0, l_num - c_num) if l_num > 0 else 0
                    return {
                        "found": True,
                        "task_id": qid,
                        "c_num": c_num,
                        "l_num": l_num,
                        "is_done": is_done,
                        "remaining": remaining,
                    }

        return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

    # ────────────────────────────────────────────────────────────────
    #  استعلام وإدارة الفيالق والمسيرات (Queue Engine)
    # ────────────────────────────────────────────────────────────────

    def get_active_marches_count(self) -> int:
        """حساب عدد الفيالق النشطة في الوقت الحالي خارج القلعة."""
        active = 0
        all_queues = []

        # 1. local_queues
        lq = getattr(self.conn, "local_queues", None)
        if isinstance(lq, list):
            all_queues.extend(lq)

        # 2. حزم التزامن NOTIFY_LOCAL_QUEUE_SYNC
        for p in self.conn.cached_packets.values():
            if isinstance(p, dict):
                d = p.get("data", {})
                if isinstance(d, dict) and d.get("notifyID") == "NOTIFY_LOCAL_QUEUE_SYNC":
                    nd = d.get("notifyData", [])
                    if isinstance(nd, list):
                        all_queues.extend(nd)

        for item in all_queues:
            q_list = item.get("data", []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
            for q in q_list:
                if isinstance(q, dict) and q.get("status") in (1, 2, 3, 4, 7):
                    active += 1
                    # استخراج الأبطال المشغولين
                    heros = q.get("heros") or q.get("data", {}).get("heros") or []
                    if isinstance(heros, list):
                        for h in heros:
                            hid = h if isinstance(h, int) else (h.get("id") if isinstance(h, dict) else None)
                            if hid and str(hid).isdigit():
                                self._busy_heroes.add(int(hid))

        return active

    def get_free_queues_count(self) -> int:
        """عدد الفيالق الشاغرة المتاحة للإرسال الآن."""
        active = self.get_active_marches_count()
        return max(0, self.max_queues - active)

    async def sync_queues(self):
        """تحديث بيانات الفيالق من السيرفر مباشرة."""
        try:
            await self.conn.query("1001", "1", {}, timeout=5)
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────
    #  الأبطال والمرافقون
    # ────────────────────────────────────────────────────────────────

    async def _load_heroes(self):
        """تحميل قائمة الأبطال المتاحين بالقلعة."""
        self._heroes = []
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        try:
            r = await self.conn.query("3080", "2", {"isSelf": True, "uids": [uid_int]}, timeout=4)
            if r and "data" in r:
                pages = r["data"].get("list", {}).get(str(uid_int), {}).get("pages", {})
                if isinstance(pages, dict):
                    for page in pages.values():
                        if isinstance(page, dict):
                            for h in page.get("heros", []):
                                hid = h.get("id") if isinstance(h, dict) else h
                                if hid:
                                    self._heroes.append({"id": int(hid)})
        except Exception as e:
            self.log.debug(f"خطأ غير حرج أثناء استعلام الأبطال: {e}")

        # تدعيم من heroCtrl إن لم تتوفر
        if not self._heroes:
            hctrl = self.conn.init_data.get("heroCtrl", {})
            hlist = hctrl.get("heroList", hctrl) if isinstance(hctrl, dict) else (hctrl if isinstance(hctrl, list) else [])
            if isinstance(hlist, dict):
                hlist = list(hlist.values())
            for h in hlist:
                hid = h.get("id") if isinstance(h, dict) else h
                if hid and str(hid).isdigit():
                    self._heroes.append({"id": int(hid)})

    def pick_heroes_for_attack(self, form_heroes: List[int]) -> List[int]:
        """اختيار الأبطال للهجوم (أبطال التشكيلة أولاً، ثم أي بطل حرب متاح)."""
        chosen = []
        # تجربة أبطال التشكيلة
        for h in form_heroes:
            if h and int(h) not in self._busy_heroes:
                chosen.append(int(h))
                if len(chosen) >= 2:
                    break

        # إذا نقص بطل: إكمال بأبطال قتال متاحين
        if len(chosen) < 2:
            for h in self._heroes:
                hid = h.get("id") if isinstance(h, dict) else h
                if hid and int(hid) not in self._busy_heroes and int(hid) not in chosen:
                    if str(hid).startswith("5501") or len(chosen) == 0:
                        chosen.append(int(hid))
                        if len(chosen) >= 2:
                            break

        return chosen

    def pick_pet_for_attack(self, form_pets: List[int]) -> List[int]:
        """اختيار المرافق المتاح للهجوم."""
        for p in form_pets:
            if p and int(p) not in self._used_pets:
                self._used_pets.add(int(p))
                return [int(p)]

        pets_data = self.conn.init_data.get("petCtrl", {}).get("pets", {})
        if isinstance(pets_data, dict):
            for pid in pets_data.keys():
                if str(pid).isdigit():
                    pid_int = int(pid)
                    if pid_int not in self._used_pets:
                        self._used_pets.add(pid_int)
                        return [pid_int]
        return []

    # ────────────────────────────────────────────────────────────────
    #  محرك الجيش والتشكيلة (معالجة الحالة 2 والحالة 3)
    # ────────────────────────────────────────────────────────────────

    async def get_available_castle_army(self) -> Dict[int, int]:
        """استخراج رصيد الجيش المتاح داخل القلعة حالياً بعد خصم المستهلك في الجولة."""
        available: Dict[int, int] = {}
        r_army = await self.conn.query("1005", "1", {}, timeout=5)
        if r_army and "data" in r_army:
            total_army = r_army["data"].get("totalArmy", {})
            if isinstance(total_army, dict):
                for k, v in total_army.items():
                    if str(k).isdigit() and str(v).isdigit():
                        available[int(k)] = int(v)

        # خصم القوات التي أُرسلت في هذه الجولة
        for tid, used in self._used_army.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used)

        return available

    async def _resolve_attack_army(self, formation_id: int) -> Tuple[Optional[List[Dict[str, int]]], Dict[str, Any]]:
        """
        حل وتشكيل جيش المسيرة وفق منطق الحالتين:
          - الحالة 2: إذا نقص جنود التشكيلة، يتم الهجوم بأي جنود لتعويض النقص بقوة قتالية مقاربة.
          - الحالة 3: إذا كانت القوات بالقلعة ككل غير كافية (< MIN_ATTACK_ARMY_COUNT)، يُرجع None للخروج من المهمة.
        """
        available = await self.get_available_castle_army()
        total_avail_count = sum(available.values())

        # ── الحالة 3: عدم توفر قوات كافية حتى خارج التشكيلة ─────────
        if total_avail_count < MIN_ATTACK_ARMY_COUNT:
            self.log.warning(
                f"🛑 [الحالة 3: انعدام القوات] إجمالي القوات المتاحة بالقلعة ({total_avail_count:,}) "
                f"أقل من الحد الأدنى للهجوم ({MIN_ATTACK_ARMY_COUNT:,}) — لا تتوفر قوات حتى خارج التشكيلة!"
            )
            return None, {"reason": "no_army_critical", "total_troops": total_avail_count}

        # جلب بيانات التشكيلة المحفوظة (1005/7)
        form_heroes: List[int] = []
        form_pets: List[int] = []
        form_rune_pages: List[int] = [1]
        form_army: Dict[int, int] = {}

        if formation_id > 0:
            r_form = await self.conn.query("1005", "7", {"compiletype": formation_id}, timeout=4)
            if r_form and "data" in r_form:
                d = r_form["data"]
                raw_heros = d.get("compileHeros", [])
                if isinstance(raw_heros, list):
                    form_heroes = [int(h) for h in raw_heros if str(h).isdigit()]
                raw_pets = d.get("compilePets", [])
                if isinstance(raw_pets, list):
                    form_pets = [int(p) for p in raw_pets if str(p).isdigit()]
                form_rune_pages = d.get("compileRunePages", [1])
                raw_army = d.get("compileArmy", {})
                if isinstance(raw_army, dict):
                    for k, v in raw_army.items():
                        if str(k).isdigit() and str(v).isdigit():
                            form_army[int(k)] = int(v)

        # احتساب القوة القتالية المستهدفة للتشكيلة
        target_form_power = 0.0
        target_form_count = 0
        for tid, cnt in form_army.items():
            target_form_count += cnt
            target_form_power += cnt * get_soldier_power(tid)

        # إذا كانت التشكيلة فارغة في اللعبة: وضع هدف افتراضي (30,000 جندي بقوة متوسطة)
        if target_form_power <= 0:
            target_form_count = 30000
            target_form_power = 30000 * 3.5

        # ── تشكيل الجيش مع فحص التشكيلة والتعويض البديل ──────────────
        final_army_dict: Dict[int, int] = {}
        accumulated_power = 0.0
        accumulated_count = 0
        troops_substituted = False

        # 1. أخذ المتوفر من جنود التشكيلة أولاً
        for tid, req_cnt in form_army.items():
            avail_cnt = available.get(tid, 0)
            take = min(avail_cnt, req_cnt)
            if take > 0:
                final_army_dict[tid] = take
                accumulated_count += take
                accumulated_power += take * get_soldier_power(tid)
                available[tid] -= take
            if take < req_cnt:
                troops_substituted = True

        # 2. الحالة 2: تعويض النقص بجنود بديلين بقوة قتالية مقاربة
        missing_power = max(0.0, target_form_power - accumulated_power)

        if missing_power > 0 or not final_army_dict:
            # ترتيب القوات البديلة المتبقية بالقلعة من الأعلى رتبة إلى الأدنى
            sorted_avail = sorted(
                [item for item in available.items() if item[1] > 0],
                key=lambda x: (get_soldier_tier(x[0]), get_soldier_power(x[0])),
                reverse=True
            )

            for tid, count in sorted_avail:
                if missing_power <= 0 and accumulated_count >= MIN_ATTACK_ARMY_COUNT:
                    break
                p_per_unit = get_soldier_power(tid)
                units_needed = max(1, int(missing_power / p_per_unit) + 1)
                take = min(count, units_needed)
                if take > 0:
                    final_army_dict[tid] = final_army_dict.get(tid, 0) + take
                    accumulated_count += take
                    accumulated_power += take * p_per_unit
                    missing_power = max(0.0, missing_power - (take * p_per_unit))
                    troops_substituted = True

        # تحويل الجيش إلى صيغة الحزمة المطلوبة للسيرفر
        army_payload = [{"id": tid, "num": cnt} for tid, cnt in final_army_dict.items() if cnt > 0]

        meta_info = {
            "form_heroes": form_heroes,
            "form_pets": form_pets,
            "form_rune_pages": form_rune_pages,
            "target_power": target_form_power,
            "achieved_power": accumulated_power,
            "total_troops": accumulated_count,
            "substituted": troops_substituted,
        }

        if troops_substituted:
            self.log.info(
                f"🔄 [الحالة 2: تعويض التشكيلة] نقص في جنود التشكيلة ({formation_id}) — "
                f"تم الهجوم بجنود بديلين بإجمالي {accumulated_count:,} جندي (القوة: ~{int(accumulated_power):,})."
            )
        else:
            self.log.info(
                f"🎖️ تم تجهيز جنود التشكيلة ({formation_id}) كاملة: {accumulated_count:,} جندي (القوة: ~{int(accumulated_power):,})."
            )

        return army_payload, meta_info

    # ────────────────────────────────────────────────────────────────
    #  البحث عن الأهداف وإرسال الهجوم على الخريطة
    # ────────────────────────────────────────────────────────────────

    async def _search_target(self, map_type: int, sub_type: int, min_lv: int, max_lv: int, range_val: int = 80) -> Optional[Dict[str, Any]]:
        """البحث عن أقرب هدف متاح على الخريطة حول القلعة."""
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        r_c = await self.conn.query("1006", "25", {"uid": uid_int}, timeout=4)
        if not r_c or not r_c.get("retData"):
            return None
        cx, cy = int(r_c["retData"].get("x", 0)), int(r_c["retData"].get("y", 0))

        r_search = await self.conn.query("2011", "3", {
            "mapType": map_type,
            "subType": sub_type,
            "num": 5,
            "x": cx,
            "y": cy,
            "exclude": {str(t): True for t in self._excluded_targets},
            "minLv": min_lv,
            "maxLv": max_lv,
            "range": range_val
        }, timeout=5)

        candidates = r_search.get("result", []) if (r_search and isinstance(r_search, dict)) else []
        for cand in candidates:
            tid = str(cand.get("id"))
            if tid and tid not in self._excluded_targets:
                return cand

        return None

    # ────────────────────────────────────────────────────────────────
    #  محرك الأولوية 1: قتل غزاة الهيبة (Prestige Invaders)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_prestige_invaders(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية غزاة الهيبة (5 هجمات) مع تطبيق الحالات الخمس كاملة.
        """
        cfg = self.config.get("prestige_invaders", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 1] تم تخطي غزاة الهيبة (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        q_info = self.get_quest_info("invaders")
        if q_info.get("is_done"):
            self.log.info(f"✨ [أولوية 1] مهمة قتال غزاة الهيبة مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}).")
            return {"status": "already_done", "c_num": q_info["c_num"]}

        needed = int(cfg.get("count", 5))
        if q_info.get("found") and q_info.get("remaining", 0) > 0:
            needed = min(needed, q_info["remaining"])

        formation_id = int(cfg.get("formation_id", 1))
        target_lv = int(cfg.get("level", cfg.get("max_lv", 30)))
        min_lv = max(1, target_lv - 5)

        self.log.info(f"👾 ───【 الأولوية 1: قتل غزاة الهيبة (المطلوب: {needed} هجمات | تشكيلة: {formation_id}) 】───")

        attacks_sent = 0
        consecutive_errors = 0

        while attacks_sent < needed:
            # فحص مهلة الـ 20 دقيقة
            if self.is_time_expired():
                self.log.warning("⏱️ [انتهاء المهلة] انتهت مدة الـ 20 دقيقة المخصصة لمهمة المسيرات بالكامل.")
                return {"status": "timeout", "attacks_sent": attacks_sent}

            # ── الحالة 1: نفاذ الفيالق المتاحة ──────────────────────────
            if self.get_free_queues_count() <= 0:
                self.log.info(
                    "⏳ [الحالة 1: نفاذ الفيالق] جميع الفيالق مشغولة بالخارج — "
                    "البقاء في أولوية غزاة الهيبة والانتظار دقيقة كاملة (60 ثانية) لتفريغ فيلق..."
                )
                await asyncio.sleep(60)
                await self.sync_queues()

                # بعد الانتظار: إذا لا تزال الفيالق ممتلئة، تستمر الحلقة في الانتظار طالما الوقت متاح
                if self.get_free_queues_count() <= 0:
                    continue

            # ── تجهيز الجيش (معالجة الحالة 2 والحالة 3) ──────────────────
            army_payload, meta = await self._resolve_attack_army(formation_id)
            if army_payload is None:
                # الحالة 3: خروج فوري من المهمة ككل
                return {"status": "critical_no_army", "error": "insufficient_troops_castle_wide"}

            # اختيار الأبطال والمرافق
            chosen_heroes = self.pick_heroes_for_attack(meta.get("form_heroes", []))
            chosen_pets = self.pick_pet_for_attack(meta.get("form_pets", []))

            # البحث عن الغازي (mapType=6, subType=0)
            target = await self._search_target(map_type=6, sub_type=0, min_lv=min_lv, max_lv=target_lv, range_val=80)
            if not target:
                consecutive_errors += 1
                self.log.warning(f"⚠️ لم يتم العثور على غزاة في النطاق (خطأ {consecutive_errors}/3)")
                # ── الحالة 4: 3 أخطاء متتالية ➔ الانتقال للأولوية التالية ───
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ [الحالة 4] تكرر تعذر العثور على غزاة 3 مرات متتالية — تجاوز الأولوية 1 والانتقال للتالية.")
                    return {"status": "failed_max_retries", "attacks_sent": attacks_sent}
                await asyncio.sleep(5)
                continue

            tid, tx, ty = target.get("id"), target.get("x"), target.get("y")
            self._excluded_targets.add(str(tid))

            kingdom_id = int(self.conn.kingdom_id or 0)
            payload = {
                "needSend": False,
                "runePages": meta.get("form_rune_pages", {}),
                "heros": chosen_heroes,
                "matrixType": 1,
                "mapId": kingdom_id,
                "moveLineType": 3,
                "judianState": 0,
                "data": {
                    "to": {"x": int(tx), "y": int(ty), "id": str(tid)},
                    "army": army_payload,
                },
                "pets": chosen_pets,
            }

            self.log.info(f"🚀 [غزاة الهيبة ({attacks_sent + 1}/{needed})] إرسال مسيرة هجوم على الغازي #{tid} عند ({tx}, {ty})...")
            r_march = await self.conn.query("1007", "2", payload, timeout=8)

            if r_march and str(r_march.get("err", "0")) == "0":
                attacks_sent += 1
                consecutive_errors = 0
                for h in chosen_heroes:
                    self._busy_heroes.add(h)
                for item in army_payload:
                    self._used_army[item["id"]] = self._used_army.get(item["id"], 0) + item["num"]
                self.log.info(f"✅ نجح إرسال مسيرة الهجوم على الغازي #{tid}!")
                await asyncio.sleep(round(random.uniform(3.5, 6.0), 2))
            else:
                consecutive_errors += 1
                err_code = r_march.get("err") if r_march else "timeout"
                self.log.warning(f"⚠️ فشل إرسال المسيرة كود: {err_code} (خطأ {consecutive_errors}/3)")
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ [الحالة 4] تكرر خطأ إرسال المسيرة 3 مرات — الانتقال للأولوية التالية.")
                    return {"status": "failed_max_retries", "attacks_sent": attacks_sent}
                await asyncio.sleep(4)

        return {"status": "success", "attacks_sent": attacks_sent}

    # ────────────────────────────────────────────────────────────────
    #  محرك الأولوية 2: الهجوم على معقل الهيبة (Prestige Stronghold)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_prestige_stronghold(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية معقل الهيبة (هجمتان) مع تطبيق الحالات الخمس كاملة.
        """
        cfg = self.config.get("prestige_stronghold", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 2] تم تخطي معقل الهيبة (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        q_info = self.get_quest_info("stronghold")
        if q_info.get("is_done"):
            self.log.info(f"✨ [أولوية 2] مهمة معقل الهيبة مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}).")
            return {"status": "already_done", "c_num": q_info["c_num"]}

        needed = int(cfg.get("count", 2))
        if q_info.get("found") and q_info.get("remaining", 0) > 0:
            needed = min(needed, q_info["remaining"])

        formation_id = int(cfg.get("formation_id", 1))
        target_lv = int(cfg.get("level", cfg.get("max_lv", 30)))
        min_lv = max(1, target_lv - 5)

        self.log.info(f"🏰 ───【 الأولوية 2: الهجوم على معقل الهيبة (المطلوب: {needed} هجمات | تشكيلة: {formation_id}) 】───")

        attacks_sent = 0
        consecutive_errors = 0

        while attacks_sent < needed:
            if self.is_time_expired():
                self.log.warning("⏱️ [انتهاء المهلة] انتهت مدة الـ 20 دقيقة المخصصة لمهمة المسيرات بالكامل.")
                return {"status": "timeout", "attacks_sent": attacks_sent}

            # ── الحالة 1: نفاذ الفيالق المتاحة ──────────────────────────
            if self.get_free_queues_count() <= 0:
                self.log.info(
                    "⏳ [الحالة 1: نفاذ الفيالق] جميع الفيالق مشغولة بالخارج — "
                    "البقاء في أولوية معقل الهيبة والانتظار دقيقة كاملة (60 ثانية) لتفريغ فيلق..."
                )
                await asyncio.sleep(60)
                await self.sync_queues()

                if self.get_free_queues_count() <= 0:
                    continue

            # ── تجهيز الجيش (الحالة 2 والحالة 3) ─────────────────────────
            army_payload, meta = await self._resolve_attack_army(formation_id)
            if army_payload is None:
                return {"status": "critical_no_army", "error": "insufficient_troops_castle_wide"}

            chosen_heroes = self.pick_heroes_for_attack(meta.get("form_heroes", []))
            chosen_pets = self.pick_pet_for_attack(meta.get("form_pets", []))

            # البحث عن معقل الهيبة (mapType=26, subType=0)
            target = await self._search_target(map_type=26, sub_type=0, min_lv=min_lv, max_lv=target_lv, range_val=80)
            if not target:
                consecutive_errors += 1
                self.log.warning(f"⚠️ لم يتم العثور على معاقل في النطاق (خطأ {consecutive_errors}/3)")
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ [الحالة 4] تكرر تعذر العثور على معاقل 3 مرات متتالية — تجاوز أولوية المعقل.")
                    return {"status": "failed_max_retries", "attacks_sent": attacks_sent}
                await asyncio.sleep(5)
                continue

            tid, tx, ty = target.get("id"), target.get("x"), target.get("y")
            self._excluded_targets.add(str(tid))

            kingdom_id = int(self.conn.kingdom_id or 0)
            payload = {
                "needSend": False,
                "runePages": meta.get("form_rune_pages", {}),
                "heros": chosen_heroes,
                "matrixType": 1,
                "mapId": kingdom_id,
                "moveLineType": 3,
                "judianState": 1,  # معقل
                "data": {
                    "to": {"x": int(tx), "y": int(ty), "id": str(tid)},
                    "army": army_payload,
                },
                "pets": chosen_pets,
            }

            self.log.info(f"🚀 [معقل الهيبة ({attacks_sent + 1}/{needed})] إرسال مسيرة هجوم على المعقل #{tid} عند ({tx}, {ty})...")
            r_march = await self.conn.query("1007", "2", payload, timeout=8)

            if r_march and str(r_march.get("err", "0")) == "0":
                attacks_sent += 1
                consecutive_errors = 0
                for h in chosen_heroes:
                    self._busy_heroes.add(h)
                for item in army_payload:
                    self._used_army[item["id"]] = self._used_army.get(item["id"], 0) + item["num"]
                self.log.info(f"✅ نجح إرسال مسيرة الهجوم على المعقل #{tid}!")
                await asyncio.sleep(round(random.uniform(3.5, 6.0), 2))
            else:
                consecutive_errors += 1
                err_code = r_march.get("err") if r_march else "timeout"
                self.log.warning(f"⚠️ فشل إرسال مسيرة المعقل كود: {err_code} (خطأ {consecutive_errors}/3)")
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ [الحالة 4] تكرر خطأ مسيرة المعقل 3 مرات — تجاوز أولوية المعقل.")
                    return {"status": "failed_max_retries", "attacks_sent": attacks_sent}
                await asyncio.sleep(4)

        return {"status": "success", "attacks_sent": attacks_sent}

    # ────────────────────────────────────────────────────────────────
    #  محرك التنفيذ المركزي (Execution Pipeline)
    # ────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """تشغيل منسق الفيالق والمسيرات المركزي."""
        self.start_time = time.time()
        self.log.info("🎖️" + "═" * 60)
        self.log.info("🎖️ بدء مهمة منسق الفيالق والمسيرات الذكي الموحد (March Manager)")
        self.log.info(f"   • الحد الأقصى لطوابير الفيالق: {self.max_queues}")
        self.log.info(f"   • مدة تشغيل المهمة الإجمالية: {self.duration_minutes} دقيقة")
        self.log.info(f"   • قائمة الأولويات النشطة حالياً: {self.priority_order}")
        self.log.info("🎖️" + "═" * 60)

        # 0. التهيئة وتجديد بيانات الهيبة والفياللق والأبطال
        await self._refresh_merit_data()
        await self.sync_queues()
        await self._load_heroes()

        pipeline_results: Dict[str, Any] = {}

        # خريطة دوال الأولويات
        handlers = {
            "prestige_invaders": self.execute_priority_prestige_invaders,
            "prestige_stronghold": self.execute_priority_prestige_stronghold,
        }

        for p_key in self.priority_order:
            # فحص انتهاء الوقت
            if self.is_time_expired():
                self.log.warning("⏱️ انتهت المهلة الزمنية للمهمة (20 دقيقة) — إيقاف متابعة باقي الأولويات.")
                break

            handler = handlers.get(p_key)
            if not handler:
                self.log.debug(f"ℹ️ أولوية {p_key} سيتم إضافتها لاحقاً.")
                continue

            res = await handler()
            pipeline_results[p_key] = res

            # الحالة 3: إذا نفدت القوات كلياً من القلعة ➔ خروج فوري من المهمة ككل
            if res.get("status") == "critical_no_army":
                self.log.warning("🛑 [الحالة 3: خروج فوري] إنهاء مهمة المسيرات ككل لعدم توفر قوات كافية بالقلعة حتى خارج التشكيلة.")
                return TaskResult.fail(
                    "إنهاء مهمة المسيرات ككل: عدم توفر قوات كافية بالقلعة حتى خارج التشكيلة",
                    data=pipeline_results
                )

            await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))

        # ── الحالة 5: انتهاء الأولويات ──────────────────────────────
        active_final = self.get_active_marches_count()
        msg = f"🎉 [الحالة 5: اكتمال الأولويات] تم الانتهاء من جميع أولويات المسيرات بنجاح ({active_final}/{self.max_queues} فيالق نشطة بالخارج)."
        self.log.info(msg)
        return TaskResult.ok(msg, data=pipeline_results)
