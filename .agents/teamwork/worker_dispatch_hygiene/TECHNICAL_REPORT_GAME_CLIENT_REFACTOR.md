# تقرير فني مستقل: هندسة تنظيف الذاكرة ومنافذ الاستقبال وبوابة الجاهزية في `game_client.py`
**Technical Pre-Action Report: Memory Hygiene, Real-Time Dispatch Refactoring & Readiness Gating**

**التاريخ**: 2026-11-09T13:28:00Z  
**المحرر والمهندس المسؤول**: Worker: Memory Hygiene & Dispatch Refactor Engineer (Agent 9 Implementation)  
**الملف المستهدف حصراً**: `e:\osmanli\game_client.py`  
**المرجعية**: `ORIGINAL_REQUEST.md`, `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`, `CONTROLLER_WHITELIST_SPEC.md`, `DEEP_MERGE_SPEC.md`, `GEMINI.md`  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause Analysis & Rationale)

1. **الهدم القسري للحالات عبر `update()` السطحي (`game_client.py:645`)**:
   عند وصول ردود أوامر السيرفر (Deltas)، يحتوي `retdata` فقط على البيانات المعدلة (مثل تحديث مبنى واحد في `blist`). استدعاء `self.init_data.update(retdata)` الحالي يستبدل كائن المتحكم بالكامل، مما يمسح كافة الحقول غير المذكورة (مثل `reslist`, `saferes`, وباقي المباني في المدينة).
2. **مسح القوائم التراكمية عبر `_deep_merge()` البدائي (`game_client.py:251-261`)**:
   في حال وجود قائمة عناصر ذات معرفات (مثل `blist` المكونة من 50 مبنى)، فإن الدمج القديم يستبدل القائمة بالكامل بالقائمة الواردة المكونة من عنصر واحد، مما يحذف 49 مبنى فوراً.
3. **التراكم غير المحدود للحزم والبحث التكراري البطيء ($O(N)$ Packet Bloat in `check_and_merge_controller`)**:
   في السطور 925-951، يتم تخزين كافة الحزم في `self.cached_packets` وتكرار فحصها ودمجها مراراً وتكراراً عند كل استعلام، مما يؤدي لتضخم الذاكرة واستهلاك المعالج.
4. **تسرب الذاكرة بالمتحكمات غير المصرح بها (187 متحكماً زائداً)**:
   تدفق مئات المتحكمات غير المستخدمة (مثل الشات الصوتي، والإعلانات، والنقاط الحمراء) يضخم استهلاك RAM بنسبة >81%.
5. **غياب بوابة الجاهزية الصارمة (`wait_for_memory_ready`)**:
   بدء المهام قبل اكتمال المتحكمات الأساسية (`CRITICAL_STARTUP_CONTROLLERS`) يتسبب في أخطاء استثنائية وقرارات خاطئة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Architectural Logic & Execution Steps)

### 2.1 ربط محرك الذاكرة الحية (`LiveMemoryEngine`)
- في `GateClient.__init__` (وكذلك دعم الاسم المستعار `GameClient = GateClient`):
  - استيراد وتهيئة `self.memory_engine = LiveMemoryEngine()`.
  - ربط `self.init_data = self.memory_engine.init_data` لتكون هي المصدر الوحيد للحقيقة (Single Source of Truth).
  - توفير استيراد مرن وآمن لمحرك الذاكرة والقوائم البيضاء (`ALLOWED_CONTROLLERS`, `CRITICAL_STARTUP_CONTROLLERS`).

### 2.2 إعادة هيكلة منفذ الاستقبال (`_dispatch`)
- بمجرد استلام حزم المقبس وفك تشفيرها:
  1. تمرير الحزمة فوراً إلى `self.memory_engine.ingest_packet(c)`.
  2. في حال استلام أمر الإشعارات `cmd == '1009'`، استخراج `notifyID` و `notifyData` وتمريرها إلى `self.memory_engine.handle_notify(notify_id, notify_data)`.
  3. استبعاد وتجاهل أي متحكم خارج `ALLOWED_CONTROLLERS` تلقائياً لمنع تسرب الذاكرة.
  4. تنظيف وحصر `self.cached_packets`: تحديد سقف أقصى آمن للحزم المخزنة مؤقتاً (Bounded LRU Ring Cache لا يتجاوز 64 حزمة)، أو الاحتفاظ فقط بما يلزم للطلبات المعلقة `_pending`، لمنع التراكم غير المحدود عبر الجلسات الطويلة.
  5. الحفاظ على المزامنات المباشرة الحساسة (مثل `local_queues_map` لحركة الجيوش على الخريطة وسفن الميناء) وتغذيتها لحظياً.

