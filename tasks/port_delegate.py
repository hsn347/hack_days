# -*- coding: utf-8 -*-
"""
tasks/port_delegate.py — مهمة الميناء العسكري: التعيين السريع + متجر الجزيرة الغامضة
═════════════════════════════════════════════════════════════════════════════════════

القسم الأول (Part 1) — مهام التعيين في الميناء العسكري (CMD 2064):
  - إرسال / تعيين مهمة مع الأبطال:
    cmd: "2064", subcmd: "10", data: {"taskId": taskId, "heros": [hero1, hero2]}
  - استلام مكافأة مهمة مكتملة:
    cmd: "2064", subcmd: "11", data: {"taskId": taskId}
  - استلام الجائزة الآلية لمكافأة الوقت:
    cmd: "2064", subcmd: "9", data: {}
  - ميزات:
    1. 🔍 استعلام ذكي وتلقائي عن حالة مهام التعيين الـ 10 ومستويات الفتح.
    2. ⚡ الإرسال السريع والتعيين الذكي للأبطال مع مطابقة شروط البونص والبدائل المتاحة.
    3. 🎁 استلام مكافآت المهام المكتملة والجائزة الآلية تلقائياً وتحرير الأبطال.

القسم الثاني (Part 2) — متجر الجزيرة الغامضة (CMD 5011):
  - شراء المنتجات المحددة وفق نقاط الحرب البحرية / الجزيرة المتوفرة:
    cmd: "5011", subcmd: "1", data: {"shopId": 1, "goodsId": goodsId, "goodsNum": num}
  - ميزات:
    1. 🛒 دعم شراء المنتجات الـ 7 كاملة بحسب الحدود اليومية ورصيد النقاط.
    2. 🛡️ نظام أمان ضد الحظر (Anti-Ban Jitter) بفواصل طبيعية بين الطلبات.

الاستخدام كملف مستقل:
    python tasks/port_delegate.py --email "king7moe1990@gmail.com" --check-only
    python tasks/port_delegate.py --email "king7moe1990@gmail.com" --buy-items 7
    python tasks/port_delegate.py --email "king7moe1990@gmail.com" --buy-all
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
import logging
import random
import time
import argparse
from typing import Any, Dict, List, Optional, Tuple, Set

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection
from core.session_manager import SessionManager


# ════════════════════════════════════════════════════════════════════
#  بيانات وقواعد مهام التعيين في الميناء العسكري (DELEGATE_TASK)
# ════════════════════════════════════════════════════════════════════

DELEGATE_TASKS_CONFIG: Dict[int, Dict[str, Any]] = {
    1001001: {
        "id": 1001001,
        "name": "استطلاع السواحل 1",
        "stars": 1,
        "duration": 300,
        "unlock_level": 4910309,
        "cond1": (0, 1, 0, 0, 5),  # (heroId, type, star, quality, lv)
        "cond2": (0, 1, 0, 0, 5),
    },
    1001002: {
        "id": 1001002,
        "name": "استطلاع السواحل 2",
        "stars": 1,
        "duration": 300,
        "unlock_level": 4910412,
        "cond1": (0, 0, 0, 5, 0),
        "cond2": (0, 0, 0, 4, 0),
    },
    1002001: {
        "id": 1002001,
        "name": "دورية بحرية 1",
        "stars": 2,
        "duration": 300,
        "unlock_level": 4910612,
        "cond1": (0, 2, 0, 5, 0),
        "cond2": (0, 0, 2, 4, 0),
    },
    1002002: {
        "id": 1002002,
        "name": "دورية بحرية 2",
        "stars": 2,
        "duration": 300,
        "unlock_level": 4910712,
        "cond1": (0, 0, 2, 5, 0),
        "cond2": (0, 0, 2, 4, 0),
    },
    1003001: {
        "id": 1003001,
        "name": "حراسة الممر المائي 1",
        "stars": 3,
        "duration": 300,
        "unlock_level": 4910812,
        "cond1": (0, 0, 2, 5, 0),
        "cond2": (0, 0, 2, 4, 0),
    },
    1003002: {
        "id": 1003002,
        "name": "حراسة الممر المائي 2",
        "stars": 3,
        "duration": 300,
        "unlock_level": 4911012,
        "cond1": (0, 0, 3, 5, 0),
        "cond2": (0, 0, 3, 4, 0),
    },
    1004001: {
        "id": 1004001,
        "name": "مهمة إغارة عسكرية 1",
        "stars": 4,
        "duration": 300,
        "unlock_level": 4911112,
        "cond1": (0, 3, 0, 5, 0),
        "cond2": (0, 0, 3, 4, 0),
    },
    1004002: {
        "id": 1004002,
        "name": "مهمة إغارة عسكرية 2",
        "stars": 4,
        "duration": 300,
        "unlock_level": 4911212,
        "cond1": (0, 2, 0, 5, 0),
        "cond2": (0, 2, 0, 4, 0),
    },
    1005001: {
        "id": 1005001,
        "name": "عملية أسطول حربي 1",
        "stars": 5,
        "duration": 300,
        "unlock_level": 4911412,
        "cond1": (0, 3, 4, 5, 0),
        "cond2": (0, 3, 0, 4, 0),
    },
    1005002: {
        "id": 1005002,
        "name": "عملية أسطول حربي 2",
        "stars": 5,
        "duration": 300,
        "unlock_level": 4911512,
        "cond1": (0, 1, 5, 5, 0),
        "cond2": (0, 2, 5, 5, 0),
    }
}

# خريطة جودة ونوع الأبطال مستخرجة من heroinfodes.lua
HERO_META: Dict[int, Tuple[int, int]] = {
    5501001: (5, 1), 5501002: (5, 1), 5501003: (5, 1), 5501004: (5, 1), 5501005: (5, 1),
    5501006: (4, 1), 5501007: (4, 1), 5501008: (4, 1), 5501009: (4, 1), 5501010: (3, 1),
    5501011: (3, 1), 5501012: (3, 1), 5501013: (3, 1), 5501014: (3, 1), 5501015: (5, 1),
    5502001: (5, 2), 5502002: (5, 2), 5502003: (5, 2), 5502004: (5, 2), 5502005: (5, 2),
    5502006: (4, 2), 5502007: (4, 2), 5502008: (4, 2), 5502009: (4, 2), 5502010: (3, 2),
    5502011: (3, 2), 5502012: (3, 2), 5502013: (3, 2), 5502014: (3, 2), 5502015: (5, 2),
    5503001: (5, 3), 5503002: (5, 3), 5503003: (5, 3), 5503004: (5, 3), 5503005: (5, 3),
    5503006: (4, 3), 5503007: (4, 3), 5503008: (4, 3), 5503009: (4, 3), 5503010: (3, 3),
    5503011: (3, 3), 5503012: (3, 3), 5503013: (3, 3), 5503014: (3, 3), 5503015: (5, 3),
    5504001: (5, 4), 5504002: (5, 4), 5504003: (5, 4), 5504004: (5, 4), 5504005: (5, 4),
    5504006: (4, 4), 5504007: (4, 4), 5504008: (4, 4), 5504009: (4, 4), 5504010: (3, 4),
    5504011: (3, 4), 5504012: (3, 4), 5504013: (3, 4), 5504014: (3, 4), 5504015: (5, 4),
    5505001: (5, 5), 5505002: (5, 5), 5505003: (5, 5), 5505004: (5, 5), 5505005: (5, 5),
    5505006: (4, 5), 5505007: (4, 5), 5505008: (4, 5), 5505009: (4, 5), 5505010: (3, 5),
    5505011: (3, 5), 5505012: (3, 5), 5505013: (3, 5), 5505014: (3, 5), 5505015: (5, 5),
}


# ════════════════════════════════════════════════════════════════════
#  بيانات وقواعد متجر الجزيرة الغامضة (MYSTERIOUS ISLAND STORE)
# ════════════════════════════════════════════════════════════════════

ISLAND_SHOP_CATALOG: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "name": "منتج الروح المعنوية",
        "item_id": 913004,
        "price": 6000,
        "limit": 2,
        "aliases": ["1", "morale", "spirit", "معنوية", "روح"]
    },
    2: {
        "id": 2,
        "name": "منتج الروح المعنوية الفارس قيصر",
        "item_id": 910007,
        "price": 6000,
        "limit": 2,
        "aliases": ["2", "caesar", "قيصر"]
    },
    3: {
        "id": 3,
        "name": "منتج بطاقة تجنيد عادية",
        "item_id": 812001,
        "price": 1200,
        "limit": 5,
        "aliases": ["3", "recruit", "card", "تجنيد", "بطاقة"]
    },
    4: {
        "id": 4,
        "name": "منتج صندوق الموارد اختياري",
        "item_id": 809601,
        "price": 1850,
        "limit": 5,
        "aliases": ["4", "chest", "box", "resource", "صندوق", "موارد"]
    },
    5: {
        "id": 5,
        "name": "منتج كتاب خبرة متوسط",
        "item_id": 812012,
        "price": 90,
        "limit": 5,
        "aliases": ["5", "exp", "book", "خبرة", "كتاب"]
    },
    6: {
        "id": 6,
        "name": "منتج حجر التقنية العام",
        "item_id": 811042,
        "price": 2000,
        "limit": 30,
        "aliases": ["6", "tech", "tech_stone", "تقنية", "حجر_تقنية"]
    },
    7: {
        "id": 7,
        "name": "منتج حجر التقوية",
        "item_id": 210001,
        "price": 200,
        "limit": 300,
        "aliases": ["7", "enhance", "enhance_stone", "تقوية", "حجر_تقوية"]
    }
}


def resolve_island_goods_id(query: Any) -> Optional[int]:
    """
    تحويل اسم المنتج أو رقمه أو الاسم المستعار إلى معرف المنتج الصحيح (goodsId).
    """
    if query is None:
        return None
    q_str = str(query).strip().lower()
    if q_str.isdigit():
        val = int(q_str)
        if val in ISLAND_SHOP_CATALOG:
            return val
    for gid, meta in ISLAND_SHOP_CATALOG.items():
        if q_str in meta["aliases"] or q_str == meta["name"].lower():
            return gid
    return None


class PortDelegateTask(BaseTask):
    """
    مهمة الميناء العسكري: التعيين السريع للأبطال (CMD 2064) + متجر الجزيرة الغامضة (CMD 5011).
    """
    name = "port_delegate"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.check_only: bool = self.config.get("check_only", False)
        self.auto_claim: bool = self.config.get("auto_claim", True)
        self.claim_time_reward: bool = bool(self.config.get("claim_time_reward", True))
        self.target_task_ids: Optional[List[int]] = self.config.get("task_ids")
        self.buy_items: Optional[Any] = self.config.get("buy_items")
        self.buy_all: bool = bool(self.config.get("buy_all", False))
        self.skip_delegate: bool = bool(self.config.get("skip_delegate", False))
        self.skip_shop: bool = bool(self.config.get("skip_shop", False))

    # ──────────────────────────────────────────────────────────────────
    #  استخراج بيانات الأبطال المتاحين في القلعة
    # ──────────────────────────────────────────────────────────────────

    def _get_castle_heroes(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة أبطال القلعة مع مستوياتهم ونجومهم وأنواعهم.
        """
        heroes_raw = self.conn.init_data.get("heroCtrl", [])
        result = []
        for h in heroes_raw:
            hid = int(h.get("id", 0))
            if hid <= 0:
                continue

            star = int(h.get("star", 1))
            lv = int(h.get("lv", 1))

            # جلب الجودة والنوع
            meta = HERO_META.get(hid)
            if meta:
                quality, htype = meta
            else:
                # محاولة استنتاج النوع من المعرف
                htype = (hid // 1000) % 10
                quality = 5

            result.append({
                "id": hid,
                "star": star,
                "lv": lv,
                "quality": quality,
                "type": htype
            })

        # ترتيب الأبطال تنازلياً حسب الجودة والنجوم والمستوى
        result.sort(key=lambda x: (x["quality"], x["star"], x["lv"]), reverse=True)
        return result

    # ──────────────────────────────────────────────────────────────────
    #  الاستعلام الذكي عن حالة مهام التعيين
    # ──────────────────────────────────────────────────────────────────

    def get_tasks_status(self) -> Dict[str, Any]:
        """
        فحص حالة جميع المهام الـ 10 من واقع بيانات السيرفر الحالية.
        """
        pve = self.conn.init_data.get("PveBattleCtrl", {})
        cur_level_id = int(pve.get("nCurLevelId", 0))
        server_tasks = pve.get("tasks", {})
        now = time.time()

        tasks_list = []
        busy_hero_ids: Set[int] = set()

        for tid, meta in DELEGATE_TASKS_CONFIG.items():
            unlock_req = meta["unlock_level"]
            is_unlocked = (cur_level_id >= unlock_req)

            s_info = server_tasks.get(str(tid)) or server_tasks.get(tid)
            status_code = "locked"
            status_desc = "🔒 مقفلة (تحتاج تقدم في الفصل)"
            left_seconds = 0
            assigned_heroes = []

            if s_info:
                state = int(s_info.get("state", 0))
                start_time = float(s_info.get("startTime", 0))
                end_time = float(s_info.get("endTime", start_time + meta["duration"]))
                assigned_heroes = [int(h) for h in s_info.get("heros", [])]

                if state == 1:  # process
                    passed = now - start_time
                    left_seconds = max(0, int(meta["duration"] - passed))
                    if left_seconds > 0:
                        status_code = "running"
                        m = left_seconds // 60
                        s = left_seconds % 60
                        status_desc = f"⏳ جارية التعيين (متبقي: {m:02d}:{s:02d})"
                        for h in assigned_heroes:
                            busy_hero_ids.add(h)
                    else:
                        status_code = "claimable"
                        status_desc = "🎁 مكتملة وجاهزة للاستلام!"
                        # الأبطال سيعودون فور الاستلام
                        for h in assigned_heroes:
                            busy_hero_ids.add(h)
                elif state == 2:  # reward claimed
                    status_code = "claimed"
                    status_desc = "✅ مكتملة ومستلمة اليوم"
            elif is_unlocked:
                status_code = "ready"
                status_desc = "🟢 جاهزة للتعيين والإرسال"

            tasks_list.append({
                "id": tid,
                "name": meta["name"],
                "stars": meta["stars"],
                "unlock_level": unlock_req,
                "is_unlocked": is_unlocked,
                "status_code": status_code,
                "status_desc": status_desc,
                "left_seconds": left_seconds,
                "assigned_heroes": assigned_heroes,
                "cond1": meta["cond1"],
                "cond2": meta["cond2"]
            })

        time_rwd = pve.get("timeReward", {})
        time_reward_seconds = 0
        if isinstance(time_rwd, dict):
            b_time = float(time_rwd.get("beginTime", 0))
            if b_time > 0:
                time_reward_seconds = max(0, int(now - b_time))

        return {
            "cur_level_id": cur_level_id,
            "tasks": tasks_list,
            "busy_heroes": busy_hero_ids,
            "time_reward_seconds": time_reward_seconds,
            "time_reward_raw": time_rwd
        }

    # ──────────────────────────────────────────────────────────────────
    #  خوارزمية الإرسال السريع للأبطال (Auto Delegate)
    # ──────────────────────────────────────────────────────────────────

    def auto_select_heroes(
        self,
        task_info: Dict[str, Any],
        available_heroes: List[Dict[str, Any]],
        excluded_hero_ids: Set[int]
    ) -> Optional[Tuple[int, int, bool]]:
        """
        اختيار بطلين لمهمة التعيين:
        1. البحث عن أبطال يحققون الشروط (للحصول على الجائزة الإضافية).
        2. إذا تعذر، اختيار أي أبطال متاحين من القلعة.
        يرجع (hero1_id, hero2_id, is_extra_fit) أو None إذا لم يتوفر بطلين.
        """
        # تصفية الأبطال غير المشغولين
        candidates = [h for h in available_heroes if h["id"] not in excluded_hero_ids]
        if len(candidates) < 2:
            return None

        cond1 = task_info["cond1"]
        cond2 = task_info["cond2"]

        def check_cond(h: Dict[str, Any], cond: Tuple[int, int, int, int, int]) -> bool:
            need_id, need_type, need_star, need_qual, need_lv = cond
            if need_id != 0 and h["id"] != need_id:
                return False
            if need_type != 0 and h["type"] != need_type:
                return False
            if need_star != 0 and h["star"] < need_star:
                return False
            if need_qual != 0 and h["quality"] < need_qual:
                return False
            if need_lv != 0 and h["lv"] < need_lv:
                return False
            return True

        # البحث عن بطل مطابق للشرط 1
        hero1 = None
        for h in candidates:
            if check_cond(h, cond1):
                hero1 = h
                break

        # إذا لم يتطابق أي بطل مع الشرط 1، نأخذ أول بطل متاح
        if not hero1:
            hero1 = candidates[0]

        # البحث عن بطل مطابق للشرط 2 (مختلف عن بطل 1)
        hero2 = None
        for h in candidates:
            if h["id"] != hero1["id"] and check_cond(h, cond2):
                hero2 = h
                break

        # إذا لم يتطابق أي بطل مع الشرط 2، نأخذ أي بطل آخر متاح
        if not hero2:
            for h in candidates:
                if h["id"] != hero1["id"]:
                    hero2 = h
                    break

        if not hero1 or not hero2:
            return None

        is_fit = check_cond(hero1, cond1) and check_cond(hero2, cond2)
        return hero1["id"], hero2["id"], is_fit

    # ──────────────────────────────────────────────────────────────────
    #  استلام مكافأة مهمة مكتملة (CMD 2064 / 11)
    # ──────────────────────────────────────────────────────────────────

    async def _claim_task_reward(self, task_id: int) -> Tuple[bool, str]:
        """
        إرسال طلب استلام مكافأة المهمة المكتملة.
        """
        try:
            rsp = await self.conn.query("2064", "11", {"taskId": task_id})
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر"

            err = str(rsp.get("err", ""))
            if err == "0":
                # تحديث حالة المهمة محلياً في tasks
                pve = self.conn.init_data.setdefault("PveBattleCtrl", {})
                tasks = pve.setdefault("tasks", {})
                if str(task_id) in tasks:
                    tasks[str(task_id)]["state"] = 2
                return True, "تم استلام المكافأة بنجاح"
            else:
                return False, f"فشل الاستلام (كود: {err})"
        except Exception as e:
            return False, f"استثناء أثناء استلام المكافأة: {e}"

    # ──────────────────────────────────────────────────────────────────
    #  إرسال تعيين مهمة جديدة (CMD 2064 / 10)
    # ──────────────────────────────────────────────────────────────────

    async def _dispatch_task(self, task_id: int, hero_ids: List[int]) -> Tuple[bool, str]:
        """
        إرسال حزمة تعيين المهمة وبدء تنفيذها بالأبطال المحددين.
        """
        payload = {
            "taskId": task_id,
            "heros": hero_ids
        }
        try:
            rsp = await self.conn.query("2064", "10", payload)
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر"

            err = str(rsp.get("err", ""))
            if err == "0":
                data = rsp.get("data", {})
                task_data = data.get("taskData", {})
                # تحديث بيانات السيرفر محلياً
                pve = self.conn.init_data.setdefault("PveBattleCtrl", {})
                tasks = pve.setdefault("tasks", {})
                tasks[str(task_id)] = task_data
                return True, "تم التعيين والإرسال بنجاح"
            elif err == "1002":
                return False, "بيانات المهمة غير صالحة"
            else:
                return False, f"فشل التعيين (كود: {err})"
        except Exception as e:
            return False, f"استثناء أثناء إرسال المهمة: {e}"

    # ──────────────────────────────────────────────────────────────────
    #  استلام الجائزة الآلية لمكافأة الوقت (CMD 2064 / 9)
    # ──────────────────────────────────────────────────────────────────

    async def _claim_time_reward(self) -> Tuple[bool, str, int]:
        """
        إرسال طلب استلام الجائزة الآلية لمكافأة الوقت في الميناء العسكري والحرب البحرية:
        cmd: "2064", subcmd: "9", data: {}
        يرجع (نجاح/فشل, الرسالة, فارق النقاط المكتسبة).
        """
        pve = self.conn.init_data.get("PveBattleCtrl", {})
        cur_level_id = int(pve.get("nCurLevelId", 0))
        time_rwd = pve.get("timeReward")

        # إذا لم يتم فتح الحرب البحرية / الميناء إطلاقاً
        if cur_level_id <= 0 and not time_rwd:
            return False, "الحرب البحرية غير مفتوحة في القلعة حالياً", 0

        old_points = self.get_island_points()
        try:
            rsp = await self.conn.query("2064", "9", {})
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر", 0

            err = str(rsp.get("err", ""))
            if err == "0":
                data = rsp.get("data", {})
                new_tr = data.get("timeReward")
                if new_tr and isinstance(new_tr, dict):
                    pve_local = self.conn.init_data.setdefault("PveBattleCtrl", {})
                    pve_local["timeReward"] = new_tr

                # انتظار قصير لالتقاط NOTIFY_PVE_BATTLE وتحديث النقاط إن وُجد
                await asyncio.sleep(0.3)
                new_points = self.get_island_points()
                pts_gained = max(0, new_points - old_points)

                msg = f"تم استلام الجائزة الآلية بنجاح (+{pts_gained:,} نقطة)" if pts_gained > 0 else "تم استلام الجائزة الآلية بنجاح"
                return True, msg, pts_gained
            elif err in ("1002", "1001"):
                return False, "لا توجد جائزة آلية جاهزة للاستلام حالياً", 0
            else:
                return False, f"فشل استلام الجائزة الآلية (كود: {err})", 0
        except Exception as e:
            return False, f"استثناء أثناء استلام الجائزة الآلية: {e}", 0

    # ──────────────────────────────────────────────────────────────────
    #  عرض تقرير الاستعلام في الطرفية
    # ──────────────────────────────────────────────────────────────────

    def _print_status_report(self, info: Dict[str, Any], castle_heroes: List[Dict[str, Any]]):
        tasks = info["tasks"]
        cur_level = info["cur_level_id"]
        busy_count = len(info["busy_heroes"])
        tr_secs = info.get("time_reward_seconds", 0)

        print("\n" + "═" * 78)
        print("  ⚓ تقرير مهام التعيين في الميناء العسكري (Military Port Delegate Tasks)")
        print("═" * 78)
        print(f"  🗺️ المرحلة الحالية في الحرب البحرية:  Level ID {cur_level}")
        print(f"  🦸 أبطال القلعة المتوفرون:             {len(castle_heroes)} بطل (المشغولون: {busy_count})")
        if tr_secs > 0:
            h = tr_secs // 3600
            m = (tr_secs % 3600) // 60
            print(f"  ⏳ الجائزة الآلية لمكافأة الوقت:      تتراكم منذ {h} س و {m} د")
        elif info.get("time_reward_raw"):
            print("  ⏳ الجائزة الآلية لمكافأة الوقت:      جاهزة / تم الاستلام حديثاً")
        print("─" * 78)
        print(f"  {'رقم المهمة':<12} {'الاسم':<22} {'النجوم':<8} {'الحالة':<30}")
        print("─" * 78)

        for t in tasks:
            stars_str = "⭐" * t["stars"]
            print(f"  {t['id']:<12} {t['name']:<22} {stars_str:<8} {t['status_desc']:<30}")

        print("═" * 78)

        # عرض حالة متجر الجزيرة الغامضة
        shop_status = self.get_island_shop_status()
        print("\n" + "═" * 78)
        print("  🛒 تقرير متجر الجزيرة الغامضة (Mysterious Island Store - CMD 5011)")
        print("═" * 78)
        print(f"  💰 رصيد النقاط المتاح حالياً:  {shop_status['points']:,} نقطة")
        print("─" * 78)
        print(f"  {'رقم':<5} {'اسم المنتج':<30} {'السعر':<10} {'الحد':<8} {'المتبقي':<10} {'المتاح شراؤه':<12}")
        print("─" * 78)

        for itm in shop_status["items"]:
            print(f"  {itm['id']:<5} {itm['name']:<30} {itm['price']:<10} {itm['limit']:<8} {itm['remaining']:<10} {itm['can_buy_count']:<12}")

        print("═" * 78 + "\n")

    # ──────────────────────────────────────────────────────────────────
    #  تنفيذ المهمة بالكامل (Main Execution Flow)
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    #  دوال متجر الجزيرة الغامضة (Island Store Methods)
    # ──────────────────────────────────────────────────────────────────

    def get_island_points(self) -> int:
        """
        قراءة رصيد نقاط الجزيرة الغامضة / الحرب البحرية من السيرفر.
        """
        pve = self.conn.init_data.get("PveBattleCtrl", {})
        return int(pve.get("points", 0))

    def get_island_shop_status(self) -> Dict[str, Any]:
        """
        استعلام حالة متجر الجزيرة الغامضة (الرصيد، ما تم شراؤه اليوم، والمتبقي).
        """
        points = self.get_island_points()
        field_shop = self.conn.init_data.get("fieldShopCtrl", {})
        shop1 = field_shop.get("1", {})
        buy_records = shop1.get("buyRecord", {}).get("1", {}).get("records", {})

        items_status = []
        for gid, meta in ISLAND_SHOP_CATALOG.items():
            bought = int(buy_records.get(str(gid), 0))
            limit = meta["limit"]
            remaining = max(0, limit - bought)
            price = meta["price"]
            affordable = points // price if price > 0 else remaining
            items_status.append({
                "id": gid,
                "name": meta["name"],
                "item_id": meta["item_id"],
                "price": price,
                "limit": limit,
                "bought": bought,
                "remaining": remaining,
                "affordable": affordable,
                "can_buy_count": min(remaining, affordable)
            })

        return {
            "points": points,
            "items": items_status
        }

    async def _buy_shop_goods(self, goods_id: int, num: int) -> Tuple[bool, str, int]:
        """
        إرسال طلب شراء منتج من متجر الجزيرة الغامضة (cmd: 5011, subcmd: 1).
        """
        payload = {
            "shopId": 1,
            "goodsId": goods_id,
            "goodsNum": num
        }
        try:
            rsp = await self.conn.query("5011", "1", payload)
            if not rsp:
                return False, "لم يتم استلام رد من السيرفر", 0

            err = str(rsp.get("err", ""))
            if err == "0":
                data = rsp.get("data", {})
                this_bought_num = int(data.get("goodsNum", num))
                total_bought_today = int(data.get("buyNum", 0))
                meta = ISLAND_SHOP_CATALOG[goods_id]
                total_cost = meta["price"] * this_bought_num

                # تحديث النقاط محلياً
                pve = self.conn.init_data.setdefault("PveBattleCtrl", {})
                cur_pts = int(pve.get("points", 0))
                pve["points"] = max(0, cur_pts - total_cost)

                # تحديث سجل المشتريات محلياً
                field_shop = self.conn.init_data.setdefault("fieldShopCtrl", {})
                shop1 = field_shop.setdefault("1", {})
                buy_rec = shop1.setdefault("buyRecord", {})
                rec1 = buy_rec.setdefault("1", {})
                records = rec1.setdefault("records", {})
                if total_bought_today > 0:
                    records[str(goods_id)] = total_bought_today
                else:
                    cur_bought = int(records.get(str(goods_id), 0))
                    records[str(goods_id)] = cur_bought + this_bought_num

                return True, f"تم الشراء بنجاح (+{this_bought_num})", this_bought_num
            elif err == "1002":
                return False, "الرصيد غير كافٍ أو تجاوزت الحد اليومي", 0
            else:
                return False, f"فشل الشراء (كود: {err})", 0
        except Exception as e:
            return False, f"استثناء أثناء الشراء: {e}", 0

    async def _execute_shop_purchases(self) -> Dict[str, Any]:
        """
        تنفيذ مشتريات متجر الجزيرة الغامضة المحددة من المستخدم حسب النقاط المتاحة.
        """
        status = self.get_island_shop_status()
        current_points = status["points"]
        items_map = {item["id"]: item for item in status["items"]}

        targets: List[Tuple[int, int]] = []

        if self.buy_all:
            for gid, item in items_map.items():
                if item["remaining"] > 0:
                    targets.append((gid, item["remaining"]))
        elif self.buy_items:
            if isinstance(self.buy_items, dict):
                for k, v in self.buy_items.items():
                    gid = resolve_island_goods_id(k)
                    if gid and gid in items_map:
                        targets.append((gid, int(v)))
            elif isinstance(self.buy_items, list):
                for item_spec in self.buy_items:
                    if isinstance(item_spec, str) and ":" in item_spec:
                        parts = item_spec.split(":")
                        gid = resolve_island_goods_id(parts[0])
                        qty = int(parts[1]) if parts[1].isdigit() else 9999
                    else:
                        gid = resolve_island_goods_id(item_spec)
                        qty = 9999
                    if gid and gid in items_map:
                        targets.append((gid, qty))
            elif isinstance(self.buy_items, str):
                for item_spec in self.buy_items.split(","):
                    item_spec = item_spec.strip()
                    if not item_spec:
                        continue
                    if ":" in item_spec:
                        parts = item_spec.split(":")
                        gid = resolve_island_goods_id(parts[0])
                        qty = int(parts[1]) if parts[1].isdigit() else 9999
                    else:
                        gid = resolve_island_goods_id(item_spec)
                        qty = 9999
                    if gid and gid in items_map:
                        targets.append((gid, qty))

        if not targets:
            return {"bought_items": 0, "total_spent": 0, "details": []}

        print("\n" + "═" * 78)
        print("  🛒 بدء الشراء من متجر الجزيرة الغامضة (Mysterious Island Store)")
        print("═" * 78)
        print(f"  💰 رصيد النقاط المتاح: {current_points:,} نقطة\n")

        bought_total_items = 0
        total_points_spent = 0
        details = []

        for i, (gid, desired_qty) in enumerate(targets):
            meta = ISLAND_SHOP_CATALOG[gid]
            field_shop = self.conn.init_data.get("fieldShopCtrl", {})
            shop1 = field_shop.get("1", {})
            records = shop1.get("buyRecord", {}).get("1", {}).get("records", {})
            bought_already = int(records.get(str(gid), 0))
            remaining_today = max(0, meta["limit"] - bought_already)

            if remaining_today <= 0:
                print(f"  ℹ️ [{meta['name']}]: تم استنفاد الحد اليومي بالفعل ({meta['limit']}/{meta['limit']}).")
                continue

            current_points = self.get_island_points()
            price = meta["price"]
            affordable = current_points // price if price > 0 else remaining_today

            if affordable <= 0:
                print(f"  ⚠️ [{meta['name']}]: رصيد النقاط ({current_points:,}) غير كافٍ لسعر القطعة ({price:,})!")
                continue

            buy_qty = min(remaining_today, desired_qty, affordable)
            if buy_qty <= 0:
                continue

            if i > 0:
                jitter = round(random.uniform(1.6, 2.8), 2)
                self.log.info(f"🛡️ انتظار أمان بشري بين المشتريات: {jitter} ثانية...")
                await asyncio.sleep(jitter)

            cost = buy_qty * price
            self.log.info(f"👉 شراء {buy_qty} من [{meta['name']}] بتكلفة {cost:,} نقطة...")
            ok, msg, actual_bought = await self._buy_shop_goods(gid, buy_qty)
            if ok:
                bought_total_items += actual_bought
                spent = actual_bought * price
                total_points_spent += spent
                print(f"  ✅ [{meta['name']}]: تم شراء {actual_bought} قطعة بنجاح! التكلفة: {spent:,} نقطة | الرصيد المتبقي: {self.get_island_points():,} نقطة")
                details.append((meta["name"], actual_bought, spent))
            else:
                print(f"  ❌ [{meta['name']}]: {msg}")

        print("═" * 78 + "\n")
        return {
            "bought_items": bought_total_items,
            "total_spent": total_points_spent,
            "details": details
        }

    # ──────────────────────────────────────────────────────────────────
    #  تنفيذ المهمة بالكامل (Main Execution Flow)
    # ──────────────────────────────────────────────────────────────────

    async def run(self) -> TaskResult:
        """
        تنفيذ استعلام المهام، استلام المكافآت الجاهزة، تعيين المهام المؤهلة،
        وشراء المنتجات المحددة من متجر الجزيرة الغامضة.
        """
        # انتظار وصول بيانات PveBattleCtrl و heroCtrl و fieldShopCtrl
        for _ in range(15):
            if "PveBattleCtrl" in self.conn.init_data and "heroCtrl" in self.conn.init_data:
                break
            await asyncio.sleep(0.3)

        info = self.get_tasks_status()
        castle_heroes = self._get_castle_heroes()

        self._print_status_report(info, castle_heroes)

        if self.check_only:
            ready_count = sum(1 for t in info["tasks"] if t["status_code"] == "ready")
            claim_count = sum(1 for t in info["tasks"] if t["status_code"] == "claimable")
            run_count = sum(1 for t in info["tasks"] if t["status_code"] == "running")
            shop_status = self.get_island_shop_status()
            msg = f"🔍 تم فحص الميناء: مهام جاهزة: {ready_count} | جارية: {run_count} | للاستلام: {claim_count} | رصيد المتجر: {shop_status['points']:,} نقطة"
            return TaskResult.ok(msg, tasks=info["tasks"], heroes_count=len(castle_heroes), shop=shop_status)

        claimed_count = 0
        dispatched_count = 0
        failed_count = 0
        time_reward_claimed = False
        time_reward_pts = 0

        # ── القسم الأول: استلام الجائزة الآلية لمكافأة الوقت (CMD 2064 / 9) ──
        if self.auto_claim and self.claim_time_reward:
            ok, msg, pts_gained = await self._claim_time_reward()
            if ok:
                time_reward_claimed = True
                time_reward_pts = pts_gained
                print(f"  🎁 [الجائزة الآلية]: {msg}")
                jitter = round(random.uniform(1.2, 2.0), 2)
                await asyncio.sleep(jitter)
            else:
                self.log.info(f"ℹ️ [الجائزة الآلية]: {msg}")

        # ── القسم الثاني: مهام التعيين ──
        if not self.skip_delegate:
            claimable_tasks = [t for t in info["tasks"] if t["status_code"] == "claimable"]
            if claimable_tasks and self.auto_claim:
                self.log.info(f"🎁 العثور على {len(claimable_tasks)} مهمة مكتملة، جارٍ استلام مكافآتها...")
                for t in claimable_tasks:
                    jitter = round(random.uniform(1.6, 2.8), 2)
                    await asyncio.sleep(jitter)

                    ok, msg = await self._claim_task_reward(t["id"])
                    if ok:
                        claimed_count += 1
                        print(f"  🎁 [{t['name']}]: {msg}")
                    else:
                        print(f"  ⚠️ [{t['name']}]: {msg}")

                info = self.get_tasks_status()

            ready_tasks = [t for t in info["tasks"] if t["status_code"] == "ready"]
            if self.target_task_ids:
                ready_tasks = [t for t in ready_tasks if t["id"] in self.target_task_ids]

            if ready_tasks:
                self.log.info(f"🚀 بدء التعيين والإرسال السريع لـ {len(ready_tasks)} مهمة جاهزة...")
                current_busy_heroes = set(info["busy_heroes"])

                for i, t in enumerate(ready_tasks):
                    pair = self.auto_select_heroes(t, castle_heroes, current_busy_heroes)
                    if not pair:
                        self.log.warning(f"⚠️ لا يتوفر عدد كافٍ من الأبطال الشاغرين في القلعة لـ [{t['name']}]!")
                        break

                    hero1, hero2, is_fit = pair

                    if i > 0:
                        jitter = round(random.uniform(1.8, 3.2), 2)
                        self.log.info(f"🛡️ انتظار أمان بشري: {jitter} ثانية...")
                        await asyncio.sleep(jitter)

                    bonus_tag = " ✨ (مطابقة الشروط الإضافية)" if is_fit else ""
                    self.log.info(f"👉 تعيين [{t['name']}] بالأبطال [{hero1}, {hero2}]{bonus_tag}...")

                    ok, err_msg = await self._dispatch_task(t["id"], [hero1, hero2])
                    if ok:
                        dispatched_count += 1
                        current_busy_heroes.add(hero1)
                        current_busy_heroes.add(hero2)
                        print(f"  ✅ [{t['name']}]: تم الإرسال بنجاح! الأبطال: ({hero1}, {hero2}){bonus_tag}")
                    else:
                        failed_count += 1
                        print(f"  ❌ [{t['name']}]: {err_msg}")

        # ── القسم الثالث: الشراء من متجر الجزيرة الغامضة ──
        shop_res = {"bought_items": 0, "total_spent": 0, "details": []}
        if not self.skip_shop and (self.buy_items or self.buy_all):
            shop_res = await self._execute_shop_purchases()

        summary_parts = []
        if time_reward_claimed:
            tr_desc = f"الجائزة الآلية (+{time_reward_pts:,} نقطة)" if time_reward_pts > 0 else "الجائزة الآلية"
            summary_parts.append(tr_desc)

        if not self.skip_delegate:
            summary_parts.append(f"التعيين: إرسال {dispatched_count} مهمة")
            if claimed_count > 0:
                summary_parts.append(f"استلام {claimed_count} مكافأة")
            if failed_count > 0:
                summary_parts.append(f"فشل {failed_count}")

        if shop_res["bought_items"] > 0:
            summary_parts.append(f"المتجر: شراء {shop_res['bought_items']} عنصر بتكلفة {shop_res['total_spent']:,} نقطة")

        summary = "🎯 " + " | ".join(summary_parts) if summary_parts else "🎯 اكتملت العملية بنجاح."
        return TaskResult.ok(
            summary,
            dispatched=dispatched_count,
            claimed=claimed_count,
            failed=failed_count,
            time_reward_claimed=time_reward_claimed,
            time_reward_points=time_reward_pts,
            shop_bought=shop_res["bought_items"],
            shop_spent=shop_res["total_spent"]
        )


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول كملف مستقل (CLI Runner)
# ════════════════════════════════════════════════════════════════════

async def _cli_main():
    parser = argparse.ArgumentParser(description="مهمة الميناء العسكري: التعيين السريع + متجر الجزيرة الغامضة")
    parser.add_argument("--email", type=str, help="البريد الإلكتروني للحساب")
    parser.add_argument("--check-only", action="store_true", help="استعلام فقط وعرض حالة المهام والمتجر")
    parser.add_argument("--no-claim", action="store_true", help="عدم استلام مكافآت المهام المكتملة تلقائياً")
    parser.add_argument("--no-time-reward", action="store_true", help="عدم استلام الجائزة الآلية (مكافأة الوقت)")
    parser.add_argument("--skip-delegate", action="store_true", help="تخطي مهام التعيين والاكتفاء بالمتجر فقط")
    parser.add_argument("--skip-shop", action="store_true", help="تخطي الشراء من المتجر والاكتفاء بمهام التعيين")
    parser.add_argument("--buy-items", type=str, help="المنتجات المراد شراؤها (مثال: 1,2,3 أو 1:2,5:5 أو morale,recruit)")
    parser.add_argument("--buy-all", action="store_true", help="شراء جميع المنتجات المتاحة في المتجر حتى نفاد النقاط")
    args = parser.parse_args()

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

    print(f"📡 جارٍ الاتصال بالحساب: {target_email}...")
    conn = GameConnection(acc)
    if not await conn.connect():
        print("❌ فشل الاتصال بالسيرفر!")
        return

    # انتظار استقرار بيانات الدخول
    for _ in range(15):
        await asyncio.sleep(0.3)
        if "PveBattleCtrl" in conn.init_data and "heroCtrl" in conn.init_data:
            break

    config = {
        "check_only": args.check_only,
        "auto_claim": not args.no_claim,
        "claim_time_reward": not args.no_time_reward,
        "skip_delegate": args.skip_delegate,
        "skip_shop": args.skip_shop,
        "buy_items": args.buy_items,
        "buy_all": args.buy_all
    }

    task = PortDelegateTask(conn, config)
    res = await task.run()

    print(f"\n📊 النتيجة النهائية:\n  {res.message}\n")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(_cli_main())
