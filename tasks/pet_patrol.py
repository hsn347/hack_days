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
#  قاموس الحيوانات الأليفة المعروفة ووجهات الدورية
# ════════════════════════════════════════════════════════════════════

KNOWN_PETS: Dict[int, Dict[str, Any]] = {
    1261: {"name": "🦌 الغزال (Gazelle)"},
    1262: {"name": "🦁 أسد (Lion)"},
    1263: {"name": "🦅 الصقر (Falcon)"},
    1264: {"name": "🐺 ذئب (Wolf)"},
    1265: {"name": "🐆 نمر / فهد (Leopard)"},
    1266: {"name": "🐻 الدب (Bear)"},
    1267: {"name": "🐘 الفيل (Elephant)"},
    1268: {"name": "🦏 وحيد القرن (Rhino)"},
    1269: {"name": "🐂 الثور البري (Wild Bull)"},
    1270: {"name": "🐕 كلب كانغال (Kangal Dog)"},
    1271: {"name": "🐅 النمر الناري (Fire Tiger)"},
    1272: {"name": "🐍 الثعبان الملكي (Royal Snake)"},
    1273: {"name": "🦅 الجريفين (Griffin)"},
    1274: {"name": "🐉 التنين (Dragon)"},
    1275: {"name": "🔥 طائر الفينيق (Phoenix)"},
}

DEFAULT_PET_ID      = 1261    # الافتراضي: الغزال (جاهز للربط مع Firebase)
DEFAULT_DESTINATION = 1389    # الوجهة القياسية الأولى


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (PetPatrolTask)
# ════════════════════════════════════════════════════════════════════

class PetPatrolTask(BaseTask):
    """
    مهمة دورية الحيوان الأليف (Pet Patrol).
    """
    name = "pet_patrol"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        cfg = self.config
        now_ts = int(time.time())

        # 1. تحديد الحيوان الأليف المستهدف
        # يمكن تمريره من Firebase أو من باراميتر المهمة أو الاعتماد على الافتراضي
        target_pet_id = int(cfg.get('pet_id', DEFAULT_PET_ID))
        target_dest   = int(cfg.get('destination', DEFAULT_DESTINATION))

        pet_name = KNOWN_PETS.get(target_pet_id, {}).get('name', f"حيوان #{target_pet_id}")
        self.log.info(f"🐾 بدء مهمة دورية الحيوان الأليف [{pet_name}] إلى الوجهة #{target_dest}")

        # 2. محاولة استلام مكافآت أي دورية منتهية سابقة (3081/5)
        r_rwd = await self.conn.query('3081', '5', {}, timeout=8)
        if r_rwd and str(r_rwd.get('err', '0')) == '0':
            self.log.info("🎁 تم استلام مكافآت دورية الحيوان المكتملة بنجاح! ✅")

        # 3. فحص حالة الدورية الحالية من init_data
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
                    active_pet_name = KNOWN_PETS.get(active_pet_id, {}).get('name', f"حيوان #{active_pet_id}")
                    self.log.info(f"🐾 {active_pet_name} في دورية حالياً | متبقي للانتهاء: {rem_min} دقيقة و {rem_sec} ثانية")
                    return TaskResult.ok(
                        f"الحيوان في دورية حالياً (متبقي {rem_min} دقيقة)",
                        status="patrolling",
                        pet_id=active_pet_id,
                        remaining_seconds=remaining_sec,
                        end_time=end_time,
                        retry_after=remaining_sec + 30
                    )

        # 4. التحقق من توفر الحيوان في حساب اللاعب
        pets_in_account = pet_ctrl.get('pets', {}) if isinstance(pet_ctrl, dict) else {}
        if isinstance(pets_in_account, dict) and pets_in_account:
            if str(target_pet_id) not in pets_in_account and target_pet_id not in pets_in_account:
                # إذا لم يكن الحيوان المطلوب مفتوحاً، نختار أول حيوان متوفر في الحساب
                first_available = next(iter(pets_in_account.keys()))
                self.log.warning(f"⚠️ الحيوان #{target_pet_id} غير مفتوح، سيتم استخدام المتوفر #{first_available}")
                target_pet_id = int(first_available)
                pet_name = KNOWN_PETS.get(target_pet_id, {}).get('name', f"حيوان #{target_pet_id}")

        # 5. إرسال أمر بدء الدورية (3081/4)
        payload = {
            "petid": target_pet_id,
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

        self.log.info(f"🎉 تم إرسال {pet_name} في دورية بنجاح! 🚀 | مدة الدورية: {duration_min} دقيقة")
        return TaskResult.ok(
            f"✅ تم إرسال {pet_name} في دورية بنجاح (المدة {duration_min} دقيقة)",
            status="patrol_started",
            pet_id=target_pet_id,
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
