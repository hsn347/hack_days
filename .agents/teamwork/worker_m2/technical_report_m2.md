# تقرير فني شامل: معالجة الأمان والتحكم بالتعديلات المتزامنة (Milestone 2)
### Technical Remediation Report: Security Hardening & Optimistic Concurrency Control (OCC)

**المرجع:** `e:\osmanli\AGENTS_CONSTITUTION.md` & `e:\osmanli\GEMINI.md` (البند 5: إلزامية التقرير الفني المسبق)  
**المرحلة:** Milestone 2 (M2)  
**الملفات المخصصة حصرياً للمهمة:**
- `api_server.py`
- `core/database.py`

---

## 1. تشخيص الأسباب الجذرية (Root Cause Diagnostics)

### 1.1 تسريب كلمات المرور بنص صريح (P0 - Plaintext Password Leak)
- **الموقع:** `api_server.py:2767-2774` في المسار `GET /api/local/castles/{identifier}`.
- **التشخيص:**
  المسار لا يحتوي على أي مصادقة (`Depends(get_current_user)` غائبة)، ويستدعي `db.get_castle(identifier)` التي تعيد كائن القلعة الخام من جدول `castle_states` بما في ذلك عمود `password` بنصه الصريح.
- **الأثر الأمني:**
  يمكن لأي مستخدم أو فاحص خارجي جلب كلمات مرور القلاع بنص صريح دون الحاجة لأي صلاحيات.

### 1.2 ثغرة BOLA/IDOR في جلب بيانات الموارد الحية (P0 - BOLA in `/api/castle-data/{email}`)
- **الموقع:** `api_server.py:2776-2794` في المسار `GET /api/castle-data/{email}`.
- **التشخيص:**
  المسار يتطلب تسجيل الدخول (`current_user`) لكنه لا يتحقق إطلاقاً من ملكية المستخدم للبريد الإلكتروني المطلوب. يقوم الخادم مباشرة بالاتصال بسيرفر اللعبة وجلب الإحداثيات والموارد والذهب وقوة اللورد لأي حساب بناءً على الإيميل فقط.
- **الأثر الأمني:**
  تجاوز عزل الحسابات وسرقة بيانات موارد ومواقع قلاع المستخدمين الآخرين.

### 1.3 انتحال البريد في تشغيل البوت (P0 - Parameter Spoofing in `/api/bot/start`)
- **الموقع:** `api_server.py:2590-2631` في المسار `POST /api/bot/start`.
- **التشخيص:**
  المسار يتحقق من ملكية `castle_id` للمستخدم `caller_uid`، ولكنه يستمر في تمرير واستخدام `req.email` الوارد من المتصفح كما هو دون مطابقته مع الإيميل المسجل فعلياً في قاعدة البيانات `c_info["email"]`.
- **الأثر الأمني:**
  إمكانية تمرير إيميل مستخدم آخر والاستيلاء على جلسة اللعبة المفتوحة في `session_cache.json`.

### 1.4 كشف مسارات التحكم الداخلي بدون مصادقة (P0 - Unprotected Internal Endpoints)
- **الموقع:** `api_server.py` (10 مسارات داخلية):
  1. `/api/internal/stop-all`
  2. `/api/internal/restart-all`
  3. `/api/internal/direct-start`
  4. `/api/internal/deploy-lock`
  5. `/api/internal/deploy-unlock`
  6. `/api/internal/gradual-start`
  7. `/api/internal/cancel-start-queue`
  8. `/api/internal/save-running-state`
  9. `/api/internal/debug-state`
  10. `/api/bot/conn-state`
- **التشخيص:**
  هذه المسارات تنفذ عمليات حساسة تشمل إيقاف جميع البوتات، قفل وضع النشر، وتعديل حالات الاتصال، لكنها كانت مكشوفة دون أي تحقق من الهوية أو توكن داخلي.
- **الأثر الأمني:**
  تعطيل الخدمة وتخريب حالات تشغيل البوتات من أي جهة خارجية.

### 1.5 غياب قفل التعديل التفاؤلي وتعارض الحفظ المتزامن (Lost Updates & OCC)
- **الموقع:** `core/database.py:1157-1195` في دالة `update_castle_config`.
- **التشخيص:**
  جدول `castle_states` لا يحتوي على عمود `version`. دالة `update_castle_config` تقرأ الإعدادات وتدمجها ثم تحفظها دون قفل ذري أو فحص نسخة، مما يؤدي إلى حدوث Lost Updates عند تعديل نفس القلعة من تبويبين مختلفين أو مستخدمين متزامنين.
- **الأثر الهندسي:**
  فقدان إعدادات المهام المحدثة عند حدوث عمليات حفظ متزامنة.

---

## 2. المنطق والخطوات الهندسية المعتمدة (Architectural Remediation Logic)

### الخطوة 1: معالجة ثغرة تسريب كلمة المرور في `/api/local/castles/{identifier}`
- إضافة تبعية المصادقة: `current_user: Dict[str, Any] = Depends(get_current_user)`.
- التحقق الصارم من الملكية:
  يجب أن يكون `c["user_id"] == current_user["uid"]` أو يكون المستخدم مشرفاً (`is_super_admin(current_user)` أو `current_user.get("role") in ("admin", "merchant_admin")`). في حال عدم التطابق، يتم إرجاع `403 Forbidden`.
- تجريد الحقول الحساسة:
  استدعاء `c.pop("password", None)` و `c.pop("raw_json", None)` بشكل قطعي قبل إرجاع الاستجابة.

