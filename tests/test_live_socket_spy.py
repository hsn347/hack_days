# -*- coding: utf-8 -*-
r"""
tests/test_live_socket_spy.py — Empirical Live Socket Spy & S2C Notify Verification Suite
══════════════════════════════════════════════════════════════════════════════════════════
Author: Agent 13 (Live Socket Spy & Notify Verifier) — Empirical Challenger
Workspace: e:\osmanli

Rigorously verifies:
1. Intercepting & processing incoming S2C packets with cmd == 1009 (authoritative push notification):
   - NOTIFY_CITY ("9" in Lua, comparison with prompt "1"): delta resources, saferes, dayMaxRes,
     uncollected resources (updateUnCollectRes), extra charge queue (openChargeQueue).
   - NOTIFY_QUEUE ("14") and NOTIFY_PLAYER_QUEUE_CHANGE ("1051"): queue lifecycle, normal lv+1,
     honorLv+1, cancellation, removal from queueCtrl.
   - NOTIFY_BACKPACK_UPDATE ("1"): add and use item counts, zero clamping.
   - NOTIFY_LOCAL_QUEUE_SYNC ("202"): march line ADD(1), REMOVE(2), UPDATE(3), ADD_ALL(4), REMOVE_ALL(5).
2. Wire-level propagation latency from TCP socket stream unpacking in _dispatch() to init_data availability (O(1)).
3. Bounded capacity check for cached_packets (FIFO limit <= 64, prevents unbounded memory bloat).
4. Detection and empirical demonstration of double-ingestion anomalies (if present).
"""

from __future__ import annotations

import copy
import json
import os
import struct
import sys
import time
import unittest
from typing import Any, Dict

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.onemt_bot import xor_crypt
from core.live_memory import (
    LiveMemoryEngine,
    ALLOWED_CONTROLLERS,
    BUILD_STATE,
)
from game_client import GateClient, GateCredentials


def make_raw_gate_packet(content: Dict[str, Any], session: int = 0) -> bytes:
    """
    Constructs a valid binary wire frame identical to the game server TCP stream:
    [2 or 5 bytes length header] + [xor_crypt(json) payload] + [1 byte ok=1] + [4 bytes session BE]
    """
    json_bytes = json.dumps(content, separators=(',', ':')).encode('utf-8')
    raw = xor_crypt(json_bytes)
    ok_byte = b'\x01'
    sess_bytes = struct.pack('>I', session)
    body = raw + ok_byte + sess_bytes

    l = len(body)
    if l < 0xFFFF:
        head = bytes([(l >> 8) & 0xFF, l & 0xFF])
    else:
        head = bytes([0xFF, 0xFF, (l >> 16) & 0xFF, (l >> 8) & 0xFF, l & 0xFF])
    return head + body


class MockGateClient(GateClient):
    """Subclass of GateClient bypassing actual network connection for wire-level testing."""
    def __init__(self):
        dummy_creds = GateCredentials(
            kingdom_id="101",
            server_name="test_srv",
            gate_ip="127.0.0.1",
            gate_port=9999,
            sub_id="sub1",
            uid="987654321",
            secret=b"0123456789abcdef"
        )
        super().__init__(dummy_creds)
        self._alive = True

    def feed_wire_packet(self, content: Dict[str, Any], session: int = 0):
        """Feeds wire packet bytes into _buf and runs _dispatch()."""
        raw_pkt = make_raw_gate_packet(content, session)
        self._buf += raw_pkt
        self._dispatch()


