// get_sorted_json.js
// الحصول على JSON المرتب كما ينتجه sortMapByKey + Gson
Java.perform(function() {
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    var HashMap = Java.use('java.util.HashMap');
    var TreeMap = Java.use('java.util.TreeMap');
    
    // Build same body
    var map = HashMap.$new();
    map.put("platform", "android");
    map.put("appid", "100002001");
    map.put("timestamp", "1750166660");
    map.put("packagename", "and.onemt.boe.tr");
    map.put("lang", "ar");
    map.put("sdid", "bot-001");
    map.put("channel", "googleplay");
    map.put("rstatus", "0");
    map.put("clientversion", "5.33.0");
    map.put("sessionid", "");
    map.put("originalid", "bot-001");
    map.put("deviceid", "bot-device-001");
    map.put("reqdata", "%7B%22name%22%3A%22test%40test.com%22%2C%22password%22%3A%22abc%22%2C%22identifytype%22%3A%22email%22%7D");
    map.put("securemode", "MD5");

    // Use the actual sortMapByKey
    var sortMethod = SdkHttpUtil.class.getDeclaredMethod("sortMapByKey", [Java.use("java.util.Map").class]);
    sortMethod.setAccessible(true);
    var sortedMap = sortMethod.invoke(null, [Java.cast(map, Java.use("java.util.Map"))]);
    
    // Convert to JSON using the actual method
    var sortedJson = SdkHttpUtil.mapToJsonStr(Java.cast(sortedMap, Java.use("java.util.Map")));
    send("SORTED_JSON=" + sortedJson);
    
    // Also get the keys in order
    var sortedKeys = Java.cast(sortedMap, Java.use("java.util.Map")).keySet().toArray();
    var keyOrder = [];
    for (var i = 0; i < sortedKeys.length; i++) {
        keyOrder.push(sortedKeys[i].toString());
    }
    send("KEY_ORDER=" + JSON.stringify(keyOrder));
    
    // Now test: httpSign result
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var appKey = SignUtil.getOriginAppKey();
    
    // sign = signWithAppKey(sortedJson) ?
    var s1 = SignUtil.signWithAppKey(sortedJson);
    send("signWithAppKey(sortedJson)=" + s1);
    
    // Call real sign
    var map2 = HashMap.$new();
    map2.put("platform", "android");
    map2.put("appid", "100002001");
    map2.put("timestamp", "1750166660");
    map2.put("packagename", "and.onemt.boe.tr");
    map2.put("lang", "ar");
    map2.put("sdid", "bot-001");
    map2.put("channel", "googleplay");
    map2.put("rstatus", "0");
    map2.put("clientversion", "5.33.0");
    map2.put("sessionid", "");
    map2.put("originalid", "bot-001");
    map2.put("deviceid", "bot-device-001");
    map2.put("reqdata", "%7B%22name%22%3A%22test%40test.com%22%2C%22password%22%3A%22abc%22%2C%22identifytype%22%3A%22email%22%7D");
    map2.put("securemode", "MD5");
    
    var s2 = SdkHttpUtil.sign(Java.cast(map2, Java.use("java.util.Map")), true);
    send("SdkHttpUtil.sign_return=" + s2);
    
    // Get the sign that httpSign added
    var signVal = map2.get("sign");
    send("httpSign_added_sign=" + (signVal ? signVal.toString() : "null"));
    
    send("DONE");
});
