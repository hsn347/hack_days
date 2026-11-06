# DISPATCH - Challenger M3 (Instance 1 - Frontend State Architecture Challenger)

## Mission
Empirically stress-test and challenge the frontend state architecture implemented in Milestone 3 in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m3\technical_report_m3.md`
- `e:\osmanli\.agents\teamwork\worker_m3\handoff.md`

## Challenge Tasks & Methodology
Write and run an empirical inspection/stress script (e.g. `tools/stress_m3_frontend_state.py`) asserting:
1. Complete elimination of all 5 competing local state variables (`liveCastle`, `liveState`, `connState`, `isStopping`, `isStarting`) from `CastleCard.tsx`.
2. Pure derivation of `effectiveStatus` and mutation states (`isStarting`, `isStopping`).
3. Verification that `TaskTabContent.tsx` unmount hook flushes changes to:
   - `['castles', userId]`
   - `['castle', userId, castle.id]`
   - `['castleConfig', castle.id]`
   - `saveCachedCastles`
4. In-flight mutation guard preventing double submits.
5. OCC version threading through `types/index.ts`, `botApi.ts`, and `useCastles.ts`.

## Verification & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\challenger_m3_1\`
- Run your harness and record exact outputs.
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicit verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.


## 2026-11-02T18:36:53Z
You are Challenger M3 (Instance 1 - Frontend State Architecture Challenger).
Your working directory is e:\osmanli\.agents\teamwork\challenger_m3_1\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\challenger_m3_1\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m3\technical_report_m3.md, and e:\osmanli\.agents\teamwork\worker_m3\handoff.md.
Empirically stress-test the frontend state architecture:
1. Verify elimination of competing useState in CastleCard.tsx.
2. Verify pure derivation of effectiveStatus.
3. Verify unmount cleanup flushes to queryClient.setQueryData (3 keys) and saveCachedCastles.
4. Verify in-flight double submit guards.
5. Verify version parameter threading.
Write and run an empirical inspection harness in tools/ (e.g. tools/stress_m3_frontend_state.py).
Write handoff.md with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.