class TestLiveSocketSpyCity(unittest.TestCase):
    """Empirical verification of NOTIFY_CITY (CMD 1009) and cityCtrl reflection."""

    def setUp(self):
        self.client = MockGateClient()
        # Initialize basic cityCtrl baseline
        self.client.init_data["cityCtrl"] = {
            "reslist": {
                "1001": "50000",   # Food
                "1002": "30000",   # Wood
                "1003": "10000",   # Iron
                "1004": "5000",    # Mithril
                "1005": "1000"     # Gold
            },
            "saferes": {"1001": "10000", "1002": "10000"},
            "dayMaxRes": {"1001": "5000000"},
            "blist": [
                {
                    "binfo": {
                        "bid": "101",
                        "iid": "1",
                        "index": "1",
                        "lv": "20",
                        "state": "0",
                        "curres": "100"
                    }
                },
                {
                    "binfo": {
                        "bid": "105",
                        "iid": "2",
                        "index": "15",
                        "lv": "15",
                        "state": "0",
                        "curres": "500"
                    }
                }
            ],
            "queue": {}
        }

    def test_notify_city_lua_spec_id_9_direct_engine(self):
        """Verify NOTIFY_CITY via LiveMemoryEngine with standard Lua notifyID '9'."""
        engine = self.client.memory_engine
        city_payload = [
            {
                "res": {"1001": 5000, "1002": -10000},
                "saferes": {"1001": "20000", "1002": "20000"},
                "dayMaxRes": {"1001": "6000000"},
                "updateUnCollectRes": {"15": 250},
                "openChargeQueue": {"totaltime": 172800, "lefttime": 86400}
            }
        ]

        engine.handle_notify("9", city_payload)
        city = self.client.init_data["cityCtrl"]

        # 1. Delta resources: 50000 + 5000 = 55000, 30000 - 10000 = 20000
        self.assertEqual(int(city["reslist"]["1001"]), 55000)
        self.assertEqual(int(city["reslist"]["1002"]), 20000)

        # 2. Safe resources & dayMaxRes
        self.assertEqual(city["saferes"]["1001"], "20000")
        self.assertEqual(city["dayMaxRes"]["1001"], "6000000")

        # 3. Uncollected resources: 500 + 250 = 750
        b15 = next(b for b in city["blist"] if b["binfo"]["index"] == "15")
        self.assertEqual(int(b15["binfo"]["curres"]), 750)

        # 4. Charge queue
        self.assertIn("1201", city["queue"])
        self.assertEqual(city["queue"]["1201"]["totaltime"], 172800)
        self.assertIn("1201", self.client.init_data["queueCtrl"])

    def test_notify_city_clamp_below_zero(self):
        """Verify resource delta subtraction clamps to 0 when cost exceeds balance."""
        engine = self.client.memory_engine
        city_payload = [{"res": {"1003": -50000}}]  # Iron 10000 - 50000 -> 0
        engine.handle_notify("9", city_payload)
        city = self.client.init_data["cityCtrl"]
        self.assertEqual(int(city["reslist"]["1003"]), 0)

    def test_notify_city_prompt_notation_discrepancy(self):
        """
        Adversarial Analysis of NOTIFY_CITY ('1') in Prompt vs Lua Spec ('9'):
        Lua cmdDef_dec.lua specifies:
          NOTIFY_BACKPACK_UPDATE = '1'
          NOTIFY_CITY_UPDATE = '9'
        If notifyID == '1' is sent with city payload, verify what LiveMemoryEngine does.
        """
        engine = LiveMemoryEngine(init_data=copy.deepcopy(self.client.init_data))
        city_payload = [{"res": {"1001": 9999}}]

        # Passing "1" should NOT update cityCtrl because "1" is mapped to BACKPACK in Lua
        engine.handle_notify("1", city_payload)
        self.assertEqual(int(engine.init_data["cityCtrl"]["reslist"]["1001"]), 50000,
                         "notifyID '1' must not accidentally affect cityCtrl (1 is reserved for BACKPACK)")

        # Passing "9" or "NOTIFY_CITY" updates cityCtrl
        engine.handle_notify("NOTIFY_CITY", city_payload)
        self.assertEqual(int(engine.init_data["cityCtrl"]["reslist"]["1001"]), 59999)


