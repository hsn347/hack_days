import requests, json, time, hashlib, urllib.parse

APP_ID = "100002001"
APP_KEY_STR = "d252596f076c9213dce69cdb39d488ea"
APP_SIGN_MD5 = "47965E93AD48A1D34F9EF116405AA6CF"
API_URL = "https://apiuc.menaapp.net/v5/passport/login"

def encrypt_sdk_pwd(pwd: str) -> str:
    """خوارزمية تشفير كلمة المرور الخاصة بشركة ONEMT SDK"""
    inner = hashlib.md5(f"gqY6DBt{pwd}Oed76U0".encode('utf-8')).hexdigest()
    return hashlib.md5(inner.encode('utf-8')).hexdigest()

def sdk_login(email: str, password: str, device_id: str = None) -> dict:
    """
    تسجيل الدخول المباشر إلى خوادم اللعبة عبر الإيميل وكلمة المرور فقط
    بدون الحاجة لمحاكي أو فريدا أو فتح اللعبة
    """
    if not device_id:
        device_id = hashlib.md5(email.encode('utf-8')).hexdigest()
        
    pwd_hash = encrypt_sdk_pwd(password)
    
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
        "appid": APP_ID,
        "timestamp": ts,
        "packagename": "and.onemt.boe.tr",
        "lang": "ar",
        "sdid": "",
        "channel": "googleplay",
        "rstatus": "0",
        "clientversion": "5.33.0",
        "sessionid": "",
        "originalid": "",
        "deviceid": device_id,
        "reqdata": reqdata_encoded,
        "securemode": "MD5"
    }
    
    sorted_map = {k: body_map[k] for k in sorted(body_map.keys())}
    json_to_sign = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)
    
    sign_str = json_to_sign + APP_KEY_STR + APP_SIGN_MD5
    sign_hash = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    sorted_map["sign"] = sign_hash
    
    final_json = json.dumps(sorted_map, separators=(',', ':'), ensure_ascii=False)
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "appid": APP_ID,
        "User-Agent": "okhttp/3.14.9"
    }
    
    resp = requests.post(API_URL, data=final_json, headers=headers, timeout=10)
    try:
        data = resp.json()
        rtncode = data.get('rtncode', '')
        if rtncode in ('0', '00000', 'SUCCESS', 0):
            # Parse rspdata if string
            rspdata = data.get('rspdata')
            if isinstance(rspdata, str) and rspdata:
                rspdata = json.loads(urllib.parse.unquote(rspdata))
            return {
                "success": True,
                "userId": rspdata.get('userid') or rspdata.get('userId'),
                "sessionId": rspdata.get('sessionid') or rspdata.get('sessionId'),
                "raw": data
            }
        else:
            return {
                "success": False,
                "error_code": rtncode,
                "error_msg": data.get('rtnmsg', 'Login failed'),
                "raw": data
            }
    except Exception as e:
        return {
            "success": False,
            "error_msg": f"JSON parse error: {e}",
            "raw": resp.text
        }

if __name__ == "__main__":
    print("Testing SDK Login with wrong pwd:")
    res = sdk_login("zzoro8290@gmail.com", "wrongpassword123")
    print(json.dumps(res, ensure_ascii=False, indent=2))
