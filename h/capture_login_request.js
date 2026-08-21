// capture_login_request.js
// يعترض طلب HTTP login الفعلي ويطبع الـ body الكامل مع التوقيع
Java.perform(function() {

    // Hook OkHttp interceptor chain to capture the real login request
    try {
        var OkHttpClient = Java.use('okhttp3.OkHttpClient');
        var Request = Java.use('okhttp3.Request');
        var Response = Java.use('okhttp3.Response');
        var Chain = Java.use('okhttp3.Interceptor$Chain');

        // Hook the execute method
        var RealCall = Java.use('okhttp3.RealCall');
        RealCall.execute.implementation = function() {
            var req = this.request();
            var url = req.url().toString();
            if (url.indexOf("login") >= 0 || url.indexOf("account") >= 0 || 
                url.indexOf("user") >= 0 || url.indexOf("sdk") >= 0) {
                send("URL: " + url);
                var body = req.body();
                if (body) {
                    try {
                        var buf = Java.use('okio.Buffer').$new();
                        body.writeTo(buf);
                        send("BODY: " + buf.readUtf8());
                    } catch(e) { send("body err: " + e); }
                }
                // Headers
                var headers = req.headers();
                for (var i = 0; i < headers.size(); i++) {
                    send("HDR: " + headers.name(i) + "=" + headers.value(i));
                }
            }
            return this.execute();
        };
        send("RealCall.execute hooked");
    } catch(e) { send("RealCall hook err: " + e); }

    // Alternative: hook at the SdkHttpUtil level before signing
    try {
        var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
        SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
            var result = this.sign(map, isUC);
            // Collect all map entries
            var entries = "";
            var keys = map.keySet().toArray();
            for (var i = 0; i < keys.length; i++) {
                entries += keys[i] + "=" + map.get(keys[i]) + "&";
            }
            send("SdkHttpUtil.sign isUC=" + isUC + " map=" + entries);
            send("SdkHttpUtil.sign result=" + result);
            return result;
        };
        send("SdkHttpUtil.sign hooked");
    } catch(e) { send("SdkHttpUtil.sign hook err: " + e); }

    // Hook SignUtil.httpSign
    try {
        var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
        SignUtil.httpSign.implementation = function(ctx, jsonStr, isUC, outMap) {
            send("httpSign BEFORE json=" + jsonStr + " isUC=" + isUC);
            this.httpSign(ctx, jsonStr, isUC, outMap);
            send("httpSign AFTER sign=" + outMap.get("sign"));
        };
        send("SignUtil.httpSign hooked");
    } catch(e) { send("SignUtil.httpSign hook err: " + e); }

    send("[*] READY - trigger login in game now...");
});
