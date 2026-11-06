# تقرير الفحص الفني المسبق للتدقيق الجنائي — المرحلة 4 (M4)

**المهمة:** تدقيق جنائي مستقل للمرحلة الرابعة (Milestone 4: Caching Policies, Invalidation Precision, and Logout Sanitization)  
**المرجع:** `GEMINI.md` (القاعدة 5: إلزامية إرفاق ملف تقرير مستقل قبل أي أمر أو تعديل) & `AGENTS_CONSTITUTION.md`

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
يتطلب التحقق الجنائي المستقل من تسليم المرحلة 4 التأكد تجريبياً وميدانياً (Empirical Verification) من:
1. صحة الكود ومطابقته لمعايير الأداء والنزاهة، وعدم وجود أي خداع أو قيم ثابتة أو واجهات وهمية (Facades) في `queryClient.ts` و`useCastles.ts` و`useAuth.ts`.
2. نزاهة أدوات الفحص التلقائي `tools/verify_m4_caching_lifecycle.py` وخلوها من التجاوزات أو تزييف نتائج الاختبارات.
3. نجاح الفحص الميداني لتنفيذ الاختبارات عبر بايثون وأدوات البناء والترجمة (`tsc`, `npm run build`, `run_all_tests.py`).

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Steps)
1. فحص حالة Git لتحديد كافة الملفات المعدلة بدقة عبر `git status` و `git diff`.
2. تشغيل أداة الفحص المخصصة للمرحلة الرابعة `python tools/verify_m4_caching_lifecycle.py`.
3. فحص سلامة بناء لوحة التحكم والتحقق الصارم من الأنواع عبر `npx tsc --noEmit` في مسار `dashboard`.
4. التحقق من سلامة الحزمة الإنتاجية عبر `npm run build` في `dashboard`.
5. تشغيل مجموعة الاختبارات الشاملة للمنصة `python tests/run_all_tests.py`.
6. التحليل الجنائي لمحتوى الكود والتأكد من عدم وجود أي من الأنماط المحظورة (Hardcoded test results, Facades, Fabricated verification outputs).

## 3. الأوامر التي ستُنفذ والنتيجة المتوقعة (Commands & Expected Results)
1. `git status` و `git diff --stat`:
   - المتوقع: عرض الملفات المعدلة ضمن نطاق M4 حصراً.
2. `python tools/verify_m4_caching_lifecycle.py`:
   - المتوقع: اجتياز جميع الفحوصات الـ 23 بنجاح كامل 100%.
3. `cd dashboard; npx tsc --noEmit`:
   - المتوقع: كود خروج 0 دون أي أخطاء نوعية في TypeScript.
4. `cd dashboard; npm run build`:
   - المتوقع: كود خروج 0 واكتمال البناء بنجاح.
5. `python tests/run_all_tests.py`:
   - المتوقع: اجتياز جميع الاختبارات الـ 30 بنجاح.
