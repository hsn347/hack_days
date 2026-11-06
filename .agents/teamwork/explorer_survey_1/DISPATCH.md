# Explorer 1 Dispatch: Frontend, State, Caching & Network Investigation

- Working Directory: e:\osmanli\.agents\teamwork\explorer_survey_1\
- Authoritative Request: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
- Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md

## Scope & Mandate
Examine the entire frontend code in `dashboard/` (React 18, Vite, TypeScript, Tailwind):
1. **State Architecture & Single Source of Truth**: Map where data lives (React state, Context, LocalStorage, hooks). Identify conflicting copies, synchronization gaps, and missing explicit states (Loading, Error, Empty, Success).
2. **Caching & Invalidation Lifecycle**: How query cache is handled, TTLs, invalidation triggers on mutation, stale data display, and cache cleanup on account/castle switch or logout.
3. **Network & API Optimization**: Check for duplicate requests, missing debouncing/throttling, unmanaged polling, missing AbortController on component unmount/navigation.
4. **Re-render Cascades & Resource Leaks**: Identify unnecessary re-render triggers, dangling listeners/intervals, unmanaged state accumulations.
5. **Localization & Theme & UX**: Hardcoded strings, dark/light mode contrast, button states during mutations.

Deliver comprehensive report and `handoff.md` in your directory.


## 2026-11-02T16:17:04Z
You are Explorer 1: Frontend & State Architect Explorer.
Your working directory is: e:\osmanli\.agents\teamwork\explorer_survey_1\
Authoritative user request file: e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md
Governing Constitution: e:\osmanli\AGENTS_CONSTITUTION.md
Dispatch instructions: e:\osmanli\.agents\teamwork\explorer_survey_1\DISPATCH.md

MANDATORY FIRST STEP:
Read e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md and e:\osmanli\AGENTS_CONSTITUTION.md before doing any analysis.

YOUR MISSION:
Perform a deep forensic audit of the frontend architecture (dashboard/ - React 18, Vite, TypeScript, Tailwind):
1. State Management & Single Source of Truth:
   - Identify where state is stored across components, contexts, hooks, and localStorage.
   - Trace data flow from API responses to UI rendering.
   - Detect state desynchronization, duplicate state, conflicting sources of truth, and missing explicit status flags (loading, error, empty, success).
2. Caching Policies & Invalidation:
   - Examine how query data is cached (if TanStack Query/swr/custom hooks are used), cache TTLs, cache key granularity.
   - Check cache invalidation mechanisms upon mutations (save, delete, toggle) — are stale data shown?
   - Check cache/state purging during logout or account/castle switching.
3. Network & API Optimization:
   - Audit all API calls in dashboard/src/api/ and custom hooks.
   - Detect duplicate calls, lack of deduplication, missing debouncing/throttling on inputs/searches.
   - Check if AbortController is implemented for cancelled requests on unmount/navigation.
   - Check for unmanaged polling intervals.
4. Performance & Re-render Cascades:
   - Detect broad re-renders (unflattened contexts, missing useMemo/useCallback, layout animations).
   - Check for memory leaks (dangling event listeners, setIntervals without cleanup).
5. UX & Mutation Feedback:
   - Audit mutation UX (save buttons, disabled states, double-click protection, toasts).
   - Audit trilingual support (ar, en, tr) and dark/light mode contrast issues.

CONSTRAINTS:
- You are READ-ONLY. Do NOT modify source code.
- Write your comprehensive findings to e:\osmanli\.agents\teamwork\explorer_survey_1\report.md and your structured handoff to e:\osmanli\.agents\teamwork\explorer_survey_1\handoff.md.
- Update your progress.md regularly for heartbeat liveness.
- Once done, send a message to orchestrator with your summary and handoff path.
