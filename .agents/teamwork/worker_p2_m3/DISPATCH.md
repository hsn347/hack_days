# DISPATCH — Worker M3 (Live Operations Lifecycle, State Clarification & Pagination)
**Role**: Implementation Worker for Milestone 3 (F5, F6, F7 / R2)
**Working directory**: `e:\osmanli\.agents\teamwork\worker_p2_m3\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R2)
**Architectural Plan**: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 3)
**Survey Blueprint**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_1\survey_report.md` (Section 3)

## Objectives
Implement Requirement R2: Live Operations Lifecycle & Pagination:

1. **State Machine & Lifecycle Decoupling (`api_server.py` & `bot_manager.py`)**:
   - Decouple Thread liveness from BotManager state: Never mark an operation as running merely because `th.is_alive()` or `threading.enumerate()` found a `"bot-"` thread.
   - Restrict allowed live operational states strictly to the 6 legitimate states:
     1. `Running`: Actual execution of a known task (e.g. GatherResources, TrainTroops, DailyQuests).
     2. `Waiting for Next Cycle`: Waiting for the scheduled next cycle, displaying exact remaining time / next cycle timestamp.
     3. `Other Device Login`: Temporarily suspended or waiting due to another device login.
     4. `Reconnecting`: Actively attempting genuine reconnections.
     5. `Waiting for Re-login`: Waiting for re-login due to auth/session issue.
     6. `Starting`: Genuine, bounded startup period.
   - Exclude manually stopped (`_user_stopped`), naturally completed without next cycle, failed, cancelled, deleted, or orphaned states from live processes.
   - Isolate stalled/orphaned threads into a diagnostic `stalled` category (e.g. `summary.stalled`), excluded from `total_active`.
   - Prevent duplicate operations for the same castle/resource: verify thread creation, bot manager restart, and stop/delete synchronization with atomic check-and-reserve.

2. **API Backend Pagination (`api_server.py`)**:
   - Update `GET /api/admin/live-processes` to accept `page: int = 1`, `page_size: int = 25`, `search: str = ""`, `status: str = "all"`.
   - Return pagination envelope:
     ```json
     {
       "processes": [...],
       "total_active": 15,
       "summary": {
         "Running": 8,
         "Waiting for Next Cycle": 4,
         "Other Device Login": 1,
         "Reconnecting": 1,
         "Waiting for Re-login": 1,
         "Starting": 0,
         "stalled": 0
       },
       "page": 1,
       "page_size": 25,
       "total_pages": 1,
       "has_more": false
     }
     ```

3. **Frontend UI & Zero-Flicker Polling (`dashboard/src/pages/AdminLiveProcesses.tsx` & `dashboard/src/lib/botApi.ts`)**:
   - Update `botApi.ts` to support paginated query params and return typed response.
   - In `AdminLiveProcesses.tsx`, implement true pagination matching `Admin.tsx` (`[10, 25, 50, 100]`, default 25, chevrons, range display).
   - Implement smooth, flicker-free polling/updating (preserve table structure, smooth row updates, no jarring UI re-render flicker).
   - Support search (by email, user_id, castle_id) and status filter dropdown (matching the 6 allowed states + "all").

4. **Build & Test Verification**:
   - Run `powershell -Command "Set-Location dashboard; npm run build"` to verify zero TypeScript errors.
   - Run `python tests/run_all_tests.py` to confirm 30/30 platform tests pass.
   - Run `python tools/measure_baseline.py` to verify system health.

## Write Ownership
You exclusively own:
- `api_server.py` (`get_admin_live_processes`, thread state resolution, live ops pagination)
- `bot_manager.py` (live task tracking, state reporting for the 6 allowed states)
- `dashboard/src/pages/AdminLiveProcesses.tsx`
- `dashboard/src/lib/botApi.ts`
- Your working directory: `e:\osmanli\.agents\teamwork\worker_p2_m3\`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
Strictly local workspace only: NO server uploads, deploys, or remote DB connections.

## Pre-Implementation Requirement
Create a technical report artifact `.md` in your working directory per GEMINI.md Rule 5 before modifying code or running build commands.
