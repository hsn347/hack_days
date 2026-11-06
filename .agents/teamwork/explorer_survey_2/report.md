# تقرير الفحص الجنائي المعمق للباك إند وقاعدة البيانات وهندسة التزامن والأمان
## Deep Forensic Audit: Backend Architecture, SQLite Database, Concurrency Safety, and Data Isolation
**التاريخ**: 2026-11-02  
**المحقق**: المستكشف 2 (Explorer 2: Backend & Database Auditor Explorer)  
**النطاق**: `core/database.py`, `api_server.py`, `bot_manager.py`, `core/session_manager.py`, `core/tenants.py`, `database/castles.db`  
**المرجع التنظيمي**: `AGENTS_CONSTITUTION.md` & `ORIGINAL_REQUEST.md` (المتطلبات R1, R2, R3, R4, R6, R7, R8)  
**طبيعة الفحص**: قراءة وفحص جنائي محلي 100% (Read-Only) مع قياس خطط تنفيذ الاستعلامات الحقيقية عبر SQLite EXPLAIN QUERY PLAN.

---

## 1. الملخص التنفيذي وبطاقة التقييم الجنائي (Executive Summary & Forensic Scorecard)

أظهر الفحص الجنائي المعمق للباك إند وقاعدة البيانات مجموعة من الاختناقات البنيوية والثغرات الأمنية الحرجة التي تهدد استقرار الخادم وسلامة حسابات المستخدمين. على الرغم من أن النظام يعتمد على SQLite محلية بنمط WAL بدلاً من خدمات سحابية خارجية، إلا أن هناك عيوباً تصميمية جوهرية في استراتيجية الفهرسة، وإدارة المعاملات، والتحكم في الوصول، وتعدد المسارات (Threads):

| المحور الرقابي | الحالة الجنائية | مستوى الخطورة | النتيجة الجنائية المختصرة |
|---|---|---|---|
| **الفهارس واستعلامات قاعدة البيانات** | اختناق شديد | **Critical** | 100% مسح شامل للجدول (`SCAN castle_states`) في معظم الاستعلامات الحيوية بسبب استخدام `LOWER()` متجاوزاً الفهارس، مع غياب الفهارس المركبة لفرز `created_at`. |
| **أنماط الاستعلام المتكررة (N+1)** | اختناق أداء | **High** | مسار لوحة الإدارة يطلق 463 استعلاماً متتالياً لجلب 154 مستخدماً (`1 + 3N queries`). |
| **عزل الحسابات والتحكم في الوصول** | ثغرات حرجة | **P0 - Critical** | تسريب كلمات المرور نصاً صريحاً عبر مسار غير موثق، وإمكانية الاستيلاء على جلسات وقلاع مستخدمين آخرين عبر تزوير المعاملات (BOLA/IDOR). |
| **سلامة التعديلات المتزامنة (Concurrency)** | تحديثات مفقودة | **High** | غياب كامل لـ Optimistic Concurrency Control (OCC) و Versioning مما يؤدي إلى ضياع الإعدادات (Lost Updates) عند الحفظ المتزامن. |
| **إدارة الاتصالات والموارد (Resources)** | استنزاف موارد | **High** | تشغيل Thread مستقل ومحرك `asyncio` منفصل لكل قلعة (500 Threads لـ 500 قلعة)، ونوم مجزأ يوقظ مئات الخيوط كل ثانية، وغياب معالج الإغلاق الآمن. |

---

## 2. المحور الأول: هيكل قاعدة البيانات، الفهارس، وتحسين الاستعلامات (Database Schema & Queries)

### 2.1 تشريح الهيكل الفعلي لقاعدة البيانات (`database/castles.db`)
بناءً على الفحص الميداني المباشر لقاعدة البيانات عبر أداة التحقيق (`tools/inspect_db_schema.py`)، يحتوي الملف الفعلي على:
- **المستخدمين (`users`)**: 154 سجلاً.
- **القلاع (`castle_states`)**: 663 سجلاً.
- **إعدادات النظام (`system_settings`)**: سجل واحد.
- **وضع السجل**: `PRAGMA journal_mode = wal`.
- **فحص التكامل**: `PRAGMA integrity_check` أعاد `ok`.

