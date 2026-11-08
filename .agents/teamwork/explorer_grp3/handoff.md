# تقرير التسليم النهائي (Handoff Report) — explorer_grp3
## تشريح مهام الأطلال (`ruins.py`) والجمع (`gather.py`) وجمع الذهب (`gold_gather.py`)

---

### 1. الملاحظات المباشرة (Observation)
تم فحص الكود المصدري للملفات الثلاثة في مجلد `tasks/` سطراً بسطر ودالة بدالة ومساراً بشرط (`if/elif/else`):
- `tasks/ruins.py`: 961 سطراً، فئة `RuinsTask(BaseTask)`.
  - أوامر الشبكة المنفذة: `2011/3` (البحث على الخريطة mapType: 7, subType: 0)، `1007/2` (إرسال مسيرة moveLineType: 4, matrixType: 1)، `1006/25` (استعلام إحداثيات القلعة)، `1006/15` (استعلام عمر الطلل leftTime)، `1005/1` (استعلام القوات الاحتياطي)، `1005/7` (استعلام التشكيلة المحفوظة الاحتياطي).
  - مفاتيح الذاكرة الحية (`init_data`): `cityCtrl.cinfo.pos`، `lordInfoCtrl.base.partition`، `armyCtrl.totalArmy`، `armyCtrl.compileHeros`، `armyCtrl.compilePets`، `armyCtrl.compileRunePages`، `armyCtrl.compileArmy`، `heroCtrl`.
  - إدارة الاستبعاد: `ExcludeManager` عبر `reserve(uid, target_id, kingdom_id)` ثم `confirm` عند النجاح أو `release` عند الفشل.
- `tasks/gather.py`: 1323 سطراً، فئة `GatherTask(BaseTask)`.
  - أوامر الشبكة: `2011/3` (البحث عن الموارد mapType: 5, subType: 1..5)، `1007/2` (إرسال مسيرة moveLineType: 3, matrixType: 3)، `1006/22` (فحص الهدف الميداني)، `1006/1000` (مزامنة الخريطة)، إشعارات `1009/201` (`NOTIFY_MAP_SYNC`)، `1006/15`، `1019/6` (سمة P_LOAD)، `1006/25`، `1005/1`.
  - مفاتيح الذاكرة الحية: `cityCtrl`، `lordInfoCtrl`، `armyCtrl`، `heroCtrl`، `petCtrl.pets`، `technologyCtrl` (أبحاث 22001 و 22010)، `lordSkillCtrl` (مهارة 11001)، `vipCtrl.vipLv`، `equipmentCtrl` (أحذية 6520000 بحساب التعزيز والصقل)، `buffCtrl`، `boeAttributeCtrl['1']['1']['11']['1']`.
  - إدارة الاستبعاد: `ExcludeManager` مع `reserve` و `confirm` و `release`.
- `tasks/gold_gather.py`: 1504 سطراً، فئة `GoldGatherTask(BaseTask)`.
  - أوامر الشبكة: `2011/3`، `1007/2`، `1006/22`، `1006/1000`، `1009/201`، `1002/7`.
  - مفاتيح الذاكرة الحية: `lordInfoCtrl`، `armyCtrl`، `heroCtrl`، `petCtrl`، `boeAttributeCtrl`.
  - إدارة الاستبعاد: ملف محلي منفصل تماماً `database/shared_gather_history.json` ودوال `record_shared_target` و `get_active_shared_history` دون استخدام `ExcludeManager` ودون أقفال خيوط `threading.Lock`.

---

### 2. سلسلة الاستدلال والمنطق البرمجي (Logic Chain)
1. **الازدواجية والنسخ الحرفي**:
   - دالة `select_gathering_pet` في `gold_gather.py` منسوخة حرفياً بالكربون من `gather.py`.
   - دالة `_is_tile_locked` في `gold_gather.py` (170 سطراً) تعيد كتابة نفس منطق `check_target_busy_or_marched` الموجود في `base_task.py`.
   - دوال اختيار أبطال الجمع والحرب موزعة ومنسوخة في 4 أماكن مختلفة.
