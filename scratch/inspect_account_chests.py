# -*- coding: utf-8 -*-
"""
inspect_account_chests.py — جرد صناديق الموارد الأربعة بدقة كاملة (العادية والآمنة)
══════════════════════════════════════════════════════════════════════════════════
القمح | الخشب | الحديد | الألماس
"""

from __future__ import annotations

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_CURRENT_DIR)
for p in [_CURRENT_DIR, _PARENT_DIR, r"e:\osmanli"]:
    if p not in sys.path:
        sys.path.insert(0, p)

import asyncio
import argparse
import logging
from typing import Any, Dict, List

from core.session_manager import SessionManager
from game_client import GameConnection

logging.getLogger("game_conn").setLevel(logging.WARNING)
logging.getLogger("game_client").setLevel(logging.WARNING)


# ════════════════════════════════════════════════════════════════════
#  تعريفات صناديق الموارد الرسمية في اللعبة (العادية + الآمنة)
# ════════════════════════════════════════════════════════════════════

# 1. القمح (Food)
FOOD_CHESTS_ALL = [
    # صناديق قمح عادية (100301 - 100308)
    {"id": 100301, "amount": 1000,    "name": "صندوق 1K قمح"},
    {"id": 100302, "amount": 10000,   "name": "صندوق 10K قمح"},
    {"id": 100303, "amount": 30000,   "name": "صندوق 30K قمح"},
    {"id": 100304, "amount": 50000,   "name": "صندوق 50K قمح"},
    {"id": 100305, "amount": 150000,  "name": "صندوق 150K قمح"},
    {"id": 100306, "amount": 500000,  "name": "صندوق 500K قمح"},
    {"id": 100307, "amount": 1500000, "name": "صندوق 1.5M قمح"},
    {"id": 100308, "amount": 5000000, "name": "صندوق 5M قمح"},
    # صناديق قمح آمنة (110101 - 110108)
    {"id": 110107, "amount": 1000,    "name": "صندوق 1K قمح (آمن)"},
    {"id": 110101, "amount": 10000,   "name": "صندوق 10K قمح (آمن)"},
    {"id": 110108, "amount": 30000,   "name": "صندوق 30K قمح (آمن)"},
    {"id": 110102, "amount": 50000,   "name": "صندوق 50K قمح (آمن)"},
    {"id": 110103, "amount": 150000,  "name": "صندوق 150K قمح (آمن)"},
    {"id": 110104, "amount": 500000,  "name": "صندوق 500K قمح (آمن)"},
    {"id": 110105, "amount": 1500000, "name": "صندوق 1.5M قمح (آمن)"},
    {"id": 110106, "amount": 5000000, "name": "صندوق 5M قمح (آمن)"},
]

# 2. الخشب (Wood)
WOOD_CHESTS_ALL = [
    # صناديق خشب عادية (100201 - 100208)
    {"id": 100201, "amount": 1000,    "name": "صندوق 1K خشب"},
    {"id": 100202, "amount": 10000,   "name": "صندوق 10K خشب"},
    {"id": 100203, "amount": 30000,   "name": "صندوق 30K خشب"},
    {"id": 100204, "amount": 50000,   "name": "صندوق 50K خشب"},
    {"id": 100205, "amount": 150000,  "name": "صندوق 150K خشب"},
    {"id": 100206, "amount": 500000,  "name": "صندوق 500K خشب"},
    {"id": 100207, "amount": 1500000, "name": "صندوق 1.5M خشب"},
    {"id": 100208, "amount": 5000000, "name": "صندوق 5M خشب"},
    # صناديق خشب آمنة (110001 - 110008)
    {"id": 110007, "amount": 1000,    "name": "صندوق 1K خشب (آمن)"},
    {"id": 110001, "amount": 10000,   "name": "صندوق 10K خشب (آمن)"},
    {"id": 110008, "amount": 30000,   "name": "صندوق 30K خشب (آمن)"},
    {"id": 110002, "amount": 50000,   "name": "صندوق 50K خشب (آمن)"},
    {"id": 110003, "amount": 150000,  "name": "صندوق 150K خشب (آمن)"},
    {"id": 110004, "amount": 500000,  "name": "صندوق 500K خشب (آمن)"},
    {"id": 110005, "amount": 1500000, "name": "صندوق 1.5M خشب (آمن)"},
    {"id": 110006, "amount": 5000000, "name": "صندوق 5M خشب (آمن)"},
]

