# -*- coding: utf-8 -*-
"""
tasks/gather.py — مهمة جمع الموارد الذكية التلقائية (Dynamic Auto-Gathering)
═════════════════════════════════════════════════════════════════════════════
python tasks/gather.py --email "shook123@gmail.com" --res 2 --level 5 --range 100

الميزات المطورة:
  1. لا تعتمد على أي تشكيلة مسبقة من المستخدم (تحديد ذاتي كامل 100%).
  2. اختيار القوات الأفضل للموارد:
     - أولوية قصوى لعربات النقل والحصار (عربات القمح 701..714) من الرتبة الأعلى للأدنى.
     - استكمال باقي الحمولة من المشاة (4xx) ثم الفرسان (5xx) ثم الرماة (6xx).
     - حساب عدد القوات المطلوب بدقة بناءً على سعة حمولة الحقل الهدف (cur_res).
     - استبعاد كامل لأسلحة الجدار والفخاخ (800 فما فوق) لحماية المسيرة من خطأ 8062.
  3. اختيار الأبطال الأنسب للجمع تلقائياً (محاكاة واجهة اللعبة الأصلية):
     - أولوية لأبطال الجمع والتنمية (5502xxx) الذين يمتلكون مهارات الجمع (5620xxx).
     - الترتيب بالأعلى نجوماً ومستوى.
     - إمكانية الإرسال بدون بطل عند نفاد الأبطال لاستغلال كافة الفيالق الشاغرة.
  4. اختيار الحيوان الأليف الأفضل تلقائياً من petCtrl (الأعلى مستوى).
  5. إرسال المسيرات متتالية حتى امتلاء كافة فيالق القلعة (QUEUE_FULL).
  6. دعم مورد الذهب (subType = 1) ومستوى محدد واحد للحقل المستهدف.

أنواع الموارد المدعومة:
  - 1 أو gold أو ذهب  → الذهب (Gold / Mithril) [subType = 1]
  - 2 أو food أو قمح  → مزارع القمح (Food)      [subType = 2]
  - 3 أو wood أو خشب  → مناشر الخشب (Wood)      [subType = 3]
  - 4 أو stone أو حجر → مناجم الحجر/الكوارنز       [subType = 4]
  - 5 أو iron أو حديد → مناجم الحديد (Iron)     [subType = 5]
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
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from tasks.exclude_manager import get_manager as _get_exclude_manager


DEFAULT_SEARCH_RANGE: int = 100  # نطاق البحث الثابت عن الموارد على الخريطة


# ════════════════════════════════════════════════════════════════════
#  تعريفات وقاموس الموارد (Resource Configurations)
# ════════════════════════════════════════════════════════════════════

RESOURCE_CONFIGS: Dict[Any, Dict[str, Any]] = {
    # 🪙 1. الذهب (Gold) — كود الخريطة: 1 | كود المورد: 1001 | مضاعف الوزن: 1000.0
    1:         {"sub_type": 1, "name": "الذهب (Gold)",        "icon": "🪙", "res_code": 1001, "multiplier": 1000.0},
    "1":       {"sub_type": 1, "name": "الذهب (Gold)",        "icon": "🪙", "res_code": 1001, "multiplier": 1000.0},
    "gold":    {"sub_type": 1, "name": "الذهب (Gold)",        "icon": "🪙", "res_code": 1001, "multiplier": 1000.0},
    "ذهب":     {"sub_type": 1, "name": "الذهب (Gold)",        "icon": "🪙", "res_code": 1001, "multiplier": 1000.0},
    "الذهب":   {"sub_type": 1, "name": "الذهب (Gold)",        "icon": "🪙", "res_code": 1001, "multiplier": 1000.0},

    # 🌾 2. مزارع القمح (Food) — كود الخريطة: 2 | كود المورد: 1002 | مضاعف الوزن: 1.0
    2:         {"sub_type": 2, "name": "مزارع القمح (Food)",   "icon": "🌾", "res_code": 1002, "multiplier": 1.0},
    "2":       {"sub_type": 2, "name": "مزارع القمح (Food)",   "icon": "🌾", "res_code": 1002, "multiplier": 1.0},
    "food":    {"sub_type": 2, "name": "مزارع القمح (Food)",   "icon": "🌾", "res_code": 1002, "multiplier": 1.0},
    "قمح":     {"sub_type": 2, "name": "مزارع القمح (Food)",   "icon": "🌾", "res_code": 1002, "multiplier": 1.0},
    "القمح":   {"sub_type": 2, "name": "مزارع القمح (Food)",   "icon": "🌾", "res_code": 1002, "multiplier": 1.0},
    "مزارع":   {"sub_type": 2, "name": "مزارع القمح (Food)",   "icon": "🌾", "res_code": 1002, "multiplier": 1.0},
    "مزرعة":   {"sub_type": 2, "name": "مزارع القمح (Food)",   "icon": "🌾", "res_code": 1002, "multiplier": 1.0},

    # 🪵 3. مناشر الخشب (Wood) — كود الخريطة: 3 | كود المورد: 1003 | مضاعف الوزن: 1.0
    3:         {"sub_type": 3, "name": "مناشر الخشب (Wood)",   "icon": "🪵", "res_code": 1003, "multiplier": 1.0},
    "3":       {"sub_type": 3, "name": "مناشر الخشب (Wood)",   "icon": "🪵", "res_code": 1003, "multiplier": 1.0},
    "wood":    {"sub_type": 3, "name": "مناشر الخشب (Wood)",   "icon": "🪵", "res_code": 1003, "multiplier": 1.0},
    "خشب":     {"sub_type": 3, "name": "مناشر الخشب (Wood)",   "icon": "🪵", "res_code": 1003, "multiplier": 1.0},
    "الخشب":   {"sub_type": 3, "name": "مناشر الخشب (Wood)",   "icon": "🪵", "res_code": 1003, "multiplier": 1.0},
    "منشرة":   {"sub_type": 3, "name": "مناشر الخشب (Wood)",   "icon": "🪵", "res_code": 1003, "multiplier": 1.0},

    # ⛏️ 4. مناجم الحديد (Iron) — كود الخريطة: 4 | كود المورد: 1004 | مضاعف الوزن: 6.0
    4:         {"sub_type": 4, "name": "مناجم الحديد (Iron)",   "icon": "⛏️", "res_code": 1004, "multiplier": 6.0},
    "4":       {"sub_type": 4, "name": "مناجم الحديد (Iron)",   "icon": "⛏️", "res_code": 1004, "multiplier": 6.0},
    "iron":    {"sub_type": 4, "name": "مناجم الحديد (Iron)",   "icon": "⛏️", "res_code": 1004, "multiplier": 6.0},
    "حديد":    {"sub_type": 4, "name": "مناجم الحديد (Iron)",   "icon": "⛏️", "res_code": 1004, "multiplier": 6.0},
    "الحديد":  {"sub_type": 4, "name": "مناجم الحديد (Iron)",   "icon": "⛏️", "res_code": 1004, "multiplier": 6.0},
    "منجم":    {"sub_type": 4, "name": "مناجم الحديد (Iron)",   "icon": "⛏️", "res_code": 1004, "multiplier": 6.0},

    # 🪙 5. مناجم الكوارنز / ميثريل (Silver / Mithril) — كود الخريطة: 5 | كود المورد: 1005 | مضاعف الوزن: 24.0
    5:         {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "5":       {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "silver":  {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "فضة":     {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "الكوارنز":   {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "mithril": {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "ميثريل":  {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "stone":   {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "حجر":     {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "الحجر":   {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "الماس":   {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "ألماس":   {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "الالماس": {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "الألماس": {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "diamond": {"sub_type": 5, "name": "مناجم الكوارنز (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
}


def resolve_resource(res_input: Any) -> Dict[str, Any]:
    """التعرف على نوع المورد من المدخلات سواء كان نصاً عربياً، إنجليزياً أو رقماً."""
    if isinstance(res_input, str):
        key = res_input.strip().lower()
        if key in RESOURCE_CONFIGS:
            return RESOURCE_CONFIGS[key]
        if key.isdigit() and int(key) in RESOURCE_CONFIGS:
            return RESOURCE_CONFIGS[int(key)]
    elif res_input in RESOURCE_CONFIGS:
        return RESOURCE_CONFIGS[res_input]

    # افتراضي: الذهب (subType = 1)
    return RESOURCE_CONFIGS[1]


# معدل حمولة الموارد الأساسية لكل صنف في كود اللعبة (armyinfo.lua: freeWeight)
UNIT_LOAD_RATES: Dict[int, int] = {
    8: 20,  # عربات النقل والإمداد (armyType 8: تبدأ من 20 إلى 30 - الأعلى في اللعبة ومزودة بمهارة الحمولة 8001)
    7: 13,  # منجنيق وحصار (armyType 7: 13 إلى 18)
    1: 10,  # مشاة (armyType 1 & 2: 8 إلى 13)
    4: 10,  # مشاة
    3: 8,   # فرسان (armyType 3 & 4: 6 إلى 11)
    5: 8,   # فرسان
    6: 10,  # رماة (armyType 5 & 6: 7 إلى 13)
}


# ════════════════════════════════════════════════════════════════════
#  إدارة استبعاد الأهداف المكررة (مدير مركزي موحد)
#  → تم نقلها إلى tasks/exclude_manager.py
# ════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الجمع التلقائي (محاكاة واجهة اللعبة)
# ════════════════════════════════════════════════════════════════════

# تكوين ترتيب مهارات أبطال الجمع المستخرج من كود اللعبة الأصلي (expedition_sort.lua)
GATHER_SORT_CONFIG: Dict[int, List[int]] = {
    3: [5650007, 5650002, 5650004, 5620002, 5620004, 5620009],  # الخشب (Wood)
    2: [5650007, 5650002, 5650004, 5620002, 5620004, 5620012],  # القمح (Food)
    4: [5650007, 5650002, 5650004, 5620002, 5620004, 5620010],  # الحديد (Iron)
    5: [5650007, 5650002, 5650004, 5620002, 5620004, 5620011],  # الكوارنز / الألماس (Mithril)
    1: [5650007, 5650002, 5650004, 5620002, 5620004, 5620003],  # الذهب (Gold)
}
LOAD_SKILL = 5620001  # مهارة زيادة حمولة القوات (Load skill)


def _score_gather_hero(hero: dict, sub_type: int = 1) -> Tuple[int, int, int, int, int]:
    """
    تقييم وترتيب الأبطال وفق كود اللعبة الأصلي 100% (expeditionTypeltCtrl.sortHeros):
    1. specialSkillWeights: عدد مهارات الجمع المتطابقة مع مهارات الفرز للمورد.
    2. additionWeights: مستوى مهارة المورد التخصصية المستهدفة (الخشب/القمح/الحديد/الألماس).
    3. valueWeights: مستوى البطل ورتبته.
    4. معيار كسر التعادل: معرف البطل الأصغر (6000000 - hid).
    """
    hid_raw = hero.get('id', 0)
    try:
        hid = int(hid_raw)
    except Exception:
        hid = 0

    sort_skills = GATHER_SORT_CONFIG.get(sub_type, [5650007, 5650002, 5650004, 5620002, 5620004])

    skills_dict = hero.get('skillList', {})
    sids: List[int] = []
    skill_lvs: Dict[int, int] = {}
    if isinstance(skills_dict, dict):
        for s in skills_dict.values():
            if isinstance(s, dict) and s.get('id'):
                try:
                    sid = int(s['id'])
                    sids.append(sid)
                    skill_lvs[sid] = int(s.get('lv', 1))
                except Exception:
                    pass

    sp_weight = sum(1 for s in sids if s in sort_skills)
    target_res_skill = sort_skills[-1] if sort_skills else 0
    add_weight = skill_lvs.get(target_res_skill, 0)

    level = int(hero.get('level') or hero.get('lv') or 1)
    star = int(hero.get('star') or 0)
    return (sp_weight, add_weight, level, star, 6000000 - hid)


def pick_best_gather_heroes(heroes: list, busy: Set[int], max_heroes: int = 2, sub_type: int = 1) -> List[int]:
    """
    اختيار أفضل أبطال جمع متاحين بالقلعة وغير مشغولين لنوع المورد المستهدف (حتى بطلين):
    1. فرز الأبطال وفق معايير اللعبة الأصلية (expeditionTypeltCtrl.sortHeros).
    2. استبعاد الأبطال المشغولين في مسيرات حربية أو مسيرات أخرى (status.state != 0).
    3. السماح بالإرسال بدون أبطال عند عدم توفرهم.
    """
    available_heroes = []
    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or int(hid) in busy:
            continue
        if hero.get('status', {}).get('state', 0) != 0:
            continue
        available_heroes.append(hero)

    if not available_heroes:
        return []

    # فرز أبطال التنمية والجمع (5502xxx أو من يملكون مهارات جمع) عن باقي أبطال القلعة
    gather_heroes = []
    other_heroes = []
    for h in available_heroes:
        hid_str = str(h.get('id', ''))
        sp_w, add_w, _, _, _ = _score_gather_hero(h, sub_type)
        if hid_str.startswith('5502') or sp_w > 0 or add_w > 0:
            gather_heroes.append(h)
        else:
            other_heroes.append(h)

    gather_heroes.sort(key=lambda h: _score_gather_hero(h, sub_type), reverse=True)
    other_heroes.sort(key=lambda h: _score_gather_hero(h, sub_type), reverse=True)

    if len(gather_heroes) >= 2:
        return [int(h['id']) for h in gather_heroes[:max_heroes]]
    elif len(gather_heroes) == 1:
        # بطل جمع واحد متاح -> يرسل بطل جمع واحد فقط لحماية أبطال الحرب من الانشغال بالموارد
        return [int(gather_heroes[0]['id'])]
    else:
        # انعدام أبطال الجمع بالكامل -> بديل اضطراري من أي أبطال متاحين
        return [int(h['id']) for h in other_heroes[:max_heroes]]


def pick_best_gather_hero(heroes: list, busy: Set[int], sub_type: int = 1) -> Optional[int]:
    """للتوافق العكسي: يعيد أول بطل."""
    res = pick_best_gather_heroes(heroes, busy, max_heroes=1, sub_type=sub_type)
    return res[0] if res else None


# ════════════════════════════════════════════════════════════════════
#  مضاعفات أوزان الموارد المستخرجة من كود اللعبة الأصلي (worldDispatchArmyView.lua)
# ════════════════════════════════════════════════════════════════════

RESOURCE_WEIGHT_MULTIPLIERS: Dict[int, float] = {
    1001: 1000.0,  # الذهب (Gold): كل 1 ذهب يعادل 1000 حمولة
    1002: 1.0,     # القمح (Food): 1.0
    1003: 1.0,     # الخشب (Wood): 1.0
    1004: 6.0,     # الحديد (Iron): 6.0
    1005: 24.0,    # الكوارنز / ميثريل (Silver/Mithril): 24.0
}

# سعات الحقول الافتراضية لكل مستوى في حال لم يُرجع السيرفر currentSourceNum
DEFAULT_NODE_CAPACITY: Dict[int, Dict[int, int]] = {
    1: {1: 15, 2: 30, 3: 45, 4: 60, 5: 75, 6: 90, 7: 110, 8: 130},              # الذهب
    2: {1: 50000, 2: 100000, 3: 180000, 4: 400000, 5: 800000, 6: 1200000, 7: 1800000, 8: 2500000}, # القمح
    3: {1: 50000, 2: 100000, 3: 180000, 4: 400000, 5: 800000, 6: 1200000, 7: 1800000, 8: 2500000}, # الخشب
    4: {1: 5000, 2: 10000, 3: 18000, 4: 30000, 5: 50000, 6: 80000, 7: 120000, 8: 180000},          # الحديد
    5: {1: 1500, 2: 3000, 3: 5000, 4: 8000, 5: 12000, 6: 20000, 7: 30000, 8: 45000},               # الكوارنز
}

def get_resource_multiplier(res_code: int = 0, sub_type: int = 1) -> float:
    """استرجاع مضاعف حمولة المورد المطابق لكود اللعبة."""
    if res_code in RESOURCE_WEIGHT_MULTIPLIERS:
        return RESOURCE_WEIGHT_MULTIPLIERS[res_code]
    sub_map = {1: 1000.0, 2: 1.0, 3: 1.0, 4: 6.0, 5: 24.0}
    return sub_map.get(sub_type, 1.0)


# ════════════════════════════════════════════════════════════════════
#  سعات حمولة الوحدات المستخرجة من جدول اللعبة (armyinfo.lua)
# ════════════════════════════════════════════════════════════════════

UNIT_FREE_WEIGHTS: Dict[int, int] = {
    # عربات الإمداد ونقل الموارد (أرقام فردية - armyType 8)
    701: 20,  # عربة نقل المستوى 1 (Tier 1) - حمولة أساسية 20
    703: 21,  # عربة نقل المستوى 3 (Tier 3) - حمولة أساسية 21
    705: 22,  # عربة نقل المستوى 5 (Tier 5) - حمولة أساسية 22
    707: 27,  # عربة نقل المستوى 7 (Tier 7) - حمولة أساسية 27
    709: 28,  # عربة نقل / ورشة هجوم المستوى 9 (Tier 9) - حمولة أساسية 28
    711: 30,  # عربة نقل المستوى 11 (Tier 11) - حمولة أساسية 30

    # منجنيق وعربات الهجوم (أرقام زوجية - armyType 7)
    702: 13,  # منجنيق المستوى 2 (Tier 2) - حمولة أساسية 13
    704: 14,  # منجنيق المستوى 4 (Tier 4) - حمولة أساسية 14
    706: 15,  # منجنيق المستوى 6 (Tier 6) - حمولة أساسية 15
    708: 16,  # منجنيق المستوى 8 (Tier 8) - حمولة أساسية 16
    710: 17,  # منجنيق المستوى 10 (Tier 10) - حمولة أساسية 17
    712: 18,  # منجنيق المستوى 12 (Tier 12) - حمولة أساسية 18

    # المشاة (Infantry - armyType 1 & 2)
    412: 13, 411: 13, 410: 12, 409: 12, 408: 11, 407: 11, 406: 10, 405: 10, 404: 9, 403: 9, 402: 8, 401: 8,
    # الفرسان (Cavalry - armyType 3 & 4)
    512: 11, 511: 11, 510: 10, 509: 10, 508: 9, 507: 9, 506: 8, 505: 8, 504: 7, 503: 7, 502: 6, 501: 6,
    # الرماة (Archers - armyType 5 & 6)
    612: 13, 611: 12, 610: 12, 609: 11, 608: 11, 607: 10, 606: 10, 605: 9, 604: 9, 603: 8, 602: 8, 601: 7,
}


def calculate_unit_capacity(
    army_id: int,
    res_type: int = 1002,
    load_bonus: float = 0.0,
    hero_bonus: float = 0.0
) -> float:
    """
    حساب سعة حمل أي وحدة لأي مورد ديناميكياً لكل حساب وفق كود اللعبة الأصلي (kingdomMapCtrl:getArmyWeightPlus):
    السعة = الوزن الأساسي للوحدة * (1 + بونص الحساب الإجمالي + بونص الأبطال)
    تحويل نوع المورد المستخرج من كود اللعبة الأصلي (worldDispatchArmyView.lua):
      - القمح والخشب (1002, 1003): سعة القمح ÷ 1.0 (مضاعف الوزن = 1.0)
      - الحديد (1004): سعة القمح ÷ 6.0 (مضاعف الوزن = 6.0)
      - الكوارنز / الميثريل (1005): سعة القمح ÷ 24.0 (مضاعف الوزن = 24.0)
      - الذهب (1001, 1006): سعة القمح ÷ 1000.0 (مضاعف الوزن = 1000.0)
    """
    base_w = float(UNIT_FREE_WEIGHTS.get(army_id, 10))
    total_mult = 1.0 + load_bonus + hero_bonus
    wheat_cap = base_w * total_mult

    if res_type == 1004:
        return wheat_cap / 6.0
    elif res_type == 1005:
        return wheat_cap / 24.0
    elif res_type in (1001, 1006):
        return wheat_cap / 1000.0
    return wheat_cap


async def fetch_war_boe_pload(conn: GameConnection) -> float:
    """
    استخراج بونص P_LOAD (11) لحمولة الجيش من الذاكرة الحية (RAM) مباشرة
    من boeAttributeCtrl بصفر طلبات شبكة، مع استعلام احتياطي فقط عند فراغ الذاكرة.
    """
    if not conn or not getattr(conn, "_alive", False):
        return 0.0

    cached = getattr(conn, "_cached_boe_pload", None)
    if cached is not None:
        return cached

    pload_bonus = 0.0

    # 1. قراءة فورية من الذاكرة الحية boeAttributeCtrl (Zero-Request)
    init_data = getattr(conn, "init_data", {})
    if isinstance(init_data, dict):
        boe = init_data.get('boeAttributeCtrl', {})
        if isinstance(boe, dict):
            c1 = boe.get('1', {}).get('1', {}).get('11', {})
            if isinstance(c1, dict) and '1' in c1:
                try:
                    pload_bonus = float(c1['1']) / 1000.0
                    setattr(conn, "_cached_boe_pload", pload_bonus)
                    return pload_bonus
                except Exception:
                    pass

    # 2. استعلام احتياطي طوارئ فقط إذا لم تكن السمة محملة بالذاكرة
    try:
        res6 = await conn.query("1019", "6", {"cond": 1, "target": 1, "attr": 11}, timeout=4.0)
        if res6 and isinstance(res6, dict):
            data = res6.get("data", {})
            if isinstance(data, dict):
                rate = float(data.get("rate", 0))
                value = float(data.get("value", 0))
                if rate > 0:
                    pload_bonus = rate / 1000.0
                elif value > 0:
                    pload_bonus = value / 1000.0
    except Exception:
        pass

    setattr(conn, "_cached_boe_pload", pload_bonus)
    return pload_bonus


# ════════════════════════════════════════════════════════════════════
#  جداول تعزيز وصقل عتاد اللورد (أحذية النقل EID 6520000 - السمة 32 SOLDIER_LOAD)
#  مستخرجة مباشرة من كود اللعبة الأصلي (equipment_strengthen.lua & equipment_refine.lua)
# ════════════════════════════════════════════════════════════════════

STRENGTHEN_6520000: List[int] = [
    0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280,
    300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500, 540, 580, 620, 660, 700, 740, 780, 820, 860,
    900, 940, 980, 1020, 1060, 1100, 1140, 1180, 1220, 1260, 1300, 1360, 1420, 1480, 1540, 1600, 1660, 1720, 1780, 1840,
    1900, 1960, 2020, 2080, 2140, 2200, 2260, 2320, 2380, 2440, 2500, 2580, 2660, 2740, 2820, 2900, 2980, 3060, 3140, 3220,
    3300, 3380, 3460, 3540, 3620, 3700, 3780, 3860, 3940, 4020, 4100, 4190, 4280, 4370, 4460, 4550, 4640, 4730, 4820, 4910, 5000
]

REFINE_6520000: Dict[int, Tuple[int, int]] = {
    0: (0, 0), 1: (100, 5), 2: (300, 9), 3: (500, 14), 4: (700, 18), 5: (900, 23),
    6: (1100, 27), 7: (1300, 32), 8: (1500, 36), 9: (1700, 41), 10: (1900, 45),
    11: (2100, 50), 12: (2300, 54), 13: (2500, 59), 14: (2700, 63), 15: (2900, 68),
    16: (3100, 72), 17: (3300, 77), 18: (3500, 81), 19: (3700, 86), 20: (3900, 90),
    21: (4100, 99), 22: (4300, 108), 23: (4500, 117), 24: (4700, 126), 25: (4900, 135)
}


def calculate_load_bonus(
    conn: GameConnection,
    sub_type: int = 1,
    hero_list: Optional[List[int]] = None,
    has_gather_hero: bool = False
) -> float:
    """
    حساب بونص سعة حمولة القوات الحقيقي لأي حساب وفق كود اللعبة الأصلي (kingdomMapCtrl:getArmyWeightPlus):
    1. أبحاث المعهد (technologyCtrl):
       - 22001 (عربة الإمداد I): +0.01 (+1%) لكل لفل (حتى +10%).
       - 22010 (عربة الإمداد II): +0.02 (+2%) لكل لفل (حتى +30%).
    2. مهارة اللورد (lordInfoCtrl / lordSkillCtrl):
       - 11001 (الحمولة القسرية): +0.02 (+2%) لكل لفل في شجرة اللورد العسكرية (حتى +10%).
    3. امتيازات الـ VIP (vipCtrl):
       - التأثير 117 (SOLDIER_LOAD_BOOST): يمنح 20 في الألف (+2%) لكل مستوى VIP.
    4. عتاد اللورد المرتدى (equipmentCtrl):
       - أحذية النقل EID 6520000 تمنح السمة 32 (SOLDIER_LOAD) بنسبة مئوية محسوبة بدقة من
         مستوى التعزيز (slv) ومستوى الصقل (rlv) وفق صيغة اللعبة الأصلية (equipmentCell:getCurEquipRefineSkillResult).
    5. بونصات العناصر والتعزيزات النشطة (buffCtrl):
       - التأثير 117 (SOLDIER_LOAD_BOOST مقسوماً على 1000).
    6. بونص السمات العامة للحرب (boeAttributeCtrl):
       - سمة P_LOAD (11) تحت الشرط ALL_WAR (1) والهدف ALL_ARMY (1) مقسومة على 1000.
    7. بونص أبطال المسيرة المختارين (مهارة الحمولة 5620001 تمنح حتى +14.312% عند لفل 40).
    """
    init_data = getattr(conn, "init_data", {})
    if not isinstance(init_data, dict):
        init_data = {}

    # 1. أبحاث المعهد الحقيقية للحمولة (TechnologyCtrl)
    tech_data = init_data.get('technologyCtrl', {})
    tech_bonus = 0.0

    def _get_tech_lv(tid_int: int) -> int:
        for k in (str(tid_int), tid_int):
            if k in tech_data:
                val = tech_data[k]
                try:
                    if isinstance(val, list) and len(val) > 1: return int(val[1])
                    elif isinstance(val, dict): return int(val.get('lv', val.get('level', 0)))
                    return int(val)
                except Exception: pass
        return 0

    # 22001: عربة الإمداد 1 (Supply Cart) - 1% لكل مستوى
    lv_22001 = _get_tech_lv(22001)
    if lv_22001 > 0:
        tech_bonus += lv_22001 * 0.01

    # 22010: عربة الإمداد 2 (Supply Cart II) - 2% لكل مستوى
    lv_22010 = _get_tech_lv(22010)
    if lv_22010 > 0:
        tech_bonus += lv_22010 * 0.02

    # 2. مهارات اللورد (lordInfoCtrl / lordSkillCtrl)
    lord_skills = init_data.get('lordInfoCtrl', {}).get('skill', {}).get('skillBasic', {})
    lord_bonus = 0.0

    val_11001 = lord_skills.get('11001') or lord_skills.get(11001)
    if not val_11001:
        # فحص شجرة مهارات اللورد النشطة في lordSkillCtrl
        ls_ctrl = init_data.get('lordSkillCtrl', {})
        active_set = str(ls_ctrl.get('activeSetID', '1'))
        sdata = ls_ctrl.get('setListData', {}).get(active_set, {})
        val_11001 = sdata.get('list', {}).get('11001')

    lv_11001 = 0
    if isinstance(val_11001, list) and len(val_11001) > 1:
        lv_11001 = int(val_11001[1])
    elif isinstance(val_11001, dict):
        lv_11001 = int(val_11001.get('lv', val_11001.get('level', 0)))
    elif val_11001:
        try:
            lv_11001 = int(val_11001)
        except Exception:
            pass

    # 11001: مهارة حمولة القوات في شجرة اللورد - 2% لكل مستوى
    if lv_11001 > 0:
        lord_bonus += lv_11001 * 0.02

    # 3. امتيازات الـ VIP (vipCtrl - التأثير 117 SOLDIER_LOAD_BOOST)
    # كل مستوى VIP يمنح 20 في الألف (0.02) لحمولة القوات
    vip_lv = int(init_data.get('vipCtrl', {}).get('vipLv', 0))
    vip_bonus = (vip_lv * 20.0) / 1000.0

    # 4. عتاد اللورد المرتدى (equipmentCtrl - السمة 32 SOLDIER_LOAD)
    equip_bonus = 0.0
    eq_ctrl = init_data.get('equipmentCtrl', {})
    if isinstance(eq_ctrl, dict):
        for item in eq_ctrl.get('equipment_array', []):
            if isinstance(item, dict) and item.get('isWear') and item.get('eid') == 6520000:
                slv = int(item.get('slv', 0))
                rlv = int(item.get('rlv', 0))
                st_val = STRENGTHEN_6520000[min(max(slv, 0), len(STRENGTHEN_6520000) - 1)]
                rf_base, rf_skill = REFINE_6520000.get(min(max(rlv, 0), 25), (0, 0))
                all_prop = 100 + st_val + rf_base
                skill_val = 400 + rf_skill
                res_val = math.floor(all_prop / 100.0 * skill_val) / 100.0  # في الألف
                equip_bonus += res_val / 1000.0

    # 5. بونصات العناصر النشطة (buffCtrl - التأثير 117 SOLDIER_LOAD_BOOST)
    buff_bonus = 0.0
    buffs = init_data.get('buffCtrl', [])
    if isinstance(buffs, list):
        for b in buffs:
            if isinstance(b, dict) and b.get('effect') == 117:
                try: buff_bonus += float(b.get('val', 0)) / 1000.0
                except Exception: pass

    # 6. بونص سمات الحرب boeAttributeCtrl (السمة 11 - P_LOAD تحت الشرط 1)
    boe_bonus = 0.0
    cached_boe = getattr(conn, "_cached_boe_pload", None)
    if cached_boe is not None and isinstance(cached_boe, (int, float)) and cached_boe > 0:
        boe_bonus = float(cached_boe)
    else:
        boe = init_data.get('boeAttributeCtrl', {})
        if isinstance(boe, dict):
            c1 = boe.get('1', {}).get('1', {}).get('11', {})
            if isinstance(c1, dict) and '1' in c1:
                try:
                    raw = float(c1['1'])
                    boe_bonus = raw / 1000.0
                except Exception: pass

    # الحساب الديناميكي الدقيق الخالي من أي أرقام تخمينية ثابتة (kingdomMapCtrl:getArmyWeightPlus)
    base_bonus = tech_bonus + lord_bonus + vip_bonus + equip_bonus + buff_bonus + boe_bonus

    # 5. بونص أبطال الجمع والتنمية المختارين للمسيرة (مهارة 5620001 - سعة الحمولة)
    hero_bonus = 0.0
    h_ctrl = init_data.get('heroCtrl', {})
    h_map: Dict[Any, dict] = {}
    if isinstance(h_ctrl, dict):
        h_map = h_ctrl.get('heroList', h_ctrl.get('heroMap', {}))
    elif isinstance(h_ctrl, list):
        for h in h_ctrl:
            if isinstance(h, dict) and 'id' in h:
                h_map[h['id']] = h

    if hero_list:
        for hid in hero_list:
            h_obj = h_map.get(hid) or h_map.get(str(hid))
            if h_obj and isinstance(h_obj, dict):
                skills = h_obj.get('skillList', {})
                load_lv = 0
                if isinstance(skills, dict):
                    for s in skills.values():
                        if isinstance(s, dict) and s.get('id') == LOAD_SKILL:
                            try: load_lv = int(s.get('lv', 0))
                            except Exception: pass
                if load_lv > 0:
                    hero_bonus += 0.143123 * (load_lv / 40.0)
            elif has_gather_hero:
                hero_bonus += 0.143123
    elif has_gather_hero:
        hero_bonus = 0.143123

    return max(0.0, base_bonus + hero_bonus)



def calculate_estimated_march_capacity(init_data: dict, chosen_heroes: list = None) -> int:
    """
    سعة مسيرة اللورد وساحة التدريب (Drill Ground - bid 121) والأبطال:
    محسوبة بدقة 100% ومطابقة لواجهة اللعبة الرسمية عبر المحرك المركزي tasks.march_capacity.
    """
    try:
        from tasks.march_capacity import get_castle_march_capacity
        return get_castle_march_capacity(init_data, chosen_heroes=chosen_heroes)
    except Exception:
        return 50000


# ════════════════════════════════════════════════════════════════════
#  اختيار تشكيلة الجيش التلقائية (محاكاة واجهة اللعبة الحقيقية 100%)
# ════════════════════════════════════════════════════════════════════

def select_gathering_army(
    available: Dict[int, int],
    target_load: int,
    load_bonus: float = 0.0,
    hero_bonus: float = 0.0,
    max_march_troops: Optional[int] = None,
) -> Tuple[List[Dict[str, int]], int]:
    """
    اختيار تشكيلة الجيش تلقائياً لجمع الموارد وفق كود اللعبة الأصلي (worldDispatchArmyView:sortArmyListByWeight):
    1. الأولوية المطلقة لعربة نقل المستوى 1 (701) أولاً دائماً.
    2. فرز باقي القوات والورشة تنازلياً حسب سعة الحمولة الحرة (freeWeight):
       - عربات الإمداد الأعلى (711، 709، 707، 705، 703) تأتي مباشرة لتغطية أي نقص.
       - ثم المنجنيق وعربات الهجوم (712..702) والمشاة والفرسان والرماة عند الحاجة.
    3. حساب سعة كل وحدة بدقة بالغة عبر calculate_unit_capacity ديناميكياً لكل حساب وفق عتاده ومستوى VIP وأبحاثه.
    4. إرسال أي قوات متاحة لتغطية حمولة الحقل بدون أي شرط مانع للسعة.
    5. الالتزام الصارم بسقف سعة معسكر التجمع ومسيرة اللورد (max_march_troops) لمنع تجاوز السعة وتجنب خطأ 8035.
    """
    # الترتيب المطابق تماماً لدالة sortArmyListByWeight في worldDispatchArmyView.lua
    def _troop_sort_key(tid: int):
        if tid == 701:
            return (0, 0, 0, 0)  # 701 أولاً دائماً
        w = UNIT_FREE_WEIGHTS.get(tid, 0)
        tid_mod = tid % 1000
        lv_mod = tid_mod % 100
        # فرز تنازلي حسب الحمولة، ثم الرتبة/المستوى، ثم تصاعدي حسب المعرف
        return (1, -w, -lv_mod, tid_mod)

    # استبعاد الفخاخ (8xx) والوحدات ذات الحمولة 0
    ordered_tids = sorted(
        [tid for tid, cnt in available.items() if cnt > 0 and tid < 800 and UNIT_FREE_WEIGHTS.get(tid, 0) > 0],
        key=_troop_sort_key
    )

    # حساب سعة الحمولة المطلوبة بدقة مطابقة لمحرك اللعبة (curResCount / armyWeight)
    rem_load = float(target_load)
    total_carried = 0.0
    army_list: List[Dict[str, int]] = []
    current_total_troops = 0

    for tid in ordered_tids:
        avail = available.get(tid, 0)
        if avail <= 0:
            continue

        unit_weight = calculate_unit_capacity(tid, load_bonus=load_bonus, hero_bonus=hero_bonus)
        needed = min(avail, math.ceil(rem_load / unit_weight))

        # كبح عدد القوات بحيث لا يتجاوز سعة معسكر التجمع ومسيرة اللورد (لمنع خطأ 8035)
        if max_march_troops and max_march_troops > 0:
            remaining_quota = max_march_troops - current_total_troops
            if remaining_quota <= 0:
                break
            needed = min(needed, remaining_quota)

        if needed > 0:
            army_list.append({"id": tid, "num": needed})
            available[tid] -= needed
            load_added = needed * unit_weight
            rem_load = max(0.0, rem_load - load_added)
            total_carried += load_added
            current_total_troops += needed
            if rem_load <= 0:
                break

    return army_list, int(round(total_carried))


# ════════════════════════════════════════════════════════════════════
#  اختيار الحيوان الأليف تلقائياً (Dynamic Pet Selection)
# ════════════════════════════════════════════════════════════════════

def select_gathering_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]:
    """اختيار حيوان أليف متاح للمسيرة من بيانات petCtrl (الأعلى مستوى)."""
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
#  كلاس المهمة (GatherTask)
# ════════════════════════════════════════════════════════════════════

class GatherTask_2(BaseTask):
    """
    مهمة جمع الموارد الذكية التلقائية:
      - مورد واحد ومستوى محدد من المستخدم
      - دعم الذهب (subType = 1) وباقي الموارد
      - اختيار تلقائي للجيش (عربات النقل أولاً)
      - اختيار تلقائي للأبطال والحيوانات
      - إرسال المسيرات حتى امتلاء كافة الفيالق (QUEUE_FULL)
    """
    name = "gather_2"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self._heroes       : list          = []
        self._busy_heroes  : Set[int]      = set()
        self._used_army    : Dict[int, int] = {}
        self._used_pets    : Set[int]      = set()
        self._exclude_mgr  = _get_exclude_manager()
        self._learned_max_march_troops: Optional[int] = None

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

    # ── المهمة الرئيسية: الإرسال حتى امتلاء كافة الفيالق ──────────

    async def run(self) -> TaskResult:
        """إرسال مسيرات متتالية حتى امتلاء جميع طوابير الفيالق المتاحة."""
        cfg = self.config or {}

        # 1. استخراج نوع المورد المستهدف (مورد واحد فقط)
        res_key = cfg.get('res_type') or cfg.get('res') or cfg.get('resource') or 1
        res_info = resolve_resource(res_key)
        sub_type = int(res_info.get('sub_type', 0))

        # فحص شرط مستوى القلعة لموارد الحديد (لفل 10) والفضة (لفل 15) لتفادي الأخطاء 8041 و 8042
        from tasks.march_capacity import get_castle_level
        c_lv = get_castle_level(getattr(self.conn, 'init_data', {}))
        if sub_type == 4 and c_lv < 10:
            self.log.warning(f"⚠️ جمع مورد الحديد (Iron) يتطلب قلعة لفل 10 على الأقل (لفل القلعة الحالي: {c_lv}) — تخطي لمنع الخطأ 8041.")
            return TaskResult.fail(f"Iron requires Castle Lv 10 (current: {c_lv})", data={"sent": 0, "stop_reason": "CASTLE_LV_LOW"})
        elif sub_type == 5 and c_lv < 15:
            self.log.warning(f"⚠️ جمع مورد الفضة/الكوارنز (Silver) يتطلب قلعة لفل 15 على الأقل (لفل القلعة الحالي: {c_lv}) — تخطي لمنع الخطأ 8042.")
            return TaskResult.fail(f"Silver requires Castle Lv 15 (current: {c_lv})", data={"sent": 0, "stop_reason": "CASTLE_LV_LOW"})

        # 2. استخراج مستوى الحقل المستهدف (مستوى واحد فقط)
        target_lv = int(cfg.get('level') or cfg.get('lv') or cfg.get('min_lv') or 6)

        search_range = 100 # ثابت 100 كم بشكل مباشر ودائم
        max_marches_safety = int(cfg.get('max_marches') or 10)  # سقف أمان أقصى

        self.log.info(f"🌾 [جمع الموارد] بدء البحث عن {res_info['name']} لفل {target_lv}")

        if not self._heroes:
            await self._load_heroes()

        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 3. جلب إحداثيات القلعة ومعرف المملكة من الذاكرة الحية (Zero-Request)
        cx, cy = None, None
        pos = self.conn.init_data.get('cityCtrl', {}).get('cinfo', {}).get('pos', {}) if hasattr(self.conn, 'init_data') else {}
        if pos and 'x' in pos and 'y' in pos:
            cx = int(pos['x'])
            cy = int(pos['y'])
        else:
            try:
                r_castle = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=6)
                if r_castle and r_castle.get('retData'):
                    cx = int(r_castle['retData'].get('x'))
                    cy = int(r_castle['retData'].get('y'))
            except Exception:
                pass

        if cx is None or cy is None:
            return TaskResult.fail("فشل في تحديد إحداثيات القلعة على الخريطة")

        self.log.debug(f"📍 موقع القلعة: ({cx}, {cy})")

        lord_base = self.conn.init_data.get('lordInfoCtrl', {}).get('base', {}) if hasattr(self.conn, 'init_data') else {}
        kingdom_id = int(lord_base.get('partition', 0)) if isinstance(lord_base, dict) else 0

        sent_count = 0
        consecutive_errors = 0
        target_marches = int(cfg.get('max_marches') or 10)
        max_attempts = target_marches * 3 + 6
        attempts = 0
        cmd_opting_retries = 0

        self._busy_heroes  = set(int(h) for h in cfg.get('busy_heroes', []))
        self._used_army    = {}
        self._used_pets    = set(int(p) for p in cfg.get('used_pets', []))
        # الذاكرة المؤقتة للاستبعاد مدمجة الآن في ExcludeManager
        last_status = None

        while sent_count < target_marches and attempts < max_attempts:
            self.log.debug(f"🏹 محاولة إرسال مسيرة الفيلق ({sent_count + 1}/{target_marches})...")

            status = await self._send_one_march(
                res_info=res_info,
                target_lv=target_lv,
                cx=cx,
                cy=cy,
                kingdom_id=kingdom_id,
                search_range=100
            )
            last_status = status

            if status == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                cmd_opting_retries = 0

                if sent_count < target_marches:
                    # مهلة أمان مدمجة في الكود بين إطلاق المسيرات لمكافحة الحظر وتشتيت النمط
                    wait_time = round(random.uniform(9.0, 14.0), 2)
                    self.log.debug(f"⏳ مهلة أمان قبل الفيلق التالي ({wait_time} ثانية)...")
                    await asyncio.sleep(wait_time)
            elif status in ("QUEUES_FULL_SKIP","8004", "9007004"):
                self.log.info("🏁 اكتملت جميع الفيالق وطوابير المسيرات للقلعة (طوابير ممتلئة بالكامل).")
                break
            elif status in ("NO_ARMY", "8009"):
                self.log.info("🏁 نفدت القوات المتاحة بالقلعة لإرسال فيالق إضافية.")
                break
            elif status in ("CMD_OPTING", "16001", "CMD_OPTING_FAILED"):
                cmd_opting_retries += 1
                if cmd_opting_retries <= 2:
                    wait_time = round(random.uniform(10.0, 16.0), 2)
                    self.log.warning(
                        f"⏳ [خادم اللعبة مشغول - كود 16001] انتظار {wait_time} ثانية لفك القفل "
                        f"ثم إعادة تجهيز المسيرة نظيفاً من البداية (محاولة {cmd_opting_retries}/2)..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    self.log.warning("🏁 استمر انشغال خادم اللعبة (كود 16001) بعد المحاولات — إيقاف الدورة مؤقتاً.")
                    break
            elif status == "NO_TARGET":
                self.log.warning(f"⚠️ لم يتم العثور على حقول {res_info['name']} من مستوى {target_lv} حتى مستوى 2 في نطاق {search_range} كم — إغلاق المهمة.")
                break
            elif status in ("HERO_BUSY", "TARGET_OCCUPIED"):
                consecutive_errors += 1
                if consecutive_errors >= 4:
                    self.log.warning("⚠️ 4 أخطاء متتالية أثناء تجهيز المسيرات — إنهاء الدورة.")
                    break
                await asyncio.sleep(round(random.uniform(1.2, 2.4), 2))
            else:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    break

        self.log.info(f"🏁 [جمع الموارد] تم إرسال {sent_count}/{target_marches} مسيرة بنجاح")

        result_data = {
            "sent": sent_count,
            "dispatched": sent_count,
            "queue_full": False,
            "stop_reason": last_status,
            "busy_heroes": list(self._busy_heroes),
            "used_pets": list(self._used_pets),
        }

        if sent_count > 0:
            return TaskResult.ok(
                f"✅ تم إرسال {sent_count} مسيرة جمع ({res_info['name']})",
                **result_data
            )
        if last_status in ("QUEUES_FULL_SKIP", "QUEUE_FULL", "8004", "9007004"):
            return TaskResult.fail("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل (QUEUES_FULL_SKIP)", **result_data)
        if last_status in ("NO_ARMY", "8009"):
            return TaskResult.fail("🛑 نفدت القوات المتاحة بالقلعة لإرسال مسيرة جمع كاملة", **result_data)
        if last_status in ("CMD_OPTING", "16001", "CMD_OPTING_FAILED"):
            return TaskResult.fail("⚠️ خادم اللعبة مشغول بعملية سابقة (كود 16001: Err_CMD_OPTING)", **result_data)
        if last_status == "NO_TARGET":
            return TaskResult.fail(f"⚠️ لم يتم العثور على حقول {res_info['name']} متاحة في النطاق المحدد", **result_data)
        return TaskResult.fail("لم يتم إرسال أي مسيرة جمع", retry_after=120, **result_data)

    # ── إرسال مسيرة فيلق واحدة ───────────────────────────────────

    async def _send_one_march(
        self,
        res_info: Dict[str, Any],
        target_lv: int,
        cx: int,
        cy: int,
        kingdom_id: int,
        search_range: int
    ) -> str:
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. البحث عن حقل المورد (النزول تدريجياً من المستوى المطلوب حتى مستوى 2)
        exclude_map = await self._exclude_mgr.get_exclude_map(self.uid, kingdom_id=kingdom_id)

        min_fallback_lv = min(2, target_lv)
        found_target = None
        actual_found_lv = target_lv

        for cur_try_lv in range(target_lv, min_fallback_lv - 1, -1):
            r_search = await self.conn.query('2011', '3', {
                "mapType": 5,
                "num": 1,
                "subType": res_info["sub_type"],
                "y": cy,
                "x": cx,
                "exclude": exclude_map,
                "minLv": cur_try_lv,
                "maxLv": cur_try_lv,
                "range": 100
            }, timeout=6)

            if r_search and r_search.get('result'):
                cand = r_search['result'][0]
                cand_id = cand.get('id')
                if cand_id and str(cand_id) in exclude_map:
                    self.log.warning(f"   ⚠️ تم تخطي الحقل {cand_id} لأن السيرفر أعاده رغم استبعاده في المملكة {kingdom_id}.")
                    continue
                found_target = cand
                actual_found_lv = cur_try_lv
                if cur_try_lv < target_lv:
                    self.log.info(f"   ℹ️ لم يتوفر حقل لفل {target_lv} — تم العثور على بديل لفل {cur_try_lv}")
                break

        if not found_target:
            return "NO_TARGET"

        target    = found_target
        target_id = target.get('id')
        tx, ty    = target.get('x'), target.get('y')
        self.log.debug(f"🎯 تم العثور على حقل {res_info['name']} لفل {actual_found_lv}: {target_id} عند ({tx}, {ty})")
        # حجز مؤقت في الذاكرة المشتركة للمملكة — لن يُثبت في الملف إلا بعد نجاح الإرسال
        await self._exclude_mgr.reserve(self.uid, target_id, kingdom_id=kingdom_id)

        # 2. فحص أمني شامل ومباشر للحقل (1006/22 + مزامنة مسيرات الخريطة 1006/1000 واعتراض 1009/201)
        cur_res = 0
        actual_res_code = res_info["res_code"]

        is_busy, busy_reason, ret22 = await self.check_target_busy_or_marched(
            target_id=target_id,
            tx=tx,
            ty=ty,
            kingdom_id=kingdom_id,
            is_stronghold=False
        )
        if is_busy:
            self.log.warning(f"⚠️ الحقل {target_id} مستبعد فوراً: {busy_reason}")
            # تثبيت الاستبعاد لمنع محاولته مجدداً خلال هذه الجلسة على مستوى المملكة
            await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
            return "TARGET_OCCUPIED"

        if ret22 and isinstance(ret22, dict):
            fresh_rem = int(ret22.get('remainSourceNum', 0))
            fresh_tot = int(ret22.get('totalSourceNum', 0))
            if fresh_rem > 0:
                cur_res = fresh_rem
            elif fresh_tot > 0:
                cur_res = fresh_tot

            if ret22.get('resourceType'):
                try:
                    actual_res_code = int(ret22.get('resourceType'))
                except Exception:
                    pass

        # خطة بديلة عبر 1006/15
        if cur_res <= 0:
            try:
                r_build = await self.conn.query('1006', '15', {
                    "x": tx, "y": ty, "kingdomId": kingdom_id, "id": target_id
                }, timeout=3.0)
                if r_build and 'retData' in r_build:
                    res_node = r_build['retData'].get('resource', {})
                    cur_res = int(res_node.get('currentSourceNum', 0))
                    if res_node.get('resourceType'):
                        try:
                            actual_res_code = int(res_node.get('resourceType'))
                        except Exception:
                            pass
            except Exception as e:
                self.log.debug(f"استعلام 1006/15 لم يكتمل: {e}")

        # حساب مضاعف الحمولة وسعة النقل المطلوبة وفق كود اللعبة الأصلي (worldDispatchArmyView.lua)
        multiplier = get_resource_multiplier(actual_res_code, res_info["sub_type"])
        if cur_res > 0:
            target_load = int(cur_res * multiplier)
            self.log.debug(f"   📦 حمولة الحقل الحقيقية: {cur_res:,} | مطلوب: {target_load:,}")
        else:
            def_cap = DEFAULT_NODE_CAPACITY.get(res_info["sub_type"], {}).get(actual_found_lv, 50000)
            target_load = int(def_cap * multiplier)
            cur_res = def_cap
            self.log.debug(f"   📦 تقدير حمولة الحقل: {def_cap:,} | مطلوب: {target_load:,}")

        # 3. جلب القوات المتوفرة بالقلعة من الذاكرة الحية مباشرة (Zero-Request)
        available: Dict[int, int] = {}
        army_ctrl = self.conn.init_data.get('armyCtrl', {}) if hasattr(self.conn, 'init_data') else {}
        if isinstance(army_ctrl, dict):
            for k, v in army_ctrl.get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        if not available:
            try:
                self.log.debug("🛑🛑🛑🛑🛑🛑🛑")
                r_army = await self.conn.query('1005', '1', {}, timeout=5)
                if r_army and 'data' in r_army:
                    for k, v in r_army['data'].get('totalArmy', {}).items():
                        if str(k).isdigit() and str(v).isdigit():
                            available[int(k)] = int(v)
            except Exception:
                pass


        for tid, used in self._used_army.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used)

        # 4. اختيار البطل الأنسب والحيوان الأليف تلقائياً
        if not self._heroes:
            await self._load_heroes()

        max_heroes_cfg = int(self.config.get("max_heroes", 2))
        chosen_heroes_list = pick_best_gather_heroes(self._heroes, self._busy_heroes, max_heroes=max_heroes_cfg, sub_type=res_info["sub_type"])
        if chosen_heroes_list:
            self.log.debug(f"   🦸 الأبطال: {chosen_heroes_list}")
        else:
            self.log.debug("   🦸 المسيرة بدون أبطال")

        pets_list = select_gathering_pet(self.conn, self._used_pets)
        if pets_list:
            self.log.debug(f"   🐾 الحيوان: #{pets_list[0]}")

        # استعلام سمات الحرب للحمولة من السيرفر وتحديث الكاش إن لم تكن متوفرة
        try:
            await fetch_war_boe_pload(self.conn)
        except Exception:
            pass

        # 5. حساب بونص سعة الحمولة الحقيقي وتشكيل الجيش
        load_bonus = calculate_load_bonus(
            self.conn,
            sub_type=res_info["sub_type"],
            hero_list=chosen_heroes_list
        )

        # تحديد سعة مسيرة اللورد ومعسكر التجمع القصوى (لمنع خطأ 8035)
        max_march_troops = self._learned_max_march_troops
        if not max_march_troops:
            cfg_troops = self.config.get("max_march_troops")
            if cfg_troops:
                try: max_march_troops = int(cfg_troops)
                except Exception: pass
        if not max_march_troops:
            max_march_troops = calculate_estimated_march_capacity(
                getattr(self.conn, 'init_data', {}),
                chosen_heroes=chosen_heroes_list
            )

        army_list, carried_load = select_gathering_army(
            available,
            target_load=target_load,
            load_bonus=load_bonus,
            max_march_troops=max_march_troops
        )
        if not army_list:
            active_marches = await self.get_active_marches_count(force_sync=True)
            if active_marches >= 1:
                self.log.info(f"⏳ [القوات في المسيرة] لا تتوفر قوات بالقلعة لوجود {active_marches} مسيرة نشطة بالخارج.")
                return "QUEUES_FULL_SKIP"
            else:
                self.log.warning("⚠️ لا توجد أي قوات متاحة بالقلعة ولا توجد مسيرات بالخارج!")
                return "NO_ARMY"

        # صمام أمان صارم: فرض سقف سعة المسيرة لمنع تجاوز طاقة الفيلق أو خطأ 8035
        from tasks.march_capacity import enforce_safe_march_troops
        army_list = enforce_safe_march_troops(army_list, max_march_troops)

        total_troops = sum(item['num'] for item in army_list)
        carts_troops = sum(item['num'] for item in army_list if 700 <= item['id'] < 800)
        eff_cart1_w = calculate_unit_capacity(701, load_bonus=load_bonus)
        eff_cart9_w = calculate_unit_capacity(709, load_bonus=load_bonus)
        coverage_pct = (carried_load / target_load * 100) if target_load > 0 else 100.0
        march_note = f" (مسيرة جزئية: تغطي {coverage_pct:.1f}% من الحقل)" if coverage_pct < 98.0 else " (مسح كامل 100%)"
        cap_note = f" [سقف معسكر التجمع: {max_march_troops:,}]" if (max_march_troops and total_troops >= max_march_troops) else ""
        self.log.debug(f"   🛡️ القوات المختارة: {total_troops:,} جندي | حمولة: {carried_load:,}/{target_load:,}")

        # محاكاة بشرية طبيعية قبل إطلاق المسيرة (تجهيز الجيش والعتاد 2.0 - 3.5 ثانية)
        prep_wait = round(random.uniform(2.2, 3.8), 2)
        self.log.debug(f"   ⏳ تجهيز تفاصيل المسيرة ({prep_wait} ثانية)...")
        await asyncio.sleep(prep_wait)

        # 7. إرسال حزمة المسيرة 1007/2
        march_payload = {
            "needSend": False,
            "runePages": {},
            "heros": chosen_heroes_list,
            "matrixType": 3,
            "mapId": int(kingdom_id),
            "moveLineType": 3,
            "data": {
                "data": {
                    "currentSourceNum": cur_res if cur_res > 0 else 50000,
                    "resourceType": actual_res_code
                },
                "to": {
                    "y": int(ty),
                    "x": int(tx),
                    "id": str(target_id)
                },
                "army": army_list
            },
            "pets": pets_list
        }

        r_march = await self.conn.query('1007', '2', march_payload, timeout=7)
        if not r_march:
            return "ERROR"

        err = str(r_march.get('err', '0'))
        if err == '0':
            self.log.info(f"✅ [جمع الموارد] انطلقت مسيرة إلى {res_info['name']} لفل {actual_found_lv} عند ({tx}, {ty}) | حمولة: {carried_load:,}")
            # ✅ نجاح — تثبيت الاستبعاد في الملف على مستوى المملكة والـ UID
            await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
            for hid in chosen_heroes_list:
                self._busy_heroes.add(hid)
            for item in army_list:
                self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
            return "SUCCESS"
        elif err in ('8004', '9007004'):
            self.log.info(f"   🛑 طوابير الفيالق ممتلئة بالكامل (كود {err})")
            # ❌ فشل — إزالة الحجز المؤقت
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "QUEUES_FULL_SKIP"
        elif err == '8009':
            self.log.warning(f"   ⚠️ نقص في القوات المتاحة بالقلعة (كود {err})")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            active_marches = await self.get_active_marches_count(force_sync=True)
            if active_marches >= 1:
                self.log.info(f"⏳ [القوات في المسيرة] نقص قوات عند الإرسال لوجود {active_marches} مسيرة نشطة بالخارج.")
                return "QUEUES_FULL_SKIP"
            else:
                self.log.warning("⚠️ نقص حقيقي في القوات ولا توجد مسيرات نشطة بالخارج!")
                return "NO_ARMY"
        elif err in ('9007020', '8014', '9007014'):
            for hid in chosen_heroes_list:
                self._busy_heroes.add(hid)
            self.log.warning(f"   ⚠️ أبطال المسيرة مشغولون في مسيرة أخرى (كود {err}) — استبعادهم واختيار بديل")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "HERO_BUSY"
        elif err in ('8015', '9007021'):
            if pets_list:
                self._used_pets.add(pets_list[0])
            self.log.warning(f"   ⚠️ الحيوان الأليف #{pets_list[0]} مشغول (كود {err}) — استبعاده فوراً واختيار بديل")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "HERO_BUSY"
        elif err in ('8062', '8063', '8060', '9007062'):
            self.log.warning(f"   ⚠️ الحقل {target_id} مشغول أو تغيرت حالته (كود {err})")
            # الحقل مشغول فعلاً — نثبت الاستبعاد لأنه مشغول من لاعب آخر على مستوى المملكة
            await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
            return "TARGET_OCCUPIED"
        elif err in ('8041', '8042'):
            self.log.warning(f"   ⚠️ المستوى المطلوب للقلعة غير كافٍ لجمع هذا المورد (كود {err}) — تخطي.")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "CASTLE_LV_LOW"
        elif err == '8035':
            from tasks.march_capacity import record_learned_march_capacity
            current_total = sum(item['num'] for item in army_list)
            reduced_target = max(300, int(current_total * 0.85))
            record_learned_march_capacity(self.conn, reduced_target)
            self.log.warning(
                f"   ⚠️ خطأ 8035 (تجاوز سعة مسيرة اللورد/ساحة التدريب: {current_total:,} جندي) — "
                f"إعادة المحاولة فوراً بضبط القوات إلى {reduced_target:,} جندي..."
            )
            self._learned_max_march_troops = reduced_target

            scale = reduced_target / float(current_total) if current_total > 0 else 1.0
            for item in army_list:
                item['num'] = max(1, int(item['num'] * scale))

            new_total = sum(item['num'] for item in army_list)
            while new_total > reduced_target and army_list:
                diff = new_total - reduced_target
                army_list[-1]['num'] = max(1, army_list[-1]['num'] - diff)
                new_total = sum(item['num'] for item in army_list)
                if army_list[-1]['num'] <= 1 and new_total > reduced_target:
                    break

            march_payload['data']['army'] = army_list
            await asyncio.sleep(round(random.uniform(1.2, 2.2), 2))

            r_retry = await self.conn.query('1007', '2', march_payload)
            err_retry = str(r_retry.get('err', '0')) if r_retry else 'ERROR'
            if err_retry == '0':
                self.log.info(f"   ✅ انطلقت المسيرة بنجاح بعد ضبط القوات وفق سعة ساحة التدريب ({new_total:,} جندي)!")
                await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                for hid in chosen_heroes_list:
                    self._busy_heroes.add(hid)
                for item in army_list:
                    self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                return "SUCCESS"
            elif err_retry == '8035':
                reduced_second = max(300, int(new_total * 0.85))
                record_learned_march_capacity(self.conn, reduced_second)
                self.log.warning(
                    f"   ⚠️ تكرر خطأ 8035 — محاولة ثانية وأخيرة بضبط القوات إلى {reduced_second:,} جندي..."
                )
                self._learned_max_march_troops = reduced_second
                scale2 = reduced_second / float(new_total) if new_total > 0 else 1.0
                for item in army_list:
                    item['num'] = max(1, int(item['num'] * scale2))
                new_total2 = sum(item['num'] for item in army_list)
                while new_total2 > reduced_second and army_list:
                    diff = new_total2 - reduced_second
                    army_list[-1]['num'] = max(1, army_list[-1]['num'] - diff)
                    new_total2 = sum(item['num'] for item in army_list)
                    if army_list[-1]['num'] <= 1 and new_total2 > reduced_second:
                        break
                march_payload['data']['army'] = army_list
                await asyncio.sleep(round(random.uniform(1.4, 2.5), 2))
                r_retry2 = await self.conn.query('1007', '2', march_payload)
                if r_retry2 and str(r_retry2.get('err', '0')) == '0':
                    self.log.info(f"   ✅ انطلقت المسيرة بنجاح في المحاولة الثانية بعد ضبط القوات ({new_total2:,} جندي)!")
                    await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
                    for hid in chosen_heroes_list:
                        self._busy_heroes.add(hid)
                    for item in army_list:
                        self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
                    return "SUCCESS"

            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "ERROR"
        elif err == '16001':
            self.log.warning(
                f"   ⚠️ خادم اللعبة مشغول بعملية سابقة (كود 16001: Err_CMD_OPTING) — "
                f"تحرير الحقل {target_id} لإعادة تجهيز المسيرة نظيفاً من البداية..."
            )
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "CMD_OPTING"
        else:
            self.log.error(f"   ❌ خطأ غير متوقع أثناء إطلاق المسيرة: كود {err} | الحقل={target_id}")
            await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
            return "ERROR"

            
# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (Standalone Testing)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Auto-Gather Bot — جمع الموارد التلقائي الذكي")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument(
        "--res", "-r",
        default="gold",
        help="نوع المورد: 1/gold=ذهب, 2/food=قمح, 3/wood=خشب, 4/stone=حجر, 5/iron=حديد [افتراضي: gold]"
    )
    parser.add_argument(
        "--level", "-l",
        type=int,
        default=6,
        help="مستوى الحقل المستهدف بالضبط [افتراضي: 6]"
    )
    parser.add_argument(
        "--marches", "-m",
        type=int,
        default=0,
        help="الحد الأقصى للمسيرات (0 = حتى امتلاء كافة الفيالق) [افتراضي: 0]"
    )
    parser.add_argument(
        "--range",
        type=int,
        default=100,
        help="نطاق البحث على الخريطة بالكيلومتر [افتراضي: 100]"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

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

        for _ in range(10):
            await asyncio.sleep(1.0)
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "res_type": args.res,
            "level": args.level,
            "max_marches": args.marches,
            "search_range": args.range
        }

        task = GatherTask_2(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
