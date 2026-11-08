# Forensic Integrity Audit Pre-Execution Technical Report
**Target**: `docs/reports/adversarial_march_audit.md` & Project Clean Status
**Auditor**: Forensic Integrity Auditor (`.agents/teamwork/auditor/`)
**Date**: 2026-11-08

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
تم تكليف المدقق الجنائي بإجراء فحص جنائي شامل ومستقل لمخرجات تدقيق المسيرات (March Tasks) والتأكد من:
1. عدم المساس بأي كود مصدري في المشروع (خاصة `tasks/*.py`) وضمان بقاء ملفات المشروع البرمجية نظيفة دون أي تعديل uncommitted أو غير مصرح به.
2. التحقق من اكتمال تقرير التدقيق الرئيسي `docs/reports/adversarial_march_audit.md` وخلوه التام من عبارات الاختصار المحظورة ("إلخ"، "بنفس الطريقة للملفات الأخرى"، "باختصار") أو الواجهات الوهمية (Facades).
3. تشغيل سكريبت التحقق البرمجي التلقائي `verify_report.py` وفحص مخرجاته.
4. إجراء فحص جنائي مستقل وتفصيلي بالبايثون للمتطلبات العشرة لملفات المهام، وأكواد الأخطاء العشرين، وأولويات المنسق العشر، وأسباب الإيقاف الخمسة، وحل تعارضات أسئلة الهيبة، والمخطط المعماري الموحد لـ `BaseTask`.

تنفيذاً للقاعدة رقم 5 في `GEMINI.md`، يجب توثيق هذا التقرير المستقل قبل تنفيذ أي أمر طرفية أو فحص في بيئة العمل.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Action Plan)

### المرحلة الأولى: فحص سلامة المستودع والكود المصدري (Git Status & Source Integrity)
- تنفيذ أمر `git status --porcelain` لفحص حالة شجرة العمل والتأكد من عدم وجود أي تعديل في `tasks/*.py` أو ملفات الكود الحيوية.
- فحص تواريخ تعديل الملفات والتحقق من عدم حدوث تلاعب أو توليد ملفات وهمية في `tasks/`.

### المرحلة الثانية: تشغيل سكريبت التحقق الآلي (Automated Script Execution)
- تنفيذ الأمر:
  `python .agents/teamwork/report_assembler/verify_report.py`
- التقاط المخرج والتحقق من النتيجة `100% CLEAN PASS`.

### المرحلة الثالثة: الفحص الجنائي المستقل الصارم (Independent Forensic Verification)
- كتابة وتشغيل سكريبت فحص جنائي مستقل خاص بالمدقق الجنائي `independent_forensic_check.py` للتحقق من:
  1. حجم الملف الفعلي، عدد الأسطر، وعدد الكلمات.
  2. البحث الدقيق عن العبارات المحظورة: "إلخ", "بنفس الطريقة للملفات الأخرى", "باختصار" وأي أشكال مشتقة منها.
  3. فحص الـ 10 ملفات مع التأكد من وجود تحليل تفصيلي حقيقي لكل ملف وليس مجرد ذكر للاسم.
  4. فحص الـ 20 كود خطأ والتأكد من ارتباطها بالبروتوكول واستجابات السيرفر.
  5. فحص الـ 10 أولويات لمنسق المسيرات وجدول الأولويات وتفاصيل تضارب المهام.
  6. فحص أسباب الإيقاف الخمسة: `WEAK_ARMY`, `SUICIDE_RISK`, `NPC_LEVEL_LOCKED`, `REBEL_PREREQUISITE_FAILED`, `CMD_OPTING`.
  7. فحص أسئلة الهيبة `4112019`, `4112030`, `4112001`, `PRESTIGE_QUEST_IDS`.
  8. فحص آليات `ExcludeManager` (confirm & release).
  9. فحص المخطط المعماري الموحد لـ `BaseTask` والدوال الخمس المشتركة وخرائط Before & After.

### المرحلة الرابعة: صياغة التقرير النهائي وإصدار الحكم (Final Verdict & Handoff)
- إعداد تقرير التسليم `handoff.md` وفق المعايير الخمسة الإلزامية:
  1. Observation
  2. Logic Chain
  3. Caveats
  4. Conclusion (CLEAN / INTEGRITY VIOLATION)
  5. Verification Method
- إخطار المنسق بالنتيجة النهائية عبر `send_message`.

---

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Output)

| # | الأمر | الهدف والمسار | النتيجة المتوقعة |
|---|---|---|---|
| 1 | `git status --porcelain` | فحص نظافة الملفات المصدرية | لا توجد تعديلات غير مصرح بها على `tasks/` |
| 2 | `python .agents/teamwork/report_assembler/verify_report.py` | تشغيل أداة التحقق المعتمدة | `100% CLEAN PASS` |
| 3 | `python .agents/teamwork/auditor/independent_forensic_check.py` | فحص جنائي مستقل متعمق وخلو من المحظورات | اجتياز جميع الفحوصات الجنائية بنسبة 100% |
