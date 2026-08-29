// ============================================================
//  🛠️ مكتبة أوامر اللعبة — دوال جاهزة للاستيراد
// ============================================================
//  شغّل: frida -D emulator-5554 -n Empire -l "E:\osmanli\game_api.js"
//  بعد ما يظهر "جاهز" المس اللعبة، ثم اكتب أوامر في الـ REPL:
//
//    Game.send('1010', '39', {})              ← إرسال بدون انتظار رد
//    Game.query('1010', '39', {})             ← إرسال + عرض الرد
//    Game.query('1001', '8', {bid:201,iid:1}) ← جمع قمح
//    Game.collect(201, 1)                     ← جمع مزرعة قمح #1
//    Game.collectAll()                        ← جمع كل الموارد
//    Game.buyStore(300201, 5)                 ← شراء من المتجر
//    Game.donate(33012)                       ← تبرع لبحث
//    Game.info()                              ← عرض حالة الاتصال
// ============================================================

var XOR_KEY = "OSxHP.!-wd?'lao5";
var _fd = -1;
var _session = 0;
var _ready = false;
var _waitingCallback = null;
var _waitingSubcmd = null;

// ======= دوال التشفير =======
function _xorEncrypt(text, key) {
    var r = []; var j = 0;
    for (var i = 0; i < text.length; i++) {
        r.push(text.charCodeAt(i) ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return r;
}

function _xorDecrypt(bytes, key) {
    var r = ''; var j = 0;
    for (var i = 0; i < bytes.length; i++) {
        r += String.fromCharCode(bytes[i] ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return r;
}

// ======= بناء حزمة =======
function _buildPacket(cmd, subcmd, data, session) {
    var msg = JSON.stringify({cmd: 'onemt_' + cmd, subcmd: String(subcmd), data: data || {}});
    var x = _xorEncrypt(msg, XOR_KEY);
    var sz = x.length + 4;
    var p = [(sz >> 8) & 0xFF, sz & 0xFF];
    for (var i = 0; i < x.length; i++) p.push(x[i] & 0xFF);
    p.push((session >> 24) & 0xFF, (session >> 16) & 0xFF, (session >> 8) & 0xFF, session & 0xFF);
    return p;
}

// ======= إرسال حزمة =======
function _sendRaw(fd, packet) {
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

// ======= محاولة فك رد السيرفر =======
function _tryParseResponse(ptr, len) {
    if (!_waitingCallback || len < 20) return;
    try {
        var offsets = [2, 0];
        for (var o = 0; o < offsets.length; o++) {
            var offset = offsets[o];
            if (offset >= len) continue;
            var bytes = [];
            for (var i = offset; i < len; i++) bytes.push(ptr.add(i).readU8());
            var decoded = _xorDecrypt(bytes, XOR_KEY);

            if (decoded.indexOf('"subcmd":"' + _waitingSubcmd + '"') !== -1 ||
                decoded.indexOf('"subcmd": "' + _waitingSubcmd + '"') !== -1) {
                var start = decoded.indexOf('{');
                var end = decoded.lastIndexOf('}');
                if (start >= 0 && end > start) {
                    try {
                        var json = JSON.parse(decoded.substring(start, end + 1));
                        var cb = _waitingCallback;
                        _waitingCallback = null;
                        _waitingSubcmd = null;
                        cb(json);
                        return;
                    } catch(e) {}
                }
            }
        }
    } catch(e) {}
}

// ╔══════════════════════════════════════════════════╗
// ║   الدوال العامة — استخدمها في الـ REPL          ║
// ╚══════════════════════════════════════════════════╝

var Game = {

    // ——— معلومات الاتصال ———
    info: function() {
        console.log("fd=" + _fd + "  session=" + _session + "  ready=" + _ready);
    },

    // ——— إرسال أمر بدون انتظار رد ———
    // Game.send('1010', '40', {itemid:300201, count:1})
    // يعيد: عدد البايتات المرسلة (أو -1 إذا فشل)
    send: function(cmd, subcmd, data) {
        if (!_ready) { console.log("⚠️ مو جاهز! المس اللعبة أولاً"); return -1; }
        _session++;
        var packet = _buildPacket(cmd, subcmd, data || {}, _session);
        var r = _sendRaw(_fd, packet);
        console.log("📤 cmd=" + cmd + " subcmd=" + subcmd + " → " + r + " bytes");
        return r;
    },

    // ——— إرسال أمر + عرض الرد ———
    // Game.query('1010', '39', {})
    // يعيد: الرد كـ JSON في التيرمنال
    query: function(cmd, subcmd, data) {
        if (!_ready) { console.log("⚠️ مو جاهز! المس اللعبة أولاً"); return; }
        _session++;
        _waitingSubcmd = String(subcmd);
        _waitingCallback = function(json) {
            console.log("\n╔═══════════════════════════════════╗");
            console.log("║ 📥 رد cmd=" + cmd + " subcmd=" + subcmd);
            console.log("╚═══════════════════════════════════╝");
            console.log(JSON.stringify(json, null, 2));
            console.log("═══════════════════════════════════\n");
        };
        var packet = _buildPacket(cmd, subcmd, data || {}, _session);
        var r = _sendRaw(_fd, packet);
        console.log("📤 أُرسل cmd=" + cmd + " subcmd=" + subcmd + " (" + r + " bytes) ⏳ ننتظر الرد...");

        // مؤقت احتياطي
        setTimeout(function() {
            if (_waitingCallback && _waitingSubcmd === String(subcmd)) {
                _waitingCallback = null;
                _waitingSubcmd = null;
                console.log("⏰ لم يصل رد لـ subcmd=" + subcmd + " (جرب live_sniffer.py للردود الكبيرة)");
            }
        }, 10000);
    },

    // ——— إرسال عدة أوامر متتالية ———
    // Game.sendMany([['1001','8',{bid:201,iid:1}], ['1001','8',{bid:201,iid:2}]])
    sendMany: function(commands, delayMs) {
        if (!_ready) { console.log("⚠️ مو جاهز!"); return; }
        var delay = delayMs || 300;
        var total = commands.length;
        console.log("📤 إرسال " + total + " أمر (delay=" + delay + "ms)...");
        commands.forEach(function(c, idx) {
            setTimeout(function() {
                _session++;
                var packet = _buildPacket(c[0], c[1], c[2] || {}, _session);
                var r = _sendRaw(_fd, packet);
                console.log("  [" + (idx+1) + "/" + total + "] cmd=" + c[0] + " sub=" + c[1] + " → " + r);
            }, idx * delay);
        });
        setTimeout(function() {
            console.log("✅ تم إرسال الكل!");
        }, total * delay + 500);
    },

    // ╔══════════════════════════════════════╗
    // ║   اختصارات جاهزة                    ║
    // ╚══════════════════════════════════════╝

    // جمع مورد: Game.collect(201, 1)  ← قمح #1
    // bid: 201=قمح, 202=خشب, 203=حديد, 204=حجر
    collect: function(bid, iid) {
        return this.send('1001', '8', {bid: bid, iid: iid});
    },

    // جمع كل الموارد: Game.collectAll()
    collectAll: function() {
        var cmds = [];
        [201, 202, 203, 204].forEach(function(bid) {
            for (var i = 0; i <= 9; i++) {
                cmds.push(['1001', '8', {bid: bid, iid: i}]);
            }
        });
        this.sendMany(cmds, 150);
    },

    // شراء من متجر التحالف: Game.buyStore(300201, 5)
    buyStore: function(itemid, count) {
        return this.send('1010', '40', {itemid: itemid, count: count || 1});
    },

    // استعلام متجر التحالف: Game.shopInfo()
    shopInfo: function() {
        this.query('1010', '39', {});
    },

    // تبرع لبحث التحالف: Game.donate(33012, 2)
    // donatetype: 1=ذهب, 2=موارد
    donate: function(sciid, donatetype) {
        return this.send('1010', '48', {sciid: sciid, donatetype: donatetype || 2});
    },

    // حالة التبرعات: Game.donateInfo(uid)
    donateInfo: function(uid) {
        this.query('1010', '81', {uid: uid || 0});
    },

    // بيانات الجيش: Game.armyInfo()
    armyInfo: function() {
        this.query('1005', '1', {});
    },

    // سجل التحالف: Game.allianceLog()
    allianceLog: function() {
        this.query('1010', '43', {});
    },

    // بيانات المدينة: Game.cityInfo()
    cityInfo: function() {
        this.query('1001', '1', {});
    },

    // بيانات الحقيبة: Game.bagInfo()
    bagInfo: function() {
        this.query('1004', '1', {});
    },

    // معلومات لاعب: Game.playerInfo(uid)
    playerInfo: function(uid) {
        this.query('1002', '7', {uid: uid});
    },

    // حرب الغزو: Game.warInfo()
    warInfo: function() {
        this.query('1070', '1', {});
    },
};

// ======= تثبيت الـ Hooks تلقائياً =======
var _libc = Process.getModuleByName("libc.so");
var _detected = false;

// مراقبة الإرسال (اكتشاف fd)
['write', 'send'].forEach(function(fn) {
    Interceptor.attach(_libc.findExportByName(fn), {
        onEnter: function(args) {
            if (_detected) return;
            var len = args[2].toInt32();
            var fd = args[0].toInt32();
            if (len < 10 || len > 2000 || fd <= 3) return;
            try {
                if (args[1].add(2).readU8() === 0x34) {
                    var s0=args[1].add(len-4).readU8(), s1=args[1].add(len-3).readU8();
                    var s2=args[1].add(len-2).readU8(), s3=args[1].add(len-1).readU8();
                    _session = ((s0<<24)|(s1<<16)|(s2<<8)|s3) >>> 0;
                    _fd = fd;
                    _ready = true;
                    _detected = true;
                    console.log("\n✅ جاهز! fd=" + _fd + " session=" + _session);
                    console.log("اكتب أوامر مثل:");
                    console.log("  Game.query('1010', '39', {})");
                    console.log("  Game.shopInfo()");
                    console.log("  Game.collectAll()");
                    console.log("  Game.send('1001', '8', {bid:201, iid:1})\n");
                }
            } catch(e) {}
        }
    });
});

// مراقبة الاستقبال (التقاط الردود)
['read', 'recv'].forEach(function(fn) {
    Interceptor.attach(_libc.findExportByName(fn), {
        onEnter: function(args) {
            this.buf = args[1];
        },
        onLeave: function(retval) {
            var len = retval.toInt32();
            if (len > 20) _tryParseResponse(this.buf, len);
        }
    });
});

console.log("\n🛠️ مكتبة أوامر اللعبة — Game API");
console.log("المس أي زر في اللعبة لبدء الاتصال...\n");
