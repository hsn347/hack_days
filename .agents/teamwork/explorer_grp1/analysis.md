# التحليل الجراحي الشامل لملفي `tasks/base_task.py` و `tasks/march_coordinator.py`
## تقرير الفحص التصادمي والهندسي المجهري (Adversarial Microscopic Code Dissection)

---

## 1. الملخص التنفيذي ونطاق الفحص (Executive Summary & Scope)

تم إجراء فحص تصادمي مجهري (Adversarial Code Audit) للملفين الأساسيين المسؤولين عن إدارة الفيالق والمسيرات الخارجية في مشروع البوت:
1. `tasks/base_task.py` (العقد المشترك لجميع مهام البوت، الكلاس الأساسي `BaseTask`، كلاس النتائج `TaskResult`، كلاس الحالة `TaskState`، وكلاس الجدولة `TaskScheduler`).
2. `tasks/march_coordinator.py` (محرك منسق الفيالق الموحد `MarchCoordinatorTask`، بروتوكول الإجراءات `CoordinatorAction`، ومعالجات الأولويات العشر `Priority 1..10`).

تم تدقيق كل سطر برمجي، وكل تفريع شرطي (`if / elif / else`)، وكل استعلام شبكي (`cmd / subcmd`)، وكل مفتاح ذاكرة حية (`init_data`)، وكافة سلوكيات أكواد الخطأ العشرين الصادرة عن خادم اللعبة، ومصفوفات إعدادات المستخدم، والتناقضات المعمارية بين العقد المشترك والمنسق.

---

## 2. التشريح المجهري لكود `tasks/base_task.py`

### 2.1 الهيكل العام والتسلسل الهرمي (Class Hierarchy & Architecture)
الملف يمثل الأساس الهيكلي (Abstract Base Architecture) لكافة مهام المشروع:
- `TaskState(str, Enum)`: تمثيل حالات دورة حياة المهمة (`IDLE`, `RUNNING`, `WAITING`, `STOPPED`, `ERROR`).
- `TaskResult`: كائن نتيجة تنفيذ المهمة الموحد القائم على `dataclass`.
- `PRESTIGE_QUEST_IDS`: قاموس معرفات مهام الهيبة اليومية على مستوى الوحدة.
- `BaseTask(ABC)`: كلاس مجرد يرث من `ABC`، يوفر طبقة خدمات متكاملة لقراءة الذاكرة الحية (Zero-Request) وتنفيذ استعلامات الشبكة الاحتياطية وإدارة القوات والأبطال والحيوانات والرونات وتأمين الأهداف.
- `TaskScheduler`: مجدول مهام دوري غير متزامن مبني على `asyncio.wait_for` و `asyncio.Event`.

---

### 2.2 جدول المدخلات والإعدادات (`config`) والأنواع والقيم الافتراضية

| المفتاح (Config Key) | النوع البرمجي (Type) | القيمة الافتراضية (Default) | التحقق المنطقي ومعالجة الأخطاء (Validation & Fallback) | الدالة المستخدمة |
| :--- | :--- | :--- | :--- | :--- |
| `conn` | `GameConnection` | إلزامي | يتم التحقق من وجوده والتحقق من `conn.is_connected` ووجود `init_data` | `__init__` |
| `config` | `Optional[Dict[str, Any]]` | `{}` | يتم إسناده كقاموس فارغ إن كان `None` | `__init__` |
| `center_x` / `x` | `int` أو `str` أو `None` | `None` | فحص `is not None` ثم تحويله عبر `int(cx)`. في حال الفشل (`ValueError`, `TypeError`) يتم التراجع للذاكرة الحية | `get_castle_coords` |
| `center_y` / `y` | `int` أو `str` أو `None` | `None` | فحص `is not None` ثم تحويله عبر `int(cy)`. في حال الفشل يتم التراجع للذاكرة الحية | `get_castle_coords` |
| `max_queues` | `int` | `None` | قراءة اختيارية لسقف الطوابير المسموح به للقلعة | `get_max_marches_capacity` |
| `formation_id` | `int` | `1` | التحقق من `formation_id > 0`. إن كان `<= 0` تعود الدالة بقوائم وقواميس فارغة | `get_formation`, `get_march_army` |
| `form_heroes` | `Optional[Any]` | `None` | يقبل قائمة `list` أو قاموس `dict` أو أرقام فردية، ويتم تسطيحه `flat_form` واستخراج المعرفات الرقمية | `get_combat_heroes` |
| `max_count` | `int` | `2` | عدد الأبطال المطلوب اختيارهم (افتراضياً 2 لمسيرة القتال) | `get_combat_heroes` |
| `exclude_busy` | `Optional[Set[int]]` | `None` | مجموعة معرفات الأبطال/الحيوانات المشغولة لاستبعادها | `get_combat_heroes`, `select_combat_pet` |
| `fallback_count` | `int` | `0` | عدد الجنود الاحتياطي في حال عدم وجود تشكيلة نهائياً | `get_march_army` |
| `max_capacity` | `Optional[int]` | `None` | السقف الأقصى لسعة مسيرة اللورد. إن كان `> 0` ومجموع التشكيلة أكبر منه يتم تقليص التشكيلة نسبياً `scale` | `get_march_army` |

---

### 2.3 كلاسات البنية الأساسية (`TaskState` و `TaskResult`)

#### أ. `TaskState(str, Enum)`
- `IDLE = "idle"`: حالة المهمة الأولية قبل تشغيلها.
- `RUNNING = "running"`: تم الدخول في `_execute()` وبدء تنفيذ `run()`.
- `WAITING = "waiting"`: انتهى تنفيذ الجولة بنجاح والمهمة تنتظر انتهاء مهلة `interval` أو `retry_after`.
- `STOPPED = "stopped"`: تم استدعاء `stop()` وتعيين حدث `_stop_event`.
- `ERROR = "error"`: رمى تنفيذ `run()` استثناءً غير معالج (`Exception`) وتم التقاطه في `_execute()`.

#### ب. `TaskResult` (محددات الحقول والدوال المساعدة)
- الحقول:
  * `success: bool`: نجاح أو فشل الجولة.
  * `message: str`: نص توضيحي للنتيجة.
  * `data: Dict[str, Any] = field(default_factory=dict)`: وعاء البيانات المرجعة (مثل `sent`, `stop_reason`, `status`, `action`).
  * `should_retry: bool = False`: مؤشر طلب إعادة المحاولة.
  * `retry_after: int = 0`: مهلة الانتظار بالثواني قبل إعادة المحاولة.
  * `action: Optional[str] = None`: الإجراء التوجيهي للمنسق (`CoordinatorAction`).
- الدوال المصنعية والخصائص:
  * `ok(cls, message="✅ تم بنجاح", action=None, **data)`: ينشئ كائناً ناجحاً. إذا تم تمرير `action` أو وجد في `data` يتم تثبيته في الحقلين `action` و `data["action"]`.
  * `fail(cls, message, retry_after=0, action=None, **data)`: ينشئ كائناً فاشلاً مع ضبط `should_retry = (retry_after > 0)`.
  * `error(self) -> str`: خاصية تعيد `""` إذا كان `success=True`، وتعيد `message` عند الفشل.
  * `queue_full(cls) -> TaskResult`: دالة مساعدة تعيد `TaskResult(success=True, message="🛑 الطوابير ممتلئة", data={"reason": "queue_full"})`. (ملاحظة: تعيد `success=True` مع أن الطوابير ممتلئة، ومفتاح السبب هو `reason` وليس `stop_reason`).
  * `no_heroes(cls) -> TaskResult`: دالة مساعدة تعيد `TaskResult(success=False, message="⚠️ لا يوجد أبطال متاحون", data={"reason": "no_heroes"}, should_retry=True, retry_after=300)`.
  * `__bool__(self)`: يعيد قيمة `self.success`.

---

### 2.4 قاموس معرفات مهام الهيبة في `base_task.py` (`PRESTIGE_QUEST_IDS`)

```python
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    # مهام المسيرات الخارجية
    "invaders":        4112004,  # قتل غزاة الهيبة (5 هجمات)
    "stronghold":      4112019,  # الهجوم على معقل الهيبة (3 هجمات)
    "gather":          4112006,  # جمع موارد الهيبة (25 ألف مورد)
    # مهام داخل المدينة
    "smuggler":        4112022,  # متجر المهربين (10 مشتريات)
    "watermill":       4112027,  # تعزيز إنتاج الساقية (مرة واحدة)
    "badge_exchange":  4112024,  # استبدال وسام الحرب (مرة واحدة)
    "train":           4112001,  # تدريب الجنود
    "fortress":        4112015,  # تدريب الفخاخ
}
```

---

### 2.5 دورة حياة `BaseTask` والدوال الهيكلية المجردة

1. **`__init__(self, conn, config=None)`**:
   - تسند الاتصال `self.conn` والإعدادات `self.config`.
   - تستخرج البريد `self.email = conn.account.email` والمعرف `self.uid = conn.uid`.
   - تنشئ المسجل `self.log = logging.getLogger(f"task.{self.name}[{self.email}]")`.
   - تهيئ الحالة الداخلية: `_state = TaskState.IDLE`, `_last_run = None`, `_last_result = None`, `_run_count = 0`, وحدث التوقف `_stop_event = asyncio.Event()`.
2. **`run(self) -> TaskResult`**: دالة مجردة `@abstractmethod` يجب على كل كلاس مشتق تنفيذها.
3. **`on_start(self)` و `on_stop(self)`**: خطافات فارغة قابلة لإعادة التعريف عند بدء وإيقاف المهمة.
4. **`stop(self)`**: يعين `self._stop_event.set()`، ويغير الحالة إلى `TaskState.STOPPED`، وينفذ `await self.on_stop()`.
5. **`is_stopped(self) -> bool`**: يفحص `self._stop_event.is_set()`.
6. **`is_connected(self) -> bool`**: يفحص هل `self.conn is not None` و `getattr(self.conn, "is_connected", False)`.
7. **`status(self) -> Dict[str, Any]`**: يعيد قاموس الحالة للوحة التحكم (`name`, `email`, `state`, `run_count`, `last_run`, `last_result`, `config`).
8. **`_execute(self) -> TaskResult`**:
   - يغير الحالة إلى `TaskState.RUNNING` ويسجل توقيت `_last_run = time.time()`.
   - ينفذ `await self.run()` داخل بلوك `try / except`.
   - عند النجاح: يحفظ `_last_result`، يزيد `_run_count += 1`، ويضع الحالة `TaskState.WAITING`.
   - عند الاستثناء: يسجل الخطأ كاملاً `self.log.exception`، يغير الحالة إلى `TaskState.ERROR`، ويعيد `TaskResult.fail(f"خطأ: {e}", retry_after=60)`.

---

### 2.6 التتبع السطري التفصيلي لكافة دوال `base_task.py` واستعلامات الشبكة ومفاتيح الذاكرة

