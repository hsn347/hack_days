Use a very large team of agents (سرب إلزامي من 20 وكيلاً على الأقل: 10 وكلاء هندسة وتنفيذ مستمرين بدون توقف حتى إغلاق كافة الثغرات + 10 وكلاء مخصصين للتجربة الفعلية الحية والتحقق الميداني). هندسة ومزامنة الذاكرة الحية (Live State Memory) في البوت بالاعتماد على ملفات اللعبة المرجعية، مع قائمة بيضاء للمتحكمات وبوابة جاهزية صارمة لمنع بدء المهام قبل اكتمال البيانات.

Working directory: e:\osmanli
Integrity mode: development

## Reference Material

- ملفات كود اللعبة المرجعية في `e:\osmanli\game file` (خاصة `lua_src/src/src/app/module/city/cityCtrl.lua` وباقي ملفات `*Ctrl.lua` وإشعارات `notifyCtrl.lua`).

## Verification Resources

- ملفات كود اللعبة المرجعية في `e:\osmanli\game file\lua_src`.
- كود البوت الحالي في `game_client.py` و `bot_manager.py` وملفات `tasks/`.
- جلسات الحسابات الحقيقية في `session_cache.json` لإجراء التجربة الفعلية الحية على السيرفر، بالإضافة إلى حزم محاكاة مطابقة لمنطق ملفات اللعبة.

## Requirements

### R0. هيكلة سرب الوكلاء الـ 20 وقواعد الاستمرارية (Mandatory 20-Agent Swarm Architecture)

