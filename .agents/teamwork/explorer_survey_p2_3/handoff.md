# Handoff Report — Explorer Survey 3 (Testing & Soak Infrastructure Explorer - R4)

## 1. Observation (الملاحظات المباشرة)
- **ملف `api_server.py` (السطور 131–142)**: تعريف الهياكل العامة التسعة للذاكرة:
  ```python
  _lock         = threading.RLock()
  _threads:     Dict[str, threading.Thread] = {}   # castle_id → thread
  _stop_events: Dict[str, threading.Event]  = {}   # castle_id → stop signal
  _bot_managers: Dict[str, Any]             = {}   # castle_id → BotManager instance
  _reserved:    Set[str]                    = set() # castle_ids محجوزة
  _log_qs:      Dict[str, "queue.Queue[str]"] = {}  # castle_id → queue
  _conn_states: Dict[str, str]              = {}    # castle_id → state
  _user_stopped: Set[str]                   = set() # castle_ids متوقفة يدوياً
  _castle_emails: Dict[str, str]            = {}    # castle_id → email
  _castle_users:  Dict[str, str]            = {}    # castle_id → user_id
  _deleted_castles: Set[str]                = set() # castle_ids المحذوفة
  ```
- **ملف `api_server.py` (السطور 1400–1411 و 2136–2148)**: في عمليتي حذف قلعة وحذف مستخدم:
  يتم استدعاء `_threads.pop(castle_id, None)` فوراً دون استدعاء `t.join(timeout=...)` خارج القفل للتأكد من موت الخيط، مما يترك الخيوط الجارية كخيوط يتيمة (Orphaned Threads) في الخلفية. كما أن `_deleted_castles` عبارة عن Set غير محدودة (Unbounded) تنمو للأبد ولا يتم تنظيف أي معرف قلعة منها بعد انتهاء مهامها.
- **ملف `api_server.py` (السطور 842–848)**:
  ```python
  import sys, importlib
  for mod_name in ("tasks.march_manager", "bot_manager"):
      if mod_name in sys.modules:
          try:
              importlib.reload(sys.modules[mod_name])
          except Exception:
              pass
  ```
  إعادة تحميل الوحدات عبر `importlib.reload` عند بدء كل خيط بوت يولد كائنات وفئات متكررة بالذاكرة ويسبب تسريباً وتنافسية خطيرة.
- **ملف `api_server.py` (السطور 1460–1628)**: الدالة `get_admin_live_processes`:
  لا تدعم الترقيم (Pagination) إطلاقاً وتُعيد كافة العمليات في مصفوفة واحدة، وتعتبر أي خيط يبدأ بـ `bot-` قيد التشغيل الفعلي (`running`) دون تدقيق مهمته، مما يعطي أرقاماً غير دقيقة.
- **ملف `api_server.py` (السطور 3296–3310)**: معالج `ws_user_status`:
  يستدعي `asyncio.to_thread(_sync_collect_user_statuses, user_id)` كل 0.8 ثانية، والذي ينفذ استعلام SQLite وحلقة تستدعي `_get_real_status` التي تأخذ `_lock`، مما يجهد المعالج ويسبب تأخيراً في حلقة أحداث AsyncIO عند تعدد المتصفحات المفتوحة.
- **ملف `core/database.py` (السطور 1631–1656)**: الدالة `get_all_castles`:
  تستعلم كافة صفوف جدول `castle_states` وتفك تسلسل حقل `config` JSON الضخم لجميع القلاع دفعة واحدة دون أي `LIMIT / OFFSET`.
- **ملفات القياس الحالية**:
  توفر `tools/benchmark_admin_baseline.py` و `tools/benchmark_m1_stress_suite.py` أنماطاً ممتازة لقياس `tracemalloc` ومؤقتات Windows عالية الدقة عبر `ctypes.windll.winmm.timeBeginPeriod(1)`.

