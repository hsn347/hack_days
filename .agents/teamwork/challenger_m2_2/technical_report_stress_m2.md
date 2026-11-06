# تقرير فني مستقل: خطة الفحص التجريبي الإجهادي لقفل التعديل التفاؤلي والتزامن (Milestone 2)
### Independent Technical Report: Empirical Stress-Testing for Optimistic Concurrency Control (OCC)

**المرجع:** `e:\osmanli\AGENTS_CONSTITUTION.md` & `e:\osmanli\GEMINI.md` (البند 5: إلزامية التقرير الفني المسبق)  
**المرحلة:** Milestone 2 (M2) — Concurrency & OCC Stress Challenger  
**الموقع المنفذ:** Challenger M2 Instance 2 (`.agents/teamwork/challenger_m2_2/`)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnostics & Rationale)
في المرحلة Milestone 2، تم تطبيق قفل التعديل التفاؤلي (Optimistic Concurrency Control - OCC) في دالة `update_castle_config` بملف `core/database.py`، بالإضافة إلى معالجة كود الخطأ HTTP 409 Conflict في مسار `PUT /api/castles/{castle_id}` بملف `api_server.py`.

الهدف من هذا الفحص الإجهادي التجريبي هو إثبات كفاءة وصلابة آلية الـ OCC عملياً تحت ظروف التزامن العالي والتنافس الشديد (Extreme Contention) ومقاومة حدوث حالات الجمود أو الانهيار (Deadlocks / Crashes / SQLite busy lock):
1. **التنافس المتزامن الكثيف (Multi-threaded Contention)**: إطلاق 20 خيطاً متزامناً (Threads) يحاولون جميعاً في نفس اللحظة تحديث نفس سجل القلعة بالنسخة المبدئية 1 (`expected_version=1`)، والتحقق تجريبياً من فوز خيط واحد فقط بالضبط ورفض الـ 19 خيطاً الآخرين مع إرجاع `conflict: True` دون أي استثناء لقفل قاعدة البيانات `sqlite3.OperationalError: database is locked`.
2. **التعديلات التراكمية المتتالية (Sequential Increment Stress)**: تنفيذ 50 تعديلاً متتالياً مع تمرير النسخة المحدثة في كل خطوة، للتأكد من وصول النسخة إلى 51 بدقة وسلامة دمج وحفظ كافة حقول الإعدادات (`_deep_merge_dict` و `_sanitize_castle_config`).
3. **التوافق العكسي (Backward Compatibility)**: اختبار استدعاء الدالة من قبل عميل قديم لا يمرر `expected_version`، والتحقق من زيادة النسخة وعمل الكائن `OCCResult` كقيمة صحيحة منطقياً (`bool(res) is True`) مع احتوائه على كامل تفاصيل النتيجة.
4. **فحص مستوى الـ HTTP Endpoint**: فحص استجابة الـ FastAPI endpoint في `api_server.py` مع `TestClient` تحت تنافس تزامني وتأكيد إرجاع HTTP 409 عند التضارب التزامني.

---

## 2. المنطق والخطوات الهندسية المعتمدة (Methodology & Logic)
1. **إنشاء أداة الفحص الإجهادي في `tools/stress_m2_concurrency.py`**:
   - بناء بيئة اختبار هرميتية ومعزولة كلياً باستخدام مجلد مؤقت وقاعدة بيانات SQLite خاصة بالاختبار `test_occ_stress.db`.
   - استخدام `threading.Barrier(20)` لمزامنة انطلاق كافة الخيوط العشرين في نفس الجزء من المليثانية لمنع أي تسلسل زمني عشوائي وتحقيق أقصى تنافس حقيقي على القفل `BEGIN IMMEDIATE`.
   - تسجيل إحصائيات زمن التنفيذ (Execution Latency) ونتائج كل خيط (نجاح، تعارض، استثناءات).
2. **فحص الـ Sequential Stress**:
   - حلقة تكرارية مكونة من 50 تكرار، تقرأ النسخة الحالية وتحدث مفتاحاً فريداً مع النسخة المتوقعة.
   - التحقق من مطابقة النسخة النهائية (51) ووجود كافة المفاتيح الخمسين سليمة في JSON.
3. **فحص التوافق العكسي (Legacy Callers)**:
   - استدعاء الدالة بدون `expected_version`، والتحقق من أن `res` يُقيم إلى `True` بواسطة `__bool__`، وأن النسخة زادت إلى 52، وأن النمط القديم `if res: ...` يعمل دون أي تعديل في كود المستدعي.
4. **فحص HTTP API Concurrency**:
   - استخدام `TestClient(app)` وتوجيه طلبات متزامنة لنقطة النهاية `/api/castles/{id}/config` للتأكد من سلوك الخادم الفعلي.

---

## 3. الأوامر والملفات المنفذة والنتيجة المتوقعة (Files, Commands & Expected Output)

| الملف المستهدف | الإجراء | النتيجة المتوقعة |
|---|---|---|
| `tools/stress_m2_concurrency.py` | كتابة سكربت الفحص الإجهادي التزامني المستقل | كود اختبار متكامل ينفذ الخيوط والحواجز والفحوصات |
| أمر: `python tools/stress_m2_concurrency.py` | تشغيل السكربت الإجهادي عبر بايثون محلياً | 20 خيط: 1 نجاح، 19 تعارض، 0 أخطاء قفل. 50 تعديل تسلسلي: نجاح بنسبة 100% ونسخة 51. التوافق العكسي: نجاح. |
| أمر: `python tests/run_all_tests.py` | تشغيل حزمة الاختبارات الشاملة للمشروع | نجاح 30/30 بنسبة 100.0% دون أي انكسار |
