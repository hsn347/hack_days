# تقرير فني مسبق لإصلاحات الذاكرة الحية وعميل اللعبة (Pre-Edit Technical Report)
**المشروع**: Empire Bot (`osmanli`)  
**المهندس**: Worker: Live Memory Remediation Engineer  
**المسار**: `e:\osmanli\.agents\teamwork\worker_remediation_m4\pre_edit_report.md`  
**التاريخ**: 2026-11-09T13:54:00Z  
**المرجعية**: `ORIGINAL_REQUEST.md`, تقارير QA للوكلاء 13 و 14 و 16، و `GEMINI.md` (القواعد 5 و 6).

---

## 1. تشخيص الأسباب والمشاكل المرصودة (Diagnosis & Rationale)

تم تكليفنا بمعالجة 4 ثغرات حرجة تم تشخيصها وتوثيقها بدقة بواسطة وكلاء التحقق الميداني والخصوم البرمجيين (QA Challengers 13 & 14 & 16):

### 1.1 الازدواجية في معالجة إشعارات السيرفر (Double Ingestion in `game_client.py:680-691`)
- **التشخيص**: في دالة `GateClient._dispatch()`، يتم تمرير الحزمة المستلمة فوراً إلى محرك الذاكرة عبر `self.memory_engine.ingest_packet(c)`. يقوم `ingest_packet(c)` تلقائياً بفحص ما إذا كانت الحزمة تحمل `cmd == "1009"` ومفتاح `notifyID`، ويستدعي داخلياً `self.handle_notify(notify_id, notify_data)`.
- **الخلل**: الكود في الكتلة رقم 3 من `_dispatch()` في السطور 680-691 يعيد فحص `cmd == '1009'` ويستدعي `self.memory_engine.handle_notify(...)` مرة ثانية لنفس الحزمة!
- **الضرر**: مضاعفة كافة فروق الموارد (`res`) بمقدار الضعف، ومضاعفة الموارد غير المجموعة (`updateUnCollectRes`)، وقفز مستوى المبنى مستويين دفعة واحدة (من 10 إلى 12) عند اكتمال البناء.
- **الحل**: حذف الكتلة رقم 3 المكررة بالكامل من `game_client.py`، بحيث تعالج كل حزمة مرة واحدة قطعية عبر `ingest_packet`.

### 1.2 كسر مرجع قاموس المسيرات عند التزامن الشامل (`local_queues_map` In-place Mutation in `core/live_memory.py:974`)
- **التشخيص**: عند استلام إشعار مزامنة المسيرات `NOTIFY_LOCAL_QUEUE_SYNC (202)` بنوع الرسالة `ADD_ALL (4)`، كان الكود ينفذ:
  `self.local_queues_map = {str(m.get("id")): m ...}`.
- **الخلل**: هذا الإسناد ينشئ كائن قاموس جديد كلياً في الذاكرة ويسنده إلى `self.memory_engine.local_queues_map`، بينما يظل `conn.local_queues_map` (المربوط بالقاموس القديم أثناء التهيئة في سطر 477) يشير إلى الكائن القديم المهجور.
- **الضرر**: انفصال مرجع الاتصال، مما يجعل قراءة المسيرات في `conn.local_queues = list(self.local_queues_map.values())` تقرأ مسيرات ميتة ولا تتلقى المسيرات الحديثة.
- **الحل**: استخدام التعديل الموضعي (In-place Mutation) عبر `.clear()` ثم `.update(new_map)` للحفاظ على نفس كائن القاموس ومرجعه المشترك سليماً.

### 1.3 عدم تصفير الجرحى وطوابير التدريب في `armyCtrl` عند الشفاء أو الانتهاء (`core/live_memory.py:821-825`)
- **التشخيص**: دالة الدمج العميق `smart_deep_merge` تحافظ على المفاتيح الموجودة في القاموس الهدف إذا كان القاموس المحدث فارغاً `{}`.
- **الخلل**: عندما يُشفى كافة الجرحى أو تنتهي طوابير التدريب، يرسل السيرفر في إشعار `NOTIFY_ARMY (15)` قاموساً فارغاً `"woundedArmy": {}` و `"trainArmy": {}`. بما أن `smart_deep_merge` لا تحذف المفاتيح الفارغة، تظل بيانات الجرحى والتدريب القديمة عالقة في الذاكرة دون تصفير.
- **الحل**: الاستبدال الصريح المباشر لقاموسي `woundedArmy` و `trainArmy` عبر `copy.deepcopy` عند ورودهما في حزمة الإشعار قبل الدمج، مطابقة لمنطق Lua الأصلي في `armyCtrl_dec.lua:848-851`.

### 1.4 افتقار طابور البناء الثاني `openChargeQueue` لوقت البداية الافتراضي (`core/live_memory.py:643`)
- **التشخيص**: في إشعار المدينة `NOTIFY_CITY`، عند استلام `openChargeQueue` بدون حقل `starttime` أو بقيمة `<= 0`، تعتبر مهمة البناء `tasks/building.py` الطابور منتهياً فور استئجاره.
- **الحل**: التأكد من ضبط `starttime = int(time.time())` إذا كان مفقوداً أو `<= 0`.

