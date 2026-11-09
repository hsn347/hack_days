## 2026-11-09T13:20:00Z
You are Worker: Core Live Memory Engineer (Agent 8 Implementation).
Your working directory is: e:\osmanli\.agents\teamwork\worker_core_memory\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Deep Merge Specification: e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\DEEP_MERGE_SPEC.md
4. Lua Protocol Specification: e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md
5. Whitelist Specification: e:\osmanli\.agents\teamwork\agent2_task_scanner\CONTROLLER_WHITELIST_SPEC.md
6. Domain Skill: e:\osmanli\.agents\skills\empire-bot\SKILL.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Ownership:
You own `core/live_memory.py` exclusively. Use direct tool `write_file` or `edit_file` to create it (GEMINI.md Rule 6: NEVER use python scripts to edit code).

Task:
Implement the complete, production-grade `core/live_memory.py` containing:
1. `ALLOWED_CONTROLLERS`: The exact frozenset of 42 controllers defined in `CONTROLLER_WHITELIST_SPEC.md`.
2. `CRITICAL_STARTUP_CONTROLLERS`: The exact frozenset of 6 controllers (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`).
3. `FALLBACK_QUERIES`: Dictionary mapping missing critical controllers to their `(cmd, subcmd, payload)` per `CONTROLLER_WHITELIST_SPEC.md`:
   - `cityCtrl`: `(1001, 1, {})`
   - `lordInfoCtrl`: `(1002, 7, {"uid": uid})`
   - `queueCtrl`: `(1003, 1, {})`
   - `armyCtrl`: `(1005, 1, {})`
   - `backpackCtrl`: `(1004, 1, {})`
   - `local_queues`: `(1007, 1000, {})`
4. `smart_deep_merge(target: dict, update: dict, key_maps: dict = None) -> dict`:
   Implement the exact algorithm specified in `DEEP_MERGE_SPEC.md`:
   - Recursive dictionary merging.
   - Keyed list merging with Copy-on-Write (CoW) container replacement:
     - `blist`: by `index` (or `binfo.index`), fallback composite `(bid, iid)`.
     - `heroes`: by `id` or `heroId`.
     - `buffCtrl`: by `id` or `buffId`.
     - `queueCtrl`: by `queueId`, `id`, or `qtype`.
     - `consignTasks`: by `index` or `id`.
     - `local_queues`: by `id`.
   - Primitive list replacement with deep copy.
5. `LiveMemoryEngine`:
   Class managing `init_data`, controller whitelisting, notification routing, and thread/async safety:
   - `filter_whitelisted(packet_data: dict) -> dict`: strips any controller key not in `ALLOWED_CONTROLLERS`.
   - `ingest_packet(packet: dict)`: extracts `retdata`, `data`, filters controllers, calls `smart_deep_merge`.
   - `handle_notify(notify_id: int | str, notify_data: dict | list)`:
     - `NOTIFY_CITY`: handles `res` (relative delta addition, min 0), `reslist` (replacement), `saferes`, `dayMaxRes`, `updateUnCollectRes` (increments `curres`), `openChargeQueue`.
     - `NOTIFY_QUEUE` & `NOTIFY_PLAYER_QUEUE_CHANGE`: updates `queueCtrl`. On completion or cancel, updates building state in `cityCtrl`:
       - regular upgrade: increments `lv`, sets `state = "0"` (`BUILD_STATE.NORMAL`).
       - honor upgrade: increments `honorLv` and `hlv`, sets `state = "0"`.
       - cancel: sets `state = "0"`.
     - `backpackCtrl`: updates `add` and `use` deltas.
     - `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, `buffCtrl`: synchronizes updates.
   - `is_memory_ready() -> tuple[bool, list[str]]`: validates presence and structural validity of `CRITICAL_STARTUP_CONTROLLERS` (e.g. non-empty `blist` and `reslist` in `cityCtrl`).
6. Run unit tests to verify all functionality before delivering your handoff.
