# Comprehensive Survey Report: Admin Castles & Live Operations (R1 & R2)
**Agent**: `explorer_survey_p2_1` (Admin Castles & Ops Explorer)  
**Date**: 2026-11-02  
**Status**: Completed (Read-Only Codebase Investigation)  
**Authoritative Request**: Requirements R1 & R2 from `ORIGINAL_REQUEST.md`  
**Reference Codebase**: `api_server.py`, `bot_manager.py`, `core/database.py`, `core/tenants.py`, `dashboard/src/...`

---

## 1. Executive Summary

A comprehensive, read-only architectural investigation was performed on the bot platform codebase to examine Requirement 1 (Admin Castles Pagination & Lazy Loading) and Requirement 2 (Live Operations Lifecycle, Accurate States & Pagination).

### Key Discoveries:
1. **R1 (Admin Castles)**:
   - **Current State**: On the Admin Castles page (`AdminUsersCastles.tsx`), the frontend currently calls `/api/admin/users-castles/summary`, which loads **all** users and castle summaries in a single request. The frontend then executes client-side filtering via `useMemo` and renders all cards into the DOM with **zero pagination**.
   - **Heavy Payload Bloat**: In `core/database.py` and `api_server.py`, querying castles regularly executes `SELECT * FROM castle_states` which pulls the `config` column. A single castle's `config` JSON is between 15 KB and 25 KB; loading 100 castles results in 1.5–2.5 MB of JSON text parsed in memory on every request.
   - **Frontend Discrepancy**: The Users page (`Admin.tsx`) implements a clean pagination UI (batch size default 25, selector `[10, 25, 50, 100]`, previous/next chevrons, range display `1–25 / 120`), but this pagination is purely client-side `filtered.slice(startIndex, endIndex)`. R1 mandates **true database-driven backend pagination** while mirroring the exact UI/UX presentation and batch size of the Users page.
   - **Cache Invalidation Flaw**: After an optimistic update (`qc.setQueryData`), existing mutation handlers immediately invoke `qc.invalidateQueries({ queryKey: ['admin_users_castles_summary'] })`, triggering a full refetch of the entire list and negating the localized update.

2. **R2 (Live Operations)**:
   - **Conflation of Thread Liveness with Operational State**: `/api/admin/live-processes` considers any thread where `th.is_alive()` is `True` as active. Even worse, it scans `threading.enumerate()` for any thread starting with `"bot-"` and synthesizes a `"running"` state for orphan or dying threads.
   - **Leaked & Unbounded Tracking Structures**: `api_server.py` manages `_threads`, `_stop_events`, `_bot_managers`, `_conn_states`, `_castle_emails`, `_castle_users`, and `_deleted_castles`. When threads stop or castles are deleted, references are popped without waiting for the thread (`th.join()`), leaving orphan background threads that continue running briefly and get misclassified as live. Furthermore, `_deleted_castles` grows indefinitely without cleanup.
   - **Missing State Definitions**: The 6 mandatory live states (Running, Waiting for Next Cycle, Other Device Login, Reconnecting, Waiting for Re-login, Starting) are currently conflated into 4 rough categories, omitting `Waiting for Re-login` and lacking explicit task tracking.
   - **No Pagination in Live Operations**: `/api/admin/live-processes` returns an unpaginated array of all processes, and `AdminLiveProcesses.tsx` polls this endpoint every 5 seconds, causing periodic re-render flickers.

---

## 2. Requirement 1 (R1): Admin Castles Pagination Deep-Dive

### 2.1 Current Implementation Breakdown

#### A. Users Page Pagination Pattern (`dashboard/src/pages/Admin.tsx`)
In `Admin.tsx`, user pagination is implemented on the frontend over the array returned by `useAllUsers()` (`/api/admin/users`):
- **Page Size**: `const [pageSize, setPageSize] = useState<number>(25)` (Lines 688-689).
- **Page Selector Options**: `[10, 25, 50, 100]` (Lines 1317-1330).
- **Current Page**: `const [currentPage, setCurrentPage] = useState<number>(1)`.
- **Search & Filter Reset**: An effect resets `currentPage` to 1 whenever search, filters, or `pageSize` changes (Lines 691-694).
- **Slicing Logic**:
  ```typescript
  const totalItems = filtered.length
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const validPage = Math.min(Math.max(1, currentPage), totalPages)
  const startIndex = (validPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, totalItems)
  const paginatedUsers = filtered.slice(startIndex, endIndex)
  ```
