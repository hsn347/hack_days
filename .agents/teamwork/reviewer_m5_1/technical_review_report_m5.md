# تقرير الفحص الفني المستقل والمراجعة الهندسية المعاكسة — المرحلة 5 (M5)
### Milestone 5: Quality & Architecture Review — Network Optimization, Request Deduplication & AbortController Integration

- **المراجع:** مراجع الجودة والناقد الخصومي (Reviewer & Adversarial Critic M5 - Instance 1)
- **دليل التكليف:** `e:\osmanli\.agents\teamwork\reviewer_m5_1\DISPATCH.md`
- **الملف المرجعي:** `GEMINI.md` (القاعدة 5: إلزامية إرفاق ملف تقرير مستقل قبل أي أمر أو تعديل) & `AGENTS_CONSTITUTION.md`
- **تاريخ الفحص:** 2026-11-02T19:43:00Z
- **وضع النزاهة:** `development` (محلي معزول تماماً، حظر النشر عن بُعد)

---

## 1. التشخيص والهدف من المراجعة (Diagnosis & Review Rationale)

تأتي هذه المراجعة لتقييم جودة وتكامل التحسينات المنفذة في المرحلة 5 (Milestone 5) والمقدمة من `worker_m5`.
الأهداف الأساسية الخاضعة للتدقيق:
1. التحقق من تطبيق إلغاء طلبات HTTP غير المطلوبة عبر `AbortController` في `botApi.ts` لمنع تزاحم الشبكة وسباقات الاستجابة (Race Conditions) وتلف البيانات عند التنقل السريع.
2. التحقق من انهيار اتصالات WebSocket المتعددة لكل قلعة (`CastleCard`) من N اتصال متزامن إلى **اتصال واحد فقط مجمع (Multiplexed)** لكل مستخدم عبر نقطة النهاية `/ws/user-status/{user_id}` في `useUserBotStatuses.ts`.
3. التحقق من تطبيق تهدئة مدخلات البحث (Debouncing بمهلة 300ms) عبر `useDebounce.ts` في كافة واجهات البحث لمنع إجهاد المعالج وإعادة التصفية اللحظية مع كل نقرة مفتاح.
4. التحقق من تحصين مسارات خادم FastAPI في `api_server.py` ضد انقطاع اتصالات WebSocket واستثناءات `asyncio.CancelledError`.
5. استكشاف الثغرات وحالات الفشل المتطرفة (Adversarial Stress-Testing) من منظور خصومي للتأكد من عدم وجود تسريبات للذاكرة، أو استثناءات غير معالجة، أو تزييف للاختبارات (Integrity Violations).

---

## 2. المنطق وخطوات الفحص المستقل (Logic Chain & Inspection Steps)

### أ. فحص الشيفرة المصدرية (Static Code Inspection)
- **`dashboard/src/lib/botApi.ts`**:
  - تم فحص تصدير `interface RequestOptions { signal?: AbortSignal }`.
  - تم التأكد من دعم تمرير `signal` إلى `fetch()` عبر 34 دالة طلب HTTP أساسية وإدارية.
  - تم فحص دالة `isAbortError(err)` ودالة `parseAndLocalizeApiError` لمنع ظهور نوافذ أخطاء مزعجة (Toasts) عند الإلغاء العادي للطلبات.
- **`dashboard/src/hooks/useUserBotStatuses.ts`**:
  - فحص معمارية `UserStatusMultiplexer`:
    - إدارة الاتصال الفردي بنمط Singleton per `userId`.
    - عداد المراجع (Reference Counting) عبر `listeners.size`.
    - فترة السماح (Grace Period) المحددة بـ 3 ثوانٍ قبل إغلاق المقبس لمنع وميض الاتصال أثناء التنقل بين الصفحات.
    - تقنية التراجع التدريجي (Exponential Backoff) لإعادة الاتصال تبدأ من ثانيتين وتصل إلى حد أقصى 10 ثوانٍ.
    - دعم دالة `purgeAllUserStatusSockets()` لتفريغ كافة المقابس عند تسجيل الخروج.
