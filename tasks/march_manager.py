# -*- coding: utf-8 -*-
"""
tasks/march_manager.py — منسق الفيالق والمسيرات الخارجي الموحد (March Orchestrator)
════════════════════════════════════════════════════════════════════════════════════════
يدير مسيرات خريطة المملكة وفق تسلسل أولويات ذكي مع تطبيق نظام الحالات الخمس الصارم:

  1. الحالة 1 (نفاذ الفيالق المتاحة):
     البقاء في نفس الأولوية والانتظار دقيقة كاملة (60 ثانية) ثم إعادة الفحص،
     في ضوء وقت المهمة الكامل (افتراضياً 20 دقيقة).
  2. الحالة 2 (نقص جنود التشكيلة المحددة):
     الهجوم بأي جنود متوفرين بالقلعة لتعويض النقص بأفضل قوات قتالية متوازنة.
  3. الحالة 3 (انعدام القوات بالقلعة كلياً):
     في حال عدم توفر قوات كافية حتى خارج التشكيلة (أقل من 300 جندي)، يخرج البوت من المهمة ككل فوراً.
  4. الحالة 4 (خطأ غير متوقع / فشل الهجوم):
     محاولة 3 مرات في الأولوية الحالية؛ وإذا تكرر الفشل يتم تجاوز هذه الأولوية والانتقال للأولوية التالية.
  5. الحالة 5 (اكتمال الأولويات):
     عند انتهاء الأولويات المفعلة يخرج البوت من المهمة بنجاح.

الأولويات المنفذة حالياً:
  [1] غزاة الهيبة (Prestige Invaders - CMD 4112004):
      - فحص مسبق لـ meritoriousTaskCtrl لتأكيد حالة إنجاز المهمة.
      - الهجوم بالعدد المتبقي المطلوب حصراً عبر وحدة tasks.monster (MonsterTask).
      - إذا كانت مكتملة مسبقاً ينتقل فوراً للأولوية التالية.

  [2] معقل الهيبة (Prestige Stronghold - CMD 4112030):
      - فحص مسبق لـ meritoriousTaskCtrl لتأكيد حالة إنجاز المهمة.
      - الهجوم بمرتين كحد أقصى لإنجاز المهمة عبر وحدة tasks.stronghold (StrongholdTask).
"""

from __future__ import annotations

import sys
import os
import asyncio
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
from tasks.monster import MonsterTask
from tasks.stronghold import StrongholdTask
from tasks.gather import GatherTask

# ── معرفات مهام الهيبة من السيرفر (meritoriousTaskCtrl) ───────────────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "invaders": 4112004,      # الهجوم على الغزاة في الخريطة (5 هجمات)
    "stronghold": 4112030,    # احتلال المعقل / الملجأ (مرتان)
    "gather_food": 4112000,   # جمع القمح من الخريطة (مرة واحدة)
    "gather_wood": 4112001,   # جمع الخشب من الخريطة (مرة واحدة)
    "gather_iron": 4112002,   # جمع الحجر / الحديد من الخريطة (مرة واحدة)
    "gather_silver": 4112003, # جمع الكوارتز / الفضة من الخريطة (مرة واحدة)
}

# قائمة مهام جمع موارد الهيبة الأربعة
PRESTIGE_GATHER_RESOURCES = [
    {"key": "gather_food",   "res_type": 2, "name": "القمح (Food)",   "quest_id": 4112000},
    {"key": "gather_wood",   "res_type": 3, "name": "الخشب (Wood)",   "quest_id": 4112001},
    {"key": "gather_iron",   "res_type": 4, "name": "الحديد (Iron)",  "quest_id": 4112002},
    {"key": "gather_silver", "res_type": 5, "name": "الفضة (Silver)", "quest_id": 4112003},
]

# أدنى حد للجنود بالقلعة لإطلاق مسيرة (إذا كان المجموع أقل منه نعتبر القلعة خالية)
MIN_ATTACK_ARMY_COUNT = 300


