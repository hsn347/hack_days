// capture_game_cmds.js
// يلتقط كل الأوامر المرسلة/المستلمة عند تنفيذ إجراءات اللعبة
// شغّله ثم نفّذ: مشاهدة قلعة لاعب آخر، الهجوم، الاستطلاع

Java.perform(function() {
    
    // ابحث عن Socket أو الـ class الذي يرسل البيانات
    // Hook java.net.Socket.getOutputStream -> write
    var OutputStream = Java.use('java.io.OutputStream');
    var lastSent = null;
    
    // Hook DataOutputStream.write لالتقاط البيانات المرسلة
    try {
        var DataOutputStream = Java.use('java.io.DataOutputStream');
        DataOutputStream.write.overload('[B', 'int', 'int').implementation = function(buf, off, len) {
            var bytes = [];
            for (var i = off; i < off + len && i < buf.length; i++) {
                bytes.push(buf[i] & 0xff);
            }
            var hex = bytes.map(b => b.toString(16).padStart(2,'0')).join('');
            // ابحث عن cmd patterns في البيانات
            if (hex.length > 4 && lastSent !== hex) {
                lastSent = hex;
                send("SENT: " + hex.substring(0, 100));
            }
            return this.write(buf, off, len);
        };
        send("[OK] DataOutputStream.write hooked");
    } catch(e) { send("DataOutputStream err: " + e); }
    
    // Hook الـ Cocos2d-x Lua binding - الدالة الرئيسية لإرسال الأوامر
    try {
        var LuaBridge = Java.use('com.cocos2dx.lib.Cocos2dxHelper');
        send("Cocos2dxHelper found");
    } catch(e) {}
    
    // الطريقة الأفضل: Hook native send function
    // ابحث عن الـ function الذي يرسل على الـ socket بالـ JNI
    
    // نبحث عن الـ class الذي يحتوي على gate protocol
    var candidates = [
        'com.onemt.sdk.component.gate.GateHelper',
        'com.onemt.sdk.component.gate.GateManager',
        'com.onemt.sdk.component.gate.GateClient',
        'com.onemt.sdk.gate.GateClient',
        'com.onemt.sdk.gate.GateHelper',
    ];
    
    candidates.forEach(function(cls) {
        try {
            var C = Java.use(cls);
            send("FOUND: " + cls);
            var methods = C.class.getDeclaredMethods();
            methods.forEach(function(m) {
                send("  METHOD: " + m.toString());
            });
        } catch(e) {}
    });
    
    // Scan for gate-related classes
    Java.enumerateLoadedClasses({
        onMatch: function(cls) {
            var cl = cls.toLowerCase();
            if (cl.indexOf('gate') >= 0 || cl.indexOf('socket') >= 0 || 
                cl.indexOf('skynet') >= 0 || cl.indexOf('network') >= 0) {
                if (cl.indexOf('onemt') >= 0 || cl.indexOf('cocos') >= 0) {
                    send("GATE_CLS: " + cls);
                }
            }
        },
        onComplete: function() { send("Scan done"); }
    });
    
    send("[*] Ready - perform game actions now (view castle, attack, scout...)");
});
