# DISPATCH - Reviewer M4 (Instance 2 - Adversarial Review)

## Mission
Perform adversarial and edge-case review of Milestone 4 implementations in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md`
- `e:\osmanli\.agents\teamwork\worker_m4\handoff.md`

## Review Scope & Adversarial Focus
- Edge cases in `purgeUserDataOnLogout`:
  - Does regex scanning handle dynamic keys with varied user IDs and corrupted entries safely?
  - Does the purge preserve necessary UI preferences (`osmanli_lang`, `osmanli_theme`) while eliminating all sensitive castle and token data?
  - What happens if `queryClient.clear()` is called while an active query is in-flight?
  - Are there any stale data flash vulnerabilities upon immediate re-login with a different user?
- Vite production build check.

## Verification Tasks
1. Run dedicated verification suite: `python tools/verify_m4_caching_lifecycle.py` (Must pass 23/23).
2. Run Vite production build: `Set-Location dashboard; npm run build` (Must pass with 0 errors).
3. Run full project test suite: `python tests/run_all_tests.py` (Must pass 30/30).
4. Evaluate robustness and edge cases.

## Working Directory & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\reviewer_m4_2\`
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicit verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.

## 2026-11-02T19:07:39Z
[Message] timestamp=2026-11-02T19:07:39Z sender=44132d7d-07d0-4709-a292-a8e4727a82fd priority=MESSAGE_PRIORITY_HIGH content=You are Reviewer M4 (Instance 2 - Adversarial Review).
Your working directory is e:\osmanli\.agents\teamwork\reviewer_m4_2\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\reviewer_m4_2\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md, and e:\osmanli\.agents\teamwork\worker_m4\handoff.md.
Perform adversarial review, focusing on localStorage scanning edge cases, multi-tab logout races, query key collision, stale data flash, and language/theme preference preservation.
Run `python tools/verify_m4_caching_lifecycle.py`, `Set-Location dashboard; npm run build`, and `python tests/run_all_tests.py`.
Write handoff.md with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.

