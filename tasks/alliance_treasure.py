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
    REQ_MANUAL_REFRESH = "2"
    REQ_DIG = "3"
    REQ_CALL_HELP = "4"
    REQ_HELP_OTHER = "5"
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

        # تحليل قائمة الحفر الحالية الخاصة بي (digListInfo)
        dig_list_raw = data.get("digListInfo", [])
        dig_list: List[Dict[str, Any]] = []
        if isinstance(dig_list_raw, list):
            dig_list = [x for x in dig_list_raw if isinstance(x, dict)]
        elif isinstance(dig_list_raw, dict):
            for v in dig_list_raw.values():
                if isinstance(v, dict):
                    dig_list.append(v)
                elif isinstance(v, list):
                    dig_list.extend([x for x in v if isinstance(x, dict)])

        can_receive_list: List[Dict[str, Any]] = []
        active_digs: List[Dict[str, Any]] = []

        for d in dig_list:
            if not isinstance(d, dict):
                continue
            can_receive = d.get("canReceive") in (True, 1, "1", "true")
            endtime = int(d.get("endtime", 0))
            if can_receive or (endtime > 0 and endtime <= now_ts):
                can_receive_list.append(d)
            else:
                active_digs.append(d)

        is_digging = len(active_digs) > 0
        dig_remain = max(0, active_digs[0].get("endtime", 0) - now_ts) if is_digging else 0

        # تحليل قائمة الأعضاء الذين يمكن مساعدتهم (canHelpList)
        can_help_raw = data.get("canHelpList", {})
        can_help_list: List[Dict[str, Any]] = []

        if isinstance(can_help_raw, dict):
            for k, v in can_help_raw.items():
                if isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            can_help_list.append(item)
                elif isinstance(v, dict):
                    can_help_list.append(v)
        elif isinstance(can_help_raw, list):
            for item in can_help_raw:
                if isinstance(item, dict):
                    can_help_list.append(item)

        # تصفية الصناديق التي يمكن مساعدتها (استبعاد الحساب نفسه وفحص عدم اكتمال المساعدة)
        my_uid = str(getattr(getattr(self.conn, "creds", None), "uid", "") or "")
        unhelped_members: List[Dict[str, Any]] = []
        for m in can_help_list:
            m_uid = str(m.get("ownUid") or m.get("helpedUid") or m.get("uid") or "")
            if my_uid and m_uid == my_uid:
                continue
            is_h = m.get("isHelped")
            if is_h in (False, 0, "0", "false", None):
                unhelped_members.append(m)

        # تحليل قائمة جوائز مساعدة أعضاء التحالف (helpInfo)
        help_info_raw = data.get("helpInfo", [])
        help_list: List[Dict[str, Any]] = []
        if isinstance(help_info_raw, list):
            help_list = [x for x in help_info_raw if isinstance(x, dict)]
        elif isinstance(help_info_raw, dict):
            for v in help_info_raw.values():
                if isinstance(v, dict):
                    help_list.append(v)
                elif isinstance(v, list):
                    help_list.extend([x for x in v if isinstance(x, dict)])

        can_receive_help_rewards: List[Dict[str, Any]] = []
        for h in help_list:
            if not isinstance(h, dict):
                continue
            can_recv = h.get("canReceive") in (True, 1, "1", "true")
            endtime_h = int(h.get("endtime", 0))
            if can_recv or (endtime_h > 0 and endtime_h <= now_ts):
                can_receive_help_rewards.append(h)

        # فحص إمكانية الحفر المجاني والمساعدات
        dig_count = int(other_info.get("digCount", 0))
        max_dig_count = int(other_info.get("maxDigCount", 8))
        next_free_dig_time = int(other_info.get("nextFreeDigTime", 0))
        left_free_today = max(0, max_dig_count - dig_count)

        help_count = int(other_info.get("helpCount", 0))
        max_help_count = int(other_info.get("maxHelpCount", 10))
        left_help_today = max(0, max_help_count - help_count)

        # الحفر المجاني متاح فقط إذا:
        # 1. لم نستهلك كل المحاولات اليومية
        # 2. انقضى وقت الانتظار المجاني
        # 3. لا يوجد صندوق قيد الحفر حالياً
        free_dig_ready = (
            left_free_today > 0
            and (next_free_dig_time <= now_ts or next_free_dig_time == 0)
            and not is_digging
        )

        can_help_others = (left_help_today > 0 and len(unhelped_members) > 0)
        can_request_help = any(d.get("canCallHelp", True) not in (False, 0, "0", "false") for d in active_digs)

        ready = bool(can_receive_list or can_receive_help_rewards or free_dig_ready or can_help_others or can_request_help)

        if can_receive_list or can_receive_help_rewards:
            total_pending_claims = len(can_receive_list) + len(can_receive_help_rewards)
            msg = f"🎁 يوجد {total_pending_claims} جوائز صناديق تحالف ومساعدة جاهزة للاستلام فوراً!"
        elif free_dig_ready:
            msg = f"🎁 حفر صندوق التحالف المجاني متاح وجاهز فوراً! (متبقي {left_free_today}/{max_dig_count} اليوم)"
        elif can_help_others:
            msg = f"🤝 يوجد {len(unhelped_members)} أعضاء تحالف بانتظار المساعدة (متبقي {left_help_today}/{max_help_count} مساعدة اليوم)"
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
            "can_receive_help_rewards": can_receive_help_rewards,
            "can_help_list": can_help_list,
            "unhelped_members": unhelped_members,
            "active_digs": active_digs,
            "can_help_others": can_help_others,
            "can_request_help": can_request_help,
            "is_digging": is_digging,
            "dig_remain": dig_remain,
            "dig_count": dig_count,
            "max_dig_count": max_dig_count,
            "help_count": help_count,
            "max_help_count": max_help_count,
            "left_free_today": left_free_today,
            "left_help_today": left_help_today,
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
        total_help_rewards = 0
        total_helped = 0
        help_requested_count = 0

        # ── الخطوة 2أ: استلام أي صناديق حفر خاصة مكتملة (2015/6 - receiveType: 1) ──
        can_receive_list = st.get("can_receive_list", [])
        if can_receive_list:
            for item in can_receive_list:
                own_uid = item.get("ownUid")
                idx = item.get("index")
                if idx is not None:
                    self.log.info(f"🎁 استلام جوائز صندوق التحالف المكتمل الخاص بي #{idx} (2015/6 Type 1)...")
                    await asyncio.sleep(0.3)
                    r_recv = await self.conn.query(
                        self.CMD_ALLIANCE_TREASURE,
                        self.REQ_RECEIVE,
                        {"receiveType": 1, "ownUid": int(own_uid) if own_uid else 0, "index": int(idx)},
                        timeout=8
                    )
                    if r_recv and str(r_recv.get("err", "-1")) == "0":
                        total_received += 1
                        self.log.info(f"✅ تم استلام جوائز صندوق التحالف الخاص بي #{idx} بنجاح!")
                    else:
                        err = r_recv.get("err") if r_recv else "timeout"
                        self.log.warning(f"⚠️ تعذر استلام صندوق التحالف الخاص بي #{idx}: {err}")

        # ── الخطوة 2ب: استلام جوائز مساعدة أعضاء التحالف (2015/6 - receiveType: 2) ──
        can_receive_help_rewards = st.get("can_receive_help_rewards", [])
        if can_receive_help_rewards:
            for item in can_receive_help_rewards:
                own_uid = item.get("ownUid")
                idx = item.get("index")
                nick = item.get("nickName", f"uid:{own_uid}")
                if idx is not None and own_uid is not None:
                    self.log.info(f"🎁 استلام جائزة مساعدة العضو {nick} [UID: {own_uid}, Index: {idx}] (2015/6 Type 2)...")
                    await asyncio.sleep(0.3)
                    r_recv = await self.conn.query(
                        self.CMD_ALLIANCE_TREASURE,
                        self.REQ_RECEIVE,
                        {"receiveType": 2, "ownUid": int(own_uid), "index": int(idx)},
                        timeout=8
                    )
                    if r_recv and str(r_recv.get("err", "-1")) == "0":
                        total_help_rewards += 1
                        self.log.info(f"✅ تم استلام جائزة مساعدة العضو {nick} لصندوق #{idx} بنجاح!")
                    else:
                        err = r_recv.get("err") if r_recv else "timeout"
                        self.log.warning(f"⚠️ تعذر استلام جائزة مساعدة العضو {nick} #{idx}: {err}")

        if can_receive_list or can_receive_help_rewards:
            # إعادة تحديث الحالة بعد الاستلامات
            st = await self.get_free_status(force_query=True)

        # ── الخطوة 3: تقديم المساعدة لأعضاء التحالف (2015/5) [إلزامي وتلقائي] ──
        can_help_members = st.get("unhelped_members", [])
        current_help_count = int(st.get("help_count", 0))
        max_help_count = int(st.get("max_help_count", 10))
        left_help_slots = max(0, max_help_count - current_help_count)

        if can_help_members and left_help_slots > 0:
            self.log.info(f"🤝 فحص طلبات مساعدة أعضاء التحالف (المتاح تقديم {left_help_slots} مساعدة اليوم)...")
            for chest in can_help_members:
                if current_help_count >= max_help_count:
                    break
                h_uid = chest.get("helpedUid") or chest.get("ownUid") or chest.get("uid")
                h_idx = chest.get("helpedIndex") or chest.get("index")
                nick = chest.get("nickName", f"uid:{h_uid}")

                if h_uid is not None and h_idx is not None:
                    self.log.info(f"🤝 تقديم مساعدة صندوق التحالف للعضو {nick} [UID: {h_uid}, Index: {h_idx}] (2015/5)...")
                    await asyncio.sleep(0.3)
                    try:
                        r_help = await self.conn.query(
                            self.CMD_ALLIANCE_TREASURE,
                            self.REQ_HELP_OTHER,
                            {"helpedUid": int(h_uid), "helpedIndex": int(h_idx)},
                            timeout=6
                        )
                        if r_help and str(r_help.get("err", "-1")) == "0":
                            total_helped += 1
                            current_help_count += 1
                            chest["isHelped"] = True
                            self.log.info(f"✅ تم تقديم المساعدة للعضو {nick} بنجاح! ({current_help_count}/{max_help_count} اليوم)")
                        elif r_help and str(r_help.get("err")) == "620009":
                            self.log.info(f"ℹ️ صندوق العضو {nick} [UID: {h_uid}, Index: {h_idx}] تمت مساعدته مسبقاً من قِبل عضو آخر في التحالف.")
                        else:
                            err_h = r_help.get("err") if r_help else "timeout"
                            self.log.warning(f"⚠️ نتيجة مساعدة العضو {nick}: {err_h}")
                    except Exception as e_h:
                        self.log.debug(f"تنبيه أثناء مساعدة العضو {nick}: {e_h}")

        # ── الخطوة 4: طلب المساعدة للصناديق الجارية الخاصة بي (2015/4) [إلزامي وتلقائي] ──
        active_digs = st.get("active_digs", [])
        for d in active_digs:
            d_idx = d.get("index") or d.get("digIndex")
            if d_idx is not None:
                self.log.info(f"🤝 طلب مساعدة أعضاء التحالف للصندوق قيد الحفر #{d_idx} (2015/4)...")
                await asyncio.sleep(0.3)
                try:
                    r_ch = await self.conn.query(
                        self.CMD_ALLIANCE_TREASURE,
                        self.REQ_CALL_HELP,
                        {"index": int(d_idx)},
                        timeout=6
                    )
                    if r_ch and str(r_ch.get("err", "-1")) == "0":
                        help_requested_count += 1
                        d["canCallHelp"] = False
                        self.log.info(f"✅ تم إرسال طلب المساعدة للصندوق الجاري #{d_idx} بنجاح.")
                    elif r_ch and str(r_ch.get("err")) == "620011":
                        d["canCallHelp"] = False
                        self.log.info(f"ℹ️ تم طلب مساعدة التحالف للصندوق #{d_idx} مسبقاً.")
                    else:
                        err_ch = r_ch.get("err") if r_ch else "timeout"
                        self.log.warning(f"⚠️ نتيجة طلب مساعدة التحالف للصندوق #{d_idx}: {err_ch}")
                except Exception as e_ch:
                    self.log.debug(f"تنبيه أثناء طلب مساعدة التحالف: {e_ch}")

        # ── الخطوة 5: التحقق الصارم من توفر الحفر المجاني ─────────────────────
        if not st.get("free_dig_ready"):
            reason_msg = st.get("message", "لا يوجد حفر مجاني جاهز الآن")
            summary_parts = []
            if total_received > 0:
                summary_parts.append(f"استلام {total_received} صندوق مكتمل")
            if total_help_rewards > 0:
                summary_parts.append(f"استلام {total_help_rewards} جائزة مساعدة أعضاء")
            if total_helped > 0:
                summary_parts.append(f"مساعدة {total_helped} من أعضاء التحالف")
            if help_requested_count > 0:
                summary_parts.append(f"طلب مساعدة لـ {help_requested_count} صندوق")

            final_msg = f"{', '.join(summary_parts)} ({reason_msg})" if summary_parts else reason_msg
            self.log.info(f"ℹ️ [صندوق التحالف] {final_msg}. إنهاء المهمة بأمان لحماية الذهب.")
            
            return TaskResult(
                success=True,
                message=final_msg,
                data={
                    "received": total_received,
                    "help_rewards": total_help_rewards,
                    "helped": total_helped,
                    "help_requested": help_requested_count,
                    "free_dig_ready": False,
                }
            )

        # ── الخطوة 6: تحديد رقم الصندوق المستهدف وبدء الحفر (2015/3) ───────────
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
        dig_data = resp_dig.get("rspdata") or resp_dig.get("data") or {}
        new_dig_info = dig_data.get("newDigInfo", {})
        dig_real_index = new_dig_info.get("index")

        # ── الخطوة 7: طلب مساعدة التحالف للصندوق الجديد (2015/4) [إلزامي وتلقائي] ──
        if dig_real_index is not None:
            self.log.info(f"🤝 طلب مساعدة أعضاء التحالف لتسريع صندوق التحالف الجديد #{dig_real_index} (2015/4)...")
            await asyncio.sleep(0.5)
            try:
                r_call = await self.conn.query(
                    self.CMD_ALLIANCE_TREASURE,
                    self.REQ_CALL_HELP,
                    {"index": int(dig_real_index)},
                    timeout=6
                )
                if r_call and str(r_call.get("err", "-1")) == "0":
                    help_requested_count += 1
                    self.log.info(f"✅ تم إرسال طلب مساعدة التحالف للصندوق #{dig_real_index} بنجاح.")
                elif r_call and str(r_call.get("err")) == "620011":
                    self.log.info(f"ℹ️ تم طلب مساعدة التحالف للصندوق #{dig_real_index} مسبقاً.")
                else:
                    err_c = r_call.get("err") if r_call else "timeout"
                    self.log.warning(f"⚠️ نتيجة طلب مساعدة الصندوق #{dig_real_index}: {err_c}")
            except Exception as e_help:
                self.log.debug(f"تنبيه أثناء طلب مساعدة التحالف: {e_help}")

        left_times = max(0, st.get("left_free_today", 1) - 1)
        res_msg = f"🎁 تم حفر صندوق التحالف المجاني #{target_index} بنجاح"
        if total_received > 0:
            res_msg += f" واستلام {total_received} صندوق"
        if total_help_rewards > 0:
            res_msg += f" واستلام {total_help_rewards} جائزة مساعدة"
        if help_requested_count > 0:
            res_msg += " وطلب المساعدة"
        if total_helped > 0:
            res_msg += f" ومساعدة {total_helped} أعضاء"
        res_msg += f" (متبقي {left_times} اليوم)"

        self.log.info(f"🎉 {res_msg}")

        return TaskResult(
            success=True,
            message=res_msg,
            data={
                "index": target_index,
                "dig_index": dig_real_index,
                "left_free_today": left_times,
                "received": total_received,
                "help_rewards": total_help_rewards,
                "helped": total_helped,
                "help_requested": help_requested_count,
            }
        )
