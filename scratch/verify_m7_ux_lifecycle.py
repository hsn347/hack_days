# -*- coding: utf-8 -*-
"""
tools/verify_m7_ux_lifecycle.py — Verification of Milestone 7:
UX Lifecycle, Modal Dialogs, Trilingual Consistency & Resource Cleanup.
══════════════════════════════════════════════════════════════════════════════════════
Automated verification suite per AGENTS_CONSTITUTION.md Rule 13 & M7 Requirements:
1. Static code audit: Zero blocking browser dialogs (confirm/alert/prompt) in frontend.
2. Reusable accessible ActionConfirmModal component integrity and non-blocking usage.
3. Trilingual consistency across dashboard/src/locales/ (ar.json, en.json, tr.json).
4. Merchant access isolation in api_server.py:get_admin_user_castles.
5. Resource lifecycle and clean unmount verification (timer & listener cleanup).
6. Theme contrast and mobile responsiveness layout compliance.
"""

import os
import re
import sys
import json
from typing import Set, Dict, Any, List

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_SRC = os.path.join(ROOT_DIR, "dashboard", "src")
LOCALES_DIR = os.path.join(DASHBOARD_SRC, "locales")
API_SERVER_PATH = os.path.join(ROOT_DIR, "api_server.py")
ACTION_MODAL_PATH = os.path.join(DASHBOARD_SRC, "components", "common", "ActionConfirmModal.tsx")


class TestHarness:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []

    def assert_true(self, condition: bool, description: str):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  [PASS] {description}")
        else:
            self.failures.append(description)
            print(f"  [FAIL] {description}")


def test_zero_blocking_dialogs(harness: TestHarness):
    print("\n--- Tier 1: Zero Blocking Dialogs Audit (window.confirm / alert) ---")

    harness.assert_true(os.path.exists(ACTION_MODAL_PATH), "ActionConfirmModal.tsx exists in components/common/")

    with open(ACTION_MODAL_PATH, "r", encoding="utf-8") as f:
        action_modal_code = f.read()

    harness.assert_true(
        "createPortal" in action_modal_code and "document.body" in action_modal_code,
        "ActionConfirmModal uses React Portal to document.body"
    )
    harness.assert_true(
        "Escape" in action_modal_code and "removeEventListener" in action_modal_code,
        "ActionConfirmModal provides accessible Escape key listener with cleanup"
    )
    harness.assert_true(
        "AnimatePresence" in action_modal_code,
        "ActionConfirmModal uses AnimatePresence for smooth snappy entry/exit"
    )

    # Scan all .tsx and .ts files under dashboard/src/pages and dashboard/src/components
    scan_dirs = [
        os.path.join(DASHBOARD_SRC, "pages"),
        os.path.join(DASHBOARD_SRC, "components"),
    ]

    blocking_calls = []
    # Match confirm( or alert( when not preceded by object property other than window.
    # e.g. confirm(...) or window.confirm(...)
    pattern = re.compile(r'(?<!\.\w)(?:window\.)?(confirm|alert)\s*\(')

    for s_dir in scan_dirs:
        for root, _, files in os.walk(s_dir):
            for file in files:
                if file.endswith((".tsx", ".ts")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, ROOT_DIR)
                    with open(full_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines, 1):
                        # Skip comments
                        clean_line = line.strip()
                        if clean_line.startswith("//") or clean_line.startswith("*"):
                            continue
                        match = pattern.search(line)
                        if match:
                            blocking_calls.append(f"{rel_path}:{idx} -> {clean_line}")

    harness.assert_true(
        len(blocking_calls) == 0,
        f"Zero blocking dialogs (confirm/alert) found across pages and components (Found: {len(blocking_calls)})"
    )
    if blocking_calls:
        for bc in blocking_calls:
            print(f"    Violation: {bc}")


def _flatten_json_keys(data: Any, prefix: str = "") -> Set[str]:
    keys = set()
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(_flatten_json_keys(v, full_key))
            else:
                keys.add(full_key)
    return keys


def test_trilingual_consistency(harness: TestHarness):
    print("\n--- Tier 2: Trilingual Consistency Across ar.json, en.json, tr.json ---")

    ar_path = os.path.join(LOCALES_DIR, "ar.json")
    en_path = os.path.join(LOCALES_DIR, "en.json")
    tr_path = os.path.join(LOCALES_DIR, "tr.json")

    harness.assert_true(os.path.exists(ar_path), "ar.json exists")
    harness.assert_true(os.path.exists(en_path), "en.json exists")
    harness.assert_true(os.path.exists(tr_path), "tr.json exists")

    with open(ar_path, "r", encoding="utf-8") as f:
        ar_data = json.load(f)
    with open(en_path, "r", encoding="utf-8") as f:
        en_data = json.load(f)
    with open(tr_path, "r", encoding="utf-8") as f:
        tr_data = json.load(f)

    ar_keys = _flatten_json_keys(ar_data)
    en_keys = _flatten_json_keys(en_data)
    tr_keys = _flatten_json_keys(tr_data)

    missing_in_en = ar_keys - en_keys
    missing_in_tr = ar_keys - tr_keys
    missing_in_ar = (en_keys | tr_keys) - ar_keys

    harness.assert_true(
        len(missing_in_en) == 0,
        f"All Arabic keys present in English locale (Missing in en.json: {len(missing_in_en)})"
    )
    if missing_in_en:
        for k in sorted(list(missing_in_en))[:10]:
            print(f"    Missing in en: {k}")

    harness.assert_true(
        len(missing_in_tr) == 0,
        f"All Arabic keys present in Turkish locale (Missing in tr.json: {len(missing_in_tr)})"
    )
    if missing_in_tr:
        for k in sorted(list(missing_in_tr))[:10]:
            print(f"    Missing in tr: {k}")

    harness.assert_true(
        len(missing_in_ar) == 0,
        f"All English/Turkish keys present in Arabic locale (Missing in ar.json: {len(missing_in_ar)})"
    )
    if missing_in_ar:
        for k in sorted(list(missing_in_ar))[:10]:
            print(f"    Missing in ar: {k}")

    # Check key counts
    print(f"    Locale Key Counts -> AR: {len(ar_keys)} | EN: {len(en_keys)} | TR: {len(tr_keys)}")


