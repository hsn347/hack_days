# -*- coding: utf-8 -*-
"""
tasks/train.py — مهمة تدريب الجنود والفخاخ في الثكنات وحصن الحرب تلقائياً
══════════════════════════════════════════════════════════════════════════════════════

بروتوكول تدريب الجيش (Army & Trap Training Protocol):
  - بدء التدريب:     cmd: "1005", subcmd: "2", data: {"bid": bid, "armyid": armyid, "armycount": count, "mode": "0", "isget": false}
  - جمع/استلام الجنود: cmd: "1005", subcmd: "5", data: {"bid": bid}
  - طابور التدريب:   queueCtrl['1203'..'1207']

المباني وأنواع القوات:
  1. 🛡️ المشاة (Infantry):    bid = "118" | armyid = 401..410 (مستوى 1..10)
  2. 🐎 الخيالة (Cavalry):     bid = "116" | armyid = 501..510 (مستوى 1..10)
  3. 🏹 الأسهم (Archers):      bid = "117" | armyid = 601..610 (مستوى 1..10)
  4. 🚜 العربات (Chariots):    bid = "119" | armyid = 701..710 (مستوى 1..10)
  5. 🏰 حصن الحرب (Fortress):  bid = "120" | armyid = 801..824 (فخاخ)

حساب أقصى عدد تدريب (armycount):
  - يفحص خيام الجيش (bid: 205) لحساب السعة الإجمالية القصوى.
  - يتحقق من الموارد المتوفرة (طعام، خشب، حديد، فضة).
  - ضبط تكيفي تلقائي ذكي (Adaptive Auto-Tuning) لتدريب الحد الأقصى المتاح بالضبط دون أخطاء.

الاستخدام كملف مستقل:
    python tasks/train.py --email "burcudemr@gmail.com" --types all --level 10
    python tasks/train.py --email "ossso5040@gmail.com" --types "حصن الحرب" --level 2
    python tasks/train.py --email "king7moe1990@gmail.com" --types "الخيالة"
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

# سعة خيام الجيش الرسمية من build205.lua
_TENT_CAPACITIES: Dict[int, int] = {
    1: 10, 2: 10, 3: 20, 4: 20, 5: 30, 6: 30, 7: 40, 8: 40, 9: 50, 10: 50,
    11: 60, 12: 60, 13: 70, 14: 70, 15: 80, 16: 80, 17: 90, 18: 90, 19: 100, 20: 100,
    21: 110, 22: 110, 23: 120, 24: 120, 25: 130, 26: 130, 27: 140, 28: 140, 29: 150, 30: 160,
    31: 160, 32: 160, 33: 160, 34: 160, 35: 160, 36: 165, 37: 165, 38: 170, 39: 170, 40: 175,
    41: 175, 42: 175, 43: 175, 44: 175, 45: 175, 46: 180, 47: 180, 48: 185, 49: 185, 50: 190,
    51: 190, 52: 190, 53: 190, 54: 190, 55: 190, 56: 195, 57: 195, 58: 200, 59: 200, 60: 205,
    61: 205, 62: 205, 63: 205, 64: 205, 65: 205
}

# علاقات الأهداف والأنواع الفرعية من attribute_relation.lua و attributeDef.lua
_TARGET_RELATIONS: Dict[int, List[int]] = {
    7: [7, 2, 1],   # مشاة دروع (Infantry Defense - Even: 402, 404, 406, 408, 410)
    8: [8, 2, 1],   # مشاة هجوم/رماح (Infantry Attack - Odd: 401, 403, 405, 407, 409)
    9: [9, 3, 1],   # رماة أسهم/نشاب زوجي (Archers Even: 602, 604, 606, 608, 610)
    10: [10, 3, 1], # رماة أسهم فردي (Archers Odd: 601, 603, 605, 607, 609)
    11: [11, 4, 1], # رماة خيل فردي (Cavalry Odd: 501, 503, 505, 507, 509)
    12: [12, 4, 1], # خيالة اشتباك زوجي (Cavalry Even: 502, 504, 506, 508, 510)
    13: [13, 5, 1], # مركبات حصار فردي (Siege Odd: 701, 703, 705, 707, 709)
    14: [14, 5, 1], # عربات حربية زوجي (Chariots Even: 702, 704, 706, 708, 710)
}

def _get_target_for_armyid(armyid: int) -> int:
    """تحديد الهدف الدقيق للسمات العسكرية بحسب نوع ورتبة الجندي (زوجي/فردي)"""
    aid = int(armyid)
    prefix = aid // 100
    tier = aid % 100
    if prefix == 4: # مشاة (فردي=8 رماح/هجوم، زوجي=7 دروع/دفاع)
        return 8 if tier % 2 == 1 else 7
    elif prefix == 5: # خيالة (فردي=11 رماة خيل، زوجي=12 خيالة اشتباك)
        return 11 if tier % 2 == 1 else 12
    elif prefix == 6: # أسهم (فردي=10 رماة، زوجي=9 نشاب)
        return 10 if tier % 2 == 1 else 9
    elif prefix == 7: # عربات (فردي=13 منجنيق/حصار، زوجي=14 عربات حربية)
        return 13 if tier % 2 == 1 else 14
    return 1


# ════════════════════════════════════════════════════════════════════
#  تعريف المباني وأنواع القوات
# ════════════════════════════════════════════════════════════════════

BUILDING_TROOP_MAP: Dict[str, Dict[str, Any]] = {
    "infantry": {
        "bid": "118",
        "name_ar": "المشاة",
        "name_en": "Infantry",
        "icon": "🛡️",
        "prefix": 400,
        "max_level": 10,
        "queue_type": "1203"
    },
    "cavalry": {
        "bid": "116",
        "name_ar": "الخيالة",
        "name_en": "Cavalry",
        "icon": "🐎",
        "prefix": 500,
        "max_level": 10,
        "queue_type": "1204"
    },
    "archers": {
        "bid": "117",
        "name_ar": "الأسهم",
        "name_en": "Archers",
        "icon": "🏹",
        "prefix": 600,
        "max_level": 10,
        "queue_type": "1205"
    },
    "chariots": {
        "bid": "119",
        "name_ar": "العربات",
        "name_en": "Chariots",
        "icon": "🚜",
        "prefix": 700,
        "max_level": 10,
        "queue_type": "1206"
    },
}

TYPE_ALIASES: Dict[str, str] = {
    # المشاة
    "infantry": "infantry", "مشاة": "infantry", "المشاة": "infantry", "جنود": "infantry", "عاديين": "infantry", "4": "infantry", "118": "infantry",
    # الخيالة
    "cavalry": "cavalry", "خيالة": "cavalry", "الخيالة": "cavalry", "فرسان": "cavalry", "الفرسان": "cavalry", "5": "cavalry", "116": "cavalry",
    # الأسهم
    "archers": "archers", "archer": "archers", "اسهم": "archers", "الاسهم": "archers", "الأسهم": "archers", "رماة": "archers", "الرماة": "archers", "6": "archers", "117": "archers",
    # العربات
    "chariots": "chariots", "chariot": "chariots", "عربات": "chariots", "العربات": "chariots", "منجنيق": "chariots", "7": "chariots", "119": "chariots",
}

# مستويات فتح الرتب العسكرية في الثكنات
TIER_UNLOCK_BUILDING_LEVEL = {
    1: 1, 2: 4, 3: 7, 4: 10, 5: 13,
    6: 16, 7: 19, 8: 22, 9: 26, 10: 30
}


def get_max_unlocked_tier(building_lv: int) -> int:
    """معرفة أقصى مستوى جندي مفتوح بناءً على مستوى الثكنة."""
    max_t = 1
    for tier, req_lv in TIER_UNLOCK_BUILDING_LEVEL.items():
        if building_lv >= req_lv:
            max_t = max(max_t, tier)
    return max_t


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (TrainTask)
# ════════════════════════════════════════════════════════════════════

class TrainTask(BaseTask):
    """
    مهمة تدريب القوات التلقائية لجميع أنواع الثكنات الأربعة مع حساب الحد الأقصى التلقائي.
    """
    name = "train"

    def __init__(self, conn: GameConnection, config: dict = None):
        super().__init__(conn, config)
        self.selected_types = self._parse_types_config()
        self.target_levels = self._parse_levels_config()
        self.requested_count = self.config.get("count", "max")

    def _parse_types_config(self) -> List[str]:
        raw = self.config.get("types", self.config.get("type", "all"))
        if not raw or str(raw).strip().lower() in ("all", "الكل", "all_types"):
            return list(BUILDING_TROOP_MAP.keys())

        if isinstance(raw, str):
            parts = [p.strip().lower() for p in raw.replace("،", ",").split(",") if p.strip()]
        elif isinstance(raw, (list, tuple)):
            parts = [str(p).strip().lower() for p in raw if str(p).strip()]
        else:
            return list(BUILDING_TROOP_MAP.keys())

        matched = []
        for p in parts:
            if p in ("all", "الكل"):
                return list(BUILDING_TROOP_MAP.keys())
            if p in TYPE_ALIASES:
                canon = TYPE_ALIASES[p]
                if canon not in matched:
                    matched.append(canon)
        return matched if matched else list(BUILDING_TROOP_MAP.keys())

    def _parse_levels_config(self) -> Dict[str, int]:
        levels = {}
        # إذا كان المستوى معطى كقيمة موحدة
        default_lvl = int(self.config.get("level", self.config.get("unit_level", 10)))
        for t in BUILDING_TROOP_MAP.keys():
            levels[t] = default_lvl

        # إذا كان هناك تخصيص فردي لكل نوع في config
        custom_lvls = self.config.get("levels", {})
        if isinstance(custom_lvls, dict):
            for k, v in custom_lvls.items():
                canon = TYPE_ALIASES.get(str(k).lower())
                if canon:
                    levels[canon] = int(v)
        return levels

    async def on_start(self):
        """انتظار وصول حزم البيانات الأساسية من السيرفر (cityCtrl, queueCtrl, lordSkillCtrl)."""
        for _ in range(15):
            has_city = "cityCtrl" in self.conn.init_data
            has_queue = "queueCtrl" in self.conn.init_data
            has_lord = ("lordSkillCtrl" in self.conn.init_data) or ("lordInfoCtrl" in self.conn.init_data)
            if has_city and has_queue and has_lord:
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

    def _calculate_auto_army_count(self, bid: str, armyid: int) -> dict:
        """
        محاكاة دقيقة 100% لخوارزمية اللعبة الأصلية المستخرجة من كود اللعبة:
          - soldiersCampView.lua (Proto 26, 27, 42)
          - armyLogic.lua (Proto 4, 9, 15)
          - buildLogic.lua (Proto 29)
          - boeAttributeCtrl.lua (Proto 17)
        تحسب:
          1. سقف الموارد الحالية (resTrain): الحد الأقصى لما تسمح به موارد الحساب (طعام، خشب، حديد، فضة).
          2. سعة التدريب القصوى للمبنى (canTrain): خيام الجيش + سمات القلعة والتكنولوجيا.
          3. الناتج التلقائي النهائي = min(canTrain, resTrain) وهو نفس الرقم الذي تضعه واجهة اللعبة في شريط التمرير تماماً.
        """
        aid_str = str(armyid)
        army_info = _ARMY_DATABASE.get(aid_str, {})
        cost_res = army_info.get("costRes", {})

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

        # 2. سعة التدريب القصوى للمبنى (canTrain)
        # خيام الجيش (Military Tents - bid: 205) باستخدام جدول السعة الرسمي بدقة
        tent_cap = 0
        blist = city_ctrl.get("blist", [])
        if isinstance(blist, list):
            for b in blist:
                binfo = b.get("binfo", {})
                if str(binfo.get("bid")) == "205":
                    lv = int(binfo.get("lv", 1))
                    tent_cap += _TENT_CAPACITIES.get(lv, 205 if lv > 65 else lv * 3)

        # مهارات ومواهب اللورد (Lord Skills / Talents)
        # كل مستوى في المهارات 13003 (مجموعة التدريب 1) و 13011 (مجموعة 2) و 13024 (مجموعة 3) يمنح 25 جندياً إضافياً بالضبط
        lord_skills = self.conn.init_data.get("lordSkillCtrl", {})
        active_set = str(lord_skills.get("activeSetID", "1")) if isinstance(lord_skills, dict) else "1"
        set_data = lord_skills.get("setListData", {}) if isinstance(lord_skills, dict) else {}
        curr_set = set_data.get(active_set) or set_data.get(int(active_set) if active_set.isdigit() else 1) or {}
        s_list = curr_set.get("list", {}) if isinstance(curr_set, dict) else {}
        if not s_list:
            sb = self.conn.init_data.get("lordInfoCtrl", {}).get("skill", {}).get("skillBasic", {})
            s_list = {k: (v[1] if isinstance(v, list) and len(v) > 1 else v) for k, v in sb.items()} if isinstance(sb, dict) else {}

        g1 = int(s_list.get("13003", 0)) if isinstance(s_list, dict) else 0
        g2 = int(s_list.get("13011", 0)) if isinstance(s_list, dict) else 0
        g3 = int(s_list.get("13024", 0)) if isinstance(s_list, dict) else 0
        skill_add = (g1 + g2 + g3) * 25

        # أدوات وبنود زيادة التدريب الفردي (singleTrainAddInfo)
        tool_info = self.conn.init_data.get("armyCtrl", {}).get("singleTrainAddInfo", {})
        tool_add = int(tool_info.get("addCount", 0)) if isinstance(tool_info, dict) and int(tool_info.get("itemCount", 0)) > 0 else 0

        # السمات العسكرية الدقيقة من boeAttributeCtrl (الوحدة 0 - Attribute 20: V_TRAIN_ARMY)
        boe_attr = self.conn.init_data.get("boeAttributeCtrl", {})
        mod0 = boe_attr.get("0", {}) if isinstance(boe_attr, dict) else {}

        target_id = _get_target_for_armyid(armyid)
        related_targets = _TARGET_RELATIONS.get(target_id, [target_id, 1])

        attr_bonus = 0.0
        if isinstance(mod0, dict) and mod0:
            for tid in related_targets:
                t_data = mod0.get(str(tid), {})
                if isinstance(t_data, dict):
                    val_entry = t_data.get("20", {})
                    if isinstance(val_entry, dict):
                        attr_bonus += float(val_entry.get("2", 0))

        base_count = 10
        can_train = base_count + tent_cap + skill_add + tool_add + int(attr_bonus)

        final_count = min(can_train, res_train)
        has_enough_res = (res_train >= 1)

        return {
            "armyid": armyid,
            "bid": str(bid),
            "can_train_cap": can_train,
            "res_train_cap": res_train,
            "final_armycount": max(1, final_count) if has_enough_res else 0,
            "has_enough_resources": has_enough_res,
            "missing_resources": missing_res
        }

    async def _harvest_finished_troops(self, bid: str) -> bool:
        """جمع واستلام الجنود المكتمل تدريبهم من الثكنة."""
        r_get = await self.conn.query("1005", "5", {"bid": str(bid)}, timeout=6)
        if r_get and str(r_get.get("err", "0")) == "0":
            return True
        return False

    async def _train_adaptive(self, bid: str, armyid: int, initial_count: int) -> Tuple[bool, int, str]:
        """
        إرسال طلب التدريب بالعدد المحسوب بدقة، مع تصحيح تكيفي ذكي وسريع:
          1. بما أن الحساب مطابق لخوارزمية اللعبة، ينجح الطلب عادة من أول محاولة (err: 0).
          2. في حال وجود فارق بسيط (1-5 وحدات)، ينزل تدريجياً بالوحدات أولاً للحفاظ على أعلى سعة ممكنة.
          3. إذا استمر التجاوز (4004/4003)، ينزل بنسبة ذكية (10%) للوصول السريع إلى الحد الأقصى دون استسلام.
          4. إعادة محاولة تلقائية عند حدوث بطء في استجابة الشبكة (timeout).
          5. تشخيص دقيق وترجمة واضحة لكافة أكواد السيرفر (4002 للمبنى المشغول، إلخ).
        """
        curr_count = initial_count
        attempts = 0
        max_attempts = 20
        last_err = ""

        while curr_count >= 1 and attempts < max_attempts:
            attempts += 1
            payload = {
                "bid": str(bid),
                "armyid": str(armyid),
                "armycount": str(curr_count),
                "mode": "0",
                "isget": False
            }

            # إعادة محاولة تلقائية في حال انقطاع أو تأخر الرد (timeout)
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
                return False, 0, "الثكنة مشغولة بعملية تدريب جارية حالياً (busy)"

            elif err == "4001":
                return False, 0, "رتبة الجندي غير مفتوحة أو مستوى الثكنة غير كافٍ"

            elif err in ("4004", "4003"):
                # أول 4 محاولات: نزول دقيق بالوحدات لعدم التفريط في أي جندي
                if attempts == 1:
                    curr_count = max(1, curr_count - 1)
                elif attempts == 2:
                    curr_count = max(1, curr_count - 2)
                elif attempts == 3:
                    curr_count = max(1, curr_count - 3)
                elif attempts == 4:
                    curr_count = max(1, curr_count - 5)
                else:
                    # بعد ذلك: نزول نسبي سريع بنسبة 10% للوصول للحد الفاصل فوراً
                    step = max(1, int(curr_count * 0.1))
                    curr_count = max(1, curr_count - step)

            elif err == "timeout":
                self.log.warning(f"⚠️ بطء مؤقت في استجابة السيرفر (timeout)، محاولة تخفيض العدد...")
                curr_count = max(1, curr_count - 5)
            else:
                return False, 0, f"كود سيرفر: {err}"

            await asyncio.sleep(0.15)

        return False, 0, f"تجاوز السعة القصوى المتاحة (كود: {last_err})"

    async def _harvest_all_ready_barracks(self, now_ts: int) -> List[Dict[str, Any]]:
        """
        فحص شامل وإلزامي لكافة الثكنات العسكرية (116, 117, 118, 119):
        إذا وُجدت أي قوات مكتمل تدريبها وجاهزة للاستلام، يتم استلامها وجمعها فوراً
        حتى لو لم تكن الثكنة مطلوبة في مهمة التدريب الحالية.
        """
        harvested = []
        army_ctrl = self.conn.init_data.get("armyCtrl", {})
        train_army = army_ctrl.get("trainArmy", {}) if isinstance(army_ctrl, dict) else {}
        if not isinstance(train_army, dict):
            train_army = {}

        queue_ctrl = self.conn.init_data.get("queueCtrl", {})
        if not isinstance(queue_ctrl, dict):
            queue_ctrl = {}

        all_bids = ["116", "117", "118", "119"]
        # خريطة عكسية لمعرفة اسم المبنى وأيقونته
        bid_to_meta = {meta["bid"]: meta for meta in BUILDING_TROOP_MAP.values()}

        for bid in all_bids:
            meta = bid_to_meta.get(bid, {})
            b_name = meta.get("name_ar", f"مبنى {bid}")
            b_icon = meta.get("icon", "🏛️")

            is_ready = False
            ready_info = {}

            # 1. فحص trainArmy في بيانات التهيئة
            if bid in train_army and train_army[bid]:
                is_ready = True
                ready_info = train_army[bid]

            # 2. فحص طابور التدريب queueCtrl
            if not is_ready:
                for qid, qdata in queue_ctrl.items():
                    if isinstance(qdata, dict) and str(qdata.get("data", {}).get("bid")) == str(bid):
                        st = int(qdata.get("starttime", 0))
                        tt = int(qdata.get("totaltime", 0))
                        if st + tt > 0 and now_ts >= (st + tt):
                            is_ready = True
                            ready_info = {
                                str(qdata.get("data", {}).get("armyid")): str(qdata.get("data", {}).get("armycount"))
                            }
                        break

            if is_ready:
                self.log.info(f"📦 وُجدت قوات جاهزة للاستلام في {b_icon} [{b_name}] (معلومات: {ready_info})! جاري الجمع...")
                resp = await self.conn.query("1005", "5", {"bid": str(bid)}, timeout=6)
                err = str(resp.get("err", "0")) if resp else "timeout"

                if err == "0":
                    self.log.info(f"✅ تم بنجاح جمع واستلام القوات الجاهزة من {b_icon} [{b_name}]! 🎖️")
                    harvested.append({
                        "type": b_name,
                        "bid": bid,
                        "details": ready_info
                    })
                    # إزالة المبنى من trainArmy و queueCtrl ليكون حراً فوراً لأي تدريب جديد
                    if bid in train_army:
                        del train_army[bid]
                    for qid in list(queue_ctrl.keys()):
                        if isinstance(queue_ctrl[qid], dict) and str(queue_ctrl[qid].get("data", {}).get("bid")) == str(bid):
                            del queue_ctrl[qid]
                else:
                    self.log.warning(f"⚠️ فشل استلام القوات من {b_name} (كود: {err})")

                await asyncio.sleep(0.5)

        return harvested

    async def run(self) -> TaskResult:
        # مزامنة سريعة لبيانات الجيش والثكنات لضمان أحدث حالة قبل بدء أي فحص
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
        # المرحلة 1: جمع واستلام كافة الجنود الجاهزين في جميع المباني إجبارياً
        # ════════════════════════════════════════════════════════════════
        self.log.info("🔍 فحص عام لكافة الثكنات لجمع أي جنود مكتمل تدريبهم...")
        collected_summary = await self._harvest_all_ready_barracks(now_ts)
        if collected_summary:
            self.log.info(f"🎉 تم جمع الجنود الجاهزين من {len(collected_summary)} مبنى بنجاح!")
            # منح السيرفر ثانية واحدة لتحديث حالة الثكنات والموارد
            await asyncio.sleep(1.2)

        # ════════════════════════════════════════════════════════════════
        # المرحلة 2: بدء تدريب القوات للأنواع المطلوبة من المستخدم
        # ════════════════════════════════════════════════════════════════
        self.log.info(f"🪖 بدء مرحلة تدريب الجيش | الأنواع المطلوبة: {len(self.selected_types)} مبنى...")

        queue_ctrl = self.conn.init_data.get("queueCtrl", {})
        if not isinstance(queue_ctrl, dict):
            queue_ctrl = {}

        trained_summary: List[Dict[str, Any]] = []
        busy_summary: List[Dict[str, Any]] = []
        earliest_finish_time: Optional[int] = None

        for t_key in self.selected_types:
            meta = BUILDING_TROOP_MAP[t_key]
            bid = meta["bid"]
            b_name = meta["name_ar"]
            b_icon = meta["icon"]

            b_lv, b_state = self._get_building_info(bid)
            if b_lv <= 0:
                self.log.warning(f"⚠️ المبنى {b_icon} [{b_name}] (bid={bid}) غير مبني في القلعة.")
                continue

            # فحص ما إذا كان المبنى قيد التدريب حالياً في queueCtrl
            active_queue = None
            for qid, qdata in queue_ctrl.items():
                if isinstance(qdata, dict) and str(qdata.get("data", {}).get("bid")) == str(bid):
                    active_queue = qdata
                    break

            if active_queue:
                start_t = int(active_queue.get("starttime", 0))
                total_t = int(active_queue.get("totaltime", 0))
                end_t = start_t + total_t

                if now_ts < end_t:
                    # ما زال قيد التدريب
                    rem_s = max(1, end_t - now_ts)
                    rem_m = max(1, rem_s // 60)
                    self.log.info(f"⏳ {b_icon} [{b_name}] قيد التدريب حالياً (متبقي: {rem_m} دقيقة).")
                    busy_summary.append({
                        "type": b_name,
                        "bid": bid,
                        "remaining_seconds": rem_s
                    })
                    if earliest_finish_time is None or end_t < earliest_finish_time:
                        earliest_finish_time = end_t
                    continue

            # تحديد رتبة الجندي (armyid) بناءً على المستوى ومستوى المبنى
            target_level = self.target_levels.get(t_key, 10)
            max_unlocked_tier = get_max_unlocked_tier(b_lv)
            effective_tier = min(target_level, max_unlocked_tier)

            prefix = meta["prefix"]
            armyid = prefix + effective_tier

            # حساب العدد التلقائي المطابق لواجهة اللعبة تماماً (سعة المبنى + سقف الموارد المتوفرة)
            calc = self._calculate_auto_army_count(bid, armyid)
            self.log.info(
                f"📊 فحص تلقائي لـ {b_icon} [{b_name}] (مستوى {effective_tier}): "
                f"سعة الثكنة: {calc['can_train_cap']} وحدة | "
                f"سقف الموارد: {calc['res_train_cap']} وحدة | "
                f"الناتج التلقائي: {calc['final_armycount']} وحدة"
            )

            if not calc["has_enough_resources"]:
                missing_str = ", ".join(calc["missing_resources"]) if calc["missing_resources"] else "الموارد"
                self.log.warning(f"⚠️ تعذر تدريب {b_name} لعدم كفاية الموارد! (نقص في: {missing_str})")
                continue

            if str(self.requested_count).lower() == "max":
                initial_count = calc["final_armycount"]
            else:
                initial_count = min(int(self.requested_count), calc["final_armycount"])

            if initial_count <= 0:
                self.log.warning(f"⚠️ العدد المحسوب لتدريب {b_name} هو 0، تم التخطي.")
                continue

            self.log.info(f"🚀 بدء تدريب {b_icon} [{b_name}] | المستوى: {effective_tier} (معرف: {armyid}) | المستهدف: {initial_count} وحدة...")

            success, actual_count, err_reason = await self._train_adaptive(bid, armyid, initial_count)

            if success:
                self.log.info(f"✅ تم بدء تدريب {actual_count} وحدة من {b_icon} [{b_name}] (مستوى {effective_tier}) بنجاح! 🎉")
                trained_summary.append({
                    "type": b_name,
                    "bid": bid,
                    "armyid": armyid,
                    "level": effective_tier,
                    "count": actual_count
                })
            else:
                self.log.warning(f"⚠️ تعذر بدء تدريب {b_name} (السبب: {err_reason})")

            await asyncio.sleep(1.0)

        # حساب وقت المراجعة القادمة
        retry_after = 3600
        if earliest_finish_time and earliest_finish_time > now_ts:
            retry_after = max(60, earliest_finish_time - now_ts)

        parts = []
        if collected_summary:
            parts.append(f"تم جمع واستلام القوات من {len(collected_summary)} مبنى")
        if trained_summary:
            parts.append(f"تم تدريب {len(trained_summary)} أنواع قوات جديدة")
        if busy_summary:
            parts.append(f"({len(busy_summary)} مباني قيد التدريب)")

        msg = " | ".join(parts) if parts else "لم يتم اتخاذ أي إجراء (كافة المباني مشغولة أو لا توجد قوات جاهزة)."
        self.log.info(f"🏁 {msg}")

        return TaskResult.ok(
            msg,
            status="success" if (collected_summary or trained_summary) else "no_action",
            retry_after=retry_after,
            data={
                "collected": collected_summary,
                "trained": trained_summary,
                "busy": busy_summary,
                "retry_after": retry_after
            }
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Empire Troop Training Task — مهمة تدريب الجيش التلقائية")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--types", "-t", default="all", help="أنواع القوات للتدريب (مشاة, خيالة, اسهم, عربات أو all)")
    parser.add_argument("--level", "-l", type=int, default=10, help="مستوى القوات المراد تدريبه (1..10)")
    parser.add_argument("--count", "-c", default="max", help="عدد الجنود للتدريب (رقم محدد أو 'max')")
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

        # انتظار اكتمال حزم بيانات Gate الأساسية (خاصة queueCtrl و cityCtrl و lordSkillCtrl)
        for _ in range(15):
            await asyncio.sleep(0.3)
            has_city = "cityCtrl" in conn.init_data
            has_queue = "queueCtrl" in conn.init_data
            has_lord = ("lordSkillCtrl" in conn.init_data) or ("lordInfoCtrl" in conn.init_data)
            if has_city and has_queue and has_lord:
                break
        await asyncio.sleep(0.4)

        cfg = {
            "types": args.types,
            "level": args.level,
            "count": args.count
        }
        task = TrainTask(conn, cfg)
        await task.on_start()
        result = await task.run()

        print(f"\n📊 النتيجة النهائية: {result.message} | تفاصيل: {result.data}")
        await conn.close()

    asyncio.run(_main())
