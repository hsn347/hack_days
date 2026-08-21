"""
فك تشفير كلا الـ 200 responses وتجربة HMAC مع field 7 (gate secret)
"""
import base64, hashlib, hmac as hmac_mod

# 200 responses
OLD_200 = "TWpVNUBhMjlvWDJkaGJXVmZNalk9QE1URTVMamd1TWpFekxqRXhNUT09QE5EQXdNQT09QE1qVXdNRFU1QE1UQTJNVE0zTVRjPUBATUE5PQ=="  # king7moe
NEW_200 = "TWpVNUBhMjlvWDJkaGJXVmZNalk9QE1URTVMamd1TWpFekxqRXpNUT09QE5EQXdNQT09QE1qVXdNakUzQE1UQTJNREEzTkRNPUBATUE5PQ=="  # account 2

def decode_200(b64_str):
    inner = base64.b64decode(b64_str).decode('latin1')
    fields = inner.split('@')
    result = {}
    for i, f in enumerate(fields):
        try:
            pad = '=' * (-len(f) % 4)
            val = base64.b64decode(f + pad)
            result[i] = {'raw': f, 'bytes': val, 'str': val.decode('utf-8', errors='replace')}
        except:
            result[i] = {'raw': f, 'bytes': b'', 'str': f}
    return result

print("=== OLD 200 (king7moe) ===")
old = decode_200(OLD_200)
for i, v in old.items():
    print(f"  Field {i}: {v['raw']!r} → {v['str']!r} hex={v['bytes'].hex()}")

print()
print("=== NEW 200 (account 2) ===")
new = decode_200(NEW_200)
for i, v in new.items():
    print(f"  Field {i}: {v['raw']!r} → {v['str']!r} hex={v['bytes'].hex()}")

# Account 2 data from capture
USERNAME2 = "MTA2MDA3NDM=@a29oX2dhbWVfMjY=#MjUwMjE3"
HMAC2_EXPECTED = "oCzB3KbMWu0="
HMAC2_BYTES = base64.b64decode(HMAC2_EXPECTED)
INDEX = 1

print()
print(f"=== Testing HMAC for account 2 ===")
print(f"Username: {USERNAME2}")
print(f"Expected: {HMAC2_EXPECTED} = {HMAC2_BYTES.hex()}")

def custom_hmac64(msg: bytes, key: bytes) -> bytes:
    klen = len(key)
    buf  = bytearray(16)
    for i, b in enumerate(msg):
        buf[i % 16] ^= b ^ key[i % klen]
    return hashlib.md5(bytes(buf)).digest()[:8]

def b64e(b): return base64.b64encode(b).decode()

u = USERNAME2.encode()
sha1_u_idx = hashlib.sha1(f"{USERNAME2}:{INDEX}".encode()).digest()

# Get field 7 for account 2
secret_bytes = new[7]['bytes']
print(f"Field 7 (gate secret): hex={secret_bytes.hex()} repr={secret_bytes!r}")

formulas = {
    "hmac64(sha1(u:i), secret)": custom_hmac64(sha1_u_idx, secret_bytes),
    "hmac64(secret, sha1(u:i))": custom_hmac64(secret_bytes, sha1_u_idx),
    "hmac64(u, secret)":          custom_hmac64(u, secret_bytes),
    "hmac64(secret, u)":          custom_hmac64(secret_bytes, u),
    "hmac64(sha1(u:i), u+secret)": custom_hmac64(sha1_u_idx, u + secret_bytes),
    "sha1(u:i + secret)[:8]":     hashlib.sha1(f"{USERNAME2}:{INDEX}".encode() + secret_bytes).digest()[:8],
    "hmac-sha1(secret, u)[:8]":  hmac_mod.new(secret_bytes, u, hashlib.sha1).digest()[:8],
    "hmac-sha1(secret, sha1(u:i))[:8]": hmac_mod.new(secret_bytes, sha1_u_idx, hashlib.sha1).digest()[:8] if len(secret_bytes) >= 1 else b'',
    "custom_hmac64(sha1(u:i+secret), u)": custom_hmac64(hashlib.sha1(f"{USERNAME2}:{INDEX}".encode() + secret_bytes).digest(), u),
}

found = False
for label, val in formulas.items():
    match = "*** MATCH ***" if val == HMAC2_BYTES else ""
    print(f"  {label}: {b64e(val)} {match}")
    if val == HMAC2_BYTES:
        found = True

if not found:
    print("\n[!] No match - field 7 might not be the secret")
    print("    Field 7 bytes:", secret_bytes.hex())
