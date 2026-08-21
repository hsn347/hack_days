"""
test_uc_login.py
اختبار تسجيل الدخول عبر UC API مباشرة من Python
يحاول إرسال طلب بتوقيع مختلف لمعرفة إذا السيرفر يتحقق منه

المعلومات المعروفة:
- Base URL: https://apiuc.menaapp.net/
- appid: 100002001
- appKey: d252596f076c9213dce69cdb39d488ea
- isUC=false sign: md5(sorted_json + appKey)
- isUC=true sign: unknown (هذا ما نختبره)
"""

import hashlib, json, time, requests, sys

APP_ID   = "100002001"
APP_KEY  = "d252596f076c9213dce69cdb39d488ea"
BASE_URL = "https://apiuc.menaapp.net"

# تحديد email + password من command line
if len(sys.argv) < 3:
    print("Usage: python test_uc_login.py EMAIL PASSWORD")
    sys.exit(1)
EMAIL    = sys.argv[1]
PASSWORD = sys.argv[2]

def md5(s): return hashlib.md5(s.encode()).hexdigest()

def make_sign_false(params: dict) -> str:
    """isUC=false sign = md5(sorted_json + appKey)"""
    j = json.dumps(params, separators=(',', ':'), sort_keys=True)
    return md5(j + APP_KEY)

def try_login(endpoint: str, params: dict, sign: str, label: str):
    """يرسل طلب login ويطبع النتيجة"""
    params_with_sign = dict(params)
    params_with_sign['sign'] = sign
    
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*50}")
    print(f"[{label}] POST {url}")
    print(f"Sign: {sign}")
    
    try:
        # محاولة 1: JSON body
        r = requests.post(url, json=params_with_sign, timeout=10,
                         headers={'Content-Type': 'application/json'})
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:500]}")
        return r
    except Exception as e:
        print(f"Error: {e}")
        
        # محاولة 2: Form body
        try:
            r = requests.post(url, data=params_with_sign, timeout=10)
            print(f"Status (form): {r.status_code}")
            print(f"Response: {r.text[:500]}")
            return r
        except Exception as e2:
            print(f"Error (form): {e2}")
    
    return None

# بناء الـ params
timestamp = str(int(time.time()))
base_params = {
    "appid": APP_ID,
    "timestamp": timestamp,
    "platform": "Android",
    "channel": "googleplay",
    "lang": "en",
    "sessionid": "",
    "securemode": "0",
}

login_reqdata = json.dumps({
    "account": EMAIL,
    "password": md5(PASSWORD),
    "type": 2,  # email login type
}, separators=(',', ':'))

full_params = dict(base_params)
full_params['reqdata'] = login_reqdata

# حساب الـ sign بالطريقة المعروفة (isUC=false)
sign_false = make_sign_false(full_params)
# توقيع وهمي
sign_dummy = "00000000000000000000000000000000"
# توقيع MD5 فارغ
sign_empty_md5 = md5("")

# قائمة الـ endpoints المحتملة للاختبار
endpoints = [
    "/v3/user/login/email",
    "/v2/user/login/email",
    "/v1/user/login/email",
    "/user/login/email",
    "/user/login",
    "/v3/user/login",
    "/v2/user/login",
]

# اختبر أول endpoint بالـ sign المعروف (isUC=false) ثم بالـ dummy
print(f"Testing UC login with email: {EMAIL}")
print(f"Base params: {base_params}")

# اختبار 1: isUC=false sign على أول endpoint
for ep in endpoints[:4]:
    r = try_login(ep, full_params, sign_false, "isUC=false sign")
    if r and r.status_code == 200:
        print(f"\n[SUCCESS] Endpoint found: {ep}")
        break
    elif r and r.status_code != 404:
        # استجابة غير 404 = endpoint موجود
        print(f"\n[ENDPOINT EXISTS] {ep} → status {r.status_code}")
        # اختبر بـ dummy sign
        try_login(ep, full_params, sign_dummy, "dummy sign")
        break
