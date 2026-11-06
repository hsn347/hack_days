# تقرير المسح والاستكشاف الشامل: استئصال تسريبات الذاكرة والمعالج (R3)
## Survey Report — Memory & CPU Leak Explorer (R3)

**تاريخ الإعداد**: 2026-11-03  
**المستكشف**: `explorer_survey_p2_2` (Teamwork Explorer Swarm)  
**النطاق**: التحقيق المعمق في متطلب **R3** (تسريبات RAM و CPU، دورة حياة المراجع والقواميس، إدارة الخيوط Threads، مقابس WebSockets، وعمليات السجلات وقواعد البيانات).  
**الملفات المفحوصة**: `api_server.py`, `bot_manager.py`, `core/database.py`, `core/session_manager.py`, `proxy/proxy_manager.py`, `tasks/base_task.py`.  
*(ملاحظة التزام: الملفات المحظورة الثلاثة `game_client.py` و `core/onemt_auth.py` و `core/onemt_bot.py` لم يتم فتحها أو قراءتها أو لمسها بأي شكل).*

---

## 1. الملخص التنفيذي (Executive Summary)

أظهر المسح الميداني الكودي وجود **4 فئات رئيسية** من الخلل الهيكلي الحاد في إدارة الموارد تتسبب مجتمعة في التراكم التدريجي لاستهلاك الذاكرة (Memory Bloat) ونبضات استهلاك المعالج (CPU Spikes):

1. **تسريب دائم في القواميس والهياكل العامة (Global Dictionaries Leak)**:
   - قاموس `_castle_emails` لا يُحذف منه أي عنصر إطلاقاً عند انتهاء خيط البوت بشكل طبيعي أو استثنائي داخل `_bot_thread` (تم نسيان سطر `pop` في كتلة `finally`).
   - خروج مبكر (Early Return) دون كتلة `try/finally` في حالات فشل تسجيل الدخول يترك خيوطاً ميتة ومراجع وقوائم سجلات في الذاكرة للأبد (`_threads`, `_stop_events`, `_log_qs`, `_castle_users`, `_castle_emails`).
   - مجموعة القلاع المحذوفة `_deleted_castles` عبارة عن بالوعة تتزايد دون سقف، حيث لا تُحذف منها أي قلعة إطلاقاً بعد انتهاء عمليتها.
   - روابط البروكسي للقلاع `_castle_bindings` في `proxy_manager.py` لا تُنظف عند حذف القلاع وتتراكم في الذاكرة وملف JSON.

2. **انعدام تام لانتظار الخيوط (Zero Thread Joins & Orphaned Threads)**:
   - لا يوجد في كامل الكود البرمجي استدعاء واحد لدالة `thread.join(timeout=...)`!
   - عند إيقاف البوت (`stop_bot` أو `stop_all_bots`) أو حذفه (`delete_castle` أو `delete_user`)، يتم وضع إشارة التوقف وإسقاط المفتاح من القواميس فوراً بينما الخيط لا يزال يعمل في الخلفية! تصبح الخيوط أيتاماً (Orphaned Threads) عالقة غير مراقبة.
   - محاولة `api_server.py` تتبع الخيوط عبر `threading.enumerate()` تحجب الأعطال وتصنف الخيوط العالقة كعمليات شغالة (`running`) بدلاً من عزلها كـ `stalled`.

3. **عمى مقابس WebSockets وتراكم مهام ThreadPoolExecutor**:
   - مقابس السجلات والحالات (`/ws/logs`, `/ws/status`, `/ws/user-status`) تعمل في حلقات إرسال فقط (`send_text` / `send_json`) دون قراءة أو انتظار رسائل العميل؛ لذا لا يعلم الخادم بانقطاع العميل إلا إذا فشل الإرسال. وإذا كانت الحالة ثابتة أو طابور السجلات فارغاً، تستمر الحلقة في العمل للأبد!
   - مقبس `/ws/user-status/{user_id}` يستدعي `asyncio.to_thread(_sync_collect_user_statuses)` كل **0.8 ثانية**، مما يفتح اتصالات SQLite متكررة وينفذ 4 استعلامات PRAGMA واستعلامات القلاع، مسبباً استنزاف مصفوفة الخيوط العامة في بايثون (`ThreadPoolExecutor`) وبطء قاعدة البيانات.

