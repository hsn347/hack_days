# تقرير الخطة الفنية للتحقق والتحدي البرمجي — Milestone 3 (Challenger M3-2)
### Empirical Verification & Challenge Plan for Build Integrity & OCC Concurrency

**تاريخ التقرير:** 2026-11-02  
**المرجع:** `e:\osmanli\GEMINI.md` (البند 5: إلزامية ملف التقرير الفني المسبق قبل أي أمر أو تعديل)  
**وكيل التحدي:** Challenger M3 (Instance 2 — Build & Concurrency OCC Challenger)  
**معرف الجلسة:** `48327de6-98e2-4935-99a6-81a97d3125f5`  
**الهدف:** الفحص التجريبي المستقل لسلامة بناء حزمة الإنتاج وتكامل التحكم بالتعديلات المتزامنة (OCC) واختبارات الانحدار.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

قام Worker M3 بتطبيق تعديلات معمارية على إدارة الحالة وتوحيد مصدر الحقيقة في الواجهة الأمامية (`CastleCard.tsx` و `TaskTabContent.tsx` و `botApi.ts` و `useCastles.ts` و `types/index.ts`). شملت هذه التعديلات:
1. إزالة الحالات المحلية المتنافسة في `CastleCard.tsx`.
2. ربط حفظ الإعدادات عند تفريغ المكون (`TaskTabContent.tsx` unmount) بكاش TanStack Query والتخزين المحلي.
3. تفعيل الـ Optimistic Concurrency Control (OCC) بإرسال حقل `version` عند التعديل، واعتراض استجابة HTTP 409 Conflict وإشعار المستخدم وإبطال الكاش.

بصفتنا وكيل التحدي التجريبي (Empirical Challenger)، يُحظر علينا الاعتماد على ادعاءات العامل أو سجلاته. يتعين علينا تجريبياً وبشكل مستقل:
- فحص سلامة بناء الحزمة الإنتاجية والتأكد من خلو المشروع تماماً من أي أخطاء ترجمة TypeScript أو أخطاء بناء Vite.
- محاكاة استجابة HTTP 409 والتحقق تجريبياً من سلوك `botApi.updateCastle` وتغليف الخطأ بالعلم `isConflict: true` و `status: 409`.
- التحقق من معالجة كود 409 في `TaskTabContent.tsx` وإبطال استعلامات الكاش تلقائياً.
- تشغيل حزمة اختبارات الانحدار الشاملة للمشروع والتأكد من اجتياز 30/30 اختباراً.

---

## 2. المنطق والخطوات الهندسية المزمع تطبيقها (Logic & Steps)

### الخطوة 1: فحص البناء الإنتاجي وفحص الـ TypeScript
- الانتقال إلى مجلد `dashboard`.
- تنفيذ فحص TypeScript الصارم بدون توليد ملفات: `npx tsc --noEmit`.
- تنفيذ بناء حزمة الإنتاج: `npm run build` (الذي يتضمن `tsc && vite build`).
- التحقق من كود الإرجاع (Exit code 0) والتأكد من عدم وجود أي Warnings أو Errors تحجب البناء.

### الخطوة 2: الفحص التجريبي المستقل لآلية OCC واعتراض HTTP 409
- تشغيل أداة التحقق المخصصة للمرحلة `python tools/verify_m3_frontend_state.py`.
- إنشاء وتشغيل سكربت اختبار تجريبي مستقل `tools/test_challenger_occ_empirical.py` يحاكي خادم HTTP محلي يرجع كود 409 Conflict مع بيانات JSON، ويستدعي أو يفحص مسار الاستجابة في `botApi.updateCastle` للتأكد تجريبياً من:
  1. اعتراض كود 409.
  2. قراءة تفاصيل رسالة الخطأ من الـ payload إن وجدت أو استخدام الرسالة الافتراضية.
  3. وسم كائن الخطأ بـ `isConflict = true` و `status = 409`.
  4. قيام `TaskTabContent.tsx` بالتقاط هذا الخطأ وإطلاق `qc.invalidateQueries` لمفاتيح `['castles', userId]` و `['castle', userId, castle.id]`.

### الخطوة 3: تشغيل حزمة اختبارات الانحدار الشاملة
- تشغيل الأمر `python tests/run_all_tests.py` من المجلد الرئيسي للمشروع.
- التأكد من اجتياز جميع الاختبارات الـ 30 بنسبة 100% (30 Passed, 0 Failed, 0 Errors).

### الخطوة 4: كتابة تقرير التسليم النهائي (Handoff Report)
- كتابة `handoff.md` المتضمن الملاحظات المباشرة، وسلسلة المنطق، والتحفظات، والخلاصة بقرار صريح (`APPROVE` أو `REQUEST_CHANGES`)، وطريقة التحقق المستقلة.
- إرسال رسالة النتيجة للمشرف (Orchestrator).

---

## 3. الأوامر والملفات المنفذة والنتيجة المتوقعة بالتفصيل (Commands & Files)

| الأمر | المسار التنفيذي | الغرض | النتيجة المتوقعة |
|---|---|---|---|
| `npx tsc --noEmit` | `e:\osmanli\dashboard` | فحص أنواع TypeScript في الواجهة | كود إرجاع 0، خلو تام من أي أخطاء برمجية |
| `npm run build` | `e:\osmanli\dashboard` | بناء حزمة الإنتاج بالكامل عبر Vite | إنتاج ملفات `dist/` بنجاح وكود إرجاع 0 |
| `python tools/verify_m3_frontend_state.py` | `e:\osmanli` | فحص معمارية الحالة والـ OCC والـ Unmount | اجتياز 8 من 8 اختبارات بنجاح |
| `python tools/test_challenger_occ_empirical.py` | `e:\osmanli` | اختبار تجريبي لاقتناص تعارض 409 وإبطال الكاش | اجتياز الاختبارات وتأكيد حماية OCC |
| `python tests/run_all_tests.py` | `e:\osmanli` | تشغيل حزمة اختبارات الانحدار الشاملة للمشروع | اجتياز 30/30 بنجاح بنسبة 100% |
