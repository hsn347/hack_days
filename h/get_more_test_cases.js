// get_more_test_cases.js
// يحصل على test cases متعددة لـ httpSign(isUC=true)
// هذه ضرورية لكسر الخوارزمية

Java.perform(function() {
    var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
    var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
    var ctx = OneMTCore.getApplicationContext();
    var HashMap = Java.use('java.util.HashMap');
    
    function sign(json, isUC) {
        var m = HashMap.$new();
        SignUtil.httpSign(ctx, json, isUC, m);
        return m.get("sign");
    }

    // Test cases for isUC=true (to crack the algorithm)
    var inputs = [
        '{}',
        '{"a":"1"}',
        '{"b":"2"}',
        '{"abc":"xyz"}',
        '{"appid":"100002001"}',
        '{"timestamp":"1000000"}',
        '{"timestamp":"1000001"}',
        '{"sessionid":""}',
        '{"sign":"test"}',
        '1234567890',
        'hello world',
        '',
        'a',
        'aaaaaaaaaaaaaaaa',
    ];

    send("=== isUC=TRUE test cases ===");
    for (var i = 0; i < inputs.length; i++) {
        var s = sign(inputs[i], true);
        send("T|" + inputs[i] + "|" + s);
    }
    
    send("=== isUC=FALSE test cases (for comparison) ===");
    for (var i = 0; i < inputs.length; i++) {
        var s = sign(inputs[i], false);
        send("F|" + inputs[i] + "|" + s);
    }
    
    // Also get the current daemon result and any key material
    send("=== Key material ===");
    try {
        Java.choose('com.onemt.sdk.component.daemon.SDKDaemon', {
            onMatch: function(inst) {
                try {
                    var daemon = inst.cachedDaemonResult.value;
                    send("DAEMON=" + daemon);
                } catch(e) {}
                // All string fields
                try {
                    var fields = inst.class.getDeclaredFields();
                    for (var i = 0; i < fields.length; i++) {
                        fields[i].setAccessible(true);
                        var val = fields[i].get(inst);
                        if (val) send("FIELD_" + fields[i].getName() + "=" + val.toString().substring(0,100));
                    }
                } catch(e) {}
            },
            onComplete: function() {}
        });
    } catch(e) { send("err: " + e); }
    
    send("DONE");
});
