# تقرير فني مسبق لإجراءات فحص وتدقيق المرحلة 3
### Technical Execution Report — Forensic Verification of Milestone 3

**التاريخ:** 2026-11-02  
**المرجع:** دستور الوكلاء `AGENTS_CONSTITUTION.md` وقواعد `GEMINI.md` (البند 5: إلزامية ملف التقرير المستقل قبل أي أمر أو تعديل)  
**الهدف:** فحص جنائي مستقل وتدقيق لنزاهة كود واختبارات المرحلة 3 (Milestone 3: Frontend State Architecture, Single Source of Truth, Unmount Sync, and OCC).

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostic Rationale)
بموجب تكليف التدقيق الجنائي `DISPATCH.md` ودستور الوكلاء، يتعين على المدقق الجنائي التحقق المستقل من:
1. صحة وسلامة المنطق البرمجي المنفذ في `CastleCard.tsx` و `TaskTabContent.tsx` و `useCastles.ts` وخلوه تماماً من الواجهات المزيفة (Facades) أو النتائج المسبقة الصنع (Hardcoded Outputs).
2. فحص النزاهة لأداة التحقق `tools/verify_m3_frontend_state.py` والتأكد من أنها تجري اختبارات حقيقية دون أي تزييف (Zero mocks, real AST/structural assertions).
3. التحقق العملي بتشغيل أداة التحقق، وفحص بناء TypeScript، وتشغيل حزمة الاختبارات الشاملة للتأكد من استقرار المشروع.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Audit Logic & Steps)
1. **الخطوة الأولى:** تنفيذ فحص الحالة البرمجية عبر `git status` للتأكد من التغييرات الفعلية وحصر الملفات المعدلة.
2. **الخطوة الثانية:** تشغيل أداة التحقق المخصصة `python tools/verify_m3_frontend_state.py` وتسجيل مخرجاتها كاملة.
3. **الخطوة الثالثة:** التحقق المستقل من بناء الواجهة `cd dashboard; npm run build` للتأكد من سلامة الأنواع وعدم وجود كسر للواجهات.
4. **الخطوة الرابعة:** تشغيل حزمة اختبارات المشروع الكاملة `python tests/run_all_tests.py` للتأكد من عدم حدوث أي تراجع في الوظائف السابقة.

---

## 3. الأوامر التي ستُنفذ بالتفصيل والنتيجة المتوقعة (Commands & Expected Results)

| # | الأمر المزمع تنفيذه | الغرض والهدف | النتيجة المتوقعة |
|---|-------------------|--------------|-----------------|
| 1 | `git status --porcelain` | حصر ملفات المشروع المعدلة في المرحلة | ظهور ملفات `CastleCard.tsx`, `TaskTabContent.tsx`, `useCastles.ts`, `botApi.ts`, `types/index.ts`, `tools/verify_m3_frontend_state.py` |
| 2 | `python tools/verify_m3_frontend_state.py` | تشغيل اختبارات التحقق الجنائي للمرحلة 3 | اجتياز 8 من 8 اختبارات بنجاح (`OK`) |
| 3 | `powershell -Command "cd dashboard; npm run build"` | التحقق من بناء الواجهة وسلامة الـ TypeScript | نجاح البناء `built in ...` دون أخطاء |
| 4 | `python tests/run_all_tests.py` | تشغيل الحزمة الكاملة لاختبارات الباك إند والأنظمة | اجتياز 30 من 30 اختباراً بنجاح (`ALL TESTS PASSED`) |

سيتم توثيق المخرجات الخام الناتجة عن كل أمر فوراً ضمن تقرير التسليم النهائي `handoff.md`.
