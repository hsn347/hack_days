## 2026-11-09T13:05:11Z
You are Agent 2: Task Scanner & Whitelist Architect.
Your working directory is: e:\osmanli\.agents\teamwork\agent2_task_scanner\

You MUST read the following files before beginning:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. PROJECT.md: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
3. Domain Skill: e:\osmanli\.agents\skills\empire-bot\SKILL.md

Your Task:
Audit all bot tasks in `e:\osmanli\tasks\`, as well as `e:\osmanli\bot_manager.py` and `e:\osmanli\game_client.py`.
Scan every file to identify:
1. Every controller accessed from `init_data` (e.g. `conn.init_data.get('...')` or `self.init_data[...]`).
2. Every command sent by bot tasks (e.g. `send_command(...)`, `call(...)`).
3. Construct the comprehensive `ALLOWED_CONTROLLERS` whitelist:
   - What controllers are actively used by any task or core bot logic?
   - What controllers arrive during login/init or notifications that are safe and necessary to keep?
   - What junk/chat/unrelated controllers arrive from the server that should be dropped at ingress to save memory?
4. Define the `CRITICAL_STARTUP_CONTROLLERS` set:
   - What controllers are strictly required for the bot to run its main loop safely? (e.g. `cityCtrl`, `lordInfoCtrl`, `queueCtrl`, `armyCtrl`, etc.)
   - For each critical controller, what is the exact fallback query command (e.g. command ID and payload, such as 1002/7 for lord info, 1006/25 for city, etc.) if the server doesn't deliver it during initial login?
5. Check all task dependencies to ensure no task breaks when controllers outside `ALLOWED_CONTROLLERS` are dropped. Note specifically GEMINI.md Rule 7 regarding elf task decoupling.

Output:
Write your full audit and whitelist specification to:
`e:\osmanli\.agents\teamwork\agent2_task_scanner\CONTROLLER_WHITELIST_SPEC.md`
and write your `handoff.md` and `progress.md` in your directory.
Send a message when finished referencing the path to your report.
