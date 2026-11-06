# -*- coding: utf-8 -*-
"""
tests/test_e2e_platform.py — End-to-End Platform, Security, Concurrency & Workflow Tests
══════════════════════════════════════════════════════════════════════════════════════
Tiers Covered:
- Tier 1: Feature Coverage (Token auth, Super/Merchant Admin, Castle Isolation, Password Sanitization)
- Tier 3: Cross-Feature Combinations (Atomic Rollback, Deep Config Merge, Concurrency, Ban/Unban Lifecycle)
- Tier 4: Real-World Workflows (Full Admin-to-Castle Aggregation, Bot State Lifecycle, Account Switching)
══════════════════════════════════════════════════════════════════════════════════════
Hermetic Isolation:
Every test creates and destroys a dedicated temporary SQLite database.
Zero bytes written to production database (database/castles.db).
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
import threading
from typing import Dict, Any, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db
from core.tenants import (
    is_super_admin,
    is_merchant_admin,
    is_user_allowed_for_tenant_domain,
    clean_domain,
    get_tenant_by_domain,
    DEFAULT_TENANT,
)


def create_test_castle(
    db_path: str,
    castle_id: str,
    email: str,
    user_id: str = "",
    password: str = "",
    config: Any = "{}",
    is_active: bool = True,
    state: str = "idle",
    conn_state: str = "idle",
    castle_name: str = "",
    lord_name: str = "",
    lord_power: int = 0,
) -> bool:
    """Helper to seed test castles cleanly using save_castle and DB connection."""
    ok = db.save_castle({
        "user_id": user_id,
        "castle_id": castle_id,
        "email": email,
        "password": password,
        "config": config,
        "is_active": 1 if is_active else 0,
        "state": state,
        "conn_state": conn_state,
    }, db_path=db_path)
    if castle_name or lord_name or lord_power:
        with db.get_connection(db_path) as conn:
            conn.execute(
                "UPDATE castle_states SET castle_name = ?, lord_name = ?, lord_power = ? WHERE castle_id = ?",
                (castle_name, lord_name, lord_power, castle_id)
            )
            conn.commit()
    return ok


class BaseIsolatedDatabaseTestCase(unittest.TestCase):
    """Base fixture creating an isolated temporary SQLite database for each test."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="osmanli_test_")
        self.db_path = os.path.join(self.temp_dir, "test_castles.db")
        db.init_db(self.db_path)

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
# ── TIER 1: CORE FEATURE COVERAGE (SECURITY, AUTH & ISOLATION) ────
# ════════════════════════════════════════════════════════════════════

