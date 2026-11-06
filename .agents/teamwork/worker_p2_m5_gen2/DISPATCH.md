## 2026-11-03T19:51:28Z
You are Worker M5 Generation 2 (teamwork_worker).
Your working directory is: `e:\osmanli\.agents\teamwork\worker_p2_m5_gen2\`
Your dispatch document is: `e:\osmanli\.agents\teamwork\worker_p2_m5_gen2\DISPATCH.md`
The authoritative request is: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R4)
The architectural plan is: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 5)
Predecessor Progress: `e:\osmanli\.agents\teamwork\worker_p2_m5\progress.md`
Predecessor Plan Report: `e:\osmanli\.agents\teamwork\worker_p2_m5\report_m5_plan.md`

### MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
Strictly local workspace only: NO server uploads, deploys, or remote DB connections.

### Pre-Implementation Requirement (GEMINI.md Rule 5)
Create a technical report artifact (.md) in your working directory (`e:\osmanli\.agents\teamwork\worker_p2_m5_gen2\report_m5_gen2_plan.md`) BEFORE writing code or running commands.

### Scope of Work (Requirement R4 — Milestone 5)
1. **`tests/test_mandatory_scenarios.py`**:
   Build a comprehensive, hermetic automated test suite covering all 18 mandatory scenarios specified in `ORIGINAL_REQUEST.md`:
   - S1: Startup (Starting -> Running)
   - S2: Auth Credential Failure
   - S3: Other Device Login
   - S4: Connection Loss
   - S5: Reconnecting
   - S6: Waiting for Re-login
   - S7: Next Cycle Wait (with timestamp)
   - S8: Natural Completion (without next cycle)
   - S9: Manual Stop
   - S10: Stop In-Flight
   - S11: Delete Castle While Running
   - S12: Delete User While Running
   - S13: Startup Exception
   - S14: In-Flight Runtime Exception
   - S15: WebSocket Disconnect
   - S16: WebSocket Reconnect
   - S17: Repeated Page Navigation / Rapid API calls
   - S18: Repeated Search & Filter with Stalled Thread Isolation

2. **`tools/soak_test_lifecycle.py`**:
   Build an automated multi-cycle continuous soak testing tool:
   - Executes multiple sequential/parallel start-run-stop lifecycles (`--cycles` default 5, `--bots` default 5).
   - Profiles physical RSS (via 64-bit Windows PSAPI `GetProcessMemoryInfo`), Private Bytes, Handles, Tracemalloc, and Active Threads after each cycle.
   - Computes mathematical linear regression slope of memory growth (assert $m \le 0.05$ MB/cycle).
   - Verifies 0 residual threads delta.
   - Emits structured JSON to `tools/soak_test_results.json` and report to `tools/SOAK_TEST_REPORT.md`.

3. **Execution & Verification**:
   - Run `python tests/test_mandatory_scenarios.py` (all 18 PASS).
   - Run `python tools/soak_test_lifecycle.py --cycles 5 --bots 5`.
   - Run `python tests/test_challenger_m4_stress.py` (4/4 PASS).
   - Run `python tests/test_memory_cpu_m4.py` (5/5 PASS).
   - Run `python tests/test_live_operations_m3.py` (4/4 PASS).
   - Run `python tests/run_all_tests.py` (30/30 PASS).

Write your handoff report to `e:\osmanli\.agents\teamwork\worker_p2_m5_gen2\handoff.md` and notify with `send_message`.
