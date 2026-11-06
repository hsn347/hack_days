# تقرير فني مستقل مسبق (Technical Report Artifact)
## المرحلة 1: تحسين استعلامات قاعدة البيانات والباك إند (Milestone 1: Backend & DB Optimization)

**التاريخ والوقت:** 2026-11-02T16:47:00Z  
**المرجع:** `GEMINI.md` (البند 5: إلزامية إرفاق ملف تقرير مستقل قبل أي تعديل أو أمر)  
**وثيقة التكليف:** `e:\osmanli\.agents\teamwork\worker_m1\DISPATCH.md`  
**الدستور الحاكم:** `e:\osmanli\AGENTS_CONSTITUTION.md`  
**حالة التقرير:** تم الإعداد والتوثيق قبل أي تعديل على الكود أو تشغيل للأوامر.

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Root Cause)

1. **غياب فهارس التعبيرات وحالة الأحرف (Expression Indexes)**:
   - استعلامات البحث في جدول `castle_states` و `users` تستخدم `LOWER(email)` و `LOWER(user_id)` وفرز `ORDER BY created_at DESC`.
   - محرك SQLite لا يستخدم الفهارس العادية (`idx_castle_email`, `idx_castle_user`) عند تغليف العمود بدالة مثل `LOWER()`، مما يُجبر المحرك على مسح الجدول بالكامل (`SCAN TABLE castle_states`) وإنشاء أشجار فرز مؤقتة (`USE TEMP B-TREE FOR ORDER BY`).
   - الإجراء المطلوب: إنشاء 5 فهارس تعبيرات وحالة أحرف وفرز تنازلي في دالة `init_db()` في `core/database.py`.

2. **اختناق 3N+1 الاستعلامي في `get_all_users_with_castles`**:
   - الدالة الحالية تجلب 154 مستخدماً، ثم تدور في حلقة برمجية لتنفيذ 3 استعلامات منفصلة لكل مستخدم (`SELECT COUNT(*) ...`).
   - هذا يُنتج $1 + (3 \times 154) = 463$ استعلاماً في كل طلب للوحة المسؤول (`/api/admin/users`).
   - الإجراء المطلوب: استبدال الحلقة باستعلام SQL تجميعي واحد باستخدام `LEFT JOIN` و `GROUP BY user_id` لتقليص الاستعلامات من 463 إلى استعلام واحد فقط (تسريع بأكثر من 2.25x مع خلو تام من هدر الذاكرة والاتصالات).

3. **حظر حلقة الـ AsyncIO بالاستعلامات القرصية المتزامنة في WebSockets**:
   - في `api_server.py:3070`، الدالة `ws_user_status` تقوم باستدعاء `db.get_user_castles(user_id)` كل 800ms مباشرة داخل الـ event loop.
   - هذا يعطل معالجة الطلبات المتزامنة والاتصالات الأخرى أثناء قراءة القرص.
   - الإجراء المطلوب: تغليف الاستدعاء التزامني بـ `await asyncio.to_thread(db.get_user_castles, user_id)` لنقله إلى خيوط معالجة منفصلة دون حظر الـ event loop.

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Step-by-Step Implementation)

1. **الخطوة 1: إضافة فهارس SQLite في `core/database.py`**:
   - إضافة أوامر إنشاء الفهارس التالية داخل `init_db()`:
     * `CREATE INDEX IF NOT EXISTS idx_castle_states_lower_email ON castle_states(LOWER(email));`
     * `CREATE INDEX IF NOT EXISTS idx_castle_states_lower_user ON castle_states(LOWER(user_id));`
     * `CREATE INDEX IF NOT EXISTS idx_users_lower_email ON users(LOWER(email));`
     * `CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);`
     * `CREATE INDEX IF NOT EXISTS idx_castle_states_created_at ON castle_states(created_at DESC);`

2. **الخطوة 2: إعادة كتابة `get_all_users_with_castles` في `core/database.py`**:
   - بناء استعلام تجميعي واحد يدمج بيانات `users` مع التجميع من `castle_states`:
     * عد القلاع النشطة `active_cnt`: `SUM(CASE WHEN is_active = 1 AND (state != 'pending' OR state IS NULL) THEN 1 ELSE 0 END)`
     * عد القلاع المعلقة `pending_cnt`: `SUM(CASE WHEN is_active = 0 OR state = 'pending' THEN 1 ELSE 0 END)`
     * إجمالي القلاع `total_cnt`: `COUNT(*)`
   - ربط النتائج بـ `LEFT JOIN` مع `u.uid = c.user_id`.
   - الحفاظ التام على شروط فلترة الإدارة ونطاقات التاجر (`base_where` و `tenant_domains`).
   - إبقاء بنية القواميس الناتجة متطابقة 100% مع الكود السابق:
     * `current_castles_count`
     * `pending_castles_count`
     * `total_castles_count`
     * كائن `subscription` بكامل حقوله المحسوبة.
     * توفير المفاتيح البديلة (`active_castles`, `pending_castles`, `total_castles`) لضمان التوافقية الكاملة.

3. **الخطوة 3: فك حظر الـ Event Loop في `api_server.py`**:
   - في `ws_user_status`، تحويل `_collect_statuses` إلى دالة `async` واستبدال `db.get_user_castles(user_id)` بـ:
     `castles = await asyncio.to_thread(db.get_user_castles, user_id)`
   - استدعاؤها باستخدام `await _collect_statuses()`.

4. **الخطوة 4: التحقق والاختبار**:
   - تشغيل فحص بايثون للتأكد من عدم وجود أخطاء استيراد أو دوال:
     `python -c "import core.database as db; u = db.get_all_users_with_castles(); print('Success! User count:', len(u))"`
   - تشغيل سكربت القياس `python tools/benchmark_admin_baseline.py` للتحقق من اختزال الاستعلامات وسرعة التنفيذ.

---

### 3. الملفات والسطور والأوامر التفصيلية مع النتيجة المتوقعة (Files, Lines & Expected Outcomes)

| الملف | السطور المستهدفة | طبيعة التعديل | النتيجة المتوقعة |
|---|---|---|---|
| `core/database.py` | ~240 (داخل `init_db`) | إضافة أوامر `CREATE INDEX IF NOT EXISTS` لخمسة فهارس جديدة | الاستعلامات عبر `LOWER()` و `ORDER BY created_at DESC` تستخدم B-Tree مباشرة بدلاً من مسح الجدول كاملاً |
| `core/database.py` | 1690 - 1728 | استبدال حلقة الـ 463 استعلاماً باستعلام `LEFT JOIN ... GROUP BY` تجميعي واحد | اختزال عدد الاستعلامات من 463 إلى استعلام واحد فقط مع تسريع الاستجابة بأكثر من 2.25x |
| `api_server.py` | 3063 - 3089 | تحويل استدعاء جلب القلاع في `ws_user_status` إلى `await asyncio.to_thread(db.get_user_castles, user_id)` | تحرير خيط الـ asyncio event loop من حظر استعلامات القرص التزامنية |

**الأوامر التي ستُنفذ للتحقق:**
1. `python -c "import core.database as db; u = db.get_all_users_with_castles(); print('Success! User count:', len(u))"`
2. `python tools/benchmark_admin_baseline.py`
