"""
cmd_explorer.py
يتصل بالـ gate server ويستكشف أوامر اللعبة
يرسل أوامر ويعرض الردود الكاملة بالتفصيل

الاستخدام:
  python cmd_explorer.py --session "XXX" --uid "YYY" --email "ZZZ"

  ثم اكتب الأمر:
    send 1033           → يرسل cmd=1033 بدون data
    send 1033 {"x":1}   → يرسل cmd=1033 مع data
    scan 1000 1100      → يجرب كل الأوامر من 1000 إلى 1100
    quit                → خروج
"""
import sys, os, json, time, socket, threading, struct

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# استيراد الدوال من البوت
from onemt_bot import (
    LoginServer, LOGIN_SERVER, GateBot,
    load_cached_session, pack_request, unpack_stream,
    decode_gate_response, CMD_PREFIX, log
)

class CmdExplorer(GateBot):
    """نسخة من GateBot تسجّل كل شيء وتقبل أوامر تفاعلية"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.responses = {}  # cmd → [responses]
        self.all_cmds = []   # كل الأوامر المستقبلة بالترتيب

    def recv_loop(self):
        """يسجّل كل packet بالتفصيل الكامل"""
        while self.alive:
            try:
                self.sock.settimeout(10)
                chunk = self.sock.recv(65535)
                if not chunk: self.alive = False; break
                self.buf += chunk
                pkts, self.buf = unpack_stream(self.buf)
                for p in pkts:
                    r = decode_gate_response(p)
                    if r and r.get('ok'):
                        c = r.get('content', {})
                        cmd = c.get('cmd', '?')

                        # خزّن الـ response
                        self.responses.setdefault(cmd, []).append(c)
                        self.all_cmds.append(c)

                        # اطبع كل شيء ما عدا heartbeat
                        if cmd not in ('1037', '1009'):
                            print(f"\n{'='*50}")
                            print(f"  ← cmd={cmd}")
                            pretty = json.dumps(c, ensure_ascii=False, indent=2)
                            if len(pretty) > 1500:
                                print(pretty[:1500] + "\n... (truncated)")
                            else:
                                print(pretty)
                            print(f"{'='*50}")

                    elif r and r.get('raw'):
                        print(f"\n  ← [RAW] {r['raw'][:200]}")

            except socket.timeout:
                try:
                    self.send_cmd("1037", "1", {"time": int(time.time()*1000)})
                except:
                    self.alive = False
            except Exception as e:
                if self.alive: print(f"\n[ERR] recv: {e}")
                self.alive = False

    def send_and_log(self, cmd: str, subcmd: str = "2", data: dict = None):
        """يرسل أمر ويطبعه"""
        print(f"\n  → cmd={cmd} subcmd={subcmd} data={json.dumps(data or {}, ensure_ascii=False)}")
        self.send_cmd(cmd, subcmd, data)

    def scan_cmds(self, start: int, end: int):
        """يجرب أوامر متتالية"""
        print(f"\n[*] Scanning cmds {start}-{end}...")
        for cmd_num in range(start, end + 1):
            self.send_and_log(str(cmd_num), "2", {})
            time.sleep(0.3)
        print(f"[*] Scan done. Wait 3s for responses...")
        time.sleep(3)

    def interactive(self, secret: bytes, index: int = 1):
        """وضع تفاعلي: اكتب أوامر وشوف الردود"""
        self.connect()
        if not self.handshake(secret, index):
            raise Exception("Gate handshake failed")
        self.alive = True
        threading.Thread(target=self.recv_loop, daemon=True).start()

        print("\n" + "="*50)
        print("  CMD Explorer - مستكشف أوامر اللعبة")
        print("="*50)
        print("  الأوامر:")
        print("    send CMD              → إرسال أمر (مثال: send 1033)")
        print("    send CMD {json}       → إرسال أمر مع بيانات")
        print("    scan START END        → تجربة أوامر من START إلى END")
        print("    responses             → عرض كل الردود المخزّنة")
        print("    save                  → حفظ كل الردود في ملف")
        print("    quit                  → خروج")
        print("="*50)
        print()

        # ابدأ بإرسال 1033 كاختبار
        self.send_and_log("1033", "2", {})
        time.sleep(1)

        while self.alive:
            try:
                line = input("\ncmd> ").strip()
                if not line:
                    continue

                parts = line.split(None, 2)
                action = parts[0].lower()

                if action == 'quit' or action == 'exit':
                    break

                elif action == 'send':
                    if len(parts) < 2:
                        print("  Usage: send CMD [json_data]")
                        continue
                    cmd_num = parts[1]
                    data = {}
                    if len(parts) >= 3:
                        try:
                            data = json.loads(parts[2])
                        except:
                            print("  [!] JSON غير صحيح")
                            continue
                    self.send_and_log(cmd_num, "2", data)

                elif action == 'scan':
                    if len(parts) < 3:
                        print("  Usage: scan START END")
                        continue
                    self.scan_cmds(int(parts[1]), int(parts[2]))

                elif action == 'responses':
                    print(f"\n  Total responses: {len(self.all_cmds)}")
                    for cmd, resps in sorted(self.responses.items()):
                        print(f"    cmd={cmd}: {len(resps)} responses")

                elif action == 'save':
                    fname = os.path.join(os.path.dirname(__file__), "captured_cmds.json")
                    with open(fname, "w", encoding="utf-8") as f:
                        json.dump({
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "total": len(self.all_cmds),
                            "by_cmd": {k: v for k, v in self.responses.items()},
                            "all": self.all_cmds
                        }, f, ensure_ascii=False, indent=2)
                    print(f"  Saved to {fname}")

                else:
                    # ربما كتب رقم مباشرة
                    try:
                        int(action)
                        self.send_and_log(action, "2", {})
                    except ValueError:
                        print("  أمر غير معروف. اكتب send CMD أو scan START END")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

        self.alive = False
        if self.sock:
            try: self.sock.close()
            except: pass
        print("\n[*] Done.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Game Command Explorer")
    parser.add_argument("--email", "-e", required=True)
    parser.add_argument("--session", "-s", help="Session ID")
    parser.add_argument("--uid", "-u", help="User ID")
    args = parser.parse_args()

    if args.session and args.uid:
        session_id = args.session
        user_id = args.uid
    else:
        cached = load_cached_session(args.email)
        if not cached:
            print(f"[!] No cached session for {args.email}")
            print("Run: python extract_session_adb.py --save-all")
            sys.exit(1)
        session_id = cached['subtoken']
        user_id = cached.get('userid', '')

    print(f"[*] Email:   {args.email}")
    print(f"[*] Session: {session_id[:30]}...")

    token = {"subtoken": session_id, "userid": user_id}

    login_srv = LoginServer(*LOGIN_SERVER)
    login_srv.connect()
    result = login_srv.do_handshake(token)
    login_srv.close()

    if not result['success']:
        print("[!] Login failed!"); sys.exit(1)

    gate   = result['gate']
    secret = result['secret']

    print(f"[*] Gate: {gate['gateip']}:{gate['gateport']} | UID: {gate['uid']}")

    explorer = CmdExplorer(gate['gateip'], int(gate['gateport']), gate)
    explorer.interactive(secret)


if __name__ == "__main__":
    main()
