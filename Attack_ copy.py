"""
bot_engine.py
Python = المنطق + فك الضغط + عرض النتائج
Frida JS = بناء الحزمة + ارسالها + التقاط الرد (نفس طريقة simple_cmd.js)
"""
import frida, sys, json, struct, zlib, time, os, threading

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

XOR_KEY = bytes([79,83,120,72,80,46,33,45,119,100,63,39,108,97,111,53])

def xor(data):
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ XOR_KEY[i % len(XOR_KEY)]
    return bytes(out)

def decompress(raw):
    for w in (-15, 15+32, 15):
        try: return zlib.decompress(raw, w)
        except: pass
    return raw

def decode_pkt(pkt):
    if len(pkt) < 5: return None
    for trim in (5, 4):
        raw = pkt[:-trim] if trim <= len(pkt) else pkt
        for attempt in (raw, decompress(raw)):
            try:
                d = json.loads(xor(attempt))
                if isinstance(d, dict) and ('cmd' in d or 'subcmd' in d):
                    c = d.get('cmd','')
                    if c.startswith('onemt_'): d['cmd'] = c[6:]
                    return d
            except: pass
    return None

# --- Frida JS ---
# يعمل بنفس طريقة simple_cmd.js تماما
# يستقبل الامر كنص JSON من Python عبر recv
FRIDA_JS = r"""
var XOR_KEY = "OSxHP.!-wd?'lao5";
var _fd = -1, _session = 0, _started = false;
var libc = Process.getModuleByName('libc.so');

function xorEncrypt(text, key) {
    var r = []; var j = 0;
    for (var i = 0; i < text.length; i++) {
        r.push(text.charCodeAt(i) ^ key.charCodeAt(j));
        j = (j + 1) % key.length;
    }
    return r;
}

function buildPacket(cmd, subcmd, data) {
    var msg = JSON.stringify({cmd: "onemt_" + cmd, subcmd: String(subcmd), data: data});
    var enc = xorEncrypt(msg, XOR_KEY);
    var totalLen = enc.length + 4;
    var pkt = [(totalLen >> 8) & 0xFF, totalLen & 0xFF];
    pkt = pkt.concat(enc);
    pkt.push((_session >> 24) & 0xFF, (_session >> 16) & 0xFF, (_session >> 8) & 0xFF, _session & 0xFF);
    return pkt;
}

function writePkt(pkt) {
    var buf = Memory.alloc(pkt.length);
    for (var i = 0; i < pkt.length; i++) buf.add(i).writeU8(pkt[i]);
    var writeFn = new NativeFunction(libc.findExportByName('write'), 'int', ['int','pointer','int']);
    var r = writeFn(_fd, buf, pkt.length);
    if (r <= 0) {
        var sendFn = new NativeFunction(libc.findExportByName('send'), 'int', ['int','pointer','int','int']);
        r = sendFn(_fd, buf, pkt.length, 0);
    }
    return r;
}

// اكتشاف الاتصال
['write','send'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), { onEnter: function(a) {
        if (_started) return;
        var len=a[2].toInt32(), fd=a[0].toInt32();
        if (len<10||len>2000||fd<=3) return;
        try {
            if (a[1].add(2).readU8()===0x34) {
                var p=a[1].add(len-4);
                _session=((p.readU8()<<24)|(p.add(1).readU8()<<16)|(p.add(2).readU8()<<8)|p.add(3).readU8())>>>0;
                _fd=fd; _started=true;
                send({type:'ready', fd:fd, session:_session});
            }
        } catch(e){}
    }});
});

// التقاط الردود وارسالها لـ Python
['read','recv'].forEach(function(fn) {
    Interceptor.attach(libc.findExportByName(fn), {
        onEnter: function(a) { this.buf=a[1]; this.fd=a[0].toInt32(); },
        onLeave: function(r) {
            var n=r.toInt32();
            if (n<=0 || this.fd !== _fd) return;
            try {
                send({type:'data', fd:this.fd}, this.buf.readByteArray(n));
            } catch(e){}
        }
    });
});

// استقبال امر من Python
function handleCmd(msg) {
    if (!_started) {
        send({type:'err', msg:'not_ready'});
        recv('cmd', handleCmd);
        return;
    }
    try {
        _session++;
        var pkt = buildPacket(msg.cmd, msg.subcmd, msg.data || {});
        var r = writePkt(pkt);
        send({type:'sent', bytes:r, cmd:msg.cmd, subcmd:msg.subcmd});
    } catch(e) {
        send({type:'err', msg:e.message});
    }
    recv('cmd', handleCmd);
}
recv('cmd', handleCmd);
"""

