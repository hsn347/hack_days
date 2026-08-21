// get_exact_json.js
// يلتقط الـ JSON string الحرفي الذي تنتجه mapToJsonStr قبل الـ hash
// مع كل المدخلات المحتملة

Java.perform(function() {
    
    var HttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    
    // 1. Hook mapToJsonStr لالتقاط الـ JSON الحرفي
    HttpUtil.mapToJsonStr.overload('java.util.Map').implementation = function(map) {
        var result = this.mapToJsonStr(map);
        // هل هذا طلب UC؟
        var mapStr = map.toString();
        if (mapStr.indexOf('securemode') >= 0 || mapStr.indexOf('sessionid') >= 0 || 
            mapStr.indexOf('deviceid') >= 0) {
            send("mapToJsonStr INPUT=" + mapStr.substring(0, 200));
            send("mapToJsonStr OUTPUT=" + result);
        }
        return result;
    };
    
    // 2. Hook sign - يطبع كل شيء
    HttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
        var r = this.sign(map, isUC);
        if (isUC) {
            var keys = map.keySet().toArray();
            var bodyFull = {};
            for (var i = 0; i < keys.length; i++) {
                var k = keys[i].toString();
                bodyFull[k] = (map.get(keys[i]) || '').toString();
            }
            send("=== isUC=TRUE SIGN ===");
            send("BODY: " + JSON.stringify(bodyFull));
            send("SIGN: " + bodyFull['sign']);
        }
        return r;
    };
    
    // 3. استدعاء اليدوي: اختبر JSON format مع map بسيط
    Java.scheduleOnMainThread(function() {
        try {
            var HashMap = Java.use('java.util.HashMap');
            var testMap = HashMap.$new();
            testMap.put("a", "1");
            testMap.put("b", "2");
            
            // اختبر mapToJsonStr على map بسيط
            var sortedMap = HttpUtil.sortMapByKey(testMap);
            var jsonStr = HttpUtil.mapToJsonStr(sortedMap);
            send("TEST_JSON(a=1,b=2): " + jsonStr);
            
            // اختبر على map فارغ
            var emptyMap = HashMap.$new();
            var sortedEmpty = HttpUtil.sortMapByKey(emptyMap);
            var emptyJson = HttpUtil.mapToJsonStr(sortedEmpty);
            send("TEST_JSON(empty): " + emptyJson);
            
            // حاول حساب sign لـ isUC=true على test map
            // أضف sign وشوف الناتج
            HttpUtil.sign(testMap, true);
            send("SIGN_UC_TRUE(a=1,b=2): " + testMap.get("sign"));
            
            HttpUtil.sign(emptyMap, true);
            send("SIGN_UC_TRUE(empty): " + emptyMap.get("sign"));
            
        } catch(e) { send("scheduleMain err: " + e); }
    });
    
    // 4. أيضاً hook SdkHttpUrlManager.getBaseUrl لمعرفة الـ URL
    try {
        var UrlMgr = Java.use('com.onemt.sdk.core.http.SdkHttpUrlManager');
        UrlMgr.getBaseUrl.overload('java.lang.String').implementation = function(module) {
            var r = this.getBaseUrl(module);
            send("getBaseUrl(" + module + ") = " + r);
            return r;
        };
    } catch(e) { send("UrlMgr hook err: " + e); }
    
    send("[*] READY - trigger any action that calls UC API");
});
