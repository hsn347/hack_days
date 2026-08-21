/**
 * capture_token_plaintext.js
 * ينتظر تحميل libcocos2dlua.so ثم يعمل hook على:
 *   ldesencode @ 0x74682C  → يلتقط plaintext + DH_key
 *   ldhsecret  @ 0x7470BC  → يلتقط الـ DH secret مباشرة
 *   lhmac64    @ 0x746E20  → يلتقط challenge + DH_secret
 *
 * الاستخدام: بعد تشغيل الـ script قم بتبديل الحساب في اللعبة
 */
'use strict';

// Offsets في libcocos2dlua.so (ARM64)
var OFFSETS = {
    ldesencode:   0x74682C,
    ldesdecode:   0x746A54,
    lhmac64:      0x746E20,
    ldhexchange:  0x746FE4,
    ldhsecret:    0x7470BC,
    lrandomkey:   0x746794,
};

var cocos_base = null;

// ============================================================
// قراءة string من Lua stack
// ============================================================
function readLuaString(L, idx) {
    /**
     * بنية Lua 5.3 lua_State (64-bit ARM):
     *   offset 0:  GCObject* next (8 bytes)
     *   offset 8:  lu_byte tt, marked (2 bytes)
     *   offset 10: lu_byte status (1 byte)
     *   offset 11: 5 bytes padding
     *   offset 16: StkId top  ← pointer للـ top of stack
     *   offset 24: global_State* l_G
     *   offset 32: CallInfo* ci
     *   offset 40: StkId stack_last
     *   offset 48: StkId stack  ← base of stack
     * 
     * TValue size = 16 bytes (value_=8, tt_=4, pad=4)
     * 
     * LUA_TSTRING = 4 (Lua 5.3 internal)
     * 
     * TString header (64-bit):
     *   offset 0:  GCObject* next (8)
     *   offset 8:  lu_byte tt (1)
     *   offset 9:  lu_byte marked (1)
     *   offset 10: lu_byte extra (1)
     *   offset 11: lu_byte shrlen (1) [short strings]
     *   offset 12: unsigned hash (4)
     *   offset 16: (depends: UTString union / lnglen for long)
     * Data starts at offset ~24 or ~32
     */
    try {
        // StkId base = lua_State->stack (offset 48)
        var stack_base = L.add(48).readPointer();
        // StkId top = lua_State->top (offset 16)
        var stack_top = L.add(16).readPointer();

        // حساب index للـ stack
        // Lua positive index: 1 = first arg = stack_base + ci->func + 1
        // Simpler: negative index -1 = top-1
        
        var TVALUE_SIZE = 16;
        var tval_ptr;
        
        if (idx > 0) {
            // CallInfo* ci (offset 32 in lua_State)
            var ci = L.add(32).readPointer();
            // ci->func هو pointer للـ function TValue (offset 0 في CallInfo)
            // CallInfo layout: StkId base(0), StkId func(8), StkId top(16)...
            var ci_func = ci.add(8).readPointer();  // ci->func
            // arg idx هو ci->func + idx
            tval_ptr = ci_func.add(idx * TVALUE_SIZE);
        } else {
            // negative: top + idx (idx is negative)
            tval_ptr = stack_top.add(idx * TVALUE_SIZE);
        }

        // TValue: value_ (8 bytes) + tt_ (4 bytes) + padding (4 bytes)
        var value_gc = tval_ptr.readPointer();  // GCObject* (string pointer)
        var tt = tval_ptr.add(8).readS32();     // type tag

        var LUA_TSTRING = 4;
        var LUA_TSHRSTR = 4; // Lua 5.3: short string tag = 4
        var LUA_TLNGSTR = 20; // long string tag = 20

        if ((tt & 0x0F) !== LUA_TSTRING && tt !== LUA_TLNGSTR) {
            return null; // ليس string
        }

        // TString header:
        // offset 0: next (8)
        // offset 8: tt(1) + marked(1) + extra(1) + shrlen(1)
        // offset 12: hash (4)
        // offset 16: data starts here for short strings? Or:
        // offset 16: lnglen (8) for long strings
        // offset 24: hnext (8) for long strings
        // Then data...
        
        // For short strings (shrlen in offset 11):
        // Data at offset 16 after header of 16 bytes? 
        // Actually TString on 64-bit Lua 5.3:
        // sizeof(UTString) = 24 (with union padding)
        // Data starts at TString + 24

        // Try offset 24 first (common for 64-bit Lua 5.3)
        var data_ptr = value_gc.add(24);
        var str = data_ptr.readCString();
        return str;
    } catch(e) {
        return null;
    }
}

