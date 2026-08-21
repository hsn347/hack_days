Java.perform(function() {
    send("appId=" + Java.use('com.onemt.sdk.core.OneMTCore').getGameAppId());
    send("appKey=" + Java.use('com.onemt.sdk.core.OneMTCore').getGameAppKey());
    send("sdkVer=" + Java.use('com.onemt.sdk.core.OneMTCore').getSdkVersion());
});
