# -*- coding: utf-8 -*-
"""
tasks/fortress.py — مهمة تدريب فخاخ حصن الحرب تلقائياً مع حساب الحد الأقصى التلقائي
══════════════════════════════════════════════════════════════════════════════════════

بروتوكول تدريب فخاخ حصن الحرب (War Fortress & Traps Protocol):
  - بدء التدريب:     cmd: "1005", subcmd: "2", data: {"bid": "120", "armyid": str(armyid), "armycount": str(count), "mode": "0", "isget": false}
  - جمع/استلام الفخاخ: cmd: "1005", subcmd: "5", data: {"bid": "120"}
  - طابور التدريب:   queueCtrl['1207'] أو qdata.bid == '120'

فئات الفخاخ ومستويات فتحها في حصن الحرب (bid: 120):
  1. 🪨 الصخور المتساقطة (Falling Rocks):
     - رتبة 1: 801 (حصن مستوى 1)
     - رتبة 2: 802 (حصن مستوى 6)
     - رتبة 3: 803 (حصن مستوى 12)
     - رتبة 4: 804 (حصن مستوى 18)
     - رتبة 5: 805 (حصن مستوى 24)
  2. 🏹 سهام السور (Wall Arrows):
     - رتبة 1: 811 (حصن مستوى 2)
     - رتبة 2: 812 (حصن مستوى 8)
     - رتبة 3: 813 (حصن مستوى 14)
     - رتبة 4: 814 (حصن مستوى 20)
     - رتبة 5: 815 (حصن مستوى 27)
  3. 🔥 فخاخ النفط المتفجرة / الجذوع (Oil / Fire Traps):
     - رتبة 1: 821 (حصن مستوى 3)
     - رتبة 2: 822 (حصن مستوى 10)
     - رتبة 3: 823 (حصن مستوى 16)
     - رتبة 4: 824 (حصن مستوى 22)
     - رتبة 5: 825 (حصن مستوى 30)

حساب الحد الأقصى التلقائي للفخاخ (Auto Max Detection):
  1. سعة السور الإجمالية (السور bid: 102 يعطي 1,000 لكل مستوى + أبحاث سعة الفخاخ 23006 و 23014).
  2. الفراغ المتاح على السور = السعة القصوى - إجمالي الفخاخ القائمة حالياً على السور (801..825).
  3. سقف الدفعة الواحدة (إنتاج 10 ساعات = 36000 / سرعة بناء الفخ + إضافات السمات V_TRAIN_ARMY).
  4. سقف الموارد المتوفرة في القلعة (طعام، خشب، حديد، فضة).
  5. الناتج التلقائي النهائي = min(سقف الدفعة, الفراغ المتبقي على السور, سقف الموارد).

الاستخدام كملف مستقل:
    python tasks/fortress.py --email "user@gmail.com" --type rocks --level 2 --count max
    python tasks/fortress.py --email "user@gmail.com" --type oil --count max
    python tasks/fortress.py --email "user@gmail.com" --type arrows
    python tasks/fortress.py --email "meik.gaertner2306.MGr@gmail.com" --type auto
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
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection

# تحميل قاعدة بيانات القوات والتكاليف المستخرجة من كود اللعبة
_ARMY_DB_PATH = os.path.join(_ROOT_DIR, "core", "army_database.json")
_ARMY_DATABASE: Dict[str, Any] = {}
if os.path.exists(_ARMY_DB_PATH):
    try:
        with open(_ARMY_DB_PATH, "r", encoding="utf-8") as _f:
            _ARMY_DATABASE = json.load(_f)
    except Exception:
        pass

# جدول إضافات أبحاث سعة الفخاخ الرسمية من technology.lua (TRAP_CAP = 22)
_TECH_TRAP_CAP: Dict[int, Dict[int, int]] = {
    23006: {1: 200, 2: 400, 3: 600, 4: 800, 5: 1000, 6: 1200, 7: 1400, 8: 1600, 9: 1800, 10: 2000},
    23014: {1: 450, 2: 900, 3: 1350, 4: 1800, 5: 2250, 6: 2700, 7: 3150, 8: 3600, 9: 4050, 10: 4500, 11: 4950, 12: 5400, 13: 5850, 14: 6300, 15: 6750}
}

# جدول إضافات أبحاث سرعة بناء الفخاخ من technology.lua (CONSTRUCTION_SPEED_TRAP = 23)
_TECH_TRAP_SPEED: Dict[int, Dict[int, float]] = {
    23009: {1: 0.01, 2: 0.02, 3: 0.03, 4: 0.04, 5: 0.05, 6: 0.06, 7: 0.07, 8: 0.08, 9: 0.09, 10: 0.10},
    23018: {1: 0.02, 2: 0.04, 3: 0.06, 4: 0.08, 5: 0.10, 6: 0.12, 7: 0.14, 8: 0.16, 9: 0.18, 10: 0.20,
            11: 0.22, 12: 0.24, 13: 0.26, 14: 0.28, 15: 0.30, 16: 0.32, 17: 0.34, 18: 0.36, 19: 0.38, 20: 0.40}
}

# ════════════════════════════════════════════════════════════════════
#  تعريف فئات الفخاخ ومستويات فتحها في حصن الحرب
# ════════════════════════════════════════════════════════════════════

TRAP_FAMILIES: Dict[str, Dict[str, Any]] = {
    "rocks": {
        "key": "rocks",
        "name_ar": "الصخور المتساقطة",
        "name_en": "Falling Rocks",
        "icon": "🪨",
        "target_id": 16,  # TRAP_STONE
        "tiers": {1: 801, 2: 802, 3: 803, 4: 804, 5: 805},
        "unlock_levels": {1: 1, 2: 6, 3: 12, 4: 18, 5: 24},
        "default_times": {801: 25, 802: 40, 803: 70, 804: 130, 805: 250}
    },
    "arrows": {
        "key": "arrows",
        "name_ar": "سهام السور",
        "name_en": "Wall Arrows",
        "icon": "🏹",
        "target_id": 17,  # TRAP_ARROW
        "tiers": {1: 811, 2: 812, 3: 813, 4: 814, 5: 815},
        "unlock_levels": {1: 2, 2: 8, 3: 14, 4: 20, 5: 27},
        "default_times": {811: 25, 812: 40, 813: 70, 814: 130, 815: 250}
    },
    "oil": {
        "key": "oil",
        "name_ar": "فخاخ النفط المتفجرة",
        "name_en": "Oil Traps",
        "icon": "🔥",
        "target_id": 15,  # TRAP_WOOD
        "tiers": {1: 821, 2: 822, 3: 823, 4: 824, 5: 825},
        "unlock_levels": {1: 3, 2: 10, 3: 16, 4: 22, 5: 30},
        "default_times": {821: 25, 822: 40, 823: 70, 824: 130, 825: 250}
    }
}

TRAP_ALIASES: Dict[str, str] = {
    # الصخور
    "rocks": "rocks", "rock": "rocks", "صخور": "rocks", "الصخور": "rocks", "حجارة": "rocks", "الحجارة": "rocks", "1": "rocks", "801": "rocks",
    # السهام
    "arrows": "arrows", "arrow": "arrows", "سهام": "arrows", "السهام": "arrows", "اسهم": "arrows", "الأسهم": "arrows", "2": "arrows", "811": "arrows",
    # النفط / الجذوع
    "oil": "oil", "fire": "oil", "نفط": "oil", "النفط": "oil", "جذوع": "oil", "الجذوع": "oil", "فخاخ": "oil", "الفخاخ": "oil", "3": "oil", "821": "oil",
    # تلقائي / الكل
    "all": "auto", "auto": "auto", "الكل": "auto", "تلقائي": "auto"
}


def get_max_unlocked_trap_tier(family_key: str, fortress_lv: int) -> int:
    """معرفة أقصى رتبة فخ مفتوحة للفئة المختارة بناءً على مستوى حصن الحرب."""
    family = TRAP_FAMILIES.get(family_key)
    if not family:
        return 1
    max_t = 1
    for tier, req_lv in family["unlock_levels"].items():
        if fortress_lv >= req_lv:
            max_t = max(max_t, tier)
    return max_t


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (FortressTask)
# ════════════════════════════════════════════════════════════════════

class FortressTask(BaseTask):
    """
    مهمة تدريب فخاخ حصن الحرب التلقائية (War Fortress) مع الاكتشاف التلقائي الكامل للحد الأقصى.
    """
    name = "fortress"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self.selected_family = self._parse_family_config()
        self.requested_level = self.config.get("level", None)
        self.requested_count = self.config.get("count", "max")

    def _parse_family_config(self) -> str:
        raw = str(self.config.get("type", self.config.get("types", "auto"))).strip().lower()
        if not raw or raw in ("auto", "all", "الكل", "تلقائي"):
            return "auto"
        return TRAP_ALIASES.get(raw, "auto")

    async def on_start(self):
        """انتظار وصول حزم البيانات الأساسية من السيرفر (cityCtrl, queueCtrl, armyCtrl)."""
        for _ in range(15):
            has_city = "cityCtrl" in self.conn.init_data
            has_queue = "queueCtrl" in self.conn.init_data
            has_army = "armyCtrl" in self.conn.init_data
            if has_city and has_queue and has_army:
                break
            await asyncio.sleep(0.3)
        await asyncio.sleep(0.3)

    def _get_building_info(self, bid: str) -> Tuple[int, int]:
        """استخراج مستوى وحالة المبنى من قائمة المباني blist."""
        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        blist = city_ctrl.get("blist", []) if isinstance(city_ctrl, dict) else []
        for b in blist:
            binfo = b.get("binfo", {})
            if str(binfo.get("bid")) == str(bid):
                return int(binfo.get("lv", 0)), int(binfo.get("state", 0))
        return 0, 0

    def _get_wall_total_capacity(self) -> Tuple[int, int, int]:
        """
        حساب سعة السور الإجمالية القصوى للفخاخ بدقة:
          - سعة السور الأساسية من مستوى مبنى السور (bid: 102): مستوى السور × 1000.
          - إضافات أبحاث التكنولوجيا لسعة الفخاخ (technologyCtrl):
              * بحث 23006: حتى 2,000 فخ
              * بحث 23014: حتى 6,750 فخ
        تعيد: (السعة_الإجمالية, السعة_الأساسية, إضافات_التكنولوجيا)
        """
        wall_lv, _ = self._get_building_info("102")
        base_cap = wall_lv * 1000

        tech_ctrl = self.conn.init_data.get("technologyCtrl", {})
        tech_add = 0
        if isinstance(tech_ctrl, dict):
            for tid_str, tdata in tech_ctrl.items():
                try:
                    tid = int(tid_str)
                    lvl = int(tdata) if isinstance(tdata, (int, str)) else int(tdata.get("lv", 0) if isinstance(tdata, dict) else 0)
                    if tid in _TECH_TRAP_CAP:
                        tech_add += _TECH_TRAP_CAP[tid].get(lvl, 0)
                except Exception:
                    pass

        total_cap = base_cap + tech_add
        return total_cap, base_cap, tech_add

    def _get_standing_traps(self) -> Tuple[int, Dict[str, int]]:
        """حساب إجمالي وتفاصيل الفخاخ القائمة حالياً على السور (المعرفات 800..899)."""
        army_ctrl = self.conn.init_data.get("armyCtrl", {})
        total_army = army_ctrl.get("totalArmy", {}) if isinstance(army_ctrl, dict) else {}
        standing = {}
        total_count = 0
        for aid_str, count in total_army.items():
            try:
                aid = int(aid_str)
                c = int(count)
                if 800 <= aid <= 899 and c > 0:
                    standing[str(aid)] = c
                    total_count += c
            except Exception:
                pass
        return total_count, standing

    def _calculate_auto_trap_count(self, armyid: int) -> dict:
        """
        محاكاة دقيقة 100% لخوارزمية اللعبة الأصلية لحصن الحرب المستخرجة من:
          - armyLogic.lua (getTotalTrapCapacity, getMaxTrapBuildCount, getTrapBuildTime)
          - soldiersCampView.lua
          - buildLogic.lua
        تحسب:
          1. السعة القصوى للسور والفراغ المتبقي (Remaining Wall Space = Total Cap - Standing Traps).
          2. سقف إنتاج الدفعة الواحدة (10-Hour Batch Limit = 36000 / BuildTime + V_TRAIN_ARMY).
          3. سقف الموارد المتوفرة في القلعة (طعام، خشب، حديد، فضة).
          4. الناتج التلقائي النهائي = min(سقف الدفعة, الفراغ المتبقي على السور, سقف الموارد).
        """
        aid_str = str(armyid)
        army_info = _ARMY_DATABASE.get(aid_str, {})
        cost_res = army_info.get("costRes", {})
        base_train_time = army_info.get("trainingTime") or 25

        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        reslist = city_ctrl.get("reslist", {})

        # 1. سقف الموارد (resTrain)
        res_train = 999999999
        missing_res = []
        res_names = {"1002": "طعام", "1003": "خشب", "1004": "حديد", "1005": "فضة", "1006": "ذهب"}

        for resid_str, cost_per_unit in cost_res.items():
            cur_count = float(reslist.get(str(resid_str), 0))
            if cost_per_unit > 0:
                affordable = int(cur_count // cost_per_unit)
                if affordable < res_train:
                    res_train = affordable
                if affordable == 0:
                    missing_res.append(res_names.get(str(resid_str), str(resid_str)))

        # 2. سعة السور والفراغ المتبقي
        total_wall_cap, base_wall_cap, tech_wall_add = self._get_wall_total_capacity()
        standing_total, standing_details = self._get_standing_traps()
        space_left = max(0, total_wall_cap - standing_total)

        # 3. سقف إنتاج الدفعة الواحدة (10-Hour Cap)
        # سرعة بناء الفخاخ (Technology + Lord Skills + Boe Attributes)
        tech_ctrl = self.conn.init_data.get("technologyCtrl", {})
        tech_speed = 0.0
        if isinstance(tech_ctrl, dict):
            for tid_str, tdata in tech_ctrl.items():
                try:
                    tid = int(tid_str)
                    lvl = int(tdata) if isinstance(tdata, (int, str)) else int(tdata.get("lv", 0) if isinstance(tdata, dict) else 0)
                    if tid in _TECH_TRAP_SPEED:
                        tech_speed += _TECH_TRAP_SPEED[tid].get(lvl, 0.0)
                except Exception:
                    pass

        # مهارات اللورد لسرعة الفخاخ (13004 بناء الفخاخ 1، 13012 بناء الفخاخ 2)
        lord_skills = self.conn.init_data.get("lordSkillCtrl", {})
        active_set = str(lord_skills.get("activeSetID", "1")) if isinstance(lord_skills, dict) else "1"
        set_data = lord_skills.get("setListData", {}) if isinstance(lord_skills, dict) else {}
        curr_set = set_data.get(active_set) or set_data.get(int(active_set) if active_set.isdigit() else 1) or {}
        s_list = curr_set.get("list", {}) if isinstance(curr_set, dict) else {}
        if not s_list:
            sb = self.conn.init_data.get("lordInfoCtrl", {}).get("skill", {}).get("skillBasic", {})
            s_list = {k: (v[1] if isinstance(v, list) and len(v) > 1 else v) for k, v in sb.items()} if isinstance(sb, dict) else {}

        sk1 = int(s_list.get("13004", 0)) if isinstance(s_list, dict) else 0
        sk2 = int(s_list.get("13012", 0)) if isinstance(s_list, dict) else 0
        skill_speed = (sk1 * 0.01) + (sk2 * 0.02)

        # سمات boeAttributeCtrl للفخاخ (target 6, 15, 16, 17)
        # Attribute 21 = P_TRAIN_SPEED, Attribute 20 = V_TRAIN_ARMY
        boe_attr = self.conn.init_data.get("boeAttributeCtrl", {})
        mod0 = boe_attr.get("0", {}) if isinstance(boe_attr, dict) else {}

        aid_int = int(armyid)
        if 801 <= aid_int <= 805:
            target_id = 16  # TRAP_STONE
        elif 811 <= aid_int <= 815:
            target_id = 17  # TRAP_ARROW
        else:
            target_id = 15  # TRAP_WOOD

        related_targets = [target_id, 6]  # الفئة والهدف العام للفخاخ
        boe_speed = 0.0
        boe_train_add = 0.0

        if isinstance(mod0, dict) and mod0:
            for tid in related_targets:
                t_data = mod0.get(str(tid), {})
                if isinstance(t_data, dict):
                    # سرعة التدريب (21)
                    val_21 = t_data.get("21", {})
                    if isinstance(val_21, dict):
                        boe_speed += float(val_21.get("2", 0)) / 1000.0
                    # زيادة كمية التدريب (20)
                    val_20 = t_data.get("20", {})
                    if isinstance(val_20, dict):
                        boe_train_add += float(val_20.get("2", 0))

        total_speed_bonus = tech_speed + skill_speed + boe_speed
        actual_train_time = max(1.0, float(base_train_time) * (1.0 / (1.0 + total_speed_bonus)))

        # خوارزمية اللعبة الرسمية: math.floor(36000 / actual_train_time) + addTrainNum
        one_count = int(36000 // actual_train_time)
        batch_limit = one_count + int(boe_train_add)

        # 4. التوليف النهائي
        # الفخاخ لا يمكن أن تتجاوز سعة الدفعة، ولا الفراغ المتبقي على السور، ولا الموارد
        final_count = min(batch_limit, space_left, res_train)
        has_enough_res = (res_train >= 1)
        has_wall_space = (space_left >= 1)

        return {
            "armyid": armyid,
            "bid": "120",
            "wall_total_cap": total_wall_cap,
            "wall_base_cap": base_wall_cap,
            "wall_tech_add": tech_wall_add,
            "standing_traps_total": standing_total,
            "standing_traps_details": standing_details,
            "space_left_on_wall": space_left,
            "batch_limit": batch_limit,
            "res_train_cap": res_train,
            "final_trap_count": max(0, final_count) if (has_enough_res and has_wall_space) else 0,
            "has_enough_resources": has_enough_res,
            "has_wall_space": has_wall_space,
            "missing_resources": missing_res
        }

    async def _harvest_finished_traps(self) -> bool:
        """جمع واستلام الفخاخ المكتمل بناؤها في حصن الحرب (bid: 120)."""
        r_get = await self.conn.query("1005", "5", {"bid": "120"}, timeout=6)
        if r_get and str(r_get.get("err", "0")) == "0":
            return True
        return False

    async def _train_adaptive(self, armyid: int, initial_count: int) -> Tuple[bool, int, str]:
        """
        إرسال طلب تدريب الفخاخ بالعدد المحسوب بدقة، مع نظام تصحيح تكيفي سريع:
          1. بما أن الحساب دقيق ومطابق لمعادلة اللعبة والسور، ينجح الطلب عادة فوراً (err: 0).
          2. في حال حدوث تجاوز سعة (4004 / 4003)، ينزل تدريجياً بالوحدات أولاً (1، 2، 3، 5) ثم بنسبة 10%.
          3. إعادة محاولة تلقائية في حال حدوث بطء في الشبكة (timeout).
          4. تشخيص الأخطاء وترجمتها بوضوح.
        """
        curr_count = initial_count
        attempts = 0
        max_attempts = 20
        last_err = ""

        while curr_count >= 1 and attempts < max_attempts:
            attempts += 1
            payload = {
                "bid": "120",
                "armyid": str(armyid),
                "armycount": str(curr_count),
                "mode": "0",
                "isget": False
            }

            resp = None
            for _retry in range(2):
                resp = await self.conn.query("1005", "2", payload, timeout=6)
                if resp:
                    break
                await asyncio.sleep(0.3)

            err = str(resp.get("err", "0")) if resp else "timeout"
            last_err = err

            if err == "0":
                return True, curr_count, "0"

            elif err == "4002":
                return False, 0, "حصن الحرب مشغول بعملية تدريب جارية حالياً (busy)"

            elif err == "4001":
                return False, 0, "رتبة الفخ غير مفتوحة أو مستوى حصن الحرب غير كافٍ"

            elif err in ("4004", "4003"):
                # نزول تكيفي ذكي
                if attempts == 1:
                    curr_count = max(1, curr_count - 1)
                elif attempts == 2:
                    curr_count = max(1, curr_count - 2)
                elif attempts == 3:
                    curr_count = max(1, curr_count - 3)
                elif attempts == 4:
                    curr_count = max(1, curr_count - 5)
                else:
                    step = max(1, int(curr_count * 0.1))
                    curr_count = max(1, curr_count - step)

            elif err == "timeout":
                self.log.warning(f"⚠️ بطء مؤقت في استجابة السيرفر (timeout)، محاولة تخفيض العدد...")
                curr_count = max(1, curr_count - 5)
            else:
                return False, 0, f"كود سيرفر: {err}"

            await asyncio.sleep(0.15)

        return False, 0, f"تجاوز السعة القصوى المتاحة على السور (كود: {last_err})"

    def _select_trap_armyid(self, fortress_lv: int) -> Tuple[str, int, int]:
        """
        تحديد فئة ورتبة ومعرف الفخ (armyid) المناسب بناءً على إعدادات المستخدم ومستوى الحصن:
        تعيد: (family_key, tier, armyid)
        """
        # إذا تم اختيار فئة محددة
        chosen_family = self.selected_family
        if chosen_family == "auto":
            # اختيار الفئة التي تملك أعلى رتبة مفتوحة، أو التناوب الذكي
            # الترتيب الافتراضي: النفط أولاً ثم الصخور ثم السهام
            best_f = "oil"
            best_tier = get_max_unlocked_trap_tier("oil", fortress_lv)
            for f_key in ("rocks", "arrows"):
                t = get_max_unlocked_trap_tier(f_key, fortress_lv)
                if t > best_tier:
                    best_f = f_key
                    best_tier = t
            chosen_family = best_f

        family = TRAP_FAMILIES.get(chosen_family, TRAP_FAMILIES["rocks"])
        max_unlocked = get_max_unlocked_trap_tier(chosen_family, fortress_lv)

        if self.requested_level is not None:
            tier = min(int(self.requested_level), max_unlocked)
        else:
            tier = max_unlocked

        tier = max(1, min(5, tier))
        armyid = family["tiers"][tier]
        return chosen_family, tier, armyid

    async def run(self) -> TaskResult:
        # مزامنة سريعة لبيانات الحساب لضمان أحدث حالة
        try:
            r_sync = await self.conn.query("1005", "1", {}, timeout=4)
            if r_sync and isinstance(r_sync.get("data"), dict):
                ret_d = r_sync["data"]
                if "trainArmy" in ret_d:
                    self.conn.init_data.setdefault("armyCtrl", {})["trainArmy"] = ret_d["trainArmy"]
        except Exception:
            pass

        now_ts = int(time.time())

        # ════════════════════════════════════════════════════════════════
        # المرحلة 1: فحص واستلام أي فخاخ جاهزة في حصن الحرب (bid: 120)
        # ════════════════════════════════════════════════════════════════
        self.log.info("🔍 فحص حصن الحرب لجمع أي فخاخ مكتمل بناؤها...")
        harvested = False

        army_ctrl = self.conn.init_data.get("armyCtrl", {})
        train_army = army_ctrl.get("trainArmy", {}) if isinstance(army_ctrl, dict) else {}
        queue_ctrl = self.conn.init_data.get("queueCtrl", {}) if isinstance(self.conn.init_data.get("queueCtrl"), dict) else {}

        is_ready = False
        ready_details = {}

        if "120" in train_army and train_army["120"]:
            is_ready = True
            ready_details = train_army["120"]

        if not is_ready:
            for qid, qdata in queue_ctrl.items():
                if isinstance(qdata, dict) and (str(qdata.get("data", {}).get("bid")) == "120" or str(qid) == "1207"):
                    st = int(qdata.get("starttime", 0))
                    tt = int(qdata.get("totaltime", 0))
                    if st + tt > 0 and now_ts >= (st + tt):
                        is_ready = True
                        ready_details = {
                            str(qdata.get("data", {}).get("armyid")): str(qdata.get("data", {}).get("armycount"))
                        }
                    break

        if is_ready:
            self.log.info(f"📦 وُجدت فخاخ جاهزة للاستلام في حصن الحرب (معلومات: {ready_details})! جاري الجمع...")
            resp = await self.conn.query("1005", "5", {"bid": "120"}, timeout=6)
            err = str(resp.get("err", "0")) if resp else "timeout"
            if err == "0":
                self.log.info("✅ تم بنجاح جمع واستلام الفخاخ الجاهزة من حصن الحرب! 🏰")
                harvested = True
                if "120" in train_army:
                    del train_army["120"]
                for qid in list(queue_ctrl.keys()):
                    if isinstance(queue_ctrl[qid], dict) and (str(queue_ctrl[qid].get("data", {}).get("bid")) == "120" or str(qid) == "1207"):
                        del queue_ctrl[qid]
                await asyncio.sleep(1.2)
            else:
                self.log.warning(f"⚠️ تعذر استلام الفخاخ (كود: {err})")

        # ════════════════════════════════════════════════════════════════
        # المرحلة 2: التحقق من حالة حصن الحرب والسور
        # ════════════════════════════════════════════════════════════════
        fortress_lv, fortress_state = self._get_building_info("120")
        if fortress_lv <= 0:
            msg = "⚠️ مبنى حصن الحرب (bid: 120) غير مشيد في القلعة!"
            self.log.warning(msg)
            return TaskResult.fail(msg)

        wall_lv, _ = self._get_building_info("102")
        self.log.info(f"🏰 فحص المنشآت: حصن الحرب (مستوى {fortress_lv}) | السور (مستوى {wall_lv})")

        # فحص ما إذا كان الحصن قيد البناء/التدريب حالياً
        active_queue = None
        for qid, qdata in queue_ctrl.items():
            if isinstance(qdata, dict) and (str(qdata.get("data", {}).get("bid")) == "120" or str(qid) == "1207"):
                active_queue = qdata
                break

        if active_queue:
            start_t = int(active_queue.get("starttime", 0))
            total_t = int(active_queue.get("totaltime", 0))
            end_t = start_t + total_t
            if now_ts < end_t:
                rem_s = max(1, end_t - now_ts)
                rem_m = max(1, rem_s // 60)
                msg = f"⏳ حصن الحرب مشغول بعملية تدريب جارية حالياً (متبقي: {rem_m} دقيقة)."
                self.log.info(msg)
                return TaskResult.ok(
                    msg,
                    status="busy",
                    retry_after=rem_s,
                    data={"busy": True, "remaining_seconds": rem_s}
                )

        # ════════════════════════════════════════════════════════════════
        # المرحلة 3: تحديد نوع الفخ والحساب التلقائي للحد الأقصى
        # ════════════════════════════════════════════════════════════════
        family_key, tier, armyid = self._select_trap_armyid(fortress_lv)
        family_meta = TRAP_FAMILIES[family_key]
        f_name = family_meta["name_ar"]
        f_icon = family_meta["icon"]

        calc = self._calculate_auto_trap_count(armyid)

        self.log.info(
            f"📊 الفحص التلقائي لحصن الحرب:\n"
            f"   • السعة الإجمالية للسور: {calc['wall_total_cap']:,} (أساسي: {calc['wall_base_cap']:,} + أبحاث: {calc['wall_tech_add']:,})\n"
            f"   • الفخاخ القائمة على السور: {calc['standing_traps_total']:,} فخ\n"
            f"   • الفراغ المتاح على السور: {calc['space_left_on_wall']:,} فخ\n"
            f"   • سقف إنتاج الدفعة الواحدة: {calc['batch_limit']:,} فخ\n"
            f"   • سقف الموارد المتوفرة: {calc['res_train_cap']:,} فخ\n"
            f"   🎯 الناتج التلقائي الصافي المتاح للتدريب: {calc['final_trap_count']:,} فخ"
        )

        if not calc["has_wall_space"]:
            msg = f"🛑 السور ممتلئ بالكامل بالفخاخ ({calc['standing_traps_total']:,} / {calc['wall_total_cap']:,})! لا يوجد فراغ متاح لبناء فخاخ جديدة."
            self.log.warning(msg)
            return TaskResult.ok(msg, status="no_action", data=calc)

        if not calc["has_enough_resources"]:
            missing_str = ", ".join(calc["missing_resources"]) if calc["missing_resources"] else "الموارد"
            msg = f"⚠️ تعذر تدريب الفخاخ لعدم كفاية الموارد في القلعة! (نقص في: {missing_str})"
            self.log.warning(msg)
            return TaskResult.ok(msg, status="no_action", data=calc)

        if str(self.requested_count).lower() == "max":
            target_count = calc["final_trap_count"]
        else:
            try:
                target_count = min(int(self.requested_count), calc["final_trap_count"])
            except Exception:
                target_count = calc["final_trap_count"]

        if target_count <= 0:
            msg = "⚠️ العدد المتاح لتدريب الفخاخ هو 0، تم التخطي."
            self.log.warning(msg)
            return TaskResult.ok(msg, status="no_action", data=calc)

        # ════════════════════════════════════════════════════════════════
        # المرحلة 4: إرسال أمر التدريب مع الضبط التكيفي
        # ════════════════════════════════════════════════════════════════
        self.log.info(
            f"🚀 بدء تدريب {f_icon} [{f_name}] | المستوى: {tier} (معرف: {armyid}) | المستهدف: {target_count:,} فخ..."
        )

        success, actual_count, err_reason = await self._train_adaptive(armyid, target_count)

        if success:
            msg = f"✅ تم بنجاح تدريب {actual_count:,} فخ من {f_icon} [{f_name}] (مستوى {tier}) في حصن الحرب! 🎉"
            self.log.info(msg)
            return TaskResult.ok(
                msg,
                status="success",
                data={
                    "armyid": armyid,
                    "family": family_key,
                    "level": tier,
                    "count": actual_count,
                    "wall_capacity": calc["wall_total_cap"],
                    "harvested_previous": harvested
                }
            )
        else:
            msg = f"⚠️ تعذر إتمام تدريب الفخاخ في حصن الحرب (السبب: {err_reason})"
            self.log.warning(msg)
            return TaskResult.fail(msg, error=err_reason)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="War Fortress Trap Training Task — مهمة تدريب فخاخ حصن الحرب التلقائية")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--type", "-t", default="auto", help="فئة الفخ المراد تدريبه (rocks / arrows / oil / auto)")
    parser.add_argument("--level", "-l", type=int, default=None, help="مستوى/رتبة الفخ (1..5) أو اتركه تلقائياً لأعلى رتبة مفتوحة")
    parser.add_argument("--count", "-c", default="max", help="عدد الفخاخ للتدريب (رقم محدد أو 'max')")
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

        # انتظار اكتمال حزم بيانات Gate الأساسية
        for _ in range(15):
            await asyncio.sleep(0.3)
            has_city = "cityCtrl" in conn.init_data
            has_queue = "queueCtrl" in conn.init_data
            has_army = "armyCtrl" in conn.init_data
            if has_city and has_queue and has_army:
                break
        await asyncio.sleep(0.4)

        cfg = {
            "type": args.type,
            "level": args.level,
            "count": args.count
        }
        task = FortressTask(conn, cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
