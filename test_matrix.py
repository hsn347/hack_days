import requests, json, time, hashlib, urllib.parse, base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

APP_KEY_STR = "d252596f076c9213dce69cdb39d488ea"
APP_SIGN_MD5 = "47965E93AD48A1D34F9EF116405AA6CF"
AES_KEY = b"55E72818A7B7DFCF"
AES_IV = b"873E53F7DC560B29"

def encrypt_sdk_pwd(pwd: str) -> str:
    inner = hashlib.md5(f"gqY6DBt{pwd}Oed76U0".encode('utf-8')).hexdigest()
    return hashlib.md5(inner.encode('utf-8')).hexdigest()

def aes_encrypt(plain_text: str) -> str:
    data = plain_text.encode('utf-8')
    pad_len = 16 - (len(data) % 16)
    data += bytes([pad_len] * pad_len)
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV), backend=default_backend()).encryptor()
    ct = cipher.update(data) + cipher.finalize()
    return base64.b64encode(ct).decode('utf-8')

def aes_decrypt(cipher_b64: str) -> str:
    ct = base64.b64decode(cipher_b64)
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV), backend=default_backend()).decryptor()
    plain = cipher.update(ct) + cipher.finalize()
    pad_len = plain[-1]
    return plain[:-pad_len].decode('utf-8')

def try_request(url, appid, clientver, lang, is_enc, send_encrypted_body):
    email = "zzoro8290@gmail.com"
    pwd = "123456"
    device_id = hashlib.md5(email.encode('utf-8')).hexdigest()
    pwd_hash = encrypt_sdk_pwd(pwd)
    
    reqdata_obj = {
        "name": email,
        "password": pwd_hash,
        "identifytype": "email"
    }
    reqdata_json = json.dumps(reqdata_obj, separators=(',', ':'), ensure_ascii=False)
    reqdata_encoded = urllib.parse.quote(reqdata_json, safe='')
    
    ts = str(int(time.time()))
    body_map = {
        "platform": "android",
        "appid": appid,
        "timestamp": ts,
        "packagename": "and.onemt.boe.tr",
        "lang": lang,
        "sdid": "",
        "channel": "googleplay",
        "rstatus": "0",
        "clientversion": clientver,
        "sessionid": "",
        "originalid": "",
        "deviceid": device_id,
        "reqdata": reqdata_encoded,
        "securemode": "MD5"
    }
    
    sorted_map = {k: body_map[k] for k in sorted(body_map.keys())}
    json_to_sign = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)
    
    if is_enc:
        sign_str = json_to_sign + APP_KEY_STR + APP_SIGN_MD5
    else:
        sign_str = json_to_sign + APP_KEY_STR
    sign_hash = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    sorted_map["sign"] = sign_hash
    
    final_json = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "appid": appid,
        "User-Agent": "okhttp/3.14.9"
    }
    if send_encrypted_body:
        headers["encrypt"] = "1"
        data = aes_encrypt(final_json)
    else:
        data = final_json
        
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=5)
        raw = resp.text.strip()
        dec = ""
        if not raw.startswith('{'):
            try:
                dec = " -> Decrypted: " + aes_decrypt(raw)
            except:
                dec = " -> Decrypt failed"
        print(f"[{appid}|{clientver}|enc_body={send_encrypted_body}|sign_enc={is_enc}] => {resp.status_code}: {raw[:70]}{dec}")
    except Exception as e:
        print(f"Err: {e}")

urls = [
    "https://apiuc.menaapp.net/v5/passport/login",
    "https://apiuc.menaapp.net/v5/core/login",
    "https://apiuc.menaapp.net/v3/channel/login"
]

for u in urls:
    print(f"\n--- Testing URL: {u} ---")
    for aid in ["100002001", "100002"]:
        for cver in ["5.33.0"]:
            for send_enc in [True, False]:
                for sign_enc in [True, False]:
                    try_request(u, aid, cver, "ar", sign_enc, send_enc)
