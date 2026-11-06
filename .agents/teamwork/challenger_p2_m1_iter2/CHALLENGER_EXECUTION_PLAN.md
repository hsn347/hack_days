# CHALLENGER EMPIRICAL VERIFICATION PLAN & TECHNICAL REPORT
**Iteration**: Milestone 1 Iteration 2 (CLI Options & Load Controls)  
**Agent**: `challenger_p2_m1_iter2`  
**Working Directory**: `e:\osmanli\.agents\teamwork\challenger_p2_m1_iter2\`  
**Date**: 2026-11-02T22:42:00Z  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Objective)

في التكرار الأول (Iteration 1)، تم اكتشاف العيوب التالية في أداة القياس `tools/measure_baseline.py`:
- فشل تمرير المعاملات التالية عبر سطر الأوامر (CLI): `--duration`, `--workers`, `--no-load` مع ظهور الخطأ `unrecognized arguments`.
- تجاهل المعامل `--skip-load` داخل دالة `main()`.

قام العامل (`worker_p2_m1_iter2`) بتعديل `tools/measure_baseline.py` لدعم جميع هذه المعاملات وتوصيلها إلى دالة القياس الرئيسية `run_full_baseline_measurement`.

بصفتي المدقق والمشكك التجريبي (Empirical Challenger):
- يُمنع قبول ادعاءات العامل أو سجلاته دون إعادة التحقق والتنفيذ المستقل.
- يجب تشغيل جميع السيناريوهات تجريبياً والتحقق من المخرجات، وحالة قاعدة البيانات، والملفات المحظورة، وحزمة الاختبارات الكاملة (30/30).

---

## 2. المنطق والخطوات التجريبية التي سيتم تطبيقها (Empirical Verification Steps)

1. **التحقق من حالة قاعدة البيانات والملفات المحظورة قبل البدء**:
   - فحص بصمة MD5 وتاريخ تعديل `database/castles.db`.
   - فحص تواريخ تعديل الملفات المحظورة: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
2. **اختبار المعامل `--duration 1`**:
   - التحقق من أن قياس Idle CPU يستغرق ثانية واحدة بدلاً من 2.5 ثانية.
   - التحقق من كود الخروج (Exit Code 0).
3. **اختبار المعامل `--workers 5`**:
   - التحقق من تشغيل 5 عمال تزامنيين ومعالجة 1875 سجلاً (5 * 25 * 15).
   - التحقق من كود الخروج (Exit Code 0).
4. **اختبار المعامل `--no-load`**:
   - التحقق من تخطي المرحلة الثالثة (Phase 3) كلياً دون تنفيذ استعلامات أو عمليات تكرار.
   - التحقق من بنية كائن الحمل (Skipped = True، 0 سجلات).
5. **اختبار المعامل `--skip-load`**:
   - التحقق من أنه يعمل كاسم بديل (alias) متطابق مع `--no-load`.
6. **اختبار المعامل `--tag prefix` (التشغيل الافتراضي المكتمل)**:
   - التحقق من توليد ملفات القياس المعتمدة: `tools/baseline_metrics_prefix.json` و `tools/BASELINE_METRICS_PREFIX.md`.
7. **التحقق من سلامة قاعدة البيانات بعد الاختبارات**:
   - إعادة فحص MD5 لـ `database/castles.db` للتأكد من عدم حدوث أي تعديل أو تلف.
8. **التحقق من حزمة الاختبارات الكاملة**:
   - تشغيل `python tests/run_all_tests.py` والتأكد من نجاح 30/30 اختباراً بنسبة 100%.
9. **اتخاذ القرار النهائي (APPROVE / REQUEST_CHANGES)** وكتابة `handoff.md` وإرسال الرسالة إلى المشرف.

---

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Detailed Commands & Expected Results)

| # | الأمر (Command) | الهدف | النتيجة المتوقعة (Expected Output / Result) |
|---|---|---|---|
| 1 | `Get-FileHash database/castles.db -Algorithm MD5` | التأكد من بصمة قاعدة البيانات | مطابقة التجزئة وعدم التعديل |
| 2 | `python tools/measure_baseline.py --duration 1` | التحقق من مدة القياس 1 ثانية | `Sampling 1.0 seconds`، خروج 0 |
| 3 | `python tools/measure_baseline.py --workers 5` | التحقق من تشغيل 5 عمال | `5 Concurrent Simulation Workers`، `1875 in ...s`، خروج 0 |
| 4 | `python tools/measure_baseline.py --no-load` | التحقق من تخطي مرحلة الحمل | `Skipping Active Workload Load Test`، خروج 0 |
| 5 | `python tools/measure_baseline.py --skip-load` | التحقق من عمل الاسم البديل | `Skipping Active Workload Load Test`، خروج 0 |
| 6 | `python tools/measure_baseline.py --tag prefix` | إعادة إنشاء التقارير الرسمية | توليد ملفات JSON و MD بنجاح، خروج 0 |
| 7 | `Get-FileHash database/castles.db -Algorithm MD5` | إعادة فحص قاعدة البيانات | التجزئة مطابقة تماماً للتجزئة الأولية |
| 8 | `python tests/run_all_tests.py` | تشغيل كافة اختبارات المشروع | `30 passed, 0 failed` بنسبة 100% |