- **UI Presentation**:
  - Left indicator: `{startIndex + 1}–{endIndex} / {totalItems} مستخدم`
  - Center controls: Prev button (`ChevronRight` in RTL), page display `{validPage} / {totalPages}`, Next button (`ChevronLeft` in RTL).
  - Right controls: Buttons for `10`, `25`, `50`, `100`.

#### B. Current Admin Castles Page (`dashboard/src/pages/AdminUsersCastles.tsx`)
- Calls `fetchAdminUsersCastlesSummary()` via `['admin_users_castles_summary']`.
- Fetches all users and their castle previews in one massive JSON blob.
- Performs client-side filtering via `filteredUsers = useMemo(...)` (Lines 214-246).
- Directly renders all matching users via `filteredUsers.map(user => ...)` (Lines 394-486) into the DOM.
- **Result**: If the system contains 500 users and 2,000 castles, all 500 user cards are rendered in the DOM, causing noticeable scroll lag and memory overhead.

#### C. Backend SQLite Query Analysis (`core/database.py` & `api_server.py`)
1. `/api/admin/users-castles/summary` (Lines 1788-1869 of `api_server.py`):
   ```python
   users = db.get_all_users()
   cur = conn.execute("SELECT castle_id, user_id, email, is_active, state, conn_state FROM castle_states")
   castle_rows = cur.fetchall()
   ```
   - Fetches **all** users from SQLite.
   - Fetches **all** castle rows from `castle_states`.
   - Loops and stitches them in Python memory.
   - Does **not** take `page`, `page_size`, `search`, or `filter` parameters.
2. In `get_all_castles()` and `get_user_castles()` (`core/database.py` Lines 1041-1081, 1631-1656):
   - Executes `SELECT * FROM castle_states` which includes `config TEXT` and `raw_json TEXT`.
   - Iterates through all rows and runs `json.loads(d.get("config") or "{}")`.
   - Each castle config contains ~25 task sub-dictionaries, consuming 15–25 KB per row.

### 2.2 Target Architecture for Admin Castles Pagination

#### A. Database Query Structure (True Backend Pagination)
To achieve true database-driven pagination without pulling the entire database into Python or React:
1. **Summary SQL Query (Lightweight Columns Only)**:
   Explicitly select only summary columns, strictly excluding `config`, `password`, and `raw_json`:
   ```sql
   SELECT 
       u.uid, u.email, u.username, u.phone, u.role, u.is_banned, u.created_at, u.tenant_domain,
       u.plan_id, u.plan_name, u.subscription_status, u.subscription_expires_at, u.max_castles_allowed,
       COALESCE(c.castles_count, 0) AS castles_count,
       COALESCE(c.running_count, 0) AS running_count,
       COALESCE(c.pending_count, 0) AS pending_count
   FROM users u
   LEFT JOIN (
       SELECT 
           user_id,
           COUNT(*) AS castles_count,
           SUM(CASE WHEN state IN ('running', 'connected') OR is_active = 1 THEN 1 ELSE 0 END) AS running_count,
           SUM(CASE WHEN is_active = 0 OR state = 'pending' THEN 1 ELSE 0 END) AS pending_count
       FROM castle_states
       WHERE user_id IS NOT NULL AND user_id != ''
       GROUP BY user_id
   ) c ON u.uid = c.user_id
   WHERE (:tenant_filter IS NULL OR LOWER(u.tenant_domain) IN (:tenant_domains))
     AND (:search IS NULL OR (
         LOWER(u.email) LIKE :search_like 
         OR LOWER(u.username) LIKE :search_like 
         OR LOWER(u.uid) LIKE :search_like
         OR u.uid IN (SELECT user_id FROM castle_states WHERE LOWER(email) LIKE :search_like OR LOWER(castle_id) LIKE :search_like)
     ))
     AND (:filter_type IS NULL OR (
         (:filter_type = 'with_castles' AND COALESCE(c.castles_count, 0) > 0) OR
         (:filter_type = 'no_castles' AND COALESCE(c.castles_count, 0) = 0) OR
         (:filter_type = 'running' AND COALESCE(c.running_count, 0) > 0)
     ))
   ORDER BY u.created_at DESC
   LIMIT :limit OFFSET :offset;
   ```

