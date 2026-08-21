// test_sign_match.js
// نبني نفس الـ body ونقارن sign
Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    var appKey = SignUtil.getOriginAppKey();
    
    // Build the same body we're sending from Python
    var body = {
        "platform": "android",
        "appid": "100002001",
        "timestamp": "1750166660",
        "packagename": "and.onemt.boe.tr",
        "lang": "ar",
        "sdid": "bot-001",
        "channel": "googleplay",
        "rstatus": "0",
        "clientversion": "5.33.0",
        "sessionid": "",
        "originalid": "bot-001",
        "deviceid": "bot-device-001",
        "reqdata": "%7B%22name%22%3A%22test%40test.com%22%2C%22password%22%3A%22abc%22%2C%22identifytype%22%3A%22email%22%7D",
        "securemode": "MD5"
    };
    
    // Sort keys and build JSON
    var keys = Object.keys(body).sort();
    var sorted = {};
    for (var i = 0; i < keys.length; i++) sorted[keys[i]] = body[keys[i]];
    
    // Use Java's Gson to match exact JSON format
    var GsonBuilder = Java.use('com.google.gson.GsonBuilder');
    var gson = GsonBuilder.$new().disableHtmlEscaping().create();
    var HashMap = Java.use('java.util.HashMap');
    var map = HashMap.$new();
    for (var k in sorted) map.put(k, sorted[k]);
    var jsonStr = gson.toJson(Java.cast(map, Java.use('java.lang.Object')));
    send("sorted_json=" + jsonStr);
    
    // signWithAppKey
    var sign1 = SignUtil.signWithAppKey(jsonStr);
    send("signWithAppKey(sortedJson)=" + sign1);
    
    // Now test with SdkHttpUtil.sign on a real map
    var map2 = HashMap.$new();
    for (var k in body) map2.put(k, body[k]);
    
    var sign2 = SdkHttpUtil.sign(Java.cast(map2, Java.use('java.util.Map')), true);
    send("SdkHttpUtil.sign(map,true)=" + sign2);
    
    // Check if httpSign added anything to map
    var it = map2.entrySet().iterator();
    while (it.hasNext()) {
        var entry = Java.cast(it.next(), Java.use('java.util.Map$Entry'));
        var k = entry.getKey().toString();
        if (!(k in body)) {
            send("ADDED_BY_httpSign: " + k + "=" + entry.getValue().toString());
        }
    }
    
    send("DONE");
});
