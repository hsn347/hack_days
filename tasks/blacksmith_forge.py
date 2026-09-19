# -*- coding: utf-8 -*-
"""
tasks/blacksmith_forge.py — مهمة معمل الحدادة وصقل الرون المجاني
══════════════════════════════════════════════════════════════════
البروتوكول:
  CMD: 2065 (CMD_RUNE_MODULE)
  SUBCMD: 2 (SUBCMD_RUNE_FORGE)
  DATA: {"forgeTimes": 1}

⚠️ تحذير أمان صارم (Gold Protection):
  نفس الطلب (2065/2) يستهلك الذهب أو مسحوق الرون إذا لم يكن الصقل المجاني متاحاً!
  لذلك تفحص المهمة بيانات `runeForgeAgCtrl` في `conn.init_data`:
    1. التأكد من توفر سحبات مجانية متبقية اليوم (useTimes < 3 حيث الإجمالي اليومي 3).
    2. التأكد من انتهاء فترة التهدئة الفاصلة بين السحبات (300 ثانية = 5 دقائق)
       بحيث (cdTime == 0 أو الوقت_الحالي - cdTime >= 300).
    3. إذا لم تتوفر السحبة المجانية أو كان الحساب قيد التهدئة، تنهي المهمة فوراً
       دون إرسال أي طلب شبكي لمنع استهلاك الذهب/المواد نهائياً.

هذه المهمة تنتمي إلى MANDATORY_TASKS في bot_manager وتعمل تلقائياً في كل دورة
بدون اشتراط رأي أو تفعيل المستخدم، تماماً مثل مهمة city_harvest و treasure_pavilion.
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from tasks.base_task import BaseTask, TaskResult

log = logging.getLogger("BlacksmithForgeTask")


class BlacksmithForgeTask(BaseTask):
    """مهمة معمل الحدادة وصقل الرون اليومي المجاني مع التحقق الصارم لحماية الذهب."""

    CMD_RUNE_MODULE = "2065"
    SUBCMD_RUNE_FORGE = "2"

    FREE_FORGE_TOTAL_TIMES = 3          # عدد السحبات المجانية اليومية (FREE_FORGING_TIME في اللعبة)
    FREE_FORGE_COOLDOWN_SECONDS = 300   # فترة التهدئة الفاصلة بين السحبات (300 ثانية = 5 دقائق)

    def __init__(self, conn, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    def get_free_status(self) -> Dict[str, Any]:
        """فحص حالة الصقل المجاني في معمل الحدادة بناءً على بيانات runeForgeAgCtrl.
        
        Returns:
            dict يتضمن:
              - ready (bool): هل الصقل المجاني جاهز للإرسال الآن؟
              - left_times (int): المرات المجانية المتبقية اليوم (0 إلى 3).
              - reason (str): سبب عدم الجاهزية ('exhausted' أو 'cooldown' أو 'ok').
              - retry_after (int): الثواني المتبقية قبل إمكانية الصقل المجاني القادم.
              - message (str): رسالة توضيحية بالعربية.
        """
        now_ts = int(time.time())
        init_data = getattr(self.conn, "init_data", {})
        rf_data = init_data.get("runeForgeAgCtrl")
        if not isinstance(rf_data, dict) or not rf_data:
            return {
                "ready": False,
                "left_times": 0,
                "use_times": 0,
                "reason": "not_loaded",
                "retry_after": 60,
                "message": "بيانات معمل الحدادة (runeForgeAgCtrl) غير متوفرة في تهيئة السيرفر (قد يكون النظام غير مفتوح بعد)"
            }

        use_times = int(rf_data.get("useTimes", 0))
        cd_time = int(rf_data.get("cdTime", 0))
        left_times = max(0, self.FREE_FORGE_TOTAL_TIMES - use_times)

        # 1. فحص هل استُهلكت كامل السحبات المجانية اليومية (3 من 3)
        if left_times <= 0:
            return {
                "ready": False,
                "left_times": 0,
                "use_times": use_times,
                "reason": "exhausted",
                "retry_after": 3600,
                "message": f"تم استهلاك جميع محاولات الحدادة المجانية لليوم ({self.FREE_FORGE_TOTAL_TIMES}/{self.FREE_FORGE_TOTAL_TIMES})"
            }

        # 2. فحص فترة التهدئة الفاصلة (300 ثانية بين كل سحبة)
        if cd_time > 0 and (now_ts - cd_time) < self.FREE_FORGE_COOLDOWN_SECONDS:
            remain_cd = self.FREE_FORGE_COOLDOWN_SECONDS - (now_ts - cd_time)
            rem_min = remain_cd // 60
            rem_sec = remain_cd % 60
            return {
                "ready": False,
                "left_times": left_times,
                "use_times": use_times,
                "reason": "cooldown",
                "retry_after": remain_cd,
                "message": f"قيد فترة التهدئة (متبقي {rem_min} دقيقة و {rem_sec} ثانية)"
            }

        # 3. الصقل المجاني متاح وجاهز تماماً
        return {
            "ready": True,
            "left_times": left_times,
            "use_times": use_times,
            "reason": "ok",
            "retry_after": 0,
            "message": f"صقل مجاني متاح في معمل الحدادة (المتبقي: {left_times} اليوم)"
        }

    async def run(self) -> TaskResult:
        """تنفيذ فحص واستكشاف معمل الحدادة المجاني بدقة وأمان تام."""
        log.info("🔨 بدء فحص مهمة معمل الحدادة وصقل الرون (Blacksmith Forge)...")

        # ── الخطوة 1: فحص الأمان المسبق لمنع صرف الذهب ─────────────────────────────
        status = self.get_free_status()

        if not status["ready"]:
            msg = f"⏳ [معمل الحدادة] {status['message']}. إيقاف المهمة الآن لمنع استهلاك الذهب/المواد (إعادة المحاولة بعد {max(1, status['retry_after'] // 60)} د)."
            log.info(msg)
            return TaskResult(
                success=True,
                message=f"معمل الحدادة قيد الانتظار: {status['message']}",
                data={
                    "status": status["reason"],
                    "retry_after": status["retry_after"],
                    "left_times": status["left_times"],
                    "use_times": status.get("use_times", 0),
                }
            )

        # ── الخطوة 2: تنفيذ الصقل المجاني المؤكد ───────────────────────────────────
        log.info(f"✨ {status['message']} — جاري إرسال طلب الصقل المجاني (2065/2)...")

        try:
            res = await self.conn.query(
                self.CMD_RUNE_MODULE,
                self.SUBCMD_RUNE_FORGE,
                {"forgeTimes": 1},
                timeout=12
            )
        except Exception as e:
            err_msg = f"❌ فشل إرسال طلب صقل معمل الحدادة: {e}"
            log.error(err_msg)
            return TaskResult(success=False, message=err_msg, data={"error": str(e)})

        if not res:
            err_msg = "⚠️ لم يتم استلام رد من خادم اللعبة لطلب معمل الحدادة (2065/2)"
            log.warning(err_msg)
            return TaskResult(success=False, message=err_msg, data={"error": "no_response"})

        err_code = str(res.get("err", ""))
        if err_code not in ("0", ""):
            err_msg = f"⚠️ خادم اللعبة أعاد خطأ في صقل الحدادة (err={err_code})"
            log.warning(err_msg)
            return TaskResult(success=False, message=err_msg, data={"err": err_code, "raw": res})

        # ── الخطوة 3: معالجة نتيجة الصقل والمكافأة ─────────────────────────────────
        res_data = res.get("data", {}) if isinstance(res, dict) else {}
        items = res_data.get("items", [])
        new_use = int(res_data.get("useTimes", status.get("use_times", 0) + 1))
        new_cd = int(res_data.get("cdTime", int(time.time())))
        new_left = max(0, self.FREE_FORGE_TOTAL_TIMES - new_use)

        # تحديث كاش بيانات القلعة في الذاكرة لمنع تكرار المحاولة في نفس الدورة
        if hasattr(self.conn, "init_data") and isinstance(self.conn.init_data, dict):
            rf_cache = self.conn.init_data.setdefault("runeForgeAgCtrl", {})
            if isinstance(rf_cache, dict):
                rf_cache.update({
                    "useTimes": new_use,
                    "cdTime": new_cd,
                    "totalTimes": res_data.get("totalTimes", rf_cache.get("totalTimes", 0)),
                    "luckyValues": res_data.get("luckyValues", rf_cache.get("luckyValues", 0)),
                    "luckyLevel": res_data.get("luckyLevel", rf_cache.get("luckyLevel", 0)),
                    "quality": res_data.get("quality", rf_cache.get("quality", 0)),
                })

        success_msg = (
            f"🎉 تم صقل معمل الحدادة مجاناً بنجاح! "
            f"العتاد/الرون: {items} | "
            f"المرات المتبقية اليوم: {new_left}"
        )
        log.info(success_msg)

        return TaskResult(
            success=True,
            message=f"تم صقل معمل الحدادة مجاناً بنجاح (متبقي {new_left} اليوم)",
            data={
                "status": "success",
                "items": items,
                "left_times": new_left,
                "use_times": new_use,
                "total_times": res_data.get("totalTimes", 0),
                "retry_after": self.FREE_FORGE_COOLDOWN_SECONDS,
            }
        )


# ── تشغيل واختبار مباشر كملف مستقل ──────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import argparse
    from core.session_manager import SessionManager
    from game_client import GameConnection

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="اختبار مهمة معمل الحدادة وصقل الرون")
    parser.add_argument("--email", help="البريد الإلكتروني للحساب")
    args = parser.parse_args()

    async def _test():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة!")
            return

        target_email = args.email or next(iter(accounts.keys()))
        acc = accounts.get(target_email)
        if not acc:
            print(f"❌ الحساب {target_email} غير موجود!")
            return

        conn = GameConnection(acc)
        print(f"🔌 جاري الاتصال بالحساب: {target_email}...")
        if not await conn.connect():
            print("❌ فشل الاتصال بالحساب!")
            return

        # انتظار وصول حزم التهيئة الأولية (1000/1)
        for _ in range(20):
            if "runeForgeAgCtrl" in conn.init_data and conn.init_data["runeForgeAgCtrl"]:
                break
            await asyncio.sleep(0.2)

        task = BlacksmithForgeTask(conn)
        res = await task.run()
        print(f"\n📊 النتيجة النهائية: {res.message} | تفاصيل: {res.data}\n")

    asyncio.run(_test())
