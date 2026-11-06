# تقرير التسليم والتحقق التجريبي المعادي: المرحلة 4 (المتطلب R3)
## Empirical Challenger Handoff Report — Milestone 4: Thread Lifecycles & Leak Prevention (R3)

**تاريخ الإعداد**: 2026-11-03  
**الجهة المُعِدّة**: Challenger 1 (`teamwork_challenger`)  
**المهمة**: التحقق التجريبي المستقل والمناورات الإجهادية (Stress Testing) لدورة حياة الخيوط والخلو التام من تسريب القواميس العشرة وعزل الخيوط العالقة وفقاً لـ `ORIGINAL_REQUEST.md` (R3) و `DISPATCH.md`.  
**الحكم النهائي (Verdict)**: **REQUEST_CHANGES** ⚠️ (بسبب رصد تسريب حتمي في `_user_stopped` عند إيقاف القلاع وحذفها، مع اجتياز ممتاز لكافة المحاور الهندسية الأخرى).

---

## Challenge Summary

**Overall risk assessment**: MEDIUM (محصور في بنية `_user_stopped` وتراكم المعرفات المحذوفة في الذاكرة دون استنزاف فوري، مع كفاءة تامة لبقية المحاور).

### Stress Test Results Summary
- **تحدي التزامن لـ 20 بوتاً متزامناً (`test_concurrent_spawn_and_stop_20_bots`)**:
  - تم تشغيل 20 خيطاً وإيقافها متزامناً عبر `concurrent.futures.ThreadPoolExecutor` و `_stop_and_join_bot` خلال **0.026 ثانية** فقط.
  - جميع الخيوط الـ 20 انتهت وماتت بالكامل (`is_alive() == False`) دون أي تعليق أو Deadlock خارج القفل العام.
  - **9 من أصل 10 هياكل عامة خلت تماماً من القلاع**: `_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_castle_emails`, `_castle_users`, `_deleted_castles` (PASS بنسبة 100%).
- **تحدي الخيوط العالقة غير المتعاونة (`test_uncooperative_thread_stall_quarantine`)**:
  - خيط عنيد يتجاهل إشارات الإيقاف تم إيقافه بمهلة 0.2 ثانية، وعاد المستدعي فوراً دون تعليق (< 1.0s).
  - تم استبعاد الخيط من `_threads` وعزله بنجاح في `_stalled_threads` مع كافة بيانات التشخيص (`ident`, `email`, `user_id`, `stalled_at`) (PASS بنسبة 100%).
- **تحدي تطهير ارتباطات البروكسي (`test_proxy_manager_cleanup_lifecycle`)**:
  - تم التحقق من نجاح `remove_castle_proxy` و `remove_user_proxy_bindings` في تطهير الذاكرة وتحديث ملف `user_proxy_bindings.json` عند حذف القلاع والمستخدمين (PASS بنسبة 100%).
- **جناح اختبارات المنصة الشامل (`python tests/run_all_tests.py`)**:
  - اجتياز **30 من أصل 30 اختباراً بنسبة 100.0%** عبر المستويات الأربعة في 7.02 ثانية.
- **جناح اختبارات الذاكرة M4 (`python tests/test_memory_cpu_m4.py`)**:
  - اجتياز **5 من أصل 5 اختبارات بنسبة 100%** في 0.267 ثانية.
- **جناح اختبارات العمليات الحية M3 (`python tests/test_live_operations_m3.py`)**:
  - اجتياز **4 من أصل 4 اختبارات بنسبة 100%** في 0.702 ثانية.

---

## 1. Observation (ما تم رصده وتوثيقه ميدانياً بالأدلة)

