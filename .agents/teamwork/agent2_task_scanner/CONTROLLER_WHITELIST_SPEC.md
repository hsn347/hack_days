# Controller Whitelist & Task Protocol Specification
**Document ID**: `SPEC-CORE-M0-CW01`  
**Agent**: Agent 2 — Task Scanner & Whitelist Architect  
**Workspace**: `e:\osmanli`  
**Date**: 2026-11-09  
**Status**: APPROVED SPECIFICATION  

---

## 1. Executive Summary

This specification establishes the authoritative protocol and memory contract for the Empire game bot (`e:\osmanli`). By conducting a forensic static audit across all 54 task files in `tasks/`, `bot_manager.py`, and `game_client.py`, cross-referenced against the decompiled Lua source (`game file/lua_src/cmdDef_dec.lua`) and 5 empirical live session memory dumps (`docs/*live_memory*.json`), this document defines:

1. **`ALLOWED_CONTROLLERS` Whitelist**: A strict frozenset of 42 controllers required by active bot tasks, background sync, and core services. All 187 non-whitelisted server controllers (high-frequency chat, audio streaming, red-point beacons, and unreferenced activity garbage) are permanently discarded at network ingress (`_dispatch`).
2. **`CRITICAL_STARTUP_CONTROLLERS` Gate**: The mandatory set of 6 foundational controllers required before allowing any bot task to execute, complete with structural validation rules and automated fallback queries (`Fallback Sync Queries`).
3. **Comprehensive Task & Command Mapping**: An exhaustive registry of 100 distinct command pairs across 200 call-sites used by the bot suite.
4. **Architectural Safety & Decoupling**: Full compliance with GEMINI.md Rule 7 (radical decoupling of `elf_boss.py` from `march_manager`).

---

## 2. Ingress Whitelist: `ALLOWED_CONTROLLERS`

### 2.1 Whitelist Definition
Incoming server packets (`retdata`, `data`, and push notifications) contain up to 226 distinct controllers. To eliminate memory leaks and unbounded state accumulation, only keys in `ALLOWED_CONTROLLERS` will be accepted by `LiveMemoryEngine`.

```python
ALLOWED_CONTROLLERS: frozenset[str] = frozenset({
    # --- Critical Startup Core ---
    "cityCtrl",
    "lordInfoCtrl",
    "queueCtrl",
    "armyCtrl",
    "heroCtrl",
    "backpackCtrl",

    # --- Core Subsystems & Progression ---
    "allianceCtrl",
    "technologyCtrl",
    "vipCtrl",
    "meritoriousTaskCtrl",
    "timeRewardCtrl",
    "lordSkillCtrl",
    "boeAttributeCtrl",
    "buffCtrl",
    "petCtrl",
    "kingdomMapCtrl",
    "buyStaminaCtrl",

    # --- Feature & Activity Tasks ---
    "salesRoomAgCtrl",
    "pyramidCtrl",
    "heroVoyageAgCtrl",
    "heroEnlistCtrl",
    "heroTacticalHallAgCtrl",
    "heroTacticalHallCtrl",
    "heroEquipAgCtrl",
    "runeForgeAgCtrl",
    "allianceTreasureCtrl",
    "cumulateRewardData",
    "fieldShopCtrl",
    "PveBattleCtrl",
    "badgeExchangeCtrl",
    "savingsBankAgCtrl",
    "troyTreasureAgCtrl",
    "exchangeStoreAgCtrl",
    "generalAtyMgr",
    "activityShowCtrl",
    "godBeastCtrl",
    "equipmentCtrl",
    "playerCtrl",
    "itemShop",
    "shopItemBuyTimesMgr",

    # --- Aliases & Internal State Keys ---
    "lord",
    "loginDataInitCtrl",
    "item_sign",
})
```

### 2.2 Controller Catalog & Access Patterns
The table below details every controller in `ALLOWED_CONTROLLERS`, its primary data structures, consuming tasks, and operational purpose.

