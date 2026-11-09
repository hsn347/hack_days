# تقرير فني مسبق: خطة تدقيق النصر المستقل (Victory Audit Execution Plan)

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Objective)
مطلوب إجراء تدقيق نصر مستقل (Victory Audit) للمشروع للتحقق من اكتمال المتطلبات (R0, R1, R2, R3, R4) ومعايير القبول المحددة في `ORIGINAL_REQUEST.md`، والتأكد من عدم وجود أي واجهات وهمية (facades) أو تزوير في النتائج أو تجاوز لاختبارات التأكيد، والتحقق من التزام قواعد `GEMINI.md`، وتنفيذ حزم الاختبارات المحددة في المرحلة C بشكل مستقل.

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Planned Steps)
- **المرحلة أ (Phase A): إعادة بناء الجدول الزمني ومراجعة المنجزات:**
  فحص سجلات الوكلاء العشرين (`.agents/teamwork/`) والتحقق من وجود مخرجات الوكلاء العشرة للهندسة والعشرة للاختبار والتجربة الحية.
- **المرحلة ب (Phase B): فحص النزاهة وكشف الغش والالتزام بالقواعد:**
  فحص الكود المصدري في `core/live_memory.py`, `game_client.py`, `bot_manager.py`, ملفات الاختبار للتأكد من عدم وجود hardcoded mock facades أو bypassed assertions، والتحقق من العزل التام لمهمة `elf` (Rule 7) والعمل المحلي فقط (Rule 4).
- **المرحلة ج (Phase C): التنفيذ المستقل لحزم الاختبارات:**
  تشغيل الأوامر العشرة المحددة في أمر التكليف وقياس النتائج ومقارنتها بما هو معلن.

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)
1. `Get-ChildItem -Directory .agents/teamwork/`
   - النتيجة المتوقعة: حصر مجلدات وتقارير الوكلاء العشرين ومجلدات التدقيق.
2. `git status; git log -n 5 --oneline`
   - النتيجة المتوقعة: معرفة حالة المستودع وآخر الالتزامات محلياً دون رفع.
3. تشغيل حزم الاختبارات المحددة:
   - `python -m unittest tests/test_agent14_city_resource_qa.py`
   - `python -m unittest tests/test_live_conn_agent11.py`
   - `python -m unittest tests/test_live_memory.py`
   - `python -m unittest tests/test_game_client_hygiene.py`
   - `python -m unittest tests/test_building_lifecycle_qa.py`
   - `python -m unittest tests/test_gate_fallback_empirical.py`
   - `python -m unittest tests/test_live_memory_marches_army.py`
   - `python -m unittest tests/test_live_socket_spy.py`
   - `python -m unittest tests/test_concurrency_stress.py`
   - `python tests/audit_whitelist_memory.py`
   - النتيجة المتوقعة: اجتياز جميع الاختبارات والتأكد من نتائجها التجريبية بالأدلة.
