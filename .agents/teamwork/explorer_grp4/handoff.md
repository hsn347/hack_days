# Handoff Report — Explorer Group 4 (`explorer_grp4`)

## 1. Observation
- **File 1**: `tasks/gather_boost.py` (352 lines).
  - Lines 50-79: Defines `ITEM_SMALL_BOOST = 400101`, `ITEM_LARGE_BOOST = 400102`, `BUFF_SMALL_BOOST = 5008`, `BUFF_LARGE_BOOST = 5009`, `DURATION_SMALL_SEC = 28800`, `DURATION_LARGE_SEC = 86400`.
  - Lines 116-126: Network command `1019/1` (`REQ_INIT_BUFFDATA`) has `timeout=6`. If it fails, line 124 captures it: `except Exception as e: self.log.debug(f"استعلام 1019/1 لتحديث التعزيزات: {e}")`.
  - Lines 128-154: If `buffCtrl` in `init_data` is empty and session cache expired, `check_active_boost()` returns `False, None, 0`.
  - Lines 237-254: Queries bag `1004/1` and selects `ITEM_SMALL_BOOST` first, then `ITEM_LARGE_BOOST`.
  - Lines 264-301: Sends `1004/2` with `{"itemID": target_item_id, "count": 1}`. On success (lines 278-285), updates `buffCtrl` by appending `{"id": buff_id, "beginTime": now}` without `"endTime"`.
  - Lines 297-301: Server errors (including `16001`) fall into `else:` and return `TaskResult.fail` immediately with zero retry logic.
  - `ExcludeManager` is completely absent from `gather_boost.py`.

- **File 2**: `tasks/transport.py` (637 lines).
  - Lines 51-59: `DEFAULT_TARGET_X = 488`, `DEFAULT_TARGET_Y = 499`, `DEFAULT_RESOURCE_IDS = [1002, 1005, 1004]`, `DEFAULT_MAX_CAPACITY = 690000`, `DEFAULT_TAX_RATE = 0.10`, `DEFAULT_MAX_MARCHES = 18`.
  - Lines 62-67: Resource weights: `1002: 1`, `1003: 1`, `1004: 6`, `1005: 24`.
  - Lines 79-102: Module dictionary `_DAILY_TRANSPORT_LIMIT_CACHE: Dict[str, str] = {}` handles daily limit tracking in memory only.
  - Lines 107-138: `MARKET_LEVEL_DATA` maps levels 1..30 to capacity and tax (e.g. lv 1: 20000, 0.45; lv 30: 690000, 0.10).
  - Lines 165-234: `get_full_market_capacity` checks `cityCtrl.blist` for `bid == '112'`, then checks alliance tech `33002` (`TRADING_WEIGHT`) via `init_data` or query `1010/75`.
  - Lines 309-336: `get_target_castle_info` queries map `2011/3` (`mapType: 4`).
  - Lines 439-560: While loop `while sent_count < max_marches:` sends `1007/2` with `matrixType: 4, moveLineType: 5`.
  - Lines 515-527: Handles `16001` with retry up to 2 times, sleeping random 10-16s.
  - Lines 528-532: Handles `8004`, `9007004`: if `sent_count == 0` returns `TaskResult.queue_full()`, else breaks loop.
  - Lines 539-556: Handles `8095` (`Err_MAP_QUEUE_RESOURCE_HELP_OUT_ONE_DAY`): sets `_DAILY_TRANSPORT_LIMIT_CACHE` and returns `TaskResult.ok(daily_limit_reached=True)`.
  - Lines 557-559: All other errors (including `8014`, `8015`, `8019`, `8021`, `8035`, `8086`) fall into `else:` and break the loop.
  - `ExcludeManager` is completely absent from `transport.py`.

- **File 3**: `tasks/march_coordinator.py`.
  - Line 44: Imports `from tasks.transport import TransportTask, is_transport_daily_limit_reached, set_transport_daily_limit_reached`.
  - Lines 501-521: `_priority_transport` is Priority 4, positioned BEFORE Priority 5 (`_priority_ruins`) and Priority 6 (`_priority_gather`).
  - Lines 657-665: In `_priority_gather`, if `cfg.get("use_boost", False)`, instantiates and runs `GatherBoostTask`.

