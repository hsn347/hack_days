# -*- coding: utf-8 -*-
"""
tasks/skills.py — مهمة الاستعلام الذكي وتفعيل المهارات التلقائية (Skills Task)
═══════════════════════════════════════════════════════════════════════════════

بروتوكول تفعيل المهارات (Lord / Beauty Skills Protocol - CMD 1002):
  - الاستعلام الأولي: يتم تلقائياً عند تسجيل الدخول عبر conn.init_data['lordSkillCtrl']
  - استخدام / تفعيل مهارة:
    cmd: "1002", subcmd: "22", data: {"setId": setId, "skillID": skillID}

المهارات المدعومة:
  1. 🌾 الحصاد الوافر (Bountiful Harvest) — skillID: 12008
     - كولداون: 8 ساعات (28,800 ثانية).
     - المجموعة: مواهب الأمير (setId: "2" أو activeSetID).
     - الوظيفة: جمع موارد فوري لجميع حقول ومباني الإنتاج في القلعة.

  2. ⚡ الجمع السريع (Crazy / Fast Gathering) — skillID: 12022
     - كولداون: 24 ساعة (86,400 ثانية).
     - المجموعة: مواهب الأمير (setId: "2" أو activeSetID).
     - الوظيفة: تسريع جمع الموارد من الخريطة بنسبة 100% لمدة ساعتين.

  3. 🏛️ حصاد المخزن (Warehouse Harvest) — skillID: 58120
     - كولداون: 24 ساعة (86,400 ثانية).
     - المجموعة: مهارات الجارية / الحسناء (setId: "999").
     - الوظيفة: الحصول على حزم موارد فورية من المخزن الملكي.

الاستعلام الذكي (Smart Inquiry):
  - فحص حالة التبريد (Cooldown) لكل مهارة بدقة متناهية من واقع سجلات السيرفر (CDData).
  - حساب الوقت المتبقي بالساعات والدقائق والثواني بدقة.
  - تفعيل المهارات الجاهزة فقط وتخطي المهارات التي لا تزال في فترة تبريد دون إرسال طلبات فاشلة.
  - محاكاة بشرية بفواصل زمنية عشوائية (Human Jitter) بين عمليات التفعيل.

الاستخدام كملف مستقل:
    python tasks/skills.py --email "johan2003@yopmail.com"
    python tasks/skills.py --email "ossso5030@gmail.com" --check-only
    python tasks/skills.py --email "meik.gaertner2306.mgr@gmail.com" --skills warehouse
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
import logging
import random
import time
import argparse
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from core.session_manager import SessionManager


# ════════════════════════════════════════════════════════════════════
#  تعريف المهارات المستهدفة وبياناتها
# ════════════════════════════════════════════════════════════════════

SUPPORTED_SKILLS: Dict[str, Dict[str, Any]] = {
    "harvest": {
        "id": 12008,
        "name": "الحصاد الوافر",
        "icon": "🌾",
        "default_set": "2",
        "base_cd": 28800,  # 8 ساعات
        "desc": "حصاد إنتاج جميع حقول القلعة فوراً"
    },
    "gather": {
        "id": 12022,
        "name": "الجمع السريع",
        "icon": "⚡",
        "default_set": "2",
        "base_cd": 86400,  # 24 ساعة
        "desc": "مضاعفة سرعة جمع الموارد 100% لمدة ساعتين"
    },
    "warehouse": {
        "id": 58120,
        "name": "حصاد المخزن",
        "icon": "🏛️",
        "default_set": "999",  # مهارة الجارية
        "base_cd": 86400,  # 24 ساعة
        "desc": "استلام موارد مجانية مباشرة من المخزن"
    }
}

# خريطة معرف المهارة إلى المفتاح
SKILL_ID_TO_KEY = {v["id"]: k for k, v in SUPPORTED_SKILLS.items()}


class SkillsTask(BaseTask):
    """
    مهمة الاستعلام الذكي وتفعيل المهارات التلقائية.
    """
    name = "skills"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.check_only: bool = self.config.get("check_only", False)
        # المهارات المطلوب فحصها وتفعيلها (الافتراضي: الكل)
        requested = self.config.get("skills")
        if requested:
            if isinstance(requested, str):
                self.target_keys = [k.strip().lower() for k in requested.split(",") if k.strip().lower() in SUPPORTED_SKILLS]
            elif isinstance(requested, (list, set)):
                self.target_keys = [k.lower() for k in requested if k.lower() in SUPPORTED_SKILLS]
            else:
                self.target_keys = list(SUPPORTED_SKILLS.keys())
        else:
            self.target_keys = list(SUPPORTED_SKILLS.keys())

    # ──────────────────────────────────────────────────────────────────
    #  الاستعلام الذكي عن المهارات (Smart Inquiry)
    # ──────────────────────────────────────────────────────────────────

    def get_skills_status(self) -> List[Dict[str, Any]]:
        """
        استعلام ذكي عن حالة المهارات، وأوقات التبريد المتبقية، وجاهزيتها.
        """
        lord_skill = self.conn.init_data.get("lordSkillCtrl", {})
        cd_data: Dict[str, Any] = lord_skill.get("CDData", {})
        active_set = str(lord_skill.get("activeSetID") or "2")
        set_list: Dict[str, Any] = lord_skill.get("setListData", {})
        now = time.time()

        results = []

        for key in self.target_keys:
            meta = SUPPORTED_SKILLS[key]
            skill_id = meta["id"]
            sid_str = str(skill_id)

            # 1. تحديد setId المناسب بذكاء وفحص الطقم النشط
            is_active_set_match = True
            is_unlocked = False

            if key == "warehouse":
                # حصاد المخزن دائماً طقم الجارية 999
                set_id = "999"
                s_list = set_list.get("999", {}).get("list", {})
                is_unlocked = (s_list.get(sid_str, 0) > 0)
            else:
                # مهارات مواهب الأمير
                active_set_skills = set_list.get(active_set, {}).get("list", {})
                if active_set_skills.get(sid_str, 0) > 0:
                    set_id = active_set
                    is_unlocked = True
                else:
                    # البحث في أي طقم آخر
                    found_set = None
                    for s_id, s_data in set_list.items():
                        if s_data.get("list", {}).get(sid_str, 0) > 0:
                            found_set = s_id
                            break
                    if found_set:
                        set_id = found_set
                        is_unlocked = True
                        if set_id != active_set:
                            is_active_set_match = False
                    else:
                        set_id = meta["default_set"]
                        is_unlocked = False

            # 2. فحص التبريد (CD calculation)
            cd_info = cd_data.get(sid_str)
            if not cd_info:
                # لا يوجد سجل تبريد إطلاقاً
                cd_total = meta["base_cd"]
                remain_sec = 0
                has_cooldown = False
            else:
                cd_total = cd_info.get("CD", meta["base_cd"])
                begin_time = cd_info.get("beginTime", 0)
                passed = now - begin_time
                remain_sec = max(0, int(cd_total - passed))
                has_cooldown = (remain_sec > 0)

            # 3. تحديد الجاهزية النهائية بدقة
            # المهارة جاهزة فقط إذا:
            # - مفتوحة في القلعة (is_unlocked)
            # - طقمها نشط (is_active_set_match أو طقم 999)
            # - ليست في فترة تبريد (not has_cooldown)
            is_ready = is_unlocked and is_active_set_match and (not has_cooldown)

            # تنسيق الوقت المتبقي
            h = remain_sec // 3600
            m = (remain_sec % 3600) // 60
            s = remain_sec % 60
            time_str = f"{h:02d}:{m:02d}:{s:02d}"

            results.append({
                "key": key,
                "id": skill_id,
                "name": meta["name"],
                "icon": meta["icon"],
                "desc": meta["desc"],
                "set_id": set_id,
                "active_set": active_set,
                "is_unlocked": is_unlocked,
                "is_active_set_match": is_active_set_match,
                "cd_total": cd_total,
                "remain_seconds": remain_sec,
                "remain_formatted": time_str,
                "is_ready": is_ready
            })

        return results

    # ──────────────────────────────────────────────────────────────────
    #  تفعيل مهارة واحدة (Skill Activation)
    # ──────────────────────────────────────────────────────────────────

    async def _activate_skill(self, skill_info: Dict[str, Any]) -> Tuple[bool, str]:
        """
        إرسال حزمة تفعيل المهارة إلى السيرفر والتحقق من النتيجة.
        """
        # إذا كانت المهارة غير مفتوحة في القلعة
        if not skill_info.get("is_unlocked", True):
            return False, "المهارة غير مفتوحة في القلعة أصلاً"

        # إذا كانت مهارة أمير ولكن الطقم الذي يحتويها غير نشط حالياً
        if not skill_info["is_active_set_match"] and skill_info["key"] != "warehouse":
            return False, f"المهارة في الطقم {skill_info['set_id']} بينما الطقم النشط هو {skill_info['active_set']}"

        payload = {
            "setId": str(skill_info["set_id"]),
            "skillID": int(skill_info["id"])
        }

        self.log.info(
            f"🚀 جارٍ تفعيل مهارة [{skill_info['name']}] (ID: {skill_info['id']}, Set: {skill_info['set_id']})..."
        )

        try:
            rsp = await self.conn.query("1002", "22", payload)
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر"

            err = str(rsp.get("err", ""))
            if err == "0":
                rsp_data = rsp.get("data", {})
                new_cd = rsp_data.get("CD", skill_info["cd_total"])
                # تحديث CDData محلياً
                lord_skill = self.conn.init_data.setdefault("lordSkillCtrl", {})
                cd_data = lord_skill.setdefault("CDData", {})
                cd_data[str(skill_info["id"])] = {
                    "CD": new_cd,
                    "beginTime": int(time.time())
                }
                hours = new_cd // 3600
                return True, f"تم التفعيل بنجاح (فترة التبريد: {hours} ساعة)"
            elif err == "3013" or err == "3027":
                return False, "المهارة لا تزال قيد فترة التبريد في السيرفر (In Cooldown)"
            elif err == "3020":
                return False, f"المهارة غير موجودة في طقم المواهب رقم {skill_info['set_id']}"
            elif err == "7":
                return False, f"طقم المواهب {skill_info['set_id']} غير نشط في القلعة"
            elif err == "3006":
                return False, "المهارة غير مفتوحة أو لم يتم تعلمها"
            else:
                return False, f"فشل التفعيل (كود الخطأ: {err})"
        except Exception as e:
            return False, f"استثناء أثناء إرسال الطلب: {e}"

    # ──────────────────────────────────────────────────────────────────
    #  تنفيذ المهمة (Main Task Flow)
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """
        تنفيذ الاستعلام والتفعيل التلقائي للمهارات الجاهزة.
        """
        # انتظار وصول بيانات lordSkillCtrl
        for _ in range(15):
            if "lordSkillCtrl" in self.conn.init_data:
                break
            await asyncio.sleep(0.3)

        skills = self.get_skills_status()
        if not skills:
            return TaskResult.fail("لم يتم العثور على مهارات للفحص!")

        ready_skills = [s for s in skills if s["is_ready"]]
        cooldown_skills = [s for s in skills if s["is_unlocked"] and not s["is_ready"]]
        locked_skills = [s for s in skills if not s["is_unlocked"]]

        # طباعة تقرير الاستعلام
        self._print_inquiry_report(skills)

        # إذا كان وضع الفحص فقط
        if self.check_only:
            msg = f"🔍 تم الاستعلام: جاهزة: {len(ready_skills)} | قيد التبريد: {len(cooldown_skills)} | غير مفتوحة: {len(locked_skills)}"
            return TaskResult.ok(msg, skills=skills, ready_count=len(ready_skills))

        if not ready_skills:
            return TaskResult.ok(
                f"⏳ لا توجد مهارات جاهزة للتفعيل حالياً (قيد التبريد: {len(cooldown_skills)} | غير مفتوحة: {len(locked_skills)})",
                skills=skills,
                activated=0
            )

        # البدء في تفعيل المهارات الجاهزة
        activated_count = 0
        failed_count = 0

        for i, skill in enumerate(ready_skills):
            # فاصل زمني أمان ضد الحظر (Human Jitter)
            if i > 0:
                jitter = round(random.uniform(2.0, 3.8), 2)
                self.log.info(f"🛡️ انتظار أمان بشري: {jitter} ثانية...")
                await asyncio.sleep(jitter)

            ok, note = await self._activate_skill(skill)
            if ok:
                activated_count += 1
                print(f"  {skill['icon']} [{skill['name']}]: ✅ {note}")
            else:
                failed_count += 1
                print(f"  {skill['icon']} [{skill['name']}]: ❌ {note}")

        summary = (
            f"🎯 اكتملت المهمة: تم تفعيل {activated_count} مهارة بنجاح"
            + (f" (وفشل {failed_count})" if failed_count > 0 else "")
            + f" | قيد التبريد: {len(cooldown_skills)}"
            + (f" | غير مفتوحة: {len(locked_skills)}" if locked_skills else "")
        )
        return TaskResult.ok(summary, activated=activated_count, failed=failed_count)

    # ──────────────────────────────────────────────────────────────────
    #  عرض التقرير التنسيقي في الطرفية
    # ──────────────────────────────────────────────────────────────────

    def _print_inquiry_report(self, skills: List[Dict[str, Any]]):
        print("\n" + "═" * 70)
        print("  🔮 استعلام حالة المهارات التلقائية (Smart Skills Inquiry)")
        print("═" * 70)

        for s in skills:
            icon = s["icon"]
            name = s["name"]
            sid = s["id"]
            set_id = s["set_id"]
            is_ready = s["is_ready"]
            remain = s["remain_formatted"]

            if not s["is_unlocked"]:
                status_str = "🔒 غير مفتوحة في القلعة"
            elif not s["is_active_set_match"] and s["key"] != "warehouse":
                status_str = f"⚠️ في طقم مواهب غير نشط (طقم {set_id} بينما النشط {s['active_set']})"
            elif is_ready:
                status_str = "🟢 جاهزة للتفعيل الآن!"
            else:
                status_str = f"⏳ في فترة تبريد (متبقي: {remain})"

            print(f"  {icon} {name:<14} (ID: {sid:<5} | طقم: {set_id:<3}) ──> {status_str}")

        print("═" * 70 + "\n")


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول كملف مستقل (CLI Runner)
# ════════════════════════════════════════════════════════════════════

async def _cli_main():
    parser = argparse.ArgumentParser(description="مهمة الاستعلام الذكي وتفعيل المهارات")
    parser.add_argument("--email", type=str, help="البريد الإلكتروني للحساب")
    parser.add_argument("--check-only", action="store_true", help="استعلام فقط وعرض حالة المهارات دون تفعيل")
    parser.add_argument("--skills", type=str, default=None, help="المهارات المطلوبة (harvest,gather,warehouse)")
    args = parser.parse_args()

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

    print(f"📡 جارٍ الاتصال بالحساب: {target_email}...")
    conn = GameConnection(acc)
    if not await conn.connect():
        print("❌ فشل الاتصال بالسيرفر!")
        return

    config = {
        "check_only": args.check_only,
        "skills": args.skills
    }

    task = SkillsTask(conn, config)
    res = await task.run()

    print(f"\n📊 النتيجة النهائية: {res.message}\n")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(_cli_main())
