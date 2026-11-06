# -*- coding: utf-8 -*-
"""
tasks/skill_finder.py — أداة ودالة استكشاف وتحديد أطقم وأماكن المهارات (Skill Finder)
══════════════════════════════════════════════════════════════════════════════════════
الغرض:
  - دالة برمجية مستقلة وقابلة لإعادة الاستخدام لمعرفة الطقم (setID) أو الأطقم
    التي تتواجد فيها مهارة معينة داخل مواهب الأمير (lordSkillCtrl).
  - تحديد ما إذا كانت المهارة في الطقم النشط حالياً، أو تتطلب تبديل الطقم (needs_switch).
  - فحص نقاط ومستوى المهارة، وفترة التبريد المتبقية (CD).
  - تشغيل فحص مباشر ومستقل لأي حساب عبر سطر الأوامر (CLI).

الاستخدام البرمجي:
    from tasks.skill_finder import find_skill_location, inspect_account_skills

    loc = find_skill_location(conn.init_data.get("lordSkillCtrl"), "stamina")
    print(loc["found"], loc["recommended_set"], loc["is_in_active_set"])

الاستخدام عبر الطرفية:
    python tasks/skill_finder.py --skill stamina
    python tasks/skill_finder.py --skill 13021
    python tasks/skill_finder.py --skill "الطاقة الوافرة" --email "mohamedfarg6233@gmil.com"
    python tasks/skill_finder.py --all --email "user@gmail.com"
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

import argparse
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

from core.session_manager import SessionManager
from game_client import GameConnection

log = logging.getLogger("SkillFinder")

# ════════════════════════════════════════════════════════════════════
#  قاموس المهارات الشائعة والمعروفة
# ════════════════════════════════════════════════════════════════════

KNOWN_SKILLS: Dict[str, Dict[str, Any]] = {
    "stamina": {
        "id": 13021,
        "name": "الطاقة الوافرة",
        "icon": "⚡",
        "tree": "دعم / مساندة (Support)",
        "base_cd": 14400,
        "desc": "استعادة 30 نقطة طاقة فوراً (مهارة اللورد)"
    },
    "harvest": {
        "id": 12008,
        "name": "الحصاد الوافر",
        "icon": "🌾",
        "tree": "تطوير / إنتاج (Economy)",
        "base_cd": 28800,
        "desc": "حصاد إنتاج جميع حقول القلعة فوراً"
    },
    "gather": {
        "id": 12022,
        "name": "الجمع السريع",
        "icon": "⚡",
        "tree": "تطوير / إنتاج (Economy)",
        "base_cd": 86400,
        "desc": "مضاعفة سرعة جمع الموارد 100% لمدة ساعتين"
    },
    "warehouse": {
        "id": 58120,
        "name": "حصاد المخزن",
        "icon": "🏛️",
        "tree": "مهارة الجارية (Maiden / Set 999)",
        "base_cd": 86400,
        "desc": "استلام موارد مجانية مباشرة من المخزن"
    },
    "fast_dig": {
        "id": 12028,
        "name": "الاستخراج السريع",
        "icon": "⛏️",
        "tree": "تطوير / إنتاج (Economy)",
        "base_cd": 86400,
        "desc": "زيادة سرعة جمع الذهب 100% لمدة ساعتين"
    },
    # مهارات قتالية إضافية
    "march_speed": {
        "id": 11011,
        "name": "السرعة الفائقة",
        "icon": "🐎",
        "tree": "معركة / حرب (War)",
        "base_cd": 86400,
        "desc": "زيادة سرعة المسيرة"
    },
    "instant_recall": {
        "id": 11028,
        "name": "الاستدعاء الفوري",
        "icon": "📯",
        "tree": "معركة / حرب (War)",
        "base_cd": 86400,
        "desc": "استرجاع جميع القوات العائدة أو السائرة فوراً"
    },
    "rescue": {
        "id": 11029,
        "name": "الإنقاذ العام",
        "icon": "🛡️",
        "tree": "معركة / حرب (War)",
        "base_cd": 86400,
        "desc": "تحويل الخسائر البشرية في أول معركة إلى جرحى"
    },
    "total_defense": {
        "id": 11033,
        "name": "الدفاع الشامل",
        "icon": "🏰",
        "tree": "معركة / حرب (War)",
        "base_cd": 86400,
        "desc": "زيادة دفاع القلعة"
    }
}

# خريطة المترادفات والأسماء لتسهيل البحث بأي صيغة
SKILL_ALIASES: Dict[str, str] = {
    # الطاقة الوافرة
    "stamina": "stamina", "طاقة": "stamina", "الطاقة": "stamina",
    "الطاقة الوافرة": "stamina", "طاقة وافرة": "stamina", "13021": "stamina",
    "second_wind": "stamina", "ikinci_ruzgar": "stamina",
    # الحصاد
    "harvest": "harvest", "حصاد": "harvest", "الحصاد": "harvest",
    "الحصاد الوافر": "harvest", "حصاد وافر": "harvest", "12008": "harvest",
    # الجمع السريع
    "gather": "gather", "جمع": "gather", "الجمع": "gather",
    "الجمع السريع": "gather", "جمع سريع": "gather", "12022": "gather",
    # المخزن
    "warehouse": "warehouse", "مخزن": "warehouse", "المخزن": "warehouse",
    "حصاد المخزن": "warehouse", "58120": "warehouse",
    # الاستخراج السريع
    "fast_dig": "fast_dig", "hizlikazi": "fast_dig", "fastdig": "fast_dig",
    "استخراج": "fast_dig", "الاستخراج": "fast_dig", "الاستخراج السريع": "fast_dig",
    "حفر": "fast_dig", "الحفر السريع": "fast_dig", "12028": "fast_dig",
    # المهارات الأخرى
    "march_speed": "march_speed", "11011": "march_speed", "السرعة": "march_speed",
    "recall": "instant_recall", "11028": "instant_recall", "استدعاء": "instant_recall",
    "rescue": "rescue", "11029": "rescue", "انقاذ": "rescue", "الإنقاذ": "rescue",
    "defense": "total_defense", "11033": "total_defense", "دفاع": "total_defense"
}


# ════════════════════════════════════════════════════════════════════
#  الدالة الرئيسية: تحديد مكان وطقم المهارة
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

    if canonical_key in KNOWN_SKILLS:
        meta = KNOWN_SKILLS[canonical_key]
        target_id = meta["id"]
        target_name = meta["name"]
        target_icon = meta["icon"]
        base_cd = meta["base_cd"]
    elif target_str.isdigit():
        target_id = int(target_str)
        # البحث في القاموس بالمعرف
        for k, v in KNOWN_SKILLS.items():
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


# ════════════════════════════════════════════════════════════════════
#  فحص شامل لجميع المهارات الشائعة دفعة واحدة
# ════════════════════════════════════════════════════════════════════

def find_all_skills_locations(data_source: Any) -> Dict[str, Dict[str, Any]]:
    """
    فحص جميع المهارات الشائعة وإرجاع تقرير بمكان وطقم كل مهارة منها.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for key in KNOWN_SKILLS:
        results[key] = find_skill_location(data_source, key)
    return results


