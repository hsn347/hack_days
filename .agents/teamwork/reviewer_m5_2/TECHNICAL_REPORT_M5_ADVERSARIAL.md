# تقرير فني مستقل: المراجعة المعاكسة والتحقق الإجهادي للمرحلة الخامسة (Milestone 5 Adversarial Review)

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Purpose)
المرحلة الخامسة تهدف إلى تحسين الشبكة، منع تكرار الطلبات المتطابقة (Request Deduplication)، وإدارة إلغاء الطلبات المعلقة عبر `AbortController`، بالإضافة إلى تحسين الـ WebSocket (إعادة الاتصال والتراجع الأسي Exponential Backoff)، وتحسين التهدئة (Debounce) لمدخلات البحث والإعدادات السريعة، وتنظيف مقابس وسياقات الـ WebSocket غير المستخدمة في السيرفر الخلفي `api_server.py`.
كمراجع معاكس (Adversarial Critic & Reviewer)، المطلوب هو فحص الكود للتأكد من:
1. السلامة الهيكلية والأمان (Integrity Check): التأكد من عدم وجود قيم اختبارية صلبة مزيفة (Hardcoded test results) أو واجهات وهمية (Facade / Dummy implementations) أو تحايل على المتطلبات.
2. سيناريوهات الإجهاد وحالات الحافة (Stress & Failure Modes):
   - التنقل السريع بين المسارات (Rapid Route Changes): إلغاء الطلبات القديمة دون ترك استثناءات Uncaught AbortError تلوث السجل أو تسبب تسريبات ذاكرة.
   - عاصفة إعادة الاتصال (Reconnect Storms): هل الـ WebSocket يطبق فعلياً تراجعاً أسياً مع حد أقصى (Max Delay) و jitter لتفادي هجمات حجب الخدمة الذاتية؟
   - ضغط الإدخال المتكرر السريع (Rapid Typing Debounce): هل إعادة الرسم مقتصرة وهل يتم تفادي إعادة الحساب المرهقة؟
   - تسريب المهام والمقابس في السيرفر `api_server.py` عند قطع الاتصال المفاجئ من العميل.

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Plan)
1. قراءة تقرير العامل `worker_m5/handoff.md` والملفات المعدلة في المشروع.
2. مراجعة الكود البرمجي التفصيلي في:
   - `dashboard/src/services/api.ts`
   - `dashboard/src/services/websocket.ts`
   - `dashboard/src/hooks/useDebounce.ts`
   - `api_server.py`
   - `tools/verify_m5_network_dedup.py`
   - المكونات ذات الصلة في واجهة المستخدم.
3. التحقق المستقل من اختبارات التحقق والأداء:
   - تشغيل سكريبت التحقق الخاص بالمرحلة 5: `python tools/verify_m5_network_dedup.py`
   - التحقق من بناء الواجهة (Vite / TypeScript build): `powershell -Command "Set-Location dashboard; npm run build"`
   - تشغيل كافة اختبارات النظام الشاملة: `python tests/run_all_tests.py`
4. تقييم النتائج بدقة ومقارنتها بالمتطلبات (R4, R7, R8).
5. كتابة تقرير التسليم النهائي `handoff.md` بحكم واضح (APPROVE أو REQUEST_CHANGES).

## 3. الأوامر التي ستُنفذ مع النتيجة المتوقعة (Commands to Execute & Expected Results)
1. الأمر: `python tools/verify_m5_network_dedup.py`
   - النتيجة المتوقعة: نجاح اختبارات دمج الطلبات (Deduplication)، وإلغاء الإشارات (AbortController)، وإعادة الاتصال بمقبس الويب.
2. الأمر: `powershell -Command "Set-Location dashboard; npm run build"`
   - النتيجة المتوقعة: بناء الواجهة الأمامية بنجاح وخلوها من أخطاء TypeScript وبناء الحزم.
3. الأمر: `python tests/run_all_tests.py`
   - النتيجة المتوقعة: اجتياز جميع اختبارات السيرفر الخلفي والوحدات بنسبة 100%.
