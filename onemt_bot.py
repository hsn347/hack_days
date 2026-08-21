"""
بوت ONEMT المستقل الكامل
يعمل بـ email + password فقط - بدون محاكي

الخطوات:
1. HTTP login → sessionId
2. TCP login server (DH exchange) → gate IP + credentials
3. TCP gate server → handshake → أوامر اللعبة

python onemt_bot.py --email EMAIL --password PASS
python onemt_bot.py --email johan2003@yopmail.com --password aalloo33
"""

import socket, json, time, struct, zlib, hashlib, hmac as hmac_mod, base64, urllib.request, urllib.parse
import threading, os, sys, logging, argparse, requests
from datetime import datetime

# ============================================================
# ثوابت
# ============================================================
XOR_KEY      = "OSxHP.!-wd?'lao5"
CMD_PREFIX   = "onemt_"
LOGIN_SERVER = ("119.8.212.255", 10000)   # من TCP capture
LOG_FILE     = os.path.join(os.path.dirname(__file__), "onemt_bot.log")

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8", errors="replace")
    ]
)
log = logging.getLogger("onemt")

# ============================================================
# Diffie-Hellman (مطابق للـ libcocos2dlua.so ARM64 binary)
# ============================================================
# من disassembly ldhexchange:
#   mov x9, #-0x3b   → P = 2^64 - 59 = 0xFFFFFFFFFFFFFFC5
#   G = 5 (ثابت في الكود)
# ALL keys stored/transmitted in LITTLE-ENDIAN!
DH_P = 0xFFFFFFFFFFFFFFC5   # 2^64 - 59 (prime), confirmed from ARM64 binary
DH_G = 5

def dh_exchange(priv_key_bytes: bytes) -> bytes:
    """
    pubkey = pow(G, priv, P) stored as LITTLE-ENDIAN 8 bytes
    priv_key_bytes: 8 random bytes, read as LE integer
    """
    priv_int = int.from_bytes(priv_key_bytes, 'little')
    pub_int  = pow(DH_G, priv_int, DH_P)
    return pub_int.to_bytes(8, 'little')

def dh_secret(server_pub_bytes: bytes, priv_key_bytes: bytes) -> bytes:
    """
    secret = pow(server_pub, priv, P) stored as LITTLE-ENDIAN 8 bytes
    Both server_pub and priv are LITTLE-ENDIAN
    """
    server_pub_int = int.from_bytes(server_pub_bytes, 'little')
    priv_int       = int.from_bytes(priv_key_bytes, 'little')
    # Reduce server_pub mod P if needed (from ldhsecret code)
    if server_pub_int >= DH_P:
        server_pub_int -= DH_P
    secret_int = pow(server_pub_int, priv_int, DH_P)
    return secret_int.to_bytes(8, 'little')

def random_key() -> bytes:
    """مفتاح عشوائي (8 bytes) - يُستخدم مباشرة كـ LE integer"""
    return os.urandom(8)

# ============================================================
# Custom MAC (custom_hmac64) - extracted from lhmac64 ARM64 binary
# ============================================================
def _md5_compress_no_add(block64: bytes):
    """
    MD5 single-block compression WITHOUT adding initial values.
    Returns (A, B, C, D) raw after 64 rounds.
    """
    K = [
        0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee,
        0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
        0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
        0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
        0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa,
        0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
        0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed,
        0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
        0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c,
        0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
        0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
        0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
        0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039,
        0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
        0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1,
        0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391,
    ]
    S = [
        7,12,17,22, 7,12,17,22, 7,12,17,22, 7,12,17,22,
        5, 9,14,20, 5, 9,14,20, 5, 9,14,20, 5, 9,14,20,
        4,11,16,23, 4,11,16,23, 4,11,16,23, 4,11,16,23,
        6,10,15,21, 6,10,15,21, 6,10,15,21, 6,10,15,21,
    ]
    M = struct.unpack('<16I', block64)
    A, B, C, D = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    for i in range(64):
        if i < 16:
            F = (B & C) | (~B & D)
            g = i
        elif i < 32:
            F = (D & B) | (~D & C)
            g = (5*i+1) % 16
        elif i < 48:
            F = B ^ C ^ D
            g = (3*i+5) % 16
        else:
            F = C ^ (B | ~D)
            g = (7*i) % 16
        F = (F + A + K[i] + M[g]) & 0xFFFFFFFF
        A = D; D = C; C = B
        rs = S[i]
        B = (B + ((F << rs) | (F >> (32-rs)))) & 0xFFFFFFFF
    return A, B, C, D

