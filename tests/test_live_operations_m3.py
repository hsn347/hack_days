# -*- coding: utf-8 -*-
"""
tests/test_live_operations_m3.py — Verification of Milestone 3 Live Operations Lifecycle & Pagination
════════════════════════════════════════════════════════════════════════════════════════════════════
Verifies:
1. Strict resolution to the 6 allowed states in BotManager & api_server.
2. Isolation of stalled threads and exclusion from total_active.
3. Deduplication and atomic check-and-reserve for (castle_id, email).
4. Full backend pagination, search, and status filtering in GET /api/admin/live-processes.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import api_server
from bot_manager import BotManager


class TestMilestone3LiveOperations(unittest.TestCase):
    """Test suite for Milestone 3 (F5, F6, F7 / Requirement R2)."""

    def setUp(self):
        # Clean api_server runtime state between tests
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

    def test_six_allowed_states_classification(self):
        """Verify that BotManager.get_live_info() maps strictly to the 6 allowed states."""
        # Create a mock session
        mock_session = MagicMock()
        mock_session.email = "lord_test@example.com"

        mgr = BotManager.__new__(BotManager)
        mgr.email = "lord_test@example.com"
        mgr.castle_id = "castle_test_1"
        mgr.user_id = "user_test_1"
        mgr.conn = None
        mgr._stop_event = MagicMock()
        mgr._stop_event.is_set.return_value = False
        mgr._last_kick_reason = ""
        mgr.status_message = "Ready"
        mgr.iteration = 1
        mgr.loop_interval_minutes = 60
        mgr.next_run_time = None
        mgr.reconnect_attempt = 0
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time()
        mgr.last_heartbeat = time.time()
        mgr.current_task = None
        mgr.current_task_name = None

        # 1. State: Starting (initial period < 30s)
        mgr.conn_state = "starting"
        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "starting")
        self.assertEqual(info["category_label"], "جاري بدء التشغيل")

        # 2. State: Running
        mgr.conn_state = "connected"
        mgr.conn = MagicMock()
        mgr.conn.is_connected = True
        mgr.current_task = "city_harvest"
        mgr.current_task_name = "🌾 حصد مزارع المدينة"
        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "running")
        self.assertEqual(info["current_step"], "🌾 حصد مزارع المدينة")

        # 3. State: Waiting for Next Cycle
        mgr.conn_state = "waiting"
        mgr.next_run_time = "2026-11-03T05:00:00Z"
        mgr.conn.is_connected = False
        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "waiting_next_cycle")
        self.assertEqual(info["category_label"], "بانتظار الدورة التالية")

        # 4. State: Other Device Login
        mgr.conn_state = "disconnected"
        mgr.status_message = "تم تسجيل الدخول من جهاز آخر"
        mgr._last_kick_reason = "other device login"
        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "other_device_login")
        self.assertEqual(info["category_label"], "دخول من جهاز آخر")

        # 5. State: Reconnecting
        mgr.conn_state = "reconnecting"
        mgr.reconnect_attempt = 2
        mgr.status_message = "محاولة إعادة الاتصال..."
        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "reconnecting")
        self.assertEqual(info["category_label"], "جاري إعادة الاتصال")

        # 6. State: Waiting for Re-login
        mgr.conn_state = "waiting_relogin"
        mgr.reconnect_attempt = 0
        mgr.status_message = "بانتظار إعادة تسجيل الدخول..."
        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "waiting_relogin")
        self.assertEqual(info["category_label"], "بانتظار إعادة تسجيل الدخول")

    def test_stalled_thread_detection(self):
        """Verify that stalled or unresponsive threads are isolated into stalled category."""
        mgr = BotManager.__new__(BotManager)
        mgr.email = "stalled@example.com"
        mgr.castle_id = "c_stalled"
        mgr.user_id = "u_stalled"
        mgr.conn = None
        mgr._stop_event = MagicMock()
        mgr._stop_event.is_set.return_value = False
        mgr._last_kick_reason = ""
        mgr.status_message = "No heartbeat"
        mgr.iteration = 1
        mgr.loop_interval_minutes = 60
        mgr.next_run_time = None
        mgr.reconnect_attempt = 0
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time() - 400
        # Heartbeat > 300s ago
        mgr.last_heartbeat = time.time() - 350
        mgr.conn_state = "running"
        mgr.current_task = None
        mgr.current_task_name = None

        info = mgr.get_live_info()
        self.assertTrue(info["is_stalled"])

    def test_deduplication_atomic_check(self):
        """Verify that _start_bot_internal blocks duplicate operations on the same castle or email."""
        req1 = api_server.StartBotRequest(
            castle_id="castle_dup_1",
            user_id="user_1",
            email="shared_dup@example.com",
            config={},
            loop_interval=20
        )
        req2 = api_server.StartBotRequest(
            castle_id="castle_dup_2",  # Different ID, same email
            user_id="user_1",
            email="shared_dup@example.com",
            config={},
            loop_interval=20
        )

        with patch("threading.Thread") as mock_th:
            mock_thread_instance = MagicMock()
            mock_thread_instance.is_alive.return_value = True
            mock_th.return_value = mock_thread_instance

            # Start first request
            ok1 = api_server._start_bot_internal(req1)
            self.assertTrue(ok1)

            # Start second request with same email -> must be blocked
            ok2 = api_server._start_bot_internal(req2)
            self.assertFalse(ok2, "Duplicate operation with the same email must be blocked")

    def test_get_admin_live_processes_pagination_and_summary(self):
        """Verify that GET /api/admin/live-processes handles pagination, summary stats, and search."""
        # Setup 4 mock active bots
        admin_user = {"email": "ibraboths@gmail.com", "is_super_admin": True, "role": "admin"}

        states = [
            ("c1", "bot1@test.com", "running"),
            ("c2", "bot2@test.com", "waiting_next_cycle"),
            ("c3", "bot3@test.com", "other_device_login"),
            ("c4", "bot4@test.com", "reconnecting"),
        ]

        with api_server._lock:
            for cid, email, st in states:
                mock_t = MagicMock()
                mock_t.is_alive.return_value = True
                mock_t.ident = hash(cid)
                mock_t.name = f"bot-{cid}"
                api_server._threads[cid] = mock_t
                api_server._castle_emails[cid] = email
                api_server._castle_users[cid] = f"user_{cid}"

                mock_mgr = MagicMock()
                mock_mgr.get_live_info.return_value = {
                    "castle_id": cid,
                    "email": email,
                    "user_id": f"user_{cid}",
                    "state": st,
                    "live_category": st,
                    "category_label": st,
                    "status_message": f"Status for {cid}",
                    "current_step": "Task 1" if st == "running" else None,
                    "iteration": 1,
                    "uptime_seconds": 120,
                    "is_connection_alive": st == "running",
                    "is_stopped": False,
                    "is_stalled": False,
                    "start_time": time.time(),
                }
                api_server._bot_managers[cid] = mock_mgr

        # 1. Query page 1, page_size 2
        res_p1 = api_server.get_admin_live_processes(page=1, page_size=2, admin=admin_user)
        self.assertEqual(res_p1["status"], "success")
        self.assertEqual(res_p1["total_active"], 4)
        self.assertEqual(res_p1["total_count"], 4)
        self.assertEqual(res_p1["page"], 1)
        self.assertEqual(res_p1["page_size"], 2)
        self.assertEqual(res_p1["total_pages"], 2)
        self.assertTrue(res_p1["has_more"])
        self.assertEqual(len(res_p1["processes"]), 2)

        # Verify summary counts
        self.assertEqual(res_p1["summary"]["total_active"], 4)
        self.assertEqual(res_p1["summary"]["running"], 1)
        self.assertEqual(res_p1["summary"]["waiting_next_cycle"], 1)
        self.assertEqual(res_p1["summary"]["other_device_login"], 1)
        self.assertEqual(res_p1["summary"]["reconnecting"], 1)
        self.assertEqual(res_p1["summary"]["stalled"], 0)

        # 2. Query page 2, page_size 2
        res_p2 = api_server.get_admin_live_processes(page=2, page_size=2, admin=admin_user)
        self.assertEqual(res_p2["page"], 2)
        self.assertFalse(res_p2["has_more"])
        self.assertEqual(len(res_p2["processes"]), 2)

        # 3. Search query
        res_search = api_server.get_admin_live_processes(page=1, page_size=10, search="bot3", admin=admin_user)
        self.assertEqual(res_search["total_count"], 1)
        self.assertEqual(res_search["processes"][0]["castle_id"], "c3")

        # 4. Status filter
        res_status = api_server.get_admin_live_processes(page=1, page_size=10, status="running", admin=admin_user)
        self.assertEqual(res_status["total_count"], 1)
        self.assertEqual(res_status["processes"][0]["live_category"], "running")


if __name__ == "__main__":
    unittest.main()
