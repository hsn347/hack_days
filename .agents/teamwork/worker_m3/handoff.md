# تقرير التسليم البرمجي للمرحلة 3 (Milestone 3 Handoff Report)
### Frontend State Architecture, Single Source of Truth Unification & Mutation Lifecycle

**المرسل:** Worker M3 (Frontend State & Single Source of Truth Worker)  
**المستلم:** Orchestrator (Supervisor - Conversation ID: `44132d7d-07d0-4709-a292-a8e4727a82fd`)  
**تاريخ الإنجاز:** 2026-11-02T18:35:00Z  
**مجلد العمل:** `e:\osmanli\.agents\teamwork\worker_m3\`  
**حالة الإنجاز:** Hard Handoff (المهمة مكتملة بنسبة 100%، البناء سليم، وجميع الاختبارات مجتازة).

---

## 1. الملاحظات المباشرة (Observation)

1. **تشتت الحالة في `CastleCard.tsx` (الأسطر 64-118):**
   - تم رصد وجود 5 متغيرات حالة محلية منفصلة:
     `[liveCastle, setLiveCastle]`, `[liveState, setLiveState]`, `[connState, setConnState]`, `[isStopping, setIsStopping]`, `[isStarting, setIsStarting]`.
   - وجود دالتي `useEffect` لمزامنة البروبس ومراقبة حالة الـ WebSocket `useRealBotStatus`. عند تأخر وصول حدث `idle` من السوكيت كان المتغير `isStopping` يظل عالقاً في قيمة `true` مما يؤدي لتجمد البطاقة في حالة "جاري الإيقاف..." وتعطيل التفاعل.
2. **فقدان التزامن عند تفريغ المكون في `TaskTabContent.tsx` (الأسطر 730-743):**
   - دالة الـ cleanup عند الـ Unmount كانت تستدعي `updateCastle(castle.id, ...)` مباشرة دون تحديث كاش TanStack Query عبر `qc.setQueryData` ودون تحديث التخزين المحلي `saveCachedCastles`.
   - عند عودة المستخدم للتبويب أو إعادة فتح البطاقة، كانت الشاشة تقرأ البيانات القديمة من الكاش مما يوهم المستخدم بفقدان الإعدادات المحفوظة.
3. **غياب التحكم بالتعديل التفاؤلي (OCC) في الواجهة:**
   - واجهة `Castle` في `types/index.ts` لم تكن تحوي حقل `version`.
   - دالة `botApi.updateCastle` لم تكن تقبل `version` ولم تكن تلتقط كود HTTP 409 Conflict.
   - دالة `useUpdateCastleConfig` لم تكن تحدث كاش `['castleConfig', castleId]`.
4. **تجربة النقر على بطاقة القلعة:**
   - حدث النقر للتوسيع كان محصوراً في الترويسة وشريط الموارد فقط، مع غياب تفعيل النقر المباشر على الحاوية الخارجية للبطاقة per GEMINI.md Rule 2.

---

## 2. سلسلة المنطق والاستنتاج (Logic Chain)

1. **توحيد مصدر الحقيقة في `CastleCard.tsx`:**
   - بالاستناد إلى الملاحظة 1، تم حذف متغيرات الحالة الخمسة المتنافسة بالكامل.
   - تم اشتقاق حالة الطفرة مباشرة من الهوك المعتمد:
     `isMutationPending = botControl.isPending && botControl.variables?.castle?.id === castle.id`
     `isStarting = isMutationPending && botControl.variables?.state === 'running'`
     `isStopping = isMutationPending && botControl.variables?.state === 'idle'`
   - تم اشتقاق الحالة الفعالة `effectiveStatus` بتدرج أسبقية واضح وحاسم:
     1) طفرة المستخدم الجارية (`starting` / `stopping`).
     2) حالة الـ WebSocket الحية (`realStatus !== 'offline'`).
     3) حالة الكاش المحفوظة في كائن القلعة المعتمد (`bot_status.conn_state || bot_status.state || 'idle'`).
   - تم نقل حدث النقر `onClick={handleToggleExpand}` إلى الحاوية الخارجية للبطاقة (`castle-card`) مع ضبط `cursor-pointer select-none`، وضمان أن جميع الأزرار وعناصر التحكم ومحتوى الإعدادات المتوسعة تستخدم `e.stopPropagation()` لمنع أي تعارض.
2. **المزامنة الفورية عند الـ Unmount في `TaskTabContent.tsx`:**
   - بالاستناد إلى الملاحظة 2، تم استيراد `useQueryClient` وتعديل دالة تفريغ المكون `cleanup effect`.
   - عند وجود مسودة معدلة لم تُحفظ بعد:
     1) تحديث كاش الاستعلامات لقائمة القلاع `['castles', userId]` فورياً.
     2) تحديث كاش القلعة الفردية `['castle', userId, castle.id]` فورياً.
     3) تحديث كاش `['castleConfig', castle.id]` فورياً.
     4) تحديث التخزين المحلي `saveCachedCastles(userId, ...)` فورياً.
     5) إرسال طلب الحفظ مصحوباً برقم النسخة `version`.
   - إضافة علم `inFlightDraftRef` وحماية `isSavingRef.current` لمنع النقر المزدوج أو إرسال طلبات متزامنة مكررة لنفس المسودة.
3. **تكامل OCC واعتراض HTTP 409 Conflict:**
   - بالاستناد إلى الملاحظة 3، تمت إضافة `version?: number` في `Castle`.
   - تم تحديث `botApi.updateCastle` لإرسال `version` والتقاط `res.status === 409` وتوليد استثناء صريح يحمل `isConflict: true` و `status: 409`.
   - تم تحديث `useUpdateCastleConfig` لقبول `{ config, version }` وتحديث الكاشات الثلاثة والتخزين المحلي بعد الحفظ بنجاح.
   - في `TaskTabContent.tsx`: عند حدوث تعارض (409 Conflict) يتم إظهار Toast تنبيهي وإبطال الكاش فورياً لإعادة جلب أحدث إعدادات من الخادم.

---

## 3. التحفظات والحدود (Caveats)

- تم اختبار كافة التعديلات محلياً 100% دون الاتصال بأي خادم إنتاجي أو قواعد بيانات خارجية.
- تم ضبط `CastleDetail.tsx` بإضافة تعريف `displayLordName` المفقود الذي كان يعترض بناء الـ TypeScript.
- كاش المتصفح القديم في بيئات التطوير قد يتطلب تحديث الصفحة (`Ctrl+F5`) لأول مرة لضمان تحميل الحزمة المحدثة.

---

## 4. الخلاصة (Conclusion)

تم إنجاز المرحلة 3 (Milestone 3) بالكامل وفق أعلى معايير الجودة ودستور الوكلاء:
- القضاء التام على تجمد بطاقات القلاع بفضل إزالة التفرعات وتوحيد مصدر الحقيقة.
- حل مشكلة ضياع الإعدادات عند مغادرة التبويب بمزامنة كاش TanStack Query والتخزين المحلي فورياً.
- تأمين التعديلات المتزامنة بنظام OCC والتقاط كود 409 Conflict بسلاسة.
- تطبيق النقر المباشر على الحاوية الخارجية للبطاقة (Direct Card Surface Toggling) دون تعارض.
- اجتياز جميع اختبارات التحقق المخصصة في `tools/verify_m3_frontend_state.py` (8 من 8).
- اجتياز كامل حزمة اختبارات المشروع في `tests/run_all_tests.py` بنسبة 100% (30 من 30).
- نجاح بناء الواجهة بالكامل `npx tsc --noEmit` و `npm run build` دون أي أخطاء.

---

## 5. طريقة التحقق المستقلة (Verification Method)

يمكن للمدقق المستقل (Forensic / Victory Auditor) أو المشرف التحقق عبر الأوامر التالية:

1. **فحص معمارية الحالة والـ OCC والـ Unmount آلياً:**
   ```powershell
   python tools/verify_m3_frontend_state.py
   ```
   *النتيجة المتوقعة:* اجتياز 8 اختبارات من أصل 8 (`OK`).

2. **فحص الـ TypeScript وخلوه من الأخطاء:**
   ```powershell
   Set-Location dashboard; npx tsc --noEmit
   ```
   *النتيجة المتوقعة:* انتهاء الأمر بكود 0 دون أي مخرجات أخطاء.

3. **فحص حزمة بناء الواجهة الكاملة:**
   ```powershell
   Set-Location dashboard; npm run build
   ```
   *النتيجة المتوقعة:* نجاح بناء حزمة Vite بالكامل (`built in < 3s`).

4. **تشغيل حزمة اختبارات المشروع الشاملة:**
   ```powershell
   python tests/run_all_tests.py
   ```
   *النتيجة المتوقعة:* اجتياز 30 اختباراً من أصل 30 بنسبة 100% (`ALL TESTS PASSED SUCCESSFULLY`).
