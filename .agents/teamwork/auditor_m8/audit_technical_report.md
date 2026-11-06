# التقرير الفني المسبق للتدقيق الجنائي الشامل وجناح النصر (Milestone 8)
## Technical Audit & Verification Methodology Report (File-Report-First Artifact)

**المشروع:** منصة أتمتة وإدارة قلاع الإمبراطورية (Osmanli Platform Overhaul)  
**المرجع التنظيمي:** `AGENTS_CONSTITUTION.md` & `GEMINI.md` (القاعدتان 4 و 5)  
**المدقق الجنائي:** Forensic Auditor M8 (`auditor_m8`)  
**المستلم:** المشرف الأعلى (`44132d7d-07d0-4709-a292-a8e4727a82fd`)  
**التاريخ والوقت:** 2026-11-02T20:57:00Z  
**المسار:** `e:\osmanli\.agents\teamwork\auditor_m8\audit_technical_report.md`  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

اختتم سرب العمل البرمجي تنفيذ وإنجاز المراحل الثمانية (M1 إلى M8) لإعادة هندسة الأداء وإدارة البيانات والكاش والحالات واستقرار المنصة. قدم Worker M8 تقرير تسليم نهائي يفيد بإنجاز كافة المتطلبات بنجاح 100% ونشر التقرير الهندسي الشامل `FINAL_PERFORMANCE_AND_ARCHITECTURE_REPORT.md` وأداة التحقق الميداني المزدوج `tools/verify_m8_dual_field.py`.

عملاً بمبادئ التدقيق الجنائي الصارم المنصوص عليها في دستور الوكلاء ودليل التدقيق (Integrity Forensics):
- **الثقة لا تُمنح، بل يُثبت كل شيء تجريبياً (Trust Nothing — Verify Everything Empirically).**
- لا يجوز قبول أي ادعاء أو نتيجة اختبار مسبقة الصنع أو تقرير دون فحص جنائي مستقل للأكواد وسجلات الفحص وتنفيذ الاختبارات ميدانياً وبشكل مستقل تماماً.
- يُحظر حظراً تاماً وجود أي نتائج صلبة (Hardcoded Test Results)، أو واجهات شكلية واهية (Facade Implementations)، أو استرجاع قيم معلبة (Canned Returns)، أو تزييف لسجلات التحقق.
- يلزم التدقيق والتأكد من صحة وصدق ومطابقة الأرقام والادعاءات الواردة في التقرير الهندسي الختامي للمنصة لواقع الكود والقياسات الفعلية.

لذا، فإن هذا الإجراء مطلوب لتنفيذ تدقيق جنائي محكم ومستقل يضمن سلامة المنصة 100% قبل الاعتماد النهائي (Victory Audit).

---

## 2. المنطق وخطوات التدقيق الميداني (Methodology & Step-by-Step Logic)

سيتم تنفيذ التدقيق الجنائي عبر 3 مراحل متتالية ومتكاملة:

### المرحلة الأولى: الفحص الجنائي لسلامة الأكواد وخلوها من التزييف (Phase 1: Anti-Cheat & Facade Audit)
1. **فحص سكربت التحقق الميداني `tools/verify_m8_dual_field.py`:**
   - فحص شجرة الكود للتأكد من أن السكربت يقوم بإنشاء واستدعاء قواعد بيانات حقيقية على القرص في مسار مؤقت بنمط WAL، وخيوط تنافسية حقيقية (`threading.Thread`, `Barrier`)، وليس فحوصات وهمية أو قيماً مفترضة سلفاً.
2. **فحص الدوال التنفيذية ومصفوفات التحقق:**
   - التأكد من خلو ملفات الاختبارات من دوال تعيد `return True` مجردة أو اختبارات self-certifying تفحص مدخلاتها ضد ثوابت مكتوبة في نفس السطر لتمرير الفحص شكلياً.
3. **فحص عدم وجود مخلفات أو ملفات سجلات سابقة الصنع (Pre-populated Artifacts):**
   - التأكد من أن النتائج تُحسب لحظياً أثناء التشغيل.

### المرحلة الثانية: التحقق البنيوي والمعماري عبر طبقات النظام (Phase 2: Architectural & Layer Verification)
1. **طبقة قاعدة البيانات والباك إند (`core/database.py`, `api_server.py`):**
   - التحقق من فهارس التعبيرات الخمسة (`idx_castle_states_lower_email`, `idx_castle_states_lower_user`, `idx_users_lower_email`, `idx_users_created_at`, `idx_castle_states_created_at`) عبر استعلامات `PRAGMA index_list` و `EXPLAIN QUERY PLAN`.
   - التحقق من تطبيق OCC: وجود عمود `version` في `castle_states`، استخدام معاملة ذرية `BEGIN IMMEDIATE` في `update_castle_config`، والتحقق من تطابق الإصدار وإرجاع `OCCResult` وتمرير 409 Conflict عند التعارض.
   - التحقق من تفريغ استعلامات SQLite في الـ WebSocket handlers إلى `asyncio.to_thread`.
