// capture_full_sign.js
// التقاط عملية sign كاملة لأي HTTP request
Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var appKey = SignUtil.getOriginAppKey();
    send("appKey=" + appKey);
    
    // signWithAppKey = md5(input + appKey) - confirmed!
    // Now we need to know what httpSign does to the map
    
    // Instead of hooking native httpSign (crashes), 
    // hook the Java wrapper SdkHttpUtil.sign
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    
    SdkHttpUtil.sign.implementation = function(map, isUC) {
        // Capture map contents BEFORE sign
        var mapStr = this.mapToJsonStr(map);
        send("=== SIGN INPUT (isUC=" + isUC + ") ===");
        send("map_before=" + mapStr.substring(0, 800));
        
        var result = this.sign(map, isUC);
        
        // Capture map AFTER sign (httpSign may have modified it)
        var mapStrAfter = this.mapToJsonStr(map);
        send("map_after=" + mapStrAfter.substring(0, 800));
        send("sign_result=" + result);
        
        // Verify: is it md5(sortedJson + appKey)?
        // We need sorted JSON
        send("=== SIGN DONE ===");
        return result;
    };
    
    // Also hook encryptPacketForUC at Java level
    var OneMTDaemonUtil = Java.use('com.onemt.sdk.component.daemon.OneMTDaemonUtil');
    OneMTDaemonUtil.encryptPacketForUC.implementation = function(str) {
        send("=== ENCRYPT INPUT ===");
        send(str.substring(0, 500));
        var result = this.encryptPacketForUC(str);
        send("=== ENCRYPT OUTPUT (len=" + result.length + ") ===");
        send(result.substring(0, 200));
        return result;
    };
    
    send("[*] Ready! Do anything in the game...");
});