#### 1. دالة `get_active_marches_count(self, force_sync: bool = False) -> int` (السطور 170-224)
- **الغرض**: حساب عدد المسيرات والفيالق النشطة بالخارج من الذاكرة الحية دون استعلام شبكي إلا عند الضرورة.
- **مفاتيح الذاكرة**:
  * `self.conn.local_queues`: قائمة طوابير المسيرات المخزنة محلياً بالاتصال.
  * `self.conn.cached_packets`: حزم الإشعارات المعترضة في الخلفية، وخاصة الحزم ذات المفتاح `notifyID == 'NOTIFY_LOCAL_QUEUE_SYNC'` ومفتاح الحزمة `202`.
- **التفريع والمسارات الشرطية (`if/elif/else`)**:
  * `has_local = bool(getattr(self.conn, 'local_queues', None))`: التحقق هل الطوابير موجودة بالذاكرة.
  * `if force_sync and not has_local`:
    - إذا طُلب التزامن الإجباري وكانت الذاكرة خالية: يرسل استعلام شبكي `cmd='1007', subcmd='1000', data={}` مع مهلة 2 ثوانٍ وانتظار `asyncio.sleep(0.3)`.
    - مسار الاستثناء `except Exception: pass`: يتم بلع أخطاء الشبكة بصمت دون رفع استثناء.
  * تجميع البيانات:
    - `if getattr(self.conn, 'local_queues', None)`: إضافة عناصر `local_queues` إلى `all_queue_data`.
    - `if getattr(self.conn, 'cached_packets', None)`:
      - حلقة فور على قيم `cached_packets.values()`. فحص `isinstance(p, dict)` و `d.get('notifyID') == 'NOTIFY_LOCAL_QUEUE_SYNC'`. استخراج `notifyData` وإضافته.
      - إضافة عناصر الحزمة `cached_packets.get(202, [])`.
  * حلقة فرز وتطبيع القوائم:
    - حلقة فور على `all_queue_data`.
    - `if not isinstance(item, dict)`: إذا كان العنصر قائمة `isinstance(item, list)` يتم تمديد `queues_to_check`، ثم `continue`.
    - `if 'status' in item or 'queueId' in item`: يضاف مباشرة لـ `queues_to_check`.
    - `elif 'data' in item`: استخراج `item['data']`. إذا كانت قائمة تُضاف عناصرها، وإن كانت قاموساً يضاف.
  * حلقة عد الطوابير النشطة:
    - فحص كل طابور `q`: `if isinstance(q, dict) and q.get('status') in (0, 1, 2, 3, 4, 7)`:
      * الحالات (0=مسيرة ذهاب، 1=عودة، 2=تخييم/جمع، 3=مساعدة، 4=هجوم معقل، 7=حشد).
      * استخراج المعرف `qid = q.get('id') or q.get('queueId')`.
      * `if qid`: إذا لم يكن في `seen_ids`، يضاف للمجموعة ويزداد العداد `active += 1`.
      * `else`: إذا لم يتوفر معرف يزداد العداد مباشرة `active += 1`.
- **المخرج**: يعيد العدد الصحيح للفيالق النشطة `active`.

---

#### 2. دالة `get_max_marches_capacity(self, allow_network: bool = True) -> int` (السطور 225-264)
- **الغرض**: حساب السقف الأقصى لعدد فيالق المسيرات المسموح بها للقلعة رياضياً بدقة 100%.
- **القواعد اللوجستية للعبة**:
  1. السقف الأساسي لجميع القلاع = 1 (`capacity = 1`).
  2. أبحاث معهد العلوم (`technologyCtrl`):
     - تقنية فيلق البعثة العسكرية الأولى `#24011`: تمنح +1 طابور.
     - تقنية فيلق البعثة العسكرية الثانية `#24017`: تمنح +1 طابور.
     - تقنية فيلق البعثة العسكرية الثالثة `#24033`: تمنح +1 طابور.
  3. ميزة كبار الشخصيات (`vipCtrl`):
     - إذا كان مستوى الـ VIP للقلعة (`vipLv >= 10`) يمنح +1 طابور مسيرة إضافي.
- **مفاتيح الذاكرة الحية**:
  * `self.conn.init_data['technologyCtrl']`
  * `self.conn.init_data['vipCtrl']`
- **التفريع الشرطي**:
  * فحص `init_data`: التأكد من أنه قاموس.
  * فحص التقنيات: حلقة على `('24011', '24017', '24033')`.
    - إذا كانت القيمة قائمة أو توبل وطولها أكبر من 1: فحص `int(val[1] or 0) > 0`، فإذا تحقق تزداد السعة `capacity += 1`.
    - إذا كانت القيمة رقماً أو نصاً رقمياً أكبر من صفر: تزداد السعة `capacity += 1`.
  * فحص VIP: استخراج `vipLv = int(vip_ctrl.get('vipLv', 0) or 0)`. فحص `if vip_lv >= 10`: تزداد السعة `capacity += 1`. مسار الاستثناء يلتقط `(ValueError, TypeError)`.
- **المخرج**: يعيد `max(1, capacity)`.

---

#### 3. دالة `get_available_marches_count(self, force_sync: bool = False, allow_network: bool = True) -> int` (السطور 265-274)
- **الغرض**: حساب عدد الفيالق الشاغرة بالقلعة الجاهزة للإرسال فوراً.
- **المسار المنطقي**:
  * تستدعي `max_cap = await self.get_max_marches_capacity(allow_network=allow_network)`.
  * تستدعي `active = await self.get_active_marches_count(force_sync=force_sync)`.
  * تعيد `max(0, max_cap - active)`.

---

#### 4. دالة `get_active_gather_resource_types(self, force_sync: bool = False) -> Set[int]` (السطور 275-314)
- **الغرض**: فحص أنواع الموارد التي تجمعها مسيرات نشطة خارج القلعة لمنع إرسال فيلقين لجمع نفس المورد في مهام الهيبة.
- **مفاتيح الذاكرة الحية**:
  * `self.conn.local_queues`
- **التفريع الشرطي والشبكي**:
  * إذا كانت `local_queues` غير محملة: ترسل استعلام تزامن `1007 / 1000` مع انتظار 0.3 ثانية.
  * تفحص كل طابور في `local_queues`: فحص `status in (0, 1, 2, 3, 4, 7)`.
  * فحص الوجهة والانطلاق في `("to", "from")`:
    - إذا كان `mapType == 5`: فحص `subMapType`.
    - إن لم يتوفر، تفكيك المعرف `parts = str(id).split("-")`: إذا كان طوله >= 4 والعنصر الثالث هو `"5"` والرابع رقمي، يتم استخراج نوع المورد الفرعي `res_sub = int(parts[3])`.
  * فحص بديل في `q.get("data", {})`: فحص `resourceType` ومطابقته بالقاموس `{1001: 1, 1002: 2, 1003: 3, 1004: 4, 1005: 5}`.
  * إذا كان `res_sub in (1, 2, 3, 4, 5)`: يضاف للمجموعة `active.add(int(res_sub))`.
- **المخرج**: تعيد مجموعة معرفات الموارد النشطة `Set[int]`. توفر اسماً بديلاً `_get_active_gather_types`.

---

#### 5. دالة `get_lord_stamina(self) -> int` (السطور 319-343)
- **الغرض**: استخراج رصيد طاقة اللورد الحالية من الذاكرة الحية بسرعة 0ms وبصفر طلبات شبكية.
- **مفاتيح الذاكرة الحية**:
  * المسار الأول: `init_data['lordInfoCtrl']['base']['health']`
  * المسار الثاني: `init_data['loginDataInitCtrl']['base']['health']`
- **التفريع والتحقق**:
  * فحص وجود `self.conn` و `init_data`. إذا لم تتوفر يعاد الافتراضي `100`.
  * إذا كان `val is not None`، يعاد `int(float(val))`.
  * عند أي استثناء يعاد `100`. توفر اسماً بديلاً `_get_lord_stamina`.

---

#### 6. دالة `get_castle_level(self) -> int` (السطور 344-366)
- **الغرض**: استخراج المستوى الحقيقي لمبنى القلعة (Castle Level - القصر الملكي ذو المعرف `bid == 101`).
- **مفاتيح الذاكرة الحية**:
  * `init_data['cityCtrl']['blist']`: قائمة مباني المدينة.
- **التفريع الشرطي**:
  * البحث داخل قائمة المباني `blist` عن المبنى الذي يحمل `str(binfo.get("bid", "")) == "101"`.
  * استخراج المستوى `lv = int(binfo.get("lv", 1))` وتحديث `castle_lv = max(castle_lv, lv)`.
  * الافتراضي عند عدم العثور هو `1`. توفر اسماً بديلاً `_get_castle_level`.

---

#### 7. دالة `get_prestige_quest_info(self, quest_key_or_id: str | int) -> Dict[str, Any]` (السطور 367-421)
- **الغرض**: استخراج بيانات وحالة مهمة الهيبة اليومية من الذاكرة الحية بصفر طلبات شبكية.
- **المدخلات**: مفتاح نصي أو معرف عددي. إذا كان نصاً يبحث في `PRESTIGE_QUEST_IDS` الخاص بـ `base_task.py`.
- **مفاتيح الذاكرة الحية**:
  * `init_data['meritoriousTaskCtrl']`
- **التفريع الداخلي ثلاثي المراحل**:
  1. **المسار الأول (`taskData`)**: فحص قاموس `meritoriousTaskCtrl.taskData`:
     - استخراج العداد الحالي `cNum / c_num`، والهدف الكلي `lNum / l_num`، والحالة `status`.
     - حساب الاكتمال: `is_done = (s == 4) or (l > 0 and c >= l)`.
     - حساب المتبقي: `remaining = max(0, l - c) if l > 0 else 0`.
  2. **المسار الثاني (`tasks`)**: فحص قائمة المهام `meritoriousTaskCtrl.tasks`:
     - مطابقة `t.get("id")` أو `t.get("taskId")` مع `qid`.
     - حساب الاكتمال: `is_done = (s in (1, 4)) or (l > 0 and c >= l)`.
  3. **المسار الثالث (`daily_task`)**: فحص عدادات الأيام `meritoriousTaskCtrl.daily_task`:
     - استخراج `c = int(daily_task[str(qid)])`.
     - حساب الاكتمال: `is_done = c >= 1`.
  - إذا لم توجد المهمة في أي مسار: تعيد `{"found": False, "task_id": qid, "c_num": 0, "l_num": 0, "status": 0, "is_done": False, "remaining": 0}`.
- توفر اسماً بديلاً `_get_quest_info`.

---

