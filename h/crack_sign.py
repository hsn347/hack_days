import hashlib, hmac

cert_md5 = '47965e93ad48a1d34f9ef116405aa6cf'
cert_sha1 = '3c9d1f19089bb8faa43e18b6e71fff35562dc918'
appKey = 'd252596f076c9213dce69cdb39d488ea'

tests = [
    ('{"a":"1"}', '171980e57ef983a1b1df64bf9ec1163b'),
    ('{"b":"2"}', '450bb7b5ee9dd99bb2e09d0775a6ea73'),
    ('{}', 'd01ac4e2ad28d6503a38ec9f779bf424'),
    ('{"appid":"100002001"}', 'f65223b0f5c6b228c7060a05ce68a348'),
]

keys = {
    'cert_md5': cert_md5.encode(),
    'cert_md5_hex': bytes.fromhex(cert_md5),
    'cert_sha1': cert_sha1.encode(),
    'cert_sha1_16': cert_sha1[:32].encode(),
    'appKey+cert': (appKey+cert_md5).encode(),
    'cert+appKey': (cert_md5+appKey).encode(),
    'md5(cert+appKey)': hashlib.md5((cert_md5+appKey).encode()).hexdigest().encode(),
    'md5(appKey+cert)': hashlib.md5((appKey+cert_md5).encode()).hexdigest().encode(),
    'md5(cert)_hex': bytes.fromhex(hashlib.md5(cert_md5.encode()).hexdigest()),
}

found = False
for js, expected in tests[:1]:  # test first case only
    for kn, k in keys.items():
        v = hmac.new(k, js.encode(), hashlib.md5).hexdigest()
        if v == expected:
            print(f'HMAC-MD5({kn}): MATCH!')
            found = True
        v2 = hashlib.md5(js.encode() + k).hexdigest()
        if v2 == expected:
            print(f'md5(json+{kn}): MATCH!')
            found = True
        v3 = hashlib.md5(k + js.encode()).hexdigest()
        if v3 == expected:
            print(f'md5({kn}+json): MATCH!')
            found = True

# Try signWithAppKey of cert
sign_cert = hashlib.md5((cert_md5 + appKey).encode()).hexdigest()
for js, expected in tests[:1]:
    v = hashlib.md5((js + sign_cert).encode()).hexdigest()
    if v == expected:
        print(f'md5(json + signWithAppKey(certMd5)): MATCH!')
        found = True
    v2 = hmac.new(sign_cert.encode(), js.encode(), hashlib.md5).hexdigest()
    if v2 == expected:
        print(f'HMAC-MD5(signWithAppKey(certMd5), json): MATCH!')
        found = True

# Try md5(appKey) as hex bytes key
appKey_md5 = hashlib.md5(appKey.encode()).hexdigest()
for js, expected in tests[:1]:
    v = hmac.new(appKey_md5.encode(), js.encode(), hashlib.md5).hexdigest()
    if v == expected:
        print(f'HMAC-MD5(md5(appKey), json): MATCH!')
        found = True

# Try cert raw bytes
cert_raw_first = bytes.fromhex('3082019930820102a0030201020204554b0e16300d06092a864886f70d01010505003010310e300c060355040a13056f6e656d743020170d3135303530373037')
for js, expected in tests[:1]:
    for size in [16, 32, 64]:
        v = hmac.new(cert_raw_first[:size], js.encode(), hashlib.md5).hexdigest()
        if v == expected:
            print(f'HMAC-MD5(cert_raw[:{size}], json): MATCH!')
            found = True

if not found:
    print("No match found with cert-based keys")
    
    # Brute: try md5(json + X) where X is any 32-char hex
    # For {} test: d01ac4e2ad28d6503a38ec9f779bf424
    # If sign = md5("{}" + KEY), then:
    print("\nReverse engineering the key from empty json test...")
    print(f"sign('{{}}') = d01ac4e2ad28d6503a38ec9f779bf424")
    print(f"If sign = md5('{{}}' + KEY), KEY must produce this hash")
    print(f"This is computationally infeasible to brute-force")
    
    print("\nAlternative: the sign might use HMAC with a key derived from the daemon")
