import frida, json, zlib, time, subprocess

XOR_KEY = "OSxHP.!-wd?'lao5"

def xor_crypt(data: bytes, key: str) -> bytes:
    k = key.encode()
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

def decode_pkt(pkt: bytes):
    if len(pkt) < 4: return None
    body = pkt[2:-2]
    dec = xor_crypt(body, XOR_KEY)
    try:
        return json.loads(zlib.decompress(dec, -15).decode('utf-8', errors='ignore'))
    except:
        try:
            return json.loads(dec.decode('utf-8', errors='ignore'))
        except:
            return None

JS_HOOK = '''
var libc = Process.getModuleByName('libc.so');
var _fd = -1, _session = 0, _started = false;
var XOR_KEY = "OSxHP.!-wd?'lao5";

function buildPacket(cmd, subcmd, data) {
    var raw = JSON.stringify({cmd: "onemt_" + cmd, subcmd: String(subcmd), data: data});
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
'''

def test_q():
    device = frida.get_device_manager().get_device("emulator-5554")
    session = device.attach("Empire")
    script = session.create_script(JS_HOOK)
    
    ready = [False]
    responses = []
    
    def on_message(msg, data):
        if msg['type'] != 'send': return
        p = msg.get('payload', {})
        t = p.get('type','')
        if t == 'ready':
            ready[0] = True
        elif t == 'data' and data:
            d = decode_pkt(bytes(data))
            if d: responses.append(d)

    script.on('message', on_message)
    script.load()

    for _ in range(30):
        if ready[0]: break
        subprocess.run(["adb", "-s", "emulator-5554", "shell", "input", "tap", "500", "500"], capture_output=True)
        time.sleep(0.2)

    if not ready[0]:
        print("[!] Not connected")
        return

    print("[+] Connected! Testing 1007/16 (REQ_ALL_QUEUE)...")
    responses.clear()
    script.post({'type': 'cmd', 'cmd': '1007', 'subcmd': '16', 'data': {}})
    time.sleep(1.5)
    for r in responses:
        print(f"1007/16 response:\n{json.dumps(r, ensure_ascii=False, indent=2)}")

if __name__ == '__main__':
    test_q()
