# DISPATCH — Challenger M4 Iteration 2 (Empirical Re-Challenge on `_user_stopped` Leak)
**Role**: Challenger M4 Iteration 2
**Working directory**: `e:\osmanli\.agents\teamwork\challenger_p2_m4_iter2\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R3)
**Previous Challenge Report**: `e:\osmanli\.agents\teamwork\challenger_p2_m4_1\handoff.md`
**Worker Iter 2 Handoff**: `e:\osmanli\.agents\teamwork\worker_p2_m4_iter2\handoff.md`

## Challenge Objective
Empirically verify that the `_user_stopped` leak has been 100% resolved:
1. Run `python tests/test_challenger_m4_stress.py` to verify:
   - All 20 concurrently stopped bots have their IDs discarded from `_user_stopped`.
   - `_user_stopped retains castle_id after _stop_and_join_bot` evaluates to `False`.
   - All 10 tracking structures are 100% clean.
2. Run `python tests/test_memory_cpu_m4.py` (5/5 PASS).
3. Run `python tests/run_all_tests.py` (30/30 PASS).
4. Verify strict prohibition: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` are untouched.

Create a technical report artifact (.md) in your working directory per GEMINI.md Rule 5 before running commands. Deliver your verdict (APPROVE or REQUEST_CHANGES) in `e:\osmanli\.agents\teamwork\challenger_p2_m4_iter2\handoff.md` and notify with `send_message`.
