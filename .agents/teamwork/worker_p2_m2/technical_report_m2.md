# التقرير الفني المسبق لتنفيذ ترقيم صفحات قلاع المسؤول والتحميل الكسول (M2 / R1)
**المهمة:** Milestone 2: Admin Castles Pagination & Lazy Loading  
**المنفذ:** `worker_p2_m2`  
**المرجع:** `ORIGINAL_REQUEST.md` (Requirement R1)، `ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 2)، `GEMINI.md` Rule 5، `AGENTS_CONSTITUTION.md`

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause & Rationale)

1. **غياب الترقيم على مستوى قاعدة البيانات والباك إند (No Backend Pagination):**
   - في الوقت الحالي، نقطة النهاية `/api/admin/users-castles/summary` في `api_server.py` (السطور 1788–1868) تستعلم عن كافة المستخدمين عبر `db.get_all_users()`، ثم تستعلم عن كافة سجلات القلاع من جدول `castle_states`، وتجمعها في الذاكرة دون تطبيق أي `LIMIT` أو `OFFSET` أو شروط تصفية في الـ SQL.
   - في واجهة المستخدم `dashboard/src/pages/AdminUsersCastles.tsx` (السطور 114–125 و 394–486)، يتم جلب كامل المصفوفة دفعة واحدة، ويتم تصفية العناصر في المتصفح عبر `useMemo` ثم رندرة كافة بطاقات المستخدمين والقلاع في الـ DOM دفعة واحدة بدون أي ترقيم (Zero Pagination)، مما يؤدي لبطء وتجميد الواجهة مع تزايد عدد المستخدمين.

2. **تسريب واستهلاك الذاكرة بحمولة الـ JSON الثقيلة (Heavy Payload Bloat):**
   - استعلامات القلاع العامة في `core/database.py` (مثل `get_all_castles` في السطور 1631–1656) تجلب عمود `config TEXT` و `raw_json TEXT`، وكل قلعة تزن إعداداتها ما بين 15 إلى 25 كيلوبايت. عند تحميل مئات القلاع، يتم فك تسلسل ميجابايتات من النصوص غير المطلوبة في العرض السريع.
   - الحل المعماري هو حصر استعلام الملخص على الأعمدة الخفيفة فقط واستبعاد `config` و `raw_json` نهائياً من القائمة الأساسية، وجلب تفاصيل وإعدادات القلعة عند الطلب (On-Demand / Lazy Loading) فقط عند فتح أكورديون المستخدم.

3. **إلغاء التحديثات المتفائلة بإعادة الجلب العشوائي (Cache Invalidation Flaw):**
   - عند حذف قلعة في `AdminUsersCastles.tsx` (السطر 166)، يتم استدعاء `qc.invalidateQueries({ queryKey: ['admin_users_castles_summary'] })`، وهو ما يلغي التحديث المحلي المتفائل الذي تم عبر `setQueryData` ويجبر المتصفح على إعادة طلب كافة البيانات والوميض.

4. **مطابقة تجربة واجهة المستخدم مع صفحة المستخدمين (UI/UX Parity):**
   - صفحة المستخدمين `Admin.tsx` تعتمد شريط ترقيم أنيق بخيارات `[10, 25, 50, 100]` مع حجم افتراضي 25، وأسهم تنقل (Prev/Next)، ومؤشرات نطاق (`{startIndex + 1}–{endIndex} / {total} مستخدم`).
   - يتطلب المتطلب R1 تطبيق نفس هذه التجربة البصرية المتقنة، ولكن بربطها بالباك إند وقاعدة البيانات مباشرة.

---

## 2. المنطق والخطوات الهندسية المزمع تطبيقها (Architecture & Implementation Logic)

### 2.1 طبقة قاعدة البيانات (`core/database.py`):
1. **دالة استعلام الترقيم المفلترة `get_admin_castles_paginated`**:
   - المعاملات: `page: int = 1`, `page_size: int = 25`, `search: str = ""`, `filter_status: str = "all"`, `tenant_domains: Optional[List[str]] = None`, `db_path: Optional[str] = None`.
   - الاستعلام الأساسي الخفيف:
     - يجلب أعمدة المستخدم الضرورية: `uid, email, username, phone, role, is_banned, created_at, tenant_domain, plan_id, plan_name, subscription_status, subscription_expires_at, max_castles_allowed`.
     - يستبعد تماماً `config` و `raw_json` و `password`.
     - يربط مع استعلام فرعي لـ `castle_states` لحساب `castles_count` و `running_count` و `pending_count`.
     - يطبق شروط العزل للتجار (`tenant_domains`).
     - يطبق البحث في بريد المستخدم، اسمه، معرّفه، أو بريد وقلاع تابعة له.
     - يطبق التصفية (`with_castles`, `no_castles`, `running`, `all`).
     - يطبق `LIMIT :limit OFFSET :offset` مع ترتيب زمني تنازلي `ORDER BY u.created_at DESC`.
   - استعلام العد الإجمالي `COUNT(*)`:
     - ينفذ نفس شروط الـ `WHERE` لحساب إجمالي السجلات والصفحات بدقة رياضية.
   - استعلام معاينات القلاع الخفيفة للمستخدمين المعروضين في الصفحة فقط:
     - يجلب `castle_id, email, is_active, state, conn_state` للقلاع التابعة للمستخدمين في الصفحة الحالية فقط.
   - النتيجة: كائن يحوي `items` (المستخدمون مع معاينات قلاعهم)، `total`، `page`، `page_size`، `total_pages`، `has_more`، و `summary_stats`.

2. **دالة جلب تفاصيل وإعدادات القلعة عند الطلب `get_castle_config`**:
   - تسترجع إعدادات `config` الكاملة لقلعة واحدة عند الحاجة.
   - تدعم دالة `get_user_castles_detailed(user_id)` أو استخدام `get_user_castles(uid)` الحالية لجلب قلاع المستخدم الموسع فقط.

### 2.2 طبقة خادم الواجهة البرمجية (`api_server.py`):
1. **تحديث نقطة النهاية `GET /api/admin/users-castles/summary`**:
   - تقبل معاملات الاستعلام: `page: Optional[int] = Query(None, ge=1)`, `page_size: Optional[int] = Query(None, ge=1, le=500)`, `search: Optional[str] = Query(None)`, `filter_status: Optional[str] = Query(None)`.
   - إذا طُلبت بمعاملات ترقيم، تستدعي `db.get_admin_castles_paginated`.
   - إذا طُلبت بدون معاملات ترقيم (للتوافق مع الاختبارات الحالية وسكربتات القياس السابقة)، تعيد التنسيق الملائم المتوافق.
   - تعيد المظروف الكامل:
     ```json
     {
       "status": "success",
       "items": [...],
       "users": [...],
       "total": 128,
       "total_count": 128,
       "page": 1,
       "page_size": 25,
       "total_pages": 6,
       "has_more": true,
       "summary_stats": {
         "total_users": 128,
         "total_castles": 412,
         "total_running": 85
       }
     }
     ```
   - دمج الحالة الحية الحقيقية عبر `_get_real_status(cid)`.
   - تطبيق عزل نطاق التاجر بدقة عبر `tenant_domains = admin["merchant_tenant"]["domains"]`.

2. **نقطة النهاية `GET /api/admin/users/{uid}/castles`**:
   - التأكد من جلب تفاصيل وإعدادات القلاع للمستخدم المحدد فقط مع التحقق الأمني من صلاحية مشرف التاجر عبر `_verify_merchant_access_to_user(admin, target_user)`.

### 2.3 طبقة واجهة المستخدم وعميل API (`dashboard/src/lib/botApi.ts` & `AdminUsersCastles.tsx`):
1. **في `dashboard/src/lib/botApi.ts`**:
   - تعريف واجهة المظروف المرقم `AdminUsersCastlesPaginatedResponse`.
   - تحديث `fetchAdminUsersCastlesSummary`: تمرير `page`, `pageSize`, `search`, `filterStatus` كـ URL Query Parameters، وإرجاع المظروف الكامل مع الحفاظ على التوافقية العكسية لـ `users` و `items`.

2. **في `dashboard/src/pages/AdminUsersCastles.tsx`**:
   - إضافة حالات الترقيم: `pageSize: number = 25`, `currentPage: number = 1`.
   - إعادة تعيين `currentPage` إلى 1 فور تغير البحث أو التصفية أو حجم الصفحة.
   - تضمين شريط الترقيم المتطابق تماماً مع `Admin.tsx`:
     - اليسار: مؤشر النطاق `{startIndex + 1}–{endIndex} / {total} مستخدم`.
     - الوسط: أزرار التنقل (السابق/التالي بالأسهم المناسبة للـ RTL) ورقم الصفحة الحالية / الإجمالي.
     - اليمين: محدد حجم الصفحة بخيارات `[10, 25, 50, 100]`.
   - جلب تفاصيل القلاع خفيفاً وكسولاً عبر المكون الفرعي `UserCastlesDetail` عند فتح الكارد فقط.
   - معالجة التحديث المحلي عند حذف قلعة:
     - تحديث كاش تفاصيل قلاع المستخدم محلياً: `qc.setQueryData<Castle[]>(['admin_user_castles', uid], old => old ? old.filter(...) : [])`.
     - تحديث كاش الملخص المرقم محلياً لتحديث أعداد القلاع: `qc.setQueryData<AdminUsersCastlesPaginatedResponse>(['admin_users_castles_summary', currentPage, pageSize, debouncedSearchQuery, filterType], old => ...)`.
     - إبقاء إبطال كاش تفاصيل المستخدم الفردي `qc.invalidateQueries({ queryKey: ['admin_user_castles', uid] })` لضمان التزامن ومطابقة شروط اختبارات النزاهة.
     - **منع** استدعاء `qc.invalidateQueries({ queryKey: ['admin_users_castles_summary'] })` لمنع وميض الشاشة وإعادة تحميل القائمة بأكملها.

---

## 3. تفاصيل الملفات والأسطر المزمع تعديلها (Files & Code Modifications)

| الملف | السطور المستهدفة | طبيعة التعديل | النتيجة المتوقعة |
|---|---|---|---|
| `core/database.py` | بعد السطر 1081 وإضافة دالة جديدة | إضافة دالة `get_admin_castles_paginated` ودالة `get_castle_config` | استعلامات SQL سريعة ومرقمة بـ `LIMIT` و `OFFSET` و `COUNT(*)` مع استبعاد `config` |
| `api_server.py` | السطور 1788–1870 | تحديث مسار `/api/admin/users-castles/summary` لدعم معاملات الترقيم والبحث والفلترة ومظروف الاستجابة الكامل | تقليل حجم الحزمة المنقولة وسرعة استجابة فائقة وعزل بيانات التجار |
| `dashboard/src/lib/botApi.ts` | السطور 860–895 | إضافة أنواع `AdminUsersCastlesPaginatedResponse` وتحديث الدالة لطلب الاستعلام المرقم | دعم الترقيم بالباك إند مع حفظ التوافقية العكسية |
| `dashboard/src/pages/AdminUsersCastles.tsx` | السطور 90–260 و 480–540 | ربط الاستعلام بالترقيم وإضافة شريط تحكم الترقيم المطابق لـ `Admin.tsx`، وضبط تحديث الكاش المحلي | تجربة مستخدم سلسة وخفيفة دون وميض ومعالجة محلية سريعة |

---

## 4. خطة التحقق والاختبار (Verification Plan)

1. **فحص بناء الواجهة (Frontend TypeScript Compilation):**
   - تشغيل: `powershell -Command "Set-Location dashboard; npm run build"`
   - المعيار: 0 أخطاء TypeScript وبناء سليم 100%.

2. **فحص منصة الاختبارات الموحدة (Platform Test Suite):**
   - تشغيل: `python tests/run_all_tests.py`
   - المعيار: اجتياز جميع الاختبارات الـ 30 بنجاح تام (30/30 PASS).

3. **فحص اختبار قياس الأداء وسيناريوهات الترقيم السابقة:**
   - تشغيل: `python tools/verify_m6_admin_scalability.py`
   - تشغيل: `python tools/measure_baseline.py`
   - التأكد من عدم حدوث أي تراجع في سلامة النظام.
