# -*- coding: utf-8 -*-
"""
tasks/march_coordinator.py — محرك منسق الفيالق الموحد (March Coordinator Engine)
════════════════════════════════════════════════════════════════════════════════════════
نسخة مُعاد هيكلتها بالكامل من march_manager.py بفلسفة Task-Driven Action Protocol:

python tasks/march_coordinator.py -e shook123@gmail.com

python tasks/march_coordinator.py -e burcudemr@gmail.com -p prestige_invaders prestige_stronghold
  - المحرك لا يتخذ قرارات منطقية — المهمة الفرعية هي التي تُرجع الإجراء المطلوب.
  - 4 إجراءات قياسية فقط: NEXT_PRIORITY, TERMINATE, WAIT_AND_RETRY_SAME, SKIP_PRIORITY.
  - طبقة أمان احتياطية (Fallback) للمهام التي لم تُحدَّث بعد لترجع action صريح.
  - المهام الفرعية موجودة في ملفاتها الخاصة وهي التي تحتوي على كامل المنطق الوظيفي.
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# ── استيراد المهام الفرعية ─────────────────────────────────────────────────
from tasks.stronghold import StrongholdTask
from tasks.gather import GatherTask
from tasks.transport import TransportTask, is_transport_daily_limit_reached, set_transport_daily_limit_reached
from tasks.ruins import RuinsTask
from tasks.monster import MonsterTask
from tasks.gold_gather import GoldGatherTask
from tasks.abra import AbraTask

log = logging.getLogger("tasks")

# ── معرفات مهام الهيبة ────────────────────────────────────────────────────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "invaders":      4112004,
    "stronghold":    4112030,
    "gather_food":   4112000,
    "gather_wood":   4112001,
    "gather_iron":   4112002,
    "gather_silver": 4112003,
}

PRESTIGE_GATHER_RESOURCES = [
    {"key": "gather_food",   "res_type": 2, "name": "القمح (Food)",      "quest_id": 4112000},
    {"key": "gather_wood",   "res_type": 3, "name": "الخشب (Wood)",      "quest_id": 4112001},
    {"key": "gather_iron",   "res_type": 4, "name": "الحديد (Iron)",     "quest_id": 4112002},
    {"key": "gather_silver", "res_type": 5, "name": "الكوارنز (Silver)", "quest_id": 4112003},
]


# ════════════════════════════════════════════════════════════════════════════
#  الإجراءات الأربعة القياسية — CoordinatorAction
# ════════════════════════════════════════════════════════════════════════════

class CoordinatorAction:
    """الإجراءات الأربعة القياسية التي يستلمها المحرك من المهام الفرعية."""
    NEXT_PRIORITY       = "next_priority"       # انتقل للأولوية التالية فوراً
    TERMINATE           = "terminate"           # أوقف المنسق ككل
    WAIT_AND_RETRY_SAME = "wait_and_retry_same" # انتظر 3 دقائق وكرر نفس المهمة
    SKIP_PRIORITY       = "skip_priority"       # تخطَّ الأولوية الحالية فوراً


# ════════════════════════════════════════════════════════════════════════════
#  محرك منسق الفيالق الموحد — MarchCoordinatorTask
# ════════════════════════════════════════════════════════════════════════════

class MarchCoordinatorTask(BaseTask):
    """
    محرك منسق الفيالق الموحد.
    يتولى استدعاء المهام الفرعية بالترتيب وتنفيذ الإجراء الذي تُرجعه كل مهمة.
    """
    name = "march_coordinator"

    DEFAULT_PRIORITY_ORDER = [
        "abra",
        "prestige_invaders",
        "prestige_stronghold",
        "prestige_gather",
        "transport",
        "ruins",
        "combat",
        "stronghold",
        "gold_gather",
        "gather",
    ]

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config or {})
        self.duration_minutes    = float(self.config.get("duration_minutes", 20.0))
        self.priority_order: List[str] = self.config.get("priority_order") or self.DEFAULT_PRIORITY_ORDER
        self.start_time: float   = 0.0
        self.max_duration: float = self.duration_minutes * 60.0
        self._busy_heroes: Set[int] = set()
        self._used_pets:   Set[int] = set()
        self._last_merit_sync: float = 0.0
        self.log.propagate = True

    # ──────────────────────────────────────────────────────────────────────
    #  المحرك الرئيسي
    # ──────────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """المحرك الرئيسي: يستدعي كل أولوية بالترتيب وينفذ إجراءها."""
        self.start_time = time.time()
        self.log.info("🎖️ [منسق الفيالق] بدء دورة التنسيق")

        for p_key in self.priority_order:

            # 1. فحص انتهاء المهلة الزمنية الكلية
            if self._is_time_expired():
                self.log.warning("⏱️ انتهت المهلة الزمنية (20 دقيقة) — إيقاف باقي الأولويات.")
                break

            # 2. حلقة الإعادة (تُكرَّر فقط في حالة WAIT_AND_RETRY_SAME)
            while not self._is_time_expired():
                try:
                    result = await self._run_priority(p_key)
                except Exception as e:
                    self.log.error(f"❌ خطأ غير متوقع في أولوية [{p_key}]: {e}", exc_info=True)
                    result = TaskResult.fail(str(e), action=CoordinatorAction.NEXT_PRIORITY)

                # 3. استخلاص الإجراء
                action = getattr(result, "action", None) or result.data.get("action")
                if not action:
                    action = self._fallback_action(result, p_key)

                self.log.debug(f"[{p_key}] إجراء: {action}")

                # 4. تنفيذ الإجراء
                if action == CoordinatorAction.TERMINATE:
                    self.log.info(f"🛑 [{p_key}] إيقاف منسق الفيالق ككل.")
                    return TaskResult.ok("تم إنهاء مهمة منسق الفيالق ككل.")

                elif action == CoordinatorAction.WAIT_AND_RETRY_SAME:
                    # ── فحص شرط توفر أقرب فيلق قبل الانتظار (Zero-Request) ──
                    remaining_task_sec = self._remaining_seconds()
                    nearest_march_sec = self._get_nearest_march_remaining_seconds()

                    # إذا كان أقرب فيلق سيعود بعد انتهاء المهلة المتبقية للمنسق ككل:
                    # نخرج من المهمة فوراً دون إضاعة الوقت في انتظار عبثي
                    if nearest_march_sec is not None and nearest_march_sec > remaining_task_sec:
                        self.log.warning(
                            f"🏁 [{p_key}] أقرب فيلق سيتوفر بعد {nearest_march_sec / 60:.1f} دقيقة، "
                            f"بينما المتبقي لمهلة منسق الفيالق {remaining_task_sec / 60:.1f} دقيقة — "
                            f"إنهاء المهمة كلياً لتفادي الانتظار العبثي."
                        )
                        return TaskResult.ok(
                            f"اكتملت مهمة منسق الفيالق: أقرب فيلق متاح ({nearest_march_sec / 60:.1f} د) "
                            f"يتجاوز المهلة المتبقية للمنسق ({remaining_task_sec / 60:.1f} د)."
                        )

                    # إيضاح مدة أقرب فيلق في السجل عند المواصلة
                    near_info = f" (أقرب فيلق متوقع خلال {nearest_march_sec / 60:.1f} د)" if nearest_march_sec is not None else ""
                    self.log.info(f"⏳ [{p_key}] الفيالق ممتلئة{near_info} — انتظار 3 دقائق ثم إعادة المحاولة.")
                    has_time = await self._wait_minutes(3)
                    if not has_time:
                        return TaskResult.ok("انتهت المهلة أثناء الانتظار.")
                    continue  # إعادة نفس الأولوية

                else:
                    # NEXT_PRIORITY أو SKIP_PRIORITY: كلاهما ينتقل للتالي
                    if action == CoordinatorAction.SKIP_PRIORITY:
                        self.log.info(f"⏭️ [{p_key}] تخطي الأولوية فوراً.")
                    else:
                        self.log.info(f"➡️ [{p_key}] الانتقال للأولوية التالية.")
                    break  # خروج من while → للأولوية التالية في for

            # فاصل أدنى بين الأولويات
            await asyncio.sleep(round(random.uniform(1.5, 3.0), 2))

        self.log.info("✅ اكتملت دورة منسق الفيالق بنجاح.")
        return TaskResult.ok("✅ اكتملت دورة منسق الفيالق بنجاح لجميع الأولويات.")

    # ──────────────────────────────────────────────────────────────────────
    #  مُرسل الأولويات
    # ──────────────────────────────────────────────────────────────────────

    async def _run_priority(self, p_key: str) -> TaskResult:
        """يستدعي دالة الأولوية المناسبة ويعيد TaskResult."""
        handlers = {
            "abra":                 self._priority_abra,
            "prestige_invaders":    self._priority_prestige_invaders,
            "prestige_stronghold":  self._priority_prestige_stronghold,
            "prestige_gather":      self._priority_prestige_gather,
            "transport":            self._priority_transport,
            "ruins":                self._priority_ruins,
            "combat":               self._priority_combat,
            "stronghold":           self._priority_stronghold,
            "gold_gather":          self._priority_gold_gather,
            "gather":               self._priority_gather,
        }
        handler = handlers.get(p_key)
        if not handler:
            self.log.debug(f"ℹ️ أولوية [{p_key}] غير موجودة — تخطي.")
            return TaskResult.ok(f"أولوية [{p_key}] غير موجودة", action=CoordinatorAction.SKIP_PRIORITY)
        return await handler()

    # ──────────────────────────────────────────────────────────────────────
    #  طبقة الأمان الاحتياطية (Fallback)
    # ──────────────────────────────────────────────────────────────────────

    def _fallback_action(self, result: TaskResult, p_key: str) -> str:
        """
        تحديد الإجراء للمهام التي لم تُعيد action صريح بعد.
        تعمل بناءً على stop_reason من result.data.
        """
        stop = result.data.get("stop_reason", "") if result.data else ""
        status = result.data.get("status", "") if result.data else ""

        if stop in ("QUEUE_FULL", "8004", "9007004") or status == "queue_full":
            return CoordinatorAction.WAIT_AND_RETRY_SAME
        if stop in ("NO_ARMY", "8009") or status == "critical_no_army":
            return CoordinatorAction.TERMINATE
        if stop in ("STAMINA_EMPTY",) or status == "stamina_empty":
            return CoordinatorAction.NEXT_PRIORITY
        if stop in ("NOT_EVENT_DAY", "CASTLE_LV_LOW") or status in ("skipped", "already_done", "already_active"):
            return CoordinatorAction.SKIP_PRIORITY
        if stop in ("WEAK_ARMY",):
            self.log.info(f"⏳ [{p_key}] ضعف الجيش المتاح — انتظار 3 دقائق لعودة القوات.")
            return CoordinatorAction.WAIT_AND_RETRY_SAME
        if stop in ("SUICIDE_RISK", "NPC_LEVEL_LOCKED", "REBEL_PREREQUISITE_FAILED"):
            self.log.info(f"⏭️ [{p_key}] تخطي الأولوية الحالية ({stop}) — انتقال للتالية.")
            return CoordinatorAction.SKIP_PRIORITY
        if stop in ("CMD_OPTING",):
            self.log.info(f"⏳ [{p_key}] خادم اللعبة مشغول (CMD_OPTING) — انتظار 3 دقائق.")
            return CoordinatorAction.WAIT_AND_RETRY_SAME
        return CoordinatorAction.NEXT_PRIORITY

    # ──────────────────────────────────────────────────────────────────────
    #  أدوات مساعدة
    # ──────────────────────────────────────────────────────────────────────

    def _is_time_expired(self) -> bool:
        if self.start_time <= 0:
            return False
        return (time.time() - self.start_time) >= self.max_duration

    def _remaining_seconds(self) -> float:
        if self.start_time <= 0:
            return self.max_duration
        return max(0.0, self.max_duration - (time.time() - self.start_time))

    def _get_nearest_march_remaining_seconds(self) -> Optional[float]:
        """
        حساب الوقت المتبقي (بالثواني) لأقرب فيلق نشط سيعود للقلعة ويصبح متاحاً.
        يعتمد بنسبة 100% على الذاكرة الحية (Zero-Request) عبر conn.local_queues.
        يعيد None إذا لم تكن هناك طوابير نشطة أو تعذر قراءة التوقيت.
        """
        queues = getattr(self.conn, "local_queues", []) or []
        if not queues:
            return None

        now_ts = time.time()
        min_remaining: Optional[float] = None

        items_to_check = []
        for q in queues:
            if isinstance(q, dict):
                items_to_check.append(q)
            elif isinstance(q, list):
                items_to_check.extend([x for x in q if isinstance(x, dict)])

        for item in items_to_check:
            # تصفية الحالات النشطة (0=حشد، 1=ذهاب، 2=عمل/جمع، 3=عودة، 4=مرابطة، 7=حشد منطلق)
            status = item.get("status")
            if status is not None and status not in (0, 1, 2, 3, 4, 7):
                continue

            rem_sec: Optional[float] = None

            # 1. فحص الوقت المتبقي المباشر (remainTime / leftTime)
            for container in (item, item.get("data") if isinstance(item.get("data"), dict) else {}):
                for k in ("remainTime", "remain_time", "leftTime", "left_time", "remain"):
                    val = container.get(k)
                    if val is not None:
                        try:
                            s = float(val)
                            if s > 100_000_000:
                                s /= 1000.0
                            if s >= 0:
                                rem_sec = s
                                break
                        except (ValueError, TypeError):
                            pass
                if rem_sec is not None:
                    break

            # 2. فحص وقت الانتهاء المحدد (endTime / endtime / arriveTime)
            if rem_sec is None:
                for container in (item, item.get("data") if isinstance(item.get("data"), dict) else {}):
                    for k in ("endTime", "endtime", "actionEndTime", "arriveTime"):
                        val = container.get(k)
                        if val is not None:
                            try:
                                end_ts = float(val)
                                if end_ts > 100_000_000_000:
                                    end_ts /= 1000.0
                                if end_ts > 0:
                                    rem_sec = max(0.0, end_ts - now_ts)
                                    break
                            except (ValueError, TypeError):
                                pass
                    if rem_sec is not None:
                        break

            # 3. فحص وقت البدء + المدة الإجمالية (startTime + totalTime / realTotalTime)
            if rem_sec is None:
                for container in (item, item.get("data") if isinstance(item.get("data"), dict) else {}):
                    st = None
                    for k in ("startTime", "starttime", "beginTime", "begintime"):
                        v = container.get(k)
                        if v is not None:
                            try:
                                s = float(v)
                                if s > 100_000_000_000:
                                    s /= 1000.0
                                if s > 0:
                                    st = s
                                    break
                            except (ValueError, TypeError):
                                pass

                    tt = None
                    for k in ("totalTime", "totaltime", "realTotalTime", "needTime"):
                        v = container.get(k)
                        if v is not None:
                            try:
                                t = float(v)
                                if t > 100_000_000:
                                    t /= 1000.0
                                if t > 0:
                                    tt = t
                                    break
                            except (ValueError, TypeError):
                                pass

                    if st is not None and tt is not None:
                        rem_sec = max(0.0, (st + tt) - now_ts)
                        break

            if rem_sec is not None:
                if min_remaining is None or rem_sec < min_remaining:
                    min_remaining = rem_sec

        return min_remaining

    async def _wait_minutes(self, minutes: float) -> bool:
        """ينتظر المدة المحددة بالدقائق. يعيد False إذا انتهت مهلة الـ 20 دقيقة."""
        wait_sec = int(minutes * 60)
        step = 15
        elapsed = 0
        while elapsed < wait_sec:
            if self._is_time_expired():
                return False
            await asyncio.sleep(min(step, wait_sec - elapsed))
            elapsed += step
        return not self._is_time_expired()

    def _forward_logs(self, subtask: BaseTask):
        """توجيه سجلات المهمة الفرعية إلى سجل المنسق وتفعيل البث للتيرمنال."""
        if hasattr(subtask, "log") and self.log:
            subtask.log.handlers = list(self.log.handlers)
            subtask.log.setLevel(self.log.level)
            subtask.log.propagate = True

    async def _refresh_merit_data(self, force: bool = False) -> bool:
        """تحديث بيانات الهيبة مع كبح الاستعلامات المكررة."""
        now = time.time()
        if not force and "meritoriousTaskCtrl" in self.conn.init_data and (now - self._last_merit_sync < 120.0):
            return True
        try:
            r = await self.conn.query("1000", "1", {}, timeout=6)
            if r and isinstance(r, dict):
                data_obj = r.get("data", {})
                retdata = data_obj.get("retdata", {}) if isinstance(data_obj, dict) else (r.get("retdata", {}) if isinstance(r.get("retdata"), dict) else {})
                if isinstance(retdata, dict) and "meritoriousTaskCtrl" in retdata:
                    merit = retdata["meritoriousTaskCtrl"]
                    if isinstance(merit, dict):
                        self.conn.init_data["meritoriousTaskCtrl"] = merit
                        self._last_merit_sync = now
                        return True
        except Exception:
            pass

        return False

    def _get_quest_info(self, quest_key_or_id) -> Dict[str, Any]:
        """جلب تفاصيل مهمة الهيبة من الذاكرة الحية."""
        qid = quest_key_or_id if isinstance(quest_key_or_id, int) else PRESTIGE_QUEST_IDS.get(str(quest_key_or_id).strip().lower(), 0)
        merit_ctrl = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if not isinstance(merit_ctrl, dict):
            return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

        # فحص taskData
        task_data = merit_ctrl.get("taskData", {})
        if isinstance(task_data, dict) and str(qid) in task_data:
            t = task_data[str(qid)]
            if isinstance(t, dict):
                c, l, s = int(t.get("cNum", 0)), int(t.get("lNum", 0)), int(t.get("status", 0))
                return {"found": True, "task_id": qid, "c_num": c, "l_num": l, "status": s,
                        "is_done": (s == 4) or (l > 0 and c >= l), "remaining": max(0, l - c) if l > 0 else 0}

        # فحص قائمة tasks
        for t in merit_ctrl.get("tasks", []):
            if isinstance(t, dict) and int(t.get("id", 0)) == qid:
                c, l, s = int(t.get("cNum", 0)), int(t.get("lNum", 0)), int(t.get("status", 0))
                return {"found": True, "task_id": qid, "c_num": c, "l_num": l, "status": s,
                        "is_done": (s == 4) or (l > 0 and c >= l), "remaining": max(0, l - c) if l > 0 else 0}

        return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 0: وحش الذهب Abra
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_abra(self) -> TaskResult:
        abra_cfg = self.config.get("abra") or getattr(self.conn, "castle_config", {}).get("abra", {})
        if isinstance(abra_cfg, bool):
            abra_cfg = {"enabled": abra_cfg}
        elif not isinstance(abra_cfg, dict):
            abra_cfg = {}

        if not abra_cfg.get("enabled", False):
            return TaskResult.ok("abra معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        is_event_day = bool(abra_cfg.get("force", False)) or (now_utc.weekday() in (0, 2))
        if not is_event_day:
            return TaskResult.ok("ليس يوم حدث Abra", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="NOT_EVENT_DAY")

        x, y = int(abra_cfg.get("x", 0) or 0), int(abra_cfg.get("y", 0) or 0)
        if x <= 0 or y <= 0:
            self.log.warning("⚠️ [Abra] إحداثيات الوحش غير محددة — تخطي.")
            return TaskResult.ok("إحداثيات Abra مفقودة", action=CoordinatorAction.SKIP_PRIORITY)

        cfg = dict(abra_cfg)
        shared_form = self.config.get("combat", {}).get("formation_id", 1)
        cfg.setdefault("formation_id", shared_form)
        cfg["busy_heroes"] = list(self._busy_heroes)

        self.log.info(f"🐉 [Abra] بدء الهجوم على ({x}, {y})")
        task = AbraTask(self.conn, cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(getattr(task, "_busy_heroes", set()))
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 1: غزاة الهيبة
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_prestige_invaders(self) -> TaskResult:
        if not self.config.get("is_main_prestige_enabled", True):
            return TaskResult.ok("الهيبة معطلة", action=CoordinatorAction.SKIP_PRIORITY)

        cfg = self.config.get("prestige_invaders", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("prestige_invaders معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        await self._refresh_merit_data()
        q = self._get_quest_info("invaders")
        self.log.info(f"👾👾👾👾👾👾👾👾{q})")
        if q.get("is_done"):
            return TaskResult.ok(f"غزاة الهيبة مكتملة ({q['c_num']}/{q['l_num']})", action=CoordinatorAction.NEXT_PRIORITY)

        needed = int(5)
        if q.get("found") and q.get("remaining", 0) > 0:
            needed = q["remaining"]

        self.log.info(f"👾 [غزاة الهيبة] بدء الهجوم (متبقي: {needed})")

        max_lv_1 = int(cfg.get("max_lv", 30))
        if max_lv_1 <= 10 :
            min_lv1 = int(1)
        else :
            min_lv1 = max_lv_1 - 5

        monster_cfg = {
            "monster_type":   "invaders",
            "max_marches":    needed,
            "min_lv":         min_lv1,
            "max_lv":         max_lv_1,
            "formation_id":   int(cfg.get("formation_id", 1)),
            "search_range":   int(100),
            "wait_for_queue": False,
            "troops_count":   int(0),
            "busy_heroes":    list(self._busy_heroes),
        }
        task = MonsterTask(self.conn, monster_cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(getattr(task, "_busy", set()))
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 2: معقل الهيبة
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_prestige_stronghold(self) -> TaskResult:
        if not self.config.get("is_main_prestige_enabled", True):
            return TaskResult.ok("الهيبة معطلة", action=CoordinatorAction.SKIP_PRIORITY)

        cfg = self.config.get("prestige_stronghold", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("prestige_stronghold معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        await self._refresh_merit_data()
        q = self._get_quest_info("stronghold")
        q2 = self._get_quest_info("invaders")
        self.log.info(f"👾👾👾👾👾👾👾👾{q2})")
        if q.get("is_done"):
            return TaskResult.ok(f"معقل الهيبة مكتمل ({q['c_num']}/{q['l_num']})", action=CoordinatorAction.NEXT_PRIORITY)

        needed = 2
        if q.get("found") and q.get("remaining", 0) > 0:
            needed = min(2, q["remaining"])

        self.log.info(f"🏰 [معقل الهيبة] بدء الهجوم (متبقي: {needed})")

        max_lv_1 = int(cfg.get("max_lv", 30))
        if max_lv_1 <= 10 :
            min_lv1 = int(1)
        else :
            min_lv1 = max_lv_1 - 5
        stronghold_cfg = {
            "max_marches":    needed,
            "min_lv":         min_lv1,
            "max_lv":         max_lv_1,
            "formation_id":   int(cfg.get("formation_id", 1)),
            "search_range":   int(100),
            "wait_for_queue": False,
            "troops_count":   int(0),
            "busy_heroes":    list(self._busy_heroes),
        }
        task = StrongholdTask(self.conn, stronghold_cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(getattr(task, "_busy", set()))
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 3: جمع موارد الهيبة
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_prestige_gather(self) -> TaskResult:
        if not self.config.get("is_main_prestige_enabled", True):
            return TaskResult.ok("الهيبة معطلة", action=CoordinatorAction.SKIP_PRIORITY)

        cfg = self.config.get("prestige_gather", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("prestige_gather معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        await self._refresh_merit_data()
        active_gather = await self._get_active_gather_types()
        castle_lv = self._get_castle_level()

        uncompleted = []
        for item in PRESTIGE_GATHER_RESOURCES:
            q = self._get_quest_info(item["quest_id"])
            if q.get("is_done") or item["res_type"] in active_gather:
                continue
            if item["res_type"] == 4 and castle_lv < 10:
                self.log.info(f"🌾 تخطي جمع {item['name']} — يتطلب قلعة لفل 10 (لفلك: {castle_lv})")
                continue
            if item["res_type"] == 5 and castle_lv < 15:
                self.log.info(f"🌾 تخطي جمع {item['name']} — يتطلب قلعة لفل 15 (لفلك: {castle_lv})")
                continue
            uncompleted.append(item)

        if not uncompleted:
            return TaskResult.ok("موارد الهيبة مكتملة أو قيد الجمع", action=CoordinatorAction.NEXT_PRIORITY)

        self.log.info(f"🌾 [جمع الهيبة] بدء الجمع (متبقي: {len(uncompleted)} موارد)")
        sent_total = 0

        for item in uncompleted:
            if self._is_time_expired():
                break
            self.log.info(f"🌾 ───【 {item['name']} 】───")
            gather_cfg = {
                "res_type":       item["res_type"],
                "max_marches":    1,
                "level":          int(cfg.get("level", 6)),
                "search_range":   int(cfg.get("search_range", 100)),
                "busy_heroes":    list(self._busy_heroes),
                "used_pets":      list(self._used_pets),
                "allow_partial":  True,
                "min_load_ratio": 0.0,
                "max_heroes":     2,
            }
            task = GatherTask(self.conn, gather_cfg)
            self._forward_logs(task)
            res = await task.run()
            self._busy_heroes.update(task._busy_heroes)
            self._used_pets.update(task._used_pets)

            if res.success and res.data.get("sent", 0) > 0:
                sent_total += 1
            elif res.data.get("stop_reason") in ("NO_ARMY", "8009"):
                # الجيش نفد — نُبلغ المحرك بـ TERMINATE
                return TaskResult.fail("نفاد الجيش أثناء جمع الهيبة", action=CoordinatorAction.TERMINATE, stop_reason="NO_ARMY")
            elif res.data.get("stop_reason") in ("QUEUE_FULL", "8004"):
                return TaskResult.fail("الفيالق ممتلئة", action=CoordinatorAction.WAIT_AND_RETRY_SAME, stop_reason="QUEUE_FULL")

            await asyncio.sleep(round(random.uniform(4.0, 7.0), 2))

        return TaskResult.ok(f"تم إرسال {sent_total} مسيرة هيبة", action=CoordinatorAction.NEXT_PRIORITY, sent=sent_total)

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 4: نقل الموارد (Transport)
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_transport(self) -> TaskResult:
        cfg = self.config.get("transport", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("transport معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        tx, ty = cfg.get("target_x"), cfg.get("target_y")
        if tx is None or ty is None or (int(tx) == 0 and int(ty) == 0):
            return TaskResult.ok("إحداثيات النقل غير محددة", action=CoordinatorAction.SKIP_PRIORITY)

        account_id = getattr(self.conn, "email", "") or str(self.uid)
        if is_transport_daily_limit_reached(account_id, int(tx), int(ty)):
            return TaskResult.ok("تم بلوغ الحد اليومي للنقل", action=CoordinatorAction.SKIP_PRIORITY)

        self.log.info(f"🚚 [النقل] بدء النقل إلى ({tx}, {ty})")
        task = TransportTask(self.conn, dict(cfg))
        self._forward_logs(task)
        result = await task.run()

        if result.data.get("daily_limit_reached"):
            set_transport_daily_limit_reached(account_id, int(tx), int(ty))
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 5: استكشاف الأطلال (Ruins)
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_ruins(self) -> TaskResult:
        cfg = self.config.get("ruins", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("ruins معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        self.log.info("🏛️ [الأطلال] بدء استكشاف الأطلال")
        ruins_cfg = dict(cfg)
        ruins_cfg["max_marches"] = 1
        ruins_cfg["busy_heroes"] = list(self._busy_heroes)
        task = RuinsTask(self.conn, ruins_cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(getattr(task, "_busy", set()))
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 6: القتال الشامل (Combat)
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_combat(self) -> TaskResult:
        cfg = self.config.get("combat", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("combat معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        choice = str(cfg.get("choice", "invaders")).strip().lower()
        if choice == "elf":
            self.log.info("ℹ️ [القتال] مهمة العفريت (elf) غير متاحة — الانتقال للتالي.")
            return TaskResult.ok("elf غير متاح", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="elf_removed")

        self.log.info(f"⚔️ [القتال] بدء الهجوم على ({choice})")
        combat_cfg = {
            "monster_type":   choice,
            "max_marches":    15,
            "min_lv":         1,
            "max_lv":         int(cfg.get("level", 35)),
            "formation_id":   int(cfg.get("formation_id", 1)),
            "search_range":   120,
            "wait_for_queue": False,
            "troops_count":   int(cfg.get("troops_count", 0)),
            "busy_heroes":    list(self._busy_heroes),
        }
        task = MonsterTask(self.conn, combat_cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(getattr(task, "_busy", set()) or getattr(task, "_busy_heroes", set()))
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 7: المعاقل العامة (Stronghold)
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_stronghold(self) -> TaskResult:
        cfg = self.config.get("stronghold", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("stronghold معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        needed = int(cfg.get("count", 2))
        self.log.info(f"🏰 [المعاقل] بدء الهجوم (مطلوب: {needed})")
        stronghold_cfg = {
            "max_marches":    needed,
            "min_lv":         1,
            "max_lv":         int(cfg.get("level", 30)),
            "formation_id":   int(cfg.get("formation_id", 1)),
            "search_range":   int(cfg.get("search_range", 100)),
            "wait_for_queue": False,
            "troops_count":   int(cfg.get("troops_count", 50000)),
            "busy_heroes":    list(self._busy_heroes),
        }
        task = StrongholdTask(self.conn, stronghold_cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(getattr(task, "_busy", set()))
        await self._refresh_merit_data(force=True)
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 8: جمع الذهب (Gold Gather)
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_gold_gather(self) -> TaskResult:
        cfg = self.config.get("gold_gather", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("gold_gather معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        if not cfg.get("locations"):
            return TaskResult.ok("لا توجد مواقع ذهب", action=CoordinatorAction.SKIP_PRIORITY)

        self.log.info(f"💰 [جمع الذهب] بدء الجمع (تحالفات: {len(cfg['locations'])})")
        gold_cfg = dict(cfg)
        gold_cfg["busy_heroes"] = list(self._busy_heroes)
        task = GoldGatherTask(self.conn, gold_cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(getattr(task, "_busy", set()))
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  أولوية 9: الجمع الخارجي المفتوح (Gather)
    # ══════════════════════════════════════════════════════════════════════

    async def _priority_gather(self) -> TaskResult:
        cfg = self.config.get("gather", {})
        if not cfg.get("enabled", False):
            return TaskResult.ok("gather معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")

        res_type = cfg.get("res_type", 2)
        target_lv = int(cfg.get("level", 6))
        castle_lv = self._get_castle_level()
        res_names = {1: "الذهب", 2: "القمح", 3: "الخشب", 4: "الحديد", 5: "الكوارنز"}
        res_name = res_names.get(int(res_type), str(res_type))

        if int(res_type) == 4 and castle_lv < 10:
            return TaskResult.ok("جمع الحديد يتطلب قلعة لفل 10", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="CASTLE_LV_LOW")
        if int(res_type) == 5 and castle_lv < 15:
            return TaskResult.ok("جمع الفضة يتطلب قلعة لفل 15", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="CASTLE_LV_LOW")

        self.log.info(f"🌾 [جمع مفتوح] بدء جمع ({res_name}) لفل {target_lv}")

        # استغلال كل الفيالق المتاحة عبر حلقة حتى QUEUE_FULL أو NO_TARGET
        total_sent = 0
        gather_cfg = {
            "res_type":     res_type,
            "level":        target_lv,
            "max_marches":  int(cfg.get("max_marches", 10)),
            "search_range": int(cfg.get("search_range", 100)),
            "busy_heroes":  list(self._busy_heroes),
            "used_pets":    list(self._used_pets),
            "max_heroes":   2,
        }

        if cfg.get("use_boost", False):
            try:
                from tasks.gather_boost import GatherBoostTask
                boost = GatherBoostTask(self.conn, {"enabled": True})
                self._forward_logs(boost)
                await boost.run()
            except Exception as e:
                self.log.warning(f"⚠️ خطأ في مكافأة الجمع: {e}")

        task = GatherTask(self.conn, gather_cfg)
        self._forward_logs(task)
        result = await task.run()
        self._busy_heroes.update(task._busy_heroes)
        self._used_pets.update(task._used_pets)
        total_sent = result.data.get("sent", 0) if result.data else 0

        self.log.info(f"🏁 [جمع مفتوح] تم إرسال {total_sent} مسيرة لجمع {res_name}")
        return result


# ══════════════════════════════════════════════════════════════════════
#  التشغيل المباشر من سطر الأوامر (Standalone CLI Runner)
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import json
    import os
    import sys

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    _CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    _ROOT_DIR = os.path.dirname(_CURRENT_DIR)
    for p in [_CURRENT_DIR, _ROOT_DIR]:
        if p not in sys.path:
            sys.path.insert(0, p)

    parser = argparse.ArgumentParser(
        description="Empire March Coordinator — منسق الفيالق والمسيرات الموحد",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للقلعة المستهدفة")
    parser.add_argument("--duration", "-d", type=float, default=20.0, help="المدة القصوى بالدقائق [افتراضي: 20]")
    parser.add_argument("--priority", "-p", nargs="*", help="ترتيب أولويات مخصص (مثال: -p gather ruins)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    logging.getLogger("game_conn").setLevel(logging.WARNING)
    logging.getLogger("game_client").setLevel(logging.WARNING)

    from core.session_manager import SessionManager
    from game_client import GameConnection

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        target_email = args.email or next(iter(accounts.keys()))
        acc = accounts.get(target_email)
        if not acc:
            for em, a in accounts.items():
                if em.lower() == target_email.lower():
                    acc = a
                    target_email = em
                    break

        if not acc:
            print(f"❌ الحساب {target_email} غير موجود في الجلسات المسجلة!")
            return

        print("═" * 70)
        print(f"🎖️ تشغيل منسق الفيالق الموحد للحساب: {target_email}")
        print("═" * 70)

        # تحميل إعدادات الحساب من قاعدة البيانات
        coord_cfg: Dict[str, Any] = {
            "duration_minutes": args.duration,
        }
        try:
            from core.database import get_castle
            c_db = get_castle(target_email)
            if c_db and c_db.get("config"):
                raw_cfg = c_db["config"]
                if isinstance(raw_cfg, str):
                    raw_cfg = json.loads(raw_cfg)
                if isinstance(raw_cfg, dict):
                    mm_cfg = raw_cfg.get("march_manager", {})
                    if isinstance(mm_cfg, dict):
                        coord_cfg.update(mm_cfg)
                    coord_cfg["is_main_prestige_enabled"] = raw_cfg.get("prestige", {}).get("enabled", True)
                    for k in ("abra", "combat", "stronghold", "gather", "gold_gather", "transport", "ruins", "prestige_invaders", "prestige_stronghold", "prestige_gather"):
                        if k in raw_cfg and k not in coord_cfg:
                            coord_cfg[k] = raw_cfg[k]
        except Exception as e:
            print(f"⚠️ تعذر تحميل إعدادات قاعدة البيانات: {e} — استخدام الإعدادات الافتراضية.")

        coord_cfg["duration_minutes"] = args.duration
        if args.priority:
            coord_cfg["priority_order"] = args.priority
            coord_cfg["is_main_prestige_enabled"] = True
            for p in args.priority:
                sub = coord_cfg.setdefault(p, {})
                if isinstance(sub, dict):
                    sub["enabled"] = True

        conn = GameConnection(acc)
        print(f"🔌 جاري الاتصال بخادم اللعبة للحساب ({acc.email})...")
        if not await conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(15):
            await asyncio.sleep(0.3)
            if len(getattr(conn, "init_data", {})) > 0 and ("cityCtrl" in conn.init_data or "lordInfoCtrl" in conn.init_data):
                break

        print("✅ تم استلام بيانات القلعة بنجاح — بدء دورة التنسيق...")
        coordinator = MarchCoordinatorTask(conn, coord_cfg)
        result = await coordinator.run()

        print("\n" + "═" * 70)
        print(f"📊 النتيجة النهائية: {result.message}")
        if result.data:
            print(f"📋 البيانات: {result.data}")
        print("═" * 70)

        await conn.close()

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف المنسق بواسطة المستخدم.")


