# تقرير فني مستقل: خطة الاختبارات التجريبية العنيفة (Empirical Stress Testing) لدورة حياة الخيوط والقواميس العامة (R3)

**تاريخ الإعداد**: 2026-11-03  
**الجهة المنفذة**: Challenger 1 (`teamwork_challenger`)  
**المهمة**: التحقق الميداني المستقل والتحدي التجريبي لمخرجات العامل M4 في المتطلب R3 وفقاً للوثيقة `ORIGINAL_REQUEST.md` والتكليف الصادر في `DISPATCH.md`.  
**الالتزام بالقواعد**: تطبيق كامل لقاعدة GEMINI.md رقم 5 والحظر الصارم للملفات الثلاثة المحظورة والعمل المحلي التام.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
وفقاً لتكليف Challenger 1، يتطلب التحقق من سلامة الباك إند بعد تعديلات العامل M4 إخضاع دورة حياة الخيوط (Thread Lifecycle) وهياكل البيانات العامة العشرة لفحص تجريبي صارم:
1. **تحدي التزامن لـ 20 بوتاً متزامناً**: التأكد من قدرة `_stop_and_join_bot` على التعامل مع إيقاف 20 خيطاً في وقت واحد دون حدوث Deadlock أو تعليق، وخلو جميع الهياكل العامة العشرة (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`) بعد الإيقاف.
2. **عزل الخيوط العالقة (Stalled Threads)**: التحقق من أن أي خيط غير متعاون (Uncooperative/Stalled) يتجاوز المهلة الزمنية يتم استبعاده فوراً من `_threads` وعزله في `_stalled_threads` دون تجميد أو تعليق المستدعي.
3. **تطهير ارتباطات البروكسي**: التحقق من دقة دوال الحذف `remove_castle_proxy` و `remove_user_proxy_bindings` في `proxy/proxy_manager.py` وتأكيد إزالتها من الذاكرة وملف التخزين الدائم JSON.
4. **سلامة جناح المنصة الشامل**: تشغيل `python tests/run_all_tests.py` لضمان عدم حدوث أي تراجع أو كسر في الطبقات الأربع للمنصة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Logic Steps)
1. **إنشاء سكربت اختبار ضغط مستقل**: `tests/test_challenger_m4_stress.py` يتضمن:
   - `test_concurrent_spawn_and_stop_20_bots`: إنشاء 20 خيطاً يحاكي عمل البوتات، تعبئة الهياكل العامة العشرة، إطلاق إيقاف متزامن عبر `concurrent.futures.ThreadPoolExecutor`، ثم قياس زمن التنفيذ وفحص فراغ الهياكل العشرة لكل قلعة.
   - `test_uncooperative_stalled_thread_isolation`: إنشاء خيوط تتجاهل إشارات الإيقاف، فحص سلوك المهلة الزمنية، والتأكد من نقلها إلى `_stalled_threads` واحتوائها على كافة بيانات التشخيص.
   - `test_proxy_manager_cleanup_lifecycle`: اختبار حذف البروكسي للقلاع والمستخدمين والتأكد من خلو الذاكرة والملف.
   - `test_deleted_castles_and_user_stopped_leak_check`: فحص سلوك `_user_stopped` و `_deleted_castles` بدقة عند الإيقاف وعند الحذف.
2. **تنفيذ سكربت اختبار الضغط**: عبر `run_command` وتشغيل `python tests/test_challenger_m4_stress.py`.
3. **تنفيذ جناح اختبارات المنصة الشامل**: تشغيل `python tests/run_all_tests.py`.
4. **تحليل النتائج وتوثيق الملاحظات**: توثيق الأدلة المباشرة وتقديم التقرير النهائي في `handoff.md`.

---

## 3. الأوامر والملفات التي ستُنفذ بالتفصيل والنتائج المتوقعة (Commands & Expected Results)
1. **الملف المستحدث**: `tests/test_challenger_m4_stress.py`
   - **الهدف**: اختبار الضغط المستقل.
2. **الأمر الأول**:
   - `python tests/test_challenger_m4_stress.py`
   - **النتيجة المتوقعة**: إتمام الاختبارات بنجاح وإبراز سلوك الهياكل العشرة بدقة.
3. **الأمر الثاني**:
   - `python tests/run_all_tests.py`
   - **النتيجة المتوقعة**: اجتياز 30 من أصل 30 اختباراً بنسبة 100%.
