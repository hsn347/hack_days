// ============================================================
// 🛠️ مكتبة الاستعلامات (QueryAPI) - تعمل مع Frida عن طريق Require
// ============================================================

var XOR_KEY = "OSxHP.!-wd?'lao5";
var _fd = -1;
var _session = 0;
var _ready = false;
var _pendingResolves = {}; // لتخزين دوال الإرجاع (Promises) حسب الـ subcmd

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

function _buildPacket(cmd, subcmd, data, session) {
    var msg = JSON.stringify({cmd: 'onemt_' + cmd, subcmd: String(subcmd), data: data || {}});
    var x = _xorEncrypt(msg, XOR_KEY);
    var sz = x.length + 4;
    var p = [(sz >> 8) & 0xFF, sz & 0xFF];
    for (var i = 0; i < x.length; i++) p.push(x[i] & 0xFF);
    p.push((session >> 24) & 0xFF, (session >> 16) & 0xFF, (session >> 8) & 0xFF, session & 0xFF);
    return p;
}

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

// ==========================================
// 🚀 الدالة الرئيسية المُصدّرة للاستخدام
// ==========================================
function queryServer(cmd, subcmd, data) {
    return new Promise(function(resolve, reject) {
        if (!_ready) {
            reject("⚠️ الاتصال غير جاهز! المس شاشة اللعبة أولاً لتهيئة الاتصال.");
            return;
        }

        _session++;
        var currentSession = _session;
        var subcmdStr = String(subcmd);
        
        _pendingResolves[subcmdStr] = resolve;

        var packet = _buildPacket(cmd, subcmd, data, currentSession);
        _sendRaw(_fd, packet);
        
        setTimeout(function() {
            if (_pendingResolves[subcmdStr]) {
                delete _pendingResolves[subcmdStr];
                reject("⏰ انتهى الوقت (Timeout) ولم يصل رد للأمر: " + cmd + "/" + subcmd);
            }
        }, 15000);
    });
}


// ==========================================
// ⚙️ نظام الاعتراض (Hooks) للالتقاط
// ==========================================
var _libc = Process.getModuleByName("libc.so");

['write', 'send'].forEach(function(fn) {
    Interceptor.attach(_libc.findExportByName(fn), {
        onEnter: function(args) {
            if (_ready) return;
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
                    console.log("\n✅ [QueryAPI] تم تهيئة الاتصال بنجاح!");
                }
            } catch(e) {}
        }
    });
});

['read', 'recv'].forEach(function(fn) {
    Interceptor.attach(_libc.findExportByName(fn), {
        onEnter: function(args) {
            this.buf = args[1];
        },
        onLeave: function(retval) {
            var len = retval.toInt32();
            if (len > 20 && Object.keys(_pendingResolves).length > 0) {
                try {
                    var offsets = [2, 0];
                    for (var o = 0; o < offsets.length; o++) {
                        if (offsets[o] >= len) continue;
                        var bytes = [];
                        for (var i = offsets[o]; i < len; i++) bytes.push(this.buf.add(i).readU8());
                        var decoded = _xorDecrypt(bytes, XOR_KEY);

                        for (var waitingSubcmd in _pendingResolves) {
                            if (decoded.indexOf('"subcmd":"' + waitingSubcmd + '"') !== -1 ||
                                decoded.indexOf('"subcmd": "' + waitingSubcmd + '"') !== -1) {
                                
                                var start = decoded.indexOf('{');
                                var end = decoded.lastIndexOf('}');
                                if (start >= 0 && end > start) {
                                    var json = JSON.parse(decoded.substring(start, end + 1));
                                    var resolveFunc = _pendingResolves[waitingSubcmd];
                                    delete _pendingResolves[waitingSubcmd];
                                    resolveFunc(json);
                                    return;
                                }
                            }
                        }
                    }
                } catch(e) {}
            }
        }
    });
});

// تصدير الدالة لتكون متاحة للاستيراد
module.exports = queryServer;
