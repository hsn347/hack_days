"""
crack_httpsign_final.py
تحليل شامل لإيجاد خوارزمية httpSign(isUC=true)
لدينا 4 اختبارات معروفة:
  {"a":"1"}             → 171980e57ef983a1b1df64bf9ec1163b
  {"b":"2"}             → 450bb7b5ee9dd99bb2e09d0775a6ea73
  {}                    → d01ac4e2ad28d6503a38ec9f779bf424
  {"appid":"100002001"} → f65223b0f5c6b228c7060a05ce68a348
"""
import hashlib, hmac as hmac_lib, itertools

# Known test cases
TESTS = [
    ('{"a":"1"}',             '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}',             '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('{}',                    'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"appid":"100002001"}', 'f65223b0f5c6b228c7060a05ce68a348'),
]

appKey = 'd252596f076c9213dce69cdb39d488ea'
gameAppKey = '+|p\x7favx#}cy-|\x7fe|*&(bv-!/gv*qul*/'

# Strings found in libdaemonutil.so
so_str1 = '1e1434dd98fa2dd9'
so_str2 = '6c7d4e03f45a595f'
so_str3 = '69A2'
so_str4 = '5D8A'
so_str5 = 'yptn'

def md5(s): return hashlib.md5(s if isinstance(s, bytes) else s.encode()).hexdigest()
def sha1(s): return hashlib.sha1(s if isinstance(s, bytes) else s.encode()).hexdigest()
def sha256(s): return hashlib.sha256(s if isinstance(s, bytes) else s.encode()).hexdigest()

def hmac_md5(key, data):
    k = key if isinstance(key, bytes) else key.encode()
    d = data if isinstance(data, bytes) else data.encode()
    return hmac_lib.new(k, d, hashlib.md5).hexdigest()

def hmac_sha1(key, data):
    k = key if isinstance(key, bytes) else key.encode()
    d = data if isinstance(data, bytes) else data.encode()
    return hmac_lib.new(k, d, hashlib.sha1).hexdigest()[:32]

def check(fn, name, all_tests=False):
    """اختبر دالة على أول test case أو الكل"""
    tests = TESTS if all_tests else TESTS[:1]
    results = [fn(t[0]) == t[1] for t in tests]
    if all(results):
        print(f"✅ MATCH ALL: {name}")
        return True
    elif results[0]:
        # تحقق من الباقي
        full = all(fn(t[0]) == t[1] for t in TESTS)
        if full:
            print(f"✅ MATCH ALL: {name}")
        else:
            print(f"⚠️  PARTIAL ({sum(r for r in [fn(t[0])==t[1] for t in TESTS])}/{len(TESTS)}): {name}")
        return full
    return False

print("=== جمع المفاتيح المحتملة ===")
keys_str = [
    appKey,
    gameAppKey,
    so_str1,
    so_str2,
    so_str1 + so_str2,
    so_str2 + so_str1,
    so_str3,
    so_str4,
    so_str5,
    md5(appKey),
    md5(so_str1),
    md5(so_str1 + so_str2),
    md5(appKey + so_str1),
    md5(so_str1 + appKey),
    sha1(so_str1)[:32],
    so_str1 + so_str2 + appKey,
]

keys_bytes = [
    bytes.fromhex(appKey),
    bytes.fromhex(so_str1),
    bytes.fromhex(so_str2),
    bytes.fromhex(so_str1 + so_str2),
    bytes.fromhex(so_str2 + so_str1),
    bytes.fromhex(md5(so_str1)),
    bytes.fromhex(md5(so_str1 + so_str2)),
    bytes.fromhex(sha1(so_str1))[:16],
    bytes.fromhex(sha256(so_str1))[:16],
    bytes.fromhex(md5(appKey + so_str1)),
    bytes.fromhex(md5(so_str1 + appKey)),
]

print(f"Keys to test: {len(keys_str)} str + {len(keys_bytes)} bytes")

print("\n=== HMAC-MD5 ===")
found = False
for key in keys_str:
    name = f"HMAC-MD5(str '{key[:20]}...' if len>20 else key, json)"
    if check(lambda j, k=key: hmac_md5(k, j), name):
        found = True