#### 8. دالة `refresh_prestige_data(self, force: bool = False, min_interval: float = 30.0) -> bool` (السطور 422-458)
- **الغرض**: تجديد وتحديث بيانات مهام الهيبة اليومية من خادم اللعبة عبر أمر تهيئة الدخول المعتمد.
- **استعلام الشبكة**: `cmd="1000", subcmd="1", data={}` (أمر `CMD_LOGIN_DATA_INIT`). المهلة: 6 ثوانٍ.
- **التفريع والشروط**:
  * فحص الاتصال: إذا كان غير متصل يعاد `False`.
  * آلية الكبح الزمني (Throttling): فحص `not force and has_merit and (now - last_sync < min_interval)` -> يعاد `True` دون إرسال طلب شبكي.
  * فحص الاستجابة: استخراج `retdata` من `data.retdata` أو `retdata` المباشرة.
  * إذا احتوت على `meritoriousTaskCtrl`: يتم تحديث `self.conn.init_data["meritoriousTaskCtrl"]` وتحديث توقيت المزامنة `_last_merit_sync_time = now`.
- توفر اسماً بديلاً `_refresh_merit_data`.

---

#### 9. دالة `get_castle_coords(self, allow_network: bool = True) -> Tuple[int, int]` (السطور 459-504)
- **الغرض**: استخراج إحداثيات القلعة المركزية `(x, y)` على الخريطة.
- **استعلام الشبكة الاحتياطي**: `cmd="1006", subcmd="25", data={"uid": uid}` (أمر `REQ_GET_CASTLE_MAP_INFO`).
- **المسارات المتدرجة (Fallback Cascade)**:
  1. الإعدادات المباشرة: فحص `config['center_x']` أو `config['x']` و `center_y` أو `y`.
  2. الذاكرة الحية (0ms): فحص `init_data['cityCtrl']['cinfo']['pos']` واستخراج `x, y`.
  3. استعلام الشبكة 1006/25: إذا لم تتوفر وكان `allow_network=True`: إرسال الطلب وحفظ النتيجة في الذاكرة الحية `init_data['cityCtrl']['cinfo']['pos']` لتفادي تكرار الاستعلام مستقبلاً.
  - الفشل التام يعيد `(0, 0)`.

---

#### 10. دالة `get_kingdom_id(self, allow_network: bool = True) -> int` (السطور 505-556)
- **الغرض**: استخراج معرف المملكة (`kingdom_id` أو `partition`).
- **استعلام الشبكة الاحتياطي**: `cmd="1002", subcmd="7", data={"uid": uid}` (أمر `REQ_USER_INFO`).
- **المسارات المتدرجة**:
  1. كائن الاتصال: `getattr(self.conn, 'kingdom_id', None)`.
  2. الذاكرة الحية: `init_data['lordInfoCtrl']['base']['partition']` أو `partition` أو `kingdomId`. عند العثور عليه يتم تثبيته في `self.conn.kingdom_id`.
  3. استعلام الشبكة 1002/7: فحص `r_player['data']['base']['partition']` وتثبيته في `self.conn.kingdom_id`.
  - الفشل يعيد `0`.

---

#### 11. دالة `get_available_troops(self, exclude_used=None, allow_network=True) -> Dict[int, int]` (السطور 557-614)
- **الغرض**: استخراج القوات المتاحة بالقلعة واستبعاد فخاخ الجدار وخصم القوات المحجوزة للمسيرات المتتالية.
- **استعلام الشبكة الاحتياطي**: `cmd="1005", subcmd="1", data={}` (أمر `REQ_GET_ARMY_INFO`).
- **مفاتيح الذاكرة الحية**: `init_data['armyCtrl']['totalArmy']`.
- **التفريع وفلترة القوات**:
  * فحص مفاتيح `totalArmy`: التحقق من أنها رقمية وأن العدد أكبر من صفر.
  * **استبعاد فخاخ وأسلحة الجدار حتماً**: الشرط الصارم `if not (800 <= tid < 900) and cnt > 0:` لمنع الوقوع في خطأ السيرفر `8062`.
  * المسار الاحتياطي 1005/1: يعمل إذا كانت القوات بالذاكرة فارغة وطُلب `allow_network`.
  * **خصم القوات المشغولة**: فحص `exclude_used` أو `self._used_army`:
    - حلقة فور على `used_map`: `available[tid] = max(0, available[tid] - used_cnt)`.

---

#### 12. دالة `get_formation(self, formation_id=1, allow_network=True) -> Tuple[List, List, List, Dict]` (السطور 615-669)
- **الغرض**: جلب بيانات التشكيلة المحفوظة (أبطال، حيوانات، رونات، جنود).
- **استعلام الشبكة الاحتياطي**: `cmd="1005", subcmd="7", data={"compiletype": formation_id}`.
- **مفاتيح الذاكرة الحية**: `init_data['armyCtrl']` عبر القواميس:
  * `compileHeros[fid_str]`
  * `compilePets[fid_str]`
  * `compileRunePages[fid_str]`
  * `compileArmy[fid_str]`
- **المعالجة والتفريع**:
  * إذا كان `formation_id <= 0`: يعيد قوائم فارغة فوراً.
  * قراءة فورية من الذاكرة الحية.
  * مسار احتياطي شبكي عبر 1005/7 إذا كانت أبطال وجيش التشكيلة فارغة بالذاكرة.
  * تنظيف صفحات الرونات عبر استدعاء `self.get_rune_pages(form_rune_pages)`.

---

#### 13. دالة `get_rune_pages(self, form_rune_pages=None) -> List[int]` (السطور 670-696)
- **الغرض**: استخراج وتنظيف صفحات الرونات لأمر المسير ومنع رفض السيرفر.
- **التفريع والمسارات**:
  * إذا كانت قائمة `list`: استخراج العناصر الرقمية الأكبر من صفر `[int(x) for x in ... if ... > 0]`.
  * إذا كانت قاموساً `dict`: فحص قيمه، فإن كانت قائمة تستخرج الأرقام، وإن كانت قيمة عددية تعاد بقائمة `[int(v)]`.
  * إذا كانت رقماً منفرداً: يعاد `[int(form_rune_pages)]`.
  * الفشل التام: يعيد القيمة القياسية الافتراضية للعبة `[1]`.

---

#### 14. دالة `get_combat_heroes(self, form_heroes=None, max_count=2, exclude_busy=None) -> List[int]` (السطور 697-854)
- **الغرض**: فحص أبطال التشكيلة واستبدال المنشغلين منهم بأفضل أبطال قتال وهجوم متاحين وفق نظام الأفضليات الحربية.
- **مفاتيح الذاكرة الحية**:
  * `init_data['heroCtrl']`: قائمة أو قاموس أبطال القلعة.
  * التراجع لـ `self._heroes` أو بوابة الاتصال `self.conn._gate.heroes`.
- **خطوات التنفيذ والتفريع المجهري**:
  1. بناء مجموعة المشغولين `busy`: دمج `exclude_busy` و `self._busy`.
  2. بناء خريطة الأبطال `hero_map = {int(h['id']): h}`.
  3. **فحص أبطال التشكيلة المعطاة (`form_heroes`)**:
     - تسطيح التشكيلة `flat_form`.
     - فحص كل بطل: إذا لم يكن في `busy` ولم يتم اختياره مسبقاً.
     - فحص الحالة: `state = h_data.get('status', {}).get('state', 0)`.
     - إذا كان `state == 0` (متاح بالقلعة وغير منشغل بمسيرة أو تكليف): يضاف إلى `chosen_heroes` ويوضع في `busy`.
     - إذا اكتمل العدد `len(chosen_heroes) >= max_count` يتوقف ويعاد فوراً.
  4. **نظام استبدال الأبطال الهرمي (3 طبقات - 3 Tiers)**:
     - استبعاد المنشغلين `state != 0`.
     - **استبعاد أبطال الجمع والدعم حتماً**:
       `if hid_str.startswith('5502') or hid_str.startswith('5503'): continue`
     - فحص المهارات القتالية والهجومية: فحص قاموس `skillList` والتأكد من وجود مهارة تبدأ بـ `5610` أو `5640`.
     - حساب سكور القوة: `score = lv * 10 + star * 50`.
     - تصنيف الطبقات:
       * `Tier 1`: أبطال حرب (`5501xxx`) يمتلكون مهارات قتالية وهجومية نشطة.
       * `Tier 2`: أبطال حرب (`5501xxx`) بدون مهارات قتالية نشطة.
       * `Tier 3`: أبطال آخرون متاحون.
     - ترتيب كل طبقة تنازلياً حسب `score`، والدمج `tier1 + tier2 + tier3`.
     - اختيار الأبطال حتى اكتمال `max_count`.
  5. **خطة الطوارئ القصوى**: في حال خلو الحساب تماماً من أبطال حرب، يتم اختيار أي بطل متاح في القلعة حالته `state == 0`.

---

#### 15. دالة `select_combat_pet(self, exclude_busy=None) -> List[int]` (السطور 855-910)
- **الغرض**: اختيار أفضل حيوان قتالي متاح في القلعة عند غياب الحيوان عن التشكيلة.
- **مفاتيح الذاكرة الحية**: `init_data['petCtrl']['pets']`.
- **التفريع والترتيب**:
  * تجميع المشغولين من `exclude_busy` و `self._used_pets`.
  * حلقة فور على `pets_data.items()`:
    - استخراج `pid, step, lv, exp`.
    - استبعاد المشغولين `pid in busy`.
  * الترتيب متعدد المستويات (Multi-level sorting):
    `available_pets.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)`
    (الرتبة والتطور `step` أولاً، ثم المستوى `lv` ثانياً، ثم نقاط الخبرة `exp` ثالثاً).
  * تسجيل الحيوان المختار في `self._used_pets` لمنع تكراره في المسيرات المتتالية.
  * يعيد `[chosen_pet]` أو `[]`.

---

