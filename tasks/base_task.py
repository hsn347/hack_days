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
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

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

    @classmethod
    def ok(cls, message: str = "✅ تم بنجاح", **data) -> "TaskResult":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str, retry_after: int = 0, **data) -> "TaskResult":
        return cls(success=False, message=message, data=data,
                   should_retry=retry_after > 0, retry_after=retry_after)

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
        if force_sync or not has_local:
            try:
                self.log.warning("🛑🛑🛑🛑🛑🛑")
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
