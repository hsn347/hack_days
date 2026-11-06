# تقرير المسح والاستكشاف الشامل: بنية القياس والاختبارات الـ 18 الإلزامية واختبارات التحمل طويلة الأمد (R4)
# Comprehensive Survey Report: Baseline Tooling, 18 Mandatory Scenarios & Soak Testing Architecture

**المستكشف:** `explorer_survey_p2_3` (Testing & Soak Infrastructure Explorer - R4)  
**المجلد المستهدف:** `e:\osmanli\.agents\teamwork\explorer_survey_p2_3\`  
**تاريخ المسح:** 2026-11-02T22:35:00Z  
**المرجعيات الدستورية:** `AGENTS_CONSTITUTION.md` | `ORIGINAL_REQUEST.md` (R1–R4) | `GEMINI.md`  
**وضع النزاهة:** Development Mode (Local Read-Only)  
**الملفات المحظورة:** تم الالتزام الصارم بعدم فتح أو قراءة أو تعديل: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.

---

## 1. الملخص التنفيذي والأهداف الاستراتيجية (Executive Summary)

انطلاقاً من تكليف المهمة R4 والمتطلبات المترابطة (R1, R2, R3, R4) في `ORIGINAL_REQUEST.md`، قام هذا الاستكشاف بمسح معمق لكافة أجزاء المنظومة المحلية في `e:\osmanli`:
1. **أدوات وسكربتات القياس وخط الأساس (Baseline Measurement Tooling)**:
   - فحص آليات قياس استهلاك الذاكرة (RSS Memory) عبر `psutil` و `tracemalloc` ومكتبة Windows PSAPI البديلة في حال عدم توفر حزم خارجية.
   - فحص استهلاك المعالج (CPU % Idle vs Running) وحساب زمن تباطؤ حلقة الأحداث (AsyncIO Event Loop Jitter/Lag).
   - فحص تعداد الـ Threads وحالاتها الحقيقية وتصنيفها.
   - فحص المقابض المفتوحة (Open Handles) ومقابس الشبكة (Sockets) والملفات المفتوحة.
   - فحص أحجام الطوابير (`_log_qs`) وهياكل البيانات العامة التسعة (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`).
   - تصميم الأداة المتكاملة `tools/measure_baseline.py`.
2. **سيناريوهات الاختبار الإلزامية الـ 18 (18 Mandatory Test Scenarios)**:
   - رسم هندسي متكامل ومفصل لكل سيناريو من السيناريوهات الـ 18 المحددة في طلب المستخدم.
   - تحديد شروط البدء (Setup)، المحفز (Stimulus)، تحولات الحالة المتوقعة (State Transition Contract)، فحص الهياكل العامة والذاكرة وقاعدة البيانات (Assertions)، والتنظيف التام بدون أي تسريب (Hermetic Isolation & Teardown).
3. **منهجية وتصميم اختبارات التحمل طويلة الأمد (Continuous Soak Testing Methodology)**:
   - تصميم محاكاة دورات تشغيل متتابعة (Multi-cycle Continuous Execution) تحاكي التشغيل الفعلي لعشرات القلاع عبر عشرات الدورات المتتالية.
   - تصميم تتبع كمي لتراكم الموارد (Resource Growth Telemetry) وفحص انحدار الذاكرة والمقابض والـ Threads بعد انتهاء المهام لضمان انعدام التسريب التراكمي بنسبة 100%.

---

## 2. دراسة ومسح البنية الحالية وتشخيص الثغرات البرمجية في الموارد (Current State & Leak Forensics)

أظهر المسح الميداني للكود المصدري في `api_server.py` و `bot_manager.py` و `core/database.py` وجود عدة أنماط برمجية مسببة لاستهلاك الذاكرة والـ CPU وتراكم الموارد:

### 2.1. تسريب مراجع الـ Threads والكائنات العامة في الذاكرة
في `api_server.py`:
- الهياكل العامة التسعة:
  ```python
  _lock         = threading.RLock()
  _threads:     Dict[str, threading.Thread] = {}
  _stop_events: Dict[str, threading.Event]  = {}
  _bot_managers: Dict[str, Any]             = {}
  _reserved:    Set[str]                    = set()
  _log_qs:      Dict[str, "queue.Queue[str]"] = {}
  _conn_states: Dict[str, str]              = {}
  _user_stopped: Set[str]                   = set()
  _castle_emails: Dict[str, str]            = {}
  _castle_users:  Dict[str, str]            = {}
  _deleted_castles: Set[str]                = set()
  ```
- **الملاحظة الحرجة 1**: عند حذف قلعة (`delete_castle_endpoint` سطر 1370) أو حذف مستخدم (`delete_user_endpoint` سطر 2090)، يتم استدعاء `_threads.pop(cid, None)` فوراً دون انتظار إنهاء الـ Thread عبر `t.join(timeout=...)` خارج القفل. يؤدي ذلك إلى بقاء الـ Thread شغالاً في الخلفية كخيط يتيم (Orphaned Zombie Thread) لا يمكن إيقافه، وإذا حاول الكتابة في قاعدة البيانات قد يتسبب في أخطاء تضارب أو إعادة إحياء بيانات محذوفة.
- **الملاحظة الحرجة 2**: الـ Set المسماة `_deleted_castles` تكبر باستمرار مع كل عملية حذف دون أي تنظيف أو تقليم (Unbounded Growing Set)، مما يمثل تسريباً دائماً للذاكرة طوال فترة عمل السيرفر.
- **الملاحظة الحرجة 3**: في الدالة `_bot_thread` (السطور 842-848):
  ```python
  import sys, importlib
  for mod_name in ("tasks.march_manager", "bot_manager"):
      if mod_name in sys.modules:
          try:
              importlib.reload(sys.modules[mod_name])
          except Exception:
              pass
  ```
  إعادة تحميل الوحدات عبر `importlib.reload` عند بداية كل خيط بوت في بيئة متعددة الخيوط (Multi-threaded) تؤدي إلى:
  - تضخم الذاكرة بسبب إنشاء نسخ جديدة من الدوال والفئات (Class/Module object proliferation).
  - مشاكل تنافسية خطيرة (Race Conditions) بين الخيوط الشغالة حالياً التي تستخدم النسخة القديمة والخيوط الجديدة.

