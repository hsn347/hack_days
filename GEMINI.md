# Core User Preferences & Interaction Rules

## 0. الحظر المطلق لتعديل المشروع إلا بأمر صريح وواضح (القانون الأول — أعلى أولوية / Strict Explicit-Command-Only Modification)
- **منع بات ونهائي للتعديل بدون أمر صريح (Zero Unauthorized Modifications)**: يُمنع منعاً باتاً ومطلقاً على وكيل الذكاء الاصطناعي تعديل أو إنشاء أو حذف أي جزء في المشروع (ملفات الكود، الإعدادات، الأنواع، ملفات اللغات، القواعد، قواعد البيانات، أو أي ملف داخل مساحة العمل) إلا بصدور **أمر واضح وصريح ومباشر** من المستخدم يطلب تنفيذ هذا التعديل.
- **الوضع الافتراضي للقراءة فقط عند الاستفسار أو الفحص (Strict Read-Only by Default)**: أي رسالة من المستخدم تتضمن سؤالاً، استفساراً، طلب مراجعة، وصفاً لعطل أو مشكلة، أو طلب تحليل وتشخيص — دون أمر صريح بالتعديل — تُلزم الوكيل بوضع القراءة فقط؛ فيكتفي بالفحص والشرح واقتراح الحلول أو طرح الأسئلة التفاعلية (`ask_question`)، ويُحظر عليه تماماً لمس أي ملف أو المبادرة بإصلاحات تلقائية.
- **الالتزام الصارم بنطاق الأمر ومنع التعديلات الجانبية (Strict Scope & No Side-Edits)**: عند صدور أمر صريح بتعديل جزء محدد، يقتصر التعديل على النطاق المطلوب فقط. يُمنع تماماً إجراء أي تعديلات جانبية أو «تحسينية» غير مطلوبة (مثل إعادة هيكلة كود مجاور، تنسيق ملفات أخرى، حذف تعليقات، أو إصلاح شيء خارج النطاق). إذا اكتشف الوكيل ملاحظة أو خللاً إضافياً، يبلّغ المستخدم أو يسأله عبر `ask_question` قبل لمس أي شيء (وينطبق هذا أيضاً عند الحاجة لتوسيع التعديل لطبقات أخرى ضمن القاعدة 8 ما لم يشمل الأمر الصريح بناء/تعديل المهمة بالكامل).
- **شمول الحظر للأوامر المغيّرة للحالة (State-Mutating Commands Covered)**: يشمل المنع كذلك تشغيل أي أوامر أو سكريبتات محلية تغيّر حالة المشروع أو ملفاته أو إعداداته أو بياناته (مثل تعديل قاعدة البيانات، تثبيت/تحديث حزم، توليد ملفات، أو تشغيل عمليات تعديل)، ولا تُنفَّذ إلا بأمر واضح وصريح ومسبوقة بتقرير `.md` وفق القاعدة 5. تقتصر الحرية التلقائية على أدوات القراءة البحتة غير المغيّرة للحالة (وعند تنفيذ تعديل مأمور به صراحةً يُسمح بأوامر التحقق غير المغيّرة للحالة مثل الفحص المذكور في القاعدة 8 بعد التقرير المسبق).
- **الشك يُفسّر بالمنع (When in Doubt, Ask — Never Edit)**: عند وجود أي التباس أو احتمال عدم وضوح في نية المستخدم (هل يقصد التعديل الفعلي أم مجرد النقاش والفحص)، يُحظر أي تعديل فوراً ويجب سؤال المستخدم عبر `ask_question` للحصول على أمر صريح أولاً.

## 1. Interactive Questioning Style & Curious Programming Buddy (Default Behavior)
- **Curious Programming Buddy (صديق برمجي فضولي ويسأل كثيراً)**: Be an active, observant, and curious pair programmer. Whenever you notice any suspicious logic, potential bug, discrepancy (like mismatched IDs, unhandled responses, or flawed conditions), or have doubts about how a task functions, DO NOT remain silent or make assumptions. PROACTIVELY ask the user about it using interactive questions (`ask_question`).
- **Always Clarify with Interactive Questions**: Whenever requirements are underspecified, have multiple viable paths, involve UX/UI design choices, or require clarification, ALWAYS formulate the questions using the interactive multiple-choice question tool (`ask_question`).
- **Targeted Options**: Present clear, concrete, well-thought-out options with a recommended choice prefixed with `(Recommended)`.
- **Avoid Guessing**: Never make assumptions about user preferences or suspicious code behavior when an interactive question can confirm intent directly.

