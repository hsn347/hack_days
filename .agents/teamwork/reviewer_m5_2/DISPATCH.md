# Dispatch Directive: Reviewer M5 (Instance 2) — Adversarial & Stress Review

## 2026-11-02T19:39:00Z
- **Target Role**: teamwork_reviewer
- **Milestone**: Milestone 5: Network Optimization, Request Deduplication & AbortController Integration
- **Working Directory**: `e:\osmanli\.agents\teamwork\reviewer_m5_2\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R4, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Worker Handoff**: `e:\osmanli\.agents\teamwork\worker_m5\handoff.md`
- **Worker Technical Report**: `e:\osmanli\.agents\teamwork\worker_m5\technical_report_m5.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
Create your technical report artifact before executing commands.

## Review Scope & Instructions
1. Independently adversarially challenge Milestone 5 implementations:
   - What happens when a user navigates between 5 pages rapidly while requests are pending? Are `AbortController` signals triggered and handled cleanly without console error explosions or memory leaks?
   - What happens when WebSocket reconnects after server restart or network drop? Does the multiplexer back off exponentially and re-subscribe all card listeners?
   - What happens when debounced inputs receive rapid keystrokes? Does the component re-render excessively?
   - Does `api_server.py` leak asyncio tasks or sockets when a client disconnects mid-message?
2. Verify all test suites:
   - `python tools/verify_m5_network_dedup.py`
   - `cd dashboard; npm run build`
   - `python tests/run_all_tests.py`
3. Deliver `handoff.md` with explicit verdict: **APPROVE** or **REQUEST_CHANGES**.
4. Notify orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`) via `send_message`.


## 2026-11-02T19:39:38Z
- Sender: 44132d7d-07d0-4709-a292-a8e4727a82fd
- Priority: MESSAGE_PRIORITY_HIGH
- Content: You are Reviewer M5 (Instance 2), assigned to Milestone 5 Adversarial & Stress Review.
Working Directory: `e:\osmanli\.agents\teamwork\reviewer_m5_2\`
Dispatch Directive: `e:\osmanli\.agents\teamwork\reviewer_m5_2\DISPATCH.md`
Context Files:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m5\handoff.md`

🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5):
Create your technical report artifact (.md) in your directory BEFORE running commands.

Adversarially evaluate:
- Rapid route changes and pending request cancellations.
- WebSocket reconnection backoff and reconnect storm prevention.
- Rapid typing debounce performance and rendering overhead.
- Backend socket disconnection cleanup in `api_server.py`.

Verify using:
- `python tools/verify_m5_network_dedup.py`
- `powershell -Command "Set-Location dashboard; npm run build"`
- `python tests/run_all_tests.py`

Deliver `handoff.md` in your directory with explicit verdict (APPROVE / REQUEST_CHANGES) and send completion message to orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`).
