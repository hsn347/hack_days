# BRIEFING — 2026-11-03T01:09:00Z

## Mission
Comprehensive read-only investigation and survey of Requirement R3: Memory and CPU Leak Explorer in Empire Bot backend (api_server.py, bot_manager.py, core/database.py, core/session_manager.py, proxy/proxy_manager.py).

## 🔒 My Identity
- Archetype: explorer
- Roles: Memory & CPU Leak Explorer (R3)
- Working directory: e:\osmanli\.agents\teamwork\explorer_survey_p2_2\
- Original parent: 849edb08-8a01-463a-a4d9-889f072bccf9
- Milestone: Phase 0 Exploration & Survey

## 🔒 Key Constraints
- Read-only investigation — do NOT implement or modify any codebase files.
- STRICT PROHIBITION: You MUST NOT open, read, modify, format, rename, delete, move, or touch: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- No remote server uploads, deploys, or production connections. Local workspace only.
- Write reports, briefings, progress only to own directory: `e:\osmanli\.agents\teamwork\explorer_survey_p2_2\`.

## Current Parent
- Conversation ID: 849edb08-8a01-463a-a4d9-889f072bccf9
- Updated: 2026-11-03T01:09:00Z

## Investigation State
- **Explored paths**:
  - `api_server.py`: Global references, `_bot_thread` lifecycle, thread cleanup, WebSocket loops, log pruning, `_get_real_status` and DB queries.
  - `bot_manager.py`: `run_loop`, `run_once`, 1-second busy sleep, stop event mechanics.
  - `core/session_manager.py`: Session caching, `_LAST_AUTH_ERRORS`.
  - `core/database.py`: `get_connection` SQLite WAL mode and PRAGMA overhead.
  - `proxy/proxy_manager.py`: `_castle_bindings` leak on delete.
- **Key findings**:
  1. Complete lifecycle leaks in global dicts: `_castle_emails` never popped in `_bot_thread` finally; early returns (auth error lines 708, 715) skip finally leaving `_threads`, `_stop_events`, `_log_qs`, `_castle_users`, `_castle_emails` dangling; `_deleted_castles` is never cleared; `_user_stopped` retains entries permanently if stopped manually.
  2. Missing thread joins everywhere: Zero calls to `thread.join()` across `stop_bot`, `stop_all_bots`, `delete_castle`, `delete_user`, `_restart_worker`. Threads become detached orphans when stopped or deleted.
  3. WebSocket disconnect blindness & SQLite task buildup: `ws_logs`, `ws_status`, `ws_user_status` never read from WebSocket, so client disconnects are undetectable unless a write fails. `ws_user_status` calls `asyncio.to_thread(_sync_collect_user_statuses)` every 0.8s, generating massive SQLite connection churn and ThreadPoolExecutor saturation.
  4. CPU bottlenecks: `bot_manager.py` loops with `await asyncio.sleep(1.0)` 1500 times per cycle instead of waiting on `asyncio.Event`; `prune_log_file_24h` loads whole files into RAM with `f.readlines()` every 1000 lines; `importlib.reload` executed on every bot start inside `_bot_thread`.
- **Unexplored areas**: None for R3 scope.

## Key Decisions Made
- Consolidate all findings into a structured, highly actionable `survey_report.md` detailing every bug location, root cause, exact code lines, and proposed architectural solution, followed by standard 5-component `handoff.md`.

## Artifact Index
- DISPATCH.md — Task assignment from orchestrator
- BRIEFING.md — Working memory and status
- progress.md — Liveness heartbeat and milestone tracker
- survey_report.md — Comprehensive survey report
- handoff.md — 5-component handoff report
