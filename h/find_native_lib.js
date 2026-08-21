// find_native_lib.js  
// إيجاد المكتبة الأصلية التي تحتوي httpSign
Java.perform(function() {
    // Search all modules for httpSign export
    var modules = Process.enumerateModules();
    for (var i = 0; i < modules.length; i++) {
        var m = modules[i];
        try {
            var exports = m.enumerateExports();
            for (var j = 0; j < exports.length; j++) {
                if (exports[j].name.indexOf("httpSign") >= 0 || 
                    exports[j].name.indexOf("signWithAppKey") >= 0 ||
                    exports[j].name.indexOf("encryptPacket") >= 0 ||
                    exports[j].name.indexOf("SignUtil") >= 0) {
                    send("FOUND: " + m.name + " -> " + exports[j].name + " @ " + exports[j].address);
                }
            }
        } catch(e) {}
    }
    
    // Also try resolving the JNI function directly
    var addr = Module.findExportByName(null, "Java_com_onemt_sdk_component_cryptoutil_SignUtil_httpSign");
    send("httpSign addr: " + addr);
    
    var addr2 = Module.findExportByName(null, "Java_com_onemt_sdk_component_cryptoutil_SignUtil_signWithAppKey");
    send("signWithAppKey addr: " + addr2);
    
    // Try getString from daemon with the cached result
    var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
    try {
        var r1 = SDKDaemon.getString("appkey");
        send("getString('appkey')=" + r1);
    } catch(e) {}
    try {
        var r2 = SDKDaemon.getString("sign_key");
        send("getString('sign_key')=" + r2);
    } catch(e) {}
    try {
        var r3 = SDKDaemon.getString("uc_key");  
        send("getString('uc_key')=" + r3);
    } catch(e) {}
    try {
        var r4 = SDKDaemon.getString("key");
        send("getString('key')=" + r4);
    } catch(e) {}
    try {
        var r5 = SDKDaemon.native_get("appkey", "default");
        send("native_get('appkey','default')=" + r5);
    } catch(e) {}
    try {
        var r6 = SDKDaemon.native_get("sign", "default");
        send("native_get('sign','default')=" + r6);
    } catch(e) {}
    
    send("DONE");
});
