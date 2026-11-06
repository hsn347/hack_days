# Execution Plan — Platform Performance & Data Management Overhaul

## Overview
Executing a deep, disciplined architectural overhaul of platform performance, data flow, state management, caching policies, network optimization, admin dashboard scalability, and backend/DB efficiency strictly aligned with `AGENTS_CONSTITUTION.md` and user requirements R1–R8.

## Phases

### Phase 0: Deep System Audit & Baseline Measurement (Current)
- **Explorer 1 (Frontend & State/Cache/Network)**:
  - Deep audit of `dashboard/src/` (React 18, Vite, hooks, contexts, TanStack Query/swr if any, localStorage usage).
  - Map data flow from API responses to component state and DOM.
  - Identify re-render cascades, memory leaks, unmanaged listeners/intervals, duplicate network calls, missing AbortControllers, and lack of explicit state transitions (Loading/Error/Empty/Success).
  - Inspect trilingual integrity, theme contrast, and asset performance.
- **Explorer 2 (Backend, Database & Concurrency)**:
  - Deep audit of `api_server.py`, `bot_manager.py`, SQLite database (`database/castles.db` schema and queries).
  - Identify slow queries, missing indexes, N+1 query patterns, unbound queries, connection leaks, resource deallocation.
  - Audit concurrency safety: lost updates, lack of OCC / versioning / idempotency, cross-castle / cross-account data isolation.
- **Explorer 3 (Admin Dashboard, Logs & Baseline Measurement)**:
  - Deep audit of Admin Dashboard tables, log viewer, pagination vs virtualization vs lazy loading.
  - Design and execute baseline measurement scripts under strictly documented, fixed test conditions:
    - Frontend metrics: LCP, INP, CLS, load/navigation times, request count & transfer payload, re-renders, memory footprint.
    - Backend metrics: P50 & P95 response times, slowest queries & execution durations, resource consumption.
    - Admin metrics: initial render time, search/filter latency, page transition time, performance across small/medium/large record sets.
  - Formulate quantitative, realistic target metrics for post-optimization.

### Phase 1: Root Cause Analysis, Synthesis & Developer Approval Gate
- Merge Explorer findings into comprehensive Feature Inventory & Bottleneck Register.
- Publish `ROOT_CAUSE_AND_PLAN.md` artifact detailing:
  1. Deep diagnostic root causes prioritized by severity (Critical, High, Medium, Low).
  2. Baseline measurement records with fixed test conditions.
  3. Concrete architecture proposals for State, Cache, Network, Admin Dashboard, and Backend.
  4. Phased remediation milestones and rollback plans.
- Submit to Developer for explicit approval before any code changes are enacted (mandatory gate).

### Phase 2: Implementation Track & E2E Testing Track (Post-Approval)
- Decompose into modular implementation sub-orchestrators:
  - Milestone 1: Backend & SQLite Query Optimization, Indexing & Connection Lifecycle.
  - Milestone 2: Concurrency Control, Transactions, Idempotency & Castle Isolation.
  - Milestone 3: Frontend State Architecture & Single Source of Truth.
  - Milestone 4: Caching Layer, Precision Invalidation & Account Switching Cleanup.
  - Milestone 5: Network Layer Optimization, Deduplication, Debounce & AbortController.
  - Milestone 6: Admin Dashboard Scalability, Table Performance & Detail On-Demand.
  - Milestone 7: UX Feedback, Mutation Lifecycle, Trilingual & Resource Cleanup.
- Spawn parallel E2E Testing Orchestrator for 4-tier opaque-box test suite (`TEST_INFRA.md` -> `TEST_READY.md`).
- Execute Final Milestone (Pass 100% E2E tests + Tier 5 Adversarial Hardening).
- Dual Field Verification (Backend live accounts + continuous browser test) & Victory Audit.

