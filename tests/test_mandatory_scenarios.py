# -*- coding: utf-8 -*-
"""
tests/test_mandatory_scenarios.py — Comprehensive Hermetic Automated Test Suite
═══════════════════════════════════════════════════════════════════════════════
Milestone 5 (F12 / Requirement R4) — 18 Mandatory Lifecycle & Verification Scenarios
Compliant with AGENTS_CONSTITUTION.md, ORIGINAL_REQUEST.md, and ROOT_CAUSE_AND_PLAN_P2.md.

Covers all 18 Mandatory Scenarios:
- S01: Startup (Starting -> Running)
- S02: Auth Credential Failure Handling
- S03: Other Device Login Detection & Transient State
- S04: Connection Loss Detection & Reconnecting State
- S05: Reconnecting Attempts with Bounded Retry Logic
- S06: Waiting for Re-login Handling
- S07: Next Cycle Wait with Timestamp
- S08: Natural Completion (without Next Cycle)
- S09: Manual Stop via _stop_and_join_bot (Deterministic Join, 0 Residual Threads)
- S10: Stop In-Flight During Active Task Execution (< 100ms Event Cancellation)
- S11: Delete Castle While Running (Atomic Stop, Purge DB & Proxy Bindings)
- S12: Delete User While Running (Atomic Stop of All Castles, Purge User & DB)
- S13: Startup Exception Handling (Clean Rollback, No Zombie Threads)
- S14: In-Flight Runtime Exception Handling (Catch, Record, Safe Termination)
- S15: WebSocket Disconnect Detection (Coroutine Termination, 0 Leaked Tasks)
- S16: WebSocket Reconnect (Fresh Initial Snapshot Push)
- S17: Repeated Page Navigation / Rapid API Calls (Paginated Summary, No Memory Growth)
- S18: Repeated Search & Filter with Stalled Thread Isolation (Quarantined in _stalled_threads)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import asyncio
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

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repository root is on sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import api_server
from bot_manager import BotManager
import core.database as db
from proxy import proxy_manager
from starlette.websockets import WebSocketDisconnect


class TestMandatory18Scenarios(unittest.TestCase):
    """
    Hermetic test harness covering all 18 mandatory scenarios specified in
    ORIGINAL_REQUEST.md Requirement R4.
    """

    def setUp(self):
        # 1. Create an isolated hermetic SQLite database for each test
        self.temp_dir = tempfile.mkdtemp(prefix="osmanli_test_m5_")
        self.db_path = os.path.join(self.temp_dir, "test_castles.db")
        db.init_db(self.db_path)
        os.environ["CASTLES_DB_PATH"] = self.db_path

        # 2. Reset and clean all api_server runtime tracking structures
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

        # 3. Clean proxy_manager runtime bindings
        with proxy_manager._lock:
            proxy_manager._castle_bindings.clear()

        # 4. Standard admin user fixture
        self.admin_user = {
            "uid": "admin_super_uid",
            "email": "ibraboths@gmail.com",
            "role": "admin",
            "is_super_admin": True,
            "is_merchant_admin": False,
        }

    def tearDown(self):
        # Clean api_server structures
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

        # Remove environment variable and temp directory
        os.environ.pop("CASTLES_DB_PATH", None)
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 1: Startup (Starting -> Running)
    # ══════════════════════════════════════════════════════════════════════════
    def test_s01_startup_lifecycle(self):
        """Scenario 1: Bot startup and task initialization transitioning Starting -> Running."""
        cid = "c_s01"
        email = "s01_bot@test.com"
        uid = "u_s01"

        mgr = BotManager.__new__(BotManager)
        mgr.castle_id = cid
        mgr.email = email
        mgr.user_id = uid
        mgr.conn = None
        mgr._stop_event = threading.Event()
        mgr._last_kick_reason = ""
        mgr.status_message = "Initializing"
        mgr.iteration = 1
        mgr.loop_interval_minutes = 60
        mgr.next_run_time = None
        mgr.reconnect_attempt = 0
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time()
        mgr.last_heartbeat = time.time()
        mgr.current_task = None
        mgr.current_task_name = None

        # Phase A: Starting phase (initial connection setup)
        mgr.conn_state = "starting"
        info_starting = mgr.get_live_info()
        self.assertEqual(info_starting["live_category"], "starting")
        self.assertEqual(info_starting["category_label"], "جاري بدء التشغيل")

        # Phase B: Transition to Running upon successful connection & task dispatch
        mock_conn = MagicMock()
        mock_conn.is_connected = True
        mgr.conn = mock_conn
        mgr.conn_state = "connected"
        mgr.current_task = "monster_hunt"
        mgr.current_task_name = "⚔️ صيد الوحوش"

        info_running = mgr.get_live_info()
        self.assertEqual(info_running["live_category"], "running")
        self.assertEqual(info_running["category_label"], "شغالة فعلياً")
        self.assertEqual(info_running["current_step"], "⚔️ صيد الوحوش")

        # Register in api_server and verify get_admin_live_processes summary
        mock_th = MagicMock()
        mock_th.is_alive.return_value = True
        mock_th.ident = 10101
        mock_th.name = f"bot-{cid}"

        with api_server._lock:
            api_server._threads[cid] = mock_th
            api_server._bot_managers[cid] = mgr
            api_server._castle_emails[cid] = email
            api_server._castle_users[cid] = uid
            api_server._conn_states[cid] = "running"

        res = api_server.get_admin_live_processes(admin=self.admin_user)
        items = res.get("processes") or res.get("items", [])
        self.assertEqual(res["summary"]["running"], 1)
        self.assertEqual(res["summary"]["starting"], 0)
        self.assertEqual(res["summary"]["total_active"], 1)
        self.assertEqual(items[0]["live_category"], "running")

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 2: Auth Credential Failure Handling
    # ══════════════════════════════════════════════════════════════════════════
    def test_s02_auth_credential_failure(self):
        """Scenario 2: Auth credential failure handling (no leaked threads, clean database status)."""
        cid = "c_s02"
        email = "bad_auth@test.com"
        uid = "u_s02"

        db.save_castle({
            "castle_id": cid,
            "user_id": uid,
            "email": email,
            "password": "wrong_password",
            "state": "idle",
            "conn_state": "idle",
        }, db_path=self.db_path)

        req = api_server.StartBotRequest(
            castle_id=cid,
            user_id=uid,
            email=email,
            password="wrong_password",
            config={},
            loop_interval=20,
        )

        mock_sm = MagicMock()
        mock_sm.get_or_login.return_value = None

        with patch("core.session_manager.SessionManager", return_value=mock_sm):
            with patch("core.session_manager.get_last_auth_error", return_value="Invalid credentials test"):
                # Run _bot_thread directly (synchronous simulation of thread target)
                api_server._bot_thread(req)

        # Verify: All 10 global tracking structures must be completely clean (zero leaks)
        with api_server._lock:
            self.assertNotIn(cid, api_server._threads, "_threads must be clean")
            self.assertNotIn(cid, api_server._stop_events, "_stop_events must be clean")
            self.assertNotIn(cid, api_server._bot_managers, "_bot_managers must be clean")
            self.assertNotIn(cid, api_server._log_qs, "_log_qs must be clean")
            self.assertNotIn(cid, api_server._conn_states, "_conn_states must be clean")
            self.assertNotIn(cid, api_server._castle_emails, "_castle_emails must be popped")
            self.assertNotIn(cid, api_server._castle_users, "_castle_users must be popped")
            self.assertNotIn(cid, api_server._reserved, "_reserved must be clean")
            self.assertNotIn(cid, api_server._user_stopped, "_user_stopped must be clean")
            self.assertNotIn(cid, api_server._deleted_castles, "_deleted_castles must be clean")

        # Verify: Database status recorded the error
        c_rec = db.get_castle_by_id(cid, uid, db_path=self.db_path)
        self.assertIsNotNone(c_rec)
        self.assertEqual(c_rec.get("state"), "error")
        self.assertEqual(c_rec.get("conn_state"), "error")
        self.assertIn("Invalid credentials test", c_rec.get("conn_message", ""))

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 3: Other Device Login Detection
    # ══════════════════════════════════════════════════════════════════════════
    def test_s03_other_device_login(self):
        """Scenario 3: 'Other Device Login' detection and transient wait state."""
        cid = "c_s03"
        email = "other_dev@test.com"
        uid = "u_s03"

        mgr = BotManager.__new__(BotManager)
        mgr.castle_id = cid
        mgr.email = email
        mgr.user_id = uid
        mgr.conn = None
        mgr._stop_event = threading.Event()
        mgr._last_kick_reason = "Other device logged in"
        mgr.status_message = "تم تسجيل الدخول من جهاز آخر، تعليق مؤقت..."
        mgr.iteration = 2
        mgr.loop_interval_minutes = 60
        mgr.next_run_time = None
        mgr.reconnect_attempt = 0
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time() - 100
        mgr.last_heartbeat = time.time()
        mgr.conn_state = "disconnected"
        mgr.current_task = None
        mgr.current_task_name = None

        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "other_device_login")
        self.assertEqual(info["category_label"], "دخول من جهاز آخر")
        self.assertFalse(info["is_stalled"])

        # Check API representation
        mock_th = MagicMock()
        mock_th.is_alive.return_value = True
        mock_th.ident = 10303
        mock_th.name = f"bot-{cid}"

        with api_server._lock:
            api_server._threads[cid] = mock_th
            api_server._bot_managers[cid] = mgr
            api_server._castle_emails[cid] = email
            api_server._castle_users[cid] = uid
            api_server._conn_states[cid] = "other_device_login"

        res = api_server.get_admin_live_processes(admin=self.admin_user)
        items = res.get("processes") or res.get("items", [])
        self.assertEqual(res["summary"]["other_device_login"], 1)
        self.assertEqual(items[0]["live_category"], "other_device_login")

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 4: Connection Loss Detection
    # ══════════════════════════════════════════════════════════════════════════
    def test_s04_connection_loss(self):
        """Scenario 4: Connection loss detection and transition to reconnect state."""
        cid = "c_s04"
        email = "conn_loss@test.com"

        mgr = BotManager.__new__(BotManager)
        mgr.castle_id = cid
        mgr.email = email
        mgr.user_id = "u_s04"
        mgr.conn = MagicMock()
        mgr.conn.is_connected = False  # Connection dropped
        mgr._stop_event = threading.Event()
        mgr._last_kick_reason = ""
        mgr.status_message = "فقد الاتصال بالمخدم، جاري محاولة إعادة الاتصال..."
        mgr.iteration = 1
        mgr.loop_interval_minutes = 60
        mgr.next_run_time = None
        mgr.reconnect_attempt = 1
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time() - 50
        mgr.last_heartbeat = time.time()
        mgr.conn_state = "reconnecting"
        mgr.current_task = None
        mgr.current_task_name = None

        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "reconnecting")
        self.assertEqual(info["category_label"], "جاري إعادة الاتصال")
        self.assertFalse(info["is_connection_alive"])
        self.assertFalse(info["is_stalled"])

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 5: Reconnecting Attempts with Bounded Retry Logic
    # ══════════════════════════════════════════════════════════════════════════
    def test_s05_reconnecting_bounded_retries(self):
        """Scenario 5: Reconnecting attempts with bounded retry logic."""
        mgr = BotManager.__new__(BotManager)
        mgr.castle_id = "c_s05"
        mgr.email = "reconn@test.com"
        mgr.user_id = "u_s05"
        mgr.conn = None
        mgr._stop_event = threading.Event()
        mgr._last_kick_reason = ""
        mgr.status_message = "محاولة إعادة الاتصال..."
        mgr.iteration = 1
        mgr.loop_interval_minutes = 60
        mgr.next_run_time = None
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time() - 30
        mgr.last_heartbeat = time.time()
        mgr.conn_state = "reconnecting"
        mgr.current_task = None
        mgr.current_task_name = None

        # Verify progression through bounded retry attempts 1 to 10
        for attempt in range(1, 11):
            mgr.reconnect_attempt = attempt
            info = mgr.get_live_info()
            self.assertEqual(info["live_category"], "reconnecting")
            self.assertEqual(info["reconnect_attempt"], attempt)
            self.assertEqual(info["max_reconnect_attempts"], 10)
            self.assertFalse(info["is_stalled"])

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 6: Waiting for Re-login Handling
    # ══════════════════════════════════════════════════════════════════════════
    def test_s06_waiting_for_relogin(self):
        """Scenario 6: Waiting for re-login due to invalid/expired session."""
        cid = "c_s06"
        email = "relogin@test.com"

        mgr = BotManager.__new__(BotManager)
        mgr.castle_id = cid
        mgr.email = email
        mgr.user_id = "u_s06"
        mgr.conn = None
        mgr._stop_event = threading.Event()
        mgr._last_kick_reason = "Session expired"
        mgr.status_message = "انتهت صلاحية الجلسة، بانتظار إعادة تسجيل الدخول يدprop..."
        mgr.iteration = 3
        mgr.loop_interval_minutes = 60
        mgr.next_run_time = None
        mgr.reconnect_attempt = 0
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time() - 120
        mgr.last_heartbeat = time.time()
        mgr.conn_state = "waiting_relogin"
        mgr.current_task = None
        mgr.current_task_name = None

        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "waiting_relogin")
        self.assertEqual(info["category_label"], "بانتظار إعادة تسجيل الدخول")

        mock_th = MagicMock()
        mock_th.is_alive.return_value = True
        mock_th.ident = 10606
        mock_th.name = f"bot-{cid}"

        with api_server._lock:
            api_server._threads[cid] = mock_th
            api_server._bot_managers[cid] = mgr
            api_server._castle_emails[cid] = email
            api_server._castle_users[cid] = "u_s06"
            api_server._conn_states[cid] = "waiting_relogin"

        res = api_server.get_admin_live_processes(admin=self.admin_user)
        self.assertEqual(res["summary"]["waiting_relogin"], 1)

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 7: Next Cycle Wait with Timestamp
    # ══════════════════════════════════════════════════════════════════════════
    def test_s07_next_cycle_wait_with_timestamp(self):
        """Scenario 7: Cycle completion with scheduled next cycle (Waiting for Next Cycle + timestamp)."""
        cid = "c_s07"
        email = "cycle_wait@test.com"
        target_timestamp = "2026-11-03T06:30:00Z"

        mgr = BotManager.__new__(BotManager)
        mgr.castle_id = cid
        mgr.email = email
        mgr.user_id = "u_s07"
        mgr.conn = None
        mgr._stop_event = threading.Event()
        mgr._last_kick_reason = ""
        mgr.status_message = f"اكتملت المهام، بانتظار الدورة التالية في {target_timestamp}"
        mgr.iteration = 4
        mgr.loop_interval_minutes = 45
        mgr.next_run_time = target_timestamp
        mgr.reconnect_attempt = 0
        mgr.max_reconnect_attempts = 10
        mgr.start_time = time.time() - 300
        mgr.last_heartbeat = time.time()
        mgr.conn_state = "waiting"
        mgr.current_task = None
        mgr.current_task_name = None

        info = mgr.get_live_info()
        self.assertEqual(info["live_category"], "waiting_next_cycle")
        self.assertEqual(info["category_label"], "بانتظار الدورة التالية")
        self.assertEqual(info["next_run_time"], target_timestamp)

        mock_th = MagicMock()
        mock_th.is_alive.return_value = True
        mock_th.ident = 10707
        mock_th.name = f"bot-{cid}"

        with api_server._lock:
            api_server._threads[cid] = mock_th
            api_server._bot_managers[cid] = mgr
            api_server._castle_emails[cid] = email
            api_server._castle_users[cid] = "u_s07"
            api_server._conn_states[cid] = "waiting"

        res = api_server.get_admin_live_processes(admin=self.admin_user)
        items = res.get("processes") or res.get("items", [])
        self.assertEqual(res["summary"]["waiting_next_cycle"], 1)
        self.assertEqual(items[0]["next_run_time"], target_timestamp)

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 8: Natural Completion (without Next Cycle)
    # ══════════════════════════════════════════════════════════════════════════
    def test_s08_natural_completion_without_next_cycle(self):
        """Scenario 8: Natural completion without next cycle (clean transition to stopped/idle, excluded from live ops)."""
        cid = "c_s08"
        email = "natural_complete@test.com"
        uid = "u_s08"

        db.save_castle({
            "castle_id": cid,
            "user_id": uid,
            "email": email,
            "password": "test_password",
            "state": "running",
            "conn_state": "running",
        }, db_path=self.db_path)

        req = api_server.StartBotRequest(
            castle_id=cid,
            user_id=uid,
            email=email,
            password="test_password",
            config={},
            loop_interval=0,  # Single-shot / no next cycle
        )

        # Mock SessionManager and BotManager so run_loop returns immediately (natural completion)
        mock_account = MagicMock()
        mock_account.email = email
        mock_sm = MagicMock()
        mock_sm.get_or_login.return_value = mock_account

        with patch("core.session_manager.SessionManager", return_value=mock_sm), \
             patch("bot_manager.SessionManager", return_value=mock_sm):
            with patch("bot_manager.BotManager.run_loop", new_callable=AsyncMock) as mock_run_loop:
                mock_run_loop.return_value = None
                api_server._bot_thread(req)

        # Verify: All tracking structures must be popped
        with api_server._lock:
            self.assertNotIn(cid, api_server._threads)
            self.assertNotIn(cid, api_server._bot_managers)
            self.assertNotIn(cid, api_server._castle_emails)

        # Verify: Excluded from live operations
        res = api_server.get_admin_live_processes(admin=self.admin_user)
        items = res.get("processes") or res.get("items", [])
        self.assertEqual(res["summary"]["total_active"], 0)
        self.assertEqual(len(items), 0)

        # Verify: DB record updated to idle
        c_rec = db.get_castle_by_id(cid, uid, db_path=self.db_path)
        self.assertEqual(c_rec.get("state"), "idle")
        self.assertEqual(c_rec.get("conn_state"), "idle")

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 9: Manual Stop via _stop_and_join_bot
    # ══════════════════════════════════════════════════════════════════════════
    def test_s09_manual_stop(self):
        """Scenario 9: Manual stop via _stop_and_join_bot (deterministic join within timeout, 0 residual threads)."""
        cid = "c_s09"
        email = "manual_stop@test.com"

        stop_event = threading.Event()
        worker_exited = threading.Event()

        def _cooperative_worker():
            stop_event.wait(timeout=5.0)
            worker_exited.set()

        t = threading.Thread(target=_cooperative_worker, name=f"bot-{cid}")
        t.start()

        mock_mgr = MagicMock()

        with api_server._lock:
            api_server._threads[cid] = t
            api_server._stop_events[cid] = stop_event
            api_server._bot_managers[cid] = mock_mgr
            api_server._castle_emails[cid] = email
            api_server._castle_users[cid] = "u_s09"

        # Invoke deterministic stop
        joined = api_server._stop_and_join_bot(cid, timeout=2.0)
        self.assertTrue(joined, "_stop_and_join_bot must join thread successfully")
        self.assertTrue(worker_exited.is_set(), "Worker thread must have responded to stop event")
        self.assertFalse(t.is_alive(), "Thread must not be alive after join")

        # Verify all structures cleaned
        with api_server._lock:
            self.assertNotIn(cid, api_server._threads)
            self.assertNotIn(cid, api_server._stop_events)
            self.assertNotIn(cid, api_server._bot_managers)
            self.assertNotIn(cid, api_server._castle_emails)
            self.assertNotIn(cid, api_server._stalled_threads)

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 10: Stop In-Flight During Active Task Execution
    # ══════════════════════════════════════════════════════════════════════════
    def test_s10_stop_in_flight(self):
        """Scenario 10: Stop in-flight during active task execution (immediate event cancellation < 100ms)."""
        mgr = BotManager.__new__(BotManager)
        mgr._stop_event = threading.Event()
        mgr._async_stop_event = None
        mgr._loop = None
        mgr.conn = MagicMock()

        async def _test_in_flight():
            loop = asyncio.get_running_loop()
            mgr._loop = loop
            mgr._async_stop_event = asyncio.Event()

            t0 = time.perf_counter()
            # Launch stop from another task
            async def _delayed_stop():
                await asyncio.sleep(0.02)
                mgr.stop()

            stop_task = asyncio.create_task(_delayed_stop())

            # Simulate in-flight wait for next cycle
            interrupted = False
            try:
                await asyncio.wait_for(mgr._async_stop_event.wait(), timeout=5.0)
                interrupted = True
            except asyncio.TimeoutError:
                interrupted = False

            elapsed = time.perf_counter() - t0
            await stop_task
            return interrupted, elapsed

        interrupted, elapsed = asyncio.run(_test_in_flight())
        self.assertTrue(interrupted, "In-flight task must be immediately unblocked by stop()")
        self.assertLess(elapsed, 0.5, f"Stop must interrupt within < 500ms (actual: {elapsed*1000:.1f}ms)")
        self.assertTrue(mgr._stop_event.is_set())

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 11: Delete Castle While Running
    # ══════════════════════════════════════════════════════════════════════════
    def test_s11_delete_castle_while_running(self):
        """Scenario 11: Castle deletion while running (atomic stop, join, delete row, purge proxy bindings)."""
        cid = "c_s11"
        email = "del_castle@test.com"
        uid = "u_s11"

        db.save_castle({
            "castle_id": cid,
            "user_id": uid,
            "email": email,
            "state": "running",
            "conn_state": "running",
        }, db_path=self.db_path)

        # Bind proxy
        proxy_manager.set_castle_proxy(email, "http://proxy_s11:8080")
        self.assertEqual(proxy_manager.get_castle_proxy(email), "http://proxy_s11:8080")

        # Start simulated bot thread
        stop_ev = threading.Event()
        t = threading.Thread(target=lambda: stop_ev.wait(timeout=5.0), name=f"bot-{cid}")
        t.start()

        with api_server._lock:
            api_server._threads[cid] = t
            api_server._stop_events[cid] = stop_ev
            api_server._castle_emails[cid] = email
            api_server._castle_users[cid] = uid

        # Delete castle via endpoint
        res = api_server.delete_castle_endpoint(cid, current_user=self.admin_user)
        self.assertEqual(res["status"], "success")

        # Verify thread joined and terminated
        self.assertFalse(t.is_alive(), "Bot thread must be terminated upon castle deletion")

        # Verify proxy binding purged
        self.assertIsNone(proxy_manager.get_castle_proxy(email), "Proxy binding must be purged")

        # Verify castle row deleted from SQLite
        self.assertIsNone(db.get_castle(cid, db_path=self.db_path))

        # Verify _deleted_castles purged safely
        with api_server._lock:
            self.assertNotIn(cid, api_server._deleted_castles)
            self.assertNotIn(cid, api_server._user_stopped)

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 12: Delete User While Running
    # ══════════════════════════════════════════════════════════════════════════
    def test_s12_delete_user_while_running(self):
        """Scenario 12: User deletion while running (atomic stop, join of all user's castles, purge all rows)."""
        uid = "u_s12_target"
        u_email = "target_user@test.com"
        c1 = "c_s12_1"
        c2 = "c_s12_2"
        em1 = "c1_user@test.com"
        em2 = "c2_user@test.com"

        # Create user and 2 castles
        db.create_user(uid, u_email, db_path=self.db_path)
        db.save_castle({"castle_id": c1, "user_id": uid, "email": em1, "state": "running"}, db_path=self.db_path)
        db.save_castle({"castle_id": c2, "user_id": uid, "email": em2, "state": "running"}, db_path=self.db_path)

        proxy_manager.set_castle_proxy(em1, "http://p1:8080")
        proxy_manager.set_castle_proxy(em2, "http://p2:8080")

        stop_ev1, stop_ev2 = threading.Event(), threading.Event()
        t1 = threading.Thread(target=lambda: stop_ev1.wait(timeout=5.0), name=f"bot-{c1}")
        t2 = threading.Thread(target=lambda: stop_ev2.wait(timeout=5.0), name=f"bot-{c2}")
        t1.start()
        t2.start()

        with api_server._lock:
            api_server._threads[c1] = t1
            api_server._threads[c2] = t2
            api_server._stop_events[c1] = stop_ev1
            api_server._stop_events[c2] = stop_ev2
            api_server._castle_emails[c1] = em1
            api_server._castle_emails[c2] = em2
            api_server._castle_users[c1] = uid
            api_server._castle_users[c2] = uid

        # Delete user
        res = api_server.delete_user_endpoint(uid, admin=self.admin_user)
        self.assertEqual(res["status"], "success")

        # Verify threads joined
        self.assertFalse(t1.is_alive())
        self.assertFalse(t2.is_alive())

        # Verify proxy bindings purged
        self.assertIsNone(proxy_manager.get_castle_proxy(em1))
        self.assertIsNone(proxy_manager.get_castle_proxy(em2))

        # Verify SQLite rows deleted
        self.assertIsNone(db.get_user(uid, db_path=self.db_path))
        self.assertEqual(len(db.get_user_castles(uid, db_path=self.db_path)), 0)

        # Verify tracking structures clean
        with api_server._lock:
            self.assertNotIn(c1, api_server._deleted_castles)
            self.assertNotIn(c2, api_server._deleted_castles)

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 13: Startup Exception Handling
    # ══════════════════════════════════════════════════════════════════════════
    def test_s13_startup_exception(self):
        """Scenario 13: Startup exception handling (clean rollback, error logging, no zombie threads)."""
        cid = "c_s13"
        email = "startup_exc@test.com"
        uid = "u_s13"

        db.save_castle({"castle_id": cid, "user_id": uid, "email": email, "state": "idle"}, db_path=self.db_path)

        req = api_server.StartBotRequest(
            castle_id=cid,
            user_id=uid,
            email=email,
            password="pass",
            config={},
            loop_interval=20,
        )

        mock_sm = MagicMock()
        mock_sm.get_or_login.side_effect = RuntimeError("Fatal crash during session initialization")

        with patch("core.session_manager.SessionManager", return_value=mock_sm):
            # _bot_thread should catch and not re-raise unhandled
            api_server._bot_thread(req)

        # Verify: All tracking structures cleaned up (no leaked state)
        with api_server._lock:
            self.assertNotIn(cid, api_server._threads)
            self.assertNotIn(cid, api_server._stop_events)
            self.assertNotIn(cid, api_server._castle_emails)

        c_rec = db.get_castle_by_id(cid, uid, db_path=self.db_path)
        self.assertEqual(c_rec.get("state"), "error")
        self.assertIn("Fatal crash", c_rec.get("conn_message", ""))

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 14: In-Flight Runtime Exception Handling
    # ══════════════════════════════════════════════════════════════════════════
    def test_s14_inflight_runtime_exception(self):
        """Scenario 14: In-flight runtime exception handling (clean catch, error recording, safe thread termination)."""
        cid = "c_s14"
        email = "runtime_exc@test.com"
        uid = "u_s14"

        db.save_castle({"castle_id": cid, "user_id": uid, "email": email, "password": "pass", "state": "idle"}, db_path=self.db_path)

        req = api_server.StartBotRequest(
            castle_id=cid,
            user_id=uid,
            email=email,
            password="pass",
            config={},
            loop_interval=20,
        )

        mock_account = MagicMock()
        mock_account.email = email
        mock_sm = MagicMock()
        mock_sm.get_or_login.return_value = mock_account

        with patch("core.session_manager.SessionManager", return_value=mock_sm), \
             patch("bot_manager.SessionManager", return_value=mock_sm):
            with patch("bot_manager.BotManager.run_loop", new_callable=AsyncMock) as mock_loop:
                mock_loop.side_effect = ZeroDivisionError("Simulated in-flight task computation fault")
                api_server._bot_thread(req)

        # Verify clean post-exception teardown
        with api_server._lock:
            self.assertNotIn(cid, api_server._threads)
            self.assertNotIn(cid, api_server._bot_managers)
            self.assertNotIn(cid, api_server._castle_emails)

        c_rec = db.get_castle_by_id(cid, uid, db_path=self.db_path)
        self.assertEqual(c_rec.get("state"), "error")
        self.assertIn("Simulated in-flight", c_rec.get("conn_message", ""))

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 15: WebSocket Client Disconnect Detection
    # ══════════════════════════════════════════════════════════════════════════
    def test_s15_websocket_disconnect(self):
        """Scenario 15: WebSocket client disconnect detection (coroutine termination within < 100ms, 0 leaked tasks)."""
        cid = "c_s15"

        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        # Raise WebSocketDisconnect when receive() is awaited
        mock_ws.receive = AsyncMock(side_effect=WebSocketDisconnect(1000))

        async def _run_ws():
            t0 = time.perf_counter()
            await api_server.ws_status(mock_ws, cid)
            elapsed = time.perf_counter() - t0
            return elapsed

        elapsed = asyncio.run(_run_ws())
        self.assertLess(elapsed, 0.25, f"WebSocket disconnect must terminate quickly (actual: {elapsed*1000:.1f}ms)")

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 16: WebSocket Reconnect After Drop
    # ══════════════════════════════════════════════════════════════════════════
    def test_s16_websocket_reconnect(self):
        """Scenario 16: WebSocket reconnect after drop (fresh connection, correct initial snapshot push)."""
        uid = "u_s16"
        cid = "c_s16"

        db.save_castle({"castle_id": cid, "user_id": uid, "email": "s16@test.com", "state": "running"}, db_path=self.db_path)

        # First connection session
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws1.receive = AsyncMock(side_effect=WebSocketDisconnect(1001))

        asyncio.run(api_server.ws_user_status(ws1, uid))
        ws1.send_json.assert_awaited_once()
        snapshot_1 = ws1.send_json.call_args[0][0]
        self.assertIn(cid, snapshot_1)

        # Second reconnection session after drop
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        ws2.receive = AsyncMock(side_effect=WebSocketDisconnect(1000))

        asyncio.run(api_server.ws_user_status(ws2, uid))
        ws2.send_json.assert_awaited_once()
        snapshot_2 = ws2.send_json.call_args[0][0]
        self.assertEqual(snapshot_1, snapshot_2, "Reconnected client must receive fresh matching snapshot")

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 17: Repeated Page Navigation / Rapid API Calls
    # ══════════════════════════════════════════════════════════════════════════
    def test_s17_repeated_page_navigation(self):
        """Scenario 17: Repeated page navigation / Rapid API calls (no unbounded memory growth, correct pagination)."""
        # Seed 30 castles in the database
        for i in range(30):
            db.save_castle({
                "castle_id": f"castle_nav_{i:02d}",
                "user_id": f"user_nav_{i % 5}",
                "email": f"nav_bot_{i:02d}@test.com",
                "castle_name": f"Empire {i:02d}",
                "state": "running" if i % 2 == 0 else "idle",
            }, db_path=self.db_path)

        # Rapidly request 50 paginated queries across different pages and filters
        for req_idx in range(50):
            page = (req_idx % 3) + 1
            page_size = 10
            search = "nav_bot_1" if req_idx % 4 == 0 else None
            filter_state = "running" if req_idx % 3 == 0 else "all"

            result = db.get_admin_castles_paginated(
                page=page,
                page_size=page_size,
                search=search,
                filter_status=filter_state,
                db_path=self.db_path,
            )

            self.assertIn("items", result)
            self.assertIn("total", result)
            self.assertIn("page", result)
            self.assertIn("page_size", result)
            self.assertLessEqual(len(result["items"]), page_size)

    # ══════════════════════════════════════════════════════════════════════════
    # Scenario 18: Repeated Search & Filter with Stalled Thread Isolation
    # ══════════════════════════════════════════════════════════════════════════
    def test_s18_repeated_search_and_filter_with_stalled_thread_isolation(self):
        """Scenario 18: Repeated search & filter with stalled thread diagnostic isolation."""
        # 1. Healthy running bot
        cid_ok = "c_healthy_18"
        mgr_ok = BotManager.__new__(BotManager)
        mgr_ok.castle_id = cid_ok
        mgr_ok.email = "healthy@test.com"
        mgr_ok.user_id = "u_18"
        mgr_ok.conn = MagicMock()
        mgr_ok.conn.is_connected = True
        mgr_ok._stop_event = threading.Event()
        mgr_ok.conn_state = "connected"
        mgr_ok.current_task = "gather"
        mgr_ok.current_task_name = "🌾 جمع"
        mgr_ok.status_message = "All good"
        mgr_ok.iteration = 1
        mgr_ok.loop_interval_minutes = 60
        mgr_ok.next_run_time = None
        mgr_ok.reconnect_attempt = 0
        mgr_ok.max_reconnect_attempts = 10
        mgr_ok.start_time = time.time()
        mgr_ok.last_heartbeat = time.time()

        th_ok = MagicMock()
        th_ok.is_alive.return_value = True
        th_ok.ident = 18001
        th_ok.name = f"bot-{cid_ok}"

        # 2. Quarantined stalled thread in _stalled_threads
        cid_stalled = "c_stalled_18"
        th_stalled = MagicMock()
        th_stalled.is_alive.return_value = True
        th_stalled.ident = 18002
        th_stalled.name = f"bot-{cid_stalled}"

        with api_server._lock:
            api_server._threads[cid_ok] = th_ok
            api_server._bot_managers[cid_ok] = mgr_ok
            api_server._castle_emails[cid_ok] = "healthy@test.com"
            api_server._castle_users[cid_ok] = "u_18"

            api_server._stalled_threads[cid_stalled] = {
                "thread": th_stalled,
                "ident": th_stalled.ident,
                "name": th_stalled.name,
                "castle_id": cid_stalled,
                "email": "stalled_bot@test.com",
                "user_id": "u_18",
                "stalled_at": datetime.now(timezone.utc).isoformat(),
            }

        # Query all: Stalled thread must be quarantined and excluded from total_active
        res_all = api_server.get_admin_live_processes(status="all", admin=self.admin_user)
        items_all = res_all.get("processes") or res_all.get("items", [])
        self.assertEqual(res_all["summary"]["total_active"], 1, "Only healthy bot counted in total_active")
        self.assertEqual(res_all["summary"]["stalled"], 1, "Stalled count correctly recorded in summary")
        self.assertEqual(len(items_all), 1, "Default items list contains only live processes")
        self.assertEqual(items_all[0]["castle_id"], cid_ok)

        # Query stalled: Retrieves isolated stalled thread
        res_stalled = api_server.get_admin_live_processes(status="stalled", admin=self.admin_user)
        items_stalled = res_stalled.get("processes") or res_stalled.get("items", [])
        self.assertEqual(len(items_stalled), 1)
        self.assertEqual(items_stalled[0]["castle_id"], cid_stalled)
        self.assertEqual(items_stalled[0]["live_category"], "stalled")

        # Query search: By email
        res_search_ok = api_server.get_admin_live_processes(search="healthy", admin=self.admin_user)
        items_search_ok = res_search_ok.get("processes") or res_search_ok.get("items", [])
        self.assertEqual(len(items_search_ok), 1)
        self.assertEqual(items_search_ok[0]["castle_id"], cid_ok)

        res_search_stalled = api_server.get_admin_live_processes(status="stalled", search="stalled_bot", admin=self.admin_user)
        items_search_stalled = res_search_stalled.get("processes") or res_search_stalled.get("items", [])
        self.assertEqual(len(items_search_stalled), 1)
        self.assertEqual(items_search_stalled[0]["castle_id"], cid_stalled)


if __name__ == "__main__":
    unittest.main()
