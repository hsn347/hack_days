"""
bot_engine.py
Python = المنطق + فك الضغط + عرض النتائج
Frida JS = بناء الحزمة + ارسالها + التقاط الرد (نفس طريقة simple_cmd.js)
"""
import frida, sys, json, struct, zlib, time, os, threading

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

XOR_KEY = bytes([79,83,120,72,80,46,33,45,119,100,63,39,108,97,111,53])

def xor(data):
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ XOR_KEY[i % len(XOR_KEY)]
    return bytes(out)

def decompress(raw):
    for w in (-15, 15+32, 15):
        try: return zlib.decompress(raw, w)
        except: pass
    return raw

def decode_pkt(pkt):
    if len(pkt) < 5: return None
    for trim in (5, 4):
        raw = pkt[:-trim] if trim <= len(pkt) else pkt
        for attempt in (raw, decompress(raw)):
            try:
                d = json.loads(xor(attempt))
                if isinstance(d, dict) and ('cmd' in d or 'subcmd' in d):
                    c = d.get('cmd','')
                    if c.startswith('onemt_'): d['cmd'] = c[6:]
                    return d
            except: pass
    return None

# --- Frida JS ---
# يعمل بنفس طريقة simple_cmd.js تماما
# يستقبل الامر كنص JSON من Python عبر recv
FRIDA_JS = r"""
var XOR_KEY = "OSxHP.!-wd?'lao5";
var _fd = -1, _session = 0, _started = false;
var libc = Process.getModuleByName('libc.so');

function xorEncrypt(text, key) {
    var r = []; var j = 0;
    for (var i = 0; i < text.length; i++) {
        r.push(text.charCodeAt(i) ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return r;
}

function buildPacket(cmd, subcmd, data) {
    var msg = JSON.stringify({cmd: "onemt_" + cmd, subcmd: String(subcmd), data: data});
    var enc = xorEncrypt(msg, XOR_KEY);
    var totalLen = enc.length + 4;
    var pkt = [(totalLen >> 8) & 0xFF, totalLen & 0xFF];
    pkt = pkt.concat(enc);
    pkt.push((_session >> 24) & 0xFF, (_session >> 16) & 0xFF, (_session >> 8) & 0xFF, _session & 0xFF);
    return pkt;
}

function writePkt(pkt) {
    var buf = Memory.alloc(pkt.length);
    for (var i = 0; i < pkt.length; i++) buf.add(i).writeU8(pkt[i]);
    var writeFn = new NativeFunction(libc.findExportByName('write'), 'int', ['int','pointer','int']);
    var r = writeFn(_fd, buf, pkt.length);
    if (r <= 0) {
        var sendFn = new NativeFunction(libc.findExportByName('send'), 'int', ['int','pointer','int','int']);
        r = sendFn(_fd, buf, pkt.length, 0);
    }
    return r;
}

// اكتشاف الاتصال
['write','send'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), { onEnter: function(a) {
        if (_started) return;
        var len=a[2].toInt32(), fd=a[0].toInt32();
        if (len<10||len>2000||fd<=3) return;
        try {
            if (a[1].add(2).readU8()===0x34) {
                var p=a[1].add(len-4);
                _session=((p.readU8()<<24)|(p.add(1).readU8()<<16)|(p.add(2).readU8()<<8)|p.add(3).readU8())>>>0;
                _fd=fd; _started=true;
                send({type:'ready', fd:fd, session:_session});
            }
        } catch(e){}
    }});
});

// التقاط الردود وارسالها لـ Python
['read','recv'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), {
        onEnter: function(a) { this.buf=a[1]; this.fd=a[0].toInt32(); },
        onLeave: function(r) {
            var n=r.toInt32();
            if (n<=0 || this.fd !== _fd) return;
            try {
                send({type:'data', fd:this.fd}, this.buf.readByteArray(n));
            } catch(e){}
        }
    });
});

// استقبال امر من Python
function handleCmd(msg) {
    if (!_started) {
        send({type:'err', msg:'not_ready'});
        recv('cmd', handleCmd);
        return;
    }
    try {
        _session++;
        var pkt = buildPacket(msg.cmd, msg.subcmd, msg.data || {});
        var r = writePkt(pkt);
        send({type:'sent', bytes:r, cmd:msg.cmd, subcmd:msg.subcmd});
    } catch(e) {
        send({type:'err', msg:e.message});
    }
    recv('cmd', handleCmd);
}
recv('cmd', handleCmd);
"""

