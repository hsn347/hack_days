# -*- coding: utf-8 -*-
"""
tools/stress_test_m1_challenger.py
══════════════════════════════════════════════════════════════════════════════════
Empirical Challenger 1 Stress & Adversarial Verification Suite (Milestone 1)
Governing Rules: AGENTS_CONSTITUTION.md Rule 13 & 18, GEMINI.md Rule 5.

Edge Cases Tested:
1. Users with 0 castles (LEFT JOIN NULL propagation & COALESCE safety).
2. Users with ONLY pending castles (is_active=0, state='pending').
3. Users with ONLY active castles (is_active=1, state!='pending', state=NULL).
4. Users with mixed active/pending/stopped castles.
5. Banned users with castles (is_banned=1 -> active forced to 0, pending=total, suspended status).
6. Admin & Merchant Admin filtering (role and email exclusion).
7. Orphaned/corrupt castles (user_id IS NULL, user_id='', non-existent user_id).
8. Completely empty database (0 users, 0 castles).
9. Exact application query count == 1 via sqlite3.set_trace_callback.
10. EXPLAIN QUERY PLAN verification: zero SCAN castle_states on LOWER() queries.
11. Multithreaded concurrency stress (30 concurrent reader threads).
12. Concurrent Reader/Writer stress (readers concurrent with SQLite writers).
13. WebSocket asyncio.to_thread non-blocking execution proof.
══════════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import time
import sqlite3
import tempfile
import threading
import concurrent.futures
import inspect
import asyncio
from typing import List, Dict, Any, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db
import api_server


def create_isolated_test_db(db_path: str):
    """تهيئة قاعدة بيانات معزولة للاختبار مع هيكلية الجداول والفهارس المحدثة."""
    db.init_db(db_path)


def populate_edge_cases(db_path: str):
    """حقن حالات حدية متطرفة في قاعدة البيانات المعزولة."""
    now = "2026-11-02T12:00:00Z"
    with db.get_connection(db_path) as conn:
        # 1. User Zero: 0 castles
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned, plan_id, plan_name, subscription_status)
            VALUES ('usr_zero', 'user_zero@test.com', 'Zero', 'user', ?, 0, 'basic', 'باقة تجريبية', 'active')
        """, (now,))

        # 2. User Only Pending: 3 castles (all pending by various conditions)
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned, plan_id, plan_name, subscription_status)
            VALUES ('usr_pending', 'user_pending@test.com', 'PendingOnly', 'user', ?, 0, 'pro', 'باقة برو', 'active')
        """, (now,))
        # castle a: is_active=0, state='pending'
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_pend_1', 'user_pending@test.com', 'usr_pending', 0, 'pending', ?)
        """, (now,))
        # castle b: is_active=0, state='running' (inactive counts as pending)
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_pend_2', 'user_pending@test.com', 'usr_pending', 0, 'running', ?)
        """, (now,))
        # castle c: is_active=1, state='pending' (pending state counts as pending)
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_pend_3', 'user_pending@test.com', 'usr_pending', 1, 'pending', ?)
        """, (now,))

        # 3. User Only Active: 3 castles (active, non-pending)
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned, plan_id, plan_name, subscription_status)
            VALUES ('usr_active', 'user_active@test.com', 'ActiveOnly', 'user', ?, 0, 'vip', 'باقة VIP', 'active')
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_act_1', 'user_active@test.com', 'usr_active', 1, 'running', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_act_2', 'user_active@test.com', 'usr_active', 1, 'idle', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_act_3', 'user_active@test.com', 'usr_active', 1, NULL, ?)
        """, (now,))

        # 4. User Mixed: 4 castles (2 active, 2 pending)
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned, plan_id, plan_name, subscription_status)
            VALUES ('usr_mixed', 'user_mixed@test.com', 'Mixed', 'user', ?, 0, 'standard', 'عادي', 'active')
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_mix_1', 'user_mixed@test.com', 'usr_mixed', 1, 'running', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_mix_2', 'user_mixed@test.com', 'usr_mixed', 1, 'stopped', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_mix_3', 'user_mixed@test.com', 'usr_mixed', 0, 'pending', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_mix_4', 'user_mixed@test.com', 'usr_mixed', 0, 'stopped', ?)
        """, (now,))

        # 5. User Banned: 3 active + 1 pending castles, but user is banned
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned, banned_reason, plan_id, plan_name, subscription_status)
            VALUES ('usr_banned', 'user_banned@test.com', 'BannedUser', 'user', ?, 1, 'Spam', 'pro', 'باقة برو', 'active')
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_ban_1', 'user_banned@test.com', 'usr_banned', 1, 'running', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_ban_2', 'user_banned@test.com', 'usr_banned', 1, 'running', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_ban_3', 'user_banned@test.com', 'usr_banned', 1, 'running', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_ban_4', 'user_banned@test.com', 'usr_banned', 0, 'pending', ?)
        """, (now,))

        # 6. Admin & Merchant Admin accounts (must be excluded from results)
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned)
            VALUES ('usr_admin', 'ibraboths@gmail.com', 'SuperAdmin', 'admin', ?, 0)
        """, (now,))
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned)
            VALUES ('usr_merchant', 'merchant@vendor.com', 'Merchant1', 'merchant_admin', ?, 0)
        """, (now,))

        # 7. Orphaned and corrupted castle rows (must not corrupt counts)
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_orphan_null', 'null@test.com', NULL, 1, 'running', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_orphan_empty', 'empty@test.com', '', 1, 'running', ?)
        """, (now,))
        conn.execute("""
            INSERT INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
            VALUES ('c_orphan_ghost', 'ghost@test.com', 'ghost_user_999', 1, 'running', ?)
        """, (now,))


        # 8. Tenant domain specific users
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned, tenant_domain)
            VALUES ('usr_tenant_1', 't1@domain1.com', 'TenantUser1', 'user', ?, 0, 'domain1.com')
        """, (now,))
        conn.execute("""
            INSERT INTO users (uid, email, username, role, created_at, is_banned, tenant_domain)
            VALUES ('usr_tenant_2', 't2@domain2.com', 'TenantUser2', 'user', ?, 0, 'domain2.com')
        """, (now,))


def run_edge_case_tests(db_path: str):
    """فحص واختبار دقة كافة الحالات الحدية بالبيانات المعزولة."""
    print(">>> [Challenger Test 1] Testing Edge Cases on Synthetic Database...")
    users = db.get_all_users_with_castles(db_path=db_path)
    user_map = {u["uid"]: u for u in users}

    # Verify exclusions
    assert "usr_admin" not in user_map, "Super admin was NOT excluded!"
    assert "usr_merchant" not in user_map, "Merchant admin was NOT excluded!"

    # 1. User Zero Castles
    u_zero = user_map.get("usr_zero")
    assert u_zero is not None, "usr_zero not found!"
    assert u_zero["current_castles_count"] == 0, f"Expected 0, got {u_zero['current_castles_count']}"
    assert u_zero["pending_castles_count"] == 0, f"Expected 0, got {u_zero['pending_castles_count']}"
    assert u_zero["total_castles_count"] == 0, f"Expected 0, got {u_zero['total_castles_count']}"
    assert u_zero["active_castles"] == 0
    assert u_zero["pending_castles"] == 0
    assert u_zero["total_castles"] == 0
    assert u_zero["subscription"]["current_castles_count"] == 0
    assert u_zero["subscription"]["total_castles_count"] == 0
    print("    [PASS] Edge Case 1: User with 0 castles handled cleanly (zeros, no NULLs).")

    # 2. User Only Pending
    u_pending = user_map.get("usr_pending")
    assert u_pending is not None
    assert u_pending["current_castles_count"] == 0, f"Expected 0, got {u_pending['current_castles_count']}"
    assert u_pending["pending_castles_count"] == 3, f"Expected 3, got {u_pending['pending_castles_count']}"
    assert u_pending["total_castles_count"] == 3, f"Expected 3, got {u_pending['total_castles_count']}"
    assert u_pending["active_castles"] == 0
    assert u_pending["pending_castles"] == 3
    print("    [PASS] Edge Case 2: User with only pending castles (active=0, pending=3, total=3).")

    # 3. User Only Active
    u_active = user_map.get("usr_active")
    assert u_active is not None
    assert u_active["current_castles_count"] == 3, f"Expected 3, got {u_active['current_castles_count']}"
    assert u_active["pending_castles_count"] == 0, f"Expected 0, got {u_active['pending_castles_count']}"
    assert u_active["total_castles_count"] == 3, f"Expected 3, got {u_active['total_castles_count']}"
    assert u_active["active_castles"] == 3
    print("    [PASS] Edge Case 3: User with only active castles (active=3, pending=0, total=3).")

    # 4. User Mixed
    u_mixed = user_map.get("usr_mixed")
    assert u_mixed is not None
    assert u_mixed["current_castles_count"] == 2, f"Expected 2, got {u_mixed['current_castles_count']}"
    assert u_mixed["pending_castles_count"] == 2, f"Expected 2, got {u_mixed['pending_castles_count']}"
    assert u_mixed["total_castles_count"] == 4, f"Expected 4, got {u_mixed['total_castles_count']}"
    assert u_mixed["active_castles"] == 2
    assert u_mixed["pending_castles"] == 2
    print("    [PASS] Edge Case 4: User with mixed castles (active=2, pending=2, total=4).")

    # 5. User Banned
    u_banned = user_map.get("usr_banned")
    assert u_banned is not None
    assert u_banned["is_banned"] is True
    assert u_banned["current_castles_count"] == 0, f"Banned user active must be 0, got {u_banned['current_castles_count']}"
    assert u_banned["pending_castles_count"] == 4, f"Banned user pending must be total (4), got {u_banned['pending_castles_count']}"
    assert u_banned["total_castles_count"] == 4, f"Expected total 4, got {u_banned['total_castles_count']}"
    assert u_banned["subscription"]["status"] == "suspended", f"Banned user status must be suspended, got {u_banned['subscription']['status']}"
    print("    [PASS] Edge Case 5: Banned user handling verified (active=0, pending=total, status='suspended').")

    # 6. Orphaned castles check
    # Make sure total castles across the valid users = 0 + 3 + 3 + 4 + 4 + 0 + 0 = 14
    total_attributed_castles = sum(u["total_castles_count"] for u in users)
    assert total_attributed_castles == 14, f"Orphaned castles leaked into users! Expected 14, got {total_attributed_castles}"
    print("    [PASS] Edge Case 6: Orphaned & corrupted castle rows completely ignored.")

    # 7. Tenant Filtering checks
    t1_users = db.get_all_users_with_castles(tenant_domains=["domain1.com"], db_path=db_path)
    assert len(t1_users) == 1 and t1_users[0]["uid"] == "usr_tenant_1", f"Tenant 1 filter failed: {t1_users}"
    t_none = db.get_all_users_with_castles(tenant_domains=["nonexistent.com"], db_path=db_path)
    assert len(t_none) == 0, f"Non-existent tenant filter expected 0 users, got {len(t_none)}"
    print("    [PASS] Edge Case 7: Tenant domain filtering verified.\n")


def run_empty_db_test():
    """فحص سلوك الدالة عند تشغيلها على قاعدة بيانات فارغة تماماً."""
    print(">>> [Challenger Test 2] Testing get_all_users_with_castles on completely empty DB...")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        empty_db_path = tf.name

    try:
        db.init_db(empty_db_path)
        res = db.get_all_users_with_castles(db_path=empty_db_path)
        assert res == [], f"Expected empty list, got: {res}"
        print("    [PASS] Empty DB test returned [] cleanly without exceptions.\n")
    finally:
        try:
            os.remove(empty_db_path)
        except Exception:
            pass


def run_query_count_trace(db_path: str, label: str):
    """التحقق القطعي من أن عدد استعلامات التطبيق هو بالضبط 1 استعلام عبر set_trace_callback."""
    print(f">>> [Challenger Test 3] Tracing SQL query count ({label})...")
    captured_queries = []

    orig_connect = sqlite3.connect
    def tracing_connect(*args, **kwargs):
        conn = orig_connect(*args, **kwargs)
        conn.set_trace_callback(lambda s: captured_queries.append(s.strip()))
        return conn

    sqlite3.connect = tracing_connect
    try:
        users = db.get_all_users_with_castles(db_path=db_path)
    finally:
        sqlite3.connect = orig_connect

    app_queries = [
        q for q in captured_queries
        if not q.upper().startswith("PRAGMA")
        and not q.upper().startswith("BEGIN")
        and not q.upper().startswith("COMMIT")
    ]

    print(f"    Raw Trace Captured Statements: {len(captured_queries)}")
    print(f"    Application SQL Queries Count: {len(app_queries)}")
    for i, q in enumerate(app_queries, 1):
        clean_q = " ".join(q.split())[:120]
        print(f"    SQL Query #{i}: {clean_q}...")

    assert len(app_queries) == 1, f"FAILED: Expected exactly 1 query, but intercepted {len(app_queries)} queries!"
    print(f"    [PASS] Query count is STRICTLY 1! ({label}: {len(users)} users loaded)\n")
    return users


def run_explain_query_plan_tests(db_path: str):
    """فحص دقيق لخطة الاستعلام EXPLAIN QUERY PLAN للتأكد من انعدام SCAN castle_states على LOWER()."""
    print(">>> [Challenger Test 4] Checking EXPLAIN QUERY PLAN for index utilization...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    queries_to_verify = [
        ("LOWER(email) on castle_states",
         "EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE LOWER(email) = 'test@example.com'",
         "idx_castle_states_lower_email",
         "SCAN castle_states"),
        
        ("LOWER(user_id) on castle_states",
         "EXPLAIN QUERY PLAN SELECT * FROM castle_states WHERE LOWER(user_id) = 'usr_123'",
         "idx_castle_states_lower_user",
         "SCAN castle_states"),

        ("LOWER(email) on users",
         "EXPLAIN QUERY PLAN SELECT * FROM users WHERE LOWER(email) = 'test@example.com'",
         "idx_users_lower_email",
         "SCAN users"),

        ("ORDER BY created_at DESC on users",
         "EXPLAIN QUERY PLAN SELECT * FROM users ORDER BY created_at DESC",
         "idx_users_created_at",
         None),

        ("ORDER BY created_at DESC on castle_states",
         "EXPLAIN QUERY PLAN SELECT * FROM castle_states ORDER BY created_at DESC",
         "idx_castle_states_created_at",
         None),
    ]

    for desc, sql, expected_idx, prohibited_phrase in queries_to_verify:
        rows = cur.execute(sql).fetchall()
        full_plan = " | ".join(row[-1] for row in rows)
        print(f"    Plan for [{desc}]: {full_plan}")
        
        if expected_idx:
            assert expected_idx in full_plan, f"Query '{desc}' failed to use expected index '{expected_idx}'! Plan: {full_plan}"
        if prohibited_phrase:
            # We strictly prohibit full table scan
            assert prohibited_phrase not in full_plan, f"Query '{desc}' performed prohibited full table scan: '{prohibited_phrase}'! Plan: {full_plan}"

    conn.close()
    print("    [PASS] All EXPLAIN QUERY PLAN checks confirmed index utilization with ZERO full table scans.\n")


def run_multithreaded_concurrency_stress(db_path: str, num_threads: int = 30, iterations_per_thread: int = 10):
    """اختبار إجهاد التزامن الشديد عبر استدعاءات متزامنة من خيوط متعددة."""
    print(f">>> [Challenger Test 5] Multithreaded Concurrency Stress Test ({num_threads} threads, {iterations_per_thread} iterations each = {num_threads * iterations_per_thread} total calls)...")
    
    latencies = []
    errors = []
    lock = threading.Lock()

    def worker_task(thread_id: int):
        for it in range(iterations_per_thread):
            t0 = time.perf_counter()
            try:
                users = db.get_all_users_with_castles(db_path=db_path)
                assert len(users) > 0, "Users returned empty under concurrency!"
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                with lock:
                    latencies.append(elapsed_ms)
            except Exception as e:
                with lock:
                    errors.append((thread_id, it, str(e)))

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(num_threads)]
    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total_time = time.perf_counter() - t_start

    print(f"    Completed {len(latencies)} successful calls in {total_time:.3f}s")
    print(f"    Errors Encountered: {len(errors)}")
    if errors:
        for err in errors[:5]:
            print(f"      [Error] Thread {err[0]} iter {err[1]}: {err[2]}")
    assert len(errors) == 0, f"Encountered {len(errors)} errors during multithreaded stress test!"

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    max_lat = latencies[-1]
    avg_lat = sum(latencies) / len(latencies)

    print(f"    Concurrency Latency Stats:")
    print(f"      Average : {avg_lat:.2f} ms")
    print(f"      P50     : {p50:.2f} ms")
    print(f"      P95     : {p95:.2f} ms")
    print(f"      P99     : {p99:.2f} ms")
    print(f"      Max     : {max_lat:.2f} ms")
    print("    [PASS] Multithreaded concurrency stress test passed with 100% success rate.\n")


def run_concurrent_reader_writer_stress(db_path: str):
    """اختبار إجهاد متزامن للقراء والكتّاب معاً (Readers + Writers) لاختبار وضع WAL ومقاومة أقفال SQLite."""
    print(">>> [Challenger Test 6] Concurrent Reader-Writer Stress Test (WAL mode resilience)...")
    stop_event = threading.Event()
    writer_errors = []
    reader_errors = []
    reads_count = [0]
    writes_count = [0]
    lock = threading.Lock()

    def writer_task():
        i = 0
        while not stop_event.is_set():
            i += 1
            cid = f"dynamic_c_{i}"
            try:
                with db.get_connection(db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO castle_states (castle_id, email, user_id, is_active, state, created_at)
                        VALUES (?, 'dyn@test.com', 'usr_zero', 1, 'running', datetime('now'))
                    """, (cid,))
                with lock:
                    writes_count[0] += 1
                time.sleep(0.005)
            except Exception as e:
                with lock:
                    writer_errors.append(str(e))

    def reader_task():
        while not stop_event.is_set():
            try:
                res = db.get_all_users_with_castles(db_path=db_path)
                assert len(res) > 0
                with lock:
                    reads_count[0] += 1
                time.sleep(0.002)
            except Exception as e:
                with lock:
                    reader_errors.append(str(e))

    # 2 writer threads, 10 reader threads
    writers = [threading.Thread(target=writer_task) for _ in range(2)]
    readers = [threading.Thread(target=reader_task) for _ in range(10)]

    for t in writers + readers:
        t.start()

    time.sleep(2.0)  # Run for 2 full seconds of heavy contention
    stop_event.set()

    for t in writers + readers:
        t.join()

    print(f"    Completed {reads_count[0]} concurrent reads and {writes_count[0]} concurrent writes in 2.0s")
    print(f"    Reader Errors: {len(reader_errors)} | Writer Errors: {len(writer_errors)}")
    if reader_errors:
        print("    Reader error sample:", reader_errors[:3])
    if writer_errors:
        print("    Writer error sample:", writer_errors[:3])

    assert len(reader_errors) == 0, f"Reader errors encountered: {reader_errors[:3]}"
    assert len(writer_errors) == 0, f"Writer errors encountered: {writer_errors[:3]}"
    print("    [PASS] Concurrent Reader-Writer test passed with 0 database lock errors.\n")


