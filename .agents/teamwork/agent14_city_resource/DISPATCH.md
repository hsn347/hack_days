## 2026-11-09T13:45:06Z
You are Agent 14: City & Resource Delta QA Agent.
Your working directory is: e:\osmanli\.agents\teamwork\agent14_city_resource\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Lua Protocol Specification: e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md
4. `core/live_memory.py` and `game_client.py`

Task:
Perform independent, rigorous QA verification of `NOTIFY_CITY` mutations:
1. Test resource delta summation:
   - Feed `NOTIFY_CITY` packets with positive and negative resource counts (`v.res`).
   - Verify proper addition and clamp-to-zero safety (no negative resource numbers).
2. Test absolute replacements:
   - Feed `v.reslist` and verify full replacement of current resource catalog.
   - Feed `v.saferes` and `v.dayMaxRes` and verify direct updates.
3. Test uncollected resources:
   - Feed `v.updateUnCollectRes` mapping building index to resource increment.
   - Verify that target building's `binfo.curres` (or `curres`) increments exactly by the delivered count.
4. Test second charge queue:
   - Feed `v.openChargeQueue` and verify queue type `1201` is added to queues with appropriate start/total times.
5. Execute the tests programmatically and record output in `e:\osmanli\.agents\teamwork\agent14_city_resource\handoff.md`.
Send a message when finished referencing your handoff.
