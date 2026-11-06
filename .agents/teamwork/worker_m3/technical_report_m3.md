# التقرير الفني الشامل للمرحلة 3: توحيد مصدر الحقيقة وإدارة دورة حياة الحالات والكاش في الواجهة
### Technical Report — Milestone 3: Frontend State Architecture, Single Source of Truth & Mutation Lifecycle

**تاريخ التقرير:** 2026-11-02  
**المرجع التنظيمي:** `e:\osmanli\AGENTS_CONSTITUTION.md` & `GEMINI.md` (البند 5: إلزامية ملف التقرير الفني المسبق)  
**وثيقة التكليف:** `e:\osmanli\.agents\teamwork\worker_m3\DISPATCH.md`  
**بيئة التنفيذ:** محلي بالكامل داخل `e:\osmanli` (حظر تام للرفع أو الاتصال بالإنتاج)  
**الحالة:** تقرير فني شامل ومسبق قبل تطبيق التعديلات وتنفيذ أوامر الفحص والتحقق.

---

## 1. تشخيص الأسباب الجذرية ولماذا هذا الإجراء مطلوب (Root Cause Diagnostics)

### 1.1 تشتت الحالة وتفرع النسخ المتنافسة في بطاقة القلعة (`CastleCard.tsx`)
- **التشخيص:**
  يحتوي المكون `CastleCard.tsx` حالياً على 5 متغيرات حالة محلية منفصلة (`useState`):
  1. `liveCastle`: نسخة محلية مفصولة عن بروب `castle`.
  2. `liveState`: تفرع محلي لحالة البوت (`state`).
  3. `connState`: تفرع محلي لحالة الاتصال (`conn_state`).
  4. `isStopping`: علم محلي يُفترض أنه يعبر عن الإيقاف الجاري.
  5. `isStarting`: علم محلي يُفترض أنه يعبر عن التشغيل الجاري.
- **مكمن الخلل:**
  تخضع هذه المتغيرات لتحديثات متنافسة عبر دالتي `useEffect` (الأسطر 84-118) تحاولان الموازنة بين تحديثات الخادم الآتية من كاش TanStack Query وتحديثات الـ WebSocket الآتية من `useRealBotStatus`.
  إذا تأخر الـ WebSocket في إرسال حالة `idle` بعد إيقاف البوت، أو في حال انقطاع مؤقت، يظل العلم `isStopping` عالقاً في قيمة `true` إلى الأبد؛ مما يعطل زر التحكم ويجعل البطاقة متجمدة في حالة "جاري الإيقاف...".
  بالإضافة إلى ذلك، فإن `liveCastle` يعزل البطاقة عن التحديثات الفورية التي يجريها كاش TanStack Query عند تعديل القلاع الأخرى أو التعديلات الموضعية.
- **الحل الهندسي:**
  إلغاء التفرعات الخمسة بالكامل (`liveCastle`, `liveState`, `connState`, `isStopping`, `isStarting`)، وجعل حالة البطاقة مشتقة بصورة نقية (Pure Derived State) من مصدر الحقيقة الوحيد المعتمد:
  `castle` الممرر من كاش الاستعلامات الموحد + حالة الطفرة الجارية (`botControl.isPending`) + حالة البث الحي للـ WebSocket (`useRealBotStatus`).

### 1.2 فقدان تزامن الحفظ عند مغادرة المكون (`TaskTabContent.tsx`)
- **التشخيص:**
  في ملف `TaskTabContent.tsx` (الأسطر 730-743):
  ```typescript
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current)
      if (
        !isBatchMode &&
        castle.id &&
        JSON.stringify(draftConfigRef.current) !== JSON.stringify(lastSavedConfigRef.current)
      ) {
        updateCastle(castle.id, { config: draftConfigRef.current as unknown as Record<string, unknown> }).catch(() => {})
      }
    }
  }, [castle.id, isBatchMode])
  ```
- **مكمن الخلل:**
  عند تفريغ المكون (Unmount) عند إغلاق الأكورديون أو التبديل بين التبويبات، يتم استدعاء دالة الـ cleanup التي تلغي المؤقت وتستدعي `updateCastle` مباشرة كطلب HTTP خام دون تحديث كاش TanStack Query ودون تحديث التخزين المحلي `localStorage`!
  نتيجة لذلك، إذا أعاد المستخدم فتح إعدادات القلعة فوراً، يقرأ المكون من كاش TanStack Query أو `localStorage` الذي يحتوي على الإعدادات القديمة، فتظهر الإعدادات للمستخدم وكأنها تراجعت ولم تُحفظ!
- **الحل الهندسي:**
  عند حدوث الـ Unmount مع وجود مسودة غير متطابقة، يجب فوراً:
  1. تحديث كاش TanStack Query مفتاح `['castles', userId]` ومفتاح `['castle', userId, castleId]` ومفتاح `['castleConfig', castleId]` بشكل لحظي متزامن عبر `qc.setQueryData`.
  2. تحديث التخزين المحلي `saveCachedCastles(userId, ...)` فورياً لضمان استرجاع 0ms حتى لو أُعيد تحميل الصفحة.
  3. إرسال طلب التحديث مصحوباً برقم النسخة `version` لدعم الـ OCC ومنع التعديلات المكررة.