// ============================================================
// Hook functions عند تحميل libcocos2dlua.so
// ============================================================
function hookCryptFunctions(base) {
    console.log('[*] Hooking crypt functions in libcocos2dlua.so @ ' + base);
    cocos_base = base;

    // ---- lhmac64 ----
    try {
        Interceptor.attach(base.add(OFFSETS.lhmac64), {
            onEnter: function(args) {
                this.L = args[0];
            },
            onLeave: function(retval) {
                try {
                    var msg = readLuaString(this.L, 1);
                    var key = readLuaString(this.L, 2);
                    if (msg && key) {
                        var msg_hex = Buffer.from(msg, 'binary').toString('hex');
                        var key_hex = Buffer.from(key, 'binary').toString('hex');
                        console.log('\n[lhmac64] msg=' + msg_hex + ' key=' + key_hex);
                        if (key.length === 8) {
                            console.log('  *** DH SECRET (from hmac64 key): ' + key_hex);
                        }
                    }
                } catch(e) {
                    console.log('[lhmac64] read error: ' + e);
                }
            }
        });
        console.log('[+] lhmac64 hooked');
    } catch(e) { console.log('[-] lhmac64: ' + e); }

    // ---- ldhsecret ----
    try {
        Interceptor.attach(base.add(OFFSETS.ldhsecret), {
            onEnter: function(args) {
                this.L = args[0];
                console.log('\n[ldhsecret] called');
            },
            onLeave: function(retval) {
                try {
                    // الـ result في top-1 بعد push
                    var secret = readLuaString(this.L, -1);
                    if (secret && secret.length === 8) {
                        var hex = Buffer.from(secret, 'binary').toString('hex');
                        console.log('  *** DH SECRET: ' + hex + ' b64=' + btoa(secret));
                    }
                } catch(e) {
                    console.log('[ldhsecret] result error: ' + e);
                }
            }
        });
        console.log('[+] ldhsecret hooked');
    } catch(e) { console.log('[-] ldhsecret: ' + e); }

    // ---- ldesencode ----
    try {
        Interceptor.attach(base.add(OFFSETS.ldesencode), {
            onEnter: function(args) {
                this.L = args[0];
                try {
                    var plain = readLuaString(this.L, 1);
                    var key = readLuaString(this.L, 2);
                    
                    if (plain) {
                        var printable = plain.replace(/[^\x20-\x7e]/g, '.');
                        console.log('\n[ldesencode] plaintext(' + plain.length + '): ' + printable);
                        // Hex dump للبيانات الثنائية
                        var hex = Buffer.from(plain, 'binary').toString('hex');
                        console.log('  hex: ' + hex.substring(0, 80) + (hex.length > 80 ? '...' : ''));
                    }
                    if (key && key.length === 8) {
                        var key_hex = Buffer.from(key, 'binary').toString('hex');
                        console.log('  *** DES KEY (=DH secret): ' + key_hex);
                    }
                } catch(e) {
                    console.log('[ldesencode] args error: ' + e);
                }
            }
        });
        console.log('[+] ldesencode hooked');
    } catch(e) { console.log('[-] ldesencode: ' + e); }

    // ---- ldhexchange ----
    try {
        Interceptor.attach(base.add(OFFSETS.ldhexchange), {
            onEnter: function(args) {
                this.L = args[0];
                console.log('\n[ldhexchange] called (DH key gen)');
            }
        });
        console.log('[+] ldhexchange hooked');
    } catch(e) { console.log('[-] ldhexchange: ' + e); }
}

// ============================================================
// Hook dlopen لكشف متى تُحمَّل libcocos2dlua.so
// ============================================================
function hookDlopen() {
    // جرب android_dlopen_ext أولاً
    var dlopen_fn = Module.findExportByName(null, 'android_dlopen_ext') || 
                    Module.findExportByName(null, 'dlopen');

    if (!dlopen_fn) {
        console.log('[!] dlopen not found');
        return;
    }

    console.log('[+] Hooking dlopen @ ' + dlopen_fn);
    
    Interceptor.attach(dlopen_fn, {
        onEnter: function(args) {
            try { this.path = args[0].readCString(); } catch(e) { this.path = ''; }
        },
        onLeave: function(retval) {
            if (this.path && this.path.indexOf('libcocos2dlua') !== -1) {
                console.log('\n[!] libcocos2dlua.so loaded! @ ' + retval);
                var mod = Process.findModuleByAddress(retval);
                if (mod) {
                    console.log('    Base: ' + mod.base + ' Size: ' + mod.size);
                    setTimeout(function() { hookCryptFunctions(mod.base); }, 100);
                }
            }
        }
    });
}

// ============================================================
// تحقق هل محملة بالفعل؟
// ============================================================
console.log('[*] Starting capture_token_plaintext.js');
console.log('[*] Looking for libcocos2dlua.so...');

try {
    var mod = Process.getModuleByName('libcocos2dlua.so');
    console.log('[+] Already loaded @ ' + mod.base);
    hookCryptFunctions(mod.base);
} catch(e) {
    console.log('[-] Not loaded yet - waiting via dlopen hook...');
    hookDlopen();
}

console.log('[*] Ready - switch account in game to capture token!');
