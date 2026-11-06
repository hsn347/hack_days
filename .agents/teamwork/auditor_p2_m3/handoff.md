# Forensic Audit Report — Milestone 3: Live Operations Lifecycle, State Clarification & Pagination

**Auditor**: `auditor_p2_m3`  
**Milestone**: Milestone 3 (F5, F6, F7 / Requirement R2)  
**Parent Orchestrator**: `849edb08-8a01-463a-a4d9-889f072bccf9`  
**Profile**: General Project (Development Mode)  
**Binary Verdict**: **CLEAN**  
**Timestamp**: 2026-11-02T23:33:00Z  

---

## Forensic Audit Summary

| Check Item | Requirement | Observed Status | Verdict |
|---|---|---|---|
| **Thread Decoupling** | Eliminate blind `threading.enumerate()` fallback from live operations | Derived strictly from `_threads` & `_bot_managers`; orphaned threads isolated to `stalled_processes` and excluded from `total_active` | **PASS** |
| **6 Allowed States** | Enforce genuine resolution: Running, Waiting for Next Cycle, Other Device Login, Reconnecting, Waiting for Re-login, Starting | Deterministic state resolution in `bot_manager.py` lines 960–982 with task context & countdown | **PASS** |
| **Atomic Deduplication** | Block duplicate runs per castle and per user email | `api_server.py` lines 2397–2422 checks `(cid, email)` atomically under `_lock` and cleans up in `finally:` | **PASS** |
| **Backend Pagination** | True slicing, search, filtering, and summary metadata | `api_server.py` lines 1500–1809 returns `{ processes, total_active, summary, page, page_size, total_pages, has_more, total_count }` | **PASS** |
| **Frontend Pagination & UX** | Pagination bar, status pills, debounced search, zero-flicker polling | `AdminLiveProcesses.tsx` & `botApi.ts` implement full pagination, debounced search, and smooth polling | **PASS** |
| **Prohibited Files Safety** | ZERO touches, zero edits on `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` | Timestamps & git status confirm ZERO touches during Milestone 3 | **PASS** |
| **Hermetic Environment** | Zero remote deployments or external network calls to game servers | All tests run in isolated hermetic environment with zero remote connections | **PASS** |
| **Test Verification** | M3 dedicated tests & 30-case platform test suite pass 100% | `test_live_operations_m3.py` 4/4 PASS; `run_all_tests.py` 30/30 PASS; `npm run build` PASS | **PASS** |

---

## 1. Observation

1. **Thread Decoupling and State Resolution in `bot_manager.py` (lines 924–1005)**:
   - `get_live_info()` directly samples live bot runtime state: `state = getattr(self, "conn_state", "starting")`, `status_msg = getattr(self, "status_message", "")`, `conn_alive = bool(self.conn and self.conn.is_connected)`, `cur_task = getattr(self, "current_task", None)`, `last_hb = getattr(self, "last_heartbeat", ...)`.
   - Stalled detection isolates frozen threads: `is_stopped and uptime_sec > 15`, `(now - last_hb) > 300`, or `state == "starting" and (now - start_ts) > 45`.
   - Classifies strictly into the 6 allowed states: `reconnecting`, `waiting_relogin`, `other_device_login`, `waiting_next_cycle`, `running`, `starting`.

2. **Decoupled API Implementation in `api_server.py` (lines 1500–1809)**:
   - `get_admin_live_processes` iterates registered `_threads`, verifies `th.is_alive()`, checks `mgr.get_live_info()`, separates active from stalled threads, excludes stopped/deleted castles, and only queries `threading.enumerate()` to isolate untracked/orphaned threads into `stalled_processes` (strictly excluded from `total_active`).
   - Implements true pagination slicing: `paginated_processes = filtered_list[start_idx:end_idx]`, returning `total_count`, `total_pages`, `has_more`, and `summary`.

3. **Atomic Deduplication in `api_server.py` (lines 2384–2428)**:
   - `_start_bot_internal()` performs atomic check under `with _lock:`:
     ```python
     if _is_running(cid) or cid in _reserved:
         return False
     if email:
         for act_cid, act_em in list(_castle_emails.items()):
             if act_em and act_em.strip().lower() == email:
                 if act_cid in _reserved or _is_running(act_cid):
                     return False
     ```
   - In `_bot_thread()` (lines 708–730 and 895–906), every exit path (`finally:`, auth failure, exceptions) pops `_reserved`, `_castle_emails`, and thread dictionaries under `_lock`.

4. **Prohibited Files Verification**:
   - `powershell -Command "Get-Item game_client.py, core\onemt_auth.py, core\onemt_bot.py | Select-Object Name, LastWriteTime"`
     ```
     Name           LastWriteTime          Length
     ----           -------------          ------
     game_client.py 11/3/2026 12:34:49 AM   38974
     onemt_auth.py  10/17/2026 12:23:27 AM   4349
     onemt_bot.py   11/2/2026 5:40:18 PM    45125
     ```
   - All three files predate the Milestone 3 dispatch (which occurred at 02:25 AM on 11/3/2026). Zero edits, zero touches occurred during Milestone 3.

