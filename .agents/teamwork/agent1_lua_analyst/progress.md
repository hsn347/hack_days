# Progress — Agent 1: Lua Protocol & Notify Analyst
Last visited: 2026-11-09T13:18:00Z

## Status
- [x] Read DISPATCH.md, ORIGINAL_REQUEST.md, PROJECT.md, and empire-bot SKILL.md.
- [x] Initialized BRIEFING.md and progress.md.
- [x] Inspected `notifyCtrl.lua`, `notifyIDDef_dec.lua`, and `cmdDef_dec.lua`.
- [x] Extracted all `gNotifyID` symbolic names, numeric command/subcommand IDs (CMD 1009), and handler mappings.
- [x] Analyzed `cityCtrl.lua` (`NOTIFY_CITY`, `res`, `reslist`, `saferes`, `dayMaxRes`, `updateUnCollectRes`, `openChargeQueue`, building states & levels).
- [x] Analyzed `queueCtrl.lua` (`NOTIFY_QUEUE`, `NOTIFY_PLAYER_QUEUE_CHANGE`, `NOTIFY_LOCAL_QUEUE_SYNC`, queue callbacks, queue structures).
- [x] Analyzed `armyCtrl.lua` (`NOTIFY_ARMY`, `armyInfo`, `totalArmy`, `woundedArmy`, `trainArmy`, march queues).
- [x] Analyzed `heroCtrl.lua` (`NOTIFY_HERO`, keyed by `id`, `heroMgr`, appoint/garrison status).
- [x] Analyzed `lordInfoCtrl.lua` (`NOTIFY_LORD`, `lordAuxiliary:updateLordBaseInfo`, base, skill, physical, official, npc).
- [x] Analyzed `buffCtrl.lua` (`NOTIFY_BUFF`, `syncType`: openBuff, closeBuff, closeSource, buffFinish, closeSingleBuff).
- [x] Analyzed `backpackCtrl.lua` (`NOTIFY_BACKPACK`, `syncType`: `add`, `use`, `err`, `invalidtimeTable`).
- [x] Analyzed `meritCtrl.lua` (`NOTIFY_MERITORIOUS_TASK`, `meritoriousTaskCtrl`, `updateData`, `updateIncrementData`).
- [x] Analyzed `timeRewardCtrl.lua` (`NOTIFY_TIME_REWARD`, `NOTIFY_RESET_TIME_REWARD`, harbor ships / Matou).
- [x] Analyzed `loginDataInitCtrl.lua` (retdata mapping into all modules).
- [x] Wrote comprehensive `LUA_PROTOCOL_SPEC.md`.
- [ ] Write `handoff.md`.
- [ ] Send coordination message to parent.
