# HANDOFF REPORT — Explorer Survey 1 (Admin Castles & Ops Explorer: R1 & R2)
**Agent**: `explorer_survey_p2_1`  
**Date**: 2026-11-02  
**Handoff Type**: Hard (Task complete)  
**Deliverable**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_1\survey_report.md`

---

## 1. Observation

### R1: Admin Castles Pagination & Lazy Loading
1. **Users Page Pagination Baseline**:
   - File: `e:\osmanli\dashboard\src\pages\Admin.tsx` (Lines 688–701, 1269–1333).
   - Directly observed: Default page size is 25 (`useState<number>(25)`), page size selector offers `[10, 25, 50, 100]`. Pagination uses range display `{startIndex + 1}–{endIndex} / {totalItems} مستخدم`, previous/next chevrons, and page indicator `{validPage} / {totalPages}`.
   - However, the pagination is implemented as a client-side slice: `filtered.slice(startIndex, endIndex)`.
2. **Current Admin Castles Page (`AdminUsersCastles.tsx`)**:
   - File: `e:\osmanli\dashboard\src\pages\AdminUsersCastles.tsx` (Lines 114–125, 214–246, 394–486).
   - Directly observed: Calls `fetchAdminUsersCastlesSummary()` via `['admin_users_castles_summary']`. Returns all users in the system without pagination. Filters client-side with `useMemo`, and renders all matching users via `.map()` into the DOM with **zero pagination**.
3. **Backend Database Querying & Config Bloat**:
   - Files: `e:\osmanli\api_server.py` (Lines 1788–1868) and `e:\osmanli\core\database.py` (Lines 1041–1081, 1631–1656).
   - Directly observed: `api_server.py` fetches all users and all castle states in memory. In `core/database.py`, `SELECT * FROM castle_states` loads the `config TEXT` column and parses JSON for every castle. A single castle config contains ~25 tasks and measures 15–25 KB. Loading 100 castles parses 1.5–2.5 MB of JSON text per request.
4. **Cache Invalidation Wiping Local Updates**:
   - File: `e:\osmanli\dashboard\src\pages\AdminUsersCastles.tsx` (Lines 149–168).
   - Directly observed: After an optimistic update (`qc.setQueryData`), the mutation handler immediately calls `qc.invalidateQueries({ queryKey: ['admin_users_castles_summary'] })`, triggering an unwanted full refetch of the entire list.

### R2: Live Operations Lifecycle & Pagination
1. **Thread Liveness Conflated with Live Operation**:
   - File: `e:\osmanli\api_server.py` (Lines 1493–1575).
   - Directly observed: `get_admin_live_processes` treats any thread where `th.is_alive()` is `True` as an active operation. It even scans `threading.enumerate()` for any thread starting with `"bot-"` (Line 1546) and blindly synthesizes a `"running"` state for orphan or dying threads.
2. **Leaked Tracking Collections**:
   - File: `e:\osmanli\api_server.py` (Lines 131–142, 677, 879–889, 1386, 2122).
   - Directly observed: `_castle_emails` is set on startup (`_castle_emails[castle_id] = email` at line 677), but never popped in the `finally` block (lines 879–889). `_deleted_castles: Set[str]` accumulates IDs on deletion but is never cleaned up.
3. **State Classification Mismatch**:
   - File: `e:\osmanli\bot_manager.py` (Lines 920–970) and `e:\osmanli\api_server.py` (Lines 1577–1590).
   - Directly observed: States are grouped into 4 rough categories (`running`, `waiting`, `other_login`, `reconnecting`). The required state `Waiting for Re-login` is missing/conflated. `BotManager.get_live_info()` does not track the specific task currently executing.
4. **No Pagination on Live Operations**:
   - Files: `e:\osmanli\api_server.py` (Line 1461) and `e:\osmanli\dashboard\src\pages\AdminLiveProcesses.tsx` (Lines 33–69).
   - Directly observed: Endpoint returns an unpaginated array of all processes. Frontend polls this endpoint every 5 seconds (`setInterval(..., 5000)`) with full replacement `setData(res)`.

---

## 2. Logic Chain

1. **From Observation 1 & 2 to R1 Design**:
   - Observation 1 establishes the exact visual and behavioral standard the user expects (page sizes `[10, 25, 50, 100]`, default 25, range counters, chevrons).
   - Observation 2 demonstrates that `AdminUsersCastles.tsx` currently lacks any pagination and renders all users at once.
   - Therefore, introducing true backend pagination with matching controls will eliminate DOM overload while fulfilling the requirement.
2. **From Observation 3 to Summary vs. Details Separation**:
   - Observation 3 proves that `config` JSON is the dominant payload bottleneck (15–25 KB per row).
   - Therefore, querying only lightweight columns in the summary list (`castle_id, email, user_id, is_active, state, conn_state, conn_message, next_run_time...`) and fetching `config` lazily on-demand when a castle card is expanded reduces payload by > 95% and eliminates JSON deserialization overhead.
3. **From Observation 4 to Local Mutation Pattern**:
   - Observation 4 shows that invalidating the summary query destroys the benefits of optimistic UI updates.
   - Therefore, editing or deleting a castle must update `['admin_user_castles', uid]` and `['admin_users_castles_summary', page, ...]` via `qc.setQueryData` without triggering query invalidation.
4. **From Observation 5 & 7 to R2 State Clarification**:
   - Observation 5 reveals that dead or dying threads are picked up by `threading.enumerate()` and reported as running.
   - Observation 7 proves that states are conflated and missing `Waiting for Re-login`.
   - Therefore, live operations must be strictly derived from verified `BotManager` instances under the 6 allowed states (Running, Waiting for Next Cycle, Other Device Login, Reconnecting, Waiting for Re-login, Starting), while stalled or dying threads are isolated into a diagnostic counter.
5. **From Observation 6 to Deduplication & Memory Leak Fix**:
   - Observation 6 identifies that `_castle_emails` leaks and `_deleted_castles` grows without bounds, while identifier mismatch allows double threads.
   - Therefore, implementing canonical `(castle_id, email)` resolution and atomic check-and-reserve will prevent duplicate operations.

---

## 3. Caveats

1. **Prohibited Files Untouched**:
   - Per the constitutional strict constraint, `game_client.py`, `core/onemt_auth.py`, and `core/onemt_bot.py` were NOT opened, read, modified, or touched. All live operation connection state analysis was performed via `bot_manager.py` and `api_server.py`.
2. **Read-Only Scope**:
   - As an explorer agent, no codebase files were modified. All proposals are documented in `survey_report.md` for the implementation agents.
3. **Database Concurrency**:
   - SQLite WAL mode is active (`PRAGMA journal_mode = WAL;`). Paginated queries must use read transactions with `timeout=10.0` to prevent blocking concurrent write updates.

---

## 4. Conclusion

1. **R1 (Admin Castles Pagination)**:
   - Must be implemented as true backend pagination in `api_server.py` and `core/database.py` with SQL `LIMIT` / `OFFSET` and `COUNT(*)`.
   - Payload must exclude `config` from summary rows, lazy-loading details on-demand.
   - Frontend `AdminUsersCastles.tsx` must adopt the Users page pagination bar and use localized `qc.setQueryData` updates upon edit/delete.
2. **R2 (Live Operations Lifecycle & Pagination)**:
   - Must decouple Thread liveness from BotManager state and strictly enforce the 6 allowed operational states.
   - Stalled threads must be isolated from `total_active` and reported under `summary.stalled`.
   - Duplicate operations must be prevented via canonical identifier resolution and atomic reservation.
   - Live operations must support true backend pagination (`page`, `page_size`, `search`, `status`) matching the Users page UX with zero-flicker polling.

---

## 5. Verification Method

To independently verify these observations and conclusions:
1. **Inspect Survey Report**:
   - Read `e:\osmanli\.agents\teamwork\explorer_survey_p2_1\survey_report.md`.
2. **Inspect Files and Lines**:
   - Check `dashboard/src/pages/Admin.tsx` lines 688–701 and 1269–1333 for User pagination baseline.
   - Check `dashboard/src/pages/AdminUsersCastles.tsx` lines 114–125 and 394–486 for unpaginated summary rendering.
   - Check `api_server.py` lines 1460–1630 for `get_admin_live_processes` thread enumeration and fallback.
   - Check `bot_manager.py` lines 920–970 for `get_live_info` state mapping.
   - Check `core/database.py` lines 1631–1656 for `SELECT *` and JSON config deserialization bloat.
3. **Invalidation Conditions**:
   - If `Admin.tsx` already uses backend pagination (verified: it uses client-side slice).
   - If `castle_states` does not store `config` as JSON (verified: it stores JSON config taking 15–25 KB per row).
