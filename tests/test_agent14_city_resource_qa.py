# -*- coding: utf-8 -*-
"""
tests/test_agent14_city_resource_qa.py
══════════════════════════════════════════════════════════════════════════════
Independent QA Verification and Adversarial Test Suite for NOTIFY_CITY Mutations
Conducted by: Agent 14 (City & Resource Delta QA Agent)
Roles: Reviewer, Adversarial Critic

Tests:
  1. Resource delta summation (+ and - counts, string and int)
  2. Clamp-to-zero safety (no negative resource balances)
  3. Absolute replacements (reslist, saferes, dayMaxRes)
  4. Deep-copy isolation (source mutation immunity)
  5. Uncollected resource updates (updateUnCollectRes for binfo and flat buildings)
  6. Second charge queue (openChargeQueue for cityCtrl.queue and queueCtrl)
  7. Adversarial edge cases (double dispatch, malformed packets, type mismatch)
"""

import copy
import unittest
from core.live_memory import LiveMemoryEngine, BUILD_STATE


class TestCityResourceDeltaQA(unittest.TestCase):
    """Rigorous QA Verification of NOTIFY_CITY mutations."""

    def setUp(self):
        self.engine = LiveMemoryEngine()
        # Seed engine with realistic cityCtrl state
        self.engine.init_data = {
            "cityCtrl": {
                "cinfo": {"cid": "88888", "name": "TestCastle"},
                "blist": [
                    {
                        "binfo": {
                            "bid": "101",
                            "iid": "1",
                            "index": "1",
                            "lv": "25",
                            "state": BUILD_STATE.NORMAL,
                            "curres": "0",
                            "honorLv": "0",
                        }
                    },
                    {
                        "binfo": {
                            "bid": "102",  # Farm
                            "iid": "1",
                            "index": "10",
                            "lv": "20",
                            "state": BUILD_STATE.NORMAL,
                            "curres": "500",
                            "honorLv": "0",
                        }
                    },
                    {
                        "binfo": {
                            "bid": "103",  # Sawmill
                            "iid": "1",
                            "index": "15",
                            "lv": "22",
                            "state": BUILD_STATE.NORMAL,
                            "curres": 1200,
                            "honorLv": "0",
                        }
                    },
                    {
                        # Flat structure without nested binfo
                        "bid": "104",  # Iron mine
                        "iid": "1",
                        "index": "20",
                        "lv": "18",
                        "state": BUILD_STATE.NORMAL,
                        "curres": 300,
                    },
                ],
                "reslist": {
                    "1001": 50000,     # Food (int)
                    "1002": "20000",   # Wood (str)
                    "1003": 5000,      # Iron (int)
                    "1004": "1000",    # Mithril (str)
                },
                "saferes": {
                    "1001": "1000000",
                    "1002": "1000000",
                },
                "dayMaxRes": {
                    "1001": "20000000",
                    "1002": "20000000",
                },
                "queue": {},
            },
            "queueCtrl": {},
            "lordInfoCtrl": {"base": {"uid": 123456}},
            "armyCtrl": {"totalArmy": {"10101": "1000"}},
            "heroCtrl": [],
            "backpackCtrl": {},
        }

    # ══════════════════════════════════════════════════════════════════════════
    # 1. Resource Delta Summation & Clamp-to-Zero Tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_resource_delta_summation_positive_and_negative(self):
        """
        Verify that positive and negative counts in v.res correctly sum
        with existing resource balances and preserve existing type.
        """
        notify_payload = [
            {
                "res": {
                    "1001": 15000,   # 50000 + 15000 = 65000 (int)
                    "1002": -5000,   # 20000 - 5000 = 15000 (str preserved)
                }
            }
        ]

        self.engine.handle_notify(9, notify_payload)
        reslist = self.engine.init_data["cityCtrl"]["reslist"]

        self.assertEqual(reslist["1001"], 65000, "Positive delta must be added to int resource")
        self.assertIsInstance(reslist["1001"], int, "Int resource type should be preserved")
        self.assertEqual(reslist["1002"], "15000", "Negative delta must be deducted from str resource")
        self.assertIsInstance(reslist["1002"], str, "Str resource type should be preserved")

    def test_resource_delta_clamp_to_zero_safety(self):
        """
        Verify that large negative resource subtractions clamp strictly to 0
        and NEVER produce negative numbers.
        """
        notify_payload = [
            {
                "res": {
                    "1001": -99999999,  # 50000 - 99999999 -> clamp to 0
                    "1003": -5000,      # 5000 - 5000 -> 0 exactly
                    "1004": "-500000",  # "1000" - 500000 -> clamp to "0"
                }
            }
        ]

        self.engine.handle_notify("9", notify_payload)
        reslist = self.engine.init_data["cityCtrl"]["reslist"]

        self.assertEqual(reslist["1001"], 0, "Massive deduction must clamp to 0")
        self.assertEqual(reslist["1003"], 0, "Exact deduction must equal 0")
        self.assertEqual(reslist["1004"], "0", "String deduction beyond balance must clamp to '0'")
        self.assertGreaterEqual(int(reslist["1001"]), 0)
        self.assertGreaterEqual(int(reslist["1003"]), 0)
        self.assertGreaterEqual(int(reslist["1004"]), 0)

    def test_resource_delta_new_resource_key(self):
        """
        Verify that a delta introducing a previously unlisted resource key
        is initialized starting from 0 and correctly assigned.
        """
        notify_payload = [
            {
                "res": {
                    "1005": 3500,  # Gold (not present in initial reslist)
                }
            }
        ]

        self.engine.handle_notify("CITY", notify_payload)
        reslist = self.engine.init_data["cityCtrl"]["reslist"]

        self.assertIn("1005", reslist)
        self.assertEqual(reslist["1005"], 3500)

    def test_resource_delta_sequential_multiple_deltas(self):
        """
        Verify that multiple delta objects delivered in a single notify list
        are evaluated sequentially in order.
        """
        notify_payload = [
            {"res": {"1001": 10000}},   # 50000 + 10000 = 60000
            {"res": {"1001": -40000}},  # 60000 - 40000 = 20000
            {"res": {"1001": 5000}},    # 20000 + 5000 = 25000
        ]

        self.engine.handle_notify(9, notify_payload)
        reslist = self.engine.init_data["cityCtrl"]["reslist"]
        self.assertEqual(reslist["1001"], 25000)

    # ══════════════════════════════════════════════════════════════════════════
    # 2. Absolute Replacements (reslist, saferes, dayMaxRes)
    # ══════════════════════════════════════════════════════════════════════════

    def test_absolute_replacement_reslist(self):
        """
        Verify that v.reslist completely replaces the current resource catalog,
        wiping keys that are no longer in the server catalog (matching Lua).
        """
        # Inject an obsolete key that must be removed on replacement
        self.engine.init_data["cityCtrl"]["reslist"]["obsolete_key"] = 9999

        new_catalog = {
            "1001": "8800000",
            "1002": "6600000",
            "1005": "50000",
        }

        notify_payload = [{"reslist": new_catalog}]
        self.engine.handle_notify(9, notify_payload)

        reslist = self.engine.init_data["cityCtrl"]["reslist"]
        self.assertEqual(reslist, new_catalog)
        self.assertNotIn("obsolete_key", reslist, "Obsolete keys must be wiped upon reslist replacement")
        self.assertNotIn("1003", reslist, "Keys not in new reslist must be absent")

    def test_absolute_replacement_saferes_and_daymaxres(self):
        """
        Verify that v.saferes and v.dayMaxRes perform direct absolute updates.
        """
        new_saferes = {"1001": "5000000", "1002": "5000000", "1003": "2000000"}
        new_daymaxres = {"1001": "50000000", "1002": "50000000"}

        notify_payload = [
            {
                "saferes": new_saferes,
                "dayMaxRes": new_daymaxres,
            }
        ]

        self.engine.handle_notify(9, notify_payload)
        city_ctrl = self.engine.init_data["cityCtrl"]

        self.assertEqual(city_ctrl["saferes"], new_saferes)
        self.assertEqual(city_ctrl["dayMaxRes"], new_daymaxres)

    def test_deep_copy_isolation_on_replacement(self):
        """
        Verify deep-copy isolation: mutating the source payload object after
        calling handle_notify MUST NOT corrupt the internal live state.
        """
        src_saferes = {"1001": "1000000"}
        src_daymax = {"1001": "20000000"}
        payload = [{"saferes": src_saferes, "dayMaxRes": src_daymax}]

        self.engine.handle_notify(9, payload)

        # Mutate the source dictionary externally
        src_saferes["1001"] = "MUTATED_VALUE"
        src_daymax["1001"] = "MUTATED_DAYMAX"

        city_ctrl = self.engine.init_data["cityCtrl"]
        self.assertEqual(city_ctrl["saferes"]["1001"], "1000000", "Source mutation must not affect memory")
        self.assertEqual(city_ctrl["dayMaxRes"]["1001"], "20000000", "Source mutation must not affect memory")

    # ══════════════════════════════════════════════════════════════════════════
    # 3. Uncollected Resources (updateUnCollectRes)
    # ══════════════════════════════════════════════════════════════════════════

    def test_uncollected_resources_with_binfo_structure(self):
        """
        Verify that updateUnCollectRes increments curres for buildings
        stored in standard binfo wrapper.
        """
        # Building at index 10 starts with curres = "500" (string)
        # Building at index 15 starts with curres = 1200 (int)
        notify_payload = [
            {
                "updateUnCollectRes": {
                    "10": 350,   # 500 + 350 = 850 (str)
                    "15": 800,   # 1200 + 800 = 2000 (int)
                }
            }
        ]

        self.engine.handle_notify(9, notify_payload)
        blist = self.engine.init_data["cityCtrl"]["blist"]

        b10 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        b15 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "15")

        self.assertEqual(b10["curres"], "850")
        self.assertIsInstance(b10["curres"], str)
        self.assertEqual(b15["curres"], 2000)
        self.assertIsInstance(b15["curres"], int)

    def test_uncollected_resources_with_flat_structure(self):
        """
        Verify that updateUnCollectRes handles flat building dicts without binfo.
        """
        # Building at index 20 starts with curres = 300
        notify_payload = [
            {
                "updateUnCollectRes": {
                    "20": 450,  # 300 + 450 = 750
                }
            }
        ]

        self.engine.handle_notify(9, notify_payload)
        blist = self.engine.init_data["cityCtrl"]["blist"]

        b20 = next(b for b in blist if str(b.get("index")) == "20")
        self.assertEqual(b20["curres"], 750)

    def test_uncollected_resources_integer_index_keys(self):
        """
        Verify that integer index keys in updateUnCollectRes properly match
        string indices in blist (e.g. {10: 100}).
        """
        notify_payload = [
            {
                "updateUnCollectRes": {
                    10: 200,  # int key instead of str
                }
            }
        ]

        self.engine.handle_notify(9, notify_payload)
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b10 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        self.assertEqual(b10["curres"], "700")

    def test_uncollected_resources_nonexistent_index_no_crash(self):
        """
        Verify that if an unknown index is sent in updateUnCollectRes,
        the engine gracefully skips it without throwing an error.
        """
        notify_payload = [
            {
                "updateUnCollectRes": {
                    "9999": 500,  # Not in blist
                }
            }
        ]

        try:
            self.engine.handle_notify(9, notify_payload)
        except Exception as e:
            self.fail(f"Nonexistent building index should not raise: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # 4. Second Charge Queue (openChargeQueue)
    # ══════════════════════════════════════════════════════════════════════════

    def test_second_charge_queue_activation(self):
        """
        Verify that openChargeQueue adds queue type '1201' to:
          1. cityCtrl.queue['1201']
          2. queueCtrl['1201'] with qtype='1201'
        """
        charge_data = {
            "starttime": 1700000000,
            "totaltime": 172800,
            "lefttime": 86400,
        }
        notify_payload = [{"openChargeQueue": charge_data}]

        self.engine.handle_notify(9, notify_payload)

        # 1. cityCtrl queue verification
        city_queue = self.engine.init_data["cityCtrl"]["queue"]
        self.assertIn("1201", city_queue)
        self.assertEqual(city_queue["1201"]["totaltime"], 172800)
        self.assertEqual(city_queue["1201"]["lefttime"], 86400)
        self.assertEqual(city_queue["1201"]["starttime"], 1700000000)

        # 2. queueCtrl queue verification
        queue_ctrl = self.engine.init_data["queueCtrl"]
        self.assertIn("1201", queue_ctrl)
        self.assertEqual(queue_ctrl["1201"]["qtype"], "1201")
        self.assertEqual(queue_ctrl["1201"]["totaltime"], 172800)
        self.assertEqual(queue_ctrl["1201"]["lefttime"], 86400)

    # ══════════════════════════════════════════════════════════════════════════
    # 5. Adversarial Stress & Failure Mode Tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_adversarial_notify_id_variants(self):
        """
        Verify that handle_notify accepts all valid forms of NOTIFY_CITY identifier:
        9 (int), '9' (str), 'CITY', 'NOTIFY_CITY', 'NOTIFY_CITY_UPDATE'.
        """
        variants = [9, "9", "CITY", "NOTIFY_CITY", "NOTIFY_CITY_UPDATE", "  city  "]
        for var in variants:
            prev = int(self.engine.init_data["cityCtrl"]["reslist"]["1001"])
            self.engine.handle_notify(var, [{"res": {"1001": 100}}])
            curr = int(self.engine.init_data["cityCtrl"]["reslist"]["1001"])
            self.assertEqual(curr, prev + 100, f"Variant '{var}' must trigger city notification handler")

    def test_adversarial_single_dict_vs_list_payload(self):
        """
        Verify that handle_notify supports single dict payload as well as list of dicts.
        """
        single_dict_payload = {"res": {"1001": 500}}
        self.engine.handle_notify(9, single_dict_payload)
        self.assertEqual(self.engine.init_data["cityCtrl"]["reslist"]["1001"], 50500)

    def test_adversarial_malformed_packets_graceful(self):
        """
        Verify that malformed or empty notification payloads do not crash the engine.
        """
        malformed = [
            None,
            [],
            [None],
            [{}],
            {"res": None},
            {"res": "not_a_dict"},
            {"openChargeQueue": "not_a_dict"},
            {"updateUnCollectRes": None},
            "string_payload",
            12345,
        ]
        for bad in malformed:
            try:
                self.engine.handle_notify(9, bad)
            except Exception as e:
                self.fail(f"Engine crashed on malformed notify payload {bad}: {e}")

    def test_adversarial_ingest_packet_double_dispatch_risk(self):
        """
        ADVERSARIAL STRESS TEST: Check whether feeding a CMD 1009 packet
        through ingest_packet causes double execution if handle_notify
        is also called externally.
        """
        packet = {
            "cmd": "1009",
            "data": {
                "notifyID": "9",
                "notifyData": [
                    {
                        "res": {"1001": 1000}
                    }
                ]
            }
        }

        # Baseline: run ingest_packet once
        initial_val = self.engine.init_data["cityCtrl"]["reslist"]["1001"]
        self.engine.ingest_packet(packet)
        after_ingest = self.engine.init_data["cityCtrl"]["reslist"]["1001"]

        self.assertEqual(
            after_ingest,
            initial_val + 1000,
            "ingest_packet must apply resource delta exactly once (1000)"
        )

    def test_adversarial_game_client_dispatch_double_call_flaw(self):
        """
        ADVERSARIAL CRITICAL FINDING REPRODUCTION:
        In game_client.py:
          - Line 676: self.memory_engine.ingest_packet(c)
          - Line 688: self.memory_engine.handle_notify(notify_id, notify_data)
        Because ingest_packet(c) already triggers handle_notify on cmd 1009,
        executing both lines results in DOUBLE MUTATION of resources.
        """
        c = {
            "cmd": "1009",
            "data": {
                "notifyID": "9",
                "notifyData": [
                    {
                        "res": {"1001": 500}
                    }
                ]
            }
        }

        initial_val = self.engine.init_data["cityCtrl"]["reslist"]["1001"]

        # Step 2 from game_client.py:676
        self.engine.ingest_packet(c)
        val_after_step2 = self.engine.init_data["cityCtrl"]["reslist"]["1001"]
        self.assertEqual(val_after_step2, initial_val + 500, "Step 2 applied delta (+500)")

        # Step 3 from game_client.py:688
        data_obj = c.get('data', {})
        notify_id = str(data_obj.get('notifyID', ''))
        notify_data = data_obj.get('notifyData', [])
        self.engine.handle_notify(notify_id, notify_data)
        val_after_step3 = self.engine.init_data["cityCtrl"]["reslist"]["1001"]

        # This proves the vulnerability: delta is applied twice (+1000 instead of +500)
        self.assertEqual(
            val_after_step3,
            initial_val + 1000,
            "DOUBLE-DISPATCH BUG CONFIRMED: Delta was applied twice!"
        )

    def test_adversarial_open_charge_queue_missing_starttime(self):
        """
        ADVERSARIAL FINDING:
        When server pushes openChargeQueue with only totaltime and lefttime (no starttime),
        cityCtrl.queue['1201'] lacks starttime.
        tasks/building.py lines 716-718 checks (st + tt) > time.time(),
        where st=0 leads to (0 + 172800) < time.time(), causing building.py
        to assume the second queue is expired!
        """
        charge_data = {
            "totaltime": 172800,
            "lefttime": 86400,
            # 'starttime' omitted as in raw server push (LUA_PROTOCOL_SPEC line 381)
        }
        notify_payload = [{"openChargeQueue": charge_data}]
        self.engine.handle_notify(9, notify_payload)

        q1201 = self.engine.init_data["cityCtrl"]["queue"]["1201"]
        # Verify that starttime is absent unless explicitly defaulted
        self.assertNotIn("starttime", q1201, "starttime is missing from openChargeQueue payload")

    def test_adversarial_open_charge_queue_when_queue_ctrl_is_list(self):
        """
        ADVERSARIAL FINDING:
        If queueCtrl in init_data was initialized as a list (standard retdata format
        from loginDataInit), openChargeQueue does NOT insert 1201 into queueCtrl
        because live_memory.py line 649 checks `if isinstance(queue_ctrl, dict):`.
        """
        # Set queueCtrl as list (as received in retdata from server login)
        self.engine.init_data["queueCtrl"] = [
            {"qtype": "1200", "starttime": 1700000000, "totaltime": 3600}
        ]

        charge_data = {"totaltime": 172800, "lefttime": 86400, "starttime": 1700000000}
        notify_payload = [{"openChargeQueue": charge_data}]
        self.engine.handle_notify(9, notify_payload)

        # In cityCtrl it is set:
        self.assertIn("1201", self.engine.init_data["cityCtrl"]["queue"])

        # But in queueCtrl (list), it was NOT inserted:
        queue_types_in_list = [q.get("qtype") for q in self.engine.init_data["queueCtrl"]]
        self.assertNotIn("1201", queue_types_in_list, "1201 not in queueCtrl list due to dict check")

    def test_adversarial_both_res_and_reslist_in_same_delta(self):
        """
        Verify precedence when both 'res' delta and 'reslist' absolute replacement
        arrive in the same delta object.
        According to Lua cityCtrl.lua: reslist overrides res.
        """
        notify_payload = [
            {
                "res": {"1001": -5000},
                "reslist": {"1001": 99999},
            }
        ]
        self.engine.handle_notify(9, notify_payload)
        reslist = self.engine.init_data["cityCtrl"]["reslist"]
        self.assertEqual(reslist["1001"], 99999, "reslist full replacement must take final precedence")


if __name__ == "__main__":
    unittest.main()
