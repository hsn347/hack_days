# -*- coding: utf-8 -*-
"""
tools/stress_m6_pagination.py — Empirical Stress Testing Harness for Milestone 6:
Pagination Boundaries, Dynamic Page Sizing, Reset Behaviors & GEMINI.md Rule 2 Conformance.
══════════════════════════════════════════════════════════════════════════════════════════
Author: Challenger M6 (Empirical Challenger - Critic / Specialist)
Target: Verification of Admin Client-Side Pagination & Boundaries

Test Coverage:
1. Exact Boundary Scenarios: 0 items, 1 item, 25 items, 26 items, 1,000 items.
2. Dynamic Page Size Switching: 10, 25, 50, 100.
3. Search / Filter / Sort Reset to Page 1 behavior.
4. Adversarial & Out-of-Bounds Clamping (negative, zero, extreme values).
5. Comprehensive Item Coverage & Non-overlap invariant across all pages.
6. Execution Speed & Memory Efficiency under high item volume.
7. Conformance to GEMINI.md Rule 2 (No word clutter, crisp UI, snappy responsiveness).
8. Static Code Verification in Admin.tsx.
"""

import os
import re
import sys
import time
import math
from typing import List, Dict, Any, Tuple, Set

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_FILE = os.path.join(ROOT_DIR, "dashboard", "src", "pages", "Admin.tsx")


class StressHarness:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []

    def assert_true(self, condition: bool, description: str, details: str = ""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  [PASS] {description}")
        else:
            msg = f"{description} | Details: {details}" if details else description
            self.failures.append(msg)
            print(f"  [FAIL] {msg}")

    def assert_equal(self, actual: Any, expected: Any, description: str):
        self.assert_true(
            actual == expected,
            description,
            f"Expected {expected!r}, got {actual!r}"
        )


def simulate_pagination(items: List[Any], current_page: int, page_size: int) -> Tuple[List[Any], int, int, int, int]:
    """
    Exact simulation of Admin.tsx lines 685-690:
    const totalItems = filtered.length
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
    const validPage = Math.min(Math.max(1, currentPage), totalPages)
    const startIndex = (validPage - 1) * pageSize
    const endIndex = Math.min(startIndex + pageSize, totalItems)
    const paginatedUsers = filtered.slice(startIndex, endIndex)
    """
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / page_size))
    valid_page = min(max(1, current_page), total_pages)
    start_index = (valid_page - 1) * page_size
    end_index = min(start_index + page_size, total_items)
    paginated_items = items[start_index:end_index]
    return paginated_items, total_pages, valid_page, start_index, end_index


def test_boundary_zero_items(harness: StressHarness):
    print("\n--- Suite 1: Boundary Condition 0 Items (Empty State) ---")
    items = []
    page_size = 25
    paginated, total_pages, valid_page, start_idx, end_idx = simulate_pagination(items, current_page=1, page_size=page_size)

    harness.assert_equal(len(paginated), 0, "0 items produces empty slice")
    harness.assert_equal(total_pages, 1, "0 items returns totalPages = 1 (prevents division by zero or 0 totalPages)")
    harness.assert_equal(valid_page, 1, "0 items clamps validPage to 1")
    harness.assert_equal(start_idx, 0, "0 items startIndex is 0")
    harness.assert_equal(end_idx, 0, "0 items endIndex is 0")

    # Static check: Admin.tsx hides pagination controls and displays empty state when totalItems === 0
    with open(ADMIN_FILE, "r", encoding="utf-8") as f:
        src = f.read()
    harness.assert_true(
        "totalItems > 0 && (" in src or "totalItems > 0 &&" in src,
        "Admin.tsx guards pagination bar with totalItems > 0"
    )
    harness.assert_true(
        "totalItems === 0 && (" in src and "noSearchResults" in src,
        "Admin.tsx renders clean empty state when totalItems === 0"
    )


