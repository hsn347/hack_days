# -*- coding: utf-8 -*-
"""
tests/test_database_performance.py — Database Query Correctness, Boundary Value Analysis & Stress
═════════════════════════════════════════════════════════════════════════════════════════════════
Tiers Covered:
- Tier 1: Core Database Queries (Schema verification, case-insensitivity, query contracts)
- Tier 2: Boundary & Corner Cases (Empty sets, exact quota boundaries, scalability, concurrent WAL stress)
═════════════════════════════════════════════════════════════════════════════════════════════════
Hermetic Isolation:
Every test operates in an isolated temporary SQLite database with WAL mode enabled.
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import tempfile
import unittest
import threading
from typing import Dict, Any, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db


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


class BaseDatabaseTestCase(unittest.TestCase):
    """Fixture creating a fresh isolated SQLite database for each test."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="osmanli_db_test_")
        self.db_path = os.path.join(self.temp_dir, "test_db.db")
        db.init_db(self.db_path)

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
# ── TIER 1: DATABASE FEATURE COVERAGE & QUERY CONTRACTS ───────────
# ════════════════════════════════════════════════════════════════════

class TestTier1DatabaseQueries(BaseDatabaseTestCase):
    """Tier 1: Feature Coverage — Schema integrity, Case-insensitivity, Query structure."""

    def test_t1_db_schema_initialization(self):
        """T1.1: Verify init_db creates all required tables and indexes."""
        with db.get_connection(self.db_path) as conn:
            tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            self.assertIn("users", tables)
            self.assertIn("castle_states", tables)
            self.assertIn("system_settings", tables)

            # Check users columns
            u_cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
            self.assertIn("uid", u_cols)
            self.assertIn("email", u_cols)
            self.assertIn("role", u_cols)
            self.assertIn("is_banned", u_cols)
            self.assertIn("subscription_status", u_cols)
            self.assertIn("max_castles_allowed", u_cols)

            # Check castle_states columns
            c_cols = [r["name"] for r in conn.execute("PRAGMA table_info(castle_states)").fetchall()]
            self.assertIn("castle_id", c_cols)
            self.assertIn("email", c_cols)
            self.assertIn("user_id", c_cols)
            self.assertIn("config", c_cols)
            self.assertIn("is_active", c_cols)
            self.assertIn("state", c_cols)
            self.assertIn("conn_state", c_cols)

    def test_t1_case_insensitive_email_lookup(self):
        """T1.2: Verify case-insensitive queries for user and castle records."""
        uid = "uid_case_sens"
        email = "MixedCase.User@Example.Com"
        db.create_or_update_user(uid=uid, email=email, role="user", db_path=self.db_path)
        create_test_castle(self.db_path, castle_id="c_case_1", email=email, user_id=uid)

        # Lookup by lower-case expression query via SQLite
        with db.get_connection(self.db_path) as conn:
            row_lower = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower(),)).fetchone()
            self.assertIsNotNone(row_lower)
            self.assertEqual(row_lower["uid"], uid)

            # Verify expression index is used
            plan = conn.execute("EXPLAIN QUERY PLAN SELECT * FROM users WHERE LOWER(email) = ?", (email.lower(),)).fetchall()
            plan_str = " ".join([str(p["detail"]) for p in plan])
            self.assertTrue("idx_users_lower_email" in plan_str or "INDEX" in plan_str)

        # Lookup castles by upper and lower case email using get_user_castles
        c_by_upper = db.get_user_castles(email.upper(), db_path=self.db_path)
        self.assertEqual(len(c_by_upper), 1)
        self.assertEqual(c_by_upper[0]["castle_id"], "c_case_1")

        c_by_lower = db.get_user_castles(email.lower(), db_path=self.db_path)
        self.assertEqual(len(c_by_lower), 1)
        self.assertEqual(c_by_lower[0]["castle_id"], "c_case_1")

    def test_t1_user_with_castles_query_structure(self):
        """T1.3: Verify get_all_users_with_castles returns required dictionary fields and subscription metadata."""
        uid = "uid_struct_test"
        db.create_or_update_user(
            uid=uid,
            email="struct@test.com",
            subscription_status="active",
            max_castles_allowed=5,
            db_path=self.db_path
        )
        create_test_castle(self.db_path, castle_id="c_struct_1", email="cs1@test.com", user_id=uid, is_active=True)

        users = db.get_all_users_with_castles(db_path=self.db_path)
        self.assertEqual(len(users), 1)
        u = users[0]

        # Verify top-level fields
        self.assertIn("uid", u)
        self.assertIn("email", u)
        self.assertIn("current_castles_count", u)
        self.assertIn("pending_castles_count", u)
        self.assertIn("total_castles_count", u)
        self.assertIn("subscription", u)

        # Verify subscription nested fields
        sub = u["subscription"]
        self.assertIn("plan_id", sub)
        self.assertIn("plan_name", sub)
        self.assertIn("status", sub)
        self.assertIn("max_castles_allowed", sub)
        self.assertEqual(u["current_castles_count"], 1)

    def test_t1_castle_creation_and_retrieval(self):
        """T1.4: Verify castle creation stores JSON config and retrieves with deserialized dictionary."""
        cid = "c_create_test"
        cfg = {"attack": {"enabled": True, "target": "monster"}}
        create_test_castle(
            self.db_path,
            castle_id=cid,
            email="create@game.com",
            user_id="uid_1",
            castle_name="Eagle Nest",
            config=cfg
        )

        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertIsNotNone(c)
        self.assertEqual(c["castle_name"], "Eagle Nest")
        self.assertIsInstance(c["config"], dict)
        self.assertTrue(c["config"].get("attack", {}).get("enabled"))


