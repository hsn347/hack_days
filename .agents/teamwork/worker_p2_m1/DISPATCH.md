# DISPATCH — Worker M1 (Baseline Measurement Tooling & Pre-Fix Profiling)
**Role**: Implementation Worker for Milestone 1
**Working directory**: `e:\osmanli\.agents\teamwork\worker_p2_m1\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`
**Architectural Plan**: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md`
**Explorer Survey Reference**: `e:\osmanli\.agents\teamwork\explorer_survey_p2_3\survey_report.md`

## Objectives
1. Implement the baseline measurement tool `tools/measure_baseline.py` adhering to AGENTS_CONSTITUTION.md and the survey specification:
   - Process memory RSS (MB) using Windows PSAPI (`ctypes.windll.psapi.GetProcessMemoryInfo`) with fallback/support for `psutil`.
   - Tracemalloc peak and current allocated memory.
   - CPU usage % in idle and under active operation.
   - Detailed thread inventory (active count, thread names, identifying bot threads, daemon threads).
   - Process handle count via `ctypes.windll.kernel32.GetProcessHandleCount`.
   - Open socket counts.
   - Global tracking structures inspector for `api_server.py` (`_threads`, `_stop_events`, `_bot_managers`, `_reserved`, `_log_qs`, `_conn_states`, `_user_stopped`, `_castle_emails`, `_castle_users`, `_deleted_castles`).
   - SQLite DB and WAL journal size metrics.
2. Execute pre-fix measurement run and generate:
   - `tools/baseline_metrics_prefix.json`
   - `tools/BASELINE_METRICS_PREFIX.md`
3. Verify that running `python tools/measure_baseline.py` completes cleanly with exit code 0 and valid JSON output.
4. Run the existing platform test suite `python tests/run_all_tests.py` to confirm baseline integrity (30/30 tests passing).

## Write Ownership
You exclusively own:
- `tools/measure_baseline.py`
- `tools/baseline_metrics_prefix.json`
- `tools/BASELINE_METRICS_PREFIX.md`
- Your working directory: `e:\osmanli\.agents\teamwork\worker_p2_m1\`
Do NOT modify other codebase files in this milestone.

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## STRICT PROHIBITION
NEVER open, read, modify, format, rename, delete, move, or touch:
- `game_client.py`
- `core/onemt_auth.py`
- `core/onemt_bot.py`
Any violation will result in immediate termination. Local workspace only.
