// sdk_email_login.js
// Frida script: تسجيل دخول بالبريد + كلمة المرور عبر SDK
// Args: recv message with {email, password}

Java.perform(function() {
    var AccountManager = Java.use('com.onemt.sdk.user.base.AccountManager');
    
    // أولاً: تحقق إذا فيه session حالي
    try {
        var am = AccountManager.getInstance();
        var uid = am.getUserId();
        var sid = am.getSessionId();
        if (sid && sid.length > 10) {
            send(JSON.stringify({
                status: "OK",
                userId: uid,
                sessionId: sid,
                source: "cached"
            }));
            return;
        }
    } catch(e) {}
    
    // Hook login success
    var LoginManager = Java.use('com.onemt.sdk.user.base.LoginManager');
    LoginManager.handleRemoteLoginSuccess.overload(
        'com.onemt.sdk.user.base.model.AccountInfo', 'boolean'
    ).implementation = function(info, silent) {
        this.handleRemoteLoginSuccess(info, silent);
        send(JSON.stringify({
            status: "OK",
            userId: info.getUserId(),
            sessionId: info.getSessionId(),
            source: "fresh_login"
        }));
    };
    
    // Hook error
    var ErrorHandler = Java.use('com.onemt.sdk.user.base.ErrorHandler');
    
    send(JSON.stringify({status: "HOOKS_READY"}));
});
