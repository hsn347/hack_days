"""
بوت ONEMT المستقل
يعمل بإيميل وكلمة مرور فقط - بدون محاكي
"""

import socket, json, time, struct, zlib, threading, os, sys, hashlib, hmac, base64, requests
from datetime import datetime

# ============================================================
# ثوابت
# ============================================================
XOR_KEY    = "OSxHP.!-wd?'lao5"
CMD_PREFIX = "onemt_"
LOG_FILE   = os.path.join(os.path.dirname(__file__), "bot_log.txt")

# ============================================================
# تشفير
# ============================================================
def xor_crypt(data: bytes) -> bytes:
    key = XOR_KEY.encode()
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

def pack_request(cmd: str, subcmd: str = "2", data: dict = None, session: int = 1) -> bytes:
    msg   = {"cmd": CMD_PREFIX + cmd, "subcmd": subcmd, "data": data or {}}
    xored = xor_crypt(json.dumps(msg, ensure_ascii=False, separators=(',',':')).encode())
    size  = len(xored) + 4
    return struct.pack('>H', size) + xored + struct.pack('>I', session)

def pack_handshake(username: str, index, hmac_val: str) -> bytes:
    payload = json.dumps({"username": username, "index": index, "hmac": hmac_val},
                         separators=(',',':')).encode()
    return bytes([(len(payload)>>8)&0xFF, len(payload)&0xFF]) + payload

def unpack_stream(buf: bytes):
    pkts = []
    while len(buf) >= 2:
        s, head = buf[0]*256+buf[1], 2
        if s == 0xFFFF:
            if len(buf)<5: break
            s, head = buf[2]*65536+buf[3]*256+buf[4], 5
        if len(buf) < head+s: break
        pkts.append(buf[head:head+s]); buf = buf[head+s:]
    return pkts, buf

def decode_response(pkt: bytes):
    if len(pkt) < 5: return None
    ok, session = pkt[-5], struct.unpack('>I', pkt[-4:])[0]
    raw = pkt[:-5]
    if not ok: return {'ok': False, 'session': session}
    if session == 0:
        try:    raw = zlib.decompress(raw, -15)
        except:
            try: raw = zlib.decompress(raw)
            except: pass
    try:
        c = json.loads(xor_crypt(raw))
        if c.get('cmd','').startswith(CMD_PREFIX):
            c['cmd'] = c['cmd'][len(CMD_PREFIX):]
        return {'ok': True, 'content': c, 'session': session}
    except:
        return {'ok': True, 'raw': xor_crypt(raw).decode('utf-8','replace')}

# ============================================================
# HMAC حساب (سيُكمَل بعد الحصول على endpoint)
# ============================================================
def compute_hmac(uid: str, servername: str, subid: str, secret: str, index) -> tuple:
    """
    من gate.lua:
    handshake = base64(uid) + "@" + base64(servername) + "#" + base64(subid)
    hmac = base64(hmac64(hashkey(handshake + ":" + index), secret))
    """
    uid_b64 = base64.b64encode(uid.encode()).decode()
    srv_b64 = base64.b64encode(servername.encode()).decode()
    sub_b64 = base64.b64encode(subid.encode()).decode()
    username = f"{uid_b64}@{srv_b64}#{sub_b64}"
    
    key_material = f"{username}:{index}".encode()
    hash_key     = hashlib.md5(key_material).digest()
    hmac_val     = hmac.new(hash_key, username.encode(), hashlib.sha1).digest()[:8]
    
    return username, base64.b64encode(hmac_val).decode()

# ============================================================
# HTTP Login (سيُكمَل بعد تحليل الـ API)
# ============================================================
class LoginClient:
    """
    تسجيل الدخول عبر HTTP وجلب بيانات الاتصال
    يُعبأ بعد تحليل طلبات HTTP من capture_http_login.js
    """

    # ملاحظة: هذه القيم ستُعبأ بعد التحليل
    BASE_URL = "https://dgapi.onemt.co"   # الدومين الرئيسي
    
    # ستُحدَّث بعد رؤية الـ API الفعلي
    ENDPOINTS = {
        "login": None,   # سيُعبأ
    }

    def __init__(self, email: str, password: str):
        self.email    = email
        self.password = password
        self.session  = requests.Session()
        self.session.headers.update({
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 8.1.0)",
            "Content-Type": "application/json",
        })

    def login(self) -> dict:
        """
        الخطوة الأولى: تسجيل الدخول عبر HTTP
        يجب تعبئة الـ endpoint بعد التحليل
        """
        raise NotImplementedError(
            "يجب تعبئة login endpoint بعد تشغيل capture_http_login.js\n"
            "شاهد الناتج وابحث عن: POST /... + email + password"
        )

    def get_server_info(self) -> dict:
        """
        الخطوة الثانية: الحصول على IP السيرفر والـ credentials
        يُستدعى بعد تسجيل الدخول
        """
        raise NotImplementedError("يجب تعبئة بعد التحليل")