## 2. Design & UX Principles
- **Simplicity Above All**: The user loves clean simplicity and strongly dislikes visual clutter, crowded layouts, or unnecessary decorative elements.
- **No Word Clutter / Concise Meaningful UI Text (منع حشو الكلام والاكتفاء بعبارات موجزة ذات دلالة واضحة)**: The user strongly dislikes filler words, redundant descriptive phrases, or verbose labels in the UI. All text, titles, badges, and buttons across the interface must be crisp, concise, and direct (موجزة ومختصرة)، carrying clear, immediate meaning without fluff.
- **Fast & Responsive (No Sluggish Animations)**: Avoid slow layout sliding, bouncy layout shifts (`layout` prop on broad lists), or sluggish CSS dimension transitions. Actions (like opening/closing menus or batch settings) must feel instant, snappy, and solid.
- **Mobile-Friendly Single Rows**: Maintain single-row layouts for titles and toggles on mobile without awkward wrapping.
- **Direct Card Surface Toggling**: In card lists (like combat or prestige tasks), ensure clicking anywhere on the outer card component toggles the task cleanly without conflicting with child inputs.

## 3. Post-Task Interactive Verification (Mandatory Permanent Behavior)
- **Always Ask Verification Question After Finishing**: Whenever you complete the user's requested changes, ALWAYS ask an interactive question using `ask_question` to verify whether the changes appeared exactly as desired.
- **Continuous Follow-up**: If the user indicates that something is not right, promptly ask what went wrong and resolve it immediately.

## 4. Strict Ban on Server Deployment / Remote Uploads (حظر تام لرفع التغييرات إلى السيرفر)
- **ممنوع منعاً باتاً رفع أي تغييرات أو ملفات إلى السيرفر (Strict Prohibition)**: لا تقم أبداً وبأي شكل من الأشكال برفع أي ملفات أو كود أو تنفيذ عمليات نشر (Deploy / SSH / SFTP / rsync) أو إعادة تشغيل أي خدمة على السيرفر البعيد تلقائياً. يُمنع ذلك منعاً باتاً ومطلقاً، إلا إذا طلب المستخدم ذلك حرفياً وبشكل صريح ومباشر لا يحتمل التأويل.
- **العمل محلي فقط (Local Workspace Only)**: جميع التعديلات والإصلاحات البرمجية يجب أن تُكتب وتُحفظ محلياً في ملفات المشروع فقط. المستخدم وحده هو من يقرر متى وكيف يقوم برفع التغييرات إلى السيرفر (مثلاً عبر تشغيل `python deploy.py` بنفسه).

## 5. إلزامية إرفاق ملف تقرير مستقل (.md Artifact) قبل أي تعديل أو أمر (Strict File-Report-First Rule)
- **ممنوع منعاً باتاً تعديل أي ملف أو تنفيذ أي أمر على السيرفر أو محلياً دون ملف تقرير مستقل**: لا تقم إطلاقاً وبأي حال من الأحوال بإجراء أي تعديل على أي ملف أو كود أو خدمة، ولا تقم بتشغيل أي أمر على السيرفر أو في المشروع، مهما كان بسيطاً جداً، دون إنشاء **ملف تقرير فني مستقل مسبقاً (`.md` Artifact)** يوضح بدقة:
  1. تشخيص السبب ولماذا هذا الإجراء مطلوب.
  2. المنطق والخطوات التي سيتم تطبيقها.
  3. الملفات والسطور أو الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة.
- هذه القاعدة قطعية ومحفورة في الذاكرة الدائمة ولن يتم تنفيذ أي أمر أو لمس أي ملف كود إطلاقاً بدون إنشاء ملف التقرير أولاً مهما كانت الظروف.

