# DISPATCH - Challenger M2 (Instance 1 - Security & Auth Challenger)

## Mission
Empirically stress-test and verify the security hardening implemented in Milestone 2 in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files before starting:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m2\technical_report_m2.md`
- `e:\osmanli\.agents\teamwork\worker_m2\handoff.md`

## Challenge Tasks & Methodology
Write and run an empirical attack harness (in an isolated script, e.g. `tools/stress_m2_security.py`) using FastAPI `TestClient` or HTTP calls to adversarially test:
1. `/api/local/castles/{id}`:
   - Attack with no token -> must return 401.
   - Attack with valid non-owner user token -> must return 403.
   - Request with owner token -> must succeed with 200, but `password` and `raw_json` MUST be absent from response body.
2. `/api/castle-data/{email}`:
   - Request with user token for an email not owned by that user -> must return 403.
   - Request with owner user token -> must allow access (or reach upstream game logic).
3. `/api/bot/start`:
   - Send payload with `castle_id` owned by user A, but spoofed `email: "victim@example.com"`.
   - Verify that the backend code overrides `req.email` with the authentic owner's email from SQLite before invoking any downstream bot startup.
4. Internal Endpoints (`/api/internal/*`, `/api/bot/conn-state`):
   - Attack with external IP header (`X-Real-IP: 203.0.113.195`) without auth -> must return 403.
   - Request with `X-Internal-Token` matching secret -> must succeed.
   - Request with Admin Bearer token -> must succeed.

## Verification & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\challenger_m2_1\`
- Run your harness, record exact outputs and metrics.
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicitly state verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.

