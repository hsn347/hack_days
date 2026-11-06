# Technical Verification Plan — Reviewer 1 (Milestone 5 / Requirement R4)

**Document**: `e:\osmanli\.agents\teamwork\reviewer_p2_m5_1\report_m5_verification_plan.md`  
**Author**: Reviewer 1 (Archetype: reviewer_critic)  
**Parent Conversation ID**: `849edb08-8a01-463a-a4d9-889f072bccf9`  
**Timestamp**: 2026-11-03T20:20:00Z  
**Compliance**: GEMINI.md Rule 5 (Strict File-Report-First Rule), Rule 4 (Local Workspace Only)

---

## 1. Diagnosis & Objectives

The purpose of this review and verification cycle is to independently and objectively assess the work delivered by Worker M5 Generation 2 for Milestone 5 (Requirement R4):
1. **18 Mandatory Scenarios Verification (`tests/test_mandatory_scenarios.py`)**:
   Verify that all 18 specified scenarios (S01 through S18) are genuinely, authentically, and hermetically implemented, covering:
   - S01: Startup (Starting -> Running)
   - S02: Auth Credential Failure Handling
   - S03: Other Device Login Detection & Transient State
   - S04: Connection Loss Detection & Reconnecting State
   - S05: Reconnecting Attempts with Bounded Retry Logic
   - S06: Waiting for Re-login Handling
   - S07: Next Cycle Wait with Timestamp
   - S08: Natural Completion (without Next Cycle)
   - S09: Manual Stop via _stop_and_join_bot (Deterministic Join, 0 Residual Threads)
   - S10: Stop In-Flight During Active Task Execution (< 100ms Event Cancellation)
   - S11: Delete Castle While Running (Atomic Stop, Purge DB & Proxy Bindings)
   - S12: Delete User While Running (Atomic Stop of All Castles, Purge User & DB)
   - S13: Startup Exception Handling (Clean Rollback, No Zombie Threads)
   - S14: In-Flight Runtime Exception Handling (Catch, Record, Safe Termination)
   - S15: WebSocket Disconnect Detection (Coroutine Termination, 0 Leaked Tasks)
   - S16: WebSocket Reconnect (Fresh Initial Snapshot Push)
   - S17: Repeated Page Navigation / Rapid API Calls (Paginated Summary, No Memory Growth)
   - S18: Repeated Search & Filter with Stalled Thread Isolation (Quarantined in _stalled_threads)
2. **Unified Regression Verification (`tests/run_all_tests.py`)**:
   Execute the full 4-tier test runner and confirm that all 30 tests pass with 100% pass rate.
3. **Strict Prohibition Compliance**:
   Confirm that the three prohibited core files:
   - `game_client.py`
   - `core/onemt_auth.py`
   - `core/onemt_bot.py`
   have never been opened, read, modified, formatted, renamed, deleted, moved, or touched.
4. **Adversarial Integrity Inspection**:
   Scrutinize the test code for facade implementations, mock bypassing, self-certifying logic, hardcoded returns, thread leaks, or database isolation issues.

---

## 2. Planned Steps & Methodology

### Step 1: Pre-Execution Verification Artifact Creation
Generate this report artifact before running any command, establishing the audit trail and rationale.

### Step 2: Prohibited File Integrity Check
Use `git status --porcelain` targeted specifically to confirm that `game_client.py`, `core/onemt_auth.py`, and `core/onemt_bot.py` have zero unstaged or staged modifications.

### Step 3: Mandatory 18-Scenario Execution
Execute `python tests/test_mandatory_scenarios.py` in the local workspace.
- Expected Result: 18 tests execute, 0 errors, 0 failures, exit code 0.

### Step 4: 4-Tier Test Suite Execution
Execute `python tests/run_all_tests.py` in the local workspace.
- Expected Result: All 30 test cases across Tiers 1-4 pass with exit code 0.

### Step 5: Adversarial Deep-Dive Code Analysis
Review each scenario implementation in `tests/test_mandatory_scenarios.py` line-by-line:
- Check test hermeticity (isolated SQLite DB per test, cleanup of `_threads`, `_stop_events`, etc.).
- Check mock fidelity (does the mock accurately reflect real code behavior?).
- Check whether assertions actually validate the underlying invariant or merely test the mock itself.
- Verify whether the tests can detect real regressions if faulty logic were reintroduced.

### Step 6: Produce Final Handoff & Issue Verdict
Synthesize observations, logic chains, caveats, and conclusions into `handoff.md` and issue either `APPROVE` or `REQUEST_CHANGES`. Notify the caller via `send_message`.

---

## 3. Exact Commands to Execute

| # | Command | Expected Output | Rationale |
|---|---------|-----------------|-----------|
| 1 | `git status --porcelain game_client.py core/onemt_auth.py core/onemt_bot.py` | Empty output | Verify strict prohibition compliance |
| 2 | `python tests/test_mandatory_scenarios.py` | `Ran 18 tests in ... OK` | Verify all 18 scenarios pass hermetically |
| 3 | `python tests/run_all_tests.py` | `30 PASS, 0 FAIL` | Verify regression suite |
