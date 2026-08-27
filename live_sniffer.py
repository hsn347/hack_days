"""
live_sniffer.py — مراقب الحزم المباشر
يعرض كل الطلبات المرسلة والردود الواردة بشكل واضح.

الاستخدام:
  python live_sniffer.py
"""
import frida, sys, json, struct, zlib, os, time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ── إعدادات ──
XOR_KEY    = bytes([79,83,120,72,80,46,33,45,119,100,63,39,108,97,111,53])
CMD_PREFIX = "onemt_"
HIDDEN     = {'1037'}                     # أوامر لا تعرضها
LOG_FILE   = os.path.join(os.path.dirname(__file__), "sniffer_log.txt")

# ── مساعدات ──
def xor(data: bytes) -> bytes:
    out = bytearray(len(data))
    kl  = len(XOR_KEY)
    for i, b in enumerate(data):
        out[i] = b ^ XOR_KEY[i % kl]
    return bytes(out)

def try_decompress(raw: bytes) -> bytes:
    for wbits in (-15, 15+32, 15):
        try: return zlib.decompress(raw, wbits)
        except: pass
    return raw

def decode_json(raw: bytes):
    """حاول فك JSON بعد XOR (مع أو بدون ضغط)."""
    for attempt in (raw, try_decompress(raw)):
        try:
            d = json.loads(xor(attempt))
            if 'cmd' in d or 'subcmd' in d:
                if d.get('cmd','').startswith(CMD_PREFIX):
                    d['cmd'] = d['cmd'][len(CMD_PREFIX):]
                return d
        except: pass
    return None

# ── فك حزم الاستقبال (السيرفر → اللعبة) ──
def unpack_recv(buf: bytes):
    """يفك حزم gate: [2B size][payload][1B ok][4B session]"""
    pkts, i = [], 0
    while i + 2 <= len(buf):
        sz = buf[i]*256 + buf[i+1]
        if sz == 0xFFFF:          # حزمة ضخمة
            if i + 5 > len(buf): break
            sz = buf[i+2]*65536 + buf[i+3]*256 + buf[i+4]
            i += 5
        else:
            i += 2
        if i + sz > len(buf): break
        pkts.append(buf[i:i+sz])
        i += sz
    return pkts, buf[i:] if i <= len(buf) else b''

def decode_recv_pkt(pkt: bytes):
    if len(pkt) < 5: return None
    raw = pkt[:-5]                # بدون ok + session
    return decode_json(raw) or decode_json(pkt[:-4])  # جرب بدون ok أيضاً

# ── فك حزم الإرسال (اللعبة → السيرفر) ──
def unpack_send(buf: bytes):
    pkts, i = [], 0
    while i + 2 <= len(buf):
        sz = buf[i]*256 + buf[i+1]
        if sz < 4 or sz > 65000: break
        if i + 2 + sz > len(buf): break
        pkt = buf[i+2 : i+2+sz]
        pkts.append(pkt)
        i += 2 + sz
    return pkts, buf[i:]

def decode_send_pkt(pkt: bytes):
    if len(pkt) < 5: return None
    return decode_json(pkt[:-4])  # بدون session فقط

# ── المخرجات ──
log_f  = None
count  = 0

def out(text):
    print(text)
    if log_f:
        log_f.write(text + '\n')
        log_f.flush()

def show(direction, num, c):
    cmd    = c.get('cmd', '?')
    sub    = c.get('subcmd', '')
    err    = c.get('err', '')
    arrow  = '>>>' if direction == 'SEND' else '<<<'
    tag    = '[SEND]' if direction == 'SEND' else ''
    err_s  = f" err={err}" if err else ''
    out(f"\n{'='*52}")
    out(f"  {arrow} #{num} cmd={cmd} subcmd={sub}{err_s} {tag}")
    out(f"{'='*52}")
    out(json.dumps(c, ensure_ascii=False, indent=2))

