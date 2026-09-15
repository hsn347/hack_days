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
from tasks.prestige import PrestigeTask


# ════════════════════════════════════════════════════════════════════
# ⚙️ لوحة التحكم وتعديل الإعدادات بسهولة (Configuration Block)
# ════════════════════════════════════════════════════════════════════

# ── 1. سعة طوابير الفيالق للقلعة ومدة التشغيل ──────────────────────
MAX_CASTLE_QUEUES: int = 6  # 5 أو 6 فيالق حسب مستوى القلعة والبحوث
DEFAULT_TASK_DURATION_MINUTES: int = 20  # مدة تشغيل المهمة ككل (ثلث ساعة = 20 دقيقة)


# ── 2. ترتيب الأولويات (Priority Order) ──────────────────────────────
# الترتيب القياسي المعتمد: مهام الهيبة الخارجية أولاً في القمة، ثم باقي المهام تباعاً
DEFAULT_PRIORITIES: List[str] = [
    "prestige_stronghold",  # 1. ملاجئ مهام الهيبة (الأولوية الأولى)
    "prestige_invaders",    # 2. غزاة مهام الهيبة (الأولوية الثانية)
    "prestige_gather",      # 3. جمع موارد مهام الهيبة 25k (الأولوية الثالثة)
    "transport",            # 4. مساعدة الموارد
    "ruins",                # 5. استكشاف الأطلال (مسيرة واحدة)
    "combat",               # 6. القتال (عفريت أو غزاة أو متمردين - بكافة الفيالق)
    "stronghold",           # 7. ملاجئ عامة
    "gold_gather",          # 8. جمع الذهب في أراضي التحالفات
    "gather",               # 9. جمع الموارد بالفيالق المتبقية
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
    "all_legions": True,  # توجيه كافة الفيالق المتاحة
}

# [3-ب] إعدادات الغزاة (Invaders)
DEFAULT_INVADERS_CONFIG: Dict[str, Any] = {
    "level": 35,          # مستوى الغزاة المستهدف (1 إلى 35)
    "formation_id": 1,    # رقم تشكيلة القتال (1 إلى 5)
    "all_legions": True,  # توجيه كافة الفيالق المتاحة
}

# [3-ج] إعدادات المتمردين (Rebels)
DEFAULT_REBELS_CONFIG: Dict[str, Any] = {
    "level": 5,           # مستوى المتمردين المستهدف (1 إلى 5)
    "formation_id": 1,    # رقم تشكيلة القتال (1 إلى 5)
    "all_legions": True,  # توجيه كافة الفيالق المتاحة
}