#### غياب قيود المفاتيح الأجنبية (Missing Foreign Key Constraints):
- جدول `castle_states` يحتوي على عمود `user_id TEXT` ولكنه **لا يحتوي على أي قيد مفتاح أجنبي** (`FOREIGN KEY (user_id) REFERENCES users(uid)`).
- في حال حذف مستخدم، يتم الاعتماد على حذف برمجي يدوي في دالة `delete_user` في `core/database.py:888` بدلاً من الاعتماد على تكامل المحرك `ON DELETE CASCADE`. إذا فشلت المعاملة البرمجية جزئياً، تبقى قلاع "يتيمة" (Orphan Records) في جدول `castle_states` تشغل الذاكرة والمساحة وتسبب ارتباكاً في الإحصائيات.

---

### 2.2 فخ حالة الأحرف والمسح الكامل للجداول (The Case-Sensitivity Index Bypass)
الملاحظة الأكثر خطورة في طبقة الاستعلامات هي أن الفهارس المنشأة في `core/database.py` مبنية كالتالي:
```sql
CREATE INDEX IF NOT EXISTS idx_castle_email ON castle_states(email);
CREATE INDEX IF NOT EXISTS idx_castle_user ON castle_states(user_id);
CREATE INDEX IF NOT EXISTS idx_castle_state ON castle_states(state);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_domain);
```
بينما تقوم شفرة الباك إند في كافة دوال القراءة والتحقق بالاستعلام باستخدام الدالة `lower()`:
```python
# core/database.py:1515
cur = conn.execute("SELECT * FROM castle_states WHERE lower(email) = ? OR lower(castle_id) = ? LIMIT 1", (clean_id, clean_id))

# core/database.py:1349
cur = conn.execute("SELECT castle_id, user_id, last_run_time FROM castle_states WHERE castle_id = ? OR lower(castle_id) = ? OR lower(email) = ? LIMIT 1", ...)

# core/database.py:1047
cur = conn.execute("SELECT * FROM castle_states WHERE user_id = ? OR lower(user_id) = ? ORDER BY created_at DESC", ...)
```

#### الأدلة الجنائية لخطط التنفيذ (EXPLAIN QUERY PLAN Results):
أثبت القياس الفعلي عبر محرك SQLite أن هذه الاستعلامات **تتجاهل الفهارس بالكامل وتقوم بمسح كامل لكل سجلات الجدول (Full Table Scan)**:
1. **استعلام جلب القلعة بالبريد أو المعرف**:
   - الاستعلام: `EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE lower(email) = '...' OR lower(castle_id) = '...' LIMIT 1`
   - الخطة الناتجة: `SCAN castle_states` (مسح 663 صفاً صفاً فصفاً في كل طلب).
2. **استعلام فحص تحديث حالة الاتصال (`upsert_castle_conn_state`)**:
   - الاستعلام: `EXPLAIN QUERY PLAN SELECT castle_id, user_id, last_run_time FROM castle_states WHERE castle_id = '...' OR lower(castle_id) = '...' OR lower(email) = '...' LIMIT 1`
   - الخطة الناتجة: `SCAN castle_states` (يُستدعى هذا الاستعلام عشرات المرات في الدقيقة من كافة خيوط البوتات النشطة، وكل استدعاء يمسح الجدول كاملاً!).
3. **استعلام جلب قلاع المستخدم (`get_user_castles`)**:
   - الاستعلام: `EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE user_id = '...' OR lower(user_id) = '...' ORDER BY created_at DESC`
   - الخطة الناتجة: `SCAN castle_states` متبوعاً بـ `USE TEMP B-TREE FOR ORDER BY` (إنشاء شجرة فرز مؤقتة في الذاكرة لكل مستخدم يفتح لوحة التحكم!).
4. **استعلام إحصائيات التجار الشاملة (`get_merchants_overview_stats`)**:
   - الاستعلام: `EXPLAIN QUERY PLAN ... FROM castle_states c JOIN users u ON u.uid = c.user_id WHERE LOWER(u.tenant_domain) IN (...)`
   - الخطة الناتجة: `SCAN c` (مسح كامل لجدول القلاع `castle_states`).

---

