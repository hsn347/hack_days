# تقرير الاستلام والتسليم النهائي: الفحص الميداني والتحقق التنافسي لمزامنة المسيرات والجيوش
**Final Handoff Report: Marches & Army State Synchronization QA & Adversarial Audit**

- **الوكيل الفاحص**: Agent 16 (Marches & Army Live QA Agent)
- **الأدوار**: Reviewer, Adversarial Critic
- **مسار العمل**: `e:\osmanli\.agents\teamwork\agent16_marches_army\`
- **التاريخ**: 2026-11-09T13:53:00Z
- **المرجعية**: `ORIGINAL_REQUEST.md`, `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`, `LUA_PROTOCOL_SPEC.md`, `armyCtrl_dec.lua`, `kingdomMapCtrl_dec.lua`, `core/live_memory.py`, `game_client.py`
- **القرار (Verdict)**: **REQUEST_CHANGES** (التحقق الوظيفي الأساسي ناجح بنسبة 100% في 15 اختباراً، ولكن تم كشف ثغرتين معماريتين يجب على الفريق الأساسي تعديلهما).

---

## 1. الملاحظات المباشرة (Observation)

### 1.1 ملاحظات الكود المصدري
1. **معالجة مسيرات الخريطة (`local_queues`) في `core/live_memory.py:945-980`**:
   ```python
   def _handle_notify_local_queue(self, notify_data: Any) -> None:
       items = notify_data if isinstance(notify_data, list) else [notify_data]
       for msg in items:
           if not isinstance(msg, dict):
               continue
           msg_type = msg.get("msgType")
           data = msg.get("data")

           if msg_type == 1 and isinstance(data, dict):  # ADD
               qid = str(data.get("id", ""))
               if qid:
                   self.local_queues_map[qid] = data
           elif msg_type == 2 and isinstance(data, dict):  # REMOVE
               qid = str(data.get("id", ""))
               self.local_queues_map.pop(qid, None)
           elif msg_type == 3 and isinstance(data, dict):  # UPDATE
               qid = str(data.get("id", ""))
               if qid in self.local_queues_map:
                   smart_deep_merge(self.local_queues_map[qid], data, in_place=True)
               else:
                   self.local_queues_map[qid] = data
           elif msg_type == 4 and isinstance(data, list):  # ADD_ALL
               self.local_queues_map = {str(m.get("id")): m for m in data if isinstance(m, dict) and m.get("id")}
           elif msg_type == 5:  # REMOVE_ALL
               self.local_queues_map.clear()

       # Mirror in init_data["local_queues"]
       self.init_data["local_queues"] = list(self.local_queues_map.values())
   ```
2. **ربط المرجع في `game_client.py:477` و `699`**:
   ```python
   # Line 477 in GameConnection.__init__:
   self.local_queues_map: dict = self.memory_engine.local_queues_map

   # Line 699 in GameConnection._dispatch:
   self.local_queues = list(self.local_queues_map.values())
   ```
   - عند تنفيذ `msg_type == 4` (ADD_ALL)، يتم عمل إسناد جديد `self.local_queues_map = { ... }` داخل `memory_engine`.
   - النتيجة: ينفصل المرجع في كائن الاتصال `conn.local_queues_map` عن `engine.local_queues_map` ويظل يشير إلى القاموس القديم المتروك، مما يجعل `conn.local_queues` في السطر 699 يقرأ بيانات قديمة ميتة.

3. **معالجة الجيوش (`armyCtrl`) في `core/live_memory.py:814-826`**:
   ```python
   def _handle_notify_army(self, notify_data: Any) -> None:
       """Synchronizes NOTIFY_ARMY (15)."""
       items = notify_data if isinstance(notify_data, list) else [notify_data]
       army_ctrl = self.init_data.setdefault("armyCtrl", {})
       for item in items:
           if not isinstance(item, dict):
               continue
           army_info = item.get("armyInfo")
           if isinstance(army_info, dict):
               smart_deep_merge(army_ctrl, army_info, in_place=True)
           else:
               smart_deep_merge(army_ctrl, item, in_place=True)
   ```
4. **منطق اللعبة المرجعي في `armyCtrl_dec.lua:848-851`**:
   ```lua
   local armyInfo = v.armyInfo
   if armyInfo then
     self.armyInfo = armyInfo
   ```
   - في Lua، الاستبدال مطلق وكامل (`self.armyInfo = armyInfo`).
   - في بايثون، يُستخدم `smart_deep_merge(army_ctrl, army_info, in_place=True)`.
   - عندما يُشفى جميع الجرحى في المشفى، يرسل السيرفر `"woundedArmy": {}`.
   - وعندما ينتهي تدريب كافة القوات، يرسل السيرفر `"trainArmy": {}`.
   - دالة `smart_deep_merge` لا تحذف أي مفتاح من الهدف إذا كان القاموس المحدث فارغاً `{}`.
   - النتيجة المثبتة بالاختبار: تظل أرقام الجرحى القديمة وطوابير التدريب المنتهية عالقة للأبد في `armyCtrl["woundedArmy"]` و `armyCtrl["trainArmy"]` دون مسح!

### 1.2 نتائج التنفيذ البرمجي
- تم تشغيل الاختبارات عبر الأمر:
  `python -m unittest tests/test_live_memory_marches_army.py -v`
- النتيجة:
  ```
  test_adversarial_add_all_breaks_connection_local_queues_map_reference ... ok
  test_adversarial_empty_wounded_and_train_clearing ... ok
  test_army_readiness_gate_validation ... ok
  test_army_sync_initial_login_payload ... ok
  test_army_sync_routing_variants ... ok
  test_army_sync_v_army_info_push_notification ... ok
  test_adversarial_malformed_queue_data_graceful_handling ... ok
  test_adversarial_remove_nonexistent_march_does_not_crash ... ok
  test_local_queue_packet_routing_variants ... ok
  test_local_queue_sync_add_all_and_remove_all ... ok
  test_local_queue_sync_add_single_and_multiple ... ok
  test_local_queue_sync_numeric_and_string_id_normalization ... ok
  test_local_queue_sync_remove_on_arrival_zero_missed_pruning ... ok
  test_local_queue_sync_update_status_and_position ... ok
  test_local_queue_sync_zero_duplicates_on_repeated_add ... ok

  Ran 15 tests in 0.001s
  OK
  ```
- تشغيل الحزمة الكاملة (52 اختباراً):
  `python -m unittest tests/test_live_memory.py tests/test_live_memory_marches_army.py`
  النتيجة: `Ran 52 tests in 0.763s — OK`.

---

## 2. سلسلة المنطق والاستدلال (Logic Chain)

1. **التحقق من صحة `local_queues` March Sync**:
   - إشعارات `ADD (1)` تضيف المسيرة بنجاح لمفتاح القاموس المعرف `id`.
   - إشعارات `UPDATE (3)` تحدث الحقول المتغيرة (الحالة، الإحداثيات، السرعة) دون المساس بالحقول السابقة.
   - إشعارات `REMOVE (2)` تحذف المسيرة فوراً بالـ `pop(id)`.
   - المزامنة مع `init_data["local_queues"]` عبر `list(self.local_queues_map.values())` تضمن عدم تكرار أي مسيرة نهائياً (`Zero Duplicates`)، لأن المعرف فريد داخل القاموس، وتضمن خلو القائمة من أي مسيرة منتهية فور حذفها (`Zero Missed Prunings`).
   - استيعاب المعرفات النصية والرقمية (`77777` و `"77777"`) تم التحقق منه ونجح تماماً.

2. **التحقق من صحة `armyCtrl` Updates**:
   - حزمة التهيئة الأولية من `CMD 1005 / Subcmd 1` تُستقبل وتُصفى عبر القائمة البيضاء (`ALLOWED_CONTROLLERS`).
   - إشعار `NOTIFY_ARMY (15)` يحمل `v.armyInfo` ويقوم بتحديث `totalArmy` و `woundedArmy` و `trainArmy`.
   - بوابة الجاهزية `is_memory_ready()` تفحص بنجاح وجود `totalArmy` أو `woundedArmy` داخل `armyCtrl`.

3. **الاستدلال التنافسي (Adversarial Findings & Root Causes)**:
   - **الثغرة الأولى (Major Finding 1 - Ingress Map Re-assignment)**:
     في `core/live_memory.py:974`، استبدال القاموس بالكامل `self.local_queues_map = { ... }` عند استلام `ADD_ALL (4)` يكسر الربط مع `conn.local_queues_map` في `game_client.py:477`. بالتالي، عندما يُحدّث `conn` لاحقاً `conn.local_queues = list(self.local_queues_map.values())` في سطر 699، فإنه يقرأ من القاموس القديم المنفصل!
     **الحل المقترح للمهندسين**: تعديل السطر 974 ليعتمد التحديث الموضعي (In-place Mutation):
     ```python
     elif msg_type == 4 and isinstance(data, list):  # ADD_ALL
         self.local_queues_map.clear()
         self.local_queues_map.update({str(m.get("id")): m for m in data if isinstance(m, dict) and m.get("id")})
     ```
   - **الثغرة الثانية (Major Finding 2 - Wounded & Training Army Retention)**:
     في `core/live_memory.py:823`، استخدام `smart_deep_merge` لتحديث `armyInfo` يعني أنه عند إرسال السيرفر `"woundedArmy": {}` (بعد شفاء كل الجرحى) أو `"trainArmy": {}` (بعد انتهاء التدريب)، فإن `smart_deep_merge` لا يحذف الجرحى أو طوابير التدريب القديمة! يظل البوت معتقداً أن لديه جرحى في المشفى وجنوداً قيد التدريب.
     **الحل المقترح للمهندسين**: في `_handle_notify_army`:
     ```python
     if isinstance(army_info, dict):
         if "woundedArmy" in army_info:
             army_ctrl["woundedArmy"] = copy.deepcopy(army_info["woundedArmy"])
         if "trainArmy" in army_info:
             army_ctrl["trainArmy"] = copy.deepcopy(army_info["trainArmy"])
         smart_deep_merge(army_ctrl, army_info, in_place=True)
     ```

---

## 3. المحاذير والافتراضات (Caveats)

1. مسيرات التحالف والفيالق المشتركة (Rallies) التي يقودها لاعبون آخرون يتم إدراجها في الخريطة، ولكن `local_queues` مخصصة حصراً لمسيرات اللاعب صاحب الحساب (`fromUserQueueMap`).
2. تم فحص منطق مقبس السيرفر ومطابقته برمجياً مع `armyCtrl_dec.lua` و `kingdomMapCtrl_dec.lua` بمحاكاة دقيقة مطابقة لبروتوكول TCP للمشروع.
3. بصفتي Reviewer & Critic، لم أقم بتعديل ملفات الكود المصدري في `core/live_memory.py` التزاماً بقواعد الحياد وضمان الجودة المستقلة.

---

## 4. الاستنتاج النهائي (Conclusion)

- **حالة التحقق الوظيفي**: نجاح كامل بنسبة 100% لكافة حالات `ADD`, `UPDATE`, `REMOVE` في `local_queues` مع إثبات `Zero Duplicates` و `Zero Missed Prunings`.
- **حالة تحديث الجيوش**: نجاح المزامنة الأولية والتراكمية لـ `totalArmy`, `woundedArmy`, `trainArmy` عبر `v.armyInfo`، واجتياز بوابة الجاهزية.
- **قرار المراجعة والتحدي (Verdict)**: **REQUEST_CHANGES** مع إحالة الثغرتين التاليتين للفريق الهندسي الأساسي (Core Sync Engineers) لتطبيقهما:
  1. `core/live_memory.py:974`: استبدال إعادة التعيين بـ `.clear()` و `.update(...)` لمنع انفصال مرجع `local_queues_map`.
  2. `core/live_memory.py:821-825`: معالجة استبدال القواميس الفارغة في `woundedArmy` و `trainArmy` فور وصولها في `v.armyInfo`.

---

## 5. طريقة التحقق المستقل (Verification Method)

لتكرار التحقق والتأكد بشكل مستقل من أي طرف:
1. فحص ملف جناح الاختبارات المنشأ:
   `tests/test_live_memory_marches_army.py`
2. تشغيل أمر الاختبارات عبر سطر الأوامر:
   ```bash
   python -m unittest tests/test_live_memory_marches_army.py -v
   ```
3. تشغيل الحزمة المتكاملة:
   ```bash
   python -m unittest tests/test_live_memory.py tests/test_live_memory_marches_army.py
   ```
4. شروط الإبطال (Invalidation Conditions):
   - فشل أي اختبار من الـ 15 اختباراً.
   - حدوث تكرار لأي مسيرة في `local_queues`.
   - بقاء مسيرة محذوفة بعد وصول `REMOVE (2)`.