def hmac64(challenge: bytes, secret: bytes) -> bytes:
    """
    Custom MAC from lhmac64 ARM64 binary (libcocos2dlua.so).
    Block = [ch[4:8], ch[0:4], sec[4:8], sec[0:4]] * 4  (as LE uint32s)
    Result = (C_final XOR D_final as LE) || (B_final XOR A_final as LE)
    CONFIRMED working - returns 200 from login server.
    """
    ch_lo, ch_hi   = struct.unpack('<2I', challenge)
    sec_lo, sec_hi = struct.unpack('<2I', secret)
    pattern = struct.pack('<4I', ch_hi, ch_lo, sec_hi, sec_lo)
    A, B, C, D = _md5_compress_no_add(pattern * 4)
    w8 = (C ^ D) & 0xFFFFFFFF
    w9 = (B ^ A) & 0xFFFFFFFF
    return struct.pack('<2I', w8, w9)


def skynet_des_encode(data: bytes, key: bytes) -> bytes:
    """
    مطابقة كاملة لـ skynet crypt.desencode (ISO 7816-4 padding)
    chunksz = (textsz + 8) & ~7   ← دائماً block إضافي!
    Padding: buf[offset] = 0x80, rest = 0x00
    """
    from Crypto.Cipher import DES
    textsz = len(data)
    chunksz = (textsz + 8) & ~7
    padded = bytearray(chunksz)
    padded[:textsz] = data
    padded[textsz] = 0x80
    cipher = DES.new(key[:8], DES.MODE_ECB)
    return cipher.encrypt(bytes(padded))

def encode_token(token: dict) -> str:
    """تحويل token dict إلى string (مطابق encodetoken في Lua)"""
    # format: b64(user)@b64(pass):b64(subtoken)
    user = base64.b64encode(token.get("userid", "").encode()).decode()
    passwd = base64.b64encode(b"password").decode()
    subtoken = base64.b64encode(token.get("subtoken", "").encode()).decode()
    return f"{user}@{passwd}:{subtoken}"

# ============================================================
# XOR + packet building
# ============================================================
def xor_crypt(data: bytes) -> bytes:
    key = XOR_KEY.encode()
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))

def pack_request(cmd: str, subcmd: str = "2", data: dict = None, session: int = 1) -> bytes:
    msg   = {"cmd": CMD_PREFIX + cmd, "subcmd": subcmd, "data": data or {}}
    xored = xor_crypt(json.dumps(msg, ensure_ascii=False, separators=(',',':')).encode())
    size  = len(xored) + 4
    return struct.pack('>H', size) + xored + struct.pack('>I', session)

def pack_gate_handshake(username: str, index, hmac_val: str) -> bytes:
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

def decode_gate_response(pkt: bytes):
    if len(pkt) < 5: return None
    ok      = pkt[-5]
    session = struct.unpack('>I', pkt[-4:])[0]
    raw     = pkt[:-5]
    if not ok:
        # لا ترمي الحزمة — حاول فكها على أي حال (بعض الحزم الكبيرة ok=0)
        log.debug(f"[decode] ok=0 session={session} rawLen={len(raw)}")
        # حاول Zlib أولاً
        decompressed = False
        for method in [lambda r: zlib.decompress(r, -15), lambda r: zlib.decompress(r), lambda r: zlib.decompress(r, 15+32)]:
            try:
                raw = method(raw)
                decompressed = True
                break
            except: pass
        if decompressed:
            try:
                c = json.loads(xor_crypt(raw))
                if c.get('cmd','').startswith(CMD_PREFIX):
                    c['cmd'] = c['cmd'][len(CMD_PREFIX):]
                log.info(f"[decode] ✅ ok=0 لكن تم فك الضغط! cmd={c.get('cmd','?')} size={len(raw)}")
                return {'ok': True, 'content': c, 'session': session}
            except: pass
        # حاول XOR مباشرة بدون Zlib
        try:
            c = json.loads(xor_crypt(raw))
            if c.get('cmd','').startswith(CMD_PREFIX):
                c['cmd'] = c['cmd'][len(CMD_PREFIX):]
            log.info(f"[decode] ✅ ok=0 XOR مباشر! cmd={c.get('cmd','?')}")
            return {'ok': True, 'content': c, 'session': session}
        except: pass
        log.warning(f"[decode] ❌ حزمة مرفوضة ok=0 session={session} rawLen={len(raw)} first20={raw[:20].hex()}")
        return {'ok': False, 'session': session}
    
    # ok != 0 (الحزمة سليمة)
    if session == 0:
        # حزمة مضغوطة — جرب كل طرق Zlib
        original_raw = raw
        for method_name, method in [
            ("raw-15", lambda r: zlib.decompress(r, -15)),
            ("raw",    lambda r: zlib.decompress(r)),
            ("raw+32", lambda r: zlib.decompress(r, 15+32)),
        ]:
            try:
                raw = method(original_raw)
                log.debug(f"[decode] Zlib {method_name}: {len(original_raw)} → {len(raw)} bytes")
                break
            except Exception as e:
                raw = original_raw
                continue
    try:
        c = json.loads(xor_crypt(raw))
        if c.get('cmd','').startswith(CMD_PREFIX):
            c['cmd'] = c['cmd'][len(CMD_PREFIX):]
        return {'ok': True, 'content': c, 'session': session}
    except Exception as e:
        log.warning(f"[decode] JSON parse failed: {e} | rawLen={len(raw)} first50={xor_crypt(raw)[:50]}")
        return {'ok': True, 'raw': xor_crypt(raw).decode('utf-8','replace')}

