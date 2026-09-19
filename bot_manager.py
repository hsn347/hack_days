# -*- coding: utf-8 -*-
"""
أمثلة التشغيل من سطر الأوامر (CLI):
  # 1. تشغيل افتراضي شامل:
  python bot_manager.py --email "johan2003@yopmail.com"

  # 2. تحديد شجرة الأبحاث (مثلاً دفاعية أو عسكرية أو فحص فقط):
  python bot_manager.py --email "samartilleli@yopmail.com" --research-tree defense
  python bot_manager.py --email "samartilleli@yopmail.com" --no-alliance

  # 3. تخصيص الحيوان والثكنات ومهمة التحالف:
  python bot_manager.py --email "samartilleli@yopmail.com" --harvest-types "قمح,حديد" --barracks "مشاة,خيالة" --pet "صقر"
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

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import copy
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from game_client import GameConnection, AccountSession
from core.session_manager import SessionManager
from tasks.port import PortTask
from tasks.train import TrainTask, BUILDING_TROOP_MAP, TYPE_ALIASES
from tasks.pet_patrol import (
    PetPatrolTask, KNOWN_PETS, DEFAULT_DESTINATION,
    PET_DESTINATIONS, resolve_pet_destination
)
from tasks.city_harvest import CityHarvestTask
from tasks.research import ResearchTask, load_tech_names
from tasks.alliance import AllianceTask
from tasks.territory_expansion import TerritoryExpansionTask
from tasks.shield import ShieldTask, SHIELD_TYPES, DURATION_ALIASES
from tasks.stamina import StaminaTask
from tasks.skills import SkillsTask, SUPPORTED_SKILLS
from tasks.hero_draw import HeroDrawTask
from tasks.treasure_pavilion import TreasurePavilionTask
from tasks.blacksmith_forge import BlacksmithForgeTask
from tasks.imperial_mausoleum import ImperialMausoleumTask
from tasks.alliance_treasure import AllianceTreasureTask
from tasks.daily_luxury_gift import DailyLuxuryGiftTask
from tasks.vip_gift import VipGiftTask
from tasks.tactics_hall import TacticsHallTask, TACTICS_MAP, parse_tactic_choice
from tasks.watermill import WatermillTask
from tasks.fountain import FountainTask
from tasks.material_workshop import MaterialWorkshopTask, MATERIALS_MAP as WORKSHOP_MATERIALS_MAP, parse_materials_choice
from tasks.caravan import CaravanTask
from tasks.port_delegate import PortDelegateTask, DELEGATE_TASKS_CONFIG, ISLAND_SHOP_CATALOG, resolve_island_goods_id
from tasks.savings_bank import SavingsBankTask, SAVINGS_PLANS, DEFAULT_DAYS as DEFAULT_SAVINGS_DAYS
from tasks.building import BuildingTask, BUILDING_INFO
from tasks.prestige import PrestigeTask
from tasks.prestige_box import PrestigeBoxTask
from tasks.troy_treasure import TroyTreasureTask
from tasks.hospital import HospitalTask



# ── إعداد نظام التسجيل (Logging) ───────────────────────────────────
# مستوى CRITICAL فقط (صمت تام) لتقليل الضجيج عند تشغيل 500+ قلعة
# (لا نُغيّر root logger حتى لا نؤثر على api_server)
_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter(
    "[%(asctime)s][%(levelname)s][%(name)s] %(message)s", datefmt="%H:%M:%S"
))
log = logging.getLogger("bot_manager")
log.setLevel(logging.CRITICAL)  # صمت تام — المعلومات تمر عبر log_callback
if not log.handlers:
    log.addHandler(_log_handler)
log.propagate = False  # لا نُكرر الرسائل في root logger


class _LogCallbackStream:
    """محوّل يحول log_callback إلى كائن شبيه بالملف ليعمل مع StreamHandler."""
    def __init__(self, callback):
        self._callback = callback
        self._buffer = ""

    def write(self, msg):
        self._buffer += msg
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self._callback(line)

    def flush(self):
        if self._buffer.strip():
            self._callback(self._buffer.strip())
            self._buffer = ""


def _safe_bind_task_logger(task: Any, log_cb: Optional[Any], level: int = logging.INFO) -> None:
    """تنظيف أي StreamHandler سابق وربط callback واحد فقط لمنع تكرار السجلات نهائياً عبر الدورات."""
    if not hasattr(task, "log") or not task.log:
        return
    task.log.propagate = False
    try:
        task.log.handlers.clear()
    except Exception:
        task.log.handlers = []
    if not log_cb:
        return
    try:
        h = logging.StreamHandler(_LogCallbackStream(log_cb))
        h.setLevel(level)
        h.setFormatter(logging.Formatter("%(message)s"))
        task.log.setLevel(level)
        task.log.addHandler(h)
    except Exception:
        pass


def _safe_unbind_task_logger(task: Any) -> None:
    """إزالة handler الـ callback بعد انتهاء تشغيل المهمة لمنع تراكمه في الذاكرة."""
    if not hasattr(task, "log") or not task.log:
        return
    try:
        task.log.handlers.clear()
    except Exception:
        task.log.handlers = []

# تشغيل وضع الحلقة الدائمة من سطر الأوامر:
#   python bot_manager.py --email "..." --loop
#   python bot_manager.py --email "..." --loop --loop-interval 30   (كل 30 دقيقة)
# ════════════════════════════════════════════════════════════════════════════════════════

DEFAULT_FIREBASE_USER_CONFIG: Dict[str, Any] = {
    # 🌾 1. مهمة حصد مزارع ومناجم المدينة (City Harvest)
    "city_harvest": {
        "enabled": True,             # تفعيل/تعطيل حصد مزارع الموارد داخل المدينة
    },

    # 🔬 2. مهمة أبحاث الأكاديمية والعلوم (Academy Research)
    "research": {
        "enabled": True,
    },

    # 🤝 3. مهمة التحالف ومساعدة الأعضاء وتبرعات العلوم (Alliance Task)
    "alliance": {
        "enabled": True,             # تفعيل/تعطيل مهام التحالف
        "auto_help": True,           # تقديم المساعدة التلقائية لطلبات أعضاء التحالف
        "gold_donations": 0,         # عدد تبرعات الذهب (0 = مجاني فقط بدون ذهب إطلاقاً لمنع استهلاك الذهب)
    },

    # 🚢 4. مهمة الميناء التجاري (Port Task)
    "port": {
        "enabled": True,             # تفعيل/تعطيل استقبال وتفريغ وإرسال سفن الميناء
    },

    # ⚔️ 5. مهمة تدريب وتجنيد الجنود (Train Troops)
    "train": {
        "enabled": True,             # تفعيل/تعطيل تدريب الجنود في الثكنات
        "levels": {                  # المستوى المستهدف للتدريب لكل نوع (العدد دائماً أقصى سعة max تلقائياً)
            "infantry": 6,          # مشاة
            "cavalry": 6,           # خيالة
            "archers": 6,           # رماة
            "chariots": 6,          # عربات
        },
    },

    # 🐾 6. مهمة دورية وتدريب الحيوانات الأليفة (Pet Patrol)
    "pet_patrol": {
        "enabled": True,             # تفعيل/تعطيل دورية الحيوان الأليف واستلام جوائزها
        "pet": "غزال",               # الحيوان القائم بالدورية: الغزال 1261 دائماً
        "destination": 1262,         # الحيوان المستهدف: الأسد 1262 افتراضياً
    },

    # 🚩 7. مهمة جمع جوائز التوسع الإقليمي (Territory Expansion)
    "territory_expansion": {
        "enabled": True,             # تفعيل/تعطيل جمع جوائز حدث التوسع الإقليمي
    },

    # 🛡️ 8. مهمة درع السلام التلقائي وحماية القلعة (Peace Shield)
    "shield": {
        "enabled": True,             # تفعيل/تعطيل درع السلام التلقائي لحماية القلعة
        "duration": "8h",            # مدة الدرع: "8h" (8 ساعات) أو "24h" (24 ساعة) أو "3d" (3 أيام)
        "allow_gold": False,         # السماح بالشراء بالذهب عند نفاد دروع الحقيبة المجانية (False افتراضياً لحماية الذهب)
    },

    # ⚡ 9. مهمة استخدام جرعات وشراء الطاقة (Stamina Task)
    "stamina": {
        "enabled": True,             # تفعيل/تعطيل مهمة استخدام وشراء الطاقة
        "gold_buys": 1,              # عدد مرات شراء الطاقة بالذهب المحدد من المستخدم (0 = مجاني فقط بدون شراء بالذهب)
    },

    # 🎯 10. مهمة تفعيل المهارات التلقائية (Skills Task)
    "skills": {
        "enabled": True,             # تفعيل/تعطيل مهمة تفعيل المهارات التلقائية
        "target_skills": [           # المهارات المطلوب تفعيلها: مهارة واحدة، أو مهارات محددة، أو "all" للكل
            "harvest",               # 🌾 الحصاد الوافر (Bountiful Harvest)
            "gather",                # ⚡ الجمع السريع (Crazy Gathering)
            "warehouse",             # 🏛️ حصاد المخزن (Warehouse Harvest)
        ],
    },

    # 🦸 11. مهمة تجنيد الأبطال وسحب الصناديق اليومية (Hero Draw)
    "hero_draw": {
        "enabled": True,             # تفعيل/تعطيل تجنيد الأبطال وبحث المهارات وسحب الصناديق اليومية تلقائياً
    },

    # 💎 11b. مهمة استكشاف جناح الكنز المجاني (Treasure Pavilion)
    "treasure_pavilion": {
        "enabled": True,             # تفعيل/تعطيل استكشاف جناح الكنز المجاني تلقائياً
    },

    # 🔨 11c. مهمة معمل الحدادة وصقل الرون المجاني (Blacksmith Forge)
    "blacksmith_forge": {
        "enabled": True,             # تفعيل/تعطيل صقل معمل الحدادة المجاني تلقائياً
    },

    # 🏛️ 11d. مهمة الضريح الإمبراطوري المجاني (Imperial Mausoleum / Pyramid)
    "imperial_mausoleum": {
        "enabled": True,             # تفعيل/تعطيل الضريح الإمبراطوري المجاني تلقائياً
    },

    # 📦 11e. مهمة صندوق التحالف المجاني (Alliance Treasure - إلزامي وتلقائي)
    "alliance_treasure": {
        "enabled": True,             # مهمة إلزامية تلقائية (حفر مجاني + طلب مساعدة + مساعدة الأعضاء)
        "index": 1,                  # رقم الصندوق المستهدف افتراضياً (1)
    },

    # 🎁 11f. مهمة الهدية الفاخرة اليومية (Daily Luxury Gift)
    "daily_luxury_gift": {
        "enabled": True,             # تفعيل/تعطيل جمع الهدية الفاخرة اليومية تلقائياً
    },

    # 👑 11g. مهمة صندوق الـ VIP اليومي المجاني (VIP Daily Free Gift)
    "vip_gift": {
        "enabled": True,             # تفعيل/تعطيل استلام صندوق الـ VIP اليومي المجاني تلقائياً
    },

    # 🏛️ 12. مهمة قاعة الاستراتيجيات وتطوير التكتيكات (Tactics Hall)
    "tactics_hall": {
        "enabled": True,             # تفعيل/تعطيل أبحاث قاعة الاستراتيجيات
        "tactic": "القلعة الفارغة",   # اسم أو معرف البحث المستهدف الذي يحدده المستخدم (مثال: "القلعة الفارغة", "قمة الاتقان", "البحث الكامل", 91010000)
    },

    # 💧 13. مهمة طاحونة الماء وزيادة إنتاج موارد القلعة (Watermill Production Boost)
    "watermill": {
        "enabled": True,             # تفعيل/تعطيل مهمة طاحونة الماء ومضاعفة إنتاج الموارد
        "types": "all",              # الموارد المطلوب تعزيزها: "all" (الكل)، أو محددة مثل: "food" (قمح), "wood" (خشب), "iron" (حديد), "diamond" (ألماس)
        "allow_shop_buy": True,      # السماح بالشراء التلقائي لأدوات التعزيز الناقصة من متجر التحالف بنقاط التحالف (True/False)
    },

    # ⛲ 14. مهمة نافورة الأمنيات الملكية وبئر الحظ (Trevi Fountain)
    "fountain": {
        "enabled": True,             # تفعيل/تعطيل مهمة نافورة الأمنيات وبئر الحظ
        "resources": [               # الموارد المطلوب التمني بها: "food" (قمح), "wood" (خشب), "iron" (حديد), "coal" (فحم), "diamond" (ألماس)
            "food",
            "wood",
            "iron",
            "diamond",
        ],
        "allow_gold": False,         # السماح بالشراء بالذهب بعد انتهاء المرات المجانية (False افتراضياً لحماية الذهب)
        "gold_times": 0,             # عدد مرات الشراء بالذهب لكل مورد محدد عند السماح بالشراء بالذهب
    },

    # 🔨 15. مهمة ورشة المواد وصناعة خامات العتاد (Material Workshop)
    "material_workshop": {
        "enabled": True,             # تفعيل/تعطيل تصنيع خامات العتاد في ورشة المواد
        "materials": [               # الخامات المطلوب تصنيعها: "fang" (الناب), "fur" (الفرو), "metal" (المعدن), "coal" (الفحم) أو "all" للكل
            "fang",
            "fur",
            "metal",
            "coal",
        ],
    },

    # 🐪 16. مهمة القافلة التجارية وحراسة الكنز (Caravan / Carriage Escort)
    "caravan": {
        "enabled": True,             # تفعيل/تعطيل إرسال القافلة وحراسة الكنز وجمع الجوائز تلقائياً
    },

    # ⚓ 18. مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة (Port Delegate & Island Store)
    "port_delegate": {
        "enabled": True,             # تفعيل/تعطيل مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة
        "shop_item": "7",            # المنتج المطلوب شراؤه بالكامل من متجر الجزيرة (رقم 1-7 أو اسمه أو all للكل)
    },

    # 🏦 19. مهمة دار الادخار وبنك التوفير (Savings Bank)
    "savings_bank": {
        "enabled": True,             # تفعيل/تعطيل استثمار الذهب وسحب الأرباح في دار الادخار تلقائياً
        "days": 7,                   # خطة الاستثمار والمدة المختارة بالأيام: 7 (أسبوعية), 15 (نصف شهرية), 30 (شهرية)
    },

    # 🏗️ 20. مهمة ترقية القلعة والمباني والتسريع (Building Upgrade & Castle)
    "building": {
        "enabled": True,                   # تفعيل/تعطيل مهمة البناء برمتها (الخيار الرابع)
        "upgrade_castle": True,            # ترقية القلعة ومتطلباتها (الخيار الأول)
        "speedup_castle": False,           # استخدام التسريع لترقية القلعة من الحقيبة والمجاني (الخيار الثاني)
        "upgrade_support_buildings": True, # ترقية المعسكرات والمراكز الطبية والمزارع وخيم العسكرية (الخيار الثالث)
    },

    # 🎖️ 22. مهمة مهام الهيبة اليومية داخل المدينة (Daily Prestige Quests)
    # ملاحظة: مهام المسيرات الخارجية (الغزاة، المعاقل، جمع الموارد 25k) نُقلت بالكامل لمنسق الفيالق march_manager
    "prestige": {
        "enabled": True,                   # تفعيل/تعطيل مهمة مهام الهيبة اليومية
        "subtasks": {                      # مهام الهيبة الداخلية
            "smuggler": True,              # متجر المهربين (10 مشتريات بالموارد)
            "watermill": True,             # الساقية وتفعيل مباني الموارد
            "train": True,                 # تدريب الجنود (250 من كل نوع مستوى 1)
            "fortress": True,              # حصن الحرب وتدريب الفخاخ
        },
    },

    # 🎁 22c. مهمة استلام صناديق مهام الهيبة والنشاط اليومي (Prestige Boxes)
    # تفحص نقاط النشاط اليومي واستلام الصناديق المستحقة (CMD 3105 / SUB 2)
    "prestige_box": {
        "enabled": True,                   # تفعيل/تعطيل استلام صناديق الهيبة اليومية تلقائياً
    },

    # 🏛️ 22d. مهمة كنز طروادة (Troy Treasure Task)
    # فحص مهام طروادة واستلام جوائز إنجاز المهام المستحقة (CMD 1028 / SUB 5)
    "troy_treasure": {
        "enabled": True,                   # تفعيل/تعطيل مهمة كنز طروادة
        "subtasks": {
            "claim_quests": True,          # استلام جوائز إنجاز المهام
        },
    },

    # 🏥 22b. مهمة معالجة الجنود الجرحى في المشفى (Hospital Cure Task)

    # تفحص جاهزية المشفى وتعالج كافة الجنود المصابين تلقائياً بالمشفى (mode: 0) قبل تشغيل منسق الفيالق
    "hospital": {
        "enabled": True,                   # تفعيل/تعطيل علاج الجنود بالمشفى تلقائياً
    },

    # 🎖️ 23. مهمة منسق الفيالق والمسيرات الذكي الموحد (March Manager & Orchestrator)
    # يدير كافة مسيرات الخريطة الخارجية للقلعة وفق مصفوفة أولويات ذكية (تأتي من فايربيس)
    "march_manager": {
        "enabled": True,                   # تفعيل/تعطيل منسق الفيالق كلياً
        "duration_minutes": 20,            # مدة تشغيل المهمة الإجمالية بالدقائق (ثلث ساعة = 20 دقيقة ككل)

        # [1] أولوية قتل غزاة الهيبة (Prestige Invaders)
        "prestige_invaders": {
            "enabled": True,               # تفعيل قتل غزاة الهيبة
        },

        # [2] أولوية الهجوم على المعقل الخاص بمهمة الهيبة (Prestige Stronghold)
        "prestige_stronghold": {
            "enabled": True,               # تفعيل الهجوم على معقل الهيبة
        },

        # [3] أولوية جمع الموارد لمهام الهيبة (Prestige Gathering)
        "prestige_gather": {
            "enabled": True,               # تفعيل جمع موارد الهيبة
        },

        # [4] إعدادات مساعدة الموارد (Transport)
        "transport": {
            "enabled": False,              # تفعيل مساعدة الموارد
            "target_x": None,              # إحداثي X للقلعة الهدف (مثال: 344)
            "target_y": None,              # إحداثي Y للقلعة الهدف (مثال: 447)
            "resource_ids": [1002, 1003, 1004, 1005],  # الموارد (1002=قمح, 1003=خشب, 1004=حديد, 1005=ألماس)
        },

        # [5] إعدادات استكشاف الأطلال (Ruins) — مسيرة واحدة فقط حصراً
        "ruins": {
            "enabled": True,               # تفعيل استكشاف الأطلال
            "explore_time": 900,           # مدة الاستكشاف بالثواني (900 = 15 دقيقة)
            "formation_id": 1,             # رقم التشكيلة العسكرية (1 إلى 5)
        },

        # [6] إعدادات القتال الشامل (Combat) — يحدد المستخدم خياراً واحداً حصراً (عفريت أو غزاة أو متمردين)
        "combat": {
            "enabled": True,               # تفعيل أولوية القتال
            "choice": "elf",               # الخيار المستهدف: "elf" (عفريت) أو "invaders" (غزاة) أو "rebels" (متمردين)
            "level": 30,                   # مستوى الهدف المطلوب مهاجمته (للغزاة/المتمردين)
            "formation_id": 1,             # رقم تشكيلة القتال (1 إلى 5)
        },
        # تخصيص كل هدف قتالي على حدة لدعم واجهات Firebase المتنوعة:
        "elf": {
            "enabled": True,               # تفعيل نخبة العفريت
            "formation_id": 1,             # رقم التشكيلة
        },
        "invaders": {
            "enabled": False,              # تفعيل الغزاة
            "level": 30,                   # مستوى الغزاة
            "formation_id": 1,             # رقم التشكيلة
        },
        "rebels": {
            "enabled": False,              # تفعيل المتمردين
            "level": 30,                   # مستوى المتمردين
            "formation_id": 1,             # رقم التشكيلة
        },

        # [7] إعدادات الهجوم على المعاقل والملاجئ العامة (Stronghold)
        "stronghold": {
            "enabled": False,              # تفعيل مهاجمة الملاجئ
            "level": 30,                   # مستوى الملجأ المستهدف (1 إلى 30)
            "count": 2,                    # عدد الملاجئ المستهدفة
            "formation_id": 1,             # رقم التشكيلة
        },

        # [8] إعدادات جمع الذهب في أراضي التحالفات (Gold Gather)
        "gold_gather": {
            "enabled": False,              # تفعيل جمع الذهب في أراضي التحالفات
            "locations": [],               # قائمة التحالفات المستهدفة: [{"alliance_tag": "POL", "x": 241, "y": 260}]
            "max_marches": 0,              # 0 = استغلال الفيالق المتاحة
        },

        # [9] إعدادات جمع الموارد الخارجية (Gathering) — تستهلك كافة الفيالق الشاغرة
        "gather": {
            "enabled": True,               # تفعيل جمع الموارد بالفيالق المتبقية حتى الامتلاء
            "res_type": 1,                 # نوع المورد: 1=ذهب, 2=قمح, 3=خشب, 4=حديد, 5=ألماس
            "level": 5,                    # مستوى حقل المورد بالضبط (1 إلى 7)
            "search_range": 100,           # نطاق البحث الأقصى حول القلعة
        },
    },
}




# ════════════════════════════════════════════════════════════════════
#  قاموس وتسميات المهارات التلقائية (Skill Aliases & Resolver)
# ════════════════════════════════════════════════════════════════════

SKILL_ALIASES: Dict[str, str] = {
    # 🌾 الحصاد الوافر (Bountiful Harvest)
    "harvest": "harvest", "الحصاد": "harvest", "حصاد": "harvest",
    "الحصاد الوافر": "harvest", "حصاد وافر": "harvest", "12008": "harvest",

    # ⚡ الجمع السريع (Crazy Gathering)
    "gather": "gather", "الجمع": "gather", "جمع": "gather",
    "الجمع السريع": "gather", "جمع سريع": "gather", "12022": "gather",

    # 🏛️ حصاد المخزن (Warehouse Harvest)
    "warehouse": "warehouse", "المخزن": "warehouse", "مخزن": "warehouse",
    "حصاد المخزن": "warehouse", "58120": "warehouse",
}

def resolve_target_skills(cfg_or_val: Any) -> List[str]:
    """
    تحليل وتطبيع خيارات المهارات المحددة من قبل المستخدم سواء كانت:
      - قائمة أسماء/معرفات: ["harvest", "gather"] أو ["الحصاد الوافر", "الجمع السريع"]
      - نص مفصول بفواصل: "harvest,gather" أو "الحصاد الوافر,الجمع السريع"
      - قاموس مفاتيح منطقية: {"harvest": True, "gather": True, "warehouse": False}
      - كلمة "all" أو "الكل" لتفعيل جميع المهارات
      - اسم مهارة واحدة: "harvest" أو "الحصاد الوافر"
    """
    if isinstance(cfg_or_val, dict):
        if "target_skills" in cfg_or_val:
            return resolve_target_skills(cfg_or_val["target_skills"])
        if "skills" in cfg_or_val and isinstance(cfg_or_val["skills"], (list, str, dict)):
            return resolve_target_skills(cfg_or_val["skills"])
        targets = []
        for k, v in cfg_or_val.items():
            if k == "enabled":
                continue
            if bool(v):
                resolved = SKILL_ALIASES.get(str(k).strip().lower())
                if resolved and resolved not in targets:
                    targets.append(resolved)
        return targets or list(SUPPORTED_SKILLS.keys())

    if isinstance(cfg_or_val, (list, tuple, set)):
        targets = []
        for item in cfg_or_val:
            s = str(item).strip().lower()
            if s in ("all", "الكل", "all_skills"):
                return list(SUPPORTED_SKILLS.keys())
            resolved = SKILL_ALIASES.get(s)
            if resolved and resolved not in targets:
                targets.append(resolved)
        return targets

    if isinstance(cfg_or_val, str):
        val = cfg_or_val.strip().lower()
        if val in ("all", "الكل", "all_skills", ""):
            return list(SUPPORTED_SKILLS.keys())
        targets = []
        for part in val.replace("،", ",").split(","):
            p = part.strip().lower()
            if p in ("all", "الكل"):
                return list(SUPPORTED_SKILLS.keys())
            resolved = SKILL_ALIASES.get(p)
            if resolved and resolved not in targets:
                targets.append(resolved)
        return targets

    return list(SUPPORTED_SKILLS.keys())


# ════════════════════════════════════════════════════════════════════
#  خيارات وخطط دار الادخار (Savings Bank Aliases)
# ════════════════════════════════════════════════════════════════════

SAVINGS_DAYS_ALIASES: Dict[str, int] = {
    "7": 7, "7d": 7, "7_days": 7, "أسبوع": 7, "اسبوع": 7, "أسبوعي": 7, "اسبوعي": 7, "weekly": 7,
    "15": 15, "15d": 15, "15_days": 15, "نصف_شهر": 15, "نصف شهر": 15, "biweekly": 15,
    "30": 30, "30d": 30, "30_days": 30, "شهر": 30, "شهري": 30, "monthly": 30,
}

def parse_savings_days(val: Any) -> int:
    """تحويل المدة المدخلة إلى أحد الخيارات الثلاثة الصالحة لدار الادخار: 7 أو 15 أو 30 يوماً."""
    if val is None:
        return DEFAULT_SAVINGS_DAYS
    s = str(val).strip().lower()
    if s.isdigit():
        d = int(s)
        if d in SAVINGS_PLANS:
            return d
    return SAVINGS_DAYS_ALIASES.get(s, DEFAULT_SAVINGS_DAYS)


# ── أهداف صناديق النشاط اليومي الستة لمهام المجد (Daily Glory & Merit Chests) ───
DAILY_MERIT_CHEST_GOALS: List[Tuple[int, int]] = [
    (1, 40),
    (2, 110),
    (3, 180),
    (4, 250),
    (5, 340),
    (6, 450),
]

# ── مسميات وأيقونات مهام المجد والنشاط اليومية (34 مهمة) ────────────────────
DAILY_MERIT_TASK_NAMES: Dict[int, Dict[str, str]] = {
    4112000: {"name": "جمع القمح من الخريطة", "icon": "🌾"},
    4112001: {"name": "جمع الخشب من الخريطة", "icon": "🪵"},
    4112002: {"name": "جمع الحجر من الخريطة", "icon": "⛏️"},
    4112003: {"name": "جمع الكوارتز من الخريطة", "icon": "💎"},
    4112004: {"name": "الهجوم على الغزاة في الخريطة", "icon": "⚔️"},
    4112005: {"name": "ترقية مباني القلعة", "icon": "🏗️"},
    4112006: {"name": "إجراء بحث علمي بالأكاديمية", "icon": "🔬"},
    4112007: {"name": "إهداء الزهور للوردات", "icon": "🌹"},
    4112008: {"name": "تقوية العتاد بمعمل الحدادة", "icon": "🔨"},
    4112009: {"name": "علاج الجنود المصابين بالمشفى", "icon": "🏥"},
    4112010: {"name": "تدريب جنود المشاة", "icon": "🛡️"},
    4112011: {"name": "تدريب الرماة", "icon": "🏹"},
    4112012: {"name": "تدريب الفرسان", "icon": "🐎"},
    4112013: {"name": "تدريب عربات الحصار", "icon": "🚜"},
    4112014: {"name": "تصنيع الفخاخ بحصن الحرب", "icon": "🏰"},
    4112015: {"name": "استلام موارد سفينة الشحن", "icon": "🚢"},
    4112016: {"name": "تقديم المساعدة لأعضاء التحالف", "icon": "🤝"},
    4112017: {"name": "إرسال تعزيزات عسكرية لحليف", "icon": "🛡️"},
    4112018: {"name": "إرسال معونات موارد لعضو تحالف", "icon": "📦"},
    4112019: {"name": "التبرع لتقنيات التحالف", "icon": "🧪"},
    4112020: {"name": "استلام جوائز وشحن الميناء", "icon": "⚓"},
    4112021: {"name": "رحلات القافلة والبحث عن الكنز", "icon": "🐪"},
    4112022: {"name": "الشراء من التاجر المتجول / المهربين", "icon": "🛒"},
    4112023: {"name": "استكشاف الضريح الإمبراطوري", "icon": "🏛️"},
    4112024: {"name": "استبدال الميداليات بمتجر الحرب", "icon": "🎖️"},
    4112025: {"name": "إنفاق واستهلاك الذهب", "icon": "🪙"},
    4112026: {"name": "استلام جوائز الباقة الأسبوعية", "icon": "🎁"},
    4112027: {"name": "تعزيز إنتاج حقول الموارد (الساقية)", "icon": "⚡"},
    4112028: {"name": "تجنيد وسحب الأبطال بقاعة الأبطال", "icon": "🦸"},
    4112029: {"name": "تطوير مستوى الأبطال بلفائف الخبرة", "icon": "📜"},
    4112030: {"name": "احتلال المعاقل والملاجئ", "icon": "🏰"},
    4112031: {"name": "معارك التحدي اليومي (الزنزانة)", "icon": "⚔️"},
    4112032: {"name": "قراءة الطالع / نظام المحظيات", "icon": "☕"},
    4112033: {"name": "مكاسب المحيطات الغامضة التلقائية", "icon": "🌊"},
}


# ════════════════════════════════════════════════════════════════════
#  كلاس سياق وبيانات الحساب (Account Context)
# ════════════════════════════════════════════════════════════════════

class AccountContext:
    """يحتفظ بالبيانات المستعلم عنها شاملاً عند بدء تشغيل الحساب."""
    def __init__(self, email: str):
        self.email: str = email
        self.uid: str = ""
        self.lord_name: str = email.split("@")[0] if email and "@" in email else (email or "قلعة")
        self.lord_level: int = 0
        self.kingdom_id: str = ""
        self.gold: int = 0
        self.total_power: int = 0
        self.stamina: int = 0
        self.castle_level: int = 0
        self.walls_level: int = 0
        
        # مستويات وحالات الثكنات الأربعة
        self.barracks_info: Dict[str, Dict[str, Any]] = {
            "infantry": {"bid": "118", "name": "المشاة", "level": 0, "state": "0", "training": False},
            "cavalry":  {"bid": "116", "name": "الخيالة", "level": 0, "state": "0", "training": False},
            "archers":  {"bid": "117", "name": "الأسهم", "level": 0, "state": "0", "training": False},
            "chariots": {"bid": "119", "name": "العربات", "level": 0, "state": "0", "training": False},
        }
        
        # طوابير العمل الحالية
        self.active_queues: Dict[str, Any] = {}
        
        # حالة أبحاث الأكاديمية
        self.research_status: Dict[str, Any] = {
            "is_busy": False,
            "tech_id": "",
            "tech_name": "",
            "remain_seconds": 0
        }

        # حالة الميناء
        self.available_ships: int = 0
        
        # مزارع ومناجم المدينة
        self.city_farms_count: int = 0
        self.city_farms_breakdown: Dict[str, int] = {"food": 0, "wood": 0, "iron": 0, "silver": 0}

        # حالة الحيوانات الأليفة
        self.unlocked_pets: Dict[int, Dict[str, Any]] = {}
        self.pet_patrol_status: Dict[str, Any] = {"active": False, "pet_name": "", "remain_seconds": 0}

        # بيانات التحالف
        self.alliance_id: int = 0
        self.alliance_name: str = "بدون تحالف"
        self.alliance_tag: str = ""
        self.alliance_available_donations: int = 0

        # جوائز حدث التوسع الإقليمي
        self.territory_ready_rewards: int = 0

        # دروع السلام المتوفرة في الحقيبة وحالة الحماية
        self.shield_backpack_counts: Dict[str, int] = {"8h": 0, "24h": 0, "3d": 0}
        self.shield_active: bool = False
        self.shield_status_str: str = "غير محمي (مكشوف)"

        # جرعات الطاقة المتوفرة في الحقيبة وسعر الشراء بالذهب
        self.stamina_potions: Dict[int, int] = {300401: 0, 300402: 0, 300403: 0}
        self.stamina_gold_cost: int = 0
        self.stamina_buy_times: int = 0
        self.stamina_limit_times: int = 0

        # حالة المهارات التلقائية (Skills)
        self.skills_status: List[Dict[str, Any]] = []

        # سحوبات وتجنيد الأبطال اليومية المجانية
        self.hero_draw_ready_count: int = 0

        # استكشاف جناح الكنز المجاني (Treasure Pavilion)
        self.treasure_pavilion_ready: bool = False
        self.treasure_pavilion_left_times: int = 0

        # صقل معمل الحدادة المجاني (Blacksmith Forge)
        self.blacksmith_forge_ready: bool = False
        self.blacksmith_forge_left_times: int = 0

        # استكشاف الضريح الإمبراطوري المجاني (Imperial Mausoleum / Pyramid)
        self.imperial_mausoleum_ready: bool = False
        self.imperial_mausoleum_has_award: bool = False
        self.imperial_mausoleum_free_throw: bool = False
        self.imperial_mausoleum_copper: int = 0
        self.imperial_mausoleum_dice_count: int = 0

        # فحص وحفر صندوق التحالف المجاني (Alliance Treasure)
        self.alliance_treasure_ready: bool = False
        self.alliance_treasure_in_alliance: bool = True
        self.alliance_treasure_free_dig_ready: bool = False
        self.alliance_treasure_can_receive: bool = False
        self.alliance_treasure_is_digging: bool = False
        self.alliance_treasure_dig_remain: int = 0
        self.alliance_treasure_dig_count: int = 0
        self.alliance_treasure_max_dig: int = 8
        self.alliance_treasure_left_free_today: int = 0

        # فحص واستلام الهدية الفاخرة اليومية (Daily Luxury Gift)
        self.daily_luxury_gift_ready: bool = False
        self.daily_luxury_gift_count: int = 0
        self.daily_luxury_gift_max_day: int = 0

        # فحص واستلام صندوق الـ VIP اليومي المجاني (VIP Daily Gift)
        self.vip_gift_ready: bool = False
        self.vip_lv: int = 0
        self.vip_point: int = 0

        # حالة أبحاث قاعة الاستراتيجيات (Tactics Hall)
        self.tactics_hall_status: Dict[str, Any] = {
            "active": False,
            "mid": 0,
            "tactic_name": "",
            "icon": "🏛️",
            "remain_seconds": 0
        }

        # حالة طاحونة الماء ومباني الموارد المعززة (Watermill Boost)
        self.watermill_boosted_count: int = 0

        # أمنيات نافورة الأمنيات الملكية المتاحة اليوم (Trevi Fountain)
        self.fountain_free_wishes: int = 0

        # حالة ورشة المواد وخامات العتاد (Material Workshop)
        self.workshop_status: Dict[str, Any] = {
            "occupied": 0,
            "capacity": 5,
            "active_name": "",
            "active_icon": "🔨",
            "remain_seconds": 0
        }

        # حالة القافلة وحراسة الكنز (Caravan / Carriage Escort)
        self.caravan_status: Dict[str, Any] = {
            "marching": False,
            "cargo_amount": 0,
            "remain_seconds": 0
        }

        # حالة التاجر المتجول (Traveling Merchant)
        self.merchant_status: Dict[str, Any] = {
            "is_open": False,
            "items_count": 0,
            "resource_items_count": 0
        }

        # حالة الميناء العسكري وتفويض السفن ومتجر الجزيرة (Port Delegate & Island Store)
        self.port_delegate_status: Dict[str, Any] = {
            "ready_tasks": 0,
            "running_tasks": 0,
            "claimable_tasks": 0,
            "island_points": 0,
        }

        # حالة دار الادخار وبنك التوفير (Savings Bank)
        self.savings_bank_status: Dict[str, Any] = {
            "has_slip": False,
            "deposit": 0,
            "days": 0,
            "remain_seconds": 0,
            "is_claimable": False
        }

        # حالة ترقية القلعة والمباني (Building & Queues Status)
        self.building_status: Dict[str, Any] = {
            "castle_level": 0,
            "walls_level": 0,
            "is_castle_upgrading": False,
            "active_queues": 0,
            "queues_info": []
        }

        # حالة حصن الحرب وفخاخ السور (War Fortress & Traps)
        self.fortress_status: Dict[str, Any] = {
            "level": 0,
            "is_training": False,
            "remain_seconds": 0,
            "standing_traps": 0,
            "wall_capacity": 0,
        }

        # حالة مهام المجد والنشاط اليومي (Meritorious / Glory Quests)
        self.merit_level: int = 0
        self.merit_exp: int = 0
        self.merit_daily_points: int = 0
        self.merit_chests_claimed: List[int] = []
        self.merit_chests_ready: List[Tuple[int, int]] = []
        self.merit_next_chest_goal: int = 0
        self.merit_next_chest_remain: int = 0
        self.merit_tasks_total: int = 0
        self.merit_tasks_claimed: int = 0
        self.merit_tasks_ready: int = 0
        self.merit_tasks_in_progress: int = 0
        self.merit_tasks_details: List[Dict[str, Any]] = []

        # البيانات الخام الكاملة
        self.raw_city: List[Dict[str, Any]] = []
        self.raw_lord: Dict[str, Any] = {}


# ════════════════════════════════════════════════════════════════════
#  كلاس مدير البوت الرئيسي (BotManager)
# ════════════════════════════════════════════════════════════════════

class BotManager:
    """
    مدير البوت ومنسق المهام:
      1. يسجل الدخول للحساب.
      2. يقوم بالاستعلام الشامل.
      3. ينفذ المهام بالترتيب المحدد ويمرر الخيارات والبيانات لكل مهمة.
    """

    # ─────────────────────────────────────────────────────────────────────────
    #  قائمة المهام الإلزامية التي تُنفَّذ دائماً في كل دورة بدون اشتراط تفعيل المستخدم
    #  (Mandatory Tasks) — أي مهمة تضاف هنا تعمل دائماً وتتجاوز أي تعطيل أو جدول زمني
    # ─────────────────────────────────────────────────────────────────────────
    MANDATORY_TASKS: Set[str] = {
        "city_harvest",        # حصد كافة مزارع ومناجم المدينة تلقائياً وبشكل دوري
        "treasure_pavilion",   # استكشاف جناح الكنز المجاني تلقائياً في كل دورة
        "blacksmith_forge",    # صقل معمل الحدادة المجاني تلقائياً في كل دورة
        "imperial_mausoleum",  # الضريح الإمبراطوري المجاني تلقائياً في كل دورة
        "alliance_treasure",   # صندوق التحالف المجاني تلقائياً في كل دورة
        "daily_luxury_gift",   # استلام الهدية الفاخرة اليومية تلقائياً في كل دورة
        "vip_gift",            # استلام صندوق الـ VIP المجاني تلقائياً في كل دورة
    }

    def __init__(
        self,
        account_or_email: Union[str, AccountSession],
        config: Optional[Dict[str, Any]] = None,
        reconnect_wait_seconds: int = 60,
        max_reconnect_attempts: int = 10,
        ignore_schedule: bool = False,
        user_id: Optional[str] = None,
        castle_id: Optional[str] = None,
        stop_event: Optional[threading.Event] = None,   # ← للـ Thread Pool: إشارة إيقاف خارجية
        log_callback: Optional[Callable[[str], None]] = None,  # ← للـ Thread Pool: بدل print()
    ):
        if isinstance(account_or_email, str):
            sm = SessionManager()
            acc = sm.get_or_login(account_or_email, user_id=user_id, castle_id=castle_id)
            if not acc:
                raise ValueError(f"الحساب {account_or_email} غير موجود في الكاش ولم يتم العثور على كلمة مرور لتسجيل دخوله!")
            self.account = acc
        else:
            self.account = account_or_email

        self.email = self.account.email
        self.conn: Optional[GameConnection] = None
        self.context = AccountContext(self.email)
        self.ignore_schedule = bool(ignore_schedule)
        self.user_id = user_id
        self.castle_id = castle_id
        self.is_loop = False

        # Thread Pool support: stop signal + log routing
        self._stop_event: threading.Event = stop_event or threading.Event()
        self._log_callback: Optional[Callable[[str], None]] = log_callback

        # دمج الإعدادات الافتراضية مع إعدادات المستخدم من قاعدة البيانات المحلية
        self.config = self._build_default_config(config or {})
        # جلب أحدث إعدادات القلعة مباشرة من قاعدة البيانات المحلية
        self.reload_config_from_db()

        # إعدادات إعادة الاتصال التلقائي عند دخول شخص آخر للحساب
        self.reconnect_wait_seconds = int(reconnect_wait_seconds)
        self.max_reconnect_attempts = int(max_reconnect_attempts)
        self._disconnected_event = asyncio.Event()
        self._last_kick_reason: str = ""

    def _update_bot_conn_state(self, conn_state: str, message: str = "", next_run_time: Optional[str] = None) -> None:
        """إبلاغ لوحة التحكم وقاعدة البيانات المحلية بحالة اتصال اللعبة الفعلية (دخول، انقطاع، إعادة اتصال، انتظار)."""
        # 🛑 حظر صارم ولحظي: إذا طُلب إيقاف البوت، يُمنع منعاً باتاً بث أو تسجيل أي حالة نشطة (connected / reconnecting / waiting)
        if self._stop_event.is_set() and conn_state in ("connected", "reconnecting", "waiting"):
            return

        nr_arg = f" next_run_time={next_run_time}" if next_run_time else ""
        event_line = f"[BOT_EVENT] conn_state={conn_state} message={message}{nr_arg}"
        # Thread Pool: توجيه عبر log_callback / CLI: print() مباشرة
        if self._log_callback:
            self._log_callback(event_line)
        else:
            print(event_line, flush=True)

        # تحديث كاش قاعدة البيانات المحلية SQLite فوراً
        try:
            from core.database import upsert_castle_conn_state
            upsert_castle_conn_state(
                email=getattr(self, "email", ""),
                conn_state=conn_state,
                message=message,
                next_run_time=next_run_time,
                user_id=getattr(self, "user_id", None),
                castle_id=getattr(self, "castle_id", None)
            )
        except Exception as e:
            log.debug(f"SQLite conn state update: {e}")

    def stop(self) -> None:
        """إيقاف فوري ولحظي للبوت وقطع مقبس الاتصال فوراً لإنهاء أي مهمة أو انتظار دون أي تأخير."""
        self._stop_event.set()
        if self.conn:
            try:
                if hasattr(self.conn, "_gate") and self.conn._gate:
                    gate = self.conn._gate
                    gate._explicit_close = True
                    gate._alive = False
                    for task in (gate._recv_task, gate._heartbeat_task, gate._init_flow_task):
                        if task and not task.done():
                            try:
                                task.cancel()
                            except Exception:
                                pass
                    if hasattr(gate, "_writer") and gate._writer:
                        try:
                            gate._writer.close()
                        except Exception:
                            pass
            except Exception:
                pass
        self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")

    def check_subscription_validity(self) -> Tuple[bool, str]:
        """فحص صلاحية اشتراك المستخدم وحالة الحظر محلياً من SQLite بدون أي اتصال بالشبكة."""
        try:
            user_id = getattr(self, "user_id", None)
            if not user_id:
                # محاولة البحث عن معرف المستخدم عبر البريد في SQLite
                from core.database import get_castle
                c = get_castle(self.email)
                if c and c.get("user_id"):
                    self.user_id = c["user_id"]
                    self.castle_id = c.get("castle_id", getattr(self, "castle_id", None))
                    user_id = self.user_id

            if not user_id:
                return True, "صالح افتراضياً (لم يُحدد مستخدم)"

            from core.database import check_user_subscription_db
            return check_user_subscription_db(user_id)
        except Exception as e:
            log.warning(f"⚠️ تنبيه أثناء التحقق من صلاحية الاشتراك محلياً: {e}")
            return True, "تعذر التحقق"

    def sync_castle_resources(self) -> None:
        """تحديث بيانات موارد ومعلومات القلعة في بداية كل دورة في SQLite المحلية."""
        if not self.conn or not getattr(self.conn, "init_data", None):
            return

        try:
            lord_ctrl = self.conn.init_data.get("lordInfoCtrl", {})
            base_info = lord_ctrl.get("base", {}) if isinstance(lord_ctrl, dict) else {}
            fc_info   = lord_ctrl.get("fcInfo", {}) if isinstance(lord_ctrl, dict) else {}
            city_ctrl = self.conn.init_data.get("cityCtrl", {})
            reslist   = city_ctrl.get("reslist", {}) if isinstance(city_ctrl, dict) else {}
            saferes   = city_ctrl.get("saferes", {}) if isinstance(city_ctrl, dict) else {}

            food    = int(float(reslist.get("1002", saferes.get("1002", 0))))
            wood    = int(float(reslist.get("1003", saferes.get("1003", 0))))
            iron    = int(float(reslist.get("1004", saferes.get("1004", 0))))
            diamond = int(float(reslist.get("1005", saferes.get("1005", 0))))
            gold    = int(float(base_info.get("gold", reslist.get("1006", saferes.get("1006", 0)))))
            stamina = int(float(base_info.get("health", 100)))
            pos     = base_info.get("sourcePos", {}) if isinstance(base_info, dict) else {}
            coords  = {"x": int(pos.get("x", 0)), "y": int(pos.get("y", 0))}

            from datetime import timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            res_data = {
                "food":         food,
                "wood":         wood,
                "iron":         iron,
                "diamond":      diamond,
                "gold":         gold,
                "stamina":      stamina,
                "last_updated": now_iso,
            }

            cinfo_data = {
                "lord_name":    str(base_info.get("nickName", self.email.split("@")[0])),
                "lord_power":   int(fc_info.get("totalFc", getattr(self.context, "total_power", 0))),
                "castle_level": max(1, getattr(self.context, "castle_level", 1)),
                "walls_level":  getattr(self.context, "walls_level", 0),
                "server_id":    int(base_info.get("partition", 1)) if str(base_info.get("partition", "")).isdigit() else 1,
                "coordinates":  coords,
                "uid":          str(base_info.get("uid", getattr(self.account, "user_id", ""))),
            }

            # إرسال السطر للـ api_server (Thread Pool: log_callback / CLI: print)
            _sync_line = f"[RESOURCE_SYNC] food={food} wood={wood} iron={iron} diamond={diamond} gold={gold} stamina={stamina} power={cinfo_data['lord_power']}"
            if self._log_callback:
                self._log_callback(_sync_line)
            else:
                print(_sync_line, flush=True)

            log.info(f"🌾 [تحديث موارد الدورة] قمح={food:,} خشب={wood:,} حديد={iron:,} زمرد={diamond:,} ذهب={gold:,} طاقة={stamina} | اللورد: {cinfo_data['lord_name']} (Lv {cinfo_data['castle_level']})")

            # تحديث كاش قاعدة البيانات المحلية SQLite فوراً
            try:
                from core.database import upsert_castle_resources
                upsert_castle_resources(
                    email=getattr(self, "email", ""),
                    resources=res_data,
                    castle_info=cinfo_data,
                    user_id=getattr(self, "user_id", None),
                    castle_id=getattr(self, "castle_id", None)
                )
            except Exception as e:
                log.debug(f"SQLite resources update: {e}")

        except Exception as e:
            log.warning(f"⚠️ تنبيه أثناء استخراج ومزامنة الموارد: {e}")

    def _build_default_config(self, user_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """بناء قاموس الإعدادات بدمج إعدادات المستخدم مع المخطط الافتراضي."""
        cfg = copy.deepcopy(DEFAULT_FIREBASE_USER_CONFIG)
        for section, values in (user_cfg or {}).items():
            if section in cfg and isinstance(values, dict) and isinstance(cfg[section], dict):
                cfg[section].update(values)
            else:
                cfg[section] = values
        return cfg

    def reload_config_from_db(self) -> None:
        """
        استعلام وجلب أحدث إعدادات المهام للقلعة من قاعدة البيانات المحلية SQLite في بداية كل دورة،
        لضمان تطبيق أي تعديلات قام بها المستخدم في لوحة التحكم أثناء تشغيل البوت فوراً في الدورة التالية
        بدون الحاجة لإعادة تشغيل البوت يدوياً.
        """
        try:
            from core.database import get_castle_by_id, get_castle
            c = None
            cid = getattr(self, "castle_id", None)
            uid = getattr(self, "user_id", None)
            em = getattr(self, "email", None)

            if cid:
                c = get_castle_by_id(cid, uid)
            if not c and em:
                c = get_castle(em)

            if c and isinstance(c.get("config"), dict) and c["config"]:
                latest_cfg = c["config"]
                self.config = self._build_default_config(latest_cfg)
                log.info(f"🔄 [{self.email}] تم تحديث إعدادات المهام بنجاح من قاعدة البيانات المحلية للدورة الحالية.")
        except Exception as ex:
            log.warning(f"⚠️ تعذر استعلام إعدادات القلعة من قاعدة البيانات: {ex}")

    def is_connection_alive(self) -> bool:
        """التحقق هل اتصال الحساب مع السيرفر نشط وما زال يعمل بصحة كاملة."""
        if self._disconnected_event.is_set():
            return False
        if not self.conn or not self.conn.is_connected:
            return False
        return True

    def get_disconnect_reason(self) -> str:
        """استخراج سبب انقطاع الاتصال (دخول شخص آخر أو غيره)."""
        r = self._last_kick_reason or (self.conn.kick_reason if self.conn else "")
        if r in ("other_device", "kick"):
            return "دخول شخص آخر إلى الحساب (Other Device Login)"
        elif r == "account_sealed":
            return "الحساب محظور أو مغلق (Account Sealed)"
        elif r == "server_maintenance":
            return "صيانة السيرفر (Server Maintenance)"
        elif r:
            return f"انقطاع اتصال: {r}"
        return "دخول شخص آخر إلى الحساب"

    async def wait_and_reconnect(self, reason: str = "") -> bool:
        """
        الانتظار دقيقة واحدة (60 ثانية) عند انقطاع الاتصال بسبب دخول شخص آخر،
        ثم إعادة تسجيل الدخول وتحديث بيانات الحساب لاستئناف المهام التي توقفت.
        """
        if self._stop_event.is_set():
            if self.conn:
                try:
                    await self.conn.close()
                except Exception:
                    pass
            self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
            return False

        display_reason = reason or self.get_disconnect_reason()
        if not self._log_callback:
            print("\n" + "!" * 70)
        log.warning(f"⚠️ [انقطاع الاتصال] تم رصد انقطاع الاتصال بالحساب (السبب: {display_reason})!")
        log.warning(f"⏳ سيتوقف البوت مؤقتاً وينتظر {self.reconnect_wait_seconds} ثانية...")
        if not self._log_callback:
            print("!" * 70 + "\n")

        self._update_bot_conn_state("disconnected", f"تم تسجيل الدخول من جهاز آخر: {display_reason}")

        for attempt in range(1, self.max_reconnect_attempts + 1):
            if self._stop_event.is_set():
                if self.conn:
                    try:
                        await self.conn.close()
                    except Exception:
                        pass
                self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                return False

            log.info(f"⏳ [المحاولة {attempt}/{self.max_reconnect_attempts}] انتظار {self.reconnect_wait_seconds} ثانية (دقيقة واحدة)...")
            self._update_bot_conn_state("reconnecting", f"جاري انتظار إعادة الاتصال (المحاولة {attempt}/{self.max_reconnect_attempts})...")
            wait_time = self.reconnect_wait_seconds
            while wait_time > 0:
                if self._stop_event.is_set():
                    log.info("🛑 [إيقاف فوري ولحظي] تم استلام أمر إيقاف البوت أثناء انتظار إعادة الاتصال — إنهاء الانتظار فوراً.")
                    if self.conn:
                        try:
                            await self.conn.close()
                        except Exception:
                            pass
                    self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                    return False

                if wait_time in (60, 45, 30, 15, 5):
                    log.info(f"⏳ متبقي على إعادة محاولة الدخول: {wait_time} ثانية...")

                # فحص سريع ومجزء جداً (كل 0.25 ثانية) لضمان الاستجابة اللحظية الفورية لأمر الإيقاف دون أي تأخير
                step_sleep = min(1.0, float(wait_time))
                slept = 0.0
                while slept < step_sleep:
                    if self._stop_event.is_set():
                        log.info("🛑 [إيقاف فوري ولحظي] تم استلام أمر إيقاف البوت أثناء انتظار إعادة الاتصال — إنهاء الانتظار فوراً.")
                        if self.conn:
                            try:
                                await self.conn.close()
                            except Exception:
                                pass
                        self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                        return False
                    await asyncio.sleep(0.25)
                    slept += 0.25
                wait_time -= int(step_sleep)

            if self._stop_event.is_set():
                log.info("🛑 [إيقاف فوري ولحظي] تم استلام أمر إيقاف البوت قبل بدء تسجيل الدخول — إلغاء الدخول فوراً.")
                if self.conn:
                    try:
                        await self.conn.close()
                    except Exception:
                        pass
                self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                return False

            log.info(f"🔄 جاري محاولة تسجيل الدخول الآن واستئناف المهام (المحاولة {attempt}/{self.max_reconnect_attempts})...")

            # إغلاق الاتصال القديم بأمان
            if self.conn:
                try:
                    await self.conn.close()
                except Exception:
                    pass

            self._disconnected_event.clear()
            connected = await self.login_and_connect()

            if self._stop_event.is_set():
                log.info("🛑 [إيقاف فوري ولحظي] تم استلام أمر إيقاف البوت بعد محاولة تسجيل الدخول — قطع الاتصال فوراً.")
                if self.conn:
                    try:
                        await self.conn.close()
                    except Exception:
                        pass
                self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                return False

            if connected:
                try:
                    await self.perform_comprehensive_query()
                except Exception as e:
                    log.warning(f"⚠️ تنبيه أثناء تحديث بيانات الحساب بعد الدخول: {e}")

                if self._stop_event.is_set():
                    if self.conn:
                        try:
                            await self.conn.close()
                        except Exception:
                            pass
                    self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                    return False

                try:
                    self.sync_castle_resources()
                except Exception:
                    pass
                log.info("🎉 تم إعادة تسجيل الدخول بنجاح تام! جاهز لاستئناف المهام المتوقفة... ✅")
                self._update_bot_conn_state("connected", "تمت إعادة الاتصال بالقلعة بنجاح")
                return True
            else:
                log.warning(f"⚠️ لم تنجح محاولة تسجيل الدخول #{attempt} (قد يكون المستخدم ما زال نشطاً داخل الحساب).")

        log.error(f"❌ استنفدت جميع محاولات إعادة تسجيل الدخول ({self.max_reconnect_attempts} محاولات).")
        return False

    # ─────────────────────────────────────────────────────────────────
    #  1. تسجيل الدخول والمصافحة
    # ─────────────────────────────────────────────────────────────────
    async def login_and_connect(self) -> bool:
        """الاتصال والمصافحة مع سيرفر اللعبة مرة واحدة، مع مراقبة انقطاع الاتصال تلقائياً."""
        if self._stop_event.is_set():
            return False

        log.info(f"🔐 [تسجيل الدخول] بدء الاتصال بالحساب: {self.email}...")
        self._disconnected_event.clear()
        self._last_kick_reason = ""

        def _on_disconnect(reason: str):
            self._disconnected_event.set()
            self._last_kick_reason = reason or "other_device"
            log.warning(f"⚠️ [تنبيه السيرفر] انقطع اتصال الحساب {self.email} (السبب: {self._last_kick_reason})")

        if self._stop_event.is_set():
            return False

        self.conn = GameConnection(self.account, on_disconnect=_on_disconnect)
        ok = await self.conn.connect()

        if self._stop_event.is_set():
            if self.conn:
                try:
                    await self.conn.close()
                except Exception:
                    pass
            return False

        if not ok and self.user_id and self.castle_id:
            if self._stop_event.is_set():
                return False
            log.warning(f"⚠️ [تسجيل الدخول] فشل الاتصال بالجلسة الحالية لـ {self.email}. جاري تجديد الجلسة تلقائياً بكلمة المرور...")
            sm = SessionManager()
            fresh_acc = sm.refresh_session(self.email, user_id=self.user_id, castle_id=self.castle_id)
            if fresh_acc:
                if self._stop_event.is_set():
                    return False
                self.account = fresh_acc
                self.conn = GameConnection(self.account, on_disconnect=_on_disconnect)
                ok = await self.conn.connect()
                if self._stop_event.is_set():
                    if self.conn:
                        try:
                            await self.conn.close()
                        except Exception:
                            pass
                    return False

        if not ok:
            log.error(f"❌ [تسجيل الدخول] فشل الاتصال بالحساب {self.email}!")
            return False

        if self._stop_event.is_set():
            if self.conn:
                try:
                    await self.conn.close()
                except Exception:
                    pass
            return False

        # انتظار وصول حزم التهيئة الأولية للبث (init_data)
        log.info("⏳ انتظار مزامنة الحزم الأولية من السيرفر...")
        for _ in range(15):
            if self._stop_event.is_set():
                if self.conn:
                    try:
                        await self.conn.close()
                    except Exception:
                        pass
                return False
            await asyncio.sleep(0.3)
            if len(self.conn.init_data) > 0:
                break

        if self._stop_event.is_set():
            if self.conn:
                try:
                    await self.conn.close()
                except Exception:
                    pass
            return False

        log.info(f"✅ [تسجيل الدخول] تم الاتصال والمصافحة بنجاح 100%!")
        self._update_bot_conn_state("connected", "تم الاتصال بالقلعة بنجاح 100%")
        return True

    # ─────────────────────────────────────────────────────────────────
    #  2. الاستعلام الشامل (Comprehensive Query)
    # ─────────────────────────────────────────────────────────────────
    async def perform_comprehensive_query(self) -> AccountContext:
        """
        إجراء استعلام شامل لحالة الحساب:
          - بيانات اللورد والقوة والذهب (init_data)
          - مباني المدينة ومستويات الثكنات (1001/1)
          - طوابير البناء والتدريب والأبحاث (1003/1)
          - سفن الميناء المتاحة (1033/2)
          - الحيوانات الأليفة المفتوحة وحالة الدورية (petCtrl)
        """
        log.info("🔍 [الاستعلام الشامل] جلب كافة بيانات ومعلومات الحساب من السيرفر...")

        ctx = self.context

        # 1. بيانات اللورد من init_data أو عبر 1002/7 إذا لم تكن متوفرة
        lord_ctrl = self.conn.init_data.get("lordInfoCtrl", {})
        base_info = lord_ctrl.get("base", {}) if isinstance(lord_ctrl, dict) else {}
        fc_info = lord_ctrl.get("fcInfo", {}) if isinstance(lord_ctrl, dict) else {}

        if not base_info or not fc_info:
            uid_val = getattr(self.conn, "uid", None) or getattr(self.account, "user_id", None)
            if uid_val:
                try:
                    uid_int = int(uid_val) if str(uid_val).isdigit() else uid_val
                    r_lord = await self.conn.query("1002", "7", {"uid": uid_int}, timeout=6)
                    if r_lord and isinstance(r_lord.get("data"), dict):
                        base_info = r_lord["data"].get("base", {}) or base_info
                        fc_info = r_lord["data"].get("fcInfo", {}) or fc_info
                        if "lordInfoCtrl" not in self.conn.init_data:
                            self.conn.init_data["lordInfoCtrl"] = {}
                        self.conn.init_data["lordInfoCtrl"]["base"] = base_info
                        self.conn.init_data["lordInfoCtrl"]["fcInfo"] = fc_info
                except Exception as e:
                    log.warning(f"⚠️ تعذر جلب بيانات اللورد عبر 1002/7: {e}")

        ctx.lord_name = str(base_info.get("nickName", self.email.split('@')[0]))
        ctx.lord_level = int(base_info.get("level", 0))
        ctx.kingdom_id = str(base_info.get("partition", ""))
        ctx.gold = int(base_info.get("gold", 0))
        ctx.total_power = int(fc_info.get("totalFc", 0))
        ctx.uid = str(base_info.get("uid", getattr(self.account, "user_id", "")))
        ctx.stamina = int(float(base_info.get("health", 100)))

        # 2. استعلام مباني المدينة 1001/1 وتحديث كاش الموارد والمباني
        r_city = await self.conn.query("1001", "1", {}, timeout=8)
        city_data = r_city.get("data", {}) if r_city and isinstance(r_city, dict) else {}
        blist = city_data.get("blist", [])
        if not blist and "cityCtrl" in self.conn.init_data:
            blist = self.conn.init_data["cityCtrl"].get("blist", [])

        if "cityCtrl" not in self.conn.init_data:
            self.conn.init_data["cityCtrl"] = {}
        if city_data:
            self.conn.init_data["cityCtrl"].update(city_data)

        ctx.raw_city = blist

        # تحليل المباني الهامة: القلعة (101)، الأسوار (102)، والثكنات الأربعة (118, 116, 117, 119)
        barrack_bid_map = {
            "118": "infantry",
            "116": "cavalry",
            "117": "archers",
            "119": "chariots"
        }

        for item in blist:
            binfo = item.get("binfo", {}) if isinstance(item, dict) else {}
            bid = str(binfo.get("bid", ""))
            lv = int(binfo.get("lv", 0))
            state = str(binfo.get("state", "0"))

            if bid == "101":
                ctx.castle_level = lv
            elif bid == "102":
                ctx.walls_level = lv
            elif bid == "120":
                ctx.fortress_status["level"] = lv
            elif bid in barrack_bid_map:
                b_key = barrack_bid_map[bid]
                ctx.barracks_info[b_key]["level"] = lv
                ctx.barracks_info[b_key]["state"] = state
                ctx.barracks_info[b_key]["index"] = str(binfo.get("index", ""))
            elif bid == "201":
                ctx.city_farms_breakdown["food"] += 1
            elif bid == "202":
                ctx.city_farms_breakdown["wood"] += 1
            elif bid == "203":
                ctx.city_farms_breakdown["iron"] += 1
            elif bid == "204":
                ctx.city_farms_breakdown["silver"] += 1

        ctx.city_farms_count = sum(ctx.city_farms_breakdown.values())

        # 3. استعلام طوابير البناء والتدريب 1003/1
        r_queues = await self.conn.query("1003", "1", {}, timeout=8)
        q_data = r_queues.get("data", {}) if r_queues and isinstance(r_queues.get("data"), dict) else {}
        ctx.active_queues = q_data

        training_queue_map = {
            "1203": "infantry",
            "1204": "cavalry",
            "1205": "archers",
            "1206": "chariots"
        }
        for qid, b_key in training_queue_map.items():
            if qid in q_data and q_data[qid]:
                ctx.barracks_info[b_key]["training"] = True
                remain = float(q_data[qid].get("totaltime", 0))
                ctx.barracks_info[b_key]["remain_time"] = remain

        # فحص طوابير البناء وحالة ترقية القلعة (1200 و 1201)
        b_queues = []
        is_castle_upg = False
        for b_qid in ["1200", "1201"]:
            if b_qid in q_data and q_data[b_qid]:
                q_info = q_data[b_qid]
                q_subdata = q_info.get("data", {}) if isinstance(q_info, dict) else {}
                bid = str(q_subdata.get("bid", ""))
                lv = int(q_subdata.get("lv", 0))
                rem = float(q_info.get("totaltime", 0))
                if bid == "101":
                    is_castle_upg = True
                b_queues.append({"qid": b_qid, "bid": bid, "lv": lv, "remain": rem})
        ctx.building_status = {
            "castle_level": ctx.castle_level,
            "walls_level": ctx.walls_level,
            "is_castle_upgrading": is_castle_upg,
            "active_queues": len(b_queues),
            "queues_info": b_queues
        }

        # فحص طابور تدريب فخاخ حصن الحرب (1207) وإحصاء الفخاخ القائمة
        fortress_q = q_data.get("1207")
        if not fortress_q:
            for _qid, _qd in q_data.items():
                if isinstance(_qd, dict) and str(_qd.get("data", {}).get("bid")) == "120":
                    fortress_q = _qd
                    break
        if fortress_q and isinstance(fortress_q, dict):
            ctx.fortress_status["is_training"] = True
            st = int(fortress_q.get("starttime", 0))
            tt = int(fortress_q.get("totaltime", 0))
            now_ts = int(time.time())
            ctx.fortress_status["remain_seconds"] = max(0, (st + tt) - now_ts) if st > 0 else int(tt)

        army_ctrl = self.conn.init_data.get("armyCtrl", {})
        total_army = army_ctrl.get("totalArmy", {}) if isinstance(army_ctrl, dict) else {}
        st_count = 0
        if isinstance(total_army, dict):
            for aid_str, cnt in total_army.items():
                try:
                    aid = int(aid_str)
                    if 800 <= aid <= 899:
                        st_count += int(cnt)
                except Exception:
                    pass
        ctx.fortress_status["standing_traps"] = st_count
        ctx.fortress_status["wall_capacity"] = ctx.walls_level * 1000

        # 4. فحص سفن الميناء 1033/2
        r_port = await self.conn.query("1033", "2", {}, timeout=6)
        if r_port and "data" in r_port:
            ships = r_port["data"].get("shipList", [])
            available = sum(1 for s in ships if s.get("status", 0) == 0)
            ctx.available_ships = available

        # 5. فحص حالة طابور الأبحاث في مبنى الأكاديمية 1017/3
        r_tech = await self.conn.query("1017", "3", {}, timeout=6)
        if r_tech and r_tech.get("err") == "0":
            t_data = r_tech.get("data", {})
            t_rem = float(t_data.get("remainTime", 0))
            t_extra = t_data.get("extraData", {})
            if t_rem > 0 and isinstance(t_extra, dict):
                t_keys = [k for k in t_extra.keys() if str(k).isdigit()]
                if t_keys:
                    cur_tid = t_keys[0]
                    tech_dict = load_tech_names()
                    t_name = tech_dict.get(str(cur_tid), {}).get("name_ar", f"بحث #{cur_tid}")
                    ctx.research_status = {
                        "is_busy": True,
                        "tech_id": str(cur_tid),
                        "tech_name": t_name,
                        "remain_seconds": int(t_rem)
                    }

        # 6. فحص بيانات التحالف (allianceCtrl) ورصيد التبرعات المتاحة (1010/81)
        alliance_ctrl = self.conn.init_data.get("allianceCtrl", {})
        if isinstance(alliance_ctrl, dict):
            a_info = alliance_ctrl.get("allianceInfo", {})
            if isinstance(a_info, dict) and a_info.get("aid"):
                ctx.alliance_id = int(a_info.get("aid", 0))
                ctx.alliance_name = str(a_info.get("name") or "بدون تحالف")
                ctx.alliance_tag = str(a_info.get("tag") or "")
            if "memberinfo" in alliance_ctrl:
                minfo = alliance_ctrl.get("memberinfo", {}).get("minfo", {})
                uinfo = alliance_ctrl.get("memberinfo", {}).get("uinfo", {})
                if isinstance(minfo, dict) and minfo.get("aid"):
                    ctx.alliance_id = int(minfo.get("aid", 0))
                    if minfo.get("donateCount") is not None:
                        ctx.alliance_available_donations = int(minfo.get("donateCount", 0))
                if isinstance(uinfo, dict):
                    if uinfo.get("allianceName"):
                        ctx.alliance_name = str(uinfo.get("allianceName"))
                    if uinfo.get("allianceAbbr"):
                        ctx.alliance_tag = str(uinfo.get("allianceAbbr"))

        if ctx.alliance_id == 0:
            lord_data = self.conn.init_data.get("lord", {})
            ctx.alliance_id = int(lord_data.get("alliance", 0)) if isinstance(lord_data, dict) else 0

        if ctx.alliance_id > 0:
            try:
                r_81 = await self.conn.query("1010", "81", {"uid": int(ctx.uid) if ctx.uid else 0}, timeout=6)
                if r_81 and r_81.get("err") == "0":
                    retdata = r_81.get("data", {}).get("retdata", {})
                    ctx.alliance_available_donations = int(retdata.get("donateCount", 0))
            except Exception:
                pass

        # 7. فحص الحيوانات الأليفة وحالة الدورية (petCtrl)
        pet_ctrl = self.conn.init_data.get("petCtrl", {})
        if isinstance(pet_ctrl, dict):
            pets_dict = pet_ctrl.get("pets", {})
            if isinstance(pets_dict, dict):
                for p_id_str, p_val in pets_dict.items():
                    p_id = int(p_id_str)
                    p_name = KNOWN_PETS.get(p_id, {}).get("name", f"حيوان #{p_id}")
                    ctx.unlocked_pets[p_id] = {
                        "name": p_name,
                        "lv": int(p_val.get("lv", 1)),
                        "step": int(p_val.get("step", 1))
                    }

            patrol_info = pet_ctrl.get("petPatrolInfo", {})
            if isinstance(patrol_info, dict):
                end_time = int(patrol_info.get("endTime", 0))
                active_pet_id = int(patrol_info.get("petID", 0))
                now_ts = int(time.time())
                if end_time > now_ts and active_pet_id > 0:
                    ctx.pet_patrol_status = {
                        "active": True,
                        "pet_id": active_pet_id,
                        "pet_name": KNOWN_PETS.get(active_pet_id, {}).get("name", f"حيوان #{active_pet_id}"),
                        "remain_seconds": end_time - now_ts
                    }

        # 8. فحص جوائز حدث التوسع الإقليمي (Activity 9001373)
        aty_mgr = self.conn.init_data.get("generalAtyMgr", {})
        if isinstance(aty_mgr, dict):
            exp_aty = aty_mgr.get("9001373") or aty_mgr.get(9001373, {})
            if isinstance(exp_aty, dict):
                quests = exp_aty.get("data", {}).get("quests", {})
                if isinstance(quests, dict):
                    ctx.territory_ready_rewards = sum(1 for q in quests.values() if isinstance(q, dict) and int(q.get("status", 0)) == 3)

        # 9. فحص دروع السلام وجرعات الطاقة في الحقيبة (backpackCtrl أو عبر 1004/1 كاحتياط)
        bp_ctrl = self.conn.init_data.get("backpackCtrl", {})
        if isinstance(bp_ctrl, dict) and bp_ctrl:
            ctx.shield_backpack_counts["8h"] = int(bp_ctrl.get("300701", {}).get("count", 0))
            ctx.shield_backpack_counts["24h"] = int(bp_ctrl.get("300702", {}).get("count", 0))
            ctx.shield_backpack_counts["3d"] = int(bp_ctrl.get("300703", {}).get("count", 0))
            for pid in (300401, 300402, 300403):
                ctx.stamina_potions[pid] = int(bp_ctrl.get(str(pid), {}).get("count", 0))

        if sum(ctx.shield_backpack_counts.values()) == 0 or sum(ctx.stamina_potions.values()) == 0:
            try:
                r_bag = await self.conn.query("1004", "1", {}, timeout=6)
                if r_bag and isinstance(r_bag.get("data"), dict):
                    raw_data = r_bag["data"]
                    items = raw_data.get("itemList", raw_data)
                    if isinstance(items, dict):
                        for k, v in items.items():
                            if isinstance(v, dict):
                                iid = str(v.get("id", v.get("itemID", k)))
                                cnt = int(v.get("count", v.get("num", 0)))
                                if iid == "300701": ctx.shield_backpack_counts["8h"] = cnt
                                elif iid == "300702": ctx.shield_backpack_counts["24h"] = cnt
                                elif iid == "300703": ctx.shield_backpack_counts["3d"] = cnt
                                elif iid == "300401": ctx.stamina_potions[300401] = cnt
                                elif iid == "300402": ctx.stamina_potions[300402] = cnt
                                elif iid == "300403": ctx.stamina_potions[300403] = cnt
                    elif isinstance(items, list):
                        for v in items:
                            if isinstance(v, dict):
                                iid = str(v.get("id", v.get("itemID", 0)))
                                cnt = int(v.get("count", v.get("num", 0)))
                                if iid == "300701": ctx.shield_backpack_counts["8h"] = cnt
                                elif iid == "300702": ctx.shield_backpack_counts["24h"] = cnt
                                elif iid == "300703": ctx.shield_backpack_counts["3d"] = cnt
                                elif iid == "300401": ctx.stamina_potions[300401] = cnt
                                elif iid == "300402": ctx.stamina_potions[300402] = cnt
                                elif iid == "300403": ctx.stamina_potions[300403] = cnt
            except Exception:
                pass

        # فحص تكلفة تبديل وشراء الطاقة بالذهب القادم (buyStaminaCtrl)
        bs_ctrl = self.conn.init_data.get("buyStaminaCtrl", {})
        if isinstance(bs_ctrl, dict):
            ctx.stamina_gold_cost = int(bs_ctrl.get("price", 0))
            ctx.stamina_buy_times = int(bs_ctrl.get("buyTimes", 0))
            ctx.stamina_limit_times = int(bs_ctrl.get("limitTimes", 30))

        # فحص حالة درع السلام النشط للقلعة
        try:
            s_task = ShieldTask(self.conn, self.config.get("shield", {}))
            is_active, r_str, _ = s_task.is_shield_active()
            ctx.shield_active = is_active
            ctx.shield_status_str = r_str
        except Exception:
            pass

        # 10. فحص حالة المهارات التلقائية (lordSkillCtrl)
        try:
            sk_task = SkillsTask(self.conn, {"skills": list(SUPPORTED_SKILLS.keys())})
            ctx.skills_status = sk_task.get_skills_status()
        except Exception:
            pass

        # 11. فحص سحوبات وتجنيد الأبطال اليومية (heroEnlistCtrl)
        he_ctrl = self.conn.init_data.get("heroEnlistCtrl", {})
        if isinstance(he_ctrl, dict):
            he_data = he_ctrl.get("heroEnlistData", {})
            if isinstance(he_data, dict):
                now_ts = int(time.time())
                ready_draws = 0
                for tid in ("1", "3", "4"):
                    d_info = he_data.get(tid, {})
                    if isinstance(d_info, dict):
                        left = int(d_info.get("leftTimes", 0))
                        cut = int(d_info.get("canusetime", 0))
                        if left > 0 and (cut <= now_ts or cut == 0):
                            ready_draws += 1
                ctx.hero_draw_ready_count = ready_draws

                # فحص استكشاف جناح الكنز المجاني (الفئة 6)
                pav_info = he_data.get("6", {})
                if isinstance(pav_info, dict):
                    p_left = int(pav_info.get("leftTimes", 0))
                    p_cut = int(pav_info.get("canusetime", 0))
                    ctx.treasure_pavilion_left_times = p_left
                    ctx.treasure_pavilion_ready = (p_left > 0 and (p_cut <= now_ts or p_cut == 0))

        # فحص صقل معمل الحدادة المجاني (runeForgeAgCtrl)
        rf_ctrl = self.conn.init_data.get("runeForgeAgCtrl", {})
        if isinstance(rf_ctrl, dict):
            rf_use = int(rf_ctrl.get("useTimes", 0))
            rf_cd = int(rf_ctrl.get("cdTime", 0))
            rf_left = max(0, 3 - rf_use)
            now_ts = int(time.time())
            ctx.blacksmith_forge_left_times = rf_left
            ctx.blacksmith_forge_ready = (rf_left > 0 and (rf_cd == 0 or (now_ts - rf_cd) >= 300))

        # فحص استكشاف الضريح الإمبراطوري المجاني (pyramidCtrl)
        pyr_ctrl = self.conn.init_data.get("pyramidCtrl")
        p_data = pyr_ctrl.get("data", {}) if isinstance(pyr_ctrl, dict) else {}
        if not isinstance(p_data, dict) or not p_data:
            try:
                resp = await self.conn.query("1045", "1", {}, timeout=6)
                if resp and str(resp.get("err", "-1")) == "0":
                    p_data = resp.get("data", {})
                    self.conn.init_data.setdefault("pyramidCtrl", {})["data"] = p_data
            except Exception:
                pass

        if isinstance(p_data, dict) and p_data:
            award = p_data.get("award", {})
            has_pending = isinstance(award, dict) and bool(award.get("itemid"))
            free_val = int(p_data.get("free", 0))
            has_free = (free_val == 1)
            ctx.imperial_mausoleum_has_award = has_pending
            ctx.imperial_mausoleum_free_throw = has_free
            ctx.imperial_mausoleum_ready = (has_free or has_pending)
            ctx.imperial_mausoleum_copper = int(p_data.get("copper", 0))
            ctx.imperial_mausoleum_dice_count = int(p_data.get("count", 0))

        # فحص صندوق التحالف المجاني (Alliance Treasure - 2015/1)
        try:
            at_task = AllianceTreasureTask(self.conn)
            at_st = await at_task.get_free_status(force_query=True)
            ctx.alliance_treasure_ready = at_st.get("ready", False)
            ctx.alliance_treasure_in_alliance = at_st.get("in_alliance", True)
            ctx.alliance_treasure_free_dig_ready = at_st.get("free_dig_ready", False)
            ctx.alliance_treasure_can_receive = (len(at_st.get("can_receive_list", [])) > 0 or len(at_st.get("can_receive_help_list", [])) > 0)
            ctx.alliance_treasure_is_digging = at_st.get("is_digging", False)
            ctx.alliance_treasure_dig_remain = at_st.get("dig_remain", 0)
            ctx.alliance_treasure_dig_count = at_st.get("dig_count", 0)
            ctx.alliance_treasure_max_dig = at_st.get("max_dig_count", 8)
            ctx.alliance_treasure_left_free_today = at_st.get("left_free_today", 0)
        except Exception as ex_at:
            log.debug(f"تنبيه أثناء استعلام صندوق التحالف في لوحة المعلومات: {ex_at}")

        # فحص الهدية الفاخرة اليومية (Daily Luxury Gift - 3094)
        try:
            dlg_task = DailyLuxuryGiftTask(self.conn)
            dlg_st = dlg_task.get_status_summary()
            ctx.daily_luxury_gift_ready = dlg_st.get("has_rewards", False)
            ctx.daily_luxury_gift_count = dlg_st.get("available_count", 0)
            ctx.daily_luxury_gift_max_day = dlg_st.get("daily_max_day", 0)
        except Exception as ex_dlg:
            log.debug(f"تنبيه أثناء استعلام الهدية الفاخرة: {ex_dlg}")

        # فحص صندوق الـ VIP اليومي المجاني (VIP Daily Gift - 1082)
        try:
            vg_task = VipGiftTask(self.conn)
            vg_st = vg_task.get_vip_status()
            ctx.vip_gift_ready = vg_st.get("free_available", False)
            ctx.vip_lv = vg_st.get("vip_lv", 0)
            ctx.vip_point = vg_st.get("vip_point", 0)
        except Exception as ex_vg:
            log.debug(f"تنبيه أثناء استعلام صندوق الـ VIP: {ex_vg}")

        # 12. فحص حالة قاعة الاستراتيجيات وأبحاث التكتيكات (queueCtrl -> 1257)
        queue_ctrl = self.conn.init_data.get("queueCtrl", {})
        tactical_q = queue_ctrl.get("1257") if isinstance(queue_ctrl, dict) else None
        if tactical_q and isinstance(tactical_q, dict):
            q_data = tactical_q.get("data", {})
            end_time = int(q_data.get("endTime", 0))
            t_mid = int(q_data.get("mid", 0))
            now_ts = int(time.time())
            if end_time > now_ts and t_mid > 0:
                t_info = TACTICS_MAP.get(t_mid, {"name_ar": f"بحث #{t_mid}", "icon": "⏳"})
                ctx.tactics_hall_status = {
                    "active": True,
                    "mid": t_mid,
                    "tactic_name": t_info.get("name_ar", f"بحث #{t_mid}"),
                    "icon": t_info.get("icon", "⏳"),
                    "remain_seconds": end_time - now_ts
                }

        # 13. فحص حالة تعزيزات طاحونة الماء لمباني الموارد (buffCtrl)
        buff_ctrl = self.conn.init_data.get("buffCtrl", [])
        active_wm_count = 0
        now_ts = int(time.time())
        if isinstance(buff_ctrl, list):
            for b in buff_ctrl:
                if isinstance(b, dict):
                    extra = b.get("extra", {})
                    b_begin = int(b.get("beginTime", 0))
                    if isinstance(extra, dict):
                        try:
                            e_bid = int(extra.get("bid", 0))
                            if e_bid in (201, 202, 203, 204) and (now_ts - b_begin) < 86400:
                                active_wm_count += 1
                        except Exception:
                            pass
        ctx.watermill_boosted_count = active_wm_count

        # 14. فحص حالة نافورة الأمنيات الملكية (1018/1)
        try:
            r_fountain = await self.conn.query("1018", "1", {}, timeout=6)
            if r_fountain and str(r_fountain.get("err", "")) == "0":
                f_data = r_fountain.get("data", {})
                free_w = int(f_data.get("multipleTimes", 0)) + int(f_data.get("pornMultipleTimes", 0))
                ctx.fountain_free_wishes = free_w
        except Exception:
            pass

        # 15. فحص حالة ورشة المواد وخامات العتاد (queueCtrl -> 1256 & heroEquipAgCtrl)
        he_ag_ctrl = self.conn.init_data.get("heroEquipAgCtrl", {})
        waiting_q = he_ag_ctrl.get("queues", []) if isinstance(he_ag_ctrl, dict) else []
        workshop_q = queue_ctrl.get("1256") if isinstance(queue_ctrl, dict) else None

        active_mat_name = ""
        active_mat_icon = "🔨"
        occupied_slots = len(waiting_q) if isinstance(waiting_q, list) else 0
        remain_s = 0

        if workshop_q and isinstance(workshop_q, dict):
            q_data = workshop_q.get("data", {})
            end_time = int(q_data.get("endTime", 0))
            w_mid = int(q_data.get("mid", 0))
            if end_time > now_ts:
                occupied_slots += 1
                remain_s = end_time - now_ts
                m_meta = WORKSHOP_MATERIALS_MAP.get(w_mid, {"name_ar": f"خامة #{w_mid}", "icon": "📦"})
                active_mat_name = m_meta["name_ar"]
                active_mat_icon = m_meta["icon"]

        ctx.workshop_status = {
            "occupied": occupied_slots,
            "capacity": 5,
            "active_name": active_mat_name,
            "active_icon": active_mat_icon,
            "remain_seconds": remain_s
        }

        # 16. فحص حالة القافلة وحراسة الكنز (3139/6)
        try:
            r_caravan = await self.conn.query("3139", "6", {}, timeout=6)
            if r_caravan and isinstance(r_caravan.get("data"), dict):
                my_c = r_caravan["data"].get("myCarriage")
                if my_c and isinstance(my_c, dict):
                    bt = my_c.get("buildTimes", [])
                    if bt and isinstance(bt, list):
                        c_end = int(bt[-1].get("endtime", 0))
                        if c_end > now_ts:
                            ctx.caravan_status = {
                                "marching": True,
                                "cargo_amount": sum(my_c.get("curCargo", {}).values()) if isinstance(my_c.get("curCargo"), dict) else 5000,
                                "remain_seconds": c_end - now_ts
                            }
        except Exception:
            pass

        # 17. فحص كشك التاجر المتجول (1024/1)
        try:
            r_merchant = await self.conn.query("1024", "1", {}, timeout=6)
            if r_merchant and str(r_merchant.get("err", "0")) == "0":
                m_data = r_merchant.get("data", {})
                if isinstance(m_data, dict):
                    m_open = bool(m_data.get("isOpen", True))
                    m_items = m_data.get("shopItemArray", [])
                    res_items = 0
                    if isinstance(m_items, list):
                        for it in m_items:
                            if isinstance(it, dict) and int(it.get("pricetype", 0)) in (1002, 1003, 1004, 1005):
                                res_items += 1
                    ctx.merchant_status = {
                        "is_open": m_open,
                        "items_count": len(m_items) if isinstance(m_items, list) else 0,
                        "resource_items_count": res_items
                    }
        except Exception:
            pass

        # 18. فحص حالة الميناء العسكري ومتجر الجزيرة (PveBattleCtrl)
        pve_ctrl = self.conn.init_data.get("PveBattleCtrl", {})
        if isinstance(pve_ctrl, dict):
            pts = int(pve_ctrl.get("points", 0))
            cur_lvl = int(pve_ctrl.get("nCurLevelId", 0))
            s_tasks = pve_ctrl.get("tasks", {})
            ready_c = 0
            running_c = 0
            claimable_c = 0
            now_t = time.time()
            for tid, meta in DELEGATE_TASKS_CONFIG.items():
                if cur_lvl >= meta["unlock_level"]:
                    s_info = s_tasks.get(str(tid)) or s_tasks.get(tid)
                    if s_info:
                        st = int(s_info.get("state", 0))
                        st_time = float(s_info.get("startTime", 0))
                        dur = meta["duration"]
                        if st == 1:
                            if (now_t - st_time) < dur:
                                running_c += 1
                            else:
                                claimable_c += 1
                    else:
                        ready_c += 1
            ctx.port_delegate_status = {
                "ready_tasks": ready_c,
                "running_tasks": running_c,
                "claimable_tasks": claimable_c,
                "island_points": pts
            }

        # 19. فحص حالة دار الادخار وبنك التوفير (savingsBankAgCtrl)
        sb_ctrl = self.conn.init_data.get("savingsBankAgCtrl", {})
        if isinstance(sb_ctrl, dict):
            slip = sb_ctrl.get("slip", {})
            if isinstance(slip, dict) and slip.get("startTime"):
                s_days = int(slip.get("day", 7))
                s_start = int(slip.get("startTime", 0))
                s_deposit = int(slip.get("deposit", 0))
                s_end = s_start + (s_days * 86400)
                now_s = int(time.time())
                rem = max(0, s_end - now_s)
                ctx.savings_bank_status = {
                    "has_slip": True,
                    "deposit": s_deposit,
                    "days": s_days,
                    "remain_seconds": rem,
                    "is_claimable": (rem <= 0)
                }

        # 20. فحص مهام المجد والنشاط اليومي وصناديق الجوائز (meritoriousTaskCtrl)
        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        if isinstance(merit, dict) and merit:
            ctx.merit_level = int(merit.get("meritLv", 0))
            ctx.merit_exp = int(merit.get("meritExp", 0))
            daily_pts = int(merit.get("dailyPoint", 0))
            ctx.merit_daily_points = daily_pts

            # فحص الصناديق اليومية
            claimed_raw = merit.get("dailyBoxRwd", {})
            claimed_box_ids = set()
            if isinstance(claimed_raw, dict):
                claimed_box_ids = {int(k) for k in claimed_raw.keys()}
            elif isinstance(claimed_raw, list):
                claimed_box_ids = {int(x) for x in claimed_raw if str(x).isdigit()}
            ctx.merit_chests_claimed = sorted(list(claimed_box_ids))

            ready_boxes = []
            next_goal = 0
            next_remain = 0
            for box_id, goal in DAILY_MERIT_CHEST_GOALS:
                if box_id in claimed_box_ids:
                    continue
                if daily_pts >= goal:
                    ready_boxes.append((box_id, goal))
                elif next_goal == 0:
                    next_goal = goal
                    next_remain = max(0, goal - daily_pts)

            ctx.merit_chests_ready = ready_boxes
            ctx.merit_next_chest_goal = next_goal
            ctx.merit_next_chest_remain = next_remain

            # فحص المهام اليومية (daily_task و taskData)
            daily_tasks = merit.get("daily_task", {})
            task_data = merit.get("taskData", {})
            if isinstance(daily_tasks, dict) and isinstance(task_data, dict):
                ctx.merit_tasks_total = len(daily_tasks)
                c_claimed = 0
                c_ready = 0
                c_in_progress = 0
                details_list = []
                for qid_str in sorted(daily_tasks.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                    qid = int(qid_str)
                    tinfo = task_data.get(str(qid)) or task_data.get(qid)
                    if not isinstance(tinfo, dict):
                        continue
                    st = int(tinfo.get("status", 2))
                    c_num = int(tinfo.get("cNum", 0))
                    l_num = int(tinfo.get("lNum", 0))
                    meta = DAILY_MERIT_TASK_NAMES.get(qid, {"name": f"مهمة #{qid}", "icon": "🎖️"})

                    if st == 5:
                        c_claimed += 1
                        st_type = "claimed"
                    elif st == 4 or (l_num > 0 and c_num >= l_num):
                        c_ready += 1
                        st_type = "ready"
                    else:
                        c_in_progress += 1
                        st_type = "in_progress"

                    details_list.append({
                        "id": qid,
                        "name": meta["name"],
                        "icon": meta["icon"],
                        "status_type": st_type,
                        "c_num": c_num,
                        "l_num": l_num,
                        "remaining": max(0, l_num - c_num) if l_num > 0 else 0
                    })
                ctx.merit_tasks_claimed = c_claimed
                ctx.merit_tasks_ready = c_ready
                ctx.merit_tasks_in_progress = c_in_progress
                ctx.merit_tasks_details = details_list

        # عرض ملخص الاستعلام الشامل بشكل منسق وجذاب
        self._print_account_dashboard()
        return ctx

    def _print_account_dashboard(self):
        """طباعة تقرير شامل وواضح لحالة الحساب قبل بدء تنفيذ المهام."""
        # في Thread Pool mode: لا طباعة — تكلفة I/O عالية بدون فائدة
        if self._log_callback:
            return
        ctx = self.context
        print("\n" + "═" * 72)
        print(f"🏰 لوحة معلومات الحساب: {ctx.lord_name} ({self.email})")
        print("═" * 72)
        print(f"👑 اللورد: {ctx.lord_name} | المستوى: {ctx.lord_level} | المملكة: #{ctx.kingdom_id}")
        print(f"⚡ القوة القتالية (Power): {ctx.total_power:,} | 🪙 الذهب: {ctx.gold:,}")
        print(f"🏰 مستوى القلعة: {ctx.castle_level} | 🧱 مستوى الأسوار: {ctx.walls_level}")
        print("─" * 72)
        print("⚔️ جاهزية الثكنات العسكرية:")
        icons = {"infantry": "🛡️", "cavalry": "🐎", "archers": "🏹", "chariots": "🚜"}
        for b_key, b_val in ctx.barracks_info.items():
            status_text = "⏳ قيد التدريب حالياً" if b_val["training"] else "✅ شاغرة وجاهزة للتدريب"
            print(f"   • {icons.get(b_key, '')} {b_val['name']}: المستوى {b_val['level']} ➔ {status_text}")
        print("─" * 72)
        print(f"🌾 مزارع ومناجم المدينة: {ctx.city_farms_count} مبنى (🌾 {ctx.city_farms_breakdown['food']} قمح | 🪵 {ctx.city_farms_breakdown['wood']} خشب | ⛏️ {ctx.city_farms_breakdown['iron']} حديد | 🪙 {ctx.city_farms_breakdown['silver']} فضة)")
        print("─" * 72)
        if ctx.research_status["is_busy"]:
            rem_m = ctx.research_status["remain_seconds"] // 60
            print(f"🔬 أبحاث الأكاديمية: ⏳ قيد البحث حالياً ({ctx.research_status['tech_name']} | متبقي {rem_m} دقيقة)")
        else:
            print("🔬 أبحاث الأكاديمية: ✅ طابور الأبحاث شاغر وجاهز لإجراء بحث جديد")
        print("─" * 72)
        if ctx.alliance_id > 0:
            tag_str = f"[{ctx.alliance_tag}] " if ctx.alliance_tag else ""
            print(f"🤝 التحالف: {tag_str}{ctx.alliance_name} (ID: {ctx.alliance_id}) | رصيد التبرع: {ctx.alliance_available_donations}/20 مجاني")
        else:
            print("🤝 التحالف: ⚠️ الحساب غير منضم إلى أي تحالف حالياً")
        print("─" * 72)
        print(f"🚢 سفن الميناء المتاحة للإرسال: {ctx.available_ships} سفينة")
        print("─" * 72)
        print("🐾 الحيوانات الأليفة في الحساب:")
        if ctx.unlocked_pets:
            pets_str = " | ".join([f"{p['name']} (مستوى {p['lv']})" for p in ctx.unlocked_pets.values()])
            print(f"   • الحيوانات المتاحة: {pets_str}")
        else:
            print("   • الحيوانات المتاحة: 🦌 الغزال (افتراضي)")
        if ctx.pet_patrol_status["active"]:
            rem_m = ctx.pet_patrol_status["remain_seconds"] // 60
            print(f"   • حالة الدورية: ⏳ {ctx.pet_patrol_status['pet_name']} في دورية حالياً (متبقي {rem_m} دقيقة)")
        else:
            print("   • حالة الدورية: ✅ شاغرة وجاهزة لبدء دورية جديدة")
        print("─" * 72)
        if ctx.territory_ready_rewards > 0:
            print(f"🚩 جوائز التوسع الإقليمي: 🎁 {ctx.territory_ready_rewards} مكافأة جاهزة للاستلام فوراً!")
        else:
            print("🚩 جوائز التوسع الإقليمي: لا توجد مكافآت جديدة جاهزة للاستلام")
        print("─" * 72)
        s_8h = ctx.shield_backpack_counts.get("8h", 0)
        s_24h = ctx.shield_backpack_counts.get("24h", 0)
        s_3d = ctx.shield_backpack_counts.get("3d", 0)
        total_shields = s_8h + s_24h + s_3d
        shield_st = "🛡️ محمي بدرع سلام نشط" if ctx.shield_active else "⚠️ غير محمي (مكشوف بدون درع)"
        print(f"🛡️ دروع السلام في الحقيبة: {total_shields} درع (🛡️ {s_8h} درع 8س | 🛡️ {s_24h} درع 24س | 🛡️ {s_3d} درع 3أيام) | الحالة: {shield_st}")
        print("─" * 72)
        p10 = ctx.stamina_potions.get(300401, 0)
        p50 = ctx.stamina_potions.get(300402, 0)
        p100 = ctx.stamina_potions.get(300403, 0)
        total_pots = p10 + p50 + p100
        gold_cost_str = f" | 🪙 التبديل بالذهب القادم: {ctx.stamina_gold_cost} ذهب (تم {ctx.stamina_buy_times}/{ctx.stamina_limit_times} اليوم)" if ctx.stamina_gold_cost > 0 else ""
        print(f"⚡ جرعات الطاقة في الحقيبة: {total_pots} جرعة (🧪 {p10} جرعة +10 | 🧪 {p50} جرعة +50 | 🧪 {p100} جرعة +100){gold_cost_str}")
        print("─" * 72)
        print("🎯 حالة المهارات التلقائية (Skills):")
        if ctx.skills_status:
            for sk in ctx.skills_status:
                if sk["is_ready"]:
                    st_str = "✅ جاهزة للتفعيل فوراً"
                elif sk["is_unlocked"]:
                    st_str = f"⏳ في فترة تبريد (متبقي {sk['remain_formatted']})"
                else:
                    st_str = "🔒 غير مفتوحة في القلعة"
                print(f"   • {sk['icon']} {sk['name']}: {st_str}")
        else:
            print("   • لم يتم العثور على بيانات المهارات")
        print("─" * 72)
        if ctx.hero_draw_ready_count > 0:
            print(f"🦸 سحوبات الأبطال اليومية: 🎁 {ctx.hero_draw_ready_count} سحوبات مجانية جاهزة للسحب فوراً!")
        else:
            print("🦸 سحوبات الأبطال اليومية: لا توجد سحبات مجانية جاهزة حالياً")
        print("─" * 72)
        if ctx.treasure_pavilion_ready:
            print(f"💎 جناح الكنز (Treasure Pavilion): 🎁 استكشاف مجاني جاهز فوراً! (متبقي {ctx.treasure_pavilion_left_times} اليوم)")
        elif ctx.treasure_pavilion_left_times > 0:
            print(f"💎 جناح الكنز (Treasure Pavilion): ⏳ قيد التهدئة الفاصلة (متبقي {ctx.treasure_pavilion_left_times} سحبة اليوم)")
        else:
            print("💎 جناح الكنز (Treasure Pavilion): لا توجد سحبات مجانية متاحة اليوم")
        print("─" * 72)
        if ctx.blacksmith_forge_ready:
            print(f"🔨 معمل الحدادة (Blacksmith Forge): 🎁 صقل مجاني جاهز فوراً! (متبقي {ctx.blacksmith_forge_left_times} اليوم)")
        elif ctx.blacksmith_forge_left_times > 0:
            print(f"🔨 معمل الحدادة (Blacksmith Forge): ⏳ قيد التهدئة الفاصلة (متبقي {ctx.blacksmith_forge_left_times} صقل اليوم)")
        else:
            print("🔨 معمل الحدادة (Blacksmith Forge): لا يوجد صقل مجاني متاح اليوم")
        print("─" * 72)
        if ctx.imperial_mausoleum_has_award:
            print(f"🏛️ الضريح الإمبراطوري (Imperial Mausoleum): 🎁 جائزة معلقة أو نرد إضافي جاهز للاستلام/الرمي! (🪙 عملات النحاس: {ctx.imperial_mausoleum_copper:,} | 🎲 رصيد النرد: {ctx.imperial_mausoleum_dice_count})")
        elif ctx.imperial_mausoleum_free_throw:
            print(f"🏛️ الضريح الإمبراطوري (Imperial Mausoleum): 🎁 رمي مجاني جاهز فوراً! (🪙 عملات النحاس: {ctx.imperial_mausoleum_copper:,} | 🎲 رصيد النرد: {ctx.imperial_mausoleum_dice_count})")
        else:
            print(f"🏛️ الضريح الإمبراطوري (Imperial Mausoleum): لا توجد رميات مجانية متاحة اليوم (🪙 عملات النحاس: {ctx.imperial_mausoleum_copper:,} | 🎲 رصيد النرد: {ctx.imperial_mausoleum_dice_count})")
        print("─" * 72)
        if not ctx.alliance_treasure_in_alliance:
            print("📦 صندوق التحالف (Alliance Treasure): ⚠️ غير متاح (الحساب غير منضم إلى أي تحالف)")
        elif ctx.alliance_treasure_can_receive:
            print(f"📦 صندوق التحالف (Alliance Treasure): 🎁 صناديق مكتملة أو جوائز مساعدة جاهزة للاستلام فوراً! (تم {ctx.alliance_treasure_dig_count}/{ctx.alliance_treasure_max_dig} اليوم)")
        elif ctx.alliance_treasure_free_dig_ready:
            print(f"📦 صندوق التحالف (Alliance Treasure): 🎁 حفر صندوق مجاني جاهز فوراً! (متبقي {ctx.alliance_treasure_left_free_today}/{ctx.alliance_treasure_max_dig} اليوم)")
        elif ctx.alliance_treasure_is_digging:
            rem_m = max(1, ctx.alliance_treasure_dig_remain // 60)
            print(f"📦 صندوق التحالف (Alliance Treasure): ⏳ قيد الحفر حالياً (متبقي {rem_m} دقيقة | تم {ctx.alliance_treasure_dig_count}/{ctx.alliance_treasure_max_dig} اليوم)")
        elif ctx.alliance_treasure_left_free_today <= 0:
            print(f"📦 صندوق التحالف (Alliance Treasure): ✅ تم استهلاك كافة المحاولات اليوم ({ctx.alliance_treasure_max_dig}/{ctx.alliance_treasure_max_dig})")
        else:
            print(f"📦 صندوق التحالف (Alliance Treasure): ⏳ في فترة انتظار فاصلة (تم {ctx.alliance_treasure_dig_count}/{ctx.alliance_treasure_max_dig} اليوم)")
        print("─" * 72)
        if ctx.daily_luxury_gift_count > 0:
            print(f"🎁 الهدية الفاخرة اليومية (Daily Luxury Gift): 🎁 {ctx.daily_luxury_gift_count} هدية فاخرة جاهزة للاستلام فوراً! (حتى اليوم {ctx.daily_luxury_gift_max_day})")
        elif ctx.daily_luxury_gift_max_day > 0:
            print(f"🎁 الهدية الفاخرة اليومية (Daily Luxury Gift): ✅ تم استلام كافة الهدايا المتاحة حتى اليوم {ctx.daily_luxury_gift_max_day}")
        else:
            print("🎁 الهدية الفاخرة اليومية (Daily Luxury Gift): لا توجد هدايا فاخرة متاحة حالياً")
        print("─" * 72)
        if ctx.vip_gift_ready:
            print(f"👑 صندوق الـ VIP اليومي (VIP Daily Gift): 🎁 صندوق مجاني جاهز للاستلام فوراً! (VIP مستوى {ctx.vip_lv} | نقاط: {ctx.vip_point:,})")
        else:
            print(f"👑 صندوق الـ VIP اليومي (VIP Daily Gift): ✅ تم استلام الصندوق اليوم مسبقاً (VIP مستوى {ctx.vip_lv} | نقاط: {ctx.vip_point:,})")
        print("─" * 72)
        if ctx.tactics_hall_status["active"]:
            rem_m = ctx.tactics_hall_status["remain_seconds"] // 60
            print(f"🏛️ قاعة الاستراتيجيات: ⏳ قيد البحث حالياً ({ctx.tactics_hall_status['icon']} {ctx.tactics_hall_status['tactic_name']} | متبقي {rem_m} دقيقة)")
        else:
            print("🏛️ قاعة الاستراتيجيات: ✅ طابور التكتيكات شاغر وجاهز لتطوير بحث جديد")
        print("─" * 72)
        if ctx.city_farms_count > 0:
            print(f"💧 طاحونة الماء (تعزيز الإنتاج): ⚡ {ctx.watermill_boosted_count}/{ctx.city_farms_count} مبنى موارد معزز حالياً")
        else:
            print("💧 طاحونة الماء (تعزيز الإنتاج): لم يتم رصد مباني موارد بالمدينة")
        print("─" * 72)
        if ctx.fountain_free_wishes > 0:
            print(f"⛲ نافورة الأمنيات الملكية: 🎁 {ctx.fountain_free_wishes} أمنية مجانية متاحة اليوم!")
        else:
            print("⛲ نافورة الأمنيات الملكية: لا توجد أمنيات مجانية متاحة حالياً")
        print("─" * 72)
        if ctx.workshop_status["active_name"]:
            rem_m = ctx.workshop_status["remain_seconds"] // 60
            print(f"🔨 ورشة المواد (خامات العتاد): ⏳ {ctx.workshop_status['occupied']}/5 قيد الإنتاج ({ctx.workshop_status['active_icon']} {ctx.workshop_status['active_name']} | متبقي {rem_m} دقيقة)")
        elif ctx.workshop_status["occupied"] > 0:
            print(f"🔨 ورشة المواد (خامات العتاد): ⏳ {ctx.workshop_status['occupied']}/5 في خط الإنتاج")
        else:
            print("🔨 ورشة المواد (خامات العتاد): ✅ خط الإنتاج شاغر بالكامل (0/5) وجاهز لتصنيع الخامات")
        print("─" * 72)
        if ctx.caravan_status["marching"]:
            rem_m = ctx.caravan_status["remain_seconds"] // 60
            print(f"🐪 القافلة وحراسة الكنز: ⏳ تسير في الطريق حالياً (حمولة: {ctx.caravan_status['cargo_amount']:,} | متبقي للوصول: {rem_m} دقيقة)")
        else:
            print("🐪 القافلة وحراسة الكنز: 🚀 جاهزة للإرسال أو استلام الجوائز ومعالجة أحداث الطريق")
        print("─" * 72)
        if ctx.merchant_status["is_open"]:
            print(f"🛒 التاجر المتجول: 🏪 الكشك مفتوح ({ctx.merchant_status['items_count']} سلع معروضة | {ctx.merchant_status['resource_items_count']} متاحة بالموارد)")
        else:
            print("🛒 التاجر المتجول: 🚪 الكشك مغلق حالياً")
        print("─" * 72)
        pd = ctx.port_delegate_status
        print(f"⚓ الميناء العسكري وتفويض السفن: 🟢 {pd['ready_tasks']} جاهزة للتعيين | ⏳ {pd['running_tasks']} جارية | 🎁 {pd['claimable_tasks']} للاستلام | 💰 نقاط الجزيرة: {pd['island_points']:,}")
        print("─" * 72)
        sb = ctx.savings_bank_status
        if sb["has_slip"]:
            if sb["is_claimable"]:
                print(f"🏦 دار الادخار (بنك التوفير): 🎁 الوديعة مكتملة الاستحقاق ({sb['deposit']:,} ذهب لمدة {sb['days']} يوم) — جاهزة لسحب الأرباح فوراً!")
            else:
                rem_d = sb["remain_seconds"] // 86400
                rem_h = (sb["remain_seconds"] % 86400) // 3600
                print(f"🏦 دار الادخار (بنك التوفير): ⏳ قيد الاستثمار ({sb['deposit']:,} ذهب لمدة {sb['days']} يوم | متبقي: {rem_d} يوم و {rem_h} ساعة)")
        else:
            print("🏦 دار الادخار (بنك التوفير): 🟢 لا توجد وديعة نشطة — جاهز لإيداع الذهب واستثماره")
        print("─" * 72)
        bs = ctx.building_status
        if bs["active_queues"] > 0:
            q_desc = []
            for q in bs["queues_info"]:
                b_name = "🏰 القلعة" if q['bid'] == '101' else ("🧱 الأسوار" if q['bid'] == '102' else BUILDING_INFO.get(q['bid'], {}).get("name", f"مبنى #{q['bid']}"))
                rem_m = int(q['remain'] // 60)
                q_desc.append(f"{b_name} (مستوى {q['lv']} | ⏳ متبقي {rem_m} د)")
            print(f"🏗️ طوابير البناء: ⏳ {bs['active_queues']}/2 قيد العمل ({' | '.join(q_desc)})")
        else:
            print("🏗️ طوابير البناء: 🟢 متاحة بالكامل (0/2) | جاهزة لبدء ترقية جديدة فوراً")
        print("─" * 72)
        fs = ctx.fortress_status
        if fs["level"] > 0:
            if fs["is_training"]:
                rem_m = fs["remain_seconds"] // 60
                print(f"🏰 حصن الحرب (فخاخ السور): ⏳ قيد التدريب (مستوى {fs['level']} | فخاخ السور: {fs['standing_traps']:,}/{fs['wall_capacity']:,} | متبقي {rem_m} دقيقة)")
            else:
                print(f"🏰 حصن الحرب (فخاخ السور): 🟢 متاح للتدريب (مستوى {fs['level']} | فخاخ السور: {fs['standing_traps']:,}/{fs['wall_capacity']:,})")
        else:
            print("🏰 حصن الحرب (فخاخ السور): ⚠️ مبنى حصن الحرب غير مشيد في القلعة")
        if ctx.merit_level > 0 or ctx.merit_daily_points > 0:
            print("─" * 72)
            claimed_str = f"{len(ctx.merit_chests_claimed)}/6 مستلمة"
            if ctx.merit_chests_ready:
                ready_boxes_desc = ", ".join(f"صندوق {g}ن" for _, g in ctx.merit_chests_ready)
                ready_str = f"🎁 {len(ctx.merit_chests_ready)} صندوق جاهز للاستلام! ({ready_boxes_desc})"
            else:
                ready_str = "0 جاهز للاستلام"
            if ctx.merit_next_chest_goal > 0:
                next_str = f"⏳ القادم عند {ctx.merit_next_chest_goal} نقطة (متبقي {ctx.merit_next_chest_remain} نقطة)"
            else:
                next_str = "🎉 تم فتح جميع صناديق اليوم بالكامل"
            print(f"🎖️ مهام المجد والنشاط اليومي (Daily Glory & Prestige):")
            print(f"   • 👑 مستوى المجد: {ctx.merit_level} | نقاط المجد: {ctx.merit_exp:,}")
            print(f"   • ⚡ نقاط النشاط اليومي الحالية: {ctx.merit_daily_points} نقطة")
            print(f"   • 🎁 صناديق النشاط اليومي (6 صناديق): {claimed_str} | {ready_str} | {next_str}")
            print(f"   • 📋 إحصائيات المهام اليومية ({ctx.merit_tasks_total} مهمة): 🎁 {ctx.merit_tasks_ready} جاهزة للاستلام | ⏳ {ctx.merit_tasks_in_progress} قيد الإنجاز | ✅ {ctx.merit_tasks_claimed} مستلمة")
            ready_tasks = [t for t in ctx.merit_tasks_details if t["status_type"] == "ready"]
            if ready_tasks:
                print(f"   • 🎁 أبرز المهام المكتملة الجاهزة للاستلام فوراً ({len(ready_tasks)} مهمة):")
                for t in ready_tasks[:7]:
                    print(f"      - {t['icon']} {t['name']}: مكتملة ({t['c_num']:,}/{t['l_num']:,}) ✅")
                if len(ready_tasks) > 7:
                    print(f"      - ... و {len(ready_tasks) - 7} مهمة أخرى جاهزة")
            started_tasks = [t for t in ctx.merit_tasks_details if t["status_type"] == "in_progress" and t["c_num"] > 0]
            unstarted_tasks = [t for t in ctx.merit_tasks_details if t["status_type"] == "in_progress" and t["c_num"] == 0]
            if started_tasks:
                print(f"   • ⏳ المهام قيد الإنجاز حالياً ({len(started_tasks)} مهمة):")
                for t in started_tasks[:6]:
                    print(f"      - {t['icon']} {t['name']}: {t['c_num']:,}/{t['l_num']:,} (متبقي {t['remaining']:,})")
            elif unstarted_tasks:
                print(f"   • 📌 نماذج من المهام غير المنجزة اليوم:")
                for t in unstarted_tasks[:4]:
                    print(f"      - {t['icon']} {t['name']} (مطلوب {t['l_num']:,})")
        print("═" * 72 + "\n")


    # ════════════════════════════════════════════════════════════════════════════════════════
    # 🌟🌟🌟 [منطقة قائمة المهام الرئيسية — TASK EXECUTION PIPELINE] 🌟🌟🌟
    # ════════════════════════════════════════════════════════════════════════════════════════
    # هنا يمكنك التدخل والتعديل بحرية وسهولة تامة:
    #   1. تغيير الترتيب: قدم أو أخر أي سطر في القائمة أدناه لتغيير تسلسل التنفيذ فوراً.
    #   2. تعطيل مهمة: ضع علامة # قبل السطر لتعطيلها بالكامل.
    #   3. إضافة مهمة جديدة: أضف سطراً جديداً: ("اسم المهمة", self.step_X_...)
    # ════════════════════════════════════════════════════════════════════════════════════════

    async def _wait_for_stop_signal(self) -> None:
        """مراقب غير متزامن فائق السرعة يستيقظ فوراً عند طلب إيقاف البوت من خارج الـ Thread."""
        while not self._stop_event.is_set():
            await asyncio.sleep(0.25)

    async def execute_task_pipeline(self) -> Dict[str, Any]:
        """تنفيذ سلسلة المهام بالترتيب المحدد وفق الجدول الزمني مع استئناف ذكي عند انقطاع الاتصال ودعم الإيقاف الفوري اللحظي."""
        results = {}
        now = datetime.now()  # لقطة واحدة للوقت تُستخدم في كل فحوصات الجدول بالدورة

        # 📋👇👇 قائمة تسلسل المهام: (الاسم، الدالة، مفتاح_الجدولة) — رتبها أو عدلها كما تشاء 👇👇📋
        # ⚠️ مفتاح_الجدولة يجب أن يطابق مفتاح المهمة في DEFAULT_FIREBASE_USER_CONFIG
        pipeline: List[Tuple[str, Callable, str]] = [
            ("🌾 حصد مزارع المدينة (City Harvest)",              self.step_1_city_harvest_task,        "city_harvest"),
            ("🔬 أبحاث الأكاديمية والعلوم (Academy Research)",   self.step_2_research_task,             "research"),
            ("🤝 مهام وتبرعات التحالف (Alliance Task)",          self.step_3_alliance_task,             "alliance"),
            ("🚢 مهمة الميناء (Port Task)",                     self.step_4_port_task,                 "port"),
            ("⚔️ مهمة تدريب الجنود (Train Troops)",             self.step_5_train_task,                "train"),
            ("🐾 مهمة دورية الحيوان الأليف (Pet Patrol)",        self.step_6_pet_patrol_task,           "pet_patrol"),
            ("🚩 جوائز التوسع الإقليمي (Territory Expansion)",   self.step_7_territory_expansion_task,  "territory_expansion"),
            ("🛡️ درع السلام وحماية القلعة (Peace Shield)",        self.step_8_shield_task,               "shield"),
            ("⚡ استخدام وشراء الطاقة (Stamina Task)",           self.step_9_stamina_task,              "stamina"),
            ("🎯 تفعيل المهارات التلقائية (Skills Task)",        self.step_10_skills_task,              "skills"),
            ("🦸 تجنيد الأبطال وسحب الصناديق (Hero Draw)",       self.step_11_hero_draw_task,           "hero_draw"),
            ("💎 استكشاف جناح الكنز (Treasure Pavilion)",       self.step_11b_treasure_pavilion_task,  "treasure_pavilion"),
            ("🔨 صقل معمل الحدادة (Blacksmith Forge)",          self.step_11c_blacksmith_forge_task,   "blacksmith_forge"),
            ("🏛️ الضريح الإمبراطوري (Imperial Mausoleum)",     self.step_11d_imperial_mausoleum_task, "imperial_mausoleum"),
            ("📦 صندوق التحالف (Alliance Treasure)",            self.step_11e_alliance_treasure_task, "alliance_treasure"),
            ("🎁 الهدية الفاخرة اليومية (Daily Luxury Gift)",    self.step_11f_daily_luxury_gift_task, "daily_luxury_gift"),
            ("👑 صندوق الـ VIP اليومي (VIP Daily Gift)",        self.step_11g_vip_gift_task,          "vip_gift"),
            ("🏛️ قاعة الاستراتيجيات (Tactics Hall)",             self.step_12_tactics_hall_task,        "tactics_hall"),
            ("💧 طاحونة الماء (Watermill Boost)",                self.step_13_watermill_task,           "watermill"),
            ("⛲ نافورة الأمنيات (Trevi Fountain)",              self.step_14_fountain_task,            "fountain"),
            ("🔨 ورشة المواد (Material Workshop)",               self.step_15_material_workshop_task,   "material_workshop"),
            ("🐪 القافلة وحراسة الكنز (Caravan Task)",           self.step_16_caravan_task,             "caravan"),
            ("⚓ الميناء العسكري (Port Delegate)",               self.step_18_port_delegate_task,       "port_delegate"),
            ("🏦 دار الادخار (Savings Bank)",                   self.step_19_savings_bank_task,        "savings_bank"),
            ("🏗️ ترقية المباني (Building Upgrade)",             self.step_20_building_task,            "building"),
            ("🎖️ مهام الهيبة اليومية (Prestige Quests)",        self.step_22_prestige_task,            "prestige"),
            ("🎁 استلام صناديق الهيبة (Prestige Boxes)",         self.step_22c_prestige_box_task,       "prestige_box"),
            ("🏛️ كنز طروادة (Troy Treasure)",                  self.step_22d_troy_treasure_task,      "troy_treasure"),
            ("🏥 معالجة الجنود بالمشفى (Hospital Cure)",        self.step_22b_hospital_task,           "hospital"),
            ("🎖️ منسق الفيالق والمسيرات (March Orchestrator)", self.step_23_march_manager_task,     "march_manager"),
            # ──────────────────────────────────────────────────────────────────────────────
            # لإضافة مهمة جديدة أضف سطراً: ("📌 اسم المهمة", self.step_N_..., "config_key")
            # ──────────────────────────────────────────────────────────────────────────────
        ]

        step_idx = 0
        while step_idx < len(pipeline):
            # 0. الفحص الفوري المسبق: هل طُلب إيقاف البوت؟
            if self._stop_event.is_set():
                log.info(f"🛑 [إيقاف فوري] تم رصد طلب الإيقاف — إنهاء سلسلة المهام فوراً للحساب {self.email}.")
                break

            step_name, step_func, task_key = pipeline[step_idx]

            # 1. التحقق من سلامة الاتصال قبل بدء المهمة
            if not self.is_connection_alive():
                if self._stop_event.is_set():
                    break
                kick_reason = self.get_disconnect_reason()
                log.warning(f"⚠️ تم رصد انقطاع الاتصال قبل بدء المهمة [{step_name}] (السبب: {kick_reason})")
                reconnected = await self.wait_and_reconnect(kick_reason)
                if not reconnected:
                    log.error(f"❌ تعذر استعادة الاتصال بعد استنفاد محاولات الدخول. إيقاف السلسلة عند: {step_name}")
                    results[step_name] = {"success": False, "error": "انقطاع الاتصال وتعذر إعادة الدخول"}
                    break

            # فحص إضافي بعد إعادة الاتصال إن حدثت
            if self._stop_event.is_set():
                break

            clean_step_name = step_name.split('(')[0].strip()
            self._update_bot_conn_state("connected", f"جاري تنفيذ: {clean_step_name}")

            if not self._log_callback:
                print("\n" + "─" * 65)
                print(f"▶️ بدء تنفيذ: {step_name}")
                print("─" * 65)

            step_interrupted = False
            step_task = asyncio.create_task(step_func())
            disconnect_waiter = asyncio.create_task(self._disconnected_event.wait())
            stop_waiter = asyncio.create_task(self._wait_for_stop_signal())

            # تحديد مهلة الأمان للمهمة: المهام العادية 300ث (5د)، ومهمة منسق الفيالق تستمر حسب مدتها (افتراضياً 20د)
            task_timeout = 300
            if task_key == "march_manager":
                mm_dur = float(self.config.get("march_manager", {}).get("duration_minutes", 20))
                task_timeout = max(300, int((mm_dur * 60) + 180))

            done, pending = await asyncio.wait(
                [step_task, disconnect_waiter, stop_waiter],
                timeout=task_timeout,
                return_when=asyncio.FIRST_COMPLETED
            )

            # ── التحقق اللحظي الأول: هل تم طلب إيقاف البوت أثناء عمل المهمة؟ ──
            if stop_waiter in done or self._stop_event.is_set():
                log.info(f"🛑 [إيقاف فوري ولحظي] تم استلام أمر إيقاف البوت أثناء تنفيذ [{step_name}] — إلغاء المهمة وقطع الاتصال والخروج فوراً.")
                for p_task in pending:
                    p_task.cancel()
                    try:
                        await p_task
                    except (asyncio.CancelledError, Exception):
                        pass
                results[step_name] = {"stopped": True, "message": "تم إيقاف البوت بواسطة المستخدم"}
                if self.conn:
                    try:
                        await self.conn.close()
                    except Exception:
                        pass
                break

            # إلغاء مراقب الإيقاف طالما انتهت الخطوة بنجاح بدونه
            stop_waiter.cancel()
            try:
                await stop_waiter
            except (asyncio.CancelledError, Exception):
                pass

            if not done:
                # انتهت مهلة الأمان والمهمة لم تنتهِ
                log.error(f"⏰ [مهلة أمان] تجاوزت المهمة [{step_name}] الحد الأقصى للوقت ({task_timeout}ث) بدون استجابة — إلغاء المهمة والمتابعة.")
                for p_task in pending:
                    p_task.cancel()
                    try:
                        await p_task
                    except (asyncio.CancelledError, Exception):
                        pass
                res = {"success": False, "error": f"تجاوز الحد الأقصى لوقت المهمة (timeout {task_timeout}s)"}
            elif disconnect_waiter in done:
                # رُصد انقطاع الاتصال فوراً أثناء عمل المهمة (مثلاً دخول شخص آخر إلى الحساب)
                kick_reason = self.get_disconnect_reason()
                log.warning(f"⚡ [رصد فوري للانقطاع] انقطع اتصال الحساب فوراً أثناء تنفيذ [{step_name}] (السبب: {kick_reason})!")
                step_interrupted = True
                step_task.cancel()
                try:
                    await step_task
                except (asyncio.CancelledError, Exception):
                    pass
            else:
                disconnect_waiter.cancel()
                try:
                    res = step_task.result()
                except Exception as e:
                    log.error(f"💥 حدث خطأ أثناء تنفيذ [{step_name}]: {e}")
                    res = {"success": False, "error": str(e)}

                # فحص إضافي هل تم تسجيل انقطاع الاتصال
                if not self.is_connection_alive():
                    kick_reason = self.get_disconnect_reason()
                    log.warning(f"⚠️ [انقطاع الاتصال] تم رصد انقطاع الاتصال بعد تنفيذ [{step_name}] (السبب: {kick_reason})!")
                    step_interrupted = True

            # فحص فوري لطلب الإيقاف بعد انتهاء المهمة قبل محاولة إعادة الاتصال
            if self._stop_event.is_set():
                log.info(f"🛑 [إيقاف فوري] تم رصد طلب الإيقاف بعد انتهاء [{step_name}] — إنهاء السلسلة فوراً.")
                break

            if step_interrupted:
                # الانتظار دقيقة واحدة وإعادة تسجيل الدخول، ثم إعادة استئناف نفس المهمة التي توقفت
                reconnected = await self.wait_and_reconnect(kick_reason)
                if reconnected:
                    log.info(f"🔄 استئناف وإعادة تشغيل المهمة التي توقفت بسبب الانقطاع: [{step_name}]...")
                    continue  # إعادة تنفيذ نفس الخطوة (step_idx لم يزدد!)
                else:
                    log.error(f"❌ تعذر استئناف المهمة [{step_name}] لعدم نجاح إعادة تسجيل الدخول.")
                    results[step_name] = {"success": False, "error": "انقطع الاتصال أثناء تنفيذ المهمة"}
                    break

            # إذا اكتملت الخطوة بنجاح دون انقطاع اتصال، ننتقل للمهمة التالية
            results[step_name] = res
            if task_key == "prestige":
                t_data = res.get("data", {}) if isinstance(res, dict) else (getattr(res, "data", {}) or {})
                if t_data.get("all_completed") is False:
                    log.info("⏳ [مهام الهيبة] لا تزال بعض المهام غير مكتملة — ستُستأنف في الدورة القادمة تلقائياً فور توفر الفيالق.")
            step_idx += 1

            # التحقق من الإيقاف قبل فترة الأمان بين المهام
            if self._stop_event.is_set():
                break

            # مهلة أمان قصيرة بين المهام مجزأة لفحص الإيقاف
            for _ in range(3):
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(0.5)

        return results

    # ─────────────────────────────────────────────────────────────────
    #  دوال تفاصيل كل مهمة على حدة (Individual Task Handlers)
    # ─────────────────────────────────────────────────────────────────

    # [1] مهمة حصد مزارع المدينة (مهمة أساسية إلزامية تنفذ دائماً في كل دورة)
    async def step_1_city_harvest_task(self) -> Dict[str, Any]:
        """فحص وحصد جميع محاصيل مزارع القمح والخشب والحديد والألماس داخل المدينة (تنفذ دائماً وبشكل إلزامي)."""
        h_cfg = self.config.get("city_harvest", {}) if isinstance(self.config.get("city_harvest"), dict) else {}
        log.info("🌾 بدء حصد كافة مزارع ومناجم المدينة وتعبئة مخازن القلعة بالموارد...")
        task_cfg = {
            "enabled": True,
            "types": h_cfg.get("types", "all"),
            "min_res": int(h_cfg.get("min_res", 0))
        }
        h_task = CityHarvestTask(self.conn, task_cfg)
        await h_task.on_start()
        res_h = await h_task.run()
        if res_h.success:
            log.info(f"🎉 نتيجة حصد المدينة: {res_h.message}")
        else:
            log.warning(f"⚠️ تنبيه في حصد المدينة: {res_h.message}")
        return {"success": res_h.success, "message": res_h.message, "data": res_h.data}

    # [2] مهمة أبحاث الأكاديمية والعلوم
    async def step_2_research_task(self) -> Dict[str, Any]:
        """فحص وإجراء البحث الموصى به تلقائياً في مبنى الأكاديمية بالموارد العادية حصراً."""
        res_cfg = self.config.get("research", {})
        if not bool(res_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي أبحاث الأكاديمية بناءً على رغبة المستخدم (research.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        task_cfg = {
            "enabled": True,
            "tree": res_cfg.get("tree", "defense"),
            "tech_id": res_cfg.get("tech_id", None),
            "check_only": bool(res_cfg.get("check_only", False))
        }

        log.info("🔬 تشغيل مهمة أبحاث الأكاديمية (البحث التلقائي الموصى به من النظام)...")
        task = ResearchTask(self.conn, task_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة أبحاث الأكاديمية: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في أبحاث الأكاديمية: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [3] مهمة التحالف (المساعدة والتبرع لعلوم التحالف)
    async def step_3_alliance_task(self) -> Dict[str, Any]:
        """فحص ومساعدة أعضاء التحالف والتبرع لعلوم التحالف الموصى بها مجاناً."""
        all_cfg = self.config.get("alliance", {})
        if not bool(all_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة التحالف بناءً على رغبة المستخدم (alliance.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        if self.context.alliance_id == 0:
            msg = "⏭️ تم تخطي مهمة التحالف لأن الحساب غير منضم لأي تحالف."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info(f"🤝 بدء تنفيذ مهمة التحالف (المساعدة والتبرع لعلوم التحالف ID: {self.context.alliance_id})...")
        task_cfg = {
            "enabled": True,
            "auto_help": bool(all_cfg.get("auto_help", True)),
            "donate_free": True,  # دائماً تبرع مجاني بالكامل
            "gold_donations": int(all_cfg.get("gold_donations", 0)),
            "sciid": all_cfg.get("sciid", None)  # تلقائي بالموصى به
        }
        task = AllianceTask(self.conn, task_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة مهمة التحالف: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة التحالف: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [4] مهمة الميناء
    async def step_4_port_task(self) -> Dict[str, Any]:
        """فحص وتنفيذ مهمة الميناء التجارية لكافة السفن المتاحة."""
        port_cfg = self.config.get("port", {})
        if not bool(port_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الميناء بناءً على رغبة المستخدم (port.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🚀 تشغيل مهمة الميناء لإرسال السفن التجارية...")
        task_cfg = {
            "enabled": True,
            "ship_type": int(port_cfg.get("ship_type", 0))
        }
        port_task = PortTask(self.conn, task_cfg)
        res_port = await port_task.run()
        if res_port.success:
            log.info(f"🎉 نتيجة الميناء: {res_port.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة الميناء: {res_port.message}")
        return {"success": res_port.success, "message": res_port.message, "data": res_port.data}

    # [5] مهمة تدريب الجنود
    async def step_5_train_task(self) -> Dict[str, Any]:
        """فحص وتنفيذ مهمة تدريب الجنود في الثكنات وفق المستويات المحددة لكل نوع بأقصى سعة."""
        train_cfg = self.config.get("train", {})
        if not bool(train_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي تدريب الجنود بناءً على رغبة المستخدم (train.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # استخراج مستويات التدريب المحددة لكل نوع من القوات
        user_levels = train_cfg.get("levels", {})
        if not isinstance(user_levels, dict) or not user_levels:
            def_lvl = int(train_cfg.get("level", 10))
            user_levels = {b: def_lvl for b in BUILDING_TROOP_MAP.keys()}

        # استخراج الثكنات المستهدفة للتدريب (فقط الأنواع المحددة بمستوى > 0)
        selected_barracks = []
        parsed_levels = {}
        for b_raw, lvl in user_levels.items():
            canon = TYPE_ALIASES.get(str(b_raw).strip().lower())
            if canon:
                lvl_int = int(lvl)
                if lvl_int > 0:
                    if canon not in selected_barracks:
                        selected_barracks.append(canon)
                    parsed_levels[canon] = lvl_int

        if not selected_barracks:
            selected_barracks = list(BUILDING_TROOP_MAP.keys())
            parsed_levels = {b: 10 for b in selected_barracks}

        task_train_config = {
            "types": selected_barracks,
            "levels": parsed_levels,
            "count": "max"  # دائماً التدريب بأقصى سعة ممكنة
        }

        desc_list = [f"{BUILDING_TROOP_MAP[b]['icon']} {BUILDING_TROOP_MAP[b]['name_ar']} (رتبة {parsed_levels.get(b, 10)})" for b in selected_barracks]
        log.info(f"🎯 القوات المستهدفة للتدريب بأقصى طاقة استيعابية: {', '.join(desc_list)}")

        train_task = TrainTask(self.conn, task_train_config)
        await train_task.on_start()
        res_train = await train_task.run()

        if res_train.success:
            log.info(f"🎉 نتيجة تدريب الجنود: {res_train.message}")
        else:
            log.warning(f"⚠️ تنبيه في تدريب الجنود: {res_train.message}")

        return {"success": res_train.success, "message": res_train.message, "data": res_train.data}

    # [6] مهمة دورية الحيوان الأليف
    async def step_6_pet_patrol_task(self) -> Dict[str, Any]:
        """فحص وتنفيذ دورية الحيوان الأليف (الغزال 1261 دائماً) إلى الحيوان المستهدف المحدد."""
        pet_cfg = self.config.get("pet_patrol", {})
        if not bool(pet_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي دورية الحيوان الأليف بناءً على رغبة المستخدم (pet_patrol.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # الحيوان القائم بالدورية: الغزال (1261) دائماً بدون الرجوع للمستخدم
        target_pet_id = 1261

        # تحديد الحيوان المستهدف (الوجهة)
        dest_val = pet_cfg.get("destination", pet_cfg.get("dest", pet_cfg.get("pet", DEFAULT_DESTINATION)))
        target_dest = resolve_pet_destination(dest_val)
        dest_name = PET_DESTINATIONS.get(target_dest, f"وجهة #{target_dest}")

        log.info(f"🐾 جاري إرسال الغزال (1261) في دورية إلى الحيوان المستهدف: [{dest_name}] (معرف: {target_dest})...")

        task_pet_cfg = {
            "pet_id": 1261,
            "destination": target_dest
        }

        pet_task = PetPatrolTask(self.conn, task_pet_cfg)
        _safe_bind_task_logger(pet_task, self._log_callback, level=logging.INFO)

        try:
            res_pet = await pet_task.run()
        finally:
            _safe_unbind_task_logger(pet_task)

        if res_pet.success:
            log.info(f"🎉 نتيجة دورية الحيوان: {res_pet.message}")
        else:
            log.warning(f"⚠️ تنبيه في دورية الحيوان: {res_pet.message}")

        return {"success": res_pet.success, "message": res_pet.message, "data": res_pet.data}

    # [7] مهمة جمع جوائز التوسع الإقليمي
    async def step_7_territory_expansion_task(self) -> Dict[str, Any]:
        """فحص وجمع كافة مكافآت وجوائز حدث التوسع الإقليمي المكتملة في الأحداث."""
        te_cfg = self.config.get("territory_expansion", {})
        if not bool(te_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي جمع جوائز التوسع الإقليمي بناءً على رغبة المستخدم (territory_expansion.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🚩 بدء فحص واستلام مكافآت وجوائز حدث التوسع الإقليمي...")
        task = TerritoryExpansionTask(self.conn, te_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة التوسع الإقليمي: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في التوسع الإقليمي: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [8] مهمة درع السلام التلقائي وحماية القلعة
    async def step_8_shield_task(self) -> Dict[str, Any]:
        """فحص وتفعيل درع السلام لحماية القلعة بالمدة المحددة والسماح بالشراء بالذهب إذا رغب المستخدم."""
        shield_cfg = self.config.get("shield", {})
        if not bool(shield_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة درع السلام بناءً على رغبة المستخدم (shield.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        raw_dur = str(shield_cfg.get("duration", "8h")).lower().strip()
        dur_key = DURATION_ALIASES.get(raw_dur, "8h")
        allow_gold = bool(shield_cfg.get("allow_gold", False))

        shield_name = SHIELD_TYPES.get(dur_key, {}).get("name", f"درع {dur_key}")
        log.info(f"🛡️ بدء مهمة درع السلام لحماية القلعة [{shield_name}] (السماح بالشراء بالذهب: {'نعم' if allow_gold else 'لا'})...")

        task = ShieldTask(self.conn, {
            "duration": dur_key,
            "allow_gold": allow_gold
        })
        res = await task.run()

        if res.success:
            if res.data.get("status") == "already_active":
                log.info(f"🛡️ درع السلام: {res.message}")
            else:
                log.info(f"🎉 نتيجة درع السلام: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في درع السلام: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [9] مهمة استخدام جرعات وشراء الطاقة
    async def step_9_stamina_task(self) -> Dict[str, Any]:
        """استهلاك جرعات الطاقة المجانية من الحقيبة وتنفيذ شراء الطاقة بالذهب بعدد المرات المحدد من المستخدم بناءً على معطيات الاستعلام الشامل."""
        stamina_cfg = self.config.get("stamina", {})
        if not bool(stamina_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الطاقة بناءً على رغبة المستخدم (stamina.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        ctx = self.context
        potions = getattr(ctx, "stamina_potions", {}) or {}
        total_potions = sum(potions.values()) if isinstance(potions, dict) else 0

        # بيانات تبديل الطاقة بالذهب المستخرجة من الاستعلام الشامل
        bs_ctrl = self.conn.init_data.get("buyStaminaCtrl", {}) if (self.conn and hasattr(self.conn, "init_data")) else {}
        current_price = getattr(ctx, "stamina_gold_cost", 0) or int(bs_ctrl.get("price", 0))
        buy_times = getattr(ctx, "stamina_buy_times", 0) if getattr(ctx, "stamina_buy_times", 0) > 0 else int(bs_ctrl.get("buyTimes", 0))
        limit_times = getattr(ctx, "stamina_limit_times", 0) or int(bs_ctrl.get("limitTimes", 30))

        gold_buys = int(stamina_cfg.get("gold_buys", stamina_cfg.get("gold", 0)))
        max_price = int(stamina_cfg.get("max_price", stamina_cfg.get("price_limit", stamina_cfg.get("max_exchange_price", stamina_cfg.get("gold_limit", 0)))))

        # 1. إذا كانت هناك جرعات طاقة في الحقيبة، تُنفّذ المهمة دائماً لاستهلاكها
        if total_potions > 0:
            remaining_buys = max(0, gold_buys - buy_times) if gold_buys > 0 else 0
            if max_price > 0 and current_price > max_price:
                remaining_buys = 0  # حماية: السعر الحالي بالقلعة تجاوز الحد الأقصى للمستخدم، نستهلك الجرعات فقط
            log.info(f"⚡ بدء مهمة الطاقة: توفر {total_potions} جرعة بالحقيبة (سعر التبديل بالقلعة: {current_price} ذهب | الشراء بالذهب المتبقي: {remaining_buys} مرة [تم {buy_times}/{gold_buys}])...")
        else:
            # 2. الحقيبة خالية من الجرعات -> التحقق من شروط تبديل الطاقة بالذهب
            if gold_buys <= 0 and max_price <= 0:
                msg = "⏭️ تم تخطي مهمة الطاقة: الحقيبة خالية من الجرعات ولم يتم تفعيل الشراء بالذهب (gold_buys = 0)."
                log.info(msg)
                return {"skipped": True, "message": msg}

            if limit_times > 0 and buy_times >= limit_times:
                msg = f"⏭️ تم تخطي مهمة الطاقة: تم استنفاد الحد الأقصى اليومي لتبديل الطاقة بالذهب ({buy_times}/{limit_times} مرة) والحقيبة خالية."
                log.iَnfo(msg)
                return {"skipped": True, "message": msg}

            if max_price > 0 and current_price > max_price:
                msg = f"⏭️ تم تخطي مهمة الطاقة: سعر تبديل الطاقة الحالي بالقلعة ({current_price} ذهب) يتجاوز الحد الأقصى المحدد ({max_price} ذهب) والحقيبة خالية."
                log.info(msg)
                return {"skipped": True, "message": msg}

            if gold_buys > 0 and buy_times >= gold_buys and max_price <= 0:
                msg = f"⏭️ تم تخطي مهمة الطاقة: تم استيفاء عدد مرات الشراء بالذهب المحددة ({buy_times}/{gold_buys} مرة) وسعر التبديل الحالي {current_price} ذهب، والحقيبة خالية."
                log.info(msg)
                return {"skipped": True, "message": msg}

            remaining_buys = max(0, gold_buys - buy_times) if gold_buys > 0 else (1 if max_price > 0 and current_price <= max_price else 0)
            if remaining_buys <= 0:
                msg = f"⏭️ تم تخطي مهمة الطاقة: لا توجد عمليات شراء متبقية مطلوبة ({buy_times}/{gold_buys}) والحقيبة خالية."
                log.info(msg)
                return {"skipped": True, "message": msg}

            log.info(f"⚡ بدء مهمة الطاقة: الحقيبة خالية، وسعر التبديل الحالي بالقلعة ({current_price} ذهب) متاح للشراء (المتبقي: {remaining_buys} مرة [تم {buy_times}/{gold_buys}])...")

        task = StaminaTask(self.conn, {
            "use_free": True,
            "gold_buys": remaining_buys,
            "gold": remaining_buys,
            "max_price": max_price
        })
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة مهمة الطاقة: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة الطاقة: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [10] مهمة تفعيل المهارات التلقائية
    async def step_10_skills_task(self) -> Dict[str, Any]:
        """فحص وتفعيل المهارات التلقائية المحددة من المستخدم (الحصاد الوافر، الجمع السريع، حصاد المخزن، أو الكل)."""
        skills_cfg = self.config.get("skills", {})
        if not bool(skills_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة المهارات بناءً على رغبة المستخدم (skills.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        target_skills = resolve_target_skills(skills_cfg)
        if not target_skills:
            msg = "⚠️ لم يتم تحديد أي مهارات لتفعيلها (قائمة المهارات فارغة)."
            log.warning(msg)
            return {"skipped": True, "message": msg}

        skills_names_str = "، ".join([SUPPORTED_SKILLS.get(k, {}).get("name", k) for k in target_skills])
        log.info(f"🎯 بدء مهمة المهارات التلقائية للمهارات المستهدفة: [{skills_names_str}]...")

        task = SkillsTask(self.conn, {
            "skills": target_skills,
            "check_only": False
        })
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة مهمة المهارات: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة المهارات: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [11] مهمة تجنيد الأبطال وسحب الصناديق اليومية
    async def step_11_hero_draw_task(self) -> Dict[str, Any]:
        """فحص وسحب تجنيد الأبطال، بحث المهارات، وصناديق الأبطال المجانية تلقائياً."""
        hero_cfg = self.config.get("hero_draw", {})
        if not bool(hero_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة تجنيد وسحب الأبطال بناءً على رغبة المستخدم (hero_draw.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🦸 بدء مهمة تجنيد الأبطال وبحث المهارات وسحب الصناديق اليومية...")
        task = HeroDrawTask(self.conn, hero_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة تجنيد الأبطال: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في تجنيد الأبطال: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [11b] مهمة استكشاف جناح الكنز المجاني (مهمة أساسية إلزامية تنفذ دائماً في كل دورة)
    async def step_11b_treasure_pavilion_task(self) -> Dict[str, Any]:
        """فحص واستكشاف جناح الكنز المجاني تلقائياً في كل دورة (تنفذ دائماً وبشكل إلزامي مثل city_harvest) مع التحقق الصارم لحماية الذهب."""
        tp_cfg = self.config.get("treasure_pavilion", {}) if isinstance(self.config.get("treasure_pavilion"), dict) else {}
        log.info("💎 بدء مهمة استكشاف جناح الكنز (Treasure Pavilion)...")
        task = TreasurePavilionTask(self.conn, tp_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة جناح الكنز: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في جناح الكنز: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [11c] مهمة صقل معمل الحدادة المجاني (مهمة أساسية إلزامية تنفذ دائماً في كل دورة)
    async def step_11c_blacksmith_forge_task(self) -> Dict[str, Any]:
        """فحص وصقل معمل الحدادة المجاني تلقائياً في كل دورة (تنفذ دائماً وبشكل إلزامي مثل city_harvest و treasure_pavilion) مع التحقق الصارم لحماية الذهب."""
        bf_cfg = self.config.get("blacksmith_forge", {}) if isinstance(self.config.get("blacksmith_forge"), dict) else {}
        log.info("🔨 بدء مهمة معمل الحدادة وصقل الرون (Blacksmith Forge)...")
        task = BlacksmithForgeTask(self.conn, bf_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة معمل الحدادة: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في معمل الحدادة: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [11d] مهمة الضريح الإمبراطوري المجاني (مهمة أساسية إلزامية تنفذ دائماً في كل دورة)
    async def step_11d_imperial_mausoleum_task(self) -> Dict[str, Any]:
        """فحص وتنفيذ الضريح الإمبراطوري المجاني تلقائياً في كل دورة (تنفذ دائماً وبشكل إلزامي مثل city_harvest و treasure_pavilion و blacksmith_forge) مع التحقق الصارم لحماية الذهب والنحاس."""
        im_cfg = self.config.get("imperial_mausoleum", {}) if isinstance(self.config.get("imperial_mausoleum"), dict) else {}
        log.info("🏛️ بدء مهمة الضريح الإمبراطوري (Imperial Mausoleum)...")
        task = ImperialMausoleumTask(self.conn, im_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة الضريح الإمبراطوري: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في الضريح الإمبراطوري: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [11e] مهمة صندوق التحالف المجاني (مهمة أساسية إلزامية تنفذ دائماً في كل دورة)
    async def step_11e_alliance_treasure_task(self) -> Dict[str, Any]:
        """فحص واستلام/حفر صندوق التحالف المجاني تلقائياً في كل دورة مع التحقق الصارم لحماية الذهب."""
        at_cfg = self.config.get("alliance_treasure", {}) if isinstance(self.config.get("alliance_treasure"), dict) else {}
        log.info("📦 بدء مهمة صندوق التحالف (Alliance Treasure)...")
        task = AllianceTreasureTask(self.conn, at_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة صندوق التحالف: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في صندوق التحالف: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [11f] مهمة الهدية الفاخرة اليومية (مهمة أساسية إلزامية تنفذ دائماً في كل دورة)
    async def step_11f_daily_luxury_gift_task(self) -> Dict[str, Any]:
        """فحص وجمع كافة هدايا الهدية الفاخرة اليومية المتاحة تلقائياً في كل دورة."""
        dlg_cfg = self.config.get("daily_luxury_gift", {}) if isinstance(self.config.get("daily_luxury_gift"), dict) else {}
        log.info("🎁 بدء مهمة الهدية الفاخرة اليومية (Daily Luxury Gift)...")
        task = DailyLuxuryGiftTask(self.conn, dlg_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة الهدية الفاخرة: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في الهدية الفاخرة: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [11g] مهمة صندوق الـ VIP اليومي المجاني (مهمة أساسية إلزامية تنفذ دائماً في كل دورة)
    async def step_11g_vip_gift_task(self) -> Dict[str, Any]:
        """فحص واستلام صندوق الـ VIP اليومي المجاني تلقائياً بأمان في كل دورة."""
        vg_cfg = self.config.get("vip_gift", {}) if isinstance(self.config.get("vip_gift"), dict) else {}
        log.info("👑 بدء مهمة صندوق الـ VIP اليومي المجاني (VIP Daily Gift)...")
        task = VipGiftTask(self.conn, vg_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة صندوق VIP: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في صندوق VIP: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [12] مهمة قاعة الاستراتيجيات وتطوير التكتيكات
    async def step_12_tactics_hall_task(self) -> Dict[str, Any]:
        """فحص واستلام أبحاث التكتيكات المكتملة وبدء البحث التكتيكي المحدد من المستخدم."""
        th_cfg = self.config.get("tactics_hall", {})
        if not bool(th_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة قاعة الاستراتيجيات بناءً على رغبة المستخدم (tactics_hall.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        target_tactic = th_cfg.get("tactic") or th_cfg.get("mid", "القلعة الفارغة")
        target_mid = parse_tactic_choice(target_tactic)
        t_meta = TACTICS_MAP.get(target_mid, {"name_ar": str(target_tactic), "category": "", "icon": "📜"})

        log.info(f"🏛️ بدء مهمة قاعة الاستراتيجيات للبحث المطلوب: {t_meta.get('icon', '📜')} [{t_meta.get('name_ar', target_tactic)}]...")

        task = TacticsHallTask(self.conn, {"tactic": target_mid})
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة قاعة الاستراتيجيات: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في قاعة الاستراتيجيات: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [13] مهمة طاحونة الماء وزيادة إنتاج موارد القلعة
    async def step_13_watermill_task(self) -> Dict[str, Any]:
        """فحص وتفعيل مضاعفة إنتاج مزارع ومناجم المدينة باستخدام أدوات التعزيز مع الشراء من المتجر إن سُمح."""
        wm_cfg = self.config.get("watermill", {})
        if not bool(wm_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة طاحونة الماء بناءً على رغبة المستخدم (watermill.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        target_types = wm_cfg.get("types", wm_cfg.get("res_type", "all"))
        allow_buy = bool(wm_cfg.get("allow_shop_buy", wm_cfg.get("auto_buy", True)))

        log.info(f"💧 بدء مهمة طاحونة الماء لزيادة إنتاج الموارد (الأنواع: {target_types} | الشراء من متجر التحالف: {'مسموح' if allow_buy else 'معطل'})...")

        task = WatermillTask(self.conn, {
            "types": target_types,
            "res_type": target_types,
            "allow_shop_buy": allow_buy,
            "auto_buy": allow_buy
        })
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة طاحونة الماء: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في طاحونة الماء: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [14] مهمة نافورة الأمنيات الملكية وبئر الحظ
    async def step_14_fountain_task(self) -> Dict[str, Any]:
        """فحص واستغلال أمنيات نافورة الأمنيات الملكية للموارد المحددة والشراء بالذهب إن سُمح."""
        fountain_cfg = self.config.get("fountain", {})
        if not bool(fountain_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة نافورة الأمنيات بناءً على رغبة المستخدم (fountain.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        res_list = fountain_cfg.get("resources", ["food", "wood", "iron", "diamond"])
        gold_times = int(fountain_cfg.get("gold_times", 0))
        raw_allow_gold = bool(fountain_cfg.get("allow_gold", False))
        allow_gold = raw_allow_gold and gold_times > 0
        if not allow_gold:
            gold_times = 0

        castle_lv = getattr(self.context, "castle_level", 0) or 0
        res_display = "، ".join(res_list) if isinstance(res_list, list) else str(res_list)
        log.info(f"⛲ بدء مهمة نافورة الأمنيات (الموارد: [{res_display}] | قلعة لفل: {castle_lv} | السماح بالشراء بالذهب: {'نعم' if allow_gold else 'لا'} | عدد مرات الذهب: {gold_times})...")

        task_cfg = {
            "resources": res_list,
            "use_gold": allow_gold,
            "allow_gold": allow_gold,
            "gold_times": gold_times,
            "max_gold": fountain_cfg.get("max_gold", 200),
            "castle_level": castle_lv,
        }

        task = FountainTask(self.conn, task_cfg)
        _safe_bind_task_logger(task, self._log_callback, level=logging.INFO)
        try:
            res = await task.run()
        finally:
            _safe_unbind_task_logger(task)

        if self._log_callback:
            self._log_callback(f"⛲ {res.message}")

        if res.success:
            log.info(f"🎉 نتيجة نافورة الأمنيات: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في نافورة الأمنيات: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [15] مهمة ورشة المواد وصناعة خامات العتاد
    async def step_15_material_workshop_task(self) -> Dict[str, Any]:
        """فحص خط إنتاج ورشة المواد وملء الفراغات المتاحة بالخامات المحددة من المستخدم بالتوازن التام."""
        mw_cfg = self.config.get("material_workshop", {})
        if not bool(mw_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة ورشة المواد بناءً على رغبة المستخدم (material_workshop.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        target_mats = mw_cfg.get("materials", "all")
        mids = parse_materials_choice(target_mats)
        mats_names = [f"{WORKSHOP_MATERIALS_MAP[m]['icon']} {WORKSHOP_MATERIALS_MAP[m]['name_ar']}" for m in mids if m in WORKSHOP_MATERIALS_MAP]
        log.info(f"🔨 بدء مهمة ورشة المواد لإنتاج الخامات المستهدفة: [{', '.join(mats_names)}]...")

        task = MaterialWorkshopTask(self.conn, {"materials": target_mats})
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة ورشة المواد: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في ورشة المواد: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [16] مهمة القافلة التجارية وحراسة الكنز
    async def step_16_caravan_task(self) -> Dict[str, Any]:
        """فحص واستلام جوائز القافلة السابقة ومعالجة أحداث الطريق وإرسال قافلة جديدة تلقائياً."""
        caravan_cfg = self.config.get("caravan", {})
        if not bool(caravan_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة القافلة وحراسة الكنز بناءً على رغبة المستخدم (caravan.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🐪 بدء مهمة القافلة التجارية وحراسة الكنز (استلام الجوائز ومعالجة الأحداث وإرسال القافلة)...")
        task = CaravanTask(self.conn, caravan_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة القافلة وحراسة الكنز: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في القافلة وحراسة الكنز: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [18] مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة
    async def step_18_port_delegate_task(self) -> Dict[str, Any]:
        """فحص وتعيين مهام الميناء العسكري واستلام المكافآت وشراء المنتج المحدد بالكامل من متجر الجزيرة."""
        pd_cfg = self.config.get("port_delegate", {})
        if not bool(pd_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الميناء العسكري وتفويض السفن بناءً على رغبة المستخدم (port_delegate.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        shop_choice = pd_cfg.get("shop_item", pd_cfg.get("item", "7"))
        buy_all = False
        buy_items = None

        choice_str = str(shop_choice).strip().lower()
        if choice_str in ("all", "الكل", "all_items"):
            buy_all = True
            log.info("⚓ بدء مهمة الميناء العسكري: تفويض السفن تلقائياً وشراء جميع منتجات متجر الجزيرة المتاحة...")
        elif choice_str in ("none", "لا_شيء", "تعطيل", "0", ""):
            log.info("⚓ بدء مهمة الميناء العسكري: تفويض السفن واستلام المكافآت (تخطي شراء المتجر)...")
        else:
            buy_items = shop_choice
            resolved_gid = resolve_island_goods_id(choice_str)
            item_name = ISLAND_SHOP_CATALOG.get(resolved_gid, {}).get("name", str(shop_choice)) if resolved_gid else str(shop_choice)
            log.info(f"⚓ بدء مهمة الميناء العسكري: تفويض السفن وشراء كامل الكمية المتاحة من [{item_name}] من متجر الجزيرة...")

        task_config = {
            "buy_all": buy_all,
            "buy_items": buy_items,
            "auto_claim": True,
            "skip_delegate": False,
            "skip_shop": (choice_str in ("none", "لا_شيء", "تعطيل", "0", ""))
        }

        task = PortDelegateTask(self.conn, task_config)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة الميناء العسكري ومتجر الجزيرة: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في الميناء العسكري: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [19] مهمة دار الادخار واستثمار الذهب
    async def step_19_savings_bank_task(self) -> Dict[str, Any]:
        """فحص وسحب أرباح دار الادخار المكتملة وإيداع الذهب التلقائي بالمدة المختارة (7 أو 15 أو 30 يوماً)."""
        sb_cfg = self.config.get("savings_bank", {})
        if not bool(sb_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة دار الادخار بناءً على رغبة المستخدم (savings_bank.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        raw_days = sb_cfg.get("days", DEFAULT_SAVINGS_DAYS)
        target_days = parse_savings_days(raw_days)

        plan_info = SAVINGS_PLANS.get(target_days, SAVINGS_PLANS[DEFAULT_SAVINGS_DAYS])
        log.info(f"🏦 بدء مهمة دار الادخار (فحص الأرباح وإيداع الذهب بخطة: {plan_info['name']})...")

        task = SavingsBankTask(self.conn, {"days": target_days})
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة دار الادخار: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في دار الادخار: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # ─────────────────────────────────────────────────────────────────
    #  الخطوة 20: مهمة ترقية القلعة ومباني الموارد والمعسكرات والتسريع
    # ─────────────────────────────────────────────────────────────────
    async def step_20_building_task(self) -> Dict[str, Any]:
        """ترقية القلعة وتسريعها وترقية المعسكرات والمراكز الطبية والمزارع وخيم العسكرية."""
        b_cfg = self.config.get("building", {})
        if not bool(b_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة ترقية المباني بناءً على رغبة المستخدم (building.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        up_castle = bool(b_cfg.get("upgrade_castle", b_cfg.get("castle", True)))
        sp_castle = bool(b_cfg.get("speedup_castle", b_cfg.get("speedup", False)))
        up_support = bool(b_cfg.get("upgrade_support_buildings", b_cfg.get("buildings", True)))

        log.info(
            f"🏗️ بدء مهمة ترقية المباني (ترقية القلعة: {up_castle} | "
            f"تسريع القلعة: {sp_castle} | ترقية المعسكرات والمراكز والمزارع وخيم الجيش: {up_support})..."
        )

        task_cfg = {
            "castle": up_castle,
            "upgrade_castle": up_castle,
            "speedup_castle": sp_castle,
            "speedup": sp_castle,
            "buildings": up_support,
            "support_buildings": up_support,
            "upgrade_support_buildings": up_support,
        }

        task = BuildingTask(self.conn, task_cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة مهمة المباني: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة المباني: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_22_prestige_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة مهام الهيبة اليومية داخل القلعة (Daily Prestige Quests):
          - متجر المهربين بالموارد العادية فقط بدون ذهب (10 مشتريات).
          - الساقية وتفعيل جميع مباني إنتاج الموارد.
          - تدريب الجنود (250 من كل نوع مستوى 1).
          - حصن الحرب وتدريب الفخاخ.
        ملاحظة: مهام المسيرات الخارجية (غزاة الهيبة، معقل الهيبة، جمع موارد الهيبة)
        نُقلت بالكامل لتُدار مركزياً وذكياً ضمن منسق الفيالق (march_manager).
        """
        p_cfg = self.config.get("prestige", {})
        if not bool(p_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة مهام الهيبة بناءً على رغبة المستخدم (prestige.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🎖️ بدء مهمة مهام الهيبة اليومية (Prestige Quests)...")
        task_cfg = dict(p_cfg)
        task = PrestigeTask(self.conn, task_cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة مهمة الهيبة: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة الهيبة: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_22c_prestige_box_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة استلام صناديق النشاط اليومي لمهام الهيبة (Prestige Box Task):
          - تتبع تلقائياً تفعيل مهمة مهام الهيبة (prestige.enabled).
          - إذا كانت prestige.enabled غير مفعلة (False)، لا يتم تنفيذ استلام الصناديق.
          - استعلام مسبق عن نقاط النشاط والصناديق المستلمة (1013/1).
          - إنهاء المهمة فوراً إذا لم تكن هناك صناديق جاهزة.
          - استلام الصناديق المستحقة تباعاً (CMD 3105 / SUB 2).
        """
        # 1. التحقق من تفعيل مهمة مهام الهيبة الرئيسية (التحكم المباشر من prestige.enabled)
        p_cfg = self.config.get("prestige", {})
        prestige_enabled = bool(p_cfg.get("enabled", True)) if isinstance(p_cfg, dict) else bool(p_cfg)

        if not prestige_enabled:
            msg = "⏭️ تم تخطي مهمة استلام صناديق الهيبة نظراً لتعطيل مهمة مهام الهيبة (prestige.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # 2. فحص إعداد مهمة الصناديق إن وُجد
        cfg = self.config.get("prestige_box", self.config.get("alliance_box", {}))
        if isinstance(cfg, bool):
            cfg = {"enabled": cfg}
        elif not isinstance(cfg, dict):
            cfg = {"enabled": True}

        if not bool(cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة استلام صناديق الهيبة (prestige_box.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🎁 بدء مهمة استلام صناديق مهام الهيبة والنشاط اليومي...")
        task = PrestigeBoxTask(self.conn, cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة استلام صناديق الهيبة: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في صناديق الهيبة: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_22d_troy_treasure_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة كنز طروادة (Troy Treasure Task):
          - فحص تفعيل المهمة (troy_treasure.enabled).
          - المرحلة 1: استلام كافة جوائز إنجاز المهام الجاهزة (CMD 1028 / SUB 5).
          - إنهاء المهمة فوراً إذا لم تكن الفعالية نشطة أو لا توجد جوائز جاهزة.
        """
        cfg = self.config.get("troy_treasure", {})
        if isinstance(cfg, bool):
            cfg = {"enabled": cfg, "subtasks": {"claim_quests": True}}
        elif not isinstance(cfg, dict):
            cfg = {"enabled": True, "subtasks": {"claim_quests": True}}

        if not bool(cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة كنز طروادة (troy_treasure.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🏛️ بدء مهمة كنز طروادة (Troy Treasure)...")
        task = TroyTreasureTask(self.conn, cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة كنز طروادة: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في كنز طروادة: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_22b_hospital_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة فحص ومعالجة الجنود الجرحى في المشفى (Hospital Cure Task):
          - التحقق من وجود مبنى المشفى (bid: 206) ومستواه في القلعة.
          - فحص طابور العلاج (queueCtrl['1202']) والتأكد من إتاحته.
          - استعلام أحدث بيانات الجيش (1005/1) لتحديد كافة الجنود الجرحى.
          - إرسال طلب العلاج العادي (1005/4 mode: 0) بكافة الأعداد المصابة.
        """
        hosp_cfg = self.config.get("hospital", {})
        if isinstance(hosp_cfg, bool):
            hosp_cfg = {"enabled": hosp_cfg}
        elif not isinstance(hosp_cfg, dict):
            hosp_cfg = {"enabled": True}

        if not hosp_cfg.get("enabled", True):
            msg = "⏭️ تم تخطي مهمة علاج الجرحى بالمشفى (hospital.enabled = False)."
            log.info(msg)
            return {"success": True, "message": msg, "skipped": True}

        task = HospitalTask(self.conn, hosp_cfg)
        _safe_bind_task_logger(task, self._log_callback, level=logging.INFO)

        try:
            res = await task.run()
        finally:
            _safe_unbind_task_logger(task)

        # إشعار لوحة التحكم وملف السجل بالنتيجة المباشرة الصريحة
        if self._log_callback:
            self._log_callback(f"🏥 {res.message}")

        if res.success:
            log.info(f"🎉 نتيجة مهمة المشفى: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة المشفى: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_23_march_manager_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة منسق الفيالق والمسيرات الذكي الموحد (March Manager & Orchestrator):
          - إدارة الفيالق المتاحة وتوزيعها وفق مصفوفة أولويات مخصصة من Firebase.
          - مساعدة الموارد (Transport).
          - استكشاف الأطلال (Ruins) بمسيرة واحدة فقط حصراً.
          - قتال: العفريت (مع استعلام استباقي لتأكيد الحدث) أو الغزاة أو المتمردين (خيار حصري).
          - الهجوم على المعاقل والملاجئ (Stronghold).
          - جمع الذهب في أراضي التحالفات (Gold Gather) بأولوية تسبق جمع الموارد العامة.
          - جمع الموارد بالفيالق الشاغرة المتبقية بحسابات حمولة رياضية دقيقة مطابقة للعبة.
        """
        return {"skipped": True, "message": "مهمة منسق الفيالق قيد التطوير"}



    # ─────────────────────────────────────────────────────────────────
    #  دورة التشغيل الواحدة (Single Run Lifecycle)
    # ─────────────────────────────────────────────────────────────────
    async def run_once(self) -> Dict[str, Any]:
        """
        تشغيل دورة واحدة كاملة:
          0. استعلام أحدث إعدادات المهام من قاعدة البيانات المحلية في بداية كل دورة.
          0.5 التحقق من صلاحية الاشتراك وحظر الحساب.
          1. تسجيل الدخول.
          2. الاستعلام الشامل (مع إعادة المحاولة عند انقطاع الاتصال).
          3. تنفيذ سلسلة المهام بالترتيب مع فحص الجدول الزمني لكل مهمة.
          4. إغلاق الاتصال بأمان وإعادة النتائج.
        """
        # 0. استعلام وتحديث إعدادات المهام للقلعة من قاعدة البيانات المحلية للدورة الحالية
        self.reload_config_from_db()

        # 0.5 التحقق من طلب الإيقاف وصلاحية الاشتراك وحظر الحساب
        if self._stop_event.is_set():
            return {"success": False, "error": "تم طلب إيقاف البوت"}

        valid, reason = self.check_subscription_validity()
        if not valid:
            log.warning(f"🛑 [إيقاف التشغيل] {reason} — لن يتم تشغيل البوت للحساب {self.email}!")
            self._update_bot_conn_state("idle", f"متوقف: {reason}")
            return {"success": False, "error": reason}

        try:
            # 1. تسجيل الدخول
            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            connected = await self.login_and_connect()
            if not connected or self._stop_event.is_set():
                return {"success": False, "error": "فشل الاتصال والمصادقة أو تم الإيقاف"}

            # 2. الاستعلام الشامل
            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            try:
                await self.perform_comprehensive_query()
            except Exception as e:
                if not self.is_connection_alive():
                    log.warning("⚠️ انقطع الاتصال أثناء الاستعلام الشامل، جاري الانتظار دقيقة وإعادة الاتصال...")
                    reconnected = await self.wait_and_reconnect(self.get_disconnect_reason())
                    if reconnected:
                        await self.perform_comprehensive_query()
                else:
                    log.warning(f"⚠️ تنبيه أثناء الاستعلام الشامل: {e}")

            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            # 2.5 تحديث بيانات وموارد القلعة في بداية الدورة مباشرة
            try:
                self.sync_castle_resources()
            except Exception as e:
                log.warning(f"⚠️ تنبيه أثناء تحديث موارد القلعة في بداية الدورة: {e}")

            # 3. تنفيذ سلسلة المهام
            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            pipeline_results = await self.execute_task_pipeline()

            # 4. تحديث الموارد في نهاية الدورة أيضاً (لحفظ نواتج الحصاد والجمع)
            try:
                self.sync_castle_resources()
            except Exception:
                pass

            if not self._log_callback:
                print("\n" + "═" * 72)
                print("🏁 اكتمال تنفيذ الدورة بنجاح من قبل مدير البوت!")
                print("═" * 72 + "\n")

            return {
                "success": True,
                "account": self.email,
                "results": pipeline_results
            }

        except Exception as e:
            log.error(f"💥 خطأ أثناء تنفيذ دورة مدير البوت: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

        finally:
            if self.conn:
                await self.conn.close()
                log.info(f"🔒 تم إغلاق اتصال الحساب {self.email} بأمان.")
            if not getattr(self, "is_loop", False):
                self._update_bot_conn_state("idle", "انتهت الدورة بنجاح")

    # للتوافق مع الكود القديم
    async def run(self) -> Dict[str, Any]:
        """مستعار لـ run_once() — للتوافق مع الاستدعاءات القديمة."""
        return await self.run_once()

    # ─────────────────────────────────────────────────────────────────
    #  دورة التشغيل المستمر (Loop Mode)
    # ─────────────────────────────────────────────────────────────────
    async def run_loop(self, loop_interval_minutes: int = 60) -> None:
        """
        تشغيل مستمر لا ينتهي — ينفذ دورة كاملة ثم ينتظر المدة المحددة.

        ⚡ كفاءة عالية (مناسب لـ 1000+ حساب متزامن):
          - asyncio.sleep() لا يستهلك أي CPU أثناء الانتظار
          - يحفظ حالة الجدول بعد كل دورة لضمان الاستمرارية
          - يكتشف أخطاء الدورة ويستمر للدورة التالية بدلاً من الإيقاف

        Args:
            loop_interval_minutes: المدة بين الدورات بالدقائق (افتراضي: 60)

        التشغيل من سطر الأوامر:
            python bot_manager.py --email "..." --loop
            python bot_manager.py --email "..." --loop --loop-interval 30
        """
        self.is_loop = True
        iteration     = 0
        interval_secs = loop_interval_minutes * 60

        log.info(f"🔁 وضع التشغيل المستمر نشط — دورة كل {loop_interval_minutes} دقيقة")

        while not self._stop_event.is_set():
            iteration += 1
            start_time = datetime.now()

            sep_line = "\n" + "═" * 72
            cycle_line = f"🔄 دورة رقم #{iteration} — بدأت {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
            if self._log_callback:
                self._log_callback(sep_line.strip())
                self._log_callback(cycle_line)
            else:
                print(sep_line)
                log.info(cycle_line)
                print("═" * 72)
            self._update_bot_conn_state("connected", f"بدء دورة رقم #{iteration}")

            try:
                await self.run_once()
            except Exception as e:
                log.error(f"💥 خطأ في الدورة #{iteration}: {e}", exc_info=True)

            # إذا طُلب الإيقاف خلال الدورة — اخرج فوراً
            if self._stop_event.is_set():
                break

            # التحقق من صلاحية الاشتراك وحالة الحظر بعد انتهاء الدورة الحالية
            valid, reason = self.check_subscription_validity()
            if not valid:
                log.warning(f"🛑 [إيقاف الدورة المستمرة] {reason}")
                self._update_bot_conn_state("idle", f"متوقف: {reason}")
                break

            # حساب وقت الانتظار المتبقي
            elapsed   = (datetime.now() - start_time).total_seconds()
            remaining = max(0.0, interval_secs - elapsed)

            from datetime import timezone
            next_run_dt = datetime.now(timezone.utc) + timedelta(seconds=remaining)
            next_run_iso = next_run_dt.isoformat()
            next_run_str = (datetime.now() + timedelta(seconds=remaining)).strftime("%H:%M:%S")
            rem_mins = max(1, round(remaining / 60))

            log.info(f"✅ انتهت الدورة #{iteration} في {elapsed:.0f}ث — الدورة القادمة الساعة: {next_run_str} (متبقي {rem_mins} دقيقة)")

            if remaining > 0:
                self._update_bot_conn_state(
                    "waiting",
                    f"بانتظار الدورة القادمة الساعة {next_run_str} (متبقي {rem_mins} دقيقة)",
                    next_run_time=next_run_iso
                )
                log.info(f"💤 انتظار {rem_mins} دقيقة...")
                # نوم مجزأ ليفحص stop_event كل ثانية بدلاً من asyncio.sleep الكامل
                sleep_step = 1.0
                slept = 0.0
                while slept < remaining and not self._stop_event.is_set():
                    await asyncio.sleep(min(sleep_step, remaining - slept))
                    slept += sleep_step
            else:
                self._update_bot_conn_state("connected", f"بدء الدورة التالية فوراً (#{iteration + 1})")

        # إغلاق الاتصال بأمان وتحديث الحالة إلى idle عند الخروج من حلقة التشغيل
        if self.conn:
            try:
                await self.conn.close()
            except Exception:
                pass
        self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")



# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر من سطر الأوامر (CLI Entry Point)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.database import get_castle

    parser = argparse.ArgumentParser(
        description="Empire Bot Manager — مدير البوت ومنسق المهام الشامل"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب المستهدف")
    parser.add_argument(
        "--firebase-config",
        dest="firebase_config",
        default=None,
        help="مسار ملف JSON يحتوي على إعدادات المستخدم من Firebase (يتجاوز جميع خيارات الإعدادات الأخرى)"
    )
    parser.add_argument("--firebase-user-id",   dest="firebase_user_id",   default=None, help="معرف المستخدم في Firebase")
    parser.add_argument("--firebase-castle-id", dest="firebase_castle_id", default=None, help="معرف القلعة في Firebase")
    parser.add_argument(
        "--reconnect-wait",
        type=int,
        default=60,
        help="مدة الانتظار بالثواني عند انقطاع الاتصال بسبب دخول شخص آخر للحساب [افتراضي: 60 ثانية]"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        default=False,
        help="تشغيل البوت في حلقة مستمرة لا تنتهي [افتراضي: معطل]"
    )
    parser.add_argument(
        "--loop-interval",
        type=int,
        default=60,
        dest="loop_interval",
        metavar="MINUTES",
        help="المدة بين الدورات بالدقائق في وضع الحلقة الدائمة [افتراضي: 60 دقيقة]"
    )
    parser.add_argument(
        "--ignore-schedule",
        action="store_true",
        default=False,
        help="تجاهل الجدولة الزمنية للمهام وتشغيلها فورياً"
    )

    args = parser.parse_args()

    # استخراج الحساب المطلوب
    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد حسابات مسجلة في session_cache.json!")
        sys.exit(1)

    target_email = args.email or next(iter(accounts.keys()))
    if target_email not in accounts:
        print(f"❌ الحساب {target_email} غير موجود في session_cache.json!")
        sys.exit(1)

    cfg = {}
    ignore_sched = args.ignore_schedule
    user_id = args.firebase_user_id
    castle_id = args.firebase_castle_id

    # 1. إذا تم تمرير ملف إعدادات Firebase
    if args.firebase_config and os.path.exists(args.firebase_config):
        try:
            with open(args.firebase_config, "r", encoding="utf-8") as _fc:
                cfg = json.load(_fc)
            log.info(f"✅ تم تحميل إعدادات Firebase من: {args.firebase_config}")
            ignore_sched = True
        except Exception as _fe:
            log.error(f"❌ خطأ في قراءة ملف إعدادات Firebase: {_fe}")
            sys.exit(1)
    else:
        # 2. استرجاع أحدث إعدادات من قاعدة البيانات المحلية إن وجدت
        try:
            c = get_castle(target_email)
            if c:
                cfg_raw = c.get("config")
                if isinstance(cfg_raw, str) and cfg_raw:
                    cfg = json.loads(cfg_raw)
                elif isinstance(cfg_raw, dict):
                    cfg = cfg_raw
                user_id = user_id or c.get("user_id")
                castle_id = castle_id or c.get("id") or c.get("castle_id")
        except Exception as _dbe:
            log.debug(f"تنبيه أثناء قراءة إعدادات القلعة من قاعدة البيانات: {_dbe}")

    manager = BotManager(
        target_email,
        cfg,
        reconnect_wait_seconds=args.reconnect_wait,
        ignore_schedule=ignore_sched,
        user_id=user_id,
        castle_id=castle_id,
    )

    if args.loop:
        print(f"\n{'═'*72}")
        print(f"🔁 وضع التشغيل المستمر (Loop Mode) — دورة كل {args.loop_interval} دقيقة")
        print(f"   الحساب : {target_email}")
        print(f"   للإيقاف: اضغط Ctrl+C")
        print(f"{'═'*72}\n")
        asyncio.run(manager.run_loop(loop_interval_minutes=args.loop_interval))
    else:
        print(f"\n{'═'*72}")
        print(f"▶️  تشغيل دورة واحدة (One-Shot Mode)")
        print(f"   الحساب : {target_email}")
        print(f"   للتشغيل المستمر أضف: --loop")
        print(f"{'═'*72}\n")
        asyncio.run(manager.run_once())
