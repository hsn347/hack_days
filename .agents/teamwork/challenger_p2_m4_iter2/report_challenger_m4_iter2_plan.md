# تقرير فني مسبق: خطة التحقق التجريبي المعادي لـ Milestone 4 (التكرار 2)
## Pre-Execution Technical Report: Empirical Verification of `_user_stopped` Leak Resolution (R3)

**تاريخ الإعداد**: 2026-11-03  
**المحرر**: Challenger M4 Iteration 2 (`teamwork_challenger`)  
**المهمة**: التحقق التجريبي القاطع من زوال تسريب المعرفات في هيكل `_user_stopped` بنسبة 100%، والتأكد من خلو كافة الهياكل العشرة من أي تسريبات عند إيقاف وحذف القلاع والمستخدمين، وضمان عدم حدوث أي انحدار (Regressions) في منظومة الاختبارات الشاملة.  
**الامتثال للقواعد**: التزام صارم بقاعدة GEMINI.md Rule 5 (إنشاء تقرير فني مسبق قبل تشغيل أي أمر أو تعديل)، والحظر القطعي للملفات المحمية (`game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`).

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

1. **خلفية التحدي السابق (Challenger Iteration 1)**:
   - في الجولة السابقة، رصد Challenger 1 وجود تسريب معرفات حتمي في هيكل `_user_stopped`:
     - عند استدعاء `_stop_and_join_bot`، كانت القلعة تضاف إلى `_user_stopped` عند بدء الإيقاف (`_user_stopped.add(castle_id)`) ولكن لا يتم تفريغها عند نجاح انتهاء الخيط (`joined == True`).
     - في كتلة `finally:` داخل `_bot_thread`، كان الشرط `if not was_user_stopped:` يستثني حذف القلعة إذا تم إيقافها يدوياً بواسطة المستخدم.
     - في نقاط النهاية لحذف القلعة (`delete_castle_endpoint`) وحذف المستخدم (`delete_user_endpoint`)، كانت المعرفات تُضاف إلى `_user_stopped` دون تفريغ لاحق عند اكتمال الحذف.
   - أسفر ذلك عن إصدار حكم `REQUEST_CHANGES` وطلب تدخل جراحي لتطبيق التطهير المتناظر (Symmetric Cleanup).

2. **التعديلات المنفذة بواسطة Worker Iteration 2**:
   - قام Worker M4 Iteration 2 بإجراء تعديل جراحي في 4 مواضع بملف `api_server.py`:
     - السطر 407: إضافة `_user_stopped.discard(castle_id)` عند نجاح `joined`.
     - السطر 999: استدعاء `_user_stopped.discard(castle_id)` بشكل حتمي دون شرط `if not was_user_stopped` مع الاحتفاظ بقيمة `was_user_stopped` في متغير محلي قبل التفريغ.
     - السطر 1517: إضافة `_user_stopped.discard(castle_id)` في `delete_castle_endpoint`.
     - السطر 2423: إضافة `_user_stopped.discard(cid)` في `delete_user_endpoint`.

3. **سبب الحاجة إلى هذا الإجراء (Empirical Challenger Mandate)**:
   - بصفتنا Empirical Challenger، لا نعتمد على مزاعم أو سجلات العامل، بل يقع على عاتقنا تشغيل الاختبارات بأنفسنا والتحقق الميداني المباشر من:
     - اختفاء التسريب تماماً في سيناريو الإجهاد المتزامن لـ 20 خيطاً.
     - تقييم التعبير `[Leak-Check] _user_stopped retains castle_id after _stop_and_join_bot` بالقيمة `False`.
     - نظافة الهياكل العشرة بنسبة 100%.
     - نجاح اختبارات الذاكرة M4 (5/5).
     - نجاح جناح اختبارات المنصة الشامل (30/30).

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Execution Steps)

1. **الخطوة الأولى: تشغيل اختبار الإجهاد المعادي المستقل (`test_challenger_m4_stress.py`)**:
   - إطلاق 20 خيط بوت وهمي بشكل متزامن.
   - إيقاف الخيوط العشرين معاً عبر `ThreadPoolExecutor` واستدعاء `_stop_and_join_bot`.
   - قياس زمن الإيقاف والتحقق من موت جميع الخيوط (`is_alive() == False`).
   - التحقق من تفريغ كافة الهياكل العشرة العامة (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`).
   - التحقق من عزل الخيوط العالقة غير المتعاونة في `_stalled_threads` دون تعليق المستدعي.
   - التحقق من تطهير ارتباطات البروكسي عند حذف القلعة أو المستخدم.
   - فحص تسريب `_user_stopped` المنفرد والتأكد من طباعة `False`.

2. **الخطوة الثانية: تشغيل جناح اختبارات الذاكرة والمعالج M4 (`test_memory_cpu_m4.py`)**:
   - التحقق من ثبات استهلاك الذاكرة وعدم وجود تسريبات دورية.
   - التحقق من صحة توثيق حالة القلعة بعد الإيقاف اليدوي بواسطة المستخدم ("تم إيقاف البوت بواسطة المستخدم").

3. **الخطوة الثالثة: تشغيل جناح اختبارات المنصة الشامل (`run_all_tests.py`)**:
   - التحقق من أن التعديلات الجراحية في `api_server.py` لم تتسبب في أي كسر أو انحدار في وظائف الوحدات الأخرى عبر المنظومة (30/30).

4. **الخطوة الرابعة: توثيق النتائج وإصدار الحكم النهائي في `handoff.md` وإرسال الرسالة إلى المشرف**.

---

### 3. الأوامر والملفات التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)

#### الأمر 1:
```powershell
python tests/test_challenger_m4_stress.py
```
- **المعلمات والبيئة**: محلياً في مجلد المشروع `e:\osmanli`، باستخدام بيئة بايثون الافتراضية للنظام.
- **النتيجة المتوقعة**:
  - `Ran 4 tests in ~0.3s - OK`.
  - طباعة `[Stress-20] Stopped and joined 20 bots concurrently in <0.1s`.
  - طباعة `[Leak-Check] _user_stopped retains castle_id after _stop_and_join_bot: False`.
  - عدم وجود أي رسالة خطأ أو فشل (AssertionError).

#### الأمر 2:
```powershell
python tests/test_memory_cpu_m4.py
```
- **المعلمات والبيئة**: محلياً في مجلد المشروع `e:\osmanli`.
- **النتيجة المتوقعة**:
  - `Ran 5 tests in ~0.4s - OK`.
  - اجتياز 5/5 بنسبة 100%.

#### الأمر 3:
```powershell
python tests/run_all_tests.py
```
- **المعلمات والبيئة**: محلياً في مجلد المشروع `e:\osmanli`.
- **النتيجة المتوقعة**:
  - اجتياز 30 من أصل 30 اختباراً بنسبة 100.0%.
  - نجاح كافة المستويات (L1, L2, L3, L4).
