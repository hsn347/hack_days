# Worker M1 (Iteration 2) Dispatch: Challenger 2 Remediation

- Working Directory: e:\osmanli\.agents\teamwork\worker_m1_iter2\
- Authoritative Request: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
- Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
- Gate Failure Feedback: e:\osmanli\.agents\teamwork\orchestrator\GATE_STATUS.md
- Challenger 2 Report: e:\osmanli\.agents\teamwork\challenger_m1_2\handoff.md
- Reviewer 2 Finding: Whitespace tenant domain handling (`if clean_domains:`)

## Concrete Remediation Mandate
1. **Full Async Offload in `api_server.py:ws_user_status`**:
   Currently, only `db.get_user_castles(user_id)` was offloaded to `to_thread`. The subsequent iteration `for c in castles: res[cid] = _get_real_status(cid)` was executing on the main event loop thread, acquiring locks and causing 107ms P95 loop lag under 50 concurrent WebSocket clients.
   **Fix**:
   Implement a synchronous helper function that encapsulates both the database read AND the castle status iteration, and offload the entire function to thread pool:
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
   ```
   Inside `ws_user_status`:
   ```python
   curr_data = await asyncio.to_thread(_sync_collect_user_statuses, user_id)
   ```
2. **Hardening in `core/database.py:get_all_users_with_castles`**:
   In lines ~1715-1718, change:
   `if clean_domains:`
   instead of `if tenant_domains and len(tenant_domains) > 0:` so that whitespace-only lists like `['', '   ']` do not generate invalid `IN ()` SQL syntax.
3. **Verification**:
   Execute `python tools/benchmark_m1_stress_suite.py` and verify:
   - WS Event Loop P95 lag drops to ~2.0 ms (Zero Blocking).
   - `python tools/verify_m1_backend.py` passes 5/5.
   - `python tests/run_all_tests.py` passes 29/29.

Deliver handoff in `e:\osmanli\.agents\teamwork\worker_m1_iter2\handoff.md`.

