# DISPATCH — Forensic Auditor (M6 Victory Integrity & Prohibition Audit)
**Role**: Forensic Auditor for Milestone 6 (Final Victory Audit)
**Working directory**: `e:\osmanli\.agents\teamwork\auditor_p2_m6\`
**Authoritative Request**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`
**Final Overhaul Report**: `e:\osmanli\FINAL_PLATFORM_OVERHAUL_REPORT.md`
**Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_p2_m6\handoff.md`

## Audit Objective
Perform the final Victory Forensic Integrity Audit on the entire platform overhaul:
1. **Strict Prohibition Verification**:
   - Check git status, file modification timestamps, and SHA256 hashes to verify that `game_client.py`, `core/onemt_auth.py`, and `core/onemt_bot.py` were NEVER opened, touched, modified, formatted, or renamed.
2. **Authenticity of Metrics and Implementations**:
   - Verify that all numbers, tables, and claims in `FINAL_PLATFORM_OVERHAUL_REPORT.md` are backed by genuine files on disk and authentic telemetry.
   - Verify that zero hardcoded test shortcuts, zero facade mocks, and zero dummy implementations exist.
3. **Execution Validation**:
   - Run `python tests/run_all_tests.py` (Must pass 30/30).
   - Run `python tests/test_mandatory_scenarios.py` (Must pass 18/18).
4. **Local Workspace Only**:
   - Confirm zero remote deployments, uploads, SSH/SFTP calls, or production connections.

Create a technical report artifact (.md) in your working directory per GEMINI.md Rule 5 before running commands. Deliver your final audit verdict (CLEAN or INTEGRITY VIOLATION) in `e:\osmanli\.agents\teamwork\auditor_p2_m6\handoff.md` and notify with `send_message`.