#### 16. دالة `get_march_army(...) -> List[Dict[str, int]]` (السطور 911-1040)
- **الغرض**: تجهيز جيش المسيرة بدقة متناهية وفق التشكيلة المحددة مع تعويض النقص بالقوة القتالية لا بالعدد، وفرض صمامات الأمان ضد هلاك الجيش أو خطأ السيرفر.
- **المعاملات**: `form_army_dict`, `formation_id`, `available_troops`, `fallback_count`, `max_capacity`.
- **التفريع الحسابي والمسارات**:
  1. جلب القوات المتاحة وفلترة فخاخ الجدار `800 <= tid < 900`.
  2. استخراج التشكيلة: إذا لم تمرر يتم جلبها من `get_formation(formation_id)`.
  3. إذا كانت التشكيلة فارغة: في حال وجود `fallback_count > 0` تستدعي `_pick_balanced_combat_troops`، وإلا تعيد `[]`.
  4. **صمام أمان سعة مسيرة اللورد (منع خطأ 8035)**:
     - `target_total = sum(target_form.values())`
     - إذا كان `max_capacity > 0 and target_total > max_capacity`:
       يتم حساب معامل التقليص: `scale = float(max_capacity) / float(target_total)` وتعديل `target_total = max_capacity`.
  5. **سحب القوات وحساب القوة القتالية المفقودة**:
     - لكل نوع `tid` في التشكيلة: حساب المطلوب `req = int(req_raw * scale)`.
     - أخذ المتاح `take = min(req, avail)`.
     - إذا وجد نقص `take < req`: حساب القوة المفقودة:
       `lost_power += (req - take) * self._get_unit_combat_power(tid)`
  6. **التعويض بالقوة القتالية المكافئة**:
     - إذا كان `lost_power > 0.5`:
       حساب سقف التعويض: `comp_cap = target_total - army_so_far`.
       استدعاء `_pick_balanced_combat_troops(available, needed_power=lost_power, cap=comp_cap)`.
       إضافة القوات المعوضة للجيش.
  7. **صمام الأمان الرياضي للعدد الإجمالي**:
     - إذا كان المجموع النهائي `final_total > target_total`: يتم تقليص الفائض `excess` من الرتب الصغرى وإعادة القوات إلى `available`.
  8. **فحص الضعف الحرج للجيش (صمام منع الانتحار - Anti-Suicide)**:
     - حساب قوة التشكيلة المطلوبة `target_power`.
     - حساب قوة الجيش المجهز الفعلي `actual_power`.
     - **الشرط الحرج**:
       ```python
       if target_power > 0 and actual_power < target_power * 0.5:
           raise RuntimeError(f"WEAK_ARMY: قوة الجيش ({actual_power:.0f} = {actual_pct:.0f}%) دون 50% من التشكيلة ({target_power:.0f})")
       ```
       (ملاحظة: ترفع استثناء `RuntimeError` يبدأ بـ `WEAK_ARMY`).
  9. تحديث القوات المشغولة في `self._used_army`.
  10. إعادة قائمة الجيش بصيغة بروتوكول السيرفر `[{"id": tid, "num": num}, ...]`.

---

#### 17. دالة `_get_unit_combat_power(self, tid: int) -> float` (السطور 1041-1053)
- **الغرض**: حساب القوة القتالية للوحدة الواحدة وفق نوعها ورتبتها (`tid % 100 = الرتبة`).
- **المعادلة الرياضية**:
  * `rank = (tid % 100) * 0.05`
  * مشاة (`400 <= tid < 500`): تعيد `1.00 + rank`
  * فرسان (`500 <= tid < 600`): تعيد `1.10 + rank` (الفرسان أعلى بطبيعتهم)
  * رماة (`600 <= tid < 700`): تعيد `1.00 + rank`
  * عربات حصار (`700 <= tid < 800`): تعيد `0.50 + rank`
  * غير ذلك: تعيد `0.50`

---

#### 18. دالة `_pick_balanced_combat_troops(...) -> List[Dict[str, int]]` (السطور 1054-1142)
- **الغرض**: اختيار قوات قتالية متوازنة تعادل بالضبط `needed_power` قوة قتالية مع احترام السقف `cap`.
- **التفريع التكتيكي**:
  * تصنيف القوات المتاحة: `infantry` (4xx)، `cavalry` (5xx)، `archers` (6xx)، `carts` (7xx).
  * ترتيب كل قائمة تنازلياً حسب المعرف (الرتب الأعلى أولاً).
  * حصر الفروع القتالية الأساسية `combat_branches = [infantry, cavalry, archers]`.
  * **الجولة الأولى (التوزيع المتساوي بالحصص)**:
    - تقسيم القوة المطلوبة بالتساوي: `branch_power = remaining_power / len(combat_branches)`.
    - لكل صنف قتالي: أخذ جنود بما لا يتجاوز `branch_power` و `cap`.
  * **الجولة الثانية (استكمال أي فجوة قوة متبقية)**:
    - إذا بقي `remaining_power > 0.5`: المرور على كافة الفروع بما فيها العربات لاستيفاء القوة المطلوبة حتى تصل إلى الصفر أو ينفد الجيش.

---

#### 19. دالة `check_target_busy_or_marched(...) -> Tuple[bool, str, Dict]` (السطور 1143-1298)
- **الغرض**: فحص أمني دقيق وشامل ومباشر للهدف (مورد أو معقل) على الخريطة قبل إرسال المسيرة لمنع التصادم.
- **استعلامات الشبكة**:
  1. `cmd="1006", subcmd="22", data={"x": tx, "y": ty, "id": str(target_id)}` (فحص الهدف المباشر).
  2. `cmd="1006", subcmd="1000", data={'centerX': tx, 'centerY': ty, 'centerKid': target_kid}` (مزامنة الخريطة).
- **اعتراض إشعارات الشبكة**:
  * تسجيل مستمع حزم `_capture_sync` لاعتراض إشعارات `cmd='1009', subcmd='201'` (`NOTIFY_MAP_SYNC`).
- **التفريع الشرطي**:
  * **المرحلة 1 (استعلام 1006/22)**:
    - إذا كان `currentCollectNum > 0` أو `collectSpeed > 0`: يعيد `(True, "لاعب آخر يشغل الهدف حالياً...", node_data)`.
    - إذا كان معقلاً ووجد `active_march`: يعيد `(True, "المعقل مشغول بمعركة نشطة حالياً...", node_data)`.
    - إذا كان حقلاً للموارد وكان `remainSourceNum == 0`: يعيد `(True, "رصيد موارد الحقل نفد تماماً...", node_data)`.
  * **المرحلة 2 (مزامنة الخريطة 1006/1000 وإشعارات 1009/201)**:
    - فحص رسائل التحرك `msgType in (11, 12, 14)`:
      * فحص وجهة كل مسيرة `q_to_id` أو `(q_to_x, q_to_y)`.
      * إذا كانت متجهة للهدف: فحص صاحب المسيرة `q_uid`. إن كان `our_uid` يعيد أن قلعتنا متجهة له، وإن كان لاعباً آخر يعيد أن مسيرة لاعب آخر متجهة له.
    - فحص كائنات الخريطة `msgType == 1`:
      * فحص كائنات قطع الخريطة ومطابقة `obj.get('id') == target_id_str`.
      * فحص الشاغل `occupier` أو `user` أو `uid`: إن وجد شاغل يحدد هل هو قلعتنا أم لاعب آخر.
  * إذا اجتاز كافة الفحوصات: يعيد `(False, "", node_data)`.

---

#### 20. كلاس `TaskScheduler` (السطور 1335-1396)
- **المعاملات**: `task: BaseTask`, `interval: int`, `offset: int = 0`.
- **دالة `run_forever(self)`**:
  * تستدعي `await self.task.on_start()`.
  * تطبيق تأخير الأوفست الأولي `if self.offset > 0`:
    `await asyncio.wait_for(self.task._stop_event.wait(), timeout=self.offset)`
    (إذا أُوقفت المهمة أثناء الأوفست تخرج فوراً عبر `return`).
  * الحلقة الدائمة `while not self.task.is_stopped():`:
    - تنفذ `result = await self.task._execute()`.
    - إذا أُوقفت تكسر الحلقة.
    - تحديد مهلة الانتظار:
      `wait_time = result.retry_after if (result.should_retry and result.retry_after > 0) else self.interval`
    - انتظار المهلة مع إمكانية المقاطعة الفورية:
      `await asyncio.wait_for(self.task._stop_event.wait(), timeout=wait_time)`
  * عند الخروج: تستدعي `await self.task.on_stop()`.

---

## 3. التشريح المجهري لكود `tasks/march_coordinator.py`

### 3.1 الفلسفة المعمارية والبروتوكول
تمت إعادة صياغة المنسق كلياً وفق بروتوكول توجيه المهام (Task-Driven Action Protocol):
- المحرك لا يتخذ قرارات استنتاجية نيابة عن المهام الفرعية، بل تنفذ المهمة الفرعية وتعيد `TaskResult` حاملاً إجراءً صريحاً `action`.
- في حال خلو النتيجة من إجراء صريح، تمر النتيجة عبر طبقة الأمان الاحتياطية `_fallback_action`.

---

### 3.2 جدول الإعدادات والمدخلات (`config`) والأنواع والقيم الافتراضية

| المفتاح (Config Key) | النوع البرمجي (Type) | القيمة الافتراضية (Default) | التحقق والمسار البديل |
| :--- | :--- | :--- | :--- |
| `duration_minutes` | `float` | `20.0` | تحويل عبر `float(...)`، وتحسب المهلة القصوى بالثواني `self.max_duration = self.duration_minutes * 60.0` |
| `priority_order` | `List[str]` | `DEFAULT_PRIORITY_ORDER` | قائمة الأولويات المخصصة، وإن لم تُمرر تستخدم القائمة الافتراضية ذات الـ 10 أولويات |
| `is_main_prestige_enabled` | `bool` | `True` | مفتاح تفعيل الهيبة العام. إن كان `False` يتم تخطي أولويات الهيبة الثلاث بـ `SKIP_PRIORITY` |
| `abra` | `dict` أو `bool` | `{}` | إعدادات وحش الذهب. إن كانت بوليان تحول إلى `{"enabled": val}` |
| `prestige_invaders` | `dict` | `{}` | إعدادات غزاة الهيبة (`enabled`, `max_lv`, `formation_id`) |
| `prestige_stronghold` | `dict` | `{}` | إعدادات معقل الهيبة (`enabled`, `max_lv`, `formation_id`) |
| `prestige_gather` | `dict` | `{}` | إعدادات جمع الهيبة (`enabled`, `level`, `search_range`) |
| `transport` | `dict` | `{}` | إعدادات النقل (`enabled`, `target_x`, `target_y`, `resource_ids`) |
| `ruins` | `dict` | `{}` | إعدادات الأطلال (`enabled`, `time`, `formation_id`) |
| `combat` | `dict` | `{}` | إعدادات القتال الشامل (`enabled`, `choice`, `level`, `formation_id`, `troops_count`) |
| `stronghold` | `dict` | `{}` | إعدادات المعاقل العامة (`enabled`, `count`, `level`, `formation_id`, `troops_count`, `search_range`) |
| `gold_gather` | `dict` | `{}` | إعدادات جمع الذهب (`enabled`, `locations`, `alliances`) |
| `gather` | `dict` | `{}` | إعدادات الجمع المفتوح (`enabled`, `res_type`, `level`, `max_marches`, `search_range`, `use_boost`) |

---

### 3.3 الثوابت وقاموس معرفات الهيبة في `march_coordinator.py`

#### أ. كلاس `CoordinatorAction`
- `NEXT_PRIORITY = "next_priority"`: الانتقال للأولوية التالية في الحلقة فوراً.
- `TERMINATE = "terminate"`: إيقاف المنسق كلياً وإنهاء دورة العمل.
- `WAIT_AND_RETRY_SAME = "wait_and_retry_same"`: الانتظار 3 دقائق وإعادة محاولة نفس الأولوية.
- `SKIP_PRIORITY = "skip_priority"`: تخطي الأولوية الحالية فوراً والانتقال للتالي.

