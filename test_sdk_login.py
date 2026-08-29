import subprocess, time, json, xml.etree.ElementTree as ET

def trigger_sdk_login(email: str, password: str) -> dict:
    """
    يقوم بتسجيل الدخول للحساب عبر SDK واستخراج الـ session مباشرة
    """
    # 1. تشغيل كود مصغر عبر ADB أو Intent أو Frida لطلب loginWithEmail
    print(f"🔄 جاري تسجيل الدخول عبر الـ SDK للحساب: {email}...")
    
    # يمكننا استدعاء Login عبر Frida أو قراءة SdkEmail.xml مباشرة
    # دعنا نتحقق من محتوى SdkEmail.xml الحالي
    out = subprocess.check_output('adb shell "su -c cat /data/data/and.onemt.boe.tr/shared_prefs/SdkEmail.xml"', shell=True).decode('utf-8', 'ignore')
    print("SdkEmail.xml length:", len(out))
    return out

trigger_sdk_login("test@gmail.com", "123")
