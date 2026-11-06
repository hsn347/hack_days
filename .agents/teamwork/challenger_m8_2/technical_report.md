# تقرير فني تحضيري: خطة التحدي التجريبي لحالة الواجهة، المخطط، والتكامل الميداني
## Empirical Stress Testing Plan for UI Lifecycle, Schema, and Victory Audit (Milestone 8)

**المعرف:** Challenger M8-2 (Chaos UI, State & Schema Challenger)  
**المسار:** `.agents/teamwork/challenger_m8_2/technical_report.md`  
**التاريخ والوقت:** 2026-11-02T21:00:00Z  
**المرجع التنظيمي:** `AGENTS_CONSTITUTION.md` & `GEMINI.md` (القاعدتان 4 و 5)  

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

بناءً على متطلبات المرحلة M8 ودستور الوكلاء، فإن تقارير وادعاءات الوكيل المنفذ (Worker M8) لا تُعتمد مطلقاً دون تدقيق تجريبي عدائي مستقل (Empirical Challenger Audit). لا نثق في السجلات أو الادعاءات ما لم نقم بتشغيل وفحص واختبار كافة الخصائص بأنفسنا محلياً.

المطلوب إخضاعه للتدقيق والتحدي التجريبي هو:
1. **مخطط قاعدة البيانات وفهارس التعبيرات (SQLite Schema & Expression Indexes):**
   - هل تم بالفعل تطبيق فهارس التعبيرات `LOWER(email)` و `LOWER(user_id)` في قاعدة البيانات الحقيقية `database/castles.db` وليس فقط في كود التهيئة؟
   - فحص `PRAGMA index_list('castle_states')`, `PRAGMA index_list('users')`, و `PRAGMA index_info` واستعلامات `sqlite_master`.
2. **توحيد مصدر الحقيقة في الواجهة ودورة حياة تفريغ المكونات (CastleCard & TaskTabContent Lifecycle):**
   - هل تم التخلص نهائياً من أي `useState` محلي يكرر حالة البوت الحية في `CastleCard.tsx`؟
   - هل تم عزل نقر الحاوية السطحية للبطاقة عبر `e.stopPropagation()` لمنع التعارض مع عناصر التحكم والأزرار الداخلية؟
   - هل تفريغ المكون `TaskTabContent` عند مغادرته (unmount) يقوم بمزامنة فورية لكاش TanStack Query عبر `queryClient.setQueryData` والتخزين المحلي، وهل يعالج تعارض OCC (409) بشكل سليم؟
3. **انعدام تام لنوافذ المتصفح الحاجبة (Zero Blocking Dialogs Scan):**
   - فحص جنائي كامل عبر AST / Regex لجميع ملفات `dashboard/src/**/*.{ts,tsx,js,jsx}` للتأكد من عدم وجود أي استدعاء متبقٍ لـ `window.confirm`, `confirm(`, `alert(`, أو `window.alert`.
   - فحص بديل الحوار `ActionConfirmModal.tsx` من حيث: React Portal، تنظيف مستمع أحداث لوحة المفاتيح `removeEventListener('keydown')` عند الـ unmount، حالة التعطيل أثناء الحفظ `isPending`، وسمات الـ A11y (`role="dialog"`, `aria-modal="true"`).
4. **التماثل الثلاثي للترجمة (Exact Symmetric Trilingual Parity):**
   - فحص ملفات اللغات الثلاث (`ar.json`, `en.json`, `tr.json`) والتأكد تجريبياً من امتلاكها لنفس المفاتيح الـ 788 تماماً مع عدم وجود أي مفتاح مفقود أو مكرر أو فارغ.
5. **التنفيذ التجريبي لحزم الاختبار والبناء الكاملة:**
   - تشغيل `python tools/verify_m8_dual_field.py` والتحقق من نتائجه الـ 16 فحصاً.
   - تشغيل `python tests/run_all_tests.py` والتأكد من اجتياز 30/30 اختباراً عبر الطبقات الأربع.
   - تشغيل `npm run build` في `dashboard/` للتأكد من نجاح تجميع TypeScript وVite دون أي خطأ.

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Methodological Steps)

