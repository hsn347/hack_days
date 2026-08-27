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
#  SMART HERO SELECTOR - اختيار الأبطال الذكي
#  يقلد نظام autoSelectHeros في اللعبة
# ========================================

class SmartHeroSelector:
    """
    يقلد خوارزمية اللعبة في اختيار الأبطال التلقائي:
    1. يجمع كل الأبطال من جميع التشكيلات (1005/1)
    2. يصنفهم: قتال (5501xxx) / تطوير وجمع (5502xxx)
    3. يستبعد المشغولين في مسيرات
    4. يختار الأنسب حسب نوع الهدف (مثل gMapExpeditionType في اللعبة)
    """

    # تصنيف الأبطال حسب رقم ID:
    # 5501xxx = أبطال حرب وقتال (War Heroes)
    # 5502xxx = أبطال تطوير وجمع ودعم (Development Heroes)

    def __init__(self, bot):
        self.bot = bot
        self.all_heroes = {}       # {hero_id: {"type": "war"|"dev", "formation": int}}
        self.busy_heroes = {}      # {hero_id: وقت_العودة}
        self.formation_data = {}   # {formation_id: {"army": {}, "pets": [], "runes": []}}

    def load(self):
        """جلب كل الأبطال من جميع التشكيلات دفعة واحدة عبر 1005/1"""
        r = self.bot.query('1005', '1', {})
        if not r or 'data' not in r:
            print(" [!] فشل جلب بيانات التشكيلات")
            return False

        data = r['data']
        compile_heros = data.get('compileHeros', {})
        compile_army = data.get('compileArmy', {})
        compile_pets = data.get('compilePets', {})
        compile_runes = data.get('compileRunePages', {})

        for form_id_str, heroes in compile_heros.items():
            if not isinstance(heroes, list) or len(heroes) == 0:
                continue
            form_id = int(form_id_str)

            # حفظ بيانات كل تشكيلة (جيش + حيوان + رون)
            army_data = compile_army.get(form_id_str, {})
            if isinstance(army_data, dict):
                self.formation_data[form_id] = {
                    "army": army_data,
                    "pets": compile_pets.get(form_id_str, []),
                    "runes": compile_runes.get(form_id_str, []),
                    "heroes": heroes
                }

            # تصنيف كل بطل
            for hid in heroes:
                hero_type = "dev" if str(hid).startswith("5502") else "war"
                self.all_heroes[hid] = {
                    "type": hero_type,
                    "formation": form_id
                }

        # طباعة تقرير
        dev_list = [h for h, i in self.all_heroes.items() if i['type'] == 'dev']
        war_list = [h for h, i in self.all_heroes.items() if i['type'] == 'war']
        print(f"\n ========================================")
        print(f" 🦸 إجمالي أبطال الحساب: {len(self.all_heroes)}")
        print(f"   ⚔️  أبطال قتال ({len(war_list)}): {war_list}")
        print(f"   🌾 أبطال تطوير/جمع ({len(dev_list)}): {dev_list}")
        print(f"   📋 تشكيلات محملة: {list(self.formation_data.keys())}")
        print(f" ========================================\n")
        return True

    def _classify_target(self, map_type):
        """
        تحديد نوع الأبطال المطلوبين حسب نوع الهدف:
        مثل gMapExpeditionType في اللعبة
        """
        if map_type == 5:    # موارد (خشب/طعام/حديد/ميثريل/ذهب)
            return "dev"     # أبطال الجمع (مهارات جمع سريع + حمولة)
        elif map_type == 6:  # غزاة (Invaders)
            return "dev"     # أبطال التطوير (مهارات سرعة المسيرة)
        elif map_type == 35: # متمردين (Rebels)
            return "dev"     # أبطال التطوير (سرعة المسيرة)
        elif map_type == 7:  # أطلال (Ruins)
            return "war"     # أبطال الحرب
        elif map_type == 26: # معقل (Stronghold)
            return "war"     # أبطال الحرب
        else:
            return "war"     # افتراضي: أبطال الحرب

    def select(self, map_type, count=2):
        """
        اختيار أفضل الأبطال المتاحين حسب نوع الهدف:
        1. ينظف قائمة المشغولين المنتهية مدتهم
        2. يفلتر الأبطال المتاحين
        3. يرتب: الأنسب لنوع الهدف أولاً
        4. يأخذ أول count أبطال
        """
        now = time.time()

        # تنظيف المشغولين الذين عادوا للقلعة
        for hid in list(self.busy_heroes):
            if now >= self.busy_heroes[hid]:
                del self.busy_heroes[hid]

        # تصنيف الهدف
        preferred_type = self._classify_target(map_type)

        # فصل الأبطال المتاحين حسب النوع
        available_preferred = []  # النوع المطلوب أولاً
        available_fallback = []   # النوع الاحتياطي

        for hid, info in self.all_heroes.items():
            if hid in self.busy_heroes:
                continue  # مشغول، تخطيه
            if info['type'] == preferred_type:
                available_preferred.append(hid)
            else:
                available_fallback.append(hid)

        # دمج: النوع المفضل أولاً ثم الاحتياط
        priority_list = available_preferred + available_fallback
        chosen = priority_list[:count]

        # طباعة القرار
        if not chosen:
            print(f" ❌ لا يوجد أبطال متاحين! كل الأبطال مشغولين")
        elif all(self.all_heroes[h]['type'] == preferred_type for h in chosen):
            type_name = "تطوير/جمع 🌾" if preferred_type == "dev" else "قتال ⚔️"
            print(f" ✅ أبطال {type_name} متاحين: {chosen}")
        else:
            print(f" 🔄 تبديل تلقائي! بعض أبطال النوع المطلوب مشغولين، سيتم إرسال: {chosen}")

        return chosen

    def get_formation_for_heroes(self, heroes):
        """
        يجلب بيانات التشكيلة (جيش + حيوان + رون) المناسبة للأبطال المختارين.
        يأخذ التشكيلة التي ينتمي لها أول بطل.
        """
        if not heroes:
            return None
        first_hero = heroes[0]
        info = self.all_heroes.get(first_hero, {})
        form_id = info.get('formation', 1)
        return self.formation_data.get(form_id, None)

    def mark_busy(self, heroes, duration_seconds=120):
        """تسجيل الأبطال المرسلين كمشغولين لمدة المسير المتوقعة"""
        free_at = time.time() + duration_seconds
        for hid in heroes:
            self.busy_heroes[hid] = free_at
        print(f" ⏱️ الأبطال {heroes} مشغولون لـ {duration_seconds} ثانية")


