# Technical Report: Empirical Stress Testing of Milestone 6 (Master-Detail Payload, Endpoint Isolation & Accordion Churn)

- **Author**: Challenger M6 (Instance 2) — Empirical Challenger
- **Role**: critic, specialist
- **Date**: 2026-11-02T20:12:00Z
- **Reference**: GEMINI.md Rule 5 (Mandatory Pre-Execution Technical Report) & AGENTS_CONSTITUTION.md Rule 13

---

## 1. Diagnosis & Motivation (تشخيص السبب ولماذا هذا الإجراء مطلوب)

In Milestone 6, Worker M6 introduced substantial architectural enhancements to resolve scalability bottlenecks in the Admin portal:
1. **Master-Detail Table Splitting**: Separating the monolithic `/api/admin/users-castles` endpoint (which dumped full JSON configurations for all castles across all users, reaching multi-megabyte payloads) into:
   - A lightweight summary endpoint: `GET /api/admin/users-castles/summary` (<60 KB budget).
   - An on-demand per-user castles endpoint: `GET /api/admin/users/{uid}/castles`.
2. **Frontend On-Demand Accordion & Query Caching**:
   - `AdminUsersCastles.tsx` renders accordions collapsed by default.
   - Upon row expansion, `UserCastlesDetail` triggers `useQuery(['admin_user_castles', user.uid])` with `staleTime: 30_000` and `gcTime: 300_000`.
   - On deletion, cache invalidation is scoped to `['admin_user_castles', uid]` with optimistic adjustment of summary counts, avoiding full re-fetch waterfalls.
3. **Client-Side Pagination**:
   - In `Admin.tsx`, users are paginated with page size 25 by default, selectors for [10, 25, 50, 100], and automatic reset to page 1 upon search/filtering.
4. **Route Code Splitting**:
   - `App.tsx` lazy-loads administrative views via `React.lazy()` and `React.Suspense`.

**The Role of Empirical Challenger**:
Worker M6 conducted static AST/regex checks and simulated math in `tools/verify_m6_admin_scalability.py`. As an empirical challenger, our duty is **adversarial empirical verification**:
- We must NOT trust static assertions or claimed metrics.
- We must author and execute an adversarial test harness (`tools/stress_m6_master_detail.py`) that actually invokes the FastAPI application / endpoints with real authentication contexts, compares true bytes transferred, tests authorization boundaries (401/403), validates UID isolation and path safety, simulates rapid accordion expand/collapse churn against TanStack Query caching semantics, and tests scoped mutation invalidation.
- We must independently execute the full suite of project tests and production build.

---

## 2. Test Logic & Step-by-Step Architecture (المنطق والخطوات التي سيتم تطبيقها)

The empirical stress test harness `tools/stress_m6_master_detail.py` will execute the following rigorous stress tiers:

### Tier 1: Real-Time Payload Benchmark (Summary vs Monolithic)
- Generate a representative synthetic system state (e.g. 50 users, each having 5-10 castles with authentic full JSON configurations of ~25 KB per castle).
- Compute and compare the raw bytes and transfer payload of:
  - Legacy monolithic payload (`/api/admin/users-castles` representation): Expected size ~6 to ~12.5 MB.
  - New master-detail summary payload (`/api/admin/users-castles/summary`): Expected size < 60 KB.
- Measure payload reduction ratio (target: >95% reduction).
- Verify all required summary fields exist: `uid`, `email`, `display_name`, `role`, `castles_count`, `running_count`, `pending_count`, `castle_previews`.

### Tier 2: Endpoint Isolation & Security Boundary Testing (`/api/admin/users/{uid}/castles`)
- Spin up or mock the FastAPI ASGI test client for `api_server.py`.
- **Unauthenticated test**: Send request with no admin credentials. Must reject with 401 Unauthorized / 403 Forbidden.
- **Regular user test**: Send request with regular non-admin user credentials. Must reject with 403 Forbidden.
- **Admin user test**: Send request with valid admin credentials. Must respond with 200 OK.
- **Data isolation test**: Create two distinct users (`user_alpha` with Castle A, and `user_beta` with Castle B). Call `/api/admin/users/user_alpha/castles` and assert that ONLY Castle A is returned, with ZERO leakage of Castle B.
- **Path & UID fuzzing / boundary test**: Call with non-existent user UID, empty UID, and path characters (`../`, `%20`, special characters). Must handle gracefully (e.g. empty list `[]` or 404/400) without 500 crashes or data leakages.

### Tier 3: Rapid Accordion Churn & TanStack Query Cache Simulation
- Build an exact replica harness of TanStack Query's cache state machine matching `staleTime: 30_000` (30 seconds) and `gcTime: 300_000` (5 minutes).
- Simulate an aggressive user interaction pattern:
  - User rapidly clicks open/close on 10 user rows 100 times over 5 seconds.
  - Assert that on first expand of each user, a network fetch is recorded (10 total fetches for 10 users).
  - Assert that all 90 subsequent rapid expand/collapse operations hit the cache directly: 0 additional network calls! Cache hit rate = 90%.
  - Verify that simulated time advancement past 30s transitions queries to stale, triggering background re-fetch upon subsequent expand.
  - Verify that simulated time advancement past 300s garbage-collects unused queries.

### Tier 4: Scoped Mutation Invalidation & Optimistic Cache Integrity
- Populate query cache with summary `['admin_users_castles_summary']` (containing User 1 and User 2) and detail queries `['admin_user_castles', 'u1']` and `['admin_user_castles', 'u2']`.
- Execute simulated castle deletion on User 1.
- Apply Worker M6's invalidation logic:
  - `qc.invalidateQueries({ queryKey: ['admin_user_castles', 'u1'] })`
  - Optimistic decrement in summary query for User 1.
- Assert that User 2's cache (`['admin_user_castles', 'u2']`) remains FRESH and is NOT invalidated or refetched.
- Assert that summary query for User 1 reflects the decremented castle count and removed castle preview.

### Tier 5: Client-Side Pagination & Boundary Edge Cases
- Test dataset of 0 items: totalPages = 1, page = 1, paginatedUsers = [].
- Test dataset of 1 item: totalPages = 1, page = 1, paginatedUsers = [1 item].
- Test dataset of 25 items: totalPages = 1, page = 1, paginatedUsers = [25 items].
- Test dataset of 26 items: totalPages = 2, page 1 = [25 items], page 2 = [1 item].
- Test out-of-bounds page clamping (page = -5 clamped to 1, page = 999 clamped to totalPages).
- Test search filter reset: changing filter string snaps `currentPage` back to 1.

---

## 3. Files to Be Created or Executed (الملفات والأوامر المنفذة بالتفصيل)

1. **Create Test Harness**: `tools/stress_m6_master_detail.py` (Empirical stress runner, ~350-450 lines of Python).
2. **Execute Harness**: `python tools/stress_m6_master_detail.py`
   - Expected Result: All stress assertions pass with 100% compliance.
3. **Execute Worker Verification**: `python tools/verify_m6_admin_scalability.py`
   - Expected Result: 38/38 checks pass.
4. **Execute Dashboard Production Build**: `powershell -Command "Set-Location dashboard; npm run build"`
   - Expected Result: Vite build finishes with 0 errors and chunks code-split.
5. **Execute Platform Full Test Runner**: `python tests/run_all_tests.py`
   - Expected Result: 30/30 platform tests pass.
6. **Deliver Final Artifact**: `.agents/teamwork/challenger_m6_2/handoff.md` with explicit APPROVE/REQUEST_CHANGES verdict.
