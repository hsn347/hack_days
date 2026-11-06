# تقرير فني مستقل وخطة الاختبار التجريبي المعادي — المرحلة السابعة (Milestone 7)
## Empirical Adversarial Stress Test Plan: Trilingual Parity, Non-Blocking Dialogs & Resource Lifecycle

**المعرف:** Challenger M7 (Instance 1)  
**التاريخ:** 2026-11-02  
**الحالة:** قبل تنفيذ الأوامر (Pre-Execution)  
**المرجع:** AGENTS_CONSTITUTION.md & GEMINI.md (القواعد 1، 2، 4، 5)

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Objective Rationale)
في إطار المرحلة السابعة (M7) من مشروع إعادة هندسة منصة عثمانلي ولوحة التحكم، قام الوكيل المطور (Worker M7) بالإجراءات التالية:
1. استبدال حوارات المتصفح الافتراضية المعطلة لخيط التنفيذ (`window.confirm` و `window.alert`) بمكون حوارات حديث وسريع (`ActionConfirmModal.tsx`).
2. مزامنة ملفات الترجمة للغات الثلاث (`ar.json`, `en.json`, `tr.json`) لمعالجة المفاتيح المفقودة مثل `plans.accountsCount_one` و `tabs.gold_bot`.
3. تطبيق عزل نطاقات التجار (Merchant Domain Isolation) في مسار `GET /api/admin/users/{uid}/castles` في `api_server.py`.
4. التحقق من تنظيف الموارد (Resource Cleanup) في `AdminLiveProcesses.tsx`.

**دور المتحدي التجريبي (Empirical Challenger):**
عملاً بمبدأ "Never trust claims without running verification code":
- فحص شجرة `dashboard/src/` بالكامل فحصاً صارماً وشاملاً عبر الـ AST والرموز لمنع أي استدعاء صريح أو خفي أو غير مباشر لـ `window.confirm` أو `window.alert` أو `confirm(` أو `alert(`.
- اختبار تجريبي شامل لتناظر ملفات اللغات الثلاث على مستوى المفاتيح الفردية، وتفرعات الكائنات، والقيم الخالية، وتطابق أعداد المفاتيح (100% key symmetry across all three locales).
- اختبار دورة حياة النوافذ المنبثقة (Modals): التحقق من فك ارتباط مستمعي لوحة المفاتيح (`Escape`) وتنظيف حالة الـ DOM لتفادي تسريب الذاكرة أو حجب التمرير (`body overflow`).
- التحقق من الالتزام بالقاعدة الثانية من GEMINI.md: واجهة مستخدم سريعة، رشيقة، بدون بطء في الحركات (Snappy transitions <= 0.25s)، وبدون حشو كلامي في نصوص الأزرار والتنبيهات.

---

### 2. المنطق والخطوات التجريبية التي سيتم تطبيقها (Methodology & Logic Chain)

#### الخطوة 1: تصميم وتأليف أداة فحص تجريبية شاملة ومعادية (`tools/stress_m7_trilingual_dialogs.py`)
الأداة ستتضمن 6 مستويات من الاختبارات الصارمة:
- **Level 1: Deep AST & Lexical Code Scan:**
  مسح كامل لجميع ملفات TypeScript وJavaScript في كامل مجلد `dashboard/src/` (وليس فقط pages وcomponents) للبحث عن أي استدعاء لـ `window.confirm`, `window.alert`, `window.prompt`, أو الاستدعاءات العامة `confirm(`, `alert(`, مع استبعاد الكلمات داخل التعليقات أو النصوص أو أسماء المتغيرات المشروعة.
- **Level 2: Strict Trilingual Parity & Value Integrity:**
  قراءة `ar.json`, `en.json`, `tr.json`.
  1. التحقق من صحة صياغة JSON دون أخطاء.
  2. مقارنة المفاتيح المسطحة (Flattened dot-notation keys) وتأكيد أن الفروق بين أي زوج من اللغات تساوي صفراً تماماً.
  3. التحقق من تطابق أنواع القيم لكل مفتاح (String vs Object vs Array).
  4. التحقق من خلو القيم من النصوص الفارغة تماماً أو المساحات البيضاء.
