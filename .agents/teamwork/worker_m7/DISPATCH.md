# Dispatch Directive: Worker M7 — UX Lifecycle, Trilingual & Resource Cleanup

## 2026-11-02T20:20:00Z
- **Target Role**: teamwork_worker
- **Milestone**: Milestone 7: UX Lifecycle, Confirm Modals, Trilingual Consistency & Resource Cleanup
- **Working Directory**: `e:\osmanli\.agents\teamwork\worker_m7\`
- **Mandatory Requirements Reference**: `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (R6, R7, R8)
- **Project Scope Document**: `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- **Integrity Mode**: `development` (Strictly local, no remote deployment per GEMINI.md Rule 4 & AGENTS_CONSTITUTION.md Rule 13)

---

## 🔒 MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

---

## 🔒 MANDATORY FILE-REPORT-FIRST RULE (GEMINI.md Rule 5)
You MUST create an independent technical report artifact (.md file) at:
`e:\osmanli\.agents\teamwork\worker_m7\technical_report_m7.md`
BEFORE modifying any code or executing any commands. The report must detail:
1. Diagnosis and why the changes are needed.
2. Step-by-step logic and changes to be applied.
3. Affected files, lines, and expected outcomes.

---

## Scope & Concrete Objectives

### 1. Replace Blocking Browser Dialogs (`window.confirm`, `window.alert`)
- Scan and replace any remaining `window.confirm` or `window.alert` calls across `dashboard/src/components/` and `dashboard/src/pages/` with clean, non-blocking modal confirmation dialogs.
- Adhere strictly to GEMINI.md Rule 2: Concise, crisp, direct text without filler words, instant snappy transitions (no slow animations or sluggish layout shifts).

### 2. Trilingual Consistency Across Locales (`ar`, `en`, `tr`)
- Check `dashboard/src/locales/ar.json`, `en.json`, and `tr.json`.
- Ensure all recent keys (pagination, castle summary, status labels, confirmation dialogs) are translated across all three languages without missing keys or untranslated fallbacks.
- Ensure RTL/LTR layouts behave cleanly across Arabic, English, and Turkish.

### 3. Theme Contrast & Mobile Single-Row Layouts
- Ensure dark/light mode contrast meets accessibility standards in newly updated pagination controls, accordion headers, and badges.
- Verify mobile responsiveness: maintain single-row layouts for titles and action toggles on mobile screens without awkward line wrapping (GEMINI.md Rule 2).

### 4. Merchant Admin Access Hardening in `api_server.py`
- In `api_server.py:get_admin_user_castles`, add merchant access verification `_verify_merchant_access_to_user(admin, db.get_user(uid))` so that merchant admins cannot inspect castles of users outside their managed merchant domain (closing the gap flagged by Reviewer M6-2).

### 5. Resource Cleanup & Leak Prevention
- Verify all unmount cleanup functions (`useEffect` returns) properly cancel timers, abort pending queries, and unregister event listeners.
- Remove obsolete debug console logging not appropriate for production.

### 6. Verification Harness & Platform Integrity
- Author a dedicated verification harness: `tools/verify_m7_ux_lifecycle.py` checking:
  - Zero `window.confirm` / `window.alert` invocations in production components.
  - Complete trilingual key parity across `ar.json`, `en.json`, and `tr.json`.
  - Merchant isolation check in `api_server.py`.
- Ensure `npx tsc --noEmit` and `npm run build` pass with 0 errors.
- Ensure `python tests/run_all_tests.py` passes 30/30 (100%).

---

## Exclusive File Boundaries
- `dashboard/src/components/` (modal dialogs, confirm wrappers)
- `dashboard/src/pages/` (replacing confirm calls)
- `dashboard/src/locales/` (`ar.json`, `en.json`, `tr.json`)
- `api_server.py` (merchant admin check on `/api/admin/users/{uid}/castles`)
- `tools/verify_m7_ux_lifecycle.py`

## Deliverables
1. `technical_report_m7.md` in your working directory (FIRST).
2. Code implementations in owned files.
3. Verification harness `tools/verify_m7_ux_lifecycle.py`.
4. Passing results for `verify_m7_ux_lifecycle.py`, `npx tsc --noEmit`, `npm run build`, and `tests/run_all_tests.py`.
5. Handoff report `handoff.md` in your working directory.
6. Notify orchestrator via `send_message`.