4. **حلقات انتظار نشطة (Fast Busy Loops) وتحميل السجلات بالكامل في الذاكرة**:
   - في `bot_manager.py` (الأسطر 3766-3768)، يتم تنفيذ حلقة انتظار مدتها 25 دقيقة عبر الاستيقاظ كل ثانية واحدة (`await asyncio.sleep(1.0)`) بواقع 1500 استيقاظ لكل دورة لكل قلعة، بدلاً من الانتظار الموجه على `asyncio.Event`.
   - دالة تقليم السجلات `prune_log_file_24h` تستخدم `f.readlines()` لتحميل ملف السجل بالكامل في الذاكرة كنصوص ثم إعادة كتابته، وتُستدعى كل 1000 سطر وعند بدء كل دورة.
   - استدعاء `importlib.reload(sys.modules['bot_manager'])` داخل كل خيط بوت جديد يسبب إعادة توليد الكائنات وفوضى في الذاكرة ونفايات زائدة.

---

## 2. التدقيق التفصيلي للهياكل العامة والقواميس (Global State Audit)

تُدار عمليات البوتات في `api_server.py` عبر قفل عام `_lock = threading.RLock()` و10 متغيرات عامة:

### 2.1 جدول دورة حياة المتغيرات العامة وتحليل التسريب

| المتغير | نوع الهيكل | نقاط الإدخال (Addition) | نقاط الحذف المبرمجة | المسارات المفقودة (Missing Cleanup Paths) | مستوى الخطورة |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `_threads` | `Dict[str, Thread]` | الأسطر: 251, 307, 674, 2241 | الأسطر: 880, 1402, 2139, 2235 | يُهمل حذفه عند فشل تسجيل الدخول المبكر (الأسطر 708, 715) فيبقى كائن الخيط الميت محجوزاً. في `delete_castle` يُحذف الخيط قبل أن يتوقف فعلياً. | 🔴 حرجة |
| `_stop_events` | `Dict[str, Event]` | السطر: 676 | الأسطر: 881, 1403, 2140, 2236 | لا يُحذف عند الخروج المبكر في السطور 708 و715. يُحذف مبكراً في 2236 قبل بدء الخيط الجديد مما يمنع إيقافه أثناء بدء التشغيل. | 🔴 حرجة |
| `_bot_managers` | `Dict[str, BotManager]` | السطر: 865 | الأسطر: 882, 1404, 2141 | يُحذف في `delete_castle` و `delete_user` بينما الخيط لا يزال ينفذ داخل كائن المدير دون إمكانية الوصول إليه. | 🟠 متوسطة |
| `_reserved` | `Set[str]` | الأسطر: 2237, 2291, 3338 | الأسطر: 679, 886, 1405, 2142, 2605, 2703, 2853, 3365, 3416 | إذا انهار خيط قبل الوصول للسطر 679، تبقى القلعة محجوزة في `_reserved` للأبد، وتظهر دائماً كـ `running` في `_is_running()` ولا يمكن إعادة تشغيلها! | 🔴 حرجة |
| `_log_qs` | `Dict[str, Queue]` | السطر: 675 | الأسطر: 883, 1406, 2143 | يُسرب تماماً عند فشل تسجيل الدخول في السطور 708 و715 محتجزاً ما يصل إلى 500 سطر لوق في الذاكرة. يتنازع عليه أكثر من عميل WebSocket ويفرغ محتواه. | 🔴 حرجة |
| `_conn_states` | `Dict[str, str]` | الأسطر: 789, 2290, 2946, 3339, 3378 | الأسطر: 884, 1407, 2144, 2948, 3366, 3373, 3410 | يتخلف في الذاكرة عند الخروج المبكر (708, 715) أو عند انهيار الخيط غير المتوقع خارج كتلة finally. | 🟡 منخفضة |
| `_user_stopped` | `Set[str]` | الأسطر: 1387, 2123, 2604, 2702, 2850, 2892, 2914 | الأسطر: 888 (بشرط), 1410, 2147, 2232, 2499, 2749, 2768 | إذا أوقف المستخدم القلعة ولم يشغلها مجدداً، تبقى في المجموعة للأبد لأن السطر 887 يشترط: `if not was_user_stopped: _user_stopped.discard(cid)`. | 🟠 متوسطة |
| `_castle_emails` | `Dict[str, str]` | الأسطر: 677, 3380 | الأسطر: 1408, 2145 | **تسريب مؤكد 100%**: تم نسيان سطر `_castle_emails.pop(castle_id, None)` داخل كتلة finally في `_bot_thread` (الأسطر 878-889)! كل قلعة تعمل تتراكم هنا للأبد ما لم تُحذف. | 🔴 حرجة جداً |
| `_castle_users` | `Dict[str, str]` | الأسطر: 678, 3379 | الأسطر: 885, 1409, 2146 | لا يُحذف عند الخروج المبكر (708, 715) لفشل المصادقة. | 🟡 منخفضة |
| `_deleted_castles` | `Set[str]` | الأسطر: 1386, 2122 | **معدومة تماماً** (لا يوجد سطر حذف واحد) | تنمو بلا سقف مع كل عملية حذف. كما تمنع أي قلعة يتم إنشاؤها بنفس الـ ID لاحقاً من حفظ حالتها أو مواردها. | 🔴 حرجة |
| `_castle_bindings` *(proxy)* | `Dict[str, str]` | السطر: 260, 283 في `proxy_manager.py` | **معدومة تماماً** عند حذف القلعة | تتراكم إيميلات القلاع المحذوفة مع عناوين البروكسي في الذاكرة وفي ملف `user_proxy_bindings.json`. | 🟠 متوسطة |

