# تقرير فني مستقل لخطة فحص وتدقيق النزاهة الجنائية (Milestone 2 Forensic Audit Plan)

**المشروع:** Platform Performance & Data Management Overhaul (`e:\osmanli`)  
**المرحلة:** Milestone 2 (M2) — Concurrency Safety & Security Hardening  
**المدقق:** Forensic Auditor M2  
**التاريخ:** 2026-11-02  
**المرجع القانوني والتنظيمي:** `e:\osmanli\GEMINI.md` (البند 5: إلزامية التقرير الفني المسبق قبل تنفيذ أي أمر) و `e:\osmanli\AGENTS_CONSTITUTION.md`

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostic Rationale)

تتطلب معايير النزاهة الصارمة لدور Forensic Auditor التحقق التجريبي المستقل (Empirical Verification) من مخرجات Milestone 2.
الهدف هو التأكد من:
1. خلو كود `core/database.py` و `api_server.py` من أي واجهات وهمية (Facades)، أو مخرجات مشفرة مسبقاً (Hardcoded outputs)، أو تجاوزات أمنية وهمية (Mock bypasses).
2. فحص سلامة أجنحة الاختبار في `tools/verify_m2_security.py` و `tests/run_all_tests.py` والتأكد من أنها تنفذ اختبارات حقيقية وصارمة على قاعدة بيانات SQLite معزولة وعميل FastAPI TestClient حقيقي.
3. تشغيل أوامر الفحص والاختبار في البيئة المحلية للحصول على مخرجات الأدوات الأولية (Raw Tool Output) كدليل إثبات قاطع.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Audit Methodology & Steps)

1. **التحقق من حالة المستودع وتغييرات Git:**
   - تنفيذ `git diff` و `git status` لمراجعة الأسطر التي تم تعديلها فعلياً في M2 والتأكد من عدم وجود تعديلات مشبوهة أو ملفات مخفية تتجاوز الفحص.
2. **التنفيذ التجريبي المستقل لاختبارات M2:**
   - تشغيل `python tools/verify_m2_security.py` لملاحظة استجابة جميع الاختبارات الـ 14 وتأكيد نجاحها الفعلي.
3. **التنفيذ التجريبي لحزمة اختبارات المشروع الشاملة:**
   - تشغيل `python tests/run_all_tests.py` للتأكد من عدم حدوث أي انحدار (Zero Regression) في وظائف المنصة.
4. **تحليل النزاهة وفق مستويات الضبط (Integrity Enforcement):**
   - مطابقة النتائج مع نمط `Development Mode` المحدد في `ORIGINAL_REQUEST.md` (وكذلك التأكد من معايير Demo/Benchmark mode).
5. **صياغة التقرير الجنائي النهائي وحكم النزاهة (`CLEAN` أو `INTEGRITY VIOLATION`).**

---

## 3. الأوامر المستهدفة والنتائج المتوقعة (Commands to Execute & Expected Results)

| # | الأمر المزمع تنفيذه | الغرض والملفات المستهدفة | النتيجة المتوقعة |
|---|---|---|---|
| 1 | `git diff --stat` و `git status` | فحص قائمة الملفات المعدلة في المستودع المحلي | حصر التعديلات في `core/database.py` و `api_server.py` والملفات المرتبطة |
| 2 | `python tools/verify_m2_security.py` | تشغيل الـ 14 فحصاً أمنياً وتزامنياً ضد TestClient وSQLite المعزولة | `Ran 14 tests ... OK` دون أي فشل أو أخطاء |
| 3 | `python tests/run_all_tests.py` | تشغيل كامل سويت اختبارات المشروع (30 اختباراً) | نجاح 100% لجميع الاختبارات (30/30 passed) |

---
*تم إنشاء هذا التقرير التزاماً بالبند 5 من GEMINI.md قبل تشغيل أي أوامر في سطر الأوامر.*
