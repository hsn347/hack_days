"""
اختبار تلقائي لجميع combinationsالممكنة من DH prime + HMAC formula
ضد login server حقيقي
"""
import socket, base64, hashlib, hmac as hmac_mod, os, itertools, time

LOGIN_SERVER = ("119.8.212.255", 10000)

# ============================================================
# DH candidates
# ============================================================
PRIMES = {
    "2^63-3  (0x7FFFD)": 0x7FFFFFFFFFFFFFFD,
    "2^64-59 (0xFFFFC5)": 0xFFFFFFFFFFFFFFC5,
    "2^64-189 (0xFF43)":  0xFFFFFFFFFFFFFF43,
    "2^64-257 (0xFEFF)":  0xFFFFFFFFFFFFFEFF,
    "2^64-15  (0xFFF1)":  0xFFFFFFFFFFFFFFF1,
    "2^64-5":             0xFFFFFFFFFFFFFFFB,
}
G = 5

def pow_mod(base, exp, mod):
    return pow(base, exp, mod)

def dh_pub(priv, P):
    result = pow_mod(G, priv, P)
    return result.to_bytes(8, 'big')

def dh_secret(server_pub_bytes, priv, P):
    s = int.from_bytes(server_pub_bytes, 'big')
    result = pow_mod(s, priv, P)
    return result.to_bytes(8, 'big')

# ============================================================
# HMAC candidates
# ============================================================
def compute_all_hmacs(challenge: bytes, secret: bytes):
    results = {}
    
    # Standard HMAC-MD5
    results["HMAC-MD5(key=secret,msg=challenge)"] = \
        hmac_mod.new(secret, challenge, hashlib.md5).digest()[:8]
    results["HMAC-MD5(key=challenge,msg=secret)"] = \
        hmac_mod.new(challenge, secret, hashlib.md5).digest()[:8]
    
    # Simple MD5
    results["MD5(challenge+secret)"] = \
        hashlib.md5(challenge + secret).digest()[:8]
    results["MD5(secret+challenge)"] = \
        hashlib.md5(secret + challenge).digest()[:8]
    
    # HMAC-SHA1
    results["HMAC-SHA1(key=secret,msg=challenge)"] = \
        hmac_mod.new(secret, challenge, hashlib.sha1).digest()[:8]
    results["HMAC-SHA1(key=challenge,msg=secret)"] = \
        hmac_mod.new(challenge, secret, hashlib.sha1).digest()[:8]
    
    # XOR
    results["XOR(challenge,secret)"] = \
        bytes(a ^ b for a, b in zip(challenge, secret))
    
    # MD5(MD5(challenge)+MD5(secret))
    results["MD5(MD5(c)+MD5(s))"] = \
        hashlib.md5(hashlib.md5(challenge).digest() + 
                    hashlib.md5(secret).digest()).digest()[:8]
    
    # skynet custom: may use key-expansion differently
    # hmac with full length keys
    results["HMAC-MD5-full(key=secret,msg=challenge)"] = \
        hmac_mod.new(secret, challenge, hashlib.md5).digest()
    
    return results

# ============================================================
# Test one connection
# ============================================================
def test_combination(prime_name, P, hmac_name, hmac_fn):
    try:
        s = socket.socket()
        s.settimeout(8)
        s.connect(LOGIN_SERVER)
        
        buf = b""
        def recv_line():
            nonlocal buf
            while b"\n" not in buf:
                chunk = s.recv(512)
                if not chunk:
                    raise ConnectionError("closed")
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
        
        # 2. Client pub key
        priv = int.from_bytes(os.urandom(8), 'big') % P
        pub_bytes = dh_pub(priv, P)
        send_line(base64.b64encode(pub_bytes).decode())
        
        # 3. Server pub key
        server_pub_b64 = recv_line()
        server_pub = base64.b64decode(server_pub_b64)
        
        # 4. Compute secret
        secret = dh_secret(server_pub, priv, P)
        
        # 5. Compute HMAC using provided function
        hmac_bytes = hmac_fn(challenge, secret)
        
        # 6. Send HMAC (8 bytes)
        send_line(base64.b64encode(hmac_bytes[:8]).decode())
        
        # 7. Server response
        resp = recv_line()
        s.close()
        
        success = resp.startswith("200")
        return success, resp, secret.hex(), challenge.hex()
        
    except Exception as e:
        try: s.close()
        except: pass
        return False, str(e)[:50], "", ""

# ============================================================
# Main test loop
# ============================================================
print("="*60)
print("DH Prime + HMAC Formula Tester")
print(f"Server: {LOGIN_SERVER[0]}:{LOGIN_SERVER[1]}")
print("="*60)

# جمع كل الـ HMAC functions
def get_hmac_fns():
    return {
        "HMAC-MD5(key=secret,msg=challenge)": 
            lambda c,s: hmac_mod.new(s, c, hashlib.md5).digest()[:8],
        "HMAC-MD5(key=challenge,msg=secret)": 
            lambda c,s: hmac_mod.new(c, s, hashlib.md5).digest()[:8],
        "MD5(challenge+secret)[:8]":
            lambda c,s: hashlib.md5(c+s).digest()[:8],
        "MD5(secret+challenge)[:8]":
            lambda c,s: hashlib.md5(s+c).digest()[:8],
        "HMAC-SHA1(key=secret,msg=challenge)":
            lambda c,s: hmac_mod.new(s, c, hashlib.sha1).digest()[:8],
        "HMAC-SHA1(key=challenge,msg=secret)":
            lambda c,s: hmac_mod.new(c, s, hashlib.sha1).digest()[:8],
        "XOR(challenge,secret)":
            lambda c,s: bytes(a^b for a,b in zip(c,s)),
    }

hmac_fns = get_hmac_fns()
found = False

for prime_name, P in PRIMES.items():
    print(f"\n[PRIME] {prime_name}")
    for hmac_name, hmac_fn in hmac_fns.items():
        time.sleep(0.3)  # avoid rate limiting
        ok, resp, secret_hex, challenge_hex = test_combination(prime_name, P, hmac_name, hmac_fn)
        status = "[OK] 200!" if ok else f"[--] {resp[:30]}"
        print(f"  {status:35} | {hmac_name}")
        if ok:
            print(f"\n{'='*60}")
            print(f"  *** FOUND CORRECT COMBINATION! ***")
            print(f"  Prime:   {prime_name}  (P={hex(P)})")
            print(f"  HMAC:    {hmac_name}")
            print(f"  Secret:  {secret_hex}")
            print(f"{'='*60}")
            found = True
            break
    if found:
        break

if not found:
    print("\n[!] لم تنجح أي combination - قد يكون السيرفر يستخدم prime مختلف")
