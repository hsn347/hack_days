# -*- coding: utf-8 -*-
r"""
tests/test_live_memory_marches_army.py — Comprehensive QA Test Suite for Marches & Army Synchronization
══════════════════════════════════════════════════════════════════════════════════════════════════════
Author: Agent 16 (Marches & Army Live QA Agent)
Roles: Reviewer, Adversarial Critic
Workspace: e:\osmanli

Coverage Matrix:
  1. local_queues March Line Sync:
     - NOTIFY_LOCAL_QUEUE_SYNC (Subcmd 202)
     - gQueueSyncMsgType:
         * ADD (1): adds new march line
         * UPDATE (3): updates march line position, status, time
         * REMOVE (2): removes march line on arrival/return
         * ADD_ALL (4): full list synchronization
         * REMOVE_ALL (5): wipes all active marches
     - Zero duplicates verification under repeated additions
     - Zero missed prunings verification upon march completion
     - Numeric integer vs string ID handling
     - Ingress packet routing via CMD 1009 & direct handle_notify
     - Reference integrity between GameConnection and LiveMemoryEngine

  2. armyCtrl State Sync:
     - Initial login payload ingestion
     - NOTIFY_ARMY (Subcmd 15) with v.armyInfo
     - Proper synchronization of totalArmy, woundedArmy, trainArmy, troop counts
     - Troop delta updates (recruiting, casualty, healing)
     - Adversarial edge case: empty container behavior (hospital cleared, train finished)
     - Ingress packet routing via CMD 1009
     - Memory readiness gate validation (is_memory_ready)
"""

from __future__ import annotations

import copy
import os
import sys
import unittest
from typing import Any, Dict, List

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.live_memory import (
    LiveMemoryEngine,
    smart_deep_merge,
    ALLOWED_CONTROLLERS,
    CRITICAL_STARTUP_CONTROLLERS,
)


