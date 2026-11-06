# تقرير الفحص الفني المسبق وخطة التنفيذ الهندسية — المرحلة 4 (M4)
### Milestone 4: Precision Caching Policies, TTL Calibration, Query Invalidation, and Logout/Switch Sanitization

**المرجع التنظيمي:** `e:\osmanli\AGENTS_CONSTITUTION.md` & `GEMINI.md` (القاعدة 5: إلزامية إرفاق ملف تقرير مستقل قبل أي تعديل أو أمر)  
**وثيقة التكليف:** `e:\osmanli\.agents\teamwork\worker_m4\DISPATCH.md`  
**وثيقة المتطلبات:** `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (المتطلبات R3 و R7)  
**نطاق التنفيذ والملفات المملوكة حصراً للوكيل M4:**
- `dashboard/src/lib/queryClient.ts`
- `dashboard/src/hooks/useCastles.ts`
- `dashboard/src/hooks/useAuth.ts`
- `dashboard/src/App.tsx`
- `tools/verify_m4_caching_lifecycle.py`

---

## 1. التشخيص الجنائي والأسباب الجذرية (Root Cause Analysis & Diagnosis)

1. **تضخم الذاكرة واحتجاز الكاش لمدة 24 ساعة (Excessive gcTime Bloat)**:
   - في `dashboard/src/lib/queryClient.ts` وفي خطافات `useCastles.ts` (الأسطر 168 و 192)، تم ضبط `gcTime` بقيمة `1000 * 60 * 60 * 24` (24 ساعة كاملة).
   - هذا الضبط المفرط يمنع محرك TanStack Query من التخلص من استعلامات القلاع والبيانات المرجعية القديمة للذاكرة (Garbage Collection)، مما يؤدي لتراكم مئات الاستعلامات في ذاكرة المتصفح RAM عند التنقل الطويل أو استعراض حسابات متعددة.
   - بالإضافة إلى ذلك، تم ضبط `staleTime` في `useCastle` (السطر 191) على 60 ثانية وهو زمن طويل نسبياً لبيانات القلعة الفردية التي تتطلب استجابة أسرع (30 ثانية)، بينما تنعدم سياسة كاش واضحة ومستقلة للاستعلامات الحية (Live Bot Stats) والتي يجب أن تكون بـ `staleTime: 10_000` و `gcTime: 60_000`.

2. **نقاط عمياء في إبطال الاستعلامات عند التعديل (Query Invalidation Blind Spots)**:
   - خطاف `useUpdateCastleCredentials` (السطر 570) يقوم بإبطال `['castles', userId]` فقط، متجاهلاً الاستعلام الفردي `['castle', userId, castleId]`. فإذا كان المستخدم في شاشة تفاصيل القلعة، سيبقى يرى البيانات القديمة غير المحدثة.
   - خطاف `useToggleCastleActive` (السطر 583) يكتفي بإبطال `['castles', userId]` ولا يبطل `['castle', userId, castleId]` ولا `['admin_stats']` أو `['admin_users']`، مما يبقي عدادات القلاع النشطة في لوحة المسؤول خاطئة.
   - خطاف `useDeleteCastle` (السطر 596) لا يزيل استعلام القلعة المحذوفة من الكاش (`qc.removeQueries`)، ولا يبطل `['live_bot_stats']`، مما يترك استعلامات ميتة في الذاكرة.
   - خطاف `useBotControl` و `useStopUserBots` يبطلان `['castles', userId]` فقط بعد مهلة زمنية، متجاهلين إبطال كاش القلعة الفردية `['castle', userId, castleId]` وكاش الإحصائيات الحية.
   - عدم وجود خطاف معتمد لعمليات الاستيراد الجماعي `useImportCastles` بإبطال دقيق للمفاتيح المتأثرة.

3. **تسريب بيانات القلاع والتخزين المحلي بعد تسجيل الخروج وتبديل الحساب (Residual Cache Leak on Logout/Switch)**:
   - عند استدعاء `logout` أو `switchAccount` في `useAuth.ts` (الأسطر 360-362 و 463-466)، يتم استدعاء `queryClient.clear()` وحذف توكن المسؤول و `ibra_auth_profile`، لكن بيانات قلاع المستخدم المخزنة في `localStorage` بمفاتيح `ibra_castles_cache_*` و `empire_castles_cache_*` و `empire_active_castle_*` تبقى بالكامل في متصفح العميل دون تنظيف!
   - هذا يسمح لأي مستخدم جديد يسجل دخوله من نفس الجهاز أو المتصفح بالوصول مؤقتاً للبيانات المخبأة للحساب السابق، مما يخترق مبدأ عزل الحسابات والخصوصية (R3 و R7).

---

## 2. المنطق الهندسي وخطوات المعالجة (Architecture & Remediation Logic)

### الخطوة 1: معايرة مدد الكاش (TTL & GC Calibration) في TanStack Query
- توحيد مدد التقادم وحفظ الذاكرة وفق المعايير الصارمة التالية:
  - **قائمة القلاع (`useCastles`)**:
    - `staleTime: 60_000` (1 دقيقة لمنع استهلاك الشبكة).
    - `gcTime: 600_000` (10 دقائق لتنظيف الذاكرة بعد مغادرة الصفحة).
  - **تفاصيل القلعة الفردية (`useCastle`)**:
    - `staleTime: 30_000` (30 ثانية لتوازن بين الحداثة وسرعة الاستجابة).
    - `gcTime: 300_000` (5 دقائق).
  - **الإحصائيات الحية للبوتات (`useLiveBotStats`)**:
    - `staleTime: 10_000` (10 ثوانٍ).
    - `gcTime: 60_000` (1 دقيقة).
    - `refetchInterval: 10_000`.
  - **الإعدادات الافتراضية العامة في `queryClient.ts`**:
    - خفض `gcTime` من 24 ساعة إلى 10 دقائق (`600_000`).

### الخطوة 2: تصحيح النقاط العمياء في إبطال الاستعلامات (Precision Query Invalidation)
- تعديل كافة الخطافات (Mutations) في `dashboard/src/hooks/useCastles.ts`:
  1. `useUpdateCastleCredentials`: إبطال `['castles', userId]` و `['castle', userId, castleId]`.
  2. `useToggleCastleActive`: إبطال `['castles', userId]`، `['castle', userId, castleId]`، `['admin_stats']`، و `['admin_users']`.
  3. `useDeleteCastle`: إزالة استعلام `['castle', userId, castleId]` و `['castleConfig', castleId]` من الذاكرة فوراً عبر `qc.removeQueries`، مع إبطال `['castles', userId]`، `['user', userId]`، `['admin_users']`، `['admin_stats']`، و `['live_bot_stats']`.
  4. `useBotControl` & `useUpdateBotState`: إبطال استعلام القلعة الفردية `['castle', userId, castleId]` واستعلام `['live_bot_stats']` بالإضافة للقائمة.
  5. `useBatchUpdateCastleConfigs`: إبطال كاش كل قلعة متأثرة وكاش إعداداتها `['castleConfig', id]`.
  6. إضافة `useImportCastles`: إبطال شامل لـ `['castles', userId]`، `['user', userId]`، `['admin_users']`، و `['admin_stats']`.

### الخطوة 3: التطهير الشامل للبيانات عند الخروج وتبديل الحساب (Sanitization Protocol)
- في `dashboard/src/hooks/useAuth.ts` و `dashboard/src/hooks/useCastles.ts`:
  - بناء دالة تطهير مركزية `purgeUserDataOnLogout(userId?)`:
    1. استدعاء `queryClient.clear()` لمسح ذاكرة الوصول العشوائي فورياً 100%.
    2. مسح كافة المفاتيح من `localStorage` التي تبدأ بـ:
       - `empire_castles_cache_` و `ibra_castles_cache_`
       - `empire_active_castle_` و `ibra_active_castle_`
       - `empire_auth_profile` و `ibra_auth_profile` و `osmanli_admin_session_token`
    3. مسح `sessionStorage` بالكامل.
  - استدعاء هذه الدالة إجبارياً في:
    - دالة `logout()`
    - دالة `switchAccount()`
    - حالات الرفض الأمني والتوجيه التلقائي (Domain mismatch forced logout).

---

## 3. تفاصيل الملفات والأسطر المستهدفة (Targeted Files & Code Modifications)

### الملف 1: `dashboard/src/lib/queryClient.ts`
- **السطور 6-12**:
  - استبدال `gcTime: 1000 * 60 * 60 * 24` بالقيمة المعيارية `600_000` (10 دقائق).

### الملف 2: `dashboard/src/hooks/useCastles.ts`
- **السطور 105-147**:
  - دعم كلا البادئتين: الأساسية `empire_castles_cache_` والتوافقية `ibra_castles_cache_`.
  - إضافة دعم إدارة وتخزين وحذف القلعة النشطة `empire_active_castle_${userId}` و `ibra_active_castle_${userId}`.
  - تصدير دالة `purgeCastlesCache(userId?: string)`.
- **السطور 150-173 (`useCastles`)**:
  - تثبيت `staleTime: 60_000` و `gcTime: 600_000`.
- **السطور 176-196 (`useCastle`)**:
  - تصحيح `staleTime: 30_000` و `gcTime: 300_000`.
- **إضافة خطاف جديد (`useLiveBotStats`)**:
  - استعلام `live_bot_stats` بـ `staleTime: 10_000` و `gcTime: 60_000`.
- **السطور 357، 420، 530، 570، 583، 610**:
  - تصحيح وإضافة إبطال المفاتيح الدقيقة لكافة الـ mutations.
- **إضافة خطاف `useImportCastles`**:
  - لدعم الاستيراد الجماعي مع إبطال دقيق للمفاتيح.

### الملف 3: `dashboard/src/hooks/useAuth.ts`
- **إضافة دالة التطهير المركزية `purgeUserDataOnLogout`**:
  - فحص وحذف كافة مفاتيح الكاش وقفل الجلسات والتخزين المحلي.
- **السطور 359-363 (`switchAccount`)**:
  - ربط استدعاء `purgeUserDataOnLogout` مع `queryClient.clear()`.
- **السطور 462-468 (`logout`)**:
  - استدعاء `purgeUserDataOnLogout` لمسح كافة بيانات المستخدم وقلاعه فوراً.

### الملف 4: `tools/verify_m4_caching_lifecycle.py`
- إنشاء سكربت فحص آلي مستقل يتحقق من:
  1. مطابقة إعدادات `staleTime` و `gcTime` في الكود المصدري وفق المتطلبات المحددة بدقة.
  2. شمولية الإبطال في جميع الخطافات وعدم وجود نقاط عمياء.
  3. كفاءة التطهير الشامل للـ localStorage وذاكرة TanStack Query عند تسجيل الخروج والتبديل.
  4. محاكاة دورة حياة الكاش والتأكد من عدم تسريب أي أثر للبيانات السابقة.

---

## 4. خطة التحقق وضمان الجودة (Verification & QA Plan)

1. **فحص الـ TypeScript**:
   - تشغيل `npx tsc --noEmit` للتأكد من خلو المشروع تماماً من أي أخطاء ترجمة أو تضارب في الأنواع.
2. **فحص حزمة البناء**:
   - تشغيل `npm run build` للتأكد من نجاح إنتاج الحزمة دون تحذيرات كاسرة.
3. **سكربت الفحص المخصص للمرحلة الرابعة**:
   - تشغيل `python tools/verify_m4_caching_lifecycle.py` ومراجعة النتائج.
4. **مجموعة الاختبارات الشاملة للمنصة**:
   - تشغيل `python tests/run_all_tests.py` والتأكد من اجتياز 30 من أصل 30 اختباراً بنجاح كامل 100%.
