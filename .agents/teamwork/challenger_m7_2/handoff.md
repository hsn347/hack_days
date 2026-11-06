# Handoff Report: Challenger M7 (Instance 2) — Empirical Adversarial Stress Test

**Author:** Challenger M7 (Instance 2) (`challenger_m7_2`)  
**Target:** Orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`)  
**Timestamp:** 2026-11-02T20:41:00Z  
**Type:** Hard Handoff (Task Complete)  
**Verdict:** **APPROVE**  

---

## 1. Observation
- **Endpoint Implementation in `api_server.py:1871-1891`:**
  - `get_admin_user_castles(uid: str, admin: Dict[str, Any] = Depends(require_admin))`
  - Line 1874: `target_user = db.get_user(uid)`
  - Line 1875: `_verify_merchant_access_to_user(admin, target_user)`
  - Verbatim check in `_verify_merchant_access_to_user` (`api_server.py:1685-1693`):
    ```python
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if admin.get("is_merchant_admin"):
        tenant_domains = [clean_domain(d) for d in admin.get("merchant_tenant", {}).get("domains", [])]
        user_domain = clean_domain(target_user.get("tenant_domain", ""))
        if user_domain not in tenant_domains:
            raise HTTPException(status_code=403, detail="غير مصرح لك بإدارة هذا المستخدم خارج نطاق دومينك")
    ```
- **Limitation of Worker Verification (`tools/verify_m7_ux_lifecycle.py`):**
  - Worker M7's test suite checked `_verify_merchant_access_to_user` solely via static regex matching against source code, without performing runtime HTTP execution.
- **Empirical Stress Test Suite Created (`tools/stress_m7_merchant_isolation.py`):**
  - Authored an adversarial test harness utilizing `fastapi.testclient.TestClient` and hermetic temporary SQLite databases (`tempfile.mkdtemp` + `os.environ["CASTLES_DB_PATH"]`), ensuring zero mutation to production data.
  - Implemented 11 empirical test cases covering 5 security tiers:
    1. `test_01_unauthenticated_request_rejected_401` -> HTTP 401 Unauthorized.
    2. `test_02_regular_user_access_rejected_403` -> HTTP 403 Forbidden ("وصول مرفوض: لا تملك صلاحيات إدارة النظام").
    3. `test_03_merchant_admin_in_domain_access_allowed_200` -> HTTP 200 OK + user castle payload.
    4. `test_04_merchant_admin_in_domain_clean_domain_matching_200` -> HTTP 200 OK for 'www.' prefix variants.
    5. `test_05_merchant_admin_blocked_from_main_tenant_user_403` -> HTTP 403 Forbidden ("غير مصرح لك بإدارة هذا المستخدم خارج نطاق دومينك").
    6. `test_06_merchant_admin_blocked_from_default_tenant_user_403` -> HTTP 403 Forbidden.
    7. `test_07_merchant_admin_blocked_from_other_merchant_user_403` -> HTTP 403 Forbidden.
    8. `test_08_global_super_admin_universal_access_all_domains_200` -> HTTP 200 OK across all domain users.
    9. `test_09_nonexistent_user_returns_404` -> HTTP 404 Not Found.
    10. `test_10_resource_cleanup_action_modal_listener` -> Event listener removal in `ActionConfirmModal.tsx`.
    11. `test_11_resource_cleanup_live_processes_interval` -> Interval timer cancellation in `AdminLiveProcesses.tsx`.
- **Execution Results:**
  - `python tools/stress_m7_merchant_isolation.py` -> 11/11 (100%) PASS in 2.55s.
  - `python tools/verify_m7_ux_lifecycle.py` -> 22/22 (100%) PASS.
  - `powershell -Command "Set-Location dashboard; npm run build"` -> 0 errors, compiled in 2.17s.
  - `python tests/run_all_tests.py` -> 30/30 (100%) PASS in 4.07s.

---

## 2. Logic Chain
1. **Adversarial Security Boundaries:**
   - When an unauthenticated caller sends a request to `/api/admin/users/{uid}/castles`, FastAPI's dependency injection invokes `require_admin` -> `get_current_user` which halts the request with HTTP 401 Unauthorized before touching the database.
   - When a logged-in regular user without admin or merchant admin privileges invokes the endpoint, `require_admin` detects the absence of `is_super_admin` and `is_merchant_admin` and rejects with HTTP 403 Forbidden.
   - When a legitimate merchant admin (e.g. `nurjan12ddsw2@gmail.com`) invokes the endpoint:
     * Accessing a target user whose `tenant_domain` matches the merchant's domain list (`nurjanbot.online`, `www.nurjanbot.online`) is permitted, returning HTTP 200 OK with the castle list.
     * Attempting to access a user belonging to the main domain (`ibrabot.com`), an empty/default domain, or another merchant domain (`vipbot.net`) triggers `_verify_merchant_access_to_user` which detects domain mismatch and halts execution with HTTP 403 Forbidden.
   - When the global super admin (`ibraboths@gmail.com`) invokes the endpoint, `is_merchant_admin` is False, bypassing domain restrictions and permitting universal master-detail castle inspection across all system accounts (HTTP 200 OK).
   - When querying an invalid or non-existent UID, the endpoint raises HTTP 404 Not Found, preventing null-reference crashes.
2. **Resource Lifecycle & Unmount Cleanup:**
   - `ActionConfirmModal.tsx` registers a window `keydown` listener when opened and cleans it up via `window.removeEventListener('keydown', handleKeyDown)` inside the `useEffect` cleanup return callback.
   - `AdminLiveProcesses.tsx` manages an active auto-refresh polling interval and cleans it up via `clearInterval(timerRef.current)` both on component unmount and when the tab is hidden or deactivated.
3. **Build & Platform Integrity:**
   - TypeScript compilation (`tsc`) and Vite bundling succeed without warnings or errors.
   - The unified 4-Tier test suite passes 30/30 tests with zero regressions.

---

## 3. Caveats
- No caveats. All tests run in isolated hermetic temporary SQLite databases per AGENTS_CONSTITUTION.md Rule 13 and GEMINI.md Rule 4 (zero production database mutation, zero remote deployment).

---

## 4. Conclusion
**Verdict: APPROVE**

Milestone 7 implementation satisfies all security, isolation, UX lifecycle, and cleanup requirements:
- Merchant domain isolation in `api_server.py:get_admin_user_castles` is empirically validated against horizontal privilege escalation (BOLA) and unauthorized cross-domain access.
- Resource cleanup guarantees zero leaking intervals and listeners upon component unmount.
- All test suites (stress, lifecycle, build, and platform) pass with 100% success rate.

---

## 5. Verification Method
The orchestrator and forensic auditor can independently reproduce all results by running:
```bash
# 1. Empirical adversarial stress suite (11/11 PASS)
python tools/stress_m7_merchant_isolation.py

# 2. Milestone 7 UX lifecycle & locale verification (22/22 PASS)
python tools/verify_m7_ux_lifecycle.py

# 3. Production frontend bundle build (0 errors)
powershell -Command "Set-Location dashboard; npm run build"

# 4. Unified platform 4-tier test runner (30/30 PASS)
python tests/run_all_tests.py
```
