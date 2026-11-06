# Technical Report: Pre-Verification Execution Plan for Milestone 6 Architecture Review

**Author**: Reviewer M6 (Instance 1)  
**Date**: 2026-11-02T20:11:00Z  
**Context**: Pre-Command Execution Technical Plan per GEMINI.md Rule 5  
**Target Files**: `Admin.tsx`, `AdminUsersCastles.tsx`, `botApi.ts`, `api_server.py`, `App.tsx`, `tools/verify_m6_admin_scalability.py`

---

## 1. Diagnosis & Motivation (تشخيص السبب ولماذا هذا الإجراء مطلوب)

Milestone 6 delivered major architectural scalability changes:
1. **Client-side pagination** in `dashboard/src/pages/Admin.tsx` with default page size of 25, selectable sizes [10, 25, 50, 100], automatic reset to page 1 upon filter/search changes, and responsive layout styling.
2. **Master-Detail Table Splitting** in `dashboard/src/pages/AdminUsersCastles.tsx`: transitioning from a monolithic 10+ MB JSON payload to a lightweight `<60 KB` summary endpoint (`GET /api/admin/users-castles/summary`), with on-demand lazy loading of full castle configurations (`GET /api/admin/users/{uid}/castles`) when a user's accordion row is expanded.
3. **TanStack Query Caching & Scoped Invalidation**: detail queries scoped to `['admin_user_castles', uid]` with 30s staleTime and 5m gcTime, along with scoped invalidation and optimistic updates on castle deletion.
4. **Route-Level Code Splitting** in `dashboard/src/App.tsx`: converting static administrative page imports to `React.lazy()` wrapped in `React.Suspense` with a lightweight loading fallback.

To independently certify that these changes operate correctly, maintain complete backward compatibility, introduce no TypeScript or bundling regressions, and pass all verification invariants, we must execute the automated test suites and the production bundle compiler.

---

## 2. Logic & Steps to Apply (المنطق والخطوات التي سيتم تطبيقها)

1. **Static Analysis & Inspection**: Inspect AST structures, state hooks, endpoint decorators, and type definitions across all modified files (already conducted via read-only inspections).
2. **Execute M6 Scalability Verification Suite**:
   Run `python tools/verify_m6_admin_scalability.py` to validate Tier 1 through Tier 6 invariants (pagination math, UI controls, master-detail separation, scoped queries, endpoint admin guards, and simulated payload bounds).
3. **Execute Production Bundle Compilation**:
   Run `powershell -Command "Set-Location dashboard; npm run build"` to verify TypeScript strict type checking (`tsc`) and Vite code splitting into separate route chunks.
4. **Execute Platform Integration Test Runner**:
   Run `python tests/run_all_tests.py` to ensure core bot engine, database OCC, and authentication subsystems remain healthy across the 30-test suite.
5. **Execute Milestone 5 Regression Suite**:
   Run `python tools/verify_m5_network_dedup.py` to confirm AbortController and debouncing mechanisms remain intact.

---

## 3. Commands to Execute & Expected Results (الأوامر والنتائج المتوقعة بالتفصيل)

| Command | Working Directory | Expected Result |
|---|---|---|
| `python tools/verify_m6_admin_scalability.py` | `e:\osmanli` | `38/38 Passed`, returncode 0 |
| `powershell -Command "Set-Location dashboard; npm run build"` | `e:\osmanli` | `tsc && vite build` succeeds, generating independent chunks, 0 errors |
| `python tests/run_all_tests.py` | `e:\osmanli` | `30/30 passed (100.0%)`, returncode 0 |
| `python tools/verify_m5_network_dedup.py` | `e:\osmanli` | `71/71 passed (100.0%)`, returncode 0 |

---

## 4. Local Execution & Safety Guardrails (القيود وحماية الإنتاج)

- No remote network requests, SSH, SFTP, or server uploads will be performed (Rule 4 strict adherence).
- All commands execute strictly within local project directories in Windows PowerShell/Python runtime.