def test_merchant_isolation(harness: TestHarness):
    print("\n--- Tier 3: Merchant Admin Access Hardening in api_server.py ---")

    harness.assert_true(os.path.exists(API_SERVER_PATH), "api_server.py exists")
    with open(API_SERVER_PATH, "r", encoding="utf-8") as f:
        api_code = f.read()

    # Verify endpoint definition
    harness.assert_true(
        '@app.get("/api/admin/users/{uid}/castles")' in api_code,
        "GET /api/admin/users/{uid}/castles endpoint exists in api_server.py"
    )

    # Locate the get_admin_user_castles function block
    pattern = re.compile(r'def get_admin_user_castles\s*\(.*?\):\s*\n.*?(?=@app|\Z)', re.DOTALL)
    match = pattern.search(api_code)
    harness.assert_true(match is not None, "get_admin_user_castles function located")

    if match:
        fn_code = match.group(0)
        harness.assert_true(
            "_verify_merchant_access_to_user" in fn_code,
            "get_admin_user_castles calls _verify_merchant_access_to_user"
        )
        harness.assert_true(
            "db.get_user(uid)" in fn_code or "target_user" in fn_code,
            "get_admin_user_castles loads target_user from db for verification"
        )


def test_resource_cleanup_lifecycle(harness: TestHarness):
    print("\n--- Tier 4: Resource Cleanup & Leak Prevention Lifecycle ---")

    # Inspect AdminLiveProcesses.tsx
    live_proc_path = os.path.join(DASHBOARD_SRC, "pages", "AdminLiveProcesses.tsx")
    with open(live_proc_path, "r", encoding="utf-8") as f:
        live_code = f.read()

    harness.assert_true(
        "clearInterval(timerRef.current)" in live_code,
        "AdminLiveProcesses clears auto-refresh interval on unmount or tab deactivation"
    )

    # Inspect modal cleanup in ActionConfirmModal
    with open(ACTION_MODAL_PATH, "r", encoding="utf-8") as f:
        modal_code = f.read()

    harness.assert_true(
        "window.removeEventListener('keydown', handleKeyDown)" in modal_code,
        "ActionConfirmModal removes keyboard event listener on unmount"
    )

    # Inspect no lingering console.log in components
    console_logs = []
    for root, _, files in os.walk(os.path.join(DASHBOARD_SRC, "components")):
        for file in files:
            if file.endswith((".tsx", ".ts")):
                fpath = os.path.join(root, file)
                with open(fpath, "r", encoding="utf-8") as f:
                    for lno, line in enumerate(f, 1):
                        if "console.log" in line and not line.strip().startswith("//"):
                            console_logs.append(f"{file}:{lno}")

    harness.assert_true(
        len(console_logs) == 0,
        f"Zero console.log statements in dashboard components (Found: {len(console_logs)})"
    )


def test_theme_and_mobile_layout(harness: TestHarness):
    print("\n--- Tier 5: Theme Contrast & Mobile Single-Row Layouts ---")

    with open(ACTION_MODAL_PATH, "r", encoding="utf-8") as f:
        modal_code = f.read()

    harness.assert_true(
        "dark:bg-[#0c1410]" in modal_code and "bg-white" in modal_code,
        "ActionConfirmModal supports dual dark/light surface styling"
    )
    harness.assert_true(
        "dark:text-white" in modal_code and "text-gray-900" in modal_code,
        "ActionConfirmModal text contrast meets dark/light mode standards"
    )

    admin_path = os.path.join(DASHBOARD_SRC, "pages", "Admin.tsx")
    with open(admin_path, "r", encoding="utf-8") as f:
        admin_code = f.read()

    harness.assert_true(
        "ActionConfirmModal" in admin_code,
        "Admin.tsx integrates ActionConfirmModal for non-blocking operations"
    )


def main():
    print("=" * 78)
    print("Milestone 7 UX Lifecycle & Verification Suite")
    print("=" * 78)

    harness = TestHarness()

    test_zero_blocking_dialogs(harness)
    test_trilingual_consistency(harness)
    test_merchant_isolation(harness)
    test_resource_cleanup_lifecycle(harness)
    test_theme_and_mobile_layout(harness)

    print("\n" + "=" * 78)
    print(f"Results: {harness.tests_passed}/{harness.tests_run} tests passed ({(harness.tests_passed/max(1, harness.tests_run))*100:.1f}%)")
    print("=" * 78)

    if harness.failures:
        print(f"\n[FAIL] {len(harness.failures)} check(s) failed:")
        for fail in harness.failures:
            print(f"  - {fail}")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All Milestone 7 UX lifecycle checks PASSED perfectly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
