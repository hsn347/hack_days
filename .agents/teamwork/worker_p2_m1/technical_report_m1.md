# التقرير الفني المستقل للمرحلة الأولى: أداة قياس خط الأساس والتشخيص الأولي للبيئة قبل التعديل (M1 / R4)
## Technical Report: Baseline Measurement Tooling & Pre-Fix Profiling Architecture

**تاريخ التقرير:** 2026-11-03  
**الوكيل المنفذ:** `worker_p2_m1` (teamwork_worker)  
**المرجع التنظيمي:** دستور الوكلاء `AGENTS_CONSTITUTION.md` وقواعد `GEMINI.md` (البند 5: إلزامية إرفاق ملف تقرير مستقل مسبقاً)  
**الوثيقة المرجعية للمهمة:** `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` و `survey_report.md`  
**الملفات المحظورة قطيعاً:** `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py` (التزام صارم بنسبة 100%)  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostic Rationale)

تتطلب الترقية الهندسية الشاملة لمنصة البوت (وفق `ORIGINAL_REQUEST.md` و `ROOT_CAUSE_AND_PLAN_P2.md`) معالجة أربعة محاور جوهرية:
1. ترقيم صفحات قلاع المسؤول وفصل إعدادات config الضخمة (R1).
2. تصحيح دورة حياة العمليات الحية ومصدر الحقيقة للـ Threads (R2).
3. القضاء على تسريبات الذاكرة وموارد المعالج ومقابض النظام (R3).
4. التحقق الكمي المنهجي واختبارات التحمل طويلة الأمد (R4).

وفق مبادئ الهندسة الصارمة ونزاهة الاختبارات، لا يمكن الحكم على نجاح التحسينات المعمارية في المراحل اللاحقة (M2 إلى M6) أو إثبات انعدام تسريب الذاكرة والمعالج بدون **خط أساس كمي دقيق وموثق (Documented Pre-Fix Baseline)** تم قياسه قبل إدخال أي تعديل على كود المنظومة.

### متطلبات أداة القياس المستقلة (`tools/measure_baseline.py`):
1. **دقة قياس الذاكرة الحقيقية (Process RSS)**: استخدام استدعاءات نظام تشغيل Windows الأصلية عبر `ctypes.windll.psapi.GetProcessMemoryInfo` (بنية `PROCESS_MEMORY_COUNTERS_EX`) للحصول على `WorkingSetSize` و `PrivateUsage` و `PeakWorkingSetSize` بدقة بالغة، مع دعم تكاملي لمكتبة `psutil` إن وجدت.
2. **تتبع ذاكرة بايثون الداخلية (Heap Tracing)**: الاستعانة بـ `tracemalloc` لقياس حجم الذاكرة المخصصة الحالية وذروتها (Peak Heap).
3. **رصد مقابض نظام التشغيل (OS Handles)**: استدعاء `ctypes.windll.kernel32.GetProcessHandleCount` لرصد مقابض الملفات والأحداث المفتوحة.
4. **تعداد وتصنيف الخيوط النشطة (Thread Inventory)**: مسح `threading.enumerate()` وحصر إجمالي الخيوط، وتصنيف خيوط البوت (`bot-*`)، وخيوط النظام وعمال AsyncIO، والخيوط الشبحية (Daemon threads).
5. **مراقبة مقابس الشبكة (Open Sockets)**: فحص المقابس المفتوحة وتوثيق نشاط الاتصالات.
6. **فحص الهياكل العامة التسعة في `api_server.py`**:
   - `_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`.
   - قياس عدد العناصر وحجم السجلات المتراكمة في طوابير السجلات `_log_qs`.
7. **قياسات قاعدة البيانات وملفات الـ WAL**:
   - حجم ملف `database/castles.db` بالبايت والميغابايت.
   - رصد وجود وحجم مجلات المعاملات `castles.db-wal` و `castles.db-shm`.
   - إحصاء عدد السجلات للمستخدمين والقلاع وحالة النشاط.
8. **استهلاك المعالج (CPU % Idle & Active)**:
   - قياس استهلاك المعالج خلال فترة خمول (Idle sampling).
   - قياس استهلاك المعالج وأزمنة الاستجابة خلال حمل تشغيلي معياري محاكي (Active operation load).

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Implementation Logic & Architecture)

### 2.1. التصميم المعماري لأداة `tools/measure_baseline.py`
تم تصميم الأداة لتعمل في نمطين:
1. **نمط الاستدعاء البرمجي (`SystemResourceMonitor`)**:
   - توفير فئة متكاملة عالية الكفاءة يمكن تضمينها واستدعاؤها برمجياً في أي سكربت اختبار أو أداة مراقبة.
   - توفير دوال:
     - `snapshot()`: التقاط لقطة فورية لجميع مقاييس الموارد.
     - `diff(snap_before, snap_after)`: حساب الفروقات المطلقة والنسبية بين لقطتين زمنيتين.
     - `measure_cpu(duration_seconds)`: قياس نسبة المعالج على نافذة زمنية محددة.
     - `inspect_globals()`: فحص آمن داخل قفل `api_server._lock`.
     - `inspect_db()`: فحص مؤشرات وحجم قاعدة البيانات ومجلات WAL.
2. **نمط سطر الأوامر المستقل (CLI Standalone Execution)**:
   - تشغيل دورة تقييم شاملة تتضمن:
     1. جمع بيانات البيئة والنظام (OS, CPU cores, Python version, Process ID).
     2. التقاط خط الأساس في حالة الخمول (Idle Baseline Snapshot).
     3. قياس استهلاك المعالج في الخمول (Idle CPU %).
     4. تشغيل حمل قياسي خفيف ومعياري لاختبار كفاءة المعالج واستجابة الاستعلامات وقراءة الذاكرة (Active Operations Load).
     5. التقاط قياسات الحمل التشغيلي (Active Snapshot & CPU %).
     6. تنفيذ دورة تنظيف وجمع المهملات (Post-teardown GC) والتقاط القياسات البعدية.
     7. تصدير المخرجات المهيكلة إلى ملف JSON: `tools/baseline_metrics_prefix.json`.
     8. صياغة تقرير Markdown احترافي شامل: `tools/BASELINE_METRICS_PREFIX.md`.

