## 2026-11-09T13:45:51Z
You are Agent 19: Concurrency & Deep-Merge Stress Tester.
Your working directory is: e:\osmanli\.agents\teamwork\agent19_concurrency_stress\

You MUST read the following files before starting:
1. ORIGINAL_REQUEST.md: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
2. Architecture Report: e:\osmanli\.agents\teamwork\LIVE_STATE_MEMORY_ARCHITECTURE_REPORT.md
3. Deep Merge Specification: e:\osmanli\.agents\teamwork\agent8_deep_merge_prep\DEEP_MERGE_SPEC.md
4. `core/live_memory.py` and `game_client.py`

Task:
Perform intensive stress testing on concurrency and the deep-merge engine:
1. Flood Test:
   - Spawn multiple threads or async coroutines injecting thousands of packets simultaneously into `LiveMemoryEngine`.
   - Concurrently have multiple reader threads/coroutines iterating over `cityCtrl.blist`, `heroCtrl.heroes`, and reading `conn.init_data`.
2. Race Condition & Duplication Audit:
   - Check if any `RuntimeError` (e.g. dictionary or list changed size during iteration) occurs.
   - Assert that list lengths match mathematical invariants (no duplicate entities created, no random list shrinkage).
   - Assert Copy-on-Write reference safety.
3. Memory and Performance Telemetry:
   - Measure time taken to process 1,000 packets and memory footprint stability before and after the flood.
4. Execute the stress test and record verified evidence in `e:\osmanli\.agents\teamwork\agent19_concurrency_stress\handoff.md`.
Send a message when finished referencing your handoff.
