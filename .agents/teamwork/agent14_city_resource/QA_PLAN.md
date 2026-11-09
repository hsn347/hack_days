# خطة الفحص البرمجي والتحقق العدائي: متحكم المدينة والموارد (NOTIFY_CITY)
**QA & Adversarial Verification Plan: City & Resource Delta Mutations**

**التاريخ**: 2026-11-09T13:45:00Z  
**المسؤول**: Agent 14 (City & Resource Delta QA Agent)  
**الأدوار**: Reviewer & Adversarial Critic  
**الملفات المستهدفة للفحص**: `core/live_memory.py`, `game_client.py`  

---

## 1. أهداف الفحص (Test Objectives)
تنفيذ فحص برمجي صارم ومستقل لتحولات إشعار `NOTIFY_CITY` (ID: 9 / "CITY"):
1. **فحص جمع وخصم الموارد التراكمي (`res`)**:
   - اختبار تدفق حزم تحتوي على كميات موجبة وسالبة.
   - التحقق من الجمع الرياضي الدقيق والحماية الصارمة من الهبوط تحت الصفر (Clamp-to-Zero).
   - اختبار الحفاظ على نوع البيانات (string vs int).
2. **فحص الاستبدال المطلق (`reslist`, `saferes`, `dayMaxRes`)**:
   - التحقق من الاستبدال الشامل لقائمة الموارد `reslist` ومسح أي مفاتيح سابقة غير موجودة في الحزمة الجديدة.
   - التحقق من استبدال وتحديث الموارد الآمنة `saferes` والحد اليومي `dayMaxRes`.
   - التحقق من عزل النسخ العميق (Deep-Copy Isolation) لمنع تلوث الذاكرة عند تعديل الحزمة لاحقاً.
3. **فحص الموارد غير المجمعة (`updateUnCollectRes`)**:
   - اختبار زيادة الموارد فوق المبنى المحدد بالـ `index` بالضبط في `binfo.curres` أو `curres`.
   - اختبار المباني ذات الهيكل المتداخل (`binfo`) والمباني المسطحة.
   - اختبار سلوك معالجة الـ `index` كـ `str` أو `int`.
   - اختبار مقاومة عدم وجود المبنى في `blist`.
4. **فحص الطابور الثاني المستأجر (`openChargeQueue`)**:
   - التحقق من إنشاء طابور `1201` في `cityCtrl.queue` و `queueCtrl`.
   - اختبار مطابقة أوقات البداية والمدة الكلية والزمن المتبقي.
5. **الفحص العدائي والتحقق من سلامة البنية (Adversarial Stress & Double-Dispatch Inspection)**:
   - فحص احتمالية الاستدعاء المزدوج (`Double-Dispatch`) بين `ingest_packet` و `_dispatch` في `game_client.py`.
   - اختبار الحالات الحدية (Boundary Conditions)، والمدخلات الفارغة، والحزم المعطوبة.

---

## 2. خطوات التنفيذ
1. إنشاء ملف اختبار مستقل `tests/test_agent14_city_resource_qa.py` باستخدام أدوات المنظومة الرسمية.
2. تنفيذ كافة سيناريوهات الاختبار برمجياً عبر `python -m unittest tests/test_agent14_city_resource_qa.py`.
3. تسجيل النتائج بدقة وسلسلة الأدلة المنطقية في `handoff.md`.
