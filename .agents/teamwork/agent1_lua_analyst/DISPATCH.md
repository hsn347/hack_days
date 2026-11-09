## 2026-11-09T13:05:01Z
You are Agent 1: Lua Protocol & Notify Analyst.
Your working directory is: e:\osmanli\.agents\teamwork\agent1_lua_analyst\

You MUST read the following files before beginning:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. PROJECT.md: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
3. Domain Skill: e:\osmanli\.agents\skills\empire-bot\SKILL.md

Your Task:
Examine the reference Lua code in `e:\osmanli\game file\lua_src` (specifically search in `lua_src/src/src/app/module/city/cityCtrl.lua`, `lua_src/src/src/app/module/notify/notifyCtrl.lua`, `lua_src/src/src/app/module/queue/queueCtrl.lua`, and other `*Ctrl.lua` files).
Extract and document comprehensively:
1. All notification IDs (`gNotifyID`), their numeric values or symbolic names, and what event they represent.
2. The exact data structures (`notifyData`, `retdata`) and field names for key notifications:
   - `NOTIFY_CITY`: how `res`, `reslist`, `saferes`, `dayMaxRes`, `updateUnCollectRes`, and `openChargeQueue` are delivered and handled in `cityCtrl.lua`.
   - `NOTIFY_QUEUE` and `NOTIFY_PLAYER_QUEUE_CHANGE` (or `NOTIFY_LOCAL_QUEUE_SYNC`): how queue updates work, queue end callbacks, and how building states (`BUILD_STATE.NORMAL`) and levels (`lv`, `honorLv`) are updated in `cityCtrl.lua`.
   - `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, `buffCtrl`: how armies, heroes, lord stats, and buffs are represented and updated.
   - `backpackCtrl` (`add`/`use`), `meritoriousTaskCtrl`, `timeRewardCtrl` (harbor ships).
3. Identify how Lua merges controller updates into its internal model (e.g. `updateData`, `mergeData`, callbacks).

Output:
Write your complete findings and reference specification to:
`e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md`
and write your `handoff.md` and `progress.md` in your directory.
Send a message when finished referencing the path to your report.
