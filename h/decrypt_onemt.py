"""
فك تشفير بروتوكول لعبة ONEMT
المفتاح: OSxHP.!-wd?'lao5
الخوارزمية: XOR + zlib
"""

import zlib
import json

# مفتاح التشفير المكتشف من gate.lua
XOR_KEY = "OSxHP.!-wd?'lao5"
CMD_PREFIX = "onemt_"

def xor_decrypt(data: bytes, key: str) -> bytes:
    """فك تشفير XOR - نفس الخوارزمية في onemtencrypt.lua"""
    key_bytes = key.encode('utf-8')
    key_len = len(key_bytes)
    result = bytearray(len(data))
    j = 0
    for i, byte in enumerate(data):
        result[i] = byte ^ key_bytes[j]
        j += 1
        if j >= key_len:
            j = 0
    return bytes(result)

def xor_encrypt(data: str, key: str) -> bytes:
    """تشفير XOR - لإرسال الأوامر"""
    return xor_decrypt(data.encode('utf-8'), key)

def pack_request(msg: dict, session: int = 1) -> bytes:
    """
    بناء رسالة للإرسال (مثل gate:pack_request في Lua)
    البنية: [2 بايت طول] [بيانات XOR] [4 بايت session]
    """
    # إضافة prefix للأمر
    msg = dict(msg)
    if 'cmd' in msg:
        msg['cmd'] = CMD_PREFIX + msg['cmd']
    
    text = json.dumps(msg, ensure_ascii=False, separators=(',', ':'))
    xor_text = xor_encrypt(text, XOR_KEY)
    
    size = len(xor_text) + 4  # +4 للـ session
    
    # 2 بايت للحجم (Big-Endian)
    header = bytes([(size >> 8) & 0xFF, size & 0xFF])
    
    # 4 بايت للـ session
    session_bytes = bytes([
        (session >> 24) & 0xFF,
        (session >> 16) & 0xFF,
        (session >> 8) & 0xFF,
        session & 0xFF
    ])
    
    return header + xor_text + session_bytes

def unpack_response(data: bytes) -> dict:
    """
    فك تعبئة رد السيرفر (مثل gate:S2C_RESPONSE في Lua)
    البنية: [محتوى] [1 بايت ok] [4 بايت session]
    """
    # استخراج الـ session (آخر 4 بايت)
    session = 0
    for i in range(4, 0, -1):
        session = (session << 8) | data[-i]
    
    # البايت قبل الأخير 4 هو ok flag
    ok = data[-5]
    
    # المحتوى هو كل شيء قبل آخر 5 بايت
    content_encrypted = data[:-5]
    
    if not ok:
        return {'error': 'response not ok', 'session': session}
    
    # فك الضغط zlib إذا كان session == 0
    if session == 0:
        try:
            content_encrypted = zlib.decompress(content_encrypted, -zlib.MAX_WBITS)
        except:
            try:
                content_encrypted = zlib.decompress(content_encrypted)
            except:
                pass
    
    # فك تشفير XOR
    content_decrypted = xor_decrypt(content_encrypted, XOR_KEY)
    
    try:
        content = json.loads(content_decrypted)
        # إزالة prefix من الأمر
        if isinstance(content, dict) and 'cmd' in content:
            cmd = content['cmd']
            if cmd.startswith(CMD_PREFIX):
                content['cmd'] = cmd[len(CMD_PREFIX):]
        return {'ok': True, 'content': content, 'session': session}
    except Exception as e:
        return {'ok': True, 'raw': content_decrypted.decode('utf-8', errors='replace'), 'session': session, 'error': str(e)}

def unpack_package(data: bytes):
    """
    استخراج حزمة من البيانات الخام (مثل gate:unpack_package في Lua)
    يرجع (محتوى_الحزمة, باقي_البيانات)
    """
    if len(data) < 2:
        return None, data
    
    head_size = 2
    s = data[0] * 256 + data[1]
    
    # حزمة كبيرة - header 5 بايت
    if s == 65535:
        head_size = 5
        if len(data) < head_size:
            return None, data
        s = data[2] * 65536 + data[3] * 256 + data[4]
    
    if len(data) < s + head_size:
        return None, data  # لم تكتمل الحزمة
    
    package = data[head_size:head_size + s]
    remaining = data[head_size + s:]
    return package, remaining

# ===== اختبار فك التشفير مع البيانات التي سجلناها =====
if __name__ == "__main__":
    print("=== اختبار فك تشفير ONEMT ===\n")
    
    # بيانات إرسال الجيش التي التقطناها من Frida
    captured_hex_march = "01 80 34 71 1b 25 34 0c 1b 0f 18 0a 5a 4a 18 3e 5e 05 7f 64 5a 64 72 5d 54 4f 14 09 5b 05 56 43 5d 17 63 71 1c 29 24 4f 03 17 0c 46 51 42 09 05 3c 50 21 37 5a 72 36 4f 4d 5e 12 48 1d 55 19 0f 0a 65 2e 34 1d 3b 72 14 5a 50 5b 46 57 42 1e 0e"
    
    captured_hex_port = "00 2f 34 71 1b 25 34 0c 1b 0f 18 0a 5a 4a 18 3e 5e 05 7c 60 5a 64 72 5d 54 4f 14 09 5b 05 56 43 5d 17 63 71 1c 29 24 4f 03 17 0c 19 42 00 00 01 dc"
    
    def decode_frida_capture(hex_str: str, label: str):
        print(f"--- {label} ---")
        raw = bytes(int(x, 16) for x in hex_str.strip().split())
        print(f"الحجم الكلي: {len(raw)} بايت")
        print(f"الـ Header: {raw[0]:02x} {raw[1]:02x} (size={raw[0]*256+raw[1]})")
        
        # البيانات بعد الـ header الأول (2 بايت)
        # تذكر: الـ header الخارجي مضاف بواسطة SocketTCP
        # الـ header الداخلي (pack_request): 2 بايت حجم + XOR data + 4 بايت session
        inner = raw[2:]  # نزيل أول 2 بايت (header SocketTCP الخارجي)
        
        if len(inner) < 6:
            print("حزمة صغيرة جداً")
            return
        
        # آخر 4 بايت = session
        session = (inner[-4] << 24) | (inner[-3] << 16) | (inner[-2] << 8) | inner[-1]
        xor_data = inner[:-4]
        
        print(f"Session: {session} (0x{session:08x})")
        
        # فك XOR
        decrypted = xor_decrypt(xor_data, XOR_KEY)
        try:
            msg = json.loads(decrypted)
            if 'cmd' in msg:
                cmd = msg['cmd']
                if cmd.startswith(CMD_PREFIX):
                    msg['cmd'] = cmd[len(CMD_PREFIX):]
            print(f"الرسالة المفككة:")
            print(json.dumps(msg, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"النص الخام: {decrypted.decode('utf-8', errors='replace')}")
            print(f"خطأ: {e}")
        print()
    
    decode_frida_capture(captured_hex_march, "إرسال جيش")
    decode_frida_capture(captured_hex_port, "مهمة الميناء")
    
    # مثال على بناء رسالة للإرسال
    print("--- مثال: بناء رسالة إرسال جيش ---")
    test_msg = {
        "cmd": "army_march",
        "uid": 12345,
        "target_x": 100,
        "target_y": 200,
        "troops": {"soldier": 1000}
    }
    packed = pack_request(test_msg, session=1)
    print(f"الرسالة المشفرة ({len(packed)} بايت):")
    print(' '.join(f'{b:02x}' for b in packed))
