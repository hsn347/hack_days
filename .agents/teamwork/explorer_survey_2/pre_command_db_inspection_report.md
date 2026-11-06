# تقرير فني مسبق: فحص بنيوي وقراءة تفصيلية لقاعدة بيانات SQLite المحلية (database/castles.db)

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب
وفقاً لدستور المشروع وقواعد GEMINI.md والمهمة الموكلة للمستكشف 2 (Backend & Database Auditor Explorer)، يُطلب إجراء فحص جنائي شامل لبنية قاعدة البيانات المحلية `database/castles.db`.
الهدف من هذا الفحص هو التحقق المباشر من:
- الجداول الفعلية المنشأة في الملف (`sqlite_master`).
- الفهارس النشطة (Index Coverage) وحجمها وتغطيتها للأعمدة المستعلم عنها بكثرة.
- إعدادات الـ PRAGMA الحالية (مثل journal_mode, synchronous, foreign_keys, cache_size, busy_timeout).
- فحص سلامة وتكامل قاعدة البيانات (`PRAGMA integrity_check`, `PRAGMA foreign_key_check`).
- إحصائيات عدد السجلات وأحجام البيانات في الجداول (`users`, `castle_states`, `system_settings`).

## 2. المنطق والخطوات التي سيتم تطبيقها
1. تشغيل سكريبت بايثون محلي للقراءة فقط (Read-Only) يتصل بـ `database/castles.db` عبر `file:database/castles.db?mode=ro`.
2. استخراج قائمة الجداول، الأعمدة، أنواع البيانات، القيود، والمفاتيح الأساسية والأجنبية.
3. استخراج قائمة الفهارس ومقارنتها بالاستعلامات المستخدمة في `core/database.py` و `api_server.py`.
4. التحقق من إعدادات PRAGMA وسلامة الملف.
5. طباعة النتائج في مخرجات الكونسول دون إجراء أي تعديل أو كتابة في قاعدة البيانات إطلاقاً.

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة
- **الأمر**:
  `python -c "import sqlite3, json; conn = sqlite3.connect('file:database/castles.db?mode=ro', uri=True); conn.row_factory = sqlite3.Row; tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]; print('Tables:', tables); print('--- Integrity Check ---'); print(conn.execute('PRAGMA integrity_check;').fetchall()); print('--- Foreign Key Check ---'); print(conn.execute('PRAGMA foreign_key_check;').fetchall()); print('--- Pragmas ---'); print('journal_mode:', conn.execute('PRAGMA journal_mode;').fetchone()[0]); print('synchronous:', conn.execute('PRAGMA synchronous;').fetchone()[0]); print('foreign_keys:', conn.execute('PRAGMA foreign_keys;').fetchone()[0]); print('--- Table Counts ---'); [print(t, conn.execute(f'SELECT count(*) FROM {t}').fetchone()[0]) for t in tables if not t.startswith('sqlite_')]; print('--- Indexes ---'); [print(r['sql']) for r in conn.execute(\"SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL\")]; conn.close()"`
- **الملفات المتأثرة**: لا يوجد أي تعديل على أي ملف كود أو قاعدة بيانات (الوصول محلي وبنمط القراءة فقط mode=ro).
- **النتيجة المتوقعة**: الحصول على تشريح كامل وموضوعي لحالة قاعدة البيانات الفعلية لدعم التقرير الجنائي.
