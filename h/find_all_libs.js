// find_all_libs.js - إيجاد كل المكتبات المحملة
Java.perform(function() {
    var mods = Process.enumerateModules();
    send("=== ALL LOADED MODULES (" + mods.length + ") ===");
    for (var i = 0; i < mods.length; i++) {
        var m = mods[i];
        // Skip system libs
        if (m.path && (
            m.path.indexOf("/system/") < 0 &&
            m.path.indexOf("/vendor/") < 0 &&
            m.path.indexOf("libandroid") < 0
        )) {
            send(m.name + " | " + m.path);
        }
    }
    
    // Find signWithAppKey JNI function pointer
    // It's registered with RegisterNatives or via name mangling
    // Java method: com.onemt.sdk.component.cryptoutil.SignUtil.signWithAppKey
    // JNI name: Java_com_onemt_sdk_component_cryptoutil_SignUtil_signWithAppKey
    var jniName = "Java_com_onemt_sdk_component_cryptoutil_SignUtil_signWithAppKey";
    var jniName2 = "Java_com_onemt_sdk_component_daemon_OneMTDaemonUtil_httpSign";
    
    for (var i = 0; i < mods.length; i++) {
        try {
            var exps = mods[i].enumerateExports();
            for (var j = 0; j < exps.length; j++) {
                if (exps[j].name === jniName || exps[j].name === jniName2 ||
                    exps[j].name.indexOf("SignUtil") >= 0 ||
                    exps[j].name.indexOf("httpSign") >= 0) {
                    send("FOUND JNI: " + exps[j].name + " in " + mods[i].name);
                }
            }
        } catch(e) {}
    }
    
    send("DONE");
});
