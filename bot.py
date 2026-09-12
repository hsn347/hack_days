# -*- coding: utf-8 -*-
"""
bot.py — الملف الرئيسي لبوت Empire
════════════════════════════════════════════════════════════════════════

• يشغّل جميع الحسابات بالتوازي الكامل (asyncio)
• لكل حساب: يُنشئ اتصالاً وينفّذ المهام المُفعَّلة بشكل دوري
• الجدولة: interval ثابت لكل مهمة + offset مختلف لكل حساب
• مُصمَّم للتشغيل كـ Docker/VPS daemon (بدون تدخل بشري)
• جاهز للربط بـ Firebase مستقبلاً

الاستخدام:
    python bot.py                              # تشغيل جميع الحسابات
    python bot.py --email user@gmail.com       # حساب واحد
    python bot.py --email u@g.com --password x # تسجيل دخول جديد
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import argparse
import signal
from typing import Dict, List, Optional

# ── إعداد sys.path ──────────────────────────────────────────────────
ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ── الاستيرادات ──────────────────────────────────────────────────────
from game_client import GameConnection, AccountSession
from core.session_manager import SessionManager
from config import get_account_config, BOT_CONFIG
from tasks.base_task import TaskScheduler
from tasks.gather import GatherTask
from tasks.port import PortTask
from tasks.alliance import AllianceTask
from tasks.train import TrainTask
from tasks.transport import TransportTask
from tasks.monster import MonsterTask

from tasks.ruins import RuinsTask
from tasks.stronghold import StrongholdTask
from tasks.gold_gather import GoldGatherTask


# ── خريطة اسم المهمة → الكلاس ──────────────────────────────────────
TASK_REGISTRY = {
    "gather":      GatherTask,
    "port":        PortTask,
    "alliance":    AllianceTask,
    "train":       TrainTask,
    "transport":   TransportTask,
    "monster":     MonsterTask,
    "ruins":       RuinsTask,
    "stronghold":  StrongholdTask,
    "gold_gather": GoldGatherTask,
}






# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level  = getattr(logging, BOT_CONFIG.get("log_level", "INFO")),
    format = "[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
    datefmt= "%H:%M:%S"
)
log = logging.getLogger("bot")


# ════════════════════════════════════════════════════════════════════
#  AccountRunner — يُشغِّل جميع مهام حساب واحد
# ════════════════════════════════════════════════════════════════════

class AccountRunner:
    """يُدير اتصال حساب واحد ويشغّل مهامه بالتوازي."""

    def __init__(self, account: AccountSession, offset: int = 0):
        self.account = account
        self.offset  = offset
        self.conn: Optional[GameConnection] = None
        self._schedulers: List[TaskScheduler] = []
        self._tasks_handles: List[asyncio.Task] = []
        self._stop = asyncio.Event()

    async def run(self):
        email = self.account.email
        log.info(f"{'═'*55}")
        log.info(f"  👤 بدء تشغيل حساب: {email} (offset={self.offset}s)")
        log.info(f"{'═'*55}")

        # انتظار الـ offset (لتفريق بدء الحسابات)
        if self.offset > 0:
            log.info(f"[{email}] ⏳ انتظار {self.offset}s قبل البدء...")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.offset)
                return
            except asyncio.TimeoutError:
                pass

        # حلقة إعادة الاتصال
        while not self._stop.is_set():
            connected = await self._connect()
            if connected:
                await self._run_tasks()
            else:
                log.warning(f"[{email}] ❌ فشل الاتصال، إعادة المحاولة بعد {BOT_CONFIG['reconnect_interval']}s...")

            if self._stop.is_set():
                break

            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=BOT_CONFIG["reconnect_interval"]
                )
            except asyncio.TimeoutError:
                pass

    async def _connect(self) -> bool:
        """إنشاء اتصال جديد بالسيرفر."""
        email = self.account.email
        try:
            self.conn = GameConnection(self.account)
            if await self.conn.connect():
                log.info(f"[{email}] ✅ متصل | UID={self.conn.uid} | Server={self.conn.server_name}")
                return True
            return False
        except Exception as e:
            log.error(f"[{email}] خطأ في الاتصال: {e}")
            return False

    async def _run_tasks(self):
        """ينشئ ويشغّل جميع المهام المُفعَّلة لهذا الحساب."""
        email      = self.account.email
        acc_config = get_account_config(email)
        tasks_cfg  = acc_config['tasks']

        self._schedulers     = []
        self._tasks_handles  = []

        for task_name, task_cfg in tasks_cfg.items():
            if not task_cfg.get('enabled', False):
                continue
            cls = TASK_REGISTRY.get(task_name)
            if not cls:
                log.warning(f"[{email}] ⚠️ مهمة غير معروفة: {task_name}")
                continue

            task      = cls(self.conn, task_cfg)
            interval  = task_cfg.get('interval', 1800)
            # offset الداخلي بين مهام نفس الحساب (مثلاً: gather يبدأ أولاً، ثم port بعد 60s...)
            inner_off = task_cfg.get('inner_offset', 0)
            scheduler = TaskScheduler(task, interval=interval, offset=inner_off)
            self._schedulers.append(scheduler)

            handle = asyncio.create_task(
                scheduler.run_forever(),
                name=f"{email}:{task_name}"
            )
            self._tasks_handles.append(handle)
            log.info(f"[{email}] 🚀 بدأت مهمة [{task_name}] (interval={interval}s)")

        if not self._tasks_handles:
            log.warning(f"[{email}] ⚠️ لا توجد مهام مُفعَّلة لهذا الحساب!")
            return

        # مراقب انقطاع الاتصال — ينتهي عندما يُقطع Gate
        disconnect_event = asyncio.Event()

        async def _watch_disconnect():
            while self.conn and self.conn._gate and self.conn._gate._alive:
                await asyncio.sleep(5)
            disconnect_event.set()

        watch_handle = asyncio.create_task(_watch_disconnect())

        # انتظار: إما انقطاع الاتصال أو انتهاء إحدى المهام بخطأ
        disconnect_future = asyncio.ensure_future(disconnect_event.wait())
        all_handles = self._tasks_handles + [disconnect_future]

        done, pending = await asyncio.wait(
            all_handles,
            return_when=asyncio.FIRST_COMPLETED
        )

        watch_handle.cancel()
        reason = self.conn._gate.kick_reason if (self.conn and self.conn._gate) else "unknown"
        if disconnect_event.is_set() and not self._stop.is_set():
            log.warning(f"[{email}] 🔁 انقطع الاتصال ({reason}) — سيتم إعادة الاتصال...")

        # إيقاف بقية المهام
        await self._stop_tasks()


    async def _stop_tasks(self):
        """إيقاف جميع المهام بشكل آمن."""
        for sched in self._schedulers:
            await sched.task.stop()
        for handle in self._tasks_handles:
            handle.cancel()
        if self.conn:
            await self.conn.close()
        log.info(f"[{self.account.email}] 🛑 تم إيقاف جميع المهام")

    async def stop(self):
        self._stop.set()
        await self._stop_tasks()


# ════════════════════════════════════════════════════════════════════
#  دالة main
# ════════════════════════════════════════════════════════════════════

async def run_all(accounts: List[AccountSession], offset_step: int = 30):
    """تشغيل جميع الحسابات بالتوازي مع offset تلقائي بين كل حساب."""
    runners: List[AccountRunner] = []
    for i, acc in enumerate(accounts):
        acc_cfg = get_account_config(acc.email)
        # offset = ما حُدِّد في ACCOUNT_OVERRIDES أو التلقائي بالترتيب
        offset  = acc_cfg.get('offset', i * offset_step)
        runner  = AccountRunner(acc, offset=offset)
        runners.append(runner)

    log.info(f"🤖 بدء تشغيل {len(runners)} حساب بالتوازي...")
    
    # إعداد إشارة الإيقاف (Ctrl+C)
    stop_event = asyncio.Event()
    
    def _signal_handler():
        log.info("🛑 تم استقبال إشارة إيقاف...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows لا يدعم add_signal_handler

    try:
        await asyncio.gather(*[r.run() for r in runners])
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("🛑 إيقاف البوت...")
        for r in runners:
            await r.stop()


async def main():
    parser = argparse.ArgumentParser(
        description="osmanli-bot — بوت Empire الرئيسي",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة:
  python bot.py                            # جميع الحسابات في session_cache.json
  python bot.py --email user@gmail.com     # حساب واحد
  python bot.py --email u@g.com --password x  # تسجيل دخول جديد
        """
    )
    parser.add_argument("--email",    "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--password", "-p", help="كلمة المرور (لتسجيل الدخول لأول مرة)")
    parser.add_argument("--all",      "-a", action="store_true", help="تشغيل جميع الحسابات")
    args = parser.parse_args()

    session_mgr = SessionManager()

    # تسجيل دخول جديد إذا طُلب
    if args.email and args.password:
        acc = session_mgr.login_and_save(args.email, args.password)
        if not acc:
            log.error("❌ فشل تسجيل الدخول!")
            sys.exit(1)
        log.info(f"✅ تم تسجيل وحفظ الحساب: {args.email}")
        await run_all([acc])
        return

    # جلب الحسابات من cache
    all_accounts = session_mgr.get_all()
    if not all_accounts:
        log.error("❌ لا توجد حسابات في session_cache.json! استخدم --email و --password أولاً.")
        sys.exit(1)

    if args.email and not args.all:
        # حساب واحد محدد
        acc_map = {a.email: a for a in all_accounts}
        if args.email not in acc_map:
            # الحساب غير موجود → اطلب كلمة المرور
            pwd = input(f"🔑 أدخل كلمة المرور للحساب ({args.email}): ").strip()
            if not pwd:
                log.error("❌ لم تُدخل كلمة مرور.")
                sys.exit(1)
            acc = session_mgr.login_and_save(args.email, pwd)
            if not acc:
                sys.exit(1)
        else:
            acc = acc_map[args.email]
        await run_all([acc])
    else:
        # جميع الحسابات
        await run_all(all_accounts, offset_step=BOT_CONFIG.get("offset_step", 30))


if __name__ == "__main__":
    asyncio.run(main())
