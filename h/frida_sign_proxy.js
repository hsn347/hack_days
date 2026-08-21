// frida_sign_proxy.js
// يوقّع طلب login ويشفّره ويعطيك النتيجة الجاهزة للإرسال
// يُستخدم مرة واحدة فقط عند الحاجة لتجديد الـ session

Java.perform(function() {
    var SdkRequestBodyFactory = Java.use('com.onemt.sdk.core.http.SdkRequestBodyFactory');
    var SdkHttpUtil = Java.use('com.onemt.sdk.core.http.SdkHttpUtil');
    var OneMTDaemonUtil = Java.use('com.onemt.sdk.component.daemon.OneMTDaemonUtil');
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var OneMTIdentifierV2 = Java.use('com.onemt.sdk.identifier.OneMTIdentifierV2');
    var SDKConfigManager = Java.use('com.onemt.sdk.core.config.SDKConfigManager');
    var AccountProvider = Java.use('com.onemt.sdk.core.provider.AccountProvider');
    var PwdUtil = Java.use('com.onemt.sdk.user.base.util.PwdUtil');
    var HashMap = Java.use('java.util.HashMap');
    var DateTimeUtil = Java.use('com.onemt.sdk.component.util.DateTimeUtil');
    var AppUtil = Java.use('com.onemt.sdk.component.util.AppUtil');

    var email = "%%EMAIL%%";
    var password = "%%PASSWORD%%";

    // Encrypt password via SDK
    var encPwd = PwdUtil.encryptSDKPwd(password);
    send(JSON.stringify({type: "pwd", value: encPwd}));

    // Build business params
    var bizMap = HashMap.$new();
    bizMap.put("name", email);
    bizMap.put("password", encPwd);
    bizMap.put("identifytype", "email");

    // Build the full request body using SDK's own factory
    var reqBody = SdkRequestBodyFactory.createRequestBodyForUC(
        Java.cast(bizMap, Java.use('java.util.Map'))
    );

    // Extract the body content
    var buffer = Java.use('com.onemt.sdk.launch.base.at').$new();
    reqBody.writeTo(buffer);
    var bodyStr = buffer.readUtf8();
    send(JSON.stringify({type: "body_before_encrypt", value: bodyStr}));

    // Now encrypt the body
    var encrypted = OneMTDaemonUtil.encryptPacketForUC(bodyStr);
    send(JSON.stringify({type: "encrypted_body", value: encrypted}));

    // Also get app ID for header
    send(JSON.stringify({type: "appid", value: OneMTCore.getGameAppId()}));

    send(JSON.stringify({type: "DONE"}));
});
