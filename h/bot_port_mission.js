// بوت شراء متجر التحالف - يستعلم ثم يشتري كل المتاح
var XOR_KEY = "OSxHP.!-wd?'lao5";
var counter = 0;
var foundFd = -1;
var foundSession = 0;
var missionSent = false;
var sessionCounter = 0;

function xorEncrypt(text, key) {
    var result = [];
    var j = 0;
    for (var i = 0; i < text.length; i++) {
        result.push(text.charCodeAt(i) ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return result;
}

function xorDecrypt(bytes, key) {
    var result = '';
    var j = 0;
    for (var i = 0; i < bytes.length; i++) {
        result += String.fromCharCode(bytes[i] ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return result;
}

function buildCmd(cmd, subcmd, data, session) {
    var msg = JSON.stringify({cmd: 'onemt_' + cmd, subcmd: subcmd, data: data || {}});
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

function sendPacket(fd, packet) {
    var r = sendViaWrite(fd, packet);
    if (r <= 0) r = sendViaSend(fd, packet);
    return r;
}

// التقاط رد السيرفر من read/recv
var storeData = null;
var waitingForStore = false;
var buyDone = false;

function tryParseRecv(ptr, len, fd) {
    if (!waitingForStore || buyDone) return;
    if (len < 20) return;
    
    try {
        // جرب فك تشفير البيانات من البداية بعد أول 2 بايت (الحجم)
        var bytes = [];
        for (var i = 2; i < len; i++) {
            bytes.push(ptr.add(i).readU8());
        }
        
        var decoded = xorDecrypt(bytes, XOR_KEY);
        
        // ابحث عن itemlist في الرد
        if (decoded.indexOf('itemlist') !== -1 && decoded.indexOf('subcmd') !== -1) {
            // استخرج JSON
            var startIdx = decoded.indexOf('{');
            var endIdx = decoded.lastIndexOf('}');
            if (startIdx >= 0 && endIdx > startIdx) {
                var jsonStr = decoded.substring(startIdx, endIdx + 1);
                try {
                    var response = JSON.parse(jsonStr);
                    if (response.data && response.data.retdata && response.data.retdata.itemlist) {
                        storeData = response.data.retdata.itemlist;
                        waitingForStore = false;
                        console.log("\n=== ✅ وصل رد المتجر! ===");
                        buyAllItems();
                        return;
                    }
                } catch(e) {}
            }
        }
    } catch(e) {}
}

function buyAllItems() {
    if (!storeData) {
        console.log("⚠️ لا توجد بيانات متجر!");
        return;
    }
    
    buyDone = true;
    var items = [];
    for (var itemId in storeData) {
        items.push({id: parseInt(itemId), count: storeData[itemId]});
    }
    
    console.log("\n📦 العناصر المتاحة (" + items.length + "):");
    items.forEach(function(item) {
        console.log("  - itemid=" + item.id + " متاح=" + item.count);
    });
    
    if (items.length === 0) {
        console.log("  ⚠️ لا توجد عناصر!");
        return;
    }
    
    console.log("\n=== 🛒 شراء كل العناصر ===");
    var delay = 500;
    items.forEach(function(item) {
        setTimeout(function() {
            var buyPacket = buildCmd('1010', '40', {
                itemid: item.id,
                count: item.count
            }, sessionCounter++);
            var r = sendPacket(foundFd, buyPacket);
            console.log("🛒 شراء itemid=" + item.id + " x" + item.count + " result=" + r);
        }, delay);
        delay += 500;
    });
    
    setTimeout(function() {
        console.log("\n=== ✅ تمت جميع عمليات الشراء! ===\n");
    }, delay + 500);
}

// ======= اكتشاف fd =======
function tryDetect(ptr, len, fd) {
    if (len < 10 || len > 2000 || fd <= 3) return;
    try {
        var b2 = ptr.add(2).readU8();
        if (b2 === 0x34) {
            var s0 = ptr.add(len - 4).readU8();
            var s1 = ptr.add(len - 3).readU8();
            var s2 = ptr.add(len - 2).readU8();
            var s3 = ptr.add(len - 1).readU8();
            var session = ((s0 << 24) | (s1 << 16) | (s2 << 8) | s3) >>> 0;
            
            foundFd = fd;
            foundSession = session;
            sessionCounter = session + 1;
            counter++;
            
            if (counter <= 2) {
                console.log("[GAME PKT] fd=" + fd + " session=" + session);
            }
            
            if (!missionSent) {
                missionSent = true;
                waitingForStore = true;
                
                console.log("\n=== مرحلة 1: استعلام المتجر ===");
                var queryPacket = buildCmd('1010', '39', {}, sessionCounter++);
                var r = sendPacket(fd, queryPacket);
                console.log("-> استعلام أُرسل، result=" + r);
                
                // احتياط: إذا لم يصل الرد خلال 5 ثوان، اشتري بآخر بيانات معروفة
                setTimeout(function() {
                    if (!buyDone) {
                        console.log("\n⚠️ لم يصل رد المتجر. نستخدم آخر بيانات معروفة...");
                        storeData = {
                            "300103": 6,
                            "400301": 30,
                            "501301": 6,
                            "300201": 283,
                            "400401": 17,
                            "300102": 3
                        };
                        buyAllItems();
                    }
                }, 5000);
            }
        }
    } catch(e) {}
}

// ======= Hooks =======
var libc = Process.getModuleByName("libc.so");

console.log("\n[*] 🛒 بوت شراء متجر التحالف");
console.log("[*] الخطوات: 1.استعلام → 2.شراء كل المتاح");
console.log("[*] اضغط أي زر في اللعبة...\n");

// Hook write
Interceptor.attach(libc.findExportByName("write"), {
    onEnter: function(args) {
        if (!missionSent)
            tryDetect(args[1], args[2].toInt32(), args[0].toInt32());
    }
});

// Hook send
Interceptor.attach(libc.findExportByName("send"), {
    onEnter: function(args) {
        if (!missionSent)
            tryDetect(args[1], args[2].toInt32(), args[0].toInt32());
    }
});

// Hook read - لالتقاط الرد
Interceptor.attach(libc.findExportByName("read"), {
    onEnter: function(args) {
        this.fd = args[0].toInt32();
        this.buf = args[1];
    },
    onLeave: function(retval) {
        var len = retval.toInt32();
        if (len > 20 && waitingForStore)
            tryParseRecv(this.buf, len, this.fd);
    }
});

// Hook recv - لالتقاط الرد
Interceptor.attach(libc.findExportByName("recv"), {
    onEnter: function(args) {
        this.fd = args[0].toInt32();
        this.buf = args[1];
    },
    onLeave: function(retval) {
        var len = retval.toInt32();
        if (len > 20 && waitingForStore)
            tryParseRecv(this.buf, len, this.fd);
    }
});

console.log("[+] جميع الـ hooks جاهزة");
