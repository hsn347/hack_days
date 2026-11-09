## 2026-11-09T13:36:34Z
You are Worker: Bot Loop Integration Engineer (Agent 10 Implementation).
Your working directory is: e:\osmanli\.agents\teamwork\worker_bot_loop\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Domain Skill: e:\osmanli\.agents\skills\empire-bot\SKILL.md
4. GEMINI.md: e:\osmanli\GEMINI.md (pay strict attention to Rule 7: Radical Decoupling of Elf from march_manager).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Ownership:
You own `bot_manager.py` exclusively. Use direct tool `edit_file` to modify it (GEMINI.md Rule 6: NEVER use python scripts to edit code).

Task:
Integrate the strict memory readiness gate `wait_for_memory_ready` into `bot_manager.py`:
1. In `bot_manager.py` inside `_run_task_pipeline()` (or wherever the account cycle runs tasks):
   - Before executing tasks, invoke:
     ```python
     is_ready = await self.conn.wait_for_memory_ready(timeout=30.0, auto_fetch_missing=True)
     if not is_ready:
         self._log("⚠️ الذاكرة الحية غير مكتملة، تعليق تشغيل المهام للدورة القادمة...")
         return
     ```
   - Ensure that if `self.conn` has `wait_for_memory_ready`, it is called and awaited.
2. Verify GEMINI.md Rule 7 (Radical Decoupling of Elf from march_manager):
   - Confirm that `ElfBossTask` is completely decoupled from `march_manager` and `MarchManagerTask`.
   - Ensure the priority execution of `ElfBossTask` still functions seamlessly and benefits from `wait_for_memory_ready`.
3. Verification:
   - Run `python -m py_compile bot_manager.py` to ensure zero syntax errors.
   - Run a test import or execution check to verify no regressions.

Deliverables:
- Edit `bot_manager.py`.
- Write your handoff report in `e:\osmanli\.agents\teamwork\worker_bot_loop\handoff.md` and update `progress.md`.
- Send a message when finished referencing your handoff.
