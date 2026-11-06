# -*- coding: utf-8 -*-
"""
live_sniffer.py — مراقب الحزم المباشر الاحترافي (انتقام السلاطين)
============================================================
يعرض كل الطلبات الصادرة [SEND] والردود الواردة [RECV] بشكل فوري ومقروء كـ JSON صريح
شاملاً حقول cmd و subcmd و data تماماً وبشكل حقيقي 100% بدون أي تشويه أو تزوير.

الاستخدام:
  python live_sniffer.py
  python live_sniffer.py --all         # إظهار نبض الاتصال الدوري (cmd 1037)
  python live_sniffer.py --notify      # إظهار كافة إشعارات السيرفر التلقائية RECV NOTIFY
  python live_sniffer.py --filter 1005 # تصفية أوامر محددة
"""

import socket
import subprocess
import struct
import json
import zlib
import base64
import sys
import os
import time
import argparse
import threading
from Crypto.Cipher import DES

try:
    import frida
    HAS_FRIDA = True
except ImportError:
    HAS_FRIDA = False

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── إعدادات وبروتوكول اللعبة ──
GATE_PORT        = 4060
BRIDGE_PORT      = 19876
HIDDEN_DEFAULT   = {'1037'}
XOR_KEY_BYTES    = b"OSxHP.!-wd?'lao5"
CMD_PREFIX       = "onemt_"

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
LOG_FILE         = os.path.join(SCRIPT_DIR, "sniffer_log.txt")
KEY_FILE         = os.path.join(SCRIPT_DIR, "des_key.bin")

KEY_SEARCH_PATHS = [
    KEY_FILE,
    os.path.join(os.path.dirname(SCRIPT_DIR), "core", "des_key.bin"),
    os.path.join(SCRIPT_DIR, "core", "des_key.bin"),
    r"E:\intqam-sultan\core\des_key.bin",
    r"E:\osmanli\des_key.bin",
    r"D:\osmanli\des_key.bin",
    r"C:\Users\Computer Home\Desktop\des_key.bin"
]

FALLBACK_KEY = bytes.fromhex("156ebeae9f679e0c")

# ── المتغيرات العامة ──
log_f            = None
send_counter     = 0
recv_counter     = 0
session_map      = {}   # session_id -> send_number
ACTIVE_DES_KEY   = None
DETECTED_PORTS   = {4060, 4012}
filter_cmds      = set()
show_all         = False
show_notify      = False
ADB_DEVICE       = "emulator-5554"


def _load_des_key() -> bytes:
    global ACTIVE_DES_KEY
    for kp in KEY_SEARCH_PATHS:
        if os.path.exists(kp):
            try:
                with open(kp, "rb") as f:
                    k = f.read()
                    if len(k) == 8 and len(set(k)) >= 4:
                        ACTIVE_DES_KEY = k
                        return k
            except Exception:
                pass
    if not ACTIVE_DES_KEY:
        ACTIVE_DES_KEY = FALLBACK_KEY
        try:
            with open(KEY_FILE, "wb") as f:
                f.write(FALLBACK_KEY)
        except Exception:
            pass
    return ACTIVE_DES_KEY

ACTIVE_DES_KEY = _load_des_key()


def out(text: str):
    print(text, flush=True)
    if log_f:
        try:
            log_f.write(text + '\n')
            log_f.flush()
        except Exception:
            pass


def get_adb_device() -> str:
    """اكتشاف المحاكي المتصل تلقائياً مع تفضيل emulator-5554"""
    try:
        res = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
        lines = [line.split()[0] for line in res.stdout.splitlines()[1:] if '\tdevice' in line]
        for dev in lines:
            if '5554' in dev:
                return dev
        if lines:
            return lines[0]
    except Exception:
        pass
    return "emulator-5554"


def get_game_pid(serial: str):
    """جلب معرّف عملية اللعبة الحقيقي ديناميكياً"""
    try:
        cmd = f"adb -s {serial} shell pidof and.onemt.war.ar"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        out_str = res.stdout.strip()
        if out_str:
            return int(out_str.split()[0])
    except Exception:
        pass
    return None


