# توثيق بروتوكول لعبة Empire (ONEMT)
# مستخرج من: Frida hooks، reverse engineering، Python bot

## 1. البنية العامة

```
[اللاعب]
    ↕ HTTPS REST
[UC API] https://apiuc.menaapp.net/
    ↕ HTTP login → sessionId + userId

[اللاعب]
    ↕ TCP text protocol (newlines)
[Login Server] 119.8.212.255:10000
    ↕ DH key exchange → secret
    ↕ DES-encrypted token → gate address

[اللاعب]
    ↕ Binary framed protocol (XOR)
[Gate Server] 119.8.213.131:4000
    ↕ أوامر اللعبة
```

## 2. HTTP / UC Layer

### SDK Info
```
App ID:     100002001
Package:    and.onemt.boe.tr
Channel:    googleplay
SDK Ver:    5.33.0
AppKey:     d252596f076c9213dce69cdb39d488ea
Base URL:   https://apiuc.menaapp.net/
```

### Signing
**isUC=false** (مُثبَّت):
```python
sorted_json = json.dumps(params, sort_keys=True, separators=(',',':'))
sign = md5(sorted_json + appKey)
```

**isUC=true** (مجهول):
```
securemode = "MD5"
المفتاح محسوب داخل libdaemonutil.so - لا يمكن كسره بدون الجهاز
test cases: {} → d01ac4e2ad28d6503a38ec9f779bf424
```

### UC Request Body
```json
{
  "appid": "100002001",
  "channel": "googleplay",
  "clientversion": "5.33.0",
  "deviceid": "b511d1c73fdc4a441ff92258e301559b",
  "lang": "ar",
  "originalid": "62471686-37C0-4343-BA63-0EB829162B17",
  "packagename": "and.onemt.boe.tr",
  "platform": "android",
  "reqdata": "<url_encoded_json>",
  "rstatus": "0",
  "sdid": "62471686-37C0-4343-BA63-0EB829162B17",
  "securemode": "MD5",
  "sessionid": "<session_base64>",
  "sign": "<computed_sign>",
  "timestamp": "<unix_timestamp>"
}
```

### Session Storage
```
File: /data/data/and.onemt.boe.tr/shared_prefs/SdkEmail.xml
Format: email → userId(32hex) + "OneMT" + base64(sessionId)
Extract: python extract_session_adb.py --save-all
```

## 3. Login Server (TCP Text)

```
Host: 119.8.212.255  Port: 10000
Protocol: Text lines (newline-separated)
```

### DH Parameters (ARM64 binary)
```python
DH_P = 0xFFFFFFFFFFFFFFC5   # 2^64 - 59 (prime)
DH_G = 5
# كل القيم Little-Endian 8 bytes
```

### Handshake Sequence
```
← CHALLENGE   base64(8 random bytes)
→ CLIENT_KEY  base64(pow(5, priv, P) as LE 8 bytes)
← SERVER_KEY  base64(server DH public)
→ HMAC        base64(custom_hmac64(challenge, secret))
← 200 challenge success
→ TOKEN       base64(DES(secret, token)) @ base64(DES(secret, game_ver)) @ ...
← 200 base64(gate_info)
```

### custom_hmac64 (lhmac64 ARM64)
```python
def hmac64(challenge, secret):
    ch_lo, ch_hi   = struct.unpack('<2I', challenge)
    sec_lo, sec_hi = struct.unpack('<2I', secret)
    pattern = struct.pack('<4I', ch_hi, ch_lo, sec_hi, sec_lo)
    A, B, C, D = md5_compress_no_add(pattern * 4)
    return struct.pack('<2I', (C^D)&0xFFFFFFFF, (B^A)&0xFFFFFFFF)
```

### DES Encoding (ISO 7816-4)
```python
def skynet_des_encode(data, key):
    chunksz = (len(data) + 8) & ~7  # دائماً block إضافي
    padded = bytearray(chunksz)
    padded[:len(data)] = data
    padded[len(data)] = 0x80
    return DES.new(key[:8], DES.MODE_ECB).encrypt(bytes(padded))
```

### Token Format
```python
token_str = f"{b64(userId)}@{b64('password')}:{b64(sessionId)}"
# ثم DES-encrypt مع secret
```

