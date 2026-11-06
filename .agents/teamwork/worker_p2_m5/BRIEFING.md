# BRIEFING — 2026-11-03T00:26:00Z

## Mission
Implement Requirement R4 (Milestone 5): 18 mandatory scenario tests (`tests/test_mandatory_scenarios.py`) and automated continuous soak testing harness (`tools/soak_test_lifecycle.py`).

## 🔒 My Identity
- Archetype: teamwork_worker
- Roles: implementer, qa, specialist
- Working directory: e:\osmanli\.agents\teamwork\worker_p2_m5\
- Original parent: 849edb08-8a01-463a-a4d9-889f072bccf9
- Milestone: Milestone 5 (F12, F13 / Requirement R4)

## 🔒 Key Constraints
- NEVER open, read, modify, format, rename, delete, move, or touch: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- Strictly local workspace only: NO server uploads, deploys, or remote DB connections.
- MANDATORY INTEGRITY WARNING: DO NOT CHEAT. All implementations must be genuine. No dummy or hardcoded test results.
- Pre-Implementation Requirement per GEMINI.md Rule 5: .md report artifact created before any modifications or commands.
- Exclusive write ownership: `tests/test_mandatory_scenarios.py`, `tools/soak_test_lifecycle.py`, `tools/soak_test_results.json`, `tools/SOAK_TEST_REPORT.md`, and `.agents/teamwork/worker_p2_m5/`.

## Current Parent
- Conversation ID: 849edb08-8a01-463a-a4d9-889f072bccf9
- Updated: 2026-11-03T00:24:01Z

## Task Summary
- **What to build**: Comprehensive 18-scenario hermetic test suite (`tests/test_mandatory_scenarios.py`) and multi-cycle soak testing tool (`tools/soak_test_lifecycle.py`) profiling 64-bit PSAPI RSS, Private Bytes, Handles, Tracemalloc, and linear regression slope.
- **Success criteria**: All 18 scenarios PASS, soak test confirms memory growth slope $m \le 0.05$ MB/cycle and 0 residual threads delta, existing tests PASS (30/30 in run_all_tests, M3 & M4 tests pass).
- **Interface contracts**: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md`
- **Code layout**: `tests/`, `tools/`

## Key Decisions Made
- Reusing high-precision PSAPI / Kernel32 bindings from `tools/measure_baseline.py` for soak test profiling.
- Hermetic design for `tests/test_mandatory_scenarios.py` using mock sessions, cooperative thread workers, and clean isolated db states.

## Change Tracker
- **Files modified**: None yet.
- **Build status**: Pending.
- **Pending issues**: None.

## Quality Status
- **Build/test result**: Pending.
- **Lint status**: 0 violations.
- **Tests added/modified**: `tests/test_mandatory_scenarios.py` (planned 18 scenarios).

## Loaded Skills
- None.

## Artifact Index
- `report_m5_plan.md` — Pre-implementation technical report artifact per GEMINI.md Rule 5.
