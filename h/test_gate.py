"""
اختبار Gate Connection - بعد إصلاح format الـ handshake
- uid: الـ numeric id من field 5 في الـ 200 response
- handshake: plaintext JSON (بدون XOR)
- session يبدأ من 0x31 = 49
"""
import socket, base64, hashlib, hmac as hmac_mod, json, struct, time

GATE_IP   = "119.8.213.111"
GATE_PORT = 4000

# من الـ capture الجديد (حساب azjfhf48 أو الحساب الجديد)
# 200 response decode:
# Field 0: '259'         → world
# Field 1: 'koh_game_26' → server
# Field 2: '119.8.213.111' → gate IP
# Field 3: '4000'          → gate port
# Field 4: '250217'        → subid
# Field 5: '10600743'      → numeric uid ← الأهم!

NUMERIC_UID = "10600743"
SERVER      = "koh_game_26"
SUBID       = "250217"

# من الـ capture
# EXPECTED_USERNAME = "MTA2MDA3NDM=@a29oX2dhbWVfMjY=#MjUwMjE3"
# EXPECTED_HMAC     = "oCzB3KbMWu0="

XOR_KEY = "OSxHP.!-wd?'lao5"

def xor_msg(data: bytes) -> bytes:
    key = XOR_KEY.encode()
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

def compute_gate_hmac(numeric_uid, servername, subid, index=1):
    uid_b64 = base64.b64encode(numeric_uid.encode()).decode()
    srv_b64 = base64.b64encode(servername.encode()).decode()
    sub_b64 = base64.b64encode(subid.encode()).decode()
    username = f"{uid_b64}@{srv_b64}#{sub_b64}"
    key_mat  = f"{username}:{index}".encode()
    hash_key = hashlib.md5(key_mat).digest()
    hmac_val = hmac_mod.new(hash_key, username.encode(), hashlib.sha1).digest()[:8]
    return username, base64.b64encode(hmac_val).decode()

def pack_handshake_plain(username, index, hmac_val):
    """Plaintext JSON handshake - NO XOR, NO session bytes"""
    body = json.dumps({"username": username, "index": index, "hmac": hmac_val}, separators=(',', ':'))
    return struct.pack('>H', len(body)) + body.encode()

def pack_request(cmd, subcmd="2", data=None, session=0x31):
    """XOR-encoded game command with raw session counter (starts at 0x31=49)"""
    body = json.dumps({"cmd": cmd, "subcmd": subcmd, "data": data or {}}, separators=(',', ':'))
    xored = xor_msg(body.encode())
    length = len(xored) + 4  # body + session bytes
    return struct.pack('>H', length) + xored + struct.pack('>I', session)

def test_gate(numeric_uid, server, subid, index=1):
    username, hmac_val = compute_gate_hmac(numeric_uid, server, subid, index)
    
    print(f"[*] Gate: {GATE_IP}:{GATE_PORT}")
    print(f"[*] username: {username}")
    print(f"[*] hmac:     {hmac_val}")
    
    # Verify matches expected from capture
    expected_user = "MTA2MDA3NDM=@a29oX2dhbWVfMjY=#MjUwMjE3"
    expected_hmac = "oCzB3KbMWu0="
    print(f"[*] username match: {username == expected_user}")
    print(f"[*] hmac match:     {hmac_val == expected_hmac}")
    
    hs = pack_handshake_plain(username, index, hmac_val)
    print(f"[*] Handshake packet len: {len(hs)} (expected: 87)")
    print(f"[*] Handshake hex: {hs.hex()}")
    
    s = socket.socket()
    s.settimeout(20)
    try:
        s.connect((GATE_IP, GATE_PORT))
        print("[+] TCP connected!")
        s.sendall(hs)
        print("[*] Handshake sent")
        resp = s.recv(1024)
        print(f"[GATE RESP] {resp!r}")
        if resp:
            print("[+] Got response!")
        s.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("="*50)
    print("Gate Test - Fixed Format")
    print("="*50)
    test_gate(NUMERIC_UID, SERVER, SUBID)
