# التقرير الفني المسبق: خطة تنفيذ المرحلة M4 (استئصال تسريبات الذاكرة وخفض استهلاك المعالج R3)
## Technical Plan Artifact — Milestone 4: Memory & CPU Optimization (R3)

**تاريخ الإعداد**: 2026-11-03  
**المحرر المسند**: Worker M4 (`teamwork_worker`)  
**المتطلب الأساسي**: متطلب R3 من وثيقة `ORIGINAL_REQUEST.md` ووثيقة `ROOT_CAUSE_AND_PLAN_P2.md` (المرحلة 4).  
**الالتزام الصارم**: تطبيق تام للقاعدة رقم 5 من `GEMINI.md` قبل تنفيذ أي تعديل أو تشغيل أي أمر، والالتزام بحظر الملفات المحظورة الثلاثة (`game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`) والعمل المحلي حصراً دون رفع أو اتصال بالإنتاج.

---

## 1. التشخيص الدقيق للأسباب ولماذا هذا الإجراء مطلوب (Root Cause Diagnosis)

كشف المسح الميداني الكودي الشامل (`explorer_survey_p2_2/survey_report.md`) عن وجود 4 اختناقات ومسارات تسريب رئيسية تتسبب في هدر الموارد وتراكم استهلاك الذاكرة والمعالج بمرور الوقت:

### 1.1 تسريب هياكل البيانات والقواميس العامة (`api_server.py` و `proxy/proxy_manager.py`)
- **المشكلة**: عند تشغيل خيط بوت `_bot_thread`، يتم تسجيل القلعة في قواميس عامة (`_threads`, `_stop_events`, `_log_qs`, `_castle_emails`, `_castle_users`). عند حدوث أخطاء مصادقة أو خروج مبكر (الأسطر 708-716، 723-731)، أو انتهاء الخيط في `finally:`، كان يُنسى تنظيف بعض القواميس مثل `_castle_emails`، مما يتسبب في بقاء معرفات وإيميلات القلاع في الذاكرة بصورة تراكمية دائمة.
- **مشكلة `_deleted_castles`**: كانت تُستخدم كـ "حاجز طوارئ" لمنع كتابة الخيوط المنتهية في قاعدة البيانات، ولكن لم يكن يتم تفريغ المعرفات منها إطلاقاً، مما يجعلها تنمو دون سقف وتمنع أي قلعة يُعاد إنشاؤها بنفس المعرف من حفظ حالتها.
- **مشكلة `_castle_bindings` في البروكسي**: عند حذف القلعة نهائياً من النظام، تظل ارتباطاتها البروكسية عالقة في الذاكرة وفي ملف `user_proxy_bindings.json`.

### 1.2 انعدام انتظار الخيوط وتفشي الخيوط اليتيمة (Zero Thread Joins & Zombie Threads)
- **المشكلة**: جميع عمليات إيقاف البوت (`stop_bot`, `stop_all_bots`, `delete_castle`, `delete_user`) كانت تكتفي بوضع إشارة `stop_event.set()` وحذف الكائنات من القواميس فوراً دون استدعاء `thread.join(timeout=...)`.
- **النتيجة**: يستمر الخيط في العمل بالخلفية كخيط يتيم (Orphaned/Zombie Thread) غير متتبع، وعند إعادة التشغيل يحدث تداخل خيوط وتنافس على نفس الحساب وقاعدة البيانات.

### 1.3 عمى مقابس WebSockets واختناق ThreadPoolExecutor بقاعدة البيانات
- **المشكلة**: مقابس `/ws/logs` و `/ws/status` و `/ws/user-status` كانت تعمل بحلقات إرسال فقط (`send_text` / `send_json`). عند إغلاق العميل للمتصفح دون إرسال بيانات، لا يعلم السيرفر بانقطاع الاتصال ما لم تفشل دالة الإرسال. وإذا كانت الحالة مستقرة، تستمر الكوروتينات بالعمل في الخلفية للأبد.
- **استنزاف SQLite في `ws_user_status`**: كل 0.8 ثانية، كان المقبس يستدعي `asyncio.to_thread(_sync_collect_user_statuses)`، مما ينشئ اتصالات متكررة بـ SQLite وينفذ 4 أوامر PRAGMA واستعلامات متعددة لكل قلعة، مسبباً استهلاك 32+ استعلاماً في الثانية للمستخدم الواحد، واختناق خيوط `ThreadPoolExecutor`.

