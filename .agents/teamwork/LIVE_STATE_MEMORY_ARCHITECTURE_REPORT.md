# تقرير المعمارية الهندسية الشاملة: محرك الذاكرة الحية وقائمة المتحكمات وبوابة الجاهزية
**Live State Memory Engine, Controller Whitelisting & Strict Readiness Gate Architecture Report**

**التاريخ**: 2026-11-09T13:20:00Z  
**الإصدار**: 1.0.0  
**المشروع**: Ottoman Empire Game Bot (`e:\osmanli`)  
**المرجعية**: `e:\osmanli\game file\lua_src` و `AGENTS_CONSTITUTION.md` و `GEMINI.md`  

---

## 1. تشخيص المشاكل والأسباب الجذرية (Root Cause Analysis)

بناءً على الفحص الاستقصائي الدقيق الذي أجراه الوكلاء المتخصصون الثلاثة (`agent1_lua_analyst`, `agent2_task_scanner`, `agent8_deep_merge_prep`)، تم حصر وتأكيد ستة أسباب جذرية للخلل الحالي في الذاكرة:

### 1.1 الهدم القسري للحالات عبر التحديث السطحي (`State Destruction via Shallow .update()`)
- **الموقع**: `game_client.py:645-648`
  ```python
  retdata = c_data.get('retdata', {}) if isinstance(c_data, dict) else (c.get('retdata', {}) if isinstance(c.get('retdata'), dict) else {})
  if isinstance(retdata, dict) and retdata:
      self.init_data.update(retdata)
  ```
- **التشخيص**: عندما يعيد السيرفر استجابة فرعية لحركة معينة (مثل ترقية مبنى عبر `1001/2`)، يحتوي `retdata` فقط على البيانات المعدلة (مثل `{"cityCtrl": {"blist": [...]}}`). استدعاء `self.init_data.update(retdata)` يستبدل كائن `cityCtrl` بالكامل في الذاكرة الحية، مما يؤدي إلى مسح فوري لكافة الحقول غير المذكورة مثل `reslist`, `saferes`, `cinfo`, `dayMaxRes`.

### 1.2 مسح القوائم التراكمية عبر الدمج الساذج (`Destructive List Replacement in _deep_merge()`)
- **الموقع**: `game_client.py:251-261`
  ```python
  def _deep_merge(source: dict, destination: dict) -> dict:
      for key, value in source.items():
          if key in destination and isinstance(destination[key], dict) and isinstance(value, dict):
              _deep_merge(value, destination[key])
          else:
              destination[key] = value
      return destination
  ```
- **التشخيص**: في حال وجود قائمة عناصر ذات معرفات (مثل `cityCtrl.blist` التي تحتوي على 50 مبنى)، وعند وصول حزمة تحتوي على مبنى واحد محدث في `blist`، فإن السطر 261 يقوم بعملية إسناد قسري `destination['blist'] = value`. النتيجة: حذف 49 مبنى فوراً من ذاكرة البوت، مما يعطل كافة مهام البناء وجمع الموارد. والأمر نفسه ينطبق على `heroCtrl.heroes` و `buffCtrl`.

### 1.3 التراكم العشوائي والبحث التكراري البطيء (`O(N) Packet Cache Bloat & Delayed Dispatch`)
- **الموقع**: `game_client.py:925-951` في دالة `check_and_merge_controller`
- **التشخيص**: لا يتم تحديث الحالات لحظياً ومباشرة عند استلام الحزمة في `_dispatch`، بل يتم تخزين كافة الحزم في قاموس متضخم `self.cached_packets`. وعندما تطلب مهمة معينة التأكد من متحكم، يتم عمل حلقة دوران تكرارية على مئات الحزم المخزنة منذ بداية الجلسة وإعادة دمجها، مما يستهلك الذاكرة ووقت المعالج دون داعٍ.

