# Handoff Report — Explorer 2: Backend & Database Auditor

- **Agent Name**: Explorer 2 (Backend, Database, Concurrency & Security Auditor)
- **Target Role / Next Agent**: Supreme Orchestrator (44132d7d-07d0-4709-a292-a8e4727a82fd) / Implementation Agents
- **Date**: 2026-11-02
- **Integrity Mode**: Local Development (Read-Only)
- **Handoff Type**: Hard Handoff (Investigation & Forensic Baseline Complete)

---

## 1. Observation

### O1. Database Table Structure & Row Counts
- **Database Path**: `e:\osmanli\database\castles.db`
- **Tables and Counts** (verified via `tools/inspect_db_schema.py`):
  - `users`: 154 rows
  - `castle_states`: 663 rows
  - `system_settings`: 1 row
- **Missing Foreign Key**: In `castle_states` table definition (`core/database.py:123-164`), `user_id TEXT` is defined without `FOREIGN KEY (user_id) REFERENCES users(uid)`. No database-level cascading exists.

### O2. EXPLAIN QUERY PLAN Results (Full Table Scans)
Executing `EXPLAIN QUERY PLAN` on queries in `core/database.py` via `tools/inspect_db_schema.py`:
1. `EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE lower(email) = '...' OR lower(castle_id) = '...' LIMIT 1`:
   - Output: `{'id': 3, 'parent': 0, 'notused': 0, 'detail': 'SCAN castle_states'}`
2. `EXPLAIN QUERY PLAN SELECT castle_id, user_id, last_run_time FROM castle_states WHERE castle_id = '...' OR lower(castle_id) = '...' OR lower(email) = '...' LIMIT 1`:
   - Output: `{'id': 3, 'parent': 0, 'notused': 0, 'detail': 'SCAN castle_states'}`
3. `EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE user_id = '...' OR lower(user_id) = '...' ORDER BY created_at DESC`:
   - Output: `{'id': 3, 'parent': 0, 'notused': 0, 'detail': 'SCAN castle_states'}`, `{'id': 54, 'parent': 0, 'notused': 0, 'detail': 'USE TEMP B-TREE FOR ORDER BY'}`
4. `EXPLAIN QUERY PLAN SELECT * FROM users WHERE role NOT IN ('admin', 'merchant_admin') AND LOWER(email) NOT IN (...) ORDER BY created_at DESC`:
   - Output: `{'id': 3, 'parent': 0, 'notused': 0, 'detail': 'SCAN users'}`, `{'id': 35, 'parent': 0, 'notused': 0, 'detail': 'USE TEMP B-TREE FOR ORDER BY'}`

### O3. N+1 Query Multiplier in Admin Dashboard
- In `core/database.py:1690-1728` (`get_all_users_with_castles`):
  - Line 1693: `users = get_all_users(...)` (1 query returning 154 rows)
  - Lines 1696-1710: Loop iterates 154 times; executing 3 separate `COUNT(*)` queries per user on `castle_states`:
    `conn.execute("SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND is_active = 1 AND state != 'pending'", (uid,))`
    `conn.execute("SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ? AND (is_active = 0 OR state = 'pending')", (uid,))`
    `conn.execute("SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = ?", (uid,))`
  - Total queries executed per call to `/api/admin/users`: $1 + (3 \times 154) = 463$ queries.

### O4. Blocking Synchronous SQLite Operations Inside Async Event Loop
- In `api_server.py:3063-3089` (`ws_user_status`):
  - Line 3070: Synchronous `castles = db.get_user_castles(user_id)` is called inside `_collect_statuses()`.
  - Line 3083: Called every `0.8` seconds in `while True: await asyncio.sleep(0.8)`.
  - Effect: The single asyncio event loop thread is blocked on synchronous disk I/O and temp B-tree sorting every 800ms for every open client websocket.

### O5. Race Condition and Lost Updates in Configuration Mutations
- In `core/database.py:1150-1188` (`update_castle_config`):
  - Line 1158: `cur = conn.execute("SELECT config FROM castle_states WHERE castle_id = ?", (castle_id,))`
  - Line 1170: `merged_config = _sanitize_castle_config(_deep_merge_dict(current_config, config_dict))`
  - Line 1175: `conn.execute("UPDATE castle_states SET config = ?, last_updated = ? WHERE castle_id = ?", ...)`
  - No `version` check, no row-level locking, default `DEFERRED` transaction mode allows interleaved reads and non-atomic overwrites.