def detect_game_connection(serial: str, pid: int) -> list:
    """فحص المنافذ الحقيقية المرتبطة باللعبة فوراً"""
    ports = []
    try:
        cmd = f"adb -s {serial} shell su -c 'cat /proc/{pid}/net/tcp'"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3.0)
        for line in res.stdout.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 4 and parts[3] == '01': # TCP_ESTABLISHED
                rem_addr = parts[2]
                if ':' in rem_addr:
                    port_hex = rem_addr.split(':')[1]
                    p = int(port_hex, 16)
                    if p not in (53, 80, 443, 853, BRIDGE_PORT):
                        ports.append(p)
    except Exception:
        pass
    return ports


def is_gate_port(p: int) -> bool:
    return p in DETECTED_PORTS or p in (GATE_PORT, 4012, 4060) or (4000 <= p <= 4350)


def show_box(direction: str, num: int, session: int, cmd: str, sub: str, err: str, tag: str, payload_dict: dict):
    arrow = '>>>' if direction == 'SEND' else '<<<'
    err_s = f" err={err}" if err and err != '0' else ''
    sess_s = f" session={session}" if session is not None else ''
    cmd_s = f" cmd={cmd}" if cmd else ''
    sub_s = f" subcmd={sub}" if sub else ''

    out(f"\n{'='*56}")
    out(f"  {arrow} #{num}{sess_s}{cmd_s}{sub_s}{err_s} [{tag}]")
    out(f"{'='*56}")
    if isinstance(payload_dict, dict):
        out(json.dumps(payload_dict, ensure_ascii=False, indent=2))
    else:
        out(str(payload_dict))


def xor_bytes(data: bytes, key: bytes = XOR_KEY_BYTES) -> bytes:
    """فك وتشفير XOR بالمفتاح الثابت المعتمد في اللعبة"""
    k_len = len(key)
    return bytes(b ^ key[i % k_len] for i, b in enumerate(data))


def try_decompress(raw: bytes) -> bytes:
    """فك ضغط ZLIB بمختلف ترويسات deflate و gzip"""
    for w in (-15, 15, 31, 47, 32):
        try:
            return zlib.decompress(raw, w)
        except Exception:
            pass
    return raw


def clean_json_dict(d: dict) -> dict:
    """تنظيف وتنسيق معرّفات الأوامر لإزالة بادئة onemt_ تماماً كما في العثمانية"""
    if not isinstance(d, dict):
        return d
    res = {}
    for k, v in d.items():
        if k == 'cmd' and isinstance(v, str):
            res[k] = v.replace(CMD_PREFIX, '')
        elif k == 'subcmd' and isinstance(v, (int, str)):
            res[k] = str(v)
        elif isinstance(v, dict):
            res[k] = clean_json_dict(v)
        else:
            res[k] = v
    return res


def _try_decrypt_des_str(ct_str: str) -> any:
    """فك تشفير سلسلة Base64 مشفرة بـ DES واستخراج كائن JSON بأمان دون تشويه UTF-8"""
    global ACTIVE_DES_KEY
    if not ct_str or not isinstance(ct_str, str):
        return None
    key = ACTIVE_DES_KEY or _load_des_key()
    if not key or len(key) != 8:
        return None
    try:
        raw_ct = base64.b64decode(ct_str)
        if len(raw_ct) % 8 == 0:
            cipher = DES.new(key, DES.MODE_ECB)
            pt = cipher.decrypt(raw_ct)
            # استخراج محتوى JSON بين أول { وآخر } لتجنب قص الأحرف العربية بواسطة unpad العشوائي
            s_idx = pt.find(b'{')
            e_idx = pt.rfind(b'}')
            if s_idx != -1 and e_idx != -1 and e_idx >= s_idx:
                parsed = json.loads(pt[s_idx:e_idx+1].decode('utf-8', errors='replace'))
                if isinstance(parsed, dict):
                    return clean_json_dict(parsed)
    except Exception:
        pass
    return None


def extract_json(raw: bytes) -> dict:
    """استخراج كائن JSON من بيانات بايتية سواء كانت صريحة أو مضغوطة"""
    if not raw:
        return None
    for cand in (raw, try_decompress(raw)):
        s_idx = cand.find(b'{')
        e_idx = cand.rfind(b'}')
        if s_idx != -1 and e_idx != -1 and e_idx >= s_idx:
            try:
                slice_str = cand[s_idx:e_idx+1].decode('utf-8', errors='replace')
                parsed = json.loads(slice_str)
                if isinstance(parsed, dict):
                    # فك تشفير حقل data الداخلي إذا كان مشفراً بـ DES
                    inner_d = parsed.get('data')
                    if isinstance(inner_d, str) and len(inner_d) > 8:
                        dec = _try_decrypt_des_str(inner_d)
                        if dec is not None:
                            parsed['data'] = dec
                    return clean_json_dict(parsed)
            except Exception:
                pass
    return None