# ============================================================
# HTTP Login (onemt SDK)
# ============================================================
def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()

def http_login(email: str, password: str) -> dict:
    """
    تسجيل الدخول عبر onemt SDK HTTP
    يعيد: sessionId, userId, passportid
    """
    log.info(f"HTTP Login: {email}")

    # endpoint مُستنتج من UserType=02 (email) + PassportManager
    # يُحدَّث بعد capture_http_login.js
    # ===== يحتاج تعبئة بعد التقاط الـ endpoint =====
    # في الوقت الحالي: إذا عندك session محفوظ استخدمه
    raise NotImplementedError(
        "HTTP Login endpoint لم يُكتشف بعد.\n"
        "استخدم الوضع المحفوظ: --session SESSION_ID --uid USER_ID"
    )

# ============================================================
# Login Server (DH exchange → gate credentials)
# ============================================================
class LoginServer:
    """التحدث مع login server بـ DH handshake"""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = None
        self.buf  = b""
    
    def connect(self):
        log.info(f"Login Server: {self.host}:{self.port}")
        s = socket.socket()
        s.settimeout(15)
        s.connect((self.host, self.port))
        self.sock = s
        self.buf  = b""
    
    def recv_line(self) -> str:
        """استقبال سطر (login server يتكلم بـ text protocol مع newlines)"""
        while b"\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("Login server closed")
            self.buf += chunk
        idx = self.buf.index(b"\n")
        line = self.buf[:idx].decode('utf-8', errors='replace').strip()
        self.buf = self.buf[idx+1:]
        return line
    
    def send_line(self, text: str):
        self.sock.sendall((text + "\n").encode())
    
    def do_handshake(self, token: dict) -> dict:
        """
        DH handshake مطابق للـ login.lua:
        1. ← CHALLENGE (random 8 bytes in base64)
        2. → CLIENT_KEY (DH public key in base64)
        3. ← SERVER_KEY (DH server public key in base64)
        4. → HMAC (hmac64(challenge, secret) in base64)
        5. ← HANDSHAKE (200 OK أو خطأ)
        6. → TOKEN (DES(secret, token) + device info in base64, joined by @)
        7. ← AUTH_TOKEN (200 + gate info أو خطأ)
        """
        log.info("DH Handshake...")
        
        # 1. استقبال CHALLENGE
        challenge_b64 = self.recv_line()
        log.info(f"  Challenge: {challenge_b64}")
        challenge = base64.b64decode(challenge_b64)
        
        # 2. توليد client key وإرساله (priv = 8 random bytes as LE int)
        priv_key = random_key()              # 8 raw bytes
        pub_key  = dh_exchange(priv_key)     # pow(5, LE(priv), P) as LE bytes
        pub_b64  = base64.b64encode(pub_key).decode()
        self.send_line(pub_b64)
        log.info(f"  ClientKey sent: {pub_b64}")
        
        # 3. استقبال SERVER_KEY
        server_key_b64 = self.recv_line()
        log.info(f"  ServerKey: {server_key_b64}")
        server_key = base64.b64decode(server_key_b64)
        
        # 4. حساب secret وإرسال HMAC
        secret = dh_secret(server_key, priv_key)  # priv_key is raw bytes
        log.info(f"  Secret: {secret.hex()}")
        mac    = hmac64(challenge, secret)
        mac_b64 = base64.b64encode(mac).decode()
        self.send_line(mac_b64)
        log.info(f"  HMAC sent: {mac_b64}")
        
        # 5. استقبال HANDSHAKE response
        hs_resp = self.recv_line()
        log.info(f"  Handshake resp: {hs_resp}")
        code = int(hs_resp[:3])
        if code != 200:
            raise Exception(f"Handshake failed: {hs_resp}")
        
        # 6. إرسال TOKEN (DES-encrypted)
        token_str = encode_token(token)
        etoken    = skynet_des_encode(token_str.encode(), secret)
        b64token  = base64.b64encode(etoken).decode()
        
        # معلومات الجهاز (ثابتة)
        game_ver  = base64.b64encode(skynet_des_encode(b"3.34.001", secret)).decode()
        platform  = base64.b64encode(skynet_des_encode(b"Android 8.1.0 sdk_gphone64_x86_64 Google and.onemt.boe.tr ar", secret)).decode()
        model_b   = base64.b64encode(skynet_des_encode(b"sdk_gphone64_x86_64", secret)).decode()
        carrier_b = base64.b64encode(skynet_des_encode(b"Android", secret)).decode()
        
        send_msg = "@".join([b64token, game_ver, platform, model_b, carrier_b])
        self.send_line(send_msg)
        log.info("  Token sent")
        
        # 7. استقبال AUTH_TOKEN response
        auth_resp = self.recv_line()
        log.info(f"  Auth resp: {auth_resp[:100]}")
        auth_code = int(auth_resp[:3])
        
        if auth_code == 200:
            # فك تشفير البيانات
            auth_data = base64.b64decode(auth_resp[4:])
            parts = auth_data.decode().split("@")
            result = {}
            fields = ['kingdomId','servername','gateip','gateport','subid','uid','gateProxyHost','gateProxyPort']
            for i, field in enumerate(fields):
                if i < len(parts):
                    try:
                        result[field] = base64.b64decode(parts[i]).decode()
                    except:
                        result[field] = parts[i]
            log.info(f"  Gate: {result.get('gateip')}:{result.get('gateport')}")
            log.info(f"  UID: {result.get('uid')} Server: {result.get('servername')}")
            return {'success': True, 'gate': result, 'secret': secret}
        elif auth_code == 406:
            raise Exception("SDK token error - sessionId منتهي الصلاحية")
        else:
            raise Exception(f"Auth failed: {auth_resp}")
    
    def close(self):
        if self.sock:
            try: self.sock.close()
            except: pass

