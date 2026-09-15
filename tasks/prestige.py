# -*- coding: utf-8 -*-
"""
tasks/prestige.py — مهمة مهام الهيبة اليومية المستقلة (Daily Prestige / Honor Quests Task)
══════════════════════════════════════════════════════════════════════════════════════════
تُنفّذ هذه المهمة المتكاملة مهام الهيبة اليومية (مهام المجد اليومية) للحصول على نقاط النشاط
وصناديق الجوائز الكبرى في اللعبة:

المرحلة 1: متجر المهربين (Smuggler Store / Traveling Merchant - CMD 1024)
  • فحص بضائع متجر المهربين / التاجر المتجول.
  • شراء كافة السلع المعروضة بالموارد العادية حصراً:
      - 1002: القمح / الطعام (Food)
      - 1003: الخشب (Wood)
      - 1004: الحديد (Iron)
      - 1005: الفضة / الألماس (Silver / Mithril)
  • ⛔ ممنوع منعاً باتاً الشراء بالذهب (1001 أو 1006) أو إنفاق أي ذهب في التحديث.
  • الاستفادة من التحديثات المجانية فقط (refreshGold == 0).

المرحلة 2: جمع الموارد الأربعة خارج القلعة (4 Resource Gathering Marches)
  • إرسال هجوم/مسيرة جمع واحدة مؤكدة لكل مورد من الموارد الأربعة:
      1. مزارع القمح (Food / subType: 1)
      2. مناشر الخشب (Wood / subType: 2)
      3. مناجم الحجر (Stone / subType: 3)
      4. مناجم الحديد (Iron / subType: 4)
  • ضبط حمولة كل مسيرة بشكل ضروري على: currentSourceNum = 25000
  • اختيار جيش تلقائي كافٍ لحمل 25,000 مورد فقط (~2,000 إلى 3,000 جندي) للحفاظ على بقية الجيش.
  • اختيار البطل المتاح والحيوان الأليف المتاح تلقائياً.
  • تطبيق فواصل أمان بشرية غير منتظمة لمكافحة الحظر.

المرحلة 3: استعراض نقاط الهيبة وصناديق الجوائز اليومية
  • قراءة بيانات meritoriousTaskCtrl وتلخيص التقدم اليومي.

طريقة التشغيل كملف مستقل:
  python tasks/prestige.py --email "fahed.K140@gmail.com"
  python tasks/prestige.py --email "fahed.K140@gmail.com" --password "mn@123450"
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from tasks.monster import MonsterTask
from tasks.stronghold import StrongholdTask
from tasks.watermill import WatermillTask
from tasks.train import TrainTask
from tasks.fortress import FortressTask
from game_client import GameConnection

# ── إعدادات مهمة الهجوم على الغزاة (Invaders) في مهام الهيبة ────────
PRESTIGE_INVADERS_CONFIG: Dict[str, Any] = {
    "count": 5,                 # عدد الهجمات المطلوبة (5 غزاة لمهام الهيبة)
    "min_lv": 1,                # أدنى مستوى للغزاة
    "max_lv": 30,               # أقصى مستوى للغزاة (يحدده المستخدم)
    "search_range": 80,         # نطاق البحث (كم) حول القلعة / المنطقة
    "formation_id": 0,          # 0 = اختيار ديناميكي تلقائي للأبطال والجيش بدون تشكيلة ثابتة
    "troops_count": 30000,      # عدد جنود القتال المناسب
    "wait_for_queue": True,     # الانتظار الذكي عند امتلاء الفيالق حتى عودتها
    "wait_interval": 15.0,      # ثواني الانتظار بين دورات فحص الفيالق العائدة
    "center_x": None,           # إحداثي X للمنطقة (None = موقع القلعة تلقائياً)
    "center_y": None,           # إحداثي Y للمنطقة (None = موقع القلعة تلقائياً)
}

# ── إعدادات مهمة الهجوم على المعقل / الملجأ (Strongholds) في مهام الهيبة ─
PRESTIGE_STRONGHOLD_CONFIG: Dict[str, Any] = {
    "count": 2,                 # عدد المعاقل / الملاجئ المستهدفة (معقلين/ملجأين لمهام الهيبة)
    "min_lv": 1,                # أدنى مستوى للمعقل
    "max_lv": 30,               # أقصى مستوى للمعقل
    "search_range": 80,         # نطاق البحث (كم) حول القلعة
    "formation_id": 0,          # 0 = اختيار ديناميكي تلقائي للأبطال والجيش بدون تشكيلة ثابتة
    "troops_count": 30000,      # عدد جنود القتال المناسب
    "wait_for_queue": True,     # الانتظار الذكي عند امتلاء الفيالق حتى عودتها
    "wait_interval": 15.0,      # ثواني الانتظار بين دورات فحص الفيالق العائدة
    "center_x": None,           # إحداثي X للمنطقة (None = موقع القلعة تلقائياً)
    "center_y": None,           # إحداثي Y للمنطقة (None = موقع القلعة تلقائياً)
}

# ── الموارد والسلع المسموح الشراء بها في متجر المهربين ──────────────
ALLOWED_SMUGGLER_CURRENCIES: Dict[int, Dict[str, str]] = {
    1002: {"name": "قمح", "icon": "🌾"},
    1003: {"name": "خشب", "icon": "🪵"},
    1004: {"name": "حديد", "icon": "⛏️"},
    1005: {"name": "فضة/ألماس", "icon": "💎"}
}
DISALLOWED_CURRENCIES: Set[int] = {1001, 1006}  # الذهب والعملات الخاصة - ممنوع نهائياً

# ── معرفات مهام الهيبة / المجد اليومية (meritoriousTaskCtrl) ───────
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "smuggler": 4112020,     # متجر المهربين (10 مشتريات)
    "invaders": 4112028,     # مهاجمة الغزاة (5 هجمات)
    "stronghold": 4112030,   # احتلال المعقل / الملجأ (مرتان)
    "food": 4112000,         # جمع القمح (25,000)
    "wood": 4112001,         # جمع الخشب (25,000)
    "stone": 4112002,        # جمع الحجر (4,000)
    "iron": 4112003,         # جمع الحديد (2,000)
}

# أسماء وتسميات مهام الهيبة للعرض والتقارير
PRESTIGE_QUEST_NAMES: Dict[str, str] = {
    "smuggler": "متجر المهربين (10 مشتريات بالموارد)",
    "invaders": "قتال الغزاة (5 هجمات)",
    "stronghold": "احتلال المعقل / الملجأ (مرتان)",
    "food": "جمع القمح / الطعام (25,000)",
    "wood": "جمع الخشب (25,000)",
    "stone": "جمع الحجر (4,000)",
    "iron": "جمع الحديد (2,000)",
}

# ── أسماء وتسميات المهام الفرعية لمهام الهيبة ──────────────────────
PRESTIGE_SUBTASKS_ALL: List[str] = [
    "smuggler",
    "invaders",
    "stronghold",
    "gather",
    "watermill",
    "train",
    "fortress",
]

PRESTIGE_SUBTASK_ALIASES: Dict[str, str] = {
    # 1. متجر المهربين
    "smuggler": "smuggler", "المهربين": "smuggler", "متجر": "smuggler", "متجر المهربين": "smuggler", "shop": "smuggler",
    # 2. قتال الغزاة
    "invaders": "invaders", "الغزاة": "invaders", "غزاة": "invaders", "monsters": "invaders", "invader": "invaders",
    # 3. المعاقل / الملاجئ
    "stronghold": "stronghold", "المعاقل": "stronghold", "معاقل": "stronghold", "الملاجئ": "stronghold", "ملجأ": "stronghold", "shelter": "stronghold",
    # 4. جمع الموارد
    "gather": "gather", "الجمع": "gather", "جمع": "gather", "جمع الموارد": "gather", "resources": "gather",
    # 5. الساقية
    "watermill": "watermill", "الساقية": "watermill", "ساقية": "watermill", "طاحونة": "watermill",
    # 6. تدريب الجنود
    "train": "train", "تدريب": "train", "الجنود": "train", "تدريب الجنود": "train", "troops": "train",
    # 7. حصن الحرب
    "fortress": "fortress", "حصن": "fortress", "الحصن": "fortress", "فخاخ": "fortress", "حصن الحرب": "fortress", "traps": "fortress",
}

# ── تعريفات الموارد الأربعة لجمع مهام الهيبة ───────────────────────
PRESTIGE_RESOURCES = [
    {"type": 2, "name": "مزارع القمح (Food)",  "icon": "🌾", "res_code": 1001, "quest_id": 4112000, "quest_key": "food"},
    {"type": 3, "name": "مناشر الخشب (Wood)",  "icon": "🪵", "res_code": 1002, "quest_id": 4112001, "quest_key": "wood"},
    {"type": 4, "name": "مناجم الحجر (Stone)", "icon": "🪨", "res_code": 1003, "quest_id": 4112002, "quest_key": "stone"},
    {"type": 5, "name": "مناجم الحديد (Iron)",  "icon": "⛏️", "res_code": 1004, "quest_id": 4112003, "quest_key": "iron"},
]

REQUIRED_SOURCE_NUM = 25000  # القيمة المستهدفة لمهام الهيبة اليومية (25,000 مورد)

TARGET_LOAD_CAPACITY = 25000  # سقف حمولة الجيش القصوى (25,000 مورد) ليعود فور امتلائه

# تقدير حمولة الوحدة الواحدة حسب صنف القوة في القلاع المتقدمة (مع احتساب أبحاث ومهارات اللورد):
# عربات (7xx): ~100 مورد لكل عربة (250 عربة = 25,000 حمولة)
# مشاة (4xx): ~30 مورد لكل جندي (834 جندي = 25,000 حمولة)
# فرسان (5xx): ~25 مورد لكل جندي (1,000 جندي = 25,000 حمولة)
# رماة (6xx): ~28 مورد لكل جندي (893 جندي = 25,000 حمولة)
UNIT_LOAD_RATES: Dict[int, int] = {
    7: 100,  # عربات الحصار والنقل
    4: 30,   # مشاة
    5: 25,   # فرسان
    6: 28,   # رماة
}


def get_unit_load(tid: int) -> int:
    """إرجاع سعة الحمولة التقديرية لوحدة الجندي بناءً على فئته في القلعة المتقدمة."""
    category = tid // 100
    return UNIT_LOAD_RATES.get(category, 25)


def select_prestige_army(available: Dict[int, int], target_capacity: int = TARGET_LOAD_CAPACITY) -> Tuple[List[Dict[str, int]], int]:
    """
    اختيار تشكيلة جيش محسوبة الحمولة بدقة بالغة بحيث لا تتجاوز سعتها القصوى 25,000 مورد.

    السر التقني:
    سيرفر اللعبة ينهي الجمع فور امتلاء حمولة الجيش بنسبة 100%.
    عند إرسال 250 عربة فقط (حمولة 25,000 مورد بالضبط)، تمتلئ العربات عند 25k مورد
    ويقوم السيرفر بإعادتها فوراً إلى القلعة تلقائياً، تاركاً باقي الحقل سليماً دون استنزافه!
    """
    import math

    carts, infantry, cavalry, archers = [], [], [], []

    for tid, count in available.items():
        if count <= 0:
            continue
        if 700 <= tid < 800:
            carts.append((tid, count))
        elif 400 <= tid < 500:
            infantry.append((tid, count))
        elif 500 <= tid < 600:
            cavalry.append((tid, count))
        elif 600 <= tid < 700:
            archers.append((tid, count))

    # ترتيب من الأعلى إلى الأدنى
    carts.sort(key=lambda x: x[0], reverse=True)
    infantry.sort(key=lambda x: x[0], reverse=True)
    cavalry.sort(key=lambda x: x[0], reverse=True)
    archers.sort(key=lambda x: x[0], reverse=True)

    priority_groups = [carts, infantry, cavalry, archers]
    army_list = []
    rem_capacity = target_capacity
    total_capacity = 0

    for group in priority_groups:
        for tid, count in group:
            avail = available.get(tid, 0)
            if avail <= 0:
                continue
            unit_cap = get_unit_load(tid)
            needed_units = max(1, math.ceil(rem_capacity / unit_cap))
            take = min(avail, needed_units)
            if take > 0:
                army_list.append({"id": tid, "num": take})
                available[tid] -= take
                load_added = take * unit_cap
                rem_capacity -= load_added
                total_capacity += load_added
                if rem_capacity <= 0:
                    break
        if rem_capacity <= 0:
            break

    return army_list, total_capacity


def pick_available_hero(heroes: list, busy: Set[int]) -> Optional[int]:
    """
    اختيار أي بطل متاح غير مشغول:
    1. أبطال الجمع (5502xxx) كأولوية أولى.
    2. أي بطل آخر متاح كأولوية بديلة.
    """
    gather_heroes = []
    other_heroes = []

    for h in heroes:
        if not isinstance(h, dict):
            continue
        hid = h.get('id')
        if not hid:
            continue
        try:
            hid_int = int(hid)
        except Exception:
            continue

        if hid_int in busy:
            continue
        if h.get('status', {}).get('state', 0) != 0:
            continue

        if str(hid_int).startswith('5502'):
            gather_heroes.append(hid_int)
        else:
            other_heroes.append(hid_int)

    candidates = gather_heroes or other_heroes
    return candidates[0] if candidates else None


def pick_available_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]:
    """اختيار أي حيوان أليف متاح في القلعة."""
    pets_data = conn.init_data.get('petCtrl', {}).get('pets', {})
    if not isinstance(pets_data, dict) or not pets_data:
        return []

    available = []
    for pid_str, pinfo in pets_data.items():
        try:
            pid = int(pid_str)
            if pid not in used_pets:
                lv = int(pinfo.get('lv', 1))
                available.append((pid, lv))
        except Exception:
            continue

    if not available:
        return []

    available.sort(key=lambda x: x[1], reverse=True)
    chosen = available[0][0]
    used_pets.add(chosen)
    return [chosen]


# ════════════════════════════════════════════════════════════════════
#  كلاس مهمة مهام الهيبة (PrestigeTask)
# ════════════════════════════════════════════════════════════════════

class PrestigeTask(BaseTask):
    """
    مهمة مهام الهيبة اليومية:
      1. متجر المهربين: الشراء بالموارد العادية فقط بدون أي ذهب.
      2. جمع الموارد الأربعة خارج القلعة (قمح، خشب، حجر، حديد) بـ currentSourceNum = 25000.
    """
    name = "prestige"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self.search_range = int(self.config.get("search_range", 120))
        self.min_lv = int(self.config.get("min_lv", 1))
        self.max_lv = int(self.config.get("max_lv", 7))
        self.target_source_num = int(self.config.get("target_source_num", REQUIRED_SOURCE_NUM))
        self.target_capacity = int(self.config.get("target_capacity", TARGET_LOAD_CAPACITY))
        # عدد المشتريات المستهدفة من متجر المهربين (10 مرات لمهام الهيبة)
        self.target_smuggler_buys = int(self.config.get("smuggler_buys", self.config.get("target_buys", 10)))
        self.max_gold_refresh = int(self.config.get("max_gold_refresh", 20))

        # إعدادات مهمة الغزاة (5 هجمات) لمهام الهيبة
        inv_cfg = self.config.get("invaders", {}) if isinstance(self.config.get("invaders"), dict) else {}
        self.invaders_count = int(self.config.get("invaders_count", inv_cfg.get("count", PRESTIGE_INVADERS_CONFIG["count"])))
        self.invaders_min_lv = int(self.config.get("invaders_min_lv", inv_cfg.get("min_lv", PRESTIGE_INVADERS_CONFIG["min_lv"])))
        self.invaders_max_lv = int(self.config.get("invaders_max_lv", inv_cfg.get("max_lv", PRESTIGE_INVADERS_CONFIG["max_lv"])))
        self.invaders_range = int(self.config.get("invaders_range", inv_cfg.get("search_range", PRESTIGE_INVADERS_CONFIG["search_range"])))
        self.invaders_formation = int(self.config.get("invaders_formation", inv_cfg.get("formation_id", PRESTIGE_INVADERS_CONFIG["formation_id"])))
        self.invaders_troops = int(self.config.get("invaders_troops", inv_cfg.get("troops_count", PRESTIGE_INVADERS_CONFIG["troops_count"])))
        self.invaders_center_x = self.config.get("invaders_x", inv_cfg.get("center_x", PRESTIGE_INVADERS_CONFIG["center_x"]))
        self.invaders_center_y = self.config.get("invaders_y", inv_cfg.get("center_y", PRESTIGE_INVADERS_CONFIG["center_y"]))
        self.invaders_wait_queue = bool(self.config.get("invaders_wait_queue", inv_cfg.get("wait_for_queue", PRESTIGE_INVADERS_CONFIG["wait_for_queue"])))

        # إعدادات مهمة المعاقل / الملاجئ (ملجأين) لمهام الهيبة
        sh_cfg = self.config.get("stronghold", {}) if isinstance(self.config.get("stronghold"), dict) else {}
        self.stronghold_count = int(self.config.get("stronghold_count", sh_cfg.get("count", PRESTIGE_STRONGHOLD_CONFIG["count"])))
        self.stronghold_min_lv = int(self.config.get("stronghold_min_lv", sh_cfg.get("min_lv", PRESTIGE_STRONGHOLD_CONFIG["min_lv"])))
        self.stronghold_max_lv = int(self.config.get("stronghold_max_lv", sh_cfg.get("max_lv", PRESTIGE_STRONGHOLD_CONFIG["max_lv"])))
        self.stronghold_range = int(self.config.get("stronghold_range", sh_cfg.get("search_range", PRESTIGE_STRONGHOLD_CONFIG["search_range"])))
        self.stronghold_formation = int(self.config.get("stronghold_formation", sh_cfg.get("formation_id", PRESTIGE_STRONGHOLD_CONFIG["formation_id"])))
        self.stronghold_troops = int(self.config.get("stronghold_troops", sh_cfg.get("troops_count", PRESTIGE_STRONGHOLD_CONFIG["troops_count"])))
        self.stronghold_center_x = self.config.get("stronghold_x", sh_cfg.get("center_x", PRESTIGE_STRONGHOLD_CONFIG["center_x"]))
        self.stronghold_center_y = self.config.get("stronghold_y", sh_cfg.get("center_y", PRESTIGE_STRONGHOLD_CONFIG["center_y"]))
        self.stronghold_wait_queue = bool(self.config.get("stronghold_wait_queue", sh_cfg.get("wait_for_queue", PRESTIGE_STRONGHOLD_CONFIG["wait_for_queue"])))

        # ── إعدادات التحكم في كل مهمة فرعية على حدة ───────────────
        self.subtasks_config = self.config.get("subtasks", {})

        self._heroes: List[Dict[str, Any]] = []
        self._busy_heroes: Set[int] = set()
        self._used_army: Dict[int, int] = {}
        self._used_pets: Set[int] = set()
        self._excluded_targets: Set[str] = set()

    def is_subtask_enabled(self, subtask_name: str) -> bool:
        """
        فحص ما إذا كانت مهمة فرعية محددة من مهام الهيبة مفعلة من المستخدم.
        يدعم تمرير القيمة كـ dict أو list أو str أو أعلام فردية.
        """
        key = PRESTIGE_SUBTASK_ALIASES.get(subtask_name.strip().lower(), subtask_name.strip().lower())

        # 1. إذا حُددت في subtasks كقاموس (dict)
        if isinstance(self.subtasks_config, dict) and self.subtasks_config:
            for k, v in self.subtasks_config.items():
                if PRESTIGE_SUBTASK_ALIASES.get(str(k).strip().lower(), str(k).strip().lower()) == key:
                    return bool(v)

        # 2. إذا حُددت كقائمة (list) أو مجموعة (set)
        elif isinstance(self.subtasks_config, (list, tuple, set)):
            norm_set = {PRESTIGE_SUBTASK_ALIASES.get(str(x).strip().lower(), str(x).strip().lower()) for x in self.subtasks_config}
            return key in norm_set

        # 3. إذا حُددت كنص (str) مفصول بفواصل
        elif isinstance(self.subtasks_config, str):
            val = self.subtasks_config.strip().lower()
            if val in ("all", "الكل", "all_tasks"):
                return True
            tokens = {PRESTIGE_SUBTASK_ALIASES.get(t.strip(), t.strip()) for t in val.replace("،", ",").split(",") if t.strip()}
            return key in tokens

        # 4. فحص الخيار المباشر في config العام (مثل enable_smuggler أو smuggler)
        direct_key = f"enable_{key}"
        if direct_key in self.config:
            return bool(self.config[direct_key])
        if key in self.config and isinstance(self.config[key], bool):
            return bool(self.config[key])

        # الافتراضي: تفعيل المهمة
        return True

    async def on_start(self):

        """انتظار بيانات القلعة والأبطال ومهام الهيبة عند بدء المهمة."""
        for _ in range(30):
            has_city = "cityCtrl" in self.conn.init_data
            has_heroes = bool((self.conn._gate and getattr(self.conn._gate, 'heroes', None)) or self.conn.init_data.get('heroCtrl'))
            has_merit = "meritoriousTaskCtrl" in self.conn.init_data
            if has_city and has_heroes and has_merit:
                break
            await asyncio.sleep(0.3)
        await self._load_heroes()

    async def _refresh_merit_data(self) -> bool:
        """
        تجديد بيانات meritoriousTaskCtrl من السيرفر قبل فحص حالة مهام الهيبة.

        الآلية:
          - نُسجّل البصمة الحالية لـ meritoriousTaskCtrl (لمعرفة إذا تغيّرت).
          - نُرسل استعلام 1024/1 (متجر المهربين) الذي يؤدي عادةً
            إلى إرسال السيرفر push يحدّث meritoriousTaskCtrl في retdata.
          - ننتظر حتى 3 ثوانٍ لاستقبال البيانات المحدَّثة.
          - نُعيد True إذا تم التحديث، False إذا لم يتغير شيء.
        """
        # نسجل الحالة الحالية (بصمة JSON) لمعرفة متى تُحدَّث
        merit_before = self.conn.init_data.get("meritoriousTaskCtrl", {})
        snapshot_before = json.dumps(
            {k: v.get("cNum", 0) if isinstance(v, dict) else v
             for k, v in (merit_before.get("taskData", {}) if isinstance(merit_before, dict) else {}).items()},
            sort_keys=True
        )

        # نُرسل استعلام 1024/1 لتحفيز السيرفر على إرسال push بالبيانات الحديثة
        try:
            r = await self.conn.query("1024", "1", {}, timeout=6)
            # السيرفر يرسل retdata يحتوي على meritoriousTaskCtrl ضمن Push
        except Exception:
            pass

        # ننتظر حتى 3 ثوانٍ لاستقبال push التحديث
        for _ in range(30):
            await asyncio.sleep(0.1)
            merit_now = self.conn.init_data.get("meritoriousTaskCtrl", {})
            snapshot_now = json.dumps(
                {k: v.get("cNum", 0) if isinstance(v, dict) else v
                 for k, v in (merit_now.get("taskData", {}) if isinstance(merit_now, dict) else {}).items()},
                sort_keys=True
            )
            if snapshot_now != snapshot_before:
                self.log.info("✅ [تجديد مهام الهيبة] تم استقبال بيانات محدَّثة من السيرفر بنجاح.")
                return True

        self.log.info("ℹ️ [تجديد مهام الهيبة] البيانات الحالية هي أحدث نسخة متاحة (لم يرد push جديد).")
        return False


    def get_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]:
        """
        الاستعلام عن حالة مهمة محددة من مهام الهيبة / المجد (meritoriousTaskCtrl):
        تُرجع:
          - 'id': رقم معرف المهمة في السيرفر
          - 'found': هل المهمة مسجلة في بيانات السيرفر
          - 'is_done': هل المهمة مكتملة بالفعل (status in (4, 5) أو c_num >= l_num)
          - 'status': كود حالة المهمة (1=تحضير, 2=إنجاز, 4=مكتملة, 5=مستلمة)
          - 'c_num': التقدم المنجز الحالي
          - 'l_num': المستهدف المطلوب
          - 'remaining': المتبقي للإنجاز
        """
        qid = PRESTIGE_QUEST_IDS.get(quest_key_or_id, quest_key_or_id) if isinstance(quest_key_or_id, str) else quest_key_or_id
        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        task_data = merit.get("taskData", {}) if isinstance(merit, dict) else {}
        tinfo = None
        if isinstance(task_data, dict):
            tinfo = task_data.get(str(qid)) or task_data.get(int(qid))

        if not tinfo or not isinstance(tinfo, dict):
            return {
                "id": qid,
                "found": False,
                "is_done": False,
                "status": 0,
                "c_num": 0,
                "l_num": 0,
                "remaining": 0,
            }

        c_num = int(tinfo.get("cNum", 0))
        l_num = int(tinfo.get("lNum", 0))
        status = int(tinfo.get("status", 2))
        is_done = (status in (4, 5)) or (l_num > 0 and c_num >= l_num)
        remaining = max(0, l_num - c_num) if l_num > 0 else 0

        return {
            "id": qid,
            "found": True,
            "is_done": is_done,
            "status": status,
            "c_num": c_num,
            "l_num": l_num,
            "remaining": remaining,
        }

    def query_prestige_summary(self) -> Dict[str, Dict[str, Any]]:
        """استعلام شامل وسريع عن حالة جميع مهام الهيبة قبل التنفيذ."""
        summary = {}
        for key in ("smuggler", "invaders", "stronghold", "food", "wood", "stone", "iron"):
            summary[key] = self.get_quest_info(key)
        return summary

    def log_prestige_overview(self, quests_status: Dict[str, Dict[str, Any]]):
        """طباعة تقرير استعلام أولي مفصل عن حالة المهام قبل البدء في التنفيذ."""
        self.log.info("🔍 ───【 فحص واستعلام مسبق لمهام الهيبة اليومية 】───")
        for key, info in quests_status.items():
            name = PRESTIGE_QUEST_NAMES.get(key, key)
            if not info.get("found"):
                self.log.info(f"   • {name:<35}: ⚠️ غير مسجلة في السيرفر حالياً (ستنفذ كالمعتاد)")
                continue

            c = info["c_num"]
            l = info["l_num"]
            if info["is_done"]:
                st_label = f"✅ مكتملة مسبقاً ({c:,}/{l:,}) [سيتم التخطي ✨]"
            else:
                rem = info["remaining"]
                st_label = f"⏳ قيد الإنجاز ({c:,}/{l:,} — متبقي {rem:,})"
            self.log.info(f"   • {name:<35}: {st_label}")
        self.log.info("─" * 60)

    async def _load_heroes(self):
        """جلب قائمة الأبطال المتاحين."""
        self._heroes = []
        if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
            self._heroes = list(self.conn._gate.heroes)
            if self._heroes:
                return

        hctrl = self.conn.init_data.get('heroCtrl')
        if isinstance(hctrl, list) and hctrl:
            self._heroes = list(hctrl)
        elif isinstance(hctrl, dict) and hctrl:
            hlist = hctrl.get('heroList', hctrl)
            if isinstance(hlist, dict):
                self._heroes = list(hlist.values())
            elif isinstance(hlist, list):
                self._heroes = list(hlist)

    def _get_castle_resources(self) -> Dict[int, float]:
        """استخراج رصيد موارد القلعة الحالية."""
        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        reslist = city_ctrl.get("reslist", {}) if isinstance(city_ctrl, dict) else {}
        resources = {}
        for resid in (1002, 1003, 1004, 1005):
            try:
                resources[resid] = float(reslist.get(str(resid), 0))
            except Exception:
                resources[resid] = 0.0
        return resources

    # ════════════════════════════════════════════════════════════════
    #  الجزء 1: متجر المهربين (Smuggler Store)
    # ════════════════════════════════════════════════════════════════

    async def run_smuggler_store(self) -> Dict[str, Any]:
        """
        تنفيذ عمليات الشراء من متجر المهربين / التاجر المتجول حتى إتمام عمليات الشراء المطلوبة بالموارد:
          - فحص مسبق: إذا كانت المهمة مكتملة بالفعل في meritoriousTaskCtrl يتم تخطيها فوراً.
          - إذا كانت مكتملة جزئياً، يتم شراء المتبقي فقط لإكمالها بدون هدر.
          - شراء البضائع بالموارد العادية حصراً (1002=قمح, 1003=خشب, 1004=حديد, 1005=فضة/ألماس).
          - استبعاد أي سلعة تباع بالذهب (1001, 1006) منعاً باتاً.
          - عند شراء سلعة واستبدالها بسلعة جديدة (newShopItem)، يتم فحص السلعة البديلة لشرائها فوراً.
          - تحديث المتجر حتى بلوغ المستهدف.
        """
        q_info = self.get_quest_info("smuggler")
        if q_info["is_done"]:
            self.log.info(
                f"✨ [استعلام مسبق] مهمة متجر المهربين مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}) "
                f"— يتم تخطي الخطوة 1 بالكامل لتوفير الموارد!"
            )
            return {
                "success": True,
                "skipped": True,
                "purchased_count": 0,
                "items": [],
                "message": f"مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']})"
            }

        needed_buys = self.target_smuggler_buys
        if q_info["found"] and q_info["remaining"] > 0:
            needed_buys = min(self.target_smuggler_buys, q_info["remaining"])
            self.log.info(f"🎯 [استعلام مسبق] تقدم المتجر الحالي: {q_info['c_num']}/{q_info['l_num']} — المطلوب إنجازه: {needed_buys} مشتريات فقط")

        self.log.info(f"🛒 ───【 الخطوة 1: متجر المهربين (المطلوب: {needed_buys} عمليات شراء بالموارد) 】───")
        store_res = {"success": True, "skipped": False, "purchased_count": 0, "items": []}

        # الاستعلام الأولي عن المتجر (1024/1)
        resp = await self.conn.query("1024", "1", {}, timeout=6)
        if not resp or str(resp.get("err", "0")) != "0":
            self.log.warning("⚠️ تعذر استلام بيانات متجر المهربين (1024/1)")
            store_res["success"] = False
            return store_res

        store_data = resp.get("data", {})
        if not store_data.get("isOpen", True):
            self.log.info("🚪 كشك متجر المهربين غير متاح حالياً بالقلعة.")
            return store_res

        shop_items: List[Dict[str, Any]] = list(store_data.get("shopItemArray", []))
        refresh_gold = int(store_data.get("refreshGold", 0))
        resources = self._get_castle_resources()
        purchased_items: List[Dict[str, Any]] = []
        total_refreshes = 0
        consecutive_errors = 0
        max_refreshes = 30

        while len(purchased_items) < needed_buys:
            if not getattr(self.conn, "is_connected", True):
                self.log.warning("⚠️ انقطع الاتصال بالسيرفر أثناء الشراء من المتجر!")
                break

            purchased_in_this_pass = False

            # فحص وشراء كافة السلع المعروضة المتاحة بالموارد
            for idx, itm in enumerate(shop_items):
                if not isinstance(itm, dict):
                    continue
                shop_id = itm.get("shopItemID")
                ptype = itm.get("pricetype")
                price = float(itm.get("price", 0))
                is_buy = itm.get("isBuy", 0)

                if is_buy == 1 or not shop_id:
                    continue

                # استبعاد الذهب والعملات الخاصة نهائياً
                if ptype in DISALLOWED_CURRENCIES or ptype not in ALLOWED_SMUGGLER_CURRENCIES:
                    continue

                curr_info = ALLOWED_SMUGGLER_CURRENCIES[ptype]
                curr_name = curr_info["name"]
                curr_icon = curr_info["icon"]
                avail_bal = resources.get(ptype, 0)

                if avail_bal < price:
                    continue

                # محاكاة بشرية سريعة قبل الشراء
                await asyncio.sleep(round(random.uniform(1.2, 2.2), 2))

                buy_resp = await self.conn.query("1024", "3", {"shopItemID": int(shop_id)}, timeout=6)
                if buy_resp and str(buy_resp.get("err", "0")) == "0":
                    consecutive_errors = 0
                    resources[ptype] = max(0, resources[ptype] - price)
                    purchased_items.append({"shop_id": shop_id, "currency": curr_name, "price": price})
                    self.log.info(
                        f"✅ [متجر المهربين ({len(purchased_items)}/{self.target_smuggler_buys})] "
                        f"تم شراء سلعة #{shop_id}! {curr_icon} السعر: {int(price):,} {curr_name}"
                    )
                    purchased_in_this_pass = True

                    # استبدال السلعة المشتراة بالسلعة البديلة الجديدة فوراً
                    new_item = buy_resp.get("data", {}).get("newShopItem")
                    if new_item and isinstance(new_item, dict):
                        shop_items[idx] = new_item
                    else:
                        shop_items[idx] = {}

                    if len(purchased_items) >= needed_buys:
                        break
                else:
                    consecutive_errors += 1
                    err_c = buy_resp.get("err") if buy_resp else "timeout"
                    self.log.warning(f"⚠️ تعذر شراء السلعة #{shop_id} (كود: {err_c})")
                    if consecutive_errors >= 3:
                        break

            if len(purchased_items) >= needed_buys:
                break

            # إذا تم شراء سلعة في هذه الدورة، نعيد فحص السلع البديلة الجديدة فوراً
            if purchased_in_this_pass:
                continue

            # لم تعد هناك أي سلع تباع بالموارد في العرض الحالي -> يلزم تحديث المتجر
            if total_refreshes >= max_refreshes:
                self.log.warning(f"⚠️ تم بلوغ الحد الأقصى للتحديثات ({max_refreshes})!")
                break

            if refresh_gold > self.max_gold_refresh:
                self.log.warning(
                    f"⚠️ تكلفة التحديث القادمة ({refresh_gold} ذهب) تتجاوز سقف الأمان ({self.max_gold_refresh} ذهب)!"
                )
                break

            # فحص رصيد الذهب إذا كان التحديث بذهب
            if refresh_gold > 0:
                lord_info = self.conn.init_data.get("lordInfoCtrl", {})
                player_gold = int(lord_info.get("baseInfo", {}).get("gold", 0))
                if player_gold < refresh_gold:
                    self.log.warning(f"⚠️ رصيد الذهب ({player_gold}) غير كافٍ لرسوم التحديث ({refresh_gold})!")
                    break

            cost_label = f"{refresh_gold} ذهب" if refresh_gold > 0 else "مجاناً (0 ذهب)"
            self.log.info(f"🔄 جاري تحديث سلع متجر المهربين (التكلفة: {cost_label})...")
            await asyncio.sleep(round(random.uniform(1.5, 2.5), 2))

            ref_resp = await self.conn.query("1024", "2", {}, timeout=6)
            if ref_resp and str(ref_resp.get("err", "0")) == "0":
                consecutive_errors = 0
                total_refreshes += 1
                ref_data = ref_resp.get("data", {})
                shop_items = list(ref_data.get("shopItemArray", []))
                refresh_gold = int(ref_data.get("refreshGold", 0))
                self.log.info(f"✨ تم تحديث المتجر بنجاح (تحديث رقم {total_refreshes} | القادم: {refresh_gold} ذهب)")
                await asyncio.sleep(round(random.uniform(1.0, 1.8), 2))
            else:
                consecutive_errors += 1
                self.log.warning("⚠️ تعذر تحديث متجر المهربين من السيرفر")
                if consecutive_errors >= 3:
                    break
                await asyncio.sleep(2.0)

        store_res["purchased_count"] = len(purchased_items)
        store_res["items"] = purchased_items
        self.log.info(f"🏁 تم إنجاز خطوة متجر المهربين بنجاح (إجمالي المشتريات بالموارد: {len(purchased_items)}/{needed_buys}).")
        return store_res

    # ════════════════════════════════════════════════════════════════
    #  الجزء 2: الهجوم على الغزاة (Invaders Attack - 5 هجمات)
    # ════════════════════════════════════════════════════════════════

    async def run_invaders_step(self) -> Dict[str, Any]:
        """
        الهجوم على الغزاة (Invaders) لمهام الهيبة اليومية عبر استيراد MonsterTask:
          - فحص مسبق: إذا كانت مهمة الغزاة مكتملة في meritoriousTaskCtrl يتم تخطيها فوراً.
          - إذا كانت مكتملة جزئياً، يتم إرسال الهجمات المتبقية فقط.
          - مستورد بالكامل من ملف tasks/monster.py.
          - عند عدم توفر فيالق فارغة: ينتظر بذكاء حتى تعود إحدى المسيرات لتفريغ الطابور وإكمال الهجمات.
          - خفيف ومنظم ويدعم تحديد المنطقة (الإحداثيات) ومستويات الغزاة ونطاق البحث بسهولة.
        """
        q_info = self.get_quest_info("invaders")
        if q_info["is_done"]:
            self.log.info(
                f"✨ [استعلام مسبق] مهمة قتال الغزاة مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}) "
                f"— يتم تخطي الخطوة 2 بالكامل لتوفير الفيالق والنشاط!"
            )
            return {
                "success": True,
                "skipped": True,
                "attacks": 0,
                "message": f"مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']})"
            }

        needed_attacks = self.invaders_count
        if q_info["found"] and q_info["remaining"] > 0:
            needed_attacks = min(self.invaders_count, q_info["remaining"])
            self.log.info(f"🎯 [استعلام مسبق] تقدم الغزاة الحالي: {q_info['c_num']}/{q_info['l_num']} — المطلوب إنجازه: {needed_attacks} هجمات فقط")

        self.log.info(f"👾 ───【 الخطوة 2: الهجوم على الغزاة (مهام الهيبة - {needed_attacks} غزاة) 】───")
        area_desc = f"عند ({self.invaders_center_x}, {self.invaders_center_y})" if (self.invaders_center_x is not None and self.invaders_center_y is not None) else "حول القلعة"
        self.log.info(
            f"🎯 إعدادات الغزاة: {needed_attacks} هجمات | لفل: {self.invaders_min_lv}-{self.invaders_max_lv} | "
            f"نطاق البحث: {self.invaders_range} كم | تشكيلة: {self.invaders_formation} | المنطقة: {area_desc}"
        )

        task_cfg = {
            "monster_type": "invaders",
            "min_lv": self.invaders_min_lv,
            "max_lv": self.invaders_max_lv,
            "max_marches": needed_attacks,
            "search_range": self.invaders_range,
            "formation_id": self.invaders_formation,
            "troops_count": self.invaders_troops,
            "wait_for_queue": self.invaders_wait_queue,
            "wait_interval": 15.0,
            "center_x": self.invaders_center_x,
            "center_y": self.invaders_center_y,
        }

        monster_task = MonsterTask(self.conn, task_cfg)
        res = await monster_task.run()

        attacks_sent = res.data.get("sent", 0) if (res and res.data) else (needed_attacks if res and res.success else 0)
        self.log.info(f"🏁 اكتملت مرحلة الغزاة: {res.message if res else 'تم الإرسال'} (أُرسلت {attacks_sent}/{needed_attacks} مسيرة هجوم)")
        return {
            "success": bool(res and res.success),
            "skipped": False,
            "attacks": attacks_sent,
            "message": res.message if res else "No response"
        }

    # ════════════════════════════════════════════════════════════════
    #  الجزء 3: الهجوم على المعاقل / الملاجئ (Stronghold Attack - ملجأين)
    # ════════════════════════════════════════════════════════════════

    async def run_stronghold_step(self) -> Dict[str, Any]:
        """
        الهجوم على المعاقل / الملاجئ (Strongholds / Shelters) لمهام الهيبة عبر استيراد StrongholdTask:
          - فحص مسبق: إذا كانت مهمة احتلال المعقل مكتملة في meritoriousTaskCtrl يتم تخطيها فوراً.
          - إذا كانت مكتملة جزئياً، يتم إرسال الهجمات المتبقية فقط.
          - مستورد بالكامل من ملف tasks/stronghold.py بشكل سليم ونظيف.
          - يختار أبطال الحرب وجيش القتال المناسب تلقائياً بدون تشكيلة ثابتة.
          - عند عدم توفر فيالق فارغة: ينتظر بذكاء حتى تعود إحدى المسيرات لتفريغ الطابور وإكمال الهجمات.
        """
        q_info = self.get_quest_info("stronghold")
        if q_info["is_done"]:
            self.log.info(
                f"✨ [استعلام مسبق] مهمة احتلال المعاقل / الملاجئ مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']}) "
                f"— يتم تخطي الخطوة 3 بالكامل لتوفير الفيالق والجنود!"
            )
            return {
                "success": True,
                "skipped": True,
                "attacks": 0,
                "message": f"مكتملة مسبقاً ({q_info['c_num']}/{q_info['l_num']})"
            }

        needed_attacks = self.stronghold_count
        if q_info["found"] and q_info["remaining"] > 0:
            needed_attacks = min(self.stronghold_count, q_info["remaining"])
            self.log.info(f"🎯 [استعلام مسبق] تقدم المعاقل الحالي: {q_info['c_num']}/{q_info['l_num']} — المطلوب إنجازه: {needed_attacks} معاقل فقط")

        self.log.info(f"🏰 ───【 الخطوة 3: الهجوم على المعاقل / الملاجئ (مهام الهيبة - {needed_attacks} معاقل) 】───")
        area_desc = f"عند ({self.stronghold_center_x}, {self.stronghold_center_y})" if (self.stronghold_center_x is not None and self.stronghold_center_y is not None) else "حول القلعة"
        self.log.info(
            f"🎯 إعدادات المعاقل: {needed_attacks} هجمات | لفل: {self.stronghold_min_lv}-{self.stronghold_max_lv} | "
            f"نطاق البحث: {self.stronghold_range} كم | اختيار تلقائي متوازن للجيش والأبطال | المنطقة: {area_desc}"
        )

        task_cfg = {
            "min_lv": self.stronghold_min_lv,
            "max_lv": self.stronghold_max_lv,
            "max_marches": needed_attacks,
            "search_range": self.stronghold_range,
            "formation_id": self.stronghold_formation,
            "troops_count": self.stronghold_troops,
            "wait_for_queue": self.stronghold_wait_queue,
            "wait_interval": 15.0,
            "center_x": self.stronghold_center_x,
            "center_y": self.stronghold_center_y,
        }

        sh_task = StrongholdTask(self.conn, task_cfg)
        res = await sh_task.run()

        attacks_sent = res.data.get("sent", 0) if (res and res.data) else (needed_attacks if res and res.success else 0)
        self.log.info(f"🏁 اكتملت مرحلة المعاقل: {res.message if res else 'تم الإرسال'} (أُرسلت {attacks_sent}/{needed_attacks} مسيرة هجوم على المعقل)")
        return {
            "success": bool(res and res.success),
            "skipped": False,
            "attacks": attacks_sent,
            "message": res.message if res else "No response"
        }

    # ════════════════════════════════════════════════════════════════
    #  الجزء 4: جمع الموارد الأربعة خارج القلعة
    # ════════════════════════════════════════════════════════════════

    async def run_gather_prestige(self) -> Dict[str, Any]:
        """
        إرسال هجوم/مسيرة جمع واحدة مؤكدة لكل مورد من الموارد غير المكتملة:
          - فحص مسبق لكل مورد على حدة (قمح، خشب، حجر، حديد):
            إذا كان المورد مكتملاً بالفعل في meritoriousTaskCtrl يتم تخطي مسيرته لتوفير الفيالق.
          - إذا كانت جميع الموارد الـ 4 مكتملة يتم تخطي خطوة الجمع بالكامل!
          - مع جعل حمولة المسيرة للموارد المتبقية: currentSourceNum = 25000.
        """
        self.log.info("🌾 ───【 الخطوة 4: جمع الموارد الأربعة خارج القلعة (مهام الهيبة) 】───")

        # فحص استعلام الموارد الأربعة وتصفية المكتمل منها
        pending_resources: List[Dict[str, Any]] = []
        skipped_resources: List[str] = []

        for res_meta in PRESTIGE_RESOURCES:
            qid = res_meta.get("quest_id")
            q_info = self.get_quest_info(qid)
            if q_info["is_done"]:
                c = q_info["c_num"]
                l = q_info["l_num"]
                self.log.info(f"   ✨ [استعلام مسبق] مهمة جمع {res_meta['name']} مكتملة مسبقاً ({c:,}/{l:,}) — يتم تخطيها!")
                skipped_resources.append(res_meta["name"])
            else:
                pending_resources.append(res_meta)

        if not pending_resources:
            self.log.info("✨ [استعلام مسبق] جميع مهام جمع الموارد الأربعة مكتملة مسبقاً — يتم تخطي خطوة الجمع بالكامل وتوفير الفيالق!")
            return {
                "success": True,
                "skipped": True,
                "dispatched": 0,
                "details": [],
                "skipped_resources": skipped_resources,
                "message": "جميع مهام جمع الموارد مكتملة مسبقاً"
            }

        self.log.info(
            f"🎯 الموارد المطلوب إرسال مسيرات جمع لها ({len(pending_resources)} مسيرة): "
            + ", ".join(r["name"] for r in pending_resources)
        )
        self.log.info(f"   • تثبيت حمولة المسيرة: currentSourceNum = {self.target_source_num}")

        gather_res = {"success": True, "skipped": False, "dispatched": 0, "details": [], "skipped_resources": skipped_resources}
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. جلب إحداثيات القلعة
        r_castle = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=5)
        if not r_castle or not r_castle.get('retData'):
            self.log.error("❌ فشل تحديد إحداثيات القلعة على الخريطة!")
            gather_res["success"] = False
            return gather_res

        cx = r_castle['retData'].get('x')
        cy = r_castle['retData'].get('y')
        self.log.info(f"📍 موقع القلعة على الخريطة: ({cx}, {cy})")

        # 2. معرف المملكة
        kingdom_id = 0
        if self.conn.kingdom_id:
            try:
                kingdom_id = int(self.conn.kingdom_id)
            except Exception:
                pass
        if not kingdom_id:
            r_map = await self.conn.query('1002', '7', {"uid": uid_int}, timeout=4)
            if r_map and 'data' in r_map:
                kingdom_id = r_map['data'].get('base', {}).get('partition', 0)

        # 3. جلب القوات المتوفرة بالقلعة (1005/1)
        available_troops: Dict[int, int] = {}
        r_army = await self.conn.query('1005', '1', {}, timeout=5)
        if r_army and 'data' in r_army:
            for k, v in r_army['data'].get('totalArmy', {}).items():
                if str(k).isdigit() and str(v).isdigit():
                    available_troops[int(k)] = int(v)

        total_castle_soldiers = sum(available_troops.values())
        self.log.info(f"🛡️ إجمالي القوات المتوفرة بالقلعة: {total_castle_soldiers:,} جندي")

        # 4. إرسال مسيرة واحدة لكل مورد من الموارد غير المكتملة
        for res_meta in pending_resources:
            rtype = res_meta["type"]
            rname = res_meta["name"]
            ricon = res_meta["icon"]
            rcode = res_meta["res_code"]

            self.log.info("─" * 60)
            self.log.info(f"🏹 تجهيز مسيرة جمع {ricon} {rname}...")

            # أ. اختيار البطل
            hero_id = pick_available_hero(self._heroes, self._busy_heroes)
            chosen_heroes = [hero_id] if hero_id else []
            hero_desc = f"بطل #{hero_id}" if hero_id else "بدون بطل (تلقائي)"
            self.log.info(f"   • اختيار البطل: {hero_desc}")

            # ب. اختيار الحيوان
            chosen_pets = pick_available_pet(self.conn, self._used_pets)
            pet_desc = f"حيوان #{chosen_pets[0]}" if chosen_pets else "بدون حيوان"
            self.log.info(f"   • اختيار الحيوان: {pet_desc}")

            # ج. اختيار الجيش الكافي لحمل 25,000 مورد
            # خصم القوات المستهلكة في المسيرات السابقة
            current_avail = {}
            for tid, count in available_troops.items():
                used = self._used_army.get(tid, 0)
                rem = max(0, count - used)
                if rem > 0:
                    current_avail[tid] = rem

            army_list, calc_capacity = select_prestige_army(current_avail, target_capacity=self.target_capacity)
            if not army_list:
                self.log.warning(f"⚠️ لا تتوفر قوات كافية بالقلعة لإرسال مسيرة {rname}!")
                continue

            march_troops_count = sum(item["num"] for item in army_list)
            self.log.info(f"   • القوات المحسوبة للحمولة: {march_troops_count:,} جندي (سعة الحمولة القصوى: ~{calc_capacity:,} مورد فقط لضمان عدم جمع كامل الحقل)")

            # د. البحث عن أقرب حقل شاغر للمورد على الخريطة (2011/3)
            exclude_map = {tid: True for tid in self._excluded_targets}
            r_search = await self.conn.query('2011', '3', {
                "mapType": 5,
                "subType": rtype,
                "num": 5,
                "y": cy,
                "x": cx,
                "exclude": exclude_map,
                "minLv": self.min_lv,
                "maxLv": self.max_lv,
                "range": self.search_range
            }, timeout=5)

            candidates = r_search.get('result', []) if (r_search and isinstance(r_search, dict)) else []
            if not candidates:
                self.log.warning(f"⚠️ لم يتم العثور على حقل شاغر لـ {rname} في نطاق {self.search_range} كم!")
                continue

            target = candidates[0]
            target_id = target.get('id')
            tx, ty = target.get('x'), target.get('y')
            self._excluded_targets.add(str(target_id))
            self.log.info(f"   • تم العثور على الحقل: {target_id} عند ({tx}, {ty})")

            # هـ. محاكاة بشرية آمنة قبل إرسال المسيرة
            prep_wait = round(random.uniform(2.5, 4.5), 2)
            self.log.info(f"   ⏳ [محاكاة بشرية] تجهيز تفاصيل المسيرة ({prep_wait} ثانية)...")
            await asyncio.sleep(prep_wait)

            # و. إرسال مسيرة الجمع (1007/2) مع تثبيت currentSourceNum = 25000
            march_payload = {
                "needSend": False,
                "runePages": {},
                "heros": chosen_heroes,
                "matrixType": 3,
                "mapId": int(kingdom_id),
                "moveLineType": 3,
                "data": {
                    "data": {
                        "currentSourceNum": self.target_source_num,  # 25000 إجبارياً لمهام الهيبة
                        "resourceType": rcode                       # كود نوع المورد (1001..1004)
                    },
                    "to": {
                        "y": int(ty),
                        "x": int(tx),
                        "id": str(target_id)
                    },
                    "army": army_list
                },
                "pets": chosen_pets
            }

            r_march = await self.conn.query('1007', '2', march_payload, timeout=8)
            if not r_march:
                self.log.error(f"❌ انتهت مهلة الرد أثناء إرسال مسيرة {rname}")
                continue

            err = str(r_march.get('err', '0'))
            queue_id = r_march.get('queueId')
            if err == '0':
                gather_res["dispatched"] += 1
                if hero_id:
                    self._busy_heroes.add(hero_id)
                for item in army_list:
                    self._used_army[item['id']] = self._used_army.get(item['id'], 0) + item['num']

                self.log.info(
                    f"🎉 تم إطلاق مسيرة جمع {ricon} {rname} بنجاح! 🚀 "
                    f"[الهدف: ({tx}, {ty}) | جنود: {march_troops_count:,} | سعة الحمولة: ~{calc_capacity:,} | الطابور: {queue_id}]"
                )
                gather_res["details"].append({
                    "resource": rname,
                    "target_id": target_id,
                    "coords": (tx, ty),
                    "troops": march_troops_count,
                    "capacity": calc_capacity,
                    "queue_id": queue_id,
                    "source_num": self.target_source_num
                })

                # فاصل زمني أمان بشري بين المسيرات المتتالية
                spacing = round(random.uniform(4.0, 7.0), 2)
                self.log.info(f"🛡️ [أمان ومكافحة حظر] انتظار {spacing} ثانية قبل تجهيز المورد التالي...")
                await asyncio.sleep(spacing)

            elif err in ('8004', '9007004'):
                self.log.warning(f"🛑 اكتملت طوابير المسيرات بالقلعة (كود {err})!")
                break
            elif err == '8009':
                self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
            else:
                self.log.warning(f"⚠️ تعذر إرسال مسيرة {rname} (كود الخطأ: {err})")

        self.log.info(f"🏁 اكتملت مرحلة جمع الموارد لمهام الهيبة (أُرسلت {gather_res['dispatched']}/{len(pending_resources)} مسيرات).")
        return gather_res

    async def recall_march(self, queue_id: str) -> bool:
        """
        سحب مسيرة معينة عبر معرف الطابور (1007/18 REQ_BACK_QUEUE_BY_ID).
        تعيد المسيرة فوراً إلى القلعة بكامل الموارد التي جمعتها حتى تلك اللحظة.
        """
        if not queue_id:
            return False
        resp = await self.conn.query("1007", "18", {"queueId": str(queue_id)}, timeout=5)
        ok = bool(resp and str(resp.get("err", "0")) == "0")
        if ok:
            self.log.info(f"↩️ تم سحب المسيرة {queue_id} وإعادتها للقلعة بنجاح!")
        else:
            err = resp.get("err") if resp else "timeout"
            self.log.warning(f"⚠️ تعذر سحب المسيرة {queue_id} (كود {err})")
        return ok

    # ════════════════════════════════════════════════════════════════
    #  الجزء 5: الساقية — تفعيل جميع مواد إنتاج الموارد
    # ════════════════════════════════════════════════════════════════

    async def run_watermill_step(self) -> Dict[str, Any]:
        """
        تشغيل مهمة الساقية لتفعيل جميع مباني الموارد (مزارع، مناشر، مناجم).
        مسموح بالشراء من متجر التحالف بالكامل لضمان التفعيل.
        """
        self.log.info("💧 ───【 الخطوة 5: الساقية — تفعيل جميع مباني إنتاج الموارد 】───")
        try:
            wm_cfg = {
                "types": "all",
                "allow_shop_buy": True,   # مسموح بالشراء من متجر التحالف
            }
            wm_task = WatermillTask(self.conn, wm_cfg)
            await wm_task.on_start()
            res = await wm_task.run()
            self.log.info(f"🏁 اكتملت مهمة الساقية: {res.message if res else 'تم التنفيذ'}")
            return {
                "success": bool(res and res.success),
                "message": res.message if res else "No response",
                "activated": res.data.get("activated", 0) if (res and res.data) else 0,
            }
        except Exception as e:
            self.log.warning(f"⚠️ خطأ في مهمة الساقية: {e}")
            return {"success": False, "message": str(e), "activated": 0}

    # ════════════════════════════════════════════════════════════════
    #  الجزء 6: تدريب الجنود — 250 من كل نوع مستوى 1 مع انتظار الفيالق
    # ════════════════════════════════════════════════════════════════

    async def run_train_step(self) -> Dict[str, Any]:
        """
        تدريب 250 جندي من كل نوع (مشاة، خيالة، أسهم، عربات) على مستوى 1.
        إذا كانت الثكنة مشغولة ينتظر حتى تنتهي ثم يكمل.
        """
        self.log.info("🪖 ───【 الخطوة 6: تدريب الجنود (250 من كل نوع — مستوى 1) 】───")
        try:
            train_cfg = {
                "types": "all",      # جميع أنواع الثكنات (مشاة، خيالة، أسهم، عربات)
                "level": 1,          # مستوى 1 لجميع الأنواع
                "count": 250,        # 250 وحدة من كل نوع
            }
            train_task = TrainTask(self.conn, train_cfg)
            await train_task.on_start()
            res = await train_task.run()
            self.log.info(f"🏁 اكتملت مهمة تدريب الجنود: {res.message if res else 'تم التنفيذ'}")
            data = res.data if (res and res.data) else {}
            trained = data.get("trained", [])
            busy    = data.get("busy", [])
            return {
                "success": bool(res and res.success),
                "message": res.message if res else "No response",
                "trained_count": len(trained),
                "busy_count": len(busy),
            }
        except Exception as e:
            self.log.warning(f"⚠️ خطأ في مهمة تدريب الجنود: {e}")
            return {"success": False, "message": str(e), "trained_count": 0, "busy_count": 0}

    # ════════════════════════════════════════════════════════════════
    #  الجزء 7: حصن الحرب — تدريب الفخاخ تلقائياً
    # ════════════════════════════════════════════════════════════════

    async def run_fortress_step(self) -> Dict[str, Any]:
        """
        تدريب فخاخ حصن الحرب بالحد الأقصى التلقائي (auto).
        """
        self.log.info("🏰 ───【 الخطوة 7: حصن الحرب — تدريب الفخاخ تلقائياً 】───")
        try:
            fortress_cfg = {
                "type": "auto",   # تدريب جميع أنواع الفخاخ المتاحة تلقائياً
                "count": "max",   # الحد الأقصى المتاح تلقائياً
            }
            fortress_task = FortressTask(self.conn, fortress_cfg)
            await fortress_task.on_start()
            res = await fortress_task.run()
            self.log.info(f"🏁 اكتملت مهمة حصن الحرب: {res.message if res else 'تم التنفيذ'}")
            return {
                "success": bool(res and res.success),
                "message": res.message if res else "No response",
            }
        except Exception as e:
            self.log.warning(f"⚠️ خطأ في مهمة حصن الحرب: {e}")
            return {"success": False, "message": str(e)}

    # ════════════════════════════════════════════════════════════════
    #  الجزء 8: فحص مهام الهيبة اليومية (Meritorious Quests Status)
    # ════════════════════════════════════════════════════════════════

    async def report_prestige_status(self):
        """عرض ملخص نقاط الهيبة ومستوى المجد والمهام اليومية الجاهزة."""
        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if not merit:
            return

        merit_lv = merit.get("meritLv", 0)
        merit_exp = merit.get("meritExp", 0)
        daily_point = merit.get("dailyPoint", 0)
        task_data = merit.get("taskData", {})

        ready_count = sum(1 for t in task_data.values() if t.get("status") == 4)
        in_progress_count = sum(1 for t in task_data.values() if t.get("status") == 2)

        self.log.info("🎖️ ───【 ملخص بيانات الهيبة والمجد 】───")
        self.log.info(f"   • مستوى الهيبة/المجد: {merit_lv} | نقاط المجد: {merit_exp:,}")
        self.log.info(f"   • نقاط النشاط اليومي الحالية: {daily_point} نقطة")
        self.log.info(f"   • المهام المكتملة الجاهزة للاستلام: {ready_count} مهمة | قيد الإنجاز: {in_progress_count}")

    # ════════════════════════════════════════════════════════════════
    #  دورة العمل الرئيسية للمهمة (run)
    # ════════════════════════════════════════════════════════════════

    async def run(self) -> TaskResult:
        """تنفيذ دورة مهام الهيبة اليومية الكاملة مع الاستعلام المسبق وتخطي المهام المكتملة."""
        print("\n" + "═" * 70)
        print("  🎖️ بدء مهمة مهام الهيبة اليومية (Daily Prestige & Honor Quests)")
        print(f"  • متجر المهربين: الشراء بالموارد العادية حصراً (المستهدف: {self.target_smuggler_buys} عمليات شراء)")
        print(f"  • هجوم الغزاة: {self.invaders_count} مسيرات هجوم (Invaders لفل حتى {self.invaders_max_lv}) مع انتظار الفيالق")
        print(f"  • هجوم المعاقل: {self.stronghold_count} مسيرات هجوم (Strongholds) مع انتظار الفيالق وتشكيل ذكي")
        print(f"  • جمع الموارد: مسيرة واحدة لكل مورد غير مكتمل بحمولة 25,000 مورد بالضبط")
        print(f"  • الساقية: تفعيل جميع مباني الموارد مع السماح بالشراء من متجر التحالف")
        print(f"  • تدريب الجنود: 250 وحدة من كل نوع على مستوى 1 (مشاة، خيالة، أسهم، عربات)")
        print(f"  • حصن الحرب: تدريب الفخاخ بالحد الأقصى التلقائي")
        print("═" * 70 + "\n")

        # 0. تجديد بيانات مهام الهيبة من السيرفر للحصول على أحدث حالة
        self.log.info("🔄 [تجديد البيانات] جاري استعلام السيرفر لأحدث حالة مهام الهيبة...")
        await self._refresh_merit_data()

        # 0.1 الاستعلام المسبق وفحص حالة مهام الهيبة من السيرفر
        quests_status = self.query_prestige_summary()
        self.log_prestige_overview(quests_status)

        # 1. متجر المهربين
        if self.is_subtask_enabled("smuggler"):
            smuggler_res = await self.run_smuggler_store()
            await asyncio.sleep(round(random.uniform(2.5, 4.0), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة متجر المهربين معطلة بناءً على اختيار المستخدم.")
            smuggler_res = {"success": True, "skipped": True, "user_disabled": True, "purchased_count": 0}

        # 2. الهجوم على الغزاة (Invaders)
        if self.is_subtask_enabled("invaders"):
            invaders_res = await self.run_invaders_step()
            await asyncio.sleep(round(random.uniform(2.5, 4.0), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة قتال الغزاة معطلة بناءً على اختيار المستخدم.")
            invaders_res = {"success": True, "skipped": True, "user_disabled": True, "attacks": 0}

        # 3. الهجوم على المعاقل / الملاجئ (Strongholds)
        if self.is_subtask_enabled("stronghold"):
            stronghold_res = await self.run_stronghold_step()
            await asyncio.sleep(round(random.uniform(2.5, 4.0), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة احتلال المعاقل / الملاجئ معطلة بناءً على اختيار المستخدم.")
            stronghold_res = {"success": True, "skipped": True, "user_disabled": True, "attacks": 0}

        # 4. جمع الموارد الأربعة خارج القلعة
        if self.is_subtask_enabled("gather"):
            gather_res = await self.run_gather_prestige()
            await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة جمع الموارد معطلة بناءً على اختيار المستخدم.")
            gather_res = {"success": True, "skipped": True, "user_disabled": True, "dispatched": 0}

        # 5. الساقية — تفعيل جميع مباني إنتاج الموارد
        if self.is_subtask_enabled("watermill"):
            watermill_res = await self.run_watermill_step()
            await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة الساقية معطلة بناءً على اختيار المستخدم.")
            watermill_res = {"success": True, "skipped": True, "user_disabled": True, "activated": 0}

        # 6. تدريب الجنود — 250 من كل نوع على مستوى 1
        if self.is_subtask_enabled("train"):
            train_res = await self.run_train_step()
            await asyncio.sleep(round(random.uniform(2.0, 3.5), 2))
        else:
            self.log.info("⏭️ [تخطي] مهمة تدريب الجنود معطلة بناءً على اختيار المستخدم.")
            train_res = {"success": True, "skipped": True, "user_disabled": True, "trained_count": 0}

        # 7. حصن الحرب — تدريب الفخاخ تلقائياً (تُفعّل تلقائياً عند تفعيل تدريب الجنود في مهام الهيبة)
        if self.is_subtask_enabled("train"):
            fortress_res = await self.run_fortress_step()
        else:
            self.log.info("⏭️ [تخطي] مهمة حصن الحرب معطلة (تعتمد حصراً على تفعيل تدريب الجنود في مهام الهيبة).")
            fortress_res = {"success": True, "skipped": True, "user_disabled": True}

        # 8. عرض تقرير حالة الهيبة
        await self.report_prestige_status()

        total_bought = smuggler_res.get("purchased_count", 0)
        total_invaders = invaders_res.get("attacks", 0)
        total_strongholds = stronghold_res.get("attacks", 0)
        total_dispatched = gather_res.get("dispatched", 0)
        watermill_activated = watermill_res.get("activated", 0)
        train_trained = train_res.get("trained_count", 0)

        smuggler_skipped = bool(smuggler_res.get("skipped"))
        invaders_skipped = bool(invaders_res.get("skipped"))
        stronghold_skipped = bool(stronghold_res.get("skipped"))
        gather_skipped = bool(gather_res.get("skipped"))

        executed_parts = []
        skipped_parts = []

        if smuggler_res.get("user_disabled"):
            skipped_parts.append("متجر المهربين (معطل)")
        elif smuggler_skipped:
            skipped_parts.append("متجر المهربين ✨")
        else:
            executed_parts.append(f"متجر المهربين ({total_bought}/{self.target_smuggler_buys})")

        if invaders_res.get("user_disabled"):
            skipped_parts.append("الغزاة (معطل)")
        elif invaders_skipped:
            skipped_parts.append("الغزاة ✨")
        else:
            executed_parts.append(f"الغزاة ({total_invaders}/{self.invaders_count})")

        if stronghold_res.get("user_disabled"):
            skipped_parts.append("المعاقل (معطل)")
        elif stronghold_skipped:
            skipped_parts.append("المعاقل ✨")
        else:
            executed_parts.append(f"المعاقل ({total_strongholds}/{self.stronghold_count})")

        if gather_res.get("user_disabled"):
            skipped_parts.append("جمع الموارد (معطل)")
        elif gather_skipped:
            skipped_parts.append("جمع الموارد ✨")
        else:
            executed_parts.append(f"جمع الموارد ({total_dispatched} مسيرة)")

        if watermill_res.get("user_disabled"):
            skipped_parts.append("الساقية (معطل)")
        else:
            executed_parts.append(f"الساقية ({watermill_activated} مبنى)")

        if train_res.get("user_disabled"):
            skipped_parts.append("تدريب الجنود (معطل)")
        else:
            executed_parts.append(f"تدريب الجنود ({train_trained} أنواع)")

        if fortress_res.get("user_disabled"):
            skipped_parts.append("حصن الحرب (معطل)")
        else:
            executed_parts.append(f"حصن الحرب ({'✅' if fortress_res.get('success') else '⚠️'})")

        summary_txt = ""
        if executed_parts:
            summary_txt += f"المنفذ: [{', '.join(executed_parts)}]"
        if skipped_parts:
            if summary_txt:
                summary_txt += " | "
            summary_txt += f"المتخطي: [{', '.join(skipped_parts)}]"


        msg = f"✅ اكتملت دورة مهام الهيبة! {summary_txt}"
        self.log.info(msg)
        return TaskResult.ok(
            msg,
            smuggler_buys=total_bought,
            smuggler_skipped=smuggler_skipped,
            invaders_attacks=total_invaders,
            invaders_skipped=invaders_skipped,
            stronghold_attacks=total_strongholds,
            stronghold_skipped=stronghold_skipped,
            gather_marches=total_dispatched,
            gather_skipped=gather_skipped,
            gather_details=gather_res.get("details", []),
            watermill_activated=watermill_activated,
            train_trained=train_trained,
            fortress_ok=fortress_res.get("success", False),
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر لسطر الأوامر (Standalone CLI)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="Prestige Quests Task — مهمة مهام الهيبة اليومية المستقلة")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--password", "-p", help="كلمة المرور للحساب للتسجيل المباشر إن لم يكن في الكاش")
    parser.add_argument("--buys", "-b", type=int, default=10, help="عدد المشتريات المستهدفة من متجر المهربين [افتراضي: 10]")
    parser.add_argument("--invaders", "-i", type=int, default=5, help="عدد هجمات الغزاة المستهدفة [افتراضي: 5]")
    parser.add_argument("--inv-minlv", type=int, default=1, help="أدنى مستوى للغزاة [افتراضي: 1]")
    parser.add_argument("--inv-maxlv", type=int, default=30, help="أقصى مستوى للغزاة [افتراضي: 30]")
    parser.add_argument("--inv-range", type=int, default=80, help="نطاق البحث عن الغزاة [افتراضي: 80]")
    parser.add_argument("--strongholds", "-s", type=int, default=2, help="عدد المعاقل/الملاجئ المستهدفة [افتراضي: 2]")
    parser.add_argument("--sh-minlv", type=int, default=1, help="أدنى مستوى للمعقل [افتراضي: 1]")
    parser.add_argument("--sh-maxlv", type=int, default=30, help="أقصى مستوى للمعقل [افتراضي: 30]")
    parser.add_argument("--sh-range", type=int, default=80, help="نطاق البحث عن المعاقل [افتراضي: 80]")
    parser.add_argument("--range", type=int, default=120, help="نطاق البحث عن حقول الموارد بالكيلومتر [افتراضي: 120]")
    parser.add_argument(
        "--subtasks",
        default="all",
        help="المهام الفرعية المطلوب تشغيلها مفصولة بفاصلة (smuggler,invaders,stronghold,gather,watermill,train,fortress أو all) [افتراضي: all]"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        target_email = args.email or (next(iter(accounts.keys())) if accounts else None)

        if not target_email:
            print("❌ يرجى تحديد البريد الإلكتروني للحساب عبر --email")
            return

        acc = accounts.get(target_email)
        conn = None

        if args.password:
            from auto_elf_boss import sdk_login
            print(f"🔐 جاري التوثيق المباشر للحساب {target_email}...")
            auth_res = await asyncio.to_thread(sdk_login, target_email, args.password)
            if auth_res.get("success"):
                from game_client import AccountSession
                acc = AccountSession(email=target_email, user_id=auth_res["userId"], session_id=auth_res["sessionId"])
            else:
                print(f"❌ فشل تسجيل الدخول بكلمة المرور: {auth_res.get('error_msg')}")
                return

        if not acc:
            print(f"❌ لم يتم العثور على جلسة للحساب {target_email}!")
            return

        conn = GameConnection(acc)
        print(f"📡 جاري الاتصال ببوابة اللعبة للحساب: {target_email}...")
        if not await conn.connect():
            print("❌ فشل الاتصال ببوابة اللعبة!")
            return

        for _ in range(15):
            await asyncio.sleep(0.3)
            if "cityCtrl" in conn.init_data and "meritoriousTaskCtrl" in conn.init_data:
                break
        await asyncio.sleep(0.5)

        prestige_cfg = {
            "search_range": args.range,
            "smuggler_buys": args.buys,
            "invaders_count": args.invaders,
            "invaders_min_lv": args.inv_minlv,
            "invaders_max_lv": args.inv_maxlv,
            "invaders_range": args.inv_range,
            "stronghold_count": args.strongholds,
            "stronghold_min_lv": args.sh_minlv,
            "stronghold_max_lv": args.sh_maxlv,
            "stronghold_range": args.sh_range,
            "subtasks": args.subtasks,
        }

        task = PrestigeTask(conn, prestige_cfg)
        result = await task.run()
        print("\n" + "═" * 70)
        print("  📊 ملخص نتائج مهام الهيبة اليومية:")
        print(f"     • النتيجة: {result.message}")
        if result.data:
            buys = result.data.get("smuggler_buys", 0)
            sm_skip = result.data.get("smuggler_skipped", False)
            inv = result.data.get("invaders_attacks", 0)
            inv_skip = result.data.get("invaders_skipped", False)
            sh = result.data.get("stronghold_attacks", 0)
            sh_skip = result.data.get("stronghold_skipped", False)
            marches = result.data.get("gather_marches", 0)
            gather_skip = result.data.get("gather_skipped", False)

            buys_str = "✨ متخطى (مكتمل مسبقاً)" if sm_skip else f"{buys}/{args.buys} سلعة"
            inv_str = "✨ متخطى (مكتمل مسبقاً)" if inv_skip else f"{inv}/{args.invaders} هجمات"
            sh_str = "✨ متخطى (مكتمل مسبقاً)" if sh_skip else f"{sh}/{args.strongholds} معاقل"
            gather_str = "✨ متخطى (مكتمل مسبقاً)" if gather_skip else f"{marches} مسيرة بـ 25k مورد"
            wm_act = result.data.get("watermill_activated", 0)
            tr_cnt = result.data.get("train_trained", 0)
            fort_ok = result.data.get("fortress_ok", False)

            print(f"     • متجر المهربين (بالموارد): {buys_str}")
            print(f"     • هجمات الغزاة (Invaders): {inv_str}")
            print(f"     • هجمات المعاقل (Strongholds): {sh_str}")
            print(f"     • مسيرات جمع الموارد: {gather_str}")
            print(f"     • الساقية: {wm_act} مبنى مفعّل")
            print(f"     • تدريب الجنود: {tr_cnt} أنواع تم تدريبها (250 × كل نوع على مستوى 1)")
            print(f"     • حصن الحرب: {'✅ تم بنجاح' if fort_ok else '⚠️ تعذر أو لا توجد فخاخ جاهزة'}")
        print("═" * 70 + "\n")
        await conn.close()

    asyncio.run(_main())
