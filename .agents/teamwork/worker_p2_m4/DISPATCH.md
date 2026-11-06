# DISPATCH — Worker M4 (Memory & CPU Optimization — Leaks, Threads, WebSockets & Loops)
**Role**: Implementation Worker for Milestone 4 (F8, F9, F10, F11 / Requirement R3)
**Working directory**: `e:\osmanli\.agents\teamwork\worker_p2_m4\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
**Architectural Plan**: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 4)
**Survey Reference**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_2\survey_report.md` (Exact lines and leak points)

## Objectives
Implement Requirement R3: Memory & CPU Optimization across four critical vectors:

1. **Global Data Structures Lifecycle & Leak Elimination (`api_server.py` & `proxy/proxy_manager.py`)**:
   - `_castle_emails`: Ensure `_castle_emails.pop(castle_id, None)` is ALWAYS executed in `_bot_thread()`'s `finally:` block and early return paths on auth error (`api_server.py:708, 715`).
   - `_deleted_castles`: Clean up castle IDs safely once their threads have stopped and resources are released, preventing permanent unbounded set growth.
   - `proxy/proxy_manager.py`: When a castle is deleted in `delete_castle` (`api_server.py:1371`), purge its associated entry from `_castle_bindings` and persist.
   - Audit all 10 global structures (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`) for symmetric insertion/removal.

2. **Deterministic Thread Lifecycle & Join Timeouts (`api_server.py`)**:
   - Implement `_stop_and_join_bot(castle_id: str, timeout: float = 3.0) -> bool`:
     - Signal `_stop_events[castle_id].set()`.
     - OUTSIDE `_lock`, wait for the thread via `t.join(timeout=timeout)`.
     - If thread is still alive after timeout, move to `_stalled_threads` for diagnosis instead of leaving as an untracked zombie thread.
     - Clean up tracking references cleanly.
   - Apply `_stop_and_join_bot` across `stop_bot`, `stop_all_bots`, `delete_castle`, and `delete_user`.

3. **WebSockets Disconnect Detection & ThreadPool Offloading (`api_server.py`)**:
   - For `ws_logs`, `ws_status`, and `ws_user_status`: Add bidirectional disconnect detection (e.g. check for client disconnect or receive) so zombie socket loops terminate immediately and release resources upon client disconnect.
   - For `ws_user_status` (`api_server.py:3296-3310`): Eliminate the 0.8s SQLite polling loop via `asyncio.to_thread(_sync_collect_user_statuses)`. Replace it with an in-memory cache/snapshot check that pushes updates only when statuses actually change, preventing SQLite connection thrashing and ThreadPoolExecutor exhaustion.

4. **CPU Bottlenecks & Streaming Log Pruning (`bot_manager.py` & `api_server.py`)**:
   - In `bot_manager.py:3766-3768`: Replace `while slept < remaining: await asyncio.sleep(1.0)` with:
     `await asyncio.wait_for(self._async_stop_event.wait(), remaining)` (handling `TimeoutError` cleanly). This eliminates 1500 unnecessary wakeups per bot per 25-minute cycle and drops idle CPU to 0.0%.
   - In `api_server.py` `prune_log_file_24h`: Replace `lines = f.readlines()` with a streaming tail/truncate approach that avoids loading entire large log files into RAM.
   - Eliminate redundant `importlib.reload(sys.modules[mod_name])` upon every thread start (`api_server.py:846`).

5. **Build & Test Verification**:
   - Run `python tools/measure_baseline.py` to verify baseline health.
   - Run `python tests/run_all_tests.py` to confirm 30/30 platform tests pass.
   - Run `python tests/test_live_operations_m3.py` (4/4 PASS).

## Write Ownership
You exclusively own:
- `api_server.py` (global structures cleanup, thread join timeouts, websocket disconnects, SQLite polling offload, log pruning)
- `bot_manager.py` (async wait sleep optimization, reload elimination)
- `proxy/proxy_manager.py` (deleted castle proxy binding cleanup)
- Your working directory: `e:\osmanli\.agents\teamwork\worker_p2_m4\`

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


## 2026-11-02T23:39:02Z
You are Worker M4 (teamwork_worker).
Your working directory is: `e:\osmanli\.agents\teamwork\worker_p2_m4\`
Your dispatch document is: `e:\osmanli\.agents\teamwork\worker_p2_m4\DISPATCH.md`
The authoritative request is: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
The architectural plan is: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 4)
Survey analysis with exact line numbers: `e:\osmanli\.agents\teamwork\explorer_survey_p2_2\survey_report.md`

### MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
Strictly local workspace only: NO server uploads, deploys, or remote DB connections.

### Pre-Implementation Requirement (GEMINI.md Rule 5)
Create a technical report artifact `.md` in your working directory (`e:\osmanli\.agents\teamwork\worker_p2_m4\report_m4_plan.md`) BEFORE modifying any code or running commands.

### Scope of Work (Requirement R3 — Milestone 4)
1. **Global Data Structures Lifecycle & Leak Elimination (`api_server.py` & `proxy/proxy_manager.py`)**:
   - In `_bot_thread()`, ensure `_castle_emails.pop(castle_id, None)` is ALWAYS executed in `finally:` block and early return paths on auth error (`api_server.py:708, 715`).
   - Clean up `_deleted_castles` safely once their threads have stopped and resources are released, preventing permanent unbounded set growth.
   - When a castle is deleted in `delete_castle` (`api_server.py:1371`), purge its associated entry from `_castle_bindings` in `proxy/proxy_manager.py` and persist.
   - Audit all 10 global structures (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`) for symmetric insertion/removal.
