# Full Exhaustive Dissection of Combat and Monster Tasks: `tasks/monster.py`, `tasks/stronghold.py`, `tasks/abra.py`

## Executive Summary & Architectural Context

This technical audit represents an exhaustive, line-by-line, function-by-function, and path-by-path dissection of three core exterior march combat modules in the Empire bot codebase:
1. `tasks/monster.py` (1,642 lines): Dispatches solo marches against Invaders (`mapType=6`) and alliance rally marches against Elite Rebels (`mapType=35`). Incorporates dynamic capacity checks, official game power matrices, level auto-capping, suicide protection, and queue throttling.
2. `tasks/stronghold.py` (507 lines): Dispatches solo occupation/attack marches against World Strongholds / Shelters (`mapType=26`, `moveLineType=3`, `judianState=1`). Relies heavily on inherited helpers from `BaseTask` and dynamic compensation routines.
3. `tasks/abra.py` (1,194 lines): Manages weekly boss combat against the God Beast / Gold Monster "Abra" (`mapType=25`, class IDs `4301`/`4302`), implementing pipelined sequential dispatching, killing-blow HP thresholds (`1,350,000` HP cutoff), outbound-only wait timing, and resilient socket reconnect loops.

The scope of this investigation satisfies the strict non-summarization directive: all functions, configuration keys, memory objects, network subcommands, server error branches, race conditions, and duplicated routines are documented in complete structural detail.

---

# Part I: Deep Surgical Dissection of `tasks/monster.py`

## 1.1 Module Metadata, Architectural Role & Imports

- **Path**: `tasks/monster.py`
- **Total Lines**: 1,642 lines
- **Role**: Exterior PvE combat against standard Invaders (solo march) and Elite Rebels (rally march).
- **Dependencies & Imports**:
  - `asyncio`, `json`, `logging`, `random`, `math`, `sys`, `os`, `typing` (`Any`, `Dict`, `List`, `Optional`, `Set`, `Tuple`)
  - `tasks.base_task.BaseTask`, `tasks.base_task.TaskResult`
  - `game_client.GameConnection`
  - `tasks.exclude_manager.get_manager as _get_exclude_manager`
  - `tasks.march_capacity.get_castle_march_capacity`, `tasks.march_capacity.enforce_safe_march_troops`, `tasks.march_capacity.record_learned_march_capacity`

### Global Constants Defined at Module Level:
- `DEFAULT_MONSTER_TYPE = "invaders"`: Default target category.
- `DEFAULT_MIN_LV = 1`: Default minimum search level.
- `DEFAULT_MAX_LV = 30`: Default maximum search level.
- `DEFAULT_MAX_MARCHES = 64`: Default total march dispatch count.
- `DEFAULT_SEARCH_RANGE = 100`: Default map search radius in coordinate units.
- `DEFAULT_FORMATION_ID = 1`: Saved formation index (1..5); 0 denotes auto-smart combat composition.
- `DEFAULT_TROOPS_COUNT = 30000`: Fallback troop count when no formation exists.
- `MONSTER_TYPES`: Target mapping dictionary:
  - `"rebels"`: `{"mapType": 35, "subType": 0, "name": "🏴‍☠️ متمردين (Rebels)"}`
  - `"invaders"`: `{"mapType": 6, "subType": 0, "name": "👾 غزاة (Invaders)"}`
- `OFFICIAL_NPC_FC` (Lines 85–121): Official Invader Force Combat (FC) table for levels 1 to 35 extracted from `npc.lua`.
  - Levels: `1: 30`, `2: 250`, `3: 740`, `4: 1694`, `5: 2765`, `6: 4945`, `7: 7418`, `8: 10404`, `9: 17294`, `10: 23084`, `11: 30142`, `12: 38622`, `13: 49767`, `14: 61408`, `15: 74751`, `16: 91404`, `17: 110626`, `18: 132470`, `19: 156972`, `20: 231400`, `21: 279580`, `22: 334960`, `23: 397750`, `24: 468160`, `25: 546390`, `26: 760670`, `27: 855840`, `28: 960000`, `29: 1073300`, `30: 1105534`, `31: 1406856`, `32: 1559454`, `33: 1763550`, `34: 2018664`, `35: 2040892`.
- `OFFICIAL_REBEL_FC` (Lines 124–130): Official Elite Rebel FC table for levels 1 to 5 extracted from `world_boss_show.lua`.
  - `1: 60000` (18,700 T2/T3 garrison)
  - `2: 312000` (53,600 T4/T5 garrison)
  - `3: 1196000` (129,000 T6/T7 garrison)
  - `4: 3020000` (266,800 T7/T8 garrison)
  - `5: 7518000` (475,200 T9/T10 garrison)
- `BUILD121_CAPACITY` (Lines 134–139): Drill Grounds (bid 121) march capacity per building level (1 to 35) extracted from `build121.lua`. Added to `DEFAULT_EXP_ARMY_COUNT = 1000`.
- `ARMY_TIER_POWER` (Lines 142–155): Official combat multiplier per soldier tier extracted from `armyinfo.lua`:
  - `T1: 1.0`, `T2: 1.4`, `T3: 1.9`, `T4: 2.5`, `T5: 3.2`, `T6: 4.0`, `T7: 4.9`, `T8: 5.9`, `T9: 7.0`, `T10: 8.2`, `T11: 9.5`, `T12: 11.0`.

---

## 1.2 Complete Table of Inputs, Configurations, Defaults & Validation Logic

| Config Parameter | Type | Default Value | Accepted / Valid Values | Validation & Sanitization Logic | Source / Ingestion Point |
|---|---|---|---|---|---|
| `monster_type` | `str` | `"invaders"` | `"invaders"`, `"rebels"`, `"غزاة"`, `"متمردين"`, `"6"`, `"35"` | `str(cfg.get('monster_type', DEFAULT_MONSTER_TYPE)).lower().strip()`. Matched against `MONSTER_TYPES`. Fallback to `"rebels"`. | `config`, CLI `--type` / `-t` |
| `min_lv` | `int` | `1` | `1` to `35` (Invaders) / `1` to `5` (Rebels) | Converted via `int(cfg.get('min_lv', DEFAULT_MIN_LV))`. Clamped dynamically in `determine_safe_monster_level` to `[1, safe_ceiling]`. | `config`, CLI `--minlv` |
| `max_lv` | `int` | `30` | `1` to `35` (Invaders) / `1` to `5` (Rebels) | Converted via `int(cfg.get('max_lv', DEFAULT_MAX_LV))`. Clamped dynamically to `min(max_lv, max_map_npc_lv, player_can_kill_lv, combat_safe_lv)`. | `config`, CLI `--maxlv` |
| `max_marches` | `int` | `64` | `1` to `1000` | Converted via `int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))`. Controls outer dispatch loop ceiling. | `config`, CLI `--marches` / `-m` |
| `search_range` | `int` | `100` | `10` to `200` | Converted via `int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))`. Passed directly to `2011/3` search payload. | `config`, CLI `--range` |
| `formation_id` | `int` | `1` | `0` to `5` | Converted via `int(cfg.get('formation_id', DEFAULT_FORMATION_ID))`. If `0`, switches to automatic smart composition (`select_smart_combat_army`). | `config`, CLI `--formation` / `-f` |
| `troops_count` | `int` | `30000` | `0` to `500000` | Converted via `int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))`. If specified and not in `(0, 30000, 50000)`, overrides dynamic scaling; clamped to `[100, castle_capacity]`. | `config` |
| `busy_heroes` / `busy` | `List[int]` | `[]` | List of hero IDs | Parsed via `set(cfg.get('busy_heroes', cfg.get('busy', [])))`. Heroes in this set are bypassed during hero picking. | `config` (passed by coordinator) |
| `wait_for_queue` / `wait_queue` | `bool` | `False` | `True`, `False` | Parsed via `bool(cfg.get('wait_for_queue', cfg.get('wait_queue', False)))`. When `True`, task sleeps instead of terminating on `QUEUE_FULL`. | `config` |
| `wait_interval` | `float` | `15.0` | `5.0` to `60.0` | Parsed via `float(cfg.get('wait_interval', 15.0))`. Loop sleep duration during queue full polling. | `config` |
| `max_wait_cycles` | `int` | `35` | `1` to `100` | Parsed via `int(cfg.get('max_wait_cycles', 35))`. Maximum queue sleep iterations before giving up (`35 * 15s = 525s`). | `config` |

---

## 1.3 Detailed Function-by-Function & Path-by-Path Dissection

### 1. `get_unit_tier(army_id: int) -> int` (Lines 157–159)
- **Signature**: `get_unit_tier(army_id: int) -> int`
- **Logic**: Computes soldier tier by taking modulo 100: `int(army_id) % 100`.
- **Paths**:
  - Input `401` -> returns `1` (Tier 1 Infantry).
  - Input `510` -> returns `10` (Tier 10 Cavalry).
  - Input `712` -> returns `12` (Tier 12 Siege Cart).

### 2. `get_unit_power(army_id: int) -> float` (Lines 161–165)
- **Signature**: `get_unit_power(army_id: int) -> float`
- **Logic**: Extracts tier via `get_unit_tier(army_id)` and retrieves multiplier from `ARMY_TIER_POWER`.
- **Paths**:
  - `if tier in ARMY_TIER_POWER`: Returns predefined float (`1.0` to `11.0`).
  - `else`: Returns linear fallback extrapolation `1.0 + tier * 0.8`.

### 3. `calculate_castle_march_capacity(init_data: dict, heroes_info=None, chosen_hero_ids=None, learned_max=None) -> int` (Lines 171–190)
- **Signature**: `calculate_castle_march_capacity(init_data: dict, heroes_info: Optional[List[dict]] = None, chosen_hero_ids: Optional[List[int]] = None, learned_max: Optional[int] = None) -> int`
- **Logic**: Computes live castle march capacity by combining Drill Grounds building level, castle bonuses, and chosen hero attributes via `tasks/march_capacity.py`.
- **Execution Paths**:
  - `if not isinstance(init_data, dict)`: Returns fallback `1000`.
  - `else`: Calls `get_castle_march_capacity(init_data, chosen_heroes=chosen_hero_ids)`.
  - `if learned_max and learned_max > 0`: Clamps `cap = min(cap, learned_max)` to honor in-session capacity reduction learned after error `8035`.
  - Final return: `max(300, cap)`.

### 4. `_pick_combat_heroes(heroes: list, max_count: int = 2, busy: Set[int] = None, target_level: int = 1) -> List[int]` (Lines 196–262)
- **Signature**: `_pick_combat_heroes(heroes: list, max_count: int = 2, busy: Set[int] = None, target_level: int = 1) -> List[int]`
- **Purpose**: Selects optimal combat heroes (`5501xxx`) while strictly excluding gathering (`5502xxx`) and support (`5503xxx`) heroes.
- **Data Structures**: Three priority tiers (`tier1`, `tier2`, `tier3`).
- **Execution Trace & Paths**:
  - Loop over `hero in heroes`:
    - `if not isinstance(hero, dict)`: `continue`.
    - `hid = hero.get('id')`: `if not hid or hid in busy`: `continue`.
    - `if hero.get('status', {}).get('state', 0) != 0`: `continue` (hero currently deployed on march, assigned, or garrisoned).
    - `hid_str = str(hid)`:
      - `if hid_str.startswith('5502') or hid_str.startswith('5503')`: `continue` (strict exclusion of gathering and internal support heroes).
    - Skill inspection: Parses `hero.get('skillList', {})`. `has_combat_skills = True` if any skill ID starts with `'5610'` or `'5640'`.
    - Score calculation: `score = lv * 10 + star * 50`.
    - Tier categorization:
      - `if hid_str.startswith('5501') and has_combat_skills`: Appends `(hid, score)` to `tier1`.
      - `elif hid_str.startswith('5501')`: Appends `(hid, score)` to `tier2`.
      - `else`: Appends `(hid, score)` to `tier3`.
  - Sorting: `tier1.sort(reverse=True)`, `tier2.sort(reverse=True)`, `tier3.sort(reverse=True)`.
  - Merging: `chosen = [h[0] for h in tier1] + [h[0] for h in tier2]`.
  - Level-based filter: `if target_level < 28`: `chosen += [h[0] for h in tier3]`. (For targets level 28+, non-5501 heroes are strictly rejected).
  - Fallback logic: `if not chosen and target_level <= 15`: Scans all heroes for any available non-busy hero not starting with `5502`/`5503`.
  - Slicing: Returns `chosen[:max_count] if max_count else chosen`.

### 5. `get_monster_recommended_power(target_type: str, level: int) -> int` (Lines 268–290)
- **Signature**: `get_monster_recommended_power(target_type: str, level: int) -> int`
- **Execution Paths**:
  - Sanitization: `m_type = str(target_type).lower().strip()`, `lv = max(1, int(level))`.
  - Path 1: `m_type in ("rebels", "متمردين", "35")`:
    - `if lv in OFFICIAL_REBEL_FC`: Returns `OFFICIAL_REBEL_FC[lv]` (e.g. `lv 5 -> 7,518,000`).
    - `else`: Extrapolates `int(7518000 * (1 + (lv - 5) * 0.25))`.
  - Path 2: `m_type in ("invaders", "غزاة", "6")`:
    - Returns `OFFICIAL_NPC_FC.get(lv, 2040892)`.
  - Path 3: `m_type in ("stronghold", "معقل", "ملاجئ", "26")`:
    - `if lv <= 10`: Returns `500000 + lv * 150000`.
    - `elif lv <= 20`: Returns `2000000 + (lv - 10) * 250000`.
    - `else`: Returns `4500000 + (lv - 20) * 350000`.
  - Path 4: `else`: Returns `0`.