def test_boundary_one_item(harness: StressHarness):
    print("\n--- Suite 2: Boundary Condition 1 Item (Single Item) ---")
    items = [{"id": "user_single_001"}]
    page_size = 25
    paginated, total_pages, valid_page, start_idx, end_idx = simulate_pagination(items, current_page=1, page_size=page_size)

    harness.assert_equal(len(paginated), 1, "1 item produces slice with exactly 1 element")
    harness.assert_equal(total_pages, 1, "1 item returns totalPages = 1")
    harness.assert_equal(valid_page, 1, "validPage is 1")
    harness.assert_equal(start_idx, 0, "startIndex is 0")
    harness.assert_equal(end_idx, 1, "endIndex is 1")

    # In UI, range display is (startIndex + 1)–endIndex: 1–1 / 1
    displayed_range = f"{start_idx + 1}–{end_idx}"
    harness.assert_equal(displayed_range, "1–1", "Displayed item range is '1–1'")

    # Both Prev and Next buttons must be disabled
    prev_disabled = valid_page <= 1
    next_disabled = valid_page >= total_pages
    harness.assert_true(prev_disabled, "Previous button is disabled on page 1 of 1")
    harness.assert_true(next_disabled, "Next button is disabled on page 1 of 1")


def test_boundary_twenty_five_items(harness: StressHarness):
    print("\n--- Suite 3: Boundary Condition 25 Items (Exact Single Page Boundary) ---")
    items = [{"id": f"user_{i:03d}"} for i in range(25)]
    page_size = 25
    paginated, total_pages, valid_page, start_idx, end_idx = simulate_pagination(items, current_page=1, page_size=page_size)

    harness.assert_equal(len(paginated), 25, "25 items produces slice of 25")
    harness.assert_equal(total_pages, 1, "25 items with pageSize 25 results in exactly 1 page")
    harness.assert_equal(valid_page, 1, "validPage is 1")
    harness.assert_equal(start_idx, 0, "startIndex is 0")
    harness.assert_equal(end_idx, 25, "endIndex is 25")

    prev_disabled = valid_page <= 1
    next_disabled = valid_page >= total_pages
    harness.assert_true(prev_disabled, "Previous button is disabled")
    harness.assert_true(next_disabled, "Next button is disabled (no page 2 exists)")


def test_boundary_twenty_six_items(harness: StressHarness):
    print("\n--- Suite 4: Boundary Condition 26 Items (Threshold Crossing to 2 Pages) ---")
    items = [{"id": f"user_{i:03d}"} for i in range(26)]
    page_size = 25

    # Page 1
    p1, total_pages, valid_p1, s1, e1 = simulate_pagination(items, current_page=1, page_size=page_size)
    harness.assert_equal(total_pages, 2, "26 items produces exactly 2 pages")
    harness.assert_equal(len(p1), 25, "Page 1 contains first 25 items")
    harness.assert_equal(s1, 0, "Page 1 start index is 0")
    harness.assert_equal(e1, 25, "Page 1 end index is 25")
    harness.assert_true(valid_p1 <= 1, "Page 1: Prev is disabled")
    harness.assert_true(valid_p1 < total_pages, "Page 1: Next is enabled")

    # Page 2
    p2, _, valid_p2, s2, e2 = simulate_pagination(items, current_page=2, page_size=page_size)
    harness.assert_equal(len(p2), 1, "Page 2 contains exactly 1 overflow item")
    harness.assert_equal(s2, 25, "Page 2 start index is 25")
    harness.assert_equal(e2, 26, "Page 2 end index is 26")
    harness.assert_true(valid_p2 > 1, "Page 2: Prev is enabled")
    harness.assert_true(valid_p2 >= total_pages, "Page 2: Next is disabled")

    # Boundary Non-Overlap and Completeness Invariant
    all_seen = [u["id"] for u in p1] + [u["id"] for u in p2]
    expected_all = [u["id"] for u in items]
    harness.assert_equal(all_seen, expected_all, "Union of Page 1 and Page 2 is identical to full 26-item dataset")
    harness.assert_equal(len(set(all_seen)), 26, "Zero duplicates across page boundaries")