class MarchManagerTask(BaseTask):
    """
    منسق الفيالق والمسيرات الذكي الموحد.
    يدير الأولويات الخارجية بالاعتماد المباشر على مهام القتال والجمع المتخصصة (monster.py و stronghold.py و gather.py).
    """
    name = "march_manager"

    DEFAULT_PRIORITY_ORDER = [
        "prestige_invaders",
        "prestige_stronghold",
        "prestige_gather",
    ]

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config or {})
        self.max_queues = int(self.config.get("max_queues", 6))
        self.duration_minutes = float(self.config.get("duration_minutes", 20.0))
        self.priority_order = self.config.get("priority_order") or self.DEFAULT_PRIORITY_ORDER

        self.start_time: float = 0.0
        self.max_duration_seconds: float = self.duration_minutes * 60.0
        self._busy_heroes: Set[int] = set()
        self._used_pets: Set[int] = set()

    # ────────────────────────────────────────────────────────────────
    #  إدارة الوقت والمهلة الزمنية (20 دقيقة)
    # ────────────────────────────────────────────────────────────────

    def is_time_expired(self) -> bool:
        """فحص ما إذا تجاوزت المهمة المدة الكلية المحددة لها (20 دقيقة)."""
        if self.start_time <= 0:
            return False
        elapsed = time.time() - self.start_time
        return elapsed >= self.max_duration_seconds

    def get_remaining_seconds(self) -> float:
        """الوقت المتبقي بالثواني من المهلة الكلية للمهمة."""
        if self.start_time <= 0:
            return self.max_duration_seconds
        elapsed = time.time() - self.start_time
        return max(0.0, self.max_duration_seconds - elapsed)

    # ────────────────────────────────────────────────────────────────
    #  استعلام بيانات مهام الهيبة (Prestige Quests State)
    # ────────────────────────────────────────────────────────────────

    async def _refresh_merit_data(self) -> bool:
        """تحديث بيانات مهام الهيبة اليومية من السيرفر مباشرة."""
        try:
            r = await self.conn.query("1013", "1", {}, timeout=5)
            if r and isinstance(r, dict) and "data" in r:
                merit_data = r["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    return True
        except Exception as e:
            self.log.debug(f"استعلام 1013/1 لتحديث مهام الهيبة لم يكتمل: {e}")

        try:
            r_all = await self.conn.query("1001", "1", {}, timeout=6)
            if r_all and isinstance(r_all, dict) and "data" in r_all:
                merit_data = r_all["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    return True
        except Exception as e:
            self.log.debug(f"استعلام 1001/1 لتحديث مهام الهيبة لم يكتمل: {e}")

        return False

    def get_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]:
        """جلب تفاصيل مهمة معينة من meritoriousTaskCtrl لمعرفة هل أنجزت وكم متبقي منها."""
        if isinstance(quest_key_or_id, int):
            qid = quest_key_or_id
        else:
            norm_key = str(quest_key_or_id).strip().lower()
            qid = PRESTIGE_QUEST_IDS.get(norm_key, 0)

        merit_ctrl = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if not isinstance(merit_ctrl, dict):
            return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

        # 1. فحص taskData (القاموس الرئيسي لمهام الهيبة)
        task_data = merit_ctrl.get("taskData", {})
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
                    "status": status,
                    "is_done": is_done,
                    "remaining": remaining,
                }

        # 2. فحص قائمة tasks البديلة
        tasks_list = merit_ctrl.get("tasks", [])
        if isinstance(tasks_list, list):
            for t_item in tasks_list:
                if isinstance(t_item, dict) and int(t_item.get("id", 0)) == qid:
                    c_num = int(t_item.get("cNum", t_item.get("c_num", 0)))
                    l_num = int(t_item.get("lNum", t_item.get("l_num", 0)))
                    status = int(t_item.get("status", 0))
                    is_done = (status == 4) or (l_num > 0 and c_num >= l_num)
                    remaining = max(0, l_num - c_num) if l_num > 0 else 0
                    return {
                        "found": True,
                        "task_id": qid,
                        "c_num": c_num,
                        "l_num": l_num,
                        "status": status,
                        "is_done": is_done,
                        "remaining": remaining,
                    }

        return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

    # ────────────────────────────────────────────────────────────────
    #  فحص الجيش الإجمالي بالقلعة (الحالة 3: انعدام القوات)
    # ────────────────────────────────────────────────────────────────

    async def get_total_available_castle_army(self) -> int:
        """حساب إجمالي عدد الجنود المتاحين داخل القلعة حالياً عبر CMD 1005/1."""
        total = 0
        try:
            r_army = await self.conn.query("1005", "1", {}, timeout=5)
            if r_army and "data" in r_army:
                total_army = r_army["data"].get("totalArmy", {})
                if isinstance(total_army, dict):
                    for k, v in total_army.items():
                        if str(k).isdigit() and str(v).isdigit():
                            tid = int(k)
                            # استبعاد فخاخ الجدار وأسلحة الدفاع (800..899)
                            if not (800 <= tid < 900):
                                total += int(v)
        except Exception as e:
            self.log.debug(f"خطأ غير حرج أثناء استعلام الجيش 1005/1: {e}")

        return total

    def get_active_marches_count(self) -> int:
        """حساب عدد الفيالق والمسيرات النشطة حالياً خارج القلعة من بيانات الطوابير."""
        active = 0
        all_queue_data = []
        if getattr(self.conn, 'local_queues', None):
            all_queue_data.extend(self.conn.local_queues)
        for p in self.conn.cached_packets.values():
            if isinstance(p, dict):
                d = p.get('data', {})
                if isinstance(d, dict) and d.get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC':
                    nd = d.get('notifyData', [])
                    if isinstance(nd, list):
                        all_queue_data.extend(nd)

        for item in all_queue_data:
            q_list = item.get('data', []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
            for q in q_list:
                if isinstance(q, dict) and q.get('status') in (1, 2, 3, 4, 7):
                    active += 1
        return active

    async def get_active_gather_resource_types(self) -> Set[int]:
        """
        فحص الفيالق النشطة بالخارج وتحديد أنواع الموارد التي توجد لها مسيرات جمع قائمة حالياً
        (2=قمح, 3=خشب, 4=حديد, 5=فضة, 1=ذهب):
          - يطلب تحديثاً فورياً لطوابير المسيرات من السيرفر (CMD 1007/1000).
          - يفحص بيانات الهدف (to) ونقطة الانطلاق (from) وكود المورد (subMapType و resourceType).
          - يتيح تخطي إرسال مسيرة مكررة لنفس المورد إذا كانت هناك مسيرة تجمعه حالياً ولم تعد بعد.
        """
        active_res_types: Set[int] = set()
        try:
            # استعلام فوري لتحديث بيانات الفيالق من السيرفر
            await self.conn.query('1007', '1000', {}, timeout=3)
            await asyncio.sleep(0.4)
        except Exception:
            pass

        all_queue_data = []
        if getattr(self.conn, 'local_queues', None):
            all_queue_data.extend(self.conn.local_queues)
        for p in self.conn.cached_packets.values():
            if isinstance(p, dict):
                d = p.get('data', {})
                if isinstance(d, dict) and d.get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC':
                    nd = d.get('notifyData', [])
                    if isinstance(nd, list):
                        all_queue_data.extend(nd)

        for item in all_queue_data:
            q_list = item.get('data', []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
            for q in q_list:
                if not isinstance(q, dict):
                    continue
                # مسيرة نشطة (1=متجهة, 2=تجمع بالحقل, 3=عائدة, 4=مرابطة, 7=حشد)
                if q.get('status') not in (1, 2, 3, 4, 7):
                    continue

                res_sub_type = None

                # 1. فحص الهدف (to)
                to_info = q.get('to', {})
                if isinstance(to_info, dict):
                    if to_info.get('mapType') == 5:
                        res_sub_type = to_info.get('subMapType')
                    if not res_sub_type and to_info.get('id'):
                        parts = str(to_info.get('id')).split('-')
                        if len(parts) >= 4 and parts[2] == '5' and parts[3].isdigit():
                            res_sub_type = int(parts[3])

                # 2. فحص نقطة الانطلاق (from) في حال كانت المسيرة في طريق العودة للقلعة
                if not res_sub_type:
                    from_info = q.get('from', {})
                    if isinstance(from_info, dict):
                        if from_info.get('mapType') == 5:
                            res_sub_type = from_info.get('subMapType')
                        if not res_sub_type and from_info.get('id'):
                            parts = str(from_info.get('id')).split('-')
                            if len(parts) >= 4 and parts[2] == '5' and parts[3].isdigit():
                                res_sub_type = int(parts[3])

                # 3. فحص كود المورد في data (resourceType)
                if not res_sub_type:
                    data_obj = q.get('data', {})
                    if isinstance(data_obj, dict):
                        res_code = data_obj.get('resourceType')
                        if res_code:
                            code_to_sub = {1001: 1, 1002: 2, 1003: 3, 1004: 4, 1005: 5}
                            res_sub_type = code_to_sub.get(int(res_code))

                if res_sub_type and int(res_sub_type) in (1, 2, 3, 4, 5):
                    active_res_types.add(int(res_sub_type))

        return active_res_types

    async def ensure_army_or_wait(self, context_desc: str = "") -> bool:
        """
        التحقق الذكي من توفر الجيش بالقلعة أو الانتظار لعودته من المسيرات:
          - إذا كانت قوات القلعة >= 300: يعيد True فوراً (جاهزية تامة).
          - إذا كانت قوات القلعة < 300 وتوجد مسيرات نشطة بالخارج:
            تُطبق الحالة 1 بالانتظار 60 ثانية لعودة الفيالق، وتتكرر طالما لم تنته مهلة الـ 20 دقيقة.
          - إذا كانت قوات القلعة < 300 والمسيرات بالخارج = 0 (جميع الفيالق داخل القلعة):
            تُطبق الحالة 3 (انعدام القوات كلياً) ويعيد False للخروج الفوري.
        """
        while not self.is_time_expired():
            castle_troops = await self.get_total_available_castle_army()
            if castle_troops >= MIN_ATTACK_ARMY_COUNT:
                return True

            active_marches = self.get_active_marches_count()
            if active_marches > 0:
                self.log.info(
                    f"⏳ [الحالة 1: القوات في مسيرات بالخارج ({active_marches} مسيرات نشطة)] "
                    f"رصيد القلعة الحالي ({castle_troops}) — انتظار دقيقة كاملة (60 ثانية) لعودة الجيش {context_desc}..."
                )
                await asyncio.sleep(60)
                await self._refresh_merit_data()
            else:
                self.log.warning(
                    f"🛑 [الحالة 3: انعدام القوات كلياً] لا توجد أي مسيرات بالخارج (0 مسيرة نشطة) "
                    f"وإجمالي قوات القلعة ({castle_troops}) أقل من الحد الأدنى ({MIN_ATTACK_ARMY_COUNT}) — الخروج فوراً."
                )
                return False

        self.log.warning("⏱️ [انتهاء المهلة] انتهت الـ 20 دقيقة المحددة للمهمة أثناء انتظار عودة الجيش.")
        return False

    # ────────────────────────────────────────────────────────────────
    #  ربط سجلات المهام الفرعية بسجل المهمة الحالي
    # ────────────────────────────────────────────────────────────────

    def _forward_subtask_logs(self, subtask: BaseTask):
        """توجيه سجلات المهمة الفرعية (monster أو stronghold) إلى سجل منسق الفيالق."""
        if hasattr(subtask, "log") and subtask.log and hasattr(self, "log") and self.log:
            subtask.log.handlers = list(self.log.handlers)
            subtask.log.setLevel(self.log.level)
            subtask.log.propagate = False

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 1: غزاة الهيبة (Prestige Invaders) عبر monster.py
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_prestige_invaders(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية قتال غزاة الهيبة (5 هجمات) بالاعتماد المباشر على وحدة monster.py:
          1. استعلام حالة مهمة غزاة الهيبة (#4112004).
          2. إذا كانت مكتملة، يتم تخطيها فوراً والانتقال للأولوية التالية.
          3. إذا لم تكن مكتملة، يتم الهجوم بالعدد المتبقي المطلوب حصراً.
          4. تطبيق الحالة 1 (انتظار 60ث عند امتلاء الطوابير) والحالة 2 (تعويض التشكيلة) والحالة 3 (الخروج عند انعدام القوات).
        """
        cfg = self.config.get("prestige_invaders", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 1] تم تخطي غزاة الهيبة (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        # استعلام أحدث بيانات الهيبة
        await self._refresh_merit_data()
        q_info = self.get_quest_info("invaders")

        if q_info.get("is_done"):
            self.log.info(f"✨ [أولوية 1: غزاة الهيبة] مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}). الانتقال للأولوية التالية مباشرة.")
            return {"status": "already_done", "c_num": q_info["c_num"]}

        # حساب عدد الهجمات المتبقية لإنجاز المهمة بدقة
        needed = int(cfg.get("count", 5))
        if q_info.get("found") and q_info.get("remaining", 0) > 0:
            needed = q_info["remaining"]

        self.log.info(f"👾 ───【 الأولوية 1: قتل غزاة الهيبة (المتبقي لإنجاز المهمة: {needed} هجمات) 】───")

        # فحص مسبق ذكي للجيش بالقلعة (التمييز بين مسيرات بالخارج وبين انعدام كلي)
        has_army = await self.ensure_army_or_wait("لهجوم غزاة الهيبة")
        if not has_army:
            return {"status": "critical_no_army"}

        # حساب دورات الانتظار المتاحة لطوابير الفيالق ضمن مهلة الـ 20 دقيقة (الحالة 1: انتظار دقيقة = 60 ثانية)
        rem_seconds = self.get_remaining_seconds()
        max_wait_cycles = max(1, int(rem_seconds // 60))

        # تجهيز إعدادات MonsterTask للهجوم على الغزاة
        monster_cfg = {
            "monster_type": "invaders",
            "max_marches": needed,
            "min_lv": int(cfg.get("min_lv", 1)),
            "max_lv": int(cfg.get("max_lv", 30)),
            "formation_id": int(cfg.get("formation_id", 1)),
            "search_range": int(cfg.get("search_range", 80)),
            "wait_for_queue": True,          # الحالة 1: الانتظار عند امتلاء الفيالق
            "wait_interval": 60.0,           # انتظار 60 ثانية كاملة كما هو مطلوب
            "max_wait_cycles": max_wait_cycles,
            "troops_count": int(cfg.get("troops_count", 30000)),
        }

        monster_task = MonsterTask(self.conn, monster_cfg)
        self._forward_subtask_logs(monster_task)

        task_res = await monster_task.run()

        # فحص الحالة 3 بعد المحاولة: هل نفد الجيش كلياً؟
        if task_res.data.get("stop_reason") == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم الغزاة")
            if not has_army:
                return {"status": "critical_no_army"}

        # تحديث بيانات الهيبة لفحص النتيجة
        await self._refresh_merit_data()
        updated_q = self.get_quest_info("invaders")
        if updated_q.get("is_done"):
            self.log.info(f"🎉 [أولوية 1: غزاة الهيبة] تم إكمال مهمة الهيبة بنجاح ({updated_q['c_num']}/{updated_q['l_num']})!")
        else:
            self.log.info(f"ℹ️ [أولوية 1: غزاة الهيبة] تقدم المهمة الحالي: ({updated_q['c_num']}/{updated_q['l_num']}).")

        return {
            "status": "completed" if updated_q.get("is_done") else "partial",
            "sent": task_res.data.get("sent", 0),
            "quest_info": updated_q,
        }

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 2: معقل الهيبة (Prestige Stronghold) عبر stronghold.py
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_prestige_stronghold(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية الهجوم على معقل الهيبة (مرتان كحد أقصى) بالاعتماد المباشر على وحدة stronghold.py:
          1. استعلام حالة مهمة معقل الهيبة (#4112030).
          2. إذا كانت مكتملة، يتم تخطيها فوراً والانتقال للأولوية التالية.
          3. إذا لم تكن مكتملة، يتم الهجوم بمرتين كحد أقصى لإنجازها.
          4. تطبيق الحالة 1 (انتظار 60ث عند امتلاء الطوابير) والحالة 2 والحالة 3.
        """
        cfg = self.config.get("prestige_stronghold", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 2] تم تخطي معقل الهيبة (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        # استعلام أحدث بيانات الهيبة
        await self._refresh_merit_data()
        q_info = self.get_quest_info("stronghold")

        if q_info.get("is_done"):
            self.log.info(f"✨ [أولوية 2: معقل الهيبة] مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}). الانتقال للأولوية التالية مباشرة.")
            return {"status": "already_done", "c_num": q_info["c_num"]}

        # مهمة المعقل باللعبة تتطلب مرتين كحد أقصى (وليس 5)
        needed = 2
        if q_info.get("found") and q_info.get("remaining", 0) > 0:
            needed = min(2, q_info["remaining"])

        self.log.info(f"🏰 ───【 الأولوية 2: الهجوم على معقل الهيبة (المتبقي لإنجاز المهمة: {needed} هجمات [بحد أقصى مرتين]) 】───")

        # فحص مسبق ذكي للجيش بالقلعة (التمييز بين مسيرات بالخارج وبين انعدام كلي)
        has_army = await self.ensure_army_or_wait("لهجوم معقل الهيبة")
        if not has_army:
            return {"status": "critical_no_army"}

        rem_seconds = self.get_remaining_seconds()
        max_wait_cycles = max(1, int(rem_seconds // 60))

        # تجهيز إعدادات StrongholdTask للهجوم على المعقل
        stronghold_cfg = {
            "max_marches": needed,
            "min_lv": int(cfg.get("min_lv", 1)),
            "max_lv": int(cfg.get("max_lv", 35)),
            "formation_id": int(cfg.get("formation_id", 1)),
            "search_range": int(cfg.get("search_range", 80)),
            "wait_for_queue": True,          # الحالة 1: الانتظار عند امتلاء الفيالق
            "wait_interval": 60.0,           # انتظار 60 ثانية كاملة
            "max_wait_cycles": max_wait_cycles,
            "troops_count": int(cfg.get("troops_count", 30000)),
        }

        stronghold_task = StrongholdTask(self.conn, stronghold_cfg)
        self._forward_subtask_logs(stronghold_task)

        task_res = await stronghold_task.run()

        # فحص الحالة 3 بعد المحاولة: هل نفد الجيش كلياً؟
        if task_res.data.get("stop_reason") == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم المعقل")
            if not has_army:
                return {"status": "critical_no_army"}

        # تحديث بيانات الهيبة لفحص النتيجة
        await self._refresh_merit_data()
        updated_q = self.get_quest_info("stronghold")
        if updated_q.get("is_done"):
            self.log.info(f"🎉 [أولوية 2: معقل الهيبة] تم إكمال مهمة المعقل بنجاح ({updated_q['c_num']}/{updated_q['l_num']})!")
        else:
            self.log.info(f"ℹ️ [أولوية 2: معقل الهيبة] تقدم مهمة المعقل الحالي: ({updated_q['c_num']}/{updated_q['l_num']}).")

        return {
            "status": "completed" if updated_q.get("is_done") else "partial",
            "sent": task_res.data.get("sent", 0),
            "quest_info": updated_q,
        }

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 3: جمع موارد الهيبة (Prestige Gather) عبر gather.py
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_prestige_gather(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية جمع موارد الهيبة اليومية (القمح، الخشب، الحديد، الفضة) عبر gather.py:
          1. استعلام حالة مهام جمع الموارد الأربعة من meritoriousTaskCtrl.
          2. تخطي الموارد المنجزة مسبقاً.
          3. إرسال مسيرة جمع عادية واحدة بحمولة الحقل كاملة لكل مورد غير مكتمل.
          4. تطبيق الحالات الخمس (نفاذ الفيالق 60ث، نقص التشكيلة، انعدام الجيش، تعذر الأهداف).
        """
        cfg = self.config.get("prestige_gather", {})
        if not cfg.get("enabled", True):
            self.log.info("⏭️ [أولوية 3] تم تخطي جمع موارد الهيبة (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        # استعلام أحدث بيانات الهيبة
        await self._refresh_merit_data()

        # فحص الفيالق النشطة بالخارج للتأكد من عدم وجود مسيرة جمع قائمة لأي مورد
        active_gather_types = await self.get_active_gather_resource_types()

        uncompleted = []
        for item in PRESTIGE_GATHER_RESOURCES:
            q_info = self.get_quest_info(item["quest_id"])
            if q_info.get("is_done"):
                self.log.info(f"✨ [أولوية 3] مهمة جمع {item['name']} مكتملة مسبقاً ({q_info.get('c_num', 1)}/{q_info.get('l_num', 1)}).")
            elif item["res_type"] in active_gather_types:
                self.log.info(
                    f"🌾 [أولوية 3] توجد مسيرة نشطة بالخارج حالياً لجمع {item['name']} "
                    f"(الفيلق قائم بالخريطة ولم يعد للقلعة بعد) — يتم تخطي إرسال مسيرة جديدة."
                )
            else:
                uncompleted.append((item, q_info))

        if not uncompleted:
            self.log.info("✨ [أولوية 3: جمع موارد الهيبة] جميع مهام جمع الموارد الأربعة مكتملة أو توجد لها مسيرات قائمة بالخارج.")
            return {"status": "already_done", "remaining": 0}

        self.log.info(f"🌾 ───【 الأولوية 3: جمع موارد الهيبة (المتبقي: {len(uncompleted)} مهام من أصل 4) 】───")

        sent_total = 0
        results_by_res = {}

        for item, q_info in uncompleted:
            if self.is_time_expired():
                self.log.warning("⏱️ [انتهاء المهلة] انتهت مدة الـ 20 دقيقة المخصصة للمهمة بالكامل.")
                break

            self.log.info(f"🌾 ───【 جمع مورد الهيبة: {item['name']} (مهمة #{item['quest_id']}) 】───")

            # فحص مسبق ذكي للجيش بالقلعة (التمييز بين مسيرات بالخارج وبين انعدام كلي)
            has_army = await self.ensure_army_or_wait(f"لجمع {item['name']}")
            if not has_army:
                return {"status": "critical_no_army"}

            # محاولة إرسال مسيرة جمع عادية واحدة بحمولة الحقل كاملة مع معالجة الحالات
            consecutive_errs = 0
            while not self.is_time_expired():
                gather_cfg = {
                    "res_type": item["res_type"],
                    "max_marches": 1,
                    "level": int(cfg.get("level", 6)),
                    "search_range": int(cfg.get("search_range", 100)),
                    "busy_heroes": list(self._busy_heroes),
                    "used_pets": list(self._used_pets),
                }

                gather_task = GatherTask(self.conn, gather_cfg)
                self._forward_subtask_logs(gather_task)
                res = await gather_task.run()

                # تراكم وتحديث الأبطال والحيوانات المشغولة عبر جميع الموارد
                self._busy_heroes.update(gather_task._busy_heroes)
                self._used_pets.update(gather_task._used_pets)

                if res.success and res.data.get("sent", 0) > 0:
                    sent_total += 1
                    results_by_res[item["key"]] = "sent"
                    active_gather_types.add(item["res_type"])
                    self.log.info(f"✅ تم إرسال مسيرة جمع عادية لـ {item['name']} بنجاح لإنجاز مهمة الهيبة!")
                    break

                # الحالة 1: الفيالق ممتلئة بالكامل بالخارج
                if res.data.get("queue_full"):
                    self.log.info(f"⏳ [الحالة 1: نفاذ الفيالق] جميع الفيالق مشغولة بالخارج — الانتظار دقيقة كاملة (60 ثانية) لتفريغ فيلق لجمع {item['name']}...")
                    await asyncio.sleep(60)
                    continue

                # فحص الحالة 3: انعدام الجيش بالقلعة
                if res.data.get("stop_reason") == "NO_ARMY":
                    has_army = await self.ensure_army_or_wait(f"لمتابعة جمع {item['name']}")
                    if not has_army:
                        return {"status": "critical_no_army"}
                    continue

                # أخطاء أخرى مثل تعذر إيجاد هدف في النطاق (الحالة 4: تجاوز بعد 3 محاولات)
                consecutive_errs += 1
                if consecutive_errs >= 3:
                    self.log.warning(f"⚠️ [الحالة 4] تكرر تعذر إرسال مسيرة جمع {item['name']} (3 محاولات) — الانتقال للمورد التالي.")
                    results_by_res[item["key"]] = "failed_max_retries"
                    break
                await asyncio.sleep(3)

            # مهلة أمان بين إطلاق مسيرات الموارد
            await asyncio.sleep(round(random.uniform(4.0, 7.0), 2))

        # تحديث بيانات الهيبة
        await self._refresh_merit_data()

        return {
            "status": "completed",
            "sent": sent_total,
            "results": results_by_res,
        }

    # ────────────────────────────────────────────────────────────────
    #  محرك التنفيذ المركزي (Execution Pipeline)
    # ────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """تشغيل منسق الفيالق والمسيرات المركزي عبر استدعاء المهام المتخصصة بالترتيب."""
        self.start_time = time.time()
        self.log.info("🎖️" + "═" * 60)
        self.log.info("🎖️ بدء مهمة منسق الفيالق والمسيرات الذكي الموحد (March Manager)")
        self.log.info(f"   • الحد الأقصى لطوابير الفيالق: {self.max_queues}")
        self.log.info(f"   • مدة تشغيل المهمة الإجمالية: {self.duration_minutes} دقيقة")
        self.log.info(f"   • قائمة الأولويات النشطة حالياً: {self.priority_order}")
        self.log.info("🎖️" + "═" * 60)

        # 0. التهيئة واستعلام بيانات الهيبة والجيش
        await self._refresh_merit_data()

        pipeline_results: Dict[str, Any] = {}

        # خريطة دوال الأولويات
        handlers = {
            "prestige_invaders": self.execute_priority_prestige_invaders,
            "prestige_stronghold": self.execute_priority_prestige_stronghold,
            "prestige_gather": self.execute_priority_prestige_gather,
        }

        for p_key in self.priority_order:
            # فحص انتهاء الوقت الكلي للمهمة
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
        msg = "🎉 [الحالة 5: اكتمال الأولويات] تم الانتهاء من جميع أولويات المسيرات بنجاح."
        self.log.info(msg)
        return TaskResult.ok(msg, data=pipeline_results)