- **Level 3: Modal Keyboard & Event Lifecycle Stress:**
  فحص جميع مكونات المودال في `dashboard/src/components/` والتأكد من:
  1. وجود معالج `Escape` لإغلاق المودال برمجياً.
  2. وجود استدعاء صريح لإلغاء المعالج `removeEventListener('keydown', ...)` في دالة التنظيف الخاصة بـ `useEffect`.
  3. فحص معالجة `overflow` على مستوى `document.body` وضمان عدم ترك الجسم في حالة `overflow: hidden` عالقة بعد إلغاء التركيب (Unmount).
- **Level 4: Snappy UX & Anti-Clutter Guardrails (GEMINI.md Rule 2):**
  1. فحص سرعة انتقالات `framer-motion` في مكونات المودال والتأكد أن مدة الانتقال <= 0.25s لضمان السرعة والرشاقة ومنع الحركات البطيئة (Sluggish animations).
  2. فحص صياغة نصوص الأزرار والمفاتيح والتأكد من خلوها من العبارات الحشوية الطويلة.
- **Level 5: Backend Merchant Isolation Logic:**
  التحقق البرمجي الدقيق من احتواء دالة `get_admin_user_castles` في `api_server.py` على التحقق الأمني `_verify_merchant_access_to_user` مع جلب بيانات المستخدم المستهدف.
- **Level 6: Resource Cleanup & In-Memory Timer Lifecycles:**
  التأكد من تنظيف مؤقتات `setInterval` بـ `clearInterval` في مكونات المراقبة الحية.

#### الخطوة 2: تشغيل سكريبت التحقق الأساسي `tools/verify_m7_ux_lifecycle.py`
تشغيل السكريبت المعتمد ومطابقة نتائجه مع التقرير.

#### الخطوة 3: تشغيل سكريبت الاختبار التجريبي المعادي `tools/stress_m7_trilingual_dialogs.py`
تشغيل السكريبت المعادي الجديد والتأكد من اجتياز كافة التحديات بنسبة 100%.

#### الخطوة 4: تشغيل بناء واجهة المستخدم بنظام Typescript الصارم
`powershell -Command "Set-Location dashboard; npm run build"` للتحقق من عدم وجود أي خطأ نوعي أو برمجي في الواجهة وحزم الإنتاج.

#### الخطوة 5: تشغيل جناح الاختبارات الموحد للباك إند وقاعدة البيانات
`python tests/run_all_tests.py` للتأكد من عدم وجود أي تراجع (zero regressions).

---

### 3. الأوامر والملفات والنتائج المتوقعة بالتفصيل (Detailed Execution Plan & Expected Outcomes)

| # | الأمر / الملف | الغرض والوصف | النتيجة المتوقعة |
|---|----------------|----------------|-------------------|
| 1 | `write_to_file: tools/stress_m7_trilingual_dialogs.py` | إنشاء أداة الاختبار التجريبي المعادي الشامل لـ M7 | إنشاء الأداة بنجاح |
| 2 | `python tools/stress_m7_trilingual_dialogs.py` | تشغيل الاختبار المعادي للغات والحوارات ودورة الحياة | 100% PASS لجميع المستويات |
| 3 | `python tools/verify_m7_ux_lifecycle.py` | تشغيل أداة التحقق من دورة حياة تجربة المستخدم | 22/22 PASS (100%) |
| 4 | `powershell -Command "Set-Location dashboard; npm run build"` | بناء الواجهة الأمامية والتحقق من سلامة الأنواع `tsc && vite build` | 0 errors، اكتمال البناء في أقل من ثانيتين |
| 5 | `python tests/run_all_tests.py` | تشغيل الاختبارات الأربعة الموحدة للنظام | 30/30 PASS في ~4 ثوانٍ |
| 6 | `write_to_file: handoff.md` | كتابة تقرير التسليم النهائي المكون من الأقسام الخمسة مع الحكم الصريح | تقرير مفصل وحكم نهائي صريح |

---
*تم إعداد هذا التقرير والتصديق عليه قبل تنفيذ أي أمر على النظام التزاماً بالقاعدة الخامسة من GEMINI.md.*