### 6. `calculate_smart_combat_troops(...) -> Tuple[int, int, str]` (Lines 293–371)
- **Signature**: `calculate_smart_combat_troops(target_type: str, target_level: int, castle_power: int = 0, user_troops_cfg: Optional[int] = None, max_safe_march: int = 170000) -> Tuple[int, int, str]`
- **Purpose**: Computes ideal troop dispatch count based on recommended enemy FC and castle readiness.
- **Execution Paths**:
  - Readiness check: Compares `castle_power / rec_power`:
    - `>= 1.25`: `"جاهزية ساحقة وتفوق كامل (pct%)"`
    - `>= 1.0`: `"مؤهل بنجاح (pct%)"`
    - `>= 0.75`: `"متكافئ مع الهدف (pct%)"`
    - `< 0.75`: `"قوة القلعة أقل من الموصى بها (pct%)"`
  - User override path: `if user_troops_cfg and user_troops_cfg not in (0, 30000, 50000)`:
    - Returns `(min(max_safe_march, max(100, user_troops_cfg)), rec_power, status_desc)`.
  - Dynamic scaling paths:
    - Rebel path (`rebels` / `35`):
      - `lv=1: 20000`, `lv=2: 55000`, `lv=3: 100000`, `lv=4: 140000`, `lv=5: max_safe_march`.
    - Invader path (`invaders` / `6`):
      - `lv=1: 200`, `lv=2: 500`, `lv=3: 1000`, `lv=4: 1800`, `lv=5: 2500`.
      - `lv<=10`: `4000 + (lv - 5) * 2000`.
      - `lv<=20`: `15000 + (lv - 10) * 4500`.
      - `lv<=28`: `60000 + (lv - 20) * 8000`.
      - `lv 29..35`: `max_safe_march`.
    - Stronghold path (`stronghold` / `26`):
      - `lv<=10: 60000`, `lv<=20: 110000`, `lv>20: min(max_safe_march, 165000)`.
    - Fallback: `needed = 80000`.
  - Clamping: `optimal_troops = min(max_safe_march, max(100, int(needed)))`.

### 7. `select_smart_combat_army(...) -> Tuple[List[Dict[str, int]], int, float, str]` (Lines 377–536)
- **Signature**: `select_smart_combat_army(available: Dict[int, int], target_type: str = "invaders", target_level: int = 1, max_capacity: int = 170000, user_troops_cfg: Optional[int] = None, heroes_info: Optional[List[dict]] = None, chosen_heroes: Optional[List[int]] = None) -> Tuple[List[Dict[str, int]], int, float, str]`
- **Algorithm**:
  - Troop segregation: Filters out traps `800 <= tid < 900` to prevent error `8062`. Segregates infantry `[400..499]`, cavalry `[500..599]`, archers `[600..699]`, and siege carts `[700..799]`.
  - Sorting: All branches sorted descending by unit ID (`tid`) so highest tiers (T12, T11...) are picked first.
  - Three-round quota allocation:
    - Round 1 (Tactical Quotas): 35% Infantry (shield), 35% Cavalry (charge), 30% Archers (ranged).
    - Round 2 (Combat Pool Spillover): If quota cannot be fulfilled by one branch, takes remaining needed troops from any combat branch descending by tier.
    - Round 3 (Siege Cart Fallback): Takes remaining needed troops from siege carts if combat troops are depleted.
  - Power & Anti-Suicide Evaluation:
    - Computes `army_power = sum(num * get_unit_power(tid))`.
    - Computes `hero_power_bonus = sum(hlv * 500 + hstar * 2500)` for chosen heroes.
    - `total_estimated_power = army_power + hero_power_bonus`.
    - Evaluation branch 1 (`lv >= 28 and target_fc > 0`):
      - `if total_estimated_power < (target_fc * 0.45)`: `safety_status = "SUICIDE_RISK"`.
      - `elif total_estimated_power < (target_fc * 1.2)`: `safety_status = "RISKY"`.
      - `else`: `safety_status = "GUARANTEED_WIN"`.
    - Evaluation branch 2 (`target_fc > 0`):
      - `>= 3.0 * target_fc`: `"GUARANTEED_WIN"`.
      - `>= 1.5 * target_fc`: `"SAFE"`.
      - `>= 0.7 * target_fc`: `"RISKY"`.
      - `< 0.7 * target_fc`: `"UNDERPOWERED"`.
  - Returns `(army_list, total_troops, total_estimated_power, safety_status)`.

### 8. `select_combat_army(available: Dict[int, int], needed_count: int = DEFAULT_TROOPS_COUNT) -> List[Dict[str, int]]` (Lines 542–626)
- **Signature**: `select_combat_army(available: Dict[int, int], needed_count: int = DEFAULT_TROOPS_COUNT) -> List[Dict[str, int]]`
- **Logic**: Balanced equal-quota troop selection among infantry, cavalry, archers, and fallback carts. Traps `800 <= tid < 900` are strictly excluded.

### 9. `select_combat_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]` (Lines 633–658)
- **Signature**: `select_combat_pet(conn: GameConnection, used_pets: Set[int]) -> List[int]`
- **Logic**: Reads `conn.init_data['petCtrl']['pets']`. Iterates through pet IDs, filters out `used_pets`, sorts by `lv` descending, picks the highest-level pet, appends to `used_pets`, and returns `[chosen_pet]`.

---

## 1.4 Detailed Trace of `MonsterTask` Methods & Line-by-Line Paths

### `MonsterTask.__init__(self, conn: GameConnection, config: dict = None)` (Lines 670–678)
- Instantiates task state: `_heroes = []`, `_busy = set()`, `_used_army = {}`, `_used_pets = set()`, `_learned_max_march_troops = None`, `_learned_max_npc_level = None`, `_exclude_mgr = _get_exclude_manager()`.

### `MonsterTask.on_start(self)` (Lines 680–688)
- Gate/init synchronization loop: Iterates 20 cycles with `asyncio.sleep(0.5)`. Breaks if `conn._gate.heroes` or `conn.init_data` is present.
- Awaits `self._load_heroes()`.

### `MonsterTask._load_heroes(self)` (Lines 689–706)
- Reads `conn.init_data.get('heroCtrl')`.
  - `if isinstance(hctrl, list) and hctrl`: `self._heroes = list(hctrl)`.
  - `else`: Fallback scans `conn.init_data.get('armyCtrl', {}).get('compileHeros', {})` values, constructing mock hero dicts with `status.state = 0`.

### `MonsterTask._check_rebel_prerequisites(self) -> Tuple[bool, str]` (Lines 709–749)
- **Condition 1 (Alliance Check)**:
  - Extracts alliance ID from `allianceCtrl.memberinfo.minfo.aid`.
  - If 0, checks `allianceCtrl.allianceInfo.aid`.
  - If 0 and `len(allianceCtrl) > 5`, infers `alliance_id = 1`.
  - If 0, checks `lord.alliance`.
  - `if alliance_id == 0`: Returns `(False, "مهاجمة نخبة المتمردين تتطلب الانضمام إلى تحالف...")`.
- **Condition 2 (Hall of War Check - Building ID 115)**:
  - Scans `cityCtrl.blist`. Checks each building where `bid == '115'`.
  - Extracts building level `lv`.
  - `if hall_of_war_lv == 0`: Returns `(False, "مهاجمة نخبة المتمردين تتطلب بناء 'قاعة الحرب' (مبنى 115)...")`.
- If both conditions met: Returns `(True, "")`.

### `MonsterTask.determine_safe_monster_level(...) -> Tuple[int, int, str]` (Lines 753–903)
- Validates target type (`rebels` vs `invaders`).
- Map level limits: Reads `kingdomMapCtrl.maxMapNpcLevel` (default 35 for invaders, 5 for rebels).
- First-kill unlock: Reads `kingdomMapCtrl.maxNpcLevel` or `lordInfoCtrl.npc.killMaxLevel`. Computes `player_can_kill_lv = player_killed_max + 1`.
- Learned session ceiling: If `_learned_max_npc_level` exists, clamps `player_can_kill_lv = min(player_can_kill_lv, self._learned_max_npc_level)`.
- Capacity & Castle Troops calculation:
  - Calls `calculate_castle_march_capacity`.
  - Reads `armyCtrl.totalArmy`. If empty, queries fallback network command `1005/1` (Lines 813–819).
  - Sorts available non-trap units by unit power descending, fills march capacity, and calculates `total_march_troops_power`.
  - Adds combat hero power bonus (`hlv * 500 + hstar * 2500`).
  - Total march power: `max_march_power = total_march_troops_power + hero_power`.
- Safe ceiling resolution:
  - For Rebels: Compares `max_march_power` against `OFFICIAL_REBEL_FC` (requires `>= 40%` for lv 1, `>= 70%` for lv 2–5). Clamps `safe_ceiling = min(req_max_lv, 5, combat_safe_lv)`.
  - For Invaders: Compares `max_march_power` against `OFFICIAL_NPC_FC` (requires `>= 40%` for lv <= 3, `>= 70%` for higher). Clamps `safe_ceiling = min(req_max_lv, max_map_npc_lv, player_can_kill_lv, combat_safe_lv)`.
  - Computes `safe_floor = min(req_min_lv, safe_ceiling)`.
  - Returns `(safe_floor, safe_ceiling, reason_str)`.

### `MonsterTask.run(self) -> TaskResult` (Lines 907–1114)
- **Pre-execution Phase**:
  - Unpacks configuration: `monster_type`, `min_lv`, `max_lv`, `max_marches`, `search_range`, `formation_id`, `troops_cfg`.
  - Rebel Prerequisite check: If `map_type == 35`, calls `_check_rebel_prerequisites()`. If failing, immediately returns `TaskResult.fail("🛑 ...", stop_reason="REBEL_PREREQUISITE_FAILED")`.
  - Determines safe levels via `determine_safe_monster_level()`. If requested levels exceed safe range, logs clamp and overrides `min_lv` and `max_lv`.
  - Initializes loop state: `sent_count = 0`, `consecutive_errors = 0`, `_busy`, `_used_army`, `_used_pets`, `wait_cycles = 0`, `cmd_opting_retries = 0`.
- **Main Dispatch Loop (`while sent_count < max_marches`)**:
  - March availability probe: Calls `get_available_marches_count(force_sync=True)`. If 0, breaks with `last_result = "QUEUE_FULL"`.
  - Calls `_send_one_attack(map_type, sub_type, min_lv, max_lv, search_range, formation_id, troops_cfg)`.
  - **Result Branching**:
    - `case "SUCCESS"`: Increments `sent_count`, resets error counters, sleeps randomized interval `[3.5, 5.5]` seconds.
    - `case "QUEUE_FULL"`:
      - If `not wait_for_queue` or `wait_cycles >= max_wait_cycles`: breaks immediately.
      - If `wait_for_queue`: polls `get_active_marches_count()` every `wait_interval` (15s) up to `max_wait_cycles` (35 cycles). If a queue frees up, clears `_busy` and `_used_army`, reloads heroes, and continues dispatch loop.
    - `case "STAMINA_EMPTY"`: Breaks loop immediately.
    - `case "HERO_BUSY" | "NO_HEROES"`:
      - Checks if alternative combat heroes (`5501xxx`) exist in castle. If `HERO_BUSY` and alternative available, continues loop immediately to try next hero.
      - If waiting enabled, sleeps `wait_interval`, clears `_busy`, and retries.
      - Otherwise breaks loop.
    - `case "NO_ARMY"`: If waiting enabled, sleeps `wait_interval` and retries; otherwise breaks.
    - `case "SUICIDE_RISK"`: Breaks immediately to protect troops from annihilation.
    - `case "NPC_LEVEL_LOCKED"`: Clamps `max_lv = self._learned_max_npc_level` and immediately retries with downgraded target level.
    - `case "CMD_OPTING" | "16001" | "CMD_OPTING_FAILED"`:
      - Increments `cmd_opting_retries`. If `<= 2`, sleeps random `[10.0, 16.0]` seconds to release server lock and retries.
      - If `> 2`, breaks loop.
    - `case "NO_TARGET" | "TARGET_OCCUPIED"`: Increments `consecutive_errors`. If `>= 4`, breaks; otherwise sleeps `[2.2, 4.0]` seconds.
    - `else`: Increments `consecutive_errors`. If `>= 3`, breaks; otherwise sleeps `[2.2, 4.0]` seconds.
- **Post-Loop Termination & `TaskResult` Construction**:
  - If `sent_count > 0`: Returns `TaskResult.ok(sent=sent_count, queue_full=(last_result == "QUEUE_FULL"), stop_reason=last_result)`.
  - Specific failure mappings:
    - `"NPC_LEVEL_LOCKED"` -> `TaskResult.fail("🛑 مستوى الهدف مغلق باللعبة...", stop_reason="NPC_LEVEL_LOCKED")`.
    - `"SUICIDE_RISK"` -> `TaskResult.fail("🛑 تم إلغاء الهجوم لحماية القوات من الانتحار...", stop_reason="SUICIDE_RISK")`.
    - `"QUEUE_FULL"` -> `TaskResult.fail("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل...", queue_full=True, stop_reason="QUEUE_FULL")`.
    - `"STAMINA_EMPTY"` -> `TaskResult.fail("🛑 نفدت طاقة اللورد بالكامل", stop_reason="STAMINA_EMPTY")`.
    - `"NO_ARMY"` -> `TaskResult.fail("🛑 نفدت القوات المتاحة بالقلعة", stop_reason="NO_ARMY")`.
    - `"NO_HEROES"` / `"HERO_BUSY"` -> `TaskResult.fail("🛑 لا يتوفر أبطال متاحون بالقلعة", stop_reason="NO_HEROES")`.
    - `"NO_TARGET"` / `"TARGET_OCCUPIED"` -> `TaskResult.fail("⚠️ لم يتم العثور على أهداف متاحة...", stop_reason="NO_TARGET")`.
    - Default: `TaskResult.fail("لم يتم إرسال أي مسيرة هجوم...", retry_after=120, stop_reason=str(last_result))`.

### `MonsterTask._send_one_attack(...) -> str` (Lines 1117–1575)
- **Step 1: Coordinates & Kingdom Discovery**:
  - `cx, cy = await self.get_castle_coords()`. If missing, returns `"ERROR"`.
  - `kingdom_id = await self.get_kingdom_id()`.
