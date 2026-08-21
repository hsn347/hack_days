// get_daemon_hex.js  
// يستخدم charCodeAt لاستخراج bytes الـ daemon المفكوكة بدقة

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
    
    var DAEMON = "4rB5GeN3NzcyJkePA4rGSxUAIGep4ecGHZi1S+ebb/n6jZ3o+ko34ZIqWtR1MbHOOnTh9nGViMgu5lqWx2r0QKSzi+UFWO+4WtPKYn5jRZdkpRDTcprXrMlvDj5/Y5eOe3AaG9qS/3O30m+YrLXd8oCNQrY2XnVgz0KNfPLXDf/8Uyo0CJ8CgSbC5MaTUg8imUrhiUqBm5eGjKNZPrVhr0lent/TjLSwyFk/f++qfe1pv2ctydVG/oVm4ZHHn2Xvqgtxm5KIvHkNPpSBZTvNZp61f59UQxbqAqaCy9M/pDi/p746gUUeX6LS+n38QAYqjoBg+YlZIyyxgWx1coNwKw==";
    
    // Get decrypted bytes via charCodeAt (JS string method)
    try {
        var dec = SignUtil.decryptPacketForUC(DAEMON);
        var len = dec.length; // JS string length property
        var hex = "";
        for (var i = 0; i < len; i++) {
            var code = dec.charCodeAt(i) & 0xff;
            hex += ('0' + code.toString(16)).slice(-2);
        }
        send("DAEMON_DEC_HEX_LEN=" + len);
        send("DAEMON_DEC_HEX=" + hex);
    } catch(e) {
        send("decryptPacketForUC charCodeAt err: " + e);
    }
    
    // Also: get ALL keys from SDKDaemon.getString
    var keys = ["sign", "appkey", "app_key", "uc_key", "sign_key", "key", 
                "secret", "token", "daemon", "daemon_key", "result", "data",
                "encrypt_key", "hmac_key", "aes_key", "des_key"];
    for (var i = 0; i < keys.length; i++) {
        try {
            var v1 = SDKDaemon.getString.overload('java.lang.String').call(null, keys[i]);
            if (v1) send("getString_1(" + keys[i] + ")=" + v1);
        } catch(e) {}
    }
    
    // Get native_get values
    try {
        var nm = SDKDaemon.native_get.overload('java.lang.String');
        for (var i = 0; i < keys.length; i++) {
            try {
                var v = nm.call(null, keys[i]);
                if (v) send("native_get(" + keys[i] + ")=" + v);
            } catch(e) {}
        }
    } catch(e) { send("native_get err: " + e); }
    
    // Get init byte[] arg - hook init to capture it
    SDKDaemon.init.implementation = function(ctx, keyBytes) {
        var hex = "";
        for (var i = 0; i < keyBytes.length; i++) {
            hex += ('0' + (keyBytes[i] & 0xff).toString(16)).slice(-2);
        }
        send("SDKDaemon.init called with bytes: " + hex);
        return this.init(ctx, keyBytes);
    };
    
    send("DONE");
});
