# تقرير الفحص الفني المسبق وخطة التنفيذ الهندسية — المرحلة 5 (M5)
### Milestone 5: Network Optimization, Request Deduplication & AbortController Integration

**المرجع التنظيمي:** `e:\osmanli\AGENTS_CONSTITUTION.md` & `GEMINI.md` (القاعدة 5: إلزامية إرفاق ملف تقرير مستقل قبل أي تعديل أو أمر)  
**وثيقة التكليف:** `e:\osmanli\.agents\teamwork\worker_m5\DISPATCH.md`  
**وثيقة المتطلبات الأصلية:** `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (المتطلبات R4، R7، و R8)  
**نطاق التنفيذ والملفات المملوكة حصراً للوكيل M5:**
- `dashboard/src/lib/botApi.ts`
- `dashboard/src/hooks/useUserBotStatuses.ts` (ملف جديد لتوحيد اشتراك WebSocket)
- `dashboard/src/hooks/useDebounce.ts` (ملف جديد لضبط تأخير مدخلات البحث)
- `dashboard/src/hooks/useCastles.ts` (تمرير AbortSignal وتوجيه useRealBotStatus للاشتراك الموحد)
- `dashboard/src/components/accounts/CastleCard.tsx` (الاستفادة من الاشتراك الموحد بدلاً من اتصال منفصل لكل بطاقة)
- `dashboard/src/pages/Accounts.tsx` (تفعيل debouncing للبحث عن القلاع)
- `dashboard/src/pages/Admin.tsx` (تفعيل debouncing لبحث المستخدمين)
- `dashboard/src/pages/AdminUsersCastles.tsx` (تفعيل debouncing لبحث قلاع المستخدمين)
- `dashboard/src/pages/AdminLiveProcesses.tsx` (تفعيل debouncing لبحث العمليات الحية)
- `api_server.py` (تحصين معالجات WebSocket و endpoints ضد انقطاع العميل و `asyncio.CancelledError`)
- `tools/verify_m5_network_dedup.py` (أداة التحقق الشاملة للمرحلة 5)

---

## 1. التشخيص الجنائي والأسباب الجذرية (Root Cause Analysis & Diagnosis)

1. **غياب دعم إلغاء الطلبات المتزامنة عبر `AbortController` في `botApi.ts`**:
   - كافة دوال طلبات HTTP في `dashboard/src/lib/botApi.ts` (`fetchCastles`, `fetchCastle`, `fetchUserCastleData`, `updateCastle`, `controlBot`, `startBot`, `stopBot`, `fetchCastleDataLive`, `getAdminUsers`, `getAdminStats`, إلخ) لا تقبل معلمة إشارة الإلغاء `signal?: AbortSignal` ولا تمررها إلى `fetch()`.
   - عند تنقل المستخدم السريع بين الصفحات أو كتابة مدخلات بحث جديدة، تستمر الطلبات السابقة في الشبكة (In-flight HTTP requests) وتستهلك موارد السيرفر والمتصفح، وقد تؤدي إلى استجابات خارج الترتيب (Race Conditions) وتحديثات حالة لمكونات تم إلغاء تثبيتها (Unmounted components).
   - انعدام معالجة صريحة لخطأ `AbortError` / `DOMException`، مما قد يؤدي في حال تطبيق الإلغاء إلى إطلاق رسائل خطأ مزعجة (Error Toasts) للمستخدم عند إلغاء طبيعي للطلب.

2. **تشتت وتكرار اتصالات WebSocket لكل بطاقة قلعة (`CastleCard`) بدلاً من الاشتراك الموحد**:
   - في `dashboard/src/components/accounts/CastleCard.tsx` (السطر 84)، تستدعي كل بطاقة منفردة خطاف `useRealBotStatus(castle.id)`.
   - يقوم `useRealBotStatus` بفتح اتصال WebSocket مستقل لكل قلعة على المسار `/ws/status/{castle_id}`.
   - إذا كان لدى المستخدم 20 أو 50 قلعة في القائمة، يقوم المتصفح بفتح 20 أو 50 اتصال WebSocket متزامن مع السيرفر!
   - هذا يسبب استنزافاً حاداً لملفات الاتصال (File Descriptors)، واستهلاكاً كبيراً لحلقات أحداث AsyncIO في `api_server.py`، وازدحاماً لرسائل الشبكة، رغم أن السيرفر يوفر بالفعل نقطة نهاية موحدة فائقة الكفاءة: `/ws/user-status/{user_id}` التي ترسل حالات كافة قلاع المستخدم دفعة واحدة في رسالة واحدة خفيفة.
   - بالإضافة إلى ذلك، فإن خطاف `useUserBotStatuses` الذي كُتب جزئياً في `useCastles.ts` لا يُستخدم إطلاقاً في الواجهة، ولم يكن مصمماً كمدير موحد بمشاركة الحالة ومراعاة دورة حياة المكونات وتفادي التسريب.

3. **فيضان عمليات التصفية وإعادة الحساب مع كل نقرة زر (Keystroke Flooding)**:
   - في صفحات لوحة التحكم (`Accounts.tsx` السطر 563، `Admin.tsx` السطر 836، `AdminUsersCastles.tsx` السطر 222، و `AdminLiveProcesses.tsx` السطر 23)، يتم ربط حدث `onChange` لمدخلات البحث مباشرة بحالة `search` أو `searchQuery`.
   - يؤدي ذلك إلى إعادة تنفيذ دوال التصفية المعقدة (التي تفحص مصفوفات تضم مئات العناصر بمطابقات متعددة للسلاسل النصية) مع كل حرف يتم إدخاله دون أي تأخير زمني (Debouncing).
   - هذا السلوك يسبب تجمدات دقيقة في واجهة المستخدم (Input Lag / UI Janks)، ويزيد من استهلاك المعالج، ويتعارض مع المعيار R4.

4. **عدم اكتمال التقاط حالات الإلغاء وانقطاع العميل في مسارات السيرفر الخلفي (`api_server.py`)**:
   - نقاط نهاية الـ WebSocket في السيرفر (`ws_logs`, `ws_status`, `ws_user_status`) تلتقط `WebSocketDisconnect` و `Exception` العام، لكن بعضها لا يحدد بشكل صريح `asyncio.CancelledError` الذي يطلقه Uvicorn عند انقطاع الاتصال المفاجئ أو إلغاء المهام غير المتزامنة، مما قد ينتج عنه أخطاء غير معالجة في السجلات أو عدم تحرير فوري لموارد الاتصال.

---

## 2. المنطق الهندسي وخطوات المعالجة (Architecture & Remediation Logic)

### الخطوة 1: دعم `AbortController` الشامل والمعالجة اللطيفة للأخطاء في `botApi.ts`
- إضافة واجهة خيارات اختيارية موحدة:
  ```ts
  export interface RequestOptions {
    signal?: AbortSignal
  }
  ```
- تحديث كافة دوال الاستدعاء في `botApi.ts` لتقبل `options?: RequestOptions` (أو خيار `signal` ضمن المعاملات الحالية)، وتمرير `signal: options?.signal` إلى استدعاءات `fetch()`.
- تصدير دالة مساعدة معيارية `isAbortError(err: unknown): boolean`:
  ```ts
  export function isAbortError(err: unknown): boolean {
    if (!err) return false
    if (typeof DOMException !== 'undefined' && err instanceof DOMException && err.name === 'AbortError') {
      return true
    }
    const e = err as { name?: string; message?: string }
    return e?.name === 'AbortError' || e?.message === 'The user aborted a request.' || e?.message?.includes('aborted') === true
  }
  ```
- تحديث معالجات الأخطاء وتحديث استدعاءات TanStack Query في `useCastles.ts` لتمرير `signal` المستلم من سياق الاستعلام:
  ```ts
  queryFn: ({ signal }) => fetchCastles(userId, { signal })
  ```
  مما يمكن TanStack Query من إلغاء الطلبات المنتهية تلقائياً بمجرد إلغاء تثبيت المكون أو تغير المستخدم.

### الخطوة 2: إنشاء المدير الموحد لـ WebSocket (`useUserBotStatuses.ts`) وتحسين `CastleCard`
- إنشاء ملف مستقل `dashboard/src/hooks/useUserBotStatuses.ts` بمواصفات مؤسسية متقدمة:
  1. **اتصال مفرد لكل مستخدم (Singleton Per User)**: يدير اتصال WebSocket واحد فقط لكل `userId` موجه إلى `/ws/user-status/{user_id}`.
  2. **عداد مراجع المشتركين (Reference Counting)**: يتتبع عدد المكونات النشطة المشتركة. يبدأ الاتصال عند اشتراك أول مكون، ويغلقه بنظافة تامة بعد انقضاء مهلة أمان قصيرة (Grace Period) عند إلغاء اشتراك آخر مكون أو تسجيل الخروج.
  3. **إعادة اتصال مرنة بأسلوب Backoff التدريجي**: يتعامل مع انقطاع الاتصال بإعادة محاولة ذكية دون إغراق السيرفر.
  4. **مزامنة مع TanStack Query**: تحديث كاش الاستعلامات `['user_bot_statuses', userId]` فور ورود بيانات جديدة، وبث الحالات اللحظية للمشتركين.
  5. **خطافات مخصصة وسهلة الاستخدام**:
     - `useUserBotStatuses(userId: string, enabled?: boolean)`: يوفر خريطة الحالات لجميع قلاع المستخدم.
     - `useMultiplexedBotStatus(castleId: string, userId: string, fallback?: string)`: يوفر الحالة اللحظية لقلعة محددة دون فتح أي اتصال إضافي.
- تحديث `dashboard/src/components/accounts/CastleCard.tsx`:
  - استبدال `useRealBotStatus(castle.id)` باستدعاء `useMultiplexedBotStatus(castle.id, userId)` أو توجيه `useRealBotStatus` داخلياً للاستفادة من المدير الموحد عندما يتوفر `userId`.
  - النتيجة: الانتقال من N اتصال WebSocket إلى **اتصال واحد فقط** لجميع بطاقات القلاع في الصفحة.

### الخطوة 3: خطاف الـ Debounce الموحد (`useDebounce.ts`) وتطبيقه على حقول البحث
- إنشاء خطاف عام ونظيف عالي الأداء:
  `dashboard/src/hooks/useDebounce.ts`
  بمعامل تأخير افتراضي 300 مللي ثانية (250-300ms حسب مواصفات التكليف).
- تطبيقه في واجهات البحث:
  - `Accounts.tsx`: الحفاظ على الاستجابة الفورية للمدخل النصي في واجهة المستخدم، وتأخير استعلام التصفية `debouncedSearch` لمدة 300ms لمنع إعادة التصفية غير المبررة.
  - `Admin.tsx`: تأخير تصفية قائمة المستخدمين وحساب الأيام المتبقية حتى توقف المستخدم عن الكتابة.
  - `AdminUsersCastles.tsx`: تأخير تصفية القلاع والمستخدمين.
  - `AdminLiveProcesses.tsx`: تأخير تصفية العمليات الحية الجارية.

### الخطوة 4: تحصين مسارات الباك إند (`api_server.py`)
- مراجعة نقاط نهاية WebSocket: `/ws/user-status/{user_id}`, `/ws/status/{castle_id}`, `/ws/logs/{castle_id}`.
- التقاط صريح وموحد لـ `(WebSocketDisconnect, asyncio.CancelledError)` لمنع أي تسريب لمؤشرات الاتصال أو رسائل تتبع غير معالجة في السجلات عند قطع المتصفح للاتصال أو إلغاء المهام غير المتزامنة.
- التأكد من عدم بقاء أي مراجع يتيمة في قواميس الاتصالات أو طوابير السجلات `_log_qs`.

### الخطوة 5: بناء منصة التحقق الشاملة للمرحلة 5 (`tools/verify_m5_network_dedup.py`)
- كتابة اختبار شامل يتأكد من:
  1. وجود ودقة دعم `signal?: AbortSignal` في كافة دوال `botApi.ts`.
  2. صحة منطق `isAbortError` وعدم إثارة أخطاء وهمية عند الإلغاء.
  3. هندسة المدير الموحد لـ WebSocket `useUserBotStatuses.ts` وربطه مع `CastleCard.tsx`.
  4. تنفيذ الـ Debouncing (250–300ms) في جميع مكونات البحث الأربعة.
  5. معالجة `api_server.py` للقطع والإلغاء بسلاسة وبدون أخطاء.
  6. فحص خلو كود TypeScript من أي أخطاء من خلال `tsc --noEmit` ونجاح بناء المشروع `npm run build`.
  7. اجتياز جميع اختبارات المنصة الـ 30 بنجاح تام 30/30 (100%).

---

## 3. تفاصيل الملفات والأسطر المستهدفة والتغييرات البرمجية

| الملف المستهدف | التعديل المزمع | النتيجة المتوقعة |
|---|---|---|
| `dashboard/src/lib/botApi.ts` | إضافة `RequestOptions`، إلحاق `signal?: AbortSignal` بكافة الدوال، تمرير `signal` إلى `fetch()`، وتصدير `isAbortError`. | تمكين إلغاء أي طلب HTTP فوري عند تغيير الصفحة أو المسار أو المدخلات. |
| `dashboard/src/hooks/useUserBotStatuses.ts` | إنشاء خطاف ومدير موحد لاتصالات WebSocket مع reference counting ودعم TanStack Query. | إيقاف تكرار الاتصالات واقتصار البث على اتصال واحد لكل مستخدم. |
| `dashboard/src/hooks/useDebounce.ts` | إنشاء خطاف `useDebounce<T>(value: T, delay: number = 300): T`. | أداة عامة خفيفة وموثوقة لتهدئة تكرار الأحداث وتصفية البيانات. |
| `dashboard/src/hooks/useCastles.ts` | تمرير `signal` من `queryFn` إلى `fetchCastles` و `fetchCastle`، وتحديث `useRealBotStatus` للاستفادة من المدير الموحد. | إلغاء تلقائي للطلبات غير المطلوبة وتوحيد إدارة الحالة. |
| `dashboard/src/components/accounts/CastleCard.tsx` | ربط استعلام الحالة بالمدير الموحد `useMultiplexedBotStatus` بدلاً من فتح WebSocket خاص بكل بطاقة. | خفض اتصالات WebSocket من N إلى 1 مع الحفاظ على التحديث اللحظي. |
| `dashboard/src/pages/Accounts.tsx` | استخدام `useDebounce` على مدخل البحث `search`. | منع تكرار تصفية مئات القلاع مع كل ضغطة مفتاح. |
| `dashboard/src/pages/Admin.tsx` | استخدام `useDebounce` على مدخل البحث `search`. | تصفية سلسة للعملاء بدون بطء في الاستجابة. |
| `dashboard/src/pages/AdminUsersCastles.tsx` | استخدام `useDebounce` على مدخل البحث `searchQuery`. | تحسين أداء البحث في قلاع المستخدمين المجمعة. |
| `dashboard/src/pages/AdminLiveProcesses.tsx` | استخدام `useDebounce` على مدخل البحث `searchQuery`. | استقرار قائمة العمليات الحية وعدم إعادة حساب المصفوفات أثناء الكتابة. |
| `api_server.py` | التقاط صريح لـ `(WebSocketDisconnect, asyncio.CancelledError)` وإطلاق الموارد بنظافة. | استقرار تام لنقاط نهاية WebSocket وخلو السجلات من الاستثناءات المفاجئة. |
| `tools/verify_m5_network_dedup.py` | إنشاء أداة الفحص الهندسي والتحقق الصارم من متطلبات M5. | التحقق المستقل والموضوعي 100% بدون أي تزييف أو اختصار. |

---

## 4. خطة التحقق والامتثال (Verification & Quality Gates)

1. تشغيل أداة التحقق المستقلة:
   `python tools/verify_m5_network_dedup.py`
2. فحص توافق أنواع TypeScript وخلوها من الأخطاء:
   `cd dashboard && npx tsc --noEmit`
3. التحقق من سلامة حزمة البناء الإنتاجية للواجهة:
   `cd dashboard && npm run build`
4. تشغيل حزمة الاختبارات الأربعة الموحدة:
   `python tests/run_all_tests.py` (يجب أن تجتاز 30/30 بنسبة 100%)
5. تحرير تقرير التسليم النهائي `handoff.md` وإرسال الإشعار للمشرف عبر `send_message`.
