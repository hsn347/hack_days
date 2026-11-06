# DISPATCH — Worker M2 (Admin Castles Pagination & Lazy Loading)
**Role**: Implementation Worker for Milestone 2 (F2, F3, F4 / R1)
**Working directory**: `e:\osmanli\.agents\teamwork\worker_p2_m2\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R1)
**Architectural Plan**: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 2)
**Survey Reference**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_1\survey_report.md` (Section 2)

## Objectives
Implement Requirement R1: Admin Castles Pagination & Lazy Loading:
1. **Database Layer (`core/database.py`)**:
   - Add database query function for paginated users and castles summary with SQL `LIMIT` and `OFFSET` and `COUNT(*)`.
   - Support `search` (matching username, user email, castle email, castle ID), `filter_status`, and `tenant_domains` (merchant isolation).
   - Ensure the summary query strictly selects lightweight columns (`castle_id, user_id, email, is_active, state, conn_state, conn_message, next_run_time...`) and strictly EXCLUDES `config TEXT` and `raw_json TEXT`.
   - Provide an on-demand detail function `get_user_castles_detailed(user_id)` or `get_castle_config(castle_id)` to load full configuration only when requested.
2. **API Layer (`api_server.py`)**:
   - Update `GET /api/admin/users-castles/summary` to accept `page: int = 1`, `page_size: int = 25`, `search: str = ""`, `filter_status: str = "all"`.
   - Return `{ items, total, page, page_size, total_pages, has_more }`.
   - Ensure `GET /api/admin/users/{uid}/castles` provides full castle details including `config` for single expanded user.
   - Preserve Super Admin vs Merchant Admin scoping and tenant data isolation.
3. **Frontend Layer (`dashboard/src/pages/AdminUsersCastles.tsx` & `dashboard/src/lib/botApi.ts`)**:
   - Update `botApi.ts` to pass pagination params (`page`, `pageSize`, `search`, `filterStatus`) and return pagination envelope.
   - In `AdminUsersCastles.tsx`, implement the exact pagination UI matching `Admin.tsx`:
     - Page selector options: `[10, 25, 50, 100]`, default 25.
     - Chevrons (prev/next), current page / total pages, range counter (`{startIndex + 1}–{endIndex} / {total} مستخدم`).
     - Reset `currentPage` to 1 on search or filter change.
   - Implement lazy loading: fetch detailed castle config only when expanding a user or castle accordion.
   - Local mutation update: when editing or deleting a castle, update TanStack Query cache locally via `qc.setQueryData` for both summary and detail caches, WITHOUT calling `qc.invalidateQueries({ queryKey: ['admin_users_castles_summary'] })` which destroys the local update.
4. **Build & Test Verification**:
   - Run `powershell -Command "Set-Location dashboard; npm run build"` to verify zero TypeScript errors.
   - Run `python tests/run_all_tests.py` to confirm 30/30 platform tests pass.
   - Verify `python tools/measure_baseline.py` continues to pass.

## Write Ownership
You exclusively own:
- `core/database.py` (pagination and config queries)
- `api_server.py` (admin castles endpoints)
- `dashboard/src/pages/AdminUsersCastles.tsx`
- `dashboard/src/lib/botApi.ts`
- Your working directory: `e:\osmanli\.agents\teamwork\worker_p2_m2\`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
Strictly local workspace only: NO server uploads, deploys, or remote DB connections.

## Pre-Implementation Requirement
Create a technical report artifact `.md` in your working directory per GEMINI.md Rule 5 before modifying code or running build commands.
