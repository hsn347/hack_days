# -*- coding: utf-8 -*-
"""
tools/verify_m2_security.py — Verification Script for Milestone 2: Security & Concurrency
══════════════════════════════════════════════════════════════════════════════════════════
Verifies:
1. P0 Security: /api/local/castles/{id} auth, ownership check, and password sanitization.
2. P0 Security: /api/castle-data/{email} BOLA/IDOR prevention.
3. P0 Security: /api/bot/start parameter spoofing override with verified DB email.
4. P0 Security: 10 internal endpoints protected by admin role / X-Internal-Token / loopback.
5. Concurrency & OCC: version column migration, optimistic concurrency check, version increment.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
import threading
from typing import Dict, Any

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

from fastapi.testclient import TestClient
from fastapi import HTTPException
import core.database as db
import api_server
from api_server import app, INTERNAL_API_SECRET, get_current_user, require_admin


class TestMilestone2SecurityAndConcurrency(unittest.TestCase):
    """Hermetic verification suite for Milestone 2."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="m2_verify_")
        self.db_path = os.path.join(self.temp_dir, "test_m2.db")
        db.init_db(self.db_path)
        # Point api_server to this test DB
        self.orig_db_path = os.environ.get("CASTLES_DB_PATH")
        os.environ["CASTLES_DB_PATH"] = self.db_path

        # Setup test users
        db.create_or_update_user(uid="user_victim", email="victim@example.com", role="user", db_path=self.db_path)
        db.update_user_subscription(uid="user_victim", max_castles_allowed=5, subscription_status="active", db_path=self.db_path)
        db.create_or_update_user(uid="user_attacker", email="attacker@example.com", role="user", db_path=self.db_path)
        db.update_user_subscription(uid="user_attacker", max_castles_allowed=5, subscription_status="active", db_path=self.db_path)
        db.create_or_update_user(uid="user_admin", email="ibraboths@gmail.com", role="admin", db_path=self.db_path)

        # Setup test castles
        db.save_castle({
            "castle_id": "castle_victim_1",
            "user_id": "user_victim",
            "email": "victim_castle@example.com",
            "password": "SUPER_SECRET_VICTIM_PASSWORD",
            "config": {"task": "gather"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        db.save_castle({
            "castle_id": "castle_attacker_1",
            "user_id": "user_attacker",
            "email": "attacker_castle@example.com",
            "password": "ATTACKER_PASSWORD",
            "config": {"task": "attack"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()
        if self.orig_db_path:
            os.environ["CASTLES_DB_PATH"] = self.orig_db_path
        else:
            os.environ.pop("CASTLES_DB_PATH", None)
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    # 1. P0 Security Fix: /api/local/castles/{id}
    # ══════════════════════════════════════════════════════════════════
    def test_local_castle_requires_auth(self):
        """Unauthenticated request must be rejected with 401."""
        resp = self.client.get("/api/local/castles/castle_victim_1")
        self.assertEqual(resp.status_code, 401, f"Expected 401 Unauthorized, got {resp.status_code}")

    def test_local_castle_bola_protection(self):
        """Non-owner user cannot access victim castle (must return 403 Forbidden)."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "user_attacker",
            "email": "attacker@example.com",
            "role": "user",
        }
        resp = self.client.get("/api/local/castles/castle_victim_1")
        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden for BOLA access, got {resp.status_code}")

    def test_local_castle_strips_password_for_owner(self):
        """Owner can access own castle, but password and raw_json are stripped."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "user_victim",
            "email": "victim@example.com",
            "role": "user",
        }
        resp = self.client.get("/api/local/castles/castle_victim_1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("castle", {})
        self.assertNotIn("password", data, "CRITICAL: Plaintext password was leaked in response!")
        self.assertNotIn("raw_json", data, "raw_json should be stripped")
        self.assertEqual(data.get("castle_id"), "castle_victim_1")

    def test_local_castle_strips_password_for_admin(self):
        """Admin can access castle, but password is still stripped."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "user_admin",
            "email": "ibraboths@gmail.com",
            "role": "admin",
            "is_super_admin": True,
        }
        resp = self.client.get("/api/local/castles/castle_victim_1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("castle", {})
        self.assertNotIn("password", data, "CRITICAL: Plaintext password was leaked to admin!")

    # ══════════════════════════════════════════════════════════════════
    # 2. P0 Security Fix: /api/castle-data/{email}
    # ══════════════════════════════════════════════════════════════════
    def test_castle_data_bola_rejected(self):
        """Attacker trying to pull live castle data for victim email gets 403 Forbidden."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "user_attacker",
            "email": "attacker@example.com",
            "role": "user",
        }
        resp = self.client.get("/api/castle-data/victim_castle@example.com")
        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden for BOLA on castle-data, got {resp.status_code}")

    def test_castle_data_owner_allowed(self):
        """Owner is permitted past security check (will fail at game connect 404/503, NOT 403)."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "user_victim",
            "email": "victim@example.com",
            "role": "user",
        }
        resp = self.client.get("/api/castle-data/victim_castle@example.com")
        self.assertNotEqual(resp.status_code, 403, "Owner should not receive 403 Forbidden")

    # ══════════════════════════════════════════════════════════════════
    # 3. P0 Security Fix: /api/bot/start parameter spoofing
    # ══════════════════════════════════════════════════════════════════
    def test_bot_start_overrides_spoofed_email(self):
        """In /api/bot/start, spoofed req.email is overridden with verified DB email."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "user_victim",
            "email": "victim@example.com",
            "role": "user",
        }
        captured_req = []
        orig_internal = api_server._start_bot_internal
        try:
            def mock_internal(req):
                captured_req.append(req.email)
                return True
            api_server._start_bot_internal = mock_internal

            payload = {
                "castle_id": "castle_victim_1",
                "user_id": "user_victim",
                "email": "spoofed_target@victim.org",  # Spoofed by attacker
                "config": {},
                "loop_interval": 20
            }
            resp = self.client.post("/api/bot/start", json=payload)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(len(captured_req), 1)
            # Must be the DB email, NOT the spoofed one
            self.assertEqual(captured_req[0], "victim_castle@example.com",
                             "CRITICAL: req.email was not overridden from verified DB castle record!")
        finally:
            api_server._start_bot_internal = orig_internal

    # ══════════════════════════════════════════════════════════════════
    # 4. P0 Security Fix: 10 Internal Routes Protection
    # ══════════════════════════════════════════════════════════════════
    def test_internal_routes_block_external_unauthorized_access(self):
        """External client without credentials/token is rejected with 403 on all internal routes."""
        internal_endpoints = [
            ("POST", "/api/internal/stop-all", {}),
            ("POST", "/api/internal/restart-all", {}),
            ("POST", "/api/internal/direct-start", {"castle_id": "c1", "user_id": "u1", "email": "e@test.com"}),
            ("POST", "/api/internal/deploy-lock", {}),
            ("POST", "/api/internal/deploy-unlock", {}),
            ("POST", "/api/internal/gradual-start", {}),
            ("POST", "/api/internal/cancel-start-queue", {}),
            ("POST", "/api/internal/save-running-state", {}),
            ("GET",  "/api/internal/debug-state", None),
            ("POST", "/api/bot/conn-state", {"castle_id": "c1", "state": "connected"}),
        ]

        external_headers = {"X-Real-IP": "198.51.100.25"}
        for method, path, body in internal_endpoints:
            if method == "GET":
                resp = self.client.get(path, headers=external_headers)
            else:
                resp = self.client.post(path, json=body or {}, headers=external_headers)
            self.assertEqual(resp.status_code, 403, f"Endpoint {path} failed security! Got {resp.status_code} instead of 403.")

    def test_internal_routes_allow_internal_token(self):
        """Internal token header allows access even from remote proxy."""
        headers = {
            "X-Real-IP": "198.51.100.25",
            "X-Internal-Token": INTERNAL_API_SECRET
        }
        resp = self.client.get("/api/internal/debug-state", headers=headers)
        self.assertEqual(resp.status_code, 200, f"Expected 200 with X-Internal-Token, got {resp.status_code}")

    # ══════════════════════════════════════════════════════════════════
    # 5. Concurrency Safety & OCC (Optimistic Concurrency Control)
    # ══════════════════════════════════════════════════════════════════
    def test_version_column_present_and_defaults_to_1(self):
        """castle_states table has version column defaulting to 1."""
        with db.get_connection(self.db_path) as conn:
            row = conn.execute("SELECT version FROM castle_states WHERE castle_id = 'castle_victim_1'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["version"], 1)

    def test_occ_update_success_increments_version(self):
        """update_castle_config with matching expected_version increments version atomically."""
        cid = "castle_victim_1"
        res = db.update_castle_config(cid, {"gather": {"mode": 1}}, expected_version=1, db_path=self.db_path)
        self.assertTrue(res)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("version"), 2)

        # Read back from DB
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(c["version"], 2)
        self.assertEqual(c["config"]["gather"]["mode"], 1)

    def test_occ_conflict_detected_and_rejected(self):
        """update_castle_config with mismatched expected_version fails with conflict."""
        cid = "castle_victim_1"
        # Version is currently 1. Client provides expected_version=99 (stale)
        res = db.update_castle_config(cid, {"gather": {"mode": 99}}, expected_version=99, db_path=self.db_path)
        self.assertFalse(res)
        self.assertFalse(res.get("success"))
        self.assertTrue(res.get("conflict"))
        self.assertEqual(res.get("current_version"), 1)
        self.assertEqual(res.get("expected_version"), 99)

        # Config must NOT have been changed in DB
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(c["version"], 1)
        self.assertNotIn("gather", c["config"])

    def test_occ_http_put_conflict_returns_409(self):
        """PUT /api/castles/{id} returns 409 Conflict when expected version doesn't match."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "user_victim",
            "email": "victim@example.com",
            "role": "user",
        }
        cid = "castle_victim_1"
        # Version in DB is 1. Send version=2
        resp = self.client.put(f"/api/castles/{cid}", json={
            "config": {"task": "new_task"},
            "version": 2
        })
        self.assertEqual(resp.status_code, 409, f"Expected 409 Conflict, got {resp.status_code}")

    def test_occ_multi_threaded_race_condition(self):
        """High-concurrency race condition: 10 threads attempt update with expected_version=1.
        Exactly 1 must succeed, 9 must be rejected with conflict."""
        cid = "c_occ_race"
        db.save_castle({
            "castle_id": cid,
            "user_id": "user_victim",
            "email": "race@test.com",
            "config": {"base": 0},
            "is_active": 1,
        }, db_path=self.db_path)

        results = []
        threads = []

        def attempt_update(thread_id: int):
            res = db.update_castle_config(
                cid,
                {"thread_winner": thread_id},
                expected_version=1,
                db_path=self.db_path
            )
            results.append(res)

        for i in range(10):
            t = threading.Thread(target=attempt_update, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r.get("success")]
        conflicts = [r for r in results if r.get("conflict")]

        self.assertEqual(len(successes), 1, f"Expected exactly 1 OCC success, got {len(successes)}")
        self.assertEqual(len(conflicts), 9, f"Expected exactly 9 OCC conflicts, got {len(conflicts)}")

        # Verify DB version is now exactly 2
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(c["version"], 2)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMilestone2SecurityAndConcurrency)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)
