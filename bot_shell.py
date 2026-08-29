"""
bot_shell.py
══════════════════════════════════════════════════════════════════════════
  🎮 Empire Native Interactive Shell (وحدة التحكم التفاعلية المباشرة)
══════════════════════════════════════════════════════════════════════════
- يحافظ على اتصال TCP دائم (مستقر) بالسيرفر بدون إعادة تسجيل الدخول في كل مرة.
- يدعم إعادة التحميل الساخن (Hot Reload) لملفاتك (مثل Attack_.py) فور تعديلها.
- يتيح لك تنفيذ أي سكريبت أو أمر بسرعة البرق أثناء التطوير دون طرد الحساب.
"""

import os
import sys
import time
import json
import asyncio
import logging
import argparse
import shlex
import importlib
import importlib.util
import traceback
import getpass
from typing import Dict, Any, Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import Attack_
import onemt_auth
from game_client import GameConnection, AccountSession, log


CACHE_FILE = os.path.join(os.path.dirname(__file__), "session_cache.json")


def sync_accounts_from_emulator() -> dict:
    """استيراد الحسابات تلقائياً من المحاكي عبر ADB وحفظها في session_cache.json"""
    try:
        import extract_session_adb
        devices = extract_session_adb.get_devices()
        if not devices:
            return {}
        content = extract_session_adb.read_sdk_email_xml(devices[0])
        if not content:
            return {}
        new_accs = extract_session_adb.parse_accounts(content)
        if not new_accs:
            return {}

        cache = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)

        accounts = cache.get('accounts', {})
        for email, acc in new_accs.items():
            accounts[email] = {
                "userId": acc['userId'],
                "sessionId": acc['sessionId'],
                "timestamp": time.time(),
                "source": "adb_sdk_email"
            }

        cache['accounts'] = accounts
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)

        return accounts
    except Exception as e:
        return {}