### الخطوة 2: معالجة BOLA/IDOR في `/api/castle-data/{email}`
- التحقق من ملكية البريد الإلكتروني للمستخدم الحالي:
  - التحقق إذا كان المستخدم مشرفاً عاماً أو مشرف تاجر.
  - أو إذا كان `email.lower() == current_user.get("email", "").lower()`.
  - أو إذا كانت القلعة تنتمي لقلاع المستخدم في SQLite: `any(c.get("email", "").lower() == email.lower() for c in db.get_user_castles(current_user["uid"]))`.
- في حال عدم تحقق أي من الشروط السابقة، يتم رفض الطلب فوراً بـ `403 Forbidden`.

### الخطوة 3: معالجة انتحال البريد في `/api/bot/start`
- بعد استخراج سجل القلعة المعتمد من قاعدة البيانات:
  `c_info = db.get_castle_by_id(req.castle_id, None if is_admin else caller_uid)`
- فرض البريد المعتمد:
  `req.email = c_info.get("email") or req.email`
- إحباط أي محاولة لتمرير بريد مزيف.

### الخطوة 4: حماية المسارات الداخلية العشرة بدالة فحص موحدة (`verify_internal_access`)
- إنشاء دالة تبعية أمنية `verify_internal_access(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme))` تتحقق من:
  1. الاتصال الداخلي المباشر عبر الـ Loopback المحلي: `request.client.host in ("127.0.0.1", "::1", "localhost")` مع عدم وجود ترويسات `x-real-ip` خارجية غير موثوقة.
  2. أو توفر توكن داخلي معتمد في ترويسة `X-Internal-Token` يطابق `INTERNAL_API_SECRET`.
  3. أو وجود جلسة مستخدم بدور مشرف (`admin` أو `merchant_admin`).
- إذا لم يتحقق أي شرط، يتم إرجاع `403 Forbidden`.
- تطبيق التبعية على المسارات الداخلية العشرة.

### الخطوة 5: تطبيق Optimistic Concurrency Control (OCC) في `core/database.py`
- إضافة عمود `version INTEGER DEFAULT 1` لجدول `castle_states` في `init_db`.
- تعديل `update_castle_config(castle_id, config_dict, user_id=None, expected_version=None, db_path=None)`:
  1. بدء معاملة ذرية فورية عبر `BEGIN IMMEDIATE`.
  2. قراءة النسخة الحالية `current_version` والإعدادات `current_config`.
  3. إذا تم تمرير `expected_version`، مقارنة `current_version == expected_version`. إذا وجد اختلاف، يتم التراجع عن المعاملة وإرجاع تعارض تزامني:
     `{"success": False, "conflict": True, "current_version": current_version, "expected_version": expected_version, "error": "Concurrency conflict"}`.
  4. في حال التطابق أو عدم تحديد نسخة، يتم حساب `new_version = current_version + 1` وتحديث السجل ذرياً بـ `version = new_version`.
  5. إرجاع `{"success": True, "version": new_version}`.
- في `api_server.py`:
  - إضافة حقل `version: Optional[int] = None` في `CastleUpdateRequest`.
  - معالجة تعارض الـ OCC وإرجاع `409 Conflict` عند حدوث تصادم.

---

## 3. تفاصيل التعديلات والملفات والأسطر المستهدفة

| الملف | النطاق / الأسطر المستهدفة | طبيعة التعديل | النتيجة المتوقعة |
|---|---|---|---|
| `core/database.py` | الأسطر 123-164 و 240-260 | إضافة `version INTEGER DEFAULT 1` للجدول وترقية الأعمدة الحالية | دعم إدارة النسخ التفاؤلية في قاعدة البيانات |
| `core/database.py` | الأسطر 1157-1195 | إعادة كتابة `update_castle_config` مع `BEGIN IMMEDIATE` وفحص `expected_version` وتحديث `version` | منع التحديثات المفقودة (Lost Updates) بنسبة 100% |
| `api_server.py` | الأسطر 350-355 | إضافة `version: Optional[int] = None` إلى `CastleUpdateRequest` | استقبال النسخة المتوقعة من العميل |
| `api_server.py` | الأسطر 1170-1195 | التحقق من نتيجة `update_castle_config` وإرجاع 409 عند التعارض | إبلاغ الواجهة الأمامية بالتعارض التزامني |
| `api_server.py` | الأسطر 2058-2588 و 2747-2757 | حماية المسارات الداخلية بتبعية `verify_internal_access` | إغلاق المسارات الداخلية أمام غير المصرح لهم |
| `api_server.py` | الأسطر 2600-2631 | فرض `req.email = c_info["email"]` في `/api/bot/start` | منع انتحال البريد في جلسات البوت |
| `api_server.py` | الأسطر 2767-2774 | مصادقة وتجريد كلمة المرور في `/api/local/castles/{id}` | منع تسريب كلمات المرور بنص صريح |
| `api_server.py` | الأسطر 2776-2794 | فحص ملكية الإيميل في `/api/castle-data/{email}` | إغلاق ثغرة BOLA/IDOR بالكامل |

---

## 4. خطة التحقق والاختبار (Verification Plan)
1. إنشاء سكربت فحص مستقل `tools/verify_m2_security.py` يفحص:
   - رفض الوصول غير المصادق لـ `/api/local/castles/{id}` وتجريد كلمة المرور.
   - رفض جلب بيانات إيميل مستخدم آخر في `/api/castle-data/{email}` بـ 403.
   - فرض الإيميل الحقيقي للقلعة وتجاهل الإيميل المزور في `/api/bot/start`.
   - حظر الوصول للمسارات الداخلية العشرة بدون صلاحيات وإتاحتها للمشرف/التوكن/المحلي.
   - نجاح الـ OCC: رفض التعديل عند تضارب النسخ وقبوله وزيادة النسخة عند تطابقها.
2. تشغيل حزمة الاختبارات الشاملة الموحدة `python tests/run_all_tests.py` والتأكد من نجاح 100% من الاختبارات.
