# تقرير الفحص والتدقيق الجنائي القبلي: القائمة البيضاء وبصمة الذاكرة (Forensic Pre-Audit Report)
**Document ID**: `AUDIT-AGENT18-WHITELIST-MEM-01`  
**Agent**: Agent 18: Whitelist & Memory Footprint Auditor  
**Date**: 2026-11-09  
**Target Scope**: Ingress controller filtering, `ALLOWED_CONTROLLERS` enforcement, memory footprint reduction (RSS & JSON serialization), and memory leak / bounded growth validation in `core/live_memory.py` & `game_client.py`.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Objective)

وفقاً لمتطلبات المهمة المعتمدة في `ORIGINAL_REQUEST.md` (المتطلب R1 والبند 18) وتوجيه التدقيق:
1. يتدفق من خادم اللعبة ما يصل إلى 226 متحكماً مختلفاً (بما في ذلك غرف الدردشة الصوتية والنصية `chatCtrl`, `chatroomCtrl`, إشعارات النقاط الحمراء `RedPointCtrl`, الإعلانات `videoAdCtrl`, وسجلات العميل `clientLogCtrl`).
2. تفرض المعمارية المعتمدة في `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md` و `CONTROLLER_WHITELIST_SPEC.md` استبعاد 187 متحكماً غير مصرح به فور وصول الحزم في `_dispatch` عبر `LiveMemoryEngine.filter_whitelisted` و `extract_controllers`، وقصر `init_data` حصراً على `ALLOWED_CONTROLLERS` (المحددة بدقة بـ 42 متحكماً).
3. يتعين تدقيق واختبار هذا العزل جنائياً وإثبات:
   - خلو `init_data` بنسبة 100% من كافة الـ 187 متحكماً غير المصرح بها بعد تلقيم حزم حقيقية ومحاكاة كاملة تحوي الـ 226 متحكماً.
   - سلامة حفظ كافة المتحكمات المصرح بها الواردة دون تشويه أو فقد لمفاتيحها وهياكلها.
   - قياس نسبة التخفيض الفعلي في استهلاك الذاكرة (مقارنة حجم JSON وحجم RSS قبل وبعد الفلترة).
   - التأكد من عدم وجود تسريب ذاكرة أو نمو غير محدود للقواميس (`unbounded dictionary growth`) عند تكرار تلقيم الحزم والتحديثات الجزئية.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Audit Methodology & Steps)

1. **الخطوة الأولى: فحص الحزم الحقيقية وقواميس المتحكمات في ملفات `docs/*live_memory*.json`**:
   - قراءة وفحص ملفات الجلسات الحية:
     - `docs/burcudemr_live_memory.json`
     - `docs/jzarco.all_live_memory.json`
     - `docs/shook123_live_memory.json`
     - `docs/shook124_live_memory.json`
   - استخراج جميع أسماء المتحكمات الموجودة فعلياً في هذه الحزم وحصر ما إذا كانت تحتوي على الـ 226 متحكماً أو غيرها.
   - إعداد حمولة اختبار شاملة تضم كافة المتحكمات الـ 226 (المصرح بها والـ 187 غير المصرح بها) مع بيانات معيارية لاختبار الفلترة.

2. **الخطوة الثانية: فحص دقيق لآلية الفلترة داخل `core/live_memory.py` و `game_client.py`**:
   - اختبار `filter_whitelisted` و `extract_controllers` و `ingest_packet`.
   - تغذية الحمولات عبر محرك `LiveMemoryEngine` واختبار ما إذا كان أي متحكم غير مصرح به مثل:
     `chatCtrl`, `chatroomCtrl`, `RedPointCtrl`, `videoAdCtrl`, `flowerSysCtrl`, `clientLogCtrl`, `clientEventCtrl`, `voiceRoomCtrl`, `htMsgCtrl`, `marqueeCtrl`, `dressCtrl`, `rechargeCtrl`
     يتسرب إلى `init_data`.
   - التحقق من أن المتحكمات المصرح بها مثل:
     `cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`, `allianceCtrl`, `vipCtrl`, `buffCtrl`, `technologyCtrl`, etc.
     تُحفظ بكل مفاتيحها وهياكلها الداخلية دون أي تشويه.

3. **الخطوة الثالثة: القياس التجريبي لبصمة الذاكرة (Memory Footprint Reduction)**:
   - قياس حجم البيانات بتنسيق JSON (Serialization Size بالبايت) قبل الفلترة وبعد الفلترة.
   - قياس الحجم العميق للكائنات في بايثون (Deep Object Size عبر اجتياز العقد) قبل وبعد الفلترة.
   - قياس ذاكرة المعالجة الفعلية (RSS Memory) باستخدام `tracemalloc` و `psutil` على عينات ضخمة (100+ حساب ومئات آلاف الكائنات).
   - حساب نسبة الانخفاض المئوية الدقيقة.

4. **الخطوة الرابعة: فحص تسرب الذاكرة ونمو القواميس غير المحدود (Memory Leak & Bounded Growth Audit)**:
   - محاكاة تدفق 10,000 حزمة متتالية (تحديثات إشعارات، استجابات أوامر، وتحديثات متكررة لنفس المباني والأبطال).
   - مراقبة عدد المفاتيح في `init_data` و `cached_packets` و `local_queues_map`.
   - التحقق من تفعيل آلية السقف في `cached_packets` (سقف 64 حزمة) في `game_client.py:669-671`.
   - التحقق من ثبات حجم الذاكرة وتفعيل Copy-on-Write دون تسريب لمراجع قديمة أو تضاعف متكرر في القوائم.

5. **الخطوة الخامسة: توثيق النتائج النهائية وتصدير التقرير**:
   - كتابة تقرير الفحص الجنائي الكامل بالأدلة الخام في `e:\osmanli\.agents\teamwork\agent18_whitelist_audit\handoff.md`.

---

## 3. الأوامر والملفات والنتائج المتوقعة بالتفصيل

| رقم الخطوة | الأمر / السكريبت المنفذ | الملفات المستهدفة | النتيجة المتوقعة |
|---|---|---|---|
| 1 | تشغيل سكريبت فحص وتدقيق جنائي مستقل `scripts/audit_whitelist_memory.py` | `core/live_memory.py`, `docs/*live_memory*.json` | استخراج كافة المتحكمات والتحقق من سقوط 100% من المتحكمات الـ 187 المحظورة |
| 2 | قياس حجم الذاكرة و JSON serialization | كائنات الذاكرة الحية | إثبات انخفاض الذاكرة بنسبة >70-80% مقارنة بالحجم الخام |
| 3 | اختبار ضخ 10,000 حزمة دورية | `LiveMemoryEngine.ingest_packet` | ثبات الذاكرة واستقرار عدد العناصر دون تسريب أو نمو غير محدود |
| 4 | فحص تشغيل الاختبارات المؤتمتة `tests/test_live_memory.py` | `tests/test_live_memory.py` | نجاح كافة الاختبارات بنسبة 100% |

تم إعداد هذا التقرير مسبقاً التزاماً بالمعايير الصارمة لـ `GEMINI.md` قبل تنفيذ عمليات التدقيق والفحص.
