import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

import tempfile
import sqlite3
from core import database as db

tf = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
tf.close()
db_p = tf.name

try:
    conn = sqlite3.connect(db_p)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE users (
            uid TEXT PRIMARY KEY, email TEXT, username TEXT, phone TEXT,
            role TEXT, is_banned INTEGER, created_at TEXT, tenant_domain TEXT,
            plan_id TEXT, plan_name TEXT, subscription_status TEXT,
            subscription_expires_at TEXT, max_castles_allowed INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE castle_states (
            castle_id TEXT PRIMARY KEY, user_id TEXT, email TEXT,
            is_active INTEGER, state TEXT, conn_state TEXT,
            castle_name TEXT, lord_name TEXT, config TEXT,
            raw_json TEXT, created_at TEXT, password TEXT
        )
    """)
    for i in range(10):
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"u{i}", f"user{i}@test.com", f"User {i}", "", "user", 0, f"2026-01-0{i+1}", "", "basic", "Basic", "active", "", 5)
        )
    conn.commit()
    conn.close()

    res1 = db.get_admin_castles_paginated(page=1, page_size=3, db_path=db_p)
    res2 = db.get_admin_castles_paginated(page=2, page_size=3, db_path=db_p)

    assert res1["total"] == 10, f"res1 total mismatch: {res1['total']}"
    assert res1["total_pages"] == 4, f"res1 total_pages mismatch: {res1['total_pages']}"
    assert len(res1["items"]) == 3, f"res1 len mismatch: {len(res1['items'])}"
    assert len(res2["items"]) == 3, f"res2 len mismatch: {len(res2['items'])}"
    assert res1["items"][0]["uid"] != res2["items"][0]["uid"], "items overlap between page 1 and page 2"
    assert res1["page"] == 1
    assert res2["page"] == 2
    assert res1["has_more"] is True

    # Also test search filtering
    res_search = db.get_admin_castles_paginated(page=1, page_size=10, search="user5", db_path=db_p)
    assert res_search["total"] == 1
    assert res_search["items"][0]["email"] == "user5@test.com"

    print("SUCCESS: Empirical DB pagination verified clean with SQL LIMIT and OFFSET.")
finally:
    if os.path.exists(db_p):
        os.unlink(db_p)