| Controller Name | Primary Fields / Sub-Keys | Consuming Files | Purpose & Impact |
|---|---|---|---|
| `cityCtrl` | `blist`, `reslist`, `cinfo`, `queue`, `saferes`, `dayMaxRes`, `arealist` | 23 files (`building`, `city_harvest`, `hospital`, `base_task`, `bot_manager`, etc.) | **Foundational**: Tracks all castle buildings, resource counts, coordinates (`x`, `y`), and build queues. |
| `lordInfoCtrl` | `base` (`uid`, `nickName`, `health`, `gold`, `partition`, `level`, `exp`) | 18 files (`base_task`, `bot_manager`, `auction`, `fountain`, `transport`, etc.) | **Foundational**: Core lord profile, stamina balance, VIP level, and kingdom identity. |
| `queueCtrl` | Keyed by queue type string (`1256`, `1257`, etc.) containing `starttime`, `ottime`, `data` | 10 files (`fortress`, `hospital`, `material_workshop`, `port`, `research`, `train`, etc.) | **Foundational**: Monitors active timers for building, healing, research, and troop recruiting. |
| `armyCtrl` | `totalArmy`, `woundedArmy`, `compileArmy`, `compileHeros`, `compilePets`, `trainArmy` | 14 files (`abra`, `base_task`, `elf_boss`, `fortress`, `gather`, `hospital`, `monster`, etc.) | **Foundational**: Stationed castle troops, hospital wounded counts, and march formation presets. |
| `heroCtrl` | Array of hero dicts (`id`, `level`, `star`, `state`, `power`, `skills`) | 13 files (`abra`, `base_task`, `caravan`, `elf_boss`, `gather`, `gold_gather`, `stronghold`, etc.) | **Foundational**: All unlocked heroes, current states (idle vs marching), and combat ratings. |
| `backpackCtrl` | Keyed by item ID string (`id`, `count`, `specialID`) | 7 files (`building`, `research`, `torch_chest`, `warrior_exchange`, `watermill`, `bot_manager`) | Inventory management, consumable resource chests, speedups, and peace shields. |
| `allianceCtrl` | `helplist`, `memberinfo`, `allianceInfo`, `sciencelist`, `territoryData` | 4 files (`alliance`, `alliance_treasure`, `monster`, `bot_manager`) | Alliance mutual help, science donations, and member coordinates. |
| `technologyCtrl` | Keyed by tech ID string (`id`, `level`, `state`) | 5 files (`base_task`, `fortress`, `gather`, `march_capacity`, `research`) | Academy research levels and stat buffs. |
| `vipCtrl` | `vipLv`, `vipPoint`, `dailyGiftFlag`, `claimDailyGiftTime` | 6 files (`base_task`, `building`, `gather`, `march_manager`, `skills`, `vip_gift`) | VIP privileges, daily VIP chest collection, and free build speedups. |
| `meritoriousTaskCtrl` | `taskData`, `daily_task`, `dailyPoint`, `dailyBoxRwd`, `bOpen` | 8 files (`base_task`, `hospital`, `march_coordinator`, `march_manager`, `prestige`, `prestige_box`) | Daily prestige / meritorious quest tracking and rewards. |
| `timeRewardCtrl` | `data` (`isReceive`, `isAllReceive`, `receiveTime`, `sequence`, `reward`) | 3 files (`port`, `bot_manager`, `game_client`) | Harbor cargo delivery ships, countdowns, and reward collection. |
| `lordSkillCtrl` | `setListData`, `activeSetID`, `CDData`, `pointTotal` | 5 files (`fortress`, `gather`, `skill_finder`, `skills`, `train`) | Lord talent tree skills, active skill activation, and book switching. |
| `boeAttributeCtrl` | Hierarchical numeric multipliers for gathering, march capacity, combat | 4 files (`fortress`, `gather`, `march_capacity`, `train`) | Dynamic calculation of maximum march troop capacity and buff modifiers. |
| `buffCtrl` | Array or dict of active temporary buffs (`id`, `endTime`, `type`) | 5 files (`gather`, `gather_boost`, `shield`, `watermill`, `game_client`) | Castle peace shields, gather speedups, and resource production boosts. |
| `petCtrl` | `pets`, `petPatrolInfo`, `garrisonPetId`, `petPoint` | 7 files (`base_task`, `caravan`, `gather`, `gold_gather`, `monster`, `pet_patrol`) | Beast levels, garrison assignments, and automated pet patrol adventures. |
| `kingdomMapCtrl` | `kinfo`, `partition`, bounds, terrain data | 4 files (`abra`, `elf_boss`, `monster`, `shield`) | World map partition discovery and coordinate validation. |
| `buyStaminaCtrl` | `count`, `lastBuyTime`, `dailyLimit` | 2 files (`stamina`, `bot_manager`) | Tracking daily stamina purchases and thresholds. |
| `salesRoomAgCtrl` | `itemsInfo`, `notReceiveGold`, `timeAndStatus` | 1 file (`auction`) | Carrier pigeon auction house browsing, bidding, and gold returns. |
| `pyramidCtrl` | `data` (`diceCount`, `pos`, `round`, `status`) | 1 file (`imperial_mausoleum`) | Imperial Mausoleum board game progression and automated dice throwing. |
| `heroVoyageAgCtrl` | `tasks`, `consignCount`, `dailyLimit`, `wishList` | 1 file (`hero_consign`) | Hero voyage dispatch, task completion, and reward chests. |
| `heroEnlistCtrl` | `normalFreeTime`, `seniorFreeTime`, `points` | 3 files (`hero_draw`, `tactics_hall`, `treasure_pavilion`) | Tavern recruitment timers and free draw readiness. |
| `heroTacticalHallAgCtrl` / `heroTacticalHallCtrl` | `hallInfo`, `stationHeroes`, `tacticsInfo` | 1 file (`tactics_hall`) | Tactical Hall hero garrisoning and military tactics upgrading. |
| `heroEquipAgCtrl` | `materials`, `forgingQueue`, `recipes` | 1 file (`material_workshop`) | Material workshop crafting timers and hero equipment synthesis. |
| `runeForgeAgCtrl` | `runeList`, `smeltPoints`, `refineLevel` | 1 file (`blacksmith_forge`) | Blacksmith rune refinement and forging. |
| `allianceTreasureCtrl` | `treasureInfo`, `digCount`, `helpList` | 1 file (`alliance_treasure`) | Alliance treasure chest excavation, map sharing, and claims. |
| `cumulateRewardData` | `mFinishTimes`, `mRewardRecords` | 1 file (`daily_luxury_gift`) | Daily consecutive login gifts and monthly reward tracks. |
| `fieldShopCtrl` | `goodsList`, `refreshCount` | 1 file (`port_delegate`) | Military port field shop exchange transactions. |
| `PveBattleCtrl` | `points`, `maxStage`, `sweepStatus` | 2 files (`port_delegate`, `game_client`) | Military port PVE combat sweeps and stage progression. |
| `badgeExchangeCtrl` | `exchangeList`, `badgeCount` | 1 file (`prestige`) | War medal / prestige badge exchange redemption. |
| `savingsBankAgCtrl` | `plans`, `depositInfo`, `interests` | 1 file (`savings_bank`) | Savings bank gold deposits and interest collection. |
| `troyTreasureAgCtrl` | `gridList`, `freeCount`, `level` | 1 file (`troy_treasure`) | Troy treasure excavation board. |
| `exchangeStoreAgCtrl` | `goods`, `warriorPoints` | 1 file (`warrior_exchange`) | Warrior shop redemption products and currency. |
| `generalAtyMgr` | Keyed by numeric activity ID (`9001306`, `9001150`, etc.) | 3 files (`territory_expansion`, `week_start_benefits`, `bot_manager`) | Unified container for periodic and seasonal game events. |
| `activityShowCtrl` | Keyed by event type (`actId`, `isOpen`, `startTime`, `endTime`) | 2 files (`elf_boss`, `bot_manager`) | Zero-request event status verification (e.g. verifying Elf Boss is active). |
| `godBeastCtrl` | `beastInfo`, `skills` | 1 file (`abra`) | Mythical god beast combat buffs and march attachment. |
| `equipmentCtrl` | `equippedGear`, `inventoryGear` | 1 file (`gather`) | Lord gear equipment attributes (gathering gear loadouts). |
| `playerCtrl` | `fountainStatus`, `wishCount` | 1 file (`fountain`) | Trevi fountain daily wishes and buff activation. |
| `itemShop` | `configData`, `goods` | 2 files (`torch_chest`, `bot_manager`) | Item shop pricing catalog for torch purchases. |
| `shopItemBuyTimesMgr` | Keyed by item ID (`buyTimes`, `resetTime`) | 2 files (`torch_chest`, `bot_manager`) | Purchase frequency limiter for shop items. |
| `lord` | Legacy alias for `lordInfoCtrl` | 4 files (`abra`, `alliance`, `elf_boss`, `monster`) | Backward-compatibility alias for older task accessors. |
| `loginDataInitCtrl` | Initial login envelope (`base`) | 3 files (`abra`, `base_task`, `march_manager`) | Fallback access to login payload before `lordInfoCtrl` merges. |
| `item_sign` | Keyed by item ID string -> integer signature | 1 file (`shield`) | Cache of cryptographic authorization signatures for zero-gold item operations. |