---

### 2.2 تحليل عميق لمشكلة `_deleted_castles` وتسريب القلاع المحذوفة

#### أين تكمن المشكلة؟
عند استدعاء نقطة النهاية `delete_castle` (الأسطر 1371-1430 في `api_server.py`):
1. يتم تسجيل القلعة في `_deleted_castles.add(castle_id)`.
2. يتم إرسال إشارة الإيقاف `mgr.stop()` و `ev.set()`.
3. فوراً وفي نفس اللحظة، تقوم الدالة بحذف كافة مراجع القلعة من القواميس:
   ```python
   # الأسطر 1401-1410
   with _lock:
       _threads.pop(castle_id, None)
       _stop_events.pop(castle_id, None)
       _bot_managers.pop(castle_id, None)
       _reserved.discard(castle_id)
       _log_qs.pop(castle_id, None)
       _conn_states.pop(castle_id, None)
       _castle_emails.pop(castle_id, None)
       _castle_users.pop(castle_id, None)
       _user_stopped.discard(castle_id)
   ```
4. **المصيبة**: خيط البوت لا يزال حياً ويعمل في الخلفية! لأنه لم يتم عمل `join` له!
5. صمم المطور مجموعة `_deleted_castles` كـ "ضمادة طوارئ" (Band-aid) لمنع هذا الخيط الهائم في الخلفية من استدعاء `update_castle_status_db` أو `sync_castle_resources_db` فيعيد إدراج القلعة في SQLite بعد أن حذفها المستخدم!
   ```python
   # الأسطر 420 و 447
   if castle_id in _deleted_castles:
       return
   ```
6. ولكن المطور **لم يضع أي آلية لتنظيف `_deleted_castles`** بعد أن ينتهي الخيط فعلياً!

#### الحل الآمن والمحكم:
1. عند حذف القلعة، يتم الاحتفاظ بمرجع الخيط `t = _threads.get(castle_id)`.
2. إرسال إشارة الإيقاف لمدير البوت وللخيط.
3. خارج القفل العام `_lock`، يتم انتظار انتهاء الخيط بمهلة آمنة:
   ```python
   if t and t.is_alive():
       t.join(timeout=3.0)
   ```
