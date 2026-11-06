# تقرير فني مستقل: متطلبات المرحلة السابعة (Milestone 7)
# UX Lifecycle, Confirm Modals, Trilingual Consistency & Resource Cleanup

**تاريخ الإنشاء:** 2026-11-02T20:25:00Z  
**الوكيل المنفذ:** Worker M7 (`teamwork_worker`)  
**المشروع:** `e:\osmanli`  
**المرجع:** GEMINI.md (القاعدة 2، 4، 5) و AGENTS_CONSTITUTION.md (المادة 13) و DISPATCH.md  

---

## 1. التشخيص وسبب طلب الإجراء (Diagnosis & Root Cause Analysis)

### 1.1 النوافذ المنبثقة المتزامنة الحاصرة (Blocking Browser Confirm Dialogs)
- **المشكلة:** كشفت المراجعة الفاحصة للكود المصدري في `dashboard/src/pages/` عن وجود 6 استدعاءات لنظام المتصفح المتزامن `confirm(...)`:
  1. `Admin.tsx:559` - تأكيد رفض قلعة معلقة (`rejectCastle`).
  2. `Admin.tsx:583` - تأكيد حذف قلعة نشطة لمستخدم (`deleteCastle`).
  3. `Admin.tsx:693` - تأكيد الموافقة السريعة على مستخدم جديد مع باقة تجريبية (`handleQuickApprove`).
  4. `Admin.tsx:708` - تأكيد الموافقة الجماعية على كافة المستخدمين المعلقين (`handleApproveAllPending`).
  5. `Admin.tsx:729` - تأكيد حظر / إلغاء حظر المستخدم (`handleBan`).
  6. `AdminLiveProcesses.tsx:71` - تأكيد إنهاء وإيقاف عملية بوت تعمل بالذاكرة (`handleStopProcess`).
- **الأثر:** دوال المتصفح الأصلية مثل `window.confirm` تحجب الـ JavaScript Event Loop بالكامل، وتوقف الرسوم المتحركة وعمليات التزامن وتحديث الواجهة، كما تفتقر إلى مظهر عصري، ولا تدعم التبديل اللوني الفاتح/الداكن (Theme Contrast)، وتخالف توجيهات GEMINI.md (Rule 2) التي تشترط واجهة خفيفة، سريعة، وسلسة بدون حشو أو بطء، مع سهولة استخدام على الجوال بدون حوارات نظام مزعجة.

### 1.2 ثغرة عزل التاجر في استعلام تفاصيل القلاع (Merchant Isolation Gap)
- **المشكلة:** في المسار `/api/admin/users/{uid}/castles` المنفذ في `api_server.py:1871-1889` لدعم خاصية التحميل عند الطلب (Master-Detail Lazy Loading)، يقوم المسار بالتحقق من `require_admin`، ولكنه **لا يستدعي** دالة الفحص `_verify_merchant_access_to_user(admin, db.get_user(uid))`.
- **الأثر:** مدراء التجار (`merchant_admin`) قد يتمكنون من إرسال طلبات بالمعرف `uid` لمستخدمين يتبعون تجاراً آخرين أو الدومين الرئيسي، مما يمكنهم من استعراض تفاصيل وإعدادات قلاع مستخدمين خارج نطاق دومين التاجر التابعين له. هذا يتعارض مع مبدأ العزل الصارم (Account Isolation & Data Privacy) المشترط في R6 و R8.

### 1.3 الاتساق اللغوي الثلاثي (Trilingual Consistency across Locales)
- **المشكلة:** ملفات اللغات الثلاث في `dashboard/src/locales/` (`ar.json`, `en.json`, `tr.json`) تحتوي على تفاوتات حجمية (`ar.json` بحجم 50.5KB مقارنة بـ 37.6KB لـ `en.json` و 40.2KB لـ `tr.json`). عند إضافة نصوص تأكيدات جديدة أو مفاتيح ترقيم أو حالات، يجب التأكد من مطابقة جميع المفاتيح عبر اللغات الثلاث بنسبة 100% بدون أي مفاتيح مفقودة أو نصوص صلبة غير مترجمة.

