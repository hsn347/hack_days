"""
gate_sniffer.py
يتصل بالـ gate server ويسجّل كل الأوامر المستلمة بشكل مفصّل
يُستخدم لاكتشاف أوامر اللعبة (مشاهدة قلعة، هجوم، استطلاع...)

الاستخدام:
  python gate_sniffer.py --email burcudemr@gmail.com --password any
  ثم نفّذ الإجراء في اللعبة (على المحاكي) وراقب الـ output
"""

import sys, os, json, time, socket, zlib, base64, hashlib, struct, threading

sys.path.insert(0, os.path.dirname(__file__))

# استيراد من onemt_bot.py
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# نسخ الدوال المطلوبة من onemt_bot
exec(open('onemt_bot.py', encoding='utf-8').read().split('if __name__')[0])

class GateSniffer(GateBot):
    """نسخة معدّلة تسجّل كل شيء"""
    
    def recv_loop(self):
        """يسجّل كل packet مستلم مع محتواه الكامل"""
        pkt_count = 0
        
        while self.alive:
            try:
                self.sock.settimeout(30)
                chunk = self.sock.recv(65535)
                if not chunk:
                    print("\n[!] Gate disconnected")
                    self.alive = False; break
                self.buf += chunk
                pkts, self.buf = unpack_stream(self.buf)
                
                for p in pkts:
                    pkt_count += 1
                    r = decode_gate_response(p)
                    
                    if r and r.get('ok'):
                        c = r.get('content', {})
                        cmd = c.get('cmd', '?')
                        
                        if cmd in ('1037', '1009'):
                            # heartbeat/ping - اطبع نقطة فقط
                            print(".", end="", flush=True)
                            continue
                        
                        # أي cmd آخر - اطبعه بالكامل
                        print(f"\n{'='*60}")
                        print(f"[PKT #{pkt_count}] cmd={cmd}")
                        print(f"Content:")
                        print(json.dumps(c, ensure_ascii=False, indent=2))
                        print(f"{'='*60}")
                    
                    elif r and r.get('raw'):
                        raw_str = r.get('raw', '')
                        if raw_str:
                            print(f"\n[PKT #{pkt_count}] RAW: {raw_str[:200]}")
                    
                    else:
                        print(f"\n[PKT #{pkt_count}] HEX: {p[:30].hex()}")
                        
            except socket.timeout:
                try: self.send_cmd("1037", "1", {"time": int(time.time()*1000)})
                except: self.alive = False
            except Exception as e:
                if self.alive: print(f"\n[ERROR] recv: {e}")
                self.alive = False
    
    def sniff(self, secret: bytes):
        """وضع الاستماع - يتصل ويستمع لكل شيء"""
        self.connect()
        if not self.handshake(secret, 1):
            raise Exception("Gate handshake failed")
        self.alive = True
        
        # أرسل cmd=1033 لتنشيط الجلسة
        self.send_cmd("1033", "2", {})
        print("[*] Sent cmd=1033 to activate session")
        
        print("\n[*] Connected to Gate! Listening for ALL commands...")
        print("[*] Now perform actions in the game (view castle, attack, scout...)")
        print("[*] Press Ctrl+C to stop\n")
        print("Heartbeats: ", end="", flush=True)
        
        self.recv_loop()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Gate sniffer - capture all game commands")
    parser.add_argument("--email", "-e", required=True)
    parser.add_argument("--password", "-p", default="any")
    parser.add_argument("--session", "-s", help="Direct session ID")
    parser.add_argument("--uid", "-u", help="User ID")
    args = parser.parse_args()
    
    # الحصول على session
    if args.session and args.uid:
        session_id = args.session
        user_id    = args.uid
    else:
        cached = load_cached_session(args.email)
        if not cached:
            print(f"ERROR: No cached session for {args.email}")
            print("Run: python extract_session_adb.py --save-all")
            sys.exit(1)
        session_id = cached['subtoken']
        user_id    = cached.get('userid', '')
    
    print(f"[*] Email:   {args.email}")
    print(f"[*] Session: {session_id[:40]}...")
    
    token = {"subtoken": session_id, "userid": user_id}
    
    # الاتصال بـ login server
    login_srv = LoginServer(*LOGIN_SERVER)
    login_srv.connect()
    result = login_srv.do_handshake(token)
    login_srv.close()
    
    if not result['success']:
        print("ERROR: Login failed!")
        sys.exit(1)
    
    gate   = result['gate']
    secret = result['secret']
    gate_ip   = gate['gateip']
    gate_port = int(gate['gateport'])
    uid    = gate['uid']
    
    print(f"[*] Gate: {gate_ip}:{gate_port} | UID: {uid} | Server: {gate['servername']}")
    
    # شغّل الـ sniffer
    sniffer = GateSniffer(gate_ip, gate_port, gate)
    try:
        sniffer.sniff(secret)
    except KeyboardInterrupt:
        print("\n\n[*] Stopped.")

if __name__ == "__main__":
    main()
