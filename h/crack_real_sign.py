"""
crack_real_sign.py
عندنا الآن test cases حقيقية لـ isUC=true!
"""
import hashlib, json, hmac as hmac_lib, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def md5(s): 
    if isinstance(s, str): s = s.encode()
    return hashlib.md5(s).hexdigest()

def hmac_md5(key, data):
    if isinstance(key, str): key = key.encode()
    if isinstance(data, str): data = data.encode()
    return hmac_lib.new(key, data, hashlib.md5).hexdigest()

APP_KEY  = "d252596f076c9213dce69cdb39d488ea"
CERT_MD5 = "47965e93ad48a1d34f9ef116405aa6cf"

# Test case 1 (بعد إزالة sign field)
CASE1_MAP = {
    "clientversion": "5.33.0",
    "packagename": "and.onemt.boe.tr",
    "channel": "googleplay",
    "sessionid": "BGywHJMjOoQhCzDhDjFi0qEaCDr8aJ602vsYfjG4Do4DMeS35icLr+G+51thn55ynKwMrbf1SiEifL3UxLXv0w==",
    "securemode": "MD5",
    "deviceid": "b511d1c73fdc4a441ff92258e301559b",
    "platform": "android",
    "reqdata": "%7B%22paylevel%22%3A%221%22%2C%22userid%22%3A%221017d92537872288e8ddbca99fffcc90%22%7D",
    "rstatus": "0",
    "appid": "100002001",
    "sdid": "62471686-37C0-4343-BA63-0EB829162B17",
    "originalid": "62471686-37C0-4343-BA63-0EB829162B17",
    "lang": "ar",
    "timestamp": "1786987644"
}
CASE1_SIGN = "678d1870a4b54a2f53c053a4c937661c"

# Test case 2
CASE2_MAP = {
    "clientversion": "5.33.0",
    "packagename": "and.onemt.boe.tr",
    "channel": "googleplay",
    "sessionid": "BGywHJMjOoQhCzDhDjFi0qEaCDr8aJ602vsYfjG4Do4DMeS35icLr+G+51thn55ynKwMrbf1SiEifL3UxLXv0w==",
    "securemode": "MD5",
    "deviceid": "b511d1c73fdc4a441ff92258e301559b",
    "platform": "android",
    "reqdata": "%7B%22userid%22%3A%221017d92537872288e8ddbca99fffcc90%22%7D",
    "rstatus": "0",
    "appid": "100002001",
    "sdid": "62471686-37C0-4343-BA63-0EB829162B17",
    "originalid": "62471686-37C0-4343-BA63-0EB829162B17",
    "lang": "ar",
    "timestamp": "1786987722"
}
CASE2_SIGN = "c41f2e6de6c9d0faaf63ea78041843a8"

CASES = [(CASE1_MAP, CASE1_SIGN), (CASE2_MAP, CASE2_SIGN)]

def test_formula(fn, name):
    results = [fn(m) == s for m, s in CASES]
    if all(results):
        print(f"*** MATCH ALL: {name} ***")
        return True
    elif any(results):
        print(f"  (partial {sum(results)}/2): {name}")
    return False

def sorted_json(m):
    return json.dumps(m, separators=(',', ':'), sort_keys=True)

def sorted_json_no_sep(m):
    return json.dumps(m, sort_keys=True)

j1 = sorted_json(CASE1_MAP)
j2 = sorted_json(CASE2_MAP)
print(f"JSON1: {j1[:80]}...")
print(f"JSON2: {j2[:80]}...")

print("\n=== Testing formulas ===")

# isUC=false formula (للمقارنة)
test_formula(lambda m: md5(sorted_json(m) + APP_KEY), "md5(json+appKey) [isUC=false]")

# Different keys
test_formula(lambda m: md5(sorted_json(m) + CERT_MD5), "md5(json+cert_md5)")
test_formula(lambda m: md5(sorted_json(m) + "MD5"), "md5(json+'MD5')")
test_formula(lambda m: md5(sorted_json(m) + m.get('securemode', '')), "md5(json+securemode)")
test_formula(lambda m: md5(sorted_json(m) + m.get('deviceid', '')), "md5(json+deviceid)")
test_formula(lambda m: md5(sorted_json(m) + m.get('sdid', '')), "md5(json+sdid)")

