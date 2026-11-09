# Handoff Report — Agent 17: Backpack, Hero & Lord QA Verification

**Agent**: Agent 17 (Backpack, Hero & Lord QA Agent)  
**Roles**: Reviewer & Adversarial Critic  
**Date**: 2026-11-09T13:55:00Z  
**Verdict**: **APPROVE** (With 2 Adversarial Edge-Case Findings Documented)  
**Target Path**: `core/live_memory.py` / `game_client.py`  
**Test Suite**: `e:\osmanli\.agents\teamwork\agent17_backpack_hero_lord\run_qa_verification.py`  

---

## 1. Observation

### 1.1 Source Code Inspection
- **`backpackCtrl` Notification Handler (`core/live_memory.py:757-814`)**:
  ```python
  def _handle_notify_backpack(self, notify_data: Any) -> None:
      data_block = notify_data[0] if (isinstance(notify_data, list) and notify_data) else notify_data
      if not isinstance(data_block, dict):
          return
      backpack = self.init_data.setdefault("backpackCtrl", {})
      # Handle additions
      add_items = data_block.get("add", {})
      if isinstance(add_items, dict):
          for item_id, count in add_items.items():
              k = str(item_id)
              delta = int(count)
              if isinstance(backpack, dict):
                  if k in backpack:
                      if isinstance(backpack[k], dict):
                          old = int(backpack[k].get("count", 0))
                          backpack[k]["count"] = str(old + delta)
                      else:
                          backpack[k] = max(0, int(backpack[k]) + delta)
                  else:
                      backpack[k] = {"id": k, "count": str(delta)}
  ```
  And for consumptions (`use`):
  ```python
      use_items = data_block.get("use", {})
      if isinstance(use_items, dict):
          for item_id, count in use_items.items():
              k = str(item_id)
              delta = int(count)
              if isinstance(backpack, dict):
                  if k in backpack:
                      if isinstance(backpack[k], dict):
                          old = int(backpack[k].get("count", 0))
                          backpack[k]["count"] = str(max(0, old - delta))
                      else:
                          backpack[k] = max(0, int(backpack[k]) - delta)
  ```
- **Reference Lua Deletion Logic (`game file/lua_src/backpack_dec.lua:38-45`)**:
  ```lua
  local function useItem_(self, itemID, count)
    local item = self.items[itemID]
    local subCount, totalCount = item:sub(count)
    self.size_ = self.size_ + subCount
    if totalCount <= 0 then
      self.items[itemID] = nil
    end
  end
  ```
- **`heroCtrl` Entity Merging (`core/live_memory.py:828-863` & `173-175`)**:
  - Entity primary keys: `DEFAULT_KEY_MAPS["heroCtrl"] = ("id", "heroId", "cId")`.
  - Normalization: String key representation `candidate:str(val).strip()` via `extract_entity_key` (`core/live_memory.py:255`).
  - Container swapping: `_merge_keyed_lists` replaces target list pointer atomically using Copy-on-Write (`CoW`).
- **`lordInfoCtrl` Dynamic State Routing (`core/live_memory.py:864-882`)**:
  - For each element in `NOTIFY_LORD` (8), extracts `key = item.get("key")` (e.g., `base`, `fcInfo`, `physical`, `official`) and applies `smart_deep_merge` to `lordInfoCtrl[key]` in place.
- **Readiness Gate & Fallback Queries (`core/live_memory.py:1019-1084` & `114-121`)**:
  - `backpackCtrl` is registered under `CRITICAL_STARTUP_CONTROLLERS` with fallback `(1004, 1, {})`.
  - `lordInfoCtrl` validates presence of `base.uid` with fallback `(1002, 7, {"uid": uid})`.
  - `heroCtrl` validates presence of list or dict container.