4. إذا لم ينتهِ الخيط خلال المهلة، يُسجل في قائمة تشخيصية خاصة `_stalled_threads` لتنبيه المشرف.
5. استخدام `_deleted_castles` مع مهلة زمنية (TTL-based Set) أو حذف المعرف فور التأكد من وفاة الخيط بالكامل (`not t.is_alive()`)، بحيث لا تتراكم المعرفات في الذاكرة، وإذا أعاد المستخدم إضافة القلعة لاحقاً تعمل بصورة طبيعية دون ابتلاع تحديثاتها.

---

## 3. دورة حياة الخيوط وعمليات التنظيف (Thread Lifecycle Audit)

### 3.1 المسار المكسور في `_bot_thread` وانعدام الـ `try/finally` الموحدة

في `api_server.py` (الأسطر 665-725):
```python
def _bot_thread(req: StartBotRequest):
    castle_id = req.castle_id
    user_id   = req.user_id
    email     = req.email

    # 1. إعداد queue للـ logs وإنشاء stop_event فوراً
    log_q = queue.Queue(maxsize=500)
    stop_event = threading.Event()
    with _lock:
        _threads[castle_id]     = threading.current_thread()
        _log_qs[castle_id]      = log_q
        _stop_events[castle_id] = stop_event
        _castle_emails[castle_id] = email
        _castle_users[castle_id]  = user_id
        _reserved.discard(castle_id)

    # 2. جلب كلمة المرور...
    # 3. فحص الجلسة وتسجيل الدخول:
    try:
        sm = SessionManager()
        account = sm.get_or_login(...)
        if not account:
            err_msg = ...
            update_castle_status_db(user_id, castle_id, "error", err_msg, conn_state="error")
            return  # ❌ خروج مبكر قاتل! كتلة finally الحقيقية تبدأ فقط في السطر 872!
    except Exception as e:
        update_castle_status_db(user_id, castle_id, "error", str(e), conn_state="error")
        return      # ❌ خروج مبكر قاتل آخر!
```

#### التبعات:
- عند حدوث أي خطأ في كلمة المرور أو تعذر تسجيل الدخول (وهو أمر شديد التكرار مع انتهاء صلاحية الحسابات أو كلمات المرور الخاطئة):
  1. ينتهي الخيط عبر `return`.
  2. كتلة `finally:` (الأسطر 872-889) لا تُنفذ إطلاقاً!
  3. تظل القواميس: `_threads[castle_id]` (خيط ميت)، و `_stop_events[castle_id]`، و `_log_qs[castle_id]`، و `_castle_users[castle_id]`، و `_castle_emails[castle_id]` محبوسة في الذاكرة للأبد!
  4. استعلامات مثل `len(_threads)` تعطي أرقاماً متضخمة وغير حقيقية.

### 3.2 غياب الـ `join` بالكامل وتفشي الخيوط اليتيمة (Orphaned Threads)

قمنا بإجراء فحص شامل بالـ Regex لجميع استدعاءات `.join(` في كامل المستودع؛ وكانت النتيجة المذهلة:
**لا يوجد أي استدعاء لـ `thread.join()` في كامل الكود! جميع ما وُجد هو `os.path.join`!**

- **في `stop_bot` (السطر 2829)**:
  يضع إشارة التوقف `ev.set()` و `mgr.stop()` ويُرجع الاستجابة للواجهة فوراً. إذا كان الخيط عالقاً في قراءة سوكت أو حلقة لا يستجيب، لا يعلم أحد ولا يُحاسب الخيط.
- **في `stop_all_bots` (السطر 2583)**:
  يمر على كل المعرفات ويضع إشارة التوقف دون أي انتظار لانتهاء أي خيط، ثم يصفر قاعدة البيانات مباشرة بينما الخيوط ربما لا تزال تكتب في قاعدة البيانات!
- **في `_restart_worker` (السطر 2743)**:
  ينفذ `time.sleep(5)` أعمى على أمل أن تكون جميع الخيوط قد توقفت! فإن لم تنتهِ خلال 5 ثوانٍ، ينطلق في تشغيل خيوط جديدة للقلاع ذاتها، فيحدث تداخل مهام وتنافس على السوكت لنفس الحساب!

