# DISPATCH - Challenger M2 (Instance 2 - Concurrency & OCC Stress Challenger)

## Mission
Empirically stress-test Optimistic Concurrency Control (OCC) and race conditions implemented in Milestone 2 (`core/database.py` and `api_server.py`).

## 🔒 Mandatory Context Files
Read these files before starting:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m2\technical_report_m2.md`
- `e:\osmanli\.agents\teamwork\worker_m2\handoff.md`

## Challenge Tasks & Methodology
Write and run a multi-threaded empirical stress test harness (in an isolated script, e.g. `tools/stress_m2_concurrency.py`) testing SQLite on a temporary test database:
1. Multi-threaded Race Condition Test:
   - Spawn 20 concurrent threads trying to update the same castle record simultaneously starting from `version = 1`, all passing `expected_version = 1`.
   - Verify that EXACTLY 1 thread succeeds, and the other 19 receive `conflict: True` / HTTP 409.
   - Verify that no data corruption, partial writes, or SQLite database locked (`sqlite3.OperationalError: database is locked`) errors crash the system.
2. Sequential Version Increment Test:
   - Perform 50 sequential valid updates (passing incremented `expected_version` each time).
   - Verify that the resulting record has version 51, and all config keys are accurately persisted.
3. Backward Compatibility Test:
   - Test `update_castle_config` called without `expected_version` (legacy callers).
   - Verify it increments version and returns `OCCResult` where `bool(res)` is `True`.

## Verification & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\challenger_m2_2\`
- Run your harness, record exact outputs and metrics.
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicitly state verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.


## 2026-11-02T18:05:52Z
[Message] timestamp=2026-11-02T18:05:52Z sender=44132d7d-07d0-4709-a292-a8e4727a82fd priority=MESSAGE_PRIORITY_HIGH content=You are Challenger M2 (Instance 2 - Concurrency & OCC Stress Challenger).
Your working directory is e:\osmanli\.agents\teamwork\challenger_m2_2\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\challenger_m2_2\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m2\technical_report_m2.md, and e:\osmanli\.agents\teamwork\worker_m2\handoff.md.
Empirically stress-test Optimistic Concurrency Control (OCC) and race conditions in core/database.py:
1. Multi-threaded contention: 20 concurrent threads trying to update the same castle record starting from version 1 with expected_version=1. Verify exactly 1 succeeds, 19 receive conflict: True, and no deadlocks/crashes occur.
2. 50 sequential valid updates verify version reaches 51 and data is intact.
3. Backward compatibility with legacy callers (no expected_version).
Write and run an empirical concurrency stress script in tools/ (e.g. tools/stress_m2_concurrency.py).
Write handoff.md in your working directory with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.
