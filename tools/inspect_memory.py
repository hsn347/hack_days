#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/inspect_memory.py — أداة فحص واستكشاف الذاكرة الحية (Live Memory Inspector) لحساب معين
══════════════════════════════════════════════════════════════════════════════════════
تتيح الاتصال بحساب معين وإبقاء اتصال السوكت حياً (Live Socket) مع إرسال نبضات القلب الدورية،
واستكشاف محتويات conn.init_data بدقة بالغة وتحديثها لحظياً (refresh)،
مع حساب العدادات التنازلية التلقائية لوصول السفن/الجوائز (Dynamic Live Countdown).

الاستخدام:
  python tools/inspect_memory.py -e degirmencisamet@gmail.com
  python tools/inspect_memory.py -e shook124@gmail.com -p "timeRewardCtrl"
  python tools/inspect_memory.py -e shook124@gmail.com --search health
  python tools/inspect_memory.py --file scratch/init_sumo.json --search academy
"""

import sys
import os
import time
import json
import asyncio
import argparse
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.session_manager import SessionManager
from game_client import GameConnection


def deep_search(data: Any, query: str, current_path: str = "") -> List[Tuple[str, str, Any]]:
    """
    بحث تعامدي في شجرة البيانات بالكامل لمطابقة اسم المفتاح أو القيمة.
    يعيد قائمة من (نوع التطابق, المسار الكامل, القيمة).
    """
    results = []
    q_lower = query.lower()

    if isinstance(data, dict):
        for k, v in data.items():
            k_str = str(k)
            path = f"{current_path}.{k_str}" if current_path else k_str

            # مطابقة اسم المفتاح
            if q_lower in k_str.lower():
                results.append(("KEY", path, v))

            # مطابقة القيمة الأولية المباشرة
            if not isinstance(v, (dict, list)):
                if q_lower in str(v).lower():
                    results.append(("VALUE", path, v))
            else:
                results.extend(deep_search(v, query, path))

    elif isinstance(data, list):
        for idx, item in enumerate(data):
            path = f"{current_path}[{idx}]"
            if not isinstance(item, (dict, list)):
                if q_lower in str(item).lower():
                    results.append(("VALUE", path, item))
            else:
                results.extend(deep_search(item, query, path))

    return results


def resolve_path(data: Any, path_str: str) -> Any:
    """
    استخراج كائن من شجرة البيانات عبر مسار نصي مثل:
    cityCtrl.blist[0].binfo
    """
    import re
    tokens = re.findall(r'[^.\[\]]+', path_str)
    curr = data
    for t in tokens:
        if isinstance(curr, dict):
            curr = curr.get(t)
        elif isinstance(curr, list) and t.isdigit():
            idx = int(t)
            curr = curr[idx] if idx < len(curr) else None
        else:
            return None
        if curr is None:
            return None
    return curr


def format_preview(val: Any, max_len: int = 150) -> str:
    if isinstance(val, (dict, list)):
        s = json.dumps(val, ensure_ascii=False)
    else:
        s = str(val)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def show_dynamic_countdown(val: Any, path_clean: str, init_timestamp: float):
    """تحليل وعرض العداد التنازلي الحي لأي كائن يحتوي على عداد زمني مثل timeRewardCtrl."""
    if not isinstance(val, dict):
        return
    tr_data = val.get("data", {}) if isinstance(val.get("data"), dict) else val
    raw_time = int(val.get("time", 0)) if "time" in val else 0
    is_receive = tr_data.get("isReceive") if isinstance(tr_data, dict) else None
    is_all = tr_data.get("isAllReceive") if isinstance(tr_data, dict) else None

    if raw_time > 0 or is_receive is not None or is_all is not None:
        elapsed = int(time.time() - init_timestamp) if init_timestamp > 0 else 0
        rem_sec = max(0, raw_time - elapsed)

        print("⏱️ [التحليل والعد التنازلي المباشر]:")
        if elapsed > 0:
            print(f"  • الوقت المنقضي منذ الاتصال/التحديث: {elapsed} ثانية")
        if raw_time > 0:
            status_text = "🟢 وصلت السفينة/الجائزة وجاهزة للاستلام فوراً!" if rem_sec == 0 else f"🟡 متبقي {rem_sec} ثانية حتى الوصول"
            print(f"  • العداد التنازلي الفعلي: {rem_sec} ثانية (الأصل في الحزمة: {raw_time}s) ➔ {status_text}")
        if is_receive is not None:
            rec_desc = "جاهزة للاستلام (2)" if is_receive == 2 else ("في الطريق / انتظار العداد (1)" if is_receive == 1 else str(is_receive))
            print(f"  • حالة الاستلام (isReceive): {rec_desc}")
        if is_all == 1:
            print("  • كافة السفن/الجوائز تم استلامها بالكامل اليوم.")


async def fetch_live_connection(email: str) -> Tuple[GameConnection, str]:
    """الاتصال بالسيرفر وإبقاء اتصال السوكت حياً."""
    sm = SessionManager()
    accounts = sm.load()
    acc = accounts.get(email)
    if not acc:
        raise ValueError(f"الحساب '{email}' غير مسجل في session_cache.json!")

    print(f"🔌 جاري الاتصال بالحساب: {email} ...")
    conn = GameConnection(acc)
    connected = await conn.connect()
    if not connected:
        raise ConnectionError(f"فشل الاتصال بخادم الـ Gate للحساب {email}")

    # انتظار استلام حزمة التهيئة الأولية (1000/1) وتعبئة الذاكرة الحية بالكامل
    print("⏳ بانتظار استلام وتدفق بيانات الذاكرة الحية (init_data) من السيرفر...")
    for _ in range(40):  # انتظار حتى 8 ثوانٍ كحد أقصى لاستقرار كافة الأقسام
        await asyncio.sleep(0.2)
        cur_keys = len(conn.init_data)
        if cur_keys >= 10 or ("cityCtrl" in conn.init_data and "lordInfoCtrl" in conn.init_data):
            await asyncio.sleep(0.5)
            break

    uid = str(getattr(conn, "uid", getattr(conn.creds, "uid", "unknown")))
    return conn, uid


async def refresh_live_data(conn: GameConnection) -> int:
    """إرسال طلب 1000/1 لجلب أحدث حالة للذاكرة الحية من السيرفر."""
    print("🔄 جاري تحديث الذاكرة الحية من السيرفر عبر حزمة التهيئة 1000/1...")
    try:
        r = await conn.query('1000', '1', {}, timeout=6)
        if r:
            c = r.get('content', {})
            c_data = c.get('data') if isinstance(c, dict) else {}
            retdata = c_data.get('retdata', {}) if isinstance(c_data, dict) else (c.get('retdata', {}) if isinstance(c, dict) else {})
            if isinstance(retdata, dict) and retdata:
                conn.init_data.update(retdata)
        print(f"✅ تم تحديث الذاكرة بنجاح! ({len(conn.init_data)} متحكم متوفر في الذاكرة)")
    except Exception as ex:
        print(f"⚠️ تنبيه أثناء التحديث: {ex}")
    return len(conn.init_data)


def print_controllers(init_data: dict):
    print("\n" + "═" * 70)
    print(f"🗂️ المتحكمات والأقسام الرئيسية في الذاكرة الحية ({len(init_data)} قسم):")
    print("═" * 70)
    for k in sorted(init_data.keys()):
        v = init_data[k]
        v_type = type(v).__name__
        v_size = len(v) if isinstance(v, (dict, list, str)) else 1
        print(f"  • {k:<32} ({v_type:<4} | {v_size} عنصر)")
    print("═" * 70)


def print_path(init_data: dict, path_str: str, init_timestamp: float = 0):
    path_clean = path_str.strip().strip("'\"")
    print(f"\n🔍 استخراج المسار: {path_clean}")
    val = resolve_path(init_data, path_clean)
    if val is None:
        print(f"❌ المسار '{path_clean}' غير موجود في الذاكرة الحية!")
    else:
        print(f"✅ نوع الكائن: {type(val).__name__}")
        if isinstance(val, (dict, list)):
            print(json.dumps(val, ensure_ascii=False, indent=2)[:3000])
        else:
            print(f"القيمة: {val}")
        show_dynamic_countdown(val, path_clean, init_timestamp)


def print_search(init_data: dict, query: str, init_timestamp: float = 0):
    q_clean = query.strip().strip("'\"")
    print(f"\n🔎 نتائج البحث العميق عن '{q_clean}':")
    print("-" * 70)
    matches = deep_search(init_data, q_clean)
    if not matches:
        print(f"❌ لم يتم العثور على أي مفتاح أو قيمة تحتوي على '{q_clean}'.")
    else:
        print(f"🎯 تم العثور على {len(matches)} مطابقة:")
        expand_count = 0
        for m_type, m_path, m_val in matches[:50]:
            tag = "🔑 مفتاح" if m_type == "KEY" else "📄 قيمة"
            if m_type == "KEY" and isinstance(m_val, (dict, list)):
                v_type = type(m_val).__name__
                v_len = len(m_val)
                # إذا كانت نتائج البحث محدودة أو أول نتيجتين لمفاتيح مركبة: عرض المحتوى بالتفصيل
                if len(matches) <= 3 or expand_count < 2:
                    expand_count += 1
                    try:
                        formatted_json = json.dumps(m_val, ensure_ascii=False, indent=2)
                    except Exception:
                        formatted_json = str(m_val)

                    if len(formatted_json) > 2500:
                        preview_body = formatted_json[:2500] + f"\n... [تفريغ كبير ({v_len} عنصر) — اكتب p {m_path} لرؤيته كاملاً]"
                    else:
                        preview_body = formatted_json

                    print(f"  [{tag}] {m_path} ({v_type} | {v_len} عنصر):")
                    indented = "\n".join("    " + line for line in preview_body.splitlines())
                    print(indented)
                    show_dynamic_countdown(m_val, m_path, init_timestamp)
                else:
                    if isinstance(m_val, dict):
                        subkeys = list(m_val.keys())[:8]
                        subkeys_str = ", ".join(f"'{k}'" for k in subkeys)
                        more = f" ...+{v_len - 8} أخرى" if v_len > 8 else ""
                        print(f"  [{tag}] {m_path} ({v_len} عنصر) ➔ عناصر: [{subkeys_str}{more}]")
                    else:
                        print(f"  [{tag}] {m_path} (قائمة: {v_len} عنصر) ➔ {format_preview(m_val)}")
            else:
                print(f"  [{tag}] {m_path} ➔ {format_preview(m_val)}")
        if len(matches) > 50:
            print(f"  ... و {len(matches) - 50} مطابقة أخرى.")
    print("-" * 70)


def save_dump(init_data: dict, account_label: str):
    os.makedirs(os.path.join(_ROOT, "scratch"), exist_ok=True)
    dump_path = os.path.join(_ROOT, "scratch", f"init_{account_label}.json")
    with open(dump_path, "w", encoding="utf-8") as fp:
        json.dump(init_data, fp, ensure_ascii=False, indent=2)
    print(f"💾 تم حفظ تفريغ الذاكرة الحية كاملاً في: {dump_path}")


async def interactive_shell(conn: Optional[GameConnection], init_data: dict, account_label: str, init_timestamp: float):
    conn_status = "🟢 مباشر (Live Socket)" if conn else "📁 محلي (Offline)"
    print("\n" + "═" * 75)
    print(f"🔎 جلسة استكشاف الذاكرة الحية التفاعلية: [{account_label}] ({len(init_data)} متحكم) — {conn_status}")
    print("═" * 75)
    print("💡 خيارات سريعة:")
    print("  • controllers (أو c)        ➔ عرض كافة المتحكمات الرئيسية وأحجامها")
    print("  • refresh (أو r)            ➔ تحديث فوري لكافة بيانات الذاكرة الحية من السيرفر (1000/1)")
    print("  • query <cmd> <subcmd>      ➔ إرسال استعلام مخصص للسيرفر ورؤية النتيجة (مثال: query 1033 2)")
    print("  • dump (أو d)               ➔ حفظ تفريغ كامل للذاكرة في scratch/")
    print("  • p <مسار>                  ➔ استخراج مسار محدد (مثال: p cityCtrl.blist[3].binfo)")
    print("  • clear (أو cls)            ➔ مسح الشاشة")
    print("  • exit (أو q)               ➔ خروج")
    print("  • أو اكتب أي كلمة/رقم للبحث الفوري المباشر (مثل: timeRewardCtrl أو 113 أو stamina)")
    print("═" * 75)

    prompt_label = f"[{account_label}] ➔ "

    while True:
        try:
            user_input = await asyncio.to_thread(input, f"\n{prompt_label}")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 إلى اللقاء!")
            break

        if not user_input:
            continue

        raw = user_input.strip().strip("'\"")
        cmd_lower = raw.lower()

        # أخذ أحدث نسخة من الذاكرة الحية دائماً إذا كان الاتصال حياً
        if conn and hasattr(conn, "init_data") and conn.init_data:
            init_data = conn.init_data

        if cmd_lower in ("exit", "quit", "q"):
            print("👋 تم إنهاء الجلسة.")
            break
        elif cmd_lower in ("clear", "cls"):
            os.system("cls" if os.name == "nt" else "clear")
        elif cmd_lower in ("controllers", "c"):
            print_controllers(init_data)
        elif cmd_lower in ("refresh", "r"):
            if conn:
                await refresh_live_data(conn)
                init_data = conn.init_data
                init_timestamp = time.time()
            else:
                print("⚠️ أنت تعمل في وضع الملف دون اتصال (Offline)، التحديث متاح فقط مع الحساب الحي.")
        elif cmd_lower.startswith("query ") or cmd_lower.startswith("req "):
            if not conn:
                print("⚠️ إرسال الاستعلامات متاح فقط أثناء الاتصال الحي.")
            else:
                parts = raw.split()
                if len(parts) >= 3:
                    c_id, s_id = parts[1], parts[2]
                    print(f"📡 إرسال استعلام مباشر: CMD={c_id}, SUB={s_id} ...")
                    try:
                        res = await conn.query(c_id, s_id, {}, timeout=7)
                        print(json.dumps(res, ensure_ascii=False, indent=2)[:3000])
                    except Exception as q_err:
                        print(f"❌ خطأ في الاستعلام: {q_err}")
                else:
                    print("صيغة الأمر: query <cmd> <subcmd> (مثال: query 1033 2)")
        elif cmd_lower in ("dump", "d"):
            save_dump(init_data, account_label)
        elif cmd_lower in ("help", "h", "?"):
            print("الأوامر: controllers (c) | refresh (r) | query <cmd> <subcmd> | dump (d) | p <مسار> | cls | exit (q) | أو أي كلمة للبحث")
        elif cmd_lower.startswith("p ") or cmd_lower.startswith("path "):
            target_path = raw.split(" ", 1)[1].strip()
            print_path(init_data, target_path, init_timestamp)
        elif cmd_lower.startswith("s ") or cmd_lower.startswith("search "):
            target_query = raw.split(" ", 1)[1].strip()
            print_search(init_data, target_query, init_timestamp)
        elif "." in raw and " " not in raw:
            print_path(init_data, raw, init_timestamp)
        elif raw in init_data:
            print_path(init_data, raw, init_timestamp)
        else:
            print_search(init_data, raw, init_timestamp)


async def async_main():
    parser = argparse.ArgumentParser(description="أداة فحص واستكشاف الذاكرة الحية (init_data) لحساب معين")
    parser.add_argument("-e", "--email", type=str, help="البريد الإلكتروني للحساب")
    parser.add_argument("-f", "--file", type=str, help="مسار ملف JSON محلي محفوظ مسبقاً (فحص دون اتصال)")
    parser.add_argument("-s", "--search", type=str, help="كلمة أو رقم للبحث عنه في كامل شجرة الذاكرة الحية")
    parser.add_argument("-p", "--path", type=str, help="استخراج مسار محدد (مثال: cityCtrl.blist أو lordInfoCtrl)")
    parser.add_argument("-c", "--controllers", action="store_true", help="سرد كافة المتحكمات الرئيسية بالذاكرة وأحجامها")
    parser.add_argument("-d", "--dump", action="store_true", help="تفريغ كامل الذاكرة في ملف JSON محلي بداخل scratch/")
    parser.add_argument("--once", action="store_true", help="تنفيذ الأمر المطلوب والخروج فوراً دون دخول الجلسة التفاعلية")

    args = parser.parse_args()

    conn = None
    init_data = None
    account_label = "offline"
    init_timestamp = time.time()

    try:
        # 1. تحميل البيانات
        if args.file:
            if not os.path.exists(args.file):
                print(f"❌ الملف غير موجود: {args.file}")
                sys.exit(1)
            print(f"📂 تحميل الذاكرة من الملف المحلي: {args.file}")
            with open(args.file, "r", encoding="utf-8") as fp:
                init_data = json.load(fp)
            account_label = os.path.splitext(os.path.basename(args.file))[0]
        else:
            sm = SessionManager()
            accounts = sm.load()
            email = args.email
            if not email:
                print("\n📋 الحسابات المتاحة محلياً:")
                acc_list = sorted(list(accounts.keys()))
                for i, acc_email in enumerate(acc_list, 1):
                    print(f"  [{i}] {acc_email}")
                print("\nيرجى تحديد الحساب عبر: python tools/inspect_memory.py -e <email>")
                return

            account_label = email.split("@")[0]
            try:
                conn, uid = await fetch_live_connection(email)
                init_data = conn.init_data
                init_timestamp = time.time()
                print(f"✅ تم الاتصال وجلب الذاكرة الحية بنجاح! (UID: {uid} | حجم: {len(init_data)} متحكم رئيسي)")
                print("🟢 اتصال السوكت نشط مع خادم اللعبة (Heartbeat فعال في الخلفية)")
            except Exception as ex:
                print(f"❌ فشل الاتصال بالحساب: {ex}")
                return

        if not init_data or not isinstance(init_data, dict):
            print("⚠️ الذاكرة الحية فارغة أو غير متوفرة!")
            return

        # 2. تنفيذ الأوامر المباشرة إذا تم تمريرها بالـ arguments
        if args.dump:
            save_dump(init_data, account_label)

        if args.controllers:
            print_controllers(init_data)

        if args.path:
            print_path(init_data, args.path, init_timestamp)

        if args.search:
            print_search(init_data, args.search, init_timestamp)

        # 3. دخول الجلسة التفاعلية المستمرة إلا إذا طلب المستخدم --once
        if not args.once:
            await interactive_shell(conn, init_data, account_label, init_timestamp)

    finally:
        if conn:
            try:
                print("🔌 جاري إغلاق اتصال السوكت بأمان...")
                await conn.close()
            except Exception:
                pass


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n👋 تم إنهاء الأداة.")


if __name__ == "__main__":
    main()
