// استخراج salt values من Android resources
Java.perform(function() {
    var ctx = Java.use('com.onemt.sdk.core.OneMTCore').getApplicationContext();
    var res = ctx.getResources();
    
    // R.string.en_word_one = 0x7f11006b
    // R.string.en_word_two = 0x7f11006c (usually next)
    var w1 = res.getString(0x7f11006b);
    send("en_word_one = " + w1);
    
    var w2 = res.getString(0x7f11006c);
    send("en_word_two = " + w2);
    
    // Also try PwdUtil directly
    try {
        var PwdUtil = Java.use('com.onemt.sdk.user.base.util.PwdUtil');
        var test = PwdUtil.encryptSDKPwd("test123");
        send("encryptSDKPwd('test123') = " + test);
    } catch(e) {
        send("PwdUtil error: " + e);
    }
    
    // Also get AccountManager info
    try {
        var AM = Java.use('com.onemt.sdk.user.base.AccountManager').getInstance();
        send("userId = " + AM.getUserId());
        send("sessionId = " + AM.getSessionId());
    } catch(e) {
        send("AccountManager error: " + e);
    }
});
