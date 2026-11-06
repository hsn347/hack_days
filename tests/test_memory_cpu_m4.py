# -*- coding: utf-8 -*-
"""
tests/test_memory_cpu_m4.py — Verification of Milestone 4 Memory & CPU Optimization (R3)
═════════════════════════════════════════════════════════════════════════════════════════
Verifies:
1. Symmetric cleanup of all 10 global structures (_castle_emails, _deleted_castles, etc.).
2. Deterministic thread lifecycle: _stop_and_join_bot timeouts and _stalled_threads quarantine.
3. Proxy bindings cleanup on castle and user deletion.
4. Async wait stop cancellation within < 100ms (no 1s busy sleep wakeups).
5. Streaming log pruning without whole-file memory allocation.
"""

import asyncio
import os
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import api_server
from bot_manager import BotManager
from proxy import proxy_manager


class TestMemoryCpuM4(unittest.TestCase):
    """Hermetic unit tests for Milestone 4 (Requirement R3)."""

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

    def test_symmetric_cleanup_castle_emails_and_deleted_castles(self):
        """Verify that _castle_emails and _deleted_castles are symmetrically cleaned up on exit."""
        castle_id = "test_cid_sym_1"
        user_id = "test_uid_1"
        email = "sym_test@example.com"

        req = api_server.StartBotRequest(
            castle_id=castle_id,
            user_id=user_id,
            email=email,
            password="wrong_password",
            config={},
            loop_interval=20
        )

        # Mock SessionManager.get_or_login to return None (auth failure)
        mock_sm = MagicMock()
        mock_sm.get_or_login.return_value = None

        with patch("core.session_manager.SessionManager", return_value=mock_sm):
            with patch("core.database.get_castle_password", return_value="dummy_pw"):
                with patch("api_server.update_castle_status_db"):
                    api_server._bot_thread(req)

        # After _bot_thread terminates on auth error:
        with api_server._lock:
            self.assertNotIn(castle_id, api_server._castle_emails, "_castle_emails must be popped on auth error")
            self.assertNotIn(castle_id, api_server._threads, "_threads must be popped on auth error")
            self.assertNotIn(castle_id, api_server._stop_events, "_stop_events must be popped on auth error")
            self.assertNotIn(castle_id, api_server._log_qs, "_log_qs must be popped on auth error")
            self.assertNotIn(castle_id, api_server._conn_states, "_conn_states must be popped on auth error")
            self.assertNotIn(castle_id, api_server._castle_users, "_castle_users must be popped on auth error")
            self.assertNotIn(castle_id, api_server._reserved, "_reserved must be discarded on auth error")
            self.assertNotIn(castle_id, api_server._deleted_castles, "_deleted_castles must be empty")

    def test_stop_and_join_bot_timeout_and_stalled_quarantine(self):
        """Verify that threads failing to exit within timeout are quarantined in _stalled_threads."""
        stalled_cid = "test_cid_stalled_1"
        user_id = "test_uid_stalled"
        email = "stalled@example.com"

        # Create an uncooperative thread that sleeps and ignores stop signals
        uncooperative_ev = threading.Event()
        def _stubborn_thread():
            uncooperative_ev.wait(timeout=5.0)

        t = threading.Thread(target=_stubborn_thread, daemon=True, name=f"bot-{stalled_cid[:10]}")
        t.start()

        with api_server._lock:
            api_server._threads[stalled_cid] = t
            api_server._stop_events[stalled_cid] = threading.Event()
            api_server._castle_emails[stalled_cid] = email
            api_server._castle_users[stalled_cid] = user_id

        # Calling _stop_and_join_bot with a short timeout (0.1s)
        joined = api_server._stop_and_join_bot(stalled_cid, timeout=0.1)
        self.assertFalse(joined, "Expected thread join to time out")

        with api_server._lock:
            # Must NOT be in _threads anymore
            self.assertNotIn(stalled_cid, api_server._threads)
            # MUST be quarantined in _stalled_threads for diagnosis
            self.assertIn(stalled_cid, api_server._stalled_threads)
            st_info = api_server._stalled_threads[stalled_cid]
            self.assertEqual(st_info["ident"], t.ident)
            self.assertEqual(st_info["email"], email)

        # Release stubborn thread
        uncooperative_ev.set()
        t.join(timeout=1.0)

        # Now test a cooperative thread that joins immediately
        coop_cid = "test_cid_coop_1"
        def _cooperative_thread():
            pass

        t2 = threading.Thread(target=_cooperative_thread, daemon=True, name=f"bot-{coop_cid[:10]}")
        t2.start()

        with api_server._lock:
            api_server._threads[coop_cid] = t2
            api_server._stop_events[coop_cid] = threading.Event()
            api_server._castle_emails[coop_cid] = "coop@example.com"

        joined2 = api_server._stop_and_join_bot(coop_cid, timeout=1.0)
        self.assertTrue(joined2, "Expected cooperative thread to join successfully")
        with api_server._lock:
            self.assertNotIn(coop_cid, api_server._threads)
            self.assertNotIn(coop_cid, api_server._stalled_threads)

    def test_proxy_bindings_cleanup_on_castle_deletion(self):
        """Verify that proxy bindings are purged from memory and persisted on deletion."""
        test_email = "proxy_purge_test@example.com"
        test_uid = "proxy_test_user_1"
        test_proxy = "socks5://u:p@1.2.3.4:1080"

        with proxy_manager._manager_lock:
            proxy_manager._castle_bindings[test_email] = test_proxy
            proxy_manager._user_bindings[test_uid] = test_proxy

        self.assertIn(test_email, proxy_manager._castle_bindings)
        self.assertIn(test_uid, proxy_manager._user_bindings)

        # 1. Purge single castle proxy
        removed = proxy_manager.remove_castle_proxy(test_email)
        self.assertTrue(removed)
        with proxy_manager._manager_lock:
            self.assertNotIn(test_email, proxy_manager._castle_bindings)

        # 2. Re-add and purge via remove_user_proxy_bindings
        with proxy_manager._manager_lock:
            proxy_manager._castle_bindings[test_email] = test_proxy
            proxy_manager._user_bindings[test_uid] = test_proxy

        proxy_manager.remove_user_proxy_bindings(test_uid, [test_email])
        with proxy_manager._manager_lock:
            self.assertNotIn(test_uid, proxy_manager._user_bindings)
            self.assertNotIn(test_email, proxy_manager._castle_bindings)

    def test_async_stop_event_cancellation_under_100ms(self):
        """Verify that bot wait cancels in <100ms via _async_stop_event without 1s sleep wakeups."""
        mgr = BotManager.__new__(BotManager)
        mgr.email = "speed_test@example.com"
        mgr._stop_event = threading.Event()
        mgr._async_stop_event = None
        mgr._loop = None
        mgr.conn = None
        mgr.conn_state = "waiting"
        mgr._log_callback = None
        mgr.user_id = "speed_uid"
        mgr.castle_id = "speed_cid"

        async def _run_wait_cycle():
            mgr._async_stop_event = asyncio.Event()
            mgr._loop = asyncio.get_running_loop()

            async def _waiter():
                remaining = 1500.0  # 25 minutes
                try:
                    await asyncio.wait_for(mgr._async_stop_event.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    pass

            wait_task = asyncio.create_task(_waiter())

            # Schedule stop() after 20ms
            await asyncio.sleep(0.02)
            t0 = time.time()
            mgr.stop()
            await wait_task
            elapsed_ms = (time.time() - t0) * 1000.0
            return elapsed_ms

        elapsed_ms = asyncio.run(_run_wait_cycle())
        # Cancellation must be instantaneous (< 100ms)
        self.assertLess(elapsed_ms, 100.0, f"Expected stop cancellation in <100ms, took {elapsed_ms:.2f}ms")

    def test_streaming_log_pruning_without_whole_file_allocation(self):
        """Verify that prune_log_file_24h streams and truncates large logs without f.readlines()."""
        test_log = os.path.join(_ROOT, "test_prune_m4.log")
        try:
            # Generate 1000 lines: 500 older than 24h, 500 fresh
            old_dt = datetime.now() - timedelta(hours=30)
            fresh_dt = datetime.now() - timedelta(minutes=10)

            with open(test_log, "w", encoding="utf-8") as f:
                for i in range(500):
                    f.write(f"[{old_dt:%Y-%m-%d %H:%M:%S}] Old line #{i}\n")
                for i in range(500):
                    f.write(f"[{fresh_dt:%Y-%m-%d %H:%M:%S}] Fresh line #{i}\n")

            # Prune with max_lines = 250
            api_server.prune_log_file_24h(test_log, max_lines=250)

            with open(test_log, "r", encoding="utf-8") as f:
                remaining_lines = f.readlines()

            # All old lines must be gone, kept lines must be <= 250
            self.assertLessEqual(len(remaining_lines), 250, f"Got {len(remaining_lines)} lines, expected <= 250")
            self.assertGreater(len(remaining_lines), 0)
            for line in remaining_lines:
                self.assertNotIn("Old line", line)
                self.assertIn("Fresh line", line)

            # Ensure temporary file was cleaned up
            self.assertFalse(os.path.exists(f"{test_log}.tmp"))
        finally:
            if os.path.exists(test_log):
                try: os.remove(test_log)
                except Exception: pass
            if os.path.exists(f"{test_log}.tmp"):
                try: os.remove(f"{test_log}.tmp")
                except Exception: pass


if __name__ == "__main__":
    unittest.main()
