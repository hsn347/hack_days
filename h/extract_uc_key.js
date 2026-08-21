// extract_uc_key.js
// نستخرج المفتاح المستخدم في UC sign عبر brute-force بسيط
// نعرف أن: httpSign('{}', true) = d01ac4e2ad28d6503a38ec9f779bf424
// لو sign = md5('{}' + KEY) فنحتاج إيجاد KEY
// بدلاً من ذلك، نستخدم الـ daemon مباشرة

Java.perform(function() {
    // Look for the daemon or the actual signing function
    var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
    
    // List all methods
    var methods = SDKDaemon.class.getDeclaredMethods();
    var methodNames = [];
    for (var i = 0; i < methods.length; i++) {
        methodNames.push(methods[i].getName());
    }
    send("SDKDaemon methods: " + JSON.stringify(methodNames));
    
    // Check fields
    var fields = SDKDaemon.class.getDeclaredFields();
    for (var i = 0; i < fields.length; i++) {
        fields[i].setAccessible(true);
        try {
            var val = fields[i].get(null);
            send("Field: " + fields[i].getName() + " = " + (val ? val.toString().substring(0, 100) : "null"));
        } catch(e) {
            send("Field: " + fields[i].getName() + " (instance field)");
        }
    }
    
    // Try to get the UC key directly
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    
    // List all native libs loaded
    var System = Java.use('java.lang.System');
    
    // Find the .so file
    send("Looking for native library...");
    var Runtime = Java.use('java.lang.Runtime');
    
    // Try to find exported symbols
    var modules = Process.enumerateModules();
    for (var i = 0; i < modules.length; i++) {
        if (modules[i].name.indexOf('sign') >= 0 || modules[i].name.indexOf('crypt') >= 0 || modules[i].name.indexOf('daemon') >= 0 || modules[i].name.indexOf('onemt') >= 0) {
            send("Module: " + modules[i].name + " @ " + modules[i].base);
        }
    }
    
    send("DONE");
});
