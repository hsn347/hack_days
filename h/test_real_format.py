#!/usr/bin/env python3
"""
الاختبار النهائي!
format من login_dec.lua + userid من AccountManager + DES padding صحيح (ISO 7816-4)
"""
import sys
sys.path.insert(0, r'E:\osmanli')
from onemt_bot import dh_exchange, dh_secret, hmac64, random_key
import socket, base64
from Crypto.Cipher import DES

HOST = '119.8.212.255'
PORT = 10000

# بيانات حقيقية من AccountManager.getInstance() dump:
USERID  = '8120e389ed552b4774dd5d8ed0c26e01'   # getUserId()
SESSION = 'PNVlQ71Jqy/h5CwD1POoJHh7hrmEjit33AKImDBOdV2cm2NZuFygKXHCVxWNYCGYthqGrvdLZo0VtEY7qnZ0kw=='  # getSessionId() = authId

def b64e(b):
    if isinstance(b, str): b = b.encode()
    return base64.b64encode(b).decode()

def skynet_des_encode(data: bytes, key: bytes) -> bytes:
    """
    مطابقة كاملة لـ skynet crypt.desencode (ISO 7816-4 padding)
    
    chunksz = (textsz + 8) & ~7   ← دائماً block إضافي!
    Padding: buf[offset] = 0x80, rest = 0x00
    DES ECB, كل block منفصل
    """
    textsz = len(data)
    chunksz = (textsz + 8) & ~7   # الفرق الأساسي! دائماً block padding إضافي
    
    # بناء buffer مع ISO 7816-4 padding
    padded = bytearray(chunksz)
    padded[:textsz] = data
    # آخر block: remaining bytes + 0x80 + 0x00...
    offset = textsz % 8
    tail_start = textsz - offset
    padded[textsz] = 0x80  # ISO 7816-4 marker
    # الباقي أصفار (bytearray يفعل ذلك تلقائياً)
    
    cipher = DES.new(key[:8], DES.MODE_ECB)
    return cipher.encrypt(bytes(padded))

# ===== Handshake =====
s = socket.socket(); s.settimeout(20); s.connect((HOST, PORT))
buf = b''
def rl():
    global buf
    while b'\n' not in buf: buf += s.recv(4096)
    idx = buf.index(b'\n'); line = buf[:idx].decode().strip(); buf = buf[idx+1:]
    return line
def sl(t): s.sendall((t+'\n').encode())

ch = base64.b64decode(rl())
priv = random_key()
pub = dh_exchange(priv)
sl(b64e(pub))
sk = base64.b64decode(rl())
sec = dh_secret(sk, priv)
sl(b64e(hmac64(ch, sec)))
resp = rl()
print('Handshake:', resp)
if '200' not in resp:
    print('HANDSHAKE FAILED!'); s.close(); exit(1)

# ===== Token =====
# encodetoken = b64(user) @ b64(pass) : b64(subtoken)
# user = userid, pass = "password", subtoken = sessionId
token_plain = '%s@%s:%s' % (b64e(USERID), b64e('password'), b64e(SESSION))
print('Token plain (%d chars): %s...' % (len(token_plain), token_plain[:60]))

# Parts
p1 = b64e(skynet_des_encode(token_plain.encode(), sec))
p2 = b64e(skynet_des_encode(b'3.34.001', sec))                # GAME_VERSION
p3 = b64e(skynet_des_encode(b'Android 8.1.0 sdk_gphone64_x86_64 Google and.onemt.boe.tr ar', sec))
p4 = b64e(skynet_des_encode(b'sdk_gphone64_x86_64', sec)) # model
p5 = b64e(skynet_des_encode(b'Android', sec))              # carrier

msg = '@'.join([p1, p2, p3, p4, p5])
sl(msg)

auth = rl()
print()
print('AUTH RESPONSE:', auth[:200])
code = auth[:3]
if code == '200':
    print()
    print('*' * 50)
    print('***         SUCCESS!!!            ***')
    print('*' * 50)
    data_b64 = auth[4:]
    data = base64.b64decode(data_b64).decode()
    parts = data.split('@')
    fields = ['kingdomId','servername','gateip','gateport','subid','uid','gateProxyHost','gateProxyPort']
    for i, name in enumerate(fields):
        if i < len(parts):
            try: val = base64.b64decode(parts[i]).decode()
            except: val = parts[i]
            print('  %s = %s' % (name, val))
    
    # حفظ البيانات
    import json
    config = {
        'userid': USERID,
        'session': SESSION,
        'gate_ip': base64.b64decode(parts[2]).decode() if len(parts) > 2 else '',
        'gate_port': int(base64.b64decode(parts[3]).decode()) if len(parts) > 3 else 0,
        'servername': base64.b64decode(parts[1]).decode() if len(parts) > 1 else '',
        'subid': base64.b64decode(parts[4]).decode() if len(parts) > 4 else '',
        'uid': base64.b64decode(parts[5]).decode() if len(parts) > 5 else '',
        'secret': base64.b64encode(sec).decode(),
        'login_index': 1,
    }
    with open('E:/osmanli/live_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    print('\n  Saved to live_config.json!')
else:
    print('Code:', code)

s.close()