### 2.2. الحفاظ على العزل والأمان والنزاهة
- **صفر اتصال شبكي**: الأداة لا تتصل بأي سيرفرات خارجية أو خدمات إنتاج.
- **صفر تعديل على ملفات الكود الحالية**: الالتزام الصارم بملكية الملفات في M1؛ لا يتم تعديل أي ملف في المستودع باستثناء إنشاء `tools/measure_baseline.py` ومخرجاتها في `tools/`.
- **الالتزام الكامل بالحظر القطعي**: لا يتم الاقتراب من `game_client.py` أو `core/onemt_auth.py` أو `core/onemt_bot.py`.
- **نزاهة القياس**: استخدام المقاييس الحقيقية للنظام المضيف (Windows PSAPI و Kernel32 ومكتبات بايثون القياسية) دون أي قيم وهمية (No Hardcoded/Dummy values).

---

## 3. الملفات والأوامر التي ستُنفذ بالتفصيل والنتائج المتوقعة (Execution Plan & Commands)

| الرقم | الإجراء / الملف المستهدف | تفاصيل التنفيذ | النتيجة المتوقعة |
|---|---|---|---|
| 1 | كتابة `tools/measure_baseline.py` | إنشاء أداة المراقبة والقياس الشاملة متضمنة فئة `SystemResourceMonitor` ودوال التقييم وتوليد تقارير JSON و Markdown | إنشاء ملف سليم بنسبة 100% بدون أي أخطاء لغوية أو استيرادات مفقودة |
| 2 | تشغيل `python tools/measure_baseline.py` | تشغيل أداة القياس عبر PowerShell لقياس خط الأساس قبل الإصلاح وتصدير التقارير | توليد `tools/baseline_metrics_prefix.json` و `tools/BASELINE_METRICS_PREFIX.md` وخروج بكود `0` |
| 3 | التحقق من صحة ملفات التقارير المولدة | فحص محتوى `baseline_metrics_prefix.json` و `BASELINE_METRICS_PREFIX.md` للتأكد من احتوائها على كافة المقاييس المطلوبة | توثيق دقيق لكافة الأرقام الحقيقية (RSS, CPU, Threads, Handles, Globals, DB) |
| 4 | تشغيل جناح الاختبارات `python tests/run_all_tests.py` | تشغيل الاختبارات الأربعة الموحدة (Tier 1 إلى Tier 4) للتحقق من سلامة البيئة المرجعية قبل إدخال أي تعديلات في المراحل اللاحقة | نجاح كافة الاختبارات الـ 30 بنسبة 100% (30 Passed, 0 Failed) |
| 5 | كتابة تقرير التسليم `handoff.md` وإخطار المشرف | توثيق النتائج وفق بروتوكول Handoff المكون من 5 أقسام، وإرسال رسالة للمشرف العام `849edb08-8a01-463a-a4d9-889f072bccf9` | استكمال المرحلة M1 بنجاح كامل واستعداد المنظومة للمرحلة M2 |

---

## 4. تشخيص تفصيلي لمعالجة استدعاءات 64-bit Windows ctypes وسلامة قياس المقابض والذاكرة

### 4.1. التشخيص (Diagnosis)
أظهر التشغيل التجريبي الأول لـ `tools/measure_baseline.py` عودة قيمة الذاكرة RSS والمقابض بـ 0.
بالتحليل الجنائي الهندسي لبيئة بايثون 64-bit على Windows:
- استدعاء `_kernel32.GetCurrentProcess()` يعيد المقبض الوهمي `(HANDLE)-1` (وهو `0xFFFFFFFFFFFFFFFF` بعرض 64-bit).
- مكتبة `ctypes` بافتراضاتها الافتراضية تعامل القيمة العائدة كـ 32-bit signed integer (`0xFFFFFFFF` أو `-1`) ما لم يتم تعيين `restype = ctypes.c_void_p`.
- تمرير هذا المقبض المبتور إلى `GetProcessMemoryInfo` و `GetProcessHandleCount` يتسبب في خطأ `ERROR_INVALID_HANDLE (6)` وفشل الاستدعاء بصمت.
- بالإضافة إلى ذلك، يجب ضبط `argtypes` لـ `GetProcessMemoryInfo` ليقبل `[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]` مع التحقق من توفر الدالة في `kernel32` (حيث نُقلت دوال PSAPI في Windows 7 والإصدارات الأحدث إلى `kernel32.dll`) أو `psapi.dll`.

### 4.2. الإجراء التصحيحي المستهدف (Remediation)
1. تعديل `tools/measure_baseline.py`:
   - ضبط صريح لـ `restype` و `argtypes` لكافة دوال Windows API المستدعاة:
     - `_kernel32.GetCurrentProcess.restype = ctypes.c_void_p`
     - `_kernel32.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]`
     - `_kernel32.GetProcessHandleCount.restype = ctypes.c_int`
     - البحث عن `GetProcessMemoryInfo` في `_kernel32` أولاً ثم `_psapi`:
       - `fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]`
       - `fn.restype = ctypes.c_int`
2. إعادة تشغيل `python tools/measure_baseline.py` للتحقق من قراءة الأرقام الحقيقية بدقة (الذاكرة الحقيقية RSS والمقابض الحقيقية لنظام التشغيل).
