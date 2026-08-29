# -*- coding: utf-8 -*-
"""
Attack_.py — بوت إرسال المسيرات وجمع الموارد المباشر (Native TCP)
════════════════════════════════════════════════════════════════════════
• يتصل مباشرة بسيرفر اللعبة عبر البروتوكول الأصلي (بدون محاكي أو Frida)
• يدعم أي حساب من session_cache.json (أو كل الحسابات معاً)
• يبحث عن حقول الموارد الأقرب ويفحص البناء ويرسل المسيرة
• يستبعد الأهداف المكررة تلقائياً عبر exclude_history.json
• يدير حالة الأبطال في الذاكرة لمنع تضارب المسيرات

الاستخدام:
    python Attack_.py                           # تشغيل على أول حساب متاح
    python Attack_.py --email user@gmail.com    # تشغيل لحساب محدد
    python Attack_.py --type 4 --max-lv 6       # تحديد نوع المورد والمستوى
    python Attack_.py --all                     # تشغيل على جميع الحسابات في session_cache.json
    python Attack_.py --loop --interval 300     # تكرار دوري كل 5 دقائق
"""

import sys
import os
import time
import json
import logging
import asyncio
import argparse
from typing import List, Dict, Any, Optional

import onemt_auth
from game_client import GameConnection, AccountSession, MultiAccountManager

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("AttackBot")

# ════════════════════════════════════════════════════════════════════
#  إدارة استبعاد الأهداف المكررة (Exclude History)
# ════════════════════════════════════════════════════════════════════

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "exclude_history.json")

def get_exclude_dict(uid: Any) -> Dict[str, bool]:
    """جلب الأهداف المستبعدة لهذا الحساب بصيغة {'id': True}"""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            arr = data.get(str(uid), [])
            return {str(target_id): True for target_id in arr}
    except Exception as e:
        log.warning(f"خطأ في قراءة exclude_history: {e}")
        return {}

def add_to_exclude_history(uid: Any, target_id: Any):
    """إضافة الهدف الجديد للملف (بحد أقصى 15 هدفاً مع حذف الأقدم)"""
    data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}

    uid_str = str(uid)
    if uid_str not in data:
        data[uid_str] = []

    arr = data[uid_str]
    t_id_str = str(target_id)
    if t_id_str not in arr:
        arr.append(t_id_str)

    while len(arr) > 15:
        arr.pop(0)

    data[uid_str] = arr
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning(f"خطأ في حفظ exclude_history: {e}")


# ════════════════════════════════════════════════════════════════════
#  اختيار أبطال الجمع (Hero Selection - هرمية الأولويات)
# ════════════════════════════════════════════════════════════════════

def filter_gathering_heroes(heroes_pool: list, max_count: int = 1, busy_hero_ids: set = None) -> List[int]:
    """
    تصفية واختيار أفضل أبطال الجمع والتنمية من قائمة الأبطال وفق 3 مستويات أولوية:
    1. الأولوية الأولى (الذهبية): بطل جمع وتنمية (5502...) يمتلك مهارة جمع مكتسبة (5620...).
    2. الأولوية الثانية (البديل): أي بطل تطوير وتنمية متاح (5502...) حتى لو لم يتعلم مهارة 5620.
    3. الأولوية الثالثة (البديل العام): أي بطل متاح في القلعة (5501...) لإرسال المسيرة بالجنود وعدم التعطيل.
    """
    busy_ids = busy_hero_ids or set()
    tier1_5620 = []
    tier2_5502 = []
    tier3_general = []

    for hero in heroes_pool:
        if not isinstance(hero, dict):
            continue
        hid = hero.get('id')
        if not hid or hid in busy_ids:
            continue

        # شرط أن يكون البطل متاحاً
        state = hero.get('status', {}).get('state', 0)
        if state != 0:
            continue

        hid_str = str(hid)
        skill_list = hero.get('skillList', {})
        has_5620 = False
        if isinstance(skill_list, dict):
            for slot, sdata in skill_list.items():
                if isinstance(sdata, dict):
                    sid = str(sdata.get('id', ''))
                    if sid.startswith('5620'):
                        has_5620 = True
                        break

        if hid_str.startswith('5502'):
            if has_5620:
                tier1_5620.append(int(hid))
            else:
                tier2_5502.append(int(hid))
        else:
            tier3_general.append(int(hid))

    # 1. إذا وجد بطل جمع بمهارة 5620
    if tier1_5620:
        return tier1_5620[:max_count] if max_count else tier1_5620

    # 2. إذا لم يوجد، اختيار أي بطل تطوير وتنمية 5502
    if tier2_5502:
        return tier2_5502[:max_count] if max_count else tier2_5502

    # 3. إذا لم يوجد، اختيار أي بطل متاح في القلعة 5501
    if tier3_general:
        return tier3_general[:max_count] if max_count else tier3_general

    return []


