# تقرير فني مسبق للتعديل والتنفيذ البرمجي (Pre-Implementation Technical Report)
**وفقاً للبند 5 من دستور وتفضيلات المستخدم الدائمة (GEMINI.md Rule 5 — Strict File-Report-First Rule)**

**التاريخ والتوقيت:** 2026-11-02T22:32:00Z  
**الوكيل:** `worker_p2_m1_iter2` (Implementation Worker)  
**المهمة:** Milestone 1 Iteration 2 — إصلاح وسائط سطر الأوامر (CLI Options) والتحكم في أحمال القياس في `tools/measure_baseline.py`.

---

## 1. تشخيص السبب ولماذا هذا الإجراء مطلوب (Root Cause Diagnostic)

أظهر تقرير التحقق المستقل من المدقق الميداني (`challenger_p2_m1_2` في `handoff.md`) وجود عيوب في واجهة سطر الأوامر (CLI) لأداة قياس خط الأساس `tools/measure_baseline.py`:
1. **أخطاء عدم التعرف على الوسائط المطلوبة**:
   - تشغيل `python tools/measure_baseline.py --duration 5` أنتج الخطأ:
     `error: unrecognized arguments: --duration 5`
   - تشغيل `python tools/measure_baseline.py --workers 20` أنتج الخطأ:
     `error: unrecognized arguments: --workers 20`
   - تشغيل `python tools/measure_baseline.py --no-load` أنتج الخطأ:
     `error: unrecognized arguments: --no-load`
   السبب: عدم تعريف هذه الوسائط في كائن `argparse.ArgumentParser` داخل الدالة `main()`.

2. **علم ميت / تجاهل تام لخاصية تخطي الحمل (`--skip-load`)**:
   - كان الخيار `--skip-load` معرفاً في `parser.add_argument("--skip-load", ...)`، ولكن في السطر 932 استدعت دالة `main()` الدالة المركزية بالصيغة:
     `report_data, report_md = run_full_baseline_measurement(tag=tag)`
     دون تمرير `args.skip_load` نهائياً إلى الدالة.
   - نتيجة لذلك، استمر تنفيذ المرحلة الثالثة (Active Workload Simulation) لـ 10 خيوط عمل متزامنة بالكامل حتى عند تمرير `--skip-load`.

3. **الأثر التشغيلي (Impact & Blast Radius)**:
   - تعتمد مهام التحسين المستمر واختبارات الإجهاد والصمود (Milestone 5 Soak Testing) على استدعاء أداة القياس بمدد زمنية محددة (`--duration`) وعدد خيوط مخصص (`--workers`) أو في وضع الخمول الصرف دون حمل (`--no-load`).
   - غياب هذه المعلمات يمنع أتمتة القياس المنهجي المطلوب في متطلبات R4.

---

## 2. المنطق والخطوات التي سيتم تطبيقها (Logic & Planned Changes)

1. **تحديث تعريفات وسائط سطر الأوامر (`argparse`) في `tools/measure_baseline.py`**:
   - إضافة `--duration`: `type=float`, `default=2.5`, `help="Sampling duration in seconds for CPU measurement"`.
   - إضافة `--workers`: `type=int`, `default=10`, `help="Number of concurrent worker threads for active workload simulation"`.
   - إضافة `--no-load`: `action="store_true"`, `help="Skip Phase 3 active workload simulation test"`.
   - الإبقاء على `--skip-load`: `action="store_true"`, مع معاملته كاسم رديف (Alias) لـ `--no-load`.
   - احتساب القيمة المنطقية `no_load = bool(args.no_load or args.skip_load)`.
   - تمرير المعلمات: `duration=args.duration`, `workers=args.workers`, `no_load=no_load` إلى الدالة `run_full_baseline_measurement`.

