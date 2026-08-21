// تسجيل دخول مباشر عبر SDK وإرجاع sessionId + userId
// يُستخدم من بايثون عبر frida-tools

Java.perform(function() {
    var email = "EMAIL_PLACEHOLDER";
    var password = "PASSWORD_PLACEHOLDER";
    
    var Activity = Java.use('android.app.Activity');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var EmailApiManager = Java.use('com.onemt.sdk.user.base.EmailApiManager');
    var AccountManager = Java.use('com.onemt.sdk.user.base.AccountManager');
    var PassportManager = Java.use('com.onemt.sdk.user.base.PassportManager');
    var PwdUtil = Java.use('com.onemt.sdk.user.base.util.PwdUtil');
    
    // Hook the login success callback to capture sessionId
    var LoginManager = Java.use('com.onemt.sdk.user.base.LoginManager');
    LoginManager.handleRemoteLoginSuccess.overload('com.onemt.sdk.user.base.model.AccountInfo', 'boolean').implementation = function(accountInfo, silent) {
        var userId = accountInfo.getUserId();
        var sessionId = accountInfo.getSessionId();
        var name = accountInfo.getName();
        send(JSON.stringify({
            status: "LOGIN_SUCCESS",
            userId: userId,
            sessionId: sessionId,
            name: name
        }));
        return this.handleRemoteLoginSuccess(accountInfo, silent);
    };
    
    // Also hook error
    var UserApiCallbackWrapper = Java.use('com.onemt.sdk.user.base.UserApiCallbackWrapper');
    UserApiCallbackWrapper.onUserLoginFail.implementation = function(code, msg) {
        send(JSON.stringify({
            status: "LOGIN_FAILED",
            code: code,
            message: msg
        }));
        return this.onUserLoginFail(code, msg);
    };
    
    // Get current session (maybe already logged in)
    try {
        var am = AccountManager.getInstance();
        var currentUserId = am.getUserId();
        var currentSession = am.getSessionId();
        if (currentSession && currentSession.length > 10) {
            send(JSON.stringify({
                status: "ALREADY_LOGGED_IN",
                userId: currentUserId,
                sessionId: currentSession
            }));
        }
    } catch(e) {
        send(JSON.stringify({status: "INFO", message: "Not logged in yet: " + e}));
    }
    
    send(JSON.stringify({status: "READY", message: "Hooks installed. Waiting for login..."}));
});
