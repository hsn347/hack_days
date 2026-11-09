## 2026-11-09T13:20:19Z
You are Worker: Memory Hygiene & Dispatch Refactor Engineer (Agent 9 Implementation).
Your working directory is: e:\osmanli\.agents\teamwork\worker_dispatch_hygiene\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Whitelist Specification: e:\osmanli\.agents\teamwork\agent2_task_scanner\CONTROLLER_WHITELIST_SPEC.md
4. Lua Protocol Specification: e:\osmanli\.agents\teamwork\agent1_lua_analyst\LUA_PROTOCOL_SPEC.md
5. Deep Merge Specification: e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\DEEP_MERGE_SPEC.md
6. Domain Skill: e:\osmanli\.agents\skills\empire-bot\SKILL.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Ownership:
You own `game_client.py` exclusively. Use direct tool `edit_file` to modify it (GEMINI.md Rule 6: NEVER use python scripts to edit code).
Wait for `core/live_memory.py` to be available (or read its specification in `DEEP_MERGE_SPEC.md` and `CONTROLLER_WHITELIST_SPEC.md`).

Task:
Refactor `game_client.py` to achieve zero packet leakage, instantaneous real-time state synchronization, and strict memory readiness gating:
1. In `GameClient.__init__`:
   - Initialize `self.memory_engine = LiveMemoryEngine()` (import from `core.live_memory`).
   - Wire `self.init_data = self.memory_engine.init_data`.
2. In `_dispatch()`:
   - When receiving packets from the socket, immediately pass them through `self.memory_engine.ingest_packet(packet)`.
   - Ensure all non-whitelisted controllers are dropped before entering `init_data` so memory cannot bloat.
   - When receiving `cmd == 1009` (or `"1009"`), extract `notifyID` and `notifyData` and route to `self.memory_engine.handle_notify(notify_id, notify_data)`.
   - Prevent unbounded accumulation of `cached_packets`: retain only packets needed for pending response futures, or cap/prune safely.
3. In `check_and_merge_controller(self, ctrl_name: str)`:
   - Eliminate the slow $O(N)$ historical packet scanning loop. State is now kept live and current in real time!
   - Simply verify if `ctrl_name` is in `self.init_data`.
4. Add `async def wait_for_memory_ready(self, timeout: float = 30.0, auto_fetch_missing: bool = True) -> bool`:
   - Checks `self.memory_engine.is_memory_ready()`.
   - If missing critical controllers and `auto_fetch_missing=True`, dispatches the exact fallback queries defined in `CONTROLLER_WHITELIST_SPEC.md` (`1001/1`, `1002/7`, `1003/1`, `1005/1`, `1004/1`, `1007/1000`).
   - Awaits until memory is ready or timeout occurs. Returns True if ready, False (or raises TimeoutError) if timeout.
5. Verification:
   - Run python syntax check and import tests to ensure zero regressions in `game_client.py`.

Deliverables:
- Edit `game_client.py`.
- Write your report in `e:\osmanli\.agents\teamwork\worker_dispatch_hygiene\handoff.md` and update `progress.md`.
- Send a message when finished referencing your handoff.
