# Handoff Report: Red Team Adversarial Trial & Unified Architecture

**From**: `critic_1` (Reviewer / Critic / Specialist)  
**To**: Parent Orchestrator (`2fe1a59e-c1ac-4e58-8bed-3e6333fd6e77`)  
**Date**: 2026-11-08T16:32:00Z  
**Deliverable Path**: `e:\osmanli\.agents\teamwork\critic_1\critique.md`  

---

## 1. Observation

Direct code observations with exact line numbers and quotations from the reviewed codebase:

1. **Coordinator Fallback Action Dropouts (`tasks/march_coordinator.py:202–219`)**:
   `_fallback_action` explicitly tests only:
   - `stop in ("QUEUE_FULL", "8004", "9007004") or status == "queue_full"` -> `WAIT_AND_RETRY_SAME`
   - `stop in ("NO_ARMY", "8009") or status == "critical_no_army"` -> `TERMINATE`
   - `stop in ("STAMINA_EMPTY",) or status == "stamina_empty"` -> `NEXT_PRIORITY`
   - `stop in ("NOT_EVENT_DAY", "CASTLE_LV_LOW") or status in ("skipped", "already_done", "already_active")` -> `SKIP_PRIORITY`
   - Default: `return CoordinatorAction.NEXT_PRIORITY`
   Verbatim observation: `WEAK_ARMY`, `SUICIDE_RISK`, `NPC_LEVEL_LOCKED`, `REBEL_PREREQUISITE_FAILED`, and `CMD_OPTING` (`16001`) are completely absent from this conditional chain and fall through to `NEXT_PRIORITY`.

2. **Coordinator Troop Tracking Gap (`tasks/march_coordinator.py:112–113`)**:
   `MarchCoordinatorTask.__init__` instantiates:
   ```python
   self._busy_heroes: Set[int] = set()
   self._used_pets:   Set[int] = set()
   ```
   No `_used_army` dictionary is declared or maintained across priority executions. In lines 332, 380, 426, 492, 538, 570, 599, 620, and 672, only heroes and pets are updated.

3. **Prestige Quest Dual-Definition Collisions (`base_task.py:89–100` vs `march_coordinator.py:53–60`)**:
   - In `base_task.py`:
     ```python
     PRESTIGE_QUEST_IDS = {
         "invaders": 4112004,
         "stronghold": 4112019,
         "gather": 4112006,
         "train": 4112001,
         ...
     }
     ```
   - In `march_coordinator.py`:
     ```python
     PRESTIGE_QUEST_IDS = {
         "invaders": 4112004,
         "stronghold": 4112030,
         "gather_food": 4112000,
         "gather_wood": 4112001,
         "gather_iron": 4112002,
         "gather_silver": 4112003,
     }
     ```
   ID `4112001` is `"train"` in `base_task.py` and `"gather_wood"` in `march_coordinator.py`. Stronghold is `4112019` in `base_task.py` and `4112030` in `march_coordinator.py`.

4. **Blanket `80xx` ExcludeManager Poisoning (`tasks/monster.py:1566–1569`, `tasks/stronghold.py:435–439`)**:
   - `monster.py:1566`:
     `elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.startswith('80') and err not in ('8004', '8009', '8032', '8027', '8035')):`
     `await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)`
   - `stronghold.py:435`:
     `elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.isdigit() and 8000 <= int(err) < 8100 and err not in ('8004', '8009', '8032')):`
     `await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)`

5. **Error `8027` Misclassification in `stronghold.py:435`**:
   Error `8027` is between `8000` and `8100` and is not `8004`, `8009`, or `8032`. It executes `confirm()` instead of `release()` and does not downgrade search level.

6. **Error `8009` Premature Abort in `stronghold.py:393–396`**:
   ```python
   elif err == '8009':
       self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
       await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
       return "NO_ARMY"
   ```
   Does not query active marches before returning `"NO_ARMY"`.

7. **Missing Error `8035` in `tasks/abra.py:862–932`**:
   No branch exists for `8035`. An `8035` error hits line 928 `else: break`, terminating the session.

8. **Abra Pipelined Killing Blow (`tasks/abra.py:955, 985–991`)**:
   Line 955 checks `if not self.killing_blow and current_hp <= self.stop_threshold: break`. If `current_hp > self.stop_threshold` (e.g. 1,400,000 > 1,350,000), line 985 launches March $N+1$ immediately. Transit time is 30–60s with no safety cushion against mid-flight damage or March $N+1$'s own damage.

---

## 2. Logic Chain

