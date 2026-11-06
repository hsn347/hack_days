## 2026-11-03T00:05:46Z
You are Challenger 1 (teamwork_challenger).
Your working directory is: `e:\osmanli\.agents\teamwork\challenger_p2_m4_1\`
Your dispatch document is: `e:\osmanli\.agents\teamwork\challenger_p2_m4_1\DISPATCH.md`
The authoritative request is: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
Worker M4 Handoff: `e:\osmanli\.agents\teamwork\worker_p2_m4\handoff.md`

### MANDATORY CONSTRAINTS
- Strict prohibition: NEVER open, read, modify, format, rename, delete, move, or touch: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- Strictly local workspace only: NO server uploads, deploys, or remote DB connections.
- GEMINI.md Rule 5: Create a technical report artifact (.md) in your working directory before running tests or modifying code.

### Instructions
Empirically stress-test thread lifecycles and dictionary leak prevention:
1. Write a standalone test script to spawn and stop 20 simulated bots concurrently with `_stop_and_join_bot`.
2. Verify that after stopping:
   - All 10 global dictionaries (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`) are completely emptied of these castles.
   - Any uncooperative thread (simulated stall) gets isolated into `_stalled_threads` without hanging the caller.
3. Verify proxy binding cleanup in `proxy/proxy_manager.py` when deleting castles.
4. Run platform suite: `python tests/run_all_tests.py`.
5. Deliver your verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\challenger_p2_m4_1\handoff.md` and notify with `send_message`.