- **Step 2: Map Search Query (`2011/3`)**:
  - Obtains `exclude_map = await self._exclude_mgr.get_exclude_map(self.uid, kingdom_id=kingdom_id)`.
  - Sends network query:
    - `cmd: "2011", subcmd: "3"`
    - Payload: `{"mapType": map_type, "num": 5, "subType": sub_type, "y": cy, "x": cx, "exclude": exclude_map, "minLv": min_lv, "maxLv": max_lv, "range": search_range}`.
  - Filters candidates: `candidates = [c for c in raw_candidates if str(c.get('id', '')) not in exclude_map]`.
  - `if not candidates`: Returns `"NO_TARGET"`.
- **Step 3: Troops & Formation Extraction**:
  - `available = await self.get_available_troops()`.
  - `form_heroes, form_pets, form_rune_pages, form_army_dict = await self.get_formation(formation_id)`.
- **Step 4: Hero Selection Hierarchy**:
  - Checks if `form_heroes` are available and idle (`state == 0`, not in `_busy`).
  - If 2 available: Uses both.
  - If 1 available: Uses that 1, fills second slot via `_pick_combat_heroes`.
  - If 0 available: Calls `_pick_combat_heroes(self._heroes, max_count=2, busy=self._busy, target_level=target_lv)`.
  - If no war heroes found: Emergency fallback picks any idle non-gathering hero. If none, returns `"NO_HEROES"`.
- **Step 5: March Army Composition & Suicide Guard**:
  - Calculates live castle march capacity: `castle_capacity = calculate_castle_march_capacity(...)`.
  - If saved formation exists (`formation_id > 0` and `form_army_dict`):
    - Scales down proportionally if `total_form_req > castle_capacity`.
    - Deducts units from `available`.
    - If formation is empty in castle: Calls `select_smart_combat_army`.
    - If formation is weak (`power_ratio < min_safe_ratio`): Automatically reinforces deficit up to `castle_capacity` using `select_smart_combat_army`.
    - If deficit still underpowered (`new_ratio < 0.45` for high levels): Flags `safety_status = "SUICIDE_RISK"`.
  - If no saved formation (`formation_id <= 0`): Calls `select_smart_combat_army`.
  - Anti-suicide check: `if safety_status == "SUICIDE_RISK"`: Returns `"SUICIDE_RISK"`.
  - Enforces capacity ceiling via `enforce_safe_march_troops(army_list, castle_capacity)`.
  - Empty army check: If `army_list` is empty, checks active marches. If active marches >= 1, returns `"QUEUE_FULL"`; else returns `"NO_ARMY"`.
- **Step 6: Pets & Runes Assembly**:
  - Pets: Uses `form_pets` if valid, otherwise calls `select_combat_pet(self.conn, set())`.
  - Runes: Extracts from `form_rune_pages` (defaulting to `[1]`).
- **Step 7: Target Iteration & March Dispatch (`1007/2`)**:
  - Iterates through `target in candidates`:
    - Calls `await self._exclude_mgr.reserve(self.uid, target_id, kingdom_id=kingdom_id)`.
    - Constructs payload:
      - **If Rebel (`mapType == 35`)**:
        - `cmd: "1007", subcmd: "2"`
        - Payload:
          ```json
          {
            "needSend": true,
            "mapId": int(kingdom_id),
            "moveLineType": 7,
            "matrixType": 1,
            "runePages": rune_pages_list,
            "needArmyList": {},
            "heros": chosen_heroes,
            "pets": pets_list,
            "data": {
              "data": {
                "mainInstanceType": 35,
                "massTime": 300
              },
              "to": { "y": int(ty), "x": int(tx), "id": str(target_id) },
              "army": army_list
            }
          }
          ```
      - **If Invader (`mapType == 6`)**:
        - `cmd: "1007", subcmd: "2"`
        - Payload:
          ```json
          {
            "needSend": false,
            "mapId": int(kingdom_id),
            "moveLineType": 1,
            "matrixType": 1,
            "runePages": rune_pages_list,
            "heros": chosen_heroes,
            "pets": pets_list,
            "data": {
              "data": {},
              "to": { "y": int(ty), "x": int(tx), "id": str(target_id) },
              "army": army_list
            }
          }
          ```
    - Awaits response `r_attack = await self.conn.query('1007', '2', attack_payload)`.
    - If `not r_attack`: Releases reservation `self._exclude_mgr.release(...)` and continues to next candidate.
    - Evaluates error code `err = str(r_attack.get('err', '0'))`:
      - Handled across the full 20 error code specification (detailed in Section 1.6).


## 1.5 Network Commands & Memory Keys (`init_data`) Reference in `monster.py`

### Network Commands Table
| Command / Subcommand | Direction | Purpose | Exact Payload Structure | Expected Response / Data Extracted |
|---|---|---|---|---|
| `2011 / 3` | Outbound (Client -> Server) | Search map for Invaders or Rebels | `{"mapType": int, "num": 5, "subType": int, "y": int, "x": int, "exclude": dict, "minLv": int, "maxLv": int, "range": int}` | `{"result": [{"id": "...", "x": int, "y": int, "level": int}, ...]}` |
| `1007 / 2` | Outbound (Client -> Server) | Dispatch March (Solo or Mass/Rally) | `{"needSend": bool, "mapId": int, "moveLineType": int, "matrixType": 1, "runePages": [...], "heros": [...], "pets": [...], "data": {"data": {...}, "to": {"x": int, "y": int, "id": str}, "army": [{"id": int, "num": int}, ...]}}` | `{"err": "0"}` on success, or non-zero error string (e.g. `'8004'`, `'8035'`, `'8027'`). |
| `1005 / 1` | Outbound (Client -> Server) | Fallback Army Info Query | `{}` | `{"data": {"totalArmy": {unit_id: count, ...}}}` |
| `1007 / 1000` | Outbound (Client -> Server) | Synchronize Local Queues (via BaseTask) | `{}` | Local queue sync packet triggering `NOTIFY_LOCAL_QUEUE_SYNC` |

### Memory Keys (`init_data`) Table
| Top-Level Key | Sub-Keys & Paths | Data Type | Usage & Purpose in `monster.py` |
|---|---|---|---|
| `heroCtrl` | Array of hero dicts `[{"id": int, "lv": int, "star": int, "status": {"state": int}, "skillList": {...}}]` | `List[Dict]` | Live hero pool. Checked for ID, level, star, busy state (`state != 0`), combat skills (`5610xxx`, `5640xxx`). |
| `armyCtrl` | `totalArmy` (`{str(id): str(cnt)}`), `compileHeros`, `compilePets`, `compileArmy` | `Dict` | Live available soldier counts by tier; fallback hero references; saved formation data. |
| `cityCtrl` | `cinfo.pos` (`{"x": int, "y": int}`), `blist` (`[{"binfo": {"bid": "115", "lv": int}}]`) | `Dict` | Castle coordinates; Hall of War building level verification for rebel rallies. |
| `kingdomMapCtrl` | `maxMapNpcLevel`, `maxNpcLevel`, `mapId`, `kingdomId` | `Dict` | World map maximum invader level ceiling; lord's historical first-kill record for level gating. |
| `lordInfoCtrl` | `npc.killMaxLevel`, `base.partition`, `base.health` | `Dict` | Player's recorded monster kill level ceiling; kingdom partition ID. |
| `allianceCtrl` | `memberinfo.minfo.aid`, `allianceInfo.aid` | `Dict` | Player alliance membership verification (mandatory for rebel mass rallies). |
| `lord` | `alliance`, `partition` | `Dict` | Fallback player metadata for alliance ID and kingdom ID. |
| `petCtrl` | `pets` (`{str(pid): {"lv": int, ...}}`) | `Dict` | Combat pet inventory; sorted by level descending. |

---

## 1.6 Server Response & Error Code Behavior Matrix for `tasks/monster.py`

This table documents how `tasks/monster.py` handles all 20 specified server error codes, detailing `ExcludeManager` interactions (`reserve`, `confirm`, `release`), retry mechanisms, and internal state modifications.

| Code | Game Protocol Definition | Exact Code Handling in `monster.py` | ExcludeManager Action | Retry Logic & State Updates | Red Team Vulnerability / Flaw |
|---|---|---|---|---|---|
| `8004` | `Err_MAP_QUEUE_OUT_LIMIT` | Lines 1499–1502: Explicitly caught | `release(uid, target_id)` | Returns `"QUEUE_FULL"`. If `wait_for_queue` enabled, waits up to `35 * 15s`. | `release()` frees target for immediate re-search by other tasks, which may immediately fail with 8004 again. |
| `9007004`| Alternative queue full code | Lines 1499–1502: Grouped with 8004 | `release(uid, target_id)` | Same as 8004. | Same as 8004. |
| `8009` | `Err_SOLDIER_NOT_ENOUGH` | Lines 1503–1512: Explicitly caught | `release(uid, target_id)` | Checks active marches. If active >= 1, returns `"QUEUE_FULL"`; else `"NO_ARMY"`. | Target is released immediately. If soldier counts desync, loops until loop limit. |
| `8035` | `Err_QUEUE_SOLDIER_LIMIT` | Lines 1522–1548: Explicitly caught | `confirm()` if retry succeeds; `release()` if retry fails | Learns `_learned_max_march_troops = int(total * 0.82)`. Rescales `army_list` and performs immediate inline retry. | In-line retry causes double query burst; if second attempt fails with 8035, reduces by 75% but does not retry until next candidate. |
| `8032` | `Err_ENERGY_NOT_ENOUGH` | Lines 1513–1516: Grouped | `release(uid, target_id)` | Returns `"STAMINA_EMPTY"`. Immediately terminates `run()` loop. | Target released. Task does not consume bag stamina potions or attempt stamina recovery. |
| `10002`| Stamina empty variant 1 | Lines 1513–1516: Grouped | `release(uid, target_id)` | Returns `"STAMINA_EMPTY"`. Breaks loop. | Same as 8032. |
| `10003`| Stamina empty variant 2 | Lines 1513–1516: Grouped | `release(uid, target_id)` | Returns `"STAMINA_EMPTY"`. Breaks loop. | Same as 8032. |
| `9007020`| `Err_HERO_IN_MARCH` | Lines 1517–1521: Explicitly caught | `release(uid, target_id)` | Adds `chosen_heroes` to `self._busy`. Returns `"HERO_BUSY"`. If alternative hero available, tries next hero immediately. | If both heroes busy and no alternatives, sleeps `wait_interval` or breaks. Target released. |
| `8014` | `Err_TARGET_PEACE_SHIELD` | Handled by fallback `err.startswith('80')` (Lines 1566–1569) | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop to next candidate. | Incorrectly treats peace shield target as occupied, excluding it for 4 hours. |
| `8015` | `Err_TARGET_CANNOT_ATTACK`| Handled by fallback `err.startswith('80')` (Lines 1566–1569) | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop to next candidate. | Excludes target permanently even if restriction was temporary. |
| `8027` | `Err_MAP_QUEUE_NPC_LEVEL_OUT` | Lines 1549–1558: Explicitly caught | `release(uid, target_id)` | Learns `_learned_max_npc_level = target_level - 1`. Returns `"NPC_LEVEL_LOCKED"`. Loop clamps `max_lv` and retries. | Target released. Correctly downgrades search level, but does not update `lordInfoCtrl` memory. |
| `8037` | `Err_MARCH_DISTANCE_LIMIT`| Handled by fallback `err.startswith('80')` (Lines 1566–1569) | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Target excluded even though user search range was simply configured too wide. |
| `8041` | `Err_MASS_NOT_IN_ALLIANCE`| Handled by fallback `err.startswith('80')` (Lines 1566–1569) | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Critical bug: Excludes the rebel boss target permanently instead of terminating task with prerequisite failure. |
| `8042` | `Err_MASS_HALL_NOT_BUILT` | Handled by fallback `err.startswith('80')` (Lines 1566–1569) | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Critical bug: Excludes target instead of identifying that Hall of War is missing. |
| `8046` | `Err_MASS_TIME_INVALID` | Handled by fallback `err.startswith('80')` (Lines 1566–1569) | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Hardcoded `massTime: 300` caused error, but target is blamed and excluded. |
| `8060` | `Err_TARGET_OCCUPIED` | Lines 1566–1569: Explicitly caught | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Correct behavior: Target confirmed occupied. |
| `8062` | `Err_TARGET_BATTLE_BUSY` | Lines 1566–1569: Explicitly caught | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | If caused by invalid trap units in payload, target is falsely excluded. |
| `8063` | `Err_TARGET_DISAPPEARED` | Lines 1566–1569: Explicitly caught | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Correct behavior: Target defeated or despawned. |
| `8095` | `Err_INVALID_FORMATION` | Handled by fallback `err.startswith('80')` (Lines 1566–1569) | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Bad formation payload causes target exclusion instead of formation reconfiguration. |
| `16001`| `Err_CMD_OPTING` | Lines 1559–1565: Explicitly caught | `release(uid, target_id)` | Returns `"CMD_OPTING"`. Outer loop waits `10-16s` and retries up to 2 times. | After 2 retries, task aborts completely. Releases target. |

---

## 1.7 In-Depth Red Team Critique for `tasks/monster.py`

### 1. The Fallback Blanket Exclusion Flaw (`err.startswith('80')`)
In line 1566:
```python
elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.startswith('80') and err not in ('8004', '8009', '8032', '8027', '8035')):
    await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
```
Any server error starting with `80` (such as `8041` Mass Not in Alliance, `8042` Hall of War Not Built, `8046` Invalid Mass Time, `8095` Invalid Formation, `8037` Distance Limit) is falsely categorized as "Target Occupied", invoking `exclude_mgr.confirm()` and poisoning `exclude_history.json` for 4 hours. The target is completely blameless, while the client payload or castle prerequisite is broken.

### 2. Rebel Mass Rally 300-Second Hardcoding & Queue Stall
Lines 1450–1453:
```python
"data": {
    "data": {
        "mainInstanceType": 35,
        "massTime": 300
    },
    ...
}
```
Rebel mass rallies are hardcoded to `massTime: 300` (5 minutes). Unlike solo attacks where the march departs immediately, a mass rally locks a march queue and 2 heroes inside the castle for 300 seconds before marching. If `max_marches > 1`, `monster.py` will attempt to launch subsequent marches. If queues are filled with waiting rallies, the bot enters queue sleep cycles (`wait_interval = 15s`) for hundreds of seconds, stalling the coordinator pipeline.

