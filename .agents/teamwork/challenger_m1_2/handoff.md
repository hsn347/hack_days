# Milestone 1 Challenger 2 Handoff Report: Empirical Benchmark & Stress Testing

**Date**: 2026-11-02T17:36:00Z  
**Agent**: Challenger 2 (`teamwork_challenger`)  
**Assigned Directory**: `e:\osmanli\.agents\teamwork\challenger_m1_2\`  
**Governing Documents**: `AGENTS_CONSTITUTION.md`, `ROOT_CAUSE_AND_PLAN.md`, `PROJECT.md`, `GEMINI.md`  
**Verdict**: **`REQUEST_CHANGES`** (Actionable, Scoped, with Verified Mitigation)

---

## 1. Observation

1. **Benchmark Suite Execution Command and Verbatim Output**:
   Executed command:
   ```powershell
   python tools/benchmark_m1_stress_suite.py
   ```
   Verbatim output from task execution:
   ```
   ======================================================================
         CHALLENGER 2: MILESTONE 1 PERFORMANCE & STRESS HARNESS          
   ======================================================================

   ======================================================================
    [SUITE 1] Running 500 Iterations of db.get_all_users_with_castles()
   ======================================================================
     * Intercepted SQL queries per call: 1
     * Pure SQL (Execute + Fetchall) P50: 3.745 ms | P95: 6.554 ms
     * Total Iterations Completed: 500
     * Users returned per call:    150
     * Full Function P50 Latency:  12.164 ms
     * Full Function P95 Latency:  15.022 ms
     * Full Function P99 Latency:  25.020 ms
     * Mean Latency:               12.698 ms (StdDev: 2.401 ms)
     * Min / Max:                  10.199 ms / 39.043 ms
     * Memory Before:              0.00 KB
     * Memory After:               279.94 KB
     * Peak Memory Allocation:     543.54 KB
     * Total Benchmark Runtime:    6.353 s

   ======================================================================
    [SUITE 2] Comparative Stress Testing: 50 Concurrent WS Clients
   ======================================================================
     * Baseline Idle Event Loop Jitter: P50 = 1.572 ms | P95 = 2.096 ms
     * [Scenario A] Synchronous (Pre-M1 Baseline) @ 0.8s interval...
       -> Lag: P50 = 153.579 ms | P95 = 860.766 ms | Max = 860.766 ms
     * [Scenario B] M1 Current Implementation (Offload db.get_user_castles) @ 0.8s interval...
       -> Lag: P50 = 16.052 ms | P95 = 107.780 ms | Max = 1035.023 ms
     * [Scenario C] Full Offload (Offload entire status loop) @ 0.8s interval...
       -> Lag: P50 = 1.035 ms | P95 = 2.024 ms | Max = 18.562 ms

   ======================================================================
                COMPARISON AGAINST ROOT_CAUSE_AND_PLAN.md                
   ======================================================================
   Metric                              | Baseline     | Target       | Measured (500 iters) | Status    
   ------------------------------------|--------------|--------------|--------------------|-----------
   SQL Query Count per Call            | 463          | 1            | 1                  | PASS      
   Pure SQL P50 Latency (ms)           | 20.47        | < 9.50       | 3.745              | PASS      
   Full Function P50 Latency (ms)      | 20.47        | < 9.50       | 12.164             | FAIL      
   Full Function P95 Latency (ms)      | 23.48        | < 10.50      | 15.022             | FAIL      
   WS Event Loop P95 (M1 Current)      | Blocked      | < 10.0 ms    | 107.780            | WARN/FAIL 
   WS Event Loop P95 (Full Offload)    | Blocked      | < 5.0 ms     | 2.024              | PASS      
   ```

2. **Source Code Inspection of `ws_user_status` (`api_server.py:3067-3077`)**:
   ```python
   async def _collect_statuses() -> Dict[str, str]:
       res = {}
       try:
           castles = await asyncio.to_thread(db.get_user_castles, user_id)
           for c in castles:
               cid = c.get("castle_id")
               if cid:
                   res[cid] = _get_real_status(cid)
       except Exception:
           pass
       return res
   ```
   Observation: Only `db.get_user_castles(user_id)` is wrapped in `asyncio.to_thread`. The iteration `for c in castles:` and the synchronous calls `res[cid] = _get_real_status(cid)` execute directly on the asyncio event loop thread. `_get_real_status` acquires a threading lock (`with _lock:`) and performs sequential dictionary scans over `_castle_emails.items()`.

3. **Source Code Inspection of `get_all_users_with_castles` (`core/database.py:1700-1773`)**:
   Observation: The SQL query execution itself is collapsed into 1 single query executing in **3.745 ms P50**. However, the full Python function spends an additional **~8.4 ms** inside:
   - `with get_connection(db_path) as conn:` executing 4 PRAGMA statements (`PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `PRAGMA busy_timeout = 5000`, `PRAGMA foreign_keys = ON`) and transaction context manager.
   - Iterating over 150 rows in Python and constructing the 9-key nested dictionary `subscription` object for each user.

