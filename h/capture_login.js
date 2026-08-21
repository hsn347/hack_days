/**
 * capture_secret.js - يلتقط DH secret من ldhsecret في libcocos2dlua.so
 * يعمل مع Frida 17 على x64 emulator مع ARM64 Houdini
 */
'use strict';

// نتائج سابقة (لا تغيير فيها)
Java.perform(function() {
    try {
        var AM = Java.use('com.onemt.sdk.user.base.AccountManager');
        AM.updateAccount.implementation = function(acc) {
            try {
                console.log('\n[SESSION] ' + acc.getSessionId());
                console.log('[UID]     ' + acc.getUserId());
            } catch(e) {}
            return this.updateAccount(acc);
        };
    } catch(e) {}
});

// ابحث عن libcocos2dlua.so
var cocos = null;
try { cocos = Process.getModuleByName('libcocos2dlua.so'); } catch(e) {}
if (!cocos) {
    console.log('[-] libcocos2dlua.so not found');
} else {
    console.log('[+] libcocos2dlua.so @ ' + cocos.base);
    
    // ابحث عن exports المتعلقة بـ crypt
    var exports = cocos.enumerateExports();
    var found = [];
    for (var i = 0; i < exports.length; i++) {
        var e = exports[i];
        if (e.name && (e.name.indexOf('dh') !== -1 || e.name.indexOf('des') !== -1 || e.name.indexOf('hmac') !== -1 || e.name.indexOf('crypt') !== -1)) {
            console.log('[EXPORT] ' + e.name + ' @ ' + e.address);
            found.push(e);
        }
    }
    
    if (found.length === 0) {
        console.log('[*] No crypt exports found - scanning for Lua C functions...');
        // ابحث عن lua_pushstring / lua_tolstring لالتقاط الـ strings
    }
}

// hook connect لمعرفة loginFd
var loginFd = -1;
var capturing = false;
var gateFd = -1;
var gateCapturing = false;

var libc = Process.getModuleByName('libc.so');
var connectPtr = libc.findExportByName('connect');
if (connectPtr) {
    Interceptor.attach(connectPtr, {
        onEnter: function(args) {
            try {
                var sa = args[1]; var family = sa.readU16();
                if (family === 2) {
                    var port = (sa.add(2).readU8() << 8) | sa.add(3).readU8();
                    if (port === 10000) {
                        loginFd = args[0].toInt32();
                        capturing = true;
                        console.log('\n[CONNECT-LOGIN] fd=' + loginFd + ' port=10000');
                    } else if (port === 4000) {
                        gateFd = args[0].toInt32();
                        gateCapturing = true;
                        console.log('\n[CONNECT-GATE] fd=' + gateFd + ' port=4000');
                    }
                }
            } catch(e) {}
        }
    });
    console.log('[+] connect() hooked');
}

// hook write (DH client pub + HMAC + TOKEN)
var writePtr = libc.findExportByName('write');
if (writePtr) {
    var msgCount = 0;
    Interceptor.attach(writePtr, {
        onEnter: function(args) {
            if (!capturing || loginFd === -1) return;
            var fd = args[0].toInt32();
            if (fd !== loginFd) return;
            var len = args[2].toInt32();
            if (len < 4 || len > 2000) return;
            try {
                var raw = args[1].readByteArray(Math.min(len, 1500));
                var bytes = new Uint8Array(raw);
                var s = '';
                for (var i = 0; i < bytes.length; i++) {
                    var b = bytes[i];
                    if (b >= 32 && b < 127) s += String.fromCharCode(b);
                    else if (b === 10) s += '\n';
                    else s += '.';
                }
                msgCount++;
                console.log('\n[SEND #' + msgCount + ' len=' + len + ']\n' + s.trim().substring(0, 1000));
            } catch(e) {}
        }
    });
    console.log('[+] write() hooked');
}

// hook sendto
var sendtoPtr = libc.findExportByName('sendto');
if (sendtoPtr) {
    var msgCount2 = 0;
    Interceptor.attach(sendtoPtr, {
        onEnter: function(args) {
            if (!capturing || loginFd === -1) return;
            var fd = args[0].toInt32();
            if (fd !== loginFd) return;
            var len = args[2].toInt32();
            if (len < 4 || len > 2000) return;
            try {
                var raw = args[1].readByteArray(Math.min(len, 1500));
                var bytes = new Uint8Array(raw);
                var s = '';
                for (var i = 0; i < bytes.length; i++) {
                    var b = bytes[i];
                    if (b >= 32 && b < 127) s += String.fromCharCode(b);
                    else if (b === 10) s += '\n';
                    else s += '.';
                }
                msgCount2++;
                console.log('\n[SENDTO #' + msgCount2 + ' len=' + len + ']\n' + s.trim().substring(0, 1000));
            } catch(e) {}
        }
    });
    console.log('[+] sendto() hooked');
}