### 1.4 هدر المعالج في حلقة الـ 25 دقيقة وتحميل ملفات السجلات بالكامل
- **المشكلة في `bot_manager.py` (3766-3768)**: الانتظار بين الدورات (25 دقيقة = 1500 ثانية) كان يتم عبر حلقة `while slept < remaining:` تستيقظ كل ثانية واحدة عبر `await asyncio.sleep(1.0)`، مما يولد 1500 استيقاظ لكل قلعة لكل دورة، بينما كائن البوت يمتلك بالفعل `self._async_stop_event`.
- **المشكلة في `prune_log_file_24h`**: استخدام `f.readlines()` لتحميل ملفات السجلات بالكامل في الذاكرة ثم إعادة كتابتها، مسبباً ضغط ذاكرة وI/O كل 1000 سطر سِجل.
- **المشكلة في `importlib.reload`**: إعادة تحميل موديولات البوت ديناميكياً عند بدء كل خيط مما يستهلك دورات المعالج ويحدث ارتباكاً في تعريفات الكلاسات بالذاكرة.

---

## 2. المنطق والخطوات الهندسية المعتمدة (Logic & Steps to Apply)

### الخطوة 1: ضبط دورة حياة القواميس والهياكل العامة والتنظيف المتماثل
1. إعادة هيكلة `_bot_thread` في `api_server.py` بكتلة `try...finally` شاملة وموحدة تبدأ فور تسجيل الخيط وتنتهي بضمان استدعاء `pop` لكافة الهياكل العشرة:
   - `_threads.pop(castle_id, None)`
   - `_stop_events.pop(castle_id, None)`
   - `_bot_managers.pop(castle_id, None)`
   - `_log_qs.pop(castle_id, None)`
   - `_conn_states.pop(castle_id, None)`
   - `_castle_users.pop(castle_id, None)`
   - `_castle_emails.pop(castle_id, None)`
   - `_reserved.discard(castle_id)`
   - معالجة `_user_stopped`.
2. تنظيف `_deleted_castles`: تفريغ معرف القلعة فور انتهاء الخيط وتحرير الموارد بأمان.
3. إضافة دوال تنظيف ارتباطات البروكسي `remove_castle_proxy` و `remove_user_proxy_bindings` في `proxy/proxy_manager.py`، واستدعاؤها عند حذف القلعة أو المستخدم.

### الخطوة 2: تطبيق الإيقاف الحتمي وانتظار الخيوط المنظم (`_stop_and_join_bot`)
1. بناء دالة مركزية `_stop_and_join_bot(castle_id: str, timeout: float = 3.0) -> bool`:
   - استدعاء `mgr.stop()` و `ev.set()`.
   - خارج القفل العام `_lock`، انتظار انتهاء الخيط عبر `t.join(timeout=timeout)`.
   - إذا استمر الخيط حياً بعد المهلة، نقله فوراً إلى القاموس التشخيصي `_stalled_threads` وتوثيقه، لمنع الخيوط الشبحية.
   - تنظيف مراجع القلعة في الذاكرة وتفريغها من `_deleted_castles` بعد اكتمال الموت.
2. تطبيق الدالة على مسارات: `stop_bot`, `stop_all_bots`, `delete_castle_endpoint`, `delete_user_endpoint`.

### الخطوة 3: كشف انقطاع WebSockets وإلغاء الاستعلام الدوري لـ SQLite
1. إضافة كشف فوري لانقطاع مقابس WebSockets (`ws_logs`, `ws_status`, `ws_user_status`):
   - إطلاق مهمة قراءة متزامنة أو فحص استقبال رسائل الإلغاء/الانقطاع (`websocket.receive()`)، بحيث يتم إنهاء حلقة الكوروتين فوراً بمجرد إغلاق العميل للمتصفح.
2. في `ws_user_status`:
   - إلغاء استدعاء `asyncio.to_thread(_sync_collect_user_statuses)` كل 0.8 ثانية.
   - استبداله بفحص سريع في الذاكرة (In-Memory State / Version Cache) يتم تحديثه لحظياً مع أحداث البوت، وبث التحديثات فقط عند وجود تغير حقيقي، مما يخفض استعلامات SQLite في وضع السكون إلى الصفر المطلق.