#### ب. قائمة الأولويات الافتراضية (`DEFAULT_PRIORITY_ORDER`)
```python
DEFAULT_PRIORITY_ORDER = [
    "abra",                 # أولوية 1: وحش الذهب Abra
    "prestige_invaders",    # أولوية 2: غزاة الهيبة
    "prestige_stronghold",  # أولوية 3: معقل الهيبة
    "prestige_gather",      # أولوية 4: جمع موارد الهيبة
    "transport",            # أولوية 5: نقل الموارد
    "ruins",                # أولوية 6: استكشاف الأطلال
    "combat",               # أولوية 7: القتال الشامل
    "stronghold",           # أولوية 8: المعاقل العامة
    "gold_gather",          # أولوية 9: جمع الذهب
    "gather",               # أولوية 10: الجمع الخارجي المفتوح
]
```

#### ج. قاموس `PRESTIGE_QUEST_IDS` الخاص بالمنسق وقائمة `PRESTIGE_GATHER_RESOURCES`
```python
PRESTIGE_QUEST_IDS: Dict[str, int] = {
    "invaders":      4112004,
    "stronghold":    4112030,
    "gather_food":   4112000,
    "gather_wood":   4112001,
    "gather_iron":   4112002,
    "gather_silver": 4112003,
}

PRESTIGE_GATHER_RESOURCES = [
    {"key": "gather_food",   "res_type": 2, "name": "القمح (Food)",      "quest_id": 4112000},
    {"key": "gather_wood",   "res_type": 3, "name": "الخشب (Wood)",      "quest_id": 4112001},
    {"key": "gather_iron",   "res_type": 4, "name": "الحديد (Iron)",     "quest_id": 4112002},
    {"key": "gather_silver", "res_type": 5, "name": "الكوارنز (Silver)", "quest_id": 4112003},
]
```

---

### 3.4 دورة حياة المنسق والمحرك الرئيسي (`run` وما يتفرع عنها)

#### دالة `run(self) -> TaskResult` (السطور 121-173)
- تسجل توقيت البدء `self.start_time = time.time()`.
- حلقة فور الخارجية: تمر على كل أولوية `p_key` في `self.priority_order`:
  1. **فحص انتهاء المهلة الزمنية الكلية**:
     `if self._is_time_expired(): break`
  2. **حلقة الإعادة الداخلية (`while not self._is_time_expired():`)**:
     - تنفذ `result = await self._run_priority(p_key)` داخل `try / except`.
     - إذا حدث استثناء: يسجل كخطأ ويعاد `TaskResult.fail(str(e), action=CoordinatorAction.NEXT_PRIORITY)`.
     - **استخلاص الإجراء**:
       `action = getattr(result, "action", None) or result.data.get("action")`
       إذا لم يتوفر: يتم اللجوء لـ `action = self._fallback_action(result, p_key)`.
     - **تنفيذ الإجراء**:
       * حالة `TERMINATE`: تسجل الخروج وتنهي المنسق فوراً بإرجاع `TaskResult.ok("تم إنهاء مهمة منسق الفيالق ككل.")`.
       * حالة `WAIT_AND_RETRY_SAME`: تسجل امتلاء الفيالق، وتنتظر عبر `has_time = await self._wait_minutes(3)`. إن لم يتبق وقت تنهي المنسق، وإن بقي وقت تنفذ `continue` لتعيد نفس الأولوية مجدداً.
       * حالة `NEXT_PRIORITY` أو `SKIP_PRIORITY`: تنفذ `break` للخروج من حلقة `while` والانتقال للأولوية التالية في حلقة `for`.
  3. فاصل زمني عشوائي بين الأولويات: `await asyncio.sleep(round(random.uniform(1.5, 3.0), 2))`.
- عند اكتمال كافة الأولويات: تعيد `TaskResult.ok("✅ اكتملت دورة منسق الفيالق بنجاح لجميع الأولويات.")`.

#### دالة `_run_priority(self, p_key: str) -> TaskResult` (السطور 178-197)
- قاموس الموزع `handlers`:
  يربط المفاتيح بدوالها الخاصة العشر.
- إذا لم يوجد المعالج: يعيد `TaskResult.ok(f"أولوية [{p_key}] غير موجودة", action=CoordinatorAction.SKIP_PRIORITY)`.

#### دالة `_fallback_action(self, result: TaskResult, p_key: str) -> str` (السطور 202-219)
- تستخرج `stop = result.data.get("stop_reason", "")` و `status = result.data.get("status", "")`.
- التفريعات الحالية:
  * `if stop in ("QUEUE_FULL", "8004", "9007004") or status == "queue_full"`: تعيد `WAIT_AND_RETRY_SAME`.
  * `if stop in ("NO_ARMY", "8009") or status == "critical_no_army"`: تعيد `TERMINATE`.
  * `if stop in ("STAMINA_EMPTY",) or status == "stamina_empty"`: تعيد `NEXT_PRIORITY`.
  * `if stop in ("NOT_EVENT_DAY", "CASTLE_LV_LOW") or status in ("skipped", "already_done", "already_active")`: تعيد `SKIP_PRIORITY`.
  * الافتراضي: يعيد `NEXT_PRIORITY`.

#### الدوال المساعدة الداخلية:
- `_is_time_expired(self) -> bool`: يفحص هل انقضت مهلة `max_duration`.
- `_remaining_seconds(self) -> float`: حساب الثواني المتبقية حتى انتهاء الـ 20 دقيقة.
- `_wait_minutes(self, minutes: float) -> bool`: ينتظر على دفعات صغيرة من 15 ثانية ويفحص `_is_time_expired()` في كل خطوة لمنع تجميد المنسق.
- `_forward_logs(self, subtask: BaseTask)`: ينسخ معالجات السجلات `handlers`، ويضبط المستوى، ويفعل `propagate = True` لبث السجلات الحية للتيرمنال ومكتبات المراقبة.
- `_refresh_merit_data(self, force: bool = False) -> bool`: يحدث بيانات الهيبة مع كبح الطلبات المتكررة لمدة 120 ثانية.
- `_get_quest_info(self, quest_key_or_id) -> Dict[str, Any]`: يقرأ من `init_data['meritoriousTaskCtrl']` بالاعتماد على قاموس `PRESTIGE_QUEST_IDS` الخاص بالمنسق.

---

### 3.5 التتبع السطري التفصيلي للأولويات العشر في `march_coordinator.py`

#### 1. الأولوية 1 (`abra` - وحش الذهب) (السطور 303-335)
- قراءة إعدادات `abra`: فحص `enabled`. إذا كان `False` يعيد `TaskResult.ok("abra معطل", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="disabled")`.
- التحقق من يوم الحدث: استخراج توقيت UTC الحالي:
  `now_utc.weekday() in (0, 2)` (يوم الإثنين = 0، والأربعاء = 2).
  إذا لم يكن يوم الحدث ولم يُفعَّل خيار `force`: يعيد `TaskResult.ok("ليس يوم حدث Abra", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="NOT_EVENT_DAY")`.
- التحقق من الإحداثيات: فحص `x, y`. إذا كانت `<= 0` يعيد `SKIP_PRIORITY`.
- تمرير الإعدادات:
  * ينسخ الإعدادات ويضيف `formation_id` (يقرأه من `combat.formation_id` كقيمة افتراضية).
  * يمرر قائمة المشغولين `cfg["busy_heroes"] = list(self._busy_heroes)`.
- التنفيذ وتحديث الحالة:
  * ينشئ `task = AbraTask(self.conn, cfg)`.
  * يربط السجلات `self._forward_logs(task)`.
  * ينفذ `result = await task.run()`.
  * يحدث الأبطال المشغولين: `self._busy_heroes.update(getattr(task, "_busy_heroes", set()))`.
  * يعيد `result`.

---

#### 2. الأولوية 2 (`prestige_invaders` - غزاة الهيبة) (السطور 340-382)
- فحص التفعيل العام للهيبة: `if not self.config.get("is_main_prestige_enabled", True)` يعيد `SKIP_PRIORITY`.
- فحص تفعيل المهمة: `if not cfg.get("enabled", False)` يعيد `SKIP_PRIORITY`.
- تحديث بيانات الهيبة: `await self._refresh_merit_data()`.
- فحص حالة المهمة: `q = self._get_quest_info("invaders")`.
  * إذا كانت `q.get("is_done")`: يعيد `TaskResult.ok(f"غزاة الهيبة مكتملة...", action=CoordinatorAction.NEXT_PRIORITY)`.
- حساب الهجمات المطلوبة: `needed = q["remaining"]` إن وجدت، وإلا الافتراضي 5.
- ضبط المستويات:
  * `max_lv_1 = int(cfg.get("max_lv", 30))`.
  * إذا كان `max_lv_1 <= 10`: يجعل `min_lv1 = 1`، وإلا `min_lv1 = max_lv_1 - 5`.
- تجهيز كائن `monster_cfg`:
  ```python
  monster_cfg = {
      "monster_type":   "invaders",
      "max_marches":    needed,
      "min_lv":         min_lv1,
      "max_lv":         max_lv_1,
      "formation_id":   int(cfg.get("formation_id", 1)),
      "search_range":   int(100),
      "wait_for_queue": False,
      "troops_count":   int(0),
      "busy_heroes":    list(self._busy_heroes),
  }
  ```
- ينشئ `MonsterTask`، يوجه السجلات، ينفذ، يحدث `self._busy_heroes.update(getattr(task, "_busy", set()))`، ويعيد النتيجة.

---

#### 3. الأولوية 3 (`prestige_stronghold` - معقل الهيبة) (السطور 387-428)
- فحص `is_main_prestige_enabled` وتفعيل `prestige_stronghold.enabled`. عند التعطيل يعيد `SKIP_PRIORITY`.
- تحديث بيانات الهيبة وفحص المهمة: `q = self._get_quest_info("stronghold")`.
  * (ملاحظة حرجة: يوجد سطر تشخيصي مهمل `q2 = self._get_quest_info("invaders")` يطبع في السجلات).
  * إذا كانت `q.get("is_done")`: يعيد `NEXT_PRIORITY`.
- حساب الهجمات المطلوبة: `needed = min(2, q["remaining"])` إن وجدت، وإلا 2.
- ضبط المستويات: `max_lv_1 = int(cfg.get("max_lv", 30))`، و `min_lv1 = 1` إذا كان `<= 10` وإلا `max_lv_1 - 5`.
- بناء `stronghold_cfg`:
  `max_marches=needed`, `formation_id=cfg.formation_id`, `search_range=100`, `troops_count=0`, `wait_for_queue=False`, `busy_heroes=list(self._busy_heroes)`.
- ينشئ `StrongholdTask`، يوجه السجلات، ينفذ، يحدث `self._busy_heroes` من `task._busy`، ويعيد النتيجة.

---

