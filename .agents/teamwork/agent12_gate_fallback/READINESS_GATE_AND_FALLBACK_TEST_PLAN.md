# تقرير فني مستقل: خطة الفحص التجريبي لبوابة جاهزية الذاكرة الحية والاستعلام التعويضي
**Technical Plan & Report: Empirical Verification of Live Memory Readiness Gate & Fallback Queries**

**المعرف**: REPORT-AGENT12-GATE-FALLBACK-01  
**التاريخ**: 2026-11-09T13:50:00Z  
**الوكيل**: Agent 12 (Live Gate & Fallback Tester / Empirical Challenger)  
**بيئة العمل**: `e:\osmanli` (Windows Selector Event Loop, Python 3.10+)  
**المرجع**: `ORIGINAL_REQUEST.md`, `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`, `GEMINI.md` (قاعدة 5)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostic & Rationale)

تعتمد سلامة دورة حياة البوت وقرارات المهام (البناء، التدريب، حصد الموارد، جمع التحالف، علاج المشفى، إلخ) على وجود صورة مكتملة وسليمة 100% في الذاكرة الحية (`init_data`). في المعمارية السابقة، كان البوت يبدأ تنفيذ المهام فور انتهاء المصافحة الأولية حتى لو تأخر السيرفر في بث بيانات المباني (`cityCtrl.blist`) أو الجيوش (`armyCtrl`) أو معلومات اللورد (`lordInfoCtrl`)، مما تسبب في أخطاء `KeyError` مميتة أو قرارات استراتيجية كارثية كاعتبار القلعة خالية من المباني أو القوات.

لحل ذلك، تم استحداث:
1. دالة التحقق الهيكلي الصارم `LiveMemoryEngine.is_memory_ready()` لفحص المتحكمات الستة الحرجة `CRITICAL_STARTUP_CONTROLLERS` (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`) والتأكد من عدم فراغ `blist` أو `reslist`.
2. بوابة الجاهزية غير المتزامنة `wait_for_memory_ready()` في `GateClient` و `GameConnection` مع دعم الاستعلام التعويضي التلقائي (`auto_fetch_missing=True`) لإرسال الحزم (`1001/1`, `1002/7`, `1003/1`, `1005/1`, `1004/1`, `1007/1000`).
3. اعتراض الدورة الرئيسية في `BotManager.execute_task_pipeline()` لمنع تشغيل أي مهمة إذا كانت الذاكرة غير جاهزة، وإعادة `None` مع تسجيل تحذير واضح.

**الهدف من هذا الفحص التجريبي**:
بصفتنا "Empirical Challenger"، لا نقبل أي ادعاء نظري دون تشغيل كود تجريبي حقيقي وصارم يثبت بالأدلة الملموسة:
- توقف البوابة عند نقص أي متحكم من الـ 6 أو فراغ هياكله الداخلية.
- اعتراض `execute_task_pipeline` وعودته بـ `None` بدون تنفيذ أي خطوة.
- إرسال أوامر التعويض الدقيقة وفك تعليق البوابة فور ورود الردود.
- التزام البوابة بمهلة timeout محددة دون تعليق لا نهائي.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Step-by-Step Procedure)

### الخطوة 1: فحص البوابة عند غياب أي متحكم حرج أو تلف هيكله الداخلي
- اختبار الحالات السلبية لكل متحكم على حدة:
  - غياب تام لكل من: `cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`.
  - تلف هيكلي في `cityCtrl`: `blist` فارغة `[]`، أو `reslist` فارغة `{}`.
  - تلف هيكلي في `lordInfoCtrl`: `base` مفقود أو لا يحتوي على `uid`.
  - تلف هيكلي في `armyCtrl`: غياب كل من `totalArmy`, `armyInfo`, `woundedArmy`.
- التحقق من أن `is_memory_ready()` تعيد `(False, [missing_keys])`.
- التحقق من أن `wait_for_memory_ready(auto_fetch_missing=False)` توقف التنفيذ وتعيد `False`.

### الخطوة 2: فحص اعتراض `BotManager.execute_task_pipeline()`
- إنشاء بيئة اختبار لـ `BotManager` وربطه باتصال mock يحاكي حالة عدم اكتمال الذاكرة الحية.
- استدعاء `bot.execute_task_pipeline()`.
- التحقق التجريبي من:
  1. اعتراض الدالة فوراً.
  2. تسجيل رسالة التحذير المعتمدة: `"⚠️ الذاكرة الحية غير مكتملة، تعليق تشغيل المهام للدورة القادمة..."`.
  3. عودة الدالة بقيمة `None` بدلاً من قاموس نتائج.
  4. عدم استدعاء أي مهمة من مهام الـ pipeline (مثل `step_1_city_harvest_task`).

### الخطوة 3: فحص الاستعلام التعويضي التلقائي (`auto_fetch_missing=True`)
- محاكاة غياب متحكم أو أكثر (مثل `cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `backpackCtrl`).
- التحقق من إرسال الأوامر المحددة:
  - `cityCtrl` -> `CMD 1001 / SUB 1`
  - `lordInfoCtrl` -> `CMD 1002 / SUB 7`
  - `queueCtrl` -> `CMD 1003 / SUB 1`
  - `armyCtrl` / `heroCtrl` -> `CMD 1005 / SUB 1`
  - `backpackCtrl` -> `CMD 1004 / SUB 1`
  - `local_queues` -> `CMD 1007 / SUB 1000`
- محاكاة تدفق رد السيرفر بعد تأخير زمني قصير، ودمجه في الذاكرة الحية عبر `ingest_packet`.
- التحقق من استيقاظ البوابة وفك الحظر وعودتها بـ `True`.

### الخطوة 4: فحص صرامة مهلة الانتظار (Strict Timeout & No Infinite Hang)
- تفعيل `wait_for_memory_ready(timeout=0.2, auto_fetch_missing=True)` مع تعمد حجب رد السيرفر.
- قياس الوقت المستغرق والتأكد من انقضاء المهلة وعودة البوابة بـ `False` خلال المدة المحددة بدقة دون أي تعليق للخيط أو حلقة مفرغة.

---

## 3. الأوامر والملفات المنفذة والنتيجة المتوقعة (Commands, Files & Expected Outcome)

### الملفات التي سيتم إنشاؤها واستخدامها:
1. `tests/test_gate_fallback_empirical.py`:
   ملف اختبار شامل ومركّز ينفذ سيناريوهات الفحص الأربعة، خارج مجلد `.agents/teamwork/` التزاماً بالمعايير الهيكلية للمشروع.
2. `e:\osmanli\.agents\teamwork\agent12_gate_fallback\handoff.md`:
   تقرير التسليم النهائي الشامل المكون من 5 أقسام وفق ميثاق الفريق.

### أوامر التشغيل التجريبي:
```powershell
python -m unittest tests/test_gate_fallback_empirical.py -v
python -m unittest tests/test_live_memory.py -v
```

### النتيجة المتوقعة:
- نجاح 100% لكافة الاختبارات البرمجية (`OK`).
- إثبات دقة واعتراض البوابة ومنعها للانهيارات، وجاهزيتها للعمل الميداني.
