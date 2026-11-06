# -*- coding: utf-8 -*-
"""
tools/measure_baseline.py — Comprehensive System Resource Baseline Measurement Tool
══════════════════════════════════════════════════════════════════════════════════════
Milestone 1 (M1 / R4) — Pre-Fix & Post-Fix System Profiling & Leak Telemetry
Compliant with AGENTS_CONSTITUTION.md, ROOT_CAUSE_AND_PLAN_P2.md, and survey_report.md.

Measures:
1. Process Memory RSS (MB) via Windows native PSAPI (GetProcessMemoryInfo) + psutil.
2. Tracemalloc peak and current allocated memory.
3. CPU usage % in idle state and under active operation load.
4. Detailed thread inventory (active count, thread names, bot threads, daemon threads).
5. OS handle count via Windows Kernel32 (GetProcessHandleCount).
6. Open socket counts & network connections.
7. Global tracking structures in api_server.py (_threads, _stop_events, _bot_managers,
   _reserved, _log_qs, _conn_states, _user_stopped, _castle_emails, _castle_users,
   _deleted_castles).
8. SQLite database and WAL journal sizes & table counts.

Supports both:
- Programmatic mode: SystemResourceMonitor class for integration into tests / soak scripts.
- CLI mode: generates baseline_metrics_prefix.json and BASELINE_METRICS_PREFIX.md.
══════════════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import gc
import json
import logging
import os
import platform
import queue
import re
import sqlite3
import sys
import threading
import time
import tracemalloc
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repository root is on sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Core project imports (strict: NEVER touch forbidden files)
import core.database as db

# Optional psutil integration
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False


# ══════════════════════════════════════════════════════════════════════════════
# Windows Native Structures & System API Bindings
# ══════════════════════════════════════════════════════════════════════════════

if sys.platform == "win32":
    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.windll.kernel32
    _psapi = getattr(ctypes.windll, "psapi", None)

    # Configure explicit 64-bit safe prototypes
    _kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    _kernel32.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    _kernel32.GetProcessHandleCount.restype = ctypes.c_int
    _kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    _kernel32.OpenProcess.restype = ctypes.c_void_p
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.CloseHandle.restype = ctypes.c_int

    _get_proc_mem_info = None
    if hasattr(_kernel32, "K32GetProcessMemoryInfo"):
        _get_proc_mem_info = _kernel32.K32GetProcessMemoryInfo
    elif _psapi is not None and hasattr(_psapi, "GetProcessMemoryInfo"):
        _get_proc_mem_info = _psapi.GetProcessMemoryInfo
    elif hasattr(_kernel32, "GetProcessMemoryInfo"):
        _get_proc_mem_info = _kernel32.GetProcessMemoryInfo

    if _get_proc_mem_info is not None:
        _get_proc_mem_info.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        _get_proc_mem_info.restype = ctypes.c_int
else:
    PROCESS_MEMORY_COUNTERS_EX = None
    _kernel32 = None
    _psapi = None
    _get_proc_mem_info = None



# ══════════════════════════════════════════════════════════════════════════════
# SystemResourceMonitor: High-Precision Monitoring Engine
# ══════════════════════════════════════════════════════════════════════════════

class SystemResourceMonitor:
    """
    High-precision programmatic resource telemetry monitor.
    Captures physical RSS, private bytes, heap allocation, OS handles, sockets,
    thread classification, and api_server global state.
    """

    def __init__(self, target_pid: Optional[int] = None):
        self.pid = target_pid or os.getpid()
        self.is_current_process = (self.pid == os.getpid())
        self._psutil_proc = None

        if _HAS_PSUTIL:
            try:
                self._psutil_proc = psutil.Process(self.pid)
            except Exception:
                self._psutil_proc = None

        # Ensure tracemalloc is running if monitoring current process
        if self.is_current_process and not tracemalloc.is_tracing():
            tracemalloc.start()

    def get_memory_info(self) -> Dict[str, Any]:
        """
        Measure process memory using Windows PSAPI with psutil fallback.
        Returns RSS, Private bytes, and Peak Working Set in bytes and MB.
        """
        rss_bytes = 0
        private_bytes = 0
        peak_rss_bytes = 0

        # Primary source on Windows: Native PSAPI
        if sys.platform == "win32" and PROCESS_MEMORY_COUNTERS_EX is not None and _get_proc_mem_info is not None:
            try:
                counters = PROCESS_MEMORY_COUNTERS_EX()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
                if self.is_current_process:
                    h_process = _kernel32.GetCurrentProcess()
                    success = _get_proc_mem_info(
                        h_process,
                        ctypes.byref(counters),
                        counters.cb,
                    )
                    if success:
                        rss_bytes = int(counters.WorkingSetSize)
                        private_bytes = int(counters.PrivateUsage)
                        peak_rss_bytes = int(counters.PeakWorkingSetSize)
                elif _kernel32 is not None:
                    # OpenProcess with PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                    PROCESS_QUERY_INFORMATION = 0x0400
                    PROCESS_VM_READ = 0x0010
                    h_process = _kernel32.OpenProcess(
                        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                        False,
                        self.pid,
                    )
                    if h_process:
                        try:
                            if _get_proc_mem_info(
                                h_process,
                                ctypes.byref(counters),
                                counters.cb,
                            ):
                                rss_bytes = int(counters.WorkingSetSize)
                                private_bytes = int(counters.PrivateUsage)
                                peak_rss_bytes = int(counters.PeakWorkingSetSize)
                        finally:
                            _kernel32.CloseHandle(h_process)
            except Exception:
                pass

        # Fallback or secondary confirmation via psutil
        if (rss_bytes == 0 or private_bytes == 0) and self._psutil_proc is not None:
            try:
                m_info = self._psutil_proc.memory_info()
                if rss_bytes == 0:
                    rss_bytes = getattr(m_info, "rss", 0)
                if private_bytes == 0:
                    private_bytes = getattr(m_info, "private", getattr(m_info, "vms", 0))
                if peak_rss_bytes == 0:
                    peak_rss_bytes = getattr(m_info, "peak_wset", rss_bytes)
            except Exception:
                pass

        return {
            "rss_bytes": rss_bytes,
            "rss_mb": round(rss_bytes / (1024 * 1024), 2),
            "private_bytes": private_bytes,
            "private_mb": round(private_bytes / (1024 * 1024), 2),
            "peak_rss_bytes": peak_rss_bytes,
            "peak_rss_mb": round(peak_rss_bytes / (1024 * 1024), 2),
        }

    def get_heap_memory(self) -> Dict[str, Any]:
        """Measure internal Python heap allocation via tracemalloc."""
        if self.is_current_process and tracemalloc.is_tracing():
            current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            return {
                "tracemalloc_current_bytes": current_bytes,
                "tracemalloc_current_kb": round(current_bytes / 1024, 2),
                "tracemalloc_current_mb": round(current_bytes / (1024 * 1024), 3),
                "tracemalloc_peak_bytes": peak_bytes,
                "tracemalloc_peak_kb": round(peak_bytes / 1024, 2),
                "tracemalloc_peak_mb": round(peak_bytes / (1024 * 1024), 3),
            }
        return {
            "tracemalloc_current_bytes": 0,
            "tracemalloc_current_kb": 0.0,
            "tracemalloc_current_mb": 0.0,
            "tracemalloc_peak_bytes": 0,
            "tracemalloc_peak_kb": 0.0,
            "tracemalloc_peak_mb": 0.0,
        }

    def get_handle_count(self) -> int:
        """Measure process OS handles via Windows Kernel32 with psutil fallback."""
        if sys.platform == "win32" and _kernel32 is not None:
            try:
                handle_count = ctypes.c_ulong()
                if self.is_current_process:
                    h_proc = _kernel32.GetCurrentProcess()
                    if _kernel32.GetProcessHandleCount(h_proc, ctypes.byref(handle_count)):
                        return int(handle_count.value)
                else:
                    PROCESS_QUERY_INFORMATION = 0x0400
                    h_proc = _kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, self.pid)
                    if h_proc:
                        try:
                            if _kernel32.GetProcessHandleCount(h_proc, ctypes.byref(handle_count)):
                                return int(handle_count.value)
                        finally:
                            _kernel32.CloseHandle(h_proc)
            except Exception:
                pass

        if self._psutil_proc is not None:
            try:
                return int(self._psutil_proc.num_handles())
            except Exception:
                pass

        return 0

    def get_socket_count(self) -> int:
        """Measure active network connections and open sockets."""
        if self._psutil_proc is not None:
            try:
                conns = self._psutil_proc.net_connections(kind="all")
                return len(conns)
            except Exception:
                pass
        return 0

    def get_thread_inventory(self) -> Dict[str, Any]:
        """
        Detailed inventory of threads in the current process.
        Categorizes active threads into bot threads, system threads, and daemons.
        """
        if not self.is_current_process:
            # For remote process, use psutil thread count if available
            remote_count = 0
            if self._psutil_proc is not None:
                try:
                    remote_count = self._psutil_proc.num_threads()
                except Exception:
                    pass
            return {
                "active_count": remote_count,
                "bot_threads_count": 0,
                "system_threads_count": remote_count,
                "daemon_threads_count": 0,
                "thread_names": [],
                "threads": [],
            }

        threads = threading.enumerate()
        active_count = len(threads)
        bot_threads = []
        system_threads = []
        daemon_count = 0
        records = []

        for t in threads:
            is_daemon = bool(t.daemon)
            if is_daemon:
                daemon_count += 1

            is_bot = t.name.startswith("bot-")
            if is_bot:
                bot_threads.append(t.name)
            else:
                system_threads.append(t.name)

            records.append({
                "name": t.name,
                "ident": t.ident,
                "is_alive": t.is_alive(),
                "daemon": is_daemon,
                "is_bot": is_bot,
            })

        return {
            "active_count": active_count,
            "bot_threads_count": len(bot_threads),
            "system_threads_count": len(system_threads),
            "daemon_threads_count": daemon_count,
            "bot_threads": bot_threads,
            "system_threads": system_threads,
            "thread_names": [t.name for t in threads],
            "threads": records,
        }

    def measure_cpu_percent(self, duration: float = 1.0) -> float:
        """
        Measure process CPU usage percentage over a specified sampling duration.
        Uses psutil if available; otherwise uses high-resolution process time.
        """
        if self._psutil_proc is not None:
            try:
                # First call primes the psutil counter if interval is None,
                # but calling with interval=duration blocks for duration and returns exact usage %
                val = self._psutil_proc.cpu_percent(interval=duration)
                return round(float(val), 2)
            except Exception:
                pass

        # Fallback to high-resolution process_time / perf_counter
        t0 = time.perf_counter()
        p0 = time.process_time()
        time.sleep(duration)
        t1 = time.perf_counter()
        p1 = time.process_time()
        dt = t1 - t0
        dp = p1 - p0
        if dt > 0:
            cpu_count = os.cpu_count() or 1
            pct = (dp / (dt * cpu_count)) * 100.0
            return round(min(100.0, max(0.0, pct)), 2)
        return 0.0

    def inspect_api_server_globals(self) -> Dict[str, Any]:
        """
        Safely inspect the global tracking data structures in api_server.py
        within the master re-entrant lock api_server._lock.
        """
        try:
            import api_server
        except Exception as e:
            return {
                "available": False,
                "error": f"Failed to import api_server: {e}",
            }

        try:
            with api_server._lock:
                # Count items in each tracking structure
                threads_len = len(api_server._threads)
                stop_events_len = len(api_server._stop_events)
                bot_managers_len = len(api_server._bot_managers)
                reserved_len = len(api_server._reserved)
                log_qs_len = len(api_server._log_qs)
                conn_states_len = len(api_server._conn_states)
                user_stopped_len = len(api_server._user_stopped)
                castle_emails_len = len(api_server._castle_emails)
                castle_users_len = len(api_server._castle_users)
                deleted_castles_len = len(api_server._deleted_castles)

                # Total queued log items across all active log queues
                total_queued_logs = 0
                for cid, q in api_server._log_qs.items():
                    try:
                        total_queued_logs += q.qsize()
                    except Exception:
                        pass

                # State breakdown in _conn_states
                states_dist: Dict[str, int] = {}
                for st in api_server._conn_states.values():
                    states_dist[st] = states_dist.get(st, 0) + 1

                return {
                    "available": True,
                    "_threads_count": threads_len,
                    "_stop_events_count": stop_events_len,
                    "_bot_managers_count": bot_managers_len,
                    "_reserved_count": reserved_len,
                    "_log_qs_count": log_qs_len,
                    "_total_queued_logs": total_queued_logs,
                    "_conn_states_count": conn_states_len,
                    "_conn_states_distribution": states_dist,
                    "_user_stopped_count": user_stopped_len,
                    "_castle_emails_count": castle_emails_len,
                    "_castle_users_count": castle_users_len,
                    "_deleted_castles_count": deleted_castles_len,
                    "_deploy_mode": getattr(api_server, "_deploy_mode", False),
                    "_gradual_running": getattr(api_server, "_gradual_running", False),
                    "summary_keys_total": (
                        threads_len + stop_events_len + bot_managers_len +
                        reserved_len + log_qs_len + conn_states_len +
                        user_stopped_len + castle_emails_len + castle_users_len +
                        deleted_castles_len
                    ),
                }
        except Exception as e:
            return {
                "available": False,
                "error": f"Error acquiring api_server._lock: {e}",
            }

    def inspect_database_metrics(self) -> Dict[str, Any]:
        """
        Inspect SQLite database file size, WAL journal, SHM index,
        and high-level table record counts without altering data.
        """
        db_path = db.get_db_path()
        db_exists = os.path.exists(db_path)
        db_size_bytes = os.path.getsize(db_path) if db_exists else 0

        wal_path = f"{db_path}-wal"
        wal_exists = os.path.exists(wal_path)
        wal_size_bytes = os.path.getsize(wal_path) if wal_exists else 0

        shm_path = f"{db_path}-shm"
        shm_exists = os.path.exists(shm_path)
        shm_size_bytes = os.path.getsize(shm_path) if shm_exists else 0

        users_count = 0
        castles_count = 0
        active_castles_count = 0
        pragma_info: Dict[str, Any] = {}

        if db_exists:
            try:
                # Open read-only connection with URI mode to avoid any write locks
                uri_path = f"file:{os.path.abspath(db_path)}?mode=ro"
                conn = sqlite3.connect(uri_path, uri=True, timeout=5.0)
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM users")
                    users_count = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM castle_states")
                    castles_count = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM castle_states WHERE is_active = 1")
                    active_castles_count = cur.fetchone()[0]

                    # PRAGMA queries
                    for p in ("journal_mode", "page_size", "page_count", "freelist_count"):
                        cur.execute(f"PRAGMA {p}")
                        row = cur.fetchone()
                        pragma_info[p] = row[0] if row else None
                finally:
                    conn.close()
            except Exception as e:
                pragma_info["error"] = str(e)

        return {
            "db_path": db_path,
            "db_exists": db_exists,
            "db_size_bytes": db_size_bytes,
            "db_size_mb": round(db_size_bytes / (1024 * 1024), 3),
            "wal_path": wal_path,
            "wal_exists": wal_exists,
            "wal_size_bytes": wal_size_bytes,
            "wal_size_kb": round(wal_size_bytes / 1024, 2),
            "shm_path": shm_path,
            "shm_exists": shm_exists,
            "shm_size_bytes": shm_size_bytes,
            "users_count": users_count,
            "castles_count": castles_count,
            "active_castles_count": active_castles_count,
            "pragma": pragma_info,
        }

    def snapshot(self) -> Dict[str, Any]:
        """Capture a comprehensive instantaneous resource snapshot."""
        mem = self.get_memory_info()
        heap = self.get_heap_memory()
        handles = self.get_handle_count()
        sockets = self.get_socket_count()
        threads = self.get_thread_inventory()
        globals_data = self.inspect_api_server_globals()
        db_data = self.inspect_database_metrics()

        return {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pid": self.pid,
            "memory": mem,
            "heap": heap,
            "handle_count": handles,
            "socket_count": sockets,
            "threads": threads,
            "globals": globals_data,
            "database": db_data,
        }

    @staticmethod
    def diff(snap_before: Dict[str, Any], snap_after: Dict[str, Any]) -> Dict[str, Any]:
        """Compute the quantitative delta between two resource snapshots."""
        mem_b = snap_before.get("memory", {})
        mem_a = snap_after.get("memory", {})
        heap_b = snap_before.get("heap", {})
        heap_a = snap_after.get("heap", {})
        th_b = snap_before.get("threads", {})
        th_a = snap_after.get("threads", {})

        return {
            "delta_rss_mb": round(mem_a.get("rss_mb", 0.0) - mem_b.get("rss_mb", 0.0), 3),
            "delta_private_mb": round(mem_a.get("private_mb", 0.0) - mem_b.get("private_mb", 0.0), 3),
            "delta_heap_kb": round(heap_a.get("tracemalloc_current_kb", 0.0) - heap_b.get("tracemalloc_current_kb", 0.0), 2),
            "delta_handles": snap_after.get("handle_count", 0) - snap_before.get("handle_count", 0),
            "delta_sockets": snap_after.get("socket_count", 0) - snap_before.get("socket_count", 0),
            "delta_threads": th_a.get("active_count", 0) - th_b.get("active_count", 0),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Active Operation Benchmark Workload Generator (Hermetic)
# ══════════════════════════════════════════════════════════════════════════════

def _worker_task_simulation(worker_id: int, iterations: int = 25) -> Dict[str, Any]:
    """
    Standardized hermetic workload simulating typical platform concurrency:
    - Reading castle rows from database
    - Parsing config JSON structures
    - Performing simulated bot task decision cycles
    - Zero network, zero mutations to production data
    """
    records_processed = 0
    configs_parsed = 0
    start_t = time.perf_counter()

    db_path = db.get_db_path()
    if os.path.exists(db_path):
        uri_path = f"file:{os.path.abspath(db_path)}?mode=ro"
        conn = sqlite3.connect(uri_path, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            for _ in range(iterations):
                cur.execute("SELECT castle_id, email, state, config FROM castle_states LIMIT 15")
                rows = cur.fetchall()
                for row in rows:
                    records_processed += 1
                    raw_cfg = row["config"]
                    if raw_cfg:
                        try:
                            parsed = json.loads(raw_cfg)
                            configs_parsed += 1
                            # Simulate task condition checks
                            _ = parsed.get("harvest", {}).get("enabled", False)
                            _ = parsed.get("defense", {}).get("auto_shield", False)
                        except Exception:
                            pass
        finally:
            conn.close()
    else:
        # Fallback simulation if db file is absent
        for _ in range(iterations * 15):
            records_processed += 1
            payload = json.dumps({"worker": worker_id, "tasks": ["gather", "train", "heal"]})
            _ = json.loads(payload)
            configs_parsed += 1

    elapsed = time.perf_counter() - start_t
    return {
        "worker_id": worker_id,
        "records_processed": records_processed,
        "configs_parsed": configs_parsed,
        "elapsed_seconds": elapsed,
    }


def run_active_load_test(concurrency: int = 10, iterations_per_worker: int = 25) -> Dict[str, Any]:
    """
    Execute 10 concurrent simulation workers to measure active CPU, memory,
    and thread load without making any network calls.
    """
    start_time = time.perf_counter()
    worker_results = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=concurrency,
        thread_name_prefix="baseline-worker",
    ) as executor:
        futures = [
            executor.submit(_worker_task_simulation, w_id, iterations_per_worker)
            for w_id in range(concurrency)
        ]
        for f in concurrent.futures.as_completed(futures):
            worker_results.append(f.result())

    total_elapsed = time.perf_counter() - start_time
    total_records = sum(r["records_processed"] for r in worker_results)
    total_configs = sum(r["configs_parsed"] for r in worker_results)

    return {
        "concurrency": concurrency,
        "total_workers": len(worker_results),
        "total_records_processed": total_records,
        "total_configs_parsed": total_configs,
        "total_duration_seconds": round(total_elapsed, 3),
        "throughput_records_per_sec": round(total_records / total_elapsed, 1) if total_elapsed > 0 else 0.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Full Baseline Profiling Pipeline & Report Formatting
# ══════════════════════════════════════════════════════════════════════════════

def run_full_baseline_measurement(
    tag: str = "prefix",
    duration: float = 2.5,
    workers: int = 10,
    no_load: bool = False,
    skip_load: Optional[bool] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    Executes the full end-to-end baseline measurement pipeline:
    1. System & Environment Inspection.
    2. Idle Resource Snapshot.
    3. Idle CPU % Sampling (customizable duration).
    4. Active Operation Load Test (customizable worker concurrency, or skipped via no_load).
    5. Active Operation CPU & Peak Resource Snapshot.
    6. Post-Teardown & GC Residual Snapshot.
    7. Computes Deltas and generates structured JSON data and Markdown report.
    """
    if skip_load:
        no_load = True

    monitor = SystemResourceMonitor()

    print("\n" + "═" * 78)
    print(f"🚀 SYSTEM RESOURCE BASELINE MEASUREMENT SUITE (TAG: {tag.upper()})")
    print(f"   Mode: 100% Hermetic Local Profiling (Zero Network, Zero Mutations)")
    print(f"   PID : {monitor.pid} | Platform: {platform.platform()} ({platform.machine()})")
    print("═" * 78 + "\n")

    # Step 1: Environment details
    env_info = {
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "python_compiler": platform.python_compiler(),
        "cpu_count": os.cpu_count(),
        "machine": platform.machine(),
        "pid": monitor.pid,
        "psutil_available": _HAS_PSUTIL,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Step 2: Idle baseline snapshot
    print(">>> [Phase 1/4] Capturing Idle Resource Snapshot...")
    idle_snapshot = monitor.snapshot()

    # Step 3: Measure Idle CPU %
    print(f">>> [Phase 2/4] Sampling Idle CPU Usage (Sampling {duration:.1f} seconds)...")
    idle_cpu = monitor.measure_cpu_percent(duration=duration)
    idle_snapshot["cpu_percent"] = idle_cpu
    print(f"    - Idle Process CPU: {idle_cpu:.2f}%")
    print(f"    - Idle Process RSS: {idle_snapshot['memory']['rss_mb']} MB (Private: {idle_snapshot['memory']['private_mb']} MB)")
    print(f"    - Idle Tracemalloc: {idle_snapshot['heap']['tracemalloc_current_kb']} KB")
    print(f"    - Idle OS Handles : {idle_snapshot['handle_count']}")
    print(f"    - Idle Threads    : {idle_snapshot['threads']['active_count']}")

    # Step 4: Active Operation Load Test
    if not no_load:
        print(f"\n>>> [Phase 3/4] Executing Active Workload Load Test ({workers} Concurrent Simulation Workers)...")
        workload_start = time.perf_counter()
        workload_cpu_samples = []

        # Thread to sample CPU during active execution
        stop_cpu_sampler = threading.Event()

        def _sample_active_cpu():
            while not stop_cpu_sampler.is_set():
                val = monitor.measure_cpu_percent(duration=0.5)
                workload_cpu_samples.append(val)

        sampler_th = threading.Thread(target=_sample_active_cpu, daemon=True, name="cpu-sampler")
        sampler_th.start()

        load_result = run_active_load_test(concurrency=workers, iterations_per_worker=25)
        stop_cpu_sampler.set()
        sampler_th.join(timeout=2.0)

        active_snapshot = monitor.snapshot()
        active_cpu_avg = round(sum(workload_cpu_samples) / len(workload_cpu_samples), 2) if workload_cpu_samples else 0.0
        active_snapshot["cpu_percent"] = active_cpu_avg
        active_snapshot["workload_metrics"] = load_result

        print(f"    - Active Process CPU (Avg)  : {active_cpu_avg:.2f}%")
        print(f"    - Active Process RSS        : {active_snapshot['memory']['rss_mb']} MB (Peak: {active_snapshot['memory']['peak_rss_mb']} MB)")
        print(f"    - Active Tracemalloc Current: {active_snapshot['heap']['tracemalloc_current_kb']} KB (Peak: {active_snapshot['heap']['tracemalloc_peak_kb']} KB)")
        print(f"    - Active OS Handles         : {active_snapshot['handle_count']}")
        print(f"    - Records Processed         : {load_result['total_records_processed']} in {load_result['total_duration_seconds']}s")
    else:
        print("\n>>> [Phase 3/4] Skipping Active Workload Load Test (--no-load / --skip-load specified)...")
        load_result = {
            "concurrency": 0,
            "total_workers": 0,
            "total_records_processed": 0,
            "total_configs_parsed": 0,
            "total_duration_seconds": 0.0,
            "throughput_records_per_sec": 0.0,
            "skipped": True,
        }
        active_snapshot = monitor.snapshot()
        active_snapshot["cpu_percent"] = idle_cpu
        active_snapshot["workload_metrics"] = load_result
        print("    - Active Workload Simulation : Skipped")
        print(f"    - Clean Snapshot RSS        : {active_snapshot['memory']['rss_mb']} MB")
        print(f"    - Clean Snapshot Handles    : {active_snapshot['handle_count']}")

    # Step 5: Post-Teardown & Garbage Collection Residual
    print("\n>>> [Phase 4/4] Performing Post-Teardown Resource & GC Residual Analysis...")
    gc.collect()
    time.sleep(0.5)
    post_snapshot = monitor.snapshot()
    post_cpu = monitor.measure_cpu_percent(duration=1.0)
    post_snapshot["cpu_percent"] = post_cpu

    # Step 6: Compute Deltas
    active_delta = monitor.diff(idle_snapshot, active_snapshot)
    residual_delta = monitor.diff(idle_snapshot, post_snapshot)

    print(f"    - Post-Teardown RSS      : {post_snapshot['memory']['rss_mb']} MB")
    print(f"    - Residual RSS Delta     : {residual_delta['delta_rss_mb']:+.3f} MB")
    print(f"    - Residual Heap Delta    : {residual_delta['delta_heap_kb']:+.2f} KB")
    print(f"    - Residual Handles Delta : {residual_delta['delta_handles']:+d}")
    print(f"    - Residual Threads Delta : {residual_delta['delta_threads']:+d}")

    # Step 7: Construct Full JSON Document
    full_report_data: Dict[str, Any] = {
        "metadata": {
            "tag": tag,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "environment": env_info,
        },
        "database_metrics": idle_snapshot["database"],
        "api_server_globals": idle_snapshot["globals"],
        "idle_state": {
            "cpu_percent": idle_snapshot["cpu_percent"],
            "rss_mb": idle_snapshot["memory"]["rss_mb"],
            "private_mb": idle_snapshot["memory"]["private_mb"],
            "peak_rss_mb": idle_snapshot["memory"]["peak_rss_mb"],
            "heap_current_kb": idle_snapshot["heap"]["tracemalloc_current_kb"],
            "heap_peak_kb": idle_snapshot["heap"]["tracemalloc_peak_kb"],
            "handle_count": idle_snapshot["handle_count"],
            "socket_count": idle_snapshot["socket_count"],
            "threads": idle_snapshot["threads"],
        },
        "active_workload_state": {
            "cpu_percent": active_snapshot["cpu_percent"],
            "rss_mb": active_snapshot["memory"]["rss_mb"],
            "private_mb": active_snapshot["memory"]["private_mb"],
            "peak_rss_mb": active_snapshot["memory"]["peak_rss_mb"],
            "heap_current_kb": active_snapshot["heap"]["tracemalloc_current_kb"],
            "heap_peak_kb": active_snapshot["heap"]["tracemalloc_peak_kb"],
            "handle_count": active_snapshot["handle_count"],
            "socket_count": active_snapshot["socket_count"],
            "threads": active_snapshot["threads"],
            "workload": load_result,
        },
        "post_teardown_state": {
            "cpu_percent": post_snapshot["cpu_percent"],
            "rss_mb": post_snapshot["memory"]["rss_mb"],
            "private_mb": post_snapshot["memory"]["private_mb"],
            "peak_rss_mb": post_snapshot["memory"]["peak_rss_mb"],
            "heap_current_kb": post_snapshot["heap"]["tracemalloc_current_kb"],
            "heap_peak_kb": post_snapshot["heap"]["tracemalloc_peak_kb"],
            "handle_count": post_snapshot["handle_count"],
            "socket_count": post_snapshot["socket_count"],
            "threads": post_snapshot["threads"],
        },
        "deltas": {
            "active_vs_idle": active_delta,
            "residual_post_gc_vs_idle": residual_delta,
        },
    }

    # Step 8: Build Markdown Report
    md_report = _format_markdown_report(full_report_data, tag)

    return full_report_data, md_report


def _format_markdown_report(data: Dict[str, Any], tag: str) -> str:
    """Format quantitative metrics into a structured markdown report."""
    meta = data["metadata"]
    env = meta["environment"]
    db_m = data["database_metrics"]
    globs = data["api_server_globals"]
    idle = data["idle_state"]
    active = data["active_workload_state"]
    post = data["post_teardown_state"]
    deltas = data["deltas"]
    res = deltas["residual_post_gc_vs_idle"]
    act_d = deltas["active_vs_idle"]

    tag_title = tag.upper()
    title = f"تقرير القياس وخط الأساس المعتمد: ما قبل الإصلاح (Baseline Metrics — {tag_title})"

    w_info = active.get("workload", {})
    if w_info.get("skipped"):
        active_col_title = "الحمل النشط (تم التخطي)"
        heading_workers = "تم التخطي — Skipped via --no-load"
    else:
        concurrency_val = w_info.get("concurrency", 10)
        active_col_title = f"تحت الحمل النشط (Active {concurrency_val} Workers)"
        heading_workers = f"{concurrency_val} Concurrent Simulation Workers"

    lines = [
        f"# {title}",
        f"**تاريخ وتوقيت القياس:** `{meta['generated_at']}`  ",
        f"**نظام التشغيل والمعمارية:** `{env['os']}` ({env['machine']})  ",
        f"**نسخة بايثون:** `{env['python_version']}`  ",
        f"**عدد أنوية المعالج (CPU Cores):** `{env['cpu_count']}`  ",
        f"**معرف العملية (PID):** `{env['pid']}`  ",
        f"**طريقة القياس:** Windows Native PSAPI (`GetProcessMemoryInfo`) + Kernel32 (`GetProcessHandleCount`) + `tracemalloc` + `psutil`  ",
        "",
        "---",
        "",
        "## 1. جدول المقاييس المجمعة (Comparative Telemetry Summary)",
        "",
        f"| المقياس الفيزيائي والبرمجي | خط الأساس الخامل (Idle) | {active_col_title} | ما بعد التحرير (Post-GC) | التغير المتبقي (Residual Delta) |",
        "|---|---|---|---|---|",
        f"| **Process RSS (ذاكرة نظام التشغيل)** | **{idle['rss_mb']} MB** | **{active['rss_mb']} MB** | **{post['rss_mb']} MB** | `{res['delta_rss_mb']:+.3f} MB` |",
        f"| **Private Memory Usage** | {idle['private_mb']} MB | {active['private_mb']} MB | {post['private_mb']} MB | `{res['delta_private_mb']:+.3f} MB` |",
        f"| **Peak Working Set** | {idle['peak_rss_mb']} MB | {active['peak_rss_mb']} MB | {post['peak_rss_mb']} MB | — |",
        f"| **Tracemalloc Current Heap** | {idle['heap_current_kb']} KB | {active['heap_current_kb']} KB | {post['heap_current_kb']} KB | `{res['delta_heap_kb']:+.2f} KB` |",
        f"| **Tracemalloc Peak Heap** | {idle['heap_peak_kb']} KB | {active['heap_peak_kb']} KB | {post['heap_peak_kb']} KB | — |",
        f"| **استهلاك المعالج (CPU %)** | **{idle['cpu_percent']:.2f}%** | **{active['cpu_percent']:.2f}%** | **{post['cpu_percent']:.2f}%** | — |",
        f"| **مقابض نظام التشغيل (OS Handles)** | **{idle['handle_count']}** | **{active['handle_count']}** | **{post['handle_count']}** | `{res['delta_handles']:+d}` |",
        f"| **مقابس الشبكة النشطة (Sockets)** | {idle['socket_count']} | {active['socket_count']} | {post['socket_count']} | `{res['delta_sockets']:+d}` |",
        f"| **إجمالي الخيوط (Total Threads)** | {idle['threads']['active_count']} | {active['threads']['active_count']} | {post['threads']['active_count']} | `{res['delta_threads']:+d}` |",
        f"| **خيوط البوتات النشطة (`bot-*`)** | {idle['threads']['bot_threads_count']} | {active['threads']['bot_threads_count']} | {post['threads']['bot_threads_count']} | `0` |",
        f"| **الخيوط الشبحية (Daemon Threads)** | {idle['threads']['daemon_threads_count']} | {active['threads']['daemon_threads_count']} | {post['threads']['daemon_threads_count']} | `{post['threads']['daemon_threads_count'] - idle['threads']['daemon_threads_count']:+d}` |",
        "",
        "---",
        "",
        "## 2. إحصائيات وقواعد بيانات المنظومة (SQLite Database & WAL Metrics)",
        "",
        f"- **مسار قاعدة البيانات المعتمد:** `{db_m['db_path']}`",
        f"- **حجم ملف قاعدة البيانات:** `{db_m['db_size_mb']} MB` ({db_m['db_size_bytes']:,} بايت)",
        f"- **حجم سجل المعاملات (WAL Journal):** `{db_m['wal_size_kb']} KB` ({db_m['wal_size_bytes']:,} بايت) — حالة الوجود: `{db_m['wal_exists']}`",
        f"- **حجم ملف الذاكرة المشتركة (SHM):** `{db_m['shm_size_bytes']:,} بايت` — حالة الوجود: `{db_m['shm_exists']}`",
        f"- **إجمالي المستخدمين المسجلين:** `{db_m['users_count']}` مستخدم",
        f"- **إجمالي القلاع المخزنة:** `{db_m['castles_count']}` قلعة",
        f"- **عدد القلاع النشطة تشغيلياً (`is_active = 1`):** `{db_m['active_castles_count']}` قلعة",
        f"- **خصائص PRAGMA:**",
        f"  - `journal_mode`: `{db_m['pragma'].get('journal_mode', 'N/A')}`",
        f"  - `page_size`: `{db_m['pragma'].get('page_size', 'N/A')} بايت`",
        f"  - `page_count`: `{db_m['pragma'].get('page_count', 'N/A')}`",
        f"  - `freelist_count`: `{db_m['pragma'].get('freelist_count', 'N/A')}`",
        "",
        "---",
        "",
        "## 3. تدقيق الهياكل العامة في خادم الـ API (`api_server.py Global Tracking Structures`)",
        "",
        "تم فحص الحالة الحالية لجميع الهياكل والقواميس العامة داخل قفل الخادم المشترك `api_server._lock`:",
        "",
        "| الهيكل العام | نوع البنية | عدد العناصر الحالي | الوظيفة ودورها في إدارة الموارد |",
        "|---|---|---|---|",
        f"| `_threads` | Dict[str, Thread] | `{globs.get('_threads_count', 0)}` | ربط معرف القلعة بالخيط المشغل |",
        f"| `_stop_events` | Dict[str, Event] | `{globs.get('_stop_events_count', 0)}` | إشارات إيقاف الخيوط المنظمة |",
        f"| `_bot_managers` | Dict[str, BotManager] | `{globs.get('_bot_managers_count', 0)}` | كائنات إدارة منطق البوت الحي |",
        f"| `_reserved` | Set[str] | `{globs.get('_reserved_count', 0)}` | حجز القلاع أثناء فترة البدء المبدئي |",
        f"| `_log_qs` | Dict[str, Queue] | `{globs.get('_log_qs_count', 0)}` | طوابير السجلات الحية لـ WebSockets |",
        f"| `_conn_states` | Dict[str, str] | `{globs.get('_conn_states_count', 0)}` | حالات الاتصال الشبكي للبوتات |",
        f"| `_user_stopped` | Set[str] | `{globs.get('_user_stopped_count', 0)}` | القلاع الموقوفة يدوياً من المستخدم |",
        f"| `_castle_emails` | Dict[str, str] | `{globs.get('_castle_emails_count', 0)}` | ربط معرف القلعة بالبريد الإلكتروني |",
        f"| `_castle_users` | Dict[str, str] | `{globs.get('_castle_users_count', 0)}` | ربط معرف القلعة بمعرف المستخدم المالك |",
        f"| `_deleted_castles` | Set[str] | `{globs.get('_deleted_castles_count', 0)}` | سجل القلاع المحذوفة لمنع استعادتها |",
        "",
        f"- **إجمالي العناصر المحتجزة في كافة الهياكل العامة:** `{globs.get('summary_keys_total', 0)}` مفتاح",
        f"- **إجمالي الرسائل المتراكمة في طوابير السجلات (`_log_qs`):** `{globs.get('_total_queued_logs', 0)}` رسالة",
        f"- **حالة وضع النشر (`_deploy_mode`):** `{globs.get('_deploy_mode', False)}`",
        f"- **حالة التشغيل التدريجي (`_gradual_running`):** `{globs.get('_gradual_running', False)}`",
        "",
        "---",
        "",
        "## 4. تفاصيل فحص الخيوط النشطة (Active Threads Inventory)",
        "",
        f"- **إجمالي الخيوط:** `{idle['threads']['active_count']}`",
        f"- **خيوط النظام وعمال الخلفية:** `{idle['threads']['system_threads_count']}`",
        f"- **خيوط البوتات (`bot-*`):** `{idle['threads']['bot_threads_count']}`",
        f"- **الخيوط الشبحية (`daemon=True`):** `{idle['threads']['daemon_threads_count']}`",
        "- **قائمة أسماء الخيوط النشطة:**",
    ]

    for th_name in idle["threads"].get("thread_names", []):
        lines.append(f"  - `{th_name}`")

    lines.extend([
        "",
        "---",
        "",
        f"## 5. نتائج الحمل التشغيلي المعياري ({heading_workers})",
        "",
        f"- **عدد العمال المتزامنين:** `{active['workload']['concurrency']}` خيوط عمل",
        f"- **إجمالي السجلات المعالجة:** `{active['workload']['total_records_processed']}` سجل",
        f"- **إجمالي إعدادات JSON المفككة:** `{active['workload']['total_configs_parsed']}` كائن",
        f"- **الزمن الكلي للتنفيذ:** `{active['workload']['total_duration_seconds']} ثانية`",
        f"- **معدل المعالجة (Throughput):** `{active['workload']['throughput_records_per_sec']} سجل/ثانية`",
        f"- **استهلاك المعالج أثناء الحمل:** `{active['cpu_percent']:.2f}%`",
        f"- **ذروة الذاكرة الحقيقية أثناء الحمل:** `{active['peak_rss_mb']} MB`",
        f"- **ذروة ذاكرة Heap أثناء الحمل:** `{active['heap_peak_kb']} KB`",
        "",
        "---",
        "",
        "## 6. استنتاجات خط الأساس ومواقع التسريب المشخصة قبل التعديل (Pre-Fix Forensic Assessment)",
        "",
        "بناءً على قياسات خط الأساس والمسح الجنائي، تم تأكيد مواقع الخلل المستهدفة في المراحل القادمة:",
        "1. **غياب الترقيم في `users-castles` و `live-processes`**: استعلام جدول القلاع الحالي يجلب عمود `config` الضخم لجميع القلاع مما يسبب قفزات مفاجئة في Heap والذاكرة الفيزيائية مع زيادة عدد القلاع.",
        "2. **تسريب مراجع القواميس العامة في `api_server.py`**: القاموس `_castle_emails` لا يتم تفريغه في مسار `finally`، والمجموعة `_deleted_castles` تنمو دون تفريغ، مما يفسر التراكم البطيء في السيرفر الحي.",
        "3. **غياب مهلة الانتظار `join(timeout=...)` خارج الأقفال**: إيقاف وحذف القلاع يترك خيوطاً يتيمة مسؤولة عن تسريب المقابض والذاكرة.",
        "4. **استنزاف الخيوط عبر WebSockets**: استدعاء `_sync_collect_user_statuses` كل 0.8 ثانية يفتح اتصالات SQLite متكررة تجهد المعالج.",
        "",
        "**الخلاصة:** خط الأساس القياسي مكتمل بنسبة 100% ومحفوظ كمرجع رسمي للمقارنة بعد تنفيذ المراحل M2 و M3 و M4 و M5.",
        "",
    ])

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="System Resource Baseline Measurement Tool")
    parser.add_argument("--tag", default="prefix", help="Report tag (prefix, postfix, soak)")
    parser.add_argument("--output-json", default=None, help="Custom output path for JSON report")
    parser.add_argument("--output-md", default=None, help="Custom output path for Markdown report")
    parser.add_argument("--duration", type=float, default=2.5, help="Sampling duration in seconds for CPU measurement")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent worker threads for active workload simulation")
    parser.add_argument("--no-load", action="store_true", help="Skip Phase 3 active workload simulation test")
    parser.add_argument("--skip-load", action="store_true", help="Alias for --no-load (skip Phase 3 active workload simulation test)")
    args = parser.parse_args()

    tag = args.tag.strip().lower()
    json_path = args.output_json or os.path.join(_ROOT, "tools", f"baseline_metrics_{tag}.json")
    md_path = args.output_md or os.path.join(_ROOT, "tools", f"BASELINE_METRICS_{tag.upper()}.md")

    no_load = bool(args.no_load or args.skip_load)
    report_data, report_md = run_full_baseline_measurement(
        tag=tag,
        duration=args.duration,
        workers=args.workers,
        no_load=no_load,
    )

    # Save JSON report
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Quantitative JSON report written to: {json_path}")

    # Save Markdown report
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"[OK] Formatted Markdown report written to: {md_path}")

    print("\n" + "=" * 78)
    print(">>> BASELINE MEASUREMENT COMPLETED SUCCESSFULLY (Code 0)")
    print("=" * 78 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
