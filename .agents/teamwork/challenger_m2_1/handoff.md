# Empirical Challenger Handoff Report: Milestone 2 — Security Hardening & Concurrency

**Verdict:** **`APPROVE`**  
**Role:** Empirical Challenger (Instance 1 — Security & Auth Challenger)  
**Working Directory:** `e:\osmanli\.agents\teamwork\challenger_m2_1\`  
**Date:** 2026-11-02  

---

## 1. Observation

1. **Independent Adversarial Attack Harness (`tools/stress_m2_security.py`)**:
   - Created a dedicated 19-test adversarial stress harness that directly tests perimeter boundaries, bypass vectors, casing/whitespace manipulation, IDOR/BOLA attacks, parameter spoofing, and high-concurrency race conditions.
   - Command:
     ```powershell
     python tools/stress_m2_security.py
     ```
   - Result:
     ```
     Ran 19 tests in 3.191s
     OK
     ```
     - `test_local_castle_unauthenticated_rejected_401`: Verifies unauthenticated access to `/api/local/castles/{id}` returns `401 Unauthorized`.
     - `test_local_castle_cross_user_bola_rejected_403`: Verifies User B requesting User A's castle returns `403 Forbidden`.
     - `test_local_castle_owner_access_strips_password_and_raw_json`: Verifies 200 OK for owner, with strict assertion that `password` string, `"password"` key, and `"raw_json"` key are completely absent from the response body.
     - `test_local_castle_admin_access_also_strips_password`: Verifies super admin receives 200 OK without password leakage.
     - `test_castle_data_cross_user_bola_rejected_403`: Verifies cross-account retrieval of live castle data returns `403 Forbidden`.
     - `test_castle_data_casing_and_whitespace_spoofing_rejected_403`: Verifies that uppercase (`VICTIM_CASTLE_1@DOMAIN.COM`) and whitespace-padded URL queries (`%20victim_castle_1@domain.com%20`) are normalized and strictly rejected with `403 Forbidden`.
     - `test_castle_data_owner_allowed_past_auth`: Verifies owner accessing their own castle data passes 403 security boundary.
     - `test_bot_start_overrides_spoofed_email_with_db_email`: Verifies that an attacker sending their own `castle_id` with `email: "victim_castle_1@domain.com"` in payload has `req.email` forcefully overwritten with their verified SQLite email (`attacker_castle_1@evilcorp.org`) before `_start_bot_internal` is called.
     - `test_bot_start_rejects_cross_user_castle_start`: Verifies cross-user castle start attempts return `403 Forbidden` (UID mismatch) or `404 Not Found` (castle not owned).
     - `test_all_10_internal_endpoints_block_external_ip_without_credentials`: Iterates over all 10 internal endpoints (`/api/internal/stop-all`, `/api/internal/restart-all`, `/api/internal/direct-start`, `/api/internal/deploy-lock`, `/api/internal/deploy-unlock`, `/api/internal/gradual-start`, `/api/internal/cancel-start-queue`, `/api/internal/save-running-state`, `/api/internal/debug-state`, `/api/bot/conn-state`) with `X-Real-IP: 203.0.113.195` and verifies every single endpoint returns `403 Forbidden`.
     - `test_internal_endpoints_block_fake_header_forgery`: Verifies forgery attempt with remote host and forged loopback header returns `403 Forbidden`.
     - `test_internal_endpoints_block_invalid_internal_token`: Verifies incorrect `X-Internal-Token` returns `403 Forbidden`.
     - `test_internal_endpoints_accept_valid_internal_token`: Verifies valid `X-Internal-Token` grants access with `200 OK`.
     - `test_internal_endpoints_reject_regular_user_bearer_token`: Verifies user with role `user` calling internal endpoints with Bearer token is rejected with `403 Forbidden`.
     - `test_internal_endpoints_accept_admin_bearer_token`: Verifies admin Bearer token from external IP is authorized with `200 OK`.
     - `test_occ_atomic_burst_20_threads_exact_single_winner`: Fires 20 threads simultaneously using `threading.Barrier` targeting the same castle with `expected_version=1`. Verifies exactly 1 thread succeeds (version -> 2), exactly 19 threads receive OCC conflict (`{"conflict": True}`), and no updates are lost.
     - `test_occ_http_conflict_returns_409_status_code`: Verifies HTTP endpoint `PUT /api/castles/{id}` with mismatched version returns `409 Conflict`.

2. **Worker M2 Verification Suite (`tools/verify_m2_security.py`)**:
   - Command:
     ```powershell
     python tools/verify_m2_security.py
     ```
   - Result:
     ```
     Ran 14 tests in 1.853s
     OK
     ```

3. **Unified 4-Tier Test Suite (`tests/run_all_tests.py`)**:
   - Command:
     ```powershell
     python tests/run_all_tests.py
     ```
   - Result:
     ```
     OVERALL SUITE TOTALS: Total: 30 | Pass: 30 | Fail: 0 | Pass: 100.0%
     Total Duration: 3.51 seconds
     >>> ALL TESTS PASSED SUCCESSFULLY! Ready to publish TEST_READY.md.
     ```

---

## 2. Logic Chain

1. **Password Sanitization & BOLA on `/api/local/castles/{id}`**:
   - In `api_server.py:2862-2878`, adding `current_user: Dict[str, Any] = Depends(get_current_user)` mandates authentication (401 for unauthenticated).
   - Calling `c.pop("password", None)` and `c.pop("raw_json", None)` occurs immediately after fetching the record. Because the dictionary is purged before returning, passwords cannot leak.
   - Enforcing `str(c.get("user_id", "")).strip() == str(caller_uid).strip()` or admin role blocks any non-owner access with `403 Forbidden`.
   - Empirically proven: 401 on unauthenticated, 403 on BOLA attack, 200 on owner access with zero password or raw_json in raw response payload.

2. **BOLA/IDOR Elimination on `/api/castle-data/{email}`**:
   - In `api_server.py:2881-2902`, the handler normalizes emails with `.strip().lower()` and checks whether the target email matches `caller_email` or belongs to any castle in `db.get_user_castles(caller_uid)`.
   - Any mismatch causes an immediate `403 Forbidden` response.
   - Empirically proven: cross-account attempts, uppercase attempts, and whitespace-padded attempts are all blocked with 403, while legitimate castle owners pass through.

3. **Parameter Spoofing Elimination on `/api/bot/start`**:
   - In `api_server.py:2696-2704`, the server retrieves `c_info = db.get_castle_by_id(req.castle_id, None if is_admin else caller_uid)`.
   - If `c_info.get("email")` exists, `req.email = c_info["email"]` unconditionally overwrites whatever email the client supplied in the JSON payload.
   - Empirically proven: when an attacker passes `email: "victim_castle_1@domain.com"` for their owned castle, the backend intercepts and replaces the email with the authentic DB email `attacker_castle_1@evilcorp.org` before bot execution.

4. **Internal Route Protection**:
   - In `api_server.py:620-658`, `verify_internal_access` acts as a multi-tier gate:
     1. Accepts if `x-internal-token == INTERNAL_API_SECRET`.
     2. Accepts if connection is direct loopback (`127.0.0.1`, `::1`, `localhost`, `testclient`) AND untrusted proxy header (`x-real-ip`) is not set to an external IP.
     3. Accepts if Bearer token belongs to an admin or merchant admin.
     4. Otherwise rejects with `403 Forbidden`.
   - Empirically proven: all 10 internal endpoints reject external access without credentials (403), reject invalid token (403), reject regular user tokens (403), and allow valid internal tokens or admin tokens (200).

5. **Optimistic Concurrency Control (OCC)**:
   - In `core/database.py:1160-1270`, `update_castle_config` acquires a write lock via `BEGIN IMMEDIATE`.
   - If `expected_version` is specified, it compares against `current_version`. On mismatch, it rolls back and returns an OCC conflict.
   - On match or initial write, `new_version = current_version + 1` is written atomically.
   - In `api_server.py`, `PUT /api/castles/{id}` translates OCC conflict into an HTTP `409 Conflict`.
   - Empirically proven: 20 concurrent threads attempting to update version 1 resulted in exactly 1 successful update (version 2) and 19 conflicts. Zero lost updates.

---

## 3. Caveats

- All empirical tests were conducted 100% locally in `e:\osmanli` using hermetic isolated SQLite databases in temporary directories per `AGENTS_CONSTITUTION.md` and `GEMINI.md`. No external or remote servers were touched.
- Live game server connections (e.g. within `/api/castle-data/{email}`) return simulated errors (such as 404/503 from session manager) during local testing due to the absence of active upstream game socket connections; however, the security layer preceding game client invocation was empirically proven to enforce strict 403 access control.

---

## 4. Conclusion

**Verdict: `APPROVE`**

Milestone 2 patches satisfy all security requirements without regressions:
1. `/api/local/castles/{id}` is fully secured against unauthenticated access (401), BOLA/IDOR (403), and plaintext password/raw_json leaks.
2. `/api/castle-data/{email}` completely blocks cross-user data scraping (403) and resists casing/whitespace evasion.
3. `/api/bot/start` is completely immune to email parameter spoofing and binds strictly to the authentic SQLite record.
4. All 10 internal endpoints are protected by `verify_internal_access`, repelling external unauthenticated requests while permitting valid internal tokens and admin credentials.
5. Optimistic Concurrency Control (OCC) reliably detects and prevents lost updates under heavy concurrent contention (20 parallel threads), returning HTTP 409 Conflict appropriately.
6. The entire test suite achieved a 100% pass rate:
   - `tools/stress_m2_security.py`: 19/19 PASS
   - `tools/verify_m2_security.py`: 14/14 PASS
   - `tests/run_all_tests.py`: 30/30 PASS

Milestone 2 is formally approved to proceed to Milestone 3.

---

## 5. Verification Method

To independently reproduce the Challenger's findings:
1. Run the empirical attack and stress suite:
   ```powershell
   python tools/stress_m2_security.py
   ```
   *Expected result:* 19 tests run, 0 failures, status `OK`.
2. Run the worker M2 verification suite:
   ```powershell
   python tools/verify_m2_security.py
   ```
   *Expected result:* 14 tests run, 0 failures, status `OK`.
3. Run the complete 4-Tier unified test runner:
   ```powershell
   python tests/run_all_tests.py
   ```
   *Expected result:* 30 tests run, 30 passed (100.0% pass rate).
