# Technical Report Artifact: Pre-Verification & Command Execution Plan
**Author:** Reviewer 2 (`reviewer_p2_m6_2`)  
**Date:** 2026-11-03T20:36:00Z  
**Governing Rule:** GEMINI.md Rule 5 (Strict File-Report-First Rule)  
**Target Milestone:** Milestone 6 (Final Certification & Adversarial Audit)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
كجزء من تدقيق الجودة والتحقق العدائي (Quality & Adversarial Review) للمرحلة النهائية M6، يُطلب من المراجع المستقل التحقق العملي والمستقل من صحة نتائج الاختبارات والادعاءات الواردة في تقرير العامل `worker_p2_m6/handoff.md` والتقرير النهائي `FINAL_PLATFORM_OVERHAUL_REPORT.md`.
وفقاً لمبادئ التحقق الصارم ومكافحة الانتهاكات النزاهية (Integrity Violations)، لا يمكن اعتماد أي ادعاء نظري أو مخرجات سابقة دون إعادة تشغيل حزم الاختبارات فعلياً في البيئة المحلية ومطابقة النتائج مع عتبات القبول المقررة.
كما يلزم التحقق من سلامة الملفات المحظورة الثلاثة (`game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`) والتأكد من عدم لمسها أو تعديلها بأي شكل من الأشكال، مع الامتثال الصارم لبيئة العمل المحلية فقط دون أي رفع للسيرفر.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Execution Steps)
1. **التحقق من حالة المستودع والملفات المحظورة**:
   - تنفيذ أمر `git status --porcelain` لفحص الملفات المعدلة في المستودع دون فتح أو لمس الملفات المحظورة.
   - التأكد التام من خلو التغييرات من أي تعديل على الملفات المحظورة.
2. **تنفيذ حزمة الاختبارات الشاملة (Master Test Suite)**:
   - تشغيل `python tests/run_all_tests.py` للتحقق من اجتياز كافة الطبقات الأربع (30 اختباراً).
3. **تنفيذ حزمة السيناريوهات الإلزامية (Mandatory Scenarios)**:
   - تشغيل `python tests/test_mandatory_scenarios.py` للتحقق من اجتياز السيناريوهات الـ 18 الإلزامية بالكامل.
4. **تنفيذ حزم الإجهاد والموارد والعمليات الحية**:
   - تشغيل `python tests/test_challenger_m4_stress.py` (4 اختبارات إجهاد).
   - تشغيل `python tests/test_memory_cpu_m4.py` (5 اختبارات ذاكرة ومعالج).
   - تشغيل `python tests/test_live_operations_m3.py` (4 اختبارات دورة حياة العمليات الحية).
5. **فحص ومراجعة الكود لاكتشاف أي ثغرات أو تحايل (Integrity Check & Adversarial Stress Testing)**:
   - فحص كود الاختبارات للتأكد من عدم وجود قيم متوقعة مفبركة أو Hardcoded facades.
   - فحص تنفيذات الـ Pagination والـ State Machine والـ Dictionary Cleanup لضمان متانتها البرمجية.

---

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)

| # | الأمر (Command) | الهدف | النتيجة المتوقعة (Expected Output) |
|---|---|---|---|
| 1 | `git status --porcelain` | التحقق من عدم لمس الملفات المحظورة وحالة المستودع | قائمة بالملفات المعدلة مع خلوها تماماً من `game_client.py` و `core/onemt_auth.py` و `core/onemt_bot.py` |
| 2 | `python tests/run_all_tests.py` | تشغيل حزمة الاختبارات الشاملة (4 طبقات) | `30 Total \| 30 Pass \| 0 Fail \| Pass: 100.0%` وخروج بكود 0 |
| 3 | `python tests/test_mandatory_scenarios.py` | تشغيل السيناريوهات الـ 18 الإلزامية | `Ran 18 tests ... OK` |
| 4 | `python tests/test_challenger_m4_stress.py` | تشغيل اختبارات الإجهاد والتوقف المتزامن | `Ran 4 tests ... OK` |
| 5 | `python tests/test_memory_cpu_m4.py` | تشغيل اختبارات الموارد وتسريبات الذاكرة | `Ran 5 tests ... OK` |
| 6 | `python tests/test_live_operations_m3.py` | تشغيل اختبارات دورة حياة العمليات الحية | `Ran 4 tests ... OK` |
| 7 | `python tools/soak_test_lifecycle.py --cycles 3 --bots 3` | تشغيل عينة اختبار استقرار وتحقق متعدد الدورات | انحدار الذاكرة $m \le 0.05$ MB/cycle وخروج بكود 0 (PASSED) |

---
**الالتزام:** لن يتم تنفيذ أي أمر خارج هذا النطاق، والعمل محلي حصراً بنسبة 100%.
