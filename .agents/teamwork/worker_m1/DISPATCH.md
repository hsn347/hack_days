# Worker M1 Dispatch: Backend & SQLite Query Optimization

- Working Directory: e:\osmanli\.agents\teamwork\worker_m1\
- Authoritative Request: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
- Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
- Project Scope: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
- Approved Remediation Plan: e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md
- Evidence Reports to Read:
  - `e:\osmanli\.agents\teamwork\explorer_survey_2\report.md`
  - `e:\osmanli\.agents\teamwork\explorer_survey_3\report.md`

## Mandate & Scope of Milestone 1
You are the Backend Implementation Worker (`teamwork_worker`).
Your exclusive file ownership for this milestone:
- `core/database.py`
- `api_server.py` (WebSocket blocking call offloading in `ws_user_status`)

## Concrete Tasks
1. **SQLite Expression / Case-Insensitive Indexes**:
   In `core/database.py` (`init_db` or schema initialization):
   Add the following indexes so that queries with `LOWER()` and `ORDER BY created_at DESC` no longer trigger full table scans:
   - `CREATE INDEX IF NOT EXISTS idx_castle_states_lower_email ON castle_states(LOWER(email));`
   - `CREATE INDEX IF NOT EXISTS idx_castle_states_lower_user ON castle_states(LOWER(user_id));`
   - `CREATE INDEX IF NOT EXISTS idx_users_lower_email ON users(LOWER(email));`
   - `CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);`
   - `CREATE INDEX IF NOT EXISTS idx_castle_states_created_at ON castle_states(created_at DESC);`
2. **Rewrite `get_all_users_with_castles` (`core/database.py:1690-1728`)**:
   Eliminate the 463-query sequential loop.
   Implement the single SQL aggregation query with `LEFT JOIN` and `GROUP BY` that computes `active_castles`, `pending_castles`, and `total_castles` in 1 single SQLite query, preserving exact backward compatibility of all dictionary keys and data formats returned to callers.
3. **Async Event Loop Offloading (`api_server.py:3063-3089`)**:
   In `ws_user_status`, replace synchronous `castles = db.get_user_castles(user_id)` with non-blocking execution via `await asyncio.to_thread(db.get_user_castles, user_id)`.
4. **Verification**:
   - Run `python tools/benchmark_admin_baseline.py` to empirically prove:
     * Query count collapsed from 463 queries to 1 single query.
     * Latency improvement confirmed.
   - Run `python -c "import core.database as db; print('Users count:', len(db.get_all_users_with_castles()))"` to confirm zero syntax errors and identical record count.

## Mandatory Rules & Integrity
- DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
- Strictly local workspace (`e:\osmanli`). NO server uploads or remote deployments.
- Write clean, transparent Python code.
- Report all verified test outputs in your `handoff.md`.


## 2026-11-02T16:43:43Z
[Message] timestamp=2026-11-02T16:43:43Z sender=44132d7d-07d0-4709-a292-a8e4727a82fd priority=MESSAGE_PRIORITY_HIGH content=You are Worker M1: Backend Implementation Worker.
Your working directory is: e:\osmanli\.agents\teamwork\worker_m1\
Authoritative user request file: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
Project Scope: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
Approved Remediation Plan: e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md
Dispatch instructions: e:\osmanli\.agents\teamwork\worker_m1\DISPATCH.md
