// get_uc_url.js
// يلتقط فقط: URL الـ UC login + الـ body الكامل مع الـ sign الصحيح
// لا يستخدم OkHttp

Java.perform(function() {
    
    // 1. التقاط URL من SdkRequestBodyFactory
    try {
        var Factory = Java.use('com.onemt.sdk.core.http.SdkRequestBodyFactory');
        
        // اطبع كل methods المتاحة
        var methods = Factory.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            send("FACTORY_METHOD: " + methods[i].toString());
        }
        
        // Hook createRequestBodyForUC بكل overloads
        Factory.class.getDeclaredMethods().forEach(function(method) {
            var mname = method.getName();
            if (mname.indexOf('UC') >= 0 || mname.indexOf('Request') >= 0 || mname.indexOf('Body') >= 0) {
                try {
                    var paramTypes = method.getParameterTypes();
                    var paramNames = [];
                    for (var p = 0; p < paramTypes.length; p++) {
                        paramNames.push(paramTypes[p].getName());
                    }
                    send("Hooking: " + mname + "(" + paramNames.join(",") + ")");
                    
                    method.setAccessible(true);
                    Java.use('java.lang.reflect.Method');
                } catch(e) { send("hook err: " + e); }
            }
        });
        
    } catch(e) { send("Factory err: " + e); }
    
    // 2. Hook SdkHttpUtil - التقاط الـ URL من خلاله
    try {
        var HttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
        var httpMethods = HttpUtil.class.getDeclaredMethods();
        for (var i = 0; i < httpMethods.length; i++) {
            send("HTTP_METHOD: " + httpMethods[i].toString());
        }
    } catch(e) { send("HttpUtil err: " + e); }
    
    // 3. Hook sign وطبع الـ body الكامل
    try {
        var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
        SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
            if (isUC) {
                var keys = map.keySet().toArray();
                var body = {};
                for (var i = 0; i < keys.length; i++) {
                    var k = keys[i].toString();
                    var v = map.get(keys[i]);
                    body[k] = v ? v.toString() : '';
                }
                send("=== UC LOGIN BODY ===");
                send(JSON.stringify(body, null, 2));
            }
            var r = this.sign(map, isUC);
            if (isUC) {
                body = body || {};
                body.sign = map.get('sign');
                send("SIGN: " + map.get('sign'));
            }
            return r;
        };
    } catch(e) { send("sign hook err: " + e); }
    
    // 4. البحث عن HTTP client - scan loaded classes
    var httpClasses = [];
    Java.enumerateLoadedClasses({
        onMatch: function(cls) {
            var cl = cls.toLowerCase();
            if ((cl.indexOf('onemt') >= 0 || cl.indexOf('okhttp') >= 0) && 
                (cl.indexOf('http') >= 0 || cl.indexOf('call') >= 0 || cl.indexOf('request') >= 0)) {
                httpClasses.push(cls);
                send("HTTP_CLS: " + cls);
            }
        },
        onComplete: function() {
            send("Total HTTP classes found: " + httpClasses.length);
        }
    });
    
    send("[*] Hooks ready - trigger login now...");
});
