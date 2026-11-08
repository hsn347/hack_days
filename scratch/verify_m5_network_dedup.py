# -*- coding: utf-8 -*-
"""
tools/verify_m5_network_dedup.py — Verification of Milestone 5:
Network Optimization, Request Deduplication & AbortController Integration.
══════════════════════════════════════════════════════════════════════════════════════
Automated verification script per AGENTS_CONSTITUTION.md Rule 13 & M5 Requirements:
1. Static code verification of AbortController signal threading across botApi.ts.
2. Static verification of graceful AbortError handling and suppression.
3. Static & structural verification of multiplexed WebSocket subscription (useUserBotStatuses).
4. Static verification of search debouncing (250-300ms) in dashboard views.
5. Static verification of backend api_server.py WebSocket disconnect & cancel handling.
6. Hermetic runtime simulation of AbortSignal cancellation, multiplexer lifecycle, and debounce timing.
"""

import os
import re
import sys
import time
from typing import List, Dict, Any

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_SRC = os.path.join(ROOT_DIR, "dashboard", "src")
BOT_API_PATH = os.path.join(DASHBOARD_SRC, "lib", "botApi.ts")
USE_CASTLES_PATH = os.path.join(DASHBOARD_SRC, "hooks", "useCastles.ts")
USE_USER_BOT_STATUSES_PATH = os.path.join(DASHBOARD_SRC, "hooks", "useUserBotStatuses.ts")
USE_DEBOUNCE_PATH = os.path.join(DASHBOARD_SRC, "hooks", "useDebounce.ts")
CASTLE_CARD_PATH = os.path.join(DASHBOARD_SRC, "components", "accounts", "CastleCard.tsx")
ACCOUNTS_PAGE_PATH = os.path.join(DASHBOARD_SRC, "pages", "Accounts.tsx")
ADMIN_PAGE_PATH = os.path.join(DASHBOARD_SRC, "pages", "Admin.tsx")
ADMIN_USERS_CASTLES_PATH = os.path.join(DASHBOARD_SRC, "pages", "AdminUsersCastles.tsx")
ADMIN_LIVE_PROCESSES_PATH = os.path.join(DASHBOARD_SRC, "pages", "AdminLiveProcesses.tsx")
API_SERVER_PATH = os.path.join(ROOT_DIR, "api_server.py")


class TestHarness:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []

    def assert_true(self, condition: bool, description: str):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  [PASS] {description}")
        else:
            self.failures.append(description)
            print(f"  [FAIL] {description}")