### 3. Hero State Desynchronization across Mass Rallies
When a mass rally is created, the heroes are assigned to the rally waiting room. The server updates `heroCtrl[i].status.state` to busy, but `conn.init_data` is only updated via async socket push packets. If push packets are delayed or dropped, `_load_heroes()` reads stale memory, selects the same heroes for the next rally, and receives error `9007020`. Although `_busy.add(hid)` catches this, `_busy` is cleared completely when `queue_freed` triggers (line 1012), causing re-selection of heroes still locked in the ongoing rally.

### 4. Inline 8035 Retry Double-Billing and Race Condition
When code `8035` occurs (Lines 1522–1548), `monster.py` reduces troops by 18% and executes an immediate inline query `await self.conn.query('1007', '2', attack_payload)`. If the second query also fails or if network latency occurs, this second query is sent outside the standard spacing sleep (`random.uniform(3.5, 5.5)`), creating a rapid double-request burst that triggers server anti-flood error `16001` (`Err_CMD_OPTING`).

---

## 1.8 Inventory of Duplicated Helper Functions in `monster.py`

| Helper Routine in `monster.py` | Lines | Functionality | Re-implemented / Duplicated In | Unification Target in `base_task.py` |
|---|---|---|---|---|
| `get_unit_tier` & `get_unit_power` | 157–165 | Unit tier and combat power multiplier | `abra.py` (65–67), `base_task.py` (1041–1052) | `BaseTask.get_unit_power(tid)` |
| `calculate_castle_march_capacity` | 171–190 | Live march capacity calculation with learned reduction | `abra.py` (64, 520), `stronghold.py` (29, 301) | `BaseTask.calculate_march_capacity()` |
| `_pick_combat_heroes` | 196–262 | Hero filtering, sorting by skills/stars, excluding gatherers | `abra.py` (62, 364–422), `base_task.py` (698–853) | `BaseTask.get_combat_heroes()` |
| `select_combat_pet` | 633–658 | Highest level pet selection | `base_task.py` (855–909), `abra.py` (line 338) | `BaseTask.select_combat_pet()` |
| `select_combat_army` | 542–626 | Balanced troop selection across infantry, cavalry, archers | `abra.py` (63, 588, 597), `base_task.py` (1054–1141) | `BaseTask.compose_balanced_army()` |
| `_load_heroes` | 689–706 | Memory extraction of heroCtrl with armyCtrl fallback | `stronghold.py` (68–85), `abra.py` (196–213) | `BaseTask.load_heroes()` |
| Queue waiting loop | 988–1018 | Loop polling active marches with sleep interval | `stronghold.py` (150–179), `abra.py` (894–908) | `BaseTask.wait_for_free_queue()` |
| Map search packet formatting | 1136–1146 | Assembling `2011/3` search payload with exclude map | `stronghold.py` (266–279), `gather.py`, `ruins.py` | `BaseTask.search_map_targets()` |
| March payload assembly | 1440–1481 | Assembling `1007/2` march structure | `stronghold.py` (353–372), `abra.py` (826–843) | `BaseTask.dispatch_march()` |


---

# Part II: Deep Surgical Dissection of `tasks/stronghold.py`

## 2.1 Module Metadata, Architectural Role & Imports

- **Path**: `tasks/stronghold.py`
- **Total Lines**: 507 lines
- **Role**: Dispatches exterior attack / occupation marches against World Strongholds / Shelters (`mapType=26`, `subType=0`, `moveLineType=3`, `judianState=1`).
- **Dependencies & Imports**:
  - `asyncio`, `json`, `logging`, `random`, `sys`, `os`, `typing` (`Any`, `Dict`, `List`, `Optional`, `Set`, `Tuple`)
  - `tasks.base_task.BaseTask`, `tasks.base_task.TaskResult`
  - `game_client.GameConnection`
  - `tasks.monster.get_monster_recommended_power`, `tasks.monster.calculate_smart_combat_troops`
  - `tasks.exclude_manager.get_manager as _get_exclude_manager`
  - `tasks.march_capacity.get_castle_march_capacity`, `tasks.march_capacity.enforce_safe_march_troops`, `tasks.march_capacity.record_learned_march_capacity`

### Global Constants Defined at Module Level:
- `DEFAULT_MIN_LV = 1`: Default minimum stronghold level.
- `DEFAULT_MAX_LV = 35`: Default maximum stronghold level.
- `DEFAULT_MAX_MARCHES = 2`: Default maximum stronghold marches to dispatch.
- `DEFAULT_SEARCH_RANGE = 100`: Search radius on the kingdom map.
- `DEFAULT_FORMATION_ID = 1`: Preferred formation ID (1..5).
- `DEFAULT_TROOPS_COUNT = 30000`: Fallback troop count when formation is empty or absent.

---

## 2.2 Complete Table of Inputs, Configurations, Defaults & Validation Logic

| Config Parameter | Type | Default Value | Accepted / Valid Values | Validation & Sanitization Logic | Source / Ingestion Point |
|---|---|---|---|---|---|
| `min_lv` | `int` | `1` | `1` to `35` | `int(cfg.get('min_lv', DEFAULT_MIN_LV))`. Passed directly to `2011/3` search query payload. | `config`, CLI `--minlv` |
| `max_lv` | `int` | `35` | `1` to `35` | `int(cfg.get('max_lv', DEFAULT_MAX_LV))`. Passed directly to `2011/3` search query payload. | `config`, CLI `--maxlv` |
| `max_marches` | `int` | `2` | `1` to `10` | `int(cfg.get('max_marches', DEFAULT_MAX_MARCHES))`. Controls loop termination (`sent_count < max_marches`). | `config`, CLI `--marches` / `-m` |
| `search_range` | `int` | `100` | `10` to `200` | `int(cfg.get('search_range', DEFAULT_SEARCH_RANGE))`. Passed directly to `2011/3` search query. | `config`, CLI `--range` |
| `formation_id` | `int` | `1` | `0` to `5` | `int(cfg.get('formation_id', DEFAULT_FORMATION_ID))`. Forwarded to `BaseTask.get_march_army`. | `config`, CLI `--formation` / `-f` |
| `troops_count` | `int` | `30000` | `0` to `500000` | `int(cfg.get('troops_count', DEFAULT_TROOPS_COUNT))`. Forwarded as `fallback_count` to `BaseTask.get_march_army`. | `config` |
| `busy_heroes` / `busy` | `List[int]` | `[]` | List of hero IDs | Parsed via `set(cfg.get('busy_heroes', cfg.get('busy', [])))`. Passed to `get_combat_heroes`. | `config` |
| `wait_for_queue` / `wait_queue` | `bool` | `False` | `True`, `False` | Parsed via `bool(cfg.get('wait_for_queue', cfg.get('wait_queue', False)))`. Controls queue-full waiting behavior. | `config` |
| `wait_interval` | `float` | `15.0` | `5.0` to `60.0` | Parsed via `float(cfg.get('wait_interval', 15.0))`. Duration of sleep per queue-full polling cycle. | `config` |
| `max_wait_cycles` | `int` | `40` | `1` to `100` | Parsed via `int(cfg.get('max_wait_cycles', 40))`. Max wait iterations (`40 * 15s = 600s`). | `config` |

---

## 2.3 Comprehensive Function-by-Function & Line-by-Line Dissection

### 1. `StrongholdTask.__init__(self, conn: GameConnection, config: dict = None)` (Lines 51–58)
- **Signature**: `StrongholdTask.__init__(self, conn: GameConnection, config: dict = None)`
- **Line-by-Line Execution**:
  - Line 52: Calls `super().__init__(conn, config)`. Sets task name to `"stronghold"`.
  - Line 53: Initializes `self._heroes: list = []`.
  - Line 54: Initializes `self._busy: Set[int] = set()`.
  - Line 55: Initializes `self._used_army: Dict[int, int] = {}`.
  - Line 56: Initializes `self._used_pets: Set[int] = set()`.
  - Line 57: Obtains singleton exclude manager: `self._exclude_mgr = _get_exclude_manager()`.

### 2. `StrongholdTask.on_start(self)` (Lines 59–67)
- **Signature**: `StrongholdTask.on_start(self)`
- **Line-by-Line Execution**:
  - Lines 60–65: Initialization barrier loop: iterates 20 times with `asyncio.sleep(0.5)`. Breaks early if `self.conn._gate.heroes` or `self.conn.init_data` is populated.
  - Line 66: Awaits `self._load_heroes()`.

### 3. `StrongholdTask._load_heroes(self)` (Lines 68–85)
- **Signature**: `StrongholdTask._load_heroes(self)`
- **Line-by-Line Execution**:
  - Line 70: Reads `self.conn.init_data.get('heroCtrl')`.
  - Lines 71–73: `if isinstance(hctrl, list) and hctrl`: sets `self._heroes = list(hctrl)` and returns immediately.
  - Lines 76–85: Fallback path: Reads `armyCtrl.compileHeros` from `init_data`. For each hero ID, constructs mock dict `{'id': int_hid, 'status': {'state': 0}, 'skillList': {}}` to allow hero selection if `heroCtrl` is unpopulated.

### 4. `StrongholdTask.run(self) -> TaskResult` (Lines 88–250)
- **Signature**: `StrongholdTask.run(self) -> TaskResult`
- **Execution Trace & Decision Branches**:
  - Lines 89–96: Extracts configuration keys: `min_lv`, `max_lv`, `max_marches`, `search_range`, `formation_id`, `troops_cfg`.
  - Line 97: Logs initialization: `"🏰 [المعقل] بدء الهجوم (لفل: {min_lv}-{max_lv} | المطلوب: {max_marches})"`.
  - Lines 99–100: Hero check: `if not self._heroes`: awaits `self._load_heroes()`.
  - Lines 102–113: Sets loop trackers: `sent_count = 0`, `consecutive_errors = 0`, `_busy`, `_used_army`, `_used_pets`, `wait_for_queue`, `wait_interval`, `max_wait_cycles = 40`, `wait_cycles = 0`, `cmd_opting_retries = 0`, `last_result = None`.
  - Line 115: Enters outer loop: `while sent_count < max_marches`.
    - Lines 119–125: March availability probe: `before_avail = await self.get_available_marches_count(force_sync=True)`.
      - `if before_avail == 0`: Logs queue saturation, sets `last_result = "QUEUE_FULL"`, and breaks loop.
    - Line 127: Calls `result_code = await self._send_one_stronghold(min_lv, max_lv, search_range, formation_id, troops_cfg)`.
    - Line 128: Sets `last_result = result_code`.
    - **Branch Evaluation on `result_code`**:
      - **Lines 130–138 (`result_code == "SUCCESS"`)**:
        - Increments `sent_count += 1`.
        - Resets `consecutive_errors = 0`, `cmd_opting_retries = 0`, `wait_cycles = 0`.
        - If more marches needed: sleeps humanized interval `random.uniform(4.5, 7.5)` seconds.
      - **Lines 139–179 (`result_code == "QUEUE_FULL"`)**:
        - If `not wait_for_queue` or `wait_cycles >= max_wait_cycles`: breaks loop.
        - If waiting enabled: enters inner polling loop. Sleeps `wait_interval` (15s) per cycle. Queries `cur_act = await self.get_active_marches_count()`. If `cur_act < max_q`: sets `queue_freed = True` and breaks inner loop.
        - If `queue_freed`: clears `_busy` and `_used_army`, reloads heroes via `await self._load_heroes()`, and continues outer loop.
        - Else: logs timeout and breaks outer loop.
      - **Lines 180–197 (`result_code in ("HERO_BUSY", "NO_HEROES")`)**:
        - Checks available combat heroes: `avail_combat_heroes = [h for h in self._heroes if ... startsWith('5501')]`.
        - If `result_code == "HERO_BUSY"` and `avail_combat_heroes`: logs immediate substitution and continues loop without sleep.
        - If waiting enabled: sleeps `wait_interval`, clears `_busy` and `_used_army`, reloads heroes, and retries.
        - Else: logs warning and breaks loop.
      - **Lines 198–207 (`result_code == "NO_ARMY"`)**:
        - If waiting enabled: sleeps `wait_interval`, clears `_busy` and `_used_army`, and retries.
        - Else: breaks loop.
      - **Lines 208–210 (`result_code == "STAMINA_EMPTY"`)**:
        - Logs stamina depletion warning and breaks loop immediately.
      - **Lines 211–223 (`result_code in ("CMD_OPTING", "16001", "CMD_OPTING_FAILED")`)**:
        - Increments `cmd_opting_retries += 1`.
        - If `<= 2`: sleeps `random.uniform(10.0, 16.0)` seconds and continues loop.
        - If `> 2`: logs failure and breaks loop.
      - **Lines 224–230 (`result_code in ("NO_TARGET", "TARGET_OCCUPIED")`)**:
        - Increments `consecutive_errors += 1`.
        - If `>= 3`: logs exhaustion of search attempts and breaks loop.
        - Else: sleeps `random.uniform(1.8, 3.2)` seconds and retries.
      - **Lines 231–236 (`else`)**:
        - Increments `consecutive_errors += 1`.
        - If `>= 2`: breaks loop.
        - Else: sleeps `random.uniform(1.8, 3.2)` seconds and retries.
  - **Lines 237–250 (Post-Loop Result Synthesis)**:
    - If `sent_count > 0`: Returns `TaskResult.ok(f"✅ تم إرسال {sent_count} مسيرة هجوم على المعقل", sent=sent_count, queue_full=(last_result == "QUEUE_FULL"), stop_reason=last_result)`.
    - If `last_result == "QUEUE_FULL"`: Returns `TaskResult.fail("🛑 طوابير المسيرات بالقلعة مكتملة بالكامل...", queue_full=True, stop_reason="QUEUE_FULL")`.
    - If `last_result == "STAMINA_EMPTY"`: Returns `TaskResult.fail("🛑 نفدت طاقة اللورد بالكامل", stop_reason="STAMINA_EMPTY")`.
    - Default: Returns `TaskResult.fail("لم يتم إرسال أي مسيرة هجوم على المعقل", retry_after=120)`.

