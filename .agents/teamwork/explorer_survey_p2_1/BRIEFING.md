# BRIEFING — 2026-11-02T22:40:00Z

## Mission
Comprehensive read-only investigation of R1 (Admin Castles Pagination) and R2 (Live Operations Lifecycle & Pagination) to support architecture design and implementation planning.

## 🔒 My Identity
- Archetype: explorer
- Roles: Admin Castles & Ops Explorer (R1 & R2)
- Working directory: e:\osmanli\.agents\teamwork\explorer_survey_p2_1
- Original parent: 849edb08-8a01-463a-a4d9-889f072bccf9
- Milestone: Phase 0 Exploration & Survey

## 🔒 Key Constraints
- Read-only investigation — do NOT implement or modify source code.
- STRICT PROHIBITION: You MUST NOT open, read, modify, format, rename, delete, move, or touch: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- No remote server uploads, deploys, or production connections. Local workspace only.
- Adhere to GEMINI.md rules and AGENTS_CONSTITUTION.md.

## Current Parent
- Conversation ID: 849edb08-8a01-463a-a4d9-889f072bccf9
- Updated: 2026-11-02T22:40:00Z

## Investigation State
- **Explored paths**:
  - `api_server.py` (Endpoints: `/api/admin/users`, `/api/admin/users-castles/summary`, `/api/admin/live-processes`, `/api/bot/start`, `/api/bot/stop`, thread management structures)
  - `bot_manager.py` (`get_live_info()`, `run_loop()`, `execute_task_pipeline()`, state transitions)
  - `core/database.py` (`get_all_users_with_castles()`, `get_all_castles()`, `get_user_castles()`, schema & indexes)
  - `core/tenants.py` (Multi-tenant scoping, Merchant Admin vs Super Admin)
  - `dashboard/src/pages/Admin.tsx` (Users page pagination UI baseline)
  - `dashboard/src/pages/AdminUsersCastles.tsx` (Admin Castles summary & detail loading, cache invalidations)
  - `dashboard/src/pages/AdminLiveProcesses.tsx` (Live operations view, polling, filtering)
  - `dashboard/src/hooks/useUsers.ts`, `dashboard/src/hooks/useCastles.ts`, `dashboard/src/lib/botApi.ts`
- **Key findings**:
  - Admin castles currently load all users and summaries in memory with zero backend pagination.
  - Castle `config` JSON column (15–25 KB per row) is eagerly loaded and parsed, bloating memory and payload.
  - Live processes endpoint treats any `is_alive()` thread and orphan `"bot-*"` threads as running, with missing states and leaked memory structures.
  - 6 allowed states mapped and formal definitions established; stalled thread isolation criteria defined.
  - Deduplication root causes identified and resolution mechanism established.
- **Unexplored areas**:
  - Investigation of R1 & R2 is complete. Downstream implementation and testing will be performed by implementation agents.

## Key Decisions Made
- Fully documented architecture baseline, gaps, and target implementation blueprint in `survey_report.md`.
- Produced complete 5-component `handoff.md`.

## Artifact Index
- DISPATCH.md — Task dispatch
- progress.md — Heartbeat & status (Completed)
- survey_report.md — Comprehensive survey report
- handoff.md — 5-component handoff report
