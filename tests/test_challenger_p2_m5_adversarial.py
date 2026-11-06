# -*- coding: utf-8 -*-
"""
tests/test_challenger_p2_m5_adversarial.py — Empirical Adversarial Stress Test Suite
══════════════════════════════════════════════════════════════════════════════════════
Milestone 5 (F12, F13 / Requirement R4) — Challenger 1 Adversarial Edge Harness
══════════════════════════════════════════════════════════════════════════════════════

Adversarial Stress Challenges:
1. Rapid Failure Churn Concurrency Stress:
   - High-concurrency simultaneous execution of rapid bot failure cycles (auth failure,
     connection loss, unexpected exception, fast cancellation).
   - Verifies lock contention safety, absence of deadlocks, zero dictionary/set leaks,
     zero zombie threads, and live process count == 0.

2. In-Flight Concurrent Deletion Under Varied Operational States:
   - Deletion of castles and users while threads/managers are actively inside varied
     operational states (active run, cycle wait, reconnecting backoff, other-device wait).
   - Concurrent double-deletion race condition challenge.
   - Verifies clean join, immediate stop event response, database purging, proxy binding
     purge, and zero zombie resurrection.

3. Stalled Thread Isolation & Diagnostic Quarantine Under Hostile Conditions:
   - Non-cooperative threads that ignore cancellation signals.
   - Enforces timeout bounds on _stop_and_join_bot (no caller hang).
   - Verifies strict exclusion from total_active and default live items.
   - Verifies accurate diagnostic retrieval under status="stalled".
   - Verifies robustness against repeated stop invocations and concurrent stall waves.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import api_server
from bot_manager import BotManager
import core.database as db
from proxy import proxy_manager


class TestChallengerP2M5Adversarial(unittest.TestCase):
    """Adversarial stress testing harness for Phase 2 Milestone 5."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="osmanli_challenger_m5_")
        self.db_path = os.path.join(self.temp_dir, "test_challenger.db")
        db.init_db(self.db_path)
        os.environ["CASTLES_DB_PATH"] = self.db_path

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
            api_server._user_status_cache.clear()
            api_server._user_status_versions.clear()

        with proxy_manager._lock:
            proxy_manager._castle_bindings.clear()

        self.admin_user = {
            "uid": "admin_challenger_uid",
            "email": "ibraboths@gmail.com",
            "role": "admin",
            "is_super_admin": True,
            "is_merchant_admin": False,
        }

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
            api_server._user_status_cache.clear()
            api_server._user_status_versions.clear()

        with proxy_manager._lock:
            proxy_manager._castle_bindings.clear()

        os.environ.pop("CASTLES_DB_PATH", None)
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # Challenge 1: Rapid Failure Churn Concurrency Stress
    # ══════════════════════════════════════════════════════════════════════════
    def test_rapid_failure_churn_concurrency_stress(self):
        """
        Adversarial Challenge 1:
        Simulate 12 bots concurrently experiencing rapid churn through failures
        (auth errors, runtime exceptions, sudden disconnects, rapid stop).
        Total 36 churn cycles executed concurrently.
        Assert 0 deadlocks, 0 leaked dictionaries, and 0 ghost live processes.
        """
        num_workers = 12
        cycles_per_worker = 3
        total_runs = num_workers * cycles_per_worker

        def _simulate_failure_worker(worker_id: int, cycle_idx: int):
            cid = f"churn_{worker_id}_{cycle_idx}"
            uid = f"user_{worker_id}"
            email = f"churn_{worker_id}_{cycle_idx}@test.com"

            # Create DB entry
            db.save_castle({
                "castle_id": cid,
                "user_id": uid,
                "email": email,
                "state": "idle",
            }, db_path=self.db_path)

            req = api_server.StartBotRequest(
                castle_id=cid,
                user_id=uid,
                email=email,
                password="pass",
                config={},
                loop_interval=10,
            )

            # Alternate between different failure modes
            mode = (worker_id + cycle_idx) % 3
            if mode == 0:
                # Auth failure mode
                mock_sm = MagicMock()
                mock_sm.get_or_login.return_value = None
                with patch("core.session_manager.SessionManager", return_value=mock_sm), \
                     patch("bot_manager.SessionManager", return_value=mock_sm):
                    api_server._bot_thread(req)
            elif mode == 1:
                # Startup crash exception mode
                mock_sm = MagicMock()
                mock_sm.get_or_login.side_effect = RuntimeError("Adversarial crash during login")
                with patch("core.session_manager.SessionManager", return_value=mock_sm), \
                     patch("bot_manager.SessionManager", return_value=mock_sm):
                    api_server._bot_thread(req)
            else:
                # In-flight runtime fault during loop
                mock_sm = MagicMock()
                mock_sm.get_or_login.return_value = MagicMock()
                with patch("core.session_manager.SessionManager", return_value=mock_sm), \
                     patch("bot_manager.SessionManager", return_value=mock_sm):
                    with patch("bot_manager.BotManager.run_loop", side_effect=ZeroDivisionError("Adversarial math fault")):
                        api_server._bot_thread(req)

        # Run concurrent churn via ThreadPoolExecutor
        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for w in range(num_workers):
                for c in range(cycles_per_worker):
                    futures.append(executor.submit(_simulate_failure_worker, w, c))
            for f in concurrent.futures.as_completed(futures):
                f.result()
        elapsed = time.perf_counter() - t_start

        # Verification 1: Execution completes quickly without deadlocks
        self.assertLess(elapsed, 10.0, f"Rapid churn took {elapsed:.2f}s, expected < 10.0s")

        # Verification 2: All 10 global tracking structures must have ZERO residual leaks
        with api_server._lock:
            self.assertEqual(len(api_server._threads), 0, f"Leaked threads: {api_server._threads.keys()}")
            self.assertEqual(len(api_server._stop_events), 0, f"Leaked stop_events: {api_server._stop_events.keys()}")
            self.assertEqual(len(api_server._bot_managers), 0, f"Leaked bot_managers: {api_server._bot_managers.keys()}")
            self.assertEqual(len(api_server._reserved), 0, f"Leaked reserved: {api_server._reserved}")
            self.assertEqual(len(api_server._log_qs), 0, f"Leaked log_qs: {api_server._log_qs.keys()}")
            self.assertEqual(len(api_server._conn_states), 0, f"Leaked conn_states: {api_server._conn_states.keys()}")
            self.assertEqual(len(api_server._castle_emails), 0, f"Leaked castle_emails: {api_server._castle_emails.keys()}")
            self.assertEqual(len(api_server._castle_users), 0, f"Leaked castle_users: {api_server._castle_users.keys()}")
            self.assertEqual(len(api_server._deleted_castles), 0, f"Leaked deleted_castles: {api_server._deleted_castles}")
            self.assertEqual(len(api_server._user_stopped), 0, f"Leaked user_stopped: {api_server._user_stopped}")
            self.assertEqual(len(api_server._stalled_threads), 0, f"Leaked stalled_threads: {api_server._stalled_threads.keys()}")

        # Verification 3: Live processes endpoint must report strictly 0 active
        live_res = api_server.get_admin_live_processes(admin=self.admin_user)
        items = live_res.get("processes") or live_res.get("items", [])
        self.assertEqual(live_res["summary"]["total_active"], 0)
        self.assertEqual(len(items), 0)

    # ══════════════════════════════════════════════════════════════════════════
    # Challenge 2: In-Flight Concurrent Deletion Under Varied Operational States
    # ══════════════════════════════════════════════════════════════════════════
    def test_in_flight_concurrent_deletion_stress(self):
        """
        Adversarial Challenge 2:
        Spawn 5 castles for a target user, each simulating a different operational state:
        - Castle A: active execution (running)
        - Castle B: waiting for next cycle with timer (waiting_next_cycle)
        - Castle C: reconnecting with backoff (reconnecting)
        - Castle D: other device login wait (other_device_login)
        - Castle E: starting transition (starting)
        Then execute concurrent deletions:
        - Concurrent delete_castle on Castle A while stopping
        - delete_user on the entire user holding Castles B, C, D, E
        - Race-condition double deletion call
        Assert all threads joined, proxy bindings purged, and zero resurrection.
        """
        uid = "u_stress_target"
        u_email = "target_inflight@test.com"
        db.create_user(uid, u_email, db_path=self.db_path)

        castles_spec = [
            ("c_inflight_run", "run@test.com", "running"),
            ("c_inflight_wait", "wait@test.com", "waiting_next_cycle"),
            ("c_inflight_rec", "rec@test.com", "reconnecting"),
            ("c_inflight_other", "other@test.com", "other_device_login"),
            ("c_inflight_start", "start@test.com", "starting"),
        ]

        threads = []
        stop_events = []
        managers = []

        for cid, email, state in castles_spec:
            db.save_castle({
                "castle_id": cid,
                "user_id": uid,
                "email": email,
                "state": state,
                "conn_state": state,
            }, db_path=self.db_path)

            proxy_url = f"http://proxy_{cid}:8080"
            proxy_manager.set_castle_proxy(email, proxy_url)

            stop_ev = threading.Event()
            stop_events.append(stop_ev)

            # Simulated bot manager
            mgr = BotManager.__new__(BotManager)
            mgr.castle_id = cid
            mgr.email = email
            mgr.user_id = uid
            mgr._stop_event = stop_ev
            mgr.conn_state = state
            mgr.conn = MagicMock()
            mgr.conn.is_connected = True
            mgr.current_task = "combat"
            mgr.current_task_name = "⚔️ قتال"
            mgr.status_message = f"State {state}"
            mgr.iteration = 1
            mgr.loop_interval_minutes = 60
            mgr.next_run_time = "2026-11-04T00:00:00Z" if state == "waiting_next_cycle" else None
            mgr.reconnect_attempt = 1 if state == "reconnecting" else 0
            mgr.max_reconnect_attempts = 10
            mgr.start_time = time.time()
            mgr.last_heartbeat = time.time()
            managers.append(mgr)

            # Simulated cooperative worker thread
            def _worker(ev=stop_ev):
                ev.wait(timeout=10.0)

            t = threading.Thread(target=_worker, name=f"bot-{cid}")
            t.start()
            threads.append(t)

            with api_server._lock:
                api_server._threads[cid] = t
                api_server._stop_events[cid] = stop_ev
                api_server._bot_managers[cid] = mgr
                api_server._reserved.add(cid)
                api_server._castle_emails[cid] = email
                api_server._castle_users[cid] = uid
                api_server._conn_states[cid] = state

        # Step 1: Concurrently trigger delete_castle on Castle A from 2 threads (race condition)
        cid_a, email_a, _ = castles_spec[0]
        delete_results = []

        def _do_delete_castle():
            try:
                res = api_server.delete_castle_endpoint(cid_a, current_user=self.admin_user)
                delete_results.append(res)
            except Exception as ex:
                delete_results.append({"status": "error", "error": str(ex)})

        t_del1 = threading.Thread(target=_do_delete_castle)
        t_del2 = threading.Thread(target=_do_delete_castle)
        t_del1.start()
        t_del2.start()
        t_del1.join(timeout=3.0)
        t_del2.join(timeout=3.0)

        # Thread A must be stopped and joined
        self.assertFalse(threads[0].is_alive(), "Thread A must be joined and dead")
        self.assertIsNone(proxy_manager.get_castle_proxy(email_a), "Proxy A must be purged")
        self.assertIsNone(db.get_castle(cid_a, db_path=self.db_path), "Castle A row must be deleted")

        # Step 2: Delete entire user holding remaining 4 castles in flight
        res_user = api_server.delete_user_endpoint(uid, admin=self.admin_user)
        self.assertEqual(res_user["status"], "success")

        # Verify all remaining threads joined and terminated
        for i, t in enumerate(threads[1:], start=1):
            self.assertFalse(t.is_alive(), f"Thread for {castles_spec[i][0]} must be joined and terminated")
            cid_i, email_i, _ = castles_spec[i]
            self.assertIsNone(proxy_manager.get_castle_proxy(email_i), f"Proxy for {email_i} must be purged")
            self.assertIsNone(db.get_castle(cid_i, db_path=self.db_path), f"Castle {cid_i} row must be deleted")

        # Verify user row deleted
        self.assertIsNone(db.get_user(uid, db_path=self.db_path))

        # Verify all global structures clean
        with api_server._lock:
            for cid, _, _ in castles_spec:
                self.assertNotIn(cid, api_server._threads)
                self.assertNotIn(cid, api_server._stop_events)
                self.assertNotIn(cid, api_server._bot_managers)
                self.assertNotIn(cid, api_server._castle_emails)
                self.assertNotIn(cid, api_server._castle_users)
                self.assertNotIn(cid, api_server._deleted_castles)
                self.assertNotIn(cid, api_server._user_stopped)

    # ══════════════════════════════════════════════════════════════════════════
    # Challenge 3: Stalled Thread Isolation & Recovery Under Hostile Conditions
    # ══════════════════════════════════════════════════════════════════════════
    def test_stalled_thread_quarantine_integrity(self):
        """
        Adversarial Challenge 3:
        Simulate hostile, non-cooperative threads that ignore cancellation signals.
        1. Ensure _stop_and_join_bot exits within timeout and does NOT hang the caller.
        2. Ensure stalled thread is quarantined into _stalled_threads.
        3. Ensure stalled thread is strictly excluded from total_active and default views.
        4. Ensure status="stalled" query retrieves it with diagnostic metadata.
        5. Stress test concurrent stall waves (4 stalled threads simultaneously).
        """
        # Create 4 non-cooperative threads that will ignore stop signals
        num_stalled = 4
        stalled_cids = [f"c_stall_adv_{i}" for i in range(num_stalled)]
        stalled_emails = [f"stall_{i}@adversarial.com" for i in range(num_stalled)]
        stalled_threads = []

        uncooperative_running = threading.Event()

        def _make_uncooperative_worker():
            def _uncooperative():
                # Non-cooperative loop that ignores stop signals and sleeps
                uncooperative_running.set()
                while True:
                    time.sleep(1.0)
            return _uncooperative

        for i, cid in enumerate(stalled_cids):
            t = threading.Thread(
                target=_make_uncooperative_worker(),
                name=f"bot-uncooperative-{cid}",
                daemon=True,  # Daemon so test process exits cleanly
            )
            t.start()
            stalled_threads.append(t)

            with api_server._lock:
                api_server._threads[cid] = t
                api_server._stop_events[cid] = threading.Event()
                api_server._castle_emails[cid] = stalled_emails[i]
                api_server._castle_users[cid] = "u_stall_adv"
                api_server._conn_states[cid] = "running"

        # 1. Stop all 4 stalled bots with a 0.2s join timeout
        t0 = time.perf_counter()
        results = []
        for cid in stalled_cids:
            joined = api_server._stop_and_join_bot(cid, timeout=0.2)
            results.append(joined)
        elapsed = time.perf_counter() - t0

        # Caller must not hang: 4 * 0.2s = ~0.8s, certainly < 2.5s
        self.assertLess(elapsed, 2.5, f"Stopping 4 stalled bots took {elapsed:.2f}s, must be bounded")
        for joined in results:
            self.assertFalse(joined, "Non-cooperative threads must return joined=False")

        # 2. All 4 must be quarantined in _stalled_threads
        with api_server._lock:
            for cid in stalled_cids:
                self.assertIn(cid, api_server._stalled_threads, f"{cid} must be in _stalled_threads")
                st_info = api_server._stalled_threads[cid]
                self.assertEqual(st_info["castle_id"], cid)
                self.assertTrue(st_info["thread"].is_alive())
                # Must be removed from active _threads
                self.assertNotIn(cid, api_server._threads)
                self.assertNotIn(cid, api_server._bot_managers)

        # 3. Live processes query (default / all) must have total_active == 0 and 0 items
        res_default = api_server.get_admin_live_processes(status="all", admin=self.admin_user)
        items_default = res_default.get("processes") or res_default.get("items", [])
        self.assertEqual(res_default["summary"]["total_active"], 0, "Stalled threads must NOT count in total_active")
        self.assertEqual(res_default["summary"]["stalled"], num_stalled, f"summary['stalled'] must be {num_stalled}")
        self.assertEqual(len(items_default), 0, "Default items list must NOT return stalled threads")

        # 4. Query status="stalled" must return all 4 quarantined threads
        res_stalled = api_server.get_admin_live_processes(status="stalled", admin=self.admin_user)
        items_stalled = res_stalled.get("processes") or res_stalled.get("items", [])
        self.assertEqual(len(items_stalled), num_stalled, f"Expected {num_stalled} stalled items")
        for item in items_stalled:
            self.assertTrue(item["is_stalled"])
            self.assertEqual(item["live_category"], "stalled")
            self.assertTrue(item["thread_alive"])

        # 5. Idempotent repeat stop call on a quarantined castle must not crash or duplicate
        repeat_joined = api_server._stop_and_join_bot(stalled_cids[0], timeout=0.1)
        self.assertTrue(repeat_joined, "Repeat stop when already popped from _threads returns True safely")
        self.assertIn(stalled_cids[0], api_server._stalled_threads, "Quarantine entry remains intact")


if __name__ == "__main__":
    unittest.main()