# 3. الحديد (Iron) — العادية (100501-100508) + الآمنة (110201-110208)
IRON_CHESTS_ALL = [
    # صناديق حديد عادية (100501 - 100508)
    {"id": 100501, "amount": 150,     "name": "صندوق 150 حديد"},
    {"id": 100502, "amount": 1600,    "name": "صندوق 1.6K حديد"},
    {"id": 100503, "amount": 5000,    "name": "صندوق 5K حديد"},
    {"id": 100504, "amount": 8000,    "name": "صندوق 8K حديد"},
    {"id": 100505, "amount": 25000,   "name": "صندوق 25K حديد"},
    {"id": 100506, "amount": 80000,   "name": "صندوق 80K حديد"},
    {"id": 100507, "amount": 250000,  "name": "صندوق 250K حديد"},
    {"id": 100508, "amount": 800000,  "name": "صندوق 800K حديد"},
    # صناديق حديد آمنة (110201 - 110208)
    {"id": 110207, "amount": 150,     "name": "صندوق 150 حديد (آمن)"},
    {"id": 110201, "amount": 1600,    "name": "صندوق 1.6K حديد (آمن)"},
    {"id": 110208, "amount": 5000,    "name": "صندوق 5K حديد (آمن)"},
    {"id": 110202, "amount": 8000,    "name": "صندوق 8K حديد (آمن)"},
    {"id": 110203, "amount": 25000,   "name": "صندوق 25K حديد (آمن)"},
    {"id": 110204, "amount": 80000,   "name": "صندوق 80K حديد (آمن)"},
    {"id": 110205, "amount": 250000,  "name": "صندوق 250K حديد (آمن)"},
    {"id": 110206, "amount": 800000,  "name": "صندوق 800K حديد (آمن)"},
]

# 4. الألماس / الكوارتز (Quartz) — العادية (100600-100608) + الآمنة (110301-110308)
QUARTZ_CHESTS_ALL = [
    {"id": 100600, "amount": 40,     "name": "صندوق 40 ألماس"},
    {"id": 100601, "amount": 80,     "name": "صندوق 80 ألماس"},
    {"id": 100602, "amount": 160,    "name": "صندوق 160 ألماس"},
    {"id": 100603, "amount": 400,    "name": "صندوق 400 ألماس"},
    {"id": 100604, "amount": 2000,   "name": "صندوق 2K ألماس"},
    {"id": 100605, "amount": 6250,   "name": "صندوق 6.25K ألماس"},
    {"id": 100606, "amount": 20000,  "name": "صندوق 20K ألماس"},
    {"id": 100607, "amount": 62500,  "name": "صندوق 62.5K ألماس"},
    {"id": 100608, "amount": 200000, "name": "صندوق 200K ألماس"},
    # الآمنة
    {"id": 110307, "amount": 40,     "name": "صندوق 40 ألماس (آمن)"},
    {"id": 110308, "amount": 80,     "name": "صندوق 80 ألماس (آمن)"},
    {"id": 110301, "amount": 400,    "name": "صندوق 400 ألماس (آمن)"},
    {"id": 110302, "amount": 2000,   "name": "صندوق 2K ألماس (آمن)"},
    {"id": 110303, "amount": 6250,   "name": "صندوق 6.25K ألماس (آمن)"},
    {"id": 110304, "amount": 20000,  "name": "صندوق 20K ألماس (آمن)"},
    {"id": 110305, "amount": 62500,  "name": "صندوق 62.5K ألماس (آمن)"},
    {"id": 110306, "amount": 200000, "name": "صندوق 200K ألماس (آمن)"},
]


def print_resource_section(title: str, chest_defs: List[Dict[str, Any]], bag: Dict[str, int]) -> int:
    print(f"\n{title}")
    print("─" * 68)
    found_any = False
    total_yield = 0
    total_count = 0

    for ch in chest_defs:
        cid = str(ch["id"])
        cnt = bag.get(cid, 0)
        if cnt > 0:
            found_any = True
            y = cnt * ch["amount"]
            total_yield += y
            total_count += cnt
            print(f"   • [{cid}] {ch['name']:<28} : {cnt:>6,} صندوق  | يمنح: {y:>14,}")

    if not found_any:
        print("   ❌ لا توجد أي صناديق متوفرة لهذا المورد بالحقيبة.")
    else:
        print(f"   📊 المجموع: {total_count:,} صندوق  |  إجمالي المورد: {total_yield:,}")

    return total_yield


