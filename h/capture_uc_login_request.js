// capture_uc_login_request.js
// يعترض الـ HTTP request الكامل لـ UC login عند الضغط على login في اللعبة

Java.perform(function() {
    // Hook OkHttp3 at the highest level - before request is sent
    var OkHttpClient = Java.use('okhttp3.OkHttpClient');
    var Chain = Java.use('okhttp3.Interceptor$Chain');
    var RequestBody = Java.use('okhttp3.RequestBody');
    var Buffer = Java.use('okio.Buffer');
    var Charset = Java.use('java.nio.charset.Charset');
    
    // Also hook SdkHttpUtil.sign to capture exact body before sign is added
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    
    SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
        if (isUC) {
            // Get body
            var keys = map.keySet().toArray();
            var bodyStr = '';
            for (var i = 0; i < keys.length; i++) {
                var key = keys[i].toString();
                var val = map.get(keys[i]);
                bodyStr += key + '=' + (val ? val.toString() : '') + '&';
            }
            send("=== UC REQUEST BODY (before sign) ===");
            send("BODY: " + bodyStr);
        }
        var r = this.sign(map, isUC);
        if (isUC) {
            var sign = map.get("sign");
            send("UC SIGN: " + sign);
        }
        return r;
    };
    
    // Hook LoginManager to capture UC login request URL
    try {
        var SdkRequestBodyFactory = Java.use('com.onemt.sdk.core.http.SdkRequestBodyFactory');
        SdkRequestBodyFactory.createRequestBodyForUC.implementation = function(map, url) {
            send("createRequestBodyForUC URL: " + (url ? url.toString() : 'null'));
            send("createRequestBodyForUC MAP keys: " + map.keySet().toString());
            return this.createRequestBodyForUC(map, url);
        };
    } catch(e) { send("createRequestBodyForUC hook err: " + e); }
    
    // Hook OkHttp Request to get URL
    try {
        var Request = Java.use('okhttp3.Request');
        var RequestBuilder = Java.use('okhttp3.Request$Builder');
        
        // Hook RealCall to capture URL
        var RealCall = Java.use('okhttp3.internal.connection.RealCall');
        RealCall.execute.implementation = function() {
            var req = this.request();
            var url = req.url().toString();
            if (url.indexOf('user') >= 0 || url.indexOf('login') >= 0 || url.indexOf('onemt') >= 0) {
                send("=== HTTP REQUEST ===");
                send("URL: " + url);
                send("Method: " + req.method());
                // Get body
                try {
                    var body = req.body();
                    if (body) {
                        var buf = Buffer.$new();
                        body.writeTo(buf);
                        send("BODY: " + buf.readString(Charset.forName("UTF-8")));
                    }
                } catch(e) { send("body err: " + e); }
            }
            return this.execute();
        };
    } catch(e) { send("RealCall hook err: " + e); }
    
    send("[*] Hooks ready. Trigger login in game now...");
});