### 1.4 تسرب واستهلاك الذاكرة بمتحكمات غير مستخدمة (`Controller Ingress Noise & Leakage`)
- **التشخيص**: فحص جلسات السيرفر الحية أثبت تدفق **226 متحكماً** مختلفاً من السيرفر. في حين أن فحص كافة مهام البوت الـ 54 أثبت أن البوت لا يحتاج ولا يقرأ سوى **42 متحكماً فقط**. هناك 187 متحكماً (مثل غرف الشات الصوتية والنصية `chatCtrl`, `chatroomCtrl`, وتنبيهات النقاط الحمراء `RedPointCtrl`, وإعلانات الفيديو `videoAdCtrl`) تتراكم في الذاكرة الحية دون أي فائدة وتزيد حجم استهلاك RAM بنسبة >81%.

### 1.5 غياب بوابة الجاهزية الصارمة (`Absence of Memory Readiness Gate`)
- **التشخيص**: يبدأ البوت بتنفيذ مهام الدورة الأساسية فور انتهاء تدفق التهيئة الأولي، حتى لو تأخر السيرفر في إرسال بيانات المباني `cityCtrl.blist` أو الجيوش `armyCtrl`. يؤدي هذا إلى أخطاء استثنائية فورية (`KeyError`) أو اتخاذ قرارات خاطئة (مثل اعتبار كافة الطوابير ممتلئة أو اعتبار الموارد صفراً).

### 1.6 غياب التزامن اللحظي لإشعارات اللعبة (`Missing Real-Time Sync for Game Notifications`)
- **الموقع**: حزم `CMD_NOTIFY_MODULE` (`1009`)
- **التشخيص**: إشعارات اللعبة مثل `NOTIFY_CITY` (الموارد الآمنة `saferes`، فروق الموارد `res`، الموارد غير المجموعة `updateUnCollectRes`) وإشعارات الطوابير `NOTIFY_QUEUE` و `NOTIFY_PLAYER_QUEUE_CHANGE` لا تعكس انتهاء أو إلغاء البناء مباشرة على حالة المبنى ومستواه في `cityCtrl`، مما يجعل حالة البوت متأخرة عن واقع السيرفر حتى يتم عمل إعادة اتصال.

---

## 2. المنطق المعماري وخطوات الحل (Architectural Solution & Blueprint)

### 2.1 إنشاء محرك الذاكرة الحية المركزي (`core/live_memory.py`)
إنشاء وحدة مركزية مستقلة ونظيفة مسؤولة عن إدارة ومزامنة الذاكرة الحية وتتضمن:
1. **قائمة المتحكمات المسموحة (`ALLOWED_CONTROLLERS`)**:
   تضم حصراً الـ 42 متحكماً التي تم تدقيقها والتأكد من احتياج مهام البوت لها، ويتم استبعاد أي متحكم خارجها فور وصوله عند مدخل الاستقبال `_dispatch`.
2. **قائمة المتحكمات الحرجة لبدء التشغيل (`CRITICAL_STARTUP_CONTROLLERS`)**:
   تضم الـ 6 متحكمات الأساسية:
   `{"cityCtrl", "lordInfoCtrl", "queueCtrl", "armyCtrl", "heroCtrl", "backpackCtrl"}`.
3. **خوارزمية الدمج العميق الذكي (`smart_deep_merge`)**:
   - القواميس: دمج تكراري عميق (Recursive Deep Merge) يحافظ على المفاتيح السابقة.
   - القوائم ذات المعرفات (Keyed Lists):
     - `blist`: التحديد عبر `index` أو `binfo.index`، مع دعم المفتاح المركب `(bid, iid)`.
     - `heroes`: التحديد عبر `id` أو `heroId`.
     - `buffCtrl`: التحديد عبر `id` أو `buffId`.
     - `queueCtrl`: التحديد عبر `queueId` أو `id` أو `qtype`.
     - `consignTasks`: التحديد عبر `index` أو `id`.
     - `local_queues`: التحديد عبر `id`.
     - التحديث يتم بنمط **Copy-on-Write (CoW)**: يتم تحديث قواميس العناصر في مكانها، واستبدال الحاوية (List container pointer) ذرياً لمنع تعطل التكرار (`RuntimeError: dictionary/list changed size during iteration`) عند قراءة الذاكرة بالتزامن مع استلام الحزم.
   - القوائم البسيطة (Primitive Lists مثل `arealist`, `wishList`): استبدال كامل مع أخذ نسخة عميقة لمنع تشارك المراجع.