2. **تحديث دالة القياس المركزية `run_full_baseline_measurement`**:
   - تعديل توقيع الدالة ليصبح:
     ```python
     def run_full_baseline_measurement(
         tag: str = "prefix",
         duration: float = 2.5,
         workers: int = 10,
         no_load: bool = False,
         skip_load: Optional[bool] = None,
     ) -> Tuple[Dict[str, Any], str]:
     ```
   - معالجة الرديف البرمجي: إذا تم تمرير `skip_load` تصبح `no_load = bool(no_load or skip_load)`.
   - في المرحلة الثانية (Phase 2): تمرير `duration=duration` إلى `monitor.measure_cpu_percent(duration=duration)`.
   - في المرحلة الثالثة (Phase 3):
     - إذا كانت `no_load` تساوي `False`:
       يتم تشغيل `run_active_load_test(concurrency=workers, iterations_per_worker=25)`، ومراقبة المعالج أثناء الحمل، وتوثيق النتائج.
     - إذا كانت `no_load` تساوي `True`:
       تخطي اختبار الحمل بالكامل مع طباعة توضيحية:
       `>>> [Phase 3/4] Skipping Active Workload Load Test (--no-load / --skip-load specified)...`
       بناء هيكل قياس نظيف ومكتمل للحمل دون أخطاء:
       ```python
       load_result = {
           "concurrency": 0,
           "total_workers": 0,
           "total_records_processed": 0,
           "total_configs_parsed": 0,
           "total_duration_seconds": 0.0,
           "throughput_records_per_sec": 0.0,
           "skipped": True,
       }
       active_snapshot = monitor.snapshot()
       active_snapshot["cpu_percent"] = idle_cpu
       active_snapshot["workload_metrics"] = load_result
       ```
   - الانتقال السلس إلى المرحلة الرابعة (Phase 4: Post-Teardown) وحساب الفروقات `deltas` وتوليد التقارير دون أي `KeyError` أو انكسار في تقرير Markdown.

3. **الحفاظ على جميع القيود الدستورية والأمنية**:
   - عدم لمس أو فتح الملفات المحظورة الثلاثة: `game_client.py`، `core/onemt_auth.py`، `core/onemt_bot.py`.
   - العمل محلياً فقط دون أي اتصال خارجي أو رفع إلى السيرفر.
   - عدم استخدام أي قيم وهمية hardcoded؛ توليد قياسات حقيقية فيزيائية للمنظومة.

---

## 3. الملفات والسطور والأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة (Files, Lines & Expected Results)

### الملف المستهدف بالتعديل:
- المسار: `e:\osmanli\tools\measure_baseline.py`
  - السطور المستهدفة (637 - 720 تقريباً): تعديل توقيع `run_full_baseline_measurement` واستخدام `duration` و `workers`، وإضافة شرط التحقق من `no_load` لتخطي الحمل النشط عند تفعيله.
  - السطور المستهدفة (920 - 935 تقريباً): إضافة `--duration` و `--workers` و `--no-load` في `argparse` وربط `--skip-load`، وتمرير القيم إلى الدالة.

### أوامر التحقق الميداني المجدولة للتنفيذ:
1. `python tools/measure_baseline.py --duration 1`
   - **النتيجة المتوقعة:** يعمل بنجاح بدون أخطاء وسائط، ويتم أخذ عينة الخمول لمدة ثانية واحدة، وينتهي بكود خروج 0.
2. `python tools/measure_baseline.py --workers 5`
   - **النتيجة المتوقعة:** يعمل بنجاح وينفذ حمل العمل المتزامن باستخدام 5 خيوط عمل بدلاً من 10، وينتهي بكود خروج 0.
3. `python tools/measure_baseline.py --no-load`
   - **النتيجة المتوقعة:** يتخطى المرحلة الثالثة بالكامل، ولا ينفذ خيوط الحمل النشط، وينتج تقرير JSON و Markdown متوافقين تماماً، بكود خروج 0.
4. `python tools/measure_baseline.py --skip-load`
   - **النتيجة المتوقعة:** يتصرف كاسم رديف مطابق لـ `--no-load` ويتخطى المرحلة الثالثة بنجاح، بكود خروج 0.
5. `python tools/measure_baseline.py --tag prefix`
   - **النتيجة المتوقعة:** يولد خط الأساس الافتراضي بنجاح بكود خروج 0 ويحدث `tools/baseline_metrics_prefix.json` و `tools/BASELINE_METRICS_PREFIX.md`.
6. `python tests/run_all_tests.py`
   - **النتيجة المتوقعة:** اجتياز 30 من أصل 30 اختبار بنسبة نجاح 100% دون أي تراجع (zero regression).
