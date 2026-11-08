# -*- coding: utf-8 -*-
"""
tools/stress_m2_concurrency.py — Milestone 2 Concurrency & OCC Stress Harness
══════════════════════════════════════════════════════════════════════════════
Empirical stress test suite verifying:
1. Multi-threaded Contention: 20 concurrent threads attempting to update
   the same castle record at version 1 with expected_version=1.
   Validates: Exactly 1 success, 19 conflicts, 0 deadlocks/crashes.
2. Sequential Version Increments: 50 sequential valid updates.
   Validates: Version reaches 51 and all merged keys are intact.
3. Backward Compatibility: Call without expected_version.
   Validates: Version increments, bool(res) is True, legacy calls work.
4. HTTP Level Concurrency: Concurrent PUT requests via TestClient.
   Validates: Exactly 1 HTTP 200, 409 Conflict for contenders.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
import threading
from typing import Dict, Any, List

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db
from api_server import app, get_current_user
from fastapi.testclient import TestClient


class TestOCCConcurrencyStress(unittest.TestCase):
    """Rigorous empirical stress test harness for OCC in SQLite."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="occ_stress_")
        self.db_path = os.path.join(self.temp_dir, "stress_occ.db")
        db.init_db(self.db_path)

        # Setup test user and baseline castle
        self.uid = "test_stress_user"
        db.create_or_update_user(
            uid=self.uid,
            email="stress@example.com",
            role="user",
            db_path=self.db_path
        )
        db.update_user_subscription(
            uid=self.uid,
            max_castles_allowed=10,
            subscription_status="active",
            db_path=self.db_path
        )

        self.cid = "castle_stress_target"
        db.save_castle({
            "castle_id": self.cid,
            "user_id": self.uid,
            "email": "castle_stress@example.com",
            "password": "pass",
            "config": {"initial_key": "initial_value"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        # Override api_server environment for HTTP tests
        self.orig_env = os.environ.get("CASTLES_DB_PATH")
        os.environ["CASTLES_DB_PATH"] = self.db_path
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self.orig_env:
            os.environ["CASTLES_DB_PATH"] = self.orig_env
        else:
            os.environ.pop("CASTLES_DB_PATH", None)
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    # Task 1: 20 Concurrent Threads Contention Test
    # ══════════════════════════════════════════════════════════════════
    def test_01_twenty_threads_contention_single_winner(self):
        """20 concurrent threads update same castle at version 1 with expected_version=1.
        Exactly 1 must succeed, 19 must receive conflict: True, 0 crashes/deadlocks."""
        c_initial = db.get_castle_by_id(self.cid, db_path=self.db_path)
        self.assertEqual(c_initial["version"], 1, "Initial version must be 1")

        num_threads = 20
        barrier = threading.Barrier(num_threads)
        results: List[Dict[str, Any]] = []
        latencies: List[float] = []
        lock = threading.Lock()

        def worker(thread_idx: int):
            # Wait for all threads to align at the barrier
            barrier.wait()
            t0 = time.perf_counter()
            try:
                res = db.update_castle_config(
                    self.cid,
                    {f"thread_key_{thread_idx}": f"winner_{thread_idx}"},
                    user_id=self.uid,
                    expected_version=1,
                    db_path=self.db_path
                )
                dur = time.perf_counter() - t0
                with lock:
                    results.append({"thread_idx": thread_idx, "res": res, "duration": dur})
                    latencies.append(dur)
            except Exception as exc:
                dur = time.perf_counter() - t0
                with lock:
                    results.append({"thread_idx": thread_idx, "exception": str(exc), "duration": dur})
                    latencies.append(dur)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        t_start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)
            self.assertFalse(t.is_alive(), f"Thread timed out / deadlocked!")
        total_time = time.perf_counter() - t_start

        # Analyze results
        successes = [r for r in results if r.get("res", {}).get("success") is True]
        conflicts = [r for r in results if r.get("res", {}).get("conflict") is True]
        exceptions = [r for r in results if "exception" in r]

        print(f"\n[STRESS 1] 20 Threads Contention Results:")
        print(f"  - Total Elapsed: {total_time*1000:.2f} ms")
        print(f"  - Successes: {len(successes)} / {num_threads}")
        print(f"  - Conflicts: {len(conflicts)} / {num_threads}")
        print(f"  - Exceptions: {len(exceptions)}")
        if latencies:
            print(f"  - Latency Min: {min(latencies)*1000:.2f} ms | Max: {max(latencies)*1000:.2f} ms | Avg: {(sum(latencies)/len(latencies))*1000:.2f} ms")

        self.assertEqual(len(exceptions), 0, f"Encountered unexpected exceptions: {exceptions}")
        self.assertEqual(len(successes), 1, f"Expected exactly 1 winner, got {len(successes)}")
        self.assertEqual(len(conflicts), 19, f"Expected exactly 19 conflicts, got {len(conflicts)}")

        # Check DB state
        c_after = db.get_castle_by_id(self.cid, db_path=self.db_path)
        self.assertEqual(c_after["version"], 2, "Version must have incremented exactly once to 2")

        # Winner key must be present, other keys must NOT be present
        winner_idx = successes[0]["thread_idx"]
        self.assertIn(f"thread_key_{winner_idx}", c_after["config"])
        for i in range(num_threads):
            if i != winner_idx:
                self.assertNotIn(f"thread_key_{i}", c_after["config"])

    # ══════════════════════════════════════════════════════════════════
    # Task 2: 50 Sequential Valid Updates Test
    # ══════════════════════════════════════════════════════════════════
    def test_02_fifty_sequential_valid_updates(self):
        """Perform 50 sequential valid updates (passing incremented expected_version each time).
        Verify final version reaches 51 and all 50 keys are intact."""
        num_updates = 50
        t0 = time.perf_counter()

        for step in range(1, num_updates + 1):
            expected = step
            new_key = f"seq_key_{step}"
            new_val = f"seq_val_{step}"

            res = db.update_castle_config(
                self.cid,
                {new_key: new_val},
                user_id=self.uid,
                expected_version=expected,
                db_path=self.db_path
            )
            self.assertTrue(res.get("success"), f"Update failed at step {step}: {res}")
            self.assertEqual(res.get("version"), expected + 1, f"Expected version {expected + 1}, got {res.get('version')}")

        total_dur = time.perf_counter() - t0
        print(f"\n[STRESS 2] 50 Sequential Updates Results:")
        print(f"  - Total Elapsed: {total_dur*1000:.2f} ms (Avg: {(total_dur/num_updates)*1000:.2f} ms/update)")

        # Verify DB state
        c_final = db.get_castle_by_id(self.cid, db_path=self.db_path)
        self.assertEqual(c_final["version"], 51, f"Expected version 51, got {c_final['version']}")

        # Verify initial key still intact
        self.assertEqual(c_final["config"].get("initial_key"), "initial_value")

        # Verify all 50 sequential keys are intact
        for step in range(1, num_updates + 1):
            key = f"seq_key_{step}"
            expected_val = f"seq_val_{step}"
            self.assertIn(key, c_final["config"], f"Missing key {key} in final config")
            self.assertEqual(c_final["config"][key], expected_val)

    # ══════════════════════════════════════════════════════════════════
    # Task 3: Backward Compatibility for Legacy Callers
    # ══════════════════════════════════════════════════════════════════
    def test_03_backward_compatibility_legacy_caller(self):
        """Calling update_castle_config without expected_version:
        1. Works unconditionally (increments version).
        2. Returns OCCResult which evaluates as truthy with bool(res).
        3. Supports dictionary accessres['version'], res['success']."""
        c_before = db.get_castle_by_id(self.cid, db_path=self.db_path)
        ver_before = c_before["version"]

        # Call with only (castle_id, config_dict) — purest legacy signature
        res = db.update_castle_config(
            self.cid,
            {"legacy_setting": True, "speed": 100},
            db_path=self.db_path
        )

        # 1. Truthy check
        self.assertTrue(bool(res), "OCCResult must evaluate to True on success")
        if not res:
            self.fail("Legacy pattern 'if not res:' failed!")

        # 2. Dictionary contract
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("version"), ver_before + 1)
        self.assertIn("config", res)
        self.assertEqual(res["config"].get("legacy_setting"), True)

        # 3. Check DB persistence
        c_after = db.get_castle_by_id(self.cid, db_path=self.db_path)
        self.assertEqual(c_after["version"], ver_before + 1)
        self.assertEqual(c_after["config"]["legacy_setting"], True)

        print(f"\n[STRESS 3] Backward Compatibility Test Passed:")
        print(f"  - Version stepped: {ver_before} -> {c_after['version']}")
        print(f"  - bool(res) is True, legacy callers fully supported.")

    # ══════════════════════════════════════════════════════════════════
    # Task 4: HTTP API Concurrent Requests Test (FastAPI + TestClient)
    # ══════════════════════════════════════════════════════════════════
    def test_04_http_endpoint_concurrent_occ_race(self):
        """10 concurrent HTTP PUT requests to /api/castles/{id}/config with expected version=1.
        Verify exactly 1 returns 200, 9 return 409 Conflict."""
        # Setup dependency override for auth
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid,
            "email": "stress@example.com",
            "role": "user",
        }

        # Create fresh castle for HTTP test
        http_cid = "castle_http_occ"
        db.save_castle({
            "castle_id": http_cid,
            "user_id": self.uid,
            "email": "http_occ@example.com",
            "password": "pass",
            "config": {"mode": "auto"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        num_http_threads = 10
        barrier = threading.Barrier(num_http_threads)
        http_results: List[Dict[str, Any]] = []
        lock = threading.Lock()

        def http_worker(thread_idx: int):
            client = TestClient(app, raise_server_exceptions=False)
            barrier.wait()
            t0 = time.perf_counter()
            resp = client.put(
                f"/api/castles/{http_cid}/config",
                json={
                    "config": {"http_winner": thread_idx},
                    "version": 1
                }
            )
            dur = time.perf_counter() - t0
            with lock:
                http_results.append({
                    "thread_idx": thread_idx,
                    "status_code": resp.status_code,
                    "body": resp.json(),
                    "duration": dur
                })

        threads = [threading.Thread(target=http_worker, args=(i,)) for i in range(num_http_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        statuses = [r["status_code"] for r in http_results]
        status_200 = [r for r in http_results if r["status_code"] == 200]
        status_409 = [r for r in http_results if r["status_code"] == 409]

        print(f"\n[STRESS 4] HTTP Endpoint Concurrency Results:")
        print(f"  - Status codes: {statuses}")
        print(f"  - HTTP 200: {len(status_200)} / {num_http_threads}")
        print(f"  - HTTP 409 Conflict: {len(status_409)} / {num_http_threads}")

        self.assertEqual(len(status_200), 1, f"Expected exactly 1 HTTP 200, got {len(status_200)}")
        self.assertEqual(len(status_409), 9, f"Expected exactly 9 HTTP 409, got {len(status_409)}")

        # Verify DB version is 2
        c_final = db.get_castle_by_id(http_cid, db_path=self.db_path)
        self.assertEqual(c_final["version"], 2)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOCCConcurrencyStress)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