### O6. Security Vulnerability P0: Plaintext Password Exposure
- In `api_server.py:2767-2774`:
  - Route: `@app.get("/api/local/castles/{identifier}")` has NO authentication dependency (`Depends(get_current_user)` is omitted).
  - Calls `c = db.get_castle(identifier)`.
  - In `core/database.py:1502-1524`, `get_castle` runs `SELECT * FROM castle_states ...` and executes `return dict(row)`. Unlike `get_user_castles` (line 1057) and `get_castle_by_id` (line 1089), it DOES NOT call `d.pop("password", None)`.
  - Plaintext passwords are leaked to unauthenticated callers.

### O7. Security Vulnerability P0: BOLA/IDOR in Live Castle Data
- In `api_server.py:2776-2794`:
  - Route: `@app.get("/api/castle-data/{email}")`
  - Takes `{email}` parameter from path. Although `current_user` is injected via `Depends(get_current_user)`, there is ZERO validation checking if `email` belongs to `current_user["uid"]`.
  - Calls `sm.get_or_login(email=email, ...)`, opens `GameConnection(account)`, connects to the live game server, fetches full lord and castle data, and returns it to the caller.

### O8. Security Vulnerability P0: Parameter Spoofing in Bot Start
- In `api_server.py:2590-2631` (`start_bot`):
  - Line 2616 verifies `db.get_castle_by_id(req.castle_id, caller_uid)` to ensure the user owns `req.castle_id`.
  - Line 2625 passes `req` (containing unvalidated `req.email`) to `_start_bot_internal(req)`.
  - In `_bot_thread(req)` (`api_server.py:646`): `sm.get_or_login(email=req.email, ...)` looks up `req.email` in the shared `session_cache.json`. A malicious user can pass another user's email with their own `castle_id` and hijack that session.

### O9. 10 Unauthenticated Internal Endpoints
- In `api_server.py:2058-2587`:
  - `/api/internal/stop-all` (line 2394), `/api/internal/restart-all` (line 2472), `/api/internal/direct-start` (line 2574), `/api/internal/deploy-lock` (line 2152), `/api/internal/deploy-unlock` (line 2164), `/api/internal/gradual-start` (line 2354), `/api/internal/cancel-start-queue` (line 2446), `/api/internal/save-running-state` (line 2058), `/api/internal/debug-state` (line 2138), `/api/bot/conn-state` (line 2748).
  - All 10 routes lack authentication dependencies and lack IP whitelisting.

### O10. Concurrency Scaling Bottleneck & Busy Waiting
- In `api_server.py:2051` and `bot_manager.py:3652`:
  - 1 OS thread + 1 separate `asyncio.run()` event loop per running castle.
  - In `bot_manager.py:3763-3765`: `while slept < remaining: await asyncio.sleep(min(1.0, remaining - slept))` wakes up every 1.0 second during the 25-60 minute delay period. For 200 bots, this causes 200 wakeups and GIL context switches per second during idle periods.
- In `game_client.py:614`: `self._writer.close()` is called without `await self._writer.wait_closed()`.
- In `api_server.py:3199-3218`: Missing `@app.on_event("shutdown")`.

---

## 2. Logic Chain

1. **Query Performance Degradation**:
   - Observations O1 and O2 prove that indexes were created on raw column values (`email`, `user_id`, `tenant_domain`), whereas application code queries using `LOWER(email)`, `LOWER(user_id)`, and `LOWER(tenant_domain)`.
   - In SQLite B-Tree indexing, functions applied to indexed columns bypass standard indexes unless an expression index (`CREATE INDEX ... ON table(LOWER(column))`) or collation (`COLLATE NOCASE`) is defined.
   - Consequently, every single status check (`upsert_castle_conn_state`) and user fetch triggers a full table scan (`SCAN castle_states`), and every user list fetch triggers an in-memory temporary B-Tree sort (`USE TEMP B-TREE`).

2. **Admin Dashboard Lag**:
   - Observation O3 shows that loading the users page executes 463 queries due to the loop in `get_all_users_with_castles`. Combined with Observation O2 (table scan on each query), the admin endpoint generates massive read amplification and disk I/O contention.

3. **Event Loop Latency**:
   - Observation O4 demonstrates that WebSocket monitoring loops execute synchronous SQLite table scans directly on the main thread of the asyncio event loop every 800ms. Because asyncio is single-threaded cooperative multitasking, any synchronous blocking disk operation blocks all other concurrent requests and WebSocket message dispatching.