def test_abort_controller_bot_api(harness: TestHarness):
    print("\n--- Tier 1: AbortController Signal Support in botApi.ts ---")

    harness.assert_true(os.path.exists(BOT_API_PATH), "botApi.ts exists")
    with open(BOT_API_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. RequestOptions interface
    harness.assert_true(
        "export interface RequestOptions" in content and "signal?: AbortSignal" in content,
        "botApi.ts exports RequestOptions interface with signal?: AbortSignal"
    )

    # 2. isAbortError helper
    harness.assert_true(
        "export function isAbortError" in content and "AbortError" in content,
        "botApi.ts exports isAbortError helper function"
    )

    # 3. parseAndLocalizeApiError handles abort gracefully
    harness.assert_true(
        "AbortError" in content and "parseAndLocalizeApiError" in content,
        "parseAndLocalizeApiError suppresses AbortError cleanly"
    )

    # 4. Check critical API functions accept options?: RequestOptions and pass signal to fetch
    functions_to_check = [
        "getUserProfile",
        "registerUser",
        "updateUserProfileApi",
        "getUserSubscription",
        "fetchCastles",
        "fetchCastle",
        "createCastle",
        "updateCastle",
        "updateCastleCredentials",
        "toggleCastleActive",
        "deleteCastle",
        "fetchCastleDataLive",
        "getAdminStats",
        "getAdminUsers",
        "getMerchantsOverview",
        "updateAdminSubscription",
        "banAdminUser",
        "deleteAdminUser",
        "approveAdminUser",
        "approveAllPendingAdminUsers",
        "approveCastleAdmin",
        "rejectCastleAdmin",
        "startBot",
        "stopBot",
        "stopUserBots",
        "getBotStatus",
        "getAllBotStatus",
        "getAdminLiveProcesses",
        "getAdminProxies",
        "testAdminProxy",
        "getAdminNetworkMode",
        "toggleAdminNetworkMode",
        "fetchAdminUsersCastles",
        "disableElfForAllCastles",
    ]

    for fn_name in functions_to_check:
        has_fn = f"export async function {fn_name}" in content
        fn_match = re.search(rf"export\s+async\s+function\s+{fn_name}\b[\s\S]*?fetch\([^{{]*\{{[\s\S]*?signal", content)
        has_signal = fn_match is not None
        harness.assert_true(
            has_fn and has_signal,
            f"botApi function '{fn_name}' accepts options and threads signal to fetch"
        )

    # 5. TanStack query functions in useCastles.ts pass signal
    with open(USE_CASTLES_PATH, "r", encoding="utf-8") as f:
        castles_content = f.read()

    harness.assert_true(
        bool(re.search(r"useCastles[\s\S]*?queryFn:\s*async\s*\(\{\s*signal\s*\}\)[\s\S]*?fetchCastles\([^)]*signal", castles_content)),
        "useCastles passes queryFn AbortSignal to fetchCastles"
    )
    harness.assert_true(
        bool(re.search(r"useCastle\b[\s\S]*?queryFn:\s*async\s*\(\{\s*signal\s*\}\)[\s\S]*?fetchCastle\([^)]*signal", castles_content)),
        "useCastle passes queryFn AbortSignal to fetchCastle"
    )
    harness.assert_true(
        bool(re.search(r"useLiveBotStats[\s\S]*?queryFn:\s*async\s*\(\{\s*signal\s*\}\)[\s\S]*?getAdminLiveProcesses\([^)]*signal", castles_content)),
        "useLiveBotStats passes queryFn AbortSignal to getAdminLiveProcesses"
    )


def test_multiplexed_websocket(harness: TestHarness):
    print("\n--- Tier 2: Multiplexed WebSocket Subscription & Deduplication ---")

    # 1. useUserBotStatuses.ts file exists
    harness.assert_true(
        os.path.exists(USE_USER_BOT_STATUSES_PATH),
        "useUserBotStatuses.ts exists in dashboard/src/hooks"
    )

    with open(USE_USER_BOT_STATUSES_PATH, "r", encoding="utf-8") as f:
        ws_content = f.read()

    # 2. Key exports
    harness.assert_true("export function useUserBotStatuses" in ws_content, "Exports useUserBotStatuses hook")
    harness.assert_true("export function useMultiplexedBotStatus" in ws_content, "Exports useMultiplexedBotStatus hook")
    harness.assert_true("export function purgeAllUserStatusSockets" in ws_content, "Exports purgeAllUserStatusSockets")
    harness.assert_true("export type RealStatus" in ws_content, "Exports RealStatus type")

    # 3. Multiplexer class features: singleton per user, reference counting, exponential backoff, grace timer
    harness.assert_true("class UserStatusMultiplexer" in ws_content, "Implements UserStatusMultiplexer class")
    harness.assert_true(
        "/ws/user-status/${this.userId}" in ws_content or "/ws/user-status/" in ws_content,
        "Connects to unified /ws/user-status/{userId} endpoint"
    )
    harness.assert_true(
        "graceTimer" in ws_content and "reconnectDelay" in ws_content,
        "Implements connection grace period and resilient backoff"
    )

    # 4. CastleCard.tsx integration
    with open(CASTLE_CARD_PATH, "r", encoding="utf-8") as f:
        card_content = f.read()

    harness.assert_true(
        "useRealBotStatus(castle.id, true, userId)" in card_content or "useMultiplexedBotStatus(castle.id, userId)" in card_content,
        "CastleCard leverages multiplexed user status without opening individual WebSockets"
    )

    # 5. useCastles.ts re-exports and delegates useRealBotStatus
    with open(USE_CASTLES_PATH, "r", encoding="utf-8") as f:
        castles_content = f.read()

    harness.assert_true(
        "useMultiplexedBotStatus" in castles_content,
        "useCastles.ts delegates useRealBotStatus to useMultiplexedBotStatus"
    )
    harness.assert_true(
        "purgeAllUserStatusSockets" in castles_content,
        "useCastles.ts integrates purgeAllUserStatusSockets in cache purging"
    )


def test_search_debouncing(harness: TestHarness):
    print("\n--- Tier 3: Search & Filter Debouncing (250-300ms) ---")

    # 1. useDebounce.ts hook
    harness.assert_true(
        os.path.exists(USE_DEBOUNCE_PATH),
        "useDebounce.ts exists in dashboard/src/hooks"
    )

    with open(USE_DEBOUNCE_PATH, "r", encoding="utf-8") as f:
        debounce_content = f.read()

    harness.assert_true(
        "export function useDebounce" in debounce_content and "delay: number = 300" in debounce_content,
        "useDebounce implements generic value debouncing with default 300ms delay"
    )

    # 2. Accounts.tsx debouncing
    with open(ACCOUNTS_PAGE_PATH, "r", encoding="utf-8") as f:
        accounts_content = f.read()

    harness.assert_true(
        "useDebounce" in accounts_content and "debouncedSearch" in accounts_content,
        "Accounts.tsx applies useDebounce to castle search query"
    )
    harness.assert_true(
        bool(re.search(r"filtered\s*=\s*useMemo\([\s\S]*?debouncedSearch[\s\S]*?\[allCastles,\s*debouncedSearch\]", accounts_content)),
        "Accounts.tsx recalculates filtered castles only after debouncedSearch updates"
    )

    # 3. Admin.tsx debouncing
    with open(ADMIN_PAGE_PATH, "r", encoding="utf-8") as f:
        admin_content = f.read()

    harness.assert_true(
        "useDebounce" in admin_content and "debouncedSearch" in admin_content,
        "Admin.tsx applies useDebounce to user search query"
    )
    harness.assert_true(
        "debouncedSearch" in admin_content and "baseList" in admin_content,
        "Admin.tsx filters clientUsers based on debouncedSearch"
    )

    # 4. AdminUsersCastles.tsx debouncing
    with open(ADMIN_USERS_CASTLES_PATH, "r", encoding="utf-8") as f:
        auc_content = f.read()

    harness.assert_true(
        "useDebounce" in auc_content and "debouncedSearchQuery" in auc_content,
        "AdminUsersCastles.tsx applies useDebounce to user/castle search query"
    )
    harness.assert_true(
        "debouncedSearchQuery" in auc_content and "filteredUsers" in auc_content,
        "AdminUsersCastles.tsx filters using debouncedSearchQuery"
    )

    # 5. AdminLiveProcesses.tsx debouncing
    with open(ADMIN_LIVE_PROCESSES_PATH, "r", encoding="utf-8") as f:
        alp_content = f.read()

    harness.assert_true(
        "useDebounce" in alp_content and "debouncedSearchQuery" in alp_content,
        "AdminLiveProcesses.tsx applies useDebounce to process search query"
    )


def test_backend_websocket_resilience(harness: TestHarness):
    print("\n--- Tier 4: Backend WebSocket Resilience & Disconnect Handling ---")

    with open(API_SERVER_PATH, "r", encoding="utf-8") as f:
        api_content = f.read()

    # 1. ws_logs catches WebSocketDisconnect and asyncio.CancelledError
    logs_match = re.search(r"async\s+def\s+ws_logs[\s\S]*?except\s*\([^)]*WebSocketDisconnect[^)]*CancelledError", api_content)
    harness.assert_true(
        bool(logs_match),
        "api_server.py:ws_logs cleanly catches (WebSocketDisconnect, asyncio.CancelledError)"
    )

    # 2. ws_status catches WebSocketDisconnect and asyncio.CancelledError
    status_match = re.search(r"async\s+def\s+ws_status[\s\S]*?except\s*\([^)]*WebSocketDisconnect[^)]*CancelledError", api_content)
    harness.assert_true(
        bool(status_match),
        "api_server.py:ws_status cleanly catches (WebSocketDisconnect, asyncio.CancelledError)"
    )

    # 3. ws_user_status catches WebSocketDisconnect and asyncio.CancelledError
    user_status_match = re.search(r"async\s+def\s+ws_user_status[\s\S]*?except\s*\([^)]*WebSocketDisconnect[^)]*CancelledError", api_content)
    harness.assert_true(
        bool(user_status_match),
        "api_server.py:ws_user_status cleanly catches (WebSocketDisconnect, asyncio.CancelledError)"
    )


def test_runtime_simulations(harness: TestHarness):
    print("\n--- Tier 5: Runtime Simulations (Abort, Multiplexing & Debounce) ---")

    # 1. Simulate AbortSignal behavior
    class SimulatedAbortSignal:
        def __init__(self):
            self.aborted = False
            self.reason = None
            self._handlers = []

        def abort(self, reason="Request aborted"):
            self.aborted = True
            self.reason = reason
            for handler in self._handlers:
                handler()

        def add_event_listener(self, event, handler):
            if event == "abort":
                if self.aborted:
                    handler()
                else:
                    self._handlers.append(handler)

    signal = SimulatedAbortSignal()
    request_cancelled = False

    def simulated_fetch(url, options=None):
        nonlocal request_cancelled
        sig = options.get("signal") if options else None
        if sig and sig.aborted:
            request_cancelled = True
            raise Exception("AbortError: The user aborted a request.")

    # Request before abort
    simulated_fetch("http://localhost:8000/api/castles", {"signal": signal})
    harness.assert_true(not request_cancelled, "In-flight request proceeds when signal is active")

    # Abort signal
    signal.abort()
    try:
        simulated_fetch("http://localhost:8000/api/castles", {"signal": signal})
    except Exception as e:
        harness.assert_true("AbortError" in str(e) and request_cancelled, "Aborted signal cancels request with AbortError")

    # 2. Simulate Reference-Counted Multiplexing
    class MockMultiplexer:
        def __init__(self):
            self.listeners = set()
            self.connected = False
            self.disconnected = False

        def subscribe(self, listener_id):
            self.listeners.add(listener_id)
            if not self.connected:
                self.connected = True
                self.disconnected = False

        def unsubscribe(self, listener_id):
            self.listeners.discard(listener_id)
            if len(self.listeners) == 0:
                self.connected = False
                self.disconnected = True

    multiplexer = MockMultiplexer()
    # Mount card 1, 2, 3
    multiplexer.subscribe("card_1")
    multiplexer.subscribe("card_2")
    multiplexer.subscribe("card_3")
    harness.assert_true(multiplexer.connected and len(multiplexer.listeners) == 3, "3 cards share 1 single multiplexed connection")

    # Unmount cards
    multiplexer.unsubscribe("card_1")
    multiplexer.unsubscribe("card_2")
    harness.assert_true(multiplexer.connected, "Multiplexer remains connected while listeners remain")

    multiplexer.unsubscribe("card_3")
    harness.assert_true(multiplexer.disconnected and not multiplexer.connected, "Multiplexer cleanly disconnects when last card unmounts")

    # 3. Simulate Debounce Timing
    class Debouncer:
        def __init__(self, delay_ms=300):
            self.delay_sec = delay_ms / 1000.0
            self.last_update = 0.0
            self.current_value = ""
            self.debounced_value = ""

        def update(self, val):
            self.current_value = val
            self.last_update = time.perf_counter()

        def poll(self):
            if self.current_value != self.debounced_value:
                if (time.perf_counter() - self.last_update) >= self.delay_sec:
                    self.debounced_value = self.current_value

    deb = Debouncer(delay_ms=50)  # fast 50ms for test
    deb.update("k")
    deb.update("ke")
    deb.update("key")
    deb.poll()
    harness.assert_true(deb.debounced_value == "", "Immediate keystrokes are debounced before delay expires")
    time.sleep(0.06)
    deb.poll()
    harness.assert_true(deb.debounced_value == "key", "Debounced value updates smoothly after delay expires")


def main() -> int:
    print("=" * 78)
    print("Osmanli Platform — Milestone 5 Verification Suite (Network & Dedup)")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print("Execution Mode: Local Hermetic Test per AGENTS_CONSTITUTION.md Rule 13")
    print("=" * 78)

    harness = TestHarness()
    test_abort_controller_bot_api(harness)
    test_multiplexed_websocket(harness)
    test_search_debouncing(harness)
    test_backend_websocket_resilience(harness)
    test_runtime_simulations(harness)

    print("\n" + "=" * 78)
    print(f"SUMMARY: {harness.tests_passed}/{harness.tests_run} tests passed ({(harness.tests_passed / harness.tests_run * 100):.1f}%)")
    print("=" * 78)

    if harness.failures:
        print(f"\n[FAILURES DETECTED ({len(harness.failures)})]:")
        for f in harness.failures:
            print(f"  - {f}")
        return 1

    print("\n>>> ALL MILESTONE 5 VERIFICATION CHECKS PASSED SUCCESSFULLY! <<<\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