# ── Frida Script ──
SCRIPT = r"""
var libc     = Process.getModuleByName('libc.so');
var gateFDs  = {};
var lastKey  = {};

function isGate(b, n) {
  if (n < 4) return false;
  var sz = (b[0] << 8) | b[1];
  return (sz >= 4 && sz < 65000) || (b[0] === 0xFF && b[1] === 0xFF);
}

['write','send'].forEach(function(fn) {
  var ptr = libc.findExportByName(fn);
  if (!ptr) return;
  Interceptor.attach(ptr, {
    onEnter: function(a) {
      this.fd = a[0].toInt32();
      this.b  = a[1];
      this.l  = a[2].toInt32();
    },
    onLeave: function() {
      var l = this.l, fd = this.fd;
      if (l < 6 || l > 65000 || fd <= 3) return;
      try {
        var hd = new Uint8Array(this.b.readByteArray(Math.min(l, 6)));
        if (!isGate(hd, l) && !gateFDs[fd]) return;
        var now = Date.now(), k = 'S:'+fd;
        if (lastKey[k] && now-lastKey[k] < 5) return;
        lastKey[k] = now;
        send({type:'send', fd:fd}, this.b.readByteArray(l));
        gateFDs[fd] = true;
      } catch(e) {}
    }
  });
});

['read','recv'].forEach(function(fn) {
  var ptr = libc.findExportByName(fn);
  if (!ptr) return;
  Interceptor.attach(ptr, {
    onEnter: function(a) { this.fd=a[0].toInt32(); this.b=a[1]; },
    onLeave: function(r) {
      var n = r.toInt32();
      if (n <= 0 || n > 200000) return;
      var fd = this.fd;
      if (!gateFDs[fd]) {
        try {
          var hd = new Uint8Array(this.b.readByteArray(Math.min(n, 6)));
          if (!isGate(hd, n)) return;
        } catch(e) { return; }
      }
      var now = Date.now(), k = 'R:'+fd;
      if (lastKey[k] && now-lastKey[k] < 5) return;
      lastKey[k] = now;
      try {
        send({type:'recv', fd:fd}, this.b.readByteArray(n));
        gateFDs[fd] = true;
      } catch(e) {}
    }
  });
});
"""

# ── مخازن الحزم المجزأة ──
send_bufs = {}
recv_bufs = {}

def on_message(msg, data):
    global count
    if msg['type'] != 'send' or not data: return
    p    = msg.get('payload', {})
    ptype = p.get('type', '')
    fd   = p.get('fd', 0)
    raw  = bytes(data)

    if ptype == 'send':
        send_bufs[fd] = send_bufs.get(fd, b'') + raw
        pkts, send_bufs[fd] = unpack_send(send_bufs[fd])
        for pkt in pkts:
            c = decode_send_pkt(pkt)
            if c and c.get('cmd','?') not in HIDDEN:
                count += 1
                show('SEND', count, c)

    elif ptype == 'recv':
        recv_bufs[fd] = recv_bufs.get(fd, b'') + raw
        pkts, recv_bufs[fd] = unpack_recv(recv_bufs[fd])
        for pkt in pkts:
            c = decode_recv_pkt(pkt)
            if c and c.get('cmd','?') not in HIDDEN:
                count += 1
                show('RECV', count, c)

    if msg.get('type') == 'error':
        print(f"[Frida] {msg.get('description','?')}")

def main():
    global log_f
    log_f = open(LOG_FILE, 'w', encoding='utf-8')

    print("="*52)
    print("  live_sniffer.py — مراقب الحزم")
    print(f"  السجل: {LOG_FILE}")
    print("="*52)

    try:
        device = frida.get_device_manager().get_device("emulator-5554")
    except Exception as e:
        print(f"[!] خطأ: {e}"); sys.exit(1)

    # حاول الاتصال باسم العملية المختلفة
    session = None
    for name in ["Empire", "and.onemt.boe.tr"]:
        try:
            session = device.attach(name)
            print(f"[+] متصل بـ: {name}")
            break
        except: pass

    if not session:
        print("[!] اللعبة غير مفتوحة! افتحها أولاً.")
        sys.exit(1)

    script = session.create_script(SCRIPT)
    script.on('message', on_message)
    script.load()

    print("[*] يراقب الحزم... (Ctrl+C للإيقاف)\n")
    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        print(f"\n[*] تم الإيقاف. السجل محفوظ في: {LOG_FILE}")
        if log_f: log_f.close()

if __name__ == '__main__':
    main()
