// hook_crypto.js
// اعتراض HMAC/MD5 في libdaemonutil.so لكشف المفتاح والخوارزمية
// يُستخدم مرة واحدة فقط ثم نبني الحل بدون Frida نهائياً

Java.perform(function() {
    // Find libdaemonutil.so
    var mod = Process.findModuleByName("libdaemonutil.so");
    if (!mod) {
        send("ERROR: libdaemonutil.so not found");
        // Try to find it
        Process.enumerateModules().forEach(function(m) {
            if (m.name.indexOf("daemon") >= 0) {
                send("Found: " + m.name + " @ " + m.base);
            }
        });
        return;
    }
    send("libdaemonutil.so @ " + mod.base);

    // Hook HMAC_Init_ex - captures the key
    var hmac_init = Module.findExportByName("libdaemonutil.so", "HMAC_Init_ex");
    if (hmac_init) {
        Interceptor.attach(hmac_init, {
            onEnter: function(args) {
                // HMAC_Init_ex(HMAC_CTX *ctx, const void *key, int key_len, const EVP_MD *md, ENGINE *impl)
                var keyPtr = args[1];
                var keyLen = args[2].toInt32();
                if (keyLen > 0 && keyLen < 256) {
                    var keyBytes = keyPtr.readByteArray(keyLen);
                    var keyHex = Array.from(new Uint8Array(keyBytes)).map(function(b) {
                        return ('0' + b.toString(16)).slice(-2);
                    }).join('');
                    // Also try as string
                    var keyStr = "";
                    try { keyStr = keyPtr.readUtf8String(keyLen); } catch(e) {}
                    send("HMAC_Init_ex: keyLen=" + keyLen + " keyHex=" + keyHex + " keyStr=" + keyStr);
                }
            }
        });
        send("Hooked HMAC_Init_ex");
    }

    // Hook HMAC_Update - captures the data being signed
    var hmac_update = Module.findExportByName("libdaemonutil.so", "HMAC_Update");
    if (hmac_update) {
        Interceptor.attach(hmac_update, {
            onEnter: function(args) {
                var dataPtr = args[1];
                var dataLen = args[2].toInt32();
                if (dataLen > 0 && dataLen < 4096) {
                    var dataStr = "";
                    try { dataStr = dataPtr.readUtf8String(dataLen); } catch(e) {}
                    send("HMAC_Update: len=" + dataLen + " data=" + dataStr.substring(0, 300));
                }
            }
        });
        send("Hooked HMAC_Update");
    }

    // Hook HMAC_Final - captures the result
    var hmac_final = Module.findExportByName("libdaemonutil.so", "HMAC_Final");
    if (hmac_final) {
        Interceptor.attach(hmac_final, {
            onEnter: function(args) {
                this.outPtr = args[1];
                this.lenPtr = args[2];
            },
            onLeave: function(ret) {
                if (this.outPtr) {
                    var len = this.lenPtr ? this.lenPtr.readU32() : 16; // MD5=16, SHA256=32
                    var outBytes = this.outPtr.readByteArray(len);
                    var outHex = Array.from(new Uint8Array(outBytes)).map(function(b) {
                        return ('0' + b.toString(16)).slice(-2);
                    }).join('');
                    send("HMAC_Final: result=" + outHex);
                }
            }
        });
        send("Hooked HMAC_Final");
    }

    // Hook MD5_Update to see what's being hashed
    var md5_update = Module.findExportByName("libdaemonutil.so", "MD5_Update");
    if (md5_update) {
        Interceptor.attach(md5_update, {
            onEnter: function(args) {
                var dataPtr = args[1];
                var dataLen = args[2].toInt32();
                if (dataLen > 0 && dataLen < 4096) {
                    var dataStr = "";
                    try { dataStr = dataPtr.readUtf8String(dataLen); } catch(e) {}
                    send("MD5_Update: len=" + dataLen + " data=" + dataStr.substring(0, 300));
                }
            }
        });
        send("Hooked MD5_Update");
    }

    // Now trigger httpSign with a test input
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var HashMap = Java.use('java.util.HashMap');
    var ctx = OneMTCore.getApplicationContext();

    var m = HashMap.$new();
    m.put("test", "123");
    
    send("=== Calling httpSign with {test:123}, isUC=true ===");
    SignUtil.httpSign(ctx, '{"test":"123"}', true, m);
    send("httpSign result: sign=" + m.get("sign"));
    
    send("DONE");
});
