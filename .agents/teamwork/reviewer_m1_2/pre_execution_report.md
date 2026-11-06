# تقرير فني مسبق لتشغيل أوامر التحقق من المرحلة 1 (Milestone 1 Verification Pre-Execution Report)

**تاريخ التقرير:** 2026-11-02T17:21:00Z  
**الجهة المنفذة:** Reviewer 2 (`teamwork_reviewer`)  
**المجلد:** `e:\osmanli\.agents\teamwork\reviewer_m1_2\`  
**المرجع:** `GEMINI.md` البند 5 (إلزامية إرفاق ملف تقرير مستقل مسبقاً قبل أي أمر أو تعديل)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
وفقاً لتكليف المهمة الصادر من المشرف الأعلى (`44132d7d-07d0-4709-a292-a8e4727a82fd`)، يتعين على المراجع 2 إجراء تحقق مستقل وفحص عدائي (Adversarial Review) لتعديلات العامل M1 في الملفين:
- `core/database.py` (الفهارس التعبيرية واستعلام التجميع الفردي وإلغاء اختناق 3N+1)
- `api_server.py` (ترحيل استعلامات السوكيت إلى مسار غير متزامن `asyncio.to_thread`)

لإتمام الفحص الموضوعي بالأدلة وتأكيد عدم وجود اختلاق نتائج أو غياب للفهارس، يجب تنفيذ أدوات الفحص المعتمدة واختبارات SQLite المباشرة محلياً.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Planned Steps)
1. فحص الفروق المباشرة للتعديلات المنجزة للتأكد من انحصارها في نطاق المهمة.
2. تشغيل أداة التحقق المستقلة `tools/verify_m1_backend.py` للتأكد من:
   - انهيار استعلامات `get_all_users_with_castles` إلى استعلام واحد فقط.
   - وجود وصحة الفهارس الخمسة (`idx_castle_states_lower_email`, `idx_castle_states_lower_user`, `idx_users_lower_email`, `idx_users_created_at`, `idx_castle_states_created_at`).
   - اعتماد SQLite الفعلي على الفهارس في خطط الاستعلام `EXPLAIN QUERY PLAN`.
   - سلامة هيكل البيانات والتوافقية الرجعية للكائنات.
   - عدم حظر حلقة الأحداث في WebSocket.
3. تشغيل أداة القياس المعيارية `tools/benchmark_admin_baseline.py` للتحقق من الأداء وعدم حدوث أي انحدار أو انهيار في النظام.
4. إجراء فحص عدائي لحالات الحافة (Edge Cases) مثل:
   - مستخدمين بدون قلاع (0 castles).
   - مستخدمين بقلاع معلقة فقط (Pending only).
   - قيم خالية `NULL` في `user_id` أو `state`.
   - حالة تمرير نطاقات فارغة أو مسافات بيضاء في `tenant_domains`.

---

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands to Execute & Expected Results)

### الأمر 1: تشغيل أداة التحقق المستقلة للباك إند
- **الأمر:**
  ```powershell
  python tools/verify_m1_backend.py
  ```
- **النتيجة المتوقعة:**
  نجاح كافة الاختبارات الخمسة (Pass 5/5) وخروج السكربت بكود 0 وطباعة:
  `ALL MILESTONE 1 VERIFICATION TESTS PASSED WITH 100% SUCCESS!`

### الأمر 2: تشغيل أداة القياس المعيارية
- **الأمر:**
  ```powershell
  python tools/benchmark_admin_baseline.py
  ```
- **النتيجة المتوقعة:**
  إتمام الفحص بكود 0 وحفظ نتائج القياس المعياري لخط الأساس دون أخطاء.

### الأمر 3: تشغيل فحص استعلامات الحالات الحدية (Adversarial Null & Edge-Case Check)
- **الأمر:**
  ```powershell
  python -c "import core.database as db; print('Testing edge cases...'); res1 = db.get_all_users_with_castles(tenant_domains=['  ', '']); print('Clean empty domains:', len(res1)); res2 = db.get_all_users_with_castles(); print('Default users count:', len(res2))"
  ```
- **النتيجة المتوقعة:**
  التحقق العملي من سلوك الدالة مع المدخلات الفارغة وحالات النطاقات والتأكد من عدم رمي استثناءات غير متوقعة.
