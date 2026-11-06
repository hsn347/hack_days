# تقرير الخطة الفنية المستقلة لمرحلة Milestone 5 (F12, F13 / Requirement R4)
## تنفيذ سيناريوهات التحقق الـ 18 الإلزامية وأداة اختبارات التحمل المستمرة (Soak Testing)

- **التاريخ:** 2026-11-03
- **المهندس المنفذ:** Worker M5 (Implementer, QA, Specialist)
- **معرف جلسة المشرف:** `849edb08-8a01-463a-a4d9-889f072bccf9`
- **حالة الالتزام:** متوافق بنسبة 100% مع `AGENTS_CONSTITUTION.md`، و `GEMINI.md` (القاعدة 4 و 5)، و `ORIGINAL_REQUEST.md`.
- **الحظر الصارم:** لا مساس ولا تعديل مطلقاً بالملفات المحظورة الثلاثة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`). بيئة التطوير محلية فقط ولا رفع للسيرفر.

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Root Rationale)
تتطلب المتطلبات الهندسية في Requirement R4 من طلب المستخدم الأصلي (`ORIGINAL_REQUEST.md` و `ROOT_CAUSE_AND_PLAN_P2.md` Milestone 5):
1. **التحقق المستقل والهرمسي من سيناريوهات دورة الحياة الـ 18 الإلزامية**:
   بعد قيام المراحل M2 (ترقيم قلاع المسؤول)، M3 (تصحيح دورة حياة العمليات الحية والحالات الست وعزل الخيوط العالقة)، و M4 (تنظيف القواميس الـ 10 والأقفال وإلغاء اتصالات الويب سوكت والتخلص من استيقاظ النوم 1s)، يتوجب توفير جناح اختبارات شامل ومستقل تماماً داخل `tests/test_mandatory_scenarios.py` يثبت صحة واستقرار كافة مسارات التشغيل الطبيعية والاستثنائية:
   - **S1 (Startup)**: انتقال البوت من `starting` إلى `running` وتعيين `current_step`.
   - **S2 (Auth Credential Failure)**: فشل الاعتماد المصادق، التأكد من عدم تسريب أي خيط، وتنظيف `_castle_emails` و `_threads` وكافة الهياكل الـ 10 دون استثناء.
   - **S3 (Other Device Login)**: اكتشاف طرد الحساب بسبب تسجيل الدخول من جهاز آخر وتصنيف الحالة حصراً إلى `other_device_login`.
   - **S4 (Connection Loss)**: اكتشاف انقطاع الاتصال المفاجئ وتحديث الحالة الحية إلى `reconnecting`.
   - **S5 (Reconnecting)**: محاولات إعادة الاتصال المحدودة بعدد محدد وفترة انتظار متزايدة.
   - **S6 (Waiting for Re-login)**: انتظار إعادة تسجيل الدخول عند فقدان الجلسة وعدم القدرة على التجديد التلقائي.
   - **S7 (Waiting for Next Cycle)**: انتهاء الدورة المجدولة مع وجود طابع زمني دقيق للموعد القادم `next_run_time`.
   - **S8 (Natural Completion)**: الانتهاء الطبيعي للمهمة دون دورة تالية، والتأكد من استبعادها تماماً من جدول العمليات الحية النشطة.
   - **S9 (Manual Stop)**: إيقاف البوت يدوياً واستدعاء `_stop_and_join_bot` مع إثبات انضمام الخيط وتحرير القواميس.
   - **S10 (Stop In-Flight)**: إيقاف البوت أثناء تنفيذ مهمة نشطة وإلغاء حلقة الانتظار الفوري عبر `_async_stop_event` في زمن < 100ms.
   - **S11 (Delete Castle While Running)**: حذف القلعة أثناء عمل البوت، التحقق من الإيقاف الذري، تنظيف قاعدة البيانات، وحذف ارتباط البروكسي من `proxy_manager`.
   - **S12 (Delete User While Running)**: حذف مستخدم بكل قلاعه قيد التشغيل، إيقاف جميع الخيوط ذرياً، وحذف صفوف المستخدم والقلاع وتطهير البروكسيات.
   - **S13 (Startup Exception)**: حدوث استثناء مفاجئ أثناء مرحلة التهيئة، والتراجع النظيف دون ترك خيوط يتيمة أو تسريب أقفال.
   - **S14 (In-Flight Runtime Exception)**: حدوث استثناء أثناء تنفيذ المهمة، التقاطه بأمان، تسجيل الخطأ، وتنظيف الخيط من القواميس العامة.
   - **S15 (WebSocket Disconnect)**: قطع اتصال الويب سوكت، واكتشاف الانقطاع فوراً وإلغاء كافة المهام الخلفية المرتبطة دون تسريب Coroutines.
   - **S16 (WebSocket Reconnect)**: إعادة اتصال العميل بعد انقطاعه، وتلقي لقطة الحالة الأولية الفورية بصورة متسقة.
   - **S17 (Repeated Page Navigation / Rapid API calls)**: استدعاء متكرر وسريع لنقطة نهاية قلاع المسؤول المرقّمة دون حدوث تسريب في الذاكرة.
   - **S18 (Repeated Search & Filter with Stalled Thread Isolation)**: استدعاء التصفية والبحث في العمليات الحية مع وجود خيط متعطل، والتأكد من عزله في `_stalled_threads` وعدم حسابه في العمليات الحية.

2. **أداة اختبارات التحمل المستمرة (Continuous Multi-Cycle Soak Testing Tool)**:
   بناء السكربت المعياري `tools/soak_test_lifecycle.py` لمحاكاة العمليات التشغيلية المكثفة عبر دورات متتالية (`--cycles` الافتراضي 5، `--bots` الافتراضي 5)، وقياس:
   - الذاكرة الحقيقية الفعلية (RSS MB) عبر واجهة 64-bit Windows PSAPI (`GetProcessMemoryInfo`).
   - Private Bytes و Peak Working Set.
   - أحجام كائنات بايثون عبر `tracemalloc`.
   - عدد المقابض المفتوحة (OS Handles via `GetProcessHandleCount`).
   - عدد الخيوط النشطة (`threading.active_count()`).
   - حساب ميل انحدار خطي حقيقي ($m = \frac{\Delta \text{RSS}}{\Delta \text{cycle}}$)، والتحقق رياضياً من أن $m \le 0.05$ MB/cycle، مع إثبات انعدام أي تراكم في الخيوط ($\Delta \text{threads} = 0$).
   - تصدير تقرير شامل إلى `tools/SOAK_TEST_REPORT.md` وبيانات مهيكلة إلى `tools/soak_test_results.json`.

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Implementation Steps)

#### الخطوة 1: إعداد ملفات الحالة وتتبع المسار
- إنشاء وتحديث `BRIEFING.md` و `progress.md` في مجلد العمل `.agents/teamwork/worker_p2_m5/`.

#### الخطوة 2: بناء جناح `tests/test_mandatory_scenarios.py`
- كتابة فئة اختبارات `unittest.TestCase` باسم `TestMandatory18Scenarios` تدير بيئة هرمسية معزولة تماماً (Hermetic Isolation) عبر إنشاء قاعدة بيانات SQLite مؤقتة في الذاكرة أو ملف مؤقت، وتنظيف القواميس العامة في `api_server` في كل من `setUp` و `tearDown`.
- تضمين 18 دالة اختبار معزولة تغطي بالتفصيل السيناريوهات من S1 إلى S18 كما هو محدد بالأعلى، بالاعتماد على المنطق الحقيقي لكائنات `BotManager` و `api_server` واستدعاءات API الحقيقية، والتحقق الصارم من الشروط الحدية.

#### الخطوة 3: بناء أداة `tools/soak_test_lifecycle.py`
- الاستفادة من آليات المراقبة الدقيقة المكتوبة في `tools/measure_baseline.py` (`SystemResourceMonitor`) لضمان التوافق التام مع 64-bit Windows PSAPI.
- إنشاء آلية تنفيذ لدورات التشغيل (Life-Cycle Harness):
  - تهيئة بيانات اختبار محلية نظيفة.
  - في كل دورة: بدء عدد `--bots` من البوتات، محاكاة أداء المهام، ثم إيقافها جميعاً عبر `_stop_and_join_bot` أو مسارات API المعتمدة.
  - إطلاق `gc.collect()` وأخذ عينة القياس (RSS, Private Bytes, Tracemalloc, Handles, Threads).
  - حساب الانحدار الخطي (Linear Regression Slope) لميل نمو الذاكرة عبر الصيغة الرياضية المعيارية:
    $$m = \frac{N \sum (x_i y_i) - \sum x_i \sum y_i}{N \sum x_i^2 - (\sum x_i)^2}$$
  - التحقق من شرط $m \le 0.05$ MB/cycle و $\Delta \text{threads} == 0$.
  - كتابة النتائج بتنسيق JSON إلى `tools/soak_test_results.json`.
  - صياغة تقرير Markdown احترافي وشامل في `tools/SOAK_TEST_REPORT.md`.

#### الخطوة 4: تشغيل الاختبارات والتحقق
- تشغيل:
  1. `python tests/test_mandatory_scenarios.py` (18/18 PASS).
  2. `python tools/soak_test_lifecycle.py --cycles 5 --bots 5` (Slope <= 0.05 MB/cycle, 0 residual threads).
  3. `python tests/test_challenger_m4_stress.py` (4/4 PASS).
  4. `python tests/test_memory_cpu_m4.py` (5/5 PASS).
  5. `python tests/test_live_operations_m3.py` (4/4 PASS).
  6. `python tests/run_all_tests.py` (30/30 PASS).

#### الخطوة 5: إعداد تقرير التسليم `handoff.md` وإرسال الرسالة للمشرف
- كتابة `handoff.md` بالأقسام الخمسة الإلزامية وإرسال `send_message` إلى المشرف `849edb08-8a01-463a-a4d9-889f072bccf9`.

---

### 3. الملفات والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Files & Executions)

| الملف المستهدف | طبيعة الإجراء | النتيجة المتوقعة |
|---|---|---|
| `.agents/teamwork/worker_p2_m5/BRIEFING.md` | إنشاء | ذاكرة عمل استيعابية مستمرة متوافقة مع القالب. |
| `.agents/teamwork/worker_p2_m5/progress.md` | إنشاء وتحديث | نبض حي لتتبع خطوات الإنجاز. |
| `tests/test_mandatory_scenarios.py` | إنشاء جديد | 18 سيناريو اختباري هرمسي يغطي كافة متطلبات S1–S18 بنجاح 100%. |
| `tools/soak_test_lifecycle.py` | إنشاء جديد | أداة تشغيل دورات التحمل مع حساب الانحدار الخطي وتوثيق الذاكرة عبر PSAPI. |
| `tools/soak_test_results.json` | توليد تلقائي | قياسات المقاييس المادية والخيوط والمقابض لكل دورة بتنسيق JSON. |
| `tools/SOAK_TEST_REPORT.md` | توليد تلقائي | تقرير مفصل يثبت بالمعادلات انعدام التسريب التراكمي وتوافق المنصة. |
| `.agents/teamwork/worker_p2_m5/handoff.md` | إنشاء | تقرير التسليم النهائي المكون من الأقسام الخمسة الإلزامية. |

الأوامر المجدولة للتنفيذ:
- `python tests/test_mandatory_scenarios.py`
- `python tools/soak_test_lifecycle.py --cycles 5 --bots 5`
- `python tests/test_challenger_m4_stress.py`
- `python tests/test_memory_cpu_m4.py`
- `python tests/test_live_operations_m3.py`
- `python tests/run_all_tests.py`

كل الأوامر تعمل محلياً تماماً، ولا تتصل بأي خدمات إنتاجية أو سيرفرات خارجية.
