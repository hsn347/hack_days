// ============================================================
//  🔬 أداة اختبار متقدمة - استعلام ثم تنفيذ
// ============================================================
//  كيف تعمل:
//    المرحلة 1: يرسل "طلب استعلام" للسيرفر (مثلاً: جلب بيانات المتجر)
//    المرحلة 2: يلتقط رد السيرفر ويحلل البيانات
//    المرحلة 3: بناءً على البيانات، يرسل "أوامر تنفيذ" (مثلاً: شراء كل المتاح)
//
//  الاستخدام:
//    1. عدّل QUERY_CMD (الاستعلام)
//    2. عدّل processResponse() (كيف يتعامل مع الرد)
//    3. عدّل FALLBACK_DATA (بيانات احتياطية لو لم يصل الرد)
//    4. شغّل: frida -D emulator-5554 -n Empire -l "E:\osmanli\advanced_cmd.js"
//    5. المس أي زر في اللعبة
// ============================================================

// ╔══════════════════════════════════════════════════════════╗
// ║  الإعدادات - عدّل هنا ↓↓↓                              ║
// ╚══════════════════════════════════════════════════════════╝

// ---------- المرحلة 1: الاستعلام ----------
var QUERY_CMD    = '1005';   // الأمر الرئيسي للاستعلام
var QUERY_SUBCMD = '7';     // الأمر الفرعي (39=بيانات متجر التحالف)
var QUERY_DATA   = {"compiletype" : 1};       // بيانات الاستعلام

// ---------- المرحلة 2: كلمة البحث في الرد ----------
// البوت يبحث عن هذه الكلمة في رد السيرفر ليعرف أنه الرد الصحيح
var RESPONSE_KEYWORD = 'data';  // الكلمة المفتاحية في الرد

// ---------- المرحلة 3: ماذا ننفذ بعد الرد ----------
var ACTION_CMD    = '1010';  // الأمر الرئيسي للتنفيذ
var ACTION_SUBCMD = '40';    // الأمر الفرعي (40=شراء من المتجر)

// ---------- معالجة الرد وتحويله لأوامر ----------
// هذه الدالة تستقبل رد السيرفر (JSON) وتعيد قائمة أوامر للتنفيذ
// كل أمر هو كائن {data: {...}} يُرسل مع ACTION_CMD/ACTION_SUBCMD
function processResponse(response) {
    var commands = [];
    
    // مثال: متجر التحالف — يشتري كل عنصر في itemlist
    try {
        var itemlist = response.data.retdata.itemlist;
        for (var itemId in itemlist) {
            commands.push({
                data: { itemid: parseInt(itemId), count: itemlist[itemId] },
                label: "شراء " + itemId + " x" + itemlist[itemId]
            });
        }
    } catch(e) {
        console.log("⚠️ خطأ في معالجة الرد: " + e);
    }
    
    return commands;
}

// ---------- بيانات احتياطية (تُستخدم لو لم يصل الرد خلال TIMEOUT ثوان) ----------
var TIMEOUT = 8;  // ثوان
var FALLBACK_DATA = {
    "300103": 6,
    "400301": 30,
    "501301": 6,
    "300201": 283,
    "400401": 17,
    "300102": 3
};

// تحويل البيانات الاحتياطية لأوامر
function fallbackCommands() {
    var commands = [];
    for (var itemId in FALLBACK_DATA) {
        commands.push({
            data: { itemid: parseInt(itemId), count: FALLBACK_DATA[itemId] },
            label: "شراء " + itemId + " x" + FALLBACK_DATA[itemId]
        });
    }
    return commands;
}

// ╔══════════════════════════════════════════════════════════╗
// ║  المحرّك — لا تعدّل تحت هذا السطر                      ║
// ╚══════════════════════════════════════════════════════════╝

var XOR_KEY = "OSxHP.!-wd?'lao5";
var foundFd = -1;
var sessionCounter = 0;
var phase = 'DETECT';  // DETECT → QUERY → WAIT → EXECUTE → DONE

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

