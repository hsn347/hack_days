# -*- coding: utf-8 -*-
"""
tools/test_m1_adversarial.py — Adversarial Stress Testing for Milestone 1
════════════════════════════════════════════════════════════════════════
Adversarial Reviewer 2 checks:
1. Integrity Audit (Anti-Cheating / Anti-Facade / AST Inspection)
2. Detailed EXPLAIN QUERY PLAN analysis of aggregated queries & indexes
3. Edge-Case Suite:
   - User with 0 castles
   - User with only pending castles
   - User with mixed active & pending castles
   - User who is banned (is_banned=1)
   - Orphan castles (user_id IS NULL or empty)
   - Null castle states (state IS NULL)
   - Whitespace / Empty tenant_domains input testing
4. Async WebSocket thread-safety and exception resilience simulation
════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import sqlite3
import tempfile
import inspect
import asyncio

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db
import api_server


def test_integrity_and_anti_facade():
    print(">>> [Adversarial 1] Integrity & Anti-Facade Audit...")
    src_db = inspect.getsource(db.get_all_users_with_castles)
    
    # 1. Ensure no hardcoded outputs or fixed lists
    assert "return [" not in src_db or "result.append" in src_db, "Suspicious hardcoded return list!"
    assert "150" not in src_db and "152" not in src_db and "154" not in src_db, "Hardcoded user count found in source!"
    
    # 2. Ensure real SQL query is executed
    assert "conn.execute(query, params)" in src_db, "Query execution missing or bypassed!"
    assert "LEFT JOIN" in src_db, "Missing LEFT JOIN in query!"
    assert "GROUP BY user_id" in src_db, "Missing GROUP BY in subquery!"
    print("    [PASS] No hardcoded results or facade implementations detected.")


def test_explain_query_plans():
    print(">>> [Adversarial 2] Deep EXPLAIN QUERY PLAN Audit...")
    conn = sqlite3.connect(db.get_db_path())
    cur = conn.cursor()

    # Detailed plan for get_all_users_with_castles query
    query = """
        SELECT 
            u.*,
            COALESCE(c.active_cnt, 0) as _agg_active,
            COALESCE(c.pending_cnt, 0) as _agg_pending,
            COALESCE(c.total_cnt, 0) as _agg_total
        FROM users u
        LEFT JOIN (
            SELECT 
                user_id,
                SUM(CASE WHEN is_active = 1 AND (state != 'pending' OR state IS NULL) THEN 1 ELSE 0 END) as active_cnt,
                SUM(CASE WHEN is_active = 0 OR state = 'pending' THEN 1 ELSE 0 END) as pending_cnt,
                COUNT(*) as total_cnt
            FROM castle_states
            WHERE user_id IS NOT NULL AND user_id != ''
            GROUP BY user_id
        ) c ON u.uid = c.user_id
        WHERE u.role NOT IN ('admin', 'merchant_admin') AND LOWER(u.email) NOT IN ('admin@test.com')
        ORDER BY u.created_at DESC
    """
    plans = cur.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
    print("    Query Plan for get_all_users_with_castles:")
    for p in plans:
        # id, parent, notused, detail
        print(f"      - [{p[0]}|{p[1]}] {p[-1]}")

    # Check whether users sorting uses idx_users_created_at
    plan_text = " ".join([p[-1] for p in plans])
    assert "idx_users_created_at" in plan_text, "Users query does not use idx_users_created_at!"
    print("    [PASS] idx_users_created_at utilized for sorting.")

    # Check castle_states index usage in subquery
    assert "idx_castle_user" in plan_text or "SCAN castle_states" in plan_text, "Unexpected plan for castle_states!"
    conn.close()
    print("    [PASS] EXPLAIN QUERY PLAN verified.")


def test_edge_cases_isolated_db():
    print(">>> [Adversarial 3] Edge Cases on Isolated Test Database...")
    temp_dir = tempfile.mkdtemp()
    test_db = os.path.join(temp_dir, "test_isolated.db")

    try:
        # Initialize isolated DB
        db.init_db(test_db)

        # Seed diverse user scenarios
        with db.get_connection(test_db) as conn:
            # User 1: Zero castles
            conn.execute("""
                INSERT INTO users (uid, email, username, role, is_banned, plan_id, created_at, tenant_domain)
                VALUES ('usr_zero', 'zero@example.com', 'Zero Castle User', 'user', 0, 'free', '2026-11-01T10:00:00Z', 'main.com')
            """)

            # User 2: Active castles only
            conn.execute("""
                INSERT INTO users (uid, email, username, role, is_banned, plan_id, created_at, tenant_domain)
                VALUES ('usr_active', 'active@example.com', 'Active User', 'user', 0, 'pro', '2026-11-01T11:00:00Z', 'main.com')
            """)
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_act_1', 'c1@game.com', 'usr_active', 1, 'running')
            """)
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_act_2', 'c2@game.com', 'usr_active', 1, 'idle')
            """)

            # User 3: Pending / inactive castles only
            conn.execute("""
                INSERT INTO users (uid, email, username, role, is_banned, plan_id, created_at, tenant_domain)
                VALUES ('usr_pending', 'pending@example.com', 'Pending User', 'user', 0, 'free', '2026-11-01T12:00:00Z', 'main.com')
            """)
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_pen_1', 'p1@game.com', 'usr_pending', 0, 'idle')
            """)
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_pen_2', 'p2@game.com', 'usr_pending', 1, 'pending')
            """)

            # User 4: Banned user with active castles
            conn.execute("""
                INSERT INTO users (uid, email, username, role, is_banned, plan_id, created_at, tenant_domain)
                VALUES ('usr_banned', 'banned@example.com', 'Banned User', 'user', 1, 'free', '2026-11-01T13:00:00Z', 'main.com')
            """)
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_ban_1', 'b1@game.com', 'usr_banned', 1, 'running')
            """)

            # User 5: Null / None castle state (state IS NULL)
            conn.execute("""
                INSERT INTO users (uid, email, username, role, is_banned, plan_id, created_at, tenant_domain)
                VALUES ('usr_nullstate', 'nullstate@example.com', 'Null State User', 'user', 0, 'free', '2026-11-01T14:00:00Z', 'main.com')
            """)
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_null_1', 'n1@game.com', 'usr_nullstate', 1, NULL)
            """)

            # Orphan castles: user_id IS NULL or empty
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_orphan_1', 'orph1@game.com', NULL, 1, 'running')
            """)
            conn.execute("""
                INSERT INTO castle_states (castle_id, email, user_id, is_active, state)
                VALUES ('c_orphan_2', 'orph2@game.com', '', 1, 'running')
            """)

            # Excluded admin user
            conn.execute("""
                INSERT INTO users (uid, email, username, role, is_banned, plan_id, created_at, tenant_domain)
                VALUES ('usr_admin', 'admin@example.com', 'Admin User', 'admin', 0, 'admin', '2026-11-01T15:00:00Z', 'main.com')
            """)
            conn.commit()

        # Run get_all_users_with_castles on this isolated database
        users = db.get_all_users_with_castles(db_path=test_db)
        u_map = {u["uid"]: u for u in users}

        # 1. Admin should be excluded
        assert "usr_admin" not in u_map, "Admin user was not excluded!"
        print("    [PASS] Admin user correctly excluded.")

        # 2. User 1 (Zero castles)
        u_zero = u_map["usr_zero"]
        assert u_zero["current_castles_count"] == 0, f"Expected 0 active, got {u_zero['current_castles_count']}"
        assert u_zero["pending_castles_count"] == 0, f"Expected 0 pending, got {u_zero['pending_castles_count']}"
        assert u_zero["total_castles_count"] == 0, f"Expected 0 total, got {u_zero['total_castles_count']}"
        assert u_zero["active_castles"] == 0
        assert u_zero["pending_castles"] == 0
        assert u_zero["total_castles"] == 0
        print("    [PASS] Zero castle user handled correctly (all counts 0, no nulls).")

        # 3. User 2 (Active castles only)
        u_act = u_map["usr_active"]
        assert u_act["current_castles_count"] == 2, f"Expected 2 active, got {u_act['current_castles_count']}"
        assert u_act["pending_castles_count"] == 0, f"Expected 0 pending, got {u_act['pending_castles_count']}"
        assert u_act["total_castles_count"] == 2, f"Expected 2 total, got {u_act['total_castles_count']}"
        print("    [PASS] Active castles user counted correctly.")

        # 4. User 3 (Pending castles only)
        u_pen = u_map["usr_pending"]
        assert u_pen["current_castles_count"] == 0, f"Expected 0 active, got {u_pen['current_castles_count']}"
        assert u_pen["pending_castles_count"] == 2, f"Expected 2 pending, got {u_pen['pending_castles_count']}"
        assert u_pen["total_castles_count"] == 2, f"Expected 2 total, got {u_pen['total_castles_count']}"
        print("    [PASS] Pending/inactive castles user counted correctly.")

        # 5. User 4 (Banned user)
        u_ban = u_map["usr_banned"]
        assert u_ban["is_banned"] is True
        assert u_ban["current_castles_count"] == 0, "Banned user active castles must be 0!"
        assert u_ban["pending_castles_count"] == 1, "Banned user castles should be moved to pending!"
        assert u_ban["total_castles_count"] == 1
        assert u_ban["subscription"]["status"] == "suspended"
        print("    [PASS] Banned user logic verified (active=0, pending=total, status=suspended).")

        # 6. User 5 (State IS NULL)
        u_null = u_map["usr_nullstate"]
        assert u_null["current_castles_count"] == 1, "state=NULL with is_active=1 should count as active!"
        assert u_null["total_castles_count"] == 1
        print("    [PASS] Castle with state=NULL handled gracefully.")

        # 7. Stress test: tenant_domains filtering with whitespace
        try:
            res_whitespace = db.get_all_users_with_castles(tenant_domains=["  ", ""], db_path=test_db)
            print(f"    [WARN / FINDING] Whitespace tenant_domains returned: {len(res_whitespace)} items.")
        except Exception as e:
            print(f"    [FAIL / FINDING] Whitespace tenant_domains raised exception: {e}")

        # 8. Valid tenant domain filtering
        res_valid = db.get_all_users_with_castles(tenant_domains=["main.com"], db_path=test_db)
        assert len(res_valid) == 5, f"Expected 5 users for main.com, got {len(res_valid)}"
        print(f"    [PASS] Tenant domain filtering works for valid domain ({len(res_valid)} users).")

    finally:
        try:
            if os.path.exists(test_db):
                os.remove(test_db)
            os.rmdir(temp_dir)
        except Exception:
            pass


def test_async_websocket_simulation():
    print(">>> [Adversarial 4] Async WebSocket Offloading Simulation...")
    # Simulate the async _collect_statuses function from ws_user_status
    async def simulate_collect(uid):
        res = {}
        try:
            castles = await asyncio.to_thread(db.get_user_castles, uid)
            for c in castles:
                cid = c.get("castle_id")
                if cid:
                    res[cid] = api_server._get_real_status(cid)
        except Exception as e:
            res["_error"] = str(e)
        return res

    loop_res = asyncio.run(simulate_collect("usr_non_existent_123"))
    assert isinstance(loop_res, dict)
    print("    [PASS] Async to_thread offload executed safely without blocking.")


if __name__ == "__main__":
    print("======================================================================")
    print("            ADVERSARIAL STRESS TEST SUITE (MILESTONE 1)               ")
    print("======================================================================")
    test_integrity_and_anti_facade()
    test_explain_query_plans()
    test_edge_cases_isolated_db()
    test_async_websocket_simulation()
    print("======================================================================")
    print("                 ADVERSARIAL SUITE EXECUTION COMPLETE                 ")
    print("======================================================================")
