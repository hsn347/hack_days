# تقرير الفحص والتحقق الفني المسبق: مزامنة المسيرات والجيوش والذاكرة الحية
**Pre-Execution QA Verification & Adversarial Test Plan: Marches & Army State Synchronization**

**التاريخ**: 2026-11-09T13:50:00Z  
**الوكيل**: Agent 16 (Marches & Army Live QA Agent)  
**الأدوار**: Reviewer & Adversarial Critic  
**المرجعية**: `ORIGINAL_REQUEST.md`, `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`, `LUA_PROTOCOL_SPEC.md`, `armyCtrl_dec.lua`, `kingdomMapCtrl_dec.lua`, `core/live_memory.py`, `game_client.py`  
**الالتزام بالقواعد**: متوافق تماماً مع بنود `GEMINI.md` (البند 5: تقرير فني مستقل مسبق).

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause & Objectives)

تتطلب معمارية الذاكرة الحية (Live State Memory) في بوت حرب الممالك العثمانية مزامنة فورية ومطابقة 100% مع بروتوكول اللعبة المرجعي في Lua لمسيرات الخريطة (`local_queues`) وتحديثات الجيوش وقوات القلعة (`armyCtrl`):
1. **طوابير ومسيرات الخريطة (`local_queues` / `NOTIFY_LOCAL_QUEUE_SYNC` - كود 202)**:
   - يجب أن يتعامل المحرك مع الإشعارات الفرعية لـ `gQueueSyncMsgType`:
     - `ADD = 1`: إضافة خط مسيرة جديد فور انطلاقه.
     - `REMOVE = 2`: حذف المسيرة فور عودتها للقلعة أو وصولها وانتهاء مهمتها.
     - `UPDATE = 3`: تحديث إحداثيات أو سرعة أو حالة المسيرة أثناء السير.
     - `ADD_ALL = 4`: مزامنة شاملة لكافة مسيرات اللاعب.
     - `REMOVE_ALL = 5`: مسح كافة المسيرات عند تسجيل الخروج أو تبديل السيرفر.
   - **الهدف الحرج**: ضمان عدم وجود أي تكرار (`Zero Duplicates`) في `local_queues` وعدم بقاء أي مسيرة منتهية دون حذف (`Zero Missed Prunings`).
2. **تحديثات الجيوش (`armyCtrl` / `v.armyInfo` - كود 15)**:
   - يجب أن ينعكس إشعار `NOTIFY_ARMY` فوراً على `totalArmy` (الجيش المتاح داخل القلعة للدفاع والمسيرات)، و `woundedArmy` (الجرحى في المشفى)، و `trainArmy` (القوات قيد التدريب في الثكنات)، و `singleTrainAddInfo` و `compileLimit`.
   - **فحص الثغرات الحرجة (Adversarial Stress Testing)**: فحص سلوك `smart_deep_merge` عند تفريغ المشفى (تحول `woundedArmy` إلى فارغ `{}`) أو انتهاء تدريب الفوج (تحول `trainArmy` إلى فارغ)، للتأكد هل يتم مسح الجرحى والمتدربين أم تظل البيانات عالقة بسبب الدمج التكراري.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Execution Steps)

### الخطوة 1: بناء جناح اختبارات مستقل ومحكم (`tests/test_live_memory_marches_army.py`)
كتابة ملف اختبارات متكامل وفق معايير `unittest` يغطي السيناريوهات التالية:
1. **فئة اختبارات المسيرات (`TestMarchesQueueSync`)**:
   - `test_local_queue_sync_add_single_and_multiple`: إضافة مسيرات مختلفة (جمع موارد، هجوم وحش، حشد).
   - `test_local_queue_sync_update_status_and_target`: تحديث بيانات المسيرة (تغير الحالة والوجهة والوقت).
   - `test_local_queue_sync_remove_on_arrival`: حذف المسيرة بعد عودتها والتحقق من نظافة القائمة.
   - `test_local_queue_sync_zero_duplicates_on_duplicate_add`: إرسال حزم ADD متكررة لنفس المعرف والتأكد من عدم تكراره.
   - `test_local_queue_sync_add_all_and_remove_all`: فحص استبدال القائمة بالكامل ومسحها بالكامل.
   - `test_local_queue_sync_id_types_string_and_int`: فحص استيعاب المعرفات النصية والرقمية (`id: 123` مقابل `id: "123"`).
   - `test_local_queue_sync_cow_and_concurrency`: فحص أمان قراءة الذاكرة أثناء تحديث المسيرات بالتزامن.
   - `test_local_queue_sync_reference_consistency_with_connection`: فحص هل مرجع `conn.local_queues_map` ينفصل عن `memory_engine.local_queues_map` عند تنفيذ `ADD_ALL`.

2. **فئة اختبارات الجيوش (`TestArmyStateSync`)**:
   - `test_army_sync_initial_population`: تهيئة بيانات الجيوش الأولية والتحقق من وجود الحقول الأساسية.
   - `test_army_sync_v_army_info_full_payload`: تمرير حزمة `NOTIFY_ARMY` تحتوي على `v.armyInfo` وتدقيق تحديث `totalArmy`, `woundedArmy`, `trainArmy`.
   - `test_army_sync_delta_troop_counts`: زيادة ونقصان تعداد الجنود في الثكنات والمشفى.
   - `test_army_sync_empty_wounded_and_train_adversarial`: **اختبار الخصم الحرج** — فحص سلوك شفاء كافة الجرحى وانتهاء كافة التدريبات، هل يتم مسحهم أم يبقون عالقين.
   - `test_army_sync_compile_limit_and_tools`: فحص تحديث الحد الأقصى للفيالق وتفاصيل أدوات التدريب.
   - `test_army_sync_is_memory_ready_gate`: التحقق من أن بوابة الجاهزية `is_memory_ready` تتحقق من سلامة `armyCtrl`.

### الخطوة 2: تشغيل الاختبارات برمجياً عبر بايثون
تشغيل الاختبارات عبر:
`python -m unittest tests/test_live_memory_marches_army.py -v`

### الخطوة 3: التوثيق والاعتماد
تسجيل كافة النتائج والملاحظات وسلسلة الاستدلال والثغرات المكتشفة في:
`e:\osmanli\.agents\teamwork\agent16_marches_army\handoff.md`

---

## 3. تفاصيل الملفات والسطور والأوامر المتوقع تنفيذها (Command & File Manifest)

| الملف / الأمر | نوع الإجراء | الوصف والنتيجة المتوقعة |
|---|---|---|
| `tests/test_live_memory_marches_army.py` | إنشاء ملف اختبار جديد (`write_file`) | كتابة جناح اختبارات شامل للمسيرات والجيوش يغطي كافة متطلبات التحقق والمحاكاة التنافسية. |
| `python -m unittest tests/test_live_memory_marches_army.py -v` | تشغيل أمر محلي (`run_command`) | تنفيذ الفحوصات والتحقق من اجتياز حالات الاختبار وكشف أي قصور في سلوك الدمج. |
| `e:\osmanli\.agents\teamwork\agent16_marches_army\handoff.md` | إنشاء ملف تقرير التسليم النهائي | توثيق النتائج وفق المكونات الخمسة الإلزامية (الملاحظات، سلسلة المنطق، المحاذير، الاستنتاج، طريقة التحقق). |

---
**الالتزام الصارم**:
- لا تعديل على أي ملفات كود تنفيذية في المشروع (Reviewer Only).
- لا يوجد أي اتصال بخوادم خارجية أو نشر شبكي (Local Workspace Only).
- التعديل والكتابة حصراً عبر الأدوات الرسمية (`write_file`, `edit_file`).