### 1.2 Programmatic Test Execution
Execution of independent QA verification suite `run_qa_verification.py`:
```
Command: python e:\osmanli\.agents\teamwork\agent17_backpack_hero_lord\run_qa_verification.py
Results:
test_01_backpack_dict_add_sync_increments_accurately ... ok
test_02_backpack_dict_use_sync_decrements_accurately ... ok
test_03_backpack_dict_count_reaches_zero_behavior ... ok
test_04_backpack_adversarial_underflow_clamped_to_zero ... ok
test_05_backpack_list_representation_add_and_use ... ok
test_06_backpack_ingest_via_network_packet_cmd1009 ... ok
test_01_hero_ctrl_list_20_heroes_delta_update_and_new_hero_append ... ok
test_02_hero_ctrl_nested_dict_heroes_entity_preservation ... ok
test_03_hero_ctrl_adversarial_mixed_string_and_int_ids ... ok
test_04_hero_ctrl_adversarial_heroId_only_discrepancy ... ok
test_01_lord_base_attributes_update_via_notify_lord ... ok
test_02_lord_fc_info_combat_power_update ... ok
test_03_lord_stamina_and_physical_recovery_update ... ok
test_04_lord_official_rank_update ... ok
test_05_lord_multi_key_batch_notification ... ok
test_fallback_queries_available ... ok
test_readiness_gate_structural_validation ... ok

Ran 17 tests in 0.005s — OK (All 17 passed, 0 failures, 0 errors)
```

---

## 2. Logic Chain

### 2.1 Inventory Math & Zero-Count Verification (`backpackCtrl`)
1. **Add Verification**: An initial inventory containing `{"200101": {"count": "50"}}` was fed `{"add": {"200101": 25, "200103": 5}}`.
   - Result: `200101` incremented to `75`; new item `200103` was initialized with count `5`. Matches mathematical addition $50 + 25 = 75$.
2. **Use Verification**: Initial inventory containing `{"200101": {"count": "75"}}` was fed `{"use": {"200101": 15}}`.
   - Result: `200101` decremented to `60`. Matches mathematical subtraction $75 - 15 = 60$.
3. **Count Reaches Zero / Deletion Behavior**:
   - Initial inventory containing `{"200101": {"count": "10"}}` was fed `{"use": {"200101": 10}}`.
   - Result: The item remained in `backpackCtrl` with `"count": "0"`. It was clamped via `max(0, old - delta)` rather than popped via `pop()`.
   - Comparison with Lua: In Lua `backpack.lua:43`, `self.items[itemID] = nil` removes the item. In Python, keeping `"count": "0"` allows downstream tasks to read `int(count) == 0`. In `tasks/research.py:262` and `tasks/building.py:746`, tasks check `int(count) > 0`, so behavior is functionally safe.
4. **Underflow Protection**: Consuming 999 items when only 5 exist resulted in count `0` (never negative).

### 2.2 Hero Entity Preservation & Delta Merging (`heroCtrl`)
1. **Initial Population**: 20 distinct canonical heroes were initialized (10 Orange heroes `5501001-5501010` and 10 Purple heroes `5502001-5502010`).
2. **Delta Update**: Delta modifying `lv=60` and `star=5` for hero `5501001` was ingested via `NOTIFY_HERO` (Subcommand 104).
   - Result: Hero `5501001` updated to `lv: 60` and `star: 5`. Untouched fields (`exp`, `skills`, `appointStatus`, `power`) remained 100% preserved.
3. **New Hero Addition**: Delta adding recruit `5502015` was ingested via `NOTIFY_HERO`.
   - Result: Exactly 21 heroes exist in `heroCtrl`.
4. **Zero Duplicates Assertion**:
   - Total hero IDs extracted: 21. Unique hero IDs: 21 (`len(set(hero_ids)) == 21`).
   - Copy-on-Write list reference was swapped cleanly without mutating existing list in place.
5. **Format Dual-Support**: Tested both canonical formats (`heroCtrl` as `List[Dict]` and `heroCtrl` as `{"heroes": List[Dict]}`); both merged cleanly.