1. **الخطوة 1: فحص قاعدة بيانات SQLite المستقل:**
   - كتابة وتنفيذ كود بايثون سريع يفحص ملف `database/castles.db` مباشرة عبر مكتبة `sqlite3`، مستخدماً استعلامات الميتاداتا:
     - `SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('castle_states', 'users');`
     - فحص وجود `idx_castle_states_lower_email`, `idx_castle_states_lower_user`, `idx_users_lower_email`.
     - تنفيذ `EXPLAIN QUERY PLAN` على استعلامات `SELECT * FROM castle_states WHERE LOWER(email) = ?` للتأكد من استخدام الفهرس الفعلي بدلاً من المسح الكامل (SCAN TABLE).
2. **الخطوة 2: الفحص الجنائي الثابت والمجهري لكود الواجهة (AST / Code Inspection):**
   - فحص دقيق لـ `dashboard/src/components/accounts/CastleCard.tsx` للتأكد من عدم وجود تفرع للحالة أو استدعاءات `useState` متنافسة.
   - فحص دقيق لـ `dashboard/src/components/accounts/TaskTabContent.tsx` للتأكد من آلية الـ unmount flush ودعم الـ OCC versioning ومعالجة الخطأ 409.
   - فحص `ActionConfirmModal.tsx` وسلامة تنظيف مستمعات الأحداث واستخدام `createPortal`.
3. **الخطوة 3: المسح الشامل لخلو الواجهة من النوافذ الحاجبة:**
   - كتابة وفحص استعلامات بحث نصية وشبه بنيوية (Regex/AST) تمسح كافة ملفات `dashboard/src/` بحثاً عن أي `confirm(` أو `alert(`.
4. **الخطوة 4: الفحص البرمجي الرياضي لتطابق اللغات الثلاث:**
   - تحميل ملفات JSON الثلاثة (`ar.json`, `en.json`, `tr.json`) باستخدام بايثون، استخراج كافة المفاتيح المتداخلة (flattened keys)، وحساب التقاطع والفروق المتناظرة (symmetric difference) للتأكد الرياضي من أن الفارق بين أي ملفين = مجموعة خالية (`set()`).
5. **الخطوة 5: التشغيل الميداني لأجنحة الاختبارات:**
   - تشغيل `python tools/verify_m8_dual_field.py` والتقاط المخرجات الحية.
   - تشغيل `python tests/run_all_tests.py` والتقاط المخرجات الحية.
   - تشغيل أمر البناء للواجهة في بيئة powershell والتحقق من كود الخروج (0).
6. **الخطوة 6: التوثيق وتقرير التسليم النهائي:**
   - كتابة `handoff.md` وفق النموذج الخماسي الصارم وتقديم الحكم النهائي الصريح.

---

### 3. الأوامر التي ستُنفذ بالتفصيل والنتيجة المتوقعة (Commands & Expected Results)

| # | الأمر المراد تنفيذه | الغرض والهدف | النتيجة المتوقعة |
|---|----------------------|--------------|-------------------|
| 1 | `python -c "import sqlite3; conn = sqlite3.connect('database/castles.db'); ..."` | فحص فهارس التعبيرات و EXPLAIN QUERY PLAN | ظهور الفهارس الثلاثة واعتماد `USING INDEX` في خطة الاستعلام |
| 2 | `python -c "import json; ..."` | فحص التماثل الثلاثي لملفات `ar.json`, `en.json`, `tr.json` | 788 مفتاحاً متطابقاً بنسبة 100%، والفارق الصفري |
| 3 | `python tools/verify_m8_dual_field.py` | تشغيل أداة التحقق الميداني المزدوجة الشاملة | خروج برمز 0 واجتياز 16/16 فحصاً بنجاح |
| 4 | `python tests/run_all_tests.py` | تشغيل حزمة اختبارات المنصة المعزولة | خروج برمز 0 واجتياز 30/30 اختباراً بنجاح |
| 5 | `powershell -Command "Set-Location dashboard; npm run build"` | اختبار تجميع TypeScript وحزم Vite | خروج برمز 0 وبناء مجلد `dashboard/dist` بنجاح دون أي خطأ |

---
**الالتزام الصارم بالضوابط:**
- التنفيذ محلي 100% داخل `e:\osmanli`.
- لا يوجد أي اتصال بخوادم خارجية أو قواعد بيانات الإنتاج.
- هذا التقرير يسبق تنفيذ أي أمر في الطرفية التزاماً بالقاعدة 5 من `GEMINI.md`.
