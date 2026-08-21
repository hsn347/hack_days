import hashlib, hmac as hmac_lib, struct

# isUC=TRUE test cases (all confirmed, fixed key)
TESTS = [
    ('',                 '292acee0423c18171018f4cee8435606'),
    ('a',                'e8fe77a5f1a269da23330f658ef55889'),
    ('{}',               'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"a":"1"}',        '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}',        '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('hello world',      '33a3b048e9a0351d341935ad4e133a32'),
    ('aaaaaaaaaaaaaaaa', 'e3700fe853c28bfc0249c12777ad40c8'),
    ('1234567890',       '3921450ff47fa5a4b86d301abed28f51'),
]

appKey = b'd252596f076c9213dce69cdb39d488ea'

def md5(b): return hashlib.md5(b).hexdigest()
def hmac_md5(key, data): return hmac_lib.new(key, data, hashlib.md5).hexdigest()

def test_key_suffix(key_bytes, name=''):
    """Test if md5(input + key_bytes) matches all test cases"""
    for t_str, expected in TESTS[:3]:
        if md5(t_str.encode() + key_bytes) != expected:
            return False
    # Full check if first 3 pass
    ok = all(md5(t.encode() + key_bytes) == e for t, e in TESTS)
    if ok: print(f"  *** SUFFIX KEY FOUND: {name} = {key_bytes.hex()} ***")
    return ok

def test_key_prefix(key_bytes, name=''):
    """Test if md5(key_bytes + input) matches"""
    for t_str, expected in TESTS[:3]:
        if md5(key_bytes + t_str.encode()) != expected:
            return False
    ok = all(md5(key_bytes + t.encode()) == e for t, e in TESTS)
    if ok: print(f"  *** PREFIX KEY FOUND: {name} = {key_bytes.hex()} ***")
    return ok

def test_hmac(key_bytes, name=''):
    """Test HMAC-MD5(key, input)"""
    for t_str, expected in TESTS[:3]:
        if hmac_md5(key_bytes, t_str.encode()) != expected:
            return False
    ok = all(hmac_md5(key_bytes, t.encode()) == e for t, e in TESTS)
    if ok: print(f"  *** HMAC KEY FOUND: {name} = {key_bytes.hex()} ***")
    return ok

# Read binary
print("Reading binary...")
with open(r'E:\osmanli\libdaemonutil.so', 'rb') as f:
    data = f.read()
print(f"Binary size: {len(data)} bytes")

# The target: find key K such that md5(input + K) = expected
# For empty input: md5(K) = 292acee0423c18171018f4cee8435606
# This means K itself is a fixed value whose MD5 = 292acee0423c18171018f4cee8435606

# Approach: slide a window over the binary and test each N-byte chunk as key
print("Scanning binary with sliding window...")
found = False
step = 4  # Scan every 4 bytes for speed
for key_len in [32, 16, 20, 24, 8, 64]:
    count = 0
    for i in range(0, len(data) - key_len, step):
        key = data[i:i+key_len]
        if test_key_suffix(key, f"binary[{i}:{i+key_len}]"):
            found = True
            print(f"  Found at offset {i}, length {key_len}: {key.hex()}")
        if test_key_prefix(key, f"binary[{i}:{i+key_len}]"):
            found = True
        if test_hmac(key, f"binary[{i}:{i+key_len}]"):
            found = True
        count += 1
    print(f"  Scanned {count} positions with key_len={key_len}")

if not found:
    print("\nNot found with simple window scan.")
    print("The key may be derived/computed at runtime from multiple sources.")
    
    # Try: key = md5(something_in_binary)
    print("\nTrying md5(binary_chunk) as key...")
    for chunk_len in [8, 16, 32]:
        for i in range(0, min(len(data)-chunk_len, 500000), 16):
            chunk = data[i:i+chunk_len]
            k = bytes.fromhex(md5(chunk))  # 16-byte key
            if test_key_suffix(k, f"md5(binary[{i}:{i+chunk_len}])"):
                found = True
                print(f"  CHUNK: {chunk.hex()}")
            if test_hmac(k, f"hmac-md5(md5(binary[{i}:{i+chunk_len}]), input)"):
                found = True

print(f"\n{'ALGORITHM CRACKED!' if found else 'KEY NOT FOUND IN BINARY - needs deeper analysis'}")
