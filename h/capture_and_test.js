/**
 * capture_and_test.js
 * يلتقط الـ session الجديدة ويحفظها في ملف
 * ثم نختبرها مباشرة مع onemt_bot.py
 * 
 * الاستخدام:
 *   frida -D emulator-5554 --attach-pid PID -l capture_and_test.js
 *   ثم بدّل الحساب في اللعبة
 */
'use strict';

var SESSION_FILE = '/sdcard/captured_session.txt';
var captured = {};

// ============================================================
// Java hooks: AccountManager + verifySessionIdNew
// ============================================================
Java.perform(function() {
    console.log('[*] Java hooks loading...');

    // Hook AccountManager.getSessionId() and related
    try {
        var acm = Java.use('com.onemt.base.manager.AccountManager');
        
        // حاول hook كل الـ methods المحتملة
        var methods = ['getSessionId','getSession','getCurrentSession',
                       'getUserId','getEmail','getUID'];
        methods.forEach(function(m) {
            try {
                acm[m].implementation = function() {
                    var r = this[m]();
                    if (r && r.toString().length > 10) {
                        console.log('[AccountManager.' + m + '] = ' + r.toString().substring(0,60));
                        captured[m] = r.toString();
                    }
                    return r;
                };
            } catch(e) {}
        });
    } catch(e) { console.log('[-] AccountManager: ' + e); }

    // Hook LoginManager.verifySessionIdNew
    try {
        var lm = Java.use('com.onemt.base.manager.LoginManager');
        var verify = lm.verifySessionIdNew;
        if (verify) {
            verify.implementation = function(a1,a2,a3,a4,a5) {
                console.log('\n[verifySessionIdNew]');
                console.log('  type    = ' + a1);
                console.log('  email   = ' + a2);
                console.log('  uid     = ' + a3);
                console.log('  session = ' + a4);
                console.log('  auto    = ' + a5);
                
                captured.login_type = '' + a1;
                captured.email      = '' + a2;
                captured.uid        = '' + a3;
                captured.session    = '' + a4;
                captured.auto       = '' + a5;
                
                saveCapture();
                return this.verifySessionIdNew(a1,a2,a3,a4,a5);
            };
            console.log('[+] verifySessionIdNew hooked');
        }
    } catch(e) { console.log('[-] verifySessionIdNew: ' + e.message); }

    // Hook PwdUtil or SDK auth methods
    try {
        var classes = Java.enumerateLoadedClassesSync();
        classes.forEach(function(cls) {
            if (cls.indexOf('onemt') !== -1 && 
                (cls.indexOf('Session') !== -1 || cls.indexOf('Auth') !== -1)) {
                console.log('[class] ' + cls);
            }
        });
    } catch(e) {}
});

// ============================================================
// Native hook: write() على socket port 10000
// ============================================================
var libc = Process.getModuleByName('libc.so');

// Hook connect لمعرفة الـ fd للـ login server
var login_fd = -1;
var connectFn = libc.findExportByName('connect');
if (connectFn) {
    Interceptor.attach(connectFn, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var sa = args[1];
            try {
                var family = sa.readU16();
                if (family === 2) {
                    var port = (sa.add(2).readU8() << 8) | sa.add(3).readU8();
                    var ip = [sa.add(4).readU8(), sa.add(5).readU8(),
                              sa.add(6).readU8(), sa.add(7).readU8()].join('.');
                    console.log('[connect] fd=' + fd + ' ' + ip + ':' + port);
                    if (port === 10000 || port === 4000) {
                        login_fd = fd;
                        captured.server_ip = ip;
                        captured.server_port = port;
                    }
                }
            } catch(e) {}
        }
    });
    console.log('[+] connect() hooked');
}

// Hook write لالتقاط الـ login token (نص ASCII)
var writeFn = libc.findExportByName('write');
if (writeFn) {
    var token_captured = false;
    Interceptor.attach(writeFn, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            if (fd !== login_fd || len < 10 || len > 2000 || token_captured) return;
            
            try {
                var data = args[1].readCString();
                if (!data) return;
                
                // الـ login token يحتوي '@' وطويل
                if (data.indexOf('@') !== -1 && len > 50) {
                    console.log('\n[LOGIN TOKEN SENT] len=' + len);
                    var parts = data.split('@');
                    parts.forEach(function(p, i) {
                        console.log('  Part' + (i+1) + ' (' + p.length + ' b64 chars): ' + p.substring(0,30) + '...');
                    });
                    captured.raw_token = data;
                    token_captured = true;
                    saveCapture();
                }
                // DH messages (short base64 strings)
                else if (len < 20 && data.trim().length > 0) {
                    console.log('[DH send] ' + data.trim());
                }
            } catch(e) {}
        }
    });
    console.log('[+] write() hooked');
}

// Hook read/recv لالتقاط responses
var readFn = libc.findExportByName('read');
if (readFn) {
    Interceptor.attach(readFn, {
        onLeave: function(retval) {
            var n = retval.toInt32();
            if (n <= 0 || n > 1000) return;
            try {
                var data = this.context.x1.readCString();
                if (data && (data.indexOf('200') !== -1 || data.indexOf('401') !== -1 || data.indexOf('challenge') !== -1)) {
                    console.log('[LOGIN RESP] ' + data.substring(0,80));
                    captured.server_response = data;
                }
            } catch(e) {}
        }
    });
    console.log('[+] read() hooked');
}

// ============================================================
// حفظ البيانات
// ============================================================
function saveCapture() {
    if (!captured.session) return;
    
    var content = [
        '# ONEMT Session Capture - ' + new Date().toISOString(),
        'LOGIN_TYPE=' + (captured.login_type || 'email'),
        'EMAIL=' + (captured.email || ''),
        'UID=' + (captured.uid || ''),
        'SESSION=' + (captured.session || ''),
        'AUTO=' + (captured.auto || 'true'),
        'SERVER_IP=' + (captured.server_ip || ''),
        'SERVER_PORT=' + (captured.server_port || ''),
    ].join('\n');
    
    console.log('\n' + '='.repeat(50));
    console.log('CAPTURED SESSION DATA:');
    console.log(content);
    console.log('='.repeat(50));
    console.log('\nNow run: python E:\\osmanli\\token_format_tester_v2.py');
    console.log('with the new SESSION above');
}

console.log('[*] Ready - switch account or login now!');