# ════════════════════════════════════════════════════════════════════
#  منطق هجوم وجمع الموارد للحساب (CastleGatherer)
# ════════════════════════════════════════════════════════════════════

class CastleGatherer:
    """
    مسؤول عن تنفيذ عمليات جمع الموارد وإرسال المسيرات لحساب واحد
    """

    def __init__(self, conn: GameConnection):
        self.conn = conn
        self.uid = conn.uid
        self.heroes: list = []
        self.busy_heroes: set = set()

    async def init_heroes(self):
        """جلب قائمة الأبطال الحقيقية وحالتهم الحالية ومهاراتهم مباشرة من سيرفر اللعبة"""
        self.heroes = []
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # 1. فحص هل تم استقبال الأبطال تلقائياً من الـ Gate
        if self.conn._gate and getattr(self.conn._gate, 'heroes', None):
            self.heroes = list(self.conn._gate.heroes)
            if self.heroes:
                return

        # 2. محاولة استعلام بيانات الحساب اللحظية من السيرفر (1000/1)
        try:
            r_init = await self.conn.query('1000', '1', {}, timeout=2)
            if r_init:
                retdata = r_init.get('data', {}).get('retdata', {}) or r_init.get('retdata', {})
                h_ctrl = retdata.get('heroCtrl', [])
                if isinstance(h_ctrl, list) and h_ctrl:
                    self.heroes = list(h_ctrl)
                    return
        except Exception:
            pass

        # 3. جلب جميع أبطال التشكيلات السريعة (3080/2)
        try:
            r_3080 = await self.conn.query('3080', '2', {'isSelf': True, 'uids': [uid_int]}, timeout=3)
            if r_3080 and 'data' in r_3080:
                list_data = r_3080['data'].get('list', {}).get(str(uid_int), {})
                pages = list_data.get('pages', {})
                for page in pages.values():
                    for h_obj in page.get('heros', []):
                        hid = h_obj.get('id') if isinstance(h_obj, dict) else h_obj
                        if hid and not any(h.get('id') == hid for h in self.heroes):
                            self.heroes.append({'id': hid, 'status': {'state': 0}, 'skillList': {}})
        except Exception:
            pass

        # 4. جلب جميع الأبطال من تشكيلات الجيش (1005/7 لجميع الخانات من 1 إلى 10)
        for ctype in range(1, 11):
            try:
                form_res = await self.conn.query('1005', '7', {"compiletype": ctype}, timeout=2)
                if form_res and 'data' in form_res:
                    c_heroes = form_res['data'].get('compileHeros', [])
                    for hid in c_heroes:
                        if hid and not any(h.get('id') == hid for h in self.heroes):
                            self.heroes.append({'id': hid, 'status': {'state': 0}, 'skillList': {}})
            except Exception:
                pass

    async def execute_gather(self, res_type: int = 4, min_lv: int = 5, max_lv: int = 6, search_range: int = 100) -> str:
        """
        تنفيذ مسيرة واحدة.
        تعيد:
        - "SUCCESS": تم إرسال المسيرة بنجاح
        - "QUEUE_FULL": طوابير المسيرات ممتلئة (كود 8004)
        - "NO_HEROES": لا يوجد أبطال جمع متاحين
        - "NO_TARGET": لا توجد حقول قريبة
        - "HERO_BUSY": البطل مشغول على السيرفر
        - "ERROR": خطأ آخر
        """
        email = self.conn.account.email
        uid_int = int(self.uid) if str(self.uid).isdigit() else self.uid

        # اختيار البطل المناسب وفق الأولويات
        await self.init_heroes()
        selected_heroes = filter_gathering_heroes(self.heroes, max_count=1, busy_hero_ids=self.busy_heroes)
        if not selected_heroes:
            log.warning(f"[{email}] ⚠️ لا يوجد أي بطل متاح في القلعة حالياً!")
            return "NO_HEROES"

        # فحص تصنيف البطل المختار لإشعار المستخدم
        chosen_hid = selected_heroes[0]
        chosen_str = str(chosen_hid)
        has_5620 = False
        for h in self.heroes:
            if h.get('id') == chosen_hid:
                skills = h.get('skillList', {})
                if isinstance(skills, dict) and any(str(s.get('id','')).startswith('5620') for s in skills.values() if isinstance(s, dict)):
                    has_5620 = True
                break

        if has_5620:
            hero_desc = "بطل جمع يمتلك مهارة 5620"
        elif chosen_str.startswith('5502'):
            hero_desc = "بطل تطوير وتنمية 5502"
        else:
            hero_desc = "بطل قلعة متاح 5501"

        log.info(f"[{email}] 🌾 البطل المختار ({hero_desc}): {selected_heroes}")

        # جلب إحداثيات القلعة
        r_castle = await self.conn.query('1006', '25', {"uid": uid_int})
        if not r_castle or not r_castle.get('retData'):
            log.error(f"[{email}] ❌ فشل جلب بيانات القلعة!")
            return "ERROR"

        c_info = r_castle['retData']
        cx, cy = c_info.get('x'), c_info.get('y')

        # جلب خريطة الأهداف المستبعدة
        exclude_map = get_exclude_dict(self.uid)

        # البحث في الخريطة عن موارد قريبة
        log.info(f"[{email}] 🔍 البحث عن حقل مورد (نوع={res_type}, لفل={min_lv}-{max_lv})...")
        r_search = await self.conn.query('2011', '3', {
            "mapType": 5,
            "num": 1,
            "subType": res_type,
            "y": cy,
            "x": cx,
            "exclude": exclude_map,
            "minLv": min_lv,
            "maxLv": max_lv,
            "range": search_range
        })

        if not r_search or not r_search.get('result'):
            log.warning(f"[{email}] ⚠️ لم يتم العثور على حقول متاحة في النطاق المحدد!")
            return "NO_TARGET"

        target = r_search['result'][0]
        target_id = target.get('id')
        tx, ty = target.get('x'), target.get('y')
        log.info(f"[{email}] 🎯 تم العثور على هدف: ID={target_id} عند ({tx}, {ty})")

        # حفظ الهدف في قائمة الاستبعاد
        add_to_exclude_history(self.uid, target_id)

        # جلب معرف المملكة والخريطة
        kingdom_id = 0
        if self.conn.kingdom_id:
            try: kingdom_id = int(self.conn.kingdom_id)
            except: pass
        if not kingdom_id:
            r_map = await self.conn.query('1002', '7', {"uid": uid_int})
            if r_map and 'data' in r_map:
                kingdom_id = r_map['data'].get('base', {}).get('partition', 0)

        # جلب تشكيل الجيش
        r_form = await self.conn.query('1005', '7', {"compiletype": 1})
        compile_army = {}
        if r_form and 'data' in r_form:
            compile_army = r_form['data'].get('compileArmy', {})

        if not compile_army:
            r_form2 = await self.conn.query('1005', '7', {"compiletype": 2})
            if r_form2 and 'data' in r_form2:
                compile_army = r_form2['data'].get('compileArmy', {})

        # تجهيز قائمة الجيش مع توزيع متوازن يسمح بإرسال عدة مسيرات متتالية
        army_list = []
        if compile_army:
            for k, v in compile_army.items():
                v_int = int(v)
                if v_int > 0:
                    army_count = min(v_int, 20000)
                    army_list.append({"id": int(k), "num": army_count})

        if not army_list:
            army_list = [{"id": 501, "num": 1000}]

        # جلب بيانات مورد البناء
        r_build = await self.conn.query('1006', '15', {
            "x": tx, "y": ty, "kingdomId": kingdom_id, "id": target_id
        })
        current_res_num = 0
        if r_build and 'retData' in r_build:
            res_obj = r_build['retData'].get('resource', {})
            current_res_num = res_obj.get('currentSourceNum', 0)

        # إرسال أمر المسيرة النهائي
        march_payload = {
            "needSend": False,
            "runePages": {},
            "heros": selected_heroes,
            "matrixType": 3,
            "mapId": kingdom_id,
            "moveLineType": 3,
            "data": {
                "data": {
                    "currentSourceNum": current_res_num,
                    "resourceType": 1000 + res_type
                },
                "to": {
                    "y": ty,
                    "x": tx,
                    "id": target_id
                },
                "army": army_list
            },
            "pets": []
        }

        log.info(f"[{email}] 🚀 إرسال أمر المسيرة إلى السيرفر (1007/2)...")
        r_march = await self.conn.query('1007', '2', march_payload)

        if r_march:
            err = str(r_march.get('err', '0'))
            if err == '0':
                log.info(f"[{email}] ✅ تم إرسال المسيرة بنجاح! 🌾 Target={target_id} | Heroes={selected_heroes}")
                for hid in selected_heroes:
                    self.busy_heroes.add(hid)
                return "SUCCESS"
            elif err in ('8004', '9007004'):
                log.info(f"[{email}] 🛑 اكتملت طوابير المسيرات للقلعة (تم الوصول للحد الأقصى من المسيرات - كود {err}).")
                return "QUEUE_FULL"
            elif err == '9007020':
                log.warning(f"[{email}] ⚠️ البطل {selected_heroes} مشغول بالفعل على السيرفر.")
                for hid in selected_heroes:
                    self.busy_heroes.add(hid)
                return "HERO_BUSY"
            else:
                log.error(f"[{email}] ❌ فشل إرسال المسيرة - كود الخطأ: {err}")
                return "ERROR"
        else:
            log.error(f"[{email}] ❌ لم يستجب السيرفر لأمر المسيرة!")
            return "ERROR"

    async def send_marches_until_full(self, res_type: int = 4, min_lv: int = 5, max_lv: int = 6, search_range: int = 100, max_marches: int = 6):
        """إرسال مسيرات متتالية حتى تمتلئ جميع الطوابير المتاحة أو تنفد الأبطال"""
        email = self.conn.account.email
        sent_count = 0

        for i in range(1, max_marches + 1):
            log.info(f"[{email}] ⚔️ محاولة إرسال المسيرة رقم ({i})...")
            status = await self.execute_gather(
                res_type=res_type,
                min_lv=min_lv,
                max_lv=max_lv,
                search_range=search_range
            )

            if status == "SUCCESS":
                sent_count += 1
                await asyncio.sleep(1.5)  # مهلة قصيرة بين كل مسيرة
            elif status in ("QUEUE_FULL", "NO_HEROES", "NO_TARGET"):
                break
            elif status == "HERO_BUSY":
                # إعادة المحاولة فوراً مع بطل آخر
                continue
            else:
                break

        log.info(f"[{email}] 🏁 ملخص المسيرات: تم إرسال {sent_count} مسيرة/مسيرات بنجاح.")


