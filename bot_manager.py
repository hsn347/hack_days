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
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from game_client import GameConnection, AccountSession
from core.session_manager import SessionManager
from tasks.port import PortTask
from tasks.train import TrainTask, BUILDING_TROOP_MAP, TYPE_ALIASES
from tasks.pet_patrol import PetPatrolTask, KNOWN_PETS, DEFAULT_PET_ID, DEFAULT_DESTINATION
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
from tasks.merchant import MerchantTask
from tasks.port_delegate import PortDelegateTask, DELEGATE_TASKS_CONFIG, ISLAND_SHOP_CATALOG, resolve_island_goods_id
from tasks.savings_bank import SavingsBankTask, SAVINGS_PLANS, DEFAULT_DAYS as DEFAULT_SAVINGS_DAYS
from tasks.building import BuildingTask, BUILDING_INFO
from tasks.fortress import FortressTask

# ── إعداد نظام التسجيل (Logging) ───────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("bot_manager")


# ════════════════════════════════════════════════════════════════════════════════════════
# 🔥🔥🔥 [متغيرات وإعدادات المستخدم القادمة من فايربيس — FIREBASE USER CONFIG] 🔥🔥🔥
# ════════════════════════════════════════════════════════════════════════════════════════
# هذا المخطط (Schema) يمثل الحقول والقيم التي سيتم جلبها لاحقاً من قاعدة بيانات Firebase
# لكل حساب مستخدم بناءً على ما يختاره ويحدده المستخدم من لوحة التحكم (Web Dashboard):
# ════════════════════════════════════════════════════════════════════════════════════════

