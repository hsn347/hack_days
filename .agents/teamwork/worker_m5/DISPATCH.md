# Dispatch Directive: Worker M5 — Network Optimization & Request Deduplication

## 2026-11-02T19:16:00Z
- **Target Role**: teamwork_worker
- **Milestone**: Milestone 5: Network Optimization, Request Deduplication & AbortController Integration
- **Working Directory**: `e:\osmanli\.agents\teamwork\worker_m5\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R4, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
You MUST create an independent technical report artifact (.md file) at:
`e:\osmanli\.agents\teamwork\worker_m5\technical_report_m5.md`
BEFORE modifying any code or executing any commands. The report must detail:
1. Diagnosis and why the changes are needed.
2. Step-by-step logic and changes to be applied.
3. Affected files, lines, and expected outcomes.

---

## Scope & Concrete Objectives

### 1. AbortController Signal Support across `dashboard/src/lib/botApi.ts`
- Enhance `botApi` request functions (`fetchCastles`, `fetchCastle`, `fetchUserCastleData`, `updateCastle`, `controlBot`, `batchControlBots`, `fetchLiveBotStats`, `fetchAdminUsers`, `fetchAdminStats`, etc.) to accept an optional `signal?: AbortSignal` in their options parameter.
- Pass `signal` to `fetch()` calls so in-flight HTTP requests are immediately aborted when a component unmounts, route changes, or a search input re-queries.
- Gracefully handle `AbortError` / `DOMException` without treating cancellations as unhandled error toasts or crashing the UI.

### 2. Multiplexed WebSocket Subscription (`dashboard/src/hooks/useUserBotStatuses.ts`)
- Review `useUserBotStatuses.ts` and its interaction with `api_server.py:ws_user_status`.
- Ensure the user status hook provides a single, multiplexed, resilient WebSocket connection per active user session, broadcasting status updates to all castle cards via TanStack Query cache updates or hook consumers.
- Ensure individual castle cards do NOT establish redundant individual WebSockets or duplicate polling loops when mounted in lists.
- Clean up the WebSocket cleanly on unmount or user change without memory or listener leaks.

### 3. Search & Filter Debouncing
- Identify search inputs across castles and admin views (e.g. castle search bar, log filter).
- Ensure keystroke inputs are debounced (e.g. 250–300ms) before triggering query re-fetches or filtering recalculations, eliminating keystroke flooding.

### 4. Backend Resilience (`api_server.py`)
- Ensure backend route handlers and WebSocket endpoints handle client aborts / disconnects gracefully (e.g., catching `asyncio.CancelledError`, `ClientDisconnect`, `WebSocketDisconnect`) without polluting logs or leaking connections.

### 5. Verification Harness & Platform Integrity
- Author a dedicated verification harness: `tools/verify_m5_network_dedup.py` checking:
  - AbortSignal support across `botApi.ts` functions.
  - AbortError handling and graceful suppression.
  - Multiplexed WebSocket hook lifecycle and cleanup.
  - Search debouncing behavior.
- Ensure `npx tsc --noEmit` and `npm run build` pass with 0 errors.
- Ensure `python tests/run_all_tests.py` passes 30/30 (100%).

---

## Exclusive File Boundaries
- `dashboard/src/lib/botApi.ts`
- `dashboard/src/hooks/useUserBotStatuses.ts`
- `dashboard/src/components/` (specifically search inputs / CastleCard status integration)
- `api_server.py` (WebSocket disconnect & abort handling)
- `tools/verify_m5_network_dedup.py`

## Deliverables
1. `technical_report_m5.md` in your working directory (FIRST).
2. Code implementations in owned files.
3. Verification harness `tools/verify_m5_network_dedup.py`.
4. Passing results for `verify_m5_network_dedup.py`, `npx tsc --noEmit`, `npm run build`, and `tests/run_all_tests.py`.
5. Handoff report `handoff.md` in your working directory summarizing Observation, Logic Chain, Caveats, Conclusion, and Verification Method.
6. Notify orchestrator via `send_message`.

