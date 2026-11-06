# تقرير خطة التنفيذ الفنية — المرحلة 4 (التكرار 2)
## Technical Implementation Plan & Diagnostic Report: Milestone 4 (Iteration 2)
### معالجة تسريب بنية التتبع `_user_stopped` والتطهير التناظري بنسبة 100%

**التاريخ**: 2026-11-03  
**الوكيل**: Worker M4 Iteration 2 (`teamwork_worker`)  
**المهمة**: تطبيق الإصلاح الجراحي الدقيق في `api_server.py` لمعالجة تسريب المعرفات في `_user_stopped` استجابةً لتقرير المدقق المعادي Challenger 1 (`challenger_p2_m4_1/handoff.md`).

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause Analysis)

1. **الرصد التجريبي للمدقق Challenger 1**:
   - خلال مناورة الإجهاد لـ 20 خيطاً متزامناً (`test_concurrent_spawn_and_stop_20_bots`)، نجحت 9 هياكل من أصل 10 في التطهير التام، بينما احتفظ الهيكل العاشر `_user_stopped` بكافة المعرفات (20 من أصل 20).
   - عند استدعاء `_stop_and_join_bot(castle_id)`، يتم تسجيل القلعة فوراً في `_user_stopped` بالسطر 359:
     ```python
     with _lock:
         _user_stopped.add(castle_id)
     ```
     ولكن عند اكتمال موت الخيط بنجاح (`if joined:` في السطر 403)، لم تكن هناك تعليمة لحذف المعرف من `_user_stopped`.
   - في مسار خروج البوت الطبيعي أو الاستثنائي داخل `_bot_thread` (السطور 988-1002)، كان هناك فحص مشروط:
     ```python
     was_user_stopped = castle_id in _user_stopped
     with _lock:
         ...
         if not was_user_stopped:
             _user_stopped.discard(castle_id)
     ```
     هذا الشرط استثنى تفريغ `_user_stopped` تحديداً في الحالات التي يكون فيها المستخدم قد أوقف القلعة، مما جعل المعرفات تتراكم بصورة دائمة.
   - عند حذف القلعة (`delete_castle_endpoint`) أو حذف المستخدم (`delete_user_endpoint`)، تُضاف المعرفات إلى `_user_stopped` كإجراء وقائي، وبعد اكتمال إيقاف الخيوط وتنظيف `_deleted_castles`، لا يتم تفريغ المعرفات من `_user_stopped`، مما يسبب تسريباً تراكمياً لمعرفات القلاع المحذوفة من قاعدة البيانات.

2. **الهدف الهندسي**:
   - تحقيق تطهير تناظري متطابق (100% Symmetric Cleanup) عبر جميع الهياكل العشرة:
     `_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`.
   - ضمان عدم بقاء أي معرف متسرب في `_user_stopped` مع الحفاظ التام على سلوك تحديث الحالة في قاعدة البيانات SQLite عند الإيقاف اليدوي.

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Implementation Logic & Steps)

1. **الخطوة 1: تنظيف `_user_stopped` عند انتهاء الخيط بنجاح في `_stop_and_join_bot`**:
   - في `api_server.py:403-407`: داخل كتلة `if joined:` المحمية بـ `_lock`، يتم استدعاء `_user_stopped.discard(castle_id)`.
   - هذا يضمن أنه بمجرد موت الخيط وتحرير موارده، يتم التخلص من معرف القلعة فوراً.

2. **الخطوة 2: جعل تنظيف `_user_stopped` حتمياً داخل `finally:` في `_bot_thread`**:
   - في `api_server.py:988-1002`: يتم تخزين القيمة المنطقية `was_user_stopped` مسبقاً في السطر 988 لاستخدامها لاحقاً في تحديث الحالة (السطر 1021)، وداخل كتلة `with _lock:` يتم تنفيذ `_user_stopped.discard(castle_id)` بصورة قطعية دون اشتراط `if not was_user_stopped`.

3. **الخطوة 3: التطهير التناظري في `delete_castle_endpoint`**:
   - في `api_server.py:1515-1517`: بعد انتهاء `_stop_and_join_bot`، وإلى جانب `_deleted_castles.discard(castle_id)`، يتم تنفيذ `_user_stopped.discard(castle_id)`.

