// التقاط Login - نسخة مستقرة نهائية

Java.perform(function() {
    console.log("\n[*] التقاط Login - ONEMT v4\n");

    // 1. PwdUtil - password → MD5
    try {
        var PwdUtil = Java.use("com.onemt.sdk.user.base.util.PwdUtil");
        PwdUtil.encryptSDKPwd.implementation = function(pwd) {
            var result = this.encryptSDKPwd(pwd);
            console.log("\n[PWD] plain=" + pwd + "  md5=" + result);
            return result;
        };
        console.log("[+] PwdUtil hooked");
    } catch(e) { console.log("[-] PwdUtil: " + e.message.substring(0,80)); }

    // 2. LoginManager.verifySessionIdNew
    try {
        var LoginManager = Java.use("com.onemt.sdk.user.base.LoginManager");
        LoginManager.verifySessionIdNew.implementation = function(a0,a1,a2,a3,a4,a5,a6,a7,a8) {
            console.log("\n[!!!] verifySessionIdNew -> token/authId مُلتقط!");
            console.log("  a1=" + a1);
            console.log("  a2=" + a2);
            console.log("  a3=" + a3);
            console.log("  a4=" + a4);
            console.log("  a5=" + a5);
            return this.verifySessionIdNew(a0,a1,a2,a3,a4,a5,a6,a7,a8);
        };
        console.log("[+] LoginManager.verifySessionIdNew hooked");
    } catch(e) { console.log("[-] LoginManager: " + e.message.substring(0,80)); }

    // 3. AccountManager.updateAccount - يُحدَّث بعد login ناجح
    try {
        var AccountManager = Java.use("com.onemt.sdk.user.base.AccountManager");
        AccountManager.updateAccount.implementation = function(account) {
            try {
                console.log("\n[ACCOUNT updated] " + account.toString());
            } catch(e2) {}
            return this.updateAccount(account);
        };
        console.log("[+] AccountManager.updateAccount hooked");
    } catch(e) { console.log("[-] AccountManager.updateAccount: " + e.message.substring(0,60)); }

    // 4. Native connect() - التقاط Login Server TCP IP:Port
    try {
        var connectFn = Module.findExportByName("libc.so", "connect");
        Interceptor.attach(connectFn, {
            onEnter: function(args) {
                try {
                    var family = args[1].readU16();
                    if (family === 2) {
                        var port = ((args[1].add(2).readU8() << 8) | args[1].add(3).readU8());
                        var b = args[1].add(4);
                        var ip = b.readU8()+"."+b.add(1).readU8()+"."+b.add(2).readU8()+"."+b.add(3).readU8();
                        if (port !== 443 && port !== 80 && port !== 53 && port > 1000 && !ip.startsWith("8.8") && !ip.startsWith("127") && !ip.startsWith("0.0")) {
                            console.log("\n[TCP-CONNECT] " + ip + ":" + port);
                        }
                    }
                } catch(e) {}
            }
        });
        console.log("[+] connect() hooked");
    } catch(e) { console.log("[-] connect: " + e.message); }

    // 5. com.android.okhttp.Call - التقاط HTTP requests
    try {
        var OkCall = Java.use("com.android.okhttp.Call");
        OkCall.execute.implementation = function() {
            var resp = this.execute();
            try {
                var req = this.request();
                var url = req.url().toString();
                console.log("\n[HTTP] " + req.method() + " " + url);
                // body
                var body = req.body();
                if (body) {
                    var Buffer = Java.use("com.android.okio.Buffer");
                    var buf = Buffer.$new();
                    body.writeTo(buf);
                    var bodyStr = buf.readUtf8();
                    if (bodyStr && bodyStr.length > 0) {
                        console.log("[HTTP-BODY] " + bodyStr.substring(0, 500));
                    }
                }
                // response
                if (resp) {
                    var rbody = resp.body();
                    if (rbody) {
                        var rStr = rbody.string();
                        console.log("[HTTP-RSP] " + rStr.substring(0, 500));
                    }
                }
            } catch(e2) {
                console.log("[HTTP-ERR] " + e2.message.substring(0,80));
            }
            return resp;
        };
        console.log("[+] OkHttp.Call.execute hooked");
    } catch(e) { console.log("[-] OkHttpCall: " + e.message.substring(0,80)); }

    console.log("\n[*] جاهز - سجّل الدخول بـ email+password الآن\n");
});
