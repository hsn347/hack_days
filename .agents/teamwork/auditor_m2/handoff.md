# Forensic Audit Report: Milestone 2 — Concurrency Safety & Security Hardening

**Work Product**: Milestone 2 (`core/database.py`, `api_server.py`, `tools/verify_m2_security.py`, `tools/stress_m2_concurrency.py`)  
**Profile**: General Project  
**Integrity Mode**: Development (also compliant with Demo & Benchmark standards)  
**Verdict**: **CLEAN**

---

## 1. Observation

### 1.1 Source Code Inspection (`core/database.py`)
- **Version Column Migration (`core/database.py:129`, `247`, `263`)**:
  - Line 129: `version INTEGER DEFAULT 1` added to `CREATE TABLE IF NOT EXISTS castle_states`.
  - Line 247: `"version": "INTEGER DEFAULT 1"` added to schema evolution dictionary `new_cols`.
  - Line 263: `UPDATE castle_states SET version = 1 WHERE version IS NULL;` ensures retroactive data consistency.
- **Genuine OCC Implementation (`core/database.py:1163-1269`)**:
  - Class `OCCResult(dict)` (`lines 1163-1167`):
    ```python
    class OCCResult(dict):
        def __bool__(self) -> bool:
            return bool(self.get("success", False))
    ```
    Preserves complete backward compatibility for legacy callers checking `if update_castle_config(...):`.
  - Function `update_castle_config` (`lines 1169-1269`):
    - Line 1198: Opens atomic transaction with `conn.execute("BEGIN IMMEDIATE")` to acquire write lock immediately and prevent read-modify-write race conditions.
    - Lines 1201-1218: Reads current `config` and `current_version = int(row_dict.get("version") or 1)`.
    - Lines 1220-1230: Genuine OCC check:
      ```python
      if expected_version is not None:
          if current_version != int(expected_version):
              conn.rollback()
              return OCCResult({
                  "success": False,
                  "conflict": True,
                  "current_version": current_version,
                  "expected_version": int(expected_version),
                  "error": f"Concurrency conflict: expected version {expected_version}, but current version is {current_version}"
              })
      ```
    - Lines 1243-1258: Atomically increments version: `new_version = current_version + 1`, writes `config_json`, `new_version`, and commits with `conn.commit()`.

### 1.2 Source Code Inspection (`api_server.py`)
- **OCC Endpoints (`api_server.py:1221-1282`)**:
  - `PUT /api/castles/{castle_id}` and `PUT /api/castles/{castle_id}/config` accept `req.version`.
  - When `res.get("conflict")` is True, they explicitly raise `HTTPException(status_code=409, detail=f"Conflict: Castle config has been modified concurrently. Current version is {res.get('current_version')}")`.
- **P0 Fix 1: Plaintext Password Leakage (`api_server.py:2862-2879`)**:
  - `GET /api/local/castles/{identifier}` requires `current_user: Dict[str, Any] = Depends(get_current_user)`.
  - Line 2870-2871: `c.pop("password", None)` and `c.pop("raw_json", None)` unconditionally purge sensitive credentials.
  - Line 2875-2876: Blocks cross-user access with `403 Forbidden` if caller UID does not match castle owner UID and caller is not admin.
- **P0 Fix 2: BOLA in Live Castle Data (`api_server.py:2881-2902`)**:
  - `GET /api/castle-data/{email}` validates that `target_email == caller_email` OR `owns_castle_email` (checked against `db.get_user_castles(caller_uid)`).
  - Unauthorized callers receive `403 Forbidden`.
- **P0 Fix 3: Bot Start Email Spoofing (`api_server.py:2679-2704`)**:
  - `POST /api/bot/start` extracts `c_info = db.get_castle_by_id(req.castle_id, None if is_admin else caller_uid)`.
  - Line 2702-2703: `if c_info.get("email"): req.email = c_info["email"]` enforces authoritative database email, discarding client-provided spoofed parameters.
- **P0 Fix 4: Protection of 10 Sensitive Internal Routes (`api_server.py:620-659`)**:
  - `verify_internal_access` decorator attached via `dependencies=[Depends(verify_internal_access)]` to:
    1. `/api/internal/save-running-state` (`line 2147`)
    2. `/api/internal/debug-state` (`line 2227`)
    3. `/api/internal/deploy-lock` (`line 2241`)
    4. `/api/internal/deploy-unlock` (`line 2253`)
    5. `/api/internal/resume-all-from-db` (`line 2265`)
    6. `/api/internal/gradual-start` (`line 2443`)
    7. `/api/internal/stop-all` (`line 2483`)
    8. `/api/internal/cancel-start-queue` (`line 2535`)
    9. `/api/internal/restart-all` (`line 2561`)
    10. `/api/internal/direct-start` (`line 2662`)
    11. `/api/bot/conn-state` (`line 2842`)
  - Validates `X-Internal-Token == INTERNAL_API_SECRET`, or direct loopback host (`127.0.0.1`, `::1`) with no external `X-Real-IP`, or Bearer admin credentials.