class BotEngine:
    def __init__(self):
        self._ready = False
        self._fd = -1
        self._script = None
        self._recv_buf = b''
        self._pending = {}
        self._lock = threading.Lock()
        self.collected_map_objects = []

    def _on_message(self, msg, data):
        if msg['type'] != 'send': return
        p = msg.get('payload', {})
        t = p.get('type','')

        if t == 'ready':
            self._fd = p['fd']
            self._ready = True
            print(f"[+] fd={self._fd} session={p['session']}")

        elif t == 'data' and data:
            self._recv_buf += bytes(data)
            self._try_parse()

        elif t == 'sent':
            pass  # نجاح الارسال

        elif t == 'err':
            print(f"[!] Frida: {p.get('msg','?')}")

    def _try_parse(self):
        buf = self._recv_buf
        while len(buf) >= 2:
            sz = buf[0]*256 + buf[1]
            head = 2
            if sz == 0xFFFF:
                if len(buf) < 5: break
                sz = buf[2]*65536 + buf[3]*256 + buf[4]
                head = 5
            if sz < 4 or sz > 200000: 
                buf = buf[1:]  # skip bad byte
                continue
            if len(buf) < head + sz: break
            pkt = buf[head:head+sz]
            buf = buf[head+sz:]
            
            d = decode_pkt(pkt)
            if d:
                # التقاط جميع كائنات الخريطة من إشعار NOTIFY_MAP_SYNC
                cmd_str = str(d.get('cmd', ''))
                notify_id = str(d.get('data', {}).get('notifyID', ''))
                
                if '1009' in cmd_str or notify_id == 'NOTIFY_MAP_SYNC':
                    notify_data = d.get('data', {}).get('notifyData', [])
                    for nd in notify_data:
                        if isinstance(nd, dict) and str(nd.get('msgType', '')) == '1':
                            map_data = nd.get('data', {})
                            if isinstance(map_data, dict):
                                for kid, pieces in map_data.items():
                                    if isinstance(pieces, dict):
                                        for piece_id, objs in pieces.items():
                                            if isinstance(objs, list):
                                                self.collected_map_objects.extend(objs)
                            elif isinstance(map_data, list):
                                self.collected_map_objects.extend(map_data)

                sub = str(d.get('subcmd',''))
                with self._lock:
                    if sub in self._pending:
                        self._pending[sub]['result'] = d
                        self._pending[sub]['done'] = True
        self._recv_buf = buf

    def connect(self):
        device = frida.get_device_manager().get_device("emulator-5554")
        session = None
        for name in ["Empire", "and.onemt.boe.tr"]:
            try:
                session = device.attach(name)
                print(f"[+] {name}")
                break
            except: pass
        if not session:
            print("[!] game not running"); sys.exit(1)
        self._script = session.create_script(FRIDA_JS)
        self._script.on('message', self._on_message)
        self._script.load()

    def wait_ready(self, timeout=30):
        print("[*] tap screen...")
        t = time.time()
        while not self._ready and time.time()-t < timeout:
            time.sleep(0.1)
        return self._ready

    def query(self, cmd, subcmd, data=None, timeout=15):
        if not self._ready: return None
        sub = str(subcmd)
        slot = {'result': None, 'done': False}
        with self._lock:
            self._pending[sub] = slot
        
        self._script.post({'type': 'cmd', 'cmd': str(cmd), 'subcmd': sub, 'data': data or {}})
        print(f"  >> {cmd}/{subcmd}")

        t = time.time()
        while not slot['done'] and time.time()-t < timeout:
            time.sleep(0.05)
        
        with self._lock:
            self._pending.pop(sub, None)
        
        if not slot['done']:
            print(f"  !! timeout {cmd}/{subcmd}")
            return None
        print(f"  << {cmd}/{subcmd} OK")
        return slot['result']

    def get_map_chunk(self, kid, x, y, wait_time=2.5):
        """طلب وتفريغ كافة كائنات الخريطة (قلاع، موارد، وحوش، مباني) حول إحداثيات محددة"""
        self.collected_map_objects = []
        # تفعيل وضع الخريطة الخارجية
        self.query('1006', '47', {"switchFlag": 2})
        # مزامنة قطع الخريطة
        self.query('1006', '1000', {"centerKid": int(kid), "centerX": int(x), "centerY": int(y)})
        time.sleep(wait_time)
        return self.collected_map_objects

    def send_cmd(self, cmd, subcmd, data=None):
        if not self._ready: return
        self._script.post({'type': 'cmd', 'cmd': str(cmd), 'subcmd': str(subcmd), 'data': data or {}})