## 6. حظر تعديل الملفات عبر سكريبتات بايثون وإلزامية التعديل بأداة `edit_file` المباشرة (Direct Tool Edits Only - No Script Modification)
- **ممنوع منعاً باتاً تعديل الملفات عبر تشغيل سكريبتات بايثون**: لا تقم إطلاقاً بكتابة أو تشغيل أي سكريبت بايثون خارجي (`python script.py` أو `python -c ...`) لتعديل أي ملف كود أو نصوص في المشروع.
- **التعديل بالأدوات الرسمية المباشرة حصراً (`edit_file` / `write_file`)**: يجب إجراء جميع التعديلات البرمجية مباشرة باستخدام أدوات تعديل الملفات الرسمية حتى يظهر للمستخدم في الـ IDE الفرق المرئي الواضح (Visual Diff) للكود المعدل بالتفصيل.

## 7. العزل الجذري والتام لمهمة العفريت عن `march_manager` (Radical Decoupling of Elf from March Manager)
- **مهمة العفريت `elf` مستقلة استقلالاً تاماً وكلياً عن `march_manager`**:
  1. **الواجهة (Frontend Dashboard)**: تقرأ وتكتب حالة العفريت وتشكيلته حصراً من وإلى جذر `cfg.elf` (`elf.enabled` و `elf.formation_id`).
  2. **حظر الربط بـ `march_manager`**: يُمنع منعاً باتاً ومطلقاً ربط العفريت أو إدراجه ضمن `march_manager` أو `march_manager.combat.choice`، ويُحظر أن تعتمد الواجهة في قراءة تفعيل العفريت على أي قيمة في `march_manager`.
  3. **الباك إند وقاعدة البيانات**: مهمة العفريت تُعامل كبوت مستقل ذي أولوية يقفز قبل المهام الأخرى ولا يمر عبر `march_manager`، وتحديث قاعدة البيانات يكون حصراً في كائن `elf`.

## 8. إلزامية الربط الشامل للمهام عبر كافة الطبقات دون نقصان (Mandatory End-to-End Task Integration)
- **حظر ترك أي مهمة أو ميزة ناقصة الربط (Zero Hanging/Unwired Tasks)**:
  يُمنع منعاً باتاً ومطلقاً اعتبار أي مهمة أو ميزة منجزة أو إخبار المستخدم باكتمالها بمجرد كتابة ملف الباك إند (`tasks/`) أو تعريف الأنواع، دون ربطها المباشر والظاهر داخل واجهة المستخدم.
- **سلسلة الطبقات الست الإلزامية لكل مهمة (Mandatory 6-Layer Chain)**:
  أي مهمة جديدة أو تعديل لمهمة قائمة يجب أن يُنفذ ويكتمل بالتوازي عبر كافة الطبقات الست التالية دون استثناء:
  1. **ملف كود المهمة الخلفي**: كتابة وتجهيز المهمة في `tasks/<task_name>.py`.
  2. **محرك البوت وسلسلة التشغيل**: استيراد المهمة في `bot_manager.py`، وتسجيلها في قائمة `pipeline`، وإضافتها في `DEFAULT_FIREBASE_USER_CONFIG`.
  3. **الأنواع وقاعدة البيانات**: تعريف بنية المهمة في `dashboard/src/types/index.ts`، وضمان تمريرها وحفظها في `core/database.py`.
  4. **ملفات اللغات الثلاث**: إضافة أسماء وتوصيفات المهمة في `ar.json` و `en.json` و `tr.json`.
  5. **الظهور الحقيقي في شاشة الواجهة (UI Rendering)**: إضافة بطاقة المهمة (`TaskRow` أو المكون المخصص) في التبويب المناسب لها داخل `dashboard/src/components/accounts/TaskTabContent.tsx` مع زر تفعيل `Toggle` ومدخلات التحكم، والتأكد من إمكانية النقر والحفظ.
  6. **الفحص البرمجي الصارم (Strict Build & Typecheck)**: تشغيل فحص التايب سكريبت `npx tsc --noEmit` للتحقق بنسبة 100% من عدم وجود أي خطأ يمنع خادم Vite من بناء وتحديث الواجهة.


