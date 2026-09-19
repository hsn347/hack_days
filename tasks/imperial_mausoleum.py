# -*- coding: utf-8 -*-
"""
tasks/imperial_mausoleum.py — مهمة الضريح الإمبراطوري (Imperial Mausoleum / Pyramid)
════════════════════════════════════════════════════════════════════════════════════════

بروتوكول الضريح الإمبراطوري:
    - الاستعلام الأولي:  cmd: "1045", subcmd: "1", data: {}
    - رمي النرد المجاني:  cmd: "1045", subcmd: "3", data: {}
    - استلام المكافأة:    cmd: "1045", subcmd: "5", data: {"receiveType": 0}

منطق حسم النرد الإضافي والمحاولات المجانية:
    1. يتم فحص حالة الضريح من السيرفر (pyramidCtrl.data):
       - هل توجد جائزة معلقة (award)؟
       - هل الرمي المجاني متاح (free == 1)؟
    2. في حال سقطت الرمية على "نرد إضافي مجاني" (Bonus Dice مثل 800101 أو 803201 وغيرها):
       تمنح اللعبة رمية مجانية فورية إضافية (قد تتكرر مرة أو مرتين أو ثلاث مرات).
       يقوم البوت بمواصلة الرمي مجاناً بطلب (1045/3) طالما أن النتيجة نرد إضافي،
       حتى يتم حسم الجائزة الفعلية بالكامل.
    3. بمجرد ظهور الجائزة الفعلية، يتم استلامها فوراً بطلب (1045/5 مع receiveType: 0).
    4. إذا كان هناك أكثر من رمية مجانية، تتكرر الحلقة تلقائياً حتى استهلاك كافة المجاني.
    5. إذا لم يعد هناك رمي مجاني (free == 0) ولا توجد مكافأة معلقة:
       تتوقف المهمة فوراً لحماية الذهب وعملات النحاس من أي استهلاك.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

log = logging.getLogger("ImperialMausoleumTask")


class ImperialMausoleumTask(BaseTask):
    """
    مهمة الضريح الإمبراطوري مع التعامل الكامل مع النرد الإضافي وحماية الذهب.
    """
    name = "imperial_mausoleum"

    CMD_PYRAMID_MODULE = "1045"
    REQ_INIT_DATA = "1"
    REQ_START_THROW = "3"
    REQ_RECEIVE_REWARD = "5"

    # معرفات عناصر النرد الإضافي (Bonus Dice) في كود اللعبة التي تمنح رمية إضافية مجانية
    DICE_ITEM_IDS = {800101, 803201, 803501, 803301, 803401}

    MAX_FREE_ROUNDS = 5       # الحد الأقصى للجولات المجانية المتتالية
    MAX_DICE_REROLLS = 10     # الحد الأقصى لرمي النرد الإضافي في الجولة الواحدة

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    async def get_free_status(self, force_query: bool = False) -> Tuple[bool, bool, bool, Dict[str, Any], str]:
        """
        فحص حالة المجاني في الضريح الإمبراطوري.
        تعيد: (is_ready, has_pending_award, has_free_throw, award_dict, reason)
        """
        init_data = getattr(self.conn, "init_data", {})
        pyr_ctrl = init_data.get("pyramidCtrl")

        # إذا طلبنا التحديث أو لم تكن البيانات متوفرة، نستعلم بـ 1045/1
        if force_query or not isinstance(pyr_ctrl, dict) or not pyr_ctrl.get("data"):
            resp = await self.conn.query(self.CMD_PYRAMID_MODULE, self.REQ_INIT_DATA, {}, timeout=8)
            if resp and str(resp.get("err", "-1")) == "0":
                data = resp.get("data", {})
                init_data.setdefault("pyramidCtrl", {})["data"] = data
            elif not pyr_ctrl or not pyr_ctrl.get("data"):
                return False, False, False, {}, "تعذر جلب بيانات الضريح الإمبراطوري من السيرفر (قد يكون غير مفتوح)"

        p_data = self.conn.init_data.get("pyramidCtrl", {}).get("data", {})
        if not isinstance(p_data, dict) or not p_data:
            return False, False, False, {}, "بيانات الضريح الإمبراطوري غير متوفرة"

        award = p_data.get("award", {})
        has_pending_award = isinstance(award, dict) and bool(award.get("itemid"))
        free_val = int(p_data.get("free", 0))
        has_free_throw = (free_val == 1)

        if has_pending_award:
            return True, True, has_free_throw, award, "توجد مكافأة سابقة أو نرد إضافي جاهز للاستلام/الرمي"

        if has_free_throw:
            return True, False, True, {}, "الرمي المجاني اليومي متاح وجاهز"

        return False, False, False, {}, "تم استهلاك الرمي المجاني اليومي ولا توجد مكافأة معلقة"

    def _update_local_cache(self, claim_data: Dict[str, Any]):
        """تحديث بيانات الكاش المحلي للضريح لمنع أي تناقض."""
        try:
            p_ctrl = self.conn.init_data.setdefault("pyramidCtrl", {})
            if "pyramidData" in claim_data and "data" in claim_data["pyramidData"]:
                p_ctrl["data"] = claim_data["pyramidData"]["data"]
            else:
                p_ctrl_data = p_ctrl.setdefault("data", {})
                p_ctrl_data["free"] = 0
                p_ctrl_data["award"] = {}
                p_ctrl_data["state"] = 0
        except Exception:
            pass

    async def run(self) -> TaskResult:
        self.log.info("🏛️ بدء فحص مهمة الضريح الإمبراطوري (Imperial Mausoleum)...")

        total_received: List[Dict[str, Any]] = []
        round_idx = 0

        while round_idx < self.MAX_FREE_ROUNDS:
            round_idx += 1
            # في الجولة الثانية وما بعد، نطلب استعلاماً طازجاً من السيرفر للتأكد
            force_refresh = (round_idx > 1)
            is_ready, has_pending_award, has_free_throw, award, reason = await self.get_free_status(force_query=force_refresh)

            # ── التحقق الصارم لحماية الذهب/النحاس ─────────────────────────────
            if not is_ready:
                if round_idx == 1:
                    self.log.info(f"ℹ️ [الضريح الإمبراطوري] {reason}. إنهاء المهمة بأمان تام دون طلب شبكي لحماية الذهب.")
                else:
                    self.log.info(f"ℹ️ [الضريح الإمبراطوري] انتهت كافة المحاولات المجانية المتاحة اليوم ({len(total_received)} مكافأة مستلمة).")
                break

            # ── الحالة الأولى: مكافأة أو نرد إضافي معلق مسبقاً ────────────────
            if has_pending_award:
                cur_award = award
                reroll_cnt = 0

                # إذا كانت النتيجة نرد إضافي (Bonus Dice)، نرمي مجدداً لحسم الجائزة (1 أو 2 أو 3 مرات...)
                while isinstance(cur_award, dict) and cur_award.get("itemid") in self.DICE_ITEM_IDS and reroll_cnt < self.MAX_DICE_REROLLS:
                    reroll_cnt += 1
                    self.log.info(f"🎲 النتيجة هي نرد إضافي مجاني ({cur_award.get('itemid')}) — إعادة الرمي مجاناً #{reroll_cnt} (1045/3)...")
                    await asyncio.sleep(0.4)
                    resp_dice = await self.conn.query(self.CMD_PYRAMID_MODULE, self.REQ_START_THROW, {}, timeout=10)
                    if resp_dice and str(resp_dice.get("err", "-1")) == "0":
                        cur_award = resp_dice.get("data", {}).get("award", {})
                        self.log.info(f"🎲 نتيجة الرمية الإضافية #{reroll_cnt}: {cur_award}")
                    else:
                        err = resp_dice.get("err") if resp_dice else "timeout"
                        self.log.warning(f"⚠️ خطأ أثناء رمي النرد الإضافي: {err}")
                        break

                # بعد حسم النرد والحصول على جائزة فعلية، نستلمها فوراً بطلب 1045/5
                if isinstance(cur_award, dict) and cur_award.get("itemid") and cur_award.get("itemid") not in self.DICE_ITEM_IDS:
                    self.log.info(f"✨ مكافأة جاهزة للاستلام: {cur_award} — جاري الاستلام بطلب (1045/5)...")
                    await asyncio.sleep(0.3)
                    resp_claim = await self.conn.query(
                        self.CMD_PYRAMID_MODULE,
                        self.REQ_RECEIVE_REWARD,
                        {"receiveType": 0},
                        timeout=10
                    )

                    if resp_claim and str(resp_claim.get("err", "-1")) == "0":
                        c_data = resp_claim.get("data", {})
                        rec_award = c_data.get("award", cur_award)
                        total_received.append(rec_award)
                        self.log.info(f"🎉 تم استلام مكافأة الضريح بنجاح: {rec_award}")
                        self._update_local_cache(c_data)
                        await asyncio.sleep(0.4)
                        continue  # فحص الجولة التالية إن كان هناك رمي مجاني آخر
                    else:
                        err = resp_claim.get("err") if resp_claim else "timeout"
                        self.log.warning(f"⚠️ تنبيه عند استلام مكافأة الضريح: {err}")
                        break

            # ── الحالة الثانية: النرد المجاني متاح (free == 1) ───────────────────
            if has_free_throw:
                self.log.info(f"🎲 [جولة #{round_idx}] الرمي المجاني متاح في الضريح الإمبراطوري — جاري رمي النرد (1045/3)...")
                resp_throw = await self.conn.query(
                    self.CMD_PYRAMID_MODULE,
                    self.REQ_START_THROW,
                    {},
                    timeout=10
                )

                if not resp_throw or str(resp_throw.get("err", "-1")) != "0":
                    err_throw = resp_throw.get("err") if resp_throw else "timeout"
                    self.log.warning(f"⚠️ تعذر رمي نرد الضريح: {err_throw}")
                    break

                t_data = resp_throw.get("data", {})
                cur_award = t_data.get("award", {})
                self.log.info(f"🎲 نتيجة الرمية الأولى: {cur_award} (النقاط: {t_data.get('score')})")

                # التعامل مع النرد الإضافي (رمي مرة أو مرتين أو ثلاث...)
                reroll_cnt = 0
                while isinstance(cur_award, dict) and cur_award.get("itemid") in self.DICE_ITEM_IDS and reroll_cnt < self.MAX_DICE_REROLLS:
                    reroll_cnt += 1
                    self.log.info(f"🎲 سقطت الرمية على نرد إضافي مجاني ({cur_award.get('itemid')}) — مواصلة الرمي مجاناً #{reroll_cnt} (1045/3)...")
                    await asyncio.sleep(0.4)
                    resp_dice = await self.conn.query(self.CMD_PYRAMID_MODULE, self.REQ_START_THROW, {}, timeout=10)
                    if resp_dice and str(resp_dice.get("err", "-1")) == "0":
                        cur_award = resp_dice.get("data", {}).get("award", {})
                        self.log.info(f"🎲 نتيجة الرمية الإضافية #{reroll_cnt}: {cur_award}")
                    else:
                        err = resp_dice.get("err") if resp_dice else "timeout"
                        self.log.warning(f"⚠️ خطأ أثناء رمي النرد الإضافي: {err}")
                        break

                # استلام المكافأة النهائية فوراً بطلب 1045/5
                if isinstance(cur_award, dict) and cur_award.get("itemid") and cur_award.get("itemid") not in self.DICE_ITEM_IDS:
                    self.log.info("✨ جاري استلام المكافأة الناتجة فوراً بطلب (1045/5)...")
                    await asyncio.sleep(0.3)
                    resp_claim2 = await self.conn.query(
                        self.CMD_PYRAMID_MODULE,
                        self.REQ_RECEIVE_REWARD,
                        {"receiveType": 0},
                        timeout=10
                    )

                    if resp_claim2 and str(resp_claim2.get("err", "-1")) == "0":
                        c_data2 = resp_claim2.get("data", {})
                        rec_award2 = c_data2.get("award", cur_award)
                        total_received.append(rec_award2)
                        self.log.info(f"🎉 تم استلام مكافأة الضريح بنجاح: {rec_award2}")
                        self._update_local_cache(c_data2)
                        await asyncio.sleep(0.4)
                        continue  # إعادة الدوران للتحقق من أي رمية مجانية متبقية
                    else:
                        err2 = resp_claim2.get("err") if resp_claim2 else "timeout"
                        self.log.warning(f"⚠️ تنبيه عند استلام مكافأة رمي النرد: {err2}")
                        break

        if total_received:
            return TaskResult.ok(
                f"تم تنفيذ الضريح الإمبراطوري بنجاح (المكافآت المستلمة: {len(total_received)})",
                status="success",
                items=total_received,
                retry_after=3600
            )

        return TaskResult.ok("تم فحص الضريح الإمبراطوري ولا توجد عمليات معلقة", status="completed", retry_after=3600)


# ── تشغيل واختبار مباشر كملف مستقل ──────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="اختبار مهمة الضريح الإمبراطوري")
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
            if "pyramidCtrl" in conn.init_data and conn.init_data["pyramidCtrl"]:
                break
            await asyncio.sleep(0.2)

        task = ImperialMausoleumTask(conn)
        res = await task.run()
        print(f"\n📊 النتيجة النهائية: {res.message} | تفاصيل: {res.data}\n")

    asyncio.run(_test())