DEFAULT_FIREBASE_USER_CONFIG: Dict[str, Any] = {
    # 🌾 1. مهمة حصد مزارع ومناجم المدينة (City Harvest)
    "city_harvest": {
        "enabled": True,             # تفعيل/تعطيل حصد مزارع الموارد داخل المدينة
    },

    # 🔬 2. مهمة أبحاث الأكاديمية والعلوم (Academy Research)
    "research": {
        "enabled": True,             # تفعيل/تعطيل أبحاث الأكاديمية التلقائية (البحث الموصى به من النظام)
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
        "pet": "غزال",               # اسم أو معرف الحيوان المطلوب تدريبه/إرساله (مثال: "غزال", "صقر", "اسد", "ذئب")
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
        "gold_buys": 0,              # عدد مرات شراء الطاقة بالذهب المحدد من المستخدم (0 = مجاني فقط بدون شراء بالذهب)
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
    },

    # 💧 13. مهمة طاحونة الماء وزيادة إنتاج موارد القلعة (Watermill Production Boost)
    "watermill": {
        "enabled": True,             # تفعيل/تعطيل مهمة طاحونة الماء ومضاعفة إنتاج الموارد
        "types": "all",              # الموارد المطلوب تعزيزها: "all" (الكل)، أو محددة مثل: "food" (قمح), "wood" (خشب), "iron" (حديد), "silver" (فضة)
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

    # 🛒 17. مهمة التاجر المتجول والمقايضة التلقائية (Traveling Merchant)
    "merchant": {
        "enabled": True,             # تفعيل/تعطيل المقايضة والشراء التلقائي من التاجر المتجول بالموارد
        "target": 10,                # عدد عمليات الشراء بالموارد المستهدفة
        "max_gold": 0,               # سقف الذهب لتحديث المتجر (0 = تحديثات مجانية فقط لمنع استهلاك الذهب)
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

    # 🏰 21. مهمة تدريب فخاخ حصن الحرب (War Fortress Traps)
    "fortress": {
        "enabled": True,                   # تفعيل/تعطيل تدريب فخاخ حصن الحرب تلقائياً لأعلى مستوى متاح
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
        self.lord_name: str = "غير معروف"
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

        # دروع السلام المتوفرة في الحقيبة
        self.shield_backpack_counts: Dict[str, int] = {"8h": 0, "24h": 0, "3d": 0}

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
        max_reconnect_attempts: int = 10
    ):
        if isinstance(account_or_email, str):
            sm = SessionManager()
            accs = sm.load()
            acc = accs.get(account_or_email)
            if not acc:
                raise ValueError(f"الحساب {account_or_email} غير موجود في session_cache.json!")
            self.account = acc
        else:
            self.account = account_or_email

        self.email = self.account.email
        self.conn: Optional[GameConnection] = None
        self.context = AccountContext(self.email)

        # دمج الإعدادات الافتراضية مع إعدادات المستخدم القادمة من Firebase
        self.config = self._build_default_config(config or {})

        # إعدادات إعادة الاتصال التلقائي عند دخول شخص آخر للحساب
        self.reconnect_wait_seconds = int(reconnect_wait_seconds)
        self.max_reconnect_attempts = int(max_reconnect_attempts)
        self._disconnected_event = asyncio.Event()
        self._last_kick_reason: str = ""

    def _build_default_config(self, user_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """بناء قاموس الإعدادات بدمج إعدادات المستخدم القادمة من Firebase مع المخطط الافتراضي."""
        cfg = copy.deepcopy(DEFAULT_FIREBASE_USER_CONFIG)
        for section, values in (user_cfg or {}).items():
            if section in cfg and isinstance(values, dict) and isinstance(cfg[section], dict):
                cfg[section].update(values)
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
        print("\n" + "!" * 70)
        log.warning(f"⚠️ [انقطاع الاتصال] تم رصد انقطاع الاتصال بالحساب (السبب: {display_reason})!")
        log.warning(f"⏳ سيتوقف البوت مؤقتاً وينتظر {self.reconnect_wait_seconds} ثانية (دقيقة واحدة) لإفساح المجال ثم إعادة الدخول...")
        print("!" * 70 + "\n")

        for attempt in range(1, self.max_reconnect_attempts + 1):
            log.info(f"⏳ [المحاولة {attempt}/{self.max_reconnect_attempts}] انتظار {self.reconnect_wait_seconds} ثانية (دقيقة واحدة)...")
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
                log.info("🎉 تم إعادة تسجيل الدخول بنجاح تام! جاهز لاستئناف المهام المتوقفة... ✅")
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

        # 1. بيانات اللورد من init_data
        lord_ctrl = self.conn.init_data.get("lordInfoCtrl", {})
        base_info = lord_ctrl.get("base", {}) if isinstance(lord_ctrl, dict) else {}
        fc_info = lord_ctrl.get("fcInfo", {}) if isinstance(lord_ctrl, dict) else {}

        ctx.lord_name = str(base_info.get("nickName", self.email.split('@')[0]))
        ctx.lord_level = int(base_info.get("level", 0))
        ctx.kingdom_id = str(base_info.get("partition", ""))
        ctx.gold = int(base_info.get("gold", 0))
        ctx.total_power = int(fc_info.get("totalFc", 0))
        ctx.uid = str(base_info.get("uid", getattr(self.account, "user_id", "")))

        # 2. استعلام مباني المدينة 1001/1
        r_city = await self.conn.query("1001", "1", {}, timeout=8)
        blist = r_city.get("data", {}).get("blist", []) if r_city else []
        if not blist and "cityCtrl" in self.conn.init_data:
            blist = self.conn.init_data["cityCtrl"].get("blist", [])

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
        print(f"🛡️ دروع السلام في الحقيبة: {total_shields} درع (🛡️ {s_8h} درع 8س | 🛡️ {s_24h} درع 24س | 🛡️ {s_3d} درع 3أيام)")
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
        """تنفيذ سلسلة المهام بالترتيب المحدد وفق إعدادات المستخدم مع استئناف ذكي عند انقطاع الاتصال."""
        results = {}

        # 📋👇👇 قائمة تسلسل المهام المنفذة — رتبها أو عدلها كما تشاء 👇👇📋
        pipeline: List[Tuple[str, Callable]] = [
            ("🌾 حصد مزارع المدينة (City Harvest)",          self.step_1_city_harvest_task),
            ("🔬 أبحاث الأكاديمية والعلوم (Academy Research)", self.step_2_research_task),
            ("🤝 مهام وتبرعات التحالف (Alliance Task)",       self.step_3_alliance_task),
            ("🚢 مهمة الميناء (Port Task)",                 self.step_4_port_task),
            ("⚔️ مهمة تدريب الجنود (Train Troops)",         self.step_5_train_task),
            ("🐾 مهمة دورية الحيوان الأليف (Pet Patrol)",    self.step_6_pet_patrol_task),
            ("🚩 جوائز التوسع الإقليمي (Territory Expansion)", self.step_7_territory_expansion_task),
            ("🛡️ درع السلام وحماية القلعة (Peace Shield)",    self.step_8_shield_task),
            ("⚡ استخدام وشراء الطاقة (Stamina Task)",       self.step_9_stamina_task),
            ("🎯 تفعيل المهارات التلقائية (Skills Task)",    self.step_10_skills_task),
            ("🦸 تجنيد الأبطال وسحب الصناديق (Hero Draw)",  self.step_11_hero_draw_task),
            ("🏛️ قاعة الاستراتيجيات وتطوير التكتيكات (Tactics Hall)", self.step_12_tactics_hall_task),
            ("💧 طاحونة الماء وزيادة الإنتاج (Watermill Boost)",     self.step_13_watermill_task),
            ("⛲ نافورة الأمنيات وبئر الحظ (Trevi Fountain)",       self.step_14_fountain_task),
            ("🔨 ورشة المواد وصناعة خامات العتاد (Material Workshop)", self.step_15_material_workshop_task),
            ("🐪 القافلة وحراسة الكنز (Caravan Task)",             self.step_16_caravan_task),
            ("🛒 التاجر المتجول والمقايضة (Merchant Task)",        self.step_17_merchant_task),
            ("⚓ الميناء العسكري ومتجر الجزيرة (Port Delegate)",    self.step_18_port_delegate_task),
            ("🏦 دار الادخار واستثمار الذهب (Savings Bank)",       self.step_19_savings_bank_task),
            ("🏗️ ترقية القلعة والمباني والتسريع (Building Upgrade)", self.step_20_building_task),
            ("🏰 فخاخ حصن الحرب (War Fortress Traps)",             self.step_21_fortress_task),
            # ──────────────────────────────────────────────────────────
            # يمكنك مستقبلاً إضافة أي مهمة جديدة هنا بسطر واحد:
            # ("🏰 ترقية القلعة والمباني", self.step_11_building_task),
            # ("🪙 جمع الذهب الذكي",       self.step_9_gold_gather_task),
            # ──────────────────────────────────────────────────────────
        ]

        step_idx = 0
        while step_idx < len(pipeline):
            step_name, step_func = pipeline[step_idx]

            # 1. التحقق من سلامة الاتصال قبل بدء المهمة
            if not self.is_connection_alive():
                kick_reason = self.get_disconnect_reason()
                log.warning(f"⚠️ تم رصد انقطاع الاتصال قبل بدء المهمة [{step_name}] (السبب: {kick_reason})")
                reconnected = await self.wait_and_reconnect(kick_reason)
                if not reconnected:
                    log.error(f"❌ تعذر استعادة الاتصال بعد استنفاد محاولات الدخول. إيقاف السلسلة عند: {step_name}")
                    results[step_name] = {"success": False, "error": "انقطاع الاتصال وتعذر إعادة الدخول"}
                    break

            print("\n" + "─" * 65)
            print(f"▶️ بدء تنفيذ: {step_name}")
            print("─" * 65)

            step_interrupted = False
            step_task = asyncio.create_task(step_func())
            disconnect_waiter = asyncio.create_task(self._disconnected_event.wait())

            done, pending = await asyncio.wait(
                [step_task, disconnect_waiter],
                return_when=asyncio.FIRST_COMPLETED
            )

            if disconnect_waiter in done:
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
        """فحص وتنفيذ دورية الحيوان الأليف المحدد من قبل المستخدم واستلام الجوائز."""
        pet_cfg = self.config.get("pet_patrol", {})
        if not bool(pet_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي دورية الحيوان الأليف بناءً على رغبة المستخدم (pet_patrol.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # تحديد الحيوان الأليف المطلوب بناءً على مدخل المستخدم
        user_pet_choice = pet_cfg.get("pet", DEFAULT_PET_ID)
        target_pet_id = resolve_pet_id(user_pet_choice)
        target_dest = int(pet_cfg.get("destination", DEFAULT_DESTINATION))

        # التحقق هل الحيوان مفتوح بالحساب (إذا توافرت بيانات init_data)
        if self.context.unlocked_pets:
            if target_pet_id not in self.context.unlocked_pets:
                first_unlocked = next(iter(self.context.unlocked_pets.keys()))
                req_name = KNOWN_PETS.get(target_pet_id, {}).get("name", f"#{target_pet_id}")
                alt_name = self.context.unlocked_pets[first_unlocked]["name"]
                log.warning(f"⚠️ الحيوان المطلوب [{req_name}] غير مفتوح في الحساب! سيتم تدريب وإرسال المتوفر [{alt_name}] بدلاً منه.")
                target_pet_id = first_unlocked

        pet_name = KNOWN_PETS.get(target_pet_id, {}).get("name", f"حيوان #{target_pet_id}")
        log.info(f"🐾 جاري تنفيذ الدورية للحيوان المحدد: [{pet_name}] (معرف: {target_pet_id})...")

        task_pet_cfg = {
            "pet_id": target_pet_id,
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
        allow_gold = bool(fountain_cfg.get("allow_gold", fountain_cfg.get("use_gold", False)))
        gold_times = int(fountain_cfg.get("gold_times", 0))

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

    # [17] مهمة التاجر المتجول والمقايضة التلقائية
    async def step_17_merchant_task(self) -> Dict[str, Any]:
        """فحص وشراء سلع التاجر المتجول بالموارد فقط وتحديث المتجر بأمان ضد الحظر وحماية الذهب."""
        merchant_cfg = self.config.get("merchant", {})
        if not bool(merchant_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة التاجر المتجول بناءً على رغبة المستخدم (merchant.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🛒 بدء مهمة التاجر المتجول للمقايضة بالموارد فقط (حماية الذهب ومكافحة الحظر)...")
        task = MerchantTask(self.conn, merchant_cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة التاجر المتجول: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في التاجر المتجول: {res.message}")

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

    # ─────────────────────────────────────────────────────────────────
    #  الخطوة 21: مهمة تدريب فخاخ حصن الحرب التلقائية
    # ─────────────────────────────────────────────────────────────────
    async def step_21_fortress_task(self) -> Dict[str, Any]:
        """تدريب فخاخ حصن الحرب تلقائياً لأعلى مستوى متاح (rocks / arrows / oil) بحساب السور والموارد."""
        f_cfg = self.config.get("fortress", {})
        if not bool(f_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة فخاخ حصن الحرب بناءً على رغبة المستخدم (fortress.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🏰 بدء مهمة تدريب فخاخ حصن الحرب (تلقائي لأعلى مستوى متاح وأقصى عدد ممكن)...")

        task_cfg = {
            "type": "auto",
            "level": None,
            "count": "max"
        }

        task = FortressTask(self.conn, task_cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة فخاخ حصن الحرب: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في فخاخ حصن الحرب: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # ─────────────────────────────────────────────────────────────────
    #  دورة التشغيل الكاملة (Full Lifecycle)
    # ─────────────────────────────────────────────────────────────────
    async def run(self) -> Dict[str, Any]:
        """
        تشغيل دورة المدير الكاملة:
          1. تسجيل الدخول.
          2. الاستعلام الشامل (مع إعادة المحاولة عند انقطاع الاتصال).
          3. تنفيذ سلسلة المهام بالترتيب (مع استئناف ذكي من نفس النقطة عند انقطاع الاتصال).
          4. إغلاق الاتصال بأمان وإعادة النتائج.
        """
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

            # 3. تنفيذ سلسلة المهام
            pipeline_results = await self.execute_task_pipeline()

            print("\n" + "═" * 72)
            print("🏁 اكتمال تنفيذ المهام بنجاح من قبل مدير البوت!")
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
        "--reconnect-wait",
        type=int,
        default=60,
        help="مدة الانتظار بالثواني عند انقطاع الاتصال بسبب دخول شخص آخر للحساب [افتراضي: 60 ثانية (دقيقة واحدة)]"
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
        default=1389,
        help="وجهة الدورية [افتراضي: 1389]"
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

    # بناء قاموس الإعدادات المطابق للمخطط الجديد
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
        }
    }

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

    # إنشاء وتشغيل مدير البوت
    manager = BotManager(target_email, cfg, reconnect_wait_seconds=args.reconnect_wait)
    asyncio.run(manager.run())
