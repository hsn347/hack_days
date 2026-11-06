# -*- coding: utf-8 -*-
"""
tests/run_all_tests.py — Unified 4-Tier Test Suite Runner with Detailed Tier Reporting
══════════════════════════════════════════════════════════════════════════════════════
Executes both test_e2e_platform.py and test_database_performance.py, categorizes tests
into Tiers 1-4, measures individual and aggregated timings, and prints a comprehensive
compliance report.
"""

import os
import sys
import time
import unittest
from typing import Dict, List, Any

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tests.test_e2e_platform import (
    TestTier1FeatureCoverage,
    TestTier3CrossFeatureConcurrency,
    TestTier4RealWorldWorkflows,
)
from tests.test_database_performance import (
    TestTier1DatabaseQueries,
    TestTier2BoundaryAndStress,
)


class TierTrackingResult(unittest.TestResult):
    """Custom TestResult tracking per-tier metrics and execution timings."""

    def __init__(self):
        super().__init__()
        self.tier_records: Dict[str, List[Dict[str, Any]]] = {
            "Tier 1 (Feature Coverage)": [],
            "Tier 2 (Boundary & Corner Cases)": [],
            "Tier 3 (Cross-Feature Combinations)": [],
            "Tier 4 (Real-World Workflows)": [],
            "Other": [],
        }
        self.test_start_time = 0.0

    def _get_tier(self, test: unittest.TestCase) -> str:
        name = test._testMethodName
        if "t1" in name.lower():
            return "Tier 1 (Feature Coverage)"
        elif "t2" in name.lower():
            return "Tier 2 (Boundary & Corner Cases)"
        elif "t3" in name.lower():
            return "Tier 3 (Cross-Feature Combinations)"
        elif "t4" in name.lower():
            return "Tier 4 (Real-World Workflows)"
        return "Other"

    def startTest(self, test: unittest.TestCase):
        super().startTest(test)
        self.test_start_time = time.perf_counter()

    def addSuccess(self, test: unittest.TestCase):
        super().addSuccess(test)
        elapsed = time.perf_counter() - self.test_start_time
        tier = self._get_tier(test)
        doc = (test._testMethodDoc or "").strip()
        self.tier_records[tier].append({
            "name": test._testMethodName,
            "doc": doc,
            "status": "PASS",
            "elapsed_ms": elapsed * 1000.0,
            "error": None,
        })
        print(f"  [PASS] [{elapsed*1000.0:6.1f}ms] {test._testMethodName} - {doc}")

    def addFailure(self, test: unittest.TestCase, err):
        super().addFailure(test, err)
        elapsed = time.perf_counter() - self.test_start_time
        tier = self._get_tier(test)
        doc = (test._testMethodDoc or "").strip()
        self.tier_records[tier].append({
            "name": test._testMethodName,
            "doc": doc,
            "status": "FAIL",
            "elapsed_ms": elapsed * 1000.0,
            "error": str(err[1]),
        })
        print(f"  [FAIL] [{elapsed*1000.0:6.1f}ms] {test._testMethodName} - {doc}")

    def addError(self, test: unittest.TestCase, err):
        super().addError(test, err)
        elapsed = time.perf_counter() - self.test_start_time
        tier = self._get_tier(test)
        doc = (test._testMethodDoc or "").strip()
        self.tier_records[tier].append({
            "name": test._testMethodName,
            "doc": doc,
            "status": "ERROR",
            "elapsed_ms": elapsed * 1000.0,
            "error": str(err[1]),
        })
        print(f"  [ERROR] [{elapsed*1000.0:6.1f}ms] {test._testMethodName} - {doc}")


def main() -> int:
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    # Add all test classes in order of tiers
    suite.addTests(loader.loadTestsFromTestCase(TestTier1FeatureCoverage))
    suite.addTests(loader.loadTestsFromTestCase(TestTier1DatabaseQueries))
    suite.addTests(loader.loadTestsFromTestCase(TestTier2BoundaryAndStress))
    suite.addTests(loader.loadTestsFromTestCase(TestTier3CrossFeatureConcurrency))
    suite.addTests(loader.loadTestsFromTestCase(TestTier4RealWorldWorkflows))

    total_planned = suite.countTestCases()

    print("\n" + "=" * 78)
    print("Osmanli Platform Performance & Concurrency - 4-Tier Test Runner")
    print(f"   Total Test Cases Loaded : {total_planned}")
    print(f"   Execution Mode          : 100% Hermetic Isolated SQLite (Zero Production Impact)")
    print(f"   Timestamp               : {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print("=" * 78 + "\n")

    result = TierTrackingResult()
    start_total = time.perf_counter()

    for test_case in suite:
        test_case.run(result)

    total_duration = time.perf_counter() - start_total

    print("\n" + "=" * 78)
    print("4-TIER COMPLIANCE & COVERAGE SUMMARY TABLE")
    print("=" * 78)
    print(f"{'Tier Name':<38} | {'Total':<6} | {'Pass':<6} | {'Fail':<6} | {'Avg Time':<10}")
    print("-" * 78)

    grand_total = 0
    grand_pass = 0
    grand_fail = 0

    for tier_name, records in result.tier_records.items():
        if not records and tier_name == "Other":
            continue
        t_total = len(records)
        t_pass = sum(1 for r in records if r["status"] == "PASS")
        t_fail = t_total - t_pass
        avg_time = (sum(r["elapsed_ms"] for r in records) / t_total) if t_total > 0 else 0.0

        grand_total += t_total
        grand_pass += t_pass
        grand_fail += t_fail

        print(f"{tier_name:<38} | {t_total:<6} | {t_pass:<6} | {t_fail:<6} | {avg_time:6.1f} ms")

    print("-" * 78)
    pass_pct = (grand_pass / grand_total * 100.0) if grand_total > 0 else 0.0
    print(f"{'OVERALL SUITE TOTALS':<38} | {grand_total:<6} | {grand_pass:<6} | {grand_fail:<6} | Pass: {pass_pct:.1f}%")
    print(f"Total Duration: {total_duration:.2f} seconds")
    print("=" * 78)

    if grand_fail == 0:
        print("\n>>> ALL TESTS PASSED SUCCESSFULLY! Ready to publish TEST_READY.md.\n")
        return 0
    else:
        print(f"\n>>> TEST RUN FAILED with {grand_fail} failures/errors.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
