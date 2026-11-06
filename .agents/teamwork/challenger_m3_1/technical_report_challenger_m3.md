# التقرير الفني المسبق: تشغيل أداة الفحص الإجهادي التجريبي لمعمارية الحالة ومصدر الحقيقة (Milestone 3)
### Pre-Execution Technical Report: Empirical Stress Harness for M3 Frontend State Architecture

**تاريخ التقرير:** 2026-11-02  
**الجهة:** Challenger M3 (Instance 1 - Frontend State Architecture Challenger)  
**المرجع:** `GEMINI.md` (البند 5: إلزامية ملف تقرير مستقل مسبقاً قبل أي تعديل أو تنفيذ لأي أمر)  
**الهدف:** إنشاء وتشغيل حزمة فحص إجهادي تجريبية `tools/stress_m3_frontend_state.py` والتحقق المستقل من خلو واجهة المستخدم من أي تعارض في الحالات أو تجمد أو فقدان للتعديلات المتزامنة.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause & Purpose)

في المرحلة الثالثة (M3)، تم تكليف العامل Worker M3 بإعادة هندسة إدارة الحالة في بطاقة القلعة (`CastleCard.tsx`) ومحتوى المهام (`TaskTabContent.tsx`) وتطبيق نظام التحكم بالتعديل المتزامن التفاؤلي (OCC).
بصفتنا جهة التدقيق والتحقق المستقل (Empirical Challenger)، يفرض علينا الدستور عدم الوثوق بادعاءات أو تقارير العامل دون إثبات تجريبي مستقل يُجرى عبر كتابة وتشغيل أداة فحص واختبار إجهادي مخصصة تفحص الشروط الحدية وتستكشف حالات الانهيار المحتملة (Edge cases & Stress testing).

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Steps)

1. **إنشاء أداة الفحص الإجهادي `tools/stress_m3_frontend_state.py`:**
   - **المحور 1: القضاء التام على الحالات المتنافسة في `CastleCard.tsx`:**
     التحقق البرمجي الدقيق من عدم وجود أي من متغيرات الحالة الخمسة (`liveCastle`, `liveState`, `connState`, `isStopping`, `isStarting`) كـ `useState`، وضمان أن `isStarting` و `isStopping` مشتقان بصورة نقية من `botControl.isPending` و `botControl.variables`.
   - **المحور 2: محاكاة فضاء الحالات (State Space Oracle) لـ `effectiveStatus`:**
     بناء محاكي لجميع التركيبات المحتملة للمدخلات (WebSocket drop, pending mutations, disconnected states, offline, null/undefined payloads) وإثبات رياضياً وتجريبياً استحالة بقاء البطاقة متجمدة في حالة "جاري الإيقاف..." عند انقطاع الاتصال.
   - **المحور 3: فحص تفريغ كاش الـ Unmount في `TaskTabContent.tsx`:**
     التأكد من التحديث المتزامن الفوري للمفاتيح الثلاثة لكاش TanStack Query:
     - `['castles', userId]`
     - `['castle', userId, castle.id]`
     - `['castleConfig', castle.id]`
     بالإضافة إلى تحديث التخزين المحلي `saveCachedCastles`.
   - **المحور 4: اختبار حواجز منع الحفظ المزدوج والتعديلات أثناء الطيران (In-flight Guards):**
     فحص آليات الحماية `isSavingRef.current` و `inFlightDraftRef.current` و `!isAlreadyInFlight` و `isPending` في الحفظ اليدوي والآلي وعند تفريغ المكون.
   - **المحور 5: تتبع معمارية OCC وتمرير النسخة `version` واعتراض 409 Conflict:**
     التحقق من تكامل `version` عبر `types/index.ts` و `botApi.ts` و `useCastles.ts` و `TaskTabContent.tsx` ومعالجة خطأ التعارض 409 بإشعار المستخدم وإبطال الكاش.
   - **المحور 6: النقر على السطح الخارجي للبطاقة (Direct Card Surface Toggling):**
     التحقق من وجود `onClick={handleToggleExpand}` على الحاوية العليا للبطاقة مع استخدام `e.stopPropagation()` في جميع الأزرار والمدخلات التفاعلية وحاوية الأكورديون.

2. **تنفيذ الأداة محلياً عبر `run_command`:**
   - تشغيل `python tools/stress_m3_frontend_state.py` والتقاط المخرجات كاملة.
3. **التحقق من مترجم المشروع:**
   - تشغيل `npx tsc --noEmit` في مجلد `dashboard`.
4. **تشغيل حزمة الاختبارات الشاملة:**
   - تشغيل `python tests/run_all_tests.py` للتأكد من عدم تأثر أي وظائف في المشروع.

---

## 3. الملفات والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة

| العملية / الأمر | الملف المستهدف | النتيجة المتوقعة |
|---|---|---|
| كتابة الكود | `tools/stress_m3_frontend_state.py` | إنشاء أداة الفحص الإجهادي الشاملة |
| تنفيذ أمر محلي | `python tools/stress_m3_frontend_state.py` | اجتياز 100% من الاختبارات الإجهادية وتأكيد سلامة المعمارية |
| تنفيذ أمر محلي | `npx tsc --noEmit` (داخل `dashboard`) | كود 0 دون أي أخطاء في الـ TypeScript |
| تنفيذ أمر محلي | `python tests/run_all_tests.py` | اجتياز 30/30 من اختبارات النظام الشاملة بنجاح |

جميع الإجراءات تتم محلياً بالكامل دون أي رفع أو نشر أو مساس بقواعد بيانات خارجية.
