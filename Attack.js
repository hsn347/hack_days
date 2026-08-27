// ============================================================
//  🤖 بوت الهجوم
//  شغّل: frida -D emulator-5554 -f and.onemt.boe.tr -l "E:\osmanli\Attack.js"
//  ثم المس الشاشة → يبدأ البوت تلقائياً
// ============================================================

// ╔══════════════════════════════════════════════╗
// ║   منطق البوت — عدّل هنا فقط ↓↓↓            ║
// ╚══════════════════════════════════════════════╝


function runBot() {
    var ctx = {};

    steps(ctx, [
        // الخطوة 1: UID معروف مسبقاً (استخرجناه من سجل السنيفر)
        function(c, next) {
            c.uid = 12242030;
            console.log("✅ uid = " + c.uid);
            next();
        },

        // الخطوة 2: بيانات القلعة
        function(c, next) {
            sendQuery('1006', '25', {uid: c.uid}, function(retData) {
                if (!retData) { console.log("❌ فشل: 1006/25"); return; }  // توقف إذا فشل
                c.castle = retData.data || retData;
                console.log("🏰 القلعة: " + JSON.stringify(c.castle));
                next();
            });
        },

        // الخطوة 3: أضف هنا استعلامات إضافية بنفس الطريقة
        function(c, next) {
            console.log("✅ اكتملت كل الخطوات!");
            console.log("البيانات المجمعة:", JSON.stringify(c));
        }
    ]);
}













// ╔══════════════════════════════════════════════╗
// ║   لا تعدل تحت هذا السطر                    ║
// ╚══════════════════════════════════════════════╝

var XOR_KEY = "OSxHP.!-wd?'lao5";
var _fd = -1, _session = 0, _started = false;
var _waiting = null, _waitingSubcmd = null;

function _enc(t){var r=[],j=0;for(var i=0;i<t.length;i++){r.push(t.charCodeAt(i)^XOR_KEY.charCodeAt(j));j=(j+1)%XOR_KEY.length;}return r;}
function _dec(b){var r='',j=0;for(var i=0;i<b.length;i++){r+=String.fromCharCode(b[i]^XOR_KEY.charCodeAt(j));j=(j+1)%XOR_KEY.length;}return r;}

function _pkt(cmd,sub,data){
    _session++;
    var m=JSON.stringify({cmd:'onemt_'+cmd,subcmd:String(sub),data:data||{}});
    var x=_enc(m); var sz=x.length+4;
    var p=[(sz>>8)&0xFF,sz&0xFF];
    for(var i=0;i<x.length;i++)p.push(x[i]&0xFF);
    p.push((_session>>24)&0xFF,(_session>>16)&0xFF,(_session>>8)&0xFF,_session&0xFF);
    return p;
}

function _write(pkt){
    var L=Process.getModuleByName("libc.so");
    var w=new NativeFunction(L.findExportByName("write"),'int',['int','pointer','int']);
    var b=Memory.alloc(pkt.length);
    for(var i=0;i<pkt.length;i++)b.add(i).writeU8(pkt[i]);
    var r=w(_fd,b,pkt.length);
    if(r<=0){var s=new NativeFunction(L.findExportByName("send"),'int',['int','pointer','int','int']);r=s(_fd,b,pkt.length,0);}
    return r;
}

// إرسال أمر بدون انتظار رد
function sendCmd(cmd, sub, data) {
    var r = _write(_pkt(cmd, sub, data));
    console.log("📤 cmd=" + cmd + " sub=" + sub + " → " + r + " bytes");
}

// إرسال أمر + انتظار رد ثم تنفيذ callback(json)
function sendQuery(cmd, sub, data, callback) {
    _waitingSubcmd = String(sub);
    _waiting = callback;
    var r = _write(_pkt(cmd, sub, data));
    console.log("📤 query cmd=" + cmd + " sub=" + sub + " → " + r + " bytes (ننتظر الرد...)");
    setTimeout(function() {
        if (_waiting) {
            console.log("⏰ لم يصل رد لـ " + cmd + "/" + sub);
            _waiting(null);
            _waiting = null; _waitingSubcmd = null;
        }
    }, 15000);
}