### 5. `StrongholdTask._send_one_stronghold(...) -> str` (Lines 253–445)
- **Signature**: `StrongholdTask._send_one_stronghold(self, min_lv: int, max_lv: int, search_range: int, formation_id: int, troops_cfg: int) -> str`
- **Execution Steps**:
  - Lines 254–258: Castle Coordinates: `cx, cy = await self.get_castle_coords()`. If missing, returns `"ERROR"`.
  - Lines 260–261: Kingdom ID: `kingdom_id = await self.get_kingdom_id()`.
  - Lines 264–284: Stronghold Search (`2011/3`):
    - Obtains `exclude_map = await self._exclude_mgr.get_exclude_map(self.uid, kingdom_id=kingdom_id)`.
    - Assembles payload: `{"mapType": 26, "subType": 0, "num": 5, "y": cy, "x": cx, "exclude": exclude_map, "range": search_range, "minLv": min_lv, "maxLv": max_lv}`.
    - Sends `r_search = await self.conn.query('2011', '3', search_payload)`.
    - Filters: `candidates = [c for c in raw_candidates if str(c.get('id', '')) not in exclude_map]`.
    - If no candidates: returns `"NO_TARGET"`.
  - Lines 286–290: Reads available troops and formation:
    - `available = await self.get_available_troops()`.
    - `form_heroes, form_pets, form_rune_pages, form_army_dict = await self.get_formation(formation_id)`.
  - Lines 294–298: Combat Hero Resolution:
    - Calls `chosen_heroes = await self.get_combat_heroes(form_heroes=form_heroes, max_count=2, exclude_busy=self._busy)`.
    - If empty: returns `"NO_HEROES"`.
  - Lines 301–320: March Army Preparation & Capacity Enforcement:
    - `max_safe_capacity = get_castle_march_capacity(self.conn, chosen_heroes=chosen_heroes)`.
    - Calls `self.get_march_army(...)`:
      - Catches `RuntimeError as e`: If `WEAK_ARMY` raised by `BaseTask`, catches exception, logs warning, and returns `"WEAK_ARMY"`.
    - If `army_list` is empty: returns `"NO_ARMY"`.
    - Computes `total_troops = sum(item['num'] for item in army_list)`.
  - Lines 322–340: Pet & Rune Resolution:
    - Flattens and extracts `form_pets`. If empty, calls `pets_list = await self.select_combat_pet()`.
    - Extracts `rune_pages_list = self.get_rune_pages(form_rune_pages)`.
  - Lines 345–444: Target Dispatch Iteration:
    - Iterates through `target in candidates`:
      - `target_id = target.get('id')`, `tx = target.get('x')`, `ty = target.get('y')`, `t_lv = target.get('level', '?')`.
      - Calls `await self._exclude_mgr.reserve(self.uid, target_id, kingdom_id=kingdom_id)`.
      - Constructs march payload (`1007/2`):
        ```json
        {
          "needSend": false,
          "runePages": rune_pages_list,
          "heros": chosen_heroes,
          "matrixType": 1,
          "mapId": int(kingdom_id),
          "moveLineType": 3,
          "data": {
            "data": { "judianState": 1 },
            "to": { "y": int(ty), "x": int(tx), "id": str(target_id) },
            "army": army_list
          },
          "pets": pets_list
        }
        ```
      - Sends query: `r_attack = await self.conn.query('1007', '2', attack_payload)`.
      - If `not r_attack`: Releases reservation and continues to next candidate.
      - Error handling logic:
        - `err == '0'`: Success. Calls `confirm()`, updates `_busy` and `_used_army`, returns `"SUCCESS"`.
        - `err in ('8004', '9007004')`: Calls `release()`, returns `"QUEUE_FULL"`.
        - `err == '8009'`: Calls `release()`, returns `"NO_ARMY"`.
        - `err in ('8032', '10002', '10003')`: Calls `release()`, returns `"STAMINA_EMPTY"`.
        - `err == '9007020'`: Adds heroes to `_busy`, calls `release()`, returns `"HERO_BUSY"`.
        - `err == '8035'`: Learns `reduced_troops = max(300, int(current_total * 0.85))`, records learned capacity, adjusts `army_list`, and attempts inline retry. If still failing, calls `release()` and continues candidate loop.
        - `err == '16001'`: Calls `release()`, returns `"CMD_OPTING"`.
        - `err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (8000 <= int(err) < 8100 and err not in ('8004', '8009', '8032'))`: Target occupied or invalid. Calls `confirm()`, continues candidate loop.
        - Default: Calls `release()`, returns `"ERROR"`.
  - Line 445: Returns `"TARGET_OCCUPIED"` if all candidates exhausted without success.

---

## 2.4 Complete Line-by-Line Execution Trace of Network Commands & Memory Keys

### Network Commands Table
| Command / Subcommand | Direction | Purpose | Exact Payload Structure | Expected Response / Data Extracted |
|---|---|---|---|---|
| `2011 / 3` | Outbound | Search map for Strongholds / Shelters | `{"mapType": 26, "subType": 0, "num": 5, "y": cy, "x": cx, "exclude": exclude_map, "range": search_range, "minLv": min_lv, "maxLv": max_lv}` | `{"result": [{"id": "...", "x": int, "y": int, "level": int}, ...]}` |
| `1007 / 2` | Outbound | Dispatch Stronghold March | `{"needSend": false, "runePages": [...], "heros": [...], "matrixType": 1, "mapId": int, "moveLineType": 3, "data": {"data": {"judianState": 1}, "to": {"x": int, "y": int, "id": str}, "army": [...]}, "pets": [...]}` | `{"err": "0"}` on success, or error string. |
| `1007 / 1000` | Outbound | Sync local queues via BaseTask probe | `{}` | Local queue sync packet. |

### Memory Keys (`init_data`) Table
| Top-Level Key | Sub-Keys & Paths | Data Type | Usage & Purpose in `stronghold.py` |
|---|---|---|---|
| `cityCtrl` | `cinfo.pos` | `Dict` | Castle coordinates (`cx`, `cy`) via `BaseTask.get_castle_coords()`. |
| `lordInfoCtrl` | `base.partition`, `base.health` | `Dict` | Kingdom partition ID and lord stamina. |
| `heroCtrl` | Array of hero dicts | `List[Dict]` | Live hero pool checked for availability. |
| `armyCtrl` | `totalArmy`, `compileHeros`, `compilePets`, `compileArmy` | `Dict` | Live troops and saved formation configuration. |
| `petCtrl` | `pets` | `Dict` | Pet inventory sorted by rank/level via `BaseTask.select_combat_pet()`. |
| `local_queues` | Array of active queues on `conn` | `List[Dict]` | March queue tracking for `get_active_marches_count()`. |

---

## 2.5 Server Response & Error Code Behavior Matrix for `tasks/stronghold.py`

| Code | Game Protocol Definition | Exact Code Handling in `stronghold.py` | ExcludeManager Action | Retry Logic & State Updates | Red Team Vulnerability / Flaw |
|---|---|---|---|---|---|
| `8004` | `Err_MAP_QUEUE_OUT_LIMIT` | Lines 389–392: Explicitly caught | `release(uid, target_id)` | Returns `"QUEUE_FULL"`. Outer loop waits up to `40 * 15s = 600s`. | Target released; other tasks can repeatedly target it and fail. |
| `9007004`| Alternative queue full code | Lines 389–392: Grouped with 8004 | `release(uid, target_id)` | Same as 8004. | Same as 8004. |
| `8009` | `Err_SOLDIER_NOT_ENOUGH` | Lines 393–396: Explicitly caught | `release(uid, target_id)` | Returns `"NO_ARMY"`. Unlike monster.py, does NOT check active marches. | If troops are in a returning march, fails with `NO_ARMY` instead of waiting for return. |
| `8035` | `Err_QUEUE_SOLDIER_LIMIT` | Lines 406–427: Explicitly caught | `confirm()` on retry success; `release()` on failure | Learns `reduced_troops = max(300, int(total * 0.85))`, rescales army, immediate inline retry. | Inline retry double query without delay; second failure continues candidate loop. |
| `8032` | `Err_ENERGY_NOT_ENOUGH` | Lines 397–400: Grouped | `release(uid, target_id)` | Returns `"STAMINA_EMPTY"`. Terminates task. | Target released. No potion consumption attempted. |
| `10002`| Stamina empty variant 1 | Lines 397–400: Grouped | `release(uid, target_id)` | Returns `"STAMINA_EMPTY"`. Terminates task. | Same as 8032. |
| `10003`| Stamina empty variant 2 | Lines 397–400: Grouped | `release(uid, target_id)` | Returns `"STAMINA_EMPTY"`. Terminates task. | Same as 8032. |
| `9007020`| `Err_HERO_IN_MARCH` | Lines 401–405: Explicitly caught | `release(uid, target_id)` | Adds heroes to `self._busy`. Returns `"HERO_BUSY"`. If alternative heroes exist, tries next hero immediately. | If all heroes busy, waits `wait_interval` or breaks. |
| `8014` | `Err_TARGET_PEACE_SHIELD` | Handled by fallback `8000 <= int(err) < 8100` (Lines 435–439) | `confirm(uid, target_id)` | Excludes target permanently in file for 4 hours. | Stronghold targets do not possess peace shields; code indicates client state error. |
| `8015` | `Err_TARGET_CANNOT_ATTACK`| Handled by fallback `8000 <= int(err) < 8100` | `confirm(uid, target_id)` | Excludes target permanently in file. | Target excluded even if restriction was temporary. |
| `8027` | `Err_MAP_QUEUE_NPC_LEVEL_OUT` | Handled by fallback `8000 <= int(err) < 8100` (Line 435) | `confirm(uid, target_id)` | Critical flaw: Treats level lock as target occupied! Calls `confirm()`. | Does NOT learn level limit or downgrade `max_lv`; permanently bans the stronghold! |
| `8037` | `Err_MARCH_DISTANCE_LIMIT`| Handled by fallback `8000 <= int(err) < 8100` | `confirm(uid, target_id)` | Excludes target permanently in file. | Excludes target due to search range configuration error. |
| `8041` | `Err_MASS_NOT_IN_ALLIANCE`| Handled by fallback `8000 <= int(err) < 8100` | `confirm(uid, target_id)` | Excludes target permanently in file. | Stronghold is solo attack (`moveLineType=3`), so 8041 should never occur. |
| `8042` | `Err_MASS_HALL_NOT_BUILT` | Handled by fallback `8000 <= int(err) < 8100` | `confirm(uid, target_id)` | Excludes target permanently in file. | Not applicable to solo strongholds; misclassified. |
| `8046` | `Err_MASS_TIME_INVALID` | Handled by fallback `8000 <= int(err) < 8100` | `confirm(uid, target_id)` | Excludes target permanently in file. | Not applicable to solo strongholds; misclassified. |
| `8060` | `Err_TARGET_OCCUPIED` | Lines 435–439: Explicitly caught | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Correct behavior: Stronghold occupied by another lord. |
| `8062` | `Err_TARGET_BATTLE_BUSY` | Lines 435–439: Explicitly caught | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Correct behavior: Stronghold is currently being attacked. |
| `8063` | `Err_TARGET_DISAPPEARED` | Lines 435–439: Explicitly caught | `confirm(uid, target_id)` | Permanently excludes target in file. Continues loop. | Correct behavior: Stronghold despawned. |
| `8095` | `Err_INVALID_FORMATION` | Handled by fallback `8000 <= int(err) < 8100` | `confirm(uid, target_id)` | Excludes target permanently in file. | Formation defect falsely blamed on stronghold target. |
| `16001`| `Err_CMD_OPTING` | Lines 428–434: Explicitly caught | `release(uid, target_id)` | Returns `"CMD_OPTING"`. Outer loop waits `10-16s` and retries up to 2 times. | Target released cleanly. |

---

## 2.6 In-Depth Red Team Critique for `tasks/stronghold.py`

### 1. Fatal Misclassification of Error `8027` (Level Locked)
Unlike `monster.py`, which explicitly catches `8027` to learn `_learned_max_npc_level` and dynamically downgrade search level (lines 1549–1558), `stronghold.py` does NOT catch `8027`!
Instead, `8027` falls into the generic range check at line 435:
```python
elif err in ('8062', '8063', '8060', '8013', '8002', '8026', '8003', '9007062') or (err.isdigit() and 8000 <= int(err) < 8100 and err not in ('8004', '8009', '8032')):
    self.log.warning(f"⚠️ المعقل {target_id} غير متاح أو مشغول بمعركة أخرى (كود {err}) — فحص معقل بديل فوراً...")
    await self._exclude_mgr.confirm(self.uid, target_id, kingdom_id=kingdom_id)
    continue
```
Because `8027` is between 8000 and 8100, the bot treats a level-locked stronghold as "occupied by another player" and permanently adds it to `exclude_history.json`. It will then proceed to try the next level-locked stronghold in `candidates`, permanently banning every single stronghold found on the map until candidates are exhausted.

### 2. Lack of Returning March Awareness on Error `8009`
In `monster.py`, when error `8009` (insufficient soldiers) is returned, the task queries `get_active_marches_count(force_sync=True)`. If active marches >= 1, it realizes troops are simply deployed and translates `8009` to `"QUEUE_FULL"` so the task can sleep and wait for returning troops.
In `stronghold.py` (lines 393–396):
```python
elif err == '8009':
    self.log.warning(f"⚠️ نقص في القوات المتاحة (كود {err})")
    await self._exclude_mgr.release(self.uid, target_id, kingdom_id=kingdom_id)
    return "NO_ARMY"
```
It immediately returns `"NO_ARMY"`, causing `run()` to terminate or sleep without recognizing that full armies are en route back to the castle.

