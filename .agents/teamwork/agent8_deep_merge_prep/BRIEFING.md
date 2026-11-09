# BRIEFING — 2026-11-09T13:16:00Z

## Mission
Survey and architect the central `smart_deep_merge` algorithm for Live State Memory, handling nested dicts, identifiable list-of-dicts deltas, and concurrency safety.

## 🔒 My Identity
- Archetype: explorer
- Roles: Smart Deep-Merge Engine Architect
- Working directory: e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\
- Original parent: fb443f18-e908-4d2d-8e4b-f6fe79f74f58
- Milestone: Live State Memory - Deep Merge Specification & Survey

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Analyze delta vs snapshot updates in retdata, data, and notifyData
- List-of-dicts identification rules (blist, heroes, buffCtrl, queueCtrl, reslist, etc.)
- Recursive dictionary merging preserving untouched keys
- Concurrency & Mutex considerations for asyncio / multi-task access
- Define exact Python function signature, algorithmic specification, and unit test cases in DEEP_MERGE_SPEC.md

## Current Parent
- Conversation ID: fb443f18-e908-4d2d-8e4b-f6fe79f74f58
- Updated: 2026-11-09T13:16:00Z

## Investigation State
- **Explored paths**:
  - `game_client.py`: naive `_deep_merge` (lines 251-261), shallow `retdata.update` (line 645), cached packets scan in `check_and_merge_controller` (lines 925-951).
  - `bot_manager.py`: account threading vs asyncio loop, `init_data` usage.
  - `tasks/building.py`, `tasks/research.py`, `tasks/hero_consign.py`, `tasks/fortress.py`, `tasks/gather.py`: data structures for `blist`, `reslist`, `saferes`, `queueCtrl`, `buffCtrl`, `backpackCtrl`, `heroVoyageAgCtrl`.
  - `e:\osmanli\game file\lua_src\src\src\app\module\city\cityCtrl.lua`, `notifyCtrl_dec.lua`, `notifyIDDef_dec.lua`, `armyCtrl_dec.lua`.
  - `scan_results.json` from Agent 2.
- **Key findings**:
  - Naive merging overwrites lists, destroying 49 of 50 buildings in `blist` upon action delta or duplicating them upon append.
  - Entity identifiers: `blist` (`index` or `binfo.index`, fallback `bid, iid`), `heroCtrl` (`id`), `buffCtrl` (`id`), `queueCtrl` (`qtype`), `consignTasks` (`index`), `meritoriousTaskCtrl` (`id`), `local_queues` (`id`).
  - Concurrency threat: async task yields during list iteration + multi-threaded Web API inspection from `api_server.py`.
  - Solved via atomic Copy-on-Write list container swap and dual-lock architecture (`threading.RLock` + `asyncio.Lock`).
- **Unexplored areas**: Implementation phase (assigned to M1 agents).

## Key Decisions Made
- Designed `smart_deep_merge` with full normalized string key extraction and composite fallback.
- Specified Copy-on-Write list container replacement (`STORE_SUBSCR` pointer swap) guaranteeing safe iterators for concurrent coroutines.
- Completed full specification and 9 executable unit tests in `DEEP_MERGE_SPEC.md`.

## Artifact Index
- e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\DISPATCH.md — Received mission instructions
- e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\BRIEFING.md — Working memory index
- e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\progress.md — Liveness & step tracking
- e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\DEEP_MERGE_SPEC.md — Target specification report
- e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\handoff.md — Final handoff report
