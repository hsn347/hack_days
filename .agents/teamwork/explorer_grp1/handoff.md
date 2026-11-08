# Handoff Report — Group 1 Exploration: BaseTask & MarchCoordinator Dissection

**Agent**: explorer_grp1
**Target Files**: `tasks/base_task.py`, `tasks/march_coordinator.py`
**Analysis Report**: `e:\osmanli\.agents\teamwork\explorer_grp1\analysis.md`
**Date**: 2026-11-08

---

## 1. Observation

1. **Exact File Paths and Line Counts**:
   - `e:\osmanli\tasks\base_task.py`: 1,396 lines, defines `TaskState` (lines 34-40), `TaskResult` (lines 46-86), `PRESTIGE_QUEST_IDS` (lines 89-100), `BaseTask` (lines 107-1330), and `TaskScheduler` (lines 1335-1396).
   - `e:\osmanli\tasks\march_coordinator.py`: 803 lines, defines module-level `PRESTIGE_QUEST_IDS` (lines 53-60), `PRESTIGE_GATHER_RESOURCES` (lines 62-67), `CoordinatorAction` (lines 74-80), `MarchCoordinatorTask` (lines 86-675), and standalone CLI runner (lines 681-803).

2. **Prestige Quest IDs Conflict (Verbatim Quotation)**:
   - In `tasks/base_task.py:89-100`:
     ```python
     PRESTIGE_QUEST_IDS: Dict[str, int] = {
         "invaders":        4112004,
         "stronghold":      4112019,
         "gather":          4112006,
         "smuggler":        4112022,
         "watermill":       4112027,
         "badge_exchange":  4112024,
         "train":           4112001,
         "fortress":        4112015,
     }
     ```
   - In `tasks/march_coordinator.py:53-60`:
     ```python
     PRESTIGE_QUEST_IDS: Dict[str, int] = {
         "invaders":      4112004,
         "stronghold":    4112030,
         "gather_food":   4112000,
         "gather_wood":   4112001,
         "gather_iron":   4112002,
         "gather_silver": 4112003,
     }
     ```
   - Observed Discrepancies:
     * `stronghold`: `4112019` in `base_task.py` vs `4112030` in `march_coordinator.py`.
     * `gather`: aggregate `4112006` in `base_task.py` vs individual `gather_food` (4112000), `gather_wood` (4112001), `gather_iron` (4112002), `gather_silver` (4112003) in `march_coordinator.py`.
     * Collision: ID `4112001` is `train` (تدريب الجنود) in `base_task.py`, while it is `gather_wood` (جمع الخشب) in `march_coordinator.py`.

3. **Subtask Return Handlers and Dropped Cases in `_fallback_action`**:
   - In `tasks/march_coordinator.py:202-219`:
     ```python
     def _fallback_action(self, result: TaskResult, p_key: str) -> str:
         stop = result.data.get("stop_reason", "") if result.data else ""
         status = result.data.get("status", "") if result.data else ""

         if stop in ("QUEUE_FULL", "8004", "9007004") or status == "queue_full":
             return CoordinatorAction.WAIT_AND_RETRY_SAME
         if stop in ("NO_ARMY", "8009") or status == "critical_no_army":
             return CoordinatorAction.TERMINATE
         if stop in ("STAMINA_EMPTY",) or status == "stamina_empty":
             return CoordinatorAction.NEXT_PRIORITY
         if stop in ("NOT_EVENT_DAY", "CASTLE_LV_LOW") or status in ("skipped", "already_done", "already_active"):
             return CoordinatorAction.SKIP_PRIORITY
         return CoordinatorAction.NEXT_PRIORITY
     ```
   - Specifically dropped / unhandled status and stop_reasons:
     * `WEAK_ARMY` (raised as `RuntimeError` in `base_task.py:1029` or returned in `stronghold.py:312`): falls through to `NEXT_PRIORITY`.
     * `SUICIDE_RISK` (returned in `monster.py:1102`): falls through to `NEXT_PRIORITY`.
     * `NPC_LEVEL_LOCKED` (code 8027, returned in `monster.py:1100`): falls through to `NEXT_PRIORITY`.
     * `REBEL_PREREQUISITE_FAILED` (returned in `monster.py:929`): falls through to `NEXT_PRIORITY`.
     * `CMD_OPTING` (code 16001, returned in `monster.py`, `gather.py`, `stronghold.py`, `gold_gather.py`): falls through to `NEXT_PRIORITY`.
     * `NO_HEROES` / `HERO_BUSY`: falls through to `NEXT_PRIORITY`.

