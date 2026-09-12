"""
game_state/daemon.py — Frida Listener Daemon
═════════════════════════════════════════════
يعمل في خيط خلفية ويحوّل حزم اللعبة إلى بيانات منظّمة في GameState.
"""
import frida, json, zlib, threading, time, os
from typing import Optional
from .state import GameState

# ─── ثوابت ───
XOR_KEY       = bytes([79,83,120,72,80,46,33,45,119,100,63,39,108,97,111,53])
DEVICE_ID     = "emulator-5554"
PROCESS_NAMES = ["Empire", "and.onemt.boe.tr"]
SILENT_CMDS   = {'1037'}

INIT_CMDS = [
    ('1000','1',{}), ('1005','1',{}),
    ('1005','7',{'compiletype':1}), ('1005','7',{'compiletype':2}),
    ('1005','7',{'compiletype':3}), ('1005','7',{'compiletype':4}),
    ('1002','1',{}), ('1002','9',{}),
    ('1019','4',{}), ('3079','3',{}), ('2058','21',{}), ('1007','16',{}),
]

# ─── Frida JS ───
FRIDA_JS = r"""
var XOR_KEY = "OSxHP.!-wd?'lao5";
var _fd = -1, _session = 0, _started = false;
var libc = Process.getModuleByName('libc.so');

function xorEnc(t,k){var r=[];var j=0;for(var i=0;i<t.length;i++){r.push(t.charCodeAt(i)^k.charCodeAt(j));j=(j+1)%k.length;}return r;}
function buildPkt(c,s,d){var m=JSON.stringify({cmd:"onemt_"+c,subcmd:String(s),data:d});var e=xorEnc(m,XOR_KEY);var l=e.length+4;var p=[(l>>8)&0xFF,l&0xFF];p=p.concat(e);p.push((_session>>24)&0xFF,(_session>>16)&0xFF,(_session>>8)&0xFF,_session&0xFF);return p;}
function writePkt(p){var b=Memory.alloc(p.length);for(var i=0;i<p.length;i++)b.add(i).writeU8(p[i]);var w=new NativeFunction(libc.findExportByName('write'),'int',['int','pointer','int']);var r=w(_fd,b,p.length);if(r<=0){var s=new NativeFunction(libc.findExportByName('send'),'int',['int','pointer','int','int']);r=s(_fd,b,p.length,0);}return r;}

['write','send'].forEach(function(fn){
    var ptr=libc.findExportByName(fn); if(!ptr)return;
    Interceptor.attach(ptr,{onEnter:function(a){
        var len=a[2].toInt32(),fd=a[0].toInt32();
        if(len<10||len>2000||fd<=3)return;
        if(!_started){
            try{if(a[1].add(2).readU8()===0x34){
                var p=a[1].add(len-4);
                _session=((p.readU8()<<24)|(p.add(1).readU8()<<16)|(p.add(2).readU8()<<8)|p.add(3).readU8())>>>0;
                _fd=fd;_started=true;send({type:'ready',fd:fd,session:_session});
            }}catch(e){}
        }else if(fd===_fd){
            try{var p=a[1].add(len-4);var s=((p.readU8()<<24)|(p.add(1).readU8()<<16)|(p.add(2).readU8()<<8)|p.add(3).readU8())>>>0;if(s>_session)_session=s;}catch(e){}
        }
    }});
});

['read','recv'].forEach(function(fn){
    var ptr=libc.findExportByName(fn); if(!ptr)return;
    Interceptor.attach(ptr,{
        onEnter:function(a){this.buf=a[1];this.fd=a[0].toInt32();},
        onLeave:function(r){var n=r.toInt32();if(n<=0||this.fd!==_fd)return;try{send({type:'data'},this.buf.readByteArray(n));}catch(e){}}
    });
});

function handleCmd(msg){
    if(!_started){send({type:'err',msg:'not_ready'});recv('cmd',handleCmd);return;}
    try{_session++;writePkt(buildPkt(msg.cmd,msg.subcmd,msg.data||{}));}catch(e){send({type:'err',msg:e.message});}
    recv('cmd',handleCmd);
}
recv('cmd',handleCmd);
"""


def _xor(data: bytes) -> bytes:
    out = bytearray(len(data))
    kl = len(XOR_KEY)
    for i, b in enumerate(data):
        out[i] = b ^ XOR_KEY[i % kl]
    return bytes(out)

def _decompress(raw: bytes) -> bytes:
    for w in (-15, 47, 15):
        try: return zlib.decompress(raw, w)
        except: pass
    return raw

def _decode_pkt(pkt: bytes):
    if len(pkt) < 5: return None
    for trim in (5, 4):
        raw = pkt[:-trim] if trim <= len(pkt) else pkt
        for attempt in (raw, _decompress(raw)):
            try:
                d = json.loads(_xor(attempt))
                if isinstance(d, dict) and ('cmd' in d or 'subcmd' in d):
                    c = d.get('cmd', '')
                    if c.startswith('onemt_'): d['cmd'] = c[6:]
                    return d
            except: pass
    return None


