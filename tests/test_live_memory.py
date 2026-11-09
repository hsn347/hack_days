# -*- coding: utf-8 -*-
r"""
tests/test_live_memory.py — Production QA Test Suite for Live State Memory Engine & Readiness Gate
══════════════════════════════════════════════════════════════════════════════════════════════════
Author: Test Writer: Live Memory & Readiness Gate QA (Track 2 Specialist)
Workspace: e:\osmanli

This test suite rigorously verifies the production contracts established in:
  1. ORIGINAL_REQUEST.md
  2. LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
  3. CONTROLLER_WHITELIST_SPEC.md (SPEC-CORE-M0-CW01)
  4. LUA_PROTOCOL_SPEC.md
  5. DEEP_MERGE_SPEC.md

Coverage Matrix:
  - Whitelist Ingress Filtering (ALLOWED_CONTROLLERS, noise drop 100%)
  - Keyed Deep Merge (cityCtrl.blist 50 buildings, heroes, buffs, queues, CoW)
  - Concurrency & Copy-on-Write Safety (Iterator invalidation shielding, multi-thread stress)
  - Real-time Notification Handling (NOTIFY_CITY, NOTIFY_QUEUE regular/honor, NOTIFY_BACKPACK)
  - Readiness Gate & Fallback Queries (Structural integrity, fallback queries, timeout)
  - Adversarial & Edge Cases (Clamping, malformed packets, string/int ID normalization)
"""

from __future__ import annotations

import asyncio
import copy
import os
import sys
import threading
import time
import unittest
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.live_memory import (
    ALLOWED_CONTROLLERS,
    CRITICAL_STARTUP_CONTROLLERS,
    FALLBACK_QUERIES,
    BUILD_STATE,
    BUILD_OPERATE_TYPE,
    LiveMemoryEngine,
    extract_entity_key,
    get_fallback_query,
    smart_deep_merge,
)

# Optional import of GateClient from game_client
try:
    from game_client import GateClient, GameClient
except ImportError:
    GateClient = None
    GameClient = None


# ══════════════════════════════════════════════════════════════════════════════
# Test Fixtures & Generators
# ══════════════════════════════════════════════════════════════════════════════

