import frida
import json
import zlib
import time
import sys
import threading
import subprocess

XOR_KEY = "OSxHP.!-wd?'lao5"

def xor_crypt(data: bytes, key: str) -> bytes:
    k = key.encode()
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

def decode_pkt(pkt: bytes):
    if len(pkt) < 4: return None
    body = pkt[2:-2]
    dec = xor_crypt(body, XOR_KEY)
    text = None
    try:
        text = zlib.decompress(dec, -15).decode('utf-8', errors='ignore')
    except:
        try:
            text = dec.decode('utf-8', errors='ignore')
        except:
            pass
    if text:
        try:
            return json.loads(text)
        except:
            pass
    return None

JS_HOOK = """
var libc = Process.getModuleByName('libc.so');
var _fd = -1, _session = 0, _started = false;
var XOR_KEY = "OSxHP.!-wd?'lao5";

function buildPacket(cmd, subcmd, data) {
    var raw = JSON.stringify({cmd: String(cmd), subcmd: String(subcmd), data: data});
    var enc = []; var k = XOR_KEY;
    for (var i = 0; i < raw.length; i++) enc.push(raw.charCodeAt(i) ^ k.charCodeAt(i % k.length));
    var len = enc.length + 4;
    var pkt = [0x54, 0x34, (len >> 8) & 0xFF, len & 0xFF];
    for (var i = 0; i < enc.length; i++) pkt.push(enc[i]);
    pkt.push(0x50, 0x4B);
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

function handleCmd(msg) {
    if (!_started || _fd < 0) {
        send({type:'err', msg:'not connected'});
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

class Scanner:
    def __init__(self):
        self._ready = False
        self._fd = -1
        self._script = None
        self._recv_buf = b''
        self.all_responses = []

    def _on_message(self, msg, data):
        if msg['type'] != 'send': return
        p = msg.get('payload', {})
        t = p.get('type','')
        if t == 'ready':
            self._fd = p['fd']
            self._ready = True
        elif t == 'data' and data:
            self._recv_buf += bytes(data)
            self._try_parse()

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
                buf = buf[1:]
                continue
            if len(buf) < head + sz: break
            pkt = buf[head:head+sz]
            buf = buf[head+sz:]
            d = decode_pkt(pkt)
            if d:
                self.all_responses.append(d)
        self._recv_buf = buf

    def send(self, cmd, subcmd, data):
        self._script.post({'type': 'cmd', 'cmd': str(cmd), 'subcmd': str(subcmd), 'data': data})

def run_scan():
    s = Scanner()
    device = frida.get_device_manager().get_device("emulator-5554")
    session = device.attach("Empire")
    s._script = session.create_script(JS_HOOK)
    s._script.on('message', s._on_message)
    s._script.load()

    for _ in range(20):
        if s._ready: break
        time.sleep(0.1)

    if not s._ready:
        print("[*] Tapping screen via adb...")
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "input", "tap", "500", "500"], capture_output=True)
        for _ in range(30):
            if s._ready: break
            time.sleep(0.1)

    if not s._ready:
        print("[!] Failed to connect")
        return

    print(f"[+] Connected! Testing all mapType & subType values...")

    for m_type in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 19]:
        for s_type in [0, 1, 2, 3, 4, 5]:
            req = {
                "mapType": m_type,
                "subType": s_type,
                "x": 485,
                "y": 289,
                "num": 5,
                "range": 500,
                "minLv": 1,
                "maxLv": 35,
                "exclude": {}
            }
            s.all_responses.clear()
            s.send("2011", "3", req)
            time.sleep(0.4)
            
            for r in s.all_responses:
                if r.get('cmd') == '2011' and r.get('subcmd') == '3':
                    res = r.get('result')
                    if res and len(res) > 0:
                        print(f"🌟 FOUND! mapType={m_type} subType={s_type} -> {len(res)} results: {json.dumps(res[:2], ensure_ascii=False)}")
                    elif isinstance(res, dict) and len(res) > 0:
                        print(f"🌟 FOUND DICT! mapType={m_type} subType={s_type} -> {json.dumps(res, ensure_ascii=False)}")

if __name__ == '__main__':
    run_scan()
