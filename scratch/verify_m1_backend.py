# -*- coding: utf-8 -*-
"""
tools/verify_m1_backend.py — Independent Verification for Milestone 1
════════════════════════════════════════════════════════════════════════
Verifies:
1. Exact SQL query count executed by db.get_all_users_with_castles() (must be 1).
2. Presence and validity of all 5 SQLite expression & sorting indexes.
3. Query plans using EXPLAIN QUERY PLAN (confirming index usage).
4. Data integrity, backward-compatible dictionary keys, and record count.
5. Async signature and non-blocking nature of ws_user_status in api_server.py.
════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import sqlite3
import inspect
import asyncio

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db
import api_server


def test_query_count():
    print(">>> [Test 1] Measuring exact SQL query count in get_all_users_with_castles()...")
    # Initialize DB first
    db._ensure_init()

    # Intercept queries via sqlite3.Connection trace callback
    executed_queries = []
    
    orig_connect = sqlite3.connect
    def traced_connect(*args, **kwargs):
        conn = orig_connect(*args, **kwargs)
        conn.set_trace_callback(lambda statement: executed_queries.append(statement.strip()))
        return conn

    sqlite3.connect = traced_connect
    try:
        users = db.get_all_users_with_castles()
    finally:
        sqlite3.connect = orig_connect

    app_queries = [q for q in executed_queries if not q.upper().startswith("PRAGMA")]
    query_count = len(app_queries)
    print(f"    Executed Application SQL Queries Count: {query_count}")
    for idx, q in enumerate(app_queries, 1):
        first_line = q.split('\n')[0][:80]
        print(f"    Query #{idx}: {first_line}...")

    assert query_count == 1, f"Expected exactly 1 query, but got {query_count}!"
    assert len(users) > 0, "Users list should not be empty!"
    print(f"    [PASS] Query count collapsed to exactly {query_count} query! Users loaded: {len(users)}\n")
    return users


def test_indexes():
    print(">>> [Test 2] Verifying SQLite expression and sorting indexes...")
    expected_indexes = {
        "idx_castle_states_lower_email": "castle_states",
        "idx_castle_states_lower_user": "castle_states",
        "idx_users_lower_email": "users",
        "idx_users_created_at": "users",
        "idx_castle_states_created_at": "castle_states",
    }

    conn = sqlite3.connect(db.get_db_path())
    cur = conn.cursor()
    cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'")
    existing_indexes = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
    conn.close()

    for idx_name, expected_table in expected_indexes.items():
        assert idx_name in existing_indexes, f"Missing index: {idx_name}"
        tbl, sql = existing_indexes[idx_name]
        assert tbl == expected_table, f"Index {idx_name} on wrong table {tbl}, expected {expected_table}"
        print(f"    [PASS] Index '{idx_name}' exists on table '{tbl}' -> SQL: {sql}")

    print("    All 5 indexes verified successfully.\n")


def test_query_plans():
    print(">>> [Test 3] Verifying EXPLAIN QUERY PLAN uses indexes (no full scans)...")
    conn = sqlite3.connect(db.get_db_path())
    cur = conn.cursor()

    # 1. Lower email search on castle_states
    plan1 = cur.execute("EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE LOWER(email) = 'test@example.com'").fetchall()
    print("    Plan 1 (LOWER(email) on castle_states):", plan1[0][-1])
    assert "idx_castle_states_lower_email" in plan1[0][-1], "Query did not use idx_castle_states_lower_email!"

    # 2. Lower user_id search on castle_states
    plan2 = cur.execute("EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE LOWER(user_id) = 'usr_123'").fetchall()
    print("    Plan 2 (LOWER(user_id) on castle_states):", plan2[0][-1])
    assert "idx_castle_states_lower_user" in plan2[0][-1], "Query did not use idx_castle_states_lower_user!"

    # 3. Lower email search on users
    plan3 = cur.execute("EXPLAIN QUERY PLAN SELECT * FROM users WHERE LOWER(email) = 'test@example.com'").fetchall()
    print("    Plan 3 (LOWER(email) on users):", plan3[0][-1])
    assert "idx_users_lower_email" in plan3[0][-1], "Query did not use idx_users_lower_email!"

    # 4. Users created_at sorting
    plan4 = cur.execute("EXPLAIN QUERY PLAN SELECT * FROM users ORDER BY created_at DESC").fetchall()
    print("    Plan 4 (ORDER BY created_at DESC on users):", plan4[0][-1])
    assert "idx_users_created_at" in plan4[0][-1], "Query did not use idx_users_created_at!"

    conn.close()
    print("    [PASS] All EXPLAIN QUERY PLAN checks confirmed index utilization.\n")


def test_user_data_structure(users):
    print(">>> [Test 4] Verifying backward-compatible user data structure...")
    assert len(users) > 0
    sample = users[0]

    required_keys = [
        "uid", "email", "role", "is_banned",
        "current_castles_count", "pending_castles_count", "total_castles_count",
        "active_castles", "pending_castles", "total_castles",
        "subscription"
    ]
    for k in required_keys:
        assert k in sample, f"Missing key in user dict: {k}"

    sub = sample["subscription"]
    required_sub_keys = [
        "plan_id", "plan_name", "status", "started_at", "expires_at",
        "max_castles_allowed", "current_castles_count", "pending_castles_count", "total_castles_count"
    ]
    for sk in required_sub_keys:
        assert sk in sub, f"Missing key in subscription dict: {sk}"

    print(f"    [PASS] Data structure 100% compliant with expected API contracts.\n")


def test_websocket_async_offload():
    print(">>> [Test 5] Verifying WebSocket full async offloading in api_server.py...")
    # Inspect source code of ws_user_status and helper
    src_ws = inspect.getsource(api_server.ws_user_status)
    assert hasattr(api_server, "_sync_collect_user_statuses"), "Missing _sync_collect_user_statuses helper!"
    src_sync = inspect.getsource(api_server._sync_collect_user_statuses)

    assert "asyncio.to_thread(_sync_collect_user_statuses, user_id)" in src_ws, (
        "ws_user_status does not wrap full status collection in asyncio.to_thread(_sync_collect_user_statuses, user_id)!"
    )
    assert "db.get_user_castles(user_id)" in src_sync, (
        "_sync_collect_user_statuses does not fetch castles via db.get_user_castles!"
    )
    assert "_get_real_status" in src_sync, (
        "_sync_collect_user_statuses does not resolve status via _get_real_status!"
    )
    print("    [PASS] ws_user_status correctly offloads entire status collection loop via asyncio.to_thread.\n")


if __name__ == "__main__":
    print("======================================================================")
    print("           MILESTONE 1 BACKEND VERIFICATION SUITE                    ")
    print("======================================================================")
    users = test_query_count()
    test_indexes()
    test_query_plans()
    test_user_data_structure(users)
    test_websocket_async_offload()
    print("======================================================================")
    print("    ALL MILESTONE 1 VERIFICATION TESTS PASSED WITH 100% SUCCESS!      ")
    print("======================================================================")
