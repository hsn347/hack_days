import hashlib, re, hmac as hmac_lib

# isUC=TRUE test cases (confirmed - same across sessions = FIXED KEY!)
TESTS_T = [
    ('',                    '292acee0423c18171018f4cee8435606'),
    ('a',                   'e8fe77a5f1a269da23330f658ef55889'),
    ('{}',                  'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"a":"1"}',           '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}',           '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('{"abc":"xyz"}',       '04ff96a12ff3537a827245cfa005f6e3'),
    ('hello world',         '33a3b048e9a0351d341935ad4e133a32'),
    ('1234567890',          '3921450ff47fa5a4b86d301abed28f51'),
    ('aaaaaaaaaaaaaaaa',    'e3700fe853c28bfc0249c12777ad40c8'),
]

# isUC=FALSE (confirmed formula: md5(input + appKey))
appKey = 'd252596f076c9213dce69cdb39d488ea'

def md5b(b): return hashlib.md5(b).hexdigest()
def md5s(s): return hashlib.md5(s.encode()).hexdigest()
def hmac_md5(key, data):
    k = key if isinstance(key, bytes) else key.encode()
    d = data.encode() if isinstance(data, str) else data
    return hmac_lib.new(k, d, hashlib.md5).hexdigest()

def test_formula(fn, name, min_match=3):
    results = [fn(t[0]) == t[1] for t in TESTS_T]
    n = sum(results)
    if n >= min_match:
        print(f'  *** ({n}/{len(TESTS_T)}): {name} ***')
        if n == len(TESTS_T): print('  *** FULL MATCH! ***')
    return n == len(TESTS_T)

print("=== Verifying isUC=false formula ===")
TESTS_F = [
    ('', '55e72818a7b7dfcf873e53f7dc560b29'),
    ('a', '043ca6675533d2993210bdfc559a1aab'),
    ('{}', '1dbfda593cb025f83d9620efaf8b3fb8'),
]
ok = all(md5b((t[0]+appKey).encode()) == t[1] for t in TESTS_F)
print(f"isUC=false formula md5(input+appKey): {'CONFIRMED' if ok else 'FAILED'}")

print("\n=== Testing isUC=true with key from binary ===")

# Read binary and extract ALL printable strings
with open(r'E:\osmanli\libdaemonutil.so', 'rb') as f:
    data = f.read()

strings = set()
for m in re.finditer(rb'[\x20-\x7e]{8,}', data):
    s = m.group().decode('ascii', errors='replace')
    # Test all substrings that could be keys
    strings.add(s)
    for n in [8, 16, 20, 32, 40, 64]:
        if len(s) >= n:
            strings.add(s[:n])

print(f"Testing {len(strings)} string candidates from binary...")

found = False
for key in strings:
    # Formula: md5(input + key)
    if test_formula(lambda j, k=key: md5b((j+k).encode()), f'md5(input+"{key[:30]}")'):
        print(f"FULL KEY: {key!r}")
        found = True
    # Formula: md5(key + input)
    if test_formula(lambda j, k=key: md5b((k+j).encode()), f'md5("{key[:30]}"+input)'):
        print(f"FULL KEY: {key!r}")
        found = True
    # HMAC
    if test_formula(lambda j, k=key: hmac_md5(k, j), f'HMAC-MD5("{key[:20]}",input)'):
        print(f"FULL KEY: {key!r}")
        found = True

if not found:
    print("Not found in binary strings. Trying derived keys...")
    
    # Try: key_uc = md5(appKey + X) or md5(X + appKey) for X in binary strings
    base_keys = [appKey, '1e1434dd98fa2dd9', '6c7d4e03f45a595f']
    for bk in base_keys[:5]:
        for s in list(strings)[:100]:
            k = md5s(bk + s)
            if test_formula(lambda j, key=k: md5b((j+key).encode()), f'md5(input+md5("{bk[:8]}"+"{s[:8]}"))', min_match=4):
                found = True

print("DONE" + (" - ALGORITHM FOUND!" if found else " - Key not in binary strings"))