def decode_send_payload(body: bytes) -> dict:
    """
    فك تشفير الطلب الصادر الحقيقي من اللعبة:
    1. تشفير XOR الرسمي بمفتاح OSxHP.!-wd?'lao5 (الأصل في 99.9% من أوامر اللعبة)
    2. نص JSON صريح
    3. تشفير XOR مع ضغط ZLIB
    4. تشفير DES-ECB بترميز Base64
    5. تشفير DES-ECB بايتات خام
    """
    global ACTIVE_DES_KEY
    if not body:
        return None

    # 1. فك تشفير XOR الرسمي المباشر
    try:
        de_xor = xor_bytes(body)
        parsed = extract_json(de_xor)
        if parsed and ('cmd' in parsed or 'subcmd' in parsed or 'data' in parsed):
            return parsed
    except Exception:
        pass

    # 2. إذا كان نص JSON صريحاً بالفعل
    parsed = extract_json(body)
    if parsed and ('cmd' in parsed or 'subcmd' in parsed or 'data' in parsed):
        return parsed

    # 3. فك تشفير DES-ECB عبر Base64
    key = ACTIVE_DES_KEY or _load_des_key()
    if key and len(key) == 8:
        try:
            raw_ct = base64.b64decode(body)
            if len(raw_ct) % 8 == 0:
                cipher = DES.new(key, DES.MODE_ECB)
                pt = cipher.decrypt(raw_ct)
                parsed = extract_json(pt)
                if parsed and ('cmd' in parsed or 'subcmd' in parsed or 'data' in parsed):
                    return parsed
        except Exception:
            pass

        # 4. فك تشفير DES-ECB المباشر للبايتات الخام
        try:
            if len(body) % 8 == 0:
                cipher = DES.new(key, DES.MODE_ECB)
                pt = cipher.decrypt(body)
                parsed = extract_json(pt)
                if parsed and ('cmd' in parsed or 'subcmd' in parsed or 'data' in parsed):
                    return parsed
        except Exception:
            pass

    return None


def decode_recv_frame(frame: bytes) -> tuple:
    """
    فك إطار الرد الوارد من السيرفر:
    الصيغة القياسية: [Body] + [1 byte _ok] + [4 bytes Session Big-Endian]
    أو صيغة الإشعارات: [Body] + [4 bytes Session Big-Endian]
    """
    session = 0
    ok = True
    body = frame

    if len(frame) >= 5:
        cand_ok = frame[-5]
        cand_session = struct.unpack('>I', frame[-4:])[0]
        cand_body = frame[:-5]
        parsed = extract_json(cand_body)
        if not parsed:
            # تجربة فك XOR
            parsed = extract_json(xor_bytes(cand_body))
        if parsed:
            return parsed, cand_session, (cand_ok != 0)

    if len(frame) >= 4:
        cand_session = struct.unpack('>I', frame[-4:])[0]
        cand_body = frame[:-4]
        parsed = extract_json(cand_body)
        if not parsed:
            parsed = extract_json(xor_bytes(cand_body))
        if parsed:
            return parsed, cand_session, True

    parsed = extract_json(frame)
    if not parsed:
        parsed = extract_json(xor_bytes(frame))
    return parsed, session, ok


