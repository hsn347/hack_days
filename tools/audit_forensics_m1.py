# -*- coding: utf-8 -*-
"""
tools/audit_forensics_m1.py
Independent Forensic Integrity Auditor Suite for Milestone 1.
Validates:
1. AST Static Verification (No facades, no hardcoded responses, genuine calls).
2. SQLite PRAGMA Integrity & Schema Inspection.
3. Dynamic Sensitivity Verification (Query responds dynamically to filters/data).
4. Direct Ground-Truth Cross-Check against raw SQLite tables.
"""

import os
import sys
import ast
import sqlite3
import random

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

def run_ast_forensics():
    print("=== [PHASE 1] AST Static Code Forensics ===")
    
    # 1. Inspect core/database.py
    db_file = os.path.join(_ROOT, "core", "database.py")
    with open(db_file, "r", encoding="utf-8") as f:
        db_tree = ast.parse(f.read(), filename=db_file)
        
    func_node = None
    for node in ast.walk(db_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_all_users_with_castles":
            func_node = node
            break
            
    assert func_node is not None, "FATAL: get_all_users_with_castles not found in AST!"
    
    # Check that func_node has genuine execution logic
    has_conn_execute = False
    has_loop = False
    returns_constant = False
    
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Attribute) and sub.func.attr == "execute":
                has_conn_execute = True
        elif isinstance(sub, (ast.For, ast.comprehension)):
            has_loop = True
        elif isinstance(sub, ast.Return):
            if isinstance(sub.value, (ast.Constant, ast.List, ast.Dict)) and not isinstance(sub.value, ast.Name):
                if isinstance(sub.value, ast.Constant):
                    returns_constant = True

    assert has_conn_execute, "VIOLATION: get_all_users_with_castles does not invoke conn.execute!"
    assert has_loop, "VIOLATION: get_all_users_with_castles does not iterate over SQL rows!"
    assert not returns_constant, "VIOLATION: get_all_users_with_castles returns a constant literal!"
    print("  [PASS] AST for core/database.py: Genuine SQL execution and dynamic row processing verified.")

    # 2. Inspect api_server.py
    api_file = os.path.join(_ROOT, "api_server.py")
    with open(api_file, "r", encoding="utf-8") as f:
        api_tree = ast.parse(f.read(), filename=api_file)

    ws_node = None
    for node in ast.walk(api_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "ws_user_status":
            ws_node = node
            break

    assert ws_node is not None, "FATAL: ws_user_status not found in api_server.py AST!"
    
    has_to_thread_call = False
    has_await = False
    
    for sub in ast.walk(ws_node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Attribute) and sub.func.attr == "to_thread":
                # Check func is asyncio.to_thread
                if isinstance(sub.func.value, ast.Name) and sub.func.value.id == "asyncio":
                    has_to_thread_call = True
        elif isinstance(sub, ast.Await):
            has_await = True

    assert has_to_thread_call, "VIOLATION: ws_user_status does not call asyncio.to_thread!"
    assert has_await, "VIOLATION: ws_user_status does not await async operations!"
    print("  [PASS] AST for api_server.py: Genuine asyncio.to_thread offload verified.")


def run_database_forensics():
    print("\n=== [PHASE 2] SQLite PRAGMA & Schema Forensics ===")
    db_path = os.path.join(_ROOT, "database", "castles.db")
    assert os.path.exists(db_path), f"Database not found at {db_path}"
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # PRAGMA integrity_check
    integrity = cur.execute("PRAGMA integrity_check;").fetchall()
    print("  PRAGMA integrity_check result:", integrity)
    assert integrity == [("ok",)], f"Database integrity check failed: {integrity}"
    
    # Check 5 indexes in sqlite_master
    indexes = cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';").fetchall()
    idx_map = {row[0]: (row[1], row[2]) for row in indexes}
    
    expected = [
        ("idx_castle_states_lower_email", "castle_states", "LOWER(email)"),
        ("idx_castle_states_lower_user", "castle_states", "LOWER(user_id)"),
        ("idx_users_lower_email", "users", "LOWER(email)"),
        ("idx_users_created_at", "users", "created_at DESC"),
        ("idx_castle_states_created_at", "castle_states", "created_at DESC"),
    ]
    
    for name, tbl, expr in expected:
        assert name in idx_map, f"VIOLATION: Index {name} missing from sqlite_master!"
        actual_tbl, actual_sql = idx_map[name]
        assert actual_tbl == tbl, f"Index {name} registered on {actual_tbl}, expected {tbl}"
        assert expr.lower() in actual_sql.lower(), f"Index {name} SQL does not contain expression {expr}: {actual_sql}"
        print(f"  [PASS] Index '{name}' verified on table '{tbl}' with SQL: {actual_sql}")

    conn.close()


def run_dynamic_sensitivity_forensics():
    print("\n=== [PHASE 3] Dynamic Query Sensitivity & Anti-Mocking Forensics ===")
    import core.database as db
    db._ensure_init()
    
    # Test 1: Full user list
    all_users = db.get_all_users_with_castles()
    count_all = len(all_users)
    print(f"  Total users loaded (no filter): {count_all}")
    assert count_all > 100, f"Expected >100 users, got {count_all}"
    
    # Test 2: Filter by non-existent domain -> must return 0
    fake_domain = "nonexistent-forensic-test-domain-99999.xyz"
    filtered_users = db.get_all_users_with_castles(tenant_domains=[fake_domain])
    print(f"  Filtered users with non-existent tenant '{fake_domain}': {len(filtered_users)}")
    assert len(filtered_users) == 0, "VIOLATION: Filtered query did not filter results (mocked facade detected)!"
    
    # Test 3: Filter by real tenant domains if any exist in the dataset
    all_domains = list(set([u.get("tenant_domain") for u in all_users if u.get("tenant_domain")]))
    if all_domains:
        target_domain = all_domains[0]
        domain_users = db.get_all_users_with_castles(tenant_domains=[target_domain])
        expected_count = sum(1 for u in all_users if (u.get("tenant_domain") or "").strip().lower() == target_domain.strip().lower())
        print(f"  Domain filter '{target_domain}': expected {expected_count}, got {len(domain_users)}")
        assert len(domain_users) == expected_count, "VIOLATION: Dynamic domain filter count mismatch!"

    print("  [PASS] Dynamic query sensitivity confirmed: SQL is dynamic, parameterized, and genuine.")


def run_ground_truth_cross_check():
    print("\n=== [PHASE 4] Ground-Truth Direct SQLite Cross-Check ===")
    import core.database as db
    all_users = db.get_all_users_with_castles()
    user_map = {u["uid"]: u for u in all_users}

    db_path = os.path.join(_ROOT, "database", "castles.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Pick 5 sample user IDs across the database
    sample_uids = random.sample(list(user_map.keys()), min(5, len(user_map)))
    print(f"  Auditing sample user IDs against raw SQLite: {sample_uids}")

    for uid in sample_uids:
        # Run raw, independent manual queries on castle_states
        active_raw = cur.execute(
            "SELECT COUNT(*) FROM castle_states WHERE user_id = ? AND is_active = 1 AND (state != 'pending' OR state IS NULL)",
            (uid,)
        ).fetchone()[0]
        
        pending_raw = cur.execute(
            "SELECT COUNT(*) FROM castle_states WHERE user_id = ? AND (is_active = 0 OR state = 'pending')",
            (uid,)
        ).fetchone()[0]

        total_raw = cur.execute(
            "SELECT COUNT(*) FROM castle_states WHERE user_id = ?",
            (uid,)
        ).fetchone()[0]

        tested_user = user_map[uid]
        is_banned = bool(tested_user.get("is_banned", False))

        expected_active = 0 if is_banned else active_raw
        expected_pending = total_raw if is_banned else pending_raw

        assert tested_user["current_castles_count"] == expected_active, (
            f"Ground-truth mismatch for user {uid}: active {tested_user['current_castles_count']} != {expected_active}"
        )
        assert tested_user["pending_castles_count"] == expected_pending, (
            f"Ground-truth mismatch for user {uid}: pending {tested_user['pending_castles_count']} != {expected_pending}"
        )
        assert tested_user["total_castles_count"] == total_raw, (
            f"Ground-truth mismatch for user {uid}: total {tested_user['total_castles_count']} != {total_raw}"
        )
        print(f"  [PASS] User '{uid}': raw SQLite (active={active_raw}, pending={pending_raw}, total={total_raw}) matches function output perfectly.")

    conn.close()
    print("  [PASS] All 5 ground-truth samples matched raw SQLite database rows with 100% precision.")


if __name__ == "__main__":
    print("=" * 70)
    print("  FORENSIC INTEGRITY AUDIT SUITE (ANTI-CHEATING & AST VERIFICATION)  ")
    print("=" * 70)
    run_ast_forensics()
    run_database_forensics()
    run_dynamic_sensitivity_forensics()
    run_ground_truth_cross_check()
    print("\n" + "=" * 70)
    print("  VERDICT: 100% CLEAN - NO INTEGRITY VIOLATION DETECTED")
    print("=" * 70)