### 2.2. استهلاك الـ CPU والـ Thread Pool في الـ WebSockets
في `api_server.py` سطر 3296:
```python
@app.websocket("/ws/user-status/{user_id}")
async def ws_user_status(websocket: WebSocket, user_id: str):
    await websocket.accept()
    last_data = await asyncio.to_thread(_sync_collect_user_statuses, user_id)
    try:
        await websocket.send_json(last_data)
        while True:
            await asyncio.sleep(0.8)
            curr_data = await asyncio.to_thread(_sync_collect_user_statuses, user_id)
            if curr_data != last_data:
                last_data = curr_data
                await websocket.send_json(curr_data)
```
- **الملاحظة الحرجة 4**: كل عميل متصل ينفذ استدعاء `asyncio.to_thread(_sync_collect_user_statuses)` كل 0.8 ثانية.
  داخل `_sync_collect_user_statuses`: يتم تنفيذ استعلام SQL كامل `db.get_user_castles(user_id)`، ثم حلقة `for` تستدعي `_get_real_status(cid)` لكل قلعة، والتي بدورها تأخذ القفل `_lock = threading.RLock()`.
  عند فتح 10 مستخدمين للوحة التحكم، ينتج عن ذلك مئات الاستعلامات ومحاولات الاستحواذ على القفل في الثانية الواحدة، مما يتسبب في إجهاد المعالج (CPU Spikes) وتباطؤ حلقة أحداث AsyncIO (Event Loop Lag).

### 2.3. غياب الـ Pagination الحقيقي وتحميل كائنات الـ Config الضخمة
- في `api_server.py` سطر 1718 (`/api/admin/users-castles`): يتم جلب كافة المستخدمين وكافة القلاع دفعة واحدة عبر `db.get_all_users()` و `db.get_all_castles()`، مع فك تسلسل كامل لـ `config` JSON لكل قلعة وتوليد حمولة ضخمة تصل لعشرات الميغابايت.
- في `api_server.py` سطر 1460 (`/api/admin/live-processes`): يتم جمع كافة العمليات في مصفوفة واحدة وإعادتها دفعة واحدة للمتصفح دون `page` أو `pageSize`، بينما يقوم المتصفح (`AdminLiveProcesses.tsx`) بإعادة طلب القائمة كاملة كل 5 ثوانٍ (`setInterval`) مما يولد ضغطاً مستمراً على السيرفر.

---

## 3. تصميم وهندسة أداة قياس خط الأساس (`tools/measure_baseline.py`)

لتلبية متطلب R4 والتحقق الكمي قبل وبعد التحسينات، تم تصميم أداة قياس خط أساس مستقلة وقوية:

### 3.1. مصفوفة المقاييس الكمية المستهدفة (Target Quantitative Metrics)

| المقياس | الأداة / الآلية | الوحدة | الوصف والهدف |
|---|---|---|---|
| **RSS Memory** | `psutil.Process().memory_info().rss` أو Windows PSAPI `GetProcessMemoryInfo` | ميغابايت (MB) | قياس حجم الذاكرة الفيزيائية الحقيقية المحجوزة للعملية في نظام التشغيل |
| **Heap Memory** | `tracemalloc.get_traced_memory()` | كيلوبايت (KB) | قياس استهلاك بايثون الداخلي للذاكرة (الحالي والذروة Peak) |
| **CPU % (Idle)** | قياس استهلاك المعالج خلال 5 ثوانٍ من الخمول التام | نسبة مئوية % | التحقق من عدم وجود حلقات نشطة (Spinlocks) أو polling مستمر |
| **CPU % (Running)** | قياس استهلاك المعالج أثناء تشغيل 10 مهام متزامنة | نسبة مئوية % | قياس كفاءة استهلاك المعالج تحت الحمل الحقيقي |
| **Event Loop Lag** | مؤقت عالي الدقة (5ms Sleep Probe) | ميلي ثانية (ms) | قياس زمن تأخر حلقة أحداث AsyncIO بسبب العمليات المعيقة |
| **Thread Count** | `threading.active_count()` و `threading.enumerate()` | عدد خيوط | تصنيف الخيوط: خيط رئيسي، خيوط بوتات (`bot-*`)، عمال AsyncIO، وخيوط عالقة |
| **Open Handles** | `ctypes.windll.kernel32.GetProcessHandleCount` | عدد مقابض | رصد تسريب مقابض نظام التشغيل (الملفات، الأحداث، المؤقتات) |
| **Active Sockets** | `psutil.net_connections()` أو فحص كائنات السوكت | عدد اتصالات | كشف مقابس TCP أو WebSocket التي لم تُغلق بعد انتهاء المهام |
| **Queues Sizes** | مجموع أطوال `_log_qs[cid].qsize()` | عدد عناصر | كشف تراكم السجلات في الذاكرة دون استهلاكها |
| **Global Dict Keys** | فحص أطوال وهياكل القواميس التسعة | عدد مفاتيح + حجم بايت | التحقق من تنظيف المفاتيح بعد انتهاء المهام وحساب حجمها |
| **SQLite WAL Size** | `os.path.getsize(db_path + "-wal")` | كيلوبايت (KB) | رصد تضخم ملف سجل المعاملات قبل الـ Checkpoint |