for key in keys_bytes:
    name = f"HMAC-MD5(bytes {key.hex()[:20]}..., json)"
    if check(lambda j, k=key: hmac_md5(k, j), name):
        found = True

print("\n=== HMAC-SHA1[:32] ===")
for key in keys_str + keys_bytes:
    name = f"HMAC-SHA1({key[:20] if isinstance(key, str) else key.hex()[:20]}, json)"
    k = key if isinstance(key, bytes) else key.encode()
    if check(lambda j, k=k: hmac_lib.new(k, j.encode(), hashlib.sha1).hexdigest()[:32], name):
        found = True

print("\n=== MD5 combinations ===")
prefixes = ['', appKey, so_str1, so_str2, so_str1+so_str2, gameAppKey]
suffixes = ['', appKey, so_str1, so_str2, so_str1+so_str2, gameAppKey]
for pre in prefixes:
    for suf in suffixes:
        if pre == '' and suf == '': continue
        val = check(lambda j, p=pre, s=suf: md5(p + j + s), f"md5('{pre[:10]}'+json+'{suf[:10]}')")
        if val: found = True

print("\n=== XOR-MD5 ===")
# Maybe the key is appKey XOR something
def xor_bytes(a, b):
    return bytes(x ^ y for x, y in zip(a, b))

appKey_bytes = bytes.fromhex(appKey)
for key in keys_bytes:
    if len(key) == len(appKey_bytes):
        xored = xor_bytes(appKey_bytes, key)
        if check(lambda j, k=xored: hmac_md5(k, j), f"HMAC-MD5(appKey XOR {key.hex()[:16]}, json)"):
            found = True
        if check(lambda j, k=xored: md5(k.hex() + j), f"md5(xored_hex+json)"):
            found = True

print("\n=== Double MD5 / MD5 of MD5 ===")
for key in [appKey, so_str1, so_str1+so_str2]:
    # md5(md5(key) + json)
    k2 = md5(key)
    if check(lambda j, k=k2: md5(k + j), f"md5(md5('{key[:16]}')+json)"):
        found = True
    # md5(json + md5(key))
    if check(lambda j, k=k2: md5(j + k), f"md5(json+md5('{key[:16]}'))"):
        found = True

print("\n=== Binary key extraction from libdaemonutil.so ===")
try:
    with open(r'E:\osmanli\libdaemonutil.so', 'rb') as f:
        data = f.read()
    
    # Find the 2 hex strings and extract surrounding bytes as key material
    idx1 = data.find(b'1e1434dd98fa2dd9')
    idx2 = data.find(b'6c7d4e03f45a595f')
    
    if idx1 >= 0 and idx2 >= 0:
        # Extract 32 bytes after each string
        region1 = data[idx1:idx1+64]
        region2 = data[idx2:idx2+64]
        
        # Try these bytes directly as keys
        for offset in range(0, 32, 4):
            key = region1[offset:offset+16]
            if len(key) == 16:
                if check(lambda j, k=key: hmac_md5(k, j), f"HMAC-MD5(so_region1[{offset}:{offset+16}], json)"):
                    found = True
        
        # Search for any 16-byte pattern near the strings
        for i in range(max(0,idx1-100), min(len(data), idx1+200)):
            chunk = data[i:i+16]
            if all(32 <= b <= 126 for b in chunk):  # printable
                key_str = chunk.decode('ascii', errors='replace')
                if check(lambda j, k=key_str: hmac_md5(k, j), f"HMAC-MD5(printable@{i}, json)"):
                    print(f"  KEY: {key_str!r}")
                    found = True
    print("Binary analysis done")
except Exception as e:
    print(f"Binary analysis error: {e}")

if not found:
    print("\n❌ لم يُعثر على الخوارزمية بالطرق التقليدية.")
    print("  → الخوارزمية على الأرجح تستخدم مفتاحاً من UC Server (cachedDaemonResult)")
    print("  → الحل: اعتراض طلب login الحقيقي عبر proxy")