class TestTier1FeatureCoverage(BaseIsolatedDatabaseTestCase):
    """Tier 1: Feature Coverage — Query correctness, Auth, BOLA & Isolation."""

    def test_t1_super_admin_identification(self):
        """T1.1: Verify is_super_admin strictly identifies ibraboths@gmail.com case-insensitively."""
        self.assertTrue(is_super_admin("ibraboths@gmail.com"))
        self.assertTrue(is_super_admin("IBRABOTHS@GMAIL.COM"))
        self.assertTrue(is_super_admin({"email": "IbraBoths@Gmail.Com"}))
        self.assertFalse(is_super_admin("regular_user@gmail.com"))
        self.assertFalse(is_super_admin("admin@otherdomain.com"))
        self.assertFalse(is_super_admin(""))
        self.assertFalse(is_super_admin(None))

    def test_t1_merchant_admin_identification(self):
        """T1.2: Verify is_merchant_admin identifies merchant tenant admins and rejects others."""
        self.assertTrue(is_merchant_admin("nurjan12ddsw2@gmail.com"))
        self.assertTrue(is_merchant_admin("NURJAN12DDSW2@GMAIL.COM"))
        # Super admin is NOT merchant admin
        self.assertFalse(is_merchant_admin("ibraboths@gmail.com"))
        self.assertFalse(is_merchant_admin("random_user@domain.com"))

    def test_t1_banned_user_quota_and_status(self):
        """T1.3: Verify banning a user sets active castles to 0 and subscription to suspended."""
        uid = "uid_banned_test"
        email = "banned_test@example.com"
        db.create_or_update_user(uid=uid, email=email, role="user", db_path=self.db_path)
        db.update_user_subscription(uid=uid, max_castles_allowed=5, subscription_status="active", db_path=self.db_path)

        # Create 2 active castles
        create_test_castle(self.db_path, castle_id="c_ban_1", email="c1@b.com", user_id=uid, is_active=True)
        create_test_castle(self.db_path, castle_id="c_ban_2", email="c2@b.com", user_id=uid, is_active=True)

        # Ban the user
        ok = db.ban_user(uid=uid, ban=True, reason="Terms Violation", db_path=self.db_path)
        self.assertTrue(ok)

        # Verify in user record
        u = db.get_user(uid, db_path=self.db_path)
        self.assertIsNotNone(u)
        self.assertEqual(u["is_banned"], 1)
        self.assertEqual(u["banned_reason"], "Terms Violation")
        self.assertEqual(u["subscription_status"], "suspended")
        self.assertEqual(u["current_castles_count"], 0)
        self.assertEqual(u["pending_castles_count"], 2)

    def test_t1_castle_isolation_by_user(self):
        """T1.4: Verify complete BOLA isolation: User A cannot see User B's castles."""
        user_a = "uid_user_alpha"
        user_b = "uid_user_beta"
        db.create_or_update_user(uid=user_a, email="alpha@test.com", db_path=self.db_path)
        db.create_or_update_user(uid=user_b, email="beta@test.com", db_path=self.db_path)

        create_test_castle(self.db_path, castle_id="castle_a1", email="a1@test.com", user_id=user_a)
        create_test_castle(self.db_path, castle_id="castle_a2", email="a2@test.com", user_id=user_a)
        create_test_castle(self.db_path, castle_id="castle_b1", email="b1@test.com", user_id=user_b)

        # Query user A's castles
        castles_a = db.get_user_castles(user_a, db_path=self.db_path)
        a_ids = [c["castle_id"] for c in castles_a]
        self.assertIn("castle_a1", a_ids)
        self.assertIn("castle_a2", a_ids)
        self.assertNotIn("castle_b1", a_ids)

        # Query user B's castles
        castles_b = db.get_user_castles(user_b, db_path=self.db_path)
        b_ids = [c["castle_id"] for c in castles_b]
        self.assertIn("castle_b1", b_ids)
        self.assertNotIn("castle_a1", b_ids)
        self.assertNotIn("castle_a2", b_ids)

    def test_t1_castle_password_sanitization(self):
        """T1.5: Verify plaintext password and raw_json are stripped from client responses."""
        uid = "uid_secret_test"
        cid = "castle_secret"
        db.create_or_update_user(uid=uid, email="secret@test.com", db_path=self.db_path)
        create_test_castle(self.db_path, castle_id=cid, email="secret@test.com", user_id=uid, password="SUPER_SECRET_PASSWORD")

        # Test get_user_castles
        castles = db.get_user_castles(uid, db_path=self.db_path)
        self.assertEqual(len(castles), 1)
        self.assertNotIn("password", castles[0])
        self.assertNotIn("raw_json", castles[0])

        # Test get_castle_by_id
        c = db.get_castle_by_id(cid, user_id=uid, db_path=self.db_path)
        self.assertIsNotNone(c)
        self.assertNotIn("password", c)
        self.assertNotIn("raw_json", c)

    def test_t1_tenant_domain_isolation(self):
        """T1.6: Verify tenant domain isolation prevents cross-tenant access."""
        nurjan_user = {"email": "player@nurjan.com", "tenant_domain": "nurjanbot.online"}
        main_user = {"email": "player@ibra.com", "tenant_domain": "ibraabot.online"}

        # User belonging to Nurjan cannot access main domain
        self.assertTrue(is_user_allowed_for_tenant_domain(nurjan_user, "nurjanbot.online"))
        self.assertFalse(is_user_allowed_for_tenant_domain(nurjan_user, "ibraabot.online"))

        # User belonging to main cannot access Nurjan domain
        self.assertTrue(is_user_allowed_for_tenant_domain(main_user, "ibraabot.online"))
        self.assertFalse(is_user_allowed_for_tenant_domain(main_user, "nurjanbot.online"))

    def test_t1_user_castle_quota_calculation(self):
        """T1.7: Verify sync_user_castles_and_quota limits active castles to max_castles_allowed."""
        uid = "uid_quota_test"
        db.create_or_update_user(uid=uid, email="quota@test.com", db_path=self.db_path)
        db.update_user_subscription(uid=uid, max_castles_allowed=2, subscription_status="active", db_path=self.db_path)

        # Create 3 castles
        create_test_castle(self.db_path, castle_id="q1", email="q1@test.com", user_id=uid, is_active=True)
        create_test_castle(self.db_path, castle_id="q2", email="q2@test.com", user_id=uid, is_active=True)
        create_test_castle(self.db_path, castle_id="q3", email="q3@test.com", user_id=uid, is_active=True)

        res = db.sync_user_castles_and_quota(uid, db_path=self.db_path)
        self.assertEqual(res["active"], 2)
        self.assertEqual(res["pending"], 1)

        # Retrieve user and verify counts
        u = db.get_user(uid, db_path=self.db_path)
        self.assertEqual(u["current_castles_count"], 2)
        self.assertEqual(u["pending_castles_count"], 1)