# ════════════════════════════════════════════════════════════════════
#  الاتصال المباشر وفحص حساب من session_cache.json
# ════════════════════════════════════════════════════════════════════

async def inspect_account_skills(
    email: Optional[str] = None,
    target_skill: Optional[str] = None
) -> Dict[str, Any]:
    """
    يقوم بالاتصال المباشر بالحساب عبر GameConnection،
    وانتظار بيانات lordSkillCtrl، ثم استخراج مواقع وأطقم المهارات وطباعتها.
    """
    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد حسابات مسجلة في session_cache.json!")
        return {"error": "no_accounts"}

    target_email = email or next(iter(accounts.keys()))
    acc = accounts.get(target_email)
    if not acc:
        print(f"❌ الحساب {target_email} غير موجود في الجلسات!")
        return {"error": "account_not_found"}

    print(f"📡 جارٍ الاتصال بالحساب: {target_email}...")
    conn = GameConnection(acc)
    ok = await conn.connect()
    if not ok:
        print("❌ فشل الاتصال بالسيرفر!")
        return {"error": "connect_failed"}

    # انتظار وصول بيانات lordSkillCtrl من خادم اللعبة
    for _ in range(15):
        if "lordSkillCtrl" in conn.init_data:
            break
        await asyncio.sleep(0.3)

    lord_skill = conn.init_data.get("lordSkillCtrl", {})
    if not lord_skill:
        print("⚠️ لم تصل بيانات lordSkillCtrl من السيرفر بعد.")
        await conn.close()
        return {"error": "no_lord_skill_data"}

    active_set = str(lord_skill.get("activeSetID") or "1")
    set_list = lord_skill.get("setListData", {})

    print("\n" + "═" * 60)
    print(f"🏰 تقرير أطقم مواهب القلعة | الحساب: {target_email}")
    print(f"📌 الطقم النشط حالياً في القلعة: [طقم رقم {active_set}]")
    print(f"📋 الأطقم المعرفة في القلعة:")
    for sid, sdata in sorted(set_list.items(), key=lambda x: str(x[0])):
        t_title = sdata.get("title") or "بدون اسم"
        pts = sdata.get("usedPoint", 0)
        skills_cnt = len(sdata.get("list", {}))
        is_act = " (النشط حالياً 🟢)" if str(sid) == active_set else ""
        print(f"   - طقم {sid}: '{t_title}' | النقاط المستخدمة: {pts} | المهارات: {skills_cnt}{is_act}")
    print("═" * 60 + "\n")

    report: Dict[str, Any] = {}

    if target_skill:
        # فحص مهارة واحدة محددة
        res = find_skill_location(lord_skill, target_skill)
        _print_single_skill_report(res)
        report[res.get("skill_key") or str(target_skill)] = res
    else:
        # فحص جميع المهارات الأساسية
        print("🔍 نتائج فحص المهارات الأساسية:")
        all_res = find_all_skills_locations(lord_skill)
        for k, res in all_res.items():
            _print_single_skill_report(res)
        report = all_res

    await conn.close()
    return report