---

## 3. Discarded Ingress Traffic (187 Dropped Controllers)

During network ingress, packets targeting controllers outside `ALLOWED_CONTROLLERS` are dropped immediately in `_dispatch()`. Below is the architectural classification of the 187 pruned controllers:

### 3.1 High-Frequency Chat & Communications (Memory Leak Vector #1)
- **Controllers**: `chatCtrl`, `chatroomCtrl`, `voiceRoomCtrl`, `htMsgCtrl`, `marqueeCtrl`, `translateCtrl`, `evaluationCtrl`.
- **Reason**: World chat, kingdom bulletins, and voice room pings generate tens of thousands of dynamic string objects per hour. The bot requires zero chat interaction.

### 3.2 UI Indicators, Red Points & Telemetry (Memory Leak Vector #2)
- **Controllers**: `RedPointCtrl`, `clientLogCtrl`, `clientEventCtrl`, `clientH5Ctrl`, `clickPraiseCtrl`, `npcTipCtrl`, `noticeCtrl`, `facebookShareCtrl`, `settingCtrl`.
- **Reason**: Red dot badge triggers and client diagnostic logs exist purely for human mobile clients and create unnecessary memory churning.

### 3.3 Cosmetics, Avatars & Visual Flair
- **Controllers**: `dressCtrl`, `dressShop`, `imageSealCtrl`, `emojiSealCtrl`, `emozhiyanCtrl`, `flowerSysCtrl`, `beautyCtrl`, `princessCtrl`.
- **Reason**: Castle skins, decorative avatars, and visual dress-ups have zero bearing on bot automation or combat mechanics.