2. **Count Query (for Total Items and Total Pages)**:
   A matching `SELECT COUNT(*) ...` query with the identical `WHERE` clauses to return the exact total count:
   ```sql
   SELECT COUNT(*) AS total_count
   FROM users u
   LEFT JOIN (...) c ON u.uid = c.user_id
   WHERE ...
   ```

3. **Pagination Response Metadata**:
   ```json
   {
     "status": "success",
     "page": 1,
     "page_size": 25,
     "total_count": 128,
     "total_pages": 6,
     "has_more": true,
     "summary_stats": {
       "total_users": 128,
       "total_castles": 412,
       "total_running": 85
     },
     "users": [ ... 25 items only ... ]
   }
   ```

#### B. Summary vs. Details Lazy-Loading Pattern
- **Summary Payload**: Only includes User identity, subscription status, counts, and lightweight preview identifiers (`id` and `email`). Payload size for 25 items is **< 15 KB** (compared to > 5 MB previously).
- **Details Payload (On-Demand)**:
  When an admin clicks a user card to expand it, `UserCastlesDetail` fires `fetchAdminUserCastles(user.uid)` (`/api/admin/users/{uid}/castles`).
  Only the castles belonging to that single expanded user are fetched and rendered.
  TanStack Query caches these details per user (`queryKey: ['admin_user_castles', uid]`, `staleTime: 30_000`, `gcTime: 300_000`).

#### C. Local Update Pattern (Zero Full-Page Refetch)
When an admin edits or deletes a castle:
1. **On Delete**:
   - Update user's castles detail query:
     ```typescript
     qc.setQueryData<Castle[]>(['admin_user_castles', userUid], old => 
       old ? old.filter(c => c.id !== castleId) : []
     )
     ```
   - Optimistically update the user's counts in the paginated summary query without re-fetching:
     ```typescript
     qc.setQueryData<PaginatedUsersCastlesResponse>(
       ['admin_users_castles_summary', page, pageSize, search, filter],
       old => {
         if (!old) return old
         return {
           ...old,
           users: old.users.map(u => u.uid === userUid ? {
             ...u,
             castles_count: Math.max(0, u.castles_count - 1),
             castle_previews: (u.castle_previews || []).filter(cp => cp.id !== castleId)
           } : u)
         }
       }
     )
     ```
   - **Crucial**: Do NOT call `qc.invalidateQueries({ queryKey: ['admin_users_castles_summary'] })`. This prevents full list reloads and flickering.

#### D. Super Admin vs. Merchant Admin Scoping
- **Super Admin (`ibraboths@gmail.com`)**: Can query without domain restrictions (`tenant_domains = None`), seeing all users across all domains.
- **Merchant Admin (`is_merchant_admin == True`)**:
  - `admin["merchant_tenant"]["domains"]` provides the list of authorized domains (e.g., `["nurjanbot.online", "www.nurjanbot.online"]`).
  - The SQLite query mandates `WHERE LOWER(u.tenant_domain) IN (:tenant_domains)`.
  - Attempts to access users outside this domain are rejected with HTTP 403 via `_verify_merchant_access_to_user()`.

---

## 3. Requirement 2 (R2): Live Operations Lifecycle & Pagination Deep-Dive

### 3.1 Current Deficits in Live Operations Management

#### A. Conflating Thread Existence with Live Operation
In `api_server.py` (Lines 1493-1574):
```python
for cid, th in list(_threads.items()):
    if not th.is_alive():
        continue
    ...
```
And in fallback step 2:
```python
for th in threading.enumerate():
    if th.name.startswith("bot-") and th.is_alive() and th.ident not in registered_idents:
        ...
        active_list.append({ ... "state": "running", "live_category": "running" ... })
```
- Just because an OS thread is in `is_alive()` state does not mean a bot operation is running!
- A thread can be alive while:
  1. Blocked in a slow network timeout or socket shutdown.
  2. Caught in an exception loop.
  3. Paused or waiting indefinitely due to an unhandled condition.
  4. Orphaned from a previously deleted castle.
- Falling back to `threading.enumerate()` causes dead/dying threads to appear as `"running"` operations.

