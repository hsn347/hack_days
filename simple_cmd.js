// ============================================================
//  📡 أداة استعلام + عرض الرد في نفس التيرمنال
// ============================================================
//  عدّل CMD, SUBCMD, DATA → شغّل → المس اللعبة → يظهر الرد هنا
// ============================================================

// ╔══════════════════════════════════╗
// ║   عدّل هنا فقط ↓↓↓                ║
// ╚══════════════════════════════════╝

// frida -D emulator-5554 -n Empire -l "E:\osmanli\simple_cmd.js"

// أمثلة: 
// var CMD='1001'; var SUBCMD='1';  var DATA={};    
// var CMD='1007'; var SUBCMD='16';  var DATA={};                         // جلب UID اللاعب
var CMD='2058'; var SUBCMD='20';  var DATA={"heroId": 4110219};                         // مزامنة طوابير الخريطة المحلية
// var CMD='1010'; var SUBCMD='43'; var DATA={};   ء                      // سجل التحالف
// var CMD='1010'; var SUBCMD='81'; var DATA={uid:10598913};             // حالة التبرعات
// var CMD='1004'; var SUBCMD='1';  var DATA={};                         // الحقيبة
// var CMD='1017'; var SUBCMD='1';  var DATA={};                         // الأبحاث
// var CMD='1070'; var SUBCMD='1';  var DATA={};                         // حرب الغزو

// ╔══════════════════════════════════╗
// ║   لا تعدّل تحت هذا السطر          ║
// ╚══════════════════════════════════╝

var XOR_KEY = "OSxHP.!-wd?'lao5";
var sent = false;
var foundFd = -1;
var waiting = true;

function xorEncrypt(text, key) {
    var r = []; var j = 0;
    for (var i = 0; i < text.length; i++) {
        r.push(text.charCodeAt(i) ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return r;
}

function xorDecrypt(bytes, key) {
    var r = ''; var j = 0;
    for (var i = 0; i < bytes.length; i++) {
        r += String.fromCharCode(bytes[i] ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return r;
}

function buildCmd(cmd, subcmd, data, session) {
    var msg = JSON.stringify({cmd: 'onemt_' + cmd, subcmd: subcmd, data: data || {}});
    var x = xorEncrypt(msg, XOR_KEY);
    var sz = x.length + 4;
    var p = [(sz >> 8) & 0xFF, sz & 0xFF];
    for (var i = 0; i < x.length; i++) p.push(x[i] & 0xFF);
    p.push((session >> 24) & 0xFF, (session >> 16) & 0xFF, (session >> 8) & 0xFF, session & 0xFF);
    return p;
}

function sendPacket(fd, packet) {
    var libc = Process.getModuleByName("libc.so");
    var w = new NativeFunction(libc.findExportByName("write"), 'int', ['int', 'pointer', 'int']);
    var buf = Memory.alloc(packet.length);
    for (var i = 0; i < packet.length; i++) buf.add(i).writeU8(packet[i]);
    var r = w(fd, buf, packet.length);
    if (r <= 0) {
        var s = new NativeFunction(libc.findExportByName("send"), 'int', ['int', 'pointer', 'int', 'int']);
        r = s(fd, buf, packet.length, 0);
    }
    return r;
}

// فك تشفير وعرض حزمة واردة
function tryShowResponse(ptr, len) {
    if (!waiting || len < 20) return;
    try {
        // نجرب كل الأوفسيتات الممكنة للبداية (2 بايت حجم أو بدون)
        var offsets = [2, 0];
        for (var o = 0; o < offsets.length; o++) {
            var offset = offsets[o];
            if (offset >= len) continue;
            
            var bytes = [];
            for (var i = offset; i < len; i++) bytes.push(ptr.add(i).readU8());
            
            var decoded = xorDecrypt(bytes, XOR_KEY);
            
            // ابحث عن JSON يحتوي subcmd الخاص بطلبنا
            if (decoded.indexOf('"subcmd":"' + SUBCMD + '"') !== -1 ||
                decoded.indexOf('"subcmd": "' + SUBCMD + '"') !== -1) {
                
                var start = decoded.indexOf('{');
                var end = decoded.lastIndexOf('}');
                if (start >= 0 && end > start) {
                    try {
                        var json = JSON.parse(decoded.substring(start, end + 1));
                        waiting = false;
                        
                        console.log("\n╔══════════════════════════════════════╗");
                        console.log("║  📥 رد السيرفر                      ║");
                        console.log("╚══════════════════════════════════════╝");
                        console.log(JSON.stringify(json, null, 2));
                        console.log("════════════════════════════════════════\n");
                        return;
                    } catch(e) {}
                }
            }
            
            // fallback: أي JSON صالح فيه cmd
            if (decoded.indexOf('"cmd"') !== -1 && decoded.indexOf('"err"') !== -1) {
                var start2 = decoded.indexOf('{');
                var end2 = decoded.lastIndexOf('}');
                if (start2 >= 0 && end2 > start2) {
                    try {
                        var json2 = JSON.parse(decoded.substring(start2, end2 + 1));
                        // تحقق أنه نفس الأمر
                        if (json2.cmd === CMD || json2.subcmd === SUBCMD) {
                            waiting = false;
                            console.log("\n╔══════════════════════════════════════╗");
                            console.log("║  📥 رد السيرفر                      ║");
                            console.log("╚══════════════════════════════════════╝");
                            console.log(JSON.stringify(json2, null, 2));
                            console.log("════════════════════════════════════════\n");
                            return;
                        }
                    } catch(e) {}
                }
            }
        }
    } catch(e) {}
}

// ======= Hooks =======
var libc = Process.getModuleByName("libc.so");

console.log("\n📡 أداة استعلام + عرض الرد");
console.log("→ cmd=" + CMD + " subcmd=" + SUBCMD + " data=" + JSON.stringify(DATA));
console.log("→ المس أي زر في اللعبة...\n");

// مراقبة الإرسال (لاكتشاف fd وإرسال الاستعلام)
['write', 'send'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), {
        onEnter: function(args) {
            if (sent) return;
            var len = args[2].toInt32();
            var fd = args[0].toInt32();
            if (len < 10 || len > 2000 || fd <= 3) return;
            try {
                if (args[1].add(2).readU8() === 0x34) {
                    var s0=args[1].add(len-4).readU8(), s1=args[1].add(len-3).readU8();
                    var s2=args[1].add(len-2).readU8(), s3=args[1].add(len-1).readU8();
                    var session = ((s0<<24)|(s1<<16)|(s2<<8)|s3) >>> 0;
                    sent = true;
                    foundFd = fd;
                    
                    var packet = buildCmd(CMD, SUBCMD, DATA, session + 1);
                    var r = sendPacket(fd, packet);
                    console.log("📤 أُرسل cmd=" + CMD + " subcmd=" + SUBCMD + " (" + r + " bytes)");
                    console.log("⏳ ننتظر الرد...\n");
                }
            } catch(e) {}
        }
    });
});

// مراقبة الاستقبال (لعرض الرد)
['read', 'recv'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), {
        onEnter: function(args) {
            this.buf = args[1];
            this.fd = args[0].toInt32();
        },
        onLeave: function(retval) {
            var len = retval.toInt32();
            if (len > 20 && waiting && sent) {
                tryShowResponse(this.buf, len);
            }
        }
    });
});

// مؤقت احتياطي
setTimeout(function() {
    if (waiting && sent) {
        console.log("⚠️ لم يصل رد خلال 15 ثانية. جرب تحقق من live_sniffer.py");
    }
}, 15000);

console.log("[+] جاهز ✓\n");
