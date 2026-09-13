# -*- coding: utf-8 -*-
"""
tasks/gather.py — مهمة جمع الموارد الذكية التلقائية (Dynamic Auto-Gathering)
═════════════════════════════════════════════════════════════════════════════
python tasks/gather.py --email "sumo-1234@hotmil.com" --res 2 --level 2

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
  - 4 أو stone أو حجر → مناجم الحجر/الفضة       [subType = 4]
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

# ── ملف تاريخ الاستبعاد ──────────────────────────────────────────
HISTORY_FILE = os.path.join(_ROOT_DIR, "exclude_history.json")


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

    # 🪙 5. مناجم الفضة / ميثريل (Silver / Mithril) — كود الخريطة: 5 | كود المورد: 1005 | مضاعف الوزن: 24.0
    5:         {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "5":       {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "silver":  {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "فضة":     {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "الفضة":   {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "mithril": {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "ميثريل":  {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "stone":   {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "حجر":     {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
    "الحجر":   {"sub_type": 5, "name": "مناجم الفضة (Silver)", "icon": "🪙", "res_code": 1005, "multiplier": 24.0},
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


# معدل حمولة الموارد لكل جندي حسب الصنف (Load Rates)
UNIT_LOAD_RATES: Dict[int, int] = {
    7: 35,  # عربات الحصار والنقل (أعلى حمولة لجمع الموارد)
    4: 15,  # مشاة
    5: 12,  # فرسان
    6: 14,  # رماة
}


# ════════════════════════════════════════════════════════════════════
#  إدارة استبعاد الأهداف المكررة
# ════════════════════════════════════════════════════════════════════

def _get_exclude(uid: Any) -> Dict[str, bool]:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {str(i): True for i in data.get(str(uid), [])}
    except Exception:
        return {}


def _add_exclude(uid: Any, target_id: Any):
    data: dict = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

    key = str(uid)
    arr = data.setdefault(key, [])
    t   = str(target_id)
    if t not in arr:
        arr.append(t)
    while len(arr) > 20:
        arr.pop(0)
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الجمع التلقائي (محاكاة واجهة اللعبة)
# ════════════════════════════════════════════════════════════════════

def _score_gather_hero(hero: dict) -> Tuple[int, int, int]:
    """
    تقييم البطل لاختيار الأنسب لجمع الموارد:
    - Tier 3: بطل تنمية وجمع (5502) يمتلك مهارات جمع (5620)
    - Tier 2: بطل تنمية وجمع (5502) آخر
    - Tier 1: أي بطل حربي متاح بالقلعة (5501)
    - المفاضلة الإضافية: النجوم ثم المستوى
    """
    hid = str(hero.get('id', ''))
    skills = hero.get('skillList', {})
    has_gather_skill = False
    if isinstance(skills, dict):
        has_gather_skill = any(
            str(s.get('id', '')).startswith('5620')
            for s in skills.values() if isinstance(s, dict)
        )

    tier = 0
    if hid.startswith('5502'):
        tier = 3 if has_gather_skill else 2
    elif hid.startswith('5501'):
        tier = 1

    level = int(hero.get('level') or hero.get('lv') or 1)
    star = int(hero.get('star') or 0)
    return (tier, star, level)


def pick_best_gather_hero(heroes: list, busy: Set[int]) -> Optional[int]:
    """
    اختيار أفضل بطل جمع متاح في القلعة وغير مشغول:
    1. أبطال الجمع والتنمية (5502) ذوو مهارات الجمع بالأعلى نجوماً ومستوى.
    2. أبطال التنمية الآخرون.
    3. الأبطال الحربيون الاحتياطيون.
    4. يعيد None عند انشغال كافة الأبطال للسماح بإرسال المسيرة بدون بطل.
    """
    available_heroes = []
    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or int(hid) in busy:
            continue
        # التأكد أن البطل موجود بالقلعة وليس في مسيرة
        if hero.get('status', {}).get('state', 0) != 0:
            continue
        available_heroes.append(hero)

    if not available_heroes:
        return None

    # ترتيب الأبطال حسب كفاءة الجمع
    available_heroes.sort(key=_score_gather_hero, reverse=True)
    chosen_id = int(available_heroes[0]['id'])
    return chosen_id


# ════════════════════════════════════════════════════════════════════
#  مضاعفات أوزان الموارد المستخرجة من كود اللعبة الأصلي (worldDispatchArmyView.lua)
# ════════════════════════════════════════════════════════════════════

RESOURCE_WEIGHT_MULTIPLIERS: Dict[int, float] = {
    1001: 1000.0,  # الذهب (Gold): كل 1 ذهب يعادل 1000 حمولة
    1002: 1.0,     # القمح (Food): 1.0
    1003: 1.0,     # الخشب (Wood): 1.0
    1004: 6.0,     # الحديد (Iron): 6.0
    1005: 24.0,    # الفضة / ميثريل (Silver/Mithril): 24.0
}

# سعات الحقول الافتراضية لكل مستوى في حال لم يُرجع السيرفر currentSourceNum
DEFAULT_NODE_CAPACITY: Dict[int, Dict[int, int]] = {
    1: {1: 15, 2: 30, 3: 45, 4: 60, 5: 75, 6: 90, 7: 110, 8: 130},              # الذهب
    2: {1: 50000, 2: 100000, 3: 180000, 4: 400000, 5: 800000, 6: 1200000, 7: 1800000, 8: 2500000}, # القمح
    3: {1: 50000, 2: 100000, 3: 180000, 4: 400000, 5: 800000, 6: 1200000, 7: 1800000, 8: 2500000}, # الخشب
    4: {1: 5000, 2: 10000, 3: 18000, 4: 30000, 5: 50000, 6: 80000, 7: 120000, 8: 180000},          # الحديد
    5: {1: 1500, 2: 3000, 3: 5000, 4: 8000, 5: 12000, 6: 20000, 7: 30000, 8: 45000},               # الفضة
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
    # عربات نقل القمح (Grain Carts / Rams) — الأرقام الفردية حصراً
    701: 20,  # عربة نقل قمح لفل 1
    703: 21,  # عربة نقل قمح لفل 2
    705: 22,  # عربة نقل قمح لفل 3
    707: 27,  # عربة نقل قمح لفل 4
    709: 28,  # عربة نقل قمح لفل 5
    711: 30,  # عربة نقل قمح لفل 6
    713: 32,  # عربة نقل قمح لفل 7
    # المشاة (Fallback فقط إذا نفدت عربات نقل القمح بالكامل)
    412: 13, 411: 13, 410: 12, 409: 12, 408: 11, 407: 11, 406: 10, 405: 10, 404: 9, 403: 9, 402: 8, 401: 8,
    # الفرسان (Fallback)
    512: 11, 511: 11, 510: 10, 509: 10, 508: 9, 507: 9, 506: 8, 505: 8, 504: 7, 503: 7, 502: 6, 501: 6,
    # الرماة (Fallback)
    612: 13, 611: 12, 610: 12, 609: 11, 608: 11, 607: 10, 606: 10, 605: 9, 604: 9, 603: 8, 602: 8, 601: 7,
}


def calculate_load_bonus(
    conn: GameConnection,
    sub_type: int = 1,
    has_gather_hero: bool = False
) -> float:
    """
    حساب بونص سعة حمولة القوات (Army Weight Plus) وفق هندسة كود اللعبة الأصلي (kingdomMapCtrl:getArmyWeightPlus):
    1. أبحاث المعهد (Force Load 1, 2, 3) من technologyCtrl:
       - 21007: سعة الحمولة 1 (0.05 لكل مستوى)
       - 24006: سعة الحمولة 2 (0.07 لكل مستوى)
       - 24106: سعة الحمولة 3 (0.075 لكل مستوى)
    2. مهارات الأمير (Lord Info Development Skill Force Load): +20.045%
    3. بونص بطل الجمع لموارد القمح والخشب: +17.365%
    
    النتيجة الدقيقة المطابقة للعبة 100%:
    - للذهب (Gold lv 5: 75 ذهب = 75,000 حمولة): سعة عربة 701 = 59.009 -> 1,271 عربة نقل قمح تماماً!
    - للقمح (Food lv 5: 800,000 حمولة مع بطل جمع): سعة عربة 701 = 62.482 -> 12,804 عربة نقل قمح تماماً!
    """
    tech_data = getattr(conn, "init_data", {}).get('technologyCtrl', {})
    tech_bonus = 0.0

    if '21007' in tech_data:
        v = tech_data['21007']
        lv = int(v[1]) if isinstance(v, list) and len(v) > 1 else int(v)
        tech_bonus += lv * 0.05
    else:
        tech_bonus += 0.30  # افتراضي مستوى 6 (30%)

    if '24006' in tech_data:
        v = tech_data['24006']
        lv = int(v[1]) if isinstance(v, list) and len(v) > 1 else int(v)
        tech_bonus += lv * 0.07
    else:
        tech_bonus += 0.70  # افتراضي مستوى 10 (70%)

    if '24106' in tech_data:
        v = tech_data['24106']
        lv = int(v[1]) if isinstance(v, list) and len(v) > 1 else int(v)
        tech_bonus += lv * 0.075
    else:
        tech_bonus += 0.75  # افتراضي مستوى 10 (75%)

    # مهارات الأمير والصفات الدائمة (Lord Skill Force Load)
    lord_bonus = 0.20045

    base_bonus = tech_bonus + lord_bonus
    if base_bonus < 0.1:
        base_bonus = 1.95045

    hero_bonus = 0.0
    # عند جمع القمح أو الخشب مع بطل جمع متاح
    if has_gather_hero and sub_type in (2, 3):
        hero_bonus = 0.17365

    return base_bonus + hero_bonus


# ════════════════════════════════════════════════════════════════════
#  اختيار تشكيلة الجيش التلقائية (محاكاة واجهة اللعبة الحقيقية 100%)
# ════════════════════════════════════════════════════════════════════

def select_gathering_army(
    available: Dict[int, int],
    target_load: int,
    load_bonus: float = 0.0
) -> Tuple[List[Dict[str, int]], int]:
    """
    اختيار تشكيلة الجيش تلقائياً لجمع الموارد وفق كود اللعبة الأصلي (worldDispatchArmyView.lua):
    1. استبعاد كامل لعربات الهجوم (الأرقام الزوجية 702, 704, 706, 708, 710, 712, 714).
    2. استبعاد كامل لأسلحة وفخاخ الجدار (800 فما فوق).
    3. الأولوية لعربات نقل القمح (Grain Carts):
       - 701 (عربة نقل القمح لفل 1) أولاً كما في واجهة اللعبة تماماً (حيث يبدأ كود sortArmyListByWeight بـ: if armyID1 == 701 then return true).
       - ثم باقي عربات نقل القمح (الأرقام الفردية 713, 711, 709, 707, 705, 703) بالأعلى حمولة.
    4. حساب عدد الجنود المطلوب بدقة لمطابقة حمولة الحقل الهدف مع تطبيق بونص سعة الحمولة الكلي:
       unit_weight = base_weight * (1.0 + load_bonus)
       needed = min(avail, math.ceil(rem_load / unit_weight))
    5. استكمال العجز (فقط عند نفاد عربات نقل القمح) من المشاة ثم الفرسان ثم الرماة.
    """
    # 1. تجميع عربات نقل القمح المتاحة (الأرقام الفردية حصراً)
    grain_carts: List[int] = []
    for tid in available.keys():
        if 700 <= tid < 800 and tid % 2 == 1:
            grain_carts.append(tid)

    # الترتيب المطابق لكود اللعبة: 701 أولاً، ثم باقي الرتب من الأعلى للأدنى
    grain_carts.sort(key=lambda tid: (0 if tid == 701 else 1, -UNIT_FREE_WEIGHTS.get(tid, 20), -tid))

    # باقي القوات كـ fallback فقط عند نفاد عربات القمح (مشاة ثم فرسان ثم رماة)
    infantry = sorted([tid for tid in available if 400 <= tid < 500], key=lambda tid: -tid)
    cavalry  = sorted([tid for tid in available if 500 <= tid < 600], key=lambda tid: -tid)
    archers  = sorted([tid for tid in available if 600 <= tid < 700], key=lambda tid: -tid)

    ordered_tids = grain_carts + infantry + cavalry + archers

    rem_load = float(max(1, target_load))
    total_carried = 0.0
    army_list: List[Dict[str, int]] = []

    for tid in ordered_tids:
        avail = available.get(tid, 0)
        if avail <= 0:
            continue

        base_w = float(UNIT_FREE_WEIGHTS.get(tid, 10))
        unit_weight = base_w * (1.0 + load_bonus)
        needed = min(avail, math.ceil(rem_load / unit_weight))
        if needed > 0:
            army_list.append({"id": tid, "num": needed})
            available[tid] -= needed
            load_added = needed * unit_weight
            rem_load = max(0.0, rem_load - load_added)
            total_carried += load_added
            if rem_load <= 0:
                break

    # في حال لم تكن القوات كافية لتغطية الحقل بالكامل، نأخذ المتاح
    if not army_list:
        for tid in ordered_tids:
            avail = available.get(tid, 0)
            if avail > 0:
                base_w = float(UNIT_FREE_WEIGHTS.get(tid, 10))
                unit_weight = base_w * (1.0 + load_bonus)
                army_list.append({"id": tid, "num": avail})
                available[tid] = 0
                total_carried += avail * unit_weight

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

class GatherTask(BaseTask):
    """
    مهمة جمع الموارد الذكية التلقائية:
      - مورد واحد ومستوى محدد من المستخدم
      - دعم الذهب (subType = 1) وباقي الموارد
      - اختيار تلقائي للجيش (عربات النقل أولاً)
      - اختيار تلقائي للأبطال والحيوانات
      - إرسال المسيرات حتى امتلاء كافة الفيالق (QUEUE_FULL)
    """
    name = "gather"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self._heroes       : list          = []
        self._busy_heroes  : Set[int]      = set()
        self._used_army    : Dict[int, int] = {}
        self._used_pets    : Set[int]      = set()
        self._excluded_now : Set[str]      = set()

    async def on_start(self):
        for _ in range(20):
            if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
                break
            if self.conn.init_data:
                break
            await asyncio.sleep(0.5)
        await self._load_heroes()

    async def _load_heroes(self):
        """جلب بيانات أبطال الحساب."""
        self._heroes = []
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. من الـ Gate مباشرة (init_data)
        if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
            self._heroes = list(self.conn._gate.heroes)
            if self._heroes:
                self.log.info(f"📋 تم جلب {len(self._heroes)} بطل من بيانات الجلسة")
                return

        # 2. من init_data heroCtrl
        hctrl = self.conn.init_data.get('heroCtrl')
        if isinstance(hctrl, list) and hctrl:
            self._heroes = list(hctrl)
            return
        elif isinstance(hctrl, dict) and hctrl:
            hlist = hctrl.get('heroList', hctrl)
            if isinstance(hlist, dict):
                self._heroes = list(hlist.values())
            elif isinstance(hlist, list):
                self._heroes = list(hlist)
            if self._heroes:
                return

        # 3. محاولة استعلام 1000/1
        if self.conn._gate and self.conn._gate._writer and self.conn._gate.is_connected:
            try:
                from onemt_bot import pack_request
                self.conn._gate._writer.write(pack_request('1000', '1', {}, session=0))
                await self.conn._gate._writer.drain()
                for _ in range(8):
                    await asyncio.sleep(0.2)
                    if self.conn._gate.heroes:
                        self._heroes = list(self.conn._gate.heroes)
                        return
            except Exception:
                pass

        # 4. خطة احتياطية عبر 3080/2
        try:
            r_3080 = await self.conn.query('3080', '2', {'isSelf': True, 'uids': [uid_int]}, timeout=3)
            if r_3080 and 'data' in r_3080:
                list_data = r_3080['data'].get('list', {}).get(str(uid_int), {})
                pages = list_data.get('pages', {})
                if isinstance(pages, dict):
                    for page in pages.values():
                        if isinstance(page, dict):
                            for h_obj in page.get('heros', []):
                                hid = h_obj.get('id') if isinstance(h_obj, dict) else h_obj
                                if hid and not any(h.get('id') == hid for h in self._heroes):
                                    self._heroes.append({'id': int(hid), 'status': {'state': 0}, 'skillList': {}})
        except Exception:
            pass

    # ── المهمة الرئيسية: الإرسال حتى امتلاء كافة الفيالق ──────────

    async def run(self) -> TaskResult:
        """إرسال مسيرات متتالية حتى امتلاء جميع طوابير الفيالق المتاحة."""
        cfg = self.config or {}

        # 1. استخراج نوع المورد المستهدف (مورد واحد فقط)
        res_key = cfg.get('res_type') or cfg.get('res') or cfg.get('resource') or 1
        res_info = resolve_resource(res_key)

        # 2. استخراج مستوى الحقل المستهدف (مستوى واحد فقط)
        target_lv = int(cfg.get('level') or cfg.get('lv') or cfg.get('min_lv') or 6)

        search_range = int(cfg.get('search_range', 100))
        max_marches_safety = int(cfg.get('max_marches') or 10)  # سقف أمان أقصى

        self.log.info("🌾" + "═" * 58)
        self.log.info(f"🌾 بدء مهمة جمع الموارد الذكية التلقائية:")
        self.log.info(f"   • المورد المستهدف : {res_info['icon']} {res_info['name']} (subType = {res_info['sub_type']})")
        self.log.info(f"   • مستوى الحقل     : المستوى {target_lv}")
        self.log.info(f"   • أولوية الجيش    : 🚜 عربات النقل والحصار أولاً (أفضل حمولة)")
        self.log.info(f"   • استراتيجية الحشد: 🏹 إرسال المسيرات متتالية حتى امتلاء كافة الفيالق")
        self.log.info("🌾" + "═" * 58)

        if not self._heroes:
            await self._load_heroes()

        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 3. جلب إحداثيات القلعة ومعرف المملكة مرة واحدة
        r_castle = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=6)
        if not r_castle or not r_castle.get('retData'):
            return TaskResult.fail("فشل في استعلام إحداثيات القلعة على الخريطة")

        cx = r_castle['retData'].get('x')
        cy = r_castle['retData'].get('y')
        self.log.info(f"📍 موقع القلعة: ({cx}, {cy})")

        kingdom_id = 0
        if self.conn.kingdom_id:
            try: kingdom_id = int(self.conn.kingdom_id)
            except: pass
        if not kingdom_id:
            r_map = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=4)
            if r_map and 'data' in r_map:
                kingdom_id = r_map['data'].get('base', {}).get('partition', 0)

        sent_count = 0
        consecutive_errors = 0
        self._busy_heroes  = set()
        self._used_army    = {}
        self._used_pets    = set()
        self._excluded_now = set()

        march_idx = 0
        while march_idx < max_marches_safety:
            march_idx += 1
            self.log.info(f"🏹 محاولة إرسال مسيرة الفيلق رقم ({march_idx})...")

            status = await self._send_one_march(
                res_info=res_info,
                target_lv=target_lv,
                cx=cx,
                cy=cy,
                kingdom_id=kingdom_id,
                search_range=search_range
            )

            if status == "SUCCESS":
                sent_count += 1
                consecutive_errors = 0
                # مهلة أمان مدمجة في الكود بين إطلاق المسيرات لمكافحة الحظر وتشتيت النمط
                wait_time = round(random.uniform(9.0, 14.0), 2)
                self.log.info(f"⏳ [حماية ومكافحة حظر] مهلة أمان قبل إطلاق الفيلق التالي ({wait_time} ثانية)...")
                await asyncio.sleep(wait_time)
            elif status in ("QUEUE_FULL", "8004", "9007004"):
                self.log.info("🏁 اكتملت جميع الفيالق وطوابير المسيرات للقلعة (طوابير ممتلئة بالكامل).")
                break
            elif status in ("NO_ARMY", "8009"):
                self.log.info("🏁 نفدت القوات المتاحة بالقلعة لإرسال فيالق إضافية.")
                break
            elif status == "NO_TARGET":
                self.log.warning(f"⚠️ لم يتم العثور على حقول {res_info['name']} من مستوى {target_lv} حتى مستوى 2 في نطاق {search_range} كم — إغلاق المهمة.")
                break
            elif status in ("HERO_BUSY", "TARGET_OCCUPIED"):
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    self.log.warning("⚠️ 3 أخطاء متتالية أثناء تجهيز المسيرات — إنهاء الدورة.")
                    break
                await asyncio.sleep(2.0)
            else:
                consecutive_errors += 1
                if consecutive_errors >= 2:
                    break

        self.log.info("═" * 60)
        self.log.info(f"🏁 النتيجة النهائية: تم إرسال {sent_count} مسيرة جمع بنجاح!")
        self.log.info("═" * 60)

        if sent_count > 0:
            return TaskResult.ok(f"✅ تم إرسال {sent_count} مسيرة جمع ({res_info['name']})", sent=sent_count)
        return TaskResult.fail("لم يتم إرسال أي مسيرة جمع", retry_after=120)

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
        exclude_map = _get_exclude(self.uid)
        for tid in self._excluded_now:
            exclude_map[tid] = True

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
                "range": search_range
            }, timeout=6)

            if r_search and r_search.get('result'):
                found_target = r_search['result'][0]
                actual_found_lv = cur_try_lv
                if cur_try_lv < target_lv:
                    self.log.info(f"   ℹ️ لم يتوفر حقل لفل {target_lv} — تم العثور على بديل لفل {cur_try_lv}")
                break

        if not found_target:
            return "NO_TARGET"

        target    = found_target
        target_id = target.get('id')
        tx, ty    = target.get('x'), target.get('y')
        self.log.info(f"🎯 تم العثور على حقل {res_info['name']} لفل {actual_found_lv}: {target_id} عند ({tx}, {ty})")
        self._excluded_now.add(str(target_id))
        _add_exclude(self.uid, target_id)

        # 2. فحص حمولة الحقل الهدف ونوع المورد الفعلي (1006/15)
        cur_res = 0
        actual_res_code = res_info["res_code"]
        r_build = await self.conn.query('1006', '15', {
            "x": tx, "y": ty, "kingdomId": kingdom_id, "id": target_id
        }, timeout=5)

        if r_build and 'retData' in r_build:
            res_node = r_build['retData'].get('resource', {})
            cur_res = int(res_node.get('currentSourceNum', 0))
            if res_node.get('resourceType'):
                actual_res_code = int(res_node.get('resourceType'))

        # حساب مضاعف الحمولة وسعة النقل المطلوبة وفق كود اللعبة الأصلي (worldDispatchArmyView.lua)
        multiplier = get_resource_multiplier(actual_res_code, res_info["sub_type"])
        if cur_res > 0:
            target_load = int(cur_res * multiplier)
            self.log.info(f"   📦 حمولة الحقل: {cur_res:,} مورد × مضاعف وزن {multiplier:g} = سعة حمولة مطلوبة: {target_load:,}")
        else:
            def_cap = DEFAULT_NODE_CAPACITY.get(res_info["sub_type"], {}).get(actual_found_lv, 50000)
            target_load = int(def_cap * multiplier)
            cur_res = def_cap
            self.log.info(f"   📦 تقدير حمولة الحقل (لفل {actual_found_lv}): {def_cap:,} مورد × مضاعف {multiplier:g} = سعة حمولة: {target_load:,}")

        # 3. فحص القوات المتوفرة بالقلعة وخصم ما تم إرساله مسبقاً (1005/1)
        available: Dict[int, int] = {}
        r_army = await self.conn.query('1005', '1', {}, timeout=5)
        if r_army and 'data' in r_army:
            for k, v in r_army['data'].get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available[int(k)] = int(v)

        for tid, used in self._used_army.items():
            if tid in available:
                available[tid] = max(0, available[tid] - used)

        # 4. اختيار البطل الأنسب والحيوان الأليف تلقائياً
        if not self._heroes:
            await self._load_heroes()

        chosen_hero = pick_best_gather_hero(self._heroes, self._busy_heroes)
        chosen_heroes_list = [chosen_hero] if chosen_hero else []
        if chosen_hero:
            self.log.info(f"   🦸 البطل المختار تلقائياً: بطل #{chosen_hero}")
        else:
            self.log.info("   🦸 تم إرسال المسيرة بدون بطل (لاستغلال كافة الفيالق الشاغرة)")

        pets_list = select_gathering_pet(self.conn, self._used_pets)
        if pets_list:
            self.log.info(f"   🐾 الحيوان الأليف المختار: حيوان #{pets_list[0]}")

        # 5. حساب بونص سعة الحمولة الكلي وتشكيل الجيش بدقة مطابقة للعبة 100%
        has_gather_hero = bool(chosen_hero and str(chosen_hero).startswith("5502"))
        load_bonus = calculate_load_bonus(
            self.conn,
            sub_type=res_info["sub_type"],
            has_gather_hero=has_gather_hero
        )

        army_list, carried_load = select_gathering_army(
            available,
            target_load=target_load,
            load_bonus=load_bonus
        )
        if not army_list:
            self.log.warning("⚠️ لا توجد قوات كافية متوفرة بالقلعة لإرسال مسيرة!")
            return "NO_ARMY"

        total_troops = sum(item['num'] for item in army_list)
        carts_troops = sum(item['num'] for item in army_list if 700 <= item['id'] < 800 and item['id'] % 2 == 1)
        eff_cart_w = UNIT_FREE_WEIGHTS.get(701, 20) * (1.0 + load_bonus)
        self.log.info(f"   🛡️ القوات المختارة: {total_troops:,} جندي (منها {carts_troops:,} عربة نقل قمح) | سعة العربة: {eff_cart_w:.2f} (بونص +{load_bonus*100:.1f}%) | حمولة المسيرة: {carried_load:,} / مطلوب: {target_load:,}")

        # محاكاة بشرية طبيعية قبل إطلاق المسيرة (تجهيز الجيش والعتاد 2.0 - 3.5 ثانية)
        prep_wait = round(random.uniform(2.2, 3.8), 2)
        self.log.info(f"   ⏳ [محاكاة بشرية] تجهيز تفاصيل المسيرة ({prep_wait} ثانية)...")
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
            self.log.info(f"   ✅ انطلقت المسيرة بنجاح إلى الحقل {target_id}!")
            if chosen_hero:
                self._busy_heroes.add(chosen_hero)
            for item in army_list:
                self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']
            return "SUCCESS"
        elif err in ('8004', '9007004'):
            self.log.info(f"   🛑 طوابير الفيالق ممتلئة بالكامل (كود {err})")
            return "QUEUE_FULL"
        elif err == '8009':
            self.log.warning(f"   ⚠️ نقص في القوات المتاحة بالقلعة (كود {err})")
            return "NO_ARMY"
        elif err == '9007020':
            if chosen_hero:
                self._busy_heroes.add(chosen_hero)
            return "HERO_BUSY"
        elif err in ('8062', '8063', '8060', '9007062'):
            self.log.warning(f"   ⚠️ الحقل {target_id} مشغول أو تغيرت حالته (كود {err})")
            return "TARGET_OCCUPIED"
        else:
            self.log.error(f"   ❌ خطأ أثناء إطلاق المسيرة: {err} | الهدف={target_id}")
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

        task = GatherTask(conn, task_cfg)
        result = await task.run()
        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
