# تقرير فني مستقل: خطة الفحص الأمني التنافسي واختبارات الإجهاد (Milestone 2 Challenger)
### Technical Report: Empirical Adversarial Security & Concurrency Stress Plan

**المرجع:** `GEMINI.md` (البند 5: إلزامية التقرير الفني المسبق) و `AGENTS_CONSTITUTION.md`  
**الدور:** Empirical Challenger (Instance 1 — Security & Auth Challenger)  
**المرحلة:** Milestone 2 (M2)  
**تاريخ التقرير:** 2026-11-02  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)

قام العامل `worker_m2` بتطبيق إصلاحات أمنية لمعالجة 4 ثغرات حرجة P0 وتحسين التحكم بالتعديلات المتزامنة (OCC).
بصفتنا الفاحص المستقل والمنافس التجريبي (Empirical Challenger)، يُحظر الاعتماد على مزاعم أو سجلات العامل، ويتوجب علينا:
1. كتابة سكربت هجومي واختبار إجهاد حقيقي `tools/stress_m2_security.py` لمحاكاة هجمات استباقية وتنافسية (Adversarial Attacks).
2. قياس سلوك النظام الفعلي تحت ظروف غير مواتية (محاولات انتحال، التفاف على الترويسات، هجمات BOLA/IDOR، سباقات تزامنية متوازية، وتمرير مدخلات خبيثة أو غير متوقعة).
3. فحص الأسطر المعدلة في `api_server.py` و `core/database.py` بشكل مستقل.
4. التأكد من عدم وجود أي تسريب لكلمات المرور أو الرموز الحساسة، ومنع أي تجاوز لعزل بيانات المستخدمين.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Methodology & Attack Vectors)

سنقوم بتنفيذ 5 متجهات هجومية رئيسية ضمن السكربت `tools/stress_m2_security.py`:

### المتجه الأول: هجمات BOLA / IDOR وتسريب البيانات على `/api/local/castles/{id}`
- **الهجوم 1.1 (Unauthenticated Access):** إرسال طلب بدون أي توكن مصادقة. المتوقع: رفض قطعي بـ `401 Unauthorized`.
- **الهجوم 1.2 (Cross-User IDOR/BOLA):** مستخدم مهاجم (User B) يحاول استرجاع بيانات قلعة الضحية (User A). المتوقع: رفض قطعي بـ `403 Forbidden`.
- **الهجوم 1.3 (Owner Data Sanitization):** مستخدم شرعي يسترجع قلعته. المتوقع: `200 OK`، مع التحقق الصارم من خلو كائن الاستجابة تماماً من `password` بنص صريح، وخلوه من `raw_json`.
- **الهجوم 1.4 (Admin Access Sanitization):** المشرف يسترجع القلعة. المتوقع: `200 OK`، مع تأكيد تجريد كلمة المرور حتى للمشرف عبر هذا المسار لمنع كشفها في المتصفح.
- **الهجوم 1.5 (Non-existent Castle ID):** طلب معرف غير موجود. المتوقع: `404 Not Found`.

### المتجه الثاني: هجمات IDOR/BOLA على مسار جلب الموارد الحية `/api/castle-data/{email}`
- **الهجوم 2.1 (Cross-Account Extraction):** مهاجم يطلب بيانات موارد حية لبريد قلعة تخص مستخدماً آخر. المتوقع: رفض قطعي بـ `403 Forbidden`.
- **الهجوم 2.2 (Case & Whitespace Manipulation):** تجربة تلاعب بحالة الأحرف والمسافات (مثل `  VICTIM@EXAMPLE.COM `) للالتفاف على الفحص. المتوقع: اكتشاف المحاولة ورفضها بـ `403 Forbidden`.
- **الهجوم 2.3 (Legitimate Castle Owner Access):** وصول المالك الشرعي لقلعته عبر إيميل القلعة المسجل لديه في SQLite. المتوقع: اجتياز الفحص الأمني (عدم إرجاع 403).

### المتجه الثالث: هجمات انتحال البريد الإلكتروني في `/api/bot/start`
- **الهجوم 3.1 (Parameter Spoofing):** يملك المستخدم القلعة `C1` بالبريد `owner@example.com`، ويرسل في جسم الطلب `email: "spoofed_victim@example.com"`.
  المتوقع: الخادم يكتشف ويستبدل `req.email` بالبريد المعتمد من قاعدة البيانات قبل استدعاء محرك البوت، ومنع تلوث الكاش أو انتحال الجلسة.
