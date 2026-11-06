# Handoff Report — Reviewer 2 (Milestone 4: Memory & CPU Optimization - Requirement R3)

**تاريخ التقرير**: 2026-11-03  
**المحرر المسند**: Reviewer 2 (`reviewer_p2_m4_2` - Reviewer & Adversarial Critic)  
**وثيقة التكليف**: `e:\osmanli\.agents\teamwork\reviewer_p2_m4_2\DISPATCH.md`  
**الطلب الأصلي**: `ORIGINAL_REQUEST.md` (Requirement R3)  
**تسليم العامل المسند**: `e:\osmanli\.agents\teamwork\worker_p2_m4\handoff.md`  
**الحكم النهائي (Verdict)**: **APPROVE (معتمد بنجاح مع ملاحظات تحسين طرفية)**

---

## 1. Review Summary & Adversarial Evaluation

### Verdict: APPROVE

تم إجراء فحص دقيق ومستقل ومعادٍ (Adversarial Review) لجميع الجوانب المطلوبة في التكليف:
1. **دورة حياة الخيوط وعمليات الإيقاف (`_stop_and_join_bot`)**:
   - تأكيد أن استدعاء `t.join(timeout=timeout)` يتم **خارج** القفل العام `_lock` تماماً (`api_server.py:377-380`).
   - سلامة التزامن عند الاستدعاء المتزامن (Simultaneous Stop / Delete): استدعاءات `mgr.stop()` و `ev.set()` متسامحة ومكررة بأمان (Idempotent)، ودوال الحذف من القواميس تعتمد على `.pop(..., None)` و `.discard(...)` المانعة للأخطاء.
2. **كاش حالات المستخدم في WebSockets (`ws_user_status`)**:
   - عزل تام وسلامة تزامن ممتازة لكل اتصال WebSocket عبر مهمة استقبال منفصلة `disconnect_task`، مع كشف انقطاع لحظي (0ms) وإلغاء فوري في كتلة `finally:`.
   - رصد سلوك كاش القلاع: القلاع المضافة حديثاً قد تتأخر في الظهور عبر WebSocket القائم حتى 30 ثانية ما لم يتم تفريغ `_user_status_cache`، وهو ما تم توثيقه وتحديده بدقة كـ Finding غير مانع للاعتماد.
3. **تقليم السجلات بنظام التدفق المباشر (`prune_log_file_24h`)**:
   - معالجة صحيحة وسليمة تماماً للملفات الفارغة (`file_size == 0`).
   - معالجة النصوص متعددة البايت (UTF-8 Arabic): الانتقال عبر `f.readline()` بعد الـ `seek` يضمن عدم اقتطاع حروف UTF-8 لأن بايت السطر الجديد `\n` (`0x0A`) لا يتقاطع قطيعاً مع بايتات استكمال UTF-8.
   - الملفات الأصغر من سعة الحاجز (Buffer) تُقرأ من البايت 0 دون اقتطاع أو تلف.
4. **النزاهة والملفات المحظورة**:
   - لا توجد أي نتائج اختبار وهمية أو مزيفة أو تحايل برمجتي (Zero Integrity Violations).
   - التزام تام وحرفي بعدم فتح أو قراءة أو تعديل أو لمس الملفات المحظورة الثلاثة: `game_client.py`، `core/onemt_auth.py`، و `core/onemt_bot.py`.
5. **نتائج الاختبارات المستقلة**:
   - `python tests/test_memory_cpu_m4.py`: 5/5 PASS (0.238s).
   - `python tests/test_live_operations_m3.py`: 4/4 PASS (0.897s).
   - `python tests/run_all_tests.py`: 30/30 PASS (100.0%, 6.43s).

---

## 2. Findings (الملاحظات والنتائج التفصيلية)

### [Minor] Finding 1: عدم إبطال `_user_status_cache` عند إضافة قلعة جديدة عبر `/api/castles`
- **الموقع**: `api_server.py:1264-1328` (دالة `add_castle`).
- **المشكلة**: عند إضافة قلعة جديدة بواسطة مستخدم، لا يتم استدعاء `_user_status_cache.pop(uid, None)` ولا `_notify_user_status_change(uid)`. وبالتالي، في اتصال `ws_user_status` القائم للمستخدم، يستمر الكاش في استخدام قائمة المعرفات القديمة حتى انقضاء مهلة التزامن الدوري (30 ثانية).
- **الأثر**: المستخدم الذي يفتح المتصفح ويضيف قلعة جديدة، قد تتأخر حالة القلعة الجديدة في الظهور في شريط الحالات اللحظي عبر WebSocket لمدة تصل إلى 30 ثانية (ما لم يقم بتحديث الصفحة).
- **التوصية**: إضافة سطرين في نهاية `add_castle`:
  ```python
  with _lock:
      _user_status_cache.pop(uid, None)
  _notify_user_status_change(uid, castle_id)
  ```

