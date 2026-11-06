# التقرير الفني المستقل: خطة التحدي الإجهادي الميداني لأداة قياس خط الأساس (M1 Challenge)
## Technical Report: Stress & Telemetry Precision Challenge for `SystemResourceMonitor`

**تاريخ التقرير:** 2026-11-03  
**الوكيل المنفذ:** `challenger_p2_m1_1` (teamwork_challenger)  
**المرجع التنظيمي:** دستور أسراب الوكلاء `AGENTS_CONSTITUTION.md` وقواعد `GEMINI.md` (البند 5: الإلزامية الصارمة لتقرير فني مستقل مسبقاً قبل أي تعديل أو تشغيل لأي أمر)  
**الهدف:** التحدي التجريبي الميداني الصارم لأداة قياس الموارد `tools/measure_baseline.py` والتحقق من عدم المساس بالملفات المحظورة.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostic Rationale)

قام وكيل التنفيذ `worker_p2_m1` بتسليم المرحلة الأولى متضمنة أداة القياس `tools/measure_baseline.py` وملفات النتائج المرجعية `tools/baseline_metrics_prefix.json` و `tools/BASELINE_METRICS_PREFIX.md`.  
وفق بروتوكول التحدي التجريبي (Empirical Challenger Role):
1. يُحظر الثقة بالادعاءات النظرية أو سجلات التنفيذ السابقة دون إعادة إنتاج واختبار مستقل.
2. يجب إخضاع فئة المراقبة `SystemResourceMonitor` لاختبارات إجهادية عدائية (Adversarial Stress Testing) تكشف حالات الانهيار المحتملة، ومنها:
   - هل تنهار الأداة عند أخذ لقطات متتالية سريعة (Repeated Snapshotting) أو تتسبب هي نفسها في تسريب ذاكرة أو مقابض؟
   - هل تنهار دالة قياس المعالج `measure_cpu_percent` عند تكرار الاستدعاء بفترات زمنية متناهية الصغر (`duration=0.01s` أو `0.05s`) أو عند عدم توفر `psutil`؟
   - هل تنهار استدعاءات `ctypes` لمقابض Windows (`GetProcessHandleCount`) تحت معدل تفريخ وإنهاء كثيف للخيوط (Rapid Thread Spawn & Join Churn)؟
   - هل يتجمد فحص القواميس العامة `inspect_api_server_globals` أو يدخل في حالة قفل ميت (Deadlock) عند وجود عمليات تعديل متزامنة تحت `api_server._lock`؟
   - هل القيم الناتجة للمقاييس الفيزيائية (RSS, Handles, CPU, Database, Threads) حقيقية، منطقية، وغير صفرية؟
   - هل تم الالتزام التام والقطعي بحظر المساس بالملفات الثلاثة المحظورة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`)؟

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Implementation Logic & Architecture)

سيتم إنشاء سكربت اختبار إجهادي مستقل بالكامل `tools/test_monitor_stress.py` يشتمل على 6 حزم اختبارية صارمة:

### حزمة 1: التحقق من الثوابت الفيزيائية والمقاييس غير الصفرية (Invariant & Plausibility Verification)
- التحقق من أن قياس الذاكرة الحقيقية `get_memory_info()` يرجع `rss_bytes > 0` و `rss_mb > 0` و `private_bytes > 0`.
- التحقق من أن عدد المقابض `get_handle_count() > 0` وأن خيوط العملية `active_count >= 1`.
- التحقق من أن فحص قاعدة البيانات يقرأ ملف `castles.db` بدقة ويعيد عدد المستخدمين والقلاع وخصائص الـ PRAGMA دون فتح أقفال كتابة.
- التحقق من سلامة فحص هياكل `api_server` العامة العشرة.

### حزمة 2: الإجهاد بالتصوير المتكرر والاستقرار الداخلي (Repeated Snapshotting Stress)
- تنفيذ 200 لقطة `snapshot()` متتالية في حلقة سريعة.
- التحقق من أن أداة القياس نفسها لا تسرب ذاكرة أو مقابض بصورة تراكمية، وأن دالة حساب الفروقات `SystemResourceMonitor.diff()` تعمل باتساق رياضي تام.

### حزمة 3: الإجهاد بالعينات السريعة للمعالج (Rapid CPU Sampling & Boundary Stress)
- استدعاء `measure_cpu_percent` بنوافذ زمنية بالغة الصغر (`0.01` و `0.05` و `0.1` و `0.2` ثانية) للتأكد من انعدام أخطاء القسمة على صفر أو القيم السالبة.
- قياس المعالج أثناء تشغيل عبء حسابي اصطناعي مكثف في خيط منفصل والتحقق من ارتفاع نسبة المعالج وتواجدها ضمن النطاق المنطقي `0.0 <= cpu <= 100.0`.

### حزمة 4: تفريخ وإنهاء الخيوط المتسارع وتتبع المقابض (Thread Churn & Handle Tracking)
- تفريخ 50 خيطاً يحمل اسم `bot-stress-X` وإنهاؤها بصورة متزامنة وسريعة.
- التحقق من قدرة `get_thread_inventory()` على رصد وتصنيف خيوط البوت بدقة.
- التحقق من أن `get_handle_count()` يستقر بعد انتهاء الخيوط دون التسبب في أخطاء وصول للذاكرة أو أعطال `ctypes`.

### حزمة 5: التزامن والتنافس على قفل خادم الـ API (Concurrent Dictionary Contention & Lock Safety)
- تشغيل خيوط خلفية تقوم بتعديل وإضافة وحذف عناصر في هياكل `api_server` (`_threads`, `_stop_events`, `_conn_states`, `_log_qs`) تحت حماية القفل `api_server._lock`.
- استدعاء `inspect_api_server_globals()` بصورة متكررة بالتزامن مع التعديلات للتحقق من عدم حدوث Deadlock وصحة المجاميع والإحصائيات.

### حزمة 6: سلامة المراقبة عن بعد وحالات الـ Target PID (Remote/Target PID Handling)
- اختبار تهيئة الفئة باستخدام `SystemResourceMonitor(target_pid=os.getpid())` ومطابقة مخرجاتها.

---

## 3. الملفات والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Files, Commands & Expected Results)

### 3.1. الملفات التي ستُنشأ:
- `tools/test_monitor_stress.py`: سكربت الفحص الإجهادي التجريبي المستقل.

### 3.2. الأوامر المزمع تنفيذها:
1. `python tools/test_monitor_stress.py`
   - **النتيجة المتوقعة**: اجتياز الحزم الست بنسبة 100% وخروج بكود 0.
2. فحص حالة الملفات المحظورة عبر تدقيق حالة git وأزمنة التعديل:
   `git status --porcelain core/onemt_auth.py core/onemt_bot.py game_client.py`
   - **النتيجة المتوقعة**: فراغ تام يثبت عدم لمس أي من هذه الملفات إطلاقاً.
3. تشغيل حزمة اختبارات المشروع الموحدة للتأكد من انعدام أي تأثير جانبي:
   `python tests/run_all_tests.py`
   - **النتيجة المتوقعة**: 30 اختباراً ناجحاً بنسبة 100%.

---

