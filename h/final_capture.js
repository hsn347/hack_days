// final_capture.js - الحل النهائي
// يعترض كل طلبات HTTP عبر RealCall + SdkHttpUrlManager

Java.perform(function() {
    
    // 1. Hook RealCall.execute - يمسك كل الطلبات HTTP
    try {
        var RealCall = Java.use('okhttp3.internal.connection.RealCall');
        var Buffer   = Java.use('okio.Buffer');
        var Charset  = Java.use('java.nio.charset.Charset');
        
        RealCall.execute.implementation = function() {
            var req = this.request();
            var url = req.url().toString();
            
            if (url.indexOf('onemt') >= 0 || url.indexOf('menaapp') >= 0 || 
                url.indexOf('apiuc') >= 0) {
                send("=== HTTP REQUEST ===");
                send("URL: " + url);
                send("Method: " + req.method());
                try {
                    var body = req.body();
                    if (body) {
                        var buf = Buffer.$new();
                        body.writeTo(buf);
                        var bodyStr = buf.readString(Charset.forName("UTF-8"));
                        send("BODY: " + bodyStr);
                    }
                } catch(e) { send("body err: " + e); }
            }
            return this.execute();
        };
        send("[OK] RealCall hooked");
    } catch(e) { send("RealCall err: " + e); }
    
    // 2. Hook SdkHttpUrlManager لمعرفة الـ base URL
    try {
        var UrlMgr = Java.use('com.onemt.sdk.core.http.SdkHttpUrlManager');
        var methods = UrlMgr.class.getDeclaredMethods();
        methods.forEach(function(m) { send("UrlMgr: " + m.toString()); });
    } catch(e) { send("UrlMgr err: " + e); }
    
    // 3. Hook UserBaseApiServiceFactory لمعرفة الـ base URL
    try {
        var Factory = Java.use('com.onemt.sdk.user.base.http.UserBaseApiServiceFactory');
        var fMethods = Factory.class.getDeclaredMethods();
        fMethods.forEach(function(m) { send("UBFactory: " + m.toString()); });
        
        // Hook كل methods
        fMethods.forEach(function(m) {
            try {
                m.setAccessible(true);
                var name = m.getName();
                var paramTypes = m.getParameterTypes();
                var overload = Factory[name];
                if (overload) {
                    send("Hooking Factory." + name);
                }
            } catch(e) {}
        });
    } catch(e) { send("UBFactory err: " + e); }
    
    // 4. Hook SdkUrlInterceptor
    try {
        var UrlInt = Java.use('com.onemt.sdk.core.http.SdkUrlInterceptor');
        var intMethods = UrlInt.class.getDeclaredMethods();
        intMethods.forEach(function(m) { send("SdkUrlInt: " + m.toString()); });
    } catch(e) { send("SdkUrlInt err: " + e); }
    
    // 5. Hook sign لالتقاط body الكامل
    try {
        var HttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
        HttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
            var r = this.sign(map, isUC);
            if (isUC) {
                var keys = map.keySet().toArray();
                var out = {};
                for (var i = 0; i < keys.length; i++) {
                    var k = keys[i].toString();
                    out[k] = (map.get(keys[i]) || '').toString();
                }
                send("=== UC SIGN BODY ===");
                send(JSON.stringify(out));
            }
            return r;
        };
        send("[OK] sign hooked");
    } catch(e) { send("sign err: " + e); }
    
    send("[*] ALL HOOKS READY - LOGIN NOW!");
});