4. **مزامنات الإشعارات المرجعية (`Notification Synchronizers`) استناداً لملفات Lua**:
   - `NOTIFY_CITY` (`notifyID == "1"`):
     - `res`: إضافة/خصم الفروق مع الحماية من النزول تحت الصفر.
     - `reslist`: استبدال مطلق للموارد.
     - `saferes` و `dayMaxRes`: تحديث مباشر.
     - `updateUnCollectRes`: زيادة الموارد المتراكمة فوق المبنى `curres` لكل `index`.
     - `openChargeQueue`: تفعيل طابور البناء المشحون (1201).
   - `NOTIFY_QUEUE` (`notifyID == "14"`) و `NOTIFY_PLAYER_QUEUE_CHANGE` (`notifyID == "1051"`):
     - تحديث بيانات الطابور في `queueCtrl`.
     - عند انتهاء الطابور أو إلغائه، مطابقة `buildQueueCallback` في `cityCtrl.lua`:
       - ترقية عادية: رفع `lv` بمقدار 1، وتحويل الحالة إلى `BUILD_STATE.NORMAL` ("0").
       - ترقية مجد (Honor): رفع `honorLv` و `hlv` بمقدار 1، وتحويل الحالة إلى `BUILD_STATE.NORMAL` ("0").
       - إلغاء: تحويل الحالة إلى `BUILD_STATE.NORMAL` دون رفع المستوى.
   - `backpackCtrl` (`notifyID == "1"` تحت كود الحقيبة): معالجة `add` (زيادة العدد) و `use` (خصم العدد).
   - `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, `buffCtrl`: تحديث لحظي للبيانات.

### 2.2 بوابة الجاهزية الصارمة والاستعلام التعويضي (`Strict Memory Readiness Gate`)
- إضافة دالة غير متزامنة في `game_client.py`:
  `async def wait_for_memory_ready(self, timeout: float = 30.0, auto_fetch_missing: bool = True) -> bool`
- التحقق من:
  1. وجود كافة متحكمات `CRITICAL_STARTUP_CONTROLLERS` في `self.init_data`.
  2. الاكتمال الهيكلي: التأكد من أن `cityCtrl['blist']` و `cityCtrl['reslist']` ليست فارغة، وأن `lordInfoCtrl['base']` يحوي المعرفات الأساسية.
- في حال نقص أي متحكم:
  إرسال استعلام تعويضي تلقائي (`Fallback Sync Query`) فوراً:
  - `cityCtrl`: إرسال `CMD 1001, Subcmd 1`
  - `lordInfoCtrl`: إرسال `CMD 1002, Subcmd 7` مع `{"uid": self.uid}`
  - `queueCtrl`: إرسال `CMD 1003, Subcmd 1`
  - `armyCtrl`: إرسال `CMD 1005, Subcmd 1`
  - `backpackCtrl`: إرسال `CMD 1004, Subcmd 1`
  - `local_queues`: إرسال `CMD 1007, Subcmd 1000`

### 2.3 التكامل مع دورة حياة البوت في `bot_manager.py` والعزل التام لمهمة العفريت
- استدعاء `await self.conn.wait_for_memory_ready(timeout=30.0, auto_fetch_missing=True)` في بداية دورة التشغيل الرئيسية قبل تنفيذ أي مهمة.
- الالتزام التام بالقاعدة 7 من `GEMINI.md`: مهمة العفريت `ElfBossTask` تعمل باستقلال تام ومباشر عن `march_manager`، وتستفيد من الذاكرة الحية المحدثة دون أي مساس بعزلها.

---

## 3. تفاصيل الملفات والسطور والتغييرات المتوقعة

| الملف | السطور المستهدفة | طبيعة الإجراء والتعديل | النتيجة المتوقعة |
|---|---|---|---|
| `core/live_memory.py` | ملف جديد بالكامل | كتابة محرك الذاكرة الحية، القوائم البيضاء، خوارزمية الدمج الذكي CoW، ومعالجات الإشعارات المرجعية | توفير محرك موحد، ذري، وسريع لحفظ وتحديث الحالات ومنع تسرب الذاكرة |
| `game_client.py` | أسطر الاستيراد، والتهيئة `__init__` | ربط `LiveMemoryEngine` بكائن الاتصال وحمايته بقفل التزامن | تهيئة المحرك مع كل جلسة اتصال نظيفة |
| `game_client.py` | `_dispatch()` (حوالي 630-670) | تمرير حزم `retdata` و `data` و `notifyData` لمحرك الذاكرة لحظياً واستبعاد المتحكمات غير المصرح بها | تحديث فوري للحالات ومنع تضخم الذاكرة واستبعاد 187 متحكماً زائداً |
| `game_client.py` | `check_and_merge_controller` | إزالة التكرار على `cached_packets` واستخدام الحالة الحية المحدثة مباشرة | إلغاء هدر المعالج وتسريع القراءة إلى $O(1)$ |
| `game_client.py` | قسم الدوال المساعدة | إضافة دالة `wait_for_memory_ready` مع آلية الاستعلام التعويضي التلقائي | منع بدء تشغيل المهام قبل اكتمال البيانات بنسبة 100% |
| `bot_manager.py` | حلقة الدورة الرئيسية `_run_task_pipeline` | انتظار جاهزية الذاكرة قبل بدء الدورة | منع انهيار المهام وضمان دقة اتخاذ القرارات |
| `tests/test_live_memory.py` | ملف فحص جديد | إنشاء حزمة اختبارات شاملة تغطي كافة حالات الدمج، القوائم البيضاء، وبوابة الجاهزية | إثبات برمجي قطعي لسلامة المعمارية |

---

## 4. خطة توزيع وتنفيذ سرب الوكلاء (Swarm Execution Plan)

بناءً على التوجيه الإلزامي (سرب الـ 20 وكيلاً)، سيتم توزيع المهام المتبقية على النحو التالي:
- **المرحلة M1 (Core Memory Engine & Hygiene)**:
  - الوكيل 9 (`teamwork_worker`): هندسة وتنظيف الذاكرة ومنافذ الاستقبال في `game_client.py`.
- **المرحلة M2 (Controller State Synchronizers)**:
  - الوكيل 4 (`teamwork_worker`): مزامنة المدينة والمباني والموارد (`cityCtrl`).
  - الوكيل 5 (`teamwork_worker`): مزامنة الطوابير وانتهاء البناء وترقية المستويات (`queueCtrl`).
  - الوكيل 6 (`teamwork_worker`): مزامنة الجيوش والأبطال واللورد والـ Buffs.
  - الوكيل 7 (`teamwork_worker`): مزامنة الحقيبة والمهام وسفن الميناء.
- **المرحلة M3 (Readiness Gate & Bot Loop Integration)**:
  - الوكيل 3 (`teamwork_worker`): بناء بوابة الجاهزية `wait_for_memory_ready` والاستعلام التعويضي.
  - الوكيل 10 (`teamwork_worker`): تكامل حلقة البوت في `bot_manager.py` مع تأكيد عزل العفريت.
- **المرحلة M4 (Live Verification & QA Battery - 10 وكلاء فحص ميداني)**:
  - الوكلاء 11، 12، 13، 14، 15، 16، 17، 18، 19: تنفيذ الفحوصات الحية والمحاكاة وضغط التزامن.
  - الوكيل 20: الاعتماد النهائي وتوثيق النتائج.

---
**الخلاصة والاعتماد**: هذا التقرير يمثل التصميم المرجعي المكتمل، وسيتم الانطلاق فوراً في تنفيذ الوحدات البرمجية محلياً وفق الضوابط الصارمة لـ `GEMINI.md`.
