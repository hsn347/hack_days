# -*- coding: utf-8 -*-
"""
أمثلة التشغيل من سطر الأوامر (CLI):
  # 1. تشغيل افتراضي شامل:
  python bot_manager.py --email "johan2003@yopmail.com"
python3 -c "import sqlite3; conn = sqlite3.connect('database/castles.db'); cur = conn.cursor(); cur.execute('DELETE FROM castle_states WHERE lower(email) = lower(\"lyalshyhany21@gmail.com\")'); conn.commit(); print(f'تم حذف {cur.rowcount} سجل بنجاح'); conn.close()"

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
import random

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
from tasks.torch_chest import TorchChestTask
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
from tasks.hero_consign import HeroConsignTask
from tasks.troy_treasure import TroyTreasureTask
from tasks.hospital import HospitalTask
from tasks.mail import MailTask
from tasks.march_manager import MarchManagerTask
from tasks.warrior_exchange import WarriorExchangeTask
from tasks.elf_boss import ElfBossTask
from tasks.auction import AuctionTask



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
    """محوّل يحول log_callback إلى كائن شبيه بالملف ليعمل مع StreamHandler مع منع الازدواجية في الطباعة."""
    def __init__(self, callback, already_printed: bool = True):
        self._callback = callback
        self._already_printed = already_printed
        self._buffer = ""

    def write(self, msg):
        self._buffer += msg
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                try:
                    self._callback(line, already_printed=self._already_printed)
                except TypeError:
                    self._callback(line)

    def flush(self):
        if self._buffer.strip():
            try:
                self._callback(self._buffer.strip(), already_printed=self._already_printed)
            except TypeError:
                self._callback(self._buffer.strip())
            self._buffer = ""


def _safe_bind_task_logger(task: Any, log_cb: Optional[Any], level: int = logging.INFO) -> None:
    """تنظيف أي StreamHandler سابق وربط callback والطباعة المباشرة ببادئة مدمجة لمنع تكرار السجلات."""
    if not hasattr(task, "log") or not task.log:
        return
    task.log.propagate = False
    task.log.setLevel(level)
    try:
        task.log.handlers.clear()
    except Exception:
        task.log.handlers = []

    # استخراج اسم الحساب المختصر لتوفير المساحة وتوحيد المظهر
    task_email = getattr(task, "email", "") or getattr(task, "name", "bot")
    short_user = task_email.split("@")[0] if "@" in str(task_email) else str(task_email)

    # ربط StreamHandler للطباعة على stdout مباشرة (journalctl / terminal) ببادئة مدمجة وأنيقة
    try:
        console_h = logging.StreamHandler(sys.stdout)
        console_h.setLevel(level)
        console_h.setFormatter(logging.Formatter(f"[%(asctime)s][{short_user}] %(message)s", datefmt="%H:%M:%S"))
        task.log.addHandler(console_h)
    except Exception:
        pass

    if not log_cb:
        return
    try:
        h = logging.StreamHandler(_LogCallbackStream(log_cb, already_printed=True))
        h.setLevel(level)
        h.setFormatter(logging.Formatter("%(message)s"))
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
    task.log.propagate = False

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
        "open_treasure": True,       # استلام وفتح كنز التحالف
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
        "destination": 1350,         # الحيوان المستهدف: الأسد 1350 افتراضياً
    },

    # 🚩 7. مهمة جمع جوائز التوسع الإقليمي (Territory Expansion)
    "territory_expansion": {
        "enabled": True,             # تفعيل/تعطيل جمع جوائز حدث التوسع الإقليمي
    },

    # 🎰 7b. مهمة صندوق مشعل رويال (Royal Torch Chest)
    "torch_chest": {
        "enabled": False,            # تفعيل/تعطيل شراء صندوق المشعل من المتجر بالذهب
    },
    "open_torch_chest": {
        "enabled": False,            # تفعيل/تعطيل فتح صندوق المشعل من الحقيبة
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
        "enabled": True,             # مهمة إلزامية تلقائية (حفر مجاني ومساعدة الأعضاء)
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
        "deposit": 2000,             # مبلغ الذهب المراد إيداعه (100 - 60000)
        "max_amount": 2000,          # المبلغ الأقصى للادخار بالذهب
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

    # 🧭 22c2. مهمة رحلات وتكليف الأبطال (Hero Voyage & Consign)
    # رحلات الأبطال اليومية (10 رحلات) + استلام جوائز التكليف المنجزة + تنفيذ مهام التكليف (5 مهام)
    "hero_consign": {
        "enabled": False,                  # تفعيل/تعطيل رحلات وتكليف الأبطال تلقائياً (معطلة افتراضياً حتى يفعلها المستخدم)
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
    # فحص المشفى وعلاج الجرحى استباقياً بحسب الموارد المتوفرة:
    #   - "prestige": علاج العدد المتبقي فقط لإتمام مهمة الهيبة اليومية بأقل استهلاك للموارد (افتراضي).
    #   - "all":      علاج كافة الجرحى الممكن علاجهم استباقياً بالموارد المتاحة دون التقيد بالهيبة.
    "hospital": {
        "enabled": False,                  # تفعيل/تعطيل علاج الجنود بالمشفى تلقائياً (ملغية افتراضياً)
        "mode": "prestige",                # نمط العلاج: "prestige" (المتبقي للهيبة) | "all" (علاج الكل الممكن)
    },

    # 🛒 22f. مهمة استبدال متجر المحارب في مركز المنافع (Warrior Exchange Task)
    # استبدال المنتج #910018 بالعدد المطلوب بشرط توفر كامل حصة الـ 15 بالسيرفر
    "warrior_exchange": {
        "enabled": False,                  # تفعيل/تعطيل المهمة (افتراضياً معطلة حتى يفعلها المستخدم)
        "count": 15,                       # عدد مرات الاستبدال المطلوبة (1 إلى 15)
    },

    # 🧝 22g. مهمة نخبة العفريت (Elf Elite Boss Task)
    "elf": {
        "enabled": False,                  # تفعيل/تعطيل الهجوم على العفريت
        "formation_id": 1,                 # رقم التشكيلة
    },

    # 🕊️ 22h. مهمة المزايدة على الحمام الزاجل في سوق المملكة (Auction Task)
    # يزايد البوت على الحمام الزاجل (#501901) وشظاياه (#503001) بحد أقصى محدد بالذهب
    "auction": {
        "enabled": False,                  # تفعيل/تعطيل المزايدة (معطلة افتراضياً)
        "max_gold": 2000,                  # الحد الأقصى للمزايدة بالذهب (افتراضي: 2000)
    },

    # 🎖️ 23. مهمة منسق الفيالق والمسيرات الذكي الموحد (March Manager & Orchestrator)
    # يدير كافة مسيرات الخريطة الخارجية للقلعة وفق مصفوفة أولويات ذكية (تأتي من فايربيس)
    "march_manager": {
        "enabled": True,                   # تفعيل/تعطيل منسق الفيالق كلياً
        "duration_minutes": 20,            # مدة تشغيل المهمة الإجمالية بالدقائق (ثلث ساعة = 20 دقيقة ككل)

        # [0] أولوية الهجوم على وحش ابرا (Abra Boss Attack)
        "abra": {
            "enabled": False,              # تفعيل مهاجمة وحش ابرا
            "x": 0,                        # إحداثي X للوحش
            "y": 0,                        # إحداثي Y للوحش
            "killing_blow": False,         # أخذ الضربة القاضية (إنهاء الوحش)
            "formation_id": 1,             # رقم التشكيلة
        },

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
            "choice": "invaders",             # الخيار المستهدف: "invaders" (غزاة) أو "rebels" (متمردين)
            "level": 30,                   # مستوى الهدف المطلوب مهاجمته (للغزاة/المتمردين)
            "formation_id": 1,             # رقم تشكيلة القتال (1 إلى 5)
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
            "use_boost": False,            # تفعيل مكافأة سرعة الجمع من الحقيبة تلقائياً (+50%)
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
    "1": 1, "1d": 1, "1_day": 1, "يوم": 1, "يومي": 1, "daily": 1,
    "7": 7, "7d": 7, "7_days": 7, "أسبوع": 7, "اسبوع": 7, "أسبوعي": 7, "اسبوعي": 7, "weekly": 7,
    "15": 15, "15d": 15, "15_days": 15, "نصف_شهر": 15, "نصف شهر": 15, "biweekly": 15,
    "30": 30, "30d": 30, "30_days": 30, "شهر": 30, "شهري": 30, "monthly": 30,
}

def parse_savings_days(val: Any) -> int:
    """تحويل المدة المدخلة إلى أحد الخيارات الأربعة الصالحة لدار الادخار: 1 أو 7 أو 15 أو 30 يوماً."""
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
#  كلاس سياق وبيانات الحساب (Account)
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
        self.tactics_hall_free_draw_left: int = 0
        self.tactics_hall_free_draw_ready: bool = False

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
#  دالة تعطيل مهمة العفريت لقلعة محددة حصراً في قاعدة البيانات
# ════════════════════════════════════════════════════════════════════

def disable_elf_task(identifier: Optional[str] = None) -> bool:
    """
    تعطيل مهمة العفريت لقلعة محددة حصراً في قاعدة البيانات (عمود config):
    تضبط قيمة "elf": {"enabled": False, ...} مع الحفاظ التام على رقم التشكيلة المحدد.

    :param identifier: البريد الإلكتروني للقلعة (email) أو معرف القلعة (castle_id).
    :return: True عند نجاح الحفظ في SQLite، و False عند الفشل أو عدم العثور على القلعة.
    """
    if not identifier:
        log.warning("⚠️ تعذر تعطيل مهمة العفريت: لم يتم تمرير معرّف القلعة أو البريد.")
        return False

    clean_id = str(identifier).strip()
    try:
        from core.database import get_castle, update_castle_config
        c = get_castle(clean_id)
        if not c:
            log.warning(f"⚠️ القلعة غير مسجلة في قاعدة البيانات ({clean_id}).")
            return False

        cid = c.get("castle_id")
        if not cid:
            return False

        # الحفاظ على رقم التشكيلة المسجل مسبقاً للقلعة
        existing_formation = 1
        raw_cfg = c.get("config")
        if isinstance(raw_cfg, str):
            try:
                import json
                raw_cfg = json.loads(raw_cfg)
            except Exception:
                raw_cfg = {}
        if isinstance(raw_cfg, dict):
            elf_val = raw_cfg.get("elf")
            if isinstance(elf_val, dict):
                existing_formation = int(elf_val.get("formation_id", 1))

        patch = {
            "elf": {
                "enabled": False,
                "formation_id": existing_formation,
            }
        }
        res = update_castle_config(cid, patch)
        ok = bool(res.get("success", False)) if isinstance(res, dict) else bool(res)
        if ok:
            log.info(f"🛑 تم بنجاح تعطيل مهمة العفريت للقلعة {clean_id} (elf.enabled = False) في قاعدة البيانات.")
        return ok
    except Exception as e:
        log.error(f"❌ خطأ أثناء تعطيل مهمة العفريت للقلعة {clean_id}: {e}")
        return False

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
        "alliance_treasure",        # صندوق التحالف المجاني تلقائياً في كل دورة
        "daily_luxury_gift",        # استلام الهدية الفاخرة اليومية تلقائياً في كل دورة
        "vip_gift",            # استلام صندوق الـ VIP المجاني تلقائياً في كل دورة
    }

    def __init__(
        self,
        account_or_email: Union[str, AccountSession],
        config: Optional[Dict[str, Any]] = None,
        reconnect_wait_seconds: int = 250,
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
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_stop_event: Optional[asyncio.Event] = None

        # ── خصائص التشغيل اللحظية الحية في الذاكرة (Direct Thread Monitoring) ──
        self.start_time: float = time.time()
        self.iteration: int = 1
        self.loop_interval_minutes: int = 40
        self.conn_state: str = "starting"
        self.status_message: str = "جاري بدء التشغيل..."
        self.next_run_time: Optional[str] = None
        self.reconnect_attempt: int = 0
        self.last_activity_time: float = time.time()
        self.last_heartbeat: float = time.time()
        self.current_task: Optional[str] = None
        self.current_task_name: Optional[str] = None

    def get_lord_stamina(self) -> int:
        """جلب طاقة اللورد من الذاكرة الحية مباشرة."""
        base = self.conn.init_data.get("lordInfoCtrl", {}).get("base", {})
        return int(float(base.get("health", 100)))
        
    def _update_bot_conn_state(self, conn_state: str, message: str = "", next_run_time: Optional[str] = None) -> None:
        """إبلاغ لوحة التحكم وقاعدة البيانات المحلية بحالة اتصال اللعبة الفعلية (دخول، انقطاع، إعادة اتصال، انتظار)."""
        # تحديث الحالة اللحظية في الذاكرة فوراً
        self.conn_state = conn_state
        self.status_message = message
        self.next_run_time = next_run_time
        self.last_activity_time = time.time()
        self.last_heartbeat = time.time()

        # 🛑 حظر صارم ولحظي: إذا طُلب إيقاف البوت، يُمنع منعاً باتاً بث أو تسجيل أي حالة نشطة (connected / reconnecting / waiting)
        if self._stop_event.is_set() and conn_state in ("connected", "reconnecting", "waiting", "waiting_next_cycle"):
            return

        nr_arg = f" next_run_time={next_run_time}" if next_run_time else ""
        event_line = f"[BOT_EVENT] conn_state={conn_state} message={message}{nr_arg}"
        # Thread Pool: توجيه عبر log_callback / CLI: print() مباشرة
        if getattr(self, "_log_callback", None):
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

    def get_live_info(self) -> Dict[str, Any]:
        """
        استخراج بيانات التشغيل الحية اللحظية من داخل كائن البوت نفسه في الذاكرة (Live Thread Memory).
        حصر الحالات بدقة في الحالات الست المعتمدة وفق Requirement R2:
        1. Running (تنفيذ فعلي لمهمة محددة)
        2. Waiting for Next Cycle (انتظار موعد الدورة القادمة مع التوقيت)
        3. Other Device Login (تعليق مؤقت بسبب دخول من جهاز آخر)
        4. Reconnecting (محاولات إعادة اتصال حقيقية)
        5. Waiting for Re-login (انتظار إعادة تسجيل الدخول لمشكلة مصادقة)
        6. Starting (فترة بدء حقيقية ومحددة دون بقاء معلق)
        """
        now = time.time()
        start_ts = getattr(self, "start_time", now)
        uptime_sec = int(now - start_ts)
        is_stopped = self._stop_event.is_set()

        state = getattr(self, "conn_state", "starting")
        kick_reason = getattr(self, "_last_kick_reason", "")
        status_msg = getattr(self, "status_message", "")
        next_run = getattr(self, "next_run_time", None)
        conn_alive = bool(self.conn and self.conn.is_connected)
        reconn_att = getattr(self, "reconnect_attempt", 0)
        cur_task = getattr(self, "current_task", None)
        cur_task_name = getattr(self, "current_task_name", None)

        last_hb = getattr(self, "last_heartbeat", getattr(self, "last_activity_time", start_ts))

        # فحص عزل الخيوط المتعطلة (Stalled detection)
        # القاعدة: أي خيط حي يظهر في العمليات الحية بغض النظر عن حالة البوت.
        # is_stalled = True فقط إذا تلقّى الخيط إشارة إيقاف ولم يمت بعد (خيط عالق فعلاً).
        is_stalled = is_stopped and uptime_sec > 15

        # تصنيف دقيق للحالات الست المعتمدة:
        if state == "reconnecting" or (reconn_att > 0 and state != "connected" and not conn_alive):
            live_category = "reconnecting"
            category_label = "جاري إعادة الاتصال"
        elif state == "waiting_relogin" or "إعادة تسجيل الدخول" in status_msg or "re-login" in status_msg.lower():
            live_category = "waiting_relogin"
            category_label = "بانتظار إعادة تسجيل الدخول"
        elif state in ("other_device_login", "disconnected") or "جهاز آخر" in status_msg or "other device" in kick_reason.lower() or "تسجيل الدخول" in kick_reason:
            live_category = "other_device_login"
            category_label = "دخول من جهاز آخر"
        elif state in ("waiting_next_cycle", "waiting", "cycle_wait") or next_run:
            live_category = "waiting_next_cycle"
            category_label = "بانتظار الدورة التالية"
        elif conn_alive or cur_task or state in ("connected", "running"):
            live_category = "running"
            category_label = "شغالة فعلياً"
        elif state == "starting" or (now - start_ts) < 45:
            live_category = "starting"
            category_label = "جاري بدء التشغيل"
        else:
            live_category = "running"
            category_label = "شغالة فعلياً"

        return {
            "castle_id": getattr(self, "castle_id", ""),
            "email": getattr(self, "email", ""),
            "user_id": getattr(self, "user_id", ""),
            "state": state,
            "live_category": live_category,
            "category_label": category_label,
            "current_step": cur_task_name or cur_task or ("تنفيذ المهام" if live_category == "running" else None),
            "status_message": status_msg,
            "iteration": getattr(self, "iteration", 1),
            "loop_interval_minutes": getattr(self, "loop_interval_minutes", 40),
            "next_run_time": next_run,
            "reconnect_attempt": reconn_att,
            "max_reconnect_attempts": getattr(self, "max_reconnect_attempts", 10),
            "last_kick_reason": kick_reason,
            "uptime_seconds": uptime_sec,
            "is_connection_alive": conn_alive,
            "is_stopped": is_stopped,
            "is_stalled": is_stalled,
            "last_heartbeat": last_hb,
            "start_time": start_ts,
        }

    def stop(self) -> None:
        """إيقاف فوري ولحظي للبوت وقطع مقبس الاتصال فوراً لإنهاء أي مهمة أو انتظار دون أي تأخير."""
        self._stop_event.set()

        def _do_abort():
            if self._async_stop_event is not None and not self._async_stop_event.is_set():
                self._async_stop_event.set()
            if self.conn:
                try:
                    self.conn.abort()
                except Exception:
                    pass

        # إذا كان هناك Event Loop نشط في خيط البوت، أرسل له أمر الإلغاء فوراً عبر call_soon_threadsafe
        if self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(_do_abort)
            except Exception:
                pass

        # وأيضاً ننفذ abort مباشرة من هذا الخيط لقطع السوكت في 0 مللي ثانية
        if self.conn:
            try:
                self.conn.abort()
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

                        # 🛡️ استخراج الموارد الآمنة والمكشوفة
            safe_food    = int(float(saferes.get("1002", 0) or 0))
            safe_wood    = int(float(saferes.get("1003", 0) or 0))
            safe_iron    = int(float(saferes.get("1004", 0) or 0))
            safe_diamond = int(float(saferes.get("1005", 0) or 0))

            unprotected_food    = max(0, food - safe_food)
            unprotected_wood    = max(0, wood - safe_wood)
            unprotected_iron    = max(0, iron - safe_iron)
            unprotected_diamond = max(0, diamond - safe_diamond)

            from datetime import timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            res_data = {
                "food":                 food,
                "wood":                 wood,
                "iron":                 iron,
                "diamond":              diamond,
                "gold":                 gold,
                "stamina":              stamina,
                "safe_food":            safe_food,
                "safe_wood":            safe_wood,
                "safe_iron":            safe_iron,
                "safe_diamond":         safe_diamond,
                "unprotected_food":     unprotected_food,
                "unprotected_wood":     unprotected_wood,
                "unprotected_iron":     unprotected_iron,
                "unprotected_diamond":  unprotected_diamond,
                "last_updated":         now_iso,
            }

            cinfo_data = {
                "lord_name":    str(base_info.get("nickName", self.email.split("@")[0])),
                "lord_power":   int(fc_info.get("totalFc", 0)),
                "castle_level": int(fc_info.get("level", 0)),
                "server_id":    int(base_info.get("partition", 1)) if str(base_info.get("partition", "")).isdigit() else 1,
                "coordinates":  coords,
                "uid":          str(base_info.get("uid", getattr(self.account, "user_id", ""))),
                "avatar":       str(base_info.get("avatar", "") or ""),
                "image_id":     int(base_info.get("imageId", 0) or 0),
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

    def disable_elf_task(self, castle_id_or_email: Optional[str] = None) -> bool:
        """
        تعطيل مهمة العفريت للقلعة الحالية (أو المحددة) في قاعدة البيانات والذاكرة الحية للبوت:
        يضبط 'elf': {'enabled': False} مع الحفاظ التام على رقم التشكيلة وبقية الإعدادات.
        """
        cid = castle_id_or_email or getattr(self, "castle_id", None) or getattr(self, "email", None)
        ok = disable_elf_task(cid)
        if isinstance(self.config, dict) and "elf" in self.config:
            if isinstance(self.config["elf"], dict):
                self.config["elf"]["enabled"] = False
        return ok


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

    async def is_event_active(self, activity_id: str = "9001083") -> Tuple[bool, str]:
        """
        التحقق الفوري من حالة حدث نخبة العفريت (أو أي حدث بالمعرف) عبر الذاكرة الحية (Zero-Request):
        يتم فحص وحدة التحكم activityShowCtrl بالذاكرة الحية ومزامنة إشعارات السيرفر
        للمعرف الرسمي للحدث 9001083 (elite_boss_title_01).
        حالات الفعالية الرسمية (gActivityState):
          - state = 3 (OPEN): الحدث مفتوح ونشط حالياً في المملكة.
          - state = 2 (PREPARE): الحدث في مرحلة الاستعداد/المعاينة قبل البدء.
          - state = 1 (CLOSE): الحدث مغلق أو منتهٍ.
        """
        ELF_ACTIVITY_ID = str(activity_id)
        is_elf = (ELF_ACTIVITY_ID == "9001083")
        event_title = "حدث نخبة العفريت" if is_elf else f"الحدث ({ELF_ACTIVITY_ID})"

        if not self.conn:
            return False, f"{event_title}: لا يوجد اتصال نشط بالسيرفر"

        init_data = getattr(self.conn, 'init_data', {}) or {}
        act_show = init_data.get('activityShowCtrl', {})

        # 1. جلب البيانات الأولية من الذاكرة الحية
        act_info = dict(act_show.get(ELF_ACTIVITY_ID, {})) if isinstance(act_show, dict) and isinstance(act_show.get(ELF_ACTIVITY_ID), dict) else {}

        # 2. فحص أحدث إشعارات السيرفر المباشرة لتحديث الحالة بالثانية (NOTIFY_ACTIVITY_SHOW_CHANGE_TIME)
        cached_packets = getattr(self.conn, 'cached_packets', {}) or {}
        for p in cached_packets.values():
            if isinstance(p, dict):
                d = p.get('data', {})
                if isinstance(d, dict) and d.get('notifyID') == 'NOTIFY_ACTIVITY_SHOW_CHANGE_TIME':
                    nd = d.get('notifyData') or d.get('data') or []
                    items = nd if isinstance(nd, list) else [nd]
                    for item in items:
                        if isinstance(item, dict) and ELF_ACTIVITY_ID in item:
                            val = item[ELF_ACTIVITY_ID]
                            if isinstance(val, dict):
                                act_info.update(val)

        # إذا كانت بيانات الفعاليات غير متوفرة إطلاقاً بالذاكرة الحية (حالات نادرة جداً قبل التهيئة)
        if not act_show or not isinstance(act_show, dict):
            return True, f"بيانات الفعاليات بالذاكرة الحية قيد التحميل — المتابعة المباشرة"

        if not act_info:
            return False, f"{event_title} غير مدرج في جدول فعاليات السيرفر الحالية (معرف {ELF_ACTIVITY_ID})"

        state = int(act_info.get('state', 1))
        begintime = int(act_info.get('begintime', 0))
        endtime = int(act_info.get('endtime', 0))
        now = time.time()

        if state == 3:
            if endtime > 0 and now >= endtime:
                end_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(endtime))
                return False, f"{event_title} انتهى وقته (انتهى عند {end_str})"
            left_seconds = max(0, int(endtime - now)) if endtime > 0 else 0
            left_str = f" (متبقي {left_seconds // 3600}س و{(left_seconds % 3600) // 60}د)" if left_seconds > 0 else ""
            return True, f"{event_title} نشط ومفتوح في المملكة{left_str}"
        elif state == 2:
            begin_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(begintime)) if begintime > 0 else "قريباً"
            return False, f"{event_title} في مرحلة التحضير ولم يبدأ بعد (سيبدأ عند {begin_str})"
        else:
            return False, f"{event_title} مغلق حالياً على السيرفر (state=CLOSE)"

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
        self._last_kick_reason = display_reason
        if not self._log_callback:
            print("\n" + "!" * 70)
        log.warning(f"⚠️ [انقطاع الاتصال] تم رصد انقطاع الاتصال بالحساب (السبب: {display_reason})!")
        log.warning(f"⏳ سيتوقف البوت مؤقتاً وينتظر {self.reconnect_wait_seconds} ثانية...")
        if not self._log_callback:
            print("!" * 70 + "\n")

        self._update_bot_conn_state("disconnected", f"تم تسجيل الدخول من جهاز آخر: {display_reason}")

        for attempt in range(1, self.max_reconnect_attempts + 1):
            self.reconnect_attempt = attempt
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
        self.conn.log_callback = self._log_callback
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
                self.conn.log_callback = self._log_callback
                ok = await self.conn.connect()
                if self._stop_event.is_set():
                    if self.conn:
                        try:
                            await self.conn.close()
                        except Exception:
                            pass
                    return False

        if not ok:
            from core.session_manager import get_last_auth_error
            auth_err = get_last_auth_error(self.email)
            if not auth_err:
                auth_err = "❌ فشل تسجيل الدخول أو الاتصال بسيرفر اللعبة (تحقق من البريد وكلمة المرور)"
            self.last_auth_error = auth_err
            log.error(f"❌ [تسجيل الدخول] فشل الاتصال بالحساب {self.email}: {auth_err}")
            self._update_bot_conn_state("error", auth_err)
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


    async def _wait_for_stop_signal(self) -> None:
        """مراقب غير متزامن فائق السرعة يستيقظ فوراً عند طلب إيقاف البوت من خارج الـ Thread."""
        if self._stop_event.is_set():
            return
        if self._async_stop_event is not None:
            await self._async_stop_event.wait()
            return
        while not self._stop_event.is_set():
            await asyncio.sleep(0.05)

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
            ("🚢 مهمة الميناء (Port Task)",                     self.step_4_port_task_1,                 "port"),
            ("⚔️ مهمة تدريب الجنود (Train Troops)",             self.step_5_train_task,                "train"),
            ("🐾 مهمة دورية الحيوان الأليف (Pet Patrol)",        self.step_6_pet_patrol_task,           "pet_patrol"),
            ("🚩 جوائز التوسع الإقليمي (Territory Expansion)",   self.step_7_territory_expansion_task,  "territory_expansion"),
            ("🎰 صندوق مشعل رويال (Royal Torch Chest)",         self.step_7b_torch_chest_task,        "torch_chest"),
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
            ("🚢 مهمة الميناء (Port Task)",                     self.step_4_port_task_2,                 "port"),
            ("🔨 ورشة المواد (Material Workshop)",               self.step_15_material_workshop_task,   "material_workshop"),
            ("🐪 القافلة وحراسة الكنز (Caravan Task)",           self.step_16_caravan_task,             "caravan"),
            ("⚓ الميناء العسكري (Port Delegate)",               self.step_18_port_delegate_task,       "port_delegate"),
            ("🏦 دار الادخار (Savings Bank)",                   self.step_19_savings_bank_task,        "savings_bank"),
            ("🏗️ ترقية المباني (Building Upgrade)",             self.step_20_building_task,            "building"),
            ("🎖️ مهام الهيبة اليومية (Prestige Quests)",        self.step_22_prestige_task,            "prestige"),
            ("🎁 استلام صناديق الهيبة (Prestige Boxes)",         self.step_22c_prestige_box_task,       "prestige_box"),
            ("🧭 رحلات وتكليف الأبطال (Hero Consign)",          self.step_22c2_hero_consign_task,      "hero_consign"),
            ("🏛️ كنز طروادة (Troy Treasure)",                  self.step_22d_troy_treasure_task,      "troy_treasure"),
            ("🏥 معالجة الجنود بالمشفى (Hospital Cure)",        self.step_22b_hospital_task,           "hospital"),
            ("📬 جمع وحذف البريد (Mail Collect & Clean)",       self.step_22e_mail_task,               "mail"),
            ("🛒 استبدال متجر المحارب (Warrior Exchange)",      self.step_22f_warrior_exchange_task,   "warrior_exchange"),
            ("🕊️ المزايدة على الحمام الزاجل (Auction Bid)",     self.step_22h_auction_task,            "auction"),
            ("🎖️ منسق الفيالق والمسيرات (March Orchestrator)", self.step_23_march_manager_task,     "march_manager"),
            ("🚢 مهمة الميناء - منتصف الدورة (Port Task - Mid)", self.step_4_port_task_3,           "port"),
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
            self.current_task = task_key
            self.current_task_name = step_name
            self.last_heartbeat = time.time()

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
            for _ in range(5):
                if self._stop_event.is_set():
                    break
                await asyncio.sleep(1.5)

        self.current_task = None
        self.current_task_name = None
        self.last_heartbeat = time.time()
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

        # فحص مبنى الأكاديمية (113) في الذاكرة الحية بنمط Zero-Request
        blist = self.conn.init_data.get("cityCtrl", {}).get("blist", []) if self.conn and hasattr(self.conn, "init_data") else []
        has_academy = any(
            str(b.get("binfo", {}).get("bid")) == "113"
            and str(b.get("binfo", {}).get("state")) != "8"
            and int(b.get("binfo", {}).get("lv", 0)) >= 1
            for b in blist if isinstance(b, dict)
        )
        if not has_academy:
            msg = "⏭️ تم تخطي أبحاث الأكاديمية: مبنى الأكاديمية (113) غير مشيّد أو مقفل بعد."
            log.info(msg)
            return {"skipped": True, "message": msg}

        task_cfg = {
            "enabled": True,
            "tree": res_cfg.get("tree", "balanced"),
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

        # فحص معرف التحالف من السياق أو مباشرة من الذاكرة الحية (Zero-Request)

        alliance_ctrl = self.conn.init_data.get('allianceCtrl', {})
        minfo = alliance_ctrl.get('memberinfo', {}).get('minfo', {})
        alliance_id = int(minfo.get('aid', 0))

        if alliance_id == 0:
            msg = "⏭️ تم تخطي مهمة التحالف لأن الحساب غير منضم لأي تحالف."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # 🤝 [السفارة] مساعدة جميع أعضاء التحالف بضغطة زر واحدة (1010/47) عند وجود طلبات في الذاكرة الحية
        if bool(all_cfg.get("auto_help", True)):
            try:
                helplist = self.conn.init_data.get("allianceCtrl", {}).get("helplist", [])
                my_uid = int(self.conn.uid or 0)
                
                # فحص الذاكرة الحية: هل يوجد طلب متاح للمساعدة؟
                has_pending_help = any(
                    isinstance(item, dict)
                    and int(item.get("uid", 0)) != my_uid
                    and int(item.get("curHp", 0)) < int(item.get("totalHp", 0))
                    and my_uid not in (item.get("helper") or [])
                    for item in helplist
                ) if isinstance(helplist, list) else True

                if has_pending_help:
                    r_help_all = await self.conn.query("1010", "47", {}, timeout=8)
                    if r_help_all and str(r_help_all.get("err", "0")) == "0":
                        log.info("🤝 [السفارة] تم إرسال مساعدة الكل لأعضاء التحالف بنجاح (1010/47) ✅")
                    else:
                        log.debug(f"🤝 استجابة مساعدة الكل (1010/47): {r_help_all}")
                else:
                    log.info("🤝 [السفارة] لا توجد طلبات مساعدة معلقة بالحلف في الذاكرة الحية.")
            except Exception as e:
                log.warning(f"⚠️ خطأ غير حرج أثناء فحص/إرسال مساعدة التحالف (1010/47): {e}")

        log.info(f"🤝 بدء تنفيذ مهمة التحالف (المساعدة والتبرع لعلوم التحالف")
        task_cfg = {
            "enabled": True,
            "auto_help": False,  # تم إرسال مساعدة الكل مسبقاً وفورياً عبر 1010/47
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
    async def step_4_port_task_1(self) -> Dict[str, Any]:
        """فحص وتنفيذ مهمة الميناء التجارية لكافة السفن المتاحة."""
        port_cfg = self.config.get("port", {})
        if not bool(port_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الميناء بناءً على رغبة المستخدم (port.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # فحص جاهزية سفينة الميناء في الذاكرة الحية بالاعتماد على توقيت الوصول
        tr = self.conn.init_data.get("timeRewardCtrl", {})
        tr_data = tr.get("data", tr) if isinstance(tr, dict) else {}
        if tr_data.get("isAllReceive") == 1:
            return {"skipped": True, "message": "⏭️ تم استلام جميع سفن الميناء لهذا اليوم."}
        now_ts = time.time()
        rec_time = float(tr_data.get("receiveTime", 0))
        if rec_time > now_ts:
            rem = int(rec_time - now_ts)
            return {"skipped": True, "message": f"⏳ سفينة الميناء في الطريق (متبقي {rem} ثانية)."}

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

        # فحص حالة دورية الحيوان في الذاكرة الحية وتخطيها فوراً إذا كانت جارية
        patrol_info = (self.conn.init_data.get("petCtrl") or {}).get("petPatrolInfo") or {}
        if int(patrol_info.get("endTime", 0)) > time.time():
            remaining_min = (int(patrol_info["endTime"]) - int(time.time())) // 60
            log.info(f"⏭️ تم تخطي مهمة الحيوان: لا يزال في دورية نشطة (متبقي {remaining_min} دقيقة).")
            return {"skipped": True, "message": f"الحيوان في دورية حالياً (متبقي {remaining_min} دقيقة)"}


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

        # فحص حدث التوسع الإقليمي (9001373) والجوائز الجاهزة في الذاكرة الحية (Zero-Request)
        aty_mgr = self.conn.init_data.get("generalAtyMgr", {}) if self.conn and hasattr(self.conn, "init_data") else {}
        exp_aty = aty_mgr.get("9001373") or aty_mgr.get(9001373, {})
        quests = exp_aty.get("data", {}).get("quests", {}) if isinstance(exp_aty, dict) else {}

        if not quests:
            msg = "⏭️ تم تخطي جوائز التوسع الإقليمي: حدث التوسع غير متاح أو منتهٍ في الحساب حالياً."
            log.info(msg)
            return {"skipped": True, "message": msg}

        has_ready = any(int(q.get("status", 0)) == 3 for q in quests.values() if isinstance(q, dict))
        is_all_events = bool(self.config.get("territory_expansion", {}).get("all_events", False))

        if not has_ready and not is_all_events:
            msg = "⏭️ تم تخطي جوائز التوسع الإقليمي: لا توجد أي مكافآت جاهزة للاستلام حالياً."
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

    # [7b] مهمة صندوق مشعل رويال (شراء وفتح)
    async def step_7b_torch_chest_task(self) -> Dict[str, Any]:
        """فحص وشراء وفتح صندوق مشعل رويال في المتجر والحقيبة."""
        torch_cfg = self.config.get("torch_chest", {})
        open_cfg = self.config.get("open_torch_chest", {})

        buy_enabled = bool(torch_cfg.get("enabled", False))
        open_enabled = bool(open_cfg.get("enabled", False))

        if not buy_enabled and not open_enabled:
            msg = "⏭️ تم تخطي مهمة صندوق مشعل رويال بناءً على رغبة المستخدم (torch_chest و open_torch_chest غير مفعّلين)."
            log.info(msg)
            return {"skipped": True, "message": msg}

                # فحص إمكانية الشراء والفتح لصندوق مشعل رويال في الذاكرة الحية (Zero-Request)
        init = getattr(self.conn, "init_data", {}) or {}
        now_ts = int(time.time())

        # 1. التحقق من توفر الشراء من المتجر (Item 1000182)
        can_buy = False
        if buy_enabled:
            shop_data = init.get("itemShop", {}).get("configData", {})
            t_item = shop_data.get("1000182") or shop_data.get(1000182, {})
            if isinstance(t_item, dict) and t_item:
                endtime = int(t_item.get("endtime", 0))
                limit_num = int(t_item.get("limitNum", 15))
                buy_mgr = init.get("shopItemBuyTimesMgr", {})
                buy_entry = buy_mgr.get("1000182") or buy_mgr.get(1000182, {})
                bought = int(buy_entry.get("buyNum", 0)) if isinstance(buy_entry, dict) else 0
                if (endtime == 0 or now_ts < endtime) and (bought < limit_num):
                    can_buy = True

        # 2. التحقق من وجود صناديق بالحقيبة لفتحها (Item 811037)
        bag_count = 0
        if open_enabled:
            bp = init.get("backpackCtrl", {})
            if isinstance(bp, dict):
                item_entry = bp.get("811037") or bp.get(811037, {})
                if isinstance(item_entry, dict):
                    bag_count = int(item_entry.get("count", 0))

        can_open = open_enabled and (bag_count > 0 or can_buy)

        if not can_buy and not can_open:
            msg = "⏭️ تم تخطي مهمة مشعل رويال: الصندوق غير متاح للشراء بالمتجر ولا توجد صناديق بالحقيبة لفتحها."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info(f"🎰 بدء مهمة صندوق مشعل رويال (الشراء: {'مفعّل' if buy_enabled else 'معطّل'} | الفتح: {'مفعّل' if open_enabled else 'معطّل'})...")
        combined_cfg = {
            "buy_enabled": buy_enabled,
            "open_enabled": open_enabled,
        }
        task = TorchChestTask(self.conn, combined_cfg)
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة صندوق مشعل رويال: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في صندوق مشعل رويال: {res.message}")

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
        """استهلاك جرعات الطاقة المجانية من الحقيبة وتنفيذ شراء الطاقة بالذهب وفق الإعدادات والذاكرة الحية."""
        stamina_cfg = self.config.get("stamina", {})
        if not bool(stamina_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الطاقة بناءً على رغبة المستخدم (stamina.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        use_free = bool(stamina_cfg.get("use_free", True))
        gold_buys = int(stamina_cfg.get("gold_buys", stamina_cfg.get("gold", 0)))
        max_price = int(stamina_cfg.get("max_price", stamina_cfg.get("price_limit", stamina_cfg.get("max_exchange_price", stamina_cfg.get("gold_limit", 0)))))

        # قراءة بيانات تبديل الطاقة بالذهب مباشرة من الذاكرة الحية (Zero-Request)
        bs_ctrl = self.conn.init_data.get("buyStaminaCtrl", {}) if (self.conn and getattr(self.conn, "init_data", None)) else {}
        buy_times = int(bs_ctrl.get("buyTimes", 0))
        limit_times = int(bs_ctrl.get("limitTimes", 30))
        current_price = int(bs_ctrl.get("price", 0))

        # حساب عدد عمليات الشراء بالذهب المتبقية
        remaining_buys = 0
        if gold_buys > 0:
            if limit_times > 0 and buy_times >= limit_times:
                log.info(f"ℹ️ استنفاد الحد اليومي لشراء الطاقة بالذهب ({buy_times}/{limit_times}).")
            elif max_price > 0 and current_price > max_price:
                log.info(f"ℹ️ سعر شراء الطاقة الحالي ({current_price} ذهب) يتجاوز الحد الأقصى ({max_price} ذهب).")
            else:
                remaining_buys = max(0, gold_buys - buy_times)

        # فحص رصيد جرعات الطاقة في الحقيبة من الذاكرة الحية (Zero-Request)
        bp = self.conn.init_data.get("backpackCtrl", {}) if (self.conn and getattr(self.conn, "init_data", None)) else {}
        potions_count = 0
        if isinstance(bp, dict):
            for pid in ("300401", "300402", "300403"):
                item = bp.get(pid)
                if isinstance(item, dict):
                    potions_count += int(item.get("count", 0) or 0)

        # إذا كانت الحقيبة خالية من الجرعات (أو استخدامها معطل) ولا توجد عمليات شراء بالذهب متبقية -> تخطي فوري
        if (not use_free or potions_count == 0) and remaining_buys <= 0:
            msg = f"⏭️ تم تخطي مهمة الطاقة: الحقيبة خالية من الجرعات ولا توجد عمليات شراء بالذهب مطلوبة (تم {buy_times}/{gold_buys})."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info(f"⚡ بدء مهمة الطاقة (الجرعات المتوفرة بالحقيبة: {potions_count} | الشراء بالذهب المتبقي: {remaining_buys} [تم {buy_times}/{gold_buys}])...")

        task = StaminaTask(self.conn, {
            "use_free": use_free,
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
        alliance_cfg = self.config.get("alliance", {}) if isinstance(self.config.get("alliance"), dict) else {}
        combined_cfg = {**at_cfg, "alliance": alliance_cfg}
        if "open_treasure" in alliance_cfg and "open_treasure" not in combined_cfg:
            combined_cfg["open_treasure"] = alliance_cfg["open_treasure"]
        log.info("📦 بدء مهمة صندوق التحالف (Alliance Treasure)...")
        task = AllianceTreasureTask(self.conn, combined_cfg)
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
        """فحص واستلام سحوبات كتب التكتيكات المجانية وأبحاث التكتيكات المكتملة وبدء البحث التكتيكي المحدد."""
        th_cfg = self.config.get("tactics_hall", {})
        if not bool(th_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة قاعة الاستراتيجيات بناءً على رغبة المستخدم (tactics_hall.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        target_tactic = th_cfg.get("tactic") or th_cfg.get("mid", "القلعة الفارغة")
        target_mid = parse_tactic_choice(target_tactic)
        t_meta = TACTICS_MAP.get(target_mid, {"name_ar": str(target_tactic), "category": "", "icon": "📜"})

        log.info(f"🏛️ بدء مهمة قاعة الاستراتيجيات للبحث المطلوب: {t_meta.get('icon', '📜')} [{t_meta.get('name_ar', target_tactic)}]...")

        task = TacticsHallTask(self.conn, {"tactic": target_mid, "collect_free": True})
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

        lord_ctrl = self.conn.init_data.get("lordInfoCtrl", {})
        base_info = lord_ctrl.get("base", {})
        castle_lv = base_info.get("level", 0)
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

    # [4] مهمة الميناء
    async def step_4_port_task_2(self) -> Dict[str, Any]:
        """فحص وتنفيذ مهمة الميناء التجارية لكافة السفن المتاحة."""
        port_cfg = self.config.get("port", {})
        if not bool(port_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الميناء بناءً على رغبة المستخدم (port.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # فحص جاهزية سفينة الميناء في الذاكرة الحية بالاعتماد على توقيت الوصول
        tr = self.conn.init_data.get("timeRewardCtrl", {})
        tr_data = tr.get("data", tr) if isinstance(tr, dict) else {}
        if tr_data.get("isAllReceive") == 1:
            return {"skipped": True, "message": "⏭️ تم استلام جميع سفن الميناء لهذا اليوم."}
        now_ts = time.time()
        rec_time = float(tr_data.get("receiveTime", 0))
        if rec_time > now_ts:
            rem = int(rec_time - now_ts)
            return {"skipped": True, "message": f"⏳ سفينة الميناء في الطريق (متبقي {rem} ثانية)."}

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
            "claim_time_reward": True,
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

        raw_deposit = sb_cfg.get("deposit")
        try:
            deposit_val = int(raw_deposit) if raw_deposit is not None else 2000
            deposit_val = max(100, min(6000, deposit_val))
        except (ValueError, TypeError):
            deposit_val = 2000

        plan_info = SAVINGS_PLANS.get(target_days, SAVINGS_PLANS[DEFAULT_SAVINGS_DAYS])
        log.info(f"🏦 بدء مهمة دار الادخار (فحص الأرباح وإيداع الذهب بخطة: {plan_info['name']} بمبلغ: {deposit_val:,} ذهب)...")

        task = SavingsBankTask(self.conn, {"days": target_days, "deposit": deposit_val})
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
          - تبديل القمح بوسام الحرب (CMD 1067/2) مرة واحدة يومياً.
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


    async def step_22c2_hero_consign_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة رحلات وتكليف الأبطال (Hero Voyage & Consign):
          1. رحلات الأبطال (الترحال حتى 10 مرات يومياً بفاصل ثانيتين).
          2. استلام جوائز مهام التكليف المنجزة (CMD 3148 / SUB 5).
          3. إطلاق مهام تكليف الأبطال (حتى 5 مهام يومياً) واستلام الصندوق التراكمي (15 مهمة).
        """
        cfg = self.config.get("hero_consign", {})
        if isinstance(cfg, bool):
            cfg = {"enabled": cfg}
        elif not isinstance(cfg, dict):
            cfg = {"enabled": False}

        if not bool(cfg.get("enabled", False)):
            msg = "⏭️ تم تخطي مهمة رحلات وتكليف الأبطال (hero_consign.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        log.info("🧭 بدء مهمة رحلات وتكليف الأبطال (Hero Voyage & Consign)...")
        task = HeroConsignTask(self.conn, cfg)
        await task.on_start()
        res = await task.run()

        if res.success:
            log.info(f"🎉 نتيجة رحلات وتكليف الأبطال: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في رحلات وتكليف الأبطال: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_22d_troy_treasure_task(self) -> Dict[str, Any]:
        return log.info(f"🎉 نتيجة كنز طروادة: ")


    async def step_22b_hospital_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة فحص ومعالجة الجنود الجرحى في المشفى (Hospital Cure Task):
          - دعم نمطين: "prestige" (علاج المتبقي للهيبة فقط) أو "all" (علاج كافة الجرحى الممكنين).
          - فحص استباقي لموارد القلعة لتحديد وعلاج ما يمكن علاجه دون تلقي أي أخطاء من السيرفر.
          - التحقق من وجود مبنى المشفى (bid: 206) وطابور العلاج (1202).
          - قراءة الجرحى مباشرة من الذاكرة الحية (init_data['armyCtrl']['woundedArmy']).
        """
        hosp_cfg = self.config.get("hospital", {})
        if isinstance(hosp_cfg, bool):
            hosp_cfg = {"enabled": hosp_cfg, "mode": "prestige"}
        elif not isinstance(hosp_cfg, dict):
            hosp_cfg = {"enabled": False, "mode": "prestige"}

        if not hosp_cfg.get("enabled", False):
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


    async def step_22e_mail_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة جمع جوائز بريد القلعة وحذف الرسائل (Mail Collect & Clean Task):
          - فحص صندوق البريد للتبويب المحدد (افتراضياً 4 = تقارير المعارك والموارد).
          - استخراج معرفات الرسائل غير المقفلة (midArray).
          - التخطي التلقائي السريع إذا كان البريد فارغاً.
          - جمع المكافآت دفعة واحدة عبر (1015/18).
          - انتظار 3 ثوانٍ قبل أمر الحذف لمحاكاة الإيقاع الطبيعي.
          - حذف الرسائل بعد الجمع عبر (1015/4).
        """
        mail_cfg = {
            "set_types": [4],
            "delete_after_collect": True,
            "wait_seconds": 3.0,
        }
        task = MailTask(self.conn, mail_cfg)
        _safe_bind_task_logger(task, self._log_callback, level=logging.INFO)

        try:
            res = await task.run()
        finally:
            _safe_unbind_task_logger(task)

        # إشعار لوحة التحكم وملف السجل فقط عند معالجة رسائل فعلية لتطبيق الصمت
        if self._log_callback and res.data and res.data.get("total_processed", 0) > 0:
            self._log_callback(f"📬 {res.message}")

        if res.success:
            log.info(f"🎉 نتيجة مهمة البريد: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة البريد: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_22f_warrior_exchange_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة استبدال منتج متجر المحارب في مركز المنافع (Warrior Shop Exchange Task):
          - فحص تفعيل المهمة في إعدادات الحساب (warrior_exchange.enabled).
          - فحص المسموح للاستبدال (limitnum - buyNum): إذا كان أقل من 15 يتم التخطي والإنهاء فوراً.
          - فحص توفر المواد المطلوبة بالحقيبة والاستبدال بأقصى عدد ممكن من العدد المطلوب (1-15).
        """
        we_cfg = self.config.get("warrior_exchange", {})
        if isinstance(we_cfg, bool):
            we_cfg = {"enabled": we_cfg, "count": 15}
        elif not isinstance(we_cfg, dict):
            we_cfg = {"enabled": False, "count": 15}

        if not bool(we_cfg.get("enabled", False)):
            msg = "⏭️ تم تخطي مهمة متجر المحارب بناءً على رغبة المستخدم (warrior_exchange.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        task = WarriorExchangeTask(self.conn, we_cfg)
        _safe_bind_task_logger(task, self._log_callback, level=logging.INFO)

        try:
            res = await task.run()
        finally:
            _safe_unbind_task_logger(task)

        # إشعار لوحة التحكم وملف السجل بالنتيجة المباشرة الصريحة
        if self._log_callback:
            self._log_callback(f"🛒 {res.message}")

        if res.success:
            log.info(f"🎉 نتيجة مهمة متجر المحارب: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة متجر المحارب: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_22h_auction_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة المزايدة التلقائية على الحمام الزاجل (#501901) وشظاياه (#503001) في سوق المملكة:
          - التحقق من تفعيل المهمة في إعدادات الحساب (auction.enabled).
          - التحقق من نشاط حدث المزاد في الذاكرة الحية (activityShowCtrl -> #9001034).
          - جلب بيانات المزاد واستدعاء AuctionTask للمزايدة أو سحب الذهب تلقائياً.
        """
        auction_cfg = self.config.get("auction", {})
        if isinstance(auction_cfg, bool):
            auction_cfg = {"enabled": auction_cfg, "max_gold": 2000}
        elif not isinstance(auction_cfg, dict):
            auction_cfg = {"enabled": False, "max_gold": 2000}

        # 1. التحقق من تفعيل المهمة
        if not bool(auction_cfg.get("enabled", False)):
            msg = "⏭️ تم تخطي مهمة المزاد (auction.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # 2. التحقق من نشاط حدث المزاد عبر الذاكرة الحية (Zero-Request)
        is_active, act_desc = await self.is_event_active("9001034")
        if not is_active:
            msg = f"⏭️ تخطي مهمة المزاد: {act_desc}."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # 3. تشغيل المهمة
        task = AuctionTask(self.conn, auction_cfg)
        _safe_bind_task_logger(task, self._log_callback, level=logging.INFO)

        try:
            res = await task.run()
        finally:
            _safe_unbind_task_logger(task)

        # إشعار لوحة التحكم وملف السجل فقط عند المزايدة أو السحب الفعلي
        if self._log_callback and not res.data.get("skipped", False) and res.data.get("reason") != "ITEM_NOT_IN_AUCTION":
            self._log_callback(f"🕊️ {res.message}")

        if res.success:
            log.info(f"🎉 نتيجة مهمة المزاد: {res.message}")
        else:
            log.warning(f"⚠️ تنبيه في مهمة المزاد: {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}


    async def step_23_march_manager_task(self) -> Dict[str, Any]:
        """
        تنفيذ مهمة منسق الفيالق والمسيرات الذكي الموحد (March Manager & Orchestrator):
          - إدارة الفيالق المتاحة وتوزيعها وفق مصفوفة أولويات ذكية ومخصصة.
          - قتال غزاة الهيبة (Prestige Invaders) عبر monster.py بعد استعلام إنجاز المهمة.
          - الهجوم على معقل الهيبة (Prestige Stronghold) مرتين كحد أقصى عبر stronghold.py بعد استعلام إنجاز المهمة.
          - تطبيق الحالات الخمس الصارمة (نفاذ الفيالق، نقص التشكيلة، انعدام الجيش، أخطاء متتالية، اكتمال الأولويات).
        """
        mm_cfg = self.config.get("march_manager", {})
        if isinstance(mm_cfg, bool):
            mm_cfg = {"enabled": mm_cfg}
        elif not isinstance(mm_cfg, dict):
            mm_cfg = {"enabled": True}

        # ─── الإضافة السحرية هنا: حقن حالة الهيبة الرئيسية داخل المنسق ───
        p_cfg = self.config.get("prestige", {})
        mm_cfg["is_main_prestige_enabled"] = p_cfg.get("enabled", True) if isinstance(p_cfg, dict) else True
        # ─────────────────────────────────────────────────────────────────

        if not mm_cfg.get("enabled", True):
            msg = "⏭️ تم تخطي مهمة منسق الفيالق (march_manager.enabled = False)."
            log.info(msg)
            return {"success": True, "message": msg, "skipped": True}

        task = MarchManagerTask(self.conn, mm_cfg)
        _safe_bind_task_logger(task, self._log_callback, level=logging.INFO)

        try:
            res = await task.run()
        finally:
            _safe_unbind_task_logger(task)

        # إشعار لوحة التحكم وملف السجل بالنتيجة المباشرة الصريحة دون تكرار
        if self._log_callback:
            self._log_callback(f"🎖️ {res.message}")

        return {"success": res.success, "message": res.message, "data": res.data}

    # [4] مهمة الميناء
    async def step_4_port_task_3(self) -> Dict[str, Any]:
        """فحص وتنفيذ مهمة الميناء التجارية لكافة السفن المتاحة."""
        port_cfg = self.config.get("port", {})
        if not bool(port_cfg.get("enabled", True)):
            msg = "⏭️ تم تخطي مهمة الميناء بناءً على رغبة المستخدم (port.enabled = False)."
            log.info(msg)
            return {"skipped": True, "message": msg}

        # فحص جاهزية سفينة الميناء في الذاكرة الحية بالاعتماد على توقيت الوصول
        tr = self.conn.init_data.get("timeRewardCtrl", {})
        tr_data = tr.get("data", tr) if isinstance(tr, dict) else {}
        if tr_data.get("isAllReceive") == 1:
            return {"skipped": True, "message": "⏭️ تم استلام جميع سفن الميناء لهذا اليوم."}
        now_ts = time.time()
        rec_time = float(tr_data.get("receiveTime", 0))
        if rec_time > now_ts:
            rem = int(rec_time - now_ts)
            return {"skipped": True, "message": f"⏳ سفينة الميناء في الطريق (متبقي {rem} ثانية)."}

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



    async def run_elf_boss_mode(self) -> bool:
        """
        فحص وتشغيل بوت العفريت المستقل ذي الأولوية:
        1. التحقق من تفعيل العفريت في قاعدة البيانات (elf.enabled).
        2. التحقق من سريان الحدث باللعبة عبر الذاكرة الحية (is_event_active).
        3. التحقق من أن طاقة اللورد أكثر من 30 (stamina > 30).
        4. الجدولة الذكية بحسب دقيقة التشغيل الحالية (حتى :40 أو 5د أو انتظار فوري لرأس الساعة).
        
        تعيد: True إذا تم تفعيل وتنفيذ وضع العفريت (لحظر المهام الأخرى)، و False إذا تم تعطيله والمتابعة للبوت العادي.
        """
        elf_cfg = self.config.get("elf", {})
        if not isinstance(elf_cfg, dict) or not bool(elf_cfg.get("enabled", False)):
            return False

        # إنشاء كائن مهمة العفريت
        elf_task = ElfBossTask(self.conn, elf_cfg)

        # الشرط 2: التحقق من سريان الحدث بالذاكرة الحية (Zero-Request)
        is_active, active_reason = await elf_task.is_event_active()
        if not is_active:
            msg = f"⚠️ [بوت العفريت] الحدث غير نشط على السيرفر ({active_reason}) — تم تعطيل مهمة العفريت ومتابعة البوت العادي."
            log.warning(f"[{self.email}] {msg}")
            self.disable_elf_task()
            if self._log_callback:
                self._log_callback(msg)
            return False

        # الشرط 3: التحقق من طاقة اللورد > 30 (Zero-Request)
        current_stamina = self.get_lord_stamina()
        if current_stamina <= 30:
            msg = f"⚠️ [بوت العفريت] طاقة اللورد غير كافية ({current_stamina}/30) — تم تعطيل مهمة العفريت ومتابعة البوت العادي."
            log.warning(f"[{self.email}] {msg}")
            self.disable_elf_task()
            if self._log_callback:
                self._log_callback(msg)
            return False

        # 🕒 4. حساب مدة الجلسة وفق دقيقة التشغيل الحالية
        now = datetime.now()
        cur_min = now.minute

        if cur_min >= 40:
            # النطاق الثالث: انتظار فوري للدورة القادمة حتى رأس الساعة
            wait_seconds = (60 - cur_min) * 60 - now.second
            wait_mins = max(1, wait_seconds // 60)
            wait_msg = f"⏳ [بوت العفريت] الساعة الآن {now:%H:%M} — في حالة انتظار الدورة التالية لرأس الساعة (متبقي {wait_mins} دقيقة)..."
            log.info(f"[{self.email}] {wait_msg}")
            if self._log_callback:
                self._log_callback(wait_msg)
            self._update_bot_conn_state("waiting", f"بانتظار رأس الساعة ({wait_mins}د)")
            if self._async_stop_event is not None:
                try:
                    await asyncio.wait_for(self._async_stop_event.wait(), timeout=max(5, wait_seconds))
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(max(5, wait_seconds))
            return True

        elif cur_min >= 35:
            # النطاق الثاني: هجوم سريع لمدة 5 دقائق
            attack_duration = 5.0
            start_msg = f"🧝 [بوت العفريت] تشغيل هجوم سريع لمدة 5 دقائق (طاقة اللورد: {current_stamina})..."
        else:
            # النطاق الأول: هجوم مستمر حتى الدقيقة 40:
            attack_duration = float(40 - cur_min)
            start_msg = f"🧝 [بوت العفريت] تشغيل الهجوم حتى الدقيقة 40: (المدة: {attack_duration:.0f} دقيقة | طاقة: {current_stamina})..."

        log.info(f"[{self.email}] {start_msg}")
        if self._log_callback:
            self._log_callback(start_msg)

        self._update_bot_conn_state("connected", "🧝 تشغيل بوت العفريت...")
        self.current_task = "elf_boss"
        self.current_task_name = "🧝 بوت نخبة العفريت"
        _safe_bind_task_logger(elf_task, self._log_callback, level=logging.INFO)

        # تمرير المدة المحسوبة بدقة لمهمة العفريت
        elf_task.config["duration"] = attack_duration

        try:
            elf_res = await elf_task.run()
            log.info(f"[{self.email}] 🏁 انتهت جلسة هجوم العفريت: {elf_res.message}")
        except Exception as ex:
            log.error(f"💥 خطأ أثناء تشغيل بوت العفريت: {ex}", exc_info=True)

        # بعد انتهاء الهجوم: الانتظار حتى رأس الساعة القادمة إذا بقي وقت
        now_after = datetime.now()
        if now_after.minute < 60 and not self._stop_event.is_set():
            remaining_wait = (60 - now_after.minute) * 60 - now_after.second
            if remaining_wait > 30:
                rem_mins = max(1, remaining_wait // 60)
                pause_msg = f"⏳ [بوت العفريت] اكتمال الهجمات — انتظار {rem_mins} دقيقة حتى بداية رأس الساعة القادمة..."
                log.info(f"[{self.email}] {pause_msg}")
                if self._log_callback:
                    self._log_callback(pause_msg)
                self._update_bot_conn_state("waiting", f"بانتظار رأس الساعة ({rem_mins}د)")
                if self._async_stop_event is not None:
                    try:
                        await asyncio.wait_for(self._async_stop_event.wait(), timeout=remaining_wait)
                    except asyncio.TimeoutError:
                        pass
                else:
                    await asyncio.sleep(remaining_wait)

        return True

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
            log.warning(f"🛑 [إيقاف التشغيل] {reason} — تعطيل القلعة وإيقاف البوت للحساب {self.email}...")
            try:
                import core.database as db
                if getattr(self, "castle_id", None):
                    db.toggle_castle_active(self.castle_id, is_active=False, user_id=getattr(self, "user_id", None))
            except Exception as ex:
                log.warning(f"⚠️ تعذر تعطيل القلعة في قاعدة البيانات: {ex}")
            self._update_bot_conn_state("idle", f"متوقف: {reason}")
            self.stop()
            return {"success": False, "error": reason}

        # التحقق من أن القلعة لا تزال نشطة في قاعدة البيانات ولم تُعطّل من الواجهة
        try:
            import core.database as db
            cid = getattr(self, "castle_id", None)
            uid = getattr(self, "user_id", None)
            if cid:
                c_rec = db.get_castle_by_id(cid, uid)
                if c_rec and not c_rec.get("is_active", True):
                    log.info(f"⏹️ القلعة {self.email} معطلة من لوحة التحكم — إنهاء التشغيل...")
                    self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                    self.stop()
                    return {"success": False, "error": "تم تعطيل القلعة"}
        except Exception:
            pass

        try:
            # 1. تسجيل الدخول
            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            connected = await self.login_and_connect()
            if not connected or self._stop_event.is_set():
                err = getattr(self, "last_auth_error", None) or "فشل الاتصال والمصادقة أو تم الإيقاف"
                return {
                    "success": False,
                    "is_auth_error": bool(getattr(self, "last_auth_error", None)),
                    "error": err,
                }

            # 2. الاستعلام الشامل
            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            # 2.5 تحديث بيانات وموارد القلعة في بداية الدورة مباشرة
            try:
                self.sync_castle_resources()
            except Exception as e:
                log.warning(f"⚠️ تنبيه أثناء تحديث موارد القلعة في بداية الدورة: {e}")

            # 🧝 2.8 فحص وتشغيل وضع بوت العفريت المستقل وفق الشروط الثلاثة والجدولة الذكية
            is_elf_handled = False
            if not self._stop_event.is_set():
                is_elf_handled = await self.run_elf_boss_mode()

            # 3. تنفيذ سلسلة المهام العادية (تُنفذ فقط إذا لم يكن العفريت مفعلاً أو تم تعطيله)
            if self._stop_event.is_set():
                return {"success": False, "error": "تم طلب إيقاف البوت"}

            if not is_elf_handled:
                pipeline_results = await self.execute_task_pipeline()
            else:
                pipeline_results = {"elf_boss": "تم تنفيذ وضع العفريت المستقل بنجاح وحظر المهام الأخرى"}

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
    
    # ─────────────────────────────────────────────────────────────────
    #  دورة التشغيل المستمر (Loop Mode)
    # ─────────────────────────────────────────────────────────────────

    async def run_loop(self, loop_interval_minutes: int = 40) -> None:
        """
        تشغيل مستمر لا ينتهي — ينفذ دورة كاملة ثم ينتظر مدة ثابتة (Delay) قبل الدورة التالية.
        هذا يعني أن العداد سيبدأ *بعد* انتهاء الدورة الحالية، وليس من بدايتها.

        ⚡ كفاءة عالية (مناسب لـ 1000+ حساب متزامن):
          - asyncio.sleep() لا يستهلك أي CPU أثناء الانتظار
          - يكتشف أخطاء الدورة ويستمر للدورة التالية بدلاً من الإيقاف

        Args:
            loop_interval_minutes: مدة الانتظار الثابتة بالدقائق بين الدورة والأخرى
        """
        self.is_loop = True
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        self._async_stop_event = asyncio.Event()

        iteration = 0
        # تحديد المدة الأساسية بالدقائق مع فرض الحدود الآمنة (30 إلى 180 دقيقة)
        base_mins = max(30, min(180, int(loop_interval_minutes or getattr(self, "loop_interval_minutes", 40) or 40)))
        self.loop_interval_minutes = base_mins

        log.info(f"🔁 وضع التشغيل المستمر نشط — دورة أساسية كل {self.loop_interval_minutes} دقيقة (+ عشوائي حتى 10 دقائق لحماية الحساب)")
        while not self._stop_event.is_set():
            iteration += 1
            self.iteration = iteration
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

            cycle_res = None
            try:
                cycle_res = await self.run_once()
            except Exception as e:
                log.error(f"💥 خطأ في الدورة #{iteration}: {e}", exc_info=True)

            # إذا طُلب الإيقاف خلال الدورة — اخرج فوراً
            if self._stop_event.is_set():
                break

            # 🛑 حظر فوري وحماية للحساب عند حدوث خطأ في كلمة المرور أو البريد
            if cycle_res and isinstance(cycle_res, dict) and cycle_res.get("is_auth_error"):
                auth_msg = cycle_res.get("error") or "خطأ في البريد أو كلمة المرور"
                log.error(f"🛑 [إيقاف فوري للحساب] {self.email}: {auth_msg} — إيقاف البوت فوراً لمنع حظر الحساب.")
                self._update_bot_conn_state("error", auth_msg)
                try:
                    import core.database as db
                    if getattr(self, "castle_id", None):
                        db.upsert_castle_conn_state(
                            email=self.email,
                            conn_state="error",
                            message=auth_msg,
                            user_id=getattr(self, "user_id", None),
                            castle_id=getattr(self, "castle_id", None)
                        )
                except Exception as ex:
                    log.warning(f"⚠️ خطأ أثناء تحديث حالة الخطأ في قاعدة البيانات: {ex}")
                self.stop()
                break  # إنهاء حلقة التشغيل فوراً وتفادي مؤقت الـ 25 دقيقة!


            # التحقق مما إذا كانت القلعة عُطّلت أثناء الدورة
            try:
                import core.database as db
                cid = getattr(self, "castle_id", None)
                uid = getattr(self, "user_id", None)
                if cid:
                    c_rec = db.get_castle_by_id(cid, uid)
                    if c_rec and not c_rec.get("is_active", True):
                        log.info(f"⏹️ القلعة {self.email} معطلة من لوحة التحكم — إنهاء التشغيل...")
                        self._update_bot_conn_state("idle", "تم إيقاف البوت بواسطة المستخدم")
                        break
            except Exception:
                pass

            # حساب الوقت المستغرق في تنفيذ الدورة الحالية للطباعة فقط
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # إذا تم تشغيل وضع العفريت المستقل، فقد تمت مزامنة والانتظار بالفعل حتى رأس الساعة التالية
            if cycle_res and isinstance(cycle_res, dict) and "elf_boss" in cycle_res.get("results", {}):
                remaining = 0.0
            else:
                # 🎲 حساب وقت انتظار عشوائي ذكي: الأساسي (30-180) + زيادة عشوائية من 0 إلى 10 دقائق لحماية الحساب
                extra_rand_mins = random.randint(0, 10)
                actual_wait_mins = self.loop_interval_minutes + extra_rand_mins
                remaining = float(actual_wait_mins * 60)
                log.info(f"🎲 توقيت الدورة القادمة: أساسي {self.loop_interval_minutes}د + عشوائي {extra_rand_mins}د = إجمالي {actual_wait_mins} دقيقة")

            from datetime import timezone
            next_run_dt = datetime.now(timezone.utc) + timedelta(seconds=remaining)
            next_run_iso = next_run_dt.isoformat()
            next_run_str = (datetime.now() + timedelta(seconds=remaining)).strftime("%H:%M:%S")
            rem_mins = max(1, round(remaining / 60))

            log.info(f"✅ انتهت الدورة #{iteration} (استغرقت {elapsed:.0f}ث) — الدورة القادمة الساعة: {next_run_str} (بعد {rem_mins} دقيقة)")

            if remaining > 0:
                self._update_bot_conn_state(
                    "waiting",
                    f"بانتظار الدورة القادمة الساعة {next_run_str} (متبقي {rem_mins} دقيقة)",
                    next_run_time=next_run_iso
                )
                log.info(f"💤 بدء انتظار ثابت لمدة {rem_mins} دقيقة...")
                # انتظار عالي الكفاءة عبر asyncio.wait_for على _async_stop_event (0% CPU وبدون 1500 استيقاظ)
                try:
                    if self._stop_event.is_set() or (self._async_stop_event and self._async_stop_event.is_set()):
                        break
                    if self._async_stop_event is not None:
                        await asyncio.wait_for(self._async_stop_event.wait(), timeout=remaining)
                    else:
                        await asyncio.sleep(remaining)
                except asyncio.TimeoutError:
                    pass
            else:
                self._update_bot_conn_state("connected", f"بدء الدورة التالية فوراً (#{iteration + 1})")

        # إغلاق الاتصال بأمان وتحديث الحالة إلى idle عند الخروج من حلقة التشغيل ما لم تكن الحالة خطأ صريح
        if self.conn:
            try:
                await self.conn.close()
            except Exception:
                pass
        if getattr(self, "conn_state", "") != "error":
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
