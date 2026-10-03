# -*- coding: utf-8 -*-
"""
tasks/hospital.py — مهمة معالجة الجنود الجرحى في المشفى (Hospital Cure Task)
═════════════════════════════════════════════════════════════════════════════

الوظيفة:
  0. الاستعلام التلقائي المسبق عن مهمة علاج الجرحى في مهام الهيبة اليومية (#4112009):
     - فحص ما إذا كانت المهمة منجزة مسبقاً (status in (4,5) أو اكتمال العدد المطلوب).
     - في حال كانت منجزة، يتم تجاهل مهمة المشفى وتخطيها تلقائياً لحفظ الموارد ومنع الاستهلاك غير الضروري.
  1. التحقق من جاهزية مبنى المشفى (Hospital - Building ID: 206) في القلعة ومستواه.
  2. فحص طابور العلاج في queueCtrl (Queue Type: 1202 - hostpital_queue):
     - إذا كان هناك طابور علاج نشط (starttime + totaltime > now)، يتم تسجيل الوقت المتبقي والتخطي بأمان.
  3. استعلام بيانات الجيش وجلب الجنود المصابين الجرحى (1005/1 -> woundedArmy).
  4. في حال وجود جرحى والمشفى متاح:
     - إرسال طلب العلاج العادي (cmd: "1005", subcmd: "4", mode: "0") بكافة أعداد الجنود المحتاجة للعلاج.
     - تحديث الذاكرة المحلية للجلسة (تصفير الجرحى، تحديث طابور 1202، وتحديث مهمة الهيبة).

بروتوكول اللعبة المعتمد:
  - مهمة الهيبة لعلاج الجرحى: #4112009 (meritoriousTaskCtrl)
  - تجديد بيانات الهيبة:      cmd: "1013", subcmd: "1"
  - استعلام الجيش:            cmd: "1005", subcmd: "1", data: {}
  - طلب بدء العلاج:           cmd: "1005", subcmd: "4", data: {"mode": "0", "armyinfo": {...}}
  - طابور العلاج:             queueCtrl['1202'] (hostpital_queue)
  - مبنى المشفى:              bid: "206" (BUILDID.HOSTPITAL)
"""

from __future__ import annotations

import sys
import os
import time
import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from tasks.base_task import BaseTask, TaskResult

if TYPE_CHECKING:
    from game_client import GameConnection

HOSPITAL_BID = "206"
HOSPITAL_QUEUE_TYPE = "1202"
PRESTIGE_CURE_QUEST_ID = 4112009  # معرف مهمة علاج الجنود المصابين بالمشفى في مهام الهيبة (meritoriousTaskCtrl)


