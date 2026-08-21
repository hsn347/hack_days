// سكربت التقاط بيانات الاتصال - يجمع كل المعلومات اللازمة
// IP السيرفر، الـ Port، وبيانات المصادقة
// شغّله مع اللعبة مفتوحة مرة واحدة فقط

var captured = {
    server_ip: null,
    server_port: null,
    handshake_raw: null,
    fd: -1,
    session_base: 0
};

var XOR_KEY = "OSxHP.!-wd?'lao5";

function xorDecrypt(bytes, key) {
    var result = "";
    var j = 0;
    for (var i = 0; i < bytes.length; i++) {
        result += String.fromCharCode(bytes[i] ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return result;
}

console.log("\n[*] سكربت التقاط بيانات الاتصال");
console.log("[*] افتح اللعبة وادخل حسابك الآن...\n");

var libc = Process.getModuleByName("libc.so");

// Hook connect() لالتقاط IP وPort
var connectFn = libc.findExportByName("connect");
if (connectFn) {
    Interceptor.attach(connectFn, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var sockaddr = args[1];
            try {
                var family = sockaddr.readU16();
                if (family === 2) { // AF_INET
                    var port = ((sockaddr.add(2).readU8() << 8) | sockaddr.add(3).readU8());
                    var ip = sockaddr.add(4).readU8() + "." +
                             sockaddr.add(5).readU8() + "." +
                             sockaddr.add(6).readU8() + "." +
                             sockaddr.add(7).readU8();
                    
                    // سيرفرات اللعبة عادة على بورتات غير عادية
                    if (port !== 80 && port !== 443 && port !== 53 && port > 1000) {
                        console.log("[CONNECT] fd=" + fd + " IP=" + ip + " Port=" + port);
                        captured.server_ip = ip;
                        captured.server_port = port;
                        captured.fd = fd;
                    }
                }
            } catch(e) {}
        }
    });
    console.log("[+] connect() مراقَب");
}

// Hook write/send لالتقاط الـ Handshake وأول رسالة
var msgCount = 0;
var sessionsCaptured = [];

function onPacket(ptr, len, fd) {
    if (len < 5 || len > 5000 || fd <= 3) return;
    try {
        var b2 = ptr.add(2).readU8();
        
        // حزمة XOR (JSON يبدأ بـ '{' = 0x7B XOR 'O' = 0x34)
        if (b2 === 0x34) {
            var s0 = ptr.add(len - 4).readU8();
            var s1 = ptr.add(len - 3).readU8();
            var s2 = ptr.add(len - 2).readU8();
            var s3 = ptr.add(len - 1).readU8();
            var session = ((s0 << 24) | (s1 << 16) | (s2 << 8) | s3) >>> 0;
            
            captured.fd = fd;
            if (session > 0) captured.session_base = session;
            
            msgCount++;
            if (msgCount <= 5) {
                // فك XOR لنقرأ محتوى الرسالة
                var dataLen = len - 6; // بدون header (2) وبدون session (4)
                var decrypted = "";
                for (var i = 0; i < Math.min(dataLen, 100); i++) {
                    var byte = ptr.add(2 + i).readU8();
                    var keyChar = XOR_KEY.charCodeAt(i % XOR_KEY.length);
                    decrypted += String.fromCharCode(byte ^ keyChar);
                }
                console.log("\n[MSG #" + msgCount + "] fd=" + fd + " len=" + len + " session=" + session);
                console.log("  Content: " + decrypted.substring(0, 80));
            }
        }
        
        // حزمة Handshake (أول 2 بايت = حجم، ثم JSON غير مشفر)
        // الـ handshake يحتوي username وhmac
        if (b2 === 0x7B) { // '{' مباشرة بدون XOR
            var rawJson = "";
            for (var i = 2; i < Math.min(len, 200); i++) {
                var c = ptr.add(i).readU8();
                if (c < 32 || c > 126) break;
                rawJson += String.fromCharCode(c);
            }
            if (rawJson.indexOf("username") !== -1 || rawJson.indexOf("hmac") !== -1) {
                console.log("\n[HANDSHAKE] fd=" + fd + " len=" + len);
                console.log("  " + rawJson);
                captured.handshake_raw = rawJson;
            }
        }
    } catch(e) {}
}

var writeFn = libc.findExportByName("write");
if (writeFn) {
    Interceptor.attach(writeFn, { onEnter: function(a) { onPacket(a[1], a[2].toInt32(), a[0].toInt32()); }});
    console.log("[+] write() مراقَب");
}
var sendFn = libc.findExportByName("send");
if (sendFn) {
    Interceptor.attach(sendFn, { onEnter: function(a) { onPacket(a[1], a[2].toInt32(), a[0].toInt32()); }});
    console.log("[+] send() مراقَب");
}
var sendtoFn = libc.findExportByName("sendto");
if (sendtoFn) {
    Interceptor.attach(sendtoFn, { onEnter: function(a) { onPacket(a[1], a[2].toInt32(), a[0].toInt32()); }});
    console.log("[+] sendto() مراقَب");
}

console.log("\n[*] جاهز. ادخل اللعبة الآن...");
console.log("[*] بعد 30 ثانية اطبع: summary()");

// دالة ملخص
setTimeout(function() {
    console.log("\n========== ملخص البيانات ==========");
    console.log("Server IP:   " + captured.server_ip);
    console.log("Server Port: " + captured.server_port);
    console.log("Socket fd:   " + captured.fd);
    console.log("Session:     " + captured.session_base);
    console.log("Handshake:   " + (captured.handshake_raw ? "تم التقاطه" : "لم يُلتقط"));
    if (captured.handshake_raw) console.log("  " + captured.handshake_raw);
    console.log("====================================\n");
}, 30000);
