# Pre-Execution Technical Report: Milestone 1 Iteration 2 Challenger Verification

## 1. Diagnosis & Reason (تشخيص السبب ولماذا هذا الإجراء مطلوب)
In Milestone 1 Iteration 1, Challenger 2 identified two empirical issues:
1. Event loop lag under 50 concurrent WebSocket clients reached P95 = 107.78 ms (max > 1000 ms) because `api_server.py:ws_user_status` executed castle status collection loops synchronously on the main thread.
2. Whitespace-only tenant domain inputs in `core/database.py:get_all_users_with_castles` generated invalid SQL `WHERE ... IN ()`.

Worker M1 Iteration 2 implemented remediation:
- Refactored `ws_user_status` in `api_server.py` to offload the entire status aggregation routine `_sync_collect_user_statuses` via `asyncio.to_thread`.
- Sanitized `tenant_domains` in `core/database.py:get_all_users_with_castles` to ignore empty and whitespace-only entries before assembling the SQL IN-clause.
- Added Tier 2 test `test_t2_whitespace_tenant_domains_boundary` in `tests/test_database_performance.py`.

As Challenger 2 (Iteration 2), our mandate is to independently execute empirical stress harnesses and unit tests to verify if the remediation meets the performance contracts:
- Event loop P95 lag < 5.0 ms under 50 concurrent WebSocket clients.
- Collapsed SQL query count strictly equal to 1.
- Pure SQL execution P50 latency < 9.5 ms.
- 100% passing test suite across all 4 tiers (30/30 tests).

## 2. Logic & Steps (المنطق والخطوات التي سيتم تطبيقها)
1. **Liveness & Persisted Memory Setup**:
   - Update `DISPATCH.md` with incoming dispatch notification.
   - Initialize `BRIEFING.md` and `progress.md` in `e:\osmanli\.agents\teamwork\challenger_m1_2_iter2\`.
2. **Code Inspection**:
   - Inspect `api_server.py` around lines 3060-3100 to verify `_sync_collect_user_statuses` implementation.
   - Inspect `core/database.py` around lines 1710-1730 to verify `clean_domains` sanitation.
   - Inspect `tools/benchmark_m1_stress_suite.py` to ensure it exercises the real `_sync_collect_user_statuses` or imports it directly.
3. **Execution of Stress Benchmark**:
   - Run `python tools/benchmark_m1_stress_suite.py` synchronously.
   - Collect exact latency distributions (P50, P95, Max) for both Pure SQL and Event Loop under 50 concurrent clients.
4. **Execution of Full Test Suite**:
   - Run `python tests/run_all_tests.py` synchronously.
   - Ensure all 30 tests across Tiers 1-4 pass without warnings/failures.
5. **Execution of Backend Verification**:
   - Run `python tools/verify_m1_backend.py`.
6. **Final Evaluation and Handoff**:
   - Produce `handoff.md` with complete evidence chain and definitive verdict.
   - Send final message to Orchestrator.

## 3. Commands to be Executed and Expected Results (الأوامر والنتائج المتوقعة)
1. `python tools/benchmark_m1_stress_suite.py`:
   - Expected: 500 iterations of `get_all_users_with_castles` with query count = 1, Pure SQL P50 < 9.5 ms.
   - Expected: 50 concurrent WS clients benchmark with Event Loop P95 lag < 5.0 ms.
2. `python tests/run_all_tests.py`:
   - Expected: 30/30 tests passing (100% pass rate).
3. `python tools/verify_m1_backend.py`:
   - Expected: 5/5 verification checks pass.
