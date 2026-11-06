# -*- coding: utf-8 -*-
"""
check_building_upgrade.py — أداة فحص متطلبات ترقية أي مبنى في المدينة
══════════════════════════════════════════════════════════════════════════════════
تقوم هذه الأداة بفحص متطلبات ترقية أي مبنى محدد (القلعة، الأسوار، المشافي، الخيام،
المزارع، الأكاديمية، الحصن، إلخ) لحساب معين:
  1. طوابير البناء (Active Build Queues) والوقت المتبقي.
  2. المباني المشروطة المسبقة (Prerequisite Buildings / preCond).
  3. أوسمة الحرب وأدوات الحقيبة (War Medals / costWEs / costTools).
  4. الموارد المطلوبة (القمح، الخشب، الحديد، الكوارتز).
  5. إصدار قرار نهائي يوضح هل المبنى جاهز 100% للترقية أم لا وما هي المعوقات.

طريقة الاستخدام:
  python check_building_upgrade.py --email "king7moe1990@gmail.com" --building 301
  python check_building_upgrade.py --email "email@gmail.com" --building walls
  python check_building_upgrade.py --building 101
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import asyncio
import argparse
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from core.session_manager import SessionManager
from game_client import GameConnection


# ════════════════════════════════════════════════════════════════════
#  قاموس المباني والأسماء والبدائل (Aliases)
# ════════════════════════════════════════════════════════════════════

BUILDING_META: Dict[str, Dict[str, Any]] = {
    "101": {"name": "🏰 القلعة (Castle)", "name_ar": "القلعة", "max_lv": 130},
    "102": {"name": "🧱 الأسوار (Walls)", "name_ar": "الأسوار", "max_lv": 130},
    "103": {"name": "🛡️ البرج الدفاعي (Turret)", "name_ar": "البرج الدفاعي", "max_lv": 130},
    "104": {"name": "🔭 برج المراقبة (Watchtower)", "name_ar": "برج المراقبة", "max_lv": 30},
    "105": {"name": "📦 المستودع (Depot)", "name_ar": "المستودع", "max_lv": 130},
    "107": {"name": "💰 التاجر (Merchant)", "name_ar": "التاجر", "max_lv": 1},
    "108": {"name": "⚓ الميناء (Port)", "name_ar": "الميناء", "max_lv": 1},
    "111": {"name": "🏛️ السفارة (Embassy)", "name_ar": "السفارة", "max_lv": 130},
    "112": {"name": "⚖️ السوق (Market)", "name_ar": "السوق", "max_lv": 30},
    "113": {"name": "🎓 المعهد / الأكاديمية (College)", "name_ar": "المعهد", "max_lv": 130},
    "114": {"name": "⛲ نافورة الأمنيات (Wishing Well)", "name_ar": "نافورة الأمنيات", "max_lv": 130},
    "115": {"name": "⚒️ الحداد (Blacksmith)", "name_ar": "الحداد", "max_lv": 30},
    "116": {"name": "🐎 معسكر الخيالة (Cavalry Barracks)", "name_ar": "معسكر الخيالة", "max_lv": 130},
    "117": {"name": "🏹 معسكر الرماة (Archer Barracks)", "name_ar": "معسكر الرماة", "max_lv": 130},
    "118": {"name": "🛡️ معسكر المشاة (Infantry Barracks)", "name_ar": "معسكر المشاة", "max_lv": 130},
    "119": {"name": "🚜 معسكر العربات (Chariot Barracks)", "name_ar": "معسكر العربات", "max_lv": 130},
    "120": {"name": "🏰 الحصن (Fortress)", "name_ar": "الحصن", "max_lv": 30},
    "121": {"name": "🎯 ساحة التدريب (Drill Grounds)", "name_ar": "ساحة التدريب", "max_lv": 130},
    "122": {"name": "⚔️ قاعة الحرب (Hall of War)", "name_ar": "قاعة الحرب", "max_lv": 130},
    "201": {"name": "🌾 مزرعة القمح (Farm)", "name_ar": "مزرعة القمح", "max_lv": 130},
    "202": {"name": "🪵 منشرة الخشب (Sawmill)", "name_ar": "منشرة الخشب", "max_lv": 130},
    "203": {"name": "⛏️ منجم الحديد (Iron Mine)", "name_ar": "منجم الحديد", "max_lv": 130},
    "204": {"name": "🪙 منجم الكوارتز (Quartz Mine)", "name_ar": "منجم الكوارتز", "max_lv": 130},
    "205": {"name": "⛺ الخيمة العسكرية (Military Tent)", "name_ar": "الخيمة العسكرية", "max_lv": 130},
    "206": {"name": "🏥 المركز الطبي / المشفى (Hospital)", "name_ar": "المركز الطبي", "max_lv": 130},
    "207": {"name": "💎 منجم الكريستال (Crystal Mine)", "name_ar": "منجم الكريستال", "max_lv": 80},
    "301": {"name": "🎖️ هيبة السلطان (Sultan's Glory)", "name_ar": "هيبة السلطان", "max_lv": 101},
    "302": {"name": "👑 القصر النخبوي (Elite Palace)", "name_ar": "القصر النخبوي", "max_lv": 5},
}

BUILDING_ALIASES: Dict[str, str] = {
    # 101 Castle
    "101": "101", "castle": "101", "قلعة": "101", "القلعة": "101", "kale": "101",
    # 102 Walls
    "102": "102", "walls": "102", "wall": "102", "سور": "102", "السور": "102", "الاسوار": "102", "أسوار": "102", "sur": "102",
    # 103 Turret
    "103": "103", "turret": "103", "برج دفاعي": "103", "البرج الدفاعي": "103", "kule": "103",
    # 104 Watchtower
    "104": "104", "watchtower": "104", "tower": "104", "برج مراقبة": "104", "برج المراقبة": "104", "gozetleme": "104",
    # 105 Depot
    "105": "105", "depot": "105", "مستودع": "105", "المستودع": "105", "depo": "105",
    # 111 Embassy
    "111": "111", "embassy": "111", "سفارة": "111", "السفارة": "111", "elcilik": "111",
    # 112 Market
    "112": "112", "market": "112", "سوق": "112", "السوق": "112", "pazar": "112",
    # 113 College
    "113": "113", "college": "113", "academy": "113", "معهد": "113", "المعهد": "113", "اكاديمية": "113", "أكاديمية": "113", "akademi": "113",
    # 114 Wishing Well
    "114": "114", "wishing": "114", "well": "114", "نافورة": "114", "نافورة الامنيات": "114", "نافورة الأمنيات": "114", "dilek": "114",
    # 115 Blacksmith
    "115": "115", "blacksmith": "115", "حداد": "115", "الحداد": "115", "demirci": "115",
    # Barracks (116 - 119)
    "116": "116", "cavalry": "116", "horse": "116", "خيالة": "116", "معسكر الخيالة": "116", "suvari": "116",
    "117": "117", "archer": "117", "bow": "117", "رماة": "117", "معسكر الرماة": "117", "okcu": "117",
    "118": "118", "infantry": "118", "foot": "118", "مشاة": "118", "معسكر المشاة": "118", "piyade": "118",
    "119": "119", "chariot": "119", "cart": "119", "عربات": "119", "معسكر العربات": "119", "araba": "119",
    # 120 Fortress
    "120": "120", "fortress": "120", "حصن": "120", "الحصن": "120", "hisar": "120",
    # 121 Drill Grounds
    "121": "121", "drill": "121", "ساحة التدريب": "121", "talim": "121",
    # 122 Hall of War
    "122": "122", "warhall": "122", "war_hall": "122", "قاعة الحرب": "122", "savas_salonu": "122",
    # Resource buildings (201 - 204)
    "201": "201", "farm": "201", "wheat": "201", "قمح": "201", "مزرعة": "201", "مزرعة القمح": "201", "tahil": "201", "ciftlik": "201",
    "202": "202", "sawmill": "202", "wood": "202", "خشب": "202", "منشرة": "202", "منشرة الخشب": "202", "odun": "202", "kereste": "202",
    "203": "203", "iron": "203", "iron_mine": "203", "حديد": "203", "منجم حديد": "203", "منجم الحديد": "203", "demir": "203",
    "204": "204", "quartz": "204", "quartz_mine": "204", "silver": "204", "كوارتز": "204", "فضة": "204", "منجم الكوارتز": "204", "kuvars": "204",
    # 205 Military Tent
    "205": "205", "tent": "205", "military_tent": "205", "خيمة": "205", "الخيمة": "205", "خيمة عسكرية": "205", "الخيمة العسكرية": "205", "cadir": "205",
    # 206 Hospital
    "206": "206", "hospital": "206", "clinic": "206", "مشفى": "206", "المشفى": "206", "مركز طبي": "206", "المركز الطبي": "206", "hastane": "206",
    # 207 Crystal Mine
    "207": "207", "crystal": "207", "منجم الكريستال": "207", "kristal": "207",
    # 301 Honor Hall / Miracle
    "301": "301", "هيبة": "301", "هيبة السلطان": "301", "سلطان": "301", "miracle": "301", "honor": "301", "مجد": "301", "قاعة المجد": "301", "شرف": "301", "معجزة": "301", "anit": "301",
    # 302 Elite Palace
    "302": "302", "elite": "302", "elite_palace": "302", "قصر نخبوي": "302", "القصر النخبوي": "302",
}

RES_INFO: Dict[int, Dict[str, str]] = {
    1002: {"name": "القمح (Food)", "emoji": "🌾"},
    1003: {"name": "الخشب (Wood)", "emoji": "🪵"},
    1004: {"name": "الحديد (Iron)", "emoji": "⛏️"},
    1005: {"name": "الكوارتز (Quartz)", "emoji": "🪙"},
}

ITEM_INFO: Dict[int, Dict[str, str]] = {
    301101: {"name": "وسام الحرب (War Medal / War Essence)", "emoji": "🎖️"},
    300501: {"name": "سهم الدفاع / بلورة البرج (Defense Arrow / Crystal)", "emoji": "🏹"},
    300601: {"name": "كتاب الحرب (Tome of War)", "emoji": "📜"},
}

# كاش حفظ جداول المباني المحملة
_BUILDING_CFG_CACHE: Dict[str, Dict[int, Dict[str, Any]]] = {}


# ════════════════════════════════════════════════════════════════════
#  دوال مساعدة في التنسيق وتحميل ملفات اللعبة
# ════════════════════════════════════════════════════════════════════

def resolve_bid(building_input: Union[str, int]) -> str:
    """تحويل أي إدخال (معرف رقمي أو اسم بالإنجليزية أو العربية) إلى معرّف المبنى bid."""
    raw = str(building_input).strip().lower()
    if raw in BUILDING_ALIASES:
        return BUILDING_ALIASES[raw]
    # محاولة تنظيف الكلمات الشائعة مثل 'upgrade' أو 'bld'
    cleaned = raw.replace("upgrade_", "").replace("bld_", "").replace("build", "").strip()
    if cleaned in BUILDING_ALIASES:
        return BUILDING_ALIASES[cleaned]
    return raw


def format_duration(seconds: float) -> str:
    """تنسيق المدة بالثواني إلى نص مقروء بالعربية (أيام، ساعات، دقائق)."""
    total_sec = int(max(0, seconds))
    days = total_sec // 86400
    rem = total_sec % 86400
    hours = rem // 3600
    minutes = (rem % 3600) // 60
    secs = rem % 60
    parts = []
    if days > 0:
        parts.append(f"{days}يوم")
    if hours > 0:
        parts.append(f"{hours}ساعة")
    if minutes > 0:
        parts.append(f"{minutes}دقيقة")
    if secs > 0 and days == 0 and hours == 0:
        parts.append(f"{secs}ثانية")
    return " و ".join(parts) if parts else "0 ثانية"


def format_level_display(bid: str, lv: int) -> str:
    """
    تنسيق المستوى إلى نص واضح ومفهوم كما يظهر داخل اللعبة:
    - المستويات العادية (1 - 30)
    - مستويات الشرف / المجد (31 - 40) -> شرف 1..10
    - مستويات الحرب (41 - 130) -> مستوى الحرب N + تقدم النسبة المئوية
    """
    if lv <= 0:
        return "غير مبني (مستوى 0)"
    if lv <= 30:
        return f"المستوى {lv}"
    if lv <= 40:
        honor_num = lv - 30
        return f"المستوى {lv} (شرف {honor_num})"

    # مستوى الحرب (War Level): كل 10 مستويات تعادل رتبة حرب واحدة
    base_war_lv = (lv - 30) // 10
    step = (lv - 30) % 10
    if step == 0:
        return f"المستوى {lv} [مستوى الحرب {base_war_lv}]"
    else:
        next_war_lv = base_war_lv + 1
        pct = step * 10
        return f"المستوى {lv} [مستوى الحرب {base_war_lv} + تقدم {pct}% نحو حرب {next_war_lv}]"


def parse_lua_build_table(content: str) -> Dict[int, Dict[str, Any]]:
    """محلل مخصص لقراءة جداول اللعبة Lua (build*.lua) واستخراج المتطلبات والتكاليف."""
    entries: Dict[int, Dict[str, Any]] = {}
    pos = 0
    pattern = re.compile(r'\[(\d+)\]\s*=\s*\{')
    while True:
        m = pattern.search(content, pos)
        if not m:
            break
        lv = int(m.group(1))
        start = m.end()
        depth = 1
        i = start
        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            i += 1
        block = content[start:i - 1]
        pos = i

        def _get_sub_dict(key: str) -> Dict[str, int]:
            km = re.search(rf'{key}\s*=\s*\{{([^}}]*)\}}', block)
            res: Dict[str, int] = {}
            if km and km.group(1).strip():
                nums = [int(x.strip()) for x in re.findall(r'\d+', km.group(1))]
                for idx in range(0, len(nums), 2):
                    if idx + 1 < len(nums):
                        res[str(nums[idx])] = nums[idx + 1]
            return res

        time_m = re.search(r'costTime\s*=\s*(\d+)', block)
        cost_time = int(time_m.group(1)) if time_m else 0

        blv_m = re.search(r'blv\s*=\s*(\d+)', block)
        actual_lv = int(blv_m.group(1)) if blv_m else lv

        entries[actual_lv] = {
            "preCond": _get_sub_dict("preCond"),
            "costRes": _get_sub_dict("costRes"),
            "costWEs": _get_sub_dict("costWEs"),
            "costTools": _get_sub_dict("costTools"),
            "costTime": cost_time,
        }
    return entries


def load_building_config(bid: str) -> Dict[int, Dict[str, Any]]:
    """تحميل جدول متطلبات المبنى من ملف JSON الشامل في core/ (يعمل على السيرفر) أو Lua محلياً مع التخزين المؤقت."""
    global _BUILDING_CFG_CACHE
    bid_str = str(bid)
    if bid_str in _BUILDING_CFG_CACHE:
        return _BUILDING_CFG_CACHE[bid_str]

    # 1. فحص ملف JSON الشامل في core/ (يعمل على السيرفر والمحلي دون الحاجة لـ Lua)
    bp_path = os.path.join(_ROOT_DIR, "core", "buildings_prereqs.json")
    if not os.path.exists(bp_path):
        bp_path = os.path.join(_ROOT_DIR, "buildings_prereqs.json")
    if os.path.exists(bp_path):
        try:
            with open(bp_path, "r", encoding="utf-8") as fp:
                raw = json.load(fp)
                if bid_str in raw:
                    cfg = {int(k): v for k, v in raw[bid_str].items()}
                    _BUILDING_CFG_CACHE[bid_str] = cfg
                    return cfg
        except Exception:
            pass

    # مسارات البحث المحتملة عن ملفات Lua
    lua_file = os.path.join(_ROOT_DIR, "lua_src", "src", "src", "app", "localtb", "config_server", f"build{bid_str}.lua")
    if not os.path.exists(lua_file):
        alt_lua = os.path.join(_ROOT_DIR, "lua_src", f"build{bid_str}.lua")
        if os.path.exists(alt_lua):
            lua_file = alt_lua

    if os.path.exists(lua_file):
        try:
            with open(lua_file, "r", encoding="utf-8", errors="ignore") as fp:
                cfg = parse_lua_build_table(fp.read())
            if cfg:
                _BUILDING_CFG_CACHE[bid_str] = cfg
                return cfg
        except Exception as e:
            logging.getLogger("check_building").warning(f"⚠️ فشل تحليل {lua_file}: {e}")

    # بديل احتياطي خاص بالقلعة: castle_prereqs.json
    if bid_str == "101":
        cp_file = os.path.join(_ROOT_DIR, "database", "castle_prereqs.json")
        if not os.path.exists(cp_file):
            cp_file = os.path.join(_ROOT_DIR, "castle_prereqs.json")
        if not os.path.exists(cp_file):
            cp_file = os.path.join(_ROOT_DIR, "core", "castle_prereqs.json")
        if os.path.exists(cp_file):
            try:
                with open(cp_file, "r", encoding="utf-8") as f:
                    cfg = {int(k): v for k, v in json.load(f).items()}
                _BUILDING_CFG_CACHE[bid_str] = cfg
                return cfg
            except Exception:
                pass

    return {}


# ════════════════════════════════════════════════════════════════════
#  الدالة الرئيسية: فحص متطلبات ترقية أي مبنى
# ════════════════════════════════════════════════════════════════════

async def check_building_upgrade(
    account_email: str,
    building_target: Union[str, int],
    conn: Optional[GameConnection] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    فحص شامل لمتطلبات ترقية مبنى محدد لحساب معين:
      - account_email: البريد الإلكتروني للحساب.
      - building_target: معرّف المبنى (رقمي أو اسم عربي/إنجليزي مثل 'walls' أو '102').
      - conn: كائن اتصال جاهز GameConnection (اختياري، إذا لم يُمرر سيتم إنشاء اتصال تلقائي).
      - verbose: طباعة تقرير مرئي جميل ومفصل في الكونسول.

    تعيد قاموساً يحتوي على:
      - is_ready (bool): هل كل شيء جاهز للترقية بنسبة 100%.
      - current_level (int): المستوى الحالي للمبنى.
      - target_level (int): المستوى المستهدف للترقية.
      - queues (dict): حالة طوابير البناء (عدد المشغول، المتاح، تفاصيل كل طابور).
      - prerequisites (list): قائمة المباني المشروطة وحالتها (مستوفاة أم ناقصة).
      - items (list): قائمة الأدوات وأوسمة الحرب المطلوبة وحالتها.
      - resources (list): قائمة الموارد المطلوبة وحالتها والرصيد الحالي والنقص.
      - blocking_reasons (list): قائمة الأسباب المعيقة للترقية بدقة.
    """
    bid = resolve_bid(building_target)
    b_meta = BUILDING_META.get(bid, {"name": f"مبنى #{bid}", "name_ar": f"مبنى #{bid}", "max_lv": 130})
    b_name = b_meta["name"]

    # 1. الاتصال بالحساب إذا لم يتم تمرير اتصال نشط
    should_close_conn = False
    if conn is None or not conn.is_connected:
        sm = SessionManager()
        accounts = sm.load()
        acc_obj = accounts.get(account_email)
        if not acc_obj:
            err_msg = f"❌ الحساب {account_email} غير موجود في session_cache.json!"
            if verbose:
                print(err_msg)
            return {"success": False, "is_ready": False, "error": err_msg}

        conn = GameConnection(acc_obj)
        if not await conn.connect():
            err_msg = f"❌ فشل الاتصال بخادم اللعبة للحساب {account_email}!"
            if verbose:
                print(err_msg)
            return {"success": False, "is_ready": False, "error": err_msg}
        should_close_conn = True

        # انتظار وصول حزم التهيئة الأولية
        for _ in range(15):
            await asyncio.sleep(0.3)
            if len(conn.init_data) > 0 and "cityCtrl" in conn.init_data:
                break

    try:
        # 2. الاستعلام عن طوابير البناء النشطة عبر 1003/1
        active_queues: Dict[str, Dict[str, Any]] = {}
        try:
            q_resp = await conn.query("1003", "1", {}, timeout=8)
            if q_resp and isinstance(q_resp, dict):
                q_data = q_resp.get("data", {})
                for qt in ["1200", "1201"]:
                    qi = q_data.get(qt)
                    if qi and isinstance(qi, dict):
                        q_info_data = qi.get("data", {})
                        active_queues[qt] = {
                            "qtype": qt,
                            "bid": str(q_info_data.get("bid", "")),
                            "lv": int(q_info_data.get("lv", 0)),
                            "remain_time": float(qi.get("totaltime", 0)),
                            "start_time": qi.get("starttime", 0),
                        }
        except Exception as e:
            logging.getLogger("check_building").warning(f"⚠️ فشل جلب طوابير البناء: {e}")

        active_count = len(active_queues)
        has_free_queue = active_count < 2

        # 3. الاستعلام عن جميع مباني المدينة عبر 1001/1
        blist: List[Dict[str, Any]] = []
        for attempt in range(2):
            try:
                b_resp = await conn.query("1001", "1", {}, timeout=10)
                if b_resp and isinstance(b_resp, dict):
                    blist = b_resp.get("data", {}).get("blist", [])
                    if blist:
                        break
            except Exception:
                pass
            await asyncio.sleep(0.5)

        if not blist:
            # محاولة جلبها من init_data.cityCtrl
            blist = conn.init_data.get("cityCtrl", {}).get("blist", [])

        # تجميع المباني حسب bid
        buildings_by_bid: Dict[str, List[Dict[str, Any]]] = {}
        for item in blist:
            bi = item.get("binfo", {}) if isinstance(item, dict) else {}
            item_bid = str(bi.get("bid", ""))
            if item_bid:
                buildings_by_bid.setdefault(item_bid, []).append(bi)

        # تحديد المبنى المستهدف ومستواه
        target_instances = buildings_by_bid.get(bid, [])
        chosen_instance = None
        if target_instances:
            # إذا كان هناك أكثر من مبنى (كالمزارع)، نختار المبنى ذو المستوى الأقل للترشيح للترقية
            target_instances.sort(key=lambda x: int(x.get("lv", 0)))
            chosen_instance = target_instances[0]
            current_lv = int(chosen_instance.get("lv", 0))
        else:
            current_lv = 0

        target_lv = current_lv + 1
        is_already_upgrading = False
        if chosen_instance:
            if str(chosen_instance.get("state", "0")) == "2":
                is_already_upgrading = True
        for q in active_queues.values():
            if str(q.get("bid")) == bid:
                is_already_upgrading = True

        # 4. جلب الموارد الحالية (cityCtrl.reslist و saferes)
        city_ctrl = conn.init_data.get("cityCtrl", {})
        reslist = city_ctrl.get("reslist", {}) if isinstance(city_ctrl, dict) else {}
        saferes = city_ctrl.get("saferes", {}) if isinstance(city_ctrl, dict) else {}

        # 5. جلب عناصر الحقيبة عبر 1004/1 للتحقق من أوسمة الحرب والأدوات
        bag_items: Dict[str, int] = {}
        try:
            bag_resp = await conn.query("1004", "1", {}, timeout=8)
            if bag_resp and isinstance(bag_resp, dict):
                bdata = bag_resp.get("data", {})
                if isinstance(bdata, dict):
                    for item_id_str, item_val in bdata.items():
                        if isinstance(item_val, dict):
                            bag_items[str(item_id_str)] = int(item_val.get("count", 0))
                        elif isinstance(item_val, (int, float)):
                            bag_items[str(item_id_str)] = int(item_val)
        except Exception:
            pass
        # دمج عناصر الحقيبة من init_data.backpackCtrl كإسناد إضافي
        bp_ctrl = conn.init_data.get("backpackCtrl", {})
        if isinstance(bp_ctrl, dict):
            for item_id_str, item_val in bp_ctrl.items():
                if str(item_id_str) not in bag_items:
                    if isinstance(item_val, dict):
                        bag_items[str(item_id_str)] = int(item_val.get("count", 0))
                    elif isinstance(item_val, (int, float, str)) and str(item_val).isdigit():
                        bag_items[str(item_id_str)] = int(item_val)

        # 6. جلب جدول متطلبات الترقية للمستوى المستهدف من ملف Lua
        b_cfg = load_building_config(bid)
        req_cfg = b_cfg.get(target_lv, {})
        if not req_cfg and target_lv <= b_meta.get("max_lv", 130):
            # محاولة البحث عن المستوى في المفاتيح النصية
            req_cfg = b_cfg.get(str(target_lv), {})

        pre_cond = req_cfg.get("preCond", {})
        cost_res = req_cfg.get("costRes", {})
        cost_wes = req_cfg.get("costWEs", {})
        cost_tools = req_cfg.get("costTools", {})
        cost_time = int(req_cfg.get("costTime", 0))

        # ═════════════════════════════════════════════════════════════
        #  فحص الشروط والموانع
        # ═════════════════════════════════════════════════════════════
        blocking_reasons: List[str] = []
        is_ready = True

        # أ. فحص ما إذا كان المبنى قد بلغ الحد الأقصى
        max_lv = b_meta.get("max_lv", 130)
        is_max_level = current_lv >= max_lv
        if is_max_level:
            is_ready = False
            blocking_reasons.append(f"المبنى بلغ الحد الأقصى للمستوى ({max_lv})")

        # ب. فحص ما إذا كان المبنى قيد الترقية بالفعل
        if is_already_upgrading:
            is_ready = False
            blocking_reasons.append("المبنى قيد الترقية حالياً على أحد طوابير البناء")

        # ج. فحص طوابير البناء
        queues_report = {
            "active_count": active_count,
            "has_free_queue": has_free_queue,
            "details": []
        }
        for qt, qi in active_queues.items():
            qb_name = BUILDING_META.get(qi['bid'], {}).get("name", f"مبنى #{qi['bid']}")
            queues_report["details"].append({
                "qtype": qt,
                "bid": qi['bid'],
                "name": qb_name,
                "level": qi['lv'],
                "remain_time": qi['remain_time'],
                "remain_formatted": format_duration(qi['remain_time'])
            })
        if not has_free_queue and not is_already_upgrading:
            is_ready = False
            blocking_reasons.append("طوابير البناء مشغولة بالكامل (2/2)")

        # د. فحص المباني المشروطة المسبقة (preCond)
        prereqs_report = []
        for req_bid, req_lv in pre_cond.items():
            req_bid_str = str(req_bid)
            r_meta = BUILDING_META.get(req_bid_str, {"name": f"مبنى #{req_bid_str}", "name_ar": f"مبنى #{req_bid_str}"})
            r_instances = buildings_by_bid.get(req_bid_str, [])
            curr_r_lv = max((int(x.get("lv", 0)) for x in r_instances), default=0)
            is_r_upgrading = any(str(x.get("state", "0")) == "2" for x in r_instances) or any(
                str(q.get("bid")) == req_bid_str for q in active_queues.values()
            )
            fulfilled = curr_r_lv >= int(req_lv)
            if not fulfilled:
                is_ready = False
                blocking_reasons.append(
                    f"نقص شرط مبنى: {r_meta['name_ar']} (الحالي: {curr_r_lv} < المطلوب: {req_lv})"
                )

            prereqs_report.append({
                "bid": req_bid_str,
                "name": r_meta["name"],
                "name_ar": r_meta["name_ar"],
                "current_lv": curr_r_lv,
                "required_lv": int(req_lv),
                "fulfilled": fulfilled,
                "is_upgrading": is_r_upgrading,
                "current_display": format_level_display(req_bid_str, curr_r_lv),
                "required_display": format_level_display(req_bid_str, int(req_lv)),
            })

        # هـ. فحص أوسمة الحرب والأدوات المطلوبة (costWEs و costTools)
        items_report = []
        all_req_items = {**cost_wes, **cost_tools}
        for item_id_str, req_count in all_req_items.items():
            if req_count <= 0:
                continue
            item_id = int(item_id_str)
            item_meta = ITEM_INFO.get(item_id, {"name": f"أداة #{item_id}", "emoji": "📦"})
            current_count = bag_items.get(str(item_id), 0)
            fulfilled = current_count >= req_count
            diff = max(0, req_count - current_count)
            if not fulfilled:
                is_ready = False
                blocking_reasons.append(
                    f"نقص أدوات: {item_meta['name']} (المتوفر: {current_count:,} < المطلوب: {req_count:,})"
                )

            items_report.append({
                "item_id": item_id,
                "name": item_meta["name"],
                "emoji": item_meta["emoji"],
                "required": req_count,
                "current": current_count,
                "diff": diff,
                "fulfilled": fulfilled,
            })

        # و. فحص الموارد المطلوبة (costRes)
        res_report = []
        for resid_str, req_amt in cost_res.items():
            if req_amt <= 0:
                continue
            resid = int(resid_str)
            r_info = RES_INFO.get(resid, {"name": f"مورد #{resid}", "emoji": "📦"})
            # إجمالي الموارد = الرصيد العادي + الآمن
            curr_reg = float(reslist.get(str(resid), 0))
            curr_safe = float(saferes.get(str(resid), 0))
            curr_total = max(curr_reg, curr_safe, curr_reg + curr_safe)
            fulfilled = curr_total >= req_amt
            diff = max(0.0, req_amt - curr_total)
            if not fulfilled:
                is_ready = False
                blocking_reasons.append(
                    f"نقص موارد: {r_info['name']} (المتوفر: {int(curr_total):,} < المطلوب: {int(req_amt):,})"
                )

            res_report.append({
                "resid": resid,
                "name": r_info["name"],
                "emoji": r_info["emoji"],
                "required": req_amt,
                "current": curr_total,
                "diff": diff,
                "fulfilled": fulfilled,
            })

        result_data = {
            "success": True,
            "account": account_email,
            "building_id": bid,
            "building_name": b_name,
            "current_level": current_lv,
            "target_level": target_lv,
            "is_max_level": is_max_level,
            "is_already_upgrading": is_already_upgrading,
            "cost_time_seconds": cost_time,
            "cost_time_formatted": format_duration(cost_time),
            "is_ready": is_ready,
            "queues": queues_report,
            "prerequisites": prereqs_report,
            "items": items_report,
            "resources": res_report,
            "blocking_reasons": blocking_reasons,
        }

        # ═════════════════════════════════════════════════════════════
        #  الطباعة المرئية في الكونسول (Visual Report)
        # ═════════════════════════════════════════════════════════════
        if verbose:
            print("\n" + "═" * 74)
            print(f"🏰 فحص متطلبات ترقية المبنى: {b_name} (معرّف: {bid})")
            print(f"👤 الحساب: {account_email}")
            print("═" * 74)

            # حالة المبنى
            cur_display = format_level_display(bid, current_lv)
            tar_display = format_level_display(bid, target_lv)
            print(f"\n📊 المستوى الحالي  : {cur_display}")
            if not is_max_level:
                print(f"🎯 المستوى المستهدف: {tar_display}")
                print(f"⏳ وقت البناء الأساسي: {format_duration(cost_time)}")
            else:
                print(f"🏆 المبنى في أقصى مستوى ممكن ({max_lv}) ولا توجد ترقية تالية.")

            # حالة طوابير البناء
            print("\n" + "─" * 74)
            print(f"🔨 طوابير البناء ({active_count}/2 مشغولة):")
            if has_free_queue:
                print("  ✔️ يوجد طابور بناء حر ومتاح حالياً للترقية.")
            else:
                print("  ❌ طوابير البناء مشغولة بالكامل (2/2):")
            for q in queues_report["details"]:
                print(f"     • {q['name']} (مستوى {q['level']}) — ⏳ متبقي: {q['remain_formatted']}")

            # المباني المشروطة
            print("\n" + "─" * 74)
            print("📋 المتطلبات المسبقة للمباني (Prerequisites):")
            if prereqs_report:
                for pr in prereqs_report:
                    status_icon = "✔️" if pr["fulfilled"] else "❌"
                    up_tag = " [⏳ قيد الترقية حالياً]" if pr["is_upgrading"] else ""
                    print(
                        f"  {status_icon} {pr['name']} : {pr['required_display']} "
                        f"(الحالي: {pr['current_display']}){up_tag}"
                    )
            else:
                print("  ✔️ لا توجد مبانٍ مشروطة مسبقاً لهذا المستوى.")

            # الأدوات وأوسمة الحرب
            print("\n" + "─" * 74)
            print("💎 الأدوات وأوسمة الحرب المطلوبة (Items & War Medals):")
            if items_report:
                for it in items_report:
                    status_icon = "✔️" if it["fulfilled"] else "❌"
                    print(
                        f"  {status_icon} {it['emoji']} {it['name']}: "
                        f"المتوفر {it['current']:,} / المطلوب {it['required']:,}"
                    )
            else:
                print("  ✔️ لا يتطلب أدوات أو أوسمة حرب خاصة.")

            # الموارد
            print("\n" + "─" * 74)
            print("📦 الموارد المطلوبة (Resources):")
            if res_report:
                for rs in res_report:
                    status_icon = "✔️" if rs["fulfilled"] else "❌"
                    diff_str = f" [نقص: {int(rs['diff']):,}]" if not rs["fulfilled"] else ""
                    print(
                        f"  {status_icon} {rs['emoji']} {rs['name']}: "
                        f"المتوفر {int(rs['current']):,} / المطلوب {int(rs['required']):,}{diff_str}"
                    )
            else:
                print("  ✔️ لا يتطلب موارد لهذا المستوى.")

            # الحكم النهائي
            print("\n" + "═" * 74)
            if is_ready:
                print("🎉 النتيجة: المبنى جاهز 100% للترقية الفورية! كافة الشروط والموارد متوفرة.")
            else:
                print("⚠️ النتيجة: المبنى غير جاهز للترقية حالياً.")
                print("🛑 الأسباب المعيقة:")
                for i, reason in enumerate(blocking_reasons, 1):
                    print(f"   {i}. {reason}")
            print("═" * 74 + "\n")

        return result_data

    finally:
        if should_close_conn and conn:
            await conn.close()


# ════════════════════════════════════════════════════════════════════
#  سطر الأوامر المباشر (CLI Runner)
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check Building Upgrade Requirements — فحص متطلبات ترقية أي مبنى"
    )
    parser.add_argument(
        "--email", "-e",
        help="البريد الإلكتروني للحساب (إذا لم يُحدد يؤخذ أول حساب مسجل)"
    )
    parser.add_argument(
        "--building", "-b",
        default="102",
        help="معرف أو اسم المبنى المراد فحصه (مثال: 101, 102, walls, farm, hospital, 205)"
    )
    args = parser.parse_args()

    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد حسابات مسجلة في session_cache.json!")
        sys.exit(1)

    target_email = args.email or next(iter(accounts.keys()))
    if target_email not in accounts:
        print(f"❌ الحساب {target_email} غير موجود!")
        sys.exit(1)

    asyncio.run(check_building_upgrade(target_email, args.building, verbose=True))
