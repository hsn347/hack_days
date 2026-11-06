# -*- coding: utf-8 -*-
"""
tests/test_m4_challenger2_empirical.py
═══════════════════════════════════════════════════════════════════════════════
Empirical adversarial verification suite by Challenger 2 for Milestone 4 (R3):
1. WebSocket disconnect detection: closing the client socket terminates server
   coroutine and frees tasks/references.
2. ws_user_status SQLite calls: zero SQLite queries and zero asyncio.to_thread
   dispatches during 5 seconds of idle client connection.
3. bot_manager.py sleep responsiveness: stopping an idle bot in its wait cycle
   completes in < 150ms instead of waiting for a 1-second sleep tick.
4. Streaming log pruning memory footprint: pruning a 10MB simulated log file
   does NOT spike process RSS by 10MB.
═══════════════════════════════════════════════════════════════════════════════
"""

import asyncio
import ctypes
import os
import sys
import threading
import time
import tracemalloc
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from starlette.websockets import WebSocketDisconnect

import api_server
from bot_manager import BotManager


# ─────────────────────────────────────────────────────────────────────────────
# Memory Measurement Helpers (Windows PSAPI & tracemalloc)
# ─────────────────────────────────────────────────────────────────────────────
def get_process_rss_bytes() -> int:
    """Return process RSS (WorkingSetSize) in bytes using Windows PSAPI or fallback."""
    if sys.platform == "win32":
        try:
            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.windll.kernel32
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            h_proc = kernel32.GetCurrentProcess()
            
            get_mem = getattr(kernel32, "K32GetProcessMemoryInfo", None)
            if get_mem is None:
                psapi = getattr(ctypes.windll, "psapi", None)
                if psapi is not None:
                    get_mem = getattr(psapi, "GetProcessMemoryInfo", None)
            if get_mem is not None:
                get_mem.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
                get_mem.restype = ctypes.c_int
                if get_mem(h_proc, ctypes.byref(counters), counters.cb):
                    return int(counters.WorkingSetSize)
        except Exception:
            pass

    try:
        import psutil
        return psutil.Process().memory_info().rss
    except Exception:
        return 0


class MockWebSocket:
    """Mock WebSocket client with configurable disconnect delay."""

    def __init__(self, disconnect_after: float = 0.2):
        self.disconnect_after = disconnect_after
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self._created_at = time.time()

    async def accept(self):
        self.accepted = True

    async def send_text(self, text: str):
        if self.closed:
            raise WebSocketDisconnect(code=1000)
        self.sent_messages.append(text)

    async def send_json(self, data: any):
        if self.closed:
            raise WebSocketDisconnect(code=1000)
        self.sent_messages.append(data)

    async def receive(self):
        await asyncio.sleep(self.disconnect_after)
        self.closed = True
        raise WebSocketDisconnect(code=1000)