# ════════════════════════════════════════════════════════════════════
#  المشغل الرئيسي (Single / Multi Account Runner)
# ════════════════════════════════════════════════════════════════════

async def run_single_account(acc: AccountSession, args: argparse.Namespace):
    """تشغيل منطق البوت لحساب واحد"""
    log.info(f"\n{'═'*55}\n  🔌 بدء العمل على الحساب: {acc.email}\n{'═'*55}")
    conn = GameConnection(acc)

    if not await conn.connect():
        log.error(f"[{acc.email}] ❌ فشل تسجيل الدخول والاتصال بالـ Gate!")
        return

    log.info(f"[{acc.email}] ✓ متصل بنجاح! UID={conn.uid} | Server={conn.server_name}")
    gatherer = CastleGatherer(conn)

    while True:
        try:
            await gatherer.send_marches_until_full(
                res_type=args.type,
                min_lv=args.min_lv,
                max_lv=args.max_lv,
                search_range=args.range,
                max_marches=args.max_marches
            )
        except Exception as e:
            log.error(f"[{acc.email}] حدث خطأ أثناء تنفيذ المسيرات: {e}")

        if not args.loop:
            break

        log.info(f"[{acc.email}] ⏳ انتظار {args.interval} ثانية قبل الجولة القادمة من المسيرات...")
        await asyncio.sleep(args.interval)

    await conn.close()
    log.info(f"[{acc.email}] اكتملت مهام الحساب.")