### 3. Missing Direct Target Pre-verification (`1006/22`)
`BaseTask` implements `check_target_busy_or_marched` (lines 1143–1250 of `base_task.py`), which queries `1006/22` to check `currentCollectNum`, `collectSpeed`, and `marchId`/`battleId` before dispatching a march. `stronghold.py` completely bypasses `check_target_busy_or_marched`, blindly dispatching `1007/2` to candidates returned by `2011/3`. If a candidate is currently under attack by an ally or enemy, the march is rejected by server error `8062`.

---

## 2.7 Inventory of Duplicated Helper Functions in `stronghold.py`

| Helper Routine in `stronghold.py` | Lines | Functionality | Re-implemented / Duplicated In | Unification Target in `base_task.py` |
|---|---|---|---|---|
| `_load_heroes` | 68–85 | Extract heroCtrl and fallback armyCtrl from init_data | `monster.py` (689–706), `abra.py` (196–213) | `BaseTask.load_heroes()` |
| Queue full wait loop | 149–179 | Polls active marches and waits up to 40 cycles | `monster.py` (988–1018), `abra.py` (894–908) | `BaseTask.wait_for_free_queue()` |
| Map search assembly | 266–279 | Assembles `2011/3` search payload with exclude map | `monster.py` (1136–1146), `gather.py`, `ruins.py` | `BaseTask.search_map_targets()` |
| March payload assembly | 353–372 | Assembles `1007/2` payload for stronghold march | `monster.py` (1440–1481), `abra.py` (826–843) | `BaseTask.dispatch_march()` |
| Inline 8035 capacity retry | 406–427 | Reduces troops by 15% and retries query immediately | `monster.py` (1522–1548) | `BaseTask.handle_capacity_error()` |


---

# Part III: Deep Surgical Dissection of `tasks/abra.py`

## 3.1 Module Metadata, Architectural Role & Imports

- **Path**: `tasks/abra.py`
- **Total Lines**: 1,194 lines
- **Role**: Exterior PvE boss combat against the God Beast / Gold Monster "Abra" (`mapType=25`, class IDs `4301`/`4302`), featuring weekly calendar validation (Mondays and Wednesdays), a 20-attack daily limit, strict killing-blow preservation thresholds (`1,350,000` HP cutoff), pipelined sequential dispatching (dispatching the next march during the return phase of the previous march), same-branch military unit substitution, and resilient socket reconnection loops.
- **Dependencies & Imports**:
  - `asyncio`, `logging`, `math`, `random`, `time`, `datetime`, `timezone`, `sys`, `os`, `typing` (`Any`, `Dict`, `List`, `Optional`, `Set`, `Tuple`)
  - `tasks.base_task.BaseTask`, `tasks.base_task.TaskResult`
  - `game_client.GameConnection`
  - `tasks.monster._pick_combat_heroes`, `tasks.monster.select_combat_army`, `tasks.monster.calculate_castle_march_capacity`, `tasks.monster.get_unit_power`, `tasks.monster.get_unit_tier`

### Global Constants Defined at Module Level:
- `ABRA_MAP_TYPE = 25`: God Beast map object type.
- `ABRA_CLASS_ID_NORMAL = 4302`: Standard Gold Monster class ID.
- `ABRA_CLASS_ID_SPECIAL = 4301`: Special Gold Monster class ID.
- `MAX_DAILY_ATTACKS = 20`: Server-enforced daily attack limit per castle.
- `KILL_BLOW_THRESHOLD = 1350000`: Health cutoff (1.35 million HP) below which attacks immediately cease if the user opts out of delivering the killing blow, preserving the final rewards for an alternate castle.

---

## 3.2 Complete Table of Inputs, Configurations, Defaults & Validation Logic

| Config Parameter | Type | Default Value | Accepted / Valid Values | Validation & Sanitization Logic | Source / Ingestion Point |
|---|---|---|---|---|---|
| `x` | `int` | `0` | `1` to `1200` | `int(self.config.get("x", 0) or 0)`. Target X coordinate on the world map. Checked in line 673 (`target_x <= 0` triggers `target_not_found`). | `config`, CLI `-x`, DB `castle.config.abra.x` |
| `y` | `int` | `0` | `1` to `1200` | `int(self.config.get("y", 0) or 0)`. Target Y coordinate on the world map. Checked in line 673 (`target_y <= 0` triggers `target_not_found`). | `config`, CLI `-y`, DB `castle.config.abra.y` |
| `killing_blow` | `bool` | `False` | `True`, `False` | `bool(self.config.get("killing_blow", False))`. If `True`, attacks continue until HP reaches 0 or 20 attacks are exhausted. If `False`, halts when HP `<= stop_hp_threshold`. | `config`, CLI `--killing-blow` / `--no-killing-blow`, DB |
| `formation_id` / `formation` | `int` | `1` | `1` to `5` | `int(self.config.get("formation_id", self.config.get("formation", 1)) or 1)`. Passed to `_load_formation`. | `config`, CLI `--formation` / `-f`, DB |
| `stop_hp_threshold` | `int` | `1350000` | `10000` to `50000000` | `int(self.config.get("stop_hp_threshold", KILL_BLOW_THRESHOLD))`. Health cutoff boundary. | `config` |
| `class_id` | `int` | `4302` | `4301`, `4302` | `int(self.config.get("class_id", ABRA_CLASS_ID_NORMAL))`. Used in target ID generation: `{x+1}-{y+1}-25-0-{class_id}`. | `config` |
| `force` | `bool` | `False` | `True`, `False` | `bool(self.config.get("force", False))`. If `True`, bypasses Monday/Wednesday calendar checks. | `config`, CLI `--force` |
| `max_queues` | `int` | `6` (adaptive) | `1` to `10` | Extracted from `config.get("max_queues")` or `conn.max_queues`. Dynamically reduced when error `8004` is encountered. | `config`, `conn.max_queues` |

---

## 3.3 Comprehensive Function-by-Function & Line-by-Line Dissection

### 1. `ReturningMarch` Data Structure (Lines 77–85)
- **Class**: `ReturningMarch`
- **Slots**: `__slots__ = ("qid", "heroes", "finish_time")`
- **Purpose**: Lightweight record tracking an outbound march that has struck the boss and is currently traveling back to the castle in the background. Stores the march queue ID (`qid`), the list of deployed hero IDs (`heroes`), and the unix timestamp of castle entry (`finish_time`).

### 2. `AbraTask.__init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None)` (Lines 95–109)
- **Signature**: `AbraTask.__init__(self, conn: GameConnection, config: Optional[Dict[str, Any]] = None)`
- **Initialization**:
  - Sets `self.name = "abra"`.
  - Parses `target_x`, `target_y`, `killing_blow`, `formation_id`, `stop_threshold`, `class_id`.
  - Initializes state variables: `_map_id = 0`, `_castle_x = 0`, `_castle_y = 0`, `_heroes = []`, `_busy_heroes = set()`.

### 3. `AbraTask.on_start(self)` (Lines 110–115)
- **Signature**: `AbraTask.on_start(self)`
- **Execution**: Awaits `_load_castle_coords()`, `_load_map_id()`, and `_load_heroes()`.

### 4. `AbraTask._resolve_map_id(self) -> int` (Lines 116–144)
- **Signature**: `AbraTask._resolve_map_id(self) -> int`
- **Hierarchy of Kingdom Partition Discovery**:
  - Step 1: Checks `conn.init_data['kingdomMapCtrl']['mapId']` or `kingdomId`.
  - Step 2: Checks `conn.kingdom_id`.
  - Step 3: Checks `conn.init_data['lordInfoCtrl']['base']['partition']`.
  - Step 4: Checks `conn.init_data['lord']['partition']` or `kingdomId`.
  - Fallback: Returns `0`.

### 5. `AbraTask._get_lord_stamina(self) -> int` (Lines 146–162)
- **Signature**: `AbraTask._get_lord_stamina(self) -> int`
- **Logic**: Inspects `conn.init_data['lordInfoCtrl']['base']['health']` or `loginDataInitCtrl['base']['health']`. Converts to `int(float(val))` and returns current stamina balance (defaulting to 100 on missing memory).

### 6. `AbraTask._load_map_id(self)` (Lines 163–176)
- **Signature**: `AbraTask._load_map_id(self)`
- **Logic**: Calls `_resolve_map_id()`. If 0, sends network query `1002/7` (`REQ_USER_INFO`) to extract `base.partition` from player metadata.

### 7. `AbraTask._load_castle_coords(self)` (Lines 177–195)
- **Signature**: `AbraTask._load_castle_coords(self)`
- **Logic**: Reads `conn.init_data['cityCtrl']['cinfo']['pos']`. If missing, queries `1006/25` (`REQ_GET_CASTLE_MAP_INFO`) with `{"uid": uid_int}` and extracts `retData.x` and `retData.y`.

### 8. `AbraTask._load_heroes(self)` (Lines 196–213)
- **Signature**: `AbraTask._load_heroes(self)`
- **Logic**: Reads `heroCtrl`. If empty, reads `armyCtrl.compileHeros` and constructs placeholder hero dictionaries.

### 9. `AbraTask._build_target_id(self, x: int, y: int, class_id: int) -> str` (Lines 214–216)
- **Signature**: `AbraTask._build_target_id(self, x: int, y: int, class_id: int) -> str`
- **Logic**: Generates official coordinate grid ID string: `f"{x + 1}-{y + 1}-{ABRA_MAP_TYPE}-0-{class_id}"` (e.g. `"480-388-25-0-4302"`). Note that the game engine adds `+1` to map cell coordinates for entity indexing.

### 10. `AbraTask.get_monster_hp(self, x: int, y: int) -> Tuple[Optional[int], int]` (Lines 218–260)
- **Signature**: `AbraTask.get_monster_hp(self, x: int, y: int) -> Tuple[Optional[int], int]`
- **Protocol Sequence**:
  - Establishes deduplicated candidate class IDs: `[class_id, 4302, 4301]`.
  - For each `cid`:
    - Generates `target_id = self._build_target_id(x, y, cid)`.
    - **Map Sync (`1006/1000`)**: Sends `centerX=x, centerY=y, centerKid=_map_id` to synchronize the 16x16 map tile sector.
    - Humanized jitter sleep: `asyncio.sleep(random.uniform(0.65, 0.95))`.
    - **Tile Detail Query (`1006/15`)**: Queries `cmd: "1006", subcmd: "15"`, payload `{"x": x, "y": y, "id": target_id, "kingdomId": self._map_id}`.
    - Extracts HP via `_extract_hp_from_tile_response(r_tile)`. If non-null, returns `(hp, cid)`.
  - Returns `(None, self.class_id)` if all class IDs fail.

### 11. `AbraTask._extract_hp_from_tile_response(self, resp: dict) -> Optional[int]` (Lines 261–286)
- **Signature**: `AbraTask._extract_hp_from_tile_response(self, resp: dict) -> Optional[int]`
- **Robust Parser**: Inspects `resp['data']`, `resp['retData']`, `resp`. Checks keys: `leftLife`, `boss.leftLife`, `bossData.leftLife`, `npc.leftLife`, `instance.leftLife`. Returns integer health value or `None`.

### 12. `AbraTask.get_daily_attack_count(self) -> int` (Lines 288–309)
- **Signature**: `AbraTask.get_daily_attack_count(self) -> int`
- **Zero-Request Path**: Inspects `conn.init_data['godBeastCtrl']['godbeastperson']['attackNum']`.
- **Fallback Query**: If missing from memory, queries `1087/3` (`REQ_GOD_BEAST_MEMBER_INFO`), extracting `data.memberdata.attackNum`.

### 13. `AbraTask._load_formation(self, fid: int) -> Tuple[List[int], List[int], List[int], Dict[int, int]]` (Lines 310–362)
- **Signature**: `AbraTask._load_formation(self, fid: int) -> Tuple[List[int], List[int], List[int], Dict[int, int]]`
- **Logic**: Inspects `armyCtrl` for `compileArmy`, `compileHeros`, `compilePets`, `compileRunePages`. If absent, queries network command `1005/7` with `{"compiletype": fid}`. Flattens hero/pet/rune arrays and constructs `army_dict`.

### 14. `AbraTask._resolve_combat_heroes(self, form_heroes: List[int]) -> List[int]` (Lines 364–422)
- **Signature**: `AbraTask._resolve_combat_heroes(self, form_heroes: List[int]) -> List[int]`
- **Hero Availability Hierarchy**:
  - Filters `form_heroes` against `_busy_heroes` and checks `status.state == 0`.
  - Case 1: Both formation heroes available -> returns both immediately.
  - Case 2: One formation hero available -> keeps available hero, calls `_pick_combat_heroes(max_count=1)` to substitute the busy hero with the best idle `5501xxx` war hero.
  - Case 3: Both formation heroes busy -> calls `_pick_combat_heroes(max_count=2)` to select the top 2 war heroes in the castle.
  - Emergency Fallback: Scans all heroes for any non-busy hero not starting with `5502` or `5503`.

### 15. `AbraTask.ensure_connection(self, max_retries: int = 5, wait_sec: int = 10) -> bool` (Lines 424–471)
- **Signature**: `AbraTask.ensure_connection(self, max_retries: int = 5, wait_sec: int = 10) -> bool`
- **Socket Health Guard**:
  - If `self.is_connected`: returns `True` immediately.
  - Disconnect handling loop (up to 5 retries):
    - Closes stale dead socket: `await self.conn.close()`.
    - Sleeps `wait_sec + random.uniform(0.5, 2.5)` seconds.
    - Reconnects: `ok = await self.conn.connect()`.
    - Initialization wait: Waits up to 25 cycles for `cityCtrl` or `heroCtrl` in `init_data`.
    - Reloads castle coordinates and hero pools.
    - Returns `True` on successful re-entry; returns `False` after 5 failed attempts.

### 16. `AbraTask._get_available_troops(self) -> Dict[int, int]` (Lines 472–498)
- **Signature**: `AbraTask._get_available_troops(self) -> Dict[int, int]`
- **Logic**: Reads `armyCtrl.totalArmy` from `init_data` (0ms). Fallback queries `1005/1` if memory unpopulated.

