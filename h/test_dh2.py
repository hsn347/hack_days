"""
اختبار محدّث يستخدم P=2^64-59 و LITTLE-ENDIAN (كما في libcocos2dlua.so)
"""
import socket, base64, hashlib, hmac as hmac_mod, os, time

LOGIN_SERVER = ("119.8.212.255", 10000)

# P من ARM64 disassembly: mov x9, #-0x3b → P = 2^64-59
P = 0xFFFFFFFFFFFFFFC5
G = 5

def dh_exchange_le(priv_bytes):
    """pow(G, priv_LE, P) → LE bytes"""
    priv_int = int.from_bytes(priv_bytes, 'little')
    pub_int  = pow(G, priv_int, P)
    return pub_int.to_bytes(8, 'little')

def dh_secret_le(server_pub_bytes, priv_bytes):
    """pow(server_pub_LE, priv_LE, P) → LE bytes"""
    spub = int.from_bytes(server_pub_bytes, 'little')
    priv = int.from_bytes(priv_bytes, 'little')
    if spub >= P: spub -= P
    return pow(spub, priv, P).to_bytes(8, 'little')

def test_hmac(challenge, secret, formula_name, formula_fn):
    """اختبار HMAC formula واحدة"""
    try:
        hmac_bytes = formula_fn(challenge, secret)
        return base64.b64encode(hmac_bytes[:8]).decode()
    except:
        return None

def run_test():
    s = socket.socket()
    s.settimeout(10)
    s.connect(LOGIN_SERVER)
    
    buf = b""
    def recv_line():
        nonlocal buf
        while b"\n" not in buf:
            chunk = s.recv(512)
            if not chunk: raise ConnectionError("closed")
            buf += chunk
        idx = buf.index(b"\n")
        line = buf[:idx].decode().strip()
        buf = buf[idx+1:]
        return line
    
    def send_line(text):
        s.sendall((text + "\n").encode())
    
    # 1. Challenge
    challenge_b64 = recv_line()
    challenge = base64.b64decode(challenge_b64)
    print(f"Challenge: {challenge_b64} ({challenge.hex()})")
    
    # 2. Client pub (LE)
    priv_bytes = os.urandom(8)
    pub_bytes  = dh_exchange_le(priv_bytes)
    pub_b64    = base64.b64encode(pub_bytes).decode()
    send_line(pub_b64)
    print(f"ClientPub: {pub_b64} ({pub_bytes.hex()})")
    
    # 3. Server pub
    server_b64 = recv_line()
    server_bytes = base64.b64decode(server_b64)
    print(f"ServerPub: {server_b64} ({server_bytes.hex()})")
    
    # 4. Secret (LE)
    secret_bytes = dh_secret_le(server_bytes, priv_bytes)
    print(f"Secret LE: {secret_bytes.hex()}")
    
    # اختبار كل HMAC formulas
    formulas = {
        "HMAC-MD5(key=challenge,msg=secret)":
            lambda c,s: hmac_mod.new(c, s, hashlib.md5).digest()[:8],
        "HMAC-MD5(key=secret,msg=challenge)":
            lambda c,s: hmac_mod.new(s, c, hashlib.md5).digest()[:8],
        "MD5(challenge+secret)[:8]":
            lambda c,s: hashlib.md5(c+s).digest()[:8],
        "MD5(secret+challenge)[:8]":
            lambda c,s: hashlib.md5(s+c).digest()[:8],
        "HMAC-SHA1(key=challenge,msg=secret)":
            lambda c,s: hmac_mod.new(c, s, hashlib.sha1).digest()[:8],
        "HMAC-SHA1(key=secret,msg=challenge)":
            lambda c,s: hmac_mod.new(s, c, hashlib.sha1).digest()[:8],
        "XOR(challenge,secret)":
            lambda c,s: bytes(a^b for a,b in zip(c,s)),
        "MD5(challenge)[:8]":
            lambda c,s: hashlib.md5(c).digest()[:8],
    }
    
    # إرسال formula واحدة فقط (نفتح connection جديدة لكل formula)
    # - أولاً HMAC-MD5(key=challenge,msg=secret) (الأكثر احتمالاً)
    formula_name = "HMAC-MD5(key=challenge,msg=secret)"
    formula_fn = formulas[formula_name]
    mac_bytes = formula_fn(challenge, secret_bytes)
    mac_b64   = base64.b64encode(mac_bytes).decode()
    send_line(mac_b64)
    print(f"HMAC ({formula_name}): {mac_b64}")
    
    resp = recv_line()
    s.close()
    print(f"Response: {resp}")
    return resp.startswith("200")

# اختبار كل الـ HMAC formulas - connection جديدة لكل واحدة
formulas_list = [
    ("HMAC-MD5(key=challenge,msg=secret)", lambda c,s: hmac_mod.new(c, s, hashlib.md5).digest()[:8]),
    ("HMAC-MD5(key=secret,msg=challenge)", lambda c,s: hmac_mod.new(s, c, hashlib.md5).digest()[:8]),
    ("MD5(challenge+secret)[:8]",          lambda c,s: hashlib.md5(c+s).digest()[:8]),
    ("MD5(secret+challenge)[:8]",          lambda c,s: hashlib.md5(s+c).digest()[:8]),
    ("HMAC-SHA1(key=challenge,msg=secret)",lambda c,s: hmac_mod.new(c, s, hashlib.sha1).digest()[:8]),
    ("XOR(challenge,secret)",              lambda c,s: bytes(a^b for a,b in zip(c,s))),
]

print("="*60)
print(f"Testing P=0x{P:X} (2^64-59), G={G}, LITTLE-ENDIAN")
print("="*60)

for fname, ffn in formulas_list:
    try:
        time.sleep(0.5)
        s2 = socket.socket()
        s2.settimeout(10)
        s2.connect(LOGIN_SERVER)
        
        buf2 = b""
        def r2():
            global buf2
            while b"\n" not in buf2:
                chunk = s2.recv(512)
                if not chunk: raise ConnectionError()
                buf2 += chunk
            idx = buf2.index(b"\n")
            line = buf2[:idx].decode().strip()
            buf2 = buf2[idx+1:]
            return line
        
        ch = base64.b64decode(r2())
        priv = os.urandom(8)
        pub  = dh_exchange_le(priv)
        s2.sendall((base64.b64encode(pub).decode() + "\n").encode())
        spub = base64.b64decode(r2())
        sec  = dh_secret_le(spub, priv)
        mac  = ffn(ch, sec)
        s2.sendall((base64.b64encode(mac[:8]).decode() + "\n").encode())
        resp2 = r2()
        s2.close()
        status = "[200 OK!]" if resp2.startswith("200") else f"[400]   "
        print(f"{status} {fname}")
        if resp2.startswith("200"):
            print(f"\n*** FOUND! P=0x{P:X}, formula={fname} ***")
            print(f"  Secret: {sec.hex()}")
            break
    except Exception as e:
        print(f"[ERR]    {fname}: {e}")
