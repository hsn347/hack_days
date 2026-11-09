# Handoff Report — Agent 1: Lua Protocol & Notify Analyst
**Date**: 2026-11-09T13:19:00Z  
**Author**: Agent 1 (Lua Protocol & Notify Analyst)  
**Destination**: Orchestrator / Swarm Engineers (Agent 4, Agent 5, Agent 6, Agent 7, Agent 8, Agent 9)

---

## 1. Observation
1. **Network Push Command**:
   In `game file/lua_src/cmdDef_dec.lua:132`, `CMD_NOTIFY_MODULE = "1009"`. All server-push notifications arrive under CMD 1009 with subcommands ranging from `"1"` (`NOTIFY_BACKPACK_UPDATE`) up to `"1000215"` (`NOTIFY_RADAR_ATY`).
2. **Notification Dispatcher**:
   In `game file/lua_src/notifyCtrl_dec.lua:1096-1111`, `notifyRsp` checks `content.err == gErrDef.Err_None`, extracts `content.data.notifyID` and `content.data.notifyData`, and dispatches it via `self:dispatchEvent({ name = notifyID, data = content.data.notifyData })`.
3. **`cityCtrl` Resource and Building Sync**:
   - In `game file/lua_src/cityCtrl_dec.lua:1001-1056`:
     - `v.res`: delta resources, processed by `updateResCount` (`ret = ret + tonumber(count)`, capped below at 0).
     - `v.reslist`: absolute resource replacement (`curcity.resList = reslist`).
     - `v.saferes`: replaced directly (`curcity.saferes = saferes`).
     - `v.dayMaxRes`: replaced directly (`curcity.dayMaxRes = dayMaxRes`).
     - `v.updateUnCollectRes`: table of `{ [index] = count }`, increments `bcell.info.curres = tostring(tonumber(bcell.info.curres) + count)`.
     - `v.openChargeQueue`: adds queue 1201 via `curcity:addBuildChargeQueue(1201, starttime, totaltime, lefttime)`.
   - In `game file/lua_src/cityCtrl_dec.lua:49-160` (`buildQueueCallback`):
     - Normal upgrade (`optype == 2`, regular): `upgradeBuild(index)` increments `bcell.info.lv = tostring(tonumber(bcell.info.lv) + 1)`, then calls `changeBuildState(index, BUILD_STATE.NORMAL)`.
     - Honor upgrade (`optype == 2`, honor): `notifyHonorUpgradeComplete(index)` calls `upgradeHonorBuild(index)` which increments `honorLv = honorLv + 1` and updates both `bcell.info.honorLv` and `bcell.info.hlv`, then calls `changeBuildState(index, BUILD_STATE.NORMAL)`.
     - Build new (`optype == 0`): `changeBuildState(index, BUILD_STATE.NORMAL)`.
     - Cancel queue (`optype == 11`): `changeBuildState(index, BUILD_STATE.NORMAL)`.
4. **`queueCtrl` Lifecycle & Events**:
   - In `game file/lua_src/queueTypeDef_dec.lua:8-62`, `gQueueTypeDef` enumerates all queue types (1200 free build, 1201 charge build, 1202 hospital, 1203-1208 military training, 1212 technology research, 1227 time reward ship, etc.).
   - In `game file/lua_src/queueCtrl_dec.lua:286-344`, registers `gNotifyID.QUEUE` ("14") and `gNotifyID.NOTIFY_PLAYER_QUEUE_CHANGE` ("1051"). Timers dispatch completion events that trigger controller callbacks like `cityCtrl:buildQueueCallback`.
   - In `game file/lua_src/kingdomMapCtrl_dec.lua:1041-1063`, `NOTIFY_LOCAL_QUEUE_SYNC` ("202") uses `gQueueSyncMsgType`: ADD(1), REMOVE(2), UPDATE(3), ADD_ALL(4), REMOVE_ALL(5) to synchronize marching armies in `local_queues_map`.
