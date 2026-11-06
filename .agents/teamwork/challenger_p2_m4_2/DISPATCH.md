# DISPATCH — Challenger 2 (M4 Sockets, SQLite Offload & CPU Sleep Verification)
**Role**: Challenger 2 (Empirical Verifier) for Milestone 4 (Requirement R3)
**Working directory**: `e:\osmanli\.agents\teamwork\challenger_p2_m4_2\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
**Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md` (Milestone 4)
**Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_p2_m4\handoff.md`

## Challenge Objective
Empirically verify socket disconnect behavior, SQLite query reduction, and async wait sleep responsiveness:
1. Write a standalone test script verifying:
   - WebSocket disconnect detection: ensure closing the client socket immediately terminates the server coroutine and frees references.
   - `ws_user_status` SQLite calls: verify that during 5 seconds of idle client connection, zero SQLite queries are dispatched via `asyncio.to_thread`.
   - `bot_manager.py` sleep responsiveness: verify that stopping an idle bot in its wait cycle takes < 150ms instead of waiting for a 1-second sleep tick.
   - Streaming log pruning: verify that pruning a 10MB simulated log file does NOT spike process RSS by 10MB.
2. Run platform suite: `python tests/run_all_tests.py`.
3. Confirm strict prohibition: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` are untouched.

Write a technical report (.md) before running tests per GEMINI.md Rule 5. Deliver your verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\challenger_p2_m4_2\handoff.md` and notify with `send_message`.


## 2026-11-03T00:05:52Z
[Message] timestamp=2026-11-03T00:05:52Z sender=849edb08-8a01-463a-a4d9-889f072bccf9 priority=MESSAGE_PRIORITY_HIGH content=You are Challenger 2 (teamwork_challenger).
Your working directory is: `e:\osmanli\.agents\teamwork\challenger_p2_m4_2\`
Your dispatch document is: `e:\osmanli\.agents\teamwork\challenger_p2_m4_2\DISPATCH.md`
The authoritative request is: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
Worker M4 Handoff: `e:\osmanli\.agents\teamwork\worker_p2_m4\handoff.md`

### MANDATORY CONSTRAINTS
- Strict prohibition: NEVER open, read, modify, format, rename, delete, move, or touch: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- Strictly local workspace only: NO server uploads, deploys, or remote DB connections.
- GEMINI.md Rule 5: Create a technical report artifact (.md) in your working directory before running tests or modifying code.

### Instructions
Empirically verify socket disconnect behavior, SQLite query reduction, and async wait sleep responsiveness:
1. Write a standalone test script verifying:
   - WebSocket disconnect detection: closing the client socket terminates the server coroutine and frees references.
   - `ws_user_status` SQLite calls: verify that during 5 seconds of idle client connection, zero SQLite queries are dispatched via `asyncio.to_thread`.
   - `bot_manager.py` sleep responsiveness: stopping an idle bot in its wait cycle takes < 150ms instead of waiting for a 1-second sleep tick.
   - Streaming log pruning: pruning a 10MB simulated log file does NOT spike process RSS by 10MB.
2. Run platform suite: `python tests/run_all_tests.py`.
3. Deliver your verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\challenger_p2_m4_2\handoff.md` and notify with `send_message`.
