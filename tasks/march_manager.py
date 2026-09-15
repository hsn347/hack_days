# -*- coding: utf-8 -*-
"""
tasks/march_manager.py — مدير الفيالق والمسيرات الذكي الموحد (March Manager & Orchestrator)
══════════════════════════════════════════════════════════════════════════════════════════════
يقوم هذا الملف بدور "المنسق العام لكافة مسيرات الخريطة الخارجية" بحيث يدير الفيالق المحدودة
(5 إلى 6 فيالق كحد أقصى) وفق قائمة أولويات وإعدادات يمكن تخصيصها بسهولة تامة:
python tasks/march_manager.py --email "samartilleli@yopmail.com" --elf --ruins --gather --gather-level 5 --gather-res 2

  1. مساعدة الموارد (Resource Transport - tasks/transport.py)
  2. استكشاف الأطلال (Ruins - tasks/ruins.py) — مسيرة واحدة حصراً
  3. قتال: غزاة / متمردين / عفريت (Combat: Invaders / Rebels / Elf Boss) — خيار واحد
  4. الهجوم على الملاجئ (Stronghold - tasks/stronghold.py)
  5. جمع الموارد (Gathering - tasks/gather.py) — حتى استهلاك كافة الفيالق المتبقية

★ يمكنك تشغيل أي مهمة أو مجموعة مهام بمفردها (مثلاً: العفريت فقط، أو المساعدة والأطلال والغزاة فقط)
  عبر تعديل المتغيرات في لوحة التحكم أدناه، أو عبر سطر الأوامر (CLI)!
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
import copy
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# استيراد فئات المهام المنفذة
from tasks.transport import TransportTask
from tasks.ruins import RuinsTask
from tasks.monster import MonsterTask
from tasks.elf_boss import ElfBossTask
from tasks.stronghold import StrongholdTask
from tasks.gold_gather import GoldGatherTask
from tasks.gather import GatherTask


# ════════════════════════════════════════════════════════════════════
# ⚙️ لوحة التحكم وتعديل الإعدادات بسهولة (Configuration Block)
# ════════════════════════════════════════════════════════════════════

# ── 1. سعة طوابير الفيالق للقلعة ─────────────────────────────────────
MAX_CASTLE_QUEUES: int = 6  # 5 أو 6 فيالق حسب مستوى القلعة والبحوث


# ── 2. ترتيب الأولويات (Priority Order) ──────────────────────────────
# يمكنك إعادة ترتيب الأولويات بسهولة هنا أو كتابة ما تريده فقط!
# الأسماء المقبولة:
#   - "transport"  أو "مساعدة"
#   - "ruins"      أو "أطلال"   (ترسل مسيرة واحدة حصراً)
#   - "combat"     أو "قتال"    (غزاة / متمردين / عفريت حسب خيار القتال بالأسفل)
#   - "elf"        أو "عفريت"   (نخبة العفريت مباشرة)
#   - "invaders"   أو "غزاة"    (الغزاة مباشرة)
#   - "rebels"     أو "متمردين" (المتمردين مباشرة)
#   - "stronghold" أو "ملاجئ"   (الهجوم على الملاجئ)
#   - "gather"     أو "جمع"     (جمع الموارد بالفيالق المتبقية حتى الامتلاء)
#
# أمثلة شائعة:
#   - تشغيل العفريت فقط:             DEFAULT_PRIORITIES = ["elf"]
#   - مساعدة + أطلال + غزاة:          DEFAULT_PRIORITIES = ["transport", "ruins", "invaders"]
#   - أطلال + جمع موارد بالباقي:     DEFAULT_PRIORITIES = ["ruins", "gather"]
#   - الترتيب الكامل القياسي:
DEFAULT_PRIORITIES: List[str] = [
    "transport",
    "ruins",
    "combat",
    "stronghold",
    "gold_gather",
    "gather",
]


# ── 3. مفاتيح التفعيل والتعطيل (Task Toggles) ────────────────────────
# حدد ما تريد تشغيله بجعله True وما لا تريده بجعله False:
DEFAULT_ENABLE_TRANSPORT   = False   # 1. مساعدة الموارد
DEFAULT_ENABLE_RUINS       = True    # 2. استكشاف الأطلال (مسيرة واحدة حصراً)

# ★ القتال: اختر واحداً فقط من الخيارات الثلاثة التالية بجعله True:
DEFAULT_ENABLE_ELF         = True    # 3-أ. نخبة العفريت (Elf Boss)
DEFAULT_ENABLE_INVADERS    = False   # 3-ب. الغزاة (Invaders)
DEFAULT_ENABLE_REBELS      = False   # 3-ج. المتمردين (Rebels)

DEFAULT_ENABLE_STRONGHOLD  = False   # 4. الهجوم على الملاجئ
DEFAULT_ENABLE_GOLD_GATHER = False   # 5. جمع الذهب في أراضي التحالفات
DEFAULT_ENABLE_GATHER      = False   # 6. جمع الموارد بالفيالق المتبقية

# مفتاح توافق عام (إذا فُعّل يُستخدم الخيار المحدد في DEFAULT_COMBAT_CONFIG):
DEFAULT_ENABLE_COMBAT      = False


# ── 4. إعدادات كل مهمة بالتفصيل (Detailed Task Settings) ─────────────

# [1] إعدادات مساعدة الموارد (Transport)
DEFAULT_TRANSPORT_CONFIG: Dict[str, Any] = {
    "target_x": None,                          # إحداثي X للقلعة الهدف (مثال: 344)
    "target_y": None,                          # إحداثي Y للقلعة الهدف (مثال: 447)
    "resource_ids": [1002, 1003, 1004, 1005],  # 1002=قمح, 1003=خشب, 1004=حديد, 1005=ألماس
}

# [2] إعدادات استكشاف الأطلال (Ruins) — مسيرة واحدة فقط حصراً
DEFAULT_RUINS_CONFIG: Dict[str, Any] = {
    "explore_time": 900,  # بالثواني: 900 (15د), 1800 (30د), 3600 (ساعة), 7200 (ساعتان)
    "formation_id": 1,    # رقم تشكيلة الجنود (1 إلى 5)
}

# [3-أ] إعدادات نخبة العفريت (Elf Boss)
DEFAULT_ELF_CONFIG: Dict[str, Any] = {
    "formation_id": 1,    # رقم تشكيلة القتال (1 إلى 5)
}

# [3-ب] إعدادات الغزاة (Invaders)
DEFAULT_INVADERS_CONFIG: Dict[str, Any] = {
    "level": 35,          # مستوى الغزاة المستهدف (1 إلى 35)
    "formation_id": 1,    # رقم تشكيلة القتال (1 إلى 5)
    "count": 1,           # عدد الهجمات للغزاة
}

# [3-ج] إعدادات المتمردين (Rebels)
DEFAULT_REBELS_CONFIG: Dict[str, Any] = {
    "level": 5,           # مستوى المتمردين المستهدف (1 إلى 5)
    "formation_id": 1,    # رقم تشكيلة القتال (1 إلى 5)
    "count": 1,           # عدد الهجمات للمتمردين
}

# إعدادات القتال العامة البديلة:
DEFAULT_COMBAT_CONFIG: Dict[str, Any] = {
    "choice": "elf",      # "elf" أو "invaders" أو "rebels"
    "level": 35,
    "formation_id": 1,
    "count": 1,
}

# [4] إعدادات الهجوم على الملاجئ (Stronghold)
DEFAULT_STRONGHOLD_CONFIG: Dict[str, Any] = {
    "level": 35,          # مستوى الملجأ المستهدف (1 إلى 35)
    "count": 2,           # عدد الملاجئ المستهدفة في الدورة
    "formation_id": 1,    # رقم التشكيلة (1 إلى 5)
}

# [5] إعدادات جمع الذهب في أراضي التحالفات (Gold Gather)
DEFAULT_GOLD_GATHER_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "locations": [],      # قائمة التحالفات: [{"alliance_tag": "POL", "x": 241, "y": 260}]
    "max_marches": 0,     # 0 = استغلال الفيالق المتاحة
}

# [6] إعدادات جمع الموارد (Gathering) — يستهلك كافة الفيالق الشاغرة
DEFAULT_GATHER_CONFIG: Dict[str, Any] = {
    "res_type": 1,        # 1=ذهب (gold), 2=قمح (food), 3=خشب (wood), 4=حديد (iron), 5=ألماس (diamond)
    "level": 5,           # مستوى حقل المورد بالضبط
    "search_range": 100,  # نطاق البحث الأقصى
}


# ════════════════════════════════════════════════════════════════════
#  الثوابت وخريطة الموارد والترجمة
# ════════════════════════════════════════════════════════════════════

RESOURCE_SUBTYPE_MAP = {
    1: {"name": "🪙 ذهب (Gold)", "code": 1001, "cli": "gold"},
    2: {"name": "🌾 قمح (Food)", "code": 1002, "cli": "food"},
    3: {"name": "🪵 خشب (Wood)", "code": 1003, "cli": "wood"},
    4: {"name": "⛏️ حديد (Iron)", "code": 1004, "cli": "iron"},
    5: {"name": "💎 ألماس/فضة (Diamond)", "code": 1005, "cli": "diamond"},
}

TASK_NAME_ALIASES = {
    "transport": "transport",
    "نقل": "transport",
    "مساعدة": "transport",
    "مساعدة_الموارد": "transport",

    "ruins": "ruins",
    "أطلال": "ruins",
    "اطلال": "ruins",
    "الاطلاق": "ruins",

    "combat": "combat",
    "قتال": "combat",
    "monster": "combat",
    "وحوش": "combat",

    "elf": "elf",
    "عفريت": "elf",
    "العفريت": "elf",
    "elf_boss": "elf",
    "زعيم": "elf",

    "invaders": "invaders",
    "غزاة": "invaders",
    "الغزاة": "invaders",

    "rebels": "rebels",
    "متمردين": "rebels",
    "المتمردين": "rebels",

    "stronghold": "stronghold",
    "ملجأ": "stronghold",
    "ملاجئ": "stronghold",
    "الملاجئ": "stronghold",

    "gold_gather": "gold_gather",
    "gold": "gold_gather",
    "ذهب": "gold_gather",
    "جمع_ذهب": "gold_gather",
    "جمع_الذهب": "gold_gather",

    "gather": "gather",
    "جمع": "gather",
    "موارد": "gather",
    "جمع_الموارد": "gather",
}


def normalize_priority_item(raw_name: str) -> Tuple[str, Optional[str]]:
    """
    تحويل اسم الأولوية المدخل إلى (نوع المهمة الأساسي، خيار فرعي إذا وجد).
    أمثلة:
      "elf" -> ("combat", "elf")
      "invaders" -> ("combat", "invaders")
      "rebels" -> ("combat", "rebels")
      "transport" -> ("transport", None)
      "ruins" -> ("ruins", None)
      "gather" -> ("gather", None)
    """
    cleaned = str(raw_name).strip().lower()
    canonical = TASK_NAME_ALIASES.get(cleaned, cleaned)

    if canonical in ("elf", "invaders", "rebels"):
        return "combat", canonical
    return canonical, None


# ════════════════════════════════════════════════════════════════════
#  فئة مدير الفيالق الذكي (MarchManagerTask)
# ════════════════════════════════════════════════════════════════════

class MarchManagerTask(BaseTask):
    """
    المنسق الذكي لإدارة وترتيب مسيرات الخريطة وفق قائمة الأولويات المحددة وسعة الفيالق.
    """
    name = "march_manager"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        cfg = self.config or {}
        if "march_manager" in cfg and isinstance(cfg["march_manager"], dict):
            inner = dict(cfg["march_manager"])
            for k, v in cfg.items():
                if k != "march_manager" and k not in inner:
                    inner[k] = v
            self.config = inner
            cfg = inner
        self.max_castle_queues: int = int(cfg.get("max_queues", MAX_CASTLE_QUEUES))

    async def _get_active_marches_count(self) -> int:
        """فحص عدد الفيالق النشطة حالياً على الخريطة عبر حزمة 1007/16."""
        try:
            r = await self.conn.query('1007', '16', {}, timeout=4)
            if r and 'data' in r and isinstance(r['data'], list):
                active = len(r['data'])
                return active
        except Exception as e:
            self.log.debug(f"فحص الفيالق النشطة 1007/16: {e}")
        return -1

    async def _has_free_queues(self) -> Tuple[bool, int]:
        """التحقق مما إذا كانت هناك فيالق متاحة لإطلاق مسيرات جديدة."""
        active = await self._get_active_marches_count()
        if active == -1:
            # إذا تعذر الاستعلام المباشر، نعتبر أن هناك فيالق متاحة مؤقتاً
            return True, -1
        self.log.info(f"📊 حالة الفيالق الحالية: {active}/{self.max_castle_queues} مسيرة نشطة على الخريطة")
        return (active < self.max_castle_queues), active

    async def _check_elf_event_status(self) -> Tuple[bool, str]:
        """
        الاستعلام الاستباقي عن حالة حدث العفريت قبل التنفيذ للتأكد من وجود الحدث الفعلي على السيرفر:
          1. استعلام حزمة 5051/1 (Hero Battle Boss Status):
             - كود 15 (Err_ACTIVITY_NOT_OPEN): الحدث مغلق كلياً كحدث عام على السيرفر.
          2. استعلام رادار الزعماء 2011/4 لنخبة العفريت (bossType 10 و 9):
             - كود 16001: الحدث غير متاح.
             - عودة إحداثيات صالحة (x, y): العفريت موجود ومتاح فوراً على الخريطة!
          3. استعلام مصفوفة الخريطة 2011/3 (mapType 24):
             - كود 7 (Err_NO_DATA): لا توجد أي أهداف للعفريت حول القلعة حالياً.
        """
        # 1. فحص حالة الحدث العامة عبر 5051/1
        try:
            r_5051 = await self.conn.query('5051', '1', {}, timeout=3)
            if r_5051 and str(r_5051.get('err', '')) == '15':
                return False, "الحدث مغلق كلياً على السيرفر (كود 15: Err_ACTIVITY_NOT_OPEN)"
        except Exception as e:
            self.log.debug(f"فحص 5051/1: {e}")

        # 2. فحص رادار الزعماء 2011/4
        for bt in (10, 9):
            try:
                r_radar = await self.conn.query('2011', '4', {"bossType": bt}, timeout=3)
                if r_radar and str(r_radar.get('err', '')) == '0':
                    rsp = r_radar.get('rspdata', {})
                    if rsp.get('x') is not None and rsp.get('y') is not None:
                        return True, f"العفريت نشط ومتاح على الخريطة عند ({rsp.get('x')}, {rsp.get('y')})"
                elif r_radar and str(r_radar.get('err', '')) == '16001':
                    return False, "حدث العفريت غير مفتوح حالياً على الخريطة (كود 16001)"
            except Exception as e:
                self.log.debug(f"فحص 2011/4 لنوع {bt}: {e}")

        # 3. فحص مصفوفة الخريطة 2011/3
        try:
            r_map = await self.conn.query('2011', '3', {"mapType": 24, "subType": 0}, timeout=3)
            if r_map and str(r_map.get('err', '')) == '7':
                return False, "لا توجد أي عفاريت نشطة على الخريطة (كود 7: Err_NO_DATA)"
            if r_map and isinstance(r_map.get('result'), list) and len(r_map['result']) > 0:
                return True, f"تم رصد {len(r_map['result'])} عفريت على الخريطة"
        except Exception as e:
            self.log.debug(f"فحص 2011/3: {e}")

        return False, "لم يتم العثور على أي مؤشر لوجود حدث العفريت على السيرفر"

    def _resolve_task_config(self, task_type: str, forced_choice: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        دمج إعدادات المهمة وتحديد ما إذا كانت مفعلة أم لا.
        يدعم:
          1. التكوين الصريح الممرر في self.config
          2. التحديد الدقيق من سطر الأوامر (Explicit CLI)
          3. التعديلات المباشرة على ثوابت الملف في الأعلى
        """
        cfg = self.config or {}

        # 1. معالجة مهمة القتال وخياراتها الحصرية (العفريت / الغزاة / المتمردين)
        if task_type == "combat":
            combat_choice = forced_choice
            user_task_cfg = cfg.get("combat") or cfg.get("monster") or {}

            if not combat_choice:
                combat_choice = user_task_cfg.get("choice") or user_task_cfg.get("type")

            if not combat_choice:
                for sub in ("elf", "invaders", "rebels"):
                    if sub in cfg and cfg[sub].get("enabled", True):
                        combat_choice = sub
                        break

            if not combat_choice:
                if DEFAULT_ENABLE_ELF:
                    combat_choice = "elf"
                elif DEFAULT_ENABLE_INVADERS:
                    combat_choice = "invaders"
                elif DEFAULT_ENABLE_REBELS:
                    combat_choice = "rebels"
                elif DEFAULT_ENABLE_COMBAT:
                    combat_choice = DEFAULT_COMBAT_CONFIG.get("choice", "elf")

            combat_choice = str(combat_choice or "elf").lower()

            choice_templates = {
                "elf": DEFAULT_ELF_CONFIG,
                "invaders": DEFAULT_INVADERS_CONFIG,
                "rebels": DEFAULT_REBELS_CONFIG,
            }
            task_cfg = copy.deepcopy(choice_templates.get(combat_choice, DEFAULT_COMBAT_CONFIG))
            task_cfg["choice"] = combat_choice
            task_cfg.update(user_task_cfg)
            if combat_choice in cfg and isinstance(cfg[combat_choice], dict):
                task_cfg.update(cfg[combat_choice])

            is_enabled = False
            if cfg.get("_explicit_cli"):
                is_enabled = bool(user_task_cfg.get("enabled", False) or cfg.get(combat_choice, {}).get("enabled", False))
            elif user_task_cfg.get("enabled") is not None:
                is_enabled = bool(user_task_cfg["enabled"])
            elif any(k in cfg for k in ("transport", "ruins", "combat", "monster", "stronghold", "gather", "elf", "invaders", "rebels")):
                is_enabled = any(k in cfg for k in ("combat", "monster", combat_choice))
            else:
                if combat_choice == "elf":
                    is_enabled = DEFAULT_ENABLE_ELF
                elif combat_choice == "invaders":
                    is_enabled = DEFAULT_ENABLE_INVADERS
                elif combat_choice == "rebels":
                    is_enabled = DEFAULT_ENABLE_REBELS
                else:
                    is_enabled = DEFAULT_ENABLE_COMBAT

            return is_enabled, task_cfg

        # 2. بقية المهام (Transport / Ruins / Stronghold / GoldGather / Gather)
        default_templates = {
            "transport": (DEFAULT_ENABLE_TRANSPORT, DEFAULT_TRANSPORT_CONFIG),
            "ruins": (DEFAULT_ENABLE_RUINS, DEFAULT_RUINS_CONFIG),
            "stronghold": (DEFAULT_ENABLE_STRONGHOLD, DEFAULT_STRONGHOLD_CONFIG),
            "gold_gather": (DEFAULT_ENABLE_GOLD_GATHER, DEFAULT_GOLD_GATHER_CONFIG),
            "gather": (DEFAULT_ENABLE_GATHER, DEFAULT_GATHER_CONFIG),
        }

        default_enabled, default_settings = default_templates.get(task_type, (False, {}))
        task_cfg = copy.deepcopy(default_settings)

        user_task_cfg = cfg.get(task_type) or (cfg.get("gold") if task_type == "gold_gather" else {}) or {}
        task_cfg.update(user_task_cfg)

        is_enabled = False
        if cfg.get("_explicit_cli"):
            is_enabled = bool(user_task_cfg.get("enabled", False))
        elif user_task_cfg.get("enabled") is not None:
            is_enabled = bool(user_task_cfg["enabled"])
        elif any(k in cfg for k in ("transport", "ruins", "combat", "monster", "stronghold", "gold_gather", "gold", "gather", "elf", "invaders", "rebels")):
            is_enabled = task_type in cfg or (task_type == "gold_gather" and "gold" in cfg)
        else:
            is_enabled = default_enabled

        return is_enabled, task_cfg

    async def _execute_transport(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: مساعدة الموارد."""
        self.log.info("\n🚚 [مهمة مساعدة الموارد] (Resource Transport)...")
        tx = cfg.get("target_x")
        ty = cfg.get("target_y")

        if tx is None or ty is None:
            self.log.warning("⚠️ تم تفعيل مساعدة الموارد ولكن لم يتم تحديد إحداثيات القلعة الهدف (target_x, target_y)!")
            return False

        task = TransportTask(self.conn, cfg)
        res = await task.run()
        return res.success

    async def _execute_ruins(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: استكشاف الأطلال (مسيرة واحدة فقط حصراً)."""
        self.log.info("\n🏛️ [مهمة استكشاف الأطلال] (Ruins - مسيرة واحدة حصراً)...")
        run_cfg = dict(cfg)
        run_cfg["max_marches"] = 1  # شرط ثابت للمنسق: مسيرة واحدة فقط للأطلال
        task = RuinsTask(self.conn, run_cfg)
        res = await task.run()
        return res.success

    async def _execute_combat(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: القتال (عفريت أو غزاة أو متمردين)."""
        choice = str(cfg.get("choice", cfg.get("type", "none"))).lower()

        if choice in ("invaders", "غزاة", "rebels", "متمردين"):
            m_type = "invaders" if choice in ("invaders", "غزاة") else "rebels"
            m_name = "الغزاة (Invaders)" if m_type == "invaders" else "المتمردين (Rebels)"
            self.log.info(f"\n👾 [مهمة قتال: {m_name}]...")

            m_level = int(cfg.get("level", cfg.get("max_lv", 30)))
            m_form  = int(cfg.get("formation_id", cfg.get("formation", 1)))
            m_count = int(cfg.get("count", cfg.get("max_marches", 6)))

            m_run_cfg = {
                "monster_type": m_type,
                "min_lv": m_level,
                "max_lv": m_level,
                "formation_id": m_form,
                "max_marches": m_count
            }
            task = MonsterTask(self.conn, m_run_cfg)
            res = await task.run()
            return res.success

        elif choice in ("elf", "elf_boss", "عفريت", "العفريت"):
            self.log.info("\n👹 [مهمة قتال: نخبة العفريت (Elf Boss)]...")

            # فحص استباقي: هل حدث العفريت نشط ومتاح حالياً على السيرفر؟
            self.log.info("🔍 استعلام حالة حدث العفريت للتأكد من وجود الحدث الفعلي على السيرفر...")
            is_active, active_reason = await self._check_elf_event_status()
            if not is_active:
                self.log.warning(f"⚠️ [حدث العفريت غير متاح] {active_reason}.")
                self.log.info("⏭️ تم تجاوز مهمة العفريت تلقائياً ومتابعة باقي الأولويات بسلاسة دون توقف.")
                return False

            elf_form = int(cfg.get("formation_id", cfg.get("formation", 1)))
            elf_run_cfg = {
                "formation_id": elf_form,
                "count": 1,
                "all_legions": False
            }
            task = ElfBossTask(self.conn, elf_run_cfg)
            res = await task.run()
            return res.success
        else:
            self.log.warning(f"⚠️ نوع هدف قتالي غير معروف: '{choice}'. يرجى اختيار 'elf' أو 'invaders' أو 'rebels'.")
            return False

    async def _execute_stronghold(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: الهجوم على الملاجئ."""
        sh_count = int(cfg.get("count", cfg.get("max_marches", 2)))
        sh_level = int(cfg.get("level", cfg.get("max_lv", 30)))
        sh_form  = int(cfg.get("formation_id", cfg.get("formation", 1)))

        self.log.info(f"\n🏰 [مهمة الهجوم على الملاجئ] (ملاجئ مستهدفة: {sh_count} | لفل: {sh_level})...")

        sh_run_cfg = {
            "min_lv": sh_level,
            "max_lv": sh_level,
            "formation_id": sh_form,
            "max_marches": sh_count
        }
        task = StrongholdTask(self.conn, sh_run_cfg)
        res = await task.run()
        return res.success

    async def _execute_gold_gather(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: جمع الذهب في أراضي التحالفات."""
        self.log.info("\n🪙 [مهمة جمع الذهب في أراضي التحالفات] (Gold Gathering)...")
        task = GoldGatherTask(self.conn, cfg)
        await task.on_start()
        res = await task.run()
        return res.success

    async def _execute_gather(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: جمع الموارد بكافة الفيالق المتبقية حتى الامتلاء."""
        g_res_input = cfg.get("res_type", cfg.get("res", 1))
        g_level     = int(cfg.get("level", 5))

        res_name = str(g_res_input)
        try:
            sub_int = int(g_res_input)
            if sub_int in RESOURCE_SUBTYPE_MAP:
                res_name = RESOURCE_SUBTYPE_MAP[sub_int]["name"]
        except Exception:
            pass

        self.log.info(f"\n🌾 [مهمة جمع الموارد] استهلاك كافة الفيالق الشاغرة ({res_name} | لفل: {g_level})...")

        gather_run_cfg = {
            "res_type": g_res_input,
            "level": g_level,
            "max_marches": 0,  # 0 تعني حتى استهلاك كافة الفيالق
            "search_range": int(cfg.get("search_range", 100))
        }
        task = GatherTask(self.conn, gather_run_cfg)
        res = await task.run()
        return res.success

    async def run(self) -> TaskResult:
        cfg = self.config or {}
        self.log.info("══════════════════════════════════════════════════════════")
        self.log.info("🎖️ بدء دورة منسق الفيالق والمسيرات (March Orchestrator)")
        self.log.info("══════════════════════════════════════════════════════════")

        # 0. التحقق المبدئي من الفيالق
        has_free, active_count = await self._has_free_queues()
        if not has_free:
            self.log.warning(f"🛑 كافة فيالق القلعة ممتلئة بالكامل ({active_count}/{self.max_castle_queues})! إنهاء الدورة.")
            return TaskResult.ok("كافة الفيالق ممتلئة بالكامل", active=active_count)

        # استخراج قائمة الأولويات
        raw_priorities = cfg.get("priority_order") or cfg.get("priorities") or DEFAULT_PRIORITIES
        if isinstance(raw_priorities, str):
            priority_list = [p.strip() for p in raw_priorities.split(",") if p.strip()]
        else:
            priority_list = list(raw_priorities)

        # ضمان وجود gold_gather في الترتيب المعتمد (قبل gather وبعد stronghold) حتى للحسابات المخزنة مسبقاً في Firebase
        normalized_existing = [normalize_priority_item(p)[0] for p in priority_list]
        if "gold_gather" not in normalized_existing and not cfg.get("_explicit_cli"):
            if "gather" in normalized_existing:
                g_pos = normalized_existing.index("gather")
                priority_list.insert(g_pos, "gold_gather")
            elif "stronghold" in normalized_existing:
                sh_pos = normalized_existing.index("stronghold")
                priority_list.insert(sh_pos + 1, "gold_gather")

        # هل قام المستخدم بتحديد قائمة مخصصة (أقل من القياسية مثل ["elf"] أو ["transport", "ruins"])؟
        is_custom_subset = (priority_list != DEFAULT_PRIORITIES)

        cycle_summary: Dict[str, Any] = {}
        executed_any = False

        handlers = {
            "transport": self._execute_transport,
            "ruins": self._execute_ruins,
            "combat": self._execute_combat,
            "stronghold": self._execute_stronghold,
            "gold_gather": self._execute_gold_gather,
            "gather": self._execute_gather,
        }

        display_titles = {
            "transport": "مساعدة الموارد (Transport)",
            "ruins": "استكشاف الأطلال (Ruins)",
            "combat": "القتال (Combat)",
            "stronghold": "الهجوم على الملاجئ (Stronghold)",
            "gold_gather": "جمع الذهب (Gold Gathering)",
            "gather": "جمع الموارد (Gathering)",
        }

        self.log.info(f"📋 مسار الأولويات المعتمد لهذه الدورة: {priority_list}")

        for index, item_name in enumerate(priority_list, 1):
            task_type, forced_choice = normalize_priority_item(item_name)
            title = display_titles.get(task_type, task_type)

            if forced_choice:
                title += f" [{forced_choice}]"

            if task_type not in handlers:
                self.log.warning(f"⚠️ تخطي مهمة غير معروفة في الأولويات: '{item_name}'")
                continue

            # فحص التفعيل
            is_enabled, task_cfg = self._resolve_task_config(task_type, forced_choice)

            # إذا وضع المستخدم المهمة في قائمة مخصصة محددة (كأن يكتب PRIORITIES = ["elf"])، نعتبرها مفعلة تلقائياً
            if is_custom_subset and not cfg.get("_explicit_cli") and "enabled" not in cfg.get(task_type, {}):
                is_enabled = True

            if not is_enabled:
                self.log.info(f"⏭️ [الأولوية {index}/{len(priority_list)}] {title} غير مفعلة، انتقال للمهمة التالية.")
                continue

            # فحص توفر فيالق قبل تشغيل المهمة
            has_free, active_before = await self._has_free_queues()
            if not has_free:
                self.log.warning(f"🛑 كافة الفيالق أصبحت ممتلئة ({active_before}/{self.max_castle_queues}) قبل تشغيل {title}! إنهاء الدورة.")
                break

            self.log.info(f"▶️ [الأولوية {index}/{len(priority_list)}] بدء تنفيذ: {title}...")
            handler_func = handlers[task_type]

            try:
                success = await handler_func(task_cfg)
                summary_key = f"{task_type}_{forced_choice}" if forced_choice else task_type
                cycle_summary[summary_key] = success
                executed_any = True
            except Exception as e:
                self.log.error(f"❌ خطأ أثناء تنفيذ {title}: {e}", exc_info=True)
                cycle_summary[task_type] = False

            # استراحة أمان بشرية بين المهام المتعاقبة
            await asyncio.sleep(random.uniform(3.5, 6.0))

            # فحص الفيالق بعد انتهاء المهمة
            has_free, active_after = await self._has_free_queues()
            if not has_free:
                self.log.info(f"🛑 اكتملت طوابير الفيالق بالكامل ({active_after}/{self.max_castle_queues}) بعد {title}. إنهاء الدورة بنجاح.")
                break

        self.log.info("\n══════════════════════════════════════════════════════════")
        if not executed_any:
            self.log.warning("⚠️ لم يتم تشغيل أي مهمة! يرجى التأكد من تفعيل المهام في المتغيرات بالأعلى أو عبر سطر الأوامر.")
        self.log.info("🏁 اكتملت دورة منسق الفيالق الذكي!")
        self.log.info(f"📋 ملخص المهام المنفذة: {cycle_summary}")
        self.log.info("══════════════════════════════════════════════════════════")

        return TaskResult.ok("اكتملت دورة منسق الفيالق بنجاح", summary=cycle_summary, executed=executed_any)


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول من سطر الأوامر (CLI Entry Point)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    from core.session_manager import SessionManager

    parser = argparse.ArgumentParser(
        description="Empire March Manager — منسق الفيالق والمسيرات الذكي الموحد وفق قائمة الأولويات وسعة الفيالق",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة التشغيل وسهولة التحكم:
  ─────────────────────────────────────────────────────────────────────────────
  ★ مثال 1: تشغيل العفريت فقط (Elf Boss Only):
      python tasks/march_manager.py --email "user@gmail.com" --combat-choice elf

  ★ مثال 2: تشغيل المساعدة والأطلال والغزاة فقط:
      python tasks/march_manager.py --email "user@gmail.com" \\
          --transport --tx 344 --ty 447 \\
          --ruins --ruins-time 900 \\
          --combat-choice invaders --combat-level 30

  ★ مثال 3: تشغيل أطلال ثم جمع ذهب بالباقي:
      python tasks/march_manager.py --email "user@gmail.com" \\
          --ruins --ruins-time 1800 \\
          --gather --gather-res gold --gather-level 5

  ★ مثال 4: إعادة ترتيب الأولويات من سطر الأوامر مباشرة:
      python tasks/march_manager.py --email "user@gmail.com" \\
          --priority "elf,ruins,gather" \\
          --combat-choice elf --ruins --gather --gather-res food

  ★ مثال 5: التشغيل بالإعدادات المكتوبة داخل الملف مباشرة (بدون وسائط إضافية):
      python tasks/march_manager.py --email "user@gmail.com"
  ─────────────────────────────────────────────────────────────────────────────
        """
    )
    parser.add_argument("--email", "-e", required=True, help="البريد الإلكتروني لحساب اللعبة")

    # تحديد ترتيب الأولويات (اختياري)
    parser.add_argument(
        "--priority", "--priorities",
        help="تحديد ترتيب الأولويات مفصولة بفواصل (مثال: 'elf' أو 'transport,ruins,invaders' أو 'ruins,gather')"
    )

    # سعة الفيالق
    parser.add_argument("--max-queues", type=int, default=MAX_CASTLE_QUEUES, help=f"أقصى عدد فيالق للقلعة [افتراضي: {MAX_CASTLE_QUEUES}]")

    # [1] مساعدة الموارد
    parser.add_argument("--transport", action="store_true", help="تفعيل أولوية: مساعدة الموارد")
    parser.add_argument("--tx", type=int, default=None, help="إحداثي X للقلعة الهدف")
    parser.add_argument("--ty", type=int, default=None, help="إحداثي Y للقلعة الهدف")
    parser.add_argument("--tres", type=int, nargs="+", default=None, help="معرفات الموارد: 1002=قمح, 1003=خشب, 1004=حديد, 1005=ألماس")

    # [2] استكشاف الأطلال
    parser.add_argument("--ruins", action="store_true", help="تفعيل أولوية: استكشاف الأطلال (مسيرة واحدة حصراً)")
    parser.add_argument("--ruins-time", type=int, default=None, choices=[900, 1800, 3600, 7200], help="مدة الاستكشاف بالثواني: 900=15د, 1800=30د, 3600=ساعة, 7200=ساعتان")
    parser.add_argument("--ruins-formation", type=int, default=None, help="رقم تشكيلة الأطلال (1..5)")

    # [3] القتال (عفريت / غزاة / متمردين)
    parser.add_argument("--elf", action="store_true", help="تفعيل أولوية القتال: نخبة العفريت مباشرة (Elf Boss)")
    parser.add_argument("--elf-level", type=int, default=None, help="مستوى أو فئة العفريت (اختياري)")
    parser.add_argument("--elf-formation", type=int, default=None, help="رقم تشكيلة العفريت (1..6)")
    parser.add_argument("--invaders", action="store_true", help="تفعيل أولوية القتال: الغزاة مباشرة (Invaders)")
    parser.add_argument("--rebels", action="store_true", help="تفعيل أولوية القتال: المتمردين مباشرة (Rebels)")
    parser.add_argument("--combat", action="store_true", help="تفعيل أولوية: القتال")
    parser.add_argument("--combat-choice", choices=["invaders", "rebels", "elf", "none"], default=None, help="اختيار هدف قتالي: elf (عفريت) أو invaders (غزاة) أو rebels (متمردين)")
    parser.add_argument("--combat-level", type=int, default=None, help="مستوى الغزاة أو المتمردين")
    parser.add_argument("--combat-formation", type=int, default=None, help="رقم تشكيلة القتال (1..5)")
    parser.add_argument("--combat-count", type=int, default=None, help="عدد مسيرات القتال للغزاة/المتمردين")

    # [4] الملاجئ
    parser.add_argument("--stronghold", action="store_true", help="تفعيل أولوية: الهجوم على الملاجئ")
    parser.add_argument("--stronghold-level", type=int, default=None, help="مستوى الملجأ المستهدف")
    parser.add_argument("--stronghold-count", type=int, default=None, help="عدد الملاجئ المستهدفة في الدورة")
    parser.add_argument("--stronghold-formation", type=int, default=None, help="رقم تشكيلة الملجأ (1..5)")

    # [5] جمع الذهب في أراضي التحالفات
    parser.add_argument("--gold-gather", "--gold", dest="gold_gather", action="store_true", help="تفعيل أولوية: جمع الذهب في أراضي التحالفات")
    parser.add_argument("--gold-tag", type=str, default=None, help="اختصار التحالف لجمع الذهب (مثال: POL)")
    parser.add_argument("--gold-coords", type=str, default=None, help="إحداثيات مركز التحالف لجمع الذهب X,Y")
    parser.add_argument("--gold-alliances", type=str, default=None, help="تحالفات متعددة لجمع الذهب بصيغة TAG1:X1,Y1;TAG2:X2,Y2")

    # [6] جمع الموارد
    parser.add_argument("--gather", action="store_true", help="تفعيل أولوية: جمع الموارد بالفيالق المتبقية حتى الامتلاء")
    parser.add_argument("--gather-res", default=None, help="نوع المورد للجمع: 1/gold=ذهب, 2/food=قمح, 3/wood=خشب, 4/iron=حديد, 5/diamond=ألماس")
    parser.add_argument("--gather-level", type=int, default=None, help="مستوى حقل المورد المستهدف بالضبط")
    parser.add_argument("--gather-range", type=int, default=None, help="نطاق البحث الأقصى عن الحقول")

    # ملف تكوين JSON مباشر
    parser.add_argument("--config-json", help="مسار ملف JSON أو نص JSON يحتوي على التكوين الكامل")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    final_config: Dict[str, Any] = {}

    if args.config_json:
        if os.path.exists(args.config_json):
            with open(args.config_json, "r", encoding="utf-8") as f:
                final_config = json.load(f)
        else:
            final_config = json.loads(args.config_json)
    else:
        # دعم الأعلام المباشرة للقتال
        if args.elf:
            args.combat = True
            args.combat_choice = "elf"
        elif args.invaders:
            args.combat = True
            args.combat_choice = "invaders"
        elif args.rebels:
            args.combat = True
            args.combat_choice = "rebels"

        # فحص هل قام المستخدم باختيار مهام صريحة عبر سطر الأوامر
        has_cli_task_selection = any([
            args.transport,
            args.tx is not None,
            args.ruins,
            args.combat,
            (args.combat_choice is not None and args.combat_choice != "none"),
            args.elf,
            args.invaders,
            args.rebels,
            args.stronghold,
            args.gold_gather,
            (args.gold_tag is not None),
            (args.gold_alliances is not None),
            args.gather,
            (args.priority is not None)
        ])

        final_config["max_queues"] = args.max_queues

        if args.priority:
            final_config["priority_order"] = args.priority

        if has_cli_task_selection:
            final_config["_explicit_cli"] = True

            # 1. Transport
            if args.transport or (args.tx is not None and args.ty is not None):
                t_cfg = copy.deepcopy(DEFAULT_TRANSPORT_CONFIG)
                t_cfg["enabled"] = True
                if args.tx is not None: t_cfg["target_x"] = args.tx
                if args.ty is not None: t_cfg["target_y"] = args.ty
                if args.tres is not None: t_cfg["resource_ids"] = args.tres
                final_config["transport"] = t_cfg
            else:
                final_config["transport"] = {"enabled": False}

            # 2. Ruins
            if args.ruins or (args.ruins_time is not None) or (args.ruins_formation is not None):
                r_cfg = copy.deepcopy(DEFAULT_RUINS_CONFIG)
                r_cfg["enabled"] = True
                if args.ruins_time is not None: r_cfg["explore_time"] = args.ruins_time
                if args.ruins_formation is not None: r_cfg["formation_id"] = args.ruins_formation
                final_config["ruins"] = r_cfg
            else:
                final_config["ruins"] = {"enabled": False}

            # 3. Combat
            if args.combat or (args.combat_choice is not None and args.combat_choice != "none"):
                c_choice = args.combat_choice or "elf"
                choice_templates = {
                    "elf": DEFAULT_ELF_CONFIG,
                    "invaders": DEFAULT_INVADERS_CONFIG,
                    "rebels": DEFAULT_REBELS_CONFIG,
                }
                c_cfg = copy.deepcopy(choice_templates.get(c_choice, DEFAULT_COMBAT_CONFIG))
                c_cfg["enabled"] = True
                c_cfg["choice"] = c_choice
                if args.combat_level is not None: c_cfg["level"] = args.combat_level
                if args.combat_formation is not None: c_cfg["formation_id"] = args.combat_formation
                if args.combat_count is not None: c_cfg["count"] = args.combat_count
                final_config["combat"] = c_cfg
            else:
                final_config["combat"] = {"enabled": False}

            # 4. Stronghold
            if args.stronghold or (args.stronghold_level is not None) or (args.stronghold_count is not None):
                s_cfg = copy.deepcopy(DEFAULT_STRONGHOLD_CONFIG)
                s_cfg["enabled"] = True
                if args.stronghold_level is not None: s_cfg["level"] = args.stronghold_level
                if args.stronghold_count is not None: s_cfg["count"] = args.stronghold_count
                if args.stronghold_formation is not None: s_cfg["formation_id"] = args.stronghold_formation
                final_config["stronghold"] = s_cfg
            else:
                final_config["stronghold"] = {"enabled": False}

            # 5. Gold Gather
            if args.gold_gather or (args.gold_tag is not None) or (args.gold_alliances is not None):
                gg_cfg = copy.deepcopy(DEFAULT_GOLD_GATHER_CONFIG)
                gg_cfg["enabled"] = True
                locations = []
                if args.gold_alliances:
                    for item in args.gold_alliances.split(';'):
                        item = item.strip()
                        if not item:
                            continue
                        if ':' in item:
                            t_part, c_part = item.split(':', 1)
                            t_tag = t_part.strip()
                            if ',' in c_part:
                                xy = c_part.split(',')
                                locations.append({"alliance_tag": t_tag, "x": int(xy[0].strip()), "y": int(xy[1].strip())})
                elif args.gold_tag:
                    gx, gy = None, None
                    if args.gold_coords and ',' in args.gold_coords:
                        parts = args.gold_coords.split(',')
                        gx, gy = int(parts[0].strip()), int(parts[1].strip())
                    locations.append({"alliance_tag": args.gold_tag, "x": gx, "y": gy})

                if locations:
                    gg_cfg["locations"] = locations
                final_config["gold_gather"] = gg_cfg
            else:
                final_config["gold_gather"] = {"enabled": False}

            # 6. Gather
            if args.gather or (args.gather_res is not None) or (args.gather_level is not None):
                g_cfg = copy.deepcopy(DEFAULT_GATHER_CONFIG)
                g_cfg["enabled"] = True
                if args.gather_res is not None: g_cfg["res_type"] = args.gather_res
                if args.gather_level is not None: g_cfg["level"] = args.gather_level
                if args.gather_range is not None: g_cfg["search_range"] = args.gather_range
                final_config["gather"] = g_cfg
            else:
                final_config["gather"] = {"enabled": False}
        else:
            # لم يمرر أي خيار للمهام -> سيعتمد على ثوابت وتفعيلات الملف الافتراضية
            pass

    async def main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            logging.error("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        target_email = args.email.strip()
        account = accounts.get(target_email)
        if not account:
            # مطابقة غير حساسة لحالة الأحرف (case-insensitive fallback)
            for email_key, acc_val in accounts.items():
                if email_key.lower() == target_email.lower():
                    account = acc_val
                    break

        if not account:
            logging.error(f"❌ لم يتم العثور على حساب بالبريد: {args.email}")
            return

        conn = GameConnection(account)
        if not await conn.connect():
            logging.error("❌ فشل الاتصال بالسيرفر!")
            return

        for _ in range(10):
            await asyncio.sleep(1.0)
            if len(conn.init_data) > 0:
                break

        orchestrator = MarchManagerTask(conn, final_config)
        await orchestrator.run()
        await conn.close()

    asyncio.run(main())