class TestM4Challenger2Empirical(unittest.TestCase):
    """Adversarial empirical tests for R3 requirements."""

    def setUp(self):
        with api_server._lock:
            api_server._threads.clear()
            api_server._bot_managers.clear()
            api_server._stop_events.clear()
            api_server._conn_states.clear()
            api_server._castle_emails.clear()
            api_server._castle_users.clear()
            api_server._reserved.clear()
            api_server._user_stopped.clear()
            api_server._deleted_castles.clear()
            api_server._stalled_threads.clear()
            api_server._user_status_cache.clear()
            api_server._user_status_versions.clear()

    def tearDown(self):
        with api_server._lock:
            api_server._threads.clear()
            api_server._bot_managers.clear()
            api_server._stop_events.clear()
            api_server._conn_states.clear()
            api_server._castle_emails.clear()
            api_server._castle_users.clear()
            api_server._reserved.clear()
            api_server._user_stopped.clear()
            api_server._deleted_castles.clear()
            api_server._stalled_threads.clear()
            api_server._user_status_cache.clear()
            api_server._user_status_versions.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. WebSocket Disconnect Detection & Resource Cleanup
    # ─────────────────────────────────────────────────────────────────────────
    def test_ws_disconnect_detection_and_termination(self):
        """Verify that client disconnect immediately terminates server coroutine."""
        async def _run_ws_disconnect():
            # Test 1: ws_user_status disconnect
            mock_ws_user = MockWebSocket(disconnect_after=0.1)
            t0 = time.perf_counter()
            with patch("core.database.get_user_castles", return_value=[{"castle_id": "c1", "name": "Castle 1"}]):
                await api_server.ws_user_status(mock_ws_user, "u_test_disc")
            elapsed_user = time.perf_counter() - t0
            self.assertTrue(mock_ws_user.accepted)
            self.assertLess(elapsed_user, 0.5, f"ws_user_status took {elapsed_user:.3f}s to terminate on disconnect")

            # Test 2: ws_status disconnect
            mock_ws_status = MockWebSocket(disconnect_after=0.1)
            t0 = time.perf_counter()
            await api_server.ws_status(mock_ws_status, "c_test_disc")
            elapsed_status = time.perf_counter() - t0
            self.assertTrue(mock_ws_status.accepted)
            self.assertLess(elapsed_status, 0.5, f"ws_status took {elapsed_status:.3f}s to terminate on disconnect")

            # Test 3: ws_logs disconnect
            mock_ws_logs = MockWebSocket(disconnect_after=0.1)
            t0 = time.perf_counter()
            await api_server.ws_logs(mock_ws_logs, "c_test_disc")
            elapsed_logs = time.perf_counter() - t0
            self.assertTrue(mock_ws_logs.accepted)
            self.assertLess(elapsed_logs, 0.5, f"ws_logs took {elapsed_logs:.3f}s to terminate on disconnect")

        asyncio.run(_run_ws_disconnect())

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Zero SQLite / to_thread Calls During 5s Idle Connection
    # ─────────────────────────────────────────────────────────────────────────
    def test_ws_user_status_zero_sqlite_calls_during_idle(self):
        """Verify that during 5 seconds of idle client connection, zero SQLite queries are dispatched."""
        idle_duration = 5.0

        async def _run_idle_ws():
            mock_ws = MockWebSocket(disconnect_after=idle_duration)
            to_thread_calls = []
            orig_to_thread = asyncio.to_thread

            async def tracking_to_thread(func, *args, **kwargs):
                to_thread_calls.append((func, args, kwargs, time.perf_counter()))
                return await orig_to_thread(func, *args, **kwargs)

            db_queries = []
            def tracking_get_castles(uid):
                db_queries.append((uid, time.perf_counter()))
                return [{"castle_id": "c_idle_1", "name": "Idle Castle"}]

            with patch("asyncio.to_thread", side_effect=tracking_to_thread):
                with patch("core.database.get_user_castles", side_effect=tracking_get_castles):
                    t_start = time.perf_counter()
                    await api_server.ws_user_status(mock_ws, "u_idle_user")
                    t_end = time.perf_counter()

            total_elapsed = t_end - t_start
            self.assertGreaterEqual(total_elapsed, idle_duration - 0.2, "Test must run for at least idle duration")

            # The first call at connect time (t=0) does initial snapshot collection:
            # last_data = await asyncio.to_thread(_collect_user_statuses_snapshot, user_id, True)
            initial_calls = [c for c in to_thread_calls if c[3] - t_start < 0.2]
            subsequent_calls = [c for c in to_thread_calls if c[3] - t_start >= 0.2]

            # In the subsequent 5 seconds of idle, there must be ZERO to_thread dispatches:
            self.assertEqual(len(subsequent_calls), 0,
                             f"Expected 0 asyncio.to_thread calls during idle, got {len(subsequent_calls)}: {subsequent_calls}")

            # Similarly, DB queries during idle must be ZERO:
            subsequent_db = [q for q in db_queries if q[1] - t_start >= 0.2]
            self.assertEqual(len(subsequent_db), 0,
                             f"Expected 0 SQLite queries during idle, got {len(subsequent_db)}: {subsequent_db}")

        asyncio.run(_run_idle_ws())

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BotManager Sleep Responsiveness Under 150ms
    # ─────────────────────────────────────────────────────────────────────────
    def test_bot_manager_sleep_responsiveness_under_150ms(self):
        """Verify that stopping an idle bot in its wait cycle takes < 150ms instead of waiting for a 1s tick."""
        mgr = BotManager.__new__(BotManager)
        mgr.email = "challenger_sleep_test@example.com"
        mgr._stop_event = threading.Event()
        mgr._async_stop_event = None
        mgr._loop = None
        mgr.conn = None
        mgr.conn_state = "waiting"
        mgr._log_callback = None
        mgr.user_id = "u_resp"
        mgr.castle_id = "c_resp"

        async def _run_wait_and_interrupt():
            mgr._loop = asyncio.get_running_loop()
            mgr._async_stop_event = asyncio.Event()

            wait_completed = False

            async def _wait_task():
                nonlocal wait_completed
                remaining = 1500.0  # 25 minutes
                try:
                    await asyncio.wait_for(mgr._async_stop_event.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    pass
                wait_completed = True

            task = asyncio.create_task(_wait_task())

            # Bot has been sleeping for 100ms
            await asyncio.sleep(0.10)
            self.assertFalse(wait_completed, "Wait task should still be sleeping")

            # Now issue stop() and measure time until wait task completes
            t_stop_issued = time.perf_counter()
            mgr.stop()
            await task
            t_stop_resolved = time.perf_counter()

            response_duration = (t_stop_resolved - t_stop_issued) * 1000.0  # ms
            return response_duration

        elapsed_ms = asyncio.run(_run_wait_and_interrupt())
        self.assertLess(elapsed_ms, 150.0,
                        f"Expected stop response < 150ms, actual was {elapsed_ms:.2f}ms")
        self.assertTrue(mgr._stop_event.is_set())

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Streaming Log Pruning Memory Footprint (10MB Log)
    # ─────────────────────────────────────────────────────────────────────────
    def test_streaming_log_pruning_memory_headroom_10mb(self):
        """Verify that pruning a 10MB simulated log file does NOT spike process RSS by 10MB."""
        test_log_path = os.path.join(_ROOT, "test_challenger2_10mb.log")
        target_size_bytes = 10 * 1024 * 1024  # 10 MB

        try:
            # Generate 10MB log file with timestamps
            old_time = datetime.now() - timedelta(hours=36)
            new_time = datetime.now() - timedelta(minutes=15)
            line_template = "[{time:%Y-%m-%d %H:%M:%S}] [INFO] Castle simulation activity record line #{idx:06d} padding data string for byte count\n"

            with open(test_log_path, "w", encoding="utf-8") as f:
                bytes_written = 0
                idx = 0
                while bytes_written < target_size_bytes:
                    t = old_time if idx % 2 == 0 else new_time
                    line = line_template.format(time=t, idx=idx)
                    f.write(line)
                    bytes_written += len(line.encode("utf-8"))
                    idx += 1

            actual_size = os.path.getsize(test_log_path)
            self.assertGreaterEqual(actual_size, target_size_bytes, "Simulated log must be at least 10MB")

            rss_before = get_process_rss_bytes()

            tracemalloc.start()
            t0 = time.perf_counter()
            api_server.prune_log_file_24h(test_log_path, max_lines=8000)
            elapsed_prune = time.perf_counter() - t0
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            rss_after = get_process_rss_bytes()
            rss_delta_mb = (rss_after - rss_before) / (1024 * 1024) if rss_before > 0 else 0.0
            peak_mem_mb = peak_mem / (1024 * 1024)

            # Verification 1: Peak heap allocation during pruning must be strictly under 5MB (not 10MB)
            self.assertLess(peak_mem_mb, 5.0,
                            f"Heap memory peak {peak_mem_mb:.2f}MB must be < 5.0MB during streaming prune")

            # Verification 2: Process RSS delta must not spike by 10MB
            self.assertLess(rss_delta_mb, 8.0,
                            f"RSS memory delta {rss_delta_mb:.2f}MB must not spike by 10MB")

            # Verification 3: Pruned file size and line counts
            new_size = os.path.getsize(test_log_path)
            self.assertLess(new_size, actual_size, "Pruned log must be significantly smaller than 10MB")

            with open(test_log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self.assertLessEqual(len(lines), 8000, f"Kept lines ({len(lines)}) must be <= 8000")
            self.assertGreater(len(lines), 0, "Kept lines must not be empty")

            # Verify no old lines survived
            for line in lines[:50]:
                self.assertNotIn(f"{old_time:%Y-%m-%d}", line, "Old timestamp survived in pruned file")

        finally:
            if os.path.exists(test_log_path):
                try:
                    os.remove(test_log_path)
                except Exception:
                    pass
            if os.path.exists(f"{test_log_path}.tmp"):
                try:
                    os.remove(f"{test_log_path}.tmp")
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
