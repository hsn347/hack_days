# -*- coding: utf-8 -*-
"""
tools/benchmark_admin_baseline.py — Rigorous Baseline Performance Measurement
══════════════════════════════════════════════════════════════════════════════
Fulfills R1 Requirements & Explorer 3 Mandate:
- Fixed, documented test conditions (hardware, OS, data volume, sample iterations).
- Exact quantitative metrics (P50, P95, Mean, Min, Max, Memory, Payload sizes).
- Microbenchmarks for:
    1. Admin Database Queries & N+1 impact analysis
    2. Scalability across Small (10s), Medium (100s), Large (1000s) record sets
    3. Search & Filter latency under varying dataset scales
    4. Log file tailing performance across small/large log files
    5. Live local API server response latency (P50/P95)
    6. Memory allocation & GC footprints via tracemalloc
══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import json
import sqlite3
import platform
import statistics
import tracemalloc
import urllib.request
from typing import Any, Dict, List, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.database as db
from core.tenants import get_all_merchants, DEFAULT_TENANT


def get_system_environment_info() -> Dict[str, Any]:
    """Capture fixed, documented hardware and execution environment details."""
    return {
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "machine": platform.machine(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": db.get_db_path(),
        "db_size_bytes": os.path.getsize(db.get_db_path()) if os.path.exists(db.get_db_path()) else 0,
    }


def analyze_db_schema_and_indexes() -> Dict[str, Any]:
    """Inspect schema, existing indexes, and row counts."""
    path = db.get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        # Row counts
        user_count = cur.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        castle_count = cur.execute("SELECT COUNT(*) as c FROM castle_states").fetchone()["c"]
        active_castles = cur.execute("SELECT COUNT(*) as c FROM castle_states WHERE is_active = 1").fetchone()["c"]
        banned_users = cur.execute("SELECT COUNT(*) as c FROM users WHERE is_banned = 1").fetchone()["c"]
        pending_users = cur.execute("SELECT COUNT(*) as c FROM users WHERE subscription_status = 'pending_approval'").fetchone()["c"]

        # Indexes
        indexes = []
        for row in cur.execute("SELECT tbl_name, name, sql FROM sqlite_master WHERE type='index'"):
            indexes.append({
                "table": row["tbl_name"],
                "name": row["name"],
                "sql": row["sql"],
            })

        # Table columns
        user_cols = [r["name"] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
        castle_cols = [r["name"] for r in cur.execute("PRAGMA table_info(castle_states)").fetchall()]

        return {
            "counts": {
                "users": user_count,
                "castles": castle_count,
                "active_castles": active_castles,
                "banned_users": banned_users,
                "pending_users": pending_users,
            },
            "columns": {
                "users": user_cols,
                "castle_states": castle_cols,
            },
            "indexes": indexes,
        }
    finally:
        conn.close()


def benchmark_function(fn, samples: int = 100) -> Dict[str, float]:
    """Execute a callable N times and compute precise timing stats (P50, P95, mean, min, max) in milliseconds."""
    timings = []
    # Warmup
    for _ in range(max(2, samples // 10)):
        fn()

    tracemalloc.start()
    for _ in range(samples):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000.0)
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    timings.sort()
    n = len(timings)
    p50_idx = int(0.50 * n)
    p95_idx = int(0.95 * n)

    return {
        "samples": samples,
        "p50_ms": round(timings[p50_idx], 3),
        "p95_ms": round(timings[p95_idx], 3),
        "mean_ms": round(statistics.mean(timings), 3),
        "min_ms": round(min(timings), 3),
        "max_ms": round(max(timings), 3),
        "stdev_ms": round(statistics.stdev(timings), 3) if len(timings) > 1 else 0.0,
        "peak_memory_kb": round(peak_mem / 1024.0, 2),
    }


def benchmark_current_get_all_users_with_castles(samples: int = 50) -> Dict[str, Any]:
    """Benchmark current implementation of get_all_users_with_castles (which exhibits 3N+1 queries)."""
    # Count queries per call
    path = db.get_db_path()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    user_count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()

    # 1 for get_all_users, plus 3 queries per user in loop
    total_queries_per_call = 1 + (3 * user_count)

    timing = benchmark_function(lambda: db.get_all_users_with_castles(), samples=samples)
    timing["queries_executed_per_call"] = total_queries_per_call
    timing["user_count"] = user_count
    return timing


def benchmark_optimized_get_all_users_with_castles(samples: int = 50) -> Dict[str, Any]:
    """
    Benchmark an optimized single SQL query with GROUP BY aggregating castle counts,
    proving the algorithmic gain of eliminating 3N+1.
    """
    def _optimized_query():
        path = db.get_db_path()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            # Single query fetching users left-joined with aggregated castle counts
            sql = """
                SELECT 
                    u.*,
                    COALESCE(c_agg.current_cnt, 0) as current_castles_count,
                    COALESCE(c_agg.pending_cnt, 0) as pending_castles_count,
                    COALESCE(c_agg.total_cnt, 0) as total_castles_count
                FROM users u
                LEFT JOIN (
                    SELECT 
                        user_id,
                        SUM(CASE WHEN is_active = 1 AND state != 'pending' THEN 1 ELSE 0 END) as current_cnt,
                        SUM(CASE WHEN is_active = 0 OR state = 'pending' THEN 1 ELSE 0 END) as pending_cnt,
                        COUNT(*) as total_cnt
                    FROM castle_states
                    WHERE user_id IS NOT NULL AND user_id != ''
                    GROUP BY user_id
                ) c_agg ON u.uid = c_agg.user_id
            """
            cur = conn.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            return rows
        finally:
            conn.close()

    timing = benchmark_function(_optimized_query, samples=samples)
    timing["queries_executed_per_call"] = 1
    return timing


def benchmark_admin_users_castles(samples: int = 30) -> Dict[str, Any]:
    """Benchmark full load of all users with full castle objects (used by /api/admin/users-castles)."""
    def _run():
        users = db.get_all_users()
        all_castles = db.get_all_castles()
        castles_by_user = {}
        for c in all_castles:
            uid = str(c.get("user_id", "")).strip()
            if uid:
                castles_by_user.setdefault(uid, []).append(c)
        result = []
        for u in users:
            uid = str(u.get("uid", "")).strip()
            u_castles = castles_by_user.get(uid, [])
            u_data = dict(u)
            u_data["castles"] = u_castles
            u_data["castles_count"] = len(u_castles)
            result.append(u_data)
        # Serialize to test payload size
        payload = json.dumps({"users": result})
        return len(payload)

    # Measure payload size
    payload_size_bytes = _run()
    timing = benchmark_function(_run, samples=samples)
    timing["payload_size_kb"] = round(payload_size_bytes / 1024.0, 2)
    return timing


def benchmark_data_volume_scalability() -> Dict[str, Any]:
    """
    Simulate Admin Dashboard rendering & data processing across:
      - Small: 10 records
      - Medium: 100 records
      - Large: 1,000 records
      - Stress: 5,000 records
    Measures: JSON payload size, client deserialization time, filtering latency, and sorting latency.
    """
    scales = [10, 100, 1000, 5000]
    results = {}

    sample_castle = {
        "id": "castle_sample_12345",
        "email": "lord_warrior_99@example.com",
        "lord_name": "السلطان_المنصور",
        "castle_level": 35,
        "lord_power": 125000000,
        "state": "running",
        "is_active": True,
        "config": {"auto_attack": True, "auto_gather": True, "gather_tiles": [1, 2, 3]},
        "resources": {"food": 10000000, "wood": 12000000, "iron": 5000000, "gold": 25000},
        "bot_status": {"state": "running", "conn_state": "running", "last_run_time": "2026-11-02T18:00:00Z"},
    }

    sample_user = {
        "uid": "usr_abc_1234567890",
        "email": "customer_test@example.com",
        "username": "خالد_السلطان",
        "role": "user",
        "is_banned": False,
        "subscription": {
            "plan_name": "10 حسابات (30 يوم)",
            "status": "active",
            "expires_at": "2026-12-02T18:00:00Z",
            "days_remaining": 30,
            "max_castles_allowed": 10,
            "current_castles_count": 8,
        },
        "castles_count": 8,
        "running_count": 5,
    }

    for n in scales:
        dataset = []
        for i in range(n):
            u = dict(sample_user)
            u["uid"] = f"user_{i}_{n}"
            u["email"] = f"user_{i}_{n}@empire.test"
            u["castles"] = [dict(sample_castle, id=f"c_{i}_{k}") for k in range(min(5, max(1, i % 10)))]
            dataset.append(u)

        # JSON serialize & size
        json_str = json.dumps(dataset)
        payload_kb = len(json_str.encode("utf-8")) / 1024.0

        # Parse timing
        def _parse():
            return json.loads(json_str)
        parse_timing = benchmark_function(_parse, samples=30)

        # Filter timing (simulating client-side search query)
        search_term = "user_4"
        def _filter():
            term = search_term.lower()
            return [
                u for u in dataset
                if term in u["email"].lower() or term in u["uid"].lower()
            ]
        filter_timing = benchmark_function(_filter, samples=50)

        # Sort timing (simulating client-side sorting by days_remaining or castles_count)
        def _sort():
            return sorted(dataset, key=lambda x: (x["subscription"]["days_remaining"], x["castles_count"]))
        sort_timing = benchmark_function(_sort, samples=50)

        results[f"scale_{n}"] = {
            "record_count": n,
            "payload_size_kb": round(payload_kb, 2),
            "parse_p50_ms": parse_timing["p50_ms"],
            "parse_p95_ms": parse_timing["p95_ms"],
            "filter_p50_ms": filter_timing["p50_ms"],
            "filter_p95_ms": filter_timing["p95_ms"],
            "sort_p50_ms": sort_timing["p50_ms"],
            "sort_p95_ms": sort_timing["p95_ms"],
            "peak_memory_kb": parse_timing["peak_memory_kb"],
        }

    return results


def benchmark_log_tailing() -> Dict[str, Any]:
    """
    Benchmark _tail_file log reader across various log sizes
    (100 lines, 1,000 lines, 10,000 lines, 50,000 lines, 100,000 lines).
    """
    from api_server import _tail_file

    results = {}
    test_log_dir = os.path.join(_ROOT, "logs")
    os.makedirs(test_log_dir, exist_ok=True)
    temp_log_path = os.path.join(test_log_dir, "_benchmark_test_tail.log")

    line_counts = [100, 1000, 10000, 50000, 100000]

    try:
        for total_lines in line_counts:
            # Generate synthetic log
            with open(temp_log_path, "w", encoding="utf-8") as f:
                for i in range(total_lines):
                    f.write(f"[18:00:{i%60:02d}][INFO][bot] Task execution step #{i} completed successfully for castle.\n")

            file_size_kb = os.path.getsize(temp_log_path) / 1024.0

            # Benchmark reading last 100 lines
            def _tail_100():
                return _tail_file(temp_log_path, n_lines=100)
            t_100 = benchmark_function(_tail_100, samples=40)

            # Benchmark reading last 500 lines
            def _tail_500():
                return _tail_file(temp_log_path, n_lines=500)
            t_500 = benchmark_function(_tail_500, samples=40)

            results[f"log_{total_lines}_lines"] = {
                "total_lines": total_lines,
                "file_size_kb": round(file_size_kb, 2),
                "tail_100_p50_ms": t_100["p50_ms"],
                "tail_100_p95_ms": t_100["p95_ms"],
                "tail_500_p50_ms": t_500["p50_ms"],
                "tail_500_p95_ms": t_500["p95_ms"],
            }
    finally:
        if os.path.exists(temp_log_path):
            try:
                os.remove(temp_log_path)
            except Exception:
                pass

    return results


def benchmark_api_health_endpoint(samples: int = 50) -> Dict[str, Any]:
    """Measure actual round-trip HTTP response time for running local server."""
    url = "http://127.0.0.1:8000/api/health"
    try:
        def _fetch():
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.read()

        timing = benchmark_function(_fetch, samples=samples)
        timing["url"] = url
        timing["status"] = "online"
        return timing
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_full_baseline_benchmark() -> Dict[str, Any]:
    """Execute all benchmark suites and assemble structured quantitative report."""
    print(">>> 1/7 Collecting Environment Info...")
    env_info = get_system_environment_info()

    print(">>> 2/7 Analyzing Database Schema & Counts...")
    schema_info = analyze_db_schema_and_indexes()

    print(">>> 3/7 Benchmarking Admin DB Queries (get_admin_stats, merchants)...")
    admin_stats_timing = benchmark_function(lambda: db.get_admin_stats(), samples=50)

    merchants = get_all_merchants()
    merchants_timing = benchmark_function(lambda: db.get_merchants_overview_stats(merchants), samples=50)

    print(">>> 4/7 Benchmarking 3N+1 Issue (Current vs Optimized SQL)...")
    current_users_timing = benchmark_current_get_all_users_with_castles(samples=40)
    optimized_users_timing = benchmark_optimized_get_all_users_with_castles(samples=40)
    admin_users_castles_timing = benchmark_admin_users_castles(samples=30)

    print(">>> 5/7 Benchmarking Data Volume Scalability (10, 100, 1000, 5000)...")
    scalability_results = benchmark_data_volume_scalability()

    print(">>> 6/7 Benchmarking Log File Tailing Performance...")
    log_results = benchmark_log_tailing()

    print(">>> 7/7 Benchmarking Running API Endpoint...")
    api_health_timing = benchmark_api_health_endpoint(samples=50)

    # Compute Speedup Ratio
    speedup = 1.0
    if optimized_users_timing["mean_ms"] > 0:
        speedup = round(current_users_timing["mean_ms"] / optimized_users_timing["mean_ms"], 2)

    full_report = {
        "metadata": {
            "title": "Baseline Performance Measurement Report (Pre-Optimization)",
            "standard": "R1 Deep System Audit & AGENTS_CONSTITUTION.md Rule 13",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "environment": env_info,
        "database_audit": schema_info,
        "backend_queries": {
            "get_admin_stats": admin_stats_timing,
            "get_merchants_overview_stats": merchants_timing,
            "get_all_users_with_castles_current_3N_plus_1": current_users_timing,
            "get_all_users_with_castles_optimized_single_query": optimized_users_timing,
            "speedup_factor_x": speedup,
            "get_admin_users_castles_full": admin_users_castles_timing,
        },
        "scalability_scale_tests": scalability_results,
        "log_tailing_benchmarks": log_results,
        "local_api_latency": api_health_timing,
    }

    return full_report


if __name__ == "__main__":
    report = run_full_baseline_benchmark()
    output_path = os.path.join(_ROOT, ".agents", "teamwork", "explorer_survey_3", "baseline_raw_metrics.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Baseline measurements completed successfully. Saved to:\n{output_path}\n")
    print(json.dumps(report["backend_queries"], indent=2, ensure_ascii=False))
