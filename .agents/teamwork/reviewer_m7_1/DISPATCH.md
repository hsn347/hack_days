# Dispatch Directive: Reviewer M7 (Instance 1) — Quality, Trilingual & UX Review

## 2026-11-02T20:35:00Z
- **Target Role**: teamwork_reviewer
- **Milestone**: Milestone 7: UX Lifecycle, Confirm Modals, Trilingual Consistency & Resource Cleanup
- **Working Directory**: `e:\osmanli\.agents\teamwork\reviewer_m7_1\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R6, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_m7\handoff.md`
- **Worker Technical Report**: `e:\osmanli\.agents\teamwork\worker_m7\technical_report_m7.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
Create your technical report artifact (.md) before executing commands.

## Review Scope & Instructions
1. Independently review changes made by Worker M7:
   - `dashboard/src/components/common/ActionConfirmModal.tsx` (accessible portal modal, escape handler, dark/light theme, snappy transition).
   - Replacement of all 6 blocking `confirm(...)` dialogs across `Admin.tsx` and `AdminLiveProcesses.tsx`.
   - Trilingual key synchronization across `dashboard/src/locales/` (`ar.json`, `en.json`, `tr.json`) — confirm 100% key parity.
   - Merchant isolation check in `api_server.py:get_admin_user_castles` (`_verify_merchant_access_to_user`).
2. Run and verify test suites:
   - `python tools/verify_m7_ux_lifecycle.py`
   - `powershell -Command "Set-Location dashboard; npm run build"`
   - `python tests/run_all_tests.py`
   - `python tools/verify_m6_admin_scalability.py`
3. Deliver `handoff.md` with explicit verdict: **APPROVE** or **REQUEST_CHANGES**.
4. Notify orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`) via `send_message`.

