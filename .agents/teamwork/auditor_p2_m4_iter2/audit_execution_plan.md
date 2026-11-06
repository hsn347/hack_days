# تقرير خطة التحقق والتدقيق الجنائي — المرحلة 4 (التكرار 2)
## Forensic Audit Pre-Execution Technical Report (GEMINI.md Rule 5 Compliance)

**التاريخ**: 2026-11-03  
**المهمة**: التدقيق الجنائي المستقل لإصلاحات المرحلة 4 التكرار 2 (Milestone 4 Iteration 2 Remediation)  
**المدقق**: Forensic Auditor M4 Iteration 2 (`teamwork_auditor`)  
**الملف المستهدف للتدقيق**: `api_server.py`  
**الملفات المحظورة قطيعاً**: `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py` (يُحظر لمسها أو فتحها أو تعديلها أو قراءتها)  

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Objective)
- قدم الوكيل Worker M4 Iteration 2 إصلاحاً في `api_server.py` لمعالجة تسريب معرفات القلاع في البنية العاشرة `_user_stopped` التي رصدها Challenger 1 في تقرير `challenger_p2_m4_1/handoff.md`.
- تقتضي مهام التدقيق الجنائي التحقق المستقل من:
  1. الالتزام الصارم بالحظر القطعي: التأكد من أن الملفات المحظورة الثلاثة لم تُمس أو تُعدل إطلاقاً، والتحقق من بصمات SHA256 وحالة Git دون فتح الملفات.
  2. أصالة المعالجة البرمجية: التأكد من أن أسطر التعديل في `api_server.py` (السطور 407، 999، 1517، 2423) تمثل منطقاً حقيقياً غير مزيف ولا تحتوي على hardcoded mocks أو تجاوزات احتيالية.
  3. التحقق التنفيذي الميداني: تشغيل سيناريوهات الإجهاد المعادي `python tests/test_challenger_m4_stress.py` وتشغيل الجناح الشامل `python tests/run_all_tests.py` للتحقق من اجتياز الاختبارات بنسبة 100%.
  4. التحقق من الحظر التام لأي نشر أو اتصال خارجي: التأكد من العمل في بيئة التطوير المحلية حصراً.

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Audit Logic & Steps)
- **الخطوة 1**: فحص حالة Git لتأكيد أن التعديلات محصورة حصراً في الملفات المسموحة ولم تطل أياً من الملفات المحظورة.
- **الخطوة 2**: فحص تجزئة التشفير (SHA256) للملفات المحظورة بالاستعلام الخارجي للأداة (مثل `certutil -hashfile`) لمقارنتها مع الحالة الأصلية وضمان عدم مساسها.
- **الخطوة 3**: تشغيل الاختبار المعادي `python tests/test_challenger_m4_stress.py` للتحقق من إفراغ `_user_stopped` بعد انتهاء دورة الخيوط الـ 20 واكتمال `_stop_and_join_bot`.
- **الخطوة 4**: تشغيل جناح الاختبارات الشامل `python tests/run_all_tests.py` للتحقق من سلامة كافة وظائف المنصة.
- **الخطوة 5**: توثيق الأدلة والمخرجات الخام وإصدار الحكم النهائي في `handoff.md`.

---

### 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands to Execute & Expected Results)

1. **أمر التحقق من حالة Git**:
   - `git status --porcelain`
   - *النتيجة المتوقعة*: الملفات المحظورة (`game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`) غير مدرجة ضمن الملفات المعدلة، والتعديل يظهر فقط في `api_server.py` وملفات التوثيق/الاختبار.

2. **أمر فحص بصمة SHA256 للملفات المحظورة**:
   - `Get-FileHash -Algorithm SHA256 game_client.py, core/onemt_auth.py, core/onemt_bot.py`
   - *النتيجة المتوقعة*: استخراج الهاشات ومقارنتها بسجلات التدقيق السابقة للتأكد من عدم حدوث أي تغيير قطعي.

3. **أمر تشغيل اختبار الإجهاد والتسريب المعادي**:
   - `python tests/test_challenger_m4_stress.py`
   - *النتيجة المتوقعة*: `Ran 4 tests in ...s - OK` مع ظهور `[Leak-Check] _user_stopped retains castle_id after _stop_and_join_bot: False`.

4. **أمر تشغيل جناح اختبارات النظام الشامل**:
   - `python tests/run_all_tests.py`
   - *النتيجة المتوقعة*: `OVERALL SUITE TOTALS: 30/30 PASS (100.0%)`.