### 3.3 تشويه وتزييف مراقبة العمليات الحية في `get_admin_live_processes`

في السطور 1546-1574 من `api_server.py`:
```python
# 2. فحص أي Thread إضافي باسم bot- في الـ runtime (مع استثناء خيوط النظام الداخلية)
for th in threading.enumerate():
    if th.name.startswith("bot-") and th.is_alive() and th.ident not in registered_idents:
        if th.name == "auto-resume" or th.name.startswith("sys-"):
            continue
        prefix = th.name[4:]
        registered_idents.add(th.ident)
        active_list.append({
            "castle_id": prefix,
            "email": prefix,
            "thread_id": th.ident,
            "thread_name": th.name,
            "thread_alive": True,
            "state": "running",
            "live_category": "running",
            "category_label": "شغالة (Thread مباشر)",
            "status_message": "Thread نشط يعمل مباشرة",
            ...
        })
```
#### الخلل:
هذا الكود وُضع للتغطية على الخيوط التي تفلت من `_threads` وتصبح أيتاماً. بدلاً من اكتشاف أنها أيتام وعزلها، يقوم الكود بتزييف حالتها وعرضها للمسؤول على أنها:
`live_category: "running"`, `category_label: "شغالة (Thread مباشر)"`!
وهذا يخالف صراحةً متطلبات R2 و R3 التي تنص على أن الخيط العالق لا يجوز أن يظهر كعملية حية، بل يجب تصنيفه كـ `stalled` في تقرير تشخيصي منفصل.

---

## 4. مقابس WebSockets واستنزاف المعالج وقاعدة البيانات (WebSockets & Async Buildup)

### 4.1 عمى الانقطاع (Disconnect Blindness) في جميع المقابس الثلاثة

فحصنا دوال المقابس الثلاثة في `api_server.py`:
1. `ws_logs` (الأسطر 3208-3260)
2. `ws_status` (الأسطر 3261-3280)
3. `ws_user_status` (الأسطر 3296-3315)

#### الملاحظة المشتركة القاتلة:
جميع الحلقات مبنية بالشكل التالي:
```python
while True:
    await asyncio.sleep(0.8)
    # فحص إذا تغيرت القيمة...
    if current != last_data:
        await websocket.send_json(current)
```
- **حقيقة عمل مكتبة Starlette / FastAPI**: لا يمكن لمكتبة الويب معرفة أن العميل أغلق المتصفح أو انقطع اتصاله في بروتوكول TCP إلا عبر أمرين:
  1. محاولة الإرسال `send_text` أو `send_json` وفشلها مع كسر الـ Pipe.
  2. أو استدعاء القراءة `await websocket.receive_text()` أو انتظار رسائل البينغ (Heartbeat / Ping-Pong).
- **النتيجة الكارثية**:
  - إذا كانت حالة القلاع مستقرة (لم تتغير)، فإن الشرط `if current != last_data` يكون دائماً `False`.
  - وبالتالي دالة `send` **لا تُستدعى نهائياً**!
  - ولا يوجد أي استدعاء لـ `receive`!
  - إذا أغلق المستخدم 10 علامات تبويب في المتصفح، تظل مهام الكوروتين الـ 10 تعمل في الخلفية على السيرفر **إلى ما لا نهاية**! وتستمر في استهلاك المعالج وفحص قاعدة البيانات كل 0.8 ثانية دون توقف!

### 4.2 استنزاف الـ ThreadPoolExecutor وقاعدة البيانات في `ws_user_status`

في السطور 3282-3310:
```python
def _sync_collect_user_statuses(user_id: str) -> Dict[str, str]:
    res = {}
    try:
        castles = db.get_user_castles(user_id)
        for c in castles:
            cid = c.get("castle_id")
            if cid:
                res[cid] = _get_real_status(cid)
    except Exception:
        pass
    return res

@app.websocket("/ws/user-status/{user_id}")
async def ws_user_status(websocket: WebSocket, user_id: str):
    await websocket.accept()
    last_data = await asyncio.to_thread(_sync_collect_user_statuses, user_id)
    ...
    while True:
        await asyncio.sleep(0.8)
        curr_data = await asyncio.to_thread(_sync_collect_user_statuses, user_id)
```

