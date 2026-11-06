# تقرير المراجعة الفنية والاختبار العدائي — Milestone 6
## Technical Review & Adversarial Stress Testing Plan for Milestone 6

**تاريخ التقرير**: 2026-11-02T20:13:00Z  
**المراجع والناقد العدائي**: Reviewer M6 (Instance 2) — `.agents/teamwork/reviewer_m6_2/`  
**الهدف**: مراجعة عدائية وفحص هندسي مستقل لمخرجات المرحلة السادسة (Milestone 6: Admin Dashboard Scalability, Client-side Pagination & Master-Detail Table Splitting).

---

### 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
وفقاً لتوجيه المشرف والدستور التنظيمي (AGENTS_CONSTITUTION.md)، فإن دور المراجع والناقد العدائي يقتضي:
1. الفحص الموضوعي المستقل لصحة ومطابقة التعديلات المنفذة في المرحلة السادسة للمتطلبات R5 و R4 و R6 و R8.
2. الكشف عن أي تلاعب بالنزاهة البرمجية (Integrity Violations)، مثل الواجهات الصورية (Facades) أو النتائج المسبقة التشفير (Hardcoded mocks) أو الالتفاف على مهام التحقق الحقيقية.
3. التقييم العدائي الصارم لأربعة محاور حرجة:
   - سلوك النقر السريع المتكرر (Rapid accordion toggling) في `AdminUsersCastles.tsx` ومنع تكرار الطلبات الشبكية (In-flight deduplication / AbortController).
   - نطاق إبطال الكاش (Scoped cache invalidation) عند تعديل أو حذف قلعة (هل يقتصر الإبطال على المستخدم المعني أم يمتد عشوائياً لكامل القائمة؟).
   - حالات الحافة في التصفح والترقيم (Pagination edge cases) وإعادة الضبط إلى الصفحة 1 عند البحث أو التصفية في `Admin.tsx`.
   - فرض صلاحيات المسؤول (Admin authentication & authorization enforcement) وعزل النطاقات (Tenant isolation / BOLA prevention) على المسارات الجديدة المضافة في `api_server.py`.
4. التحقق العملي عبر تشغيل الأوامر المحددة في الدليل:
   - `python tools/verify_m6_admin_scalability.py`
   - `powershell -Command "Set-Location dashboard; npm run build"`
   - `python tests/run_all_tests.py`

---

### 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Execution Steps)
1. **الخطوة الأولى: الفحص المصدري العدائي (Static Code & Architecture Audit)**:
   - تدقيق منطق `Admin.tsx` للتأكد من حسابات `startIndex`, `endIndex`, `validPage`, `totalPages`, وتأثير الفلاتر المتزامنة.
   - تدقيق `AdminUsersCastles.tsx` ومكون `UserCastlesDetail` وتفاعل TanStack Query مع مفتاح `['admin_user_castles', user.uid]`.
   - تدقيق مسارات الباك إند: `GET /api/admin/users-castles/summary` و `GET /api/admin/users/{uid}/castles` ومقارنة صلاحيات `require_admin` مع العزل المتعدد للمستأجرين (`_verify_merchant_access_to_user`).
   - فحص نزاهة أداة التحقق `tools/verify_m6_admin_scalability.py` للتأكد من أنها تفحص الكود الحقيقي ولا تحتوي على نجاحات شكلية أو صورية.
2. **الخطوة الثانية: تنفيذ أوامر التحقق المستقل محلياً (Independent Verification Execution)**:
   - تنفيذ سكربت التحقق التخصصي `tools/verify_m6_admin_scalability.py`.
   - بناء مشروع لوحة التحكم `dashboard` عبر `npm run build` للتأكد من صحة TypeScript وعدم وجود أخطاء في الـ Chunks المقتطعة عبر `React.lazy`.
   - تشغيل حزمة الاختبارات الشاملة للمنصة `tests/run_all_tests.py` لضمان عدم حدوث أي انحدار (Regressions).
3. **الخطوة الثالثة: صياغة التحديات العدائية والتوصيات وإصدار القرار (Verdict)**:
   - توثيق الملاحظات والنتائج الحرجة وتأثيرها الأمني والتشغيلي.
   - كتابة تقرير التسليم الشامل `handoff.md` المتضمن الأقسام الخمسة الإلزامية.
   - إرسال رسالة الإنجاز إلى المشرف العام (`44132d7d-07d0-4709-a292-a8e4727a82fd`).

---

### 3. الأوامر والملفات والسطور التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)

| # | الأمر المراد تنفيذه | الغرض والملفات المفحوصة | النتيجة المتوقعة |
|---|---------------------|--------------------------|------------------|
| 1 | `python tools/verify_m6_admin_scalability.py` | التحقق من 38 فحصاً تغطي الترقيم، تجزئة الجداول، مفاتيح الكاش، ومسارات الباك إند | نجاح 38/38 فحصاً بنسبة 100% |
| 2 | `powershell -Command "Set-Location dashboard; npm run build"` | فحص ترجمة TypeScript وبناء الحزم الإنتاجية مع تقطيع المسارات `React.lazy` | نجاح البناء (0 errors) وإنتاج Chunks مستقلة للمسارات الإدارية |
| 3 | `python tests/run_all_tests.py` | تشغيل كافة اختبارات المنصة (Unit, Integration, Security, Database) | نجاح 30/30 اختباراً بنسبة 100% |

---
**تأكيد الامتثال**: لن يتم إجراء أي تعديل على كود المشروع الأصلي (Review-only role)، ولن يتم رفع أي ملفات للسيرفر، وسيتم تشغيل الأوامر محلياً فقط بعد حفظ هذا التقرير مباشرة.