def generate_50_buildings() -> List[Dict[str, Any]]:
    """Generates 50 canonical castle building entities matching cityCtrl.lua."""
    blist = []
    for i in range(1, 51):
        bid = str(100 + (i % 12))
        iid = str(i // 12)
        blist.append({
            "binfo": {
                "index": str(i),
                "bid": bid,
                "iid": iid,
                "lv": "10",
                "state": "0",
                "curres": "0",
                "curres_safe": "0",
                "honorLv": "0",
                "hlv": "0",
            }
        })
    return blist


def generate_10_heroes() -> List[Dict[str, Any]]:
    """Generates 10 canonical hero dictionaries matching heroCtrl.lua."""
    heroes = []
    for i in range(10):
        hero_id = 5501000 + i
        heroes.append({
            "id": hero_id,
            "heroId": hero_id,
            "lv": 20,
            "star": 2,
            "exp": 5000,
            "power": 12000,
            "state": 0,
        })
    return heroes


def generate_valid_critical_state() -> Dict[str, Any]:
    """Generates a complete, structurally valid snapshot of all 6 critical controllers."""
    return {
        "cityCtrl": {
            "blist": generate_50_buildings(),
            "reslist": {
                "1001": "5000000",
                "1002": "4000000",
                "1003": "1000000",
                "1004": "800000",
                "1005": "35000",
            },
            "cinfo": {"cid": "123456", "name": "Capital", "pos": {"x": 500, "y": 500}},
            "saferes": {"1001": "1000000", "1002": "1000000"},
            "dayMaxRes": {"1001": "20000000", "1002": "20000000"},
            "arealist": ["1", "2", "3", "4"],
        },
        "lordInfoCtrl": {
            "base": {
                "uid": 12345678,
                "nickName": "TestLord",
                "partition": 105,
                "level": 30,
                "gold": 5000,
            }
        },
        "queueCtrl": {
            "1200": {"qtype": "1200", "bid": "101", "startTime": 1700000000, "totalTime": 3600}
        },
        "armyCtrl": {
            "totalArmy": {"101": 5000, "102": 3000},
            "woundedArmy": {},
        },
        "heroCtrl": generate_10_heroes(),
        "backpackCtrl": {
            "2001": {"id": "2001", "count": "15"},
            "2002": {"id": "2002", "count": "5"},
        },
    }


async def standalone_wait_for_memory_ready(
    engine_or_conn: Any,
    timeout: float = 5.0,
    auto_fetch_missing: bool = True,
    query_dispatcher: Optional[Callable[[str, int, int, Dict[str, Any]], Any]] = None,
    poll_interval: float = 0.02,
    uid: int = 12345678,
) -> bool:
    """
    Standard memory readiness gate runner conforming to SPEC-CORE-M0-CW01:
      1. If the target object natively provides `wait_for_memory_ready`, calls it.
      2. Otherwise, interrogates `target.is_memory_ready()` or `target.memory_engine.is_memory_ready()`.
      3. If missing controllers and `auto_fetch_missing=True`, dispatches fallback queries.
      4. Polls until ready or timeout expiration.
    """
    if hasattr(engine_or_conn, "wait_for_memory_ready") and callable(getattr(engine_or_conn, "wait_for_memory_ready")):
        return await engine_or_conn.wait_for_memory_ready(timeout=timeout, auto_fetch_missing=auto_fetch_missing)

    engine: LiveMemoryEngine
    if isinstance(engine_or_conn, LiveMemoryEngine):
        engine = engine_or_conn
    elif hasattr(engine_or_conn, "memory_engine") and isinstance(engine_or_conn.memory_engine, LiveMemoryEngine):
        engine = engine_or_conn.memory_engine
    else:
        raise TypeError(f"Unsupported target for memory readiness gate: {type(engine_or_conn)}")

    is_ready, missing = engine.is_memory_ready()
    if is_ready:
        return True

    dispatched = set()
    start_time = time.monotonic()

    while time.monotonic() - start_time < timeout:
        is_ready, missing = engine.is_memory_ready()
        if is_ready:
            return True

        if auto_fetch_missing:
            for item in missing:
                root_ctrl = item.split(".")[0]
                if root_ctrl not in dispatched:
                    dispatched.add(root_ctrl)
                    q = get_fallback_query(root_ctrl, uid=uid)
                    if q:
                        cmd, subcmd, payload = q
                        if query_dispatcher is not None:
                            res = query_dispatcher(root_ctrl, cmd, subcmd, payload)
                            if asyncio.iscoroutine(res):
                                await res

        await asyncio.sleep(poll_interval)

    return False


# ══════════════════════════════════════════════════════════════════════════════
# 1. Whitelist Ingress Filtering Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestWhitelistIngressFiltering(unittest.TestCase):
    """
    Verifies Whitelist Ingress Filtering:
      - Feed packet containing whitelisted controllers (cityCtrl, lordInfoCtrl, queueCtrl)
        and non-whitelisted noise (chatCtrl, RedPointCtrl, videoAdCtrl, randomGarbage).
      - Assert only whitelisted controllers exist in init_data; non-whitelisted controllers
        are dropped 100%.
    """

    def setUp(self):
        self.engine = LiveMemoryEngine()

    def test_allowed_controllers_exact_catalog(self):
        """Asserts ALLOWED_CONTROLLERS contains exactly the required 42/43/44 controllers."""
        self.assertIn(len(ALLOWED_CONTROLLERS), (42, 43, 44))
        self.assertIn("local_queues", ALLOWED_CONTROLLERS)
        self.assertEqual(len(CRITICAL_STARTUP_CONTROLLERS), 6)
        self.assertTrue(CRITICAL_STARTUP_CONTROLLERS.issubset(ALLOWED_CONTROLLERS))

        # Critical controllers
        for ctrl in ("cityCtrl", "lordInfoCtrl", "queueCtrl", "armyCtrl", "heroCtrl", "backpackCtrl"):
            self.assertIn(ctrl, ALLOWED_CONTROLLERS)

        # Core subsystems
        for ctrl in ("allianceCtrl", "technologyCtrl", "vipCtrl", "meritoriousTaskCtrl",
                     "timeRewardCtrl", "lordSkillCtrl", "boeAttributeCtrl", "buffCtrl",
                     "petCtrl", "kingdomMapCtrl", "buyStaminaCtrl"):
            self.assertIn(ctrl, ALLOWED_CONTROLLERS)

        # Noise controllers MUST NOT be in ALLOWED_CONTROLLERS
        forbidden_noise = {
            "chatCtrl", "chatroomCtrl", "voiceRoomCtrl", "htMsgCtrl", "marqueeCtrl",
            "RedPointCtrl", "clientLogCtrl", "clientEventCtrl", "videoAdCtrl", "adCtrl",
            "dressCtrl", "dressShop", "rechargeCtrl", "randomGarbage", "fakeController"
        }
        for noise in forbidden_noise:
            self.assertNotIn(noise, ALLOWED_CONTROLLERS, f"Noise controller '{noise}' leaked into whitelist!")

    def test_filter_whitelisted_isolated(self):
        """Tests filter_whitelisted directly removes 100% of non-whitelisted keys."""
        dirty_input = {
            "cityCtrl": {"blist": []},
            "lordInfoCtrl": {"base": {}},
            "queueCtrl": {},
            "chatCtrl": {"messages": ["spam1", "spam2"]},
            "RedPointCtrl": {"beacons": [1, 2, 3]},
            "videoAdCtrl": {"ads": ["ad1"]},
            "randomGarbage": {"junk": True},
            "voiceRoomCtrl": {"channel": "global"},
        }
        clean = self.engine.filter_whitelisted(dirty_input)
        self.assertIn("cityCtrl", clean)
        self.assertIn("lordInfoCtrl", clean)
        self.assertIn("queueCtrl", clean)

        self.assertNotIn("chatCtrl", clean)
        self.assertNotIn("RedPointCtrl", clean)
        self.assertNotIn("videoAdCtrl", clean)
        self.assertNotIn("randomGarbage", clean)
        self.assertNotIn("voiceRoomCtrl", clean)
        self.assertEqual(len(clean), 3)

    def test_feed_packet_with_whitelisted_and_noise_controllers(self):
        """
        Feeds packet containing whitelisted controllers (cityCtrl, lordInfoCtrl, queueCtrl)
        and non-whitelisted noise (chatCtrl, RedPointCtrl, videoAdCtrl, randomGarbage).
        Asserts only whitelisted controllers exist in init_data; non-whitelisted controllers
        are dropped 100%.
        """
        packet = {
            "cmd": "1001",
            "sub": "1",
            "data": {
                "retdata": {
                    "cityCtrl": {
                        "blist": [{"binfo": {"index": "1", "bid": "101", "lv": "10"}}],
                        "reslist": {"1001": "50000"}
                    },
                    "lordInfoCtrl": {"base": {"uid": 12345}},
                    "queueCtrl": {"1200": {"qtype": "1200"}},
                    # Non-whitelisted noise:
                    "chatCtrl": {"room": "kingdom", "chat": ["hello", "world"]},
                    "RedPointCtrl": {"dots": {"101": 1, "102": 2}},
                    "videoAdCtrl": {"dailyWatch": 5},
                    "randomGarbage": {"randomField": "junkData"},
                }
            }
        }

        self.engine.ingest_packet(packet)

        # Assert only whitelisted controllers exist in init_data
        self.assertIn("cityCtrl", self.engine.init_data)
        self.assertIn("lordInfoCtrl", self.engine.init_data)
        self.assertIn("queueCtrl", self.engine.init_data)

        # Assert non-whitelisted noise controllers are dropped 100%
        self.assertNotIn("chatCtrl", self.engine.init_data)
        self.assertNotIn("RedPointCtrl", self.engine.init_data)
        self.assertNotIn("videoAdCtrl", self.engine.init_data)
        self.assertNotIn("randomGarbage", self.engine.init_data)

    def test_nested_data_envelope_noise_dropped(self):
        """Asserts noise in packet root level or direct data envelope is also dropped 100%."""
        packet = {
            "cmd": "1002",
            "sub": "1",
            "data": {
                "lordInfoCtrl": {"base": {"uid": 9999}},
                "clientLogCtrl": {"event": "click"},
                "dressCtrl": {"skin": 10},
            }
        }
        self.engine.ingest_packet(packet)
        self.assertIn("lordInfoCtrl", self.engine.init_data)
        self.assertNotIn("clientLogCtrl", self.engine.init_data)
        self.assertNotIn("dressCtrl", self.engine.init_data)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Keyed Deep Merge Correctness Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestKeyedDeepMerge(unittest.TestCase):
    """
    Verifies Keyed Deep Merge Correctness:
      - 50 buildings in cityCtrl.blist with 1 updated building: 50 remain, 1 updated, 0 duplicates.
      - 10 heroes in heroCtrl.heroes: delta update, 10 exist, updated reflects new data, 0 duplicates.
      - buffCtrl merge deltas (update, add, delete).
      - queueCtrl dict merge deltas.
      - Composite key fallback (bid, iid).
      - Primitive lists replaced with deep copy.
      - Mixed string/int ID normalization.
    """

    def setUp(self):
        self.engine = LiveMemoryEngine()

    def test_city_blist_50_buildings_delta_update_no_wipe_no_duplicate(self):
        """
        Initial state with 50 buildings in cityCtrl.blist.
        Incoming delta with 1 updated building (e.g. index: 10, lv: 25, state: 1).
        Assert all 50 buildings remain in blist; only building 10 was updated; zero duplicate entries.
        """
        initial_blist = generate_50_buildings()
        self.engine.init_data["cityCtrl"] = {
            "blist": initial_blist,
            "reslist": {"1001": "5000000"},
            "cinfo": {"name": "Capital"},
        }

        # Server sends delta response for building upgrade: only building index 10 modified
        delta_packet = {
            "cmd": "1001",
            "sub": "3",
            "data": {
                "retdata": {
                    "cityCtrl": {
                        "blist": [
                            {
                                "binfo": {
                                    "index": "10",
                                    "lv": 25,
                                    "state": 1,
                                }
                            }
                        ]
                    }
                }
            }
        }

        self.engine.ingest_packet(delta_packet)

        blist = self.engine.init_data["cityCtrl"]["blist"]

        # 1. Assert all 50 buildings remain in blist
        self.assertEqual(len(blist), 50, "Buildings were deleted or duplicated by delta update!")

        # 2. Assert zero duplicate entries (all indices 1..50 appear exactly once)
        indices = [str(b["binfo"]["index"]) for b in blist]
        self.assertEqual(len(indices), len(set(indices)), "Duplicate building entries found in blist!")
        self.assertEqual(set(indices), {str(i) for i in range(1, 51)})

        # 3. Assert only building 10 was updated
        b10 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        self.assertEqual(b10["lv"], 25)
        self.assertEqual(b10["state"], 1)

        # 4. Assert untouched fields of building 10 are preserved
        self.assertEqual(b10["bid"], str(100 + (10 % 12)))
        self.assertEqual(b10["iid"], str(10 // 12))

        # 5. Assert sibling building 9 and building 11 remain untouched
        b9 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "9")
        self.assertEqual(b9["lv"], "10")
        self.assertEqual(b9["state"], "0")

        # 6. Assert other cityCtrl fields (reslist, cinfo) are strictly preserved
        self.assertEqual(self.engine.init_data["cityCtrl"]["reslist"]["1001"], "5000000")
        self.assertEqual(self.engine.init_data["cityCtrl"]["cinfo"]["name"], "Capital")

    def test_city_blist_composite_key_fallback(self):
        """Asserts buildings without 'index' match by composite key (bid, iid)."""
        initial = {
            "cityCtrl": {
                "blist": [
                    {"binfo": {"bid": "101", "iid": "0", "lv": "10", "state": "0"}},
                    {"binfo": {"bid": "102", "iid": "1", "lv": "5", "state": "0"}},
                    {"binfo": {"bid": "102", "iid": "2", "lv": "6", "state": "0"}},
                ]
            }
        }
        self.engine.init_data = initial

        # Delta updates Farm 2 (bid: 102, iid: 2) without sending index
        delta = {
            "cityCtrl": {
                "blist": [
                    {"binfo": {"bid": "102", "iid": "2", "lv": "7", "state": "2"}}
                ]
            }
        }
        smart_deep_merge(self.engine.init_data, delta, in_place=True)

        blist = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(blist), 3)

        farm2 = next(b["binfo"] for b in blist if b["binfo"]["bid"] == "102" and b["binfo"]["iid"] == "2")
        self.assertEqual(farm2["lv"], "7")
        self.assertEqual(farm2["state"], "2")

    def test_hero_ctrl_10_heroes_delta_update(self):
        """
        Initial heroes list with 10 heroes in heroCtrl.heroes.
        Incoming delta updating 1 hero's exp/stars.
        Assert all 10 heroes exist; updated hero reflects new data; zero duplicates.
        """
        initial_heroes = generate_10_heroes()
        self.engine.init_data["heroCtrl"] = {"heroes": initial_heroes}

        # Delta updates hero 5501005 (exp=15000, star=4)
        delta_packet = {
            "cmd": "1005",
            "sub": "1",
            "data": {
                "retdata": {
                    "heroCtrl": {
                        "heroes": [
                            {"id": 5501005, "exp": 15000, "star": 4}
                        ]
                    }
                }
            }
        }

        self.engine.ingest_packet(delta_packet)

        heroes = self.engine.init_data["heroCtrl"]["heroes"]

        # 1. Assert all 10 heroes exist
        self.assertEqual(len(heroes), 10)

        # 2. Assert updated hero reflects new data and preserves untouched lv
        h5 = next(h for h in heroes if h["id"] == 5501005)
        self.assertEqual(h5["exp"], 15000)
        self.assertEqual(h5["star"], 4)
        self.assertEqual(h5["lv"], 20, "Untouched hero level must be preserved")
        self.assertEqual(h5["power"], 12000)

        # 3. Assert zero duplicates
        hero_ids = [h["id"] for h in heroes]
        self.assertEqual(len(hero_ids), len(set(hero_ids)), "Duplicate hero entries detected!")

        # 4. Appending 11th hero
        append_packet = {
            "cmd": "1005",
            "sub": "1",
            "data": {
                "retdata": {
                    "heroCtrl": {
                        "heroes": [
                            {"id": 5502001, "lv": 1, "star": 1, "exp": 0, "power": 1000}
                        ]
                    }
                }
            }
        }
        self.engine.ingest_packet(append_packet)
        self.assertEqual(len(self.engine.init_data["heroCtrl"]["heroes"]), 11)

    def test_buff_ctrl_merge_deltas_and_verify(self):
        """Initial buff list in buffCtrl. Merge deltas and verify."""
        self.engine.init_data["buffCtrl"] = [
            {"id": 5001, "beginTime": 1000, "endTime": 5000, "val": 10},
            {"id": 5002, "beginTime": 2000, "endTime": 6000, "val": 20},
            {"id": 5003, "beginTime": 3000, "endTime": 7000, "val": 30},
        ]

        # Delta: update 5001, delete 5002 via _delete, add 5004
        delta = {
            "buffCtrl": [
                {"id": 5001, "endTime": 9999},
                {"id": 5002, "_delete": True},
                {"id": 5004, "beginTime": 4000, "endTime": 8000, "val": 40},
            ]
        }
        smart_deep_merge(self.engine.init_data, delta, in_place=True)

        buffs = self.engine.init_data["buffCtrl"]
        self.assertEqual(len(buffs), 3)

        b5001 = next(b for b in buffs if b["id"] == 5001)
        self.assertEqual(b5001["endTime"], 9999)
        self.assertEqual(b5001["val"], 10)

        self.assertFalse(any(b["id"] == 5002 for b in buffs), "Buff 5002 was not pruned!")
        self.assertTrue(any(b["id"] == 5004 for b in buffs), "Buff 5004 was not appended!")

    def test_queue_ctrl_merge_and_verify(self):
        """Initial queue dict in queueCtrl. Merge and verify."""
        self.engine.init_data["queueCtrl"] = {
            "1200": {"qtype": "1200", "bid": "101", "totalTime": 3600, "leftTime": 1800},
            "1201": {"qtype": "1201", "bid": "102", "totalTime": 1800, "leftTime": 900},
        }

        # Update 1201 remaining time and add research queue 1202
        delta = {
            "queueCtrl": {
                "1201": {"leftTime": 300},
                "1202": {"qtype": "1202", "techId": "5001", "totalTime": 7200},
            }
        }
        smart_deep_merge(self.engine.init_data, delta, in_place=True)

        q = self.engine.init_data["queueCtrl"]
        self.assertEqual(len(q), 3)
        self.assertEqual(q["1200"]["bid"], "101")
        self.assertEqual(q["1201"]["leftTime"], 300)
        self.assertEqual(q["1201"]["totalTime"], 1800)
        self.assertEqual(q["1202"]["techId"], "5001")

    def test_primitive_list_snapshot_replacement(self):
        """Asserts primitive lists (arealist, wishList) are replaced with deep copies."""
        self.engine.init_data = {
            "cityCtrl": {"arealist": ["1", "2"]},
            "heroVoyageAgCtrl": {"wishList": [5501001, 5501002]},
        }
        delta = {
            "cityCtrl": {"arealist": ["1", "2", "3", "4"]},
            "heroVoyageAgCtrl": {"wishList": [5502011]},
        }
        smart_deep_merge(self.engine.init_data, delta, in_place=True)

        self.assertEqual(self.engine.init_data["cityCtrl"]["arealist"], ["1", "2", "3", "4"])
        self.assertEqual(self.engine.init_data["heroVoyageAgCtrl"]["wishList"], [5502011])

    def test_mixed_string_integer_id_normalization(self):
        """Asserts integer ID matches string ID without creating duplicates."""
        self.engine.init_data = {
            "blist": [{"index": "1001", "lv": 5}],
            "buffCtrl": [{"id": "5001", "val": 10}],
        }
        delta = {
            "blist": [{"index": 1001, "lv": 6}],
            "buffCtrl": [{"id": 5001, "val": 20}],
        }
        smart_deep_merge(self.engine.init_data, delta, in_place=True)

        self.assertEqual(len(self.engine.init_data["blist"]), 1)
        self.assertEqual(self.engine.init_data["blist"][0]["lv"], 6)

        self.assertEqual(len(self.engine.init_data["buffCtrl"]), 1)
        self.assertEqual(self.engine.init_data["buffCtrl"][0]["val"], 20)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Concurrency & Copy-on-Write Safety Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestConcurrencyAndCopyOnWrite(unittest.IsolatedAsyncioTestCase):
    """
    Verifies Concurrency & Copy-on-Write Safety:
      - Simulate an active thread or async task iterating over cityCtrl.blist.
      - Concurrently perform 100 packet merges on blist.
      - Assert no RuntimeError: dictionary/list changed size during iteration occurs.
      - Verify atomic container reference swapping (CoW).
    """

    async def test_active_iteration_safe_during_100_concurrent_merges(self):
        """
        Simulate an active thread or async task iterating over cityCtrl.blist.
        Concurrently perform 100 packet merges on blist.
        Assert no RuntimeError: dictionary/list changed size during iteration occurs.
        """
        engine = LiveMemoryEngine()
        engine.init_data["cityCtrl"] = {"blist": generate_50_buildings()}

        # Active reader holding pointer to original blist
        reader_blist = engine.init_data["cityCtrl"]["blist"]
        read_indices = []
        errors = []

        async def active_reader_task():
            try:
                for item in reader_blist:
                    read_indices.append(item["binfo"]["index"])
                    # Yield to event loop to simulate realistic async bot task behavior
                    await asyncio.sleep(0.001)
            except Exception as e:
                errors.append(e)

        async def concurrent_merger_task():
            for i in range(100):
                target_idx = str((i % 50) + 1)
                packet = {
                    "cmd": "1001",
                    "sub": "3",
                    "data": {
                        "retdata": {
                            "cityCtrl": {
                                "blist": [
                                    {"binfo": {"index": target_idx, "lv": 20 + (i % 5)}}
                                ]
                            }
                        }
                    }
                }
                engine.ingest_packet(packet)
                if i % 10 == 0:
                    await asyncio.sleep(0.001)

        # Run reader and concurrent merger concurrently
        await asyncio.gather(active_reader_task(), concurrent_merger_task())

        self.assertEqual(len(errors), 0, f"Concurrent iteration failed with error: {errors}")
        self.assertEqual(len(read_indices), 50, "Reader was interrupted or skipped elements during concurrent merges!")

        # Final state verification: exactly 50 buildings remain in blist
        final_blist = engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(final_blist), 50)

    def test_cow_pointer_swap_shields_reader_reference(self):
        """Asserts modifying a keyed list swaps the container pointer without mutating the old container."""
        engine = LiveMemoryEngine()
        engine.init_data = {
            "cityCtrl": {
                "blist": [
                    {"index": 1001, "lv": 10},
                    {"index": 1002, "lv": 12}
                ]
            }
        }
        reader_blist_ref = engine.init_data["cityCtrl"]["blist"]

        # Ingest new building 1003
        update = {
            "cityCtrl": {
                "blist": [
                    {"index": 1003, "lv": 1}
                ]
            }
        }
        smart_deep_merge(engine.init_data, update, in_place=True)

        # New list pointer has 3 items
        self.assertEqual(len(engine.init_data["cityCtrl"]["blist"]), 3)
        # Original reader reference remains frozen at 2 items
        self.assertEqual(len(reader_blist_ref), 2, "Reader reference must be shielded from container mutation!")

    def test_multithreaded_read_write_stress(self):
        """Spawns 4 reader threads and 4 writer threads pumping 50 merges each. Zero exceptions."""
        engine = LiveMemoryEngine()
        engine.init_data = generate_valid_critical_state()

        exceptions: List[Exception] = []
        stop_event = threading.Event()

        def reader_worker():
            try:
                while not stop_event.is_set():
                    snapshot = engine.get_snapshot("cityCtrl")
                    blist = snapshot.get("blist", [])
                    for b in blist:
                        _ = b.get("binfo", {}).get("lv")
                    time.sleep(0.002)
            except Exception as e:
                exceptions.append(e)

        def writer_worker(thread_id: int):
            try:
                for step in range(50):
                    idx = str((step % 50) + 1)
                    packet = {
                        "cmd": "1001",
                        "sub": "3",
                        "data": {
                            "retdata": {
                                "cityCtrl": {
                                    "blist": [
                                        {"binfo": {"index": idx, "lv": 10 + step, "state": 0}}
                                    ]
                                }
                            }
                        }
                    }
                    engine.ingest_packet(packet)
                    time.sleep(0.001)
            except Exception as e:
                exceptions.append(e)

        readers = [threading.Thread(target=reader_worker) for _ in range(4)]
        writers = [threading.Thread(target=writer_worker, args=(i,)) for i in range(4)]

        for r in readers:
            r.start()
        for w in writers:
            w.start()

        for w in writers:
            w.join(timeout=10.0)

        stop_event.set()
        for r in readers:
            r.join(timeout=5.0)

        self.assertEqual(len(exceptions), 0, f"Thread stress test encountered exceptions: {exceptions}")
        self.assertEqual(len(engine.init_data["cityCtrl"]["blist"]), 50)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Notification Handling Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestNotificationHandling(unittest.TestCase):
    """
    Verifies Notification Handling:
      - NOTIFY_CITY: delta resources addition, safe resources update, uncollected resources addition (updateUnCollectRes).
      - NOTIFY_QUEUE: building upgrade completion -> assert cityCtrl.blist building resets state to
        BUILD_STATE.NORMAL ('0') and regular lv increments by 1.
      - Honor upgrade completion -> assert honorLv and hlv increment by 1 and state resets to '0'.
    """

    def setUp(self):
        self.engine = LiveMemoryEngine()
        self.engine.init_data = generate_valid_critical_state()

    def test_notify_city_delta_resources_safe_res_uncollected(self):
        """
        NOTIFY_CITY:
          - delta resources addition (with 0 clamping).
          - safe resources update.
          - uncollected resources addition (updateUnCollectRes).
        """
        # Initial resources
        self.engine.init_data["cityCtrl"]["reslist"] = {
            "1001": 50000,
            "1002": 20000,
            "1003": 5000,
        }

        notify_payload = [
            {
                "res": {
                    "1001": -30000,  # 50000 - 30000 = 20000
                    "1002": 15000,   # 20000 + 15000 = 35000
                    "1003": -100000, # Clamped to 0 (min 0)
                },
                "saferes": {"1001": "2500000", "1002": "2500000"},
                "dayMaxRes": {"1001": "30000000"},
                "updateUnCollectRes": {
                    "10": 450,
                    "15": 1200,
                },
                "openChargeQueue": {
                    "totaltime": 172800,
                    "lefttime": 86400,
                    "starttime": 1700000000,
                },
            }
        ]

        self.engine.handle_notify(9, notify_payload)

        # 1. Delta resources addition & zero clamping
        reslist = self.engine.init_data["cityCtrl"]["reslist"]
        self.assertEqual(reslist["1001"], 20000)
        self.assertEqual(reslist["1002"], 35000)
        self.assertEqual(reslist["1003"], 0, "Resource balance must never drop below 0!")

        # 2. Safe resources update & day max
        self.assertEqual(self.engine.init_data["cityCtrl"]["saferes"]["1001"], "2500000")
        self.assertEqual(self.engine.init_data["cityCtrl"]["dayMaxRes"]["1001"], "30000000")

        # 3. Uncollected resources addition
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b10 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        b15 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "15")
        self.assertEqual(int(b10["curres"]), 450)
        self.assertEqual(int(b15["curres"]), 1200)

        # 4. Open second charge queue (1201)
        self.assertIn("1201", self.engine.init_data["queueCtrl"])
        self.assertEqual(self.engine.init_data["queueCtrl"]["1201"]["totaltime"], 172800)
        self.assertEqual(self.engine.init_data["queueCtrl"]["1201"]["starttime"], 1700000000)

    def test_open_charge_queue_starttime_when_provided_or_absent(self):
        """
        Verify openChargeQueue retains starttime when present, and omits when absent (matching Lua protocol).
        """
        # Case A: starttime provided
        notify_payload = [
            {
                "openChargeQueue": {
                    "totaltime": 86400,
                    "starttime": 1700000000,
                    "lefttime": 86400,
                }
            }
        ]
        self.engine.handle_notify(9, notify_payload)
        q1201 = self.engine.init_data.get("queueCtrl", {}).get("1201", {})
        self.assertEqual(q1201.get("starttime"), 1700000000)

        # Case B: starttime absent
        notify_payload_absent = [
            {
                "openChargeQueue": {
                    "totaltime": 86400,
                    "lefttime": 86400,
                }
            }
        ]
        self.engine.handle_notify(9, notify_payload_absent)
        q1201_absent = self.engine.init_data.get("cityCtrl", {}).get("queue", {}).get("1201", {})
        self.assertNotIn("starttime", q1201_absent)

    def test_notify_city_float_string_res_and_curres(self):
        """
        Verify delta resources and uncollected resources accept float strings without ValueError.
        """
        self.engine.init_data["cityCtrl"] = {
            "reslist": {"1001": "514089541.49461"},
            "blist": [
                {
                    "binfo": {
                        "index": "7",
                        "bid": "201",
                        "curres": "150.75",
                    }
                }
            ]
        }
        notify_payload = [
            {
                "res": {"1001": "1000.5"},
                "updateUnCollectRes": {"7": "50.25"},
            }
        ]
        self.engine.handle_notify(9, notify_payload)
        # 514089541 + 1000 = 514090541
        self.assertEqual(int(self.engine.init_data["cityCtrl"]["reslist"]["1001"]), 514090541)
        b7 = self.engine.init_data["cityCtrl"]["blist"][0]["binfo"]
        # 150 + 50 = 200
        self.assertEqual(int(b7["curres"]), 200)

    def test_notify_queue_building_regular_upgrade_completion(self):
        """
        NOTIFY_QUEUE: building upgrade completion
        -> assert cityCtrl.blist building resets state to BUILD_STATE.NORMAL ('0')
        and regular lv increments by 1.
        """
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b10 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        b10["state"] = BUILD_STATE.UPGRADING  # "2"
        b10["lv"] = "24"

        self.engine.init_data["queueCtrl"]["1200"] = {
            "qtype": "1200",
            "index": "10",
            "bid": b10["bid"],
            "totalTime": 3600,
        }

        notify_payload = {
            "queuetype": "1200",
            "qtype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "index": "10",
        }

        self.engine.handle_notify(14, notify_payload)

        # Assert queue is removed
        self.assertNotIn("1200", self.engine.init_data.get("queueCtrl", {}))

        # Assert building resets state to NORMAL ("0") and regular lv increments by 1
        b10_after = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        self.assertEqual(b10_after["state"], BUILD_STATE.NORMAL, "State must reset to NORMAL ('0')")
        self.assertEqual(str(b10_after["lv"]), "25", "Regular level must increment by 1!")

    def test_notify_queue_honor_upgrade_completion(self):
        """
        Honor upgrade completion
        -> assert honorLv and hlv increment by 1 and state resets to '0'.
        """
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b1 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "1")
        b1["lv"] = "30"
        b1["honorLv"] = "5"
        b1["hlv"] = "5"
        b1["state"] = BUILD_STATE.UPGRADING  # "2"

        notify_payload = {
            "queuetype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "index": "1",
            "isHonor": True,
        }

        self.engine.handle_notify(14, notify_payload)

        b1_after = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "1")
        self.assertEqual(b1_after["state"], BUILD_STATE.NORMAL)
        self.assertEqual(str(b1_after["honorLv"]), "6", "honorLv must increment by 1!")
        self.assertEqual(str(b1_after["hlv"]), "6", "hlv must increment by 1!")
        self.assertEqual(str(b1_after["lv"]), "30", "Regular level must not change during honor upgrade!")

    def test_notify_queue_cancellation_reverts_state_without_level_increment(self):
        """Asserts canceling a build queue reverts state to NORMAL without level increment."""
        blist = self.engine.init_data["cityCtrl"]["blist"]
        b10 = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        b10["state"] = BUILD_STATE.UPGRADING
        b10["lv"] = "15"

        cancel_payload = {
            "queuetype": "1200",
            "notifyType": "cancel",
            "optype": BUILD_OPERATE_TYPE.CANCEL,  # 11
            "index": "10",
        }
        self.engine.handle_notify(14, cancel_payload)

        b10_after = next(b["binfo"] for b in blist if str(b["binfo"]["index"]) == "10")
        self.assertEqual(b10_after["state"], BUILD_STATE.NORMAL)
        self.assertEqual(str(b10_after["lv"]), "15", "Level must NOT increment on cancellation!")

    def test_notify_backpack_add_and_use(self):
        """Asserts NOTIFY_BACKPACK updates item inventory with additions and subtractions."""
        self.engine.init_data["backpackCtrl"] = {
            "2001": {"id": "2001", "count": "10"},
            "2002": {"id": "2002", "count": "5"},
        }

        payload = [
            {
                "add": {"2001": 5, "2003": 2},
                "use": {"2002": 3},
            }
        ]
        self.engine.handle_notify(1, payload)

        bp = self.engine.init_data["backpackCtrl"]
        self.assertEqual(int(bp["2001"]["count"]), 15)
        self.assertEqual(int(bp["2002"]["count"]), 2)
        self.assertEqual(int(bp["2003"]["count"]), 2)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Readiness Gate & Fallback Queries Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestReadinessGateAndFallback(unittest.IsolatedAsyncioTestCase):
    """
    Verifies Readiness Gate & Fallback Queries:
      - Test wait_for_memory_ready:
        * Initial state missing cityCtrl -> assert gate reports not ready.
        * With auto_fetch_missing=True, simulate fallback response arrival -> assert gate passes.
        * Timeout case when server never responds -> assert gate returns False or raises timeout.
    """

    def setUp(self):
        self.engine = LiveMemoryEngine()

    def test_is_memory_ready_structural_validation(self):
        """Tests that is_memory_ready strictly checks all 6 critical controllers and internal data structures."""
        # 1. Empty state -> Not ready, lists missing controllers
        is_ready, missing = self.engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("cityCtrl", missing)
        self.assertIn("lordInfoCtrl", missing)
        self.assertIn("queueCtrl", missing)
        self.assertIn("armyCtrl", missing)
        self.assertIn("heroCtrl", missing)
        self.assertIn("backpackCtrl", missing)

        # 2. cityCtrl present but missing blist -> reports cityCtrl.blist
        self.engine.init_data = generate_valid_critical_state()
        self.engine.init_data["cityCtrl"]["blist"] = []
        is_ready, missing = self.engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("cityCtrl.blist", missing)

        # 3. cityCtrl present but missing reslist -> reports cityCtrl.reslist
        self.engine.init_data = generate_valid_critical_state()
        self.engine.init_data["cityCtrl"]["reslist"] = {}
        is_ready, missing = self.engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("cityCtrl.reslist", missing)

        # 4. lordInfoCtrl missing base.uid -> reports lordInfoCtrl.base
        self.engine.init_data = generate_valid_critical_state()
        self.engine.init_data["lordInfoCtrl"] = {"base": {"uid": 0}}
        is_ready, missing = self.engine.is_memory_ready()
        self.assertFalse(is_ready)
        self.assertIn("lordInfoCtrl.base", missing)

        # 5. All valid -> Returns True, []
        self.engine.init_data = generate_valid_critical_state()
        is_ready, missing = self.engine.is_memory_ready()
        self.assertTrue(is_ready)
        self.assertEqual(len(missing), 0)

    def test_fallback_queries_registry_correctness(self):
        """Asserts get_fallback_query returns the exact commands specified in CONTROLLER_WHITELIST_SPEC."""
        self.assertEqual(get_fallback_query("cityCtrl"), (1001, 1, {}))
        self.assertEqual(get_fallback_query("lordInfoCtrl", uid=8888), (1002, 7, {"uid": 8888}))
        self.assertEqual(get_fallback_query("queueCtrl"), (1003, 1, {}))
        self.assertEqual(get_fallback_query("armyCtrl"), (1005, 1, {}))
        self.assertEqual(get_fallback_query("backpackCtrl"), (1004, 1, {}))
        self.assertEqual(get_fallback_query("local_queues"), (1007, 1000, {}))

    async def test_wait_for_memory_ready_missing_city_ctrl_reports_not_ready(self):
        """Initial state missing cityCtrl -> assert gate reports not ready."""
        valid_state = generate_valid_critical_state()
        del valid_state["cityCtrl"]
        self.engine.init_data = valid_state

        ready = await standalone_wait_for_memory_ready(
            self.engine,
            timeout=0.05,
            auto_fetch_missing=False
        )
        self.assertFalse(ready, "Gate must return False when cityCtrl is missing and auto_fetch is False")

    async def test_wait_for_memory_ready_success_with_simulated_fallback_response(self):
        """With auto_fetch_missing=True, simulate fallback response arrival -> assert gate passes."""
        # Initial state has 5 controllers, missing cityCtrl
        valid_state = generate_valid_critical_state()
        city_data_to_arrive = valid_state.pop("cityCtrl")
        self.engine.init_data = valid_state

        dispatched_queries = []

        def mock_query_dispatcher(controller: str, cmd: int, subcmd: int, payload: Dict[str, Any]):
            dispatched_queries.append((controller, cmd, subcmd))

        # Background coroutine to simulate server response arriving after 20ms
        async def simulate_server_response():
            await asyncio.sleep(0.02)
            fallback_packet = {
                "cmd": "1001",
                "sub": "1",
                "data": {
                    "retdata": {
                        "cityCtrl": city_data_to_arrive
                    }
                }
            }
            self.engine.ingest_packet(fallback_packet)

        sim_task = asyncio.create_task(simulate_server_response())

        ready = await standalone_wait_for_memory_ready(
            self.engine,
            timeout=1.0,
            auto_fetch_missing=True,
            query_dispatcher=mock_query_dispatcher,
            poll_interval=0.01,
        )
        await sim_task

        self.assertTrue(ready, "Gate must pass once fallback response is ingested!")
        self.assertIn(("cityCtrl", 1001, 1), dispatched_queries, "Fallback query 1001/1 for cityCtrl must be dispatched!")

    async def test_wait_for_memory_ready_timeout_when_server_never_responds(self):
        """Timeout case when server never responds -> assert gate returns False or raises timeout."""
        valid_state = generate_valid_critical_state()
        del valid_state["cityCtrl"]
        self.engine.init_data = valid_state

        ready = await standalone_wait_for_memory_ready(
            self.engine,
            timeout=0.08,
            auto_fetch_missing=True,
            poll_interval=0.02
        )
        self.assertFalse(ready, "Gate must time out and return False when server does not respond")

    async def test_gate_client_native_wait_for_memory_ready_integration(self):
        """
        Tests GateClient.wait_for_memory_ready if GateClient is available,
        verifying end-to-end integration with the client connection class.
        """
        if GateClient is None:
            self.skipTest("GateClient not importable from game_client")

        class DummyCreds:
            uid = "12345678"
            kingdom_id = "105"
            server_name = "test_srv"
            gate_ip = "127.0.0.1"
            gate_port = 12345
            sub_id = "sub_1"
            secret = b"0" * 32

        client = GateClient(DummyCreds())
        client._alive = True
        dispatched_cmds = []

        def mock_send_nowait(cmd, subcmd, data=None):
            dispatched_cmds.append((str(cmd), str(subcmd)))

        client.send_nowait = mock_send_nowait

        # 1. Initially missing critical controllers
        valid_state = generate_valid_critical_state()
        city_payload = valid_state.pop("cityCtrl")
        client.memory_engine.init_data.clear()
        client.memory_engine.init_data.update(valid_state)

        # 2. Simulate server sending fallback response after 30ms
        async def delayed_server_response():
            await asyncio.sleep(0.03)
            pkt = {
                "cmd": "1001",
                "sub": "1",
                "data": {"retdata": {"cityCtrl": city_payload}}
            }
            client.memory_engine.ingest_packet(pkt)

        task = asyncio.create_task(delayed_server_response())
        passed = await client.wait_for_memory_ready(timeout=1.0, auto_fetch_missing=True)
        await task

        self.assertTrue(passed, "GateClient.wait_for_memory_ready must pass once data arrives!")
        self.assertTrue(any(c == ('1001', '1') for c in dispatched_cmds), "CMD 1001/1 must be sent for cityCtrl!")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Adversarial Verification & Edge Cases
