# -*- coding: utf-8 -*-
"""
tasks/research.py — مهمة استعراض وإجراء أبحاث الأكاديمية (Academy Research Task)
════════════════════════════════════════════════════════════════════════════════
تقوم هذه المهمة بفحص حالة مبنى الأكاديمية (College) وطابور البحث:
  1. الاستعلام عن طابور البحث الحالي (1017/3) والتأكد هل هو متاح أم قيد البحث.
  2. الاستعلام عن قائمة الأبحاث المكتسبة ومستوياتها (1017/1).
  3. تحديد البحث الموصى به تلقائياً (حسب مهام الفصل أو مسار الشجرة المحددة) أو حسب --tech-id.
  4. عرض بيانات وتفاصيل البحث الموصى به باللغة العربية (الاسم، المعرف، الشجرة، المستوى).
  5. تنفيذ طلب البحث فوراً بالسيرفر عبر (1017/2) مع إرسال clientData المطابق.

الاستخدام كملف مستقل:
    python tasks/research.py --email "sumo-1234@hotmil.com"
    python tasks/research.py --email "burcudemr@gmail.com" --tree defense
    python tasks/research.py --email "burcudemr@gmail.com" --tech-id 23016
    python tasks/research.py --email "hmzawyha44@gmail.com" --check-only
    python tasks/research.py --all-accounts --tree resources
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
#  تصنيفات أشجار الأبحاث في اللعبة
# ════════════════════════════════════════════════════════════════════

TECH_TREES: Dict[str, Dict[str, Any]] = {
    "defense": {
        "name_ar": "🛡️ الدفاع والتحصينات (الأسوار والفخاخ)",
        "tech_ids": [
            23001, 23002, 23003, 23004, 23005, 23006, 23007, 23008, 23009, 23010,
            23011, 23012, 23013, 23014, 23015, 23016, 23017, 23018
        ]
    },
    "resources": {
        "name_ar": "🌾 الموارد والإنتاج",
        "tech_ids": [
            21001, 21002, 21003, 21004, 21005, 21006, 21007, 21008, 21009, 21010,
            21011, 21012, 21013, 21014, 21015, 21016, 21017, 21018, 21019, 21020
        ]
    },
    "city": {
        "name_ar": "🏛️ تنمية وتطوير المدينة",
        "tech_ids": [
            22001, 22002, 22003, 22004, 22005, 22006, 22007, 22008, 22009, 22010,
            22011, 22012, 22013, 22014
        ]
    },
    "military": {
        "name_ar": "⚔️ الشؤون العسكرية وتدريب الجيش",
        "tech_ids": [
            24001, 24002, 24003, 24004, 24005, 24006, 24007, 24008, 24009, 24010,
            24011, 24012, 24013, 24014, 24015, 24016, 24017, 24018, 24019, 24020,
            24021, 24022, 24023, 24024, 24025, 24026, 24027, 24028, 24029, 24030,
            24031, 24032, 24033, 24034, 24035, 24036, 24037, 24038, 24039, 24040,
            24041, 24042, 24043, 24044, 24045, 24046, 24047, 24048
        ]
    },
    "special": {
        "name_ar": "✨ التقنيات الخاصة",
        "tech_ids": list(range(24101, 24119))
    },
    "hero": {
        "name_ar": "👑 قيادة الأبطال والإمكانات",
        "tech_ids": list(range(25001, 25011))
    },
    "advanced": {
        "name_ar": "🔥 العسكرية المتقدمة والتكتيكات",
        "tech_ids": list(range(26001, 26035))
    },
    "war": {
        "name_ar": "⚔️ تكنولوجيا حرب الممالك",
        "tech_ids": [
            110001, 110002, 110003, 110004, 110005, 110006, 110007, 110008, 110009, 110010,
            110011, 110012, 110013, 110014, 110015, 110016, 110017, 110018, 110019, 110020,
            110021, 110027, 110028, 110030, 110031, 110035, 110036, 110037, 110038, 110039,
            110040, 110041, 110042, 110043, 110044, 110045, 110046, 110047, 110048, 110049,
            110050, 110051, 110056
        ]
    }
}

# خريطة أسماء الموارد
RESOURCE_NAMES = {
    "1002": "🌾 طعام",
    "1003": "🪵 خشب",
    "1004": "⛏️ حديد",
    "1005": "🪙 فضة"
}


# ════════════════════════════════════════════════════════════════════
#  تحميل قاموس أسماء الأبحاث
# ════════════════════════════════════════════════════════════════════

_TECH_NAMES_CACHE: Dict[str, Dict[str, Any]] = {}
_TECH_PREREQS_CACHE: Dict[str, Dict[str, Any]] = {}

def load_tech_names() -> Dict[str, Dict[str, Any]]:
    global _TECH_NAMES_CACHE
    if _TECH_NAMES_CACHE:
        return _TECH_NAMES_CACHE
    json_path = os.path.join(_ROOT_DIR, "database", "tech_names.json")
    if not os.path.exists(json_path):
        json_path = os.path.join(_ROOT_DIR, "tech_names.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                _TECH_NAMES_CACHE = json.load(f)
        except Exception as e:
            logging.getLogger("tasks").warning(f"⚠️ فشل قراءة tech_names.json: {e}")
    return _TECH_NAMES_CACHE


def load_tech_prereqs() -> Dict[str, Dict[str, Any]]:
    """تحميل متطلبات الأبحاث وشروط المباني والموارد من core/tech_prereqs.json بنمط Zero-Request."""
    global _TECH_PREREQS_CACHE
    if _TECH_PREREQS_CACHE:
        return _TECH_PREREQS_CACHE
    json_path = os.path.join(_ROOT_DIR, "core", "tech_prereqs.json")
    if not os.path.exists(json_path):
        json_path = os.path.join(_ROOT_DIR, "database", "tech_prereqs.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                _TECH_PREREQS_CACHE = json.load(f)
        except Exception as e:
            logging.getLogger("tasks").warning(f"⚠️ فشل قراءة tech_prereqs.json: {e}")
    return _TECH_PREREQS_CACHE


def format_duration(seconds: float) -> str:
    """تنسيق المدة بالثواني إلى صيغة مقروءة بالعربية."""
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
#  كلاس المهمة الرئيسي (ResearchTask)
# ════════════════════════════════════════════════════════════════════

class ResearchTask(BaseTask):
    """
    مهمة فحص وإجراء أبحاث الأكاديمية تلقائياً.
    """
    name = "research"

    def __init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None):
        super().__init__(conn, config)
        self.tech_names = load_tech_names()
        self.tech_prereqs = load_tech_prereqs()

    def get_building_levels_from_memory(self) -> Dict[str, int]:
        """
        استخراج مستويات مباني المدينة من الذاكرة الحية (init_data["cityCtrl"]["blist"])
        بنمط Zero-Request خالص بدون إرسال أي طلب للسيرفر.
        """
        levels: Dict[str, int] = {}
        if not self.conn or not hasattr(self.conn, "init_data") or not isinstance(self.conn.init_data, dict):
            return levels

        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        if not isinstance(city_ctrl, dict):
            return levels

        blist = city_ctrl.get("blist", [])
        if not isinstance(blist, list):
            return levels

        for item in blist:
            if isinstance(item, dict):
                binfo = item.get("binfo", {})
                if isinstance(binfo, dict):
                    # فحص حالة المبنى: حالة 8 تعني مقفل LOCK وغير مشيّد إطلاقاً في المدينة
                    state = str(binfo.get("state", "0"))
                    if state == "8":
                        continue
                    bid = str(binfo.get("bid", ""))
                    try:
                        lv = int(binfo.get("lv", 0))
                    except (ValueError, TypeError):
                        lv = 0
                    if bid and lv > levels.get(bid, 0):
                        levels[bid] = lv
        return levels

    def get_resources_from_memory(self) -> Dict[str, float]:
        """
        استخراج الموارد المتاحة من الذاكرة الحية (reslist + saferes)
        بنمط Zero-Request خالص بدون إرسال أي طلب شبكي.
        """
        res: Dict[str, float] = {"1002": 0.0, "1003": 0.0, "1004": 0.0, "1005": 0.0}
        if not self.conn or not hasattr(self.conn, "init_data") or not isinstance(self.conn.init_data, dict):
            return res

        city_ctrl = self.conn.init_data.get("cityCtrl", {})
        if not isinstance(city_ctrl, dict):
            return res

        reslist = city_ctrl.get("reslist", {})
        saferes = city_ctrl.get("saferes", {})

        for r_k in res:
            v_reg = 0.0
            v_safe = 0.0
            if isinstance(reslist, dict) and r_k in reslist:
                try:
                    v_reg = float(reslist[r_k])
                except (ValueError, TypeError):
                    v_reg = 0.0
            if isinstance(saferes, dict) and r_k in saferes:
                try:
                    v_safe = float(saferes[r_k])
                except (ValueError, TypeError):
                    v_safe = 0.0
            res[r_k] = v_reg + v_safe
        return res

    def get_backpack_items_from_memory(self) -> Dict[str, int]:
        """
        استخراج كميات الأدوات في الحقيبة من الذاكرة الحية (init_data["backpackCtrl"])
        بنمط Zero-Request خالص بدون إرسال أي طلب شبكي.
        """
        bag: Dict[str, int] = {}
        if not self.conn or not hasattr(self.conn, "init_data") or not isinstance(self.conn.init_data, dict):
            return bag

        bp = self.conn.init_data.get("backpackCtrl", {})
        if isinstance(bp, dict):
            for k, v in bp.items():
                if isinstance(v, dict):
                    try:
                        bag[str(k)] = int(v.get("count", 0))
                    except (ValueError, TypeError):
                        bag[str(k)] = 0
                elif isinstance(v, (int, str)):
                    try:
                        bag[str(k)] = int(v)
                    except (ValueError, TypeError):
                        bag[str(k)] = 0
        return bag

    def check_tech_feasibility(
        self,
        tech_id: str,
        target_level: int,
        learned_techs: Dict[str, int],
        building_levels: Dict[str, int],
        current_res: Dict[str, float],
        bag_items: Optional[Dict[str, int]] = None
    ) -> Tuple[bool, str]:
        """
        التحقق من إمكانية وصلاحية إجراء البحث بالاعتماد الكلي على الذاكرة الحية:
          1. فحص هل تجاوز البحث الحد الأقصى للمستوى.
          2. فحص مستوى مبنى الأكاديمية (College 113) وأي مبنى مشترط آخر مع فحص حالة القفل (LOCK=8).
          3. فحص الأبحاث السابقة المطلوبة (pre-requisite science).
          4. فحص الموارد المتاحة (طعام، خشب، حديد، فضة).
          5. فحص أدوات وأوسمة الحرب المطلوبة (technologyWEs مثل وسام الحرب 301101).
        """
        s_id = str(tech_id)
        s_lv = str(target_level)

        t_data = self.tech_prereqs.get(s_id, {})
        if not t_data:
            # إذا لم تكن البيانات مسجلة بالقاعدة، نسمح به فقط للمستوى 1 مع تنبيه
            return True, "بيانات المتطلبات غير مسجلة في القاعدة"

        lv_info = t_data.get(s_lv)
        if not lv_info:
            return False, f"تجاوز أقصى مستوى مسجل للبحث ({len(t_data)})"

        # 1. فحص مبنى الأكاديمية والمباني المشترطة
        build_reqs = lv_info.get("build_reqs", {})
        for req_bid, req_blv in build_reqs.items():
            curr_blv = building_levels.get(str(req_bid), 0)
            if curr_blv < int(req_blv):
                if str(req_bid) == "113":
                    b_name = "الأكاديمية"
                elif str(req_bid) == "301":
                    b_name = "المعجزة / قاعة المجد"
                elif str(req_bid) == "101":
                    b_name = "القلعة"
                else:
                    b_name = f"المبنى {req_bid}"
                curr_status = f"الحالي: {curr_blv}" if curr_blv > 0 else "المبنى مقفل أو غير مشيّد"
                return False, f"يتطلب {b_name} مستوى {req_blv} ({curr_status})"

        # 2. فحص الأبحاث المسبقة (pre_techs)
        pre_techs = lv_info.get("pre_techs", [])
        for pre in pre_techs:
            p_id = str(pre.get("tech_id"))
            p_req_lv = int(pre.get("level", 1))
            p_curr_lv = learned_techs.get(p_id, 0)
            if p_curr_lv < p_req_lv:
                p_title = self.get_tech_title(p_id)
                return False, f"يتطلب بحث {p_title} بمستوى {p_req_lv} (الحالي: {p_curr_lv})"

        # 3. فحص الموارد المتاحة من الذاكرة الحية
        cost_res = lv_info.get("cost_res", {})
        for r_id, r_cost in cost_res.items():
            cost_val = float(r_cost)
            if cost_val > 0:
                avail_val = current_res.get(str(r_id), 0.0)
                if avail_val < cost_val:
                    r_name = RESOURCE_NAMES.get(str(r_id), f"مورد #{r_id}")
                    return False, f"نقص في {r_name} (المطلوب: {int(cost_val):,} | المتوفر: {int(avail_val):,})"

        # 4. فحص متطلبات الأدوات وأوسمة الحرب (technologyWEs مثل وسام الحرب 301101)
        cost_wes = lv_info.get("cost_wes", {})
        if cost_wes and bag_items is not None:
            for w_id, w_cost in cost_wes.items():
                w_cost_int = int(w_cost)
                if w_cost_int > 0:
                    avail_cnt = bag_items.get(str(w_id), 0)
                    if avail_cnt < w_cost_int:
                        item_name = "وسام الحرب (301101)" if str(w_id) == "301101" else f"الأداة #{w_id}"
                        return False, f"نقص في {item_name} (المطلوب: {w_cost_int} | المتوفر: {avail_cnt})"

        return True, "جاهز ومستوفٍ لكافة الشروط"

    def get_tech_title(self, tech_id: Any) -> str:
        """إرجاع الاسم العربي والرمز للبحث."""
        s_id = str(tech_id)
        info = self.tech_names.get(s_id, {})
        name_ar = info.get("name_ar", "").strip()
        if not name_ar or name_ar.startswith("technology_name_"):
            name_en = info.get("name_en", "").strip()
            name_ar = name_en or f"بحث #{s_id}"
        return f"[{s_id}] {name_ar}"

    async def get_queue_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        الاستعلام عن حالة طابور الأبحاث الحالي بنمط Zero-Request.
        يفحص أولاً طابور أبحاث الأكاديمية (Queue 1212) في queueCtrl والذاكرة المؤقتة،
        ولا يرسل طلب 1017/3 إلى السيرفر إلا إذا كانت الذاكرة فارغة أو طُلب التحديث إجبارياً.
        """
        # 1. فحص طابور الأبحاث (1212) في queueCtrl داخل init_data مباشرة بدون أي طلب شبكي
        if not force_refresh and self.conn and hasattr(self.conn, "init_data"):
            init_data = self.conn.init_data
            if isinstance(init_data, dict) and "queueCtrl" in init_data:
                queue_ctrl = init_data.get("queueCtrl", {})
                if isinstance(queue_ctrl, dict):
                    q1212 = queue_ctrl.get("1212") or queue_ctrl.get(1212)
                    if isinstance(q1212, dict):
                        start_time = float(q1212.get("starttime", 0))
                        total_time = float(q1212.get("totaltime", q1212.get("ottime", 0)))
                        remain_time = max(0.0, (start_time + total_time) - time.time())
                        extra_data = q1212.get("data", {})

                        if remain_time > 0 and isinstance(extra_data, dict):
                            tech_keys = [k for k in extra_data.keys() if str(k).isdigit()]
                            if tech_keys:
                                cur_tid = tech_keys[0]
                                item_info = extra_data.get(cur_tid)
                                if isinstance(item_info, list):
                                    target_level = item_info[1] if len(item_info) > 1 else 1
                                    cost_info = item_info[2] if len(item_info) > 2 and isinstance(item_info[2], dict) else {}
                                elif isinstance(item_info, (int, str)):
                                    try:
                                        target_level = int(item_info)
                                    except (ValueError, TypeError):
                                        target_level = 1
                                    cost_info = {}
                                else:
                                    target_level = 1
                                    cost_info = {}

                                return {
                                    "is_busy": True,
                                    "remain_time": remain_time,
                                    "tech_id": str(cur_tid),
                                    "target_level": target_level,
                                    "cost_info": cost_info,
                                    "raw": q1212
                                }
                    else:
                        # طابور الأبحاث 1212 غير موجود في queueCtrl، مما يعني أن الطابور فارغ ومتاح
                        return {"is_busy": False, "remain_time": 0, "raw": {}}

        # 2. فحص الحزم المخزنة مسبقاً (cached_packets) لـ 1017/3
        if not force_refresh and self.conn:
            cached = getattr(self.conn, "cached_packets", {})
            resp_cached = cached.get(("1017", "3")) or cached.get((1017, 3))
            if isinstance(resp_cached, dict) and resp_cached.get("err") == "0":
                data = resp_cached.get("data", {})
                remain_time = float(data.get("remainTime", 0))
                extra_data = data.get("extraData", {})
                if remain_time > 0 and extra_data:
                    tech_keys = [k for k in extra_data.keys() if str(k).isdigit()]
                    if tech_keys:
                        cur_tid = tech_keys[0]
                        item_info = extra_data.get(cur_tid)
                        target_level = item_info[1] if isinstance(item_info, list) and len(item_info) > 1 else 1
                        cost_info = item_info[2] if isinstance(item_info, list) and len(item_info) > 2 and isinstance(item_info[2], dict) else {}
                        return {
                            "is_busy": True,
                            "remain_time": remain_time,
                            "tech_id": str(cur_tid),
                            "target_level": target_level,
                            "cost_info": cost_info,
                            "raw": data
                        }
                return {"is_busy": False, "remain_time": 0, "raw": data}

        # 3. الاستعلام الشبكي كخيار أخير عند الحاجة أو عند التحديث الإجباري
        self.log.warning("🛑🛑🛑🛑🛑🛑")
        resp = await self.conn.query("1017", "3", {}, timeout=6)
        if resp.get("err") != "0":
            return {"is_busy": False, "remain_time": 0}

        data = resp.get("data", {})
        remain_time = float(data.get("remainTime", 0))
        extra_data = data.get("extraData", {})

        if remain_time > 0 and extra_data:
            tech_keys = [k for k in extra_data.keys() if str(k).isdigit()]
            if tech_keys:
                cur_tid = tech_keys[0]
                item_info = extra_data.get(cur_tid)
                if isinstance(item_info, list):
                    target_level = item_info[1] if len(item_info) > 1 else 1
                    cost_info = item_info[2] if len(item_info) > 2 and isinstance(item_info[2], dict) else {}
                elif isinstance(item_info, (int, str)):
                    try:
                        target_level = int(item_info)
                    except (ValueError, TypeError):
                        target_level = 1
                    cost_info = {}
                else:
                    target_level = 1
                    cost_info = {}

                return {
                    "is_busy": True,
                    "remain_time": remain_time,
                    "tech_id": str(cur_tid),
                    "target_level": target_level,
                    "cost_info": cost_info,
                    "raw": data
                }

        return {"is_busy": False, "remain_time": 0, "raw": data}

    async def get_learned_technologies(self, force_refresh: bool = False) -> Dict[str, int]:
        """
        الاستعلام عن كافة الأبحاث المكتسبة ومستوياتها الحالية بنمط Zero-Request.
        يفحص أولاً technologyCtrl في الذاكرة الحية (init_data)، ولا يرسل 1017/1 إلا إذا كانت الذاكرة فارغة أو طُلب التحديث.
        """
        data: Dict[str, Any] = {}

        # 1. القراءة المباشرة من technologyCtrl المخزن بالذاكرة الحية
        if not force_refresh and self.conn and hasattr(self.conn, "init_data"):
            init_data = self.conn.init_data
            if isinstance(init_data, dict):
                tech_ctrl = init_data.get("technologyCtrl")
                if isinstance(tech_ctrl, dict) and tech_ctrl:
                    data = tech_ctrl

        # 2. فحص الحزم المخزنة مسبقاً (cached_packets) لـ 1017/1
        if not data and not force_refresh and self.conn:
            cached = getattr(self.conn, "cached_packets", {})
            resp_cached = cached.get(("1017", "1")) or cached.get((1017, 1))
            if isinstance(resp_cached, dict) and resp_cached.get("err") == "0":
                data = resp_cached.get("data", {})

        # 3. الاستعلام الشبكي كخيار أخير فقط عند الحاجة أو التحديث الإجباري
        if not data:
            self.log.warning("🛑🛑🛑🛑🛑🛑")
            resp = await self.conn.query("1017", "1", {}, timeout=6)
            if resp.get("err") == "0":
                data = resp.get("data", {})
                # تحديث الذاكرة الحية بالبيانات الجديدة
                if self.conn and hasattr(self.conn, "init_data") and isinstance(self.conn.init_data, dict):
                    self.conn.init_data["technologyCtrl"] = data
            else:
                return {}

        # تحليل وتنسيق الأبحاث المستخرجة
        learned: Dict[str, int] = {}
        for tid, val in data.items():
            if isinstance(val, list) and len(val) > 1:
                try:
                    learned[str(tid)] = int(val[1])
                except (ValueError, TypeError):
                    learned[str(tid)] = 1
            elif isinstance(val, (int, str)):
                try:
                    learned[str(tid)] = int(val)
                except (ValueError, TypeError):
                    learned[str(tid)] = 1
        return learned

    def determine_recommended_tech(
        self,
        learned_techs: Dict[str, int],
        tree_pref: str = "balanced",
        explicit_tech_id: Optional[str] = None,
        building_levels: Optional[Dict[str, int]] = None,
        current_res: Optional[Dict[str, float]] = None,
        bag_items: Optional[Dict[str, int]] = None
    ) -> Optional[Tuple[str, int, str]]:
        """
        تحديد البحث الموصى به بذكاء وموازنة متساوية بين جميع الأشجار:
          1. إذا حدد المستخدم بحثاً معيناً (--tech-id):
             - يتم فحص شروطه؛ إن تحققت اعتُمد، وإن تعذر وُضّح السبب في السجل وسقط إلى الاختيار المتوازن.
          2. النمط المتوازن (balanced / all / auto):
             - حساب إجمالي المستويات المكتسبة في كل شجرة أبحاث.
             - ترتيب الأشجار تصاعدياً (الشجرة الأقل تطوراً تحصل على الأولوية القصوى).
             - فحص أبحاث الشجرة الأقل (الأبحاث بمستوى 0 أولاً، ثم الأقل تصاعدياً).
             - فحص الصلاحية والمتطلبات (الأكاديمية + الأبحاث المسبقة + الموارد) عبر الذاكرة الحية.
             - إذا كانت الشجرة الأقل متعذرة بسبب شروط لم تكتمل، ينتقل تلقائياً للشجرة التالية الأقل (Cascading Fallback).
          3. إذا حدد المستخدم شجرة مخصصة (مثل: defense أو military):
             - تُفحص تلك الشجرة أولاً مع التحقق الصارم من المتطلبات.
             - إن تعذرت جميع أبحاث الشجرة المحددة، ينتقل تلقائياً للأشجار الأقل الأخرى لمنع توقف البوت.
        """
        if building_levels is None:
            building_levels = self.get_building_levels_from_memory()
        if current_res is None:
            current_res = self.get_resources_from_memory()
        if bag_items is None:
            bag_items = self.get_backpack_items_from_memory()

        # 1. إذا حدد المستخدم معرّف بحث صريحاً
        if explicit_tech_id:
            s_tid = str(explicit_tech_id).strip()
            cur_lv = learned_techs.get(s_tid, 0)
            target_lv = cur_lv + 1
            feasible, reason = self.check_tech_feasibility(s_tid, target_lv, learned_techs, building_levels, current_res, bag_items)
            if feasible:
                return (s_tid, target_lv, "محدد يدوياً")
            else:
                t_title = self.get_tech_title(s_tid)
                self.log.warning(f"⚠️ البحث المحدد يدوياً {t_title} غير ممكن حالياً ({reason})! سيتم الانتقال للبحث المتوازن...")

        # 2. تحديد قائمة الأشجار وترتيبها وفق مبدأ الموازنة المتساوية
        all_tree_keys = ["resources", "city", "defense", "military", "hero", "advanced", "special", "war"]
        is_balanced = (tree_pref in ("balanced", "all", "auto", "", "none") or tree_pref not in TECH_TREES)

        # حساب مجموع ومتوسط المستويات لكل شجرة في اللعبة
        tree_scores = []
        for t_k in all_tree_keys:
            if t_k in TECH_TREES:
                t_ids = [str(x) for x in TECH_TREES[t_k].get("tech_ids", [])]
                tot_lv = sum(learned_techs.get(tid, 0) for tid in t_ids)
                avg_lv = tot_lv / max(1, len(t_ids))
                tree_scores.append((t_k, tot_lv, avg_lv))

        # ترتيب تصاعدي: الأقل تطوراً في إجمالي المستويات أولاً
        tree_scores.sort(key=lambda x: (x[1], x[2]))

        if not is_balanced:
            # إذا اختار المستخدم شجرة معينة، تُفحص أولاً ثم باقي الأشجار كاحتياطي
            ordered_keys = [tree_pref] + [x[0] for x in tree_scores if x[0] != tree_pref]
        else:
            ordered_keys = [x[0] for x in tree_scores]

        # 3. البحث في الأشجار بالترتيب واختيار أول بحث مستوفٍ للشروط
        try:
            for t_key in ordered_keys:
                tree_data = TECH_TREES.get(t_key, {})
                if not isinstance(tree_data, dict):
                    continue

                tech_ids = tree_data.get("tech_ids", [])
                tree_title = tree_data.get("name_ar", t_key)

                # استخراج مرشحي الشجرة مع أقصى مستوى متاح
                candidates = []
                for tid in tech_ids:
                    s_id = str(tid)
                    cur_l = learned_techs.get(s_id, 0)
                    t_cfg = self.tech_prereqs.get(s_id, {})
                    max_l = len(t_cfg) or 10
                    if cur_l < max_l:
                        candidates.append((cur_l, int(tid), s_id))

                # فرز المرشحين: الأقل مستوى حالياً أولاً (المستوى 0 لفتح الجديد، ثم المستويات الأقل)
                candidates.sort(key=lambda c: (c[0], c[1]))

                for cur_l, _, s_id in candidates:
                    tgt_l = cur_l + 1
                    feasible, reason = self.check_tech_feasibility(s_id, tgt_l, learned_techs, building_levels, current_res, bag_items)
                    if feasible:
                        return (s_id, tgt_l, tree_title)

        except Exception as e:
            self.log.warning(f"⚠️ خطأ أثناء فحص شجرة الأبحاث: {e}")
            return None

        return None


    async def execute_research(self, tech_id: str) -> Dict[str, Any]:
        """
        إرسال أمر إجراء البحث للسيرفر (1017/2).
        مطابق للطلب الفعلي للعبة:
        {
          "cmd": "1017",
          "clientData": [tech_id],
          "subcmd": "2",
          "data": {
            "type": 1,
            "technologyId": tech_id,
            "rtype": 1
          }
        }
        """
        s_id = str(tech_id)
        payload = {
            "type": 1,
            "technologyId": s_id,
            "rtype": 1
        }
        resp = await self.conn.query(
            "1017",
            "2",
            payload,
            client_data=[s_id]
        )
        return resp

    async def run(self) -> TaskResult:
        cfg = self.config
        tree_pref = str(cfg.get("tree", "balanced")).lower().strip()
        explicit_id = cfg.get("tech_id")
        check_only = bool(cfg.get("check_only", False))

        self.log.info(f"🔬 بدء مهمة أبحاث الأكاديمية (الشجرة: {tree_pref} | بحث مخصص: {explicit_id or 'متوازن تلقائي'})")

        # 1. الاستعلام عن طابور البحث من الذاكرة الحية
        queue_info = await self.get_queue_status()

        # 2. الاستعلام عن الأبحاث الحالية من الذاكرة الحية
        learned_techs = await self.get_learned_technologies()
        self.log.info(f"📚 تم استرجاع {len(learned_techs)} بحث مكتمل/قيد التطوير للحساب.")

        # إذا كان الطابور مشغولاً بالفعل
        if queue_info.get("is_busy"):
            cur_tid = queue_info.get("tech_id")
            tgt_lv = queue_info.get("target_level", 1)
            rem_sec = queue_info.get("remain_time", 0)
            cur_title = self.get_tech_title(cur_tid)
            rem_str = format_duration(rem_sec)

            msg = f"⏳ طابور الأبحاث مشغول حالياً ببحث {cur_title} للمستوى {tgt_lv} (متبقي: {rem_str})"
            self.log.warning(msg)
            return TaskResult(
                success=True,
                message=msg,
                data={
                    "status": "busy",
                    "current_research": cur_title,
                    "tech_id": cur_tid,
                    "target_level": tgt_lv,
                    "remain_seconds": int(rem_sec),
                    "remain_human": rem_str
                },
                should_retry=True,
                retry_after=max(60, int(rem_sec))
            )

        # 3. قراءة مستويات المباني والموارد ومحتويات الحقيبة من الذاكرة الحية (بدون أي طلب شبكي)
        building_levels = self.get_building_levels_from_memory()
        current_res = self.get_resources_from_memory()
        bag_items = self.get_backpack_items_from_memory()
        college_lv = building_levels.get("113", 0)
        self.log.info(f"🏛️ مستوى الأكاديمية الحالي بالذاكرة: {college_lv}")

        # 4. تحديد البحث الموصى به وفق الموازنة المتساوية مع فحص المتطلبات المسبقة
        rec = self.determine_recommended_tech(
            learned_techs=learned_techs,
            tree_pref=tree_pref,
            explicit_tech_id=explicit_id,
            building_levels=building_levels,
            current_res=current_res,
            bag_items=bag_items
        )
        if not rec:
            msg = "⚠️ لم يتم العثور على أي بحث مستوفٍ للمتطلبات وشروط الأكاديمية والموارد حالياً!"
            self.log.warning(msg)
            return TaskResult.fail(msg)

        rec_tid, target_lv, tree_name = rec
        rec_title = self.get_tech_title(rec_tid)
        cur_lv = learned_techs.get(rec_tid, 0)

        self.log.info(f"💡 البحث الموصى به: {rec_title} | الشجرة: {tree_name} | المستوى: {cur_lv} -> {target_lv}")

        # 5. إذا كان الخيار فحص وعرض فقط
        if check_only:
            msg = f"🔍 [فحص فقط] البحث الموصى به: {rec_title} (مستوى {cur_lv} ➔ {target_lv}) في {tree_name}"
            return TaskResult.ok(
                msg,
                tech_id=rec_tid,
                name=rec_title,
                tree=tree_name,
                current_level=cur_lv,
                target_level=target_lv,
                action="checked"
            )

        # 6. تنفيذ البحث فوراً بالسيرفر
        self.log.info(f"🚀 جارٍ إرسال أمر إجراء البحث للسيرفر: {rec_title}...")
        resp = await self.execute_research(rec_tid)
        err = str(resp.get("err", "-1"))

        if err == "0":
            # تحديث حالة الطابور لمعرفة وقت الانتهاء والموارد المستهلكة
            new_queue = await self.get_queue_status()
            rem_sec = new_queue.get("remain_time", 0)
            rem_str = format_duration(rem_sec)

            success_msg = f"✅ تم بنجاح بدء البحث الموصى به: {rec_title} (المستوى {target_lv}) ⏳ الوقت: {rem_str}"
            self.log.info(success_msg)
            return TaskResult.ok(
                success_msg,
                tech_id=rec_tid,
                name=rec_title,
                target_level=target_lv,
                tree=tree_name,
                duration_seconds=int(rem_sec),
                duration_human=rem_str,
                cost_info=new_queue.get("cost_info", {})
            )
        else:
            # معالجة الخطأ وتفسيره بدقة
            err_msg = f"❌ فشل بدء البحث {rec_title}! رمز الخطأ: {err}"
            if err == "10006":
                err_msg += " (لم يتم بلوغ مستوى المبنى المشترط للبحث - Err_PRECOND_BUILD_NOT_REACH)"
            elif err == "10007":
                err_msg += " (الأبحاث السابقة المشترطة غير مكتملة - Err_PRE_SCIENCE_NOT_REACH)"
            elif err == "101701" or "resource" in str(resp).lower():
                err_msg += " (الموارد غير كافية أو متطلبات المبنى غير مكتملة)"
            elif err == "101702":
                err_msg += " (متطلبات الأكاديمية أو الأبحاث السابقة غير محققة)"
            self.log.error(err_msg)
            return TaskResult.fail(err_msg, err=err, resp=resp)


# ════════════════════════════════════════════════════════════════════
#  التشغيل المباشر كملف مستقل (CLI Runner)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Empire Academy Research Task — مهمة فحص وإجراء أبحاث الأكاديمية"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument(
        "--tree", "-t", default="balanced",
        choices=["balanced", "all", "defense", "resources", "city", "military", "advanced", "war", "special", "hero"],
        help="مسار شجرة الأبحاث المستهدفة أو موازنة متساوية [افتراضي: balanced]"
    )
    parser.add_argument("--tech-id", "-id", help="تحديد معرّف بحث معين بالرقم لإجرائه مباشرة (مثل: 23016)")
    parser.add_argument("--check-only", "-c", action="store_true", help="فحص وعرض البحث الموصى به دون بدئه")
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
            "tree": args.tree,
            "tech_id": args.tech_id,
            "check_only": args.check_only
        }

        task = ResearchTask(conn, task_cfg)
        await task.on_start()
        res = await task.run()

        print("\n" + "─" * 70)
        if res.success:
            print(f"🎉 {res.message}")
            if res.data:
                for k, v in res.data.items():
                    if k != "raw":
                        print(f"   • {k}: {v}")
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
