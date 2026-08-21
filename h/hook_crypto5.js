// hook_crypto5.js - استخدام العناوين المباشرة
Java.perform(function() {
    var capturing = false;
    var hmacKey = null;
    var hmacData = [];
    var md5Data = [];

    // العناوين من النتيجة السابقة
    var HMAC_Init_ex = ptr("0x763912e700c0");
    var HMAC_Update  = ptr("0x763912e703a0");
    var HMAC_Final   = ptr("0x763912e703c0");
    var MD5_Update   = ptr("0x763912e71090");

    Interceptor.attach(HMAC_Init_ex, {
        onEnter: function(args) {
            if (!capturing) return;
            var keyLen = args[2].toInt32();
            if (keyLen > 0 && keyLen < 512) {
                var bytes = new Uint8Array(args[1].readByteArray(keyLen));
                var hex = Array.from(bytes).map(b => ('0'+b.toString(16)).slice(-2)).join('');
                var str = "";
                try { str = args[1].readCString(keyLen); } catch(e) {}
                hmacKey = {hex: hex, str: str, len: keyLen};
                send("HMAC_KEY: len=" + keyLen + " hex=" + hex + " str=[" + str + "]");
            }
        }
    });

    Interceptor.attach(HMAC_Update, {
        onEnter: function(args) {
            if (!capturing) return;
            var len = args[2].toInt32();
            if (len > 0 && len < 4096) {
                try {
                    var s = args[1].readCString(len);
                    hmacData.push(s);
                    send("HMAC_DATA[" + len + "]: " + s.substring(0, 300));
                } catch(e) { send("HMAC_DATA_ERR: " + e); }
            }
        }
    });

    Interceptor.attach(HMAC_Final, {
        onEnter: function(args) { this.out = args[1]; },
        onLeave: function(ret) {
            if (!capturing) return;
            try {
                var bytes = new Uint8Array(this.out.readByteArray(32));
                var hex = Array.from(bytes).map(b => ('0'+b.toString(16)).slice(-2)).join('');
                send("HMAC_RESULT: " + hex.substring(0, 32)); // first 16 bytes = MD5 length
            } catch(e) {}
        }
    });

    Interceptor.attach(MD5_Update, {
        onEnter: function(args) {
            if (!capturing) return;
            var len = args[2].toInt32();
            if (len > 0 && len < 4096) {
                try {
                    var s = args[1].readCString(len);
                    md5Data.push(s);
                    send("MD5_DATA[" + len + "]: " + s.substring(0, 300));
                } catch(e) {}
            }
        }
    });

    send("[*] All hooks attached. Triggering...");

    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    var HashMap = Java.use('java.util.HashMap');

    // Test 1: isUC=true
    send("=== TEST 1: httpSign({a:1}, isUC=true) ===");
    capturing = true; hmacKey=null; hmacData=[]; md5Data=[];
    var m1 = HashMap.$new(); m1.put("a","1");
    SignUtil.httpSign(ctx, '{"a":"1"}', true, m1);
    capturing = false;
    send("SIGN_TRUE=" + m1.get("sign"));
    send("---");

    // Test 2: isUC=false
    send("=== TEST 2: httpSign({a:1}, isUC=false) ===");
    capturing = true; hmacKey=null; hmacData=[]; md5Data=[];
    var m2 = HashMap.$new(); m2.put("a","1");
    SignUtil.httpSign(ctx, '{"a":"1"}', false, m2);
    capturing = false;
    send("SIGN_FALSE=" + m2.get("sign"));

    send("DONE");
});
