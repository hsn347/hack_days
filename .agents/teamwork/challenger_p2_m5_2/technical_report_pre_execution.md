# تقرير فني مسبق لإجراءات الفحص والتحقق التجريبي (Pre-Execution Technical Report)
═══════════════════════════════════════════════════════════════════════════════
Milestone 5 (F12, F13 / Requirement R4): Empirical Soak Stress Testing & Suite Verification
المطابقة التامة للقاعدة رقم 5 في `GEMINI.md` ووثيقة `AGENTS_CONSTITUTION.md`
═══════════════════════════════════════════════════════════════════════════════

- **التاريخ:** 2026-11-03
- **المنفذ:** Challenger 2 (`teamwork_challenger`) — Critic & Specialist
- **مسار العمل:** `e:\osmanli\.agents\teamwork\challenger_p2_m5_2\`
- **مرجع المهمة الأساسي:** `ORIGINAL_REQUEST.md` (Requirement R4)
- **تسليم العامل:** `worker_p2_m5_gen2/handoff.md`

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

تتطلب المرحلة الخامسة (Milestone 5) وفقاً لوثيقة المتطلبات `ORIGINAL_REQUEST.md` (Requirement R4) التحقق التجريبي المستقل والصارم من:
1. **استقرار الذاكرة والموارد في الاختبارات طويلة الأمد (Continuous Multi-Cycle Soak Testing)**:
   تشغيل أداة الفحص `tools/soak_test_lifecycle.py` تحت ظروف إجهاد أعلى من فحص العامل (6 دورات متتالية مع 6 بوتات متزامنة لكل دورة بدلاً من 5x5)، والتحقق رياضياً وجنائياً من:
   - ميل انحدار الذاكرة المادية (RSS Memory Regression Slope): $m \le 0.05$ MB/cycle.
   - التغير النهائي في خيوط التنفيذ (Final Thread Delta): $\Delta\text{threads} == 0$.
   - تسريب هياكل البيانات العامة (Dictionary Leaks across 10 structures): $0$ تسريب.
   - بقاء مقابض نظام التشغيل (OS Handles) ضمن نطاق محدد ومستقر دون تراكم تصاعدي.
2. **سلامة حزمة الاختبارات الشاملة الموحدة (Unified 4-Tier Test Suite)**:
   تشغيل `tests/run_all_tests.py` والتأكد من اجتياز كافة الاختبارات الثلاثين (30/30 PASS بنسبة 100%).
3. **سلامة السيناريوهات الإلزامية الـ 18 (18 Mandatory Lifecycle Scenarios)**:
   تشغيل `tests/test_mandatory_scenarios.py` للتحقق المستقل من تغطية السيناريوهات S01 إلى S18 هرمسياً.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Execution Workflow)

1. **الخطوة الأولى — اختبار الإجهاد التراكمي (Adversarial Soak Profiling)**:
   - تنفيذ `python tools/soak_test_lifecycle.py --cycles 6 --bots 6`.
   - قياس خط الأساس، ثم تشغيل 6 بوتات متزامنة عبر دورات دورية متتابعة، وإطلاق سجلات ومحاكاة مهام حقيقية.
   - التحقق من آلية الإيقاف الحتمي المنظم `_stop_and_join_bot` بمهلة محددة.
   - جمع قياسات PSAPI المادية (RSS, Private Bytes, Peak WS, Handles, Tracemalloc, Threads, Dictionary Audit).
   - حساب الانحدار الخطي $m$ و $R^2$ ومقارنتها بالحد الحرج $0.05$ MB/cycle.

2. **الخطوة الثانية — فحص حزمة الاختبارات الموحدة (Unified 4-Tier Test Runner)**:
   - تنفيذ `python tests/run_all_tests.py`.
   - فحص نتائج المستويات الأربعة (Tier 1 Feature Coverage, Tier 1 DB Queries, Tier 2 Boundary/Stress, Tier 3 Cross-Feature Concurrency, Tier 4 Real-World Workflows).
   - التأكد من عدم وجود أي Failures أو Errors (30/30 PASS).

3. **الخطوة الثالثة — فحص السيناريوهات الـ 18 الإلزامية (18 Mandatory Scenarios)**:
   - تنفيذ `python tests/test_mandatory_scenarios.py`.
   - التأكد من اجتياز كافة الحالات الـ 18 هرمسياً بنجاح 100%.

4. **الخطوة الرابعة — الفحص الجنائي وصياغة التقرير والقرار (Handoff & Verdict)**:
   - استخراج وتوثيق الأرقام القياسية بدقة، وصياغة تقرير التسليم النهائي `handoff.md`.
   - إرسال الإشعار النهائي للمشرف بالقرار (APPROVE).

---

## 3. الأوامر والملفات والنتائج المتوقعة بالتفصيل (Commands & Expected Results)

| الرقم | الأمر المراد تنفيذه (Command) | الملفات المتأثرة / المستهدفة | النتيجة المتوقعة (Expected Output) |
|---|---|---|---|
| 1 | `python tools/soak_test_lifecycle.py --cycles 6 --bots 6` | `tools/soak_test_lifecycle.py`, `tools/soak_test_results.json`, `tools/SOAK_TEST_REPORT.md` | إتمام 6 دورات بـ 6 بوتات، $m \le 0.05$ MB/cycle، $\Delta\text{threads} == 0$، تسريبات قواميس $= 0$، `OVERALL SOAK VERDICT: >>> PASSED <<<`، كود الخروج `0`. |
| 2 | `python tests/run_all_tests.py` | `tests/run_all_tests.py`, `tests/test_e2e_platform.py`, `tests/test_database_performance.py` | تنفيذ 30 حالة اختبار، 30 PASS، 0 FAIL، كود الخروج `0`. |
| 3 | `python tests/test_mandatory_scenarios.py` | `tests/test_mandatory_scenarios.py` | تنفيذ 18 اختباراً للسيناريوهات الإلزامية، 18/18 PASS، كود الخروج `0`. |

---

## 4. القيود والمحاذير (Safety & Compliance Constraints)
- ممنوع منعاً باتاً فتح أو قراءة أو تعديل أو لمس الملفات الثلاثة المحظورة: `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`.
- الالتزام التام بالبيئة المحلية (Hermetic SQLite In-Memory / Temp DB) وعدم الاتصال بأي خادم أو قاعدة بيانات إنتاجية.
