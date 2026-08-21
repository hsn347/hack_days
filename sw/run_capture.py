import frida
import sys
import json
import zlib
import struct
import os

# كود Frida سيقوم بالتقاط البيانات الخام (بدون فك) وإرسالها لبايثون
# بايثون سيتكفل بفك الضغط (Zlib) وفك التشفير (XOR) لضمان عدم ضياع أي بيانات كبيرة

JS_CODE = """
'use strict';

var libc = Process.getModuleByName('libc.so');
var recvBuffers = {};
var gateFDs = {};

function isGatePacket(bytes) {
  if (bytes.length < 6) return false;
  var sz = (bytes[0] << 8) | bytes[1];
  return sz >= 4 && sz < 60000 && sz + 2 <= bytes.length + 50000;
}

function processBuffer(fd, direction) {
  var bytes = recvBuffers[fd];
  var offset = 0;

  while (offset + 2 < bytes.length) {
    var sz, head;

    // دعم الـ extended header (0xFFFF)
    if (bytes[offset] === 0xFF && bytes[offset+1] === 0xFF) {
      if (offset + 5 > bytes.length) break; // لسه ما وصل كل الـ header
      sz = (bytes[offset+2] * 65536) + (bytes[offset+3] * 256) + bytes[offset+4];
      head = 5;
    } else {
      sz = (bytes[offset] << 8) | bytes[offset + 1];
      head = 2;
    }

    if (sz < 4 || sz > 500000) break;  // رفع الحد من 60000 إلى 500000
    if (offset + head + sz > bytes.length) break; // لسه ما اكتملت الحزمة

    // إرسال الحزمة كاملة لبايثون
    var packet = bytes.slice(offset, offset + head + sz);
    send({type: 'packet', direction: direction, fd: fd, head: head}, packet);

    gateFDs[fd] = true;
    offset += head + sz;
  }

  if (offset > 0) {
    recvBuffers[fd] = recvBuffers[fd].slice(offset);
  }
  if (recvBuffers[fd].length > 1000000) recvBuffers[fd] = [];
}

['send', 'sendto', 'write'].forEach(function(fn) {
  var ptr = libc.findExportByName(fn);
  if (!ptr) return;
  Interceptor.attach(ptr, {
    onEnter: function(a) { this.fd = a[0].toInt32(); this.b = a[1]; this.l = a[2].toInt32(); },
    onLeave: function() {
      if (this.l < 6 || this.l > 65000) return;
      if (fn === 'write' && !gateFDs[this.fd]) {
        try {
          var peek = Array.from(new Uint8Array(this.b.readByteArray(Math.min(this.l, 10))));
          if (!isGatePacket(peek)) return;
        } catch(e) { return; }
      }
      try {
        var chunk = Array.from(new Uint8Array(this.b.readByteArray(this.l)));
        if (!recvBuffers[this.fd]) recvBuffers[this.fd] = [];
        recvBuffers[this.fd] = recvBuffers[this.fd].concat(chunk);
        processBuffer(this.fd, '>>>');
      } catch(e) {}
    }
  });
});

['recv', 'recvfrom', 'read'].forEach(function(fn) {
  var ptr = libc.findExportByName(fn);
  if (!ptr) return;
  Interceptor.attach(ptr, {
    onEnter: function(a) { this.fd = a[0].toInt32(); this.b = a[1]; },
    onLeave: function(r) {
      var n = r.toInt32();
      if (n <= 0 || n > 65000) return;
      if (fn === 'read' && !gateFDs[this.fd]) {
        try {
          var peek = Array.from(new Uint8Array(this.b.readByteArray(Math.min(n, 10))));
          if (!isGatePacket(peek)) return;
        } catch(e) { return; }
      }
      try {
        var chunk = Array.from(new Uint8Array(this.b.readByteArray(n)));
        if (!recvBuffers[this.fd]) recvBuffers[this.fd] = [];
        recvBuffers[this.fd] = recvBuffers[this.fd].concat(chunk);
        processBuffer(this.fd, '<<<');
      } catch(e) {}
    }
  });
});
"""

XOR_KEY = b"OSxHP.!-wd?'lao5"
def xor_crypt(data: bytes) -> bytes:
    return bytes(b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(data))

all_responses = []

def on_message(message, data):
    if message['type'] == 'error':
        print(f"[JS ERROR] {message['description']}")
        return
        
    if message['type'] == 'send' and message['payload'].get('type') == 'packet':
        direction = message['payload']['direction']
        head = message['payload'].get('head', 2)
        if not data or len(data) < head + 5: return

        pkt = data  # يشمل الـ header
        trailer_sz = 4 if direction == '>>>' else 5
        session = struct.unpack('>I', pkt[-4:])[0]
        raw = pkt[head:-trailer_sz]
        
        # debug: اطبع أول بيانات تصل لنتأكد من الاتصال
        if len(all_responses) == 0 and direction == '<<<':
            print(f"[debug] أول رد وصل: {len(pkt)} bytes, session={session}, raw[:20]={raw[:20].hex()}")

        # فك الضغط
        if session == 0:
            try:
                raw = zlib.decompress(raw, -15)
            except:
                try:
                    raw = zlib.decompress(raw)
                except:
                    pass

        try:
            dec = xor_crypt(raw)
            c = json.loads(dec)
            cmd = str(c.get('cmd', '?')).replace('onemt_', '')

            if cmd not in ('1037', '1030', '1009'):
                print(f"\n━━━ {direction} cmd={cmd} ━━━")
                pretty = json.dumps(c, indent=2, ensure_ascii=False)
                print(pretty[:3000])
                if len(pretty) > 3000:
                    print(f"... ({len(pretty)} chars total)")

            if direction == '<<<' and cmd not in ('1037', '1030'):
                all_responses.append(c)
                with open("castle_info.json", "w", encoding="utf-8") as f:
                    json.dump(all_responses, f, ensure_ascii=False, indent=2)

        except Exception as e:
            # اطبع الخطأ لنفهم السبب
            print(f"[decode error] session={session} len={len(raw)} err={e} raw[:30]={raw[:30].hex() if raw else 'empty'}")

def main():
    print("[*] جاري الاتصال بالمحاكي...")
    device = frida.get_device_manager().get_device('emulator-5554')
    try:
        session = device.attach('Empire')
    except frida.ProcessNotFoundError:
        print("[!] اللعبة غير مفتوحة. افتح اللعبة أولاً.")
        return
        
    script = session.create_script(JS_CODE)
    script.on('message', on_message)
    script.load()
    
    print("[*] تم التشغيل بنجاح!")
    print("[*] السكربت الآن يدعم فك ضغط Zlib التلقائي.")
    print("[*] سيتم حفظ أي بيانات ضخمة في castle_info.json مباشرة.")
    print("[*] افتح اللعبة الآن واستكشف (اضغط Ctrl+C للإيقاف)...")
    
    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        print("\n[*] تم الإيقاف.")

if __name__ == '__main__':
    main()
