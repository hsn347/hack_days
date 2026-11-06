# DISPATCH - Worker M4: Caching Policies & Logout/Switch Sanitization

## Mission
Execute Milestone 4 (Caching Policies, TTL Calibration, Precision Invalidation, and Comprehensive Logout/Switch Sanitization) in `e:\osmanli\dashboard\src\`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md`
- `e:\osmanli\AGENTS_CONSTITUTION.md`

## ⚠️ MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## ⚠️ MANDATORY RULE: File-Report-First (GEMINI.md Rule 5)
Before making ANY edits to source code files or running build commands, you MUST create a comprehensive technical report artifact in your working directory:
`e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md`
detailing root causes, architecture/logic, and exact targeted files/lines.

## Exclusive Write Boundaries (File Ownership)
You exclusively own and may edit:
- `dashboard/src/hooks/useAuth.ts`
- `dashboard/src/hooks/useCastles.ts`
- `dashboard/src/App.tsx` (or query client setup file)
- Measurement / verification scripts in `tools/` (e.g. `tools/verify_m4_caching_lifecycle.py`)

## Technical Objectives (R3 & R7)
1. **Precision Query Invalidation & TTL Calibration**:
   - Standardize `staleTime` and `gcTime` in TanStack Query:
     - Castle list: `staleTime: 60_000`, `gcTime: 600_000` (10 min).
     - Single castle config: `staleTime: 30_000`, `gcTime: 300_000` (5 min).
     - Live bot stats: `staleTime: 10_000`, `gcTime: 60_000` (1 min).
   - Fix invalidation blind spots: Ensure all mutation hooks (add castle, delete castle, batch update, import) invalidate the exact affected query keys.
2. **Comprehensive Logout & Account Switch Sanitization**:
   - In `useAuth.ts` (and wherever logout/switch is handled):
     - Immediately invoke `queryClient.clear()` to purge all cached server responses from memory.
     - Scan and remove all cached user castle entries from `localStorage`:
       * `localStorage.removeItem('empire_castles_cache_' + userId)`
       * Purge any lingering user keys matching `empire_castles_cache_*`
       * Clear active castle selection `empire_active_castle_*`
     - Guarantee that logging out or switching accounts leaves ZERO residual data of the previous user in the browser.
3. **Verification**:
   - Create automated verification script `tools/verify_m4_caching_lifecycle.py` verifying cache configuration, logout purge, and mutation invalidation.
   - Run `Set-Location dashboard; npx tsc --noEmit` (Must pass with 0 errors).
   - Run project test runner `python tests/run_all_tests.py` (Must pass 30/30).

## Working Directory & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\worker_m4\`
- When finished, write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion, Verification Method.
- Report completion via `send_message`.


## 2026-11-02T18:53:05Z
You are Worker M4 (Role: Caching Policies & Logout Sanitization Worker).
Your working directory is e:\osmanli\.agents\teamwork\worker_m4\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\worker_m4\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md and e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY RULE: File-Report-First (GEMINI.md Rule 5):
Before making ANY edits to source code files or running build commands, you MUST create a comprehensive technical report artifact in your working directory:
e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md
detailing root causes, architecture/logic, and exact targeted files/lines.

Execute Milestone 4:
1. Standardize Query TTLs in TanStack Query (dashboard/src/hooks/useCastles.ts, App.tsx):
   - Castle list: staleTime 60_000, gcTime 600_000.
   - Single castle: staleTime 30_000, gcTime 300_000.
   - Live bot stats: staleTime 10_000, gcTime 60_000.
2. Fix invalidation blind spots: Ensure all mutation hooks (add castle, delete castle, batch update, import) invalidate the exact affected query keys.
3. Logout & Account Switch Sanitization in dashboard/src/hooks/useAuth.ts:
   - Call queryClient.clear() to purge all cached server responses from memory.
   - Purge all user castle cache keys from localStorage (`empire_castles_cache_*`).
   - Clear active castle selection (`empire_active_castle_*`).
   - Guarantee zero residual user data on logout/switch.
4. Verify frontend build (`npx tsc --noEmit` & `npm run build`).
5. Create tools/verify_m4_caching_lifecycle.py to verify caching and sanitization logic.
6. Run `python tests/run_all_tests.py` (Must pass 30/30).
7. Write handoff.md with all 5 sections and report back via send_message.
