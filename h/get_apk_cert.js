// get_apk_cert.js
// استخراج شهادة توقيع APK + اختبار كمفتاح sign
Java.perform(function() {
    var ctx = Java.use('com.onemt.sdk.core.OneMTCore').getApplicationContext();
    var pm = ctx.getPackageManager();
    var pi = pm.getPackageInfo("and.onemt.boe.tr", 64); // GET_SIGNATURES=64
    var sigs = pi.signatures.value;
    
    var sig = sigs[0];
    var sigBytes = sig.toByteArray();
    
    // MD5 of signature
    var md = Java.use('java.security.MessageDigest').getInstance("MD5");
    md.update(sigBytes);
    var digest = md.digest();
    var hex = "";
    for (var i = 0; i < digest.length; i++) {
        var b = (digest[i] & 0xff).toString(16);
        if (b.length < 2) b = "0" + b;
        hex += b;
    }
    send("cert_md5=" + hex);
    
    // SHA1 of signature
    var md2 = Java.use('java.security.MessageDigest').getInstance("SHA-1");
    md2.update(sigBytes);
    var digest2 = md2.digest();
    var hex2 = "";
    for (var i = 0; i < digest2.length; i++) {
        var b = (digest2[i] & 0xff).toString(16);
        if (b.length < 2) b = "0" + b;
        hex2 += b;
    }
    send("cert_sha1=" + hex2);
    
    // SHA256 of signature  
    var md3 = Java.use('java.security.MessageDigest').getInstance("SHA-256");
    md3.update(sigBytes);
    var digest3 = md3.digest();
    var hex3 = "";
    for (var i = 0; i < digest3.length; i++) {
        var b = (digest3[i] & 0xff).toString(16);
        if (b.length < 2) b = "0" + b;
        hex3 += b;
    }
    send("cert_sha256=" + hex3);
    
    // Raw cert bytes (first 64 as hex)
    var rawHex = "";
    for (var i = 0; i < Math.min(64, sigBytes.length); i++) {
        var b = (sigBytes[i] & 0xff).toString(16);
        if (b.length < 2) b = "0" + b;
        rawHex += b;
    }
    send("cert_raw_first64=" + rawHex);
    send("cert_len=" + sigBytes.length);
    
    // Also get the hashCode
    send("cert_hashcode=" + sig.hashCode());
    
    send("DONE");
});
