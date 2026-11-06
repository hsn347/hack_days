# DISPATCH - Challenger M4 (Instance 1 - Caching & Invalidation Challenger)

## Mission
Empirically stress-test caching policies and mutation query invalidations implemented in Milestone 4 in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md`
- `e:\osmanli\.agents\teamwork\worker_m4\handoff.md`

## Challenge Tasks & Methodology
Write and run an empirical challenge harness in `tools/` (e.g. `tools/stress_m4_caching.py`):
1. Verify exact TTL values (`staleTime: 60s`, `gcTime: 10m` for castle list; `30s`/`5m` for single castle; `10s`/`1m` for live stats; `600_000` global default).
2. Verify that all mutation hooks (`useAddCastle`, `useDeleteCastle`, `useUpdateCastleCredentials`, `useToggleCastleActive`, `useBatchUpdateCastleConfigs`, `useUpdateBotState`, `useBotControl`, `useStopUserBots`, `useImportCastles`) invalidate both collection and item query keys.
3. Verify that `useDeleteCastle` performs `qc.removeQueries` for deleted item cache.
4. Run regression suite `python tests/run_all_tests.py` (Must pass 30/30).

## Verification & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\challenger_m4_1\`
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicit verdict: `APPROVE` or `REQUEST_CHANGES`), and Verification Method.

## 2026-11-02T19:07:39Z
You are Challenger M4 (Instance 1 - Caching & Invalidation Challenger).
Your working directory is e:\osmanli\.agents\teamwork\challenger_m4_1\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\challenger_m4_1\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md, and e:\osmanli\.agents\teamwork\worker_m4\handoff.md.
Empirically stress-test caching policies and mutation query invalidations:
1. Verify exact TTL values (staleTime/gcTime) across list, single item, live stats, and global queryClient.
2. Verify mutation hooks invalidate both collection and item query keys.
3. Verify useDeleteCastle performs qc.removeQueries.
Write and run an empirical challenge harness in tools/ (e.g. tools/stress_m4_caching.py).
Write handoff.md with an explicit verdict: APPROVE or REQUEST_CHANGES.
Report your completion and verdict back via send_message.