### 1.3 غياب التحكم بالتعديل التفاؤلي (OCC) ومعالجة تعارض 409 Conflict
- **التشخيص:**
  في المرحلة السابقة (M2) قام الباك إند بإضافة حقل `version` لجدول `castle_states` وأصبح المسار `PUT /api/castles/{id}` يقبل `version` ويرجع خطأ HTTP 409 Conflict إذا كان رقم النسخة متقادماً.
  ومع ذلك، فإن واجهة المستخدم في `botApi.ts` و `useCastles.ts` و `TaskTabContent.tsx` لا تمرر `version` ولا تلتقط كود 409 Conflict بشكل منظم.
- **الحل الهندسي:**
  1. إضافة حقل `version?: number` في واجهة `Castle` بملف `types/index.ts`.
  2. دعم تمرير `version` في `botApi.updateCastle` والتقاط استجابة HTTP 409 وتغليفها بخطأ واضح يحمل `isConflict: true` و `status: 409`.
  3. دعم `version` في `useUpdateCastleConfig` وتحديث الكاش برقم النسخة الجديد فور نجاح الحفظ.
  4. في `TaskTabContent.tsx`: عند استلام 409 Conflict، يتم تنبيه المستخدم بإشعار Toast واضح وإبطال كاش القلعة تلقائياً لجلب أحدث البيانات من السيرفر.

### 1.4 تجربة المستخدم والنقر على البطاقة (Direct Card Surface Toggling)
- **التشخيص:**
  وفقاً للبند 2 في `GEMINI.md`:
  "Direct Card Surface Toggling: In card lists (like combat or prestige tasks), ensure clicking anywhere on the outer card component toggles the task cleanly without conflicting with child inputs."
  في `CastleCard.tsx`، حدث النقر للتوسيع موضوع فقط على ترويسة البطاقة وشريط الموارد، مما يسبب عدم استجابة النقر على أطراف البطاقة أو هوامشها، وفي نفس الوقت يجب التأكد من أن جميع الأزرار والمدخلات التفاعلية داخل البطاقة تمنع انتشار النقر (`e.stopPropagation()`) بدقة لمنع فتح وإغلاق الأكورديون بالخطأ.

---

## 2. المنطق والخطوات الهندسية المزمع تطبيقها (Architecture & Steps)

### الخطوة 1: تنظيف وهيكلة `CastleCard.tsx` كمصدر حقيقة وحيد
1. حذف حالات `useState` الخمس المتنافسة: `liveCastle`, `liveState`, `connState`, `isStopping`, `isStarting`.
2. اشتقاق حالة الطفرة الجارية مباشرة من `botControl`:
   ```typescript
   const isMutationPending = botControl.isPending && botControl.variables?.castle?.id === castle.id
   const isStarting = isMutationPending && botControl.variables?.state === 'running'
   const isStopping = isMutationPending && botControl.variables?.state === 'idle'
   ```
3. اشتقاق الحالة الفعالة `effectiveStatus`:
   - الأولوية الأولى: الطفرة الجارية للمستخدم (`starting` أو `stopping`).
   - الأولوية الثانية: حالة الـ WebSocket اللحظية في حال اتصاله (`realStatus !== 'offline'`).
   - الأولوية الثالثة: حالة القلعة المحفوظة في الكاش المعتمد (`castle.bot_status.conn_state || castle.bot_status.state || 'idle'`).
4. نقل معالج النقر `handleToggleExpand` إلى الحاوية الخارجية العليا للبطاقة (`castle-card`) مع ضبط `cursor-pointer` وإزالة الازدواجية، والتأكد من استمرار عمل `e.stopPropagation()` في جميع الأزرار وعناصر التحكم ومحتوى الأكورديون الداخلي.
5. توفير حالات واضحة ومستقلة:
   - حالة التحميل: سبينر واضح أثناء البدء والإيقاف والرفع إلى السيرفر وتطبيق القوالب.
   - حالة الخطأ: شريط تنبيه واضح لنص الخطأ ورسالة المصادقة.
   - حالة الفراغ: قيم بديلة آمنة للموارد والإحداثيات واللورد.
   - حالة النجاح: شارات نيون متوهجة مع مؤشر نبض حي.