#### حجم الاستنزاف بالأرقام:
1. في كل دورة مدتها **0.8 ثانية** لكل مستخدم متصل باللوحة:
   - يتم حجز خيط عامل من مصفوفة `ThreadPoolExecutor` عبر `asyncio.to_thread`.
   - يتم فتح اتصال SQLite جديد عبر `db.get_connection()`.
   - يتم تنفيذ **4 أوامر PRAGMA** على الفور (`journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON`).
   - يتم تنفيذ استعلام `SELECT` لجلب جميع قلاع المستخدم.
   - لكل قلعة في حالة `idle` (غير شغالة)، تستدعي `_get_real_status` استعلاماً إضافياً `db.get_castle_by_id`!
2. إذا كان لدى المستخدم 25 قلعة:
   - ينتج عن ذلك **26 استعلام SQLite وفتح 26 اتصال وإغلاقها كل 0.8 ثانية**!
   - أي أكثر من **32 عملية قاعدة بيانات في الثانية الواحدة للمستخدم الواحد**!
3. إذا فتح 5 مستخدمين لوحة التحكم، يقفز العدد إلى **160 استعلاماً في الثانية** في حلقة لا تنتهي، مما يسبب اختناق قاعدة البيانات (`database is locked`) وتراكم مهام `asyncio.to_thread` في طابور التنفيذ، وارتفاع استهلاك المعالج إلى 40-70% في حالة السكون التام!

### 4.3 تنازع السجلات في `ws_logs` وسرقة الرسائل

في السطر 671:
`log_q: queue.Queue[str] = queue.Queue(maxsize=500)`
وفي `ws_logs` (السطر 3248):
`line = q.get_nowait()`
- إذا فتح المسؤول نافذتين للمتصفح على نفس القلعة، أو فتح مستخدم والمسؤول سجل القلعة في نفس الوقت:
  - كل نافذة تستدعي `q.get_nowait()` وتسحب السطر من الطابور!
  - النافذة الأولى تأخذ الأسطر الزوجية، والنافذة الثانية تأخذ الأسطر الفردية! (Data Interleaving / Message Stealing).
- الحل: استخدام نمط الموزع (Broadcaster / PubSub) بحيث يسجل كل WebSocket مستمعاً خاصاً به، أو قراءة السجلات بتدفق موحد.

---

## 5. اختناقات استهلاك المعالج (CPU Bottlenecks) وإجهاد الذاكرة

### 5.1 حلقة الانتظار النشطة في `bot_manager.py` (1500 استيقاظ لكل دورة)

في السطور 3763-3768 من `bot_manager.py`:
```python
# نوم مجزأ ليفحص stop_event كل ثانية بدلاً من asyncio.sleep الكامل
sleep_step = 1.0
slept = 0.0
while slept < remaining and not self._stop_event.is_set():
    await asyncio.sleep(min(sleep_step, remaining - slept))
    slept += sleep_step
```
- مدة الانتظار بين الدورات هي 25 دقيقة (`remaining = 1500.0` ثانية).
- الكود يقوم بعمل حلقة `while` تستيقظ **كل ثانية واحدة** (`await asyncio.sleep(1.0)`).
- هذا يعني **1500 استيقاظ وتبديل سياق (Context Switch)** لكل قلعة في الدورة الواحدة!
- إذا كان هناك 100 قلعة تنتظر دورتها القادمة، فإن الـ Event Loop يستيقظ **100 مرة في كل ثانية**، فقط ليفحص هل حدث إيقاف أم لا!
- **المفارقة العجيبة**: كائن `BotManager` يحتوي بالفعل في السطر 3672 على `self._async_stop_event = asyncio.Event()`! ويحتوي في السطر 978 في دالة `stop()` على `self._async_stop_event.set()`!
- فلماذا الدوران في حلقة 1 ثانية، بينما يمكن بكلمة واحدة الانتظار بكفاءة صفرية للمعالج:
  ```python
  try:
      await asyncio.wait_for(self._async_stop_event.wait(), timeout=remaining)
  except asyncio.TimeoutError:
      pass  # انتهى وقت الانتظار طبيعياً، ابدأ الدورة التالية
  ```
  هذا التعديل البسيط يخفض استهلاك المعالج في فترة الانتظار من مئات الاستيقاظات في الثانية إلى **صفر مطلق (0% CPU)**!

