// capture_real_login2.js
// يُشغّل login الحقيقي مباشرة من الكود ويلتقط التوقيع
Java.perform(function() {
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');

    SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
        var keys = map.keySet().toArray();
        var obj = {};
        for (var i = 0; i < keys.length; i++) {
            obj[keys[i]] = map.get(keys[i]);
        }
        send("PRE_SIGN isUC=" + isUC + " keys=" + JSON.stringify(Object.keys(obj)));
        var result = this.sign(map, isUC);
        var finalKeys = map.keySet().toArray();
        var finalObj = {};
        for (var i = 0; i < finalKeys.length; i++) {
            finalObj[finalKeys[i]] = map.get(finalKeys[i]);
        }
        send("POST_SIGN=" + JSON.stringify(finalObj));
        return result;
    };

    // Now trigger the real UC login via the SDK
    try {
        var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
        var ctx = OneMTCore.getApplicationContext();
        
        // Find the login controller/manager
        var AccountManager = Java.use('com.onemt.sdk.user.base.AccountManager').getInstance();
        
        // Try to trigger a login with email
        var LoginCtrl = Java.use('com.onemt.sdk.user.login.OneMTLoginCtrl');
        send("Calling loginWithEmail...");
        LoginCtrl.loginWithEmail(ctx, "test@test.com", "test123", null);
    } catch(e) {
        send("loginWithEmail err: " + e);
    }
    
    try {
        // Alternative: find SdkRequestBodyFactory and build login request manually
        var Factory = Java.use('com.onemt.sdk.core.http.SdkRequestBodyFactory');
        var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
        var ctx = OneMTCore.getApplicationContext();
        
        // createRequestBodyForUC
        var HashMap = Java.use('java.util.HashMap');
        var reqMap = HashMap.$new();
        reqMap.put("name", "test@test.com");
        reqMap.put("password", "test123");
        reqMap.put("identifytype", "email");
        
        send("Calling createRequestBodyForUC...");
        var body = Factory.createRequestBodyForUC(ctx, reqMap);
        send("Body type: " + body);
    } catch(e2) {
        send("Factory err: " + e2);
    }
    
    send("DONE");
});