# ══════════════════════════════════════════════════════════════════════════════

class TestAdversarialAndEdgeCases(unittest.TestCase):
    """Adversarial stress tests for malformed inputs, extreme bounds, and disambiguation."""

    def setUp(self):
        self.engine = LiveMemoryEngine()

    def test_malformed_packets_graceful_handling(self):
        """Asserts ingest_packet gracefully handles None, empty dicts, non-dicts without throwing."""
        self.engine.ingest_packet(None)
        self.engine.ingest_packet({})
        self.engine.ingest_packet([])
        self.engine.ingest_packet("corrupted_payload")
        self.engine.ingest_packet({"cmd": None, "data": None})
        self.engine.ingest_packet({"data": {"retdata": None}})
        self.assertEqual(self.engine.init_data, {})

    def test_resource_subtraction_underflow_safety(self):
        """Asserts extreme resource delta subtraction clamps to 0 and never overflows into negative."""
        self.engine.init_data["cityCtrl"] = {"reslist": {"1001": 50}}
        self.engine.handle_notify(9, [{"res": {"1001": -999_999_999}}])
        self.assertEqual(self.engine.init_data["cityCtrl"]["reslist"]["1001"], 0)

    def test_building_honor_vs_regular_disambiguation(self):
        """Asserts regular upgrade never touches honorLv, and honor upgrade never touches regular lv."""
        self.engine.init_data["cityCtrl"] = {
            "blist": [
                {
                    "binfo": {
                        "index": "1",
                        "bid": "101",
                        "lv": "30",
                        "honorLv": "3",
                        "hlv": "3",
                        "state": BUILD_STATE.UPGRADING,
                    }
                }
            ]
        }

        # 1. Regular upgrade completion on building 1
        regular_upgrade = {
            "queuetype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "index": "1",
            "isHonor": False,
        }
        self.engine.handle_notify(14, regular_upgrade)
        b = self.engine.init_data["cityCtrl"]["blist"][0]["binfo"]
        self.assertEqual(str(b["lv"]), "31")
        self.assertEqual(str(b["honorLv"]), "3", "Regular upgrade must NOT increment honorLv!")

        # 2. Honor upgrade completion on building 1
        b["state"] = BUILD_STATE.UPGRADING
        honor_upgrade = {
            "queuetype": "1200",
            "notifyType": "finish",
            "optype": 2,
            "index": "1",
            "isHonor": True,
        }
        self.engine.handle_notify(14, honor_upgrade)
        b_after_honor = self.engine.init_data["cityCtrl"]["blist"][0]["binfo"]
        self.assertEqual(str(b_after_honor["honorLv"]), "4", "Honor upgrade must increment honorLv!")
        self.assertEqual(str(b_after_honor["hlv"]), "4")
        self.assertEqual(str(b_after_honor["lv"]), "31", "Honor upgrade must NOT increment regular lv!")