def _print_single_skill_report(res: Dict[str, Any]):
    """طباعة بطاقة تقرير أنيقة للمهارة."""
    name = res.get("skill_name", "غير معروف")
    icon = res.get("icon", "✨")
    sid = res.get("skill_id", "—")
    found = res.get("found", False)
    in_act = res.get("is_in_active_set", False)
    rec_set = res.get("recommended_set")
    needs_sw = res.get("needs_set_switch", False)
    cd = res.get("cooldown", {})

    cd_status = f"⏳ تبريد متبقي: {cd.get('remain_formatted')}" if cd.get("in_cooldown") else "🟢 جاهزة فوراً"

    if not found:
        print(f"{icon} [{name}] (ID: {sid}):")
        print(f"   ❌ غير موجودة في أي طقم مواهب! (اللاعب لم يضع نقاطاً في شجرتها)")
        print(f"   الحالة: {cd_status}\n")
        return

    sets_info = []
    for s in res.get("sets", []):
        act_mark = " [نشط حالياً ⚡]" if s["is_active"] else ""
        sets_info.append(f"طقم {s['set_id']} ('{s['title']}' - نقاط: {s['points']}){act_mark}")

    print(f"{icon} [{name}] (ID: {sid}):")
    print(f"   📍 الأطقم التي تتواجد فيها: {', '.join(sets_info)}")
    if in_act:
        print(f"   ✅ متوفرة في الطقم النشط حالياً! (لا تحتاج أي تبديل للأطقم)")
    else:
        print(f"   ⚠️ ليست في الطقم النشط. (يلزم التبديل إلى طقم {rec_set} عبر أمر 1002/23)")
    print(f"   ⏱️ حالة التبريد: {cd_status}\n")


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول من سطر الأوامر (CLI)
# ════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="أداة فحص وتحديد الطقم ومكان المهارة في مواهب الأمير"
    )
    parser.add_argument(
        "--skill", "-s",
        type=str,
        default=None,
        help="اسم أو معرف المهارة (مثال: stamina أو 13021 أو 'الطاقة الوافرة')"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        default=None,
        help="البريد الإلكتروني للحساب المراد فحصه من session_cache.json"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="فحص جميع المهارات المدعومة بالكامل"
    )

    args = parser.parse_args()

    target = args.skill
    if not target and not args.all:
        # الافتراضي مهارة الطاقة الوافرة
        target = "stamina"

    asyncio.run(inspect_account_skills(email=args.email, target_skill=None if args.all else target))


if __name__ == "__main__":
    main()
