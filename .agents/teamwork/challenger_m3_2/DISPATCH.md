# DISPATCH - Challenger M3 (Instance 2 - Build & Concurrency OCC Challenger)

## Mission
Empirically test production build integrity and OCC frontend/backend integration in Milestone 3 in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m3\technical_report_m3.md`
- `e:\osmanli\.agents\teamwork\worker_m3\handoff.md`

## Challenge Tasks & Methodology
1. Production Build Stress Test:
   - Run `Set-Location dashboard; npm run build` and verify that Vite compiles the entire bundle with 0 errors.
   - Run `Set-Location dashboard; npx tsc --noEmit` and verify 0 type errors.
2. OCC API Simulation:
   - Verify that `botApi.updateCastle` captures HTTP 409 responses and tags the error with `isConflict: true`.
   - Verify that `TaskTabContent.tsx` catches 409 and triggers query cache invalidation.
3. Regression Test:
   - Run `python tests/run_all_tests.py` (Must pass 30/30).

## Verification & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\challenger_m3_2\`
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicit verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.


## 2026-11-02T18:36:53Z
You are Challenger M3 (Instance 2 - Build & Concurrency OCC Challenger).
Your working directory is e:\osmanli\.agents\teamwork\challenger_m3_2\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\challenger_m3_2\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m3\technical_report_m3.md, and e:\osmanli\.agents\teamwork\worker_m3\handoff.md.
Empirically test build integrity and OCC frontend integration:
1. Test production bundle build: `Set-Location dashboard; npm run build` and `npx tsc --noEmit`.
2. Test OCC error handling: verify botApi.updateCastle catches 409 and flags isConflict.
3. Run project regression suite: `python tests/run_all_tests.py` (Must pass 30/30).
Write handoff.md with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.
