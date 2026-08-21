// frida_sign_server.js
// خادم توقيع يعمل عبر Frida RPC
// يُشغَّل مرة واحدة فقط ويخدم كل الحسابات

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var AM = Java.use('com.onemt.sdk.user.base.AccountManager').getInstance();
    var ctx = OneMTCore.getApplicationContext();
    
    // RPC exports - callable from Python
    rpc.exports = {
        // Get current session
        getSession: function() {
            var sid = AM.getSessionId();
            var uid = AM.getUserId();
            return {
                sessionId: sid ? sid.toString() : "",
                userId: uid ? uid.toString() : ""
            };
        },
        
        // Sign a JSON string (isUC=false: md5 based)
        signJson: function(jsonStr, isUc) {
            var HashMap = Java.use('java.util.HashMap');
            var m = HashMap.$new();
            SignUtil.httpSign(ctx, jsonStr, isUc, m);
            var sign = m.get("sign");
            return sign ? sign.toString() : "";
        },
        
        // Get app key
        getAppKey: function() {
            var key = SignUtil.signWithAppKey("__getkey__");
            return key ? key.toString() : "";
        },
        
        // Get deviceId, sdId etc.
        getDeviceInfo: function() {
            try {
                var IdMgr = Java.use('com.onemt.sdk.identifier.OneMTIdentifierV2').getInstance();
                return {
                    deviceId: IdMgr.getDeviceId().toString(),
                    sdId: IdMgr.getSdId().toString()
                };
            } catch(e) {
                return {deviceId: "", sdId: ""};
            }
        },
        
        // Ping
        ping: function() { return "pong"; }
    };
    
    send("sign_server_ready");
});
