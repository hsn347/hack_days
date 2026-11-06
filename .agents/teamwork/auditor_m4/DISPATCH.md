# DISPATCH - Forensic Auditor M4

## Mission
Conduct forensic integrity audit and anti-cheating verification of Milestone 4 (Caching Policies, TTL Calibration, Invalidation Precision, and Logout Sanitization) in `e:\osmanli`.

## 🔒 Mandatory Context Files
Read these files in full before starting work:
- `e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md` (MANDATORY - read in full)
- `e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md`
- `e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md`
- `e:\osmanli\.agents\teamwork\worker_m4\handoff.md`

## Audit Criteria & Forensic Checks
1. Genuine Logic vs Cheating:
   - Inspect git diff or line changes in `dashboard/src/lib/queryClient.ts`, `dashboard/src/hooks/useCastles.ts`, and `dashboard/src/hooks/useAuth.ts`.
   - Verify that TTLs and gcTime are authentically calibrated, not bypassed.
   - Verify that `purgeUserDataOnLogout` genuinely purges queryClient and localStorage.
2. Test Suite Integrity:
   - Inspect `tools/verify_m4_caching_lifecycle.py`: verify real AST/regex/structural assertions and zero mock bypasses or dummy constant returns.
3. Zero Tolerance Violation Check:
   - If any cheating, hardcoded expected outputs, or dummy facades are found, report `INTEGRITY VIOLATION`.
   - If clean and authentic, report `CLEAN`.

## Working Directory & Handoff
- Working directory: `e:\osmanli\.agents\teamwork\auditor_m4\`
- Write `handoff.md` with: Observation, Logic Chain, Caveats, Conclusion (explicit verdict: `CLEAN` or `INTEGRITY VIOLATION`), and Verification Method.


## 2026-11-02T19:07:39Z
You are Forensic Auditor M4.
Your working directory is e:\osmanli\.agents\teamwork\auditor_m4\
Read your dispatch instructions in e:\osmanli\.agents\teamwork\auditor_m4\DISPATCH.md
Read the mandatory context file e:\osmanli\.agents\teamwork\ORIGINAL_REQUEST.md in full before starting work.
Also read e:\osmanli\.agents\teamwork\orchestrator\PROJECT.md, e:\osmanli\.agents\teamwork\worker_m4\technical_report_m4.md, and e:\osmanli\.agents\teamwork\worker_m4\handoff.md.
Conduct an independent forensic integrity audit of Milestone 4:
1. Verify genuine logic vs hardcoded facades in queryClient.ts, useCastles.ts, and useAuth.ts.
2. Verify test integrity in tools/verify_m4_caching_lifecycle.py (real structural/AST assertions, zero mocks).
3. Zero tolerance check: report CLEAN if authentic, or INTEGRITY VIOLATION if any cheating is found.
Write handoff.md with a binary verdict: CLEAN or INTEGRITY VIOLATION.
Report your completion and verdict back via send_message.
