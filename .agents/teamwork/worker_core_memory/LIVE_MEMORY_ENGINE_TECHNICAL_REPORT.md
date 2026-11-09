# تقرير فني شامل: هندسة وبناء محرك الذاكرة الحية (Live Memory Engine)
**Technical Architecture & Implementation Report for `core/live_memory.py`**

**التاريخ**: 2026-11-09T13:25:00Z  
**المهندس**: Worker: Core Live Memory Engineer (Agent 8 Implementation)  
**الملف المملوك**: `e:\osmanli\core\live_memory.py`  
**المرجعيات**:
- `ORIGINAL_REQUEST.md`
- `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`
- `agent8_deep_merge_prep/DEEP_MERGE_SPEC.md`
- `agent1_lua_analyst/LUA_PROTOCOL_SPEC.md`
- `agent2_task_scanner/CONTROLLER_WHITELIST_SPEC.md`
- `GEMINI.md` (القواعد 1-8)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause & Motivation)

### 1.1 التشخيص
1. **انهيار حالة المدينة عند التحديثات الجزئية**: كان كود العميل القديم يستدعي `self.init_data.update(retdata)` بشكل سطحي عند كل استجابة من السيرفر. فعند استلام رد ترقية مبنى يحوي فقط المبنى المحدث في `blist`، كان يستبدل كائن `cityCtrl` بالكامل، مما يؤدي لحذف فوري لقوائم الموارد (`reslist`) والموارد الآمنة (`saferes`) وكافة المباني الأخرى الـ 49.
2. **المسح التدميري للقوائم عبر الدمج الساذج**: دالة `_deep_merge` السابقة كانت تسند القائمة المستلمة مباشرة `dest[key] = value`، مما يمسح أي عناصر سابقة غير متضمنة في التحديث.
3. **تضخم الذاكرة بالمتحكمات غير المستخدمة**: أثبت الفحص الميداني أن السيرفر يرسل ما يصل إلى 226 متحكماً (شات، راديو، إعلانات، نقاط حمراء)، بينما لا يحتاج البوت إلا إلى 42 متحكماً فقط. ترك هذه المتحكمات يتسبب في تضخم الذاكرة بنسبة >81% وبطء المعالجة.
4. **غياب التزامن اللحظي مع إشعارات اللعبة**: إشعارات `CMD_NOTIFY_MODULE` (1009) مثل `NOTIFY_CITY` (9) و `NOTIFY_QUEUE` (14) لم تكن تنعكس فورياً في الذاكرة الحية لترقية المباني (`lv` / `honorLv`) أو ضبط حالة البناء (`state = "0"`).
5. **عدم وجود بوابة جاهزية صارمة**: كان البوت يبدأ تنفيذ المهام قبل اكتمال تحميل البيانات الهيكلية للقلعة مما يتسبب في `KeyError` وقرارات خاطئة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Architecture & Implementation Steps)

### 2.1 القوائم البيضاء والمتحكمات الحرجة
- تعريف `ALLOWED_CONTROLLERS`: مجموعة ثابتة `frozenset` تضم بالضبط الـ 42 متحكماً المصرح بها وفق `CONTROLLER_WHITELIST_SPEC.md`.
- تعريف `CRITICAL_STARTUP_CONTROLLERS`: مجموعة ثابتة تضم الـ 6 متحكمات الإلزامية (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`).
- تعريف `FALLBACK_QUERIES`: جدول استعلامات التعويض التلقائي عند نقص أي متحكم حرج.

### 2.2 خوارزمية الدمج الذكي العميق (`smart_deep_merge`)
- **القواميس المتداخلة**: دمج تكراري عميق يحافظ على كافة المفاتيح غير المعدلة.
- **القوائم ذات المعرفات (Keyed Lists)**:
  - مطابقة الكيانات بمعرفاتها الأساسية والمركبة:
    - `cityCtrl.blist`: عبر `index` أو `binfo.index`، مع دعم المفتاح المركب `(bid, iid)`.
    - `heroCtrl.heroes` / `heroes`: عبر `id`, `heroId`, `cId`.
    - `buffCtrl`: عبر `id`, `buffId`.
    - `queueCtrl`: عبر `qtype`, `queuetype`, `queueId`, `id`.
    - `consignTasks`: عبر `index`, `id`.
    - `local_queues`: عبر `id`.
    - `backpackCtrl.items`: عبر `id`, `itemId`.
  - معالجة الحذف الآمن عبر `_delete`, `notifyType in ('del', 'remove', 'cancel', 'finish')`.
  - تطبيق مبدأ **Copy-on-Write (CoW)** لاستبدال مرجع حاوية القائمة ذرياً لمنع تعطل مؤشرات التكرار أثناء القراءة المتزامنة.
- **القوائم البسيطة (Primitive Lists)**: استبدال فوري بنسخة عميقة (`copy.deepcopy`).

### 2.3 محرك الذاكرة الحية الموحد (`LiveMemoryEngine`)
- فلترة الحزم عبر `filter_whitelisted` لاستبعاد أي متحكم خارج الـ 42 متحكماً.
- استخراج الحزم ودمجها عبر `ingest_packet`.
- معالجة كافة الإشعارات عبر `handle_notify`:
  - `NOTIFY_CITY`: تحديث نسبي للموارد `res`، استبدال مطلق لـ `reslist` و `saferes` و `dayMaxRes`، وزيادة الموارد غير المجموعة `updateUnCollectRes` في المبنى المعني، وفتح الطابور الإضافي `openChargeQueue`.
  - `NOTIFY_QUEUE` و `NOTIFY_PLAYER_QUEUE_CHANGE`: تحديث طوابير البناء، وعكس انتهاء/إلغاء البناء مباشرة على مستوى وحالة المبنى في `cityCtrl` (`state = "0"`، ترقية `lv` أو `honorLv`).
  - `NOTIFY_BACKPACK`: حساب دقيق لإضافة وخصم العناصر (`add` و `use`).
  - `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, `buffCtrl`: مزامنة لحظية دقيقة.
- التحقق الصارم من جاهزية الذاكرة واكتمالها الهيكلي عبر `is_memory_ready() -> tuple[bool, list[str]]`.
- حماية التزامن المزدوج عبر `threading.RLock` و `asyncio.Lock`.

---

## 3. الملفات والسطور والتغييرات المتوقعة والنتائج

| الملف | طبيعة الإجراء | التفاصيل التقنية | النتيجة المتوقعة |
|---|---|---|---|
| `core/live_memory.py` | إنشاء ملف جديد بالكامل | بناء كافة الثوابت والخوارزميات وفئة `LiveMemoryEngine` | توفير محرك ذاكرة حية موحد وذري وعالي الأداء ومحمي من التضارب |
| `tests/test_live_memory.py` | إنشاء ملف اختبارات جديد | تغطية كافة الاختبارات الـ 9 المحددة في المواصفات واختبارات الإشعارات وبوابة الجاهزية | التحقق المؤتمت بنسبة 100% من صحة وسلامة المنطق |

---
**جاهز للانتقال الفوري لكتابة الكود والتحقق البرمجي.**