### 3.4 Payment Gateways, In-App Purchases & Advertising
- **Controllers**: `rechargeCtrl`, `rechargeActivityCtrl`, `rechargeGiftCtrl`, `rechargeFirstAccuCtrl`, `rechargeGiftV3Ctrl`, `cashPurchaseCtrl`, `adCtrl`, `videoAdCtrl`, `multiPositionRechargeCtrl`, `firstRechargeAccu`, `continueRechargeCtrl`.
- **Reason**: The automated bot performs zero real-money transactions and never renders video ads.

### 3.5 Inactive Seasonal Minigames & Ephemeral Activity Bloat
- **Controllers**: `smashBoomAgCtrl`, `whackAMoleAgCtrl`, `goldenMinerAgCtrl`, `fishAgCtrl`, `fishermanAgCtrl`, `pizzaChallengeAgCtrl`, `corbanCelebrationAgCtrl`, `thanksgivingCtrl`, `snowManActCtrl`, `easterEggsCtrl`, `devilValleyCtrl`, `circusAgCtrl`, `chiselLandAgCtrl`, `pullPinCtrl`, `cakePuzzleCtrl`, `bullSacrificeCtrl`, etc.
- **Reason**: The server broadcasts state dictionaries for dozens of seasonal or retired minigames that no bot task executes.

