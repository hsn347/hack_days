## 2026-11-03T00:13:03Z
You are Worker M4 Iteration 2 (teamwork_worker).
Your working directory is: `e:\osmanli\.agents\teamwork\worker_p2_m4_iter2\`
Your dispatch document is: `e:\osmanli\.agents\teamwork\worker_p2_m4_iter2\DISPATCH.md`
The authoritative request is: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
Challenge Evidence & Exact Remediation: `e:\osmanli\.agents\teamwork\challenger_p2_m4_1\handoff.md`

### MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

### STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
Strictly local workspace only: NO server uploads, deploys, or remote DB connections.

### Pre-Implementation Requirement (GEMINI.md Rule 5)
Create a technical report artifact (.md) in your working directory (`e:\osmanli\.agents\teamwork\worker_p2_m4_iter2\report_iter2_plan.md`) BEFORE modifying any code or running commands.

### Scope of Work
Apply the exact 4-line surgical remediation in `api_server.py` identified by Challenger 1 to achieve 100% symmetric cleanup across all 10 tracking structures, eliminating the residual leak in `_user_stopped`:
1. `api_server.py:407` (in `_stop_and_join_bot`): Under `if joined:`, add `_user_stopped.discard(castle_id)`
2. `api_server.py:998-1000` (in `finally:` of `_bot_thread`): Always discard `castle_id` from `_user_stopped`
3. `api_server.py:1516` (in `delete_castle_endpoint`): Add `_user_stopped.discard(castle_id)`
4. `api_server.py:2421` (in `delete_user_endpoint`): Add `_user_stopped.discard(cid)`

### Test Verification
Run:
- `python tests/test_challenger_m4_stress.py` (Must pass 100% with 0 leaked IDs in `_user_stopped`)
- `python tests/test_memory_cpu_m4.py` (5/5 PASS)
- `python tests/test_live_operations_m3.py` (4/4 PASS)
- `python tests/run_all_tests.py` (30/30 PASS)

Write your handoff report to `e:\osmanli\.agents\teamwork\worker_p2_m4_iter2\handoff.md` and notify with `send_message`.