# ============================================================
# Gate HMAC حساب
# ============================================================
def skynet_hashkey(data: bytes) -> bytes:
    djb_hash = 5381
    js_hash = 1315423911
    for b in data:
        djb_hash = (djb_hash + (djb_hash << 5) + b) & 0xFFFFFFFF
        js_hash = (js_hash ^ ((js_hash << 5) + b + (js_hash >> 2))) & 0xFFFFFFFF
    return struct.pack('<2I', djb_hash, js_hash)

def compute_gate_hmac(uid: str, servername: str, subid: str, secret: bytes, index: int) -> tuple:
    uid_b64 = base64.b64encode(uid.encode()).decode()
    srv_b64 = base64.b64encode(servername.encode()).decode()
    sub_b64 = base64.b64encode(subid.encode()).decode()
    username = f"{uid_b64}@{srv_b64}#{sub_b64}"
    
    key_mat  = f"{username}:{index}".encode()
    hash_key = skynet_hashkey(key_mat)
    hmac_val = hmac64(hash_key, secret)
    return username, base64.b64encode(hmac_val).decode()

# ============================================================
# Gate Bot
# ============================================================
class GateBot:
    """الاتصال بـ Gate وتنفيذ المهام"""
    
    def __init__(self, ip, port, gate_info):
        self.ip   = ip
        self.port = port
        self.info = gate_info
        self.sock = None
        self.session = 1
        self.buf  = b''
        self.alive = False
        self.castle_data = {}   # بيانات القلعة الكاملة
        self.responses = {}     # آخر رد لكل cmd
        self.initial_data_received = threading.Event()

    def connect(self):
        log.info(f"Gate: {self.ip}:{self.port}")
        s = socket.socket()
        s.settimeout(15)
        s.connect((self.ip, self.port))
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(None)
        self.sock = s; self.session = 1; self.buf = b''
        log.info("[OK] Gate connected")

    def handshake(self, secret: bytes, index: int = 1) -> bool:
        uid       = self.info['uid']
        servername= self.info['servername']
        subid     = self.info['subid']
        username, hmac_val = compute_gate_hmac(uid, servername, subid, secret, index)
        
        hs = pack_gate_handshake(username, index, hmac_val)
        self.sock.sendall(hs)
        
        self.sock.settimeout(15)
        resp = self.sock.recv(512)
        self.sock.settimeout(None)
        log.info(f"Gate handshake resp: {resp!r}")
        
        if b'200' in resp:
            log.info("[OK] Gate authenticated!")
            return True
        log.error(f"Gate handshake failed: {resp[:30]}")
        return False

    def send_cmd(self, cmd: str, subcmd: str = "2", data: dict = None):
        self.sock.sendall(pack_request(cmd, subcmd, data or {}, self.session))
        log.info(f"-> cmd={cmd} sess={self.session}")
        self.session += 1

    def recv_loop(self):
        """يستقبل كل الردود من السيرفر ويخزنها بشكل منظّم"""
        data_file = os.path.join(os.path.dirname(__file__), "game_data.json")
        while self.alive:
            try:
                self.sock.settimeout(30)
                chunk = self.sock.recv(65535)
                if not chunk: self.alive = False; break
                self.buf += chunk
                pkts, self.buf = unpack_stream(self.buf)
                for p in pkts:
                    r = decode_gate_response(p)
                    if r and r.get('ok'):
                        c   = r.get('content', {})
                        cmd = c.get('cmd','?')
                        
                        # حفظ آخر رد لكل cmd
                        self.responses[cmd] = c
                        
                        # cmd=1009: إشعارات السيرفر (push) — أهم البيانات
                        if cmd == '1009':
                            data = c.get('data', {})
                            notify_id = data.get('notifyID', '')
                            notify_data = data.get('notifyData', [])
                            
                            if notify_id:
                                # نخزن حسب الـ notifyID
                                self.castle_data[notify_id] = notify_data
                                
                                # استخراج البيانات المهمة تلقائياً
                                self._process_notify(notify_id, notify_data)
                        
                        # cmd=1005: رد التدريب/بيانات الجيش
                        elif cmd == '1005':
                            data = c.get('data', {})
                            if data.get('armyInfo'):
                                self.castle_data['_armyInfo'] = data['armyInfo']
                            if data.get('retdata'):
                                self.castle_data['_lastTrainResult'] = data
                        
                        # أي cmd آخر: نخزن الرد كاملاً مع الـ subcmd
                        else:
                            subcmd = c.get('subcmd', '')
                            self.castle_data[f'_cmd_{cmd}_{subcmd}'] = c
                        
                        if cmd not in ('1037',):
                            log.info(f"<- cmd={cmd} subcmd={c.get('subcmd', '')}")
                        
                        # تحديث الملف
                        if not self.initial_data_received.is_set():
                            self.initial_data_received.set()
                        self._save_data(data_file)
                        
            except socket.timeout:
                try: self.send_cmd("1037","1",{"time":int(time.time()*1000)})
                except: self.alive = False
            except Exception as e:
                if self.alive: log.error(f"recv: {e}")
                self.alive = False
    
    def _process_notify(self, notify_id, notify_data):
        """يستخرج البيانات المهمة من الإشعارات"""
        if not notify_data: return
        
        for item in notify_data:
            if not isinstance(item, dict): continue
            
            # NOTIFY_CITY: موارد القلعة والمباني
            if notify_id == 'NOTIFY_CITY':
                if 'saferes' in item:
                    self.castle_data['_resources'] = {
                        'safe': item.get('saferes', {}),
                        'change': item.get('res', {}),
                        'max': item.get('maxRes', {}),
                    }
                if 'build' in item:
                    self.castle_data['_buildings'] = item.get('build', {})
            
            # NOTIFY_LORD: بيانات اللورد (القوة، الخسائر، إلخ)
            elif notify_id == 'NOTIFY_LORD':
                key = item.get('key', '')
                if key == 'fcInfo':
                    self.castle_data['_lordInfo'] = item.get('fcInfo', {})
            
            # NOTIFY_UNIVERSAL_TASK: المهام الجارية
            elif notify_id == 'NOTIFY_UNIVERSAL_TASK':
                task = item.get('data', {})
                if task:
                    tid = str(task.get('id', task.get('dynamicId', '?')))
                    if '_tasks' not in self.castle_data:
                        self.castle_data['_tasks'] = {}
                    self.castle_data['_tasks'][tid] = task
    
    def _save_data(self, path):
        """حفظ البيانات في ملف"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.castle_data, f, ensure_ascii=False, indent=2)
        except: pass

    def get_castle_info(self):
        """عرض ملخص بيانات القلعة"""
        if not self.castle_data:
            log.info("[Castle] لا توجد بيانات بعد. ننتظر...")
            self.initial_data_received.wait(timeout=15)
        
        keys = [k for k in self.castle_data.keys()]
        log.info(f"[Castle] البيانات المتاحة ({len(keys)}): {keys}")
        return self.castle_data

    def get_army_info(self):
        """الحصول على بيانات الجيش الكاملة"""
        # أولاً نطلب من السيرفر
        self.send_cmd("1005", "5", {"bid": "119"})
        time.sleep(2)
        return self.castle_data.get('_armyInfo', {})

    def get_resources(self):
        """الحصول على الموارد الحالية"""
        return self.castle_data.get('_resources', {})

    def init_game(self):
        """
        إرسال أوامر التهيئة — نفس الأوامر اللي يرسلها التطبيق عند بداية اللعبة.
        بدونها السيرفر لا يرسل بيانات القلعة.
        (مأخوذة من capture_cmds.js)
        """
        uid = int(self.info.get('uid', 0))
        log.info(f"[Init] إرسال أوامر التهيئة (uid={uid})...")
        
        # الأوامر الأولية حسب ترتيب اللعبة
        init_cmds = [
            ("1001", "1",  {}),                          # بيانات المدينة والمباني (مهم جداً!)
            ("1011", "9",  {}),                          # بيانات عامة
            ("1011", "15", {}),                          # بيانات عامة
            ("1005", "5",  {"bid": "119"}),              # بيانات الجيش - ثكنة 119
            ("1005", "5",  {"bid": "117"}),              # بيانات الجيش - ثكنة 117
            ("1005", "5",  {"bid": "116"}),              # بيانات الجيش - ثكنة 116
            ("2065", "1",  {}),                          # بيانات أخرى
            ("2089", "1",  {"areaEnum": 1}),             # بيانات المنطقة
            ("2069", "1",  {"uid": uid}),                # بيانات اللاعب
            ("3103", "5",  {}),                          # بيانات التحالف
            ("3111", "2",  {}),                          # بيانات التحالف
            ("3133", "8",  {}),                          # بيانات التحالف
            ("2089", "1",  {"areaEnum": 9}),             # بيانات المنطقة
            ("1056", "1",  {"language": 3}),             # اللغة
            ("3110", "1",  {}),                          # بيانات التحالف
            ("3101", "1",  {}),                          # بيانات التحالف
            ("1030", "6",  {"uid": uid}),                # بيانات اللاعب الكاملة
        ]
        
        for cmd, subcmd, data in init_cmds:
            try:
                self.send_cmd(cmd, subcmd, data)
                time.sleep(0.15)  # تأخير بسيط بين الأوامر
            except Exception as e:
                log.warning(f"[Init] فشل cmd={cmd}: {e}")
        
        log.info(f"[Init] تم إرسال {len(init_cmds)} أمر تهيئة")

    def wait_for_data(self, timeout=15):
        """ننتظر استقبال البيانات الأولية من السيرفر"""
        log.info("[*] ننتظر البيانات الأولية من السيرفر...")
        self.initial_data_received.wait(timeout=timeout)
        # ننتظر أكثر لاستقبال كل الردود
        time.sleep(5)
        keys = [k for k in self.castle_data.keys() if k.startswith('NOTIFY_') or k.startswith('_')]
        log.info(f"[+] تم استقبال {len(keys)} نوع بيانات: {keys}")
        return len(keys) > 0

    def train_troops(self, bid: str = "119", armyid: str = "710", armycount: str = None):
        """
        تدريب الجنود
        bid: معرف المبنى (119 = ثكنة)
        armyid: نوع الجيش (710 = مثلاً)
        armycount: العدد — إذا None يسأل السيرفر أولاً عن بيانات الجيش
        """
        # إذا ما حددت العدد، نحاول نحصل عليه من بيانات الجيش
        if armycount is None:
            army_info = self.get_army_info()
            total = army_info.get('totalArmy', {})
            log.info(f"[Train] الجيش الحالي: {total}")
            log.info(f"[Train] التدريب الجاري: {army_info.get('trainArmy', {})}")
            
            # نستخدم القيمة الافتراضية — سيتم تحسينها لاحقاً
            armycount = "245"
            log.info(f"[Train] عدد التدريب: {armycount}")
        
        # تحقق إذا فيه تدريب جاري
        army_info = self.castle_data.get('_armyInfo', {})
        train_army = army_info.get('trainArmy', {})
        if train_army:
            log.warning(f"[Train] ⚠ يوجد تدريب جاري: {train_army}")
            return False
        
        log.info(f"=== تدريب الجنود === bid={bid} army={armyid} count={armycount}")
        self.send_cmd("1005", "2", {
            "isget": False,
            "armycount": str(armycount),
            "bid": str(bid),
            "mode": "0",
            "armyid": str(armyid)
        })
        return True

    def port_mission(self):
        log.info("=== مهمة الميناء ===")
        self.send_cmd("1033", "2", {})

    def run(self, secret: bytes, interval: int = 300, index: int = 1):
        try:
            self.connect()
            if not self.handshake(secret, index):
                raise Exception("Gate handshake failed")
            self.alive = True
            threading.Thread(target=self.recv_loop, daemon=True).start()
            while self.alive:
                self.port_mission()
                log.info(f"Waiting {interval}s...")
                for _ in range(interval):
                    if not self.alive: break
                    time.sleep(1)
        except KeyboardInterrupt:
            raise
        finally:
            self.alive = False
            if self.sock:
                try: self.sock.close()
                except: pass
        # خرج من الـ loop → run_bot سيتولى reconnect مع token جديد

# ============================================================
# Main Flow
# ============================================================
# ============================================================
# Frida Session Reader → يقرأ session من اللعبة المفتوحة
# ============================================================
FRIDA_SESSION_SCRIPT = r"""
Java.perform(function() {
    try {
        // Try AccountManager first
        try {
            var AM = Java.use('com.onemt.sdk.user.base.AccountManager').getInstance();
            var sid = AM.getSessionId();
            var uid = AM.getUserId();
            if (sid && sid.length > 10) {
                send(JSON.stringify({status:"OK", userId:uid, sessionId:sid}));
                return;
            }
        } catch(e1) {
            send(JSON.stringify({status:"DEBUG", msg:"AccountManager: " + e1}));
        }

        // Try AccountProvider
        try {
            var AP = Java.use('com.onemt.sdk.core.provider.AccountProvider');
            var sid2 = AP.getSessionId();
            var uid2 = AP.getUserId();
            if (sid2 && sid2.length > 10) {
                send(JSON.stringify({status:"OK", userId:uid2, sessionId:sid2}));
                return;
            }
        } catch(e2) {
            send(JSON.stringify({status:"DEBUG", msg:"AccountProvider: " + e2}));
        }

        // Try SharedPreferences directly
        try {
            var ctx = Java.use('com.onemt.sdk.core.OneMTCore').getApplicationContext();
            var sp = ctx.getSharedPreferences("onemt_account", 0);
            var sid3 = sp.getString("sessionid", "");
            var uid3 = sp.getString("userid", "");
            if (sid3 && sid3.length > 10) {
                send(JSON.stringify({status:"OK", userId:uid3, sessionId:sid3}));
                return;
            }
        } catch(e3) {
            send(JSON.stringify({status:"DEBUG", msg:"SharedPrefs: " + e3}));
        }

        send(JSON.stringify({status:"NO_SESSION", msg:"No session found via any method"}));
    } catch(e) {
        send(JSON.stringify({status:"ERROR", msg:"" + e}));
    }
});
"""


def frida_login(email: str, password: str, timeout: int = 20) -> dict:
    """
    يقرأ session من اللعبة المفتوحة عبر Frida CLI (مرة واحدة فقط).
    بعدها يُحفظ في session_cache.json ولن تحتاج Frida مجدداً.
    """
    import subprocess, tempfile
    
    log.info(f"[Frida] Reading session from game...")
    
    # حفظ السكربت كملف مؤقت
    script_path = os.path.join(os.path.dirname(__file__), "_frida_session.js")
    with open(script_path, "w") as f:
        f.write(FRIDA_SESSION_SCRIPT)
    
    # تشغيل frida CLI
    cmd = [
        "frida", "-D", "emulator-5554",
        "-n", "Empire",
        "-l", script_path,
        "-q"
    ]
    
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        raise Exception(
            "❌ frida غير مثبت!\n"
            "   pip install frida-tools"
        )
    except subprocess.TimeoutExpired:
        raise Exception("❌ Timeout — تأكد أن اللعبة مفتوحة و Frida server شغال")
    
    # تحليل النتيجة
    uid = None
    sid = None
    error = None
    
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        # البحث عن payload JSON
        if '"status"' in line and '"OK"' in line:
            # استخراج JSON من السطر
            try:
                # الخط قد يكون: message: {'type': 'send', 'payload': '{"status":"OK",...}'} data: None
                # أو مباشرة JSON
                import re
                json_match = re.search(r'\{[^{}]*"status"\s*:\s*"OK"[^{}]*\}', line)
                if json_match:
                    data = json.loads(json_match.group())
                    uid = data.get("userId", "")
                    sid = data.get("sessionId", "")
            except:
                pass
        elif "NO_SESSION" in line:
            error = "اللعبة مفتوحة لكن ما فيها session. سجّل دخول في اللعبة أولاً!"
        elif "ERROR" in line and "status" in line:
            error = line
    
    # تنظيف
    try:
        os.remove(script_path)
    except:
        pass
    
    if error:
        raise Exception(f"❌ {error}")
    if not sid:
        raise Exception(
            f"❌ فشل قراءة الـ session\n"
            f"   Output: {output[:300]}\n\n"
            f"   تأكد أن:\n"
            f"   1. اللعبة مفتوحة ومسجّل دخول\n"
            f"   2. Frida server شغال على المحاكي"
        )
    
    log.info(f"[Frida] ✅ Got session! userId={uid}, session={sid[:30]}...")
    
    # حفظ الـ session (multi-account cache)
    cache_file = os.path.join(os.path.dirname(__file__), "session_cache.json")
    try:
        with open(cache_file) as f:
            all_cache = json.load(f)
        if not isinstance(all_cache, dict) or "accounts" not in all_cache:
            all_cache = {"accounts": {}}
    except:
        all_cache = {"accounts": {}}
    
    all_cache["accounts"][email] = {
        "userId": uid, "sessionId": sid, "timestamp": time.time()
    }
    with open(cache_file, "w") as f:
        json.dump(all_cache, f, indent=2)
    log.info(f"[Frida] Session cached → session_cache.json")
    
    return {"subtoken": sid, "uid": uid}

def load_cached_session(email: str) -> dict:
    """تحميل session محفوظ لهذا الحساب (يدوم 7 أيام)"""
    cache_file = os.path.join(os.path.dirname(__file__), "session_cache.json")
    try:
        with open(cache_file) as f:
            all_cache = json.load(f)
        # Support both old format (single account) and new format (multi-account)
        if "accounts" in all_cache:
            acc = all_cache["accounts"].get(email, {})
        elif all_cache.get("email") == email:
            acc = all_cache  # old single-account format
            acc["sessionId"] = acc.get("sessionId", "")
        else:
            return None
        
        if acc.get("sessionId") and time.time() - acc.get("timestamp", 0) < 7 * 86400:
            log.info(f"[Cache] Using cached session for {email}")
            return {"subtoken": acc["sessionId"], "uid": acc["userId"]}
    except:
        pass
    return None


def invalidate_cached_session(email: str):
    """حذف session منتهي الصلاحية من الـ cache"""
    cache_file = os.path.join(os.path.dirname(__file__), "session_cache.json")
    try:
        with open(cache_file) as f:
            all_cache = json.load(f)
        if "accounts" in all_cache and email in all_cache["accounts"]:
            del all_cache["accounts"][email]
            with open(cache_file, "w") as f:
                json.dump(all_cache, f, indent=2)
            log.info(f"[Cache] Invalidated session for {email}")
    except:
        pass

def http_login(email: str, password: str) -> dict:
    """
    تسجيل دخول: يحاول الـ cache أولاً، ثم Frida
    """
    # 1) جرب الـ cache
    cached = load_cached_session(email)
    if cached:
        return cached
    
    # 2) استخدم Frida
    return frida_login(email, password)

def run_bot(session_id: str = None, user_id: str = None,
            email: str = None, password: str = None,
            interval: int = 300):
    """
    شغّل البوت.
    إما session_id مباشرةً أو email+password للحصول على session جديد.
    """
    if email and password:
        log.info("[HTTP] Logging in via email/password...")
        info = http_login(email, password)
        session_id = info["subtoken"]
        if not user_id:
            user_id = info.get("uid", "")
        log.info(f"[HTTP] Got session: {session_id[:40]}...")
    
    if not session_id:
        raise Exception("يجب توفير --session أو --email و --password")
    
    token = {"subtoken": session_id, "userid": user_id}
    
    while True:
        try:
            # كل مرة: احصل على gate credentials جديدة من login server
            log.info(f"Login Server: {LOGIN_SERVER[0]}:{LOGIN_SERVER[1]}")
            login_srv = LoginServer(*LOGIN_SERVER)
            login_srv.connect()
            result = login_srv.do_handshake(token)
            login_srv.close()
            
            if not result['success']:
                log.error("Login failed!")
                time.sleep(30); continue
            
            gate   = result['gate']
            secret = result['secret']
            gate_ip   = gate['gateip']
            gate_port = int(gate['gateport'])
            
            log.info(f"Gate: {gate_ip}:{gate_port}")
            log.info(f"UID: {gate['uid']} | Server: {gate['servername']}")
            
            # اتصل بـ Gate وشغّل المهام
            bot = GateBot(gate_ip, gate_port, gate)
            bot.run(secret, interval)
            
        except KeyboardInterrupt:
            log.info("Stopped"); sys.exit(0)
        except Exception as e:
            err = str(e)
            if "406" in err or "منتهي" in err or "session" in err.lower():
                # Session منتهية الصلاحية - يحتاج Frida لتجديدها
                log.warning(f"[!] Session expired: {err}")
                if email and password:
                    log.info("[!] Refreshing session via Frida...")
                    invalidate_cached_session(email)
                    try:
                        info = frida_login(email, password)
                        session_id = info["subtoken"]
                        user_id = info.get("uid", user_id)
                        token = {"subtoken": session_id, "userid": user_id}
                        log.info("[!] Session refreshed!")
                    except Exception as fe:
                        log.error(f"Session refresh failed: {fe}")
                        log.info("Retrying in 60s...")
                        time.sleep(60)
                else:
                    log.error("No email/password to refresh session. Stopping.")
                    sys.exit(1)
            else:
                log.error(f"Error: {err}")
            time.sleep(15)

# ============================================================
# Entry Point
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ONEMT Bot - بوت مهمة الميناء",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة:
  python onemt_bot.py --email user@mail.com --password mypass123
  python onemt_bot.py --session SESSION_ID --uid USER_ID
  python onemt_bot.py --email user@mail.com --password mypass123 --interval 600
        """
    )
    parser.add_argument("--email",    "-e", help="البريد الإلكتروني")
    parser.add_argument("--password", "-p", help="كلمة المرور")
    parser.add_argument("--session",  "-s", help="SessionId (بديل عن email+password)")
    parser.add_argument("--uid",      "-u", help="UserId (مع --session)")
    parser.add_argument("--interval", "-i", type=int, default=300, help="وقت بين المهام بالثواني (افتراضي: 300)")
    args = parser.parse_args()
    
    if not args.email and not args.session:
        parser.print_help()
        print("\n[!] يجب توفير --email و --password أو --session و --uid")
        sys.exit(1)
    
    log.info("="*50)
    log.info(" ONEMT Bot - بوت مهمة الميناء")
    log.info("="*50)
    
    run_bot(
        session_id=args.session,
        user_id=args.uid,
        email=args.email,
        password=args.password,
        interval=args.interval
    )

