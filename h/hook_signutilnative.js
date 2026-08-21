// hook_signutilnative.js
// اعتراض signWithAppKey و getString من SDKDaemon لكشف مفتاح isUC=true
Java.perform(function() {
    // Hook signWithAppKey to see input/output
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    
    SignUtil.signWithAppKey.implementation = function(input) {
        var result = this.signWithAppKey(input);
        send("signWithAppKey IN=[" + input + "] OUT=" + result);
        return result;
    };
    
    // Hook SDKDaemon.getString to see what key is used
    try {
        var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
        // getString(String key) - the one-arg version
        SDKDaemon.getString.overload('java.lang.String').implementation = function(key) {
            var result = this.getString(key);
            send("SDKDaemon.getString(1) key=[" + key + "] => [" + result + "]");
            return result;
        };
        // getString(String key, String def) - the two-arg version
        SDKDaemon.getString.overload('java.lang.String', 'java.lang.String').implementation = function(key, def) {
            var result = this.getString(key, def);
            send("SDKDaemon.getString(2) key=[" + key + "] def=[" + def + "] => [" + result + "]");
            return result;
        };
        send("SDKDaemon.getString hooked");
    } catch(e) { send("SDKDaemon hook err: " + e); }

    // Hook native_get
    try {
        var SDKDaemon2 = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
        SDKDaemon2.native_get.overload('java.lang.String').implementation = function(key) {
            var result = this.native_get(key);
            send("native_get key=[" + key + "] => [" + result + "]");
            return result;
        };
    } catch(e) { send("native_get hook err: " + e); }

    // Hook OneMTDaemonUtil.httpSign wrapper if exists in Java
    try {
        var DaemonUtil = Java.use('com.onemt.sdk.component.daemon.OneMTDaemonUtil');
        DaemonUtil.httpSign.implementation = function(ctx, json, isUC, map) {
            send("OneMTDaemonUtil.httpSign json=[" + json + "] isUC=" + isUC);
            this.httpSign(ctx, json, isUC, map);
            send("OneMTDaemonUtil.httpSign sign=" + map.get("sign"));
        };
    } catch(e) { send("DaemonUtil.httpSign hook err: " + e); }

    // Now trigger to capture everything
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var HashMap = Java.use('java.util.HashMap');
    var ctx = OneMTCore.getApplicationContext();

    send("=== Triggering httpSign(isUC=true) ===");
    var m = HashMap.$new();
    m.put("a", "1");
    SignUtil.httpSign(ctx, '{"a":"1"}', true, m);
    send("FINAL SIGN_TRUE=" + m.get("sign"));

    send("=== Triggering httpSign(isUC=false) ===");
    var m2 = HashMap.$new();
    m2.put("a", "1");
    SignUtil.httpSign(ctx, '{"a":"1"}', false, m2);
    send("FINAL SIGN_FALSE=" + m2.get("sign"));

    send("DONE");
});
