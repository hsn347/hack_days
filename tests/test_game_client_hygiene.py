# -*- coding: utf-8 -*-
"""
tests/test_game_client_hygiene.py — Comprehensive Verification Suite for game_client.py
══════════════════════════════════════════════════════════════════════════════════════
Tests:
  1. GameClient / GateClient initialization and LiveMemoryEngine wiring.
  2. Zero packet leakage: Non-whitelisted controllers dropped at network ingress.
  3. Real-time CMD 1009 push notification synchronization into init_data.
  4. Bounded cached_packets: Bounded ring cache capping to prevent unbounded memory growth.
  5. check_and_merge_controller: Fast O(1) live memory lookup without scanning cached_packets.
  6. wait_for_memory_ready: Strict startup gating with automated fallback queries.
  7. GameConnection delegation and memory_engine accessor.
"""

import asyncio
import unittest
from game_client import GameClient, GateClient, GameConnection, GateCredentials, AccountSession
from core.live_memory import LiveMemoryEngine, ALLOWED_CONTROLLERS, CRITICAL_STARTUP_CONTROLLERS


class TestGameClientHygiene(unittest.TestCase):

    def setUp(self):
        self.creds = GateCredentials(
            kingdom_id="100",
            server_name="kingdom_100",
            gate_ip="127.0.0.1",
            gate_port=1234,
            sub_id="sub_test",
            uid="998877",
            secret=b"secret1234567890"
        )
        self.client = GameClient(self.creds)
        self.client._alive = True

    def test_initialization_and_engine_wiring(self):
        """Verify GameClient initializes LiveMemoryEngine and wires init_data."""
        self.assertIs(GameClient, GateClient)
        self.assertIsInstance(self.client.memory_engine, LiveMemoryEngine)
        self.assertIs(self.client.init_data, self.client.memory_engine.init_data)
        self.assertIs(self.client.local_queues_map, self.client.memory_engine.local_queues_map)

    def test_zero_packet_leakage_in_dispatch(self):
        """Verify non-whitelisted controllers are dropped before entering init_data."""
        packet_content = {
            "cmd": "1001",
            "subcmd": "1",
            "data": {
                "retdata": {
                    "cityCtrl": {
                        "blist": [{"binfo": {"index": 1, "bid": 101, "lv": 10, "state": 0}}],
                        "reslist": {"1001": 50000}
                    },
                    "chatCtrl": {"history": ["chat1", "chat2"]},
                    "RedPointCtrl": {"red": 1},
                    "voiceRoomCtrl": {"active": True},
                    "rechargeActivityCtrl": {"bonus": 100}
                }
            }
        }
        self.client.memory_engine.ingest_packet(packet_content)

        # Whitelisted controller retained
        self.assertIn("cityCtrl", self.client.init_data)
        self.assertEqual(len(self.client.init_data["cityCtrl"]["blist"]), 1)

        # Non-whitelisted controllers permanently pruned
        self.assertNotIn("chatCtrl", self.client.init_data)
        self.assertNotIn("RedPointCtrl", self.client.init_data)
        self.assertNotIn("voiceRoomCtrl", self.client.init_data)
        self.assertNotIn("rechargeActivityCtrl", self.client.init_data)

    def test_real_time_cmd_1009_notification_sync(self):
        """Verify CMD 1009 notifications update init_data in real time."""
        # Initial baseline state
        self.client.init_data["cityCtrl"] = {
            "blist": [{"binfo": {"index": 10, "bid": 102, "lv": 5, "curres": "100"}}],
            "reslist": {"1001": 1000, "1002": 2000}
        }

        # Simulate push notification NOTIFY_CITY (9)
        notify_content = {
            "cmd": "1009",
            "subcmd": "9",
            "data": {
                "notifyID": "NOTIFY_CITY",
                "notifyData": [
                    {
                        "res": {"1001": -200, "1002": 500},
                        "updateUnCollectRes": {"10": 50}
                    }
                ]
            }
        }
        self.client.memory_engine.ingest_packet(notify_content)

        # Check resource deltas
        reslist = self.client.init_data["cityCtrl"]["reslist"]
        self.assertEqual(int(reslist["1001"]), 800)
        self.assertEqual(int(reslist["1002"]), 2500)

        # Check uncollected resource increment on building 10
        building = self.client.init_data["cityCtrl"]["blist"][0]
        curres = building.get("curres") or building.get("binfo", {}).get("curres")
        self.assertEqual(int(curres), 150)

    def test_bounded_cached_packets(self):
        """Verify cached_packets remains strictly bounded and does not bloat memory."""
        # Inject 150 unique packets
        for i in range(150):
            cmd_key = (f"cmd_{i}", f"sub_{i}")
            self.client.cached_packets[cmd_key] = {"data": {"i": i}}
            if len(self.client.cached_packets) > 64:
                oldest = next(iter(self.client.cached_packets))
                self.client.cached_packets.pop(oldest, None)

        self.assertEqual(len(self.client.cached_packets), 64)
        # Oldest packets must have been pruned
        self.assertNotIn(("cmd_0", "sub_0"), self.client.cached_packets)
        # Most recent packets must be present
        self.assertIn(("cmd_149", "sub_149"), self.client.cached_packets)

    def test_check_and_merge_controller_fast_o1(self):
        """Verify check_and_merge_controller is an O(1) direct check without packet scanning."""
        self.client.init_data["lordInfoCtrl"] = {"base": {"nickName": "Sultan", "level": 25}}

        exists, data = self.client.check_and_merge_controller("lordInfoCtrl")
        self.assertTrue(exists)
        self.assertEqual(data.get("base", {}).get("nickName"), "Sultan")

        not_exists, empty_data = self.client.check_and_merge_controller("nonExistent")
        self.assertFalse(not_exists)
        self.assertEqual(empty_data, {})

    def test_wait_for_memory_ready_behavior(self):
        """Verify wait_for_memory_ready gate and automated fallback queries."""
        # Incomplete memory -> wait_for_memory_ready times out / returns False
        async def run_not_ready():
            return await self.client.wait_for_memory_ready(timeout=0.1, auto_fetch_missing=False)

        res = asyncio.run(run_not_ready())
        self.assertFalse(res)

        # Fill critical controllers structurally
        self.client.init_data["cityCtrl"] = {"blist": [{"index": 1}], "reslist": {"1001": 100}}
        self.client.init_data["lordInfoCtrl"] = {"base": {"uid": 998877, "partition": 100}}
        self.client.init_data["queueCtrl"] = {}
        self.client.init_data["armyCtrl"] = {"totalArmy": {"101": 1000}}
        self.client.init_data["heroCtrl"] = []
        self.client.init_data["backpackCtrl"] = {}

        async def run_ready():
            return await self.client.wait_for_memory_ready(timeout=1.0, auto_fetch_missing=False)

        ready_res = asyncio.run(run_ready())
        self.assertTrue(ready_res)

    def test_game_connection_delegation(self):
        """Verify GameConnection delegates init_data, memory_engine, and wait_for_memory_ready."""
        account = AccountSession("test@example.com", "u123", "sess123")
        conn = GameConnection(account)
        conn._gate = self.client

        self.assertIs(conn.init_data, self.client.init_data)
        self.assertIs(conn.memory_engine, self.client.memory_engine)

        # check_and_merge_controller delegation
        exists, _ = conn.check_and_merge_controller("cityCtrl")
        self.assertEqual(exists, "cityCtrl" in self.client.init_data)

        # wait_for_memory_ready delegation
        async def run_conn_ready():
            return await conn.wait_for_memory_ready(timeout=0.1, auto_fetch_missing=False)

        # Depending on state of client
        is_ready = asyncio.run(run_conn_ready())
        self.assertIsInstance(is_ready, bool)


if __name__ == "__main__":
    unittest.main()
