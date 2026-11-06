# Technical Report: Milestone 6 (Admin Dashboard Scalability & Master-Detail Table Splitting)

**Date**: 2026-11-02  
**Author**: Worker M6 (Teamwork Implementer, QA & Specialist)  
**Target Milestone**: Milestone 6  
**Reference Directives**: `DISPATCH.md`, `ORIGINAL_REQUEST.md` (R5, R6, R7, R8), `PROJECT.md` § Feature 11, GEMINI.md Rules 2 & 5.

---

## 1. Diagnosis & Rationale (تشخيص السبب ولماذا هذا الإجراء مطلوب)

### 1.1 Inefficiencies in `Admin.tsx`
- **Issue**: `dashboard/src/pages/Admin.tsx` currently renders the entire `filtered` list of users in a single DOM pass (both in the desktop `<table>` at line 924 and in the mobile cards list at line 1031).
- **Impact**: With dozens or hundreds of users, rendering all user rows along with their DOM trees, event handlers, and subcomponents causes DOM bloat, high initial paint times, sluggish scrolling, and frame drops during filter/search state updates.
- **Remediation**: Implement snappy, client-side pagination with a default page size of 25 (with options for 10, 25, 50, and 100). Crucially, search and filter queries (`debouncedSearch`, `filterPending`, `sortByLeastDays`) must seamlessly filter the entire dataset first, and then slice the results. Any change in filters or page size must immediately reset `currentPage` to 1. In compliance with GEMINI.md Rule 2, UI controls must be crisp, concise, without decorative word clutter or sluggish animations.

### 1.2 Monolithic Payload in `AdminUsersCastles.tsx` & Backend
- **Issue**: In `AdminUsersCastles.tsx`, the component fetches `fetchAdminUsersCastles` on mount. On the backend, `api_server.py` at line 1718 (`GET /api/admin/users-castles`) loads `db.get_all_users()` and `db.get_all_castles()`, loading every castle's complete JSON configuration (which can be 20–50 KB per castle).
- **Impact**: For an admin with dozens of users and hundreds of castles, the initial payload easily exceeds 2–10 MB. Network transfer is bloated, memory usage spikes, and initial page load stalls. Furthermore, when deleting or updating a single castle, either the entire monolithic query was refetched or complex full-table reconciliations were needed.
- **Remediation**:
  1. Split into **Master-Detail Architecture**:
     - **Master (Summary)**: Load initial user summary list with castle counts, running counts, and user metadata via `GET /api/admin/users-castles/summary`. The payload is lightweight (<60 KB).
     - **Detail (On-Demand)**: Fetch full castle objects and configurations ONLY when the admin expands a specific user accordion row via `GET /api/admin/users/{uid}/castles`.
  2. Cache expanded castle details using TanStack Query key `['admin_user_castles', uid]` with `staleTime: 30_000` (30s) and `gcTime: 300_000` (5 minutes).
  3. Scoped mutations: Deleting or modifying a castle invalidates only `['admin_user_castles', uid]` and updates summary counts, eliminating full table refetches.

### 1.3 Route-Level Code Splitting in `App.tsx`
- **Issue**: In `dashboard/src/App.tsx`, all routes—including secondary and heavy admin views (`AdminUsersCastlesPage`, `AdminLiveProcessesPage`, `AdminMerchantsPage`, `AdminProxiesPage`, `CastleDetailPage`, `SettingsPage`)—are imported statically at the top of the file.
- **Impact**: The initial JavaScript bundle contains all administrative code, charts, and heavy modals even for regular users visiting `/login` or `/dashboard`.
- **Remediation**: Use `React.lazy()` with `React.Suspense` to code-split these secondary and admin routes, keeping the initial bundle lean and loading admin code chunks strictly on demand.

---

## 2. Logic & Step-by-Step Architecture (المنطق والخطوات التي سيتم تطبيقها)

### Step 1: Backend API Endpoints in `api_server.py`
1. **Lightweight Summary Endpoint**: `GET /api/admin/users-castles/summary`
   - Authorization: `Depends(require_admin)`
   - Queries `db.get_all_users()` and aggregates castle counts (`castle_count`, `running_count`, `pending_count`) without deserializing heavy config payloads.
   - Returns JSON: `{"status": "success", "users": [...]}` with:
     - `uid`, `email`, `display_name`, `role`, `is_banned`, `created_at`, `tenant_domain`
     - `subscription`: `{ plan_id, plan_name, status, expires_at, max_castles_allowed }`
     - `castles_count`, `castle_count`, `running_count`, `active_count`, `pending_count`
     - Payload is < 60 KB.
2. **On-Demand User Castles Endpoint**: `GET /api/admin/users/{uid}/castles`
   - Authorization: `Depends(require_admin)`
   - Takes `uid: str` path parameter.
   - Fetches castles specifically for this user via `db.get_user_castles(uid)`.
   - Enriches each castle with real-time process state `_get_real_status(cid)`.
   - Returns JSON: `{"status": "success", "user_id": uid, "castles": [...]}`.

### Step 2: Client API Methods in `dashboard/src/lib/botApi.ts`
1. Export `AdminUserSummary` interface representing the lightweight user row.
2. Implement `fetchAdminUsersCastlesSummary(options?: RequestOptions): Promise<AdminUserSummary[]>`.
3. Implement `fetchAdminUserCastles(uid: string, options?: RequestOptions): Promise<Castle[]>`.

### Step 3: Client-Side Pagination in `dashboard/src/pages/Admin.tsx`
1. Add pagination states:
   - `pageSize` state (default: 25, options: 10, 25, 50, 100).
   - `currentPage` state (default: 1).
