# -*- coding: utf-8 -*-
"""
tests/test_challenger_m4_stress.py — Challenger 1 Empirical Stress Test Suite (Milestone 4 / R3)
══════════════════════════════════════════════════════════════════════════════════════════════
Adversarial stress-testing of:
1. Concurrent spawn & stop of 20 simulated bot threads via _stop_and_join_bot.
2. Complete dictionary leak audit across all 10 global tracking structures:
   _threads, _stop_events, _bot_managers, _reserved, _log_qs, _conn_states,
   _user_stopped, _castle_emails, _castle_users, _deleted_castles.
3. Thread stall isolation into _stalled_threads without caller hanging.
4. Proxy binding cleanup in proxy/proxy_manager.py upon castle & user deletion.
5. Verification of _user_stopped cleanup lifecycle on stop and deletion.
"""

import concurrent.futures
import os
import queue
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import api_server
from proxy import proxy_manager


class TestChallengerM4Stress(unittest.TestCase):
    """Empirical adversarial stress test for thread lifecycles and dictionary leaks."""

    def setUp(self):
        with api_server._lock:
            api_server._threads.clear()
            api_server._stop_events.clear()
            api_server._bot_managers.clear()
            api_server._reserved.clear()
            api_server._log_qs.clear()
            api_server._conn_states.clear()
            api_server._user_stopped.clear()
            api_server._castle_emails.clear()
            api_server._castle_users.clear()
            api_server._deleted_castles.clear()
            api_server._stalled_threads.clear()

    def tearDown(self):
        with api_server._lock:
            api_server._threads.clear()
            api_server._stop_events.clear()
            api_server._bot_managers.clear()
            api_server._reserved.clear()
            api_server._log_qs.clear()
            api_server._conn_states.clear()
            api_server._user_stopped.clear()
            api_server._castle_emails.clear()
            api_server._castle_users.clear()
            api_server._deleted_castles.clear()
            api_server._stalled_threads.clear()

    def test_concurrent_spawn_and_stop_20_bots(self):
        """Stress-test: Spawn 20 bots concurrently, stop concurrently, verify join & cleanups."""
        num_bots = 20
        cids = [f"stress_cid_{i:02d}" for i in range(num_bots)]
        threads = []
        started_events = [threading.Event() for _ in range(num_bots)]

        def _make_simulated_bot_worker(idx, cid, stop_ev, started_ev):
            def _worker():
                started_ev.set()
                # Simulate cooperative bot loop waiting on stop_event
                stop_ev.wait(timeout=10.0)
            return _worker

        # 1. Spawn 20 simulated bot threads and register in global structures
        for i, cid in enumerate(cids):
            stop_ev = threading.Event()
            mgr = MagicMock()
            mgr.stop = MagicMock()
            lq = queue.Queue(maxsize=100)

            t = threading.Thread(
                target=_make_simulated_bot_worker(i, cid, stop_ev, started_events[i]),
                name=f"bot-{cid[:10]}",
                daemon=True,
            )
            threads.append(t)

            with api_server._lock:
                api_server._threads[cid] = t
                api_server._stop_events[cid] = stop_ev
                api_server._bot_managers[cid] = mgr
                api_server._reserved.add(cid)
                api_server._log_qs[cid] = lq
                api_server._conn_states[cid] = "connected"
                api_server._castle_emails[cid] = f"bot_{cid}@example.com"
                api_server._castle_users[cid] = f"user_{cid}"

            t.start()

        # Wait for all 20 threads to actually start running
        for ev in started_events:
            self.assertTrue(ev.wait(timeout=2.0), "Bot thread failed to start in time")

        # 2. Concurrently call _stop_and_join_bot on all 20 bots using ThreadPoolExecutor
        t0 = time.perf_counter()
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_cid = {
                executor.submit(api_server._stop_and_join_bot, cid, 3.0): cid
                for cid in cids
            }
            for future in concurrent.futures.as_completed(future_to_cid):
                cid = future_to_cid[future]
                results[cid] = future.result()
        elapsed = time.perf_counter() - t0

        print(f"\n  [Stress-20] Stopped and joined 20 bots concurrently in {elapsed:.3f}s")

        # Verify all threads joined successfully
        for cid in cids:
            self.assertTrue(results[cid], f"Bot {cid} was expected to join cleanly")

        for t in threads:
            self.assertFalse(t.is_alive(), f"Thread {t.name} is still alive!")

        # 3. Check leakage across all 10 tracking structures
        with api_server._lock:
            for cid in cids:
                self.assertNotIn(cid, api_server._threads, f"{cid} leaked in _threads")
                self.assertNotIn(cid, api_server._stop_events, f"{cid} leaked in _stop_events")
                self.assertNotIn(cid, api_server._bot_managers, f"{cid} leaked in _bot_managers")
                self.assertNotIn(cid, api_server._reserved, f"{cid} leaked in _reserved")
                self.assertNotIn(cid, api_server._log_qs, f"{cid} leaked in _log_qs")
                self.assertNotIn(cid, api_server._conn_states, f"{cid} leaked in _conn_states")
                self.assertNotIn(cid, api_server._user_stopped, f"{cid} leaked in _user_stopped")
                self.assertNotIn(cid, api_server._castle_emails, f"{cid} leaked in _castle_emails")
                self.assertNotIn(cid, api_server._castle_users, f"{cid} leaked in _castle_users")
                self.assertNotIn(cid, api_server._deleted_castles, f"{cid} leaked in _deleted_castles")
                self.assertNotIn(cid, api_server._stalled_threads, f"{cid} incorrectly in _stalled_threads")

    def test_uncooperative_thread_stall_quarantine(self):
        """Verify that stalled threads are isolated without blocking the caller."""
        stalled_cid = "uncooperative_cid_99"
        email = "stalled_bot@example.com"
        uid = "stalled_user_99"
        unblock_event = threading.Event()

        def _stubborn_worker():
            unblock_event.wait(timeout=10.0)

        t = threading.Thread(target=_stubborn_worker, name=f"bot-{stalled_cid[:10]}", daemon=True)
        t.start()

        with api_server._lock:
            api_server._threads[stalled_cid] = t
            api_server._stop_events[stalled_cid] = threading.Event()
            api_server._castle_emails[stalled_cid] = email
            api_server._castle_users[stalled_cid] = uid
            api_server._conn_states[stalled_cid] = "running"

        t0 = time.perf_counter()
        # Call stop with short timeout (0.2s)
        joined = api_server._stop_and_join_bot(stalled_cid, timeout=0.2)
        elapsed = time.perf_counter() - t0

        # Caller must return within ~250ms (not hang)
        self.assertFalse(joined, "Expected stubborn thread join to fail/timeout")
        self.assertLess(elapsed, 1.0, f"Caller hung for {elapsed:.3f}s")

        with api_server._lock:
            # Active thread tracking must be purged
            self.assertNotIn(stalled_cid, api_server._threads)
            # Must be recorded in _stalled_threads quarantine
            self.assertIn(stalled_cid, api_server._stalled_threads)
            info = api_server._stalled_threads[stalled_cid]
            self.assertEqual(info["ident"], t.ident)
            self.assertEqual(info["email"], email)
            self.assertEqual(info["user_id"], uid)
            self.assertIn("stalled_at", info)

        # Release thread
        unblock_event.set()
        t.join(timeout=1.0)

    def test_proxy_manager_cleanup_lifecycle(self):
        """Verify proxy bindings cleanup in proxy/proxy_manager.py on castle & user deletion."""
        email = "proxy_leak_test@domain.com"
        uid = "user_proxy_leak_01"
        proxy_url = "socks5://user:pass@127.0.0.1:1080"

        with proxy_manager._manager_lock:
            proxy_manager._castle_bindings[email] = proxy_url
            proxy_manager._user_bindings[uid] = proxy_url

        self.assertIn(email, proxy_manager._castle_bindings)
        self.assertIn(uid, proxy_manager._user_bindings)

        # Remove single castle proxy
        res = proxy_manager.remove_castle_proxy(email)
        self.assertTrue(res)
        with proxy_manager._manager_lock:
            self.assertNotIn(email, proxy_manager._castle_bindings)

        # Re-add and purge via user deletion
        with proxy_manager._manager_lock:
            proxy_manager._castle_bindings[email] = proxy_url
            proxy_manager._user_bindings[uid] = proxy_url

        proxy_manager.remove_user_proxy_bindings(uid, [email])
        with proxy_manager._manager_lock:
            self.assertNotIn(uid, proxy_manager._user_bindings)
            self.assertNotIn(email, proxy_manager._castle_bindings)

    def test_user_stopped_leak_on_stop_and_deletion(self):
        """Adversarial check: Verify if _user_stopped leaks IDs after _stop_and_join_bot and deletion."""
        cid = "cid_leak_check_01"
        ev = threading.Event()
        t = threading.Thread(target=lambda: ev.wait(timeout=2.0), daemon=True)
        t.start()

        with api_server._lock:
            api_server._threads[cid] = t
            api_server._stop_events[cid] = ev
            api_server._castle_emails[cid] = "leak@example.com"
            api_server._castle_users[cid] = "uid_leak"

        joined = api_server._stop_and_join_bot(cid, timeout=1.0)
        self.assertTrue(joined)

        # Empirical measurement of _user_stopped retention
        with api_server._lock:
            leaked_in_user_stopped = cid in api_server._user_stopped

        print(f"\n  [Leak-Check] _user_stopped retains castle_id after _stop_and_join_bot: {leaked_in_user_stopped}")
        self.assertFalse(leaked_in_user_stopped, f"{cid} was leaked in _user_stopped")
        self.assertNotIn(cid, api_server._user_stopped)


if __name__ == "__main__":
    unittest.main()
