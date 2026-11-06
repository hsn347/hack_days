# تقرير فني مستقل: خطة الفحص التجريبي والتحقق الميداني للأدوات والمخرجات (Milestone 1 — Challenger 2)

**التاريخ والوقت:** 2026-11-03T01:26:00Z  
**الوكيل:** Challenger 2 (`challenger_p2_m1_2`)  
**المهمة:** التحقق التجريبي الصارم من صحة المخطط (Schema)، الخيارات السطرية (CLI Options)، والآثار الجانبية (Side Effects) لأداة ومخرجات خط الأساس M1.  
**المرجع الإلزامي:** قاعدة GEMINI.md رقم 5 (إلزامية إرفاق ملف تقرير مستقل قبل أي أمر).

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

قام وكيل التنفيذ `worker_p2_m1` بتسليم المرحلة الأولى (M1 / R4) متضمنة أداة القياس `tools/measure_baseline.py` والملفين الناتجين:
- `tools/baseline_metrics_prefix.json`
- `tools/BASELINE_METRICS_PREFIX.md`

بصفتي المدقق التجريبي المستقل (Empirical Challenger)، يتطلب دوري عدم الاعتماد على ادعاءات الوكيل أو التقارير النصية، بل إجراء التحقق العملي والمباشر عبر تنفيذ الاختبارات بأنفسنا لإثبات أو دحض التالي:
1. **التحقق من الخيارات السطرية (CLI Options):**
   وفقاً لتكليف Challenger 2، يجب فحص الخيارات: `--tag`, `--duration`, `--workers`, `--no-load`.
   الفحص المبدئي للكود أظهر أن `argparse` في `measure_baseline.py` يحتوي فقط على:
   - `--tag`
   - `--output-json`
   - `--output-md`
   - `--skip-load` (غير ممررة وغير مفعلة داخل دالة التنفيذ).
   ولا توجد خيارات `--duration` أو `--workers` أو `--no-load`. يجب إثبات هذا القصور تجريبياً بتنفيذ الأوامر وتسجيل أكواد الخطأ Verbatim.
2. **التحقق من صحة المخطط واكتماله وإمكانية إعادة التوليد (Schema & Reproducibility):**
   التأكد من أن ملف JSON صالح، يحتوي على كافة الحقول الإلزامية دون أي حقول ناقصة أو أصفار وهمية، ومطابقته مع ملف Markdown.
3. **التأكد من عدم وجود أي آثار جانبية ضارة (Zero Side Effects):**
   حساب البصمة الرقمية (Hash / MD5) لقاعدة البيانات `database/castles.db` قبل وبعد تشغيل أداة القياس للتأكد قطيعاً من عدم التعديل على أي سجل.
4. **التأكد التام من عدم لمس الملفات المحظورة:**
   فحص حالة Git لملفات `game_client.py` و `core/onemt_auth.py` و `core/onemt_bot.py`.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Execution Steps)

1. **الخطوة الأولى: فحص سلامة وتماسك قاعدة البيانات قبل التشغيل:**
   - استخراج بصمة MD5 وحجم ملف `database/castles.db`.
   - فحص وجود ملفات WAL أو SHM.

2. **الخطوة الثانية: اختبار خيارات سطر الأوامر (CLI Options Stress-Testing):**
   - اختبار تشغيل الأداة مع `--tag test_cli`.
   - اختبار تشغيل الأداة مع `--duration 3` وملاحظة استجابة `argparse`.
   - اختبار تشغيل الأداة مع `--workers 5` وملاحظة استجابة `argparse`.
   - اختبار تشغيل الأداة مع `--no-load` وملاحظة استجابة `argparse`.
   - اختبار خيار `--skip-load` للتأكد هل يتخطى مرحلة الحمل النشط فعلياً أم يتجاهله الكود.

3. **الخطوة الثالثة: التحقق من عدم تعديل قاعدة البيانات بعد التشغيل:**
   - إعادة استخراج بصمة MD5 وحجم ملف `database/castles.db` ومقارنتهما مع القيمة السابقة للتأكد من انعدام الطفرات (Zero Mutations).

4. **الخطوة الرابعة: فحص سلامة الملفات المحظورة:**
   - فحص `git status` و `git diff` للملفات المحظورة الثلاثة للتأكد بنسبة 100% من عدم المساس بها.

5. **الخطوة الخامسة: فحص بنية ومخطط ملفات القياس المنشأة:**
   - تشغيل سكربت بايثون تجريبي مستقل للتحقق من JSON Schema وجميع المفاتيح الحسابية.

---

## 3. الأوامر والملفات والنتائج المتوقعة بالتفصيل (Detailed Commands & Expected Outcomes)

1. **أمر فحص بصمة قاعدة البيانات الأولية:**
   - **الأمر:** `Get-FileHash -Algorithm MD5 database\castles.db`
   - **النتيجة المتوقعة:** طباعة بصمة الهاش الأولية.

2. **أمر اختبار خيار `--tag` ومسارات المخرجات المخصصة:**
   - **الأمر:** `python tools\measure_baseline.py --tag test_cli --output-json .agents\teamwork\challenger_p2_m1_2\test_cli.json --output-md .agents\teamwork\challenger_p2_m1_2\TEST_CLI.md`
   - **النتيجة المتوقعة:** نجاح التنفيذ وخروج بكود 0 مع توليد الملفين في مجلد الوكيل دون تلويث المستودع.

3. **أوامر اختبار الخيارات الناقصة أو غير المدعومة:**
   - **الأمر:** `python tools\measure_baseline.py --duration 3`
   - **النتيجة المتوقعة:** فشل `argparse: error: unrecognized arguments: --duration 3` (Exit code 2).
   - **الأمر:** `python tools\measure_baseline.py --workers 5`
   - **النتيجة المتوقعة:** فشل `argparse: error: unrecognized arguments: --workers 5` (Exit code 2).
   - **الأمر:** `python tools\measure_baseline.py --no-load`
   - **النتيجة المتوقعة:** فشل `argparse: error: unrecognized arguments: --no-load` (Exit code 2).
   - **الأمر:** `python tools\measure_baseline.py --skip-load`
   - **النتيجة المتوقعة:** طباعة مخرجات المرحلة الثالثة (Active Workload Load Test) مما يثبت تجريبياً أن الكود يتجاهل الراية تماماً ولا يطبق تخطي الحمل النشط!

4. **أمر إعادة فحص بصمة قاعدة البيانات:**
   - **الأمر:** `Get-FileHash -Algorithm MD5 database\castles.db`
   - **النتيجة المتوقعة:** تطابق الهاش بنسبة 100% مع البصمة الأولية.

5. **أمر فحص الملفات المحظورة عبر Git:**
   - **الأمر:** `git status --porcelain game_client.py core/onemt_auth.py core/onemt_bot.py`
   - **النتيجة المتوقعة:** مخرجات فارغة تؤكد عدم تعديل أي ملف محظور.

6. **أمر فحص جناح الاختبارات الكامل للتأكد من عدم وجود أي كسر تراجعي:**
   - **الأمر:** `python tests\run_all_tests.py`
   - **النتيجة المتوقعة:** نجاح كافة الاختبارات 30/30 (100% Pass).