class BotShell:
    def __init__(self, email: str):
        self.email = email
        self.conn: Optional[GameConnection] = None
        self.is_running = True
        self.accounts_map = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.accounts_map = data.get('accounts', {})

        # إذا لم يكن الحساب موجوداً، نجرب المزامنة التلقائية من المحاكي فوراً
        if self.email and self.email not in self.accounts_map:
            synced = sync_accounts_from_emulator()
            if synced:
                self.accounts_map = synced
                if self.email in self.accounts_map:
                    print(f"✨ تم اكتشاف واستيراد الحساب [{self.email}] تلقائياً من المحاكي!")

    async def start(self):
        """بدء الاتصال وتشغيل حلقة الأوامر التفاعلية"""
        if self.email not in self.accounts_map:
            print(f"\n❌ الحساب '{self.email}' غير موجود في {CACHE_FILE}")
            print(f"الحسابات المتاحة: {list(self.accounts_map.keys())}\n")
            return

        info = self.accounts_map[self.email]
        acc = AccountSession(self.email, info['userId'], info['sessionId'])

        print(f"\n{'═'*60}")
        print(f"  🔌 جاري الاتصال الثابت بالسيرفر للحساب: {self.email}")
        print(f"{'═'*60}\n")

        self.conn = GameConnection(acc)
        if not await self.conn.connect():
            print("❌ فشل الاتصال بالسيرفر!")
            return

        print(f"\n✅ متصل بنجاح ودائم! UID={self.conn.uid} | Kingdom={self.conn.kingdom_id}")
        self._print_help()

        # تشغيل مهمة Keep-Alive في الخلفية لمنع قطع الاتصال
        keepalive_task = asyncio.create_task(self._keepalive_loop())

        try:
            await self._repl_loop()
        finally:
            self.is_running = False
            keepalive_task.cancel()
            if self.conn:
                await self.conn.close()
            print("\n👋 تم إغلاق الاتصال وإنهاء الـ Shell بنجاح.")

    async def _keepalive_loop(self):
        """إرسال نبضات خفيفة دورية للحفاظ على بقاء الاتصال حياً"""
        while self.is_running and self.conn and self.conn.is_connected:
            try:
                await asyncio.sleep(45)
                # إرسال استعلام زمني خفيف للحفاظ على المقبس مفتوحاً
                if self.conn and self.conn.is_connected:
                    self.conn.send_nowait('1009', '36', {})
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def _print_help(self):
        print("""
╔══════════════════════════════════════════════════════════════════════════╗
║                     📌 الأوامر التفاعلية المتاحة                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║  login <email> <password>  : تسجيل دخول سحابي فوري لأي حساب جديد        ║
║  attack / gather [خيارات]  : تشغيل مسيرات الجمع (مثال: attack -t 4 -m 5)║
║  port / harbor             : استلام مكافآت الميناء وصناديق الوقت اليومية║
║  heroes                    : عرض قائمة الأبطال وحالتهم الحالية          ║
║  castle                    : عرض إحداثيات ومعلومات ومستوى القلعة        ║
║  search <نوع> <أدنى> <أعلى>: البحث عن حقول الموارد بالخريطة             ║
║  query <cmd> <subcmd> [json]: إرسال أي حزمة واستعراض رد السيرفر فوراً   ║
║  accounts / list           : عرض جميع الحسابات المسجلة وحالتها          ║
║  sync / import             : استيراد وتحديث كل الحسابات من المحاكي (ADB)║
║  add <email> <uid> <token> : إضافة أو تحديث بيانات أي حساب يدوياً        ║
║  switch <email>            : التبديل إلى حساب آخر داخل نفس الجلسة       ║
║  reload                    : إعادة تحميل ملفات الكود المعدلة فوراً      ║
║  run <script.py> [args]    : تشغيل أي ملف بايثون وتمرير الاتصال المباشر ║
║  help                      : عرض قائمة المساعدة                         ║
║  exit / quit               : الخروج وإغلاق الاتصال                      ║
╚══════════════════════════════════════════════════════════════════════════╝
""")

    async def _repl_loop(self):
        loop = asyncio.get_running_loop()
        while self.is_running:
            try:
                prompt = f"Empire [{self.email}]> "
                # قراءة المدخلات في Thread منفصل لعدم تجميد شبكة الـ Async
                line = await loop.run_in_executor(None, input, prompt)
                line = line.strip()
                if not line:
                    continue

                parts = shlex.split(line)
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in ('exit', 'quit', 'q'):
                    break
                elif cmd in ('help', '?'):
                    self._print_help()
                elif cmd == 'reload':
                    self._cmd_reload()
                elif cmd == 'login':
                    await self._cmd_auth_login(args)
                elif cmd in ('attack', 'gather', 'march'):
                    await self._cmd_attack(args)
                elif cmd in ('port', 'harbor'):
                    await self._cmd_port()
                elif cmd == 'heroes':
                    await self._cmd_heroes()
                elif cmd == 'castle':
                    await self._cmd_castle()
                elif cmd == 'search':
                    await self._cmd_search(args)
                elif cmd == 'query':
                    await self._cmd_query(args)
                elif cmd in ('accounts', 'list'):
                    self._cmd_list_accounts()
                elif cmd in ('sync', 'import'):
                    self._cmd_sync_accounts()
                elif cmd == 'add':
                    self._cmd_add_account(args)
                elif cmd == 'run':
                    await self._cmd_run_script(args)
                elif cmd == 'switch':
                    if args:
                        await self._cmd_switch(args[0])
                    else:
                        print("الاستخدام: switch email@domain.com")
                else:
                    print(f"⚠️ أمر غير معروف: '{cmd}'. اكتب help لعرض الأوامر.")

            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"❌ خطأ أثناء تنفيذ الأمر: {e}")
                traceback.print_exc()

    async def _cmd_auth_login(self, args: list):
        """تسجيل دخول حساب جديد مباشرة عبر السيرفر بالإيميل وكلمة المرور فقط"""
        if len(args) < 2:
            print("الاستخدام: login email@domain.com password")
            return
        em, pwd = args[0], args[1]
        print(f"\n🔐 جاري المصادقة السحابية مع خوادم ONEMT للحساب: {em}...")
        res = onemt_auth.sdk_login(em, pwd)
        if res.get('success'):
            uid = res['userId']
            sess = res['sessionId']
            print(f"✅ تم تسجيل الدخول بنجاح! UID={uid}")
            self._cmd_add_account([em, uid, sess])
            await self._cmd_switch(em)
        else:
            print(f"❌ فشل تسجيل الدخول: {res.get('error_msg')} (رمز الخطأ: {res.get('error_code')})\n")

    def _cmd_list_accounts(self):
        """عرض جميع الحسابات المسجلة"""
        self._load_cache()
        print(f"\n{'═'*65}")
        print(f"  📋 قائمة الحسابات المسجلة ({len(self.accounts_map)} حساب):")
        print(f"{'═'*65}")
        for i, (em, info) in enumerate(self.accounts_map.items(), 1):
            is_cur = " 🟢 (الحساب الحالي)" if em == self.email else ""
            uid = info.get('userId', 'N/A')
            src = info.get('source', 'unknown')
            print(f" {i}. {em:<30} | UID: {uid[:12]}... | المصدر: {src}{is_cur}")
        print(f"{'═'*65}\n")

    def _cmd_sync_accounts(self):
        """استيراد الحسابات من المحاكي"""
        print("\n🔄 جاري فحص واستيراد الحسابات من المحاكي (ADB)...")
        synced = sync_accounts_from_emulator()
        if synced:
            self.accounts_map = synced
            print(f"✅ تم العثور على {len(synced)} حساب/حسابات وتحديث {CACHE_FILE} بنجاح!")
            self._cmd_list_accounts()
        else:
            print("⚠️ لم يتم العثور على أجهزة محاكي متصلة أو ملفات جلسات جديدة.\n")

    def _cmd_add_account(self, args: list):
        """إضافة حساب يدوياً"""
        if len(args) < 3:
            print("الاستخدام: add <email> <userId> <sessionId>")
            return
        em, uid, sess = args[0], args[1], args[2]
        self._load_cache()
        cache = {}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        
        accounts = cache.get('accounts', {})
        accounts[em] = {
            "userId": uid,
            "sessionId": sess,
            "timestamp": time.time(),
            "source": "manual_add"
        }
        cache['accounts'] = accounts
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        self.accounts_map = accounts
        print(f"✅ تم حفظ الحساب [{em}] بنجاح في {CACHE_FILE}!")

    def _cmd_reload(self):
        """إعادة تحميل الملفات الساخنة دون قطع الاتصال"""
        try:
            importlib.reload(Attack_)
            print("🔄 تم إعادة تحميل ملف [Attack_.py] بنجاح! التعديلات أصبحت سارية فوراً.")
        except Exception as e:
            print(f"❌ خطأ أثناء إعادة التحميل: {e}")

    async def _cmd_attack(self, args: list):
        """تشغيل منطق إرسال المسيرات عبر Attack_.py بعد إعادة تحميله تلقائياً"""
        self._cmd_reload()

        parser = argparse.ArgumentParser(prog="attack", add_help=False)
        parser.add_argument("--type", "-t", type=int, default=4)
        parser.add_argument("--min-lv", type=int, default=5)
        parser.add_argument("--max-lv", type=int, default=6)
        parser.add_argument("--range", "-r", type=int, default=100)
        parser.add_argument("--max-marches", "-m", type=int, default=6)

        try:
            parsed = parser.parse_args(args)
        except Exception:
            print("الخيارات: attack [-t 1..4] [--min-lv 5] [--max-lv 6] [-r 100] [-m 6]")
            return

        gatherer = Attack_.CastleGatherer(self.conn)
        print(f"\n🚀 بدء تنفيذ مسيرات الجمع على الحساب [{self.email}] (نوع={parsed.type}, الحد={parsed.max_marches})...")
        await gatherer.send_marches_until_full(
            res_type=parsed.type,
            min_lv=parsed.min_lv,
            max_lv=parsed.max_lv,
            search_range=parsed.range,
            max_marches=parsed.max_marches
        )
        print("✅ اكتمل تنفيذ أمر الجمع.\n")

    async def _cmd_port(self):
        """استلام مكافأة الميناء وصناديق الوقت اليومية وشحنات الميناء"""
        print(f"\n⚓ فحص واستلام مكافآت الميناء للحساب [{self.email}]...")
        claimed_boxes = 0
        for seq in range(1, 9):
            r = await self.conn.query('1033', '2', {'sequence': seq}, timeout=3)
            if r and str(r.get('err', '')) == '0':
                claimed_boxes += 1
                rdata = r.get('data', {}).get('data', {}) or {}
                reward = rdata.get('reward', [])
                print(f" • 🎁 تم استلام صندوق الميناء رقم ({seq}) بنجاح! المكافأة: {reward}")
            elif r and str(r.get('err', '')) not in ('0', ''):
                pass

        if claimed_boxes > 0:
            print(f"✅ تم استلام إجمالي {claimed_boxes} صندوق/صناديق ميناء بنجاح.")
        else:
            print("ℹ️ صناديق الوقت بالميناء تم استلامها مسبقاً أو لم تكتمل بعد.")

        # استلام تفويضات شحنات الميناء (3148/5)
        r_consign = await self.conn.query('3148', '5', {}, timeout=3)
        if r_consign and str(r_consign.get('err', '')) == '0':
            print("✅ تم استلام عوائد شحنة الميناء بنجاح.")
        print("⚓ اكتمل فحص الميناء.\n")

    async def _cmd_heroes(self):
        """عرض جميع أبطال الحساب وحالتهم"""
        self._cmd_reload()
        gatherer = Attack_.CastleGatherer(self.conn)
        await gatherer.init_heroes()

        heroes = gatherer.heroes
        print(f"\n{'═'*65}")
        print(f"  🏰 أبطال القلعة للحساب: {self.email} (الإجمالي: {len(heroes)})")
        print(f"{'═'*65}")

        for h in heroes:
            hid = str(h.get('id', ''))
            state = h.get('status', {}).get('state', 0)
            state_desc = "🟢 متاح (Idle)" if state == 0 else f"🔴 مشغول (State={state})"
            
            # تصنيف البطل
            if hid.startswith('5502'):
                htype = "🌾 تطوير وتنمية (5502)"
            elif hid.startswith('5501'):
                htype = "⚔️ عسكري أساسي (5501)"
            else:
                htype = f"⭐ بطل ({hid[:4]})"

            skills = h.get('skillList', {})
            sids = [str(s.get('id', '')) for s in skills.values() if isinstance(s, dict)]
            has_5620 = any(s.startswith('5620') for s in sids)
            skill_mark = " [✨ مهارة جمع 5620]" if has_5620 else ""

            print(f" • بطل {hid} | {htype:<22} | {state_desc} {skill_mark}")
            if sids:
                print(f"    └── المهارات: {sids}")
        print()

    async def _cmd_castle(self):
        """عرض معلومات القلعة"""
        uid_int = int(self.conn.uid) if str(self.conn.uid).isdigit() else self.conn.uid
        r = await self.conn.query('1006', '25', {"uid": uid_int}, timeout=5)
        info = None
        if r:
            info = r.get('retData') or r.get('data', {}).get('retdata', {}) or r.get('data', {})
        if info and isinstance(info, dict) and ('x' in info or 'level' in info):
            print(f"\n🏰 بيانات القلعة:")
            print(f" • UID: {uid_int}")
            print(f" • الاسم: {info.get('nickName', 'N/A')}")
            print(f" • المستوى: {info.get('level', 'N/A')}")
            print(f" • الإحداثيات: X={info.get('x')}, Y={info.get('y')}")
            print(f" • المملكة: {self.conn.kingdom_id}")
            print(f" • السيرفر: {self.conn.server_name}\n")
        else:
            print("❌ لم يستجب السيرفر لبيانات القلعة!")

    async def _cmd_search(self, args: list):
        """البحث في الخريطة"""
        res_type = int(args[0]) if len(args) > 0 else 4
        min_lv = int(args[1]) if len(args) > 1 else 5
        max_lv = int(args[2]) if len(args) > 2 else 6
        search_range = int(args[3]) if len(args) > 3 else 100

        uid_int = int(self.conn.uid) if str(self.conn.uid).isdigit() else self.conn.uid
        r_castle = await self.conn.query('1006', '25', {"uid": uid_int})
        cx, cy = 0, 0
        if r_castle:
            info = r_castle.get('retData') or r_castle.get('data', {}).get('retdata', {}) or r_castle.get('data', {})
            if isinstance(info, dict):
                cx, cy = info.get('x', 0), info.get('y', 0)

        if not cx and not cy:
            print("❌ تعذر جلب إحداثيات القلعة للبحث.")
            return

        print(f"🔍 البحث من موقع القلعة ({cx}, {cy}) عن مورد نوع {res_type} لفل {min_lv}-{max_lv}...")
        
        r_search = await self.conn.query('2011', '3', {
            "mapType": 5, "num": 5, "subType": res_type,
            "y": cy, "x": cx, "minLv": min_lv, "maxLv": max_lv, "range": search_range
        })

        if r_search and r_search.get('result'):
            print(f"\n🎯 الأهداف التي تم العثور عليها ({len(r_search['result'])} حقول):")
            for t in r_search['result']:
                print(f" • Target ID: {t.get('id')} عند ({t.get('x')}, {t.get('y')})")
            print()
        else:
            print("⚠️ لم يتم العثور على أهداف في النطاق المحدد.\n")

    async def _cmd_query(self, args: list):
        """إرسال حزمة خام"""
        if len(args) < 2:
            print("الاستخدام: query <cmd> <subcmd> [json_data]")
            return
        cmd, subcmd = args[0], args[1]
        data = {}
        if len(args) > 2:
            try:
                data = json.loads(" ".join(args[2:]))
            except Exception as e:
                print(f"❌ خطأ في تنسيق JSON: {e}")
                return

        print(f"📡 إرسال الطلب ({cmd}/{subcmd})...")
        r = await self.conn.query(cmd, subcmd, data, timeout=10)
        print(f"📥 الرد:\n{json.dumps(r, ensure_ascii=False, indent=2)}\n")

    async def _cmd_run_script(self, args: list):
        """تشغيل ملف بايثون خارجي وتمرير كائن الاتصال النشط له"""
        if not args:
            print("الاستخدام: run <file.py> [args]")
            return
        script_path = args[0]
        if not os.path.exists(script_path):
            print(f"❌ الملف '{script_path}' غير موجود!")
            return

        print(f"▶️ تشغيل السكريبت [{script_path}] على الاتصال النشط...")
        try:
            spec = importlib.util.spec_from_file_location("user_script", script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, 'run_with_conn'):
                if asyncio.iscoroutinefunction(module.run_with_conn):
                    await module.run_with_conn(self.conn, args[1:])
                else:
                    module.run_with_conn(self.conn, args[1:])
            elif hasattr(module, 'main'):
                if asyncio.iscoroutinefunction(module.main):
                    await module.main()
                else:
                    module.main()
            else:
                print(f"⚠️ الملف {script_path} تم تنفيذه لكنه لا يحتوي على دالة run_with_conn(conn, args).")
        except Exception as e:
            print(f"❌ خطأ أثناء تشغيل الملف: {e}")
            traceback.print_exc()

    async def _cmd_switch(self, new_email: str):
        """التبديل إلى حساب آخر"""
        self._load_cache()
        if new_email not in self.accounts_map:
            synced = sync_accounts_from_emulator()
            if synced:
                self.accounts_map = synced

        if new_email not in self.accounts_map:
            print(f"\n❌ الحساب '{new_email}' غير مسجل في session_cache.json")
            print(f"الحسابات المتاحة: {list(self.accounts_map.keys())}")
            print("💡 يمكنك إضافة الحساب عبر: add <email> <userId> <sessionId>\n")
            return

        if self.conn:
            await self.conn.close()

        self.email = new_email
        info = self.accounts_map[self.email]
        acc = AccountSession(self.email, info['userId'], info['sessionId'])

        print(f"\n🔄 جاري التبديل إلى الحساب: {self.email}...")
        self.conn = GameConnection(acc)
        if await self.conn.connect():
            print(f"✅ تم الاتصال بنجاح بالحساب الجديد: {self.email} (UID={self.conn.uid})\n")
        else:
            print(f"❌ فشل الاتصال بالحساب: {self.email}\n")


