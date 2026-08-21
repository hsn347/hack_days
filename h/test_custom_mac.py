"""
Custom MAC extracted from lhmac64 ARM64 binary in libcocos2dlua.so
Algorithm:
1. Create 64-byte block from challenge and secret (with swapped 32-bit halves)
2. Run ONE block of MD5 compression (without final addition of initial values)
3. XOR specific output registers: result = (C^D) || (B^A) as LE uint32 pairs

Also tests the correct DH: P=2^64-59, LITTLE-ENDIAN byte order
"""
import socket, base64, hashlib, hmac as hmac_mod, os, time, struct

LOGIN_SERVER = ("119.8.212.255", 10000)

# DH parameters from ARM64 binary (mov x9, #-0x3b)
P = 0xFFFFFFFFFFFFFFC5   # 2^64-59
G = 5

def dh_exchange_le(priv_bytes):
    priv_int = int.from_bytes(priv_bytes, 'little')
    pub_int  = pow(G, priv_int, P)
    return pub_int.to_bytes(8, 'little')

def dh_secret_le(server_pub_bytes, priv_bytes):
    spub = int.from_bytes(server_pub_bytes, 'little')
    priv = int.from_bytes(priv_bytes, 'little')
    if spub >= P: spub -= P
    return pow(spub, priv, P).to_bytes(8, 'little')

# ======================================================
# Custom MD5-based MAC from lhmac64
# ======================================================
def _md5_compress_no_add(block64: bytes):
    """
    MD5 single-block compression WITHOUT adding initial values at end.
    Returns (A, B, C, D) after 64 rounds.
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
        A = D
        D = C
        C = B
        rot_s = S[i]
        B = (B + ((F << rot_s) | (F >> (32 - rot_s)))) & 0xFFFFFFFF
    
    return A, B, C, D

def custom_hmac64(challenge: bytes, secret: bytes) -> bytes:
    """
    Custom MAC from lhmac64 ARM64 binary.
    
    Block layout: [ch[4:8], ch[0:4], sec[4:8], sec[0:4]] repeated 4 times
    (each as LE uint32)
    
    Output: (C_final XOR D_final as LE) || (B_final XOR A_final as LE)
    """
    # Load as two 32-bit halves each (LE)
    ch_lo, ch_hi = struct.unpack('<2I', challenge)   # bytes 0-3 and 4-7
    sec_lo, sec_hi = struct.unpack('<2I', secret)    # bytes 0-3 and 4-7
    
    # Build 64-byte block (pattern repeated 4 times)
    pattern = struct.pack('<4I', ch_hi, ch_lo, sec_hi, sec_lo)
    block64 = pattern * 4
    
    # MD5 compression (without final addition)
    A, B, C, D = _md5_compress_no_add(block64)
    
    # Custom XOR output from disassembly
    w8 = (C ^ D) & 0xFFFFFFFF   # C_final XOR D_final
    w9 = (B ^ A) & 0xFFFFFFFF   # B_final XOR A_final
    
    return struct.pack('<2I', w8, w9)

# ======================================================
# Test all formulas
# ======================================================
formulas = {
    "custom_md5_mac (from binary)":
        lambda c, s: custom_hmac64(c, s),
    "HMAC-MD5(key=challenge,msg=secret)":
        lambda c, s: hmac_mod.new(c, s, hashlib.md5).digest()[:8],
    "HMAC-MD5(key=secret,msg=challenge)":
        lambda c, s: hmac_mod.new(s, c, hashlib.md5).digest()[:8],
    "MD5(challenge+secret)[:8]":
        lambda c, s: hashlib.md5(c+s).digest()[:8],
    "MD5(ch_hi+ch_lo+sec_hi+sec_lo)[:8]":
        lambda c, s: hashlib.md5(c[4:]+c[:4]+s[4:]+s[:4]).digest()[:8],
}

print("="*65)
print(f"P=0x{P:X} (2^64-59), G={G}, LITTLE-ENDIAN byte order")
print("="*65)

for fname, ffn in formulas.items():
    try:
        time.sleep(0.8)
        s2 = socket.socket()
        s2.settimeout(10)
        s2.connect(LOGIN_SERVER)
        
        buf = b""
        def rl():
            global buf
            while b"\n" not in buf:
                chunk = s2.recv(512)
                if not chunk: raise ConnectionError()
                buf += chunk
            idx = buf.index(b"\n")
            line = buf[:idx].decode().strip()
            buf = buf[idx+1:]
            return line
        
        ch = base64.b64decode(rl())
        priv = os.urandom(8)
        pub  = dh_exchange_le(priv)
        s2.sendall((base64.b64encode(pub).decode() + "\n").encode())
        spub = base64.b64decode(rl())
        sec  = dh_secret_le(spub, priv)
        mac  = ffn(ch, sec)
        s2.sendall((base64.b64encode(mac[:8]).decode() + "\n").encode())
        resp = rl()
        s2.close()
        buf = b""
        status = "[200 OK!!!]" if resp.startswith("200") else f"[400]     "
        print(f"{status} {fname}")
        if resp.startswith("200"):
            print(f"\n*** FOUND! P=0x{P:X}, formula={fname} ***")
            print(f"  Challenge: {ch.hex()}")
            print(f"  Secret:    {sec.hex()}")
            print(f"  MAC:       {mac.hex()}")
    except Exception as e:
        print(f"[ERR]      {fname}: {e}")
