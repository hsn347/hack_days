# Dispatch Directive: Challenger M6 (Instance 2) — Master-Detail Payload & Accordion Stress Test

## 2026-11-02T20:09:00Z
- **Target Role**: teamwork_challenger
- **Milestone**: Milestone 6: Admin Dashboard Scalability, Client-side Pagination & Master-Detail Table Splitting
- **Working Directory**: `e:\osmanli\.agents\teamwork\challenger_m6_2\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R5, R6, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_m6\handoff.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
Create your technical report artifact before executing commands.

## Objective & Test Harness
1. Author and execute an independent empirical test script (e.g. `tools/stress_m6_master_detail.py`) verifying:
   - Payload size reduction: compare `/api/admin/users-castles/summary` size (<60 KB) vs legacy monolithic `/api/admin/users-castles`.
   - On-demand detail endpoint `/api/admin/users/{uid}/castles`: verifies isolation, loads only specified user's castles, validates admin auth (401/403 for non-admins).
   - Accordion expansion/collapse churn: rapid simulated toggles, TanStack Query cache hits within 30s staleTime, query key isolation (`['admin_user_castles', uid]`).
   - Scoped mutation invalidation: verify modifying one user's castle does NOT purge or refetch other users' cached details.
2. Run standard suites:
   - `python tools/verify_m6_admin_scalability.py`
   - `powershell -Command "Set-Location dashboard; npm run build"`
   - `python tests/run_all_tests.py`
3. Deliver `handoff.md` with explicit verdict: **APPROVE** or **REQUEST_CHANGES**.
4. Notify orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`) via `send_message`.

