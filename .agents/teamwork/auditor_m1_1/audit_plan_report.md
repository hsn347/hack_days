# تقرير فني مستقل وخطة التدقيق الجنائي (Milestone 1 Forensic Audit Plan)

**التاريخ والوقت**: 2026-11-02T17:21:00Z  
**المدقق الجنائي**: Forensic Integrity Auditor (`auditor_m1_1`)  
**الهدف**: التدقيق الجنائي المستقل لمخرجات المرحلة الأولى (Backend & SQLite Query Optimization) قبل إصدار الحكم النهائي.  
**مسار الأرتيفاكت**: `C:\Users\Computer Home\.gemini\antigravity\brain\326a0f3a-6204-4bd7-a2a4-8b447bde9ad3\audit_plan_report.md`  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
وفقاً لدستور الوكلاء ووثيقة التكليف الصادرة من المشرف الأعلى، يتطلب إصدار حكم النزاهة (Verdict) التحقق العملي والمستقل من:
1. خلو كود `core/database.py` و `api_server.py` من أي التفاف أو خداع (Hardcoding, Facades, Mocking, Dummy Returns).
2. سلامة قاعدة البيانات المحلية `database/castles.db` فيزيائياً ومنطقياً عبر فحص سلامة SQLite (`PRAGMA integrity_check`).
3. وجود الفهارس الخمسة فعلياً في جدول البيانات التعريفي `sqlite_master` بصيغتها الصحيحة غير الوهمية.
4. تنفيذ أداة التحقق المستقلة `tools/verify_m1_backend.py` والتأكد من مطابقة النتائج للواقع الفعلي لقاعدة البيانات.

تطبيقاً للقاعدة الصارمة رقم 5 في `GEMINI.md`، يتم توثيق هذه الأوامر في هذا التقرير المستقل مسبقاً قبل تشغيل أي أمر.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)

1. **الخطوة الأولى: الفحص الجنائي لسلامة قاعدة البيانات وفهارس `sqlite_master`**:
   - الاتصال بقاعدة البيانات `database/castles.db` محلياً بدون تعديل أي بيانات (Read-Only).
   - تشغيل `PRAGMA integrity_check` للتأكد من عدم وجود أي تلف بالملف.
   - استعلام جدول `sqlite_master` للتأكد من وجود الفهارس الخمسة:
     - `idx_castle_states_lower_email` على `castle_states(LOWER(email))`
     - `idx_castle_states_lower_user` على `castle_states(LOWER(user_id))`
     - `idx_users_lower_email` على `users(LOWER(email))`
     - `idx_users_created_at` على `users(created_at DESC)`
     - `idx_castle_states_created_at` على `castle_states(created_at DESC)`
   - تشغيل `PRAGMA foreign_key_check` للتأكد من الاتساق المرجعي.

2. **الخطوة الثانية: تنفيذ أداة التحقق المستقلة `tools/verify_m1_backend.py`**:
   - تشغيل سكريبت التحقق المستقل عبر بايثون.
   - رصد المخرجات والتحقق من استيفاء كافة الاختبارات الخمسة.

3. **الخطوة الثالثة: التحليل الجنائي المتقدم (AST & Dynamic Behavior Inspection)**:
   - كتابة سكريبت فحص فوري ومستقل يتحقق من:
     - أن استعلام `get_all_users_with_castles()` ينفذ استعلام SQL حقيقي ديناميكي يتأثر بالبيانات (مثلاً: تغير معلمات `tenant_domains` يغير الاستعلام فعلياً وعدد السجلات).
     - أن ميثود `ws_user_status` في `api_server.py` يستدعي فعلياً `asyncio.to_thread` لتنفيذ `get_user_castles`.

---

## 3. الأوامر والملفات التي ستُنفذ بالتفصيل والنتيجة المتوقعة (Commands & Expected Results)

### الأمر الأول: فحص سلامة قاعدة البيانات والفهارس في SQLite
- **الأمر**:
  ```powershell
  python -c "import sqlite3; conn = sqlite3.connect('database/castles.db'); cur = conn.cursor(); print('PRAGMA integrity_check:', cur.execute('PRAGMA integrity_check;').fetchall()); print('PRAGMA foreign_key_check:', cur.execute('PRAGMA foreign_key_check;').fetchall()); cur.execute(\"SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';\"); [print('INDEX:', r) for r in cur.fetchall()]; conn.close()"
  ```
- **النتيجة المتوقعة**:
  - `PRAGMA integrity_check: [('ok',)]`
  - `PRAGMA foreign_key_check: []`
  - طباعة تعريفات الفهارس الخمسة وتطابقها التام مع أسماء الجداول والتعبيرات.

### الأمر الثاني: تشغيل سكريبت التحقق المستقل `tools/verify_m1_backend.py`
- **الأمر**:
  ```powershell
  python tools/verify_m1_backend.py
  ```
- **النتيجة المتوقعة**:
  - اجتياز الاختبارات الخمسة بنجاح 100% مع خروج بكود 0 وطباعة `ALL MILESTONE 1 VERIFICATION TESTS PASSED WITH 100% SUCCESS!`.

### الأمر الثالث: اختبار الفحص الديناميكي لخاصية الفلترة وتتبع الاستعلام
- **الأمر**:
  ```powershell
  python -c "import core.database as db; db._ensure_init(); print('Total users (no filter):', len(db.get_all_users_with_castles())); print('Total users (nonexistent tenant):', len(db.get_all_users_with_castles(['nonexistent.domain'])))"
  ```
- **النتيجة المتوقعة**:
  - بدون فلتر: 152 مستخدم.
  - مع فلتر لنطاق غير موجود: 0 مستخدم (يبرهن بشكل قاطع أن الاستعلام ديناميكي وحقيقي وليس قيمة ثابتة مخزنة).
