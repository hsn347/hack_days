// get_decrypted_bytes.js
// يحصل على bytes الـ daemon result المفكوك التشفير بدقة (كـ hex)

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    var HashMap = Java.use('java.util.HashMap');
    var Base64 = Java.use('android.util.Base64');
    var String = Java.use('java.lang.String');
    
    var DAEMON = "4rB5GeN3NzcyJkePA4rGSxUAIGep4ecGHZi1S+ebb/n6jZ3o+ko34ZIqWtR1MbHOOnTh9nGViMgu5lqWx2r0QKSzi+UFWO+4WtPKYn5jRZdkpRDTcprXrMlvDj5/Y5eOe3AaG9qS/3O30m+YrLXd8oCNQrY2XnVgz0KNfPLXDf/8Uyo0CJ8CgSbC5MaTUg8imUrhiUqBm5eGjKNZPrVhr0lent/TjLSwyFk/f++qfe1pv2ctydVG/oVm4ZHHn2Xvqgtxm5KIvHkNPpSBZTvNZp61f59UQxbqAqaCy9M/pDi/p746gUUeX6LS+n38QAYqjoBg+YlZIyyxgWx1coNwKw==";
    
    // decryptPacketForUC returns a Java String
    // The string contains raw bytes - get them as byte array
    try {
        var decStr = SignUtil.decryptPacketForUC(DAEMON);
        var decBytes = decStr.getBytes("ISO-8859-1");  // raw bytes as latin-1
        
        // Convert to hex
        var hexStr = "";
        for (var i = 0; i < decBytes.length; i++) {
            var b = decBytes[i] & 0xff;
            hexStr += ('0' + b.toString(16)).slice(-2);
        }
        send("DECRYPTED_HEX len=" + decBytes.length + ": " + hexStr);
        
        // Now test: use chunks as HMAC key
        // The test cases:
        //   {"a":"1"} → 171980e57ef983a1b1df64bf9ec1163b  
        //   {}        → d01ac4e2ad28d6503a38ec9f779bf424
        
        // We'll test all 16-byte chunks as possible HMAC keys
        // from Python side - just send the hex
        
    } catch(e) {
        send("decryptPacketForUC err: " + e);
    }
    
    // Also: figure out the AES key used by encryptPacketForUC
    // Test with known input/output to determine the key
    var testPlain = "AAAAAAAAAAAAAAAA";  // 16 'A' chars
    var enc = SignUtil.encryptPacketForUC(testPlain);
    send("encrypt(16xA) = " + enc);
    
    var testPlain2 = "BBBBBBBBBBBBBBBB";
    var enc2 = SignUtil.encryptPacketForUC(testPlain2);
    send("encrypt(16xB) = " + enc2);
    
    // Test: empty string
    var enc3 = SignUtil.encryptPacketForUC("");
    send("encrypt('') = " + enc3);
    
    // Also get the current daemon result fresh
    try {
        Java.choose('com.onemt.sdk.component.daemon.SDKDaemon', {
            onMatch: function(inst) {
                try {
                    var fresh = inst.cachedDaemonResult.value;
                    send("FRESH_DAEMON: " + fresh);
                    var decFresh = SignUtil.decryptPacketForUC(fresh);
                    var bytes = decFresh.getBytes("ISO-8859-1");
                    var hex = "";
                    for (var i = 0; i < bytes.length; i++) hex += ('0' + (bytes[i] & 0xff).toString(16)).slice(-2);
                    send("FRESH_DECRYPTED_HEX: " + hex);
                } catch(e) { send("fresh err: " + e); }
            },
            onComplete: function() {}
        });
    } catch(e) { send("choose err: " + e); }
    
    send("DONE");
});