#### 4. الأولوية 4 (`prestige_gather` - جمع موارد الهيبة) (السطور 433-496)
- فحص التفعيل العام وتفعيل المهمة.
- تحديث بيانات الهيبة: `await self._refresh_merit_data()`.
- استخراج الموارد قيد الجمع حالياً: `active_gather = await self._get_active_gather_types()`.
- استخراج مستوى القلعة: `castle_lv = self._get_castle_level()`.
- تصفية الموارد غير المكتملة `uncompleted`:
  * حلقة فور على `PRESTIGE_GATHER_RESOURCES` (قمح، خشب، حديد، فضة):
    - فحص هل المهمة منجزة `q.get("is_done")` أو المورد قيد الجمع حالياً `item["res_type"] in active_gather` -> يتم التخطي.
    - فحص قيود اللعبة لمستوى القلعة:
      * حديد (`res_type == 4`) و `castle_lv < 10`: يتم تخطيه.
      * فضة (`res_type == 5`) و `castle_lv < 15`: يتم تخطيه.
    - إضافة المورد غير المكتمل لـ `uncompleted`.
- إذا كانت `uncompleted` فارغة: يعيد `TaskResult.ok("موارد الهيبة مكتملة أو قيد الجمع", action=CoordinatorAction.NEXT_PRIORITY)`.
- حلقة إرسال المسيرات على الموارد غير المكتملة:
  * لكل مورد: إنشاء `gather_cfg` بمقدار `max_marches=1`, `max_heroes=2`, `allow_partial=True`, `min_load_ratio=0.0`.
  * إنشاء `GatherTask`، تنفيذها، وتحديث `self._busy_heroes.update(task._busy_heroes)` و `self._used_pets.update(task._used_pets)`.
  * **معالجة الإخفاق داخل الحلقة**:
    - إذا كان `stop_reason in ("NO_ARMY", "8009")`: يعيد فوراً `TaskResult.fail("نفاد الجيش...", action=CoordinatorAction.TERMINATE, stop_reason="NO_ARMY")`.
    - إذا كان `stop_reason in ("QUEUE_FULL", "8004")`: يعيد فوراً `TaskResult.fail("الفيالق ممتلئة", action=CoordinatorAction.WAIT_AND_RETRY_SAME, stop_reason="QUEUE_FULL")`.
  * فاصل عشوائي بين إرسال الموارد: `await asyncio.sleep(round(random.uniform(4.0, 7.0), 2))`.
- عند الانتهاء: يعيد `TaskResult.ok(f"تم إرسال {sent_total} مسيرة هيبة", action=CoordinatorAction.NEXT_PRIORITY, sent=sent_total)`.

---

#### 5. الأولوية 5 (`transport` - نقل الموارد) (السطور 501-522)
- فحص `transport.enabled`. إن كان معطلاً يعيد `SKIP_PRIORITY`.
- فحص الإحداثيات `target_x, target_y`: إن كانت مفقودة أو صفرية يعيد `SKIP_PRIORITY`.
- فحص كاش الحد اليومي: `is_transport_daily_limit_reached(account_id, int(tx), int(ty))`:
  إن تحقق يعيد `TaskResult.ok("تم بلوغ الحد اليومي للنقل", action=CoordinatorAction.SKIP_PRIORITY)`.
- تشغيل `TransportTask(self.conn, dict(cfg))`.
- إذا أعادت النتيجة `result.data.get("daily_limit_reached")`:
  يتم تسجيل بلوغ الحد اليومي عبر `set_transport_daily_limit_reached(...)`.
- يعيد `result`.

---

#### 6. الأولوية 6 (`ruins` - استكشاف الأطلال) (السطور 527-541)
- فحص `ruins.enabled`. إن كان معطلاً يعيد `SKIP_PRIORITY`.
- ضبط الإعدادات: `ruins_cfg["max_marches"] = 1` و `busy_heroes = list(self._busy_heroes)`.
- تشغيل `RuinsTask(self.conn, ruins_cfg)`.
- تحديث `self._busy_heroes.update(getattr(task, "_busy", set()))`.
- يعيد `result`.

---

#### 7. الأولوية 7 (`combat` - القتال الشامل) (السطور 546-573)
- فحص `combat.enabled`. إن كان معطلاً يعيد `SKIP_PRIORITY`.
- فحص نوع الهدف `choice`: تحويل إلى أحرف صغيرة.
  * **عزل العفريت الصارم (Rule 7 Compliance)**:
    `if choice == "elf":` تسجل رسالة أن العفريت غير متاح هنا ويعيد:
    `TaskResult.ok("elf غير متاح", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="elf_removed")`.
- بناء `combat_cfg`:
  * `monster_type = choice`
  * `max_marches = 15`
  * `min_lv = 1`, `max_lv = int(cfg.get("level", 35))`
  * `formation_id = int(cfg.get("formation_id", 1))`
  * `search_range = 120`
  * `troops_count = int(cfg.get("troops_count", 0))`
  * `busy_heroes = list(self._busy_heroes)`
- تشغيل `MonsterTask`، تحديث `self._busy_heroes` من `task._busy` أو `task._busy_heroes`، ويعيد النتيجة.

---

#### 8. الأولوية 8 (`stronghold` - المعاقل العامة) (السطور 578-601)
- فحص `stronghold.enabled`. إن كان معطلاً يعيد `SKIP_PRIORITY`.
- قراءة العدد المطلوب: `needed = int(cfg.get("count", 2))`.
- بناء `stronghold_cfg`:
  * `max_marches = needed`
  * `min_lv = 1`, `max_lv = int(cfg.get("level", 30))`
  * `formation_id = int(cfg.get("formation_id", 1))`
  * `search_range = int(cfg.get("search_range", 100))`
  * `troops_count = int(cfg.get("troops_count", 50000))`
  * `busy_heroes = list(self._busy_heroes)`
- تشغيل `StrongholdTask`، تحديث `self._busy_heroes`، ثم إجبار تحديث بيانات الهيبة `await self._refresh_merit_data(force=True)`.
- يعيد النتيجة.

---

#### 9. الأولوية 9 (`gold_gather` - جمع الذهب) (السطور 606-622)
- فحص `gold_gather.enabled`. إن كان معطلاً يعيد `SKIP_PRIORITY`.
- فحص وجود مواقع التحالفات: `if not cfg.get("locations"):` يعيد `TaskResult.ok("لا توجد مواقع ذهب", action=CoordinatorAction.SKIP_PRIORITY)`.
- تمرير `busy_heroes = list(self._busy_heroes)`.
- تشغيل `GoldGatherTask`، تحديث `self._busy_heroes`، وإرجاع النتيجة.

---

#### 10. الأولوية 10 (`gather` - الجمع الخارجي المفتوح) (السطور 627-675)
- فحص `gather.enabled`. إن كان معطلاً يعيد `SKIP_PRIORITY`.
- فحص شروط القلعة للمورد:
  * حديد (`res_type == 4`) و `castle_lv < 10`: يعيد `TaskResult.ok("...", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="CASTLE_LV_LOW")`.
  * فضة (`res_type == 5`) و `castle_lv < 15`: يعيد `TaskResult.ok("...", action=CoordinatorAction.SKIP_PRIORITY, stop_reason="CASTLE_LV_LOW")`.
- بناء `gather_cfg`:
  * `max_marches = int(cfg.get("max_marches", 10))`
  * `search_range = int(cfg.get("search_range", 100))`
  * `max_heroes = 2`
  * `busy_heroes = list(self._busy_heroes)`
  * `used_pets = list(self._used_pets)`
- **تفعيل مكافأة الجمع (Gather Boost)**:
  * إذا كان `cfg.get("use_boost", False)`: ينشئ `GatherBoostTask(self.conn, {"enabled": True})` وينفذها داخل `try/except`.
- تشغيل `GatherTask`، وتحديث `_busy_heroes` و `_used_pets`.
- يعيد `result`.

---

### 3.6 التشغيل المباشر من سطر الأوامر (`Standalone CLI Runner`) (السطور 681-803)
- يستقبل المعاملات عبر `argparse`:
  * `--email / -e`: البريد الإلكتروني.
  * `--duration / -d`: المهلة بالدقائق (افتراضياً 20.0).
  * `--priority / -p`: قائمة أولويات مخصصة.
- يحمل الحسابات من `core.session_manager.SessionManager`.
- يحمل الإعدادات من قاعدة البيانات `core.database.get_castle(target_email)`.
- يدمج إعدادات `march_manager` ويقرأ إعداد الهيبة `raw_cfg.get("prestige", {}).get("enabled", True)`.
- ينشئ اتصال `GameConnection(acc)` ويتصل بالسيرفر وينتظر حزم التهيئة (`cityCtrl` أو `lordInfoCtrl`) بحد أقصى 15 دورة (كل دورة 0.3 ثانية).
- يشغل المنسق `MarchCoordinatorTask(conn, coord_cfg)` ويطبع النتائج ثم يغلق الاتصال بأمان `await conn.close()`.

---

## 4. جدول استجابات وأكواد أخطاء السيرفر العشرين وسلوك `ExcludeManager`

يوضح الجدول التالي التشريح الكامل للأكواد العشرين المحددة في النظام، ومدلولاتها، وردود فعل المهام وسلوك `ExcludeManager`:

| كود الخطأ | الاسم الرسمي للعبة (Game Protocol Constant) | المعنى والسبب الفني | استجابة المهام الفرعية (`stop_reason` / `result_code`) | سلوك `ExcludeManager` (`confirm` أم `release`) | منطق إعادة المحاولة وتحديث الحالة (Retry & State Mutations) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **8004** | `Err_MAP_QUEUE_FULL` | طوابير المسيرات للقلعة ممتلئة بالكامل | تعيد `"QUEUE_FULL"` | **`release`** (تحرير فوري للهدف) | إيقاف الإرسال، وتحديث سقف الطوابير المرصودة. في المنسق تترجم إلى `WAIT_AND_RETRY_SAME` للانتظار 3 دقائق. |
| **9007004** | `Err_HERO_QUEUE_LIMIT` | تجاوز الحد الأقصى لطوابير الأبطال | تعيد `"QUEUE_FULL"` | **`release`** (تحرير فوري للهدف) | تطابق كود 8004 تماماً في تحرير الهدف والتوقف. |
| **8009** | `Err_NOT_ENOUGH_ARMY` | نقص في القوات المتاحة بالقلعة | تعيد `"NO_ARMY"` | **`release`** (تحرير فوري للهدف) | فحص المسيرات النشطة بالخارج: إن وجدت ينتظر عودتها، وإن انعدمت يوقف المهمة نهائياً. في المنسق تترجم إلى `TERMINATE`. |
| **8035** | `Err_ARMY_CAPACITY_LIMIT` | تجاوز سعة مسيرة اللورد أو ساحة التدريب | تعيد `"SUCCESS"` بعد المعالجة أو تتجاوز الهدف | **`release`** عند الفشل، و **`confirm`** عند نجاح الإعادة | تقليص الجيش فورياً بنسبة 15-18% (`scale = 0.82..0.85`)، وحفظ السعة المتعلمة عبر `record_learned_march_capacity`، وإعادة إرسال نفس الحزمة فوراً. لا يتم استبعاد الهدف لأنه صالح. |
| **8032** | `Err_STAMINA_EMPTY` | نفاد طاقة اللورد بالكامل لشن الهجوم | تعيد `"STAMINA_EMPTY"` | **`release`** (تحرير فوري للهدف) | إنهاء فوري لكافة محاولات الهجوم القتالي. في المنسق تترجم إلى `NEXT_PRIORITY`. |
| **10002** | `Err_ENERGY_NOT_ENOUGH` | طاقة اللورد غير كافية لشن الهجمة | تعيد `"STAMINA_EMPTY"` | **`release`** (تحرير فوري للهدف) | تعامل مطابقة لـ 8032 بإنهاء المهمة والانتقال للأولويات غير المستهلكة للطاقة. |
| **10003** | `Err_ENERGY_BUY_LIMIT` | استنفاد الحد الأقصى لشراء الطاقة اليومي | تعيد `"STAMINA_EMPTY"` | **`release`** (تحرير فوري للهدف) | تعامل مطابقة لـ 8032 و 10002. |
| **9007020** | `Err_HERO_BUSY` | البطل محجوز بمسيرة أو تكليف خارجي | تعيد `"HERO_BUSY"` | **`release`** (تحرير الهدف) | إضافة أبطال المسيرة إلى `_busy_heroes` فوراً، واستدعاء بطل بديل من الذاكرة وإعادة المحاولة على الهدف. |
| **8014** | `Err_TARGET_NOT_EXIST` | الهدف اختفى أو انتهت مدته على الخريطة | تعيد `"TARGET_OCCUPIED"` أو `"HERO_BUSY"` | **`release`** في بعض المهام و **`confirm`** في أخرى | إذا اعتبر بطلاً مشغولاً يتم استبعاده، وإذا اعتبر هدفاً منتهياً يتم البحث عن هدف بديل. |
| **8015** | `Err_TARGET_PEACE_SHIELD` / `Err_PET_BUSY` | درع حماية للهدف أو انشغال الحيوان الأليف | تعيد `"HERO_BUSY"` في الجمع و `"TARGET_OCCUPIED"` في القتال | **`release`** للهدف | في `gather.py` يضاف الحيوان إلى `_used_pets` لمنع إرساله واختيار حيوان بديل. |
| **8027** | `Err_MAP_QUEUE_NPC_LEVEL_OUT` | المستوى مغلق ويتطلب القتل الأول للمستويات السابقة | تعيد `"NPC_LEVEL_LOCKED"` | **`release`** (تحرير الهدف فوراً) | تسجيل السقف المتعلم `_learned_max_npc_level = target_lv - 1` وتخفيض مستوى البحث فوراً وإعادة المحاولة. |
| **8037** | `Err_RUINS_ALREADY_ACTIVE` / `Err_CANNOT_ATTACK_ALLY` | مسيرة أطلال نشطة بالفعل أو الهدف حليف | تعيد `"ALREADY_ACTIVE"` | **`release`** (تحرير الهدف) | إنهاء فوري لمهمة الأطلال مع `already_active=True` لمنع تكرار المحاولات. في المنسق تترجم إلى `SKIP_PRIORITY`. |
| **8041** | `Err_RESOURCE_EXHAUSTED` / `Err_CASTLE_LV_LOW` | مستوى القلعة غير كافٍ للمورد أو نفاد الحقل | تعيد `"CASTLE_LV_LOW"` | **`release`** (تحرير الهدف) | تخطي المورد الحالي والانتقال لمورد آخر متوافق مع مستوى القلعة. |
| **8042** | `Err_RESOURCE_OCCUPIED_BY_OTHER` / `Err_CASTLE_LV_LOW` | الحقل مشغول أو مستوى القلعة غير كافٍ | تعيد `"CASTLE_LV_LOW"` أو `"TARGET_OCCUPIED"` | **`release`** أو **`confirm`** بحسب نوع المهمة | استبعاد الحقل وتجربة هدف بديل فوراً. |
| **8046** | `Err_RUINS_TIME_INVALID_OR_EXPIRING` | مدة استكشاف الأطلال غير صالحة أو الطلل يوشك على الزوال | تعيد `"INVALID_TIME_OR_EXPIRING"` | **`release`** (تحرير الهدف) | الانتقال إلى طلل آخر يمتلك وقتاً متبقياً كافياً. |
| **8060** | `Err_MAP_TARGET_MARCHING` | توجد مسيرة متجهة للهدف حالياً | تعيد `"TARGET_OCCUPIED"` | **`confirm`** (تثبيت الاستبعاد) | استبعاد الهدف في قاعدة بيانات المملكة لمنع كافة الحسابات من استهدافه، والانتقال لهدف بديل. |
| **8062** | `Err_WALL_TRAPS_IN_MARCH` / `Err_TARGET_OCCUPIED` | فخاخ الجدار في المسيرة أو الهدف مشغول | تعيد `"TARGET_OCCUPIED"` | **`confirm`** (تثبيت الاستبعاد) | تثبيت استبعاد الهدف في الملف والانتقال لهدف بديل. استبعاد فخاخ 800-899 في كود تجهيز الجيش يمنع هذا الخطأ من المنبع. |
| **8063** | `Err_TARGET_BATTLE_IN_PROGRESS` | الهدف يخوض معركة حالياً على الخريطة | تعيد `"TARGET_OCCUPIED"` | **`confirm`** (تثبيت الاستبعاد) | تثبيت استبعاد الهدف المشغول في الملف والانتقال لهدف بديل فوراً. |
| **8095** | `Err_MAP_QUEUE_RESOURCE_HELP_OUT_ONE_DAY` | بلوغ الحد اليومي لمساعدة ونقل الموارد للهدف | تعيد `daily_limit_reached=True` | **`release`** | تسجيل بلوغ الحد اليومي للهدف في `_DAILY_TRANSPORT_LIMIT_CACHE` وتخطي المهمة لبقية اليوم. |
| **16001** | `Err_CMD_OPTING` | خادم اللعبة مشغول بمعالجة أمر متزامن للقلعة | تعيد `"CMD_OPTING"` | **`release`** (تحرير فوري للهدف) | انتظار عشوائي من 10 إلى 16 ثانية لفك القفل على السيرفر وإعادة المحاولة مرتين قبل الاستسلام. |

---

## 5. محاكمة بروتوكول التنسيق ومطابقة حالات `stop_reason` وتضارب الهيبة

### 5.1 جدول المقارنة الشامل لكافة قيم `stop_reason` و `status` وترجمتها في المنسق

| القيمة المرجعة من المهمة الفرعية | نوع الحقل المرجع في `TaskResult.data` | السلوك المفترض في المنسق | المعالجة الحقيقية في `_fallback_action` | الإجراء الناتج (`CoordinatorAction`) | التقييم الهندسي والخلل المرصود |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `QUEUE_FULL` / `8004` / `9007004` | `stop_reason` أو `status` | انتظار عودة المسيرات وإعادة المحاولة | معالجة صريحة في السطر 210 | `WAIT_AND_RETRY_SAME` | سليم |
| `NO_ARMY` / `8009` | `stop_reason` | إنهاء المنسق لعدم وجود جيش | معالجة صريحة في السطر 212 | `TERMINATE` | سليم |
| `critical_no_army` | `status` | إنهاء المنسق | معالجة صريحة في السطر 212 | `TERMINATE` | سليم |
| `STAMINA_EMPTY` | `stop_reason` | تخطي للأولويات التي لا تتطلب طاقة | معالجة صريحة في السطر 214 | `NEXT_PRIORITY` | سليم |
| `stamina_empty` | `status` | تخطي للأولويات التي لا تتطلب طاقة | معالجة صريحة في السطر 214 | `NEXT_PRIORITY` | سليم |
| `NOT_EVENT_DAY` | `stop_reason` | تخطي فوري للأولوية الحالية | معالجة صريحة في السطر 216 | `SKIP_PRIORITY` | سليم |
| `CASTLE_LV_LOW` | `stop_reason` | تخطي فوري للأولوية الحالية | معالجة صريحة في السطر 216 | `SKIP_PRIORITY` | سليم |
| `skipped` / `already_done` / `already_active` | `status` | تخطي فوري للأولوية الحالية | معالجة صريحة في السطر 216 | `SKIP_PRIORITY` | سليم |
| **`WEAK_ARMY`** | `stop_reason` (تُرمى كـ `RuntimeError` في `base_task.py`) | إيقاف الهجمات القتالية مؤقتاً أو انتظار عودة الفيالق | **غير معالجة إطلاقاً (ساقطة سهواً)** | **`NEXT_PRIORITY`** (سقوط في الـ default) | **خلل حرج**: عندما يقل الجيش عن 50% من التشكيلة، تسقط المهمة وينتقل المنسق للأولوية التالية التي قد تكون قتالية فتفشل مجدداً! |
| **`SUICIDE_RISK`** | `stop_reason` | تخطي فوري لأولويات القتال للهدف المرتفع أو تقليص المستوى | **غير معالجة إطلاقاً (ساقطة سهواً)** | **`NEXT_PRIORITY`** (سقوط في الـ default) | **خلل حرج**: الهدف أقوى من القلعة بكثير، والمنسق لا يعلم أنه انتحار ويتعامل معه كخطأ عابر. |
| **`NPC_LEVEL_LOCKED`** | `stop_reason` | إعادة المحاولة بمستوى أدنى أو تخطي القتال | **غير معالجة إطلاقاً (ساقطة سهواً)** | **`NEXT_PRIORITY`** (سقوط في الـ default) | **خلل حرج**: كود 8027 يعني أن المستوى مقفل بالقتل الأول، والمنسق يتجاهل الحالة تماماً. |
| **`REBEL_PREREQUISITE_FAILED`**| `stop_reason` | تخطي فوري لعدم وجود تحالف أو قاعة حرب | **غير معالجة إطلاقاً (ساقطة سهواً)** | **`NEXT_PRIORITY`** (سقوط في الـ default) | **خلل**: المنسق لا يميز بين فشل مؤقت وفشل هيكلي دائم في متطلبات الحساب. |
| **`CMD_OPTING`** / `16001` | `stop_reason` | انتظار 15 ثانية لفك القفل ثم إعادة المحاولة | **غير معالجة إطلاقاً (ساقطة سهواً)** | **`NEXT_PRIORITY`** (سقوط في الـ default) | **خلل كارثي**: السيرفر مقفل بمعالجة سابقة، والمنسق يقفز فوراً للأولوية التالية فتفشل هي الأخرى بكود 16001 ويفشل المنسق بالكامل في ثوانٍ! |
| `NO_HEROES` / `HERO_BUSY` | `stop_reason` | انتظار عودة الأبطال من المسيرات | **غير معالجة إطلاقاً** | **`NEXT_PRIORITY`** | يسقط في الانتقال للتالي مع أن الأبطال قد يعودون خلال ثوانٍ. |
| `NO_TARGET` / `TARGET_OCCUPIED` | `stop_reason` | تخطي الأولوية لعدم وجود أهداف | **غير معالجة إطلاقاً** | **`NEXT_PRIORITY`** | يسقط في الانتقال للتالي. |