### 1.3 Test Suite Integrity Inspection (`tools/verify_m2_security.py` & `tools/stress_m2_concurrency.py`)
- Test scripts use real `tempfile.mkdtemp` isolated databases, initialize genuine SQLite tables via `db.init_db`, and communicate via FastAPI `TestClient(app)`.
- No mock bypasses, dummy returns, or pre-calculated static strings.
- Multi-threaded tests use `threading.Barrier` and `threading.Thread` to generate real lock contention.

### 1.4 Raw Empirical Execution Results
- `python tools/verify_m2_security.py`:
  ```
  Ran 14 tests in 2.041s
  OK
  ```
- `python tools/stress_m2_concurrency.py`:
  ```
  [STRESS 1] 20 Threads Contention Results:
    - Successes: 1 / 20, Conflicts: 19 / 20, Exceptions: 0
  [STRESS 2] 50 Sequential Updates Results:
    - Version stepped monotonically: 1 -> 51, all 50 keys intact
  [STRESS 3] Backward Compatibility:
    - bool(res) is True, legacy calls supported
  [STRESS 4] HTTP Endpoint Concurrency Results:
    - 1 HTTP 200, 9 HTTP 409 Conflict
  Ran 4 tests in 1.469s
  OK
  ```
- `python tests/run_all_tests.py`:
  ```
  OVERALL SUITE TOTALS: Total: 30 | Pass: 30 | Fail: 0 | Pass: 100.0%
  Total Duration: 4.02 seconds
  >>> ALL TESTS PASSED SUCCESSFULLY! Ready to publish TEST_READY.md.
  ```

---

## 2. Logic Chain

1. **Phase 1 Forensic Analysis**:
   - Absence of hardcoded test outputs: Inspected `tools/verify_m2_security.py` and `tools/stress_m2_concurrency.py`. All assertions evaluate real dynamic HTTP response statuses (`401`, `403`, `200`, `409`) and real SQLite database contents.
   - Absence of facade implementations: `update_castle_config` performs authentic SQL `BEGIN IMMEDIATE`, `SELECT`, version comparison, `UPDATE`, and `COMMIT`/`ROLLBACK`.
   - Absence of fabricated verification outputs: All test executions were performed live during the audit turn; raw outputs match runtime logs.
2. **Phase 2 Behavioral Verification**:
   - Both unit tests and stress contention tests passed 100% under isolated hermetic conditions.
   - 20-thread and 10-thread race condition tests proved that OCC successfully eliminates lost updates and enforces single-winner atomic increments.
   - 4 P0 security patches successfully block unauthenticated access, BOLA/IDOR, parameter spoofing, and external loopback spoofing.
3. **Phase 3 Mode-Specific Flagging**:
   - `ORIGINAL_REQUEST.md` specifies `Integrity mode: development`.
   - Under Development Mode (and even under Demo and Benchmark modes), zero integrity violations exist. The implementation is authentic, rigorous, and free of cheating or bypasses.

---

## 3. Caveats

- In `verify_internal_access`, requests originating from behind reverse proxies rely on `X-Real-IP` to identify external clients. In local development / test environments without reverse proxies, loopback connections from `127.0.0.1` are trusted as expected.
- No remote server uploads, deployment, or production database touches were performed; all work strictly adheres to GEMINI.md Rule 4 and AGENTS_CONSTITUTION.md Rule 13.

---

## 4. Conclusion

**Verdict: CLEAN**

Milestone 2 (Concurrency Safety & Security Hardening) exhibits complete integrity:
- Zero facades, zero hardcoding, zero mock bypasses.
- Authentic Optimistic Concurrency Control (OCC) with `BEGIN IMMEDIATE` and `OCCResult` backward compatibility.
- Comprehensive security hardening across all 4 P0 vulnerabilities.
- Verified test suite executing against real FastAPI `TestClient` and isolated SQLite instances.

---

## 5. Verification Method

To independently reproduce this forensic verification:
1. Run the Milestone 2 security verification suite:
   ```powershell
   python tools/verify_m2_security.py
   ```
   *Expected outcome:* 14 tests run, 0 failures, status `OK`.
2. Run the OCC concurrency stress harness:
   ```powershell
   python tools/stress_m2_concurrency.py
   ```
   *Expected outcome:* 4 tests run (including 20-thread race & 50 sequential updates), 0 failures, status `OK`.
3. Run the full project test suite:
   ```powershell
   python tests/run_all_tests.py
   ```
   *Expected outcome:* 30 tests run, 30 passed (100.0% pass rate).
