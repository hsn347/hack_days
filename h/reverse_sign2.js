// reverse_sign2.js - يبقى مفتوح ويلتقط أي HTTP request
Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    
    // AppKey
    try {
        send("appKey=" + SignUtil.getOriginAppKey());
    } catch(e) {}
    
    // Hook httpSign
    SignUtil.httpSign.implementation = function(ctx, jsonStr, isUC, map) {
        var mapBefore = {};
        var it = Java.cast(map, Java.use('java.util.Map'));
        var keys = it.keySet().toArray();
        for (var i = 0; i < keys.length; i++) {
            var v = it.get(keys[i]);
            mapBefore[keys[i].toString()] = v ? v.toString() : "";
        }
        
        send("=== httpSign INPUT ===");
        send("json=" + jsonStr.substring(0, 500));
        send("isUC=" + isUC);
        
        this.httpSign(ctx, jsonStr, isUC, map);
        
        // Check what changed
        keys = it.keySet().toArray();
        for (var i = 0; i < keys.length; i++) {
            var k = keys[i].toString();
            var v = it.get(keys[i]);
            var val = v ? v.toString() : "";
            if (!(k in mapBefore) || mapBefore[k] !== val) {
                send("ADDED: " + k + "=" + val);
            }
        }
        send("=== httpSign DONE ===");
    };
    
    // Hook encryptPacketForUC
    SignUtil.encryptPacketForUC.implementation = function(str) {
        send("=== ENCRYPT INPUT (first 500) ===");
        send(str.substring(0, 500));
        var result = this.encryptPacketForUC(str);
        send("=== ENCRYPT OUTPUT (first 200) ===");
        send(result.substring(0, 200));
        return result;
    };
    
    // Hook signWithAppKey
    SignUtil.signWithAppKey.implementation = function(str) {
        var result = this.signWithAppKey(str);
        send("signWithAppKey: input=" + str.substring(0, 200) + " => " + result);
        return result;
    };
    
    send("[*] Hooks ready. Do ANYTHING in the game (open shop, settings, etc)...");
});