function executeCommands(commands) {
    if (commands.length === 0) {
        console.log("⚠️ لا توجد أوامر للتنفيذ!");
        phase = 'DONE';
        return;
    }
    
    phase = 'EXECUTE';
    console.log("\n=== المرحلة 3: تنفيذ " + commands.length + " أمر ===\n");
    
    var delay = 500;
    commands.forEach(function(cmd) {
        setTimeout(function() {
            var packet = buildCmd(ACTION_CMD, ACTION_SUBCMD, cmd.data, sessionCounter++);
            var r = sendPacket(foundFd, packet);
            console.log("🔹 " + cmd.label + " → " + r + " bytes");
        }, delay);
        delay += 400;
    });
    
    setTimeout(function() {
        console.log("\n=== ✅ تم تنفيذ جميع الأوامر! ===\n");
        phase = 'DONE';
    }, delay + 500);
}

// ======= اكتشاف fd (المرحلة 1) =======
function tryDetect(ptr, len, fd) {
    if (phase !== 'DETECT') return;
    if (len < 10 || len > 2000 || fd <= 3) return;
    try {
        if (ptr.add(2).readU8() === 0x34) {
            var s0=ptr.add(len-4).readU8(), s1=ptr.add(len-3).readU8();
            var s2=ptr.add(len-2).readU8(), s3=ptr.add(len-1).readU8();
            var session = ((s0<<24)|(s1<<16)|(s2<<8)|s3) >>> 0;
            
            foundFd = fd;
            sessionCounter = session + 1;
            phase = 'QUERY';
            
            console.log("[✓] fd=" + fd + " session=" + session);
            
            // المرحلة 2: إرسال الاستعلام
            console.log("\n=== المرحلة 1: إرسال الاستعلام ===");
            console.log("    cmd=" + QUERY_CMD + " subcmd=" + QUERY_SUBCMD);
            
            var packet = buildCmd(QUERY_CMD, QUERY_SUBCMD, QUERY_DATA, sessionCounter++);
            var r = sendPacket(fd, packet);
            console.log("    → أُرسل (" + r + " bytes)");
            
            phase = 'WAIT';
            console.log("\n=== المرحلة 2: انتظار الرد (" + TIMEOUT + " ثوان) ===\n");
            
            // مؤقت احتياطي
            setTimeout(function() {
                if (phase === 'WAIT') {
                    console.log("⏰ انتهى الوقت! نستخدم البيانات الاحتياطية...");
                    executeCommands(fallbackCommands());
                }
            }, TIMEOUT * 1000);
        }
    } catch(e) {}
}

// ======= التقاط رد السيرفر (المرحلة 2) =======
function tryParseRecv(ptr, len) {
    if (phase !== 'WAIT') return;
    if (len < 20) return;
    try {
        var bytes = [];
        for (var i = 2; i < len; i++) bytes.push(ptr.add(i).readU8());
        var decoded = xorDecrypt(bytes, XOR_KEY);
        
        if (decoded.indexOf(RESPONSE_KEYWORD) !== -1) {
            var start = decoded.indexOf('{');
            var end = decoded.lastIndexOf('}');
            if (start >= 0 && end > start) {
                var json = JSON.parse(decoded.substring(start, end + 1));
                console.log("✅ وصل الرد! تم التقاط الكلمة: " + RESPONSE_KEYWORD);
                phase = 'PARSE';
                var commands = processResponse(json);
                executeCommands(commands);
            }
        }
    } catch(e) {}
}

// ======= الـ Hooks =======
var libc = Process.getModuleByName("libc.so");

console.log("\n[*] 🔬 أداة اختبار متقدمة (استعلام → تنفيذ)");
console.log("[*] استعلام: cmd=" + QUERY_CMD + " subcmd=" + QUERY_SUBCMD);
console.log("[*] تنفيذ:  cmd=" + ACTION_CMD + " subcmd=" + ACTION_SUBCMD);
console.log("[*] المس أي زر في اللعبة...\n");

// مراقبة الإرسال (لاكتشاف fd)
['write', 'send'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), {
        onEnter: function(args) {
            tryDetect(args[1], args[2].toInt32(), args[0].toInt32());
        }
    });
});

// مراقبة الاستقبال (لالتقاط الرد)
['read', 'recv'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), {
        onEnter: function(args) {
            this.buf = args[1];
        },
        onLeave: function(retval) {
            var len = retval.toInt32();
            if (len > 20) tryParseRecv(this.buf, len);
        }
    });
});

console.log("[+] جاهز ✓");
