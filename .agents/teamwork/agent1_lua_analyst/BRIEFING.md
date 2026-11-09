# BRIEFING — 2026-11-09T13:17:30Z

## Mission
Analyze reference Lua code in `e:\osmanli\game file\lua_src` for notification IDs, notify data structures, queue handling, building state/levels, controller data updates, and produce a comprehensive LUA_PROTOCOL_SPEC.md.

## 🔒 My Identity
- Archetype: Specification Miner
- Roles: Lua Protocol & Notify Analyst
- Working directory: e:\osmanli\.agents\teamwork\agent1_lua_analyst\
- Original parent: fb443f18-e908-4d2d-8e4b-f6fe79f74f58
- Milestone: Notification & Controller Protocol Specification

## 🔒 Key Constraints
- Read-only specification miner — do NOT implement or modify project runtime code.
- Prioritize authoritative source (`game file/lua_src`).
- Produce detailed LUA_PROTOCOL_SPEC.md, progress.md, and handoff.md.

## Loaded Skills
- **Source**: e:\osmanli\.agents\skills\empire-bot\SKILL.md
- **Core methodology**: Game bot protocol reference for Empire (and.onemt.boe.tr), command structures, game mechanics, and Lua analysis.

## Current Parent
- Conversation ID: fb443f18-e908-4d2d-8e4b-f6fe79f74f58
- Updated: 2026-11-09T13:05:01Z

## Task Summary
- **What to build**: Comprehensive Lua protocol specification document covering all gNotifyID, notify data payloads, city/queue/army/hero/lord/backpack/buff controller models and update mechanisms.
- **Success criteria**: Full extraction of gNotifyID values and meanings, payload shapes for NOTIFY_CITY, NOTIFY_QUEUE, army/hero/lord/buff/backpack/meritorious/timeReward controllers, and updateData/merge logic.
- **Interface contracts**: LUA_PROTOCOL_SPEC.md
- **Code layout**: Written to .agents/teamwork/agent1_lua_analyst/

## Key Decisions Made
- Mapped all 256 notification IDs from `notifyIDDef_dec.lua` and `cmdDef_dec.lua` under CMD 1009 (`CMD_NOTIFY_MODULE`).
- Documented exact delta vs replacement mechanisms: `cityCtrl` (`res` vs `reslist`, `saferes`, `updateUnCollectRes`, `openChargeQueue`), `queueCtrl` (queue callbacks restoring building state to `BUILD_STATE.NORMAL` and incrementing regular `lv` or `honorLv`/`hlv`), `armyCtrl`, `heroCtrl`, `lordInfoCtrl`, `buffCtrl`, `backpackCtrl`, `meritCtrl`, and `timeRewardCtrl`.
- Formulated the primary keyed list merge strategies (`blist` via `index`, `heroes` via `id`, `buffList` via `id`+`source`, march lines via `id`).

## Artifact Index
- DISPATCH.md — Dispatch instructions
- BRIEFING.md — Working memory
- progress.md — Liveness and step tracking
- ANALYSIS_PLAN.md — Technical investigation plan artifact
- LUA_PROTOCOL_SPEC.md — Protocol specification document
- handoff.md — Final handoff report