### 2.3 نمط الاستعلام المتكرر N+1 في لوحة تحكم المسؤول (N+1 Query Pattern)
في `core/database.py`، الدالة `get_all_users_with_castles` (السطور 1690-1728) المسؤولة عن تغذية صفحة المستخدمين للمشرف (`/api/admin/users`):
```python
def get_all_users_with_castles(tenant_domains=None, db_path=None):
    users = get_all_users(tenant_domains=tenant_domains, db_path=db_path) # استعلام 1
    with get_connection(db_path) as conn:
        for u in users: # حلقة تدور 154 مرة!
            uid = u["uid"]
            row_a = conn.execute("SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND is_active = 1 AND state != 'pending'", (uid,)).fetchone() # استعلام 2
            row_p = conn.execute("SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND (is_active = 0 OR state = 'pending')", (uid,)).fetchone() # استعلام 3
            row_t = conn.execute("SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ?", (uid,)).fetchone() # استعلام 4
```
- **الحساب الجنائي**:
  - عدد المستخدمين: 154 مستخدماً.
  - عدد الاستعلامات المنفذة في كل زيارة لصفحة الإدارة:
    $$\text{Total Queries} = 1 + (3 \times 154) = 463 \text{ استعلاماً متتالياً!}$$
  - كل استعلام من الـ 462 استعلاماً الفرعية يفتح قفلاً للقراءة ويغلقه.
  - **الحل الجذري**: استبدال هذه الحلقة باستعلام تجميعي واحد (`GROUP BY user_id` مع `COUNT(CASE ...)` و `LEFT JOIN`) يُقلص عدد الاستعلامات من 463 استعلاماً إلى استعلام واحد فقط بزمن تنفيذ < 2 ميلي ثانية.

---

### 2.4 استعلامات غير محددة (Unbounded SELECTs Without LIMIT/OFFSET)
تخلو المسارات الحيوية للبيانات من أي تحديد لحجم النتائج (Pagination / Limits):
1. `db.get_all_castles()` (`core/database.py:1550`): ينفذ `SELECT * FROM castle_states ORDER BY email ASC` بدون `LIMIT` أو `OFFSET`. يعيد جميع الـ 663 قلعة بما فيها الحقول النصية الضخمة (`config` الذي يتجاوز حجمه 4 كيلوبايت لكل سجل، و `raw_json`).
2. `db.get_all_users()` (`core/database.py:438`): ينفذ `SELECT * FROM users ORDER BY created_at DESC` بدون تحديد.
3. `/api/admin/users-castles` (`api_server.py:1635`): يدمج في الذاكرة جميع المستخدمين مع جميع القلاع الـ 663 في استجابة JSON واحدة تتجاوز 1.5 ميغابايت لكل طلب.
4. `/api/castles` (`api_server.py:1007`): يعيد جميع قلاع المستخدم دفعة واحدة دون إمكانية التصفح بالصفحات.

---

### 2.5 دورة حياة الاتصالات وغياب التجميع (Connection Lifecycle & Connection Pooling)
- **غياب التجميع (No Connection Pool)**: في `core/database.py:64`، كل دالة في التطبيق تستدعي سياق `get_connection()` الذي يقوم في كل مرة بـ:
  1. إنشاء مقبس واتصال نظام تشغيل جديد عبر `sqlite3.connect(path, timeout=10.0)`.
  2. تنفيذ 4 أوامر PRAGMA في كل اتصال:
     - `PRAGMA journal_mode = WAL;` (أمر ثقيل يتحقق من ملف الـ WAL ويحصل على قفل حصري لحظي، رغم أن WAL خاصية مستمرة لا تحتاج إعادة تعيين مع كل اتصال).
     - `PRAGMA synchronous = NORMAL;`
     - `PRAGMA busy_timeout = 5000;`
     - `PRAGMA foreign_keys = ON;`
  3. تنفيذ الاستعلام وإغلاق الاتصال وتحريره.
- **تأثير ذلك تحت الضغط**: عندما ينتهي 30 بوتاً من دورتهم في نفس اللحظة ويحاولون تسجيل الموارد وحالة الاتصال، يتم فتح 30 اتصالاً متزامناً وكل اتصال يحاول التحقق من وضع WAL، مما يتسبب في تصادمات `sqlite3.OperationalError: database is locked`.

---

### 2.6 حظر مسار الـ Event Loop غير المتزامن (Event Loop Blocking in WebSockets)
في `api_server.py`، خادم الويب مبني على FastAPI غير المتزامن (`asyncio`)، لكن دوال الـ WebSockets تستدعي دوال SQLite المتزامنة مباشرة داخل حلقة الأحداث الرئيسية:
```python
# api_server.py:3063
@app.websocket("/ws/user-status/{user_id}")
async def ws_user_status(websocket: WebSocket, user_id: str):
    await websocket.accept()
    def _collect_statuses() -> Dict[str, str]:
        res = {}
        try:
            castles = db.get_user_castles(user_id) # دالة SQLite متزامنة تحظر الـ Thread!
            for c in castles:
                cid = c.get("castle_id")
                if cid:
                    res[cid] = _get_real_status(cid)
        except Exception:
            pass
        return res

    while True:
        await asyncio.sleep(0.8)
        curr_data = _collect_statuses() # تُنفذ كل 800 ميلي ثانية لكل عميل متصل!
```
- **المصيبة الجنائية**:
  - دالة `db.get_user_castles` تستغرق وقتاً لأنها تجري `SCAN castle_states` وفرز `ORDER BY created_at DESC`.
  - بما أن هذا الاستدعاء متزامن ويجري داخل دالة الـ WebSocket غير المتزامنة، فإنه **يُجمد الـ Event Loop الرئيسي** للخادم بالكامل كل 800 ميلي ثانية لكل متصفح مفتوح.
  - إذا كان هناك 20 مستخدماً يراقبون شاشاتهم، فإن الـ Event Loop يُقضي معظم وقته في انتظار I/O متزامن لقاعدة البيانات، مما يؤخر كافة استجابات واجهات برمجة التطبيقات (API Delays).
  - نفس الكارثة تتكرر في `ws_logs` (`api_server.py:2997`) حيث يجري استعلام متزامن داخل دالة الـ WebSocket.

