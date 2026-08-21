import hashlib, hmac as hmac_lib, sys

TESTS = [
    ('{"a":"1"}',             '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}',             '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('{}',                    'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"appid":"100002001"}', 'f65223b0f5c6b228c7060a05ce68a348'),
]
appKey = 'd252596f076c9213dce69cdb39d488ea'
gameAppKey = '+|p\x7favx#}cy-|\x7fe|*&(bv-!/gv*qul*/'
so1 = '1e1434dd98fa2dd9'
so2 = '6c7d4e03f45a595f'

def hmac_md5(key, data):
    k = key if isinstance(key, bytes) else key.encode()
    d = data.encode() if isinstance(data, str) else data
    return hmac_lib.new(k, d, hashlib.md5).hexdigest()

def hmac_sha1(key, data):
    k = key if isinstance(key, bytes) else key.encode()
    d = data.encode() if isinstance(data, str) else data
    return hmac_lib.new(k, d, hashlib.sha1).hexdigest()

def md5(s):
    b = s.encode() if isinstance(s, str) else s
    return hashlib.md5(b).hexdigest()

def test_all(fn, name):
    results = [fn(t[0]) for t in TESTS]
    matches = sum(r == t[1] for r, t in zip(results, TESTS))
    if matches >= 1:
        print(f'  ({matches}/4): {name}')
        if matches == 4:
            print(f'  *** FULL MATCH! ***')
    return matches == 4

keys = [
    ('appKey', appKey),
    ('appKey_hex', bytes.fromhex(appKey)),
    ('gameAppKey', gameAppKey),
    ('so1', so1),
    ('so1_hex', bytes.fromhex(so1)),
    ('so2', so2),
    ('so2_hex', bytes.fromhex(so2)),
    ('so12', so1+so2),
    ('so12_hex', bytes.fromhex(so1+so2)),
    ('md5so1', md5(so1)),
    ('md5so1_hex', bytes.fromhex(md5(so1))),
    ('md5appKey', md5(appKey)),
    ('md5appKey_hex', bytes.fromhex(md5(appKey))),
    ('md5appKey+so1', md5(appKey+so1)),
    ('md5appKey+so1_hex', bytes.fromhex(md5(appKey+so1))),
    ('md5so12', md5(so1+so2)),
    ('md5so12_hex', bytes.fromhex(md5(so1+so2))),
]

print('=== HMAC-MD5 ===')
for kname, key in keys:
    test_all(lambda j, k=key: hmac_md5(k, j), f'HMAC-MD5({kname}, json)')

print('=== HMAC-SHA1[:32] ===')
for kname, key in keys:
    test_all(lambda j, k=key: hmac_sha1(k, j)[:32], f'HMAC-SHA1[:32]({kname}, json)')

print('=== md5 combos ===')
atoms = ['', appKey, so1, so2, so1+so2, gameAppKey, md5(so1), md5(so1+so2)]
for pre in atoms:
    for suf in atoms:
        if not pre and not suf: continue
        test_all(lambda j, p=pre, s=suf: md5(p+j+s), f'md5({pre[:8]!r}+json+{suf[:8]!r})')

print('=== binary key scan ===')
try:
    with open(r'E:\osmanli\libdaemonutil.so', 'rb') as f:
        data = f.read()
    
    # Scan for 16-byte printable strings as potential keys
    found_keys = set()
    for i in range(0, len(data)-16, 4):
        chunk = data[i:i+16]
        try:
            s = chunk.decode('ascii')
            if s.isprintable() and len(s.strip()) == 16:
                found_keys.add(s)
        except:
            pass
    
    print(f'Found {len(found_keys)} printable 16-char keys to test')
    for key in list(found_keys)[:200]:
        test_all(lambda j, k=key: hmac_md5(k, j), f'HMAC-MD5("{key[:16]}", json)')
        test_all(lambda j, p=key: md5(p+j+appKey), f'md5("{key[:8]}"+json+appKey)')
        test_all(lambda j, s=key: md5(j+s), f'md5(json+"{key[:16]}")')
except Exception as e:
    print(f'Binary error: {e}')

print('DONE')
