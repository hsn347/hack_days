# -*- coding: utf-8 -*-
"""
tasks/week_start_benefits.py — مهمة استلام جوائز مزايا بداية الأسبوع (Week-Start Benefits / Back to Work Booster)
══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
مهمة أساسية إلزامية تنفذ تلقائياً لجميع الحسابات (لا تتطلب أي إعداد في قاعدة البيانات):
  1. استعلام الفعالية من بيانات السيرفر (generalAtyMgr):
     - مطابقة معرفات الفعالية: 9001127, 9001368, 9001369, 9001370
     - أو مطابقة معرفات المهام الخاصة بالحدث (4110467..4110481, 4118582..4118586)
  2. فحص المهام المكتملة الجاهزة للاستلام (status == 3 أو cNum >= lNum و status != 4).
  3. إذا لم توجد أي جوائز جاهزة للاستلام، يتم إنهاء المهمة فوراً بهدوء ودون أي تأخير.
  4. إذا وجدت جوائز، يتم إرسال طلب استلام المكافأة تباعاً مع فاصل زمني آمن بين كل جمع:
     cmd: "1028", subcmd: "5", data: {"dynamicId": dynamicId}
  5. فحص واستلام صناديق المعالم الإضافية (Milestone Boxes عند 3, 6, 9, 12 مهمة منجزة):
     cmd: "2063", subcmd: "2", data: {"activityId": activityId, "needNum": needNum}
"""

from __future__ import annotations

import sys
import os
import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

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
from game_client import GameConnection

# معرفات فعاليات مزايا بداية الأسبوع المعروفة في اللعبة (Activity IDs)
WEEK_START_ACTIVITY_IDS: Set[int] = {
    9001127,  # المعرف الكلاسيكي لمزايا بداية الأسبوع (Back to Work Booster)
    9001368,  # الإصدار المطور
    9001369,  # إصدار متقدم
    9001370,  # الإصدار الأحدث الموسع (20 مهمة)
}

# نطاق معرفات المهام المميزة لفعالية بداية الأسبوع
WEEK_START_TASK_IDS: Set[int] = set(range(4110467, 4110482)).union(range(4118582, 4118587))

# مسميات المهام باللغة العربية لعرض سجلات واضحة
TASK_DESCRIPTIONS: Dict[int, str] = {
    4110467: "تسجيل الدخول اليومي",
    4110468: "تدريب 200 جندي",
    4110469: "تدريب 800 جندي",
    4110470: "جمع 60,000 من الموارد",
    4110471: "جمع 120,000 من الموارد",
    4110472: "استهلاك 2,000 نقطة طاقة",
    4110473: "استهلاك 6,000 نقطة طاقة",
    4110474: "هزيمة 10 من الغزاة",
    4110475: "هزيمة 30 من الغزاة",
    4110476: "التبرع لتقنيات التحالف مرتين",
    4110477: "تقديم المساعدة لأعضاء التحالف 3 مرات",
    4110478: "تجنيد 3 أبطال",
    4110479: "تجنيد 10 أبطال",
    4110480: "استكمال مهام الميناء/المشفى (12 مرة)",
    4110481: "استكمال مهام الميناء/المشفى (25 مرة)",
    4118582: "المشاركة في أنشطة التحالف (5 مرات)",
    4118583: "استكشاف أراضي المعارك (مرة واحدة)",
    4118584: "استكشاف أراضي المعارك (3 مرات)",
    4118585: "معارك التحدي (5 مرات)",
    4118586: "معارك التحدي (10 مرات)",
}

# معالم الصناديق التراكمية (Milestones)
MILESTONE_BOX_COUNTS: List[int] = [3, 6, 9, 12]


