// الهدف الرئيسي: الحصول على الـ secret الحقيقي من crypt.dhsecret
// والـ HMAC الذي أرسله اللعبة للـ login server

Java.perform(function() {
    try {
        var AM = Java.use("com.onemt.sdk.user.base.AccountManager");
        AM.updateAccount.implementation = function(acc) {
            try { console.log("\n[SESSION] " + acc.getSessionId()); } catch(e) {}
            return this.updateAccount(acc);
        };
    } catch(e) {}
});

// طريقة جديدة: ابحث عن __write في libc وفي libcocos2dlua
var loginFd = -1;
var captureActive = false;
var capturedData = {challenge: null, client_pub: null, server_pub: null, hmac: null, secret: null};

// hook connect لتحديد fd الـ login server
var libc = Process.getModuleByName('libc.so');
var connectFn = libc.findExportByName('connect')
             || libc.findExportByName('__connect')
             || Module.findExportByName(null, 'connect');

if (connectFn) {
    Interceptor.attach(connectFn, {
        onEnter: function(args) {
            try {
                var family = args[1].readU16();
                if (family === 2) {
                    var port = ((args[1].add(2).readU8() << 8) | args[1].add(3).readU8());
                    if (port === 10000) {
                        loginFd = args[0].toInt32();
                        captureActive = true;
                        console.log('\n[LOGIN-FD=' + loginFd + '] Connected to port 10000');
                    }
                }
            } catch(e) {}
        }
    });
    console.log('[+] connect() hooked @ ' + connectFn);
} else {
    console.log('[-] connect() not found - will match all fds');
    captureActive = true;  // التقط كل شيء إذا لم نجد connect
    loginFd = -2;          // -2 يعني: لا تفلتر
}

// ابحث عن write function - تجرب كل الأسماء الممكنة
var writeAddr = null;
var writeNames = ["write", "__write", "__write_chk", "write_real", "sys_write"];
for (var i = 0; i < writeNames.length; i++) {
    var addr = Module.findExportByName(null, writeNames[i]);
    if (addr) {
        console.log("[+] Found write as: " + writeNames[i] + " @ " + addr);
        writeAddr = addr;
        break;
    }
}

if (writeAddr) {
    Interceptor.attach(writeAddr, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            if ((loginFd === -2 || fd === loginFd) && len > 3 && len < 3000 && captureActive) {
                try {
                    var raw = Memory.readByteArray(args[1], Math.min(len, 2048));
                    var bytes = new Uint8Array(raw);
                    var s = '';
                    for (var bi = 0; bi < bytes.length; bi++) {
                        var b = bytes[bi];
                        if (b >= 32 && b < 127) s += String.fromCharCode(b);
                        else if (b === 10) s += '\n';
                        else s += '.';
                    }
                    var trimmed = s.trim();
                    if (trimmed.length > 0) {
                        console.log('[WRITE->LOGIN len=' + len + '] ' + trimmed.substring(0, 1000));
                    }
                } catch(e) { console.log('[WRITE err] ' + e); }
            }
        }
    });
    console.log('[+] write() hooked');
}

// أيضاً hook sendto
var sendtoAddr = libc.findExportByName('sendto');
if (sendtoAddr) {
    Interceptor.attach(sendtoAddr, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            if ((loginFd === -2 || fd === loginFd) && len > 3 && len < 3000 && captureActive) {
                try {
                    var raw = Memory.readByteArray(args[1], Math.min(len, 2048));
                    var bytes = new Uint8Array(raw);
                    var s = '';
                    for (var bi = 0; bi < bytes.length; bi++) {
                        var b = bytes[bi];
                        if (b >= 32 && b < 127) s += String.fromCharCode(b);
                        else if (b === 10) s += '\n';
                        else s += '.';
                    }
                    var trimmed = s.trim();
                    if (trimmed.length > 0) {
                        console.log('[SENDTO->LOGIN len=' + len + '] ' + trimmed.substring(0, 1000));
                    }
                } catch(e) {}
            }
        }
    });
    console.log("[+] sendto() hooked");
}

var recvfromAddr = libc.findExportByName("recvfrom");
if (recvfromAddr) {
    Interceptor.attach(recvfromAddr, {
        onEnter: function(args) { this.fd = args[0].toInt32(); this.buf = args[1]; },
        onLeave: function(ret) {
            var len = ret.toInt32();
            if (this.fd === loginFd && len > 3 && captureActive) {
                try {
                    var raw = Memory.readByteArray(this.buf, Math.min(len, 2048));
                    var bytes = new Uint8Array(raw);
                    var s = '';
                    for (var bi = 0; bi < bytes.length; bi++) {
                        var b = bytes[bi];
                        if (b >= 32 && b < 127) s += String.fromCharCode(b);
                        else if (b === 10) s += '\n';
                        else s += '.';
                    }
                    var trimmed = s.trim();
                    if (trimmed.length > 0) console.log('[RECVFROM<-LOGIN len=' + len + '] ' + trimmed.substring(0, 500));
                } catch(e) {}
            }
        }
    });
    console.log('[+] recvfrom() hooked');
}

// read hook
var readAddr = Module.findExportByName(null, "read");
if (readAddr) {
    Interceptor.attach(readAddr, {
        onEnter: function(args) { this.fd = args[0].toInt32(); this.buf = args[1]; },
        onLeave: function(ret) {
            var len = ret.toInt32();
            if (this.fd === loginFd && len > 3 && captureActive) {
                try {
                    var raw = Memory.readByteArray(this.buf, Math.min(len, 2048));
                    var bytes = new Uint8Array(raw);
                    var s = '';
                    for (var bi = 0; bi < bytes.length; bi++) {
                        var b = bytes[bi];
                        if (b >= 32 && b < 127) s += String.fromCharCode(b);
                        else if (b === 10) s += '\n';
                        else s += '.';
                    }
                    var trimmed = s.trim();
                    if (trimmed.length > 0) console.log('[READ<-LOGIN len=' + len + '] ' + trimmed.substring(0, 500));
                } catch(e) {}
            }
        }
    });
    console.log('[+] read() hooked');
}


// هوك libcocos2dlua.so write
var cocos = Module.findBaseAddress("libcocos2dlua.so");
if (cocos) {
    console.log("[+] libcocos2dlua.so @ " + cocos);
    
    // ابحث عن write في libcocos2dlua نفسه
    try {
        var cocosWrite = cocos.add(0).findExportByName ? 
            Process.findModuleByName("libcocos2dlua.so").findExportByName("write") : null;
        if (cocosWrite) {
            console.log("[+] write in cocos @ " + cocosWrite);
        }
    } catch(e) {}
} else {
    console.log("[-] libcocos2dlua.so not loaded yet");
    // محاولة بعد تأخير
    setTimeout(function() {
        var cocos2 = Module.findBaseAddress("libcocos2dlua.so");
        if (cocos2) console.log("[+] libcocos2dlua.so @ " + cocos2 + " (delayed)");
    }, 5000);
}

console.log("\n[*] جاهز - سجّل الدخول بـ email+password\n");