2. **Deterministic Thread Lifecycle & Join Timeouts (`api_server.py`)**:
   - Implement `_stop_and_join_bot(castle_id: str, timeout: float = 3.0) -> bool`:
     - Signal `_stop_events[castle_id].set()`.
     - OUTSIDE `_lock`, wait for the thread via `t.join(timeout=timeout)`.
     - If thread is still alive after timeout, move to `_stalled_threads` for diagnosis instead of leaving as an untracked zombie thread.
     - Clean up tracking references cleanly.
   - Apply `_stop_and_join_bot` across `stop_bot`, `stop_all_bots`, `delete_castle`, and `delete_user`.
3. **WebSockets Disconnect Detection & ThreadPool Offloading (`api_server.py`)**:
   - For `ws_logs`, `ws_status`, and `ws_user_status`: Add bidirectional disconnect detection (e.g. check for client disconnect or receive) so zombie socket loops terminate immediately and release resources upon client disconnect.
   - For `ws_user_status` (`api_server.py:3296-3310`): Eliminate the 0.8s SQLite polling loop via `asyncio.to_thread(_sync_collect_user_statuses)`. Replace it with an in-memory cache/snapshot check that pushes updates only when statuses actually change, preventing SQLite connection thrashing and ThreadPoolExecutor exhaustion.
4. **CPU Bottlenecks & Streaming Log Pruning (`bot_manager.py` & `api_server.py`)**:
   - In `bot_manager.py:3766-3768`: Replace `while slept < remaining: await asyncio.sleep(1.0)` with:
     `await asyncio.wait_for(self._async_stop_event.wait(), remaining)` (handling `TimeoutError` cleanly). This eliminates 1500 unnecessary wakeups per bot per 25-minute cycle and drops idle CPU to 0.0%.
   - In `api_server.py` `prune_log_file_24h`: Replace `lines = f.readlines()` with a streaming tail/truncate approach that avoids loading entire large log files into RAM.
   - Eliminate redundant `importlib.reload(sys.modules[mod_name])` upon every thread start (`api_server.py:846`).
5. **Test Suite Verification**:
   - Create `tests/test_memory_cpu_m4.py` to hermetically verify:
     a) Symmetric cleanup of `_castle_emails` and `_deleted_castles`.
     b) `_stop_and_join_bot` timeouts and `_stalled_threads` quarantine.
     c) Proxy bindings cleanup on castle deletion.
     d) Async stop event cancellation within < 100ms instead of waiting for 1s sleep increments.
     e) Streaming log pruning without whole-file memory allocation.
   - Run `python tests/test_memory_cpu_m4.py`
   - Run `python tests/test_live_operations_m3.py` (4/4 PASS)
   - Run `python tests/run_all_tests.py` (30/30 PASS)
   - Run `python tools/measure_baseline.py`
