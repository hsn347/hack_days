# Dispatch Directives: Challenger M7 (Instance 2)

## 2026-11-02T20:35:19Z
You are Challenger M7 (Instance 2), assigned to Milestone 7 Merchant Isolation & Security Stress Test.

Working Directory: `e:\osmanli\.agents\teamwork\challenger_m7_2\`
Dispatch Directive: `e:\osmanli\.agents\teamwork\challenger_m7_2\DISPATCH.md`
Context Files:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md`
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m7\handoff.md`

🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5):
Create your technical report artifact (.md) in your directory BEFORE running commands.

Objective:
Author an empirical stress test (e.g. `tools/stress_m7_merchant_isolation.py`) verifying:
- Strict merchant admin isolation in `api_server.py:get_admin_user_castles`:
  * Global admin can access user castles.
  * Merchant admin can access users under their assigned domain.
  * Merchant admin is blocked (403 Forbidden) from accessing users outside their domain.
  * Unauthenticated requests are rejected (401).
- Resource lifecycle cleanup on component unmount.

Verify:
- `python tools/verify_m7_ux_lifecycle.py`
- `powershell -Command "Set-Location dashboard; npm run build"`
- `python tests/run_all_tests.py`

Deliver `handoff.md` with explicit verdict (APPROVE / REQUEST_CHANGES) and send completion message to orchestrator (`44132d7d-07d0-4709-a292-a8e4727a82fd`).
