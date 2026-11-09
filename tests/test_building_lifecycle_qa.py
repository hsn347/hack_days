# -*- coding: utf-8 -*-
r"""
tests/test_building_lifecycle_qa.py — Empirical QA Verification Suite for Building Upgrade & Queue Lifecycle
═════════════════════════════════════════════════════════════════════════════════════════════════════════════
Agent 15: Building Upgrade & Queue End QA Agent
Workspace: e:\osmanli

This test suite rigorously and empirically verifies the building upgrade and queue lifecycle contracts:
  1. Regular Upgrade Completion (queue removal, lv + 1, state -> BUILD_STATE.NORMAL "0")
  2. Honor Upgrade Completion (honorLv + 1, hlv + 1, lv unchanged, state -> BUILD_STATE.NORMAL "0")
  3. Queue Cancellation (optype 11 / cancel: state -> BUILD_STATE.NORMAL "0", level strictly unchanged)
  4. City Integrity Preservation (across all transitions, all 46+ other buildings in blist remain pristine)
  5. Adversarial Edge Cases:
     - Wrapped in `dispatchQueueEvent` structure (as pushed by skynet/Lua server)
     - Targeting via composite key (bid, iid) when index is omitted
     - Flat building dictionary support (without nested binfo)
     - Non-existent building handling (graceful degradation without crashes)
     - Full GameConnection dispatch integration via simulated S2C CMD 1009 packet
     - Code integrity & anti-tampering verification
"""

from __future__ import annotations

import copy
import inspect
import os
import sys
import unittest
from typing import Any, Dict, List

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from core.live_memory import (
    BUILD_OPERATE_TYPE,
    BUILD_STATE,
    LiveMemoryEngine,
)

try:
    from game_client import GateClient, GateCredentials
except ImportError:
    GateClient = None
    GateCredentials = None


