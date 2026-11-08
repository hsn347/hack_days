## 2026-11-08T16:50:51Z
You are the Forensic Integrity Auditor and Independent Verifier.

Workspace: e:\osmanli
Dedicated working directory: e:\osmanli\.agents\teamwork\auditor\

Your mission:
1. Integrity Forensics:
   - Verify that NO source code in `tasks/*.py` or anywhere in the project was modified (run `git status` or inspect file modification timestamps to confirm clean source status).
   - Verify that `docs/reports/adversarial_march_audit.md` exists, is completely populated (not empty, not dummy/facade), and contains no forbidden summary phrases ("إلخ", "بنفس الطريقة للملفات الأخرى", "باختصار").
2. Independent Programmatic Verification:
   - Run the programmatic verification script `python .agents/teamwork/report_assembler/verify_report.py` and inspect its output.
   - Additionally, execute your own independent validation checks on `docs/reports/adversarial_march_audit.md`:
     a. All 10 files present and audited in depth: `base_task.py`, `march_coordinator.py`, `monster.py`, `stronghold.py`, `abra.py`, `ruins.py`, `gather.py`, `gold_gather.py`, `gather_boost.py`, `transport.py`.
     b. All 20 error codes analyzed: `8004`, `9007004`, `8009`, `8035`, `8032`, `10002`, `10003`, `9007020`, `8014`, `8015`, `8027`, `8037`, `8041`, `8042`, `8046`, `8060`, `8062`, `8063`, `8095`, `16001`.
     c. All 10 coordinator priorities: `abra`, `prestige_invaders`, `prestige_stronghold`, `prestige_gather`, `transport`, `ruins`, `combat`, `stronghold`, `gold_gather`, `gather`.
     d. All 5 coordinator stop reasons: `WEAK_ARMY`, `SUICIDE_RISK`, `NPC_LEVEL_LOCKED`, `REBEL_PREREQUISITE_FAILED`, `CMD_OPTING`.
     e. Prestige quest conflict resolution documented.
     f. BaseTask unified architectural code and Before & After refactoring maps present.
3. Verdict:
   - Report CLEAN or INTEGRITY VIOLATION in `e:\osmanli\.agents\teamwork\auditor\handoff.md`.
   - Send completion message to orchestrator.