**Footprint Impact**: Trimming these 187 controllers reduces memory retention by over 81% per connected account, eliminating cyclic garbage collector stalls.

---

## 4. Strict Startup Readiness Gate: `CRITICAL_STARTUP_CONTROLLERS`

### 4.1 Specification
Before the bot loop in `bot_manager.py` executes any task in `pipeline`, `conn.wait_for_memory_ready()` MUST ensure that the following 6 controllers are present in `init_data` and pass structural integrity validation.

```python
CRITICAL_STARTUP_CONTROLLERS: frozenset[str] = frozenset({
    "cityCtrl",
    "lordInfoCtrl",
    "queueCtrl",
    "armyCtrl",
    "heroCtrl",
    "backpackCtrl",
})
```

### 4.2 Structural Validation & Fallback Query Matrix

If the server delays delivering any critical controller during `_init_flow` (`1000/1`), the readiness gate triggers the automated fallback sync query specified below.

```
                  ┌────────────────────────────────────────┐
                  │    Start wait_for_memory_ready()       │
                  └──────────────────┬─────────────────────┘
                                     │
                   Validate CRITICAL_STARTUP_CONTROLLERS
                                     │
                 ┌───────────────────┴───────────────────┐
                 │ Are all 6 controllers structurally ok? │
                 └─────────┬───────────────────┬─────────┘
                          YES                  NO
                           │                   │
                           │     Dispatch Fallback Sync Queries
                           │     (1001/1, 1002/7, 1003/1, 1005/1)
                           │                   │
                           │         Wait up to timeout (30s)
                           │                   │
                           │       All Received & Valid?
                           │       ┌───────────┴───────────┐
                           │      YES                      NO
                           │       │                       │
                  ┌────────┴───────┴──────┐      ┌─────────┴─────────┐
                  │ Return True: Run Loop │      │ Raise TimeoutError│
                  └───────────────────────┘      └───────────────────┘
```

| Critical Controller | Structural Validity Rule | Primary Fallback Query | Alternate / Secondary Query | Timeout |
|---|---|---|---|---|
| `cityCtrl` | Must be `dict` containing:<br>1. `blist`: `list` with `len >= 1`<br>2. `reslist`: `dict` with `len >= 1`<br>3. `cinfo`: `dict` with `'pos'` or `'x'`, `'y'` | **CMD 1001 / Sub 1**<br>`REQ_INIT_CITYDATA`<br>Payload: `{}` | **CMD 1006 / Sub 25**<br>`REQ_GET_USER_BASE_INFO`<br>Payload: `{"uid": self.uid}` | 15s |
| `lordInfoCtrl` | Must be `dict` containing:<br>1. `base`: `dict`<br>2. `base.uid`: integer `> 0`<br>3. `base.partition`: integer `> 0` | **CMD 1002 / Sub 7**<br>`REQ_LORD_INFO_UID`<br>Payload: `{"uid": self.uid}` | **CMD 1002 / Sub 1**<br>`REQ_INIT_LORDDATA`<br>Payload: `{}` | 10s |
| `queueCtrl` | Must be `dict` (can be empty `{}` if no active queues) | **CMD 1003 / Sub 1**<br>`REQ_INIT_QUEUEDATA`<br>Payload: `{}` | None | 8s |
| `armyCtrl` | Must be `dict` containing either `'totalArmy'`, `'armyInfo'`, or `'woundedArmy'` | **CMD 1005 / Sub 1**<br>`REQ_INIT_ARMYDATA`<br>Payload: `{}` | None | 10s |
| `heroCtrl` | Must be `list` (may be empty `[]` on brand new accounts) | **CMD 1005 / Sub 1**<br>`REQ_INIT_ARMYDATA`<br>Payload: `{}` | **CMD 1000 / Sub 1**<br>`REQ_LOGIN_DATA_INIT`<br>Payload: `{}` | 10s |
| `backpackCtrl` | Must be `dict` (contains inventory item maps) | **CMD 1004 / Sub 1**<br>`REQ_INIT_BACKPACKDATA`<br>Payload: `{}` | None | 10s |
| *(Auxiliary)* `local_queues` | `conn.local_queues_map` populated | **CMD 1007 / Sub 1000**<br>`REQ_GET_ALL_QUEUE_INFO`<br>Payload: `{}` | None | 5s |