1. **تسريب المعرفات في مجموعة `_user_stopped` بعد الإيقاف الحتمي**:
   - في `tests/test_challenger_m4_stress.py`، عند فحص القلاع الـ 20 بعد استدعاء `_stop_and_join_bot` ونجاح الـ `join`، تبيّن أن جميع القلاع الـ 20 لا تزال محتجزة داخل مجموعة `_user_stopped`:
     ```
     [Stress-20] Stopped and joined 20 bots concurrently in 0.026s
     [Leak-Check] _user_stopped retains castle_id after _stop_and_join_bot: True
     ```
   - عند فحص كود `_stop_and_join_bot` في `api_server.py:359` و `api_server.py:396-407`:
     ```python
     # api_server.py:359
     with _lock:
         _user_stopped.add(castle_id)
     ...
     # api_server.py:396-407
     with _lock:
         _threads.pop(castle_id, None)
         _stop_events.pop(castle_id, None)
         _bot_managers.pop(castle_id, None)
         _reserved.discard(castle_id)
         _log_qs.pop(castle_id, None)
         _conn_states.pop(castle_id, None)
         if joined:
             _castle_emails.pop(castle_id, None)
             _castle_users.pop(castle_id, None)
             _deleted_castles.discard(castle_id)
             # _user_stopped.discard(castle_id) غير موجودة إطلاقاً!
     ```
2. **الاستثناء المشروط غير المبرر في `_bot_thread`**:
   - في `api_server.py:988-1002`:
     ```python
     was_user_stopped = castle_id in _user_stopped
     with _lock:
         ...
         if not was_user_stopped:
             _user_stopped.discard(castle_id)
     ```
     إذا كان المستخدم قد أوقف القلعة (`was_user_stopped == True`)، فإن الشرط `if not was_user_stopped` يتخطى حذف القلعة من `_user_stopped`، مما يتركها عالقة للأبد في الذاكرة.
3. **تسريب معرفات القلاع المحذوفة نهائياً من قاعدة البيانات**:
   - في `delete_castle_endpoint` (`api_server.py:1501, 1515-1517`):
     ```python
     with _lock:
         _deleted_castles.add(castle_id)
         _user_stopped.add(castle_id)
     _stop_and_join_bot(castle_id, timeout=3.0)
     ...
     with _lock:
         _deleted_castles.discard(castle_id)
         # _user_stopped.discard(castle_id) غير موجودة!
     ```
   - في `delete_user_endpoint` (`api_server.py:2405, 2419-2422`):
     ```python
     with _lock:
         for cid in target_cids:
             _deleted_castles.add(cid)
             _user_stopped.add(cid)
     for cid in target_cids:
         _stop_and_join_bot(cid, timeout=3.0)
     ...
     with _lock:
         for cid in target_cids:
             _deleted_castles.discard(cid)
             # _user_stopped.discard(cid) غير موجودة!
     ```
     القلاع التي يتم حذفها نهائياً من قاعدة البيانات SQLite تظل معرفاتها عالقة في الذاكرة داخل `_user_stopped` دون تفريغ.

---

## 2. Logic Chain (التسلسل المنطقي من الملاحظات إلى الحكم)

1. نص التكليف في `DISPATCH.md` الصادر لـ Challenger 1 يشترط صراحة في البند 2:
   > "Verify that after stopping: All 10 global dictionaries (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`) are completely emptied of these castles."
2. تقرير العامل M4 (`worker_p2_m4/handoff.md` السطر 30) ادعى تفريغ القواميس العشرة بالكامل:
   > "تم تغليف مسارات الخروج المبكر وكتلة `finally:` في `_bot_thread` بآلية تنظيف حتمية تحذف القلعة من القواميس العشرة: `_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, و `_deleted_castles`."