# ════════════════════════════════════════════════════════════════════
# ── TIER 3: CROSS-FEATURE COMBINATIONS & CONCURRENCY ──────────────
# ════════════════════════════════════════════════════════════════════

class TestTier3CrossFeatureConcurrency(BaseIsolatedDatabaseTestCase):
    """Tier 3: Pairwise interactions, atomic rollback, OCC version contracts, and concurrency."""

    def test_t3_transaction_atomic_rollback(self):
        """T3.1: Verify SQLite atomic rollback on transaction failure prevents partial writes."""
        uid = "uid_tx_test"
        db.create_or_update_user(uid=uid, email="tx@test.com", db_path=self.db_path)
        create_test_castle(self.db_path, castle_id="c_tx_1", email="c1@tx.com", user_id=uid, lord_power=100)

        # Attempt atomic multi-step update where second step fails
        failed = False
        try:
            with db.get_connection(self.db_path) as conn:
                conn.execute("UPDATE castle_states SET lord_power = 999 WHERE castle_id = 'c_tx_1'")
                # Intentionally execute invalid SQL to trigger rollback
                conn.execute("INSERT INTO non_existent_table VALUES (1, 2, 3)")
        except Exception:
            failed = True

        self.assertTrue(failed)

        # Verify lord_power was rolled back to 100, not 999
        c = db.get_castle_by_id("c_tx_1", db_path=self.db_path)
        self.assertEqual(c["lord_power"], 100)

    def test_t3_deep_config_merge_preserves_unrelated_tasks(self):
        """T3.2: Verify updating one task config section does not overwrite or wipe existing tasks."""
        cid = "c_merge_test"
        initial_config = {
            "march_manager": {"enabled": True, "ruins": {"explore_time": 3600}},
            "savings_bank": {"enabled": True, "deposit": 2000},
        }
        create_test_castle(self.db_path, castle_id=cid, email="merge@test.com", config=initial_config)

        # Update only gather config
        update_cfg = {
            "gather": {"enabled": True, "level": 6, "prefer_tiles": [1, 2]}
        }
        ok = db.update_castle_config(cid, update_cfg, db_path=self.db_path)
        self.assertTrue(ok)

        # Verify all sections exist and none were wiped
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        cfg = c["config"]
        self.assertIn("march_manager", cfg)
        self.assertEqual(cfg["march_manager"]["ruins"]["explore_time"], 3600)
        self.assertIn("savings_bank", cfg)
        self.assertEqual(cfg["savings_bank"]["deposit"], 2000)
        self.assertIn("gather", cfg)
        self.assertEqual(cfg["gather"]["level"], 6)

    def test_t3_concurrency_config_simulation(self):
        """T3.3: Concurrent multi-threaded config updates do not corrupt the JSON configuration."""
        cid = "c_concurrent_cfg"
        create_test_castle(self.db_path, castle_id=cid, email="conc_cfg@test.com", config={"base": 0})

        errors = []

        def worker(key: str, val: int):
            try:
                for _ in range(5):
                    db.update_castle_config(cid, {key: val}, db_path=self.db_path)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(f"task_{i}", i * 10))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        cfg = c["config"]
        self.assertIn("base", cfg)

    def test_t3_ban_unban_quota_resynchronization(self):
        """T3.4: Complete lifecycle: active user with 3 castles -> ban -> unban -> verify restored quotas."""
        uid = "uid_lifecycle"
        db.create_or_update_user(uid=uid, email="life@test.com", db_path=self.db_path)
        db.update_user_subscription(uid=uid, max_castles_allowed=3, subscription_status="active", db_path=self.db_path)

        for i in range(3):
            create_test_castle(self.db_path, castle_id=f"c_life_{i}", email=f"life{i}@test.com", user_id=uid, is_active=True)

        # Verify initial active = 3
        active, pending = db.count_user_castles(uid, db_path=self.db_path)
        self.assertEqual(active, 3)
        self.assertEqual(pending, 0)

        # Ban user
        db.ban_user(uid=uid, ban=True, reason="Testing", db_path=self.db_path)
        u_banned = db.get_user(uid, db_path=self.db_path)
        self.assertEqual(u_banned["current_castles_count"], 0)
        self.assertEqual(u_banned["pending_castles_count"], 3)

        # Unban user
        db.ban_user(uid=uid, ban=False, db_path=self.db_path)
        u_restored = db.get_user(uid, db_path=self.db_path)
        self.assertEqual(u_restored["is_banned"], 0)
        self.assertEqual(u_restored["current_castles_count"], 3)
        self.assertEqual(u_restored["pending_castles_count"], 0)

    def test_t3_optimistic_concurrency_versioning_contract(self):
        """T3.5: Verify atomic transaction integrity and timestamp tracking on castle updates."""
        cid = "c_occ_contract"
        create_test_castle(self.db_path, castle_id=cid, email="occ@test.com")

        c1 = db.get_castle_by_id(cid, db_path=self.db_path)
        initial_updated = c1.get("last_updated")

        time.sleep(0.05)
        db.update_castle_config(cid, {"setting": "v1"}, db_path=self.db_path)

        c2 = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertNotEqual(c2.get("last_updated"), initial_updated)
        self.assertEqual(c2["config"].get("setting"), "v1")

    def test_t3_concurrent_status_and_resource_updates(self):
        """T3.6: Simultaneous status update and resource updates on the same castle do not conflict."""
        cid = "c_conc_status_res"
        email = "status_res@test.com"
        create_test_castle(self.db_path, castle_id=cid, email=email)

        errors = []

        def update_status():
            try:
                for i in range(10):
                    db.upsert_castle_conn_state(
                        email=email,
                        conn_state="connected" if i % 2 == 0 else "reconnecting",
                        message=f"msg_{i}",
                        castle_id=cid,
                        db_path=self.db_path
                    )
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        def update_res():
            try:
                for i in range(10):
                    db.upsert_castle_resources(
                        email=email,
                        resources={"food": 1000 + i, "wood": 2000 + i},
                        castle_id=cid,
                        db_path=self.db_path
                    )
                    time.sleep(0.005)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=update_status)
        t2 = threading.Thread(target=update_res)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(errors), 0)
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertIsNotNone(c)
        self.assertGreaterEqual(c["food"], 1000)