## 2. Logic Chain (سلسلة الاستدلال المنطقي)
1. من الملاحظة (api_server.py: 1400–1411 و 2136–2148)، فإن حذف القلعة أو المستخدم يفرغ القاموس دون التحقق من موت الخيط، مما يؤدي بالضرورة إلى تراكم خيوط بايثون النشطة في النظام (`threading.active_count()`) وزيادة استهلاك المقابض والذاكرة.
2. من الملاحظة (api_server.py: 842–848)، إعادة تحميل الوحدات عبر `importlib.reload` بشكل متكرر عند بداية كل دورة تشغيلية هي سبب رئيسي لنمو الذاكرة التدريجي (Memory Bloat) في بايثون.
3. من الملاحظة (api_server.py: 3296–3310)، الـ polling الدوري كل 800 ميلي ثانية لكل مستخدم متصل عبر WebSockets يؤدي حتماً إلى ارتفاع استهلاك المعالج وتأخر حلقة الأحداث (Event Loop Lag)، ولابد من تحويله إلى نظام مدفوع بالأحداث (Event-Driven) أو تقليل التكرار واستخدام الذاكرة الحية.
4. من الملاحظة (core/database.py: 1631–1656 و api_server.py: 1718–1785)، تحميل كافة القلاع وكافة إعدادات الـ config لكل القلاع يفسر ثقل لوحة التحكم وتضخم حمولة الـ HTTP، ويؤكد حتمية تطبيق الترقيم الحقيقي (Pagination) في الـ API وقاعدة البيانات مع استبعاد الـ config من القوائم السريعة (تطبيق R1).
5. من الملاحظة (api_server.py: 1460–1628)، اقتصار حالات العمليات الحية على الحالات الست الحقيقية وعزل الخيوط المتعطلة كـ `stalled` وتطبيق الترقيم يحل بصورة جذرية مشكلة العمليات الوهمية والمكررة (تطبيق R2).
6. بناءً على ما سبق، فإن التحقق الشامل يستلزم:
   - أداة خط أساس محلية مستقلة `tools/measure_baseline.py` تقيس (RSS, CPU %, Threads, Handles, Sockets, Queues, Dicts, WAL).
   - مصفوفة الاختبارات الـ 18 الإلزامية التي تغطي كل سيناريو بدقة.
   - سكربت اختبارات التحمل طويلة الأمد `tools/soak_test_lifecycle.py` لإثبات انعدام التسريب التراكمي بميل انحدار خطي $\le 0.05$ MB/cycle وتطابق تام في الخيوط والمقابض.

## 3. Caveats (الافتراضات والحدود)
- لم يتم فتح أو قراءة أو فحص أي من الملفات المحظورة الثلاثة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`) التزاماً صارماً ومطلقاً بالدستور وتوجيهات المهمة.
- تم التحقق من إمكانية قياس RSS والمقابض على بيئة Windows دون اشتراط حزمة `psutil` عبر استدعاءات `ctypes.windll.psapi` و `ctypes.windll.kernel32` مباشرة لضمان عمل خط الأساس محلياً تحت أي ظرف.
- لا توجد أي افتراضات تتطلب اتصالاً بخوادم اللعبة الحية؛ كافة الاختبارات الـ 18 وسكربت التحمل مصممة لتعمل محلياً بنسبة 100% (Hermetic In-Memory / Isolated SQLite).

## 4. Conclusion (الخلاصة والتقييم النهائي)
- تم إنجاز المسح الاستكشافي لبنية القياس واختبارات التحمل بنجاح كامل ومطابقة تامة للمتطلب R4.
- تم توثيق تقرير المسح الشامل في الملف المستقل:
  `e:\osmanli\.agents\teamwork\explorer_survey_p2_3\survey_report.md`
- تضمن التقرير تفصيلاً دقيقاً لبنية أداة القياس `tools/measure_baseline.py`، والمواصفات الكاملة للسيناريوهات الـ 18 الإلزامية، ومنهجية وتصميم سكربت الـ Soak Testing المعتمد على الانحدار الرياضي لمنع التسريبات التراكمية.
- المنظومة جاهزة للانتقال إلى المرحلة التالية.

## 5. Verification Method (طريقة التحقق المستقل)
1. **معاينة تقرير المسح الفني المعتمد**:
   - فحص الملف `e:\osmanli\.agents\teamwork\explorer_survey_p2_3\survey_report.md`.
2. **فحص الالتزام بالملفات المحظورة**:
   - التأكد من عدم فتح أو تعديل `game_client.py` أو `core/onemt_auth.py` أو `core/onemt_bot.py`.
3. **التحقق من جاهزية تشغيل الاختبارات الحالية المعتمدة**:
   - تشغيل جناح الاختبارات الموحد للتحقق من سلامة البيئة:
     `python tests/run_all_tests.py`
