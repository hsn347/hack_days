# Explorer 2 Dispatch: Backend, Database, Concurrency & Security Investigation

- Working Directory: e:\osmanli\.agents\teamwork\explorer_survey_2\
- Authoritative Request: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
- Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md

## Scope & Mandate
Examine the backend code (`api_server.py`, `bot_manager.py`, `database/`, tasks and controllers):
1. **Database & Queries**: Inspect SQLite database schema (`database/castles.db`), table indexes, slow queries, N+1 patterns, unbounded SELECTs, connection pooling and lifetime, WAL mode, transaction boundaries, and resource cleanup.
2. **Concurrency & Data Integrity**: Audit for lost updates, race conditions between concurrent requests/threads, lack of optimistic concurrency control (OCC)/versioning, transaction management, and idempotency in mutations.
3. **Data Isolation & Access Control**: Check castle ID tampering defense, cross-user/cross-castle data bleeding, and multi-account boundary security.
4. **Backend Resource Leaks**: Identify long-lived unmanaged memory allocations, background task accumulation, unclosed connections or handles.

Deliver comprehensive report and `handoff.md` in your directory.

## 2026-11-02T16:17:11Z
[Message] timestamp=2026-11-02T16:17:11Z sender=44132d7d-07d0-4709-a292-a8e4727a82fd priority=MESSAGE_PRIORITY_HIGH content=You are Explorer 2: Backend & Database Auditor Explorer.
Your working directory is: e:\osmanli\.agents\teamwork\explorer_survey_2\
Authoritative user request file: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
Dispatch instructions: e:\osmanli\.agents\teamwork\explorer_survey_2\DISPATCH.md

MANDATORY FIRST STEP:
Read e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md and e:\osmanli\AGENTS_CONSTITUTION.md before doing any analysis.

YOUR MISSION:
Perform a deep forensic audit of the backend architecture (api_server.py, bot_manager.py, database/, tasks, game protocol):
1. Database Schema & Query Optimization:
   - Audit database/castles.db schema, table designs, index coverage, and foreign keys.
   - Detect slow queries, N+1 query patterns, unbounded SELECTs without LIMIT/OFFSET.
   - Check connection lifecycle, WAL mode, transaction scopes, connection pooling, and connection leak risks in async/long-running handlers.
2. Concurrency Safety & Mutation Integrity:
   - Audit concurrent read/write operations to castles.db.
   - Check for race conditions, lost updates, lack of Optimistic Concurrency Control (OCC) / versioning / row locks.
   - Audit idempotency of mutation endpoints and handling of out-of-order requests.
3. Multi-Account Isolation & Access Control:
   - Check castle ID tampering defense: Can an API request modify another castle or user data by spoofing castle_id or email?
   - Verify boundary isolation across accounts and castles.
4. Resource Leaks & Long-Running Operations:
   - Identify unclosed sockets, uncancelled background tasks, unmanaged memory accumulation in bot_manager or api_server.

CONSTRAINTS:
- You are READ-ONLY. Do NOT modify source code or database files.
- Local workspace only. NO connection to production or remote servers.
- Write your comprehensive findings to e:\osmanli\.agents\teamwork\explorer_survey_2\report.md and your structured handoff to e:\osmanli\.agents\teamwork\explorer_survey_2\handoff.md.
- Update your progress.md regularly for heartbeat liveness.
- Once done, send a message to orchestrator with your summary and handoff path.
