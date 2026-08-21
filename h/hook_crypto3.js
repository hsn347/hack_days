// hook_crypto3.js - الإصدار المصحح
// Module API خارج Java.perform، Java API داخله

var capturing = false;

// Hook HMAC من libcrypto.so
var hmac_init = Module.findExportByName("libcrypto.so", "HMAC_Init_ex");
var hmac_update = Module.findExportByName("libcrypto.so", "HMAC_Update");
var hmac_final = Module.findExportByName("libcrypto.so", "HMAC_Final");
var md5_update = Module.findExportByName("libcrypto.so", "MD5_Update");

send("HMAC_Init_ex: " + hmac_init);
send("HMAC_Update: " + hmac_update);
send("HMAC_Final: " + hmac_final);
send("MD5_Update: " + md5_update);

if (hmac_init) {
    Interceptor.attach(hmac_init, {
        onEnter: function(args) {
            if (!capturing) return;
            var keyLen = args[2].toInt32();
            if (keyLen > 0 && keyLen < 256) {
                var keyBytes = new Uint8Array(args[1].readByteArray(keyLen));
                var keyHex = Array.from(keyBytes).map(b => ('0'+b.toString(16)).slice(-2)).join('');
                var keyStr = "";
                try { keyStr = args[1].readCString(keyLen); } catch(e) {}
                send("HMAC_KEY len=" + keyLen + " hex=" + keyHex + " str=[" + keyStr + "]");
            }
        }
    });
}

if (hmac_update) {
    Interceptor.attach(hmac_update, {
        onEnter: function(args) {
            if (!capturing) return;
            var len = args[2].toInt32();
            if (len > 0 && len < 4096) {
                try { send("HMAC_DATA: " + args[1].readCString(len)); } catch(e) {}
            }
        }
    });
}

if (hmac_final) {
    Interceptor.attach(hmac_final, {
        onEnter: function(args) { this.out = args[1]; },
        onLeave: function(ret) {
            if (!capturing || !this.out) return;
            try {
                var bytes = new Uint8Array(this.out.readByteArray(32));
                var hex = Array.from(bytes).map(b => ('0'+b.toString(16)).slice(-2)).join('');
                send("HMAC_RESULT: " + hex);
            } catch(e) {}
        }
    });
}

if (md5_update) {
    Interceptor.attach(md5_update, {
        onEnter: function(args) {
            if (!capturing) return;
            var len = args[2].toInt32();
            if (len > 0 && len < 4096) {
                try { send("MD5_DATA: " + args[1].readCString(len)); } catch(e) {}
            }
        }
    });
}

send("[*] Hooks ready, triggering...");

Java.perform(function() {
    capturing = true;
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var HashMap = Java.use('java.util.HashMap');
    var ctx = OneMTCore.getApplicationContext();

    var m = HashMap.$new();
    m.put("a", "1");
    send("=== httpSign({a:1}, isUC=true) ===");
    SignUtil.httpSign(ctx, '{"a":"1"}', true, m);
    send("SIGN_ADDED=" + m.get("sign"));
    
    // Test 2
    var m2 = HashMap.$new();
    m2.put("a", "1");
    send("=== httpSign({a:1}, isUC=false) ===");
    SignUtil.httpSign(ctx, '{"a":"1"}', false, m2);
    send("SIGN_ADDED=" + m2.get("sign"));
    
    capturing = false;
    send("DONE");
});
