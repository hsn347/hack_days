# -*- coding: utf-8 -*-
"""
check_optional_chests.py — فحص وجرد صناديق الموارد الاختيارية (809601 - 809605) في القلعة
══════════════════════════════════════════════════════════════════════════════════════
الاستخدام:
    python check_optional_chests.py <email>
    python check_optional_chests.py --email "johan2003@yopmail.com"
    python check_optional_chests.py --list
"""

import asyncio
import argparse
import os
import sys
from typing import Dict, Any, List

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.session_manager import SessionManager
from game_client import GameConnection

# المعجم الرسمي لصناديق الموارد الاختيارية بمستوياتها الخمسة (مستخرج من Lua سورس)
OPTIONAL_CHESTS_SPEC = [
    {
        "item_id": 809605,
        "level": 5,
        "name": "صندوق الموارد إختياري مستوي 5",
        "wood": 5000000,
        "food": 5000000,
        "iron": 800000,
        "quartz": 200000,
    },
    {
        "item_id": 809604,
        "level": 4,
        "name": "صندوق الموارد إختياري مستوي 4",
        "wood": 1500000,
        "food": 1500000,
        "iron": 250000,
        "quartz": 62500,
    },
    {
        "item_id": 809603,
        "level": 3,
        "name": "صندوق الموارد إختياري مستوي 3",
        "wood": 500000,
        "food": 500000,
        "iron": 80000,
        "quartz": 20000,
    },
    {
        "item_id": 809602,
        "level": 2,
        "name": "صندوق الموارد إختياري مستوي 2",
        "wood": 150000,
        "food": 150000,
        "iron": 25000,
        "quartz": 6250,
    },
    {
        "item_id": 809601,
        "level": 1,
        "name": "صندوق الموارد إختياري مستوي 1",
        "wood": 50000,
        "food": 50000,
        "iron": 8000,
        "quartz": 2000,
    },
]

# صندوق التسريعات الاختياري الإضافي
OPTIONAL_SPEEDUP_CHEST = {
    "item_id": 809701,
    "name": "صندوق التسريعات الإختياري (2 ساعة)",
    "hours_per_unit": 2,
}