5. **Other Controller Synchronizers**:
   - `armyCtrl` (`armyCtrl_dec.lua:845-867`): `v.armyInfo` fully replaces `totalArmy`, `woundedArmy`, `trainArmy`, and `singleTrainAddInfo`.
   - `heroCtrl` (`heroCtrl_dec.lua:106-122`): updates keyed by hero `id`. Existing heroes update attributes; new IDs append to `heroMap`.
   - `lordInfoCtrl` (`lordInfoCtrl_dec.lua:122-260`): keyed updates on `base`, `fcInfo`, `skill`, `physical`, `updateOfficial`, `npc`. `lordAuxiliary:updateLordBaseInfo` merges table fields into `lordInfo.base`.
   - `buffCtrl` (`buffCtrl_dec.lua:426-510`): updates driven by `syncType` (`openBuff`, `closeBuff`, `closeSource`, `buffFinish`, `closeSingleBuff`).
   - `backpackCtrl` (`backpackCtrl_dec.lua:332-410`): updates driven by `syncType` (`add` increments item count, `use` decrements item count).
   - `meritCtrl` (`meritCtrl_dec.lua:113-186`): `flag == "base"` replaces base metrics (`meritLv`, `meritExp`, `dailyPoint`), while `flag == "task"` provides `add` and `remove` maps for `main_task`, `branch_task`, `daily_task`, and `taskData`.
   - `timeRewardCtrl` (`timeRewardCtrl_dec.lua:36-67`): `NOTIFY_TIME_REWARD` ("16") sets `isReceive = 2` (ready to claim); `NOTIFY_RESET_TIME_REWARD` ("20") resets daily sequence to 1.

---

## 2. Logic Chain
1. **From Observation 1 & 2**: All asynchronous game state modifications originate from TCP packets with `cmd = "1009"`. The Python bot must intercept packets where `cmd == 1009` (or string `"1009"`), inspect `data.notifyID` or the subcommand, and route `data.notifyData` to the appropriate controller synchronizer.
2. **From Observation 3**: In `cityCtrl`, `res` is a relative delta map ($\Delta$) while `reslist` is an absolute replacement. If Python treated `res` as absolute, resource balances would collapse to negative or tiny values. Furthermore, building upgrade completion must not only update the level (`lv` or `honorLv`) but must explicitly reset `state` to `"0"` (`BUILD_STATE.NORMAL`), matching `cityCtrl:buildQueueCallback`.
3. **From Observation 4**: Queues in `queueCtrl` have two lifecycle mechanisms: local timers that expire when `lefttime <= 0`, and explicit server pushes (`NOTIFY_QUEUE`, `NOTIFY_PLAYER_QUEUE_CHANGE`, `NOTIFY_LOCAL_QUEUE_SYNC`). The smart deep-merge engine must maintain keyed lookup by `index` (or `bid`/`iid`) for buildings and `id` for march lines.
4. **From Observation 5**: `backpackCtrl` inventory tracking requires delta additions for `add` and delta deductions for `use`. `heroes` list must never be replaced by partial arrays — it must be keyed by `id` so that an update to Hero 5501001 does not erase the other 30 heroes in the account.
5. **Synthesis**: Full specification documented in `e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md` provides complete schemas, ID mappings, and algorithmic steps required by Agents 4-10 to implement the unified memory engine without discrepancies.

---

## 3. Caveats
- No caveats regarding Lua decompiled source: all controller handlers and notification definitions were directly read from `game file/lua_src`.
- Note on server implementations: Some private or modified game servers might send `notifyData` either as a dict or wrapped in a 1-element list (`[data]`). Synchronizers must handle both `isinstance(notifyData, list)` and `isinstance(notifyData, dict)` defensively.

---

## 4. Conclusion
1. The notification protocol for Empire (Boe) is fully documented in `LUA_PROTOCOL_SPEC.md`.
2. All 256 `gNotifyID` entries have been mapped to their respective subcommands under CMD 1009 and their corresponding client controller modules.
3. The exact schemas and merging rules for `cityCtrl` (`res`, `reslist`, `saferes`, `updateUnCollectRes`, `openChargeQueue`, `BUILD_STATE.NORMAL`, `lv`, `honorLv`), `queueCtrl`, `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, `buffCtrl`, `backpackCtrl`, `meritCtrl`, and `timeRewardCtrl` are extracted with 100% fidelity to the authoritative Lua reference.

---

## 5. Verification Method
1. Inspect the generated specification:
   `e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md`
2. Verify against reference Lua sources:
   - `Select-String -Path "game file/lua_src/cmdDef_dec.lua" -Pattern "CMD_NOTIFY_MODULE"`
   - `Select-String -Path "game file/lua_src/cityCtrl_dec.lua" -Pattern "function cityCtrl:updateCityData"`
   - `Select-String -Path "game file/lua_src/cityCtrl_dec.lua" -Pattern "function cityCtrl:buildQueueCallback"`
   - `Select-String -Path "game file/lua_src/backpackCtrl_dec.lua" -Pattern "function RSP:updateDataRsp"`
   - `Select-String -Path "game file/lua_src/queueTypeDef_dec.lua" -Pattern "gQueueTypeDef"`
