# تقرير فني مستقل: دمج بوابة جاهزية الذاكرة الصارمة في دورة حياة البوت (bot_manager.py)
**Technical Architecture & Implementation Report: Bot Loop Readiness Gate Integration**

- **التاريخ**: 2026-11-09T13:42:00Z
- **الوكيل المسند**: Worker: Bot Loop Integration Engineer (Agent 10)
- **الملف المستهدف حصراً**: `bot_manager.py`
- **المرجعيات**: `ORIGINAL_REQUEST.md`, `LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md`, `GEMINI.md` (خاصة القاعدة 4 و 5 و 6 و 7)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostic & Root Cause)

1. **الخلل السابق**:
   كانت دورة البوت في `bot_manager.py` تبدأ فور حدوث الاتصال والمصافحة وتلقي أي حزمة أولية (`len(init_data) > 0`)، دون التأكد الفعلي من اكتمال كافة المتحكمات الحيوية الستة (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`) ولا اكتمال بياناتها الهيكلية الداخلية (مثل `blist` للمباني و `reslist` للموارد في `cityCtrl`).
2. **الآثار السلبية للبدء المبكر**:
   - انهيار المهام بأخطاء استثنائية (`KeyError`) عند محاولة قراءة مبانٍ أو جنود لم تصل بياناتهم بعد.
   - اتخاذ قرارات خاطئة (مثل قراءة موارد القلعة كأصفار أو اعتبار طوابير البناء ممتلئة).
   - تخطي مهام حرجة (مثل الأبحاث أو التدريب) لعدم ظهور المباني المقابلة في الذاكرة الحية.
3. **أهمية بوابة الجاهزية (`wait_for_memory_ready`)**:
   تضمن الدالة غير المتزامنة `await self.conn.wait_for_memory_ready(timeout=30.0, auto_fetch_missing=True)` فحص اكتمال كافة المتحكمات الحرجة وإرسال استعلامات تعويضية تلقائية (`Fallback Sync Queries`) للمتحكمات الناقصة. إذا لم تكتمل الذاكرة الحية خلال المهلة المحددة، يتم تعليق تشغيل المهام للدورة القادمة لحماية الحساب ومنع السلوكيات الشاذة.
4. **العزل الجذري لمهمة العفريت (`GEMINI.md Rule 7`)**:
   يجب أن تعمل مهمة نخبة العفريت `ElfBossTask` كبوت مستقل ذي أولوية قصوى يتجاوز المهام العادية ولا يمر مطلقاً عبر `march_manager`، مع استفادة العفريت أيضاً من جاهزية الذاكرة الحية قبل مباشرة استعلاماته وهجماته.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Implementation Logic & Architecture)

1. **إضافة دالة المساعد الموحدة للتسجيل `_log`**:
   إضافة دالة `_log(self, message: str) -> None` داخل كلاس `BotManager` لتوحيد إرسال السجلات إلى `log.info` و `self._log_callback` و `sys.stdout`.
2. **دمج بوابة الجاهزية الصارمة في `execute_task_pipeline()`**:
   في بداية دالة تنفيذ سلسلة المهام:
   ```python
   # فحص بوابة جاهزية الذاكرة الصارمة قبل بدء تنفيذ أي مهمة
   if self.conn and hasattr(self.conn, "wait_for_memory_ready"):
       is_ready = await self.conn.wait_for_memory_ready(timeout=30.0, auto_fetch_missing=True)
       if not is_ready:
           self._log("⚠️ الذاكرة الحية غير مكتملة، تعليق تشغيل المهام للدورة القادمة...")
           return results
   ```
3. **توفير الاسم المستعار `_run_task_pipeline`**:
   تعريف `_run_task_pipeline = execute_task_pipeline` على كلاس `BotManager` لضمان التوافقية الكاملة والقطعية مع أي اختبارات أو نداءات خارجية.
4. **دمج بوابة الجاهزية في وضع بوت العفريت المستقل `run_elf_boss_mode()`**:
   قبل فحص طاقة اللورد أو سريان الحدث في `run_elf_boss_mode()`، إذا كانت مهمة العفريت مفعلة في `self.config['elf']`، يتم استدعاء `wait_for_memory_ready` لضمان اكتمال بيانات اللورد والفعاليات قبل اتخاذ أي قرار، مع الحفاظ التام والقطعي على عزل العفريت عن `march_manager`.
5. **التحقق من العزل الجذري للعفريت عن `march_manager` (Rule 7)**:
   - التأكد من أن `ElfBossTask` لا يتم استدعاؤه داخل `step_23_march_manager_task`.
   - التأكد من عدم وجود أي ربط بين إعدادات `elf` وإعدادات `march_manager.combat.choice`.
   - التأكد من تشغيل العفريت كوضع ذي أولوية يقفز قبل `execute_task_pipeline`.

---

## 3. الملفات والسطور والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة

| الملف | الموقع التقريبي | التعديل البرمجي | النتيجة المتوقعة |
|---|---|---|---|
| `bot_manager.py` | بعد أسطر `get_lord_stamina` (حوالي سطر 978) | إضافة `def _log(self, message: str) -> None` | توفير واجهة موحدة ونظيفة لبث السجلات |
| `bot_manager.py` | في بداية `execute_task_pipeline` (حوالي سطر 1598) | استدعاء `await self.conn.wait_for_memory_ready(...)` وفحص النتيجة | حظر تشغيل المهام إذا كانت الذاكرة الحية غير مكتملة بنسبة 100% |
| `bot_manager.py` | بعد دالة `execute_task_pipeline` (حوالي سطر 1792) | تعيين الاسم المستعار `_run_task_pipeline = execute_task_pipeline` | ضمان التوافقية البرمجية مع متطلبات التعيين |
| `bot_manager.py` | في `run_elf_boss_mode` (حوالي سطر 3051) | استدعاء `await self.conn.wait_for_memory_ready(...)` بعد التحقق من `elf.enabled` | تزويد مهمة العفريت المستقلة بنفس حماية بوابة الجاهزية |

### أوامر الفحص والتحقق المتوقعة:
1. `python -m py_compile bot_manager.py`
   - **النتيجة المتوقعة**: كود خروج 0 (خالٍ تماماً من أي أخطاء لغوية أو استيراد).
2. تشغيل فحص بايثون داخلي للتأكد من وجود الدالة وتكامل الواجهة دون أخطاء:
   `python -c "import bot_manager; print('Import successful')"`
   - **النتيجة المتوقعة**: استيراد ناجح 100%.
