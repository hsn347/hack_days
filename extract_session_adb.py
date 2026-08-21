"""
extract_session_adb.py - v3
يقرأ SdkEmail.xml من المحاكي لاستخراج sessions كل الحسابات - بدون Frida!

الصيغة المخزّنة: email → userId + "OneMT" + sessionId

الاستخدام:
  python extract_session_adb.py                        # يعرض كل الحسابات
  python extract_session_adb.py --email user@mail.com  # يحفظ في cache
  python extract_session_adb.py --list                 # يعرض بدون حفظ
"""
import subprocess, json, re, time, os, sys, argparse

# Fix Unicode on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PACKAGE = "and.onemt.boe.tr"
PREF_FILE = "SdkEmail.xml"
CACHE_FILE = os.path.join(os.path.dirname(__file__), "session_cache.json")
SEPARATOR = "OneMT"

def adb(args: list, device: str = None, timeout: int = 15) -> str:
    cmd = ["adb"]
    if device:
        cmd += ["-s", device]
    cmd += args
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return (r.stdout + r.stderr).decode("utf-8", errors="replace").strip()
    except Exception as e:
        return f"ERROR: {e}"

def adb_shell(cmd: str, device: str = None, timeout: int = 15) -> str:
    return adb(["shell", cmd], device, timeout)

def get_devices() -> list:
    out = adb(["devices"])
    devices = []
    for line in out.split("\n")[1:]:
        if "\t" in line and "device" in line.split("\t")[1]:
            devices.append(line.split("\t")[0].strip())
    return devices

def read_sdk_email_xml(device: str) -> str:
    """يقرأ SdkEmail.xml من SharedPreferences"""
    prefs_path = f"/data/data/{PACKAGE}/shared_prefs/{PREF_FILE}"
    
    # حاول بـ root أولاً
    content = adb_shell(f"su -c 'cat \"{prefs_path}\"'", device, timeout=20)
    if content and len(content) > 50 and "<?xml" in content:
        return content
    
    # حاول بدون root (run-as)
    content = adb_shell(f"run-as {PACKAGE} cat shared_prefs/{PREF_FILE}", device, timeout=20)
    if content and len(content) > 50:
        return content
    
    return None

def parse_accounts(xml_content: str) -> dict:
    """
    يحلّل SdkEmail.xml ويستخرج الحسابات
    الصيغة: email → userId(32hex) + "OneMT" + sessionId(base64)
    """
    accounts = {}
    
    # استخراج كل الإدخالات من XML
    pattern = r'name="([^"]+@[^"]+)"[^>]*>([^<]+)</'
    
    for match in re.finditer(pattern, xml_content):
        email = match.group(1).strip()
        raw_value = match.group(2).strip()
        
        # فك ترميز HTML entities
        raw_value = raw_value.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'")
        
        # الصيغة: userId(32) + "OneMT" + sessionId
        if SEPARATOR in raw_value:
            parts = raw_value.split(SEPARATOR, 1)
            user_id = parts[0].strip()
            session_id = parts[1].strip()
            
            if len(user_id) == 32 and re.match(r'^[a-f0-9]+$', user_id):
                accounts[email] = {
                    "userId": user_id,
                    "sessionId": session_id,
                    "raw": raw_value
                }
    
    return accounts

def save_to_cache(email: str, user_id: str, session_id: str):
    """حفظ في session_cache.json"""
    try:
        with open(CACHE_FILE, encoding='utf-8') as f:
            cache = json.load(f)
        if "accounts" not in cache:
            cache = {"accounts": {}}
    except:
        cache = {"accounts": {}}
    
    cache["accounts"][email] = {
        "userId": user_id,
        "sessionId": session_id,
        "timestamp": time.time(),
        "source": "adb_sdk_email"
    }
    
    with open(CACHE_FILE, "w", encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Saved session for '{email}' in session_cache.json")

def main():
    parser = argparse.ArgumentParser(
        description="Extract ALL account sessions from Android device via ADB"
    )
    parser.add_argument("--email", "-e", help="Extract and save specific account")
    parser.add_argument("--device", "-d", help="ADB device ID (e.g. emulator-5554)")
    parser.add_argument("--list", "-l", action="store_true", help="List all accounts")
    parser.add_argument("--save-all", action="store_true", help="Save all accounts to cache")
    args = parser.parse_args()
    
    # تحديد الجهاز
    if args.device:
        devices = [args.device]
    else:
        devices = get_devices()
        if not devices:
            print("ERROR: No device/emulator connected!")
            print("  Start the emulator and run: adb devices")
            sys.exit(1)
    
    device = devices[0]
    print(f"[*] Device: {device}")
    
    # قراءة SdkEmail.xml
    print(f"[*] Reading {PREF_FILE}...")
    xml_content = read_sdk_email_xml(device)
    
    if not xml_content:
        print(f"ERROR: Cannot read {PREF_FILE}")
        print("  Make sure the game has been launched and logged in at least once")
        sys.exit(1)
    
    # تحليل الحسابات
    accounts = parse_accounts(xml_content)
    
    if not accounts:
        print(f"ERROR: No accounts found in {PREF_FILE}")
        print(f"  File content preview: {xml_content[:200]}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"  Found {len(accounts)} account(s):")
    print(f"{'='*60}")
    
    for email, info in accounts.items():
        sid = info['sessionId']
        uid = info['userId']
        print(f"\n  Email:   {email}")
        print(f"  UserId:  {uid}")
        print(f"  Session: {sid[:50]}...")
        print(f"  Run bot: python onemt_bot.py --session \"{sid[:30]}...\" --uid \"{uid}\"")
    
    print(f"\n{'='*60}")
    
    # حفظ حساب محدد
    if args.email:
        if args.email in accounts:
            info = accounts[args.email]
            save_to_cache(args.email, info['userId'], info['sessionId'])
            print(f"\n  Next: python onemt_bot.py --email \"{args.email}\" --password \"any\"")
        else:
            print(f"\nERROR: Email '{args.email}' not found in device accounts")
            print(f"  Available: {list(accounts.keys())}")
    
    # حفظ كل الحسابات
    elif args.save_all:
        for email, info in accounts.items():
            save_to_cache(email, info['userId'], info['sessionId'])
        print(f"\n[OK] All {len(accounts)} accounts saved to session_cache.json")
        print(f"\nTo run bots:")
        for email in accounts:
            print(f'  python onemt_bot.py --email "{email}" --password "any" --interval 300')
    
    # عرض الأول فقط بدون حفظ
    else:
        first_email, first_info = next(iter(accounts.items()))
        sid = first_info['sessionId']
        uid = first_info['userId']
        print(f"\nQuick run (first account):")
        print(f'  python onemt_bot.py --session "{sid}" --uid "{uid}"')
        print(f"\nTo save all accounts: python extract_session_adb.py --save-all")

if __name__ == "__main__":
    main()