### 2.3 Lord State Updates (`lordInfoCtrl`)
1. **Base Attributes**: NOTIFY_LORD with `key: "base"` updated `level` (35 -> 36), `exp` (4500000 -> 5200000), `gold` (5000 -> 6500), `spar` (1200 -> 1500), `power` (45M -> 48M), while preserving untouched `uid: 12345678` and `name: "OttomanSultan"`.
2. **Combat Power (`fcInfo`)**: NOTIFY_LORD with `key: "fcInfo"` updated overall `power`, `armyPower`, and `heroPower`, leaving `buildPower` and `techPower` intact.
3. **Stamina / Health**: NOTIFY_LORD with `key: "base", health: 85` updated lord stamina. Recovery queue timer `key: "physical", time: 240` was updated concurrently.
4. **Official Rank**: NOTIFY_LORD with `key: "official"` updated office ID `105`, rank `4`, title `"Grand Vizier"`.
5. **Batch Updates**: A multi-key payload containing `base`, `fcInfo`, `skill`, and `official` in a single packet merged all sub-models atomically.

### 2.4 Integrity Assessment
- Checked `core/live_memory.py` for hardcoded hero IDs, item IDs, or fake mock values. None exist; logic is fully generic.
- No shortcuts or facade mocks detected.

---

## 3. Caveats

1. **Item Deletion Discrepancy (Finding 1 - Low)**:
   - In `core/live_memory.py:804`, when an item count drops to zero through `use`, the item entry remains in `backpackCtrl` with `"count": "0"` rather than being deleted via `del` or `.pop()`.
   - In reference Lua (`backpack_dec.lua:42`), the item is explicitly deleted (`self.items[itemID] = nil`).
   - Mitigation: All existing bot tasks in `tasks/` query items by reading `int(v.get("count", 0)) > 0`, so functionality is unaffected. However, code that checks `if item_id in conn.init_data['backpackCtrl']` will evaluate to `True`.
2. **Asymmetric Key Prefixing (Finding 2 - Low)**:
   - In `core/live_memory.py:255`, `extract_entity_key` prefixes the matching field name (e.g., `id:5501001` vs `heroId:5501001`).
   - If an existing hero in target memory was keyed by `id` and an incoming partial delta provides ONLY `heroId` without `id`, `extract_entity_key` will produce different keys (`id:5501001` vs `heroId:5501001`), resulting in an append rather than a merge.
   - Mitigation: Standard server hero packets deliver `id`, so standard flow is unaffected. Recommended fix in future refactoring is aliasing `id` and `heroId` to the same canonical key prefix.

---

## 4. Conclusion

1. **Backpack Inventory Math**: **VERIFIED**. Additions increment accurately; consumptions decrement accurately; negative underflows are clamped to 0. Items reaching count 0 are retained with count `"0"`.
2. **Hero Entity Preservation**: **VERIFIED**. Starting with 20 heroes, delta updating hero `5501001` and adding hero `5502015` results in exactly 21 heroes, zero duplicate entities, and full preservation of unmentioned fields.
3. **Lord Info State Updates**: **VERIFIED**. Base attributes, fcInfo combat power, stamina/health, and official ranks update cleanly across individual and batched push notifications.
4. **Final Verdict**: **APPROVE**.

---

## 5. Verification Method

To independently reproduce and verify this review, execute the following commands in the workspace root:

```powershell
# 1. Run the dedicated Agent 17 QA Verification Suite (17 tests)
python e:\osmanli\.agents\teamwork\agent17_backpack_hero_lord\run_qa_verification.py

# 2. Run the core Live Memory regression test suite (37 tests)
python -m unittest tests.test_live_memory
```

**Invalidation Conditions**:
- If `TestHeroCtrlEntityPreservation.test_01_hero_ctrl_list_20_heroes_delta_update_and_new_hero_append` fails or reports `len(heroes) != 21` or duplicate hero IDs.
- If `TestBackpackInventoryMath.test_01_backpack_dict_add_sync_increments_accurately` or `test_02_backpack_dict_use_sync_decrements_accurately` fails.
- If `TestLordInfoCtrlStateUpdates.test_01_lord_base_attributes_update_via_notify_lord` fails to preserve `uid` or fails to update `level`/`gold`/`spar`.
