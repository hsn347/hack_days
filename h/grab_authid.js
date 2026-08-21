/**
 * grab_authid.js
 * يلتقط userSDKManager.authId مباشرة
 * هذا هو الـ subtoken الحقيقي المستخدم في login_dec.lua
 * 
 * شغّله: frida -D emulator-5554 --attach-pid PID -l grab_authid.js
 * ثم ادخل اللعبة بشكل طبيعي
 */
'use strict';

console.log('[*] grab_authid.js - التقاط authId من SDK');
console.log('[*] ادخل اللعبة أو بدّل حسابك...');
console.log('');

Java.perform(function() {
    
    // ====================================================
    // Hook 1: AccountManager - جلب الـ session مباشرة
    // ====================================================
    var classes = [
        'com.onemt.base.manager.AccountManager',
        'com.onemt.base.AccountManager',
        'com.onemt.sdk.AccountManager',
    ];
    
    classes.forEach(function(cls) {
        try {
            var Cls = Java.use(cls);
            // Hook كل methods إرجاع String
            var methods = Cls.class.getDeclaredMethods();
            methods.forEach(function(m) {
                var name = m.getName();
                var retType = m.getReturnType().getName();
                if (retType === 'java.lang.String' || retType === 'String') {
                    try {
                        Cls[name].implementation = function() {
                            var r = this[name].apply(this, arguments);
                            if (r && r.length > 30 && r.length < 200) {
                                console.log('[' + cls.split('.').pop() + '.' + name + '] ' + r.substring(0,80));
                            }
                            return r;
                        };
                    } catch(e2) {}
                }
            });
            console.log('[+] Hooked: ' + cls);
        } catch(e) {}
    });

    // ====================================================
    // Hook 2: loginCtrl.token.subtoken assignment
    // شغّل frida مع libcocos2dlua.so loaded
    // ====================================================

    // ====================================================
    // Hook 3: Lua crypt.desencode - يعطينا الـ token plaintext
    // الـ drawback: يعمل فقط بعد تحميل libcocos2dlua.so
    // ====================================================
    
    // ====================================================
    // Hook 4: Java String passing to native (JNI bridge)
    // ====================================================
    try {
        // hook أي class يحتوي authId أو sessionId
        var scanClasses = Java.enumerateLoadedClassesSync();
        var targets = [];
        scanClasses.forEach(function(c) {
            if ((c.indexOf('onemt') !== -1 || c.indexOf('sdk') !== -1) &&
                c.indexOf('Manager') !== -1) {
                targets.push(c);
            }
        });
        
        console.log('[*] ONEMT Manager classes found:');
        targets.forEach(function(t) { console.log('  ' + t); });
        
        // حاول hook كل واحد
        targets.forEach(function(cls) {
            try {
                var C = Java.use(cls);
                ['getAuthId','getSessionId','getSession','getToken',
                 'getSubToken','authId','sessionId'].forEach(function(field) {
                    try {
                        C[field].implementation = function() {
                            var r = this[field]();
                            if (r && r.toString().length > 20) {
                                console.log('\n[' + cls.split('.').pop() + '.' + field + '] =' + r.toString().substring(0,100));
                            }
                            return r;
                        };
                    } catch(e) {}
                });
            } catch(e) {}
        });
    } catch(e) { console.log('[-] Scan error: ' + e); }
    
    // ====================================================
    // Hook 5: String constructor / intern (catch all session strings)
    // ====================================================
    try {
        // hook SharedPreferences to get stored session
        var sp = Java.use('android.content.SharedPreferences');
        // هذا abstract، نحتاج hook implementation
    } catch(e) {}
    
    // ====================================================
    // Hook 6: connect() TCP للـ login server port 10000
    // يعطينا session من write() payload
    // ====================================================
    var libc = Process.getModuleByName('libc.so');
    var writeFn = libc.findExportByName('write');
    var login_fd = -1;
    
    // Hook connect لمعرفة fd للـ login server
    var connectFn = libc.findExportByName('connect');
    Interceptor.attach(connectFn, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            try {
                var sa = args[1];
                var family = sa.readU16();
                if (family === 2) {
                    var port = (sa.add(2).readU8() << 8) | sa.add(3).readU8();
                    var ip = [sa.add(4),sa.add(5),sa.add(6),sa.add(7)].map(function(p){return p.readU8();}).join('.');
                    if (port === 10000) {
                        console.log('\n[!] Login server connected: ' + ip + ':' + port + ' fd=' + fd);
                        login_fd = fd;
                    }
                }
            } catch(e) {}
        }
    });
    
    // Hook write لالتقاط ما يُرسل للـ login server
    var write_count = 0;
    Interceptor.attach(writeFn, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            if (len < 5 || len > 2000) return;
            
            // أي fd لـ game servers
            try {
                var data = args[1].readUtf8String(Math.min(len, 500));
                if (!data) return;
                
                // رسائل DH (base64 قصيرة)
                if (data.length < 20 && /^[A-Za-z0-9+/=]+$/.test(data.trim())) {
                    write_count++;
                    console.log('[write#' + write_count + ' fd=' + fd + '] DH: ' + data.trim());
                }
                // Token (@ separator، طويل)
                else if (data.indexOf('@') !== -1 && len > 30) {
                    console.log('\n[!] TOKEN SENT (fd=' + fd + ' len=' + len + '):');
                    var parts = data.split('@');
                    console.log('  Parts count: ' + parts.length);
                    // Decode Part 1 (token)
                    if (parts[0]) {
                        try {
                            // Part1 هو base64(DES(token_string))
                            // نطبعه كـ b64 فقط
                            console.log('  Part1 b64 (' + parts[0].length + ' chars): ' + parts[0].substring(0,40) + '...');
                        } catch(e2) {}
                    }
                }
            } catch(e) {}
        }
    });
    
    // Hook read لالتقاط challenge
    var readFn = libc.findExportByName('read');
    Interceptor.attach(readFn, {
        onLeave: function(retval) {
            var n = retval.toInt32();
            if (n < 5 || n > 200) return;
            try {
                var data = this.context.x1.readCString();
                if (!data) return;
                // DH messages
                if (/^[A-Za-z0-9+/=\n]+$/.test(data.trim()) && data.trim().length > 5) {
                    console.log('[read] Server: ' + data.trim().substring(0,50));
                }
            } catch(e) {}
        }
    });
    
    console.log('[+] All hooks set. Enter game now!');
});
