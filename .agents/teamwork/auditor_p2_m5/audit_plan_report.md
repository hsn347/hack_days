# Technical Report: Forensic Integrity Audit Plan for Milestone 5 (Requirement R4)

## 1. Diagnosis & Rationale (تشخيص السبب ولماذا هذا الإجراء مطلوب)
This technical report is established prior to executing any commands or checks in the workspace, in strict compliance with `GEMINI.md` Rule 5.
The objective is to conduct a forensic integrity audit on Milestone 5 deliverables submitted by `worker_p2_m5_gen2`, specifically verifying Requirement R4 from `ORIGINAL_REQUEST.md`:
- Strict prohibition compliance regarding: `game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`.
- Authenticity of the 18 mandatory test scenarios in `tests/test_mandatory_scenarios.py` (checking for zero hardcoded or facade implementations, verifying genuine calls to bot lifecycle, API endpoints, and database).
- Authenticity of the continuous soak testing script `tools/soak_test_lifecycle.py` (verifying real Windows PSAPI / ctypes memory profiling and genuine linear regression math, rather than simulated slopes).
- Empirical verification by executing tests independently and checking exit codes and output logs.

## 2. Logic & Step-by-Step Forensic Methodology (المنطق والخطوات التي سيتم تطبيقها)

### Step 1: Strict Prohibition Verification
- Use git status, git log, and git diff without opening, modifying, or reading the three prohibited files (`game_client.py`, `core/onemt_auth.py`, `core/onemt_bot.py`).
- Check SHA256 hashes against git head or commit history to confirm they were untouched, unopened, and unmodified.

### Step 2: Static Source Code Authenticity Analysis
- Inspect `tests/test_mandatory_scenarios.py`:
  - Check imports, mocking strategies, and assertions.
  - Verify if real platform logic is executed or if mocks bypass the real implementation.
  - Verify whether responses are hardcoded or derived from real execution of `BotManager`, `api_server`, SQLite database, etc.
- Inspect `tools/soak_test_lifecycle.py`:
  - Verify ctypes declarations (`GetProcessMemoryInfo`, `PROCESS_MEMORY_COUNTERS_EX`, `GetProcessHandleCount`).
  - Verify that memory metrics (`WorkingSetSize`, `PrivateUsage`, `tracemalloc`) are actual native calls reading real OS memory and Python heap.
  - Verify mathematical regression formulas (ordinary least squares slope and intercept) are genuinely computed over measured cycle data.

### Step 3: Empirical Execution Validation
- Execute `python tests/test_mandatory_scenarios.py` in PowerShell. Expected result: 18/18 PASS with OK status.
- Execute `python tests/run_all_tests.py` in PowerShell. Expected result: 30/30 PASS with OK status.
- Execute an independent soak test verification run: `python tools/soak_test_lifecycle.py --cycles 3 --bots 3` to verify live execution, memory measurement, and slope computation.
- Verify regression tests: `python tests/test_challenger_m4_stress.py`, `python tests/test_memory_cpu_m4.py`, `python tests/test_live_operations_m3.py`.

### Step 4: Adversarial Stress-Testing & Integrity Verdict
- Test edge cases in `test_mandatory_scenarios.py` and `soak_test_lifecycle.py`.
- Formulate verdict (CLEAN vs INTEGRITY VIOLATION) with evidence chain.

## 3. Files & Commands Detailed (الملفات والسطور أو الأوامر التي ستُنفذ بالتفصيل مع النتيجة المتوقعة)

| Order | Command / Action | Target Files | Expected Result |
|-------|------------------|--------------|-----------------|
| 1 | `git status --porcelain` | Workspace | Confirm no uncommitted modifications to prohibited files |
| 2 | Hash verification command | Prohibited files | Confirm exact match with git baseline |
| 3 | Static inspection | `tests/test_mandatory_scenarios.py` | Genuine assertions, 18 scenarios |
| 4 | Static inspection | `tools/soak_test_lifecycle.py` | Native PSAPI ctypes, tracemalloc, genuine OLS regression |
| 5 | `python tests/test_mandatory_scenarios.py` | Test suite | 18 tests run, 18 passed, 0 failures |
| 6 | `python tests/run_all_tests.py` | Unified test suite | 30 tests run, 30 passed, 0 failures |
| 7 | `python tools/soak_test_lifecycle.py --cycles 3 --bots 3` | Soak harness | Live execution, PASS verdict, valid slope calculation |
| 8 | Handoff generation | `e:\osmanli\.agents\teamwork\auditor_p2_m5\handoff.md` | Complete 5-component handoff report with forensic verdict |
