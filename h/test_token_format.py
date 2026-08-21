"""
يجرب كل صيغ ممكنة للـ token حتى يحصل على 200
"""
import socket, base64, os, struct, time

LOGIN_SERVER = ("119.8.212.255", 10000)
P = 0xFFFFFFFFFFFFFFC5
G = 5

# البيانات المعروفة من Frida capture
SESSION = "BGywHJMjOoQhCzDhDjFi0qEaCDr8aJ602vsYfjG4Do4DMeS35icLr+G+51thn55ynKwMrbf1SiEifL3UxLXv0w=="
UID     = "1017d92537872288e8ddbca99fffcc90"
EMAIL   = "azjfhf48@gmail.com"

def dh_exchange(priv):
    return pow(G, int.from_bytes(priv, 'little'), P).to_bytes(8, 'little')

def dh_secret(spub, priv):
    s = int.from_bytes(spub, 'little')
    if s >= P: s -= P
    return pow(s, int.from_bytes(priv, 'little'), P).to_bytes(8, 'little')

def custom_hmac64(ch, sec):
    import struct as st
    K = [0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,0xf57c0faf,0x4787c62a,0xa8304613,0xfd469501,
         0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,0x6b901122,0xfd987193,0xa679438e,0x49b40821,
         0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,0xd62f105d,0x02441453,0xd8a1e681,0xe7d3fbc8,
         0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a,
         0xfffa3942,0x8771f681,0x6d9d6122,0xfde5380c,0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70,
         0x289b7ec6,0xeaa127fa,0xd4ef3085,0x04881d05,0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665,
         0xf4292244,0x432aff97,0xab9423a7,0xfc93a039,0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1,
         0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,0xf7537e82,0xbd3af235,0x2ad7d2bb,0xeb86d391]
    S = [7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,
         5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,
         4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,
         6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21]
    cl, ch_ = st.unpack('<2I', ch); sl, sh = st.unpack('<2I', sec)
    M = st.unpack('<16I', st.pack('<4I', ch_, cl, sh, sl) * 4)
    A,B,C,D = 0x67452301,0xEFCDAB89,0x98BADCFE,0x10325476
    for i in range(64):
        if i<16: F,g = (B&C)|(~B&D),i
        elif i<32: F,g = (D&B)|(~D&C),(5*i+1)%16
        elif i<48: F,g = B^C^D,(3*i+5)%16
        else: F,g = C^(B|~D),(7*i)%16
        F=(F+A+K[i]+M[g])&0xFFFFFFFF; A=D; D=C; C=B
        rs=S[i]; B=(B+((F<<rs)|(F>>(32-rs))))&0xFFFFFFFF
    return st.pack('<2I',(C^D)&0xFFFFFFFF,(B^A)&0xFFFFFFFF)

def des_enc(data, key):
    from Crypto.Cipher import DES
    n = (len(data)+7)//8
    return DES.new(key[:8], DES.MODE_ECB).encrypt(data.ljust(n*8, b'\x00'))

def b64e(b): return base64.b64encode(b).decode()

def try_format(label, token_str, extra_parts):
    try:
        time.sleep(0.3)
        s = socket.socket(); s.settimeout(8); s.connect(LOGIN_SERVER)
        buf = b""
        def rl():
            nonlocal buf
            while b"\n" not in buf:
                buf += s.recv(512)
            i = buf.index(b"\n"); line = buf[:i].decode().strip(); buf = buf[i+1:]; return line
        ch   = base64.b64decode(rl())
        priv = os.urandom(8); pub = dh_exchange(priv)
        s.sendall((b64e(pub)+"\n").encode())
        spub = base64.b64decode(rl()); sec = dh_secret(spub, priv)
        mac  = custom_hmac64(ch, sec)
        s.sendall((b64e(mac)+"\n").encode())
        resp = rl()
        if not resp.startswith("200"): s.close(); return f"[DH-FAIL] {resp[:30]}"
        
        # build token message
        parts = [b64e(des_enc(token_str.encode(), sec))]
        for ep in extra_parts:
            parts.append(b64e(des_enc(ep.encode() if isinstance(ep,str) else ep, sec)))
        msg = "@".join(parts) + "\n"
        s.sendall(msg.encode())
        auth = rl(); s.close()
        return auth[:80]
    except Exception as e:
        return f"ERR: {e}"

