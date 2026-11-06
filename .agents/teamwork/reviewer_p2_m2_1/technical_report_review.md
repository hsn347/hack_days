# تقرير فني مسبق لإجراءات التحقق المستقلة — المرحلة الثانية (Milestone 2 Verification Plan)

**الوكيل:** `reviewer_p2_m2_1` (teamwork_reviewer / critic)  
**المهمة:** التحقق المستقل من ترقيم قلاع المسؤول والتحميل الكسول (Requirement R1 / Milestone 2)  
**التاريخ والوقت:** 2026-11-03T02:06:00Z  
**الامتثال للقواعد:** خاضع للبند 5 من دستور `GEMINI.md` والبند 19 من `AGENTS_CONSTITUTION.md`

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

1. **التحقق من صحة بناء واجهة المستخدم (Frontend Build Integrity)**:
   - تم إجراء تعديلات على `dashboard/src/pages/AdminUsersCastles.tsx` و `dashboard/src/lib/botApi.ts` لدعم الترقيم وحجم الدفعة وإلغاء تحميل `config` المسبق.
   - كمدقق مستقل، يجب التأكد من عدم وجود أي خطأ في الترجمة أو توافق الأنواع (TypeScript Errors) بنسبة 0 أخطاء وكود الخروج 0.

2. **التحقق من منصة الاختبارات الموحدة (Platform Regression Testing)**:
   - يجب تشغيل `python tests/run_all_tests.py` للتأكد من أن التعديلات في `core/database.py` و `api_server.py` لم تكسر أياً من المستويات الأربعة للاختبارات (30/30 PASS).

3. **التحقق من معايير الترقيم والتحمل الميداني (Scalability & Stress Verification)**:
   - تشغيل `python tools/verify_m6_admin_scalability.py` و `python tools/stress_m6_master_detail.py` للتحقق من أداء الـ API، وحجم الحزم المنقولة (< 60 KB)، وسلوك الكاش في الأكورديون.

4. **التحقق الجنائي الصارم من الملفات المحظورة**:
   - التحقق من عدم المساس بالملفات المحظورة الثلاثة (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`) عبر `git status`.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Step-by-Step Procedure)

1. **الخطوة الأولى: بناء الواجهة الأمامية**:
   - تنفيذ أمر PowerShell لبناء حزمة الإنتاج للواجهة عبر Vite و TypeScript compiler.
   - التحقق من انتهاء البناء بنجاح وخلوه من أي تحذيرات حرجة أو أخطاء نوعية.

2. **الخطوة الثانية: تشغيل منصة الاختبارات الموحدة**:
   - تنفيذ `python tests/run_all_tests.py` للتحقق من اجتياز جميع اختبارات المنظومة (المصادقة، قاعدة البيانات، المهام، السيرفر).

3. **الخطوة الثالثة: تشغيل أدوات قياس قابلية التوسع والتحمل**:
   - تنفيذ `python tools/verify_m6_admin_scalability.py` للتحقق من مطابقة المعايير الـ 38.
   - تنفيذ `python tools/stress_m6_master_detail.py` للتحقق من اختبارات الضغط الـ 36 وخفض حجم الباندويث بنسبة تفوق 98%.

4. **الخطوة الرابعة: الفحص الجنائي للملفات المحظورة**:
   - تنفيذ `git status --porcelain` والتحقق من عدم لمس الملفات المحظورة مطلقاً.

---

## 3. الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Outcomes)

### الأمر 1: بناء الواجهة الأمامية
- **الأمر:** `powershell -Command "Set-Location dashboard; npm run build"`
- **بيئة التشغيل:** Windows PowerShell محلياً في `e:\osmanli`
- **النتيجة المتوقعة:** كود الخروج 0، وإنتاج ملفات `dist/` دون أخطاء TypeScript (0 errors).

### الأمر 2: تشغيل منصة الاختبارات الموحدة
- **الأمر:** `python tests/run_all_tests.py`
- **بيئة التشغيل:** Windows PowerShell محلياً في `e:\osmanli`
- **النتيجة المتوقعة:** اجتياز 30/30 بنسبة نجاح 100% وكود الخروج 0.

### الأمر 3: تشغيل فحص الترقيم وقابلية التوسع
- **الأمر:** `python tools/verify_m6_admin_scalability.py`
- **بيئة التشغيل:** Windows PowerShell محلياً في `e:\osmanli`
- **النتيجة المتوقعة:** اجتياز 38/38 بنجاح وكود الخروج 0.

### الأمر 4: تشغيل اختبارات التحمل والضغط لحجم الحزم
- **الأمر:** `python tools/stress_m6_master_detail.py`
- **بيئة التشغيل:** Windows PowerShell محلياً في `e:\osmanli`
- **النتيجة المتوقعة:** اجتياز 36/36 بنجاح وانخفاض حجم الحزمة لأقل من 60 KB.

### الأمر 5: الفحص الجنائي لحالة المستودع والملفات المحظورة
- **الأمر:** `git status --short`
- **بيئة التشغيل:** Windows PowerShell محلياً في `e:\osmanli`
- **النتيجة المتوقعة:** خلو التعديلات قطيعاً من `game_client.py` و `core/onemt_auth.py` و `core/onemt_bot.py`.