class BotEngine:
    def __init__(self):
        self._ready = False
        self._fd = -1
        self._script = None
        self._recv_buf = b''
        self._pending = {}
        self._lock = threading.Lock()

    def _on_message(self, msg, data):
        if msg['type'] != 'send': return
        p = msg.get('payload', {})
        t = p.get('type','')

        if t == 'ready':
            self._fd = p['fd']
            self._ready = True
            print(f"[+] fd={self._fd} session={p['session']}")

        elif t == 'data' and data:
            self._recv_buf += bytes(data)
            self._try_parse()

        elif t == 'sent':
            pass  # نجاح الارسال

        elif t == 'err':
            print(f"[!] Frida: {p.get('msg','?')}")

    def _try_parse(self):
        buf = self._recv_buf
        while len(buf) >= 2:
            sz = buf[0]*256 + buf[1]
            head = 2
            if sz == 0xFFFF:
                if len(buf) < 5: break
                sz = buf[2]*65536 + buf[3]*256 + buf[4]
                head = 5
            if sz < 4 or sz > 200000: 
                buf = buf[1:]  # skip bad byte
                continue
            if len(buf) < head + sz: break
            pkt = buf[head:head+sz]
            buf = buf[head+sz:]
            
            d = decode_pkt(pkt)
            if d:
                sub = str(d.get('subcmd',''))
                with self._lock:
                    if sub in self._pending:
                        self._pending[sub]['result'] = d
                        self._pending[sub]['done'] = True
        self._recv_buf = buf

    def connect(self):
        device = frida.get_device_manager().get_device("emulator-5554")
        session = None
        for name in ["Empire", "and.onemt.boe.tr"]:
            try:
                session = device.attach(name)
                print(f"[+] {name}")
                break
            except: pass
        if not session:
            print("[!] game not running"); sys.exit(1)
        self._script = session.create_script(FRIDA_JS)
        self._script.on('message', self._on_message)
        self._script.load()

    def wait_ready(self, timeout=30):
        print("[*] tap screen...")
        t = time.time()
        while not self._ready and time.time()-t < timeout:
            time.sleep(0.1)
        return self._ready

    def query(self, cmd, subcmd, data=None, timeout=15):
        if not self._ready: return None
        sub = str(subcmd)
        slot = {'result': None, 'done': False}
        with self._lock:
            self._pending[sub] = slot
        
        self._script.post({'type': 'cmd', 'cmd': str(cmd), 'subcmd': sub, 'data': data or {}})
        print(f"  >> {cmd}/{subcmd}")

        t = time.time()
        while not slot['done'] and time.time()-t < timeout:
            time.sleep(0.05)
        
        with self._lock:
            self._pending.pop(sub, None)
        
        if not slot['done']:
            print(f"  !! timeout {cmd}/{subcmd}")
            return None
        print(f"  << {cmd}/{subcmd} OK")
        return slot['result']

    def send_cmd(self, cmd, subcmd, data=None):
        if not self._ready: return
        self._script.post({'type': 'cmd', 'cmd': str(cmd), 'subcmd': str(subcmd), 'data': data or {}})


# ========================================
#  EXCLUDE HISTORY (JSON)
# ========================================

HISTORY_FILE = "exclude_history.json"

def get_exclude_dict(uid):
    """جلب الأهداف المستبعدة لهذا الحساب بصيغة {'id': True}"""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            arr = data.get(str(uid), [])
            return {target_id: True for target_id in arr}
    except Exception as e:
        return {}

def add_to_exclude_history(uid, target_id):
    """إضافة الهدف الجديد لمصفوفة الحساب في ملف json (بحد أقصى 10 مع حذف الأقدم)"""
    data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
    
    uid_str = str(uid)
    if uid_str not in data:
        data[uid_str] = []
    
    arr = data[uid_str]
    if target_id not in arr:
        arr.append(target_id)
    
    # إذا تجاوز 10 عناصر، احذف الأقدم (من بداية المصفوفة)
    while len(arr) > 10:
        arr.pop(0)
    
    data[uid_str] = arr
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] خطأ في حفظ ملف exclude_history: {e}")


# ========================================
#  BOT LOGIC
# ========================================

def run_bot(bot):
    type_R = 5
    r0 = bot.query('2058', '20', {"heroId": 5501010})
    if r0:
        print(json.dumps(r0, ensure_ascii=False, indent=2)) 




if __name__ == '__main__':
    bot = BotEngine()
    bot.connect()
    if not bot.wait_ready():
        print("[!] failed"); sys.exit(1)
    
    print("[+] ready!\n")
    run_bot(bot)
    
    print("\n[*] done. Ctrl+C to exit")
    try: sys.stdin.read()
    except KeyboardInterrupt: pass
