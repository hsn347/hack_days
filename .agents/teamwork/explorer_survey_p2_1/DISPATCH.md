# DISPATCH — Explorer Survey 1 (Admin Castles & Ops Explorer)
**Role**: Read-only exploration agent for R1 & R2
**Working directory**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_1\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`

## Mission
Investigate Requirements R1 & R2 in detail:
1. R1: Admin Castles Pagination:
   - Check how user pagination is implemented currently in `api_server.py` and `dashboard/src/...` (Users page endpoints, queries, frontend hook/table component, batch size, pagination metadata: `page`, `page_size`, `total_count`, `has_more`, etc.).
   - Check how castles are currently queried and displayed in Admin dashboard (`/api/admin/castles` or similar, SQLite queries, payload size, how `config` is currently loaded).
   - How to split summary vs details (load config on demand only).
   - How search, filter, and sorting should work on backend with pagination.
   - Local update pattern upon edit/delete without full re-fetch.
   - Super Admin vs Merchant Admin scoping and data isolation.
2. R2: Live Operations Lifecycle & Pagination:
   - Current state of live operations in `api_server.py` (`/api/admin/operations`, `/api/operations`, etc.).
   - Inspect how live operations are tracked, filtered, and reported.
   - Inspect Thread lifecycle vs BotManager state vs connection state vs actual running task vs waiting/reconnecting states.
   - Analyze the 6 allowed states: Running, Waiting for Next Cycle, Other Device Login, Reconnecting, Waiting for Re-login, Starting.
   - Identification of stalled threads / operations.
   - How to implement true backend pagination for live operations matching the Users page.
   - Avoid duplicate operations for the same castle/resource.

## STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`

## Output
Write comprehensive report to:
`e:\osmanli\.agents\teamwork\explorer_survey_p2_1\survey_report.md`
and write your `handoff.md`.