class WeekStartBenefitsTask(BaseTask):
    """
    مهمة استلام جوائز مزايا بداية الأسبوع (CMD 1028 / SUB 5):
    تفحص المهام المكتملة وتستلم جوائزها تباعاً مع فاصل زمني آمن، وتنهي المهمة فوراً إذا لم توجد جوائز.
    """
    name = "week_start_benefits"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config or {})

    # ──────────────────────────────────────────────────────────────────
    #  استعلام واكتشاف فعاليات بداية الأسبوع النشطة
    # ──────────────────────────────────────────────────────────────────

    def _find_week_start_activities(self) -> List[Tuple[int, Dict[str, Any]]]:
        """
        البحث في generalAtyMgr عن فعاليات مزايا بداية الأسبوع ومطابقتها.
        ترجع قائمة بالأزواج (activity_id, activity_data) مرتبة بالأحدث نشاطاً.
        """
        mgr = self.conn.init_data.get("generalAtyMgr", {})
        if not isinstance(mgr, dict):
            return []

        matched: List[Tuple[int, Dict[str, Any], int]] = []

        for aid_str, aty in mgr.items():
            if not isinstance(aty, dict):
                continue

            try:
                aid = int(aty.get("activityId", aid_str))
            except Exception:
                continue

            data_block = aty.get("data", {})
            quests = data_block.get("quests", {}) if isinstance(data_block, dict) else {}

            is_match = False
            if aid in WEEK_START_ACTIVITY_IDS:
                is_match = True
            elif isinstance(quests, dict) and any(int(q.get("id", qk)) in WEEK_START_TASK_IDS for qk, q in quests.items() if isinstance(q, dict)):
                is_match = True

            if is_match and isinstance(quests, dict) and len(quests) > 0:
                # معرفة أحدث وقت بدء للفعالية لترتيبها
                start_time = 0
                for q in quests.values():
                    if isinstance(q, dict):
                        start_time = max(start_time, int(q.get("startTime", 0)))
                matched.append((aid, aty, start_time))

        # ترتيب الفعاليات حسب أحدث وقت بدء أولاً
        matched.sort(key=lambda x: x[2], reverse=True)
        return [(aid, aty) for aid, aty, _ in matched]

    # ──────────────────────────────────────────────────────────────────
    #  استخراج المهام الجاهزة للاستلام
    # ──────────────────────────────────────────────────────────────────

    def _get_ready_quests(self, activity_id: int, activity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        استخراج قائمة المهام المكتملة الجاهزة للاستلام (status == 3).
        """
        data_block = activity_data.get("data", {})
        if not isinstance(data_block, dict):
            return []

        quests = data_block.get("quests", {})
        if not isinstance(quests, dict):
            return []

        ready = []
        for qk, q in quests.items():
            if not isinstance(q, dict):
                continue

            dynamic_id = q.get("dynamicId")
            if dynamic_id is None:
                continue

            try:
                dynamic_id = int(dynamic_id)
            except Exception:
                continue

            try:
                qid = int(q.get("id", qk))
            except Exception:
                qid = 0

            status = int(q.get("status", 2))
            c_num = int(q.get("cNum", 0))
            l_num = int(q.get("lNum", 1))

            # status == 3: مكتملة وجاهزة للاستلام (gTaskStatus.COMPLETE)
            # أو c_num >= l_num مع عدم استلامها مسبقاً (status != 4)
            if status == 3 or (c_num >= l_num and status != 4):
                desc = TASK_DESCRIPTIONS.get(qid, f"مهمة #{qid}")
                ready.append({
                    "id": qid,
                    "dynamicId": dynamic_id,
                    "status": status,
                    "cNum": c_num,
                    "lNum": l_num,
                    "desc": desc,
                    "activityId": activity_id,
                    "ref": q,
                })

        return ready

    # ──────────────────────────────────────────────────────────────────
    #  استلام جائزة مهمة فردية (CMD 1028 / SUB 5)
    # ──────────────────────────────────────────────────────────────────

    async def _claim_quest(self, dynamic_id: int, quest_ref: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        إرسال حزمة استلام جائزة المهمة (cmd: 1028, subcmd: 5, dynamicId).
        """
        payload = {"dynamicId": dynamic_id}
        try:
            rsp = await self.conn.query("1028", "5", payload, timeout=6)
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر"

            err = str(rsp.get("err", ""))
            if err == "0":
                if quest_ref is not None and isinstance(quest_ref, dict):
                    quest_ref["status"] = 4
                return True, "تم استلام المكافأة بنجاح"
            elif err == "1002":
                if quest_ref is not None and isinstance(quest_ref, dict):
                    quest_ref["status"] = 4
                return False, "المهمة مستلمة مسبقاً أو غير مكتملة"
            else:
                return False, f"خطأ السيرفر: err={err}"
        except Exception as e:
            return False, f"استثناء أثناء إرسال الطلب: {e}"

    # ──────────────────────────────────────────────────────────────────
    #  فحص واستلام صناديق المعالم (Milestone Boxes - CMD 2063 / SUB 2)
    # ──────────────────────────────────────────────────────────────────

    async def _claim_milestone_boxes(self, activity_id: int, activity_data: Dict[str, Any]) -> int:
        """
        فحص واستلام صناديق المعالم الإضافية عند الوصول لعدد معين من المهام المنجزة (3, 6, 9, 12).
        """
        data_block = activity_data.get("data", {})
        if not isinstance(data_block, dict):
            return 0

        quests = data_block.get("quests", {})
        if not isinstance(quests, dict):
            return 0

        # حساب عدد المهام المستلمة أو المكتملة
        completed_count = 0
        for q in quests.values():
            if isinstance(q, dict):
                st = int(q.get("status", 0))
                c_num = int(q.get("cNum", 0))
                l_num = int(q.get("lNum", 1))
                if st == 4 or st == 3 or (c_num >= l_num and l_num > 0):
                    completed_count += 1

        claimed_boxes = data_block.get("boxs", {})
        if not isinstance(claimed_boxes, dict):
            claimed_boxes = {}

        boxes_claimed = 0
        for milestone in MILESTONE_BOX_COUNTS:
            if completed_count >= milestone and not claimed_boxes.get(str(milestone)):
                self.log.info(f"🎁 استلام صندوق معلم {milestone} مهام في مزايا بداية الأسبوع (الفعالية: {activity_id})...")
                try:
                    payload = {
                        "activityId": int(activity_id),
                        "needNum": int(milestone)
                    }
                    rsp = await self.conn.query("2063", "2", payload, timeout=6)
                    if rsp and str(rsp.get("err", "")) == "0":
                        claimed_boxes[str(milestone)] = True
                        data_block["boxs"] = claimed_boxes
                        boxes_claimed += 1
                        self.log.info(f"  ✅ تم استلام صندوق المعلم ({milestone} مهام) بنجاح.")
                        await asyncio.sleep(random.uniform(1.0, 1.8))
                except Exception as e:
                    self.log.debug(f"استثناء أثناء استلام صندوق المعلم {milestone}: {e}")

        return boxes_claimed

    # ──────────────────────────────────────────────────────────────────
    #  التنفيذ الرئيسي للمهمة (Main Execution)
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """
        تنفيذ استعلام وجمع جوائز مزايا بداية الأسبوع.
        """
        # انتظار توفر بيانات generalAtyMgr بمهلة قصيرة
        for _ in range(15):
            if "generalAtyMgr" in self.conn.init_data and len(self.conn.init_data["generalAtyMgr"]) > 5:
                break
            await asyncio.sleep(0.2)

        # 1. البحث عن فعاليات مزايا بداية الأسبوع
        activities = self._find_week_start_activities()
        if not activities:
            msg = "لا توجد فعالية مزايا بداية الأسبوع نشطة حالياً في الحساب"
            self.log.info(f"ℹ️ {msg}")
            return TaskResult.ok(message=msg, claimed_count=0, active=False)

        total_claimed = 0
        total_failed = 0
        total_boxes = 0
        details_log: List[str] = []

        for aid, aty_data in activities:
            # 2. استعلام المهام الجاهزة للاستلام
            ready_quests = self._get_ready_quests(aid, aty_data)

            if ready_quests:
                self.log.info(f"🎁 مزايا بداية الأسبوع (الفعالية: {aid}): تم العثور على {len(ready_quests)} جوائز جاهزة للاستلام.")

                for i, q in enumerate(ready_quests):
                    dynamic_id = q["dynamicId"]
                    qid = q["id"]
                    desc = q["desc"]

                    # فاصل أمان بسيط ومدروس بين كل عملية جمع
                    if i > 0 or total_claimed > 0:
                        jitter = round(random.uniform(1.2, 2.0), 2)
                        await asyncio.sleep(jitter)

                    self.log.info(f"  ⬆️ جاري استلام جائزة {desc} (ID: {qid}, dynamicId: {dynamic_id})...")
                    success, note = await self._claim_quest(dynamic_id, q.get("ref"))

                    if success:
                        total_claimed += 1
                        details_log.append(f"{desc} (dynamicId: {dynamic_id}): تم الاستلام بنجاح")
                        self.log.info(f"  ✅ تم استلام جائزة {desc} بنجاح.")
                    else:
                        total_failed += 1
                        details_log.append(f"{desc} (dynamicId: {dynamic_id}): {note}")
                        self.log.warning(f"  ⚠️ تعذر استلام جائزة {desc}: {note}")

            # 3. فحص واستلام صناديق المعالم الإضافية
            boxes_claimed = await self._claim_milestone_boxes(aid, aty_data)
            total_boxes += boxes_claimed

        # 4. تحديد الرسالة النهائية والإنهاء النظيف
        if total_claimed == 0 and total_boxes == 0:
            msg = "لا توجد جوائز جاهزة للاستلام حالياً في مزايا بداية الأسبوع"
            self.log.info(f"ℹ️ {msg}")
            return TaskResult.ok(message=msg, claimed_count=0, boxes_claimed=0)

        final_msg = f"تم استلام {total_claimed} من جوائز مزايا بداية الأسبوع بنجاح"
        if total_boxes > 0:
            final_msg += f" مع {total_boxes} من صناديق المعالم"
        if total_failed > 0:
            final_msg += f" (تعذر {total_failed})"

        self.log.info(f"🎉 {final_msg}")
        return TaskResult.ok(
            message=final_msg,
            claimed_count=total_claimed,
            boxes_claimed=total_boxes,
            failed_count=total_failed,
            log=details_log
        )


if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="اختبار مهمة مزايا بداية الأسبوع المستقلة")
    parser.add_argument("--email", required=True, help="البريد الإلكتروني للقلعة")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    async def main():
        session_mgr = SessionManager()
        accounts = session_mgr.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        creds = accounts.get(args.email)
        if not creds:
            for em, acc in accounts.items():
                if em.lower() == args.email.lower():
                    creds = acc
                    break

        if not creds:
            print(f"❌ لم يتم العثور على جلسة للحساب {args.email}")
            return

        conn = GameConnection(creds)
        connected = await conn.connect()
        if not connected:
            print(f"❌ تعذر الاتصال بالسيرفر للحساب {args.email}")
            return

        for _ in range(20):
            await asyncio.sleep(0.3)
            if "generalAtyMgr" in conn.init_data and len(conn.init_data["generalAtyMgr"]) > 5:
                break
        await asyncio.sleep(0.4)

        try:
            print(f"🚀 بدء تنفيذ مهمة مزايا بداية الأسبوع للحساب: {args.email}")
            task = WeekStartBenefitsTask(conn, {})
            result = await task.run()
            print(f"📋 النتيجة: {result.message}")
            if result.data:
                print(f"📊 التفاصيل: {result.data}")
        finally:
            await conn.close()

    asyncio.run(main())
