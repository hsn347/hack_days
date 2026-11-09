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

  4. ⚡ الطاقة الوافرة (Abundant Stamina / Second Wind) — skillID: 13021
     - كولداون: 4 ساعات (14,400 ثانية).
     - المجموعة: مواهب الأمير - الدعم (setId: "3" أو activeSetID).
     - الوظيفة: الحصول على 30 نقطة طاقة فوراً.

  5. ⛏️ الاستخراج السريع (Fast Extraction / Quick Mining) — skillID: 12028
     - كولداون: 24 ساعة (86,400 ثانية).
     - المجموعة: مواهب الأمير - الدعم (setId: "3" أو activeSetID).
     - الوظيفة: مضاعفة سرعة استخراج وجمع الذهب 100% لمدة ساعتين.

الاستعلام الذكي (Smart Inquiry):
  - فحص حالة التبريد (Cooldown) لكل مهارة بدقة متناهية من واقع سجلات السيرفر (CDData).
  - حساب الوقت المتبقي بالساعات والدقائق والثواني بدقة.
  - تفعيل المهارات الجاهزة فقط وتخطي المهارات التي لا تزال في فترة تبريد دون إرسال طلبات فاشلة.
  - محاكاة بشرية بفواصل زمنية عشوائية (Human Jitter) بين عمليات التفعيل.

الاستخدام كملف مستقل:
    python tasks/skills.py --email "frankamar44@gmail.com" --skills stamina
    python tasks/skills.py --email "ossso5030@gmail.com" --check-only
    python tasks/skills.py --email "mohamedfarg6233@gmil.com" --skills stamina
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        getattr(sys.stdout, "reconfigure")(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        getattr(sys.stderr, "reconfigure")(encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import logging
import random
import time
import argparse
from typing import Any, Dict, List, Optional, Tuple, Union

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
        "base_cd": 28800,  # 8 ساعات
        "desc": "حصاد إنتاج جميع حقول القلعة فوراً"
    },
    "gather": {
        "id": 12022,
        "name": "الجمع السريع",
        "icon": "⚡",
        "base_cd": 86400,  # 24 ساعة
        "desc": "مضاعفة سرعة جمع الموارد 100% لمدة ساعتين"
    },
    "warehouse": {
        "id": 58120,
        "name": "حصاد المخزن",
        "icon": "🏛️",
        "base_cd": 86400,  # 24 ساعة
        "desc": "استلام موارد مجانية مباشرة من المخزن"
    },
    "stamina": {
        "id": 13021,
        "name": "الطاقة الوافرة",
        "icon": "⚡",
        "base_cd": 14400,  # 4 ساعات
        "desc": "استعادة 30 نقطة طاقة فوراً"
    },
    "fast_dig": {
        "id": 12028,
        "name": "الاستخراج السريع",
        "icon": "⛏️",
        "base_cd": 86400,  # 24 ساعة
        "desc": "زيادة سرعة جمع الذهب 100% لمدة ساعتين"
    }
}

# خريطة معرف المهارة إلى المفتاح
SKILL_ID_TO_KEY = {v["id"]: k for k, v in SUPPORTED_SKILLS.items()}

# خريطة أسماء ومترادفات المهارات
SKILL_ALIASES: Dict[str, str] = {
    "harvest": "harvest", "الحصاد": "harvest", "حصاد": "harvest", "الحصاد الوافر": "harvest", "حصاد وافر": "harvest", "12008": "harvest",
    "gather": "gather", "الجمع": "gather", "جمع": "gather", "الجمع السريع": "gather", "جمع سريع": "gather", "12022": "gather",
    "warehouse": "warehouse", "المخزن": "warehouse", "مخزن": "warehouse", "حصاد المخزن": "warehouse", "58120": "warehouse",
    "stamina": "stamina", "الطاقة": "stamina", "طاقة": "stamina", "الطاقة الوافرة": "stamina", "طاقة وافرة": "stamina", "13021": "stamina", "second_wind": "stamina", "ikinci_ruzgar": "stamina",
    "fast_dig": "fast_dig", "fastdig": "fast_dig", "hizlikazi": "fast_dig", "hizli_kazi": "fast_dig",
    "الاستخراج": "fast_dig", "استخراج": "fast_dig", "الاستخراج السريع": "fast_dig", "استخراج سريع": "fast_dig",
    "الحفر السريع": "fast_dig", "حفر سريع": "fast_dig", "12028": "fast_dig", "quick_mining": "fast_dig",
    "mining": "fast_dig", "extract": "fast_dig", "fast_extract": "fast_dig", "gold_mining": "fast_dig"
}


