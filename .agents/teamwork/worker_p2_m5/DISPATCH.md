# DISPATCH — Worker M5 (18 Mandatory Test Scenarios & Soak Testing Verification)
**Role**: Implementation Worker for Milestone 5 (F12, F13 / Requirement R4)
**Working directory**: `e:\osmanli\.agents\teamwork\worker_p2_m5\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R4)
**Architectural Plan**: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 5)

## Objectives
Implement the complete test harness for Requirement R4:

### 1. `tests/test_mandatory_scenarios.py`
Build a comprehensive, hermetic automated test suite covering all 18 mandatory scenarios specified in `ORIGINAL_REQUEST.md`:
- **Scenario 1**: Successful bot startup and task initialization (`Starting` -> `Running`).
- **Scenario 2**: Auth credential failure handling (no leaked threads, clean database status).
- **Scenario 3**: "Other Device Login" detection and transient wait state.
- **Scenario 4**: Connection loss detection and transition to reconnect state.
- **Scenario 5**: Reconnecting attempts with bounded retry logic.
- **Scenario 6**: Waiting for re-login due to invalid session.
- **Scenario 7**: Cycle completion with scheduled next cycle (`Waiting for Next Cycle` with timestamp).
- **Scenario 8**: Natural completion without next cycle (clean transition to stopped/idle, excluded from live operations).
- **Scenario 9**: Manual stop via `stop_bot` (deterministic join within timeout, 0 residual threads).
- **Scenario 10**: Stop in-flight during active task execution (immediate event cancellation, clean exit).
- **Scenario 11**: Castle deletion while running (atomic stop, join, deletion of castle row, proxy bindings purged).
- **Scenario 12**: User deletion while running (atomic stop, join of all user's castles, user and castle rows deleted).
- **Scenario 13**: Startup exception handling (clean rollback, error logging, no zombie threads).
- **Scenario 14**: In-flight runtime exception handling (clean catch, error recording, safe thread termination).
- **Scenario 15**: WebSocket client disconnect detection (coroutine termination within < 100ms, 0 leaked tasks).
- **Scenario 16**: WebSocket reconnect after drop (fresh connection, correct initial snapshot push).
- **Scenario 17**: Repeated page navigation / Rapid API calls (castles paginated summary, no unbounded memory growth).
- **Scenario 18**: Repeated search & filter with stalled thread diagnostic isolation (stalled thread quarantined in `_stalled_threads`, excluded from live ops).

### 2. `tools/soak_test_lifecycle.py`
Build an automated multi-cycle continuous soak testing tool:
- Executes multiple sequential/parallel start-run-stop lifecycles (configurable `--cycles` default 5, `--bots` default 10).
- Profiles physical RSS (via 64-bit Windows PSAPI `GetProcessMemoryInfo`), Private Bytes, Handles, Tracemalloc heap, and Active Thread Count at the end of each cycle after gc.collect().
- Performs linear regression on RSS across cycles to compute the memory leak slope ($m = \Delta \text{RSS} / \Delta \text{cycle}$).
- Asserts that the memory growth slope is $\le 0.05$ MB/cycle (or zero asymptotic growth).
- Asserts that residual threads delta is +0 and handle growth is bounded.
- Emits structured JSON metrics to `tools/soak_test_results.json` and a readable summary report `tools/SOAK_TEST_REPORT.md`.

### 3. Execution & Verification
- Run `python tests/test_mandatory_scenarios.py` (all 18 scenarios PASS).
- Run `python tools/soak_test_lifecycle.py --cycles 5 --bots 5`.
- Run `python tests/test_memory_cpu_m4.py` (5/5 PASS).
- Run `python tests/test_live_operations_m3.py` (4/4 PASS).
- Run `python tests/run_all_tests.py` (30/30 PASS).

## Write Ownership
You exclusively own:
- `tests/test_mandatory_scenarios.py`
- `tools/soak_test_lifecycle.py`
- `tools/soak_test_results.json`
- `tools/SOAK_TEST_REPORT.md`
- Your working directory: `e:\osmanli\.agents\teamwork\worker_p2_m5\`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work.

## STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
Strictly local workspace only: NO server uploads, deploys, or remote DB connections.

## Pre-Implementation Requirement
Create a technical report artifact (.md) in your working directory per GEMINI.md Rule 5 before writing code or running commands.
Deliver handoff in `e:\osmanli\.agents\teamwork\worker_p2_m5\handoff.md` and notify with `send_message`.