def start_frida_worker(serial: str):
    """هوك Frida لالتقاط مفتاح DES ديناميكياً من الذاكرة إذا توفرت"""
    global ACTIVE_DES_KEY
    if not HAS_FRIDA:
        return

    def _worker():
        while True:
            try:
                pid = get_game_pid(serial)
                if not pid:
                    time.sleep(2)
                    continue

                frida_code = """
                (function() {
                    var pattern = '08 00 00 00 ?? ?? ?? ?? ?? ?? ?? ?? 00';
                    var heapRanges = Process.enumerateRanges('rw-');
                    var keyFound = false;
                    heapRanges.forEach(function(region) {
                        if (keyFound) return;
                        if (region.size < 4096 || region.size > 8*1024*1024) return;
                        if (region.base.compare(ptr('0x10000000')) < 0) return;
                        try {
                            Memory.scan(region.base, region.size, pattern, {
                                onMatch: function(addr, sz) {
                                    if (keyFound) return;
                                    try {
                                        var kb = addr.add(4).readByteArray(8);
                                        var arr = new Uint8Array(kb);
                                        var uniq = new Set(Array.from(arr)).size;
                                        if (uniq >= 4) {
                                            send({type:'KEY_CAND'}, kb);
                                        }
                                    } catch(e) {}
                                },
                                onError: function() {},
                                onComplete: function() {}
                            });
                        } catch(e) {}
                    });
                })();
                """
                dev = frida.get_device_manager().get_device(serial)
                session = dev.attach(pid)
                scr = session.create_script(frida_code)

                def _on_frida(msg, data):
                    p = msg.get('payload', {})
                    t = p.get('type', '')
                    if t == 'KEY_CAND' and data:
                        raw8 = bytes(data)
                        global ACTIVE_DES_KEY
                        if len(raw8) == 8 and len(set(raw8)) >= 4 and raw8 != ACTIVE_DES_KEY:
                            ACTIVE_DES_KEY = raw8
                            try:
                                with open(KEY_FILE, "wb") as f:
                                    f.write(raw8)
                            except Exception:
                                pass
                            out(f"\n[KEY] *** تم اعتماد مفتاح DES النشط: {raw8.hex()} ***")

                scr.on('message', _on_frida)
                scr.load()

                while True:
                    time.sleep(3)
                    if get_game_pid(serial) != pid:
                        break
            except Exception:
                time.sleep(3)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def start_stream_bridge(serial: str, detected_ports: list = None):
    """تأسيس جسر TCP مباشر مع الأندرويد لنقل الحزم دون أي تأخير"""
    subprocess.run(f"adb -s {serial} reverse tcp:{BRIDGE_PORT} tcp:{BRIDGE_PORT}", shell=True, check=True, stdout=subprocess.DEVNULL)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', BRIDGE_PORT))
    server.listen(1)

    ports = set(detected_ports or [])
    ports.add(GATE_PORT)
    ports.add(4012)
    ports.add(4060)
    ports.discard(853)
    ports.discard(53)

    port_filter = " or ".join(f"port {p}" for p in sorted(ports))

    cmd = f"adb -s {serial} shell \"su -c 'tcpdump -i any -l -U -s 0 -w - {port_filter} 2>/dev/null | toybox nc 127.0.0.1 {BRIDGE_PORT}'\""
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    server.settimeout(12.0)
    try:
        conn, addr = server.accept()
    except socket.timeout:
        proc.kill()
        server.close()
        raise TimeoutError("فشل الاتصال بالمحاكي! تأكد من تشغيل المحاكي وصلاحيات Root.")

    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    server.close()
    return conn, proc


def read_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionResetError("Stream closed by bridge")
        buf.extend(chunk)
    return bytes(buf)