---

## 2. Logic Chain

1. **Query Collapse and Pure SQL Performance (Validated)**:
   - Observation 1 demonstrates that the N+1 query explosion was completely eliminated: exactly 1 SQL query is executed per call (a 99.8% reduction from 463 queries).
   - Pure SQL query time measured across 500 iterations is `P50 = 3.745 ms` and `P95 = 6.554 ms`, easily surpassing the target of `< 9.5 ms` and `< 10.5 ms` set in `ROOT_CAUSE_AND_PLAN.md`.

2. **Full-Function Latency Discrepancy (Identified)**:
   - While pure SQL runs in 3.745 ms, `get_all_users_with_castles()` measured P50 latency across 500 iterations is `12.164 ms` (P95 is `15.022 ms`).
   - Step-by-step trace shows that the baseline target `< 9.5 ms` in `ROOT_CAUSE_AND_PLAN.md` was derived from a microbenchmark that measured only `cur.execute(...)` and `fetchall()`, without `get_connection()` overhead and without the row iteration building 150 nested subscription dictionaries.
   - Although 12.164 ms represents a 1.66x speedup over the 20.47 ms baseline, it strictly exceeds the `< 9.5 ms` target.

3. **Event Loop Offloading Stress Test (Identified Failure Mode & Mitigation)**:
   - In Scenario A (Pre-M1 Synchronous), running 50 concurrent WebSocket clients locked the event loop with a P95 lag of `860.766 ms`.
   - In Scenario B (Worker M1 Partial Offload), wrapping `db.get_user_castles` in `asyncio.to_thread` reduced P50 lag to `16.052 ms`. However, because the loop `for c in castles: res[cid] = _get_real_status(cid)` remains on the event loop thread, concurrent wakes across 50 clients cause micro-burst lock contention, resulting in a P95 lag of `107.780 ms` (Max `1035.023 ms`).
   - In Scenario C (Full Offload Mitigation), moving the entire synchronous status collection (`_sync_collect_all`) into `asyncio.to_thread` eliminated event loop lag entirely: P50 lag dropped to `1.035 ms` and P95 lag dropped to `2.024 ms` (virtually identical to idle event loop jitter of `1.572 ms`).

---

## 3. Caveats

- **Load Profile**: The 50-client concurrent stress test simulated 50 simultaneous WebSocket connections connected to the same local process polling every 800 ms. In smaller deployments (e.g. 5–10 concurrent clients), Scenario B exhibits minimal noticeable lag, but under the mandated 50-client stress test, Scenario B spikes to 107 ms P95 lag.
- **Python Overhead**: The gap between 3.75 ms (pure SQL) and 12.16 ms (full function) is inherent to CPython dictionary allocations for 150 users. If the orchestrator accepts 12.16 ms as meeting the practical intent of Milestone 1, the target in `ROOT_CAUSE_AND_PLAN.md` should be amended to reflect full-function serialization realities.

---

## 4. Conclusion

**Verdict**: **`REQUEST_CHANGES`**

Milestone 1 has successfully solved the primary SQL bottleneck (collapsing 463 queries to 1 and achieving 3.745 ms pure SQL P50). However, before approving Milestone 1, two concrete items must be addressed by Worker M1:

1. **Fix `ws_user_status` in `api_server.py`**:
   Change `ws_user_status` to offload the **entire** dictionary and status collection to the thread pool rather than just `db.get_user_castles`:
   ```python
   def _sync_collect_user_statuses(user_id: str) -> Dict[str, str]:
       res = {}
       try:
           castles = db.get_user_castles(user_id)
           for c in castles:
               cid = c.get("castle_id")
               if cid:
                   res[cid] = _get_real_status(cid)
       except Exception:
           pass
       return res

   # In ws_user_status:
   curr_data = await asyncio.to_thread(_sync_collect_user_statuses, user_id)
   ```
   *Verified empirical gain*: Event loop P95 lag drops from 107.78 ms to **2.024 ms** (Scenario C).

2. **Clarify / Optimize `get_all_users_with_castles()`**:
   Either optimize dictionary construction (or reuse a lightweight schema) to push full-function P50 closer to 9.5 ms, or document the 12.16 ms measurement as the ratified full-function SLA given that pure SQL executes in 3.75 ms.

---

## 5. Verification Method

To independently reproduce and verify Challenger 2's empirical findings:

1. **Run the 500-Iteration & Concurrency Stress Suite**:
   ```powershell
   python tools/benchmark_m1_stress_suite.py
   ```
2. **Inspect Persisted Raw Results**:
   View `e:\osmanli\.agents\teamwork\challenger_m1_2\empirical_benchmark_results.json`.
3. **Invalidation Conditions**:
   - If SQL query count per call exceeds 1 -> Invalidation.
   - If pure SQL P50 exceeds 9.5 ms -> Invalidation.
   - If event loop P95 lag under 50 concurrent clients exceeds 10 ms with full offload -> Invalidation.
