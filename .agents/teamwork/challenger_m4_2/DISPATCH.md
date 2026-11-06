# DISPATCH - Challenger M4 (Instance 2 - Logout Sanitization Challenger)

## Mission
Empirically stress-test the logout and account switch sanitization protocol implemented in Milestone 4 in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md`
- `e:\osmanli\.agents\teamwork\worker_m4\handoff.md`

## Challenge Tasks & Methodology
Write and run an empirical attack/sanitization test script in Node.js or Python (e.g. `tools/stress_m4_sanitization.mjs`):
1. Populate mock `localStorage` and `sessionStorage` with:
   - Multiple user castle caches: `empire_castles_cache_user1`, `empire_castles_cache_user2`, `ibra_castles_cache_legacy`
   - Active castle keys: `empire_active_castle_user1`, `ibra_active_castle_legacy`
   - Auth tokens & profile: `empire_auth_profile`, `ibra_auth_profile`, `osmanli_admin_session_token`
   - UI preferences: `osmanli_lang`, `osmanli_theme`
2. Simulate `purgeUserDataOnLogout`:
   - Verify that 100% of sensitive castle and auth tokens are wiped.
   - Verify that non-sensitive UI preferences (`osmanli_lang`, `osmanli_theme`) remain intact.
3. Test account switch:
   - Verify switching from User A to User B leaves zero data from User A.
4. Run project regression test runner `python tests/run_all_tests.py` (Must pass 30/30).

## Verification & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\challenger_m4_2\`
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicit verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.


## 2026-11-02T19:07:39Z
You are Challenger M4 (Instance 2 - Logout Sanitization Challenger).
Your working directory is e:\osmanli\.agents\teamwork\challenger_m4_2\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\challenger_m4_2\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md, and e:\osmanli\.agents\teamwork\worker_m4\handoff.md.
Empirically stress-test the logout and account switch sanitization protocol:
1. Populate mock storage with multi-user castle caches, active castle keys, auth profiles, and preferences.
2. Execute purgeUserDataOnLogout simulation and assert 100% absence of sensitive castle/auth data while preserving theme/lang.
3. Test account switch isolation.
Write and run an empirical test script in tools/ (e.g. tools/stress_m4_sanitization.mjs).
Write handoff.md with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.
