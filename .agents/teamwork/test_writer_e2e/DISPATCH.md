# E2E Test Writer Dispatch: Opaque-Box Requirement-Driven Test Suite (Replacement)

- Working Directory: e:\osmanli\.agents\teamwork\test_writer_e2e\
- Authoritative Request: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
- Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
- Project Scope: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
- Approved Remediation Plan: e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md

## Mandate & Scope
You are the replacement E2E Test Writer (`teamwork_test_writer`).
Your role is to build the comprehensive 4-tier opaque-box test suite for the platform performance, state management, caching, network, and admin dashboard overhaul:
- Tier 1: Feature Coverage (>=5 test cases per feature across R1-R7)
- Tier 2: Boundary & Corner Cases (empty inputs, large records, concurrent saves, account switching)
- Tier 3: Cross-Feature Combinations (pairwise interactions: state change + cache invalidation, network cancellation + unmount)
- Tier 4: Real-World Application Scenarios (full user journey: login -> castle config save -> navigate away -> verify persistence without stale cache)

## Concrete Tasks
1. Complete `e:\osmanli\TEST_INFRA.md` at project root documenting test architecture, runner command, and coverage thresholds.
2. Implement test runner scripts and test cases strictly in `e:\osmanli\tests/` (e.g. `tests/test_e2e_platform.py` and `tests/test_database_performance.py`).
3. Execute the tests locally and ensure test runner operates cleanly.
4. When complete, publish `e:\osmanli\TEST_READY.md` summarizing test counts across all 4 tiers.
5. Write your handoff report to `e:\osmanli\.agents\teamwork\test_writer_e2e\handoff.md` and notify the orchestrator.

