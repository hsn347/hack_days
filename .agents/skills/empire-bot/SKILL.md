---
name: empire-bot
description: Game bot protocol reference for Empire (and.onemt.boe.tr). Contains all discovered commands, hero system, army mechanics, and Lua source analysis. Activate when working on any bot code in the osmanli workspace.
---

# Empire Game Bot - Protocol Reference

## How to Use
This skill contains pre-extracted knowledge from the game's decompiled Lua source files.
- **CONTEXT.md** (`e:\osmanli\CONTEXT.md`): Full protocol documentation
- **LUA_COMMANDS_COMPACT.txt** (`e:\osmanli\LUA_COMMANDS_COMPACT.txt`): All important command IDs
- **LUA_REFERENCE.md** (`e:\osmanli\LUA_REFERENCE.md`): Extracted function bodies from Lua source

## When You Need More Detail
If the compact references above don't have enough info, ONLY THEN read the full Lua source files:
- `e:\osmanli\lua_src\cmdDef_dec.lua` - All command definitions (143KB, use LUA_COMMANDS_COMPACT.txt instead)
- `e:\osmanli\lua_src\armyCtrl_dec.lua` - Army/formation logic
- `e:\osmanli\lua_src\worldDispatchArmyView.lua` - Hero auto-selection (binary, search with grep)
- `e:\osmanli\lua_src\commonArmyInfo.lua` - Army info management (binary, search with grep)
- `e:\osmanli\lua_src\gameFunctions_dec.lua` - Helper functions

## Quick Command Reference

### Player Info
| Command | Description | Data |
|---------|-------------|------|
| 1002/9 | Get player UID | `{}` |
| 1006/25 | Castle info | `{"uid": UID}` |
| 1002/7 | Full player info | `{"uid": UID}` |

### Search (2011/3)
| mapType | Target | subType |
|---------|--------|---------|
| 5 | Resources | 1=mithril, 2=iron, 3=wood, 4=food, 5=gold |
| 6 | Invaders | 0 |
| 7 | Ruins | 0 |
| 26 | Stronghold | 0 |
| 35 | Rebels | 0 |

### March (1007/2)
Required fields: needSend, heros, pets, runePages, matrixType, mapId, moveLineType, data.to, data.army

### Hero Consign / Voyage (3148)
- Module in init_data: `heroVoyageAgCtrl`
- Daily limit: 5 (`dailyLimit - consignCount`)
- Subcommands:
  - `3148/1`: Choose hero (`{"cId": heroId}`)
  - `3148/2`: Set wish list (`{"wishList": [id1, id2, ...]}`)
  - `3148/3`: Voyage travel (`{"amount": 1, "isItem": 0, "isGuide": false}`)
  - `3148/4`: Start consign task (`{"index": task_index_1based, "heroIds": [id1, id2, ...]}`)
  - `3148/5`: Award consign task (`{"index": task_index_1based}`)
  - `3148/6`: Refresh tasks
  - `3148/7`: Consign cumulative gift chest (15 tasks)
  - `3148/8`: Consign shop buy (`{"id": id, "count": count}`)

### Errors
| Code | Meaning |
|------|---------|
| 0 | Success |
| 9007020 | Hero busy on another march |
| 8009 | Insufficient troops in castle |

### Hero Classification
- `5501xxx` = War/Combat heroes
- `5502xxx` = Development/Gathering heroes

## Bot Source Files
- `e:\osmanli\Attack_.py` - Main bot (BotEngine + run_bot)
- `e:\osmanli\Attack_ Invaders.py` - Invader attack bot
- `e:\osmanli\simple_cmd.js` - Manual command testing via Frida
- `e:\osmanli\exclude_history.json` - Excluded targets per account

## Mandatory Workflow Rules
- **No Code/Command Changes Without a Report (إلزامية إرفاق تقرير فني)**: Never modify any bot code, file, server service, or execution command without an accompanying report. For substantive changes, write a dedicated `.md` artifact report. For very simple/minor changes, provide a clear, concise in-chat technical report detailing: (1) exact file and lines modified, (2) root cause/reason, and (3) expected impact.