async def inspect_account(email: str) -> None:
    sm = SessionManager()
    accounts = sm.load()
    acc_obj = accounts.get(email)
    if not acc_obj:
        print(f"❌ الحساب {email} غير موجود!")
        return

    print("═" * 68)
    print(f"🔌 جاري جرد صناديق الحساب: {email}")
    print("═" * 68)

    conn = GameConnection(acc_obj)
    if not await conn.connect():
        print(f"❌ فشل الاتصال بخادم اللعبة للحساب {email}!")
        return

    for _ in range(15):
        await asyncio.sleep(0.3)
        if len(conn.init_data) > 0 and "cityCtrl" in conn.init_data:
            break

    try:
        city_ctrl = conn.init_data.get("cityCtrl", {})
        castle_lv = 0
        blist = city_ctrl.get("blist", [])
        if isinstance(blist, list):
            for b in blist:
                binfo = b.get("binfo", {}) if isinstance(b, dict) else {}
                if str(binfo.get("bid")) == "101":
                    castle_lv = int(binfo.get("lv", 0))
                    break

        # استعلام الحقيبة المباشر 1004/1
        bag: Dict[str, int] = {}
        try:
            resp_bag = await conn.query("1004", "1", {}, timeout=10)
            if resp_bag and isinstance(resp_bag, dict):
                bdata = resp_bag.get("data", {})
                if isinstance(bdata, dict):
                    for iid_str, ival in bdata.items():
                        if isinstance(ival, dict):
                            bag[str(iid_str)] = int(ival.get("count", 0))
                        elif isinstance(ival, (int, float)):
                            bag[str(iid_str)] = int(ival)
        except Exception:
            pass

        bp_ctrl = conn.init_data.get("backpackCtrl", {})
        if isinstance(bp_ctrl, dict):
            for iid_str, ival in bp_ctrl.items():
                if str(iid_str) not in bag:
                    if isinstance(ival, dict):
                        bag[str(iid_str)] = int(ival.get("count", 0))
                    elif isinstance(ival, (int, float, str)) and str(ival).isdigit():
                        bag[str(iid_str)] = int(ival)

        print(f"🏰 مستوى القلعة: المستوى {castle_lv}")

        # 1. القمح
        food_total = print_resource_section("🌾 1. صناديق القمح (Food):", FOOD_CHESTS_ALL, bag)

        # 2. الخشب
        wood_total = print_resource_section("🪵 2. صناديق الخشب (Wood):", WOOD_CHESTS_ALL, bag)

        # 3. الحديد (العادي والآمن!)
        iron_total = print_resource_section("⛏️ 3. صناديق الحديد (Iron) — العادية والآمنة:", IRON_CHESTS_ALL, bag)

        # 4. الألماس / الكوارتز
        diamond_status = "💎 4. صناديق الألماس (Diamond):"
        if castle_lv < 15:
            diamond_status += f" (ملاحظة: منجم الألماس غير مفتوح في المدينة بعد — يتطلب قلعة 15)"
        quartz_total = print_resource_section(diamond_status, QUARTZ_CHESTS_ALL, bag)

        print("\n" + "═" * 68)
        print("🏁 ملخص إجمالي الموارد في الصناديق المتوفرة بالحقيبة:")
        print(f"   • 🌾 القمح:   {food_total:>14,} قمح")
        print(f"   • 🪵 الخشب:   {wood_total:>14,} خشب")
        print(f"   • ⛏️ الحديد:  {iron_total:>14,} حديد")
        print(f"   • 💎 الألماس: {quartz_total:>14,} ألماس")
        print("═" * 68 + "\n")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="جرد صناديق الموارد الأربعة")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--list", "-l", action="store_true", help="عرض قائمة الحسابات")
    args = parser.parse_args()

    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد أي حسابات مسجلة!")
        sys.exit(1)

    if args.list:
        print("📋 قائمة الحسابات:")
        for idx, acc_email in enumerate(accounts.keys(), 1):
            print(f"   {idx}. {acc_email}")
        sys.exit(0)

    target_email = args.email or next(iter(accounts.keys()))
    if target_email not in accounts:
        print(f"❌ الحساب {target_email} غير موجود!")
        sys.exit(1)

    asyncio.run(inspect_account(target_email))
