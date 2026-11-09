# تقرير فني مسبق رقم 3: التحقق البرمجي من عزل مهمة العفريت وبوابة الجاهزية

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب
كجزء من تدقيق النزاهة والمطابقة مع متطلبات ORIGINAL_REQUEST.md والقاعدة رقم 7 في GEMINI.md (العزل الجذري والتام لمهمة العفريت elf عن march_manager)، يجب فحص كافة مواضع استدعاء وتعريف مهمة العفريت `elf` والتأكد من أنها:
1. تقرأ وتكتب حصراً من جذر `cfg.elf` (`elf.enabled`, `elf.formation_id`).
2. معزولة تماماً عن `march_manager` و `march_manager.combat.choice`.
3. تتحقق من بوابة جاهزية الذاكرة `wait_for_memory_ready` وتعمل كبوت ذي أولوية.

## 2. المنطق والخطوات التي سيتم تطبيقها
- البحث في `bot_manager.py` عن كافة الأسطر التي تحتوي على `elf` و `wait_for_memory_ready`.
- فحص ملف `tasks/elf_boss.py` للتأكد من عدم وجود أي استيراد أو ربط مع `march_manager`.

## 3. الأوامر التي ستُنفذ بالتفصيل والنتيجة المتوقعة
- الأمر: `powershell -NoProfile -Command "Select-String -Path bot_manager.py -Pattern 'wait_for_memory_ready' -Context 2,2"`
  النتيجة المتوقعة: إظهار كافة مواضع فحص بوابة الجاهزية في `bot_manager.py`.
- الأمر: `powershell -NoProfile -Command "Select-String -Path bot_manager.py -Pattern '\belf\b' -Context 1,1"`
  النتيجة المتوقعة: إظهار سياق تعامل `bot_manager.py` مع `elf`.
- الأمر: `powershell -NoProfile -Command "Select-String -Path tasks/elf_boss.py -Pattern 'march_manager'"`
  النتيجة المتوقعة: لا يوجد أي تطابق (صفر نتائج)، إثباتاً للعزل التام وفق القاعدة 7.
