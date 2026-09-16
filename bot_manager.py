# -*- coding: utf-8 -*-
"""
bot_manager.py — مدير البوت ومنسق المهام الشامل (Empire Bot Manager & Orchestrator)
════════════════════════════════════════════════════════════════════════════════════════
يقوم هذا الملف بدور "مدير البوت" للحساب:
  1. تسجيل الدخول مرة واحدة فقط وإجراء المصافحة المشفرة مع السيرفر.
  2. الاستعلام الشامل الأولي (Comprehensive Status Query):
     - جلب بيانات اللورد (الاسم، المستوى، المملكة، القوة القتالية، الذهب).
     - جلب مباني المدينة ومستوياتها وحالاتها (القلعة، الأسوار، الثكنات الأربعة، الخيام).
     - جلب طوابير العمل النشطة (البناء، التدريب، الأبحاث، المسيرات).
     - فحص سفن الميناء المتاحة.
     - فحص الحيوانات الأليفة المتاحة وحالة دورياتها.
     - تخزين هذه البيانات في سياق موحد (Account Context) لتمريرها للمهام.
  3. تنفيذ المهام بالترتيب المحدد وفق رغبة المستخدم في منطقة مهام واضحة وسهلة التعديل:
     • الخطوة 1: حصد مزارع المدينة (City Harvest Task)
     • الخطوة 2: أبحاث الأكاديمية والعلوم (Academy Research Task)
     • الخطوة 3: مهمة التحالف ومساعدة الأعضاء والتبرع للعلوم (Alliance Task)
     • الخطوة 4: مهمة الميناء التجاري (Port Task)
     • الخطوة 5: مهمة تدريب الجنود (Train Task)
     • الخطوة 6: مهمة دورية الحيوانات الأليفة (Pet Patrol Task)
     • الخطوة 7: مهمة جمع جوائز التوسع الإقليمي (Territory Expansion Task)
     • الخطوة 8: مهمة درع السلام التلقائي وحماية القلعة (Peace Shield Task)
     • الخطوة 9: مهمة استخدام وشراء الطاقة (Stamina Task)
     • الخطوة 10: مهمة تفعيل المهارات التلقائية (Skills Task)
     • الخطوة 11: مهمة تجنيد الأبطال وسحب الصناديق اليومية (Hero Draw Task)
     • الخطوة 12: مهمة قاعة الاستراتيجيات وتطوير التكتيكات (Tactics Hall Task)
     • الخطوة 13: مهمة طاحونة الماء وزيادة إنتاج موارد القلعة (Watermill Task)
     • الخطوة 14: مهمة نافورة الأمنيات الملكية وبئر الحظ (Trevi Fountain Task)
     • الخطوة 15: مهمة ورشة المواد وصناعة خامات العتاد (Material Workshop Task)
     • الخطوة 16: مهمة القافلة التجارية وحراسة الكنز (Caravan Task)
     • الخطوة 17: مهمة التاجر المتجول والمقايضة التلقائية (Traveling Merchant Task)
     • الخطوة 18: مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة (Port Delegate Task)
     • الخطوة 19: مهمة دار الادخار وبنك التوفير واستثمار الذهب (Savings Bank Task)
     • الخطوة 20: مهمة ترقية القلعة ومباني الموارد والمعسكرات والتسريع (Building Upgrade Task)
     • الخطوة 21: مهمة تدريب فخاخ حصن الحرب التلقائية (War Fortress Traps Task)

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
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from game_client import GameConnection, AccountSession
from core.session_manager import SessionManager
from tasks.port import PortTask
from tasks.train import TrainTask, BUILDING_TROOP_MAP, TYPE_ALIASES
from tasks.pet_patrol import (
    PetPatrolTask, KNOWN_PETS, DEFAULT_PET_ID, DEFAULT_DESTINATION,
    PET_DESTINATIONS, resolve_pet_destination
)
from tasks.city_harvest import CityHarvestTask
from tasks.research import ResearchTask, load_tech_names
from tasks.alliance import AllianceTask
from tasks.territory_expansion import TerritoryExpansionTask
from tasks.shield import ShieldTask, SHIELD_TYPES, DURATION_ALIASES
from tasks.stamina import StaminaTask, STAMINA_POTIONS
from tasks.skills import SkillsTask, SUPPORTED_SKILLS
from tasks.hero_draw import HeroDrawTask
from tasks.tactics_hall import TacticsHallTask, TACTICS_MAP, parse_tactic_choice
from tasks.watermill import WatermillTask, BUILDING_CONFIG as WATERMILL_BUILDING_CONFIG
from tasks.fountain import FountainTask, SUPPORTED_RESOURCES as FOUNTAIN_RESOURCES
from tasks.material_workshop import MaterialWorkshopTask, MATERIALS_MAP as WORKSHOP_MATERIALS_MAP, parse_materials_choice
from tasks.caravan import CaravanTask
from tasks.port_delegate import PortDelegateTask, DELEGATE_TASKS_CONFIG, ISLAND_SHOP_CATALOG, resolve_island_goods_id
from tasks.savings_bank import SavingsBankTask, SAVINGS_PLANS, DEFAULT_DAYS as DEFAULT_SAVINGS_DAYS
from tasks.building import BuildingTask, BUILDING_INFO
from tasks.prestige import PrestigeTask, PRESTIGE_SUBTASKS_ALL, PRESTIGE_SUBTASK_ALIASES
from tasks.march_manager import (
    MarchManagerTask,
    DEFAULT_PRIORITIES as MARCH_DEFAULT_PRIORITIES,
    DEFAULT_TRANSPORT_CONFIG as MARCH_DEFAULT_TRANSPORT,
    DEFAULT_RUINS_CONFIG as MARCH_DEFAULT_RUINS,
    DEFAULT_COMBAT_CONFIG as MARCH_DEFAULT_COMBAT,
    DEFAULT_ELF_CONFIG as MARCH_DEFAULT_ELF,
    DEFAULT_INVADERS_CONFIG as MARCH_DEFAULT_INVADERS,
    DEFAULT_REBELS_CONFIG as MARCH_DEFAULT_REBELS,
    DEFAULT_STRONGHOLD_CONFIG as MARCH_DEFAULT_STRONGHOLD,
    DEFAULT_GATHER_CONFIG as MARCH_DEFAULT_GATHER,
    RESOURCE_SUBTYPE_MAP as MARCH_RESOURCE_SUBTYPE_MAP,
)

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


# ════════════════════════════════════════════════════════════════════════════════════════
# 🔥🔥🔥 [متغيرات وإعدادات المستخدم القادمة من فايربيس — FIREBASE USER CONFIG] 🔥🔥🔥
# ════════════════════════════════════════════════════════════════════════════════════════
# هذا المخطط (Schema) يمثل الحقول والقيم التي سيتم جلبها لاحقاً من قاعدة بيانات Firebase
# لكل حساب مستخدم بناءً على ما يختاره ويحدده المستخدم من لوحة التحكم (Web Dashboard):
# ════════════════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════════════════
# 🕐 نظام الجدولة الزمنية للمهام (Task Scheduling System)
# ════════════════════════════════════════════════════════════════════════════════════════
# يمكن إضافة مفتاح "schedule" لأي مهمة للتحكم في توقيت تشغيلها.
# البوت يعمل في حلقة مستمرة (افتراضياً كل 60 دقيقة) ويفحص الجدول في كل دورة.
#
# الأنواع المدعومة:
#
#  ① times_per_day — عدد مرات التشغيل يومياً (موزعة تلقائياً):
#     "schedule": {"times_per_day": 3}   → كل ~8 ساعات
#     "schedule": {"times_per_day": 2}   → كل ~12 ساعة
#     "schedule": {"times_per_day": 24}  → في كل دورة (إذا كانت الدورة ساعة)
#
#  ② hours — ساعات محددة بالتوقيت المحلي (24h):
#     "schedule": {"hours": [8, 20]}        → مرتين: 8 صباحاً و8 مساءً
#     "schedule": {"hours": [6, 14, 22]}    → ثلاث مرات في اليوم
#
#  ③ active_window — نافذة زمنية للتشغيل (from <= hour < to):
#     "schedule": {"active_window": {"from": 7, "to": 23}}  → بين 7 ص و11 م فقط
#
#  ④ دمج أنواع متعددة معاً:
#     "schedule": {"times_per_day": 3, "active_window": {"from": 7, "to": 23}}
#     → تُشغَّل 3 مرات يومياً لكن فقط بين 7 صباحاً و11 مساءً
#
#  ⑤ بدون "schedule" أو schedule = None → تُشغَّل في كل دورة (الافتراضي)
#
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
        "schedule": {"times_per_day": 4}
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
        "schedule": {"times_per_day": 4}
    },

    # ⚡ 9. مهمة استخدام جرعات وشراء الطاقة (Stamina Task)
    "stamina": {
        "enabled": True,             # تفعيل/تعطيل مهمة استخدام وشراء الطاقة
        "gold_buys": 1,              # عدد مرات شراء الطاقة بالذهب المحدد من المستخدم (0 = مجاني فقط بدون شراء بالذهب)
        "schedule": {"times_per_day": 4}
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

    # 🏛️ 12. مهمة قاعة الاستراتيجيات وتطوير التكتيكات (Tactics Hall)
    "tactics_hall": {
        "enabled": True,             # تفعيل/تعطيل أبحاث قاعة الاستراتيجيات
        "tactic": "القلعة الفارغة",   # اسم أو معرف البحث المستهدف الذي يحدده المستخدم (مثال: "القلعة الفارغة", "قمة الاتقان", "البحث الكامل", 91010000)
        "schedule": {"times_per_day": 2}
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
        "schedule": {"times_per_day": 2}
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
        "schedule": {"times_per_day": 2}
    },

    # 🐪 16. مهمة القافلة التجارية وحراسة الكنز (Caravan / Carriage Escort)
    "caravan": {
        "enabled": True,             # تفعيل/تعطيل إرسال القافلة وحراسة الكنز وجمع الجوائز تلقائياً
        "schedule": {"times_per_day": 5, "active_window": {"from": 7, "to": 23}}
    },

    # ⚓ 18. مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة (Port Delegate & Island Store)
    "port_delegate": {
        "enabled": True,             # تفعيل/تعطيل مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة
        "shop_item": "7",            # المنتج المطلوب شراؤه بالكامل من متجر الجزيرة (رقم 1-7 أو اسمه أو all للكل)
        "schedule": {"times_per_day": 3}
    },

    # 🏦 19. مهمة دار الادخار وبنك التوفير (Savings Bank)
    "savings_bank": {
        "enabled": True,             # تفعيل/تعطيل استثمار الذهب وسحب الأرباح في دار الادخار تلقائياً
        "days": 7,                   # خطة الاستثمار والمدة المختارة بالأيام: 7 (أسبوعية), 15 (نصف شهرية), 30 (شهرية)
        "schedule": {"times_per_day": 1}
    },

    # 🏗️ 20. مهمة ترقية القلعة والمباني والتسريع (Building Upgrade & Castle)
    "building": {
        "enabled": True,                   # تفعيل/تعطيل مهمة البناء برمتها (الخيار الرابع)
        "upgrade_castle": True,            # ترقية القلعة ومتطلباتها (الخيار الأول)
        "speedup_castle": False,           # استخدام التسريع لترقية القلعة من الحقيبة والمجاني (الخيار الثاني)
        "upgrade_support_buildings": True, # ترقية المعسكرات والمراكز الطبية والمزارع وخيم العسكرية (الخيار الثالث)
        "schedule": {"times_per_day": 3}
    },

    # 🎖️ 22. مهمة مهام الهيبة اليومية (Daily Prestige Quests)
    "prestige": {
        "enabled": True,                   # تفعيل/تعطيل مهمة مهام الهيبة اليومية
        "schedule": {
            "hours": [3],                  # تشغيل مرة واحدة في اليوم الساعة 3 فجراً
        },
        "invaders_max_lv": 30,             # الحد الأقصى لمستوى الغزاة المطلوب قتالهم (1-30)
        "subtasks": {                      # تفعيل كل مهمة من مهام الهيبة على حدة
            "smuggler": True,              # متجر المهربين (10 مشتريات بالموارد)
            "invaders": True,              # قتال الغزاة (5 هجمات)
            "stronghold": True,            # احتلال المعاقل / الملاجئ (مرتان)
            "gather": True,                # جمع الموارد الأربعة خارج القلعة بحمولة 25k
            "watermill": True,             # الساقية وتفعيل مباني الموارد
            "train": True,                 # تدريب الجنود (250 من كل نوع مستوى 1)
            "fortress": True,              # حصن الحرب وتدريب الفخاخ
        },
    },

    # 🎖️ 23. مهمة منسق الفيالق والمسيرات الذكي الموحد (March Manager & Orchestrator)
    # يدير كافة مسيرات الخريطة الخارجية للقلعة وفق الأولويات وسعة الفيالق المتاحة (تأتي من فايربيس)
    "march_manager": {
        "enabled": True,                   # تفعيل/تعطيل منسق الفيالق كلياً
        "duration_minutes": 20,            # مدة تشغيل المهمة الإجمالية بالدقائق (ثلث ساعة = 20 دقيقة ككل)
        "max_queues": 6,                   # سعة طوابير الفيالق القصوى للقلعة (5 أو 6)
        "priority_order": [                # قائمة الأولويات المعتمدة بالترتيب
            "transport",                   # 1. مساعدة الموارد
            "ruins",                       # 2. استكشاف الأطلال (مسيرة واحدة حصراً)
            "combat",                      # 3. القتال (عفريت / غزاة / متمردين)
            "stronghold",                  # 4. الهجوم على الملاجئ
            "gold_gather",                 # 5. جمع الذهب في أراضي التحالفات (قبل الأخير)
            "gather",                      # 6. جمع الموارد بالفيالق الشاغرة
        ],
        # [1] إعدادات مساعدة الموارد (Transport)
        "transport": {
            "enabled": False,              # تفعيل مساعدة الموارد
            "target_x": None,              # إحداثي X للقلعة الهدف (مثال: 344)
            "target_y": None,              # إحداثي Y للقلعة الهدف (مثال: 447)
            "resource_ids": [1002, 1003, 1004, 1005],  # الموارد (1002=قمح, 1003=خشب, 1004=حديد, 1005=ألماس)
        },
        # [2] إعدادات استكشاف الأطلال (Ruins) — مسيرة واحدة فقط حصراً
        "ruins": {
            "enabled": True,               # تفعيل استكشاف الأطلال
            "explore_time": 900,           # مدة الاستكشاف بالثواني (900 = 15 دقيقة)
            "formation_id": 1,             # رقم التشكيلة العسكرية (1 إلى 5)
        },
        # [3] إعدادات القتال الشامل (Combat) — يحدد المستخدم خياراً واحداً حصراً (عفريت أو غزاة أو متمردين)
        "combat": {
            "enabled": True,               # تفعيل أولوية القتال
            "choice": "elf",               # الخيار المستهدف: "elf" (عفريت) أو "invaders" (غزاة) أو "rebels" (متمردين)
            "level": 30,                   # مستوى الهدف المطلوب مهاجمته (للغزاة/المتمردين)
            "formation_id": 1,             # رقم تشكيلة القتال (1 إلى 5)
            "count": 1,                    # عدد الهجمات
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
            "count": 1,                    # عدد الهجمات
        },
        "rebels": {
            "enabled": False,              # تفعيل المتمردين
            "level": 30,                   # مستوى المتمردين
            "formation_id": 1,             # رقم التشكيلة
            "count": 1,                    # عدد الهجمات
        },
        # [4] إعدادات الهجوم على المعاقل والملاجئ (Stronghold)
        "stronghold": {
            "enabled": False,              # تفعيل مهاجمة الملاجئ
            "level": 30,                   # مستوى الملجأ المستهدف (1 إلى 30)
            "count": 2,                    # عدد الملاجئ المستهدفة
            "formation_id": 1,             # رقم التشكيلة
        },
        # [5] إعدادات جمع الذهب في أراضي التحالفات (Gold Gather)
        "gold_gather": {
            "enabled": False,              # تفعيل جمع الذهب في أراضي التحالفات
            "locations": [],               # قائمة التحالفات المستهدفة: [{"alliance_tag": "POL", "x": 241, "y": 260}]
            "max_marches": 0,              # 0 = استغلال الفيالق المتاحة
        },
        # [6] إعدادات جمع الموارد الخارجية (Gathering) — تستهلك كافة الفيالق الشاغرة
        "gather": {
            "enabled": True,               # تفعيل جمع الموارد بالفيالق المتبقية حتى الامتلاء
            "res_type": 1,                 # نوع المورد: 1=ذهب, 2=قمح, 3=خشب, 4=حديد, 5=ألماس
            "level": 5,                    # مستوى حقل المورد بالضبط (1 إلى 7)
            "search_range": 100,           # نطاق البحث الأقصى حول القلعة
        },
    },

    # 🪙 24. إعدادات جمع الذهب المتوافقة مع واجهة المستخدم (Firebase Root Fallback)
    "gold_gather": {
        "enabled": False,
        "locations": [],
    }
}


# ════════════════════════════════════════════════════════════════════
#  قاموس وتسميات الحيوانات الأليفة (Pet Aliases)
# ════════════════════════════════════════════════════════════════════

PET_ALIASES: Dict[str, int] = {
    # الغزال
    "غزال": 1261, "الغزال": 1261, "gazelle": 1261, "1261": 1261,
    # الأسد
    "اسد": 1262, "أسد": 1262, "الاسد": 1262, "الأسد": 1262, "lion": 1262, "1262": 1262,
    # الصقر
    "صقر": 1263, "الصقر": 1263, "falcon": 1263, "1263": 1263,
    # الذئب
    "ذئب": 1264, "الذئب": 1264, "wolf": 1264, "1264": 1264,
    # النمر / الفهد
    "نمر": 1265, "فهد": 1265, "النمر": 1265, "الفهد": 1265, "leopard": 1265, "1265": 1265,
    # الدب
    "دب": 1266, "الدب": 1266, "bear": 1266, "1266": 1266,
    # الفيل
    "فيل": 1267, "الفيل": 1267, "elephant": 1267, "1267": 1267,
    # وحيد القرن
    "وحيد القرن": 1268, "rhino": 1268, "1268": 1268,
    # الثور البري
    "ثور": 1269, "الثور": 1269, "bull": 1269, "1269": 1269,
    # الكلب
    "كلب": 1270, "الكلب": 1270, "كانغال": 1270, "dog": 1270, "1270": 1270,
    # النمر الناري
    "نمر ناري": 1271, "fire tiger": 1271, "1271": 1271,
    # الثعبان الملكي
    "ثعبان": 1272, "الثعبان": 1272, "افعى": 1272, "snake": 1272, "1272": 1272,
    # الجريفين
    "جريفين": 1273, "الجريفين": 1273, "griffin": 1273, "1273": 1273,
    # التنين
    "تنين": 1274, "التنين": 1274, "dragon": 1274, "1274": 1274,
    # فينيكس
    "فينيكس": 1275, "طائر الفينيق": 1275, "عنقاء": 1275, "العنقاء": 1275, "phoenix": 1275, "1275": 1275,
}

def resolve_pet_id(pet_input: Union[str, int]) -> int:
    """تحويل اسم الحيوان المدخل بالعربية أو الإنجليزية أو المعرف الرقمي إلى ID صحيح."""
    if isinstance(pet_input, int):
        return pet_input
    key = str(pet_input).strip().lower()
    if key.isdigit():
        return int(key)
    return PET_ALIASES.get(key, DEFAULT_PET_ID)


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

        # جرعات الطاقة المتوفرة في الحقيبة
        self.stamina_potions: Dict[int, int] = {300401: 0, 300402: 0, 300403: 0}

        # حالة المهارات التلقائية (Skills)
        self.skills_status: List[Dict[str, Any]] = []

        # سحوبات وتجنيد الأبطال اليومية المجانية
        self.hero_draw_ready_count: int = 0

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

        # البيانات الخام الكاملة
        self.raw_city: List[Dict[str, Any]] = []
        self.raw_lord: Dict[str, Any] = {}


# ════════════════════════════════════════════════════════════════════
#  كلاس الجدولة الزمنية للمهام (BotScheduler)
# ════════════════════════════════════════════════════════════════════

class BotScheduler:
    """
    محرك الجدولة الزمنية للمهام — مصمم للكفاءة القصوى مع آلاف الحسابات المتزامنة.

    ⚡ تصميم خفيف الوزن (مناسب لـ 1000+ حساب):
      - Dict بسيط بدون threads أو background tasks أو timers
      - يستخدم asyncio.sleep() للانتظار — لا يستهلك CPU إطلاقاً
      - يحفظ الحالة في ملف JSON صغير (<1KB) لكل حساب منفصلاً
      - جميع العمليات O(1) — لا عمليات بحث أو loop ثقيلة

    أنواع الجدولة المدعومة (قابلة للدمج):
      ① times_per_day  : عدد مرات التشغيل يومياً (كل N ساعة تلقائياً)
      ② hours          : قائمة ساعات تشغيل محددة بالتوقيت المحلي [8, 14, 20]
      ③ active_window  : نافذة زمنية {"from": 7, "to": 23} — 7 ص إلى 11 م
      ④ بدون schedule  : يُشغَّل في كل دورة (السلوك الافتراضي)

    مثال دمج متعدد:
      {"times_per_day": 3, "active_window": {"from": 7, "to": 23}}
      → تُشغَّل 3 مرات يومياً لكن فقط بين 7 صباحاً و11 مساءً
    """

    def __init__(
        self,
        config: Dict[str, Any],
        state_file: Optional[str] = None,
    ) -> None:
        # استخراج إعدادات الجدولة فقط من المهام التي تحتوي عليها
        self._schedules: Dict[str, Dict[str, Any]] = {}
        for task_key, task_cfg in config.items():
            if isinstance(task_cfg, dict):
                sched = task_cfg.get("schedule")
                if sched and isinstance(sched, dict):
                    self._schedules[task_key] = sched

        # آخر وقت تشغيل لكل مهمة: {task_key: unix_timestamp}
        self._last_run: Dict[str, float] = {}

        # ملف حفظ الحالة لاستمراريتها عند إعادة تشغيل البوت
        self._state_file = state_file
        self._load_state()

    # ── حفظ وتحميل الحالة ──────────────────────────────────────────

    def _load_state(self) -> None:
        """تحميل آخر وقت تشغيل لكل مهمة من ملف الحالة المحفوظ."""
        if not self._state_file or not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._last_run = {k: float(v) for k, v in data.items()}
        except Exception:
            self._last_run = {}  # إذا تلف الملف نبدأ من جديد بأمان

    def save_state(self) -> None:
        """حفظ آخر وقت تشغيل لكل مهمة في ملف JSON (خفيف جداً < 1KB)."""
        if not self._state_file:
            return
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(self._last_run, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # فشل الحفظ لا يوقف البوت

    # ── منطق قرار التشغيل ─────────────────────────────────────────

    def should_run(self, task_key: str, now: Optional[datetime] = None) -> bool:
        """
        هل يجب تشغيل هذه المهمة الآن؟

        أولوية الفحص:
          1. active_window → هل الوقت ضمن النافذة الزمنية المسموحة؟
          2. hours         → هل الساعة الحالية مُدرجة ولم تُشغَّل فيها اليوم؟
          3. times_per_day → هل مضت المدة الكافية منذ آخر تشغيل؟
          4. لا إعدادات   → True دائماً (في كل دورة)
        """
        sched = self._schedules.get(task_key)
        if not sched:
            return True  # لا جدول محدد = تشغيل في كل دورة

        now = now or datetime.now()

        # استثناء ذكي لمهام الهيبة: إذا لم تكتمل كافة مهامها اليوم، تستمر في العمل في كل دورة حتى تكتمل بنسبة 100%
        if task_key == "prestige":
            last_ts = self._last_run.get(task_key, 0.0)
            if last_ts > 0.0:
                last_dt = datetime.fromtimestamp(last_ts)
                if last_dt.date() == now.date():
                    return False  # اكتملت كافة مهام الهيبة اليوم بنجاح → تخطّي
            return True  # لم تكتمل بعد لليوم → تشغيل في هذه الدورة

        # ① فحص النافذة الزمنية (active_window) — يمنع التشغيل خارجها
        active_window = sched.get("active_window")
        if active_window and isinstance(active_window, dict):
            from_h = int(active_window.get("from", 0))
            to_h   = int(active_window.get("to",   24))
            if not (from_h <= now.hour < to_h):
                return False  # خارج النافذة الزمنية المسموحة

        # ② فحص الساعات المحددة (hours)
        # المنطق: نفّذ في أول دورة تأتي بعد مرور الساعة المحددة (مرة لكل فترة يومياً)
        # hours=[3]     → تشغيل في أول دورة تبدأ ≥ 03:00 ولم تُنفذ اليوم بعد 03:00
        # hours=[3, 15] → تشغيلتان: الأولى بعد 03:00، الثانية بعد 15:00
        hours = sched.get("hours")
        if hours and isinstance(hours, list):
            sorted_hours = sorted(hours)
            now_date = now.date()
            now_hour = now.hour

            # آخر ساعة هدف مرّت (≤ الساعة الحالية) = الفترة الزمنية الحالية
            passed_hours = [h for h in sorted_hours if now_hour >= h]
            if not passed_hours:
                return False  # لم تحن أي ساعة هدف بعد → انتظار

            current_slot_hour = max(passed_hours)

            # هل تم التشغيل بالفعل في هذه الفترة اليوم؟
            last_ts = self._last_run.get(task_key, 0.0)
            if last_ts > 0.0:
                last_dt = datetime.fromtimestamp(last_ts)
                if last_dt.date() == now_date and last_dt.hour >= current_slot_hour:
                    return False  # نُفذت في هذه الفترة → تخطّي
            return True  # حانت الفترة ولم تُنفذ → شغّل


        # ③ فحص عدد مرات التشغيل يومياً (times_per_day)
        times_per_day = sched.get("times_per_day")
        if times_per_day and isinstance(times_per_day, (int, float)) and float(times_per_day) > 0:
            interval_secs = 86400.0 / float(times_per_day)
            last_ts  = self._last_run.get(task_key, 0.0)
            elapsed  = now.timestamp() - last_ts
            return elapsed >= interval_secs

        # الجدول موجود لكن لا شروط واضحة → شغّل دائماً
        return True

    def mark_ran(self, task_key: str, now: Optional[datetime] = None) -> None:
        """تسجيل أن المهمة تم تنفيذها بنجاح الآن."""
        self._last_run[task_key] = (now or datetime.now()).timestamp()

    def seconds_until_next_any_task(self, now: Optional[datetime] = None) -> float:
        """
        كم ثانية حتى تستحق أي مهمة مُجدوَلة التشغيل القادم؟
        يُستخدم لتحديد الانتظار المُثلى بين دورات loop mode.
        إذا لا توجد مهام مُجدوَلة أو حان وقتها فوراً: يعيد 0.
        """
        if not self._schedules:
            return 0.0

        now       = now or datetime.now()
        min_wait  = float("inf")
        now_ts    = now.timestamp()

        for task_key, sched in self._schedules.items():
            # times_per_day: حساب الوقت المتبقي حتى الدورة القادمة
            tpd = sched.get("times_per_day")
            if tpd and isinstance(tpd, (int, float)) and float(tpd) > 0:
                interval = 86400.0 / float(tpd)
                last_ts  = self._last_run.get(task_key, 0.0)
                wait     = max(0.0, interval - (now_ts - last_ts))
                min_wait = min(min_wait, wait)

            # hours: حساب الوقت حتى أقرب ساعة تشغيل قادمة
            hours = sched.get("hours")
            if hours and isinstance(hours, list):
                for h in sorted(hours):
                    candidate = now.replace(hour=h, minute=0, second=0, microsecond=0)
                    if candidate <= now:
                        candidate += timedelta(days=1)
                    wait = (candidate - now).total_seconds()
                    min_wait = min(min_wait, wait)

        return 0.0 if min_wait == float("inf") else min_wait

    def summary(self) -> str:
        """ملخص نصي لحالة الجدول (للـ logging)."""
        if not self._schedules:
            return "لا توجد مهام مُجدوَلة — جميعها تعمل في كل دورة"
        lines = [f"  📅 مهام مُجدوَلة ({len(self._schedules)} مهمة):"]
        for key, sched in self._schedules.items():
            last_ts = self._last_run.get(key, 0.0)
            last_str = datetime.fromtimestamp(last_ts).strftime("%H:%M") if last_ts > 0 else "لم تُشغَّل بعد"
            lines.append(f"     • {key}: {sched} | آخر تشغيل: {last_str}")
        return "\n".join(lines)


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

        # دمج الإعدادات الافتراضية مع إعدادات المستخدم القادمة من Firebase
        self.config = self._build_default_config(config or {})

        # إعدادات إعادة الاتصال التلقائي عند دخول شخص آخر للحساب
        self.reconnect_wait_seconds = int(reconnect_wait_seconds)
        self.max_reconnect_attempts = int(max_reconnect_attempts)
        self._disconnected_event = asyncio.Event()
        self._last_kick_reason: str = ""

        # ── مدير الجدولة الزمنية للمهام ─────────────────────────────
        # ملف حالة خفيف لكل حساب منفصلاً (يضمن العزل الكامل بين 1000 حساب)
        _safe_email = self.email.replace("@", "_").replace(".", "_").replace("+", "_")
        _sched_file = os.path.join(_ROOT_DIR, f".sched_{_safe_email}.json")
        self.scheduler = BotScheduler(self.config, state_file=_sched_file)

    def _update_bot_conn_state(self, conn_state: str, message: str = "", next_run_time: Optional[str] = None) -> None:
        """إبلاغ لوحة التحكم وFirebase بحالة اتصال اللعبة الفعلية (دخول، انقطاع، إعادة اتصال، انتظار)."""
        nr_arg = f" next_run_time={next_run_time}" if next_run_time else ""
        event_line = f"[FIREBASE_EVENT] conn_state={conn_state} message={message}{nr_arg}"
        # Thread Pool: توجيه عبر log_callback / CLI: print() مباشرة
        if self._log_callback:
            self._log_callback(event_line)
        else:
            print(event_line, flush=True)

        # 1. تحديث كاش قاعدة البيانات المحلية SQLite فوراً
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
        except Exception:
            pass

        if not getattr(self, "user_id", None) or not getattr(self, "castle_id", None):
            return
        def _bg_update():
            try:
                import firebase_admin
                from firebase_admin import credentials, firestore as fb_fs
                sak = os.path.join(_ROOT_DIR, "firebase_service_account.json")
                if not firebase_admin._apps and os.path.exists(sak):
                    firebase_admin.initialize_app(credentials.Certificate(sak))
                if firebase_admin._apps:
                    db = fb_fs.client()
                    ref = db.collection("users").document(self.user_id).collection("castles").document(self.castle_id)
                    from datetime import timezone
                    now_iso = datetime.now(timezone.utc).isoformat()
                    doc_data = {
                        "bot_status.conn_state":   conn_state,
                        "bot_status.conn_message": message,
                        "bot_status.conn_updated": now_iso,
                    }
                    if conn_state in ("connected", "reconnecting", "disconnected", "waiting"):
                        doc_data["bot_status.state"] = "running"
                        if conn_state == "connected":
                            doc_data["bot_status.last_run_time"] = now_iso
                        elif conn_state == "waiting" and next_run_time:
                            doc_data["bot_status.next_run_time"] = next_run_time
                    elif conn_state == "idle":
                        doc_data["bot_status.state"] = "idle"
                        if message:
                            doc_data["bot_status.last_run_message"] = message
                    ref.update(doc_data)
            except Exception:
                pass
        import threading
        threading.Thread(target=_bg_update, daemon=True, name=f"bm-fb-{conn_state}").start()

    def check_subscription_validity(self) -> Tuple[bool, str]:
        """فحص صلاحية اشتراك المستخدم وحالة الحظر من Firestore."""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore as fb_fs
            sak = os.path.join(_ROOT_DIR, "firebase_service_account.json")
            if not firebase_admin._apps and os.path.exists(sak):
                firebase_admin.initialize_app(credentials.Certificate(sak))
            if not firebase_admin._apps:
                return True, "Firebase غير مهيأ"

            db = fb_fs.client()
            user_doc = None
            if getattr(self, "user_id", None):
                user_snap = db.collection("users").document(self.user_id).get()
                if user_snap.exists:
                    user_doc = user_snap.to_dict() or {}
            else:
                try:
                    castles = db.collection_group("castles").where("email", "==", self.email.strip().lower()).limit(1).stream()
                    for c in castles:
                        self.castle_id = c.id
                        u_ref = c.reference.parent.parent
                        if u_ref:
                            self.user_id = u_ref.id
                            u_snap = u_ref.get()
                            if u_snap.exists:
                                user_doc = u_snap.to_dict() or {}
                        break
                except Exception:
                    for u in db.collection("users").stream():
                        for c in u.reference.collection("castles").where("email", "==", self.email.strip().lower()).limit(1).stream():
                            self.castle_id = c.id
                            self.user_id = u.id
                            user_doc = u.to_dict() or {}
                            break
                        if user_doc:
                            break

            if not user_doc:
                return True, "لم يتم العثور على مستند المستخدم"

            from core.firebase_schema import check_user_subscription
            return check_user_subscription(user_doc)
        except Exception as e:
            log.warning(f"⚠️ تنبيه أثناء التحقق من صلاحية الاشتراك: {e}")
            return True, "تعذر التحقق"

    def sync_castle_resources(self) -> None:
        """تحديث بيانات موارد ومعلومات القلعة في بداية كل دورة في Firebase."""
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
            except Exception:
                pass

            # تحديث Firebase في الخلفية
            def _bg_sync():
                try:
                    import firebase_admin
                    from firebase_admin import credentials, firestore as fb_fs
                    try:
                        firebase_admin.get_app()
                    except ValueError:
                        sak = os.path.join(_ROOT_DIR, "firebase_service_account.json")
                        if os.path.exists(sak):
                            firebase_admin.initialize_app(credentials.Certificate(sak))

                    if firebase_admin._apps:
                        db = fb_fs.client()
                        target_ref = None
                        if getattr(self, "user_id", None) and getattr(self, "castle_id", None):
                            target_ref = db.collection("users").document(self.user_id).collection("castles").document(self.castle_id)
                        else:
                            for u in db.collection("users").stream():
                                for c in u.reference.collection("castles").where("email", "==", self.email.strip().lower()).limit(1).stream():
                                    target_ref = c.reference
                                    self.user_id = u.id
                                    self.castle_id = c.id
                                    break
                                if target_ref:
                                    break
                        if target_ref:
                            update_dict = {}
                            for k, v in res_data.items():
                                update_dict[f"resources.{k}"] = v
                            for k, v in cinfo_data.items():
                                update_dict[f"castle_info.{k}"] = v
                            target_ref.update(update_dict)
                            log.info(f"💾 [Firebase Sync] تم تحديث موارد وبيانات القلعة في بداية الدورة بنجاح ✅")
                except Exception as ex:
                    log.warning(f"⚠️ [Firebase Sync Warning]: {ex}")

            import threading
            threading.Thread(target=_bg_sync, daemon=True, name=f"res-sync-{self.email[:8]}").start()

        except Exception as e:
            log.warning(f"⚠️ تنبيه أثناء استخراج ومزامنة الموارد: {e}")

    def _build_default_config(self, user_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """بناء قاموس الإعدادات بدمج إعدادات المستخدم القادمة من Firebase مع المخطط الافتراضي.
        ملاحظة: مفتاح 'schedule' محمي دائماً ويُؤخذ من DEFAULT_FIREBASE_USER_CONFIG فقط
        ولا يمكن لـ Firebase تجاوزه أو تغييره."""
        cfg = copy.deepcopy(DEFAULT_FIREBASE_USER_CONFIG)
        for section, values in (user_cfg or {}).items():
            if section in cfg and isinstance(values, dict) and isinstance(cfg[section], dict):
                # ← نحذف 'schedule' من قيم Firebase لحماية جدول التنفيذ المحلي
                firebase_values = {k: v for k, v in values.items() if k != 'schedule'}
                cfg[section].update(firebase_values)
            else:
                # إذا كان القسم كاملاً قادماً من Firebase، نحافظ على schedule المحلي
                if isinstance(values, dict):
                    local_schedule = cfg.get(section, {}).get('schedule') if isinstance(cfg.get(section), dict) else None
                    cfg[section] = {k: v for k, v in values.items() if k != 'schedule'}
                    if local_schedule is not None:
                        cfg[section]['schedule'] = local_schedule
                else:
                    cfg[section] = values
        return cfg

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
        display_reason = reason or self.get_disconnect_reason()
        if not self._log_callback:
            print("\n" + "!" * 70)
        log.warning(f"⚠️ [انقطاع الاتصال] تم رصد انقطاع الاتصال بالحساب (السبب: {display_reason})!")
        log.warning(f"⏳ سيتوقف البوت مؤقتاً وينتظر {self.reconnect_wait_seconds} ثانية...")
        if not self._log_callback:
            print("!" * 70 + "\n")

        self._update_bot_conn_state("disconnected", f"تم تسجيل الدخول من جهاز آخر: {display_reason}")

        for attempt in range(1, self.max_reconnect_attempts + 1):
            log.info(f"⏳ [المحاولة {attempt}/{self.max_reconnect_attempts}] انتظار {self.reconnect_wait_seconds} ثانية (دقيقة واحدة)...")
            self._update_bot_conn_state("reconnecting", f"جاري انتظار إعادة الاتصال (المحاولة {attempt}/{self.max_reconnect_attempts})...")
            wait_time = self.reconnect_wait_seconds
            while wait_time > 0:
                if wait_time in (60, 45, 30, 15, 5):
                    log.info(f"⏳ متبقي على إعادة محاولة الدخول: {wait_time} ثانية...")
                step_sleep = 5 if wait_time >= 5 else wait_time
                await asyncio.sleep(step_sleep)
                wait_time -= step_sleep

            log.info(f"🔄 جاري محاولة تسجيل الدخول الآن واستئناف المهام (المحاولة {attempt}/{self.max_reconnect_attempts})...")

            # إغلاق الاتصال القديم بأمان
            if self.conn:
                try:
                    await self.conn.close()
                except Exception:
                    pass

            self._disconnected_event.clear()
            connected = await self.login_and_connect()
            if connected:
                try:
                    await self.perform_comprehensive_query()
                except Exception as e:
                    log.warning(f"⚠️ تنبيه أثناء تحديث بيانات الحساب بعد الدخول: {e}")
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
        log.info(f"🔐 [تسجيل الدخول] بدء الاتصال بالحساب: {self.email}...")
        self._disconnected_event.clear()
        self._last_kick_reason = ""

        def _on_disconnect(reason: str):
            self._disconnected_event.set()
            self._last_kick_reason = reason or "other_device"
            log.warning(f"⚠️ [تنبيه السيرفر] انقطع اتصال الحساب {self.email} (السبب: {self._last_kick_reason})")

        self.conn = GameConnection(self.account, on_disconnect=_on_disconnect)
        ok = await self.conn.connect()
        if not ok and self.user_id and self.castle_id:
            log.warning(f"⚠️ [تسجيل الدخول] فشل الاتصال بالجلسة الحالية لـ {self.email}. جاري تجديد الجلسة تلقائياً بكلمة المرور...")
            sm = SessionManager()
            fresh_acc = sm.refresh_session(self.email, user_id=self.user_id, castle_id=self.castle_id)
            if fresh_acc:
                self.account = fresh_acc
                self.conn = GameConnection(self.account, on_disconnect=_on_disconnect)
                ok = await self.conn.connect()

        if not ok:
            log.error(f"❌ [تسجيل الدخول] فشل الاتصال بالحساب {self.email}!")
            return False

        # انتظار وصول حزم التهيئة الأولية للبث (init_data)
        log.info("⏳ انتظار مزامنة الحزم الأولية من السيرفر...")
        for _ in range(15):
            await asyncio.sleep(0.3)
            if len(self.conn.init_data) > 0:
                break

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
                ctx.alliance_name = str(a_info.get("name", "بدون تحالف"))
                ctx.alliance_tag = str(a_info.get("tag", ""))
            elif "memberinfo" in alliance_ctrl:
                minfo = alliance_ctrl.get("memberinfo", {}).get("minfo", {})
                if isinstance(minfo, dict) and minfo.get("aid"):
                    ctx.alliance_id = int(minfo.get("aid", 0))

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

        # 9. فحص دروع السلام وجرعات الطاقة في الحقيبة (backpackCtrl)
        bp_ctrl = self.conn.init_data.get("backpackCtrl", {})
        if isinstance(bp_ctrl, dict):
            ctx.shield_backpack_counts["8h"] = int(bp_ctrl.get("300701", {}).get("count", 0))
            ctx.shield_backpack_counts["24h"] = int(bp_ctrl.get("300702", {}).get("count", 0))
            ctx.shield_backpack_counts["3d"] = int(bp_ctrl.get("300703", {}).get("count", 0))
            for pid in (300401, 300402, 300403):
                ctx.stamina_potions[pid] = int(bp_ctrl.get(str(pid), {}).get("count", 0))

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
        print(f"⚡ جرعات الطاقة في الحقيبة: {total_pots} جرعة (🧪 {p10} جرعة +10 | 🧪 {p50} جرعة +50 | 🧪 {p100} جرعة +100)")
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
        print("═" * 72 + "\n")


    # ════════════════════════════════════════════════════════════════════════════════════════
    # 🌟🌟🌟 [منطقة قائمة المهام الرئيسية — TASK EXECUTION PIPELINE] 🌟🌟🌟
    # ════════════════════════════════════════════════════════════════════════════════════════
    # هنا يمكنك التدخل والتعديل بحرية وسهولة تامة:
    #   1. تغيير الترتيب: قدم أو أخر أي سطر في القائمة أدناه لتغيير تسلسل التنفيذ فوراً.
    #   2. تعطيل مهمة: ضع علامة # قبل السطر لتعطيلها بالكامل.
    #   3. إضافة مهمة جديدة: أضف سطراً جديداً: ("اسم المهمة", self.step_X_...)
    # ════════════════════════════════════════════════════════════════════════════════════════

    async def execute_task_pipeline(self) -> Dict[str, Any]:
        """تنفيذ سلسلة المهام بالترتيب المحدد وفق الجدول الزمني مع استئناف ذكي عند انقطاع الاتصال."""
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
            ("🏛️ قاعة الاستراتيجيات (Tactics Hall)",             self.step_12_tactics_hall_task,        "tactics_hall"),
            ("💧 طاحونة الماء (Watermill Boost)",                self.step_13_watermill_task,           "watermill"),
            ("⛲ نافورة الأمنيات (Trevi Fountain)",              self.step_14_fountain_task,            "fountain"),
            ("🔨 ورشة المواد (Material Workshop)",               self.step_15_material_workshop_task,   "material_workshop"),
            ("🐪 القافلة وحراسة الكنز (Caravan Task)",           self.step_16_caravan_task,             "caravan"),
            ("⚓ الميناء العسكري (Port Delegate)",               self.step_18_port_delegate_task,       "port_delegate"),
            ("🏦 دار الادخار (Savings Bank)",                   self.step_19_savings_bank_task,        "savings_bank"),
            ("🏗️ ترقية المباني (Building Upgrade)",             self.step_20_building_task,            "building"),
            ("🎖️ مهام الهيبة اليومية (Prestige Quests)",        self.step_22_prestige_task,            "prestige"),
            ("🎖️ منسق الفيالق والمسيرات (March Orchestrator)", self.step_23_march_manager_task,     "march_manager"),
            # ──────────────────────────────────────────────────────────────────────────────
            # لإضافة مهمة جديدة أضف سطراً: ("📌 اسم المهمة", self.step_N_..., "config_key")
            # ──────────────────────────────────────────────────────────────────────────────
        ]

        step_idx = 0
        while step_idx < len(pipeline):
            step_name, step_func, task_key = pipeline[step_idx]

            # ── فحص الجدول الزمني ─────────────────────────────────────────
            if not self.ignore_schedule and not self.scheduler.should_run(task_key, now):
                log.info(f"⏭️  [{step_name}] — متجاوزة (ليس وقتها بحسب الجدول)")
                results[step_name] = {"skipped": True, "reason": "schedule"}
                step_idx += 1
                continue

            # 1. التحقق من سلامة الاتصال قبل بدء المهمة
            if not self.is_connection_alive():
                kick_reason = self.get_disconnect_reason()
                log.warning(f"⚠️ تم رصد انقطاع الاتصال قبل بدء المهمة [{step_name}] (السبب: {kick_reason})")
                reconnected = await self.wait_and_reconnect(kick_reason)
                if not reconnected:
                    log.error(f"❌ تعذر استعادة الاتصال بعد استنفاد محاولات الدخول. إيقاف السلسلة عند: {step_name}")
                    results[step_name] = {"success": False, "error": "انقطاع الاتصال وتعذر إعادة الدخول"}
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

            # تحديد مهلة الأمان للمهمة: المهام العادية 300ث (5د)، ومهمة منسق الفيالق تستمر حسب مدتها (افتراضياً 20د)
            task_timeout = 300
            if task_key == "march_manager":
                mm_dur = float(self.config.get("march_manager", {}).get("duration_minutes", 20))
                task_timeout = max(300, int((mm_dur * 60) + 180))

            done, pending = await asyncio.wait(
                [step_task, disconnect_waiter],
                timeout=task_timeout,
                return_when=asyncio.FIRST_COMPLETED
            )

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
                else:
                    self.scheduler.mark_ran(task_key, now)  # تسجيل وقت الاكتمال النهائي في الجدول
            else:
                self.scheduler.mark_ran(task_key, now)  # تسجيل وقت التشغيل في الجدول
            step_idx += 1
            await asyncio.sleep(1.5)  # مهلة أمان قصيرة بين المهام

        return results

    # ─────────────────────────────────────────────────────────────────
    #  دوال تفاصيل كل مهمة على حدة (Individual Task Handlers)
    # ─────────────────────────────────────────────────────────────────

    # [1] مهمة حصد مزارع المدينة
    async def step_1_city_harvest_task(self) -> Dict[str, Any]:
        """فحص وحصد جميع محاصيل مزارع القمح والخشب والحديد والألماس داخل المدينة."""
        h_cfg = self.config.get("city_harvest", {})
        if not bool(h_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي حصد مزارع المدينة بناءً على رغبة المستخدم (city_harvest.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

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
        res_pet = await pet_task.run()

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
        """استهلاك جرعات الطاقة المجانية من الحقيبة وتنفيذ شراء الطاقة بالذهب بعدد المرات المحدد من المستخدم."""
        stamina_cfg = self.config.get("stamina", {})
        if not bool(stamina_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الطاقة بناءً على رغبة المستخدم (stamina.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        gold_buys = int(stamina_cfg.get("gold_buys", stamina_cfg.get("gold", 0)))
        log.info(f"⚡ بدء مهمة الطاقة (استهلاك الجرعات المجانية + شراء بالذهب: {gold_buys} مرة)...")

        task = StaminaTask(self.conn, {
            "use_free": True,
            "gold_buys": gold_buys,
            "gold": gold_buys
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
        allow_gold = bool(fountain_cfg.get("allow_gold", fountain_cfg.get("use_gold", False))) and gold_times > 0
        if not allow_gold:
            gold_times = 0

        res_display = "، ".join(res_list) if isinstance(res_list, list) else str(res_list)
        log.info(f"⛲ بدء مهمة نافورة الأمنيات (الموارد: [{res_display}] | السماح بالشراء بالذهب: {'نعم' if allow_gold else 'لا'} | عدد مرات الذهب: {gold_times})...")

        task_cfg = {
            "resources": res_list,
            "use_gold": allow_gold,
            "allow_gold": allow_gold,
            "gold_times": gold_times,
            "max_gold": fountain_cfg.get("max_gold", 200)
        }

        task = FountainTask(self.conn, task_cfg)
        res = await task.run()

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
        تنفيذ مهمة مهام الهيبة اليومية (Daily Prestige Quests):
          - متجر المهربين بالموارد العادية فقط بدون ذهب.
          - قتال الغزاة حتى الحد الأقصى للمستوى الذي حدده المستخدم (invaders_max_lv).
          - مهاجمة المعاقل / الملاجئ.
          - جمع الموارد الأربعة خارج القلعة بحمولة 25,000 مورد.
          - الساقية وتفعيل جميع مباني إنتاج الموارد.
          - تدريب الجنود (250 من كل نوع مستوى 1).
          - حصن الحرب وتدريب الفخاخ.
        تتيح للمستخدم تحديد كل مهمة فرعية على حدة (subtasks) والحد الأقصى لمستوى الغزاة.
        مجدولة افتراضياً للعمل مرة واحدة يومياً الساعة 3 فجراً (schedule: {"hours": [3]}).
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
        mm_cfg = copy.deepcopy(self.config.get("march_manager", {}))
        if not bool(mm_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة منسق الفيالق بناءً على رغبة المستخدم (march_manager.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # دمج إعدادات gold_gather المحفوظة من واجهة المستخدم (في جذر config أو داخل march_manager)
        if "gold_gather" in self.config and isinstance(self.config["gold_gather"], dict):
            root_gg = self.config["gold_gather"]
            if "gold_gather" not in mm_cfg or not isinstance(mm_cfg["gold_gather"], dict):
                mm_cfg["gold_gather"] = copy.deepcopy(root_gg)
            else:
                mm_cfg["gold_gather"].update(copy.deepcopy(root_gg))

        # تمرير إعدادات مهام الهيبة للربط والتنسيق التكتيكي الذكي
        mm_cfg["_prestige_config"] = copy.deepcopy(self.config.get("prestige", {}))

        # تمرير إشارة الإيقاف الخارجية والمدة المحددة ومسار الـ logs (افتراضياً 20 دقيقة ككل)
        mm_cfg["_external_stop_event"] = self._stop_event
        mm_cfg["_log_callback"] = self._log_callback
        if "duration_minutes" not in mm_cfg:
            mm_cfg["duration_minutes"] = 20

        log.info("🎖️ بدء مهمة منسق الفيالق والمسيرات الذكي (March Orchestrator)...")
        task_cfg = mm_cfg
        task = MarchManagerTask(self.conn, task_cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة مهمة منسق الفيالق: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة منسق الفيالق: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    # ─────────────────────────────────────────────────────────────────
    #  دورة التشغيل الواحدة (Single Run Lifecycle)
    # ─────────────────────────────────────────────────────────────────
    async def run_once(self) -> Dict[str, Any]:
        """
        تشغيل دورة واحدة كاملة:
          0. التحقق من صلاحية الاشتراك وحظر الحساب.
          1. تسجيل الدخول.
          2. الاستعلام الشامل (مع إعادة المحاولة عند انقطاع الاتصال).
          3. تنفيذ سلسلة المهام بالترتيب مع فحص الجدول الزمني لكل مهمة.
          4. إغلاق الاتصال بأمان وإعادة النتائج.
        """
        # 0. التحقق من صلاحية الاشتراك وحظر الحساب
        valid, reason = self.check_subscription_validity()
        if not valid:
            log.warning(f"🛑 [إيقاف التشغيل] {reason} — لن يتم تشغيل البوت للحساب {self.email}!")
            self._update_bot_conn_state("idle", f"متوقف: {reason}")
            return {"success": False, "error": reason}

        try:
            # 1. تسجيل الدخول
            connected = await self.login_and_connect()
            if not connected:
                return {"success": False, "error": "فشل الاتصال والمصادقة"}

            # 2. الاستعلام الشامل
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

            # 2.5 تحديث بيانات وموارد القلعة في بداية الدورة مباشرة
            try:
                self.sync_castle_resources()
            except Exception as e:
                log.warning(f"⚠️ تنبيه أثناء تحديث موارد القلعة في بداية الدورة: {e}")

            # 3. تنفيذ سلسلة المهام
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
        log.info(self.scheduler.summary())

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
            finally:
                # حفظ حالة الجدول بعد كل دورة (ملف صغير < 1KB)
                self.scheduler.save_state()

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



# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر من سطر الأوامر (CLI Entry Point)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

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
    parser.add_argument("--firebase-user-id",    dest="firebase_user_id",    default=None, help="معرف المستخدم في Firebase (للإبلاغ عن الحالة)")
    parser.add_argument("--firebase-castle-id",  dest="firebase_castle_id",  default=None, help="معرف القلعة في Firebase (للإبلاغ عن الحالة)")
    parser.add_argument(
        "--reconnect-wait",
        type=int,
        default=60,
        help="مدة الانتظار بالثواني عند انقطاع الاتصال بسبب دخول شخص آخر للحساب [افتراضي: 60 ثانية (دقيقة واحدة)]"
    )

    # ── خيارات وضع التشغيل المستمر (Loop Mode) ─────────────────────
    parser.add_argument(
        "--loop",
        action="store_true",
        default=False,
        help="تشغيل البوت في حلقة مستمرة لا تنتهي — ينفذ دورة كاملة ثم ينتظر المدة المحددة [افتراضي: معطل]"
    )
    parser.add_argument(
        "--loop-interval",
        type=int,
        default=60,
        dest="loop_interval",
        metavar="MINUTES",
        help="المدة بين الدورات بالدقائق في وضع الحلقة الدائمة [افتراضي: 60 دقيقة]"
    )

    # خيارات مهمة حصد مزارع المدينة
    parser.add_argument("--harvest", dest="harvest", action="store_true", default=True, help="تفعيل حصد جميع مزارع موارد المدينة [افتراضي: تفعيل]")
    parser.add_argument("--no-harvest", dest="harvest", action="store_false", help="تعطيل حصد مزارع المدينة")
    parser.add_argument("--harvest-types", default="all", help="أنواع المزارع المطلوب حصدها (مثال: 'قمح,حديد' أو 'all') [افتراضي: الكل]")

    # خيارات مهمة أبحاث الأكاديمية والعلوم
    parser.add_argument("--research", dest="research", action="store_true", default=True, help="تفعيل مهمة أبحاث الأكاديمية [افتراضي: تفعيل]")
    parser.add_argument("--no-research", dest="research", action="store_false", help="تعطيل مهمة أبحاث الأكاديمية")
    parser.add_argument(
        "--research-tree",
        default="defense",
        choices=["defense", "military", "resources", "city", "advanced", "war", "all"],
        help="شجرة الأبحاث المستهدفة (defense, military, resources, city, all) [افتراضي: defense]"
    )
    parser.add_argument(
        "--tech-id",
        default=None,
        help="معرف بحث محدد يدوياً (مثال: 23016) [افتراضي: البحث الموصى به تلقائياً]"
    )
    parser.add_argument(
        "--research-check-only",
        action="store_true",
        help="فحص وعرض البحث الموصى به فقط دون بدء البحث فعلياً"
    )

    # خيارات مهمة التحالف ومساعدة الأعضاء وتبرعات العلوم
    parser.add_argument("--alliance", dest="alliance", action="store_true", default=True, help="تفعيل مهمة التحالف (المساعدة والتبرع) [افتراضي: تفعيل]")
    parser.add_argument("--no-alliance", dest="alliance", action="store_false", help="تعطيل مهمة التحالف")
    parser.add_argument("--alliance-sciid", default=None, help="معرف تقنية تحالف محددة للتبرع [افتراضي: التقنية الموصى بها تلقائياً]")
    parser.add_argument("--alliance-gold", type=int, default=0, help="عدد مرات التبرع بالذهب للتحالف [افتراضي: 0 - مجاني فقط]")

    # خيارات مهمة الميناء
    parser.add_argument("--port", dest="port", action="store_true", default=True, help="تفعيل مهمة الميناء [افتراضي: تفعيل]")
    parser.add_argument("--no-port", dest="port", action="store_false", help="تعطيل مهمة الميناء")

    # خيارات مهمة تدريب الجنود
    parser.add_argument("--train", dest="train", action="store_true", default=True, help="تفعيل مهمة تدريب الجنود [افتراضي: تفعيل]")
    parser.add_argument("--no-train", dest="train", action="store_false", help="تعطيل مهمة تدريب الجنود")
    parser.add_argument(
        "--barracks", "-b",
        default="all",
        help="الثكنات المراد تدريبها مفصولة بفاصلة (مثال: 'مشاة,خيالة' أو 'infantry,cavalry,archers') [افتراضي: الكل]"
    )
    parser.add_argument(
        "--troop-level", "-l",
        type=int,
        default=10,
        help="المستوى المستهدف للجنود في الثكنات (مثال: 10 أو 8) [افتراضي: 10 أو أعلى مستوى متاح]"
    )
    parser.add_argument(
        "--troop-levels",
        help="تخصيص فردي لكل ثكنة (مثال: 'infantry:10,archers:8,cavalry:9')"
    )

    # خيارات مهمة دورية الحيوانات الأليفة
    parser.add_argument("--pet-patrol", dest="pet_patrol", action="store_true", default=True, help="تفعيل مهمة دورية الحيوان الأليف [افتراضي: تفعيل]")
    parser.add_argument("--no-pet-patrol", dest="pet_patrol", action="store_false", help="تعطيل مهمة دورية الحيوان الأليف")
    parser.add_argument(
        "--pet", "-p",
        default="غزال",
        help="الحيوان المطلوب تدريبه/إرساله للدورية بالاسم أو المعرف (مثال: 'غزال', 'صقر', 'اسد', 'ذئب', 1261, 1263) [افتراضي: غزال]"
    )
    parser.add_argument(
        "--dest", "--destination",
        dest="destination",
        type=int,
        default=DEFAULT_DESTINATION,
        help="معرف الحيوان المستهدف (وجهة الدورية) [افتراضي: 1262 الأسد]"
    )

    # خيارات مهمة جمع جوائز التوسع الإقليمي
    parser.add_argument("--territory", dest="territory", action="store_true", default=True, help="تفعيل جمع جوائز التوسع الإقليمي [افتراضي: تفعيل]")
    parser.add_argument("--no-territory", dest="territory", action="store_false", help="تعطيل جمع جوائز التوسع الإقليمي")

    # خيارات مهمة درع السلام التلقائي وحماية القلعة
    parser.add_argument("--shield", dest="shield", action="store_true", default=True, help="تفعيل درع السلام لحماية القلعة [افتراضي: تفعيل]")
    parser.add_argument("--no-shield", dest="shield", action="store_false", help="تعطيل درع السلام لحماية القلعة")
    parser.add_argument(
        "--shield-duration", "-sd",
        default="8h",
        choices=["8h", "24h", "3d", "8", "24", "72"],
        help="مدة درع السلام: 8h (8 ساعات) أو 24h (24 ساعة) أو 3d (3 أيام) [افتراضي: 8h]"
    )
    parser.add_argument(
        "--shield-allow-gold",
        dest="shield_allow_gold",
        action="store_true",
        default=False,
        help="السماح بشراء الدرع بالذهب عند نفاد دروع الحقيبة المجانية [افتراضي: معطل لمنع استهلاك الذهب]"
    )

    # خيارات مهمة استخدام وشراء الطاقة
    parser.add_argument("--stamina", dest="stamina", action="store_true", default=True, help="تفعيل مهمة استخدام وشراء الطاقة [افتراضي: تفعيل]")
    parser.add_argument("--no-stamina", dest="stamina", action="store_false", help="تعطيل مهمة استخدام وشراء الطاقة")
    parser.add_argument(
        "--stamina-gold",
        type=int,
        default=0,
        help="عدد مرات شراء الطاقة بالذهب [افتراضي: 0 = مجاني فقط بدون شراء بالذهب]"
    )

    # خيارات مهمة تفعيل المهارات التلقائية
    parser.add_argument("--skills", dest="skills", action="store_true", default=True, help="تفعيل مهمة تفعيل المهارات التلقائية [افتراضي: تفعيل]")
    parser.add_argument("--no-skills", dest="skills", action="store_false", help="تعطيل مهمة تفعيل المهارات التلقائية")
    parser.add_argument(
        "--target-skills", "--skill-list",
        dest="target_skills",
        default="all",
        help="المهارات المطلوب تفعيلها مفصولة بفاصلة (مثال: 'harvest,gather' أو 'الحصاد الوافر,الجمع السريع' أو 'all') [افتراضي: الكل]"
    )

    # خيارات مهمة تجنيد الأبطال وسحب الصناديق اليومية
    parser.add_argument("--hero-draw", dest="hero_draw", action="store_true", default=True, help="تفعيل سحب وتجنيد الأبطال وبحث المهارات المجاني تلقائياً [افتراضي: تفعيل]")
    parser.add_argument("--no-hero-draw", dest="hero_draw", action="store_false", help="تعطيل سحب وتجنيد الأبطال المجاني")

    # خيارات مهمة قاعة الاستراتيجيات وتطوير التكتيكات
    parser.add_argument("--tactics-hall", dest="tactics_hall", action="store_true", default=True, help="تفعيل مهمة قاعة الاستراتيجيات وتطوير التكتيكات [افتراضي: تفعيل]")
    parser.add_argument("--no-tactics-hall", dest="tactics_hall", action="store_false", help="تعطيل مهمة قاعة الاستراتيجيات")
    parser.add_argument(
        "--tactic", "--tactic-name",
        dest="tactic",
        default="القلعة الفارغة",
        help="البحث المستهدف في قاعة الاستراتيجيات بالاسم أو المعرف (مثال: 'القلعة الفارغة', 'قمة الاتقان', 'البحث الكامل', 91010000) [افتراضي: القلعة الفارغة]"
    )

    # خيارات مهمة طاحونة الماء وزيادة إنتاج الموارد
    parser.add_argument("--watermill", dest="watermill", action="store_true", default=True, help="تفعيل مهمة طاحونة الماء وزيادة إنتاج الموارد [افتراضي: تفعيل]")
    parser.add_argument("--no-watermill", dest="watermill", action="store_false", help="تعطيل مهمة طاحونة الماء")
    parser.add_argument(
        "--watermill-types", "--watermill-res",
        dest="watermill_types",
        default="all",
        help="الموارد المراد تعزيز إنتاجها (all, food, wood, iron, silver أو بالعربية: قمح,خشب,حديد,فضة) [افتراضي: all]"
    )
    parser.add_argument(
        "--watermill-buy",
        dest="watermill_buy",
        action="store_true",
        default=True,
        help="السماح بالشراء التلقائي لأدوات التعزيز الناقصة من متجر التحالف [افتراضي: تفعيل]"
    )
    parser.add_argument(
        "--no-watermill-buy",
        dest="watermill_buy",
        action="store_false",
        help="تعطيل الشراء من متجر التحالف والاعتماد حصراً على أدوات الحقيبة"
    )

    # خيارات مهمة نافورة الأمنيات الملكية وبئر الحظ
    parser.add_argument("--fountain", dest="fountain", action="store_true", default=True, help="تفعيل مهمة نافورة الأمنيات الملكية وبئر الحظ [افتراضي: تفعيل]")
    parser.add_argument("--no-fountain", dest="fountain", action="store_false", help="تعطيل مهمة نافورة الأمنيات")
    parser.add_argument(
        "--fountain-res", "--fountain-resources",
        dest="fountain_resources",
        default="food,wood,iron,diamond",
        help="الموارد المطلوب التمني بها مفصولة بفاصلة (food, wood, iron, coal, diamond أو قمح,خشب,حديد,الماس أو all) [افتراضي: food,wood,iron,diamond]"
    )
    parser.add_argument(
        "--fountain-gold",
        dest="fountain_gold",
        action="store_true",
        default=False,
        help="السماح بالشراء بالذهب بعد انتهاء المرات المجانية [افتراضي: معطل لمنع استهلاك الذهب]"
    )
    parser.add_argument(
        "--fountain-gold-times",
        dest="fountain_gold_times",
        type=int,
        default=0,
        help="عدد مرات الشراء بالذهب لكل مورد عند تفعيل الشراء بالذهب [افتراضي: 0]"
    )

    # خيارات مهمة ورشة المواد وصناعة خامات العتاد
    parser.add_argument("--workshop", dest="workshop", action="store_true", default=True, help="تفعيل مهمة ورشة المواد وإنتاج خامات العتاد [افتراضي: تفعيل]")
    parser.add_argument("--no-workshop", dest="workshop", action="store_false", help="تعطيل مهمة ورشة المواد")
    parser.add_argument(
        "--materials", "-m",
        dest="materials",
        default="all",
        help="الخامات المراد إنتاجها مفصولة بفاصلة (fang, fur, metal, coal أو ناب,فرو,معدن,فحم أو all) [افتراضي: all]"
    )

    # خيارات مهمة القافلة التجارية وحراسة الكنز
    parser.add_argument("--caravan", dest="caravan", action="store_true", default=True, help="تفعيل مهمة القافلة التجارية وحراسة الكنز [افتراضي: تفعيل]")
    parser.add_argument("--no-caravan", dest="caravan", action="store_false", help="تعطيل مهمة القافلة التجارية")

    # خيارات مهمة التاجر المتجول والمقايضة التلقائية
    parser.add_argument("--merchant", dest="merchant", action="store_true", default=True, help="تفعيل مهمة التاجر المتجول والمقايضة بالموارد تلقائياً [افتراضي: تفعيل]")
    parser.add_argument("--no-merchant", dest="merchant", action="store_false", help="تعطيل مهمة التاجر المتجول")

    # خيارات مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة
    parser.add_argument("--port-delegate", dest="port_delegate", action="store_true", default=True, help="تفعيل مهمة الميناء العسكري وتفويض السفن ومتجر الجزيرة [افتراضي: تفعيل]")
    parser.add_argument("--no-port-delegate", dest="port_delegate", action="store_false", help="تعطيل مهمة الميناء العسكري")
    parser.add_argument(
        "--island-item", "--island-goods",
        dest="island_item",
        default="7",
        help="المنتج المطلوب شراؤه بالكامل من متجر الجزيرة (1:معنوية, 2:قيصر, 3:تجنيد, 4:صندوق موارد, 5:خبرة, 6:حجر تقنية, 7:حجر تقوية, أو all) [افتراضي: 7]"
    )

    # خيارات مهمة دار الادخار وبنك التوفير
    parser.add_argument("--savings", dest="savings", action="store_true", default=True, help="تفعيل مهمة دار الادخار واستثمار الذهب [افتراضي: تفعيل]")
    parser.add_argument("--no-savings", dest="savings", action="store_false", help="تعطيل مهمة دار الادخار")
    parser.add_argument(
        "--savings-days", "-sdays",
        dest="savings_days",
        choices=["7", "15", "30", 7, 15, 30],
        default="7",
        help="مدة استثمار الذهب في دار الادخار: 7 (أسبوعي) أو 15 (نصف شهري) أو 30 (شهري) [افتراضي: 7]"
    )

    # خيارات مهمة ترقية القلعة ومباني الموارد والمعسكرات والتسريع
    parser.add_argument("--building", dest="building", action="store_true", default=True, help="تفعيل مهمة ترقية المباني والقلعة [افتراضي: تفعيل]")
    parser.add_argument("--no-building", dest="building", action="store_false", help="تعطيل مهمة ترقية المباني والقلعة")
    parser.add_argument("--upgrade-castle", "--castle", dest="upgrade_castle", action="store_true", default=True, help="ترقية القلعة ومتطلباتها المسبقة [افتراضي: True]")
    parser.add_argument("--no-upgrade-castle", "--no-castle", dest="upgrade_castle", action="store_false", help="تعطيل ترقية القلعة")
    parser.add_argument("--speedup-castle", "--speedup", dest="speedup_castle", action="store_true", default=False, help="استخدام التسريع لترقية القلعة بالأدوات المجانية والحقيبة [افتراضي: False]")
    parser.add_argument("--no-speedup-castle", "--no-speedup", dest="speedup_castle", action="store_false", help="تعطيل تسريع القلعة")
    parser.add_argument("--upgrade-support", "--upgrade-buildings", "--buildings", dest="upgrade_support", action="store_true", default=True, help="ترقية المعسكرات والمراكز الطبية والمزارع وخيم العسكرية [افتراضي: True]")
    parser.add_argument("--no-upgrade-support", "--no-upgrade-buildings", "--no-buildings", dest="upgrade_support", action="store_false", help="تعطيل ترقية المعسكرات والمراكز الطبية والمزارع وخيم العسكرية")

    # خيارات مهمة تدريب فخاخ حصن الحرب
    parser.add_argument("--fortress", dest="fortress", action="store_true", default=True, help="تفعيل تدريب فخاخ حصن الحرب تلقائياً لأعلى مستوى متاح [افتراضي: تفعيل]")
    parser.add_argument("--no-fortress", dest="fortress", action="store_false", help="تعطيل تدريب فخاخ حصن الحرب")

    # خيارات مهمة مهام الهيبة اليومية (Prestige Quests)
    parser.add_argument("--prestige", dest="prestige", action="store_true", default=True, help="تفعيل مهمة مهام الهيبة اليومية (تعمل الساعة 3 فجراً) [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige", dest="prestige", action="store_false", help="تعطيل مهمة مهام الهيبة")
    parser.add_argument(
        "--prestige-invaders-max-lv", "--prestige-max-lv",
        dest="prestige_invaders_max_lv",
        type=int,
        default=30,
        help="الحد الأقصى لمستوى الغزاة المطلوب قتالهم في مهام الهيبة [افتراضي: 30]"
    )
    parser.add_argument(
        "--prestige-subtasks",
        dest="prestige_subtasks",
        default="all",
        help="المهام الفرعية المطلوب تشغيلها من مهام الهيبة مفصولة بفاصلة (smuggler,invaders,stronghold,gather,watermill,train,fortress أو all) [افتراضي: الكل]"
    )
    # خيارات تشغيل كل مهمة من مهام الهيبة على حدة
    parser.add_argument("--prestige-smuggler", dest="prestige_smuggler", action="store_true", default=True, help="تفعيل متجر المهربين في مهام الهيبة [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige-smuggler", dest="prestige_smuggler", action="store_false", help="تعطيل متجر المهربين في مهام الهيبة")
    parser.add_argument("--prestige-invaders", dest="prestige_invaders", action="store_true", default=True, help="تفعيل قتال الغزاة في مهام الهيبة [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige-invaders", dest="prestige_invaders", action="store_false", help="تعطيل قتال الغزاة في مهام الهيبة")
    parser.add_argument("--prestige-stronghold", dest="prestige_stronghold", action="store_true", default=True, help="تفعيل قتال المعاقل في مهام الهيبة [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige-stronghold", dest="prestige_stronghold", action="store_false", help="تعطيل قتال المعاقل في مهام الهيبة")
    parser.add_argument("--prestige-gather", dest="prestige_gather", action="store_true", default=True, help="تفعيل جمع الموارد الأربعة في مهام الهيبة [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige-gather", dest="prestige_gather", action="store_false", help="تعطيل جمع الموارد في مهام الهيبة")
    parser.add_argument("--prestige-watermill", dest="prestige_watermill", action="store_true", default=True, help="تفعيل الساقية في مهام الهيبة [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige-watermill", dest="prestige_watermill", action="store_false", help="تعطيل الساقية في مهام الهيبة")
    parser.add_argument("--prestige-train", dest="prestige_train", action="store_true", default=True, help="تفعيل تدريب الجنود في مهام الهيبة [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige-train", dest="prestige_train", action="store_false", help="تعطيل تدريب الجنود في مهام الهيبة")
    parser.add_argument("--prestige-fortress", dest="prestige_fortress", action="store_true", default=True, help="تفعيل حصن الحرب في مهام الهيبة [افتراضي: تفعيل]")
    parser.add_argument("--no-prestige-fortress", dest="prestige_fortress", action="store_false", help="تعطيل حصن الحرب في مهام الهيبة")

    # خيارات مهمة منسق الفيالق والمسيرات (March Orchestrator)
    parser.add_argument("--march-manager", "--march", dest="march_manager", action="store_true", default=True, help="تفعيل مهمة منسق الفيالق والمسيرات الذكي [افتراضي: تفعيل]")
    parser.add_argument("--no-march-manager", "--no-march", dest="march_manager", action="store_false", help="تعطيل مهمة منسق الفيالق والمسيرات")
    parser.add_argument("--march-priorities", dest="march_priorities", default=None, help="قائمة الأولويات مفصولة بفاصلة (مثال: 'transport,ruins,combat,stronghold,gather' أو 'elf' فقط)")
    parser.add_argument("--march-max-queues", dest="march_max_queues", type=int, default=6, help="الحد الأقصى لطوابير فيالق القلعة (5 أو 6) [افتراضي: 6]")
    parser.add_argument("--march-duration", dest="march_duration", type=int, default=20, help="المدة الإجمالية لتشغيل منسق الفيالق بالدقائق (ثلث ساعة = 20 دقيقة) [افتراضي: 20]")

    # مساعدة الموارد
    parser.add_argument("--march-transport", dest="march_transport", action="store_true", default=None, help="تفعيل مساعدة الموارد في منسق الفيالق")
    parser.add_argument("--no-march-transport", dest="march_transport", action="store_false", help="تعطيل مساعدة الموارد في منسق الفيالق")
    parser.add_argument("--march-transport-coords", dest="march_transport_coords", default=None, help="إحداثيات القلعة الهدف للمساعدة بصيغة X,Y (مثال: '344,447')")

    # الأطلال
    parser.add_argument("--march-ruins", dest="march_ruins", action="store_true", default=None, help="تفعيل استكشاف الأطلال (مسيرة واحدة حصراً) [افتراضي: تفعيل]")
    parser.add_argument("--no-march-ruins", dest="march_ruins", action="store_false", help="تعطيل استكشاف الأطلال")
    parser.add_argument("--march-ruins-time", dest="march_ruins_time", type=int, default=900, help="مدة استكشاف الأطلال بالثواني [افتراضي: 900]")
    parser.add_argument("--march-ruins-formation", dest="march_ruins_formation", type=int, default=1, help="تشكيلة استكشاف الأطلال (1-5) [افتراضي: 1]")

    # القتال الحصري (عفريت / غزاة / متمردين)
    parser.add_argument("--march-combat-choice", dest="march_combat_choice", choices=["elf", "invaders", "rebels", "عفريت", "غزاة", "متمردين"], default="elf", help="الهدف القتالي المختار: elf أو invaders أو rebels [افتراضي: elf]")
    parser.add_argument("--march-elf", dest="march_elf", action="store_true", default=None, help="تفعيل قتال نخبة العفريت")
    parser.add_argument("--no-march-elf", dest="march_elf", action="store_false", help="تعطيل قتال نخبة العفريت")
    parser.add_argument("--march-invaders", dest="march_invaders", action="store_true", default=None, help="تفعيل قتال الغزاة")
    parser.add_argument("--no-march-invaders", dest="march_invaders", action="store_false", help="تعطيل قتال الغزاة")
    parser.add_argument("--march-rebels", dest="march_rebels", action="store_true", default=None, help="تفعيل قتال المتمردين")
    parser.add_argument("--no-march-rebels", dest="march_rebels", action="store_false", help="تعطيل قتال المتمردين")
    parser.add_argument("--march-combat-level", dest="march_combat_level", type=int, default=30, help="مستوى الهدف القتالي (غزاة/متمردين) [افتراضي: 30]")
    parser.add_argument("--march-combat-count", dest="march_combat_count", type=int, default=1, help="عدد الهجمات القتالية [افتراضي: 1]")
    parser.add_argument("--march-combat-formation", dest="march_combat_formation", type=int, default=1, help="تشكيلة القتال (1-5) [افتراضي: 1]")

    # المعاقل والملاجئ
    parser.add_argument("--march-stronghold", dest="march_stronghold", action="store_true", default=None, help="تفعيل الهجوم على الملاجئ")
    parser.add_argument("--no-march-stronghold", dest="march_stronghold", action="store_false", help="تعطيل الهجوم على الملاجئ")
    parser.add_argument("--march-stronghold-level", dest="march_stronghold_level", type=int, default=30, help="مستوى الملجأ المستهدف [افتراضي: 30]")
    parser.add_argument("--march-stronghold-count", dest="march_stronghold_count", type=int, default=2, help="عدد الملاجئ المستهدفة [افتراضي: 2]")
    parser.add_argument("--march-stronghold-formation", dest="march_stronghold_formation", type=int, default=1, help="تشكيلة مهاجمة الملجأ [افتراضي: 1]")

    # جمع الموارد
    parser.add_argument("--march-gather", dest="march_gather", action="store_true", default=None, help="تفعيل جمع الموارد بالفيالق الشاغرة [افتراضي: تفعيل]")
    parser.add_argument("--no-march-gather", dest="march_gather", action="store_false", help="تعطيل جمع الموارد")
    parser.add_argument("--march-gather-res", dest="march_gather_res", default="1", help="نوع المورد المطلوب جمعه (1=ذهب, 2=قمح, 3=خشب, 4=حديد, 5=ألماس أو بالاسم) [افتراضي: 1]")
    parser.add_argument("--march-gather-level", dest="march_gather_level", type=int, default=5, help="مستوى حقل المورد للجمع [افتراضي: 5]")
    parser.add_argument("--march-gather-range", dest="march_gather_range", type=int, default=100, help="أقصى نطاق بحث لحقول الموارد [افتراضي: 100]")

    # خيار تجاوز فحص مواعيد الجدول الزمني للتجربة الفورية
    parser.add_argument(
        "--ignore-schedule", "--now",
        dest="ignore_schedule",
        action="store_true",
        default=False,
        help="تجاوز فحص مواعيد الجدول وتشغيل كافة المهام المفعلة فوراً في هذه الدورة [افتراضي: معطل]"
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

    # تجهيز مستويات التدريب لكل نوع من القوات
    custom_lvls = {}
    if args.troop_levels:
        for item in args.troop_levels.replace("،", ",").split(","):
            if ":" in item:
                k, v = item.split(":", 1)
                custom_lvls[k.strip()] = int(v.strip())
    elif args.barracks.strip().lower() not in ("all", "الكل", "all_types"):
        for b in args.barracks.replace("،", ",").split(","):
            b = b.strip()
            if b:
                custom_lvls[b] = args.troop_level
    else:
        custom_lvls = {
            "infantry": args.troop_level,
            "cavalry": args.troop_level,
            "archers": args.troop_level,
            "chariots": args.troop_level,
        }

    # ── إذا مُرِّر ملف إعدادات Firebase، استخدمه مباشرة ─────────────────────────────────
    if args.firebase_config and os.path.exists(args.firebase_config):
        try:
            with open(args.firebase_config, "r", encoding="utf-8") as _fc:
                cfg = json.load(_fc)
            log.info(f"✅ تم تحميل إعدادات Firebase من: {args.firebase_config}")
            # إنشاء مدير البوت مباشرة بدون المرور بـ argparse config builder
            manager = BotManager(
                target_email,
                cfg,
                reconnect_wait_seconds=args.reconnect_wait,
                ignore_schedule=True,  # Firebase دائماً يتجاهل الجدول الزمني ويعمل فورياً حسب خيارات المستخدم
                user_id=getattr(args, "firebase_user_id", None),
                castle_id=getattr(args, "firebase_castle_id", None),
            )
            if args.loop:
                asyncio.run(manager.run_loop(loop_interval_minutes=args.loop_interval))
            else:
                asyncio.run(manager.run_once())
            sys.exit(0)
        except Exception as _fe:
            log.error(f"❌ خطأ في قراءة ملف إعدادات Firebase: {_fe}")
            sys.exit(1)

    # بناء قاموس الإعدادات المطابق للمخطط الجديد (من argparse)
    cfg = {
        "city_harvest": {
            "enabled": args.harvest,
        },
        "research": {
            "enabled": args.research,
        },
        "alliance": {
            "enabled": args.alliance,
            "auto_help": True,
            "gold_donations": args.alliance_gold,
        },
        "port": {
            "enabled": args.port,
        },
        "train": {
            "enabled": args.train,
            "levels": custom_lvls,
        },
        "pet_patrol": {
            "enabled": args.pet_patrol,
            "pet": args.pet,
        },
        "territory_expansion": {
            "enabled": args.territory,
        },
        "shield": {
            "enabled": args.shield,
            "duration": args.shield_duration,
            "allow_gold": args.shield_allow_gold,
        },
        "stamina": {
            "enabled": args.stamina,
            "gold_buys": args.stamina_gold,
        },
        "skills": {
            "enabled": args.skills,
            "target_skills": resolve_target_skills(args.target_skills),
        },
        "hero_draw": {
            "enabled": args.hero_draw,
        },
        "tactics_hall": {
            "enabled": args.tactics_hall,
            "tactic": args.tactic,
        },
        "watermill": {
            "enabled": args.watermill,
            "types": args.watermill_types,
            "allow_shop_buy": args.watermill_buy,
        },
        "fountain": {
            "enabled": args.fountain,
            "resources": [r.strip() for r in args.fountain_resources.replace("،", ",").split(",") if r.strip()],
            "allow_gold": args.fountain_gold,
            "gold_times": args.fountain_gold_times,
        },
        "material_workshop": {
            "enabled": args.workshop,
            "materials": [m.strip() for m in args.materials.replace("،", ",").split(",") if m.strip()] if args.materials != "all" else "all",
        },
        "caravan": {
            "enabled": args.caravan,
        },
        "merchant": {
            "enabled": args.merchant,
        },
        "port_delegate": {
            "enabled": args.port_delegate,
            "shop_item": args.island_item,
        },
        "savings_bank": {
            "enabled": args.savings,
            "days": parse_savings_days(args.savings_days),
        },
        "building": {
            "enabled": args.building,
            "upgrade_castle": args.upgrade_castle,
            "speedup_castle": args.speedup_castle,
            "upgrade_support_buildings": args.upgrade_support,
        },
        "fortress": {
            "enabled": args.fortress,
        },
        "prestige": {
            "enabled": args.prestige,
            "schedule": {
                "hours": [3],
            },
            "invaders_max_lv": args.prestige_invaders_max_lv,
            "subtasks": {
                "smuggler": args.prestige_smuggler,
                "invaders": args.prestige_invaders,
                "stronghold": args.prestige_stronghold,
                "gather": args.prestige_gather,
                "watermill": args.prestige_watermill,
                "train": args.prestige_train,
                "fortress": args.prestige_fortress,
            },
        },
        "march_manager": {
            "enabled": args.march_manager,
            "schedule": {"times_per_day": 4},
            "duration_minutes": args.march_duration,
            "max_queues": args.march_max_queues,
            "priority_order": (
                [p.strip() for p in args.march_priorities.replace("،", ",").split(",") if p.strip()]
                if args.march_priorities
                else ["transport", "ruins", "combat", "stronghold", "gather"]
            ),
            "transport": {
                "enabled": bool(args.march_transport) if args.march_transport is not None else False,
                "target_x": (
                    int(args.march_transport_coords.split(",")[0].strip())
                    if args.march_transport_coords and "," in args.march_transport_coords
                    else None
                ),
                "target_y": (
                    int(args.march_transport_coords.split(",")[1].strip())
                    if args.march_transport_coords and "," in args.march_transport_coords
                    else None
                ),
                "resource_ids": [1002, 1003, 1004, 1005],
            },
            "ruins": {
                "enabled": bool(args.march_ruins) if args.march_ruins is not None else True,
                "explore_time": args.march_ruins_time,
                "formation_id": args.march_ruins_formation,
            },
            "combat": {
                "enabled": (
                    bool(args.march_elf or args.march_invaders or args.march_rebels)
                    if (args.march_elf is not None or args.march_invaders is not None or args.march_rebels is not None)
                    else True
                ),
                "choice": (
                    "elf" if args.march_elf else (
                        "invaders" if args.march_invaders else (
                            "rebels" if args.march_rebels else (
                                "elf" if args.march_combat_choice in ("elf", "عفريت") else (
                                    "invaders" if args.march_combat_choice in ("invaders", "غزاة") else "rebels"
                                )
                            )
                        )
                    )
                ),
                "level": args.march_combat_level,
                "formation_id": args.march_combat_formation,
                "count": args.march_combat_count,
            },
            "elf": {
                "enabled": (
                    bool(args.march_elf)
                    if args.march_elf is not None
                    else (args.march_combat_choice in ("elf", "عفريت") and not args.march_invaders and not args.march_rebels)
                ),
                "formation_id": args.march_combat_formation,
            },
            "invaders": {
                "enabled": (
                    bool(args.march_invaders)
                    if args.march_invaders is not None
                    else (args.march_combat_choice in ("invaders", "غزاة") and not args.march_elf and not args.march_rebels)
                ),
                "level": args.march_combat_level,
                "formation_id": args.march_combat_formation,
                "count": args.march_combat_count,
            },
            "rebels": {
                "enabled": (
                    bool(args.march_rebels)
                    if args.march_rebels is not None
                    else (args.march_combat_choice in ("rebels", "متمردين") and not args.march_elf and not args.march_invaders)
                ),
                "level": args.march_combat_level,
                "formation_id": args.march_combat_formation,
                "count": args.march_combat_count,
            },
            "stronghold": {
                "enabled": bool(args.march_stronghold) if args.march_stronghold is not None else False,
                "level": args.march_stronghold_level,
                "count": args.march_stronghold_count,
                "formation_id": args.march_stronghold_formation,
            },
            "gather": {
                "enabled": bool(args.march_gather) if args.march_gather is not None else True,
                "res_type": args.march_gather_res,
                "level": args.march_gather_level,
                "search_range": args.march_gather_range,
            },
        }
    }

    # تخصيص المهام الفرعية لمهام الهيبة إن تم تمرير قائمة محددة
    if args.prestige_subtasks and args.prestige_subtasks.strip().lower() not in ("all", "الكل"):
        chosen_subtasks = [s.strip() for s in args.prestige_subtasks.replace("،", ",").split(",") if s.strip()]
        for k in cfg["prestige"]["subtasks"]:
            cfg["prestige"]["subtasks"][k] = False
        for s in chosen_subtasks:
            res_key = PRESTIGE_SUBTASK_ALIASES.get(s.lower(), s.lower())
            if res_key in cfg["prestige"]["subtasks"]:
                cfg["prestige"]["subtasks"][res_key] = True

    # تمرير أي خيارات تجريبية إضافية إن حُددت من سطر الأوامر صراحة
    if args.harvest_types != "all":
        cfg["city_harvest"]["types"] = args.harvest_types
    if args.research_tree != "defense":
        cfg["research"]["tree"] = args.research_tree
    if args.tech_id:
        cfg["research"]["tech_id"] = args.tech_id
    if args.research_check_only:
        cfg["research"]["check_only"] = True
    if args.alliance_sciid:
        cfg["alliance"]["sciid"] = args.alliance_sciid
    if args.destination != 1389:
        cfg["pet_patrol"]["destination"] = args.destination

    # إنشاء مدير البوت
    manager = BotManager(
        target_email,
        cfg,
        reconnect_wait_seconds=args.reconnect_wait,
        ignore_schedule=args.ignore_schedule,
        user_id=getattr(args, "firebase_user_id", None),
        castle_id=getattr(args, "firebase_castle_id", None),
    )

    # اختيار وضع التشغيل
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