### 17. `AbraTask._resolve_combat_army(...) -> List[Dict[str, int]]` (Lines 499–613)
- **Signature**: `AbraTask._resolve_combat_army(self, form_army_dict: Dict[int, int], chosen_heroes: List[int]) -> List[Dict[str, int]]`
- **Same-Branch Military Substitution Algorithm**:
  - Calculates `castle_capacity = calculate_castle_march_capacity(...)`.
  - Excludes traps `800 <= tid < 900`.
  - If formation exceeds capacity: scales down proportionally (`scale = castle_capacity / total_form_req`).
  - Iterates through requested units:
    - Takes available units from castle.
    - If deficit occurs: determines branch prefix `branch_prefix = tid // 100` (`4`=Infantry, `5`=Cavalry, `6`=Archers, `7`=Siege).
    - Filters castle units matching the exact same branch prefix (`cand_id // 100 == branch_prefix`), excluding traps and unit `tid`.
    - Sorts substitution candidates descending by `(get_unit_power(c), c)` so highest tier units substitute first.
    - Deducts substitutions from deficit and available pools.
  - If remaining march deficit persists: fills remaining capacity using `select_combat_army(available, needed_count=remaining_deficit)`.
  - If formation was empty: fills entirely via `select_combat_army(available, needed_count=castle_capacity)`.
  - Returns finalized `army_list`.

### 18. `AbraTask._wait_for_outbound_hit(self, queue_id: str, one_way_seconds: int = 60) -> Optional[int]` (Lines 615–645)
- **Signature**: `AbraTask._wait_for_outbound_hit(self, queue_id: str, one_way_seconds: int = 60) -> Optional[int]`
- **Outbound-Only March Timing Engine**:
  - Clamps `one_way = max(20, int(one_way_seconds))`.
  - Slices wait into 15-second heartbeats while checking `self.is_stopped()`.
  - Sleeps post-impact delay `random.uniform(1.2, 2.2)` seconds to allow server battle damage processing.
  - Checks socket via `ensure_connection()`.
  - Queries `hp_after_hit, _ = await self.get_monster_hp(self.target_x, self.target_y)`.
  - Returns updated boss health `hp_after_hit`.

### 19. `AbraTask._wait_for_returning_march(self, queue_id: str, finish_time: float)` (Lines 646–661)
- **Signature**: `AbraTask._wait_for_returning_march(self, queue_id: str, finish_time: float)`
- **Logic**: Polls current timestamp against `finish_time`, sleeping in 15-second intervals until the returning march enters the castle gates, freeing its heroes and troops.

### 20. `AbraTask.run(self) -> TaskResult` (Lines 662–1030)
- **Pipelined Marching & Execution Flow**:
  - Step 0: Calls `await self.on_start()`.
  - Step 1: Validates coordinates: `if self.target_x <= 0 or self.target_y <= 0`: returns `TaskResult.fail(status="target_not_found")`.
  - Step 1.5: Stamina check: `lord_stamina = self._get_lord_stamina()`. If `< 10`, returns `TaskResult.ok(status="stamina_empty")`.
  - Step 2: Calendar check: `now_utc.weekday() in (0, 2)` (Monday or Wednesday) or `force=True`.
  - Step 3: Map verification: Queries `initial_hp, actual_cid = await self.get_monster_hp(...)`.
    - If `initial_hp is None`: If not event day, returns `TaskResult.ok(status="skipped")`; else returns `TaskResult.fail(status="target_not_found")`.
    - If `initial_hp <= 0`: returns `TaskResult.ok(status="defeated")`.
  - Step 4: Pre-flight Killing Blow Check: `if not self.killing_blow and initial_hp <= self.stop_threshold`: returns `TaskResult.ok(status="safe_hp_stop")`.
  - Step 5: Daily attack check: `attacks_done = await self.get_daily_attack_count()`. If `>= 20`, returns `TaskResult.ok(status="attacks_completed")`.
  - Step 6: Loads formation: `_load_formation(self.formation_id)`.
  - Step 7: **Pipelined Attack Loop (`while attacks_done < MAX_DAILY_ATTACKS and not is_stopped()`)**:
    - Reconnection guard: `await self.ensure_connection()`.
    - Garbage collects returned marches: `cleanup_returned_marches()`.
    - Polls live HP: `cur_hp = await self.get_monster_hp()`. If `<= 0`, breaks; if `not killing_blow and cur_hp <= stop_threshold`, breaks.
    - Stamina re-check: `if lord_stamina < 10`: breaks.
    - Hero & Queue Availability:
      - Resolves `march_heroes = self._resolve_combat_heroes(form_heroes)`.
      - If no heroes available or active marches >= max queues: waits for nearest returning march, cleans up, and continues loop.
    - Army Preparation:
      - Resolves `march_army = await self._resolve_combat_army(form_army_dict, march_heroes)`.
      - If no troops: waits for nearest returning march; if no marches returning, returns `TaskResult.fail(status="critical_no_army")`.
    - Assembles payload (`1007/2`):
      - `needSend: false`, `runePages: [1]`, `matrixType: 1`, `moveLineType: 1`, `to: {"x": target_x, "y": target_y, "id": target_id}`.
    - **Dispatch Retry Loop (up to 10 attempts)**:
      - Sends `r_march = await self.conn.query('1007', '2', march_payload, timeout=6)`.
      - If success (`err == '0'`): extracts `qid` from response queue object.
      - If `err == '9007020'`: Updates `_busy_heroes`. Resolves alternative heroes. If alternative found, replaces `march_payload['heros']` and retries immediately! If no alternative, waits for returning march or sleeps 13-18s.
      - If `err in ('8004', '9007004')`: Lowers `max_castle_queues` to observed active count. Waits for returning march or sleeps 25-35s.
      - If `err == '8009'`: Waits for returning march.
      - If `err in ('8032', '10002', '10003')`: Returns `TaskResult.fail("🛑 نفدت طاقة اللورد...")`.
      - If `err == '16001'`: Sleeps `10-16s` and retries.
      - Else: logs error and breaks attempt loop.
    - Post-Dispatch Tracking:
      - Increments `attacks_done += 1`, `session_attacks += 1`.
      - Marks `_busy_heroes.update(march_heroes)`.
      - Computes distance and duration: `dist = math.hypot(target_x - _castle_x, target_y - _castle_y)`. `est_one_way = realTotalTime` or `int(dist * 1.25)`.
    - **Outbound Strike Wait**:
      - Awaits `hp_after_strike = await self._wait_for_outbound_hit(qid, one_way_seconds=est_one_way)`.
      - Updates `current_hp = hp_after_strike`.
      - Records returning march: `return_finish = time.time() + est_one_way + 3`. Appends `ReturningMarch(qid, march_heroes, return_finish)`.
    - **Post-Strike Killing Blow Check**:
      - `if not self.killing_blow and current_hp <= self.stop_threshold`: Breaks loop immediately!
      - `if current_hp <= 0 or attacks_done >= 20`: Breaks loop.
    - **Pipeline Marching Evaluation**:
      - Checks `has_queue = active_now < max_castle_queues`.
      - Checks `can_heroes = bool(self._resolve_combat_heroes(form_heroes))`.
      - Checks `has_troops = (sum(cur_avail_troops.values()) >= 300)`.
      - Sleeps humanized interval `random.uniform(2.2, 3.8)` seconds.
      - If `has_queue and can_heroes and has_troops`: Logs pipeline dispatch and **continues loop immediately**, launching the next march while the prior march is still returning!
      - Else: Waits for nearest returning march via `_wait_for_returning_march()`, cleans up, and reloads heroes.
  - Finalization: Queries final HP and returns `TaskResult.ok(status="completed", session_attacks=session_attacks, total_attacks=attacks_done, remaining_hp=final_hp_val)`.

---

## 3.4 Complete Line-by-Line Execution Trace of Network Commands & Memory Keys

### Network Commands Table
| Command / Subcommand | Direction | Purpose | Exact Payload Structure | Expected Response / Data Extracted |
|---|---|---|---|---|
| `1002 / 7` | Outbound | Fallback Player Info Query | `{"uid": uid_int}` | `{"data": {"base": {"partition": int}}}` |
| `1006 / 25` | Outbound | Fallback Castle Coords Query | `{"uid": uid_int}` | `{"retData": {"x": int, "y": int}}` |
| `1006 / 1000` | Outbound | Map Tile Sector Sync | `{"centerX": x, "centerY": y, "centerKid": kingdom_id}` | Map sector sync response |
| `1006 / 15` | Outbound | Query Boss Tile Details & Health | `{"x": x, "y": y, "id": target_id, "kingdomId": kingdom_id}` | `{"retData": {"leftLife": int, "boss": {"leftLife": int}}}` |
| `1087 / 3` | Outbound | Fallback Daily Attack Count Query | `{}` | `{"data": {"memberdata": {"attackNum": int}}}` |
| `1005 / 7` | Outbound | Fallback Formation Query | `{"compiletype": fid}` | `{"data": {"compileHeros": [...], "compileArmy": {...}}}` |
| `1005 / 1` | Outbound | Fallback Total Army Query | `{}` | `{"data": {"totalArmy": {...}}}` |
| `1007 / 2` | Outbound | Dispatch Abra Solo March | `{"needSend": false, "runePages": [...], "heros": [...], "matrixType": 1, "mapId": int, "moveLineType": 1, "data": {"data": {}, "to": {"x": int, "y": int, "id": str}, "army": [...]}, "pets": [...]}` | `{"err": "0", "data": {"queue": {"id": str, "realTotalTime": int}}}` |

### Memory Keys (`init_data`) Table
| Top-Level Key | Sub-Keys & Paths | Data Type | Usage & Purpose in `abra.py` |
|---|---|---|---|
| `godBeastCtrl` | `godbeastperson.attackNum` | `Dict` | Live count of boss attacks executed today (0 to 20). |
| `cityCtrl` | `cinfo.pos` | `Dict` | Castle coordinates for distance calculations. |
| `kingdomMapCtrl` | `mapId`, `kingdomId` | `Dict` | Kingdom partition ID resolution. |
| `lordInfoCtrl` | `base.health`, `base.partition` | `Dict` | Lord stamina balance and kingdom partition ID. |
| `loginDataInitCtrl`| `base.health` | `Dict` | Fallback stamina balance. |
| `heroCtrl` | Array of hero dicts | `List[Dict]` | Live hero pool for combat hero resolution. |
| `armyCtrl` | `totalArmy`, `compileArmy`, `compileHeros`, `compilePets` | `Dict` | Live troop counts and formation definitions. |
| `local_queues` | Array of active queues on `conn` | `List[Dict]` | Active march queues for capacity checks. |

---

## 3.5 Server Response & Error Code Behavior Matrix for `tasks/abra.py`

| Code | Game Protocol Definition | Exact Code Handling in `abra.py` | ExcludeManager Action | Retry Logic & State Updates | Red Team Vulnerability / Flaw |
|---|---|---|---|---|---|
| `8004` | `Err_MAP_QUEUE_OUT_LIMIT` | Lines 885–907: Explicitly caught | Not using ExcludeManager | Lowers `max_castle_queues = min(max_castle_queues, observed)`. If returning march exists, waits for return; else sleeps 25–35s. Retries up to 10 times. | Does not interact with ExcludeManager (Abra is a single world boss). |
| `9007004`| Alternative queue full code | Lines 885–907: Grouped with 8004 | Not using ExcludeManager | Same as 8004. | Same as 8004. |
| `8009` | `Err_SOLDIER_NOT_ENOUGH` | Lines 908–915: Explicitly caught | Not using ExcludeManager | If returning march exists, waits for return; else terminates attempt loop. | If soldiers desync and no march is returning, task fails with `critical_no_army`. |
| `8035` | `Err_QUEUE_SOLDIER_LIMIT` | Not explicitly caught; falls to line 928 | Not using ExcludeManager | Logs failure code and breaks attempt loop. | Critical omission: Unlike monster and stronghold, does NOT learn or scale down troops on 8035! |
| `8032` | `Err_ENERGY_NOT_ENOUGH` | Lines 916–918: Grouped | Not using ExcludeManager | Returns `TaskResult.fail("🛑 نفدت طاقة اللورد...")`. Breaks task. | No stamina potion consumption attempted. |
| `10002`| Stamina empty variant 1 | Lines 916–918: Grouped | Not using ExcludeManager | Returns `TaskResult.fail("🛑 نفدت طاقة اللورد...")`. Breaks task. | Same as 8032. |
| `10003`| Stamina empty variant 2 | Lines 916–918: Grouped | Not using ExcludeManager | Returns `TaskResult.fail("🛑 نفدت طاقة اللورد...")`. Breaks task. | Same as 8032. |
| `9007020`| `Err_HERO_IN_MARCH` | Lines 863–884: Explicitly caught | Not using ExcludeManager | Adds heroes to `_busy_heroes`. Resolves alternative heroes. If alternative found, updates payload and retries immediately! If none, waits for returning march or sleeps 13–18s. | Retries up to 10 attempts. Highly resilient hero swapping. |
| `8014` | `Err_TARGET_PEACE_SHIELD` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | World boss cannot have peace shield; indicates incorrect coordinate payload. |
| `8015` | `Err_TARGET_CANNOT_ATTACK`| Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Boss event expired or target inactive. |
| `8027` | `Err_MAP_QUEUE_NPC_LEVEL_OUT` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Not applicable to Abra (boss has no progressive first-kill levels). |
| `8037` | `Err_MARCH_DISTANCE_LIMIT`| Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Castle is too far from Abra on the world map. |
| `8041` | `Err_MASS_NOT_IN_ALLIANCE`| Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Abra uses solo march (`moveLineType=1`), so mass errors do not occur. |
| `8042` | `Err_MASS_HALL_NOT_BUILT` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Not applicable to solo marches. |
| `8046` | `Err_MASS_TIME_INVALID` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Not applicable to solo marches. |
| `8060` | `Err_TARGET_OCCUPIED` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Abra is not an occupiable tile. |
| `8062` | `Err_TARGET_BATTLE_BUSY` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Multiple players can attack Abra simultaneously; code indicates invalid march payload. |
| `8063` | `Err_TARGET_DISAPPEARED` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Boss despawned or was killed. |
| `8095` | `Err_INVALID_FORMATION` | Handled by fallback (Line 928) | None | Logs warning and breaks attempt loop. | Malformed army array. |
| `16001`| `Err_CMD_OPTING` | Lines 919–926: Explicitly caught | None | Sleeps `10.0–16.0` seconds and retries attempt loop up to 10 times. | Resilient backoff logic. |

