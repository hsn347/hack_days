from Crypto.Cipher import AES
import base64, hashlib, hmac as hmac_lib

# Known encrypt/decrypt pairs from Frida
# encryptPacketForUC(plaintext) = ciphertext_b64
KNOWN = [
    (b"",                    "BZHu/6d0e14wLnDIBIHUHw=="),  # 0 bytes → 1 block padded
    (b"test_input_123",      "C/l2KU6HSIgcRlRd2G9cYA=="),  # 14 bytes → 1 block
    (b"AAAAAAAAAAAAAAAA",    "KPn2WwOoVntkL9Z3T4lIItFPDRB0Vytek0zWjr01OiE="),  # 16 bytes → 2 blocks
    (b"BBBBBBBBBBBBBBBB",    "WH7jCasuGCdyVPwBzN4v6HxtlsZLqC9k09QGLcNPiD4="),  # 16 bytes → 2 blocks
]

def pkcs7_pad(data, bs=16):
    pad = bs - (len(data) % bs)
    return data + bytes([pad] * pad)

def aes_ecb_encrypt(key, data):
    return AES.new(key, AES.MODE_ECB).encrypt(pkcs7_pad(data))

def aes_cbc_encrypt(key, iv, data):
    return AES.new(key, AES.MODE_CBC, iv=iv).encrypt(pkcs7_pad(data))

def test_key_ecb(key, name):
    try:
        ok = all(aes_ecb_encrypt(key, pt) == base64.b64decode(ct) for pt, ct in KNOWN)
        if ok:
            print(f"  *** AES-ECB MATCH: {name} = {key.hex()} ***")
        return ok
    except Exception as e:
        return False

def test_key_cbc(key, iv, name):
    try:
        ok = all(aes_cbc_encrypt(key, iv, pt) == base64.b64decode(ct) for pt, ct in KNOWN)
        if ok:
            print(f"  *** AES-CBC(iv={iv.hex()}) MATCH: {name} = {key.hex()} ***")
        return ok
    except:
        return False

so1 = '1e1434dd98fa2dd9'
so2 = '6c7d4e03f45a595f'
appKey = 'd252596f076c9213dce69cdb39d488ea'
gameAppKey = b'+|p\x7favx#}cy-|\x7fe|*&(bv-!/gv*qul*/'

def md5(s): return hashlib.md5(s if isinstance(s, bytes) else s.encode()).hexdigest()

keys_128 = [
    ('so1+so2 hex bytes', bytes.fromhex(so1+so2)),
    ('so2+so1 hex bytes', bytes.fromhex(so2+so1)),
    ('appKey hex bytes', bytes.fromhex(appKey)),
    ('md5(so1) hex', bytes.fromhex(md5(so1))),
    ('md5(so2) hex', bytes.fromhex(md5(so2))),
    ('md5(so1+so2) hex', bytes.fromhex(md5(so1+so2))),
    ('md5(appKey) hex', bytes.fromhex(md5(appKey))),
    ('md5(appKey+so1) hex', bytes.fromhex(md5(appKey+so1))),
    ('md5(so1+appKey) hex', bytes.fromhex(md5(so1+appKey))),
    ('gameAppKey[:16]', gameAppKey[:16]),
]

keys_256 = [
    ('so1+so2 ascii', (so1+so2).encode()),
    ('so2+so1 ascii', (so2+so1).encode()),
    ('appKey ascii', appKey.encode()),
    ('gameAppKey padded', gameAppKey + b'\x00'*(32-len(gameAppKey)) if len(gameAppKey) < 32 else gameAppKey[:32]),
]

# Print known first block ciphertexts for analysis
print("=== Known ciphertexts (first block) ===")
for pt, ct_b64 in KNOWN:
    ct = base64.b64decode(ct_b64)
    pt_padded = pkcs7_pad(pt)
    print(f"  pt={pt_padded.hex()} -> ct[:16]={ct[:16].hex()}")

print("\n=== Testing AES-128-ECB ===")
for name, key in keys_128:
    test_key_ecb(key, f'AES-128-ECB({name})')

print("\n=== Testing AES-256-ECB ===")
for name, key in keys_256:
    test_key_ecb(key, f'AES-256-ECB({name})')

print("\n=== Testing AES-128-CBC (various IVs) ===")
ivs = [b'\x00'*16, bytes.fromhex(so1+so1), bytes.fromhex(so2+so2)]
for name, key in keys_128:
    for iv in ivs:
        test_key_cbc(key, iv, f'AES-128-CBC({name})')

print("\n=== Brute force IVs for single-block known plaintext ===")
# For 0-byte input: AES_CBC(key, iv, \x10*16) = BZHu/6d0e14wLnDIBIHUHw==
# AES_ECB(key, \x10*16 XOR iv) = BZHu/6d0e14wLnDIBIHUHw==
# For single block: AES-ECB with modified plaintext (\x10*16 XOR iv)
ct0 = base64.b64decode("BZHu/6d0e14wLnDIBIHUHw==")
ct_test = base64.b64decode("C/l2KU6HSIgcRlRd2G9cYA==")
ct_AAA_b1 = base64.b64decode("KPn2WwOoVntkL9Z3T4lIItFPDRB0Vytek0zWjr01OiE=")[:16]
ct_BBB_b1 = base64.b64decode("WH7jCasuGCdyVPwBzN4v6HxtlsZLqC9k09QGLcNPiD4=")[:16]

print(f"ct_empty[:16]: {ct0.hex()}")
print(f"ct_test[:16]: {ct_test.hex()}")
print(f"ct_AAA_b1: {ct_AAA_b1.hex()}")
print(f"ct_BBB_b1: {ct_BBB_b1.hex()}")

# For ECB, both blocks of "AAAAAAAAAAAAAAAA" should be:
# block1 = AES(key, "AAAAAAAAAAAAAAAA") 
# block2 = AES(key, \x10*16) = same as ct_empty!
ct_AAA = base64.b64decode("KPn2WwOoVntkL9Z3T4lIItFPDRB0Vytek0zWjr01OiE=")
print(f"\nIf ECB mode:")
print(f"  block2 of AAA = {ct_AAA[16:].hex()}")
print(f"  ct_empty      = {ct0.hex()}")
print(f"  Match: {ct_AAA[16:] == ct0}")

print("\nDONE")