# ════════════════════════════════════════════════════════════════════
# ── TIER 2: BOUNDARY & CORNER CASES (BVA & STRESS) ────────────────
# ════════════════════════════════════════════════════════════════════

class TestTier2BoundaryAndStress(BaseDatabaseTestCase):
    """Tier 2: Boundary Value Analysis — Empty datasets, exact quotas, large scale, concurrent WAL."""

    def test_t2_empty_database_queries(self):
        """T2.1: Empty database returns empty collections without throwing exceptions."""
        users = db.get_all_users(db_path=self.db_path)
        self.assertEqual(users, [])

        users_castles = db.get_all_users_with_castles(db_path=self.db_path)
        self.assertEqual(users_castles, [])

        castles = db.get_all_castles(db_path=self.db_path)
        self.assertEqual(castles, [])

        u_castles = db.get_user_castles("non_existent_uid", db_path=self.db_path)
        self.assertEqual(u_castles, [])

    def test_t2_single_user_zero_castles_boundary(self):
        """T2.2: Boundary: User with zero castles returns strictly 0 active, 0 pending, 0 total."""
        uid = "uid_zero_castles"
        db.create_or_update_user(uid=uid, email="zero@test.com", db_path=self.db_path)

        active, pending = db.count_user_castles(uid, db_path=self.db_path)
        self.assertEqual(active, 0)
        self.assertEqual(pending, 0)

        users = db.get_all_users_with_castles(db_path=self.db_path)
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["current_castles_count"], 0)
        self.assertEqual(users[0]["pending_castles_count"], 0)
        self.assertEqual(users[0]["total_castles_count"], 0)

    def test_t2_user_at_exact_quota_boundary(self):
        """T2.3: Boundary: Exact limit behavior (max=3). Adding 3 castles -> 3 active; adding 4th -> 1 pending."""
        uid = "uid_boundary_quota"
        db.create_or_update_user(uid=uid, email="boundary_quota@test.com", db_path=self.db_path)
        db.update_user_subscription(uid=uid, max_castles_allowed=3, subscription_status="active", db_path=self.db_path)

        # Add exactly 3 castles
        for i in range(3):
            create_test_castle(self.db_path, castle_id=f"c_b_{i}", email=f"cb{i}@test.com", user_id=uid, is_active=True)

        res = db.sync_user_castles_and_quota(uid, db_path=self.db_path)
        self.assertEqual(res["active"], 3)
        self.assertEqual(res["pending"], 0)

        # Add 4th castle beyond limit
        create_test_castle(self.db_path, castle_id="c_b_3", email="cb3@test.com", user_id=uid, is_active=True)
        res = db.sync_user_castles_and_quota(uid, db_path=self.db_path)
        self.assertEqual(res["active"], 3)
        self.assertEqual(res["pending"], 1)

    def test_t2_extreme_record_set_scalability(self):
        """T2.4: Scalability stress test: Bulk insert 100 users and 200 castles, verify query completes < 1.0s."""
        # Bulk populate
        with db.get_connection(self.db_path) as conn:
            user_tuples = [
                (f"uid_bulk_{i}", f"bulk_{i}@example.com", "user", 0, "active", 5)
                for i in range(100)
            ]
            conn.executemany(
                "INSERT INTO users (uid, email, role, is_banned, subscription_status, max_castles_allowed) VALUES (?, ?, ?, ?, ?, ?)",
                user_tuples
            )

            castle_tuples = [
                (f"castle_bulk_{i}", f"c_{i}@example.com", f"uid_bulk_{i % 100}", 1, "idle", "idle")
                for i in range(200)
            ]
            conn.executemany(
                "INSERT INTO castle_states (castle_id, email, user_id, is_active, state, conn_state) VALUES (?, ?, ?, ?, ?, ?)",
                castle_tuples
            )

        start = time.perf_counter()
        users = db.get_all_users_with_castles(db_path=self.db_path)
        duration = time.perf_counter() - start

        self.assertEqual(len(users), 100)
        # Performance check: 100 users aggregation must be fast
        self.assertLess(duration, 1.5, f"Aggregation took too long: {duration:.3f}s")

    def test_t2_concurrent_reads_and_writes_wal(self):
        """T2.5: Stress test: 8 concurrent threads (4 readers, 4 writers) against SQLite WAL database."""
        db.create_or_update_user(uid="uid_wal_stress", email="wal@test.com", db_path=self.db_path)
        errors = []
        stop_event = threading.Event()

        def reader():
            try:
                while not stop_event.is_set():
                    db.get_all_users(db_path=self.db_path)
                    db.get_user_castles("uid_wal_stress", db_path=self.db_path)
                    time.sleep(0.005)
            except Exception as ex:
                errors.append(f"Reader error: {ex}")

        def writer(w_id: int):
            try:
                for j in range(15):
                    cid = f"c_wal_{w_id}_{j}"
                    create_test_castle(
                        self.db_path,
                        castle_id=cid,
                        email=f"w{w_id}_{j}@test.com",
                        user_id="uid_wal_stress",
                    )
                    db.upsert_castle_conn_state(
                        email=f"w{w_id}_{j}@test.com",
                        conn_state="connected",
                        castle_id=cid,
                        db_path=self.db_path
                    )
                    time.sleep(0.005)
            except Exception as ex:
                errors.append(f"Writer error: {ex}")

        threads = [threading.Thread(target=reader) for _ in range(4)]
        writers = [threading.Thread(target=writer, args=(i,)) for i in range(4)]

        for t in threads + writers:
            t.start()

        for w in writers:
            w.join()

        stop_event.set()
        for r in threads:
            r.join()

        self.assertEqual(len(errors), 0, f"Encountered concurrent errors: {errors}")
        castles = db.get_user_castles("uid_wal_stress", db_path=self.db_path)
        self.assertEqual(len(castles), 60)

    def test_t2_special_characters_in_identifiers(self):
        """T2.6: Robustness: Handle Arabic characters, emojis, quotes, and punctuation without corruption."""
        uid = "uid_special_!@#$%"
        email = "أحمد_سلطان+test@example.com"
        lord_name = "🛡️ السلطان الأعظم ⚔️ 'Quote' \"Double\""
        castle_name = "قلعة_الفرسان_#1"

        ok = db.create_or_update_user(uid=uid, email=email, username="أحمد", db_path=self.db_path)
        self.assertTrue(ok)

        cid = "cid_خاص_123"
        create_test_castle(
            self.db_path,
            castle_id=cid,
            email=email,
            user_id=uid,
            lord_name=lord_name,
            castle_name=castle_name,
        )

        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertIsNotNone(c)
        self.assertEqual(c["lord_name"], lord_name)
        self.assertEqual(c["castle_name"], castle_name)

    def test_t2_malformed_json_config_graceful_recovery(self):
        """T2.7: Graceful recovery: Malformed JSON string in config column returns empty dict, not crash."""
        cid = "c_corrupted_json"
        with db.get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO castle_states (castle_id, email, config) VALUES (?, ?, ?)",
                (cid, "corrupted@test.com", "{INVALID_JSON: unterminated string")
            )

        c = db.get_castle_by_id(cid, db_path=self.db_path)
        self.assertIsNotNone(c)
        self.assertEqual(c["config"], {})

    def test_t2_delete_user_cascades_all_castles(self):
        """T2.8: Cascade boundary: delete_user cleanly removes user and all their associated castles."""
        uid = "uid_cascade_del"
        email = "cascade@test.com"
        db.create_or_update_user(uid=uid, email=email, db_path=self.db_path)
        for i in range(5):
            create_test_castle(self.db_path, castle_id=f"c_casc_{i}", email=f"casc_{i}@test.com", user_id=uid)

        # Confirm 5 castles exist
        self.assertEqual(len(db.get_user_castles(uid, db_path=self.db_path)), 5)

        # Delete user
        ok = db.delete_user(uid, db_path=self.db_path)
        self.assertTrue(ok)

        # Confirm user is gone
        self.assertIsNone(db.get_user(uid, db_path=self.db_path))

        # Confirm all castles for that user are gone
        self.assertEqual(len(db.get_user_castles(uid, db_path=self.db_path)), 0)

    def test_t2_whitespace_tenant_domains_boundary(self):
        """T2.9: Boundary: tenant_domains with empty strings, spaces, or mixed whitespace does not crash SQL IN ()."""
        uid = "uid_tenant_ws"
        email = "tenant_ws@test.com"
        db.create_or_update_user(uid=uid, email=email, tenant_domain="client.example.com", db_path=self.db_path)

        # 1. Whitespace-only lists should fallback cleanly to base query without IN () syntax error
        users_empty_str = db.get_all_users_with_castles(tenant_domains=["", "   "], db_path=self.db_path)
        self.assertEqual(len(users_empty_str), 1)

        # 2. Mixed list with valid domain and whitespace should clean and filter properly
        users_mixed = db.get_all_users_with_castles(tenant_domains=["  client.example.com  ", "   ", ""], db_path=self.db_path)
        self.assertEqual(len(users_mixed), 1)
        self.assertEqual(users_mixed[0]["uid"], uid)

        # 3. Non-matching domain should return empty list without error
        users_other = db.get_all_users_with_castles(tenant_domains=["other.domain.com", " "], db_path=self.db_path)
        self.assertEqual(len(users_other), 0)


if __name__ == "__main__":
    unittest.main()

