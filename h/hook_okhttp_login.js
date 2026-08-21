// hook_okhttp_login.js
// يعترض OkHttp request عند استدعاء login
// هذا يكشف isUC والـ body الكامل

Java.perform(function() {
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    
    // Hook SdkHttpUtil.sign - single overload [Map, boolean]
    SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
        // Get a stack trace to know who called this
        var stack = Java.use('java.lang.Thread').currentThread().getStackTrace();
        var callers = [];
        for (var i = 2; i < Math.min(stack.length, 8); i++) {
            callers.push(stack[i].getClassName() + "." + stack[i].getMethodName());
        }
        
        // Get all map entries
        var keys = map.keySet().toArray();
        var body = {};
        for (var i = 0; i < keys.length; i++) {
            body[keys[i]] = map.get(keys[i]);
        }
        
        send("=== SdkHttpUtil.sign called ===");
        send("isUC=" + isUC);
        send("BODY=" + JSON.stringify(body));
        send("CALLERS=" + callers.join(" -> "));
        
        var result = this.sign(map, isUC);
        send("SIGN=" + map.get("sign"));
        send("===");
        
        return result;
    };

    send("[*] Hook ready. Trigger login in game now...");
    
    // setInterval to keep alive 60 seconds
    var count = 0;
    var timer = setInterval(function() {
        count++;
        send("Waiting... " + count);
        if (count >= 12) { // 60 seconds
            clearInterval(timer);
            send("Timeout. Exiting.");
        }
    }, 5000);
});