### 3.2. بنية التنفيذ الهندسية للأداة (`tools/measure_baseline.py`)

تم تصميم الأداة لتعمل بوضعيتين:
1. **وضع مستقل (Standalone CLI Mode)**: يقوم بتشغيل سيناريو قياس كامل، وحفظ النتيجة في ملف JSON مهيكل (`tools/baseline_metrics.json`) يحتوي على:
   - بيانات البيئة والمواصفات (OS, CPU cores, Python version).
   - قياسات الخمول (Idle Baseline).
   - قياسات الحمل التشغيلي (Active Operations Load).
   - قياسات ما بعد التحرير (Post-Teardown & GC).
2. **وضع الاستدعاء البرمجي (Programmatic API Mode)**: فئة `SystemResourceMonitor` تتيح أخذ لقطات زمنية (`snapshot()`) قبل وبعد أي اختبار، وحساب الفرق الدقيق (`delta = snap_after - snap_before`).

```python
# Blueprint for tools/measure_baseline.py (Architectural Design)
import os, sys, time, ctypes, threading, tracemalloc, json, sqlite3
from typing import Dict, Any, List

class SystemResourceMonitor:
    def __init__(self, target_pid: int = None):
        self.pid = target_pid or os.getpid()
        self._has_psutil = False
        try:
            import psutil
            self.psutil_proc = psutil.Process(self.pid)
            self._has_psutil = True
        except ImportError:
            self.psutil_proc = None

    def get_rss_memory_bytes(self) -> int:
        """قياس دقيق لـ RSS بـ psutil أو عبر Windows PSAPI كبديل خالص دون مكتبات خارجية."""
        if self._has_psutil:
            return self.psutil_proc.memory_info().rss
        if sys.platform == "win32":
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', ctypes.c_ulong),
                    ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
        return 0

    def get_handle_count(self) -> int:
        """قياس عدد المقابض المفتوحة عبر Windows Kernel32."""
        if sys.platform == "win32":
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            count = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetProcessHandleCount(handle, ctypes.byref(count)):
                return count.value
        return 0

    def get_thread_breakdown(self) -> Dict[str, Any]:
        """تحليل شامل وتصنيف للخيوط النشطة في بايثون."""
        threads = threading.enumerate()
        breakdown = {
            "total_count": len(threads),
            "bot_threads": [t.name for t in threads if t.name.startswith("bot-")],
            "system_threads": [t.name for t in threads if not t.name.startswith("bot-")],
        }
        return breakdown

    def get_global_dict_metrics(self) -> Dict[str, Any]:
        """فحص أحجام القواميس والهياكل العامة في api_server."""
        import api_server
        with api_server._lock:
            return {
                "threads_count": len(api_server._threads),
                "stop_events_count": len(api_server._stop_events),
                "bot_managers_count": len(api_server._bot_managers),
                "reserved_count": len(api_server._reserved),
                "log_qs_count": len(api_server._log_qs),
                "conn_states_count": len(api_server._conn_states),
                "user_stopped_count": len(api_server._user_stopped),
                "castle_emails_count": len(api_server._castle_emails),
                "castle_users_count": len(api_server._castle_users),
                "deleted_castles_count": len(api_server._deleted_castles),
            }

    def snapshot(self) -> Dict[str, Any]:
        """التقاط لقطة فورية لجميع الموارد."""
        current_heap, peak_heap = (0, 0)
        if tracemalloc.is_tracing():
            current_heap, peak_heap = tracemalloc.get_traced_memory()
        return {
            "timestamp": time.time(),
            "rss_mb": round(self.get_rss_memory_bytes() / (1024 * 1024), 2),
            "heap_current_kb": round(current_heap / 1024, 2),
            "heap_peak_kb": round(peak_heap / 1024, 2),
            "handle_count": self.get_handle_count(),
            "thread_metrics": self.get_thread_breakdown(),
            "global_dicts": self.get_global_dict_metrics(),
        }
```

---

## 4. تصميم وهندسة سيناريوهات الاختبار الإلزامية الـ 18 (The 18 Mandatory Test Scenarios)

