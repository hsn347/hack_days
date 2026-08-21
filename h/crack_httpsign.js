// crack_httpsign.js
// نختبر httpSign بمدخلات بسيطة لفهم الخوارزمية
Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var HashMap = Java.use('java.util.HashMap');
    var ctx = OneMTCore.getApplicationContext();
    
    send("appKey=" + SignUtil.getOriginAppKey());
    send("gameAppKey=" + OneMTCore.getGameAppKey());
    
    // Test 1: simple map
    var m1 = HashMap.$new();
    m1.put("a", "1");
    SignUtil.httpSign(ctx, '{"a":"1"}', true, m1);
    send('httpSign({"a":"1"}, true) => sign=' + m1.get("sign"));
    
    // Test 2: same but isUC=false
    var m2 = HashMap.$new();
    m2.put("a", "1");
    SignUtil.httpSign(ctx, '{"a":"1"}', false, m2);
    send('httpSign({"a":"1"}, false) => sign=' + m2.get("sign"));
    
    // Test 3: different value
    var m3 = HashMap.$new();
    m3.put("b", "2");
    SignUtil.httpSign(ctx, '{"b":"2"}', true, m3);
    send('httpSign({"b":"2"}, true) => sign=' + m3.get("sign"));
    
    // Test 4: empty
    var m4 = HashMap.$new();
    SignUtil.httpSign(ctx, '{}', true, m4);
    send('httpSign({}, true) => sign=' + m4.get("sign"));
    
    // Test 5: just appid
    var m5 = HashMap.$new();
    m5.put("appid", "100002001");
    SignUtil.httpSign(ctx, '{"appid":"100002001"}', true, m5);
    send('httpSign({"appid":"100002001"}, true) => sign=' + m5.get("sign"));
    
    send("DONE");
});
