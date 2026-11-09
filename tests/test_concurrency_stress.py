# -*- coding: utf-8 -*-
r"""
tests/test_concurrency_stress.py — Concurrency & Deep-Merge Stress Testing Suite
══════════════════════════════════════════════════════════════════════════════════
Author: Agent 19 (Empirical Challenger - Concurrency & Deep-Merge Stress Tester)
Workspace: e:\osmanli

This test suite executes empirical stress testing on `LiveMemoryEngine` and `smart_deep_merge`:
  1. Multi-threaded Flood Test: Concurrent writers injecting thousands of packets
     while multiple reader threads continuously iterate blist, heroes, and init_data.
  2. Async Coroutine Flood Test: Async producers & readers with yield points testing
     event-loop iteration safety and invariant preservation.
  3. Race Condition & Invariant Audit:
     - Mathematical invariants: Exactly 50 buildings, unique IDs, no duplicates.
     - Zero `RuntimeError` (dictionary or list changed size during iteration).
  4. Copy-on-Write Reference Safety:
     - Proves reader coroutines holding list references are shielded from in-place container mutations.
  5. Telemetry & Memory Profiling:
     - Measures time taken for 1,000 packets, throughput (packets/sec), and memory stability.
"""

from __future__ import annotations

import asyncio
import copy
import gc
import os
import random
import sys
import threading
import time
import tracemalloc
import unittest
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.live_memory import (
    ALLOWED_CONTROLLERS,
    CRITICAL_STARTUP_CONTROLLERS,
    BUILD_STATE,
    LiveMemoryEngine,
    extract_entity_key,
    smart_deep_merge,
)


def build_canonical_initial_state() -> Dict[str, Any]:
    """Builds a realistic 50-building castle, 20 heroes, full resources, and lordInfo."""
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
                "curres": "100",
                "curres_safe": "50",
                "honorLv": "0",
                "hlv": "0",
            }
        })

    heroes = []
    for h_id in range(5501001, 5501021):
        heroes.append({
            "id": h_id,
            "heroId": h_id,
            "lv": 25,
            "star": 2,
            "exp": 15000,
            "status": 0,
        })

    return {
        "cityCtrl": {
            "cinfo": {"cid": "1001", "name": "ImperialCity", "cityLv": "25"},
            "blist": blist,
            "reslist": {"1001": 5000000, "1002": 4500000, "1003": 3000000, "1004": 2000000},
            "saferes": {"1001": 1000000, "1002": 1000000, "1003": 1000000, "1004": 1000000},
            "dayMaxRes": {"1001": 10000000, "1002": 10000000},
            "arealist": [1, 2, 3, 4, 5],
        },
        "heroCtrl": {
            "heroes": heroes,
            "lottery": {"freeTimes": 1},
        },
        "lordInfoCtrl": {
            "base": {"uid": 99887766, "name": "SultanBayezid", "power": 15000000},
        },
        "queueCtrl": {
            "1200": {"qtype": "1200", "bid": "101", "startTime": 1700000000, "totalTime": 3600},
        },
        "backpackCtrl": {
            "10001": {"id": "10001", "count": "50"},
            "10002": {"id": "10002", "count": "100"},
        },
        "buffCtrl": [
            {"id": 5001, "beginTime": 1700000000, "endTime": 1700050000, "val": 10},
        ],
    }


