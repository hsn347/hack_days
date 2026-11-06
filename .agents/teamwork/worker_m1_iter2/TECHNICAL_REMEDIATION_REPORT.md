# تقرير فني مسبق: خطة المعالجة الهندسية لملاحظات المراجعين والمُتحدي 2 (Milestone 1 Remediation)

**التاريخ والوقت**: 2026-11-02T17:40:00Z  
**الوكيل**: Worker M1 (Iteration 2)  
**المجلد**: `e:\osmanli\.agents\teamwork\worker_m1_iter2\`  
**المرجع الدستوري**: `AGENTS_CONSTITUTION.md` & `GEMINI.md` (البند 5: إلزامية إرفاق ملف تقرير مستقل قبل أي تعديل أو أمر)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause & Justification)

### أ. اختناق حلقة الـ Event Loop في `api_server.py:ws_user_status`
- **التشخيص**: في التكرار الأول (Iteration 1)، تم تفريغ استدعاء قاعدة البيانات `db.get_user_castles(user_id)` فقط عبر `asyncio.to_thread`. ومع ذلك، ظلت حلقة التكرار `for c in castles: res[cid] = _get_real_status(cid)` تُنفذ مباشرة على خيط الـ Event Loop الرئيسي.
- **الأثر المقاس**: دالة `_get_real_status` تستحوذ على قفل التزامن `with _lock:` وتجري مسحاً على هياكل الذاكرة الحية وقاعدة البيانات عند اللزوم. وتحت ضغط 50 عميل WebSocket متزامن يقومون بالاستعلام كل 0.8 ثانية، أدى استيقاظ العملاء المتزامن إلى تنافس حاد وتجميد الـ Event Loop بتأخير P95 بلغ **107.780 ms**، وأقصى تأخير بلغ **1035.023 ms** (كما وثق Challenger 2).
- **الهدف**: نقل عملية جمع الحالات بالكامل (قراءة قاعدة البيانات + حلقة القلاع + جلب الحالات) إلى Thread Pool عبر دالة متزامنة واحدة، مما يخفض تأخير الـ Event Loop إلى **~2.0 ms** (مطابق لتذبذب الـ Event Loop في وضع الخمول).

### ب. خطأ صياغة SQL عند تمرير نطاقات بيضاء فارغة في `core/database.py`
- **التشخيص**: في السطور 1714-1721 من `core/database.py`، كان الفحص ينص على:
  ```python
  if tenant_domains and len(tenant_domains) > 0:
      clean_domains = [d.strip().lower() for d in tenant_domains if d.strip()]
      placeholders = ",".join("?" for _ in clean_domains)
      where_clause = f"WHERE {base_where} AND LOWER(u.tenant_domain) IN ({placeholders})"
  ```
  عند تمرير قائمة تحتوي سلاسل فارغة أو مسافات بيضاء فقط مثل `['', '   ']`، يكون الشرط `len(tenant_domains) > 0` صحيحاً، ولكن قائمة `clean_domains` تصبح فارغة `[]`، وتصبح `placeholders` نصاً فارغاً `""`، مما ينتج استعلام SQL غير صالح:
  `WHERE ... AND LOWER(u.tenant_domain) IN ()`
  وهو ما يسبب انهيار الاستعلام بخطأ SQLite النحوي: `sqlite3.OperationalError: near ")": syntax error`.
- **الهدف**: تنظيف القائمة أولاً والتحقق عبر `if clean_domains:` لمنع إنشاء `IN ()` تماماً في حال كانت كل العناصر فارغة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Remediation Logic & Strategy)

1. **في `api_server.py`**:
   - تعريف دالة متزامنة مستقلة `_sync_collect_user_statuses(user_id: str) -> Dict[str, str]` على مستوى الموديل، تجمع بيانات القلاع وحالاتها بالكامل دفعة واحدة بدون أي تفريغ جزئي.
   - في `ws_user_status`، استدعاء `_sync_collect_user_statuses` عبر:
     ```python
     curr_data = await asyncio.to_thread(_sync_collect_user_statuses, user_id)
     ```
   - الحفاظ على توافقية الدوال الداخلية `_collect_statuses` مع توجيهها للاستدعاء الكامل غير الحاجب.

2. **في `core/database.py`**:
   - تنظيف `tenant_domains` مسبقاً:
     ```python
     clean_domains = [d.strip().lower() for d in tenant_domains if d and d.strip()] if tenant_domains else []
     if clean_domains:
         placeholders = ",".join("?" for _ in clean_domains)
         where_clause = f"WHERE {base_where} AND LOWER(u.tenant_domain) IN ({placeholders})"
         params.extend(clean_domains)
     else:
         where_clause = f"WHERE {base_where}"
     ```

3. **في `tools/verify_m1_backend.py`**:
   - مواءمة فحص `test_websocket_async_offload` ليدعم ويتحقق من التفريغ الكامل `_sync_collect_user_statuses` إلى `asyncio.to_thread`.

4. **في `tests/test_database_performance.py`**:
   - إضافة اختبار وحدة `test_t2_whitespace_tenant_domains_boundary` للتحقق من عدم حدوث أي خطأ SQL عند تمرير قوائم بيضاء مثل `['', '   ']`.

---

## 3. الملفات والسطور والأوامر بالتفصيل والنتائج المتوقعة (Detailed Actions & Expected Results)

| الملف | السطور المستهدفة | التعديل | النتيجة المتوقعة |
|---|---|---|---|
| `api_server.py` | 3060-3090 | إضافة `_sync_collect_user_statuses` وتعديل `ws_user_status` للتفريغ الكامل | اختفاء أي حجز للـ Event Loop وانخفاض P95 إلى < 5.0ms |
| `core/database.py` | 1714-1721 | فحص `clean_domains` قبل بناء شرط `IN` | منع أخطاء النحو `near ")": syntax error` |
| `tools/verify_m1_backend.py` | 140-151 | مطابقة فحص التفريغ الكامل لـ `_sync_collect_user_statuses` | نجاح 5/5 في الفحص المستقل |
| `tests/test_database_performance.py` | نهاية الفئة `TestTier2BoundaryAndStress` | إضافة اختبار حالات النطاقات البيضاء الفارغة | اجتياز الاختبارات وتأكيد حماية الحالات الحدية |

### الأوامر التنفيذية المخططة للتحقق:
1. `python tools/benchmark_m1_stress_suite.py` -> P95 lag < 5.0 ms
2. `python tools/verify_m1_backend.py` -> 5/5 PASSED
3. `python tests/run_all_tests.py` -> 30/30 PASSED (29 سابقاً + اختبار الحالات الحدية الجديد)
