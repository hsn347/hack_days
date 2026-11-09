# تقرير فني مسبق رقم 7: فحص بقية الاختبارات المستقلة والتحقق من النتائج الفردية

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب
كجزء من التدقيق الشامل للأدلة، يجب فحص واختبار بقية الملفات للتأكد هل جميع الاختبارات الأخرى ناجحة وهل توجد أي إخفاقات أو اختلافات أخرى غير `test_agent14_city_resource_qa.py`.

## 2. المنطق والخطوات التي سيتم تطبيقها
تشغيل ملفات الاختبارات التالية فرادى وتسجيل أعداد الاختبارات وأزمنتها والنتائج:
1. `tests/test_building_lifecycle_qa.py`
2. `tests/test_gate_fallback_empirical.py`
3. `tests/test_live_memory_marches_army.py`
4. `tests/test_live_socket_spy.py`
5. `tests/test_concurrency_stress.py`
6. `tests/test_live_conn_agent11.py`
7. `tests/audit_whitelist_memory.py`

## 3. الأوامر التي ستُنفذ بالتفصيل والنتيجة المتوقعة
- تشغيل كل ملف unittest وتسجيل مخرجاته بالأرقام.