تم رسم وتفصيل السيناريوهات الـ 18 وفق متطلب R4 لضمان تغطية كافة حالات الفشل والتشغيل والانقطاع وإعادة الاتصال:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     خريطة السيناريوهات الإلزامية الـ 18                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ [1] تشغيل طبيعي       │ [2] فشل اعتماد        │ [3] دخول جهاز آخر           │
│ [4] فقدان اتصال       │ [5] إعادة اتصال       │ [6] انتظار تسجيل دخول       │
│ [7] انتهاء دورة       │ [8] انتهاء طبيعي      │ [9] إيقاف يدوي              │
│ [10] إيقاف أثناء عمل  │ [11] حذف قلعة شغال    │ [12] حذف مستخدم شغال        │
│ [13] استثناءات بدء    │ [14] استثناءات مهمة   │ [15] انقطاع وعودة WS        │
│ [16] تكرار فتح وتغيير │ [17] تكرار بحث وتصفية │ [18] اكتشاف وعزل خيط معطل   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### السيناريو 1: تشغيل طبيعي (Run Normal Operation)
- **الهدف**: التحقق من دورة حياة التشغيل السليم الكاملة للقلعة.
- **التهيئة (Setup)**: إنشاء قلعة ومستخدم في قاعدة بيانات اختبار مؤقتة مع جلسة صالحة.
- **المحفز (Stimulus)**: استدعاء `_start_bot_internal(req)` أو طلب API `/api/bot/start`.
- **مسار تحول الحالة (State Transition)**:
  `idle` ➔ `starting` (إدراج في `_reserved`) ➔ تشغيل `_bot_thread` ➔ إنشاء `BotManager` ➔ اتصال اللعبة `login_and_connect()` بنجاح ➔ انتقال الحالة إلى `running` (أو `connected`) ➔ تنفيذ الدورة ➔ تحديث الموارد في SQLite.
- **التأكيدات (Assertions)**:
  1. القلعة موجودة في `_threads` و `_bot_managers` وخيطها `t.is_alive() == True`.
  2. استدعاء `/api/admin/live-processes` يرجع القلعة تحت تصنيف `running`.
  3. حقل `_reserved` خالٍ من معرف القلعة فور اكتمال البدء.
- **التنظيف (Teardown)**: إيقاف البوت عبر `stop()` والتحقق من تحرير الخيط.

### السيناريو 2: فشل اعتماد / خطأ مصادقة (Auth Failure)
- **الهدف**: التحقق من التعامل الحازم مع فشل تسجيل الدخول دون تعليق أو حلقات لا نهائية.
- **التهيئة (Setup)**: إنشاء قلعة ببيانات اعتماد غير صالحة (كلمة مرور خاطئة).
- **المحفز (Stimulus)**: بدء تشغيل البوت.
- **مسار تحول الحالة (State Transition)**:
  `idle` ➔ `starting` ➔ فشل `SessionManager.get_or_login()` أو فشل الاتصال ➔ تسجيل رسالة الخطأ ➔ تحديث SQLite إلى `state='error', conn_state='error'` ➔ تشغيل كتلة `finally` فوراً وتفريغ الهياكل العامة.
- **التأكيدات (Assertions)**:
  1. لا يبقى معرف القلعة في `_threads` أو `_bot_managers` أو `_reserved`.
  2. القلعة لا تظهر في قائمة العمليات الحية `/api/admin/live-processes` كعملية نشطة.
  3. حالة القلعة في SQLite هي `error` ورسالة الخطأ واضحة ومسجلة.
  4. عدم تكرار محاولات تسجيل الدخول تجنباً لحظر الحساب.

### السيناريو 3: تسجيل دخول من جهاز آخر (Other Device Login)
- **الهدف**: استجابة البوت الفورية لطرد السيرفر بسبب دخول اللاعب من الهاتف.
- **التهيئة (Setup)**: بوت متصل وفي حالة `running`.
- **المحفز (Stimulus)**: استدعاء كولباك الانقطاع بحزمة الطرد `_on_disconnect(reason="other_device")`.
- **مسار تحول الحالة (State Transition)**:
  `running` ➔ ضبط `_last_kick_reason = "other_device"` ➔ دخول `wait_and_reconnect()` ➔ تحول الحالة إلى `disconnected` ثم `other_login`.
- **التأكيدات (Assertions)**:
  1. في `/api/admin/live-processes` تصنف العملية كـ `other_login` (دخول من جهاز آخر) وليس `running`.
  2. توقف البوت المؤقت عن إرسال أي طلبات لعبة طوال مدة الانتظار.
  3. مؤقت العد التنازلي التنازلي يظهر بوضوح في الواجهة ومطابق لـ `reconnect_wait_seconds`.

### السيناريو 4: فقدان اتصال شبكي مفاجئ (Connection Loss)
- **الهدف**: التعامل مع انقطاع المقبس المفاجئ (TCP Reset / Broken Pipe / Timeout) دون استلام حزمة طرد.
- **التهيئة (Setup)**: بوت شغال متصل.
- **المحفز (Stimulus)**: قطع المقبس من جانب السيرفر الوهمي محلياً.
- **مسار تحول الحالة (State Transition)**:
  `running` ➔ كشف انقطاع المقبس `is_connection_alive() == False` ➔ إغلاق المقبس القديم بأمان ➔ الانتقال إلى `reconnecting`.
- **التأكيدات (Assertions)**:
  1. تحرير كائن السوكت المنقطع وعدم تسريبه في الذاكرة.
  2. عدم انهيار خيط البوت بالاستثناءات غير المعالجة.
  3. تحديث `conn_state` إلى `reconnecting`.

### السيناريو 5: إعادة اتصال حقيقية (Reconnecting)
- **الهدف**: التحقق من مراحل وعدادات إعادة الاتصال المنضبطة.
- **التهيئة (Setup)**: بوت في حالة انقطاع اتصال يبدأ محاولات الاستعادة.
- **المحفز (Stimulus)**: دوران حلقة `for attempt in range(1, max_reconnect_attempts + 1)`.
- **مسار تحول الحالة (State Transition)**:
  `disconnected` ➔ `reconnecting` مع زيادة `reconnect_attempt` (1, 2, ...).
- **التأكيدات (Assertions)**:
  1. تصنيف العملية في العمليات الحية كـ `reconnecting`.
  2. إظهار رقم المحاولة والحد الأقصى للمحاولات بدقة.
  3. استجابة البوت الفورية لأمر الإيقاف أثناء فترة الانتظار بين المحاولات دون انتظار اكتمال الثواني.

