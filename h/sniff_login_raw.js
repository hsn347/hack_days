/**
 * sniff_login_raw.js
 * يلتقط كل بايت يُرسل ويُستقبل من/إلى login server (port 10000)
 * بدون فلترة — كل شيء يُطبع
 * 
 * شغّله ثم ادخل اللعبة (ادخل عالم):
 *   frida -D emulator-5554 --attach-pid PID -l sniff_login_raw.js
 */
'use strict';

var login_fds = {};  // fd → {ip, port}
var libc = Process.getModuleByName('libc.so');

// ====================================================
// Hook connect() — تتبع كل fd لـ port 10000
// ====================================================
Interceptor.attach(libc.findExportByName('connect'), {
    onEnter: function(args) {
        var fd = args[0].toInt32();
        try {
            var sa = args[1];
            if (sa.readU16() === 2) {
                var port = (sa.add(2).readU8() << 8) | sa.add(3).readU8();
                var ip = [4,5,6,7].map(function(o){return sa.add(o).readU8();}).join('.');
                if (port === 10000) {
                    login_fds[fd] = {ip: ip, port: port};
                    console.log('\n[CONNECT] fd=' + fd + ' → ' + ip + ':' + port);
                }
            }
        } catch(e) {}
    }
});

// ====================================================
// Hook write/send — التقط كل ما يُرسل
// ====================================================
function onWrite(fd, buf, len) {
    if (!login_fds[fd]) return;
    if (len <= 0 || len > 5000) return;
    
    try {
        var bytes = buf.readByteArray(len);
        var arr = new Uint8Array(bytes);
        
        // حاول قراءة كـ ASCII
        var ascii = '';
        var hex = '';
        for (var i = 0; i < arr.length; i++) {
            ascii += (arr[i] >= 32 && arr[i] < 127) ? String.fromCharCode(arr[i]) : '.';
            hex += ('0' + arr[i].toString(16)).slice(-2);
        }
        
        console.log('\n[SEND fd=' + fd + ' len=' + len + ']');
        console.log('  ASCII: ' + ascii);
        if (len < 200) {
            console.log('  HEX:   ' + hex);
        } else {
            console.log('  HEX:   ' + hex.substring(0, 100) + '...');
        }
        
        // هل يحتوي @ ؟ (= token)
        if (ascii.indexOf('@') !== -1 && len > 30) {
            console.log('\n  *** TOKEN DETECTED ***');
            var parts = ascii.split('@');
            console.log('  Parts: ' + parts.length);
            for (var p = 0; p < parts.length; p++) {
                console.log('  Part' + (p+1) + ' (' + parts[p].length + ' chars): ' + parts[p].substring(0, 60));
            }
        }
    } catch(e) {}
}

['write', 'send', 'sendto'].forEach(function(fn) {
    var ptr = libc.findExportByName(fn);
    if (ptr) {
        Interceptor.attach(ptr, {
            onEnter: function(args) {
                onWrite(args[0].toInt32(), args[1], args[2].toInt32());
            }
        });
    }
});

// ====================================================
// Hook read/recv — التقط كل ما يُستقبل
// ====================================================
function onRead(fd, buf, ret) {
    if (!login_fds[fd]) return;
    if (ret <= 0 || ret > 5000) return;
    
    try {
        var bytes = buf.readByteArray(ret);
        var arr = new Uint8Array(bytes);
        var ascii = '';
        for (var i = 0; i < arr.length; i++) {
            ascii += (arr[i] >= 32 && arr[i] < 127) ? String.fromCharCode(arr[i]) : '.';
        }
        console.log('\n[RECV fd=' + fd + ' len=' + ret + ']');
        console.log('  ASCII: ' + ascii);
    } catch(e) {}
}

['read', 'recv', 'recvfrom'].forEach(function(fn) {
    var ptr = libc.findExportByName(fn);
    if (ptr) {
        Interceptor.attach(ptr, {
            onEnter: function(args) {
                this.fd = args[0].toInt32();
                this.buf = args[1];
            },
            onLeave: function(retval) {
                onRead(this.fd, this.buf, retval.toInt32());
            }
        });
    }
});

// ====================================================
// أيضاً hook writev (بعض التطبيقات تستخدمه)
// ====================================================
var writevFn = libc.findExportByName('writev');
if (writevFn) {
    Interceptor.attach(writevFn, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            if (!login_fds[fd]) return;
            var iov = args[1];
            var cnt = args[2].toInt32();
            for (var i = 0; i < Math.min(cnt, 5); i++) {
                var base = iov.add(i * Process.pointerSize * 2).readPointer();
                var len = iov.add(i * Process.pointerSize * 2 + Process.pointerSize).readULong();
                if (len > 0 && len < 5000) {
                    onWrite(fd, base, len);
                }
            }
        }
    });
}

console.log('[*] sniff_login_raw.js loaded');
console.log('[*] Hooks: connect, write, send, sendto, read, recv, recvfrom, writev');
console.log('[*] Now enter the game (switch account or enter a world)');
console.log('[*] All traffic to port 10000 will be captured');
