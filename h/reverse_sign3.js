// reverse_sign3.js - التقاط الـ sign بدون hook native
// نراقب SdkHttpUtil.sign ونرى المدخل والمخرج فقط
Java.perform(function() {
    // Hook the OkHttp interceptor to see the final request
    var SdkPacketInterceptor = Java.use('com.onemt.sdk.core.http.SdkPacketInterceptor');
    SdkPacketInterceptor.intercept.implementation = function(chain) {
        var request = chain.request();
        var body = request.f(); // requestBody
        if (body) {
            var at = Java.use('com.onemt.sdk.launch.base.at');
            var buffer = at.$new();
            body.writeTo(buffer);
            var bodyStr = buffer.readUtf8();
            send("=== HTTP REQUEST BODY (before encrypt) ===");
            send(bodyStr.substring(0, 1000));
        }
        
        var url = request.m().toString();
        send("URL: " + url);
        
        // Check for encrypt header
        var encHeader = request.i("encrypt");
        send("encrypt header: " + encHeader);
        
        return this.intercept(chain);
    };
    
    send("[*] Interceptor hooked. Do anything in game...");
});