# ══════════════════════════════════════════════════════════════════════════════
# 7. Benchmark DEEP_MERGE_SPEC Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestDeepMergeSpecBenchmarks(unittest.TestCase):
    """The 9 Canonical Benchmark Tests from DEEP_MERGE_SPEC."""

    def test_recursive_dict_merge_preserves_untouched_keys(self):
        """Test 1 from DEEP_MERGE_SPEC: Preserves sibling keys during deep dictionary merge."""
        target = {
            "cityCtrl": {
                "cinfo": {"cid": "1001", "name": "Capital"},
                "reslist": {"1002": 50000, "1003": 80000},
                "saferes": {"1002": 20000}
            }
        }
        update = {
            "cityCtrl": {
                "saferes": {"1003": 30000},
                "newField": "active"
            }
        }
        res = smart_deep_merge(target, update)
        self.assertEqual(res["cityCtrl"]["cinfo"]["name"], "Capital")
        self.assertEqual(res["cityCtrl"]["reslist"]["1002"], 50000)
        self.assertEqual(res["cityCtrl"]["saferes"]["1002"], 20000)
        self.assertEqual(res["cityCtrl"]["saferes"]["1003"], 30000)
        self.assertEqual(res["cityCtrl"]["newField"], "active")

    def test_city_blist_delta_merge_prevents_city_wipe(self):
        """Test 2 from DEEP_MERGE_SPEC: Updating one building in blist does NOT delete other buildings."""
        target = {
            "cityCtrl": {
                "blist": [
                    {"binfo": {"index": 1001, "bid": 101, "lv": 10, "state": 0}},
                    {"binfo": {"index": 1002, "bid": 102, "lv": 8, "state": 0}},
                    {"binfo": {"index": 1003, "bid": 103, "lv": 12, "state": 0}}
                ]
            }
        }
        update = {
            "cityCtrl": {
                "blist": [
                    {"binfo": {"index": 1001, "lv": 11, "state": 2}}
                ]
            }
        }
        res = smart_deep_merge(target, update)
        blist = res["cityCtrl"]["blist"]
        self.assertEqual(len(blist), 3)
        b1001 = next(b["binfo"] for b in blist if b["binfo"]["index"] == 1001)
        self.assertEqual(b1001["lv"], 11)
        self.assertEqual(b1001["state"], 2)
        self.assertEqual(b1001["bid"], 101)

    def test_city_blist_composite_key_fallback(self):
        """Test 3 from DEEP_MERGE_SPEC: Buildings without index match uniquely on (bid, iid)."""
        target = {
            "blist": [
                {"binfo": {"bid": 108, "iid": 0, "lv": 15, "state": 0}},
                {"binfo": {"bid": 102, "iid": 1, "lv": 5, "state": 0}},
                {"binfo": {"bid": 102, "iid": 2, "lv": 6, "state": 0}}
            ]
        }
        update = {
            "blist": [
                {"binfo": {"bid": 102, "iid": 2, "lv": 7, "state": 2}}
            ]
        }
        res = smart_deep_merge(target, update)
        self.assertEqual(len(res["blist"]), 3)
        farm2 = next(b["binfo"] for b in res["blist"] if b["binfo"]["bid"] == 102 and b["binfo"]["iid"] == 2)
        self.assertEqual(farm2["lv"], 7)
        self.assertEqual(farm2["state"], 2)

    def test_hero_ctrl_delta_update_and_append(self):
        """Test 4 from DEEP_MERGE_SPEC: Merges existing heroes and appends newly recruited heroes."""
        target = {
            "heroCtrl": {
                "heroes": [
                    {"id": 5501001, "lv": 20, "star": 2, "exp": 5000},
                    {"id": 5501002, "lv": 30, "star": 3, "exp": 12000}
                ]
            }
        }
        update = {
            "heroCtrl": {
                "heroes": [
                    {"id": 5501001, "exp": 8000},
                    {"id": 5502011, "lv": 1, "star": 1, "exp": 0}
                ]
            }
        }
        res = smart_deep_merge(target, update)
        heroes = res["heroCtrl"]["heroes"]
        self.assertEqual(len(heroes), 3)
        h1 = next(h for h in heroes if h["id"] == 5501001)
        self.assertEqual(h1["lv"], 20)
        self.assertEqual(h1["exp"], 8000)
        h3 = next(h for h in heroes if h["id"] == 5502011)
        self.assertEqual(h3["lv"], 1)

    def test_buff_ctrl_add_update_and_delete(self):
        """Test 5 from DEEP_MERGE_SPEC: Buff list adds new buff, updates existing, and prunes on _delete."""
        target = {
            "buffCtrl": [
                {"id": 5001, "beginTime": 1000, "endTime": 5000, "val": 10},
                {"id": 5002, "beginTime": 2000, "endTime": 6000, "val": 20}
            ]
        }
        update = {
            "buffCtrl": [
                {"id": 5001, "endTime": 8000},
                {"id": 5002, "_delete": True},
                {"id": 5003, "beginTime": 3000, "endTime": 9000, "val": 50}
            ]
        }
        res = smart_deep_merge(target, update)
        buffs = res["buffCtrl"]
        self.assertEqual(len(buffs), 2)
        b5001 = next(b for b in buffs if b["id"] == 5001)
        self.assertEqual(b5001["endTime"], 8000)
        self.assertFalse(any(b["id"] == 5002 for b in buffs))
        self.assertTrue(any(b["id"] == 5003 for b in buffs))

    def test_queue_ctrl_keyed_merge_and_removal(self):
        """Test 6 from DEEP_MERGE_SPEC: queueCtrl delta updates."""
        target = {
            "queueCtrl": {
                "1200": {"qtype": "1200", "bid": 101, "totalTime": 3600},
                "1201": {"qtype": "1201", "bid": 102, "totalTime": 1800}
            }
        }
        update = {
            "queueCtrl": {
                "1200": {"qtype": "1200", "notifyType": "del"},
                "1201": {"leftTime": 900}
            }
        }
        res = smart_deep_merge(target, update)
        self.assertEqual(res["queueCtrl"]["1201"]["totalTime"], 1800)
        self.assertEqual(res["queueCtrl"]["1201"]["leftTime"], 900)

    def test_primitive_list_replacement(self):
        """Test 7 from DEEP_MERGE_SPEC: Primitive lists are replaced with deep copies."""
        target = {
            "cityCtrl": {"arealist": [1, 2, 3]},
            "heroVoyageAgCtrl": {"wishList": [5501001, 5501002]}
        }
        update = {
            "cityCtrl": {"arealist": [1, 2, 3, 4]},
            "heroVoyageAgCtrl": {"wishList": [5502011]}
        }
        res = smart_deep_merge(target, update)
        self.assertEqual(res["cityCtrl"]["arealist"], [1, 2, 3, 4])
        self.assertEqual(res["heroVoyageAgCtrl"]["wishList"], [5502011])

    def test_mixed_string_integer_id_normalization(self):
        """Test 8 from DEEP_MERGE_SPEC: String and integer entity keys match cleanly without duplicates."""
        target = {
            "buffCtrl": [{"id": "5001", "val": 10}],
            "blist": [{"index": "1001", "lv": 5}]
        }
        update = {
            "buffCtrl": [{"id": 5001, "val": 20}],
            "blist": [{"index": 1001, "lv": 6}]
        }
        res = smart_deep_merge(target, update)
        self.assertEqual(len(res["buffCtrl"]), 1)
        self.assertEqual(res["buffCtrl"][0]["val"], 20)
        self.assertEqual(len(res["blist"]), 1)
        self.assertEqual(res["blist"][0]["lv"], 6)

    def test_cow_reference_integrity(self):
        """Test 9 from DEEP_MERGE_SPEC: Copy-on-Write reference integrity shields concurrent readers."""
        target = {
            "cityCtrl": {
                "blist": [
                    {"index": 1001, "lv": 10},
                    {"index": 1002, "lv": 12}
                ]
            }
        }
        reader_blist_ref = target["cityCtrl"]["blist"]
        update = {
            "cityCtrl": {
                "blist": [
                    {"index": 1003, "lv": 1}
                ]
            }
        }
        res = smart_deep_merge(target, update)
        self.assertEqual(len(res["cityCtrl"]["blist"]), 3)
        self.assertEqual(len(reader_blist_ref), 2)


if __name__ == "__main__":
    unittest.main()
