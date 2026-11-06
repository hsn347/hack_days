# تقرير خطة التدقيق الجنائي المستقل لمخرجات المرحلة الخامسة (Milestone 5)

**التاريخ**: 2026-11-02  
**المدقق الجنائي**: Forensic Auditor M5 (`auditor_m5`)  
**المهمة**: التحقق الجنائي الصارم والمستقل من مخرجات المرحلة الخامسة (Milestone 5: Network Optimization & Request Deduplication)  
**المرجع**: GEMINI.md (القاعدة 4 و 5) و AGENTS_CONSTITUTION.md (المادة 13 و 14)

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

تتطلب المرحلة الخامسة (Milestone 5) التحقق الجنائي الصارم من تنفيذ المتطلبات R4 و R7 و R8 من `ORIGINAL_REQUEST.md`:
- التأكد من عدم وجود نتائج وهمية أو مصفوفات ثابتة (Hardcoded Canned Responses) في `botApi.ts` و `useUserBotStatuses.ts` و `api_server.py`.
- التأكد من عدم وجود واجهات شكلية (Facade Implementations)، والتثبت من تمرير `AbortSignal` فعلياً إلى كافة استدعاءات `fetch()` في `botApi.ts` واستدعاءات TanStack Query في `useCastles.ts`.
- التأكد من أن `UserStatusMultiplexer` ينشئ ويدير اتصال WebSocket حقيقي وموحد ومجمع لكل مستخدم، مع إدارة دورة الحياة والعد التنازلي لإلغاء الاشتراك (Reference Counting & Grace Period) دون تسريب اتصالات.
- التأكد من تفعيل تقنية Debouncing (300ms) على حقول البحث في شاشات لوحة التحكم الأربع (`Accounts.tsx`, `Admin.tsx`, `AdminUsersCastles.tsx`, `AdminLiveProcesses.tsx`).
- التحقق من معالجة `asyncio.CancelledError` و `WebSocketDisconnect` في نهايات WebSocket في `api_server.py`.

تنفيذاً للمادة 14 (الفحص الجنائي المستقل) والقاعدة 5 من GEMINI.md، يتعين تشغيل حزم الفحص والبناء والاختبار المعتمدة محلياً لتوثيق الأدلة التجريبية (Empirical Evidence).

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Step-by-Step Procedure)

1. **الخطوة الأولى**: تشغيل سكربت التحقق المستقل الخاص بالمرحلة الخامسة:
   `python tools/verify_m5_network_dedup.py`
   للتحقق من تمرير الـ signal في كافة الدوال البرمجية (34 دالة)، ودمج WebSocket، وإلغاء ارتداد البحث، ومعالجة انقطاع الاتصال بالخادم، ومحاكاة دورة حياة الإلغاء والاشتراك المجمع.
2. **الخطوة الثانية**: التحقق من سلامة الواجهة الأمامية وخلوها من أخطاء الـ Type وتجميع حزمة الإنتاج:
   `powershell -Command "Set-Location dashboard; npm run build"`
   للتأكد من اجتياز فحص `tsc` و `vite build` بنجاح بنسبة 100%.
3. **الخطوة الثالثة**: تشغيل حزمة الاختبارات الشاملة للمنصة (4 مستويات - 30 اختباراً):
   `python tests/run_all_tests.py`
   للتأكد من عدم حدوث أي تراجع أو كسر في وظائف الباك إند أو قاعدة البيانات أو أمان التعديلات المتزامنة.
4. **الخطوة الرابعة**: تقييم الأدلة وإصدار تقرير التسليم النهائي `handoff.md` بحكم بات: **CLEAN** أو **INTEGRITY VIOLATION**.

---

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)

| # | الأمر المراد تنفيذه | المسار / البيئة | النتيجة المتوقعة |
|---|--------------------|-----------------|------------------|
| 1 | `python tools/verify_m5_network_dedup.py` | `e:\osmanli` | اجتياز جميع الفحوصات (71/71 tests passed - 100%) بدون أي إخفاق |
| 2 | `powershell -Command "Set-Location dashboard; npm run build"` | `e:\osmanli\dashboard` | انتهاء البناء برمز خروج 0 (Zero TypeScript errors, Vite build successful) |
| 3 | `python tests/run_all_tests.py` | `e:\osmanli` | نجاح كافة الاختبارات عبر المستويات الأربعة (30/30 passed - 100%) في بيئة محلية معزولة |

---
**تنبيه أمان صارم**: كافة الأوامر أعلاه محلية 100% ولا تتضمن أي اتصال بخوادم خارجية أو نشر عن بُعد، التزاماً تاماً بالقاعدة 4 والقاعدة 5.