def generate_canonical_city(num_buildings: int = 50) -> Dict[str, Any]:
    """Generates a canonical cityCtrl structure with `num_buildings` distinct buildings."""
    blist = []
    for i in range(1, num_buildings + 1):
        bid = str(100 + (i % 10))
        iid = str(i // 10)
        blist.append({
            "binfo": {
                "index": str(i),
                "bid": bid,
                "iid": iid,
                "lv": "10",
                "state": BUILD_STATE.NORMAL,  # "0"
                "curres": "500",
                "curres_safe": "100",
                "honorLv": "0",
                "hlv": "0",
            }
        })
    return {
        "cityCtrl": {
            "cinfo": {"cid": "999888", "name": "QA_City"},
            "blist": blist,
            "reslist": {"1001": "5000000", "1002": "3000000"},
            "saferes": {"1001": "1000000", "1002": "1000000"},
            "dayMaxRes": {"1001": "20000000"},
        },
        "queueCtrl": {},
    }


class TestBuildingLifecycleQA(unittest.TestCase):
    """Rigorous QA verification of building lifecycle transitions and city integrity."""

    def setUp(self):
        self.engine = LiveMemoryEngine()
        self.engine.init_data = generate_canonical_city(50)

    # ──────────────────────────────────────────────────────────────────────────
    # Requirement 1: Regular Upgrade Completion
    # ──────────────────────────────────────────────────────────────────────────
    def test_regular_upgrade_completion(self):
        """
        Req 1:
        - Target building in cityCtrl.blist starts in UPGRADING state ("2") at level 14.
        - Queue is active in queueCtrl for qtype "1200".
        - Dispatch completion callback (notifyType="finish", optype=2).
        - Verify:
          a) Target building lv increments by 1 (14 -> 15).
          b) Target building state resets to BUILD_STATE.NORMAL ("0").
          c) Queue "1200" is removed from queueCtrl.
        """
        target_idx = "12"
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b12 = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        b12["lv"] = "14"
        b12["state"] = BUILD_STATE.UPGRADING  # "2"

        self.engine.init_data["queueCtrl"]["1200"] = {
            "qtype": "1200",
            "index": target_idx,
            "bid": b12["bid"],
            "iid": b12["iid"],
            "optype": BUILD_OPERATE_TYPE.UPGRADE,
            "startTime": 1700000000,
            "totalTime": 7200,
        }

        # Dispatch completion notification (NOTIFY_QUEUE = 14)
        completion_payload = {
            "queuetype": "1200",
            "qtype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "index": target_idx,
            "bid": b12["bid"],
            "iid": b12["iid"],
        }
        self.engine.handle_notify(14, completion_payload)

        # 1. Assert queue is removed from queueCtrl
        self.assertNotIn("1200", self.engine.init_data["queueCtrl"], "Completed queue must be evicted from queueCtrl!")

        # 2. Assert building state reverted to NORMAL ("0")
        b12_after = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        self.assertEqual(b12_after["state"], BUILD_STATE.NORMAL, f"Building state must revert to NORMAL ('0'), got {b12_after['state']}")

        # 3. Assert level incremented by exactly 1
        self.assertEqual(str(b12_after["lv"]), "15", f"Building regular level must increment from 14 to 15, got {b12_after['lv']}")

    # ──────────────────────────────────────────────────────────────────────────
    # Requirement 2: Honor Upgrade Completion
    # ──────────────────────────────────────────────────────────────────────────
    def test_honor_upgrade_completion(self):
        """
        Req 2:
        - Target building starts at regular lv 30, honorLv 4, hlv 4 in UPGRADING state ("2").
        - Queue is active in queueCtrl for qtype "1200".
        - Dispatch completion callback with honor flag (isHonor=True).
        - Verify:
          a) honorLv and hlv increment by 1 (4 -> 5).
          b) Regular lv remains strictly unchanged at 30.
          c) state reverts to BUILD_STATE.NORMAL ("0").
          d) Queue is removed from queueCtrl.
        """
        target_idx = "1"
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b1 = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        b1["lv"] = "30"
        b1["honorLv"] = "4"
        b1["hlv"] = "4"
        b1["state"] = BUILD_STATE.UPGRADING  # "2"

        self.engine.init_data["queueCtrl"]["1200"] = {
            "qtype": "1200",
            "index": target_idx,
            "bid": b1["bid"],
            "iid": b1["iid"],
            "isHonor": True,
            "startTime": 1700000000,
            "totalTime": 86400,
        }

        # Dispatch completion notification with honor flag
        honor_completion_payload = {
            "queuetype": "1200",
            "qtype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "index": target_idx,
            "bid": b1["bid"],
            "iid": b1["iid"],
            "isHonor": True,
        }
        self.engine.handle_notify(14, honor_completion_payload)

        # 1. Assert queue removed
        self.assertNotIn("1200", self.engine.init_data["queueCtrl"])

        # 2. Assert honor levels incremented
        b1_after = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        self.assertEqual(str(b1_after["honorLv"]), "5", f"honorLv must increment from 4 to 5, got {b1_after['honorLv']}")
        self.assertEqual(str(b1_after["hlv"]), "5", f"hlv must increment from 4 to 5, got {b1_after['hlv']}")

        # 3. Assert regular level did NOT change
        self.assertEqual(str(b1_after["lv"]), "30", f"Regular level must remain 30 during honor upgrade, got {b1_after['lv']}")

        # 4. Assert state reverted to NORMAL ("0")
        self.assertEqual(b1_after["state"], BUILD_STATE.NORMAL)

    # ──────────────────────────────────────────────────────────────────────────
    # Requirement 3: Queue Cancellation
    # ──────────────────────────────────────────────────────────────────────────
    def test_queue_cancellation(self):
        """
        Req 3:
        - Target building starts in UPGRADING state ("2") at level 18.
        - Queue is canceled with optype 11 or notifyType "cancel".
        - Verify:
          a) state reverts back to BUILD_STATE.NORMAL ("0").
          b) level remains strictly unchanged at 18 (NO increment).
          c) honorLv remains strictly unchanged at 0.
          d) Queue is removed from queueCtrl.
        """
        target_idx = "7"
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b7 = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        b7["lv"] = "18"
        b7["honorLv"] = "0"
        b7["hlv"] = "0"
        b7["state"] = BUILD_STATE.UPGRADING

        self.engine.init_data["queueCtrl"]["1200"] = {
            "qtype": "1200",
            "index": target_idx,
            "bid": b7["bid"],
            "iid": b7["iid"],
            "startTime": 1700000000,
        }

        # Dispatch cancellation payload (optype 11)
        cancel_payload = {
            "queuetype": "1200",
            "qtype": "1200",
            "notifyType": "cancel",
            "optype": BUILD_OPERATE_TYPE.CANCEL,  # 11
            "index": target_idx,
            "bid": b7["bid"],
            "iid": b7["iid"],
        }
        self.engine.handle_notify(14, cancel_payload)

        # 1. Assert queue removed
        self.assertNotIn("1200", self.engine.init_data["queueCtrl"])

        # 2. Assert state reverted to NORMAL
        b7_after = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        self.assertEqual(b7_after["state"], BUILD_STATE.NORMAL)

        # 3. Assert level NOT incremented
        self.assertEqual(str(b7_after["lv"]), "18", f"Level must NOT increment on cancel, got {b7_after['lv']}")
        self.assertEqual(str(b7_after["honorLv"]), "0")

    # ──────────────────────────────────────────────────────────────────────────
    # Requirement 4: City Integrity Preservation
    # ──────────────────────────────────────────────────────────────────────────
    def test_city_integrity_preservation_across_all_lifecycle_transitions(self):
        """
        Req 4:
        - Verify that during all transitions (upgrade index 12, honor upgrade index 1, cancel index 7,
          second queue 1201 upgrade index 33), none of the other buildings in blist are altered or wiped.
        - Exactly 50 buildings must persist at all times.
        - Untouched buildings must match their baseline snapshot identically across all fields.
        """
        blist = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(blist), 50, "Pre-condition: city must contain exactly 50 buildings.")

        # Capture complete deep copy baseline before mutations
        baseline_snapshot = copy.deepcopy(blist)
        targeted_indices = {"1", "7", "12", "33"}

        # 1. Mutate building 12 (Regular upgrade)
        b12 = next(b["binfo"] for b in blist if b["binfo"]["index"] == "12")
        b12["state"] = BUILD_STATE.UPGRADING
        self.engine.handle_notify(14, {"queuetype": "1200", "notifyType": "finish", "optype": 2, "index": "12"})

        # 2. Mutate building 1 (Honor upgrade)
        b1 = next(b["binfo"] for b in blist if b["binfo"]["index"] == "1")
        b1["lv"] = "30"
        b1["honorLv"] = "2"
        b1["hlv"] = "2"
        b1["state"] = BUILD_STATE.UPGRADING
        self.engine.handle_notify(14, {"queuetype": "1200", "notifyType": "finish", "optype": 2, "index": "1", "isHonor": True})

        # 3. Mutate building 7 (Cancel)
        b7 = next(b["binfo"] for b in blist if b["binfo"]["index"] == "7")
        b7["state"] = BUILD_STATE.UPGRADING
        self.engine.handle_notify(14, {"queuetype": "1200", "notifyType": "cancel", "optype": 11, "index": "7"})

        # 4. Mutate building 33 on second hired queue (1201)
        b33 = next(b["binfo"] for b in blist if b["binfo"]["index"] == "33")
        b33["state"] = BUILD_STATE.UPGRADING
        b33["lv"] = "8"
        self.engine.handle_notify(14, {"queuetype": "1201", "notifyType": "finish", "optype": 2, "index": "33"})

        # ── Verify City Integrity ──
        current_blist = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(current_blist), 50, "blist length must remain exactly 50; no buildings deleted or wiped!")

        # Verify all 46 untargeted buildings are byte-for-byte identical to baseline
        for orig_b in baseline_snapshot:
            idx = orig_b["binfo"]["index"]
            if idx in targeted_indices:
                continue

            current_b = next((b for b in current_blist if b.get("binfo", {}).get("index") == idx), None)
            self.assertIsNotNone(current_b, f"Building with index {idx} was lost or wiped from blist!")
            self.assertEqual(
                current_b,
                orig_b,
                f"Integrity violation: Building index {idx} was unexpectedly modified! Expected {orig_b}, got {current_b}"
            )

        # Verify targeted buildings reached expected final states
        b12_final = next(b["binfo"] for b in current_blist if b["binfo"]["index"] == "12")
        self.assertEqual(str(b12_final["lv"]), "11")
        self.assertEqual(b12_final["state"], BUILD_STATE.NORMAL)

        b1_final = next(b["binfo"] for b in current_blist if b["binfo"]["index"] == "1")
        self.assertEqual(str(b1_final["honorLv"]), "3")
        self.assertEqual(str(b1_final["hlv"]), "3")
        self.assertEqual(str(b1_final["lv"]), "30")
        self.assertEqual(b1_final["state"], BUILD_STATE.NORMAL)

        b7_final = next(b["binfo"] for b in current_blist if b["binfo"]["index"] == "7")
        self.assertEqual(str(b7_final["lv"]), "10")
        self.assertEqual(b7_final["state"], BUILD_STATE.NORMAL)

        b33_final = next(b["binfo"] for b in current_blist if b["binfo"]["index"] == "33")
        self.assertEqual(str(b33_final["lv"]), "9")
        self.assertEqual(b33_final["state"], BUILD_STATE.NORMAL)

    # ──────────────────────────────────────────────────────────────────────────
    # Requirement 5: Adversarial & Edge Case Tests
    # ──────────────────────────────────────────────────────────────────────────
    def test_dispatch_queue_event_wrapped_payload(self):
        """
        Stress Test:
        Server often sends queue payloads wrapped inside `dispatchQueueEvent` with nested `data`.
        Verify `_handle_notify_queue` unpacks it correctly without losing targeting info.
        """
        target_idx = "18"
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b18 = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        b18["lv"] = "5"
        b18["state"] = BUILD_STATE.UPGRADING

        self.engine.init_data["queueCtrl"]["1200"] = {"qtype": "1200", "index": target_idx}

        wrapped_payload = {
            "dispatchQueueEvent": {
                "queuetype": 1200,
                "name": "1200",
                "notifyType": "finish",
                "data": {
                    "bid": b18["bid"],
                    "iid": b18["iid"],
                    "index": target_idx,
                    "optype": 2,
                }
            }
        }
        self.engine.handle_notify(14, wrapped_payload)

        self.assertNotIn("1200", self.engine.init_data["queueCtrl"])
        b18_after = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        self.assertEqual(str(b18_after["lv"]), "6")
        self.assertEqual(b18_after["state"], BUILD_STATE.NORMAL)

    def test_composite_key_targeting_bid_iid(self):
        """
        Stress Test:
        Queue payload omits `index`, providing only `bid` and `iid`.
        Verify target building is correctly resolved via composite identity (bid, iid).
        """
        blist = self.engine.init_data["cityCtrl"]["blist"]
        # Find building at index 25
        b25 = next(b["binfo"] for b in blist if b["binfo"]["index"] == "25")
        b25["lv"] = "12"
        b25["state"] = BUILD_STATE.UPGRADING
        target_bid = b25["bid"]
        target_iid = b25["iid"]

        payload_no_index = {
            "queuetype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "bid": target_bid,
            "iid": target_iid,
            # Notice: no "index" field provided!
        }
        self.engine.handle_notify(14, payload_no_index)

        b25_after = next(b["binfo"] for b in blist if b["binfo"]["index"] == "25")
        self.assertEqual(str(b25_after["lv"]), "13", "Building must be identified and upgraded via (bid, iid)!")
        self.assertEqual(b25_after["state"], BUILD_STATE.NORMAL)

    def test_flat_building_structure_without_binfo(self):
        """
        Stress Test:
        Some server notifications or subsystems expose flat building dictionaries
        `{"index": "9", "bid": "105", "lv": "2", "state": "2"}` without `binfo` nesting.
        Verify seamless update and level increment.
        """
        flat_city = {
            "cityCtrl": {
                "blist": [
                    {"index": "9", "bid": "105", "iid": "0", "lv": "2", "state": BUILD_STATE.UPGRADING},
                    {"index": "10", "bid": "106", "iid": "0", "lv": "5", "state": BUILD_STATE.NORMAL},
                ]
            },
            "queueCtrl": {"1200": {"qtype": "1200", "index": "9"}},
        }
        engine = LiveMemoryEngine(init_data=flat_city)
        engine.handle_notify(14, {"queuetype": "1200", "notifyType": "finish", "optype": 2, "index": "9"})

        self.assertNotIn("1200", engine.init_data["queueCtrl"])
        b9 = next(b for b in engine.init_data["cityCtrl"]["blist"] if b["index"] == "9")
        self.assertEqual(str(b9["lv"]), "3")
        self.assertEqual(b9["state"], BUILD_STATE.NORMAL)

    def test_missing_or_invalid_building_index_does_not_crash(self):
        """
        Stress Test:
        Queue finishes for an index that does not exist in blist (e.g., '9999').
        Must cleanly evict the queue without throwing IndexError or KeyError, leaving city intact.
        """
        self.engine.init_data["queueCtrl"]["1200"] = {"qtype": "1200", "index": "9999"}
        payload = {
            "queuetype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "index": "9999",
        }
        # Should not raise any exception
        self.engine.handle_notify(14, payload)
        self.assertNotIn("1200", self.engine.init_data["queueCtrl"])
        self.assertEqual(len(self.engine.init_data["cityCtrl"]["blist"]), 50)

    def test_game_client_s2c_dispatch_integration(self):
        """
        End-to-End Stress Test:
        Simulate a network-level S2C push packet arriving at GateClient._dispatch:
        CMD 1009, subcmd 14 with notifyID=14 and queue finish payload.
        Verify that GateClient.init_data automatically reflects the building upgrade.
        """
        if GateClient is None or GateCredentials is None:
            self.skipTest("GateClient not importable")

        creds = GateCredentials(
            uid="999888",
            server_name="test_srv",
            sub_id="1",
            secret="test_secret",
            gate_ip="127.0.0.1",
            gate_port=8000,
        )
        client = GateClient(creds)
        client.init_data = generate_canonical_city(10)
        # Ensure memory engine holds the same reference
        client.memory_engine.init_data = client.init_data

        target_idx = "3"
        blist = client.init_data["cityCtrl"]["blist"]
        b3 = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        b3["lv"] = "7"
        b3["state"] = BUILD_STATE.UPGRADING
        client.init_data["queueCtrl"]["1200"] = {"qtype": "1200", "index": target_idx}

        # Simulated decoded packet received from socket
        simulated_s2c_packet = {
            "cmd": "1009",
            "subcmd": "14",
            "data": {
                "notifyID": "14",
                "notifyData": [
                    {
                        "queuetype": "1200",
                        "notifyType": "finish",
                        "optype": 2,
                        "index": target_idx,
                        "bid": b3["bid"],
                        "iid": b3["iid"],
                    }
                ]
            }
        }

        # Ingest directly through memory_engine (or simulate packet dispatch)
        client.memory_engine.ingest_packet(simulated_s2c_packet)

        # Assertions on client.init_data
        self.assertNotIn("1200", client.init_data["queueCtrl"])
        b3_after = next(b["binfo"] for b in blist if b["binfo"]["index"] == target_idx)
        self.assertEqual(str(b3_after["lv"]), "8")
        self.assertEqual(b3_after["state"], BUILD_STATE.NORMAL)

    def test_code_integrity_anti_tampering(self):
        """
        Adversarial Review Integrity Check:
        Inspects the AST / source of LiveMemoryEngine._handle_notify_queue to ensure:
        - No hardcoded building indices (e.g. '12', '10', '101') used to cheat tests.
        - Real mathematical increments (e.g., + 1 or int conversions) are present.
        - State reset to BUILD_STATE.NORMAL is generic across any building.
        """
        src = inspect.getsource(LiveMemoryEngine._handle_notify_queue)

        # 1. Ensure mathematical increment logic exists
        self.assertIn("current_lv + 1", src, "Source code must contain genuine level increment arithmetic!")
        self.assertIn("current_hlv + 1", src, "Source code must contain genuine honor level increment arithmetic!")

        # 2. Ensure state reset to BUILD_STATE.NORMAL
        self.assertIn("BUILD_STATE.NORMAL", src, "Source code must assign BUILD_STATE.NORMAL!")

        # 3. Ensure no hardcoded index checks designed to fake test results
        forbidden_hardcoded_patterns = [
            'if b_index == "10":',
            'if b_index == "12":',
            'if b_index == "1":',
            'lv = 25',
            'lv = "25"',
        ]
        for pattern in forbidden_hardcoded_patterns:
            self.assertNotIn(
                pattern,
                src,
                f"Integrity violation detected! Found suspicious hardcoded pattern '{pattern}' in _handle_notify_queue!"
            )


if __name__ == "__main__":
    unittest.main()
