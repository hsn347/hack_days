"""
تجربة كل صيغ HMAC الممكنة للعثور على الصحيحة
Expected: oCzB3KbMWu0=
"""
import base64, hashlib, hmac as hmac_mod

USERNAME = "MTA2MDA3NDM=@a29oX2dhbWVfMjY=#MjUwMjE3"
INDEX    = 1
EXPECTED = "oCzB3KbMWu0="
EXPECTED_BYTES = base64.b64decode(EXPECTED)

username_bytes = USERNAME.encode()

def b64(b): return base64.b64encode(b).decode()

# custom_hmac64 (Skynet-style)
def custom_hmac64(msg: bytes, key: bytes) -> bytes:
    klen = len(key)
    buf  = bytearray(16)
    for i, b in enumerate(msg):
        buf[i % 16] ^= b ^ key[i % klen]
    return hashlib.md5(bytes(buf)).digest()[:8]

idx_str = str(INDEX)
combo = (USERNAME + ":" + idx_str).encode()

results = {}

# 1. hmac64(sha1(username:index), username)
sha1_combo = hashlib.sha1(combo).digest()
r1 = custom_hmac64(sha1_combo, username_bytes)
results["hmac64(sha1(u:i), u)"] = r1

# 2. hmac64(username, sha1(username:index))
r2 = custom_hmac64(username_bytes, sha1_combo)
results["hmac64(u, sha1(u:i))"] = r2

# 3. hmac64(sha1(username:index), sha1(username:index))
r3 = custom_hmac64(sha1_combo, sha1_combo)
results["hmac64(sha1, sha1)"] = r3

# 4. sha1(username:index)[:8]
r4 = sha1_combo[:8]
results["sha1(u:i)[:8]"] = r4

# 5. md5(username:index)[:8]
r5 = hashlib.md5(combo).digest()[:8]
results["md5(u:i)[:8]"] = r5

# 6. hmac-sha1 with key=sha1(u:i), msg=u
r6 = hmac_mod.new(sha1_combo, username_bytes, hashlib.sha1).digest()[:8]
results["hmac-sha1(sha1(u:i), u)[:8]"] = r6

# 7. hmac-sha1 with key=md5(u:i), msg=u
md5_combo = hashlib.md5(combo).digest()
r7 = hmac_mod.new(md5_combo, username_bytes, hashlib.sha1).digest()[:8]
results["hmac-sha1(md5(u:i), u)[:8]"] = r7

# 8. hmac-md5 with key=sha1(u:i), msg=u
r8 = hmac_mod.new(sha1_combo, username_bytes, hashlib.md5).digest()[:8]
results["hmac-md5(sha1(u:i), u)[:8]"] = r8

# 9. hmac64(sha1(sha1(u:i)), u)
sha1_sha1 = hashlib.sha1(sha1_combo).digest()
r9 = custom_hmac64(sha1_sha1, username_bytes)
results["hmac64(sha1(sha1(u:i)), u)"] = r9

# 10. hmac64 with index
combo2 = (USERNAME + ":" + str(INDEX)).encode()
r10 = custom_hmac64(hashlib.sha1(combo2).digest(), username_bytes)
results["hmac64(sha1(u:idx_int), u)"] = r10

# 11. Skynet style: hmac64(sha1(key), username) where key = username:index
# same as #1, but try different encoding of index
combo3 = (USERNAME + ":" + format(INDEX, 'd')).encode()
r11 = custom_hmac64(hashlib.sha1(combo3).digest(), username_bytes)
results["hmac64(sha1(u:d), u)"] = r11

# 12. hmac-sha1 directly on username with key = username:index bytes
r12 = hmac_mod.new(combo, username_bytes, hashlib.sha1).digest()[:8]
results["hmac-sha1(u:i, u)[:8]"] = r12

# 13. sha1(username + sha1(username:index))
inner = USERNAME.encode() + sha1_combo
r13 = hashlib.sha1(inner).digest()[:8]
results["sha1(u + sha1(u:i))[:8]"] = r13

# 14. raw custom_hmac64(username, username:index)
r14 = custom_hmac64(username_bytes, combo)
results["hmac64(u, u:i)"] = r14

# 15. hmac64 with just index as key
r15 = custom_hmac64(username_bytes, str(INDEX).encode())
results["hmac64(u, idx)"] = r15

# 16. SHA1(sha1(u:i) + u)
r16 = hashlib.sha1(sha1_combo + username_bytes).digest()[:8]
results["sha1(sha1(u:i)+u)[:8]"] = r16

print(f"Expected: {EXPECTED} = {EXPECTED_BYTES.hex()}")
print()
found = False
for label, val in results.items():
    match = "*** MATCH! ***" if val == EXPECTED_BYTES else ""
    print(f"  {label}: {b64(val)} {match}")
    if val == EXPECTED_BYTES:
        found = True

if not found:
    print("\n[!] None matched - need to try other algorithms")