#### B. State Leakage and Unbounded Growth
In `api_server.py`:
- `_castle_emails` is populated on thread startup (`_castle_emails[castle_id] = email` at line 677), but in the `finally` block (lines 879-889), `_castle_emails.pop(castle_id, None)` is **missing**! This causes `_castle_emails` to leak memory indefinitely.
- `_deleted_castles: Set[str]` accumulates castle IDs upon deletion (line 1386, 2122) to prevent threads from writing back to SQLite. However, deleted castle IDs are **never purged** from `_deleted_castles`, growing monotonically over the lifetime of the process.

#### C. Duplicate Operations for the Same Castle/Resource
Duplicate threads for the same castle occur due to three distinct race conditions:
1. **Identifier Casing & Resolution**: Start requests sometimes pass `castle_id` while internal auto-resume passes `email`. Because `_threads` was keyed solely by the passed string, two distinct entries (`castle_123` and `lord@game.com`) could be created in `_threads` for the exact same physical game account.
2. **Double-Start Race Condition**: During `_start_bot_internal(req)`, if `_is_running(req.castle_id)` evaluates to `False` (for example, if the previous thread received a stop signal but has not yet finished joining), `_threads.pop(req.castle_id, None)` is invoked, dropping the reference to the dying thread and launching a second thread immediately. Both threads then attempt to connect to the game server with the same credentials, kicking each other back and forth in an infinite reconnect loop.
3. **Orphan Thread Pick-up**: When a castle is stopped or deleted, `_threads.pop(cid, None)` removes it from `_threads`, but the thread may take 1–3 seconds to terminate. During those seconds, `get_admin_live_processes` scans `threading.enumerate()`, detects the thread name `bot-xxx`, and re-adds it to the live processes list!

### 3.2 Decoupling the Operational Lifecycle

To ensure complete accuracy, the platform must cleanly separate four distinct layers:

```
┌────────────────────────────────────────────────────────┐
│ 1. Thread Layer (Runtime OS Process)                   │
│    alive | terminating | dead                          │
└──────────────────────────┬─────────────────────────────┘
                           │ owns
┌──────────────────────────▼─────────────────────────────┐
│ 2. BotManager Layer (Execution Orchestrator)           │
│    idle | starting | running_tasks | cycle_wait        │
└──────────────────────────┬─────────────────────────────┘
                           │ manages
┌──────────────────────────▼─────────────────────────────┐
│ 3. Connection Layer (Game Socket Session)              │
│    connected | disconnected | reconnecting             │
└──────────────────────────┬─────────────────────────────┘
                           │ executes
┌──────────────────────────▼─────────────────────────────┐
│ 4. Task Layer (Specific Pipeline Step)                 │
│    march_manager | city_harvest | building | none      │
└────────────────────────────────────────────────────────┘
```

### 3.3 The 6 Allowed Operational States

Any operation displayed in Live Operations must strictly resolve to one of the following 6 states:

| # | Allowed State | Code Identifier | Exact Meaning & Source of Truth |
|---|---|---|---|
| 1 | **Running** | `running` | Actively executing a verified, known task from `pipeline` (e.g. `march_manager`, `city_harvest`, `building`). Sockets are verified connected (`conn.is_connected == True`), recent heartbeat (`< 60s`), `_stop_event` is unset. |
| 2 | **Waiting for Next Cycle** | `waiting_next_cycle` | Successfully completed the previous cycle, cleanly closed/idled game connection to conserve server/proxy resources, and waiting for the fixed delay. `next_run_time` is valid, non-null, and in the future. |
| 3 | **Other Device Login** | `other_device_login` | Game server issued a kick packet (code 10006 / "other device"). Bot immediately disconnected and entered backoff waiting mode (e.g., 20–30 min) to allow the human player uninterrupted play. |
| 4 | **Reconnecting** | `reconnecting` | Socket disconnected due to transient network/proxy drop. Bot is actively executing retry attempts with exponential/linear backoff (`reconnect_attempt <= max_attempts`). |
| 5 | **Waiting for Re-login** | `waiting_relogin` | Session ticket or SDK auth failed with a recoverable error. Bot is pausing before re-authenticating to prevent triggering game anti-bot login rate limits. |
| 6 | **Starting** | `starting` | Thread was launched within the last 30 seconds (`now - start_time < 30s`). BotManager is initializing and resolving credentials. If this state persists beyond 45 seconds without transitioning to `running` or `error`, it transitions to `stalled`. |