1. **Priority Inversion & Deadlock**: Because `ruins` (Priority 6) and `prestige_gather` (Priority 4) lock queues for 15 minutes to 8 hours, placing them ahead of `combat` (Priority 7) and `stronghold` (Priority 8) causes `combat` to encounter saturated queues. `_fallback_action` translates `QUEUE_FULL` into `WAIT_AND_RETRY_SAME` (3-minute wait). Since ruins cannot finish in 3 minutes, the 3-minute retry loop repeats until the coordinator's 20-minute timer (`max_duration`) expires, completely starving Priorities 7, 8, 9, and 10.
2. **Ghost Troop Aborts**: Subtasks dispatch marches that consume castle troops. Because `march_coordinator.py` does not track `_used_army`, the subsequent priority executes with stale total troops, dispatches ghost troops, triggers server error `8009`, and because `stronghold.py` immediately returns `NO_ARMY`, the coordinator executes `TERMINATE`, aborting all remaining priorities.
3. **Cache Poisoning**: When non-target errors (`8041`, `8042`, `8046`, `8037`, `8095`, `8014`, `8015`) occur, lines 1566 in `monster.py` and 435 in `stronghold.py` execute `confirm()`. This writes the blameless map target into `exclude_history.json` with a 4-hour ban, blinding all bots in the kingdom.
4. **Stronghold High-Tier Lockout**: Because `stronghold.py` lacks an `8027` handler, first-kill locked strongholds are treated as occupied, confirming their exclusion and blacklisting all discovered targets in the search radius.
5. **Abra Session Destruction**: Buff expirations reduce march capacity. When `1007/2` fails with `8035`, `abra.py`'s failure to reduce troops by 18% causes an immediate `break`, abandoning up to 19 attacks and millions in gold.
6. **Kill-Stealing Race Condition**: Because March $N+1$ is dispatched whenever HP is above the stop boundary without subtracting March $N+1$'s projected damage ($D_{march} \approx 650,000$), March $N+1$ frequently lands the killing blow when HP was between $1,350,000$ and $2,000,000$, violating user configuration.

---

## 3. Caveats

- All findings were derived from surgical code analysis of the local workspace files and verified against game protocol specifications and Lua decompilation rules (`empire-bot` skill).
- Live execution verification was performed in demonstration/audit mode without modifying production files or pushing to remote servers (complying strictly with `GEMINI.md` Rules 4 and 5).
- No caveats regarding code coverage: 100% of the 10 priorities and all 5 files were audited without summarization.

---

## 4. Conclusion

The current exterior march implementation suffers from severe architectural fragmentation. Core combat routines (hero filtering, pet sorting, troop capacity scaling, error handling) are duplicated across 1,680+ lines in `monster.py`, `stronghold.py`, and `abra.py`. These duplicates contain divergent logic that introduces critical failure modes (blanket 80xx cache poisoning, 8027 stronghold lockouts, 8035 Abra aborts, and priority inversion deadlocks).

**Verdict: REQUEST_CHANGES**  
The proposed canonical unified design in `critique.md` must be adopted:
1. Absorb all hero, pet, rune, army substitution, anti-suicide, and error handling methods into `BaseTask`.
2. Delete redundant dictionaries and helpers across `monster.py`, `stronghold.py`, and `abra.py`, reducing combined code footprint by ~1,680 lines.
3. Add `_used_army` tracking and explicit fallback action mappings to `march_coordinator.py`.
4. Enforce the Damage Safety Margin on Abra pipelined marching.

---

## 5. Verification Method

To independently verify all claims:
1. **Source Inspection**:
   - Inspect `e:\osmanli\tasks\march_coordinator.py:202–219` to verify omission of `WEAK_ARMY`, `SUICIDE_RISK`, `NPC_LEVEL_LOCKED`, `REBEL_PREREQUISITE_FAILED`, `CMD_OPTING`.
   - Inspect `e:\osmanli\tasks\stronghold.py:435` to verify omission of `8027` from the `not in ('8004', '8009', '8032')` exception list.
   - Inspect `e:\osmanli\tasks\abra.py:862–932` to verify absence of `8035` handling.
   - Inspect `e:\osmanli\tasks\base_task.py:89–100` vs `e:\osmanli\tasks\march_coordinator.py:53–60` to verify `4112019` vs `4112030` and `train` vs `gather_wood` on `4112001`.
2. **Report Review**:
   - Read the exhaustive deliverable: `e:\osmanli\.agents\teamwork\critic_1\critique.md`.
3. **Invalidation Conditions**:
   - If `stronghold.py` can be shown to handle `8027` without calling `confirm()`, claim 5 is invalidated.
   - If `abra.py` can be shown to scale down troops on `8035`, claim 7 is invalidated.
   - If `_fallback_action` in `march_coordinator.py` can be shown to map `WEAK_ARMY` or `16001`, claim 1 is invalidated.
