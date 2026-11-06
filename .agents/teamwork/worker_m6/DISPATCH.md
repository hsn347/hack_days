# Dispatch Directive: Worker M6 — Admin Dashboard Scalability & Table Splitting

## 2026-11-02T19:54:00Z
- **Target Role**: teamwork_worker
- **Milestone**: Milestone 6: Admin Dashboard Scalability, Client-side Pagination & Master-Detail Table Splitting
- **Working Directory**: `e:\osmanli\.agents\teamwork\worker_m6\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R5, R6, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
You MUST create an independent technical report artifact (.md file) at:
`e:\osmanli\.agents\teamwork\worker_m6\technical_report_m6.md`
BEFORE modifying any code or executing any commands. The report must detail:
1. Diagnosis and why the changes are needed.
2. Step-by-step logic and changes to be applied.
3. Affected files, lines, and expected outcomes.

---

## Scope & Concrete Objectives

### 1. Client-Side Pagination & Ergonomics in `dashboard/src/pages/Admin.tsx`
- Implement clean, responsive client-side pagination with default page size of 25 (with selector for 10 / 25 / 50 / 100).
- Preserve real-time search filtering, role/status filtering, and column sorting seamlessly across pages.
- Ensure page resets to 1 whenever search query or filters change.
- Follow GEMINI.md Rule 2: Crisp, concise pagination controls, no word clutter, instant snappy transitions (no sluggish CSS sliding).

### 2. Master-Detail Table Splitting in `dashboard/src/pages/AdminUsersCastles.tsx`
- Replace the monolithic payload fetching pattern:
  - Implement a lightweight summary query that loads user summary rows with castle counts (<60 KB).
  - Implement lazy on-demand detail fetching: detailed castle configurations and task states are fetched ONLY when the admin clicks/expands a specific user accordion or row.
  - Cache expanded user castle details in TanStack Query using key `['admin_user_castles', uid]` with clean staleTime (30s) and gcTime (5m).
  - When an admin updates a castle status or configuration, update or invalidate only that specific user's query rather than re-fetching the entire table.

### 3. Backend Master-Detail Endpoints in `api_server.py`
- Verify or add lightweight summary endpoint `GET /api/admin/users-castles/summary`:
  - Returns array of `{ uid, email, display_name, castle_count, active_count, pending_count }`.
- Verify or add detailed endpoint `GET /api/admin/users/{uid}/castles`:
  - Returns castles and configs for that single user.
- Ensure all endpoints adhere to existing admin authorization (`verify_admin_access`).

### 4. Route-Level Code Splitting (Optional / Recommended)
- Review dashboard route declarations: ensure admin views or large secondary tabs use `React.lazy()` / `Suspense` with simple spinner to minimize the initial bundle size.

### 5. Verification Harness & Platform Integrity
- Author a dedicated verification harness: `tools/verify_m6_admin_scalability.py` checking:
  - Client-side pagination logic (page size 25, boundaries, filter reset).
  - Master-detail separation (summary payload vs on-demand detail loading).
  - API endpoint response formats and performance.
- Ensure `npx tsc --noEmit` and `npm run build` pass with 0 errors.
- Ensure `python tests/run_all_tests.py` passes 30/30 (100%).

---

## Exclusive File Boundaries
- `dashboard/src/pages/Admin.tsx`
- `dashboard/src/pages/AdminUsersCastles.tsx`
- `dashboard/src/components/admin/`
- `dashboard/src/lib/botApi.ts` (for admin summary/detail API methods)
- `api_server.py` (for admin summary endpoint / route handling)
- `tools/verify_m6_admin_scalability.py`

## Deliverables
1. `technical_report_m6.md` in your working directory (FIRST).
2. Code implementations in owned files.
3. Verification harness `tools/verify_m6_admin_scalability.py`.
4. Passing results for `verify_m6_admin_scalability.py`, `npx tsc --noEmit`, `npm run build`, and `tests/run_all_tests.py`.
5. Handoff report `handoff.md` in your working directory.
6. Notify orchestrator via `send_message`.

