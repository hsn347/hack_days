// التقاط DH exchange بالكامل من native code
// يلتقط: challenge bytes, client key, server key, secret, HMAC الفعلي
// لمعرفة الـ parameters الصحيحة لـ skynet crypt

Java.perform(function() {
    // AccountManager - لمعرفة sessionId
    try {
        var AccountManager = Java.use("com.onemt.sdk.user.base.AccountManager");
        AccountManager.updateAccount.implementation = function(account) {
            try {
                var sessionId = account.getSessionId ? account.getSessionId() : "?";
                var userId    = account.getUserId    ? account.getUserId()    : "?";
                console.log("\n[ACCOUNT] userId=" + userId + "\n  sessionId=" + sessionId);
            } catch(e2) {}
            return this.updateAccount(account);
        };
        console.log("[+] AccountManager.updateAccount hooked");
    } catch(e) { console.log("[-] AccountManager: " + e.message.substring(0,60)); }
});

// Hook send() لالتقاط كل ما يُرسل للـ login server
var libc = Module.load("libc.so");
var sendFn = libc.getExportByName("send");
var recvFn = libc.getExportByName("recv");

// تتبع الـ fd المتصل بـ port 10000
var loginFd = -1;
var capturedLines = [];

var connectFn = libc.getExportByName("connect");
Interceptor.attach(connectFn, {
    onEnter: function(args) {
        try {
            var family = args[1].readU16();
            if (family === 2) {
                var port = ((args[1].add(2).readU8() << 8) | args[1].add(3).readU8());
                if (port === 10000) {
                    loginFd = args[0].toInt32();
                    console.log("\n[LOGIN-CONNECT] fd=" + loginFd + " port=" + port);
                    capturedLines = [];
                }
            }
        } catch(e) {}
    }
});
console.log("[+] connect() hooked");

// Hook send
Interceptor.attach(sendFn, {
    onEnter: function(args) {
        var fd = args[0].toInt32();
        var len = args[2].toInt32();
        if (fd === loginFd && len > 3 && len < 500) {
            try {
                var s = Memory.readUtf8String(args[1], len);
                console.log("[SEND→LOGIN] " + s.trim());
            } catch(e) {}
        }
    }
});
console.log("[+] send() hooked");

// Hook recv
Interceptor.attach(recvFn, {
    onLeave: function(retval) {
        var len = retval.toInt32();
        if (len > 3 && len < 500) {
            try {
                // نقرأ من الـ buffer - args[1]
                var s = Memory.readUtf8String(ptr(this.context.x1), len);
                if (s && s.indexOf("=") > -1) {
                    console.log("[RECV←LOGIN] " + s.trim());
                }
            } catch(e) {}
        }
    },
    onEnter: function(args) {
        this._fd = args[0].toInt32();
    }
});
console.log("[+] recv() hooked");

console.log("\n[*] جاهز - اخرج من اللعبة ثم أعد الدخول وسجّل بـ email+password\n");
