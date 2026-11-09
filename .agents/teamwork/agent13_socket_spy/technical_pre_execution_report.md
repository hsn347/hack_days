# Technical Pre-Execution Report: Live Socket Spy & S2C Notify Verification
**Agent**: Agent 13 (Live Socket Spy & Notify Verifier)  
**Role**: Empirical Challenger (critic, specialist)  
**Date**: 2026-11-09T13:50:00Z  
**Workspace**: `e:\osmanli`  
**Reference Documents**:
- `ORIGINAL_REQUEST.md`
- `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`
- `agent1_lua_analyst/LUA_PROTOCOL_SPEC.md`
- `core/live_memory.py`
- `game_client.py`
- `game file/lua_src/cmdDef_dec.lua`
- `game file/lua_src/notifyCtrl_dec.lua`
- `game file/lua_src/cityCtrl_dec.lua`

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Purpose)

يتطلب طلب المستخدم وتوجيه الوكيل الرئيسي التحقق التجريبي الميداني الصارم (Empirical Verification) من السلوك اللحظي لمقبس الشبكة ومحرك الذاكرة الحية (`core/live_memory.py` و `game_client.py`) عند استلام حزم وإشعارات السيرفر `S2C` (خاصة حزم `cmd == 1009`).

تحديداً، يجب التحقق تجريبياً وقياسياً من النقاط التالية:
1. **انعكاس إشعارات CMD 1009 لحظياً في الذاكرة الحية**:
   - `NOTIFY_CITY` (معرف 9 بالبروتوكول): فروق الموارد `res`، الموارد الآمنة `saferes`، الحد اليومي `dayMaxRes`، الموارد غير المجموعة بالمباني `updateUnCollectRes`، وتفعيل طابور الشحن `openChargeQueue`.
   - تدقيق الفارق بين تسمية التكليف `NOTIFY_CITY ("1")` والبروتوكول الفعلي للعبة (`NOTIFY_CITY_UPDATE == "9"` و `NOTIFY_BACKPACK_UPDATE == "1"` في `cmdDef_dec.lua`).
   - `NOTIFY_QUEUE` (14) و `NOTIFY_PLAYER_QUEUE_CHANGE` (1051): دورة حياة الطوابير وانعكاس انتهاء/إلغاء الترقية على مستوى وحالة المبنى في `cityCtrl.blist` (ترقية عادية `lv + 1`، ترقية مجد `honorLv + 1`، إلغاء `state = NORMAL` دون رفع المستوى).
   - `NOTIFY_BACKPACK_UPDATE` (1): إضافة (`add`) وخصم (`use`) عناصر الحقيبة.
   - `NOTIFY_LOCAL_QUEUE_SYNC` (202): إضافة (1)، تحديث (3)، حذف (2)، مزامنة كاملة (4)، ومسح شامل (5) لمسيرات الجيوش في `local_queues`.
2. **قياس زمن انتقال الحزمة (Propagation Latency)** من لحظة استقبال البايتات في المقبس وفكها في `_dispatch` حتى تصبح متاحة في `init_data` (المطلوب $O(1)$ لحظي، أقل من 1 ملي ثانية).
3. **التحقق من سقف `cached_packets`**: إثبات بقاء السعة محصورة (لا تزيد عن 64 حزمة FIFO) وعدم تراكم الذاكرة بشكل غير محدود.
4. **فحص الصمود العدائي (Adversarial Stress Testing)**: ضخ سيول متزامنة من الحزم والإشعارات غير المرتبة أو المشوهة للتأكد من عدم حدوث Race Conditions أو KeyErrors.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Steps)

1. **كتابة كود اختبار تجريبي شامل ومستقل (`tests/test_live_socket_spy.py`)**:
   - استخدام محاكاة واقعية لحزم الشبكة من خلال `game_client.GateClient` و `LiveMemoryEngine`.
   - اختبار تدفق البايتات الخام عبر بروتوكول البوت الحقيقي (`pack_request` / `unpack_stream` / `decode_gate_response`) ليمر عبر `_buf` و `_dispatch` الفعلي للمقبس، لقياس زمن المعالجة الحقيقي للشبكة وليس مجرد استدعاء دالة.
   - اختبار كافة السيناريوهات الفرعية للـ 5 إشعارات المطلوبة.
   - إجراء اختبار قياس زمن الاستجابة (Latency Benchmarking) عبر 1000 حزمة متتالية وحساب المتوسط والانحراف المعياري والحد الأقصى (Microsecond precision).
   - إجراء اختبار سعة `cached_packets` بضخ 500 حزمة والتأكد من عدم تجاوز الحجم لـ 64 عنصر.
   - إجراء اختبار الصمود العدائي ضد الحزم المشوهة (Missing fields, wrong types, concurrent threading access).
2. **تنفيذ الاختبار محلياً باستخدام بايثون عبر `run_command`**.
3. **تحليل المخرجات وتوثيق كافة النتائج بدقة في تقرير التسليم `handoff.md`**.

---

## 3. الأوامر والملفات والنتائج المتوقعة بالتفصيل (Commands, Files & Expected Results)

### الملفات المستهدفة:
- إنشاء ملف الفحص: `tests/test_live_socket_spy.py`
- إنشاء تقرير التسليم النهائي: `e:\osmanli\.agents\teamwork\agent13_socket_spy\handoff.md`

### الأمر المزمع تنفيذه:
```powershell
python -m unittest tests/test_live_socket_spy.py
```
أو
```powershell
python tests/test_live_socket_spy.py
```

### النتائج المتوقعة:
1. نجاح كافة الفحوصات بنسبة 100%.
2. إثبات أن زمن المعالجة والانعكاس في `init_data` يستغرق أقل من 0.05 ملي ثانية لكل حزمة ($O(1)$).
3. إثبات أن سعة `cached_packets` تقف بدقة عند 64 حزمة ولا تتجاوزها إطلاقاً.
4. إثبات صحة تحديث الموارد والمباني والطوابير والحقيبة والمسيرات بدقة تطابق سلوك كود اللعبة المرجعي `lua_src`.
