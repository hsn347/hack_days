/**
 * capture_dh_java.js
 * يلتقط DH secret من خلال Java bridge لأن libtcb.so هو ARM32 عبر Houdini
 * الاستراتيجية: hook الـ Java functions التي تتعامل مع login
 */
'use strict';

Java.perform(function() {
    console.log('[*] Searching for DH/login related Java classes...');
    
    // 1. Hook أي method فيه "dh" أو "secret" أو "token"
    var classesFound = [];
    
    // AccountManager - هذا نعرفه
    try {
        var AM = Java.use('com.onemt.sdk.user.base.AccountManager');
        AM.updateAccount.implementation = function(acc) {
            try {
                console.log('\n[SESSION] ' + acc.getSessionId());
                console.log('[UID]     ' + acc.getUserId());
            } catch(e) {}
            return this.updateAccount(acc);
        };
        console.log('[+] AccountManager hooked');
    } catch(e) { console.log('[-] AccountManager: ' + e); }

    // 2. ابحث عن LoginManager أو أي class فيها دالة DH
    var loginClasses = ['com.onemt.sdk.net.LoginManager',
                        'com.onemt.sdk.core.LoginService',
                        'com.onemt.sdk.auth.AuthManager',
                        'com.onemt.game.LoginManager',
                        'com.onemt.sdk.net.TCPClient',
                        'com.onemt.sdk.net.SocketManager'];
    
    loginClasses.forEach(function(cls) {
        try {
            var C = Java.use(cls);
            console.log('[+] Found class: ' + cls);
            var methods = C.class.getDeclaredMethods();
            for (var i = 0; i < methods.length; i++) {
                console.log('  Method: ' + methods[i].getName());
            }
        } catch(e) {}
    });

    // 3. ابحث عن PwdUtil (من capture سابق)
    try {
        var PU = Java.use('com.onemt.sdk.util.PwdUtil');
        var pwdMethods = PU.class.getDeclaredMethods();
        console.log('[+] PwdUtil methods:');
        for (var i = 0; i < pwdMethods.length; i++) {
            var m = pwdMethods[i];
            console.log('  ' + m.getName());
            // Hook all methods
            try {
                var mName = m.getName();
                PU[mName].implementation = function() {
                    var args = Array.prototype.slice.call(arguments);
                    console.log('[PwdUtil.' + mName + '] args: ' + JSON.stringify(args));
                    var result = this[mName].apply(this, args);
                    console.log('[PwdUtil.' + mName + '] result: ' + result);
                    return result;
                };
            } catch(e) {}
        }
    } catch(e) { console.log('[-] PwdUtil: ' + e); }

    // 4. ابحث عن verifySessionIdNew (من captures سابقة)
    try {
        var LM = Java.use('com.onemt.sdk.user.base.LoginManager');
        var lmMethods = LM.class.getDeclaredMethods();
        console.log('[+] LoginManager methods:');
        lmMethods.forEach(function(m) {
            console.log('  ' + m.getName());
        });
        
        LM.verifySessionIdNew.implementation = function(a1, a2, a3, a4, a5) {
            console.log('\n[verifySessionIdNew]');
            console.log('  type:    ' + a1);
            console.log('  email:   ' + a2);
            console.log('  uid:     ' + a3);
            console.log('  session: ' + a4);
            console.log('  auto:    ' + a5);
            return this.verifySessionIdNew(a1, a2, a3, a4, a5);
        };
        console.log('[+] verifySessionIdNew hooked');
    } catch(e) { console.log('[-] LoginManager: ' + e); }

    // 5. Hook أي String operations على login flow
    // ابحث عن Class التي تبني الـ token
    try {
        Java.enumerateLoadedClasses({
            onMatch: function(cls) {
                var n = cls.toLowerCase();
                if (n.indexOf('login') !== -1 || n.indexOf('auth') !== -1 || 
                    n.indexOf('socket') !== -1 || n.indexOf('tcp') !== -1 ||
                    n.indexOf('crypt') !== -1 || n.indexOf('token') !== -1) {
                    console.log('[CLASS] ' + cls);
                }
            },
            onComplete: function() {
                console.log('[*] Class enumeration done');
            }
        });
    } catch(e) {
        console.log('[!] Class enum error: ' + e);
    }
});
