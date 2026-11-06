# Dispatch Directive: Forensic Auditor M5 — Integrity Verification

## 2026-11-02T19:39:00Z
- **Target Role**: teamwork_auditor
- **Milestone**: Milestone 5: Network Optimization, Request Deduplication & AbortController Integration
- **Working Directory**: `e:\osmanli\.agents\teamwork\auditor_m5\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R4, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_m5\handoff.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
Create your technical report artifact before executing commands.

## 🔒 AUDIT INTEGRITY MANDATE
Verify that Milestone 5 implementations are genuine, functional, and authentic:
1. **Hardcoded Test Results Check**: Confirm that no mocked responses or canned strings exist in `botApi.ts`, `useUserBotStatuses.ts`, `useDebounce.ts`, or `api_server.py`.
2. **Facade Check**: Verify that `AbortSignal` is genuinely passed to `fetch()` calls and not ignored; verify `UserStatusMultiplexer` genuinely opens and manages a real WebSocket.
3. **Verification Integrity**: Inspect `tools/verify_m5_network_dedup.py` to ensure it exercises real code paths without self-certification cheats.
4. Run standard suites:
   - `python tools/verify_m5_network_dedup.py`
   - `cd dashboard; npm run build`
   - `python tests/run_all_tests.py`
5. Deliver `handoff.md` with explicit verdict: **CLEAN** or **INTEGRITY VIOLATION**.
   - Note: If ANY integrity violation is found, report **INTEGRITY VIOLATION** immediately (Hard Veto).
6. Notify orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`) via `send_message`.

## 2026-11-02T19:40:09Z
- **Sender**: 44132d7d-07d0-4709-a292-a8e4727a82fd
- **Priority**: MESSAGE_PRIORITY_HIGH
- **Directive**: Milestone 5 Forensic Integrity Audit execution.
- **Tasks**:
  1. Hardcoded results check: ensure no mocked responses or canned strings exist.
  2. Facade implementation check: verify that AbortSignal is genuinely passed to fetch and UserStatusMultiplexer genuinely manages real WebSocket connections.
  3. Verification integrity check: inspect `tools/verify_m5_network_dedup.py` for genuine test coverage.
  4. Run verification suites (`verify_m5_network_dedup.py`, `npm run build`, `run_all_tests.py`).
  5. Deliver `handoff.md` with explicit verdict: **CLEAN** or **INTEGRITY VIOLATION**.
  6. Send completion message to orchestrator.