---

### 5.2 تحليل تضارب معرفات مهام الهيبة (`PRESTIGE_QUEST_IDS`) وجذوره

#### 1. رصد التضارب البرمجي الصارخ بين الملفين:
- **في `tasks/base_task.py` (السطور 89-100)**:
  * `"stronghold": 4112019` (الهجوم على معقل الهيبة - 3 هجمات).
  * `"gather": 4112006` (جمع موارد الهيبة الإجمالي - 25 ألف مورد).
  * `"train": 4112001` (تدريب الجنود).
- **في `tasks/march_coordinator.py` (السطور 53-67)**:
  * `"stronghold": 4112030` (معرف مختلف تماماً عن العقد المشترك!).
  * `"gather_food": 4112000`
  * `"gather_wood": 4112001` (تصادم مباشر! المعرف 4112001 هو تدريب جنود في BaseTask، بينما هو جمع خشب في المنسق!).
  * `"gather_iron": 4112002`
  * `"gather_silver": 4112003`

#### 2. الجذر الفني للمشكلة (Root Cause Analysis):
1. **اختلاف تصنيف نظام المهام في سيرفر اللعبة**:
   - المعرفات `4112000..4112003` تمثل مهام الهيبة اليومية من النمط الفردي لكل مورد (قمح، خشب، حديد، فضة).
   - المعرف `4112006` يمثل مهمة الجمع التراكمي الشاملة لجميع الموارد بحمولة 25,000.
   - المعرف `4112019` هو المعرف القديم لمعقل الهيبة (3 هجمات)، بينما `4112030` هو المعرف الجديد في تحديثات اللعبة الأخيرة للحدث.
2. **عزل القواميس وغياب التوحيد**:
   - قام مطور `march_coordinator.py` بتعريف قاموس محلي مستقل `PRESTIGE_QUEST_IDS` في رأس الملف متجاهلاً القاموس المعرف في الكلاس الأب `base_task.py`!
   - عندما يستدعي المنسق دالة `self._get_quest_info("stronghold")`، تقوم الدالة المحلية في السطر 276 بقراءة القاموس المحلي للمنسق (`4112030`)، بينما لو استدعت أي مهمة فرعية (مثل `StrongholdTask`) الدالة الموروثة `super().get_prestige_quest_info("stronghold")` فإنها ستقرأ القاموس الأب (`4112019`)!
   - **النتيجة**: تعيد إحدى الدالتين `found=False` والأخرى تعيد `found=True` لنفس الحساب ونفس المهمة، مما يؤدي إلى فشل فحص اكتمال معقل الهيبة أو جمع الهيبة وتكرار الهجمات دون مبرر أو تخطيها بالخطأ!

---

## 6. نقد الفريق الأحمر (Red Team Critique)

### 6.1 ثغرات التصميم المعماري (Architectural Bugs)
1. **تشتت المسؤولية بين `base_task.py` والمهام الفرعية**:
   - `BaseTask` يحتوي على كود تنفيذي ضخم جداً خاص بالقتال والمسيرات (`get_combat_heroes`, `get_march_army`, `select_combat_pet`, `_pick_balanced_combat_troops`) كان ينبغي أن يكون في كلاس وسيط `CombatMarchTask`، لأن مهام أخرى ترث من `BaseTask` (مثل مهام داخل القلعة `train.py`, `watermill.py`, `smuggler.py`) تجبر على تحميل وتوارث دوال مسيرات القتال دون حاجة لها.
2. **ازدواجية وتناقض `PRESTIGE_QUEST_IDS`**:
   - وجود نسختين متضاربتين من القاموس في `base_task.py` و `march_coordinator.py` يكسر مبدأ الحقيقة الواحدة (Single Source of Truth).
3. **غياب التوحيد في بنية `TaskResult.data`**:
   - بعض المهام تضع سبب التوقف في `result.data["stop_reason"]`، وبعضها في `result.data["status"]`، وبعضها في `result.data["reason"]` (مثل `TaskResult.queue_full()` في `base_task.py:77`)، وبعضها مثل `AbraTask:918` تضعه فقط في نص `message` وتترك `data` فارغة تماماً! مما يعمي المنسق عن اتخاذ القرار الصحيح.

### 6.2 سباقات البيانات والحالات الحرجة (Race Conditions)
1. **سباق حجز الأبطال والجيش بين الفيالق المتتالية في المنسق**:
   - المنسق يملك متغيرات داخلية `self._busy_heroes` و `self._used_pets`، لكنه لا يملك `_used_army` على مستوى المنسق ككل!
   - عندما تنتهي أولوية `prestige_invaders` وتنتقل إلى `prestige_stronghold`، لا يتم تمرير القوات المشغولة `_used_army` إلى المهمة التالية. فإذا كانت المسيرة الأولى لا تزال في طريق الذهاب ولم تحدث الذاكرة الحية بعد، تعتقد المهمة الثانية أن كامل قوات القلعة متوفرة، فترسل مسيرة تتجاوز الرصيد الحقيقي وتقع في خطأ `8009`!
2. **سباق فحص واحتجاز الأهداف (`check_target_busy_or_marched`)**:
   - الفحص يتم عبر استعلام 1006/22 ثم مزامنة 1006/1000 ثم انتظار 0.7 ثانية. خلال هذا الفارق الزمني (700ms) يمكن لحساب آخر أو لاعب منافس إرسال مسيرة لنفس الهدف والوصول إليه قبل انطلاق حزمة 1007/2.

### 6.3 تسريبات الذاكرة واستهلاك الموارد (Memory Leaks & CPU Starvation)
1. **تراكم معالجات السجلات (Logger Handler Leak)**:
   - في دالة `_forward_logs(self, subtask: BaseTask)` بالسطر 246 في `march_coordinator.py`:
     ```python
     subtask.log.handlers = list(self.log.handlers)
     subtask.log.propagate = True
     ```
     في كل دورة للمنسق وفي كل أولوية، يتم إنشاء كائنات مهام جديدة وتكرار ربط `handlers` وتفعيل `propagate=True`. مع استمرار تشغيل البوت لأيام، يؤدي ذلك إلى تكرار طباعة السجل الواحد 10 أو 20 مرة في التيرمنال وتضخم استهلاك الرام!
2. **تسريب مستمعي الحزم (Packet Listener Leak)**:
   - في `base_task.py:1195`، يتم استدعاء `self.conn.add_packet_listener(_capture_sync)`.
   - في حال حدوث استثناء غير متوقع داخل `try` وكان الكود يفتقر لـ `finally` محكم في بعض السيناريوهات أو المهام الأخرى، يظل المستمع محجوزاً في كائن الاتصال للأبد مع كل استدعاء لفحص الهدف.

### 6.4 الاستثناءات غير المعالجة والانهيارات القاتلة (Unhandled Exceptions)
1. **رمي `RuntimeError: WEAK_ARMY` دون التقاطه في الكلاس الأب**:
   - دالة `get_march_army` في `base_task.py:1029` ترمي صراحة:
     `raise RuntimeError(f"WEAK_ARMY: قوة الجيش...")`
     إذا استدعت أي مهمة فرعية هذه الدالة ولم تحطها بـ `try/except` صريح، فإن الاستثناء ينهار ويوقف المهمة كاملة بحالة `TaskState.ERROR` وتوقف غير منضبط!
2. **تحويل القيم الفارغة إلى أرقام (`int(None)`)**:
   - في `march_coordinator.py` السطور 324-326:
     `shared_form = self.config.get("combat", {}).get("formation_id", 1)`
     إذا كان المستخدم قد وضع `formation_id: null` في Firebase، فإن تمريره إلى `int()` داخل المهام الفرعية دون فحص يرفع `TypeError: int() argument must be a string... not 'NoneType'`.

### 6.5 حالات القفل الميت والجمود (Deadlocks & Cascade Hangs)
1. **حلقة القفل الميت في خطأ 16001 (`CMD_OPTING`)**:
   - إذا استجاب السيرفر بكود 16001 أثناء أولوية معينة وفشلت محاولات الإعادة المحلية، تعيد المهمة `stop_reason="CMD_OPTING"`.
   - يسقط هذا الكود في `_fallback_action` إلى `NEXT_PRIORITY`.
   - يبدأ المنسق فوراً بعد 1.5 ثانية الأولوية التالية ويرسل حزمة إلى نفس السيرفر المشغول!
   - يستجيب السيرفر مجدداً بـ 16001، فيقفز المنسق للأولوية الثالثة، وهكذا يتم استهلاك كافة الأولويات العشر وإهدار دورة التنسيق بالكامل في أقل من 20 ثانية دون تنفيذ أي مسيرة!
2. **جمود الانتظار في `_wait_for_returning_march`**:
   - في مهام مثل `abra.py` و `monster.py`، عند انتظار فيلق عائد بناءً على `finish_time` المتوقع:
   - إذا تم تسريع الفيلق، أو إلغاؤه، أو انقطع اتصال السيرفر وتغير معرف الطابور، تظل المهمة نائمة تنتظر طابوراً لم يعد موجوداً حتى انتهاء أقصى مهلة انتظار.

---

## 7. الخاتمة والتوصيات المعمارية (Architectural Recommendations)

1. **توحيد قاموس `PRESTIGE_QUEST_IDS`**: حذف القاموس المحلي المكرر في `march_coordinator.py`، والاعتماد الكامل على `PRESTIGE_QUEST_IDS` المركزي في `base_task.py` بعد تصحيح معرف المعقل إلى `4112030` وفصل معرفات الجمع الفردية عن الجمع الشامل `4112006`.
2. **تحديث `_fallback_action` في `march_coordinator.py`**:
   إضافة معالجة صريحة للحالات الخمس الحرجة:
   - `WEAK_ARMY` -> تحويله إلى `CoordinatorAction.TERMINATE` أو `WAIT_AND_RETRY_SAME`.
   - `SUICIDE_RISK` -> تحويله إلى `CoordinatorAction.SKIP_PRIORITY`.
   - `NPC_LEVEL_LOCKED` -> تحويله إلى `CoordinatorAction.SKIP_PRIORITY`.
   - `REBEL_PREREQUISITE_FAILED` -> تحويله إلى `CoordinatorAction.SKIP_PRIORITY`.
   - `CMD_OPTING` -> إدخال فترة نوم أمان (20 ثانية) قبل الانتقال أو إعادة المحاولة بـ `WAIT_AND_RETRY_SAME`.
3. **توحيد حقل النتيجة في `TaskResult`**: إلزام كافة المهام بإرجاع `stop_reason` موحد وإجراء `action` صريح يمنع اللجوء للـ Fallback إلا في حالات الطوارئ القصوى.
4. **تتبع الموارد والقوات المشغولة مركزياً**: تزويد المنسق بوعاء مشترك `self._used_army` يُمرر تباعاً لكافة الأولويات العشر لمنع خطأ `8009`.