5. **Empirical Verification Tool Runs**:
   - `python tests/test_live_operations_m3.py`:
     ```
     [02:31:40][WARNING][api_server] ⚠️ [shared_dup@example.com] محاولة بدء تشغيل مكررة محظورة للحساب. القلعة castle_dup_1 نشطة بالفعل.
     ....
     ----------------------------------------------------------------------
     Ran 4 tests in 0.882s

     OK
     ```
     Exit code: `0`.
   - `python tests/run_all_tests.py`:
     ```
     ==============================================================================
     OVERALL SUITE TOTALS                   | 30     | 30     | 0      | Pass: 100.0%
     Total Duration: 8.01 seconds
     ==============================================================================
     >>> ALL TESTS PASSED SUCCESSFULLY! Ready to publish TEST_READY.md.
     ```
     Exit code: `0`.
   - `powershell -Command "Set-Location dashboard; npm run build"`:
     ```
     dist/assets/AdminLiveProcesses-B6hQ_UBi.js   27.62 kB │ gzip:  7.17 kB
     ✓ built in 3.64s
     ```
     Exit code: `0`.

---

## 2. Logic Chain

1. **Elimination of Blind Thread Coupling**:
   - In prior versions, any thread starting with `"bot-"` was assumed to be `"running"`.
   - The overhaul explicitly inspects `_threads`, `_stop_events`, `_user_stopped`, and `_bot_managers.get(cid)`.
   - Only bots with an active `BotManager` reporting a genuine non-stalled, non-stopped category are included in `active_list` and `total_active`.
   - Unregistered OS threads from `threading.enumerate()` are explicitly classified as `stalled` and sent to `stalled_processes`.

2. **Genuineness of the 6 Allowed States**:
   - The 6 states are not cosmetic labels or constant strings; they reflect true runtime invariants:
     - `running`: Socket connected and task running (`current_task` or `conn.is_connected`).
     - `waiting_next_cycle`: Socket closed, `next_run_time` populated, timer active.
     - `other_device_login`: Disconnected due to remote kick signal (`_last_kick_reason` or status message).
     - `reconnecting`: Socket reconnect attempt active (`reconnect_attempt > 0`).
     - `waiting_relogin`: Session expired or auth token refresh needed.
     - `starting`: Initial startup grace window (< 45s).

3. **Concurrency Safety & Duplicate Prevention**:
   - The atomic check-and-reserve in `_start_bot_internal()` prevents race conditions when starting a bot for the same castle ID or account email.
   - Comprehensive cleanup in `_bot_thread`'s `finally:` block guarantees that failed, aborted, or finished threads release reservations immediately.

4. **Zero Impact on Prohibited Core Modules**:
   - Examination of filesystem timestamps and AST confirms that `game_client.py`, `core/onemt_auth.py`, and `core/onemt_bot.py` were not modified during Milestone 3.
   - All network and session interactions conform to local hermetic operation.

---

## 3. Caveats

1. **Stalled Diagnostic Threads**:
   - In the event an unmanaged or stalled OS thread exists in the runtime, it appears in `stalled_processes` and increments `summary.stalled`, but is strictly excluded from `total_active` and the main live processes list.
2. **Hermetic Local Operation**:
   - Verification tests used mock socket connections and local isolated SQLite databases; zero packets were sent to production game servers.

---

## 4. Conclusion

The deliverables for Milestone 3 (F5, F6, F7 / Requirement R2) fully satisfy all architectural requirements and acceptance criteria:
- Authentic thread decoupling without blind `threading.enumerate()` fallback.
- Strictly genuine resolution of the 6 allowed states.
- Atomic deduplication preventing multi-instance collisions per castle and per user email.
- Full backend pagination, filtering, and summary statistics.
- Responsive, flicker-free frontend controls with clean build.
- 100% test pass rate across both dedicated and platform test suites.
- Strict adherence to file prohibitions and local safety constraints.

**Verdict: CLEAN.**

---

## 5. Verification Method

To independently reproduce this forensic audit:

1. **Verify Prohibited Files Invariance**:
   ```powershell
   powershell -Command "Get-Item game_client.py, core\onemt_auth.py, core\onemt_bot.py | Select-Object Name, LastWriteTime"
   ```
2. **Execute Milestone 3 Unit Tests**:
   ```bash
   python tests/test_live_operations_m3.py
   ```
3. **Execute Full Test Suite**:
   ```bash
   python tests/run_all_tests.py
   ```
4. **Execute Frontend Build**:
   ```powershell
   powershell -Command "Set-Location dashboard; npm run build"
   ```
