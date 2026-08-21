#!/usr/bin/env python3
"""
token_format_tester.py
يختبر كل الـ formats الممكنة للـ token حتى يجد الصحيح
نتحكم في client_priv → نحسب DH secret → نشفر التوكن → نختبر
"""
import socket, struct, base64, hashlib, time
import Crypto.Cipher.DES as DES_lib

# ============ SETTINGS ============
LOGIN_HOST = "119.8.212.255"
LOGIN_PORT = 10000

# بيانات الحساب (king7moe1990@gmail.com)
LOGIN_TYPE  = "email"
EMAIL       = "king7moe1990@gmail.com"
UID         = "84d85f70eff2c02970105e1f17d8272a"
SESSION     = "KMVYLv24+KhWDrmpsxRD2yvJPUPPIVuPNeFK/hoId1xyBPm+Dkyn455c3g+1FndAwZ6ApSlfn6GVa6alUNQNdw=="
GOOGLE_ID   = "111689573946604734775"
SERVER_NAME = "koh_game_26"

# DH parameters (Skynet/Mersenne)
DH_G = 5
DH_P = (1 << 61) - 1  # 2305843009213693951

# ============ CRYPTO ============
def b64e(b: bytes) -> str: return base64.b64encode(b).decode()
def b64d(s: str) -> bytes: return base64.b64decode(s)
def i2b(n: int) -> bytes:  return n.to_bytes(8, 'big')
def b2i(b: bytes) -> int:  return int.from_bytes(b, 'big')

def custom_hmac64(msg: bytes, key: bytes) -> bytes:
    buf = bytearray(16)
    for i, b in enumerate(msg):
        buf[i % 16] ^= b ^ key[i % len(key)]
    return hashlib.md5(bytes(buf)).digest()[:8]

def des_ecb(plaintext: bytes, key: bytes) -> bytes:
    rem = len(plaintext) % 8
    if rem: plaintext = plaintext + b'\x00' * (8 - rem)
    c = DES_lib.new(key[:8], DES_lib.MODE_ECB)
    return c.encrypt(plaintext)

# ============ DH HANDSHAKE ============
def do_handshake(sock, client_priv: int):
    """
    DH handshake - نتحكم في client_priv → نعرف secret
    Returns: dh_secret (bytes, 8)
    """
    # 1. استقبل challenge
    challenge_b64 = sock.recv(1024).decode().strip()
    challenge = b64d(challenge_b64)
    print(f"  [DH] Challenge: {challenge_b64}")

    # 2. أرسل client_pub
    client_pub = pow(DH_G, client_priv, DH_P)
    sock.sendall(b64e(i2b(client_pub)).encode() + b'\n')
    print(f"  [DH] Sent client_pub: {b64e(i2b(client_pub))}")

    # 3. استقبل server_pub
    server_pub_b64 = sock.recv(1024).decode().strip()
    server_pub = b2i(b64d(server_pub_b64))
    print(f"  [DH] Server pub: {server_pub_b64}")

    # 4. احسب DH secret
    dh_secret_int = pow(server_pub, client_priv, DH_P)
    dh_secret = i2b(dh_secret_int)
    print(f"  [DH] Secret: {b64e(dh_secret)} (hex={dh_secret.hex()})")

    # 5. أرسل HMAC
    hmac_val = custom_hmac64(challenge, dh_secret)
    sock.sendall(b64e(hmac_val).encode() + b'\n')
    print(f"  [DH] Sent HMAC: {b64e(hmac_val)}")

    # 6. استقبل "200 challenge success"
    resp = sock.recv(1024).decode().strip()
    print(f"  [DH] Response: {resp}")

    if not resp.startswith("200"):
        raise Exception(f"DH failed: {resp}")

    return dh_secret

# ============ TOKEN BUILDERS ============
def build_part2(key: bytes) -> bytes:
    return des_ecb(SERVER_NAME.encode(), key)

def build_parts_345(key: bytes) -> bytes:
    """Parts 3,4,5 - نجرب مع zero bytes أولاً"""
    p3 = b64e(des_ecb(b'\x00' * 80, key)).encode()
    p4 = b64e(des_ecb(b'\x00' * 8, key)).encode()
    p5 = b64e(des_ecb(b'\x00' * 8, key)).encode()
    return p3, p4, p5

def send_token(sock, key: bytes, part1_plaintext: bytes) -> str:
    """يشفر ويرسل التوكن ويرجع الـ response"""
    p1 = b64e(des_ecb(part1_plaintext, key)).encode()
    p2 = b64e(build_part2(key)).encode()
    p3, p4, p5 = build_parts_345(key)

    token = p1 + b'@' + p2 + b'@' + p3 + b'@' + p4 + b'@' + p5 + b'\n'
    sock.sendall(token)

    resp = sock.recv(4096).decode().strip()
    return resp

# ============ FORMAT CANDIDATES ============
def sep(s):
    """Helper: try different separators"""
    parts = [LOGIN_TYPE, EMAIL, UID, SESSION, GOOGLE_ID, "true"]
    return s.join(parts).encode()