# ============================================================
# TCP Bot
# ============================================================
class OnemtBot:
    def __init__(self, server_ip: str, server_port: int, creds: dict):
        self.ip      = server_ip
        self.port    = server_port
        self.creds   = creds
        self.sock    = None
        self.session = 1
        self.buf     = b''
        self.alive   = False
        self.log_fh  = open(LOG_FILE, 'a', encoding='utf-8', errors='replace')

    def log(self, msg: str, lvl: str = 'INFO'):
        ts   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        safe = msg.encode('ascii', errors='replace').decode()
        line = f"[{ts}][{lvl}] {safe}"
        print(line); self.log_fh.write(line+'\n'); self.log_fh.flush()

    def connect(self):
        self.log(f"Connecting {self.ip}:{self.port}...")
        s = socket.socket(); s.settimeout(15); s.connect((self.ip, self.port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(None)
        self.sock = s; self.session = 1; self.buf = b''
        self.log("[OK] Connected")

    def handshake(self) -> bool:
        self.log("Handshake...")
        hs = pack_handshake(self.creds['username'], self.creds['index'], self.creds['hmac'])
        self.sock.sendall(hs)
        self.sock.settimeout(15)
        resp = self.sock.recv(512); self.sock.settimeout(None)
        self.log(f"Response: {resp!r}")
        if b'200' in resp:
            self.log("[OK] Authenticated!")
            return True
        self.log(f"[FAIL] code={resp[:20]}", 'ERROR')
        return False

    def send_cmd(self, cmd: str, subcmd: str = "2", data: dict = None):
        self.sock.sendall(pack_request(cmd, subcmd, data or {}, self.session))
        self.log(f"-> cmd={cmd} sess={self.session}")
        self.session += 1

    def recv_loop(self):
        while self.alive:
            try:
                self.sock.settimeout(30)
                chunk = self.sock.recv(65535)
                if not chunk: self.alive = False; break
                self.buf += chunk
                pkts, self.buf = unpack_stream(self.buf)
                for p in pkts:
                    r = decode_response(p)
                    if r and r.get('ok'):
                        c = r.get('content', {}); cmd = c.get('cmd','?')
                        if cmd not in ('1037',): self.log(f"<- cmd={cmd}")
            except socket.timeout:
                try: self.send_cmd("1037", "1", {"time": int(time.time()*1000)})
                except: self.alive = False
            except Exception as e:
                if self.alive: self.log(f"recv error: {e}", 'ERROR')
                self.alive = False

    def port_mission(self):
        self.log("=== Port Mission ===")
        self.send_cmd("1033", "2", {})

    def run(self, interval: int = 300):
        while True:
            try:
                self.connect()
                if not self.handshake():
                    time.sleep(60); continue
                self.alive = True
                threading.Thread(target=self.recv_loop, daemon=True).start()
                while self.alive:
                    self.port_mission()
                    self.log(f"Waiting {interval}s...")
                    for _ in range(interval):
                        if not self.alive: break
                        time.sleep(1)
            except KeyboardInterrupt:
                self.log("Stopped."); sys.exit(0)
            except Exception as e:
                self.log(f"Error: {e}", 'ERROR')
            finally:
                self.alive = False
                if self.sock:
                    try: self.sock.close()
                    except: pass
            self.log("Reconnecting in 15s..."); time.sleep(15)

# ============================================================
# نقطة البدء
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  ONEMT Bot - Standalone (No Emulator)")
    print("=" * 50)
    print()
    print("[!] هذا البوت بحاجة لمعرفة الـ login API أولاً.")
    print("[!] شغّل capture_http_login.js وادخل اللعبة")
    print("[!] ثم سنكمل بناء دالة login()")
    print()
    print("للاختبار المباشر بـ credentials محفوظة:")
    print("  python standalone_bot.py --config game_config.json")
