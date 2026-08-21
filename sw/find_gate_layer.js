// find_gate_layer.js
// يبحث عن الـ layer المسؤول عن اتصال gate بـ 3 طرق:
// 1. يعرض كل الـ native modules
// 2. يجرب Java NIO channels
// 3. يبحث عن classes فيها كلمة socket/tcp/gate/network

Java.perform(function() {

    // ═══ 1. All native modules ═══
    send("=== NATIVE MODULES ===");
    var mods = Process.enumerateModules();
    mods.forEach(function(m) {
        // skip android/system libs
        if (m.path.indexOf('/system/') >= 0) return;
        if (m.path.indexOf('/vendor/') >= 0) return;
        if (m.path.indexOf('frida') >= 0) return;
        send("MOD: " + m.name + " [" + m.size + "] " + m.path);
    });

    // ═══ 2. Hook java.nio.channels.SocketChannel ═══
    try {
        var SC = Java.use('java.nio.channels.SocketChannel');
        SC.write.overload('java.nio.ByteBuffer').implementation = function(buf) {
            var pos = buf.position();
            var lim = buf.limit();
            var len = lim - pos;
            if (len > 6) {
                var arr = Java.array('byte', new Array(Math.min(len, 200)));
                buf.get(arr);
                buf.position(pos); // reset
                var bytes = [];
                for (var i = 0; i < arr.length; i++) bytes.push(arr[i] & 0xff);
                send("NIO_WRITE(" + len + "): " + bytes.slice(0,20).map(function(b){return b.toString(16).padStart(2,'0')}).join(''));
            }
            return this.write(buf);
        };
        send("[OK] NIO SocketChannel.write hooked");
    } catch(e) { send("[skip] NIO write: " + e); }

    try {
        var SC2 = Java.use('java.nio.channels.SocketChannel');
        SC2.read.overload('java.nio.ByteBuffer').implementation = function(buf) {
            var n = this.read(buf);
            if (n > 6) {
                var pos = buf.position();
                buf.position(pos - n);
                var arr = Java.array('byte', new Array(Math.min(n, 200)));
                buf.get(arr);
                buf.position(pos);
                var bytes = [];
                for (var i = 0; i < arr.length; i++) bytes.push(arr[i] & 0xff);
                send("NIO_READ(" + n + "): " + bytes.slice(0,20).map(function(b){return b.toString(16).padStart(2,'0')}).join(''));
            }
            return n;
        };
        send("[OK] NIO SocketChannel.read hooked");
    } catch(e) { send("[skip] NIO read: " + e); }

    // ═══ 3. Search loaded classes ═══
    send("=== SEARCHING CLASSES ===");
    Java.enumerateLoadedClasses({
        onMatch: function(cls) {
            var cl = cls.toLowerCase();
            if (cl.indexOf('socket') >= 0 || cl.indexOf('tcp') >= 0 ||
                cl.indexOf('gate') >= 0 || cl.indexOf('netclient') >= 0 ||
                cl.indexOf('connection') >= 0 || cl.indexOf('netutil') >= 0) {
                // skip standard java/android/okhttp
                if (cl.indexOf('java.') >= 0) return;
                if (cl.indexOf('android.') >= 0) return;
                if (cl.indexOf('okhttp') >= 0) return;
                if (cl.indexOf('okio') >= 0) return;
                if (cl.indexOf('javax.') >= 0) return;
                if (cl.indexOf('sun.') >= 0) return;
                if (cl.indexOf('dalvik') >= 0) return;
                send("CLASS: " + cls);
            }
        },
        onComplete: function() { send("=== SEARCH DONE ==="); }
    });
});