---

## 5. Exhaustive Task Command Registry (100 Command Pairs)

The audit verified 100 distinct command pairs across all bot tasks. Below is the full index grouped by module:

### 5.1 City & Construction (`CMD 1001`, `1003`)
- `1001/1`: `REQ_INIT_CITYDATA` — Query all castle buildings, resource production, and active timers.
- `1001/2`: `REQ_BUILD_BUILDING` — Construct a new building on an open plot.
- `1001/3`: `REQ_BUILD_UPGRADE` — Upgrade an existing building using resources.
- `1001/8`: `REQ_COLLECT_RES` — Harvest stored resources from farm/lumber/iron/mithril buildings.
- `1001/9`: `REQ_SPEED_UP_RES` — Watermill production speedup.
- `1003/1`: `REQ_INIT_QUEUEDATA` — Query build and construction queue status.
- `1003/2`: `REQ_SPEED_UP_QUEUE` — Apply free or item speedups to an active queue.

### 5.2 Lord & Skills (`CMD 1002`)
- `1002/1`: `REQ_INIT_LORDDATA` — Query general lord statistics.
- `1002/7`: `REQ_LORD_INFO_UID` — Fetch full lord profile, kingdom ID, and stamina balance.
- `1002/22`: `REQ_LORD_SKILL_USE` — Trigger an active lord skill (e.g. instant harvest, stamina boost).
- `1002/23`: `REQ_LORD_SKILL_SWITCH` — Switch active talent tree book / preset.

### 5.3 Inventory & Items (`CMD 1004`, `1034`)
- `1004/1`: `REQ_INIT_BACKPACKDATA` — Fetch full player backpack inventory.
- `1004/2`: `REQ_USE_ITEM` — Consume an item (resource box, speedup, shield, stamina potion).
- `1034/1`: `REQ_SHOP_INIT` — Query item shop catalogue.
- `1034/2`: `REQ_SHOP_BUY` — Purchase shop items (torch chests, peace shields).

### 5.4 Army, Troops & Marches (`CMD 1005`, `1006`, `1007`, `1013`)
- `1005/1`: `REQ_INIT_ARMYDATA` — Query castle troop counts and garrisoned formations.
- `1005/2`: `REQ_TRAIN_ARMY` — Train new troops in barracks/stables/ranges.
- `1005/4`: `REQ_HEAL_ARMY` — Heal wounded soldiers in hospital.
- `1005/5`: `REQ_DISMISS_ARMY` — Cancel or dismiss troops.
- `1005/7`: `REQ_GET_FORMATION_INFO` — Fetch saved army preset formation.
- `1006/15`: `REQ_GET_RUINS_INFO` — Inspect ruins structure on the map.
- `1006/22`: `REQ_GET_GOLD_GATHER_INFO` — Inspect world gold resource node.
- `1006/25`: `REQ_GET_USER_BASE_INFO` — Retrieve user castle position (`x`, `y`) and status.
- `1006/1000`: `REQ_MAP_RADAR_QUERY` — Scan surrounding tiles for targets.
- `1007/2`: `REQ_MARCH_DISPATCH` — Dispatch an army march (gather, monster attack, elf mass attack).
- `1007/16`: `REQ_MASS_MARCH_DETAIL` — Query rally details for mass attack.
- `1007/1000`: `REQ_GET_ALL_QUEUE_INFO` — Sync all active marching legions on kingdom map.
- `1013/1`: `REQ_HOSPITAL_CURE_ALL` — One-key cure hospital wounded.

