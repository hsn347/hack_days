# -*- coding: utf-8 -*-
"""
tools/stress_m7_merchant_isolation.py — Empirical Stress & Adversarial Test Harness:
Milestone 7 Merchant Domain Isolation, Security Boundaries & Resource Lifecycle.
══════════════════════════════════════════════════════════════════════════════════════
Automated verification suite per AGENTS_CONSTITUTION.md Rule 13 & M7 Specifications:
1. Strict Merchant Domain Isolation in /api/admin/users/{uid}/castles:
   - Unauthenticated requests are rejected (401 Unauthorized).
   - Regular non-admin users are rejected (403 Forbidden).
   - Merchant admin accessing users within assigned merchant domain is permitted (200 OK).
   - Merchant admin accessing users outside domain (main tenant, other merchant, empty) is blocked (403 Forbidden).
   - Global super admin (ibraboths@gmail.com) has universal access across all domains (200 OK).
   - Non-existent target user returns 404 Not Found.
2. Resource Lifecycle & Component Unmount Cleanup:
   - ActionConfirmModal removes 'keydown' event listener on unmount.
   - AdminLiveProcesses clears auto-refresh timer on unmount / visibility change.
3. Hermetic Isolation:
   - Dedicated temporary SQLite database; zero mutations to production database.
"""

import os
import sys
import re
import shutil
import tempfile
import unittest
from typing import Dict, Any

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
import core.database as db
from core.tenants import clean_domain, MERCHANTS_CONFIG, DEFAULT_TENANT
from api_server import app, get_current_user


