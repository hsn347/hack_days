import frida, time, sys

device = frida.get_usb_device()
# find and.onemt pid from ps
pids = [p.pid for p in device.enumerate_processes() if 'and.onemt.boe' in p.name]
if not pids:
    # fallback to 5826 or find via adb
    import subprocess
    out = subprocess.check_output('adb shell "pidof and.onemt.boe.tr"', shell=True).decode().strip()
    target_pid = int(out)
else:
    target_pid = pids[0]

print('Target PID:', target_pid)
session = device.attach(target_pid)

js = """
Java.perform(function() {
    try {
        var SignUtil = Java.use('com.onemt.sdk.component.cryptoutil.SignUtil');
        var PwdUtil = Java.use('com.onemt.sdk.user.base.util.PwdUtil');
        var OneMTCore = Java.use('com.onemt.sdk.core.OneMTCore');
        var AccountManager = Java.use('com.onemt.sdk.user.base.AccountManager');
        
        var appKey = SignUtil.getOriginAppKey();
        var testPlain = '{"name":"test@gmail.com","password":"abc"}';
        var testEnc = SignUtil.encryptPacketForUC(testPlain);
        var testDec = SignUtil.decryptPacketForUC(testEnc);
        var pwdEnc = PwdUtil.encryptSDKPwd("123456");
        var sdkVer = OneMTCore.getSdkVersion();
        var appId = OneMTCore.getGameAppId();

        send({
            appKey: appKey,
            testPlain: testPlain,
            testEnc: testEnc,
            testDec: testDec,
            pwdEnc: pwdEnc,
            sdkVer: sdkVer,
            appId: appId
        });
    } catch(e) {
        send({error: e.toString()});
    }
});
"""

def on_msg(m, d):
    if m['type'] == 'send':
        print('FRIDA_RESULT:', m['payload'])
    else:
        print('FRIDA_MSG:', m)

script = session.create_script(js)
script.on('message', on_msg)
script.load()
time.sleep(2)
session.detach()