### الخطوة 2: مزامنة دورة حياة التعديلات عند الـ Unmount في `TaskTabContent.tsx`
1. استيراد `useQueryClient` من `@tanstack/react-query` واستيراد دوال الكاش المعتمدة `getCachedCastles`, `saveCachedCastles`, `mergeCastleConfig` من `../../hooks/useCastles`.
2. تعديل دالة الـ cleanup الخاصة بـ `useEffect` (الأسطر 730-743):
   - عند وجود فرق بين `draftConfigRef.current` و `lastSavedConfigRef.current`:
     أ. تحديث كاش `['castles', userId]` فورياً.
     ب. تحديث كاش `['castle', userId, castle.id]` فورياً.
     ج. تحديث كاش `['castleConfig', castle.id]` فورياً.
     د. تحديث التخزين المحلي `saveCachedCastles`.
     هـ. إرسال الطلب عبر `updateCastle(castle.id, { config: unmountDraft, version: currentVersionRef.current })`.
3. منع الإرسال المكرر (Double Submits / Race Conditions):
   - التحقق من `isSavingRef.current` وحفظ المسودة الجاري حفظها في `inFlightDraftRef`.
   - عدم إطلاق طلب مكرر لنفس المسودة إذا كانت قيد الإرسال بالفعل.

### الخطوة 3: تطبيق الـ Optimistic Concurrency Control (OCC)
1. تعديل `types/index.ts`:
   - إضافة `version?: number` لـ `Castle`.
2. تعديل `dashboard/src/lib/botApi.ts`:
   - دعم `version?: number` في معامل دالة `updateCastle`.
   - فحص `res.status === 409` في دالة `updateCastle` وتوليد استثناء مخصص يحمل `isConflict: true` و `status: 409`.
   - التأكد من قراءة `raw.version` في `formatCastleFromApi`.
3. تعديل `dashboard/src/hooks/useCastles.ts`:
   - دعم قبول `{ config, version }` في دالة التحويل لـ `useUpdateCastleConfig`.
   - في `onSuccess`: تحديث كاش TanStack Query وكاش التخزين المحلي بالبيانات والنسخة المحدثة.
4. تعديل `TaskTabContent.tsx`:
   - الاحتفاظ بـ `currentVersionRef` ومزامنته مع `castle.version`.
   - تمرير النسخة الحالية عند الحفظ.
   - في حال التقاط خطأ تعارض (409 Conflict): إشعار المستخدم فورياً بإشعار تحذيري وإبطال الكاش لإعادة جلب التعديل الأحدث.

### الخطوة 4: التحقق والاختبار البرمجي الشامل
1. إنشاء أداة فحص واختبار هندسية `tools/verify_m3_frontend_state.py` تفحص شجرة الكود (AST / Regex / Type Check) وتتحقق من استيفاء كافة المتطلبات دون وجود أي حالات متنافسة.
2. فحص بناء الـ TypeScript للواجهة: التأكد من خلوه من الأخطاء عبر مترجم المشروع.
3. تشغيل حزمة اختبارات المشروع الشاملة `python tests/run_all_tests.py` والتأكد من اجتيازها بالكامل (30/30).

---

## 3. تفاصيل الملفات المستهدفة والتغييرات المتوقعة

| الملف المستهدف | السطور التقريبية | نوع التعديل | النتيجة المتوقعة |
|---|---|---|---|
| `dashboard/src/types/index.ts` | ~168-180 | إضافة `version?: number` إلى كائن `Castle` | توفير حقل النسخة لنظام OCC في الأنواع |
| `dashboard/src/lib/botApi.ts` | ~222-238, ~532-588 | دعم `version` في `updateCastle`، اعتراض كود 409، وربط `version` في `formatCastleFromApi` | إرسال النسخة والتقاط التعارض وتغذية واجهة المستخدم برقم النسخة |
| `dashboard/src/hooks/useCastles.ts` | ~470-505 | دعم معاملات النسخة في `useUpdateCastleConfig` وتحديث الكاشات الثلاثة والتخزين المحلي | تحديث كاش TanStack Query فورياً بعد الحفظ وتفادي التناقض |
| `dashboard/src/components/accounts/CastleCard.tsx` | ~64-150, ~194-255, ~258-285 | إزالة الحالات المتنافسة الخمس، واشتقاق الحالة مباشرة من الكاش والـ mutation والـ WS، ونقل النقر للحاوية الخارجية | القضاء على تجمد البطاقات نهائياً وتوحيد مصدر الحقيقة |
| `dashboard/src/components/accounts/TaskTabContent.tsx` | ~640-745 | مزامنة كاش TanStack Query والتخزين المحلي عند الـ Unmount، تمرير النسخة، ومعالجة كود 409 | منع فقدان الإعدادات عند الخروج ومقاومة التعارض التزامني |
| `tools/verify_m3_frontend_state.py` | جديد | سكربت فحص آلي لمعمارية الحالة والـ OCC والـ Unmount | تحقق برمجي مستقل يثبت مطابقة المعايير بدقة |

---
**الخلاصة:**  
تم استكمال تشخيص المشاكل بدقة، ورسم الخطة الهندسية المعيارية، وتحديد الملفات والسطور المستهدفة. بناءً على هذا التقرير، سنشرع الآن في تطبيق التعديلات البرمجية وتشغيل الاختبارات المحلية.
