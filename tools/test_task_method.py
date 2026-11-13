# -*- coding: utf-8 -*-
"""
tools/test_task_method.py — أداة تجربة واختبار دوال المهام على حسابات session_cache.json
══════════════════════════════════════════════════════════════════════════════════════

أداة لاختبار أي دالة (مثل get_castle_coords, get_kingdom_id, get_available_troops, إلخ)
على أي قلعة من المسجلة في database/session_cache.json وعرض مخرجاتها فوراً.

أمثلة الاستخدام:
  1. اختبار دالة إحداثيات القلعة:
     python tools/test_task_method.py burcudemr@gmail.com _get_castle_army

  2. اختبار دالة معرف المملكة:
     python tools/test_task_method.py shook124 get_formation

  3. اختبار دالة القوات المتوفرة بالقلعة:
     python tools/test_task_method.py jzarco.all get_combat_heroes

  4. اختبار سعة الفيالق القصوى:
     python tools/test_task_method.py jzarco.all get_available_marches_count

  5. اختبار سريع بدون اتصال (Offline) باستخدام ملفات docs/:
     python tools/test_task_method.py shook123 get_available_troops --offline

  6. استعراض الحسابات أو الدوال المتاحة:
     python tools/test_task_method.py --list-accounts
     python tools/test_task_method.py --list-methods
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
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

# ضبط المسار الرئيسي للمشروع
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

CACHE_FILE = os.path.join(WORKSPACE_DIR, "database", "session_cache.json")
DOCS_DIR = os.path.join(WORKSPACE_DIR, "docs")

from game_client import GameConnection, AccountSession
from tasks.base_task import BaseTask
from tasks.stronghold import StrongholdTask


# كلاس اتصال وهمي للاختبار في وضع Offline
class OfflineMockConnection:
    def __init__(self, email: str, uid: Any, init_data: Dict[str, Any]):
        self.account = type("MockAccount", (), {"email": email})()
        self.uid = uid
        self.is_connected = True
        self.init_data = init_data
        self.kingdom_id = None
        self.local_queues = []
        self.cached_packets = {}

    async def query(self, cmd: str, sub: str, data: Any = None, timeout: float = 3.0):
        return {}


def load_session_accounts() -> Dict[str, Dict[str, Any]]:
    """تحميل حسابات الجلسات من session_cache.json"""
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


def get_available_methods(cls: Any) -> List[str]:
    """استخراج الدوال العامة المتاحة في الكلاس"""
    methods = []
    for name in dir(cls):
        if name.startswith("_"):
            continue
        attr = getattr(cls, name)
        if callable(attr):
            methods.append(name)
    # إضافة دوال البداية المفيدة
    extra_useful = [
        "get_castle_coords",
        "get_kingdom_id",
        "get_available_troops",
        "get_max_marches_capacity",
        "get_active_marches_count",
        "get_available_marches_count",
        "get_formation",
        "get_combat_heroes",
        "select_combat_pet",
        "get_rune_pages",
        "get_march_army",
    ]
    for m in extra_useful:
        if hasattr(cls, m) and m not in methods:
            methods.append(m)
    return sorted(methods)


def find_offline_memory_file(email: str) -> Optional[str]:
    """البحث عن ملف ذاكرة حية محفوظ مسبقاً في docs/"""
    name_prefix = email.split("@")[0].lower()
    if os.path.exists(DOCS_DIR):
        for f in os.listdir(DOCS_DIR):
            if f.endswith(".json") and (name_prefix in f.lower() or email.lower() in f.lower()):
                return os.path.join(DOCS_DIR, f)
    return None


async def run_test(account_email: str, account_info: Dict[str, Any], method_name: str, is_offline: bool = False):
    """تنفيذ تجربة الدالة وعرض النتائج"""
    print("=" * 70)
    print(f"🏰 الحساب المستهدف : {account_email}")
    print(f"⚙️  الدالة المطلوبة : {method_name}")
    print(f"🌐 وضع التشغيل    : {'🔴 بدون اتصال (Offline Memory)' if is_offline else '🟢 مباشر مع السيرفر (Live Gate)'}")
    print("=" * 70)

    conn = None
    offline_file = None

    if is_offline:
        offline_file = find_offline_memory_file(account_email)
        if not offline_file or not os.path.exists(offline_file):
            print(f"❌ لم يتم العثور على ملف ذاكرة حية محفوظ للحساب في docs/! يرجى تشغيل الأداة في وضع Live.")
            return

        print(f"📂 قراءة الذاكرة من: {os.path.basename(offline_file)}")
        with open(offline_file, "r", encoding="utf-8") as f:
            dump_data = json.load(f)

        uid = dump_data.get("lordInfoCtrl", {}).get("base", {}).get("uid", 10939063)
        conn = OfflineMockConnection(account_email, uid, dump_data)
    else:
        # وضع الاتصال المباشر بالسيرفر
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
                print("❌ فشل الاتصال بالسيرفر! جاري المحاولة من الذاكرة المحلية كخيار بديل...")
                offline_file = find_offline_memory_file(account_email)
                if offline_file and os.path.exists(offline_file):
                    print(f"📂 استرجاع الذاكرة البديلة: {os.path.basename(offline_file)}")
                    with open(offline_file, "r", encoding="utf-8") as f:
                        dump_data = json.load(f)
                    uid = dump_data.get("lordInfoCtrl", {}).get("base", {}).get("uid", 0)
                    conn = OfflineMockConnection(account_email, uid, dump_data)
                else:
                    return
            else:
                print(f"✅ تم الاتصال بنجاح بـ Gate السيرفر! UID: {conn.uid}")
                print("⏳ بانتظار مزامنة حزم البيانات الأولية من السيرفر (init_data)...")
                for _ in range(35):
                    if len(getattr(conn, "init_data", {})) >= 15:
                        break
                    await asyncio.sleep(0.15)
                synced_count = len(getattr(conn, "init_data", {}))
                print(f"📦 تم استلام حزم السيرفر: {synced_count} موديول في الذاكرة الحية.")
        except Exception as e:
            print(f"⚠️ خطأ أثناء الاتصال بالبوابة: {e}")
            offline_file = find_offline_memory_file(account_email)
            if offline_file and os.path.exists(offline_file):
                print(f"📂 استخدام الذاكرة المحلية كبديل: {os.path.basename(offline_file)}")
                with open(offline_file, "r", encoding="utf-8") as f:
                    dump_data = json.load(f)
                uid = dump_data.get("lordInfoCtrl", {}).get("base", {}).get("uid", 0)
                conn = OfflineMockConnection(account_email, uid, dump_data)
            else:
                return

    # إنشاء كائن المهمة (StrongholdTask لامتلاكه دوال المعقل وBaseTask)
    task = StrongholdTask(conn, config={})

    # استخراج الدالة
    method = getattr(task, method_name, None)
    if not method:
        print(f"❌ الدالة '{method_name}' غير موجودة في الكائن!")
        print("💡 الدوال المتاحة:")
        for m in get_available_methods(StrongholdTask):
            if "get_" in m or "check_" in m:
                print(f"   - {m}")
        if conn:
            if hasattr(conn, "close"):
                try: await conn.close()
                except Exception: pass
            elif hasattr(conn, "disconnect"):
                try: await conn.disconnect()
                except Exception: pass
        return

    # تنفيذ الدالة وقياس الوقت
    print(f"\n🚀 جاري تشغيل الدالة `{method_name}()`...")
    start_t = time.perf_counter()
    try:
        if inspect.iscoroutinefunction(method) or inspect.isawaitable(method):
            res = await method()
        elif callable(method):
            res = method()
            if inspect.isawaitable(res):
                res = await res
        else:
            res = method
    except Exception as e:
        print(f"\n❌ حدث خطأ أثناء تنفيذ الدالة: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            if hasattr(conn, "close"):
                try: await conn.close()
                except Exception: pass
            elif hasattr(conn, "disconnect"):
                try: await conn.disconnect()
                except Exception: pass
        return

    elapsed_ms = (time.perf_counter() - start_t) * 1000

    # عرض النتائج بتنسيق واضح
    print("\n" + "─" * 70)
    print(f"📊 [نتيجة التنفيذ] (استغرق: {elapsed_ms:.2f}ms)")
    print(f"📌 نوع القيمة المرجعة: {type(res).__name__}")
    print("─" * 70)

    if isinstance(res, dict):
        print(f"🔢 إجمالي المفاتيح: {len(res)}")
        if res:
            try:
                # محاولة طباعة JSON منسق
                print(json.dumps(res, indent=2, ensure_ascii=False))
            except Exception:
                for k, v in list(res.items())[:30]:
                    print(f"   • {k}: {v}")
                if len(res) > 30:
                    print(f"   ... ({len(res) - 30} عناصر أخرى)")
        else:
            print("   (قاموس فارغ: {})")
    elif isinstance(res, (list, tuple, set)):
        print(f"🔢 إجمالي العناصر: {len(res)}")
        print(f"   {res}")
    else:
        print(f"👉 القيمة: {res}")

    print("─" * 70)

    # قطع الاتصال بأمان
    if conn:
        if hasattr(conn, "close"):
            try:
                await conn.close()
            except Exception:
                pass
        elif hasattr(conn, "disconnect"):
            try:
                await conn.disconnect()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="أداة تجربة واختبار دوال المهام على حسابات session_cache.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("account", nargs="?", help="البريد الإلكتروني أو جزء منه (مثل: shook123)")
    parser.add_argument("method", nargs="?", help="اسم الدالة المراد تجربتها (مثل: get_available_troops)")
    parser.add_argument("-a", "--acc", dest="account_flag", help="تحديد الحساب عبر خيار")
    parser.add_argument("-m", "--method", dest="method_flag", help="تحديد الدالة عبر خيار")
    parser.add_argument("--offline", action="store_true", help="تشغيل بدون اتصال بالاعتماد على ملفات الذاكرة في docs/")
    parser.add_argument("--list-accounts", action="store_true", help="عرض قائمة بجميع الحسابات المتاحة في الكاش")
    parser.add_argument("--list-methods", action="store_true", help="عرض قائمة بالدوال المتاحة للتجربة")

    args = parser.parse_args()

    accounts = load_session_accounts()

    if args.list_accounts:
        print(f"\n📋 الحسابات المتاحة في {CACHE_FILE} (الإجمالي: {len(accounts)}):")
        print("─" * 60)
        for i, (em, info) in enumerate(accounts.items(), 1):
            source = info.get("source", "unknown")
            print(f"{i:2d}. {em:<35} | {source}")
        print("─" * 60)
        return

    if args.list_methods:
        print("\n📋 الدوال المتاحة للاختبار والتجربة:")
        print("─" * 60)
        for m in get_available_methods(StrongholdTask):
            doc = inspect.getdoc(getattr(StrongholdTask, m, None)) or ""
            first_line = doc.splitlines()[0] if doc else "دالة مساعدة"
            print(f"• {m:<28} ➔ {first_line}")
        print("─" * 60)
        return

    account_query = args.account or args.account_flag
    method_name = args.method or args.method_flag

    if not account_query:
        print("⚠️ يرجى تحديد الحساب المطلوب.")
        print("مثال: python tools/test_task_method.py shook123 get_castle_coords")
        print("أو اعرض الحسابات عبر: python tools/test_task_method.py --list-accounts")
        return

    if not method_name:
        print("⚠️ يرجى تحديد اسم الدالة المراد تجربتها.")
        print(f"مثال: python tools/test_task_method.py {account_query} get_available_troops")
        print("أو اعرض الدوال عبر: python tools/test_task_method.py --list-methods")
        return

    match = find_matching_account(account_query, accounts)
    if not match:
        print(f"❌ لم يتم العثور على حساب يطابق '{account_query}' في session_cache.json!")
        return

    email, info = match
    asyncio.run(run_test(email, info, method_name, is_offline=args.offline))


if __name__ == "__main__":
    main()

