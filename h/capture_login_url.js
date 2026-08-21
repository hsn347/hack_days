// capture_login_url.js
// يعترض طلب HTTP login الكامل - يحصل على URL + body + sign

Java.perform(function() {
    
    // 1. Hook SdkHttpUtil.sign لالتقاط الـ body
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    var capturedBody = null;
    var capturedSign = null;
    
    SdkHttpUtil.sign.overload('java.util.Map', 'boolean').implementation = function(map, isUC) {
        if (isUC) {
            var obj = {};
            var keys = map.keySet().toArray();
            for (var i = 0; i < keys.length; i++) {
                var k = keys[i].toString();
                var v = map.get(keys[i]);
                obj[k] = v ? v.toString() : '';
            }
            capturedBody = obj;
        }
        var r = this.sign(map, isUC);
        if (isUC) {
            capturedSign = map.get("sign");
        }
        return r;
    };
    
    // 2. Hook java.net.URL - system class, always available
    var URL = Java.use('java.net.URL');
    URL.openConnection.overload().implementation = function() {
        var urlStr = this.toString();
        if (urlStr.indexOf('onemt') >= 0 || urlStr.indexOf('uc.') >= 0 || 
            urlStr.indexOf('user') >= 0 || urlStr.indexOf('login') >= 0) {
            send("URL.openConnection: " + urlStr);
        }
        return this.openConnection();
    };
    
    // 3. Hook okhttp - find shaded class
    // The app uses a shaded/renamed okhttp - find it
    var classLoaderWrapper = Java.use('java.lang.ClassLoader');
    var currentClassLoader = Java.classFactory.loader;
    
    // Search for HTTP client class
    var okHttpNames = [
        'com.onemt.sdk.core.http.d',
        'com.onemt.sdk.core.http.HttpClient',
        'com.onemt.okhttp3.OkHttpClient',
        'okhttp3.OkHttpClient',
    ];
    
    for (var i = 0; i < okHttpNames.length; i++) {
        try {
            var cls = Java.use(okHttpNames[i]);
            send("Found HTTP class: " + okHttpNames[i]);
            break;
        } catch(e) {}
    }
    
    // 4. Hook HttpURLConnection for all HTTP calls
    var HttpURLConnection = Java.use('java.net.HttpURLConnection');
    HttpURLConnection.connect.implementation = function() {
        try {
            var url = this.getURL().toString();
            if (url.indexOf('onemt') >= 0 || url.indexOf('uc.') >= 0) {
                send("HttpURLConnection.connect: " + url);
                send("Method: " + this.getRequestMethod());
            }
        } catch(e) {}
        return this.connect();
    };
    
    // 5. أهم: Hook Retrofit OkHttp call via scanning all loaded classes
    // البحث عن كلاسات الـ HTTP
    Java.enumerateLoadedClasses({
        onMatch: function(cls) {
            if (cls.indexOf('okhttp') >= 0 || cls.indexOf('OkHttp') >= 0 || 
                cls.indexOf('retrofit') >= 0 || cls.indexOf('Retrofit') >= 0) {
                send("HTTP class: " + cls);
            }
        },
        onComplete: function() { send("Scan done"); }
    });
    
    send("[*] Ready - trigger login in game now...");
});