---

## 2. المنطق والخطوات التطبيقية (Logic & Execution Steps)

1. **الخطوة 1: تعديل `game_client.py`**:
   - إزالة الكتلة 3 (`# ── 3. توجيه إشعارات CMD 1009 اللحظية لمحرك الذاكرة الحية ──────────`) في السطور 680-691.
   - إعادة ترقيم الكتل اللاحقة لتظل التعليقات متناسقة وواضحة.
   - استخدام أداة `edit_file` المباشرة فقط بدون سكريبتات بايثون.

2. **الخطوة 2: تعديل `core/live_memory.py`**:
   - إضافة `import time` إلى استيرادات رأس الملف.
   - في `_handle_notify_city` (قسم `openChargeQueue`): فحص `starttime` وتعيينه إلى `int(time.time())` إذا كان `<= 0` أو غير موجود.
   - في `_handle_notify_army`: استبدال `woundedArmy` و `trainArmy` صراحة عند توفرهما في `army_info` أو في `item` المباشر.
   - في `_handle_notify_local_queue`: في معالجة `msg_type == 4` (ADD_ALL)، بناء القاموس الجديد في متغير `new_map` ثم تنفيذ:
     ```python
     self.local_queues_map.clear()
     self.local_queues_map.update(new_map)
     ```

3. **الخطوة 3: تكييف الاختبارات التنافسية للتحقق من زوال العيوب**:
   - في `tests/test_live_socket_spy.py`: تحديث الاختبارين التنافسيين اللذين كتبهما الوكيل 13 لإثبات الخلل:
     - `test_double_ingestion_bug_detection`: التحقق من أن الموارد زادت بمقدار 1,000 فقط (الناتج 11000 وليس 12000).
     - `test_wire_queue_finish_double_level_jump_proof`: التحقق من أن مستوى المبنى زاد خطوة واحدة فقط (11 وليس 12).
   - في `tests/test_live_memory_marches_army.py`: تحديث الاختبارين التنافسيين اللذين كتبهما الوكيل 16 لإثبات الخلل:
     - `test_adversarial_empty_wounded_and_train_clearing`: التحقق من أن `woundedArmy` و `trainArmy` أصبحت قواميس فارغة `{}` بعد الشفاء وانتهاء التدريب.
     - `test_adversarial_add_all_breaks_connection_local_queues_map_reference`: التحقق من أن `is_detached` أصبحت `False` وأن المرجع المشترك ظل متصلاً وتحديثات `conn_local_queues_map` فورية.

4. **الخطوة 4: الفحص البرمجي والتحقق الشامل بنسبة 100%**:
   - تشغيل `python -m unittest tests/test_live_socket_spy.py`
   - تشغيل `python -m unittest tests/test_live_memory_marches_army.py`
   - تشغيل `python -m unittest tests/test_live_memory.py`
   - تشغيل `python -m unittest tests/test_game_client_hygiene.py`
   - التأكد من اجتياز كافة الاختبارات بنجاح 100%.

---

## 3. تفاصيل التعديلات والملفات والسطور المستهدفة (Exact File Diffs Plan)

### ملف 1: `game_client.py`
- **الموقع**: السطور 680-691.
- **الإجراء**: حذف كود استدعاء `handle_notify` المزدوج.

### ملف 2: `core/live_memory.py`
- **الموقع 1**: رأس الملف (سطر 25 تقريباً) - إضافة `import time`.
- **الموقع 2**: سطر 643 - ضبط `starttime` لطابور `openChargeQueue`.
- **الموقع 3**: سطور 821-825 - استبدال `woundedArmy` و `trainArmy` صراحة.
- **الموقع 4**: سطر 974 - استبدال إعادة تعيين `self.local_queues_map` بـ `.clear()` و `.update(...)`.

### ملفات الاختبار: `tests/test_live_socket_spy.py` و `tests/test_live_memory_marches_army.py`
- **الإجراء**: تكييف الفحوصات التنافسية لتوكيد سلامة الإصلاحات ومطابقتها للمعايير.

---
**النتيجة المتوقعة**: انعدام تام لأي مضاعفة للإشعارات، سلامة تامة لمراجع المسيرات وقواميس الجيوش، واستقرار كامل لكافة وحدات الاختبار.


### 1.5 حصانة قراءة الأرقام الكسرية كأوتار نصوص (Float String Safe Conversion)
- **التشخيص**: أبلغ الوكيل 18 عن إمكانية إرسال سيرفر اللعبة كميات الموارد كأرقام كسرية في سلاسل نصوص (مثل `'514089541.49461'` أو `'0.0'`). استخدام `int(...)` مباشرة على هذه النصوص يسبب استثناء `ValueError: invalid literal for int() with base 10`.
- **الحل**: استخدام `int(float(...))` في سطور قراءة وحساب موارد المدينة والمباني (`reslist` و `curres`).
