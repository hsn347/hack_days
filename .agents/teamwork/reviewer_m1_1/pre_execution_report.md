# تقرير فني مستقل مسبق لتنفيذ أوامر الفحص والتحقق المستقل (Pre-Execution Verification Report)
**التاريخ**: 2026-11-02T17:25:00Z  
**الوكيل**: Reviewer 1 & Adversarial Critic (`reviewer_m1_1`)  
**المرحلة**: Milestone 1 (Backend & SQLite Optimization)  
**المرجعية**: القاعدة 5 من `GEMINI.md` ودستور الوكلاء `AGENTS_CONSTITUTION.md`

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
تم تكليف المدقق المستقل بفحص واعتماد تعديلات العامل M1 على قاعدة البيانات `core/database.py` وخادم الواجهة `api_server.py`.
للتحقق المستقل وتجنب الاعتماد على شهادة العامل الذاتية (Self-Certification) أو ادعاءات غير مدعومة، يتطلب الدستور تشغيل حزم الاختبار والقياس الميداني محلياً والتأكد من عدم وجود تراجع وظيفي (Regression) أو تحايل برمجي (Façade/Cheating).

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)
1. **الخطوة الأولى**: التحقق من الملفات المعدلة بدقة عبر `git status` و `git diff --stat`.
2. **الخطوة الثانية**: تشغيل سكربت الفحص المخصص للمرحلة الأولى `python tools/verify_m1_backend.py` للتحقق من:
   - انهيار استعلامات `get_all_users_with_castles` إلى استعلام واحد فقط (Single Query).
   - وجود وصحة فهارس التعبيرات والترتيب الخمسة (`idx_castle_states_lower_email`, `idx_castle_states_lower_user`, `idx_users_lower_email`, `idx_users_created_at`, `idx_castle_states_created_at`).
   - خطط الاستعلام `EXPLAIN QUERY PLAN` وتأكيد استخدام الفهارس ومنع الـ Full Table Scan.
   - سلامة هيكل البيانات والتوافق مع المفاتيح القديمة والجديدة.
   - عدم حظر الـ Event Loop في الـ WebSocket عبر `asyncio.to_thread`.
3. **الخطوة الثالثة**: تشغيل اختبارات الأداء والتراجع الشاملة في `tests/test_database_performance.py`.
4. **الخطوة الرابعة**: تشغيل سكربت القياس `python tools/benchmark_admin_baseline.py` للتحقق من أزمنة الاستجابة P50/P95.

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Outcomes)

### أمر 1: فحص حالة التعديلات المحلية
- **الأمر**: `git status --short`
- **الهدف**: معرفة الملفات المتغيرة والتأكد من عدم وجود ملفات غريبة أو غير مصرح بها.
- **النتيجة المتوقعة**: تعديلات في `core/database.py` و `api_server.py` وملفات التوثيق/الأدوات فقط.

### أمر 2: تشغيل سكربت التحقق للمرحلة الأولى
- **الأمر**: `python tools/verify_m1_backend.py`
- **الهدف**: تشغيل اختبارات التحقق الخمسة للمرحلة الأولى.
- **النتيجة المتوقعة**: نجاح كافة الاختبارات بنسبة 100% وظهور `ALL MILESTONE 1 VERIFICATION TESTS PASSED WITH 100% SUCCESS!`.

### أمر 3: تشغيل اختبارات التراجع وقاعدة البيانات الشاملة
- **الأمر**: `python -m unittest tests/test_database_performance.py`
- **الهدف**: التأكد من اجتياز اختبارات Tier 1 و Tier 2 (حالات الفراغ، الحدود، الضغط، التزامن، وعزل البيانات).
- **النتيجة المتوقعة**: `Ran 11 tests in ... OK`.

### أمر 4: تشغيل قياس خط الأساس المرجعي
- **الأمر**: `python tools/benchmark_admin_baseline.py`
- **الهدف**: قياس زمن الاستعلام المحدث والتحقق من عدم حدوث أي انهيار أو استثناء.
- **النتيجة المتوقعة**: إنهاء السكربت بنجاح وتحديث قياسات الأداء.

### أمر 5: فحص توزيع حسابات المستخدمين والمشرفين
- **الأمر**: `python -c "import sqlite3, core.database as db; conn = sqlite3.connect(db.get_db_path()); cur = conn.cursor(); print('total users in db:', cur.execute('SELECT COUNT(*) FROM users').fetchone()[0]); print('admin roles:', cur.execute(\"SELECT role, COUNT(*) FROM users GROUP BY role\").fetchall()); conn.close()"`
- **الهدف**: التحقق الدقيق من إجمالي المستخدمين في قاعدة البيانات وتفسير سبب كون النتيجة 150 (استبعاد حسابات المشرفين والتجار).
- **النتيجة المتوقعة**: إجمالي المستخدمين 154، واستبعاد 4 حسابات إدارية وتجار فينتج 150 مستخدماً عادياً.

### أمر 6: استعلام توزيع أدوار المستخدمين عبر أداة فحص في tools/
- **الأمر**: `python tools/inspect_user_roles.py`
- **الهدف**: تشغيل سكربت استعلامي آمن في مجلد tools/ لفحص عدد الحسابات بدقة.
- **النتيجة المتوقعة**: طباعة إجمالي المستخدمين وتوزيع الأدوار واستبعاد الإداريين.
