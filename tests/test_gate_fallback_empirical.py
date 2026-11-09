# -*- coding: utf-8 -*-
r"""
tests/test_gate_fallback_empirical.py
══════════════════════════════════════════════════════════════════════════════════════
Empirical Challenger Test Suite: Strict Memory Readiness Gate & Automated Fallback Recovery
Agent 12 Verification Battery.

Covers:
  1. Missing any of the 6 CRITICAL_STARTUP_CONTROLLERS or empty structural data:
     - wait_for_memory_ready halts and reports ready == False.
     - bot_manager.execute_task_pipeline() intercepts, logs warning, returns None without executing tasks.
  2. Fallback query dispatch when auto_fetch_missing=True:
     - 1001/1, 1002/7, 1003/1, 1005/1, 1004/1, 1007/1000 dispatched via send_nowait.
     - Ingestion of arriving packets unblocks the gate and returns True.
  3. Strict timeout enforcement:
     - When server never responds, gate strictly times out and returns False without hanging.
"""

from __future__ import annotations

import asyncio
import copy
import os
import sys
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure workspace root is in sys.path
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.live_memory import (
    LiveMemoryEngine,
    CRITICAL_STARTUP_CONTROLLERS,
    ALLOWED_CONTROLLERS,
    FALLBACK_QUERIES,
    get_fallback_query,
)
from game_client import (
    GateClient,
    GameConnection,
    GateCredentials,
    AccountSession,
)
from bot_manager import BotManager


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def make_valid_critical_init_data() -> Dict[str, Any]:
    """Generates a complete, structurally sound init_data mapping."""
    return {
        "cityCtrl": {
            "blist": [
                {
                    "binfo": {
                        "index": "1",
                        "bid": "101",
                        "iid": "0",
                        "lv": "25",
                        "state": "0",
                        "curres": "1000",
                    }
                },
                {
                    "binfo": {
                        "index": "2",
                        "bid": "102",
                        "iid": "0",
                        "lv": "20",
                        "state": "0",
                        "curres": "500",
                    }
                },
            ],
            "reslist": {
                "1001": "5000000",
                "1002": "4000000",
                "1003": "3000000",
                "1004": "2000000",
                "1005": "100000",
            },
            "saferes": {"1001": "1000000"},
            "dayMaxRes": {"1001": "20000000"},
        },
        "lordInfoCtrl": {
            "base": {
                "uid": 98765432,
                "nickName": "EmpiricalTester",
                "level": 35,
                "gold": 9999,
            }
        },
        "queueCtrl": {
            "1200": {"qtype": "1200", "bid": "101", "totalTime": 1800}
        },
        "armyCtrl": {
            "totalArmy": {"101": 15000, "102": 8000},
            "armyInfo": {},
        },
        "heroCtrl": [
            {"id": 5501001, "heroId": 5501001, "lv": 30, "state": 0},
            {"id": 5502001, "heroId": 5502001, "lv": 25, "state": 0},
        ],
        "backpackCtrl": {
            "2001": {"id": "2001", "count": "50"},
            "2002": {"id": "2002", "count": "10"},
        },
    }