### [Minor] Finding 2: اختلاف التوثيق عن التنفيذ في ذرية كتابة ملف السجل بـ `prune_log_file_24h`
- **الموقع**: `api_server.py:181` و `api_server.py:222-223`.
- **المشكلة**: يذكر التوثيق (Docstring) السطر 181: `- يستخدم استبدالاً ذرياً عبر ملف مؤقت لمنع تلف الملفات.` بينما التنفيذ في السطر 222 يفتح الملف مباشرة بوضع الكتابة `with open(file_path, "w", encoding="utf-8", errors="replace") as f:`.
- **الأثر**: الفتح المباشر بوضع `"w"` يفرغ الملف فوراً. إذا انقطع التيار أو حدث استثناء أثناء `writelines`، قد يفقد الملف محتواه مؤقتاً. كما قد يُصدر `PermissionError` على نظام Windows إذا كان الملف مفتوحاً للقراءة/الكتابة المتزامنة في معالج آخر.
- **التوصية**: الكتابة في ملف مؤقت `f"{file_path}.tmp"` ثم استبداله ذرياً عبر `os.replace`، أو الاحتفاظ بكتلة `try/except` الحالية التي تحمي السيرفر من التوقف.

### [Minor] Finding 3: سباق نظري نادر بين `_stop_and_join_bot` و `_start_bot_internal`
- **الموقع**: `api_server.py:350-410` و `api_server.py:2508-2538`.
- **المشكلة**: إذا كان خيط قلعة معينة يستغرق مهلة `join` كاملة (مثلاً 3 ثوانٍ)، وتزامن ذلك مع إرسال المستخدم طلب بدء تشغيل جديد لنفس القلعة (`start_bot`)، قد تقوم `_stop_and_join_bot` عند استيقاظها بمسح `_threads[castle_id]` الجديد الذي تم إنشاؤه للتو.
- **الأثر**: احتمال نظري ضئيل جداً لأن واجهة المستخدم تمنع النقر المزدوج وعمليات الإيقاف الطبيعية تستغرق أقل من 50 مللي ثانية.
- **التوصية**: في السطر 397 من `api_server.py`، استبدال `_threads.pop(castle_id, None)` بفحص تطابق الخيط:
  ```python
  if _threads.get(castle_id) == t:
      _threads.pop(castle_id, None)
  ```

---

## 3. Five-Component Handoff

### 1. Observation (الملاحظات الميدانية الموثقة)
- **فصل قفل الخيوط في `_stop_and_join_bot`**:
  ```python
  # api_server.py:358-380
  with _lock:
      ...
      t = _threads.get(castle_id)
  ...
  if t is not None and t.is_alive() and t != threading.current_thread():
      t.join(timeout=timeout)
  ```
  تم التحقق قطعاً من أن `t.join` يقع خارج كتلة `with _lock:` بالكامل.
- **عزل الخيوط العالقة في `_stalled_threads`**:
  ```python
  # api_server.py:384-393
  with _lock:
      _stalled_threads[castle_id] = {
          "thread": t,
          "ident": t.ident,
          ...
      }
  ```
  تم التحقق من خلال اختبار `test_stop_and_join_bot_timeout_and_stalled_quarantine` بأن الخيط الذي لا يستجيب للإيقاف يُنقل إلى `_stalled_threads` فور انقضاء المهلة.
- **تقليم السجلات بنظام `seek`**:
  ```python
  # api_server.py:195-200
  with open(file_path, "rb") as f:
      if file_size > tail_bytes:
          f.seek(file_size - tail_bytes)
          f.readline()
      for line_bytes in f:
          lines.append(line_bytes.decode("utf-8", errors="replace").replace("\r", ""))
  ```
  عندما يكون `file_size <= tail_bytes`، لا يتم طلب `seek` أو `readline`، مما يضمن قراءة الملفات الصغيرة كاملة بدون نقصان.
