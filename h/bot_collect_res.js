// استعلام بسيط - يرسل cmd=1001 subcmd=1 فقط (بيانات المدينة/المزارع)
var XOR_KEY = "OSxHP.!-wd?'lao5";
var sent = false;

function xorEncrypt(text, key) {
    var r = []; var j = 0;
    for (var i = 0; i < text.length; i++) {
        r.push(text.charCodeAt(i) ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return r;
}

function buildCmd(cmd, subcmd, data, session) {
    var msg = JSON.stringify({cmd:'onemt_'+cmd, subcmd:subcmd, data:data||{}});
    var x = xorEncrypt(msg, XOR_KEY);
    var s = x.length + 4;
    var p = [(s>>8)&0xFF, s&0xFF];
    for (var i=0;i<x.length;i++) p.push(x[i]&0xFF);
    p.push((session>>24)&0xFF,(session>>16)&0xFF,(session>>8)&0xFF,session&0xFF);
    return p;
}

var libc = Process.getModuleByName("libc.so");
var writeFn = new NativeFunction(libc.findExportByName("write"),'int',['int','pointer','int']);

console.log("[*] استعلام بيانات المدينة - اضغط أي زر...");

Interceptor.attach(libc.findExportByName("write"), {
    onEnter: function(args) {
        if (sent) return;
        var len = args[2].toInt32();
        var fd = args[0].toInt32();
        if (len < 10 || len > 2000 || fd <= 3) return;
        try {
            if (args[1].add(2).readU8() === 0x34) {
                var s0=args[1].add(len-4).readU8(), s1=args[1].add(len-3).readU8();
                var s2=args[1].add(len-2).readU8(), s3=args[1].add(len-1).readU8();
                var session = ((s0<<24)|(s1<<16)|(s2<<8)|s3)>>>0;
                sent = true;
                
                var packet = buildCmd('1001', '1', {}, session+1);
                var buf = Memory.alloc(packet.length);
                for (var i=0;i<packet.length;i++) buf.add(i).writeU8(packet[i]);
                writeFn(fd, buf, packet.length);
                console.log("✅ أرسل REQ_INIT_CITYDATA (cmd=1001 subcmd=1)");
                console.log("راقب live_sniffer.py للنتائج");
            }
        } catch(e){}
    }
});