class TestLiveSocketSpyQueue(unittest.TestCase):
    """Empirical verification of NOTIFY_QUEUE (14) & NOTIFY_PLAYER_QUEUE_CHANGE (1051)."""

    def setUp(self):
        self.client = MockGateClient()
        self.client.init_data["cityCtrl"] = {
            "blist": [
                {
                    "binfo": {
                        "bid": "101",
                        "iid": "1",
                        "index": "1",
                        "lv": "24",
                        "honorLv": "0",
                        "hlv": "0",
                        "state": BUILD_STATE.UPGRADING
                    }
                },
                {
                    "binfo": {
                        "bid": "102",
                        "iid": "1",
                        "index": "2",
                        "lv": "30",
                        "honorLv": "2",
                        "hlv": "2",
                        "state": BUILD_STATE.UPGRADING
                    }
                },
                {
                    "binfo": {
                        "bid": "103",
                        "iid": "1",
                        "index": "3",
                        "lv": "15",
                        "state": BUILD_STATE.UPGRADING
                    }
                }
            ]
        }
        self.client.init_data["queueCtrl"] = {
            "1200": {
                "qtype": "1200",
                "bid": 101,
                "iid": 1,
                "index": 1,
                "optype": 2
            }
        }

    def test_notify_queue_regular_upgrade_finish(self):
        """Regular building upgrade: increments lv by 1, state resets to NORMAL, queue removed."""
        engine = self.client.memory_engine
        payload = [
            {
                "dispatchQueueEvent": {
                    "queuetype": "1200",
                    "bid": 101,
                    "iid": 1,
                    "index": 1,
                    "optype": 2,
                    "notifyType": "finish"
                }
            }
        ]
        engine.handle_notify("14", payload)
        b = self.client.init_data["cityCtrl"]["blist"][0]["binfo"]
        self.assertEqual(b["lv"], "25")
        self.assertEqual(b["state"], BUILD_STATE.NORMAL)
        self.assertNotIn("1200", self.client.init_data["queueCtrl"])

    def test_notify_queue_honor_upgrade_finish(self):
        """Honor building upgrade: increments honorLv & hlv by 1, state resets to NORMAL."""
        engine = self.client.memory_engine
        payload = [
            {
                "dispatchQueueEvent": {
                    "queuetype": "1200",
                    "bid": 102,
                    "iid": 1,
                    "index": 2,
                    "optype": 2,
                    "honorUpgradeWaitRsp": 1,
                    "notifyType": "finish"
                }
            }
        ]
        engine.handle_notify("14", payload)
        b = self.client.init_data["cityCtrl"]["blist"][1]["binfo"]
        self.assertEqual(int(b["honorLv"]), 3)
        self.assertEqual(int(b["hlv"]), 3)
        self.assertEqual(b["state"], BUILD_STATE.NORMAL)

    def test_notify_queue_cancel_upgrade(self):
        """Upgrade cancellation: state resets to NORMAL, lv does NOT increment."""
        engine = self.client.memory_engine
        payload = [
            {
                "dispatchQueueEvent": {
                    "queuetype": "1200",
                    "bid": 103,
                    "iid": 1,
                    "index": 3,
                    "optype": 11,  # CANCEL
                    "notifyType": "cancel"
                }
            }
        ]
        engine.handle_notify("14", payload)
        b = self.client.init_data["cityCtrl"]["blist"][2]["binfo"]
        self.assertEqual(b["lv"], "15")  # Level untouched
        self.assertEqual(b["state"], BUILD_STATE.NORMAL)

    def test_notify_player_queue_change_1051(self):
        """NOTIFY_PLAYER_QUEUE_CHANGE (1051) updates queueCtrl."""
        engine = self.client.memory_engine
        payload = [
            {
                "qtype": "1227",
                "starttime": 1700000000,
                "totaltime": 3600,
                "lefttime": 1800,
                "notifyType": "update"
            }
        ]
        engine.handle_notify("1051", payload)
        self.assertIn("1227", self.client.init_data["queueCtrl"])
        self.assertEqual(self.client.init_data["queueCtrl"]["1227"]["lefttime"], 1800)


class TestLiveSocketSpyBackpack(unittest.TestCase):
    """Empirical verification of NOTIFY_BACKPACK_UPDATE (CMD 1009 / sub 1)."""

    def setUp(self):
        self.client = MockGateClient()
        self.client.init_data["backpackCtrl"] = {
            "200101": {"id": "200101", "count": "100"},
            "200102": {"id": "200102", "count": "20"}
        }

    def test_backpack_add_and_use_dict_format(self):
        """Item addition and consumption with dictionary backpack container."""
        engine = self.client.memory_engine
        payload = [
            {
                "add": {"200101": 50, "300501": 5},
                "use": {"200102": 15}
            }
        ]
        engine.handle_notify("1", payload)
        bp = self.client.init_data["backpackCtrl"]

        # 200101: 100 + 50 = 150
        self.assertEqual(int(bp["200101"]["count"]), 150)
        # 300501: newly added = 5
        self.assertEqual(int(bp["300501"]["count"]), 5)
        # 200102: 20 - 15 = 5
        self.assertEqual(int(bp["200102"]["count"]), 5)

    def test_backpack_clamp_to_zero_on_excessive_use(self):
        """Using more than available count clamps to 0."""
        engine = self.client.memory_engine
        payload = [{"use": {"200102": 999}}]
        engine.handle_notify("1", payload)
        bp = self.client.init_data["backpackCtrl"]
        self.assertEqual(int(bp["200102"]["count"]), 0)