- **نتائج تشغيل أدوات التحقق**:
  - `python tests/test_memory_cpu_m4.py` -> `Ran 5 tests in 0.238s - OK`.
  - `python tests/test_live_operations_m3.py` -> `Ran 4 tests in 0.897s - OK`.
  - `python tests/run_all_tests.py` -> `30/30 PASS (100.0%) - Total Duration: 6.43s`.
- **حالة الملفات المحظورة**:
  - لم يتم فتح أو قراءة أو تعديل الملفات المحظورة الثلاثة: `game_client.py`، `core/onemt_auth.py`، و `core/onemt_bot.py`.

### 2. Logic Chain (تسلسل الاستدلال المنطقي)
1. من قراءة `api_server.py:350-410`، يتبين أن القفل العام `_lock` لا يُحتجز أثناء انتظار الخيوط (`join`)، مما يمنع تجمد مسارات معالجة الطلبات وتوقف الـ Event Loop.
2. استخدام `.pop(key, None)` و `.discard(key)` في خطوة التنظيف يجعل الدالة آمنة تماماً ضد التكرار (Idempotent) حتى عند استدعائها بالتزامن من عدة مسارات (مثل إيقاف القلعة وحذفها في نفس اللحظة).
3. في `bot_manager.py:3808`، استبدال حلقة الاستيقاظ الدوري بـ `await asyncio.wait_for(self._async_stop_event.wait(), timeout=remaining)` يخفض عدد استيقاظات المعالج من 1500 استيقاظ إلى صفر في الخمول، مع استجابة لحظية لأمر الإيقاف في زمن أقل من 100 مللي ثانية (تم التحقق في 20 مللي ثانية).
4. في `prune_log_file_24h`، القراءة بنظام البايت والتخلص من السطر الأول غير المكتمل عبر `f.readline()` يحل مشكلة اقتطاع حروف الـ UTF-8 متعددة البايت لأن بايت السطر الجديد `0x0A` فريد ومحمي في مواصفات UTF-8.
5. تمرير كافة الاختبارات القديمة والجديدة بنسبة 100% يثبت خلو الكود من أي انحدار (No Regressions) وتحقيق كافة معايير القبول لمتطلب R3.

### 3. Caveats (الافتراضات والحدود)
1. القلاع المضافة حديثاً أثناء فتح اتصال WebSocket للمستخدم قد تتأخر حتى 30 ثانية لتظهر في شريط الحالات ما لم يقم المستخدم بتحديث الصفحة (Finding 1).
2. كتابة ملف اللوق المقلّم تتم مباشرة عبر `open(..., "w")` بدلاً من الملف المؤقت الذري، ومحمية بـ `try/except` (Finding 2).
3. الاختبارات الميدانية نُفذت في بيئة اختبار محلية نقية ومعزولة بدون أي مساس ببيانات الإنتاج أو الاتصال بالسيرفر البعيد.

### 4. Conclusion (الخلاصة والقرار النهائي)
العمل المنجز من قبل Worker M4 يلبي بدقة متناهية متطلبات R3 من حيث:
- القضاء على تسريبات المراجع في القواميس العشرة.
- التنظيف المتماثل والحتمي لموارد الخيوط والبروكسي.
- التصفية الفورية لاتصالات WebSocket عند انقطاعها.
- خفض استهلاك المعالج وإلغاء الاستيقاظ المتكرر.
- تقليم السجلات بتدفق مباشر دون تحميلها بالكامل في الذاكرة.
- خلو التنفيذ من أي تزييف أو تحايل أو مساس بالملفات المحظورة.

**القرار النهائي: APPROVE (معتمد بنجاح).**

### 5. Verification Method (طريقة التحقق المستقل)
لإعادة التحقق من صحة هذا التقرير ونتائجه، يمكن تشغيل الأوامر التالية محلياً:

```powershell
# 1. اختبارات الذاكرة والمعالج R3 المباشرة
python tests/test_memory_cpu_m4.py

# 2. اختبارات دورة حياة العمليات الحية R2
python tests/test_live_operations_m3.py

# 3. جناح الاختبارات الشامل للمنصة (30 اختباراً)
python tests/run_all_tests.py
```
- **شروط الإبطال (Invalidation Conditions)**:
  - فشل أي اختبار من الاختبارات أعلاه.
  - حدوث أي تعديل على `game_client.py`, `core/onemt_auth.py`, أو `core/onemt_bot.py`.
  - بقاء خيوط عالقة دون تسجيلها في `_stalled_threads` أو تجميد السيرفر عند الإيقاف.
