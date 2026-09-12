# -*- coding: utf-8 -*-
"""
tasks/building.py — مهمة ترقية القلعة ومباني الموارد والمعسكرات والتسريع الذكي
══════════════════════════════════════════════════════════════════════════════════
تقوم هذه المهمة بإدارة وترقية مباني المدينة وترقية القلعة وفق النظام الموصى به:
  1. ترقية القلعة (Castle 101) حسب التوصية والأولويات:
     - فحص ما إذا كانت القلعة قيد الترقية بالفعل.
     - فحص المتطلبات المسبقة للقلعة (مثل الأسوار 102 والمبنى المطلوب تمهيدياً).
     - تطبيق مبدأ "الأولى فالأولى": إذا كانت الأسوار أو المتطلبات أقل من المطلوب، تُرقّى المتطلبات أولاً.
     - إرسال أمر ترقية القلعة (1001/3) بالموارد فقط (ممنوع الترقية بالذهب منعاً باتاً).
  2. ترقية مباني الموارد والمعسكرات والمستشفى (مبنى واحد من كل نوع في كل دورة):
     - مزارع القمح (201)
     - مناشر الخشب (202)
     - مناجم الحديد (203)
     - مناجم الفضة/الألماس (204)
     - المراكز الطبية / المستشفيات (206)
     - الخيام العسكرية / المعسكرات (205)
     - جمع المحصول أولاً لمباني الموارد عبر (1001/8) ثم إرسال الترقية عبر (1001/3).
     - ترقية المبنى الأقل مستوى دائماً لتحقيق التوازن والترقية الذكية.
     - مراعاة طوابير البناء المتاحة (طابوران بحد أقصى) والتوقف بأمان عند امتلاء الطوابير.
  3. تسريع ترقية القلعة فقط (إذا فُعّل خيار التسريع):
     - استخدام التسريع المجاني الفوري (1003/2 mode: 0) عند توفره.
     - استخدام أدوات تسريع البناء الخاصة (5011xx) والعامة (5006xx) من الحقيبة.
     - ممنوع التسريع بالذهب تماماً.
     - التسريع مخصص للقلعة فقط ولا يُطبّق على باقي المباني.

خيارات التشغيل:
    python tasks/building.py --email "samartilleli@yopmail.com" --castle --buildings
    python tasks/building.py --email "burcudemr@gmail.com" --castle --speedup
    python tasks/building.py --email "johan2003@yopmail.com" --no-castle --buildings
    python tasks/building.py --email "king7moe1990@gmail.com" --check-only
    python tasks/building.py --all-accounts
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
from typing import Any, Dict, List, Optional, Tuple

from tasks.base_task import BaseTask, TaskResult
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  تعريفات المباني وأدوات التسريع
# ════════════════════════════════════════════════════════════════════

BUILDING_INFO: Dict[str, Dict[str, Any]] = {
    "101": {"name": "🏰 القلعة (Castle)", "category": "castle", "harvest": False},
    "102": {"name": "🧱 الأسوار (Walls)", "category": "walls", "harvest": False},
    "116": {"name": "🐎 معسكر الخيالة (Cavalry Barracks)", "category": "camp", "harvest": False},
    "117": {"name": "🏹 معسكر الرماة (Archer Barracks)", "category": "camp", "harvest": False},
    "118": {"name": "🛡️ معسكر المشاة (Infantry Barracks)", "category": "camp", "harvest": False},
    "119": {"name": "🚜 معسكر العربات (Chariot Barracks)", "category": "camp", "harvest": False},
    "201": {"name": "🌾 مزرعة القمح (Farm)", "category": "resource", "harvest": True},
    "202": {"name": "🪵 منشرة الخشب (Sawmill)", "category": "resource", "harvest": True},
    "203": {"name": "⛏️ منجم الحديد (Iron Mine)", "category": "resource", "harvest": True},
    "204": {"name": "🪙 منجم الفضة/الألماس (Steel/Silver)", "category": "resource", "harvest": True},
    "205": {"name": "⛺ الخيمة العسكرية (Military Tent)", "category": "tent", "harvest": False},
    "206": {"name": "🏥 المركز الطبي (Hospital)", "category": "hospital", "harvest": False},
}

# أدوات تسريع البناء والتسريع العام مرتبة من الأطول للأقصر
SPEEDUP_ITEMS: List[Tuple[int, int, str]] = [
    # تسريع بناء المباني (Building Speedup 5011xx)
    (501105, 86400, "تسريع بناء 24 ساعة"),
    (501104, 43200, "تسريع بناء 12 ساعة"),
    (501103, 28800, "تسريع بناء 8 ساعات"),
    (501102, 7200,  "تسريع بناء ساعتين"),
    (501107, 3600,  "تسريع بناء ساعة"),
    (501101, 300,   "تسريع بناء 5 دقائق"),
    (501106, 60,    "تسريع بناء دقيقة"),
    # تسريع عام (General Speedup 5006xx)
    (500605, 86400, "تسريع عام 24 ساعة"),
    (500604, 43200, "تسريع عام 12 ساعة"),
    (500603, 28800, "تسريع عام 8 ساعات"),
    (500602, 3600,  "تسريع عام ساعة"),
    (500601, 300,   "تسريع عام 5 دقائق"),
    (500606, 60,    "تسريع عام دقيقة"),
]

def format_duration(seconds: float) -> str:
    """تنسيق المدة بالثواني إلى نص مقروء بالعربية."""
    total_sec = int(max(0, seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours} س")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes} د")
    parts.append(f"{secs} ث")
    return " و ".join(parts)


# ════════════════════════════════════════════════════════════════════
#  كلاس المهمة (BuildingTask)
# ════════════════════════════════════════════════════════════════════

class BuildingTask(BaseTask):
    """
    مهمة فحص وترقية القلعة ومباني الموارد والمعسكرات مع التسريع الذكي للقلعة.
    """
    name = "building"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)

    async def get_city_buildings(self) -> List[Dict[str, Any]]:
        """الاستعلام عن جميع مباني المدينة عبر 1001/1."""
        resp = await self.conn.query("1001", "1", {}, timeout=10)
        blist = resp.get("data", {}).get("blist", [])
        return blist

    async def get_active_build_queues(self) -> Dict[str, Dict[str, Any]]:
        """
        الاستعلام عن طوابير البناء النشطة حالياً عبر 1003/1.
        يعيد dict يربط qtype (1200 / 1201) ببيانات البناء (bid, lv, remain_time).
        """
        resp = await self.conn.query("1003", "1", {}, timeout=8)
        data = resp.get("data", {})
        active_queues = {}
        if isinstance(data, dict):
            for qtype in ["1200", "1201"]:
                q_info = data.get(qtype)
                if q_info and isinstance(q_info, dict):
                    q_data = q_info.get("data", {})
                    bid = str(q_data.get("bid", ""))
                    lv = int(q_data.get("lv", 0))
                    total_time = float(q_info.get("totaltime", 0))
                    active_queues[qtype] = {
                        "qtype": qtype,
                        "bid": bid,
                        "lv": lv,
                        "remain_time": total_time,
                        "raw": q_info
                    }
        return active_queues

    async def harvest_resource_building(self, bid: int, iid: int) -> bool:
        """جمع المحصول من مبنى الموارد قبل الترقية عبر 1001/8."""
        try:
            resp = await self.conn.query("1001", "8", {"bid": bid, "iid": iid}, timeout=6)
            return resp.get("err") == "0"
        except Exception as e:
            self.log.warning(f"⚠️ خطأ أثناء جمع الموارد من مبنى {bid}/{iid}: {e}")
            return False

    async def upgrade_building(self, bid: str, index: str) -> Dict[str, Any]:
        """
        إرسال أمر الترقية لمبنى معين عبر 1001/3 بالموارد حصراً (mode: 0).
        ممنوع استخدام الذهب نهائياً.
        """
        payload = {
            "bid": str(bid),
            "mode": "0",  # ترقية بالموارد فقط
            "index": str(index)
        }
        resp = await self.conn.query("1001", "3", payload, timeout=10)
        return resp

    async def speedup_castle(self, qtype: Optional[str] = None, max_seconds_to_speed: int = 86400 * 30) -> int:
        """
        تسريع ترقية القلعة فقط باستخدام التسريع المجاني وأدوات التسريع من الحقيبة.
        ممنوع استخدام الذهب نهائياً.
        يعيد إجمالي الثواني التي تم تسريعها.
        """
        # 1. فحص طابور القلعة للتأكد من الوقت المتبقي والبحث التلقائي عن طابور القلعة
        queues = await self.get_active_build_queues()
        if not qtype or (qtype in queues and str(queues[qtype].get("bid")) != "101"):
            for qt, qi in queues.items():
                if str(qi.get("bid")) == "101":
                    qtype = qt
                    break

        castle_q = queues.get(qtype) if qtype else None
        if not castle_q or str(castle_q.get("bid")) != "101":
            for qt, qi in queues.items():
                if str(qi.get("bid")) == "101":
                    qtype = qt
                    castle_q = qi
                    break

        if not castle_q or str(castle_q.get("bid")) != "101":
            self.log.info("ℹ️ لم يتم العثور على القلعة قيد الترقية على أي طابور للتسريع.")
            return 0

        self.log.info(f"⚡ بدء محاولة تسريع ترقية القلعة على طابور {qtype}...")
        total_reduced_sec = 0

        remain_sec = castle_q.get("remain_time", 0)
        self.log.info(f"⏳ الوقت المتبقي لترقية القلعة: {format_duration(remain_sec)} ({int(remain_sec)} ثانية)")

        # 2. تجربة التسريع المجاني أولاً (mode: 0)
        resp_free = await self.conn.query("1003", "2", {
            "qtype": str(qtype),
            "mode": "0",
            "otherinfo": "",
            "count": 1,
            "decreaseTime": "0"
        }, timeout=8)
        if resp_free.get("err") == "0":
            self.log.info("🎉 تم تطبيق التسريع المجاني الفوري للقلعة بنجاح!")
            return int(remain_sec)

        # 3. فحص أدوات التسريع في الحقيبة عبر 1004/1
        resp_bag = await self.conn.query("1004", "1", {}, timeout=8)
        bag_items = resp_bag.get("data", {})
        if not isinstance(bag_items, dict):
            return 0

        # 4. استخدام أدوات التسريع المناسبة
        for item_id, item_sec, item_name in SPEEDUP_ITEMS:
            s_id = str(item_id)
            if s_id not in bag_items:
                continue

            available_count = int(bag_items[s_id].get("count", 0))
            if available_count <= 0:
                continue

            if remain_sec <= 300:  # إذا كان الوقت صغيراً جداً، قد يدخل في النطاق المجاني
                break

            # حساب كم نحتاج من هذا الأداة دون إهدار وقت زائد كبير
            needed_count = int(remain_sec // item_sec)
            if needed_count <= 0:
                continue

            use_count = min(available_count, needed_count)
            self.log.info(f"📦 استخدام {use_count}x من {item_name} (معرف {item_id}) لتسريع القلعة...")

            resp_tool = await self.conn.query("1003", "2", {
                "qtype": str(qtype),
                "mode": "2",  # TOOLS
                "otherinfo": s_id,
                "count": use_count,
                "decreaseTime": "0"
            }, timeout=8)

            if resp_tool.get("err") == "0":
                reduced = use_count * item_sec
                total_reduced_sec += reduced
                remain_sec = max(0, remain_sec - reduced)
                bag_items[s_id]["count"] = available_count - use_count
                self.log.info(f"✅ تم تقليص {format_duration(reduced)} | الوقت المتبقي: {format_duration(remain_sec)}")

                # تجربة التسريع المجاني بعد كل تقليص
                resp_free = await self.conn.query("1003", "2", {
                    "qtype": str(qtype),
                    "mode": "0",
                    "otherinfo": "",
                    "count": 1,
                    "decreaseTime": "0"
                }, timeout=5)
                if resp_free.get("err") == "0":
                    self.log.info("🎉 اكتملت ترقية القلعة عبر التسريع المجاني بعد تقليص الوقت!")
                    return total_reduced_sec + int(remain_sec)
            else:
                self.log.warning(f"⚠️ فشل استخدام الأداة {item_id}: {resp_tool.get('err')}")
                break

        return total_reduced_sec

    async def run(self) -> TaskResult:
        cfg = self.config
        do_castle = bool(cfg.get("upgrade_castle", cfg.get("castle", True)))
        do_buildings = bool(cfg.get("upgrade_support_buildings", cfg.get("buildings", cfg.get("support_buildings", True))))
        do_speedup = bool(cfg.get("speedup_castle", cfg.get("speedup", False)))
        check_only = bool(cfg.get("check_only", False))

        self.log.info(
            f"🏗️ بدء مهمة ترقية المباني (ترقية القلعة: {do_castle} | "
            f"ترقية المعسكرات والموارد: {do_buildings} | تسريع القلعة: {do_speedup} | فحص فقط: {check_only})"
        )

        # 1. الاستعلام عن حالة طوابير البناء النشطة
        active_queues = await self.get_active_build_queues()
        active_count = len(active_queues)
        self.log.info(f"📊 عدد طوابير البناء النشطة حالياً: {active_count} من أصل 2")
        for qtype, qinfo in active_queues.items():
            b_name = BUILDING_INFO.get(qinfo['bid'], {}).get("name", f"مبنى #{qinfo['bid']}")
            self.log.info(f"   • طابور {qtype}: {b_name} (المستوى {qinfo['lv']}) ⏳ متبقي: {format_duration(qinfo['remain_time'])}")

        # 2. جلب جميع مباني المدينة ومستوياتها
        blist = await self.get_city_buildings()
        if not blist:
            msg = "⚠️ فشل جلب بيانات مباني المدينة من السيرفر (1001/1)!"
            self.log.error(msg)
            return TaskResult.fail(msg)

        # تجميع المباني حسب bid
        buildings_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for item in blist:
            binfo = item.get("binfo", {})
            bid = str(binfo.get("bid", ""))
            if bid:
                if bid not in buildings_by_type:
                    buildings_by_type[bid] = []
                buildings_by_type[bid].append(binfo)

        # العثور على القلعة والأسوار
        castle_list = buildings_by_type.get("101", [])
        walls_list = buildings_by_type.get("102", [])
        castle_binfo = castle_list[0] if castle_list else None
        walls_binfo = walls_list[0] if walls_list else None

        castle_lv = int(castle_binfo.get("lv", 0)) if castle_binfo else 0
        walls_lv = int(walls_binfo.get("lv", 0)) if walls_binfo else 0
        castle_idx = str(castle_binfo.get("index", "1050")) if castle_binfo else "1050"
        walls_idx = str(walls_binfo.get("index", "1053")) if walls_binfo else "1053"
        castle_state = str(castle_binfo.get("state", "0")) if castle_binfo else "0"

        self.log.info(f"🏰 مستوى القلعة الحالي: {castle_lv} | 🧱 مستوى الأسوار الحالي: {walls_lv}")

        # نتائج العمليات
        actions_taken = []

        # ─────────────────────────────────────────────────────────────
        #  القسم 1: تسريع القلعة (إذا كانت قيد الترقية وخيار التسريع مفعل)
        # ─────────────────────────────────────────────────────────────
        if do_speedup:
            castle_qtype = None
            for qtype, qinfo in active_queues.items():
                if str(qinfo.get("bid")) == "101":
                    castle_qtype = qtype
                    break

            if castle_state == "2" or castle_qtype:
                if not check_only:
                    reduced = await self.speedup_castle(castle_qtype or "1200")
                    if reduced > 0:
                        actions_taken.append(f"⚡ تم تسريع ترقية القلعة بمقدار {format_duration(reduced)}")
                        # تحديث الطوابير بعد التسريع
                        active_queues = await self.get_active_build_queues()
                        active_count = len(active_queues)
                else:
                    actions_taken.append("🔍 [فحص] القلعة قيد الترقية ومؤهلة للتسريع")
            else:
                self.log.info("ℹ️ القلعة ليست قيد الترقية حالياً لتسريعها.")

        # ─────────────────────────────────────────────────────────────
        #  القسم 2: ترقية القلعة الموصى بها (الأولى فالأولى)
        # ─────────────────────────────────────────────────────────────
        if do_castle and (check_only or active_count < 2):
            is_castle_upgrading = (castle_state == "2") or any(str(q.get("bid")) == "101" for q in active_queues.values())

            if is_castle_upgrading:
                self.log.info(f"⏳ القلعة ({castle_lv}) قيد الترقية حالياً بالفعل.")
                actions_taken.append(f"🏰 القلعة (مستوى {castle_lv}) قيد الترقية بالفعل")
            else:
                # التحقق من المتطلبات المسبقة للقلعة:
                # الشرط الأساسي في اللعبة: الأسوار (102) يجب أن تصل لمستوى القلعة الحالي لترقية القلعة
                if walls_lv < castle_lv:
                    self.log.warning(
                        f"⚠️ [الأولى فالأولى] ترقية القلعة إلى {castle_lv + 1} تتطلب وصول الأسوار إلى مستوى {castle_lv} أولاً "
                        f"(الأسوار حالياً: {walls_lv})!"
                    )
                    if not check_only:
                        self.log.info(f"🧱 جاري ترقية الأسوار أولاً تمهيداً للقلعة (مستوى {walls_lv} ➔ {walls_lv + 1})...")
                        r_wall = await self.upgrade_building("102", walls_idx)
                        if r_wall.get("err") == "0":
                            actions_taken.append(f"🧱 تم بدء ترقية الأسوار (مستوى {walls_lv + 1}) لفتح ترقية القلعة")
                            active_count += 1
                        else:
                            actions_taken.append(f"⚠️ تعذر ترقية الأسوار: خطأ {r_wall.get('err')}")
                    else:
                        actions_taken.append(f"🔍 [فحص] التوصية للقلعة: ترقية الأسوار أولاً من {walls_lv} إلى {castle_lv} تمهيداً للقلعة")
                else:
                    # الأسوار جاهزة: محاولة ترقية القلعة مباشرة
                    self.log.info(f"🚀 الأسوار مكتملة ({walls_lv}). جاري ترقية القلعة إلى المستوى {castle_lv + 1}...")
                    if not check_only:
                        r_castle = await self.upgrade_building("101", castle_idx)
                        err_c = str(r_castle.get("err", "-1"))
                        if err_c == "0":
                            actions_taken.append(f"🏰 تم بنجاح بدء ترقية القلعة إلى المستوى {castle_lv + 1} 🎉")
                            active_count += 1
                            # إذا كان التسريع مفعل، نسارع فوراً بتسريع القلعة بعد بدئها!
                            if do_speedup:
                                await asyncio.sleep(1.0)
                                await self.speedup_castle("1200")
                        elif err_c == "1001":
                            actions_taken.append("🛑 طوابير البناء ممتلئة بالكامل")
                        else:
                            actions_taken.append(f"⚠️ فشل ترقية القلعة: كود الخطأ {err_c} (قد تنقص موارد أو شروط خاصة)")
                    else:
                        actions_taken.append(f"🔍 [فحص] القلعة جاهزة للترقية إلى المستوى {castle_lv + 1}")

        # ─────────────────────────────────────────────────────────────
        #  القسم 3: ترقية الموارد والمعسكرات والمستشفى (واحد فقط لكل نوع)
        # ─────────────────────────────────────────────────────────────
        if do_buildings and (check_only or active_count < 2):
            # الأنواع المستهدفة: مزارع (201-204)، مستشفى/مركز طبي (206)، خيمة عسكرية (205)، ومعسكرات الجيش (116-119)
            target_types = ["201", "202", "203", "204", "206", "205", "116", "117", "118", "119"]

            for bid in target_types:
                if not check_only and active_count >= 2:
                    self.log.info("🛑 تم شغل طوابير البناء المتاحة (2/2).")
                    break

                b_list = buildings_by_type.get(bid, [])
                if not b_list:
                    continue

                # تصفية المباني التي ليست قيد الترقية حالياً
                available_to_upgrade = [b for b in b_list if str(b.get("state", "0")) != "2"]
                if not available_to_upgrade:
                    self.log.info(f"ℹ️ جميع مباني النوع {bid} قيد الترقية حالياً.")
                    continue

                # اختيار المبنى ذو المستوى الأقل لتحقيق التوازن الشامل
                available_to_upgrade.sort(key=lambda x: int(x.get("lv", 0)))
                chosen_b = available_to_upgrade[0]

                cur_lv = int(chosen_b.get("lv", 0))
                idx = str(chosen_b.get("index", ""))
                iid = int(chosen_b.get("iid", 0))
                b_name = BUILDING_INFO.get(bid, {}).get("name", f"مبنى #{bid}")
                is_resource = BUILDING_INFO.get(bid, {}).get("harvest", False)

                self.log.info(f"🎯 ترشيح ترقية: {b_name} (مستوى {cur_lv} ➔ {cur_lv + 1} | index: {idx})")

                if not check_only:
                    # 1. إذا كان مبنى موارد: جمع المحصول أولاً (1001/8)
                    if is_resource:
                        await self.harvest_resource_building(int(bid), iid)
                        await asyncio.sleep(0.3)

                    # 2. إرسال أمر الترقية (1001/3)
                    r_up = await self.upgrade_building(bid, idx)
                    err_up = str(r_up.get("err", "-1"))
                    if err_up == "0":
                        actions_taken.append(f"✅ تم بدء ترقية {b_name} (مستوى {cur_lv + 1} | index {idx})")
                        active_count += 1
                        # تحديث حالة المبنى محلياً لمنع تكراره في نفس الدورة
                        chosen_b["state"] = "2"
                    elif err_up == "1001":
                        self.log.info("🛑 طوابير البناء ممتلئة.")
                        break
                    else:
                        self.log.warning(f"⚠️ فشل ترقية {b_name}: كود {err_up}")
                else:
                    actions_taken.append(f"🔍 [فحص] موصى بترقية: {b_name} من مستوى {cur_lv} إلى {cur_lv + 1}")

        # ─────────────────────────────────────────────────────────────
        #  النتيجة النهائية
        # ─────────────────────────────────────────────────────────────
        summary_msg = " | ".join(actions_taken) if actions_taken else "لم يتم اتخاذ أي إجراء (الطوابير ممتلئة أو الشروط غير محققة)"
        self.log.info(f"🏁 ملخص نتيجة المهمة: {summary_msg}")

        return TaskResult.ok(
            summary_msg,
            castle_level=castle_lv,
            walls_level=walls_lv,
            active_queues=active_count,
            actions=actions_taken
        )


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (CLI Runner)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Empire Building Upgrade Task — مهمة ترقية القلعة ومباني الموارد والمعسكرات والتسريع"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--castle", dest="castle", action="store_true", default=True, help="ترقية القلعة وفق النظام الموصى به [افتراضي: True]")
    parser.add_argument("--no-castle", dest="castle", action="store_false", help="تعطيل ترقية القلعة")
    parser.add_argument("--buildings", "--resources", dest="buildings", action="store_true", default=True, help="ترقية مباني الموارد والمعسكرات والمستشفى [افتراضي: True]")
    parser.add_argument("--no-buildings", dest="buildings", action="store_false", help="تعطيل ترقية مباني الموارد والمعسكرات")
    parser.add_argument("--speedup", "--speedup-castle", dest="speedup_castle", action="store_true", default=False, help="تسريع ترقية القلعة فقط بالأدوات المجانية والحقيبة")
    parser.add_argument("--check-only", "-c", action="store_true", help="فحص وعرض المباني الموصى بترقيتها دون إجراء الترقية")
    parser.add_argument("--all-accounts", action="store_true", help="تشغيل المهمة لجميع الحسابات المسجلة")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    from core.session_manager import SessionManager

    async def _run_for_account(acc_email: str, acc_obj: Any):
        print("\n" + "═" * 70)
        print(f"🏰 الحساب المستهدف: {acc_email}")
        print("═" * 70)

        conn = GameConnection(acc_obj)
        if not await conn.connect():
            print(f"❌ فشل الاتصال بالحساب {acc_email}!")
            return

        for _ in range(12):
            await asyncio.sleep(0.4)
            if len(conn.init_data) > 0:
                break

        task_cfg = {
            "castle": args.castle,
            "buildings": args.buildings,
            "speedup_castle": args.speedup_castle,
            "check_only": args.check_only
        }

        task = BuildingTask(conn, task_cfg)
        await task.on_start()
        res = await task.run()

        print("\n" + "─" * 70)
        if res.success:
            print(f"🎉 {res.message}")
            if res.data and "actions" in res.data:
                for act in res.data["actions"]:
                    print(f"   • {act}")
        else:
            print(f"⚠️ {res.message}")
        print("─" * 70)

        await conn.close()

    async def _main():
        sm = SessionManager()
        accounts = sm.load()
        if not accounts:
            print("❌ لا توجد حسابات مسجلة في session_cache.json!")
            return

        target_list = []
        if args.all_accounts:
            target_list = list(accounts.items())
        else:
            target_email = args.email or next(iter(accounts.keys()))
            acc = accounts.get(target_email)
            if not acc:
                print(f"❌ الحساب {target_email} غير موجود!")
                return
            target_list = [(target_email, acc)]

        for email, acc in target_list:
            if email.startswith("azjfhf"):  # تخطي الحسابات المغلقة المعروفة
                continue
            await _run_for_account(email, acc)

    asyncio.run(_main())
