# Empire Game Bot - Protocol Reference (Local Copy)

Source: `e:\osmanli\.agents\skills\empire-bot\SKILL.md`

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
