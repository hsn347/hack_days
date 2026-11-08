# -*- coding: utf-8 -*-
"""
tasks/monster.py — مهمة الهجوم على الغزاة والمتمردين (Monsters & Rebels Attack)
══════════════════════════════════════════════════════════════════════════════
# الهجوم على المتمردين (Rebels):
python tasks/monster.py --email "avgch1@gmail.com" --type invaders --minlv 1 --maxlv 2 --marches 6

# أو الهجوم على الغزاة (Invaders):
python tasks/monster.py --email "johan2003@yopmail.com" --type rebels --minlv 3 --maxlv 4 --marches 6



تُرسِل مسيرات هجوم وقتال متتالية ضد الغزاة (Invaders) أو المتمردين (Rebels).

أنواع الأهداف:
    • "rebels"   : 🏴‍☠️ متمردين  (mapType=35, subType=0)
    • "invaders" : 👾 غزاة      (mapType=6,  subType=0)

نظام التشكيلة والأبطال:
    1. استخدام أبطال وحيوانات وجيوش التشكيلة المحفوظة (1005/7) إن كانوا متاحين.
    2. إذا كان أبطال التشكيلة مشغولين:
       - يُرسل أبطال الحرب والقتال فقط (5501xxx) الذين يمتلكون مهارات قتال وهجوم (5610xxx / 5640xxx).
       - يُستبعد أبطال الجمع (5502xxx) وأبطال الدعم الداخلي (5503xxx) تماماً.

الإعدادات (config / Firebase):
    monster_type : نوع الهدف ("rebels" أو "invaders") [افتراضي: "rebels"]
    min_lv       : أدنى مستوى للهدف [افتراضي: 1]
    max_lv       : أعلى مستوى للهدف [افتراضي: 30]
    max_marches  : الحد الأقصى للمسيرات [افتراضي: 6]
    search_range : نطاق البحث على الخريطة [افتراضي: 50]
    formation_id : رقم التشكيلة المحفوظة [افتراضي: 1]
"""

from __future__ import annotations

import sys
import os

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import json
import logging
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from tasks.exclude_manager import get_manager as _get_exclude_manager
from tasks.march_capacity import get_castle_march_capacity, enforce_safe_march_troops, record_learned_march_capacity


# ════════════════════════════════════════════════════════════════════
#  إعدادات افتراضية في رأس الملف (قابلة للتعديل والربط بـ Firebase)
# ════════════════════════════════════════════════════════════════════

DEFAULT_MONSTER_TYPE       = "invaders"         # "rebels" (متمردين: 35) أو "invaders" (غزاة: 6)
DEFAULT_MIN_LV             = 1                # أدنى مستوى
DEFAULT_MAX_LV             = 30               # أقصى مستوى
DEFAULT_MAX_MARCHES        = 64                # الحد الأقصى للمسيرات
DEFAULT_SEARCH_RANGE       = 100               # نطاق البحث
DEFAULT_FORMATION_ID       = 1                # رقم التشكيلة المفضلة (1..5) [0 = تلقائي ذكي بدون تشكيلة ثابتة]
DEFAULT_TROOPS_COUNT       = 30000            # عدد الجنود الافتراضي في حال عدم وجود تشكيلة

# خريطة أنواع الأهداف
MONSTER_TYPES = {
    "rebels":   {"mapType": 35, "subType": 0, "name": "🏴‍☠️ متمردين (Rebels)"},
    "invaders": {"mapType": 6,  "subType": 0, "name": "👾 غزاة (Invaders)"},
}


# ════════════════════════════════════════════════════════════════════
#  إدارة استبعاد الأهداف المكررة (مدير مركزي موحد)
#  → تم نقلها إلى tasks/exclude_manager.py
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
#  جداول اللعبة الرسمية (Official Server Data & Capacities)
# ════════════════════════════════════════════════════════════════════

# القوة الرسمية الدقيقة للغزاة (Invaders FC) من ملف npc.lua للعبة لجميع المستويات 1 إلى 35
OFFICIAL_NPC_FC: Dict[int, int] = {
    1: 30,
    2: 250,
    3: 740,
    4: 1694,
    5: 2765,
    6: 4945,
    7: 7418,
    8: 10404,
    9: 17294,
    10: 23084,
    11: 30142,
    12: 38622,
    13: 49767,
    14: 61408,
    15: 74751,
    16: 91404,
    17: 110626,
    18: 132470,
    19: 156972,
    20: 231400,
    21: 279580,
    22: 334960,
    23: 397750,
    24: 468160,
    25: 546390,
    26: 760670,
    27: 855840,
    28: 960000,
    29: 1073300,
    30: 1105534,
    31: 1406856,
    32: 1559454,
    33: 1763550,
    34: 2018664,
    35: 2040892,
}

# القوة الرسمية الدقيقة لنخبة المتمردين (Elite Rebels FC) من ملف world_boss_show.lua للعبة (المستويات 1 إلى 5)
OFFICIAL_REBEL_FC: Dict[int, int] = {
    1: 60000,       # لفل 1: القوة 60,000 (حامية 18,700 جندي T2/T3)
    2: 312000,      # لفل 2: القوة 312,000 (حامية 53,600 جندي T4/T5)
    3: 1196000,     # لفل 3: القوة 1,196,000 (حامية 129,000 جندي T6/T7)
    4: 3020000,     # لفل 4: القوة 3,020,000 (حامية 266,800 جندي T7/T8)
    5: 7518000,     # لفل 5: القوة 7,518,000 (حامية 475,200 جندي T9/T10)
}

# السعة الإضافية لمبنى ساحة التدريب (bid 121 - Drill Grounds) من build121.lua للمستويات 1 إلى 35
# (ملاحظة: تضاف إلى السعة الأساسية DEFAULT_EXP_ARMY_COUNT = 1000)
BUILD121_CAPACITY: Dict[int, int] = {
    1: 300, 2: 400, 3: 500, 4: 800, 5: 1000, 6: 1200, 7: 1500, 8: 1800, 9: 2700, 10: 3600,
    11: 5500, 12: 8200, 13: 11300, 14: 13500, 15: 16300, 16: 18800, 17: 21600, 18: 24800, 19: 28300, 20: 31800,
    21: 36400, 22: 39900, 23: 44700, 24: 48200, 25: 52800, 26: 56300, 27: 59800, 28: 64400, 29: 67900, 30: 70400,
    31: 76200, 32: 76200, 33: 76200, 34: 76200, 35: 76200
}

# القوة الرسمية الأساسية لكل رتبة جندي (Official Unit Tier Power) من armyinfo.lua
ARMY_TIER_POWER: Dict[int, float] = {
    1: 1.0,   # T1  (401, 501, 601, 701)
    2: 1.4,   # T2  (402, 502, 602, 702)
    3: 1.9,   # T3  (403, 503, 603, 703)
    4: 2.5,   # T4  (404, 504, 604, 704)
    5: 3.2,   # T5  (405, 505, 605, 705)
    6: 4.0,   # T6  (406, 506, 606, 706)
    7: 4.9,   # T7  (407, 507, 607, 707)
    8: 5.9,   # T8  (408, 508, 608, 708)
    9: 7.0,   # T9  (409, 509, 609, 709)
    10: 8.2,  # T10 (410, 510, 610, 710)
    11: 9.5,  # T11 (411, 511, 611, 711)
    12: 11.0, # T12 (412, 512, 612, 712)
}

def get_unit_tier(army_id: int) -> int:
    """استخراج رتبة الجندي (Tier) من معرف الوحدة (مثال: 401 -> 1, 511 -> 11)."""
    return int(army_id) % 100

def get_unit_power(army_id: int) -> float:
    """إرجاع القوة الأساسية للوحدة الواحدة."""
    tier = get_unit_tier(army_id)
    return ARMY_TIER_POWER.get(tier, 1.0 + tier * 0.8)


# ════════════════════════════════════════════════════════════════════
#  حساب سعة مسيرة اللورد الحقيقية (Castle March Capacity)
# ════════════════════════════════════════════════════════════════════

def calculate_castle_march_capacity(
    init_data: dict,
    heroes_info: Optional[List[dict]] = None,
    chosen_hero_ids: Optional[List[int]] = None,
    learned_max: Optional[int] = None
) -> int:
    """
    حساب سعة مسيرة اللورد الحقيقية بالقلعة بدقة بالغة عبر المحرك المركزي (tasks/march_capacity.py):
    - سعة ساحة التدريب الأساسية + إضافات وبونص القلعة.
    - سعة الأبطال المختارين وفق جودتهم ومستواهم ومهاراتهم.
    - الالتزام بالسقف المتعلم بالجلسة إن وُجد.
    """
    if not isinstance(init_data, dict):
        return 1000

    cap = get_castle_march_capacity(init_data, chosen_heroes=chosen_hero_ids)
    if learned_max and learned_max > 0:
        cap = min(cap, learned_max)
    return max(300, cap)


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الحرب والقتال (Combat Heroes Selection)
# ════════════════════════════════════════════════════════════════════

