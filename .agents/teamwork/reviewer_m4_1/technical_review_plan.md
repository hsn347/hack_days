# خطة المراجعة الفنية المستقلة والتحقق الصارم — المرحلة 4 (M4)
### Milestone 4 Review: Caching Policies, TTL Calibration, Invalidation Precision & Logout Sanitization

**المرجع:** `GEMINI.md` (القاعدة 5: إلزامية إرفاق ملف تقرير مستقل قبل أي أمر) & `AGENTS_CONSTITUTION.md`  
**الدور:** Reviewer & Adversarial Critic  
**الهدف:** التحقق والتدقيق المستقل للأعمال المنجزة في المرحلة 4 قبل إصدار حكم الاعتماد (Verdict: APPROVE / REQUEST_CHANGES).

---

## 1. التشخيص وسبب الإجراء (Diagnosis & Rationale)
قامت ورشة العمل M4 بإجراء تعديلات جذرية على دورة حياة الكاش في الواجهة الأمامية للمنصة:
- تعديل `gcTime` الافتراضي في TanStack Query لمنع تضخم استهلاك الذاكرة.
- معايرة `staleTime` و `gcTime` في `useCastles.ts` لضمان التوازن بين خفض طلبات الشبكة وحداثة البيانات.
- إغلاق النقاط العمياء في إبطال الاستعلامات (Invalidation Blind Spots) لجميع الـ mutations.
- تنفيذ بروتوكول تطهير الذاكرة والتخزين المحلي (`localStorage` / `sessionStorage`) عند تسجيل الخروج وتبديل الحسابات.

بصفتنا مراجعاً ومشككاً عدائياً (Adversarial Critic)، يتعين علينا عدم الاكتفاء بالادعاءات النظرية، وفحص الكود سطراً بسطر للتأكد من:
1. عدم وجود أي تحايل أو غش أو نتائج اختبارات مشفرة مسبقاً (Integrity Violation Check).
2. دقة وصحة التعديلات المنفذة ومطابقتها للمتطلبات R3 و R7.
3. مناعة الكود ضد حالات الفشل الحافة (Edge Cases) والسباق (Race Conditions) وتنازع البيانات.

---

## 2. المنطق الهندسي وخطوات المراجعة (Review Logic & Steps)

1. **فحص الكود المصدري المستهدف (Source Code Inspection)**:
   - فحص `dashboard/src/lib/queryClient.ts` للتأكد من ضبط `gcTime: 600_000` (10 دقائق).
   - فحص `dashboard/src/hooks/useCastles.ts`:
     - فحص `staleTime: 60_000` و `gcTime: 600_000` في `useCastles`.
     - فحص `staleTime: 30_000` و `gcTime: 300_000` في `useCastle`.
     - فحص `staleTime: 10_000` و `gcTime: 60_000` في `useLiveBotStats`.
     - فحص جميع دوال التعديل (`useUpdateCastleCredentials`, `useToggleCastleActive`, `useDeleteCastle`, `useBotControl`, `useImportCastles`, `useBatchUpdateCastleConfigs`) والتأكد من إبطالها لجميع المفاتيح المتأثرة بدقة بما فيها `['castle', userId, castleId]` و `['live_bot_stats']` و `['admin_stats']`.
     - فحص `purgeCastlesCache` للتأكد من تنظيف كافة مفاتيح `empire_castles_cache_*` و `ibra_castles_cache_*` و `empire_active_castle_*`.
   - فحص `dashboard/src/hooks/useAuth.ts`:
     - فحص `purgeUserDataOnLogout` والتأكد من شموليتها لمسح `queryClient.clear()`، ومفاتيح `localStorage` و `sessionStorage`.
     - فحص استدعائها في `logout()` و `switchAccount()`.
   - فحص `dashboard/src/App.tsx`:
     - فحص استيراد وتطبيق دالة التطهير وضمان عدم حدوث تعارض.
   - فحص `tools/verify_m4_caching_lifecycle.py`:
     - التحقق الصارم من منطق الفحص للتأكد من أنه اختبار فحص حقيقي يقوم بتحليل AST وفحص ملفات المشروع الفعلية وليس سكربت شكلياً يعيد أرقاماً ثابتة.

2. **التنفيذ والتحقق المستقل (Independent Command Execution)**:
   - تشغيل سكربت الفحص المخصص للمرحلة الرابعة:
     `python tools/verify_m4_caching_lifecycle.py`
     النتيجة المتوقعة: نجاح 23 من أصل 23 فحصاً.
   - تشغيل فحص مترجم TypeScript:
     `Set-Location dashboard; npx tsc --noEmit`
     النتيجة المتوقعة: كود خروج 0 دون أي خطأ نوع أو تعريف.
   - تشغيل كامل مجموعة الاختبارات للمشروع:
     `python tests/run_all_tests.py`
     النتيجة المتوقعة: نجاح 30 من أصل 30 اختباراً بنسبة 100%.

3. **الفحص العدائي وسيناريوهات الفشل (Adversarial Stress-Testing)**:
   - اختبار السيناريوهات المعقدة:
     - ماذا يحدث إذا كان `userId` غير معرف أو فارغ أثناء التطهير؟
     - هل تتبقى بيانات لمفاتيح تبدأ بـ `ibra_` القديمة أو `empire_` الحديثة؟
     - هل يؤثر مسح الـ cache على تفضيلات اللغة أو الثيم؟
     - ماذا عن حذف قلعة وإلغاء استعلامها: هل استخدام `removeQueries` يمنع ظهور شاشات فارغة أو بقايا بيانات؟

4. **إعداد التقرير النهائي وإصدار الحكم (Final Verdict & Handoff)**:
   - كتابة `handoff.md` المتضمن الأقسام الخمسة الدستورية مع حكم صريح (`APPROVE` أو `REQUEST_CHANGES`).
   - إرسال التقرير النهائي للمشرف الأعلى عبر `send_message`.