### السيناريو 6: انتظار تسجيل دخول لمشكلة مصادقة مؤقتة (Waiting for Re-login)
- **الهدف**: التعامل مع انتهاء صلاحية الـ Token وحاجة الحساب لتجديد الجلسة.
- **التهيئة (Setup)**: جلسة منتهية الصلاحية تتطلب تجديداً من خادم المصادقة.
- **المحفز (Stimulus)**: استدعاء `refresh_session()`.
- **مسار تحول الحالة (State Transition)**:
  `disconnected` ➔ فحص الجلسة ➔ تصنيف الحالة كـ `waiting_relogin` (انتظار إعادة تسجيل الدخول) ضمن الحالات الست المعتمدة.
- **التأكيدات (Assertions)**:
  1. ظهور الحالة بوضوح في لوحة التحكم وتصنيفها الصحيح.
  2. عدم اعتبارها شغالة فعلياً `running`.

### السيناريو 7: انتهاء دورة - انتظار الدورة التالية (Cycle Completion - Waiting for Next Cycle)
- **الهدف**: التحقق من كفاءة وضع الخمول بين الدورات وصفرية استهلاك الـ CPU والشبكة.
- **التهيئة (Setup)**: بوت يعمل في وضع الحلقة الدائمة `run_loop(loop_interval_minutes=60)`.
- **المحفز (Stimulus)**: اكتمال آخر مهمة في خط الإنتاج للدورة الحالية.
- **مسار تحول الحالة (State Transition)**:
  `running` ➔ اكتمال `run_once()` ➔ إغلاق مقبس اللعبة بأمان `await conn.close()` في كتلة `finally` ➔ حساب `next_run_time` بدقة كـ ISO timestamp ➔ تحول الحالة إلى `waiting` ➔ دخول حلقة النوم المجزأة (`await asyncio.sleep(min(1.0, remaining))`).
- **التأكيدات (Assertions)**:
  1. تصنيف العملية في قائمة العمليات الحية كـ `waiting` (بانتظار الدورة التالية).
  2. مقبس اتصال اللعبة مغلق تماماً (Zero Open Sockets) طوال فترة الانتظار.
  3. استهلاك المعالج للمهمة 0.0% CPU.
  4. وجود موعد الدورة القادمة `next_run_time` بدقة متناهية.

### السيناريو 8: انتهاء طبيعي دون دورة قادمة (Natural Completion - No Next Cycle)
- **الهدف**: التحقق من تنظيف العمليات الفردية المنتهية طبيعياً وإزالتها تماماً من العمليات الحية.
- **التهيئة (Setup)**: تشغيل البوت في وضع الدورة الواحدة `is_loop=False`.
- **المحفز (Stimulus)**: انتهاء مهام الدورة بنجاح.
- **مسار تحول الحالة (State Transition)**:
  `running` ➔ اكتمال المهام ➔ إغلاق الاتصال ➔ تحديث SQLite إلى `idle` ➔ خروج خيط البوت وإنهاؤه ➔ تنظيف `_threads` و `_bot_managers`.
- **التأكيدات (Assertions)**:
  1. القلعة تختفي تماماً وبنسبة 100% من قائمة العمليات الحية `/api/admin/live-processes`.
  2. انعدام وجود أي مراجع يتيمة في الهياكل العامة.
  3. حالة القلعة في قاعدة البيانات `idle`.

### السيناريو 9: إيقاف يدوي أثناء الخمول والانتظار (Manual Stop During Waiting)
- **الهدف**: التحقق من الاستجابة اللحظية (< 1 ثانية) لزر الإيقاف أثناء فترة الانتظار بين الدورات.
- **التهيئة (Setup)**: بوت في حالة `waiting` (ينتظر مثلاً 25 دقيقة).
- **المحفز (Stimulus)**: إرسال طلب إيقاف `POST /api/bot/stop/{castle_id}`.
- **مسار تحول الحالة (State Transition)**:
  `waiting` ➔ تفعيل `stop_event.set()` ➔ انكسار حلقة `while slept < remaining` فوراً في أقل من ثانية واحدة ➔ خروج الخيط وتنظيف الهياكل ➔ تحديث SQLite إلى `idle`.
- **التأكيدات (Assertions)**:
  1. زمن الاستجابة للإيقاف أقل من ثانية واحدة (عدم الانتظار لنهاية مدة الدورة).
  2. إزالة القلعة فوراً من العمليات الحية.
  3. تحرير كافة الموارد وانضمام الـ Thread (`join()`).

### السيناريو 10: إيقاف أثناء تنفيذ مهمة جارية (Stop During In-Flight Execution)
- **الهدف**: إيقاف البوت بأمان تام في منتصف تنفيذ مهمة (مثل البناء أو الجمع) دون تجميد أو إفساد البيانات.
- **التهيئة (Setup)**: بوت ينفذ مهمة في خط الإنتاج.
- **المحفز (Stimulus)**: إرسال أمر الإيقاف `stop()`.
- **مسار تحول الحالة (State Transition)**:
  `running` ➔ تفعيل `_stop_event` و `_async_stop_event` ➔ انكسار حلقة المهام عند نقطة الفحص التالية ➔ إغلاق السوكت فوراً ➔ تحرير الأقفال وخروج الخيط.
