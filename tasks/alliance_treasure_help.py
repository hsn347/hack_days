"""
tasks/alliance_treasure_help.py — مهمة طلب مساعدة كنز التحالف واستلام الجوائز (2015/4 & 2015/6)

المهام المنفذة:
  1. الاستعلام المسبق عن حالة كنز التحالف (2015/1).
  2. استلام أي صناديق حفر خاصة مكتملة جاهزة للاستلام (2015/6 - receiveType: 1).
  3. استلام أي جوائز مساعدة أعضاء التحالف المكتملة (2015/6 - receiveType: 2).
  4. فحص الصناديق قيد الحفر النشطة وإرسال طلب المساعدة للأعضاء (2015/4) برقم index الحفر الفعلي.
"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from .base_task import BaseTask, TaskResult

log = logging.getLogger("AllianceTreasureHelpTask")


class AllianceTreasureHelpTask(BaseTask):
    """مهمة طلب مساعدة كنز التحالف واستلام كافة الجوائز المكتملة تلقائياً."""

    CMD_ALLIANCE_TREASURE = "2015"
    REQ_INIT = "1"         # استعلام حالة كنز التحالف
    REQ_CALL_HELP = "4"    # طلب مساعدة التحالف للصندوق قيد الحفر
    REQ_RECEIVE = "6"      # استلام جوائز الصندوق (receiveType 1: حفري, receiveType 2: مساعدة)

    def __init__(self, conn, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        email_str = getattr(self, "email", "") or getattr(conn, "email", "unknown")
        self.log = logging.getLogger(f"task.alliance_treasure_help[{email_str}]")

    async def get_status(self, force_query: bool = True) -> Dict[str, Any]:
        """استعلام الحالة المسبقة لكنز التحالف والصناديق الجارية وجوائز الاستلام."""
        now_ts = int(time.time())

        raw_data = await self.conn.query(self.CMD_ALLIANCE_TREASURE, self.REQ_INIT, {}, timeout=8)
        if not raw_data or str(raw_data.get("err", "-1")) != "0":
            err_code = str(raw_data.get("err", "")) if raw_data else ""
            if err_code == "620005":
                return {
                    "in_alliance": False,
                    "can_receive_own": [],
                    "can_receive_help": [],
                    "active_digs": [],
                    "message": "⚠️ الحساب غير منضم إلى أي تحالف حالياً",
                }
            return {
                "in_alliance": True,
                "can_receive_own": [],
                "can_receive_help": [],
                "active_digs": [],
                "message": f"⚠️ فشل استعلام كنز التحالف: {err_code or 'timeout'}",
            }

        data = raw_data.get("rspdata") or raw_data.get("data") or {}

        # 1. تحليل صناديق الحفر الخاصة بي (digListInfo)
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

        can_receive_own: List[Dict[str, Any]] = []
        active_digs: List[Dict[str, Any]] = []

        for d in dig_list:
            if not isinstance(d, dict):
                continue
            can_recv = d.get("canReceive") in (True, 1, "1", "true")
            endtime = int(d.get("endtime", 0))
            if can_recv or (endtime > 0 and endtime <= now_ts):
                can_receive_own.append(d)
            else:
                active_digs.append(d)

        # 2. تحليل جوائز مساعدة أعضاء التحالف (helpInfo)
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

        can_receive_help: List[Dict[str, Any]] = []
        for h in help_list:
            if not isinstance(h, dict):
                continue
            can_recv_h = h.get("canReceive") in (True, 1, "1", "true")
            endtime_h = int(h.get("endtime", 0))
            if can_recv_h or (endtime_h > 0 and endtime_h <= now_ts):
                can_receive_help.append(h)

        return {
            "in_alliance": True,
            "can_receive_own": can_receive_own,
            "can_receive_help": can_receive_help,
            "active_digs": active_digs,
            "message": "تم استعلام بيانات كنز التحالف بنجاح",
        }

    async def run(self) -> TaskResult:
        """تنفيذ مهمة استلام الجوائز وطلب المساعدة بعد الاستعلام المسبق."""
        self.log.info("🤝 بدء مهمة طلب مساعدة كنز التحالف واستلام الجوائز...")

        # ── الخطوة 1: الاستعلام المسبق ───────────────────────────────────────
        st = await self.get_status(force_query=True)
        if not st.get("in_alliance"):
            self.log.info(f"ℹ️ [طلب مساعدة التحالف] {st.get('message')}. تخطي المهمة.")
            return TaskResult(success=True, message=st.get("message", "غير منضم لتحالف"))

        total_received_own = 0
        total_received_help = 0
        total_help_calls = 0

        # ── الخطوة 2: استلام صناديق الحفر الخاصة المكتملة (2015/6 Type 1) ─────
        can_receive_own = st.get("can_receive_own", [])
        if can_receive_own:
            self.log.info(f"🎁 رصد {len(can_receive_own)} صندوق حفر مكتمل خاص بي جاهز للاستلام...")
            for item in can_receive_own:
                own_uid = item.get("ownUid")
                idx = item.get("index")
                if idx is not None:
                    self.log.info(f"🎁 استلام جائزة صندوق الحفر الخاص بي #{idx} (2015/6 - Type 1)...")
                    await asyncio.sleep(0.3)
                    try:
                        r_recv = await self.conn.query(
                            self.CMD_ALLIANCE_TREASURE,
                            self.REQ_RECEIVE,
                            {"receiveType": 1, "ownUid": int(own_uid) if own_uid else 0, "index": int(idx)},
                            timeout=8
                        )
                        if r_recv and str(r_recv.get("err", "-1")) == "0":
                            total_received_own += 1
                            self.log.info(f"✅ تم استلام جائزة صندوق الحفر الخاص #{idx} بنجاح!")
                        else:
                            err_r = r_recv.get("err") if r_recv else "timeout"
                            self.log.warning(f"⚠️ تعذر استلام صندوق الحفر الخاص #{idx}: {err_r}")
                    except Exception as e_r:
                        self.log.debug(f"تنبيه أثناء استلام صندوق الحفر #{idx}: {e_r}")

        # ── الخطوة 3: استلام جوائز مساعدة أعضاء التحالف (2015/6 Type 2) ───────
        can_receive_help = st.get("can_receive_help", [])
        if can_receive_help:
            self.log.info(f"🎁 رصد {len(can_receive_help)} جائزة مساعدة أعضاء تحالف جاهزة للاستلام...")
            for item in can_receive_help:
                own_uid = item.get("ownUid")
                idx = item.get("index")
                nick = item.get("nickName", f"uid:{own_uid}")
                if idx is not None and own_uid is not None:
                    self.log.info(f"🎁 استلام جائزة مساعدة العضو {nick} [UID: {own_uid}, Index: {idx}] (2015/6 - Type 2)...")
                    await asyncio.sleep(0.3)
                    try:
                        r_help_recv = await self.conn.query(
                            self.CMD_ALLIANCE_TREASURE,
                            self.REQ_RECEIVE,
                            {"receiveType": 2, "ownUid": int(own_uid), "index": int(idx)},
                            timeout=8
                        )
                        if r_help_recv and str(r_help_recv.get("err", "-1")) == "0":
                            total_received_help += 1
                            self.log.info(f"✅ تم استلام جائزة مساعدة العضو {nick} لصندوق #{idx} بنجاح!")
                        else:
                            err_hr = r_help_recv.get("err") if r_help_recv else "timeout"
                            self.log.warning(f"⚠️ تعذر استلام جائزة مساعدة العضو {nick} #{idx}: {err_hr}")
                    except Exception as e_hr:
                        self.log.debug(f"تنبيه أثناء استلام جائزة مساعدة العضو {nick}: {e_hr}")

        # إعادة الاستعلام إذا حدث استلام لتحديث قائمة الحفر الجارية بدقة
        if can_receive_own or can_receive_help:
            st = await self.get_status(force_query=True)

        # ── الخطوة 4: طلب مساعدة التحالف للصناديق الجارية (2015/4) ─────────────
        active_digs = st.get("active_digs", [])
        if active_digs:
            self.log.info(f"🤝 فحص الصناديق قيد الحفر لطلب المساعدة ({len(active_digs)} صندوق جارٍ)...")
            for d in active_digs:
                d_idx = d.get("index") or d.get("digIndex")
                if d_idx is not None:
                    self.log.info(f"🤝 إرسال طلب مساعدة التحالف للصندوق قيد الحفر #{d_idx} (2015/4)...")
                    await asyncio.sleep(0.4)
                    try:
                        r_call = await self.conn.query(
                            self.CMD_ALLIANCE_TREASURE,
                            self.REQ_CALL_HELP,
                            {"index": int(d_idx)},
                            timeout=6
                        )
                        if r_call and str(r_call.get("err", "-1")) == "0":
                            total_help_calls += 1
                            self.log.info(f"✅ تم إرسال طلب مساعدة التحالف للصندوق #{d_idx} بنجاح!")
                        elif r_call and str(r_call.get("err")) == "620011":
                            self.log.info(f"ℹ️ تم طلب مساعدة التحالف للصندوق #{d_idx} مسبقاً.")
                        elif r_call and str(r_call.get("err")) == "620003":
                            self.log.info(f"ℹ️ الصندوق #{d_idx} تمت مساعدته بالفعل من قبل عضو في التحالف.")
                        else:
                            err_c = r_call.get("err") if r_call else "timeout"
                            self.log.warning(f"⚠️ نتيجة طلب مساعدة التحالف للصندوق #{d_idx}: {err_c}")
                    except Exception as e_call:
                        self.log.debug(f"تنبيه أثناء إرسال طلب مساعدة التحالف للصندوق #{d_idx}: {e_call}")
        else:
            self.log.info("ℹ️ لا توجد صناديق قيد الحفر حالياً لطلب المساعدة لها.")

        # تجميع الرسالة النهائية
        summary = []
        if total_received_own > 0:
            summary.append(f"استلام {total_received_own} صندوق خاص")
        if total_received_help > 0:
            summary.append(f"استلام {total_received_help} جائزة مساعدة أعضاء")
        if total_help_calls > 0:
            summary.append(f"طلب مساعدة لـ {total_help_calls} صندوق")

        final_msg = f"🤝 تم فحص طلب مساعدة كنز التحالف بنجاح ({', '.join(summary)})" if summary else "🤝 تم فحص طلب مساعدة كنز التحالف واستلام الجوائز (لا توجد عمليات معلقة حالياً)"
        self.log.info(f"🎉 {final_msg}")

        return TaskResult(
            success=True,
            message=final_msg,
            data={
                "received_own": total_received_own,
                "received_help": total_received_help,
                "help_calls": total_help_calls,
                "active_digs_count": len(active_digs),
            }
        )
