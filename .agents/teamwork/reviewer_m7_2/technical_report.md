# تقرير التدقيق الفني والجنائي المسبق لمرحلة M7 (UX Lifecycle, Confirm Modals, Trilingual Consistency & Resource Cleanup)

**المعرف:** Reviewer M7 (Instance 2) — Adversarial & Security Reviewer  
**التاريخ والوقت:** 2026-11-02T20:38:00Z  
**المرجع القانوني والتنظيمي:** GEMINI.md (القاعدة 5 - إلزامية التقرير المسبق) و AGENTS_CONSTITUTION.md (المادة 13)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Root Cause)

في مرحلة Milestone 7، قام وكيل التطوير (`worker_m7`) بتنفيذ حزمة من الإصلاحات الهيكلية لتجربة المستخدم والأمان ودورة حياة الموارد، وتشمل:
1. **عزل مشرفي التجار (Merchant Admin Domain Isolation):** سد الثغرة الأمنية في المسار `GET /api/admin/users/{uid}/castles` (`api_server.py:1871-1891`) بحيث يمنع التاجر من استعراض قلاع وإعدادات مستخدم لا ينتمي لنطاق الدومين الخاص به، بإرجاع رمز الخطأ 403 Forbidden.
2. **استبدال نوافذ المتصفح المعطلة (Zero Blocking Dialogs):** استبدال كافة استدعاءات `window.confirm` أو `confirm(...)` بمكون مودال حديث `ActionConfirmModal.tsx` غير معطل لخيط معالجة الواجهة (Non-blocking)، ومبني عبر React Portal و Framer Motion.
3. **تطابق مفاتيح الترجمة الثلاثية بنسبة 100% (Trilingual Key Parity):** التخلص من أي مفاتيح مفقودة في `ar.json` و `en.json` و `tr.json` ومنع ظهور نصوص خام غير مترجمة.
4. **تنظيف دورة حياة الموارد (Resource Cleanup & Unmount Lifecycle):** ضمان إزالة مستمع حدث المفاتيح `keydown` (زر الهروب Escape) عند إغلاق المودال أو إلغاء تثبيته (unmount)، وتنظيف مؤقتات التحديث الدوري `setInterval` في `AdminLiveProcesses.tsx`.
5. **فحص النزاهة الجنائية (Integrity Audit):** التأكد من عدم وجود قيم اختبار وهمية مشفرة (Hardcoded test results)، أو واجهات شكلية زائفة (Dummy facades)، أو تزييف لنتائج الاختبارات.

لتأكيد هذه المخرجات مخبرياً وعدلياً، يلزم تشغيل حزم الفحص المستقلة وبناء المشروع ومراجعة الأسطر البرمجية بدقة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Execution Steps)

1. **الفحص الجنائي المكتبي (Static Code Audit):**
   - فحص كود `api_server.py` الأسطر 1871-1891 للتأكد من استدعاء `_verify_merchant_access_to_user(admin, target_user)` والتعامل مع حالة عدم وجود المستخدم (404) وتجاوز صلاحيات التاجر (403).
   - فحص شجرة كود الواجهة الأمامية `dashboard/src/` بالكامل للتأكد من عدم وجود أي استدعاءات متبقية لـ `window.confirm`، `confirm(`, `alert(`, أو `prompt(`.
   - فحص `ActionConfirmModal.tsx` للتأكد من تنظيف `removeEventListener` لحدث `keydown` وعدم تلويث DOM الخاص بـ `document.body`.
   - فحص ملفات القواميس الثلاثية `dashboard/src/locales/{ar,en,tr}.json` والتأكد من مطابقة شجرة المفاتيح وتغطيتها.

2. **تنفيذ أدوات التحقق المخبرية المستقلة (Automated Test Execution):**
   - تشغيل سكريبت فحص المرحلة 7: `python tools/verify_m7_ux_lifecycle.py`
   - التحقق من بناء الواجهة الأمامية وخلوها من أخطاء TypeScript: `powershell -Command "Set-Location dashboard; npm run build"`
   - تشغيل حزمة الاختبارات الشاملة للمشروع: `python tests/run_all_tests.py`

3. **التقييم العدائي وسيناريوهات الفشل (Adversarial Stress Testing & Attack Scenarios):**
   - اختبار سيناريو هجوم BOLA/BFLA عبر محاولة مشرف تاجر الوصول لقلاع مستخدم في دومين تاجر آخر أو مستخدم عام عبر معرف UID.
   - اختبار سيناريو النقر المتعدد أو الضغط على Escape أثناء تنفيذ عملية غير متزامنة (Pending state).
   - اختبار التوافقية البصرية في الوضعين الليلي والنهاري ومراعاة ألوان التباين و GEMINI.md Rule 2 (Simplicity & No Word Clutter).

4. **إصدار القرار النهائي والتسليم (Verdict & Handoff):**
   - صياغة تقرير التسليم `handoff.md` وفق المعايير الخمسة الإلزامية وتضمين الحكم القاطع (`APPROVE` أو `REQUEST_CHANGES`).

---

## 3. الأوامر والملفات والنتائج المتوقعة (Detailed Commands & Expected Results)

| # | الأمر المزمع تنفيذه | الغرض والهدف | النتيجة المتوقعة |
|---|----------------------|--------------|-------------------|
| 1 | `python tools/verify_m7_ux_lifecycle.py` | تشغيل سكريبت فحص معايير M7 (غياب المودالات المعطلة، تطابق الترجمة 100%، عزل التاجر، تنظيف الموارد، التباين) | نجاح 22/22 فحص (100% PASS) |
| 2 | `powershell -Command "Set-Location dashboard; npm run build"` | التحقق من صحة أنواع TypeScript وبناء حزمة الإنتاج عبر Vite | كود خروج 0، 0 أخطاء تايب سكريبت، زمن بناء سريع (< 3 ثواني) |
| 3 | `python tests/run_all_tests.py` | تشغيل جناح الاختبارات الشامل لجميع المراحل المنجزة (M1-M7) والتأكد من عدم وجود انحدار (No Regressions) | نجاح 30/30 فحص (100% PASS) |

---
**الامتثال:** العمل محلي بالكامل داخل بيئة `e:\osmanli`. لا يوجد أي رفع أو نشر أو اتصال خارجي عملاً بـ GEMINI.md Rule 4 و AGENTS_CONSTITUTION.md Rule 13.
