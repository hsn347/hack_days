# تقرير فني مسبق لخطة التحقق والتشغيل التجريبي — تشالنجر (Milestone M6 Certification Challenge)

**تاريخ التقرير**: 2026-11-03  
**الوكيل**: Challenger 1 (`teamwork_challenger`)  
**المهمة**: التحقق التجريبي المستقل (Empirical Verification & Stress Challenge) لمخرجات وادعاءات العامل (Worker M6) وتقرير `FINAL_PLATFORM_OVERHAUL_REPORT.md`.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Purpose)

قدّم العامل في تقريره النهائي `FINAL_PLATFORM_OVERHAUL_REPORT.md` وفي `worker_p2_m6/handoff.md` ادعاءات بنجاح 100% لجميع حزم الاختبارات:
- حزمة الاختبارات الرئيسية (30/30)
- السيناريوهات الإلزامية الـ 18 (18/18)
- اختبارات الإجهاد (4/4)
- قياسات الذاكرة والمعالج (5/5)
- دورة حياة العمليات الحية (4/4)
- اجتياز اختبار الـ Soak Testing متعدد الدورات بمعدل انحدار ذاكرة $m = +0.0034$ MB/cycle وبدون أي تسريبات للـ Threads أو القواميس العامة.
- عدم لمس الملفات المحظورة الثلاثة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`).

بصفتنا فاحصاً تجريبياً ومراجعاً معادياً (Empirical Challenger & Critic)، تقتضي المبادئ الصارمة عدم الوثوق بادعاءات أو سجلات العامل، وإجراء التحقق المباشر وتشغيل الأكواد وسكربتات الاختبار بأنفسنا في بيئة العمل المحلية، واستخراج الأدلة التجريبية وفحص متانة المنصة وعدم وجود حالات إخفاق مستترة أو نتائج خادعة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic Chain & Execution Strategy)

1. **التحقق من عدم لمس الملفات المحظورة**:
   - التحقق من حالة git للملفات الثلاثة والتأكد من عدم وجود أي تعديل عليها دون فتحها أو لمس محتواها.
2. **التنفيذ المتسلسل لحزم الاختبارات الإلزامية**:
   - تشغيل `python tests/run_all_tests.py` ومقارنة عدد الاختبارات وزمن التنفيذ ومعدل النجاح (المتوقع 30/30).
   - تشغيل `python tests/test_mandatory_scenarios.py` والتأكد من اجتياز السيناريوهات الـ 18 بدون أخطاء أو تخطي غير مبرر.
   - تشغيل `python tests/test_challenger_m4_stress.py` للتحقق من إجهاد الإيقاف المتزامن لـ 20 بوتاً وعزل الـ Threads المتعثرة.
   - تشغيل `python tests/test_memory_cpu_m4.py` للتحقق من الانتظار المعتمد على الأحداث وتنظيف القواميس العشرة.
   - تشغيل `python tests/test_live_operations_m3.py` للتحقق من الحالات الست وحظر التكرار وترقيم الصفحات.
3. **إعادة تشغيل Soak Test للتحقق من التكرارية (Reproducibility)**:
   - تشغيل `python tools/soak_test_lifecycle.py --cycles 3 --bots 3` للتأكد المستقل من أن ميل نمو الذاكرة $m \le 0.05$ MB/cycle مع انعدام تسريبات الـ Threads والقواميس.
4. **الفحص المعادي والتأكد من صحة التوكيدات (Adversarial Assertion Auditing)**:
   - مراجعة منطق الاختبارات والتحقق من أنها لا تحتوي على توكيدات وهمية (tautological assertions) أو تجاوزات تخفي أعطالاً حقيقية.
5. **إصدار القرار النهائي (Final Verdict)**:
   - كتابة `handoff.md` المتضمن الأدلة التجريبية والقرار (APPROVE أو REQUEST_CHANGES).

---

## 3. الملفات والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Output)

| الخطوة | الأمر المخطط تنفيذه | الغرض والملف المستهدف | النتيجة المتوقعة |
|---|---|---|---|
| **C1** | `python tests/run_all_tests.py` | تشغيل حزمة الاختبارات الشاملة المكونة من 4 طبقات | 30 Total \| 30 Pass \| 0 Fail \| 100.0% |
| **C2** | `python tests/test_mandatory_scenarios.py` | تشغيل السيناريوهات الإلزامية الـ 18 | Ran 18 tests ... OK |
| **C3** | `python tests/test_challenger_m4_stress.py` | اختبار إيقاف 20 بوتاً متزامناً وتنظيف الموارد | Ran 4 tests ... OK |
| **C4** | `python tests/test_memory_cpu_m4.py` | اختبار الذاكرة والمعالج والقواميس العامة | Ran 5 tests ... OK |
| **C5** | `python tests/test_live_operations_m3.py` | اختبار دورة حياة العمليات الحية والحالات الست | Ran 4 tests ... OK |
| **C6** | `python tools/soak_test_lifecycle.py --cycles 3 --bots 3` | اختبار التحمل التكراري المستقل | ميل الانحدار $\le 0.05$ MB/cycle و PASS |
| **C7** | `git status --porcelain game_client.py core/onemt_auth.py core/onemt_bot.py` | التحقق من عدم المساس بالملفات المحظورة قط | لا مخرجات (الملفات غير معدلة) |

---
*تم إنشاء هذا التقرير الفني المسبق التزاماً بالقاعدة رقم 5 من GEMINI.md قبل تشغيل أي أمر.*


---

## 4. تقرير إلحاقي: فحص تاريخ git للملفات المحظورة (Git History & Status Audit)

**التشخيص**: أظهر استعلام `git status --porcelain` وجود `M game_client.py` و `?? core/onemt_auth.py` و `?? core/onemt_bot.py`. مطلوب فحص تاريخ التعديل في git لمعرفة هل تم التعديل خلال هذه المرحلة (M6) أم أنه موجود مسبقاً قبل بدء مراحل فريق العمل الحالية، دون فتح الملفات المحظورة مطلقاً.

**الأمر المخطط**: `git log -n 5 --oneline` و `git diff --stat HEAD -- game_client.py`
**النتيجة المتوقعة**: معرفة توقيت التعديل وما إذا كانت ملفات untracked منذ إنشاء المستودع.


---

## 5. تقرير إلحاقي: فحص تطابق بصمات SHA256 للملفات المحظورة (SHA256 Baseline Integrity Verification)

**التشخيص**: للتأكد القاطع من عدم تعديل أو مساس أي ملف من الملفات المحظورة الثلاثة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`) مقارنة بخط الأساس المعتمد والموثق في المرحلة السابقة (`auditor_p2_m5`).

**الأمر المخطط**:
`Get-FileHash game_client.py, core/onemt_auth.py, core/onemt_bot.py`

**البصمات المرجعية المعتمدة**:
- `game_client.py`: `9D23C17526BFDE21011EFAC9A89D4BA7880F812325F02B5557C9DD675C0A5236`
- `core/onemt_auth.py`: `750D15E6A9F2F8B931D3B226487AB8D7FFC7F08312381035CC60F17D7DEC63A5`
- `core/onemt_bot.py`: `79EBD39BDC1D201E8A62A593C4A06BA0356B0B81FD8FECDD356FD143567153F9`

**النتيجة المتوقعة**: تطابق تام 100% لجميع البصمات، مما يثبت أن حالة git لا تعود إلى أي تعديل حديث بواسطة العامل.
