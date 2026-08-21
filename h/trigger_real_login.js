// trigger_real_login.js
// يُشغّل login حقيقي عبر PassportManager ويعترض التوقيع

Java.perform(function() {
    var capturedIsUC = null;
    var capturedBody = null;
    var capturedSign = null;

    // Hook SdkHttpUtil.sign
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
        var keys = map.keySet().toArray();
        var body = {};
        for (var i = 0; i < keys.length; i++) {
            body[keys[i]] = map.get(keys[i]);
        }
        send("SdkHttpUtil.sign isUC=" + isUC);
        send("  body=" + JSON.stringify(body));
        capturedIsUC = isUC;
        capturedBody = JSON.stringify(body);
        var result = this.sign(map, isUC);
        capturedSign = map.get("sign");
        send("  sign=" + capturedSign);
        return result;
    };

    // Hook httpSign 
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    SignUtil.httpSign.implementation = function(ctx, json, isUC, map) {
        send("httpSign json=" + json.substring(0,300) + " isUC=" + isUC);
        this.httpSign(ctx, json, isUC, map);
        send("httpSign sign=" + map.get("sign"));
    };

    send("Hooks ready. Finding PassportManager methods...");
    
    // Inspect PassportManager
    try {
        var PM = Java.use('com.onemt.sdk.user.base.PassportManager');
        var methods = PM.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            send("PM." + methods[i].getName() + " " + methods[i].toString().substring(0,100));
        }
    } catch(e) { send("PM err: " + e); }
    
    // Inspect UserLoginHelper
    try {
        var ULH = Java.use('com.onemt.sdk.user.base.UserLoginHelper');
        var methods = ULH.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            send("ULH." + methods[i].getName() + " " + methods[i].toString().substring(0,100));
        }
    } catch(e) { send("ULH err: " + e); }
    
    // Inspect BaseApi
    try {
        var BA = Java.use('com.onemt.sdk.user.BaseApi');
        var methods = BA.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            send("BA." + methods[i].getName() + " " + methods[i].toString().substring(0,100));
        }
    } catch(e) { send("BA err: " + e); }

    // Look at UserBaseApiService
    try {
        var UBAS = Java.use('com.onemt.sdk.user.base.http.UserBaseApiService');
        var methods = UBAS.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            send("UBAS." + methods[i].getName() + " " + methods[i].toString().substring(0,150));
        }
    } catch(e) { send("UBAS err: " + e); }

    send("DONE");
});