def _pick_combat_heroes(heroes: list, max_count: int = 2, busy: Set[int] = None, target_level: int = 1) -> List[int]:
    """
    يختار أفضل أبطال قتال وحرب (5501xxx) وفق هرمية المهارات القتالية والمستوى:
    1. أبطال حرب 5501xxx يمتلكون مهارات هجومية/قتالية (5610xxx / 5640xxx).
    2. أبطال حرب 5501xxx متاحين.
    ملاحظة: يتم استبعاد أبطال الجمع (5502xxx) والدعم (5503xxx) تماماً في المعارك.
    """
    busy = busy or set()
    tier1, tier2, tier3 = [], [], []

    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or hid in busy:
            continue
        if hero.get('status', {}).get('state', 0) != 0:
            continue

        hid_str = str(hid)
        # استبعاد أبطال الجمع (5502xxx) والدعم (5503xxx) نهائياً من أي معركة
        if hid_str.startswith('5502') or hid_str.startswith('5503'):
            continue

        skills = hero.get('skillList', {})
        has_combat_skills = False
        if isinstance(skills, dict):
            has_combat_skills = any(
                str(s.get('id', '')).startswith('5610') or str(s.get('id', '')).startswith('5640')
                for s in skills.values() if isinstance(s, dict)
            )

        lv = int(hero.get('lv', 1))
        star = int(hero.get('star', 1))
        score = lv * 10 + star * 50

        if hid_str.startswith('5501'):
            if has_combat_skills:
                tier1.append((int(hid), score))
            else:
                tier2.append((int(hid), score))
        else:
            tier3.append((int(hid), score))

    tier1.sort(key=lambda x: x[1], reverse=True)
    tier2.sort(key=lambda x: x[1], reverse=True)
    tier3.sort(key=lambda x: x[1], reverse=True)

    chosen = [h[0] for h in tier1] + [h[0] for h in tier2]
    # للمستويات العالية (28+) نقتصر تماماً على أبطال الحرب 5501xxx
    if target_level < 28:
        chosen += [h[0] for h in tier3]

    # خطة احتياطية للمستويات المنخفضة فقط: أي بطل متاح في حال عدم وجود أبطال حرب
    if not chosen and target_level <= 15:
        for hero in heroes:
            if isinstance(hero, dict):
                hid = hero.get('id')
                if hid and hid not in busy and hero.get('status', {}).get('state', 0) == 0:
                    hid_str = str(hid)
                    if not (hid_str.startswith('5502') or hid_str.startswith('5503')):
                        chosen.append(int(hid))
                        if len(chosen) >= (max_count or 2):
                            break

    return chosen[:max_count] if max_count else chosen


# ════════════════════════════════════════════════════════════════════
#  حساب القوة الموصى بها وسعة الجيش الذكية (Recommended Power & Smart Troops)
# ════════════════════════════════════════════════════════════════════

def get_monster_recommended_power(target_type: str, level: int) -> int:
    """
    حساب / إرجاع القوة الموصى بها (Recommended Power) المعروضة في واجهة اللعبة للهدف:
    - نخبة المتمردين (Rebels): من لفل 1 إلى 5 (لفل 5 = 7,518,000 بالضبط كما باللعبة).
    - الغزاة (Invaders): من لفل 1 إلى 35 (باستخدام جدول القوة الرسمي الدقيق).
    - المعاقل (Stronghold): من لفل 1 إلى 30.
    """
    m_type = str(target_type).lower().strip()
    lv = max(1, int(level))
    if m_type in ("rebels", "متمردين", "35"):
        if lv in OFFICIAL_REBEL_FC:
            return OFFICIAL_REBEL_FC[lv]
        return int(7518000 * (1 + (lv - 5) * 0.25))
    elif m_type in ("invaders", "غزاة", "6"):
        return OFFICIAL_NPC_FC.get(lv, 2040892)
    elif m_type in ("stronghold", "معقل", "ملاجئ", "26"):
        if lv <= 10:
            return 500000 + lv * 150000
        elif lv <= 20:
            return 2000000 + (lv - 10) * 250000
        else:
            return 4500000 + (lv - 20) * 350000
    return 0


def calculate_smart_combat_troops(
    target_type: str,
    target_level: int,
    castle_power: int = 0,
    user_troops_cfg: Optional[int] = None,
    max_safe_march: int = 170000
) -> Tuple[int, int, str]:
    """
    دالة ذكية ومرنة لحساب عدد جنود المسيرة الأمثل وفحص القوة الموصى بها:
    1. تستعلم القوة الموصى بها للهدف من الجداول الرسمية.
    2. تفحص قوة القلعة الحالية ومستوى الأمان ونسبة الجاهزية.
    3. تحسب عدد الجنود المطلوب بدقة لضمان النصر الحاسم بصفر خسائر ودون تجاوز سعة مسيرة اللورد.
    """
    m_type = str(target_type).lower().strip()
    lv = max(1, int(target_level))
    rec_power = get_monster_recommended_power(m_type, lv)

    # حساب نسبة الجاهزية والأمان
    status_desc = "جاهزية تامة"
    if castle_power > 0 and rec_power > 0:
        ratio = castle_power / float(rec_power)
        pct = int(ratio * 100)
        if ratio >= 1.25:
            status_desc = f"جاهزية ساحقة وتفوق كامل ({pct}%)"
        elif ratio >= 1.0:
            status_desc = f"مؤهل بنجاح ({pct}%)"
        elif ratio >= 0.75:
            status_desc = f"متكافئ مع الهدف ({pct}%)"
        else:
            status_desc = f"قوة القلعة أقل من الموصى بها ({pct}%)"

    # إذا حدد المستخدم رقماً مخصصاً صريحاً في الإعدادات (وليس قيماً افتراضية قديمة كـ 30 أو 50 ألف)
    if user_troops_cfg and user_troops_cfg not in (0, 30000, 50000):
        troops = min(max_safe_march, max(100, user_troops_cfg))
        return troops, rec_power, status_desc

    # الحساب الديناميكي المرن لعدد الجنود حسب نوع الهدف ومستواه لضمان سحق الهدف دون تجاوز سعة اللورد
    if m_type in ("rebels", "متمردين", "35"):
        base_troops_map = {
            1: 20000,          # لفل 1 (FC = 60k)
            2: 55000,          # لفل 2 (FC = 312k)
            3: 100000,         # لفل 3 (FC = 1.196M)
            4: 140000,         # لفل 4 (FC = 3.02M)
            5: max_safe_march  # لفل 5 (FC = 7.518M - كامل سعة مسيرة اللورد)
        }
        needed = base_troops_map.get(lv, max_safe_march)
    elif m_type in ("invaders", "غزاة", "6"):
        # التدرج الذكي الدقيق للغزاة (1-35)
        if lv == 1:
            needed = 200
        elif lv == 2:
            needed = 500
        elif lv == 3:
            needed = 1000
        elif lv == 4:
            needed = 1800
        elif lv == 5:
            needed = 2500
        elif lv <= 10:
            needed = 4000 + (lv - 5) * 2000
        elif lv <= 20:
            needed = 15000 + (lv - 10) * 4500
        elif lv <= 28:
            needed = 60000 + (lv - 20) * 8000
        else: # 29 إلى 35 (بما فيها لفل 34)
            needed = max_safe_march
    elif m_type in ("stronghold", "معقل", "ملاجئ", "26"):
        if lv <= 10:
            needed = 60000
        elif lv <= 20:
            needed = 110000
        else:
            needed = min(max_safe_march, 165000)
    else:
        needed = 80000

    optimal_troops = min(max_safe_march, max(100, int(needed)))
    return optimal_troops, rec_power, status_desc


# ════════════════════════════════════════════════════════════════════
#  الدالة الخارقة: اختيار الجيش القتالي الذكي المتكامل (Smart Combat Army)
# ════════════════════════════════════════════════════════════════════

