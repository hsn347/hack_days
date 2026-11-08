# Project: Adversarial March Audit & Architectural Unification Blueprint
# Scope: Full 10-File Audit, Red Team Critique, March Coordinator Trial, base_task Architecture, Programmatic Verification

## Architecture & Scope
A comprehensive, surgical adversarial audit of the 10 external march and combat task files in `e:\osmanli\tasks\`:
1. `tasks/base_task.py`
2. `tasks/march_coordinator.py`
3. `tasks/monster.py`
4. `tasks/stronghold.py`
5. `tasks/abra.py`
6. `tasks/ruins.py`
7. `tasks/gather.py`
8. `tasks/gold_gather.py`
9. `tasks/gather_boost.py`
10. `tasks/transport.py`

Output target: `docs/reports/adversarial_march_audit.md` (no source code modifications allowed in the workspace).

## Feature Inventory
| # | Feature / Scope Item | Description | Milestone | Source |
|---|---------------------|-------------|-----------|--------|
| 1 | File Audit: base_task.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M1 | R1 |
| 2 | File Audit: march_coordinator.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M1 | R1 |
| 3 | File Audit: monster.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M2 | R1 |
| 4 | File Audit: stronghold.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M2 | R1 |
| 5 | File Audit: abra.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M2 | R1 |
| 6 | File Audit: ruins.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M3 | R1 |
| 7 | File Audit: gather.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M3 | R1 |
| 8 | File Audit: gold_gather.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M3 | R1 |
| 9 | File Audit: gather_boost.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M4 | R1 |
| 10 | File Audit: transport.py | Line-by-line, config table, execution traces, network cmds, memory keys, error tables, Red Team critique | M4 | R1 |
| 11 | Error Codes (20 codes) Coverage | 8004, 9007004, 8009, 8035, 8032, 10002, 10003, 9007020, 8014, 8015, 8027, 8037, 8041, 8042, 8046, 8060, 8062, 8063, 8095, 16001 + ExcludeManager confirm/release | M1-M4 | R1 |
| 12 | March Coordinator Life Cycle & 10 Priorities | Complete tracing of 10 priorities, config dispatching, fallback action mapping | M5 | R2 |
| 13 | Stop Reason & Status Matrix | Exhaustive table of 5 stop reasons (WEAK_ARMY, SUICIDE_RISK, NPC_LEVEL_LOCKED, REBEL_PREREQUISITE_FAILED, CMD_OPTING) & statuses translated into CoordinatorAction | M5 | R2 |
| 14 | Prestige Quest ID Conflict Resolution | Deep dive into PRESTIGE_QUEST_IDS conflict between base_task.py and march_coordinator.py (stronghold, gather, etc.) | M5 | R2 |
| 15 | Duplication Matrix & base_task Architecture | Complete cross-task duplicate function analysis and full architectural design of unified base_task.py methods | M6 | R3 |
| 16 | Before & After Clean-up Blueprint | Exact line/method removal and migration map for all 10 files | M6 | R3 |
| 17 | Final Master Document Assembly | Compilation of all sections into docs/reports/adversarial_march_audit.md without any summary phrases | M7 | R4 |
| 18 | Programmatic Verification Script | Independent automated audit script verifying 100% coverage of all 10 files, all functions, 20 error codes, 10 coordinator priorities | M8 | Acceptance |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Framework Audit (Group 1) | base_task.py & march_coordinator.py deep dissection | none | DONE |
| M2 | Combat & Rally Audit (Group 2) | monster.py, stronghold.py, abra.py deep dissection | none | DONE |
| M3 | Gathering & Resource Audit (Group 3) | ruins.py, gather.py, gold_gather.py deep dissection | none | DONE |
| M4 | Buffs & Logistics Audit (Group 4) | gather_boost.py, transport.py deep dissection | none | DONE |
| M5 | March Coordinator Trial & Protocol Analysis | Coordinator 10 priorities, fallback actions, stop_reason matrix, prestige ID conflict | M1 | DONE |
| M6 | Architectural Unification Blueprint | Unified base_task.py design, duplication matrix, Before & After cleanup | M1-M4 | DONE |
| M7 | Master Report Compilation | Assembly into docs/reports/adversarial_march_audit.md | M1-M6 | DONE |
| M8 | Programmatic 100% Verification | Independent verification script run & validation report | M7 | DONE |

## Code Layout & Boundaries
- All analysis metadata: `.agents/teamwork/<agent_dir>/`
- Final report destination: `docs/reports/adversarial_march_audit.md`
- Verification script: `.agents/teamwork/orchestrator_1/verify_audit_coverage.py`
- Source files: `tasks/*.py` (READ-ONLY, ZERO MODIFICATIONS)
