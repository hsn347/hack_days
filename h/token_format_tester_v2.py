#!/usr/bin/env python3
"""
token_format_tester_v2.py
يستخدم DH parameters الصحيحة من onemt_bot.py ويختبر formats مختلفة
"""
import sys
sys.path.insert(0, r'E:\osmanli')

import socket, struct, base64, time, os

# استورد الـ DH و HMAC الصحيحين من onemt_bot.py
from onemt_bot import (
    dh_exchange, dh_secret, hmac64, des_encode_ecb,
    random_key, DH_G, DH_P, LOGIN_SERVER
)

print(f"DH_P = {hex(DH_P)}")
print(f"DH_G = {DH_G}")

# ============================================================
# بيانات الحساب
# ============================================================
LOGIN_TYPE  = "email"
EMAIL       = "king7moe1990@gmail.com"
UID         = "84d85f70eff2c02970105e1f17d8272a"
SESSION     = "KMVYLv24+KhWDrmpsxRD2yvJPUPPIVuPNeFK/hoId1xyBPm+Dkyn455c3g+1FndAwZ6ApSlfn6GVa6alUNQNdw=="
GOOGLE_ID   = "111689573946604734775"
SERVER_NAME = "koh_game_26"

def b64e(b): return base64.b64encode(b).decode()
def b64d(s): return base64.b64decode(s)

# ============================================================
# DH Handshake (بالكود الصحيح)
# ============================================================
def do_handshake(sock):
    buf = b""
    def recv_line():
        nonlocal buf
        while b"\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk: raise ConnectionError("closed")
            buf += chunk
        idx = buf.index(b"\n")
        line = buf[:idx].decode().strip()
        buf = buf[idx+1:]
        return line

    def send_line(s):
        sock.sendall((s + "\n").encode())

    # 1. Challenge
    challenge_b64 = recv_line()
    challenge = b64d(challenge_b64)
    print(f"    Challenge: {challenge_b64}")

    # 2. Client pub (CORRECT: LE DH)
    priv = random_key()
    pub  = dh_exchange(priv)
    send_line(b64e(pub))
    print(f"    ClientPub: {b64e(pub)}")

    # 3. Server pub
    server_pub_b64 = recv_line()
    server_pub = b64d(server_pub_b64)
    print(f"    ServerPub: {server_pub_b64}")

    # 4. Secret + HMAC
    secret = dh_secret(server_pub, priv)
    print(f"    Secret: {secret.hex()}")
    mac = hmac64(challenge, secret)
    send_line(b64e(mac))
    print(f"    HMAC: {b64e(mac)}")

    # 5. Response
    resp = recv_line()
    print(f"    HS resp: {resp}")
    if not resp.startswith("200"):
        raise Exception(f"DH failed: {resp}")

    return secret, recv_line  # recv_line closure captures buf

# ============================================================
# Token format candidates
# ============================================================
def build_token(secret, part1_bytes):
    """بناء الـ token كامل مع Parts 2-5"""
    p1 = b64e(des_encode_ecb(part1_bytes, secret))

    # Part 2: server name (11 bytes → 2 DES blocks = 16 bytes → 24 b64)
    p2 = b64e(des_encode_ecb(SERVER_NAME.encode(), secret))

    # Part 3: platform (80 bytes = 10 blocks)
    # نحاول مع قيم مختلفة
    platform_str = f"Android 8.1.0 {SERVER_NAME} Google com.game ar"
    p3 = b64e(des_encode_ecb(platform_str.encode(), secret))

    # Part 4: model (≤8 bytes = 1 block)
    p4 = b64e(des_encode_ecb(b"Generic", secret))

    # Part 5: carrier (≤8 bytes = 1 block)
    p5 = b64e(des_encode_ecb(b"Android", secret))

    msg = "@".join([p1, p2, p3, p4, p5])
    print(f"    Part1 len (b64={len(p1)}, bytes={len(b64d(p1))})")
    print(f"    Part2 len (b64={len(p2)}, bytes={len(b64d(p2))})")
    print(f"    Part3 len (b64={len(p3)}, bytes={len(b64d(p3))})")
    return msg

