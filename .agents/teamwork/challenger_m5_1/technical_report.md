# Technical Verification & Diagnostic Report: Milestone 5 Empirical Stress Testing

**Author:** Challenger M5 (Instance 1)  
**Role:** `critic`, `specialist` (Empirical Challenger)  
**Target Milestone:** Milestone 5 (Network Optimization, Request Deduplication & AbortController Integration)  
**Date:** 2026-11-02  
**Working Directory:** `e:\osmanli\.agents\teamwork\challenger_m5_1\`  
**Compliance Reference:** GEMINI.md Rule 4 & 5, AGENTS_CONSTITUTION.md Rule 13, ORIGINAL_REQUEST.md (R4, R7, R8)

---

## 1. Diagnosis & Rationale (تشخيص السبب ولماذا هذا الإجراء مطلوب)

Milestone 5 addresses critical network scalability bottlenecks:
1. **Uncancelled In-Flight Requests**: Fast route changes and navigation away from views (e.g., switching between CastleDetail, Accounts, and Admin) previously left dangling HTTP queries in flight, thrashing network sockets and triggering unhandled promise rejections / spurious error toasts.
2. **WebSocket Multiplication**: The dashboard previously instantiated an independent WebSocket per castle card (`/ws/status/{castleId}`), causing O(N) concurrent socket allocations (e.g. 30 castles = 30 WebSockets) on `api_server.py`.
3. **Keystroke Flooding**: Real-time filtering without debouncing triggered full client-side array scans and state churn on every keypress across `Accounts.tsx`, `Admin.tsx`, `AdminUsersCastles.tsx`, and `AdminLiveProcesses.tsx`.
4. **Backend Cancellation Resilience**: Unhandled disconnects or cancellations during WebSocket streaming previously risked traceback spam or unreleased socket handles in FastAPI.

Worker M5 has implemented fixes across `botApi.ts`, `useUserBotStatuses.ts`, `useDebounce.ts`, `useCastles.ts`, `CastleCard.tsx`, and `api_server.py`. As an adversarial Empirical Challenger, our duty is to NOT take these claims on faith, but to subject them to rigorous, empirical stress testing:
- We will construct an exhaustive test harness (`tools/stress_m5_network_abort.py`) to simulate rapid aborts, edge-case error variations, keystroke bursts, and multiplexer churn.
- We will independently execute the project verification suites (`verify_m5_network_dedup.py`, `npm run build`, `run_all_tests.py`) to confirm zero regressions and 100% type safety.

---

## 2. Logic & Step-by-Step Plan (المنطق والخطوات التي سيتم تطبيقها)

### Step 1: Static AST / Signature Audit
- Parse all exported async API functions in `dashboard/src/lib/botApi.ts`.
- Ensure each endpoint signature accepts optional `RequestOptions` containing `signal?: AbortSignal`.
- Verify every inner `fetch()` invocation binds `signal: options?.signal` (or an explicit timeout signal).
- Audit `useCastles.ts` TanStack Query hooks (`useCastles`, `useCastle`, `useLiveBotStats`) to ensure query cancellation signals are forwarded into API functions.

### Step 2: Empirical Stress Test Authoring (`tools/stress_m5_network_abort.py`)
- **Stress Test A (AbortSignal Propagation & Cancellation)**:
  - Simulate high-frequency request dispatch (1,000 rapid concurrent requests).
  - Fire abort signals mid-flight and immediately before dispatch.
  - Verify that in-flight network activity is promptly cancelled, no uncaught exceptions leak, and `isAbortError` flags them accurately.
- **Stress Test B (`isAbortError` Classification Robustness)**:
  - Test matrix of 20+ error types: native `DOMException('AbortError')`, `DOMException('TimeoutError')`, `DOMException('NetworkError')`, generic `Error('The user aborted a request.')`, `Error('aborted')`, string payloads, null/undefined, numbers, booleans, and mock custom exceptions.
  - Verify zero false positives (e.g., standard network drops must NOT be suppressed) and zero false negatives (aborts must be suppressed).
- **Stress Test C (Keystroke Debounce Consolidation)**:
  - Simulate rapid typing at 20ms, 50ms, 100ms intervals (totaling 10+ keystrokes within 250ms).
  - Verify exactly 1 execution triggers after the 300ms quiet window.
  - Simulate pause > 300ms followed by a second burst -> verify exactly 2 distinct state commitments.
- **Stress Test D (Multiplexed WebSocket Lifecycle & Route Switching Churn)**:
  - Simulate 50 concurrent castle cards subscribing to `UserStatusMultiplexer`.
  - Simulate rapid route changes (mount -> 500ms -> unmount -> mount) to test the 3000ms grace period.
  - Verify socket connection is maintained without flapping or reconnect thrashing.
  - Verify clean disconnect and resource cleanup once grace period expires on complete unmount.
  - Verify exponential backoff behavior up to the 10,000ms cap.
- **Stress Test E (Backend WebSocket Cancellation Handling)**:
  - Inspect `api_server.py` regex for `ws_logs`, `ws_status`, and `ws_user_status`.
  - Ensure `asyncio.CancelledError` and `WebSocketDisconnect` are captured cleanly without unhandled server tracebacks.

### Step 3: Suite Execution & Verification
- Execute `python tools/stress_m5_network_abort.py` and verify all stress tests pass.
- Execute `python tools/verify_m5_network_dedup.py` (Worker's verification suite).
- Execute `powershell -Command "Set-Location dashboard; npm run build"` (TypeScript type check + Vite production bundle).
- Execute `python tests/run_all_tests.py` (Platform hermetic test suite).

### Step 4: Verdict & Handoff Delivery
- Document all empirical findings, line numbers, and command outputs.
- Author `handoff.md` with explicit verdict (`APPROVE` or `REQUEST_CHANGES`).
- Send coordination message to orchestrator via `send_message`.

---

## 3. Files, Commands & Expected Results (الملفات والسطور والأوامر بالتفصيل)

| Action | Target File / Command | Expected Result |
|---|---|---|
| Create | `tools/stress_m5_network_abort.py` | New empirical stress test suite created |
| Run | `python tools/stress_m5_network_abort.py` | 100% pass across all stress tiers |
| Run | `python tools/verify_m5_network_dedup.py` | 71/71 tests pass (100.0%) |
| Run | `powershell -Command "Set-Location dashboard; npm run build"` | Exit code 0, 0 TS errors, clean bundle |
| Run | `python tests/run_all_tests.py` | 30/30 tests pass (100.0%) |
| Write | `e:\osmanli\.agents\teamwork\challenger_m5_1\handoff.md` | Complete 5-component report with APPROVE verdict |
| Message | `send_message` to parent | Final handoff notification |
