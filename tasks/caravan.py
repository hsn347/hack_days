# -*- coding: utf-8 -*-
"""
tasks/caravan.py — مهمة إرسال القافلة وحراسة الكنز (Carriage Escort / Caravan)
══════════════════════════════════════════════════════════════════════════════════════
python tasks/caravan.py --email "burcudemr@gmail.com"
دورة عمل المهمة:
  1. فحص واستلام جوائز القافلة السابقة تلقائياً (3139/8 و 3139/7).
  2. المعالجة السريعة لجميع أحداث الطريق وجمع مكافآت المسير (3139/14).
  3. فحص حالة القافلة الحالية (3139/6):
     - إذا كانت القافلة تسير حالياً ← حساب الوقت المتبقي وتجاوز الإرسال.
     - إذا لم تكن هناك قافلة نشطة ← اختيار بطل متاح وإرسال القافلة بالبهارات القصوى (3139/1).

الاستخدام كملف مستقل:
    python tasks/caravan.py --email "meik.gaertner2306.MGr@gmail.com"
    python tasks/caravan.py --email "sumo-1234@hotmil.com" --cargo 5000
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
#  ثوابت القافلة (Caravan Constants)
# ════════════════════════════════════════════════════════════════════

DEFAULT_CARGO_TYPE   = "10001"   # نوع البهارات / البضائع القياسية
DEFAULT_CARGO_AMOUNT = 5000      # الكمية القصوى الافتراضية للبضائع
DEFAULT_ARMY_ID      = 1051      # فيلق الحراسة الافتراضي


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (CaravanTask)
# ════════════════════════════════════════════════════════════════════

class CaravanTask(BaseTask):
    """
    مهمة إدارة وحراسة القافلة (Carriage Escort).
    """
    name = "caravan"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)

    async def run(self) -> TaskResult:
        cfg = self.config
        cargo_amount = int(cfg.get('cargo', DEFAULT_CARGO_AMOUNT))
        custom_hero  = cfg.get('hero_id')

        self.log.info(f"🐪 بدء مهمة القافلة وحراسة الكنز (البضائع: {cargo_amount:,})")

        # 1. المعالجة السريعة لجميع أحداث الطريق إن وجدت (3139/14)
        r_events = await self.conn.query('3139', '14', {}, timeout=8)
        if r_events and str(r_events.get('err', '0')) == '0':
            ev_data = r_events.get('data', {})
            ev_list = ev_data.get('events', [])
            rewards = ev_data.get('rewards', [])
            if ev_list or rewards:
                self.log.info(f"⚡ تمت المعالجة السريعة لـ {len(ev_list)} حدث في طريق القافلة! (مكافآت: {rewards})")

        # 2. فحص واستلام جوائز القافلة المكتملة (3139/7)
        r_claim = await self.conn.query('3139', '7', {}, timeout=8)
        if r_claim and str(r_claim.get('err', '0')) == '0':
            claim_data = r_claim.get('data', {})
            if claim_data.get('isClaimedReward'):
                self.log.info("🏆 تم استلام جوائز وصول القافلة السابقة بنجاح! ✅")

        # 3. فحص حالة القافلة الحالية (3139/6)
        r_look = await self.conn.query('3139', '6', {}, timeout=8)
        now_ts = int(time.time())

        if r_look and isinstance(r_look.get('data'), dict):
            my_carriage = r_look['data'].get('myCarriage')
            if my_carriage and isinstance(my_carriage, dict):
                build_times = my_carriage.get('buildTimes', [])
                if build_times and isinstance(build_times, list):
                    final_end_time = int(build_times[-1].get('endtime', 0))
                    # إذا كانت القافلة لا تزال تسير
                    if now_ts < final_end_time:
                        remaining_sec = final_end_time - now_ts
                        rem_min = remaining_sec // 60
                        rem_sec = remaining_sec % 60
                        cargo_info = my_carriage.get('curCargo', {})
                        self.log.info(f"🐪 القافلة تسير حالياً في الطريق | متبقي للوصول: {rem_min} دقيقة و {rem_sec} ثانية | حمولة: {cargo_info}")
                        return TaskResult.ok(
                            f"القافلة تسير في الطريق (متبقي {rem_min} دقيقة)",
                            status="marching",
                            remaining_seconds=remaining_sec,
                            arrival_time=final_end_time,
                            retry_after=remaining_sec + 30
                        )

        # 4. إذا لم تكن هناك قافلة تسير ← اختيار أفضل بطل وحيوان أليف متاحين
        hero_id = None
        if custom_hero:
            hero_id = int(custom_hero)
        else:
            # جمع الأبطال من Gate أو init_data
            heroes_pool = []
            if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
                heroes_pool = list(self.conn._gate.heroes)
            if not heroes_pool:
                hctrl = self.conn.init_data.get('heroCtrl', {})
                if isinstance(hctrl, list): heroes_pool = hctrl
                elif isinstance(hctrl, dict):
                    hlist = hctrl.get('heroList', hctrl)
                    heroes_pool = list(hlist.values()) if isinstance(hlist, dict) else list(hlist)

            # ترشيح أفضل أبطال قتال (5501xxx) حسب النجوم والمستوى والمهارات
            combat_heroes = []
            other_heroes = []
            for h in heroes_pool:
                if not isinstance(h, dict): continue
                st = h.get('status', {})
                if isinstance(st, dict) and st.get('state', 0) != 0: continue
                hid = int(h.get('id', 0))
                if hid <= 0: continue
                lv = int(h.get('lv', 1))
                star = int(h.get('star', 1))
                score = star * 50 + lv * 10
                if str(hid).startswith('5501'):
                    combat_heroes.append((hid, score))
                else:
                    other_heroes.append((hid, score))

            if combat_heroes:
                combat_heroes.sort(key=lambda x: x[1], reverse=True)
                hero_id = combat_heroes[0][0]
            elif other_heroes:
                other_heroes.sort(key=lambda x: x[1], reverse=True)
                hero_id = other_heroes[0][0]

        if not hero_id or hero_id <= 0:
            hero_id = 5501002

        # اختيار أفضل حيوان أليف متاح (أعلى رتبة ومستوى)
        pets_payload = []
        pet_ctrl = self.conn.init_data.get('petCtrl', {})
        if isinstance(pet_ctrl, dict):
            pets_dict = pet_ctrl.get('pets', {})
            if isinstance(pets_dict, dict) and pets_dict:
                sorted_pets = sorted(
                    pets_dict.values(),
                    key=lambda p: (int(p.get('step', 1)), int(p.get('lv', 1))),
                    reverse=True
                )
                best_pet_id = int(sorted_pets[0].get('id', 0))
                if best_pet_id > 0:
                    pets_payload = [best_pet_id]
                    self.log.info(f"🐾 تم تعيين أفضل حيوان أليف: ID={best_pet_id} (لفل={sorted_pets[0].get('lv')})")

        guard_army = int(cfg.get('army_id', DEFAULT_ARMY_ID))
        self.log.info(f"🎯 تعيين بطل الحراسة: {hero_id} | الفيلق: {guard_army} | الحيوان: {pets_payload} | البضائع: {cargo_amount:,}")

        # 5. إرسال أمر بدء القافلة (3139/1)
        payload = {
            "runes": {},
            "heros": [hero_id],
            "armyid": guard_army,
            "pets": pets_payload,
            "cargo": {
                DEFAULT_CARGO_TYPE: cargo_amount
            }
        }

        r_start = await self.conn.query('3139', '1', payload, timeout=10)
        if not r_start or str(r_start.get('err', '0')) != '0':
            err_code = str(r_start.get('err', 'unknown')) if r_start else 'timeout'
            if "TODAY_LIMIT_MAX" in err_code:
                self.log.info("ℹ️ تم استهلاك جميع محاولات إرسال القوافل المتاحة لهذا اليوم (الحد اليومي مكتمل) ✅")
                return TaskResult.ok(
                    "تم استهلاك الحد اليومي لإرسال القوافل لهذا اليوم",
                    status="daily_limit_reached",
                    retry_after=14400
                )
            elif "HAS_MARCHING" in err_code:
                self.log.info("ℹ️ توجد قافلة تسير بالفعل في الطريق حالياً.")
                return TaskResult.ok("توجد قافلة تسير بالفعل", status="marching", retry_after=1800)
            else:
                self.log.error(f"❌ فشل إرسال القافلة (كود السيرفر: {err_code})")
                return TaskResult.fail(f"فشل إرسال القافلة (كود {err_code})", retry_after=600)

        # 6. التحقق من بيانات القافلة بعد الإرسال
        start_data = r_start.get('data', {})
        my_c = start_data.get('myCarriage', {})
        build_times = my_c.get('buildTimes', []) if isinstance(my_c, dict) else []

        duration_min = 0
        if build_times:
            final_end = int(build_times[-1].get('endtime', 0))
            duration_sec = max(0, final_end - now_ts)
            duration_min = duration_sec // 60
            self.log.info(f"🎉 تم إرسال القافلة بنجاح! 🚀 | مدة الرحلة المتوقعة: {duration_min} دقيقة (15 محطة)")
            return TaskResult.ok(
                f"✅ تم إرسال القافلة بنجاح (مدة الرحلة {duration_min} دقيقة)",
                status="started",
                hero_id=hero_id,
                cargo=cargo_amount,
                duration_minutes=duration_min,
                arrival_time=final_end,
                retry_after=duration_sec + 30
            )

        self.log.info("🎉 تم إرسال القافلة بنجاح! ✅")
        return TaskResult.ok("✅ تم إرسال القافلة بنجاح", status="started", hero_id=hero_id)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Caravan / Carriage Escort Task — مهمة إرسال القافلة وحراسة الكنز")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--cargo", "-c", type=int, default=DEFAULT_CARGO_AMOUNT,
                        help=f"كمية البهارات/البضائع [افتراضي: {DEFAULT_CARGO_AMOUNT}]")
    parser.add_argument("--hero", type=int, default=None,
                        help="معرف البطل المخصص للحراسة [افتراضي: بطل متفرغ تلقائياً]")
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
            "cargo": args.cargo,
            "hero_id": args.hero,
        }

        task = CaravanTask(conn, task_cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