---

## 3. المحور الثاني: سلامة التعديلات المتزامنة وتكامل البيانات (Concurrency Safety & Mutations)

### 3.1 سباق التحديث وضياع الإعدادات (Race Conditions & Lost Updates)
في `core/database.py`، دالة `update_castle_config` (السطور 1150-1188):
```python
def update_castle_config(castle_id: str, config_dict: Dict[str, Any], user_id: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    with get_connection(db_path) as conn:
        # خطوة 1: قراءة الإعدادات الحالية من القاعدة
        cur = conn.execute("SELECT config FROM castle_states WHERE castle_id = ?", (castle_id,))
        row = cur.fetchone()
        current_config = json.loads(row["config"]) if row and row["config"] else {}

        # خطوة 2: دمج التعديلات في ذاكرة بايثون
        merged_config = _sanitize_castle_config(_deep_merge_dict(current_config, config_dict))
        config_json = json.dumps(merged_config, ensure_ascii=False)

        # خطوة 3: كتابة الإعدادات المدمجة
        conn.execute("UPDATE castle_states SET config = ?, last_updated = ? WHERE castle_id = ?", (config_json, now, castle_id))
        conn.commit()
```
#### سيناريو حدوث ضياع البيانات (Lost Update Trace):
1. **اللحظة $T_0$**: المستخدم يقوم بتعديل إعداد "المشفى" (تفعيل علاج الجنود) في المتصفح. ترسل الواجهة طلب `PUT /api/castles/{id}`. الدالة تقرأ الإعدادات الحالية $C_0$.
2. **اللحظة $T_1$**: في نفس الوقت، المستخدم يقوم بتبديل خيار "مهاجمة الغزاة" (Auto-save toggle). ترسل الواجهة طلباً ثانياً يقرأ الإعدادات $C_0$ أيضاً قبل أن يكتمل الطلب الأول.
3. **اللحظة $T_2$**: الطلب الأول يدمج إعداد المشفى ويكتب $C_1$ في القاعدة ويعمل Commit.
4. **اللحظة $T_3$**: الطلب الثاني يدمج إعداد الغزاة فوق النسخة القديمة $C_0$ (التي لا تحتوي على تفعيل المشفى)، ويكتب $C_2$ فوق $C_1$!
5. **النتيجة**: تعديل إعداد المشفى **ضاع بالكامل (Lost Update)** دون أي خطأ ظاهر للمستخدم!

---

### 3.2 غياب التحكم بالتزامن المتفائل والتحقق من الإصدارات (Lack of OCC & Versioning)
- جدول `castle_states` **لا يحتوي على عمود إصدار (`version INTEGER DEFAULT 1`)**.
- لا توجد آلية Optimistic Concurrency Control (OCC) مثل:
  ```sql
  UPDATE castle_states 
  SET config = ?, version = version + 1 
  WHERE castle_id = ? AND version = ?;
  ```
- لا يتم استخدام معاملات فورية مانعة للقراءة غير المتزامنة (`BEGIN IMMEDIATE`). في بايثون `sqlite3`، نوع المعاملة الافتراضي هو `DEFERRED`، مما يعني أن الاتصال لا يحصل على قفل كتابة حتى تنفيذ أمر `UPDATE`، مما يفتح نافذة زمنية واسعة للقراءات المتضاربة.

---

### 3.3 غياب معالجة الطلبات غير المرتبة (Out-of-Order Requests) وغياب الـ Idempotency
- لا توجد ترويسات أو مفاتيح Idempotency في طلبات الحفظ (`Idempotency-Key` أو `request_timestamp`).
- في حال تأخر أحد الطلبات عبر الشبكة (Network Jitter)، فإن وصول طلب قديم بعد طلب حديث يؤدي إلى كتابة الحالة القديمة فوق الحديثة دون أي آلية رفض أو تحقق زمني.

