# تقرير فني مستقل مسبق: خطة فحص واختبار مخرجات المرحلة 3
### Technical Review & Verification Plan — Milestone 3 (Frontend State & Concurrency)

**التاريخ:** 2026-11-02T18:48:00Z  
**المرجع:** `GEMINI.md` (البند 5: إلزامية ملف تقرير فني مستقل مسبقاً قبل أي أمر أو تعديل)  
**وكيل المراجعة:** Reviewer M3 (Replacement Instance 1)  
**معرف المهمة:** `5bb133e6-d201-4868-8878-794990fb8aa5`  
**المستلم:** Orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`)  

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
تم تكليف المراجع M3 (Replacement Instance 1) بإجراء مراجعة كود وتدقيق معادي مستقل لمخرجات المرحلة 3 (Milestone 3)، والتي تركز على:
1. القضاء على تفرعات الحالة المتنافسة في `dashboard/src/components/accounts/CastleCard.tsx` وتوحيد مصدر الحقيقة لحالة البوت.
2. حل مشكلة فقدان المسودات عند مغادرة المكون (`Unmount`) في `dashboard/src/components/accounts/TaskTabContent.tsx` عبر مزامنة كاش TanStack Query والتخزين المحلي `saveCachedCastles`.
3. تكامل نظام التحكم بالتعديلات المتزامنة (OCC) وتمرير `version` واعتراض كود `409 Conflict` عبر `botApi.ts` و `useCastles.ts` و `types/index.ts`.
4. التحقق من النقر المباشر على الحاوية الخارجية للبطاقة (Direct Card Surface Toggling) per `GEMINI.md` دون تعارض مع العناصر الفرعية.
5. الفحص الصارم ضد انتهاكات النزاهة (Integrity Violations): التحقق من عدم وجود أي مخرجات صلبة (hardcoded outputs)، أو واجهات وهمية (facade implementations)، أو مسارات مختصرة غير حقيقية.

لتنفيذ هذا التدقيق المستقل، يلزم تشغيل أوامر الفحص والتحقق الآلية والتحقق من شفرة المصدر بدقة.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Planned Steps)
1. تشغيل أداة الفحص الهندسية المخصصة للمرحلة الثالثة: `python tools/verify_m3_frontend_state.py`.
2. تشغيل فحص مترجم TypeScript لمشروع الواجهة: `Set-Location dashboard; npx tsc --noEmit`.
3. تشغيل الحزمة الكاملة لاختبارات النظام: `python tests/run_all_tests.py`.
4. فحص الأسطر البرمجية المعدلة في ملفات الواجهة والتحقق من عدم وجود تفرعات، وحماية `e.stopPropagation()`، وصحة منطق الـ unmount cleanup.
5. اختبار سيناريوهات هجومية معادية (Adversarial stress-testing):
   - سيناريو تأخر أو فشل اتصال WebSocket.
   - سيناريو الخروج السريع أثناء إرسال طلب الحفظ.
   - سيناريو تعارض النسخ 409 Conflict وتأثيره على الواجهة.
6. تحديث تقرير التسليم `handoff.md` وسجل التقدم `progress.md` وذاكرة العمل `BRIEFING.md`، ثم إرسال النتيجة الرسمية والقرار للمشرف عبر `send_message`.

---

## 3. الأوامر والملفات التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Output)

| # | الأمر المنفذ | مسار التنفيذ | النتيجة المتوقعة |
|---|---|---|---|
| 1 | `python tools/verify_m3_frontend_state.py` | `e:\osmanli` | اجتياز 8 اختبارات كاملة بنجاح بنسبة 100% (`OK`) |
| 2 | `Set-Location dashboard; npx tsc --noEmit` | `e:\osmanli` | انتهاء الفحص بكود خروج 0 دون أي أخطاء من مترجم TypeScript |
| 3 | `python tests/run_all_tests.py` | `e:\osmanli` | اجتياز 30 اختباراً بنجاح بنسبة 100% (`ALL TESTS PASSED`) |

---
**إقرار الامتثال الصارم:**
- جميع العمليات والأوامر تتم محلياً 100% داخل `e:\osmanli`.
- لا يوجد أي اتصال بخوادم خارجية أو قواعد بيانات إنتاجية.
- لا توجد أي عمليات نشر أو رفع (Deploy).
