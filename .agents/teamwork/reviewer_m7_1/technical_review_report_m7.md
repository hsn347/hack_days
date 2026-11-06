# تقرير فني مستقل: خطة الفحص والتحقق المستقل للمرحلة السابعة (Milestone 7 Review)
# UX Lifecycle, Confirm Modals, Trilingual Consistency & Resource Cleanup

**تاريخ الإنشاء:** 2026-11-02T20:37:00Z  
**الوكيل الفاحص:** Reviewer M7 (`teamwork_reviewer` / `critic`)  
**المشروع:** `e:\osmanli`  
**المرجع:** GEMINI.md (القواعد 2، 4، 5) و AGENTS_CONSTITUTION.md (المادة 13) و DISPATCH.md  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Purpose)

أكمل الوكيل `Worker M7` تنفيذ تعديلات المرحلة السابعة (Milestone 7) والتي شملت:
1. بناء المكون الموحد غير الحاظر `ActionConfirmModal.tsx` بدعم للـ Portals والـ Escape handler وتباين الألوان الداكن والفاتح.
2. استبدال كافة استدعاءات `confirm(...)` الحاظرة (6 استدعاءات) في `Admin.tsx` و `AdminLiveProcesses.tsx`.
3. مزامنة قواميس اللغات الثلاث (`ar.json`, `en.json`, `tr.json`) لتحقيق تكافؤ مفاتيح بنسبة 100%.
4. سد ثغرة عزل التاجر في مسار `GET /api/admin/users/{uid}/castles` في `api_server.py`.
5. تنظيف الموارد في دورة حياة المكونات (`timerRef` و event listeners و console logs).

يتطلب دور المراجع والمشكك العدائي (Reviewer & Adversarial Critic) التحقق المستقل من صحة هذه الادعاءات، والتأكد من خلو العمل من أي غش برمجيات (Hardcoded test results أو Facade implementations) أو انكسارات في بناء الواجهة أو تراجعات في الاختبارات.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Steps)

1. **التحقق من الكود المصدري المستقل (Static Audit):**
   - فحص بنية `ActionConfirmModal.tsx`، والتأكد من عدم وجود تسريب لمستمعي الأحداث أو حجب لـ Event Loop.
   - فحص استدعاءات المودال في `Admin.tsx` و `AdminLiveProcesses.tsx`.
   - فحص مسار `api_server.py:get_admin_user_castles` للتأكد من استدعاء `_verify_merchant_access_to_user`.
   - فحص تكافؤ ملفات اللغات الثلاث.

2. **تشغيل أوامر التحقق والاختبار المستقل (Independent Command Execution):**
   - تشغيل أداة التحقق الشاملة للمرحلة السابعة: `python tools/verify_m7_ux_lifecycle.py`.
   - تشغيل فحص البناء والأنماط للواجهة الأمامية: `npm run build` للتأكد من خلو الـ TypeScript والـ JSX من أي أخطاء ترجمة.
   - تشغيل حزمة الاختبارات الشاملة: `python tests/run_all_tests.py` للتأكد من سلامة النظام الإجمالية وعدم حدوث أي تراجع (Zero Regressions).
   - تشغيل أداة فحص قابلية التوسع للمرحلة السادسة: `python tools/verify_m6_admin_scalability.py` للتأكد من سلامة المسارات المعدلة.

3. **التحدي العدائي واختبار حالات الحافة (Adversarial Stress Testing):**
   - اختبار سيناريوهات تعليق المودال عند الخطأ.
   - اختبار التفاعل عند ضغط المفاتيح المتكرر (`Escape`, Enter).
   - اختبار محاولة الوصول كتاجر لمستخدم من خارج النطاق.

---

## 3. الأوامر التي ستُنفذ بالتفصيل والنتيجة المتوقعة (Commands & Expected Outcomes)

| الأمر المخطط تنفيذه | الغرض الهندسي | النتيجة المتوقعة |
|---|---|---|
| `python tools/verify_m7_ux_lifecycle.py` | التحقق الآلي من خلو الواجهة من `confirm()` ومزامنة اللغات وعزل التاجر وتنظيف الموارد | اجتياز 22/22 بنسبة 100% |
| `powershell -Command "Set-Location dashboard; npm run build"` | التحقق من ترجمة TypeScript وبناء الحزمة الإنتاجية عبر Vite بدون أي خطأ | كود الخروج 0 بدون أخطاء |
| `python tests/run_all_tests.py` | تشغيل كافة اختبارات النظام للتأكد من عدم حدوث أي تراجع | اجتياز 30/30 بنسبة 100% |
| `python tools/verify_m6_admin_scalability.py` | فحص عدم تراجع مسارات المسؤول المعدلة | اجتياز 38/38 بنسبة 100% |

تم إنشاء هذا التقرير الفني كإجراء استباقي ملزم قبل تنفيذ أي أمر طرفي وفق القاعدة الخامسة من GEMINI.md.
