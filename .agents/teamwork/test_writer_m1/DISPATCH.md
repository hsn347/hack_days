## 2026-11-09T13:20:36Z
You are Test Writer: Live Memory & Readiness Gate QA (Track 2 Specialist).
Your working directory is: e:\osmanli\.agents\teamwork\test_writer_m1\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Whitelist Specification: e:\osmanli\.agents\teamwork\agent2_task_scanner\CONTROLLER_WHITELIST_SPEC.md
4. Lua Protocol Specification: e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md
5. Deep Merge Specification: e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\DEEP_MERGE_SPEC.md
6. Domain Skill: e:\osmanli\.agents\skills\empire-bot\SKILL.md

Task:
Write a comprehensive, standalone test suite in `e:\osmanli\tests\test_live_memory.py` using standard `unittest` or `pytest`.
The test suite must rigorously verify:
1. Whitelist Ingress Filtering:
   - Feed packet containing whitelisted controllers (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`) and non-whitelisted noise (`chatCtrl`, `RedPointCtrl`, `videoAdCtrl`, `randomGarbage`).
   - Assert only whitelisted controllers exist in `init_data`; non-whitelisted controllers are dropped 100%.
2. Keyed Deep Merge Correctness:
   - Initial state with 50 buildings in `cityCtrl.blist`.
   - Incoming delta with 1 updated building (e.g. `index: 10`, `lv: 25`, `state: 1`).
   - Assert all 50 buildings remain in `blist`; only building 10 was updated; zero duplicate entries.
   - Initial heroes list with 10 heroes in `heroCtrl.heroes`.
   - Incoming delta updating 1 hero's exp/stars.
   - Assert all 10 heroes exist; updated hero reflects new data; zero duplicates.
   - Initial buff list in `buffCtrl`. Merge deltas and verify.
   - Initial queue dict in `queueCtrl`. Merge and verify.
3. Concurrency & Copy-on-Write Safety:
   - Simulate an active thread or async task iterating over `cityCtrl.blist`.
   - Concurrently perform 100 packet merges on `blist`.
   - Assert no `RuntimeError: dictionary/list changed size during iteration` occurs.
4. Notification Handling:
   - `NOTIFY_CITY`: delta resources addition, safe resources update, uncollected resources addition (`updateUnCollectRes`).
   - `NOTIFY_QUEUE`: building upgrade completion -> assert `cityCtrl.blist` building resets state to `BUILD_STATE.NORMAL` ("0") and regular `lv` increments by 1.
   - Honor upgrade completion -> assert `honorLv` and `hlv` increment by 1 and state resets to `"0"`.
5. Readiness Gate & Fallback Queries:
   - Test `wait_for_memory_ready`:
     - Initial state missing `cityCtrl` -> assert gate reports not ready.
     - With `auto_fetch_missing=True`, simulate fallback response arrival -> assert gate passes.
     - Timeout case when server never responds -> assert gate returns False or raises timeout.
6. Execution:
   - Run the tests via PowerShell command and assert 100% pass rate.

Deliverables:
- Create `e:\osmanli\tests\test_live_memory.py`.
- Write your report in `e:\osmanli\.agents\teamwork\test_writer_m1\handoff.md`.
- Send a message when finished referencing your test results and handoff.
