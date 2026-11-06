# تقرير فني مسبق لإجراءات التدقيق الجنائي والاختبار المستقل (Milestone 6 Victory Audit)
**التاريخ والوقت:** 2026-11-03T23:36:00Z  
**المُعد:** المدقق الجنائي والنزاهة المستقل (Forensic Auditor - M6)  
**المهمة:** تنفيذ التدقيق الجنائي النهائي الشامل على مخرجات التحسين الهندسي للمنصة (R1, R2, R3, R4) والتحقق من النزاهة التامة والامتثال للقواعد الصارمة.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
تتطلب إجراءات التدقيق والتحقق المستقل للمرحلة السادسة (Milestone 6 Victory Audit) التحقق القطعي مما يلي:
1. **الامتثال الصارم للحظر (Strict Prohibition Compliance):** التأكد من عدم فتح أو قراءة أو تعديل أو لمس الملفات المحظورة الثلاثة: `game_client.py`، و`core/onemt_auth.py`، و`core/onemt_bot.py`، والتأكد من عدم وجود أي تغييرات في git أو تغييرات زمنية تمس هذه الملفات إطلاقاً.
2. **أصالة البيانات والمقاييس (Authenticity of Telemetry & Implementations):** التأكد من أن جميع الأرقام والجداول والادعاءات الواردة في تقرير المنصة النهائي `FINAL_PLATFORM_OVERHAUL_REPORT.md` وتقرير خط الأساس وتقرير الـ Soak Testing تستند إلى ملفات ونتائج حقيقية على القرص، وخلو الكود تماماً من أي نتائج اختبار مسبقة الصنع (Hardcoded shortcuts) أو واجهات وهمية (Facade mocks) أو دوال شكلية فارغة.
3. **التحقق السلوكي والتنفيذي (Execution Validation):** إعادة تشغيل حزم الاختبار الرئيسية للتأكد من نجاحها بشكل حقيقي ومستقل:
   - `python tests/run_all_tests.py` (يجب أن تنجح 30/30).
   - `python tests/test_mandatory_scenarios.py` (يجب أن تنجح 18/18).
4. **حظر النشر الخارجي (Local Workspace Only):** التأكد التام من أن كافة العمليات تمت محلياً فقط دون أي اتصال خارجي أو رفع إلى خوادم الإنتاج.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Methodological Steps)

### الخطوة الأولى: فحص النزاهة وحظر الملفات عبر Git
- تنفيذ أمر فحص حالة المستودع `git status` و `git diff --stat HEAD~5..HEAD` للتأكد من عدم تعديل الملفات المحظورة إطلاقاً.
- التحقق من هاشات وتواريخ تعديل الملفات عبر بايثون أو أوامر النظام دون فتح محتوى الملفات المحظورة.

### الخطوة الثانية: فحص أصالة ملفات المقاييس على القرص
- فحص وجود وصحة ملفات:
  - `tools/baseline_metrics_prefix.json`
  - `tools/baseline_metrics_postfix.json`
  - `tools/soak_test_results.json`
  - `tools/BASELINE_METRICS_POSTFIX.md`
  - `tools/SOAK_TEST_REPORT.md`
- مقارنة الأرقام الواردة في `FINAL_PLATFORM_OVERHAUL_REPORT.md` مع القيم الخام المخزنة في ملفات JSON والتأكد من التطابق التام بدون أي تزوير.

### الخطوة الثالثة: كشف الدوال الوهمية والاختصارات المزيفة (Anti-Facade & Anti-Hardcoding Search)
- فحص التعديلات في ملفات الباك إند (`core/database.py`, `api_server.py`, `bot_manager.py`, `dashboard/src/pages/AdminUsersCastles.tsx`, `dashboard/src/pages/AdminLiveProcesses.tsx`) للتأكد من أن:
  - منطق الـ Pagination يعمل باستعلامات SQL فعلية (`LIMIT`, `OFFSET`, `COUNT(*) OVER()`).
  - منطق حالات العمليات الحية الست يعتمد على `BotManager` ودورة حياة حقيقية وليس نصوص ثابتة.
  - إيقاف البوت يتم فعلياً عبر `_stop_and_join_bot` وتحرير القواميس العشرة.

### الخطوة الرابعة: تشغيل الاختبارات المستقلة والتحقق من النتيجة
- تشغيل:
  1. `python tests/run_all_tests.py` والتحقق من نتيجة 30/30 بنسبة 100%.
  2. `python tests/test_mandatory_scenarios.py` والتحقق من نتيجة 18/18 بنسبة 100%.
  3. (اختياري إضافي) تشغيل `python tests/test_challenger_m4_stress.py` و `python tests/test_memory_cpu_m4.py` للتأكد من شمولية النجاح.

### الخطوة الخامسة: إصدار القرار النهائي وكتابة تقرير Handoff
- توثيق كافة الملاحظات وسلسلة الاستدلال المنطقي والتحفظات والقرار النهائي (CLEAN أو INTEGRITY VIOLATION) في `handoff.md`.
- إرسال إشعار الإنجاز النهائي للمنسق عبر `send_message`.

---

## 3. الأوامر والملفات التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Output)

| # | الأمر / الملف | المسار | النتيجة المتوقعة |
|---|---|---|---|
| 1 | `git status --porcelain` | root | عدم وجود أي تعديل غير ملتزم في الملفات المحظورة الثلاثة |
| 2 | `git log -n 5 --name-only` | root | مراجعة الكوميتات الأخيرة للتأكد من عدم مساس الملفات المحظورة |
| 3 | فحص ملفات JSON للمقاييس | `tools/*.json` | تطابق أرقام الذاكرة، المعالج، الإنتاجية، وسلوب Soak مع التقرير |
| 4 | `python tests/run_all_tests.py` | root | `30 Total | 30 Pass | 0 Fail | Pass: 100.0%` |
| 5 | `python tests/test_mandatory_scenarios.py` | root | `Ran 18 tests in ...s - OK` |

تم إعداد هذا التقرير مسبقاً التزاماً تاماً بالقاعدة الخامسة من GEMINI.md قبل تشغيل أي أمر.
