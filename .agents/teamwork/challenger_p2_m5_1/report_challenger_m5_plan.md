# تقرير الخطة الفنية والتحدي التجريبي لمرحلة Milestone 5 (Requirement R4)
## التدقيق المعادي المستقل لسيناريوهات دورة الحياة الـ 18 واختبارات التحمل المستمرة (Soak Testing)

- **التاريخ:** 2026-11-03
- **المهندس المنفذ:** Challenger 1 (teamwork_challenger: Critic, Specialist)
- **معرف جلسة المشرف:** `849edb08-8a01-463a-a4d9-889f072bccf9`
- **حالة الالتزام:** متوافق بنسبة 100% مع `AGENTS_CONSTITUTION.md`، و `GEMINI.md` (القاعدة 4 و 5)، و `ORIGINAL_REQUEST.md` (المتطلب R4).
- **الحظر الصارم:** لا مساس ولا تعديل ولا فتح إطلاقاً للملفات المحظورة الثلاثة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`). بيئة العمل محلية فقط دون أي رفع أو اتصال بسيرفر خارجي، ولا تعديل على كود التطبيق الأساسي (Review-only).

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Root Rationale)
وفقاً للمتطلب R4 من وثيقة `ORIGINAL_REQUEST.md` وتكليف المشرف:
1. **التحقق المستقل والتجريبي من السيناريوهات الـ 18 الإلزامية**:
   قام العامل (Worker M5 Gen 2) بالادعاء بأن الجناح الهرمسي `tests/test_mandatory_scenarios.py` يجتاز 18 سيناريو دورة حياة بنسبة 100%، وأن اختبار التحمل `tools/soak_test_lifecycle.py` حقق انحدار نمو ذاكرة $m = +0.0269$ MB/cycle وصفر خيوط متبقية.
   كدور Challenger تجريبي ومعادٍ، يُمنع الوثوق بأي ادعاء غير مثبت تجريبياً. يتوجب تشغيل الجناح بالكامل مع الراية التفصيلية `-v` والتأكد من انعدام السباقات والتسريبات.
2. **التحدي المعادي للسيناريوهات الحدية (Adversarial Edge Scenario Challenge)**:
   يتعين بناء واختبار سيناريوهات عدائية متطرفة مستقلة في `tests/test_challenger_p2_m5_adversarial.py` لاختبار:
   - **Rapid Failure Churn**: دورات سريعة جداً من الفشل المتكرر وإعادة المحاولة في فترات زمنية متقاربة، وفحص عدم حدوث Deadlock أو تسريب مراجع أو احتجاز أقفال.
   - **In-Flight Deletion**: حذف القلاع والمستخدمين بالتزامن في أطوار حرجة متعددة (أثناء محاولات المصادقة، أثناء إعادة الاتصال، أثناء انتظار الدورة، وأثناء التشغيل).
   - **Stalled Thread Isolation**: عزل الخيوط غير المستجيبة، والتأكد التام من وضعها في `_stalled_threads` كحالة تشخيصية وعدم احتسابها كعمليات حية نشطة تحت أي ظرف وتأكيد سلامة استرداد الموارد.
3. **التثبت من جناح المنصة الموحد**:
   تشغيل `python tests/run_all_tests.py` والتأكد من نجاح 30/30 بدون أي فشل أو تراجع.
4. **التحقق المستقل من اختبار التحمل (Soak Testing)**:
   تشغيل `python tools/soak_test_lifecycle.py --cycles 5 --bots 5` والتحقق من حسابات الانحدار ومقابض الذاكرة والخيوط.

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Implementation Steps)

#### الخطوة 1: تشغيل وتحليل جناح السيناريوهات الإلزامية الـ 18
- تنفيذ الأمر: `python tests/test_mandatory_scenarios.py -v`
- فحص مخرجات كل اختبار من S01 إلى S18 بدقة.

#### الخطوة 2: إنشاء وتشغيل جناح التحدي المعادي المستقل
- إنشاء ملف اختبار معادٍ في `tests/test_challenger_p2_m5_adversarial.py` يتضمن:
  - اختبار `test_rapid_failure_churn_concurrency`: إطلاق دورات فشل خاطفة متعددة وفحص هياكل التتبع `_threads`, `_stop_events`, `_bot_managers`, `_conn_states`, إلخ.
  - اختبار `test_in_flight_concurrent_deletion_stress`: تدمير متزامن لقلاع ومستخدمين في مختلف حالات التشغيل والتأكد من نظافة التحرير والربط مع البروكسي.
  - اختبار `test_stalled_thread_quarantine_integrity`: توليد خيوط عالقة عمداً والتحقق من بقائها في `_stalled_threads` واستبعادها التام من العمليات الحية وقوائم الـ API.
- تنفيذ الأمر: `python tests/test_challenger_p2_m5_adversarial.py -v`

#### الخطوة 3: تشغيل جناح المنصة الموحد
- تنفيذ الأمر: `python tests/run_all_tests.py`
- التأكد من تسجيل 30/30 PASS.

#### الخطوة 4: التحقق المستقل من سكربت التحمل
- تنفيذ الأمر: `python tools/soak_test_lifecycle.py --cycles 5 --bots 5`
- فحص الميل الرياضي $m \le 0.05$ وصافي الخيوط المتبقية $= 0$ وانعدام تسريبات القواميس.

#### الخطوة 5: صياغة تقرير التسليم النهائي (Handoff Report)
- كتابة `e:\osmanli\.agents\teamwork\challenger_p2_m5_1\handoff.md` المتضمن للملاحظات وسلسلة الاستدلال والمحاذير والقرار النهائي وإرسال الإشعار عبر `send_message`.

---

### 3. الأوامر والملفات والنتائج المتوقعة بالتفصيل (Detailed Commands & Expected Results)

1. **الأمر الأول**:
   - الأمر: `python tests/test_mandatory_scenarios.py -v`
   - النتيجة المتوقعة: تشغيل 18 اختباراً واجتيازها جميعاً `OK (18/18)` دون أخطاء أو تعليق.
2. **الأمر الثاني**:
   - الأمر: إنشاء `tests/test_challenger_p2_m5_adversarial.py` ثم تشغيله: `python tests/test_challenger_p2_m5_adversarial.py -v`
   - النتيجة المتوقعة: نجاح كافة اختبارات الإجهاد المعادي (Rapid Failure Churn, In-Flight Deletion, Stalled Thread Isolation).
3. **الأمر الثالث**:
   - الأمر: `python tests/run_all_tests.py`
   - النتيجة المتوقعة: نجاح 30/30 اختباراً بنسبة 100%.
4. **الأمر الرابع**:
   - الأمر: `python tools/soak_test_lifecycle.py --cycles 5 --bots 5`
   - النتيجة المتوقعة: إنهاء 5 دورات بـ 5 بوتات، ظهور `OVERALL SOAK VERDICT: >>> PASSED <<<`، slope $m \le 0.05$ MB/cycle، و $\Delta\text{threads} = 0$.
