# DISPATCH — Reviewer 2 (M4 Concurrency & Edge Cases)
**Role**: Reviewer 2 (Adversarial / Concurrency) for Milestone 4 (Requirement R3)
**Working directory**: `e:\osmanli\.agents\teamwork\reviewer_p2_m4_2\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
**Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md` (Milestone 4)
**Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_p2_m4\handoff.md`
**Worker Pre-Implementation Report**: `e:\osmanli\.agents\teamwork\worker_p2_m4\report_m4_plan.md`

## Review Objective
Adversarially evaluate concurrency safety, edge cases, and leak vectors:
1. Examine `_stop_and_join_bot`: Are joins truly outside `_lock`? What happens under simultaneous stop / delete calls?
2. Examine `ws_user_status` snapshot cache: Can cache staleness hide newly added castles? Is concurrency safe across multiple simultaneous WebSocket connections?
3. Examine `prune_log_file_24h`: Does the seek-based tail handle empty files, multi-byte encodings, or logs shorter than the buffer without truncation or corruption?
4. Run and verify test suites: `python tests/test_memory_cpu_m4.py`, `python tests/run_all_tests.py`.
5. Confirm strict prohibition: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` must NOT be touched.

Write a technical report (.md) before running tests per GEMINI.md Rule 5. Deliver your final verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\reviewer_p2_m4_2\handoff.md` and notify with `send_message`.


## 2026-11-03T00:05:39Z
[Message] timestamp=2026-11-03T00:05:39Z sender=849edb08-8a01-463a-a4d9-889f072bccf9 priority=MESSAGE_PRIORITY_HIGH
You are Reviewer 2 (teamwork_reviewer).
Your working directory is: `e:\osmanli\.agents\teamwork\reviewer_p2_m4_2\`
Your dispatch document is: `e:\osmanli\.agents\teamwork\reviewer_p2_m4_2\DISPATCH.md`
The authoritative request is: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
Worker M4 Handoff: `e:\osmanli\.agents\teamwork\worker_p2_m4\handoff.md`

### MANDATORY CONSTRAINTS
- Strict prohibition: NEVER open, read, modify, format, rename, delete, move, or touch: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- Strictly local workspace only: NO server uploads, deploys, or remote DB connections.
- GEMINI.md Rule 5: Create a technical report artifact (.md) in your working directory before running tests or modifying code.

### Instructions
1. Adversarially evaluate concurrency safety, edge cases, and leak vectors:
   - Examine `_stop_and_join_bot`: Are joins truly outside `_lock`? What happens under simultaneous stop / delete calls?
   - Examine `ws_user_status` snapshot cache: Can cache staleness hide newly added castles? Is concurrency safe across multiple simultaneous WebSocket connections?
   - Examine `prune_log_file_24h`: Does the seek-based tail handle empty files, multi-byte encodings, or logs shorter than the buffer without truncation or corruption?
2. Run test suites:
   - `python tests/test_memory_cpu_m4.py`
   - `python tests/run_all_tests.py`
3. Deliver your final verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\reviewer_p2_m4_2\handoff.md` and notify with `send_message`.