### Gate Info Response
```
kingdomId @ servername @ gateip @ gateport @ subid @ uid @ proxyHost @ proxyPort
```
مثال: `119.8.213.131:4000  UID:10615183  koh_game_26`

## 4. Gate Server (TCP Binary)

```
Host: 119.8.213.131  Port: 4000
```

### Gate Handshake
```python
payload = json.dumps({"username": username, "index": index, "hmac": hmac_val})
packet  = bytes([len>>8, len&0xFF]) + payload.encode()
# Response: b'\x00\x06200 OK'
```

### Gate HMAC
```python
username = f"{b64(uid)}@{b64(servername)}#{b64(subid)}"
key_mat  = f"{username}:{index}".encode()
hash_key = skynet_hashkey(key_mat)
hmac_val = base64(hmac64(hash_key, secret))

def skynet_hashkey(data):
    djb = 5381; js = 1315423911
    for b in data:
        djb = (djb + (djb<<5) + b) & 0xFFFFFFFF
        js  = (js ^ ((js<<5) + b + (js>>2))) & 0xFFFFFFFF
    return struct.pack('<2I', djb, js)
```

### Packet Format (Send)
```
[2 bytes: payload_size][xor_json][4 bytes: session_counter]
```

### Packet Format (Receive)
```
[2 bytes: size][xor_payload][1 byte: ok_flag][4 bytes: session]
session==0 → payload مضغوط zlib (wbits=-15)
```

### XOR Key
```python
XOR_KEY = "OSxHP.!-wd?'lao5"
```

### Command JSON Format
```json
{"cmd": "onemt_XXXX", "subcmd": "2", "data": {...}}
```

## 5. Game Commands المكتشفة

| cmd  | الاتجاه | الوصف | Data |
|------|---------|-------|------|
| 1033 | → | Port Mission (مهمة الميناء) | `{}` |
| 1037 | → | Heartbeat | `{"time": unix_ms}` |
| 1009 | ← | Server Ping | - |

**مجهولة:** هجوم، استطلاع، معلومات قلعة، تجنيد جيش

## 6. Device Constants (المحاكي)

```
Android ID:  96a6f198ca2dd6bc
OpenUDID:    CCC55D5F-AB22-404E-8CEE-EA1DF79EA9A2
DeviceID:    b511d1c73fdc4a441ff92258e301559b
SDID:        62471686-37C0-4343-BA63-0EB829162B17
Game ver:    3.34.001
Model:       sdk_gphone64_x86_64
```

## 7. الحسابات

| Email | UserID |
|-------|--------|
| azjfhf48@gmail.com | 1017d92537872288e8ddbca99fffcc90 |
| hmzawyha44@gmail.com | 0ec50d0e8c26b1a18623146e337ae24a |
| burcudemr@gmail.com | 8120e389ed552b4774dd5d8ed0c26e01 |
| king7moe1990@gmail.com | 84d85f70eff2c02970105e1f17d8272a |
| johan2003@yopmail.com | 42113187d926eb59a95f15a71e587b74 |

## 8. الملفات

| الملف | الوصف |
|-------|-------|
| `onemt_bot.py` | البوت الرئيسي |
| `extract_session_adb.py` | استخراج sessions من ADB |
| `session_cache.json` | كاش الـ sessions |
| `capture_cmds.js` | Frida - التقاط أوامر |
| `Dockerfile` + `docker-compose.yml` | نشر VPS |

## 9. ما تبقى مجهولاً

1. **isUC=true sign** — المفتاح في libdaemonutil.so
2. **أوامر gate:** هجوم، استطلاع، معلومات قلعة
3. **HTTP login endpoint** — المسار الدقيق على apiuc.menaapp.net
4. **مدة صلاحية session** — غير محددة

## 10. إضافة أمر جديد

```python
# 1. في GateBot class:
def attack_city(self, x, y, troops):
    self.send_cmd("XXXX", "2", {"x": x, "y": y, "count": troops})

# 2. في recv_loop:
elif cmd == "XXXX":
    result = c.get('data', {})
    log.info(f"Attack result: {result}")
```
