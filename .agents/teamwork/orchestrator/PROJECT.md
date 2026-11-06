# Project: Platform Reliability, Admin Pagination & Memory Overhaul

## Architecture
- **Backend**: FastAPI (`api_server.py`), AsyncIO, SQLite WAL mode (`database/castles.db`).
- **State & Bot Engine**: `bot_manager.py`, in-memory thread & state registries, WebSocket streaming.
- **Frontend**: React 18, TypeScript, Tailwind CSS, TanStack Query v5, Zustand v5 (`dashboard/src/`).
- **Inspection & Testing**: Hermetic baseline measurement (`tools/measure_baseline.py`), 18-scenario harness (`tests/test_mandatory_scenarios.py`), soak tester (`tools/soak_test_lifecycle.py`).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Baseline Measurement Tooling | Multi-metric baseline profiling tool (RSS MB via ctypes/psutil, tracemalloc, CPU %, threads, handles, sockets, queues, dicts, WAL) | M1 | R4 |
| 2 | Admin Castles Backend Pagination | SQL pagination (`LIMIT`, `OFFSET`, `COUNT(*)`, search, filter, merchant tenant isolation) in `core/database.py` & `api_server.py` | M2 | R1 |
| 3 | Admin Castles Config Separation | Exclude heavy `config` JSON from summary query; lazy-load castle details on demand when expanding card | M2 | R1 |
| 4 | Admin Castles Frontend Pagination | Mirror Users page pagination UI (`[10, 25, 50, 100]`, default 25, range counters, chevrons) with local mutation updates (`setQueryData`) | M2 | R1 |
| 5 | Live Operations State Decoupling | Decouple thread liveness from bot state; enforce 6 allowed states (Running, Waiting for Next Cycle, Other Device Login, Reconnecting, Waiting for Re-login, Starting) | M3 | R2 |
| 6 | Stalled Thread Isolation & Deduplication | Isolate orphan/stalled threads into `stalled` diagnostic counter; prevent duplicate operations per castle with atomic check-and-reserve | M3 | R2 |
| 7 | Live Operations Backend Pagination & Zero-Flicker UI | Implement backend pagination (`page`, `page_size`, `search`, `status`) in API; update `AdminLiveProcesses.tsx` with smooth, flicker-free polling | M3 | R2 |
| 8 | Global Data Structures Leak Cleanup | Clean up `_castle_emails` in `finally:`, secure early returns in `_bot_thread`, purge `_deleted_castles` safely, clean `_castle_bindings` in proxy manager | M4 | R3 |
| 9 | Thread Lifecycle Management & Join Timeouts | Implement deterministic stop signals and `thread.join(timeout=3.0)` outside global locks across all stop/delete paths | M4 | R3 |
| 10 | WebSockets Disconnect & ThreadPool Protection | Add disconnect detection to `ws_logs`, `ws_status`, `ws_user_status`; eliminate 0.8s SQLite polling spam in `asyncio.to_thread` | M4 | R3 |
| 11 | CPU Optimization & Streaming Log Pruning | Replace 1-second busy sleep in `bot_manager.py` with `asyncio.wait_for`; stream/tail logs without `f.readlines()`; remove redundant `importlib.reload` | M4 | R3 |
| 12 | 18 Mandatory Test Scenarios | Hermetic test suite verifying all 18 specified operational and failure scenarios | M5 | R4 |
| 13 | Multi-Cycle Continuous Soak Testing | Automated soak test verifying memory leak regression slope $\le 0.05$ MB/cycle and zero leaked threads/handles | M5 | R4 |
| 14 | Post-Fix Measurement & Final Comprehensive Report | Measure post-fix baseline under identical conditions, verify all acceptance criteria, and publish final report | M6 | R4 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Baseline Measurement Tooling & Pre-Fix Profiling | F1: `tools/measure_baseline.py` & pre-fix metrics recording | none | DONE |
| M2 | Admin Castles Pagination & Lazy-Loading | F2, F3, F4: SQL pagination, config separation, UI pagination & local mutations | M1 | DONE |
| M3 | Live Operations Lifecycle, State Clarification & Pagination | F5, F6, F7: State decoupling, 6 allowed states, stalled isolation, live ops pagination | M1 | DONE |
| M4 | Memory & CPU Optimization — Leaks, Threads, WebSockets & Loops | F8, F9, F10, F11: Global dict cleanup, thread join timeouts, socket disconnects, CPU loops | M2, M3 | DONE |
| M5 | 18 Mandatory Scenarios & Soak Testing Verification | F12, F13: Hermetic 18 scenarios suite & multi-cycle soak test with mathematical slope | M4 | DONE |
| M6 | Post-Fix Baseline Measurement, E2E Suite & Final Report | F14: Post-fix profiling, run_all_tests suite, comprehensive report | M5 | DONE |

