// hook_all_signs.js
// يعترض كل methods توقيع ثم يُشغّل login حقيقي عبر SDK
Java.perform(function() {

    // Hook 1: httpSign (native)
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    SignUtil.httpSign.implementation = function(ctx, json, isUC, map) {
        send("httpSign called: json=" + json.substring(0,200) + " isUC=" + isUC);
        this.httpSign(ctx, json, isUC, map);
        send("httpSign result: sign=" + map.get("sign"));
    };

    // Hook 2: signWithAppKey (native)
    SignUtil.signWithAppKey.implementation = function(input) {
        var result = this.signWithAppKey(input);
        send("signWithAppKey: in=" + input.substring(0,100) + " out=" + result);
        return result;
    };

    // Hook 3: Find SdkHttpUtil.sign overloads
    try {
        var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
        var overloads = SdkHttpUtil.sign.overloads;
        send("SdkHttpUtil.sign overloads: " + overloads.length);
        overloads.forEach(function(ov) {
            send("  overload: " + ov.returnType + " " + JSON.stringify(ov.argumentTypes.map(function(t) { return t.name; })));
        });
        
        // Try to hook all overloads
        for (var i = 0; i < overloads.length; i++) {
            (function(ov) {
                ov.implementation = function() {
                    var args = Array.from(arguments).map(function(a) {
                        try { return String(a); } catch(e) { return "?"; }
                    });
                    send("SdkHttpUtil.sign called: " + JSON.stringify(args.map(function(a) { return a.substring(0,100); })));
                    var result = ov.apply(this, arguments);
                    send("SdkHttpUtil.sign result: " + result);
                    return result;
                };
            })(overloads[i]);
        }
    } catch(e) { send("SdkHttpUtil err: " + e); }
    
    // Now trigger a test login to see what isUC is used
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    var HashMap = Java.use('java.util.HashMap');
    
    // Test httpSign with empty session (like a real login)
    var loginMap = HashMap.$new();
    loginMap.put("appid", "100002001");
    loginMap.put("channel", "googleplay");
    loginMap.put("sessionid", "");
    loginMap.put("timestamp", "" + Math.floor(Date.now()/1000));
    loginMap.put("reqdata", "test");
    
    // Try isUC=false (MD5 mode)
    var m1 = HashMap.$new(); m1.put("a","1");
    send("=== Testing isUC=false ===");
    SignUtil.httpSign(ctx, '{"a":"1"}', false, m1);
    send("isUC=false: sign=" + m1.get("sign"));
    
    // Try isUC=true  
    var m2 = HashMap.$new(); m2.put("a","1");
    send("=== Testing isUC=true ===");
    SignUtil.httpSign(ctx, '{"a":"1"}', true, m2);
    send("isUC=true: sign=" + m2.get("sign"));

    // Find the real login method
    Java.enumerateLoadedClasses({
        onMatch: function(name) {
            var low = name.toLowerCase();
            if (low.indexOf('onemt') >= 0 && (low.indexOf('login') >= 0 || 
                low.indexOf('user') >= 0 || low.indexOf('account') >= 0)) {
                send("LOGIN_CLASS: " + name);
            }
        },
        onComplete: function() { send("ENUM_DONE"); }
    });
    
    send("SETUP_DONE");
});