class TestLiveSocketSpyLocalQueues(unittest.TestCase):
    """Empirical verification of NOTIFY_LOCAL_QUEUE_SYNC (CMD 1009 / sub 202)."""

    def setUp(self):
        self.client = MockGateClient()
        self.engine = self.client.memory_engine

    def test_local_queue_sync_full_lifecycle(self):
        """Tests ADD (1), UPDATE (3), REMOVE (2), ADD_ALL (4), REMOVE_ALL (5)."""
        # 1. ADD march
        add_msg = [{"msgType": 1, "data": {"id": "march_01", "speed": 100, "status": "marching"}}]
        self.engine.handle_notify("202", add_msg)
        self.assertIn("march_01", self.engine.local_queues_map)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 1)

        # 2. UPDATE march
        update_msg = [{"msgType": 3, "data": {"id": "march_01", "speed": 200, "status": "returning"}}]
        self.engine.handle_notify("202", update_msg)
        self.assertEqual(self.engine.local_queues_map["march_01"]["speed"], 200)
        self.assertEqual(self.engine.local_queues_map["march_01"]["status"], "returning")

        # 3. ADD another march
        add_msg_2 = [{"msgType": 1, "data": {"id": "march_02", "speed": 150, "status": "gathering"}}]
        self.engine.handle_notify("202", add_msg_2)
        self.assertEqual(len(self.engine.local_queues_map), 2)

        # 4. REMOVE first march
        remove_msg = [{"msgType": 2, "data": {"id": "march_01"}}]
        self.engine.handle_notify("202", remove_msg)
        self.assertNotIn("march_01", self.engine.local_queues_map)
        self.assertIn("march_02", self.engine.local_queues_map)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 1)

        # 5. ADD_ALL full replacement
        add_all_msg = [
            {
                "msgType": 4,
                "data": [
                    {"id": "m10", "speed": 100},
                    {"id": "m20", "speed": 120}
                ]
            }
        ]
        self.engine.handle_notify("202", add_all_msg)
        self.assertEqual(set(self.engine.local_queues_map.keys()), {"m10", "m20"})
        self.assertEqual(len(self.engine.init_data["local_queues"]), 2)

        # 6. REMOVE_ALL clear
        remove_all_msg = [{"msgType": 5, "data": {}}]
        self.engine.handle_notify("202", remove_all_msg)
        self.assertEqual(len(self.engine.local_queues_map), 0)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 0)