4. **الخطوة 4: التطهير التناظري في `delete_user_endpoint`**:
   - في `api_server.py:2419-2422`: بعد انتهاء إيقاف جميع بوتات المستخدم المستهدف، وإلى جانب `_deleted_castles.discard(cid)`، يتم تنفيذ `_user_stopped.discard(cid)` لكل قلعة.

5. **الخطوة 5: ترقية وتأكيد جناح الاختبارات `tests/test_challenger_m4_stress.py`**:
   - التأكد من فحص الهياكل العشرة كاملة بما فيها `_user_stopped` داخل اختبار التزامن لـ 20 خيطاً واختبار التحقق المعادي المنفرد، والتحقق من النتيجة `assertNotIn(cid, api_server._user_stopped)`.

---

### 3. الملفات والسطور الدقيقة المزمع تعديلها (Target Files & Exact Lines)

#### الملف 1: `api_server.py`

- **الموقع 1 (السطر ~403-407)**:
  ```python
  # قبل:
          if joined:
              _castle_emails.pop(castle_id, None)
              _castle_users.pop(castle_id, None)
              _deleted_castles.discard(castle_id)
  
  # بعد:
          if joined:
              _castle_emails.pop(castle_id, None)
              _castle_users.pop(castle_id, None)
              _deleted_castles.discard(castle_id)
              _user_stopped.discard(castle_id)
  ```

- **الموقع 2 (السطر ~998-1000)**:
  ```python
  # قبل:
              _reserved.discard(castle_id)
              if not was_user_stopped:
                  _user_stopped.discard(castle_id)
              if castle_id in _deleted_castles:
  
  # بعد:
              _reserved.discard(castle_id)
              _user_stopped.discard(castle_id)
              if castle_id in _deleted_castles:
  ```

- **الموقع 3 (السطر ~1515-1517)**:
  ```python
  # قبل:
      # تفريغ معرف القلعة من _deleted_castles بعد اكتمال الموت وتحرير الموارد
      with _lock:
          _deleted_castles.discard(castle_id)
  
  # بعد:
      # تفريغ معرف القلعة من _deleted_castles بعد اكتمال الموت وتحرير الموارد
      with _lock:
          _deleted_castles.discard(castle_id)
          _user_stopped.discard(castle_id)
  ```

- **الموقع 4 (السطر ~2419-2422)**:
  ```python
  # قبل:
      # تفريغ المعرفات من _deleted_castles بعد اكتمال الموت
      with _lock:
          for cid in target_cids:
              _deleted_castles.discard(cid)
  
  # بعد:
      # تفريغ المعرفات من _deleted_castles بعد اكتمال الموت
      with _lock:
          for cid in target_cids:
              _deleted_castles.discard(cid)
              _user_stopped.discard(cid)
  ```

#### الملف 2: `tests/test_challenger_m4_stress.py`
- إضافة توكيد `assertNotIn(cid, api_server._user_stopped)` في اختبار الـ 20 خيطاً واختبار `test_user_stopped_leak_on_stop_and_deletion` للتحقق الصارم والمثبت بنسبة 100%.

---

### 4. النتائج المتوقعة وأوامر التحقق (Expected Results & Verification Commands)

| الأمر | النتيجة المتوقعة |
|---|---|
| `python tests/test_challenger_m4_stress.py` | اجتياز 100% (4/4 PASS) مع تأكيد خلو `_user_stopped` من أي تسريب |
| `python tests/test_memory_cpu_m4.py` | اجتياز 100% (5/5 PASS) |
| `python tests/test_live_operations_m3.py` | اجتياز 100% (4/4 PASS) |
| `python tests/run_all_tests.py` | اجتياز شامل لكافة مستويات المنصة 100.0% (30/30 PASS) |

**الالتزام الصارم بالقيود**:
- عدم لمس الملفات المحظورة نهائياً: `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`.
- بيئة محلية فقط، بدون أي اتصال خارجي أو رفع للسيرفر.
