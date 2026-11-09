# تقرير فني: استكشاف ملفات الجلسات وحزم الشبكة المسجلة
**Technical Report: Session and Network Packet Replay Discovery**
**Agent**: Agent 11 (Live Connection & Init Tester)  
**Date**: 2026-11-09T13:46:00Z  

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
مطلوب فحص واختبار الاتصال الحي وتدفق حزم التهيئة إلى `LiveMemoryEngine` في `GameClient` / `GameConnection`.
لإجراء الفحص التجريبي، نحتاج إلى تحديد مواقع ملفات الجلسات الحقيقية (`session_cache.json` أو ملفات الحسابات وقواعد البيانات) أو ملفات الحزم الملتقطة الحقيقية (`*live_memory*.json` في مجلد `docs/` أو المشروع).
وحيث أن `session_cache.json` غير موجود في الجذر، يجب فحص محتويات مجلد `docs/` وقاعدة بيانات `database/castles.db` لمعرفة الجلسات والبيانات المسجلة.

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)
1. تشغيل استعلام PowerShell سريع للبحث عن ملفات الجلسات أو الحزم المسجلة (`*session*`, `*live*`, `*.json`) في `docs/` وباقي مسارات المشروع ذات الصلة.
2. فحص الجلسات المكتشفة للتأكد من وجود حسابات وبيانات اعتماد أو ملفات حزم ملتقطة حقيقية.

## 3. الأوامر التي ستنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)
- **الأمر**:
  `Get-ChildItem -Path e:\osmanli -Filter "*live*" -Recurse -File -ErrorAction SilentlyContinue | Select-Object FullName, Length`
  و
  `Get-ChildItem -Path e:\osmanli\docs -File -ErrorAction SilentlyContinue | Select-Object FullName, Length`
- **النتيجة المتوقعة**:
  الحصول على قائمة المسارات الدقيقة لملفات الحزم الملتقطة وجلسات الاتصال الحقيقية لاستخدامها في الاختبار.
