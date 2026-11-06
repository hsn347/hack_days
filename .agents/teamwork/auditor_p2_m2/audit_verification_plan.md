# تقرير خطة التحقق والتدقيق الجنائي للمرحلة الثانية (Milestone 2 Forensic Verification Plan)

**المعرف:** `auditor_p2_m2`  
**التاريخ والوقت:** 2026-11-03T02:06:00Z  
**المرجع:** `GEMINI.md` البند 5 (إلزامية إرفاق ملف تقرير مستقل قبل أي أمر أو تعديل)  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
بموجب التكليف الممنوح للمدقق الجنائي في المرحلة الثانية (Milestone 2: Requirement R1 - Admin Castles Pagination & Lazy Loading)، ودستور الوكلاء `AGENTS_CONSTITUTION.md`، ودليل النزاهة الجنائية، يُشترط التحقق المستقل من خلو تسليمات المرحلة الثانية من أي تزييف، أو واجهات وهمية (Facades)، أو تقسيم بيانات صوري في الذاكرة بدلاً من قاعدة البيانات، والتأكد القطعي من عدم لمس الملفات المحظورة الثلاثة:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
وكذلك التأكد من اجتياز كافة اختبارات المنصة (30/30) واختبارات التحجيم وضغط الحزم دون أي أخطاء.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)
1. **الخطوة الأولى:** التحقق الجنائي عبر Git و AST من سلامة الملفات المحظورة وعدم وجود أي تعديلات أو تدنيس لها.
2. **الخطوة الثانية:** التحقق من بناء الواجهة الأمامية بدون أي أخطاء تصريف TypeScript.
3. **الخطوة الثالثة:** تشغيل حزمة الاختبارات الشاملة للمنصة `python tests/run_all_tests.py` للتحقق من اجتياز 30/30 اختباراً بنسبة 100%.
4. **الخطوة الرابعة:** تشغيل اختبارات التحقق من الترقيم وقابلية التوسع `python tools/verify_m6_admin_scalability.py`.
5. **الخطوة الخامسة:** تشغيل اختبارات التحمل وضغط الحزم `python tools/stress_m6_master_detail.py`.
6. **الخطوة السادسة:** استخراج النتائج وإصدار التقرير النهائي وقرار النزاهة (CLEAN / INTEGRITY VIOLATION).

---

## 3. الأوامر التي ستُنفذ بالتفصيل والنتائج المتوقعة (Commands & Expected Output)

| # | الأمر (Command) | الغرض | النتيجة المتوقعة |
|---|---|---|---|
| 1 | `git status --porcelain game_client.py core/onemt_auth.py core/onemt_bot.py` | التأكد من عدم وجود أي تعديل مسجل في Git للملفات المحظورة | مخرج فارغ (Zero changes) |
| 2 | `python -c "import ast; [ast.parse(open(f, 'rb').read()) for f in ['game_client.py', 'core/onemt_auth.py', 'core/onemt_bot.py']]; print('PROHIBITED_FILES_PARSED_CLEAN')"` | التحقق من صحة وقابلية قراءة الشجرة التركيبية للملفات المحظورة دون تعديل محتواها | `PROHIBITED_FILES_PARSED_CLEAN` |
| 3 | `powershell -Command "Set-Location dashboard; npm run build"` | التحقق من خلو الواجهة ومكونات الترقيم من أخطاء TypeScript | كود الخروج `0` وملفات الـ dist مبنية بنجاح |
| 4 | `python tests/run_all_tests.py` | تشغيل الـ 30 اختباراً الخاصة بالمنصة | 30/30 PASS بنسبة 100% |
| 5 | `python tools/verify_m6_admin_scalability.py` | اختبارات الترقيم الهيكلي واستبعاد الـ config | 38/38 PASS بنسبة 100% |
| 6 | `python tools/stress_m6_master_detail.py` | اختبارات التحمل وتخفيض الباندويث | 36/36 PASS وباندويث < 60 KB |
