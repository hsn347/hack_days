# Project: Live State Memory Architecture & 20-Agent Swarm

## Architecture
- **Core Game Client**: `game_client.py` (Packet dispatching, socket framing, real-time dispatch, state caches).
- **Bot Engine & Lifecycle**: `bot_manager.py` (Account lifecycle, task execution loop, memory readiness verification).
- **Live Memory Engine**: Unified memory engine (`core/live_memory_engine.py` or within `game_client.py`) intercepting `retdata`, `data`, and `notifyData`.
- **Reference Specification**: `e:\osmanli\game file\lua_src` (`cityCtrl.lua`, `notifyCtrl.lua`, `queueCtrl.lua`, etc.).
- **Live Verification Suite**: Real session execution via `session_cache.json` and hermetic simulated packet test suites.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Lua Protocol & Notification Analysis | Comprehensive extraction of `gNotifyID`s, notification payloads, and controller schemas from `game file/lua_src` | M0 | R0 (Agent 1) |
| 2 | Task Scanner & Controller Whitelist | Audit all `tasks/` and `bot_manager.py` to establish `ALLOWED_CONTROLLERS` and `CRITICAL_STARTUP_CONTROLLERS` | M0 | R0 (Agent 2), R1 |
| 3 | Smart Deep-Merge Engine | Keyed list merge algorithm (`blist` via `index`, `heroes`/`buffCtrl` via `id`) preventing data wipes and duplicates | M1 | R0 (Agent 8), R2 |
| 4 | Memory Hygiene & Dispatch Refactor | Immediate packet routing in `_dispatch`, eliminating packet staleness and memory bloat | M1 | R0 (Agent 9), R2 |
| 5 | City, Building & Resource Sync | Full replication of `cityCtrl.lua` logic (`reslist`, `saferes`, `dayMaxRes`, `updateUnCollectRes`, `openChargeQueue`) | M2 | R0 (Agent 4), R2 |
| 6 | Queues & Build Lifecycle Sync | Direct linkage of `NOTIFY_QUEUE` to `queueCtrl` and `cityCtrl` building state/level updates | M2 | R0 (Agent 5), R2 |
| 7 | Army, Hero, Lord & Backpack Sync | Real-time synchronization for `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, `buffCtrl`, `backpackCtrl`, `meritoriousTaskCtrl` | M2 | R0 (Agent 6, 7) |
| 8 | Strict Memory Readiness Gate & Fallback Query | `wait_for_memory_ready` with automated fallback queries for missing critical controllers | M3 | R0 (Agent 3), R3 |
| 9 | Bot Loop Integration & Elf Decoupling | Integrate memory readiness into `bot_manager.py` startup loop while strictly preserving elf task decoupling | M3 | R0 (Agent 10), R3, GEMINI.md |
| 10 | Live Connection & Init Verification | Field testing with real `session_cache.json` validating packet flow and live state population | M4 | R0 (Agent 11) |
| 11 | Live Gate & Fallback Testing | Empirical verification of bot pausing on missing critical controllers and successful fallback recovery | M4 | R0 (Agent 12) |
| 12 | Live Socket Spy & Notify Verification | Verification of live S2C packet reception and instantaneous reflection in state | M4 | R0 (Agent 13) |
| 13 | City & Resource Delta QA | Practical verification of `NOTIFY_CITY` mutations and building upgrades | M4 | R0 (Agent 14, 15) |
| 14 | Marches, Army, Backpack & Hero QA | Empirical verification of army march queues and inventory delta computations | M4 | R0 (Agent 16, 17) |
| 15 | Whitelist & Memory Footprint Audit | Verification of zero unauthorized controllers in `init_data` | M4 | R0 (Agent 18) |
| 16 | Concurrency & Stress Testing | Verification of race condition resistance and duplicate-free concurrent deep merges | M4 | R0 (Agent 19) |
| 17 | Chief QA Sign-off & Forensic Audit | Comprehensive verification and independent forensic integrity sign-off | M5 | R0 (Agent 20) |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Survey & Specification Mining | F1, F2: Lua protocol mapping & task controller audit | none | DONE |
| M1 | Core Memory Engine & Deep Merge | F3, F4: Smart deep-merge engine, memory hygiene, dispatch refactoring | M0 | DONE |
| M2 | Controller State Synchronizers | F5, F6, F7: City, building, queue, army, hero, backpack sync | M1 | DONE |
| M3 | Readiness Gate & Bot Loop Integration | F8, F9: `wait_for_memory_ready`, fallback query, `bot_manager.py` hook | M1, M2 | DONE |
| M4 | Swarm Live Verification & QA Battery | F10 - F16: 7 specialized live & simulated test agents executing in parallel | M2, M3 | DONE |
| M5 | Chief QA Sign-Off & Forensic Audit | F17: Final forensic integrity audit and sign-off report | M4 | DONE |

## Interface Contracts
### 1. Controller Whitelists
- `ALLOWED_CONTROLLERS: frozenset[str]`:
  Strict set of all 44 controllers consumed by bot tasks, internal state keys, and core logic (including `local_queues`). Any packet targeting a controller outside this set is dropped at ingress.
- `CRITICAL_STARTUP_CONTROLLERS: frozenset[str]`:
  Mandatory 6 controllers required for bot operation (`cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, `heroCtrl`, `backpackCtrl`). Bot execution is blocked until all are populated with structural validity.

### 2. LiveMemoryEngine Interface
- `smart_deep_merge(target: dict, source: dict) -> dict`:
  Recursively merges `source` into `target`.
  - Dictionaries: recursive merge.
  - Lists of dicts: identify primary keys (`index`, `bid`, `iid`, `id`, `queueId`) and merge matching elements; append new elements.
  - Primitive values: replace.
- `handle_notify(notify_id: int, notify_data: dict) -> None`:
  Dispatches notification payloads to registered controller synchronizers.

### 3. Readiness Gate Contract
- `async wait_for_memory_ready(self, timeout: float = 30.0, auto_fetch_missing: bool = True) -> bool`:
  Checks presence of `CRITICAL_STARTUP_CONTROLLERS` in `self.init_data`.
  Validates structural integrity (e.g., `cityCtrl.blist` is non-empty list, `reslist` present).
  If missing and `auto_fetch_missing=True`, dispatches fallback sync commands (`_send_command`) for each missing controller.
  Raises or returns `False` if timeout expires before memory is ready.

## Code Layout
- Reference Code: `game file/lua_src/src/src/app/module/*/*.lua`
- Core Client: `game_client.py`
- Memory Engine / Modules: `core/live_memory.py` (or integrated in `game_client.py`)
- Bot Manager: `bot_manager.py`
- Tasks: `tasks/*.py`
- Test Suites: `tests/test_live_memory.py`, `tests/test_readiness_gate.py`, `tests/test_deep_merge.py`
- Metadata: `.agents/teamwork/`