async def inspect_optional_chests(email: str) -> None:
    sm = SessionManager()
    accounts = sm.load()
    
    # مطابقة غير حساسة لحالة الأحرف
    acc_obj = accounts.get(email)
    if not acc_obj:
        for em, obj in accounts.items():
            if em.lower() == email.lower():
                email = em
                acc_obj = obj
                break

    if not acc_obj:
        print(f"❌ خطأ: الحساب '{email}' غير موجود في مسجل الجلسات (session_cache.json).")
        return

    print("\n" + "═" * 76)
    print(f"🔍 جاري فحص صناديق الموارد الاختيارية للحساب: {email}")
    print("═" * 76)

    conn = GameConnection(acc_obj)
    if not await conn.connect():
        print(f"❌ فشل الاتصال بخادم اللعبة للحساب: {email}")
        return

    # انتظار استلام بيانات البداية init_data
    for _ in range(15):
        await asyncio.sleep(0.3)
        if len(conn.init_data) > 0 and "cityCtrl" in conn.init_data:
            break

    try:
        city_ctrl = conn.init_data.get("cityCtrl", {})
        lord_ctrl = conn.init_data.get("lordCtrl", {})
        lord_name = lord_ctrl.get("name", "غير معروف")
        
        castle_lv = 0
        blist = city_ctrl.get("blist", [])
        if isinstance(blist, list):
            for b in blist:
                binfo = b.get("binfo", {}) if isinstance(b, dict) else {}
                if str(binfo.get("bid")) == "101":
                    castle_lv = int(binfo.get("lv", 0))
                    break

        print(f"🏰 الحاكم: {lord_name} | مستوى القلعة: {castle_lv}")
        print("📦 جاري استعلام محتويات الحقيبة (1004/1)...")

        # استعلام الحقيبة المباشر
        bag: Dict[str, int] = {}
        try:
            resp_bag = await conn.query("1004", "1", {}, timeout=8)
            if resp_bag and isinstance(resp_bag, dict):
                bdata = resp_bag.get("data", {})
                if isinstance(bdata, dict):
                    for iid_str, ival in bdata.items():
                        if isinstance(ival, dict):
                            bag[str(iid_str)] = int(ival.get("count", 0))
                        elif isinstance(ival, (int, float)):
                            bag[str(iid_str)] = int(ival)
        except Exception as e:
            print(f"⚠️ تعذر استعلام الحقيبة المباشر عبر 1004/1: {e}")

        # دعم init_data كإسناد احتياطي
        bp_ctrl = conn.init_data.get("backpackCtrl", {})
        if isinstance(bp_ctrl, dict):
            for iid_str, ival in bp_ctrl.items():
                if str(iid_str) not in bag:
                    if isinstance(ival, dict):
                        bag[str(iid_str)] = int(ival.get("count", 0))
                    elif isinstance(ival, (int, float, str)) and str(ival).isdigit():
                        bag[str(iid_str)] = int(ival)

        print("-" * 76)
        print("📋 تقرير صناديق الموارد الاختيارية المتوفرة (من مستوى 5 إلى مستوى 1):")
        print("-" * 76)

        total_optional_count = 0
        potential_wood = 0
        potential_food = 0
        potential_iron = 0
        potential_quartz = 0

        found_any = False
        for spec in OPTIONAL_CHESTS_SPEC:
            cid = spec["item_id"]
            lvl = spec["level"]
            name = spec["name"]
            cnt = bag.get(str(cid), 0)

            if cnt > 0:
                found_any = True
                total_optional_count += cnt
                w_tot = cnt * spec["wood"]
                f_tot = cnt * spec["food"]
                i_tot = cnt * spec["iron"]
                q_tot = cnt * spec["quartz"]

                potential_wood += w_tot
                potential_food += f_tot
                potential_iron += i_tot
                potential_quartz += q_tot

                print(f"  ⭐ [مستوى {lvl}] {name} (ID: {cid}):")
                print(f"      • المتوفر بالحقيبة: {cnt:,} صندوق")
                print(f"      • قيمة الحبة الواحدة: خشب {spec['wood']:,} | قمح {spec['food']:,} | حديد {spec['iron']:,} | كوارتز {spec['quartz']:,}")
                print(f"      • إذا حُول لإجمالي خشب : +{w_tot:,} خشب")
                print(f"      • إذا حُول لإجمالي قمح  : +{f_tot:,} قمح")
                print(f"      • إذا حُول لإجمالي حديد : +{i_tot:,} حديد")
                print(f"      • إذا حُول لإجمالي كوارتز: +{q_tot:,} كوارتز")
                print()
            else:
                print(f"  ▫️ [مستوى {lvl}] {name} (ID: {cid}): 0 صندوق (غير متوفر)")

        print("-" * 76)
        if not found_any:
            print("⚠️ النتيجة: لا توجد أي صناديق موارد اختيارية (809601 - 809605) متوفرة في حقيبة هذا الحساب.")
        else:
            print("📊 ملخص الاحتياطي الاستراتيجي (في حال تحويل كامل الصناديق المتوفرة لمورد معين):")
            print(f"   • إجمالي عدد الصناديق الاختيارية: {total_optional_count:,} صندوق")
            print(f"   • الحد الأقصى للخشب المحتمل : {potential_wood:>14,} خشب")
            print(f"   • الحد الأقصى للقمح المحتمل  : {potential_food:>14,} قمح")
            print(f"   • الحد الأقصى للحديد المحتمل : {potential_iron:>14,} حديد")
            print(f"   • الحد الأقصى للكوارتز المحتمل: {potential_quartz:>14,} كوارتز")

        # فحص صندوق التسريعات الاختياري الإضافي
        sp_id = OPTIONAL_SPEEDUP_CHEST["item_id"]
        sp_cnt = bag.get(str(sp_id), 0)
        print("-" * 76)
        print("⚡ فحص صندوق التسريعات الاختياري (809701):")
        if sp_cnt > 0:
            sp_hours = sp_cnt * OPTIONAL_SPEEDUP_CHEST["hours_per_unit"]
            print(f"   • متوفر: {sp_cnt:,} صندوق ({sp_hours:,} ساعة تسريع اختيارية)")
        else:
            print("   • غير متوفر بالحقيبة (0 صندوق)")

        print("═" * 76 + "\n")

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="فحص وجرد صناديق الموارد الاختيارية (809601 - 809605)")
    parser.add_argument("email_pos", nargs="?", help="بريد الحساب المستهدف")
    parser.add_argument("--email", "-e", help="بريد الحساب المستهدف")
    parser.add_argument("--list", "-l", action="store_true", help="عرض قائمة الحسابات المسجلة")
    args = parser.parse_args()

    sm = SessionManager()
    accounts = sm.load()
    if not accounts:
        print("❌ لا توجد أي حسابات مسجلة في session_cache.json!")
        sys.exit(1)

    if args.list:
        print("\n📋 الحسابات المتاحة:")
        for idx, em in enumerate(accounts.keys(), 1):
            print(f"   {idx}. {em}")
        print()
        sys.exit(0)

    target_email = args.email or args.email_pos
    if not target_email:
        print("\n💡 لم يتم تحديد بريد إلكتروني. يمكنك تمرير البريد كمعامل، مثلاً:")
        print("   python check_optional_chests.py johan2003@yopmail.com")
        print("\nالحسابات المتاحة حالياً:")
        account_keys = list(accounts.keys())
        for idx, em in enumerate(account_keys, 1):
            print(f"   {idx}. {em}")
        
        try:
            choice = input("\nاختر رقم الحساب أو أدخل البريد مباشرة: ").strip()
            if not choice:
                print("❌ تم الإلغاء.")
                sys.exit(1)
            if choice.isdigit() and 1 <= int(choice) <= len(account_keys):
                target_email = account_keys[int(choice) - 1]
            else:
                target_email = choice
        except (KeyboardInterrupt, EOFError):
            print("\n❌ تم الإلغاء.")
            sys.exit(1)

    asyncio.run(inspect_optional_chests(target_email))


if __name__ == "__main__":
    main()
