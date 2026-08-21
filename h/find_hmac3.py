import base64, hashlib, hmac as hmac_mod

OLD_200 = "TWpVNUBhMjlvWDJkaGJXVmZNalk9QE1URTVMamd1TWpFekxqRXhNUT09QE5EQXdNQT09QE1qVXdNRFU1QE1UQTJNVE0zTVRjPUBATUE5PQ=="
NEW_200 = "TWpVNUBhMjlvWDJkaGJXVmZNalk9QE1URTVMamd1TWpFekxqRXpNUT09QE5EQXdNQT09QE1qVXdNakUzQE1UQTJNREEzTkRNPUBATUE5PQ=="

def decode_200(s):
    inner = base64.b64decode(s).decode("latin1")
    fields = inner.split("@")
    res = {}
    for i,f in enumerate(fields):
        try:
            pad = "=" * (-len(f) % 4)
            v = base64.b64decode(f + pad)
            res[i] = (f, v)
        except:
            res[i] = (f, b"")
    return res

print("OLD 200:")
for i,(f,v) in decode_200(OLD_200).items():
    print("  [%d] hex=%s str=%r" % (i, v.hex(), v.decode("latin1")))

print("NEW 200:")
new = decode_200(NEW_200)
for i,(f,v) in new.items():
    print("  [%d] hex=%s str=%r" % (i, v.hex(), v.decode("latin1")))

sec = new.get(7, (None, b""))[1]
print("Field7 secret: %s" % sec.hex())

USERNAME2 = "MTA2MDA3NDM=@a29oX2dhbWVfMjY=#MjUwMjE3"
HMAC2_BYTES = base64.b64decode("oCzB3KbMWu0=")
u = USERNAME2.encode()
sha1_u1 = hashlib.sha1((USERNAME2 + ":1").encode()).digest()

def hmac64(msg, key):
    klen = len(key)
    buf = bytearray(16)
    for i,b in enumerate(msg):
        buf[i%16] ^= b ^ key[i%klen]
    return hashlib.md5(bytes(buf)).digest()[:8]

def b64(b):
    return base64.b64encode(b).decode()

tests = [
    ("hmac64(sha1,sec)", hmac64(sha1_u1, sec)),
    ("hmac64(sec,sha1)", hmac64(sec, sha1_u1)),
    ("hmac64(u,sec)",    hmac64(u, sec)),
    ("hmac64(sec,u)",    hmac64(sec, u)),
    ("hmac-sha1(sec,u)", hmac_mod.new(sec, u, hashlib.sha1).digest()[:8]),
    ("sha1(sec+sha1)[:8]", hashlib.sha1(sec + sha1_u1).digest()[:8]),
    ("sha1(sha1+sec)[:8]", hashlib.sha1(sha1_u1 + sec).digest()[:8]),
    ("hmac64(sha1,u+sec)", hmac64(sha1_u1, u + sec)),
    ("hmac64(sec+sha1,u)", hmac64(sec + sha1_u1, u)),
    ("hmac-sha1(sha1+sec,u)", hmac_mod.new(sha1_u1+sec, u, hashlib.sha1).digest()[:8]),
]

print("\nHMAC tests (expected oCzB3KbMWu0=):")
for label,val in tests:
    m = "*** MATCH ***" if val == HMAC2_BYTES else ""
    print("  %s: %s %s" % (label, b64(val), m))
