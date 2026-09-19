# -*- coding: utf-8 -*-
"""
tasks/treasure_pavilion.py — مهمة استكشاف جناح الكنز المجاني (Treasure Pavilion)
══════════════════════════════════════════════════════════════════════════════════

طلب الاستكشاف:
    cmd: "2058", subcmd: "1", data: {"nSubType": 1, "nType": 6}

قاعدة الأمان الصارمة:
    - الشراء والاستكشاف المجاني يستخدمان نفس الحزمة تماماً.
    - تفحص المهمة بيانات السيرفر أولاً: heroEnlistCtrl.heroEnlistData['6']
    - تتأكد من وجود مرات مجانية متبقية اليوم (leftTimes > 0).
    - تتأكد من عدم وجود فترة تهدئة فاصلة بين السحبات (canusetime <= now أو 0).
    - إذا توفر الاستكشاف المجاني ➔ تنفذ الطلب وتستلم المكافأة.
    - إذا لم يتوفر الاستكشاف المجاني ➔ تنهي المهمة فوراً دون إرسال أي طلب لمنع صرف الذهب نهائياً.

الاستخدام كملف مستقل:
    python tasks/treasure_pavilion.py --email "user@example.com"
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
import logging
import time
from typing import Any, Dict, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


class TreasurePavilionTask(BaseTask):
    """
    مهمة استكشاف جناح الكنز المجاني مع التحقق الصارم لمنع استهلاك الذهب.
    """
    name = "treasure_pavilion"

    # الفئة 6 مخصصة لجناح الكنز في بروتوكول 2058
    PAVILION_TYPE_ID = 6
    COOLDOWN_SECONDS = 300  # 5 دقائق فترة تهدئة قياسية بين السحبات

    def __init__(self, conn: GameConnection, config: Optional[dict] = None):
        super().__init__(conn, config or {})

    def get_free_status(self) -> Tuple[bool, int, int, int, str]:
        """
        فحص حالة الاستكشاف المجاني من بيانات السيرفر.
        تعيد: (is_free_ready, left_times, can_use_time, day_num, reason)
        """
        now_ts = int(time.time())
        enlist_ctrl = self.conn.init_data.get('heroEnlistCtrl', {})
        if not isinstance(enlist_ctrl, dict):
            return False, 0, 0, 0, "بيانات heroEnlistCtrl غير متوفرة في تهيئة السيرفر"

        enlist_data = enlist_ctrl.get('heroEnlistData', {})
        if not isinstance(enlist_data, dict):
            return False, 0, 0, 0, "قائمة heroEnlistData غير متوفرة"

        pavilion_data = enlist_data.get(str(self.PAVILION_TYPE_ID), {})
        if not isinstance(pavilion_data, dict) or not pavilion_data:
            return False, 0, 0, 0, "بيانات جناح الكنز (الفئة 6) غير موجودة (قد يكون المبنى غير مفتوح)"

        left_times = int(pavilion_data.get('leftTimes', 0))
        can_use_time = int(pavilion_data.get('canusetime', 0))
        day_num = int(pavilion_data.get('dayNum', 0))

        # 1. فحص توفر مرات سحب مجانية متبقية اليوم
        if left_times <= 0:
            return False, left_times, can_use_time, day_num, "تم استهلاك كافة مرات الاستكشاف المجانية اليومية"

        # 2. فحص فترة التهدئة الفاصلة
        if can_use_time > now_ts:
            rem_sec = can_use_time - now_ts
            rem_min = rem_sec // 60
            return False, left_times, can_use_time, day_num, f"قيد فترة التهدئة (متبقي {rem_min} دقيقة و {rem_sec % 60} ثانية)"

        # الاستكشاف المجاني جاهز ومتاح فوراً
        return True, left_times, can_use_time, day_num, "جاهز للاستكشاف المجاني"

    async def run(self) -> TaskResult:
        self.log.info("💎 بدء فحص مهمة جناح الكنز (Treasure Pavilion)...")

        is_ready, left_times, can_use_time, day_num, reason = self.get_free_status()
        now_ts = int(time.time())

        # ── التحقق الصارم قبل إرسال أي طلب ────────────────────────────
        if not is_ready:
            # حساب أقرب موعد للمحاولة القادمة
            if left_times > 0 and can_use_time > now_ts:
                retry_after = max(10, can_use_time - now_ts + 5)
                self.log.info(f"⏳ [جناح الكنز] {reason}. إيقاف المهمة الآن لمنع استهلاك الذهب (إعادة المحاولة بعد {retry_after // 60} د).")
                return TaskResult.ok(
                    f"جناح الكنز قيد التهدئة: {reason}",
                    status="cooldown",
                    retry_after=retry_after,
                    left_times=left_times,
                    day_num=day_num
                )
            else:
                self.log.info(f"ℹ️ [جناح الكنز] لا يوجد استكشاف مجاني متاح ({reason}). تم إنهاء المهمة بأمان تام دون طلب.")
                return TaskResult.ok(
                    f"لا يوجد استكشاف مجاني متاح: {reason}",
                    status="no_free_explore",
                    retry_after=3600,
                    left_times=left_times,
                    day_num=day_num
                )

        # ── تنفيذ طلب الاستكشاف المجاني ────────────────────────────────
        self.log.info(f"✨ استكشاف مجاني متاح لجناح الكنز! (المرات المتبقية اليوم: {left_times}) — جاري الإرسال...")

        payload = {
            "nSubType": 1,
            "nType": self.PAVILION_TYPE_ID
        }

        resp = await self.conn.query('2058', '1', payload, timeout=10)

        if not resp:
            self.log.warning("⚠️ لم يتم استلام أي رد من السيرفر على طلب استكشاف جناح الكنز (Timeout).")
            return TaskResult.fail("انتهت مهلة انتظار رد السيرفر على طلب جناح الكنز", retry_after=60)

        err_code = str(resp.get('err', '-1'))
        if err_code == '0':
            data = resp.get('data', {})
            rewards = data.get('reward', [])
            total_num = data.get('totalNum', 0)
            new_day_num = data.get('dayNum', day_num + 1)
            new_left = max(0, left_times - 1)

            self.log.info(f"🎉 تم استكشاف جناح الكنز مجاناً بنجاح! المكافأة: {rewards} | المرات المتبقية: {new_left}")

            # تحديث الذاكرة المؤقتة المحلية لمنع أي استدعاء متكرر خاطئ
            try:
                enlist_ctrl = self.conn.init_data.setdefault('heroEnlistCtrl', {})
                enlist_data = enlist_ctrl.setdefault('heroEnlistData', {})
                pav_data = enlist_data.setdefault(str(self.PAVILION_TYPE_ID), {})
                pav_data['leftTimes'] = new_left
                pav_data['canusetime'] = now_ts + self.COOLDOWN_SECONDS
                pav_data['dayNum'] = new_day_num
                pav_data['totalNum'] = total_num
            except Exception:
                pass

            # جدولة الفحص القادم بعد انتهاء فترة التهدئة إذا كان هناك مرات متبقية
            next_retry = (self.COOLDOWN_SECONDS + 10) if new_left > 0 else 3600

            return TaskResult.ok(
                f"تم استكشاف جناح الكنز مجاناً بنجاح (متبقي {new_left} اليوم)",
                status="success",
                rewards=rewards,
                left_times=new_left,
                day_num=new_day_num,
                total_num=total_num,
                retry_after=next_retry
            )
        else:
            self.log.warning(f"⚠️ فشل استكشاف جناح الكنز من السيرفر (كود الخطأ: {err_code})")
            return TaskResult.fail(f"فشل السيرفر في استكشاف جناح الكنز (err={err_code})", retry_after=300)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Treasure Pavilion Task — مهمة استكشاف جناح الكنز المجاني")
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
            if 'heroEnlistCtrl' in conn.init_data and conn.init_data['heroEnlistCtrl']:
                break

        task = TreasurePavilionTask(conn)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
