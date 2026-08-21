/**
 * find_capacity.js
 * يبحث في كود Cocos2d-JS عن دالة حساب سعة التدريب
 * ويعترض الـ send لقراءة armycount قبل الإرسال
 */
'use strict';

var libc = Process.getModuleByName('libc.so');
var XOR_KEY = "OSxHP.!-wd?'lao5";

function xorDecrypt(bytes) {
    var out = [];
    for (var i = 0; i < bytes.length; i++)
        out.push(bytes[i] ^ XOR_KEY.charCodeAt(i % XOR_KEY.length));
    return out;
}

// الطريقة 1: اعترض أي طلب تدريب (cmd=1005) من اللعبة نفسها
// وسجّل الـ armycount الذي تختاره اللعبة
console.log("[*] مراقبة طلبات التدريب من اللعبة...");
console.log("[*] افتح شاشة التدريب في اللعبة واضغط 'تدريب' بنفسك");
console.log("[*] سأعرض لك الـ armycount الذي اختارته اللعبة\n");

var gateFDs = {};

['send', 'sendto', 'write'].forEach(function(fn) {
    var ptr = libc.findExportByName(fn);
    if (!ptr) return;
    
    Interceptor.attach(ptr, {
        onEnter: function(a) {
            this.fd = a[0].toInt32();
            this.b = a[1];
            this.l = a[2].toInt32();
        },
        onLeave: function() {
            if (this.l < 6 || this.l > 65000) return;
            
            try {
                var bytes = Array.from(new Uint8Array(this.b.readByteArray(this.l)));
                
                // فك الحزمة
                var offset = 0;
                while (offset + 2 < bytes.length) {
                    var sz = (bytes[offset] << 8) | bytes[offset + 1];
                    if (sz < 4 || sz > 60000) break;
                    if (offset + 2 + sz > bytes.length) break;
                    
                    var raw = bytes.slice(offset + 2, offset + 2 + sz - 4);
                    var dec = xorDecrypt(raw);
                    var str = '';
                    for (var i = 0; i < dec.length; i++) {
                        if (dec[i] === 0) break;
                        str += String.fromCharCode(dec[i]);
                    }
                    
                    var j0 = str.indexOf('{');
                    if (j0 >= 0) {
                        try {
                            var parsed = JSON.parse(str.substring(j0));
                            var cmd = String(parsed.cmd || '').replace(/^onemt_/, '');
                            
                            if (cmd === '1005') {
                                console.log("\n╔══════════════════════════════════════╗");
                                console.log("║  🎯 طلب تدريب ملتقط من اللعبة!     ║");
                                console.log("╠══════════════════════════════════════╣");
                                console.log("║  subcmd:    " + parsed.subcmd);
                                if (parsed.data) {
                                    console.log("║  armycount: " + (parsed.data.armycount || 'N/A'));
                                    console.log("║  armyid:    " + (parsed.data.armyid || 'N/A'));
                                    console.log("║  bid:       " + (parsed.data.bid || 'N/A'));
                                    console.log("║  mode:      " + (parsed.data.mode || 'N/A'));
                                    console.log("║  isget:     " + parsed.data.isget);
                                }
                                console.log("╚══════════════════════════════════════╝");
                                console.log("\n[+] هذا هو العدد الأقصى! استخدمه في البوت.");
                            }
                        } catch(e) {}
                    }
                    offset += 2 + sz;
                }
            } catch(e) {}
        }
    });
});

console.log("[+] الهوكات جاهزة. افتح الثكنة واضغط تدريب بأقصى عدد!");