### 1.4 تنظيف الموارد ودورة حياة المكونات (Resource Cleanup & Unmount Lifecycle)
- **المشكلة:** ضرورة التأكد من أن جميع المؤقتات (`setInterval`, `setTimeout`) ومستمعي الأحداث (`keydown`, `click`) وإلغاء الطلبات الشبكية يتم تنظيفها بالكامل في دوال الـ cleanup لدوال `useEffect` لمنع تسريبات الذاكرة وتراكم المستمعين.

---

## 2. المنطق والخطوات الهندسية المتبعة (Implementation Logic & Architecture)

### الخطوة 1: بناء مكون تأكيد شامل، متجاوب، وسريع (`ActionConfirmModal`)
- إنشاء المكون الموحد `dashboard/src/components/common/ActionConfirmModal.tsx` بميزات:
  - غير حاظر (Non-blocking): يستخدم Framer Motion و React Portal إلى `document.body` مع خلفية معتمة خفيفة `backdrop-blur-sm`.
  - يدعم وضعيتي الداكن والفاتح (Dark/Light Mode Contrast) باحترافية عالية مع حدود شفافة رقيقة وتباين نصوص ملائم لـ WCAG AA.
  - يدعم مفتاح `Escape` للإغلاق والنقر الخارجي، وحالة التحميل أثناء التنفيذ (`isPending`).
  - نصوص واضحة ومباشرة بدون حشو (وفق GEMINI.md Rule 2).
  - متغيرات ألوان متعددة حسب طبيعة العملية: `danger` (أحمر للعمليات الحساسة كالحذف والإنهاء)، `warning` (برتقالي للحظر)، `success`/`primary` (أخضر/أزرق للموافقة والتفعيل).

### الخطوة 2: استبدال جميع استدعاءات `confirm(...)` في `Admin.tsx`
- في `Admin.tsx`:
  - إزالة كافة استدعاءات `if (!confirm(...))` من:
    - زر رفض القلعة المعلقة في قائمة القلاع.
    - زر حذف القلعة النشطة في قائمة القلاع.
    - زر الموافقة السريعة على مستخدم جديد (`handleQuickApprove`).
    - زر الموافقة الجماعية على المستخدمين المعلقين (`handleApproveAllPending`).
    - زر الحظر / فك الحظر (`handleBan`).
  - توحيد إدارة الحالة عبر كائن حالة تأكيد أنيق `confirmActionState`:
    ```typescript
    interface ConfirmActionState {
      isOpen: boolean
      title: string
      message: string
      confirmText?: string
      variant?: 'danger' | 'warning' | 'primary'
      onConfirm: () => void | Promise<void>
    }
    ```
  - ربط كافة الأزرار بنافذة التأكيد، مع بقاء الواجهة نشطة واستجابة نقية سريعة.

### الخطوة 3: استبدال استدعاء `confirm(...)` في `AdminLiveProcesses.tsx`
- في `AdminLiveProcesses.tsx`:
  - إزالة `if (!confirm(t('admin.live.confirmStop', { target: targetName })))`
  - فتح نافذة التأكيد قبل إنهاء عملية البوت بالذاكرة، مع خيار الإلغاء السلس وتأكيد التنفيذ.

### الخطوة 4: سد ثغرة عزل التاجر في `api_server.py:get_admin_user_castles`
- في `api_server.py`:
  - تعديل الدالة `get_admin_user_castles(uid: str, admin: Dict[str, Any] = Depends(require_admin))`
  - جلب بيانات المستخدم المستهدف عبر `target_user = db.get_user(uid)`
  - استدعاء فحص الصلاحية الصارم:
    `_verify_merchant_access_to_user(admin, target_user)`
  - هذا الفحص يقوم برمي `HTTPException(404, "المستخدم غير موجود")` إذا كان المستخدم غير موجود، و `HTTPException(403, "غير مصرح لك بإدارة هذا المستخدم خارج نطاق دومينك")` إذا كان التاجر يحاول استعراض قلاع مستخدمين خارج نطاق دوميناته.

