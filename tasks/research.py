# -*- coding: utf-8 -*-
"""
tasks/research.py — مهمة استعراض وإجراء أبحاث الأكاديمية (Academy Research Task)
════════════════════════════════════════════════════════════════════════════════
تقوم هذه المهمة بفحص حالة مبنى الأكاديمية (College) وطابور البحث:
  1. الاستعلام عن طابور البحث الحالي (1017/3) والتأكد هل هو متاح أم قيد البحث.
  2. الاستعلام عن قائمة الأبحاث المكتسبة ومستوياتها (1017/1).
  3. تحديد البحث الموصى به تلقائياً (حسب مهام الفصل أو مسار الشجرة المحددة) أو حسب --tech-id.
  4. عرض بيانات وتفاصيل البحث الموصى به باللغة العربية (الاسم، المعرف، الشجرة، المستوى).
  5. تنفيذ طلب البحث فوراً بالسيرفر عبر (1017/2) مع إرسال clientData المطابق.

الاستخدام كملف مستقل:
    python tasks/research.py --email "sumo-1234@hotmil.com"
    python tasks/research.py --email "burcudemr@gmail.com" --tree defense
    python tasks/research.py --email "burcudemr@gmail.com" --tech-id 23016
    python tasks/research.py --email "hmzawyha44@gmail.com" --check-only
    python tasks/research.py --all-accounts --tree resources
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
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  تصنيفات أشجار الأبحاث في اللعبة
# ════════════════════════════════════════════════════════════════════

TECH_TREES: Dict[str, Dict[str, Any]] = {
    "defense": {
        "name_ar": "🛡️ الدفاع والتحصينات (الأسوار والفخاخ)",
        "tech_ids": [
            23001, 23002, 23003, 23004, 23005, 23006, 23007, 23008, 23009, 23010,
            23011, 23012, 23013, 23014, 23015, 23016, 23017, 23018
        ]
    },
    "resources": {
        "name_ar": "🌾 الموارد والإنتاج",
        "tech_ids": [
            21001, 21002, 21003, 21004, 21005, 21006, 21007, 21008, 21009, 21010,
            21011, 21012, 21013, 21014, 21015, 21016, 21017, 21018, 21019, 21020
        ]
    },
    "city": {
        "name_ar": "🏛️ تنمية وتطوير المدينة",
        "tech_ids": [
            22001, 22002, 22003, 22004, 22005, 22006, 22007, 22008, 22009, 22010,
            22011, 22012, 22013, 22014
        ]
    },
    "military": {
        "name_ar": "⚔️ الشؤون العسكرية وتدريب الجيش",
        "tech_ids": [
            24001, 24002, 24003, 24004, 24005, 24006, 24007, 24008, 24009, 24010,
            24011, 24012, 24013, 24014, 24015, 24016, 24017, 24018, 24019, 24020,
            24021, 24022, 24023, 24024, 24025, 24026, 24027, 24028, 24029, 24030,
            24031, 24032, 24033, 24034, 24035, 24036, 24037, 24038, 24039, 24040,
            24041, 24042, 24043, 24044, 24045, 24046, 24047, 24048
        ]
    },
    "special": {
        "name_ar": "✨ التقنيات الخاصة",
        "tech_ids": list(range(24101, 24119))
    },
    "hero": {
        "name_ar": "👑 قيادة الأبطال والإمكانات",
        "tech_ids": list(range(25001, 25011))
    },
    "advanced": {
        "name_ar": "🔥 العسكرية المتقدمة والتكتيكات",
        "tech_ids": list(range(26001, 26035))
    },
    "war": {
        "name_ar": "⚔️ تكنولوجيا حرب الممالك",
        "tech_ids": [
            110001, 110002, 110003, 110004, 110005, 110006, 110007, 110008, 110009, 110010,
            110011, 110012, 110013, 110014, 110015, 110016, 110017, 110018, 110019, 110020,
            110021, 110027, 110028, 110030, 110031, 110035, 110036, 110037, 110038, 110039,
            110040, 110041, 110042, 110043, 110044, 110045, 110046, 110047, 110048, 110049,
            110050, 110051, 110056
        ]
    }
}

# خريطة أسماء الموارد
RESOURCE_NAMES = {
    "1002": "🌾 طعام",
    "1003": "🪵 خشب",
    "1004": "⛏️ حديد",
    "1005": "🪙 فضة"
}


# ════════════════════════════════════════════════════════════════════
#  تحميل قاموس أسماء الأبحاث
# ════════════════════════════════════════════════════════════════════

_TECH_NAMES_CACHE: Dict[str, Dict[str, Any]] = {}

def load_tech_names() -> Dict[str, Dict[str, Any]]:
    global _TECH_NAMES_CACHE
    if _TECH_NAMES_CACHE:
        return _TECH_NAMES_CACHE
    json_path = os.path.join(_ROOT_DIR, "tech_names.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                _TECH_NAMES_CACHE = json.load(f)
        except Exception as e:
            logging.getLogger("tasks").warning(f"⚠️ فشل قراءة tech_names.json: {e}")
    return _TECH_NAMES_CACHE


def format_duration(seconds: float) -> str:
    """تنسيق المدة بالثواني إلى صيغة مقروءة بالعربية."""
    total_sec = int(max(0, seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours} س")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes} د")
    parts.append(f"{secs} ث")
    return " و ".join(parts)


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة الرئيسي (ResearchTask)
# ════════════════════════════════════════════════════════════════════

class ResearchTask(BaseTask):
    """
    مهمة فحص وإجراء أبحاث الأكاديمية تلقائياً.
    """
    name = "research"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.tech_names = load_tech_names()

    def get_tech_title(self, tech_id: Any) -> str:
        """إرجاع الاسم العربي والرمز للبحث."""
        s_id = str(tech_id)
        info = self.tech_names.get(s_id, {})
        name_ar = info.get("name_ar", "").strip()
        if not name_ar or name_ar.startswith("technology_name_"):
            name_en = info.get("name_en", "").strip()
            name_ar = name_en or f"بحث #{s_id}"
        return f"[{s_id}] {name_ar}"

    async def get_queue_status(self) -> Dict[str, Any]:
        """
        الاستعلام عن حالة طابور الأبحاث الحالي عبر 1017/3.
        يعيد dict يحتوي: is_busy, remain_time, tech_id, current_level, resources.
        """
        resp = await self.conn.query("1017", "3", {})
        if resp.get("err") != "0":
            return {"is_busy": False, "remain_time": 0}

        data = resp.get("data", {})
        remain_time = float(data.get("remainTime", 0))
        extra_data = data.get("extraData", {})

        if remain_time > 0 and extra_data:
            tech_keys = [k for k in extra_data.keys() if str(k).isdigit()]
            if tech_keys:
                cur_tid = tech_keys[0]
                item_info = extra_data.get(cur_tid)
                if isinstance(item_info, list):
                    target_level = item_info[1] if len(item_info) > 1 else 1
                    cost_info = item_info[2] if len(item_info) > 2 and isinstance(item_info[2], dict) else {}
                elif isinstance(item_info, (int, str)):
                    try:
                        target_level = int(item_info)
                    except (ValueError, TypeError):
                        target_level = 1
                    cost_info = {}
                else:
                    target_level = 1
                    cost_info = {}

                return {
                    "is_busy": True,
                    "remain_time": remain_time,
                    "tech_id": str(cur_tid),
                    "target_level": target_level,
                    "cost_info": cost_info,
                    "raw": data
                }

        return {"is_busy": False, "remain_time": 0, "raw": data}

    async def get_learned_technologies(self) -> Dict[str, int]:
        """
        الاستعلام عن كافة الأبحاث المكتسبة ومستوياتها الحالية عبر 1017/1.
        يعيد dict: {tech_id: level}
        """
        resp = await self.conn.query("1017", "1", {})
        if resp.get("err") != "0":
            return {}

        data = resp.get("data", {})
        learned = {}
        for tid, val in data.items():
            if isinstance(val, list) and len(val) > 1:
                try:
                    learned[str(tid)] = int(val[1])
                except (ValueError, TypeError):
                    learned[str(tid)] = 1
            elif isinstance(val, (int, str)):
                learned[str(tid)] = int(val)
        return learned

    def determine_recommended_tech(
        self,
        learned_techs: Dict[str, int],
        tree_pref: str = "military",
        explicit_tech_id: Optional[str] = None
    ) -> Optional[Tuple[str, int, str]]:
        """
        تحديد البحث الموصى به.
        يعيد tuple: (tech_id, target_level, tree_name)
        """
        # 1. إذا حدد المستخدم ID صريحاً
        if explicit_tech_id:
            s_tid = str(explicit_tech_id).strip()
            cur_lv = learned_techs.get(s_tid, 0)
            return (s_tid, cur_lv + 1, "محدد يدوياً")

        # 2. فحص مهام التحالف / الفصل (Chapter / Quest recommendation)
        # إذا وجدنا في بيانات الحساب مهمة تطلب بحثاً معيناً
        # فحص الشجرة المطلوبة
        tree_keys = []
        if tree_pref == "all":
            tree_keys = ["defense", "resources", "city", "military", "advanced", "war"]
        elif tree_pref in TECH_TREES:
            tree_keys = [tree_pref]
        else:
            tree_keys = ["military", "defense", "resources", "city"]

        # البحث في الأشجار المحددة عن أول بحث غير مكتمل أو تالي
        for t_key in tree_keys:
            tree_data = TECH_TREES.get(t_key, {})
            tech_ids = tree_data.get("tech_ids", [])
            tree_title = tree_data.get("name_ar", t_key)

            # أ) أولاً: أي بحث في الشجرة لم يُكتسب مطلقاً (المستوى 0)
            for tid in tech_ids:
                s_id = str(tid)
                if s_id not in learned_techs:
                    return (s_id, 1, tree_title)

            # ب) ثانياً: البحث ذو المستوى الأقل في الشجرة لترقيته
            lowest_tid = None
            lowest_lvl = 999
            for tid in tech_ids:
                s_id = str(tid)
                lv = learned_techs.get(s_id, 0)
                if lv < lowest_lvl:
                    lowest_lvl = lv
                    lowest_tid = s_id

            if lowest_tid is not None:
                return (lowest_tid, lowest_lvl + 1, tree_title)

        return None

    async def execute_research(self, tech_id: str) -> Dict[str, Any]:
        """
        إرسال أمر إجراء البحث للسيرفر (1017/2).
        مطابق للطلب الفعلي للعبة:
        {
          "cmd": "1017",
          "clientData": [tech_id],
          "subcmd": "2",
          "data": {
            "type": 1,
            "technologyId": tech_id,
            "rtype": 1
          }
        }
        """
        s_id = str(tech_id)
        payload = {
            "type": 1,
            "technologyId": s_id,
            "rtype": 1
        }
        resp = await self.conn.query(
            "1017",
            "2",
            payload,
            client_data=[s_id]
        )
        return resp

    async def run(self) -> TaskResult:
        cfg = self.config
        tree_pref = str(cfg.get("tree", "defense")).lower().strip()
        explicit_id = cfg.get("tech_id")
        check_only = bool(cfg.get("check_only", False))

        self.log.info(f"🔬 بدء مهمة أبحاث الأكاديمية (الشجرة: {tree_pref} | بحث مخصص: {explicit_id or 'تلقائي'})")

        # 1. الاستعلام عن طابور البحث
        queue_info = await self.get_queue_status()

        # 2. الاستعلام عن الأبحاث الحالية
        learned_techs = await self.get_learned_technologies()
        self.log.info(f"📚 تم استرجاع {len(learned_techs)} بحث مكتمل/قيد التطوير للحساب.")

        # إذا كان الطابور مشغولاً بالفعل
        if queue_info.get("is_busy"):
            cur_tid = queue_info.get("tech_id")
            tgt_lv = queue_info.get("target_level", 1)
            rem_sec = queue_info.get("remain_time", 0)
            cur_title = self.get_tech_title(cur_tid)
            rem_str = format_duration(rem_sec)

            msg = f"⏳ طابور الأبحاث مشغول حالياً ببحث {cur_title} للمستوى {tgt_lv} (متبقي: {rem_str})"
            self.log.warning(msg)
            return TaskResult(
                success=True,
                message=msg,
                data={
                    "status": "busy",
                    "current_research": cur_title,
                    "tech_id": cur_tid,
                    "target_level": tgt_lv,
                    "remain_seconds": int(rem_sec),
                    "remain_human": rem_str
                },
                should_retry=True,
                retry_after=max(60, int(rem_sec))
            )

        # 3. تحديد البحث الموصى به
        rec = self.determine_recommended_tech(learned_techs, tree_pref, explicit_id)
        if not rec:
            msg = "⚠️ لم يتم العثور على بحث موصى به مناسب في الشجرة المحددة!"
            self.log.warning(msg)
            return TaskResult.fail(msg)

        rec_tid, target_lv, tree_name = rec
        rec_title = self.get_tech_title(rec_tid)
        cur_lv = learned_techs.get(rec_tid, 0)

        self.log.info(f"💡 البحث الموصى به: {rec_title} | الشجرة: {tree_name} | المستوى: {cur_lv} -> {target_lv}")

        # 4. إذا كان الخيار فحص وعرض فقط
        if check_only:
            msg = f"🔍 [فحص فقط] البحث الموصى به: {rec_title} (مستوى {cur_lv} ➔ {target_lv}) في {tree_name}"
            return TaskResult.ok(
                msg,
                tech_id=rec_tid,
                name=rec_title,
                tree=tree_name,
                current_level=cur_lv,
                target_level=target_lv,
                action="checked"
            )

        # 5. تنفيذ البحث فوراً بالسيرفر
        self.log.info(f"🚀 جارٍ إرسال أمر إجراء البحث للسيرفر: {rec_title}...")
        resp = await self.execute_research(rec_tid)
        err = str(resp.get("err", "-1"))

        if err == "0":
            # تحديث حالة الطابور لمعرفة وقت الانتهاء والموارد المستهلكة
            new_queue = await self.get_queue_status()
            rem_sec = new_queue.get("remain_time", 0)
            rem_str = format_duration(rem_sec)

            success_msg = f"✅ تم بنجاح بدء البحث الموصى به: {rec_title} (المستوى {target_lv}) ⏳ الوقت: {rem_str}"
            self.log.info(success_msg)
            return TaskResult.ok(
                success_msg,
                tech_id=rec_tid,
                name=rec_title,
                target_level=target_lv,
                tree=tree_name,
                duration_seconds=int(rem_sec),
                duration_human=rem_str,
                cost_info=new_queue.get("cost_info", {})
            )
        else:
            # معالجة الخطأ
            err_msg = f"❌ فشل بدء البحث {rec_title}! رمز الخطأ: {err}"
            if err == "101701" or "resource" in str(resp).lower():
                err_msg += " (الموارد غير كافية أو متطلبات المبنى غير مكتملة)"
            elif err == "101702":
                err_msg += " (متطلبات الأكاديمية أو الأبحاث السابقة غير محققة)"
            self.log.error(err_msg)
            return TaskResult.fail(err_msg, err=err, resp=resp)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (CLI Runner)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Empire Academy Research Task — مهمة فحص وإجراء أبحاث الأكاديمية"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument(
        "--tree", "-t", default="defense",
        choices=["defense", "resources", "city", "military", "advanced", "war", "special", "hero", "all"],
        help="مسار شجرة الأبحاث المستهدفة [افتراضي: defense]"
    )
    parser.add_argument("--tech-id", "-id", help="تحديد معرّف بحث معين بالرقم لإجرائه مباشرة (مثل: 23016)")
    parser.add_argument("--check-only", "-c", action="store_true", help="فحص وعرض البحث الموصى به دون بدئه")
    parser.add_argument("--all-accounts", action="store_true", help="تشغيل المهمة لجميع الحسابات المسجلة")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    from core.session_manager import SessionManager

    async def _run_for_account(acc_email: str, acc_obj: Any):
        print("\n" + "═" * 70)
        print(f"🏰 الحساب المستهدف: {acc_email}")
        print("═" * 70)

        conn = GameConnection(acc_obj)
        if not await conn.connect():
            print(f"❌ فشل الاتصال بالحساب {acc_email}!")
            return

        for _ in range(12):
            await asyncio.sleep(0.4)
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "tree": args.tree,
            "tech_id": args.tech_id,
            "check_only": args.check_only
        }

        task = ResearchTask(conn, task_cfg)
        await task.on_start()
        res = await task.run()

        print("\n" + "─" * 70)
        if res.success:
            print(f"🎉 {res.message}")
            if res.data:
                for k, v in res.data.items():
                    if k != "raw":
                        print(f"   • {k}: {v}")
        else:
            print(f"⚠️ {res.message}")
        print("─" * 70)

        await conn.close()

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        target_list = []
        if args.all_accounts:
            target_list = list(accounts.items())
        else:
            target_email = args.email or next(iter(accounts.keys()))
            acc = accounts.get(target_email)
            if not acc:
                print(f"❌ الحساب {target_email} غير موجود!")
                return
            target_list = [(target_email, acc)]

        for email, acc in target_list:
            if email.startswith("azjfhf"):  # تخطي الحسابات المغلقة المعروفة
                continue
            await _run_for_account(email, acc)

    asyncio.run(_main())
