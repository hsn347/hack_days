/**
 * find_crypt_symbols.js
 * يبحث في libtcb.so عبر enumerateSymbols (ليس فقط exports)
 * ويعمل memory scan للعثور على ldhsecret/ldesencode
 */
'use strict';

var tcb = null;
try {
    tcb = Process.getModuleByName('libtcb.so');
    console.log('[+] libtcb.so @ ' + tcb.base + ' size=' + tcb.size);
} catch(e) {
    console.log('[-] ' + e); 
}

if (tcb) {
    // 1. جرّب enumerateSymbols (يشمل internal symbols)
    try {
        var syms = tcb.enumerateSymbols();
        console.log('[*] Total symbols: ' + syms.length);
        
        var found = [];
        for (var i = 0; i < syms.length; i++) {
            var s = syms[i];
            var n = (s.name || '').toLowerCase();
            if (n.indexOf('dh') !== -1 || n.indexOf('des') !== -1 || 
                n.indexOf('hmac') !== -1 || n.indexOf('crypt') !== -1 ||
                n.indexOf('lua') !== -1 || n.indexOf('hash') !== -1 ||
                n.indexOf('rand') !== -1 || n.indexOf('skynet') !== -1 ||
                n.indexOf('gate') !== -1 || n.indexOf('secret') !== -1 ||
                n.indexOf('encode') !== -1 || n.indexOf('decode') !== -1) {
                console.log('[SYM] ' + s.name + ' @ ' + s.address + ' type=' + s.type);
                found.push(s);
            }
        }
        
        if (found.length === 0) {
            console.log('[!] No crypt symbols found - printing all symbols:');
            for (var i = 0; i < Math.min(syms.length, 200); i++) {
                console.log('  ' + syms[i].name + ' @ ' + syms[i].address);
            }
        }
    } catch(e) {
        console.log('[!] enumerateSymbols failed: ' + e);
    }

    // 2. Memory scan لـ string "dhsecret" أو "desencode" في الـ binary
    console.log('\n[*] Scanning memory for crypt strings...');
    var base = tcb.base;
    var size = tcb.size;

    var patterns = ['ldhsecret', 'ldesencode', 'lhmac64', 'dhsecret', 'desencode', 'hmac64', 'randomkey', 'dhexchange'];
    
    for (var pi = 0; pi < patterns.length; pi++) {
        var pat = patterns[pi];
        try {
            var matches = Memory.scanSync(base, size, pat.split('').map(function(c) {
                return c.charCodeAt(0).toString(16).padStart(2, '0');
            }).join(' '));
            
            if (matches.length > 0) {
                console.log('[FOUND] "' + pat + '":');
                matches.forEach(function(m) {
                    console.log('  @ ' + m.address + ' (offset=' + m.address.sub(base) + ')');
                    // اقرأ السياق
                    try {
                        var ctx = m.address.readByteArray(64);
                        var bytes = new Uint8Array(ctx);
                        var s = '';
                        for (var j = 0; j < bytes.length; j++) {
                            var b = bytes[j];
                            s += (b >= 32 && b < 127) ? String.fromCharCode(b) : '.';
                        }
                        console.log('  Context: ' + s);
                    } catch(e2) {}
                });
            }
        } catch(e) {
            // ignore
        }
    }

    // 3. ابحث عن string table - تسلسل ASCII strings في الـ binary
    console.log('\n[*] Scanning for ASCII strings containing crypt keywords...');
    try {
        var keywords = ['dh', 'des', 'hmac', 'crypt', 'lua', 'secret', 'encode', 'skynet', 'gate', 'token'];
        Memory.scan(base, size, '6c 64 68', {  // "ldh" in hex
            onMatch: function(addr, size2) {
                try {
                    var s = addr.readUtf8String(20);
                    if (s && s.length > 3) {
                        console.log('[STRING] @ ' + addr + ' offset=' + addr.sub(base) + ': ' + s);
                    }
                } catch(e) {}
            },
            onError: function(r) {},
            onComplete: function() { console.log('[*] Scan done'); }
        });
    } catch(e) {
        console.log('[!] Scan error: ' + e);
    }
}
