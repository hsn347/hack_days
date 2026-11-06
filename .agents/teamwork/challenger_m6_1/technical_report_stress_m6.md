# تقرير فني مسبق: اختبار الإجهاد التجريبي لقيود التصفح وحدود الصفحات (Milestone 6)

**التاريخ**: 2026-11-02  
**المهمة**: Milestone 6 Pagination & Boundaries Stress Test (Challenger M6 Instance 1)  
**الحالة**: مسودة ما قبل التنفيذ (Pre-Execution Technical Report per GEMINI.md Rule 5)  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

تم تكليفنا بدور **Empirical Challenger (Critic / Specialist)** للتحقق الصارم والمستقل من مخرجات العامل `worker_m6` الخاصة بـ:
1. التصفح من جانب العميل (Client-side Pagination) وسلوك الحدود القصوى والدنيا.
2. التبديل الديناميكي لأحجام الصفحات (Dynamic Page Size Switching: 10, 25, 50, 100).
3. إعادة الضبط التلقائي إلى الصفحة الأولى عند تغير محددات البحث أو الفرز أو حجم الصفحة (Reset-to-page-1 behavior upon filter/search/pageSize changes).
4. سلوك الحدود الحرجة للبيانات:
   - 0 عنصر (Empty State).
   - 1 عنصر (Single item boundary).
   - 25 عنصر (Exact single page boundary عند الحجم الافتراضي).
   - 26 عنصر (Crossing threshold: split into 2 pages).
   - 1,000 عنصر (Large scale load: 40 pages at 25, 100 pages at 10, 10 pages at 100).
5. مطابقة معايير GEMINI.md Rule 2 (Simplicity Above All, No Word Clutter, Fast & Responsive snappy UI).
6. التأكد من خلو المشروع من أي أخطاء تجميعية في الواجهة الأمامية (`npm run build`) واجتياز كافة اختبارات المنصة (`verify_m6_admin_scalability.py` و `tests/run_all_tests.py`).

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Implementation Plan)

1. **كتابة أداة اختبار إجهاد تجريبية شاملة (`tools/stress_m6_pagination.py`)**:
   - اختبارات الحدود الصارمة (Boundary Tests): 0، 1، 25، 26، 1000 عنصر، والتحقق الحسابي من:
     * `totalPages = max(1, ceil(totalItems / pageSize))`
     * `validPage = min(max(1, currentPage), totalPages)`
     * `startIndex = (validPage - 1) * pageSize`
     * `endIndex = min(startIndex + pageSize, totalItems)`
     * عدم تكرار أي عنصر بين الصفحات وعدم فقدان أي عنصر (`set(union of all pages) == set(all items)`).
     * صحة طول الشريحة المعروضة لكل صفحة.
   - اختبارات التبديل الديناميكي لحجم الصفحة (Page Size Switching):
     * الانتقال بين الأحجام [10, 25, 50, 100] وملاحظة إعادة ضبط المؤشر للصفحة الأولى والتأكد من ملاءمة الشرائح.
   - اختبارات محددات البحث والفرز (Filter & Search Resets):
     * التحقق من الـ `useEffect` في `Admin.tsx` الذي يستمع لـ `[debouncedSearch, filterPending, sortByLeastDays, pageSize]`.
   - اختبارات القيم الشاذة والمتطرفة (Adversarial / Out-of-bounds inputs):
     * طلب أرقام صفحات سالبة (مثل -5)، صفر (0)، أو صفحات تفوق الحد الأقصى (مثل 99999) والتأكد من الكبح الآمن (Clamping).
   - التحقق من معايير GEMINI.md Rule 2:
     * التدقيق الثابت (Static AST / Code Inspection) لخلو واجهة التصفح من حشو العبارات والتأكد من استخدام نصوص موجزة ذات دلالة واضحة ("1–25 / 120"، "عرض:"، "1 / 5").
   - محاكاة أداء الذاكرة والوقت تحت حمولة 1,000 مستخدم للتأكد من زمن استجابة دون الميلي ثانية وعدم وجود تسريب أو بطء في الحساب.

2. **تنفيذ أوامر التحقق التجريبي (Empirical Execution)**:
   - تشغيل `python tools/stress_m6_pagination.py` وتسجيل المخرجات بدقة.
   - تشغيل `python tools/verify_m6_admin_scalability.py`.
   - تشغيل `powershell -Command "Set-Location dashboard; npm run build"` للتحقق من سلامة البناء وخلو TypeScript من أي أخطاء.
   - تشغيل `python tests/run_all_tests.py` لضمان عدم حدوث أي انحدار (regression) في النظام.

3. **توثيق النتائج وإصدار التقرير النهائي (`handoff.md`)**:
   - كتابة تقرير تسليم خماسي الأقسام (Observation, Logic Chain, Caveats, Conclusion, Verification Method) مع قرار نهائي صريح (APPROVE / REQUEST_CHANGES).

---

## 3. الملفات والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Files, Lines & Commands)

| الملف / الأمر | الإجراء المطلوب | النتيجة المتوقعة |
|---|---|---|
| `tools/stress_m6_pagination.py` | إنشاء أداة اختبار إجهاد مخصصة بـ 8 محاور تجريبية | ملف بايثون متكامل يقوم بفحص جميع حالات الحدود والتبديل والعزل |
| `python tools/stress_m6_pagination.py` | تشغيل أداة اختبار الإجهاد | اجتياز 100% من اختبارات الإجهاد (جميع حالات الحدود 0, 1, 25, 26, 1000 واختبارات Clamping وGEMINI Rule 2) |
| `python tools/verify_m6_admin_scalability.py` | تشغيل فحص التحقق الرسمي لـ M6 | اجتياز 38/38 فحص بنجاح 100% |
| `powershell -Command "Set-Location dashboard; npm run build"` | بناء حزمة الإنتاج للوحة التحكم | اكتمال البناء بنجاح (Exit code 0) دون أي أخطاء تجميعية |
| `python tests/run_all_tests.py` | تشغيل حزمة اختبارات المنصة الكاملة | اجتياز 30/30 فحص عبر جميع الطبقات الأربع بنجاح تام |
| `e:\osmanli\.agents\teamwork\challenger_m6_1\handoff.md` | إعداد تقرير التسليم النهائي | تقرير مفصل يحدد حكم الاعتماد النهائي وموجز الاختبارات |
