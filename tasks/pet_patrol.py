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
    python tasks/pet_patrol.py --email "3r228@g.com"
    python tasks/pet_patrol.py --email "3r228@g.com" --pet 1261 --dest 1389
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
from typing import Any, Dict, List, Optional ,Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  الحيوان القائم بالدورية (ثابت دائماً: الغزال 1261) والحيوانات المستهدفة
# ════════════════════════════════════════════════════════════════════

PET_RUNNER_ID   = 1261    # الغزال دائماً بدون الرجوع للمستخدم
DEFAULT_PET_ID  = 1261

PET_DESTINATIONS: Dict[int, str] = {
    1350: "🦁 الأسد",
    1353: "🦅 الصقر",
    1360: "🐺 الذئب",
    1357: "🐆 الفهد",
    1362: "🐻 الدب",
    1365: "🐘 الفيل",
    1368: "🐂 الثور البري",
    1371: "🐕 كلب الكنغال",
    1374: "🐅 النمر السيفي",
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

DEFAULT_DESTINATION = 1350  # الأسد افتراضياً

DESTINATION_ALIASES: Dict[str, int] = {
    # الأسد 1350
    "1350": 1350, "اسد": 1350, "أسد": 1350, "الاسد": 1350, "الأسد": 1350, "lion": 1350,
    # الصقر 1353 (والسابق 1263)
    "1353": 1353, "1263": 1353, "صقر": 1353, "الصقر": 1353, "falcon": 1353,
    # الذئب 1360 (والسابق 1264)
    "1360": 1360, "1264": 1360, "ذئب": 1360, "الذئب": 1360, "wolf": 1360,
    # الفهد 1357 (والسابق 1265)
    "1357": 1357, "1265": 1357, "فهد": 1357, "الفهد": 1357, "leopard": 1357, "cheetah": 1357,
    # الدب 1362 (والسابق 1266)
    "1362": 1362, "1266": 1362, "دب": 1362, "الدب": 1362, "bear": 1362,
    # الفيل 1365 (والسابق 1267)
    "1365": 1365, "1267": 1365, "فيل": 1365, "الفيل": 1365, "elephant": 1365,
    # الثور البري 1368 (والسابق 1268)
    "1368": 1368, "1268": 1368, "ثور": 1368, "الثور": 1368, "ثور بري": 1368, "الثور البري": 1368, "bull": 1368,
    # كلب الكنغال 1371 (والسابق 1269)
    "1371": 1371, "1269": 1371, "كلب": 1371, "الكلب": 1371, "كنغال": 1371, "الكنغال": 1371, "كلب الكنغال": 1371, "kangal": 1371, "dog": 1371,
    # النمر السيفي 1374
    "1374": 1374, "نمر سيفي": 1374, "النمر السيفي": 1374, "سيفي": 1374, "sabertooth": 1374,
    # وحيد القرن 1377
    "1377": 1377, "وحيد القرن": 1377, "وحيد قرن": 1377, "rhino": 1377,
    # عنقاء العاصفة الرملية 1380
    "1380": 1380, "عنقاء": 1380, "العنقاء": 1380, "عنقاء العاصفة": 1380, "عنقاء العاصفة الرملية": 1380, "phoenix": 1380,
    # النمر الثائر 1383
    "1383": 1383, "نمر ثائر": 1383, "النمر الثائر": 1383, "ثائر": 1383, "raging tiger": 1383,
    # سحلية الموت 1386
    "1386": 1386, "سحلية": 1386, "السحلية": 1386, "سحلية الموت": 1386, "lizard": 1386, "death lizard": 1386,
    # الهيدرا 1389
    "1389": 1389, "هيدرا": 1389, "الهيدرا": 1389, "hydra": 1389,
}

def resolve_pet_destination(dest_input: Any) -> int:
    """تحويل اسم الحيوان المستهدف أو معرفه إلى ID صحيح من قائمة الـ 14 حيواناً."""
    if dest_input is None:
        return DEFAULT_DESTINATION
    if isinstance(dest_input, int):
        if dest_input in PET_DESTINATIONS:
            return dest_input
        # فحص إن كان معرفاً قديماً مسجلاً في التحويلات
        str_id = str(dest_input)
        if str_id in DESTINATION_ALIASES:
            return DESTINATION_ALIASES[str_id]
    key = str(dest_input).strip().lower()
    if key in DESTINATION_ALIASES:
        return DESTINATION_ALIASES[key]
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

    async def _unlock_pet_feature_and_gazelle(self) -> Tuple[bool, str]:
        """
        تنفيذ التسلسل الرسمي لمحرك اللعبة لفتح مبنى وخاصية الحيوان الأليف وتفعيل الغزال:
        1. إرسال حزمة الدليل التوجيهي (3078/1 guideId: 200400, state: 1) لفك قفل موديول الحيوانات.
        2. انتظار وجيز (1.0 ثانية).
        3. إرسال حزمة فتح وتفعيل الغزال المجانية (3081/1 petid: 1261, type: 1).
        4. تحديث كاش petCtrl.pets محلياً لتمكين إرسال الدوريات فوراً.
        """
        # الخطوة 1: إنهاء خطوة الدليل التوجيهي للحيوان (guideId = 200400)
        self.log.info("🐾 [الخطوة 1/2] إرسال حزمة إنهاء الدليل التوجيهي لخاصية الحيوان (3078/1: guideId 200400)...")
        r_guide = await self.conn.query('3078', '1', {"guideId": 200400, "state": 1}, timeout=8)
        g_err = str(r_guide.get('err', '-1')) if r_guide else 'timeout'
        if g_err == '0':
            self.log.info("✅ تم إنهاء خطوة الدليل التوجيهي للحيوان الأليف بنجاح (3078/1: guide 200400)!")
        else:
            self.log.debug(f"نتيجة حزمة الدليل 3078/1: {r_guide}")

        await asyncio.sleep(1.0)

        # الخطوة 2: إرسال أمر فتح وتفعيل الغزال #1261 (3081/1)
        self.log.info("🐾 [الخطوة 2/2] إرسال أمر فتح وتفعيل الغزال #1261 (3081/1)...")
        r_unlock = await self.conn.query('3081', '1', {"petid": 1261, "type": 1}, timeout=10)
        u_err = str(r_unlock.get('err', '-1')) if r_unlock else 'timeout'

        pet_ctrl = self.conn.init_data.get('petCtrl', {})
        if u_err == '0':
            self.log.info("🎉 تم فتح وتفعيل مبنى الحيوان الأليف واستلام الغزال #1261 بنجاح! 🦌")
            if isinstance(pet_ctrl, dict):
                if "pets" not in pet_ctrl:
                    pet_ctrl["pets"] = {}
                pet_ctrl["pets"]["1261"] = {"id": 1261, "lv": 1}
            await asyncio.sleep(1.5)
            return True, "success"
        elif u_err == '800009':
            self.log.info("ℹ️ الغزال #1261 مفتوح مسبقاً على السيرفر.")
            if isinstance(pet_ctrl, dict):
                if "pets" not in pet_ctrl:
                    pet_ctrl["pets"] = {}
                pet_ctrl["pets"]["1261"] = {"id": 1261, "lv": 1}
            return True, "already_unlocked"
        elif u_err == '800002':
            msg = "ℹ️ مستوى القلعة غير كافٍ لفتح الحيوان الأليف (يتطلب مستوى 13)."
            self.log.info(msg)
            return False, "castle_level_low"
        elif u_err == '14':
            msg = "ℹ️ لم تكتمل أدوات فتح الغزال بعد على السيرفر (كود 14) — في انتظار التحديث."
            self.log.info(msg)
            return False, "items_not_reach"
        else:
            msg = f"تعذر فتح الحيوان الأليف (كود {u_err})"
            self.log.warning(f"⚠️ {msg} — تخطي محاولة الدورية.")
            return False, u_err

    async def run(self) -> TaskResult:
        cfg = self.config or {}
        now_ts = int(time.time())

        self.log.debug(f"🐾 [DEBUG] إعدادات المهمة الواردة: {cfg}")

        # 1. الحيوان القائم بالدورية ثابت دائماً (الغزال 1261) بدون الرجوع للمستخدم
        target_pet_id = 1261

        # 2. الحيوان المستهدف (destination)
        dest_val = cfg.get('destination', cfg.get('dest', cfg.get('pet', DEFAULT_DESTINATION)))
        target_dest = resolve_pet_destination(dest_val)
        dest_name = PET_DESTINATIONS.get(target_dest, f"وجهة #{target_dest}")

        self.log.info(f"🐾 بدء مهمة دورية الحيوان الأليف [الغزال #1261] إلى الحيوان المستهدف [{dest_name}] (#{target_dest})")
        self.log.debug(f"🐾 [DEBUG] dest_val={dest_val} → target_dest={target_dest}")

        # 3. التحقق من مستوى القلعة (الحد الأدنى لفتح مبنى وخاصية الحيوان هو قلعة 13)
        city_ctrl = self.conn.init_data.get('cityCtrl', {}) if isinstance(self.conn.init_data, dict) else {}
        blist = city_ctrl.get('blist', []) if isinstance(city_ctrl, dict) else []
        castle_lv = 1
        for b in blist:
            if isinstance(b, dict):
                binfo = b.get('binfo', b)
                if isinstance(binfo, dict) and str(binfo.get('bid', '')) == '101':
                    try:
                        castle_lv = max(castle_lv, int(binfo.get('lv', 1)))
                    except Exception:
                        pass

        if castle_lv < 13:
            self.log.info(f"ℹ️ مستوى القلعة الحالي ({castle_lv}) أقل من 13 — مبنى الحيوان الأليف يفتح عند قلعة لفل 13. تخطي المهمة بأمان.")
            return TaskResult.ok(
                f"الحيوان الأليف غير متاح (يتطلب قلعة لفل 13، المستوى الحالي {castle_lv})",
                status="castle_level_low",
                castle_level=castle_lv,
                retry_after=7200
            )

        # 4. فحص هل الحيوان الأليف (الغزال #1261) مفتوح أم يحتاج إلى فتح وتفعيل
        pet_ctrl = self.conn.init_data.get('petCtrl', {})
        pets_data = pet_ctrl.get('pets', {}) if isinstance(pet_ctrl, dict) else {}
        is_unlocked = bool(pets_data and (1261 in pets_data or "1261" in pets_data))

        if not is_unlocked:
            self.log.info("🐾 فحص حالة الحيوان: الغزال #1261 غير مفتوح — جاري تفعيل خاصية الحيوان...")
            unlocked_ok, status_code = await self._unlock_pet_feature_and_gazelle()
            if not unlocked_ok:
                if status_code in ("castle_level_low", "items_not_reach"):
                    return TaskResult.ok(
                        f"الحيوان الأليف في مرحلة التجهيز ({status_code}) — سيُعاد الفحص في الدورة القادمة",
                        status=status_code,
                        retry_after=3600
                    )
                else:
                    return TaskResult.ok(
                        f"تعذر فتح الحيوان الأليف مؤقتاً ({status_code})",
                        status="pet_unlock_pending",
                        retry_after=1800
                    )
        else:
            self.log.info("🐾 فحص حالة الحيوان: الغزال #1261 مفتوح مسبقاً — المتابعة لإرسال الدورية مباشرة.")

        # 4. محاولة استلام مكافآت أي دورية منتهية سابقة (3081/5)
        self.log.debug("🐾 [DEBUG] إرسال طلب استلام مكافآت (3081/5)...")
        r_rwd = await self.conn.query('3081', '5', {}, timeout=8)
        self.log.debug(f"🐾 [DEBUG] نتيجة استلام المكافآت (3081/5): {r_rwd}")
        if r_rwd and str(r_rwd.get('err', '0')) == '0':
            self.log.info("🎁 تم استلام مكافآت دورية الحيوان المكتملة بنجاح! ✅")
        else:
            err = r_rwd.get('err', 'N/A') if r_rwd else 'timeout/None'
            self.log.debug(f"🐾 [DEBUG] لم يتم استلام مكافآت (err={err}) - قد لا توجد دورية منتهية")

        # 5. فحص حالة الدورية الحالية من init_data
        pet_ctrl = self.conn.init_data.get('petCtrl', {})
        self.log.debug(f"🐾 [DEBUG] petCtrl من init_data: {pet_ctrl}")

        if isinstance(pet_ctrl, dict):
            patrol_info = pet_ctrl.get('petPatrolInfo', {})
            self.log.debug(f"🐾 [DEBUG] petPatrolInfo: {patrol_info}")

            if isinstance(patrol_info, dict):
                end_time = int(patrol_info.get('endTime', 0))
                active_pet_id = int(patrol_info.get('petID', 0))
                self.log.debug(f"🐾 [DEBUG] endTime={end_time}, active_pet_id={active_pet_id}, now_ts={now_ts}, الفرق={end_time - now_ts} ثانية")

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
                else:
                    self.log.debug(f"🐾 [DEBUG] لا توجد دورية نشطة (endTime={end_time} <= now={now_ts} أو petID={active_pet_id} <= 0)")
            else:
                self.log.debug(f"🐾 [DEBUG] petPatrolInfo ليس dict: type={type(patrol_info)}")
        else:
            self.log.debug(f"🐾 [DEBUG] petCtrl ليس dict: type={type(pet_ctrl)}, value={pet_ctrl}")

        # 6. إرسال أمر بدء الدورية (3081/4) بـ petid: 1261 دائماً
        payload = {
            "petid": 1261,
            "destination": target_dest
        }

        self.log.debug(f"🐾 [DEBUG] إرسال أمر بدء الدورية (3081/4) بالحمولة: {payload}")
        r_patrol = await self.conn.query('3081', '4', payload, timeout=10)
        self.log.debug(f"🐾 [DEBUG] نتيجة بدء الدورية (3081/4): {r_patrol}")

        if not r_patrol or str(r_patrol.get('err', '0')) != '0':
            err_code = str(r_patrol.get('err', 'unknown')) if r_patrol else 'timeout'
            if err_code == "800006":
                self.log.info("ℹ️ مبنى أو خاصية دورية الحيوان الأليف غير مفتوحة في هذه القلعة (كود 800006) — تخطي المهمة بأمان.")
                return TaskResult.ok("الحيوان الأليف غير مفتوح في هذه القلعة", status="not_unlocked", retry_after=7200)

            self.log.error(f"❌ فشل إرسال دورية الحيوان (كود السيرفر: {err_code})")
            self.log.debug(f"❌ [DEBUG] الرد الكامل: {r_patrol}")
            return TaskResult.fail(f"فشل إرسال دورية الحيوان (كود {err_code})", retry_after=600)

        # 6. قراءة وقت انتهاء الدورية
        patrol_finish_time = int(r_patrol.get('patrolTime', now_ts + 3600))
        duration_sec = max(0, patrol_finish_time - now_ts)
        duration_min = duration_sec // 60

        self.log.info(f"🎉 تم إرسال الغزال في دورية إلى [{dest_name}] بنجاح! 🚀 | مدة الدورية: {duration_min} دقيقة")
        self.log.debug(f"🐾 [DEBUG] patrolTime={patrol_finish_time}, duration_sec={duration_sec}")
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