async def main():
    parser = argparse.ArgumentParser(description="Empire Interactive Bot Shell")
    parser.add_argument("--email", "-e", help="البريد الإلكتروني للحساب المطلوب تسجيل الدخول إليه")
    parser.add_argument("--password", "-p", help="كلمة المرور للحساب في حال تسجيل الدخول لأول مرة بدون محاكي")
    parser.add_argument("--uid", "-u", help="معرف المستخدم (UserId) في حال إضافة حساب جديد مباشرة")
    parser.add_argument("--session", "-s", help="رمز الجلسة (SessionId) في حال إضافة حساب جديد مباشرة")
    args = parser.parse_args()

    cache_path = CACHE_FILE
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache = json.load(f)

    accounts_map = cache.get('accounts', {})

    # إذا تم تمرير البريد وكلمة المرور مباشرة، المصادقة السحابية فوراً
    if args.email and args.password:
        print(f"🔐 جاري تسجيل الدخول عبر البريد وكلمة المرور للحساب [{args.email}]...")
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
            print(f"✅ تم توثيق الحساب بنجاح عبر السيرفر وحفظه في session_cache.json!")
        else:
            print(f"❌ فشل تسجيل الدخول: {auth_res.get('error_msg')} (رمز الخطأ: {auth_res.get('error_code')})")
            sys.exit(1)

    # إذا تم تمرير بيانات uid و session مباشرة
    elif args.email and args.uid and args.session:
        accounts_map[args.email] = {
            "userId": args.uid,
            "sessionId": args.session,
            "timestamp": time.time(),
            "source": "cli_argument"
        }
        cache['accounts'] = accounts_map
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        print(f"✅ تم تسجيل الحساب الجديد [{args.email}] في session_cache.json!")

    # إذا طلب المستخدم إيميل غير مسجل، نطلب كلمة المرور منه في الطرفية
    elif args.email and args.email not in accounts_map:
        print(f"\nℹ️ الحساب '{args.email}' غير مسجل مسبقاً في الذاكرة.")
        pwd_input = input(f"🔑 أدخل كلمة المرور للحساب ({args.email}): ").strip()
        if pwd_input:
            print(f"🔐 جاري المصادقة السحابية مع خوادم اللعبة...")
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
                print(f"✅ تم تسجيل وتوثيق الحساب بنجاح!")
            else:
                print(f"❌ فشل تسجيل الدخول: {auth_res.get('error_msg')} (رمز الخطأ: {auth_res.get('error_code')})")
                sys.exit(1)
        else:
            print("❌ لم يتم إدخال كلمة المرور.")
            sys.exit(1)

    if not accounts_map:
        accounts_map = sync_accounts_from_emulator()

    email = args.email
    if not email:
        if accounts_map:
            email = next(iter(accounts_map.keys()))
            print(f"[*] لم يتم تحديد حساب، سيتم الاتصال بأول حساب متاح: {email}")
        else:
            print("❌ لا توجد حسابات متاحة في session_cache.json!")
            sys.exit(1)

    shell = BotShell(email)
    await shell.start()


if __name__ == "__main__":
    asyncio.run(main())
