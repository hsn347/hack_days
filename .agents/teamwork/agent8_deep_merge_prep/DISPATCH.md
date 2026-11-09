## 2026-11-09T13:05:20Z
You are Agent 8: Smart Deep-Merge Engine Architect (Survey & Algorithmic Design Phase).
Your working directory is: e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\

You MUST read the following files before beginning:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. PROJECT.md: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
3. Domain Skill: e:\osmanli\.agents\skills\empire-bot\SKILL.md

Your Task:
Investigate and design the central `smart_deep_merge` algorithm for Live State Memory.
Analyze how the game server sends delta updates vs full snapshots in `retdata`, `data`, and `notifyData`.
Specifically investigate:
1. List of Dictionaries merging:
   - In `cityCtrl.blist`: items are identified by `index` (or `bid`/`iid`). When the server sends an updated building (e.g. state change or level up), a naive list replace (`target['blist'] = source['blist']`) would overwrite the entire city! Or naive list append would duplicate buildings!
   - In `heroCtrl.heroes` or `heroVoyageAgCtrl`: items are identified by `id` or `heroId`.
   - In `buffCtrl`: buffs are identified by `id` or `buffId`.
   - In `queueCtrl`: queues are identified by `queueId` or `id`.
   - In `reslist`: resource list by resource type or index.
2. Dictionary merging:
   - Recursive dictionary merge (deep merge) so that partial keys updated by notifications (e.g. `{"cityCtrl": {"saferes": ...}}`) do not wipe other existing keys in `cityCtrl`.
3. Concurrency & Mutex considerations:
   - Thread safety: `game_client.py` receives packets on an asyncio event loop or background reader task while bot tasks read `conn.init_data` concurrently.
   - Design an atomic / thread-safe merge strategy without race conditions or list corruption during iteration.
4. Define the exact Python function signature and implementation pseudo-code for `smart_deep_merge(target, update, key_maps=None)`.

Output:
Write your full technical analysis, algorithmic specification, and test cases to:
`e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\DEEP_MERGE_SPEC.md`
and write your `handoff.md` and `progress.md` in your directory.
Send a message when finished referencing the path to your report.
