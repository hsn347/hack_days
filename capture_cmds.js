/**
 * capture_cmds.js v3
 * يلتقط كل شيء: send/sendto/write + recv/recvfrom/read
 * مع تجميع الحزم المقطّعة وفلترة ذكية
 */
'use strict';

var count = 0;
var libc = Process.getModuleByName('libc.so');
var XOR_KEY = [79,83,120,72,80,46,33,45,119,100,63,39,108,97,111,53];

var recvBuffers = {};
var gateFDs = {};  // نحفظ الـ fds التي تبيّن أنها gate

// أوامر مخفية
var HIDDEN = {'1037':1, '1030':1};

function xorDecrypt(bytes) {
  var out = [];
  for (var i = 0; i < bytes.length; i++)
    out.push(bytes[i] ^ XOR_KEY[i % XOR_KEY.length]);
  return out;
}

function tryDecodePackets(bytes, direction, fd) {
  var offset = 0;

  while (offset + 2 < bytes.length) {
    var sz = (bytes[offset] << 8) | bytes[offset + 1];
    if (sz < 4 || sz > 60000) break;
    if (offset + 2 + sz > bytes.length) break;

    var trailerSize = (direction.indexOf('>>>') !== -1) ? 4 : 5;
    if (sz < trailerSize) break;

    var raw = bytes.slice(offset + 2, offset + 2 + sz - trailerSize);
    var dec = xorDecrypt(raw);
    var str = '';
    for (var i = 0; i < dec.length; i++) {
      var c = dec[i];
      if (c === 0) break;
      if (c >= 32 && c < 127) str += String.fromCharCode(c);
    }

    var j0 = str.indexOf('{');
    if (j0 >= 0) {
      try {
        var parsed = JSON.parse(str.substring(j0));
        var cmd = String(parsed.cmd || '?').replace(/^onemt_/, '');
        
        // سجّل هذا الـ fd كـ gate fd
        if (fd !== undefined) gateFDs[fd] = true;
        
        if (!HIDDEN[cmd]) {
          count++;
          console.log('\n━━━ ' + direction + ' #' + count + ' cmd=' + cmd + ' ━━━');
          var pretty = JSON.stringify(parsed, null, 2);
          console.log(pretty.substring(0, 2500));
          if (pretty.length > 2500) console.log('... (' + pretty.length + ' total)');
        }
      } catch(e) {
        if (str.indexOf('cmd') !== -1 && str.indexOf('onemt') !== -1) {
          count++;
          console.log('\n━━━ ' + direction + ' #' + count + ' [PARTIAL] ━━━');
          console.log(str.substring(0, 500));
        }
      }
    }
    offset += 2 + sz;
  }
  return offset;
}

function isGatePacket(bytes) {
  if (bytes.length < 6) return false;
  var sz = (bytes[0] << 8) | bytes[1];
  return sz >= 4 && sz < 60000 && sz + 2 <= bytes.length + 50000;
}

// ─── SEND hooks ───
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
      // لـ write: فقط إذا كان gate fd أو يبدو كـ gate packet
      if (fn === 'write' && !gateFDs[this.fd]) {
        try {
          var peek = Array.from(new Uint8Array(this.b.readByteArray(Math.min(this.l, 10))));
          if (!isGatePacket(peek)) return;
        } catch(e) { return; }
      }
      try {
        var bytes = Array.from(new Uint8Array(this.b.readByteArray(this.l)));
        tryDecodePackets(bytes, '>>>', this.fd);
      } catch(e) {}
    }
  });
  console.log('[+] ' + fn + ' hooked');
});

// ─── RECV hooks ───
['recv', 'recvfrom', 'read'].forEach(function(fn) {
  var ptr = libc.findExportByName(fn);
  if (!ptr) return;
  Interceptor.attach(ptr, {
    onEnter: function(a) { this.fd = a[0].toInt32(); this.b = a[1]; },
    onLeave: function(r) {
      var n = r.toInt32();
      if (n <= 0 || n > 65000) return;
      var fd = this.fd;
      
      // لـ read: فقط إذا كان gate fd أو يبدو كـ gate packet
      if (fn === 'read' && !gateFDs[fd]) {
        try {
          var peek = Array.from(new Uint8Array(this.b.readByteArray(Math.min(n, 10))));
          if (!isGatePacket(peek)) return;
        } catch(e) { return; }
      }
      
      try {
        var chunk = Array.from(new Uint8Array(this.b.readByteArray(n)));
        if (!recvBuffers[fd]) recvBuffers[fd] = [];
        recvBuffers[fd] = recvBuffers[fd].concat(chunk);

        var consumed = tryDecodePackets(recvBuffers[fd], '<<<', fd);
        if (consumed > 0) recvBuffers[fd] = recvBuffers[fd].slice(consumed);
        
        // debug: إذا gate fd وفيه بيانات لم تُفك
        if (gateFDs[fd] && recvBuffers[fd].length > 6 && consumed === 0) {
          var b = recvBuffers[fd];
          var expectedSz = (b[0] << 8) | b[1];
          // console.log('[buf] fd=' + fd + ' waiting=' + b.length + '/' + (expectedSz+2) + ' bytes');
          return;
        }
        
        if (recvBuffers[fd].length > 200000) recvBuffers[fd] = [];
      } catch(e) {}
    }
  });
  console.log('[+] ' + fn + ' hooked');
});

console.log('\n[*] Capture v3 Ready!');
console.log('[*] Hidden: heartbeat (1037/1009) + 1030');
console.log('[*] Hooks: send/sendto/write + recv/recvfrom/read');
console.log('[*] Play the game now...');
