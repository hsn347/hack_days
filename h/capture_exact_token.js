/**
 * capture_exact_token.js
 * يعمل hook داخل ldesencode بعد قراءة الـ arguments مباشرة
 * - @ 0x746874 (بعد BL luaL_checklstring أول): x0 = plaintext_ptr
 * - @ 0x746898 (بعد BL luaL_checklstring ثاني): x0 = key_ptr (8 bytes DH secret)
 * 
 * شغّل Script ثم بدّل حساب في اللعبة
 */
'use strict';

// ====================================================
// Offsets من libcocos2dlua.so (ARM64, verified)
// ====================================================
var OFFSETS = {
    ldesencode_entry:      0x74682C,
    // بعد أول BL (luaL_checklstring arg1 = plaintext)
    after_first_bl:        0x746874,
    // بعد ثاني BL (luaL_checklstring arg2 = key)
    after_second_bl:       0x746898,
    // entry points أخرى مفيدة
    ldhsecret:             0x7470BC,
    lhmac64:               0x746E20,
    ldhexchange:           0x746FE4,
    lbase64encode:         0x747170,
};

var cocos_base = null;
var plaintext_ptr_saved = null;
var call_count = 0;

// ====================================================
function hookAtBase(base) {
    cocos_base = base;
    console.log('[+] Hooking ldesencode internals @ base=' + base);

    // ---- Hook entry of ldesencode ----
    var entry_addr = base.add(OFFSETS.ldesencode_entry);
    try {
        Interceptor.attach(entry_addr, {
            onEnter: function(args) {
                call_count++;
                this.call_id = call_count;
                // args[0] = lua_State* L
                this.L = args[0];
                console.log('\n[ldesencode #' + this.call_id + '] called');
            }
        });
        console.log('[+] ldesencode entry hooked @ ' + entry_addr);
    } catch(e) {
        console.log('[-] ldesencode entry: ' + e);
    }

    // ---- Hook after first luaL_checklstring (plaintext) ----
    var after_bl1_addr = base.add(OFFSETS.after_first_bl);
    try {
        Interceptor.attach(after_bl1_addr, {
            onEnter: function(args) {
                // عند هذه النقطة: x0 = plaintext_ptr (returned from luaL_checklstring)
                // في ARM64، Interceptor.attach على instruction عشوائية يعطي context
                // this.context.x0 = plaintext_ptr
                try {
                    var ptr = this.context.x0;
                    plaintext_ptr_saved = ptr;

                    // اقرأ حتى 300 bytes أو null terminator
                    var bytes = [];
                    var printable = '';
                    var hex = '';
                    for (var i = 0; i < 300; i++) {
                        try {
                            var b = ptr.add(i).readU8();
                            bytes.push(b);
                            hex += ('0' + b.toString(16)).slice(-2);
                            printable += (b >= 32 && b < 127) ? String.fromCharCode(b) : '.';
                            if (b === 0) break;  // null terminator
                        } catch(e2) { break; }
                    }

                    console.log('[+] PLAINTEXT (' + (bytes.length-1) + ' chars):');
                    console.log('    ASCII: ' + printable);
                    console.log('    HEX:   ' + hex.substring(0, 80));
                    if (hex.length > 80) {
                        console.log('           ' + hex.substring(80, 160));
                        if (hex.length > 160) {
                            console.log('           ' + hex.substring(160));
                        }
                    }
                } catch(e) {
                    console.log('[-] plaintext read error: ' + e);
                }
            }
        });
        console.log('[+] After-BL1 hooked @ ' + after_bl1_addr);
    } catch(e) {
        console.log('[-] after_first_bl: ' + e);
    }

    // ---- Hook after second luaL_checklstring (key = DH secret) ----
    var after_bl2_addr = base.add(OFFSETS.after_second_bl);
    try {
        Interceptor.attach(after_bl2_addr, {
            onEnter: function(args) {
                try {
                    var key_ptr = this.context.x0;

                    // اقرأ 8 bytes للـ DES key (= DH secret)
                    var key_bytes = key_ptr.readByteArray(8);
                    var key_arr = new Uint8Array(key_bytes);
                    var key_hex = Array.from(key_arr).map(function(b) {
                        return ('0' + b.toString(16)).slice(-2);
                    }).join('');
                    var key_b64 = btoa(String.fromCharCode.apply(null, key_arr));

                    console.log('[+] DES KEY (= DH Secret): ' + key_hex + ' b64=' + key_b64);

                    // تحقق من الـ plaintext_ptr المحفوظ
                    if (plaintext_ptr_saved) {
                        try {
                            var len_check = 0;
                            while (plaintext_ptr_saved.add(len_check).readU8() !== 0 && len_check < 500) {
                                len_check++;
                            }
                            console.log('[+] Plaintext length (null scan): ' + len_check);
                        } catch(e) {}
                    }
                } catch(e) {
                    console.log('[-] key read error: ' + e);
                }
            }
        });
        console.log('[+] After-BL2 hooked @ ' + after_bl2_addr);
    } catch(e) {
        console.log('[-] after_second_bl: ' + e);
    }

    // ---- Hook ldhsecret to get DH secret at computation time ----
    var dhs_addr = base.add(OFFSETS.ldhsecret);
    try {
        var dhs_captured = false;
        Interceptor.attach(dhs_addr, {
            onEnter: function(args) {
                this.L = args[0];
            },
            onLeave: function(retval) {
                if (dhs_captured) return;
                // لقراءة الـ result من الـ Lua stack
                // نحاول قراءة من الـ lua_State->top - 16 bytes
                try {
                    var L = this.L;
                    // Lua 5.3 64-bit: lua_State->top at offset 16
                    var top = L.add(16).readPointer();
                    // TValue size = 16, last value = top - 16
                    var last_tv = top.sub(16);
                    // gc pointer (first 8 bytes of TValue)
                    var gc = last_tv.readPointer();
                    // TString data starts at offset 24
                    var str_data = gc.add(24);
                    var bytes = str_data.readByteArray(8);
                    var arr = new Uint8Array(bytes);
                    var hex = Array.from(arr).map(function(b) {
                        return ('0' + b.toString(16)).slice(-2);
                    }).join('');
                    var b64 = btoa(String.fromCharCode.apply(null, arr));
                    console.log('\n[ldhsecret] DH SECRET from Lua stack: ' + hex + ' b64=' + b64);
                    dhs_captured = true;
                } catch(e) {
                    // try offset 32
                    try {
                        var L2 = this.L;
                        var top2 = L2.add(16).readPointer();
                        var last_tv2 = top2.sub(16);
                        var gc2 = last_tv2.readPointer();
                        var str_data2 = gc2.add(32);
                        var bytes2 = str_data2.readByteArray(8);
                        var arr2 = new Uint8Array(bytes2);
                        var hex2 = Array.from(arr2).map(function(b) {
                            return ('0' + b.toString(16)).slice(-2);
                        }).join('');
                        console.log('\n[ldhsecret] offset32: ' + hex2);
                    } catch(e2) {}
                }
            }
        });
        console.log('[+] ldhsecret hooked @ ' + dhs_addr);
    } catch(e) {
        console.log('[-] ldhsecret: ' + e);
    }

    // ---- Hook lhmac64 (to capture challenge + DH secret) ----
    var hmac_addr = base.add(OFFSETS.lhmac64);
    try {
        Interceptor.attach(hmac_addr, {
            onEnter: function(args) {
                this.L = args[0];
                // نحاول قراءة arg 1 و 2 من الـ stack
                // (يحتاج Lua stack reading - سيضاف لاحقاً)
                console.log('\n[lhmac64] called');
            }
        });
        console.log('[+] lhmac64 hooked @ ' + hmac_addr);
    } catch(e) {
        console.log('[-] lhmac64: ' + e);
    }

    console.log('\n[*] ALL HOOKS SET. Switch account in game now!');
}