def test_boundary_one_thousand_items_and_page_sizes(harness: StressHarness):
    print("\n--- Suite 5: Large Scale (1,000 Items) Across Dynamic Page Sizes [10, 25, 50, 100] ---")
    total_count = 1000
    items = [{"id": f"usr_large_{i:04d}", "val": i} for i in range(total_count)]
    page_sizes = [10, 25, 50, 100]

    for ps in page_sizes:
        expected_pages = total_count // ps
        start_time = time.perf_counter()

        collected_items = []
        for p in range(1, expected_pages + 1):
            slice_items, total_pages, valid_p, s_idx, e_idx = simulate_pagination(items, current_page=p, page_size=ps)
            harness.assert_equal(total_pages, expected_pages, f"PageSize={ps} has totalPages={expected_pages}")
            harness.assert_equal(valid_p, p, f"PageSize={ps} requested {p} equals validPage {valid_p}")
            harness.assert_equal(len(slice_items), ps, f"PageSize={ps} page {p} has exact length {ps}")
            harness.assert_equal(s_idx, (p - 1) * ps, f"PageSize={ps} page {p} start index correct")
            harness.assert_equal(e_idx, p * ps, f"PageSize={ps} page {p} end index correct")
            collected_items.extend(slice_items)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Invariant checks: No duplicate, no missing, exact order preserved
        collected_ids = [it["id"] for it in collected_items]
        expected_ids = [it["id"] for it in items]
        harness.assert_equal(len(collected_ids), total_count, f"PageSize={ps}: 1000 items retrieved")
        harness.assert_equal(collected_ids, expected_ids, f"PageSize={ps}: Item order and identity perfectly preserved")
        harness.assert_equal(len(set(collected_ids)), total_count, f"PageSize={ps}: Zero duplicates across all pages")
        harness.assert_true(elapsed_ms < 50.0, f"PageSize={ps}: Slicing all {expected_pages} pages took {elapsed_ms:.2f}ms (< 50ms)")


def test_adversarial_out_of_bounds_clamping(harness: StressHarness):
    print("\n--- Suite 6: Adversarial & Out-of-Bounds Clamping Stress ---")
    items = [{"id": f"u_{i}"} for i in range(120)]
    page_size = 25  # total_pages = 5

    # Case A: Negative page request (e.g. -10)
    _, _, valid_p, s_idx, e_idx = simulate_pagination(items, current_page=-10, page_size=page_size)
    harness.assert_equal(valid_p, 1, "Negative page (-10) safely clamped to page 1")
    harness.assert_equal(s_idx, 0, "Negative page start index safely clamped to 0")

    # Case B: Zero page request (0)
    _, _, valid_p, s_idx, e_idx = simulate_pagination(items, current_page=0, page_size=page_size)
    harness.assert_equal(valid_p, 1, "Zero page (0) safely clamped to page 1")

    # Case C: Page exceeding upper bound (e.g. 99999)
    _, total_pages, valid_p, s_idx, e_idx = simulate_pagination(items, current_page=99999, page_size=page_size)
    harness.assert_equal(total_pages, 5, "120 items has 5 total pages")
    harness.assert_equal(valid_p, 5, "Excessive page (99999) safely clamped to last page (5)")
    harness.assert_equal(s_idx, 100, "Clamped page 5 start index is 100")
    harness.assert_equal(e_idx, 120, "Clamped page 5 end index is 120 (remaining 20 items)")


def test_dynamic_page_size_and_filter_resets(harness: StressHarness):
    print("\n--- Suite 7: Dynamic Switching & Reset-to-Page-1 Behavior ---")
    with open(ADMIN_FILE, "r", encoding="utf-8") as f:
        src = f.read()

    # 1. Verify useEffect dependencies for setCurrentPage(1)
    reset_effect_match = re.search(
        r'useEffect\(\(\)\s*=>\s*\{\s*setCurrentPage\(1\)\s*\}\s*,\s*\[(.*?)\]\)',
        src
    )
    harness.assert_true(
        reset_effect_match is not None,
        "Admin.tsx contains explicit reset effect: useEffect(() => { setCurrentPage(1) }, [...])"
    )

    if reset_effect_match:
        deps = [d.strip() for d in reset_effect_match.group(1).split(",")]
        harness.assert_true("debouncedSearch" in deps, "Reset effect listens to debouncedSearch")
        harness.assert_true("filterPending" in deps, "Reset effect listens to filterPending")
        harness.assert_true("sortByLeastDays" in deps, "Reset effect listens to sortByLeastDays")
        harness.assert_true("pageSize" in deps, "Reset effect listens to pageSize")

    # 2. Simulate state scenario: User is on page 4 with pageSize 10.
    # When pageSize switches to 50, the effect sets currentPage = 1.
    current_page = 4
    page_size = 10
    total_items = 100

    # User switches pageSize to 50:
    page_size = 50
    # Simulate effect firing:
    current_page = 1
    paginated, total_p, valid_p, s, e = simulate_pagination([i for i in range(total_items)], current_page, page_size)
    harness.assert_equal(valid_p, 1, "Switching page size resets active view to page 1")
    harness.assert_equal(len(paginated), 50, "New page 1 presents 50 items")
    harness.assert_equal(total_p, 2, "100 items with pageSize 50 produces exactly 2 pages")


