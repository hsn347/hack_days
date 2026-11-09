# تقرير فني مستقل: خطة بناء وتنفيذ حزمة اختبارات الذاكرة الحية وبوابة الجاهزية
**Technical Report: Live Memory Engine & Readiness Gate QA Test Suite**

**التاريخ**: 2026-11-09T13:25:00Z  
**المعرف**: `REPORT-QA-M1-LIVE-MEM-001`  
**الوكيل**: Test Writer: Live Memory & Readiness Gate QA (`test_writer_m1`)  
**المسار المستهدف**: `e:\osmanli\tests\test_live_memory.py`  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause & Justification)

وفقاً للتكليف في `ORIGINAL_REQUEST.md` وتقارير المعمارية والمواصفات:
- `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`
- `CONTROLLER_WHITELIST_SPEC.md`
- `LUA_PROTOCOL_SPEC.md`
- `DEEP_MERGE_SPEC.md`

يعاني البوت في النسخة السابقة من مشاكل جوهرية:
1. **استبدال سطحي للكائنات (`init_data.update(retdata)`)**: يؤدي إلى هدم ومسح القوائم التراكمية مثل `blist` في `cityCtrl` وحقول الموارد الآمنة `saferes` وغيرها فور وصول تحديث فرعي.
2. **الدمج الساذج للقوائم (`_deep_merge`)**: استبدال قائمة كاملة ذات 50 مبنى بقائمة تحتوي على مبنى واحد فقط مرسل من السيرفر كـ delta.
3. **تسرب الذاكرة بالمتحكمات غير المصرح بها**: دخول 187 متحكماً زائداً من السيرفر (شات، إعلانات، نقاط حمراء).
4. **تزامن التكرار (Race Conditions & Iterator Invalidation)**: انهيار المهام عند قراءة `blist` بالتزامن مع استقبال وتحديث الحزم (`RuntimeError: dictionary/list changed size during iteration`).
5. **غياب بوابة الجاهزية الصارمة (`wait_for_memory_ready`)**: بدء المهام قبل اكتمال المتحكمات الأساسية، وغياب الاستعلام التعويضي التلقائي (`Fallback Sync Query`).

المطلوب إنشاء حزمة اختبارات شاملة، مستقلة وعالية الصرامة في `e:\osmanli\tests\test_live_memory.py` للتحقق بنسبة 100% من معايير القبول.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Implementation Steps)

1. **استكشاف بيئة العمل وحالة التنفيذ في المشروع**:
   - التحقق من وجود وحالة ملفات التنفيذ المركزية (`core/live_memory.py`, `game_client.py`).
   - التحقق من تكامل الكود أو استخدام وحدات الاختبار المعيارية (`pytest` / `unittest`).
2. **تصميم حزمة الاختبارات الشاملة `tests/test_live_memory.py`**:
   - **القسم الأول: Whitelist Ingress Filtering**:
     - تمرير حزم تحوي متحكمات مسموحة (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`) ومتحكمات ضوضاء غير مسموحة (`chatCtrl`, `RedPointCtrl`, `videoAdCtrl`, `randomGarbage`).
     - التأكيد الصارم على وجود المسموح فقط واستبعاد غير المصرح به بنسبة 100%.
   - **القسم الثاني: Keyed Deep Merge Correctness**:
     - اختبار 50 مبنى في `cityCtrl.blist` ودمج دلتا لمبنى واحد (`index: 10`, `lv: 25`, `state: 1`) والتأكد من بقاء الـ 50 مبنى بدون أي تكرار وتحديث المبنى 10 فقط.
     - اختبار قائمة الأبطال `heroCtrl.heroes` وتحديث بطل دون تكرار.
     - اختبار قائمة الـ buffs في `buffCtrl`.
     - اختبار قاموس الطوابير في `queueCtrl`.
     - اختبار القوائم البسيطة (Primitive Lists مثل `arealist`) والتأكد من استبدالها بشكل آمن.
   - **القسم الثالث: Concurrency & Copy-on-Write (CoW) Safety**:
     - محاكاة قراءة تكرارية نشطة لـ `blist` عبر مهام متزامنة بالتوازي مع 100 عملية دمج متزامنة للحزم.
     - التأكد من عدم حدوث أي استثناء `RuntimeError: dictionary/list changed size during iteration`.
   - **القسم الرابع: Notification Handling**:
     - معالجة `NOTIFY_CITY`: فروق الموارد `res` بالجمع/الطرح وحماية الصفر، تحديث الموارد الآمنة `saferes`، وإضافة الموارد غير المجموعة `updateUnCollectRes`.
     - معالجة `NOTIFY_QUEUE`: انتهاء ترقية مبنى عادي ورفع `lv` بمقدار 1 وتحويل الحالة إلى `BUILD_STATE.NORMAL` ("0").
     - ترقية المجد (Honor level) ورفع `honorLv` و `hlv` بمقدار 1 وتحويل الحالة إلى `"0"`.
   - **القسم الخامس: Readiness Gate & Fallback Queries**:
     - فحص `wait_for_memory_ready` عند نقص متحكم أساسي والتأكد من إرجاع False.
     - فحص الاستعلام التعويضي التلقائي وتدفق البيانات واجتياز البوابة بنجاح.
     - فحص انتهاء المهلة (Timeout) عند عدم استجابة السيرفر.
3. **تنفيذ الاختبارات**:
   - تشغيل الاختبارات عبر PowerShell باستخدام `pytest` أو `python -m unittest`.
   - التأكد من اجتياز كافة الاختبارات بنسبة 100%.
4. **كتابة تقرير التسليم النهائي (`handoff.md`) ومراسلة المنسق**.

---

## 3. الأوامر والملفات والأسطر المستهدفة بالتفصيل مع النتيجة المتوقعة

1. **أمر فحص حالة الملفات والمجلدات في المشروع**:
   - الأمر: `git status` أو `Get-ChildItem -Path .agents\teamwork`
   - النتيجة المتوقعة: معرفة ما إذا كانت هناك ملفات قيد التطوير بواسطة الوكلاء المتزامنين في السرب.
2. **ملف الاختبار `tests/test_live_memory.py`**:
   - الإجراء: إنشاء الملف بكافة فئات الاختبارات المطلوبة.
   - النتيجة المتوقعة: بناء ملف كود فحص مؤتمت يتضمن اختبارات معيارية دقيقة وتغطية شاملة للمتطلبات الخمسة.
3. **أمر تشغيل الاختبارات**:
   - الأمر: `python -m unittest tests/test_live_memory.py` أو `pytest tests/test_live_memory.py -v`
   - النتيجة المتوقعة: اجتياز كافة الاختبارات بنجاح تام (100% Pass).