#### Excluded States (MUST NOT appear in Live Operations):
- **User Stopped**: `cid in _user_stopped` or `_stop_event.is_set()`.
- **Naturally Completed**: Single-run mode completed with no future cycle.
- **Failed / Errored**: Explicit auth error, password mismatch, or unrecoverable exception.
- **Cancelled / Deleted**: Castle deleted from SQLite or deactivated (`is_active == False`).
- **Dangling / Stale**: In-memory structures referring to non-existent database records.

### 3.4 Diagnostic Isolation of Stalled Threads

A thread or process is classified as **`stalled`** if any of the following conditions hold:
1. Thread is alive in the OS runtime, but no state/heartbeat update has been posted for more than 5 minutes.
2. `stop()` was signaled (`_stop_event.is_set() == True`) more than 30 seconds ago, but the thread has failed to terminate (`th.is_alive() == True`).
3. An alive thread named `bot-*` exists in `threading.enumerate()` but has no entry in `_bot_managers` and was created > 60 seconds ago.
4. The castle associated with the thread does not exist in the database or was deleted.

**Diagnostic Handling**:
- Stalled threads are **strictly excluded** from `total_active` and the main live operations list.
- They are counted in a separate diagnostic summary counter: `summary.stalled_count`.
- Admin telemetry provides a diagnostic tab or expandable section showing stalled threads with thread ID, runtime uptime, and a "Force Kill / Terminate" action.

### 3.5 True Backend Pagination for Live Operations

#### A. Backend Endpoint Specification
- **Route**: `GET /api/admin/live-processes`
- **Query Parameters**:
  - `page: int = Query(1, ge=1)`
  - `page_size: int = Query(25, ge=10, le=100)`
  - `search: Optional[str] = Query(None)` (searches castle email, castle ID, user email, lord name)
  - `status: Optional[str] = Query(None)` (`all`, `running`, `waiting_next_cycle`, `other_device_login`, `reconnecting`, `waiting_relogin`, `starting`)
- **Processing Logic**:
  1. Collect all genuine live operations from `_bot_managers` under `_lock`.
  2. Filter out stopped, deleted, and dead threads.
  3. Deduplicate by canonical castle ID.
  4. Classify each operation into one of the 6 allowed states (or flag as stalled).
  5. Compute aggregate summary metrics (`total_active`, `running`, `waiting_next_cycle`, `other_device_login`, `reconnecting`, `waiting_relogin`, `starting`, `stalled`).
  6. Apply `search` and `status` filters.
  7. Compute `total_count = len(filtered_list)`.
  8. Slice the list: `start = (page - 1) * page_size`, `end = start + page_size`.
  9. Return paginated response.

#### B. Response Structure
```json
{
  "status": "success",
  "page": 1,
  "page_size": 25,
  "total_count": 48,
  "total_pages": 2,
  "has_more": true,
  "summary": {
    "total_active": 48,
    "running": 22,
    "waiting_next_cycle": 18,
    "other_device_login": 4,
    "reconnecting": 3,
    "waiting_relogin": 1,
    "starting": 0,
    "stalled": 2
  },
  "processes": [ ... 25 items ... ]
}
```

#### C. Frontend UI/UX Alignment (`AdminLiveProcesses.tsx`)
- Embed the exact pagination controls from `Admin.tsx`:
  - Range and count: `1–25 / 48 عملية حية`
  - Chevrons (Prev / Next) with `validPage / totalPages`
  - Page size buttons: `[10, 25, 50, 100]`
- **Zero-Flicker Background Polling**:
  - Auto-refresh maintains the user's current `page`, `page_size`, and filter selections.
  - Cards use stable keys (`proc.castle_id`).
  - Loading indicators use quiet background spinners (`isFetching`) rather than replacing the entire card list with a full-page loading skeleton.

### 3.6 Concrete Deduplication Mechanism

To guarantee that no duplicate operations ever run or appear for the same castle or account:
1. **Canonical Identifier Resolution**:
   Before performing any dictionary lookup or lock acquisition, resolve the target to a canonical pair:
   `(canonical_castle_id, canonical_email_lowercase)`.
