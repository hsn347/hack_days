import hashlib, hmac as hmac_lib, base64

T = [
    ('', '292acee0423c18171018f4cee8435606'),
    ('a', 'e8fe77a5f1a269da23330f658ef55889'),
    ('{}', 'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('hello world', '33a3b048e9a0351d341935ad4e133a32'),
    ('{"a":"1"}', '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}', '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('aaaaaaaaaaaaaaaa', 'e3700fe853c28bfc0249c12777ad40c8'),
    ('1234567890', '3921450ff47fa5a4b86d301abed28f51'),
]

def md5b(b): return hashlib.md5(b).hexdigest()
def hmac_md5(k, d): return hmac_lib.new(k if isinstance(k,bytes) else k.encode(), d if isinstance(d,bytes) else d.encode(), hashlib.md5).hexdigest()

def test(fn, name):
    r = [fn(t[0]) == t[1] for t in T]
    n = sum(r)
    if n >= 2: print(f'  ({n}/{len(T)}): {name}')
    if n == len(T): print(f'  *** FULL MATCH: {name} ***')
    return n == len(T)

cert_md5 = '47965e93ad48a1d34f9ef116405aa6cf'
cert_sha1 = '3c9d1f19089bb8faa43e18b6e71fff35562dc918'
cert_md5_b = bytes.fromhex(cert_md5)
cert_sha1_b = bytes.fromhex(cert_sha1)
ak_str = 'd252596f076c9213dce69cdb39d488ea'
ak_b = bytes.fromhex(ak_str)

DAEMON_B64 = "4rB5GeN3NzcyJkePA4rGSxUAIGep4ecGHZi1S+ebb/n6jZ3o+ko34ZIqWtR1MbHOOnTh9nGViMgu5lqWx2r0QKSzi+UFWO+4WtPKYn5jRZdkpRDTcprXrMlvDj5/Y5eOe3AaG9qS/3O30m+YrLXd8oCNQrY2XnVgz0KNfPLXDf/8Uyo0CJ8CgSbC5MaTUg8imUrhiUqBm5eGjKNZPrVhr0lent/TjLSwyFk/f++qfe1pv2ctydVG/oVm4ZHHn2Xvqgtxm5KIvHkNPpSBZTvNZp61f59UQxbqAqaCy9M/pDi/p746gUUeX6LS+n38QAYqjoBg+YlZIyyxgWx1coNwKw=="
daemon_bytes = base64.b64decode(DAEMON_B64)

print('=== Testing cert keys ===')
for key_bytes, name in [
    (cert_md5_b,       'cert_md5_bytes'),
    (cert_sha1_b[:16], 'cert_sha1_bytes[:16]'),
    (cert_sha1_b,      'cert_sha1_bytes'),
]:
    test(lambda j, k=key_bytes: md5b(j.encode() + k), f'md5(input+{name})')
    test(lambda j, k=key_bytes: md5b(k + j.encode()), f'md5({name}+input)')
    if len(key_bytes) in [16, 20]:
        test(lambda j, k=key_bytes: hmac_md5(k, j), f'HMAC-MD5({name},input)')

for key_str, name in [
    (cert_md5, 'cert_md5_str'),
    (cert_sha1, 'cert_sha1_str'),
]:
    test(lambda j, k=key_str: md5b((j+k).encode()), f'md5(input+{name})')
    test(lambda j, k=key_str: md5b((k+j).encode()), f'md5({name}+input)')

print('=== cert + appKey combos ===')
for key_str, name in [
    (cert_md5 + ak_str, 'cert_md5+appKey'),
    (ak_str + cert_md5, 'appKey+cert_md5'),
    (md5b((cert_md5+ak_str).encode()), 'md5(cert_md5+appKey)'),
    (md5b((ak_str+cert_md5).encode()), 'md5(appKey+cert_md5)'),
    (md5b((cert_sha1+ak_str).encode()), 'md5(cert_sha1+appKey)'),
]:
    test(lambda j, k=key_str: md5b((j+k).encode()), f'md5(input+{name[:20]})')
    
print('=== daemon as key ===')
for i in range(0, min(len(daemon_bytes)-16, 256), 8):
    for klen in [16, 20]:
        k = daemon_bytes[i:i+klen]
        if len(k) == klen:
            if test(lambda j, key=k: hmac_md5(key, j), f'HMAC-MD5(daemon[{i}:{i+klen}])'):
                print(f'KEY: {k.hex()}')
            if test(lambda j, key=k: md5b(j.encode()+key), f'md5(input+daemon[{i}:{i+klen}])'):
                print(f'KEY: {k.hex()}')

print('=== cert XOR daemon ===')
for i in range(0, min(len(daemon_bytes)-16, 64), 4):
    k = bytes(a^b for a,b in zip(daemon_bytes[i:i+16], cert_md5_b))
    test(lambda j, key=k: hmac_md5(key, j), f'HMAC-MD5(daemon[{i}] XOR cert_md5)')
    test(lambda j, key=k: md5b(j.encode()+key), f'md5(input+daemon[{i}] XOR cert_md5)')

print('=== XOR patterns ===')
xk = bytes(a^b for a,b in zip(cert_md5_b, ak_b))
test(lambda j,k=xk: hmac_md5(k,j), 'HMAC(cert XOR ak)')
test(lambda j,k=xk: md5b(j.encode()+k), 'md5(input+cert XOR ak)')

print('DONE')
