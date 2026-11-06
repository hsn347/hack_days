# BRIEFING — 2026-11-02T19:06:00Z

## Mission
Execute Milestone 4 (Caching Policies, TTL Calibration, Invalidation Precision, and Logout/Switch Sanitization) in `dashboard/src/` to guarantee zero stale data and zero residual user data on logout or account switch.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa
- Working directory: e:\osmanli\.agents\teamwork\worker_m4
- Original parent: 44132d7d-07d0-4709-a292-a8e4727a82fd
- Milestone: M4 (Caching Policies & Logout Sanitization)

## 🔒 Key Constraints
- Local workspace only (`e:\osmanli`). Strictly NO remote uploads or server deployment (GEMINI.md Rule 4).
- File-Report-First rule (GEMINI.md Rule 5): Create `technical_report_m4.md` before ANY code edits or build commands.
- Exclusive file ownership:
  - `dashboard/src/hooks/useAuth.ts`
  - `dashboard/src/hooks/useCastles.ts`
  - `dashboard/src/App.tsx` (and query client setup)
  - `tools/verify_m4_caching_lifecycle.py`
- DO NOT CHEAT: Genuine logic, no hardcoded test outputs or fake verification.
- Pass `python tests/run_all_tests.py` (30/30).

## Current Parent
- Conversation ID: 44132d7d-07d0-4709-a292-a8e4727a82fd
- Updated: 2026-11-02T19:06:00Z

## Task Summary
- **What to build**: Standardize TanStack Query TTLs (Castle list, single castle, live stats), precision query key invalidations in mutations, complete purge of memory and `localStorage` on logout/account switch.
- **Success criteria**:
  - `useCastles.ts`: Castle list TTL: staleTime 60s, gcTime 10m; single castle: staleTime 30s, gcTime 5m; live bot stats: staleTime 10s, gcTime 1m.
  - Invalidation blind spots resolved for all castle mutations (add, delete, batch, import, toggle, credentials, control).
  - `useAuth.ts`: `queryClient.clear()` called, `localStorage` purged of all `empire_castles_cache_*` and `empire_active_castle_*` entries.
  - Zero TypeScript errors (`npx tsc --noEmit`).
  - Automated test script `tools/verify_m4_caching_lifecycle.py` verifies all requirements (23/23 PASS).
  - Regression test suite passes (30/30).
- **Interface contracts**: `PROJECT.md` & `ROOT_CAUSE_AND_PLAN.md`
- **Code layout**: `dashboard/src/` and `tools/`

## Key Decisions Made
- Standardized default `queryClient` gcTime to 600_000 (10 min) to avoid memory accumulation.
- Implemented dual-prefix support (`empire_castles_cache_` & `ibra_castles_cache_`) ensuring backwards compatibility while adopting the standard empire schema.
- Added active castle selection tracking (`empire_active_castle_`) with dedicated getter, setter, and purge handlers.
- Implemented `purgeUserDataOnLogout` in `useAuth.ts` which purges memory (`queryClient.clear()`), wipes all matching cache keys from `localStorage`, and purges session storage. Hooked it into `logout`, `switchAccount`, and forced domain mismatch exits.
- Added `useLiveBotStats` query hook with calibrated 10s staleTime / 1m gcTime.
- Added `useImportCastles` mutation with full invalidation coverage.
- Updated all mutations to invalidate single castle queries `['castle', userId, castleId]` and stats queries without blind spots.

## Artifact Index
- `technical_report_m4.md` — Mandatory pre-modification technical report
- `tools/verify_m4_caching_lifecycle.py` — Automated verification script (23/23 tests pass)
- `handoff.md` — Final 5-component handoff report

## Change Tracker
- **Files modified**:
  - `dashboard/src/lib/queryClient.ts`: gcTime set to 600_000 (10 min)
  - `dashboard/src/hooks/useCastles.ts`: Standardized TTLs, dual prefix support, active castle helpers, purgeCastlesCache, precision invalidation, useImportCastles
  - `dashboard/src/hooks/useAuth.ts`: purgeUserDataOnLogout hooked into logout/switch
  - `tools/verify_m4_caching_lifecycle.py`: Automated verification suite
- **Build status**: PASS (`tsc --noEmit` 0 errors, `npm run build` PASS)
- **Pending issues**: None

## Quality Status
- **Build/test result**: PASS (M4: 23/23, Full Platform: 30/30)
- **Lint status**: Clean
- **Tests added/modified**: `tools/verify_m4_caching_lifecycle.py` (23 tests across 4 tiers)
