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
from tasks.stronghold import StrongholdTask
from tasks.gather import GatherTask
from tasks.transport import TransportTask
from tasks.ruins import RuinsTask
from tasks.monster import MonsterTask
from tasks.elf_boss import ElfBossTask
from tasks.gold_gather import GoldGatherTask

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
        self.log.propagate = True

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

    def _get_lord_stamina(self) -> int:
        """جلب رصيد طاقة اللورد الحالي من بيانات القلعة المحملة."""
        try:
            base = self.conn.init_data.get('loginDataInitCtrl', {}).get('base', {}) if hasattr(self.conn, 'init_data') else {}
            return int(float(base.get('health', 100)))
        except Exception:
            return 100

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

    async def get_active_marches_count(self) -> int:
        """حساب عدد الفيالق والمسيرات النشطة حالياً خارج القلعة مع تحديث فوري وتجنب التكرار."""
        try:
            await self.conn.query('1007', '1000', {}, timeout=2)
            await asyncio.sleep(0.3)
        except Exception:
            pass

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
                if isinstance(q, dict) and q.get('status') in (1, 2, 3, 4, 7):
                    qid = q.get('id') or q.get('queueId')
                    if qid:
                        if qid not in seen_ids:
                            seen_ids.add(qid)
                            active += 1
                    else:
                        active += 1
        return active

    async def wait_for_free_queue(self, context_desc: str = "") -> bool:
        """
        الانتظار الذكي عند نفاذ الفيالق (الحالة 1):
          - يسجل سقف الفيالق الممتلئة للقلعة عند حدوث امتلاء الفيالق (كود 8004).
          - يدخل حلقة انتظار بدقيقة كاملة (60 ثانية).
          - بعد انتهاء الدقيقة: يستعلم من السيرفر فورياً (1007/1000) ويفحص حالة وعدد الفيالق.
          - إذا وجد فيلقاً شاغراً (عاد أحد الفيالق)، يخرج فوراً ويسمح بإطلاق المسيرة.
          - إذا كانت جميع الفيالق لا تزال مشغولة بالكامل، لا يطلق المسيرة ولا يرسل حزم للسيرفر، بل يواصل دورة انتظار 60 ثانية أخرى.
        """
        current_active = await self.get_active_marches_count()
        max_q = getattr(self, '_max_castle_queues', 0)
        if current_active > max_q:
            self._max_castle_queues = current_active
            max_q = current_active
        if max_q <= 0:
            max_q = max(current_active, self.max_queues)
            self._max_castle_queues = max_q

        # إذا كان هناك فيلق شاغر بالفعل عند الفحص، السماح بالإطلاق فوراً دون انتظار 60 ثانية
        if 0 <= current_active < max_q:
            return True

        wait_count = 0
        while not self.is_time_expired():
            wait_count += 1
            self.log.info(
                f"⏳ [الحالة 1: نفاذ الفيالق ({current_active}/{max_q})] "
                f"جميع الفيالق مشغولة بالخارج — الانتظار دقيقة كاملة (60 ثانية) لتفريغ فيلق {context_desc} [دورة {wait_count}]..."
            )
            await asyncio.sleep(60)

            if self.is_time_expired():
                self.log.warning("⏱️ [انتهاء المهلة] انتهت مهلة الـ 20 دقيقة المخصصة أثناء انتظار عودة الفيالق.")
                return False

            # فحص حالة الفيالق بعد انتهاء دقيقة الانتظار قبل القيام بأي محاولة إطلاق
            current_active = await self.get_active_marches_count()
            self.log.info(f"🔍 [فحص الفيالق] الفيالق النشطة بالخارج حالياً: {current_active}/{max_q}")

            if current_active < max_q:
                self.log.info(
                    f"✅ [توفر فيلق شاغر] عاد أحد الفيالق إلى القلعة بنجاح ({current_active}/{max_q}) "
                    f"— جاري إطلاق المسيرة {context_desc} الآن!"
                )
                return True
            else:
                self.log.info(
                    f"⏳ [الفيالق لا تزال ممتلئة ({current_active}/{max_q})] "
                    f"لم يعد أي فيلق بعد — مواصلة الانتظار 60 ثانية أخرى دون إرسال محاولات فاشلة..."
                )

        return False

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
        min_needed = 50 if any(k in context_desc for k in ("جمع", "أطلال", "نقل")) else MIN_ATTACK_ARMY_COUNT

        while not self.is_time_expired():
            castle_troops = await self.get_total_available_castle_army()
            if castle_troops >= min_needed:
                return True

            active_marches = await self.get_active_marches_count()
            if active_marches == 0:
                # إعادة التحقق بعد 2.5 ثانية لتفادي أي تأخير لحظي في تحديث السيرفر فور إرسال المسيرة
                await asyncio.sleep(2.5)
                active_marches = await self.get_active_marches_count()

            if active_marches > 0:
                self.log.info(
                    f"⏳ [الحالة 1: القوات في مسيرات بالخارج ({active_marches} مسيرات نشطة)] "
                    f"رصيد القلعة الحالي ({castle_troops}) — انتظار دقيقة كاملة (60 ثانية) لعودة الجيش {context_desc}..."
                )
                await asyncio.sleep(60)
                await self._refresh_merit_data()
            else:
                self.log.warning(
                    f"🛑 [الحالة 3: انعدام القوات كلياً] تم التأكد: لا توجد أي مسيرات بالخارج (0 مسيرة نشطة) "
                    f"وإجمالي قوات القلعة ({castle_troops}) أقل من الحد الأدنى ({min_needed}) — الخروج فوراً."
                )
                return False

        self.log.warning("⏱️ [انتهاء المهلة] انتهت الـ 20 دقيقة المحددة للمهمة أثناء انتظار عودة الجيش.")
        return False


    async def is_ruins_march_active(self) -> bool:
        """
        يفحص بشكل فوري ما إذا كانت هناك مسيرة استكشاف أطلال نشطة بالخارج حالياً.
        يعتمد على نوع المسار (moveLineType = 4) أو نوع خريطة الهدف (mapType = 7).
        """
        try:
            await self.conn.query('1007', '1000', {}, timeout=3)
            await asyncio.sleep(0.3)
        except Exception:
            pass

        all_queue_data = []
        if getattr(self.conn, 'local_queues', None):
            all_queue_data.extend(self.conn.local_queues)
        for p in self.conn.cached_packets.values():
            if isinstance(p, dict) and p.get('data', {}).get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC':
                nd = p.get('data', {}).get('notifyData', [])
                if isinstance(nd, list):
                    all_queue_data.extend(nd)

        for item in all_queue_data:
            q_list = item.get('data', []) if isinstance(item, dict) else (item if isinstance(item, list) else [])
            for q in q_list:
                if not isinstance(q, dict):
                    continue
                # حالة المسيرة نشطة
                if q.get('status') in (1, 2, 3, 4, 7):
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
            subtask.log.propagate = True

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

        # --- سطر الطباعة للتأكد من القيمة ---
        main_enabled_value = self.config.get('is_main_prestige_enabled', True)
        self.log.info(f"🔎 [فحص الحقل المحقون] قيمة is_main_prestige_enabled هي: {main_enabled_value}")

        # 1. التحقق من تفعيل قسم الهيبة الرئيسي
        if not self.config.get("is_main_prestige_enabled", True):
            self.log.info("⏭️ [أولوية 1] تم تخطي غزاة الهيبة (قسم الهيبة الرئيسي معطل بالكامل).")
            return {"status": "skipped", "reason": "main_prestige_disabled"}

        
        cfg = self.config.get("prestige_invaders", {})
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
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

        # فحص مسبق لطاقة اللورد (Stamina) لتجنب أخطاء 8032 والمحاولات غير المجدية
        lord_stamina = self._get_lord_stamina()
        if lord_stamina < 10:
            self.log.warning(f"🛑 [أولوية 1: غزاة الهيبة] طاقة اللورد الحالية ({lord_stamina}) غير كافية لمسيرات الهجوم (مطلوب 10 على الأقل) — الانتقال للأولوية التالية.")
            return {"status": "stamina_empty", "stamina": lord_stamina}

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

        task_res_data = getattr(task_res, "data", {}) if (task_res is not None and isinstance(getattr(task_res, "data", None), dict)) else {}

        # فحص نفاد الطاقة أثناء الهجمات (كود 8032)
        if task_res_data.get("stop_reason") == "STAMINA_EMPTY":
            self.log.warning("🛑 [أولوية 1: غزاة الهيبة] توقف الهجوم بسبب نفاد طاقة اللورد — الانتقال للأولوية التالية.")

        # فحص الحالة 3 بعد المحاولة: هل نفد الجيش كلياً؟
        if task_res_data.get("stop_reason") == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم الغزاة")
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
            self.log.info("⏭️ [أولوية 2] تم تخطي معقل الهيبة (قسم الهيبة الرئيسي معطل بالكامل).")
            return {"status": "skipped", "reason": "main_prestige_disabled"}

        cfg = self.config.get("prestige_stronghold", {})
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
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

        task_res_data = getattr(task_res, "data", {}) if (task_res is not None and isinstance(getattr(task_res, "data", None), dict)) else {}

        # فحص نفاد الطاقة أثناء الهجمات (كود 8032)
        if task_res_data.get("stop_reason") == "STAMINA_EMPTY":
            self.log.warning("🛑 [أولوية 2: معقل الهيبة] توقف الهجوم بسبب نفاد طاقة اللورد — الانتقال للأولوية التالية.")

        # فحص الحالة 3 بعد المحاولة: هل نفد الجيش كلياً؟
        if task_res_data.get("stop_reason") == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم المعقل")
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
          4. تطبيق الحالات الخمس (نفاذ الفيالق 60ث، نقص التشكيلة، انعدام الجيش، تعذر الأهداف).
        """

        # 1. التحقق من تفعيل قسم الهيبة الرئيسي
        if not self.config.get("is_main_prestige_enabled", True):
            self.log.info("⏭️ [أولوية 3] تم تخطي جمع موارد الهيبة (قسم الهيبة الرئيسي معطل بالكامل).")
            return {"status": "skipped", "reason": "main_prestige_disabled"}


        cfg = self.config.get("prestige_gather", {})
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
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
                # فحص مسبق: إذا كان سقف الفيالق معروفاً وكل الفيالق مشغولة بالخارج حالياً، ننتظر تفريغ فيلق أولاً
                if getattr(self, '_max_castle_queues', 0) > 0:
                    cur_act = await self.get_active_marches_count()
                    if cur_act >= self._max_castle_queues:
                        has_free_queue = await self.wait_for_free_queue(f"لجمع {item['name']}")
                        if not has_free_queue:
                            return {"status": "timeout_or_no_queue"}

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

                res_data = getattr(res, "data", {}) if (res is not None and isinstance(getattr(res, "data", None), dict)) else {}

                if res is not None and res.success and res_data.get("sent", 0) > 0:
                    sent_total += 1
                    results_by_res[item["key"]] = "sent"
                    active_gather_types.add(item["res_type"])
                    self.log.info(f"✅ تم إرسال مسيرة جمع عادية لـ {item['name']} بنجاح لإنجاز مهمة الهيبة!")
                    break

                # الحالة 1: الفيالق ممتلئة بالكامل بالخارج (كود 8004)
                if res_data.get("queue_full"):
                    has_free_queue = await self.wait_for_free_queue(f"لجمع {item['name']}")
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue"}
                    continue

                # فحص الحالة 3: انعدام الجيش بالقلعة
                if res_data.get("stop_reason") == "NO_ARMY":
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
    #  الأولوية 4: مساعدة الموارد (Resource Transport / Aid)
    # ────────────────────────────────────────────────────────────────

    async def execute_priority_transport(self) -> Dict[str, Any]:
        """
        تنفيذ أولوية مساعدة ونقل الموارد بالاعتماد المباشر على وحدة transport.py:
          - يتم تفويض منطق بناء الحزمة وتقسيم الحمولة لملف النقل المتخصص.
          - يقتصر دور المنسق على مراقبة الفيالق (الحالة 1) وإدارة مهلة الـ 20 دقيقة.
        """
        cfg = self.config.get("transport", {})
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 transport: {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 4] تم تخطي مساعدة الموارد (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        target_x = cfg.get("target_x")
        target_y = cfg.get("target_y")
        if target_x is None or target_y is None or (int(target_x) == 0 and int(target_y) == 0):
            self.log.warning("⚠️ [أولوية 4] لم يتم تحديد إحداثيات القلعة الهدف...")
            return {"status": "skipped", "reason": "no_target_coords"}

        self.log.info(f"🚚 ───【 الأولوية 4: مساعدة ونقل الموارد إلى ({target_x}, {target_y}) 】───")

        sent_total = 0
        total_transported = 0

        while not self.is_time_expired():
            # فحص مسبق لامتلاء الفيالق (الحالة 1 الخاصة بالمنسق)
            if getattr(self, '_max_castle_queues', 0) > 0:
                cur_act = await self.get_active_marches_count()
                if cur_act >= self._max_castle_queues:
                    has_free_queue = await self.wait_for_free_queue("لنقل الموارد")
                    if not has_free_queue:
                        break

            # تجهيز الإعدادات لتشغيل مسيرة واحدة في كل دورة ليحتفظ المنسق بالسيطرة
            transport_cfg = dict(cfg)
            transport_cfg["max_marches"] = 1

            # تشغيل المهمة الفرعية من ملف transport.py
            transport_task = TransportTask(self.conn, transport_cfg)
            self._forward_subtask_logs(transport_task)
            
            res = await transport_task.run()

            # معالجة الرد القادم من ملف النقل
            res_data = getattr(res, "data", {}) if (res is not None and isinstance(getattr(res, "data", None), dict)) else {}
            sent_count = res_data.get("sent", 0)
            reason = res_data.get("reason")

            if res is not None and res.success and sent_count > 0:
                sent_total += sent_count
                total_transported += res_data.get("total", 0)
            elif reason == "queue_full" or res_data.get("queue_full"):
                self.log.info("🛑 [أولوية 4: نفاذ الفيالق] الفيالق ممتلئة، المنسق سيتولى الانتظار...")
                has_free_queue = await self.wait_for_free_queue("لنقل الموارد")
                if not has_free_queue:
                    break
            else:
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
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 ruins: {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 5] تم تخطي استكشاف الأطلال (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        self.log.info("🏛️ ───【 الأولوية 5: استكشاف الأطلال (Ruins) 】───")

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
                    has_free_queue = await self.wait_for_free_queue("لاستكشاف الأطلال")
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue"}

            ruins_cfg = dict(cfg)
            ruins_cfg["max_marches"] = 1  # إجبار البوت على إرسال مسيرة واحدة فقط
            
            ruins_task = RuinsTask(self.conn, ruins_cfg)
            self._forward_subtask_logs(ruins_task)
            res = await ruins_task.run()

            # 3. معالجة النتيجة
            if res.success:
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
          - يقرأ خيار المستخدم (elf, invaders, rebels).
          - يستدعي ملف elf_boss.py أو monster.py حسب الهدف المختار.
          - يستمر بالهجوم حتى نفاذ طاقة اللورد، ويتولى المنسق إدارة مهلة الفيالق.
        """
        cfg = self.config.get("combat", {})
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 combat: {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 6] تم تخطي القتال الشامل (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        choice = str(cfg.get("choice", "elf")).strip().lower()
        self.log.info(f"⚔️ ───【 الأولوية 6: القتال الشامل (الهدف: {choice}) 】───")

        # 1. فحص مسبق لطاقة اللورد
        lord_stamina = self._get_lord_stamina()
        if lord_stamina < 10:
            self.log.warning(f"🛑 [أولوية 6] طاقة اللورد الحالية ({lord_stamina}) غير كافية للقتال — الانتقال للأولوية التالية.")
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
                    has_free_queue = await self.wait_for_free_queue(f"لقتال {choice}")
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}

            # توجيه الدفة: عفريت أو (غزاة/متمردين)
            if choice == "elf":
                combat_cfg = {
                    "formation_id": int(cfg.get("formation_id", 1)),
                    "boss_type": 10,
                    "all_legions": True,
                }
                combat_task = ElfBossTask(self.conn, combat_cfg)
            else:
                combat_cfg = {
                    "monster_type": choice,
                    "max_marches": 50,
                    "min_lv": 1,
                    "max_lv": int(cfg.get("level", 35)),
                    "formation_id": int(cfg.get("formation_id", 1)),
                    "search_range": 120,
                    "wait_for_queue": False,  # تم التعطيل لأن المنسق هو من ينتظر
                    "troops_count": int(cfg.get("troops_count", 50000)),
                }
                combat_task = MonsterTask(self.conn, combat_cfg)

            self._forward_subtask_logs(combat_task)
            
            # تنفيذ المهمة واستلام النتيجة
            res = await combat_task.run()
            
            # 4. تجميع الإحصائيات وفحص الرد
            res_data = getattr(res, "data", {}) if (res is not None and isinstance(getattr(res, "data", None), dict)) else {}
            sent_this = (res_data.get("attacks", 0) if choice == "elf" else res_data.get("sent", 0))
            total_sent += sent_this

            err_msg = str(getattr(res, "error", "") or "") if res is not None else ""
            msg = str(getattr(res, "message", "") or "") if res is not None else ""
            stop_reason = str(res_data.get("stop_reason", ""))
            is_queue_full = bool(res_data.get("queue_full") or ("QUEUE_FULL" in err_msg) or ("QUEUE_FULL" in msg) or (stop_reason == "QUEUE_FULL"))

            # 5. معالجة حالات الاستمرار والتوقف:
            # أ) في حال نجاح إرسال هجمات/مسيرات: تصفير الأخطاء والاستمرار فوراً
            if res is not None and res.success and sent_this > 0:
                consecutive_errors = 0
                if is_queue_full:
                    self.log.info(f"🛑 [أولوية 6: نفاذ الفيالق] الفيالق ممتلئة بعد إرسال الهجوم، المنسق سيتولى الانتظار...")
                    has_free_queue = await self.wait_for_free_queue(f"لقتال {choice}")
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}
                else:
                    await asyncio.sleep(round(random.uniform(4.0, 7.0), 2))
                continue

            # ب) نفاذ طاقة اللورد بالكامل ➔ الانتقال للأولوية التالية
            if "STAMINA_EMPTY" in err_msg or "STAMINA_EMPTY" in msg or stop_reason == "STAMINA_EMPTY":
                self.log.warning("🛑 [أولوية 6] نفدت طاقة اللورد — سيتم الانتقال للأولوية التالية.")
                break

            # ج) امتلاء طوابير الفيالق دون إرسال مسيرات جديدة ➔ انتظار تفريغ فيلق
            elif is_queue_full:
                self.log.info("🛑 [أولوية 6: نفاذ الفيالق] الفيالق ممتلئة، المنسق سيتولى الانتظار...")
                has_free_queue = await self.wait_for_free_queue(f"لقتال {choice}")
                if not has_free_queue:
                    return {"status": "timeout_or_no_queue", "sent": total_sent}
                continue

            # د) نقص القوات بالقلعة ➔ فحص ذكي وانتظار عودة القوات
            elif "NO_ARMY" in err_msg or "NO_ARMY" in msg or stop_reason == "NO_ARMY":
                has_army = await self.ensure_army_or_wait(f"لمتابعة قتال {choice}")
                if not has_army:
                    return {"status": "critical_no_army", "sent": total_sent}
                continue

            # هـ) انعدام أهداف قريبة أو الحدث غير نشط ➔ الانتقال للأولوية التالية
            elif "NO_TARGET" in err_msg or "لم يتم العثور" in msg or stop_reason == "NO_TARGET" or res_data.get("event_active") is False:
                self.log.warning(f"⚠️ [أولوية 6] لا توجد أهداف ({choice}) قريبة متاحة حالياً أو الحدث غير نشط — سيتم الانتقال للأولوية التالية.")
                break

            # و) أخطاء غير مصنفة: المحاولة حتى 3 مرات قبل الانتقال للأولوية التالية
            else:
                consecutive_errors += 1
                err_desc = err_msg or msg or stop_reason or "خطأ غير معروف"
                self.log.warning(f"⚠️ [أولوية 6: قتال] خطأ غير مصنف ({consecutive_errors}/3): {err_desc}")
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ [أولوية 6] 3 أخطاء متتالية غير مصنفة أثناء القتال — تخطي هذه الأولوية والانتقال للأولوية التالية.")
                    break
                await asyncio.sleep(3.0)
                continue

        self.log.info(f"🏁 ───【 اكتمال أولوية القتال الشامل: تم إرسال {total_sent} هجمة على ({choice}) 】───")
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
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 stronghold: {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 7] تم تخطي الهجوم على المعاقل (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        needed = int(cfg.get("count", 2))
        target_lv = int(cfg.get("level", 30))
        self.log.info(f"🏰 ───【 الأولوية 7: الهجوم على المعاقل (العدد المطلوب: {needed} هجمات | لفل: {target_lv}) 】───")

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
        max_wait_cycles = max(1, int(rem_seconds // 60))

        # 3. تجهيز إعدادات StrongholdTask
        stronghold_cfg = {
            "max_marches": needed,
            "min_lv": 1,
            "max_lv": target_lv,
            "formation_id": int(cfg.get("formation_id", 1)),
            "search_range": int(cfg.get("search_range", 100)),
            "wait_for_queue": True,          # نترك للمهمة مهمة الانتظار الذكي عند الامتلاء
            "wait_interval": 60.0,
            "max_wait_cycles": max_wait_cycles,
            "troops_count": int(cfg.get("troops_count", 50000)),
        }

        stronghold_task = StrongholdTask(self.conn, stronghold_cfg)
        self._forward_subtask_logs(stronghold_task)

        task_res = await stronghold_task.run()

        # 4. معالجة أسباب التوقف من المهمة
        task_res_data = getattr(task_res, "data", {}) if (task_res is not None and isinstance(getattr(task_res, "data", None), dict)) else {}
        stop_reason = task_res_data.get("stop_reason")
        if stop_reason == "STAMINA_EMPTY":
            self.log.warning("🛑 [أولوية 7] توقف الهجوم بسبب نفاد طاقة اللورد — الانتقال للأولوية التالية.")
        elif stop_reason == "NO_ARMY":
            has_army = await self.ensure_army_or_wait("لمتابعة هجوم المعاقل")
            if not has_army:
                return {"status": "critical_no_army"}

        sent_cnt = task_res_data.get("sent", 0)
        self.log.info(f"🏁 ───【 اكتمال أولوية المعاقل: تم إرسال {sent_cnt} هجمة من أصل {needed} 】───")

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
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 gold_gather: {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 8] تم تخطي جمع الذهب في أراضي التحالفات (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        locations = cfg.get("locations", [])
        if not locations:
            self.log.warning("⚠️ [أولوية 8] تم تفعيل جمع الذهب لكن لم يتم تحديد أي مواقع (Locations) في الإعدادات.")
            return {"status": "skipped", "reason": "no_locations"}

        requested_marches = int(cfg.get("max_marches", 0))
        target_desc = "استغلال كافة الفيالق الشاغرة" if requested_marches == 0 else f"{requested_marches} مسيرات"
        self.log.info(f"💰 ───【 الأولوية 8: جمع الذهب (التحالفات: {len(locations)} | المطلوب: {target_desc}) 】───")

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
                    has_free_queue = await self.wait_for_free_queue("لجمع الذهب")
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}

            # 3. تجهيز الإعدادات لتشغيل المهمة
            gold_cfg = dict(cfg)
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
            
            sent_this_round = res.data.get("sent", 0) if res.data else 0
            total_sent += sent_this_round

            # 5. تقييم النتائج وتحديد الخطوة التالية
            if res.success:
                # إذا نجحت المهمة وأرسلت مسيرات (لكنها قد تكون توقفت بسبب امتلاء الفيالق)
                # سنعيد الدوران: المحرك سيفحص الفيالق في بداية الحلقة، وإذا كانت ممتلئة سينتظر بذكاء!
                await asyncio.sleep(2)
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
        self.log.info(f"🔎🔎🔎🔎🔎🔎🔎🔎🔎 gather: {cfg.get('enabled')}")
        if not cfg.get("enabled", False):
            self.log.info("⏭️ [أولوية 9] تم تخطي الجمع الخارجي المفتوح (معطلة من الإعدادات).")
            return {"status": "skipped", "reason": "disabled"}

        res_type = cfg.get("res_type", 2)
        target_lv = int(cfg.get("level", 6))
        
        # استخراج اسم المورد للطباعة
        res_names = {1: "الذهب", 2: "القمح", 3: "الخشب", 4: "الحديد", 5: "الكوارنز"}
        res_name = res_names.get(int(res_type), str(res_type))

        self.log.info(f"🌾 ───【 الأولوية 9: الجمع الخارجي المفتوح (المورد: {res_name} | لفل: {target_lv} | استغلال كافة الفيالق الشاغرة) 】───")

        # فحص ذكي مسبق للجيش (الجمع لا يتطلب طاقة)
        has_army = await self.ensure_army_or_wait("للجمع المفتوح")
        if not has_army:
            return {"status": "critical_no_army"}

        total_sent = 0

        while not self.is_time_expired():
            # فحص امتلاء الفيالق مسبقاً
            if getattr(self, '_max_castle_queues', 0) > 0:
                cur_act = await self.get_active_marches_count()
                if cur_act >= self._max_castle_queues:
                    has_free_queue = await self.wait_for_free_queue(f"لجمع {res_name}")
                    if not has_free_queue:
                        return {"status": "timeout_or_no_queue", "sent": total_sent}

            gather_cfg = {
                "res_type": res_type,
                "level": target_lv,
                "max_marches": 1, # المنسق يرسلها حبة حبة ليسيطر على الطوابير بذكاء
                "search_range": 100,
                "busy_heroes": list(self._busy_heroes),
                "used_pets": list(self._used_pets),
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
                # نجاح الإرسال، ننتظر قليلاً قبل فحص الفيلق التالي (المنسق سيفحص الفيالق في بداية الحلقة)
                await asyncio.sleep(round(random.uniform(4.0, 7.0), 2))
                continue
                
            # إذا توقف الإرسال، نحلل السبب
            if stop_reason in ("QUEUE_FULL", "8004", "9007004") or "QUEUE_FULL" in err_msg:
                self.log.info(f"🛑 [أولوية 9: نفاذ الفيالق] الفيالق ممتلئة بالكامل، المنسق سيتولى الانتظار لجمع {res_name}...")
                has_free_queue = await self.wait_for_free_queue(f"لجمع {res_name}")
                if not has_free_queue:
                    return {"status": "timeout_or_no_queue", "sent": total_sent}
                continue
                
            elif stop_reason in ("NO_ARMY", "8009") or "NO_ARMY" in err_msg:
                has_army = await self.ensure_army_or_wait(f"لمتابعة جمع {res_name}")
                if not has_army:
                    return {"status": "critical_no_army", "sent": total_sent}
                continue
                
            elif stop_reason == "NO_TARGET" or "NO_TARGET" in err_msg:
                self.log.warning(f"⚠️ [أولوية 9] لا توجد حقول ({res_name}) قريبة متاحة باللفل المطلوب حالياً — سيتم إنهاء هذه الأولوية.")
                break
                
            else:
                self.log.warning(f"⚠️ تعذر استكمال الجمع المفتوح لسبب غير متوقع ({stop_reason}) — إنهاء الأولوية.")
                break

        self.log.info(f"🏁 ───【 اكتمال أولوية الجمع الخارجي: تم إرسال {total_sent} مسيرة لجمع {res_name} 】───")
        return {
            "status": "completed",
            "sent": total_sent,
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

        # ── 🚨 فحص الفيالق المشغولة الإلزامي عند انتهاء مهمة مدير المسيرات ──
        # سواء انتهت المهمة بالوقت أو باكتمال الأولويات: إذا لم يكن هناك أي فيلق مشغول (0 مسيرات نشطة)، فهذا خطأ خطير جداً
        await asyncio.sleep(1.0)
        final_busy_marches = await self.get_active_marches_count()
        if final_busy_marches == 0:
            finish_reason = "time_expired" if self.is_time_expired() else "priorities_completed"
            finish_reason_ar = "انتهاء مهلة الوقت للمهمة (20 دقيقة)" if finish_reason == "time_expired" else "انتهاء وفحص كافة الأولويات"

            danger_title = f"🚨 خطأ فادح: انتهت مهمة المسيرات دون وجود أي فيلق مشغول (0 مسيرات نشطة)!"
            danger_msg = (
                f"🚨 تنبيه إداري فائق الخطورة (CRITICAL FAILURE):\n"
                f"انتهت مهمة مدير المسيرات للحساب [{self.email}] بسبب ({finish_reason_ar})، "
                f"ولكن عند الفحص النهائي الشامل تبيّن عدم وجود أي فيلق مشغول أو نشط بالخارج (0 فيالق)!\n"
                f"القلعة باتت خاملة تماماً دون جمع موارد أو تنفيذ مهام حربية، وتوقفت طوابير المسيرات بالكامل."
            )
            self.log.critical(danger_msg)

            fail_msg = f"🚨 خطأ: انتهت المهمة دون وجود أي فيلق مشغول (0 فيالق مشغولة)."
            return TaskResult.fail(fail_msg, data=pipeline_results, active_marches=0)

        # ── الحالة 5: انتهاء الأولويات بنجاح مع وجود فيالق نشطة ──────
        msg = f"🎉 [الحالة 5: اكتمال الأولويات] تم الانتهاء من أولويات المسيرات بنجاح ({final_busy_marches} فيالق مشغولة بالخارج)."
        self.log.info(msg)
        return TaskResult.ok(msg, data=pipeline_results, active_marches=final_busy_marches)

        
