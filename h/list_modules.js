/**
 * list_modules.js - يعدد كل الـ modules المحملة في البروسس
 * ويبحث عن functions متعلقة بـ crypt/dh/des
 */
'use strict';

var modules = Process.enumerateModules();
console.log('[*] Total modules: ' + modules.length);
console.log('[*] Looking for crypt/lua related...\n');

for (var i = 0; i < modules.length; i++) {
    var m = modules[i];
    var name = m.name.toLowerCase();
    
    // أي module قد يحتوي على Lua أو crypt
    if (name.indexOf('lua') !== -1 || name.indexOf('crypt') !== -1 || 
        name.indexOf('cocos') !== -1 || name.indexOf('game') !== -1 ||
        name.indexOf('onemt') !== -1 || name.indexOf('koh') !== -1 ||
        name.indexOf('skynet') !== -1 || name.indexOf('libmain') !== -1) {
        console.log('[MODULE] ' + m.name + ' @ ' + m.base + ' size=' + m.size);
        
        // ابحث عن exports
        try {
            var exports = m.enumerateExports();
            for (var j = 0; j < exports.length; j++) {
                var e = exports[j];
                var ename = (e.name || '').toLowerCase();
                if (ename.indexOf('dh') !== -1 || ename.indexOf('des') !== -1 || 
                    ename.indexOf('hmac') !== -1 || ename.indexOf('lua') !== -1 ||
                    ename.indexOf('crypt') !== -1) {
                    console.log('  [EXPORT] ' + e.name + ' @ ' + e.address);
                }
            }
        } catch(e) {}
    }
}

// طباعة كل الـ modules
console.log('\n[*] ALL modules:');
for (var i = 0; i < modules.length; i++) {
    var m = modules[i];
    console.log('  ' + m.name + ' (size=' + m.size + ')');
}
