// find_native_lib2.js
Java.perform(function() {
    var modules = Process.enumerateModules();
    for (var i = 0; i < modules.length; i++) {
        var m = modules[i];
        try {
            var exports = m.enumerateExports();
            for (var j = 0; j < exports.length; j++) {
                var n = exports[j].name;
                if (n.indexOf("Sign") >= 0 || n.indexOf("sign") >= 0 || n.indexOf("httpSign") >= 0) {
                    send(m.name + " -> " + n + " @ " + exports[j].address);
                }
            }
        } catch(e) {}
    }
    
    // Try SDKDaemon.getString
    var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
    var keys = ["appkey", "sign_key", "uc_key", "key", "secret", "app_key", "signKey"];
    for (var i = 0; i < keys.length; i++) {
        try {
            var r = SDKDaemon.getString(keys[i]);
            send("getString('" + keys[i] + "')=" + r);
        } catch(e) {}
    }
    
    send("DONE");
});
