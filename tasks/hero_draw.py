# -*- coding: utf-8 -*-
"""
tasks/hero_draw.py — مهمة الشارات الملكية، تجنيد الأبطال وبحث المهارات وصندوق البطل
══════════════════════════════════════════════════════════════════════════════════════

تشمل 3 مهام مجانية في حزمة واحدة (cmd: 2058 / subcmd: 1):
  1. 🦸 تجنيد البطل (Hero Enlist):      {"nType": 1, "nSubType": 1}
  2. 📜 بحث المهارة (Skill Research):   {"nType": 3, "nSubType": 1}
  3. 🎁 صندوق البطل (Hero Box / Chest): {"nType": 4, "nSubType": 1}

التحقق التلقائي:
  - يفحص heroEnlistCtrl.heroEnlistData لكل نوع لمعرفة المرات المجانية المتبقية (leftTimes)
  - يتحقق من انتهاء المؤقت الزمني الفاصل (canusetime)
  - ينفذ السحبات المجانية الجاهزة فقط، ويحسب أقرب موعد للسحبة القادمة تلقائياً (retry_after)

الاستخدام كملف مستقل:
    python tasks/hero_draw.py --email "meik.gaertner2306.MGr@gmail.com"
    python tasks/hero_draw.py --email "burcudemr@gmail.com"
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
#  تعريف المهام الثلاث ضمن الحزمة
# ════════════════════════════════════════════════════════════════════

DRAW_TYPES = {
    1: {"name": "🦸 تجنيد البطل (Hero Enlist)", "type_id": 1},
    3: {"name": "📜 بحث المهارة (Skill Research)", "type_id": 3},
    4: {"name": "🎁 صندوق البطل (Hero Box)", "type_id": 4},
}


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (HeroDrawTask)
# ════════════════════════════════════════════════════════════════════

class HeroDrawTask(BaseTask):
    """
    مهمة سحب وتجنيد الأبطال والمهارات وصناديق الأبطال المجانية.
    """
    name = "hero_draw"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        self.log.info("🎖️ بدء مهمة الشارات الملكية (تجنيد الأبطال / بحث المهارات / صندوق البطل)...")

        now_ts = int(time.time())
        enlist_ctrl = self.conn.init_data.get('heroEnlistCtrl', {})
        enlist_data = enlist_ctrl.get('heroEnlistData', {}) if isinstance(enlist_ctrl, dict) else {}

        executed_actions: List[str] = []
        rewards_summary: List[Dict[str, Any]] = []
        next_ready_times: List[int] = []

        # فحص وتنفيذ كل نوع من الأنواع الثلاثة
        for type_id, meta in DRAW_TYPES.items():
            type_key = str(type_id)
            info = enlist_data.get(type_key, {})
            
            left_times = int(info.get('leftTimes', 0))
            can_use_time = int(info.get('canusetime', 0))
            type_name = meta["name"]

            self.log.info(f"🔍 فحص [{type_name}]: المرات المجانية المتبقية اليوم: {left_times} | وقت الاستحقاق: {can_use_time}")

            # هل السحبة المجانية متاحة وجاهزة الآن؟
            if left_times > 0 and (can_use_time <= now_ts or can_use_time == 0):
                self.log.info(f"✨ السحبة المجانية متاحة لـ [{type_name}]! جاري السحب الآن...")

                payload = {
                    "nSubType": 1,
                    "nType": type_id
                }

                r_draw = await self.conn.query('2058', '1', payload, timeout=8)
                if r_draw and str(r_draw.get('err', '0')) == '0':
                    draw_data = r_draw.get('data', {})
                    rewards = draw_data.get('reward', [])
                    self.log.info(f"✅ تم سحب [{type_name}] بنجاح 🎉 المكافأة: {rewards}")
                    executed_actions.append(type_name)
                    rewards_summary.append({
                        "type": type_name,
                        "nType": type_id,
                        "rewards": rewards
                    })

                    # تحديث بيانات السحب في الذاكرة إن أمكن
                    if isinstance(enlist_data, dict) and type_key in enlist_data:
                        enlist_data[type_key]['leftTimes'] = max(0, left_times - 1)
                else:
                    err_code = str(r_draw.get('err', 'unknown')) if r_draw else 'timeout'
                    self.log.warning(f"⚠️ فشل سحب [{type_name}] (كود: {err_code})")

                # فاصل زمني بسيط بين السحبات للأمان
                await asyncio.sleep(1.8)
            elif left_times > 0 and can_use_time > now_ts:
                rem_sec = can_use_time - now_ts
                rem_mins = rem_sec // 60
                self.log.info(f"⏳ [{type_name}] قيد التهدئة | متبقي {rem_mins} دقيقة ({rem_sec} ثانية)")
                next_ready_times.append(rem_sec)
            else:
                self.log.info(f"ℹ️ [{type_name}] تم استهلاك جميع المرات المجانية اليوم.")

        # تحديد وقت التكرار القادم
        if next_ready_times:
            earliest_retry = min(next_ready_times) + 15
        else:
            earliest_retry = 3600  # إعادة الفحص بعد ساعة

        # تجهيز رسالة التقرير
        if executed_actions:
            msg = f"تم إنجاز السحبات المجانية التالية بنجاح: {', '.join(executed_actions)}"
            return TaskResult.ok(
                msg,
                status="success",
                executed=executed_actions,
                rewards=rewards_summary,
                retry_after=min(earliest_retry, 86400)
            )
        else:
            if next_ready_times:
                min_wait = min(next_ready_times) // 60
                msg = f"لا توجد سحبات مجانية جاهزة الآن (أقرب سحبة بعد {min_wait} دقيقة)"
            else:
                msg = "لا توجد سحبات مجانية متاحة حالياً (تم استهلاك السحبات اليومية)"
            
            self.log.info(f"ℹ️ {msg}")
            return TaskResult.ok(
                msg,
                status="no_free_draws_ready",
                retry_after=min(earliest_retry, 86400)
            )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Hero Draw Task — مهمة الشارات الملكية وسحب الأبطال والمهارات والصناديق")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
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

        task = HeroDrawTask(conn)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
