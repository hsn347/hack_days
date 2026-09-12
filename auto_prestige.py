# -*- coding: utf-8 -*-
"""
auto_prestige.py — مشغل مهام الهيبة اليومية التلقائي المستقل (Prestige Quests Daily Runner)
══════════════════════════════════════════════════════════════════════════════════════════
برنامج تشغيل مستقل ومباشر لمهام الهيبة اليومية (Prestige Quests):
  1. متجر المهربين (Smuggler Store / Traveling Merchant):
     • شراء البضائع بالموارد العادية حصراً (طعام، خشب، حديد، فضة).
     • حظر استخدام الذهب نهائياً (0 ذهب).
  2. جمع الموارد الأربعة خارج القلعة (4 Resource Gathering Marches):
     • إرسال مسيرة واحدة مؤكدة لكل مورد (قمح، خشب، حجر، حديد).
     • تثبيت قيمة جمع الموارد المستهدفة على: currentSourceNum = 25000.
     • اختيار جيش كافٍ لحمل الـ 25,000 مورد فقط دون استنزاف باقي جيش القلعة.
     • اختيار البطل والحيوان المتاحين تلقائياً.
  3. استعراض تقدم نقاط الهيبة وصناديق الجوائز اليومية.

أمثلة التشغيل:
  python auto_prestige.py --email "fahed.K140@gmail.com" --password "mn@123450"
  python auto_prestige.py --email "user@gmail.com"
  python auto_prestige.py
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

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

import argparse
import asyncio
import logging
from core.session_manager import SessionManager
from game_client import GameConnection, AccountSession
from tasks.prestige import PrestigeTask
from auto_elf_boss import sdk_login

# ── إعداد نظام التسجيل ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("auto_prestige")


async def run_prestige_flow(
    email: str,
    password: str = None,
    search_range: int = 120,
    target_buys: int = 10,
    invaders_count: int = 5,
    invaders_min_lv: int = 1,
    invaders_max_lv: int = 30,
    invaders_range: int = 80,
    invaders_x: int = None,
    invaders_y: int = None,
    strongholds_count: int = 2,
    strongholds_min_lv: int = 1,
    strongholds_max_lv: int = 30,
    strongholds_range: int = 80,
):
    sm = SessionManager()
    accounts = sm.load()
    acc = None

    if password:
        log.info(f"🔐 جاري تسجيل الدخول المباشر سحابياً عبر ONEMT للحساب: {email}...")
        auth_res = await asyncio.to_thread(sdk_login, email, password)
        if auth_res.get("success"):
            acc = AccountSession(email=email, user_id=auth_res["userId"], session_id=auth_res["sessionId"])
            log.info(f"✅ تم التوثيق المباشر بنجاح! UID={auth_res['userId']}")
        else:
            log.error(f"❌ فشل تسجيل الدخول بكلمة المرور: {auth_res.get('error_msg')}")
            return

    if not acc:
        acc = accounts.get(email)

    if not acc:
        log.error(f"❌ لم يتم العثور على جلسة أو كلمة مرور للحساب {email}!")
        return

    conn = GameConnection(acc)
    log.info(f"📡 جاري الاتصال ببوابة اللعبة للحساب: {email}...")
    if not await conn.connect():
        log.error("❌ تعذر الاتصال ببوابة اللعبة حالياً!")
        return

    # انتظار استلام حزم بيانات القلعة ومهام الهيبة
    for _ in range(15):
        await asyncio.sleep(0.3)
        if "cityCtrl" in conn.init_data and "meritoriousTaskCtrl" in conn.init_data:
            break
    await asyncio.sleep(0.5)

    prestige_config = {
        "search_range": search_range,
        "smuggler_buys": target_buys,
        "invaders_count": invaders_count,
        "invaders_min_lv": invaders_min_lv,
        "invaders_max_lv": invaders_max_lv,
        "invaders_range": invaders_range,
        "invaders_x": invaders_x,
        "invaders_y": invaders_y,
        "stronghold_count": strongholds_count,
        "stronghold_min_lv": strongholds_min_lv,
        "stronghold_max_lv": strongholds_max_lv,
        "stronghold_range": strongholds_range,
    }

    task = PrestigeTask(conn, prestige_config)
    result = await task.run()

    print("\n" + "═" * 70)
    print("  📊 ملخص نتائج مهام الهيبة اليومية:")
    print(f"     • النتيجة: {result.message}")
    if result.data:
        buys = result.data.get("smuggler_buys", 0)
        sm_skip = result.data.get("smuggler_skipped", False)
        inv = result.data.get("invaders_attacks", 0)
        inv_skip = result.data.get("invaders_skipped", False)
        sh = result.data.get("stronghold_attacks", 0)
        sh_skip = result.data.get("stronghold_skipped", False)
        marches = result.data.get("gather_marches", 0)
        gather_skip = result.data.get("gather_skipped", False)

        buys_str = "✨ متخطى (مكتمل مسبقاً)" if sm_skip else f"{buys}/{target_buys} سلعة"
        inv_str = "✨ متخطى (مكتمل مسبقاً)" if inv_skip else f"{inv}/{invaders_count} هجمات"
        sh_str = "✨ متخطى (مكتمل مسبقاً)" if sh_skip else f"{sh}/{strongholds_count} معاقل"
        gather_str = "✨ متخطى (مكتمل مسبقاً)" if gather_skip else f"{marches} مسيرة بـ 25k مورد"

        print(f"     • متجر المهربين (بالموارد): {buys_str}")
        print(f"     • هجمات الغزاة (Invaders - حتى لفل {invaders_max_lv}): {inv_str}")
        print(f"     • هجمات المعاقل / الملاجئ (Strongholds): {sh_str}")
        print(f"     • مسيرات جمع الموارد الأربعة (25k مورد): {gather_str}")
    print("═" * 70 + "\n")

    await conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Auto Prestige Runner — مشغل مهام الهيبة اليومية التلقائي"
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب")
    parser.add_argument("--password", "-p", help="كلمة المرور للحساب للتسجيل المباشر بدون ملفات")
    parser.add_argument("--buys", "-b", type=int, default=10, help="عدد المشتريات المستهدفة من متجر المهربين [افتراضي: 10]")
    parser.add_argument("--invaders", "-i", type=int, default=5, help="عدد هجمات الغزاة المستهدفة [افتراضي: 5]")
    parser.add_argument("--inv-minlv", type=int, default=1, help="أدنى مستوى للغزاة [افتراضي: 1]")
    parser.add_argument("--inv-maxlv", type=int, default=30, help="أقصى مستوى للغزاة يحدده المستخدم [افتراضي: 30]")
    parser.add_argument("--inv-range", type=int, default=80, help="نطاق البحث عن الغزاة [افتراضي: 80]")
    parser.add_argument("-x", type=int, default=None, help="إحداثي X لمنطقة الغزاة [افتراضي: موقع القلعة]")
    parser.add_argument("-y", type=int, default=None, help="إحداثي Y لمنطقة الغزاة [افتراضي: موقع القلعة]")
    parser.add_argument("--strongholds", "-s", type=int, default=2, help="عدد المعاقل/الملاجئ المستهدفة [افتراضي: 2]")
    parser.add_argument("--sh-minlv", type=int, default=1, help="أدنى مستوى للمعقل [افتراضي: 1]")
    parser.add_argument("--sh-maxlv", type=int, default=30, help="أقصى مستوى للمعقل [افتراضي: 30]")
    parser.add_argument("--sh-range", type=int, default=80, help="نطاق البحث عن المعاقل [افتراضي: 80]")
    parser.add_argument("--range", type=int, default=120, help="نطاق البحث عن حقول الموارد بالكيلومتر [افتراضي: 120]")
    args = parser.parse_args()

    sm = SessionManager()
    accounts = sm.load()

    target_email = args.email
    if not target_email:
        if "fahed.K140@gmail.com" in accounts:
            target_email = "fahed.K140@gmail.com"
        elif accounts:
            target_email = next(iter(accounts.keys()))
        else:
            try:
                target_email = input("📧 أدخل البريد الإلكتروني للحساب: ").strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)

    try:
        asyncio.run(run_prestige_flow(
            email=target_email,
            password=args.password,
            search_range=args.range,
            target_buys=args.buys,
            invaders_count=args.invaders,
            invaders_min_lv=args.inv_minlv,
            invaders_max_lv=args.inv_maxlv,
            invaders_range=args.inv_range,
            invaders_x=args.x,
            invaders_y=args.y,
            strongholds_count=args.strongholds,
            strongholds_min_lv=args.sh_minlv,
            strongholds_max_lv=args.sh_maxlv,
            strongholds_range=args.sh_range,
        ))
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف البرنامج من قبل المستخدم.")


if __name__ == "__main__":
    main()