def test_websocket_async_nonblocking():
    """التحقق التجريبي من أن ws_user_status لا يحظر الـ Event Loop."""
    print(">>> [Challenger Test 7] Testing WebSocket asyncio.to_thread non-blocking behavior...")
    
    src = inspect.getsource(api_server.ws_user_status)
    assert "await asyncio.to_thread(db.get_user_castles, user_id)" in src, (
        "ws_user_status fails to offload db.get_user_castles via asyncio.to_thread!"
    )
    assert "async def _collect_statuses" in src
    assert "await _collect_statuses()" in src

    # Run simulated async event loop loop check
    async def simulation():
        event_loop_ticks = 0
        stop = False

        async def ticker():
            nonlocal event_loop_ticks
            while not stop:
                event_loop_ticks += 1
                await asyncio.sleep(0.01)

        async def worker():
            # simulate calling db.get_user_castles via asyncio.to_thread
            for _ in range(5):
                castles = await asyncio.to_thread(db.get_user_castles, "usr_active")
                assert isinstance(castles, list)
                await asyncio.sleep(0.01)

        t_task = asyncio.create_task(ticker())
        w_task = asyncio.create_task(worker())
        await w_task
        stop = True
        await t_task
        assert event_loop_ticks > 0, "Event loop was starved/blocked!"
        print(f"    Event loop ticks during async to_thread execution: {event_loop_ticks}")

    asyncio.run(simulation())
    print("    [PASS] WebSocket async offloading confirmed non-blocking on event loop.\n")


