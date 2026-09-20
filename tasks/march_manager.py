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

# ── معرفات مهام الهيبة من السيرفر (meritoriousTaskCtrl) ───────────────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "invaders": 4112004,    # الهجوم على الغزاة في الخريطة (5 هجمات)
    "stronghold": 4112030,  # احتلال المعقل / الملجأ (مرتان)
}

# أدنى حد للجنود بالقلعة لإطلاق مسيرة (إذا كان المجموع أقل منه نعتبر القلعة خالية)
MIN_ATTACK_ARMY_COUNT = 300


class MarchManagerTask(BaseTask):
    """
    منسق الفيالق والمسيرات الذكي الموحد.
    يدير الأولويات الخارجية بالاعتماد المباشر على مهام القتال المتخصصة (monster.py و stronghold.py).
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

        # فحص مسبق للجيش بالقلعة (الحالة 3: انعدام القوات كلياً)
        castle_troops = await self.get_total_available_castle_army()
        if castle_troops < MIN_ATTACK_ARMY_COUNT:
            self.log.warning(
                f"🛑 [الحالة 3: انعدام القوات] إجمالي قوات القلعة ({castle_troops}) أقل من الحد الأدنى ({MIN_ATTACK_ARMY_COUNT}) — "
                f"الخروج فوراً من مهمة المسيرات ككل."
            )
            return {"status": "critical_no_army", "castle_troops": castle_troops}

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
            current_troops = await self.get_total_available_castle_army()
            if current_troops < MIN_ATTACK_ARMY_COUNT:
                self.log.warning("🛑 [الحالة 3: خروج فوري] نفدت القوات المتاحة بالقلعة تماماً أثناء الهجوم على الغزاة.")
                return {"status": "critical_no_army", "castle_troops": current_troops}

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

        # فحص مسبق للجيش بالقلعة (الحالة 3: انعدام القوات كلياً)
        castle_troops = await self.get_total_available_castle_army()
        if castle_troops < MIN_ATTACK_ARMY_COUNT:
            self.log.warning(
                f"🛑 [الحالة 3: انعدام القوات] إجمالي قوات القلعة ({castle_troops}) أقل من الحد الأدنى ({MIN_ATTACK_ARMY_COUNT}) — "
                f"الخروج فوراً من مهمة المسيرات ككل."
            )
            return {"status": "critical_no_army", "castle_troops": castle_troops}

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
            current_troops = await self.get_total_available_castle_army()
            if current_troops < MIN_ATTACK_ARMY_COUNT:
                self.log.warning("🛑 [الحالة 3: خروج فوري] نفدت القوات المتاحة بالقلعة تماماً أثناء الهجوم على المعقل.")
                return {"status": "critical_no_army", "castle_troops": current_troops}

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