- **`dashboard/src/components/accounts/CastleCard.tsx`**:
  - التأكد من استبدال الاتصال الفردي القديم باستدعاء `useRealBotStatus(castle.id, true, userId)`.
  - التأكد من تفويض هذا الخطاف في `useCastles.ts` إلى `useMultiplexedBotStatus`.
- **`dashboard/src/hooks/useDebounce.ts`**:
  - التحقق من تنفيذ خطاف عام نظيف `useDebounce<T>(value: T, delay: number = 300): T` مع تنظيف المؤقت (`clearTimeout`) عند كل تحديث لمنع تسريب الموارد.
- **واجهات البحث (`Accounts.tsx`, `Admin.tsx`, `AdminUsersCastles.tsx`, `AdminLiveProcesses.tsx`)**:
  - التأكد من إبقاء حقل الإدخال تفاعلياً بشكل فوري (`value={search}`)، مع قصر إعادة حساب مصفوفات التصفية (`useMemo`) على المتغير المهدأ (`debouncedSearch`).
- **`api_server.py`**:
  - فحص معالجة `(WebSocketDisconnect, asyncio.CancelledError)` في دوال `ws_logs`, `ws_status`, و `ws_user_status`.

---

## 3. الأوامر المستهدفة للتنفيذ والتحقق المخبري (Commands & Expected Outcomes)

1. **أداة التحقق الشاملة للمرحلة 5**:
   - الأمر: `python tools/verify_m5_network_dedup.py`
   - النتيجة المتوقعة: اجتياز 71 من أصل 71 فحصاً بنسبة 100.0%.
2. **بناء وتجميع تطبيق لوحة التحكم (TypeScript Build Check)**:
   - الأمر: `powershell -Command "Set-Location dashboard; npm run build"`
   - النتيجة المتوقعة: خلو المشروع تماماً من أي أخطاء ترجمة (Zero Type Errors) وإنتاج حزمة البناء الإنتاجية بنجاح (Exit code 0).
3. **حزمة الاختبارات الشاملة للمنصة (4 Tiers Regression Suite)**:
   - الأمر: `python tests/run_all_tests.py`
   - النتيجة المتوقعة: اجتياز جميع اختبارات المنصة الـ 30 بنسبة 100% دون أي فشل أو انتكاس.

---

## 4. استكشاف السطح الهجومي وحالات الفشل المتطرفة (Adversarial Attack Surface)

| الفرضية / السيناريو | آلية الهجوم أو الفشل المحتمل | النطاق المتأثر | التقييم الهندسي / إجراء التخفيف |
|---|---|---|---|
| **انقطاع شبكة ممتد مع إعادة محاولة لا نهائية** | في حال انقطاع السيرفر، هل يستمر `UserStatusMultiplexer` في محاولة إعادة الاتصال بمعدل مرتفع؟ | استهلاك الذاكرة وتراكم المؤقتات | **آمن:** الكود يطبق Backoff أسّي محكوم بسقف أقصى 10 ثوانٍ (`Math.min(delay * 1.5, 10000)`). |
| **تسريب مراجع في خريطة `multiplexers` بعد خروج المستخدم** | في حال تسجيل خروج المستخدم أو تبديل الحساب دون تنظيف، هل تبقى المقابس معلقة؟ | تسريب مقابس الويب | **آمن جزئياً / قيد التحقق:** يوفر الكود `purgeAllUserStatusSockets` ومربوط بانتهاء المهلة (3 ثوانٍ) بعد إلغاء اشتراك آخر بطاقة. |
| **سباق إغلاق المقبس والتنقل السريع (Route Flapping)** | انتقال المستخدم بين الصفحات وإلغاء تثبيت البطاقات ثم العودة خلال أقل من 3 ثوانٍ | انهيار المقبس أو اشتراك مكرر | **آمن:** يلغي `subscribe` مؤقت السماح فوراً `clearTimeout(this.graceTimer)` ويعيد استخدام نفس المقبس الحي. |
| **إلغاء طلبات TanStack Query وتضارب الإشعارات** | إلغاء الطلب عبر `AbortSignal` أثناء مغادرة الصفحة | ظهور إشعارات أخطاء وهمية في واجهة المستخدم | **آمن:** `isAbortError` تفحص بدقة `DOMException` و رسائل `AbortError` ويتم تجاهلها في معالج الأخطاء. |
