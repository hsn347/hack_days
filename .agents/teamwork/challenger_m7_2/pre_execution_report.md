# تقرير فني مسبق (Pre-Execution Technical Report)
## مهمة التدقيق والتحقق العدائي لميلستون 7: عزل نطاقات التجار ودورة حياة الموارد
**المحرر:** Challenger M7 (Instance 2) — EMPIRICAL CHALLENGER  
**التاريخ والوقت:** 2026-11-02T20:38:00Z  
**المرجع التنظيمي:** AGENTS_CONSTITUTION.md & GEMINI.md (القاعدة 4 و 5)

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
- **السياق الفني:** في ميلستون 7، قام العامل (Worker M7) بإضافة التحقق الأمني `_verify_merchant_access_to_user(admin, target_user)` إلى مسار جلب قلاع المستخدمين للمشرفين في الباك إند:
  `api_server.py:1871-1891` (`@app.get("/api/admin/users/{uid}/castles")`).
- **المشكلة المكتشفة في التدقيق الأولي:**
  أداة التحقق التي أنشأها العامل `tools/verify_m7_ux_lifecycle.py` تقتصر على الفحص الثابت (Static AST / Regex Audit) لوجود الاستدعاء داخل الكود النصي فقط، دون تشغيل فعلي (Runtime Empirical Execution) للطلبات عبر بروتوكول HTTP للتحقق من سلوك المنظومة الفعلي ضد هجمات تجاوز الصلاحيات (BOLA / Horizontal Privilege Escalation) ورفض الطلبات غير المصرح بها.
- **الهدف المطلوب:**
  بناء وتشغيل أداة اختبار ضغط عدائية وتجريبية كاملة `tools/stress_m7_merchant_isolation.py` تستخدم `fastapi.testclient.TestClient` وقاعدة بيانات SQLite معزولة ومؤقتة بالكامل (Hermetic Zero-Production Mutation) لاختبار كافّة سيناريوهات العزل والحدود الأمنية ودورة حياة تنظيف الموارد عند تفريغ المكونات (Unmount).

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Logic Chain)
1. **العزل التام لقاعدة البيانات (Hermetic Isolation):**
   - إنشاء قاعدة بيانات مؤقتة باستخدام `tempfile.mkdtemp` وضبط `CASTLES_DB_PATH`.
   - تهيئة الجداول عبر `db.init_db`.
   - استعادة المسار الأصلي وحذف الملفات المؤقتة بالكامل في `tearDown` لضمان عدم لمس أو تلويث قاعدة الإنتاج نهائياً.
2. **بناء مصفوفة المستخدمين والقلاع الاختبارية (Test Matrix & Fixtures):**
   - **المشرف الأعلى (Super Admin):** `ibraboths@gmail.com` (كامل الصلاحيات عبر جميع النطاقات).
   - **مشرف التاجر (Merchant Admin):** `nurjan12ddsw2@gmail.com` التابع لنطاق `nurjanbot.online`.
   - **مستخدم تابع لنطاق التاجر (In-Domain User):** `user_nurjan_1` ذو `tenant_domain = "nurjanbot.online"` وله قلعة مسجلة.
   - **مستخدم تابع للنطاق الرئيسي (Main Domain User):** `user_main_1` ذو `tenant_domain = "ibrabot.com"` وله قلعة مسجلة.
   - **مستخدم بدون نطاق (Default Tenant User):** `user_no_domain` ذو `tenant_domain = ""` وله قلعة مسجلة.
   - **مستخدم تاجر منافس (Cross-Merchant User):** `user_other_merchant` ذو `tenant_domain = "vipbot.net"` وله قلعة مسجلة.
   - **مستخدم عادي غير مشرف (Regular User):** `user_regular` لمحاولة الوصول المباشر لـ endpoint المشرفين.
3. **مصفوفة متجهات الاختبار العدائي (Attack Vectors):**
   - **Vector 1 (Unauthenticated 401):** إرسال طلب بدون أي توكن أو استيثاق -> التحقق من الرفض بـ 401 Unauthorized.
   - **Vector 2 (Non-Admin User 403):** محاولة وصول مستخدم عادي -> الرفض بـ 403 Forbidden ("وصول مرفوض: لا تملك صلاحيات إدارة النظام").
   - **Vector 3 (Merchant Admin Cross-Domain BOLA 403):** محاولة مشرف التاجر جلب قلاع مستخدم خارج نطاقه (مثلاً `user_main_1` أو `user_other_merchant` أو `user_no_domain`) -> الرفض القطعي بـ 403 Forbidden ("غير مصرح لك بإدارة هذا المستخدم خارج نطاق دومينك").
   - **Vector 4 (Merchant Admin Legitimate In-Domain Access 200):** وصول مشرف التاجر لقلاع مستخدم مسجل ضمن نطاقه (`nurjanbot.online`) -> نجاح الطلب 200 OK وإرجاع قلاعه حصراً.
   - **Vector 5 (Global Super Admin Universal Access 200):** قدرة المشرف الأعلى على فحص قلاع أي مستخدم عبر كافة النطاقات -> نجاح 200 OK.
   - **Vector 6 (Non-existent Target User 404):** طلب قلاع مستخدم غير موجود في قاعدة البيانات -> إرجاع 404 Not Found.
   - **Vector 7 (Resource Lifecycle & Unmount Cleanup):** فحص إزالة مستمعات الأحداث (`removeEventListener('keydown')` في `ActionConfirmModal.tsx`) ومؤقتات التحديث الدوري (`clearInterval(timerRef.current)` في `AdminLiveProcesses.tsx`).
4. **تنفيذ حزمة التحقق الشاملة للمشروع:**
   - تشغيل سكريبت الاختبار العدائي المطور حديثاً.
   - تشغيل سكريبت فحص دورة حياة وتجربة المستخدم `tools/verify_m7_ux_lifecycle.py`.
   - فحص بناء الواجهة البرمجية بالأمر `powershell -Command "Set-Location dashboard; npm run build"`.
   - تشغيل الحزمة الموحدة `python tests/run_all_tests.py`.

---

### 3. الملفات والسطور والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة
1. **إنشاء ملف الاختبار العدائي:**
   - الملف: `tools/stress_m7_merchant_isolation.py`
   - المحتوى: فئة اختبار `MerchantIsolationStressSuite` ترث من `unittest.TestCase` مع 9 اختبارات تجريبية منفصلة.
2. **الأوامر التنفيذية:**
   - أمر 1: `python tools/stress_m7_merchant_isolation.py`
     * النتيجة المتوقعة: اجتياز جميع اختبارات العزل بنسبة 100% (9/9 PASS).
   - أمر 2: `python tools/verify_m7_ux_lifecycle.py`
     * النتيجة المتوقعة: اجتياز جميع الفحوصات الـ 22 بنسبة 100%.
   - أمر 3: `powershell -Command "Set-Location dashboard; npm run build"`
     * النتيجة المتوقعة: نجاح تجميع TypeScript وإنتاج حزمة Vite في أقل من 3 ثوانٍ دون أي أخطاء.
   - أمر 4: `python tests/run_all_tests.py`
     * النتيجة المتوقعة: اجتياز جميع اختبارات المنظومة الـ 30 بنسبة 100% في أقل من 5 ثوانٍ.
