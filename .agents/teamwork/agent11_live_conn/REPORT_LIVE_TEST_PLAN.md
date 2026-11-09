# تقرير فني: تصميم وتنفيذ حزمة الاختبارات التجريبية الحية (Live Connection & Init Replay QA Battery)
**Technical Report: Empirical Live Connection & Packet Replay Test Execution**
**Agent**: Agent 11 (Live Connection & Init Tester)  
**Date**: 2026-11-09T13:50:00Z  

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
وفقاً لمتطلبات المهمة R0 (الوكيل 11) و R1 و R2 و R3:
يجب التحقق تجريبياً وعملياً من:
1. تدفق الحزم عبر دالة الاستقبال المركزية `_dispatch()` في `GateClient` / `game_client.py`.
2. امتلاء `init_data` بالمتحكمات الحرجة الستة (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`).
3. التحقق الهيكلي من صحة البيانات (طول `blist`، حقول `reslist`، ومعرف `base` في `lordInfoCtrl`).
4. استبعاد كافة المتحكمات الـ 186 غير المصرح بها ومنع تسربها لذاكرة البوت.
5. تجربة محاولة الاتصال الحي بحساب من `database/session_cache.json`.
6. اختبار حالات الحافة والفشل العدائي (Adversarial stress testing): دمج جزئي لمبنى دون مسح الـ 56 مبنى الأخرى، حزم غير مصرح بها، وتفعيل بوابة الجاهزية.

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)
1. إنشاء ملف اختبار برميجي مستقل في مسار الاختبارات الرسمي `tests/test_live_conn_agent11.py`.
2. يشتمل الاختبار على الفئات الآتية:
   - **Test 1: Authentic Live Wire Packet Ingestion via `_dispatch()`**:
     ترميز حزم حقيقية بتنسيق بروتوكول المقبس (`pack_request` / `xor_crypt` / `zlib`) وحقنها في `client._buf`، ثم استدعاء `_dispatch()` لمحاكاة الاستقبال الشبكي الفعلي.
   - **Test 2: Whitelist Ingress Enforcement**:
     إثبات أن المتحكمات الـ 186 غير المدرجة في `ALLOWED_CONTROLLERS` تم رفضها واستبعادها بنسبة 100%.
   - **Test 3: Structural Integrity & Critical Controllers**:
     التأكد من اكتمال `cityCtrl.blist` (57 مبنى) و `cityCtrl.reslist` و `lordInfoCtrl.base.uid` و `armyCtrl` و `heroCtrl` و `backpackCtrl`.
   - **Test 4: Non-destructive Partial Update (Anti-Shallow-Update)**:
     إرسال حزمة فرعية لتحديث مبنى واحد فقط في `blist`، والتأكد من بقاء المباني الـ 56 الأخرى كما هي دون حذف.
   - **Test 5: Memory Readiness Gate Validation**:
     اختبار `client.wait_for_memory_ready()` والتأكد من نجاحه عند اكتمال البيانات وفشله/إرساله للاستعلام التعويضي عند نقصها.
   - **Test 6: Real Session Cache Live Gateway Authentication Attempt**:
     استدعاء `async_login` بحساب من `database/session_cache.json` لفحص استجابة خادم اللعبة المباشر وتسجيل النتيجة بدقة.
3. تشغيل الاختبار عبر `python -m unittest tests/test_live_conn_agent11.py` وتوثيق السجلات والنتائج.

## 3. الملفات والسطور أو الأوامر التي ستنفذ بالتفصيل مع النتيجة المتوقعة (Files, Lines & Commands)
- إنشاء ملف `tests/test_live_conn_agent11.py`.
- تشغيل: `python -m unittest tests/test_live_conn_agent11.py -v`.
- النتيجة المتوقعة: اجتياز كافة الاختبارات وتأكيد حماية الذاكرة وعزل الـ 186 متحكماً غير مصرح به.