# ════════════════════════════════════════════════════════════════════
#  الدالة المساعدة: فحص وتحديد أطقم ومكان المهارة بذكاء
# ════════════════════════════════════════════════════════════════════

def find_skill_location(
    data_source: Any,
    skill_identifier: Union[int, str]
) -> Dict[str, Any]:
    """
    دالة فحص وتحديد الطقم أو الأطقم التي تتواجد فيها مهارة معينة.

    المعاملات:
      - data_source: يمكن تمرير أي من:
          * قاموس lordSkillCtrl مباشرة
          * قاموس conn.init_data الكامل
          * كائن GameConnection
      - skill_identifier: معرف المهارة برقم (مثال: 13021) أو اسم/مفتاح (مثال: 'stamina' أو 'الطاقة الوافرة')

    المخرجات:
      قاموس يحتوي على:
        - found: هل المهارة متعلمة وموجودة في أي طقم؟ (True/False)
        - skill_id: المعرف الرقمي للمهارة (int)
        - skill_name: الاسم المعرّب للمهارة
        - active_set_id: رقم الطقم النشط حالياً على القلعة
        - is_in_active_set: هل المهارة جاهزة وموجودة في الطقم النشط حالياً؟
        - recommended_set: الطقم الأفضل للاستخدام (النشط إن وجد، أو أول طقم يحوي المهارة)
        - needs_set_switch: هل يلزم إرسال أمر تبديل الطقم (1002/23) لتفعيلها؟
        - sets: قائمة تفصيلية بكل الأطقم التي وُجدت بها المهارة ونقاطها واسم الطقم
        - cooldown: تفاصيل وقت التبريد المتبقي إن وُجد
    """
    # 1. استخراج قاموس lordSkillCtrl بمرونة
    lord_skill: Dict[str, Any] = {}
    if hasattr(data_source, "init_data"):
        lord_skill = getattr(data_source, "init_data", {}).get("lordSkillCtrl", {})
    elif isinstance(data_source, dict):
        if "lordSkillCtrl" in data_source:
            lord_skill = data_source.get("lordSkillCtrl", {})
        elif "setListData" in data_source or "activeSetID" in data_source:
            lord_skill = data_source
        else:
            lord_skill = data_source.get("lordSkillCtrl", {})

    # 2. تحديد المعرف الرقمي وبيانات المهارة المستهدفة
    target_str = str(skill_identifier).strip().lower()
    canonical_key = SKILL_ALIASES.get(target_str, target_str)

    target_id: Optional[int] = None
    target_name = str(skill_identifier)
    target_icon = "✨"
    base_cd = 14400

    if canonical_key in SUPPORTED_SKILLS:
        meta = SUPPORTED_SKILLS[canonical_key]
        target_id = meta["id"]
        target_name = meta["name"]
        target_icon = meta["icon"]
        base_cd = meta["base_cd"]
    elif target_str.isdigit():
        target_id = int(target_str)
        # البحث في القاموس بالمعرف
        for k, v in SUPPORTED_SKILLS.items():
            if v["id"] == target_id:
                canonical_key = k
                target_name = v["name"]
                target_icon = v["icon"]
                base_cd = v["base_cd"]
                break

    if target_id is None:
        try:
            target_id = int(skill_identifier)
        except (ValueError, TypeError):
            return {
                "found": False,
                "error": f"تعذر التعرف على المهارة المستهدفة: '{skill_identifier}'",
                "skill_id": None,
                "skill_name": str(skill_identifier),
                "sets": []
            }

    sid_str = str(target_id)

    # 3. قراءة بيانات الأطقم النشطة من السيرفر
    active_set_id = str(lord_skill.get("activeSetID") or "1")
    set_list_data: Dict[str, Any] = lord_skill.get("setListData", {})
    cd_data: Dict[str, Any] = lord_skill.get("CDData", {})

    matching_sets: List[Dict[str, Any]] = []
    all_sets_summary: Dict[str, str] = {}

    # 4. فحص الأطقم والبحث عن المهارة
    for s_id, s_data in set_list_data.items():
        s_id_str = str(s_id)
        title = s_data.get("title") or f"طقم {s_id_str}"
        all_sets_summary[s_id_str] = title

        skill_points = s_data.get("list", {}).get(sid_str, 0)
        if skill_points > 0:
            matching_sets.append({
                "set_id": s_id_str,
                "title": title,
                "points": skill_points,
                "is_active": (s_id_str == active_set_id),
                "power": s_data.get("power", 0),
                "used_points": s_data.get("usedPoint", 0)
            })

    # حالة خاصة: مهارة الجارية (حصاد المخزن 58120) تتبع دائماً الطقم 999
    if target_id == 58120 and not matching_sets:
        s_999 = set_list_data.get("999", {})
        pts = s_999.get("list", {}).get(sid_str, 0)
        matching_sets.append({
            "set_id": "999",
            "title": "مهارات الجارية",
            "points": pts if pts > 0 else 1,
            "is_active": True,
            "power": 0,
            "used_points": 0
        })

    is_found = len(matching_sets) > 0
    is_in_active = any(s["is_active"] for s in matching_sets)

    # تحديد الطقم الموصى به:
    # 1. إذا كانت في الطقم النشط، نستخدمه لتفادي التبديل
    # 2. وإلا نستخدم أول طقم وُجدت به المهارة
    recommended_set: Optional[str] = None
    if is_in_active:
        recommended_set = active_set_id
    elif is_found:
        recommended_set = matching_sets[0]["set_id"]

    needs_switch = (is_found and not is_in_active and target_id != 58120)

    # 5. حساب وقت التبريد (CD calculation)
    now = time.time()
    cd_info = cd_data.get(sid_str)
    if cd_info:
        total_cd = cd_info.get("CD", base_cd)
        begin_time = cd_info.get("beginTime", 0)
        passed = now - begin_time
        remain_sec = max(0, int(total_cd - passed))
    else:
        total_cd = base_cd
        remain_sec = 0

    h = remain_sec // 3600
    m = (remain_sec % 3600) // 60
    s = remain_sec % 60
    remain_formatted = f"{h:02d}:{m:02d}:{s:02d}"

    return {
        "found": is_found,
        "skill_id": target_id,
        "skill_key": canonical_key,
        "skill_name": target_name,
        "icon": target_icon,
        "active_set_id": active_set_id,
        "is_in_active_set": is_in_active,
        "recommended_set": recommended_set,
        "needs_set_switch": needs_switch,
        "sets": matching_sets,
        "all_available_sets": all_sets_summary,
        "cooldown": {
            "in_cooldown": (remain_sec > 0),
            "remain_seconds": remain_sec,
            "remain_formatted": remain_formatted,
            "total_cd": total_cd
        }
    }


