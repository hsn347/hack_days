// التسجيل يبدأ بعد 15 ثانية ويستمر 10 ثوانٍ فقط
// جهّز إرسال الجيش خلال الـ 15 ثانية واضغط إرسال فوراً

var counter = 0;

function readHex(ptr, len) {
    var hex = "";
    var ascii = "";
    var max = len < 80 ? len : 80;
    for (var i = 0; i < max; i++) {
        var b = ptr.add(i).readU8();
        var h = b.toString(16);
        if (h.length === 1) h = "0" + h;
        hex = hex + h + " ";
        if (b >= 32 && b <= 126) {
            ascii = ascii + String.fromCharCode(b);
        } else {
            ascii = ascii + ".";
        }
    }
    return "HEX: " + hex + "\nASC: " + ascii;
}

var libc = Process.getModuleByName("libc.so");
var recording = false;

var writeFn = libc.findExportByName("write");
if (writeFn) {
    Interceptor.attach(writeFn, {
        onEnter: function(args) {
            if (!recording) return;
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            if (fd > 10 && len > 30 && len < 5000) {
                counter++;
                try {
                    var data = Memory.readUtf8String(args[1], len < 300 ? len : 300);
                    console.log("\n=== W #" + counter + " fd=" + fd + " len=" + len + " ===\n" + data);
                } catch(e) {
                    console.log("\n=== W #" + counter + " fd=" + fd + " len=" + len + " ===\n" + readHex(args[1], len));
                }
            }
        }
    });
}

var sendtoFn = libc.findExportByName("sendto");
if (sendtoFn) {
    Interceptor.attach(sendtoFn, {
        onEnter: function(args) {
            if (!recording) return;
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            if (fd > 10 && len > 30 && len < 5000) {
                counter++;
                try {
                    var data = Memory.readUtf8String(args[1], len < 300 ? len : 300);
                    console.log("\n=== S #" + counter + " fd=" + fd + " len=" + len + " ===\n" + data);
                } catch(e) {
                    console.log("\n=== S #" + counter + " fd=" + fd + " len=" + len + " ===\n" + readHex(args[1], len));
                }
            }
        }
    });
}

console.log("[+] Hooks installed (PAUSED)");
console.log("[!] Recording starts in 15 seconds...");
console.log("[!] Prepare your action NOW!\n");

// عد تنازلي
setTimeout(function() { console.log("[...] 10 seconds left..."); }, 5000);
setTimeout(function() { console.log("[...] 5 seconds left..."); }, 10000);

// بدء التسجيل بعد 15 ثانية
setTimeout(function() {
    recording = true;
    console.log("\n>>> RECORDING NOW! Do your action! <<<\n");
}, 15000);

// إيقاف التسجيل بعد 25 ثانية (10 ثوانٍ تسجيل)
setTimeout(function() {
    recording = false;
    console.log("\n>>> STOPPED. Total packets: " + counter + " <<<\n");
}, 25000);
