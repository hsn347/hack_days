# -*- coding: utf-8 -*-
"""
tasks/alliance_treasure.py — مهمة صندوق التحالف المجاني (Alliance Treasure)
═════════════════════════════════════════════════════════════════════════
البروتوكول:
  CMD: 2015 (CMD_ALLIANCE_TREASURE_MODULE)
  SUBCMD: 1 (REQ_ALLIANCE_TREASURE_INIT) -> استعلام بيانات وحالة الصناديق والمحاولات المجانية
  SUBCMD: 3 (REQ_ALLIANCE_TREASURE_DIG)  -> بدء حفر صندوق التحالف: {"index": 1}
  SUBCMD: 4 (REQ_ALLIANCE_TREASURE_REQUEST_HELP) -> طلب مساعدة أعضاء التحالف لتسريع الفتح
  SUBCMD: 6 (REQ_ALLIANCE_TREASURE_RECEIVE)      -> استلام جوائز الصندوق المكتمل

⚠️ تحذير أمان صارم (Gold Protection):
  نفس الطلب (2015/3) يستهلك 50 ذهباً (digCostGold) إذا لم يكن الحفر المجاني متاحاً!
  لذلك تفحص المهمة بيانات السيرفر قبل إرسال أي طلب:
    1. التأكد من انضمام الحساب إلى تحالف.
    2. استلام أي صناديق مكتملة جاهزة للاستلام فوراً (canReceive == True).
    3. التأكد من عدم وجود صندوق قيد الحفر حالياً (isDigging).
    4. التأكد من توفر محاولات حفر متبقية اليوم (digCount < maxDigCount حيث الحد اليومي 8).
    5. التأكد من انتهاء وقت الانتظار المجاني (nextFreeDigTime == 0 أو nextFreeDigTime <= now).
    6. إذا لم يكن الحفر مجانياً 100%، تنهي المهمة فوراً دون أي طلب لحماية الذهب نهائياً.

هذه المهمة تنتمي إلى MANDATORY_TASKS وتعمل تلقائياً في كل دورة وبشكل مستقل.
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

log = logging.getLogger("AllianceTreasureTask")


class AllianceTreasureTask(BaseTask):
    """مهمة فحص واستلام وحفر صندوق التحالف المجاني مع التحقق الصارم لحماية الذهب."""

    name = "alliance_treasure"

    CMD_ALLIANCE_TREASURE = "2015"
    REQ_INIT = "1"
    REQ_DIG = "3"
    REQ_CALL_HELP = "4"
    REQ_RECEIVE = "6"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    async def get_free_status(self, force_query: bool = True) -> Dict[str, Any]:
        """
        استعلام وفحص حالة صندوق التحالف والمحاولات المجانية.
        
        Returns:
            dict يتضمن:
              - ready (bool): هل يوجد إجراء مجاني جاهز للتنفيذ الآن (استلام أو حفر)؟
              - in_alliance (bool): هل الحساب منضم لتحالف؟
              - free_dig_ready (bool): هل الحفر المجاني متاح دون أي استهلاك للذهب؟
              - can_receive_list (list): قائمة الصناديق المكتملة الجاهزة للاستلام فوراً.
              - is_digging (bool): هل يوجد صندوق قيد الحفر حالياً؟
              - dig_remain (int): الثواني المتبقية لانتهاء الحفر الحالي.
              - dig_count (int): عدد مرات الحفر المنجزة اليوم.
              - max_dig_count (int): الحد الأقصى للحفر اليومي (افتراضياً 8).
              - left_free_today (int): المحاولات المتبقية اليوم.
              - next_free_dig_time (int): توقيت انتهاء فترة الانتظار المجانية.
              - treasure_info (list): قائمة الصناديق المعروضة للحفر.
              - message (str): نص وصفي للحالة بالعربية.
        """
        now_ts = int(time.time())
        init_data = getattr(self.conn, "init_data", {})
        
        # التحقق الأولي من عضوية التحالف
        member_mgr = init_data.get("memberMgr", {})
        own_member = member_mgr.get("ownMember") if isinstance(member_mgr, dict) else None
        has_alliance = bool(own_member and isinstance(own_member, dict) and own_member.get("aid"))

        # جلب أحدث بيانات صندوق التحالف عبر 2015/1
        cached_ctrl = init_data.get("allianceTreasureCtrl", {})
        raw_data = cached_ctrl.get("data") if isinstance(cached_ctrl, dict) else None

        if force_query or not raw_data:
            try:
                resp = await self.conn.query(self.CMD_ALLIANCE_TREASURE, self.REQ_INIT, {}, timeout=6)
                if resp and str(resp.get("err", "-1")) == "0":
                    raw_data = resp.get("data") or resp.get("rspdata") or {}
                    init_data.setdefault("allianceTreasureCtrl", {})["data"] = raw_data
                    has_alliance = True
                elif resp and str(resp.get("err")) in ("10002", "10003", "10004", "10005"):
                    has_alliance = False
            except Exception as ex:
                log.debug(f"خطأ أثناء استعلام صندوق التحالف 2015/1: {ex}")

        if not has_alliance:
            return {
                "ready": False,
                "in_alliance": False,
                "free_dig_ready": False,
                "can_receive_list": [],
                "is_digging": False,
                "dig_remain": 0,
                "dig_count": 0,
                "max_dig_count": 8,
                "left_free_today": 0,
                "next_free_dig_time": 0,
                "treasure_info": [],
                "message": "⚠️ الحساب غير منضم إلى أي تحالف حالياً",
            }

        data = raw_data or {}
        other_info = data.get("otherInfo", {}) if isinstance(data.get("otherInfo"), dict) else {}
        treasure_info = data.get("treasureInfo", []) if isinstance(data.get("treasureInfo"), list) else []
        dig_list_info = data.get("digListInfo", []) if isinstance(data.get("digListInfo"), list) else []

        # فحص الصناديق الجاهزة للاستلام (canReceive == True أو انتهى وقتها)
        can_receive_list: List[Dict[str, Any]] = []
        active_digs: List[Dict[str, Any]] = []

        for d in dig_list_info:
            if not isinstance(d, dict):
                continue
            endtime = int(d.get("endtime", 0))
            if bool(d.get("canReceive")) or (endtime > 0 and endtime <= now_ts):
                can_receive_list.append(d)
            elif endtime > now_ts:
                active_digs.append(d)

        is_digging = len(active_digs) > 0
        dig_remain = max(0, active_digs[0].get("endtime", 0) - now_ts) if is_digging else 0

        # فحص إمكانية الحفر المجاني
        dig_count = int(other_info.get("digCount", 0))
        max_dig_count = int(other_info.get("maxDigCount", 8))
        next_free_dig_time = int(other_info.get("nextFreeDigTime", 0))
        left_free_today = max(0, max_dig_count - dig_count)

        # الحفر المجاني متاح فقط إذا:
        # 1. لم نستهلك كل المحاولات اليومية
        # 2. انقضى وقت الانتظار المجاني
        # 3. لا يوجد صندوق قيد الحفر حالياً
        free_dig_ready = (
            left_free_today > 0
            and (next_free_dig_time <= now_ts or next_free_dig_time == 0)
            and not is_digging
        )

        ready = bool(can_receive_list or free_dig_ready)

        if can_receive_list:
            msg = f"🎁 يوجد {len(can_receive_list)} صندوق تحالف مكتمل جاهز للاستلام فوراً!"
        elif free_dig_ready:
            msg = f"🎁 حفر صندوق التحالف المجاني متاح وجاهز فوراً! (متبقي {left_free_today}/{max_dig_count} اليوم)"
        elif is_digging:
            rem_m = max(1, dig_remain // 60)
            msg = f"⏳ صندوق التحالف قيد الحفر حالياً (متبقي {rem_m} دقيقة | تم {dig_count}/{max_dig_count} اليوم)"
        elif left_free_today <= 0:
            msg = f"✅ تم استهلاك كافة محاولات حفر صناديق التحالف اليوم ({max_dig_count}/{max_dig_count})"
        elif next_free_dig_time > now_ts:
            cd_m = max(1, (next_free_dig_time - now_ts) // 60)
            msg = f"⏳ صندوق التحالف في فترة تبريد فاصلة (متبقي {cd_m} دقيقة | تم {dig_count}/{max_dig_count} اليوم)"
        else:
            msg = "صندوق التحالف غير متاح للحفر المجاني حالياً"

        return {
            "ready": ready,
            "in_alliance": True,
            "free_dig_ready": free_dig_ready,
            "can_receive_list": can_receive_list,
            "is_digging": is_digging,
            "dig_remain": dig_remain,
            "dig_count": dig_count,
            "max_dig_count": max_dig_count,
            "left_free_today": left_free_today,
            "next_free_dig_time": next_free_dig_time,
            "treasure_info": treasure_info,
            "message": msg,
        }

    async def run(self) -> TaskResult:
        """تنفيذ مهمة صندوق التحالف مع ضمان الأمان وحماية الذهب."""
        self.log.info("📦 بدء فحص مهمة صندوق التحالف (Alliance Treasure)...")

        # ── الخطوة 1: استعلام الحالة الأولي ──────────────────────────────────
        st = await self.get_free_status(force_query=True)

        if not st.get("in_alliance"):
            self.log.info(f"ℹ️ [صندوق التحالف] {st.get('message')}. تخطي المهمة بأمان.")
            return TaskResult(success=True, message=st.get("message", "غير منضم لتحالف"))

        total_received = 0

        # ── الخطوة 2: استلام أي صناديق مكتملة جاهزة فوراً ─────────────────────
        can_receive_list = st.get("can_receive_list", [])
        if can_receive_list:
            for item in can_receive_list:
                own_uid = item.get("ownUid")
                idx = item.get("index")
                if idx is not None:
                    self.log.info(f"🎁 استلام جوائز صندوق التحالف المكتمل #{idx} (2015/6)...")
                    await asyncio.sleep(0.3)
                    r_recv = await self.conn.query(
                        self.CMD_ALLIANCE_TREASURE,
                        self.REQ_RECEIVE,
                        {"receiveType": 1, "ownUid": own_uid, "index": idx},
                        timeout=8
                    )
                    if r_recv and str(r_recv.get("err", "-1")) == "0":
                        total_received += 1
                        self.log.info(f"✅ تم استلام جوائز صندوق التحالف #{idx} بنجاح!")
                    else:
                        err = r_recv.get("err") if r_recv else "timeout"
                        self.log.warning(f"⚠️ تعذر استلام صندوق التحالف #{idx}: {err}")

            # إعادة تحديث الحالة بعد الاستلام
            st = await self.get_free_status(force_query=True)

        # ── الخطوة 3: التحقق الصارم من توفر الحفر المجاني ─────────────────────
        if not st.get("free_dig_ready"):
            reason_msg = st.get("message", "لا يوجد حفر مجاني جاهز الآن")
            self.log.info(f"ℹ️ [صندوق التحالف] {reason_msg}. إنهاء المهمة بأمان تام لحماية الذهب.")
            
            if total_received > 0:
                return TaskResult(
                    success=True,
                    message=f"🎁 تم استلام {total_received} صندوق مكتمل بنجاح! ({reason_msg})",
                    data={"received": total_received}
                )
            return TaskResult(success=True, message=reason_msg, data={"free_dig_ready": False})

        # ── الخطوة 4: تحديد رقم الصندوق المستهدف وبدء الحفر (2015/3) ───────────
        target_index = int(self.config.get("index", 1))
        treasure_info = st.get("treasure_info", [])

        # التأكد من وجود الصندوق برقم index، وإن لم يوجد نأخذ أول صندوق معروض
        available_indices = [int(t.get("index", 0)) for t in treasure_info if isinstance(t, dict)]
        if target_index not in available_indices and available_indices:
            target_index = available_indices[0]

        self.log.info(f"📦 إرسال طلب حفر صندوق التحالف المجاني (2015/3) للصندوق رقم: {target_index}...")
        resp_dig = await self.conn.query(
            self.CMD_ALLIANCE_TREASURE,
            self.REQ_DIG,
            {"index": target_index},
            timeout=8
        )

        if not resp_dig or str(resp_dig.get("err", "-1")) != "0":
            err = resp_dig.get("err") if resp_dig else "timeout"
            self.log.error(f"❌ فشل بدء حفر صندوق التحالف: {err}")
            return TaskResult(success=False, message=f"فشل حفر صندوق التحالف: {err}")

        # استخراج بيانات الحفر الجديد
        dig_data = resp_dig.get("data") or resp_dig.get("rspdata") or {}
        new_dig_info = dig_data.get("newDigInfo", {})
        dig_real_index = new_dig_info.get("index")

        # ── الخطوة 5: طلب مساعدة التحالف لتسريع الفتح تلقائياً (2015/4) ───────
        auto_help = bool(self.config.get("auto_help", True))
        if auto_help and dig_real_index is not None:
            self.log.info(f"🤝 طلب مساعدة أعضاء التحالف لتسريع صندوق التحالف #{dig_real_index} (2015/4)...")
            await asyncio.sleep(0.3)
            try:
                await self.conn.query(
                    self.CMD_ALLIANCE_TREASURE,
                    self.REQ_CALL_HELP,
                    {"index": dig_real_index},
                    timeout=6
                )
                self.log.info(f"✅ تم إرسال طلب مساعدة التحالف للصندوق #{dig_real_index} بنجاح.")
            except Exception as e_help:
                self.log.debug(f"تنبيه أثناء طلب مساعدة التحالف: {e_help}")

        left_times = max(0, st.get("left_free_today", 1) - 1)
        res_msg = f"🎁 تم حفر صندوق التحالف المجاني #{target_index} بنجاح وطلب المساعدة (متبقي {left_times} اليوم)"
        self.log.info(f"🎉 {res_msg}")

        return TaskResult(
            success=True,
            message=res_msg,
            data={
                "index": target_index,
                "dig_index": dig_real_index,
                "left_free_today": left_times,
                "received": total_received,
            }
        )
