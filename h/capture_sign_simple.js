// capture_sign_simple.js
// طريقة بسيطة: نستدعي signWithAppKey بنص معروف ونرى النتيجة
Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    
    // 1) AppKey الخام
    var appKey = SignUtil.getOriginAppKey();
    send("appKey=" + appKey);
    
    // 2) اختبار signWithAppKey
    var test1 = SignUtil.signWithAppKey("hello");
    send("signWithAppKey('hello')=" + test1);
    
    var test2 = SignUtil.signWithAppKey("test123");
    send("signWithAppKey('test123')=" + test2);
    
    // 3) نختبر: هل هو md5(input + appKey)؟
    // appKey = d252596f076c9213dce69cdb39d488ea
    // md5("hello" + appKey) = ?
    send("DONE - compare results with md5 in Python");
});