def select_smart_combat_army(
    available: Dict[int, int],
    target_type: str = "invaders",
    target_level: int = 1,
    max_capacity: int = 170000,
    user_troops_cfg: Optional[int] = None,
    heroes_info: Optional[List[dict]] = None,
    chosen_heroes: Optional[List[int]] = None
) -> Tuple[List[Dict[str, int]], int, float, str]:
    """
    الدالة الخارقة لاختيار الجيش القتالي:
    1. حساب قوة الهدف الرسمية (FC) وفق مستواه ونوعه.
    2. تحديد عدد القوات الأمثل (من 200 جندي للمستويات 1-5، وصولاً إلى كامل سعة المسيرة 160k+ للمستويات 30-35).
    3. تشكيل جيش تكتيكي متوازن من الرتب الأعلى المتوفرة (35% مشاة كدرع، 35% فرسان كهجوم، 30% رماة كرمي).
    4. استبعاد فخاخ الجدار (800-899) وعربات الحصار إلا كاحتياط أخير.
    5. فحص الأمان الاستراتيجي (Anti-Suicide Check) لمنع هلاك القوات أمام أهداف خارقة تفوق طاقة القلعة.
    """
    m_type = str(target_type).lower().strip()
    lv = max(1, int(target_level))
    target_fc = get_monster_recommended_power(m_type, lv)

    # 1. تحديد العدد المطلوب من الجنود
    if user_troops_cfg and user_troops_cfg not in (0, 30000, 50000):
        needed_troops = min(max_capacity, max(100, int(user_troops_cfg)))
    else:
        needed_troops, _, _ = calculate_smart_combat_troops(
            target_type=m_type,
            target_level=lv,
            user_troops_cfg=user_troops_cfg,
            max_safe_march=max_capacity
        )

    needed_troops = max(50, min(needed_troops, max_capacity))

    # 2. تصنيف القوات المتاحة بالقلعة
    infantry = []   # 401..414
    cavalry  = []   # 501..514
    archers  = []   # 601..614
    carts    = []   # 701..714 كاحتياط

    for tid, count in available.items():
        if count <= 0:
            continue
        # استبعاد فخاخ وأسلحة الجدار (800..899) لمنع خطأ 8062
        if 800 <= tid < 900:
            continue
        if 400 <= tid < 500:
            infantry.append((tid, count))
        elif 500 <= tid < 600:
            cavalry.append((tid, count))
        elif 600 <= tid < 700:
            archers.append((tid, count))
        elif 700 <= tid < 800:
            carts.append((tid, count))

    # ترتيب كل صنف من الرتبة الأعلى أولاً (T12 -> T11 -> ... -> T1)
    infantry.sort(key=lambda x: x[0], reverse=True)
    cavalry.sort(key=lambda x: x[0], reverse=True)
    archers.sort(key=lambda x: x[0], reverse=True)
    carts.sort(key=lambda x: x[0], reverse=True)

    army_map: Dict[int, int] = {}
    remaining_needed = needed_troops

    # 3. توزيع الحصص التكتيكية: 35% مشاة، 35% فرسان، 30% رماة
    combat_branches = [b for b in [infantry, cavalry, archers] if b]
    if combat_branches:
        target_inf = int(needed_troops * 0.35)
        target_cav = int(needed_troops * 0.35)
        target_arc = needed_troops - (target_inf + target_cav)

        quotas = [
            (infantry, target_inf),
            (cavalry, target_cav),
            (archers, target_arc),
        ]

        # جولة 1: أخذ الحصة من كل صنف قتالي متوفر
        for branch_list, quota in quotas:
            branch_taken = 0
            for tid, count in branch_list:
                avail = available.get(tid, 0)
                if avail <= 0:
                    continue
                take = min(avail, quota - branch_taken, remaining_needed)
                if take > 0:
                    army_map[tid] = army_map.get(tid, 0) + take
                    available[tid] -= take
                    branch_taken += take
                    remaining_needed -= take
                    if branch_taken >= quota or remaining_needed <= 0:
                        break

        # جولة 2: إكمال المتبقي من أي قوات قتالية متاحة (من الأعلى رتبة للأدنى)
        if remaining_needed > 0:
            for branch_list in [infantry, cavalry, archers]:
                for tid, count in branch_list:
                    avail = available.get(tid, 0)
                    if avail <= 0:
                        continue
                    take = min(avail, remaining_needed)
                    if take > 0:
                        army_map[tid] = army_map.get(tid, 0) + take
                        available[tid] -= take
                        remaining_needed -= take
                        if remaining_needed <= 0:
                            break
                if remaining_needed <= 0:
                    break

    # جولة 3: استكمال النقص من عربات الحصار إن لزم كاحتياط
    if remaining_needed > 0 and carts:
        for tid, count in carts:
            avail = available.get(tid, 0)
            if avail <= 0:
                continue
            take = min(avail, remaining_needed)
            if take > 0:
                army_map[tid] = army_map.get(tid, 0) + take
                available[tid] -= take
                remaining_needed -= take
                if remaining_needed <= 0:
                    break

    army_list = [{"id": tid, "num": num} for tid, num in army_map.items() if num > 0]
    total_troops = sum(item['num'] for item in army_list)

    # 4. حساب القوة التقديرية وفحص الأمان الاستراتيجي (Anti-Suicide Check)
    army_power = sum(item['num'] * get_unit_power(item['id']) for item in army_list)
    hero_power_bonus = 0.0
    if chosen_heroes and heroes_info:
        for hid in chosen_heroes:
            h_data = next((h for h in heroes_info if isinstance(h, dict) and h.get('id') == hid), None)
            if h_data:
                hlv = int(h_data.get('lv', 1))
                hstar = int(h_data.get('star', 1))
                hero_power_bonus += (hlv * 500 + hstar * 2500)

    total_estimated_power = army_power + hero_power_bonus

    safety_status = "SAFE"
    if lv >= 28 and target_fc > 0:
        if total_estimated_power < (target_fc * 0.45):
            safety_status = "SUICIDE_RISK"
        elif total_estimated_power < (target_fc * 1.2):
            safety_status = "RISKY"
        else:
            safety_status = "GUARANTEED_WIN"
    elif target_fc > 0:
        if total_estimated_power >= (target_fc * 3.0):
            safety_status = "GUARANTEED_WIN"
        elif total_estimated_power >= (target_fc * 1.5):
            safety_status = "SAFE"
        elif total_estimated_power >= (target_fc * 0.7):
            safety_status = "RISKY"
        else:
            safety_status = "UNDERPOWERED"

    return army_list, total_troops, total_estimated_power, safety_status


# ════════════════════════════════════════════════════════════════════
#  اختيار جيش القتال التلقائي المتوازن (Balanced Combat Army Selection)
# ════════════════════════════════════════════════════════════════════

def select_combat_army(available: Dict[int, int], needed_count: int = DEFAULT_TROOPS_COUNT) -> List[Dict[str, int]]:
    """
    اختيار تشكيلة جيش قتالية متوازنة بالعدد المناسب:
    توزيع متوازن بين المشاة، الفرسان، والرماة بحسب المتاح في القلعة من الرتب الأعلى.
    1. المشاة (401..414)
    2. الفرسان (501..514)
    3. الرماة (601..614)
    4. القوات الخاصة (800+)
    5. عربات الحصار (701..714) كاحتياط
    """
    infantry = []   # 401..414
    cavalry  = []   # 501..514
    archers  = []   # 601..614
    carts    = []   # 701..714 كاحتياط

    for tid, count in available.items():
        if count <= 0:
            continue
        # يُمنع بتاتاً تضمين أسلحة الدفاع وفخاخ الجدار (800 فما فوق) لأنها تسبب خطأ 8062
        if 800 <= tid < 900:
            continue
        if 400 <= tid < 500:
            infantry.append((tid, count))
        elif 500 <= tid < 600:
            cavalry.append((tid, count))
        elif 600 <= tid < 700:
            archers.append((tid, count))
        elif 700 <= tid < 800:
            carts.append((tid, count))

    # ترتيب كل صنف من الرتبة الأعلى إلى الأدنى
    infantry.sort(key=lambda x: x[0], reverse=True)
    cavalry.sort(key=lambda x: x[0], reverse=True)
    archers.sort(key=lambda x: x[0], reverse=True)
    carts.sort(key=lambda x: x[0], reverse=True)

    combat_branches = [b for b in [infantry, cavalry, archers] if b]
    if not combat_branches:
        combat_branches = [carts] if carts else []

    if not combat_branches:
        return []

    army_map: Dict[int, int] = {}
    remaining_needed = needed_count

    # جولة 1: توزيع متوازن متساوٍ بين الأصناف القتالية المتوفرة
    branch_quota = max(1, remaining_needed // len(combat_branches))
    for branch in combat_branches:
        quota = min(branch_quota, remaining_needed)
        branch_taken = 0
        for tid, count in branch:
            avail = available.get(tid, 0)
            if avail <= 0:
                continue
            take = min(avail, quota - branch_taken)
            if take > 0:
                army_map[tid] = army_map.get(tid, 0) + take
                available[tid] -= take
                branch_taken += take
                remaining_needed -= take
                if branch_taken >= quota or remaining_needed <= 0:
                    break
        if remaining_needed <= 0:
            break

    # جولة 2: استكمال العدد المتبقي من أي قوات قتالية متاحة (بالترتيب من الأعلى للأدنى)
    if remaining_needed > 0:
        all_branches = combat_branches + ([carts] if carts and carts not in combat_branches else [])
        for branch in all_branches:
            for tid, count in branch:
                avail = available.get(tid, 0)
                if avail <= 0:
                    continue
                take = min(avail, remaining_needed)
                if take > 0:
                    army_map[tid] = army_map.get(tid, 0) + take
                    available[tid] -= take
                    remaining_needed -= take
                    if remaining_needed <= 0:
                        break
            if remaining_needed <= 0:
                break

    return [{"id": tid, "num": num} for tid, num in army_map.items() if num > 0]


# ════════════════════════════════════════════════════════════════════
#  اختيار الحيوان الأليف للقتال (Combat Pet Selection)
# ════════════════════════════════════════════════════════════════════

def select_combat_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]:
    """
    اختيار أعلى حيوان قتالي متاح في القلعة.
    """
    pets_data = conn.init_data.get('petCtrl', {}).get('pets', {})
    if not pets_data:
        return []

    available_pets = []
    for pid_str, pinfo in pets_data.items():
        try:
            pid = int(pid_str)
            if pid not in used_pets:
                lv = int(pinfo.get('lv', 1))
                available_pets.append((pid, lv))
        except Exception:
            continue

    if not available_pets:
        return []

    available_pets.sort(key=lambda x: x[1], reverse=True)
    chosen_pet = available_pets[0][0]
    used_pets.add(chosen_pet)
    return [chosen_pet]


# ════════════════════════════════════════════════════════════════════
#  مهمة الهجوم على الوحوش والمتمردين (MonsterTask)
# ════════════════════════════════════════════════════════════════════

