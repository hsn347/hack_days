# DISPATCH — Reviewer 1 (M5 18 Mandatory Scenarios Verification)
**Role**: Reviewer 1 for Milestone 5 (Requirement R4)
**Working directory**: `e:\osmanli\.agents\teamwork\reviewer_p2_m5_1\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R4)
**Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md` (Milestone 5)
**Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_p2_m5_gen2\handoff.md`

## Review Objective
Review the Milestone 5 implementation of `tests/test_mandatory_scenarios.py`:
1. Verify that all 18 mandatory scenarios (S01 to S18) are genuinely and hermetically implemented:
   - S01: Startup (Starting -> Running)
   - S02: Auth Credential Failure Handling
   - S03: Other Device Login Detection & Transient State
   - S04: Connection Loss Detection & Reconnecting State
   - S05: Reconnecting Attempts with Bounded Retry Logic
   - S06: Waiting for Re-login Handling
   - S07: Next Cycle Wait with Timestamp
   - S08: Natural Completion (without Next Cycle)
   - S09: Manual Stop via _stop_and_join_bot (Deterministic Join, 0 Residual Threads)
   - S10: Stop In-Flight During Active Task Execution (< 100ms Event Cancellation)
   - S11: Delete Castle While Running (Atomic Stop, Purge DB & Proxy Bindings)
   - S12: Delete User While Running (Atomic Stop of All Castles, Purge User & DB)
   - S13: Startup Exception Handling (Clean Rollback, No Zombie Threads)
   - S14: In-Flight Runtime Exception Handling (Catch, Record, Safe Termination)
   - S15: WebSocket Disconnect Detection (Coroutine Termination, 0 Leaked Tasks)
   - S16: WebSocket Reconnect (Fresh Initial Snapshot Push)
   - S17: Repeated Page Navigation / Rapid API Calls (Paginated Summary, No Memory Growth)
   - S18: Repeated Search & Filter with Stalled Thread Isolation (Quarantined in _stalled_threads)
2. Run `python tests/test_mandatory_scenarios.py` (Must pass 18/18).
3. Run `python tests/run_all_tests.py` (Must pass 30/30).
4. Confirm strict prohibition: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` are untouched.

Create a technical report artifact (.md) in your working directory per GEMINI.md Rule 5 before running commands. Deliver your verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\reviewer_p2_m5_1\handoff.md` and notify with `send_message`.
## 2026-11-03T20:16:55Z
From: 849edb08-8a01-463a-a4d9-889f072bccf9
Content:
You are Reviewer 1 (teamwork_reviewer).
Your working directory is: `e:\osmanli\.agents\teamwork\reviewer_p2_m5_1\`
Your dispatch document is: `e:\osmanli\.agents\teamwork\reviewer_p2_m5_1\DISPATCH.md`
The authoritative request is: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R4)
Worker Handoff: `e:\osmanli\.agents\teamwork\worker_p2_m5_gen2\handoff.md`

### MANDATORY CONSTRAINTS
- Strict prohibition: NEVER open, read, modify, format, rename, delete, move, or touch: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- Strictly local workspace only: NO server uploads, deploys, or remote DB connections.
- GEMINI.md Rule 5: Create a technical report artifact (.md) in your working directory before running tests or modifying code.

### Instructions
1. Review `tests/test_mandatory_scenarios.py`: Confirm all 18 mandatory scenarios (S01 to S18) are genuinely and hermetically implemented.
2. Run `python tests/test_mandatory_scenarios.py` (Must pass 18/18).
3. Run `python tests/run_all_tests.py` (Must pass 30/30).
4. Deliver your final verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\reviewer_p2_m5_1\handoff.md` and notify with `send_message`.