- **التأكيدات (Assertions)**:
  1. عدم تعليق الخيط أو حدوث Deadlock.
  2. خروج نظيف وتحديث الحالة إلى `idle`.
  3. عدم تلف بيانات الموارد أو إعدادات القلعة.

### السيناريو 11: حذف قلعة أثناء تشغيلها (Delete Castle While Running)
- **الهدف**: التحقق من إيقاف البوت وتنظيف موارده بالكامل عند حذف القلعة ومنع الخيط من إعادة تسجيلها في SQLite.
- **التهيئة (Setup)**: قلعة قيد التشغيل الفعلي في خيط نشط.
- **المحفز (Stimulus)**: استدعاء `DELETE /api/castles/{castle_id}`.
- **مسار تحول الحالة (State Transition)**:
  `running` ➔ تسجيل القلعة فوراً في `_deleted_castles` ➔ إرسال إشارة الإيقاف لـ `mgr` و `stop_event` ➔ انتظار انتهاء الخيط بمهلة زمنية محددة `join(timeout=3.0)` ➔ حذف سجل القلعة من SQLite ➔ تنظيف الهياكل العامة ➔ إزالة المعرف بأمان من `_deleted_castles` بعد التيقن من موت الخيط.
- **التأكيدات (Assertions)**:
  1. خيط البوت يتوقف تماماً وينتهي.
  2. لا يقوم الخيط بإعادة إدراج صف القلعة المحذوفة في SQLite أثناء خروجه.
  3. عدم بقاء معرف القلعة متراكماً في `_deleted_castles` بعد اكتمال التنظيف.

### السيناريو 12: حذف مستخدم وجميع قلاعه أثناء تشغيلها (Delete User While Running)
- **الهدف**: التحقق من الإيقاف الجماعي الآمن والمتوازي لكافة قلاع المستخدم المحذوف.
- **التهيئة (Setup)**: مستخدم لديه 5 قلاع تعمل بالتزامن.
- **المحفز (Stimulus)**: استدعاء `DELETE /api/admin/user/{uid}`.
- **مسار تحول الحالة (State Transition)**:
  حصر جميع قلاع المستخدم في الذاكرة والقاعدة ➔ إرسال إشارات الإيقاف المتزامنة لكافة قلاعه ➔ انتظار انتهاء الخيوط ➔ حذف جميع القلاع وسجل المستخدم وحذف ملفات السجلات المرتبطة بها من القرص ➔ تنظيف شامل للذاكرة.
- **التأكيدات (Assertions)**:
  1. توقف جميع الخيوط الخمسة وانضمامها بنجاح (Zero Leaked Threads).
  2. حذف كافة السجلات التابعة من SQLite بنجاح عبر عملية ذرية واحدة (Atomic Transaction).
  3. تنظيف ملفات `bot_*.log` الخاصة بتلك القلاع من القرص.

### السيناريو 13: استثناءات مرحلة بدء البوت (Bot Start Exceptions)
- **الهدف**: منع بقاء القلعة معلقة في حالة `starting` أو محجوزة في `_reserved` عند فشل التهيئة الأولية.
- **التهيئة (Setup)**: محاكاة خطأ غير متوقع أثناء مرحلة البدء (مثل تلف ملف الإعدادات أو انقطاع مفاجئ).
- **المحفز (Stimulus)**: استدعاء البدء ورمي استثناء قبل اكتمال ربط `BotManager`.
- **مسار تحول الحالة (State Transition)**:
  `starting` ➔ حدوث استثناء ➔ التقاط الخطأ في `try/except` في `_bot_thread` ➔ إزالة القلعة فوراً من `_reserved` ➔ تحديث الحالة إلى `error` في SQLite.
- **التأكيدات (Assertions)**:
  1. القلعة لا تعلق أبداً في حالة `starting`.
  2. قائمة `_reserved` خالية تماماً.
  3. لا يظهر خيط شبحي في الذاكرة.

### السيناريو 14: استثناءات المهام أثناء التنفيذ (In-Flight Task Exceptions)
- **الهدف**: عزل أخطاء المهام الفرعية (مثل تعذر إيجاد معقل أو نفاد طاقة) ومنع انهيار دورة البوت بالكامل.
- **التهيئة (Setup)**: محاكاة استثناء (`KeyError` أو `ValueError`) داخل مهمة معينة (مثل `tasks.building`).
- **المحفز (Stimulus)**: تشغيل خط إنتاج المهام `execute_task_pipeline()`.
- **مسار تحول الحالة (State Transition)**:
  تنفيذ المهمة ➔ حدوث الخطأ ➔ التقاطه في `try/except` على مستوى المهمة ➔ توثيق الخطأ في السجل ➔ متابعة تنفيذ باقي المهام في الدورة بسلام.
- **التأكيدات (Assertions)**:
  1. بقاء خيط البوت وحلقة الأحداث سليمة دون انهيار غير معالج.
  2. استمرار باقي المهام المستقلة المجدولة.
  3. توثيق الاستثناء بوضوح في سجلات القلعة.

### السيناريو 15: انقطاع وعودة اتصالات الـ WebSocket (WebSocket Disconnect & Reconnect)
- **الهدف**: القضاء التام على تسريب مهام AsyncIO ومهام `asyncio.to_thread` عند انقطاع اتصال المتصفح.
- **التهيئة (Setup)**: فتح 30 اتصال WebSocket متزامن مع `/ws/logs/{castle_id}` و `/ws/user-status/{user_id}`.
- **المحفز (Stimulus)**: قطع جميع الاتصالات الـ 30 فجأة ودون إشعار إغلاق رسمي (Abrupt TCP Severing).
- **مسار تحول الحالة (State Transition)**:
  رفع استثناء `WebSocketDisconnect` أو `asyncio.CancelledError` ➔ كسر حلقات الاستماع اللانهائية فوراً ➔ إنهاء مهام الخلفية.
