# -*- coding: utf-8 -*-
"""
refresh_live_memory.py — أداة تجديد وتحديث ملفات تفريغ الذاكرة الحية (Live Memory Dumper) للعبة العثمانية
══════════════════════════════════════════════════════════════════════════════════════

تتيح هذه الأداة استخراج الذاكرة الحية لأي حساب وتحديث ملفات الـ JSON في مجلد docs/ تلقائياً.
يمكن تمرير مسار ملف JSON قائم ليتم تجديده، أو تمرير بريد الحساب ليتم استخراج ذاكرته،
أو تشغيل الأداة مباشرة بدون وسائط لتحديث الحساب النشط الافتراضي أو الاختيار من القائمة.

أمثلة على الاستخدام من سطر الأوامر:
  1. تجديد ملف موجود بالفعل في docs/:
     python refresh_live_memory.py docs/my_account_live_memory.json
     أو:
     python refresh_live_memory.py my_account_live_memory.json

  2. استخراج الذاكرة عبر تحديد البريد مباشرة:
     python tools/refresh_live_memory.py jzarco.all@gmail.com
     أو:
     python refresh_live_memory.py razan@gamil.com

  3. تحديد مسار مخصص لحفظ الملف الناتج:
     python refresh_live_memory.py king7moe1990@gmail.com -o docs/my_dump.json

  4. عرض قائمة الحسابات والملفات المتاحة في المشروع:
     python refresh_live_memory.py --list
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ════════════════════════════════════════════════════════════════════
#  مسارات بيئة العمل والمجلدات الرئيسية
# ════════════════════════════════════════════════════════════════════

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

DOCS_DIR = os.path.join(WORKSPACE_DIR, "docs")
DB_PATH = os.path.join(WORKSPACE_DIR, "database", "castles.db")

from core.session_manager import SessionManager
from game_client import GameConnection, AccountSession


# ════════════════════════════════════════════════════════════════════
#  مغلّف إدارة الاتصال والمصادقة (CastleBot Adapter)
# ════════════════════════════════════════════════════════════════════

class CastleBot:
    """
    مغلّف خفيف ومتوافق مع واجهة CastleBot لإدارة الاتصال والمصادقة للعبة العثمانية:
    - تسجيل الدخول والمصادقة مع البوابة واستخدام session_cache.json تلقائياً.
    - فتح اتصال GameConnection ومراقبة تدفق المتحكمات الأولية (CMD 1000).
    - توفير حدث controllers_ready وإتاحة init_data للإخراج.
    """
    def __init__(self, email: str, password: Optional[str] = None):
        self.email = email
        self.password = password
        self.account: Optional[AccountSession] = None
        self.conn: Optional[GameConnection] = None
        self.creds: Optional[Any] = None

    async def connect(self) -> bool:
        sm = SessionManager()
        self.account = sm.get_or_login(self.email, password=self.password)
        if not self.account:
            return False

        self.conn = GameConnection(self.account)

        # تجهيز حدث controllers_ready لمطابقة بروتوكول استلام الحزم
        controllers_ready = asyncio.Event()
        setattr(self.conn, "controllers_ready", controllers_ready)

        def _on_packet(cmd: str, sub: str, content: dict):
            if str(cmd) in ("1000", "onemt_1000") or (isinstance(content, dict) and "retdata" in str(content)):
                controllers_ready.set()

        self.conn.add_packet_listener(_on_packet)

        connected = await self.conn.connect()
        if not connected or not self.conn.is_connected:
            return False

        self.creds = self.conn.creds

        # فحص استباقي ومراقبة تدفق المتحكمات للتأكد من إطلاق الإشارة
        async def _check_ready():
            for _ in range(40):
                if len(getattr(self.conn, "init_data", {})) >= 10:
                    controllers_ready.set()
                    break
                await asyncio.sleep(0.3)

        asyncio.create_task(_check_ready())

        # إرسال استعلام 1000/1 النشط لجلب الذاكرة الحية بالكامل بمطابقة معمارية البوابة
        try:
            r = await self.conn.query("1000", "1", {}, timeout=10)
            if r and isinstance(r, dict):
                c_data = r.get("data") if isinstance(r.get("data"), dict) else r
                retdata = c_data.get("retdata") if isinstance(c_data, dict) else r.get("retdata")
                if isinstance(retdata, dict) and retdata:
                    self.conn.init_data.update(retdata)
                    controllers_ready.set()
                elif isinstance(c_data, dict) and len(c_data) > 0:
                    for k, v in c_data.items():
                        if isinstance(v, (dict, list)) and ("Ctrl" in k or "Mgr" in k):
                            self.conn.init_data[k] = v
                    if len(self.conn.init_data) > 0:
                        controllers_ready.set()
        except Exception:
            pass

        # استعلام تكميلي لمباني المدينة إن لم تكن متوفرة
        if "cityCtrl" not in self.conn.init_data or not self.conn.init_data.get("cityCtrl", {}).get("blist"):
            try:
                r_city = await self.conn.query("1001", "1", {}, timeout=6)
                if r_city and isinstance(r_city.get("data"), dict):
                    self.conn.init_data.setdefault("cityCtrl", {}).update(r_city["data"])
            except Exception:
                pass

        # استعلام تكميلي لبيانات اللورد الأساسية إن لم تكن متوفرة
        uid_val = getattr(self.conn, "uid", None) or (self.creds.uid if self.creds else None)
        if uid_val and ("lordInfoCtrl" not in self.conn.init_data or not self.conn.init_data.get("lordInfoCtrl", {}).get("base")):
            try:
                uid_int = int(uid_val) if str(uid_val).isdigit() else uid_val
                r_lord = await self.conn.query("1002", "7", {"uid": uid_int}, timeout=6)
                if r_lord and isinstance(r_lord.get("data"), dict):
                    base_info = r_lord["data"].get("base", {})
                    fc_info = r_lord["data"].get("fcInfo", {})
                    self.conn.init_data.setdefault("lordInfoCtrl", {})["base"] = base_info
                    self.conn.init_data.setdefault("lordInfoCtrl", {})["fcInfo"] = fc_info
            except Exception:
                pass

        if len(self.conn.init_data) > 0:
            controllers_ready.set()

        return True


# ════════════════════════════════════════════════════════════════════
#  مساعدات فحص قاعدة البيانات وملفات الـ JSON
# ════════════════════════════════════════════════════════════════════

def get_all_db_accounts() -> List[Dict[str, Any]]:
    """جلب كافة الحسابات المسجلة في قاعدة بيانات القلاع"""
    accounts = []
    if not os.path.exists(DB_PATH):
        return accounts

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT email, password, is_active, lord_name, castle_name, server_id FROM castle_states")
        for row in cur.fetchall():
            email, pwd, active, l_name, c_name, s_id = row
            accounts.append({
                "email": email,
                "password": pwd,
                "is_active": bool(active),
                "lord_name": l_name or "",
                "castle_name": c_name or "",
                "kid": s_id or 0,
            })
        conn.close()
    except Exception as e:
        print(f"⚠️ خطأ أثناء قراءة قاعدة البيانات: {e}")

    return accounts


def get_existing_docs_dumps() -> List[Dict[str, Any]]:
    """جلب كافة ملفات تفريغ الذاكرة الحية الموجودة في مجلد docs/"""
    dumps = []
    if not os.path.exists(DOCS_DIR):
        return dumps

    for fname in os.listdir(DOCS_DIR):
        if fname.endswith(".json"):
            full_path = os.path.join(DOCS_DIR, fname)
            try:
                size_kb = os.path.getsize(full_path) / 1024
                mtime = os.path.getmtime(full_path)
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            except Exception:
                size_kb = 0.0
                time_str = ""

            # محاولة قراءة بيانات اللورد من الملف
            lord_name = ""
            uid = ""
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    lord_info = data.get("lordInfoCtrl", {})
                    base = lord_info.get("base", {}) if isinstance(lord_info, dict) else {}
                    lord_name = base.get("nickName") or base.get("name") or ""
                    uid = str(base.get("uid", ""))
                    if not uid:
                        lord = data.get("lord", {})
                        uid = str(lord.get("uid", ""))
            except Exception:
                pass

            dumps.append({
                "filename": fname,
                "path": full_path,
                "size_kb": size_kb,
                "mtime": time_str,
                "lord_name": lord_name,
                "uid": uid,
            })
    return dumps


def resolve_account_and_output(target: Optional[str], custom_out: Optional[str] = None) -> Tuple[str, str, str]:
    """
    تحليل المدخل بذكاء لتحديد (البريد الإلكتروني، كلمة المرور، ومسار ملف الحفظ):
    - إذا كان target مسار ملف JSON: يكتشف الحساب المناسب ويحدد نفس الملف كوجهة.
    - إذا كان target بريد أو اسم حساب: يحدد الحساب وينشئ اسم ملف في docs/.
    - إذا كان target فارغاً: يختار أول حساب نشط في قاعدة البيانات.
    """
    accounts = get_all_db_accounts()
    if not accounts:
        raise ValueError(f"❌ لم يتم العثور على أي حسابات في قاعدة البيانات {DB_PATH}!")

    # 1. إذا تم تمرير مسار ملف .json
    if target and (target.lower().endswith(".json") or os.path.exists(target)):
        file_path = target if os.path.isabs(target) else os.path.join(DOCS_DIR, os.path.basename(target))
        if not os.path.exists(file_path) and os.path.exists(target):
            file_path = os.path.abspath(target)

        # استخراج بيانات من الملف القديم إن وُجد لمطابقته
        matched_acc = None
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    lord_info = old_data.get("lordInfoCtrl", {})
                    base = lord_info.get("base", {}) if isinstance(lord_info, dict) else {}
                    lord_name = str(base.get("nickName") or base.get("name") or "").lower()
                    lord_uid = str(base.get("uid") or old_data.get("lord", {}).get("uid", ""))

                    # مطابقة عبر UID أو اسم اللورد مع حسابات القاعدة
                    for acc in accounts:
                        acc_lord = str(acc.get("lord_name", "")).lower()
                        if lord_name and acc_lord and (lord_name == acc_lord or lord_name in acc_lord or acc_lord in lord_name):
                            matched_acc = acc
                            break
            except Exception:
                pass

        # إذا لم يتطابق من داخل الملف، نطابق باسم الملف نفسه
        if not matched_acc:
            base_stem = os.path.splitext(os.path.basename(file_path))[0].lower()
            clean_stem = base_stem.replace("_live_memory", "").replace("sample_", "")
            for acc in accounts:
                email_prefix = acc["email"].split("@")[0].lower()
                if clean_stem in email_prefix or email_prefix in clean_stem:
                    matched_acc = acc
                    break
                if clean_stem in str(acc.get("lord_name", "")).lower():
                    matched_acc = acc
                    break

        if not matched_acc:
            # افتراض الحساب النشط أو الأول
            matched_acc = next((a for a in accounts if a["is_active"]), accounts[0])

        return matched_acc["email"], matched_acc["password"], file_path

    # 2. إذا تم تمرير بريد أو اسم حساب
    if target:
        target_clean = target.strip().lower()
        matched_acc = None
        for acc in accounts:
            if acc["email"].lower() == target_clean:
                matched_acc = acc
                break
            if acc["email"].split("@")[0].lower() == target_clean:
                matched_acc = acc
                break
            if target_clean in str(acc.get("lord_name", "")).lower():
                matched_acc = acc
                break

        if not matched_acc:
            raise ValueError(f"❌ لم يتم العثور على حساب يطابق '{target}' في قاعدة البيانات!")

        # مسار الملف الافتراضي
        out_path = custom_out
        if not out_path:
            prefix = matched_acc["email"].split("@")[0].lower()
            # فحص إذا كان هناك ملف مخصص موجود مسبقاً لهذا الحساب
            candidate = os.path.join(DOCS_DIR, f"{prefix}_live_memory.json")
            out_path = candidate

        return matched_acc["email"], matched_acc["password"], os.path.abspath(out_path)

    # 3. إذا لم يمرر المستخدم أي وسيط (الافتراضي: الحساب النشط الأول)
    active_acc = next((a for a in accounts if a["is_active"]), accounts[0])

    prefix = active_acc["email"].split("@")[0].lower()
    default_out = os.path.join(DOCS_DIR, f"{prefix}_live_memory.json")
    return active_acc["email"], active_acc["password"], os.path.abspath(default_out)


# ════════════════════════════════════════════════════════════════════
#  عملية استخراج وتحديث الذاكرة الحية
# ════════════════════════════════════════════════════════════════════

async def refresh_live_memory(email: str, password: str, output_path: str, fetch_lazy: bool = True) -> bool:
    """
    الاتصال بالبوابة الرسمية للحساب، تفريغ الذاكرة الحية وتحديث الوحدات الكسولة، ثم حفظها في ملف JSON
    """
    start_time = time.time()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    prev_size_kb = 0.0
    if os.path.exists(output_path):
        prev_size_kb = os.path.getsize(output_path) / 1024.0

    print(f"\n📡 بدء الاتصال بالبوابة الرسمية لتجديد الذاكرة الحية...")
    print(f"   📧 الحساب: {email}")
    print(f"   🎯 مسار الإخراج: {output_path}")

    bot = CastleBot(email=email, password=password)

    try:
        # الاتصال بالحساب (يستفيد تلقائياً من session_cache.json إن وُجد)
        connected = await bot.connect()
        if not connected or not bot.conn:
            print("❌ فشل الاتصال بالبوابة أو مصافحة تسجيل الدخول.")
            return False

        # انتظار تفريغ المتحكمات في الذاكرة الحية (CMD 1000)
        try:
            await asyncio.wait_for(bot.conn.controllers_ready.wait(), timeout=12.0)
        except asyncio.TimeoutError:
            print("⚠️ مهلة استقبال متحكمات القلعة انتهت، سيتم استخدام ما وصل بالفعل.")

        live_data = bot.conn.init_data
        ctrl_count = len(live_data)
        print(f"✓ تم استلام وتفريغ {ctrl_count} متحكم في الذاكرة الحية بنجاح.")

        # استخراج بيانات اللورد والقلعة بدقة (من lordInfoCtrl و cityCtrl)
        lord_info = live_data.get("lordInfoCtrl", {})
        base = lord_info.get("base", {}) if isinstance(lord_info, dict) else {}
        lord_name = base.get("nickName") or base.get("name") or "Unknown"
        lord_level = int(base.get("level", 0))

        city_ctrl = live_data.get("cityCtrl", {})
        castle_level = int(city_ctrl.get("level", 1)) if isinstance(city_ctrl, dict) else 1
        blist = city_ctrl.get("blist", []) if isinstance(city_ctrl, dict) else []
        if isinstance(blist, list):
            for b in blist:
                if isinstance(b, dict):
                    binfo = b.get("binfo") if isinstance(b.get("binfo"), dict) else b
                    if str(binfo.get("bid", "")) == "101":
                        castle_level = int(binfo.get("lv", castle_level))
                        break

        uid = bot.creds.uid if bot.creds else base.get("uid", "")
        kid = bot.creds.kingdom_id if bot.creds else base.get("kid", "")

        # التحقق من عضوية التحالف
        aid = 0
        alliance_ctrl = live_data.get("allianceCtrl", {})
        if isinstance(alliance_ctrl, dict):
            minfo = alliance_ctrl.get("memberinfo", {}).get("minfo", {})
            if isinstance(minfo, dict):
                aid = int(minfo.get("aid", 0))
        if not aid:
            member_mgr = live_data.get("memberMgr", {})
            if isinstance(member_mgr, dict):
                own_member = member_mgr.get("ownMember", {})
                if isinstance(own_member, dict):
                    aid = int(own_member.get("aid", 0))
        if not aid:
            lord = live_data.get("lord", {})
            if isinstance(lord, dict):
                aid = int(lord.get("alliance", 0))

        # جلب بيانات كنز التحالف (Lazy Load عبر CMD 2015 SubCMD 1) لملء allianceTreasureCtrl
        if fetch_lazy and aid > 0:
            print("📦 جلب بيانات كنز التحالف الميدانية (CMD 2015 / 1) لتضمينها في الذاكرة...")
            try:
                res_treasure = await bot.conn.query("2015", "1")
                if res_treasure and str(res_treasure.get("err", "")) in ("0", 0):
                    rspdata = res_treasure.get("rspdata") or res_treasure.get("data") or {}
                    live_data["allianceTreasureCtrl"] = rspdata
                    print("   ✓ تم تحديث بيانات `allianceTreasureCtrl` بالكامل بنجاح.")
                else:
                    err_c = res_treasure.get("err") if res_treasure else "none"
                    print(f"   ⚠️ استجابة كنز التحالف بكود غير صفري: {err_c}")
            except Exception as e:
                print(f"   ⚠️ تعذر جلب كنز التحالف: {e}")

        saved_ctrl_count = len(live_data)

        # حفظ الذاكرة الحية بصيغة JSON منسق ونظيف
        print(f"💾 جاري كتابة ملف الذاكرة الحية الجديد إلى القرص...")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(live_data, f, indent=2, ensure_ascii=False)

        elapsed = time.time() - start_time
        new_size_kb = os.path.getsize(output_path) / 1024.0

        # إغلاق الاتصال بأمان
        if bot.conn:
            await bot.conn.close()

        # طباعة التقرير النهائي
        print("\n" + "═" * 78)
        print(" 🎉 اكتمل تجديد واستخراج الذاكرة الحية بنجاح!")
        print("═" * 78)
        print(f" 🏰 اللورد: {lord_name} (Lv.{lord_level}) | القصر: Lv.{castle_level} | المملكة: {kid} | UID: {uid}")
        print(f" 🏛️ التحالف: {'AID=' + str(aid) if aid > 0 else 'بدون تحالف'}")
        print(f" 📊 عدد المتحكمات المحفوظة: {saved_ctrl_count} متحكم")
        if prev_size_kb > 0:
            print(f" 📦 حجم الملف: {new_size_kb:.1f} KB (الحجم السابق: {prev_size_kb:.1f} KB)")
        else:
            print(f" 📦 حجم الملف الجديد: {new_size_kb:.1f} KB")
        print(f" ⏱️ استغرق التحديث: {elapsed:.2f} ثانية")
        print(f" 📁 المسار: {output_path}")
        print("═" * 78 + "\n")
        return True

    except Exception as e:
        print(f"\n❌ حدث خطأ غير متوقع أثناء تفريغ الذاكرة: {e}")
        import traceback
        traceback.print_exc()
        if bot.conn:
            try:
                await bot.conn.close()
            except Exception:
                pass
        return False


# ════════════════════════════════════════════════════════════════════
#  نقطة الدخول الرئيسية (CLI Interface)
# ════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="أداة تجديد واستخراج الذاكرة الحية للعبة العثمانية (Live Memory Refresh Utility)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="مسار ملف JSON موجود للتجديد (مثل: docs/dump.json) أو بريد الحساب",
    )
    parser.add_argument(
        "-e", "--email",
        type=str,
        default=None,
        help="تحديد بريد الحساب صراحة",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="مسار ملف الإخراج المخصص (افتراضياً: docs/<name>_live_memory.json)",
    )
    parser.add_argument(
        "--no-lazy",
        action="store_true",
        help="تعطيل جلب الوحدات الكسولة الإضافية (مثل كنز التحالف)",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="عرض قائمة الحسابات والملفات المتاحة في المشروع فقط",
    )

    args = parser.parse_args()

    # إذا طُلبت القائمة فقط
    if args.list:
        print("\n📋 الحسابات المسجلة في قاعدة البيانات:")
        accounts = get_all_db_accounts()
        for i, acc in enumerate(accounts, 1):
            act_str = "🟢 نشط" if acc["is_active"] else "⚪ متوقف"
            print(f"   {i}. {acc['email']} | اللورد: {acc['lord_name']} (K:{acc['kid']}) | {act_str}")

        print("\n📁 ملفات الذاكرة الحية الموجودة في مجلد docs/:")
        dumps = get_existing_docs_dumps()
        if not dumps:
            print("   (لا توجد ملفات حالياً)")
        for d in dumps:
            print(f"   • {d['filename']} ({d['size_kb']:.1f} KB) - معدل: {d['mtime']} | اللورد: {d['lord_name']}")
        print()
        return

    target = args.email or args.target

    try:
        email, password, output_path = resolve_account_and_output(target, args.output)
    except Exception as e:
        print(f"\n{e}\n")
        sys.exit(1)

    fetch_lazy = not args.no_lazy
    asyncio.run(refresh_live_memory(email, password, output_path, fetch_lazy=fetch_lazy))


if __name__ == "__main__":
    main()

