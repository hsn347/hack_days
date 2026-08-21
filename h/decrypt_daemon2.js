// decrypt_daemon2.js
Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    var HashMap = Java.use('java.util.HashMap');
    
    // The known cachedDaemonResult (captured earlier)
    var DAEMON = "4rB5GeN3NzcyJkePA4rGSxUAIGep4ecGHZi1S+ebb/n6jZ3o+ko34ZIqWtR1MbHOOnTh9nGViMgu5lqWx2r0QKSzi+UFWO+4WtPKYn5jRZdkpRDTcprXrMlvDj5/Y5eOe3AaG9qS/3O30m+YrLXd8oCNQrY2XnVgz0KNfPLXDf/8Uyo0CJ8CgSbC5MaTUg8imUrhiUqBm5eGjKNZPrVhr0lent/TjLSwyFk/f++qfe1pv2ctydVG/oVm4ZHHn2Xvqgtxm5KIvHkNPpSBZTvNZp61f59UQxbqAqaCy9M/pDi/p746gUUeX6LS+n38QAYqjoBg+YlZIyyxgWx1coNwKw==";
    
    // Call decryptPacketForUC
    send("Calling decryptPacketForUC...");
    try {
        var dec = SignUtil.decryptPacketForUC(DAEMON);
        send("DECRYPTED: " + dec);
        send("DECRYPTED_LEN: " + (dec ? dec.length() : 0));
    } catch(e) {
        send("decryptPacketForUC error: " + e);
    }
    
    // Also try encryptPacketForUC
    try {
        var enc = SignUtil.encryptPacketForUC("test_input_123");
        send("encryptPacketForUC(test_input_123): " + enc);
        var dec2 = SignUtil.decryptPacketForUC(enc);
        send("decrypt(encrypt(test)): " + dec2);
    } catch(e) {
        send("encryptPacketForUC error: " + e);
    }

    // Find SDKDaemon instance via Java.choose
    send("Finding SDKDaemon instance...");
    try {
        Java.choose('com.onemt.sdk.component.daemon.SDKDaemon', {
            onMatch: function(instance) {
                send("Found SDKDaemon instance!");
                // Get all fields
                var cls = instance.class;
                var fields = cls.getDeclaredFields();
                for (var i = 0; i < fields.length; i++) {
                    fields[i].setAccessible(true);
                    try {
                        var val = fields[i].get(instance);
                        if (val) send("FIELD " + fields[i].getName() + " = " + val.toString().substring(0, 200));
                    } catch(e) {}
                }
            },
            onComplete: function() { send("Java.choose done"); }
        });
    } catch(e) { send("Java.choose err: " + e); }
    
    // Test signWithAppKey with various inputs to find key pattern
    send("=== Testing signWithAppKey patterns ===");
    var inputs = ["", "a", "{}", "test", "123", DAEMON.substring(0, 10)];
    for (var i = 0; i < inputs.length; i++) {
        try {
            var r = SignUtil.signWithAppKey(inputs[i]);
            send("signWithAppKey(" + inputs[i].substring(0,20) + ") = " + r);
        } catch(e) {}
    }
    
    send("DONE");
});