# إعدادات القتال العامة البديلة:
DEFAULT_COMBAT_CONFIG: Dict[str, Any] = {
    "choice": "elf",      # "elf" أو "invaders" أو "rebels"
    "level": 35,
    "formation_id": 1,
    "all_legions": True,  # توجيه كافة الفيالق المتاحة
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

    # مهام الهيبة الخارجية
    "prestige_stronghold": "prestige_stronghold",
    "ملاجئ_الهيبة": "prestige_stronghold",
    "معاقل_الهيبة": "prestige_stronghold",
    "ملجأ_الهيبة": "prestige_stronghold",
    "ملاجئ_هيبة": "prestige_stronghold",

    "prestige_invaders": "prestige_invaders",
    "غزاة_الهيبة": "prestige_invaders",
    "الغزاة_الهيبة": "prestige_invaders",
    "غزاة_هيبة": "prestige_invaders",

    "prestige_gather": "prestige_gather",
    "جمع_الهيبة": "prestige_gather",
    "موارد_الهيبة": "prestige_gather",
    "جمع_موارد_الهيبة": "prestige_gather",
    "جمع_هيبة": "prestige_gather",

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
        dur_min = float(cfg.get("duration_minutes", cfg.get("duration", DEFAULT_TASK_DURATION_MINUTES)))
        self.duration_seconds: float = max(30.0, dur_min * 60.0)
        self._log_cb = cfg.get("_log_callback")

    def _log_event(self, msg: str, level: str = "info") -> None:
        """تسجيل الرسالة محلياً وإرسالها إلى لوحة التحكم والـ log file عبر _log_callback إن توفر."""
        if level == "warning":
            self.log.warning(msg)
        elif level == "error":
            self.log.error(msg)
        else:
            self.log.info(msg)

        if getattr(self, "_log_cb", None):
            try:
                self._log_cb(msg)
            except Exception:
                pass

    def _is_stop_requested(self) -> bool:
        """فحص طلب إيقاف المهمة (سواء من BaseTask أو حدث خارجي من BotManager)."""
        if self.is_stopped():
            return True
        ext = self.config.get("_external_stop_event")
        if ext is not None and hasattr(ext, "is_set") and ext.is_set():
            return True
        return False

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

        # 0. مهام الهيبة خارج القلعة (الملاجئ، الغزاة، جمع الموارد) — تُفعّل من إعدادات الهيبة في الواجهة
        p_cfg = cfg.get("_prestige_config") or cfg.get("prestige", {})
        prestige_master_enabled = bool(p_cfg.get("enabled", True))
        prestige_subtasks = p_cfg.get("subtasks", {}) if isinstance(p_cfg.get("subtasks"), dict) else {}

        if task_type == "prestige_stronghold":
            is_enabled = prestige_master_enabled and bool(prestige_subtasks.get("stronghold", True))
            sh_cfg = p_cfg.get("stronghold", {}) if isinstance(p_cfg.get("stronghold"), dict) else {}
            task_cfg = {
                "count": int(sh_cfg.get("count", 2)),
                "min_lv": int(sh_cfg.get("min_lv", 1)),
                "max_lv": int(sh_cfg.get("max_lv", 30)),
                "search_range": int(sh_cfg.get("search_range", 80)),
                "formation_id": int(sh_cfg.get("formation_id", 0)),
                "troops_count": int(sh_cfg.get("troops_count", 30000)),
            }
            return is_enabled, task_cfg

        elif task_type == "prestige_invaders":
            is_enabled = prestige_master_enabled and bool(prestige_subtasks.get("invaders", True))
            inv_cfg = p_cfg.get("invaders", {}) if isinstance(p_cfg.get("invaders"), dict) else {}
            task_cfg = {
                "count": int(inv_cfg.get("count", 5)),
                "min_lv": int(inv_cfg.get("min_lv", 1)),
                "max_lv": int(p_cfg.get("invaders_max_lv", inv_cfg.get("max_lv", 30))),
                "search_range": int(inv_cfg.get("search_range", 80)),
                "formation_id": int(inv_cfg.get("formation_id", 0)),
                "troops_count": int(inv_cfg.get("troops_count", 30000)),
            }
            return is_enabled, task_cfg

        elif task_type == "prestige_gather":
            is_enabled = prestige_master_enabled and bool(prestige_subtasks.get("gather", True))
            task_cfg = {
                "target_source_num": 25000,
                "target_capacity": 25000,
                "search_range": int(p_cfg.get("search_range", 120)),
                "min_lv": 1,
                "max_lv": 7,
            }
            return is_enabled, task_cfg

        # 1. معالجة مهمة القتال وخياراتها الحصرية (العفريت / الغزاة / المتمردين)
        if task_type == "combat":
            combat_choice = forced_choice
            user_task_cfg = cfg.get("combat") or cfg.get("monster") or {}

            # الأولوية 1: فحص أي خيار فرعي مفعل صراحة في إعدادات الواجهة (elf / invaders / rebels)
            if not combat_choice:
                for sub in ("elf", "invaders", "rebels"):
                    if sub in cfg and isinstance(cfg[sub], dict) and cfg[sub].get("enabled") is True:
                        combat_choice = sub
                        break

            # الأولوية 2: الخيار المسجل في choice / type
            if not combat_choice:
                combat_choice = user_task_cfg.get("choice") or user_task_cfg.get("type")

            # الأولوية 3: فحص أي خيار فرعي موجود في الإعدادات
            if not combat_choice:
                for sub in ("elf", "invaders", "rebels"):
                    if sub in cfg and isinstance(cfg[sub], dict) and cfg[sub].get("enabled", True):
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
            task_cfg.update(user_task_cfg)
            if combat_choice in cfg and isinstance(cfg[combat_choice], dict):
                task_cfg.update(cfg[combat_choice])
            task_cfg["choice"] = combat_choice  # تأكيد الخيار القتالي الحقيقي وعدم استبداله بقيمة قديمة

            sub_enabled = cfg.get(combat_choice, {}).get("enabled") if (combat_choice in cfg and isinstance(cfg[combat_choice], dict)) else None
            root_combat_enabled = user_task_cfg.get("enabled")

            is_enabled = False
            if sub_enabled is not None:
                is_enabled = bool(sub_enabled)
            elif root_combat_enabled is not None:
                is_enabled = bool(root_combat_enabled)
            elif cfg.get("_explicit_cli"):
                is_enabled = bool(root_combat_enabled or sub_enabled)
            elif any(k in cfg for k in ("transport", "ruins", "combat", "monster", "stronghold", "gather", "elf", "invaders", "rebels")):
                is_enabled = bool(sub_enabled if sub_enabled is not None else any(k in cfg for k in ("combat", "monster", combat_choice)))
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

    async def _execute_prestige_stronghold(self, cfg: Dict[str, Any]) -> bool:
        """
        تنفيذ أولوية: ملاجئ مهام الهيبة اليومية (Prestige Strongholds) - الأولوية الأولى.
        - تفحص meritoriousTaskCtrl للتأكد مما إذا كانت المهمة مكتملة مسبقاً اليوم.
        - إذا كانت مكتملة: تتخطاها وتعود فوراً لينتقل المنسق للأولوية التالية.
        - إذا كان متبقياً هجمات: ترسل مسيرات بعدد المتبقي وبحد أقصى الفيالق الشاغرة.
        """
        if "meritoriousTaskCtrl" not in self.conn.init_data:
            try:
                await self.conn.query("1024", "1", {}, timeout=4)
            except Exception:
                pass

        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        task_data = merit.get("taskData", {}) if isinstance(merit, dict) else {}
        t_sh = task_data.get("4112030") or task_data.get(4112030)

        needed = cfg.get("count", 2)
        if t_sh and isinstance(t_sh, dict):
            c_num = int(t_sh.get("cNum", 0))
            l_num = int(t_sh.get("lNum", needed))
            status = int(t_sh.get("status", 2))
            if (status in (4, 5)) or (l_num > 0 and c_num >= l_num):
                self._log_event(f"✨ [ملاجئ الهيبة] المهمة مكتملة مسبقاً اليوم ({c_num}/{l_num}) — الانتقال للأولوية التالية.")
                return False
            needed = max(1, l_num - c_num)

        active_count = await self._get_active_marches_count()
        if active_count != -1 and active_count < self.max_castle_queues:
            free_slots = max(1, self.max_castle_queues - active_count)
        else:
            free_slots = self.max_castle_queues

        target_count = min(needed, free_slots)
        if target_count <= 0:
            return False

        self._log_event(f"🏰 [ملاجئ الهيبة] إرسال {target_count} مسيرة هجوم على الملاجئ (متبقي {needed} لمهام الهيبة)...")

        sh_run_cfg = {
            "min_lv": cfg.get("min_lv", 1),
            "max_lv": cfg.get("max_lv", 30),
            "formation_id": cfg.get("formation_id", 0),
            "troops_count": cfg.get("troops_count", 30000),
            "search_range": cfg.get("search_range", 80),
            "max_marches": target_count,
            "wait_for_queue": False,
        }
        task = StrongholdTask(self.conn, sh_run_cfg)
        res = await task.run()
        return res.success if res else False

    async def _execute_prestige_invaders(self, cfg: Dict[str, Any]) -> bool:
        """
        تنفيذ أولوية: غزاة مهام الهيبة اليومية (Prestige Invaders) - الأولوية الثانية.
        - تفحص meritoriousTaskCtrl للتأكد مما إذا كانت مهمة الغزاة مكتملة مسبقاً.
        - إذا كانت مكتملة: تتخطاها وتعود فوراً لينتقل المنسق للأولوية التالية.
        - إذا كان متبقياً هجمات: ترسل مسيرات بعدد المتبقي وبحد أقصى الفيالق الشاغرة.
        """
        if "meritoriousTaskCtrl" not in self.conn.init_data:
            try:
                await self.conn.query("1024", "1", {}, timeout=4)
            except Exception:
                pass

        merit = self.conn.init_data.get("meritoriousTaskCtrl", {})
        task_data = merit.get("taskData", {}) if isinstance(merit, dict) else {}
        t_inv = task_data.get("4112028") or task_data.get(4112028)

        needed = cfg.get("count", 5)
        if t_inv and isinstance(t_inv, dict):
            c_num = int(t_inv.get("cNum", 0))
            l_num = int(t_inv.get("lNum", needed))
            status = int(t_inv.get("status", 2))
            if (status in (4, 5)) or (l_num > 0 and c_num >= l_num):
                self._log_event(f"✨ [غزاة الهيبة] المهمة مكتملة مسبقاً اليوم ({c_num}/{l_num}) — الانتقال للأولوية التالية.")
                return False
            needed = max(1, l_num - c_num)

        active_count = await self._get_active_marches_count()
        if active_count != -1 and active_count < self.max_castle_queues:
            free_slots = max(1, self.max_castle_queues - active_count)
        else:
            free_slots = self.max_castle_queues

        target_count = min(needed, free_slots)
        if target_count <= 0:
            return False

        max_lv = cfg.get("max_lv", 30)
        self._log_event(f"👾 [غزاة الهيبة] إرسال {target_count} مسيرة هجوم على الغزاة حتى لفل {max_lv} (متبقي {needed} لمهام الهيبة)...")

        inv_run_cfg = {
            "monster_type": "invaders",
            "min_lv": cfg.get("min_lv", 1),
            "max_lv": max_lv,
            "formation_id": cfg.get("formation_id", 0),
            "troops_count": cfg.get("troops_count", 30000),
            "search_range": cfg.get("search_range", 80),
            "max_marches": target_count,
            "wait_for_queue": False,
        }
        task = MonsterTask(self.conn, inv_run_cfg)
        res = await task.run()
        return res.success if res else False

    async def _execute_prestige_gather(self, cfg: Dict[str, Any]) -> bool:
        """
        تنفيذ أولوية: جمع موارد مهام الهيبة الأربعة (Prestige Gather) - الأولوية الثالثة.
        - تفحص meritoriousTaskCtrl وتتخطى أي مورد مكتمل مسبقاً.
        - إذا كانت جميع الموارد مكتملة: تتخطى وتعود فوراً لينتقل المنسق للأولوية التالية.
        - ترسل مسيرة جمع بحمولة 25k لكل مورد معلق ما دامت هناك فيالق شاغرة.
        """
        p_cfg = self.config.get("_prestige_config") or self.config.get("prestige", {})
        p_task = PrestigeTask(self.conn, p_cfg)
        await p_task._load_heroes()
        res = await p_task.run_gather_prestige()
        if res.get("skipped"):
            self._log_event("✨ [جمع موارد الهيبة] كافة مهام جمع الموارد مكتملة مسبقاً — الانتقال للأولوية التالية.")
            return False
        dispatched = res.get("dispatched", 0)
        return dispatched > 0

    async def _execute_combat(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: القتال (عفريت أو غزاة أو متمردين) وتوجيه كافة الفيالق المتاحة نحوها."""
        choice = str(cfg.get("choice", cfg.get("type", "none"))).lower()

        # حساب عدد الفيالق الشاغرة حالياً بالقلعة لتوجيه كافة الفيالق المتاحة نحو الهدف القتالي
        active_count = await self._get_active_marches_count()
        if active_count != -1 and active_count < self.max_castle_queues:
            free_slots = max(1, self.max_castle_queues - active_count)
        else:
            free_slots = self.max_castle_queues

        # إذا تم تحديد count صريح > 1 يؤخذ به، وإلا نوجه كافة الفيالق الشاغرة المتاحة
        explicit_count = cfg.get("count")
        if explicit_count is not None and int(explicit_count) > 1:
            target_count = min(int(explicit_count), free_slots)
        else:
            target_count = free_slots

        if choice in ("invaders", "غزاة", "rebels", "متمردين"):
            m_type = "invaders" if choice in ("invaders", "غزاة") else "rebels"
            m_name = "الغزاة (Invaders)" if m_type == "invaders" else "المتمردين (Rebels)"
            self.log.info(f"\n👾 [مهمة قتال: {m_name}] توجيه كافة الفيالق المتاحة ({target_count} فيالق)...")

            m_level = int(cfg.get("level", cfg.get("max_lv", 30)))
            m_form  = int(cfg.get("formation_id", cfg.get("formation", 1)))

            m_run_cfg = {
                "monster_type": m_type,
                "min_lv": m_level,
                "max_lv": m_level,
                "formation_id": m_form,
                "max_marches": target_count,
                "wait_for_queue": False
            }
            task = MonsterTask(self.conn, m_run_cfg)
            res = await task.run()
            return res.success

        elif choice in ("elf", "elf_boss", "عفريت", "العفريت"):
            self.log.info(f"\n👹 [مهمة قتال: نخبة العفريت (Elf Boss)] توجيه كافة الفيالق المتاحة ({target_count} فيالق)...")

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
                "count": target_count,
                "all_legions": True
            }
            task = ElfBossTask(self.conn, elf_run_cfg)
            res = await task.run()
            return res.success
        else:
            self.log.warning(f"⚠️ نوع هدف قتالي غير معروف: '{choice}'. يرجى اختيار 'elf' أو 'invaders' أو 'rebels'.")
            return False

    async def _execute_stronghold(self, cfg: Dict[str, Any]) -> bool:
        """تنفيذ أولوية: الهجوم على الملاجئ العامة."""
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
        start_time = time.time()
        end_time = start_time + self.duration_seconds
        dur_min_display = int(self.duration_seconds // 60)

        self.log.info("══════════════════════════════════════════════════════════")
        self.log.info(f"🎖️ بدء مهمة منسق الفيالق والمسيرات الذكي (المدة الإجمالية: {dur_min_display} دقيقة)")
        self.log.info("══════════════════════════════════════════════════════════")

        # استخراج قائمة الأولويات
        raw_priorities = cfg.get("priority_order") or cfg.get("priorities") or DEFAULT_PRIORITIES
        if isinstance(raw_priorities, str):
            priority_list = [p.strip() for p in raw_priorities.split(",") if p.strip()]
        else:
            priority_list = list(raw_priorities)

        # ضمان شمول كافة المهام المفعلة في الواجهة حتى لو كانت قائمة الأولويات المخزنة في Firebase قديمة أو مجتزأة
        if not cfg.get("_explicit_cli"):
            canonical_order = [
                "prestige_stronghold",
                "prestige_invaders",
                "prestige_gather",
                "transport",
                "ruins",
                "combat",
                "stronghold",
                "gold_gather",
                "gather"
            ]
            normalized_current = [normalize_priority_item(p)[0] for p in priority_list]

            # فحص وتضمين أي مهمة مفعلة بالواجهة لكنها ناقصة في priority_list
            for task_name in canonical_order:
                if task_name not in normalized_current:
                    is_on = False
                    if task_name == "prestige_stronghold":
                        p_cfg = cfg.get("_prestige_config") or cfg.get("prestige", {})
                        is_on = bool(p_cfg.get("enabled", True)) and bool(p_cfg.get("subtasks", {}).get("stronghold", True))
                    elif task_name == "prestige_invaders":
                        p_cfg = cfg.get("_prestige_config") or cfg.get("prestige", {})
                        is_on = bool(p_cfg.get("enabled", True)) and bool(p_cfg.get("subtasks", {}).get("invaders", True))
                    elif task_name == "prestige_gather":
                        p_cfg = cfg.get("_prestige_config") or cfg.get("prestige", {})
                        is_on = bool(p_cfg.get("enabled", True)) and bool(p_cfg.get("subtasks", {}).get("gather", True))
                    elif task_name == "combat":
                        for sub in ("elf", "invaders", "rebels"):
                            if cfg.get(sub, {}).get("enabled") is True:
                                is_on = True
                                break
                        if not is_on and (cfg.get("combat", {}).get("enabled") is True or cfg.get("monster", {}).get("enabled") is True):
                            is_on = True
                    elif task_name == "gold_gather":
                        is_on = bool(cfg.get("gold_gather", {}).get("enabled") or cfg.get("gold", {}).get("enabled"))
                    else:
                        is_on = bool(cfg.get(task_name, {}).get("enabled") is True)

                    if is_on:
                        priority_list.append(task_name)
                        normalized_current.append(task_name)

            # إعادة ترتيب الأولويات وفق الترتيب التكتيكي المعتمد (الملاجئ والغزاة وجمع موارد الهيبة أولاً في القمة، ثم باقي المهام)
            priority_list.sort(
                key=lambda x: canonical_order.index(normalize_priority_item(x)[0])
                if normalize_priority_item(x)[0] in canonical_order
                else 99
            )

        # هل قام المستخدم بتحديد قائمة مخصصة محددة؟
        is_custom_subset = (priority_list != DEFAULT_PRIORITIES)

        handlers = {
            "prestige_stronghold": self._execute_prestige_stronghold,
            "prestige_invaders":   self._execute_prestige_invaders,
            "prestige_gather":     self._execute_prestige_gather,
            "transport":           self._execute_transport,
            "ruins":               self._execute_ruins,
            "combat":              self._execute_combat,
            "stronghold":          self._execute_stronghold,
            "gold_gather":         self._execute_gold_gather,
            "gather":              self._execute_gather,
        }

        display_titles = {
            "prestige_stronghold": "ملاجئ مهام الهيبة (Prestige Strongholds)",
            "prestige_invaders":   "غزاة مهام الهيبة (Prestige Invaders)",
            "prestige_gather":     "جمع موارد الهيبة 25k (Prestige Gather)",
            "transport":           "مساعدة الموارد (Transport)",
            "ruins":               "استكشاف الأطلال (Ruins)",
            "combat":              "القتال (Combat)",
            "stronghold":          "الهجوم على الملاجئ (Stronghold)",
            "gold_gather":         "جمع الذهب (Gold Gathering)",
            "gather":              "جمع الموارد (Gathering)",
        }

        self.log.info(f"📋 مسار الأولويات المعتمد لهذه المهمة: {priority_list}")

        cycle_count = 0
        overall_summary: Dict[str, int] = {}
        total_marches_sent = 0

        # ── الحلقة المستمرة طوال مدة المهمة (افتراضياً 20 دقيقة ككل) ────────
        while True:
            if self._is_stop_requested():
                self.log.info("🛑 تم استلام إشارة إيقاف، إنهاء مهمة منسق الفيالق فوراً.")
                break

            now = time.time()
            if now >= end_time:
                self.log.info(f"🏁 اكتملت المدة الإجمالية المحددة لمنسق الفيالق ({dur_min_display} دقيقة).")
                break

            rem_total_sec = max(0, int(end_time - now))
            rem_m, rem_s = divmod(rem_total_sec, 60)
            cycle_count += 1

            self._log_event(f"🔄 [منسق الفيالق - جولة {cycle_count}] فحص الفيالق ومطابقة الأولويات | الوقت المتبقي: {rem_m}د و{rem_s}ث")

            executed_in_this_cycle = False

            # فحص توفر فيالق متاحة
            has_free, active_count = await self._has_free_queues()

            if has_free:
                for index, item_name in enumerate(priority_list, 1):
                    if self._is_stop_requested() or time.time() >= end_time:
                        break

                    task_type, forced_choice = normalize_priority_item(item_name)
                    title = display_titles.get(task_type, task_type)
                    if forced_choice:
                        title += f" [{forced_choice}]"

                    if task_type not in handlers:
                        self.log.warning(f"⚠️ تخطي مهمة غير معروفة في الأولويات: '{item_name}'")
                        continue

                    # فحص التفعيل
                    is_enabled, task_cfg = self._resolve_task_config(task_type, forced_choice)
                    if is_custom_subset and not cfg.get("_explicit_cli") and "enabled" not in cfg.get(task_type, {}):
                        is_enabled = True

                    if not is_enabled:
                        continue

                    # فحص توفر فيالق قبل تشغيل المهمة
                    has_free_before, active_before = await self._has_free_queues()
                    if not has_free_before:
                        self._log_event(f"🛑 كافة الفيالق أصبحت ممتلئة بالكامل ({active_before}/{self.max_castle_queues}) قبل تشغيل {title}.")
                        break

                    self._log_event(f"▶️ [الأولوية {index}/{len(priority_list)}] بدء تنفيذ: {title}...")
                    handler_func = handlers[task_type]

                    try:
                        success = await handler_func(task_cfg)
                        summary_key = f"{task_type}_{forced_choice}" if forced_choice else task_type
                        if success:
                            executed_in_this_cycle = True
                            total_marches_sent += 1
                            overall_summary[summary_key] = overall_summary.get(summary_key, 0) + 1
                    except Exception as e:
                        self.log.error(f"❌ خطأ أثناء تنفيذ {title}: {e}", exc_info=True)

                    # استراحة أمان بشرية قصيرة بين المهام
                    await asyncio.sleep(random.uniform(2.5, 4.0))

                    # فحص الفيالق بعد تنفيذ المهمة
                    has_free_after, active_after = await self._has_free_queues()
                    if not has_free_after:
                        self.log.info(f"🛑 اكتملت طوابير الفيالق بالكامل ({active_after}/{self.max_castle_queues}) بعد {title}.")
                        break

            # فحص هل تم طلب إيقاف أو نفد وقت المهمة ككل
            if self._is_stop_requested() or time.time() >= end_time:
                break

            # فحص حالة الفيالق بعد محاولة الإرسال
            has_free_now, current_active = await self._has_free_queues()

            if not has_free_now:
                # كافة الفيالق في الميدان حالياً -> ننتظر حتى يعود أي فيلق للقلعة
                self._log_event(
                    f"⏳ كافة الفيالق ({current_active}/{self.max_castle_queues}) في الميدان حالياً. "
                    f"انتظار عودة أي فيلق شاغر إلى القلعة لمواصلة المهام... (المتبقي ككل: {rem_m}د و{rem_s}ث)"
                )

                wait_poll_count = 0
                # حلقة مراقبة خفيفة تفحص حزمة 1007/16 دورياً كل 10 ثوانٍ
                while time.time() < end_time and not self._is_stop_requested():
                    sleep_time = min(10.0, max(1.0, end_time - time.time()))
                    await asyncio.sleep(sleep_time)

                    if self._is_stop_requested() or time.time() >= end_time:
                        break

                    active_check = await self._get_active_marches_count()
                    now_check = time.time()
                    rem_chk = max(0, int(end_time - now_check))
                    rm_chk, rs_chk = divmod(rem_chk, 60)
                    wait_poll_count += 1

                    # هل عاد فيلق وأصبح شاغراً؟
                    if active_check != -1 and active_check < self.max_castle_queues:
                        freed = self.max_castle_queues - active_check
                        self._log_event(
                            f"✨ عاد فيلق إلى القلعة! الفيالق النشطة الآن: {active_check}/{self.max_castle_queues} "
                            f"(يوجد {freed} فيلق شاغر). استئناف الهجمات والمسيرات فوراً..."
                        )
                        break
                    else:
                        if wait_poll_count % 3 == 0:
                            self._log_event(
                                f"⏳ لا تزال كافة الفيالق في الميدان ({active_check if active_check != -1 else '?'}/{self.max_castle_queues})... "
                                f"(المتبقي للمهمة ككل: {rm_chk}د و{rs_chk}ث)"
                            )
            else:
                # توجد فيالق شاغرة ولكن لم يتم إرسال مسيرات جديدة في هذه الدورة
                # (مثل انتهاء الأهداف المتاحة حالياً أو عدم تفعيل مهام أخرى للفيالق المتبقية)
                if not executed_in_this_cycle:
                    # إذا كانت هناك قوات في الميدان بالفعل (current_active > 0) وسقف الفيالق أعلى منها لكن تعذر الإرسال:
                    # نضبط سعة القلعة إلى current_active لنتجنب التكرار العقيم وننتظر عودة الفيلق حتى نهاية مدة الـ 20 دقيقة
                    if current_active > 0 and self.max_castle_queues > current_active:
                        self._log_event(f"💡 استشعار سعة فيالق القلعة الفعلية: {current_active} مسيرة نشطة بالكامل. انتظار عودة الفيالق...")
                        self.max_castle_queues = current_active
                        continue

                    self._log_event(f"ℹ️ لم تُرسل مسيرات جديدة في هذه الدورة. انتظار 15 ثانية قبل إعادة الفحص... (متبقي {rem_m}د و{rem_s}ث)")
                    sleep_time = min(15.0, max(1.0, end_time - time.time()))
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(random.uniform(3.0, 5.0))

        self.log.info("\n══════════════════════════════════════════════════════════")
        self.log.info("🏁 اكتملت فترة تشغيل منسق الفيالق الذكي!")
        self.log.info(f"📊 إجمالي الدورات: {cycle_count} | إجمالي المسيرات الناجحة: {total_marches_sent}")
        self.log.info(f"📋 تفاصيل العمليات المنفذة: {overall_summary}")
        self.log.info("══════════════════════════════════════════════════════════")

        return TaskResult.ok(
            f"اكتملت مهمة منسق الفيالق ({dur_min_display} دقيقة) بإجمالي {total_marches_sent} مسيرة",
            summary=overall_summary,
            cycles=cycle_count,
            total_marches=total_marches_sent
        )


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

    # سعة الفيالق والمدة
    parser.add_argument("--max-queues", type=int, default=MAX_CASTLE_QUEUES, help=f"أقصى عدد فيالق للقلعة [افتراضي: {MAX_CASTLE_QUEUES}]")
    parser.add_argument("--duration", "--duration-minutes", dest="duration_minutes", type=int, default=DEFAULT_TASK_DURATION_MINUTES, help=f"المدة الإجمالية لتشغيل المهمة بالدقائق [افتراضي: {DEFAULT_TASK_DURATION_MINUTES} دقيقة (ثلث ساعة)]")

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

    final_config.setdefault("duration_minutes", args.duration_minutes)
    final_config.setdefault("max_queues", args.max_queues)

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