## Interface Contracts
### 1. Admin Castles Paginated API
- Endpoint: `GET /api/admin/users-castles/summary`
- Parameters: `page: int = 1`, `page_size: int = 25`, `search: str = ""`, `filter_status: str = "all"`
- Response JSON:
  ```json
  {
    "items": [
      {
        "uid": "user_123",
        "email": "user@example.com",
        "username": "user1",
        "castles_count": 3,
        "running_count": 1,
        "pending_count": 2,
        "castles": [
          {
            "castle_id": "c_1",
            "email": "c1@example.com",
            "is_active": 1,
            "state": "running",
            "conn_state": "connected"
          }
        ]
      }
    ],
    "total": 120,
    "page": 1,
    "page_size": 25,
    "total_pages": 5,
    "has_more": true
  }
  ```
- Castle Detail Endpoint: `GET /api/admin/users/{uid}/castles` returns full castle rows including `config` on-demand for single expanded user.

### 2. Live Operations Paginated API
- Endpoint: `GET /api/admin/live-processes`
- Parameters: `page: int = 1`, `page_size: int = 25`, `search: str = ""`, `status: str = "all"`
- Response JSON:
  ```json
  {
    "processes": [
      {
        "castle_id": "c_1",
        "email": "c1@example.com",
        "user_id": "u_1",
        "status": "Running",
        "current_task": "GatherResources",
        "uptime_seconds": 1420,
        "next_cycle_time": null
      }
    ],
    "total_active": 15,
    "summary": {
      "Running": 8,
      "Waiting for Next Cycle": 4,
      "Other Device Login": 1,
      "Reconnecting": 1,
      "Waiting for Re-login": 1,
      "Starting": 0,
      "stalled": 0
    },
    "page": 1,
    "page_size": 25,
    "total_pages": 1,
    "has_more": false
  }
  ```

### 3. Thread & Resource Termination Contract
- Function: `_stop_and_join_bot(castle_id: str, timeout: float = 3.0) -> bool`
- Invariants:
  1. Signal `_stop_events[castle_id].set()`.
  2. Outside `_lock`, invoke `thread.join(timeout=timeout)`.
  3. If thread is still alive after timeout, move to `_stalled_threads[castle_id] = thread` for diagnostic isolation; do not orphan silently.
  4. Safely pop all tracking references (`_threads`, `_stop_events`, `_bot_managers`, `_log_qs`, `_conn_states`, `_castle_emails`, `_castle_users`).

## Code Layout
- Backend Core: `api_server.py`, `bot_manager.py`, `core/database.py`, `core/session_manager.py`, `proxy/proxy_manager.py`
- Frontend Dashboard: `dashboard/src/pages/AdminUsersCastles.tsx`, `dashboard/src/pages/AdminLiveProcesses.tsx`, `dashboard/src/lib/botApi.ts`, `dashboard/src/pages/Admin.tsx`
- Measurement & Inspection Tools: `tools/measure_baseline.py`, `tools/soak_test_lifecycle.py`
- Automated Test Scenarios: `tests/test_mandatory_scenarios.py`, `tests/run_all_tests.py`
- Strictly Prohibited (NEVER touch/read/modify): `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`
