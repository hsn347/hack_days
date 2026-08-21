// hook_jni_decrypt.js
// يعترض دالة decryptPacketForUC على مستوى native للحصول على bytes الحقيقية

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    var HashMap = Java.use('java.util.HashMap');
    
    var DAEMON = "4rB5GeN3NzcyJkePA4rGSxUAIGep4ecGHZi1S+ebb/n6jZ3o+ko34ZIqWtR1MbHOOnTh9nGViMgu5lqWx2r0QKSzi+UFWO+4WtPKYn5jRZdkpRDTcprXrMlvDj5/Y5eOe3AaG9qS/3O30m+YrLXd8oCNQrY2XnVgz0KNfPLXDf/8Uyo0CJ8CgSbC5MaTUg8imUrhiUqBm5eGjKNZPrVhr0lent/TjLSwyFk/f++qfe1pv2ctydVG/oVm4ZHHn2Xvqgtxm5KIvHkNPpSBZTvNZp61f59UQxbqAqaCy9M/pDi/p746gUUeX6LS+n38QAYqjoBg+YlZIyyxgWx1coNwKw==";
    
    // Find decryptPacketForUC native function in libdaemonutil.so
    var lib = Process.findModuleByName('libdaemonutil.so');
    if (!lib) { send("libdaemonutil.so not found"); }
    else {
        send("libdaemonutil.so base: " + lib.base + " size: " + lib.size);
        
        // Search for JNI function name
        var jniName = 'Java_com_onemt_sdk_component_cryptoutil_SignUtil_decryptPacketForUC';
        var exp = Module.findExportByName('libdaemonutil.so', jniName);
        send("Export " + jniName + ": " + exp);
        
        // Try with findExportByName for all names in the module
        var exports = lib.enumerateExports();
        send("Total exports: " + exports.length);
        for (var i = 0; i < exports.length; i++) {
            var e = exports[i];
            if (e.name.indexOf('decrypt') >= 0 || e.name.indexOf('sign') >= 0 || 
                e.name.indexOf('Sign') >= 0 || e.name.indexOf('http') >= 0 ||
                e.name.indexOf('Http') >= 0) {
                send("EXPORT: " + e.name + " @ " + e.address);
            }
        }
    }
    
    // Alternative: hook at Java level but use codePointAt for unicode
    send("Trying codePointAt approach...");
    try {
        var dec = SignUtil.decryptPacketForUC(DAEMON);
        // dec is JS string - use codePointAt (not charCodeAt)
        var hex = "";
        var i = 0;
        var len = dec.length;
        while (i < len) {
            var cp = dec.codePointAt(i);
            hex += ('0000' + cp.toString(16)).slice(-4); // 4 hex chars = 16-bit
            i++;
        }
        send("CODEPOINT_HEX_LEN=" + len);
        send("CODEPOINT_HEX=" + hex);
    } catch(e) {
        send("codePointAt err: " + e);
    }
    
    send("DONE");
});
