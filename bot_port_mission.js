// تشخيص - نعرض كل الحزم على جميع fd
// لا فلترة - فقط نشوف ايش يمر

var XOR_KEY = "OSxHP.!-wd?'lao5";
var counter = 0;
var foundFd = -1;
var foundSession = 0;
var missionSent = false;

function xorEncrypt(text, key) {
    var result = [];
    var j = 0;
    for (var i = 0; i < text.length; i++) {
        result.push(text.charCodeAt(i) ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return result;
}
/*
{
  "cmd": "onemt_1001",
  "subcmd": "9",
  "data": {
    "allData": [
      {
        "bid": 204,
        "iid": 8,
        "mode": 1
      },
      {
        "bid": 204,
        "iid": 7,
        "mode": 1
      },
      {
        "bid": 204,
        "iid": 6,
        "mode": 1
      },
      {
        "bid": 204,
        "iid": 5,
        "mode": 1
      },
      {
        "bid": 204,
        "iid": 2,
        "mode": 1
      },
      {
        "bid": 204,
        "iid": 9,
        "mode": 1
      },
      {
        "bid": 204,
        "iid": 4,
        "mode": 1
      },
      {
        "bid": 204,
        "iid": 3,
        "mode": 1
      }
    ]
  }
}
*/

function buildPortMission(session) {
    var msg = '{"cmd":"onemt_1001","subcmd":"9","data":{"allData":[{"bid":204,"iid":8,"mode":1},{"bid":204,"iid":7,"mode":1},{"bid":204,"iid":6,"mode":1},{"bid":204,"iid":5,"mode":1},{"bid":204,"iid":2,"mode":1},{"bid":204,"iid":9,"mode":1},{"bid":204,"iid":4,"mode":1},{"bid":204,"iid":3,"mode":1}]}}';
    var xorBytes = xorEncrypt(msg, XOR_KEY);
    var size = xorBytes.length + 4;
    var p = [(size >> 8) & 0xFF, size & 0xFF];
    for (var i = 0; i < xorBytes.length; i++) p.push(xorBytes[i] & 0xFF);
    p.push((session >> 24) & 0xFF, (session >> 16) & 0xFF, (session >> 8) & 0xFF, session & 0xFF);
    return p;
}

function sendViaWrite(fd, packet) {
    var libc = Process.getModuleByName("libc.so");
    var w = new NativeFunction(libc.findExportByName("write"), 'int', ['int', 'pointer', 'int']);
    var buf = Memory.alloc(packet.length);
    for (var i = 0; i < packet.length; i++) buf.add(i).writeU8(packet[i]);
    return w(fd, buf, packet.length);
}

function sendViaSend(fd, packet) {
    var libc = Process.getModuleByName("libc.so");
    var s = new NativeFunction(libc.findExportByName("send"), 'int', ['int', 'pointer', 'int', 'int']);
    var buf = Memory.alloc(packet.length);
    for (var i = 0; i < packet.length; i++) buf.add(i).writeU8(packet[i]);
    return s(fd, buf, packet.length, 0);
}

function tryDetect(ptr, len, fd) {
    if (len < 10 || len > 2000 || fd <= 3) return;
    try {
        var b0 = ptr.add(0).readU8();
        var b1 = ptr.add(1).readU8();
        // byte 2 XOR 'O'(0x4F) يجب أن يكون '{' (0x7B) = 0x34
        var b2 = ptr.add(2).readU8();
        
        if (b2 === 0x34) {
            // استخرج الـ session (آخر 4 بايت)
            var s0 = ptr.add(len - 4).readU8();
            var s1 = ptr.add(len - 3).readU8();
            var s2 = ptr.add(len - 2).readU8();
            var s3 = ptr.add(len - 1).readU8();
            var session = ((s0 << 24) | (s1 << 16) | (s2 << 8) | s3) >>> 0;
            
            foundFd = fd;
            foundSession = session;
            
            counter++;
            if (counter <= 3) {
                console.log("\n[GAME PKT] fd=" + fd + " len=" + len + " session=" + session);
            }
            
            // أرسل مهمة الميناء بعد أول حزمة
            if (!missionSent) {
                missionSent = true;
                var nextSession = session + 1;
                var packet = buildPortMission(nextSession);
                
                console.log("\n=== إرسال مهمة الميناء ===");
                console.log("fd=" + fd + " session=" + nextSession);
                
                // جرب write أولاً
                var r1 = sendViaWrite(fd, packet);
                console.log("write() = " + r1);
                
                if (r1 <= 0) {
                    // جرب send
                    var r2 = sendViaSend(fd, packet);
                    console.log("send() = " + r2);
                    
                    if (r2 > 0) {
                        console.log("[✓] نجح الإرسال عبر send()!");
                    } else {
                        console.log("[X] فشل كلاهما. fd ربما خاطئ.");
                        missionSent = false;
                    }
                } else {
                    console.log("[✓] نجح الإرسال عبر write()!");
                }
                console.log("=========================\n");
            }
        }
    } catch(e) {}
}

var libc = Process.getModuleByName("libc.so");

console.log("\n[*] بوت مهمة الميناء - يراقب write() و send() و sendto()");
console.log("[*] اضغط أي زر في اللعبة...\n");

// Hook write()
var writeFn = libc.findExportByName("write");
if (writeFn) {
    Interceptor.attach(writeFn, {
        onEnter: function(args) {
            if (!missionSent)
                tryDetect(args[1], args[2].toInt32(), args[0].toInt32());
        }
    });
    console.log("[+] write() مراقَب");
}

// Hook send()
var sendFn = libc.findExportByName("send");
if (sendFn) {
    Interceptor.attach(sendFn, {
        onEnter: function(args) {
            if (!missionSent)
                tryDetect(args[1], args[2].toInt32(), args[0].toInt32());
        }
    });
    console.log("[+] send() مراقَب");
}

// Hook sendto()
var sendtoFn = libc.findExportByName("sendto");
if (sendtoFn) {
    Interceptor.attach(sendtoFn, {
        onEnter: function(args) {
            if (!missionSent)
                tryDetect(args[1], args[2].toInt32(), args[0].toInt32());
        }
    });
    console.log("[+] sendto() مراقَب");
}
