# تقرير الخطة الفنية المستقلة لمرحلة Milestone 5 Gen 2 (F12, F13 / Requirement R4)
## تنفيذ أداة اختبارات التحمل المستمرة (Soak Testing) والتحقق الشامل من سيناريوهات دورة الحياة الـ 18

- **التاريخ:** 2026-11-03
- **المهندس المنفذ:** Worker M5 Generation 2 (Implementer, QA, Specialist)
- **معرف جلسة المشرف:** `849edb08-8a01-463a-a4d9-889f072bccf9`
- **حالة الالتزام:** متوافق بنسبة 100% مع `AGENTS_CONSTITUTION.md`، و `GEMINI.md` (القاعدة 4 و 5)، و `ORIGINAL_REQUEST.md` (المتطلب R4)، و `ROOT_CAUSE_AND_PLAN_P2.md` (المرحلة M5).
- **الحظر الصارم:** لا مساس ولا تعديل ولا فتح مطلقاً بالملفات المحظورة الثلاثة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`). بيئة العمل محلية فقط دون أي رفع أو اتصال بسيرفر خارجي.

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Root Rationale)
تتطلب متطلبات المرحلة الخامسة (Milestone 5) وفقاً لوثيقة المتطلبات الأصلية `ORIGINAL_REQUEST.md` وخطة الإصلاح المعمارية `ROOT_CAUSE_AND_PLAN_P2.md`:
1. **التحقق الشامل والهرمسي من سيناريوهات دورة الحياة الـ 18 الإلزامية**:
   تم في الجيل الأول صياغة هيكل الاختبارات الهرمسي في `tests/test_mandatory_scenarios.py` الذي يغطي جميع الحالات من S01 إلى S18 (الـ Startup، وفشل الاعتماد والمصادقة، والدخول من جهاز آخر، وفقدان الاتصال، وإعادة المحاولات المحدودة، وانتظار تسجيل الدخول، وانتظار الدورة مع طابع زمني، والانتهاء الطبيعي، والإيقاف اليدوي، والإيقاف أثناء العمل، وحذف القلعة أثناء التشغيل، وحذف المستخدم، واستثناءات البدء والعمل، وانقطاع وعودة WebSocket، والتنقل السريع عبر الصفحات، وتكرار البحث والتصفية مع عزل الخيوط العالقة).
   يتوجب تشغيل هذا الجناح والتحقق من نجاح كافة السيناريوهات الـ 18 بنسبة 100% (18/18 PASS).

2. **بناء أداة اختبارات التحمل المستمرة (Continuous Multi-Cycle Soak Testing Tool)**:
   بناء سكربت هندسي متكامل ومستقل `tools/soak_test_lifecycle.py` يقيس بدقة وسلوك حقيقي (Non-dummy, Non-mocked) استهلاك الموارد عبر دورات تشغيل متعددة (افتراضياً 5 دورات مع 5 بوتات لكل دورة):
   - استخدام واجهات 64-bit Windows PSAPI الأصلية (`GetProcessMemoryInfo`) لقياس RSS الفعلي، و Private Bytes، و Peak Working Set.
   - استخدام `GetProcessHandleCount` لرصد مقابض نظام التشغيل OS Handles.
   - قياس تخصيص كائنات بايثون عبر `tracemalloc`.
   - قياس عدد الخيوط النشطة (`threading.active_count()`).
   - تنفيذ حقيقي لدورات: بدء البوتات، تنفيذ العمليات، ثم إيقافها وتنظيفها بالكامل عبر `_stop_and_join_bot` أو مسارات API المعتمدة.
   - حساب الميل الرياضي للانحدار الخطي (Linear Regression Slope $m$) لنمو الذاكرة باستخدام طريقة المربعات الصغرى القياسية:
     $$m = \frac{N \sum (x_i y_i) - \sum x_i \sum y_i}{N \sum x_i^2 - (\sum x_i)^2}$$
   - التحقق الصارم من أن ميل نمو الذاكرة $m \le 0.05$ MB/cycle، وأن صافي الزيادة في الخيوط بعد نهاية الدورات يساوي صفراً ($\Delta \text{threads} = 0$).
   - تصدير تقرير بصيغة Markdown إلى `tools/SOAK_TEST_REPORT.md` وبيانات مهيكلة بصيغة JSON إلى `tools/soak_test_results.json`.

3. **التثبت من عدم وجود أي تراجع (Regression Testing)**:
   تشغيل كافة أجنحة الاختبارات الأخرى للتحقق من تكامل النظام:
   - `tests/test_challenger_m4_stress.py` (4/4 PASS).
   - `tests/test_memory_cpu_m4.py` (5/5 PASS).
   - `tests/test_live_operations_m3.py` (4/4 PASS).
   - `tests/run_all_tests.py` (30/30 PASS).

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Implementation Steps)

#### الخطوة 1: بناء أداة `tools/soak_test_lifecycle.py`
- استيراد وتوظيف محرك القياس الدقيق `SystemResourceMonitor` من `tools/measure_baseline.py` لدعم القياس عبر 64-bit Windows PSAPI و `Kernel32`.
- بناء فئة `SoakTestLifecycleRunner`:
  - إعداد بيئة معزولة مؤقتة لقاعدة البيانات SQLite وتنظيف هياكل `api_server` قبل البدء.
  - قياس نقطة البداية (Baseline Snapshot) للذاكرة (RSS, Private Bytes, Tracemalloc)، والمقابض (Handles)، والخيوط (Active Threads).
  - حلقة تشغيل عبر `--cycles`:
    - تشغيل `--bots` بوتات بالتزامن عبر `api_server.start_bot` أو خيوط دورة حياة تحاكي العمليات الحية الفعلية.
    - انتظار فترة زمنية ومحاكاة معالجة المهام.
    - إيقاف جميع البوتات عبر `api_server._stop_and_join_bot` وانتظار انضمام الخيوط بالكامل (Deterministic Join).
    - استدعاء `gc.collect()` وأخذ عينة القياسات الدقيقة بنهاية الدورة.
    - تسجيل القياسات (RSS, Private Bytes, Handles, Tracemalloc, Threads).
  - حساب الميل الرياضي لانحدار الذاكرة $m$ والانحدار للخيوط والمقابض.
  - التحقق من شروط النجاح: $m \le 0.05$ MB/cycle و $\Delta \text{threads} == 0$.
  - تصدير `tools/soak_test_results.json` و `tools/SOAK_TEST_REPORT.md`.

#### الخطوة 2: تنفيذ حزمة الاختبارات الشاملة والتحقق المستقل
1. تشغيل `python tests/test_mandatory_scenarios.py` للتحقق من اجتياز السيناريوهات الـ 18 بنجاح.
2. تشغيل `python tools/soak_test_lifecycle.py --cycles 5 --bots 5` والتحقق من حساب الميل الحقيقي وانعدام أي تسريب.
3. تشغيل `python tests/test_challenger_m4_stress.py`.
4. تشغيل `python tests/test_memory_cpu_m4.py`.
5. تشغيل `python tests/test_live_operations_m3.py`.
6. تشغيل `python tests/run_all_tests.py` (جناح الاختبارات المتعدد الـ 30 اختباراً).

#### الخطوة 3: التوثيق وإعداد تقرير التسليم `handoff.md`
- تحديث `BRIEFING.md` و `progress.md`.
- كتابة `handoff.md` المكون من الأقسام الخمسة المعيارية (Observation, Logic Chain, Caveats, Conclusion, Verification Method).
- إرسال رسالة الإنجاز إلى المشرف عبر `send_message`.

---

### 3. الملفات والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Files & Executions)

| الملف المستهدف | طبيعة الإجراء | النتيجة المتوقعة |
|---|---|---|
| `tools/soak_test_lifecycle.py` | إنشاء جديد | أداة تشغيل دورات التحمل مع قياسات PSAPI وحساب ميل الانحدار الخطي للذاكرة |
| `tools/soak_test_results.json` | توليد تلقائي | ملف JSON يحتوي تفاصيل قياسات الذاكرة والمقابض والخيوط لكل دورة تشغيل |
| `tools/SOAK_TEST_REPORT.md` | توليد تلقائي | تقرير تفصيلي يوضح ميل الانحدار واستقرار الموارد وصفرية الخيوط المتبقية |
| `.agents/teamwork/worker_p2_m5_gen2/handoff.md` | إنشاء | تقرير التسليم الشامل وفق بروتوكول Handoff المعتمد |

الأوامر المجدولة للتنفيذ:
1. `python tests/test_mandatory_scenarios.py` (المتوقع: 18/18 PASS)
2. `python tools/soak_test_lifecycle.py --cycles 5 --bots 5` (المتوقع: PASS مع ميل <= 0.05 MB/cycle وخيوط متبقية = 0)
3. `python tests/test_challenger_m4_stress.py` (المتوقع: 4/4 PASS)
4. `python tests/test_memory_cpu_m4.py` (المتوقع: 5/5 PASS)
5. `python tests/test_live_operations_m3.py` (المتوقع: 4/4 PASS)
6. `python tests/run_all_tests.py` (المتوقع: 30/30 PASS)

جميع العمليات والأوامر تتم محلياً 100% ودون المساس بالملفات المحظورة قطيعاً.
