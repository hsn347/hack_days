import frida
import json
import zlib
import time
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

class RelicHunter:
    def __init__(self):
        self._ready = False
        self._fd = -1
        self._script = None
        self._recv_buf = b''
        self.responses = []

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
                self.responses.append(d)
        self._recv_buf = buf

    def test_cmd(self, cmd, subcmd, data, wait=0.8):
        self.responses.clear()
        self._script.post({'type': 'cmd', 'cmd': str(cmd), 'subcmd': str(subcmd), 'data': data})
        time.sleep(wait)
        return list(self.responses)

def main():
    h = RelicHunter()
    device = frida.get_device_manager().get_device("emulator-5554")
    session = device.attach("Empire")
    h._script = session.create_script(JS_HOOK)
    h._script.on('message', h._on_message)
    h._script.load()

    for _ in range(30):
        if h._ready: break
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "input", "tap", "500", "500"], capture_output=True)
        time.sleep(0.3)

    if not h._ready:
        print("[!] Not connected")
        return

    print(f"[+] Connected! fd={h._fd}")

    # 1. Test 1008/1 (Relics Module - Init / Query)
    print("\n--- Testing 1008/1 (CMD_RELICS_EXPLORE_MODULE) ---")
    res1008 = h.test_cmd('1008', '1', {})
    for r in res1008:
        print(f"1008/1 -> {json.dumps(r, ensure_ascii=False)}")

    # 2. Test 1008/2
    print("\n--- Testing 1008/2 ---")
    res1008_2 = h.test_cmd('1008', '2', {})
    for r in res1008_2:
        print(f"1008/2 -> {json.dumps(r, ensure_ascii=False)}")

    # 3. Test 2011/3 for all candidate mapTypes
    candidate_types = [7, 8, 16, 17, 18, 19, 20, 24, 25, 27, 28, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40]
    print(f"\n--- Testing 2011/3 candidate mapTypes ---")
    for mt in candidate_types:
        for st in [0, 1]:
            req = {
                "mapType": mt,
                "subType": st,
                "x": 397,
                "y": 268,
                "num": 5,
                "range": 500,
                "minLv": 1,
                "maxLv": 30,
                "exclude": {}
            }
            res = h.test_cmd('2011', '3', req, wait=0.5)
            for r in res:
                if r.get('cmd') in ('2011', 'onemt_2011') and str(r.get('subcmd')) == '3':
                    result = r.get('result', [])
                    err = r.get('err', '0')
                    cnt = len(result) if isinstance(result, (list, dict)) else 0
                    if cnt > 0:
                        print(f"🎯 FOUND RESULT! mapType={mt}, subType={st} -> Count={cnt} -> {json.dumps(result, ensure_ascii=False)}")
                    elif err == '0':
                        print(f"✅ Schema valid (err=0): mapType={mt}, subType={st}")

if __name__ == '__main__':
    main()
