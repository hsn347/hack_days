# Worker M2 Dispatch: Concurrency Safety & Security Hardening

- Working Directory: e:\osmanli\.agents\teamwork\worker_m2\
- Authoritative Request: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
- Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
- Project Scope: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
- Approved Remediation Plan: e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md
- Test Suite: `python tests/run_all_tests.py`

## Mandate & Scope of Milestone 2
You are the Security & Concurrency Worker (`teamwork_worker`).
Your exclusive file ownership:
- `api_server.py`
- `core/database.py`

## Concrete Tasks
1. **P0 Security Patch: Plaintext Password Leakage (`api_server.py:2767-2774`)**:
   - In `/api/local/castles/{identifier}`:
     * Add authentication dependency `current_user: dict = Depends(get_current_user)`.
     * Verify that `c["user_id"] == current_user["uid"]` or `current_user.get("role") in ("admin", "merchant_admin")`. Return 403 Forbidden if unauthorized.
     * Ensure `c.pop("password", None)` is ALWAYS called so plaintext passwords are never returned.
2. **P0 Security Patch: BOLA/IDOR in `/api/castle-data/{email}` (`api_server.py:2776-2794`)**:
   - Verify that `{email}` belongs to `current_user["uid"]` by checking that the email matches `current_user["email"]` OR exists in `db.get_user_castles(current_user["uid"])`, OR caller has admin role. Return 403 Forbidden if caller does not own the email.
3. **P0 Security Patch: Parameter Spoofing in `/api/bot/start` (`api_server.py:2590-2631`)**:
   - When resolving account email for `_start_bot_internal(req)`:
     * Extract the castle from database `c = db.get_castle_by_id(req.castle_id, caller_uid)`.
     * Override `req.email = c["email"]` from the verified database record instead of trusting caller-supplied `req.email`.
4. **P0 Security Patch: Secure 10 Internal Routes (`api_server.py`)**:
   - Protect routes `/api/internal/*`:
     `/api/internal/stop-all`, `/api/internal/restart-all`, `/api/internal/direct-start`,
     `/api/internal/deploy-lock`, `/api/internal/deploy-unlock`, `/api/internal/gradual-start`,
     `/api/internal/cancel-start-queue`, `/api/internal/save-running-state`,
     `/api/internal/debug-state`, `/api/bot/conn-state`.
   - Add verification: require admin role (`Depends(get_admin_user)`) OR valid internal token `X-Internal-Token` or loopback verification.
5. **Concurrency Safety & OCC (Optimistic Concurrency Control)**:
   - In `core/database.py`:
     * Add `version INTEGER DEFAULT 1` column to `castle_states` table in migration/init if not present.
     * In `update_castle_config(castle_id, config_dict, expected_version=None, db_path=None)`:
       Use `BEGIN IMMEDIATE` transaction to eliminate race conditions.
       If `expected_version` is provided, verify `current_version == expected_version`. If mismatch, raise/return concurrency conflict (OCC).
       Increment `version = version + 1` upon update.
       Return `{ "success": True, "version": new_version }`.
6. **Verification**:
   - Execute `python tests/run_all_tests.py` and ensure all tests pass (including Tier 1 security & Tier 3 OCC tests).
   - Write verification script in `tools/verify_m2_security.py` verifying each P0 fix and OCC behavior.

## Mandatory Rules & Integrity
- DO NOT CHEAT. All implementations must be genuine.
- Strictly local workspace (`e:\osmanli`). NO server uploads or remote deployments.
- Deliver detailed handoff in `e:\osmanli\.agents\teamwork\worker_m2\handoff.md`.


## 2026-11-02T17:44:47Z
[Message] timestamp=2026-11-02T17:44:47Z sender=44132d7d-07d0-4709-a292-a8e4727a82fd priority=MESSAGE_PRIORITY_HIGH content=You are Worker M2: Security & Concurrency Worker.
Your working directory is: e:\osmanli\.agents\teamwork\worker_m2\
Authoritative user request file: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
Project Scope: e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md
Approved Remediation Plan: e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md
Dispatch instructions: e:\osmanli\.agents\teamwork\worker_m2\DISPATCH.md