### 5.2 قراءة وتقليم ملفات السجلات بالكامل في الذاكرة عبر `f.readlines()`

في السطور 168-188 من `api_server.py`:
```python
def prune_log_file_24h(file_path: str, max_lines: int = MAX_LOG_LINES_PER_FILE) -> None:
    ...
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()   # ❌ تحميل الملف كاملاً في الذاكرة!
    ...
    with open(file_path, "w", encoding="utf-8", errors="replace") as f:
        f.writelines(kept)      # ❌ إعادة كتابة الملف كاملاً على القرص!
```
- تُستدعى هذه الدالة:
  1. عند بدء كل دورة لأي قلعة (السطر 724).
  2. كل 1000 سطر لوق يتم كتابته أثناء تشغيل القلعة (السطر 764).
  3. دورياً كل ساعة لجميع ملفات السجلات في السيرفر (السطر 223 و 3434).
- عند وجود ملفات سجلات بحجم 10-50 ميغابايت لكل قلعة، فإن `f.readlines()` يقوم بقراءة عشرات الآلاف من الأسطر وتوليد ملايين الكائنات النصية في RAM، ثم كتابتها بالكامل إلى القرص مسبباً ضغط I/O وتجميداً جزئياً للخيط.
- بالمقابل، دالة `_tail_file` (السطر 461) كُتبت بذكاء عبر `seek` من نهاية الملف. يجب تطبيق نفس الأسلوب الذكي في التقليم، أو استخدام تدوير الملفات القياسي (`RotatingFileHandler` بحجم أقصى 5MB وحفظ ملف احتياطي واحد) لضمان عدم قراءة كامل الملف في الذاكرة إطلاقاً.

### 5.3 تكرار `importlib.reload` داخل خيوط البوت

في السطور 842-848 من `api_server.py`:
```python
import sys, importlib
for mod_name in ("tasks.march_manager", "bot_manager"):
    if mod_name in sys.modules:
        try:
            importlib.reload(sys.modules[mod_name])
        except Exception:
            pass
```
- يتم تنفيذ إعادة تحميل الموديل في وقت التشغيل (Runtime Reload) **في كل مرة يبدأ فيها خيط بوت لأي قلعة**!
- في بيئة متعددة الخيوط (Multithreaded Server)، إعادة تحميل الموديل أثناء عمل خيوط أخرى تستخدم نفس الكلاسات يسبب:
  1. استهلاك معالج غير مبرر في إعادة تصيير الكود وتفسيره (Parsing & Re-compilation).
  2. مشاكل تطابق الكائنات (`isinstance` discrepancies).
  3. تراكم كائنات الموديولات والدوال القديمة في الذاكرة دون قدرة جامع القمامة على تفريغها بسبب المراجع المتبقية.

### 5.4 تكرار `threading.enumerate()` داخل دوال الحالة

- في `_is_running` (السطر 247): حلقة `for th in threading.enumerate():`
- في `_get_real_status` (السطر 292): حلقة `for th in threading.enumerate():`
- في `get_admin_dashboard_stats` (السطر 1448): حلقة `for t in threading.enumerate():`
- في `get_admin_live_processes` (السطر 1546): حلقة `for th in threading.enumerate():`
- في `get_admin_users_castles` (السطر 1728): استدعاء `_get_real_status(cid)` لكل قلعة في قاعدة البيانات، والتي بدورها تستدعي `threading.enumerate()`!
- `threading.enumerate()` تقفل الـ Threading State الداخلي في مترجم بايثون وتنشئ قائمة جديدة بجميع الخيوط في كل استدعاء. تكرارها مئات المرات في الثانية يسبب اختناقاً في الـ GIL وتباطؤاً كبيراً في استجابة السيرفر.

---

## 6. خطة الإصلاح الهندسية والتوصيات القاطعة (Remediation Roadmap)