def make_dummy_creds() -> GateCredentials:
    return GateCredentials(
        kingdom_id="105",
        server_name="empirical_srv",
        gate_ip="127.0.0.1",
        gate_port=12345,
        sub_id="sub_test",
        uid="98765432",
        secret=b"secret_bytes_1234567890",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite 1: Structural Readiness Gate Negative & Halt Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessGateStructuralHalting(unittest.IsolatedAsyncioTestCase):
    """
    Verifies that when conn.init_data is missing any critical controller
    or has empty structural data, wait_for_memory_ready halts and reports False.
    """

    def setUp(self):
        self.creds = make_dummy_creds()
        self.client = GateClient(self.creds)
        self.client._alive = True
        self.client.send_nowait = MagicMock()

    async def test_empty_init_data_halts_and_reports_false(self):
        """Empty init_data must halt gate and return False."""
        self.client.memory_engine.init_data.clear()
        is_ready, missing = self.client.memory_engine.is_memory_ready()
        self.assertFalse(is_ready)
        for ctrl in CRITICAL_STARTUP_CONTROLLERS:
            self.assertIn(ctrl, missing)

        ready = await self.client.wait_for_memory_ready(timeout=0.05, auto_fetch_missing=False)
        self.assertFalse(ready)

    async def test_each_missing_critical_controller_halts_gate(self):
        """Iteratively remove each of the 6 critical controllers and ensure gate halts."""
        for missing_ctrl in ("cityCtrl", "lordInfoCtrl", "queueCtrl", "armyCtrl", "heroCtrl", "backpackCtrl"):
            with self.subTest(missing_ctrl=missing_ctrl):
                data = make_valid_critical_init_data()
                del data[missing_ctrl]
                self.client.memory_engine.init_data = data

                is_ready, missing = self.client.memory_engine.is_memory_ready()
                self.assertFalse(is_ready)
                self.assertTrue(any(item.startswith(missing_ctrl) for item in missing))

                ready = await self.client.wait_for_memory_ready(timeout=0.05, auto_fetch_missing=False)
                self.assertFalse(ready, f"Gate must return False when {missing_ctrl} is missing")

    async def test_empty_city_blist_halts_gate(self):
        """cityCtrl with empty blist [] must halt gate and report cityCtrl.blist."""
        data = make_valid_critical_init_data()
        data["cityCtrl"]["blist"] = []
        self.client.memory_engine.init_data = data

        is_ready, missing = self.client.memory_engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("cityCtrl.blist", missing)

        ready = await self.client.wait_for_memory_ready(timeout=0.05, auto_fetch_missing=False)
        self.assertFalse(ready)

    async def test_empty_city_reslist_halts_gate(self):
        """cityCtrl with empty reslist {} must halt gate and report cityCtrl.reslist."""
        data = make_valid_critical_init_data()
        data["cityCtrl"]["reslist"] = {}
        self.client.memory_engine.init_data = data

        is_ready, missing = self.client.memory_engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("cityCtrl.reslist", missing)

        ready = await self.client.wait_for_memory_ready(timeout=0.05, auto_fetch_missing=False)
        self.assertFalse(ready)

    async def test_invalid_lord_info_base_halts_gate(self):
        """lordInfoCtrl without base or with zero/missing uid must halt gate."""
        data = make_valid_critical_init_data()
        data["lordInfoCtrl"] = {"base": {}}
        self.client.memory_engine.init_data = data

        is_ready, missing = self.client.memory_engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("lordInfoCtrl.base", missing)

        ready = await self.client.wait_for_memory_ready(timeout=0.05, auto_fetch_missing=False)
        self.assertFalse(ready)

    async def test_army_ctrl_missing_all_data_keys_halts_gate(self):
        """armyCtrl present but lacking totalArmy, armyInfo, and woundedArmy must halt gate."""
        data = make_valid_critical_init_data()
        data["armyCtrl"] = {"someOtherKey": 123}
        self.client.memory_engine.init_data = data

        is_ready, missing = self.client.memory_engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("armyCtrl.data", missing)

        ready = await self.client.wait_for_memory_ready(timeout=0.05, auto_fetch_missing=False)
        self.assertFalse(ready)

    async def test_complete_valid_data_passes_immediately(self):
        """When all 6 controllers and structural contents are valid, gate immediately unblocks True."""
        self.client.memory_engine.init_data = make_valid_critical_init_data()
        is_ready, missing = self.client.memory_engine.is_memory_ready()
        self.assertTrue(is_ready)
        self.assertEqual(missing, [])

        t0 = time.monotonic()
        ready = await self.client.wait_for_memory_ready(timeout=1.0, auto_fetch_missing=False)
        elapsed = time.monotonic() - t0

        self.assertTrue(ready)
        self.assertLess(elapsed, 0.1, "Valid memory must pass without delay!")


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite 2: Bot Manager Pipeline Interception
# ─────────────────────────────────────────────────────────────────────────────

class TestBotManagerPipelineInterception(unittest.IsolatedAsyncioTestCase):
    """
    Verifies that bot_manager.execute_task_pipeline() intercepts memory unreadiness:
    - Logs warning
    - Returns None
    - Does NOT execute any task from the pipeline
    """

    async def test_pipeline_intercepts_unready_memory_and_returns_none(self):
        session = AccountSession(email="gate_test@empire.local", user_id="12345", session_id="sess_gate")
        bot = BotManager(session, config={})

        logged_messages: List[str] = []
        bot._log_callback = lambda msg, *args, **kwargs: logged_messages.append(str(msg))

        # Mock connection where wait_for_memory_ready returns False
        mock_conn = MagicMock(spec=GameConnection)
        mock_conn.wait_for_memory_ready = AsyncMock(return_value=False)
        mock_conn.init_data = {}
        bot.conn = mock_conn

        # Track any task execution attempts
        executed_tasks: List[str] = []

        async def dummy_step_task(name: str):
            executed_tasks.append(name)
            return {"success": True}

        bot.step_1_city_harvest_task = lambda: dummy_step_task("city_harvest")
        bot.step_2_research_task = lambda: dummy_step_task("research")
        bot.step_3_alliance_task = lambda: dummy_step_task("alliance")

        # Execute pipeline
        result = await bot.execute_task_pipeline()

        # 1. Pipeline MUST return None
        self.assertIsNone(result, "execute_task_pipeline must return None when memory gate fails!")

        # 2. Warning message MUST be logged
        warning_found = any("الذاكرة الحية غير مكتملة" in m for m in logged_messages)
        self.assertTrue(warning_found, f"Warning about incomplete live memory must be logged! Found: {logged_messages}")

        # 3. ZERO tasks must be executed
        self.assertEqual(len(executed_tasks), 0, "No task must run when memory readiness gate fails!")

        # 4. wait_for_memory_ready was indeed called
        mock_conn.wait_for_memory_ready.assert_awaited_once_with(timeout=30.0, auto_fetch_missing=True)


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite 3: Automated Fallback Recovery & Query Dispatch
# ─────────────────────────────────────────────────────────────────────────────

class TestFallbackQueryDispatchAndRecovery(unittest.IsolatedAsyncioTestCase):
    """
    Verifies:
      1. Fallback queries (1001/1, 1002/7, 1003/1, 1005/1, 1004/1, 1007/1000)
         are dispatched via send_nowait when auto_fetch_missing=True.
      2. Ingestion of arriving responses unblocks the gate and returns True.
    """

    def setUp(self):
        self.creds = make_dummy_creds()
        self.client = GateClient(self.creds)
        self.client._alive = True
        self.sent_cmds: List[Tuple[str, str, Any]] = []

        def mock_send_nowait(cmd: str, subcmd: str, data: Any = None):
            self.sent_cmds.append((str(cmd), str(subcmd), data))

        self.client.send_nowait = mock_send_nowait

    async def test_fallback_dispatches_queries_for_missing_controllers(self):
        """When multiple controllers are missing, all corresponding fallback queries are dispatched."""
        # Missing cityCtrl, lordInfoCtrl, queueCtrl, armyCtrl, backpackCtrl, local_queues
        self.client.memory_engine.init_data.clear()
        self.client.local_queues_map.clear()

        # Run wait_for_memory_ready with short timeout so it sends queries and exits
        passed = await self.client.wait_for_memory_ready(timeout=0.08, auto_fetch_missing=True)
        self.assertFalse(passed)

        sent_pairs = [(c[0], c[1]) for c in self.sent_cmds]

        # Verify fallback query dispatch
        self.assertIn(('1001', '1'), sent_pairs, "CMD 1001/1 must be sent for cityCtrl")
        self.assertIn(('1002', '7'), sent_pairs, "CMD 1002/7 must be sent for lordInfoCtrl")
        self.assertIn(('1003', '1'), sent_pairs, "CMD 1003/1 must be sent for queueCtrl")
        self.assertIn(('1005', '1'), sent_pairs, "CMD 1005/1 must be sent for armyCtrl/heroCtrl")
        self.assertIn(('1004', '1'), sent_pairs, "CMD 1004/1 must be sent for backpackCtrl")
        self.assertIn(('1007', '1000'), sent_pairs, "CMD 1007/1000 must be sent for local_queues")

        # Verify lordInfoCtrl payload included uid
        lord_query = next((c for c in self.sent_cmds if c[0] == '1002' and c[1] == '7'), None)
        self.assertIsNotNone(lord_query)
        self.assertEqual(lord_query[2], {"uid": self.creds.uid})

    async def test_fallback_response_arrival_unblocks_gate(self):
        """
        When missing cityCtrl, fallback query is sent.
        When server response packet arrives and is ingested, gate unblocks and returns True.
        """
        valid_state = make_valid_critical_init_data()
        city_data_arriving = valid_state.pop("cityCtrl")

        # Initial state has 5 controllers, missing cityCtrl
        self.client.memory_engine.init_data = valid_state
        self.client.local_queues_map["1"] = {"id": "1"}

        # Background simulator coroutine that sends server response after 30ms
        async def simulate_server_reply():
            await asyncio.sleep(0.03)
            # Ingest packet mimicking server response for CMD 1001 / SUB 1
            response_packet = {
                "cmd": "1001",
                "sub": "1",
                "data": {
                    "retdata": {
                        "cityCtrl": city_data_arriving
                    }
                }
            }
            self.client.memory_engine.ingest_packet(response_packet)

        sim_task = asyncio.create_task(simulate_server_reply())

        t0 = time.monotonic()
        ready = await self.client.wait_for_memory_ready(timeout=1.0, auto_fetch_missing=True)
        elapsed = time.monotonic() - t0
        await sim_task

        # Gate must unblock and succeed
        self.assertTrue(ready, "Gate must return True once fallback data arrives!")
        self.assertLess(elapsed, 0.5, "Gate should unblock promptly after response ingestion!")

        # Verify cityCtrl.blist was actually restored in init_data
        self.assertIn("cityCtrl", self.client.memory_engine.init_data)
        self.assertEqual(len(self.client.memory_engine.init_data["cityCtrl"]["blist"]), 2)

        # Verify fallback query was sent
        sent_pairs = [(c[0], c[1]) for c in self.sent_cmds]
        self.assertIn(('1001', '1'), sent_pairs)

    async def test_multi_controller_gradual_arrival_unblocks_gate(self):
        """Simulate staggered arrival of multiple missing controllers (cityCtrl and lordInfoCtrl)."""
        valid_state = make_valid_critical_init_data()
        city_payload = valid_state.pop("cityCtrl")
        lord_payload = valid_state.pop("lordInfoCtrl")

        self.client.memory_engine.init_data = valid_state
        self.client.local_queues_map["1"] = {"id": "1"}

        async def staggered_responses():
            # City arrives at 25ms
            await asyncio.sleep(0.025)
            self.client.memory_engine.ingest_packet({
                "cmd": "1001", "sub": "1",
                "data": {"retdata": {"cityCtrl": city_payload}}
            })
            # Lord arrives at 50ms
            await asyncio.sleep(0.025)
            self.client.memory_engine.ingest_packet({
                "cmd": "1002", "sub": "7",
                "data": {"retdata": {"lordInfoCtrl": lord_payload}}
            })

        sim_task = asyncio.create_task(staggered_responses())
        ready = await self.client.wait_for_memory_ready(timeout=1.0, auto_fetch_missing=True)
        await sim_task

        self.assertTrue(ready, "Gate must unblock when all staggered responses arrive!")
        self.assertIn("cityCtrl", self.client.memory_engine.init_data)
        self.assertIn("lordInfoCtrl", self.client.memory_engine.init_data)


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite 4: Strict Timeout Enforcement & No Infinite Hang
# ─────────────────────────────────────────────────────────────────────────────

class TestReadinessGateStrictTimeout(unittest.IsolatedAsyncioTestCase):
    """
    Verifies that if the server NEVER responds to fallback queries:
      - The gate strictly times out after the specified timeout period.
      - Does NOT hang indefinitely or exceed acceptable time margins.
      - Returns False cleanly.
    """

    def setUp(self):
        self.creds = make_dummy_creds()
        self.client = GateClient(self.creds)
        self.client._alive = True
        self.client.send_nowait = MagicMock()

    async def test_gate_strictly_times_out_when_server_is_silent(self):
        """Server is completely silent; gate must timeout at ~0.15s without hanging."""
        data = make_valid_critical_init_data()
        del data["cityCtrl"]  # Missing cityCtrl
        self.client.memory_engine.init_data = data

        timeout_sec = 0.15
        t0 = time.monotonic()
        ready = await self.client.wait_for_memory_ready(timeout=timeout_sec, auto_fetch_missing=True)
        elapsed = time.monotonic() - t0

        self.assertFalse(ready, "Gate must return False upon timeout!")
        self.assertGreaterEqual(elapsed, timeout_sec * 0.85, f"Elapsed ({elapsed:.3f}s) must be >= 85% of timeout ({timeout_sec}s)")
        self.assertLess(elapsed, timeout_sec + 0.35, f"Elapsed ({elapsed:.3f}s) must not exceed timeout + margin")

    async def test_gate_aborts_immediately_if_connection_dies(self):
        """If gate client connection dies (_alive becomes False), gate aborts immediately without waiting for timeout."""
        data = make_valid_critical_init_data()
        del data["cityCtrl"]
        self.client.memory_engine.init_data = data

        async def kill_conn_after_30ms():
            await asyncio.sleep(0.03)
            self.client._alive = False

        sim_task = asyncio.create_task(kill_conn_after_30ms())
        t0 = time.monotonic()
        ready = await self.client.wait_for_memory_ready(timeout=5.0, auto_fetch_missing=True)
        elapsed = time.monotonic() - t0
        await sim_task

        self.assertFalse(ready)
        self.assertLess(elapsed, 0.5, "Gate must abort immediately when connection dies, without waiting 5.0s!")

    async def test_game_connection_wrapper_timeout(self):
        """GameConnection.wait_for_memory_ready delegates properly and enforces timeout."""
        session = AccountSession("test@emp.local", "uid_wrap", "sess_wrap")
        conn = GameConnection(session)
        conn._gate = self.client
        conn.creds = self.creds

        # Set incomplete memory
        self.client.memory_engine.init_data.clear()

        t0 = time.monotonic()
        ready = await conn.wait_for_memory_ready(timeout=0.1, auto_fetch_missing=True)
        elapsed = time.monotonic() - t0

        self.assertFalse(ready)
        self.assertGreaterEqual(elapsed, 0.08)
        self.assertLess(elapsed, 0.4)


if __name__ == "__main__":
    unittest.main()
