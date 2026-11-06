# DISPATCH - Reviewer M4 (Instance 1)

## Mission
Perform independent code correctness and interface review of Milestone 4 implementations (Caching Policies, TTL Calibration, Invalidation Precision, and Logout/Switch Sanitization) in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md`
- `e:\osmanli\.agents\teamwork\worker_m4\handoff.md`

## Review Scope
- `dashboard/src/lib/queryClient.ts`: default `gcTime: 600_000` (down from 24h).
- `dashboard/src/hooks/useCastles.ts`:
  - `useCastles`: `staleTime: 60_000`, `gcTime: 600_000`.
  - `useCastle`: `staleTime: 30_000`, `gcTime: 300_000`.
  - `useLiveBotStats`: `staleTime: 10_000`, `gcTime: 60_000`.
  - Invalidation precision across all mutation hooks (`useUpdateCastleCredentials`, `useToggleCastleActive`, `useDeleteCastle`, `useBotControl`, `useImportCastles`, etc.).
- `dashboard/src/hooks/useAuth.ts`:
  - `purgeUserDataOnLogout`: `queryClient.clear()`, scanning and purging `localStorage` castle caches (`empire_castles_cache_*`, `ibra_castles_cache_*`, `empire_active_castle_*`), and `sessionStorage`.

## Verification Tasks
1. Run dedicated verification suite: `python tools/verify_m4_caching_lifecycle.py` (Must pass 23/23).
2. Run TypeScript compiler check: `Set-Location dashboard; npx tsc --noEmit` (Must pass with 0 errors).
3. Run full project test suite: `python tests/run_all_tests.py` (Must pass 30/30).
4. Evaluate correctness, completeness, robustness, and layout compliance.

## Working Directory & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\reviewer_m4_1\`
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicit verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.


## 2026-11-02T19:07:39Z
You are Reviewer M4 (Instance 1).
Your working directory is e:\osmanli\.agents\teamwork\reviewer_m4_1\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\reviewer_m4_1\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md, and e:\osmanli\.agents\teamwork\worker_m4\handoff.md.
Perform code review of caching policies, query TTL standardization, mutation invalidation precision, and logout sanitization.
Run `python tools/verify_m4_caching_lifecycle.py`, `Set-Location dashboard; npx tsc --noEmit`, and `python tests/run_all_tests.py`.
Write handoff.md with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.