- **الهجوم 3.2 (Unauthorized Castle Start):** مهاجم يرسل طلب تشغيل لقلعة مستخدم آخر. المتوقع: رفض بـ `403 Forbidden` أو `404 Not Found`.

### المتجه الرابع: هجمات الالتفاف على حماية المسارات الداخلية العشرة
- المسارات المستهدفة:
  1. `/api/internal/stop-all`
  2. `/api/internal/restart-all`
  3. `/api/internal/direct-start`
  4. `/api/internal/deploy-lock`
  5. `/api/internal/deploy-unlock`
  6. `/api/internal/gradual-start`
  7. `/api/internal/cancel-start-queue`
  8. `/api/internal/save-running-state`
  9. `/api/internal/debug-state`
  10. `/api/bot/conn-state`
- **الهجوم 4.1 (External IP Spoofing):** إرسال طلبات من عناوين خارجية مع ترويسات `X-Real-IP: 198.51.100.1` أو `X-Forwarded-For: 203.0.113.1` بدون توكن. المتوقع: رفض شامل بـ `403 Forbidden` لكافة المسارات العشرة.
- **الهجوم 4.2 (Header Forgery - Fake Loopback):** مهاجم خارجي يحاول حقن `X-Real-IP: 127.0.0.1` عبر اتصال من عنوان IP غير محلي. المتوقع: رفض بـ `403 Forbidden`.
- **الهجوم 4.3 (Invalid / Partial Token):** إرسال توكن خاطئ أو ناقص في `X-Internal-Token`. المتوقع: رفض بـ `403 Forbidden`.
- **الهجوم 4.4 (Valid Internal Token Access):** إرسال التوكن السري الصحيح. المتوقع: قبول الطلب بنجاح.
- **الهجوم 4.5 (Admin Bearer Token Access):** إرسال Bearer Token لمشرف معتمد من عنوان خارجي. المتوقع: قبول الطلب بنجاح.
- **الهجوم 4.6 (Regular User Bearer Token Access):** إرسال Bearer Token لمستخدم عادي من عنوان خارجي. المتوقع: رفض بـ `403 Forbidden`.

### المتجه الخامس: اختبار الإجهاد التزامني (Optimistic Concurrency Control - OCC Stress)
- **الهجوم 5.1 (Stale Version Conflict):** إرسال تحديث بإصدار قديم (`expected_version = current - 1`). المتوقع: رفض مع إعادة رمز `409 Conflict`.
- **الهجوم 5.2 (Race Condition Burst):** إطلاق 20 خيط متزامن (Threads) يحاولون تعديل نفس السجل في نفس اللحظة بنفس رقم الإصدار.
  المتوقع: نجاح طلب واحد فقط، ورفض 19 طلباً بتعارض تزامني (Conflict)، وزيادة الإصدار في قاعدة البيانات ذرياً وبدقة.

---

## 3. الملفات والسطور والأوامر التي ستُنفذ بالتفصيل (Files & Commands)

### الملفات التي سيتم إنشاؤها:
1. `tools/stress_m2_security.py`: سكربت الفحص التنافسي المستقل وحزمة الاختبارات الهجومية.
2. `.agents/teamwork/challenger_m2_1/handoff.md`: تقرير التسليم النهائي وحكم الفاحص المستقل (Verdict: APPROVE أو REQUEST_CHANGES).

### الأوامر التي ستُنفذ محلياً:
1. تشغيل سكربت الفحص التنافسي:
   ```powershell
   python tools/stress_m2_security.py
   ```
2. إعادة التحقق من الاختبارات الشاملة للمشروع للتأكد من عدم وجود أي انكسار أو تراجع (Regression):
   ```powershell
   python tests/run_all_tests.py
   ```

### النتيجة المتوقعة:
- نجاح 100% من الاختبارات الهجومية في `tools/stress_m2_security.py`.
- تأكيد عدم تسريب أي بيانات حساسة وصمود الحماية أمام محاولات الالتفاف.
- إصدار الحكم النهائي المستقل.