class HospitalTask(BaseTask):
    """مهمة فحص المشفى وعلاج كافة الجنود الجرحى تلقائياً مع الاستعلام المسبق لمهام الهيبة."""

    name = "hospital"
    description = "🏥 معالجة الجنود الجرحى في المشفى"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    async def _refresh_merit_data(self) -> bool:
        """
        تجديد بيانات مهام الهيبة اليومية (meritoriousTaskCtrl) من السيرفر مباشرة.
        يحاول الاستعلام عبر 1013/1 ثم 1001/1 في حال التعذر.
        """
        try:
            r = await self.conn.query("1013", "1", {}, timeout=5)
            if r and isinstance(r, dict) and "data" in r:
                merit_data = r["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    return True
        except Exception as e:
            self.log.debug(f"استعلام 1013/1 لتجديد بيانات الهيبة لم يكتمل: {e}")

        try:
            r_all = await self.conn.query("1001", "1", {}, timeout=6)
            if r_all and isinstance(r_all, dict) and "data" in r_all:
                merit_data = r_all["data"].get("meritoriousTaskCtrl")
                if merit_data and isinstance(merit_data, dict):
                    self.conn.init_data["meritoriousTaskCtrl"] = merit_data
                    return True
        except Exception as e:
            self.log.debug(f"استعلام 1001/1 لتجديد بيانات الهيبة لم يكتمل: {e}")

        return False

    def check_prestige_cure_done(self) -> Tuple[bool, Dict[str, Any]]:
        """
        الاستعلام عن حالة مهمة علاج الجنود الجرحى في مهام الهيبة (ID: 4112009) من meritoriousTaskCtrl.
        يعيد: (منجزة_أم_لا, تفاصيل_المهمة)
        """
        merit_ctrl = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if not isinstance(merit_ctrl, dict) or not merit_ctrl:
            return False, {"found": False, "task_id": PRESTIGE_CURE_QUEST_ID, "c_num": 0, "l_num": 0, "is_done": False}

        qid = PRESTIGE_CURE_QUEST_ID
        qid_str = str(qid)

        # 1. فحص taskData (القاموس الرئيسي لمهام الهيبة اليومية)
        task_data = merit_ctrl.get("taskData", {})
        if isinstance(task_data, dict) and (qid_str in task_data or qid in task_data):
            t_obj = task_data.get(qid_str) or task_data.get(qid)
            if isinstance(t_obj, dict):
                c_num = int(t_obj.get("cNum", t_obj.get("c_num", 0)))
                l_num = int(t_obj.get("lNum", t_obj.get("l_num", 0)))
                status = int(t_obj.get("status", 0))
                # status == 4 (جاهزة للاستلام), status == 5 (تم استلامها), أو تحقيق الهدف المطلوب
                is_done = (status in (4, 5)) or (l_num > 0 and c_num >= l_num)
                remaining = max(0, l_num - c_num) if l_num > 0 else 0
                return is_done, {
                    "found": True,
                    "task_id": qid,
                    "c_num": c_num,
                    "l_num": l_num,
                    "status": status,
                    "is_done": is_done,
                    "remaining": remaining,
                }

        # 2. فحص قائمة tasks
        tasks = merit_ctrl.get("tasks", [])
        if isinstance(tasks, dict):
            tasks = list(tasks.values())
        if isinstance(tasks, list):
            for task_obj in tasks:
                if not isinstance(task_obj, dict):
                    continue
                t_id = task_obj.get("taskId") or task_obj.get("id")
                if t_id and int(t_id) == qid:
                    c_num = int(task_obj.get("c_num", task_obj.get("cNum", 0)))
                    l_num = int(task_obj.get("l_num", task_obj.get("lNum", 0)))
                    status = int(task_obj.get("status", 0))
                    is_finish = int(task_obj.get("is_finish", task_obj.get("isFinish", 0)))
                    is_done = (status in (4, 5)) or (is_finish == 1) or (l_num > 0 and c_num >= l_num)
                    remaining = max(0, l_num - c_num) if l_num > 0 else 0
                    return is_done, {
                        "found": True,
                        "task_id": qid,
                        "c_num": c_num,
                        "l_num": l_num,
                        "status": status,
                        "is_done": is_done,
                        "remaining": remaining,
                    }

        # 3. فحص daily_task (قاموس العدادات اليومية)
        daily_task = merit_ctrl.get("daily_task", {})
        if isinstance(daily_task, dict) and (qid_str in daily_task or qid in daily_task):
            c_val = int(daily_task.get(qid_str, daily_task.get(qid, 0)))
            is_done = c_val >= 1
            return is_done, {
                "found": True,
                "task_id": qid,
                "c_num": c_val,
                "l_num": 1,
                "status": 4 if is_done else 2,
                "is_done": is_done,
                "remaining": 0 if is_done else 1,
            }

        return False, {"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "is_done": False, "remaining": 0}

    def check_hospital_building(self) -> Tuple[bool, int, str]:
        """
        التحقق من وجود مبنى المشفى في القلعة ومستواه من قائمة blist.
        يعيد: (متاح, المستوى, وصف الحالة)
        """
        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        blist = city_ctrl.get("blist", []) if isinstance(city_ctrl, dict) else []

        hospitals = []
        for b in blist:
            binfo = b.get("binfo", {}) if isinstance(b, dict) else {}
            if str(binfo.get("bid")) == HOSPITAL_BID:
                hospitals.append(binfo)

        if not hospitals:
            return False, 0, "⚠️ لا يوجد مبنى مشفى (Hospital) مشيد بالقلعة!"

        # اختيار أعلى مستوى للمشفى إن وجد أكثر من مبنى
        max_lv = max(int(h.get("lv", 0)) for h in hospitals)
        if max_lv <= 0:
            return False, 0, "⚠️ مبنى المشفى ما زال قيد الإنشاء بمستوى 0!"

        return True, max_lv, f"مشفى جاهز (مستوى {max_lv})"

    def check_hospital_queue(self) -> Tuple[bool, float, str]:
        """
        فحص ما إذا كان المشفى قيد العلاج حالياً من طابور queueCtrl['1202'].
        يعيد: (متاح للعلاج_الآن, الثواني_المتبقية, وصف_الحالة)
        """
        queue_ctrl = self.conn.init_data.get("queueCtrl", {})
        if not isinstance(queue_ctrl, dict):
            return True, 0.0, "لا توجد طوابير مسجلة (المشفى متاح)"

        # البحث عن طابور علاج المشفى بالمعرف الحصري 1202 (hostpital_queue)
        # ملاحظة: طوابير 1200 و1201 هي طوابير ترقية المباني وليست طوابير علاج
        hosp_q = queue_ctrl.get(HOSPITAL_QUEUE_TYPE)
        if not hosp_q:
            for qid, qdata in queue_ctrl.items():
                if isinstance(qdata, dict):
                    if str(qdata.get("qtype")) == HOSPITAL_QUEUE_TYPE or str(qid) == HOSPITAL_QUEUE_TYPE:
                        hosp_q = qdata
                        break

        if not hosp_q or not isinstance(hosp_q, dict):
            return True, 0.0, "طابور المشفى شاغر ومتاح للعلاج"

        now_ts = time.time()
        starttime = float(hosp_q.get("starttime", 0))
        totaltime = float(hosp_q.get("totaltime", 0))
        endtime = starttime + totaltime

        if endtime > now_ts:
            remain = endtime - now_ts
            m, s = divmod(int(remain), 60)
            h, m = divmod(m, 60)
            time_str = f"{h}س و{m}د" if h > 0 else f"{m}د و{s}ث"
            return False, remain, f"المشفى قيد علاج دفعة سابقة حالياً (المتبقي: {time_str})"

        return True, 0.0, "اكتملت الدفعة السابقة (المشفى متاح للعلاج فوراً)"

    async def get_wounded_troops(self) -> Tuple[Dict[str, str], int]:
        """
        استعلام أحدث بيانات الجيش من السيرفر (1005/1) وجلب قائمة الجنود الجرحى.
        يعيد: (armyinfo_dict, total_count)
        """
        wounded_map: Dict[str, str] = {}

        try:
            r_army = await self.conn.query("1005", "1", {}, timeout=6)
            if r_army and str(r_army.get("err", "-1")) == "0":
                data = r_army.get("data", {})
                if isinstance(data, dict):
                    # تحديث الكاش المحلي
                    if "armyCtrl" in self.conn.init_data and isinstance(self.conn.init_data["armyCtrl"], dict):
                        self.conn.init_data["armyCtrl"]["woundedArmy"] = data.get("woundedArmy", {})
                        if "totalArmy" in data:
                            self.conn.init_data["armyCtrl"]["totalArmy"] = data.get("totalArmy", {})
                    raw_wounded = data.get("woundedArmy", {})
                    if isinstance(raw_wounded, dict):
                        for k, v in raw_wounded.items():
                            if str(k).isdigit() and str(v).isdigit() and int(v) > 0:
                                wounded_map[str(k)] = str(v)
        except Exception as e:
            self.log.warning(f"⚠️ تعذر استعلام الجيش 1005/1: {e} — استخدام البيانات المخزنة محلياً.")

        # خطة بديلة: قراءة الجرحى من بيانات init_data المخزنة مسبقاً
        if not wounded_map:
            army_ctrl = self.conn.init_data.get("armyCtrl", {})
            raw_cached = army_ctrl.get("woundedArmy", {}) if isinstance(army_ctrl, dict) else {}
            if isinstance(raw_cached, dict):
                for k, v in raw_cached.items():
                    if str(k).isdigit() and str(v).isdigit() and int(v) > 0:
                        wounded_map[str(k)] = str(v)

        total_cnt = sum(int(v) for v in wounded_map.values())
        return wounded_map, total_cnt

    async def run(self) -> TaskResult:
        """تنفيذ مهمة فحص وعلاج الجنود الجرحى بالمشفى مع التحقق المسبق من مهام الهيبة."""
        self.log.info("🏥 [مهمة المشفى] بدء فحص جاهزية المشفى ومهمة الهيبة...")

        # 0. الاستعلام التلقائي المسبق: التحقق من إنجاز مهمة علاج الجرحى في مهام الهيبة اليومية (#4112009)
        # إذا كانت منجزة بالفعل، يتم تجاهل علاج الجرحى وتخطي المشفى تلقائياً لحفظ موارد القلعة
        await self._refresh_merit_data()
        is_prestige_done, q_info = self.check_prestige_cure_done()
        if is_prestige_done:
            c_num = q_info.get("c_num", 0)
            l_num = q_info.get("l_num", 0)
            status_desc = f"({c_num}/{l_num})" if l_num > 0 else "(مكتملة)"
            skip_msg = (
                f"✨ [مهام الهيبة] مهمة علاج الجرحى في مهام الهيبة اليومية منجزة مسبقاً {status_desc} "
                f"— تم تخطي مهمة المشفى تلقائياً لتوفير الموارد ومنع الاستهلاك غير الضروري!"
            )
            self.log.info(f"⏭️ {skip_msg}")
            return TaskResult.ok(
                skip_msg,
                skipped=True,
                reason="PRESTIGE_CURE_ALREADY_DONE",
                quest_id=PRESTIGE_CURE_QUEST_ID,
                quest_info=q_info,
            )

        # 1. التحقق من وجود مبنى المشفى
        has_bld, b_lv, b_desc = self.check_hospital_building()
        if not has_bld:
            self.log.warning(f"⏭️ {b_desc} — تخطي مهمة العلاج.")
            return TaskResult.ok(b_desc, skipped=True, reason="NO_HOSPITAL_BUILDING")

        # 2. فحص طابور المشفى هل هو متاح أم مشغول حالياً
        q_avail, q_remain, q_desc = self.check_hospital_queue()
        if not q_avail:
            self.log.info(f"⏳ {q_desc} — المشفى مشغول حالياً، تخطي العلاج بأمان لهذه الدورة.")
            return TaskResult.ok(q_desc, skipped=True, reason="HOSPITAL_BUSY", remaining_seconds=q_remain)

        # 3. استعلام الجنود الجرحى
        armyinfo, total_wounded = await self.get_wounded_troops()
        if total_wounded <= 0 or not armyinfo:
            self.log.info("✅ [المشفى سليم] لا يوجد أي جنود جرحى بحاجة للعلاج في المشفى حالياً.")
            return TaskResult.ok("لا يوجد جنود جرحى", wounded_count=0)

        self.log.info(f"🩹 تم رصد {total_wounded:,} جندي جريح في المشفى بحاجة للعلاج عبر {len(armyinfo)} فئة قوات...")

        # 4. إرسال طلب العلاج (1005 / 4)
        payload = {
            "mode": "0",
            "armyinfo": armyinfo
        }

        try:
            resp = await self.conn.query("1005", "4", payload, timeout=10)
        except Exception as e:
            self.log.error(f"❌ خطأ أثناء إرسال طلب علاج الجرحى: {e}")
            return TaskResult.fail(f"خطأ اتصال أثناء العلاج: {e}")

        if not resp:
            return TaskResult.fail("لم يتم استلام أي استجابة من السيرفر لطلب العلاج")

        err = str(resp.get("err", "-1"))
        if err == "0":
            data = resp.get("data", {})
            retdata = data.get("retdata", {})
            totaltime = float(retdata.get("totaltime", 0.0))
            queuetype = str(retdata.get("queuetype", HOSPITAL_QUEUE_TYPE))

            # تحديث الذاكرة المحلية للجلسة فوراً
            if "armyCtrl" in self.conn.init_data and isinstance(self.conn.init_data["armyCtrl"], dict):
                self.conn.init_data["armyCtrl"]["woundedArmy"] = {}

            if "queueCtrl" in self.conn.init_data and isinstance(self.conn.init_data["queueCtrl"], dict):
                self.conn.init_data["queueCtrl"][queuetype] = {
                    "starttime": time.time(),
                    "totaltime": totaltime,
                    "qtype": queuetype,
                    "data": {
                        "bid": HOSPITAL_BID,
                        "armyinfo": armyinfo,
                        "costres": retdata.get("costres", {})
                    }
                }

            # تحديث حالة مهمة علاج الجرحى في مهام الهيبة محلياً
            merit = self.conn.init_data.get("meritoriousTaskCtrl")
            if isinstance(merit, dict):
                task_data = merit.setdefault("taskData", {})
                if isinstance(task_data, dict):
                    t_info = task_data.setdefault(str(PRESTIGE_CURE_QUEST_ID), {
                        "id": PRESTIGE_CURE_QUEST_ID,
                        "cNum": 0,
                        "lNum": 1,
                        "status": 2
                    })
                    if isinstance(t_info, dict):
                        t_info["cNum"] = int(t_info.get("cNum", 0)) + total_wounded
                        t_info["status"] = 4
                daily = merit.setdefault("daily_task", {})
                if isinstance(daily, dict):
                    daily[str(PRESTIGE_CURE_QUEST_ID)] = int(daily.get(str(PRESTIGE_CURE_QUEST_ID), 0)) + 1

            m, s = divmod(int(totaltime), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h}س و{m}د" if h > 0 else f"{m}د و{s}ث"

            succ_msg = f"🏥 تم إرسال طلب علاج {total_wounded:,} جندي جريح بنجاح! (مدة العلاج: {dur_str})"
            self.log.info(f"✅ {succ_msg}")
            return TaskResult.ok(succ_msg, healed_count=total_wounded, totaltime=totaltime)

        # التعامل مع أخطاء السيرفر المعروفة
        err_descriptions = {
            "1001": "طوابير العلاج ممتلئة بالكامل",
            "1002": "نقص في كمية الطعام (Food) المطلوبة للعلاج",
            "1003": "نقص في كمية الخشب (Wood) المطلوبة للعلاج",
            "1004": "نقص في كمية الحديد (Iron) المطلوبة للعلاج",
            "1005": "نقص في كمية الفضة/الألماس المطلوبة للعلاج",
            "4002": "المشفى مشغول في معالجة قوات أخرى حالياً",
        }
        err_msg = err_descriptions.get(err, f"كود خطأ غير معروف ({err})")
        self.log.warning(f"⚠️ تعذر بدء علاج الجرحى: {err_msg}")
        return TaskResult.fail(f"فشل بدء العلاج: {err_msg}", err_code=err)


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول للتشغيل المستقل (Standalone CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager
    from game_client import GameConnection

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    parser = argparse.ArgumentParser(description="🏥 مهمة معالجة الجنود الجرحى في المشفى")
    parser.add_argument("--email", required=True, help="البريد الإلكتروني للقلعة المستهدفة")
    args = parser.parse_args()

    async def main():
        sm = SessionManager()
        acc = sm.get_or_login(email=args.email)
        if not acc:
            print(f"❌ تعذر العثور على بيانات الحساب: {args.email}")
            return

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال باللعبة!")
            return

        for _ in range(12):
            await asyncio.sleep(0.3)
            if "cityCtrl" in conn.init_data and "queueCtrl" in conn.init_data:
                break

        task = HospitalTask(conn)
        res = await task.run()
        print("\n🏁 نتيجة المهمة:", res)
        await conn.close()

    asyncio.run(main())
