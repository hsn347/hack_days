# DISPATCH - Reviewer M2 (Instance 2 - Adversarial Review)

## Mission
Perform adversarial and edge-case security & concurrency review of Milestone 2 implementations in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files before starting:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m2\technical_report_m2.md`
- `e:\osmanli\.agents\teamwork\worker_m2\handoff.md`

## Review Scope & Adversarial Focus
- Security Bypasses:
  - Can `verify_internal_access` be bypassed via malicious headers (e.g. spoofed `X-Real-IP`, `X-Forwarded-For`, case differences)?
  - Are there any edge cases where unauthenticated requests can reach `/api/local/castles/{identifier}` or receive sensitive data?
  - Can BOLA be triggered in `/api/castle-data/{email}` via case mismatch (e.g. `USER@domain.com` vs `user@domain.com`)?
  - Does `/api/bot/start` properly enforce the database email when `castle_id` is passed as a string vs integer?
- Concurrency & OCC:
  - Does `update_castle_config` handle database exceptions gracefully without leaving locks or dangling transactions?
  - How does `OCCResult` interact with existing callers that expect a boolean (`if res: ...`) vs dictionary (`res["version"]`)?
  - Does the version column migration work seamlessly on existing SQLite databases?

## Verification Tasks
1. Run dedicated verification suite: `python tools/verify_m2_security.py` (Must pass 14/14).
2. Run full 4-tier test suite: `python tests/run_all_tests.py` (Must pass 30/30).
3. Evaluate edge cases and adversarial scenarios.

## Working Directory & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\reviewer_m2_2\`
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicitly state verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.

## 2026-11-02T18:05:52Z
[Message] timestamp=2026-11-02T18:05:52Z sender=44132d7d-07d0-4709-a292-a8e4727a82fd priority=MESSAGE_PRIORITY_HIGH content=You are Reviewer M2 (Instance 2 - Adversarial Review).
Your working directory is e:\osmanli\.agents\teamwork\reviewer_m2_2\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\reviewer_m2_2\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m2\technical_report_m2.md, and e:\osmanli\.agents\teamwork\worker_m2\handoff.md.
Perform adversarial review, examining security edge cases, header spoofing bypasses, and OCC rollback handling.
Run `python tools/verify_m2_security.py` and `python tests/run_all_tests.py`.
Write handoff.md in your working directory with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.