class TestMarchesQueueSync(unittest.TestCase):
    """
    QA Test Suite for local_queues march synchronization (NOTIFY_LOCAL_QUEUE_SYNC, Subcmd 202).
    Verifies gQueueSyncMsgType operations (ADD=1, REMOVE=2, UPDATE=3, ADD_ALL=4, REMOVE_ALL=5).
    """

    def setUp(self):
        self.engine = LiveMemoryEngine()

    def test_local_queue_sync_add_single_and_multiple(self):
        """
        Verify msgType 1 (ADD) inserts new march lines into both
        local_queues_map and init_data['local_queues'].
        """
        # March 1: Resource gathering march line
        march_1 = {
            "id": "1001",
            "uid": 123456,
            "queueType": 1221,  # moveline_map
            "status": 1,        # Marching to destination
            "toPos": {"x": 350, "y": 420},
            "statusStartTime": 1700000000,
            "statusEndTime": 1700000300,
            "armyCount": 50000,
        }

        # March 2: Monster rally march line
        march_2 = {
            "id": "1002",
            "uid": 123456,
            "queueType": 1222,  # moveline_hall_or_war
            "status": 1,
            "toPos": {"x": 380, "y": 410},
            "statusStartTime": 1700000100,
            "statusEndTime": 1700000450,
            "armyCount": 85000,
        }

        # Push notification containing 2 ADD events
        notify_payload = [
            {"msgType": 1, "data": march_1},
            {"msgType": 1, "data": march_2},
        ]

        self.engine.handle_notify(202, notify_payload)

        # Assert map contains both marches
        self.assertEqual(len(self.engine.local_queues_map), 2)
        self.assertIn("1001", self.engine.local_queues_map)
        self.assertIn("1002", self.engine.local_queues_map)

        # Assert init_data['local_queues'] is strictly mirrored
        mirrored = self.engine.init_data.get("local_queues", [])
        self.assertEqual(len(mirrored), 2)
        m_ids = {str(m.get("id")) for m in mirrored}
        self.assertEqual(m_ids, {"1001", "1002"})

    def test_local_queue_sync_update_status_and_position(self):
        """
        Verify msgType 3 (UPDATE) correctly modifies existing march details
        (e.g., status transition from marching to gathering, or new target/time).
        """
        # 1. Add initial march
        initial_march = {
            "id": "2001",
            "queueType": 1221,
            "status": 1,  # Marching
            "toPos": {"x": 500, "y": 500},
            "statusStartTime": 1700000000,
            "statusEndTime": 1700000200,
            "speed": 100,
        }
        self.engine.handle_notify(202, [{"msgType": 1, "data": initial_march}])

        # 2. Update march: reached destination, now gathering (status = 2)
        update_march = {
            "id": "2001",
            "status": 2,  # Gathering
            "statusStartTime": 1700000200,
            "statusEndTime": 1700003800,  # 1 hour gather
            "collectedRes": 15000,
        }
        self.engine.handle_notify(202, [{"msgType": 3, "data": update_march}])

        # Assert updated values merged in place
        march_in_map = self.engine.local_queues_map.get("2001")
        self.assertIsNotNone(march_in_map)
        self.assertEqual(march_in_map["status"], 2)
        self.assertEqual(march_in_map["collectedRes"], 15000)
        # Verify untouched original fields preserved
        self.assertEqual(march_in_map["queueType"], 1221)
        self.assertEqual(march_in_map["toPos"], {"x": 500, "y": 500})
        self.assertEqual(march_in_map["speed"], 100)

        # Verify mirrored in init_data['local_queues']
        local_q = self.engine.init_data["local_queues"]
        self.assertEqual(len(local_q), 1)
        self.assertEqual(local_q[0]["status"], 2)
        self.assertEqual(local_q[0]["collectedRes"], 15000)

    def test_local_queue_sync_remove_on_arrival_zero_missed_pruning(self):
        """
        Verify msgType 2 (REMOVE) deletes completed or returned march line,
        leaving zero leftover / missed prunings.
        """
        # Seed 3 active marches
        seed_payload = [
            {"msgType": 1, "data": {"id": "3001", "name": "Gather Wood"}},
            {"msgType": 1, "data": {"id": "3002", "name": "Attack Boss"}},
            {"msgType": 1, "data": {"id": "3003", "name": "Scout Enemy"}},
        ]
        self.engine.handle_notify(202, seed_payload)
        self.assertEqual(len(self.engine.local_queues_map), 3)

        # March 3002 arrives back at castle -> REMOVE
        remove_payload = [{"msgType": 2, "data": {"id": "3002"}}]
        self.engine.handle_notify(202, remove_payload)

        # Assert 3002 is completely pruned from map and list
        self.assertEqual(len(self.engine.local_queues_map), 2)
        self.assertNotIn("3002", self.engine.local_queues_map)
        self.assertIn("3001", self.engine.local_queues_map)
        self.assertIn("3003", self.engine.local_queues_map)

        # Assert init_data['local_queues'] reflects exact remaining items
        mirrored = self.engine.init_data["local_queues"]
        self.assertEqual(len(mirrored), 2)
        self.assertFalse(any(m["id"] == "3002" for m in mirrored), "March 3002 was not pruned!")

        # Remove remaining two marches
        self.engine.handle_notify(202, [
            {"msgType": 2, "data": {"id": "3001"}},
            {"msgType": 2, "data": {"id": "3003"}},
        ])
        self.assertEqual(len(self.engine.local_queues_map), 0)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 0)

    def test_local_queue_sync_zero_duplicates_on_repeated_add(self):
        """
        Verify zero duplicates even if identical or slightly modified ADD
        messages are received repeatedly for the same march ID.
        """
        march = {"id": "4001", "status": 1, "army": 10000}

        # Send ADD 5 times
        for _ in range(5):
            self.engine.handle_notify(202, [{"msgType": 1, "data": copy.deepcopy(march)}])

        # Assert map and list length is strictly 1
        self.assertEqual(len(self.engine.local_queues_map), 1)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 1)
        self.assertEqual(self.engine.init_data["local_queues"][0]["id"], "4001")

    def test_local_queue_sync_add_all_and_remove_all(self):
        """
        Verify msgType 4 (ADD_ALL) replaces existing marches completely,
        and msgType 5 (REMOVE_ALL) clears the entire march list.
        """
        # Initially have march 5001
        self.engine.handle_notify(202, [{"msgType": 1, "data": {"id": "5001", "type": "old"}}])
        self.assertEqual(len(self.engine.local_queues_map), 1)

        # ADD_ALL with 3 completely new marches
        add_all_payload = [
            {
                "msgType": 4,
                "data": [
                    {"id": "6001", "name": "March A"},
                    {"id": "6002", "name": "March B"},
                    {"id": "6003", "name": "March C"},
                ]
            }
        ]
        self.engine.handle_notify(202, add_all_payload)

        # Old march 5001 must be gone; exactly 3 new marches exist
        self.assertEqual(len(self.engine.local_queues_map), 3)
        self.assertNotIn("5001", self.engine.local_queues_map)
        self.assertIn("6001", self.engine.local_queues_map)
        self.assertIn("6002", self.engine.local_queues_map)
        self.assertIn("6003", self.engine.local_queues_map)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 3)

        # REMOVE_ALL (msgType 5)
        self.engine.handle_notify(202, [{"msgType": 5}])
        self.assertEqual(len(self.engine.local_queues_map), 0)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 0)

    def test_local_queue_sync_numeric_and_string_id_normalization(self):
        """
        Verify integer IDs in data are converted to strings without creating
        dual integer/string keys or failing to remove.
        """
        # ADD with integer ID: 77777
        self.engine.handle_notify(202, [{"msgType": 1, "data": {"id": 77777, "status": 1}}])
        self.assertIn("77777", self.engine.local_queues_map)

        # UPDATE with string ID: "77777"
        self.engine.handle_notify(202, [{"msgType": 3, "data": {"id": "77777", "status": 2}}])
        self.assertEqual(self.engine.local_queues_map["77777"]["status"], 2)

        # REMOVE with integer ID: 77777
        self.engine.handle_notify(202, [{"msgType": 2, "data": {"id": 77777}}])
        self.assertNotIn("77777", self.engine.local_queues_map)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 0)

    def test_local_queue_packet_routing_variants(self):
        """
        Verify packet routing through various network envelopes:
          1. Direct handle_notify with int 202
          2. Direct handle_notify with string "202"
          3. Direct handle_notify with symbolic name "NOTIFY_LOCAL_QUEUE_SYNC"
          4. Full network packet with cmd="1009", data={"notifyID": 202, "notifyData": [...]}
        """
        # 1. Int 202
        self.engine.handle_notify(202, [{"msgType": 1, "data": {"id": "R1"}}])
        self.assertIn("R1", self.engine.local_queues_map)

        # 2. String "202"
        self.engine.handle_notify("202", [{"msgType": 1, "data": {"id": "R2"}}])
        self.assertIn("R2", self.engine.local_queues_map)

        # 3. Symbolic name
        self.engine.handle_notify("NOTIFY_LOCAL_QUEUE_SYNC", [{"msgType": 1, "data": {"id": "R3"}}])
        self.assertIn("R3", self.engine.local_queues_map)

        # 4. Ingest full CMD 1009 packet
        packet = {
            "cmd": "1009",
            "data": {
                "notifyID": 202,
                "notifyData": [{"msgType": 1, "data": {"id": "R4"}}]
            }
        }
        self.engine.ingest_packet(packet)
        self.assertIn("R4", self.engine.local_queues_map)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 4)

    def test_adversarial_remove_nonexistent_march_does_not_crash(self):
        """
        Adversarial test: Server sends REMOVE for a march that was never tracked
        or was already removed. Must not throw KeyError or corrupt state.
        """
        self.engine.handle_notify(202, [{"msgType": 2, "data": {"id": "nonexistent_999"}}])
        self.assertEqual(len(self.engine.local_queues_map), 0)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 0)

    def test_adversarial_malformed_queue_data_graceful_handling(self):
        """
        Adversarial test: Server sends corrupted / empty messages in queue sync.
        Must handle gracefully without exception.
        """
        self.engine.handle_notify(202, None)
        self.engine.handle_notify(202, [])
        self.engine.handle_notify(202, [None, {}, "corrupted"])
        self.engine.handle_notify(202, [{"msgType": 1, "data": None}])
        self.engine.handle_notify(202, [{"msgType": 1, "data": {}}])  # No id
        self.engine.handle_notify(202, [{"msgType": 999, "data": {"id": "invalid_type"}}])
        self.assertEqual(len(self.engine.local_queues_map), 0)
        self.assertEqual(len(self.engine.init_data["local_queues"]), 0)


