// find_login_classes.js
Java.perform(function() {
    // Enumerate all loaded classes containing "login" or "account" or "user"
    Java.enumerateLoadedClasses({
        onMatch: function(name) {
            var low = name.toLowerCase();
            if ((low.indexOf('login') >= 0 || low.indexOf('account') >= 0 || 
                 low.indexOf('register') >= 0) && low.indexOf('onemt') >= 0) {
                send("CLASS: " + name);
            }
        },
        onComplete: function() { send("DONE"); }
    });
});
