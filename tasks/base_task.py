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
from typing import TYPE_CHECKING, Any, Dict, Optional

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

    async def get_active_marches_count(self) -> int:
        """حساب عدد الفيالق والمسيرات النشطة حالياً خارج القلعة مع استعلام فوري وتجنب التكرار."""
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