---

## 4. المحور الثالث: عزل الحسابات والتحكم في الوصول والأمان (Multi-Account Isolation & Access Control)

### 4.1 🚨 الثغرة الكارثية الأولى: تسريب كلمات المرور عبر مسار مفتوح بدون مصادقة (Plaintext Password Leak)
- **المسار المتأثر**: `GET /api/local/castles/{identifier}` في `api_server.py:2767`.
- **كود المسار**:
  ```python
  @app.get("/api/local/castles/{identifier}")
  def get_local_castle(identifier: str):
      c = db.get_castle(identifier)
      if not c:
          raise HTTPException(status_code=404, detail="Castle not found in local database")
      return {"castle": c}
  ```
- **الكود المستدعى في قاعدة البيانات**:
  ```python
  # core/database.py:1502
  def get_castle(identifier: str, db_path: Optional[str] = None):
      ...
      with get_connection(db_path) as conn:
          cur = conn.execute("SELECT * FROM castle_states WHERE lower(email) = ? OR lower(castle_id) = ? LIMIT 1", (clean_id, clean_id))
          row = cur.fetchone()
          if row:
              return dict(row) # ⚠️ يعيد كل الأعمدة بما فيها password دون تصفية!
  ```
- **التحليل الأمني الجنائي**:
  1. المسار **لا يحتوي على أي تبعية مصادقة (`Depends(get_current_user)`) على الإطلاق**!
  2. الدالة `db.get_castle` تنفذ `SELECT *` وتعيد القاموس كاملاً محتوياً على عمود `password` بنصه الصريح. (بينما في `get_user_castles` و `get_castle_by_id` تم حذف كلمة المرور عبر `d.pop("password", None)`، لكن في `get_castle` تم نسيانها تماماً!).
  3. أي شخص على الشبكة المحلية أو الإنترنت (في حال كشف المنفذ أو تجاوز الوكيل العكسي) يستطيع إرسال طلب `GET /api/local/castles/victim@email.com` والحصول فوراً على:
     - كلمة مرور الحساب الصريحة (`password`).
     - إحداثيات القلعة (`coord_x`, `coord_y`).
     - الموارد والذهب وقوة اللورد ومستوى القلعة.
     - كامل إعدادات البوت والتشكيلات.
- **التصنيف**: **CWE-200: Exposure of Sensitive Information to an Unauthorized Actor / P0 - CRITICAL**.

---

### 4.2 🚨 الثغرة الكارثية الثانية: انتحال الحسابات وسرقة بيانات القلاع الحية (BOLA/IDOR in Live Castle Data)
- **المسار المتأثر**: `GET /api/castle-data/{email}` في `api_server.py:2776`.
- **كود المسار**:
  ```python
  @app.get("/api/castle-data/{email}")
  async def get_castle_data(email: str, user_id: Optional[str] = None, castle_id: Optional[str] = None, current_user: Dict[str, Any] = Depends(get_current_user)):
      sm = SessionManager()
      account = sm.get_or_login(email=email, user_id=user_id, castle_id=castle_id)
      ...
      conn = GameConnection(account)
      ok = await asyncio.wait_for(conn.connect(), timeout=15)
      ...
  ```
- **التحليل الأمني الجنائي**:
  1. المسار يتطلب توكن مصادقة (`Depends(get_current_user)`).
  2. **لكن المسار لا يتحقق إطلاقاً من أن الـ `email` المطلوب يخص المستخدم صاحب التوكن (`current_user["uid"]`)**!
  3. يمكن لأي مستخدم عادي يمتلك حساباً مجانياً بسيطاً أن يرسل بريد أي قلعة أخرى في المنصة (`GET /api/castle-data/victim@target.com`).
  4. خادم الـ API سيقوم فوراً بـ:
     - استخراج الجلسة المخزنة للضحية من `session_cache.json` أو استخراج كلمة مرور الضحية من `castles.db` وتسجيل دخوله.
     - الاتصال بسيرفرات اللعبة الحية باستخدام حساب الضحية وطرد اللاعب الحقيقي من اللعبة (`kick / other device login`)!
     - استخراج كافة بيانات الضحية (الذهب، الموارد المحمية وغير المحمية، القوة، الإحداثيات) وإعادتها للمهاجم في استجابة الـ HTTP!
- **التصنيف**: **CWE-639: Authorization Bypass Through User-Controlled Key (IDOR/BOLA) / P0 - CRITICAL**.

---

