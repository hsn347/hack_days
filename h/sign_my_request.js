// sign_my_request.js
// يوقّع طلب login كامل ويعطيني الـ sign + encrypted body
Java.perform(function() {
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var OneMTIdentifierV2 = Java.use('com.onemt.sdk.identifier.OneMTIdentifierV2');
    var SDKConfigManager = Java.use('com.onemt.sdk.core.config.SDKConfigManager');
    var AccountProvider = Java.use('com.onemt.sdk.core.provider.AccountProvider');
    var HashMap = Java.use('java.util.HashMap');
    
    // Get real device values
    var sdId = OneMTIdentifierV2.getInstance().getSdId();
    var deviceId = OneMTIdentifierV2.getInstance().getDeviceId();
    var channel = SDKConfigManager.getChannel();
    var sdkVer = OneMTCore.getSdkVersion();
    var appId = OneMTCore.getGameAppId();
    var lang = OneMTCore.getGameLanguageStr();
    var pkg = "and.onemt.boe.tr";
    
    send("sdId=" + sdId);
    send("deviceId=" + deviceId);
    send("channel=" + channel);
    send("sdkVer=" + sdkVer);
    send("appId=" + appId);
    send("lang=" + lang);
    
    // Now find the .so that has httpSign
    var mods = Process.enumerateModules();
    for (var i = 0; i < mods.length; i++) {
        if (mods[i].path.indexOf("and.onemt") >= 0 && mods[i].name.indexOf(".so") >= 0) {
            send("SO: " + mods[i].name + " @ " + mods[i].path);
        }
    }
    
    // Find .so files in app lib dir
    var File = Java.use('java.io.File');
    var libDir = new File("/data/app/and.onemt.boe.tr-09iLei-IzaRnfSZWYlCajw==/lib/arm64");
    if (libDir.exists()) {
        var files = libDir.listFiles();
        if (files) {
            for (var i = 0; i < files.length; i++) {
                send("LIB: " + files[i].getName());
            }
        }
    }
    
    // Also check split APK libs
    var libDir2 = new File("/data/app/and.onemt.boe.tr-09iLei-IzaRnfSZWYlCajw==/split_InstallPack.apk");
    send("InstallPack exists: " + libDir2.exists());
    
    send("DONE");
});