# ════════════════════════════════════════════════════════════════════
# ── TIER 4: REAL-WORLD WORKFLOWS & END-TO-END SCENARIOS ───────────
# ════════════════════════════════════════════════════════════════════

class TestTier4RealWorldWorkflows(BaseIsolatedDatabaseTestCase):
    """Tier 4: Real-world operational scenarios across admin, user, and bot layers."""

    def test_t4_full_admin_to_castle_aggregation_journey(self):
        """T4.1: Admin views all users with castles; validates aggregated castle counts and subscription state."""
        u_active = "uid_admin_u1"
        u_banned = "uid_admin_u2"
        u_pending = "uid_admin_u3"

        db.create_or_update_user(uid=u_active, email="active@admin.com", db_path=self.db_path)
        db.update_user_subscription(uid=u_active, max_castles_allowed=5, subscription_status="active", db_path=self.db_path)
        for i in range(3):
            create_test_castle(self.db_path, castle_id=f"c_act_{i}", email=f"act{i}@a.com", user_id=u_active, is_active=True)

        db.create_or_update_user(uid=u_banned, email="banned@admin.com", db_path=self.db_path)
        for i in range(2):
            create_test_castle(self.db_path, castle_id=f"c_ban_{i}", email=f"ban{i}@b.com", user_id=u_banned, is_active=True)
        db.ban_user(uid=u_banned, ban=True, reason="Abuse", db_path=self.db_path)

        db.create_or_update_user(uid=u_pending, email="pending@admin.com", db_path=self.db_path)

        # Admin fetches all users with castles
        users = db.get_all_users_with_castles(db_path=self.db_path)
        self.assertGreaterEqual(len(users), 3)

        user_map = {u["uid"]: u for u in users}
        self.assertIn(u_active, user_map)
        self.assertEqual(user_map[u_active]["current_castles_count"], 3)
        self.assertEqual(user_map[u_active]["pending_castles_count"], 0)
        self.assertEqual(user_map[u_active]["total_castles_count"], 3)

        self.assertIn(u_banned, user_map)
        self.assertEqual(user_map[u_banned]["current_castles_count"], 0)
        self.assertEqual(user_map[u_banned]["pending_castles_count"], 2)

        self.assertIn(u_pending, user_map)
        self.assertEqual(user_map[u_pending]["total_castles_count"], 0)

    def test_t4_bot_lifecycle_and_state_persistence_workflow(self):
        """T4.2: Complete bot operational lifecycle: idle -> connected -> reconnecting -> idle."""
        cid = "c_bot_flow"
        email = "bot_flow@game.com"
        create_test_castle(self.db_path, castle_id=cid, email=email)

        # Step 1: Initial state is idle
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(c["state"], "idle")

        # Step 2: Bot connects
        db.upsert_castle_conn_state(
            email=email,
            conn_state="connected",
            message="Game engine connected successfully",
            castle_id=cid,
            db_path=self.db_path
        )
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(c["state"], "running")
        self.assertEqual(c["conn_state"], "connected")
        self.assertIn("Game engine connected", c["conn_message"])

        # Step 3: Network drop / reconnecting
        db.upsert_castle_conn_state(
            email=email,
            conn_state="reconnecting",
            message="Heartbeat timeout, reconnecting in 5s...",
            castle_id=cid,
            db_path=self.db_path
        )
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(c["state"], "running")
        self.assertEqual(c["conn_state"], "reconnecting")

        # Step 4: Bot stopped by user
        db.upsert_castle_conn_state(
            email=email,
            conn_state="idle",
            message="Bot stopped by user",
            castle_id=cid,
            db_path=self.db_path
        )
        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertEqual(c["state"], "idle")
        self.assertEqual(c["conn_state"], "idle")

    def test_t4_multi_user_account_switch_and_data_isolation(self):
        """T4.3: Simulate account switching: User 1 logoff -> User 2 login, verify zero leakage."""
        u1 = "uid_switch_1"
        u2 = "uid_switch_2"

        db.create_or_update_user(uid=u1, email="u1@switch.com", db_path=self.db_path)
        db.create_or_update_user(uid=u2, email="u2@switch.com", db_path=self.db_path)

        create_test_castle(self.db_path, castle_id="c_u1", email="u1@switch.com", user_id=u1, castle_name="U1 Palace")
        create_test_castle(self.db_path, castle_id="c_u2", email="u2@switch.com", user_id=u2, castle_name="U2 Stronghold")

        # Session 1: User 1 queries
        u1_castles = db.get_user_castles(u1, db_path=self.db_path)
        self.assertEqual(len(u1_castles), 1)
        self.assertEqual(u1_castles[0]["castle_name"], "U1 Palace")

        # Session 2: User 2 queries
        u2_castles = db.get_user_castles(u2, db_path=self.db_path)
        self.assertEqual(len(u2_castles), 1)
        self.assertEqual(u2_castles[0]["castle_name"], "U2 Stronghold")
        self.assertNotIn("U1 Palace", [c["castle_name"] for c in u2_castles])

    def test_t4_batch_approval_and_quota_promotion_workflow(self):
        """T4.4: Batch approval workflow: Pending users with pending castles get auto-promoted to active."""
        pending_uids = []
        for i in range(3):
            uid = f"uid_pend_{i}"
            pending_uids.append(uid)
            db.create_or_update_user(uid=uid, email=f"pending_{i}@test.com", db_path=self.db_path)
            # Set to pending trial
            db.update_user_subscription(uid=uid, subscription_status="pending_approval", max_castles_allowed=0, db_path=self.db_path)
            # Add castle in pending state
            create_test_castle(
                self.db_path,
                castle_id=f"c_pend_{i}",
                email=f"p_{i}@test.com",
                user_id=uid,
                is_active=False,
                state="pending",
                conn_state="pending"
            )

        # Admin executes approve_all_pending_users
        approved_count = db.approve_all_pending_users(days=3, max_castles=5, db_path=self.db_path)
        self.assertEqual(approved_count, 3)

        # Verify all users are now active and castles promoted
        for uid in pending_uids:
            u = db.get_user(uid, db_path=self.db_path)
            self.assertEqual(u["subscription_status"], "active")
            self.assertEqual(u["max_castles_allowed"], 5)
            self.assertEqual(u["current_castles_count"], 1)
            self.assertEqual(u["pending_castles_count"], 0)


if __name__ == "__main__":
    unittest.main()
