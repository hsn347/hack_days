/**
 * hook_dh_secret.js
 * يبحث في libtcb.so عن ldhsecret/ldesencode/lhmac64
 * ويعمل hook لالتقاط DH secret والـ token plaintext
 */
'use strict';

// ابحث عن libtcb.so
var tcb = null;
try {
    tcb = Process.getModuleByName('libtcb.so');
    console.log('[+] libtcb.so @ ' + tcb.base + ' size=' + tcb.size);
} catch(e) {
    console.log('[-] libtcb.so not found: ' + e);
}

if (tcb) {
    // عدّد كل الـ exports
    var exports = tcb.enumerateExports();
    console.log('[*] Total exports in libtcb.so: ' + exports.length);
    
    var cryptFuncs = [];
    for (var i = 0; i < exports.length; i++) {
        var e = exports[i];
        var n = (e.name || '').toLowerCase();
        if (n.indexOf('dh') !== -1 || n.indexOf('des') !== -1 || 
            n.indexOf('hmac') !== -1 || n.indexOf('crypt') !== -1 ||
            n.indexOf('lua') !== -1 || n.indexOf('hash') !== -1 ||
            n.indexOf('key') !== -1 || n.indexOf('rand') !== -1) {
            console.log('[CRYPT] ' + e.name + ' @ ' + e.address);
            cryptFuncs.push(e);
        }
    }
    
    // طباعة كل الـ exports (قد تكون كثيرة لكن مهمة)
    console.log('\n[*] All exports from libtcb.so:');
    for (var i = 0; i < exports.length; i++) {
        console.log('  ' + exports[i].name + ' @ ' + exports[i].address);
    }
    
    // ابحث عن lua_State أو luaopen للتأكد أنه Lua library
    var luaExports = exports.filter(function(e) {
        return (e.name || '').toLowerCase().indexOf('lua') !== -1;
    });
    console.log('\n[*] Lua-related exports: ' + luaExports.length);
    luaExports.forEach(function(e) {
        console.log('  ' + e.name);
    });
}