async def main():
    parser = argparse.ArgumentParser(
        description="Empire Native Bot - بوت إرسال المسيرات المباشر بدون محاكي",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب المطلوب تشغيله")
    parser.add_argument("--password", "-p", help="كلمة المرور للحساب في حال تشغيله لأول مرة بدون محاكي")
    parser.add_argument("--all", "-a", action="store_true", help="تشغيل على جميع الحسابات في session_cache.json بالتوازي")
    parser.add_argument("--type", "-t", type=int, default=4, help="نوع مورد الجمع (1=مزارع, 2=خشب, 3=حجر, 4=حديد/ذهب) [افتراضي: 4]")
    parser.add_argument("--min-lv", type=int, default=5, help="أدنى مستوى للحقل [افتراضي: 5]")
    parser.add_argument("--max-lv", type=int, default=6, help="أعلى مستوى للحقل [افتراضي: 6]")
    parser.add_argument("--range", "-r", type=int, default=100, help="نطاق البحث [افتراضي: 100]")
    parser.add_argument("--max-marches", "-m", type=int, default=6, help="الحد الأقصى لعدد المسيرات لكل قلعة [افتراضي: 6]")
    parser.add_argument("--loop", "-l", action="store_true", help="تكرار المهمة دورياً")
    parser.add_argument("--interval", "-i", type=int, default=300, help="المدة بالثواني بين كل تكرار [افتراضي: 300]")
    args = parser.parse_args()

    cache_path = os.path.join(os.path.dirname(__file__), "session_cache.json")
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)

    accounts_map = cache.get('accounts', {})

    # إذا تم تمرير الإيميل وكلمة المرور، المصادقة السحابية مباشرة وحفظ الجلسة
    if args.email and args.password:
        log.info(f"🔐 جاري تسجيل الدخول السحابي للحساب [{args.email}]...")
        auth_res = onemt_auth.sdk_login(args.email, args.password)
        if auth_res.get('success'):
            accounts_map[args.email] = {
                "userId": auth_res['userId'],
                "sessionId": auth_res['sessionId'],
                "timestamp": time.time(),
                "source": "sdk_password_login"
            }
            cache['accounts'] = accounts_map
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            log.info(f"✅ تم توثيق الحساب بنجاح وحفظه في session_cache.json!")
        else:
            log.error(f"❌ فشل تسجيل الدخول: {auth_res.get('error_msg')} (رمز الخطأ: {auth_res.get('error_code')})")
            sys.exit(1)

    # إذا طلب حساب غير مسجل، نطلب كلمة المرور في الطرفية
    elif args.email and args.email not in accounts_map:
        log.info(f"ℹ️ الحساب '{args.email}' غير مسجل مسبقاً في session_cache.json.")
        pwd_input = input(f"🔑 أدخل كلمة المرور للحساب ({args.email}): ").strip()
        if pwd_input:
            log.info(f"🔐 جاري المصادقة السحابية مع خوادم ONEMT...")
            auth_res = onemt_auth.sdk_login(args.email, pwd_input)
            if auth_res.get('success'):
                accounts_map[args.email] = {
                    "userId": auth_res['userId'],
                    "sessionId": auth_res['sessionId'],
                    "timestamp": time.time(),
                    "source": "interactive_password_login"
                }
                cache['accounts'] = accounts_map
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, indent=2, ensure_ascii=False)
                log.info(f"✅ تم تسجيل وتوثيق الحساب بنجاح!")
            else:
                log.error(f"❌ فشل تسجيل الدخول: {auth_res.get('error_msg')} (رمز الخطأ: {auth_res.get('error_code')})")
                sys.exit(1)
        else:
            log.error("❌ لم يتم إدخال كلمة المرور.")
            sys.exit(1)

    if not accounts_map:
        log.error("لا توجد حسابات مسجلة في session_cache.json!")
        sys.exit(1)

    if args.all:
        log.info(f"🚀 تشغيل البوت على جميع الحسابات ({len(accounts_map)} حساب بالتوازي)...")
        tasks = [
            run_single_account(AccountSession(email, info['userId'], info['sessionId']), args)
            for email, info in accounts_map.items()
        ]
        await asyncio.gather(*tasks)

    elif args.email:
        info = accounts_map[args.email]
        acc = AccountSession(args.email, info['userId'], info['sessionId'])
        await run_single_account(acc, args)

    else:
        # تشغيل أول حساب متاح تلقائياً
        first_email, info = next(iter(accounts_map.items()))
        log.info(f"[*] لم يتم تحديد حساب، سيتم التشغيل على أول حساب متاح: {first_email}")
        acc = AccountSession(first_email, info['userId'], info['sessionId'])
        await run_single_account(acc, args)


if __name__ == "__main__":
    asyncio.run(main())