class MerchantIsolationStressSuite(unittest.TestCase):
    """Adversarial stress test suite verifying merchant isolation and resource lifecycle."""

    @classmethod
    def setUpClass(cls):
        # Verify merchant configuration exists
        cls.nurjan_merchant = next((m for m in MERCHANTS_CONFIG if m.get("id") == "nurjan"), None)
        assert cls.nurjan_merchant is not None, "nurjan merchant configuration required in core/tenants.py"
        cls.merchant_email = cls.nurjan_merchant["admin_email"]
        cls.merchant_domains = cls.nurjan_merchant["domains"]

    def setUp(self):
        # Create dedicated hermetic temporary SQLite database
        self.temp_dir = tempfile.mkdtemp(prefix="stress_m7_")
        self.db_path = os.path.join(self.temp_dir, "test_m7.db")
        db.init_db(self.db_path)

        self.orig_db_path = os.environ.get("CASTLES_DB_PATH")
        os.environ["CASTLES_DB_PATH"] = self.db_path

        # 1. Super Admin
        self.uid_super = "uid_super_admin_ibra"
        db.create_or_update_user(
            uid=self.uid_super,
            email=DEFAULT_TENANT["admin_email"],
            username="SuperAdmin",
            role="admin",
            tenant_domain="",
            db_path=self.db_path
        )

        # 2. Merchant Admin (nurjan)
        self.uid_merchant = "uid_merchant_nurjan"
        db.create_or_update_user(
            uid=self.uid_merchant,
            email=self.merchant_email,
            username="NurjanAdmin",
            role="merchant_admin",
            tenant_domain=self.merchant_domains[0],
            db_path=self.db_path
        )

        # 3. In-domain User under nurjanbot.online
        self.uid_user_in_domain = "uid_user_nurjan_valid"
        db.create_or_update_user(
            uid=self.uid_user_in_domain,
            email="player1@nurjanbot.online",
            username="NurjanPlayer1",
            role="user",
            tenant_domain="nurjanbot.online",
            db_path=self.db_path
        )
        db.save_castle({
            "castle_id": "castle_nurjan_1",
            "user_id": self.uid_user_in_domain,
            "email": "castle1@nurjanbot.online",
            "password": "hashed_secret_pass",
            "config": {"task": "gather"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        # 4. In-domain User under www.nurjanbot.online (testing clean_domain handling)
        self.uid_user_in_domain_www = "uid_user_nurjan_www"
        db.create_or_update_user(
            uid=self.uid_user_in_domain_www,
            email="player2@www.nurjanbot.online",
            username="NurjanPlayer2",
            role="user",
            tenant_domain="www.nurjanbot.online",
            db_path=self.db_path
        )
        db.save_castle({
            "castle_id": "castle_nurjan_2",
            "user_id": self.uid_user_in_domain_www,
            "email": "castle2@www.nurjanbot.online",
            "password": "hashed_secret_pass_2",
            "config": {"task": "farm"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        # 5. Main Tenant User (ibrabot.com)
        self.uid_user_main = "uid_user_main_tenant"
        db.create_or_update_user(
            uid=self.uid_user_main,
            email="player_main@ibrabot.com",
            username="MainTenantPlayer",
            role="user",
            tenant_domain="ibrabot.com",
            db_path=self.db_path
        )
        db.save_castle({
            "castle_id": "castle_main_1",
            "user_id": self.uid_user_main,
            "email": "castle_main@ibrabot.com",
            "password": "main_secret_pass",
            "config": {"task": "defend"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        # 6. Default/Empty Domain User
        self.uid_user_default = "uid_user_default_tenant"
        db.create_or_update_user(
            uid=self.uid_user_default,
            email="player_default@example.com",
            username="DefaultPlayer",
            role="user",
            tenant_domain="",
            db_path=self.db_path
        )
        db.save_castle({
            "castle_id": "castle_default_1",
            "user_id": self.uid_user_default,
            "email": "castle_default@example.com",
            "password": "default_secret_pass",
            "config": {"task": "scout"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        # 7. Other Merchant User (vipbot.net)
        self.uid_user_other_merchant = "uid_user_other_merchant"
        db.create_or_update_user(
            uid=self.uid_user_other_merchant,
            email="player_vip@vipbot.net",
            username="VipPlayer",
            role="user",
            tenant_domain="vipbot.net",
            db_path=self.db_path
        )
        db.save_castle({
            "castle_id": "castle_other_1",
            "user_id": self.uid_user_other_merchant,
            "email": "castle_other@vipbot.net",
            "password": "other_secret_pass",
            "config": {"task": "attack"},
            "is_active": 1,
            "state": "idle",
        }, db_path=self.db_path)

        # 8. Regular non-admin User
        self.uid_regular = "uid_regular_user"
        db.create_or_update_user(
            uid=self.uid_regular,
            email="regular_user@example.com",
            username="RegularJoe",
            role="user",
            tenant_domain="",
            db_path=self.db_path
        )

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

    # ══════════════════════════════════════════════════════════════════════
    # TIER 1: AUTHENTICATION & ACCESS CONTROL BOUNDARIES
    # ══════════════════════════════════════════════════════════════════════

    def test_01_unauthenticated_request_rejected_401(self):
        """Unauthenticated caller querying /api/admin/users/{uid}/castles must receive 401."""
        resp = self.client.get(f"/api/admin/users/{self.uid_user_in_domain}/castles")
        self.assertEqual(resp.status_code, 401, f"Expected 401 Unauthorized, got {resp.status_code}: {resp.text}")

    def test_02_regular_user_access_rejected_403(self):
        """Regular non-admin authenticated caller must receive 403 Forbidden."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_regular,
            "email": "regular_user@example.com",
            "role": "user",
            "is_super_admin": False,
            "is_merchant_admin": False,
        }
        resp = self.client.get(f"/api/admin/users/{self.uid_user_in_domain}/castles")
        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden, got {resp.status_code}: {resp.text}")
        self.assertIn("صلاحيات", resp.text)

    # ══════════════════════════════════════════════════════════════════════
    # TIER 2: MERCHANT IN-DOMAIN LEGITIMATE ACCESS
    # ══════════════════════════════════════════════════════════════════════

    def test_03_merchant_admin_in_domain_access_allowed_200(self):
        """Merchant admin accessing user within assigned domain must receive 200 OK and castle list."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_merchant,
            "email": self.merchant_email,
            "role": "merchant_admin",
            "is_merchant_admin": True,
            "merchant_tenant": self.nurjan_merchant,
        }
        resp = self.client.get(f"/api/admin/users/{self.uid_user_in_domain}/castles")
        self.assertEqual(resp.status_code, 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}")
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertEqual(data.get("user_id"), self.uid_user_in_domain)
        castles = data.get("castles", [])
        self.assertEqual(len(castles), 1)
        self.assertEqual(castles[0]["castle_id"], "castle_nurjan_1")

    def test_04_merchant_admin_in_domain_clean_domain_matching_200(self):
        """Merchant admin domain matching handles 'www.' prefixes cleanly via clean_domain."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_merchant,
            "email": self.merchant_email,
            "role": "merchant_admin",
            "is_merchant_admin": True,
            "merchant_tenant": self.nurjan_merchant,
        }
        resp = self.client.get(f"/api/admin/users/{self.uid_user_in_domain_www}/castles")
        self.assertEqual(resp.status_code, 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}")
        data = resp.json()
        castles = data.get("castles", [])
        self.assertEqual(len(castles), 1)
        self.assertEqual(castles[0]["castle_id"], "castle_nurjan_2")

    # ══════════════════════════════════════════════════════════════════════
    # TIER 3: MERCHANT CROSS-DOMAIN BOLA ATTACK MITIGATION
    # ══════════════════════════════════════════════════════════════════════

    def test_05_merchant_admin_blocked_from_main_tenant_user_403(self):
        """Merchant admin attempting to access user on main domain (ibrabot.com) must receive 403."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_merchant,
            "email": self.merchant_email,
            "role": "merchant_admin",
            "is_merchant_admin": True,
            "merchant_tenant": self.nurjan_merchant,
        }
        resp = self.client.get(f"/api/admin/users/{self.uid_user_main}/castles")
        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden, got {resp.status_code}")
        self.assertIn("خارج نطاق دومينك", resp.text)

    def test_06_merchant_admin_blocked_from_default_tenant_user_403(self):
        """Merchant admin attempting to access user with empty tenant_domain must receive 403."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_merchant,
            "email": self.merchant_email,
            "role": "merchant_admin",
            "is_merchant_admin": True,
            "merchant_tenant": self.nurjan_merchant,
        }
        resp = self.client.get(f"/api/admin/users/{self.uid_user_default}/castles")
        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden, got {resp.status_code}")
        self.assertIn("خارج نطاق دومينك", resp.text)

    def test_07_merchant_admin_blocked_from_other_merchant_user_403(self):
        """Merchant admin attempting to access user under another merchant (vipbot.net) must receive 403."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_merchant,
            "email": self.merchant_email,
            "role": "merchant_admin",
            "is_merchant_admin": True,
            "merchant_tenant": self.nurjan_merchant,
        }
        resp = self.client.get(f"/api/admin/users/{self.uid_user_other_merchant}/castles")
        self.assertEqual(resp.status_code, 403, f"Expected 403 Forbidden, got {resp.status_code}")
        self.assertIn("خارج نطاق دومينك", resp.text)

    # ══════════════════════════════════════════════════════════════════════
    # TIER 4: GLOBAL SUPER ADMIN UNIVERSAL ACCESS & 404 HANDLING
    # ══════════════════════════════════════════════════════════════════════

    def test_08_global_super_admin_universal_access_all_domains_200(self):
        """Global super admin (ibraboths@gmail.com) has universal access across all merchant and main users."""
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_super,
            "email": DEFAULT_TENANT["admin_email"],
            "role": "admin",
            "is_super_admin": True,
            "is_merchant_admin": False,
        }

        all_target_uids = [
            self.uid_user_in_domain,
            self.uid_user_in_domain_www,
            self.uid_user_main,
            self.uid_user_default,
            self.uid_user_other_merchant,
        ]

        for target_uid in all_target_uids:
            with self.subTest(target_uid=target_uid):
                resp = self.client.get(f"/api/admin/users/{target_uid}/castles")
                self.assertEqual(resp.status_code, 200, f"Super admin should access {target_uid}, got {resp.status_code}")
                data = resp.json()
                self.assertEqual(data.get("status"), "success")
                self.assertEqual(data.get("user_id"), target_uid)
                self.assertIsInstance(data.get("castles"), list)

    def test_09_nonexistent_user_returns_404(self):
        """Querying a non-existent UID returns 404 Not Found for both super admin and merchant admin."""
        # Test with super admin
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_super,
            "email": DEFAULT_TENANT["admin_email"],
            "role": "admin",
            "is_super_admin": True,
            "is_merchant_admin": False,
        }
        resp = self.client.get("/api/admin/users/uid_non_existent_ghost/castles")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("غير موجود", resp.text)

        # Test with merchant admin
        app.dependency_overrides[get_current_user] = lambda: {
            "uid": self.uid_merchant,
            "email": self.merchant_email,
            "role": "merchant_admin",
            "is_merchant_admin": True,
            "merchant_tenant": self.nurjan_merchant,
        }
        resp = self.client.get("/api/admin/users/uid_non_existent_ghost/castles")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("غير موجود", resp.text)

    # ══════════════════════════════════════════════════════════════════════
    # TIER 5: RESOURCE LIFECYCLE & CLEANUP ON UNMOUNT
    # ══════════════════════════════════════════════════════════════════════

    def test_10_resource_cleanup_action_modal_listener(self):
        """Verify ActionConfirmModal cleanly removes window keydown listener on unmount/close."""
        modal_file = os.path.join(ROOT_DIR, "dashboard", "src", "components", "common", "ActionConfirmModal.tsx")
        self.assertTrue(os.path.exists(modal_file), "ActionConfirmModal.tsx must exist")
        with open(modal_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check useEffect structure for addEventListener & removeEventListener pairing
        pattern = re.compile(r'useEffect\(\s*\(\)\s*=>\s*\{.*?addEventListener\(.*?return\s*\(\)\s*=>\s*.*?removeEventListener\(.*?\}\s*,\s*\[.*?\]\)', re.DOTALL)
        self.assertIsNotNone(pattern.search(content), "ActionConfirmModal must cleanly deregister keydown event listener in cleanup return function")

    def test_11_resource_cleanup_live_processes_interval(self):
        """Verify AdminLiveProcesses cleanly clears timerRef.current on unmount or tab deactivation."""
        live_file = os.path.join(ROOT_DIR, "dashboard", "src", "pages", "AdminLiveProcesses.tsx")
        self.assertTrue(os.path.exists(live_file), "AdminLiveProcesses.tsx must exist")
        with open(live_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check useEffect cleanup return function calls clearInterval
        self.assertIn("timerRef.current = setInterval(", content)
        self.assertIn("return () => {", content)
        self.assertIn("clearInterval(timerRef.current)", content)


def main():
    print("=" * 78)
    print("Milestone 7 Empirical Adversarial Stress Suite: Merchant Isolation & Lifecycle")
    print("=" * 78)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(MerchantIsolationStressSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 78)
    if result.wasSuccessful():
        print(f"[SUCCESS] All {result.testsRun} empirical stress tests PASSED perfectly (100%).")
        sys.exit(0)
    else:
        print(f"[FAIL] Stress suite failed: {len(result.failures)} failures, {len(result.errors)} errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
