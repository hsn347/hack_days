# -*- coding: utf-8 -*-
"""
check_online.py — سكريبت تجريبي لمعرفة ما إذا كانت القلعة مفتوحة حالياً من مستخدم
══════════════════════════════════════════════════════════════════════════════════════
طريقة العمل الآمنة (بدون تسجيل الدخول في القلعة المستهدفة):
  1. استخراج معرف القلعة (UID) ورقم المملكة عبر خادم الاستعلام المبدئي (Login Server) فقط دون لمس بوابة اللعبة (Gate).
  2. الاستعانة بحساب مراقب/كشاف (Watcher) للاتصال بالسيرفر.
  3. استعلام بروفايل الحاكم (1002/7) وبيانات أعضاء التحالف (1010/6).
  4. فحص حقل online الرسمي من السيرفر:
     - إذا كانت القيمة 0 -> 🟢 القلعة مفتوحة حالياً من مستخدم (Online).
     - إذا كانت القيمة > 0 -> 🔴 القلعة مغلقة (Offline)، مع إظهار وقت آخر خروج والمدة المنقضية.

الاستخدام:
    python check_online.py --email "sumo-1234@hotmil.com"
    python check_online.py --email "johan2003@yopmail.com" --watcher "hmzawyha44@gmail.com"
"""

import asyncio
import argparse
import datetime
import json
import logging
import os
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# كتم رسائل التسجيل المزعجة لإبقاء المخرجات نظيفة وواضحة تماماً
logging.disable(logging.CRITICAL)

from game_client import GameConnection, AccountSession, async_login

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_CACHE_FILE = os.path.join(_ROOT_DIR, "database", "session_cache.json")
if not os.path.exists(SESSION_CACHE_FILE):
    SESSION_CACHE_FILE = os.path.join(_ROOT_DIR, "session_cache.json")


def load_session_cache() -> dict:
    if os.path.exists(SESSION_CACHE_FILE):
        try:
            with open(SESSION_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("accounts", {})
        except Exception:
            pass
    return {}


async def resolve_target_uid(target_email: str, cache: dict) -> tuple:
    """
    جلب معرف الحساب المستهدف (UID ومملكة السيرفر) عبر Login Server المبدئي فقط
    ملاحظة: هذا الاتصال لا يتصل ببوابة Gate وبالتالي لا يطرد اللاعب مطلقاً.
    """
    acc_data = cache.get(target_email)
    if not acc_data:
        # محاولة البحث غير الحساس لحالة الأحرف
        for em, d in cache.items():
            if em.lower() == target_email.lower():
                target_email = em
                acc_data = d
                break

    if not acc_data:
        return None, None, f"البريد الإلكتروني '{target_email}' غير موجود في ملف الجلسات ({SESSION_CACHE_FILE})."

    session = AccountSession(target_email, acc_data["userId"], acc_data["sessionId"])
    creds = await async_login(session)
    if not creds:
        return None, None, f"فشل التحقق من جلسة الحساب المستهدف عبر Login Server (قد تكون منتهية)."

    return creds.uid, creds.kingdom_id, None


async def pick_working_watcher(cache: dict, exclude_email: str, preferred_watcher: str = None, target_kingdom: str = None) -> tuple:
    """
    اختيار حساب كشاف صالح ومتصل لفحص القلعة من الخارج.
    يتم إعطاء الأولوية للحسابات المتواجدة في نفس المملكة لضمان دقة الاستعلام.
    """
    candidates = []
    if preferred_watcher:
        candidates.append(preferred_watcher)
    
    # إضافة حسابات الكاش كمرشحين تلقائيين (مع استبعاد الحساب المستهدف)
    for em in cache.keys():
        if em.lower() != exclude_email.lower() and em not in candidates:
            candidates.append(em)

    best_fallback = None

    for em in candidates:
        data = cache.get(em)
        if not data:
            continue
        try:
            session = AccountSession(em, data["userId"], data["sessionId"])
            creds = await async_login(session)
            if creds:
                # إذا وجدنا حساباً في نفس المملكة، نختاره فوراً
                if target_kingdom and str(creds.kingdom_id) == str(target_kingdom):
                    conn = GameConnection(session)
                    ok = await conn.connect()
                    if ok:
                        return conn, em
                    else:
                        await conn.close()
                elif best_fallback is None:
                    # حفظ أول حساب شغال كخيار بديل إذا لم نجد حساباً في نفس المملكة
                    conn = GameConnection(session)
                    ok = await conn.connect()
                    if ok:
                        best_fallback = (conn, em)
                    else:
                        await conn.close()
        except Exception:
            continue

    if best_fallback:
        return best_fallback

    return None, None


def format_duration(seconds: int) -> str:
    """تنسيق المدة الزمنية بشكل مقروء (أيام، ساعات، دقائق)"""
    if seconds < 60:
        return f"{seconds} ثانية"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} دقيقة"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours < 24:
        return f"{hours} ساعة و {rem_min} دقيقة"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days} يوم و {rem_hours} ساعة"


