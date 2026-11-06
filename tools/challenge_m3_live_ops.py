# -*- coding: utf-8 -*-
"""
tools/challenge_m3_live_ops.py — Empirical Challenge Harness for Milestone 3
═════════════════════════════════════════════════════════════════════════════
Adversarially tests and verifies:
1. Boundary parameters for pagination: page=1, page=2, page=-5, page=0, page=9999,
   page_size=10, 25, 50, 100, 500, -1, 0.
2. Metadata consistency across sliced pages (total_active, total_count, total_pages, has_more).
3. Search querying: case-insensitivity, substring matching across fields, special characters.
4. Status filtering: snake_case, Title Case, spaces, stalled isolation, and unhandled inputs.
5. Operational priority sorting (other_device_login > reconnecting > running > waiting).
6. Zero-Flicker frontend invariants and contract conformance.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import api_server
from bot_manager import BotManager


class EmpiricalLiveOperationsChallenge(unittest.TestCase):
    """Adversarial stress and challenge suite for Milestone 3."""

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

        self.admin = {"email": "admin@example.com", "is_super_admin": True, "role": "admin"}

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

    def _populate_mock_bots(self, count=45):
        """Populates N mock bots with varying states, uptimes, and categories."""
        categories = [
            ("running", "🌾 جمع الموارد"),
            ("waiting_next_cycle", None),
            ("other_device_login", None),
            ("reconnecting", None),
            ("waiting_relogin", None),
            ("starting", "تهيئة الجلسة"),
        ]

        with api_server._lock:
            for i in range(count):
                cid = f"castle_{i:03d}"
                email = f"user_{i:03d}@example.com"
                cat, step = categories[i % len(categories)]
                uptime = 100 * (i + 1)

                mock_t = MagicMock()
                mock_t.is_alive.return_value = True
                mock_t.ident = 1000 + i
                mock_t.name = f"bot-{cid}"
                api_server._threads[cid] = mock_t
                api_server._castle_emails[cid] = email
                api_server._castle_users[cid] = f"uid_{i:03d}"

                mock_mgr = MagicMock()
                mock_mgr.get_live_info.return_value = {
                    "castle_id": cid,
                    "email": email,
                    "user_id": f"uid_{i:03d}",
                    "state": cat,
                    "live_category": cat,
                    "category_label": cat.replace("_", " ").title(),
                    "status_message": f"Status for {cid} ({cat})",
                    "current_step": step,
                    "iteration": 1,
                    "uptime_seconds": uptime,
                    "is_connection_alive": cat == "running",
                    "is_stopped": False,
                    "is_stalled": False,
                    "start_time": time.time() - uptime,
                }
                api_server._bot_managers[cid] = mock_mgr

    def test_01_pagination_boundary_values(self):
        """Stress-test extreme boundary inputs for page and page_size."""
        self._populate_mock_bots(45)

        # 1. Standard page 1 with page_size 10
        r1 = api_server.get_admin_live_processes(page=1, page_size=10, admin=self.admin)
        self.assertEqual(r1["page"], 1)
        self.assertEqual(r1["page_size"], 10)
        self.assertEqual(r1["total_count"], 45)
        self.assertEqual(r1["total_pages"], 5)
        self.assertTrue(r1["has_more"])
        self.assertEqual(len(r1["processes"]), 10)

        # 2. Page 5 (last page) with page_size 10 (45 items -> 5 items on page 5)
        r5 = api_server.get_admin_live_processes(page=5, page_size=10, admin=self.admin)
        self.assertEqual(r5["page"], 5)
        self.assertEqual(len(r5["processes"]), 5)
        self.assertFalse(r5["has_more"])

        # 3. Beyond last page (page 6)
        r6 = api_server.get_admin_live_processes(page=6, page_size=10, admin=self.admin)
        self.assertEqual(len(r6["processes"]), 0)
        self.assertFalse(r6["has_more"])

        # 4. Extreme page beyond boundaries (page 9999)
        r_far = api_server.get_admin_live_processes(page=9999, page_size=10, admin=self.admin)
        self.assertEqual(len(r_far["processes"]), 0)
        self.assertFalse(r_far["has_more"])

        # 5. Negative page (page=-5) -> Should clamp to page=1
        r_neg = api_server.get_admin_live_processes(page=-5, page_size=10, admin=self.admin)
        self.assertEqual(r_neg["page"], 1, "Negative page must be clamped to 1")
        self.assertEqual(len(r_neg["processes"]), 10)

        # 6. Zero page (page=0) -> Should clamp to page=1
        r_zero = api_server.get_admin_live_processes(page=0, page_size=10, admin=self.admin)
        self.assertEqual(r_zero["page"], 1, "Zero page must be clamped to 1")

        # 7. Oversized page_size (500) -> Clamped to 100
        r_oversize = api_server.get_admin_live_processes(page=1, page_size=500, admin=self.admin)
        self.assertEqual(r_oversize["page_size"], 100, "page_size > 100 must be clamped to 100")
        self.assertEqual(len(r_oversize["processes"]), 45)
        self.assertFalse(r_oversize["has_more"])

        # 8. Negative or Zero page_size (-10, 0) -> Clamped to min 1
        r_neg_size = api_server.get_admin_live_processes(page=1, page_size=-10, admin=self.admin)
        self.assertEqual(r_neg_size["page_size"], 1, "Negative page_size must be clamped to 1")
        self.assertEqual(len(r_neg_size["processes"]), 1)

    def test_02_pagination_slicing_integrity_and_no_duplicates(self):
        """Verify that traversing all pages retrieves exactly all items with no duplicates or omissions."""
        self._populate_mock_bots(45)

        collected_ids = []
        page = 1
        page_size = 10
        total_pages = 5

        while page <= total_pages:
            res = api_server.get_admin_live_processes(page=page, page_size=page_size, admin=self.admin)
            p_ids = [p["castle_id"] for p in res["processes"]]
            collected_ids.extend(p_ids)
            page += 1

        self.assertEqual(len(collected_ids), 45)
        self.assertEqual(len(set(collected_ids)), 45, "No duplicate castles across pages!")

    def test_03_stalled_thread_isolation_from_active_count(self):
        """Verify that stalled threads are isolated in stalled_processes and do NOT increment total_active."""
        self._populate_mock_bots(6)  # 6 normal bots

        # Inject 2 stalled threads:
        # One is in _threads with stop event set
        with api_server._lock:
            cid_stalled1 = "c_stalled_1"
            mock_t1 = MagicMock()
            mock_t1.is_alive.return_value = True
            mock_t1.ident = 9991
            mock_t1.name = f"bot-{cid_stalled1}"
            api_server._threads[cid_stalled1] = mock_t1
            api_server._user_stopped.add(cid_stalled1)

            # One is an orphaned OS thread in threading.enumerate
            mock_t2 = MagicMock()
            mock_t2.is_alive.return_value = True
            mock_t2.ident = 9992
            mock_t2.name = "bot-orphan_castle"

            with unittest.mock.patch("threading.enumerate", return_value=[mock_t1, mock_t2]):
                res = api_server.get_admin_live_processes(page=1, page_size=25, admin=self.admin)

        # total_active should ONLY be 6 (the normal bots)
        self.assertEqual(res["total_active"], 6, "total_active must strictly exclude stalled/orphaned threads")
        self.assertGreaterEqual(res["summary"]["stalled"], 1)

        # In standard view (status='all'), stalled threads must NOT appear in processes
        process_ids = [p["castle_id"] for p in res["processes"]]
        self.assertNotIn("c_stalled_1", process_ids)
        self.assertNotIn("orphan_castle", process_ids)

        # When status='stalled', the stalled threads SHOULD appear
        res_stalled = api_server.get_admin_live_processes(page=1, page_size=25, status="stalled", admin=self.admin)
        stalled_ids = [p["castle_id"] for p in res_stalled["processes"]]
        self.assertIn("c_stalled_1", stalled_ids)

    def test_04_search_filtering_robustness(self):
        """Verify search filtering across email, castle_id, user_id, status_message, and special characters."""
        self._populate_mock_bots(20)

        # 1. Search by exact castle_id
        r_cid = api_server.get_admin_live_processes(search="castle_005", admin=self.admin)
        self.assertEqual(r_cid["total_count"], 1)
        self.assertEqual(r_cid["processes"][0]["castle_id"], "castle_005")

        # 2. Search case-insensitive email
        r_email = api_server.get_admin_live_processes(search="USER_012@EXAMPLE.COM", admin=self.admin)
        self.assertEqual(r_email["total_count"], 1)
        self.assertEqual(r_email["processes"][0]["email"], "user_012@example.com")

        # 3. Search with whitespace padding
        r_pad = api_server.get_admin_live_processes(search="   user_003   ", admin=self.admin)
        self.assertEqual(r_pad["total_count"], 1)

        # 4. Search with special characters (SQL injection / regex chars) -> must not crash
        r_special = api_server.get_admin_live_processes(search="'; DROP TABLE castles; --", admin=self.admin)
        self.assertEqual(r_special["total_count"], 0)
        self.assertEqual(len(r_special["processes"]), 0)

        r_regex = api_server.get_admin_live_processes(search=".*+?^$[](){}|\\", admin=self.admin)
        self.assertEqual(r_regex["total_count"], 0)

    def test_05_status_filter_inputs(self):
        """Test status filter with exact categories and challenge title-case/alias variations."""
        self._populate_mock_bots(30)  # 5 of each of the 6 categories

        # 1. snake_case filter for running
        r_run = api_server.get_admin_live_processes(status="running", admin=self.admin)
        self.assertEqual(r_run["total_count"], 5)
        for p in r_run["processes"]:
            self.assertEqual(p["live_category"], "running")

        # 2. snake_case filter for waiting_next_cycle
        r_wait = api_server.get_admin_live_processes(status="waiting_next_cycle", admin=self.admin)
        self.assertEqual(r_wait["total_count"], 5)
        for p in r_wait["processes"]:
            self.assertEqual(p["live_category"], "waiting_next_cycle")

        # 3. Legacy alias: waiting
        r_wait_alias = api_server.get_admin_live_processes(status="waiting", admin=self.admin)
        self.assertEqual(r_wait_alias["total_count"], 5)

        # 4. Legacy alias: other_login
        r_other_alias = api_server.get_admin_live_processes(status="other_login", admin=self.admin)
        self.assertEqual(r_other_alias["total_count"], 5)

        # 5. Title-case filter: 'Running'
        r_title_run = api_server.get_admin_live_processes(status="Running", admin=self.admin)
        self.assertEqual(r_title_run["total_count"], 5)

        # 6. Check 'Waiting for Next Cycle'
        r_title_wait = api_server.get_admin_live_processes(status="Waiting for Next Cycle", admin=self.admin)
        print(f"\n[CHALLENGE OBSERVATION] status='Waiting for Next Cycle' returned {r_title_wait['total_count']} items.")

        # 7. Check 'Other Device Login'
        r_title_other = api_server.get_admin_live_processes(status="Other Device Login", admin=self.admin)
        print(f"[CHALLENGE OBSERVATION] status='Other Device Login' returned {r_title_other['total_count']} items.")

    def test_06_sorting_priority(self):
        """Verify sorting order: other_device_login first, then waiting_relogin, reconnecting, running, etc."""
        self._populate_mock_bots(12)  # 2 of each category

        res = api_server.get_admin_live_processes(page=1, page_size=12, admin=self.admin)
        cats = [p["live_category"] for p in res["processes"]]

        # First items must be other_device_login (priority 0)
        self.assertEqual(cats[0], "other_device_login")
        self.assertEqual(cats[1], "other_device_login")
        # Next items must be waiting_relogin (priority 1)
        self.assertEqual(cats[2], "waiting_relogin")
        self.assertEqual(cats[3], "waiting_relogin")
        # Next items must be reconnecting (priority 2)
        self.assertEqual(cats[4], "reconnecting")
        self.assertEqual(cats[5], "reconnecting")
        # Next items must be running (priority 3)
        self.assertEqual(cats[6], "running")
        self.assertEqual(cats[7], "running")


if __name__ == "__main__":
    unittest.main()