# ========================================
#  EXCLUDE HISTORY (JSON)
# ========================================

HISTORY_FILE = "exclude_history.json"

def get_exclude_dict(uid):
    """جلب الأهداف المستبعدة لهذا الحساب بصيغة {'id': True}"""
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            arr = data.get(str(uid), [])
            return {target_id: True for target_id in arr}
    except Exception as e:
        return {}

def add_to_exclude_history(uid, target_id):
    """إضافة الهدف الجديد لمصفوفة الحساب في ملف json (بحد أقصى 10 مع حذف الأقدم)"""
    data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {}
    
    uid_str = str(uid)
    if uid_str not in data:
        data[uid_str] = []
    
    arr = data[uid_str]
    if target_id not in arr:
        arr.append(target_id)
    
    # إذا تجاوز 10 عناصر، احذف الأقدم (من بداية المصفوفة)
    while len(arr) > 10:
        arr.pop(0)
    
    data[uid_str] = arr
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] خطأ في حفظ ملف exclude_history: {e}")


# ========================================
#  BOT LOGIC
# ========================================

def run_bot(bot):
    # 1. جلب uid والمملكة وإحداثيات القلعة
    r0 = bot.query('1002', '9', {})
    MY_UID = r0['pid'] if r0 else 0

    r_castle = bot.query('1006', '25', {"uid": MY_UID})
    cx = r_castle['retData']['x'] if r_castle and 'retData' in r_castle else 289
    cy = r_castle['retData']['y'] if r_castle and 'retData' in r_castle else 485

    r3 = bot.query('1002', '7', {"uid": MY_UID})
    KID = r3['data']['base']['partition'] if r3 and 'data' in r3 and 'base' in r3['data'] else 259

    print(f"\n[+] جارٍ مسح وتفريغ كل كائنات الخريطة للمملكة {KID} حول ({cx}, {cy})...")

    # 2. تفريغ جميع الكائنات دفعة واحدة من مربعات الخريطة
    all_objs = bot.get_map_chunk(KID, cx, cy, wait_time=2.0)

    # 3. فرز وفك تشفير الكائنات - بناءً على مفاتيح البيانات الفعلية من السيرفر
    rebels = []       # المتمردين - مفتاح 'bandit'
    strongholds = []  # المعاقل / judian - مفتاح 'judian' أو 'stronghold'
    bosses = []       # الغزاة / الزعماء - مفتاح 'boss' أو 'beast'
    monsters = []     # الوحوش العادية - مفتاح 'npc'
    castles = []      # قلاع اللاعبين - مفتاح 'castle'
    alliance_b = []   # مباني التحالف - مفتاح 'build'
    unknown = []      # كائنات مجهولة لعرضها للتحليل

    for obj in all_objs:
        oid = obj.get('id', '')
        parts = oid.split('-')
        if len(parts) < 5: continue

        ox = int(parts[0])
        oy = int(parts[1])
        otype = int(parts[2])

        dist = round(((ox - cx)**2 + (oy - cy)**2)**0.5, 1)

        item_info = {'id': oid, 'x': ox, 'y': oy, 'dist': dist, 'type': otype, 'raw': obj}

        if 'bandit' in obj:
            bdata = obj.get('bandit', {})
            item_info['level'] = bdata.get('level', int(parts[4]) % 100)
            rebels.append(item_info)

        elif 'judian' in obj or 'stronghold' in obj:
            jdata = obj.get('judian', obj.get('stronghold', {}))
            item_info['level'] = jdata.get('level', int(parts[4]) % 100)
            strongholds.append(item_info)

        elif 'boss' in obj:
            bdata = obj.get('boss', {})
            item_info['level'] = bdata.get('level', int(parts[4]) % 100)
            item_info['name'] = bdata.get('name', '')
            bosses.append(item_info)

        elif 'beast' in obj:
            bdata = obj.get('beast', {})
            item_info['level'] = bdata.get('level', int(parts[4]) % 100)
            bosses.append(item_info)

        elif 'npc' in obj:
            ndata = obj.get('npc', {})
            item_info['level'] = ndata.get('level', int(parts[4]) % 100)
            monsters.append(item_info)

        elif 'castle' in obj:
            cdata = obj.get('castle', {})
            item_info['name'] = cdata.get('nickName', '???')
            item_info['uid'] = cdata.get('uid', 0)
            item_info['level'] = cdata.get('level', 0)
            item_info['alliance'] = cdata.get('leagueAbbrName', '')
            castles.append(item_info)

        elif 'build' in obj:
            bdata = obj.get('build', {})
            item_info['alliance'] = bdata.get('leagueName', bdata.get('leagueAbbrName', ''))
            item_info['hp'] = bdata.get('hp', 0)
            item_info['level'] = bdata.get('level', 0)
            alliance_b.append(item_info)

        elif 'resource' not in obj:
            # كائن مجهول - نطبعه للتحليل
            keys = [k for k in obj.keys() if k != 'id']
            item_info['keys'] = keys
            unknown.append(item_info)

    # ترتيب القوائم
    rebels.sort(key=lambda k: k['dist'])
    strongholds.sort(key=lambda k: k['dist'])
    bosses.sort(key=lambda k: k['dist'])
    monsters.sort(key=lambda k: k['dist'])
    castles.sort(key=lambda k: k['dist'])
    alliance_b.sort(key=lambda k: k['dist'])

    print(f"\n=================================================================")
    print(f" 🎯 تقرير الأهداف (مرتبة حسب الأقرب):")
    print(f"=================================================================")

    # 1. المتمردين
    print(f"\n🚩 معسكرات المتمردين ({len(rebels)}):")
    if rebels:
        for r in rebels:
            print(f"   ⚔️  ({r['x']}, {r['y']}) مسافة: {r['dist']} | ID: {r['id']}")
    else:
        print("   (لا يوجد)")

    # 2. المعاقل
    print(f"\n🏰 معاقل / Strongholds ({len(strongholds)}):")
    if strongholds:
        for s in strongholds:
            print(f"   🛡️  ({s['x']}, {s['y']}) مسافة: {s['dist']} | ID: {s['id']}")
    else:
        print("   (لا يوجد)")

    # 3. الغزاة والزعماء
    print(f"\n👑 الغزاة وزعماء العالم ({len(bosses)}):")
    if bosses:
        for b in bosses:
            nm = f"({b.get('name','')})" if b.get('name') else ''
            print(f"   🔥 {nm} ({b['x']}, {b['y']}) مسافة: {b['dist']} | ID: {b['id']}")
    else:
        print("   (لا يوجد غزاة نشطين حالياً)")

    # 4. قلاع اللاعبين
    print(f"\n🏯 قلاع اللاعبين القريبة ({len(castles)}):")
    if castles:
        for c in castles:
            ally = f"[{c['alliance']}]" if c['alliance'] else ""
            print(f"   👤 {ally} {c['name']} (لفل {c['level']}) | ({c['x']}, {c['y']}) مسافة: {c['dist']} | UID: {c['uid']}")
    else:
        print("   (لا يوجد)")

    # 5. مباني التحالف
    print(f"\n🏛️  مباني التحالف ({len(alliance_b)}):")
    for b in alliance_b:
        print(f"   🔵 [{b.get('alliance','')}] ({b['x']}, {b['y']}) HP:{b.get('hp',0)} مسافة: {b['dist']} type:{b['type']} | ID: {b['id']}")

    # 6. الوحوش مرتبة حسب المستوى
    print(f"\n👾 الوحوش (إجمالي: {len(monsters)}) مجمّعة حسب المستوى:")
    lv_groups = {}
    for m in monsters:
        lv = m.get('level', 0)
        lv_groups.setdefault(lv, []).append(m)
    for lv in sorted(lv_groups.keys(), reverse=True):
        sample = lv_groups[lv][0]
        count = len(lv_groups[lv])
        print(f"   👾 لفل {lv:2d} ({count:3d} وحش) -> الأقرب: ({sample['x']}, {sample['y']}) مسافة: {sample['dist']}")

    # 7. كائنات مجهولة - لمعرفة نوعها الحقيقي
    if unknown:
        print(f"\n❓ كائنات مجهولة النوع ({len(unknown)}) - لتحليلها:")
        for u in unknown[:10]:  # أول 10 فقط
            print(f"   type={u['type']} keys={u['keys']} | ID: {u['id']}")
            print(f"   البيانات: {json.dumps({k:v for k,v in u['raw'].items() if k != 'id'}, ensure_ascii=False)}")

    print(f"\n=================================================================\n")


if __name__ == '__main__':
    bot = BotEngine()
    bot.connect()
    if not bot.wait_ready():
        print("[!] failed"); sys.exit(1)
    
    print("[+] ready!\n")
    run_bot(bot)
    
    print("\n[*] done. Ctrl+C to exit")
    try: sys.stdin.read()
    except KeyboardInterrupt: pass