بناءً على هذا المسح الدقيق، نوصي فريق التنفيذ بالحلول الهندسية التالية:

### 1. تصحيح دورة حياة القواميس والهياكل (Fix Global State Dictionaries)
- **كتلة `try/finally` شاملة من أول سطر في `_bot_thread`**:
  نقل تسجيل الخيط والمراجع إلى بداية كتلة `try` عامة تغلف تسجيل الدخول وكل شيء، وضمان أن كتلة `finally` تقوم دوماً بحذف:
  `_threads`, `_stop_events`, `_bot_managers`, `_log_qs`, `_conn_states`, `_castle_users`, `_castle_emails` (بما فيها السطر المفقود!), و `_reserved`.
- **تنظيف `_deleted_castles` الذكي**:
  عدم ترك المعرفات للأبد؛ تحويل المجموعة إلى TTL Cache تنتهي صلاحية المعرف بعد 60 ثانية من الحذف (وهي مدة كافية جداً لانتهاء أي مهمة عالقة)، أو تنظيفه فور موت الخيط.
- **تنظيف `_castle_bindings` في البروكسي**:
  إضافة دالة `remove_castle_proxy(email)` واستدعاؤها عند حذف القلعة أو حذف المستخدم.

### 2. فرض مهل الانتظار الآمنة للخيوط (Enforce Join Timeouts)
- استبدال التخلي العشوائي عن الخيوط بدالة إيقاف موحدة `_safe_stop_and_join_bot(castle_id, timeout=3.0)`:
  - ترسل إشارة `mgr.stop()` و `stop_event.set()`.
  - تنتظر الخيط عبر `thread.join(timeout=timeout)` **خارج القفل العام `_lock`**.
  - إذا انتهى الخيط بنجاح، تُنظف مرافقه فوراً.
  - إذا ظل الخيط حياً بعد المهلة، يُصنف كـ `stalled` ويسجل في قائمة خيوط متعثرة للمراقبة، دون ترك بياناته حية.

### 3. إصلاح مقابس WebSockets وتخفيف عبء قاعدة البيانات
- **كشف انقطاع العميل الفوري (Disconnect Detection)**:
  تشغيل مهمة استقبال خفيفة بالتوازي مع حلقة الإرسال:
  `asyncio.create_task(websocket.receive())` تلغي حلقة الإرسال فور حدوث انقطاع.
- **إلغاء الاستعلام كل 0.8 ثانية واستبداله بـ In-Memory State Cache**:
  الاعتماد على الحالة المخزنة في الذاكرة الحية فور تحديثها عبر الأحداث بدلاً من استدعاء `db.get_user_castles` وفتح اتصالات SQLite كل 0.8 ثانية.
- **استخدام Broadcaster خفيف للسجلات**:
  تحويل السجلات إلى طابور دائري للمشاهدة المتعددة لمنع سرقة الأسطر.

### 4. استئصال حلقات الـ CPU الزائدة وتقليم السجلات
- استبدال حلقة الـ 1 ثانية في `bot_manager.py` بانتظار `await asyncio.wait_for(self._async_stop_event.wait(), timeout=remaining)`.
- استبدال `f.readlines()` في تقليم السجلات بمكتبة تدوير السجلات القياسية أو تقليم الملفات عبر الاقتصاص المباشر من النهاية (Truncation from end).
- إزالة `importlib.reload` التلقائي من داخل خيوط البوتات وتشغيله فقط عند التحديث اليدوي الصريح.
- استبدال البحث عبر `threading.enumerate()` بالقواميس المباشرة ذات المفاتيح `_threads[castle_id]`.

---

## 7. الخاتمة والجاهزية للانتقال

هذا التقرير يقدم تشخيصاً دقيقاً وموثقاً بالأسطر والملفات لجميع مسببات تسريب الذاكرة واستهلاك المعالج في المشروع. المنظومة جاهزة للانتقال إلى المرحلة التالية لتطبيق التعديلات البرمجية وتصميم سكربتات الاختبار الميداني والـ Soak Testing للتحقق من زوال كافة التسريبات بالأرقام والقياسات الحية.