class SkillsTask(BaseTask):
    """
    مهمة الاستعلام الذكي وتفعيل المهارات التلقائية.
    """
    name = "skills"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.check_only: bool = self.config.get("check_only", False)
        # المهارات المطلوب فحصها وتفعيلها (الافتراضي: الكل)
        requested = self.config.get("skills") or self.config.get("target_skills")
        if requested:
            if isinstance(requested, str):
                raw = [k.strip().lower() for k in requested.split(",")]
            elif isinstance(requested, (list, set, tuple)):
                raw = [str(k).strip().lower() for k in requested]
            else:
                raw = list(SUPPORTED_SKILLS.keys())

            self.target_keys = []
            for r in raw:
                resolved = SKILL_ALIASES.get(r, r)
                if resolved in SUPPORTED_SKILLS and resolved not in self.target_keys:
                    self.target_keys.append(resolved)
        else:
            self.target_keys = list(SUPPORTED_SKILLS.keys())

    # ──────────────────────────────────────────────────────────────────
    #  الاستعلام الذكي عن المهارات (Smart Inquiry)
    # ──────────────────────────────────────────────────────────────────

    def get_skills_status(self) -> List[Dict[str, Any]]:
        """
        استعلام ذكي عن حالة المهارات، وأماكن أطقمها، وأوقات التبريد المتبقية، وجاهزيتها.
        يستخدم دالة find_skill_location لفحص أطقم المواهب وتحديد الطقم الأنسب بذكاء.
        """
        lord_skill = self.conn.init_data.get("lordSkillCtrl", {})
        active_set = str(lord_skill.get("activeSetID") or "1")
        vip_ctrl = self.conn.init_data.get("vipCtrl", {})
        vip_lv = int(vip_ctrl.get("vipLv", 0)) if isinstance(vip_ctrl, dict) else 0
        has_free_switch = (vip_lv >= 7)

        results = []

        for key in self.target_keys:
            meta = SUPPORTED_SKILLS.get(key)
            if not meta:
                continue

            skill_id = meta["id"]

            # فحص موقع وأطقم المهارة بدقة عبر دالة find_skill_location
            loc = find_skill_location(lord_skill, key)

            is_unlocked = loc.get("found", False)
            target_set = str(loc.get("recommended_set") or active_set)
            is_active_set_match = loc.get("is_in_active_set", False)
            needs_set_switch = loc.get("needs_set_switch", False)
            cooldown_data = loc.get("cooldown", {})

            has_cooldown = cooldown_data.get("in_cooldown", False)
            remain_sec = cooldown_data.get("remain_seconds", 0)
            time_str = cooldown_data.get("remain_formatted", "00:00:00")
            cd_total = cooldown_data.get("total_cd", meta["base_cd"])

            # المهارة جاهزة إذا كانت مفتوحة بنقاط مواهب في القلعة وليست في فترة تبريد
            # حماية الذهب: التبديل بين أطقم المواهب مجاني فقط عند VIP 7 فما فوق (خلاف ذلك يخصم 1000 ذهب)
            skip_reason = None
            if needs_set_switch and not has_free_switch and key != "warehouse":
                is_ready = False
                skip_reason = f"تتطلب طقم المواهب [{target_set}] ولكن القلعة VIP {vip_lv} (التبديل المجاني يتطلب VIP 7+ لمنع استهلاك 1000 ذهب)"
            else:
                is_ready = is_unlocked and (not has_cooldown)

            results.append({
                "key": key,
                "id": skill_id,
                "name": meta["name"],
                "icon": meta["icon"],
                "desc": meta["desc"],
                "set_id": target_set,
                "active_set": active_set,
                "is_unlocked": is_unlocked,
                "is_active_set_match": is_active_set_match,
                "needs_set_switch": needs_set_switch,
                "matching_sets": loc.get("sets", []),
                "cd_total": cd_total,
                "remain_seconds": remain_sec,
                "remain_formatted": time_str,
                "is_ready": is_ready,
                "skip_reason": skip_reason
            })

        return results

    # ──────────────────────────────────────────────────────────────────
    #  تفعيل مهارة واحدة (Skill Activation)
    # ──────────────────────────────────────────────────────────────────

    async def _activate_skill(self, skill_info: Dict[str, Any]) -> Tuple[bool, str]:
        """
        إرسال حزمة تفعيل المهارة إلى السيرفر والتحقق من النتيجة.
        يدعم التبديل التلقائي الذكي بين أطقم المواهب (Talent Sets) بحماية VIP 7+ والعودة المؤكدة للطقم الأصلي عبر try...finally.
        """
        # إذا كانت المهارة غير مفتوحة في القلعة أصلاً
        if not skill_info.get("is_unlocked", False):
            return False, "المهارة غير مفتوحة أو لم يتم توزيع نقاط المواهب عليها في أي طقم"

        target_set = str(skill_info["set_id"])
        active_set = str(skill_info.get("active_set", "1"))
        need_switch = skill_info.get("needs_set_switch", False) and (target_set != active_set) and (skill_info["key"] != "warehouse")

        vip_ctrl = self.conn.init_data.get("vipCtrl", {})
        vip_lv = int(vip_ctrl.get("vipLv", 0)) if isinstance(vip_ctrl, dict) else 0

        if need_switch and vip_lv < 7:
            return False, f"تم تخطي التبديل إلى الطقم [{target_set}] لحماية الذهب (القلعة VIP {vip_lv} والتبديل المجاني يتطلب VIP 7+)"

        switched = False
        try:
            if need_switch:
                self.log.info(
                    f"🔄 تبديل طقم المواهب من [{active_set}] إلى [{target_set}] لتفعيل مهارة [{skill_info['name']}] (VIP {vip_lv} مجاني)..."
                )
                sw_rsp = await self.conn.query("1002", "23", {"setID": target_set})
                if not sw_rsp or str(sw_rsp.get("err", "")) != "0":
                    err_code = str(sw_rsp.get("err", "timeout")) if sw_rsp else "no_response"
                    return False, f"فشل تبديل طقم المواهب إلى {target_set} (كود {err_code}) — تحقق من تفعيل الـ VIP"
                switched = True
                if "lordSkillCtrl" in self.conn.init_data:
                    self.conn.init_data["lordSkillCtrl"]["activeSetID"] = target_set
                await asyncio.sleep(1.0)

            payload = {
                "setId": target_set,
                "skillID": int(skill_info["id"])
            }

            self.log.info(
                f"🚀 جارٍ تفعيل مهارة [{skill_info['name']}] (ID: {skill_info['id']}, Set: {target_set})..."
            )

            rsp = await self.conn.query("1002", "22", payload)
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر أثناء تفعيل المهارة"

            err = str(rsp.get("err", ""))

            # في حال وجود خطأ 7 (طقم غير نشط) ولم نكن قد قمنا بالتبديل مسبقاً (مع التحقق من VIP 7+)
            if err == "7" and not switched and skill_info["key"] != "warehouse" and vip_lv >= 7:
                self.log.info(f"🔄 إعادة المحاولة مع تبديل طقم المواهب إلى {target_set}...")
                sw_rsp = await self.conn.query("1002", "23", {"setID": target_set})
                if sw_rsp and str(sw_rsp.get("err", "")) == "0":
                    switched = True
                    if "lordSkillCtrl" in self.conn.init_data:
                        self.conn.init_data["lordSkillCtrl"]["activeSetID"] = target_set
                    await asyncio.sleep(1.0)
                    rsp = await self.conn.query("1002", "22", payload)
                    err = str(rsp.get("err", "")) if rsp else "no_response"

            if err == "0" and isinstance(rsp, dict):
                rsp_data = rsp.get("data", {})
                new_cd = rsp_data.get("CD", skill_info["cd_total"]) if isinstance(rsp_data, dict) else skill_info["cd_total"]
                # تحديث CDData محلياً
                lord_skill = self.conn.init_data.setdefault("lordSkillCtrl", {})
                cd_data = lord_skill.setdefault("CDData", {})
                cd_data[str(skill_info["id"])] = {
                    "CD": new_cd,
                    "beginTime": int(time.time())
                }
                hours = new_cd // 3600
                hours_label = f"{hours} ساعات" if (3 <= hours <= 10) else (f"{hours} ساعة" if hours > 10 else ("ساعتان" if hours == 2 else "ساعة واحدة"))
                return True, f"تم التفعيل بنجاح (فترة التبريد: {hours_label})"
            elif err == "3013" or err == "3027":
                return False, "المهارة لا تزال قيد فترة التبريد في السيرفر (In Cooldown)"
            elif err == "3020":
                return False, f"المهارة غير موجودة في طقم المواهب رقم {target_set}"
            elif err == "7":
                return False, f"طقم المواهب {target_set} غير نشط في القلعة"
            elif err == "3006":
                return False, "المهارة غير مفتوحة أو لم يتم تعلمها"
            else:
                return False, f"فشل التفعيل (كود الخطأ: {err})"

        except Exception as e:
            return False, f"استثناء أثناء تفعيل المهارة: {e}"

        finally:
            if switched:
                self.log.info(f"🛡️ انتظار أمان 2.5 ثانية قبل استرجاع الطقم الأصلي [{active_set}]...")
                await asyncio.sleep(2.5)
                self.log.info(f"🔁 إعادة تفعيل الطقم الأصلي [{active_set}] بعد اكتمال المهارة...")
                try:
                    re_rsp = await self.conn.query("1002", "23", {"setID": active_set})
                    if re_rsp and str(re_rsp.get("err", "")) == "0":
                        self.log.info(f"✅ تم استرجاع الطقم الأصلي [{active_set}] بنجاح.")
                        if "lordSkillCtrl" in self.conn.init_data:
                            self.conn.init_data["lordSkillCtrl"]["activeSetID"] = active_set
                    else:
                        self.log.warning(f"⚠️ تنبيه أثناء استرجاع الطقم الأصلي [{active_set}]: {re_rsp} — إعادة المحاولة...")
                        await asyncio.sleep(2.5)
                        re_rsp2 = await self.conn.query("1002", "23", {"setID": active_set})
                        if re_rsp2 and str(re_rsp2.get("err", "")) == "0":
                            self.log.info(f"✅ تم استرجاع الطقم الأصلي [{active_set}] بنجاح في المحاولة الثانية.")
                            if "lordSkillCtrl" in self.conn.init_data:
                                self.conn.init_data["lordSkillCtrl"]["activeSetID"] = active_set
                        else:
                            self.log.error(f"❌ فشل استرجاع الطقم الأصلي [{active_set}]: {re_rsp2}")
                except Exception as ex:
                    self.log.warning(f"⚠️ خطأ أثناء استرجاع الطقم الأصلي [{active_set}]: {ex}")

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

        # طباعة تنبيهات المهارات التي تم تخطي تبديل أطقمها لحماية الذهب
        for s in skills:
            if s.get("skip_reason"):
                self.log.info(f"⏭️ {s['icon']} [{s['name']}]: {s['skip_reason']}")

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
                self.log.info(f"{skill['icon']} [{skill['name']}]: ✅ {note}")
            else:
                failed_count += 1
                self.log.warning(f"{skill['icon']} [{skill['name']}]: ❌ {note}")

        skills_word = "مهارة واحدة" if activated_count == 1 else ("مهارتين" if activated_count == 2 else f"{activated_count} مهارات")
        summary = (
            f"🎯 اكتملت المهمة: تم تفعيل {skills_word} بنجاح"
            + (f" (وفشل {failed_count})" if failed_count > 0 else "")
            + f" | قيد التبريد: {len(cooldown_skills)}"
            + (f" | غير مفتوحة: {len(locked_skills)}" if locked_skills else "")
        )
        return TaskResult.ok(summary, activated=activated_count, failed=failed_count)

    # ──────────────────────────────────────────────────────────────────
    #  عرض التقرير التنسيقي في الطرفية
    # ──────────────────────────────────────────────────────────────────

    def _print_inquiry_report(self, skills: List[Dict[str, Any]]):
        """تقرير الطرفية — معطّل في Thread Pool mode (المعلومات تمر عبر Firebase)."""
        pass


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
