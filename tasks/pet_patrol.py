# -*- coding: utf-8 -*-
"""
tasks/pet_patrol.py — مهمة دورية الحيوان الأليف واستلام المكافآت (Pet Patrol)
══════════════════════════════════════════════════════════════════════════════════════

دورة عمل المهمة:
  1. محاولة استلام مكافآت دورية الحيوان السابقة تلقائياً (3081/5).
  2. فحص حالة دورية الحيوان الحالية من petPatrolInfo (3081 / init_data).
     - إذا كان الحيوان في دورية تسير حالياً ← حساب الوقت المتبقي وتعيين موعد التكرار.
  3. إذا لم تكن هناك دورية نشطة ← إرسال الحيوان المحدد (الافتراضي: 1261 الغزال)
     إلى وجهة الدورية (3081/4).

الاستخدام كملف مستقل:
    python tasks/pet_patrol.py --email "johan2003@yopmail.com"
    python tasks/pet_patrol.py --email "sumo-1234@hotmil.com" --pet 1263 --dest 1389
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
#  الحيوان القائم بالدورية (ثابت دائماً: الغزال 1261) والحيوانات المستهدفة
# ════════════════════════════════════════════════════════════════════

PET_RUNNER_ID   = 1261    # الغزال دائماً بدون الرجوع للمستخدم
DEFAULT_PET_ID  = 1261

PET_DESTINATIONS: Dict[int, str] = {
    1262: "🦁 الأسد",
    1263: "🦅 الصقر",
    1264: "🐺 الذئب",
    1265: "🐆 الفهد",
    1266: "🐻 الدب",
    1267: "🐘 الفيل",
    1268: "🐂 الثور البري",
    1269: "🐕 كلب الكنغال",
    1270: "🐅 النمر السيفي",
    1377: "🦏 وحيد القرن",
    1380: "🔥 عنقاء العاصفة الرملية",
    1383: "🐯 النمر الثائر",
    1386: "🦎 سحلية الموت",
    1389: "🐉 الهيدرا",
}

# للتوافقية الكاملة
KNOWN_PETS = {
    1261: {"name": "🦌 الغزال (Gazelle)"},
    **{pid: {"name": pname} for pid, pname in PET_DESTINATIONS.items()}
}

DEFAULT_DESTINATION = 1262  # الأسد افتراضياً

DESTINATION_ALIASES: Dict[str, int] = {
    "1262": 1262, "اسد": 1262, "أسد": 1262, "الاسد": 1262, "الأسد": 1262, "lion": 1262,
    "1263": 1263, "صقر": 1263, "الصقر": 1263, "falcon": 1263,
    "1264": 1264, "ذئب": 1264, "الذئب": 1264, "wolf": 1264,
    "1265": 1265, "فهد": 1265, "الفهد": 1265, "leopard": 1265, "cheetah": 1265,
    "1266": 1266, "دب": 1266, "الدب": 1266, "bear": 1266,
    "1267": 1267, "فيل": 1267, "الفيل": 1267, "elephant": 1267,
    "1268": 1268, "ثور": 1268, "الثور": 1268, "ثور بري": 1268, "الثور البري": 1268, "bull": 1268,
    "1269": 1269, "كلب": 1269, "الكلب": 1269, "كنغال": 1269, "الكنغال": 1269, "كلب الكنغال": 1269, "kangal": 1269, "dog": 1269,
    "1270": 1270, "نمر سيفي": 1270, "النمر السيفي": 1270, "سيفي": 1270, "sabertooth": 1270,
    "1377": 1377, "وحيد القرن": 1377, "وحيد قرن": 1377, "rhino": 1377,
    "1380": 1380, "عنقاء": 1380, "العنقاء": 1380, "عنقاء العاصفة": 1380, "عنقاء العاصفة الرملية": 1380, "phoenix": 1380,
    "1383": 1383, "نمر ثائر": 1383, "النمر الثائر": 1383, "ثائر": 1383, "raging tiger": 1383,
    "1386": 1386, "سحلية": 1386, "السحلية": 1386, "سحلية الموت": 1386, "lizard": 1386, "death lizard": 1386,
    "1389": 1389, "هيدرا": 1389, "الهيدرا": 1389, "hydra": 1389,
}

def resolve_pet_destination(dest_input: Any) -> int:
    """تحويل اسم الحيوان المستهدف أو معرفه إلى ID صحيح من قائمة الـ 14 حيواناً."""
    if dest_input is None:
        return DEFAULT_DESTINATION
    if isinstance(dest_input, int) and dest_input in PET_DESTINATIONS:
        return dest_input
    key = str(dest_input).strip().lower()
    if key.isdigit():
        val = int(key)
        if val in PET_DESTINATIONS:
            return val
    return DESTINATION_ALIASES.get(key, DEFAULT_DESTINATION)


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (PetPatrolTask)
# ════════════════════════════════════════════════════════════════════

class PetPatrolTask(BaseTask):
    """
    مهمة دورية الحيوان الأليف (Pet Patrol).
    الحيوان القائم بالدورية: 1261 (الغزال) دائماً وأبداً.
    الوجهة (destination): الحيوان المستهدف المختار من قائمة الـ 14 حيواناً.
    """
    name = "pet_patrol"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        cfg = self.config or {}
        now_ts = int(time.time())

        # 1. الحيوان القائم بالدورية ثابت دائماً (الغزال 1261) بدون الرجوع للمستخدم
        target_pet_id = 1261

        # 2. الحيوان المستهدف (destination)
        dest_val = cfg.get('destination', cfg.get('dest', cfg.get('pet', DEFAULT_DESTINATION)))
        target_dest = resolve_pet_destination(dest_val)
        dest_name = PET_DESTINATIONS.get(target_dest, f"وجهة #{target_dest}")

        self.log.info(f"🐾 بدء مهمة دورية الحيوان الأليف [الغزال #1261] إلى الحيوان المستهدف [{dest_name}] (#{target_dest})")

        # 3. محاولة استلام مكافآت أي دورية منتهية سابقة (3081/5)
        r_rwd = await self.conn.query('3081', '5', {}, timeout=8)
        if r_rwd and str(r_rwd.get('err', '0')) == '0':
            self.log.info("🎁 تم استلام مكافآت دورية الحيوان المكتملة بنجاح! ✅")

        # 4. فحص حالة الدورية الحالية من init_data
        pet_ctrl = self.conn.init_data.get('petCtrl', {})
        if isinstance(pet_ctrl, dict):
            patrol_info = pet_ctrl.get('petPatrolInfo', {})
            if isinstance(patrol_info, dict):
                end_time = int(patrol_info.get('endTime', 0))
                active_pet_id = int(patrol_info.get('petID', 0))

                # إذا كان هناك حيوان في دورية حالياً والوقت لم ينتهِ
                if end_time > now_ts and active_pet_id > 0:
                    remaining_sec = end_time - now_ts
                    rem_min = remaining_sec // 60
                    rem_sec = remaining_sec % 60
                    self.log.info(f"🐾 الحيوان في دورية حالياً | متبقي للانتهاء: {rem_min} دقيقة و {rem_sec} ثانية")
                    return TaskResult.ok(
                        f"الحيوان في دورية حالياً (متبقي {rem_min} دقيقة)",
                        status="patrolling",
                        pet_id=active_pet_id,
                        remaining_seconds=remaining_sec,
                        end_time=end_time,
                        retry_after=remaining_sec + 30
                    )

        # 5. إرسال أمر بدء الدورية (3081/4) بـ petid: 1261 دائماً
        payload = {
            "petid": 1261,
            "destination": target_dest
        }

        r_patrol = await self.conn.query('3081', '4', payload, timeout=10)
        if not r_patrol or str(r_patrol.get('err', '0')) != '0':
            err_code = str(r_patrol.get('err', 'unknown')) if r_patrol else 'timeout'
            self.log.error(f"❌ فشل إرسال دورية الحيوان (كود السيرفر: {err_code})")
            return TaskResult.fail(f"فشل إرسال دورية الحيوان (كود {err_code})", retry_after=600)

        # 6. قراءة وقت انتهاء الدورية
        patrol_finish_time = int(r_patrol.get('patrolTime', now_ts + 3600))
        duration_sec = max(0, patrol_finish_time - now_ts)
        duration_min = duration_sec // 60

        self.log.info(f"🎉 تم إرسال الغزال في دورية إلى [{dest_name}] بنجاح! 🚀 | مدة الدورية: {duration_min} دقيقة")
        return TaskResult.ok(
            f"✅ تم إرسال الغزال في دورية إلى {dest_name} بنجاح (المدة {duration_min} دقيقة)",
            status="patrol_started",
            pet_id=1261,
            destination=target_dest,
            duration_minutes=duration_min,
            patrol_finish_time=patrol_finish_time,
            retry_after=duration_sec + 30
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Pet Patrol Task — مهمة دورية الحيوان الأليف واستلام المكافآت")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--pet", "-p", type=int, default=DEFAULT_PET_ID,
                        help=f"معرف الحيوان الأليف [افتراضي: {DEFAULT_PET_ID} الغزال]")
    parser.add_argument("--dest", "-d", type=int, default=DEFAULT_DESTINATION,
                        help=f"معرف وجهة الدورية [افتراضي: {DEFAULT_DESTINATION}]")
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
            "pet_id": args.pet,
            "destination": args.dest,
        }

        task = PetPatrolTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
