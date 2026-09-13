    # -*- coding: utf-8 -*-
"""
tasks/savings_bank.py — مهمة دار الادخار وبنك التوفير (Savings Bank Task)
══════════════════════════════════════════════════════════════════════════════════════

دورة عمل المهمة:
  1. فحص الوديعة الحالية في دار الادخار (savingsBankAgCtrl):
     - إذا كانت الوديعة مكتملة المدة ← سحب الوديعة مع الأرباح تلقائياً (6023/2).
     - إذا كانت قيد الاستثمار ← حساب المدة المتبقية وتعيين موعد المراجعة.
  2. إذا لم تكن هناك وديعة نشطة (أو بعد سحب الأرباح):
     - إيداع الذهب تلقائياً بأقصى حد متاح (6023/1) للمدة المختارة (7 أو 15 أو 30 يوماً).

الاستخدام كملف مستقل:
    python tasks/savings_bank.py --email "meik.gaertner2306.MGr@gmail.com" --days 30
    python tasks/savings_bank.py --email "zzoro8290@gmail.com" --days 30
    python tasks/savings_bank.py --email "ossso5040@gmail.com" --days 15 --deposit 4000
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  ثوابت وخطط دار الادخار
# ════════════════════════════════════════════════════════════════════

SAVINGS_PLANS: Dict[int, Dict[str, Any]] = {
    1:  {"name": "خطة يوم واحد (يومية)",   "max_deposit": 2000, "days": 1},
    7:  {"name": "خطة 7 أيام (أسبوعية)",  "max_deposit": 2000, "days": 7},
    15: {"name": "خطة 15 يوماً (نصف شهرية)", "max_deposit": 2000, "days": 15},
    30: {"name": "خطة 30 يوماً (شهرية)",  "max_deposit": 2000, "days": 30},
}

DEFAULT_DAYS = 7
GOLD_ITEM_ID = 1001


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (SavingsBankTask)
# ════════════════════════════════════════════════════════════════════

class SavingsBankTask(BaseTask):
    """
    مهمة إدارة دار الادخار وسحب الأرباح وإيداع الذهب.
    """
    name = "savings_bank"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        cfg = self.config
        target_days = int(cfg.get('days', DEFAULT_DAYS))
        if target_days not in SAVINGS_PLANS:
            target_days = DEFAULT_DAYS

        plan_info = SAVINGS_PLANS[target_days]
        self.log.info(f"🏦 بدء مهمة دار الادخار (الخطة المستهدفة: {plan_info['name']})")

        now_ts = int(time.time())
        savings_ctrl = self.conn.init_data.get('savingsBankAgCtrl', {})
        active_slip = savings_ctrl.get('slip') if isinstance(savings_ctrl, dict) else None

        claimed_profit = 0

        # 1. فحص وجود وديعة نشطة وموعد استحقاقها
        if active_slip and isinstance(active_slip, dict) and active_slip.get('startTime'):
            slip_days = int(active_slip.get('day', 7))
            slip_start = int(active_slip.get('startTime', 0))
            slip_deposit = int(active_slip.get('deposit', 0))
            slip_end = slip_start + (slip_days * 86400)

            if now_ts >= slip_end:
                # الوديعة اكتملت، نقوم بسحب الأرباح أولاً (6023/2)
                self.log.info(f"💰 الوديعة السابقة ({slip_deposit} ذهب لمدة {slip_days} يوم) مكتملة الاستحقاق! جاري سحب الأرباح...")
                r_withdraw = await self.conn.query('6023', '2', {}, timeout=8)
                if r_withdraw and str(r_withdraw.get('err', '0')) == '0':
                    claimed_profit = int(r_withdraw.get('data', {}).get('deposit', 0))
                    self.log.info(f"✅ تم سحب الوديعة والأرباح بنجاح: +{claimed_profit:,} ذهب 🎉")
                    # تفريغ الوديعة القديمة في الذاكرة
                    if isinstance(savings_ctrl, dict):
                        savings_ctrl['slip'] = {}
                else:
                    err_code = str(r_withdraw.get('err', 'unknown')) if r_withdraw else 'timeout'
                    self.log.warning(f"⚠️ فشل سحب أرباح دار الادخار (كود: {err_code})")
            else:
                # الوديعة لا تزال جارية
                remaining_sec = slip_end - now_ts
                rem_days = remaining_sec // 86400
                rem_hours = (remaining_sec % 86400) // 3600
                rem_mins = (remaining_sec % 3600) // 60
                msg = f"الوديعة قيد الاستثمار ({slip_deposit} ذهب - {slip_days} يوم) | متبقي: {rem_days} يوم و {rem_hours} ساعة و {rem_mins} دقيقة"
                self.log.info(f"⏳ {msg}")
                return TaskResult.ok(
                    msg,
                    status="investing",
                    slip=active_slip,
                    remaining_seconds=remaining_sec,
                    retry_after=min(remaining_sec + 60, 86400)
                )

        # 2. تحديد مبلغ الإيداع (الافتراضي 2000 أو المحدد صراحة من المستخدم/Firebase)
        custom_deposit = cfg.get('deposit')
        deposit_amount = int(custom_deposit) if custom_deposit else plan_info.get("max_deposit", 2000)

        # 3. تنفيذ الإيداع الجديد (6023/1)
        self.log.info(f"🚀 جاري إيداع {deposit_amount:,} ذهب في دار الادخار لمدة {target_days} يوماً...")
        payload = {
            "itemId": GOLD_ITEM_ID,
            "day": target_days,
            "deposit": deposit_amount
        }

        r_deposit = await self.conn.query('6023', '1', payload, timeout=8)
        if r_deposit and str(r_deposit.get('err', '0')) == '0':
            new_slip = r_deposit.get('data', {}).get('slip', payload)
            if isinstance(savings_ctrl, dict):
                savings_ctrl['slip'] = new_slip

            retry_delay = target_days * 86400
            success_msg = f"تم إيداع {deposit_amount:,} ذهب بنجاح لمدة {target_days} يوماً في دار الادخار"
            if claimed_profit > 0:
                success_msg += f" (وسحب أرباح سابقة: +{claimed_profit:,} ذهب)"
            self.log.info(f"✅ {success_msg} 🎉")

            return TaskResult.ok(
                success_msg,
                status="deposited",
                deposit=deposit_amount,
                days=target_days,
                claimed_profit=claimed_profit,
                retry_after=retry_delay
            )
        else:
            err_code = str(r_deposit.get('err', 'unknown')) if r_deposit else 'timeout'
            if err_code == "6":
                self.log.info("ℹ️ توجد وديعة نشطة بالفعل في دار الادخار.")
                return TaskResult.ok("توجد وديعة نشطة بالفعل", status="investing", retry_after=43200)
            else:
                self.log.error(f"❌ فشل إيداع الذهب في دار الادخار (كود السيرفر: {err_code})")
                return TaskResult.fail(f"فشل الإيداع (كود: {err_code})", retry_after=3600)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Savings Bank Task — مهمة دار الادخار وبنك التوفير")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--days", "-d", type=int, default=7, choices=[7, 15, 30],
                        help="مدة الإيداع بالأيام: 7 أو 15 أو 30 [افتراضي: 7]")
    parser.add_argument("--deposit", "-m", type=int, default=None,
                        help="مبلغ الذهب المراد إيداعه [افتراضي: أقصى حد متاح للخطة]")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    from core.session_manager import SessionManager

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        target_email = args.email or next(iter(accounts.keys()))
        acc = accounts.get(target_email)
        if not acc:
            print(f"❌ الحساب {target_email} غير موجود!")
            return

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(12):
            await asyncio.sleep(1.0)
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "days": args.days,
            "deposit": args.deposit,
        }

        task = SavingsBankTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