---

## 3.6 In-Depth Red Team Critique for `tasks/abra.py`

### 1. The Pipelined Killing Blow Race Condition (Accidental Overkill)
`abra.py` incorporates an aggressive Pipelined Marching optimization: when March #1 strikes the boss and begins its return journey, the bot evaluates boss HP. If HP is still above `1,350,000` (e.g. `1,400,000`), the bot launches March #2 immediately (lines 985–991).
However, if another player or another alliance member hits the boss while March #2 is traveling outward, or if March #2 deals more than `1,400,000` damage (which a high-tier full castle march frequently does), March #2 will strike the boss and deliver the killing blow, completely violating the user's explicit `--no-killing-blow` instruction!
While line 954 checks HP *after* the hit, by that time the blow has already landed and the boss is dead. To guarantee 100% compliance with killing blow preservation, pipelining must be automatically disabled whenever HP is within 2 full march damage equivalents (e.g. `< 4,000,000` HP).

### 2. Complete Absence of Error `8035` Capacity Mitigation
Unlike `monster.py` and `stronghold.py`, which catch `8035` and dynamically scale down troops by 15–18% and record learned capacity, `abra.py` has no handler for `8035`. If a player's castle buffs expire or if heroes provide less capacity than expected, `1007/2` fails with `8035`, hits line 928:
```python
else:
    self.log.warning(f"⚠️ فشل إرسال هجمة Abra (كود الخطأ: {err_code})")
    break
```
and permanently terminates the 20-attack session.

### 3. Coordinate String Inconsistency & Grid Desync
In line 215:
`return f"{x + 1}-{y + 1}-{ABRA_MAP_TYPE}-0-{class_id}"`
While in `monster.py` and `stronghold.py`, target IDs are parsed directly from `2011/3` search results as returned by the server. If the server map indexing changes or if the boss coordinate is registered with a different offset on certain kingdom map partitions, `1006/15` fails to extract HP, causing `initial_hp is None` and aborting the task.

---

## 3.7 Inventory of Duplicated Helper Functions in `abra.py`

| Helper Routine in `abra.py` | Lines | Functionality | Re-implemented / Duplicated In | Unification Target in `base_task.py` |
|---|---|---|---|---|
| `_resolve_map_id` | 116–144 | Resolves kingdom partition ID from init_data / lord | `base_task.py` (505–555) | `BaseTask.get_kingdom_id()` |
| `_load_castle_coords` | 177–195 | Resolves castle coordinates from cityCtrl / 1006/25 | `base_task.py` (459–504) | `BaseTask.get_castle_coords()` |
| `_load_heroes` | 196–213 | Reads heroCtrl or reconstructs from compileHeros | `monster.py` (689–706), `stronghold.py` (68–85) | `BaseTask.load_heroes()` |
| `_load_formation` | 310–362 | Reads compileArmy/Heros/Pets/Runes or queries 1005/7 | `base_task.py` (615–669) | `BaseTask.get_formation()` |
| `_resolve_combat_heroes` | 364–422 | Combat hero substitution and hierarchy | `base_task.py` (698–853), `monster.py` (196–262) | `BaseTask.get_combat_heroes()` |
| `ensure_connection` | 424–471 | Reconnection loop with init_data synchronization | Custom in `abra.py` | `BaseTask.ensure_connection()` |
| `_get_available_troops` | 472–498 | Reads totalArmy or queries 1005/1 | `base_task.py` (557–613) | `BaseTask.get_available_troops()` |
| `_resolve_combat_army` | 499–613 | Capacity scaling and military branch unit substitution | `base_task.py` (911–1040), `monster.py` (377–536) | `BaseTask.get_march_army()` |
| Map sector sync (`1006/1000`) | 231–235 | Synchronizes map sector before entity query | `base_task.py` (1197–1203) | `BaseTask.sync_map_tile()` |


---

# Part IV: Comparative Cross-Task Synthesis & BaseTask Unification Blueprint

## 4.1 Master Capability & Behavior Comparison Matrix

| Architectural Feature / Behavior | `tasks/monster.py` | `tasks/stronghold.py` | `tasks/abra.py` | Unified Blueprint Standard (`BaseTask`) |
|---|---|---|---|---|
| **Primary Target Types** | Invaders (`6`) & Rebels (`35`) | Strongholds / Shelters (`26`) | God Beast Boss Abra (`25`) | Extensible `target_type` registry |
| **March Mode** | Solo (`moveLineType=1`) or Mass Rally (`moveLineType=7`) | Solo Attack (`moveLineType=3`, `judianState=1`) | Solo Boss March (`moveLineType=1`) | Parameterized `moveLineType` |
| **Pipelined Dispatching** | No (Wait for return before next march if queue full) | No (Wait for return if queue full) | **Yes** (Dispatches next march while prior march is returning) | Support Pipelined Marching via configurable flag |
| **Killing Blow Protection** | Not applicable | Not applicable | **Yes** (Stops at `1,350,000` HP) | Standard HP threshold guard |
| **Dynamic Level Clamping** | **Yes** (Clamps by map, kill record, and army power) | No (Direct user level query) | Not applicable | Centralized `determine_safe_level()` |
| **Pre-requisite Verification** | **Yes** (Alliance check + Hall of War lv >= 1) | No prerequisite checks | Calendar check (Mon/Wed) + 20-attack cap | Centralized `check_prerequisites()` |
| **Suicide Prevention Guard** | **Yes** (Rejects march if power < 45% of enemy FC) | Partial (via BaseTask `WEAK_ARMY` 50% check) | No explicit FC suicide check | Centralized `Anti-Suicide Guard` |
| **Hero Selection Hierarchy** | Local `_pick_combat_heroes` (5501 prioritized, 5502/5503 excluded) | Inherited `BaseTask.get_combat_heroes` | Custom `_resolve_combat_heroes` calling `_pick_combat_heroes` | Single canonical `BaseTask.get_combat_heroes()` |
| **Pet Selection** | Local `select_combat_pet` (by level) | Inherited `BaseTask.select_combat_pet` (by rank/level/exp) | Flattened formation pets | Single canonical `BaseTask.select_combat_pet()` |
| **Rune Selection** | Custom inline extraction (default `[1]`) | Inherited `BaseTask.get_rune_pages` | Custom inline extraction (default `[1]`) | Single canonical `BaseTask.get_rune_pages()` |
| **Troop Shortfall Compensation** | Re-runs `select_smart_combat_army` on deficit | Power-weighted compensation via `_pick_balanced_combat_troops` | Same military branch (`tid // 100`) highest tier substitution | Unified Same-Branch Tier Substitution with Power Fallback |
| **March Capacity Safeguard** | `enforce_safe_march_troops` + learned session cap | `enforce_safe_march_troops` + learned session cap | Proportional scale-down | Mandatory `BaseTask.enforce_capacity()` |
| **Target Pre-verification** | None (Relies on search result) | None (Bypasses `1006/22`) | Queries `1006/1000` + `1006/15` | Pre-verification via `1006/22` / `1006/15` |
| **ExcludeManager Integration** | Full `reserve` -> `confirm` / `release` | Full `reserve` -> `confirm` / `release` | Not integrated (Single target) | Standardized in `BaseTask.dispatch_with_exclude()` |
| **Handling of Error `8027`** | **Learns level cap and retries** | **Bans target as occupied (Bug!)** | Unhandled | Centralized Level Downgrade |
| **Handling of Error `8035`** | Scales down 18% and retries | Scales down 15% and retries | Unhandled (Aborts task) | Centralized Capacity Reduction Retry |
| **Handling of Error `8009`** | Checks active marches -> `QUEUE_FULL` | Returns `NO_ARMY` immediately | Waits for returning march | Centralized Active March Check |
| **Socket Drop Recovery** | None (Fails on connection lost) | None (Fails on connection lost) | **Robust `ensure_connection` loop** | Canonical `BaseTask.ensure_connection()` |

---

## 4.2 Duplication Census Across the Three Files

| Duplicated Logic / Routine | `monster.py` Lines | `stronghold.py` Lines | `abra.py` Lines | Root Architectural Flaw |
|---|---|---|---|---|
| **Hero Data Extraction (`_load_heroes`)** | 689–706 | 68–85 | 196–213 | Triplicated logic scanning `heroCtrl` and falling back to `compileHeros`. |
| **Hero Selection & Filtering** | 196–262 | Inherited (698–853) | 364–422 | `abra.py` imports `_pick_combat_heroes` from `monster.py` while `stronghold.py` calls `BaseTask.get_combat_heroes()`, creating 3 divergent hero selection behaviors! |
| **Troop Composition & Capacity Scaling** | 377–536, 1221–1354 | Inherited (911–1040) | 499–613 | 3 different algorithms for handling troop shortages: `monster.py` re-runs smart composition, `stronghold.py` uses power-balanced compensation, `abra.py` uses branch-prefix substitution. |
| **Pet Selection & Fallback** | 633–658 | Inherited (855–909) | 338 | Divergent sorting: `monster.py` sorts only by level; `base_task.py` sorts by step, level, exp; `abra.py` takes whatever is in formation. |
| **Rune Extraction & Sanitization** | 1413–1426 | Inherited (670–696) | 347–352 | Identical type-checking loops converting lists/dicts/ints to `[int]`. |
| **Map Search Query Formatting** | 1136–1146 | 266–279 | N/A | Duplicate assembly of `2011/3` payloads with identical exclude mapping. |
| **March Queue Full Wait Loop** | 988–1018 | 150–179 | 894–908 | 3 separate implementations of polling loops sleeping `wait_interval` and checking active march counts. |
| **Error 8035 Mitigation** | 1522–1548 | 406–427 | Missing | In-line query retry copied almost verbatim between `monster.py` and `stronghold.py`, but missing in `abra.py`. |

---

## 4.3 Unified Architecture Blueprint for `BaseTask`

To eliminate all code duplication, prevent Red Team vulnerabilities, and establish a single source of truth, `BaseTask` must absorb and unify the following canonical subsystems:

### 1. Canonical March Dispatcher with Exclude Lifecycle
```python
async def dispatch_exterior_march(
    self,
    map_type: int,
    move_line_type: int,
    target_id: str,
    tx: int,
    ty: int,
    formation_id: int = 1,
    troops_cfg: int = 0,
    mass_time: Optional[int] = None,
    allow_pipelining: bool = False
) -> Tuple[bool, str]:
    """
    Standardized exterior march lifecycle:
    1. Reserves target in ExcludeManager.
    2. Resolves idle combat heroes via canonical get_combat_heroes().
    3. Resolves army via canonical get_march_army() with same-branch tier substitution.
    4. Resolves pet and runes via canonical helpers.
    5. Dispatches 1007/2.
    6. Centralized Error Code Handler (8004, 8009, 8035, 8027, 8062, 16001).
    7. Confirms or releases target in ExcludeManager based on exact error classification.
    """
```

### 2. Canonical Troop Substitution Engine
Merge `abra.py`'s same-branch tier substitution algorithm (`tid // 100`) with `monster.py`'s anti-suicide calculation into `BaseTask.get_march_army()`.
- Primary: Exact formation matching.
- Secondary (Deficit): Substitution from the same branch (`400`, `500`, `600`, `700`) ordered descending by tier.
- Tertiary (Capacity fill): Balanced combat army from remaining combat branches.
- Guard: Anti-suicide check rejecting march if estimated combat power < 45% of enemy FC.

### 3. Canonical Error Resolution Matrix
- `8004` / `9007004`: Release target. Mark queue saturated. If wait enabled, enter unified `wait_for_free_queue()`.
- `8009`: Check active marches via `get_active_marches_count(force_sync=True)`. If active >= 1, treat as `QUEUE_FULL`; else return `NO_ARMY`.
- `8027`: Release target. Record learned level ceiling `target_level - 1`. Downgrade search level and retry.
- `8035`: Reduce troops by 18%, record learned capacity, adjust payload, and retry.
- `8060` / `8062` / `8063`: Confirm exclusion in ExcludeManager.
- `16001`: Sleep random backoff `[10.0, 16.0]` seconds, retry up to 2 times.
- Blanket `80xx`: Do NOT confirm exclusion! Log unknown error, release target, and return error status.

---

## 4.4 Refactoring Map (Before & After)

### File 1: `tasks/monster.py`
- **Lines Removed**: ~800 lines of duplicated code (lines 85–262, 411–658, 689–706, 1221–1426, 1500–1574).
- **Lines Retained**: Core business logic: Rebel prerequisite validation (`_check_rebel_prerequisites`), level determination (`determine_safe_monster_level`), and target search coordination.
- **Before**: 1,642 lines with custom hero selection, custom troop scaling, inline 8035 retries, and flawed blanket 80xx exclusions.
- **After**: ~350 lines inheriting all army assembly, hero resolution, error code translation, and exclude management from `BaseTask`.

### File 2: `tasks/stronghold.py`
- **Lines Removed**: ~280 lines (lines 68–85, 149–179, 301–344, 389–444).
- **Lines Retained**: Stronghold-specific search parameters (`mapType=26`, `judianState=1`, `moveLineType=3`).
- **Before**: 507 lines with broken 8027 handling, missing returning march awareness on 8009, and redundant queue polling.
- **After**: ~140 lines cleanly calling `self.dispatch_exterior_march(map_type=26, move_line_type=3, ...)`.

### File 3: `tasks/abra.py`
- **Lines Removed**: ~600 lines (lines 116–213, 310–422, 472–613, 854–930).
- **Lines Retained**: Abra-specific business rules: 20-attack counter, killing blow threshold (`1,350,000` HP), outbound-only wait timing, and socket auto-reconnection.
- **Before**: 1,194 lines with missing 8035 handling, duplicated hero and army routines, and potential overkill race condition.
- **After**: ~450 lines utilizing unified `BaseTask` methods while maintaining specialized boss health tracking and killing blow safety.