2. **طبقة الأمان وحماية المسارات (`api_server.py`):**
   - التحقق من إغلاق ثغرات P0 الأربعة: تجريد كلمة المرور من `/api/local/castles/{id}`، سد BOLA في `/api/castle-data/{email}`، منع انتحال البريد في `/api/bot/start`، وتأمين مسارات `/api/internal/*` عبر `verify_internal_access`.
   - التحقق من عزل مدراء التجار عبر `_verify_merchant_access_to_user` وردع الوصول غير المصرح به برمز 403 Forbidden.
3. **طبقة الشبكة وإدارة الحالات في الواجهة (`dashboard/src`):**
   - التحقق من دوال `botApi.ts` الـ 34 وتزويدها بمعامل `options?: RequestOptions` ودعم `AbortSignal` واعتراض 409.
   - التحقق من اتصال الـ WebSocket المجمع `UserStatusMultiplexer` واستخدامه في البطاقات لمنع تشتت الاتصالات.
   - التحقق من توحيد مصدر الحقيقة في `CastleCard.tsx` وخلوه من متغيرات الحالة المتنافسة، وحل تعارض النقر السطحي عبر `e.stopPropagation()`.
   - التحقق من مزامنة الحفظ عند الـ unmount في `TaskTabContent.tsx` مع كاش TanStack Query والتخزين المحلي.
   - التحقق من خلو الواجهة تماماً من `window.confirm` و `alert` واعتماد `ActionConfirmModal.tsx` بـ React Portal و ARIA standards.
   - التحقق من التطابق التام لملفات الترجمة (`ar.json`, `en.json`, `tr.json`) واحتوائها على 788 مفتاحاً متطابقاً بنسبة 100%.
4. **فحص صدق ودقة التقرير الهندسي الشامل (`FINAL_PERFORMANCE_AND_ARCHITECTURE_REPORT.md`):**
   - مطابقة كافة الادعاءات بالأرقام، وتوافق الملفات المعدلة الـ 25، وتوافق مصفوفة المشاكل الـ 20 مع الواقع.

### المرحلة الثالثة: التحقق السلوكي والتنفيذي الميداني المستقل (Phase 3: Empirical Execution)
تنفيذ أوامر الفحص والتحقق الرسمية الثلاثة ومراقبة النتائج والمخرجات الحية:
1. `python tools/verify_m8_dual_field.py`
2. `python tests/run_all_tests.py`
3. `powershell -Command "Set-Location dashboard; npm run build"`

---

## 3. الملفات والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Files & Commands)

### الملفات التي سيتم فحصها وقراءتها (Inspection Only - No Modifications):
1. `tools/verify_m8_dual_field.py` (فحص الأكواد والمنطق التنافسي)
2. `core/database.py` (فحص فهارس التعبيرات، دمج الاستعلامات، ومنطق OCC)
3. `api_server.py` (فحص المسارات، الأمان، WebSockets، وعزل التجار)
4. `dashboard/src/lib/botApi.ts` (فحص AbortController و 409 handling)
5. `dashboard/src/components/accounts/CastleCard.tsx` (فحص Single Source of Truth و stopPropagation)
6. `dashboard/src/components/accounts/TaskTabContent.tsx` (فحص مزامنة الـ unmount مع كاش Query و Storage)
7. `dashboard/src/components/common/ActionConfirmModal.tsx` (فحص Portal و ARIA و Escape listener)
8. `dashboard/src/locales/ar.json`, `en.json`, `tr.json` (فحص التماثل الثلاثي لـ 788 مفتاحاً)
9. `FINAL_PERFORMANCE_AND_ARCHITECTURE_REPORT.md` (فحص الدقة والصدق الهندسي)

### الأوامر التنفيذية التي ستُشغل:
1. **الأمر الأول:**
   - **السطر:** `python tools/verify_m8_dual_field.py`
   - **الهدف:** تشغيل جناح التحقق الميداني المزدوج التنافسي (Field 1 إلى Field 4).
   - **النتيجة المتوقعة:** اجتياز 16/16 فحصاً بنجاح 100.0% وخروج برمز 0.
2. **الأمر الثاني:**
   - **السطر:** `python tests/run_all_tests.py`
   - **الهدف:** تشغيل حزمة اختبارات المنصة المعزولة الشاملة (الطبقات 1 و 2 و 3 و 4).
   - **النتيجة المتوقعة:** اجتياز 30/30 اختباراً بنجاح 100.0% وخروج برمز 0.
3. **الأمر الثالث:**
   - **السطر:** `powershell -Command "Set-Location dashboard; npm run build"`
   - **الهدف:** التحقق من صحة واكتمال تصريف TypeScript وبناء حزمة الإنتاج بواسطة Vite.
   - **النتيجة المتوقعة:** إتمام البناء بنجاح بدون أخطاء تصريف (0 TypeScript errors) وخروج برمز 0.

### معايير الحكم النهائي (Verdict Criteria):
- في حال اجتياز جميع الفحوصات الجنائية، وثبوت أصالة الأكواد، وعدم وجود أي تزييف، ونجاح كافة أوامر التشغيل بنسبة 100%: الحكم هو **`CLEAN`**.
- في حال فشل أي فحص، أو اكتشاف واجهات شكلية واهية أو نتائج صلبة، أو فشل أي أمر تنفيذي: الحكم هو **`INTEGRITY VIOLATION`**.