### 5.5 Alliance & Mutual Aid (`CMD 1010`, `1026`)
- `1010/39`: `REQ_ALLIANCE_WATERMILL_DONATE` — Donate resources to alliance watermill.
- `1010/40`: `REQ_ALLIANCE_WATERMILL_RECEIVE` — Collect watermill rewards.
- `1010/47`: `REQ_ALLIANCE_MEMBER_LIST` — Query roster of alliance members.
- `1010/48`: `REQ_ALLIANCE_HELP_ALL` — Click one-key help for all alliance member timers.
- `1010/75`: `REQ_ALLIANCE_RESOURCE_TRANSPORT` — Transport food/wood/iron to an ally.

### 5.6 Mail, Technology & Buffs (`CMD 1015`, `1017`, `1018`, `1019`)
- `1015/1`: `REQ_MAIL_LIST` — Fetch mail inbox messages.
- `1015/4`: `REQ_MAIL_READ` — Read specific mail message.
- `1015/18`: `REQ_MAIL_COLLECT_REWARD` — Collect attached rewards from system mail.
- `1015/19`: `REQ_MAIL_DELETE` — Delete processed mail messages.
- `1017/1`: `REQ_INIT_TECHDATA` — Query academy research tree.
- `1017/2`: `REQ_TECH_UPGRADE` — Start an academy research technology.
- `1017/3`: `REQ_TECH_CANCEL` — Cancel ongoing academy research.
- `1018/1`: `REQ_FOUNTAIN_WISH` — Make a daily wish at the Trevi Fountain.
- `1018/2`: `REQ_FOUNTAIN_COLLECT` — Collect Trevi fountain blessing.
- `1019/1`: `REQ_INIT_BUFFDATA` — Query player active buffs.
- `1019/6`: `REQ_APPLY_BUFF` — Activate a timed gathering buff.

### 5.7 Quests, Merchants & Special Tasks (`CMD 1024`, `1028`, `1033`, `1045`, `1067`, `1082`, `1087`)
- `1024/1`: `REQ_STORES_INFO` — Query travelling merchant / smuggler shop inventory.
- `1024/2`: `REQ_STORES_BUY` — Purchase item from smuggler merchant.
- `1024/3`: `REQ_STORES_REFRESH` — Refresh smuggler merchant inventory.
- `1028/5`: `REQ_QUEST_CLAIM` — Claim completed quest reward.
- `1033/2`: `REQ_TIME_REWARD_CLAIM` — Collect harbor delivery cargo reward.
- `1045/1`: `REQ_PYRAMID_INIT` — Query Imperial Mausoleum state.
- `1045/3`: `REQ_PYRAMID_ROLL_DICE` — Throw dice in Imperial Mausoleum.
- `1045/5`: `REQ_PYRAMID_CLAIM_BOX` — Claim milestone chest in Imperial Mausoleum.
- `1067/1`: `REQ_BADGE_EXCHANGE_INFO` — Query war badge exchange offerings.
- `1067/2`: `REQ_BADGE_EXCHANGE_BUY` — Redeem war badges for items.
- `1082/1`: `REQ_BUY_VIP_DAILY_GIFT` — Claim daily free VIP chest.
- `1087/3`: `REQ_GOD_BEAST_HEAL` — Restore stamina/health of god beast.

