// hook_gate_native.js
// يعترض النيتف send/recv على socket البورت 4000 (gate server)
// يطبع كل ما يرسله وما يستقبله اللعبة

// البورت المستهدف
var GATE_PORT = 4000;

// Hook native send() function
Interceptor.attach(Module.getExportByName(null, "send"), {
    onEnter: function(args) {
        var fd  = args[0].toInt32();
        var buf = args[1];
        var len = args[2].toInt32();
        
        // تحقق إذا هذا الـ socket متصل بالـ gate port
        try {
            var sockName = Socket.peerAddress(fd);
            if (sockName && sockName.port == GATE_PORT) {
                var data = Memory.readByteArray(buf, Math.min(len, 512));
                var hex  = Array.from(new Uint8Array(data))
                               .map(b => b.toString(16).padStart(2,'0')).join('');
                send("GAME->GATE(" + len + "): " + hex);
            }
        } catch(e) {}
    }
});

// Hook native recv() function
Interceptor.attach(Module.getExportByName(null, "recv"), {
    onLeave: function(retval) {
        var fd  = this.context.x0 ? this.context.x0.toInt32() : -1;
        if (fd < 0) return;
        var len = retval.toInt32();
        if (len <= 0) return;
        
        try {
            var sockName = Socket.peerAddress(fd);
            if (sockName && sockName.port == GATE_PORT) {
                var buf = this.context.x1;
                var data = Memory.readByteArray(buf, Math.min(len, 512));
                var hex  = Array.from(new Uint8Array(data))
                               .map(b => b.toString(16).padStart(2,'0')).join('');
                send("GATE->GAME(" + len + "): " + hex);
            }
        } catch(e) {}
    },
    onEnter: function(args) {
        // Save args for onLeave
        this.context = {
            x0: args[0],
            x1: args[1],
        };
    }
});

send("[*] Native gate hooks ready - play the game now!");
send("[*] Port " + GATE_PORT + " traffic will be captured");
