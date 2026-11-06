# Progress — Explorer Survey 1 (Admin Castles & Ops Explorer)

Last visited: 2026-11-02T22:42:00Z
Status: Completed

## Tasks
- [x] Initialized workspace (BRIEFING.md, progress.md)
- [x] Investigate R1: Admin Castles Pagination
  - [x] Analyze existing Users pagination in `api_server.py` and React dashboard (`Admin.tsx`)
  - [x] Analyze existing Castles querying in `api_server.py` and React dashboard (`AdminUsersCastles.tsx`)
  - [x] Analyze summary vs detail separation (config lazy-loading)
  - [x] Backend search, filter, and sorting logic for castles with SQLite
  - [x] Frontend local update pattern (mutations without refetch)
  - [x] Role scoping: Super Admin vs Merchant Admin isolation
- [x] Investigate R2: Live Operations Lifecycle & Pagination
  - [x] Trace `/api/admin/live-processes` endpoint in `api_server.py` and `AdminLiveProcesses.tsx`
  - [x] Thread lifecycle vs BotManager state vs connection state vs task execution
  - [x] The 6 allowed states mapping and definitions (Running, Waiting for Next Cycle, Other Device Login, Reconnecting, Waiting for Re-login, Starting)
  - [x] Stalled thread detection, causes, and diagnostic isolation
  - [x] Live operations pagination matching Users page
  - [x] Root causes and prevention of duplicate operations per castle/resource
- [x] Synthesize findings into comprehensive `survey_report.md`
- [x] Write 5-component `handoff.md` and notify orchestrator