### 4.3 🚨 الثغرة الكارثية الثالثة: تزوير البريد واختطاف الجلسات في تشغيل البوت (Parameter Spoofing in Bot Start)
- **المسار المتأثر**: `POST /api/bot/start` في `api_server.py:2590`.
- **التحليل الجنائي**:
  ```python
  class StartBotRequest(BaseModel):
      castle_id: str
      user_id: str
      email: str
      ...

  @app.post("/api/bot/start")
  def start_bot(req: StartBotRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
      caller_uid = current_user.get("uid", "")
      ...
      if not is_admin and caller_uid != req.user_id:
          raise HTTPException(status_code=403, detail="غير مصرح بتشغيل قلاع مستخدم آخر")
      
      c_info = db.get_castle_by_id(req.castle_id, None if is_admin else caller_uid)
      if not c_info:
          raise HTTPException(status_code=404, detail="القلعة غير موجودة")
      
      started = _start_bot_internal(req)
  ```
  1. الكود يتحقق من أن `req.castle_id` يخص `caller_uid` (السطر 2616).
  2. **لكنه لا يتحقق إطلاقاً من أن `req.email` يطابق `c_info["email"]`**!
  3. يمرر كائن `req` كما هو إلى `_bot_thread(req)`، وهناك:
     ```python
     # api_server.py:646
     account = sm.get_or_login(
         email=req.email, # ⚠️ البريد المزور من جسم الطلب وليس بريد القلعة الحقيقي من DB!
         password=password,
         user_id=user_id,
         castle_id=castle_id,
     )
     ```
  4. إذا أدخل المهاجم معرف قلعته الخاصة المصرح له بها، لكنه وضع في حقل `email` بريد قلعة مستخدم آخر:
     - `SessionManager` يبحث في `session_cache.json` المشترك عن بريد الضحية، فيجد جلسة صالحة ويشغل البوت بحساب الضحية تحت مظلة قلعة المهاجم!
- **التصنيف**: **Parameter Tampering / Session Hijacking / P0 - CRITICAL**.

---

### 4.4 🚨 الثغرة الرابعة: 10 مسارات داخلية حساسة مكشوفة بدون أي حماية (Unprotected Internal API Endpoints)
المسارات التالية في `api_server.py` معرّفة بدون أي تبعية مصادقة وبدون أي تحقق من عنوان الـ IP للعميل:
1. `POST /api/internal/stop-all` (`api_server.py:2394`): يمكن لأي زائر على الإنترنت إيقاف كافة بوتات السيرفر وإلغاء تشغيلها وتصفير حالتها في DB.
2. `POST /api/internal/restart-all` (`api_server.py:2472`): يمكن لأي شخص إجبار السيرفر على إعادة تشغيل جميع البوتات.
3. `POST /api/internal/direct-start` (`api_server.py:2574`): يسمح بتشغيل أي بوت دون توكن. التوثيق يزعم أنه يقبل فقط من `127.0.0.1`، ولكن **لا يوجد سطر كود واحد يتحقق من `request.client.host`**!
4. `POST /api/internal/deploy-lock` & `deploy-unlock` (`api_server.py:2152, 2164`): إقفال وفتح وضع النشر.
5. `POST /api/internal/gradual-start` (`api_server.py:2354`): إطلاق التشغيل التدريجي الجماعي.
6. `POST /api/internal/cancel-start-queue` (`api_server.py:2446`).
7. `POST /api/internal/save-running-state` (`api_server.py:2058`).
8. `GET /api/internal/debug-state` (`api_server.py:2138`): يسرب أسماء الخيوط النشطة وجميع معرفات القلاع والمستخدمين في الذاكرة.
9. `POST /api/bot/conn-state` (`api_server.py:2748`): تزوير حالة اتصال أي قلعة.
10. `POST /api/user/register` (`api_server.py:960`): يسمح بتسجيل مستخدمين جدد مباشرة بدون توكن Firebase أو التحقق من صحة البريد.

---

## 5. المحور الرابع: تسريب الموارد، وإدارة العمليات طويلة الأمد (Resource Leaks & Scalability)

