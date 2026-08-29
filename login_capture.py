"""
login_capture.py
التقاط بيانات الأبطال والبيانات المهمة
يعمل مع اللعبة المفتوحة بدون إعادة تشغيل

الطريقة: يتصل بالعملية عبر Frida → يرسل أوامر التهيئة → يلتقط كل الردود والإشعارات
مؤسس ليعمل لاحقاً عبر onemt_bot.py بنفس المنطق
"""
import frida, sys, json, zlib, time, os, threading

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

# === Frida JS — يتصل + يرسل + يلتقط ===
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

// التقاط الردود
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

// استقبال أمر من Python
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


class DataCapture:
    """يلتقط كل الحزم الواردة ويصنفها"""
    def __init__(self):
        self._recv_buf = b''
        self._packets = []
        self._ready = False
        self._script = None
        self._count = 0
        self._lock = threading.Lock()
    
    def _on_message(self, msg, data):
        if msg['type'] != 'send': return
        p = msg.get('payload', {})
        t = p.get('type','')
        
        if t == 'ready':
            self._ready = True
            print(f"[+] fd={p['fd']} session={p.get('session','?')}")
        elif t == 'data' and data:
            with self._lock:
                self._recv_buf += bytes(data)
                self._parse()
        elif t == 'sent':
            print(f"  >> {p.get('cmd')}/{p.get('subcmd')}")
        elif t == 'err':
            print(f"  [!] {p.get('msg','?')}")
    
    def _parse(self):
        buf = self._recv_buf
        while len(buf) >= 2:
            sz = buf[0]*256 + buf[1]
            head = 2
            if sz == 0xFFFF:
                if len(buf) < 5: break
                sz = buf[2]*65536 + buf[3]*256 + buf[4]
                head = 5
            if sz < 4 or sz > 500000:
                buf = buf[1:]
                continue
            if len(buf) < head + sz: break
            pkt = buf[head:head+sz]
            buf = buf[head+sz:]
            
            d = decode_pkt(pkt)
            if d:
                self._count += 1
                self._packets.append(d)
                cmd = d.get('cmd','?')
                sub = d.get('subcmd','?')
                data_obj = d.get('data', {})
                
                # تمييز الحزم المهمة
                tag = ''
                if isinstance(data_obj, dict):
                    keys = list(data_obj.keys())
                    notify_id = data_obj.get('notifyID', '')
                    if 'heroCtrl' in keys: tag = ' >>> HERO_CTRL'
                    elif notify_id == 'NOTIFY_HERO': tag = ' >>> NOTIFY_HERO'
                    elif 'hero' in str(keys).lower(): tag = ' > hero'
                    
                    size = len(json.dumps(d, ensure_ascii=False))
                    print(f"  << #{self._count} [{cmd}/{sub}] {size/1024:.1f}KB {notify_id or keys[:5]}{tag}")
                else:
                    print(f"  << #{self._count} [{cmd}/{sub}]{tag}")
        
        self._recv_buf = buf
    
    def send_cmd(self, cmd, subcmd, data=None):
        if not self._ready: return
        self._script.post({'type': 'cmd', 'cmd': str(cmd), 'subcmd': str(subcmd), 'data': data or {}})
    
    def save_results(self):
        """حفظ كل النتائج — نفس البنية التي سيستخدمها onemt_bot.py لاحقاً"""
        # 1) حفظ كل الحزم الخام
        with open('captured_packets.json', 'w', encoding='utf-8') as f:
            json.dump(self._packets, f, ensure_ascii=False, indent=2)
        
        # 2) تصنيف البيانات (نفس بنية castle_data في onemt_bot.py)
        castle_data = {}
        hero_packets = []
        
        for pkt in self._packets:
            cmd = pkt.get('cmd','')
            sub = str(pkt.get('subcmd',''))
            data = pkt.get('data', {})
            
            if not isinstance(data, dict): continue
            
            # إشعارات (1009)
            if cmd == '1009':
                notify_id = data.get('notifyID', '')
                notify_data = data.get('notifyData', [])
                if notify_id:
                    castle_data[notify_id] = notify_data
                    if notify_id == 'NOTIFY_HERO':
                        hero_packets.append(pkt)
            
            # بيانات تسجيل الدخول (1000)
            elif cmd == '1000':
                if 'heroCtrl' in data:
                    castle_data['heroCtrl'] = data['heroCtrl']
                    hero_packets.append(('heroCtrl', data['heroCtrl']))
                # حفظ كل مفاتيح الـ init
                for key in data:
                    castle_data[f'_init_{key}'] = data[key]
            
            # بيانات الجيش (1005)
            elif cmd == '1005':
                castle_data[f'_army_{sub}'] = data
            
            # بيانات الأبطال (2058)
            elif cmd == '2058':
                hero_packets.append(pkt)
                castle_data[f'_hero_{sub}'] = data
            
            # أي أمر آخر
            else:
                castle_data[f'_cmd_{cmd}_{sub}'] = data
        
        # حفظ البيانات المصنفة
        with open('game_data_captured.json', 'w', encoding='utf-8') as f:
            json.dump(castle_data, f, ensure_ascii=False, indent=2)
        
        # حفظ بيانات الأبطال تحديداً
        if hero_packets:
            with open('hero_data_captured.json', 'w', encoding='utf-8') as f:
                json.dump(hero_packets, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n[+] hero data: {len(hero_packets)} sets -> hero_data_captured.json")
        
        print(f"[+] all data: {len(castle_data)} keys -> game_data_captured.json")
        print(f"[+] raw packets: {len(self._packets)} -> captured_packets.json")
        
        return castle_data


def main():
    device = frida.get_device_manager().get_device("emulator-5554")
    cap = DataCapture()
    
    print("=" * 50)
    print("  DATA CAPTURE (no restart)")
    print("=" * 50)
    
    # الاتصال باللعبة المفتوحة
    session = None
    for name in ["Empire", "and.onemt.boe.tr"]:
        try:
            session = device.attach(name)
            print(f"[+] attached to {name}")
            break
        except: pass
    
    if not session:
        print("[!] game not running!"); return
    
    script = session.create_script(FRIDA_JS)
    script.on('message', cap._on_message)
    script.load()
    cap._script = script
    
    # انتظار اكتشاف الاتصال
    print("[*] tap screen to detect connection...")
    t = time.time()
    while not cap._ready and time.time()-t < 30:
        time.sleep(0.1)
    
    if not cap._ready:
        print("[!] connection not detected"); return
    
    print("\n[*] sending init commands + capturing responses...")
    print("[*] wait ~15 seconds...\n")
    
    # === إرسال أوامر التهيئة (نفس init_game في onemt_bot.py) ===
    # هذه الأوامر تجبر السيرفر على إعادة إرسال البيانات
    init_cmds = [
        ('1000', '1', {}),                    # LOGIN_DATA_INIT (قد لا يرد لكن نجرب)
        ('1005', '1', {}),                    # INIT_ARMYDATA
        ('1005', '7', {"compiletype": 1}),    # تشكيلة 1
        ('1005', '7', {"compiletype": 2}),    # تشكيلة 2
        ('1005', '7', {"compiletype": 3}),    # تشكيلة 3
        ('1005', '7', {"compiletype": 4}),    # تشكيلة 4
        ('1002', '1', {}),                    # INIT_LORDDATA
        ('1002', '9', {}),                    # LORD_VALUE_UID
        ('1019', '4', {}),                    # ALL_ATTRIBUTE_INFO
        ('3079', '3', {}),                    # WAR_GEM_HALL_INFO
        ('2058', '21', {}),                   # HERO_HANDBOOK_INFO
        ('1007', '16', {}),                   # ALL_QUEUE (مسيرات)
    ]
    
    for cmd, subcmd, data in init_cmds:
        cap.send_cmd(cmd, subcmd, data)
        time.sleep(0.3)
    
    # ننتظر كل الردود
    print("\n[*] waiting for all responses...")
    time.sleep(12)
    
    # حفظ النتائج
    print("\n" + "=" * 50)
    castle_data = cap.save_results()
    
    print(f"\n[*] done! captured {cap._count} packets")
    print(f"[*] keys: {[k for k in castle_data.keys() if not k.startswith('_cmd_')]}")


if __name__ == '__main__':
    main()