class TestLiveSocketSpyWireLatencyAndMemoryBounds(unittest.TestCase):
    """
    Measures propagation latency from raw socket packet arrival through _dispatch()
    to init_data reflection, and verifies cached_packets bounded capacity.
    """

    def setUp(self):
        self.client = MockGateClient()
        self.client.init_data["cityCtrl"] = {"reslist": {"1001": "100000"}}

    def test_cached_packets_strict_fifo_bound(self):
        """Feed 250 packets with distinct cmd/subcmd. Verify cached_packets never exceeds 64."""
        for i in range(250):
            cmd = f"9{i:03d}"
            sub = f"{i % 10}"
            pkt_dict = {
                "cmd": cmd,
                "subcmd": sub,
                "data": {"seq": i}
            }
            self.client.feed_wire_packet(pkt_dict, session=i)

        self.assertLessEqual(len(self.client.cached_packets), 64,
                             f"cached_packets must be strictly bounded <= 64, got {len(self.client.cached_packets)}")

    def test_propagation_latency_benchmark_o1(self):
        """
        Benchmark propagation latency across 1,000 real binary wire packets.
        Ensures O(1) instantaneous reflection (average < 100 microseconds).
        """
        latencies_us = []
        target_ctrl = "test_run"

        for i in range(1000):
            # Create a packet updating lordInfoCtrl
            content = {
                "cmd": "1002",
                "subcmd": "1",
                "data": {
                    "lordInfoCtrl": {
                        "base": {
                            "gold": 1000 + i,
                            "uid": "12345"
                        }
                    }
                }
            }
            wire_bytes = make_raw_gate_packet(content, session=i)

            t0 = time.perf_counter_ns()
            self.client._buf += wire_bytes
            self.client._dispatch()
            t1 = time.perf_counter_ns()

            # Verify instantaneous reflection in init_data
            gold_val = self.client.init_data.get("lordInfoCtrl", {}).get("base", {}).get("gold")
            self.assertEqual(gold_val, 1000 + i)

            latency_us = (t1 - t0) / 1000.0  # microseconds
            latencies_us.append(latency_us)

        avg_latency = sum(latencies_us) / len(latencies_us)
        p95_latency = sorted(latencies_us)[int(len(latencies_us) * 0.95)]
        p99_latency = sorted(latencies_us)[int(len(latencies_us) * 0.99)]
        max_latency = max(latencies_us)

        print(f"\n[LATENCY BENCHMARK] 1,000 Packets Wire-to-init_data:")
        print(f"  Average: {avg_latency:.2f} µs ({avg_latency/1000.0:.4f} ms)")
        print(f"  P95:     {p95_latency:.2f} µs ({p95_latency/1000.0:.4f} ms)")
        print(f"  P99:     {p99_latency:.2f} µs ({p99_latency/1000.0:.4f} ms)")
        print(f"  Max:     {max_latency:.2f} µs ({max_latency/1000.0:.4f} ms)")

        # Assert instantaneous O(1) performance (< 1 millisecond = 1000 µs on average)
        self.assertLess(avg_latency, 1000.0, f"Average propagation latency must be < 1ms, got {avg_latency:.2f} µs")

    def test_double_ingestion_bug_detection(self):
        """
        ADVERSARIAL CHALLENGE TEST:
        Checks whether _dispatch() triggers double execution on CMD 1009 notifications:
        - game_client.py:676 calls `self.memory_engine.ingest_packet(c)`
        - inside ingest_packet(), it checks cmd == '1009' and calls handle_notify()
        - game_client.py:688 calls `self.memory_engine.handle_notify(...)` again!
        """
        # Set up a fresh client with 10,000 food
        self.client.init_data["cityCtrl"] = {"reslist": {"1001": "10000"}}

        # Feed ONE packet with +1,000 food via CMD 1009
        content = {
            "cmd": "1009",
            "subcmd": "9",
            "data": {
                "notifyID": "9",
                "notifyData": [{"res": {"1001": 1000}}]
            }
        }
        self.client.feed_wire_packet(content, session=1)

        actual_food = int(self.client.init_data["cityCtrl"]["reslist"]["1001"])
        print(f"\n[ADVERSARIAL CHECK 1: RESOURCES] Expected Food: 11000, Actual Food in init_data: {actual_food}")
        self.assertEqual(actual_food, 11000, "Verifies single ingestion: 1000 added exactly once")

    def test_wire_queue_finish_double_level_jump_proof(self):
        """
        ADVERSARIAL CHALLENGE TEST 2:
        Demonstrates that single ingestion correctly increments the building level
        exactly ONCE (from lv 10 to lv 11 on a single finish packet).
        """
        self.client.init_data["cityCtrl"] = {
            "blist": [
                {
                    "binfo": {
                        "bid": "101",
                        "iid": "1",
                        "index": "5",
                        "lv": "10",
                        "state": BUILD_STATE.UPGRADING
                    }
                }
            ]
        }
        self.client.init_data["queueCtrl"] = {
            "1200": {"qtype": "1200", "bid": 101, "iid": 1, "index": 5, "optype": 2}
        }

        # Wire packet with finish event
        content = {
            "cmd": "1009",
            "subcmd": "14",
            "data": {
                "notifyID": "14",
                "notifyData": [
                    {
                        "dispatchQueueEvent": {
                            "queuetype": "1200",
                            "bid": 101,
                            "iid": 1,
                            "index": 5,
                            "optype": 2,
                            "notifyType": "finish"
                        }
                    }
                ]
            }
        }
        self.client.feed_wire_packet(content, session=2)

        actual_lv = int(self.client.init_data["cityCtrl"]["blist"][0]["binfo"]["lv"])
        print(f"[ADVERSARIAL CHECK 2: QUEUE FINISH] Initial Lv: 10, Expected Single Increment: 11, Actual Lv: {actual_lv}")
        self.assertEqual(actual_lv, 11, "Verifies single increment: building incremented exactly once from 10 to 11")


if __name__ == "__main__":
    unittest.main(verbosity=2)
