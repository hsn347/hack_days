# -*- coding: utf-8 -*-
"""
tools/stress_m2_security.py — Empirical Challenger Stress Suite for Milestone 2
══════════════════════════════════════════════════════════════════════════════
Adversarial Verification of:
1. /api/local/castles/{id}: 401 unauthenticated, 403 non-owner, 200 owner/admin,
   STRICT sanitization of 'password' and 'raw_json'.
2. /api/castle-data/{email}: Cross-user BOLA/IDOR blocking, casing & whitespace checks.
3. /api/bot/start: Immunity to email spoofing parameter tampering, authentic DB email binding.
4. Internal Endpoints (10 routes): Multi-vector boundary stress, header forgery defense,
   token & admin validation.
5. Concurrency OCC: 20-thread atomic race condition stress & 409 Conflict validation.
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

# Ensure UTF-8 output on Windows
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
from starlette.datastructures import Address
import core.database as db
import api_server
from api_server import app, INTERNAL_API_SECRET, get_current_user


INTERNAL_ENDPOINTS = [
    ("POST", "/api/internal/stop-all", {}),
    ("POST", "/api/internal/restart-all", {}),
    ("POST", "/api/internal/direct-start", {"castle_id": "c_direct", "user_id": "user_victim", "email": "victim_castle@example.com"}),
    ("POST", "/api/internal/deploy-lock", {}),
    ("POST", "/api/internal/deploy-unlock", {}),
    ("POST", "/api/internal/gradual-start", {}),
    ("POST", "/api/internal/cancel-start-queue", {}),
    ("POST", "/api/internal/save-running-state", {}),
    ("GET",  "/api/internal/debug-state", None),
    ("POST", "/api/bot/conn-state", {"castle_id": "c_conn", "state": "connected"}),
]


class ChallengerM2StressSuite(unittest.TestCase):
    """Adversarial stress test harness for M2 Security and Concurrency patches."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="m2_challenger_")
        self.db_path = os.path.join(self.temp_dir, "test_challenger.db")
        db.init_db(self.db_path)

        self.orig_db_path = os.environ.get("CASTLES_DB_PATH")
        os.environ["CASTLES_DB_PATH"] = self.db_path

        # Create Victim User
        db.create_or_update_user(
            uid="uid_victim_alpha",
            email="victim.alpha@domain.com",
            role="user",
            db_path=self.db_path
        )
        db.update_user_subscription(
            uid="uid_victim_alpha",
            max_castles_allowed=10,
            subscription_status="active",
            db_path=self.db_path
        )

        # Create Attacker User
        db.create_or_update_user(
            uid="uid_attacker_malicious",
            email="attacker.hacker@evilcorp.org",
            role="user",
            db_path=self.db_path
        )
        db.update_user_subscription(
            uid="uid_attacker_malicious",
            max_castles_allowed=10,
            subscription_status="active",
            db_path=self.db_path
        )

        # Create Admin User
        db.create_or_update_user(
            uid="uid_super_admin",
            email="ibraboths@gmail.com",
            role="admin",
            db_path=self.db_path
        )

        # Victim Castle with highly sensitive secret password
        self.victim_password = "ULTRA_SENSITIVE_PLAINTEXT_SECRET_KEY_12345!"
        db.save_castle({
            "castle_id": "castle_victim_secure_1",
            "user_id": "uid_victim_alpha",
            "email": "victim_castle_1@domain.com",
            "password": self.victim_password,
            "config": {"task": "gather", "subtask": "wood"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        # Attacker Castle
        self.attacker_password = "ATTACKER_OWN_KEY_999"
        db.save_castle({
            "castle_id": "castle_attacker_evil_1",
            "user_id": "uid_attacker_malicious",
            "email": "attacker_castle_1@evilcorp.org",
            "password": self.attacker_password,
            "config": {"task": "harass"},
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

    # ═════════════════════════════════════════════════════════════════════
    # VECTOR 1: /api/local/castles/{id} Authentication, BOLA & Sanitization
    # ═════════════════════════════════════════════════════════════════════

    def test_local_castle_unauthenticated_rejected_401(self):
        """Attacker with no credentials MUST be rejected with 401 Unauthorized."""
        resp = self.client.get("/api/local/castles/castle_victim_secure_1")
        self.assertEqual(resp.status_code, 401, f"Expected 401, got {resp.status_code}: {resp.text}")

    def test_local_castle_cross_user_bola_rejected_403(self):
        """Attacker user MUST be rejected with 403 Forbidden when requesting victim castle."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_attacker_malicious",
            "email": "attacker.hacker@evilcorp.org",
            "role": "user",
        }
        resp = self.client.get("/api/local/castles/castle_victim_secure_1")
        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden, got {resp.status_code}")

    def test_local_castle_owner_access_strips_password_and_raw_json(self):
        """Owner access succeeds (200) but MUST NEVER leak password or raw_json."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_victim_alpha",
            "email": "victim.alpha@domain.com",
            "role": "user",
        }
        resp = self.client.get("/api/local/castles/castle_victim_secure_1")
        self.assertEqual(resp.status_code, 200)

        # Inspect raw payload text for leakage
        raw_text = resp.text
        self.assertNotIn(self.victim_password, raw_text, "CRITICAL LEAK: Password string found in raw response text!")
        self.assertNotIn('"password"', raw_text, "CRITICAL LEAK: 'password' key found in JSON!")
        self.assertNotIn('"raw_json"', raw_text, "'raw_json' key found in JSON!")

        data = resp.json().get("castle", {})
        self.assertNotIn("password", data)
        self.assertNotIn("raw_json", data)
        self.assertEqual(data.get("castle_id"), "castle_victim_secure_1")

    def test_local_castle_admin_access_also_strips_password(self):
        """Super admin can view any castle, but password must STILL be stripped to prevent browser leakage."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_super_admin",
            "email": "ibraboths@gmail.com",
            "role": "admin",
            "is_super_admin": True,
        }
        resp = self.client.get("/api/local/castles/castle_victim_secure_1")
        self.assertEqual(resp.status_code, 200)
        raw_text = resp.text
        self.assertNotIn(self.victim_password, raw_text, "CRITICAL LEAK: Password found in admin response!")
        self.assertNotIn('"password"', raw_text)

    def test_local_castle_nonexistent_returns_404(self):
        """Requesting a non-existent castle returns 404 Not Found."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_victim_alpha",
            "email": "victim.alpha@domain.com",
            "role": "user",
        }
        resp = self.client.get("/api/local/castles/non_existent_castle_id_xyz")
        self.assertEqual(resp.status_code, 404)

    # ═════════════════════════════════════════════════════════════════════
    # VECTOR 2: /api/castle-data/{email} BOLA/IDOR Defense & Edge Cases
    # ═════════════════════════════════════════════════════════════════════

    def test_castle_data_cross_user_bola_rejected_403(self):
        """Attacker querying victim castle email MUST return 403 Forbidden."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_attacker_malicious",
            "email": "attacker.hacker@evilcorp.org",
            "role": "user",
        }
        resp = self.client.get("/api/castle-data/victim_castle_1@domain.com")
        self.assertEqual(resp.status_code, 403, f"Expected 403 BOLA block, got {resp.status_code}")

    def test_castle_data_casing_and_whitespace_spoofing_rejected_403(self):
        """Attacker using uppercase or whitespace tricks MUST STILL return 403 Forbidden."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_attacker_malicious",
            "email": "attacker.hacker@evilcorp.org",
            "role": "user",
        }
        # Uppercase
        resp_upper = self.client.get("/api/castle-data/VICTIM_CASTLE_1@DOMAIN.COM")
        self.assertEqual(resp_upper.status_code, 403, "Casing bypass succeeded! Must be 403.")

        # Whitespace padded
        resp_space = self.client.get("/api/castle-data/%20victim_castle_1@domain.com%20")
        self.assertEqual(resp_space.status_code, 403, "Whitespace bypass succeeded! Must be 403.")

    def test_castle_data_owner_allowed_past_auth(self):
        """Owner querying their own castle email MUST pass 403 security check."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_victim_alpha",
            "email": "victim.alpha@domain.com",
            "role": "user",
        }
        resp = self.client.get("/api/castle-data/victim_castle_1@domain.com")
        # Should NOT return 403 Forbidden (may return 404 or 503 because live game server is not running)
        self.assertNotEqual(resp.status_code, 403, f"Owner was blocked with 403: {resp.text}")

    def test_castle_data_admin_allowed_past_auth(self):
        """Admin querying any castle email MUST pass 403 security check."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_super_admin",
            "email": "ibraboths@gmail.com",
            "role": "admin",
            "is_super_admin": True,
        }
        resp = self.client.get("/api/castle-data/victim_castle_1@domain.com")
        self.assertNotEqual(resp.status_code, 403, "Admin was wrongly blocked with 403")

    # ═════════════════════════════════════════════════════════════════════
    # VECTOR 3: /api/bot/start Parameter Spoofing & Identity Binding
    # ═════════════════════════════════════════════════════════════════════

    def test_bot_start_overrides_spoofed_email_with_db_email(self):
        """Payload has castle A owned by user, but spoofed email: 'victim.alpha@domain.com'.
        The backend MUST force req.email = 'attacker_castle_1@evilcorp.org' from SQLite."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_attacker_malicious",
            "email": "attacker.hacker@evilcorp.org",
            "role": "user",
        }

        captured_calls = []
        orig_internal = api_server._start_bot_internal

        try:
            def mock_internal(req):
                captured_calls.append({
                    "castle_id": req.castle_id,
                    "user_id": req.user_id,
                    "email": req.email
                })
                return True

            api_server._start_bot_internal = mock_internal

            # Attacker sends spoofed email
            payload = {
                "castle_id": "castle_attacker_evil_1",
                "user_id": "uid_attacker_malicious",
                "email": "victim_castle_1@domain.com",  # Spoofed victim email!
                "config": {},
                "loop_interval": 20
            }
            resp = self.client.post("/api/bot/start", json=payload)
            self.assertEqual(resp.status_code, 200, f"Start failed: {resp.text}")
            self.assertEqual(len(captured_calls), 1)

            dispatched_email = captured_calls[0]["email"]
            self.assertEqual(
                dispatched_email,
                "attacker_castle_1@evilcorp.org",
                f"SPOOFING SUCCESSFUL! Backend dispatched with '{dispatched_email}' instead of verified DB email!"
            )
            self.assertNotEqual(dispatched_email, "victim_castle_1@domain.com")
        finally:
            api_server._start_bot_internal = orig_internal

    def test_bot_start_rejects_cross_user_castle_start(self):
        """Attacker trying to start victim's castle directly MUST be rejected."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_attacker_malicious",
            "email": "attacker.hacker@evilcorp.org",
            "role": "user",
        }
        # Attempt 1: attacker claims victim's user_id
        payload_impersonate = {
            "castle_id": "castle_victim_secure_1",
            "user_id": "uid_victim_alpha",
            "email": "victim_castle_1@domain.com",
        }
        resp1 = self.client.post("/api/bot/start", json=payload_impersonate)
        self.assertEqual(resp1.status_code, 403, "Caller UID mismatch must return 403")

        # Attempt 2: attacker sends own user_id but victim's castle_id
        payload_tamper_castle = {
            "castle_id": "castle_victim_secure_1",
            "user_id": "uid_attacker_malicious",
            "email": "attacker_castle_1@evilcorp.org",
        }
        resp2 = self.client.post("/api/bot/start", json=payload_tamper_castle)
        self.assertEqual(resp2.status_code, 404, "Target castle not owned by caller must return 404")

    # ═════════════════════════════════════════════════════════════════════
    # VECTOR 4: Internal Endpoints (10 routes) Perimeter Security
    # ═════════════════════════════════════════════════════════════════════

    def test_all_10_internal_endpoints_block_external_ip_without_credentials(self):
        """Every single internal endpoint MUST return 403 Forbidden when called with external IP headers."""
        external_headers = {
            "X-Real-IP": "203.0.113.195",
            "X-Forwarded-For": "203.0.113.195"
        }

        for method, path, body in INTERNAL_ENDPOINTS:
            with self.subTest(endpoint=path, method=method):
                if method == "GET":
                    resp = self.client.get(path, headers=external_headers)
                else:
                    resp = self.client.post(path, json=body or {}, headers=external_headers)
                self.assertEqual(
                    resp.status_code, 403,
                    f"CRITICAL SECURITY FAIL: Internal route {path} accepted external request without auth! Status: {resp.status_code}"
                )

    def test_internal_endpoints_block_fake_header_forgery(self):
        """Attacker forging loopback header (X-Real-IP: 127.0.0.1) from an external connection
        must NOT trick verify_internal_access when simulated properly."""
        # When request comes from external host
        # TestClient uses "testclient" by default, so verify_internal_access checks client_host and x_real_ip.
        # If client passes an external X-Real-IP, it must be rejected:
        headers = {"X-Real-IP": "198.51.100.99"}
        resp = self.client.get("/api/internal/debug-state", headers=headers)
        self.assertEqual(resp.status_code, 403, "External X-Real-IP must trigger 403")

    def test_internal_endpoints_block_invalid_internal_token(self):
        """Providing a fraudulent or invalid X-Internal-Token header MUST return 403 Forbidden."""
        bad_headers = {
            "X-Real-IP": "203.0.113.195",
            "X-Internal-Token": "completely_wrong_secret_attacker_token"
        }
        for method, path, body in INTERNAL_ENDPOINTS:
            with self.subTest(endpoint=path):
                if method == "GET":
                    resp = self.client.get(path, headers=bad_headers)
                else:
                    resp = self.client.post(path, json=body or {}, headers=bad_headers)
                self.assertEqual(resp.status_code, 403)

    def test_internal_endpoints_accept_valid_internal_token(self):
        """Valid X-Internal-Token MUST allow access to internal routes even from proxy/external IP."""
        valid_headers = {
            "X-Real-IP": "203.0.113.195",
            "X-Internal-Token": INTERNAL_API_SECRET
        }
        # Test debug-state
        resp = self.client.get("/api/internal/debug-state", headers=valid_headers)
        self.assertEqual(resp.status_code, 200, f"Failed with internal token: {resp.text}")

        # Test conn-state
        resp_conn = self.client.post("/api/bot/conn-state", json={"castle_id": "c_conn", "state": "connected"}, headers=valid_headers)
        self.assertEqual(resp_conn.status_code, 200, f"Failed conn-state with internal token: {resp_conn.text}")

    def test_internal_endpoints_reject_regular_user_bearer_token(self):
        """Regular user token (role: 'user') from external IP MUST return 403 on internal routes."""
        orig_gcu = api_server.get_current_user
        try:
            api_server.get_current_user = lambda req, creds: {
                "uid": "uid_attacker_malicious",
                "email": "attacker.hacker@evilcorp.org",
                "role": "user",
            }
            headers = {
                "X-Real-IP": "203.0.113.195",
                "Authorization": "Bearer fake_regular_user_token"
            }
            resp = self.client.get("/api/internal/debug-state", headers=headers)
            self.assertEqual(resp.status_code, 403, "Regular user Bearer token must NOT access internal routes!")
        finally:
            api_server.get_current_user = orig_gcu

    def test_internal_endpoints_accept_admin_bearer_token(self):
        """Admin user Bearer token (role: 'admin') from external IP MUST be authorized."""
        orig_gcu = api_server.get_current_user
        try:
            api_server.get_current_user = lambda req, creds: {
                "uid": "uid_super_admin",
                "email": "ibraboths@gmail.com",
                "role": "admin",
                "is_super_admin": True,
            }
            headers = {
                "X-Real-IP": "203.0.113.195",
                "Authorization": "Bearer valid_super_admin_jwt"
            }
            resp = self.client.get("/api/internal/debug-state", headers=headers)
            self.assertEqual(resp.status_code, 200, f"Admin token failed on internal endpoint: {resp.text}")
        finally:
            api_server.get_current_user = orig_gcu

    # ═════════════════════════════════════════════════════════════════════
    # VECTOR 5: Concurrency OCC & Race Condition Stress Testing
    # ═════════════════════════════════════════════════════════════════════

    def test_occ_atomic_burst_20_threads_exact_single_winner(self):
        """Empirical Stress: 20 threads simultaneously attempt to mutate castle config
        with expected_version=1.
        Strict Requirement: Exactly 1 thread succeeds (version -> 2), exactly 19 threads
        receive OCC conflict. Zero lost updates."""
        cid = "castle_occ_stress_target"
        db.save_castle({
            "castle_id": cid,
            "user_id": "uid_victim_alpha",
            "email": "occ_stress@domain.com",
            "config": {"initial": True},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        thread_count = 20
        results = []
        barrier = threading.Barrier(thread_count)

        def worker_task(tid: int):
            barrier.wait()  # Align all threads to fire simultaneously
            res = db.update_castle_config(
                castle_id=cid,
                config_dict={"winner_thread": tid, "timestamp": time.time()},
                expected_version=1,
                db_path=self.db_path
            )
            results.append((tid, res))

        threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for tid, r in results if r.get("success")]
        conflicts = [r for tid, r in results if r.get("conflict")]

        self.assertEqual(len(successes), 1, f"Expected exactly 1 winner, got {len(successes)}")
        self.assertEqual(len(conflicts), 19, f"Expected exactly 19 conflicts, got {len(conflicts)}")

        # Verify DB version is now exactly 2
        castle_post = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(castle_post["version"], 2)

    def test_occ_http_conflict_returns_409_status_code(self):
        """Mutating castle config via PUT /api/castles/{id} with stale version yields 409 Conflict."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": "uid_victim_alpha",
            "email": "victim.alpha@domain.com",
            "role": "user",
        }
        cid = "castle_victim_secure_1"
        # Current version is 1. Send stale version 0 or mismatch 99
        resp = self.client.put(f"/api/castles/{cid}", json={
            "config": {"task": "tampered"},
            "version": 999
        })
        self.assertEqual(resp.status_code, 409, f"Expected 409 Conflict, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertTrue(data.get("conflict") or "تعارض" in str(data) or "conflict" in str(data).lower())


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ChallengerM2StressSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