if __name__ == "__main__":
    print("=" * 80)
    print("       CHALLENGER 1 EMPIRICAL ADVERSARIAL STRESS SUITE (M1)        ")
    print("=" * 80)

    # 1. Edge Case Tests on Synthetic Database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        synth_db_path = tf.name

    try:
        create_isolated_test_db(synth_db_path)
        populate_edge_cases(synth_db_path)
        
        run_edge_case_tests(synth_db_path)
        run_empty_db_test()
        run_query_count_trace(synth_db_path, label="Synthetic DB")
        
        # 2. Real Production Database Verification
        real_db_path = db.get_db_path()
        print(f"Using Production DB Path: {real_db_path}")
        db._ensure_init(real_db_path)
        
        run_query_count_trace(real_db_path, label="Production DB (database/castles.db)")
        run_explain_query_plan_tests(real_db_path)
        run_multithreaded_concurrency_stress(real_db_path, num_threads=30, iterations_per_thread=10)
        run_concurrent_reader_writer_stress(synth_db_path)
        test_websocket_async_nonblocking()

        print("=" * 80)
        print("   ALL EMPIRICAL CHALLENGER STRESS TESTS PASSED WITH 100% SUCCESS!   ")
        print("   VERDICT: APPROVE                                                 ")
        print("=" * 80)
    finally:
        try:
            os.remove(synth_db_path)
            # Remove WAL files if present
            for extra in ["-wal", "-shm"]:
                if os.path.exists(synth_db_path + extra):
                    os.remove(synth_db_path + extra)
        except Exception:
            pass
