import hashlib, hmac as hmac_lib

TESTS = [
    ('', '292acee0423c18171018f4cee8435606'),
    ('a', 'e8fe77a5f1a269da23330f658ef55889'),
    ('{}', 'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('hello world', '33a3b048e9a0351d341935ad4e133a32'),
    ('{"a":"1"}', '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}', '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('1234567890', '3921450ff47fa5a4b86d301abed28f51'),
    ('aaaaaaaaaaaaaaaa', 'e3700fe853c28bfc0249c12777ad40c8'),
]

DEC_HEX = '3afd7bfdfdfd493007fdfdfdfd552813fd467c6bfd58fd4417fd254047190632fdfd09010b2c177e76fd7cfd1bfdfdfdfd5a0362a3fdfdfdfdfd342a64fd3efdfdfdfdfdfdfdfdfdfd44fd6f2d7dfd5b7cfdfdfdb1bc140dfdfd2b5ffdfd1214fd60fd6c4efd1627fd2cfdfdfd52fd4efdfd5f7558fd0efd3a24fd15fd57fdfdfd4afd06fdfd0e2b1e26440bfd016a24fdfdfd6cfd11fd1d57fdfd2e0cfdfd56fd07fd6c4c3c75fd7974fd75634498411c450efdfd1bfd5402fdfdfd706b5c72fd76501cfd4c11fd6155fd48fdfd39fd0efd12fdfdfd1744fd22fdfdfdfdfdfdfd4031735c'
dec = bytes.fromhex(DEC_HEX)
print(f'dec len={len(dec)} bytes')

cert_md5_b = bytes.fromhex('47965e93ad48a1d34f9ef116405aa6cf')
ak_b = bytes.fromhex('d252596f076c9213dce69cdb39d488ea')

def md5b(b): return hashlib.md5(b).hexdigest()
def hmac_md5(k, d):
    return hmac_lib.new(k if isinstance(k, bytes) else k.encode(), 
                        d if isinstance(d, bytes) else d.encode(), hashlib.md5).hexdigest()

def test(fn, name, mn=4):
    r = [fn(t[0]) == t[1] for t in TESTS]
    n = sum(r)
    if n >= mn:
        print(f'  ({n}/{len(TESTS)}): {name}')
    if n == len(TESTS):
        print(f'  *** FULL MATCH ***')
    return n == len(TESTS)

found = False

print('\n=== Sliding window over decrypted daemon bytes ===')
for klen in [16, 20, 24, 32]:
    for i in range(0, len(dec)-klen+1, 1):
        k = dec[i:i+klen]
        if test(lambda j, key=k: hmac_md5(key, j), f'HMAC(dec[{i}:{i+klen}])'):
            found = True
            print(f'  KEY HEX: {k.hex()}')
        if test(lambda j, key=k: md5b(j.encode() + key), f'md5(j+dec[{i}:{i+klen}])'):
            found = True
            print(f'  KEY HEX: {k.hex()}')
        if test(lambda j, key=k: md5b(key + j.encode()), f'md5(dec[{i}:{i+klen}]+j)'):
            found = True
            print(f'  KEY HEX: {k.hex()}')

print('\n=== Full decrypted daemon variants ===')
for k, name in [
    (dec, 'full_dec'),
    (bytes.fromhex(md5b(dec)), 'md5(full_dec)'),
    (bytes(a^b for a,b in zip(dec[:16], cert_md5_b)), 'dec[:16] XOR cert'),
    (bytes(a^b for a,b in zip(dec[:16], ak_b)), 'dec[:16] XOR appKey'),
]:
    if len(k) in [16, 20, 24, 32]:
        test(lambda j, key=k: hmac_md5(key, j), f'HMAC({name})', mn=2)
        test(lambda j, key=k: md5b(j.encode()+key), f'md5(j+{name})', mn=2)

print('\n=== Daemon + cert combos ===')
for i in range(0, min(len(dec)-16, 64), 4):
    chunk = dec[i:i+16]
    k = bytes(a^b for a,b in zip(chunk, cert_md5_b))
    test(lambda j, key=k: hmac_md5(key, j), f'HMAC(dec[{i}] XOR cert)', mn=3)
    test(lambda j, key=k: md5b(j.encode()+key), f'md5(j+dec[{i}] XOR cert)', mn=3)

print(f'\n{"FOUND!" if found else "Not found - fd bytes may be corrupted replacements"}')