2. **الثغرات الحرجة المكتشفة (Red Team Findings)**:
   - **انشقاق إدارة الاستبعاد**: `gold_gather.py` لا يستخدم `ExcludeManager` المركزي، ويكتب في ملفه المنفصل بدون قفل، مما يسبب تسابقاً برمجياً (Race Conditions) وتلف البيانات عند تشغيل عدة حسابات.
   - **كارثة اصطياد النطاق 8000-8099 في `ruins.py`**: السطر 877 يعتبر أي خطأ بين 8000 و 8099 (بما فيها أخطاء انشغال الأبطال 8014 أو الحيوانات 8015 أو متطلبات القلعة 8041) انشغالاً للهدف ويستدعي `confirm`، مما يحرق الأطلال ويستبعدها 4 ساعات عن بقية الحسابات.
   - **إسقاط كود `CASTLE_LV_LOW` في `gather.py`**: تعيد الدالة الفرعية `CASTLE_LV_LOW` عند نقص مستوى القلعة، ولكن حلقة `run()` تسقطها في `else` وتكرر المحاولات الفاشلة.
   - **تطابق ثوابت الموارد في `gold_gather.py`**: السطران 67-68 يعرفان `SUBTYPE_GOLD = 1` و `SUBTYPE_MITHRIL = 1`، مما يعطل مسح مناجم الذهب العادية ذات الكود 5 في النمط التلقائي.
   - **تباين معالجة خطأ السعة `8035`**: تعالجه `ruins.py` بتقليص 82% ثم 75%، وتعالجه `gather.py` بتقليص 85% ثم 85%، بينما تهرب منه `gold_gather.py` فورياً وتعيد `ERROR` دون أي محاولة ثانية.

---

### 3. التحفظات والافتراضات (Caveats)
- تم فحص الكود المصدري محلياً وبشكل قراءة فقط (Read-Only) تنفيذاً لتعليمات المستخدم الصارمة في `GEMINI.md`.
- لم يتم إجراء تعديلات على الكود المصدري؛ كافة التوصيات الهندسية وخريطة Before & After موثقة في ملف التحليل `analysis.md`.
- ملفات رايات التحالف (`flags_*.json`) تعتمد على وجود ملفات مهيأة مسبقاً، وإذا غابت يسقط النظام للمسح الدائري البسيط.

---

### 4. الخلاصة الهندسية والتوصيات (Conclusion)
- المهام الثلاث تعاني من تشظي معماري حاد وتكرار يزيد عن 60% من حجم الأكواد، مع وجود ثغرات أمنية وتشغيلية تسبب تجويع الأهداف وتصادم المسيرات.
- تم وضع المخطط الهندسي الكامل لتوحيد الدوال في `base_task.py`:
  1. `select_heroes_for_task(purpose="combat"|"gather")`
  2. `select_best_pet()`
  3. `build_march_army(purpose="combat"|"gather")`
  4. `verify_target_safe_and_clear()`
  5. `dispatch_march_with_retry(payload, retry_on_8035=True)`
- التقرير الكامل المحتوي على كافة الجداول والتتبع السطري المفصل محفوظ في:
  `e:\osmanli\.agents\teamwork\explorer_grp3\analysis.md`.

---

### 5. طريقة التحقق المستقلة (Verification Method)
- فحص قراءة ملف التحليل:
  `read_file` على `e:\osmanli\.agents\teamwork\explorer_grp3\analysis.md`.
- التحقق من تغطية الأكواد الـ 20 كاملة في الجداول والمقارنات.
- تشغيل أداة التحقق البرمجية إن لزم:
  التحقق من خلو التقرير من أي عبارات تلخيص مخلة أو "إلخ" ومطابقة كافة المتطلبات الصارمة في `ORIGINAL_REQUEST.md`.
