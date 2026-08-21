// crack_uc_key.js
// نستخدم cachedDaemonResult كمفتاح ونختبر
Java.perform(function() {
    var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    
    // Get cached result
    var f = SDKDaemon.class.getDeclaredField("cachedDaemonResult");
    f.setAccessible(true);
    var daemonResult = f.get(null).toString();
    send("daemonResult=" + daemonResult);
    
    // Try getString methods
    try {
        var methods = SDKDaemon.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            if (methods[i].getName() === "getString") {
                send("getString params: " + methods[i].getParameterTypes().length);
                var paramTypes = methods[i].getParameterTypes();
                for (var j = 0; j < paramTypes.length; j++) {
                    send("  param " + j + ": " + paramTypes[j].getName());
                }
            }
            if (methods[i].getName() === "native_get") {
                send("native_get params: " + methods[i].getParameterTypes().length);
                var paramTypes = methods[i].getParameterTypes();
                for (var j = 0; j < paramTypes.length; j++) {
                    send("  param " + j + ": " + paramTypes[j].getName());
                }
            }
        }
    } catch(e) { send("err: " + e); }
    
    // Try calling getString
    try {
        var gs1 = SDKDaemon.getString(daemonResult, "sign");
        send("getString(daemon, 'sign')=" + gs1);
    } catch(e) { send("getString err1: " + e); }
    
    try {
        var gs2 = SDKDaemon.getString(daemonResult, 0);
        send("getString(daemon, 0)=" + gs2);
    } catch(e) { send("getString err2: " + e); }
    
    // Try native_get
    try {
        var ng = SDKDaemon.native_get(0);
        send("native_get(0)=" + ng);
    } catch(e) { send("native_get err: " + e); }
    
    try {
        var ng1 = SDKDaemon.native_get("sign");
        send("native_get('sign')=" + ng1);
    } catch(e) { send("native_get err2: " + e); }
    
    // Try to find the actual UC key by hooking at lower level
    // Intercept the native httpSign
    var mod = Process.findModuleByName("libonemt_daemon.so") || 
              Process.findModuleByName("libsign.so") ||
              Process.findModuleByName("libcryptoutil.so");
    
    if (!mod) {
        // Find all modules
        Process.enumerateModules().forEach(function(m) {
            if (m.path.indexOf("and.onemt") >= 0) {
                send("APP_MODULE: " + m.name + " @ " + m.path);
            }
        });
    } else {
        send("Found module: " + mod.name);
    }
    
    send("DONE");
});
