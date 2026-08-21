"""
test_cmd.py — أداة اختبار عامة
تتصل بالـ Gate وتستقبل كل البيانات الأولية من السيرفر
ثم تعرضها وتحفظها في game_data.json
"""
import sys, os, json, time, threading
sys.path.insert(0, os.path.dirname(__file__))

from onemt_bot import (
    LoginServer, LOGIN_SERVER, GateBot,
    frida_login, decode_gate_response, unpack_stream
)

EMAIL = "king7moe1990@gmail.com"

if __name__ == "__main__":
    print(f"[*] الاتصال بحساب {EMAIL}...")

    try:
        session_info = frida_login(EMAIL, "dummy")
    except Exception as e:
        print(f"[!] فشل: {e}"); sys.exit(1)

    real_uid = session_info.get('uid', '')
    token = {"subtoken": session_info['subtoken'], "userid": real_uid}

    login = LoginServer(*LOGIN_SERVER)
    login.connect()
    try:
        res = login.do_handshake(token)
    except Exception as e:
        print(f"[!] فشل: {e}"); sys.exit(1)
    finally:
        login.close()

    if not res['success']:
        print("[!] فشل"); sys.exit(1)

    gate = res['gate']
    bot = GateBot(gate['gateip'], int(gate['gateport']), gate)
    bot.connect()

    if bot.handshake(res['secret'], 1):
        bot.alive = True
        threading.Thread(target=bot.recv_loop, daemon=True).start()

        # ═══════════════════════════════════════
        # 1. أوامر التهيئة + انتظار البيانات
        # ═══════════════════════════════════════
        bot.init_game()      # أرسل نفس أوامر اللعبة
        bot.wait_for_data(timeout=10)  # انتظر الردود

        # ═══════════════════════════════════════
        # 2. نعرض كل البيانات المتاحة
        # ═══════════════════════════════════════
        print("\n" + "="*60)
        print("  البيانات المستقبلة من السيرفر")
        print("="*60)
        
        data = bot.get_castle_info()
        
        # عرض الموارد
        res_data = bot.get_resources()
        if res_data:
            print("\n📦 الموارد:")
            safe = res_data.get('safe', {})
            res_names = {'1001': 'ذهب', '1002': 'خشب', '1003': 'طعام', 
                        '1004': 'حجر', '1005': 'حديد', '1006': 'فضة'}
            for rid, amount in safe.items():
                name = res_names.get(rid, rid)
                print(f"  {name}: {amount:,.0f}")
        
        # عرض بيانات اللورد
        lord = data.get('_lordInfo', {})
        if lord:
            print(f"\n👑 اللورد:")
            print(f"  القوة: {lord.get('totalFc', '?'):,}")
            print(f"  الانتصارات: {lord.get('victoryTimes', '?')}")
            print(f"  الهزائم: {lord.get('loseTimes', '?')}")
        
        # عرض بيانات الجيش
        print("\n⚔️ بيانات الجيش:")
        army = bot.get_army_info()
        if army:
            total = army.get('totalArmy', {})
            print(f"  الجنود الكلي: {total}")
            train = army.get('trainArmy', {})
            print(f"  قيد التدريب: {train if train else 'لا يوجد'}")
        
        # عرض المهام
        tasks = data.get('_tasks', {})
        if tasks:
            print(f"\n📋 المهام الجارية ({len(tasks)}):")
            for tid, t in tasks.items():
                print(f"  [{tid}] status={t.get('status')} startTime={t.get('startTime')}")
        
        # عرض كل الـ notify IDs المتاحة
        print(f"\n📡 كل أنواع الإشعارات المستقبلة:")
        for key in sorted(data.keys()):
            if key.startswith('NOTIFY_'):
                val = data[key]
                size = len(json.dumps(val))
                print(f"  {key} ({size} bytes)")
        
        print(f"\n[+] كل البيانات محفوظة في game_data.json ({os.path.getsize('game_data.json'):,} bytes)")
        
        # ═══════════════════════════════════════
        # 3. ننتظر المزيد من البيانات (10 ثواني)
        # ═══════════════════════════════════════
        print("\n[*] ننتظر 10 ثواني للمزيد من البيانات...")
        time.sleep(10)
        
        bot.alive = False
        bot.sock.close()
        print("\n[*] انتهى.")
    else:
        print("[!] فشل الاتصال بالـ Gate.")
