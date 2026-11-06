# Technical Report & Empirical Stress Test Plan: Milestone 5 WebSocket Multiplexer & Connection Scaling

**Agent:** Challenger M5 (Instance 2) — Empirical Challenger (`teamwork_challenger`)  
**Parent Conversation ID:** `44132d7d-07d0-4709-a292-a8e4727a82fd`  
**Date:** 2026-11-02  
**Target Milestone:** Milestone 5 (Network Optimization, Request Deduplication, WebSocket Multiplexing)  
**Compliance:** Strict adherence to GEMINI.md Rule 4 (Strict Ban on Server Deployment) & Rule 5 (Strict File-Report-First Rule).

---

## 1. Problem Diagnosis & Motivation

Milestone 5 introduced multiplexed WebSocket subscriptions (`useUserBotStatuses.ts`, `useMultiplexedBotStatus`), replacing individual per-castle WebSockets (`/ws/status/{castle_id}`) with a unified endpoint (`/ws/user-status/{user_id}`).

While Worker M5 provided static AST checks and a lightweight unit simulation in `tools/verify_m5_network_dedup.py`, an empirical stress test is required to independently challenge the implementation against real-world chaos scenarios:

1. **Mass Card Concurrency (50 Cards)**:
   Does mounting 50 castle cards concurrently on a single dashboard page create strictly **1** underlying WebSocket connection per user, or does race condition during concurrent mounts spawn multiple redundant connections?
2. **Reference-Counted Lifecycle & Grace Period**:
   Does unmounting 49 cards keep the single connection active? When the 50th card unmounts (ref count = 0), does it properly trigger the 3-second grace period without immediately severing the connection? If a card remounts during the grace period (e.g. fast tab toggle), is the timer cancelled without socket reconnection churn?
3. **Account Switch / Logout Teardown**:
   When `switchAccount` or `logout` triggers `purgeUserDataOnLogout`, are all active user sockets (`UserStatusMultiplexer`) forcefully closed immediately and the global registry purged, leaving zero lingering or zombie connections?
4. **Backend AsyncIO Task Leak Prevention**:
   In `api_server.py`, does the FastAPI/Starlette WebSocket endpoint (`/ws/user-status/{user_id}`) cleanly catch `WebSocketDisconnect` and `asyncio.CancelledError` without leaking un-awaited background coroutines or accumulating zombie `asyncio.Task` instances on high-churn client disconnects?

---

## 2. Methodology & Test Harness Architecture

We will implement an empirical stress test suite: `tools/stress_m5_ws_multiplex.py` (and test harnesses) covering:

### Test Suite Structure:
- **Phase 1: Multiplexer Scaling & Dedup (50-Card Concurrency)**
  Simulate 50 concurrent card mountings for `user_A` and 50 cards for `user_B`. Verify socket count = 1 per user (total 2).
- **Phase 2: Ref-Counting & Grace-Period Cancellation**
  Unmount 49 cards for `user_A` -> socket remains alive.
  Unmount 50th card -> grace period starts.
  Remount a card at t = 1.0s -> verify grace period cancelled, socket preserved without reconnect.
  Unmount again and let grace period expire (>3.0s) -> verify socket disconnects and user entry purged.
- **Phase 3: Immediate User Account Switch Teardown**
  Mount cards for `user_C`. Call `purgeAllUserStatusSockets()`. Verify immediate teardown, socket closure, and map clearance.
- **Phase 4: Backend AsyncIO Task Leak Stress Test**
  Using FastAPI `TestClient` / async WebSocket client against `api_server.py` `/ws/user-status/{user_id}`:
  - Measure baseline `asyncio.all_tasks()`.
  - Connect 50 concurrent WebSocket clients.
  - Abruptly disconnect all 50 clients.
  - Allow event loop cycle to process disconnect handlers.
  - Measure final `asyncio.all_tasks()`.
  - Assert zero leaked tasks (baseline delta == 0).
- **Phase 5: Regression & Verification Suite Execution**
  - Run `python tools/verify_m5_network_dedup.py`
  - Run `npm run build` in `dashboard`
  - Run `python tests/run_all_tests.py`

---

## 3. Planned Commands & Expected Outcomes

| Step | Command | Expected Result |
|------|---------|-----------------|
| 1 | `python tools/stress_m5_ws_multiplex.py` | 100% pass across all 4 stress suites (Mounting 50 cards = 1 socket, grace timer lifecycle, account switch purge, 0 leaked asyncio tasks) |
| 2 | `python tools/verify_m5_network_dedup.py` | 71/71 tests pass |
| 3 | `cd dashboard && npm run build` | Zero TypeScript errors, clean production bundle |
| 4 | `python tests/run_all_tests.py` | 30/30 tests pass (100%) |

All operations are strictly local to `e:\osmanli`. No remote operations or servers are accessed.
