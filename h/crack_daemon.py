import hashlib, hmac as hmac_lib, base64, struct

# Known test cases
TESTS = [
    ('{"a":"1"}',             '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}',             '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('{}',                    'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"appid":"100002001"}', 'f65223b0f5c6b228c7060a05ce68a348'),
]

# cachedDaemonResult captured via Frida
DAEMON_B64 = "4rB5GeN3NzcyJkePA4rGSxUAIGep4ecGHZi1S+ebb/n6jZ3o+ko34ZIqWtR1MbHOOnTh9nGViMgu5lqWx2r0QKSzi+UFWO+4WtPKYn5jRZdkpRDTcprXrMlvDj5/Y5eOe3AaG9qS/3O30m+YrLXd8oCNQrY2XnVgz0KNfPLXDf/8Uyo0CJ8CgSbC5MaTUg8imUrhiUqBm5eGjKNZPrVhr0lent/TjLSwyFk/f++qfe1pv2ctydVG/oVm4ZHHn2Xvqgtxm5KIvHkNPpSBZTvNZp61f59UQxbqAqaCy9M/pDi/p746gUUeX6LS+n38QAYqjoBg+YlZIyyxgWx1coNwKw=="
daemon_bytes = base64.b64decode(DAEMON_B64)

appKey = 'd252596f076c9213dce69cdb39d488ea'

def md5(s): return hashlib.md5(s if isinstance(s, bytes) else s.encode()).hexdigest()
def hmac_md5(key, data):
    k = key if isinstance(key, bytes) else key.encode()
    d = data.encode() if isinstance(data, str) else data
    return hmac_lib.new(k, d, hashlib.md5).hexdigest()

def test_all(fn, name):
    r = [fn(t[0]) == t[1] for t in TESTS]
    n = sum(r)
    if n >= 1:
        print(f'  ({n}/4): {name}')
    return n == 4

print(f"daemon_bytes length: {len(daemon_bytes)}")
print(f"daemon_bytes hex[:32]: {daemon_bytes[:32].hex()}")

print("\n=== HMAC-MD5 with daemon chunks ===")
# Try every 16-byte chunk of daemon as key
for i in range(0, len(daemon_bytes)-16, 8):
    key = daemon_bytes[i:i+16]
    if test_all(lambda j, k=key: hmac_md5(k, j), f"HMAC-MD5(daemon[{i}:{i+16}], json)"):
        print(f"  KEY HEX: {key.hex()}")

# Try every 32-byte chunk
for i in range(0, len(daemon_bytes)-32, 16):
    key = daemon_bytes[i:i+32]
    if test_all(lambda j, k=key: hmac_md5(k, j), f"HMAC-MD5(daemon[{i}:{i+32}], json)"):
        print(f"  KEY HEX: {key.hex()}")

print("\n=== MD5 combinations with daemon chunks ===")
for i in range(0, len(daemon_bytes)-16, 16):
    chunk = daemon_bytes[i:i+16]
    chunk_hex = chunk.hex()
    if test_all(lambda j, c=chunk_hex: md5(c + j), f"md5(daemon_hex[{i}]+json)"):
        print("FOUND!")
    if test_all(lambda j, c=chunk_hex: md5(j + c), f"md5(json+daemon_hex[{i}])"):
        print("FOUND!")

print("\n=== HMAC-MD5 with md5(daemon chunks) ===")
for i in range(0, len(daemon_bytes)-16, 16):
    chunk = daemon_bytes[i:i+16]
    key = bytes.fromhex(md5(chunk))  # md5(chunk) as 16-byte key
    if test_all(lambda j, k=key: hmac_md5(k, j), f"HMAC-MD5(md5(daemon[{i}:{i+16}]), json)"):
        print(f"  KEY: {key.hex()}")

print("\n=== XOR daemon with appKey ===")
appkey_bytes = bytes.fromhex(appKey)
for i in range(0, len(daemon_bytes)-16, 16):
    chunk = daemon_bytes[i:i+16]
    xored = bytes(a ^ b for a, b in zip(chunk, appkey_bytes))
    if test_all(lambda j, k=xored: hmac_md5(k, j), f"HMAC-MD5(daemon[{i}] XOR appKey, json)"):
        print(f"  KEY: {xored.hex()}")

print("\n=== HMAC-MD5 full daemon ===")
for fn_name, fn in [
    ("full", lambda: daemon_bytes),
    ("md5(full)", lambda: bytes.fromhex(md5(daemon_bytes))),
    ("first16", lambda: daemon_bytes[:16]),
    ("last16", lambda: daemon_bytes[-16:]),
    ("mid16", lambda: daemon_bytes[len(daemon_bytes)//2-8:len(daemon_bytes)//2+8]),
]:
    key = fn()
    if test_all(lambda j, k=key: hmac_md5(k, j), f"HMAC-MD5({fn_name}, json)"):
        print("FOUND!")

print("\n=== md5 daemon full ===")
d_hex = daemon_bytes.hex()
d_b64 = DAEMON_B64
for pre, suf, name in [
    (d_hex[:32], '', 'daemon_hex[:32]+json'),
    ('', d_hex[:32], 'json+daemon_hex[:32]'),
    (md5(daemon_bytes), '', 'md5(daemon)+json'),
    ('', md5(daemon_bytes), 'json+md5(daemon)'),
    (md5(daemon_bytes[:16]), '', 'md5(daemon[:16])+json'),
]:
    if test_all(lambda j, p=pre, s=suf: md5(p + j + s), name):
        print(f"FOUND: {name}")

print("DONE")