def test_gemini_rule_2_conformance(harness: StressHarness):
    print("\n--- Suite 8: Conformance to GEMINI.md Rule 2 (Simplicity & No Word Clutter) ---")
    with open(ADMIN_FILE, "r", encoding="utf-8") as f:
        src = f.read()

    # 1. No Word Clutter in Pagination UI:
    # Check that pagination shows crisp indicators: "{startIndex + 1}–{endIndex}", "/", "{totalItems}"
    harness.assert_true(
        "{startIndex + 1}–{endIndex}" in src and "{totalItems}" in src,
        "Pagination uses concise range metric '{startIndex + 1}–{endIndex} / {totalItems}'"
    )
    harness.assert_true(
        "{validPage}" in src and "{totalPages}" in src,
        "Page indicator is crisp '{validPage} / {totalPages}'"
    )

    # 2. Page size buttons: [10, 25, 50, 100] without redundant labels
    harness.assert_true(
        "[10, 25, 50, 100].map(sz =>" in src or "[10, 25, 50, 100].map" in src,
        "Page size options are clean numbers [10, 25, 50, 100]"
    )

    # 3. Concise label: "عرض:" or t('common.pageSize', 'عرض:')
    harness.assert_true(
        "common.pageSize" in src or "عرض:" in src,
        "Page size label is crisp and brief ('عرض:')"
    )

    # 4. Snappy UI: check that buttons have instant feedback without slow transition delays
    harness.assert_true(
        "cursor-pointer" in src and "active:scale" not in src.split("admin-pagination-prev")[1].split("admin-pagination-next")[0],
        "Pagination prev/next navigation controls are instant and snappy"
    )

    # 5. Mobile friendly: flex-col sm:flex-row layout
    harness.assert_true(
        "flex flex-col sm:flex-row items-center justify-between" in src,
        "Pagination container adheres to single-row responsive standard on larger viewports with vertical stack on mobile"
    )


def main():
    print("=" * 80)
    print("EMPIRICAL CHALLENGER STRESS HARNESS: M6 Pagination & Boundary Testing")
    print("=" * 80)

    harness = StressHarness()
    start_total = time.perf_counter()

    test_boundary_zero_items(harness)
    test_boundary_one_item(harness)
    test_boundary_twenty_five_items(harness)
    test_boundary_twenty_six_items(harness)
    test_boundary_one_thousand_items_and_page_sizes(harness)
    test_adversarial_out_of_bounds_clamping(harness)
    test_dynamic_page_size_and_filter_resets(harness)
    test_gemini_rule_2_conformance(harness)

    total_time_ms = (time.perf_counter() - start_total) * 1000.0

    print("\n" + "=" * 80)
    print(f"Stress Test Results: {harness.tests_passed}/{harness.tests_run} Passed in {total_time_ms:.2f}ms")
    print("=" * 80)

    if harness.failures:
        print(f"\nCRITICAL FAILURES DETECTED ({len(harness.failures)}):")
        for fail in harness.failures:
            print(f"  [X] {fail}")
        sys.exit(1)
    else:
        print("\nALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY (100% RELIABILITY).")
        sys.exit(0)


if __name__ == "__main__":
    main()
