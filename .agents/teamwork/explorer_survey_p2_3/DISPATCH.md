# DISPATCH — Explorer Survey 3 (Testing & Soak Infrastructure Explorer)
**Role**: Read-only exploration agent for R4
**Working directory**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_3\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`

## Mission
Investigate Requirement R4 in detail:
1. Baseline measurement tooling:
   - Investigate how to measure RSS memory (psutil, tracemalloc), CPU % idle vs running, thread counts, open handles/sockets, queue sizes, and global dict sizes locally in `e:\osmanli`.
   - Check existing tools (`tools/`, `tests/`) and design the baseline measurement script `tools/measure_baseline.py` (or similar).
2. 18 Mandatory Test Scenarios:
   - Map and design the 18 specific test scenarios:
     1. Run normal operation
     2. Auth failure
     3. Other device login
     4. Connection loss
     5. Reconnecting
     6. Waiting for re-login
     7. Cycle completion (Waiting for next cycle)
     8. Natural completion (no next cycle)
     9. Manual stop
     10. Stop during execution
     11. Delete castle while running
     12. Delete user while running
     13. Bot start exceptions
     14. In-flight task exceptions
     15. WebSocket disconnect & reconnect
     16. Repeated page opening / switching
     17. Repeated search & filter queries
     18. Stalled thread detection & isolation
3. Soak testing methodology:
   - Design multi-cycle continuous execution soak test script to detect cumulative resource / thread / handle growth.

## STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`

## Output
Write comprehensive report to:
`e:\osmanli\.agents\teamwork\explorer_survey_p2_3\survey_report.md`
and write your `handoff.md`.


## 2026-11-02T22:02:15Z
Sender: 849edb08-8a01-463a-a4d9-889f072bccf9
Content:
You are explorer_survey_p2_3, a teamwork_explorer.
Your working directory is: e:\osmanli\.agents\teamwork\explorer_survey_p2_3\
Read your task dispatch at: e:\osmanli\.agents\teamwork\explorer_survey_p2_3\DISPATCH.md
Read the authoritative request at: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
Also review e:\osmanli\AGENTS_CONSTITUTION.md.

YOUR ROLE: Testing & Soak Infrastructure Explorer (R4).
Explore the codebase (read-only) to investigate:
1. Baseline measurement tooling:
   - Investigate how to measure RSS memory (psutil, tracemalloc), CPU % idle vs running, thread counts, open handles/sockets, queue sizes, and global dict sizes locally in `e:\osmanli`.
   - Check existing tools (`tools/`, `tests/`) and design the baseline measurement script `tools/measure_baseline.py` (or similar).
2. 18 Mandatory Test Scenarios:
   - Map and design the 18 specific test scenarios:
     1. Run normal operation
     2. Auth failure
     3. Other device login
     4. Connection loss
     5. Reconnecting
     6. Waiting for re-login
     7. Cycle completion (Waiting for next cycle)
     8. Natural completion (no next cycle)
     9. Manual stop
     10. Stop during execution
     11. Delete castle while running
     12. Delete user while running
     13. Bot start exceptions
     14. In-flight task exceptions
     15. WebSocket disconnect & reconnect
     16. Repeated page opening / switching
     17. Repeated search & filter queries
     18. Stalled thread detection & isolation
3. Soak testing methodology:
   - Design multi-cycle continuous execution soak test script to detect cumulative resource / thread / handle growth.

STRICT CONSTRAINTS:
- YOU ARE READ-ONLY. DO NOT write or edit any codebase files or run commands that modify code.
- STRICT PROHIBITION: You MUST NOT open, read, modify, format, rename, delete, move, or touch:
  `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- No remote server uploads, deploys, or production connections.