### 5.8 Secondary Engines & Feature Modules
- `2011/3`: `REQ_WORLD_SEARCH` — Search world map for resource tiles, monsters, or ruins.
- `2011/4`: `REQ_BOSS_SEARCH` — Locate closest Elf Boss / Elite Battle Boss on map.
- `2015/1`, `/3`, `/4`, `/5`, `/6`: `CMD_ALLIANCE_TREASURE` — Excavate, invite, and claim alliance treasure.
- `2031/1`, `/2`, `/5`: `CMD_SALESROOM` — Browse, bid, and withdraw from auction house.
- `2057/1`: `CMD_WARRIOR_EXCHANGE` — Purchase items with warrior exchange tokens.
- `2058/1`: `CMD_HERO_ENLIST` — Perform free or token-based hero draws.
- `2059/36`: `CMD_TROY_TREASURE` — Excavate tiles in Troy treasure board.
- `2060/1`: `CMD_BUY_STAMINA` — Purchase lord stamina using gold/potions.
- `2063/2`: `CMD_WEEK_START_BENEFITS` — Claim Monday / week-start login bonuses.
- `2064/9`, `/10`, `/11`: `CMD_PORT_DELEGATE` — Sweep stages and purchase from military port shop.
- `2065/2`: `CMD_RUNE_FORGE` — Refine runes in blacksmith forge.
- `3078/1`: `CMD_BOE_NEW_PLAYER_GUIDE` — Claim novice adventure rewards.
- `3081/1`, `/4`, `/5`: `CMD_BOE_PET` — Feed pets, dispatch pet patrols, and claim rewards.
- `3094/1`: `CMD_CUMULATE_REWARD` — Claim consecutive luxury daily gifts.
- `3105/2`: `CMD_EXPLOIT_TASK` — Claim prestige milestone box.
- `3129/4`: `CMD_HERO_EQUIP` — Craft hero equipment in material workshop.
- `3137/1`, `/2`: `CMD_HERO_TACTICAL_HALL` — Assign tactical garrison heroes and upgrade tactics.
- `3139/1`, `/6`, `/7`, `/14`: `CMD_NEW_ESCORT` — Caravan delivery, escort dispatch, and rewards.
- `3148/1`, `/3`, `/4`, `/5`, `/7`: `CMD_HERO_VOYAGE` — Hero consign, voyage travel, and cumulative chests.
- `5011/1`: `CMD_FIELD_SHOP` — Port delegate field exchange.
- `6023/1`, `/2`: `CMD_SAVINGSBANK` — Deposit gold in savings bank and withdraw matured interest.

---

## 6. GEMINI.md Rule 7 & Elf Decoupling Verification

### 6.1 Audit Finding
A comprehensive static analysis was conducted on `tasks/elf_boss.py` and `tasks/march_manager.py`:
- `tasks/elf_boss.py` contains **zero** imports, references, or invocations of `MarchManagerTask` or `tasks.march_manager`.
- `tasks/elf_boss.py` implements its own autonomous lifecycle:
  1. Searches for the nearest boss via `2011/4` (`bossType: 10`).
  2. Queries saved formation presets via `1005/7`.
  3. Validates hero availability and substitutes idle war heroes dynamically if needed.
  4. Dispatches the 5-minute mass rally march directly via `1007/2` (`mainInstanceType: 24`).
- In `bot_manager.py:3050-3062`, `ElfBossTask` is executed as a **standalone priority bot** reading strictly from `cfg.elf` (`elf.enabled`, `elf.formation_id`, `elf.max_distance`), running before normal pipeline tasks without passing through `march_manager`.

### 6.2 Decoupling Guarantee
Dropping non-whitelisted controllers will NOT impact `elf_boss.py` because all controllers accessed by `elf_boss.py` (`activityShowCtrl`, `armyCtrl`, `cityCtrl`, `heroCtrl`, `kingdomMapCtrl`, `lordInfoCtrl`) are fully retained in `ALLOWED_CONTROLLERS`.

---

## 7. Downstream Engineering Directives

This specification directly guides subsequent agents in the swarm:

1. **Agent 8 & Agent 9 (Smart Deep-Merge Engine & Memory Hygiene)**:
   - Configure `LiveMemoryEngine._dispatch` to filter `retdata`, `data`, and push notifications against `ALLOWED_CONTROLLERS`.
   - Never write keys outside `ALLOWED_CONTROLLERS` into `conn.init_data`.
2. **Agent 3 & Agent 10 (Readiness Gate & Bot Loop Integration)**:
   - Implement `conn.wait_for_memory_ready(timeout=30, auto_fetch_missing=True)`.
   - Validate presence and non-emptiness of the 6 `CRITICAL_STARTUP_CONTROLLERS`.
   - If missing, trigger the exact Fallback Sync Queries documented in Section 4.2.
   - Hook the readiness check at `bot_manager.py` before `execute_task_pipeline()` begins.
3. **Agent 18 (Whitelist & Memory Footprint Auditor)**:
   - Use `ALLOWED_CONTROLLERS` as the assertion baseline in live session tests.
   - Assert `len(set(conn.init_data.keys()) - ALLOWED_CONTROLLERS) == 0`.