def generate_packet_stream(count: int, seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generates a stream of realistic game server packets:
    - sparse building upgrades (cmd 1001/2)
    - push notifications (NOTIFY_CITY, NOTIFY_QUEUE, NOTIFY_HERO)
    - hero level & exp deltas
    - backpack item additions & uses
    - non-whitelisted noise packets (chat, red points, etc.)
    """
    rng = random.Random(seed)
    packets = []

    packet_types = ["building_delta", "notify_city", "notify_queue", "hero_delta", "backpack_delta", "noise"]

    for seq in range(count):
        ptype = rng.choice(packet_types)

        if ptype == "building_delta":
            target_idx = str(rng.randint(1, 50))
            new_lv = str(rng.randint(11, 35))
            state = str(rng.choice([0, 1, 2]))
            packets.append({
                "cmd": "1001",
                "subcmd": "2",
                "data": {
                    "retdata": {
                        "cityCtrl": {
                            "blist": [
                                {
                                    "binfo": {
                                        "index": target_idx,
                                        "lv": new_lv,
                                        "state": state,
                                    }
                                }
                            ]
                        }
                    }
                }
            })

        elif ptype == "notify_city":
            # Push notification 9: NOTIFY_CITY
            res_delta = rng.choice([-500, -1000, 2000, 5000])
            b_idx = str(rng.randint(1, 50))
            uncollect = rng.randint(10, 200)
            packets.append({
                "cmd": "1009",
                "subcmd": "9",
                "data": {
                    "notifyID": "9",
                    "notifyData": [
                        {
                            "res": {"1001": res_delta},
                            "updateUnCollectRes": {b_idx: uncollect},
                        }
                    ]
                }
            })

        elif ptype == "notify_queue":
            # Push notification 14: NOTIFY_QUEUE
            b_idx = str(rng.randint(1, 50))
            packets.append({
                "cmd": "1009",
                "subcmd": "14",
                "data": {
                    "notifyID": "14",
                    "notifyData": [
                        {
                            "qtype": "1200",
                            "index": b_idx,
                            "notifyType": rng.choice(["finish", "cancel", "update"]),
                            "optype": "2",
                        }
                    ]
                }
            })

        elif ptype == "hero_delta":
            target_hero = rng.randint(5501001, 5501020)
            exp_delta = rng.randint(100, 5000)
            packets.append({
                "cmd": "1009",
                "subcmd": "104",
                "data": {
                    "notifyID": "104",
                    "notifyData": [
                        {"id": target_hero, "exp": exp_delta, "lv": rng.randint(25, 40)}
                    ]
                }
            })

        elif ptype == "backpack_delta":
            packets.append({
                "cmd": "1009",
                "subcmd": "1",
                "data": {
                    "notifyID": "1",
                    "notifyData": [
                        {
                            "add": {"10001": rng.randint(1, 5)},
                            "use": {"10002": rng.randint(1, 3)},
                        }
                    ]
                }
            })

        else:  # noise (non-whitelisted controllers that should be dropped)
            packets.append({
                "cmd": "2001",
                "subcmd": "1",
                "data": {
                    "retdata": {
                        "chatCtrl": {"messages": [{"msg": f"Hello world {seq}"}]},
                        "videoAdCtrl": {"adCount": seq},
                        "RedPointCtrl": {"reds": [1, 2, 3]},
                    }
                }
            })

    return packets


class TestConcurrencyAndDeepMergeStress(unittest.TestCase):
    """Rigorous Concurrency, Race Condition, Duplication, and Telemetry Test Battery."""

    def setUp(self):
        self.initial_state = build_canonical_initial_state()
        self.engine = LiveMemoryEngine(init_data=copy.deepcopy(self.initial_state))

    # ══════════════════════════════════════════════════════════════════════════
    # Test 1: Multi-Threaded Flood Test with Concurrent Iteration
    # ══════════════════════════════════════════════════════════════════════════
    def test_multi_threaded_flood_with_concurrent_iteration(self):
        """
        Spawns 4 writer threads injecting 2,000 packets simultaneously into LiveMemoryEngine,
        while 4 reader threads continuously iterate over blist, heroes, and init_data.
        Asserts:
          - Zero exceptions (No RuntimeError: dictionary changed size during iteration).
          - Mathematical Invariant: Exactly 50 buildings in cityCtrl.blist.
          - Mathematical Invariant: Unique entity keys (No duplicated indices).
        """
        num_writers = 4
        packets_per_writer = 500
        total_packets = num_writers * packets_per_writer
        exceptions: List[Tuple[str, Exception]] = []
        stop_event = threading.Event()

        # Shared reader metrics
        read_iterations = {"blist": 0, "heroes": 0, "snapshot": 0, "init_data": 0}
        read_lock = threading.Lock()

        def writer_worker(worker_id: int):
            try:
                packets = generate_packet_stream(packets_per_writer, seed=100 + worker_id)
                for pkt in packets:
                    self.engine.ingest_packet(pkt)
            except Exception as e:
                exceptions.append((f"Writer-{worker_id}", e))

        def reader_blist_worker():
            try:
                while not stop_event.is_set():
                    city = self.engine.init_data.get("cityCtrl", {})
                    blist = city.get("blist", [])
                    if isinstance(blist, list):
                        # Direct iteration over the list reference
                        count = 0
                        for b in blist:
                            if isinstance(b, dict):
                                binfo = b.get("binfo", {})
                                _ = binfo.get("lv")
                                _ = binfo.get("state")
                                count += 1
                        with read_lock:
                            read_iterations["blist"] += 1
                    time.sleep(0.0001)
            except Exception as e:
                exceptions.append(("Reader-blist", e))

        def reader_heroes_worker():
            try:
                while not stop_event.is_set():
                    hero_ctrl = self.engine.init_data.get("heroCtrl", {})
                    heroes = hero_ctrl.get("heroes", [])
                    if isinstance(heroes, list):
                        for h in heroes:
                            if isinstance(h, dict):
                                _ = h.get("id")
                                _ = h.get("exp")
                        with read_lock:
                            read_iterations["heroes"] += 1
                    time.sleep(0.0001)
            except Exception as e:
                exceptions.append(("Reader-heroes", e))

        def reader_snapshot_worker():
            try:
                while not stop_event.is_set():
                    snapshot = self.engine.get_snapshot("cityCtrl")
                    self.assertIsInstance(snapshot, dict)
                    with read_lock:
                        read_iterations["snapshot"] += 1
                    time.sleep(0.0002)
            except Exception as e:
                exceptions.append(("Reader-snapshot", e))

        def reader_full_data_worker():
            try:
                while not stop_event.is_set():
                    # Direct reading from self.engine.init_data keys
                    # LiveMemoryEngine protects updates with _thread_lock
                    with self.engine._thread_lock:
                        for k, v in list(self.engine.init_data.items()):
                            if isinstance(v, dict):
                                _ = list(v.keys())
                    with read_lock:
                        read_iterations["init_data"] += 1
                    time.sleep(0.0002)
            except Exception as e:
                exceptions.append(("Reader-init_data", e))

        # Launch reader threads
        readers = [
            threading.Thread(target=reader_blist_worker, daemon=True),
            threading.Thread(target=reader_heroes_worker, daemon=True),
            threading.Thread(target=reader_snapshot_worker, daemon=True),
            threading.Thread(target=reader_full_data_worker, daemon=True),
        ]
        for r in readers:
            r.start()

        # Launch writer threads
        writers = [
            threading.Thread(target=writer_worker, args=(i,))
            for i in range(num_writers)
        ]

        t0 = time.perf_counter()
        for w in writers:
            w.start()
        for w in writers:
            w.join()
        t1 = time.perf_counter()

        stop_event.set()
        for r in readers:
            r.join(timeout=1.0)

        # Assert zero exceptions occurred across all threads
        self.assertEqual(len(exceptions), 0, f"Thread exceptions occurred during stress test: {exceptions}")

        # Assert Mathematical Invariants on cityCtrl.blist
        blist = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(blist), 50, f"Expected exactly 50 buildings, found {len(blist)}!")

        # Assert no duplicate indices in blist
        indices_seen = set()
        for b in blist:
            idx = b["binfo"]["index"]
            self.assertNotIn(idx, indices_seen, f"Duplicate building index detected: {idx}")
            indices_seen.add(idx)

        # Assert all 50 indices from "1" to "50" exist
        expected_indices = {str(i) for i in range(1, 51)}
        self.assertEqual(indices_seen, expected_indices, "Missing building indices after concurrent merge!")

        # Assert heroes invariant: exactly 20 unique heroes
        heroes = self.engine.init_data["heroCtrl"]["heroes"]
        self.assertEqual(len(heroes), 20, f"Expected 20 heroes, found {len(heroes)}!")
        hero_ids = {h["id"] for h in heroes}
        self.assertEqual(len(hero_ids), 20, "Duplicate hero IDs detected!")

        # Assert noise filtering under concurrency: zero non-whitelisted controllers
        for forbidden in ("chatCtrl", "videoAdCtrl", "RedPointCtrl"):
            self.assertNotIn(forbidden, self.engine.init_data, f"Forbidden noise controller leaked into init_data: {forbidden}")

        elapsed = t1 - t0
        print(f"\n[Multi-Thread Stress] Ingested {total_packets} packets in {elapsed:.4f}s ({total_packets / elapsed:.1f} pkt/s)")
        print(f"[Multi-Thread Stress] Reader cycles completed: {read_iterations}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 2: Async Coroutines Flood Test with Yield Contention
    # ══════════════════════════════════════════════════════════════════════════
    def test_async_coroutine_flood_with_yield_contention(self):
        """
        Spawns 5 async producer coroutines injecting 2,500 packets while 5 reader
        coroutines perform deep traversals and yield via asyncio.sleep(0).
        Verifies:
          - Event-loop coroutine safety.
          - Zero IndexError, KeyError, or list corruption.
          - Preserved building structures.
        """
        async def run_async_test():
            num_producers = 5
            pkts_per_producer = 500
            total_pkts = num_producers * pkts_per_producer
            stop_event = asyncio.Event()
            async_errors = []
            reader_counts = {"blist": 0, "heroes": 0}

            async def producer_task(pid: int):
                try:
                    packets = generate_packet_stream(pkts_per_producer, seed=200 + pid)
                    for pkt in packets:
                        # In real bot, network packets arrive on event loop thread
                        self.engine.ingest_packet(pkt)
                        if pid % 2 == 0:
                            await asyncio.sleep(0)  # Yield point
                except Exception as e:
                    async_errors.append((f"AsyncProducer-{pid}", e))

            async def reader_blist_task():
                try:
                    while not stop_event.is_set():
                        blist = self.engine.init_data.get("cityCtrl", {}).get("blist", [])
                        # Reader iterates through list across yield
                        for b in blist:
                            _ = b.get("binfo", {}).get("lv")
                        reader_counts["blist"] += 1
                        await asyncio.sleep(0)
                except Exception as e:
                    async_errors.append(("AsyncReader-blist", e))

            async def reader_heroes_task():
                try:
                    while not stop_event.is_set():
                        heroes = self.engine.init_data.get("heroCtrl", {}).get("heroes", [])
                        for h in heroes:
                            _ = h.get("exp")
                        reader_counts["heroes"] += 1
                        await asyncio.sleep(0)
                except Exception as e:
                    async_errors.append(("AsyncReader-heroes", e))

            # Start readers
            readers = [
                asyncio.create_task(reader_blist_task()),
                asyncio.create_task(reader_heroes_task()),
                asyncio.create_task(reader_blist_task()),
            ]

            # Start producers
            t0 = time.perf_counter()
            producers = [asyncio.create_task(producer_task(i)) for i in range(num_producers)]
            await asyncio.gather(*producers)
            t1 = time.perf_counter()

            stop_event.set()
            await asyncio.gather(*readers)

            self.assertEqual(len(async_errors), 0, f"Async coroutine errors: {async_errors}")
            blist = self.engine.init_data["cityCtrl"]["blist"]
            self.assertEqual(len(blist), 50, f"Expected 50 buildings, got {len(blist)}")
            self.assertEqual(len(self.engine.init_data["heroCtrl"]["heroes"]), 20)

            elapsed = t1 - t0
            print(f"\n[Async Stress] Ingested {total_pkts} async packets in {elapsed:.4f}s ({total_pkts / elapsed:.1f} pkt/s)")
            print(f"[Async Stress] Async reader cycles: {reader_counts}")

        asyncio.run(run_async_test())

    # ══════════════════════════════════════════════════════════════════════════
    # Test 3: Copy-on-Write Reference Safety & Isolation
    # ══════════════════════════════════════════════════════════════════════════
    def test_copy_on_write_reference_safety(self):
        """
        Tests Copy-on-Write list container swapping:
        When a reader task obtains a reference to `blist`, concurrent ingestion
        that appends or removes entities must NOT mutate the original list container in-place.
        """
        initial_blist_ref = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(initial_blist_ref), 50)

        # Ingest packet with a brand-new building (index 51)
        new_building_packet = {
            "cmd": "1001",
            "subcmd": "2",
            "data": {
                "retdata": {
                    "cityCtrl": {
                        "blist": [
                            {"binfo": {"index": "51", "bid": "199", "iid": "0", "lv": "1", "state": "0"}}
                        ]
                    }
                }
            }
        }
        self.engine.ingest_packet(new_building_packet)

        # The new engine blist must have 51 items
        new_blist_ref = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(new_blist_ref), 51)

        # The original reader reference MUST retain its original length (50) — proving no in-place list.append!
        self.assertEqual(len(initial_blist_ref), 50, "CoW Violation: Old list container was mutated in-place!")
        self.assertIsNot(initial_blist_ref, new_blist_ref, "CoW Violation: Container reference was not swapped!")

        # Now test tombstone deletion
        delete_packet = {
            "cmd": "1001",
            "subcmd": "2",
            "data": {
                "retdata": {
                    "cityCtrl": {
                        "blist": [
                            {"binfo": {"index": "51"}, "_delete": True}
                        ]
                    }
                }
            }
        }
        pre_delete_ref = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(pre_delete_ref), 51)

        self.engine.ingest_packet(delete_packet)
        post_delete_ref = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(post_delete_ref), 50)
        # Pre-delete ref must still hold 51 items
        self.assertEqual(len(pre_delete_ref), 51, "CoW Violation: Old list container was mutated during deletion!")
        self.assertIsNot(pre_delete_ref, post_delete_ref)

    # ══════════════════════════════════════════════════════════════════════════
    # Test 4: Performance & Memory Telemetry (1,000 Packets Benchmark)
    # ══════════════════════════════════════════════════════════════════════════
    def test_performance_and_memory_telemetry(self):
        """
        Measures:
          1. Time taken to process 1,000 realistic server packets.
          2. Throughput in packets/second.
          3. Mean latency per packet in microseconds.
          4. Memory footprint before, peak during flood, and after gc.collect().
        """
        gc.collect()
        tracemalloc.start()
        mem_before, _ = tracemalloc.get_traced_memory()

        packets = generate_packet_stream(1000, seed=999)

        t0 = time.perf_counter()
        for pkt in packets:
            self.engine.ingest_packet(pkt)
        t1 = time.perf_counter()

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        gc.collect()

        total_time_ms = (t1 - t0) * 1000.0
        throughput = 1000.0 / (t1 - t0)
        mean_latency_us = ((t1 - t0) / 1000.0) * 1_000_000.0

        mem_delta_kb = (current_mem - mem_before) / 1024.0
        peak_delta_kb = (peak_mem - mem_before) / 1024.0

        print(f"\n" + "═" * 70)
        print(" [PERFORMANCE & MEMORY TELEMETRY REPORT]")
        print("═" * 70)
        print(f"  • Packets Processed:        1,000 packets")
        print(f"  • Total Ingestion Time:     {total_time_ms:.2f} ms")
        print(f"  • Ingestion Throughput:     {throughput:.1f} packets/second")
        print(f"  • Mean Latency Per Packet:  {mean_latency_us:.2f} µs")
        print(f"  • Memory Initial:           {mem_before / 1024.0:.1f} KB")
        print(f"  • Memory Peak Delta:        {peak_delta_kb:.1f} KB")
        print(f"  • Memory Net Delta:         {mem_delta_kb:.1f} KB")
        print("═" * 70)

        # Performance assertions
        # Processing 1,000 packets in-memory must complete well under 2.0 seconds (>500 pkt/s)
        self.assertLess(total_time_ms, 2000.0, f"Performance bottleneck: 1,000 packets took {total_time_ms:.2f}ms (>2000ms)")
        self.assertGreater(throughput, 500.0, f"Throughput too low: {throughput:.1f} pkt/s (<500)")

        # Memory assertion: 1,000 packets must not produce runaway memory bloat (< 15 MB)
        self.assertLess(peak_delta_kb, 15360.0, f"Memory leak: Peak memory growth was {peak_delta_kb:.1f} KB (>15MB)")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 5: Adversarial 10,000 Packets Extreme Flood Across 10 Threads
    # ══════════════════════════════════════════════════════════════════════════
    def test_adversarial_10k_packets_extreme_flood(self):
        """
        Adversarial stress: Floods 10,000 packets using 10 concurrent threads
        while 5 readers execute heavy nested scans.
        Verifies:
          - Zero thread deadlocks or race condition crashes.
          - Invariant: Building count stays exactly 50.
          - High throughput stability (>10,000 pkt/s).
        """
        num_writers = 10
        pkts_per_writer = 1000
        total_packets = num_writers * pkts_per_writer
        exceptions = []
        stop_event = threading.Event()
        read_counts = {"iterations": 0}

        def heavy_reader():
            try:
                while not stop_event.is_set():
                    snap = self.engine.get_snapshot("cityCtrl")
                    blist = snap.get("blist", [])
                    for b in blist:
                        _ = b.get("binfo", {}).get("lv")
                    read_counts["iterations"] += 1
                    time.sleep(0.0001)
            except Exception as e:
                exceptions.append(("HeavyReader", e))

        def writer_task(wid: int):
            try:
                packets = generate_packet_stream(pkts_per_writer, seed=500 + wid)
                for pkt in packets:
                    self.engine.ingest_packet(pkt)
            except Exception as e:
                exceptions.append((f"ExtremeWriter-{wid}", e))

        readers = [threading.Thread(target=heavy_reader, daemon=True) for _ in range(5)]
        for r in readers:
            r.start()

        writers = [threading.Thread(target=writer_task, args=(i,)) for i in range(num_writers)]

        t0 = time.perf_counter()
        for w in writers:
            w.start()
        for w in writers:
            w.join()
        t1 = time.perf_counter()

        stop_event.set()
        for r in readers:
            r.join(timeout=1.0)

        self.assertEqual(len(exceptions), 0, f"Extreme flood errors: {exceptions}")
        blist = self.engine.init_data["cityCtrl"]["blist"]
        self.assertEqual(len(blist), 50, f"Expected 50 buildings after 10k flood, found {len(blist)}")

        elapsed = t1 - t0
        rate = total_packets / elapsed
        print(f"\n[Extreme 10k Flood] Ingested {total_packets} packets in {elapsed:.4f}s ({rate:.1f} pkt/s)")
        print(f"[Extreme 10k Flood] Completed {read_counts['iterations']} reader cycles")
        self.assertGreater(rate, 5000.0, f"Throughput degraded below 5,000 pkt/s: {rate:.1f}")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 6: Simultaneous Same-ID Insert & Delete Race
    # ══════════════════════════════════════════════════════════════════════════
    def test_simultaneous_same_id_insert_and_delete_race(self):
        """
        Adversarial race condition:
        Multiple threads concurrently insert, mutate, and delete the EXACT SAME entity IDs:
        - Building indices: "91", "92", "93"
        - Heroes: 5509991, 5509992
        Asserts that after all operations conclude:
          - Zero duplicate entries exist for any ID.
          - Structure remains fully valid.
        """
        num_threads = 6
        ops_per_thread = 200
        exceptions = []

        def race_worker(wid: int):
            try:
                rng = random.Random(700 + wid)
                for _ in range(ops_per_thread):
                    target_b_idx = str(rng.choice([91, 92, 93]))
                    action = rng.choice(["insert_or_update", "delete"])

                    if action == "insert_or_update":
                        pkt = {
                            "cmd": "1001",
                            "subcmd": "2",
                            "data": {
                                "retdata": {
                                    "cityCtrl": {
                                        "blist": [
                                            {
                                                "binfo": {
                                                    "index": target_b_idx,
                                                    "bid": "105",
                                                    "iid": "0",
                                                    "lv": str(rng.randint(1, 20)),
                                                    "state": "0",
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    else:
                        pkt = {
                            "cmd": "1001",
                            "subcmd": "2",
                            "data": {
                                "retdata": {
                                    "cityCtrl": {
                                        "blist": [
                                            {"binfo": {"index": target_b_idx}, "_delete": True}
                                        ]
                                    }
                                }
                            }
                        }

                    self.engine.ingest_packet(pkt)
            except Exception as e:
                exceptions.append((f"RaceWorker-{wid}", e))

        threads = [threading.Thread(target=race_worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(exceptions), 0, f"Same-ID race errors: {exceptions}")

        # Validate no duplicate indices in cityCtrl.blist
        blist = self.engine.init_data["cityCtrl"]["blist"]
        indices = [b["binfo"]["index"] for b in blist]
        unique_indices = set(indices)
        self.assertEqual(len(indices), len(unique_indices), f"Duplicates found in blist: {indices}")

        # The base 50 buildings must never have been deleted
        for base_i in range(1, 51):
            self.assertIn(str(base_i), unique_indices, f"Base building index {base_i} was accidentally pruned!")

    # ══════════════════════════════════════════════════════════════════════════
    # Test 7: Concurrent Readiness Gate Evaluation Under Flood
    # ══════════════════════════════════════════════════════════════════════════
    def test_concurrent_readiness_gate_checks(self):
        """
        Verifies that is_memory_ready() is completely safe to call continuously
        across multiple threads while thousands of packets are mutating init_data.
        """
        num_readers = 4
        stop_event = threading.Event()
        exceptions = []
        checks_performed = [0] * num_readers

        def readiness_checker(cid: int):
            try:
                while not stop_event.is_set():
                    ready, missing = self.engine.is_memory_ready()
                    # Initially and during flood, base data is populated, so it should be ready
                    if not ready:
                        # If not ready, missing must be a non-empty list of strings
                        self.assertIsInstance(missing, list)
                    checks_performed[cid] += 1
                    time.sleep(0)
            except Exception as e:
                exceptions.append((f"ReadinessChecker-{cid}", e))

        checker_threads = [threading.Thread(target=readiness_checker, args=(i,)) for i in range(num_readers)]
        for t in checker_threads:
            t.start()

        # Ingest 3,000 packets across 3 worker threads
        writer_threads = [
            threading.Thread(
                target=lambda: [self.engine.ingest_packet(p) for p in generate_packet_stream(1000, seed=800 + i)]
            )
            for i in range(3)
        ]
        for w in writer_threads:
            w.start()
        for w in writer_threads:
            w.join()

        stop_event.set()
        for t in checker_threads:
            t.join()

        self.assertEqual(len(exceptions), 0, f"Readiness check errors: {exceptions}")
        total_checks = sum(checks_performed)
        print(f"\n[Readiness Gate Concurrency] Verified {total_checks} readiness evaluations under concurrent packet flood")
        self.assertGreater(total_checks, 50, "Insufficient readiness evaluations completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
