# -*- coding: utf-8 -*-
"""
tasks/base_task.py — العقد المشترك لجميع مهام البوت
════════════════════════════════════════════════════

كل مهمة في مجلد tasks/ ترث من BaseTask وتُنفِّذ:
    - run()   : تنفيذ المهمة مرة واحدة، يعيد TaskResult
    - stop()  : إيقاف آمن للمهمة
    - status(): حالة المهمة الحالية (للمراقبة والـ panel)

TaskScheduler: يشغل run() بشكل دوري مع interval + offset
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple ,Set

if TYPE_CHECKING:
    from game_client import GameConnection

log = logging.getLogger("tasks")


# ════════════════════════════════════════════════════════════════════
#  حالات تشغيل المهمة
# ════════════════════════════════════════════════════════════════════

class TaskState(str, Enum):
    IDLE      = "idle"       # لم تبدأ بعد
    RUNNING   = "running"    # تعمل الآن
    WAITING   = "waiting"    # تنتظر interval القادم
    STOPPED   = "stopped"    # تم الإيقاف
    ERROR     = "error"      # توقفت بسبب خطأ


# ════════════════════════════════════════════════════════════════════
#  نتيجة المهمة (TaskResult)
# ════════════════════════════════════════════════════════════════════

@dataclass
class TaskResult:
    """نتيجة تنفيذ مهمة واحدة — موحدة لكل المهام."""
    success:      bool
    message:      str
    data:         Dict[str, Any] = field(default_factory=dict)
    should_retry: bool = False
    retry_after:  int  = 0    # ثواني قبل إعادة المحاولة
    action:       Optional[str] = None

    @classmethod
    def ok(cls, message: str = "✅ تم بنجاح", action: Optional[str] = None, **data) -> "TaskResult":
        act = action or data.get("action")
        if act:
            data["action"] = act
        return cls(success=True, message=message, data=data, action=act)

    @classmethod
    def fail(cls, message: str, retry_after: int = 0, action: Optional[str] = None, **data) -> "TaskResult":
        act = action or data.get("action")
        if act:
            data["action"] = act
        return cls(success=False, message=message, data=data,
                   should_retry=retry_after > 0, retry_after=retry_after, action=act)

    @property
    def error(self) -> str:
        return "" if self.success else self.message

    @classmethod
    def queue_full(cls) -> "TaskResult":
        return cls(success=True, message="🛑 الطوابير ممتلئة", data={"reason": "queue_full"})

    @classmethod
    def no_heroes(cls) -> "TaskResult":
        return cls(success=False, message="⚠️ لا يوجد أبطال متاحون", data={"reason": "no_heroes"},
                   should_retry=True, retry_after=300)

    def __bool__(self):
        return self.success


# ── المعرفات الرسمية لمهام الهيبة اليومية (meritoriousTaskCtrl) ──────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    # مهام المسيرات الخارجية
    "invaders":        4112004,  # قتل غزاة الهيبة (5 هجمات)
    "stronghold":      4112019,  # الهجوم على معقل الهيبة (3 هجمات)
    "gather":          4112006,  # جمع موارد الهيبة (25 ألف مورد)
    # مهام داخل المدينة
    "smuggler":        4112022,  # متجر المهربين (10 مشتريات)
    "watermill":       4112027,  # تعزيز إنتاج الساقية (مرة واحدة)
    "badge_exchange":  4112024,  # استبدال وسام الحرب (مرة واحدة)
    "train":           4112001,  # تدريب الجنود
    "fortress":        4112015,  # تدريب الفخاخ
}


# ════════════════════════════════════════════════════════════════════
#  سعات حقول ومناجم الموارد على الخريطة وفق كود اللعبة الأصلي
#  (E:\osmanli\game file\lua_src\src\src\app\localtb\config_server\resource.lua)
# ════════════════════════════════════════════════════════════════════

RESOURCE_NODE_CAPACITIES: Dict[int, Dict[int, int]] = {
    # 🪙 1. الذهب (Gold / Mithril) [subType = 1 | outputId = 1001]
    1: {1: 12, 2: 22, 3: 35, 4: 55, 5: 75, 6: 105, 7: 135, 8: 170, 9: 205, 10: 250},
    # 🌾 2. مزارع القمح (Food) [subType = 2 | outputId = 1002]
    2: {1: 126000, 2: 252000, 3: 378000, 4: 504000, 5: 630000, 6: 756000, 7: 882000, 8: 1008000, 9: 1134000, 10: 1260000},
    # 🪵 3. مناشر الخشب (Wood) [subType = 3 | outputId = 1003]
    3: {1: 126000, 2: 252000, 3: 378000, 4: 504000, 5: 630000, 6: 756000, 7: 882000, 8: 1008000, 9: 1134000, 10: 1260000},
    # ⛏️ 4. مناجم الحديد (Iron) [subType = 4 | outputId = 1004]
    4: {1: 21000, 2: 42000, 3: 63000, 4: 84000, 5: 105000, 6: 126000, 7: 147000, 8: 168000, 9: 189000, 10: 210000},
    # 💎 5. مناجم الكوارنز / الفضة (Silver / Mithril) [subType = 5 | outputId = 1005]
    5: {1: 5250, 2: 10500, 3: 15750, 4: 21000, 5: 26250, 6: 31500, 7: 36750, 8: 42000, 9: 47250, 10: 52500},
}

RESOURCE_TYPE_ALIASES: Dict[str, int] = {
    "1": 1, "gold": 1, "ذهب": 1, "الذهب": 1, "mithril": 1,
    "2": 2, "food": 2, "قمح": 2, "القمح": 2, "مزرعة": 2, "مزارع": 2,
    "3": 3, "wood": 3, "خشب": 3, "الخشب": 3, "منشرة": 3, "مناشر": 3,
    "4": 4, "iron": 4, "حديد": 4, "الحديد": 4, "منجم": 4, "مناجم": 4,
    "5": 5, "silver": 5, "فضة": 5, "الفضة": 5, "كوارنز": 5, "الكوارنز": 5, "stone": 5, "حجر": 5, "الحجر": 5, "diamond": 5, "الماس": 5, "ألماس": 5,
}

def get_resource_node_capacity(res_type: int | str, level: int) -> int:
    """
    استرجاع السعة القصوى لحقل المورد على الخريطة وفق كود اللعبة الأصلي (config_server/resource.lua).
    
    :param res_type: نوع المورد (1/gold, 2/food, 3/wood, 4/iron, 5/silver أو المسميات العربية/الإنجليزية).
    :param level: مستوى الحقل (من 1 إلى 10).
    :return: سعة الحقل الإجمالية، أو 0 إذا كان النوع أو المستوى غير صالح.
    """
    sub_type: Optional[int] = None
    if isinstance(res_type, int):
        sub_type = res_type
    elif isinstance(res_type, str):
        sub_type = RESOURCE_TYPE_ALIASES.get(res_type.strip().lower(), None)
        if sub_type is None and res_type.strip().isdigit():
            sub_type = int(res_type.strip())

    if sub_type not in RESOURCE_NODE_CAPACITIES:
        return 0
    return RESOURCE_NODE_CAPACITIES[sub_type].get(int(level), 0)


# ════════════════════════════════════════════════════════════════════
#  الـ interface المشترك لجميع المهام (BaseTask)
# ════════════════════════════════════════════════════════════════════

class BaseTask(ABC):
    """
    الكلاس الأساسي لكل مهمة في مجلد tasks/.

    الاستخدام:
        class GatherTask(BaseTask):
            name = "gather"

            async def run(self) -> TaskResult:
                # منطق الجمع هنا
                return TaskResult.ok("تم إرسال المسيرة")
    """

    #: اسم المهمة (يجب تعريفه في كل subclass)
    name: str = "base"

    def __init__(self, conn: "GameConnection", config: Optional[Dict[str, Any]] = None):
        self.conn   = conn
        self.config = config or {}
        self.email  = conn.account.email
        self.uid    = conn.uid
        self.log    = logging.getLogger(f"task.{self.name}[{self.email}]")

        self._state      : TaskState       = TaskState.IDLE
        self._last_run   : Optional[float] = None   # timestamp
        self._last_result: Optional[TaskResult] = None
        self._run_count  : int             = 0
        self._stop_event : asyncio.Event   = asyncio.Event()

    # ── الواجهة الإلزامية ─────────────────────────────────────────

    @abstractmethod
    async def run(self) -> TaskResult:
        """تنفيذ المهمة مرة واحدة — يجب تنفيذها في كل subclass."""
        ...

    # ── الواجهة الاختيارية ────────────────────────────────────────

    async def on_start(self):
        """يُستدعى مرة واحدة عند أول تشغيل للمهمة (للتهيئة)."""
        pass

    async def on_stop(self):
        """يُستدعى عند الإيقاف الآمن للمهمة."""
        pass

    # ── الإيقاف ───────────────────────────────────────────────────

    async def stop(self):
        """إيقاف المهمة بشكل آمن."""
        self._stop_event.set()
        self._state = TaskState.STOPPED
        await self.on_stop()
        self.log.info(f"🛑 تم إيقاف مهمة [{self.name}]")

    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    @property
    def is_connected(self) -> bool:
        """التحقق هل اتصال السيرفر ما زال نشطاً وقائماً."""
        return self.conn is not None and getattr(self.conn, "is_connected", False)

    async def get_active_marches_count(self, force_sync: bool = False) -> int:
        """حساب عدد الفيالق والمسيرات النشطة حالياً خارج القلعة بالاعتماد على الذاكرة الحية (Zero-Request)."""
        has_local = bool(getattr(self.conn, 'local_queues', None))
        if force_sync and not has_local:
            sync_reason = "force_sync=True (طلب مزامنة إجباري)" if force_sync else "local_queues فارغة في الذاكرة (تهيئة أولى)"
            self.log.info(f"🔄 [QUEUE_SYNC] استعلام مزامنة طوابير الفيالق 1007/1000 من السيرفر | السبب: {sync_reason}")
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
        if getattr(self.conn, 'cached_packets', None):
            for p in self.conn.cached_packets.values():
                if isinstance(p, dict):
                    d = p.get('data', {})
                    if isinstance(d, dict) and d.get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC':
                        nd = d.get('notifyData', [])
                        if isinstance(nd, list):
                            all_queue_data.extend(nd)
            all_queue_data.extend(self.conn.cached_packets.get(202, []))

        queues_to_check = []
        for item in all_queue_data:
            if not isinstance(item, dict):
                if isinstance(item, list):
                    queues_to_check.extend(item)
                continue
            if 'status' in item or 'queueId' in item:
                queues_to_check.append(item)
            elif 'data' in item:
                d = item['data']
                if isinstance(d, list):
                    queues_to_check.extend(d)
                elif isinstance(d, dict):
                    queues_to_check.append(d)

        for q in queues_to_check:
            if isinstance(q, dict) and q.get('status') in (0, 1, 2, 3, 4, 7):
                qid = q.get('id') or q.get('queueId')
                if qid:
                    if qid not in seen_ids:
                        seen_ids.add(qid)
                        active += 1
                else:
                    active += 1
        return active

    async def get_max_marches_capacity(self, allow_network: bool = True) -> int:
        """
        حساب سعة الفيالق والمسيرات القصوى المسموح بها للقلعة بدقة طبقاً لكود اللعبة:
        1. السقف الأساسي لجميع القلاع = 1 (DEFAULT_EXP_ARMY_QUEUE).
        2. أبحاث معهد العلوم (technologyCtrl - EXPEDITION_TROOPS):
           - #24011 (فيلق البعثة I): +1
           - #24017 (فيلق البعثة II): +1
           - #24033 (فيلق البعثة III): +1
           (الحد الأقصى لزيادة الأبحاث = +3).
        3. ميزة الـ VIP (vipCtrl - buffType 30 / MARCH_TROOP_TOTAL_BOOST):
           - المستويات من VIP 4 إلى VIP 9: تمنح +1 طابور مسيرة إضافي.
           - المستويات من VIP 10 إلى VIP 18: تمنح +2 طابور مسيرة إضافي.
        4. مراعاة السقف الأقصى العام للعبة (MAX_MARCH_TROOP = 6) أو التقييد اليدوي في config.max_queues إن وُجد.
        """
        capacity = 1

        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}

        # 1. استخراج بيانات التقنيات مع دعم الذاكرة الحية والحزم المؤقتة والاستعلام الشبكي
        tech_data: Dict[str, Any] = {}
        if isinstance(init_data, dict):
            raw_tech = init_data.get('technologyCtrl')
            if isinstance(raw_tech, dict) and raw_tech:
                tech_data = raw_tech

        if not tech_data and hasattr(self, 'conn') and self.conn:
            cached = getattr(self.conn, 'cached_packets', {})
            resp_cached = cached.get(('1017', '1')) or cached.get(('1017', 1)) or cached.get((1017, 1))
            if isinstance(resp_cached, dict) and resp_cached.get('err') == '0':
                tech_data = resp_cached.get('data', {})

        if not tech_data and allow_network and getattr(self, 'is_connected', False):
            try:
                resp = await self.conn.query('1017', '1', {}, timeout=4)
                if isinstance(resp, dict) and resp.get('err') == '0':
                    tech_data = resp.get('data', {})
                    if isinstance(init_data, dict):
                        init_data['technologyCtrl'] = tech_data
            except Exception:
                pass

        # فحص تقنيات فيالق البعثة العسكرية الثلاثة (24011, 24017, 24033)
        for tid in ('24011', '24017', '24033'):
            val = tech_data.get(tid) if tid in tech_data else tech_data.get(int(tid))
            if val is not None:
                lv = 0
                if isinstance(val, (list, tuple)):
                    if len(val) > 1:
                        try:
                            lv = int(val[1] or 0)
                        except (ValueError, TypeError):
                            lv = 0
                    elif len(val) == 1:
                        try:
                            lv = int(val[0] or 0)
                        except (ValueError, TypeError):
                            lv = 0
                elif isinstance(val, dict):
                    lv = int(val.get('level', val.get('lv', 0)) or 0)
                else:
                    try:
                        lv = int(val or 0)
                    except (ValueError, TypeError):
                        lv = 0
                if lv > 0:
                    capacity += 1

        # 2. احتساب طوابير الـ VIP طبقاً لكود اللعبة (VIP 4..9 -> +1, VIP 10+ -> +2)
        vip_lv = 0
        if isinstance(init_data, dict):
            vip_ctrl = init_data.get('vipCtrl', {})
            if isinstance(vip_ctrl, dict):
                try:
                    vip_lv = int(vip_ctrl.get('vipLv', 0) or 0)
                except (ValueError, TypeError):
                    vip_lv = 0

        if vip_lv >= 10:
            capacity += 2
        elif vip_lv >= 4:
            capacity += 1

        # 3. سقف اللعبة الأقصى 6 مسيرات (MAX_MARCH_TROOP = 6)
        capacity = min(6, max(1, capacity))

        # مراعاة التقييد اليدوي config.max_queues إن وُجد
        if hasattr(self, 'config') and isinstance(self.config, dict):
            cfg_max = self.config.get('max_queues')
            if cfg_max is not None:
                try:
                    c_val = int(cfg_max)
                    if c_val > 0:
                        capacity = min(capacity, c_val)
                except (ValueError, TypeError):
                    pass

        return capacity

    async def get_available_marches_count(self, force_sync: bool = False, allow_network: bool = True) -> int:
        """
        حساب عدد الفيالق المتاحة والشاغرة للإرسال حالياً:
        الفارق بين سعة الفيالق القصوى للقلعة (get_max_marches_capacity)
        وعدد الفيالق النشطة بالخارج حالياً (get_active_marches_count).
        """
        max_cap = await self.get_max_marches_capacity(allow_network=allow_network)
        active = await self.get_active_marches_count(force_sync=force_sync)
        return max(0, max_cap - active)

    async def get_active_gather_resource_types(self, force_sync: bool = False) -> Set[int]:
        """
        فحص أنواع الموارد التي تجمعها مسيرات نشطة بالخارج حالياً (2=قمح, 3=خشب, 4=حديد, 5=فضة, 1=ذهب):
        - قراءة فورية من الذاكرة الحية (Zero-Request) إذا كانت local_queues محملة.
        - استعلام 1007/1000 مشروط فقط إذا كانت الذاكرة خالية تماماً (not has_local).
        """
        has_local = bool(getattr(self.conn, 'local_queues', None))
        if not has_local:
            try:
                await self.conn.query('1007', '1000', {}, timeout=2)
                await asyncio.sleep(0.3)
            except Exception:
                pass

        active: Set[int] = set()
        queues = list(getattr(self.conn, "local_queues", []) or [])
        for q in queues:
            if not isinstance(q, dict) or q.get("status") not in (0, 1, 2, 3, 4, 7):
                continue
            res_sub = None
            for loc_key in ("to", "from"):
                info = q.get(loc_key, {})
                if isinstance(info, dict) and info.get("mapType") == 5:
                    res_sub = info.get("subMapType")
                    if not res_sub:
                        parts = str(info.get("id", "")).split("-")
                        if len(parts) >= 4 and parts[2] == "5" and parts[3].isdigit():
                            res_sub = int(parts[3])
                if res_sub:
                    break
            if not res_sub:
                data_obj = q.get("data", {})
                if isinstance(data_obj, dict):
                    code = data_obj.get("resourceType")
                    if code:
                        res_sub = {1001: 1, 1002: 2, 1003: 3, 1004: 4, 1005: 5}.get(int(code))
            if res_sub and int(res_sub) in (1, 2, 3, 4, 5):
                active.add(int(res_sub))
        return active

    async def _get_active_gather_types(self, force_sync: bool = False) -> Set[int]:
        """اسم بديل للتوافق مع المهام القائمة."""
        return await self.get_active_gather_resource_types(force_sync=force_sync)

    def print_local_queues(self, label: str = "") -> List[Any]:
        """دالة تجريبية لطباعة كامل محتوى local_queues من الذاكرة الحية."""
        conn = getattr(self, "conn", None)
        local_queues = list(getattr(conn, "local_queues", None) or [])
        init_data = getattr(conn, "init_data", None)
        init_queues = init_data.get("local_queues") if isinstance(init_data, dict) else None
        mem_engine = getattr(conn, "memory_engine", None)
        raw_map = getattr(mem_engine, "local_queues_map", None)
        synced = getattr(mem_engine, "local_queues_synced", None)

        payload = {
            "label": label or self.name,
            "uid": self.uid,
            "synced": synced,
            "conn_local_queues_count": len(local_queues),
            "conn_local_queues": local_queues,
            "init_data_local_queues": init_queues,
            "local_queues_map_count": len(raw_map) if isinstance(raw_map, dict) else None,
            "local_queues_map": raw_map,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        header = f"\n===== [local_queues dump | {self.email} | {label or self.name}] ====="
        footer = "=" * len(header.strip())
        print(f"{header}\n{text}\n{footer}", flush=True)
        return local_queues

    def get_lord_stamina(self) -> int:
        """
        جلب رصيد طاقة اللورد الحالي من بيانات القلعة المحملة بالذاكرة الحية (Zero-Request / 0ms):
        lordInfoCtrl -> base -> health
        أو loginDataInitCtrl -> base -> health
        """
        try:
            if not hasattr(self, 'conn') or not self.conn or not getattr(self.conn, 'init_data', None):
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

    def _get_lord_stamina(self) -> int:
        """اسم بديل للتوافق مع المهام القائمة."""
        return self.get_lord_stamina()

    def get_resource_capacity(self, res_type: int | str, level: int) -> int:
        """
        استرجاع سعة حقل المورد الإجمالية وفق كود اللعبة الأصلي (resource.lua).
        متاح لكافة المهام المشتقة من BaseTask.
        """
        return get_resource_node_capacity(res_type, level)

    def get_castle_level(self) -> int:
        """
        استخراج المستوى الحقيقي للقلعة (Castle Level - bid 101) من بيانات الذاكرة الحية (Zero-Request / 0ms):
        cityCtrl -> blist -> bid == 101 -> lv
        """
        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}
        city_ctrl = init_data.get("cityCtrl", {}) if isinstance(init_data, dict) else {}
        blist = city_ctrl.get("blist", []) if isinstance(city_ctrl, dict) else []
        castle_lv = 1
        for b in blist:
            if isinstance(b, dict):
                binfo = b.get("binfo", b)
                if isinstance(binfo, dict) and str(binfo.get("bid", "")) == "101":
                    try:
                        castle_lv = max(castle_lv, int(binfo.get("lv", 1)))
                    except Exception:
                        pass
        return castle_lv

    def _get_castle_level(self) -> int:
        """اسم بديل للتوافق مع المهام القائمة."""
        return self.get_castle_level()

    def get_prestige_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]:
        """
        جلب تفاصيل وحالة مهمة الهيبة اليومية من الذاكرة الحية (Zero-Request / 0ms):
        - يبحث في meritoriousTaskCtrl -> taskData أو tasks أو daily_task
        - يعيد dict موحد:
          {"found": bool, "task_id": int, "c_num": int, "l_num": int, "status": int, "is_done": bool, "remaining": int}
        """
        qid = quest_key_or_id if isinstance(quest_key_or_id, int) else PRESTIGE_QUEST_IDS.get(str(quest_key_or_id).strip().lower(), 0)
        merit_ctrl = getattr(self.conn, 'init_data', {}).get("meritoriousTaskCtrl", {}) if hasattr(self, 'conn') and self.conn else {}
        if not isinstance(merit_ctrl, dict):
            return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "status": 0, "is_done": False, "remaining": 0}

        # 1. فحص taskData (القاموس الأساسي لمهام الهيبة اليومية)
        task_data = merit_ctrl.get("taskData", {})
        if isinstance(task_data, dict) and str(qid) in task_data:
            t = task_data[str(qid)]
            if isinstance(t, dict):
                c = int(t.get("cNum", t.get("c_num", 0)))
                l = int(t.get("lNum", t.get("l_num", 0)))
                s = int(t.get("status", 0))
                is_done = (s == 4) or (l > 0 and c >= l)
                remaining = max(0, l - c) if l > 0 else 0
                return {"found": True, "task_id": qid, "c_num": c, "l_num": l, "status": s,
                        "is_done": is_done, "remaining": remaining}

        # 2. فحص قائمة tasks
        tasks = merit_ctrl.get("tasks", [])
        if isinstance(tasks, dict):
            tasks = list(tasks.values())
        if isinstance(tasks, list):
            for t in tasks:
                if isinstance(t, dict):
                    t_id = t.get("id") or t.get("taskId")
                    if t_id and int(t_id) == qid:
                        c = int(t.get("cNum", t.get("c_num", 0)))
                        l = int(t.get("lNum", t.get("l_num", 0)))
                        s = int(t.get("status", t.get("is_finish", 0)))
                        is_done = (s in (1, 4)) or (l > 0 and c >= l)
                        remaining = max(0, l - c) if l > 0 else 0
                        return {"found": True, "task_id": qid, "c_num": c, "l_num": l, "status": s,
                                "is_done": is_done, "remaining": remaining}

        # 3. فحص daily_task (العدادات اليومية)
        daily_task = merit_ctrl.get("daily_task", {})
        if isinstance(daily_task, dict) and str(qid) in daily_task:
            c = int(daily_task[str(qid)])
            return {"found": True, "task_id": qid, "c_num": c, "l_num": 1, "status": 4 if c >= 1 else 0,
                    "is_done": c >= 1, "remaining": 0 if c >= 1 else 1}

        return {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "status": 0, "is_done": False, "remaining": 0}

    def _get_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]:
        """اسم بديل للتوافق مع المهام القائمة."""
        return self.get_prestige_quest_info(quest_key_or_id)

    async def refresh_prestige_data(self, force: bool = False, min_interval: float = 30.0) -> bool:
        """
        تحديث بيانات مهام الهيبة اليومية (meritoriousTaskCtrl) من السيرفر:
        - قراءة فورية من الذاكرة الحية إذا كانت البيانات حديثة (Zero-Request).
        - استعلام 1000/1 (CMD_LOGIN_DATA_INIT) المعتمد بروتوكولياً إذا طُلب force=True أو انقضت min_interval ثانية.
        """
        if not hasattr(self, 'conn') or not self.conn or not getattr(self.conn, 'is_connected', False):
            return False

        now = time.time()
        last_sync = getattr(self.conn, '_last_merit_sync_time', 0.0)
        has_merit = "meritoriousTaskCtrl" in getattr(self.conn, 'init_data', {})

        if not force and has_merit and (now - last_sync < min_interval):
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
                        setattr(self.conn, '_last_merit_sync_time', now)
                        return True
        except Exception as e:
            if hasattr(self, 'log'):
                self.log.debug(f"استعلام 1000/1 لتجديد مهام الهيبة: {e}")

        return has_merit

    async def _refresh_merit_data(self, force: bool = False) -> bool:
        """اسم بديل للتوافق مع المهام القائمة."""
        return await self.refresh_prestige_data(force=force)

    async def get_castle_coords(self, allow_network: bool = True) -> Tuple[int, int]:
        """
        جلب إحداثيات القلعة (x, y) المركزية بأعلى سرعة وأمان:
        1. من إعدادات المهمة config (center_x/center_y أو x/y) إن حُددت.
        2. من الذاكرة الحية (cityCtrl -> cinfo -> pos) بسرعة 0ms (Zero-Request).
        3. مسار احتياطي عبر استعلام 1006/25 (REQ_GET_CASTLE_MAP_INFO) في حال عدم توفرها بالذاكرة.
        """
        # 1. فحص الإعدادات المباشرة للمهمة
        if isinstance(getattr(self, 'config', None), dict):
            cx = self.config.get('center_x') if self.config.get('center_x') is not None else self.config.get('x')
            cy = self.config.get('center_y') if self.config.get('center_y') is not None else self.config.get('y')
            if cx is not None and cy is not None:
                try:
                    return int(cx), int(cy)
                except (ValueError, TypeError):
                    pass

        # 2. فحص الذاكرة الحية (0ms)
        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}
        if isinstance(init_data, dict):
            pos = init_data.get('cityCtrl', {}).get('cinfo', {}).get('pos', {})
            if isinstance(pos, dict) and 'x' in pos and 'y' in pos:
                try:
                    return int(pos['x']), int(pos['y'])
                except (ValueError, TypeError):
                    pass

        # 3. مسار احتياطي شبكي عبر استعلام 1006/25
        if allow_network and self.conn and getattr(self.conn, 'is_connected', False):
            try:
                uid_val = getattr(self, 'uid', 0)
                uid_int = int(uid_val) if str(uid_val).isdigit() else uid_val
                r_castle = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=3.0)
                if r_castle and isinstance(r_castle, dict):
                    ret_data = r_castle.get('retData', {})
                    if isinstance(ret_data, dict) and 'x' in ret_data and 'y' in ret_data:
                        cx, cy = int(ret_data['x']), int(ret_data['y'])
                        # حفظها بالذاكرة الحية لتجنب تكرار الطلب مستقبلاً
                        if isinstance(init_data, dict):
                            init_data.setdefault('cityCtrl', {}).setdefault('cinfo', {})['pos'] = {"x": cx, "y": cy}
                        return cx, cy
            except Exception as e:
                self.log.debug(f"استعلام إحداثيات القلعة 1006/25: {e}")

        return 0, 0

    async def get_kingdom_id(self, allow_network: bool = True) -> int:
        """
        جلب معرف المملكة (kingdom_id / partition) بدقة وسرعة:
        1. من كائن الاتصال self.conn.kingdom_id إذا تم تعيينه مسبقاً (0ms).
        2. من الذاكرة الحية (lordInfoCtrl -> base -> partition) بسرعة 0ms (Zero-Request).
        3. مسار احتياطي عبر استعلام 1002/7 (REQ_USER_INFO) في حال عدم توفره بالذاكرة.
        """
        # 1. فحص كائن الاتصال
        kid = getattr(self.conn, 'kingdom_id', None)
        if kid and str(kid).isdigit() and int(kid) > 0:
            return int(kid)

        # 2. فحص الذاكرة الحية lordInfoCtrl (0ms)
        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}
        if isinstance(init_data, dict):
            lord_ctrl = init_data.get('lordInfoCtrl', {})
            if isinstance(lord_ctrl, dict):
                part = (
                    lord_ctrl.get('base', {}).get('partition')
                    or lord_ctrl.get('partition')
                    or lord_ctrl.get('kingdomId')
                )
                if part and str(part).isdigit() and int(part) > 0:
                    kid_val = int(part)
                    if hasattr(self.conn, 'kingdom_id'):
                        try:
                            self.conn.kingdom_id = kid_val
                        except Exception:
                            pass
                    return kid_val

        # 3. مسار احتياطي شبكي عبر استعلام 1002/7
        if allow_network and self.conn and getattr(self.conn, 'is_connected', False):
            try:
                uid_val = getattr(self, 'uid', 0)
                uid_int = int(uid_val) if str(uid_val).isdigit() else uid_val
                r_player = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=3.0)
                if r_player and isinstance(r_player, dict):
                    part = r_player.get('data', {}).get('base', {}).get('partition')
                    if part and str(part).isdigit() and int(part) > 0:
                        kid_val = int(part)
                        if hasattr(self.conn, 'kingdom_id'):
                            try:
                                self.conn.kingdom_id = kid_val
                            except Exception:
                                pass
                        return kid_val
            except Exception as e:
                self.log.debug(f"استعلام معرف المملكة 1002/7: {e}")

        return int(kid) if (kid and str(kid).isdigit()) else 0

    async def get_available_troops(
        self,
        exclude_used: Optional[Dict[int, int]] = None,
        allow_network: bool = True
    ) -> Dict[int, int]:
        """
        جلب القوات المتوفرة بالقلعة والجاهزة للمسيرات (غير المشغولة):
        1. قراءة totalArmy من الذاكرة الحية (armyCtrl -> totalArmy) بسرعة 0ms (Zero-Request).
        2. استبعاد فخاخ الجدار (800-899) تلقائياً والإبقاء على القوات القتالية فقط.
        3. مسار احتياطي عبر استعلام 1005/1 (REQ_GET_ARMY_INFO) في حال عدم توفر القوات بالذاكرة.
        4. خصم القوات المحجوزة تلقائياً من self._used_army أو المعطاة في exclude_used.
        """
        available: Dict[int, int] = {}

        # 1. القراءة من الذاكرة الحية (0ms)
        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}
        if isinstance(init_data, dict):
            army_ctrl = init_data.get('armyCtrl', {})
            if isinstance(army_ctrl, dict):
                for k, v in army_ctrl.get('totalArmy', {}).items():
                    if str(k).isdigit() and str(v).isdigit():
                        tid, cnt = int(k), int(v)
                        # استبعاد فخاخ الجدار (800-899)
                        if not (800 <= tid < 900) and cnt > 0:
                            available[tid] = cnt

        # 2. مسار احتياطي شبكي عبر استعلام 1005/1
        if not available and allow_network and self.conn and getattr(self.conn, 'is_connected', False):
            try:
                r_army = await self.conn.query('1005', '1', {}, timeout=3.0)
                if r_army and isinstance(r_army, dict):
                    data = r_army.get('data', {})
                    if isinstance(data, dict):
                        raw_total = data.get('totalArmy', {})
                        if isinstance(raw_total, dict):
                            if isinstance(init_data, dict):
                                init_data.setdefault('armyCtrl', {})['totalArmy'] = raw_total
                            for k, v in raw_total.items():
                                if str(k).isdigit() and str(v).isdigit():
                                    tid, cnt = int(k), int(v)
                                    if not (800 <= tid < 900) and cnt > 0:
                                        available[tid] = cnt
            except Exception as e:
                self.log.debug(f"استعلام قوات القلعة 1005/1: {e}")

        # 3. خصم القوات المشغولة في المسيرات
        used_map: Dict[int, int] = {}
        if isinstance(exclude_used, dict):
            used_map.update(exclude_used)
        elif hasattr(self, '_used_army') and isinstance(self._used_army, dict):
            used_map.update(self._used_army)

        for tid, used_cnt in used_map.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used_cnt)

        return available

    async def get_formation(
        self,
        formation_id: int = 1,
        allow_network: bool = True
    ) -> Tuple[List[Any], List[Any], List[Any], Dict[str, Any]]:
        """
        جلب بيانات التشكيلة المحفوظة (أبطال، حيوانات، رونات، جيش) بدقة وسرعة:
        1. من الذاكرة الحية armyCtrl (compileHeros, compilePets, compileRunePages, compileArmy) بسرعة 0ms (Zero-Request).
        2. مسار احتياطي عبر استعلام 1005/7 في حال عدم توفر التشكيلة بالذاكرة الحية.
        """
        form_heroes: List[Any] = []
        form_pets: List[Any] = []
        form_rune_pages: List[Any] = []
        form_army_dict: Dict[str, Any] = {}

        if not formation_id or formation_id <= 0:
            return form_heroes, form_pets, form_rune_pages, form_army_dict

        fid_str = str(formation_id)
        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}
        if isinstance(init_data, dict):
            army_ctrl = init_data.get('armyCtrl', {})
            if isinstance(army_ctrl, dict):
                c_heroes = army_ctrl.get('compileHeros', {})
                if isinstance(c_heroes, dict) and fid_str in c_heroes:
                    form_heroes = c_heroes[fid_str]

                c_pets = army_ctrl.get('compilePets', {})
                if isinstance(c_pets, dict) and fid_str in c_pets:
                    form_pets = c_pets[fid_str]

                c_runes = army_ctrl.get('compileRunePages', {})
                if isinstance(c_runes, dict) and fid_str in c_runes:
                    form_rune_pages = c_runes[fid_str]

                c_army = army_ctrl.get('compileArmy', {})
                if isinstance(c_army, dict) and fid_str in c_army:
                    form_army_dict = c_army[fid_str]

        # مسار احتياطي عبر استعلام 1005/7 إذا كانت فارغة بالذاكرة
        if not form_heroes and not form_army_dict and allow_network and self.conn and getattr(self.conn, 'is_connected', False):
            try:
                r_form = await self.conn.query('1005', '7', {"compiletype": formation_id}, timeout=3.0)
                if r_form and isinstance(r_form, dict) and 'data' in r_form:
                    f_data = r_form['data']
                    form_heroes     = f_data.get('compileHeros', [])
                    form_pets       = f_data.get('compilePets', [])
                    form_rune_pages = f_data.get('compileRunePages', [1])
                    form_army_dict  = f_data.get('compileArmy', {})
            except Exception as e:
                self.log.debug(f"استعلام التشكيلة 1005/7: {e}")

        clean_runes = self.get_rune_pages(form_rune_pages)
        return form_heroes, form_pets, clean_runes, form_army_dict

    def get_rune_pages(self, form_rune_pages: Optional[Any] = None) -> List[int]:
        """
        استخراج وتنظيف صفحات الرونات (Rune Pages) المطلوبة لأمر المسير (1007/2):
        1. إذا كانت قائمة: استخراج الأرقام الصالحة منها.
        2. إذا كانت قاموساً: استخراج أول قيمة عددية صالحة منه.
        3. إذا كانت رقماً منفرداً: تحويله إلى قائمة [int].
        4. في حال خلوها أو فشل الاستخراج: إعادة القيمة الافتراضية القياسية [1] لمنع رفض السيرفر.
        """
        if isinstance(form_rune_pages, list) and form_rune_pages:
            res = [int(x) for x in form_rune_pages if str(x).isdigit() and int(x) > 0]
            if res:
                return res

        if isinstance(form_rune_pages, dict) and form_rune_pages:
            for v in form_rune_pages.values():
                if isinstance(v, list) and v:
                    res = [int(x) for x in v if str(x).isdigit() and int(x) > 0]
                    if res:
                        return res
                elif str(v).isdigit() and int(v) > 0:
                    return [int(v)]

        if form_rune_pages is not None and str(form_rune_pages).isdigit() and int(form_rune_pages) > 0:
            return [int(form_rune_pages)]

        return [1]

    async def get_combat_heroes(
        self,
        form_heroes: Optional[Any] = None,
        max_count: int = 2,
        exclude_busy: Optional[Set[int]] = None
    ) -> List[int]:
        """
        فحص أبطال التشكيلة واستبدال المشغولين منهم بأفضل أبطال قتال وهجوم متاحين:
        1. فحص أبطال التشكيلة (form_heroes): هل هم متوفرون بالقلعة (state == 0) وغير محجوزين؟
        2. إذا كان أي منهم مشغولاً أو ناقصاً:
           - اختيار أفضل أبطال قتال وحرب (5501xxx) يمتلكون مهارات قتالية وهجومية نشطة (5610xxx / 5640xxx).
           - الأولوية للأعلى مستوى ونجوماً (lv * 10 + star * 50).
           - استبعاد أبطال الجمع (5502xxx) وأبطال الدعم (5503xxx) تماماً من القتال.
        """
        # 1. تجميع قائمة المشغولين
        busy: Set[int] = set()
        if isinstance(exclude_busy, (set, list, tuple)):
            busy.update(int(x) for x in exclude_busy if str(x).isdigit())
        if hasattr(self, '_busy') and isinstance(self._busy, (set, list)):
            busy.update(int(x) for x in self._busy if str(x).isdigit())

        # 2. جلب بيانات أبطال الحساب
        account_heroes: List[Dict[str, Any]] = []
        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}
        if isinstance(init_data, dict):
            h_ctrl = init_data.get('heroCtrl')
            if isinstance(h_ctrl, list):
                account_heroes = h_ctrl
            elif isinstance(h_ctrl, dict):
                account_heroes = list(h_ctrl.values())

        if not account_heroes and hasattr(self, '_heroes') and isinstance(self._heroes, list):
            account_heroes = self._heroes

        # في حال لم تكن محملة بالذاكرة بعد، محاولة جلبها من GateClient
        if not account_heroes and self.conn and hasattr(self.conn, '_gate') and self.conn._gate:
            gate_heroes = getattr(self.conn._gate, 'heroes', None)
            if isinstance(gate_heroes, list) and gate_heroes:
                account_heroes = gate_heroes

        # خريطة سريعة للأبطال لتسهيل الفحص بالـ ID (0ms)
        hero_map: Dict[int, Dict[str, Any]] = {}
        for h in account_heroes:
            if isinstance(h, dict) and h.get('id') and str(h['id']).isdigit():
                hero_map[int(h['id'])] = h

        chosen_heroes: List[int] = []

        # 3. فحص أبطال التشكيلة المعطاة (form_heroes)
        if form_heroes:
            flat_form: List[int] = []
            if isinstance(form_heroes, list):
                for item in form_heroes:
                    if isinstance(item, list):
                        flat_form.extend([int(x) for x in item if str(x).isdigit()])
                    elif str(item).isdigit():
                        flat_form.append(int(item))
            elif isinstance(form_heroes, dict):
                for val in form_heroes.values():
                    if isinstance(val, list):
                        flat_form.extend([int(x) for x in val if str(x).isdigit()])
                    elif str(val).isdigit():
                        flat_form.append(int(val))

            for hid in flat_form:
                if hid in busy or hid in chosen_heroes:
                    continue
                h_data = hero_map.get(hid)
                # فحص حالة البطل: state == 0 تعني متاح وغير مشغول بمسيرة أو تكليف
                if h_data:
                    state = h_data.get('status', {}).get('state', 0)
                    if state == 0:
                        chosen_heroes.append(hid)
                        busy.add(hid)
                else:
                    # إذا لم يتوفر كائن البطل بالذاكرة، اعتماده إذا لم يكن مشغولاً
                    chosen_heroes.append(hid)
                    busy.add(hid)

                if len(chosen_heroes) >= max_count:
                    break

        # 4. إذا اكتمل العدد من التشكيلة، إرجاعهم مباشرة
        if len(chosen_heroes) >= max_count:
            return chosen_heroes[:max_count]

        # 5. استبدال المشغولين أو إكمال النقص بأبطال قتال وهجوم يمتلكون مهارات حربية
        tier1: List[Tuple[int, int]] = []  # 5501 حرب + مهارات قتال وهجوم (5610 / 5640)
        tier2: List[Tuple[int, int]] = []  # 5501 حرب متاح
        tier3: List[Tuple[int, int]] = []  # أبطال آخرون متاحون

        for h in account_heroes:
            if not isinstance(h, dict):
                continue
            hid_raw = h.get('id')
            if not hid_raw or not str(hid_raw).isdigit():
                continue
            hid = int(hid_raw)
            if hid in busy or hid in chosen_heroes:
                continue

            # استبعاد المشغولين حتماً
            state = h.get('status', {}).get('state', 0)
            if state != 0:
                continue

            hid_str = str(hid)
            # استبعاد أبطال الجمع 5502 والدعم 5503 من مسيرات القتال
            if hid_str.startswith('5502') or hid_str.startswith('5503'):
                continue

            # فحص مهارات القتال والهجوم (5610xxx / 5640xxx)
            skills = h.get('skillList', {})
            has_combat_skills = False
            if isinstance(skills, dict):
                has_combat_skills = any(
                    str(s.get('id', '')).startswith('5610') or str(s.get('id', '')).startswith('5640')
                    for s in skills.values() if isinstance(s, dict)
                )

            lv = int(h.get('lv', 1) or 1)
            star = int(h.get('star', 1) or 1)
            score = lv * 10 + star * 50

            if hid_str.startswith('5501'):
                if has_combat_skills:
                    tier1.append((hid, score))
                else:
                    tier2.append((hid, score))
            else:
                tier3.append((hid, score))

        tier1.sort(key=lambda x: x[1], reverse=True)
        tier2.sort(key=lambda x: x[1], reverse=True)
        tier3.sort(key=lambda x: x[1], reverse=True)

        for hid, _ in tier1 + tier2 + tier3:
            chosen_heroes.append(hid)
            busy.add(hid)
            if len(chosen_heroes) >= max_count:
                break

        # خطة طوارئ أخيرة: أي بطل متاح في القلعة في حال خلو الحساب من أبطال حرب
        if len(chosen_heroes) < max_count:
            for h in account_heroes:
                if isinstance(h, dict):
                    hid_raw = h.get('id')
                    if hid_raw and str(hid_raw).isdigit():
                        hid = int(hid_raw)
                        if hid not in busy and hid not in chosen_heroes:
                            if h.get('status', {}).get('state', 0) == 0:
                                chosen_heroes.append(hid)
                                busy.add(hid)
                                if len(chosen_heroes) >= max_count:
                                    break

        return chosen_heroes[:max_count]

    async def select_combat_pet(self, exclude_busy: Optional[Set[int]] = None) -> List[int]:
        """
        اختيار أفضل حيوان قتالي متاح في القلعة عند عدم وجود حيوان في التشكيلة:
        1. قراءة بيانات الحيوانات من الذاكرة الحية petCtrl.pets بسرعة 0ms (Zero-Request).
        2. استبعاد الحيوانات المشغولة أو المحجوزة في exclude_busy أو self._used_pets.
        3. ترتيب الحيوانات تنازلياً وفق:
           - الرتبة والتطور (step) أولاً
           - المستوى (lv) ثانياً
           - نقاط الخبرة (exp) ثالثاً
        4. تسجيل الحيوان المختار في self._used_pets لمنع تكرار إرساله بالفيالق المتتالية.
        5. إرجاع قائمة [chosen_pet_id] أو [] إذا لم يتوفر أي حيوان.
        """
        busy: Set[int] = set()
        if isinstance(exclude_busy, (set, list, tuple)):
            busy.update(int(x) for x in exclude_busy if str(x).isdigit())
        if hasattr(self, '_used_pets') and isinstance(self._used_pets, (set, list)):
            busy.update(int(x) for x in self._used_pets if str(x).isdigit())

        init_data = getattr(self.conn, 'init_data', {}) if hasattr(self, 'conn') and self.conn else {}
        pets_data = init_data.get('petCtrl', {}).get('pets', {}) if isinstance(init_data, dict) else {}
        if not isinstance(pets_data, dict) or not pets_data:
            return []

        available_pets = []
        for pid_raw, pinfo in pets_data.items():
            if not isinstance(pinfo, dict):
                continue
            try:
                pid = int(pinfo.get('id', pid_raw))
                if pid <= 0 or pid in busy:
                    continue
                step = int(pinfo.get('step', 1) or 1)
                lv   = int(pinfo.get('lv', 1) or 1)
                exp  = int(pinfo.get('exp', 0) or 0)
                available_pets.append((pid, step, lv, exp))
            except Exception:
                continue

        if not available_pets:
            return []

        # الترتيب: الرتبة (step) ثم المستوى (lv) ثم الخبرة (exp) تنازلياً
        available_pets.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
        chosen_pet = available_pets[0][0]

        # تحديث قائمة الحيوانات المحجوزة للمهمة
        if hasattr(self, '_used_pets') and isinstance(self._used_pets, set):
            self._used_pets.add(chosen_pet)
        elif hasattr(self, '_used_pets') and isinstance(self._used_pets, list):
            self._used_pets.append(chosen_pet)

        best_step = available_pets[0][1]
        best_lv = available_pets[0][2]
        self.log.info(f"🐾 [حيوان بديل] تم اختيار الحيوان #{chosen_pet} (رتبة {best_step} | لفل {best_lv}) لغيابه عن التشكيلة.")
        return [chosen_pet]

    async def get_march_army(
        self,
        form_army_dict: Optional[Dict[str, Any]] = None,
        formation_id: int = 1,
        available_troops: Optional[Dict[int, int]] = None,
        fallback_count: int = 0,
        max_capacity: Optional[int] = None
    ) -> List[Dict[str, int]]:
        """
        تجهيز جيش المسيرة بدقة صارمة وفق التشكيلة المحددة:
        1. الالتزام الصارم بعدد جنود التشكيلة وعدم زيادة أي جندي من تلقاء النفس.
        2. جلب كل صنف من أصناف التشكيلة وفق رقمه المحدد بالضبط.
        3. في حال وجود نقص في أي صنف، يتم تعويض النقص بما يعادل القوة القتالية المفقودة
           (لا بالعدد الحرفي) من أفضل القوات القتالية المتوفرة، دون أي زيادة فوق السقف.
        4. استبعاد فخاخ الجدار (800-899) تلقائياً لمنع خطأ 8062.
        """
        # 1. القوات المتاحة بالقلعة
        available: Dict[int, int] = {}
        if isinstance(available_troops, dict):
            available = {int(k): int(v) for k, v in available_troops.items() if not (800 <= int(k) < 900) and int(v) > 0}
        else:
            available = await self.get_available_troops()

        # 2. جلب تشكيلة الجيش إن لم تُمرر مباشرة
        target_form: Dict[int, int] = {}
        raw_form = form_army_dict
        if (not raw_form or not isinstance(raw_form, dict)) and formation_id > 0:
            _, _, _, raw_form = await self.get_formation(formation_id)

        if isinstance(raw_form, dict):
            for k, v in raw_form.items():
                if str(k).isdigit() and str(v).isdigit():
                    tid = int(k)
                    cnt = int(v)
                    # استبعاد فخاخ الجدار 800-899
                    if not (800 <= tid < 900) and cnt > 0:
                        target_form[tid] = cnt

        # في حال عدم وجود تشكيلة نهائياً، استخدام خطة الاحتياط المحددة بـ fallback_count
        if not target_form:
            if fallback_count > 0:
                needed = fallback_count
                if max_capacity and max_capacity > 0:
                    needed = min(needed, max_capacity)
                return self._pick_balanced_combat_troops(available, needed_power=float(needed), cap=needed)
            return []

        # 3. حساب إجمالي جنود التشكيلة المطلوب (سقف صارم لا يمكن تجاوزه)
        target_total = sum(target_form.values())

        # صمام أمان السقف الأقصى لسعة مسيرة اللورد (إن حُددت وكانت التشكيلة أكبر منها)
        scale = 1.0
        if max_capacity and max_capacity > 0 and target_total > max_capacity:
            scale = float(max_capacity) / float(target_total)
            target_total = max_capacity
            self.log.info(
                f"🛡️ جنود التشكيلة ({sum(target_form.values()):,}) يتجاوزون سعة مسيرة اللورد ({max_capacity:,}) — "
                f"تم ضبط السقف لـ {target_total:,} جندي لمنع خطأ 8035"
            )

        # 4. جلب جنود التشكيلة المطلوبين بالضبط وحساب القوة القتالية المفقودة
        army_map: Dict[int, int] = {}
        lost_power = 0.0

        for tid, req_raw in target_form.items():
            req = max(1, int(req_raw * scale)) if scale < 1.0 else req_raw
            avail = available.get(tid, 0)
            take = min(req, avail)
            if take > 0:
                army_map[tid] = army_map.get(tid, 0) + take
                available[tid] -= take

            if take < req:
                lost_power += (req - take) * self._get_unit_combat_power(tid)

        # 5. تعويض النقص بما يعادل القوة القتالية المفقودة (لا العدد الحرفي)
        if lost_power > 0.5:
            army_so_far  = sum(army_map.values())
            comp_cap     = target_total - army_so_far   # لا تتجاوز السقف الكلي
            self.log.info(
                f"ℹ️ قوة قتالية مفقودة من التشكيلة ≈ {lost_power:.1f} — "
                f"جاري التعويض بقوات مكافئة (سقف {comp_cap:,} جندي، موجود قبل التعويض: {army_so_far:,})..."
            )
            compensation = self._pick_balanced_combat_troops(available, needed_power=lost_power, cap=comp_cap)
            for item in compensation:
                c_tid = item['id']
                c_num = item['num']
                if c_num > 0:
                    army_map[c_tid] = army_map.get(c_tid, 0) + c_num

        # 6. صمام أمان رياضي نهائي: ضمان ألا يتجاوز المجموع النهائي target_total تحت أي ظرف
        final_total = sum(army_map.values())
        if final_total > target_total:
            excess = final_total - target_total
            for tid in sorted(army_map.keys(), reverse=True):
                if excess <= 0:
                    break
                trim = min(excess, army_map[tid])
                if trim > 0:
                    army_map[tid] -= trim
                    available[tid] = available.get(tid, 0) + trim
                    excess -= trim

        # 7. فحص القوة القتالية الفعلية مقابل 50% من قوة التشكيلة المطلوبة
        target_power = sum(
            (max(1, int(req * scale)) if scale < 1.0 else req) * self._get_unit_combat_power(tid)
            for tid, req in target_form.items()
        )
        actual_power = sum(
            count * self._get_unit_combat_power(tid)
            for tid, count in army_map.items() if count > 0
        )
        actual_pct = (actual_power / target_power * 100) if target_power > 0 else 0
        if target_power > 0 and actual_power < target_power * 0.5:
            self.log.warning(
                f"⚠️ [ضعيف_الجيش] نفدت القوات — الجيش المتاح ({actual_power:.0f} قوة = {actual_pct:.0f}%) "
                f"أقل من 50% من قوة التشكيلة ({target_power:.0f}) — رفض الإرسال."
            )
            raise RuntimeError(
                f"WEAK_ARMY: قوة الجيش ({actual_power:.0f} = {actual_pct:.0f}%) دون 50% من التشكيلة ({target_power:.0f})"
            )

        # تحديث القوات المحجوزة في self._used_army لتتبع المسيرات المتتالية
        if hasattr(self, '_used_army') and isinstance(self._used_army, dict):
            for tid, count in army_map.items():
                if count > 0:
                    self._used_army[tid] = self._used_army.get(tid, 0) + count

        return [{"id": tid, "num": num} for tid, num in army_map.items() if num > 0]

    def _get_unit_combat_power(self, tid: int) -> float:
        """قوة القتال لكل جندي حسب نوعه ورتبته (tid % 100 = الرتبة)."""
        rank = (tid % 100) * 0.05
        if 400 <= tid < 500:
            return 1.00 + rank   # مشاة
        if 500 <= tid < 600:
            return 1.10 + rank   # فرسان (أقوى بطبيعتهم)
        if 600 <= tid < 700:
            return 1.00 + rank   # رماة
        if 700 <= tid < 800:
            return 0.50 + rank   # عربات حصار
        return 0.50

    def _pick_balanced_combat_troops(
        self,
        available: Dict[int, int],
        needed_power: float,
        cap: int = 0,
    ) -> List[Dict[str, int]]:
        """
        اختيار قوات قتالية متوازنة بما يعادل needed_power قوة قتالية بالضبط.
        cap: سقف اختياري لعدد الجنود الكلي (0 = لا سقف).
        الأولوية: مشاة ← فرسان ← رماة ← عربات (بالرتبة الأعلى أولاً).
        """
        if needed_power <= 0 or not available:
            return []

        infantry, cavalry, archers, carts = [], [], [], []
        for tid, count in available.items():
            if count <= 0 or (800 <= tid < 900):
                continue
            if 400 <= tid < 500:
                infantry.append((tid, count))
            elif 500 <= tid < 600:
                cavalry.append((tid, count))
            elif 600 <= tid < 700:
                archers.append((tid, count))
            elif 700 <= tid < 800:
                carts.append((tid, count))

        for lst in (infantry, cavalry, archers, carts):
            lst.sort(key=lambda x: x[0], reverse=True)

        combat_branches = [b for b in [infantry, cavalry, archers] if b]
        if not combat_branches:
            combat_branches = [carts] if carts else []
        if not combat_branches:
            return []

        army_map: Dict[int, int] = {}
        remaining_power = needed_power

        # جولة 1: توزيع متساوٍ بالقوة بين الأصناف
        branch_power = remaining_power / len(combat_branches)
        for branch in combat_branches:
            bp_left = branch_power
            for tid, _count in branch:
                if bp_left <= 0 or remaining_power <= 0:
                    break
                avail = available.get(tid, 0)
                if avail <= 0:
                    continue
                unit_pow = self._get_unit_combat_power(tid)
                max_take_by_power = int(min(bp_left, remaining_power) / unit_pow)
                if cap > 0:
                    taken_so_far = sum(army_map.values())
                    max_take_by_power = min(max_take_by_power, cap - taken_so_far)
                take = min(avail, max_take_by_power)
                if take <= 0:
                    continue
                army_map[tid] = army_map.get(tid, 0) + take
                available[tid] -= take
                power_taken = take * unit_pow
                bp_left        -= power_taken
                remaining_power -= power_taken

        # جولة 2: استكمال أي فجوة قوة متبقية
        if remaining_power > 0.5:
            all_branches = combat_branches + ([carts] if carts else [])
            for branch in all_branches:
                for tid, _count in branch:
                    if remaining_power <= 0:
                        break
                    avail = available.get(tid, 0)
                    if avail <= 0:
                        continue
                    unit_pow = self._get_unit_combat_power(tid)
                    max_take = int(remaining_power / unit_pow)
                    if cap > 0:
                        taken_so_far = sum(army_map.values())
                        max_take = min(max_take, cap - taken_so_far)
                    take = min(avail, max_take)
                    if take <= 0:
                        continue
                    army_map[tid] = army_map.get(tid, 0) + take
                    available[tid] -= take
                    remaining_power -= take * unit_pow
                if remaining_power <= 0:
                    break

        return [{"id": tid, "num": num} for tid, num in army_map.items() if num > 0]

    async def check_target_busy_or_marched(
        self,
        target_id: Any,
        tx: int,
        ty: int,
        kingdom_id: int = 0,
        is_stronghold: bool = False
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        فحص أمني دقيق وشامل ومباشر للهدف (مورد أو معقل) على الخريطة قبل إرسال المسيرة:
        1. فحص استعلام 1006/22 المباشر (currentCollectNum, collectSpeed, marchId, remainSourceNum).
        2. مزامنة الخريطة 1006/1000 واعتراض إشعارات 1009/201 (NOTIFY_MAP_SYNC):
           - فحص طوابير التحرك (11, 12, 14): هل توجد مسيرة متجهة نحو هذا الهدف (سواء من قلعتنا أو لاعب آخر).
           - فحص قطع الخريطة (1): هل كائن الهدف مسجل كشاغل للاعب آخر.

        يعيد:
            (is_busy: bool, reason: str, node_data: Dict[str, Any])
        """
        parts = str(target_id).split('-')
        gx = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else tx
        gy = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else ty
        node_data: Dict[str, Any] = {}

        # 1. فحص 1006/22 المباشر
        try:
            r22 = await self.conn.query('1006', '22', {"x": tx, "y": ty, "id": str(target_id)}, timeout=3.0)
            if r22 and isinstance(r22, dict):
                ret22 = r22.get('retData', {})
                if isinstance(ret22, dict):
                    node_data = ret22
                    c_num = int(ret22.get('currentCollectNum', 0))
                    c_spd = float(ret22.get('collectSpeed', 0))
                    active_march = ret22.get('marchId') or ret22.get('battleId')

                    if c_num > 0 or c_spd > 0:
                        return True, f"لاعب آخر يشغل الهدف حالياً (currentCollectNum={c_num}, collectSpeed={c_spd})", node_data
                    if is_stronghold and active_march:
                        return True, f"المعقل مشغول بمعركة نشطة حالياً (marchId={active_march})", node_data
                    if not is_stronghold:
                        fresh_rem = int(ret22.get('remainSourceNum', -1))
                        if fresh_rem == 0:
                            return True, "رصيد موارد الحقل نفد تماماً (remainSourceNum=0)", node_data
        except Exception as e:
            self.log.debug(f"استعلام 1006/22 للهدف {target_id}: {e}")

        # 2. مزامنة الخريطة 1006/1000 واعتراض إشعارات 1009/201
        target_kid = int(kingdom_id or getattr(self.conn, 'kingdom_id', 0) or 0)
        sync_packets = []
        def _capture_sync(cmd, sub, content):
            if str(cmd) == '1009' and str(sub) == '201':
                sync_packets.append(content)

        self.conn.add_packet_listener(_capture_sync)
        try:
            await self.conn.query('1006', '1000', {
                'centerX': tx,
                'centerY': ty,
                'centerKid': target_kid
            }, timeout=3.0)
            await asyncio.sleep(0.7)
        except Exception as e:
            self.log.debug(f"استعلام 1006/1000 للهدف {target_id}: {e}")
        finally:
            self.conn.remove_packet_listener(_capture_sync)

        cached_sync = getattr(self.conn, 'cached_packets', {}).get(('1009', '201'))
        if cached_sync and cached_sync not in sync_packets:
            sync_packets.append(cached_sync)

        our_uid_str = str(self.uid)
        target_id_str = str(target_id)

        for pkt in sync_packets:
            if not isinstance(pkt, dict):
                continue
            p_data = pkt.get('data')
            if isinstance(p_data, dict):
                notify_list = p_data.get('notifyData', [])
            elif isinstance(p_data, list):
                notify_list = p_data
            else:
                notify_list = []

            if not isinstance(notify_list, list):
                continue

            for msg in notify_list:
                if not isinstance(msg, dict):
                    continue
                m_type = msg.get('msgType')
                m_data = msg.get('data')

                # طوابير ومسيرات التحرك (11, 12, 14)
                if m_type in (11, 12, 14):
                    q_items = []
                    if isinstance(m_data, dict):
                        for k, v in m_data.items():
                            if isinstance(v, list):
                                q_items.extend([x for x in v if isinstance(x, dict)])
                            elif isinstance(v, dict):
                                for qid, qd in v.items():
                                    if isinstance(qd, dict):
                                        q_items.append(qd)
                                if 'to' in v:
                                    q_items.append(v)
                    elif isinstance(m_data, list):
                        q_items.extend([x for x in m_data if isinstance(x, dict)])

                    for q in q_items:
                        to_info = q.get('to', {})
                        q_to_x = to_info.get('x')
                        q_to_y = to_info.get('y')
                        q_to_id = to_info.get('id') or to_info.get('mapObjId')
                        q_uid = q.get('playerID') or q.get('uid') or q.get('from', {}).get('uid')
                        p_name = q.get('playerName', '')

                        is_target = False
                        if q_to_id and str(q_to_id) == target_id_str:
                            is_target = True
                        elif q_to_x is not None and q_to_y is not None:
                            try:
                                qx, qy = int(q_to_x), int(q_to_y)
                                if (qx, qy) in ((tx, ty), (gx, gy), (tx + 1, ty + 1), (gx - 1, gy - 1)):
                                    is_target = True
                            except Exception:
                                pass

                        if is_target:
                            if q_uid and str(q_uid) == our_uid_str:
                                return True, "قلعتك متجهة بالفعل نحو هذا الهدف حالياً (مسيرة نشطة لك)", node_data
                            elif q_uid:
                                return True, f"مسيرة نشطة للاعب آخر ({p_name or q_uid}) متجهة نحو هذا الهدف حالياً على الخريطة", node_data
                            else:
                                return True, "توجد مسيرة نشطة متجهة نحو هذا الهدف حالياً على الخريطة", node_data

                # كائنات قطع الخريطة (1)
                elif m_type == 1:
                    if isinstance(m_data, dict):
                        for kid_k, p_dict in m_data.items():
                            if isinstance(p_dict, dict):
                                for piece_id, objs in p_dict.items():
                                    if isinstance(objs, list):
                                        for obj in objs:
                                            if isinstance(obj, dict) and str(obj.get('id')) == target_id_str:
                                                res_obj = obj.get('resource', {})
                                                r_uid = res_obj.get('uid') or res_obj.get('playerID')
                                                occupier = res_obj.get('occupier') or obj.get('occupier') or obj.get('user')
                                                occ = occupier or r_uid
                                                if occ:
                                                    if str(occ) == our_uid_str:
                                                        return True, "قلعتك تشغل هذا الهدف حالياً", node_data
                                                    else:
                                                        return True, f"الهدف مسجل كشاغل للاعب آخر ({occ})", node_data

        return False, "", node_data

    # ── الحالة للمراقبة ───────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """حالة المهمة الحالية — تُرسَل إلى Firebase/panel."""
        return {
            "name":        self.name,
            "email":       self.email,
            "state":       self._state.value,
            "run_count":   self._run_count,
            "last_run":    self._last_run,
            "last_result": self._last_result.message if self._last_result else None,
            "config":      self.config,
        }

    # ── تشغيل داخلي (يستخدمه TaskScheduler) ─────────────────────

    async def _execute(self) -> TaskResult:
        """تغليف run() مع تتبع الحالة والإحصائيات."""
        self._state    = TaskState.RUNNING
        self._last_run = time.time()
        try:
            result = await self.run()
            self._last_result = result
            self._run_count  += 1
            self._state       = TaskState.WAITING
            return result
        except Exception as e:
            self.log.exception(f"❌ خطأ غير متوقع في المهمة [{self.name}]: {e}")
            self._state = TaskState.ERROR
            return TaskResult.fail(f"خطأ: {e}", retry_after=60)


    # ════════════════════════════════════════════════════════════════
    #  دوال التعامل مع ذاكرة الحية حق المسيرات
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _read_live_local_queues(conn: Any) -> List[Any]:
        """قراءة طوابير المسيرات الحالية من مراجع الذاكرة الحية دون استعلام شبكي."""
        queues = getattr(conn, "local_queues", None)
        if queues:
            return list(queues)
        init_data = getattr(conn, "init_data", None)
        if isinstance(init_data, dict) and init_data.get("local_queues"):
            return list(init_data["local_queues"])
        mem_engine = getattr(conn, "memory_engine", None)
        if mem_engine is not None and hasattr(mem_engine, "get_own_local_queues"):
            own_queues = mem_engine.get_own_local_queues()
            if own_queues:
                return list(own_queues)
        return []

    async def get_active_march_targets(
        self,
        force_sync: bool = False,
        allow_network: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        قراءة الأهداف التي تسير إليها أو تتعامل معها فيالق الحساب من الذاكرة الحية،
        مع إرسال استعلام مزامنة (1007/1000) إذا كانت local_queues فارغة ولم تُزامن بعد.
        """
        conn = getattr(self, "conn", None)
        if conn is None:
            return []

        queues = self._read_live_local_queues(conn)
        mem_engine = getattr(conn, "memory_engine", None)
        is_synced = bool(getattr(mem_engine, "local_queues_synced", False))

        if (not queues or force_sync) and allow_network and (force_sync or not is_synced):
            if getattr(conn, "is_connected", False) and hasattr(conn, "query"):
                resp = None
                try:
                    self.log.info(f"😎😎😎😎😎")
                    resp = await conn.query("1007", "1000", {}, timeout=3)
                except Exception:
                    resp = None

                # انتظار قصير لوصول إشعار NOTIFY_LOCAL_QUEUE_SYNC (202) وتحديث الذاكرة الحية
                for _ in range(5):
                    queues = self._read_live_local_queues(conn)
                    if queues or bool(getattr(mem_engine, "local_queues_synced", False)):
                        break
                    await asyncio.sleep(0.1)

                if not queues and isinstance(resp, dict) and isinstance(resp.get("data"), list):
                    queues = list(resp["data"])

        if not queues:
            return []

        my_uid = str(getattr(self, "uid", "") or "").strip()
        active_statuses = (0, 1, 2, 3, 4, 7)
        targets_by_id: Dict[str, float] = {}

        for q in queues:
            if not isinstance(q, dict):
                continue

            q_uid = q.get("uid")
            if my_uid and q_uid is not None and str(q_uid).strip() != my_uid:
                continue

            raw_status = q.get("status")
            if raw_status is None:
                continue
            try:
                status = int(raw_status)
            except (TypeError, ValueError):
                continue
            if status not in active_statuses:
                continue

            loc_order = (q.get("from"), q.get("to")) if status == 3 else (q.get("to"), q.get("from"))
            tid = ""
            for loc in loc_order:
                if not isinstance(loc, dict) or loc.get("mapType") == 4:
                    continue
                raw_id = str(loc.get("id") or "").strip()
                if not raw_id or (my_uid and raw_id.endswith(f"-{my_uid}")):
                    continue
                tid = raw_id
                break
            if not tid:
                continue

            raw_ts = q.get("createTime") or q.get("startTime") or q.get("statusStartTime")
            try:
                ts = float(raw_ts) if raw_ts else time.time()
            except (TypeError, ValueError):
                ts = time.time()
            if ts <= 0:
                ts = time.time()

            prev_ts = targets_by_id.get(tid)
            if prev_ts is None or ts > prev_ts:
                targets_by_id[tid] = ts

        return [
            {"id": tid, "ts": ts}
            for tid, ts in sorted(targets_by_id.items(), key=lambda item: item[1])
        ]


# ════════════════════════════════════════════════════════════════════
#  المجدِّل الزمني للمهمة (TaskScheduler)
# ════════════════════════════════════════════════════════════════════

class TaskScheduler:
    """
    يشغّل مهمة (BaseTask) بشكل دوري مع:
    - interval : فترة التكرار بالثواني (مثلاً: 1800 = كل 30 دقيقة)
    - offset   : تأخير أولي بالثواني (لتفريق الحسابات)

    مثال:
        scheduler = TaskScheduler(task=gather_task, interval=1800, offset=120)
        await scheduler.run_forever()
    """

    def __init__(self, task: BaseTask, interval: int, offset: int = 0):
        self.task     = task
        self.interval = interval
        self.offset   = offset
        self.log      = logging.getLogger(f"scheduler.{task.name}[{task.email}]")

    async def run_forever(self):
        """حلقة لا نهائية: تشغيل المهمة + انتظار interval."""

        # تهيئة المهمة مرة واحدة
        await self.task.on_start()
        self.log.info(
            f"🕐 [{self.task.name}] بدء بعد {self.offset}s، "
            f"يتكرر كل {self.interval}s"
        )

        # انتظار الـ offset الأولي (يمكن إيقافه مبكراً)
        if self.offset > 0:
            try:
                await asyncio.wait_for(
                    self.task._stop_event.wait(),
                    timeout=self.offset
                )
                return  # تم الإيقاف أثناء الانتظار
            except asyncio.TimeoutError:
                pass

        while not self.task.is_stopped():
            result = await self.task._execute()

            if self.task.is_stopped():
                break

            # إذا طلبت المهمة retry_after خاص
            wait_time = result.retry_after if (result.should_retry and result.retry_after > 0) else self.interval

            self.log.info(
                f"⏳ [{self.task.name}] الانتظار {wait_time}s "
                f"قبل الجولة القادمة..."
            )
            try:
                await asyncio.wait_for(
                    self.task._stop_event.wait(),
                    timeout=wait_time
                )
                break  # تم الإيقاف أثناء الانتظار
            except asyncio.TimeoutError:
                pass  # انتهى الانتظار بشكل طبيعي، نكمل الحلقة

        await self.task.on_stop()
        self.log.info(f"✅ [{self.task.name}] توقف المُجدِّل.")