- **التأكيدات (Assertions)**:
  1. عدد مهام `asyncio.all_tasks()` يعود إلى مستواه الأساسي خلال ثانية واحدة.
  2. عدم تراكم خيوط في `ThreadPoolExecutor` الخاص بـ `asyncio.to_thread`.
  3. عند إعادة اتصال العملاء مجدداً، تعمل الاتصالات الجديدة فوراً دون أي تجميد.

### السيناريو 16: تكرار فتح وتبديل الصفحات في الواجهة (Repeated Page Switching)
- **الهدف**: التحقق من صمود وثبات السيرفر وقاعدة البيانات تحت ضغط التنقل السريع بين التبويبات.
- **التهيئة (Setup)**: محاكاة مستخدم يتنقل بسرعة فائقة بين صفحات لوحة التحكم (Users, Castles, Live Processes, Dashboard).
- **المحفز (Stimulus)**: إرسال 200 طلب متتابع وسريع على واجهات الـ API المعنية خلال 5 ثوانٍ.
- **مسار تحول الحالة (State Transition)**:
  استقبال الطلبات ➔ معالجة سريعة عبر الاستعلامات المفهرسة ➔ إرجاع الاستجابات دون تجميد حلقة الأحداث.
- **التأكيدات (Assertions)**:
  1. زمن الاستجابة P95 أقل من 25 ميلي ثانية لكافة الطلبات.
  2. عدم حدوث أخطاء `database is locked` في SQLite.
  3. استقرار الذاكرة وعدم وجود نمو تراكمي بعد انتهاء سيل الطلبات.

### السيناريو 17: تكرار عمليات البحث والتصفية عبر الصفحات (Repeated Search & Filter Queries)
- **الهدف**: التحقق من كفاءة استعلامات التصفية والـ Pagination عند كتابة المستخدم لحروف البحث تباعاً.
- **التهيئة (Setup)**: قاعدة بيانات تحتوي على مئات القلاع والمستخدمين.
- **المحفز (Stimulus)**: إرسال 100 استعلام بحث وتصفية متتابع مع معايير مختلفة (بريد، قلعة، حالة، رقم صفحة).
- **مسار تحول الحالة (State Transition)**:
  تنفيذ استعلامات SQL تتضمن `WHERE LOWER(email) LIKE ? ... LIMIT ? OFFSET ?` بالاعتماد على الفهارس التعبيرية.
- **التأكيدات (Assertions)**:
  1. زمن استعلام قاعدة البيانات لكل طلب < 3 ميلي ثانية.
  2. إرجاع العدد الصحيح لإجمالي النتائج ورقم الصفحة وعدد الصفحات الإجمالي.
  3. عدم تحميل حقول الـ JSON الضخمة (`config`) في نتائج القوائم السريعة.

### السيناريو 18: اكتشاف وعزل الخيوط المتعطلة/العالقة (Stalled Thread Detection & Isolation)
- **الهدف**: كشف الـ Threads التي تجمدت في حلقة مغلقة أو قفل عالق أو استدعاء شبكي حاجب، وعزلها عن العمليات الحية.
- **التهيئة (Setup)**: إنشاء خيط وهمي يحاكي خيط بوت عالق لم يحدث نبضات قلبه (Heartbeat) منذ أكثر من 5 دقائق.
- **المحفز (Stimulus)**: استدعاء واجهة العمليات الحية `/api/admin/live-processes`.
- **مسار تحول الحالة (State Transition)**:
  فحص طابع النبض الأخير `last_heartbeat_time` لكل خيط نشط ➔ إذا تجاوز الفارق الحد المسموح (مثلاً 300 ثانية) ولم يكن في حالة انتظار مشروعة ➔ تصنيف الخيط كـ `stalled` (معطل/عالق) ➔ استبعاده من إجمالي العمليات الحية الشغالة `total_active` ➔ وضعه في قسم تشخيصي منفصل للمسؤول.
- **التأكيدات (Assertions)**:
  1. لا يُحتسب الخيط المتعطل ضمن عداد `running` أو `total_active`.
  2. إتاحته للمسؤول كحالة `stalled` مع تفاصيل التشخيص وزر إيقاف إجباري.
  3. عدم تأثير الخيط المتعطل على سائر العمليات الطبيعية.

---

## 5. منهجية وتصميم اختبارات التحمل طويلة الأمد (Continuous Soak Testing Methodology)

### 5.1. فلسفة الاختبار ونموذج المحاكاة الميدانية
تم تصميم اختبار التحمل طويل الأمد (`tools/soak_test_lifecycle.py`) ليعمل كنظام محاكاة مستمر لا يكتفي بفحص دورة واحدة، بل يكرر دورات تشغيل كاملة عبر مصفوفة من المتغيرات:
- **الحجم التشغيلي**: 10 إلى 20 قلعة افتراضية تعمل بالتوازي عبر خيوط مستقلة.
- **عدد الدورات المتتالية**: من 10 إلى 50 دورة تشغيلية كاملة لكل قلعة.
- **حقن الاضطرابات والتبديل (Chaos Churn Injection)**:
  - 10% من الدورات يتم فيها إرسال إشارة انقطاع دخول جهاز آخر (`other_device`) لاختبار مسار إعادة الاتصال.
  - 5% من الدورات يتم فيها إرسال أمر إيقاف يدوي ثم إعادة تشغيل لاختبار تنظيف الذاكرة وإعادة الربط.
  - 5% من العمليات تخضع لحذف وإعادة إنشاء القلعة لاختبار تنظيف مراجع القلاع المحذوفة.
  - محاكاة متزامنة لـ 20 عميل WebSocket يستمعون للبث اللحظي ويقطعون الاتصال عشوائياً.

