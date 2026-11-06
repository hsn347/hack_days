# -*- coding: utf-8 -*-
"""
tools/challenge_m3_lifecycle.py — Independent Empirical Challenge & Stress Suite for Milestone 3
════════════════════════════════════════════════════════════════════════════════════════════════
Adversarial verification of:
1. Exact classification of the 6 allowed states and task/countdown metadata.
2. Complete exclusion of stopped, deleted, finished, and dead bots from live processes.
3. Isolation of stalled threads (dead heartbeat, startup timeout, orphaned OS threads) into summary.stalled.
4. Thread decoupling: OS thread existence does not inflate total_active.
5. High-concurrency race condition testing on duplicate starts (same castle, same email).
6. Pagination boundaries, out-of-range pages, filtering, debounced search semantics.
"""

import os
import sys
import time
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import api_server
from bot_manager import BotManager


class Milestone3EmpiricalChallenge(unittest.TestCase):
    """Adversarial challenger suite for Milestone 3."""

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
        self.admin = {"email": "ibraboths@gmail.com", "is_super_admin": True, "role": "admin"}

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

    # ─────────────────────────────────────────────────────────────────────────
    # CHALLENGE 1: Empirical Verification of the 6 Allowed States
    # ─────────────────────────────────────────────────────────────────────────
    def test_challenge_six_allowed_states_full_fidelity(self):
        """Stress-test each of the 6 allowed states and verify required metadata."""
        now = time.time()

        def make_mgr(cid, email, state, **kwargs):
            mgr = BotManager.__new__(BotManager)
            mgr.castle_id = cid
            mgr.email = email
            mgr.user_id = f"usr_{cid}"
            mgr.conn = kwargs.get("conn", None)
            mgr._stop_event = MagicMock()
            mgr._stop_event.is_set.return_value = kwargs.get("is_stopped", False)
            mgr._last_kick_reason = kwargs.get("last_kick_reason", "")
            mgr.status_message = kwargs.get("status_message", "Operational")
            mgr.iteration = kwargs.get("iteration", 1)
            mgr.loop_interval_minutes = kwargs.get("loop_interval_minutes", 60)
            mgr.next_run_time = kwargs.get("next_run_time", None)
            mgr.reconnect_attempt = kwargs.get("reconnect_attempt", 0)
            mgr.max_reconnect_attempts = 10
            mgr.start_time = kwargs.get("start_time", now)
            mgr.last_heartbeat = kwargs.get("last_heartbeat", now)
            mgr.conn_state = state
            mgr.current_task = kwargs.get("current_task", None)
            mgr.current_task_name = kwargs.get("current_task_name", None)
            return mgr

        # 1. Running state
        conn_mock = MagicMock()
        conn_mock.is_connected = True
        mgr_running = make_mgr(
            "c_run", "run@test.com", "running",
            conn=conn_mock,
            current_task="train_infantry",
            current_task_name="⚔️ تدريب المشاة"
        )
        info_run = mgr_running.get_live_info()
        self.assertEqual(info_run["live_category"], "running")
        self.assertEqual(info_run["current_step"], "⚔️ تدريب المشاة")
        self.assertTrue(info_run["is_connection_alive"])

        # 2. Waiting for Next Cycle
        mgr_wait = make_mgr(
            "c_wait", "wait@test.com", "waiting_next_cycle",
            next_run_time="2026-11-03T08:00:00Z"
        )
        info_wait = mgr_wait.get_live_info()
        self.assertEqual(info_wait["live_category"], "waiting_next_cycle")
        self.assertEqual(info_wait["next_run_time"], "2026-11-03T08:00:00Z")

        # 3. Other Device Login
        mgr_kicked = make_mgr(
            "c_kick", "kick@test.com", "other_device_login",
            last_kick_reason="other device login detected",
            status_message="تم قطع الاتصال بسبب تسجيل الدخول من جهاز آخر"
        )
        info_kick = mgr_kicked.get_live_info()
        self.assertEqual(info_kick["live_category"], "other_device_login")
        self.assertEqual(info_kick["last_kick_reason"], "other device login detected")

        # 4. Reconnecting
        mgr_reconn = make_mgr(
            "c_reconn", "reconn@test.com", "reconnecting",
            reconnect_attempt=3,
            status_message="محاولة إعادة الاتصال (3/10)..."
        )
        info_reconn = mgr_reconn.get_live_info()
        self.assertEqual(info_reconn["live_category"], "reconnecting")
        self.assertEqual(info_reconn["reconnect_attempt"], 3)

        # 5. Waiting for Re-login
        mgr_relogin = make_mgr(
            "c_relogin", "relogin@test.com", "waiting_relogin",
            status_message="بانتظار إعادة تسجيل الدخول لتحديث رمز الجلسة"
        )
        info_relogin = mgr_relogin.get_live_info()
        self.assertEqual(info_relogin["live_category"], "waiting_relogin")

        # 6. Starting (startup grace period < 45s)
        mgr_starting = make_mgr(
            "c_start", "start@test.com", "starting",
            start_time=now - 5,
            status_message="جاري بدء التشغيل..."
        )
        info_starting = mgr_starting.get_live_info()
        self.assertEqual(info_starting["live_category"], "starting")

    # ─────────────────────────────────────────────────────────────────────────
    # CHALLENGE 2: Inactive/Stopped/Deleted Bots Must Never Appear in Live Processes
    # ─────────────────────────────────────────────────────────────────────────
    def test_challenge_stopped_deleted_completed_exclusion(self):
        """Bots that are stopped, deleted, or ended naturally must not appear in processes."""
        with api_server._lock:
            # Case A: Bot marked as stopped in _user_stopped
            mock_t_stopped = MagicMock()
            mock_t_stopped.is_alive.return_value = True
            mock_t_stopped.ident = 1001
            mock_t_stopped.name = "bot-c_stopped"
            api_server._threads["c_stopped"] = mock_t_stopped
            api_server._user_stopped.add("c_stopped")

            # Case B: Castle in _deleted_castles
            mock_t_del = MagicMock()
            mock_t_del.is_alive.return_value = True
            mock_t_del.ident = 1002
            mock_t_del.name = "bot-c_deleted"
            api_server._threads["c_deleted"] = mock_t_del
            api_server._deleted_castles.add("c_deleted")

            # Case C: Thread is not alive (exited / finished)
            mock_t_dead = MagicMock()
            mock_t_dead.is_alive.return_value = False
            mock_t_dead.ident = 1003
            mock_t_dead.name = "bot-c_dead"
            api_server._threads["c_dead"] = mock_t_dead

            # Case D: One genuine running bot
            mock_t_act = MagicMock()
            mock_t_act.is_alive.return_value = True
            mock_t_act.ident = 1004
            mock_t_act.name = "bot-c_active"
            api_server._threads["c_active"] = mock_t_act
            api_server._castle_emails["c_active"] = "active@test.com"
            api_server._castle_users["c_active"] = "user_act"

            mgr_active = MagicMock()
            mgr_active.get_live_info.return_value = {
                "castle_id": "c_active",
                "email": "active@test.com",
                "user_id": "user_act",
                "state": "running",
                "live_category": "running",
                "category_label": "شغالة فعلياً",
                "current_step": "جمع الموارد",
                "status_message": "Running ok",
                "is_stopped": False,
                "is_stalled": False,
                "uptime_seconds": 50,
            }
            api_server._bot_managers["c_active"] = mgr_active

        res = api_server.get_admin_live_processes(page=1, page_size=10, admin=self.admin)
        self.assertEqual(res["total_active"], 1)
        self.assertEqual(len(res["processes"]), 1)
        self.assertEqual(res["processes"][0]["castle_id"], "c_active")

        # Deleted castle must NOT be in active processes or stalled processes
        cids_in_processes = [p["castle_id"] for p in res["processes"]]
        self.assertNotIn("c_deleted", cids_in_processes)
        self.assertNotIn("c_dead", cids_in_processes)
        self.assertNotIn("c_stopped", cids_in_processes)

        # Stopped castle thread still alive must be in stalled_processes (isolated)
        stalled_cids = [s["castle_id"] for s in res.get("stalled_processes", [])]
        self.assertIn("c_stopped", stalled_cids)

    # ─────────────────────────────────────────────────────────────────────────
    # CHALLENGE 3: Stalled and Orphaned OS Thread Isolation
    # ─────────────────────────────────────────────────────────────────────────
    def test_challenge_orphaned_and_unresponsive_thread_isolation(self):
        """Simulate unresponsive threads and orphaned OS threads. Must be isolated into stalled."""
        now = time.time()

        with api_server._lock:
            # 1. Thread with BotManager having dead heartbeat (> 300s ago)
            t_unresp = MagicMock()
            t_unresp.is_alive.return_value = True
            t_unresp.ident = 2001
            t_unresp.name = "bot-c_unresp"
            api_server._threads["c_unresp"] = t_unresp
            api_server._castle_emails["c_unresp"] = "unresp@test.com"

            mgr_unresp = BotManager.__new__(BotManager)
            mgr_unresp.castle_id = "c_unresp"
            mgr_unresp.email = "unresp@test.com"
            mgr_unresp.user_id = "u1"
            mgr_unresp.conn = None
            mgr_unresp._stop_event = MagicMock()
            mgr_unresp._stop_event.is_set.return_value = False
            mgr_unresp._last_kick_reason = ""
            mgr_unresp.status_message = "Frozen task"
            mgr_unresp.start_time = now - 600
            mgr_unresp.last_heartbeat = now - 400  # 400s > 300s threshold
            mgr_unresp.conn_state = "running"
            api_server._bot_managers["c_unresp"] = mgr_unresp

            # 2. Thread stuck in "starting" for > 45s
            t_stuck_start = MagicMock()
            t_stuck_start.is_alive.return_value = True
            t_stuck_start.ident = 2002
            t_stuck_start.name = "bot-c_stuck_start"
            api_server._threads["c_stuck_start"] = t_stuck_start
            api_server._castle_emails["c_stuck_start"] = "stuck@test.com"

            mgr_stuck_start = BotManager.__new__(BotManager)
            mgr_stuck_start.castle_id = "c_stuck_start"
            mgr_stuck_start.email = "stuck@test.com"
            mgr_stuck_start.user_id = "u2"
            mgr_stuck_start.conn = None
            mgr_stuck_start._stop_event = MagicMock()
            mgr_stuck_start._stop_event.is_set.return_value = False
            mgr_stuck_start._last_kick_reason = ""
            mgr_stuck_start.status_message = "Starting stuck"
            mgr_stuck_start.start_time = now - 90  # 90s > 45s threshold
            mgr_stuck_start.last_heartbeat = now
            mgr_stuck_start.conn_state = "starting"
            api_server._bot_managers["c_stuck_start"] = mgr_stuck_start

            # 3. Legitimate running bot
            t_legit = MagicMock()
            t_legit.is_alive.return_value = True
            t_legit.ident = 2003
            t_legit.name = "bot-c_legit"
            api_server._threads["c_legit"] = t_legit
            api_server._castle_emails["c_legit"] = "legit@test.com"

            mgr_legit = BotManager.__new__(BotManager)
            mgr_legit.castle_id = "c_legit"
            mgr_legit.email = "legit@test.com"
            mgr_legit.user_id = "u3"
            mgr_legit.conn = MagicMock()
            mgr_legit.conn.is_connected = True
            mgr_legit._stop_event = MagicMock()
            mgr_legit._stop_event.is_set.return_value = False
            mgr_legit._last_kick_reason = ""
            mgr_legit.status_message = "Healthy"
            mgr_legit.start_time = now - 100
            mgr_legit.last_heartbeat = now
            mgr_legit.conn_state = "running"
            mgr_legit.current_task = "gather"
            mgr_legit.current_task_name = "🌾 جمع الحبوب"
            api_server._bot_managers["c_legit"] = mgr_legit

        # 4. Mock an orphaned OS thread in threading.enumerate() that has "bot-" prefix
        # but is completely unregistered in api_server._threads
        orphan_mock_th = MagicMock()
        orphan_mock_th.is_alive.return_value = True
        orphan_mock_th.ident = 99999
        orphan_mock_th.name = "bot-c_ghost_orphan"

        real_enumerate = threading.enumerate

        def mock_enumerate():
            return real_enumerate() + [orphan_mock_th]

        with patch("threading.enumerate", side_effect=mock_enumerate):
            res = api_server.get_admin_live_processes(page=1, page_size=25, admin=self.admin)

            # Verification: Only 1 legitimate active bot
            self.assertEqual(res["total_active"], 1, "Only healthy running bot should be in total_active")
            self.assertEqual(len(res["processes"]), 1)
            self.assertEqual(res["processes"][0]["castle_id"], "c_legit")

            # Verification: Stalled count must be exactly 3 (unresponsive + stuck starting + orphaned thread)
            self.assertEqual(res["summary"]["stalled"], 3, "All 3 unhealthy threads must be isolated to stalled")
            stalled_cids = {p["castle_id"] for p in res.get("stalled_processes", [])}
            self.assertIn("c_unresp", stalled_cids)
            self.assertIn("c_stuck_start", stalled_cids)
            self.assertIn("c_ghost_orphan", stalled_cids)

    # ─────────────────────────────────────────────────────────────────────────
    # CHALLENGE 4: High-Concurrency Duplicate Start Prevention
    # ─────────────────────────────────────────────────────────────────────────
    def test_challenge_concurrent_duplicate_start_prevention(self):
        """Simulate high concurrent bursts attempting duplicate starts on same castle and same email."""
        req_same_castle = api_server.StartBotRequest(
            castle_id="c_burst_dup",
            user_id="user_burst",
            email="burst@example.com",
            config={},
            loop_interval=30
        )

        success_count = 0
        failure_count = 0

        # Use RealThread to dispatch harness test threads while mocking Thread inside _start_bot_internal
        RealThread = threading.Thread
        count_lock = threading.Lock()

        with patch("threading.Thread") as mock_th:
            mock_instance = MagicMock()
            mock_instance.is_alive.return_value = True
            mock_th.return_value = mock_instance

            # 20 concurrent threads trying to start the same castle at the exact same millisecond
            num_workers = 20
            barrier = threading.Barrier(num_workers)

            def attempt_start():
                nonlocal success_count, failure_count
                barrier.wait()  # Synchronize threads to hit _start_bot_internal simultaneously
                res = api_server._start_bot_internal(req_same_castle)
                with count_lock:
                    if res:
                        success_count += 1
                    else:
                        failure_count += 1

            threads = [RealThread(target=attempt_start) for _ in range(num_workers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(success_count, 1, "Exactly one thread must succeed in starting the castle")
            self.assertEqual(failure_count, 19, "All 19 concurrent duplicate requests must be blocked")

        # Now test cross-castle same email duplicate start under concurrency
        req_same_email_other_castle = api_server.StartBotRequest(
            castle_id="c_burst_other_id",
            user_id="user_burst",
            email="burst@example.com",  # Same email as c_burst_dup
            config={},
            loop_interval=30
        )
        with patch("threading.Thread") as mock_th:
            mock_instance = MagicMock()
            mock_instance.is_alive.return_value = True
            mock_th.return_value = mock_instance

            res2 = api_server._start_bot_internal(req_same_email_other_castle)
            self.assertFalse(res2, "Must block duplicate start on different castle sharing the same active email")

    # ─────────────────────────────────────────────────────────────────────────
    # CHALLENGE 5: Pagination, Filter, and Search Semantics
    # ─────────────────────────────────────────────────────────────────────────
    def test_challenge_pagination_search_and_filtering(self):
        """Test pagination bounds, empty pages, edge case searches, and status filtering."""
        with api_server._lock:
            # Create 15 mock running bots
            for i in range(1, 16):
                cid = f"c_batch_{i:02d}"
                email = f"lord_{i:02d}@kingdom.com"
                th = MagicMock()
                th.is_alive.return_value = True
                th.ident = 3000 + i
                th.name = f"bot-{cid}"
                api_server._threads[cid] = th
                api_server._castle_emails[cid] = email
                api_server._castle_users[cid] = f"usr_{i}"

                mgr = MagicMock()
                cat = "running" if i <= 10 else "waiting_next_cycle"
                mgr.get_live_info.return_value = {
                    "castle_id": cid,
                    "email": email,
                    "user_id": f"usr_{i}",
                    "state": cat,
                    "live_category": cat,
                    "category_label": cat,
                    "status_message": f"Status for castle {i}",
                    "current_step": "حصاد القمح" if cat == "running" else None,
                    "iteration": 1,
                    "uptime_seconds": i * 10,
                    "is_connection_alive": cat == "running",
                    "is_stopped": False,
                    "is_stalled": False,
                    "start_time": time.time(),
                }
                api_server._bot_managers[cid] = mgr

        # 1. Page 1 of size 5 -> returns items 1-5, has_more=True
        p1 = api_server.get_admin_live_processes(page=1, page_size=5, admin=self.admin)
        self.assertEqual(len(p1["processes"]), 5)
        self.assertEqual(p1["total_count"], 15)
        self.assertEqual(p1["total_pages"], 3)
        self.assertTrue(p1["has_more"])

        # 2. Page 3 of size 5 -> returns items 11-15, has_more=False
        p3 = api_server.get_admin_live_processes(page=3, page_size=5, admin=self.admin)
        self.assertEqual(len(p3["processes"]), 5)
        self.assertFalse(p3["has_more"])

        # 3. Page 4 (out of bounds) -> returns empty list, has_more=False
        p4 = api_server.get_admin_live_processes(page=4, page_size=5, admin=self.admin)
        self.assertEqual(len(p4["processes"]), 0)
        self.assertFalse(p4["has_more"])

        # 4. Filter by status: "running" -> total_count must be 10
        f_run = api_server.get_admin_live_processes(page=1, page_size=20, status="running", admin=self.admin)
        self.assertEqual(f_run["total_count"], 10)
        for proc in f_run["processes"]:
            self.assertEqual(proc["live_category"], "running")

        # 5. Filter by status: "waiting_next_cycle" -> total_count must be 5
        f_wait = api_server.get_admin_live_processes(page=1, page_size=20, status="waiting_next_cycle", admin=self.admin)
        self.assertEqual(f_wait["total_count"], 5)
        for proc in f_wait["processes"]:
            self.assertEqual(proc["live_category"], "waiting_next_cycle")

        # 6. Search by substring "lord_07" -> exactly 1 match
        s_res = api_server.get_admin_live_processes(page=1, page_size=10, search="lord_07", admin=self.admin)
        self.assertEqual(s_res["total_count"], 1)
        self.assertEqual(s_res["processes"][0]["castle_id"], "c_batch_07")

        # 7. Search by non-existent query -> 0 matches, clean response
        s_empty = api_server.get_admin_live_processes(page=1, page_size=10, search="non_existent_xyz", admin=self.admin)
        self.assertEqual(s_empty["total_count"], 0)
        self.assertEqual(len(s_empty["processes"]), 0)
        self.assertFalse(s_empty["has_more"])


if __name__ == "__main__":
    unittest.main()
