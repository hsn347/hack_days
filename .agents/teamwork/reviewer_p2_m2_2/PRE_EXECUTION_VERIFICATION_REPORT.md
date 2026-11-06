# تقرير فني مستقل مسبق لتشغيل أوامر التحقق والفحص المستقل (Reviewer Pre-Execution Report)

**التاريخ:** 2026-11-03T02:06:00Z  
**المدقق:** `reviewer_p2_m2_2` (Adversarial & Security Reviewer)  
**المرحلة:** Milestone 2: Admin Castles Pagination & Lazy Loading (R1)  
**الهدف:** توثيق تشخيص وأسباب الأوامر التنفيذية المطلوب تشغيلها محلياً للتحقق المستقل وفق اشتراطات المهمة وقواعد الدستور.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

وفقاً لتكليف التدقيق في `DISPATCH.md` ودستور أسراب الوكلاء `AGENTS_CONSTITUTION.md`:
1. يتعين التحقق المستقل من خلو كود الواجهة الأمامية من أي أخطاء ترجمة برمجية TypeScript (`npm run build`) والتأكد من نجاح توليد حزم الإنتاج بـ 0 أخطاء.
2. يتعين تشغيل منصة الاختبارات الشاملة للمشروع (`python tests/run_all_tests.py`) والتحقق المباشر من اجتياز كافة الاختبارات الـ 30 بنسبة 100% دون أي فشل.
3. يتعين فحص حالة المستودع المحلي عبر Git للتأكد القاطع من عدم فتح أو لمس أو تعديل الملفات المحظورة الثلاثة:
   - `game_client.py`
   - `core/onemt_auth.py`
   - `core/onemt_bot.py`
4. تشغيل سكربتات فحص الترقيم والأداء الخاصة بـ M2 للتأكد من مطابقة خفض الباندويث وسرعة الاستجابة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Planned Steps)

1. **الخطوة الأولى:** التحقق من حالة الملفات المحظورة وسجل التعديلات عبر `git status --porcelain`.
2. **الخطوة الثانية:** تشغيل بناء الواجهة الأمامية (`npm run build`) داخل مجلد `dashboard/`.
3. **الخطوة الثالثة:** تشغيل الجناح الكامل لاختبارات المنصة (`python tests/run_all_tests.py`).
4. **الخطوة الرابعة:** تشغيل سكربتات التحقق الخاصة بالترقيم والأداء (`tools/verify_m6_admin_scalability.py` و `tools/stress_m6_master_detail.py`).
5. **الخطوة الخامسة:** توثيق النتائج الفعلية والمخرجات في تقرير التسليم `handoff.md`.

---

## 3. الأوامر والملفات المستهدفة بالتفصيل مع النتيجة المتوقعة (Target Commands & Expected Output)

| # | الأمر المراد تنفيذه | المسار / المجلد المستهدف | النتيجة المتوقعة |
|---|---|---|---|
| 1 | `git status --porcelain` | `e:\osmanli` | تأكيد أن `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` غير معدلة نهائياً |
| 2 | `powershell -Command "Set-Location dashboard; npm run build"` | `e:\osmanli\dashboard` | خروج بكود 0 و 0 أخطاء TypeScript وتوليد أصول Vite بنجاح |
| 3 | `python tests/run_all_tests.py` | `e:\osmanli` | نجاح كافة الاختبارات الـ 30 (30/30 PASS) بنسبة 100% |
| 4 | `python tools/verify_m6_admin_scalability.py` | `e:\osmanli` | اجتياز جميع فحوصات الترقيم والتقسيم 38/38 |
| 5 | `python tools/stress_m6_master_detail.py` | `e:\osmanli` | اجتياز 36/36 اختبار ضغط وخفض الحجم بنسبة >98% |

---
