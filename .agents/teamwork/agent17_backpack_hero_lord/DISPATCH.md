## 2026-11-09T13:45:32Z
You are Agent 17: Backpack, Hero & Lord QA Agent.
Your working directory is: e:\osmanli\.agents\teamwork\agent17_backpack_hero_lord\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Lua Protocol Specification: e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md
4. `core/live_memory.py` and `game_client.py`

Task:
Perform independent QA verification of inventory math, hero lists, and lord info updates:
1. `backpackCtrl` Inventory Math:
   - Feed `add` sync: assert item count increments accurately.
   - Feed `use` sync: assert item count decrements accurately.
   - Test item deletion when count reaches 0.
2. `heroCtrl` Entity Preservation:
   - Initial list of 20 heroes.
   - Incoming delta updating level/stars of hero `5501001`.
   - Incoming delta adding a new hero `5502015`.
   - Assert all 21 heroes exist; updated hero reflects new data; zero duplicates.
3. `lordInfoCtrl` State Updates:
   - Test updating `base` attributes, `fcInfo`, `stamina`, and official rank.
4. Execute the tests programmatically and record output in `e:\osmanli\.agents\teamwork\agent17_backpack_hero_lord\handoff.md`.
Send a message when finished referencing your handoff.