### الخطوة 4: خفض استهلاك المعالج وتقليم السجلات بنظام التدفق
1. في `bot_manager.py:3806`:
   - استبدال حلقة الـ 1 ثانية بانتظار حدث الإيقاف غير المتزامن:
     ```python
     try:
         await asyncio.wait_for(self._async_stop_event.wait(), timeout=remaining)
     except asyncio.TimeoutError:
         pass
     ```
2. في `prune_log_file_24h`:
   - استبدال `lines = f.readlines()` بآلية اقتصاص ذكية تقرأ من نهاية الملف عبر `seek` عند كبر حجم الملف، واستخدام ملف مؤقت للكتابة المباشرة دون احتجاز كامل الملف في الذاكرة.
3. في `api_server.py:858-864`:
   - إزالة استدعاءات `importlib.reload` غير المبررة عند بدء كل خيط.

---

## 3. تفاصيل الملفات والسطور والتغييرات المستهدفة والنتائج المتوقعة

| الملف المستهدف | النطاق / السطور | الإجراء البرمجي | النتيجة المتوقعة |
| :--- | :--- | :--- | :--- |
| `api_server.py` | 130-145 | إضافة `_stalled_threads: Dict[str, Dict[str, Any]] = {}` والتوثيق | هيكل معتمد لعزل الخيوط المتعطلة وتشخيصها |
| `api_server.py` | 162-192 | إعادة كتابة `prune_log_file_24h` بدون `f.readlines()` | تقليم الملفات الكبيرة في 0 ميغابايت ذاكرة إضافية |
| `api_server.py` | 665-735, 870-905 | دمج كتلة `try...finally` شاملة في `_bot_thread` وتنظيف `_castle_emails` دائماً | صفر تسريب في القواميس العامة العشرة |
| `api_server.py` | 858-864 | إزالة `importlib.reload` التلقائي | منع إعادة ترجمة الأكواد في الذاكرة وخفض CPU |
| `api_server.py` | دالة جديدة (بجوار 3050) | إضافة `_stop_and_join_bot` مع مهلة `join(timeout=3.0)` وعزل `_stalled_threads` | دورة حياة حتمية للخيوط ومنع الخيوط اليتيمة |
| `api_server.py` | 1387-1428 | استخدام `_stop_and_join_bot` وتنظيف البروكسي في `delete_castle_endpoint` | تنظيف القلعة ومواردها والبروكسي وتفريغ `_deleted_castles` |
| `api_server.py` | 2253-2315 | استخدام `_stop_and_join_bot` وتنظيف البروكسي في `delete_user_endpoint` | إيقاف نظيف وانتظار خيوط المستخدم وحذف ارتباطات البروكسي |
| `api_server.py` | 3012-3062 | استخدام `_stop_and_join_bot` في `stop_bot` و `stop_all_bots` | انعدام تام للخيوط العالقة بعد الإيقاف |
| `api_server.py` | 3392-3498 | إضافة Disconnect Detection في `ws_logs`, `ws_status`, `ws_user_status`، وكاش الذاكرة لـ `ws_user_status` | التحرير الفوري لموارد السوكت وإلغاء استنزاف SQLite |
| `proxy/proxy_manager.py` | 240-300 | إضافة `remove_castle_proxy` و `remove_user_proxy_bindings` | تنظيف الذاكرة وملف JSON فور حذف القلعة |
| `bot_manager.py` | 3803-3809 | استبدال حلقة الـ 1 ثانية بـ `asyncio.wait_for(self._async_stop_event.wait(), remaining)` | خفض استهلاك المعالج إلى 0.0% في فترة الانتظار واستجابة إيقاف لحظية (<100ms) |
| `tests/test_memory_cpu_m4.py` | ملف جديد | اختبارات وحدة محكمة لتأكيد كافة النقاط الخمس لـ R3 | إثبات برمجي hermetic لنجاح كافة متطلبات M4 |

---

## 4. خطة التحقق والاختبار بعد التعديل (Verification Plan)
1. تشغيل الفحص البرمجي المنفصل: `python tests/test_memory_cpu_m4.py`
2. تشغيل جناح فحص العمليات الحية: `python tests/test_live_operations_m3.py` (4/4 PASS)
3. تشغيل جناح الاختبارات الشامل للمنصة: `python tests/run_all_tests.py` (30/30 PASS)
4. تشغيل سكربت القياس المحلي: `python tools/measure_baseline.py`
5. إعداد تقرير التسليم `handoff.md` وإرسال الرسالة إلى المشرف عبر `send_message`.
