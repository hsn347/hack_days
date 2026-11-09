# تقرير فني: فحص المتحكمات الحيوية وغير المسموحة في حزم docs/*live_memory.json
**Technical Report: Verification of Critical and Non-Whitelisted Controllers in Captured Live Memory**
**Agent**: Agent 11 (Live Connection & Init Tester)  
**Date**: 2026-11-09T13:48:00Z  

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Diagnosis & Rationale)
نحتاج إلى التأكد من:
1. هل يحتوي ملف `docs/burcudemr_live_memory.json` (والملفات الأخرى) على الستة متحكمات الحرجة (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`)؟
2. هل يحتوي `cityCtrl` على `blist` (وعدد عناصره) و `reslist`؟
3. هل يحتوي `lordInfoCtrl` على `base` ومعرف `uid`؟
4. كم عدد المتحكمات خارج `ALLOWED_CONTROLLERS` في الملف (مثل `chatCtrl`, `RedPointCtrl`, إلخ)؟

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Steps)
كتابة استعلام بايثون يفحص المتحكمات في الملف مقابل `ALLOWED_CONTROLLERS` و `CRITICAL_STARTUP_CONTROLLERS` المعرفة في `core/live_memory.py`.

## 3. الأوامر التي ستنفذ بالتفصيل مع النتيجة المتوقعة (Commands & Expected Results)
- فحص المتحكمات ومطابقتها للقوائم البيضاء واستخراج إحصائيات تفصيلية.
