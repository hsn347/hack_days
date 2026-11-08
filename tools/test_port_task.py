# -*- coding: utf-8 -*-
"""
tools/test_port_task.py — أداة تشغيل واختبار مهمة الميناء (PortTask) على حساب محدد
══════════════════════════════════════════════════════════════════════════════════

تشغيل واختبار مهمة الميناء التجاري (tasks/port.py) على أي حساب مسجل
في database/session_cache.json دون أي تعديل على ملف المهمة الأصلي.

أمثلة الاستخدام:
  1. استعراض قائمة الحسابات المسجلة:
     python tools/test_port_task.py --list-accounts

  2. فحص حالة سفينة الميناء في الذاكرة الحية فقط (دون تنفيذ أو استلام):
     python tools/test_port_task.py king7moe --check-only

  3. تشغيل مهمة الميناء واستلام السفينة مباشرة:
     python tools/test_port_task.py king7moe

  4. استخدام البريد الكامل أو جزء منه:
     python tools/test_port_task.py burcudemr@gmail.com
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

CACHE_FILE = os.path.join(WORKSPACE_DIR, "database", "session_cache.json")

from game_client import GameConnection, AccountSession
from tasks.port import PortTask


def load_session_accounts() -> Dict[str, Dict[str, Any]]:
    """تحميل الحسابات المسجلة من session_cache.json"""
    if not os.path.exists(CACHE_FILE):
        print(f"❌ لم يتم العثور على ملف الجلسات: {CACHE_FILE}")
        sys.exit(1)

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        cache = json.load(f)

    return cache.get("accounts", {})


def find_matching_account(query: str, accounts: Dict[str, Dict[str, Any]]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """البحث عن حساب بالبريد الكامل أو جزء منه"""
    q_lower = query.lower().strip()
    # 1. مطابقة دقيقة
    for email, info in accounts.items():
        if email.lower() == q_lower:
            return email, info

    # 2. مطابقة جزئية
    matches = [(email, info) for email, info in accounts.items() if q_lower in email.lower()]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"⚠️ وُجد أكثر من حساب يطابق '{query}':")
        for em, _ in matches[:10]:
            print(f"   - {em}")
        print("يرجى تحديد البريد بدقة أكبر.")
        return None

    return None


def print_port_memory_state(init_data: Dict[str, Any], title: str = "حالة الميناء في الذاكرة الحية"):
    """قراءة وتنسيق حالة timeRewardCtrl من الذاكرة الحية"""
    tr = init_data.get("timeRewardCtrl", {})
    tr_data = tr.get("data", tr) if isinstance(tr, dict) else {}

    print(f"\n⚓ ─── {title} ───")
    if not tr_data:
        print("  ⚠️ بيانات timeRewardCtrl غير متوفرة بعد في الذاكرة.")
        return

    is_all = int(tr_data.get("isAllReceive", 0))
    is_rcv = int(tr_data.get("isReceive", 0))
    seq = tr_data.get("sequence", "?")
    rec_time = float(tr_data.get("receiveTime", 0))
    reward = tr_data.get("reward", [])
    now_ts = time.time()

    # تنسيق الحالة
    if is_all == 1:
        status_str = "✅ تم استلام جميع سفن الميناء لهذا اليوم بالكامل."
    elif is_rcv == 1 or (rec_time > 0 and now_ts >= rec_time):
        status_str = "🎁 السفينة وصلت والجائزة جاهزة للاستلام فوراً!"
    else:
        rem = max(0, int(rec_time - now_ts))
        mins, secs = divmod(rem, 60)
        status_str = f"⏳ السفينة في الطريق (متبقي {mins} دقيقة و {secs} ثانية - توقيت: {int(rec_time)})"

    print(f"  • رقم السفينة الحالية (sequence) : {seq}")
    print(f"  • حالة الاستلام (isReceive)        : {is_rcv}")
    print(f"  • استلام الكل (isAllReceive)       : {is_all}")
    print(f"  • موعد الوصول (receiveTime)        : {int(rec_time)}")
    print(f"  • الجائزة المحمولة (reward)        : {reward}")
    print(f"  • الخلاصة                         : {status_str}")


async def run_port_test(account_email: str, account_info: Dict[str, Any], check_only: bool = False):
    """الاتصال بالحساب وتنفيذ اختبار مهمة الميناء"""
    print("=" * 70)
    print(f"🏰 الحساب المستهدف : {account_email}")
    print(f"🎯 المهمة المطلوبة : مهمة الميناء التجاري (tasks/port.py)")
    print(f"⚙️  وضع التشغيل    : {'🔍 فحص الذاكرة فقط (Check-Only)' if check_only else '🚀 تشغيل المهمة واستلام السفينة (Execute)'}")
    print("=" * 70)

    account_sess = AccountSession(
        email=account_email,
        user_id=account_info["userId"],
        session_id=account_info["sessionId"]
    )

    print("⏳ جاري تسجيل الدخول والاتصال بـ Gate السيرفر...")
    conn = GameConnection(account_sess)
    try:
        connected = await asyncio.wait_for(conn.connect(), timeout=15.0)
        if not connected:
            print("❌ فشل الاتصال بالسيرفر! يرجى التحقق من صحة الجلسة أو الشبكة.")
            return

        print(f"✅ تم الاتصال بنجاح بـ Gate السيرفر! (UID: {conn.uid})")
        print("⏳ بانتظار مزامنة الذاكرة الحية الأولية من السيرفر...")

        for _ in range(40):
            if "timeRewardCtrl" in getattr(conn, "init_data", {}):
                break
            await asyncio.sleep(0.15)

        # 1. عرض حالة الميناء قبل التنفيذ
        print_port_memory_state(conn.init_data, "حالة الميناء الحالية في الذاكرة الحية (قبل التشغيل)")

        if check_only:
            print("\n✨ تم إنهاء الفحص بنجاح بدون إرسال أي أوامر استلام.")
            return

        # 2. إنشاء كائن PortTask وتشغيله مباشرة دون أي تعديل على ملف المهمة
        print("\n🚀 بدء تنفيذ PortTask(conn).run() ...")
        start_t = time.perf_counter()

        port_task = PortTask(conn, {"enabled": True, "ship_type": 0})
        res = await port_task.run()

        elapsed = time.perf_counter() - start_t

        print("\n" + "=" * 70)
        if res.success:
            print(f"🎉 نتيجة المهمة : ناجحة ({elapsed:.2f} ثانية)")
            print(f"💬 الرسالة     : {res.message}")
        else:
            print(f"⚠️ نتيجة المهمة : تنبيه / لم تنجح ({elapsed:.2f} ثانية)")
            print(f"💬 الرسالة     : {res.message}")
        if res.data:
            print(f"📦 البيانات    : {res.data}")
        print("=" * 70)

        # 3. عرض حالة الميناء في الذاكرة الحية بعد التنفيذ
        print_port_memory_state(conn.init_data, "حالة الميناء في الذاكرة الحية (بعد التنفيذ)")

    except Exception as e:
        print(f"\n❌ حدث استثناء أثناء التشغيل: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn and hasattr(conn, "close"):
            try:
                await conn.close()
                print("\n🔌 تم إغلاق الاتصال بأمان.")
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="أداة تجربة وتشغيل مهمة الميناء على حساب معين")
    parser.add_argument("account", nargs="?", help="البريد الإلكتروني للحساب أو جزء منه")
    parser.add_argument("--list-accounts", action="store_true", help="استعراض قائمة الحسابات المتاحة")
    parser.add_argument("--check-only", action="store_true", help="فحص وعرض حالة سفينة الميناء في الذاكرة فقط دون استلام")

    args = parser.parse_args()

    accounts = load_session_accounts()

    if args.list_accounts:
        print("=" * 70)
        print(f"📋 قائمة الحسابات المتوفرة في session_cache.json ({len(accounts)} حساب):")
        print("=" * 70)
        for idx, (email, info) in enumerate(sorted(accounts.items()), 1):
            uid = info.get("userId", "")[:12]
            print(f"  {idx:2d}. {email} (User ID: {uid}...)")
        print("=" * 70)
        return

    if not args.account:
        print("❌ يرجى تحديد بريد الحساب المستهدف!")
        print("💡 مثال: python tools/test_port_task.py king7moe")
        print("💡 أو استعرض الحسابات: python tools/test_port_task.py --list-accounts")
        sys.exit(1)

    matched = find_matching_account(args.account, accounts)
    if not matched:
        print(f"❌ لم يتم العثور على أي حساب يطابق: '{args.account}'")
        sys.exit(1)

    target_email, target_info = matched
    asyncio.run(run_port_test(target_email, target_info, check_only=args.check_only))


if __name__ == "__main__":
    main()

