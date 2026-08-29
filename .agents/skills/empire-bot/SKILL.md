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