class TestArmyStateSync(unittest.TestCase):
    """
    QA Test Suite for armyCtrl state synchronization (NOTIFY_ARMY, Subcmd 15).
    Verifies totalArmy, woundedArmy, trainArmy, and troop counts.
    """

    def setUp(self):
        self.engine = LiveMemoryEngine()

    def test_army_sync_initial_login_payload(self):
        """
        Verify armyCtrl initial payload from login or query 1005/1
        is correctly ingested and whitelisted.
        """
        login_packet = {
            "cmd": "1005",
            "subcmd": "1",
            "data": {
                "retdata": {
                    "armyCtrl": {
                        "totalArmy": {
                            "10101": "5000",
                            "10205": "3200",
                            "10308": "1500",
                        },
                        "woundedArmy": {
                            "10101": "120",
                            "10205": "45",
                        },
                        "trainArmy": {
                            "103": {"10101": "200"}
                        },
                        "singleTrainAddInfo": {"103": "1"},
                        "compileLimit": 4,
                    }
                }
            }
        }
        self.engine.ingest_packet(login_packet)

        army = self.engine.init_data.get("armyCtrl", {})
        self.assertIsNotNone(army)
        self.assertEqual(int(army["totalArmy"]["10101"]), 5000)
        self.assertEqual(int(army["totalArmy"]["10205"]), 3200)
        self.assertEqual(int(army["totalArmy"]["10308"]), 1500)
        self.assertEqual(int(army["woundedArmy"]["10101"]), 120)
        self.assertEqual(int(army["woundedArmy"]["10205"]), 45)
        self.assertEqual(int(army["trainArmy"]["103"]["10101"]), 200)
        self.assertEqual(army["compileLimit"], 4)

    def test_army_sync_v_army_info_push_notification(self):
        """
        Verify NOTIFY_ARMY push notification carrying v.armyInfo
        updates totalArmy, woundedArmy, trainArmy in live memory.
        """
        # Pre-populate base state
        self.engine.init_data["armyCtrl"] = {
            "totalArmy": {"10101": "5000", "10205": "3200"},
            "woundedArmy": {"10101": "120"},
            "trainArmy": {},
            "compileLimit": 4,
        }

        # Server sends NOTIFY_ARMY (15) with updated armyInfo
        notify_payload = [
            {
                "armyInfo": {
                    "totalArmy": {
                        "10101": "5500",  # 500 recruited
                        "10205": "3200",
                        "10410": "800",   # New siege unit added
                    },
                    "woundedArmy": {
                        "10101": "200",   # More wounded
                        "10205": "50",
                    },
                    "trainArmy": {
                        "104": {"10205": "300"}  # New training in cavalry stable 104
                    },
                    "singleTrainAddInfo": {"104": "1"},
                    "compileLimit": 4,
                },
                "filterQueueId": "987654",
                "notifyType": "complieLimit",
                "limit": 5,
            }
        ]

        self.engine.handle_notify(15, notify_payload)

        army = self.engine.init_data["armyCtrl"]
        # Verify totalArmy updated and new troop type added
        self.assertEqual(army["totalArmy"]["10101"], "5500")
        self.assertEqual(army["totalArmy"]["10205"], "3200")
        self.assertEqual(army["totalArmy"]["10410"], "800")

        # Verify woundedArmy updated
        self.assertEqual(army["woundedArmy"]["10101"], "200")
        self.assertEqual(army["woundedArmy"]["10205"], "50")

        # Verify trainArmy updated
        self.assertEqual(army["trainArmy"]["104"]["10205"], "300")

    def test_army_sync_routing_variants(self):
        """
        Verify NOTIFY_ARMY routing through integer 15, string "15",
        symbolic name "NOTIFY_ARMY", and CMD 1009 network envelope.
        """
        # 1. Direct handle_notify(15)
        self.engine.handle_notify(15, [{"armyInfo": {"totalArmy": {"101": "100"}}}])
        self.assertEqual(self.engine.init_data["armyCtrl"]["totalArmy"]["101"], "100")

        # 2. String "15"
        self.engine.handle_notify("15", [{"armyInfo": {"totalArmy": {"101": "200"}}}])
        self.assertEqual(self.engine.init_data["armyCtrl"]["totalArmy"]["101"], "200")

        # 3. Symbolic name "NOTIFY_ARMY"
        self.engine.handle_notify("NOTIFY_ARMY", [{"armyInfo": {"totalArmy": {"101": "300"}}}])
        self.assertEqual(self.engine.init_data["armyCtrl"]["totalArmy"]["101"], "300")

        # 4. CMD 1009 packet
        pkt = {
            "cmd": "1009",
            "data": {
                "notifyID": 15,
                "notifyData": [{"armyInfo": {"totalArmy": {"101": "400"}}}]
            }
        }
        self.engine.ingest_packet(pkt)
        self.assertEqual(self.engine.init_data["armyCtrl"]["totalArmy"]["101"], "400")

    def test_army_readiness_gate_validation(self):
        """
        Verify is_memory_ready strictly inspects armyCtrl.
        Asserts missing armyCtrl or armyCtrl missing army data is flagged.
        """
        # State with all critical controllers except armyCtrl
        valid_mock_state = {
            "cityCtrl": {"blist": [{"index": "1"}], "reslist": {"1001": 100}},
            "lordInfoCtrl": {"base": {"uid": 12345}},
            "queueCtrl": {},
            "heroCtrl": [],
            "backpackCtrl": {},
        }

        # 1. Completely missing armyCtrl -> Not ready
        self.engine.init_data = copy.deepcopy(valid_mock_state)
        ready, missing = self.engine.is_memory_ready()
        self.assertFalse(ready)
        self.assertIn("armyCtrl", missing)

        # 2. armyCtrl is empty dict -> reports armyCtrl.data
        self.engine.init_data["armyCtrl"] = {}
        ready, missing = self.engine.is_memory_ready()
        self.assertFalse(ready)
        self.assertIn("armyCtrl.data", missing)

        # 3. armyCtrl contains totalArmy -> Passes
        self.engine.init_data["armyCtrl"] = {"totalArmy": {"10101": "1000"}}
        ready, missing = self.engine.is_memory_ready()
        self.assertTrue(ready)
        self.assertEqual(missing, [])

    def test_adversarial_empty_wounded_and_train_clearing(self):
        """
        ADVERSARIAL STRESS TEST:
        When all wounded troops are healed, server sends woundedArmy: {}.
        When training finishes, server sends trainArmy: {}.
        We test the behavior of LiveMemoryEngine when receiving empty dictionaries
        for woundedArmy and trainArmy.
        """
        # Setup initial state with wounded and training troops
        self.engine.init_data["armyCtrl"] = {
            "totalArmy": {"10101": "5000"},
            "woundedArmy": {"10101": "500"},
            "trainArmy": {"103": {"10101": "200"}},
        }

        # Server sends update indicating all healed (woundedArmy={}) and training completed (trainArmy={})
        healed_notification = [
            {
                "armyInfo": {
                    "totalArmy": {"10101": "5700"},
                    "woundedArmy": {},
                    "trainArmy": {},
                }
            }
        ]
        self.engine.handle_notify(15, healed_notification)

        army = self.engine.init_data["armyCtrl"]
        self.assertEqual(army["totalArmy"]["10101"], "5700")

        # VERIFICATION OF REMEDIATION:
        # woundedArmy and trainArmy are explicitly replaced when empty dicts arrive.
        self.assertEqual(army["woundedArmy"], {},
                         "woundedArmy is safely cleared when server sends empty dict")
        self.assertEqual(army["trainArmy"], {},
                         "trainArmy is safely cleared when server sends empty dict")

    def test_adversarial_add_all_breaks_connection_local_queues_map_reference(self):
        """
        ADVERSARIAL STRESS TEST:
        In GameConnection.__init__:
            self.local_queues_map: dict = self.memory_engine.local_queues_map
        In LiveMemoryEngine._handle_notify_local_queue (msgType 4 / ADD_ALL):
            Mutating self.local_queues_map in-place via .clear() and .update() preserves
            the reference held by GameConnection.local_queues_map!
        """
        # Simulate connection binding
        conn_local_queues_map = self.engine.local_queues_map

        # Initial ADD
        self.engine.handle_notify(202, [{"msgType": 1, "data": {"id": "1001", "name": "Old March"}}])
        self.assertIn("1001", conn_local_queues_map)

        # Server sends ADD_ALL with fresh marches
        self.engine.handle_notify(202, [{
            "msgType": 4,
            "data": [
                {"id": "2001", "name": "New March A"},
                {"id": "2002", "name": "New March B"},
            ]
        }])

        # Verify engine.local_queues_map has new marches
        self.assertIn("2001", self.engine.local_queues_map)
        self.assertIn("2002", self.engine.local_queues_map)
        self.assertNotIn("1001", self.engine.local_queues_map)

        # VERIFICATION OF REMEDIATION:
        # conn_local_queues_map remains BOUND to engine.local_queues_map!
        is_detached = (conn_local_queues_map is not self.engine.local_queues_map)
        self.assertFalse(is_detached, "In-place update preserves the shared dictionary reference!")
        self.assertNotIn("1001", conn_local_queues_map, "conn_local_queues_map purged deleted march!")
        self.assertIn("2001", conn_local_queues_map, "conn_local_queues_map received new marches!")


if __name__ == "__main__":
    unittest.main()
