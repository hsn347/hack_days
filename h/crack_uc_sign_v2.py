"""
crack_uc_sign_v2.py
يستخدم test cases بسيطة (input=JSON string) لكسر خوارزمية isUC=true
"""
import hashlib, hmac as hmac_lib, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def md5(s):
    if isinstance(s, str): s = s.encode('utf-8')
    return hashlib.md5(s).hexdigest()

def sha1(s):
    if isinstance(s, str): s = s.encode('utf-8')
    return hashlib.sha1(s).hexdigest()

def hmac_md5(key, data):
    if isinstance(key, str): key = key.encode('utf-8')
    if isinstance(data, str): data = data.encode('utf-8')
    return hmac_lib.new(key, data, hashlib.md5).hexdigest()

def hmac_sha1(key, data):
    if isinstance(key, str): key = key.encode('utf-8')
    if isinstance(data, str): data = data.encode('utf-8')
    return hmac_lib.new(key, data, hashlib.sha1).hexdigest()[:32]

# === Test cases: httpSign(json_string, true) ===
# مأخوذة من get_more_test_cases.js
TRUE_CASES = [
    ('{}',                              'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"a":"1"}',                       '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}',                       '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('{"abc":"xyz"}',                   '04ff96a12ff3537a827245cfa005f6e3'),
    ('{"appid":"100002001"}',           'f65223b0f5c6b228c7060a05ce68a348'),
    ('{"timestamp":"1000000"}',         '4b1b793aefa0a710fe4851d041b4abe1'),
    ('{"timestamp":"1000001"}',         'dbb012ea56b5290cbafe78638855c623'),
    ('{"sessionid":""}',               '6b642210863affdc474a4cd5f3e3d44c'),
]

# === قائمة المفاتيح المحتملة ===
KEYS = {
    'appKey':   'd252596f076c9213dce69cdb39d488ea',
    'cert0':    '47965e93ad48a1d34f9ef116405aa6cf',
    'cert1':    '9dd7d6cd5e70b9f0b21ea50e41a8d2f1',
    'deviceid': 'b511d1c73fdc4a441ff92258e301559b',
    'uid1':     '1017d92537872288e8ddbca99fffcc90',  # azjfhf48
    'uid2':     '8120e389ed552b4774dd5d8ed0c26e01',  # burcudemr
    'uuid':     '6247168637C043438A630EB829162B17',  # sdid without dashes (uppercase)
    'uuid_l':   '6247168637c043438a630eb829162b17',  # lowercase
    'sdid':     '62471686-37C0-4343-BA63-0EB829162B17',
    'MD5':      'MD5',
    'empty':    '',
}

def test_all(json_input, expected_sign, tests_fn):
    """اختبر صيغة على جميع test cases"""
    results = [tests_fn(j) == s for j, s in TRUE_CASES]
    if all(results):
        print(f"*** FULL MATCH: {tests_fn.__doc__} ***")
        return True
    return False

def check(fn_name, fn):
    """اختبر fn على كل test cases"""
    results = [fn(j) == s for j, s in TRUE_CASES]
    matches = sum(results)
    if matches == len(TRUE_CASES):
        print(f"!!! FULL MATCH: {fn_name}")
        return True
    elif matches >= 2:
        print(f"  partial {matches}/{len(TRUE_CASES)}: {fn_name}")
    return False

print("Testing all formulas against", len(TRUE_CASES), "test cases...\n")

found = False

# --- md5 variants ---
for k_name, k_val in KEYS.items():
    found |= check(f"md5(json+{k_name})",   lambda j, k=k_val: md5(j + k))
    found |= check(f"md5({k_name}+json)",   lambda j, k=k_val: md5(k + j))
    found |= check(f"md5(json+md5({k_name}))", lambda j, k=k_val: md5(j + md5(k)))
    found |= check(f"md5(md5({k_name})+json)", lambda j, k=k_val: md5(md5(k) + j))
    found |= check(f"hmac_md5({k_name},json)", lambda j, k=k_val: hmac_md5(k, j))
    found |= check(f"hmac_md5(json,{k_name})", lambda j, k=k_val: hmac_md5(j, k))

# --- Two-key combinations ---
key_pairs = [
    ('appKey', KEYS['appKey']),
    ('cert0', KEYS['cert0']),
    ('cert1', KEYS['cert1']),
    ('deviceid', KEYS['deviceid']),
]
for (n1, k1), (n2, k2) in [(a, b) for a in key_pairs for b in key_pairs if a != b]:
    xor_k = bytes(a^b for a, b in zip(bytes.fromhex(k1[:32]), bytes.fromhex(k2[:32]))).hex()
    found |= check(f"md5(json+{n1}+{n2})", lambda j, k=k1+k2: md5(j + k))
    found |= check(f"md5(json+xor({n1},{n2}))", lambda j, k=xor_k: md5(j + k))

# --- SHA variants ---
for k_name, k_val in KEYS.items():
    r = check(f"sha1[:32](json+{k_name})", lambda j, k=k_val: sha1(j + k)[:32])
    found |= r

# --- Special: maybe uses URL-encoded json? ---
import urllib.parse
found |= check("md5(url(json)+appKey)", lambda j: md5(urllib.parse.quote(j) + KEYS['appKey']))
found |= check("md5(json+appKey+deviceid)", lambda j: md5(j + KEYS['appKey'] + KEYS['deviceid']))
found |= check("md5(json+deviceid+appKey)", lambda j: md5(j + KEYS['deviceid'] + KEYS['appKey']))

# --- Maybe the key is derived from appKey by modification ---
# appKey hex → bytes → reversed → hex
appkey_bytes = bytes.fromhex(KEYS['appKey'])
rev_key = appkey_bytes[::-1].hex()
found |= check("md5(json+appKey_reversed)", lambda j, k=rev_key: md5(j + k))

# XOR appKey with cert0
xk = bytes(a^b for a,b in zip(bytes.fromhex(KEYS['appKey']), bytes.fromhex(KEYS['cert0']))).hex()
found |= check("md5(json+appKey_xor_cert0)", lambda j, k=xk: md5(j + k))

# md5 of appKey
appkey_md5 = md5(KEYS['appKey'])
found |= check("md5(json+md5(appKey))", lambda j, k=appkey_md5: md5(j + k))

# md5 of cert0 + appKey
found |= check("md5(json+md5(cert0+appKey))", lambda j: md5(j + md5(KEYS['cert0'] + KEYS['appKey'])))

# --- Maybe it's a completely different format ---
# Values only (not JSON)
def vals_sorted(j_str):
    """values joined sorted"""
    try:
        d = json.loads(j_str)
        return ''.join(str(v) for k, v in sorted(d.items()))
    except: return j_str

found |= check("md5(values+appKey)", lambda j: md5(vals_sorted(j) + KEYS['appKey']))
found |= check("md5(values+cert0)", lambda j: md5(vals_sorted(j) + KEYS['cert0']))

if not found:
    print("\nNo match found.\n")
    print("Hypothesis: the key might be device-specific (computed from daemon/hardware ID)")
    print("\nComputed false signs for comparison (isUC=false):")
    for j, s in TRUE_CASES[:3]:
        false_s = md5(j + KEYS['appKey'])
        print(f"  FALSE: {j} -> {false_s}")
        print(f"  TRUE:  {j} -> {s}")
        print()