- يُمنع تنفيذ المهمة بشكل أحادي أو التوقف قبل اكتمال كافة المتطلبات واجتياز التجارب الفعلية بنسبة 100%. يجب تقسيم العمل فعلياً على **20 وكيلاً على الأقل** وفق التوزيع الإلزامي التالي:
  - **الفريق الأول: 10 وكلاء هندسة وتنفيذ مستمرين (Persistent Core & Sync Engineers - لا يتوقفون حتى انتهاء المهمة):**
    1. **وكيل تحليل بروتوكول Lua (`Lua Protocol & Notify Analyst`):** يفحص `cityCtrl.lua` و `notifyCtrl.lua` وكافة ملفات `*Ctrl.lua` لاستخراج جميع معرفات الإشعارات (`gNotifyID`) وهياكل البيانات (`retdata` و `notifyData`).
    2. **وكيل فحص المهام والقائمة البيضاء (`Task Scanner & Whitelist Architect`):** يمسح كافة ملفات `tasks/` و `bot_manager.py` لحصر المتحكمات التي يقرأها البوت فعلياً وبناء قوائم الفلترة.
    3. **وكيل هندسة بوابة الجاهزية (`Memory Readiness Gatekeeper`):** يبني نظام الانتظار غير المتزامن (`wait_for_memory_ready`) وآلية الاستعلام التعويضي (`Fallback Sync Query`).
    4. **وكيل مزامنة المدينة والمباني والموارد (`City & Building State Engineer`):** يطابق منطق `cityCtrl.lua` بالكامل داخل بايثون (`blist`, `reslist`, `saferes`, `dayMaxRes`, `updateUnCollectRes`, `openChargeQueue`).
    5. **وكيل مزامنة الطوابير وحالات البناء (`Queues & Build Lifecycle Engineer`):** يربط `NOTIFY_QUEUE` و `NOTIFY_LOCAL_QUEUE_SYNC` بـ `queueCtrl` و `local_queues_map`، ويحدث حالة ومستوى المبنى في `cityCtrl` فور انتهاء الطابور أو إلغائه (`BUILD_STATE.NORMAL` ورفع `lv` أو `honorLv`).
    6. **وكيل مزامنة الجيوش والأبطال واللورد (`Army, Hero & Lord Sync Engineer`):** يوحد تحديثات `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, و `buffCtrl`.
    7. **وكيل مزامنة الحقيبة والمهام والميناء (`Backpack, Tasks & Harbor Sync Engineer`):** يعالج تحديثات `backpackCtrl` (`add`/`use`), `meritoriousTaskCtrl`, و `timeRewardCtrl` (سفن الميناء).
    8. **وكيل محرك الدمج العميق الذكي (`Smart Deep-Merge Engine Architect`):** يطور خوارزمية الدمج المركزي التي تحدث القوائم ذات المعرفات (`blist` عبر `index` أو `bid/iid`، و `heroes` و `buffCtrl` عبر `id`) دون مسح أو تكرار.
    9. **وكيل تنظيف الذاكرة وإلغاء العشوائية (`Memory Hygiene & Dispatch Refactor Agent`):** يزيل التحديثات العشوائية وتراكم `cached_packets` في `game_client.py` ويجعل التحديث لحظياً فور وصول الحزمة في `_dispatch`.
    10. **وكيل تكامل حلقة البوت (`Bot Loop Integration Engineer`):** يربط بوابة الجاهزية والذاكرة الحية بدورة حياة البوت في `bot_manager.py` والمهام دون المساس بالمهام المعزولة.
  - **الفريق الثاني: 10 وكلاء مخصصين للتجربة الفعلية والتأكد الميداني (Live Verification & Real Testing Agents):** 11. **وكيل التجربة الحية للاتصال والتهيئة (`Live Connection & Init Tester`):** يشغل اتصالاً فعلياً بحساب حقيقي من `session_cache.json` ويتأكد من تدفق حزم التهيئة وملء الذاكرة الحية. 12. **وكيل التجربة الفعلية لبوابة الجاهزية (`Live Gate & Fallback Tester`):** يختبر فعلياً توقف دورة البوت عند نقص أي متحكم في `CRITICAL_STARTUP_CONTROLLERS` ونجاح `auto_fetch_missing` في جلبه من السيرفر. 13. **وكيل التجربة الحية لإشعارات السيرفر (`Live Socket Spy & Notify Verifier`):** يراقب الحزم الواردة فعلياً من مقبس اللعبة (`S2C`) ويتحقق من انعكاس كل إشعار في `init_data` في نفس اللحظة. 14. **وكيل اختبار تطابق المدينة والموارد (`City & Resource Delta QA Agent`):** يختبر عملياً تحديثات `NOTIFY_CITY` (الموارد، الموارد الآمنة، الحد اليومي، الموارد غير المجموعة، الطابور الإضافي). 15. **وكيل اختبار دورة حياة المباني والطوابير (`Building Upgrade & Queue End QA Agent`):** يختبر بدء وانتهاء/إلغاء ترقية مبنى وتحول حالته ومستواه في `cityCtrl` و `queueCtrl`. 16. **وكيل اختبار المسيرات والجيوش (`Marches & Army Live QA Agent`):** يختبر تحديثات `local_queues` و `armyCtrl` عند تغير حالة الفيالق. 17. **وكيل اختبار الحقيبة والأبطال واللورد (`Backpack, Hero & Lord QA Agent`):** يتحقق عملياً من دقة حساب الإضافة والخصم (`add`/`use`) في الحقيبة وتحديثات الأبطال واللورد. 18. **وكيل فحص العزل والقائمة البيضاء (`Whitelist & Memory Footprint Auditor`):** يفحص الذاكرة الحية بعد الاتصال الفعلي ليثبت عدم تسرب أي متحكم من خارج `ALLOWED_CONTROLLERS`. 19. **وكيل اختبار الضغط والتزامن (`Concurrency & Deep-Merge Stress Tester`):** يضخ سيلاً متزامناً من الحزم والإشعارات للتحقق من عدم حدوث Race Conditions أو تكرار للعناصر داخل القوائم. 20. **وكيل الاعتماد النهائي وإغلاق المهمة (`Chief QA Sign-off Agent`):** يراجع مخرجات الـ 19 وكيلاً، ويمنع إنهاء المهمة إذا فشل أي اختبار حي أو محاكى، ويعيد أي خلل للفريق الأول لإصلاحه فوراً.

### R1. نظام القائمة البيضاء للمتحكمات (Controller Whitelisting)

- حصر المتحكمات التي يستخدمها البوت فعلياً في قائمة `ALLOWED_CONTROLLERS`، وتجاهل واستبعاد أي متحكم خارجها فور استلام حزم `retdata` أو `data` لتوفير الذاكرة ومنع التضخم.
- تحديد قائمة `CRITICAL_STARTUP_CONTROLLERS` للمتحكمات الأساسية الإلزامية التي يجب أن تكتمل في الذاكرة الحية قبل السماح لدورة البوت ببدء تنفيذ أي مهام.

### R2. محرك الذاكرة الحية الموحد (LiveMemoryEngine)

- استبدال المعالجة العشوائية في `_dispatch` و `check_and_merge_controller` بمحرك توجيه مركزي يعترض كافة حزم السيرفر الواردة (`retdata`, `data`, `notifyData`) ويدمجها لحظياً (`Smart Deep Merge`) مع الحفاظ على القوائم ذات المعرفات (مثل `blist` للمباني عبر `index`، و `heroes` و `buffCtrl` عبر `id`) دون مسح أو تكرار.
- ربط شامل لكافة الإشعارات الخاصة بالمتحكمات المعتمدة استناداً إلى منطق `lua_src`، وعلى رأسها:
  - إشعار `NOTIFY_CITY`: لتحديث `reslist`، خصم/إضافة `res`، `saferes`، `dayMaxRes`، `updateUnCollectRes` لكل مبنى عبر `index`، و `openChargeQueue`.
  - إشعار `NOTIFY_QUEUE` و `NOTIFY_PLAYER_QUEUE_CHANGE`: لتحديث `queueCtrl` وعكس انتهاء أو إلغاء طابور البناء مباشرة على حالة المبنى (`state`) ومستواه (`lv` / `honorLv`) في `cityCtrl` تماماً كما يفعل `buildQueueCallback` في `cityCtrl.lua`.

### R3. بوابة جاهزية الذاكرة الصارمة (Strict Memory Readiness Gate)

- إضافة آلية غير متزامنة `await conn.wait_for_memory_ready(timeout=30, auto_fetch_missing=True)` تتحقق من وجود كافة متحكمات `CRITICAL_STARTUP_CONTROLLERS` في `init_data` واكتمال بياناتها الداخلية الهيكلية (مثل التأكد من وجود `blist` و `reslist` غير فارغين في `cityCtrl`).
- إرسال استعلام تعويضي تلقائي (`Fallback Sync Query`) لكل متحكم ناقص في حال تأخر السيرفر في إرساله بعد التهيئة الأولية (`_init_flow`).
- ربط البوابة ببداية دورة البوت الرئيسية في `bot_manager.py` لمنع تنفيذ أي مهمة قبل تحقق اكتمال الذاكرة بنسبة 100%.

### R4. ضوابط التنفيذ الصارمة وبيئة العمل

- تنفيذ كافة التعديلات محلياً فقط داخل `e:\osmanli`، ويُمنع منعاً باتاً ومطلقاً أي رفع للسيرفر الخارجي أو تشغيل عمليات نشر.
- التعديل على ملفات الكود يتم حصراً باستخدام أدوات التحرير المباشرة، ويُحظر استخدام سكريبتات بايثون لتعديل الكود.
- إنشاء ملف تقرير فني مستقل (`.md Artifact`) يسبق أي تعديل على الملفات، مع الحفاظ على العزل التام للمهام المستقلة (مثل مهمة العفريت `elf`).

## Acceptance Criteria

### التحقق الوظيفي والتجربة الفعلية الحية (Live & Automated Verification)

- [ ] تشغيل الـ 20 وكيلاً بالتوزيع المحدد (10 تنفيذ مستمر + 10 تجربة فعلية وتحقق) وتوثيق نتائجهم.
- [ ] استبعاد أي متحكم غير مدرج في `ALLOWED_CONTROLLERS` والتأكد فعلياً من عدم تسربه إلى `init_data`.
- [ ] إثبات تحديث `cityCtrl` بكافة الحقول المتأثرة بإشعار `NOTIFY_CITY` (`res`, `reslist`, `saferes`, `dayMaxRes`, `updateUnCollectRes`, `openChargeQueue`) وتحديث حالة ومستوى المباني عند انتهاء طابور البناء.
- [ ] إثبات صحة دمج القوائم ذات المعرفات عبر `Smart Deep Merge` دون تكرار أو مسح للبيانات عند تدفق تحديثات متزامنة.
- [ ] التحقق العملي من توقف دورة البوت وعدم بدء أي مهمة إذا كانت متحكمات `CRITICAL_STARTUP_CONTROLLERS` ناقصة، ونجاح استكمالها تلقائياً عبر الاستعلام التعويضي (`Fallback Sync Query`).
- [ ] إجراء **تجربة اتصال فعلية حية** على حساب من `session_cache.json` بالإضافة إلى اجتياز مجموعة اختبارات برمجية مؤتمتة شاملة (Unit & Integration Tests) تثبت بالأرقام والسجلات سلامة الذاكرة الحية بنسبة 100%.