class MonsterTask(BaseTask):
    """
    مهمة الهجوم على الغزاة أو المتمردين بالتشكيلة أو أبطال الحرب.
    """
    name = "monster"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self._heroes    : list     = []
        self._busy      : Set[int] = set()
        self._used_army : Dict[int, int] = {}
        self._used_pets : Set[int] = set()
        self._learned_max_march_troops: Optional[int] = None
        self._learned_max_npc_level: Optional[int] = None
        self._exclude_mgr = _get_exclude_manager()

    async def on_start(self):
        for _ in range(20):
            if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
                break
            if self.conn.init_data:
                break
            await asyncio.sleep(0.5)
        await self._load_heroes()

    async def _load_heroes(self):
        """جلب بيانات أبطال الحساب من الذاكرة الحية."""
        hctrl = self.conn.init_data.get('heroCtrl') if hasattr(self.conn, 'init_data') else None
        if isinstance(hctrl, list) and hctrl:
            self._heroes = list(hctrl)
            return

        # احتياطي نادر إذا كانت الذاكرة غير محملة
        self._heroes = []
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        for h_list in army_ctrl.get('compileHeros', {}).values():
            if isinstance(h_list, list):
                for hid in h_list:
                    if str(hid).isdigit() and int(hid) > 0:
                        int_hid = int(hid)
                        if not any(h.get('id') == int_hid for h in self._heroes):
                            self._heroes.append({'id': int_hid, 'status': {'state': 0}, 'skillList': {}})

    # ── فحص شروط نخبة المتمردين (Alliance & Hall of War) ─────────

    def _check_rebel_prerequisites(self) -> Tuple[bool, str]:
        """
        فحص شروط الانضمام لحشود نخبة المتمردين (Elite Rebels Prerequisite Checks):
        1. التحالف (Alliance): يجب أن تكون القلعة في تحالف رسمي لفتح مسيرة الحشد (moveLineType 7).
        2. مبنى قاعة الحرب (Hall of War - bid 115): يجب أن يكون مبنياً بالقلعة (lv >= 1).
        """
        # 1. فحص التحالف
        alliance_ctrl = self.conn.init_data.get('allianceCtrl', {})
        alliance_id = 0
        if isinstance(alliance_ctrl, dict) and alliance_ctrl:
            minfo = alliance_ctrl.get('memberinfo', {}).get('minfo', {})
            if isinstance(minfo, dict):
                alliance_id = int(minfo.get('aid', 0))
            if alliance_id == 0:
                alliance_id = int(alliance_ctrl.get('allianceInfo', {}).get('aid', 0))
            if alliance_id == 0 and len(alliance_ctrl) > 5:
                alliance_id = 1
        if alliance_id == 0:
            lord_data = self.conn.init_data.get('lord', {})
            alliance_id = int(lord_data.get('alliance', 0)) if isinstance(lord_data, dict) else 0

        if alliance_id == 0:
            return False, "مهاجمة نخبة المتمردين تتطلب الانضمام إلى تحالف لفتح مسيرة الحشد (Rally). القلعة ليست في تحالف حالياً."

        # 2. فحص قاعة الحرب (bid 115)
        blist = self.conn.init_data.get('cityCtrl', {}).get('blist', [])
        if not isinstance(blist, list):
            blist = []
        hall_of_war_lv = 0
        for b in blist:
            if isinstance(b, dict):
                b_info = b.get('binfo', b)
                if isinstance(b_info, dict):
                    bid = str(b_info.get('bid', ''))
                    if bid == '115':
                        hall_of_war_lv = max(hall_of_war_lv, int(b_info.get('lv', 1)))

        if hall_of_war_lv == 0:
            return False, "مهاجمة نخبة المتمردين تتطلب بناء 'قاعة الحرب' (مبنى 115) لتفعيل الحشود. المبنى غير مشيد في القلعة."

        return True, ""

    # ── فحص وتحديد المستوى الآمن وفق منطق اللعبة الرسمي ─────────────

    async def determine_safe_monster_level(
        self,
        target_type: str,
        req_min_lv: int,
        req_max_lv: int
    ) -> Tuple[int, int, str]:
        """
        حماية القلعة بالاعتماد الصارم والشامل على منطق اللعبة الرسمي:
        1. فحص سقف خريطة المملكة وسقف قتل اللاعب الشخصي (kingdomMapCtrl / lordInfoCtrl).
        2. فحص استجابة السيرفر الرسمية للغزاة والمتمردين (cmd: 2011, subcmd: 7).
        3. حساب السعة القصوى الحقيقية لمسيرة اللورد وقوة الجيش المتاح بالقلعة.
        4. مقارنة قوة المسيرة بقوة الهدف الرسمية بنسبة أمان >= 0.70 لمنع الانتحار والهزيمة.
        5. إرجاع (safe_min_lv, safe_max_lv, reason).
        """
        target_type_clean = str(target_type).lower().strip()
        is_rebel = target_type_clean in ("rebels", "متمردين", "35")

        # 1. استخراج سقف قتل اللاعب وسقف الخريطة من بيانات اللعبة الرسمية (init_data)
        kmap = self.conn.init_data.get('kingdomMapCtrl', {})
        max_map_npc_lv = 5 if is_rebel else 35
        if isinstance(kmap, dict) and not is_rebel:
            try: max_map_npc_lv = int(kmap.get('maxMapNpcLevel', 35))
            except: pass

        player_killed_max = 0
        if isinstance(kmap, dict) and 'maxNpcLevel' in kmap:
            try: player_killed_max = max(player_killed_max, int(kmap['maxNpcLevel']))
            except: pass

        lord_npc = self.conn.init_data.get('lordInfoCtrl', {}).get('npc', {})
        if isinstance(lord_npc, dict) and 'killMaxLevel' in lord_npc:
            try: player_killed_max = max(player_killed_max, int(lord_npc['killMaxLevel']))
            except: pass

        # وفق كود اللعبة الرسمي kingdomMapCell:getMaxCanKillLevel(): ret = self.maxNpcLevel + 1
        player_can_kill_lv = player_killed_max + 1 if player_killed_max > 0 else 1

        # 3. سقف التعلم أثناء الجلسة (عند حدوث أي خطأ 8027 سابقاً)
        if self._learned_max_npc_level is not None and not is_rebel:
            player_can_kill_lv = min(player_can_kill_lv, self._learned_max_npc_level)

        # 4. حساب السعة الحقيقية لمسيرة اللورد وقوة الجيش المتاح بالقلعة
        castle_capacity = calculate_castle_march_capacity(
            init_data=self.conn.init_data,
            heroes_info=self._heroes,
            learned_max=self._learned_max_march_troops
        )

        # قراءة الجيش المتاح بالقلعة مباشرة من الذاكرة الحية (Zero Request)
        available_troops: Dict[int, int] = {}
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        if isinstance(army_ctrl, dict):
            for k, v in army_ctrl.get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available_troops[int(k)] = int(v)

        # خطة طوارئ احتياطية فقط إذا كانت الذاكرة غير محملة إطلاقاً
        if not available_troops:
            try:
                self.conn.debug_log("🛑🛑🛑🛑🛑🛑🛑")
                r_army = await self.conn.query('1005', '1', {}, timeout=3)
                if r_army and 'data' in r_army:
                    for k, v in r_army['data'].get('totalArmy', {}).items():
                        if str(k).isdigit() and str(v).isdigit():
                            available_troops[int(k)] = int(v)
            except Exception:
                pass


        # فرز أفضل القوات القتالية المتاحة لحساب قوة المسيرة القصوى
        sorted_units = sorted(
            [(tid, cnt) for tid, cnt in available_troops.items() if not (800 <= tid < 900) and cnt > 0],
            key=lambda x: get_unit_power(x[0]),
            reverse=True
        )
        rem_cap = castle_capacity
        total_march_troops_power = 0.0
        for tid, cnt in sorted_units:
            take = min(cnt, rem_cap)
            if take > 0:
                total_march_troops_power += take * get_unit_power(tid)
                rem_cap -= take
                if rem_cap <= 0:
                    break

        hero_power = 0.0
        if self._heroes:
            combat_heroes = [h for h in self._heroes if isinstance(h, dict) and str(h.get('id', '')).startswith('5501')]
            for h in combat_heroes[:2]:
                hlv = int(h.get('lv', 1))
                hstar = int(h.get('star', 1))
                hero_power += (hlv * 500 + hstar * 2500)
            if not combat_heroes:
                hero_power = 1500.0
        else:
            hero_power = 1500.0

        max_march_power = total_march_troops_power + hero_power

        # 5. حساب أعلى مستوى آمن قتالياً وفق معادلة القوة الرسمية (worldDispatchArmyView.lua)
        if is_rebel:
            combat_safe_lv = 1
            for lv in sorted(OFFICIAL_REBEL_FC.keys()):
                fc = OFFICIAL_REBEL_FC[lv]
                if lv == 1 and max_march_power >= (fc * 0.40):
                    combat_safe_lv = lv
                elif max_march_power >= (fc * 0.70):
                    combat_safe_lv = lv
                else:
                    break

            safe_ceiling = min(req_max_lv, 5, combat_safe_lv)
            safe_ceiling = max(1, min(safe_ceiling, 5))
            safe_floor = min(req_min_lv, safe_ceiling)

            reasons = []
            if safe_ceiling < req_max_lv:
                if safe_ceiling == combat_safe_lv:
                    reasons.append(f"معادلة قوة المعركة الرسمية لنخبة المتمردين (أقصى قوة لمسيرة القلعة {max_march_power:,.0f} تكفي بأمان حتى لفل {combat_safe_lv} بقوة FC={OFFICIAL_REBEL_FC.get(combat_safe_lv, 0):,} لمنع خسارة القوات والانتحار)")
                elif req_max_lv > 5:
                    reasons.append("الحد الأقصى لمستويات نخبة المتمردين باللعبة هو لفل 5 فقط")

            reason_str = " | ".join(reasons) if reasons else "المستوى المختار متوافق تماماً مع طاقة القلعة وشروط اللعبة"
            return safe_floor, safe_ceiling, reason_str
        else:
            # الغزاة (Invaders)
            combat_safe_lv = 1
            for lv in sorted(OFFICIAL_NPC_FC.keys()):
                fc = OFFICIAL_NPC_FC[lv]
                if lv <= 3 and max_march_power >= (fc * 0.4):
                    combat_safe_lv = lv
                elif max_march_power >= (fc * 0.70):
                    combat_safe_lv = lv
                else:
                    break

            safe_ceiling = min(req_max_lv, max_map_npc_lv, player_can_kill_lv, combat_safe_lv)
            safe_ceiling = max(1, min(safe_ceiling, 35))
            safe_floor = min(req_min_lv, safe_ceiling)

            reasons = []
            if safe_ceiling < req_max_lv:
                if safe_ceiling == player_can_kill_lv and player_can_kill_lv < combat_safe_lv:
                    reasons.append(f"نظام القتل الأول باللعبة (المستويات أعلى من {safe_ceiling} مغلقة وتتطلب قتل المستويات السابقة أولاً لتفادي كود 8027)")
                elif safe_ceiling == combat_safe_lv:
                    reasons.append(f"معادلة قوة المعركة الرسمية (أقصى قوة لمسيرة القلعة {max_march_power:,.0f} تكفي بأمان حتى لفل {combat_safe_lv} بقوة FC={OFFICIAL_NPC_FC.get(combat_safe_lv, 0):,} لمنع خسارة القوات والانتحار)")
                elif safe_ceiling == max_map_npc_lv:
                    reasons.append(f"الحد الأقصى لخريطة المملكة حالياً (لفل {max_map_npc_lv})")

            reason_str = " | ".join(reasons) if reasons else "المستوى المختار متوافق تماماً مع طاقة القلعة وشروط اللعبة"
            return safe_floor, safe_ceiling, reason_str

    # ── المهمة الرئيسية ───────────────────────────────────────────

    async def run(self) -> TaskResult:
        cfg = self.config
        target_type_str = str(cfg.get('monster_type', DEFAULT_MONSTER_TYPE)).lower().strip()
        min_lv          = int(cfg.get('min_lv', DEFAULT_MIN_LV))
        max_lv          = int(cfg.get('max_lv', DEFAULT_MAX_LV))
        max_marches     = int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))
        search_range    = int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))
        formation_id    = int(cfg.get('formation_id', DEFAULT_FORMATION_ID))
        troops_cfg      = int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))

        target_info = MONSTER_TYPES.get(target_type_str, MONSTER_TYPES["rebels"])
        map_type = target_info["mapType"]
        sub_type = target_info["subType"]
        type_name = target_info["name"]

        self.log.info(f"⚔️ بدء مهمة الهجوم على [{type_name}] | لفل: {min_lv}-{max_lv} | الحد الأقصى للمسيرات: {max_marches}")

        # ── فحص شروط الحشود لنخبة المتمردين (تحالف + قاعة الحرب) ──
        if map_type == 35:
            can_rally, rally_err = self._check_rebel_prerequisites()
            if not can_rally:
                self.log.warning(f"🛑 [شروط نخبة المتمردين] {rally_err}")
                return TaskResult.fail(f"🛑 {rally_err}", stop_reason="REBEL_PREREQUISITE_FAILED")

        if not self._heroes:
            await self._load_heroes()

        # ── فحص حماية القلعة ومنطق اللعبة (Game-Logic Protection) ──
        safe_min, safe_max, reason_str = await self.determine_safe_monster_level(target_type_str, min_lv, max_lv)
        if max_lv > safe_max or min_lv > safe_min:
            self.log.warning(f"🛡️ [حماية القلعة] ضبط المستوى إلى ({safe_min}-{safe_max}) | {reason_str}")
            min_lv = safe_min
            max_lv = safe_max

        sent_count = 0
        consecutive_errors = 0
        self._busy      = set(cfg.get('busy_heroes', cfg.get('busy', [])))
        self._used_army = {}
        self._used_pets = set()

        wait_for_queue = bool(cfg.get('wait_for_queue', cfg.get('wait_queue', False)))
        wait_interval  = float(cfg.get('wait_interval', 15.0))
        max_wait_cycles = int(cfg.get('max_wait_cycles', 35))
        wait_cycles = 0
        cmd_opting_retries = 0
        last_result = None

        while sent_count < max_marches:
            current_target_idx = sent_count + 1
            
            # ── 🧪 اختبار: قراءة الفيالق المتاحة قبل الإرسال ──
            before_avail = await self.get_available_marches_count(force_sync=True)
            self.log.info(f"🔬 [MARCH_TEST] قبل الإرسال #{sent_count + 1}: الفيالق المتاحة = {before_avail}")
            if before_avail == 0:
                self.log.info("🏁 اكتملت جميع الفيالق وطوابير المسيرات للقلعة (طوابير ممتلئة بالكامل).")
                last_result = "QUEUE_FULL"
                break

            self.log.debug(f"🚀 محاولة إرسال مسيرة الهجوم رقم ({current_target_idx}/{max_marches})...")
            result_code = await self._send_one_attack(map_type, sub_type, min_lv, max_lv, search_range, formation_id, troops_cfg)
            last_result = result_code

            if result_code == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                cmd_opting_retries = 0
                wait_cycles = 0
                if sent_count < max_marches:
                    spacing = round(random.uniform(3.5, 5.5), 2)
                    self.log.debug(f"🛡️ انتظار {spacing} ثانية قبل المسيرة التالية...")
                    await asyncio.sleep(spacing)
            elif result_code == "QUEUE_FULL":
                if not wait_for_queue or wait_cycles >= max_wait_cycles:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل.")
                    break

                cur_act = await self.get_active_marches_count()
                max_q = max(getattr(self, '_max_castle_queues', 0), max(1, cur_act))
                self._max_castle_queues = max_q

                queue_freed = False
                while wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(
                        f"⏳ [طوابير ممتلئة ({cur_act}/{max_q}) - دورة {wait_cycles}/{max_wait_cycles}] "
                        f"جميع الفيالق مشغولة بالخارج — الانتظار {wait_interval:.0f} ثانية لتفريغ فيلق للغزاة..."
                    )
                    await asyncio.sleep(wait_interval)

                    cur_act = await self.get_active_marches_count()
                    self.log.info(f"🔍 [فحص الفيالق] الفيالق النشطة بالخارج حالياً: {cur_act}/{max_q}")
                    if cur_act < max_q:
                        self.log.info(
                            f"✅ [توفر فيلق شاغر] عاد أحد الفيالق إلى القلعة بنجاح ({cur_act}/{max_q}) "
                            f"— استئناف هجوم الغزاة الآن!"
                        )
                        queue_freed = True
                        break
                    else:
                        self.log.info(
                            f"⏳ [الفيالق لا تزال ممتلئة ({cur_act}/{max_q})] "
                            f"لم يعد أي فيلق بعد — مواصلة الانتظار {wait_interval:.0f} ثانية أخرى دون إرسال محاولات فاشلة..."
                        )

                if queue_freed:
                    self._busy.clear()
                    self._used_army.clear()
                    await self._load_heroes()
                    continue
                else:
                    self.log.info("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل بعد استنفاد دورات الانتظار.")
                    break
            elif result_code == "STAMINA_EMPTY":
                self.log.warning("🛑 نفدت طاقة اللورد بالكامل — إنهاء المهمة.")
                break
            elif result_code in ("HERO_BUSY", "NO_HEROES"):
                # إذا كان البطل مشغولاً وتوجد أبطال قتال بديلة متاحة: تجربة البطل التالي فوراً
                avail_combat_heroes = [h for h in self._heroes if isinstance(h, dict) and h.get('id') not in self._busy and str(h.get('id', '')).startswith('5501')]
                if result_code == "HERO_BUSY" and avail_combat_heroes:
                    self.log.info(f"🔄 البطل السابق في مسيرة — تجربة بطل قتالي بديل فوراً ({len(avail_combat_heroes)} متاح بالقلعة)...")
                    continue
                if wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(f"⏳ [أبطال مشغولون ({wait_cycles}/{max_wait_cycles})] بانتظار عودة الأبطال من المسيرات (انتظار {wait_interval:.0f} ثانية)...")
                    await asyncio.sleep(wait_interval)
                    self._busy.clear()
                    self._used_army.clear()
                    await self._load_heroes()
                    continue
                else:
                    self.log.warning("⚠️ لا يتوفر أبطال متاحون حالياً بالقلعة.")
                    break
            elif result_code == "NO_ARMY":
                if wait_for_queue and wait_cycles < max_wait_cycles:
                    wait_cycles += 1
                    self.log.info(f"⏳ [القوات في مسيرات ({wait_cycles}/{max_wait_cycles})] بانتظار عودة الجيش إلى القلعة (انتظار {wait_interval:.0f} ثانية)...")
                    await asyncio.sleep(wait_interval)
                    self._busy.clear()
                    self._used_army.clear()
                    continue
                else:
                    self.log.warning("⚠️ نفدت القوات المتاحة بالقلعة.")
                    break
            elif result_code == "SUICIDE_RISK":
                self.log.warning("🛑 توقف الهجوم: الجيش المتاح أضعف بكثير من الهدف ويشكل خطراً على القوات (انتحار) — إنهاء المهمة بأمان لحماية الجيش.")
                break
            elif result_code == "NPC_LEVEL_LOCKED":
                if hasattr(self, '_learned_max_npc_level') and self._learned_max_npc_level:
                    max_lv = min(max_lv, self._learned_max_npc_level)
                    if min_lv > max_lv:
                        min_lv = max_lv
                    self.log.info(f"🔄 [تعديل تلقائي لمنطق اللعبة] تم تحديث مستوى البحث إلى ({min_lv}-{max_lv}) واستئناف الهجوم فوراً...")
                    continue
                else:
                    max_lv = max(1, max_lv - 1)
                    if min_lv > max_lv:
                        min_lv = max_lv
                    continue
            elif result_code in ("CMD_OPTING", "16001", "CMD_OPTING_FAILED"):
                cmd_opting_retries += 1
                if cmd_opting_retries <= 2:
                    wait_time = round(random.uniform(10.0, 16.0), 2)
                    self.log.warning(
                        f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_time} ثانية لفك القفل "
                        f"ثم إعادة تجهيز مسيرة الهجوم نظيفاً من البداية (محاولة {cmd_opting_retries}/2)..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    self.log.warning("🏁 استمر انشغال خادم اللعبة (كود 16001) بعد المحاولات — إيقاف الدورة مؤقتاً.")
                    break
            elif result_code in ("NO_TARGET", "TARGET_OCCUPIED"):
                consecutive_errors += 1
                if consecutive_errors >= 4:
                    self.log.warning("⚠️ تعذر العثور على أهداف جديدة في النطاق المحدد — توقف مؤقت")
                    break
                await asyncio.sleep(round(random.uniform(2.2, 4.0), 2))
                continue
            else:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    break
                await asyncio.sleep(round(random.uniform(2.2, 4.0), 2))

        self.log.info(f"🏁 إجمالي مسيرات الهجوم المُرسَلة: {sent_count}/{max_marches}")
        if sent_count > 0:
            return TaskResult.ok(
                f"✅ تم إرسال {sent_count} مسيرة هجوم على {type_name}",
                sent=sent_count,
                queue_full=(last_result == "QUEUE_FULL"),
                stop_reason=last_result
            )
        if last_result == "NPC_LEVEL_LOCKED":
            return TaskResult.fail("🛑 مستوى الهدف مغلق باللعبة ويتطلب القتل الأول للمستويات السابقة (كود 8027)", stop_reason="NPC_LEVEL_LOCKED")
        if last_result == "SUICIDE_RISK":
            return TaskResult.fail("🛑 تم إلغاء الهجوم لحماية القوات من الانتحار (الهدف أعلى بكثير من قوة الجيش المتاح)", stop_reason="SUICIDE_RISK")
        if last_result == "QUEUE_FULL":
            return TaskResult.fail("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل (كود 8004: QUEUE_FULL)", queue_full=True, stop_reason="QUEUE_FULL")
        if last_result == "STAMINA_EMPTY":
            return TaskResult.fail("🛑 نفدت طاقة اللورد بالكامل", stop_reason="STAMINA_EMPTY")
        if last_result == "NO_ARMY":
            return TaskResult.fail("🛑 نفدت القوات المتاحة بالقلعة", stop_reason="NO_ARMY")
        if last_result in ("NO_HEROES", "HERO_BUSY"):
            return TaskResult.fail("🛑 لا يتوفر أبطال متاحون بالقلعة", stop_reason="NO_HEROES")
        if last_result in ("NO_TARGET", "TARGET_OCCUPIED"):
            return TaskResult.fail(f"⚠️ لم يتم العثور على أهداف متاحة لـ {type_name} في النطاق المحدد", stop_reason="NO_TARGET")
        return TaskResult.fail(f"لم يتم إرسال أي مسيرة هجوم على {type_name}", retry_after=120, stop_reason=str(last_result))

    # ── إرسال مسيرة هجوم واحدة ──────────────────────────────────

    async def _send_one_attack(self, map_type: int, sub_type: int, min_lv: int, max_lv: int, search_range: int, formation_id: int, troops_cfg: int) -> str:
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid
        target_type_str = str(self.config.get('monster_type', 'rebels' if map_type == 35 else 'invaders')).lower().strip()
        target_info = MONSTER_TYPES.get(target_type_str, MONSTER_TYPES.get("rebels", {}))
        type_name = target_info.get("name", "متمردين" if map_type == 35 else "غزاة")

        # 1. جلب إحداثيات البحث (من الإعدادات أو من الذاكرة الحية cityCtrl)
        cx, cy = await self.get_castle_coords()
        if not cx or not cy:
            self.log.warning("⚠️ تعذر تحديد إحداثيات القلعة للهجوم على المعقل!")
            return "ERROR"


        # 2. جلب معرف المملكة من الذاكرة الحية
        kingdom_id = await self.get_kingdom_id()


        # 3. البحث عن الأهداف (متمردين 35 أو غزاة 6)
        exclude_map = await self._exclude_mgr.get_exclude_map(self.uid, kingdom_id=kingdom_id)
        r_search = await self.conn.query('2011', '3', {
            "mapType": map_type,
            "num": 5,
            "subType": sub_type,
            "y": cy,
            "x": cx,
            "exclude": exclude_map,
            "minLv": min_lv,
            "maxLv": max_lv,
            "range": search_range
        })

        raw_candidates = r_search.get('result', []) if r_search else []
        candidates = [c for c in raw_candidates if str(c.get('id', '')) not in exclude_map]
        if not candidates:
            self.log.warning(f"⚠️ لا توجد أهداف متاحة من هذا النوع في نطاق {search_range}!")
            return "NO_TARGET"

        # 4. جلب القوات المتوفرة بالقلعة من الذاكرة الحية مباشرة
        available = await self.get_available_troops()

        # 5. جلب بيانات التشكيلة المحفوظة من الذاكرة الحية مباشرة
        form_heroes, form_pets, form_rune_pages, form_army_dict = await self.get_formation(formation_id)


        # 6. فحص أبطال التشكيلة: هل هم متاحون وغير مشغولين؟
        chosen_heroes = []
        target_lv = int(candidates[0].get('level', max_lv)) if candidates else max_lv

        if not self._heroes:
            await self._load_heroes()

        if form_heroes:
            flat_heroes = []
            if isinstance(form_heroes, list):
                flat_heroes = form_heroes
            elif isinstance(form_heroes, dict):
                for sub in form_heroes.values():
                    if isinstance(sub, list): flat_heroes.extend(sub)
                    elif sub: flat_heroes.append(sub)

            available_form_heroes = []
            for h in flat_heroes:
                if h and str(h).isdigit():
                    hid = int(h)
                    if hid not in self._busy:
                        hero_data = next((x for x in self._heroes if x.get('id') == hid), None)
                        if hero_data and hero_data.get('status', {}).get('state', 0) == 0:
                            available_form_heroes.append(hid)

            if len(available_form_heroes) >= 2:
                chosen_heroes = available_form_heroes[:2]
                self.log.debug(f"🎖️ تم اختيار بطلي التشكيلة المحفوظة ({formation_id}): {chosen_heroes}")
            elif len(available_form_heroes) == 1:
                hero1 = available_form_heroes[0]
                self.log.debug(f"ℹ️ أحد أبطال التشكيلة متاح ({hero1}) — إكمال البطل الثاني")
                extra_busy = set(self._busy) | {hero1}
                filler = _pick_combat_heroes(self._heroes, max_count=1, busy=extra_busy, target_level=target_lv)
                if filler:
                    chosen_heroes = [hero1, filler[0]]
                else:
                    chosen_heroes = [hero1]
                self.log.debug(f"⚔️ تشكيلة الأبطال: {chosen_heroes}")

        # إذا كانت أبطال التشكيلة مشغولة أو بدون تشكيلة ثابتة: تطبيق الهرم
        if not chosen_heroes:
            if formation_id > 0:
                self.log.debug("⚠️ أبطال التشكيلة مشغولون — اختيار أفضل أبطال الحرب تلقائياً")
            else:
                self.log.debug("⚔️ اختيار أبطال الحرب والقتال تلقائياً")
            chosen_heroes = _pick_combat_heroes(self._heroes, max_count=2, busy=self._busy, target_level=target_lv)
            if len(chosen_heroes) == 2:
                self.log.debug(f"⚔️ أبطال الحرب المختارون (بطلان اثنان): {chosen_heroes}")
            elif len(chosen_heroes) == 1:
                self.log.debug(f"⚔️ بطل حرب واحد متاح بالقلعة: {chosen_heroes}")
            else:
                any_cands = [int(h['id']) for h in self._heroes if isinstance(h, dict) and h.get('id') and int(h['id']) not in self._busy and h.get('status', {}).get('state', 0) == 0]
                if any_cands:
                    chosen_heroes = any_cands[:2]
                    self.log.debug(f"⚠️ بديل اضطراري: تم اختيار أي أبطال متاحين ({len(chosen_heroes)}): {chosen_heroes}")
                else:
                    self.log.warning("⚠️ لا يوجد أي بطل متاح بالقلعة نهائياً!")
                    return "NO_HEROES"

        # 7. تكوين جيش المسيرة الذكي (مع حساب سعة مسيرة اللورد الحقيقية بالقلعة لمنع خطأ 8035)
        castle_capacity = calculate_castle_march_capacity(
            init_data=self.conn.init_data,
            heroes_info=self._heroes,
            chosen_hero_ids=chosen_heroes,
            learned_max=self._learned_max_march_troops
        )
        self.log.debug(f"🛡️ سقف مسيرة اللورد: {castle_capacity:,} جندي")

        army_list = []
        safety_status = "SAFE"
        target_fc = get_monster_recommended_power(target_type_str, target_lv)

        if form_army_dict and formation_id > 0:
            total_form_req = sum(
                int(v) for k, v in form_army_dict.items()
                if str(k).isdigit() and str(v).isdigit() and not (800 <= int(k) < 900)
            )

            scale = 1.0
            if total_form_req > castle_capacity:
                scale = float(castle_capacity) / float(total_form_req)
                needed_target = castle_capacity
                self.log.debug(
                    f"🎖️ جنود التشكيلة #{formation_id} ({total_form_req:,}) يتجاوز سعة المسيرة ({castle_capacity:,}) — تم ضبطها لـ {needed_target:,}"
                )
            else:
                needed_target = total_form_req
                self.log.debug(f"🎖️ اعتماد جنود التشكيلة #{formation_id} ({needed_target:,} جندي)")

            for k, v in form_army_dict.items():
                if str(k).isdigit() and str(v).isdigit():
                    tid = int(k)
                    if 800 <= tid < 900:
                        continue
                    req = int(v)
                    scaled_req = max(1, int(req * scale)) if scale < 1.0 else req
                    avail = available.get(tid, 0)
                    take = min(scaled_req, avail)
                    if take > 0:
                        army_list.append({"id": tid, "num": take})
                        available[tid] -= take

            form_troops_count = sum(item['num'] for item in army_list)

            # حالة 1: التشكيلة فارغة تماماً أو لا تتوفر أي من قواتها بالقلعة
            if form_troops_count == 0:
                self.log.debug(f"⚠️ التشكيلة المحفوظة ({formation_id}) فارغة بالقلعة — تطبيق الدالة الخارقة")
                army_list, _, _, safety_status = select_smart_combat_army(
                    available=available,
                    target_type=target_type_str,
                    target_level=target_lv,
                    max_capacity=castle_capacity,
                    user_troops_cfg=troops_cfg,
                    heroes_info=self._heroes,
                    chosen_heroes=chosen_heroes
                )
            else:
                # حساب القوة القتالية الحقيقية للتشكيلة المحددة (قوة الجنود + قوة الأبطال)
                form_troops_power = sum(item['num'] * get_unit_power(item['id']) for item in army_list)
                hero_power = 0.0
                if chosen_heroes and self._heroes:
                    for hid in chosen_heroes:
                        h_data = next((h for h in self._heroes if isinstance(h, dict) and h.get('id') == hid), None)
                        if h_data:
                            hlv = int(h_data.get('lv', 1))
                            hstar = int(h_data.get('star', 1))
                            hero_power += (hlv * 500 + hstar * 2500)
                total_form_power = form_troops_power + hero_power
                power_ratio = total_form_power / float(target_fc) if target_fc > 0 else 1.0

                self.log.debug(
                    f"📊 قوة التشكيلة #{formation_id}: {total_form_power:,.0f} | قوة الهدف ({type_name} لفل {target_lv}): {target_fc:,} ({power_ratio*100:.1f}%)"
                )

                # حالة 2: فحص هل التشكيلة ضعيفة وستسبب خسارة واضحة أمام الهدف؟
                min_safe_ratio = 0.40 if target_lv <= 3 and not (target_type_str in ("rebels", "35")) else 0.70
                is_weak = power_ratio < min_safe_ratio
                deficit_troops = max(0, castle_capacity - form_troops_count)

                if is_weak and deficit_troops > 0:
                    self.log.warning(
                        f"⚠️ [تعزيز التشكيلة #{formation_id}] القوة ({power_ratio*100:.0f}%) أقل من الأمان ({min_safe_ratio*100:.0f}%) — تعزيزها بالقوات المتاحة لتفادي الخسارة."
                    )
                    extra_army, _, _, _ = select_smart_combat_army(
                        available=available,
                        target_type=target_type_str,
                        target_level=target_lv,
                        max_capacity=deficit_troops,
                        user_troops_cfg=deficit_troops,
                        heroes_info=self._heroes,
                        chosen_heroes=chosen_heroes
                    )
                    if extra_army:
                        army_dict_combined: Dict[int, int] = {}
                        for item in army_list:
                            army_dict_combined[item['id']] = army_dict_combined.get(item['id'], 0) + item['num']
                        for item in extra_army:
                            army_dict_combined[item['id']] = army_dict_combined.get(item['id'], 0) + item['num']
                        army_list = [{"id": tid, "num": cnt} for tid, cnt in army_dict_combined.items() if cnt > 0]

                        new_troops_power = sum(item['num'] * get_unit_power(item['id']) for item in army_list)
                        new_total_power = new_troops_power + hero_power
                        new_ratio = new_total_power / float(target_fc) if target_fc > 0 else 1.0
                        self.log.debug(
                            f"✅ اكتمل التعزيز: القوة {new_total_power:,.0f} ({new_ratio*100:.1f}%) | إجمالي الجنود: {sum(x['num'] for x in army_list):,}"
                        )
                        if new_ratio < (0.45 if target_lv >= 28 or target_type_str in ('rebels', '35') else 0.35):
                            safety_status = "SUICIDE_RISK"
                        else:
                            safety_status = "SAFE"
                    else:
                        if power_ratio < 0.45:
                            safety_status = "SUICIDE_RISK"
                        else:
                            safety_status = "RISKY"
                elif form_troops_count < needed_target and deficit_troops > 0:
                    self.log.debug(f"ℹ️ إكمال نقص جنود التشكيلة #{formation_id} بالدالة الخارقة")
                    extra_army, _, _, _ = select_smart_combat_army(
                        available=available,
                        target_type=target_type_str,
                        target_level=target_lv,
                        max_capacity=needed_target - form_troops_count,
                        user_troops_cfg=needed_target - form_troops_count,
                        heroes_info=self._heroes,
                        chosen_heroes=chosen_heroes
                    )
                    if extra_army:
                        army_dict_combined: Dict[int, int] = {}
                        for item in army_list:
                            army_dict_combined[item['id']] = army_dict_combined.get(item['id'], 0) + item['num']
                        for item in extra_army:
                            army_dict_combined[item['id']] = army_dict_combined.get(item['id'], 0) + item['num']
                        army_list = [{"id": tid, "num": cnt} for tid, cnt in army_dict_combined.items() if cnt > 0]
        else:
            # لم يحدد المستخدم تشكيلة (formation_id <= 0) — تطبيق الدالة الخارقة لاختيار جيش قتالي متوازن ذكي
            army_list, _, _, safety_status = select_smart_combat_army(
                available=available,
                target_type=target_type_str,
                target_level=target_lv,
                max_capacity=castle_capacity,
                user_troops_cfg=troops_cfg,
                heroes_info=self._heroes,
                chosen_heroes=chosen_heroes
            )

        # فحص الأمان الاستراتيجي (Anti-Suicide Check)
        if safety_status == "SUICIDE_RISK":
            self.log.warning(
                f"🛑 [فحص الأمان الاستراتيجي] قوات القلعة المتاحة أضعف بكثير من قوة {type_name} لفل {target_lv} "
                f"(قوة الهدف {target_fc:,}) — إلغاء الهجوم لتجنب إبادة الجيش والانتحار!"
            )
            return "SUICIDE_RISK"

        # صمام الأمان الصارم (Strict Troop Guard): منع تجاوز سعة مسيرة اللورد برمجياً
        army_list = enforce_safe_march_troops(army_list, castle_capacity)

        if not army_list:
            active_marches = await self.get_active_marches_count(force_sync=True)
            if active_marches >= 1:
                self.log.info(f"⏳ [القوات في المسيرة] لا تتوفر قوات بالقلعة حالياً لوجود {active_marches} مسيرة نشطة بالخارج.")
                return "QUEUE_FULL"
            else:
                self.log.warning("⚠️ لا توجد قوات قتالية متوفرة بالقلعة ولا توجد مسيرات بالخارج!")
                return "NO_ARMY"

        total_troops = sum(item['num'] for item in army_list)
        # صمام أمان نهائي: تقليص فوري إذا تجاوز المجموع سعة مسيرة القلعة
        if total_troops > castle_capacity:
            scale_down = float(castle_capacity) / float(total_troops)
            for itm in army_list:
                itm['num'] = max(1, int(itm['num'] * scale_down))
            total_troops = sum(item['num'] for item in army_list)

        # 8. اختيار الحيوان الأليف والرونات (الحيوان يمكن إرساله في كل المسيرات معاً)
        pets_list = []
        if form_pets:
            flat_pets = []
            if isinstance(form_pets, list):
                flat_pets = form_pets
            elif isinstance(form_pets, dict):
                for sub in form_pets.values():
                    if isinstance(sub, list): flat_pets.extend(sub)
                    elif sub: flat_pets.append(sub)

            for p in flat_pets:
                if p and str(p).isdigit() and int(p) > 0:
                    pets_list = [int(p)]
                    break

        if not pets_list:
            pets_list = select_combat_pet(self.conn, set())

        rune_pages_list = [1]
        if isinstance(form_rune_pages, list) and form_rune_pages:
            rune_pages_list = [int(x) for x in form_rune_pages if str(x).isdigit()]
        elif isinstance(form_rune_pages, dict) and form_rune_pages:
            for v in form_rune_pages.values():
                if isinstance(v, list) and v:
                    rune_pages_list = [int(x) for x in v if str(x).isdigit()]
                    break
                elif str(v).isdigit():
                    rune_pages_list = [int(v)]
                    break
        if not rune_pages_list:
            rune_pages_list = [1]

        self.log.debug(f"🛡️ تشكيلة القتال: {army_list[:3]}... (إجمالي جنود: {total_troops:,}) | حيوان: {pets_list}")

        # 9. محاولة إرسال الهجوم على أهداف القائمة تباعاً حتى ينجح أحدها
        for target in candidates:
            target_id = target.get('id')
            tx, ty    = target.get('x'), target.get('y')
            t_lv      = target.get('level', '?')
            self.log.debug(f"🎯 محاولة استهداف: ID={target_id} عند ({tx}, {ty}) لفل={t_lv}")
            # حجز مؤقت في الذاكرة فقط — لن يُثبت في الملف إلا بعد نجاح الهجوم
            await self._exclude_mgr.reserve(self.uid, target_id, kingdom_id=kingdom_id)

            if map_type == 35:
                # 🏴‍☠️ المتمردين: مسيرة حشد (Mass / Rally - moveLineType 7)
                attack_payload = {
                    "needSend": True,
                    "mapId": int(kingdom_id),
                    "moveLineType": 7,
                    "matrixType": 1,
                    "runePages": rune_pages_list,
                    "needArmyList": {},
                    "heros": chosen_heroes,
                    "pets": pets_list,
                    "data": {
                        "data": {
                            "mainInstanceType": 35,
                            "massTime": 300
                        },
                        "to": {
                            "y": int(ty),
                            "x": int(tx),
                            "id": str(target_id)
                        },
                        "army": army_list
                    }
                }
            else:
                # 👾 الغزاة: مسيرة هجوم فردية (Solo Attack - moveLineType 1)
                attack_payload = {
                    "needSend": False,
                    "mapId": int(kingdom_id),
                    "moveLineType": 1,
                    "matrixType": 1,
                    "runePages": rune_pages_list,
                    "heros": chosen_heroes,
                    "pets": pets_list,
                    "data": {
                        "data": {},
                        "to": {
                            "y": int(ty),
                            "x": int(tx),
                            "id": str(target_id)
                        },
                        "army": army_list
                    }
                }

            r_attack = await self.conn.query('1007', '2', attack_payload)
            if not r_attack:
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                continue

            err = str(r_attack.get('err', '0'))
            if err == '0':
                self.log.info(f"✅ هجوم ناجح! → {target_id} (لفل {t_lv}) | أبطال={chosen_heroes} | جنود={total_troops:,}")
                # ✅ نجاح — تثبيت الاستبعاد في الملف
                await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                for hid in chosen_heroes:
                    self._busy.add(hid)
                for item in army_list:
                    self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                await asyncio.sleep(round(random.uniform(6.5, 9.5), 2))
                return "SUCCESS"
            elif err in ('8004', '9007004'):
                self.log.info(f"🛑 اكتملت طوابير المسيرات للقلعة (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "QUEUE_FULL"
            elif err == '8009':
                self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                active_marches = await self.get_active_marches_count(force_sync=True)
                if active_marches >= 1:
                    self.log.info(f"⏳ [القوات في المسيرة] نقص قوات عند الإرسال لوجود {active_marches} مسيرة نشطة بالخارج.")
                    return "QUEUE_FULL"
                else:
                    self.log.warning("⚠️ نقص حقيقي في القوات المتاحة ولا توجد مسيرات نشطة بالخارج!")
                    return "NO_ARMY"
            elif err in ('8032', '10002', '10003'):
                self.log.warning(f"🛑 نفدت طاقة اللورد بالكامل (كود {err})")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "STAMINA_EMPTY"
            elif err == '9007020':
                for hid in chosen_heroes:
                    self._busy.add(hid)
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "HERO_BUSY"
            elif err == '8035':
                current_total = sum(item['num'] for item in army_list)
                reduced_troops = max(50, int(current_total * 0.82))
                self._learned_max_march_troops = reduced_troops
                record_learned_march_capacity(self.conn, reduced_troops)
                self.log.warning(
                    f"⚠️ كود 8035 (تجاوز سعة مسيرة اللورد لـ {current_total:,} جندي) — "
                    f"تم تعديل سقف السعة فوراً إلى {reduced_troops:,} جندي وإعادة المحاولة على الهدف..."
                )
                if current_total > 50:
                    army_list = enforce_safe_march_troops(army_list, reduced_troops)
                    total_troops = sum(itm['num'] for itm in army_list)
                    attack_payload['data']['army'] = army_list
                    r_retry = await self.conn.query('1007', '2', attack_payload)
                    if r_retry and str(r_retry.get('err', '0')) == '0':
                        self.log.info(f"✅ هجوم ناجح بعد ضبط القوات! → {target_id} (لفل {t_lv}) | أبطال={chosen_heroes} | جنود={total_troops:,}")
                        await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                        for hid in chosen_heroes:
                            self._busy.add(hid)
                        for item in army_list:
                            self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                        return "SUCCESS"
                    elif r_retry and str(r_retry.get('err', '0')) == '8035':
                        self._learned_max_march_troops = max(50, int(total_troops * 0.75))
                # تحرير حجز الهدف لأن الخطأ في سعة الجيش وليس في شغل الهدف بمعركة أخرى
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                continue
            elif err == '8027':
                # كود 8027 (Err_MAP_QUEUE_NPC_LEVEL_OUT): المستوى المطلوب لم يُفتح بعد بالقتل الأول في اللعبة
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                new_max = max(1, int(t_lv) - 1) if str(t_lv).isdigit() else 1
                self._learned_max_npc_level = min(getattr(self, '_learned_max_npc_level', 35) or 35, new_max)
                self.log.warning(
                    f"⚠️ [منطق اللعبة: كود 8027] الغازي لفل {t_lv} مغلق بحسابك لأنه يتطلب القتل الأول للمستويات السابقة!\n"
                    f"   تم تحرير الهدف وتخفيض سقف المستوى تلقائياً إلى ({self._learned_max_npc_level}) لإعادة المحاولة فوراً..."
                )
                return "NPC_LEVEL_LOCKED"
            elif err == '16001':
                self.log.warning(
                    f"   ⚠️ خادم اللعبة مشغول بعملية سابقة (كود 16001: Err_CMD_OPTING) — "
                    f"تحرير الهدف {target_id} لإعادة تجهيز المسيرة نظيفاً من البداية..."
                )
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                return "CMD_OPTING"
            elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.startswith('80') and err not in ('8004', '8009', '8032', '8027', '8035')):
                self.log.warning(f"⚠️ الهدف {target_id} غير متاح أو مشغول بمعركة أخرى (كود {err}) — فحص هدف بديل فوراً...")
                await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                continue
            else:
                self.log.warning(f"⚠️ تعذر استهداف {target_id} (كود {err}) — تجربة هدف بديل...")
                await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
                continue

        return "TARGET_OCCUPIED"


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Monster Attack Bot — الهجوم على الغزاة والمتمردين")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--type", "-t", choices=["rebels", "invaders"], default=DEFAULT_MONSTER_TYPE, help="نوع الهدف: rebels (متمردين) أو invaders (غزاة) [افتراضي: rebels]")
    parser.add_argument("--minlv", type=int, default=DEFAULT_MIN_LV, help=f"أدنى لفل للهدف [افتراضي: {DEFAULT_MIN_LV}]")
    parser.add_argument("--maxlv", type=int, default=DEFAULT_MAX_LV, help=f"أعلى لفل للهدف [افتراضي: {DEFAULT_MAX_LV}]")
    parser.add_argument("--marches", "-m", type=int, default=DEFAULT_MAX_MARCHES, help=f"الحد الأقصى للمسيرات [افتراضي: {DEFAULT_MAX_MARCHES}]")
    parser.add_argument("--range", type=int, default=DEFAULT_SEARCH_RANGE, help=f"نطاق البحث [افتراضي: {DEFAULT_SEARCH_RANGE}]")
    parser.add_argument("--formation", "-f", type=int, default=DEFAULT_FORMATION_ID, help=f"رقم التشكيلة [افتراضي: {DEFAULT_FORMATION_ID}]")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    for noisy in ("onemt", "onemt_bot", "game_client", "core", "GameConnection"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    from core.session_manager import SessionManager

    async def _main():
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

        conn = GameConnection(acc)
        if not await conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(12):
            await asyncio.sleep(2.0)  # حماية من الحظر
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "monster_type": args.type,
            "min_lv": args.minlv,
            "max_lv": args.maxlv,
            "max_marches": args.marches,
            "search_range": args.range,
            "formation_id": args.formation
        }

        task = MonsterTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
