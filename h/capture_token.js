/**
 * Capture login token - hooks at Lua level using lua_tolstring
 * Works on x64 emulator with Houdini ARM translation
 * Captures the exact strings passed to ldesencode (desencode in crypt library)
 */
'use strict';

// On x64 emulator, the Lua VM runs in the Java process
// We hook lua_tolstring to capture string values at Lua level

var luaModule = null;
var modules = Process.enumerateModules();
for (var i = 0; i < modules.length; i++) {
  var m = modules[i];
  if (m.name.indexOf('lua') !== -1 || m.name.indexOf('cocos') !== -1) {
    console.log('[+] Found module: ' + m.name + ' @ ' + m.base);
    luaModule = m;
  }
}

// Try to find lua_tolstring
var lua_tolstring = null;
if (luaModule) {
  lua_tolstring = luaModule.findExportByName('lua_tolstring');
  if (lua_tolstring) console.log('[+] lua_tolstring @ ' + lua_tolstring);
}

// Alternative: hook the desencode string passing via luaL_checkstring
// Find crypt module strings

// Simple approach: use Interceptor on write() but with error handling
var libc = null;
try { libc = Process.getModuleByName('libc.so'); } catch(e) {}

if (libc) {
  var writeSym = libc.findExportByName('write');
  if (writeSym) {
    Interceptor.attach(writeSym, {
      onEnter: function(args) {
        this._fd  = args[0].toInt32();
        this._len = args[2].toInt32();
        if (this._len > 0 && this._len < 2048) {
          try {
            this._data = args[1].readByteArray(Math.min(this._len, 600));
          } catch(e) { this._data = null; }
        }
      },
      onLeave: function() {
        if (!this._data) return;
        try {
          var bytes = new Uint8Array(this._data);
          // Filter: look for base64 characters (the token message is base64)
          // and check if it contains '@' separator
          var text = '';
          var hasAt = false;
          for (var i = 0; i < bytes.length; i++) {
            var b = bytes[i];
            if (b >= 32 && b < 127) {
              var c = String.fromCharCode(b);
              text += c;
              if (c === '@') hasAt = true;
            } else if (b === 10) {
              text += '\n';
            } else {
              text += '.';
            }
          }
          // Only print lines that look like login traffic
          // (base64 with @ separator, or short base64 lines ~12 chars)
          var lines = text.split('\n');
          for (var j = 0; j < lines.length; j++) {
            var line = lines[j].trim();
            if (line.length === 0) continue;
            // Challenge/key lines are ~12 base64 chars
            // Token line has multiple @-separated base64 segments  
            if (hasAt && line.length > 20) {
              console.log('[WRITE fd=' + this._fd + ' len=' + this._len + ']');
              console.log('  ' + line.substring(0, 500));
            } else if (line.length >= 10 && line.length <= 16 && /^[A-Za-z0-9+/]+=*$/.test(line)) {
              console.log('[WRITE fd=' + this._fd + '] ' + line);
            }
          }
        } catch(e) {}
      }
    });
    console.log('[+] write() hooked with safe byte reading');
  }
  
  var readSym = libc.findExportByName('read');
  if (readSym) {
    Interceptor.attach(readSym, {
      onEnter: function(args) {
        this._fd = args[0].toInt32();
        this._buf = args[1];
      },
      onLeave: function(retval) {
        var n = retval.toInt32();
        if (n <= 0 || n > 500) return;
        try {
          var data = this._buf.readByteArray(Math.min(n, 300));
          var bytes = new Uint8Array(data);
          var text = '';
          for (var i = 0; i < bytes.length; i++) {
            var b = bytes[i];
            if (b >= 32 && b < 127) text += String.fromCharCode(b);
            else if (b === 10) text += '\n';
            else text += '.';
          }
          var lines = text.split('\n');
          for (var j = 0; j < lines.length; j++) {
            var line = lines[j].trim();
            if (line.length >= 5) {
              console.log('[READ  fd=' + this._fd + ' len=' + n + '] ' + line.substring(0, 200));
            }
          }
        } catch(e) {}
      }
    });
    console.log('[+] read() hooked with safe byte reading');
  }
}

console.log('');
console.log('[*] Ready - login to the game now');
console.log('[*] All write/read traffic will be printed');
