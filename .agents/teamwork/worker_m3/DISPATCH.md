# DISPATCH - Worker M3: Frontend State & Single Source of Truth Unification

## Mission
Execute Milestone 3 (Frontend State Architecture, Single Source of Truth Unification, and Mutation Lifecycle) in `e:\osmanli\dashboard\src\`.

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
`e:\osmanli\.agents\teamwork\worker_m3\technical_report_m3.md`
detailing:
1. Exact root causes and diagnostic analysis.
2. Architecture and logic steps to be applied.
3. Targeted files, lines, and expected results.

## Exclusive Write Boundaries (File Ownership)
You exclusively own and may edit:
- `dashboard/src/components/CastleCard.tsx`
- `dashboard/src/components/TaskTabContent.tsx`
- `dashboard/src/hooks/useUserBotStatuses.ts` (if needed for status unification)
- `dashboard/src/types/` (if any type definition is needed)
- Measurement / verification scripts in `tools/` (e.g. `tools/verify_m3_frontend_state.py`)

## Technical Objectives (R2 & R7)
1. **Single Source of Truth in `CastleCard.tsx`**:
   - Eliminate redundant local React state forks (`isStarting`, `isStopping`, `realStatus`, etc.) that compete or get out of sync with TanStack Query and the multiplexed WebSocket state.
   - Bind card status directly to the authoritative cache / WebSocket status.
   - Implement clean and explicit state transitions: loading, error, empty, success.
   - Ensure clicking anywhere on the outer card toggles the task cleanly without conflicting with child inputs (per GEMINI.md UX rule 2).
2. **Eliminate Mutation Desync on Unmount in `TaskTabContent.tsx`**:
   - Currently, task configuration saves triggered during component unmount bypass the TanStack Query cache or can race with active queries.
   - Ensure unmount saves immediately flush to TanStack Query cache via `queryClient.setQueryData(["castleConfig", castleId], ...)` and update local state so navigating back/away never displays stale or reverted settings.
   - Prevent double-clicking / duplicate mutation submissions (R7).
3. **Optimistic Concurrency Control (OCC) Integration**:
   - Update config save mutations to send the current record `version` and handle HTTP 409 Conflict gracefully (prompting user or refreshing with latest server config).
4. **Verification**:
   - Verify frontend build: `npm run build` or `npx tsc --noEmit` inside `dashboard/`.
   - Create an automated inspection / verification script `tools/verify_m3_frontend_state.py` asserting AST / structure / TypeScript compliance.
   - Run project test runner `python tests/run_all_tests.py` ensuring 100% pass rate.

## Working Directory & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\worker_m3\`
- When finished, write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion, Verification Method.
- Report completion via `send_message`.


## 2026-11-02T18:16:23Z
[Message] timestamp=2026-11-02T18:16:23Z sender=44132d7d-07d0-4709-a292-a8e4727a82fd priority=MESSAGE_PRIORITY_HIGH content=You are Worker M3 (Role: Frontend State & Single Source of Truth Worker).
Your working directory is e:\osmanli\.agents\teamwork\worker_m3\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\worker_m3\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md and e:\osmanli\.agents\teamwork\ROOT_CAUSE_AND_PLAN.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY RULE: File-Report-First (GEMINI.md Rule 5):
Before making ANY edits to source code files or running build commands, you MUST create a comprehensive technical report artifact in your working directory:
e:\osmanli\.agents\teamwork\worker_m3\technical_report_m3.md
detailing root causes, architecture/logic, and exact targeted files/lines.

Execute Milestone 3:
1. Single source of truth in dashboard/src/components/CastleCard.tsx (eliminate competing local states, bind to query/websocket, explicit loading/error/success states, clean outer card toggle).
2. Fix mutation desync on unmount in dashboard/src/components/TaskTabContent.tsx (flush unmount saves to TanStack Query setQueryData and local state, prevent duplicate submits).
3. Integrate OCC versioning and HTTP 409 handling in config save mutations.
4. Verify frontend build and run tests: run `python tests/run_all_tests.py` (Must pass 30/30).
5. Create tools/verify_m3_frontend_state.py to verify state architecture.
6. Write handoff.md with all 5 sections and report back via send_message.