### الخطوة 5: التحقق من الاتساق اللغوي الكامل ومزامنة المفاتيح عبر `ar`, `en`, `tr`
- فحص جميع المفاتيح في `dashboard/src/locales/` ومزامنة أي مفاتيح مستخدمة في نوافذ التأكيد أو الترقيم أو الحالات في الملفات الثلاثة (`ar.json`, `en.json`, `tr.json`).
- ضمان دعم RTL/LTR الكامل والتأكد من خلو ملفات JSON من أخطاء البنية.

### الخطوة 6: برمجة أداة التحقق الآلية الشاملة `tools/verify_m7_ux_lifecycle.py`
- بناء سكريبت تحقق مستقل ينفذ 5 طبقات فحص (Tiers 1-5):
  - **Tier 1:** فحص كامل لكافة ملفات `dashboard/src/` والتأكد التام من خلوها من أي استدعاء لـ `window.confirm`, `window.alert`, `window.prompt`, أو `confirm(...)` الخام.
  - **Tier 2:** فحص الاتساق اللغوي عبر `ar.json`, `en.json`, `tr.json` بنسبة مطابقة وتكافؤ 100%.
  - **Tier 3:** فحص كود الباك إند والتأكد من وجود استدعاء `_verify_merchant_access_to_user` داخل `get_admin_user_castles` وعزل البيانات.
  - **Tier 4:** فحص دورة حياة المكونات ومستمعي الأحداث وتنظيف المؤقتات والـ `useEffect cleanup`.
  - **Tier 5:** فحص التباين اللوني والتجاوب في صفوف الشاشات المحمولة.

---

## 3. الملفات والسطور المستهدفة والنتائج المتوقعة (Affected Files & Expected Outcomes)

| الملف المستهدف | طبيعة التعديل | السطور التقريبية | النتيجة المتوقعة |
|---|---|---|---|
| `dashboard/src/components/common/ActionConfirmModal.tsx` | ملف جديد | جديد (حوالي 120 سطر) | توفير مكون حوار تأكيد غير حاظر، أنيق، وسريع التفاعل وفق GEMINI.md |
| `dashboard/src/pages/Admin.tsx` | تعديل | 550-590, 690-735, 1290-1310 | استبدال 5 استدعاءات `confirm(...)` بحوارات مودال عصرية غير حاظرة |
| `dashboard/src/pages/AdminLiveProcesses.tsx` | تعديل | 69-89, 480-520 | استبدال استدعاء `confirm(...)` بمودال التأكيد لإنهاء العمليات الحية |
| `api_server.py` | تعديل | 1871-1889 | تفعيل `_verify_merchant_access_to_user` لمنع تسريب بيانات القلاع بين التجار |
| `dashboard/src/locales/ar.json` | مراجعة ومزامنة | الأقسام المحدثة | إضافة مفاتيح التأكيدات الموحدة والتأكد من صحة التنسيق |
| `dashboard/src/locales/en.json` | مراجعة ومزامنة | الأقسام المحدثة | مزامنة الترجمة الإنجليزية المقابلة بدقة واختصار |
| `dashboard/src/locales/tr.json` | مراجعة ومزامنة | الأقسام المحدثة | مزامنة الترجمة التركية المقابلة بدقة واختصار |
| `tools/verify_m7_ux_lifecycle.py` | سكريبت تحقق جديد | جديد (حوالي 300 سطر) | إجراء فحص شامل بنسبة نجاح 100% لكافة معايير المرحلة M7 |

---

## 4. خطة الاختبار والتحقق المستقل (Verification Commands)
بعد إتمام التعديلات البرمجية محلياً:
1. تشغيل أداة التحقق المخصصة:
   `python tools/verify_m7_ux_lifecycle.py`
2. تشغيل فحص البناء والأنماط للواجهة الأمامية:
   `powershell -Command "Set-Location dashboard; npm run build"`
3. تشغيل الحزمة الشاملة للاختبارات للتأكد من عدم وجود أي تراجع (Zero Regressions):
   `python tests/run_all_tests.py` (يجب أن يجتاز 30/30)

تم إعداد هذا التقرير كخطوة إلزامية أولى وقاطعة قبل الشروع في أي تعديل على الكود، امتثالاً للقاعدة رقم 5 في GEMINI.md.
