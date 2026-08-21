from Crypto.Cipher import DES, DES3, AES
import base64, hashlib, hmac as hmac_lib

TESTS = [
    ('{"a":"1"}',             '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}',             '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('{}',                    'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"appid":"100002001"}', 'f65223b0f5c6b228c7060a05ce68a348'),
]

DAEMON_B64 = "4rB5GeN3NzcyJkePA4rGSxUAIGep4ecGHZi1S+ebb/n6jZ3o+ko34ZIqWtR1MbHOOnTh9nGViMgu5lqWx2r0QKSzi+UFWO+4WtPKYn5jRZdkpRDTcprXrMlvDj5/Y5eOe3AaG9qS/3O30m+YrLXd8oCNQrY2XnVgz0KNfPLXDf/8Uyo0CJ8CgSbC5MaTUg8imUrhiUqBm5eGjKNZPrVhr0lent/TjLSwyFk/f++qfe1pv2ctydVG/oVm4ZHHn2Xvqgtxm5KIvHkNPpSBZTvNZp61f59UQxbqAqaCy9M/pDi/p746gUUeX6LS+n38QAYqjoBg+YlZIyyxgWx1coNwKw=="
daemon_enc = base64.b64decode(DAEMON_B64)

k1 = bytes.fromhex('1e1434dd98fa2dd9')  # 8 bytes
k2 = bytes.fromhex('6c7d4e03f45a595f')  # 8 bytes
k3des = k1 + k2 + k1  # 24 bytes for 3DES
appKey = 'd252596f076c9213dce69cdb39d488ea'

def hmac_md5(key, data):
    k = key if isinstance(key, bytes) else key.encode()
    return hmac_lib.new(k, data.encode(), hashlib.md5).hexdigest()

def md5(b): return hashlib.md5(b if isinstance(b, bytes) else b.encode()).hexdigest()

def test_fn(fn, name):
    r = [fn(t[0]) == t[1] for t in TESTS]
    n = sum(r)
    if n >= 1: print(f'  ({n}/4): {name}')
    return n == 4

print(f"daemon length: {len(daemon_enc)} bytes")

print("\n--- DES ECB ---")
for key in [k1, k2]:
    try:
        dec = DES.new(key, DES.MODE_ECB).decrypt(daemon_enc)
        print(f"DES-ECB({key.hex()}) decrypted[:64]: {dec[:64].hex()}")
        try: print(f"  as text: {dec[:64].decode('latin-1')}")
        except: pass
        for i in range(0, min(len(dec)-16, 128), 8):
            chunk = dec[i:i+16]
            test_fn(lambda j, k=chunk: hmac_md5(k, j), f"HMAC-MD5(DES_ECB_{key.hex()[:4]}[{i}:{i+16}])")
    except Exception as e: print(f"err: {e}")

print("\n--- DES CBC ---")
for key in [k1, k2]:
    for iv in [k1, k2, b'\x00'*8, daemon_enc[:8]]:
        try:
            dec = DES.new(key, DES.MODE_CBC, iv=iv).decrypt(daemon_enc)
            for i in range(0, min(len(dec)-16, 64), 8):
                chunk = dec[i:i+16]
                test_fn(lambda j, k=chunk: hmac_md5(k, j), f"HMAC-MD5(DES_CBC({key.hex()[:4]},iv={iv.hex()[:4]})[{i}:{i+16}])")
        except Exception as e: print(f"err: {e}")

print("\n--- 3DES ECB ---")
try:
    dec = DES3.new(k3des, DES3.MODE_ECB).decrypt(daemon_enc)
    print(f"3DES-ECB decrypted[:64]: {dec[:64].hex()}")
    try: print(f"  as text: {dec[:64].decode('latin-1')}")
    except: pass
    for i in range(0, min(len(dec)-16, 128), 8):
        chunk = dec[i:i+16]
        test_fn(lambda j, k=chunk: hmac_md5(k, j), f"HMAC-MD5(3DES_ECB[{i}:{i+16}])")
    # Special: use full decrypted as HMAC key
    test_fn(lambda j, k=dec: hmac_md5(k, j), "HMAC-MD5(3DES_full)")
    test_fn(lambda j, k=dec: hmac_md5(bytes.fromhex(md5(dec)), j), "HMAC-MD5(md5(3DES_full))")
except Exception as e: print(f"3DES err: {e}")

print("\n--- 3DES CBC ---")
for iv in [k1, k2, b'\x00'*8, k1+k2]:
    if len(iv) != 8: continue
    try:
        dec = DES3.new(k3des, DES3.MODE_CBC, iv=iv).decrypt(daemon_enc)
        print(f"3DES-CBC(iv={iv.hex()}) decrypted[:32]: {dec[:32].hex()}")
        for i in range(0, min(len(dec)-16, 64), 8):
            chunk = dec[i:i+16]
            test_fn(lambda j, k=chunk: hmac_md5(k, j), f"HMAC-MD5(3DES_CBC_iv{iv.hex()[:4]}[{i}:{i+16}])")
    except Exception as e: print(f"3DES CBC err: {e}")

print("\n--- AES ---")
# appKey bytes = 16 bytes = AES-128 key
aes_key = bytes.fromhex(appKey)
for mode_name, mode, extra in [
    ('ECB', AES.MODE_ECB, {}),
    ('CBC', AES.MODE_CBC, {'iv': b'\x00'*16}),
    ('CBC', AES.MODE_CBC, {'iv': daemon_enc[:16]}),
]:
    try:
        if extra:
            dec = AES.new(aes_key, mode, **extra).decrypt(daemon_enc)
        else:
            dec = AES.new(aes_key, mode).decrypt(daemon_enc)
        print(f"AES-{mode_name} decrypted[:32]: {dec[:32].hex()}")
        for i in range(0, min(len(dec)-16, 64), 16):
            chunk = dec[i:i+16]
            test_fn(lambda j, k=chunk: hmac_md5(k, j), f"HMAC-MD5(AES-{mode_name}[{i}:{i+16}])")
    except Exception as e: print(f"AES err: {e}")

print("DONE")