// تنفيذ خطوات بالتسلسل (بدون تداخل)
// الاستخدام: steps(ctx, [ fn1, fn2, fn3 ])
// كل دالة تستقبل (ctx, next) وتستدعي next() عند الانتهاء
function steps(ctx, list) {
    var i = 0;
    function next() {
        if (i >= list.length) return;
        var fn = list[i++];
        fn(ctx, next);
    }
    next();
}


var L = Process.getModuleByName("libc.so");

// اكتشاف الاتصال وبدء البوت
['write','send'].forEach(function(fn) {
    Interceptor.attach(L.findExportByName(fn), { onEnter: function(a) {
        if (_started) return;
        var len=a[2].toInt32(), fd=a[0].toInt32();
        if (len<10||len>2000||fd<=3) return;
        try {
            if (a[1].add(2).readU8()===0x34) {
                var s0=a[1].add(len-4).readU8(),s1=a[1].add(len-3).readU8(),s2=a[1].add(len-2).readU8(),s3=a[1].add(len-1).readU8();
                _session=((s0<<24)|(s1<<16)|(s2<<8)|s3)>>>0;
                _fd=fd; _started=true;
                console.log("\n✅ اتصال تم! بدء البوت...\n");
                runBot();  // ← هنا ينطلق البوت
            }
        } catch(e){}
    }});
});

// بفر لتجميع الحزم المجزأة
var _recvBuf = [];
var _recvBufFd = -1;

// محاولة فك تشفير + فك ضغط الحزمة
function _tryDecode(bytes) {
    // جرب بدون ضغط
    var d = _dec(bytes);
    if (d.indexOf('{') !== -1) return d;
    // جرب مع إزالة ok byte + session (5 bytes من الآخر)
    if (bytes.length > 5) {
        d = _dec(bytes.slice(0, bytes.length - 5));
        if (d.indexOf('{') !== -1) return d;
    }
    // جرب فك ضغط Zlib (deflate raw)
    try {
        var raw = bytes.slice(0, bytes.length - 5);
        var inflate = new JavaInflater(true); // raw deflate
        inflate.setInput(raw);
        var out = Java.array('byte', new Array(65536).fill(0));
        var len = inflate.inflate(out);
        inflate.end();
        if (len > 0) {
            var decompressed = Array.from(out.slice(0, len));
            return _dec(decompressed);
        }
    } catch(e) {}
    return '';
}

// التقاط الردود
['read','recv'].forEach(function(fn) {
    Interceptor.attach(L.findExportByName(fn), {
        onEnter: function(a) { this.buf=a[1]; this.fd=a[0].toInt32(); },
        onLeave: function(r) {
            var n=r.toInt32();
            if (n<=0||!_waiting) return;
            try {
                var chunk=[]; for(var i=0;i<n;i++) chunk.push(this.buf.add(i).readU8());
                
                // تجميع الحزم المجزأة
                if (_recvBufFd !== this.fd) { _recvBuf=[]; _recvBufFd=this.fd; }
                _recvBuf = _recvBuf.concat(chunk);
                
                // جرب فك تشفير الحزمة المجمعة
                var attempts = [
                    _recvBuf,                                    // كامل
                    _recvBuf.slice(2),                           // بدون 2 bytes header
                    _recvBuf.slice(5),                           // بدون 5 bytes header
                    chunk,                                       // الجزء الحالي فقط
                    chunk.slice(2)                               // الجزء بدون header
                ];
                
                for (var a2=0; a2<attempts.length; a2++) {
                    if (attempts[a2].length < 10) continue;
                    var d = _tryDecode(attempts[a2]);
                    if (d && (d.indexOf('"subcmd":"'+_waitingSubcmd+'"')!==-1 || d.indexOf('"subcmd": "'+_waitingSubcmd+'"')!==-1)) {
                        var s=d.indexOf('{'), e=d.lastIndexOf('}');
                        if (s>=0&&e>s) {
                            var json=JSON.parse(d.substring(s,e+1));
                            _recvBuf=[]; // مسح البفر
                            var cb=_waiting; _waiting=null; _waitingSubcmd=null;
                            cb(json); return;
                        }
                    }
                }
            } catch(e){}
        }
    });
});


console.log("[*] البوت جاهز — المس الشاشة لبدء الاتصال...");