### 5.1 معضلة معمارية Thread-Per-Castle واستهلاك الذاكرة
في `api_server.py:2051`:
```python
t = threading.Thread(target=_bot_thread, args=(req,), daemon=True, name=f"bot-{req.castle_id[:10]}")
t.start()
```
وداخل كل Thread:
```python
# api_server.py:816
asyncio.run(manager.run_loop(loop_interval_minutes=req.loop_interval))
```
- **التشخيص الجنائي**:
  1. النظام ينشئ Thread مستقلاً في نظام التشغيل لكل قلعة تعمل.
  2. كل خيط يقوم بتشغيل محرك حلقة أحداث كامل خاص به (`asyncio.run()`).
  3. إذا كان هناك 500 قلعة نشطة، فهذا يعني وجود **500 خيط نظام تشغيل + 500 حلقة أحداث asyncio متزامنة** تتنافس جميعها على قفل بايثون العام (GIL).
  4. هذا النمط يهدر مئات الميغابايت من ذاكرة المكدس (Thread Stack Memory) ويجعل تبديل السياق (Context Switching) حملاً هائلاً على المعالج.

---

### 5.2 الاستيقاظ المفرط في وضع الانتظار (Busy Waiting Wakeup Storm)
في `bot_manager.py:3763-3765`:
```python
sleep_step = 1.0
slept = 0.0
while slept < remaining and not self._stop_event.is_set():
    await asyncio.sleep(min(sleep_step, remaining - slept))
    slept += sleep_step
```
- **التشخيص الجنائي**:
  - عندما تنتظر القلعة 25 أو 60 دقيقة بين الدورة والأخرى، الكود لا ينام بالكامل، بل يستيقظ **كل ثانية واحدة بالضبط** ليتحقق من `self._stop_event.is_set()`.
  - مع وجود 200 قلعة في وضع الانتظار، هناك **200 استيقاظ للخيوط في الثانية الواحدة** على الـ Event Loop، مما يتسبب في استهلاك غير مبرر للمعالج حتى أثناء خمول البوتات تماماً!
  - **الحل الجذري**: استخدام حدث غير متزامن `await self._async_stop_event.wait(timeout=remaining)`، والذي يسمح بالنوم المستمر لـ 60 دقيقة كاملة مع الاستيقاظ الفوري في صفر ميلي ثانية فور إطلاق إشارة الإيقاف، دون الحاجة لأي حلقة استيقاظ دورية.

---

### 5.3 تسريب المقابس والمهام غير المدارة (Socket & Background Task Leaks)
1. **عدم انتظار إغلاق المقبس (`wait_closed()`)**:
   في `game_client.py:614`:
   ```python
   async def close(self):
       self._explicit_close = True
       self._alive = False
       self.abort()
       if self._writer:
           try:
               self._writer.close()
           except Exception:
               pass
   ```
   استدعاء `self._writer.close()` يضع علامة على المقبس للإغلاق، ولكنه **لا ينتظر اكتمال إغلاق الـ TCP Handshake عبر `await self._writer.wait_closed()`**. هذا يترك واصفات الملفات (File Descriptors) معلقة لفترة في نظام التشغيل ويؤدي لظهور تحذيرات `ResourceWarning: unclosed transport`.
2. **إطلاق مهام متطايرة بدون تتبع (Untracked Background Tasks)**:
   في `game_client.py:501, 508, 338`:
   ```python
   asyncio.create_task(self._notifies[nid](c))
   asyncio.create_task(listener(cmd, sub, c))
   asyncio.create_task(self.on_disconnect(self.kick_reason))
   ```
   يتم إطلاق مهام عبر `asyncio.create_task` بدون الاحتفاظ بمرجع (Strong Reference) لها. في بايثون 3.8+، هذا يعرض المهام للجمع القسري للقمامة (Garbage Collection) أثناء تنفيذها، وإذا حدث استثناء داخل المهمة يتم كتمه كـ "Task exception was never retrieved".
3. **غياب خطاف الإغلاق النظيف في FastAPI (Missing Shutdown Hook)**:
   في `api_server.py:3199-3218`:
   - يوجد `@app.on_event("startup")`، ولكنه **يخلو تماماً من `@app.on_event("shutdown")`**!
   - عند إعادة تشغيل خدمة السيرفر (`systemctl restart` أو إيقاف uvicorn)، يتم قتل الخادم فوراً وخيوط البوتات تعمل (`daemon=True`)، مما يقطع اتصالات اللعبة فجأة دون إرسال حزم تسجيل الخروج، ويترك سجلات WAL في SQLite في حالة غير مفرغة.

---

### 5.4 تسريب الذاكرة وتراكم السجلات في `api_server.py`
1. **تراكم المعرفات في `_castle_emails`**:
   في `api_server.py:627`، يتم تخزين `_castle_emails[castle_id] = email`. وفي كتلة `finally` (السطور 829-839)، يتم استئصال كافة الهياكل ما عدا `_castle_emails` التي تم نسيانها تماماً، فتظل تتراكم في الذاكرة عبر آلاف الدورات.
