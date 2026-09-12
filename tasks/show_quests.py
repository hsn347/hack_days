# -*- coding: utf-8 -*-
"""
tasks/show_quests.py — عرض جميع مهام المجد والمهام اليومية وحالتها ونسبة إنجازها والمتبقي
"""

import sys
import os
import asyncio
import json
import argparse

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.session_manager import SessionManager
from game_client import GameConnection

STATUS_NAMES = {
    1: "⏳ قيد التحضير",
    2: "🏃 قيد الإنجاز",
    3: "⏳ قيد المعالجة",
    4: "✅ مكتملة (جاهزة للاستلام!)",
    5: "🎁 تم الاستلام مسبقاً"
}

async def display_quests(email: str):
    sm = SessionManager()
    accounts = sm.load()
    acc = accounts.get(email)
    if not acc:
        print(f"❌ الحساب {email} غير موجود في session_cache.json!")
        return

    print(f"\n📡 جارٍ الاتصال بالحساب: {email}...")
    conn = GameConnection(acc)
    if not await conn.connect():
        print("❌ فشل الاتصال بالسيرفر!")
        return

    # انتظار استلام meritoriousTaskCtrl
    for _ in range(15):
        await asyncio.sleep(0.2)
        if "meritoriousTaskCtrl" in conn.init_data:
            break

    merit = conn.init_data.get("meritoriousTaskCtrl", {})
    if not merit:
        print("⚠️ لم يتم العثور على بيانات meritoriousTaskCtrl!")
        await conn.close()
        return

    merit_lv = merit.get("meritLv", 0)
    merit_exp = merit.get("meritExp", 0)
    daily_point = merit.get("dailyPoint", 0)
    task_data = merit.get("taskData", {})
    daily_boxes = merit.get("dailyBoxRwd", {})

    print("\n" + "═" * 75)
    print(f"🎖️  بيانات المجد: المستوى: {merit_lv} | نقاط المجد: {merit_exp:,} | نقاط النشاط اليومي: {daily_point}")
    print(f"🎁 الصناديق اليومية المستلمة اليوم: {list(daily_boxes.keys()) if daily_boxes else 'لا يوجد'}")
    print("═" * 75)

    print(f"\n📋 إجمالي المهام المسجلة في السيرفر: {len(task_data)} مهمة\n")

    ready_tasks = []
    in_progress = []
    finished_tasks = []

    for tid, t in task_data.items():
        st = t.get("status", 2)
        if st == 4:
            ready_tasks.append(t)
        elif st == 2:
            in_progress.append(t)
        else:
            finished_tasks.append(t)

    # 1. المهام الجاهزة للاستلام
    if ready_tasks:
        print(f"🎉 ───【 مهام مكتملة وجاهزة للاستلام فوراً: {len(ready_tasks)} 】───")
        for t in ready_tasks:
            dynamic_id = t.get("dynamicId")
            c_num = t.get("cNum", 0)
            l_num = t.get("lNum", 0)
            t_id = t.get("id")
            print(f"  ✨ [مهمة #{t_id}] dynamicId: {dynamic_id:<5} | الإنجاز: {c_num}/{l_num} (100%) | الحالة: ✅ مكتملة")
        print()

    # 2. المهام قيد الإنجاز
    if in_progress:
        print(f"⏳ ───【 مهام قيد الإنجاز (كم متبقي لتكتمل): {len(in_progress)} 】───")
        for t in in_progress:
            dynamic_id = t.get("dynamicId")
            c_num = t.get("cNum", 0)
            l_num = t.get("lNum", 0)
            remaining = max(0, l_num - c_num)
            pct = (c_num / l_num * 100) if l_num > 0 else 0
            t_id = t.get("id")
            print(f"  🔹 [مهمة #{t_id}] dynamicId: {dynamic_id:<5} | تم: {c_num:<6} / مطلوب: {l_num:<6} | ⏳ باقي: {remaining:<6} ({pct:.1f}%)")
        print()

    # 3. ملخص المهام
    print("═" * 75)
    print(f"📌 ملخص: مكتمل وجاهز: {len(ready_tasks)} | قيد الإنجاز: {len(in_progress)} | مستلم مسبقاً: {len(finished_tasks)}")
    print("═" * 75 + "\n")

    await conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="عرض تفاصيل المهام وحالتها")
    parser.add_argument("--email", type=str, help="البريد الإلكتروني للحساب")
    args = parser.parse_args()

    sm = SessionManager()
    accounts = sm.load()
    email = args.email or (next(iter(accounts.keys())) if accounts else None)
    if not email:
        print("❌ لا توجد حسابات مسجلة!")
        sys.exit(1)

    asyncio.run(display_quests(email))
