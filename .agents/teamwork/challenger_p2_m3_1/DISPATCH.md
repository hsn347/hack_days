# DISPATCH — Challenger 1 (M3 State Classification & Lifecycle Empirical Challenge)
**Role**: Challenger for Milestone 3
**Working directory**: `e:\osmanli\.agents\teamwork\challenger_p2_m3_1\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (Requirement R2)
**Architectural Plan**: `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN_P2.md` (Milestone 3)
**Worker Deliverable**: `e:\osmanli\.agents\teamwork\worker_p2_m3\handoff.md`

## Mission
1. Empirically verify the 6 allowed states and lifecycle decoupling:
   - Write an independent stress/challenge script (in `tools/` or your directory) to simulate various bot manager conditions:
     - Bot with active task -> must report `Running` with current task name.
     - Bot sleeping between cycles -> must report `Waiting for Next Cycle` with remaining seconds.
     - Bot with other device login -> must report `Other Device Login`.
     - Bot reconnecting -> must report `Reconnecting`.
     - Bot waiting for re-login -> must report `Waiting for Re-login`.
     - Bot starting -> must report `Starting`.
     - Bot stopped / failed / finished -> must NOT appear in live processes!
     - Orphan/unresponsive OS thread -> must appear in `summary.stalled`, NOT in `total_active`.
   - Test duplicate start prevention: Attempt concurrent start requests for same castle and same email under load.
2. Run `python tests/test_live_operations_m3.py` (4/4 PASS).
3. Run `python tests/run_all_tests.py` (30/30 PASS).
4. Verify forbidden files: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` were NOT touched.
5. Deliver verdict: APPROVE or REQUEST_CHANGES.


## 2026-11-02T23:28:08Z
[Message] timestamp=2026-11-02T23:28:08Z sender=849edb08-8a01-463a-a4d9-889f072bccf9 priority=MESSAGE_PRIORITY_HIGH content=You are challenger_p2_m3_1, a teamwork_challenger.
Your working directory is: e:\osmanli\.agents\teamwork\challenger_p2_m3_1\
Read your task dispatch at: e:\osmanli\.agents\teamwork\challenger_p2_m3_1\DISPATCH.md
Read the authoritative request at: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md (Requirement R2)
Read the worker handoff at: e:\osmanli\.agents\teamwork\worker_p2_m3\handoff.md
Read the code files: `api_server.py`, `bot_manager.py`, `dashboard/src/pages/AdminLiveProcesses.tsx`, `dashboard/src/lib/botApi.ts`, `tests/test_live_operations_m3.py`.
Also review e:\osmanli\AGENTS_CONSTITUTION.md.

YOUR ROLE: Challenger 1 for Milestone 3 (State Classification & Lifecycle Empirical Challenge).
1. Empirically verify the 6 allowed states, thread decoupling, duplicate start prevention, and stalled thread isolation.
2. Run unit tests: `python tests/test_live_operations_m3.py` (4/4 PASS).
3. Run platform tests: `python tests/run_all_tests.py` (30/30 PASS).
4. Verify forbidden files: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py` were NOT touched.
5. Write your handoff.md with explicit verdict: APPROVE or REQUEST_CHANGES and notify parent via send_message.