### 2.3 تسريع وإعادة صياغة `check_and_merge_controller`
- إلغاء حلقة التكرار البطيئة على `cached_packets` ($O(N)$ loop).
- الاعتماد التام على المزامنة اللحظية الحية: التحقق المباشر من وجود `ctrl_name in self.init_data` خلال زمن قياسي $O(1)$ وإرجاع `(True, self.init_data[ctrl_name])`.

### 2.4 بناء بوابة الجاهزية الصارمة (`wait_for_memory_ready`)
- إضافة الدالة غير المتزامنة:
  `async def wait_for_memory_ready(self, timeout: float = 30.0, auto_fetch_missing: bool = True) -> bool:`
  1. فحص `self.memory_engine.is_memory_ready()`.
  2. في حال وجود نقص في أي من المتحكمات الأساسية الستة (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`) وكان `auto_fetch_missing=True`:
     إرسال الاستعلامات التعويضية المحددة في `CONTROLLER_WHITELIST_SPEC.md`:
     - `cityCtrl`: إرسال استعلام `1001/1` (`REQ_INIT_CITYDATA`)
     - `lordInfoCtrl`: إرسال استعلام `1002/7` (`REQ_LORD_INFO_UID`) مع `{"uid": self.uid}`
     - `queueCtrl`: إرسال استعلام `1003/1` (`REQ_INIT_QUEUEDATA`)
     - `armyCtrl`: إرسال استعلام `1005/1` (`REQ_INIT_ARMYDATA`)
     - `backpackCtrl`: إرسال استعلام `1004/1` (`REQ_INIT_BACKPACKDATA`)
     - `local_queues`: إرسال استعلام `1007/1000` (`REQ_GET_ALL_QUEUE_INFO`)
  3. حلقة انتظار ذكية بفاصل زمني 0.25 ثانية حتى اكتمال الجاهزية أو انقضاء `timeout`.
  4. توفير نفس الدالة في كائن الواجهة الشاملة `GameConnection.wait_for_memory_ready()`.

---

## 3. الملفات والسطور والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة

### 3.1 التعديل على `game_client.py`
1. **السطور 30-50**: استيراد `LiveMemoryEngine` من `core.live_memory`.
2. **السطور 430-465**: تهيئة `self.memory_engine` وربط `self.init_data` في `GateClient.__init__`.
3. **السطور 620-750**: استبدال الدمج السطحي في `_dispatch` بالمعالجة اللحظية عبر `self.memory_engine.ingest_packet` و `handle_notify`، وتطبيق سقف الحزم المؤقتة لمنع التضخم.
4. **السطور 910-955**: إعادة كتابة `check_and_merge_controller` لتكون فحصاً فورياً $O(1)$ في `self.init_data`.
5. **إضافة دالة `wait_for_memory_ready`**: داخل كل من `GateClient` و `GameConnection`.
6. **إضافة الاسم المستعار `GameClient = GateClient`**: لضمان التوافقية بنسبة 100%.

### 3.2 الأوامر التي ستُنفذ للتحقق بعد التعديل (Commands to Execute)
1. `python -m py_compile game_client.py` (التحقق من صحة القواعد النحوية وخلو الملف من أخطاء الـ Syntax).
2. فحص الاستيراد واختبار الوحدات البرمجية للتحقق من عدم حدوث أي Regressions:
   `python -c "import game_client; print('game_client imported successfully')"`

---
**النتيجة المتوقعة**:
- صفر تسريب للحزم غير المصرح بها (Drop 187 non-whitelisted controllers).
- تزامن لحظي فوري للذاكرة الحية (Real-time $O(1)$ synchronization).
- منع تام لهدم أو مسح الحالات والمباني (Zero state destruction).
- جاهزية صارمة تمنع انطلاق مهام البوت قبل اكتمال البيانات بنسبة 100%.
