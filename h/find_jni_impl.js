// find_jni_impl.js
// إيجاد المكتبة التي تنفّذ httpSign و signWithAppKey فعلياً
Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    
    // Get the class loader
    var cls = SignUtil.class;
    send("ClassLoader: " + cls.getClassLoader());
    
    // Find native methods
    var methods = cls.getDeclaredMethods();
    for (var i = 0; i < methods.length; i++) {
        var m = methods[i];
        var mods = m.getModifiers();
        // Check if native (modifier 256)
        if ((mods & 256) !== 0) {
            send("NATIVE: " + m.getName() + " " + m.toString());
        }
    }
    
    // Try to find where httpSign JNI is loaded
    // List ALL loaded modules
    var mods = Process.enumerateModules();
    send("Total modules: " + mods.length);
    for (var i = 0; i < mods.length; i++) {
        var mod = mods[i];
        // Look for app-specific libs
        if (mod.path && (
            mod.path.indexOf("and.onemt") >= 0 ||
            mod.path.indexOf("data/data") >= 0 ||
            mod.name.indexOf("daemon") >= 0 ||
            mod.name.indexOf("sign") >= 0 ||
            mod.name.indexOf("crypt") >= 0
        )) {
            send("APP_LIB: " + mod.name + " @ " + mod.base + " path=" + mod.path);
            
            // Try to find httpSign or signWithAppKey in exports
            try {
                var exps = mod.enumerateExports();
                for (var j = 0; j < exps.length; j++) {
                    if (exps[j].name.indexOf("httpSign") >= 0 || 
                        exps[j].name.indexOf("signWith") >= 0 ||
                        exps[j].name.indexOf("SignUtil") >= 0 ||
                        exps[j].name.indexOf("Daemon") >= 0) {
                        send("  EXPORT: " + exps[j].name + " @ " + exps[j].address);
                    }
                }
            } catch(e) {}
        }
    }
    
    // Check /data/data path
    var File = Java.use("java.io.File");
    var dataDir = new File("/data/data/and.onemt.boe.tr/");
    if (dataDir.exists()) {
        var subDirs = dataDir.listFiles();
        if (subDirs) {
            for (var i = 0; i < subDirs.length; i++) {
                send("DATA: " + subDirs[i].getAbsolutePath());
            }
        }
    }
    
    send("DONE");
});
