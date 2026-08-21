/**
 * يلتقط كل الـ traffic المرسل من اللعبة
 * يطبع أي شيء يبدو كـ base64 أو نص عادي
 */
'use strict';

var count = 0;
var libc = Process.getModuleByName('libc.so');

// Hook sendto (أكثر دوال الـ network استخداماً)
var sendtoPtr = libc.findExportByName('sendto');
if (sendtoPtr) {
  Interceptor.attach(sendtoPtr, {
    onEnter: function(args) {
      this.buf = args[1];
      this.len = args[2].toInt32();
    },
    onLeave: function() {
      if (this.len <= 0 || this.len > 2000) return;
      try {
        var data = this.buf.readByteArray(this.len);
        var bytes = new Uint8Array(data);
        var txt = '';
        var isPrintable = true;
        for (var i = 0; i < bytes.length; i++) {
          var b = bytes[i];
          if (b === 10) { txt += '\n'; continue; }
          if (b >= 32 && b < 127) { txt += String.fromCharCode(b); continue; }
          if (b < 32 || b === 127) { isPrintable = false; txt += '.'; }
        }
        // فقط طباعة إذا يوجد base64 أو @ separator
        if (txt.indexOf('@') !== -1 || (txt.length > 8 && /[A-Za-z0-9+\/=]{10}/.test(txt))) {
          count++;
          console.log('\n=== SENDTO #' + count + ' len=' + this.len + ' ===');
          console.log(txt.substring(0, 600));
        }
      } catch(e) {}
    }
  });
  console.log('[+] sendto() hooked');
}

// Hook send
var sendPtr = libc.findExportByName('send');
if (sendPtr) {
  Interceptor.attach(sendPtr, {
    onEnter: function(args) {
      this.buf = args[1];
      this.len = args[2].toInt32();
    },
    onLeave: function() {
      if (this.len <= 0 || this.len > 2000) return;
      try {
        var data = this.buf.readByteArray(this.len);
        var bytes = new Uint8Array(data);
        var txt = '';
        for (var i = 0; i < bytes.length; i++) {
          var b = bytes[i];
          if (b === 10) { txt += '\n'; continue; }
          if (b >= 32 && b < 127) { txt += String.fromCharCode(b); continue; }
          txt += '.';
        }
        if (txt.indexOf('@') !== -1 || (txt.length > 8 && /[A-Za-z0-9+\/=]{10}/.test(txt))) {
          count++;
          console.log('\n=== SEND #' + count + ' len=' + this.len + ' ===');
          console.log(txt.substring(0, 600));
        }
      } catch(e) {}
    }
  });
  console.log('[+] send() hooked');
}

// Hook recvfrom لرؤية الردود أيضاً
var recvfromPtr = libc.findExportByName('recvfrom');
if (recvfromPtr) {
  Interceptor.attach(recvfromPtr, {
    onEnter: function(args) {
      this.buf = args[1];
    },
    onLeave: function(retval) {
      var n = retval.toInt32();
      if (n <= 0 || n > 500) return;
      try {
        var data = this.buf.readByteArray(n);
        var bytes = new Uint8Array(data);
        var txt = '';
        for (var i = 0; i < bytes.length; i++) {
          var b = bytes[i];
          if (b === 10) { txt += '\n'; continue; }
          if (b >= 32 && b < 127) { txt += String.fromCharCode(b); continue; }
          txt += '.';
        }
        if (txt.length > 5 && /[A-Za-z0-9]/.test(txt)) {
          console.log('\n--- RECVFROM len=' + n + ' ---');
          console.log(txt.substring(0, 200));
        }
      } catch(e) {}
    }
  });
  console.log('[+] recvfrom() hooked');
}

var recvPtr = libc.findExportByName('recv');
if (recvPtr) {
  Interceptor.attach(recvPtr, {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
      var n = retval.toInt32();
      if (n <= 0 || n > 500) return;
      try {
        var data = this.buf.readByteArray(n);
        var bytes = new Uint8Array(data);
        var txt = '';
        for (var i = 0; i < bytes.length; i++) {
          var b = bytes[i];
          if (b === 10) { txt += '\n'; continue; }
          if (b >= 32 && b < 127) { txt += String.fromCharCode(b); continue; }
          txt += '.';
        }
        if (txt.length > 5 && /[A-Za-z0-9]/.test(txt)) {
          console.log('\n--- RECV len=' + n + ' ---');
          console.log(txt.substring(0, 200));
        }
      } catch(e) {}
    }
  });
  console.log('[+] recv() hooked');
}

console.log('\n[*] Ready! Switch account in the game now...');
