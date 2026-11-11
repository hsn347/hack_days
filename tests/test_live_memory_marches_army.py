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


class TestNotificationTelemetryAndGatePrint(unittest.TestCase):
    """
    Tests notification ingestion reporting (merged/unhandled/missing/failed)
    and GateClient terminal trace output + march status consistency.
    """

    def test_ingest_packet_with_report_local_queue_and_edge_cases(self):
        engine = LiveMemoryEngine()

        # 1. Valid NOTIFY_LOCAL_QUEUE_SYNC using string msgType and fallback queueId
        pkt_ok = {
            "cmd": "1009",
            "subcmd": "1",
            "data": {
                "notifyID": "NOTIFY_LOCAL_QUEUE_SYNC",
                "notifyData": [
                    {"msgType": "1", "data": {"queueId": "Q-55", "status": 1, "moveLineType": 3, "to": {"x": 222, "y": 333, "mapType": 5}}}
                ],
            },
        }
        init_ref, rep = engine.ingest_packet_with_report(pkt_ok)
        self.assertIs(init_ref, engine.init_data)
        self.assertEqual(rep["overall_status"], "merged")
        self.assertEqual(rep["notify_status"], "merged")
        self.assertTrue(rep["is_notification"])
        self.assertTrue(rep["should_log"])
        self.assertEqual(rep["local_queues_count"], 1)
        self.assertIn("ADD(Q-55)", rep["notify_detail"]["ops"])
        self.assertIn("local_queues", rep["updated_state"])
        self.assertEqual(rep["updated_state"]["local_queues"][0]["queueId"], "Q-55")

        # 2. Unhandled notifyID
        _, rep_unhandled = engine.ingest_packet_with_report({
            "cmd": "1009",
            "subcmd": "1",
            "data": {"notifyID": "NOTIFY_UNKNOWN_CUSTOM_EVENT", "notifyData": {"foo": "bar"}},
        })
        self.assertEqual(rep_unhandled["notify_status"], "unhandled_notify")
        self.assertEqual(rep_unhandled["overall_status"], "unhandled_notify")
        self.assertTrue(rep_unhandled["should_log"])

        # 3. Missing notifyID on cmd=1009
        _, rep_missing = engine.ingest_packet_with_report({
            "cmd": "1009",
            "subcmd": "99",
            "data": {"someOtherKey": 123},
        })
        self.assertEqual(rep_missing["notify_status"], "missing_notify_id")
        self.assertEqual(rep_missing["overall_status"], "missing_notify_id")
        self.assertTrue(rep_missing["should_log"])

        # 4. Malformed NOTIFY_CITY causing ValueError inside handler -> clean failure report
        _, rep_fail = engine.ingest_packet_with_report({
            "cmd": "1009",
            "subcmd": "1",
            "data": {"notifyID": "9", "notifyData": [{"res": {"1001": "not-a-number"}}]},
        })
        self.assertEqual(rep_fail["notify_status"], "failed")
        self.assertEqual(rep_fail["overall_status"], "failed")
        self.assertIsNotNone(rep_fail["error"])
        self.assertIn("ValueError", rep_fail["error"])

        # 5. Controller-extracted local_queues merges cleanly and stays synced with local_queues_map
        _, rep_ctrl = engine.ingest_packet_with_report({
            "cmd": "1007",
            "subcmd": "1000",
            "data": {"local_queues": [{"id": "Q-99", "status": 2, "to": {"x": 10, "y": 20}}]},
        })
        self.assertEqual(rep_ctrl["overall_status"], "merged")
        self.assertTrue(rep_ctrl["local_queues_synced"])
        self.assertIn("Q-55", engine.local_queues_map)
        self.assertIn("Q-99", engine.local_queues_map)
        self.assertEqual(rep_ctrl["local_queues_count"], 2)

        # 6. Dict-wrapped notifyData & dict-valued ADD_ALL.data + msgType 11/21 acks
        engine2 = LiveMemoryEngine()
        self.assertFalse(engine2.local_queues_synced)
        _, rep_dict = engine2.ingest_packet_with_report({
            "cmd": "1009",
            "subcmd": "202",
            "data": {
                "notifyID": "NOTIFY_LOCAL_QUEUE_SYNC",
                "notifyData": {
                    "1": {
                        "msgType": "ADD_ALL",
                        "data": {
                            "MQ-1": {"status": 1, "to": {"x": 50, "y": 60}},
                            "MQ-2": {"id": "MQ-2", "status": 2, "to": {"x": 70, "y": 80}},
                        },
                    },
                    "2": {"msgType": 11},
                },
            },
        })
        self.assertEqual(rep_dict["overall_status"], "merged")
        self.assertTrue(engine2.local_queues_synced)
        self.assertIn("MQ-1", engine2.local_queues_map)
        self.assertIn("MQ-2", engine2.local_queues_map)
        self.assertIn("ADD_ALL(2)", rep_dict["notify_detail"]["ops"])
        self.assertIn("ACK(11)", rep_dict["notify_detail"]["ops"])

    def test_gate_client_dispatch_prints_compact_json_and_marches_status(self):
        import contextlib
        import io
        import json
        import struct
        from core.onemt_bot import xor_crypt
        from game_client import GateClient, GateCredentials

        creds = GateCredentials(
            kingdom_id="52",
            server_name="koh_game_7",
            gate_ip="127.0.0.1",
            gate_port=4000,
            sub_id="sub1",
            uid="10939075",
            secret=b"01234567",
        )
        creds.email = "shook124@gmail.com"
        client = GateClient(creds)

        # Giant unhandled NOTIFY_ALLIANCE packet should print just 1 short line (no huge JSON dump)
        alliance_payload = {
            "cmd": "1009",
            "subcmd": "3",
            "data": {
                "notifyID": "NOTIFY_ALLIANCE",
                "notifyData": [{"alliance": {"memberlist": list(range(1000, 1200))}}],
            },
        }
        raw_alliance = json.dumps(alliance_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        pkt_alliance = xor_crypt(raw_alliance) + b"\x01" + struct.pack(">I", 0)
        wire_alliance = struct.pack(">H", len(pkt_alliance)) + pkt_alliance

        payload = {
            "cmd": "1009",
            "subcmd": "1",
            "data": {
                "notifyID": "NOTIFY_LOCAL_QUEUE_SYNC",
                "notifyData": [
                    {
                        "msgType": 1,
                        "data": {
                            "id": "10939075-1",
                            "status": 1,
                            "moveLineType": 4,
                            "to": {"x": 512, "y": 640, "mapType": 7},
                            "data": {"heros": [5501001]},
                        },
                    }
                ],
            },
        }
        raw_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        pkt_body = xor_crypt(raw_json) + b"\x01" + struct.pack(">I", 0)
        wire_bytes = struct.pack(">H", len(pkt_body)) + pkt_body

        buf_alliance = io.StringIO()
        with contextlib.redirect_stdout(buf_alliance):
            client._buf = wire_alliance
            client._dispatch()
        out_alliance = buf_alliance.getvalue().strip()
        self.assertEqual(len(out_alliance.splitlines()), 1)
        self.assertIn("NOTIFY_ALLIANCE", out_alliance)
        self.assertNotIn("memberlist", out_alliance)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            client._buf = wire_bytes
            client._dispatch()

        printed = buf.getvalue()
        self.assertIn("[shook124]", printed)
        self.assertIn("NOTIFY_LOCAL_QUEUE_SYNC", printed)
        self.assertIn("تم الدمج بنجاح في الذاكرة الحية", printed)
        self.assertIn("10939075-1", printed)
        self.assertIn("sync=✅", printed)
        self.assertIn("مسيرات=1", printed)
        self.assertEqual(client._notify_count, 2)
        self.assertEqual(client._notify_merged_count, 1)
        self.assertEqual(client._notify_unhandled_count, 1)


class TestTaskLocalQueuesConsumers(unittest.TestCase):
    """
    Verifies that MarchManagerTask, ElfBossTask, GoldGatherTask, and RuinsTask
    correctly read direct march dicts (with or without nested data dicts) from
    conn.local_queues, avoid ghost marches from stale cached_packets, and
    perform backup 1007/1000 sync when local_queues_synced is False.
    """

    def _make_conn(self):
        class _FakeConn:
            def __init__(self):
                self.account = type("_Acc", (), {"email": "shook123@gmail.com"})()
                self.uid = "10939075"
                self.is_connected = True
                self.memory_engine = LiveMemoryEngine()
                self.init_data = self.memory_engine.init_data
                self.cached_packets = {}
                self.local_queues = []
                self.query_calls = []

            async def query(self, cmd, subcmd, data=None, timeout=5):
                self.query_calls.append((str(cmd), str(subcmd), data))
                return {"cmd": str(cmd), "subcmd": str(subcmd), "err": "0", "data": {}}

        return _FakeConn()

    def test_consumers_read_direct_marches_and_ignore_ghosts(self):
        import asyncio
        from tasks.base_task import BaseTask
        from tasks.march_manager import MarchManagerTask
        from tasks.elf_boss import ElfBossTask
        from tasks.gold_gather import GoldGatherTask
        from tasks.ruins import RuinsTask

        conn = self._make_conn()
        # Simulate live push ADD_ALL with gather march (nested data dict) + ruins march
        pkt = {
            "cmd": "1009",
            "subcmd": "202",
            "data": {
                "notifyID": "NOTIFY_LOCAL_QUEUE_SYNC",
                "notifyData": [
                    {
                        "msgType": 4,
                        "data": [
                            {
                                "id": "Q-GATHER-1",
                                "status": 2,
                                "moveLineType": 3,
                                "to": {"id": "100-200-5-2", "x": 100, "y": 200, "mapType": 5},
                                "data": {"resourceType": 1002, "heros": [5502001]},
                            },
                            {
                                "id": "Q-RUINS-2",
                                "status": 1,
                                "moveLineType": 4,
                                "to": {"id": "300-400-7-1", "x": 300, "y": 400, "mapType": 7},
                                "data": {"heros": [5501001]},
                            },
                        ],
                    }
                ],
            },
        }
        conn.memory_engine.ingest_packet(pkt)
        conn.local_queues = list(conn.memory_engine.local_queues_map.values())
        conn.cached_packets[("1009", "202")] = pkt

        mm = MarchManagerTask(conn, {})
        elf = ElfBossTask(conn, {})
        gold = GoldGatherTask(conn, {})
        ruins = RuinsTask(conn, {})

        async def _verify():
            cnt = await mm.get_active_marches_count()
            self.assertEqual(cnt, 2)
            # Zero-request: memory is already synced -> no extra 1007/1000 needed here
            self.assertEqual(conn.query_calls, [])

            res_types = await mm.get_active_gather_resource_types()
            self.assertEqual(res_types, {2})

            self.assertTrue(await mm.is_ruins_march_active())
            self.assertTrue(await ruins.is_ruins_march_active())

            elf._detect_busy_heroes()
            self.assertIn(5502001, elf._busy_heroes)
            self.assertIn(5501001, elf._busy_heroes)
            self.assertEqual(await elf._get_queue_id(), "Q-GATHER-1")

            t_ids, t_coords = gold._get_my_active_targets()
            self.assertEqual(t_ids, {"100-200-5-2", "300-400-7-1"})
            self.assertEqual(t_coords, {(100, 200), (300, 400)})
            self.assertIn(5502001, gold._busy)

            # Now simulate REMOVE_ALL while stale cached_packets STILL holds old packet -> NO GHOSTS!
            conn.memory_engine.handle_notify(202, [{"msgType": 5}])
            conn.local_queues = list(conn.memory_engine.local_queues_map.values())
            self.assertEqual(len(BaseTask.extract_live_march_queues(conn)), 0)
            self.assertEqual(await mm.get_active_marches_count(), 0)
            self.assertFalse(await ruins.is_ruins_march_active())

        asyncio.run(_verify())

    def test_backup_sync_triggers_when_unsynced(self):
        import asyncio
        from tasks.march_manager import MarchManagerTask

        conn = self._make_conn()
        self.assertFalse(conn.memory_engine.local_queues_synced)
        mm = MarchManagerTask(conn, {})

        async def _verify_sync():
            await mm.get_active_marches_count()
            self.assertTrue(any(c == ("1007", "1000", {}) for c in conn.query_calls))

        asyncio.run(_verify_sync())


class TestOwnCastleQueueIsolation(unittest.TestCase):
    """اختبارات عزل مسيرات القلعة (uid) عن مسيرات التحالف واللاعبين الآخرين عبر كامل المنظومة."""

    def _build_gate_client_like_live(self, my_uid: str = "10939063"):
        from core.live_memory import LiveMemoryEngine
        from game_client import GateClient

        gate = object.__new__(GateClient)
        gate.creds = type("C", (), {"email": "shook123@gmail.com", "uid": my_uid})()
        gate.uid = my_uid
        gate.subid = "1"
        gate.secret = ""
        gate.host = "127.0.0.1"
        gate.port = 4000
        gate.memory_engine = LiveMemoryEngine(owner_uid=my_uid)
        gate.memory_engine.ingest_packet(
            {
                "cmd": "1001",
                "subcmd": "1",
                "err": "0",
                "data": {"lordInfoCtrl": {"base": {"uid": int(my_uid)}}},
            }
        )
        gate.init_data = gate.memory_engine.init_data
        gate.local_queues_map = gate.memory_engine.local_queues_map
        gate.heroes = []
        gate.army_troops = []
        gate.all_troops = {}
        gate.troops = {}
        gate.local_queues = []
        gate.queued_events = []
        gate.cached_packets = {}
        gate._pending = {}
        gate._listeners = []
        gate._packet_listeners = []
        gate._notifies = {}
        gate._buf = b""
        gate.spy_mode = False
        gate.memory_terminal_trace = True
        gate._last_notify_at = 0.0
        gate._notify_count = 0
        gate._notify_merged_count = 0
        gate._notify_failed_count = 0
        gate._notify_unhandled_count = 0
        gate._printed_lines = []
        gate._safe_terminal_print = gate._printed_lines.append
        return gate

    @staticmethod
    def _feed_gate_packet(gate, packet):
        _, report = gate.memory_engine.ingest_packet_with_report(packet)
        gate.local_queues = gate.memory_engine.get_own_local_queues()
        return report

    def test_live_scenario_filters_alliance_marches_across_engine_and_tasks(self):
        import asyncio
        import time
        from tasks.base_task import BaseTask
        from tasks.march_manager import MarchManagerTask
        from tasks.march_coordinator import MarchCoordinatorTask
        from tasks.gold_gather import GoldGatherTask
        from tasks.ruins import RuinsTask

        now = int(time.time())
        gate = self._build_gate_client_like_live("10939063")

        # نفس سيناريو التيرمنال الحقيقي: 2 للقلعة + 3 للاعبين آخرين بالتحالف
        notify_packet = {
            "cmd": "1009",
            "err": "0",
            "data": {
                "notifyID": "NOTIFY_LOCAL_QUEUE_SYNC",
                "notifyData": [
                    {
                        "msgType": 4,
                        "data": [
                            {
                                "id": "9048282-10432",
                                "status": 1,
                                "type": 3,
                                "moveLineType": 4,  # مسيرة أطلال للاعب آخر
                                "to": {"x": 281, "y": 352, "mapType": 5},
                                "endTime": now + 10,
                                "heros": [99001],
                            },
                            {
                                "id": "10939063-610",
                                "status": 2,
                                "type": 3,
                                "to": {"id": "7771", "x": 370, "y": 310, "mapType": 5, "subMapType": 5},
                                "endTime": now + 150,
                                "from": {"uid": "10939063", "heros": {"10939063": [{"id": 5501001}, {"id": 5501002}]}},
                            },
                            {
                                "id": "2488608-30375",
                                "status": 1,
                                "type": 3,
                                "to": {"id": "8882", "x": 281, "y": 352, "mapType": 5, "subMapType": 4},
                                "endTime": now + 20,
                            },
                            {
                                "id": "2469590-77439",
                                "status": 2,
                                "type": 3,
                                "to": {"id": "8883", "x": 281, "y": 352, "mapType": 5, "subMapType": 1},
                                "endTime": now + 30,
                            },
                            {
                                "id": "10939063-613",
                                "status": 1,
                                "type": 1,
                                "to": {"id": "7772", "x": 395, "y": 319, "mapType": 6},
                                "endTime": now + 120,
                                "heros": [5501009, 5501010],
                            },
                        ],
                    }
                ],
            },
        }
        report = self._feed_gate_packet(gate, notify_packet)
        gate._print_live_memory_report(notify_packet, "1009", "202", 0, report)

        # 1. الذاكرة الحية و GateClient يعرضان مسيرتي قلعتنا فقط رغم وجود 5 ببث السيرفر
        own_q, other_q = gate.memory_engine.get_local_queues_breakdown()
        self.assertEqual(len(own_q), 2)
        self.assertEqual(len(other_q), 3)
        self.assertEqual(len(gate.local_queues), 2)
        self.assertEqual(len(gate.local_queues_map), 5)
        self.assertEqual(
            {q["id"] for q in gate.local_queues},
            {"10939063-610", "10939063-613"},
        )
        summary_lines = gate._format_march_summary_lines(gate.local_queues, report)
        self.assertIn("مسيرات قلعتي (2, بث كلي=5 (لغيري=3))", summary_lines[0])
        self.assertTrue(all("9048282" not in ln and "2488608" not in ln and "2469590" not in ln for ln in summary_lines))
        self.assertTrue(any("10939063-610" in ln for ln in summary_lines))
        self.assertTrue(gate._printed_lines and "مسيرات=2 (لغيري=3)" in gate._printed_lines[0])

        # بناء غلاف اتصال خفيف للمهام
        class _TaskConn:
            def __init__(self, g):
                self._gate = g
                self.account = type("Acc", (), {"email": "shook123@gmail.com", "uid": g.uid})()
                self.uid = g.uid
                self.init_data = g.init_data
                self.memory_engine = g.memory_engine
                self.cached_packets = {1: notify_packet}
                self.kingdom_id = 52

            @property
            def local_queues(self):
                return self._gate.local_queues

            def add_packet_listener(self, cb):
                pass

            def remove_packet_listener(self, cb):
                pass

            async def query(self, cmd, subcmd, data=None, timeout=10.0):
                return {"err": "0", "data": {}}

        conn = _TaskConn(gate)

        # 2. MarchManagerTask يحسب مسيرتين فقط ومورد 5 فقط
        mm = MarchManagerTask(conn, {})
        count = asyncio.run(mm.get_active_marches_count())
        gather_types = asyncio.run(mm.get_active_gather_resource_types())
        self.assertEqual(count, 2)
        self.assertEqual(gather_types, {5})

        # 3. MarchCoordinatorTask يتجاهل مسيرة اللاعب الآخر الأقصر (10ث) ويأخذ أقرب مسيرة لقلعتنا (~120ث)
        mc = MarchCoordinatorTask(conn, {})
        nearest = mc._get_nearest_march_remaining_seconds()
        self.assertGreaterEqual(nearest, 100.0)
        self.assertLessEqual(nearest, 125.0)

        # 4. GoldGatherTask يستخرج أهدافنا فقط وأبطال from.heros دون أبطال أو أهداف اللاعبين الآخرين
        gg = GoldGatherTask(conn, {})
        gg._busy = set()
        target_ids, target_coords = gg._get_my_active_targets()
        self.assertEqual(target_ids, {"7771", "7772"})
        self.assertEqual(target_coords, {(370, 310), (395, 319)})
        self.assertEqual(gg._busy, {5501001, 5501002, 5501009, 5501010})

        # 5. RuinsTask لا تعتبر مسيرة اللاعب الآخر moveLineType=4 مسيرة أطلال خاصة بنا
        ruins = RuinsTask(conn, {})
        self.assertFalse(asyncio.run(ruins.is_ruins_march_active()))

        # وعند إضافة مسيرة أطلال تابعة لقلعتنا تصبح True
        self._feed_gate_packet(gate, {
            "cmd": "1009",
            "err": "0",
            "data": {
                "notifyID": "NOTIFY_LOCAL_QUEUE_SYNC",
                "notifyData": [
                    {
                        "msgType": 1,
                        "data": {"id": "10939063-614", "status": 1, "moveLineType": 4, "to": {"x": 300, "y": 300, "mapType": 7}},
                    }
                ],
            },
        })
        self.assertTrue(asyncio.run(ruins.is_ruins_march_active()))
        self.assertEqual(BaseTask.extract_queue_hero_ids({"from": {"heros": {"10939063": [{"id": 5501001}]}}}), {5501001})

    def test_synthetic_queues_without_owner_uid_remain_compatible(self):
        from core.live_memory import LiveMemoryEngine, is_own_march_queue

        engine = LiveMemoryEngine(owner_uid="10939063")
        engine.ingest_packet({
            "cmd": "1009",
            "err": "0",
            "data": {
                "notifyID": "NOTIFY_LOCAL_QUEUE_SYNC",
                "notifyData": [{"msgType": 4, "data": [{"id": "q_synthetic", "status": 1}]}],
            },
        })
        self.assertTrue(is_own_march_queue({"id": "q_synthetic", "status": 1}, "10939063"))
        self.assertFalse(is_own_march_queue({"id": "q_other", "uid": 9048282, "status": 1}, "10939063"))
        self.assertFalse(is_own_march_queue({"id": "q_other_from", "from": {"uid": "9048282"}, "status": 1}, "10939063"))
        self.assertEqual(len(engine.get_own_local_queues()), 1)


if __name__ == "__main__":
    unittest.main()