### 5.2. القياس التراكمي وتحليل الانحدار الرياضي (Cumulative Telemetry & Regression)
يقوم السكربت بتسجيل قراءات الموارد بعد انتهاء كل دورة تشغيلية وعند ثبات الخمول، وجمعها في سجل بيانات زمني (Telemetry Time Series):
1. **ذاكرة العمليات (RSS Memory in MB)**:
   - حساب ميل الانحدار الخطي (Linear Regression Slope) لاستهلاك الذاكرة عبر الدورات:
     $$\text{Slope} = \frac{\sum (c_i - \bar{c})(m_i - \bar{m})}{\sum (c_i - \bar{c})^2}$$
   - **معيار النجاح الصارم**: بعد أول دورتين (فترة الإحماء واستقرار كاش بايثون)، يجب أن يكون ميل الانحدار مساوياً تقريباً للصفر ($\text{Slope} \le 0.05 \text{ MB/cycle}$). أي نمو مستمر بميل موجب يعد إخفاقاً صريحاً (Memory Leak).
2. **تعداد الخيوط (Thread Count Invariant)**:
   - يجب أن يتطابق عدد الخيوط النشطة عند نهاية الاختبار بعد إيقاف كافة المهام مع عدد الخيوط الأساسي في بداية الاختبار ($\Delta \text{Threads} == 0$).
3. **تعداد المقابض (Handle Count Invariant)**:
   - عدم وجود تراكم مستمر في مقابض نظام التشغيل ($\Delta \text{Handles} \le 0$).
4. **تصفير الهياكل العامة (Zero Dangling Entities)**:
   - التحقق من تصفير كافة القواميس في `api_server` الخاصة بالمهام المنتهية.

---

## 6. مصفوفة مقارنة خط الأساس والتأثير المتوقع للإصلاحات

| المورد / المؤشر | الوضع الحالي (قبل الإصلاح) | الوضع المستهدف (بعد تطبيق R1–R4) | وسيلة التحقق المؤكدة |
|---|---|---|---|
| **تقسيم صفحات قلاع المسؤول** | جلب كافة القلاع وفك تسلسل JSON لكل قلاع السيرفر دفعة واحدة (100% Client-side Slice) | ترقيم حقيقي في الباك إند وقاعدة البيانات (`LIMIT / OFFSET`) مع استبعاد الـ config من القائمة | اختبارات الترقيم `tools/stress_m6_pagination.py` وقياس حجم الحمولة |
| **تصنيف العمليات الحية** | احتساب أي Thread نشط كعملية شغال حتى لو كان معطلاً أو يتيماً، ولا يوجد Pagination | حصر العرض في الحالات الست الحقيقية، ترقيم الصفحات، وعزل الخيوط المتعطلة كـ `stalled` | اختبار سيناريوهات 1، 7، 8، 18 وواجهة `/api/admin/live-processes` |
| **تنظيف الذاكرة ومراجع الخيوط** | استدعاء `pop()` دون انتظار موت الخيط، وتراكم معرفات `_deleted_castles` للأبد | إيقاف بإشارة وانتظار `join(timeout)` خارج القفل، وتنظيف آمن لـ `_deleted_castles` | قياس الهياكل العامة واختبارات السيناريوهات 11 و 12 |
| **استهلاك الـ CPU في الـ WebSockets** | استعلام SQLite متكرر وحساب الحالات تحت القفل كل 0.8 ثانية لكل متصفح | نقل جمع الحالات لخيط خلفي ذكي ببث الأحداث عند التغير فقط (Event-driven) | قياس استهلاك المعالج وتأخر حلقة الأحداث (Loop Lag < 2ms) |
| **نمو الذاكرة التراكمي (Leak)** | نمو مستمر بسبب `importlib.reload` وتراكم المقابض والمهام المعلقة | انعدام النمو التراكمي (Zero Cumulative Leak) وثبات الـ RSS بعد الإحماء | اختبار التحمل الممتد `tools/soak_test_lifecycle.py` |

---

## 7. الخلاصة والتوصيات الهندسية المعتمدة (Architectural Recommendations)

1. **اعتماد تصميم `tools/measure_baseline.py`**:
   - توفير قياسات فورية دقيقة تجمع بين `tracemalloc` للذاكرة البرمجية الداخلية، و Windows PSAPI لقياس RSS الحقيقي بدون أي اعتماديات خارجية مفقودة.
2. **تجهيز جناح الاختبارات الـ 18 المتكامل**:
   - ربط السيناريوهات الـ 18 بحزمة اختبارات مؤتمتة وموحدة (`tests/test_18_scenarios.py` أو أداة مخصصة في `tools/`) يمكن تشغيلها بضغطة زر وتعمل بعزل محلي هرمسي 100% دون لمس قاعدة البيانات الحية.
3. **اعتماد سكربت التحمل `tools/soak_test_lifecycle.py`**:
   - تشغيله كبوابة جودة حاسمة (Quality Gate) قبل اعتماد أي مرحلة نهائية لإثبات صفرية التسريب كمياً ورياضياً.