# Format builders (Part 1 only)
FORMATS = {
    "LF: type+mail+uid+sess+gid+true+NL":
        lambda: f"{LOGIN_TYPE}\n{EMAIL}\n{UID}\n{SESSION}\n{GOOGLE_ID}\ntrue\n",

    "LF: type+mail+uid+sess+true+gid+NL":
        lambda: f"{LOGIN_TYPE}\n{EMAIL}\n{UID}\n{SESSION}\ntrue\n{GOOGLE_ID}\n",

    "LF: type+mail+uid+sess+gid+true":
        lambda: f"{LOGIN_TYPE}\n{EMAIL}\n{UID}\n{SESSION}\n{GOOGLE_ID}\ntrue",

    "LF: type+mail+uid+sess+true":
        lambda: f"{LOGIN_TYPE}\n{EMAIL}\n{UID}\n{SESSION}\ntrue",

    "LF: type+mail+uid+sess":
        lambda: f"{LOGIN_TYPE}\n{EMAIL}\n{UID}\n{SESSION}",

    "AT: type@mail@uid@sess@gid@true":
        lambda: f"{LOGIN_TYPE}@{EMAIL}@{UID}@{SESSION}@{GOOGLE_ID}@true",

    "AT: type@uid@sess@gid@true":
        lambda: f"{LOGIN_TYPE}@{UID}@{SESSION}@{GOOGLE_ID}@true",

    "AT: type@mail@uid@sess@true":
        lambda: f"{LOGIN_TYPE}@{EMAIL}@{UID}@{SESSION}@true",

    "PIPE: type|mail|uid|sess|gid|true":
        lambda: f"{LOGIN_TYPE}|{EMAIL}|{UID}|{SESSION}|{GOOGLE_ID}|true",

    "SESSION only (raw bytes)":
        lambda: None,  # special: raw session bytes
}

def get_part1(fmt_name, fmt_fn, secret):
    if fmt_fn() is None:
        return base64.b64decode(SESSION)
    return fmt_fn().encode()

# ============================================================
# Run one test
# ============================================================
def test_format(fmt_name, fmt_fn):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(20)
        sock.connect(LOGIN_SERVER)

        secret, recv_line = do_handshake(sock)

        part1_bytes = get_part1(fmt_name, fmt_fn, secret)
        print(f"    Part1 plain ({len(part1_bytes)} bytes): {part1_bytes[:60]!r}")

        msg = build_token(secret, part1_bytes)
        sock.sendall((msg + "\n").encode())
        print(f"    Token sent ({len(msg)} chars)")

        auth_resp = recv_line()
        sock.close()
        return auth_resp

    except Exception as e:
        try: sock.close()
        except: pass
        return f"ERROR: {e}"

# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("Token Format Tester v2 (CORRECT DH params)")
    print("=" * 60)
    print(f"Account: {EMAIL}")
    print(f"Login Server: {LOGIN_SERVER}")
    print()

    results = {}
    for i, (name, fn) in enumerate(FORMATS.items()):
        print(f"\n[{i+1}/{len(FORMATS)}] {name}")
        resp = test_format(name, fn)
        results[name] = resp

        if resp.startswith("200"):
            print(f"  *** SUCCESS! {resp[:150]}")
            break
        elif "401" in resp:
            print(f"  [401] Wrong token format")
        elif "406" in resp:
            print(f"  [406] SDK token error (session expired?)")
        else:
            print(f"  Response: {resp[:100]}")

        time.sleep(1.5)

    print("\n" + "=" * 60)
    print("SUMMARY:")
    for name, resp in results.items():
        tag = "OK " if resp.startswith("200") else ("401" if "401" in resp else "406" if "406" in resp else "ERR")
        print(f"  [{tag}] {name}")

if __name__ == "__main__":
    main()
