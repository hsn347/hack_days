# -*- coding: utf-8 -*-
"""
tasks/building.py — مهمة ترقية القلعة الذكية والمتسلسلة وصناديق الموارد وبناء المنشآت
══════════════════════════════════════════════════════════════════════════════════
تقوم هذه المهمة بإدارة وترقية مباني المدينة وترقية القلعة وفق نظام متقدم وذكي:
  1. ترقية القلعة (Castle 101) وحل شجرة المتطلبات المتداخلة (Recursive Cascade):
     - فحص ما إذا كانت القلعة قيد الترقية بالفعل.
     - فحص المتطلبات المسبقة للقلعة من ملفات اللعبة الرسمية (preCond).
     - إذا تطلب الأمر ترقية مبنى آخر (مثل الأسوار 102 أو المنشرة 202 أو المستودع 105):
       يتم فحص ذلك المبنى، وإذا كان المبنى نفسه يحتاج مبنى ثالثاً، يستمر التعقب
       بشكل متسلسل لترقية الأساس أولاً بأول.
  2. الاستعلام عن صناديق الموارد وفتحها تلقائياً عند وجود نقص:
     - فحص أرصدة الموارد الحالية في المدينة (القمح 1002، الخشب 1003، الحديد 1004، الكوارتز 1005).
     - عند وجود عجز، يتم الاستعلام عن الحقيبة (1004/1) لفحص الصناديق المتوفرة وأحجامها.
     - فتح الصناديق المطلوبة بدقة عبر (1004/2) لتغطية النقص فقط ومنع الهدر.
  3. بناء المباني المفقودة تلقائياً (Auto-Construction):
     - إذا كان أحد متطلبات القلعة أو لوازمها غير مبني أساساً (المستوى 0):
       يكتشف البوت الأراضي الشاغرة تلقائياً ويرسل أمر التشييد عبر (1001/2 mode: 3).
  4. تجاوز مانع وسام الحرب بذكاء (War Medal Shortage Fallback):
     - إذا كان المانع الوحيد لترقية القلعة هو نقص وسام الحرب (301101)، يتم تجاهل القلعة
       مؤقتاً والانتقال لترقية المباني الداعمة ولوازم البناء الأخرى لشغل الطوابير.
  5. ترقية المباني الداعمة والمعسكرات والمشافي بتوازن ذكي (الأقل مستوى دائماً).
  6. تسريع ترقية القلعة بالأدوات المجانية والحقيبة عند تفعيل خيار التسريع.
  7. الأمان المطلق: حظر تام وقطعي لاستخدام الذهب في أي عملية (ترقية أو بناء أو تسريع).

خيارات التشغيل:
    python tasks/building.py --email "10r228@g.com" --castle --speedup --buildings
    python tasks/building.py --email "x.abd3@gmail.com" --castle --speedup
 --buildings
    python tasks/building.py --email "king7moe1990@gmail.com" --check-only
    python tasks/building.py --all-accounts
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
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Set, Union

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  تعريفات المباني والموارد
# ════════════════════════════════════════════════════════════════════

BUILDING_INFO: Dict[str, Dict[str, Any]] = {
    "101": {"name": "🏰 القلعة (Castle)", "name_ar": "القلعة", "category": "castle", "harvest": False, "max_lv": 130},
    "102": {"name": "🧱 الأسوار (Walls)", "name_ar": "الأسوار", "category": "walls", "harvest": False, "max_lv": 130},
    "103": {"name": "🛡️ البرج الدفاعي (Turret)", "name_ar": "البرج الدفاعي", "category": "defense", "harvest": False, "max_lv": 130},
    "104": {"name": "🔭 برج المراقبة (Watchtower)", "name_ar": "برج المراقبة", "category": "watchtower", "harvest": False, "max_lv": 30},
    "105": {"name": "📦 المستودع (Depot)", "name_ar": "المستودع", "category": "depot", "harvest": False, "max_lv": 130},
    "107": {"name": "💰 التاجر (Merchant)", "name_ar": "التاجر", "category": "merchant", "harvest": False, "max_lv": 1},
    "108": {"name": "⚓ الميناء (Port)", "name_ar": "الميناء", "category": "port", "harvest": False, "max_lv": 1},
    "111": {"name": "🏛️ السفارة (Embassy)", "name_ar": "السفارة", "category": "embassy", "harvest": False, "max_lv": 130},
    "112": {"name": "⚖️ السوق (Market)", "name_ar": "السوق", "category": "market", "harvest": False, "max_lv": 30},
    "113": {"name": "🎓 المعهد / الأكاديمية (College)", "name_ar": "المعهد", "category": "college", "harvest": False, "max_lv": 130},
    "114": {"name": "⛲ نافورة الأمنيات (Wishing Well)", "name_ar": "نافورة الأمنيات", "category": "wishing", "harvest": False, "max_lv": 130},
    "115": {"name": "⚒️ الحداد (Blacksmith)", "name_ar": "الحداد", "category": "blacksmith", "harvest": False, "max_lv": 30},
    "116": {"name": "🐎 معسكر الخيالة (Cavalry Barracks)", "name_ar": "معسكر الخيالة", "category": "camp", "harvest": False, "max_lv": 130},
    "117": {"name": "🏹 معسكر الرماة (Archer Barracks)", "name_ar": "معسكر الرماة", "category": "camp", "harvest": False, "max_lv": 130},
    "118": {"name": "🛡️ معسكر المشاة (Infantry Barracks)", "name_ar": "معسكر المشاة", "category": "camp", "harvest": False, "max_lv": 130},
    "119": {"name": "🚜 معسكر العربات (Chariot Barracks)", "name_ar": "معسكر العربات", "category": "camp", "harvest": False, "max_lv": 130},
    "120": {"name": "🏰 الحصن (Fortress)", "name_ar": "الحصن", "category": "fortress", "harvest": False, "max_lv": 30},
    "121": {"name": "🎯 ساحة التدريب (Drill Grounds)", "name_ar": "ساحة التدريب", "category": "drill", "harvest": False, "max_lv": 130},
    "122": {"name": "⚔️ قاعة الحرب (Hall of War)", "name_ar": "قاعة الحرب", "category": "warhall", "harvest": False, "max_lv": 130},
    "201": {"name": "🌾 مزرعة القمح (Farm)", "name_ar": "مزرعة القمح", "category": "resource", "harvest": True, "max_lv": 130},
    "202": {"name": "🪵 منشرة الخشب (Sawmill)", "name_ar": "منشرة الخشب", "category": "resource", "harvest": True, "max_lv": 130},
    "203": {"name": "⛏️ منجم الحديد (Iron Mine)", "name_ar": "منجم الحديد", "category": "resource", "harvest": True, "max_lv": 130},
    "204": {"name": "🪙 منجم الكوارتز (Quartz Mine)", "name_ar": "منجم الكوارتز", "category": "resource", "harvest": True, "max_lv": 130},
    "205": {"name": "⛺ الخيمة العسكرية (Military Tent)", "name_ar": "الخيمة العسكرية", "category": "tent", "harvest": False, "max_lv": 130},
    "206": {"name": "🏥 المركز الطبي / المشفى (Hospital)", "name_ar": "المركز الطبي", "category": "hospital", "harvest": False, "max_lv": 130},
    "207": {"name": "💎 منجم الكريستال (Crystal Mine)", "name_ar": "منجم الكريستال", "category": "crystal", "harvest": True, "max_lv": 80},
    "301": {"name": "🎖️ هيبة السلطان (Sultan's Glory)", "name_ar": "هيبة السلطان", "category": "honor", "harvest": False, "max_lv": 101},
    "302": {"name": "👑 القصر النخبوي (Elite Palace)", "name_ar": "القصر النخبوي", "category": "elite", "harvest": False, "max_lv": 5},
}

RES_NAMES: Dict[int, str] = {
    1002: "🌾 القمح (Food)",
    1003: "🪵 الخشب (Wood)",
    1004: "⛏️ الحديد (Iron)",
    1005: "🪙 الكوارتز / الألماس (Quartz)",
}

# ════════════════════════════════════════════════════════════════════
#  المعجم الشامل لصناديق الموارد الـ 38 الرسمية في اللعبة
#  (مرتبة تنازلياً حسب القيمة لتطبيق خوارزمية Greedy Knapsack)
# ════════════════════════════════════════════════════════════════════

REGULAR_RESOURCE_CHESTS: Dict[int, List[Dict[str, Any]]] = {
    # 1003: الخشب (Wood) — تمنحه الصناديق 100201 - 100208
    1003: [
        {"item_id": 100208, "amount": 5000000, "name": "صندوق خشب 5M"},
        {"item_id": 100207, "amount": 1500000, "name": "صندوق خشب 1.5M"},
        {"item_id": 100206, "amount": 500000,  "name": "صندوق خشب 500K"},
        {"item_id": 100205, "amount": 150000,  "name": "صندوق خشب 150K"},
        {"item_id": 100204, "amount": 50000,   "name": "صندوق خشب 50K"},
        {"item_id": 100203, "amount": 30000,   "name": "صندوق خشب 30K"},
        {"item_id": 100202, "amount": 10000,   "name": "صندوق خشب 10K"},
        {"item_id": 100201, "amount": 1000,    "name": "صندوق خشب 1K"},
    ],
    # 1002: القمح (Food) — تمنحه الصناديق 100301 - 100308
    1002: [
        {"item_id": 100308, "amount": 5000000, "name": "صندوق قمح 5M"},
        {"item_id": 100307, "amount": 1500000, "name": "صندوق قمح 1.5M"},
        {"item_id": 100306, "amount": 500000,  "name": "صندوق قمح 500K"},
        {"item_id": 100305, "amount": 150000,  "name": "صندوق قمح 150K"},
        {"item_id": 100304, "amount": 50000,   "name": "صندوق قمح 50K"},
        {"item_id": 100303, "amount": 30000,   "name": "صندوق قمح 30K"},
        {"item_id": 100302, "amount": 10000,   "name": "صندوق قمح 10K"},
        {"item_id": 100301, "amount": 1000,    "name": "صندوق قمح 1K"},
    ],
    # 1004: الحديد (Iron) — تمنحه الصناديق 100501 - 100508
    1004: [
        {"item_id": 100508, "amount": 800000, "name": "صندوق حديد 800K"},
        {"item_id": 100507, "amount": 250000, "name": "صندوق حديد 250K"},
        {"item_id": 100506, "amount": 80000,  "name": "صندوق حديد 80K"},
        {"item_id": 100505, "amount": 25000,  "name": "صندوق حديد 25K"},
        {"item_id": 100504, "amount": 8000,   "name": "صندوق حديد 8K"},
        {"item_id": 100503, "amount": 5000,   "name": "صندوق حديد 5K"},
        {"item_id": 100502, "amount": 1600,   "name": "صندوق حديد 1.6K"},
        {"item_id": 100501, "amount": 150,    "name": "صندوق حديد 150"},
    ],
    # 1005: الكوارتز / الألماس (Quartz) — تمنحه الصناديق 100600 - 100608
    1005: [
        {"item_id": 100608, "amount": 200000, "name": "صندوق كوارتز 200K"},
        {"item_id": 100607, "amount": 62500,  "name": "صندوق كوارتز 62.5K"},
        {"item_id": 100606, "amount": 20000,  "name": "صندوق كوارتز 20K"},
        {"item_id": 100605, "amount": 6250,   "name": "صندوق كوارتز 6.25K"},
        {"item_id": 100604, "amount": 2000,   "name": "صندوق كوارتز 2K"},
        {"item_id": 100603, "amount": 400,    "name": "صندوق كوارتز 400"},
        {"item_id": 100602, "amount": 160,    "name": "صندوق كوارتز 160"},
        {"item_id": 100601, "amount": 80,     "name": "صندوق كوارتز 80"},
        {"item_id": 100600, "amount": 40,     "name": "صندوق كوارتز 40"},
    ],
}

# 2. صناديق الموارد الآمنة (Safe Resource Chests) — احتياطي ذكي يُستخدم فقط عند انعدام/نفاد الصناديق العادية
SAFE_RESOURCE_CHESTS: Dict[int, List[Dict[str, Any]]] = {
    # 1003: الخشب الآمن (110001 - 110008)
    1003: [
        {"item_id": 110006, "amount": 5000000, "name": "صندوق خشب 5M (آمن)"},
        {"item_id": 110005, "amount": 1500000, "name": "صندوق خشب 1.5M (آمن)"},
        {"item_id": 110004, "amount": 500000,  "name": "صندوق خشب 500K (آمن)"},
        {"item_id": 110003, "amount": 150000,  "name": "صندوق خشب 150K (آمن)"},
        {"item_id": 110002, "amount": 50000,   "name": "صندوق خشب 50K (آمن)"},
        {"item_id": 110008, "amount": 30000,   "name": "صندوق خشب 30K (آمن)"},
        {"item_id": 110001, "amount": 10000,   "name": "صندوق خشب 10K (آمن)"},
        {"item_id": 110007, "amount": 1000,    "name": "صندوق خشب 1K (آمن)"},
    ],
    # 1002: القمح الآمن (110101 - 110108)
    1002: [
        {"item_id": 110106, "amount": 5000000, "name": "صندوق قمح 5M (آمن)"},
        {"item_id": 110105, "amount": 1500000, "name": "صندوق قمح 1.5M (آمن)"},
        {"item_id": 110104, "amount": 500000,  "name": "صندوق قمح 500K (آمن)"},
        {"item_id": 110103, "amount": 150000,  "name": "صندوق قمح 150K (آمن)"},
        {"item_id": 110102, "amount": 50000,   "name": "صندوق قمح 50K (آمن)"},
        {"item_id": 110108, "amount": 30000,   "name": "صندوق قمح 30K (آمن)"},
        {"item_id": 110101, "amount": 10000,   "name": "صندوق قمح 10K (آمن)"},
        {"item_id": 110107, "amount": 1000,    "name": "صندوق قمح 1K (آمن)"},
    ],
    # 1004: الحديد الآمن (110201 - 110208)
    1004: [
        {"item_id": 110206, "amount": 800000, "name": "صندوق حديد 800K (آمن)"},
        {"item_id": 110205, "amount": 250000, "name": "صندوق حديد 250K (آمن)"},
        {"item_id": 110204, "amount": 80000,  "name": "صندوق حديد 80K (آمن)"},
        {"item_id": 110203, "amount": 25000,  "name": "صندوق حديد 25K (آمن)"},
        {"item_id": 110202, "amount": 8000,   "name": "صندوق حديد 8K (آمن)"},
        {"item_id": 110208, "amount": 5000,   "name": "صندوق حديد 5K (آمن)"},
        {"item_id": 110201, "amount": 1600,   "name": "صندوق حديد 1.6K (آمن)"},
        {"item_id": 110207, "amount": 150,    "name": "صندوق حديد 150 (آمن)"},
    ],
    # 1005: الكوارتز / الألماس الآمن (110301 - 110308)
    1005: [
        {"item_id": 110306, "amount": 200000, "name": "صندوق كوارتز 200K (آمن)"},
        {"item_id": 110305, "amount": 62500,  "name": "صندوق كوارتز 62.5K (آمن)"},
        {"item_id": 110304, "amount": 20000,  "name": "صندوق كوارتز 20K (آمن)"},
        {"item_id": 110303, "amount": 6250,   "name": "صندوق كوارتز 6.25K (آمن)"},
        {"item_id": 110302, "amount": 2000,   "name": "صندوق كوارتز 2K (آمن)"},
        {"item_id": 110301, "amount": 400,    "name": "صندوق كوارتز 400 (آمن)"},
        {"item_id": 110308, "amount": 80,     "name": "صندوق كوارتز 80 (آمن)"},
        {"item_id": 110307, "amount": 40,     "name": "صندوق كوارتز 40 (آمن)"},
    ],
}

# 3. صناديق الموارد الاختيارية (Optional Resource Chests) — احتياطي استراتيجي يُستخدم فقط عند انعدام/نفاد الصناديق العادية والآمنة
OPTIONAL_RESOURCE_CHESTS: Dict[int, List[Dict[str, Any]]] = {
    # 1003: الخشب (Wood) — group: 1
    1003: [
        {"item_id": 809605, "amount": 5000000, "name": "صندوق موارد اختياري 5M (م5)", "group": 1},
        {"item_id": 809604, "amount": 1500000, "name": "صندوق موارد اختياري 1.5M (م4)", "group": 1},
        {"item_id": 809603, "amount": 500000,  "name": "صندوق موارد اختياري 500K (م3)", "group": 1},
        {"item_id": 809602, "amount": 150000,  "name": "صندوق موارد اختياري 150K (م2)", "group": 1},
        {"item_id": 809601, "amount": 50000,   "name": "صندوق موارد اختياري 50K (م1)", "group": 1},
    ],
    # 1002: القمح (Food) — group: 2
    1002: [
        {"item_id": 809605, "amount": 5000000, "name": "صندوق موارد اختياري 5M (م5)", "group": 2},
        {"item_id": 809604, "amount": 1500000, "name": "صندوق موارد اختياري 1.5M (م4)", "group": 2},
        {"item_id": 809603, "amount": 500000,  "name": "صندوق موارد اختياري 500K (م3)", "group": 2},
        {"item_id": 809602, "amount": 150000,  "name": "صندوق موارد اختياري 150K (م2)", "group": 2},
        {"item_id": 809601, "amount": 50000,   "name": "صندوق موارد اختياري 50K (م1)", "group": 2},
    ],
    # 1004: الحديد (Iron) — group: 3
    1004: [
        {"item_id": 809605, "amount": 800000, "name": "صندوق موارد اختياري 800K (م5)", "group": 3},
        {"item_id": 809604, "amount": 250000, "name": "صندوق موارد اختياري 250K (م4)", "group": 3},
        {"item_id": 809603, "amount": 80000,  "name": "صندوق موارد اختياري 80K (م3)", "group": 3},
        {"item_id": 809602, "amount": 25000,  "name": "صندوق موارد اختياري 25K (م2)", "group": 3},
        {"item_id": 809601, "amount": 8000,   "name": "صندوق موارد اختياري 8K (م1)", "group": 3},
    ],
    # 1005: الكوارتز / الألماس (Quartz) — group: 4
    1005: [
        {"item_id": 809605, "amount": 200000, "name": "صندوق موارد اختياري 200K (م5)", "group": 4},
        {"item_id": 809604, "amount": 62500,  "name": "صندوق موارد اختياري 62.5K (م4)", "group": 4},
        {"item_id": 809603, "amount": 20000,  "name": "صندوق موارد اختياري 20K (م3)", "group": 4},
        {"item_id": 809602, "amount": 6250,   "name": "صندوق موارد اختياري 6.25K (م2)", "group": 4},
        {"item_id": 809601, "amount": 2000,   "name": "صندوق موارد اختياري 2K (م1)", "group": 4},
    ],
}

# للحفاظ على التوافق مع أي استدعاء خارجي
RESOURCE_CHESTS = REGULAR_RESOURCE_CHESTS

# ═════════════════════════════════════════════════════════════════
#  محددات مواقع البناء في المدينة (مستخرجة من سورس اللعبة الرسمي Lua)
#  المراجع: mainCityFunctions.lua:947 و cityBuildConstDef.lua
# ═════════════════════════════════════════════════════════════════

# 1. مباني المواقع الثابتة الحصرية (Fixed Position Buildings)
FIXED_BUILDING_INDEXES: Dict[str, str] = {
    "101": "1050",  # القلعة (Castle)
    "102": "1053",  # الأسوار (Walls)
    "103": "1052",  # البرج الدفاعي الأيسر (TurretL) - والبرج الأيمن 1054
    "104": "1055",  # برج المراقبة (Watchtower)
    "108": "1068",  # الميناء (Port)
    "301": "1200",  # قاعة المجد والشرف / المعجزة (Miracle)
    "302": "1201",  # القصر النخبوي (Elite Palace)
    "1151": "1151", # ورشة المواد (Material Workshop)
    "1152": "1152", # الكريستال (Crystal)
}

# للتوافقية السابقة مع أي استيراد خارجي
INNER_BUILDING_DEFAULT_INDEX: Dict[str, str] = FIXED_BUILDING_INDEXES

# 2. قوائم الأولوية الرسمية للمباني الداخلية الحرة (Inner City Buildings - buildType == 0)
PREFER_INNER_CITY_INDEXES_STABLES: List[int] = [
    1064, 1063, 1067, 1061, 1062, 1065, 1058, 1059, 1060
]

PREFER_INNER_CITY_INDEXES: List[int] = [
    1067, 1061, 1062, 1064, 1063, 1065, 1058, 1059, 1060
]

# 3. قوائم الأولوية الرسمية للمباني الخارجية (Outer City Buildings - buildType == 1)
PREFER_OUTER_CITY_INDEXES_SPECIAL: Dict[int, List[int]] = {
    201: [1102, 1100, 1101, 1103, 1104],  # مزارع القمح
    202: [1107, 1105, 1106, 1108, 1109],  # مناشر الخشب
    205: [1111, 1110, 1112, 1113, 1114],  # الخيم العسكرية
}

PREFER_OUTER_CITY_INDEXES_GENERAL: List[int] = [
    1107, 1102, 1104, 1106, 1111, 1103, 1101, 1100, 1108, 1109, 1105
]

# خرائط نطاقات أراضي التوسعة الخارجية المفتوحة (openGroundInfo من اللعبة)
OPEN_GROUND_AREAS: Dict[int, Tuple[int, int]] = {
    1220: (1115, 1119),
    1221: (1120, 1124),
    1222: (1125, 1129),
    1223: (1130, 1134),
}


def get_can_build_index(
    bid: Union[str, int],
    used_indexes: Set[str],
    open_areas: Optional[List[int]] = None
) -> Optional[str]:
    """
    تحديد خانة البناء الشاغرة المناسبة للمبنى طبقاً لخوارزمية اللعبة الرسمية (mainCityFunctions.lua:947).
    يضمن بنسبة 100% عدم اختيار أي خانة مشغولة إطلاقاً لتفادي الخطأ 1020 (Err_INDEX_HAVE_BUILD).
    """
    try:
        bid_int = int(bid)
    except Exception:
        bid_int = 0
    bid_str = str(bid)

    # 1. مباني المواقع الثابتة الحصرية
    if bid_str in FIXED_BUILDING_INDEXES:
        if bid_str == "103":
            # البرج الدفاعي له موقعان: 1052 و 1054
            if "1052" not in used_indexes:
                return "1052"
            elif "1054" not in used_indexes:
                return "1054"
            return None
        fixed_idx = FIXED_BUILDING_INDEXES[bid_str]
        return fixed_idx if fixed_idx not in used_indexes else None

    # المعجزة / قاعة المجد 301
    if bid_int == 301:
        return "1200" if "1200" not in used_indexes else None

    # 2. تحديد نوع المبنى (0 = داخلي، 1 = خارجي للموارد والمعسكرات)
    # SoraDGetBuildTypeByBid: if bid < 200 or bid > 30000 or bid >= 300 -> 0 else 1
    is_inner = (bid_int < 200 or bid_int > 30000 or bid_int >= 300)

    candidate_indexes: List[int] = []

    def _add_if_absent(idx: int):
        if idx not in candidate_indexes:
            candidate_indexes.append(idx)

    if is_inner:
        # مباني داخلية (معسكرات 116..119، معهد 113، حداد 115، نافورة 114، حصن 120...)
        if bid_int == 116:  # معسكر الخيالة
            for idx in PREFER_INNER_CITY_INDEXES_STABLES:
                _add_if_absent(idx)
        else:
            for idx in PREFER_INNER_CITY_INDEXES:
                _add_if_absent(idx)

        # إضافة الاحتياطي الداخلي وفق تسلسل سورس اللعبة
        _add_if_absent(1051)
        for idx in range(1056, 1068):
            _add_if_absent(idx)
        _add_if_absent(1200)

    else:
        # مباني خارجية للموارد والمعسكرات والمشافي (201..206)
        if bid_int in PREFER_OUTER_CITY_INDEXES_SPECIAL:
            for idx in PREFER_OUTER_CITY_INDEXES_SPECIAL[bid_int]:
                _add_if_absent(idx)

        for idx in PREFER_OUTER_CITY_INDEXES_GENERAL:
            _add_if_absent(idx)

        for idx in range(1100, 1115):
            _add_if_absent(idx)

        # أراضي التوسعة المفتوحة (areaList)
        if open_areas:
            for area_id in open_areas:
                if area_id in OPEN_GROUND_AREAS:
                    min_idx, max_idx = OPEN_GROUND_AREAS[area_id]
                    for idx in range(min_idx, max_idx + 1):
                        _add_if_absent(idx)
        else:
            # احتياطي لكافة الخانات الخارجية حتى 1134
            for idx in range(1115, 1135):
                _add_if_absent(idx)

    # اختيار أول خانة شاغرة تماماً ليست في used_indexes
    for idx in candidate_indexes:
        idx_str = str(idx)
        if idx_str not in used_indexes:
            return idx_str

    return None


# أدوات تسريع البناء والتسريع العام مرتبة من الأطول للأقصر
SPEEDUP_ITEMS: List[Tuple[int, int, str]] = [
    (501105, 86400, "تسريع بناء 24 ساعة"),
    (501104, 43200, "تسريع بناء 12 ساعة"),
    (501103, 28800, "تسريع بناء 8 ساعات"),
    (501102, 7200,  "تسريع بناء ساعتين"),
    (501107, 3600,  "تسريع بناء ساعة"),
    (501101, 300,   "تسريع بناء 5 دقائق"),
    (501106, 60,    "تسريع بناء دقيقة"),
    (500605, 86400, "تسريع عام 24 ساعة"),
    (500604, 43200, "تسريع عام 12 ساعة"),
    (500603, 28800, "تسريع عام 8 ساعات"),
    (500602, 3600,  "تسريع عام ساعة"),
    (500601, 300,   "تسريع عام 5 دقائق"),
    (500606, 60,    "تسريع عام دقيقة"),
]

# خريطة الأسماء المستعارة لكل مبنى
BUILDING_KEY_TO_BID: Dict[str, str] = {
    "farm": "201", "wheat": "201", "tahil": "201", "201": "201", "مزرعة": "201",
    "sawmill": "202", "wood": "202", "odun": "202", "202": "202", "منشرة": "202",
    "iron_mine": "203", "iron": "203", "demir": "203", "203": "203", "حديد": "203",
    "quartz_mine": "204", "quartz": "204", "silver": "204", "kuvars": "204", "204": "204", "كوارتز": "204",
    "hospital": "206", "medical_tent": "206", "clinic": "206", "hastane": "206", "206": "206", "مشفى": "206",
    "military_tent": "205", "tent": "205", "army_tent": "205", "cadir": "205", "205": "205", "خيمة": "205",
    "castle": "101", "walls": "102", "wall": "102", "depot": "105", "college": "113",
}

# كاش حفظ جداول المباني المحملة ديناميكياً
_BUILDING_CFG_CACHE: Dict[str, Dict[int, Dict[str, Any]]] = {}
_ALL_BUILDINGS_CFG_CACHE: Optional[Dict[str, Dict[int, Dict[str, Any]]]] = None


def format_duration(seconds: float) -> str:
    """تنسيق المدة بالثواني إلى نص مقروء بالعربية."""
    total_sec = int(max(0, seconds))
    days = total_sec // 86400
    rem = total_sec % 86400
    hours = rem // 3600
    minutes = (rem % 3600) // 60
    secs = rem % 60
    parts = []
    if days > 0:
        parts.append(f"{days} يوم")
    if hours > 0:
        parts.append(f"{hours} س")
    if minutes > 0 or (days == 0 and hours > 0):
        parts.append(f"{minutes} د")
    if secs > 0 and days == 0 and hours == 0:
        parts.append(f"{secs} ث")
    return " و ".join(parts) if parts else "0 ث"


def parse_lua_build_table(content: str) -> Dict[int, Dict[str, Any]]:
    """محلل مخصص لقراءة جداول اللعبة Lua (build*.lua) واستخراج المتطلبات والتكاليف بدقة."""
    entries: Dict[int, Dict[str, Any]] = {}
    pos = 0
    pattern = re.compile(r'\[(\d+)\]\s*=\s*\{')
    while True:
        m = pattern.search(content, pos)
        if not m:
            break
        lv = int(m.group(1))
        start = m.end()
        depth = 1
        i = start
        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            i += 1
        block = content[start:i - 1]
        pos = i

        def _get_sub_dict(key: str) -> Dict[str, int]:
            km = re.search(rf'{key}\s*=\s*\{{([^}}]*)\}}', block)
            res: Dict[str, int] = {}
            if km and km.group(1).strip():
                nums = [int(x.strip()) for x in re.findall(r'\d+', km.group(1))]
                for idx in range(0, len(nums), 2):
                    if idx + 1 < len(nums):
                        res[str(nums[idx])] = nums[idx + 1]
            return res

        time_m = re.search(r'costTime\s*=\s*(\d+)', block)
        cost_time = int(time_m.group(1)) if time_m else 0

        blv_m = re.search(r'blv\s*=\s*(\d+)', block)
        actual_lv = int(blv_m.group(1)) if blv_m else lv

        entries[actual_lv] = {
            "preCond": _get_sub_dict("preCond"),
            "costRes": _get_sub_dict("costRes"),
            "costWEs": _get_sub_dict("costWEs"),
            "costTools": _get_sub_dict("costTools"),
            "costTime": cost_time,
        }
    return entries


def load_building_config(bid: str) -> Dict[int, Dict[str, Any]]:
    """تحميل جدول متطلبات المبنى من ملف JSON الشامل في core/ (يعمل على السيرفر) أو Lua محلياً مع التخزين المؤقت."""
    global _ALL_BUILDINGS_CFG_CACHE
    bid_str = str(bid)
    if bid_str in _BUILDING_CFG_CACHE:
        return _BUILDING_CFG_CACHE[bid_str]

    # 1. فحص ملف JSON الشامل في core/ (يعمل على السيرفر والمحلي بنسبة 100% دون الحاجة لـ Lua)
    if _ALL_BUILDINGS_CFG_CACHE is None:
        bp_path = os.path.join(_ROOT_DIR, "core", "buildings_prereqs.json")
        if not os.path.exists(bp_path):
            bp_path = os.path.join(_ROOT_DIR, "buildings_prereqs.json")
        if os.path.exists(bp_path):
            try:
                with open(bp_path, "r", encoding="utf-8") as fp:
                    raw = json.load(fp)
                    _ALL_BUILDINGS_CFG_CACHE = {
                        str(b_k): {int(lv_k): v for lv_k, v in b_data.items()}
                        for b_k, b_data in raw.items()
                    }
            except Exception:
                _ALL_BUILDINGS_CFG_CACHE = {}
        else:
            _ALL_BUILDINGS_CFG_CACHE = {}

    if _ALL_BUILDINGS_CFG_CACHE and bid_str in _ALL_BUILDINGS_CFG_CACHE:
        cfg = _ALL_BUILDINGS_CFG_CACHE[bid_str]
        _BUILDING_CFG_CACHE[bid_str] = cfg
        return cfg

    # 2. فحص ملف Lua كخيار محلي احتياطي
    lua_file = os.path.join(_ROOT_DIR, "lua_src", "src", "src", "app", "localtb", "config_server", f"build{bid_str}.lua")
    if not os.path.exists(lua_file):
        alt_lua = os.path.join(_ROOT_DIR, "lua_src", f"build{bid_str}.lua")
        if os.path.exists(alt_lua):
            lua_file = alt_lua

    if os.path.exists(lua_file):
        try:
            with open(lua_file, "r", encoding="utf-8", errors="ignore") as fp:
                cfg = parse_lua_build_table(fp.read())
            if cfg:
                _BUILDING_CFG_CACHE[bid_str] = cfg
                return cfg
        except Exception:
            pass

    # 3. احتياطي خاص بالقلعة: castle_prereqs.json
    if bid_str == "101":
        cp_file = os.path.join(_ROOT_DIR, "database", "castle_prereqs.json")
        if not os.path.exists(cp_file):
            cp_file = os.path.join(_ROOT_DIR, "tools", "castle_prereqs.json")
        if not os.path.exists(cp_file):
            cp_file = os.path.join(_ROOT_DIR, "core", "castle_prereqs.json")
        if not os.path.exists(cp_file):
            cp_file = os.path.join(_ROOT_DIR, "castle_prereqs.json")
        if os.path.exists(cp_file):
            try:
                with open(cp_file, "r", encoding="utf-8") as f:
                    cfg = {int(k): v for k, v in json.load(f).items()}
                _BUILDING_CFG_CACHE[bid_str] = cfg
                return cfg
            except Exception:
                pass

    return {}


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (BuildingTask)
# ════════════════════════════════════════════════════════════════════

class BuildingTask(BaseTask):
    """
    مهمة فحص وترقية القلعة ومباني الموارد والمعسكرات مع حل المتطلبات المتداخلة
    واستخدام صناديق الموارد وبناء المباني المفقودة تلقائياً.
    """
    name = "building"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.cached_bag: Optional[Dict[str, int]] = None
        self.city_buildings: List[Dict[str, Any]] = []
        self.open_area_list: List[int] = []
        self.active_queues: Dict[str, Dict[str, Any]] = {}
        self.max_build_slots: int = 2
        self.city_queue_data: Dict[str, Any] = {}
        self.city_reslist: Dict[str, Any] = {}
        self.city_saferes: Dict[str, Any] = {}
        self.upgraded_prereq_bids: Set[str] = set()

    async def safety_sleep(self, action_name: str = "", min_s: float = 3.0, max_s: float = 6.0) -> float:
        """تأخير أمان عشوائي فائق الحذر (3.0 - 6.0 ثوانٍ) يحاكي السلوك البشري لتفادي كشف البوت أو حظر الحساب."""
        delay = round(random.uniform(min_s, max_s), 2)
        if action_name:
            self.log.info(f"🛡️ أمان ضد الحظر: انتظار {delay} ثانية ({action_name})...")
        else:
            self.log.info(f"🛡️ أمان ضد الحظر: انتظار {delay} ثانية...")
        await asyncio.sleep(delay)
        return delay

    def get_selected_support_bids(self) -> List[str]:
        """تحديد قائمة المباني الداعمة المستهدفة للترقية بناءً على إعدادات المستخدم."""
        cfg = self.config
        tb = cfg.get("target_buildings") or cfg.get("subtasks") or cfg.get("selected_buildings")
        all_support_bids = ["201", "202", "203", "204", "206", "205"]

        if isinstance(tb, dict) and tb:
            selected = []
            for k, enabled in tb.items():
                if bool(enabled):
                    bid = BUILDING_KEY_TO_BID.get(str(k).lower())
                    if bid and bid not in selected:
                        selected.append(bid)
            return [b for b in all_support_bids if b in selected]

        if isinstance(tb, (list, tuple, set)) and tb:
            selected = []
            for item in tb:
                bid = BUILDING_KEY_TO_BID.get(str(item).lower())
                if bid and bid not in selected:
                    selected.append(bid)
            return [b for b in all_support_bids if b in selected]

        direct_keys = [
            ("farm", "201"), ("sawmill", "202"), ("iron_mine", "203"),
            ("quartz_mine", "204"), ("hospital", "206"), ("military_tent", "205")
        ]
        if any(f"upgrade_{k}" in cfg or k in cfg for k, _ in direct_keys):
            selected = []
            for k, bid in direct_keys:
                val = cfg.get(f"upgrade_{k}", cfg.get(k))
                if val is not None and bool(val):
                    selected.append(bid)
            return selected

        return all_support_bids

    async def get_city_buildings(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """الاستعلام عن جميع مباني المدينة عبر 1001/1 مع محاولة إعادة إذا تأخر الرد."""
        if self.city_buildings and not force_refresh:
            return self.city_buildings

        for attempt in range(2):
            resp = await self.conn.query("1001", "1", {}, timeout=15)
            if resp and isinstance(resp, dict):
                r_data = resp.get("data", {})
                if isinstance(r_data, dict):
                    q_data = r_data.get("queue")
                    if isinstance(q_data, dict):
                        self.city_queue_data = q_data
                    if "reslist" in r_data and isinstance(r_data["reslist"], dict):
                        self.city_reslist = r_data["reslist"]
                    if "saferes" in r_data and isinstance(r_data["saferes"], dict):
                        self.city_saferes = r_data["saferes"]
                    areas = r_data.get("areaList") or r_data.get("arealist")
                    if isinstance(areas, list):
                        self.open_area_list = [int(a) for a in areas if str(a).isdigit()]
                    blist = r_data.get("blist", [])
                    if isinstance(blist, list) and blist:
                        self.city_buildings = blist
                        return blist
            if attempt == 0:
                await asyncio.sleep(round(random.uniform(0.6, 1.2), 2))

        # احتياطي من init_data
        init_city = self.conn.init_data.get("cityCtrl", {})
        if isinstance(init_city, dict):
            if not self.city_queue_data and isinstance(init_city.get("queue"), dict):
                self.city_queue_data = init_city.get("queue", {})
            if not self.city_reslist and "reslist" in init_city and isinstance(init_city["reslist"], dict):
                self.city_reslist = init_city["reslist"]
            if not self.city_saferes and "saferes" in init_city and isinstance(init_city["saferes"], dict):
                self.city_saferes = init_city["saferes"]
            areas = init_city.get("areaList") or init_city.get("arealist")
            if isinstance(areas, list):
                self.open_area_list = [int(a) for a in areas if str(a).isdigit()]
            init_blist = init_city.get("blist", [])
            if isinstance(init_blist, list) and init_blist:
                self.city_buildings = init_blist
                return init_blist

        return []

    async def get_active_build_queues(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """الاستعلام عن طوابير البناء النشطة حالياً عبر 1003/1."""
        resp = await self.conn.query("1003", "1", {}, timeout=8)
        if not resp or not isinstance(resp, dict):
            return self.active_queues
        data = resp.get("data", {})
        active = {}
        if isinstance(data, dict):
            for qtype in ["1200", "1201"]:
                q_info = data.get(qtype)
                if q_info and isinstance(q_info, dict):
                    q_data = q_info.get("data", {})
                    bid = str(q_data.get("bid", ""))
                    lv = int(q_data.get("lv", 0))
                    total_time = float(q_info.get("totaltime", 0))
                    active[qtype] = {
                        "qtype": qtype,
                        "bid": bid,
                        "lv": lv,
                        "remain_time": total_time,
                        "raw": q_info
                    }
        self.active_queues = active
        return active

    async def get_max_build_slots(self, city_data: Optional[Dict[str, Any]] = None, active_queues: Optional[Dict[str, Any]] = None) -> int:
        """
        تحديد السعة القصوى لطوابير البناء للحساب (1 أو 2 طابور) بدقة:
        1. VIP >= 2 يمنح الطابور الثاني (71) مجاناً وبشكل دائم دون الحاجة لوقت VIP نشط.
        2. استئجار الطابور الثاني 1201 (عبر الذهب أو أدوات التوظيف) إذا كان وقت الإيجار لم ينتهِ بعد.
        3. وجود طابور 1201 نشط حالياً يبني بالفعل.
        4. إذا لم ينطبق أي مما سبق، فالحساب مبتدئ ولديه طابور بناء واحد فقط (1200).
        """
        # 1. فحص مستوى الـ VIP
        vip_ctrl = self.conn.init_data.get("vipCtrl", {})
        vip_lv = int(vip_ctrl.get("vipLv", 0)) if isinstance(vip_ctrl, dict) else 0
        if vip_lv >= 2:
            self.max_build_slots = 2
            return 2

        # 2. فحص استئجار الطابور الثاني 1201 من بيانات المدينة (1001/1 أو init_data)
        q_dict = getattr(self, "city_queue_data", {})
        if not q_dict and city_data and isinstance(city_data, dict):
            q_dict = city_data.get("queue", {})
        if not q_dict:
            q_dict = self.conn.init_data.get("cityCtrl", {}).get("queue", {})

        if isinstance(q_dict, dict) and "1201" in q_dict:
            q1201 = q_dict["1201"]
            if isinstance(q1201, dict):
                st = float(q1201.get("starttime", 0))
                tt = float(q1201.get("totaltime", 0))
                if (st + tt) > time.time():
                    self.max_build_slots = 2
                    return 2

        # 3. فحص هل الطابور 1201 نشط حالياً ويبني بالفعل (1003/1)
        if active_queues is None:
            active_queues = self.active_queues
        if active_queues and "1201" in active_queues:
            self.max_build_slots = 2
            return 2

        # حساب مبتدئ بدون VIP وبدون استئجار نشط
        self.max_build_slots = 1
        return 1

    async def get_backpack_items(self, force_refresh: bool = False) -> Dict[str, int]:
        """الاستعلام الدقيق عن محتويات الحقيبة عبر 1004/1 لجرد الصناديق والأدوات."""
        if self.cached_bag is not None and not force_refresh:
            return self.cached_bag

        bag_dict: Dict[str, int] = {}
        try:
            resp = await self.conn.query("1004", "1", {}, timeout=8)
            if resp and isinstance(resp, dict):
                bdata = resp.get("data", {})
                if isinstance(bdata, dict):
                    for iid_str, ival in bdata.items():
                        if isinstance(ival, dict):
                            bag_dict[str(iid_str)] = int(ival.get("count", 0))
                        elif isinstance(ival, (int, float)):
                            bag_dict[str(iid_str)] = int(ival)
        except Exception as e:
            self.log.warning(f"⚠️ تعذر استعلام الحقيبة عبر 1004/1: {e}")

        # نستخدم init_data فقط كإسناد احتياطي إذا فشل استعلام 1004/1 بالكامل ولم يرجع أي بيانات
        if not bag_dict:
            bp_ctrl = self.conn.init_data.get("backpackCtrl", {})
            if isinstance(bp_ctrl, dict):
                for iid_str, ival in bp_ctrl.items():
                    if isinstance(ival, dict):
                        bag_dict[str(iid_str)] = int(ival.get("count", 0))
                    elif isinstance(ival, (int, float, str)) and str(ival).isdigit():
                        bag_dict[str(iid_str)] = int(ival)

        self.cached_bag = bag_dict
        return bag_dict

    def get_current_resources(self) -> Dict[int, float]:
        """جلب أرصدة الموارد الحالية في المدينة (الرصيد العادي + الآمن) بأحدث القيم المحدثة."""
        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        reslist = self.city_reslist if self.city_reslist else (city_ctrl.get("reslist", {}) if isinstance(city_ctrl, dict) else {})
        saferes = self.city_saferes if self.city_saferes else (city_ctrl.get("saferes", {}) if isinstance(city_ctrl, dict) else {})

        res_balances: Dict[int, float] = {}
        for rid in [1002, 1003, 1004, 1005]:
            reg = float(reslist.get(str(rid), 0))
            safe = float(saferes.get(str(rid), 0))
            res_balances[rid] = reg + safe
        return res_balances

    async def harvest_resource_building(self, bid: int, iid: int) -> bool:
        """جمع المحصول من مبنى الموارد قبل الترقية عبر 1001/8."""
        try:
            resp = await self.conn.query("1001", "8", {"bid": bid, "iid": iid}, timeout=6)
            return isinstance(resp, dict) and resp.get("err") == "0"
        except Exception:
            return False

    async def upgrade_building(self, bid: str, index: str) -> Dict[str, Any]:
        """إرسال أمر الترقية لمبنى معين عبر 1001/3 بالموارد حصراً (mode: 0). ممنوع الذهب نهائياً."""
        payload = {
            "bid": str(bid),
            "mode": "0",  # ترقية بالموارد فقط
            "index": str(index)
        }
        res = await self.conn.query("1001", "3", payload, timeout=10)
        return res if isinstance(res, dict) else {"err": "-1"}

    # ═════════════════════════════════════════════════════════════════
    #  المكون 1: الاستعلام عن صناديق الموارد وفتحها بذكاء (Smart Unpacker)
    # ═════════════════════════════════════════════════════════════════

    async def _open_chests_for_deficit(
        self,
        chest_list: List[Dict[str, Any]],
        bag: Dict[str, int],
        deficit: float
    ) -> Tuple[int, List[str], float]:
        """
        خوارزمية فتح الصناديق التنازلية (من الأكبر للأصغر) مع حبة تغطية للعجز الصغير.
        تُعيد: (إجمالي المكتسب, قائمة أسماء الصناديق المفتوحة, العجز المتبقي).
        """
        rem_deficit = deficit
        opened_summary = []
        total_gained = 0

        for ch in chest_list:
            if rem_deficit <= 0:
                break

            c_id_str = str(ch["item_id"])
            cnt_available = bag.get(c_id_str, 0)
            c_amt = ch["amount"]

            if cnt_available <= 0:
                continue

            needed_cnt = int(rem_deficit // c_amt)
            if needed_cnt > 0:
                use_cnt = min(cnt_available, needed_cnt)
                payload: Dict[str, Any] = {"itemID": ch["item_id"], "count": use_cnt}
                if "group" in ch:
                    payload["extra"] = {"group": ch["group"]}
                resp_use = await self.conn.query("1004", "2", payload, timeout=8)
                if resp_use and isinstance(resp_use, dict) and resp_use.get("err") == "0":
                    gained = use_cnt * c_amt
                    total_gained += gained
                    rem_deficit -= gained
                    bag[c_id_str] = cnt_available - use_cnt
                    opened_summary.append(f"{use_cnt}x {ch['name']}")
                    await self.safety_sleep("فتح صناديق الموارد", min_s=1.5, max_s=3.0)

        # إذا بقي عجز صغير، فتح حبة واحدة من أصغر صندوق متوفر قادر على تغطية الباقي
        if rem_deficit > 0:
            smallest_cover_chest = None
            for ch in reversed(chest_list):
                c_id_str = str(ch["item_id"])
                cnt_available = bag.get(c_id_str, 0)
                if cnt_available > 0 and ch["amount"] >= rem_deficit:
                    smallest_cover_chest = ch
                    break

            if not smallest_cover_chest:
                # فتح حبة واحدة من أي صندوق متوفر
                for ch in reversed(chest_list):
                    c_id_str = str(ch["item_id"])
                    if bag.get(c_id_str, 0) > 0:
                        smallest_cover_chest = ch
                        break

            if smallest_cover_chest:
                c_id = smallest_cover_chest["item_id"]
                payload = {"itemID": c_id, "count": 1}
                if "group" in smallest_cover_chest:
                    payload["extra"] = {"group": smallest_cover_chest["group"]}
                resp_use = await self.conn.query("1004", "2", payload, timeout=8)
                if resp_use and isinstance(resp_use, dict) and resp_use.get("err") == "0":
                    gained = smallest_cover_chest["amount"]
                    total_gained += gained
                    rem_deficit = max(0.0, rem_deficit - gained)
                    bag[str(c_id)] -= 1
                    opened_summary.append(f"1x {smallest_cover_chest['name']}")
                    await self.safety_sleep("فتح صندوق موارد", min_s=1.5, max_s=3.0)

        return total_gained, opened_summary, rem_deficit

    async def ensure_resources(self, cost_res: Dict[str, int], force_open: bool = False) -> Tuple[bool, List[str]]:
        """
        التحقق من كفاية الموارد الأربعة للترقية، وعند وجود نقص:
          1. الاستعلام عن الحقيبة (1004/1).
          2. المرحلة الأولى: استهلاك الصناديق العادية أولاً لحماية الموارد الآمنة والاختيارية من الاستهلاك.
          3. المرحلة الثانية: اللجوء إلى الصناديق الآمنة فقط عند عدم كفاية الصناديق العادية أو انعدامها.
          4. المرحلة الثالثة: اللجوء إلى صناديق الموارد الاختيارية (الاحتياطي الأخير) كخط دفاع أخير.
        """
        if not cost_res:
            return True, []

        auto_chests = bool(self.config.get("auto_open_chests", True))
        current_res = self.get_current_resources()
        actions = []
        is_all_covered = True
        bag: Optional[Dict[str, int]] = None

        for resid_str, req_amt in cost_res.items():
            resid = int(resid_str)
            if req_amt <= 0 or resid not in RES_NAMES:
                continue

            curr_amt = 0.0 if force_open else current_res.get(resid, 0.0)
            if curr_amt >= req_amt:
                continue

            deficit = float(req_amt - curr_amt)
            r_name = RES_NAMES.get(resid, f"مورد #{resid}")

            if not auto_chests:
                self.log.warning(f"📦 نقص موارد {r_name}: المتوفر {int(curr_amt):,} < المطلوب {int(req_amt):,} (العجز: {int(deficit):,})")
                is_all_covered = False
                continue

            # استعلام الحقيبة المباشر لفحص الصناديق المتوفرة وأحجامها (مرة واحدة للدورة بدلاً من التكرار لكل مورد)
            if bag is None:
                bag = await self.get_backpack_items(force_refresh=True)
            reg_chest_list = REGULAR_RESOURCE_CHESTS.get(resid, [])
            safe_chest_list = SAFE_RESOURCE_CHESTS.get(resid, [])
            opt_chest_list = OPTIONAL_RESOURCE_CHESTS.get(resid, [])

            # جرد الصناديق المتوفرة في الحقيبة لهذا المورد
            avail_reg_info = []
            for ch in reg_chest_list:
                cnt = bag.get(str(ch["item_id"]), 0)
                if cnt > 0:
                    avail_reg_info.append(f"{ch['name']} (حجم {ch['amount']:,} × {cnt} حبة)")

            avail_safe_info = []
            for ch in safe_chest_list:
                cnt = bag.get(str(ch["item_id"]), 0)
                if cnt > 0:
                    avail_safe_info.append(f"{ch['name']} (حجم {ch['amount']:,} × {cnt} حبة)")

            avail_opt_info = []
            for ch in opt_chest_list:
                cnt = bag.get(str(ch["item_id"]), 0)
                if cnt > 0:
                    avail_opt_info.append(f"{ch['name']} (حجم {ch['amount']:,} × {cnt} حبة)")

            self.log.info(f"🔍 [فحص الصناديق] مطلوب تغطية عجز {int(deficit):,} من {r_name}")
            if avail_reg_info:
                self.log.info(f"   📦 الصناديق العادية المتوفرة في الحقيبة: {', '.join(avail_reg_info[:4])}")
            if avail_safe_info:
                self.log.info(f"   🛡️ الصناديق الآمنة المتوفرة في الحقيبة: {', '.join(avail_safe_info[:4])}")
            if avail_opt_info:
                self.log.info(f"   🎁 الصناديق الاختيارية المتوفرة في الحقيبة: {', '.join(avail_opt_info[:4])}")

            if not avail_reg_info and not avail_safe_info and not avail_opt_info:
                self.log.warning(f"   ⚠️ لا توجد أي صناديق متوفرة (عادية أو آمنة أو اختيارية) في الحقيبة لمورد {r_name}!")
                is_all_covered = False
                continue

            rem_deficit = deficit
            opened_summary = []
            total_gained = 0

            # ── المرحلة 1: فتح الصناديق العادية أولاً لحماية الموارد الآمنة والاختيارية ──
            if avail_reg_info:
                gained_reg, opened_reg, rem_deficit = await self._open_chests_for_deficit(reg_chest_list, bag, rem_deficit)
                total_gained += gained_reg
                opened_summary.extend(opened_reg)

            # ── المرحلة 2: الاستعانة بالصناديق الآمنة فقط إذا بقي عجز متبقي ──
            if rem_deficit > 0 and avail_safe_info:
                if avail_reg_info:
                    self.log.info(f"   🛡️ الصناديق العادية لم تكفِ. جاري فتح الصناديق الآمنة لتغطية العجز المتبقي ({int(rem_deficit):,} من {r_name})...")
                else:
                    self.log.info(f"   🛡️ لا توجد صناديق عادية متوفرة. جاري فتح الصناديق الآمنة لتغطية عجز {r_name} ({int(rem_deficit):,})...")
                gained_safe, opened_safe, rem_deficit = await self._open_chests_for_deficit(safe_chest_list, bag, rem_deficit)
                total_gained += gained_safe
                opened_summary.extend(opened_safe)

            # ── المرحلة 3: الاستعانة بصناديق الموارد الاختيارية كخط دفاع أخير إذا بقي عجز متبقي ──
            if rem_deficit > 0 and avail_opt_info:
                if avail_reg_info or avail_safe_info:
                    self.log.info(f"   🎁 الصناديق العادية والآمنة لم تكفِ. جاري فتح صناديق الموارد الاختيارية (الاحتياطي الأخير) لتغطية العجز المتبقي ({int(rem_deficit):,} من {r_name})...")
                else:
                    self.log.info(f"   🎁 لا توجد صناديق عادية أو آمنة متوفرة. جاري فتح صناديق الموارد الاختيارية لتغطية عجز {r_name} ({int(rem_deficit):,})...")
                gained_opt, opened_opt, rem_deficit = await self._open_chests_for_deficit(opt_chest_list, bag, rem_deficit)
                total_gained += gained_opt
                opened_summary.extend(opened_opt)

            if opened_summary:
                act_msg = f"📦 تم فتح صناديق {r_name} ({', '.join(opened_summary)}) بمقدار +{total_gained:,}"
                self.log.info(f"✅ {act_msg}")
                actions.append(act_msg)

            # تحديث الرصيد المحسوب محلياً
            new_curr = curr_amt + total_gained
            current_res[resid] = new_curr
            if total_gained > 0:
                cur_str = str(resid)
                old_v = float(self.city_reslist.get(cur_str, 0))
                self.city_reslist[cur_str] = old_v + total_gained

            if new_curr < req_amt:
                self.log.warning(f"⚠️ الصناديق المتوفرة لم تكفِ لتغطية كامل عجز {r_name} (المتبقي: {int(req_amt - new_curr):,})")
                is_all_covered = False

        return is_all_covered, actions

    # ═════════════════════════════════════════════════════════════════
    #  المكون 2: اكتشاف الأراضي الشاغرة وبناء المباني المفقودة (1001/2)
    # ═════════════════════════════════════════════════════════════════

    async def construct_missing_building(self, bid: str) -> Tuple[bool, str]:
        """
        بناء مبنى مفقود غير مشيّد إطلاقاً في المدينة:
          1. تحديد موقع البناء (index) الشاغر المناسب عبر خوارزمية اللعبة الرسمية (get_can_build_index).
          2. فحص وتأمين موارد التشييد الأولية (المستوى 1).
          3. إرسال أمر البناء عبر 1001/2 بـ mode: "0" (OPERATE_MODE.NORMAL التشييد الطبيعي بالموارد).
        """
        bid_str = str(bid)
        b_meta = BUILDING_INFO.get(bid_str, {"name": f"مبنى #{bid_str}", "name_ar": f"مبنى #{bid_str}"})
        b_name = b_meta["name"]

        # 1. جلب قائمة المباني الحالية وتحديد الخانات المشغولة
        blist = await self.get_city_buildings()
        used_indexes: Set[str] = {
            str(item.get("binfo", {}).get("index", ""))
            for item in blist
            if item.get("binfo", {}).get("index")
        }

        # استدعاء دالة اختيار الخانة الرسمية من اللعبة
        open_areas = getattr(self, "open_area_list", None)
        target_index = get_can_build_index(bid_str, used_indexes, open_areas)

        if not target_index or target_index in used_indexes:
            msg = f"❌ تعذر العثور على قطعة أرض شاغرة في المدينة لبناء {b_name} (جميع الخانات المرشحة مشغولة)!"
            self.log.error(msg)
            return False, msg

        # التحقق من توفر طابور بناء حر قبل استهلاك الصناديق
        active_q = await self.get_active_build_queues()
        if len(active_q) >= self.max_build_slots:
            msg = f"🛑 طوابير البناء مشغولة بالكامل ({len(active_q)}/{self.max_build_slots}) — تعذر بناء {b_name}."
            self.log.info(msg)
            return False, msg

        # 2. فحص موارد المستوى 1 للمبنى وتأمينها من الصناديق
        b_cfg = load_building_config(bid_str)
        lv1_cfg = b_cfg.get(1, {})
        cost_res = lv1_cfg.get("costRes", {})
        covered, _ = await self.ensure_resources(cost_res)
        if not covered:
            msg = f"⚠️ نقص موارد لبناء {b_name} في الموقع [{target_index}] ولم تكفِ الصناديق!"
            self.log.warning(msg)
            return False, msg

        # 3. إرسال أمر البناء 1001/2 بـ mode: "0" (OPERATE_MODE.NORMAL)
        self.log.info(f"🏗️ إرسال أمر تشييد مبنى جديد: {b_name} في الموقع الشاغر [{target_index}] عبر 1001/2...")
        payload = {
            "bid": bid_str,
            "mode": "0",  # OPERATE_MODE.NORMAL التشييد الطبيعي بالموارد في كود اللعبة
            "index": target_index
        }
        resp = await self.conn.query("1001", "2", payload, timeout=10)
        err = str(resp.get("err", "-1")) if isinstance(resp, dict) else "-1"

        # 🛡️ معالجة ذاتية ذكية عند خطأ نقص الموارد (كود 2 أو 1002)
        if err in ("2", "1002"):
            self.log.warning(f"⚠️ رفض السيرفر تشييد {b_name} بنقص موارد (كود {err}) — جاري تحديث الأرصدة وفتح الصناديق...")
            await self.get_city_buildings(force_refresh=True)
            covered, _ = await self.ensure_resources(cost_res, force_open=True)
            if covered:
                self.log.info(f"🏗️ إعادة إرسال أمر تشييد {b_name} بعد فتح الصناديق...")
                resp = await self.conn.query("1001", "2", payload, timeout=10)
                err = str(resp.get("err", "-1")) if isinstance(resp, dict) else "-1"

        if err == "0":
            msg = f"🎉 تم تشييد مبنى {b_name} بنجاح في الموقع [{target_index}]!"
            self.log.info(msg)
            # تحديث قائمة المباني محلياً
            self.upgraded_prereq_bids.add(bid_str)
            for cr_id, cr_amt in cost_res.items():
                cr_str = str(cr_id)
                cur_v = float(self.city_reslist.get(cr_str, 0))
                self.city_reslist[cr_str] = max(0.0, cur_v - float(cr_amt))
            await self.get_city_buildings(force_refresh=True)
            await self.safety_sleep(f"تشييد {b_name}")
            return True, msg
        elif err == "1001":
            msg = f"🛑 طوابير البناء ممتلئة ({len(self.active_queues)}/{self.max_build_slots}) — تعذر بناء {b_name}."
            self.log.info(msg)
            return False, msg
        elif err in ("2", "1002"):
            msg = f"⚠️ نقص موارد لدى السيرفر لتشييد {b_name} في الموقع [{target_index}]."
            self.log.warning(msg)
            return False, msg
        elif err == "1020":
            msg = f"❌ فشل تشييد {b_name}: الخانة [{target_index}] محجوزة لدى السيرفر (كود: 1020)."
            self.log.error(msg)
            return False, msg
        else:
            msg = f"⚠️ فشل تشييد {b_name} (كود خطأ: {err})"
            self.log.warning(msg)
            return False, msg

    # ═════════════════════════════════════════════════════════════════
    #  المكون 3: شجرة حل المتطلبات المتداخلة (Recursive Prerequisite Resolver)
    # ═════════════════════════════════════════════════════════════════

    async def resolve_and_upgrade_chain(
        self,
        target_bid: str,
        target_blv: int,
        visited: Optional[Set[Tuple[str, int]]] = None,
        depth: int = 0
    ) -> Dict[str, Any]:
        """
        دالة استدعاء ذاتي لحل شجرة المتطلبات وترقيتها بشكل متسلسل:
          - تفحص متطلبات target_bid للوصول إلى target_blv.
          - إذا كان المبنى غير موجود إطلاقاً، تقوم ببنائه فوراً.
          - إذا كان يتطلب مبنى آخر بمستوى أعلى، تستدعي نفسها لذلك المبنى لترقيته أولاً.
          - إذا كان المانع الوحيد للقلعة هو وسام الحرب، تضع إشارة تخطي وتسمح بترقية اللوازم.
          - تعيد تقريراً بالعمليات المنفذة وحالة الجاهزية.
        """
        if visited is None:
            visited = set()

        chain_key = (str(target_bid), int(target_blv))
        if chain_key in visited or depth > 8:
            return {"ready": False, "actions": [], "reason": "حلقة متطلبات دائرية أو تجاوز أقصى عمق"}
        visited.add(chain_key)

        if not self.conn or not getattr(self.conn, "is_connected", True):
            return {"ready": False, "actions": [], "reason": "انقطع الاتصال بالسيرفر"}

        bid_str = str(target_bid)
        b_meta = BUILDING_INFO.get(bid_str, {"name": f"مبنى #{bid_str}", "name_ar": f"مبنى #{bid_str}", "max_lv": 130})
        b_name = b_meta["name"]

        # جلب مباني المدينة الحالية
        blist = await self.get_city_buildings()
        matching_buildings = [
            item.get("binfo", {}) for item in blist
            if str(item.get("binfo", {}).get("bid", "")) == bid_str
        ]

        # 1. حالة المبنى المفقود تماماً (المستوى 0)
        if not matching_buildings:
            self.log.info(f"🔍 المتطلب المشروط {b_name} غير موجود في المدينة إطلاقاً — جاري محاولة بنائه...")
            if not self.config.get("check_only", False):
                ok_build, b_msg = await self.construct_missing_building(bid_str)
                return {"ready": ok_build, "actions": [b_msg] if ok_build else [], "reason": b_msg if not ok_build else ""}
            else:
                return {"ready": False, "actions": [f"🔍 مطلوب بناء {b_name} في المدينة"], "reason": "المبنى غير مشيّد"}

        # اختيار المبنى ذو المستوى الأعلى لحساب كفاية الشرط
        max_instance = max(matching_buildings, key=lambda x: int(x.get("lv", 0)))
        curr_blv = int(max_instance.get("lv", 0))

        # إذا كان المستوى الحالي يلبي المطلوب بالفعل
        if curr_blv >= target_blv:
            return {"ready": True, "actions": [], "reason": "المتطلب مكتمل بالفعل"}

        # إذا كان المبنى قيد الترقية حالياً على أحد الطوابير
        is_upgrading = any(str(b.get("state", "0")) == "2" for b in matching_buildings) or any(
            str(q.get("bid")) == bid_str for q in self.active_queues.values()
        )
        if is_upgrading:
            return {
                "ready": False,
                "actions": [f"⏳ {b_name} قيد الترقية حالياً (مستوى {curr_blv} ➔ {curr_blv + 1})"],
                "reason": "المبنى قيد الترقية بالفعل"
            }

        # نحن بحاجة لترقية هذا المبنى إلى المستوى التالي (curr_blv + 1)
        next_blv = curr_blv + 1
        b_cfg = load_building_config(bid_str)
        req_cfg = b_cfg.get(next_blv, {})
        pre_cond = req_cfg.get("preCond", {})
        cost_res = req_cfg.get("costRes", {})
        cost_wes = req_cfg.get("costWEs", {})
        cost_tools = req_cfg.get("costTools", {})

        # صمام أمان وقائي للقلعة
        if bid_str == "101" and not pre_cond:
            pre_cond = {"102": curr_blv}
            if next_blv >= 41:
                pre_cond["301"] = curr_blv

        actions_taken = []

        # 2. فحص وحل شجرة المباني المتطلبة مسبقاً لهذا المبنى (Recursive Cascade بالتوازي)
        all_pre_satisfied = True
        for req_bid, req_lv in pre_cond.items():
            req_bid_str = str(req_bid)
            r_name = BUILDING_INFO.get(req_bid_str, {}).get("name", f"مبنى #{req_bid_str}")

            if req_bid_str == "101":
                # متطلب القلعة لمبنى فرعي: نكتفي بمقارنة المستوى الحالي للقلعة لمنع التكرار الدائري
                c_item = next((b.get("binfo", {}) for b in blist if str(b.get("binfo", {}).get("bid", "")) == "101"), {})
                c_lv = int(c_item.get("lv", 0))
                if c_lv < int(req_lv):
                    all_pre_satisfied = False
                    actions_taken.append(f"⚠️ {b_name} تتطلب 🏰 القلعة مستوى {req_lv} (الحالي: {c_lv})")
                continue

            # استدعاء ذاتي لحل وترقية المتطلب الأدنى
            sub_res = await self.resolve_and_upgrade_chain(
                req_bid_str,
                int(req_lv),
                visited=visited,
                depth=depth + 1
            )
            sub_acts = sub_res.get("actions", [])
            if sub_acts:
                actions_taken.extend(sub_acts)

            # التحقق هل المتطلب مكتمل وبلغ المستوى المطلوب فعلياً
            blist_now = await self.get_city_buildings()
            curr_inst = [b.get("binfo", {}) for b in blist_now if str(b.get("binfo", {}).get("bid", "")) == req_bid_str]
            curr_max_l = max([int(b.get("lv", 0)) for b in curr_inst], default=0)
            if curr_max_l < int(req_lv):
                all_pre_satisfied = False

        if not all_pre_satisfied:
            return {
                "ready": False,
                "actions": actions_taken,
                "reason": "المتطلبات المسبقة قيد الترقية أو غير مكتملة"
            }

        # 3. فحص الأدوات وأوسمة الحرب
        bag = await self.get_backpack_items()
        missing_items = []
        for iid_str, req_cnt in {**cost_wes, **cost_tools}.items():
            if req_cnt > 0:
                curr_cnt = bag.get(str(iid_str), 0)
                if curr_cnt < req_cnt:
                    it_title = "وسام الحرب (301101)" if str(iid_str) == "301101" else f"أداة #{iid_str}"
                    missing_items.append({
                        "id": str(iid_str),
                        "name": it_title,
                        "current": curr_cnt,
                        "required": req_cnt
                    })

        if missing_items:
            m_names = [f"{mi['name']} ({mi['current']}/{mi['required']})" for mi in missing_items]
            reason_str = f"نقص أدوات وأوسمة: {', '.join(m_names)}"
            self.log.info(f"⚠️ {b_name} بانتظار {reason_str}")
            return {
                "ready": False,
                "actions": actions_taken + [f"⚠️ {b_name} بانتظار {reason_str}"],
                "reason": reason_str,
                "blocked_by_items": True
            }

        # 4. التحقق من توفر طابور بناء حر قبل فتح الصناديق
        active_q = await self.get_active_build_queues()
        if len(active_q) >= self.max_build_slots:
            return {
                "ready": False,
                "actions": actions_taken,
                "reason": f"طوابير البناء مشغولة بالكامل ({len(active_q)}/{self.max_build_slots})"
            }

        # 5. فحص الموارد واستخدام الصناديق إن لزم
        res_covered, chest_actions = await self.ensure_resources(cost_res)
        actions_taken.extend(chest_actions)
        if not res_covered:
            res_reason = f"نقص موارد لترقية {b_name} (الصناديق غير كافية)"
            self.log.info(f"⚠️ {res_reason}")
            return {
                "ready": False,
                "actions": actions_taken + [f"⚠️ {res_reason}"],
                "reason": res_reason,
                "blocked_by_res": True
            }

        # 6. تنفيذ الترقية الفعلية للمبنى الجاهز بنسبة 100%
        if not self.config.get("check_only", False):
            # إذا كان مبنى موارد: جمع المحصول أولاً
            if BUILDING_INFO.get(bid_str, {}).get("harvest", False):
                iid = int(max_instance.get("iid", 0))
                await self.harvest_resource_building(int(bid_str), iid)
                await asyncio.sleep(round(random.uniform(1.0, 2.0), 2))

            idx_to_up = str(max_instance.get("index", ""))
            self.log.info(f"🔨 إرسال أمر ترقية {b_name} إلى المستوى {next_blv} (موقع: {idx_to_up})...")
            r_up = await self.upgrade_building(bid_str, idx_to_up)
            err_up = str(r_up.get("err", "-1")) if isinstance(r_up, dict) else "-1"

            # 🛡️ معالجة ذاتية ذكية عند خطأ نقص الموارد (كود 2 أو 1002)
            if err_up in ("2", "1002"):
                self.log.warning(f"⚠️ رفض السيرفر ترقية {b_name} بنقص موارد (كود {err_up}) — جاري تحديث الأرصدة وفتح الصناديق فوراً...")
                await self.get_city_buildings(force_refresh=True)
                res_covered, c_acts = await self.ensure_resources(cost_res, force_open=True)
                actions_taken.extend(c_acts)
                if res_covered:
                    self.log.info(f"🔨 إعادة إرسال أمر ترقية {b_name} بعد فتح الصناديق...")
                    r_up = await self.upgrade_building(bid_str, idx_to_up)
                    err_up = str(r_up.get("err", "-1")) if isinstance(r_up, dict) else "-1"

            if err_up == "0":
                act_msg = f"🔨 بدء ترقية {b_name} إلى المستوى {next_blv} 🎉"
                self.log.info(act_msg)
                actions_taken.append(act_msg)
                max_instance["state"] = "2"
                self.upgraded_prereq_bids.add(bid_str)
                for cr_id, cr_amt in cost_res.items():
                    cr_str = str(cr_id)
                    cur_v = float(self.city_reslist.get(cr_str, 0))
                    self.city_reslist[cr_str] = max(0.0, cur_v - float(cr_amt))
                await self.safety_sleep(f"ترقية {b_name}")
                await self.get_active_build_queues()
                return {"ready": True, "actions": actions_taken, "reason": ""}
            elif err_up in ("1001", "1008"):
                self.max_build_slots = len(active_q) or 1
                self.log.info(f"🛑 طوابير البناء المتاحة ممتلئة بالكامل ({len(active_q)}/{self.max_build_slots})")
                return {"ready": False, "actions": actions_taken, "reason": f"طوابير البناء ممتلئة ({len(active_q)}/{self.max_build_slots})"}
            else:
                self.log.warning(f"⚠️ فشل أمر ترقية {b_name} لدى السيرفر (كود {err_up})")
                return {"ready": False, "actions": actions_taken, "reason": f"فشل أمر ترقية {b_name} (كود {err_up})"}
        else:
            actions_taken.append(f"🔍 [فحص] {b_name} جاهز 100% للترقية إلى المستوى {next_blv}")
            return {"ready": True, "actions": actions_taken, "reason": ""}

    async def upgrade_single_instance(self, binfo: Dict[str, Any]) -> Tuple[bool, List[str], str]:
        """
        فحص وترقية مبنى محدد (Instance) في المدينة:
        - يفحص المتطلبات المسبقة لهذا المبنى
        - يفحص الأدوات والميداليات
        - يفحص الموارد ويستخدم الصناديق التلقائية إذا لزم
        - ينفذ الترقية إذا لم يكن وضع فحص فقط
        """
        if not self.conn or not getattr(self.conn, "is_connected", True):
            return False, [], "انقطع الاتصال بالسيرفر"

        bid_str = str(binfo.get("bid", ""))
        curr_lv = int(binfo.get("lv", 0))
        next_lv = curr_lv + 1
        b_meta = BUILDING_INFO.get(bid_str, {"name": f"مبنى #{bid_str}", "max_lv": 130})
        b_name = b_meta["name"]
        idx_str = str(binfo.get("index", ""))

        if next_lv > b_meta.get("max_lv", 130):
            return False, [], f"{b_name} في الحد الأقصى للمستوى"

        b_cfg = load_building_config(bid_str)
        req_cfg = b_cfg.get(next_lv, {})
        pre_cond = req_cfg.get("preCond", {})
        cost_res = req_cfg.get("costRes", {})
        cost_wes = req_cfg.get("costWEs", {})
        cost_tools = req_cfg.get("costTools", {})

        # 1. فحص المتطلبات المسبقة في المدينة
        blist = await self.get_city_buildings()
        city_max_levels: Dict[str, int] = {}
        for b in blist:
            bi = b.get("binfo", {})
            b_id = str(bi.get("bid", ""))
            b_l = int(bi.get("lv", 0))
            if b_l > city_max_levels.get(b_id, 0):
                city_max_levels[b_id] = b_l

        for req_bid, req_lv in pre_cond.items():
            req_bid_s = str(req_bid)
            if city_max_levels.get(req_bid_s, 0) < int(req_lv):
                r_name = BUILDING_INFO.get(req_bid_s, {}).get("name", f"مبنى #{req_bid_s}")
                return False, [], f"يتطلب {r_name} مستوى {req_lv}"

        # 2. فحص الأدوات والميداليات
        bag = await self.get_backpack_items()
        for iid_str, req_cnt in {**cost_wes, **cost_tools}.items():
            if req_cnt > 0 and bag.get(str(iid_str), 0) < req_cnt:
                it_name = "وسام الحرب" if str(iid_str) == "301101" else f"أداة #{iid_str}"
                return False, [], f"نقص {it_name} ({bag.get(str(iid_str), 0)}/{req_cnt})"

        # 3. فحص الموارد واستخدام الصناديق
        res_covered, chest_actions = await self.ensure_resources(cost_res)
        if not res_covered:
            return False, chest_actions, f"نقص موارد لترقية {b_name} (الصناديق غير كافية)"

        # 4. الترقية أو الفحص
        if self.config.get("check_only", False):
            msg = f"🔍 [فحص] جاهز للترقية: {b_name} (مستوى {curr_lv} ➔ {next_lv})"
            self.log.info(msg)
            return True, chest_actions + [msg], ""

        # وضع الترقية الفعلي
        if b_meta.get("harvest", False):
            await self.harvest_resource_building(int(bid_str), int(binfo.get("iid", 0)))
            await asyncio.sleep(round(random.uniform(1.0, 2.0), 2))

        self.log.info(f"🔨 إرسال أمر ترقية {b_name} إلى المستوى {next_lv} (موقع: {idx_str})...")
        r_up = await self.upgrade_building(bid_str, idx_str)
        err = str(r_up.get("err", "-1")) if isinstance(r_up, dict) else "-1"

        # 🛡️ معالجة ذاتية ذكية عند خطأ نقص الموارد (كود 2 أو 1002)
        if err in ("2", "1002"):
            self.log.warning(f"⚠️ رفض السيرفر ترقية {b_name} بنقص موارد (كود {err}) — جاري تحديث الأرصدة وفتح الصناديق فوراً...")
            await self.get_city_buildings(force_refresh=True)
            res_covered, c_acts = await self.ensure_resources(cost_res, force_open=True)
            chest_actions.extend(c_acts)
            if res_covered:
                self.log.info(f"🔨 إعادة إرسال أمر ترقية {b_name} بعد فتح الصناديق...")
                r_up = await self.upgrade_building(bid_str, idx_str)
                err = str(r_up.get("err", "-1")) if isinstance(r_up, dict) else "-1"

        if err == "0":
            act_msg = f"🔨 بدء ترقية {b_name} إلى المستوى {next_lv} 🎉"
            self.log.info(act_msg)
            binfo["state"] = "2"
            for cr_id, cr_amt in cost_res.items():
                cr_str = str(cr_id)
                cur_v = float(self.city_reslist.get(cr_str, 0))
                self.city_reslist[cr_str] = max(0.0, cur_v - float(cr_amt))
            await self.safety_sleep(f"ترقية {b_name}")
            await self.get_active_build_queues()
            return True, chest_actions + [act_msg], ""
        elif err in ("1001", "1008"):
            self.max_build_slots = len(self.active_queues) or 1
            self.log.info(f"🛑 طوابير البناء المتاحة ممتلئة بالكامل ({len(self.active_queues)}/{self.max_build_slots})")
            return False, chest_actions, f"طوابير البناء ممتلئة ({len(self.active_queues)}/{self.max_build_slots})"
        else:
            self.log.warning(f"⚠️ فشل ترقية {b_name} لدى السيرفر (كود {err})")
            return False, chest_actions, f"فشل ترقية {b_name} (كود {err})"

    # ═════════════════════════════════════════════════════════════════
    #  المكون 4: تسريع القلعة ولوازم تطويرها بالأدوات المجانية والحقيبة
    # ═════════════════════════════════════════════════════════════════

    def get_castle_prerequisite_bids(self, target_castle_lv: int) -> Set[str]:
        """استخراج جميع معرفات المباني التي تمثل متطلباً لترقية القلعة حتى المستوى المستهدف."""
        prereq_bids: Set[str] = {"101"}
        visited: Set[Tuple[str, int]] = set()

        def _collect(bid: str, lv: int, depth: int = 0):
            if depth > 8 or (bid, lv) in visited:
                return
            visited.add((bid, lv))
            prereq_bids.add(str(bid))
            b_cfg = load_building_config(str(bid))
            pre = b_cfg.get(int(lv), {}).get("preCond", {})
            if str(bid) == "101" and not pre:
                pre = {"102": lv - 1}
                if lv >= 41:
                    pre["301"] = lv - 1
            for p_bid, p_lv in pre.items():
                _collect(str(p_bid), int(p_lv), depth + 1)

        _collect("101", target_castle_lv)
        return prereq_bids | getattr(self, "upgraded_prereq_bids", set())

    async def speedup_queue(self, qtype: str, allowed_bids: Optional[Set[str]] = None) -> int:
        """
        تسريع طابور محدد (القلعة أو أحد لوازم تطويرها) بالأدوات المجانية والحقيبة (ممنوع الذهب).
        يستثني تماماً أي طابور متبقٍ عليه أقل من دقيقة (< 60 ثانية) منعاً لهدر الأدوات.
        """
        queues = await self.get_active_build_queues()
        q_info = queues.get(str(qtype))
        if not q_info:
            return 0

        bid = str(q_info.get("bid", ""))
        b_name = BUILDING_INFO.get(bid, {}).get("name", f"مبنى #{bid}")

        # التحقق من أن المبنى مصرح بتسريعه (القلعة أو أحد لوازم تطويرها)
        if allowed_bids is not None and bid not in allowed_bids:
            return 0

        remain_sec = float(q_info.get("remain_time", 0))

        # 🛑 شرط المستخدم الصارم: منع استخدام التسريع إذا كان الوقت المتبقي أقل من دقيقة (< 60 ثانية)
        if remain_sec < 60:
            self.log.info(f"⏳ المتبقي على ترقية {b_name} هو {int(remain_sec)} ثانية (< دقيقة) — تخطي استخدام أدوات التسريع وانتظار الاكتمال الطبيعي.")
            return 0

        self.log.info(f"⚡ بدء تسريع ترقية {b_name} على طابور {qtype}...")
        self.log.info(f"⏳ الوقت المتبقي: {format_duration(remain_sec)} ({int(remain_sec)} ثانية)")

        # 1. تجربة التسريع المجاني أولاً (mode: 0)
        resp_free = await self.conn.query("1003", "2", {
            "qtype": str(qtype),
            "mode": "0",
            "otherinfo": "",
            "count": 1,
            "decreaseTime": "0"
        }, timeout=12)
        if resp_free and isinstance(resp_free, dict) and resp_free.get("err") == "0":
            self.log.info(f"🎉 تم تطبيق التسريع المجاني الفوري لـ {b_name} بنجاح!")
            return int(remain_sec)

        # 2. أدوات الحقيبة
        bag_items = await self.get_backpack_items(force_refresh=True)
        total_reduced_sec = 0

        for item_id, item_sec, item_name in SPEEDUP_ITEMS:
            # فحص حالة الاتصال
            if not self.conn or not getattr(self.conn, "is_connected", True):
                self.log.warning(f"⚠️ توقف تسريع {b_name} بسبب انقطاع الاتصال بالسيرفر.")
                break

            # إعادة فحص شرط الدقيقة: إذا انخفض الوقت المتبقي إلى أقل من 60 ثانية، نتوقف فوراً
            if remain_sec < 60:
                self.log.info(f"⏳ انخفض الوقت المتبقي لـ {b_name} إلى {int(remain_sec)} ثانية (< دقيقة) — توقف التسريع للاكتمال الطبيعي.")
                break

            s_id = str(item_id)
            available_count = bag_items.get(s_id, 0)
            if available_count <= 0:
                continue

            needed_count = int(remain_sec // item_sec)
            if needed_count <= 0:
                continue

            use_count = min(available_count, needed_count)
            self.log.info(f"📦 استخدام {use_count}x من {item_name} لتسريع {b_name}...")

            resp_tool = await self.conn.query("1003", "2", {
                "qtype": str(qtype),
                "mode": "2",
                "otherinfo": s_id,
                "count": use_count,
                "decreaseTime": "0"
            }, timeout=15)

            if not resp_tool or not isinstance(resp_tool, dict):
                # فحص سريع ومباشر لطابور البناء لمعرفة هل نجح التسريع رغم تأخر رد السيرفر
                q_check = await self.get_active_build_queues(force_refresh=True)
                new_q = q_check.get(str(qtype))
                if not new_q or float(new_q.get("remain_time", 0)) <= 0:
                    total_reduced_sec += int(remain_sec)
                    remain_sec = 0.0
                    self.log.info(f"🎉 تم تأكيد اكتمال ترقية {b_name} بالسيرفر وتفريغ الطابور!")
                    return total_reduced_sec
                if new_q and float(new_q.get("remain_time", 0)) < remain_sec:
                    actual_remain = float(new_q.get("remain_time", 0))
                    diff = remain_sec - actual_remain
                    total_reduced_sec += int(diff)
                    remain_sec = actual_remain
                    bag_items[s_id] = max(0, bag_items.get(s_id, 0) - use_count)
                    self.log.info(f"✅ تم تأكيد التسريع من السيرفر ({format_duration(diff)}) | متبقي: {format_duration(remain_sec)}")
                    continue
                # إذا لم يستجب السيرفر ولم ينقص الوقت، نضع رصيد هذا العنصر 0 وننتقل للحزم التالية
                bag_items[s_id] = 0
                if self.cached_bag:
                    self.cached_bag[s_id] = 0
                self.log.warning(f"⚠️ تعذر استلام رد التسريع لـ {b_name} لحزمة {item_name} (قد تكون غير متوفرة) — تجربة الحزم التالية.")
                continue

            err_code = str(resp_tool.get("err", "-1"))
            if err_code in ("0", "1010"):
                reduced = use_count * item_sec
                total_reduced_sec += reduced
                remain_sec = max(0.0, remain_sec - reduced)
                bag_items[s_id] -= use_count
                if self.cached_bag and s_id in self.cached_bag:
                    self.cached_bag[s_id] = bag_items[s_id]
                if err_code == "1010" or remain_sec <= 0:
                    self.log.info(f"🎉 تم إنهاء ترقية {b_name} بالكامل عبر {item_name} (اكتمل الطابور)!")
                    return total_reduced_sec + int(remain_sec)
                self.log.info(f"✅ تم تقليص {format_duration(reduced)} | متبقي: {format_duration(remain_sec)}")
                await self.safety_sleep(f"استخدام تسريع {b_name}", min_s=2.0, max_s=4.0)

                # تجربة المجاني مجدداً
                resp_f2 = await self.conn.query("1003", "2", {
                    "qtype": str(qtype), "mode": "0", "otherinfo": "", "count": 1, "decreaseTime": "0"
                }, timeout=8)
                if resp_f2 and isinstance(resp_f2, dict) and str(resp_f2.get("err")) in ("0", "1010"):
                    self.log.info(f"🎉 اكتملت ترقية {b_name} عبر التسريع المجاني بعد تقليص الوقت!")
                    return total_reduced_sec + int(remain_sec)
            else:
                bag_items[s_id] = 0
                if self.cached_bag:
                    self.cached_bag[s_id] = 0
        # 2.5. بديل أخير ذكي: إذا نفدت الحزم الأصغر وبقي وقت (>= 300 ثانية)،
        # يُسمح باستهلاك حبة واحدة (1x) من أصغر باقة متوفرة تحقق أن الهدر الزمني لا يتجاوز 10%
        # (أي أن الوقت المتبقي يغطي 90% على الأقل من مدة تلك الباقة: remain_sec >= 0.90 * item_sec)
        if remain_sec >= 300:
            candidate_packages = [
                (501107, 3600, "تسريع بناء ساعة"),
                (500602, 3600, "تسريع عام ساعة"),
                (501102, 7200, "تسريع بناء ساعتين"),
                (501103, 28800, "تسريع بناء 8 ساعات"),
                (500603, 28800, "تسريع عام 8 ساعات"),
                (501104, 43200, "تسريع بناء 12 ساعة"),
                (500604, 43200, "تسريع عام 12 ساعة"),
                (501105, 86400, "تسريع بناء 24 ساعة"),
                (500605, 86400, "تسريع عام 24 ساعة"),
            ]
            for item_id, item_sec, item_name in candidate_packages:
                if not self.conn or not getattr(self.conn, "is_connected", True):
                    break
                s_id = str(item_id)
                available_count = bag_items.get(s_id, 0)
                # شرط الهدر الصارم 10%: الباقة أكبر من الوقت المتبقي، ولكن الوقت يغطي 90% فأكثر منها (الهدر <= 10%)
                if available_count > 0 and (0.90 * item_sec) <= remain_sec < item_sec:
                    waste_sec = item_sec - remain_sec
                    waste_pct = (waste_sec / item_sec) * 100.0
                    self.log.info(
                        f"📦 [بديل أخير] استخدام 1x من {item_name} لتسريع {b_name} "
                        f"(الوقت المتبقي: {format_duration(remain_sec)} | الهدر: {format_duration(waste_sec)} [{waste_pct:.1f}% ≤ 10%])..."
                    )
                    resp_tool = await self.conn.query("1003", "2", {
                        "qtype": str(qtype),
                        "mode": "2",
                        "otherinfo": s_id,
                        "count": 1,
                        "decreaseTime": "0"
                    }, timeout=15)

                    err_code = str(resp_tool.get("err", "-1")) if isinstance(resp_tool, dict) else "-1"
                    if err_code in ("0", "1010"):
                        total_reduced_sec += int(remain_sec)
                        remain_sec = 0.0
                        bag_items[s_id] = max(0, bag_items.get(s_id, 0) - 1)
                        if self.cached_bag and s_id in self.cached_bag:
                            self.cached_bag[s_id] = bag_items[s_id]
                        self.log.info(f"🎉 تم إنهاء ترقية {b_name} بالكامل عبر {item_name} بنجاح!")
                        await self.safety_sleep(f"استخدام تسريع {b_name}", min_s=2.0, max_s=4.0)
                        break
                    else:
                        q_check = await self.get_active_build_queues(force_refresh=True)
                        new_q = q_check.get(str(qtype))
                        if not new_q or float(new_q.get("remain_time", 0)) <= 0:
                            total_reduced_sec += int(remain_sec)
                            remain_sec = 0.0
                            bag_items[s_id] = max(0, bag_items.get(s_id, 0) - 1)
                            if self.cached_bag and s_id in self.cached_bag:
                                self.cached_bag[s_id] = bag_items[s_id]
                            self.log.info(f"🎉 تم تأكيد إنهاء ترقية {b_name} بنجاح واكتمال الطابور بالسيرفر!")
                            break
                        bag_items[s_id] = 0
                        if self.cached_bag:
                            self.cached_bag[s_id] = 0
                        self.log.warning(f"⚠️ تعذر استلام رد التسريع لـ {b_name} لحزمة {item_name} (كود: {err_code}) — تجربة الحزمة البديلة.")
                        continue

        # 3. إنهاء الوقت المتبقي (بين 60 ثانية و 300 ثانية) باستخدام حزمة 5 دقائق واحدة
        # شرط المستخدم المعتمد: إذا تبقى أقل من 5 دقائق وأكثر من دقيقة (60 <= remain_sec < 300)
        # يُسمح باستخدام تسريع 5 دقائق واحد (1x) لإنهاء المبنى فوراً وتفادي الانتظار.
        if 60 <= remain_sec < 300:
            five_min_candidates = [
                (501101, "تسريع بناء 5 دقائق"),
                (500601, "تسريع عام 5 دقائق"),
            ]
            for item_id, item_name in five_min_candidates:
                if not self.conn or not getattr(self.conn, "is_connected", True):
                    break
                s_id = str(item_id)
                available_count = bag_items.get(s_id, 0)
                if available_count > 0:
                    self.log.info(f"📦 استخدام 1x من {item_name} لإنهاء الوقت المتبقي لـ {b_name} ({format_duration(remain_sec)})...")
                    resp_tool = await self.conn.query("1003", "2", {
                        "qtype": str(qtype),
                        "mode": "2",
                        "otherinfo": s_id,
                        "count": 1,
                        "decreaseTime": "0"
                    }, timeout=15)

                    err_code = str(resp_tool.get("err", "-1")) if isinstance(resp_tool, dict) else "-1"
                    if err_code in ("0", "1010"):
                        total_reduced_sec += int(remain_sec)
                        remain_sec = 0.0
                        bag_items[s_id] = max(0, bag_items.get(s_id, 0) - 1)
                        self.log.info(f"🎉 تم إنهاء ترقية {b_name} بالكامل عبر {item_name}!")
                        await self.safety_sleep(f"استخدام تسريع {b_name}", min_s=2.0, max_s=4.0)
                        break
                    else:
                        # فحص سريع لطابور البناء لمعرفة هل اكتمل المبنى بالفعل وتفرغ الطابور
                        q_check = await self.get_active_build_queues(force_refresh=True)
                        new_q = q_check.get(str(qtype))
                        if not new_q or float(new_q.get("remain_time", 0)) <= 0:
                            total_reduced_sec += int(remain_sec)
                            remain_sec = 0.0
                            bag_items[s_id] = max(0, bag_items.get(s_id, 0) - 1)
                            self.log.info(f"🎉 تم تأكيد إنهاء ترقية {b_name} بنجاح واكتمال الطابور بالسيرفر!")
                            break
                        bag_items[s_id] = 0
                        if self.cached_bag:
                            self.cached_bag[s_id] = 0
                        self.log.warning(f"⚠️ تعذر استلام رد التسريع لـ {b_name} لحزمة {item_name} (كود: {err_code}) — تجربة الحزمة البديلة.")
                        continue

        return total_reduced_sec

    async def speedup_castle(self, qtype: Optional[str] = None) -> int:
        """دالة متوافقة لتسريع القلعة أو لوازمها."""
        queues = await self.get_active_build_queues()
        if qtype and qtype in queues:
            return await self.speedup_queue(qtype)
        for qt, qi in queues.items():
            if str(qi.get("bid")) == "101":
                return await self.speedup_queue(qt, allowed_bids={"101"})
        return 0

    # ═════════════════════════════════════════════════════════════════
    #  دورة التنفيذ الرئيسية (Task Run Loop) — مبسطة ونظيفة
    # ═════════════════════════════════════════════════════════════════

    async def run(self) -> TaskResult:
        cfg = self.config
        do_castle = bool(cfg.get("upgrade_castle", cfg.get("castle", True)))
        do_buildings = bool(cfg.get("upgrade_support_buildings", cfg.get("buildings", cfg.get("support_buildings", True))))
        do_speedup = bool(cfg.get("speedup_castle", cfg.get("speedup", False)))
        check_only = bool(cfg.get("check_only", False))

        # 1. فحص مباني وطوابير المدينة بدقة
        blist = await self.get_city_buildings(force_refresh=True)
        if not blist:
            msg = "⚠️ تعذر جلب بيانات مباني المدينة من السيرفر (1001/1)!"
            self.log.error(msg)
            return TaskResult.fail(msg)

        active_queues = await self.get_active_build_queues(force_refresh=True)
        active_count = len(active_queues)
        max_slots = await self.get_max_build_slots(active_queues=active_queues)
        free_slots = max(0, max_slots - active_count)

        self.log.info(f"📊 طوابير البناء: {active_count}/{max_slots} مشغولة | المتاح للترقية: {free_slots}")
        for qt, qi in active_queues.items():
            b_name = BUILDING_INFO.get(qi['bid'], {}).get("name", f"مبنى #{qi['bid']}")
            self.log.info(f"   • طابور {qt}: {b_name} (مستوى {qi['lv']}) ⏳ متبقي: {format_duration(qi['remain_time'])}")

        castle_item = next((b.get("binfo", {}) for b in blist if str(b.get("binfo", {}).get("bid", "")) == "101"), {})
        walls_item = next((b.get("binfo", {}) for b in blist if str(b.get("binfo", {}).get("bid", "")) == "102"), {})
        castle_lv = int(castle_item.get("lv", 0))
        walls_lv = int(walls_item.get("lv", 0))

        self.log.info(f"🏰 القلعة: مستوى {castle_lv} | 🧱 الأسوار: مستوى {walls_lv}")

        # إذا كانت الطوابير ممتلئة بالكامل ولا يوجد أي طابور شاغر (وليس وضع فحص فقط، والتسريع غير مفعّل)
        if free_slots <= 0 and not check_only and not do_speedup:
            min_remain = min((float(qi.get("remain_time", 0)) for qi in active_queues.values()), default=999999.0)
            if min_remain > 60:
                summary_msg = f"طوابير البناء مشغولة بأوقات طويلة (> دقيقة: {format_duration(min_remain)})"
                self.log.info(f"🛑 {summary_msg}")
                return TaskResult.ok(
                    summary_msg,
                    castle_level=castle_lv,
                    walls_level=walls_lv,
                    active_queues=active_count,
                    free_slots=0,
                    actions=[f"طوابير البناء مشغولة بالكامل ({active_count}/{self.max_build_slots})"]
                )
            else:
                self.log.info(f"⏳ أقل طابور متبقٍ عليه {int(min_remain)} ثانية (≤ دقيقة) — انتظار اكتماله لمواصلة الترقية...")
                await asyncio.sleep(min_remain + round(random.uniform(1.8, 3.2), 2))
                active_queues = await self.get_active_build_queues(force_refresh=True)
                active_count = len(active_queues)
                free_slots = max(0, self.max_build_slots - active_count)

        actions_taken: List[str] = []

        # ─────────────────────────────────────────────────────────────
        #  الحلقة 1: حلقة القلعة وتوابعها (Castle & Prerequisites Loop)
        # ─────────────────────────────────────────────────────────────
        if do_castle:
            if check_only:
                target_castle_lv = castle_lv + 1
                c_res = await self.resolve_and_upgrade_chain("101", target_castle_lv)
                c_actions = c_res.get("actions", [])
                actions_taken.extend(c_actions)
                rec_count = sum(1 for a in c_actions if a.startswith("🔍 [فحص]"))
                free_slots = max(0, free_slots - rec_count)
            else:
                castle_passes = 0
                max_castle_passes = 5  # حماية من الدوران اللانهائي (5 دورات كحد أقصى لتجنب الطلبات المفرطة)

                while castle_passes < max_castle_passes:
                    if not self.conn or not getattr(self.conn, "is_connected", True):
                        k_reason = getattr(self.conn, "kick_reason", "اتصال مقطوع")
                        r_desc = "تم فتح الحساب من جهاز آخر" if k_reason == "other_device" else k_reason
                        self.log.warning(f"🛑 توقف دورة القلعة: انقطع الاتصال بالسيرفر ({r_desc})")
                        break
                    castle_passes += 1

                    # تحديث الطوابير الحالية
                    active_queues = await self.get_active_build_queues(force_refresh=True)
                    free_slots = max(0, self.max_build_slots - len(active_queues))

                    # جلب أحدث بيانات مباني المدينة لمعرفة المستوى المستهدف وشجرة المتطلبات
                    blist = await self.get_city_buildings(force_refresh=True)
                    castle_item = next((b.get("binfo", {}) for b in blist if str(b.get("binfo", {}).get("bid", "")) == "101"), {})
                    castle_lv = int(castle_item.get("lv", 0))
                    target_castle_lv = castle_lv + 1
                    castle_prereq_bids = self.get_castle_prerequisite_bids(target_castle_lv) | {"205", "206"}

                    # 1. تسريع القلعة أو أي من لوازم تطويرها النشطة حالياً (إذا كان التسريع مفعلاً)
                    if do_speedup:
                        for qt, qi in list(active_queues.items()):
                            q_bid = str(qi.get("bid", ""))
                            if q_bid in castle_prereq_bids:
                                q_rem = float(qi.get("remain_time", 0))
                                if q_rem >= 60:
                                    red = await self.speedup_queue(qt, allowed_bids=castle_prereq_bids)
                                    if red > 0:
                                        active_queues = await self.get_active_build_queues(force_refresh=True)
                                        free_slots = max(0, self.max_build_slots - len(active_queues))
                                        blist = await self.get_city_buildings(force_refresh=True)
                                        castle_item = next((b.get("binfo", {}) for b in blist if str(b.get("binfo", {}).get("bid", "")) == "101"), {})
                                        castle_lv = int(castle_item.get("lv", 0))
                                        target_castle_lv = castle_lv + 1
                                        castle_prereq_bids = self.get_castle_prerequisite_bids(target_castle_lv) | {"205", "206"}

                    # شرط التوقف المعتمد: إذا لم تكن هناك طوابير شاغرة (بعد محاولة التسريع)
                    if free_slots <= 0:
                        min_remain = min((float(qi.get("remain_time", 0)) for qi in active_queues.values()), default=999999.0)
                        if 0 < min_remain <= 60:
                            self.log.info(f"⏳ أقل طابور متبقٍ عليه {int(min_remain)} ثانية (≤ دقيقة) — انتظار اكتماله...")
                            await asyncio.sleep(min_remain + round(random.uniform(1.8, 3.2), 2))
                            continue
                        else:
                            self.log.info(f"🛑 أقل طابور متبقٍ عليه أكثر من دقيقة ({format_duration(min_remain)}) — انتهاء حلقة القلعة")
                            break

                    is_castle_upgrading = (str(castle_item.get("state", "0")) == "2") or any(
                        str(q.get("bid")) == "101" for q in active_queues.values()
                    )

                    if is_castle_upgrading:
                        # إذا كانت القلعة نفسها قيد الترقية وسيكتمل بناؤها خلال دقيقة أو أقل:
                        c_q_time = next((float(q.get("remain_time", 0)) for q in active_queues.values() if str(q.get("bid")) == "101"), 999999.0)
                        if 0 < c_q_time <= 60:
                            self.log.info(f"⏳ القلعة قيد الترقية وسيكتمل بناؤها خلال {int(c_q_time)} ثانية — انتظار اكتمالها...")
                            await asyncio.sleep(c_q_time + round(random.uniform(1.8, 3.2), 2))
                            continue

                        note = f"القلعة قيد الترقية حالياً (مستوى {castle_lv})"
                        if note not in actions_taken:
                            actions_taken.append(note)
                        self.log.info(f"⏳ {note}")
                        # القلعة نفسها قيد الترقية بوقت طويل، نخرج من حلقة القلعة لنترك أي طابور شاغر للحلقة 2
                        break

                    if target_castle_lv > 130:
                        note = f"القلعة في الحد الأقصى للمستوى ({castle_lv})"
                        if note not in actions_taken:
                            actions_taken.append(note)
                        break

                    # فحص وترقية شجرة متطلبات القلعة
                    c_res = await self.resolve_and_upgrade_chain("101", target_castle_lv)
                    c_actions = c_res.get("actions", [])
                    if c_actions:
                        actions_taken.extend(c_actions)

                    # إذا تم إطلاق ترقية للقلعة أو أحد لوازمها وكان التسريع مفعّلاً:
                    if do_speedup and (c_res.get("ready", False) or any("بدء ترقية" in a for a in c_actions)):
                        await self.get_active_build_queues(force_refresh=True)
                        castle_prereq_bids = self.get_castle_prerequisite_bids(target_castle_lv) | {"205", "206"}
                        for qt, qi in list(self.active_queues.items()):
                            q_bid = str(qi.get("bid", ""))
                            if q_bid in castle_prereq_bids:
                                q_rem = float(qi.get("remain_time", 0))
                                if q_rem >= 60:
                                    await self.safety_sleep("الاستعداد لتسريع المبنى", min_s=2.0, max_s=4.0)
                                    await self.speedup_queue(qt, allowed_bids=castle_prereq_bids)

                    # تحديث الطوابير الحرة والنشطة فوراً بعد محاولة الترقية
                    active_queues = await self.get_active_build_queues(force_refresh=True)
                    free_slots = max(0, self.max_build_slots - len(active_queues))

                    # التحقق الدقيق مما إذا تم إطلاق أي ترقية في هذه الدورة
                    made_progress = c_res.get("ready", False) or any(
                        "بدء ترقية" in a or "تشييد" in a or "✅" in a for a in c_actions
                    )

                    # فحص أقل وقت متبقٍ بين الطوابير النشطة حالياً
                    min_remain = min((float(qi.get("remain_time", 0)) for qi in active_queues.values()), default=999999.0)

                    # إذا كان هناك طابور نشط مدته دقيقة أو أقل (≤ 60 ثانية):
                    # سواء كانت الطوابير 2/2 أو كان هناك طابور فارغ (1/2):
                    # ننتظره ليستمر البوت ولا يخرج!
                    if 0 < min_remain <= 60:
                        self.log.info(f"⏳ طابور نشط سينتهي خلال {int(min_remain)} ثانية (≤ دقيقة) — انتظار اكتماله لمواصلة الترقية...")
                        await asyncio.sleep(min_remain + round(random.uniform(1.8, 3.2), 2))
                        continue

                    # إذا لم يحدث تقدم في القلعة أو امتلأت الطوابير بأوقات طويلة (> دقيقة):
                    if not made_progress or free_slots <= 0:
                        if free_slots <= 0:
                            self.log.info(f"🛑 طوابير البناء مشغولة بأوقات طويلة ({format_duration(min_remain)}) — انتهاء حلقة القلعة")
                        break

                    await self.safety_sleep("دورة ترقية القلعة وتوابعها")

        # ─────────────────────────────────────────────────────────────
        #  الحلقة 2: حلقة المباني الداعمة ومباني الموارد (Support Buildings Loop)
        # ─────────────────────────────────────────────────────────────
        # تحديث الطوابير الحرة قبل بدء الحلقة 2
        active_queues = await self.get_active_build_queues(force_refresh=True)
        active_count = len(active_queues)
        free_slots = max(0, self.max_build_slots - active_count)

        if do_buildings and free_slots > 0:
            selected_bids = set(self.get_selected_support_bids())

            if check_only:
                city_bids = {str(b.get("binfo", {}).get("bid", "")) for b in blist}
                for s_bid in selected_bids:
                    if free_slots <= 0:
                        break
                    if s_bid not in city_bids:
                        b_title = BUILDING_INFO.get(s_bid, {}).get("name", f"مبنى #{s_bid}")
                        actions_taken.append(f"🔍 [فحص] مطلوب تشييد {b_title} في المدينة")
                        free_slots = max(0, free_slots - 1)

                if free_slots > 0:
                    candidates = []
                    for item in blist:
                        bi = item.get("binfo", {})
                        bid_k = str(bi.get("bid", ""))
                        if bid_k in selected_bids:
                            st = str(bi.get("state", "0"))
                            lv = int(bi.get("lv", 0))
                            if st != "2" and lv < castle_lv:
                                candidates.append(bi)
                    candidates.sort(key=lambda x: int(x.get("lv", 0)))
                    for cand in candidates[:free_slots]:
                        ok, c_actions, _ = await self.upgrade_single_instance(cand)
                        if c_actions:
                            actions_taken.extend(c_actions)
            else:
                support_passes = 0
                max_support_passes = 5  # حماية من الدوران اللانهائي (5 دورات كحد أقصى لتجنب الطلبات المفرطة)

                while support_passes < max_support_passes:
                    if not self.conn or not getattr(self.conn, "is_connected", True):
                        k_reason = getattr(self.conn, "kick_reason", "اتصال مقطوع")
                        r_desc = "تم فتح الحساب من جهاز آخر" if k_reason == "other_device" else k_reason
                        self.log.warning(f"🛑 توقف دورة المباني الداعمة: انقطع الاتصال بالسيرفر ({r_desc})")
                        break
                    support_passes += 1

                    # فحص الطوابير النشطة
                    active_queues = await self.get_active_build_queues(force_refresh=True)
                    free_slots = max(0, self.max_build_slots - len(active_queues))

                    # تسريع الخيم العسكرية (205) والمشافي (206) إن كانت قيد الترقية وكان التسريع مفعلاً
                    if do_speedup:
                        for qt, qi in list(active_queues.items()):
                            q_bid = str(qi.get("bid", ""))
                            if q_bid in ("205", "206"):
                                q_rem = float(qi.get("remain_time", 0))
                                if q_rem >= 60:
                                    red = await self.speedup_queue(qt, allowed_bids={"205", "206"})
                                    if red > 0:
                                        active_queues = await self.get_active_build_queues(force_refresh=True)
                                        free_slots = max(0, self.max_build_slots - len(active_queues))

                    # شرط التوقف المعتمد: إذا لم تكن هناك طوابير شاغرة
                    if free_slots <= 0:
                        min_remain = min((float(qi.get("remain_time", 0)) for qi in active_queues.values()), default=999999.0)
                        if 0 < min_remain <= 60:
                            self.log.info(f"⏳ أقل طابور متبقٍ عليه {int(min_remain)} ثانية (≤ دقيقة) — انتظار اكتماله...")
                            await asyncio.sleep(min_remain + round(random.uniform(1.8, 3.2), 2))
                            continue
                        else:
                            self.log.info(f"🛑 أقل طابور متبقٍ عليه أكثر من دقيقة ({format_duration(min_remain)}) — انتهاء حلقة المباني الداعمة")
                            break

                    blist = await self.get_city_buildings(force_refresh=True)
                    castle_item = next((b.get("binfo", {}) for b in blist if str(b.get("binfo", {}).get("bid", "")) == "101"), {})
                    castle_lv = int(castle_item.get("lv", 0))
                    city_bids = {str(b.get("binfo", {}).get("bid", "")) for b in blist}

                    # 1. تشييد أي مبنى داعم مفقود تماماً (مستوى 0)
                    constructed_any = False
                    for s_bid in selected_bids:
                        if free_slots <= 0:
                            break
                        if s_bid not in city_bids:
                            ok_c, c_m = await self.construct_missing_building(s_bid)
                            if ok_c:
                                actions_taken.append(c_m)
                                constructed_any = True
                                if do_speedup and str(s_bid) in ("205", "206"):
                                    await self.get_active_build_queues(force_refresh=True)
                                    for qt, qi in list(self.active_queues.items()):
                                        if str(qi.get("bid", "")) == str(s_bid):
                                            q_rem = float(qi.get("remain_time", 0))
                                            if q_rem >= 60:
                                                await self.safety_sleep("الاستعداد لتسريع المبنى", min_s=2.0, max_s=4.0)
                                                await self.speedup_queue(qt, allowed_bids={"205", "206"})
                                break
                    if constructed_any:
                        await self.safety_sleep("تشييد مبنى مفقود")
                        continue

                    # 2. جمع كل المباني الداعمة المؤهلة وترتيبها تصاعدياً حسب المستوى
                    candidates = []
                    for item in blist:
                        bi = item.get("binfo", {})
                        bid_k = str(bi.get("bid", ""))
                        if bid_k in selected_bids:
                            st = str(bi.get("state", "0"))
                            lv = int(bi.get("lv", 0))
                            if st != "2" and st != "failed" and lv < castle_lv:
                                candidates.append(bi)

                    if not candidates:
                        self.log.info("✨ جميع المباني الداعمة بلغت مستوى القلعة أو لا توجد مبانٍ مؤهلة")
                        break

                    candidates.sort(key=lambda x: int(x.get("lv", 0)))

                    upgraded_any = False
                    for cand in candidates:
                        if not self.conn or not getattr(self.conn, "is_connected", True):
                            k_reason = getattr(self.conn, "kick_reason", "اتصال مقطوع")
                            r_desc = "تم فتح الحساب من جهاز آخر" if k_reason == "other_device" else k_reason
                            self.log.warning(f"🛑 توقف فحص المباني: انقطع الاتصال بالسيرفر ({r_desc})")
                            break
                        ok, c_actions, reason = await self.upgrade_single_instance(cand)
                        if c_actions:
                            actions_taken.extend(c_actions)
                        if ok:
                            upgraded_any = True
                            cand_bid = str(cand.get("bid", ""))
                            # تسريع الخيمة العسكرية (205) أو المشفى (206) فور ترقيتها إن كان التسريع مفعلاً
                            if do_speedup and cand_bid in ("205", "206"):
                                await self.get_active_build_queues(force_refresh=True)
                                for qt, qi in list(self.active_queues.items()):
                                    if str(qi.get("bid", "")) == cand_bid:
                                        q_rem = float(qi.get("remain_time", 0))
                                        if q_rem >= 60:
                                            await self.safety_sleep("الاستعداد لتسريع المبنى", min_s=2.0, max_s=4.0)
                                            await self.speedup_queue(qt, allowed_bids={"205", "206"})
                            break
                        else:
                            cand["state"] = "failed"
                            if "موارد" in reason or "صناديق" in reason or "انقطع الاتصال" in reason or "-1" in reason or "طوابير البناء ممتلئة" in reason or "1008" in reason:
                                if "-1" in reason and (not self.conn or not getattr(self.conn, "is_connected", True)):
                                    k_reason = getattr(self.conn, "kick_reason", "اتصال مقطوع")
                                    r_desc = "تم فتح الحساب من جهاز آخر" if k_reason == "other_device" else k_reason
                                    self.log.warning(f"🛑 توقف فحص المباني: انقطع الاتصال بالسيرفر ({r_desc})")
                                break

                    # تحديث الطوابير بعد محاولة ترقية المبنى الداعم
                    active_queues = await self.get_active_build_queues(force_refresh=True)
                    free_slots = max(0, self.max_build_slots - len(active_queues))
                    min_remain = min((float(qi.get("remain_time", 0)) for qi in active_queues.values()), default=999999.0)

                    # إذا كان هناك طابور سينتهي خلال دقيقة أو أقل: ننتظره ونستمر سواء بقي طابور فارغ أو امتلأت الطوابير
                    if 0 < min_remain <= 60:
                        self.log.info(f"⏳ طابور نشط سينتهي خلال {int(min_remain)} ثانية (≤ دقيقة) — انتظار اكتماله لمواصلة الترقية...")
                        await asyncio.sleep(min_remain + round(random.uniform(1.8, 3.2), 2))
                        continue

                    if not upgraded_any or free_slots <= 0:
                        if free_slots <= 0:
                            self.log.info(f"🛑 طوابير البناء مشغولة بأوقات طويلة ({format_duration(min_remain)}) — انتهاء حلقة المباني الداعمة")
                        break

                    await self.safety_sleep("دورة ترقية المبنى الداعم")

        # ─────────────────────────────────────────────────────────────
        #  النتيجة والملخص النظيف
        # ─────────────────────────────────────────────────────────────
        active_queues = await self.get_active_build_queues(force_refresh=True)
        active_count = len(active_queues)
        free_slots = max(0, self.max_build_slots - active_count)

        unique_actions = list(dict.fromkeys(actions_taken))
        if not unique_actions:
            if active_count >= self.max_build_slots:
                summary_msg = f"طوابير البناء مشغولة بالكامل ({active_count}/{self.max_build_slots})"
            else:
                summary_msg = "لا توجد ترقيات جديدة متاحة حالياً"
        else:
            primary_act = unique_actions[0]
            if len(unique_actions) > 1:
                summary_msg = f"{primary_act} (+{len(unique_actions) - 1} إجراءات)"
            else:
                summary_msg = primary_act

        self.log.info(f"🏁 النتيجة: {summary_msg}")

        # فحص هل تم إطلاق أو إكمال أي ترقية أو تسريع أو بناء فعلي في هذه الدورة
        has_upgrade = any(
            any(w in act for w in ["بدأ بناء", "بدأت ترقية", "تم تسريع", "اكتملت ترقية", "بدء ترقية", "تشييد"])
            for act in unique_actions
        )

        is_blocked_by_res = not has_upgrade and any("نقص موارد" in act or "الصناديق غير كافية" in act for act in unique_actions)
        is_blocked_by_items = not has_upgrade and any("نقص أدوات" in act or "وسام الحرب" in act for act in unique_actions)

        if is_blocked_by_res:
            return TaskResult.fail(
                summary_msg,
                castle_level=castle_lv,
                walls_level=walls_lv,
                active_queues=active_count,
                free_slots=free_slots,
                actions=unique_actions,
                code="NO_RESOURCES"
            )
        elif is_blocked_by_items:
            return TaskResult.fail(
                summary_msg,
                castle_level=castle_lv,
                walls_level=walls_lv,
                active_queues=active_count,
                free_slots=free_slots,
                actions=unique_actions,
                code="NO_ITEMS"
            )

        return TaskResult.ok(
            summary_msg,
            castle_level=castle_lv,
            walls_level=walls_lv,
            active_queues=active_count,
            free_slots=free_slots,
            actions=unique_actions
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (CLI Runner) — تصميم مبسط وأنيق
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Empire Building Upgrade Task — مهمة ترقية القلعة والمباني المتقدمة"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--castle", dest="castle", action="store_true", default=None, help="ترقية القلعة وتوابعها فقط [أو كلاهما إذا لم يحدد أي خيار]")
    parser.add_argument("--no-castle", dest="castle", action="store_false", help="تعطيل ترقية القلعة")
    parser.add_argument("--buildings", "--resources", dest="buildings", action="store_true", default=None, help="ترقية مباني الموارد والمعسكرات فقط")
    parser.add_argument("--no-buildings", dest="buildings", action="store_false", help="تعطيل ترقية مباني الموارد والمعسكرات")
    parser.add_argument("--speedup", "--speedup-castle", dest="speedup_castle", action="store_true", default=False, help="تسريع ترقية القلعة بالأدوات المجانية والحقيبة")
    parser.add_argument("--no-chests", dest="auto_chests", action="store_false", default=True, help="تعطيل فتح صناديق الموارد التلقائي")
    parser.add_argument("--check-only", "-c", action="store_true", help="فحص وعرض الترقيات الموصى بها دون إجراء الترقية")
    parser.add_argument("--all-accounts", action="store_true", help="تشغيل المهمة لجميع الحسابات المسجلة")

    # خيارات تفصيل وتحديد المباني الداعمة
    parser.add_argument("--farm", dest="bld_farm", action="store_true", default=None, help="ترقية مزارع القمح (201)")
    parser.add_argument("--no-farm", dest="bld_farm", action="store_false", help="تعطيل ترقية مزارع القمح")
    parser.add_argument("--sawmill", "--wood", dest="bld_sawmill", action="store_true", default=None, help="ترقية مناشر الخشب (202)")
    parser.add_argument("--no-sawmill", "--no-wood", dest="bld_sawmill", action="store_false", help="تعطيل ترقية مناشر الخشب")
    parser.add_argument("--iron", "--iron-mine", dest="bld_iron", action="store_true", default=None, help="ترقية مناجم الحديد (203)")
    parser.add_argument("--no-iron", "--no-iron-mine", dest="bld_iron", action="store_false", help="تعطيل ترقية مناجم الحديد")
    parser.add_argument("--quartz", "--quartz-mine", dest="bld_quartz", action="store_true", default=None, help="ترقية مناجم الكوارتز (204)")
    parser.add_argument("--no-quartz", "--no-quartz-mine", dest="bld_quartz", action="store_false", help="تعطيل ترقية مناجم الكوارتز")
    parser.add_argument("--hospital", "--clinic", dest="bld_hospital", action="store_true", default=None, help="ترقية الخيمة الطبية / المشفى (206)")
    parser.add_argument("--no-hospital", "--no-clinic", dest="bld_hospital", action="store_false", help="تعطيل ترقية المشفى")
    parser.add_argument("--military-tent", "--tent", dest="bld_tent", action="store_true", default=None, help="ترقية الخيمة العسكرية (205)")
    parser.add_argument("--no-military-tent", "--no-tent", dest="bld_tent", action="store_false", help="تعطيل ترقية الخيمة العسكرية")
    parser.add_argument("--target-buildings", dest="target_buildings", default=None, help="المباني المستهدفة مفصولة بفاصلة أو all")
    args = parser.parse_args()

    # تحديد رغبة المستخدم بناءً على الأعلام الممررة:
    # 1. إذا لم يُحدد أي علم: تفعيل القلعة والمباني الداعمة معاً (الوضع الافتراضي)
    # 2. إذا حدد --castle فقط دون --buildings: تفعيل القلعة وتوابعها فقط وتعطيل المباني الداعمة
    # 3. إذا حدد --buildings فقط دون --castle: تفعيل المباني الداعمة فقط وتعطيل القلعة
    castle_flag = args.castle
    buildings_flag = args.buildings

    if castle_flag is None and buildings_flag is None:
        resolved_castle = True
        resolved_buildings = True
    elif castle_flag is True and buildings_flag is None:
        resolved_castle = True
        resolved_buildings = True  # القلعة أولاً، وإذا بقيت طوابير شاغرة تُشغل بالمباني الداعمة
    elif buildings_flag is True and castle_flag is None:
        resolved_castle = False
        resolved_buildings = True
    else:
        resolved_castle = bool(castle_flag) if castle_flag is not None else True
        resolved_buildings = bool(buildings_flag) if buildings_flag is not None else True

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    logging.getLogger("onemt").setLevel(logging.WARNING)

    from core.session_manager import SessionManager

    async def _run_for_account(acc_email: str, acc_obj: Any):
        print("\n" + "═" * 68)
        print(f"🏰 الحساب: {acc_email}")
        print("═" * 68)

        conn = GameConnection(acc_obj)
        if not await conn.connect():
            print(f"❌ فشل الاتصال بالحساب {acc_email}!")
            return

        for _ in range(12):
            await asyncio.sleep(round(random.uniform(0.3, 0.7), 2))
            if len(conn.init_data) > 0:
                break

        # معالجة تفضيلات المباني
        target_buildings = {}
        if args.target_buildings:
            if args.target_buildings.strip().lower() == "all":
                target_buildings = {k: True for k in ["farm", "sawmill", "iron_mine", "quartz_mine", "hospital", "military_tent"]}
            else:
                items = [x.strip().lower() for x in args.target_buildings.split(",") if x.strip()]
                target_buildings = {k: (k in items or BUILDING_KEY_TO_BID.get(k) in items) for k in ["farm", "sawmill", "iron_mine", "quartz_mine", "hospital", "military_tent"]}

        specific_flags = [args.bld_farm, args.bld_sawmill, args.bld_iron, args.bld_quartz, args.bld_hospital, args.bld_tent]
        if any(x is not None for x in specific_flags):
            has_positive = any(x is True for x in specific_flags)
            default_val = False if has_positive else True
            target_buildings = {
                "farm": default_val if args.bld_farm is None else bool(args.bld_farm),
                "sawmill": default_val if args.bld_sawmill is None else bool(args.bld_sawmill),
                "iron_mine": default_val if args.bld_iron is None else bool(args.bld_iron),
                "quartz_mine": default_val if args.bld_quartz is None else bool(args.bld_quartz),
                "hospital": default_val if args.bld_hospital is None else bool(args.bld_hospital),
                "military_tent": default_val if args.bld_tent is None else bool(args.bld_tent),
            }

        task_cfg = {
            "upgrade_castle": resolved_castle,
            "castle": resolved_castle,
            "upgrade_support_buildings": resolved_buildings,
            "buildings": resolved_buildings,
            "speedup_castle": args.speedup_castle,
            "auto_open_chests": args.auto_chests,
            "check_only": args.check_only,
            "target_buildings": target_buildings,
        }

        task = BuildingTask(conn, task_cfg)
        await task.on_start()
        res = await task.run()

        # طباعة تقرير مقتضب وبسيط وأنيق
        print("\n" + "─" * 68)
        print("📊 ملخص حالة البناء:")
        if task.active_queues:
            for qt, qi in task.active_queues.items():
                b_name = BUILDING_INFO.get(str(qi.get('bid', '')), {}).get("name", f"مبنى #{qi.get('bid')}")
                rem_str = format_duration(qi.get("remain_time", 0))
                print(f"   • طابور {qt}: ⏳ {b_name} (المستوى {qi.get('lv')}) — متبقي: {rem_str}")

        actions = res.data.get("actions", []) if res.data else []
        non_queue_actions = [a for a in actions if not a.startswith("⏳")]
        if non_queue_actions:
            print("💡 الإجراءات / التوصيات:")
            for act in non_queue_actions:
                print(f"   • {act}")
        elif not task.active_queues:
            print(f"   • {res.message}")
        print("─" * 68)

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
            if email.startswith("azjfhf"):
                continue
            await _run_for_account(email, acc)

    asyncio.run(_main())
