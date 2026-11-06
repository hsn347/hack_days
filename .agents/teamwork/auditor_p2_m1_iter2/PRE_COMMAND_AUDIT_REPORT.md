# تقرير فني مسبق لأوامر التحقق الجنائي (Pre-Command Forensic Audit Report)
**وفقاً للبند 5 من دستور وتفضيلات المستخدم الدائمة (GEMINI.md Rule 5 — Strict File-Report-First Rule)**

**التاريخ والتوقيت:** 2026-11-02T22:42:00Z  
**الوكيل:** `auditor_p2_m1_iter2` (Forensic Integrity Auditor)  
**المهمة:** Milestone 1 Iteration 2 — التحقق الجنائي المستقل من التعديلات المنفذة في `tools/measure_baseline.py` والامتثال التام للحظر الدستوري.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostic Rationale)

1. **التحقق من حل العيوب البرمجية لواجهة سطر الأوامر (CLI Options)**:
   - قام `worker_p2_m1_iter2` بتعديل `tools/measure_baseline.py` لدعم `--duration`, `--workers`, `--no-load`, و `--skip-load`.
   - كمدقق جنائي مستقل، يُطلب التحقق ميدانياً وتنفيذياً من أن هذه الوسائط تعمل بصورة حقيقية وأصيلة دون محاكاة زائفة (Facades/Mocks/Stubs) وأن تخطي الحمل لا يسبب انهيار البرنامج أو تزييف البيانات.

2. **التحقق من الامتثال الصارم للحظر الدستوري (Strict Prohibition Compliance)**:
   - تنص وثيقة `ORIGINAL_REQUEST.md` و `AGENTS_CONSTITUTION.md` على الحظر القطعي لأي لمس أو تعديل أو فتح أو قراءة للملفات الثلاثة:
     `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
   - يلزم فحص حالة Git وأختام التعديل الزمني (File Timestamps) والتأكد من سلامة المعمارية (AST Integrity) من الخارج دون فتح الملفات أو تعديلها.

3. **التحقق من عدم وجود اتصالات خارجية أو رفع للسيرفر (Zero Network / Zero Deploy)**:
   - التحقق من عدم وجود أي طلبات شبكية لخدمات اللعبة أو محاولات نشر خارجي.

4. **التحقق من اجتياز حزمة الاختبارات الشاملة (Unified Test Suite)**:
   - تشغيل `python tests/run_all_tests.py` للتأكد من نجاح 30/30 اختبار دون أي تراجع.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Audit Logic & Verification Steps)

1. **الخطوة الأولى: فحص سلامة وتاريخ الملفات المحظورة ومستودع Git**:
   - تنفيذ أمر PowerShell لفحص حالة `git status --porcelain` والتأكد من عدم وجود أي تعديلات على الملفات المحظورة.
   - فحص تواريخ آخر تعديل للملفات المحظورة عبر `Get-ItemProperty`.
   - فحص شجرة الـ AST للملفات المحظورة عبر بايثون خارجياً للتأكد من سلامة الكود النحوية دون قراءة محتواه للمدقق أو لمسه.

2. **الخطوة الثانية: التحقق العملي من وسائط سطر الأوامر وأداة القياس**:
   - تشغيل `python tools/measure_baseline.py --duration 1` للتأكد من قبول مدة العينة الزمنية.
   - تشغيل `python tools/measure_baseline.py --workers 5` للتأكد من تطبيق الحمل بعدد خيوط مخصص (5 خيوط).
   - تشغيل `python tools/measure_baseline.py --no-load` للتأكد من التخطي الفعلي للمرحلة الثالثة وتوليد تقرير سليم.
   - تشغيل `python tools/measure_baseline.py --skip-load` للتأكد من مطابقة الاسم الرديف.
   - تشغيل `python tools/measure_baseline.py --tag prefix` للتأكد من التشغيل القياسي وتوليد ملفات خط الأساس.

3. **الخطوة الثالثة: التحقق من حزمة الاختبارات الكاملة**:
   - تشغيل `python tests/run_all_tests.py`.
   - تشغيل `python tools/test_monitor_stress.py` للتحقق من صمود أدوات المراقبة.

4. **الخطوة الرابعة: الفحص الجنائي لملفات المخرجات والتقارير**:
   - فحص ملفات `tools/baseline_metrics_prefix.json` و `tools/BASELINE_METRICS_PREFIX.md` والتأكد من عدم احتوائها على قيم مصطنعة.

---

## 3. الأوامر والملفات المجدولة للتنفيذ والنتائج المتوقعة (Commands & Expected Outputs)

### الأمر 1: فحص حالة Git وتواريخ الملفات المحظورة
- **الأمر:**
  ```powershell
  git status --porcelain tools/measure_baseline.py game_client.py core/onemt_auth.py core/onemt_bot.py ; Get-Item game_client.py, core/onemt_auth.py, core/onemt_bot.py | Select-Object Name, LastWriteTime, Length
  ```
- **النتيجة المتوقعة:**
  - `tools/measure_baseline.py` يظهر كملف معدل (`M`).
  - الملفات المحظورة الثلاثة لا تظهر في حالة Git بتاتاً وتواريخ تعديلها سابقة لبدء المهمة.

### الأمر 2: التحقق من صحة وبناء الـ AST للملفات المحظورة دون قراءتها
- **الأمر:**
  ```powershell
  python -c "import ast; [ast.parse(open(f, 'rb').read()) for f in ['game_client.py', 'core/onemt_auth.py', 'core/onemt_bot.py']]; print('FORBIDDEN_FILES_AST_VALID')"
  ```
- **النتيجة المتوقعة:** طباعة `FORBIDDEN_FILES_AST_VALID` بنجاح دون أخطاء نحوية.

### الأمر 3: فحص خيارات `--duration` و `--workers` و `--no-load` و `--skip-load`
- **الأوامر:**
  ```powershell
  python tools/measure_baseline.py --duration 1
  python tools/measure_baseline.py --workers 5
  python tools/measure_baseline.py --no-load
  python tools/measure_baseline.py --skip-load
  ```
- **النتيجة المتوقعة:** انتهاء جميع الأوامر بنجاح بكود خروج 0 وظهور رسائل التشغيل المطابقة للمواصفات.

### الأمر 4: تشغيل خط الأساس الشامل وتحديث التقرير
- **الأمر:**
  ```powershell
  python tools/measure_baseline.py --tag prefix
  ```
- **النتيجة المتوقعة:** اكتمال المراحل الأربع بنجاح وتحديث التقارير وإنهاء بكود 0.

### الأمر 5: تشغيل حزمة الاختبارات الشاملة المكونة من 4 طبقات
- **الأمر:**
  ```powershell
  python tests/run_all_tests.py
  ```
- **النتيجة المتوقعة:** نجاح 30 من 30 اختبار بنسبة 100% بكود خروج 0.

### الأمر 6: تشغيل حزمة اختبارات إجهاد المراقبة
- **الأمر:**
  ```powershell
  python tools/test_monitor_stress.py
  ```
- **النتيجة المتوقعة:** نجاح 6 من 6 أجنحة اختبار بنسبة 100% بكود خروج 0.