// ====================================================
// Main: check if libcocos2dlua.so is loaded
// ====================================================
console.log('[*] capture_exact_token.js starting...');

try {
    var mod = Process.getModuleByName('libcocos2dlua.so');
    console.log('[+] libcocos2dlua.so FOUND @ ' + mod.base + ' size=' + mod.size);
    hookAtBase(mod.base);
} catch(e) {
    console.log('[-] libcocos2dlua.so not loaded yet');
    console.log('[*] Hooking dlopen to catch it...');

    // Hook android_dlopen_ext
    var dlopen_fn = Module.findExportByName(null, 'android_dlopen_ext') ||
                    Module.findExportByName(null, '__loader_android_dlopen_ext') ||
                    Module.findExportByName(null, 'dlopen');

    if (dlopen_fn) {
        console.log('[+] dlopen found @ ' + dlopen_fn);
        Interceptor.attach(dlopen_fn, {
            onEnter: function(args) {
                try { this.name = args[0].readCString(); } catch(e2) { this.name = ''; }
            },
            onLeave: function(retval) {
                if (this.name && this.name.indexOf('libcocos2dlua') !== -1) {
                    console.log('\n[!] libcocos2dlua.so is being loaded!');
                    // delay slightly for linker to finish
                    setTimeout(function() {
                        try {
                            var m = Process.getModuleByName('libcocos2dlua.so');
                            hookAtBase(m.base);
                        } catch(e2) {
                            // try using retval directly as base
                            try { hookAtBase(retval); } catch(e3) {}
                        }
                    }, 200);
                }
            }
        });
        console.log('[+] dlopen hooked - enter game world to load engine');
    } else {
        console.log('[!] dlopen not found!');
    }
}