FORMAT_CANDIDATES = [
    # --- \n separators ---
    ("LF: type\\nmail\\nuid\\nsess\\ngid\\ntrue\\n",
     lambda: (LOGIN_TYPE + "\n" + EMAIL + "\n" + UID + "\n" + SESSION + "\n" + GOOGLE_ID + "\ntrue\n").encode()),
    ("LF: type\\nmail\\nuid\\nsess\\ntrue\\ngid\\n",
     lambda: (LOGIN_TYPE + "\n" + EMAIL + "\n" + UID + "\n" + SESSION + "\ntrue\n" + GOOGLE_ID + "\n").encode()),
    ("LF: type\\nmail\\nuid\\nsess\\ngid\\ntrue",
     lambda: (LOGIN_TYPE + "\n" + EMAIL + "\n" + UID + "\n" + SESSION + "\n" + GOOGLE_ID + "\ntrue").encode()),
    ("LF: type\\nmail\\nuid\\nsess\\ntrue",
     lambda: (LOGIN_TYPE + "\n" + EMAIL + "\n" + UID + "\n" + SESSION + "\ntrue").encode()),
    ("LF: type\\nuid\\nsess\\ngid\\ntrue\\n",
     lambda: (LOGIN_TYPE + "\n" + UID + "\n" + SESSION + "\n" + GOOGLE_ID + "\ntrue\n").encode()),

    # --- | separators ---
    ("PIPE: type|mail|uid|sess|gid|true",
     lambda: sep("|")),
    ("PIPE: type|mail|uid|sess|true|gid",
     lambda: ("|".join([LOGIN_TYPE, EMAIL, UID, SESSION, "true", GOOGLE_ID])).encode()),

    # --- @ separators ---
    ("AT: type@mail@uid@sess@gid@true",
     lambda: sep("@")),

    # --- \0 separators ---
    ("NUL: type\\0mail\\0uid\\0sess\\0gid\\0true",
     lambda: sep("\x00")),

    # --- without google_id ---
    ("LF: type\\nmail\\nuid\\nsess\\n",
     lambda: (LOGIN_TYPE + "\n" + EMAIL + "\n" + UID + "\n" + SESSION + "\n").encode()),
    ("AT: type@mail@uid@sess",
     lambda: (LOGIN_TYPE + "@" + EMAIL + "@" + UID + "@" + SESSION).encode()),
    ("PIPE: type|mail|uid|sess",
     lambda: (LOGIN_TYPE + "|" + EMAIL + "|" + UID + "|" + SESSION).encode()),

    # --- spaces ---
    ("SPC: type mail uid sess gid true",
     lambda: sep(" ")),

    # --- TAB ---
    ("TAB: type\\tmail\\tuid\\tsess\\tgid\\ttrue",
     lambda: sep("\t")),

    # --- JSON ---
    ("JSON: {type,email,uid,session,googleId}",
     lambda: f'{{"type":"{LOGIN_TYPE}","email":"{EMAIL}","uid":"{UID}","session":"{SESSION}","googleId":"{GOOGLE_ID}"}}'.encode()),
    ("JSON: {type,email,uid,session}",
     lambda: f'{{"type":"{LOGIN_TYPE}","email":"{EMAIL}","uid":"{UID}","session":"{SESSION}"}}'.encode()),

    # --- Skynet standard: just the session ---
    ("RAW: session_only",
     lambda: b64d(SESSION)),
    ("B64: base64(session)",
     lambda: SESSION.encode()),

    # --- comma ---
    ("COMMA: type,mail,uid,sess,gid,true",
     lambda: sep(",")),

    # --- colon ---
    ("COLON: type:mail:uid:sess:gid:true",
     lambda: sep(":")),
]

# ============ MAIN ============
def test_format(fmt_name: str, build_fn, client_priv: int):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((LOGIN_HOST, LOGIN_PORT))

        key = do_handshake(sock, client_priv)
        plaintext = build_fn()
        print(f"  Plain({len(plaintext)} bytes): {plaintext[:60]!r}{'...' if len(plaintext)>60 else ''}")
        resp = send_token(sock, key, plaintext)
        sock.close()
        return resp
    except Exception as e:
        return f"ERROR: {e}"

def main():
    import random
    print("=" * 60)
    print("Token Format Tester")
    print("=" * 60)
    print(f"Account: {EMAIL}")
    print(f"UID:     {UID}")
    print(f"Session: {SESSION[:30]}...")
    print()

    results = {}
    found = False

    for i, (name, build_fn) in enumerate(FORMAT_CANDIDATES):
        # استخدم client_priv مختلف لكل محاولة لتجنب rate limiting
        client_priv = random.randint(10000000, 2**60)

        print(f"\n[{i+1}/{len(FORMAT_CANDIDATES)}] Testing: {name}")
        resp = test_format(name, build_fn, client_priv)
        results[name] = resp

        if resp.startswith("200"):
            print(f"  *** SUCCESS! *** Response: {resp[:100]}")
            found = True
            break
        elif "401" in resp:
            print(f"  [401] Wrong format/creds")
        else:
            print(f"  Response: {resp[:100]}")

        time.sleep(1)  # تجنب rate limit

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY:")
    for name, resp in results.items():
        status = "✓ 200" if resp.startswith("200") else "✗ " + resp[:30]
        print(f"  {status} | {name}")

    if not found:
        print("\n[!] No format worked. Session might be expired.")
        print("    Switch accounts in game to get fresh session, then retry.")

if __name__ == "__main__":
    main()