4. **All 20 Server Error Codes & `ExcludeManager` Protocol**:
   - `8004`, `9007004`, `8009`, `8035`, `8032`, `10002`, `10003`, `9007020`, `8014`, `8015`, `8027`, `8037`, `8041`, `8042`, `8046`, `8060`, `8062`, `8063`, `8095`, `16001`.
   - `ExcludeManager` calls observed: `reserve(uid, target_id, kingdom_id)` on search match; `confirm(uid, target_id, kingdom_id)` on success or permanent occupied (8062, 8063, 8060); `release(uid, target_id, kingdom_id)` on retryable/transient failures (8004, 8009, 8032, 8035, 8027, 16001).

---

## 2. Logic Chain

1. **Premise 1 (Prestige Query Divergence)**:
   - When `march_coordinator.py` checks `self._get_quest_info("stronghold")`, it references `march_coordinator.PRESTIGE_QUEST_IDS`, resolving `"stronghold"` to `4112030` (`march_coordinator.py:55`).
   - If a subtask or client code references `base_task.PRESTIGE_QUEST_IDS`, it resolves `"stronghold"` to `4112019` (`base_task.py:92`).
   - Since server packet `meritoriousTaskCtrl` contains task data keyed by one specific ID depending on quest type/game event version, querying with the mismatched key returns `found: False`, causing `_priority_prestige_stronghold` to miscalculate `needed` marches or repeat completed quests.

2. **Premise 2 (Cascade Hang on Code 16001 `CMD_OPTING`)**:
   - When game server returns `16001` (lock on concurrent actions for the UID), the subtask fails and outputs `stop_reason="CMD_OPTING"`.
   - `_fallback_action` in `march_coordinator.py:218` does not intercept `CMD_OPTING`, dropping it into default `NEXT_PRIORITY`.
   - The coordinator sleeps only 1.5–3.0 seconds (`march_coordinator.py:169`) before firing the next priority subtask.
   - The server lock has not cleared (requires ~10–16 seconds), causing the next priority to fail immediately with 16001 as well.
   - All 10 priorities fail in sequence within ~20 seconds without dispatching a single march.

3. **Premise 3 (Troop Allocation Deficit across Priorities)**:
   - Coordinator tracks `self._busy_heroes` and `self._used_pets` (`march_coordinator.py:112-113`), but has NO `self._used_army` tracking across priority transitions.
   - When priority 2 (`prestige_invaders`) completes an attack, the troops are marching out, but `self.conn.init_data['armyCtrl']['totalArmy']` has not yet synced from server.
   - Priority 3 (`prestige_stronghold`) reads available troops from memory, assumes the dispatched troops are still in castle, attempts to form a march, and triggers server error `8009` (`Err_NOT_ENOUGH_ARMY`).

---

## 3. Caveats

1. The exact live server packet structure for `meritoriousTaskCtrl` may vary between older game server versions (where 4112019 was used) and newer partitions (where 4112030 is used). Both IDs should be checked or consolidated with an alias map.
2. We strictly maintained read-only access: no code modifications were applied to `tasks/base_task.py` or `tasks/march_coordinator.py`. All proposed fixes are documented in `analysis.md` and this handoff.

---

## 4. Conclusion

1. `tasks/base_task.py` provides a comprehensive framework, but leaks domain-specific combat logic (`get_combat_heroes`, `get_march_army`, `_pick_balanced_combat_troops`) into the generic base class and throws an uncaught `RuntimeError` (`WEAK_ARMY`).
2. `tasks/march_coordinator.py` possesses critical protocol gaps: 5 major stop reasons (`WEAK_ARMY`, `SUICIDE_RISK`, `NPC_LEVEL_LOCKED`, `REBEL_PREREQUISITE_FAILED`, `CMD_OPTING`) are dropped into `NEXT_PRIORITY`, leading to rapid cascade failures.
3. The collision in `PRESTIGE_QUEST_IDS` (especially `stronghold` 4112019 vs 4112030, and ID `4112001` meaning both `train` and `gather_wood`) must be reconciled into a unified dictionary in `base_task.py`.
4. Comprehensive detailed evidence, line numbers, execution traces, and red-team critiques have been written to `e:\osmanli\.agents\teamwork\explorer_grp1\analysis.md`.

---

## 5. Verification Method

1. **Verify File Existence and Content**:
   - Inspect `e:\osmanli\.agents\teamwork\explorer_grp1\analysis.md` to verify all 6 required sections are thoroughly populated with zero summarization.
   - Inspect `e:\osmanli\tasks\base_task.py` lines 89-100 and `e:\osmanli\tasks\march_coordinator.py` lines 53-67 to verify the exact quest ID conflicts.
   - Inspect `e:\osmanli\tasks\march_coordinator.py` lines 202-219 to verify the exact missing branches in `_fallback_action`.

2. **Programmatic Verification Target**:
   - Run verification test script ensuring 100% coverage of all 10 priority functions, 20 error codes, and 5 critical stop reasons documented in `analysis.md`.
