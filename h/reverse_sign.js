// reverse_sign.js
// التقاط خوارزمية httpSign من الـ native code
// نحتاج تشغيل هذا مرة واحدة فقط لفهم الخوارزمية

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    
    // 1) Hook httpSign لرؤية المدخلات والمخرجات
    SignUtil.httpSign.implementation = function(ctx, jsonStr, isUC, map) {
        send(JSON.stringify({
            type: "httpSign_BEFORE",
            json: jsonStr,
            isUC: isUC,
            mapKeys: Object.keys(Java.cast(map, Java.use('java.util.Map')).keySet().toArray())
        }));
        
        // Store map before
        var mapBefore = {};
        var entrySet = Java.cast(map, Java.use('java.util.Map')).entrySet().toArray();
        for (var i = 0; i < entrySet.length; i++) {
            var entry = Java.cast(entrySet[i], Java.use('java.util.Map$Entry'));
            mapBefore[entry.getKey().toString()] = entry.getValue() ? entry.getValue().toString() : "null";
        }
        
        // Call original
        this.httpSign(ctx, jsonStr, isUC, map);
        
        // Check map after
        var mapAfter = {};
        entrySet = Java.cast(map, Java.use('java.util.Map')).entrySet().toArray();
        for (var i = 0; i < entrySet.length; i++) {
            var entry = Java.cast(entrySet[i], Java.use('java.util.Map$Entry'));
            mapAfter[entry.getKey().toString()] = entry.getValue() ? entry.getValue().toString() : "null";
        }
        
        // Find differences
        var added = {};
        for (var k in mapAfter) {
            if (!(k in mapBefore) || mapBefore[k] !== mapAfter[k]) {
                added[k] = mapAfter[k];
            }
        }
        
        send(JSON.stringify({
            type: "httpSign_AFTER",
            addedOrChanged: added,
            mapAfter: mapAfter
        }));
    };
    
    // 2) Hook signWithAppKey
    SignUtil.signWithAppKey.implementation = function(str) {
        var result = this.signWithAppKey(str);
        send(JSON.stringify({
            type: "signWithAppKey",
            input: str,
            output: result
        }));
        return result;
    };
    
    // 3) Hook encryptPacketForUC
    SignUtil.encryptPacketForUC.implementation = function(str) {
        send(JSON.stringify({
            type: "encryptPacketForUC_INPUT",
            input: str.substring(0, 500)
        }));
        var result = this.encryptPacketForUC(str);
        send(JSON.stringify({
            type: "encryptPacketForUC_OUTPUT",
            outputLen: result.length,
            output: result.substring(0, 200)
        }));
        return result;
    };
    
    // 4) Get AppKey
    try {
        var appKey = SignUtil.getOriginAppKey();
        send(JSON.stringify({type: "appKey", value: appKey}));
    } catch(e) {}
    
    // 5) Hook EncryptUtil.md5
    try {
        var EncryptUtil = Java.use('com.onemt.sdk.core.util.EncryptUtil');
        EncryptUtil.md5.overload('java.lang.String').implementation = function(str) {
            var result = this.md5(str);
            send(JSON.stringify({
                type: "md5",
                input: str.substring(0, 300),
                output: result
            }));
            return result;
        };
    } catch(e) {
        send(JSON.stringify({type: "error", msg: "EncryptUtil hook failed: " + e}));
    }
    
    send(JSON.stringify({type: "READY", msg: "All hooks installed. Do any action in the game..."}));
});