2. Reset effect: Whenever `debouncedSearch`, `filterPending`, `sortByLeastDays`, or `pageSize` changes, reset `currentPage` to 1.
3. Compute paginated slice:
   - `totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))`
   - `validPage = Math.min(Math.max(1, currentPage), totalPages)`
   - `paginatedUsers = filtered.slice((validPage - 1) * pageSize, validPage * pageSize)`
4. Replace raw mapping of `filtered` with `paginatedUsers` for both desktop table and mobile cards.
5. Add crisp, clutter-free pagination controls at the bottom of the table:
   - Item range info: e.g. `1–25 / 120`
   - Fast Previous / Next buttons, page selector.
   - Page size dropdown / chips: `10`, `25`, `50`, `100`.

### Step 4: Master-Detail Lazy Loading in `dashboard/src/pages/AdminUsersCastles.tsx`
1. Change primary query:
   - Fetch `fetchAdminUsersCastlesSummary` with query key `['admin_users_castles_summary']`.
   - Loading indicator displayed while summary loads.
2. Extract subcomponent `UserCastlesDetail`:
   - Subcomponent receives `user: AdminUserSummary`, `onDeleteCastle`, and `isExpanded`.
   - When `isExpanded` is true, runs `useQuery({ queryKey: ['admin_user_castles', user.uid], queryFn: ({ signal }) => fetchAdminUserCastles(user.uid, { signal }), staleTime: 30_000, gcTime: 300_000 })`.
   - Renders spinner during detail loading; renders `CastleCard` instances once loaded.
3. Scoped Cache Invalidation:
   - On castle delete: invalidate only `['admin_user_castles', user.uid]`, and optimistically decrement user's `castles_count` in `['admin_users_castles_summary']`.

### Step 5: Route-Level Code Splitting in `dashboard/src/App.tsx`
1. Replace static imports of heavy pages with `React.lazy()`:
   - `AdminPage = React.lazy(() => import('./pages/Admin').then(m => ({ default: m.AdminPage })))`
   - `AdminUsersCastlesPage = React.lazy(() => import('./pages/AdminUsersCastles').then(m => ({ default: m.AdminUsersCastlesPage })))`
   - `AdminLiveProcessesPage = React.lazy(() => import('./pages/AdminLiveProcesses').then(m => ({ default: m.AdminLiveProcessesPage })))`
   - `AdminMerchantsPage = React.lazy(() => import('./pages/AdminMerchants').then(m => ({ default: m.AdminMerchantsPage })))`
   - `AdminProxiesPage = React.lazy(() => import('./pages/AdminProxies').then(m => ({ default: m.AdminProxiesPage })))`
   - `CastleDetailPage = React.lazy(() => import('./pages/CastleDetail').then(m => ({ default: m.CastleDetailPage })))`
   - `SettingsPage = React.lazy(() => import('./pages/Settings').then(m => ({ default: m.SettingsPage })))`
   - `AccountsPage = React.lazy(() => import('./pages/Accounts').then(m => ({ default: m.AccountsPage })))`
2. Wrap route elements in `<React.Suspense fallback={<PageFallback />}>`.

### Step 6: Dedicated Verification Harness `tools/verify_m6_admin_scalability.py`
1. Validate client-side pagination logic (page size 25 default, boundaries, reset on search/filter changes).
2. Validate master-detail separation (summary endpoint vs on-demand detail endpoint).
3. Validate backend endpoint authentication, performance, and payload size (<60 KB).
4. Validate code splitting in `App.tsx` (`React.lazy` and `Suspense`).
5. Run full test suite:
   - `python tools/verify_m6_admin_scalability.py`
   - `npm run build`
   - `python tests/run_all_tests.py` (30/30).

---

## 3. Detailed Files, Line Numbers & Expected Outcomes (الملفات والسطور والأوامر المتأثرة)

| File | Target Lines / Area | Changes | Expected Outcome |
|------|---------------------|---------|------------------|
| `api_server.py` | ~1786 | Add `@app.get("/api/admin/users-castles/summary")` and `@app.get("/api/admin/users/{uid}/castles")` | Summary returns lightweight user list with counts; detail returns single user's castle array |
| `dashboard/src/lib/botApi.ts` | ~847 | Add `AdminUserSummary`, `fetchAdminUsersCastlesSummary`, `fetchAdminUserCastles` | Typed client API methods with `RequestOptions` and signal forwarding |
| `dashboard/src/pages/Admin.tsx` | ~611, ~924, ~1031, ~1198 | Implement `currentPage`, `pageSize` (default 25), filter reset effect, slice pagination, and responsive pagination UI controls | Smooth pagination across 25 items/page, reset to page 1 on filter, no word clutter |
| `dashboard/src/pages/AdminUsersCastles.tsx` | ~39, ~305, ~377 | Replace monolithic fetch with summary query; create `UserCastlesDetail` with `['admin_user_castles', uid]` query | Initial load <60 KB; on-demand detail loading upon expanding rows |
| `dashboard/src/App.tsx` | ~5-15, ~170-200 | Convert heavy pages to `React.lazy()` wrapped with `React.Suspense` | Split admin chunks from main bundle |
| `tools/verify_m6_admin_scalability.py` | New file | Author comprehensive verification script for pagination, master-detail API, and bundle splitting | 100% pass across all verification checks |

---

## 4. Verification & Safety Guardrails
- All modifications are strictly local (no remote servers or deployment per GEMINI.md Rule 4).
- No production database modifications.
- Existing endpoints remain backward-compatible.
- `tests/run_all_tests.py` must maintain 30/30 (100%) passing tests.
