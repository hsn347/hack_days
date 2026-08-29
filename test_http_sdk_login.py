import requests, json, time, hashlib, urllib.parse, base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

APP_ID = "100002001"
APP_KEY_STR = "d252596f076c9213dce69cdb39d488ea"
APP_SIGN_MD5 = "47965E93AD48A1D34F9EF116405AA6CF"
AES_KEY = b"55E72818A7B7DFCF"
AES_IV = b"873E53F7DC560B29"
API_URL = "https://apiuc.menaapp.net/v5/passport/login"

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

def do_login(email: str, password: str):
    device_id = hashlib.md5(email.encode('utf-8')).hexdigest()
    pwd_hash = encrypt_sdk_pwd(password)
    
    reqdata_obj = {
        "name": email,
        "password": pwd_hash,
        "identifytype": "email"
    }
    # In Gson, json of map
    reqdata_json = json.dumps(reqdata_obj, separators=(',', ':'), ensure_ascii=False)
    reqdata_encoded = urllib.parse.quote(reqdata_json, safe='')
    
    ts = str(int(time.time()))
    
    # Try different combinations of fields to see what User Center accepts
    body_map = {
        "appid": APP_ID,
        "channel": "googleplay",
        "clientversion": "5.33.0",
        "deviceid": device_id,
        "lang": "ar",
        "originalid": "",
        "packagename": "and.onemt.boe.tr",
        "platform": "android",
        "reqdata": reqdata_encoded,
        "rstatus": "0",
        "sdid": "",
        "securemode": "MD5",
        "sessionid": "",
        "timestamp": ts
    }
    
    sorted_map = {k: body_map[k] for k in sorted(body_map.keys())}
    json_to_sign = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)
    
    sign_str = json_to_sign + APP_KEY_STR + APP_SIGN_MD5
    sign_hash = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    sorted_map["sign"] = sign_hash
    
    final_json = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)
    enc_body = aes_encrypt(final_json)
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "encrypt": "1",
        "appid": APP_ID,
        "User-Agent": "okhttp/3.14.9"
    }
    
    resp = requests.post(API_URL, data=enc_body, headers=headers, timeout=10)
    print(f"[{email}] Status: {resp.status_code} | Raw: {resp.text}")

do_login("hmzawyha44@gmail.com", "pass123")
do_login("king7moe1990@gmail.com", "pass123")