3. أثبت الفحص التجريبي في السكربت `tests/test_challenger_m4_stress.py` أن 9 قواميس يتم تفريغها بنجاح تام، بينما القاموس العاشر `_user_stopped` لا يتم تفريغه بل يحتفظ بالمعرفات 100%.
4. عند حذف القلعة أو حذف المستخدم، تصبح القلعة معدومة في قاعدة البيانات، ومع ذلك يبقى معرفها داخل `_user_stopped` بصورة دائمة كـ Memory Leak تراكمي غير محدود.
5. بما أن المتطلب R3 يركز جذرياً على "القضاء على تسريبات الموارد وتطهير هياكل البيانات العامة العشرة"، وبما أن شرط التفريغ التام للقواميس العشرة لم يتحقق بنسبة 100% للقاموس `_user_stopped`، فإن الحكم الهندسي الصارم والمعتمد هو **طلب التعديل (REQUEST_CHANGES)** لتصحيح هذه الأسطر الأربعة المحددة بدقة.

---

## 3. Caveats (الافتراضات والحدود)

- استهلاك الذاكرة لـ `_user_stopped` طفيف لكل عنصر (~64 بايت للمعرف النصي)، إلا أن تراكم المعرفات مع مئات القلاع المحذوفة أو الموقوفة يشكل خرقاً لمبدأ الخلو التام من التسريب (Zero Leaks).
- تم التحقق من أن بقية إنجازات العامل M4 (خيوط Join، عزل Stalled، أداء البروكسي، تقليم السجلات المتدفق، إلغاء Wait السريع، كاش WebSockets) في غاية المتانة واجتازت كافة الاختبارات بجدارة استثنائية.
- لم يتم لمس الملفات المحظورة قطيعاً: `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`.

---

## 4. Conclusion & Required Actions (الخلاصة والتعديلات المطلوبة بدقة)

**الحكم النهائي**: **REQUEST_CHANGES** ⚠️

### التعديلات المطلوبة من العامل المصلح (Remediation Actions):
1. **في `api_server.py:407` (داخل دالة `_stop_and_join_bot`)**:
   إضافة تفريغ `_user_stopped` عند موت الخيط بنجاح (`joined == True`):
   ```python
   if joined:
       _castle_emails.pop(castle_id, None)
       _castle_users.pop(castle_id, None)
       _deleted_castles.discard(castle_id)
       _user_stopped.discard(castle_id)  # <--- إضافة هذا السطر
   ```
2. **في `api_server.py:998-1000` (داخل `finally:` في `_bot_thread`)**:
   تعديل الشرط ليتم تفريغ `_user_stopped` دائماً عند انتهاء الخيط:
   ```python
   # استبدال:
   # if not was_user_stopped:
   #     _user_stopped.discard(castle_id)
   # بـ:
   _user_stopped.discard(castle_id)
   ```
3. **في `api_server.py:1516` (داخل `delete_castle_endpoint`)**:
   إضافة تفريغ المعرف من `_user_stopped` عند حذف القلعة:
   ```python
   with _lock:
       _deleted_castles.discard(castle_id)
       _user_stopped.discard(castle_id)  # <--- إضافة هذا السطر
   ```
4. **في `api_server.py:2421` (داخل `delete_user_endpoint`)**:
   إضافة تفريغ المعرفات من `_user_stopped` عند حذف المستخدم وقلاعه:
   ```python
   with _lock:
       for cid in target_cids:
           _deleted_castles.discard(cid)
           _user_stopped.discard(cid)  # <--- إضافة هذا السطر
   ```

---

## 5. Verification Method (طريقة التحقق المستقل)

1. **تشغيل سكربت التحدي الإجهادي المستقل**:
   ```powershell
   python tests/test_challenger_m4_stress.py
   ```
   **المعيار**: تفريغ القواميس العشرة بما فيها `_user_stopped` بنسبة 100%، وعدم بقاء أي معرف.
2. **تشغيل جناح اختبارات المنصة الشامل**:
   ```powershell
   python tests/run_all_tests.py
   ```
   **المعيار**: اجتياز 30/30 بنسبة 100.0%.
3. **تشغيل جناح اختبارات M4 المستقل**:
   ```powershell
   python tests/test_memory_cpu_m4.py
   ```
   **المعيار**: اجتياز 5/5 بنسبة 100%.