def main():
    global log_f, send_counter, recv_counter, filter_cmds, show_all, show_notify, ADB_DEVICE, GATE_PORT, ACTIVE_DES_KEY, DETECTED_PORTS

    parser = argparse.ArgumentParser(description="مراقب الحزم المباشر الاحترافي (انتقام السلاطين)")
    parser.add_argument('--all', action='store_true', help='عرض كافة الحزم بما فيها نبض الاتصال الدوري (cmd 1037)')
    parser.add_argument('--notify', action='store_true', help='عرض كافة إشعارات السيرفر التلقائية RECV NOTIFY')
    parser.add_argument('--filter', type=str, default="", help='تصفية أوامر محددة مفصولة بفاصلة (مثال: --filter 1004,1005)')
    parser.add_argument('--device', type=str, default="", help='معرف جهاز المحاكي (مثال: emulator-5554)')
    parser.add_argument('--port', type=int, default=GATE_PORT, help='منفذ سيرفر البوابة (افتراضي 4060)')
    parser.add_argument('--key', type=str, default="", help='تحديد مفتاح DES يدوياً بصيغة Hex (8 بايت / 16 حرف)')
    args = parser.parse_args()
    GATE_PORT = args.port

    show_all = args.all
    show_notify = args.notify
    if args.filter:
        filter_cmds = set(args.filter.split(','))

    if args.key:
        try:
            raw_k = bytes.fromhex(args.key.strip())
            if len(raw_k) == 8:
                ACTIVE_DES_KEY = raw_k
                try:
                    with open(KEY_FILE, "wb") as f:
                        f.write(raw_k)
                except Exception:
                    pass
                print(f"  [مفتاح التشفير]: تم التعيين يدوياً عبر الخيار --key ({raw_k.hex()})", flush=True)
        except Exception as e:
            print(f"  [تحذير]: تنسيق المفتاح غير صالح ({e})", flush=True)

    ADB_DEVICE = args.device if args.device else get_adb_device()

    log_f = open(LOG_FILE, 'w', encoding='utf-8')

    print("=" * 56, flush=True)
    print("  live_sniffer.py — مراقب حزم انتقام السلاطين المباشر", flush=True)
    print(f"  المحاكي المستهدف: {ADB_DEVICE}", flush=True)
    print(f"  السجل: {LOG_FILE}", flush=True)

    game_pid = get_game_pid(ADB_DEVICE)
    active_ports = []
    if game_pid:
        print(f"  [عملية اللعبة]: قيد التشغيل بنجاح (PID={game_pid})", flush=True)
        active_ports = detect_game_connection(ADB_DEVICE, game_pid)
        if active_ports:
            for p in active_ports:
                if p not in (53, 853):
                    DETECTED_PORTS.add(p)
            print(f"  [منافذ البوابة النشطة]: {list(DETECTED_PORTS)}", flush=True)
    else:
        print(f"  [تنبيه]: لم يتم العثور على لعبة انتقام السلاطين قيد التشغيل على {ADB_DEVICE}!", flush=True)
        print("  -> يرجى فتح اللعبة على المحاكي والدخول إلى القلعة.", flush=True)

    if ACTIVE_DES_KEY:
        print(f"  [مفتاح التشفير]: جاهز ومحمل ({ACTIVE_DES_KEY.hex()})", flush=True)
    else:
        print("  [مفتاح التشفير]: جاري التحميل التلقائي", flush=True)

    if not show_all:
        print("  [تصفية تلقائية]: حزم نبض الاتصال 1037 مخفية (استخدم --all لإظهارها)", flush=True)
    if not show_notify:
        print("  [تصفية تلقائية]: إشعارات السيرفر مخفية (استخدم --notify لإظهارها)", flush=True)
    if filter_cmds:
        print(f"  [تصفية مخصصة]: فقط الأوامر ({', '.join(filter_cmds)})", flush=True)
    print("=" * 56, flush=True)

    start_frida_worker(ADB_DEVICE)

    print("[*] جارٍ تأسيس جسر التدفق الفوري المباشر مع المحاكي...", flush=True)

    try:
        conn, proc = start_stream_bridge(ADB_DEVICE, active_ports)
    except Exception as e:
        print(f"[!] خطأ في بدء المراقب: {e}", flush=True)
        return

    print("[+] تم الاتصال بنجاح! يراقب كافة الطلبات والردود الآن...")
    print("[*] (قم بأي حركة في اللعبة: تدريب جيش، ترقية، متجر، بطل، خريطة، مهام...)")
    print("[*] اضغط Ctrl+C للإيقاف في أي وقت.\n", flush=True)

    try:
        pcap_hdr = read_exact(conn, 24)
    except Exception as e:
        print(f"[!] خطأ في قراءة ترويسة الحزم: {e}", flush=True)
        proc.kill()
        conn.close()
        return

    magic = pcap_hdr[:4]
    little_endian = (magic in (b'\xd4\xc3\xb2\xa1', b'\x4d\x3c\xb2\xa1'))
    order = '<' if little_endian else '>'

    # عزل تدفقات TCP لكل اتصال بشكل مستقل لمنع تداخل الحزم وتشويه البيانات
    stream_buffers = {}

    try:
        while True:
            hdr_raw = read_exact(conn, 16)
            ts_sec, ts_usec, incl_len, orig_len = struct.unpack(f'{order}IIII', hdr_raw)

            pkt_data = read_exact(conn, incl_len)

            if len(pkt_data) < 16 + 20 + 20:
                continue

            ip_hdr = pkt_data[16:36]
            ihl = (ip_hdr[0] & 0x0F) * 4
            proto = ip_hdr[9]
            if proto != 6: # TCP only
                continue

            src_ip = socket.inet_ntoa(ip_hdr[12:16])
            dst_ip = socket.inet_ntoa(ip_hdr[16:20])

            tcp_offset = 16 + ihl
            if len(pkt_data) < tcp_offset + 20:
                continue

            tcp_hdr = pkt_data[tcp_offset:tcp_offset+20]
            src_port, dst_port = struct.unpack('>HH', tcp_hdr[:4])
            data_offset = ((tcp_hdr[12] >> 4) & 0x0F) * 4
            payload = pkt_data[tcp_offset + data_offset:]

            if not payload:
                continue

            stream_key = (src_ip, src_port, dst_ip, dst_port)
            buf = stream_buffers.setdefault(stream_key, bytearray())
            buf.extend(payload)

            # معالجة التدفق وإعادة التجميع الآمن
            while len(buf) >= 2:
                sz = buf[0] * 256 + buf[1]
                head_len = 2
                if sz == 0xFFFF:
                    if len(buf) < 5:
                        break
                    sz = buf[2] * 65536 + buf[3] * 256 + buf[4]
                    head_len = 5

                # حماية ضد عدم المحاذاة (Resynchronization Guard)
                if sz > 1048576 or sz <= 0:
                    del buf[0]
                    continue

                total_len = head_len + sz
                if len(buf) < total_len:
                    break

                frame = bytes(buf[head_len:total_len])
                del buf[:total_len]

                # ─────────────────────────────────────────────────────────
                # 1. طلب صادر من اللعبة (SEND)
                # ─────────────────────────────────────────────────────────
                if is_gate_port(dst_port):
                    GATE_PORT = dst_port
                    if len(frame) < 4:
                        continue

                    session = struct.unpack('>I', frame[-4:])[0]
                    body = frame[:-4]
                    if not body:
                        continue

                    parsed = decode_send_payload(body)
                    cmd = str(parsed.get('cmd', '')) if parsed else ''
                    sub = str(parsed.get('subcmd', '')) if parsed else ''

                    if not show_all and cmd in HIDDEN_DEFAULT:
                        continue
                    if filter_cmds and cmd not in filter_cmds:
                        continue

                    send_counter += 1
                    if session:
                        session_map[session] = send_counter

                    show_box(
                        direction='SEND',
                        num=send_counter,
                        session=session,
                        cmd=cmd,
                        sub=sub,
                        err='',
                        tag='SEND',
                        payload_dict=parsed if parsed else {"raw": repr(body[:120])}
                    )

                # ─────────────────────────────────────────────────────────
                # 2. رد وارد من السيرفر (RECV)
                # ─────────────────────────────────────────────────────────
                elif is_gate_port(src_port):
                    GATE_PORT = src_port
                    parsed, session, ok = decode_recv_frame(frame)

                    cmd = str(parsed.get('cmd', '')) if parsed else ''
                    sub = str(parsed.get('subcmd', '')) if parsed else ''
                    err = str(parsed.get('err', '0')) if parsed else ''

                    if not show_all and cmd in HIDDEN_DEFAULT:
                        session_map.pop(session, None)
                        continue
                    if filter_cmds and cmd not in filter_cmds:
                        session_map.pop(session, None)
                        continue

                    matched_send_num = session_map.pop(session, None)
                    tag = 'RECV' if matched_send_num else 'RECV NOTIFY'

                    if not matched_send_num and not show_notify and not show_all:
                        # إخفاء الإشعارات التلقائية إذا لم يفعل المستخدم خيار --notify
                        continue

                    recv_counter += 1
                    show_box(
                        direction='RECV',
                        num=matched_send_num if matched_send_num else recv_counter,
                        session=session,
                        cmd=cmd,
                        sub=sub,
                        err=err,
                        tag=tag,
                        payload_dict=parsed if parsed else {"raw": repr(frame[:120])}
                    )

    except KeyboardInterrupt:
        print(f"\n[*] تم الإيقاف بواسطة المستخدم. تم حفظ السجل الكامل في: {LOG_FILE}", flush=True)
    except Exception as e:
        print(f"\n[!] انقطع الاتصال: {e}", flush=True)
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        if log_f:
            try:
                log_f.close()
            except Exception:
                pass


if __name__ == '__main__':
    main()
