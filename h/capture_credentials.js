// التقاط secret وindex الجديد من الـ handshake في كل مرة
// يُشغَّل مع اللعبة ثم يحفظ البيانات في ملف

var outFile = "/sdcard/creds.json";

function tryWrite(data) {
    try {
        var libc = Process.getModuleByName("libc.so");
        var fopen  = new NativeFunction(libc.findExportByName("fopen"),  'pointer', ['pointer','pointer']);
        var fputs  = new NativeFunction(libc.findExportByName("fputs"),  'int',     ['pointer','pointer']);
        var fclose = new NativeFunction(libc.findExportByName("fclose"), 'int',     ['pointer']);

        var path  = Memory.allocUtf8String(outFile);
        var mode  = Memory.allocUtf8String("w");
        var f     = fopen(path, mode);
        if (!f.isNull()) {
            fputs(Memory.allocUtf8String(data), f);
            fclose(f);
            console.log("[+] تم الحفظ في " + outFile);
        }
    } catch(e) { console.log("خطأ الكتابة: " + e); }
}

console.log("\n[*] يراقب الـ handshake - انتظر تسجيل الدخول...\n");

var libc = Process.getModuleByName("libc.so");

function checkHandshake(ptr, len, fd) {
    if (len < 30 || len > 300) return;
    try {
        var b2 = ptr.add(2).readU8();
        if (b2 !== 0x7B) return; // '{'

        var raw = "";
        for (var i = 2; i < len; i++) {
            var c = ptr.add(i).readU8();
            if (c === 0) break;
            raw += String.fromCharCode(c);
        }

        if (raw.indexOf("username") === -1 || raw.indexOf("hmac") === -1) return;

        console.log("\n[!!!] HANDSHAKE مُلتقط:");
        console.log(raw);

        try {
            var obj = JSON.parse(raw);
            var parts = obj.username.split("@");
            var uid = atob(parts[0]);
            var rest = parts[1].split("#");
            var srv  = atob(rest[0]);
            var sub  = rest[1] ? atob(rest[1]) : "";

            var out = JSON.stringify({
                server_ip:      "101.46.140.232",
                server_port:    4000,
                uid:            obj.username.split("@")[0],
                servername:     rest[0],
                subid:          rest[1] || "",
                index:          obj.index,
                hmac_full:      obj.hmac,
                username_raw:   obj.username,
                mission_interval: 300,
                uid_decoded:    uid,
                srv_decoded:    srv,
                sub_decoded:    sub
            }, null, 2);

            console.log("\n=== game_config.json ===");
            console.log(out);
            console.log("========================\n");

            tryWrite(out);
        } catch(e) {
            console.log("خطأ parse: " + e);
        }
    } catch(e) {}
}

var w = libc.findExportByName("write");
var s = libc.findExportByName("send");

if (w) { Interceptor.attach(w, { onEnter: function(a) { checkHandshake(a[1], a[2].toInt32(), a[0].toInt32()); }}); console.log("[+] write()"); }
if (s) { Interceptor.attach(s, { onEnter: function(a) { checkHandshake(a[1], a[2].toInt32(), a[0].toInt32()); }}); console.log("[+] send()"); }

console.log("[*] جاهز. اخرج من اللعبة ثم ادخل مجدداً (أو وقف الإنترنت وأعده)");
