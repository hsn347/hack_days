"""
live_sniffer.py
يتصل باللعبة مباشرة عبر Frida ويلتقط الحزم (إرسال/استقبال).
ثم يقوم بإرسالها إلى بايثون لفك ضغط Zlib و XOR بدقة.
بهذه الطريقة لن تخرج من اللعبة، وسترى كل البيانات بشكل واضح!
"""
import frida
import sys
import json
import struct
import os

sys.path.insert(0, os.path.dirname(__file__))
from onemt_bot import unpack_stream, decode_gate_response

# الأوامر التي لا نريد إزعاج الشاشة بها
HIDDEN_CMDS = {'1037'}

FRIDA_SCRIPT = """
var libc = Process.getModuleByName('libc.so');
var gateFDs = {};

function isGatePacket(bytes) {
  if (bytes.length < 6) return false;
  var sz = (bytes[0] << 8) | bytes[1];
  return sz >= 4 && sz < 65000 && sz + 2 <= bytes.length + 50000;
}

// اعتراض الإرسال
['send', 'sendto', 'write'].forEach(function(fn) {
  var ptr = libc.findExportByName(fn);
  if (!ptr) return;
  Interceptor.attach(ptr, {
    onEnter: function(a) {
      this.fd = a[0].toInt32();
      this.b = a[1];
      this.l = a[2].toInt32();
    },
    onLeave: function() {
      if (this.l < 6 || this.l > 65000) return;
      if (fn === 'write' && !gateFDs[this.fd]) {
        try {
          var peek = Array.from(new Uint8Array(this.b.readByteArray(Math.min(this.l, 10))));
          if (!isGatePacket(peek)) return;
        } catch(e) { return; }
      }
      try {
        var bytes = Array.from(new Uint8Array(this.b.readByteArray(this.l)));
        send({type: 'packet', dir: '>>>', fd: this.fd, data: bytes});
        gateFDs[this.fd] = true;
      } catch(e) {}
    }
  });
});

// اعتراض الاستقبال
['recv', 'recvfrom', 'read'].forEach(function(fn) {
  var ptr = libc.findExportByName(fn);
  if (!ptr) return;
  Interceptor.attach(ptr, {
    onEnter: function(a) { this.fd = a[0].toInt32(); this.b = a[1]; },
    onLeave: function(r) {
      var n = r.toInt32();
      if (n <= 0 || n > 65000) return;
      var fd = this.fd;
      if (fn === 'read' && !gateFDs[fd]) {
        try {
          var peek = Array.from(new Uint8Array(this.b.readByteArray(Math.min(n, 10))));
          if (!isGatePacket(peek)) return;
        } catch(e) { return; }
      }
      try {
        var bytes = Array.from(new Uint8Array(this.b.readByteArray(n)));
        send({type: 'packet', dir: '<<<', fd: fd, data: bytes});
      } catch(e) {}
    }
  });
});
"""

# مخازن الحزم المقطعة
recv_buffers = {}
send_buffers = {}

def process_buffer(fd, direction, raw_bytes):
    buffers = recv_buffers if direction == '<<<' else send_buffers
    if fd not in buffers:
        buffers[fd] = b''
    
    buffers[fd] += bytes(raw_bytes)
    
    pkts, remaining = unpack_stream(buffers[fd])
    buffers[fd] = remaining
    
    for p in pkts:
        res = decode_gate_response(p)
        if res and res.get('ok'):
            c = res.get('content', {})
            cmd = c.get('cmd', '?')
            subcmd = c.get('subcmd', '?')
            
            if cmd in HIDDEN_CMDS:
                continue
                
            print(f"\n━━━ {direction} cmd={cmd} subcmd={subcmd} ━━━")
            pretty = json.dumps(c, ensure_ascii=False, indent=2)
            if len(pretty) > 3000:
                print(pretty[:3000] + "\n... [تم قص الباقي لأن البيانات ضخمة]")
            else:
                print(pretty)
        else:
            # إذا فشل في فك التشفير
            if res and 'raw' in res:
                print(f"\n━━━ {direction} [RAW DATA] ━━━")
                print(res['raw'][:500])

def on_message(message, data):
    if message['type'] == 'send':
        payload = message.get('payload', {})
        if payload.get('type') == 'packet':
            process_buffer(payload['fd'], payload['dir'], payload['data'])
    elif message['type'] == 'error':
        print(f"[*] Frida Error: {message['description']}")

def main():
    print("[*] جاري الاتصال بالمحاكي...")
    device = frida.get_device_manager().get_device("emulator-5554")
    print("[*] جاري الاتصال باللعبة...")
    session = device.attach("Empire")
    print("[*] تم الاتصال! جاري زرع السكربت...")
    script = session.create_script(FRIDA_SCRIPT)
    script.on('message', on_message)
    script.load()
    
    print("\n" + "="*50)
    print("✅ السكربت يعمل الآن! العب في اللعبة وسترى الحزم هنا.")
    print("   ملاحظة: هذا السكربت لن يطردك من اللعبة!")
    print("="*50 + "\n")
    
    sys.stdin.read()

if __name__ == '__main__':
    main()
