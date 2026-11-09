# -*- coding: utf-8 -*-
"""
tasks/march_manager.py — منسق الفيالق والمسيرات الخارجي الموحد (March Orchestrator)
════════════════════════════════════════════════════════════════════════════════════════
يدير مسيرات خريطة المملكة وفق تسلسل أولويات ذكي مع تطبيق نظام الحالات الخمس الصارم:

  1. الحالة 1 (نفاذ الفيالق المتاحة):
     البقاء في نفس الأولوية والانتظار دقيقتين (120 ثانية) ثم إعادة الفحص،
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
from tasks.stronghold import StrongholdTask
from tasks.gather import GatherTask
from tasks.transport import TransportTask, is_transport_daily_limit_reached, set_transport_daily_limit_reached
from tasks.ruins import RuinsTask
from tasks.monster import MonsterTask
from tasks.gold_gather import GoldGatherTask
from tasks.abra import AbraTask

# ── معرفات مهام الهيبة من السيرفر (meritoriousTaskCtrl) ───────────────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "invaders": 4112004,      # الهجوم على الغزاة في الخريطة (5 هجمات)
    "stronghold": 4112030,    # احتلال المعقل / الملجأ (مرتان)
    "gather_food": 4112000,   # جمع القمح من الخريطة (مرة واحدة)
    "gather_wood": 4112001,   # جمع الخشب من الخريطة (مرة واحدة)
    "gather_iron": 4112002,   # جمع الحجر / الحديد من الخريطة (مرة واحدة)
    "gather_silver": 4112003, # جمع الكوارتز / الكوارنز من الخريطة (مرة واحدة)
}

# قائمة مهام جمع موارد الهيبة الأربعة
PRESTIGE_GATHER_RESOURCES = [
    {"key": "gather_food",   "res_type": 2, "name": "القمح (Food)",   "quest_id": 4112000},
    {"key": "gather_wood",   "res_type": 3, "name": "الخشب (Wood)",   "quest_id": 4112001},
    {"key": "gather_iron",   "res_type": 4, "name": "الحديد (Iron)",  "quest_id": 4112002},
    {"key": "gather_silver", "res_type": 5, "name": "الكوارنز (Silver)", "quest_id": 4112003},
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
        self.max_queues = int(self.config.get("max_queues", 6))
        self.duration_minutes = float(self.config.get("duration_minutes", 20.0))
        self.priority_order = self.config.get("priority_order") or self.DEFAULT_PRIORITY_ORDER

        self.start_time: float = 0.0
        self.max_duration_seconds: float = self.duration_minutes * 60.0
        self._busy_heroes: Set[int] = set()
        self._used_pets: Set[int] = set()
        self._max_castle_queues: int = 0
        self._last_queue_sync_time: float = 0.0
        self.log.propagate = False

    def get_castle_level(self) -> int:
        """جلب المستوى الحقيقي للقلعة لمنع طلب موارد تتطلب مستوى أعلى (مثل الحديد 10 والفضة 15)."""
        from tasks.march_capacity import get_castle_level
        return get_castle_level(getattr(self.conn, "init_data", {}))

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

    async def _refresh_merit_data(self, force: bool = False) -> bool:
        """تحديث بيانات مهام الهيبة من الذاكرة الحية فورياً مع كبح الاستعلامات المكررة."""
        now = time.time()
        last_sync = getattr(self, "_last_merit_sync_time", 0.0)

        # 1. إذا كانت البيانات موجودة في الذاكرة الحية ومحملة، نعتمدها فوراً (Zero-Request)
        if not force and "meritoriousTaskCtrl" in self.conn.init_data and (now - last_sync < 120.0):
            return True

        # 2. استعلام السيرفر فقط عند الحاجة القصوى
        try:
            self.log.debug("🛑🛑🛑🛑🛑🛑🛑 جاري استدعاء 1013/1 للهيبة")
            r = await self.conn.query("1013", "1", {}, timeout=5)
            if r and isinstance(r, dict) and "data" in r:
                merit_data = r["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    self._last_merit_sync_time = now
                    return True
        except Exception as e:
            self.log.debug(f"استعلام 1013/1 لتحديث مهام الهيبة لم يكتمل: {e}")

        try:
            r_all = await self.conn.query("1001", "1", {}, timeout=6)
            if r_all and isinstance(r_all, dict) and "data" in r_all:
                merit_data = r_all["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    self._last_merit_sync_time = now
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

    def _get_lord_stamina(self) -> int:
        """جلب رصيد طاقة اللورد الحالي من بيانات القلعة المحملة (lordInfoCtrl.base.health)."""
        try:
            if not hasattr(self.conn, 'init_data') or not self.conn.init_data:
                return 100
            init = self.conn.init_data
            base = (
                init.get('lordInfoCtrl', {}).get('base', {})
                or init.get('loginDataInitCtrl', {}).get('base', {})
            )
            val = base.get('health')
            if val is not None:
                return int(float(val))
            return 100
        except Exception:
            return 100

    def get_vip_level(self) -> int:
        """جلب مستوى المجد (VIP) من الذاكرة الحية (vipCtrl.vipLv)."""
        try:
            init = getattr(self.conn, 'init_data', {}) or {}
            return int(init.get('vipCtrl', {}).get('vipLv', 0))
        except Exception:
            return 0

    def get_merit_level(self) -> int:
        """جلب مستوى الهيبة / الجدارة من الذاكرة الحية (meritoriousTaskCtrl.meritLv)."""
        try:
            init = getattr(self.conn, 'init_data', {}) or {}
            return int(init.get('meritoriousTaskCtrl', {}).get('meritLv', 0))
        except Exception:
            return 0

    async def get_total_available_castle_army(self) -> int:
        """حساب إجمالي الجنود المتاحين بالقلعة من الذاكرة الحية (RAM) بصفر طلبات شبكية."""
        total = 0
        try:
            # 1. قراءة فورية من الذاكرة الحية (Zero-Request)
            total_army = self.conn.init_data.get('armyCtrl', {}).get('totalArmy', {}) if hasattr(self.conn, 'init_data') else {}
            if isinstance(total_army, dict) and total_army:
                for k, v in total_army.items():
                    if str(k).isdigit() and str(v).isdigit():
                        tid = int(k)
                        if not (800 <= tid < 900):  # استبعاد فخاخ الجدار
                            total += int(v)
                return total

            # 2. استعلام احتياطي فقط في حال كانت الذاكرة غير محملة
            self.log.debug("🛑🛑🛑🛑🛑🛑🛑")
            r_army = await self.conn.query("1005", "1", {}, timeout=5)
            self.log.debug("جاري استدعاء استعلام 1005/1 نجح")
            if r_army and "data" in r_army:
                t_data = r_army["data"].get("totalArmy", {})
                if isinstance(t_data, dict):
                    for k, v in t_data.items():
                        if str(k).isdigit() and str(v).isdigit():
                            tid = int(k)
                            if not (800 <= tid < 900):
                                total += int(v)
        except Exception as e:
            self.log.debug(f"خطأ أثناء حساب الجيش: {e}")

        return total

    async def _sync_queues_if_needed(self, max_stale_seconds: float = 45.0, force: bool = False) -> None:
        """مزامنة ذكية لطوابير الفيالق مع كبح القصف: تمنع سؤال السيرفر إذا كانت البيانات حديثة بالذاكرة إلا إذا فُرضت المزامنة."""
        now_t = time.time()
        last_t = getattr(self, "_last_queue_sync_time", 0.0)
        if not force and last_t > 0 and (now_t - last_t) < max_stale_seconds:
            return

        try:
            await self.conn.query('1007', '1000', {}, timeout=3)
            self._last_queue_sync_time = now_t
            await asyncio.sleep(round(random.uniform(0.8, 1.5), 2))
        except Exception:
            pass

    async def get_active_marches_count(self, force_sync: bool = False) -> int:
        """حساب عدد الفيالق والمسيرات النشطة حالياً خارج القلعة مع تحديث فوري وتجنب التكرار."""
        await self._sync_queues_if_needed(force=force_sync)

        seen_ids = set()
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
                if isinstance(q, dict) and q.get('status') in (0, 1, 2, 3, 4, 7):
                    qid = q.get('id') or q.get('queueId')
                    if qid:
                        if qid not in seen_ids:
                            seen_ids.add(qid)
                            active += 1
                    else:
                        active += 1
        return active

    async def wait_for_free_queue(
        self, 
        context_desc: str = "", 
        caused_by_queue_full: bool = True,
        wait_seconds: Optional[int] = None
    ) -> bool:
        """
        الانتظار الصرف عند امتلاء الفيالق دون أي فحص أو استعلام:
          - ينتظر المدة المحددة (أو عشوائياً 120-150 ثانية افتراضياً).
          - لا يتحقق إطلاقاً من عدد أو حالة الفيالق بالخارج.
          - يعود بـ True لاستئناف المحاولة فور انتهاء مدة الانتظار.
          - يعود بـ False فقط في حال انتهاء مهلة الـ 20 دقيقة الكلية للمهمة.
        """
        if self.is_time_expired():
            self.log.warning("⏱️ [انتهاء المهلة] انتهت مهلة الـ 20 دقيقة المخصصة لمهمة المسيرات.")
            return False

        sec = int(wait_seconds) if (wait_seconds is not None and wait_seconds > 0) else random.randint(120, 150)
        self.log.info(
            f"⏳ [انتظار الفيالق] جميع الفيالق مشغولة — الانتظار {sec} ثانية لإتاحة تفريغ فيلق {context_desc}..."
        )
        await asyncio.sleep(sec)

        if self.is_time_expired():
            self.log.warning("⏱️ [انتهاء المهلة] انتهت مهلة الـ 20 دقيقة المخصصة أثناء انتظار عودة الفيالق.")
            return False

        self.log.info(f"✅ [اكتمال الانتظار] انتهت مدة الانتظار ({sec} ثانية) {context_desc} — متابعة التنفيذ الآن.")
        return True

    async def get_active_gather_resource_types(self) -> Set[int]:
        """
        فحص الفيالق النشطة بالخارج وتحديد أنواع الموارد التي توجد لها مسيرات جمع قائمة حالياً
        (2=قمح, 3=خشب, 4=حديد, 5=فضة, 1=ذهب):
          - يطلب تحديثاً فورياً لطوابير المسيرات من السيرفر (CMD 1007/1000).
          - يفحص بيانات الهدف (to) ونقطة الانطلاق (from) وكود المورد (subMapType و resourceType).
          - يتيح تخطي إرسال مسيرة مكررة لنفس المورد إذا كانت هناك مسيرة تجمعه حالياً ولم تعد بعد.
        """
        active_res_types: Set[int] = set()
        await self._sync_queues_if_needed()

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
                # مسيرة نشطة (0=حشد بتجمع القلعة, 1=متجهة, 2=تجمع بالحقل, 3=عائدة, 4=مرابطة, 7=حشد منطلق)
                if q.get('status') not in (0, 1, 2, 3, 4, 7):
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

    async def ensure_army_or_wait(
        self, 
        context_desc: str = "", 
        is_retry: bool = False,
        min_needed: Optional[int] = None
    ) -> bool:
        """
        التحقق الذكي من توفر الجيش بالقلعة أو الانتظار لعودته من المسيرات:
          - عند الفحص المسبق (is_retry=False):
            إذا كانت قوات القلعة >= الحد الأدنى، يعيد True فوراً (جاهزية تامة).
          - عند إعادة المحاولة بعد فشل المهمة بنقص القوات (is_retry=True أو سياق "متابعة"):
            القوات الحالية بالقلعة أثبتت التجربة أنها غير كافية، فلا يُعاد True إلا بعد عودة قوات جديدة من الخارج!
          - إذا كانت هناك مسيرات نشطة بالخارج (active_marches > 0):
            تُطبق الحالة 1 بالانتظار دقيقتين (120 ثانية) لعودة الفيالق، وتتكرر حتى عودة قوات أو انتهاء مهلة الـ 20 دقيقة.
          - إذا كانت المسيرات بالخارج = 0 (جميع الفيالق داخل القلعة):
            تُطبق الحالة 3 (انعدام القوات كلياً) ويعيد False للخروج الفوري لتجنب التكرار العبثي.
        """
        if min_needed is None:
            min_needed = 50 if any(k in context_desc for k in ("جمع", "أطلال", "نقل")) else MIN_ATTACK_ARMY_COUNT

        # كشف تلقائي إذا كانت العملية إعادة محاولة بعد نقص القوات
        if "متابعة" in context_desc:
            is_retry = True

        initial_troops = await self.get_total_available_castle_army()

        # في الفحص المسبق فقط: إذا كانت القوات متوفرة بالقلعة نسمح بالبدء
        if not is_retry and initial_troops >= min_needed:
            return True

        wait_cycle = 0
        while not self.is_time_expired():
            active_marches = await self.get_active_marches_count()
            if active_marches == 0:
                # إعادة التحقق بعد مهلة عشوائية لتفادي أي تأخير لحظي في تحديث السيرفر
                await asyncio.sleep(round(random.uniform(1.8, 2.8), 2))
                active_marches = await self.get_active_marches_count()

            if active_marches > 0:
                wait_cycle += 1
                wait_sec = random.randint(115, 128)
                self.log.info(
                    f"⏳ [الحالة 1: نقص القوات / مسيرات بالخارج ({active_marches} مسيرة نشطة)] "
                    f"القوات بالقلعة غير كافية حالياً ({initial_troops}) — "
                    f"انتظار قرابة دقيقتين ({wait_sec} ثانية) لعودة الجيش {context_desc} [دورة {wait_cycle}]..."
                )
                await asyncio.sleep(wait_sec)
                await self._refresh_merit_data()

                if self.is_time_expired():
                    break

                # فحص هل عاد جيش بعد انتهاء الدقيقتين انتظار
                current_troops = await self.get_total_available_castle_army()
                current_active = await self.get_active_marches_count()

                troops_arrived = (current_troops > initial_troops) or (current_active < active_marches)
                ready = (current_troops >= min_needed) if not is_retry else troops_arrived

                if ready:
                    self.log.info(
                        f"✅ [توفر قوات جديدة] عاد جيش إلى القلعة (القوات: {initial_troops} ➔ {current_troops}) "
                        f"— استئناف المحاولة {context_desc} الآن!"
                    )
                    return True
                else:
                    self.log.info(
                        f"⏳ [الجيش لا يزال بالخارج] لم تعد أي قوات كافية بعد خلال الدقيقتين الماضيتين "
                        f"(مسيرات نشطة: {current_active} | قوات بالقلعة: {current_troops}) — مواصلة دورة انتظار دقيقتين أخرى..."
                    )
            else:
                self.log.warning(
                    f"🛑 [الحالة 3: انعدام القوات كلياً] تم التأكد: لا توجد أي مسيرات بالخارج (0 مسيرة نشطة) "
                    f"والقوات المتوفرة بالقلعة ({initial_troops}) غير كافية لتسيير المهمة {context_desc} — "
                    f"الخروج فوراً لتجنب التكرار العبثي."
                )
                return False

        self.log.warning("⏱️ [انتهاء المهلة] انتهت الـ 20 دقيقة المحددة للمهمة أثناء انتظار عودة الجيش.")
        return False

    async def is_ruins_march_active(self) -> bool:
        """
        يفحص بشكل فوري ما إذا كانت هناك مسيرة استكشاف أطلال نشطة بالخارج حالياً.
        يعتمد على نوع المسار (moveLineType = 4) أو نوع خريطة الهدف (mapType = 7).
        """

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
            q_list = item.get('data', []) if (isinstance(item, dict) and 'data' in item) else ([item] if isinstance(item, dict) else (item if isinstance(item, list) else []))
            for q in q_list:
                if not isinstance(q, dict):
                    continue
                # حالة المسيرة نشطة (تشمل حشود 0 و 7)
                if q.get('status') in (0, 1, 2, 3, 4, 7):
                    # استكشاف الأطلال يحمل moveLineType = 4
                    if q.get('moveLineType') == 4:
                        return True
                    # أو إذا كان الهدف من نوع mapType = 7
                    to_info = q.get('to', {})
                    if isinstance(to_info, dict) and to_info.get('mapType') == 7:
                        return True
        return False
        
    # ────────────────────────────────────────────────────────────────
    #  ربط سجلات المهام الفرعية بسجل المهمة الحالي
    # ────────────────────────────────────────────────────────────────

    def _forward_subtask_logs(self, subtask: BaseTask):
        """توجيه سجلات المهمة الفرعية (monster أو stronghold أو gather) إلى سجل منسق الفيالق والسماح بالطباعة."""
        if hasattr(subtask, "log") and subtask.log and hasattr(self, "log") and self.log:
            subtask.log.handlers = list(self.log.handlers)
            subtask.log.setLevel(self.log.level)
            subtask.log.propagate = False

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 0: وحش الذهب (Abra Boss Attack) عبر abra.py
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_abra(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية الهجوم على وحش الذهب Abra كأولوية أولى مطلقة خارج القلعة:
          1. فحص تفعيل المهمة في الإعدادات.
          2. فحص يوم الحدث (الإثنين والأربعاء) أو تجاوز الفحص عبر force.
          3. فحص طاقة اللورد (الحالة 6: stamina_empty).
          4. استدعاء AbraTask بنظام التدفق السريع وعقود الحالات الست.
          5. تحديث الأبطال المشغولين والانتقال السلس لباقي الأولويات.
        """
        # قراءة الإعدادات من march_manager.abra أو الإعداد العام abra
        abra_cfg = self.config.get("abra")
        if abra_cfg is None:
            abra_cfg = getattr(self.conn, "castle_config", {}).get("abra", {}) if hasattr(self.conn, "castle_config") else {}

        if isinstance(abra_cfg, bool):
            abra_cfg = {"enabled": abra_cfg}
        elif not isinstance(abra_cfg, dict):
            abra_cfg = {}

        if not bool(abra_cfg.get("enabled", False)):
            return {"status": "skipped", "reason": "disabled"}

        # فحص اليوم والحدث (إثنين وأربعاء) بنظام UTC
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        is_event_day = bool(abra_cfg.get("force", False)) or (now_utc.weekday() in (0, 2))
        if not is_event_day:
            return {"status": "skipped", "reason": "not_event_day"}

        target_x = int(abra_cfg.get("x", 0) or 0)
        target_y = int(abra_cfg.get("y", 0) or 0)
        if target_x <= 0 or target_y <= 0:
            self.log.warning(f"⚠️ [أولوية 0: Abra] إحداثيات الوحش غير محددة ({target_x}, {target_y}) — تخطي.")
            return {"status": "skipped", "reason": "invalid_coords"}

        # فحص مسبق لطاقة اللورد (الحالة 6)
        lord_stamina = self._get_lord_stamina()
        if lord_stamina < 10:
            self.log.warning(f"🛑 [أولوية 0: Abra] طاقة اللورد ({lord_stamina}) غير كافية للهجوم.")
            return {"status": "stamina_empty", "stamina": lord_stamina}

        # فحص مسبق لتوفر القوات بالقلعة (الحالة 3)
        has_army = await self.ensure_army_or_wait("لهجوم وحش الذهب Abra")
        if not has_army:
            return {"status": "critical_no_army"}

        # دمج تشكيلة القتال المشتركة إن لم تكن محددة
        task_cfg = dict(abra_cfg)
        shared_form = self.config.get("combat", {}).get("formation_id", 1)
        if "formation_id" not in task_cfg and "formation" not in task_cfg:
            task_cfg["formation_id"] = shared_form

        task_cfg["busy_heroes"] = list(self._busy_heroes)

        self.log.info(f"🐉 [وحش الذهب] بدء الهجوم على Abra عند ({target_x}, {target_y})")
        abra_task = AbraTask(self.conn, task_cfg)
        self._forward_subtask_logs(abra_task)

        task_res = await abra_task.run()
        self._busy_heroes.update(getattr(abra_task, '_busy_heroes', set()))

        task_data = getattr(task_res, "data", {}) if (task_res is not None and isinstance(getattr(task_res, "data", None), dict)) else {}
        ret_status = task_data.get("status") or ("completed" if task_res.success else "error")

        if ret_status == "critical_no_army":
            return {"status": "critical_no_army"}
        if ret_status == "stamina_empty":
            return {"status": "stamina_empty", "stamina": task_data.get("stamina", lord_stamina)}

        return {
            "status": ret_status,
            "success": task_res.success,
            "message": task_res.message,
            "data": task_data
        }

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

        # 1. التحقق من تفعيل قسم الهيبة الرئيسي
        if not self.config.get("is_main_prestige_enabled", True):
            return {"status": "skipped", "reason": "main_prestige_disabled"}

        cfg = self.config.get("prestige_invaders", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        # استعلام أحدث بيانات الهيبة
        await self._refresh_merit_data()

        merit_lv = self.get_merit_level()
        if merit_lv < 1:
            self.log.info(f"👾 [غزاة الهيبة] تم التخطي: نظام الهيبة غير مفتوح للقلعة بعد (meritLv = {merit_lv}).")
            return {"status": "skipped", "reason": "merit_level_too_low", "merit_level": merit_lv}

        q_info = self.get_quest_info("invaders")

        if q_info.get("is_done"):
            return {"status": "already_done", "c_num": q_info["c_num"]}

        # حساب عدد الهجمات المتبقية لإنجاز المهمة بدقة
        needed = int(cfg.get("count", 5))
        if q_info.get("found") and q_info.get("remaining", 0) > 0:
            needed = q_info["remaining"]

        self.log.info(f"👾 [غزاة الهيبة] بدء الهجوم (متبقي: {needed} هجمة)")

        # فحص مسبق لطاقة اللورد (Stamina) لتجنب أخطاء 8032 والمحاولات غير المجدية
        lord_stamina = self._get_lord_stamina()
        if lord_stamina < 10:
            self.log.warning(f"🛑 [أولوية 1: غزاة الهيبة] طاقة اللورد الحالية ({lord_stamina}) غير كافية لمسيرات الهجوم (مطلوب 10 على الأقل) — الانتقال للأولوية التالية.")
            return {"status": "stamina_empty", "stamina": lord_stamina}

        # فحص مسبق ذكي للجيش بالقلعة (التمييز بين مسيرات بالخارج وبين انعدام كلي)
        has_army = await self.ensure_army_or_wait("لهجوم غزاة الهيبة")
        if not has_army:
            return {"status": "critical_no_army"}

        # حساب دورات الانتظار المتاحة لطوابير الفيالق ضمن مهلة الـ 20 دقيقة (الحالة 1: انتظار دقيقتين = 120 ثانية)
        rem_seconds = self.get_remaining_seconds()
        max_wait_cycles = max(1, int(rem_seconds // 120))

        # تجهيز إعدادات MonsterTask للهجوم على الغزاة
        monster_cfg = {
            "monster_type": "invaders",
            "max_marches": needed,
            "min_lv": int(cfg.get("min_lv", 1)),
            "max_lv": int(cfg.get("max_lv", 30)),
            "formation_id": int(cfg.get("formation_id", 1)),
            "search_range": int(cfg.get("search_range", 80)),
            "wait_for_queue": True,          # الحالة 1: الانتظار عند امتلاء الفيالق
            "wait_interval": 165.0,          # انتظار قرابة دقيقتين ونصف إلى 3 دقائق (165 ثانية)
            "max_wait_cycles": max_wait_cycles,
            "troops_count": int(cfg.get("troops_count", 0)),
            "busy_heroes": list(self._busy_heroes),
        }

        monster_task = MonsterTask(self.conn, monster_cfg)
        self._forward_subtask_logs(monster_task)

        task_res = await monster_task.run()
        self._busy_heroes.update(getattr(monster_task, '_busy', set()))

        task_res_data = getattr(task_res, "data", {}) if (task_res is not None and isinstance(getattr(task_res, "data", None), dict)) else {}

        # فحص نفاد الطاقة أثناء الهجمات (كود 8032)
        if task_res_data.get("stop_reason") == "STAMINA_EMPTY":
            self.log.warning("🛑 [أولوية 1: غزاة الهيبة] توقف الهجوم بسبب نفاد طاقة اللورد — الانتقال للأولوية التالية.")

        # فحص الحالة 3 بعد المحاولة: هل نفد الجيش كلياً؟
        if task_res_data.get("stop_reason") == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم الغزاة", is_retry=True)
            if not has_army:
                return {"status": "critical_no_army"}

        sent_cnt = task_res_data.get("sent", 0)

        # تحديث بيانات الهيبة لفحص النتيجة
        await self._refresh_merit_data()
        updated_q = self.get_quest_info("invaders")
        if updated_q.get("is_done"):
            self.log.info(f"🎉 [أولوية 1: غزاة الهيبة] تم إكمال مهمة الهيبة بنجاح ({updated_q['c_num']}/{updated_q['l_num']})!")
        elif sent_cnt > 0:
            self.log.info(
                f"ℹ️ [أولوية 1: غزاة الهيبة] تم إرسال {sent_cnt} مسيرة هجوم بنجاح وهي في طريقها للأهداف حالياً "
                f"(التقدم المسجل حالياً: {updated_q['c_num']}/{updated_q['l_num']} — سيتم احتساب القتلى باللعبة فور وصول المسيرات للأهداف)."
            )
        else:
            self.log.info(f"ℹ️ [أولوية 1: غزاة الهيبة] تقدم المهمة الحالي: ({updated_q['c_num']}/{updated_q['l_num']}).")

        return {
            "status": "completed" if updated_q.get("is_done") else "partial",
            "sent": sent_cnt,
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

        # 1. التحقق من تفعيل قسم الهيبة الرئيسي
        if not self.config.get("is_main_prestige_enabled", True):
            return {"status": "skipped", "reason": "main_prestige_disabled"}

        cfg = self.config.get("prestige_stronghold", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        # استعلام أحدث بيانات الهيبة
        await self._refresh_merit_data()

        merit_lv = self.get_merit_level()
        if merit_lv < 5:
            self.log.info(f"🏰 [معقل الهيبة] تم التخطي: مستوى الهيبة الحالي ({merit_lv}) أقل من 5 المطلوب.")
            return {"status": "skipped", "reason": "merit_level_too_low", "merit_level": merit_lv}
        q_info = self.get_quest_info("stronghold")

        if q_info.get("is_done"):
            return {"status": "already_done", "c_num": q_info["c_num"]}

        # مهمة المعقل باللعبة تتطلب مرتين كحد أقصى (وليس 5)
        needed = 2
        if q_info.get("found") and q_info.get("remaining", 0) > 0:
            needed = min(2, q_info["remaining"])

        self.log.info(f"🏰 [معقل الهيبة] بدء الهجوم (متبقي: {needed} هجمة)")

        # فحص مسبق لطاقة اللورد (Stamina)
        lord_stamina = self._get_lord_stamina()
        if lord_stamina < 10:
            self.log.warning(f"🛑 [أولوية 2: معقل الهيبة] طاقة اللورد الحالية ({lord_stamina}) غير كافية لمسيرات المعقل (مطلوب 10 على الأقل) — الانتقال للأولوية التالية.")
            return {"status": "stamina_empty", "stamina": lord_stamina}

        # فحص مسبق ذكي للجيش بالقلعة (التمييز بين مسيرات بالخارج وبين انعدام كلي)
        has_army = await self.ensure_army_or_wait("لهجوم معقل الهيبة")
        if not has_army:
            return {"status": "critical_no_army"}

        rem_seconds = self.get_remaining_seconds()
        max_wait_cycles = max(1, int(rem_seconds // 120))

        # تجهيز إعدادات StrongholdTask للهجوم على المعقل
        stronghold_cfg = {
            "max_marches": needed,
            "min_lv": int(cfg.get("min_lv", 1)),
            "max_lv": int(cfg.get("max_lv", 35)),
            "formation_id": int(cfg.get("formation_id", 1)),
            "search_range": int(cfg.get("search_range", 80)),
            "wait_for_queue": True,          # الحالة 1: الانتظار عند امتلاء الفيالق
            "wait_interval": 165.0,          # انتظار قرابة دقيقتين ونصف إلى 3 دقائق (165 ثانية)
            "max_wait_cycles": max_wait_cycles,
            "troops_count": int(cfg.get("troops_count", 30000)),
            "busy_heroes": list(self._busy_heroes),
        }

        stronghold_task = StrongholdTask(self.conn, stronghold_cfg)
        self._forward_subtask_logs(stronghold_task)

        task_res = await stronghold_task.run()
        self._busy_heroes.update(getattr(stronghold_task, '_busy', set()))

        task_res_data = getattr(task_res, "data", {}) if (task_res is not None and isinstance(getattr(task_res, "data", None), dict)) else {}

        # فحص نفاد الطاقة أثناء الهجمات (كود 8032)
        if task_res_data.get("stop_reason") == "STAMINA_EMPTY":
            self.log.warning("🛑 [أولوية 2: معقل الهيبة] توقف الهجوم بسبب نفاد طاقة اللورد — الانتقال للأولوية التالية.")

        # فحص الحالة 3 بعد المحاولة: هل نفد الجيش كلياً؟
        if task_res_data.get("stop_reason") == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم المعقل", is_retry=True)
            if not has_army:
                return {"status": "critical_no_army"}

        sent_cnt = task_res_data.get("sent", 0)

        # تحديث بيانات الهيبة لفحص النتيجة
        await self._refresh_merit_data()
        updated_q = self.get_quest_info("stronghold")
        if updated_q.get("is_done"):
            self.log.info(f"🎉 [أولوية 2: معقل الهيبة] تم إكمال مهمة المعقل بنجاح ({updated_q['c_num']}/{updated_q['l_num']})!")
        elif sent_cnt > 0:
            self.log.info(
                f"ℹ️ [أولوية 2: معقل الهيبة] تم إرسال {sent_cnt} مسيرة معقل بنجاح وهي في طريقها للأهداف حالياً "
                f"(التقدم المسجل حالياً: {updated_q['c_num']}/{updated_q['l_num']} — سيتم تحديث التقدم باللعبة فور وصول المسيرات للأهداف)."
            )
        else:
            self.log.info(f"ℹ️ [أولوية 2: معقل الهيبة] تقدم مهمة المعقل الحالي: ({updated_q['c_num']}/{updated_q['l_num']}).")

        return {
            "status": "completed" if updated_q.get("is_done") else "partial",
            "sent": sent_cnt,
            "quest_info": updated_q,
        }

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 3: جمع موارد الهيبة (Prestige Gather) عبر gather.py
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_prestige_gather(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية جمع موارد الهيبة اليومية (القمح، الخشب، الحديد، الكوارنز) عبر gather.py:
          1. استعلام حالة مهام جمع الموارد الأربعة من meritoriousTaskCtrl.
          2. تخطي الموارد المنجزة مسبقاً.
          3. إرسال مسيرة جمع عادية واحدة بحمولة الحقل كاملة لكل مورد غير مكتمل.
          4. تطبيق الحالات الخمس (نفاذ الفيالق 120ث، نقص التشكيلة، انعدام الجيش، تعذر الأهداف).
        """

        # 1. التحقق من تفعيل قسم الهيبة الرئيسي
        if not self.config.get("is_main_prestige_enabled", True):
            return {"status": "skipped", "reason": "main_prestige_disabled"}

        cfg = self.config.get("prestige_gather", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        # استعلام أحدث بيانات الهيبة
        await self._refresh_merit_data()

        merit_lv = self.get_merit_level()
        if merit_lv < 6:
            self.log.info(f"🌾 [جمع موارد الهيبة] تم التخطي: مستوى الهيبة الحالي ({merit_lv}) أقل من 5 المطلوب.")
            return {"status": "skipped", "reason": "merit_level_too_low", "merit_level": merit_lv}

        # فحص الفيالق النشطة بالخارج للتأكد من عدم وجود مسيرة جمع قائمة لأي مورد
        active_gather_types = await self.get_active_gather_resource_types()

        uncompleted = []
        for item in PRESTIGE_GATHER_RESOURCES:
            q_info = self.get_quest_info(item["quest_id"])
            if q_info.get("is_done"):
                pass
            elif item["res_type"] in active_gather_types:
                pass
            else:
                uncompleted.append((item, q_info))

        if not uncompleted:
            return {"status": "already_done", "remaining": 0}

        self.log.info(f"🌾 [جمع موارد الهيبة] بدء الجمع (متبقي: {len(uncompleted)} مهام)")

        sent_total = 0
        results_by_res = {}

        castle_lv = self.get_castle_level()

        for item, q_info in uncompleted:
            if self.is_time_expired():
                self.log.warning("⏱️ [انتهاء المهلة] انتهت مدة الـ 20 دقيقة المخصصة للمهمة بالكامل.")
                break

            # فحص شرط مستوى القلعة لموارد الحديد (10) والفضة (15) لتفادي الأخطاء 8041 و 8042
            if item["res_type"] == 4 and castle_lv < 10:
                self.log.info(
                    f"🌾 [أولوية 3] تخطي جمع {item['name']} — يتطلب قلعة لفل 10 على الأقل (لفل القلعة الحالي: {castle_lv}) [لتفادي خطأ 8041]."
                )
                continue
            elif item["res_type"] == 5 and castle_lv < 15:
                self.log.info(
                    f"🌾 [أولوية 3] تخطي جمع {item['name']} — يتطلب قلعة لفل 15 على الأقل (لفل القلعة الحالي: {castle_lv}) [لتفادي خطأ 8042]."
                )
                continue

            self.log.info(f"🌾 ───【 جمع مورد الهيبة: {item['name']} (مهمة #{item['quest_id']}) 】───")

            # فحص مسبق ذكي للجيش بالقلعة (التمييز بين مسيرات بالخارج وبين انعدام كلي)
            has_army = await self.ensure_army_or_wait(f"لجمع {item['name']}")
            if not has_army:
                return {"status": "critical_no_army"}

            # محاولة إرسال مسيرة جمع عادية واحدة بحمولة الحقل كاملة مع معالجة الحالات
            consecutive_errs = 0
            while not self.is_time_expired():
                # فحص مسبق: إذا كان سقف الفيالق معروفاً وكل الفيالق مشغولة بالخارج حالياً، ننتظر تفريغ فيلق أولاً
                if getattr(self, '_max_castle_queues', 0) > 0:
                    cur_act = await self.get_active_marches_count()
                    if cur_act >= self._max_castle_queues:
                        has_free_queue = await self.wait_for_free_queue(f"لجمع {item['name']}", caused_by_queue_full=False)
                        if not has_free_queue:
                            return {"status": "timeout_or_no_queue"}

                gather_cfg = {
                    "res_type": item["res_type"],
                    "max_marches": 1,
                    "level": int(cfg.get("level", 6)),
                    "search_range": int(cfg.get("search_range", 100)),
                    "busy_heroes": list(self._busy_heroes),
                    "used_pets": list(self._used_pets),
                    "allow_partial": True,  # السماح بمسيرة جزئية لمهام الهيبة لإكمال المهمة اليومية (25k) للحسابات الصغيرة
                    "min_load_ratio": 0.0,
                    "max_heroes": 2,
                }

                gather_task = GatherTask(self.conn, gather_cfg)
                self._forward_subtask_logs(gather_task)
                res = await gather_task.run()

                # تراكم وتحديث الأبطال والحيوانات المشغولة عبر جميع الموارد
                self._busy_heroes.update(gather_task._busy_heroes)
                self._used_pets.update(gather_task._used_pets)

                res_data = getattr(res, "data", {}) if (res is not None and isinstance(getattr(res, "data", None), dict)) else {}

                if res is not None and res.success and res_data.get("sent", 0) > 0:
                    sent_total += 1
                    results_by_res[item["key"]] = "sent"
                    active_gather_types.add(item["res_type"])
                    self.log.info(f"✅ تم إرسال مسيرة جمع عادية لـ {item['name']} بنجاح لإنجاز مهمة الهيبة!")
                    break

                # فحص توقف المهمة لعدم كفاية مستوى القلعة (8041 أو 8042)
                if res_data.get("stop_reason") == "CASTLE_LV_LOW":
                    self.log.info(f"🌾 [أولوية 3] تجاوز جمع {item['name']} لعدم كفاية لفل القلعة.")
                    results_by_res[item["key"]] = "skipped_castle_lv"
                    break

                # الحالة 1: الفيالق ممتلئة بالكامل بالخارج (كود 8004)
                if res_data.get("queue_full"):
                    has_free_queue = await self.wait_for_free_queue(f"لجمع {item['name']}", caused_by_queue_full=True)
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue"}
                    continue

                # فحص الحالة 3: انعدام الجيش بالقلعة
                if res_data.get("stop_reason") == "NO_ARMY":
                    has_army = await self.ensure_army_or_wait(f"لمتابعة جمع {item['name']}", is_retry=True)
                    if not has_army:
                        return {"status": "critical_no_army"}
                    continue

                # أخطاء أخرى مثل تعذر إيجاد هدف في النطاق (الحالة 4: تجاوز بعد 3 محاولات)
                consecutive_errs += 1
                if consecutive_errs >= 3:
                    self.log.warning(f"⚠️ [الحالة 4] تكرر تعذر إرسال مسيرة جمع {item['name']} (3 محاولات) — الانتقال للمورد التالي.")
                    results_by_res[item["key"]] = "failed_max_retries"
                    break
                await asyncio.sleep(round(random.uniform(2.5, 4.2), 2))

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
    #  الأولوية 4: مساعدة الموارد (Resource Transport / Aid)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_transport(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية مساعدة ونقل الموارد بالاعتماد المباشر على وحدة transport.py:
          - يتم تفويض منطق بناء الحزمة وتقسيم الحمولة لملف النقل المتخصص.
          - يقتصر دور المنسق على مراقبة الفيالق (الحالة 1) وإدارة مهلة الـ 20 دقيقة.
        """
        cfg = self.config.get("transport", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        target_x = cfg.get("target_x")
        target_y = cfg.get("target_y")
        if target_x is None or target_y is None or (int(target_x) == 0 and int(target_y) == 0):
            self.log.warning("⚠️ [أولوية 4] لم يتم تحديد إحداثيات القلعة الهدف...")
            return {"status": "skipped", "reason": "no_target_coords"}

        account_id = getattr(self.conn, 'email', '') or str(self.uid)
        if is_transport_daily_limit_reached(account_id, int(target_x), int(target_y)):
            return {"status": "skipped", "reason": "daily_limit_reached"}

        self.log.info(f"🚚 [نقل الموارد] بدء النقل إلى ({target_x}, {target_y})")

        sent_total = 0
        total_transported = 0
        target_max_marches = int(cfg.get("max_marches", 18))

        while not self.is_time_expired():
            # فحص هل تم إرسال كامل المسيرات المطلوبة
            remaining_needed = target_max_marches - sent_total
            if remaining_needed <= 0:
                break

            # فحص مسبق لامتلاء الفيالق (الحالة 1 الخاصة بالمنسق)
            if getattr(self, '_max_castle_queues', 0) > 0:
                cur_act = await self.get_active_marches_count()
                if cur_act >= self._max_castle_queues:
                    has_free_queue = await self.wait_for_free_queue("لنقل الموارد", caused_by_queue_full=False)
                    if not has_free_queue:
                        break
                free_queues = max(1, self._max_castle_queues - cur_act)
            else:
                free_queues = remaining_needed

            # تمرير الفيالق الشاغرة دفعة واحدة للمهمة لتفحص مرة واحدة فقط
            batch_size = min(free_queues, remaining_needed)
            transport_cfg = dict(cfg)
            transport_cfg["max_marches"] = batch_size

            # تشغيل المهمة الفرعية من ملف transport.py
            transport_task = TransportTask(self.conn, transport_cfg)
            self._forward_subtask_logs(transport_task)
            
            res = await transport_task.run()

            # معالجة الرد القادم من ملف النقل
            res_data = getattr(res, "data", {}) if (res is not None and isinstance(getattr(res, "data", None), dict)) else {}
            sent_count = res_data.get("sent", 0)
            reason = res_data.get("reason")
            daily_limit = res_data.get("daily_limit_reached", False)

            if daily_limit:
                sent_total += sent_count
                total_transported += res_data.get("total", 0)
                set_transport_daily_limit_reached(account_id, int(target_x), int(target_y))
                self.log.info("🛑 [أولوية 4] تم تسجيل بلوغ القلعة الهدف للحد الأقصى اليومي — سيتم تخطي مهمة النقل لبقية اليوم والانتقال للأولويات التالية.")
                break

            if res is not None and sent_count > 0:
                sent_total += sent_count
                total_transported += res_data.get("total", 0)

            if reason == "queue_full" or res_data.get("queue_full"):
                self.log.info("🛑 [أولوية 4: نفاذ الفيالق] الفيالق ممتلئة، المنسق سيتولى الانتظار...")
                has_free_queue = await self.wait_for_free_queue("لنقل الموارد", caused_by_queue_full=True)
                if not has_free_queue:
                    break
                continue
            elif not res or not res.success or sent_count == 0:
                # توقف البوت إما بسبب نفاد الموارد أو حدوث أخطاء متتالية
                break

        self.log.info(f"🏁 ───【 اكتمال أولوية مساعدة الموارد: تم إرسال {sent_total} فيلق | إجمالي الموارد المنقولة: {total_transported:,} 】───")
        return {
            "status": "completed",
            "sent": sent_total,
            "total_transported": total_transported,
        }
    
    # ────────────────────────────────────────────────────────────────
    #  الأولوية 5: استكشاف الأطلال (Ruins)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_ruins(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية استكشاف الأطلال بالاعتماد على وحدة ruins.py:
          - تفحص مسبقاً إذا كانت هناك مسيرة أطلال نشطة لتتجاوز المهمة فوراً.
          - ترسل مسيرة واحدة فقط حصراً ثم تنتقل للأولوية التالية.
        """
        cfg = self.config.get("ruins", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        self.log.info("🏛️ [الأطلال] بدء استكشاف الأطلال")

        # 1. فحص مسبق وحاسم: هل توجد مسيرة أطلال بالخارج بالفعل؟
        is_active = await self.is_ruins_march_active()
        if is_active:
            self.log.info("🏛️ [أولوية 5] توجد مسيرة استكشاف أطلال نشطة بالخارج بالفعل — سيتم التخطي والانتقال للأولوية التالية مباشرة.")
            return {"status": "already_active"}

        # 2. فحص توفر الجيش بالقلعة
        has_army = await self.ensure_army_or_wait("لاستكشاف الأطلال")
        if not has_army:
            return {"status": "critical_no_army"}

        while not self.is_time_expired():
            # فحص امتلاء الفيالق مسبقاً
            if getattr(self, '_max_castle_queues', 0) > 0:
                cur_act = await self.get_active_marches_count()
                if cur_act >= self._max_castle_queues:
                    has_free_queue = await self.wait_for_free_queue("لاستكشاف الأطلال", caused_by_queue_full=False)
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue"}

            ruins_cfg = dict(cfg)
            ruins_cfg["max_marches"] = 1  # إجبار البوت على إرسال مسيرة واحدة فقط
            ruins_cfg["busy_heroes"] = list(self._busy_heroes)
            
            ruins_task = RuinsTask(self.conn, ruins_cfg)
            self._forward_subtask_logs(ruins_task)
            res = await ruins_task.run()
            self._busy_heroes.update(getattr(ruins_task, '_busy', set()))

            # 3. معالجة النتيجة
            if res.success:
                if res.data and res.data.get("already_active"):
                    self.log.info("🏛️ [أولوية 5] توجد مسيرة استكشاف أطلال نشطة بالخارج بالفعل — سيتم التخطي والانتقال للأولوية التالية مباشرة.")
                    return {"status": "already_active"}
                self.log.info("✅ [أولوية 5] تم إرسال مسيرة استكشاف الأطلال بنجاح! سيتم الانتقال للأولوية التالية.")
                return {"status": "completed", "sent": 1}
            else:
                # إذا فشل الإرسال لأي سبب آخر (انعدام أهداف قريبة، أو امتلاء الفيالق دون علمنا)
                self.log.warning("⚠️ تعذر إرسال مسيرة الأطلال — سيتم التخطي والانتقال للأولوية التالية.")
                break

        return {"status": "failed"}
   

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 6: القتال الشامل (Combat - Elf / Invaders / Rebels)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_combat(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية القتال الشامل:
          - يقرأ خيار المستخدم (invaders, rebels).
          - يستدعي monster.py حسب الهدف المختار.
          - يستمر بالهجوم حتى نفاذ طاقة اللورد، ويتولى المنسق إدارة مهلة الفيالق.
        """
        cfg = self.config.get("combat", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        choice = str(cfg.get("choice", "elf")).strip().lower()
        self.log.info(f"⚔️ [القتال الشامل] بدء الهجوم على ({choice})")

        # 1. فحص مسبق لطاقة اللورد
        lord_stamina = self._get_lord_stamina()
        min_required_stamina = 10
        if lord_stamina < min_required_stamina:
            self.log.warning(f"🛑 [أولوية 6] طاقة اللورد الحالية ({lord_stamina}) غير كافية لقتال {choice} (المطلوب {min_required_stamina}) — الانتقال للأولوية التالية فوراً.")
            return {"status": "stamina_empty", "stamina": lord_stamina}

        # 2. فحص توفر الجيش بالقلعة
        has_army = await self.ensure_army_or_wait(f"لقتال {choice}")
        if not has_army:
            return {"status": "critical_no_army"}

        total_sent = 0
        consecutive_errors = 0

        # 3. حلقة الهجوم المستمر حتى نفاذ الطاقة أو اكتمال المهمة
        while not self.is_time_expired():
            # فحص امتلاء الفيالق مسبقاً (الحالة 1 للمنسق)
            if getattr(self, '_max_castle_queues', 0) > 0:
                cur_act = await self.get_active_marches_count()
                if cur_act >= self._max_castle_queues:
                    has_free_queue = await self.wait_for_free_queue(f"لقتال {choice}", caused_by_queue_full=False)
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}

            # توجيه الدفة: (غزاة/متمردين) — العفريت محذوف
            if choice == "elf":
                # مهمة العفريت تمت إزالتها — تخطي فوري
                self.log.info("ℹ️ [أولوية 6] مهمة العفريت (elf) غير متاحة — الانتقال للأولوية التالية.")
                return {"status": "skipped", "reason": "elf_removed"}
            else:
                combat_cfg = {
                    "monster_type": choice,
                    "max_marches": 15,
                    "min_lv": 1,
                    "max_lv": int(cfg.get("level", 35)),
                    "formation_id": int(cfg.get("formation_id", 1)),
                    "search_range": 120,
                    "wait_for_queue": False,  # تم التعطيل لأن المنسق هو من ينتظر
                    "troops_count": int(cfg.get("troops_count", 0)),
                    "busy_heroes": list(self._busy_heroes),
                }
                combat_task = MonsterTask(self.conn, combat_cfg)

            self._forward_subtask_logs(combat_task)
            
            # تنفيذ المهمة واستلام النتيجة
            res = await combat_task.run()
            self._busy_heroes.update(getattr(combat_task, '_busy', set()) or getattr(combat_task, '_busy_heroes', set()))
            
            # 4. تجميع الإحصائيات وفحص الرد
            res_data = getattr(res, "data", {}) if (res is not None and isinstance(getattr(res, "data", None), dict)) else {}
            sent_this = res_data.get("sent", 0)
            total_sent += sent_this

            err_msg = str(getattr(res, "error", "") or "") if res is not None else ""
            msg = str(getattr(res, "message", "") or "") if res is not None else ""
            stop_reason = str(res_data.get("stop_reason", ""))
            is_queue_full = bool(res_data.get("queue_full") or ("QUEUE_FULL" in err_msg) or ("QUEUE_FULL" in msg) or (stop_reason == "QUEUE_FULL"))

            # 5. معالجة حالات الاستمرار والتوقف:
            # أ) نفاذ طاقة اللورد بالكامل ➔ الانتقال للأولوية التالية فوراً دون أي انتظار
            if "STAMINA_EMPTY" in err_msg or "STAMINA_EMPTY" in msg or stop_reason == "STAMINA_EMPTY":
                self.log.warning("🛑 [أولوية 6] نفدت طاقة اللورد — سيتم الانتقال للأولوية التالية فوراً دون انتظار.")
                break

            # ب) في حال نجاح إرسال هجمات/مسيرات: تصفير الأخطاء والاستمرار
            if res is not None and res.success and sent_this > 0:
                consecutive_errors = 0
                if is_queue_full:
                    self.log.info(f"🛑 [أولوية 6: نفاذ الفيالق] الفيالق ممتلئة بعد إرسال الهجوم، المنسق سيتولى الانتظار...")
                    has_free_queue = await self.wait_for_free_queue(f"لقتال {choice}", caused_by_queue_full=True)
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}
                elif stop_reason == "NO_ARMY":
                    has_army = await self.ensure_army_or_wait(f"لمتابعة قتال {choice}", is_retry=True)
                    if not has_army:
                        return {"status": "critical_no_army", "sent": total_sent}
                else:
                    # مهلة أمان طبيعية بين الهجمات الناجحة
                    await asyncio.sleep(round(random.uniform(3.5, 6.0), 2))
                continue

            # ج) امتلاء طوابير الفيالق دون إرسال مسيرات جديدة ➔ انتظار تفريغ فيلق
            elif is_queue_full:
                self.log.info("🛑 [أولوية 6: نفاذ الفيالق] الفيالق ممتلئة، المنسق سيتولى الانتظار...")
                has_free_queue = await self.wait_for_free_queue(f"لقتال {choice}", caused_by_queue_full=True)
                if not has_free_queue:
                    return {"status": "timeout_or_no_queue", "sent": total_sent}
                continue

            # د) نقص القوات بالقلعة ➔ فحص ذكي وانتظار عودة القوات
            elif "NO_ARMY" in err_msg or "NO_ARMY" in msg or stop_reason == "NO_ARMY":
                has_army = await self.ensure_army_or_wait(f"لمتابعة قتال {choice}", is_retry=True)
                if not has_army:
                    return {"status": "critical_no_army", "sent": total_sent}
                continue

            # هـ) خطورة انتحار الجيش أمام هدف يفوق القوة ➔ الانتقال للأولوية التالية
            elif "SUICIDE_RISK" in err_msg or "SUICIDE_RISK" in msg or stop_reason == "SUICIDE_RISK":
                self.log.warning(f"🛑 [أولوية 6] تم إلغاء الهجوم على {choice} لتجنب انتحار الجيش أمام هدف يفوق قدرة القلعة — الانتقال للأولوية التالية.")
                break

            # و) انعدام أهداف قريبة أو الحدث غير نشط ➔ الانتقال للأولوية التالية
            elif "NO_TARGET" in err_msg or "لم يتم العثور" in msg or stop_reason == "NO_TARGET" or res_data.get("event_active") is False:
                self.log.warning(f"⚠️ [أولوية 6] لا توجد أهداف ({choice}) قريبة متاحة حالياً أو الحدث غير نشط — سيتم الانتقال للأولوية التالية.")
                break

            # و) أخطاء غير مصنفة: قاطع الدائرة الفوري (تخطي الأولوية فوراً دون أي إعادة محاولة لحماية الحساب)
            else:
                err_desc = err_msg or msg or stop_reason or "خطأ غير معروف"
                self.log.warning(f"🛑 [أولوية 6: قاطع الدائرة الفوري] توقف القتال بسبب: {err_desc} — تخطي الأولوية فوراً دون أي تكرار لمنع الحظر.")
                break

        self.log.info(f"🏁 [القتال الشامل] تم إرسال {total_sent} هجمة على ({choice})")
        return {"status": "completed", "sent": total_sent}


    # ────────────────────────────────────────────────────────────────
    #  الأولوية 7: الهجوم على المعاقل والملاجئ العامة (Stronghold)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_stronghold(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية الهجوم على المعاقل/الملاجئ العامة بالاعتماد على وحدة stronghold.py:
          - يهاجم بالعدد المحدد من المستخدم (count).
          - يفحص توفر الطاقة والجيش مسبقاً.
          - يُسند مهام الانتظار (في حال نفاذ الفيالق) للوحدة مع تمرير دورات الانتظار.
        """
        cfg = self.config.get("stronghold", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        needed = int(cfg.get("count", 2))
        target_lv = int(cfg.get("level", 30))
        self.log.info(f"🏰 [المعاقل] بدء الهجوم على المعاقل (مطلوب: {needed} | لفل: {target_lv})")

        # 1. فحص مسبق لطاقة اللورد (Stamina)
        lord_stamina = self._get_lord_stamina()
        if lord_stamina < 10:
            self.log.warning(f"🛑 [أولوية 7: المعاقل] طاقة اللورد الحالية ({lord_stamina}) غير كافية (مطلوب 10 على الأقل) — الانتقال للأولوية التالية.")
            return {"status": "stamina_empty", "stamina": lord_stamina}

        # 2. فحص مسبق ذكي للجيش بالقلعة
        has_army = await self.ensure_army_or_wait("لهجوم المعاقل العامة")
        if not has_army:
            return {"status": "critical_no_army"}

        rem_seconds = self.get_remaining_seconds()
        max_wait_cycles = max(1, int(rem_seconds // 120))

        # 3. تجهيز إعدادات StrongholdTask
        stronghold_cfg = {
            "max_marches": needed,
            "min_lv": 1,
            "max_lv": target_lv,
            "formation_id": int(cfg.get("formation_id", 1)),
            "search_range": int(cfg.get("search_range", 100)),
            "wait_for_queue": True,          # نترك للمهمة مهمة الانتظار الذكي عند الامتلاء
            "wait_interval": 165.0,          # انتظار قرابة دقيقتين ونصف إلى 3 دقائق (165 ثانية)
            "max_wait_cycles": max_wait_cycles,
            "troops_count": int(cfg.get("troops_count", 50000)),
            "busy_heroes": list(self._busy_heroes),
        }

        stronghold_task = StrongholdTask(self.conn, stronghold_cfg)
        self._forward_subtask_logs(stronghold_task)

        task_res = await stronghold_task.run()
        self._busy_heroes.update(getattr(stronghold_task, '_busy', set()))

        # 4. معالجة أسباب التوقف من المهمة
        task_res_data = getattr(task_res, "data", {}) if (task_res is not None and isinstance(getattr(task_res, "data", None), dict)) else {}
        stop_reason = task_res_data.get("stop_reason")
        if stop_reason == "STAMINA_EMPTY":
            self.log.warning("🛑 [أولوية 7] توقف الهجوم بسبب نفاد طاقة اللورد — الانتقال للأولوية التالية.")
        elif stop_reason == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم المعاقل", is_retry=True)
            if not has_army:
                return {"status": "critical_no_army"}

        sent_cnt = task_res_data.get("sent", 0)
        self.log.info(f"🏁 [المعاقل] تم إرسال {sent_cnt}/{needed} هجمة")

        return {
            "status": "completed",
            "sent": sent_cnt,
        }
    

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 8: جمع الذهب في أراضي التحالفات (Gold Gather)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_gold_gather(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية جمع الذهب في أراضي التحالفات المستهدفة:
          - تعتمد على ملف gold_gather.py المتقدم.
          - المنسق يغلف المهمة بحلقة ذكية: إذا امتلأت الفيالق، ينتظر تفريغها ثم يستأنف 
            إرسال مسيرات الذهب حتى استيفاء العدد المطلوب أو استنفاد الحقول.
        """
        cfg = self.config.get("gold_gather", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        locations = cfg.get("locations", [])
        if not locations:
            return {"status": "skipped", "reason": "no_locations"}

        requested_marches = int(cfg.get("max_marches", 0))
        self.log.info(f"💰 [جمع الذهب] بدء المسح والجمع (تحالفات: {len(locations)})")

        total_sent = 0

        while not self.is_time_expired():
            # 1. فحص الجيش قبل أي شيء (المنسق سيتولى الانتظار إذا كانت القوات بالخارج)
            has_army = await self.ensure_army_or_wait("لجمع الذهب")
            if not has_army:
                return {"status": "critical_no_army", "sent": total_sent}

            # 2. فحص امتلاء الفيالق مسبقاً (المنسق سيتولى الانتظار إذا كانت الفيالق ممتلئة)
            if getattr(self, '_max_castle_queues', 0) > 0:
                cur_act = await self.get_active_marches_count()
                if cur_act >= self._max_castle_queues:
                    has_free_queue = await self.wait_for_free_queue("لجمع الذهب", caused_by_queue_full=False)
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}

            # 3. تجهيز الإعدادات لتشغيل المهمة
            gold_cfg = dict(cfg)
            gold_cfg["busy_heroes"] = list(self._busy_heroes)
            if requested_marches > 0:
                rem = requested_marches - total_sent
                if rem <= 0:
                    break  # اكتمل العدد المطلوب
                gold_cfg["max_marches"] = rem
            else:
                gold_cfg["max_marches"] = 0  # 0 تعني استغلال كافة الفيالق

            # 4. تشغيل المهمة الفرعية
            gold_task = GoldGatherTask(self.conn, gold_cfg)
            self._forward_subtask_logs(gold_task)
            
            res = await gold_task.run()
            self._busy_heroes.update(gold_task._busy)
            
            sent_this_round = res.data.get("sent", 0) if res.data else 0
            total_sent += sent_this_round

            # 5. تقييم النتائج وتحديد الخطوة التالية
            if res.success:
                # إذا نجحت المهمة وأرسلت مسيرات (لكنها قد تكون توقفت بسبب امتلاء الفيالق)
                # سنعيد الدوران: المحرك سيفحص الفيالق في بداية الحلقة، وإذا كانت ممتلئة سينتظر بذكاء!
                await asyncio.sleep(round(random.uniform(1.8, 3.2), 2))
                continue
            else:
                # إذا فشلت المهمة وأعادت (TaskResult.fail)، فهذا يعني أن sent_count = 0
                # والسبب هو أنه "لم يتم العثور على حقول ذهب شاغرة" كما هو مبرمج في ملف gold_gather
                self.log.info("✅ [أولوية 8] تم استنفاد حقول الذهب المتاحة في التحالفات المستهدفة بنجاح.")
                break

        self.log.info(f"🏁 ───【 اكتمال أولوية جمع الذهب: تم إرسال {total_sent} مسيرة جمع 】───")
        return {
            "status": "completed",
            "sent": total_sent,
        }

    # ────────────────────────────────────────────────────────────────
    #  الأولوية 9: الجمع الخارجي المفتوح للموارد (Gather)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_gather(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية الجمع الخارجي المفتوح بالاعتماد على وحدة gather.py:
          - لا تتطلب طاقة (Stamina).
          - تستغل كافة الفيالق الشاغرة المتبقية بالقلعة حتى تمتلئ الطوابير بالكامل.
          - المنسق يتولى إدارة الانتظار بذكاء إذا نفدت الفيالق.
        """
        cfg = self.config.get("gather", {})
        if not cfg.get("enabled", False):
            return {"status": "skipped", "reason": "disabled"}

        res_type = cfg.get("res_type", 2)
        target_lv = int(cfg.get("level", 6))
        
        # استخراج اسم المورد للطباعة
        res_names = {1: "الذهب", 2: "القمح", 3: "الخشب", 4: "الحديد", 5: "الكوارنز"}
        res_name = res_names.get(int(res_type), str(res_type))

        # فحص شرط مستوى القلعة لموارد الحديد (10) والفضة (15) لتفادي الأخطاء 8041 و 8042
        castle_lv = self.get_castle_level()
        if int(res_type) == 4 and castle_lv < 10:
            self.log.warning(f"🛑 [الجمع المفتوح] جمع الحديد يتطلب قلعة لفل 10 على الأقل — تخطي.")
            return {"status": "skipped", "reason": "castle_level_low"}
        elif int(res_type) == 5 and castle_lv < 15:
            self.log.warning(f"🛑 [الجمع المفتوح] جمع الفضة يتطلب قلعة لفل 15 على الأقل — تخطي.")
            return {"status": "skipped", "reason": "castle_level_low"}

        self.log.info(f"🌾 [الجمع المفتوح] بدء جمع ({res_name}) لفل {target_lv}")

        # فحص ذكي مسبق للجيش (الجمع لا يتطلب طاقة)
        has_army = await self.ensure_army_or_wait("للجمع المفتوح")
        if not has_army:
            return {"status": "critical_no_army"}

        # فحص وتفعيل مكافأة سرعة الجمع من الحقيبة إذا كانت مفعلة في الإعدادات
        if cfg.get("use_boost", False):
            try:
                from tasks.gather_boost import GatherBoostTask
                boost_task = GatherBoostTask(self.conn, {"enabled": True})
                self._forward_subtask_logs(boost_task)
                await boost_task.run()
            except Exception as e:
                self.log.warning(f"⚠️ خطأ أثناء تشغيل مكافأة سرعة الجمع: {e}")

        total_sent = 0

        while not self.is_time_expired():
            # فحص امتلاء الفيالق مسبقاً
            if getattr(self, '_max_castle_queues', 0) > 0:
                cur_act = await self.get_active_marches_count()
                if cur_act >= self._max_castle_queues:
                    has_free_queue = await self.wait_for_free_queue(f"لجمع {res_name}", caused_by_queue_full=False)
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}

            gather_cfg = {
                "res_type": res_type,
                "level": target_lv,
                "max_marches": 6, # المنسق يرسلها حبة حبة ليسيطر على الطوابير بذكاء
                "search_range": 100,
                "busy_heroes": list(self._busy_heroes),
                "used_pets": list(self._used_pets),
                "max_heroes": 2,
            }

            gather_task = GatherTask(self.conn, gather_cfg)
            self._forward_subtask_logs(gather_task)
            
            res = await gather_task.run()

            # تراكم وتحديث الأبطال والحيوانات المشغولة
            self._busy_heroes.update(gather_task._busy_heroes)
            self._used_pets.update(gather_task._used_pets)

            # معالجة الرد القادم من مهمة الجمع
            sent_this_round = res.data.get("sent", 0) if res.data else 0
            total_sent += sent_this_round
            stop_reason = res.data.get("stop_reason") if res.data else None
            err_msg = str(res.error) if res.error else ""

            if res.success and sent_this_round > 0:
                # إذا توقف بسبب نفاد القوات أثناء الإرسال → انتظر فوراً
                if stop_reason in ("NO_ARMY", "8009") or "NO_ARMY" in err_msg:
                    has_army = await self.ensure_army_or_wait(f"لمتابعة جمع {res_name}", is_retry=True)
                    if not has_army:
                        return {"status": "critical_no_army", "sent": total_sent}
                    continue
                # وإلا: نجاح عادي، انتظر قليلاً وكمّل
                await asyncio.sleep(round(random.uniform(4.0, 7.0), 2))
                continue
                
            # إذا توقف الإرسال، نحلل السبب
            if stop_reason in ("QUEUE_FULL", "8004", "9007004") or "QUEUE_FULL" in err_msg:
                self.log.info(f"🛑 [أولوية 9: نفاذ الفيالق] الفيالق ممتلئة بالكامل، المنسق سيتولى الانتظار لجمع {res_name}...")
                has_free_queue = await self.wait_for_free_queue(f"لجمع {res_name}", caused_by_queue_full=True)
                if not has_free_queue:
                    return {"status": "timeout_or_no_queue", "sent": total_sent}
                continue
                
            elif stop_reason in ("NO_ARMY", "8009") or "NO_ARMY" in err_msg:
                has_army = await self.ensure_army_or_wait(f"لمتابعة جمع {res_name}", is_retry=True)
                if not has_army:
                    return {"status": "critical_no_army", "sent": total_sent}
                continue
                
            elif stop_reason == "NO_TARGET" or "NO_TARGET" in err_msg:
                self.log.warning(f"⚠️ [أولوية 9] لا توجد حقول ({res_name}) قريبة متاحة باللفل المطلوب حالياً — سيتم إنهاء هذه الأولوية.")
                break
                
            elif stop_reason == "CASTLE_LV_LOW":
                self.log.warning(f"🛑 [أولوية 9] تم إنهاء الجمع لعدم كفاية لفل القلعة لجمع {res_name}.")
                break
                
            else:
                self.log.warning(f"⚠️ تعذر استكمال الجمع المفتوح لسبب غير متوقع ({stop_reason}) — إنهاء الأولوية.")
                break

        self.log.info(f"🏁 [الجمع المفتوح] تم إرسال {total_sent} مسيرة لجمع {res_name}")
        return {
            "status": "completed",
            "sent": total_sent,
        }

    # ────────────────────────────────────────────────────────────────
    #  محرك التنفيذ المركزي (Execution Pipeline)
    # ────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """تشغيل منسق الفيالق والمسيرات المركزي عبر استدعاء المهام المتخصصة بالترتيب."""
        self.log.debug(f"🎖️ [منسق المسيرات] بدء التنسيق")
        self.start_time = time.time() 

        pipeline_results: Dict[str, Any] = {}

        # خريطة دوال الأولويات
        handlers = {
            "abra": self.execute_priority_abra,
            "prestige_invaders": self.execute_priority_prestige_invaders,
            "prestige_stronghold": self.execute_priority_prestige_stronghold,
            "prestige_gather": self.execute_priority_prestige_gather,
            "transport": self.execute_priority_transport,
            "ruins": self.execute_priority_ruins,
            "combat": self.execute_priority_combat,
            "stronghold": self.execute_priority_stronghold,
            "gold_gather": self.execute_priority_gold_gather,
            "gather": self.execute_priority_gather,
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

            try:
                res = await handler()
            except Exception as e:
                self.log.error(f"❌ خطأ غير متوقع أثناء تنفيذ أولوية [{p_key}]: {e}", exc_info=True)
                pipeline_results[p_key] = {"status": "error", "error": str(e)}
                continue

            res = res or {}
            pipeline_results[p_key] = res

            # الحالة 3: إذا نفدت القوات كلياً من القلعة ➔ خروج فوري من المهمة ككل
            if res.get("status") == "critical_no_army":
                self.log.warning("🛑 [الحالة 3: خروج فوري] إنهاء مهمة المسيرات ككل لعدم توفر قوات كافية بالقلعة حتى خارج التشكيلة.")
                return TaskResult.fail(
                    "إنهاء مهمة المسيرات ككل: عدم توفر قوات كافية بالقلعة حتى خارج التشكيلة",
                    data=pipeline_results
                )

            # ────────────────────────────────────────────────────────────────
            # الحالة 6: نفاذ طاقة اللورد (Stamina)
            # ────────────────────────────────────────────────────────────────
            if res.get("status") == "stamina_empty":
                self.log.warning(f"🔋 [الحالة 6: نفاذ طاقة اللورد] تم إيقاف/تخطي أولوية [{p_key}] لأن طاقة اللورد غير كافية للهجوم، سيتم استكمال فحص الأولويات السلمية.")
                # نستخدم continue للانتقال للمهمة التالية (مثل الجمع أو النقل) بدلاً من الخروج الكلي
                continue

            await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))


        # ── الحالة 5: انتهاء الأولويات بنجاح مع وجود فيالق نشطة ──────
        msg = f"🎉 اكتملت أولويات المسيرات بنجاح."
        self.log.info(msg)
        return TaskResult.ok(msg, data=pipeline_results)

        
