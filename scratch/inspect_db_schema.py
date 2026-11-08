# -*- coding: utf-8 -*-
"""
tools/inspect_db_schema.py — أداة فحص جنائي وقراءة لهيكل قاعدة البيانات وفهارسها وخطط تنفيذ الاستعلامات
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "castles.db")

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    print("=== EXPLAIN QUERY PLANS ===")
    test_queries = [
        ("Query by lower(email) or lower(castle_id):", 
         "EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE lower(email) = 'test@example.com' OR lower(castle_id) = 'test@example.com' LIMIT 1"),
        ("Query castle exists by lower(email):",
         "EXPLAIN QUERY PLAN SELECT 1 FROM castle_states WHERE lower(email) = 'test@example.com' LIMIT 1"),
        ("Query upsert_castle_conn_state check:",
         "EXPLAIN QUERY PLAN SELECT castle_id, user_id, last_run_time FROM castle_states WHERE castle_id = 'c_123' OR lower(castle_id) = 'c_123' OR lower(email) = 'test@example.com' LIMIT 1"),
        ("Query get_user_castles with lower(user_id) ORDER BY created_at DESC:",
         "EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE user_id = 'uid_123' OR lower(user_id) = 'uid_123' ORDER BY created_at DESC"),
        ("Query active castles count:",
         "EXPLAIN QUERY PLAN SELECT COUNT(*) as cnt FROM castle_states WHERE user_id = 'uid_123' AND is_active = 1 AND state != 'pending'"),
        ("Query sync user castles ORDER BY created_at ASC:",
         "EXPLAIN QUERY PLAN SELECT castle_id, is_active, state, created_at FROM castle_states WHERE user_id = 'uid_123' ORDER BY created_at ASC, rowid ASC"),
        ("Query get_all_users ORDER BY created_at DESC:",
         "EXPLAIN QUERY PLAN SELECT * FROM users WHERE role NOT IN ('admin', 'merchant_admin') AND LOWER(email) NOT IN ('admin@test.com') ORDER BY created_at DESC"),
        ("Query user by uid or lower(email):",
         "EXPLAIN QUERY PLAN SELECT uid, email FROM users WHERE uid = 'u123' OR lower(email) = 'u123' LIMIT 1"),
        ("Query admin merchants overview:",
         "EXPLAIN QUERY PLAN SELECT COUNT(c.castle_id) as total_castles, COUNT(CASE WHEN c.state = 'running' OR c.conn_state = 'connected' THEN 1 END) as running_castles FROM castle_states c JOIN users u ON u.uid = c.user_id WHERE LOWER(u.tenant_domain) IN ('domain.com')"),
    ]

    for desc, q in test_queries:
        print(f"\n--> {desc}")
        print(f"SQL: {q}")
        try:
            plan = conn.execute(q).fetchall()
            for step in plan:
                print("   ", dict(step))
        except Exception as e:
            print("   ERROR:", e)

    conn.close()

if __name__ == "__main__":
    main()
