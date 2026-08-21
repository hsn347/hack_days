// hook_crypto4.js
Java.perform(function() {
    // Test what Module API is available
    send("Module type: " + typeof Module);
    send("Module.findExportByName: " + typeof Module.findExportByName);
    send("Module.getExportByName: " + typeof Module.getExportByName);
    
    // Try to find HMAC using the available API
    try {
        var addr = Module.findExportByName(null, "HMAC_Init_ex");
        send("HMAC_Init_ex (null): " + addr);
    } catch(e) { send("findExportByName(null): " + e); }
    
    try {
        var addr2 = Module.getExportByName(null, "HMAC_Init_ex");
        send("HMAC_Init_ex getExport: " + addr2);
    } catch(e) { send("getExportByName: " + e); }
    
    // Try DebugSymbol
    try {
        var sym = DebugSymbol.getFunctionByName("HMAC_Init_ex");
        send("DebugSymbol HMAC: " + sym);
    } catch(e) { send("DebugSymbol: " + e); }
    
    // List all exports from libcrypto
    try {
        var mods = Process.enumerateModules();
        var cryptoMod = null;
        for (var i = 0; i < mods.length; i++) {
            if (mods[i].name === "libcrypto.so") {
                cryptoMod = mods[i];
                break;
            }
        }
        if (cryptoMod) {
            send("libcrypto base: " + cryptoMod.base);
            var exports = cryptoMod.enumerateExports();
            for (var j = 0; j < exports.length; j++) {
                var e = exports[j];
                if (e.name === "HMAC_Init_ex" || e.name === "HMAC_Update" || 
                    e.name === "HMAC_Final" || e.name === "MD5_Update") {
                    send("EXPORT: " + e.name + " @ " + e.address);
                }
            }
        }
    } catch(e) { send("enumModules: " + e); }
    
    send("DONE");
});