async def check_castle_online(target_email: str, watcher_email: str = None):
    print("=" * 65)
    print("   🔍 فاحص حالة القلعة الذكي (كشف التواجد بدون تسجيل الدخول)")
    print("=" * 65)
    print(f"📧 الحساب المستهدف  : {target_email}")

    cache = load_session_cache()
    if not cache:
        print(f"❌ لم يتم العثور على أي حسابات في {SESSION_CACHE_FILE}!")
        return

    # 1. استخراج معرف القلعة والمملكة دون لمس البوابة (بدون طرد)
    print("\n[1/3] جلب معرف القلعة من خادم الاستعلامات (بدون الدخول للعبة)...")
    target_uid, target_kingdom, err = await resolve_target_uid(target_email, cache)
    if err:
        print(f"❌ خطأ: {err}")
        return

    print(f"   ✓ تم جلب المعرف بنجاح: UID={target_uid} | المملكة={target_kingdom}")

    # 2. تجهيز حساب المراقب الخارجي
    print(f"\n[2/3] تجهيز حساب المراقب الكشاف (Watcher)...")
    watcher_conn, actual_watcher = await pick_working_watcher(cache, target_email, watcher_email, target_kingdom)
    if not watcher_conn:
        print("❌ تعذر العثور على حساب مراقب صالح للاتصال بالسيرفر وفحص القلعة!")
        return

    print(f"   ✓ تم الاتصال عبر المراقب: {actual_watcher}")

    # 3. فحص بيانات الحاكم والتحالف من الخارج
    print(f"\n[3/3] فحص بيانات القلعة المستهدفة من الخارج...")
    try:
        # استعلام 1002/7 بروفايل الحاكم
        res_lord = await watcher_conn.query("1002", "7", {"uid": target_uid}, timeout=10)
        lord_data = res_lord.get("data", {}) if res_lord else {}

        base = lord_data.get("base", {})
        online_info = lord_data.get("onlineInfo", {})
        aid = lord_data.get("aid", 0)

        nickname = base.get("nickName", "غير معروف")
        level = base.get("level", 0)
        pos = base.get("sourcePos", {})
        shield_time = base.get("shieldTime", 0)
        online_flag = base.get("onlineFlag", 0)
        last_login = online_info.get("lastLoginTime", 0)
        last_logout = online_info.get("lastLogoutTime", 0)

        # فحص التحالف الرسمي (حقل online = 0 يعني متصل الآن)
        alliance_online = None
        alliance_offline_duration = None

        if aid:
            res_alliance = await watcher_conn.query("1010", "6", {"aid": aid}, timeout=10)
            if res_alliance and "data" in res_alliance:
                retdata = res_alliance["data"].get("retdata", {})
                target_member = retdata.get(str(target_uid)) or retdata.get(int(target_uid))
                if target_member:
                    uinfo = target_member.get("uinfo", {})
                    raw_online = uinfo.get("online")
                    if raw_online == 0:
                        alliance_online = True
                    elif isinstance(raw_online, (int, float)):
                        alliance_online = False
                        alliance_offline_duration = int(raw_online)

        # استنتاج النتيجة النهائية بدقة
        is_online = False
        if alliance_online is not None:
            is_online = alliance_online
        else:
            # في حال لم تكن في تحالف، نعتمد على مقارنة توقيت الدخول والخروج وعلم onlineFlag
            is_online = (online_flag == 1) and (last_login >= last_logout)

        # طباعة التقرير النهائي الأنيق
        print("\n" + "═" * 65)
        print("                  📊 نتيجة الفحص المباشر")
        print("═" * 65)
        print(f"👤 اسم الحاكم       : {nickname}")
        print(f"🏰 مستوى القلعة     : {level}")
        print(f"📍 موقع القلعة      : X={pos.get('x', '?')}, Y={pos.get('y', '?')}")
        print(f"🛡️ التحالف          : {aid if aid else 'لا يوجد تحالف'}")

        if shield_time and shield_time > int(time.time()):
            rem_shield = shield_time - int(time.time())
            print(f"🛡️ درع الحماية      : مفعّل (متبقي {format_duration(rem_shield)})")
        else:
            print(f"🛡️ درع الحماية      : غير مفعّل")

        print("─" * 65)
        if is_online:
            print("🟢 الحالة الحالية  : 【 متصل الآن - القلعة مفتوحة 】")
            print("⚠️ ملاحظة          : يوجد شخص أو بوت متصل بالقلعة حالياً من جهاز آخر!")
        else:
            print("🔴 الحالة الحالية  : 【 غير متصل - القلعة مغلقة 】")
            if alliance_offline_duration:
                print(f"⏱️ مدة الغياب      : مغلقة منذ {format_duration(alliance_offline_duration)}")
            elif last_logout:
                dt_logout = datetime.datetime.fromtimestamp(last_logout).strftime("%Y-%m-%d %H:%M:%S")
                print(f"⏱️ آخر وقت خروج    : {dt_logout}")

        print("═" * 65)
        print("✅ تم الفحص بأمان تام وبدون تسجيل الدخول في حساب القلعة وبدون طرد اللاعب.")
        print("═" * 65)

    finally:
        await watcher_conn.close()


def main():
    parser = argparse.ArgumentParser(description="فاحص حالة القلعة الذكي (كشف التواجد بدون تسجيل الدخول)")
    parser.add_argument("--email", "--target", dest="target", required=True, help="بريد الحساب المراد فحص قلعته")
    parser.add_argument("--watcher", dest="watcher", default=None, help="بريد حساب المراقب (اختياري، يتم اختياره تلقائياً)")

    args = parser.parse_args()
    asyncio.run(check_castle_online(args.target, args.watcher))


if __name__ == "__main__":
    main()