2. **سرقة سجلات الـ WebSocket وفقدانها (Log Queue Stealing)**:
   في `api_server.py:3028`:
   ```python
   line = q.get_nowait()
   await websocket.send_text(line)
   ```
   `q.get_nowait()` يسحب السطر ويحذفه من الـ Queue. إذا فتح المستخدم نافذتين أو تبويبين لمراقبة نفس البوت، تتقاسم النافذتان أسطر السجل بالتناوب (النافذة 1 تأخذ الأسطر الفردية والنافذة 2 تأخذ الزوجية!)، وتضيع نصف الرسائل عن كل شاشة!

---

## 6. مصفوفة المشاكل وخطة الإصلاح الهندسية المقترحة (Engineering Remediation Matrix)

| المعرف | المشكلة المرصودة | التصنيف | الملف والسطور المتأثرة | الإصلاح الهندسي المقترح |
|---|---|---|---|---|
| **BUG-01** | مسار غير مصرح يسرب كلمات المرور صراحة | **P0 - Critical** | `api_server.py:2767`, `core/database.py:1502` | حذف مسار `/api/local/castles/{id}` أو حمايته بتوثيق المشرف الأعلى مع حذف حقل `password` دائماً عبر `d.pop("password", None)`. |
| **BUG-02** | ثغرة BOLA/IDOR في جلب بيانات القلاع الحية | **P0 - Critical** | `api_server.py:2776` | إضافة فحص صارم: التحقق من أن القلعة والبريد يخصان `current_user["uid"]` حصراً ما لم يكن الطالب مشرفاً. |
| **BUG-03** | انتحال البريد في تشغيل البوت لتجاوز العزل | **P0 - Critical** | `api_server.py:2590, 646` | استخراج البريد من السجل الموثق في قاعدة البيانات `c_info["email"]` حصراً وتجاهل أي بريد ممرر في جسم الطلب. |
| **BUG-04** | مسارات داخلية حساسة مكشوفة بدون توثيق | **P0 - Critical** | `api_server.py:2058-2580` | حظر كافة مسارات `/api/internal/*` إلا برمز مرور سري محلي أو حصرها بـ `request.client.host == '127.0.0.1'`. |
| **PERF-01** | استعلامات تتجاوز الفهارس وتجري Full Table Scan | **Critical** | `core/database.py:1515, 1349, 1047` | إضافة فهارس غير حساسة للأحرف (`COLLATE NOCASE` أو Functional Indexes: `CREATE INDEX idx_cs_lower_email ON castle_states(lower(email))`). |
| **PERF-02** | فرز بطيء بالذاكرة المؤقتة `USE TEMP B-TREE` | **High** | `core/database.py:1047` | إضافة فهرس مركب: `CREATE INDEX idx_cs_user_created ON castle_states(user_id, created_at DESC)`. |
| **PERF-03** | نمط N+1 يولد 463 استعلاماً في صفحة الإدارة | **High** | `core/database.py:1690` | استبدال الـ 463 استعلاماً باستعلام تجميعي واحد (`GROUP BY user_id` مع Conditional Aggregation). |
| **PERF-04** | تجميد الـ Event Loop عبر دوال متزامنة في WebSockets | **High** | `api_server.py:3063, 2989` | تفويض قراءة SQLite إلى threadpool عبر `asyncio.to_thread(db.get_user_castles, user_id)` أو استخدام الكاش الحي. |
| **CONC-01** | ضياع التعديلات المتزامنة (Lost Updates) | **High** | `core/database.py:1150` | تطبيق OCC بإضافة عمود `version` في `castle_states` واستخدام `BEGIN IMMEDIATE` لحماية دورة القراءة والدمج والكتابة. |
| **RES-01** | معمارية Thread-per-castle والاستيقاظ كل ثانية | **High** | `bot_manager.py:3763`, `api_server.py:2051` | استبدال النوم المجزأ بـ `await self._async_stop_event.wait(timeout=delay)` لمنع الاستيقاظ المفرط أثناء الخمول. |
| **RES-02** | غياب خطاف الإغلاق النظيف في FastAPI | **Medium** | `api_server.py:3199` | إضافة `@app.on_event("shutdown")` لإيقاف جميع المقابس وتفريغ سجل WAL وكتابة الحالات النهائية بأمان. |
| **RES-03** | سرقة سجلات الـ WebSocket عند فتح أكثر من تبويب | **Medium** | `api_server.py:3028` | استخدام نمط Pub/Sub (قائمة مشتركة أو ring buffer) بدلاً من تفريغ `Queue.get_nowait()` الحصري. |
