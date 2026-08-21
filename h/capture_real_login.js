// capture_real_login.js
// يعترض طلب login HTTP الحقيقي ويطبع كل شيء
// شغّل هذا ثم اضغط "تسجيل دخول" في اللعبة

Java.perform(function() {
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');

    SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
        var keys = map.keySet().toArray();
        var obj = {};
        for (var i = 0; i < keys.length; i++) {
            obj[keys[i]] = map.get(keys[i]);
        }
        send("PRE_SIGN isUC=" + isUC + " body=" + JSON.stringify(obj));
        var result = this.sign(map, isUC);
        var finalKeys = map.keySet().toArray();
        var finalObj = {};
        for (var i = 0; i < finalKeys.length; i++) {
            finalObj[finalKeys[i]] = map.get(finalKeys[i]);
        }
        send("POST_SIGN body=" + JSON.stringify(finalObj));
        send("SIGN=" + result + " isUC=" + isUC);
        return result;
    };

    send("[*] READY - trigger login in game now (press login button)...");
    send("[*] Press Ctrl+C when done.");
    
    // Keep alive
    setInterval(function() {}, 60000);
});
