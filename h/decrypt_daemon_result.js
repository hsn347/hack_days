// decrypt_daemon_result.js
// يستدعي decryptPacketForUC على cachedDaemonResult
// ثم يجرب استخدام النتيجة كمفتاح توقيع

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    var HashMap = Java.use('java.util.HashMap');

    // Get cachedDaemonResult
    var daemonInstance = SDKDaemon.getInstance();
    var daemonResult = daemonInstance.cachedDaemonResult.value;
    send("cachedDaemonResult: " + daemonResult);
    
    // Decrypt it
    try {
        var decrypted = SignUtil.decryptPacketForUC(daemonResult);
        send("decryptPacketForUC result: " + decrypted);
        send("decrypted length: " + (decrypted ? decrypted.length() : 0));
        
        // Now try using the decrypted value as key for signing
        // Test 1: sign = md5(decrypted + json)
        // Test 2: sign = hmac-md5(decrypted, json)
        // We'll see by testing manually
        
        // Also try decrypting with the daemon result from field
        var fields = daemonInstance.class.getDeclaredFields();
        for (var i = 0; i < fields.length; i++) {
            fields[i].setAccessible(true);
            try {
                var val = fields[i].get(daemonInstance);
                send("FIELD: " + fields[i].getName() + " = " + val);
            } catch(e) {}
        }
    } catch(e) {
        send("decryptPacketForUC err: " + e);
    }
    
    // Also try: what does native_get return for various keys?
    var testKeys = ["sign", "key", "secret", "token", "appkey", "signing_key", 
                    "hmac_key", "uc_key", "daemon_key", "encrypt_key"];
    for (var i = 0; i < testKeys.length; i++) {
        try {
            var val = daemonInstance.native_get.overload('java.lang.String').call(daemonInstance, testKeys[i]);
            if (val) send("native_get(" + testKeys[i] + ") = " + val);
        } catch(e) {}
        try {
            var val2 = daemonInstance.getString.overload('java.lang.String').call(daemonInstance, testKeys[i]);
            if (val2) send("getString(" + testKeys[i] + ") = " + val2);
        } catch(e) {}
    }
    
    // Get the actual sign computation input/output for empty json
    send("=== Testing sign for {} ===");
    var m1 = HashMap.$new();
    SignUtil.httpSign(ctx, '{}', true, m1);
    send("sign({}, true) = " + m1.get("sign"));
    
    // And with appid
    var m2 = HashMap.$new();
    SignUtil.httpSign(ctx, '{"appid":"100002001"}', true, m2);
    send("sign({appid:100002001}, true) = " + m2.get("sign"));
    
    send("DONE");
});
