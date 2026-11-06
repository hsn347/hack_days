# Dispatch Directive: Forensic Auditor M7 — Integrity Verification

## 2026-11-02T20:35:00Z
- **Target Role**: teamwork_auditor
- **Milestone**: Milestone 7: UX Lifecycle, Confirm Modals, Trilingual Consistency & Resource Cleanup
- **Working Directory**: `e:\osmanli\.agents\teamwork\auditor_m7\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R6, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_m7\handoff.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
Create your technical report artifact before executing commands.

## 🔒 AUDIT INTEGRITY MANDATE
Verify that Milestone 7 implementations are genuine, functional, and authentic:
1. **Hardcoded Test Results Check**: Confirm that no mocked responses, canned translations, or bypassed assertions exist in `ActionConfirmModal.tsx`, `Admin.tsx`, `AdminLiveProcesses.tsx`, or `api_server.py`.
2. **Facade Check**: Verify that `ActionConfirmModal` genuinely renders portal modals and executes confirm/cancel callbacks; verify merchant domain isolation genuinely executes in `api_server.py:get_admin_user_castles`.
3. **Verification Integrity**: Inspect `tools/verify_m7_ux_lifecycle.py` to ensure it exercises real code paths without self-certification cheats.
4. Run standard suites:
   - `python tools/verify_m7_ux_lifecycle.py`
   - `powershell -Command "Set-Location dashboard; npm run build"`
   - `python tests/run_all_tests.py`
5. Deliver `handoff.md` with explicit verdict: **CLEAN** or **INTEGRITY VIOLATION**.
   - Note: If ANY integrity violation is found, report **INTEGRITY VIOLATION** immediately (Hard Veto).
6. Notify orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`) via `send_message`.