4. **Data Loss During Concurrent Mutations**:
   - Observation O5 traces the read-modify-write cycle in `update_castle_config`. Because the database connection defaults to deferred transactions and lacks OCC / versioning, concurrent mutations (e.g., auto-save toggle and manual form submit) overwrite each other's changes, leading to lost updates.

5. **Security & Boundary Isolation Compromise**:
   - Observations O6, O7, O8, and O9 reveal that object-level ownership checks are missing in multiple endpoints. Because `get_castle` omits password stripping and `/api/local/castles/{id}` omits authentication, plaintext passwords are exposed. Because `/api/castle-data/{email}` and `/api/bot/start` accept user-supplied emails without cross-checking database ownership, cross-account session hijacking and live data exfiltration are trivially possible.

6. **Process Stability and Memory Inefficiencies**:
   - Observation O10 shows that running 1 OS thread per bot with its own event loop and busy 1.0s polling creates high CPU context switching overhead, while un-awaited socket closing and lack of shutdown hooks risk socket leaks and unclean database checkpointing on server restarts.

---

## 3. Caveats

- **No Live Production Database**: Investigation was strictly conducted in the local development environment (`e:\osmanli\database\castles.db`). No live connection was made to production servers.
- **SQLite Single-File Limitations**: SQLite is a serverless, single-file embedded database. While WAL mode enables concurrent readers alongside a single writer, write operations are strictly serialized. Heavy concurrent write contention will always result in `SQLITE_BUSY` unless transactions are kept minimal (`BEGIN IMMEDIATE`) or batched.
- **Firebase Token Verification Mocking**: In local development without internet connectivity or valid `firebase_service_account.json`, `verify_id_token` falls back or fails. Testing API endpoints locally requires development bypass headers or valid local test tokens.

---

## 4. Conclusion

The backend architecture suffers from four major architectural bottlenecks:
1. **Severe Index Mismatches & N+1 Queries**: 100% full table scan rate on core queries due to `LOWER()` function calls bypassing indexes, combined with 463 queries executed sequentially in the admin panel.
2. **Missing OCC and Atomic Updates**: Configuration writes suffer from race conditions and lost updates due to deferred read-modify-write cycles without versioning.
3. **Four P0 Security Vulnerabilities**: Plaintext password leakage via unauthenticated `/api/local/castles/{id}`, BOLA/IDOR in `/api/castle-data/{email}`, parameter spoofing in `/api/bot/start`, and 10 unprotected `/api/internal/*` routes.
4. **Thread-Per-Castle Scaling Limits & Event Loop Blocking**: Synchronous SQLite calls in WebSockets block the event loop, while 1 OS thread per bot with 1-second busy wakeups wastes CPU and RAM.

---

## 5. Verification Method (Independent Reproduction)

To independently verify all findings:

### 1. Verify Full Table Scans and Query Plans
Run the dedicated inspection script in `tools/inspect_db_schema.py`:
```powershell
python tools/inspect_db_schema.py
```
- **Check**: Observe `SCAN castle_states` on `lower(email) = ?` and `lower(user_id) = ?`. Observe `USE TEMP B-TREE FOR ORDER BY` on `ORDER BY created_at DESC`.

### 2. Verify N+1 Query Multiplier in `core/database.py`
Inspect lines 1690-1728 of `core/database.py`:
- Count the queries in `get_all_users_with_castles`. Note that inside `for u in users:`, three `conn.execute` statements are issued per user.

### 3. Verify Plaintext Password Exposure
Inspect lines 2767-2774 of `api_server.py` and lines 1502-1524 of `core/database.py`:
- Confirm that `@app.get("/api/local/castles/{identifier}")` lacks `Depends(get_current_user)`.
- Confirm that `get_castle(identifier)` returns `dict(row)` without calling `d.pop("password", None)`.

### 4. Verify IDOR in Live Castle Data
Inspect lines 2776-2794 of `api_server.py`:
- Confirm that `get_castle_data(email: str, ...)` takes `email` from path but never checks if `email` exists in `db.get_user_castles(current_user["uid"])`.

### 5. Verify Event Loop Blocking in WebSockets
Inspect lines 3063-3089 of `api_server.py`:
- Confirm that `ws_user_status` calls `db.get_user_castles(user_id)` inside an async function on the main event loop every 800ms without `asyncio.to_thread`.
