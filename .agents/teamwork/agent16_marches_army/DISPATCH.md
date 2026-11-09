## 2026-11-09T13:45:23Z
From: fb443f18-e908-4d2d-8e4b-f6fe79f74f58 (Parent Orchestrator)
Content:
You are Agent 16: Marches & Army Live QA Agent.
Your working directory is: e:\osmanli\.agents\teamwork\agent16_marches_army\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Lua Protocol Specification: e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md
4. `core/live_memory.py` and `game_client.py`

Task:
Perform independent QA verification of marches and army state synchronization:
1. `local_queues` March Sync:
   - Test `NOTIFY_LOCAL_QUEUE_SYNC` with `gQueueSyncMsgType`:
     - `ADD` (1): adds new march line to `local_queues`.
     - `UPDATE` (3): updates march line status/position.
     - `REMOVE` (2): removes march line from `local_queues` upon arrival/return.
   - Verify zero duplicates or missed prunings.
2. `armyCtrl` Updates:
   - Feed `v.armyInfo` and verify proper synchronization of `totalArmy`, `woundedArmy`, `trainArmy`, and troop counts.
3. Execute the tests programmatically and record output in `e:\osmanli\.agents\teamwork\agent16_marches_army\handoff.md`.
Send a message when finished referencing your handoff.
