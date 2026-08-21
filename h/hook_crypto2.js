// hook_crypto2.js
// اعتراض HMAC/MD5 من libcrypto.so النظامية
Java.perform(function() {
    // Hook from system libcrypto.so
    var hmac_init = Module.findExportByName("libcrypto.so", "HMAC_Init_ex");
    var hmac_update = Module.findExportByName("libcrypto.so", "HMAC_Update");
    var hmac_final = Module.findExportByName("libcrypto.so", "HMAC_Final");
    var md5_update = Module.findExportByName("libcrypto.so", "MD5_Update");
    var md5_final = Module.findExportByName("libcrypto.so", "MD5_Final");
    
    send("HMAC_Init_ex: " + hmac_init);
    send("HMAC_Update: " + hmac_update);
    send("HMAC_Final: " + hmac_final);
    send("MD5_Update: " + md5_update);
    
    var capturing = false;
    
    if (hmac_init) {
        Interceptor.attach(hmac_init, {
            onEnter: function(args) {
                if (!capturing) return;
                var keyPtr = args[1];
                var keyLen = args[2].toInt32();
                if (keyLen > 0 && keyLen < 256) {
                    var keyHex = "";
                    var keyBytes = keyPtr.readByteArray(keyLen);
                    var arr = new Uint8Array(keyBytes);
                    for (var i = 0; i < arr.length; i++) {
                        keyHex += ('0' + arr[i].toString(16)).slice(-2);
                    }
                    var keyStr = "";
                    try { keyStr = keyPtr.readCString(keyLen); } catch(e) {}
                    send("HMAC_KEY: len=" + keyLen + " hex=" + keyHex + " str=" + keyStr);
                }
            }
        });
    }
    
    if (hmac_update) {
        Interceptor.attach(hmac_update, {
            onEnter: function(args) {
                if (!capturing) return;
                var dataLen = args[2].toInt32();
                if (dataLen > 0 && dataLen < 4096) {
                    try {
                        var dataStr = args[1].readCString(dataLen);
                        send("HMAC_DATA: " + dataStr.substring(0, 500));
                    } catch(e) {}
                }
            }
        });
    }
    
    if (hmac_final) {
        Interceptor.attach(hmac_final, {
            onEnter: function(args) {
                this.outPtr = args[1];
            },
            onLeave: function(ret) {
                if (!capturing) return;
                if (this.outPtr) {
                    try {
                        var bytes = this.outPtr.readByteArray(32);
                        var arr = new Uint8Array(bytes);
                        var hex = "";
                        for (var i = 0; i < arr.length; i++) {
                            hex += ('0' + arr[i].toString(16)).slice(-2);
                        }
                        send("HMAC_RESULT: " + hex);
                    } catch(e) {}
                }
            }
        });
    }
    
    if (md5_update) {
        Interceptor.attach(md5_update, {
            onEnter: function(args) {
                if (!capturing) return;
                var dataLen = args[2].toInt32();
                if (dataLen > 0 && dataLen < 4096) {
                    try {
                        var dataStr = args[1].readCString(dataLen);
                        send("MD5_DATA: " + dataStr.substring(0, 500));
                    } catch(e) {}
                }
            }
        });
    }
    
    send("[*] Hooks ready. Triggering httpSign...");
    
    // Now trigger
    capturing = true;
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var HashMap = Java.use('java.util.HashMap');
    var ctx = OneMTCore.getApplicationContext();

    var m = HashMap.$new();
    m.put("a", "1");
    
    send("=== httpSign({a:1}, true) ===");
    SignUtil.httpSign(ctx, '{"a":"1"}', true, m);
    send("SIGN=" + m.get("sign"));
    capturing = false;
    
    send("DONE");
});
