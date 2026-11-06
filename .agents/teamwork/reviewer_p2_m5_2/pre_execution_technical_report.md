# تقرير فني مسبق للمراجعة والتحقق الجنائي (Pre-Execution Technical Report)
═══════════════════════════════════════════════════════════════════════════════
Milestone 5 (F12, F13 / Requirement R4) — Reviewer 2 Independent Verification
═══════════════════════════════════════════════════════════════════════════════

- **التاريخ:** 2026-11-03
- **الدور:** Reviewer 2 & Adversarial Critic
- **المهمة:** التحقق المستقل الجنائي من أدوات الفحص المستمر طويل الأمد (Soak Test) وحزمة الاختبارات الإلزامية الـ 18 وفق المتطلب R4 من ORIGINAL_REQUEST.md.
- **البيئة:** بيئة محلية هرمسية معزولة تماماً (Local Isolated Environment - Zero Production / Zero Server / Prohibited Files Untouched).

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

وفقاً لتعليمات التكليف (Dispatch) والوثيقة المرجعية `ORIGINAL_REQUEST.md` (المتطلب R4):
1. يتطلب استكمال المرحلة الخامسة M5 التحقق الجنائي المستقل من:
   - أداة الفحص المستمر `tools/soak_test_lifecycle.py` وصحة صيغة الانحدار الخطي العادي (Ordinary Least Squares - OLS).
   - استدعاءات واجهات ويندوز 64-bit PSAPI ومقابض النظام `GetProcessHandleCount` وسلامة مؤشرات الذاكرة.
   - التحقق من معيار ميل نمو الذاكرة $m \le 0.05$ MB/cycle وانعدام الخيوط المتسربة ($\Delta\text{threads} = 0$) وانعدام تسريبات القواميس العامة العشرة.
2. تشغيل سيناريوهات الاختبار المستقلة لضمان عدم وجود تزييف أو نتائج وهمية أو كود زائف (Anti-Cheat & Anti-Facade Review).
3. تشغيل الحزمة الموحدة `tests/run_all_tests.py` للتأكد من نجاح الـ 30 اختباراً بنسبة 100% دون أي تراجع (Zero Regression).

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)

1. **الخطوة الأولى: مراجعة الكود البرمجي والصيغ الرياضية (Static Code & Math Audit)**:
   - فحص دالة `compute_linear_regression(x_vals, y_vals)` والتأكد من مطابقتها الدقيقة لصيغة OLS:
     $$m = \frac{n \sum xy - \sum x \sum y}{n \sum x^2 - (\sum x)^2}, \quad b = \frac{\sum y - m \sum x}{n}, \quad R^2 = 1 - \frac{SS_{res}}{SS_{tot}}$$
   - فحص هياكل ctypes الخاصة بـ Windows 64-bit (`PROCESS_MEMORY_COUNTERS_EX`) والتأكد من استخدام `c_size_t` للحقول 64-بت، واستخدام `c_void_p` لمقابض العمليات لمنع قطع العناوين (Handle truncation).
   - التحقق من آلية تنظيف القواميس العشرة بعد انتهاء كل دورة.

2. **الخطوة الثانية: تنفيذ اختبارات التحقق المستقلة (Execution & Dynamic Verification)**:
   - تنفيذ أمر فحص دورة الحياة الممتد:
     `python tools/soak_test_lifecycle.py --cycles 5 --bots 5`
   - فحص ملف النتائج الهيكلي `tools/soak_test_results.json` وتقرير الـ Markdown الناتج `tools/SOAK_TEST_REPORT.md`.
   - تنفيذ حزمة الاختبارات الشاملة:
     `python tests/run_all_tests.py`
   - تنفيذ حزمة سيناريوهات الـ 18 الإلزامية:
     `python tests/test_mandatory_scenarios.py`

3. **الخطوة الثالثة: التحليل المعادي وفحص النزاهة (Adversarial Review & Integrity Audit)**:
   - التحقق من عدم وجود قيم نجاح مشفرة ثابتاً (Hardcoded values).
   - اختبار حالات الحافة (Edge cases) مثل القسمة على الصفر في OLS، وفشل الانضمام في حال التأخر، ومحاكاة التسريب.

4. **الخطوة الرابعة: توثيق النتائج وإصدار القرار (Final Verdict & Handoff)**:
   - كتابة تقرير التسليم `handoff.md` وفق النموذج الخماسي وإرسال إشعار للمنسق عبر `send_message`.

---

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)

1. **الأمر الأول: فحص دورة الحياة المستمر (Multi-Cycle Soak Test)**:
   - **الأمر:** `python tools/soak_test_lifecycle.py --cycles 5 --bots 5`
   - **المدخلات:** 5 دورات متتالية، 5 بوتات متزامنة لكل دورة، قاعدة بيانات SQLite مؤقتة ومعزولة.
   - **النتيجة المتوقعة:**
     - انضمام حتمي لجميع البوتات خلال كل دورة.
     - ميل نمو الذاكرة $m \le 0.05$ MB/cycle.
     - فرق الخيوط النهائي $\Delta\text{threads} = 0$.
     - تسريب القواميس العشرة $= 0$.
     - انتهاء الأمر بنجاح (Exit code 0) وظهور `OVERALL SOAK VERDICT: >>> PASSED <<<`.
     - تحديث الملفين `tools/soak_test_results.json` و `tools/SOAK_TEST_REPORT.md`.

2. **الأمر الثاني: تشغيل حزمة الـ 18 سيناريو الإلزامي**:
   - **الأمر:** `python tests/test_mandatory_scenarios.py`
   - **النتيجة المتوقعة:** اجتياز 18 من أصل 18 اختباراً بنجاح (OK) دون أي فشل أو خطأ.

3. **الأمر الثالث: تشغيل حزمة الاختبارات الموحدة للطبقات الأربع (Unified 4-Tier Test Runner)**:
   - **الأمر:** `python tests/run_all_tests.py`
   - **النتيجة المتوقعة:** 30/30 اختباراً بنجاح (100.0% Pass Rate) وزمن تنفيذ إجمالي أقل من 10 ثوانٍ.

4. **الالتزام بالقيود الصارمة**:
   - عدم فتح أو قراءة أو تعديل أو لمس الملفات المحظورة الثلاثة: `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`.
   - عدم تشغيل أي أوامر شبكية أو رفع أو نشر خارجي.