# صيغ الـ game_ver و platform و model و carrier الثابتة
GAME_VER = "NONE"
PLATFORM = "Android 8.1.0 device123 Google com.game ar"
MODEL    = "Generic"
CARRIER  = "Android"
EXTRAS   = [GAME_VER, PLATFORM, MODEL, CARRIER]

def try_format_pkcs7(token_str, extra_parts):
    from Crypto.Cipher import DES
    def enc(data, key):
        pad = 8 - (len(data) % 8)
        return DES.new(key[:8], DES.MODE_ECB).encrypt(data + bytes([pad]*pad))
    try:
        time.sleep(0.3)
        s = socket.socket(); s.settimeout(8); s.connect(LOGIN_SERVER)
        buf = b""
        def rl():
            nonlocal buf
            while b"\n" not in buf: buf += s.recv(512)
            i = buf.index(b"\n"); line = buf[:i].decode().strip(); buf = buf[i+1:]; return line
        ch = base64.b64decode(rl())
        priv = os.urandom(8); pub = dh_exchange(priv)
        s.sendall((b64e(pub)+"\n").encode())
        spub = base64.b64decode(rl()); sec = dh_secret(spub, priv)
        s.sendall((b64e(custom_hmac64(ch, sec))+"\n").encode())
        resp = rl()
        if not resp.startswith("200"): s.close(); return f"[DH-FAIL] {resp[:30]}"
        parts = [b64e(enc(token_str.encode(), sec))]
        for ep in extra_parts: parts.append(b64e(enc(ep.encode(), sec)))
        s.sendall(("@".join(parts)+"\n").encode())
        auth = rl(); s.close(); return auth[:80]
    except Exception as e: return f"ERR: {e}"

formats = [
    ("1. sessionId فقط",                           SESSION,                                                        EXTRAS),
    ("2. uid|sessionId",                            f"{UID}|{SESSION}",                                             EXTRAS),
    ("3. email|sessionId",                          f"{EMAIL}|{SESSION}",                                           EXTRAS),
    ("4. email|uid|sessionId",                      f"{EMAIL}|{UID}|{SESSION}",                                     EXTRAS),
    ("5. email@uid@sessionId",                      f"{EMAIL}@{UID}@{SESSION}",                                     EXTRAS),
    ("6. type|email|uid|sessionId",                 f"email|{EMAIL}|{UID}|{SESSION}",                               EXTRAS),
    ("7. uid|email|sessionId",                      f"{UID}|{EMAIL}|{SESSION}",                                     EXTRAS),
    ("8. sessionId raw bytes",                      base64.b64decode(SESSION).decode('latin1'),                     EXTRAS),
    ("9. sessionId|uid",                            f"{SESSION}|{UID}",                                             EXTRAS),
    ("10. sessionId ب PKCS7",                       SESSION,                                                        EXTRAS),  # نجربها بـ PKCS7
]

print("="*60)
print("Token Format Brute Force")
print(f"Session: {SESSION[:40]}...")
print(f"UID: {UID}")
print(f"Email: {EMAIL}")
print("="*60)

for label, tok, extras in formats:
    # الصيغة 10: استخدم PKCS7 بدل zero-pad
    if "PKCS7" in label:
        result = try_format_pkcs7(tok, extras)
    else:
        result = try_format(label, tok, extras)

    
    status = "[200 OK!]" if "200" in result else "[401]   "
    print(f"{status} {label}")
    print(f"   -> {result}")
    if "200" in result:
        print(f"\n*** FOUND! Token format: {label} ***")
        break

print("Done.")