# HMAC variants
test_formula(lambda m: hmac_md5(APP_KEY, sorted_json(m)), "hmac(appKey, json)")
test_formula(lambda m: hmac_md5(CERT_MD5, sorted_json(m)), "hmac(cert_md5, json)")
test_formula(lambda m: hmac_md5("MD5", sorted_json(m)), "hmac('MD5', json)")
test_formula(lambda m: hmac_md5(m.get('deviceid', ''), sorted_json(m)), "hmac(deviceid, json)")

# md5 of combinations
test_formula(lambda m: md5(APP_KEY + sorted_json(m)), "md5(appKey+json)")
test_formula(lambda m: md5(APP_KEY + sorted_json(m) + APP_KEY), "md5(appKey+json+appKey)")
test_formula(lambda m: md5(sorted_json(m) + APP_KEY + CERT_MD5), "md5(json+appKey+cert)")
test_formula(lambda m: md5(sorted_json(m) + CERT_MD5 + APP_KEY), "md5(json+cert+appKey)")

# Double hash
test_formula(lambda m: md5(md5(sorted_json(m)) + APP_KEY), "md5(md5(json)+appKey)")
test_formula(lambda m: md5(sorted_json(m) + md5(APP_KEY)), "md5(json+md5(appKey))")

# XOR of two keys  
appKey_b = bytes.fromhex(APP_KEY)
cert_b = bytes.fromhex(CERT_MD5)
xor_key = bytes(a^b for a,b in zip(appKey_b, cert_b))
test_formula(lambda m, k=xor_key: hmac_md5(k, sorted_json(m)), "hmac(appKey XOR cert, json)")
test_formula(lambda m, k=xor_key: md5(sorted_json(m) + k.hex()), "md5(json+xor_key)")

# Try with value-only concatenation (not JSON)
def concat_values(m):
    return ''.join(str(m[k]) for k in sorted(m.keys()))
test_formula(lambda m: md5(concat_values(m) + APP_KEY), "md5(sortedValues+appKey)")
test_formula(lambda m: md5(concat_values(m) + CERT_MD5), "md5(sortedValues+cert)")

# Try key=value& format
def kv_format(m):
    return '&'.join(f"{k}={m[k]}" for k in sorted(m.keys()))
test_formula(lambda m: md5(kv_format(m) + APP_KEY), "md5(kv+appKey)")
test_formula(lambda m: md5(kv_format(m) + CERT_MD5), "md5(kv+cert)")

# Try without sessionid
def sorted_json_no_session(m):
    m2 = {k: v for k, v in m.items() if k != 'sessionid'}
    return json.dumps(m2, separators=(',', ':'), sort_keys=True)
test_formula(lambda m: md5(sorted_json_no_session(m) + APP_KEY), "md5(json_no_session+appKey)")
test_formula(lambda m: md5(sorted_json_no_session(m) + CERT_MD5), "md5(json_no_session+cert)")

# securemode="MD5" means the key IS the MD5 hash
# Maybe key = md5(appKey)
appKey_md5 = md5(APP_KEY)
test_formula(lambda m: md5(sorted_json(m) + appKey_md5), "md5(json+md5(appKey))")
test_formula(lambda m: hmac_md5(appKey_md5, sorted_json(m)), "hmac(md5(appKey), json)")

# Try md5(appKey + cert)
combo = md5(APP_KEY + CERT_MD5)
test_formula(lambda m: md5(sorted_json(m) + combo), "md5(json+md5(appKey+cert))")

# Pure md5 of json (no key)
test_formula(lambda m: md5(sorted_json(m)), "md5(json)")

# timestamp as key
test_formula(lambda m: md5(sorted_json(m) + m['timestamp']), "md5(json+timestamp)")

print("\n=== Checking isUC=false sign for SAME body ===")
# Just to confirm isUC=false for case1
j1_nosign = sorted_json(CASE1_MAP)
false_sign = md5(j1_nosign + APP_KEY)
print(f"isUC=false sign for case1: {false_sign}")
print(f"isUC=true  sign for case1: {CASE1_SIGN}")
print(f"Same? {false_sign == CASE1_SIGN}")

print("\nDone.")
