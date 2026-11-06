# Dispatch Directive: Forensic Auditor M6 — Integrity Verification

## 2026-11-02T20:09:00Z
- **Target Role**: teamwork_auditor
- **Milestone**: Milestone 6: Admin Dashboard Scalability, Client-side Pagination & Master-Detail Table Splitting
- **Working Directory**: `e:\osmanli\.agents\teamwork\auditor_m6\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R5, R6, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_m6\handoff.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
Create your technical report artifact before executing commands.

## 🔒 AUDIT INTEGRITY MANDATE
Verify that Milestone 6 implementations are genuine, functional, and authentic:
1. **Hardcoded Test Results Check**: Confirm that no mocked responses or canned strings exist in `Admin.tsx`, `AdminUsersCastles.tsx`, `botApi.ts`, or `api_server.py`.
2. **Facade Check**: Verify that `AdminUsersCastles.tsx` genuinely performs lazy on-demand loading of castle configs (only when row is expanded) rather than fetching all configs upfront; verify pagination in `Admin.tsx` genuinely slices rows and responds to page size changes.
3. **Verification Integrity**: Inspect `tools/verify_m6_admin_scalability.py` to ensure it exercises real code paths without self-certification cheats.
4. Run standard suites:
   - `python tools/verify_m6_admin_scalability.py`
   - `powershell -Command "Set-Location dashboard; npm run build"`
   - `python tests/run_all_tests.py`
5. Deliver `handoff.md` with explicit verdict: **CLEAN** or **INTEGRITY VIOLATION**.
   - Note: If ANY integrity violation is found, report **INTEGRITY VIOLATION** immediately (Hard Veto).
6. Notify orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`) via `send_message`.