# ========================================
#  BOT LOGIC
# ========================================

def run_bot(bot):
    type_R = 4       # نوع المورد الفرعي (2=حديد، 3=خشب، 4=طعام، 5=ذهب)
    map_type = 5     # نوع الهدف (5=موارد، 6=غزاة، 7=أطلال، 26=معقل، 35=متمردين)

    # === 1. جلب UID ===
    r0 = bot.query('1002', '9', {})
    if not r0:
        print("[!] فشل جلب UID اللاعب"); return
    MY_UID = r0['pid']
    print(f" city id = {MY_UID}")

    # === 2. معلومات القلعة ===
    r = bot.query('1006', '25', {"uid": MY_UID})
    if not r or 'retData' not in r:
        print("[!] فشل جلب معلومات القلعة"); return
    print(f" castle info 😺😺😺 = {json.dumps(r, ensure_ascii=False, indent=2)}")
    my_x, my_y = r['retData']['x'], r['retData']['y']

    # === 3. تحميل نظام الأبطال الذكي (مرة واحدة) ===
    hero_selector = SmartHeroSelector(bot)
    if not hero_selector.load():
        print("[!] فشل تحميل الأبطال"); return

    # === 4. الأهداف المستبعدة ===
    exclude_map = get_exclude_dict(MY_UID)
    if exclude_map:
        print(f" 📋 أهداف مستبعدة ({len(exclude_map)}/10): {list(exclude_map.keys())}")

    # === 5. البحث عن هدف قريب ===
    r2 = bot.query('2011', '3', {
        "mapType": map_type, "num": 1, "subType": type_R,
        "y": my_y, "x": my_x,
        "exclude": exclude_map,
        "minLv": 5, "maxLv": 6, "range": 100
    })
    if not r2 or not r2.get('result') or len(r2['result']) == 0:
        print("[!] لم يتم العثور على أي هدف"); return
    target = r2['result'][0]
    print(f" 🎯 هدف: {target['id']} @ ({target['x']},{target['y']}) لفل {target.get('level','?')}")
    add_to_exclude_history(MY_UID, target['id'])

    # === 6. معلومات اللاعب (لجلب partition) ===
    r3 = bot.query('1002', '7', {"uid": MY_UID})
    if not r3:
        print("[!] فشل جلب معلومات الخريطة"); return
    kingdom_id = r3['data']['base']['partition']

    # === 7. معلومات المنجم / الهدف ===
    r5 = bot.query('1006', '15', {
        "x": target['x'], "y": target['y'],
        "kingdomId": kingdom_id, "id": target['id']
    })
    resource_amount = 0
    if r5 and 'retData' in r5:
        resource_amount = r5.get('retData', {}).get('resource', {}).get('currentSourceNum', 0)
        print(f" 💎 كمية المورد: {resource_amount}")

    # === 8. اختيار الأبطال الذكي حسب نوع الهدف ===
    heroes_to_send = hero_selector.select(map_type=map_type, count=2)
    if not heroes_to_send:
        print("[!] لا يوجد أبطال متاحين، إيقاف."); return

    # === 9. جلب بيانات التشكيلة المناسبة للأبطال المختارين ===
    form_data = hero_selector.get_formation_for_heroes(heroes_to_send)
    if form_data:
        army_list = [{"id": int(k), "num": v} for k, v in form_data['army'].items()]
        pets_list = form_data.get('pets', [])
        runes_list = form_data.get('runes', [])
    else:
        # احتياط: استخدام التشكيلة 1
        r4 = bot.query('1005', '7', {"compiletype": 1})
        if r4 and 'data' in r4:
            army_list = [{"id": int(k), "num": v} for k, v in r4['data']['compileArmy'].items()]
            pets_list = r4['data'].get('compilePets', [])
            runes_list = r4['data'].get('compileRunePages', [])
        else:
            print("[!] فشل جلب بيانات التشكيلة"); return

    # === 10. إرسال المسير مع إعادة المحاولة ===
    march_data = {
        "needSend": False,
        "bAutoHero": True,
        "heros": heroes_to_send,
        "pets": pets_list,
        "runePages": runes_list if runes_list else {},
        "matrixType": 3,
        "mapId": kingdom_id,
        "moveLineType": 3,
        "data": {
            "data": {
                "currentSourceNum": resource_amount,
                "resourceType": 1000 + type_R
            } if resource_amount > 0 else {},
            "to": {
                "y": target['y'], "x": target['x'], "id": target['id']
            },
            "army": army_list
        }
    }

    r6 = bot.query('1007', '2', march_data)

    # إذا فشل بسبب "بطل مشغول" (9007020)، حاول بأبطال بديلين
    if r6 and r6.get('err') == '9007020':
        print(f" ⚠️ خطأ 9007020: الأبطال {heroes_to_send} مشغولون! جاري التبديل...")
        hero_selector.mark_busy(heroes_to_send, duration_seconds=300)

        heroes_to_send = hero_selector.select(map_type=map_type, count=2)
        if heroes_to_send:
            # نبدل الأبطال فقط ونبقي نفس الجيش والحيوان والرون الأصليين
            # لتجنب خطأ 8009 (جنود تشكيلة أخرى أكبر من المتوفر)
            march_data['heros'] = heroes_to_send

            print(f" 🔄 إعادة المحاولة بأبطال بديلين: {heroes_to_send}")
            r6 = bot.query('1007', '2', march_data)
        else:
            print(f" ❌ لا يوجد أبطال بديلين!")

    if r6:
        err = r6.get('err', '?')
        if err == '0':
            print(f" ✅ تم إرسال المسير بنجاح!")
            hero_selector.mark_busy(heroes_to_send, duration_seconds=120)
        else:
            print(f" ❌ فشل المسير: err={err}")
        print(f" march info = {json.dumps(r6, ensure_ascii=False, indent=2)}")


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