2. **Canonical Active Registry**:
   Maintain a bidirectional tracking map:
   `_active_by_cid: Dict[str, threading.Thread]`
   `_active_by_email: Dict[str, str]` (maps `email -> castle_id`)
3. **Atomic Check-and-Reserve**:
   Inside `_start_bot_internal(req)`:
   ```python
   with _lock:
       cid = req.castle_id
       email = req.email.strip().lower()
       
       # Check if already running under either castle_id OR email
       if cid in _active_by_cid or email in _active_by_email:
           existing_th = _active_by_cid.get(cid) or _active_by_cid.get(_active_by_email.get(email))
           if existing_th and existing_th.is_alive():
               log.warning(f"⚠️ [{email}] Attempt to start duplicate operation blocked. Thread {existing_th.ident} is already alive.")
               return False
       
       # If an old dying thread is still terminating, wait up to 2 seconds
       old_th = _threads.get(cid)
       if old_th and old_th.is_alive():
           old_ev = _stop_events.get(cid)
           if old_ev: old_ev.set()
   ```
4. **Clean Join on Replacement**:
   If an old thread exists, wait with a short timeout `old_th.join(timeout=2.0)` outside the global lock before creating the new thread.
5. **Elimination of Blind Orphan Fallback**:
   Remove the unbounded `threading.enumerate()` scanner in `get_admin_live_processes`. Only threads properly registered with an active `BotManager` instance are reported as live operations.

---

## 4. Architectural Comparison & Gap Analysis

| Aspect | Current Architecture | Required Target Architecture |
|---|---|---|
| **Castles Querying** | Entire table loaded (`SELECT * FROM castle_states`) including heavy `config` JSON for all castles. | Lightweight summary query (`SELECT id, email, user_id, is_active, state...`) excluding `config`. |
| **Admin Castles Pagination** | None. All user summaries loaded; client-side filtering; all DOM nodes rendered. | True backend SQLite pagination with `LIMIT ? OFFSET ?`, `COUNT(*)`, matching Users page UI. |
| **Castle Config Loading** | Eagerly loaded for all castles on initial page load. | Lazy-loaded on-demand only when a specific castle card or config modal is opened. |
| **Mutation Updates** | Invalidation of `['admin_users_castles_summary']` forces complete refetch. | Optimistic local update via `qc.setQueryData`; no invalidation of paginated query. |
| **Live Operations Source** | `th.is_alive()` check + blind `threading.enumerate()` fallback. | Decoupled verification: Thread alive + BotManager running + Socket connected + Active task. |
| **Live Operations States** | 4 loosely defined categories (`running`, `waiting`, `other_login`, `reconnecting`). | Strictly 6 real states (`running`, `waiting_next_cycle`, `other_device_login`, `reconnecting`, `waiting_relogin`, `starting`). |
| **Stalled Threads** | Misclassified as `"running"` or ignored in memory leaks. | Detected by heartbeat/timeout rules, isolated from `total_active`, reported in diagnostic counter. |
| **Live Operations Pagination** | None. Full array returned and polled every 5s. | Backend pagination matching Users page (`page`, `page_size`, `total_count`, `has_more`), zero-flicker polling. |
| **Deduplication** | Keyed by string `req.castle_id`; email collisions possible. | Canonical `(castle_id, email)` resolution and atomic check-and-reserve. |
| **Merchant Scoping** | Inconsistent across sub-queries. | Strict SQL-level filtering by `tenant_domain` for all merchant admin requests. |

---

## 5. Verification & Safety Constraints

1. **Strict Prohibition Compliance**:
   - `game_client.py`: NOT opened, NOT read, NOT modified, NOT touched.
   - `core/onemt_auth.py`: NOT opened, NOT read, NOT modified, NOT touched.
   - `core/onemt_bot.py`: NOT opened, NOT read, NOT modified, NOT touched.
2. **Local Environment Only**:
   - Zero production network calls, deployments, or remote server uploads.
   - All investigations performed strictly on local files.
3. **Non-Breaking API Compatibility**:
   - Existing parameters and response formats are preserved with optional pagination query parameters (`page`, `page_size`) defaulting gracefully to full results when omitted by older clients.

---
*Report compiled by explorer_survey_p2_1 on 2026-11-02.*
