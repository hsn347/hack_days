from Crypto.Cipher import AES
import base64, hashlib, itertools

# Known plaintext/ciphertext from Frida
# encryptPacketForUC uses AES-CBC with fixed IV
ct1 = base64.b64decode("BZHu/6d0e14wLnDIBIHUHw==")         # P1 = \x10*16
ct2 = base64.b64decode("C/l2KU6HSIgcRlRd2G9cYA==")         # P2 = "test_input_123\x02\x02"
ct3 = base64.b64decode("KPn2WwOoVntkL9Z3T4lIItFPDRB0Vytek0zWjr01OiE=")[:16]  # P3 = "A"*16
ct4 = base64.b64decode("WH7jCasuGCdyVPwBzN4v6HxtlsZLqC9k09QGLcNPiD4=")[:16]  # P4 = "B"*16

P1 = b"\x10" * 16
P2 = b"test_input_123\x02\x02"
P3 = b"A" * 16
P4 = b"B" * 16

# XOR property for CBC: decrypt(ct1) XOR decrypt(ct2) = (P1 XOR iv) XOR (P2 XOR iv) = P1 XOR P2
# This is true for ANY key! Used to verify key without knowing IV.
xor_target_12 = bytes(a ^ b for a, b in zip(P1, P2))
xor_target_13 = bytes(a ^ b for a, b in zip(P1, P3))
xor_target_14 = bytes(a ^ b for a, b in zip(P1, P4))

print(f"XOR target P1^P2: {xor_target_12.hex()}")

so1 = '1e1434dd98fa2dd9'
so2 = '6c7d4e03f45a595f'
appKey = 'd252596f076c9213dce69cdb39d488ea'
gameAppKey = b'+|p\x7favx#}cy-|\x7fe|*&(bv-!/gv*qul*/'

def md5(s): return hashlib.md5(s if isinstance(s, bytes) else s.encode()).hexdigest()
def sha256(s): return hashlib.sha256(s if isinstance(s, bytes) else s.encode()).hexdigest()

# Verify appKey first
print(f"\n=== AppKey verification ===")
ak = b'd252596f076c9213dce69cdb39d488ea'
r1 = hashlib.md5(b'' + ak).hexdigest()
r2 = hashlib.md5(b'a' + ak).hexdigest()
r3 = hashlib.md5(b'{}' + ak).hexdigest()
print(f"md5('' + appKey) = {r1}  (expected: 55e72818a7b7dfcf873e53f7dc560b29) {'OK' if r1 == '55e72818a7b7dfcf873e53f7dc560b29' else 'FAIL'}")
print(f"md5('a' + appKey) = {r2}  (expected: 043ca6675533d2993210bdfc559a1aab) {'OK' if r2 == '043ca6675533d2993210bdfc559a1aab' else 'FAIL'}")
print(f"md5('{{}}' + appKey) = {r3}  (expected: 1dbfda593cb025f83d9620efaf8b3fb8) {'OK' if r3 == '1dbfda593cb025f83d9620efaf8b3fb8' else 'FAIL'}")

def test_aes_key(key, name):
    """Test AES key using XOR property (no IV needed)"""
    try:
        cipher = AES.new(key, AES.MODE_ECB)
        d1 = cipher.decrypt(ct1)
        d2 = AES.new(key, AES.MODE_ECB).decrypt(ct2)
        d3 = AES.new(key, AES.MODE_ECB).decrypt(ct3)
        d4 = AES.new(key, AES.MODE_ECB).decrypt(ct4)
        
        xor12 = bytes(a ^ b for a, b in zip(d1, d2))
        xor13 = bytes(a ^ b for a, b in zip(d1, d3))
        xor14 = bytes(a ^ b for a, b in zip(d1, d4))
        
        score = sum([
            xor12 == xor_target_12,
            xor13 == xor_target_13,
            xor14 == xor_target_14,
        ])
        
        if score >= 2:
            print(f"  ** LIKELY KEY ({score}/3): {name} = {key.hex()} **")
            # Extract IV: iv = d1 XOR P1
            iv = bytes(a ^ b for a, b in zip(d1, P1))
            print(f"     Derived IV: {iv.hex()}")
            return True
        return False
    except Exception as e:
        return False

print(f"\n=== Testing AES-128 keys (16 bytes) ===")
keys128 = [
    bytes.fromhex(so1+so2),
    bytes.fromhex(so2+so1),
    bytes.fromhex(appKey),
    bytes.fromhex(md5(so1)),
    bytes.fromhex(md5(so2)),
    bytes.fromhex(md5(so1+so2)),
    bytes.fromhex(md5(so2+so1)),
    bytes.fromhex(md5(appKey)),
    bytes.fromhex(md5(so1+appKey[:16])),
    bytes.fromhex(md5(appKey+so1)),
    bytes.fromhex(md5(so1+so2+appKey)),
    bytes.fromhex(sha256(so1))[:16],
    bytes.fromhex(sha256(so2))[:16],
    bytes.fromhex(sha256(so1+so2))[:16],
    gameAppKey[:16],
    bytes.fromhex(md5(gameAppKey)),
    bytes.fromhex(md5(so1)) + bytes.fromhex(md5(so2))[:0],  # skip
]

names128 = [
    'so1+so2_hex', 'so2+so1_hex', 'appKey_hex',
    'md5(so1)_hex', 'md5(so2)_hex', 'md5(so1+so2)_hex', 'md5(so2+so1)_hex',
    'md5(appKey)_hex', 'md5(so1+appKey[:16])_hex', 'md5(appKey+so1)_hex',
    'md5(so1+so2+appKey)_hex', 'sha256(so1)[:16]', 'sha256(so2)[:16]',
    'sha256(so1+so2)[:16]', 'gameAppKey[:16]', 'md5(gameAppKey)_hex', 'skip'
]

for key, name in zip(keys128, names128):
    if len(key) == 16:
        test_aes_key(key, name)

print(f"\n=== Testing AES-256 keys (32 bytes) ===")
keys256 = [
    (so1+so2).encode(),
    (so2+so1).encode(),
    appKey.encode(),
    bytes.fromhex(sha256(so1)),
    bytes.fromhex(sha256(so2)),
    bytes.fromhex(sha256(so1+so2)),
    bytes.fromhex(sha256(appKey)),
    gameAppKey + b'\x00'*(32-len(gameAppKey)) if len(gameAppKey) < 32 else gameAppKey[:32],
]

names256 = [
    'so12_str', 'so21_str', 'appKey_str',
    'sha256(so1)_hex', 'sha256(so2)_hex', 'sha256(so1+so2)_hex',
    'sha256(appKey)_hex', 'gameAppKey_padded'
]

for key, name in zip(keys256, names256):
    if len(key) == 32:
        test_aes_key(key, name)

print("DONE")
