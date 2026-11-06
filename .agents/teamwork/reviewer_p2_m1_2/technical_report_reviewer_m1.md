# تقرير فني مسبق لأوامر التحقق والاختبار (Reviewer Verification Execution Plan)

**التاريخ والوقت:** 2026-11-02T22:30:00Z  
**الوكيل:** `reviewer_p2_m1_2` (teamwork_reviewer / critic)  
**المهمة:** التحقق المستقل والمعادي للمرحلة الأولى (Milestone 1 Baseline Measurement & Pre-Fix Metrics)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
بموجب تكليف المشرف العام وتعليمات `AGENTS_CONSTITUTION.md` وقواعد `GEMINI.md` (البند 5 الخاص بإلزامية التقرير المسبق):
يتعين على المراجع المستقل التحقق الحقيقي من المخرجات عبر تنفيذ الأوامر بأنفسنا وعدم الاكتفاء بالثقة العمياء في تقرير العامل (`worker_p2_m1`):
1. فحص سبب ظهور `game_client.py` بحالة `M` في الـ git status ومعرفة توقيت تعديله وتاريخ التغيير وما إذا كان قد عُدل بواسطة العامل الحالي `worker_p2_m1` أم كان معدلاً مسبقاً قبل بدء المرحلة M1.
2. التحقق من سلامة تنفيذ سكربت قياس خط الأساس `tools/measure_baseline.py` وخروجه بكود 0 دون أي استثناءات، والتحقق من قياسات الذاكرة، المقابض، الخيوط، وقاعدة البيانات.
3. التحقق من نجاح كافة اختبارات المنصة الموحدة الـ 30 في `tests/run_all_tests.py` لضمان عدم حدوث أي تراجع أو كسر في بيئة العمل.
4. التحقق الجنائي الصارم من عدم لمس أو فتح أو تعديل الملفات المحظورة الثلاثة: `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py` خلال هذه الجولة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)
1. **الخطوة 1: فحص تاريخ وتوقيت تعديل `game_client.py`**:
   - فحص `git diff --stat game_client.py` أو تاريخ التعديل لمعرفة هل تم لمسه بواسطة Worker M1.
2. **الخطوة 2: تشغيل سكربت خط الأساس `measure_baseline.py`**:
   - تنفيذ `python tools/measure_baseline.py --tag prefix`.
   - رصد الخرج والتأكد من خروج السكربت بكود 0، وتحديث ملفات `tools/baseline_metrics_prefix.json` و `tools/BASELINE_METRICS_PREFIX.md`.
3. **الخطوة 3: تشغيل منصة الاختبارات الموحدة الـ 30**:
   - تنفيذ `python tests/run_all_tests.py`.
   - التأكد من اجتياز كافة الاختبارات بنسبة 100% (30/30 Pass).

---

## 3. الأوامر والملفات والنتائج المتوقعة بالتفصيل (Commands, Files & Expected Outputs)

### الأمر 1: فحص التعديلات في `game_client.py` وتوقيتها
- **الأمر:** `git log -n 5 --oneline` ثم فحص تاريخ ملف `game_client.py`.
- **النتيجة المتوقعة:** توضيح سياق حالة الملف في المستودع.

### الأمر 2: تشغيل أداة قياس خط الأساس
- **الأمر:** `python tools/measure_baseline.py --tag prefix`
- **الملفات المتأثرة:** `tools/measure_baseline.py` (قراءة وتشغيل)، `tools/baseline_metrics_prefix.json` (كتابة)، `tools/BASELINE_METRICS_PREFIX.md` (كتابة).
- **النتيجة المتوقعة:** كود خروج 0 (Exit Code 0).

### الأمر 3: تشغيل جناح الاختبارات الموحد
- **الأمر:** `python tests/run_all_tests.py`
- **النتيجة المتوقعة:** كود خروج 0، 30/30 نجاح.