- **File 4**: `game file/lua_src/errDef_dec.lua`.
  - Confirmed 20 error code definitions: `16001` (Err_CMD_OPTING), `8004` (Err_MAP_QUEUE_FULL), `8009` (Err_MAP_QUEUE_ARMY_NOT_ENOUGH), `8014` (Err_MAP_QUEUE_EMBASSY_LEVEL_LESS), `8015` (Err_MAP_QUEUE_ARMP_HELPER_NEED_SAME_ALLIANCE), `8027` (Err_MAP_QUEUE_NPC_LEVEL_OUT), `8032` (Err_MAP_QUEUE_PHY_NOT_ENGHOUT), `8035` (Err_MAP_QUEUE_BATTLE_NUM_OUT), `8037` (Err_MAP_QUEUE_RELICS_ONE_TIME), `8041` (Err_MAP_QUEUE_COLL_IRON_CASTLE_LEVEL_LESS), `8042` (Err_MAP_QUEUE_COLL_MITHRIL_CASTLE_LEVEL_LESS), `8095` (Err_MAP_QUEUE_RESOURCE_HELP_OUT_ONE_DAY), `10002` (Err_OUTNUMBER_MAX_LEVEL), `10003` (Err_UPGRADE_ING), etc.

## 2. Logic Chain
1. *From Observation 1*: In `gather_boost.py`, if network query `1019/1` fails silently and session cache is empty, `check_active_boost` returns `False`. The bot then uses an item via `1004/2`. Because server game logic does not stack gathering boosts, this causes double-activation, wasting expensive 8h/24h items.
2. *From Observation 1*: In `gather_boost.py`, `16001` (server busy) is treated as a generic failure without retry, failing the entire boost task even when items exist.
3. *From Observation 2 & 3*: In `transport.py`, `DEFAULT_MAX_MARCHES = 18`. In `march_coordinator.py`, transport runs at Priority 4 before ruins (Priority 5) and gather (Priority 6). Sending up to 18 transport marches sequentially exhausts all available castle march queues until server error `8004` occurs. This starves out ruins and gathering tasks, completely breaking the multi-task pipeline.
4. *From Observation 2*: In `transport.py`, `_DAILY_TRANSPORT_LIMIT_CACHE` is an in-memory dictionary. A process restart wipes it, causing the bot to immediately retry sending to capped castles and re-trigger error `8095`. Furthermore, other bot accounts on the same machine cannot see this limit, causing multi-account collisions.
5. *From Observation 2*: In `transport.py`, if the recipient castle teleports away and another player occupies `(target_x, target_y)`, `get_target_castle_info` will target the new castle without verifying the recipient's name or UID, leading to accidental resource delivery to enemy players.
6. *From Observation 2 & 4*: Crucial alliance transport errors such as `8019` (`Err_MAP_QUEUE_RESOURCE_HELP_NEED_SAME_ALLIANCE`) and `8014` are unhandled and treated as unknown failures in `else:`, causing endless 3-minute retry loops.

## 3. Caveats
- No live network packets were injected into the production server during this investigation; analysis was conducted via static code auditing, local Lua source definitions, and cross-task comparison.
- The behavior of item stacking in `1004/2` is based on server error responses and standard Empire game mechanics (where speed boost durations do not accumulate).

## 4. Conclusion
Both `tasks/gather_boost.py` and `tasks/transport.py` contain architectural and operational defects:
1. `gather_boost.py` risks silent item waste under transient network lag and lacks retry handling for `16001`.
2. `transport.py` causes march slot starvation across the entire bot coordinator due to greedy march dispatching (up to 18 marches), relies on a volatile in-memory dictionary instead of `ExcludeManager`, lacks recipient identity verification, and fails to handle error `8019`.
Full line-by-line dissection, 20 error codes mapping, red team critiques, and unified architectural remedies are exhaustively documented in `e:\osmanli\.agents\teamwork\explorer_grp4\analysis.md`.

## 5. Verification Method
- **Analysis File Inspection**: Verify `e:\osmanli\.agents\teamwork\explorer_grp4\analysis.md` exists and contains complete tables for all 20 error codes without summarization.
- **Line Reference Validation**:
  - `gather_boost.py`: Inspect lines 116-126 (1019/1 query), lines 278-285 (buffCtrl update), lines 297-301 (failure else branch).
  - `transport.py`: Inspect lines 58 (DEFAULT_MAX_MARCHES = 18), lines 79-102 (_DAILY_TRANSPORT_LIMIT_CACHE), lines 515-559 (error code dispatch).
  - `march_coordinator.py`: Inspect lines 501-521 (Priority 4 transport position).
