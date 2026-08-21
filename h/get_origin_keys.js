// get_origin_keys.js
// يحصل على المفاتيح الأصلية من SignUtil + certificate + daemon

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    
    // 1. Try getOriginAppKey
    try {
        var origKey = SignUtil.getOriginAppKey();
        send("getOriginAppKey: " + origKey);
    } catch(e) { send("getOriginAppKey err: " + e); }
    
    // 2. Try all static methods on SignUtil
    try {
        var methods = SignUtil.class.getDeclaredMethods();
        for (var i = 0; i < methods.length; i++) {
            var m = methods[i];
            var name = m.getName();
            var types = m.getParameterTypes();
            if (types.length === 0) {
                try {
                    m.setAccessible(true);
                    var result = m.invoke(null, []);
                    if (result) send("SignUtil." + name + "() = " + result.toString().substring(0, 200));
                } catch(e) {}
            }
            send("METHOD: " + name + " params=" + types.length + " return=" + m.getReturnType().getName());
        }
    } catch(e) { send("methods err: " + e); }
    
    // 3. Get certificate/signing info
    try {
        var pm = ctx.getPackageManager();
        var info = pm.getPackageInfo("and.onemt.boe.tr", 0x40); // GET_SIGNATURES = 64
        var sigs = info.signatures.value;
        for (var i = 0; i < sigs.length; i++) {
            var certBytes = sigs[i].toByteArray();
            // Get MD5 of cert
            var md5 = Java.use('java.security.MessageDigest').getInstance('MD5');
            md5.update(certBytes);
            var digest = md5.digest();
            var hexCert = "";
            for (var j = 0; j < digest.length; j++) {
                hexCert += ('0' + (digest[j] & 0xff).toString(16)).slice(-2);
            }
            send("CERT_MD5[" + i + "]: " + hexCert);
            
            var sha1 = Java.use('java.security.MessageDigest').getInstance('SHA-1');
            sha1.update(certBytes);
            var sha1d = sha1.digest();
            var hexSHA1 = "";
            for (var j = 0; j < sha1d.length; j++) {
                hexSHA1 += ('0' + (sha1d[j] & 0xff).toString(16)).slice(-2);
            }
            send("CERT_SHA1[" + i + "]: " + hexSHA1);
        }
    } catch(e) { send("cert err: " + e); }
    
    // 4. Try SDKDaemon via static field access
    try {
        var SDKDaemon = Java.use('com.onemt.sdk.component.daemon.SDKDaemon');
        var fields = SDKDaemon.class.getDeclaredFields();
        for (var i = 0; i < fields.length; i++) {
            fields[i].setAccessible(true);
            try {
                var val = fields[i].get(null); // static field
                if (val) send("DAEMON_STATIC_" + fields[i].getName() + ": " + val.toString().substring(0,200));
            } catch(e) {}
        }
        
        var daemonMethods = SDKDaemon.class.getDeclaredMethods();
        for (var i = 0; i < daemonMethods.length; i++) {
            send("DAEMON_METHOD: " + daemonMethods[i].getName() + " " + daemonMethods[i].toString().substring(0,100));
        }
    } catch(e) { send("daemon err: " + e); }
    
    send("DONE");
});