class GameDaemon:
    """
    Frida Daemon — يعمل في الخلفية ويُغذّي GameState بالبيانات اللحظية.
    """

    def __init__(self, state: GameState, verbose: bool = False):
        self._state   = state
        self._verbose = verbose
        self._script  = None
        self._buf     = b''
        self._lock    = threading.Lock()
        self._ready   = threading.Event()
        self._alive   = True
        self._thread: Optional[threading.Thread] = None

    # ─── الاتصال ───
    def start(self, tap_timeout: int = 60) -> bool:
        """
        يبدأ الاتصال بالمحاكي. يعيد True عند النجاح.
        tap_timeout: ثوانٍ للانتظار حتى يضغط المستخدم على الشاشة.
        """
        try:
            device = frida.get_device_manager().get_device(DEVICE_ID)
        except Exception as e:
            print(f"[Daemon] ✗ خطأ في الاتصال بالمحاكي: {e}")
            return False

        session = None
        for name in PROCESS_NAMES:
            try:
                session = device.attach(name)
                print(f"[Daemon] ✓ متصل بـ: {name}")
                break
            except: pass

        if not session:
            print("[Daemon] ✗ اللعبة غير مفتوحة.")
            return False

        script = session.create_script(FRIDA_JS)
        script.on('message', self._on_msg)
        script.load()
        self._script = script
        self._state.connected = True

        print("[Daemon] * المس شاشة اللعبة لاكتشاف جلسة الشبكة...")
        if not self._ready.wait(tap_timeout):
            print("[Daemon] ✗ انتهت مهلة الاكتشاف.")
            return False

        # انتظار استقرار session قبل إرسال الأوامر
        time.sleep(2)

        # جلب اللقطة الأولية
        self._fetch_init()
        return True

    def start_background(self, tap_timeout: int = 60) -> threading.Thread:
        """يشغّل الـ daemon في خيط خلفية ويعيد الخيط"""
        self._thread = threading.Thread(
            target=self.start, args=(tap_timeout,), daemon=True, name="GameDaemon"
        )
        self._thread.start()
        return self._thread

    def stop(self):
        self._alive = False
        self._state.connected = False

    def send_cmd(self, cmd: str, subcmd: str, data: dict = None):
        """إرسال أمر للسيرفر"""
        if self._ready.is_set() and self._script:
            self._script.post({
                'type': 'cmd', 'cmd': str(cmd),
                'subcmd': str(subcmd), 'data': data or {}
            })

    # ─── معالجة رسائل Frida ───
    def _on_msg(self, msg, data):
        if msg.get('type') != 'send': return
        p = msg.get('payload', {})
        t = p.get('type', '')
        if t == 'ready':
            self._ready.set()
            print(f"[Daemon] ✓ جلسة مكتشفة — fd={p.get('fd')} session={p.get('session')}")
        elif t == 'data' and data:
            with self._lock:
                self._buf += bytes(data)
                self._parse()
        elif t == 'err' and self._verbose:
            print(f"[Daemon] ! {p.get('msg')}")

    def _parse(self):
        buf = self._buf
        while len(buf) >= 2:
            sz = buf[0]*256 + buf[1]; head = 2
            if sz == 0xFFFF:
                if len(buf) < 5: break
                sz = buf[2]*65536 + buf[3]*256 + buf[4]; head = 5
            if sz < 4 or sz > 500000: buf = buf[1:]; continue
            if len(buf) < head + sz: break
            d = _decode_pkt(buf[head:head+sz])
            buf = buf[head+sz:]
            if d:
                self._state.pkt_count += 1
                self._dispatch(d)
        self._buf = buf

    def _dispatch(self, pkt: dict):
        cmd  = pkt.get('cmd', '')
        sub  = str(pkt.get('subcmd', ''))
        data = pkt.get('data', {})
        if not isinstance(data, dict) or cmd in SILENT_CMDS:
            return

        if cmd == '1009':
            nid   = data.get('notifyID', '')
            ndata = data.get('notifyData', [])
            if nid:
                self._state.process_notify(nid, ndata)
                if self._verbose and nid not in ('NOTIFY_SERVER_TIME',):
                    print(f"[Daemon]  🔔 {nid}")

        elif cmd == '1000':
            self._state.process_init_data(data)
            if self._verbose:
                print(f"[Daemon]  📦 INIT — {len(data)} مفتاح")

        elif cmd == '1007':
            self._state.process_queue_data(sub, data)

        elif cmd == '1005':
            self._state.set_raw(f'_army_{sub}', data)

        elif cmd == '2058':
            self._state.set_raw(f'_hero_{sub}', data)

        elif cmd == '1002':
            self._state.set_raw(f'_player_{sub}', data)

        elif cmd == '1019':
            self._state.set_raw(f'_attr_{sub}', data)

        else:
            self._state.set_raw(f'_cmd_{cmd}_{sub}', data)

    def _fetch_init(self):
        """جلب اللقطة الأولية الكاملة من السيرفر"""
        print("[Daemon] * جلب البيانات الأولية...")
        for c, s, d in INIT_CMDS:
            self.send_cmd(c, s, d)
            time.sleep(0.3)
        print("[Daemon] * انتظار الردود (8 ثوانٍ)...")
        time.sleep(8)
        s = self._state.get_summary()
        print(f"[Daemon] ✓ {s['heroes_total']} بطل | {s['raw_keys']} مفتاح | {s['packets']} حزمة")
        print(f"[Daemon] ✓ الأبطال المتاحون: {s['heroes_idle']} | المشغولون: {s['heroes_busy']}")