// hook read/recvfrom (server responses)
var readPtr = libc.findExportByName('read');
if (readPtr) {
    Interceptor.attach(readPtr, {
        onEnter: function(args) { this.fd = args[0].toInt32(); this.buf = args[1]; },
        onLeave: function(ret) {
            if (!capturing || loginFd === -1 || this.fd !== loginFd) return;
            var n = ret.toInt32();
            if (n < 4 || n > 500) return;
            try {
                var raw = this.buf.readByteArray(n);
                var bytes = new Uint8Array(raw);
                var s = '';
                for (var i = 0; i < bytes.length; i++) {
                    var b = bytes[i];
                    if (b >= 32 && b < 127) s += String.fromCharCode(b);
                    else if (b === 10) s += '\n';
                    else s += '.';
                }
                console.log('\n[RECV len=' + n + '] ' + s.trim().substring(0, 300));
            } catch(e) {}
        }
    });
    console.log('[+] read() hooked');
}

var recvfromPtr = libc.findExportByName('recvfrom');
if (recvfromPtr) {
    Interceptor.attach(recvfromPtr, {
        onEnter: function(args) { this.fd = args[0].toInt32(); this.buf = args[1]; },
        onLeave: function(ret) {
            if (!capturing || loginFd === -1 || this.fd !== loginFd) return;
            var n = ret.toInt32();
            if (n < 4 || n > 500) return;
            try {
                var raw = this.buf.readByteArray(n);
                var bytes = new Uint8Array(raw);
                var s = '';
                for (var i = 0; i < bytes.length; i++) {
                    var b = bytes[i];
                    if (b >= 32 && b < 127) s += String.fromCharCode(b);
                    else if (b === 10) s += '\n';
                    else s += '.';
                }
                console.log('\n[RECVFROM len=' + n + '] ' + s.trim().substring(0, 300));
            } catch(e) {}
        }
    });
    console.log('[+] recvfrom() hooked');
}

// ============================================================
// Gate capture (port 4000)
// ============================================================
function dumpBytes(buf, len, label) {
    try {
        var raw = buf.readByteArray(Math.min(len, 512));
        var bytes = new Uint8Array(raw);
        var hex = '';
        var asc = '';
        for (var i = 0; i < bytes.length; i++) {
            hex += ('0' + bytes[i].toString(16)).slice(-2) + ' ';
            asc += (bytes[i] >= 32 && bytes[i] < 127) ? String.fromCharCode(bytes[i]) : '.';
        }
        console.log('\n' + label + ' len=' + len);
        console.log('HEX: ' + hex.substring(0, 200));
        console.log('ASC: ' + asc.substring(0, 100));
    } catch(e) {}
}

// write على gate
if (writePtr) {
    // already attached, just need to add gate check inside
}
// sendto على gate - نعيد attach مع gateFd
// بدلاً من ذلك نستخدم نفس hook ونضيف gate check
// read hook للـ gate reds
if (readPtr) {
    // نستخدم نفس interceptor مع إضافة gate check
}

// الحل: نضيف interceptors جديدة منفصلة
var writePtr2 = libc.findExportByName('write');
if (writePtr2) {
    Interceptor.attach(writePtr2, {
        onEnter: function(args) {
            if (!gateCapturing || gateFd === -1) return;
            var fd = args[0].toInt32();
            if (fd !== gateFd) return;
            var len = args[2].toInt32();
            if (len < 1 || len > 2000) return;
            dumpBytes(args[1], len, '[GATE-SEND fd=' + fd + ']');
        }
    });
}

var recvPtr2 = libc.findExportByName('read');
if (recvPtr2) {
    Interceptor.attach(recvPtr2, {
        onEnter: function(args) { this.gfd = args[0].toInt32(); this.gbuf = args[1]; },
        onLeave: function(ret) {
            if (!gateCapturing || gateFd === -1 || this.gfd !== gateFd) return;
            var n = ret.toInt32();
            if (n < 1 || n > 2000) return;
            dumpBytes(this.gbuf, n, '[GATE-RECV fd=' + this.gfd + ']');
        }
    });
}

var sendtoPtr2 = libc.findExportByName('sendto');
if (sendtoPtr2) {
    Interceptor.attach(sendtoPtr2, {
        onEnter: function(args) {
            if (!gateCapturing || gateFd === -1) return;
            var fd = args[0].toInt32();
            if (fd !== gateFd) return;
            var len = args[2].toInt32();
            if (len < 1 || len > 2000) return;
            dumpBytes(args[1], len, '[GATE-SENDTO fd=' + fd + ']');
        }
    });
}

console.log('\n[*] Ready - switch account now\n');
