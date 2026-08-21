// البحث عن DH prime في الذاكرة
// نبحث عن 0x7FFFFFFFFFFFFFFD أو قيمة أخرى قريبة
// ونهوك crypt.dhexchange لنرى النتائج الفعلية

Java.perform(function() {
    // AccountManager لالتقاط sessionId
    try {
        var AM = Java.use("com.onemt.sdk.user.base.AccountManager");
        AM.updateAccount.implementation = function(acc) {
            try {
                console.log("\n[SESSION] " + acc.getSessionId());
                console.log("[UID] " + acc.getUserId());
            } catch(e) {}
            return this.updateAccount(acc);
        };
    } catch(e) {}
});

// 1. البحث عن قيمة 0x7FFFFFFFFFFFFFFD في الوحدات المحملة
setTimeout(function() {
    try {
        var modules = Process.enumerateModules();
        var target = null;
        
        // نبحث عن الوحدة التي تحتوي على crypt functions
        for (var i = 0; i < modules.length; i++) {
            var m = modules[i];
            if (m.name.indexOf("cocos") > -1 || m.name.indexOf("game") > -1 || 
                m.name.indexOf("boe") > -1 || m.name.indexOf("script") > -1) {
                console.log("[MODULE] " + m.name + " @ " + m.base + " size=" + m.size);
                target = m;
            }
        }
        
        // 2. هوك crypt.dhexchange عبر البحث عن Pattern
        // من skynet lcrypt.c: dhexchange = pack64(buf, powmod(G, key, P))
        // G=5 هو constant في الكود
        
        // ابحث عن الـ prime الثابت 0xFFFFFFFFFFFFFD في الذاكرة
        var primes_to_search = [
            { value: ptr("0x7FFFFFFFFFFFFFFD"), name: "2^63-3" },
            { value: ptr("0xFFFFFFFFFFFFFFC5"), name: "2^64-59" },
        ];
        
        if (target) {
            console.log("[*] Searching in " + target.name);
            try {
                // بحث عن bytes الـ prime
                var p1 = new Uint8Array([0xFD, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x7F]); // LE
                var p2 = new Uint8Array([0x7F, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFD]); // BE
                
                [p1, p2].forEach(function(pattern, idx) {
                    try {
                        var results = Memory.scanSync(target.base, target.size, 
                            pattern.reduce(function(s, b) { 
                                return s + (b < 16 ? '0' : '') + b.toString(16) + ' '; 
                            }, '').trim());
                        
                        if (results.length > 0) {
                            console.log("[PRIME FOUND " + (idx===0?"LE":"BE") + "] at " + results[0].address);
                        }
                    } catch(e2) {
                        console.log("scan error: " + e2.message.substring(0,50));
                    }
                });
            } catch(e) {
                console.log("search error: " + e.message.substring(0,50));
            }
        }
    } catch(e) {
        console.log("module error: " + e.message);
    }
}, 3000);

// 3. هوك connect للـ login server + هوك send/write
var libc = Module.load("libc.so");
var sendFn = libc.getExportByName("send");
var loginFd = -1;

var connectFn = libc.getExportByName("connect");
Interceptor.attach(connectFn, {
    onEnter: function(args) {
        try {
            var family = args[1].readU16();
            if (family === 2) {
                var port = ((args[1].add(2).readU8() << 8) | args[1].add(3).readU8());
                if (port === 10000) {
                    loginFd = args[0].toInt32();
                    console.log("\n[LOGIN-FD=" + loginFd + "] connecting to port 10000");
                }
            }
        } catch(e) {}
    }
});

Interceptor.attach(sendFn, {
    onEnter: function(args) {
        var fd = args[0].toInt32();
        var len = args[2].toInt32();
        if (fd === loginFd && len > 3 && len < 500) {
            try {
                var s = Memory.readUtf8String(args[1], len);
                if (s) console.log("[SEND→10000] " + s.trim());
            } catch(e) {}
        }
    }
});

var recvFn = libc.getExportByName("recv");
Interceptor.attach(recvFn, {
    onEnter: function(a) { this.fd = a[0].toInt32(); this.buf = a[1]; },
    onLeave: function(ret) {
        var len = ret.toInt32();
        if (this.fd === loginFd && len > 3 && len < 500) {
            try {
                var s = Memory.readUtf8String(this.buf, len);
                if (s) console.log("[RECV←10000] " + s.trim());
            } catch(e) {}
        }
    }
});

console.log("[*] Hooks ready - login now");
