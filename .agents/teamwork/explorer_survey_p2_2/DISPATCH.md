# DISPATCH — Explorer Survey 2 (Memory & CPU Leak Explorer)
**Role**: Read-only exploration agent for R3
**Working directory**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_2\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`

## Mission
Investigate Requirement R3 in detail:
1. Global references, dictionaries, and sets:
   - Trace all occurrences and lifecycles of: `_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles` in `api_server.py` and across the codebase.
   - Trace when items are added vs removed, identify missing cleanup paths.
   - Analyze memory retention from deleted castles (ensuring safe cleanup without causing re-appearance).
2. Thread lifecycle & execution cleanup:
   - Check thread ownership, exception paths, missing `try/finally` blocks, missing joins or join timeouts inside/outside locks.
   - Check stalled/orphaned threads.
3. WebSocket & open connection lifecycle:
   - Inspect WebSocket handlers, client disconnect detection, loop termination, connection multiplexing / broadcasting leaks.
   - Check SQLite query accumulation or thread pool task buildup (`asyncio.to_thread`).
4. CPU consumption bottlenecks:
   - Fast polling loops, busy waiting, frequent un-throttled recalculations.
   - Logging overhead and log truncation/tailing (ensure log reading doesn't load whole files into RAM).

## STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`

## Output
Write comprehensive report to:
`e:\osmanli\.agents\teamwork\explorer_survey_p2_2\survey_report.md`
and write your `handoff.md`.
