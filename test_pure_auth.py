import base64, hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

app_key_b64 = 'K3xwf2F2eCN9Y3ktfH9lfComKGJ2LSEvZ3YqcXVsKi8='
app_token_bytes = base64.b64decode(app_key_b64)
print('Decoded token bytes:', app_token_bytes)

# XOR with b"ONEMT"
onemt_key = b"ONEMT"
xored = bytearray(len(app_token_bytes))
for i in range(len(app_token_bytes)):
    xored[i] = app_token_bytes[i] ^ onemt_key[i % len(onemt_key)]

print('XORed string:', bytes(xored))

# MD5 uppercase
md5_hex = hashlib.md5(xored).hexdigest().upper()
print('MD5 hex:', md5_hex)

aes_key = md5_hex[:16].encode('utf-8')
aes_iv = md5_hex[16:32].encode('utf-8')
print('AES Key:', aes_key)
print('AES IV: ', aes_iv)

# Test AES encryption with PKCS7 padding
def aes_encrypt(plain_text: str) -> str:
    data = plain_text.encode('utf-8')
    pad_len = 16 - (len(data) % 16)
    data += bytes([pad_len] * pad_len)
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv), backend=default_backend()).encryptor()
    ct = cipher.update(data) + cipher.finalize()
    return base64.b64encode(ct).decode('utf-8')

def aes_decrypt(cipher_b64: str) -> str:
    ct = base64.b64decode(cipher_b64)
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv), backend=default_backend()).decryptor()
    plain = cipher.update(ct) + cipher.finalize()
    pad_len = plain[-1]
    return plain[:-pad_len].decode('utf-8')

test_str = '{"name":"test@gmail.com","password":"abc"}'
enc = aes_encrypt(test_str)
dec = aes_decrypt(enc)
print('Test enc:', enc)
print('Test dec:', dec)
assert dec == test_str, "AES Decrypt mismatch!"
print('✓ AES Encryption and Decryption Verified Perfectly!')
