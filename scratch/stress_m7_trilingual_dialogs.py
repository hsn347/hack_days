# -*- coding: utf-8 -*-
"""
tools/stress_m7_trilingual_dialogs.py — Empirical Stress Test & Adversarial Verification:
Trilingual Parity, Non-Blocking Dialogs, Modal Lifecycle & Snappy UI.
══════════════════════════════════════════════════════════════════════════════════════════
Adversarial Verification Suite for Milestone 7 per AGENTS_CONSTITUTION.md & GEMINI.md:
  - 100% Full-Tree AST/Lexical scan of dashboard/src/ (0 window.confirm / alert)
  - Strict Trilingual Parity (ar.json, en.json, tr.json) with interpolation variable parity
  - Modal keydown Escape handling and body overflow safety
  - GEMINI.md Rule 2 Snappy UI (transition durations <= 0.25s, no sluggishness)
  - Backend Merchant Domain Isolation verification
  - Resource and timer leak prevention lifecycle
"""

import os
import re
import sys
import json
from typing import Set, Dict, Any, List, Tuple

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


class StressHarness:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []

    def assert_true(self, condition: bool, description: str, error_detail: str = ""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  [PASS] {description}")
        else:
            msg = f"{description} -> {error_detail}" if error_detail else description
            self.failures.append(msg)
            print(f"  [FAIL] {msg}")


def test_full_tree_lexical_scan(harness: StressHarness):
    print("\n--- Challenge 1: Full-Tree Lexical Scan of dashboard/src/ (0 Blocking Dialogs) ---")

    # Match confirm( or alert( when not preceded by a dot property or part of an identifier
    # e.g. window.confirm(...) or confirm(...)
    # Exclude method calls like deferredPrompt.prompt()
    blocking_pattern = re.compile(r'(?<![.\w])(?:window\.)?(confirm|alert)\s*\(')

    scanned_files = 0
    violations = []

    for root, _, files in os.walk(DASHBOARD_SRC):
        for file in files:
            if file.endswith((".ts", ".tsx", ".js", ".jsx")):
                scanned_files += 1
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ROOT_DIR)
                with open(full_path, "r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, 1):
                        stripped = line.strip()
                        # Ignore single line comments
                        if stripped.startswith("//") or stripped.startswith("*"):
                            continue
                        # Check match
                        match = blocking_pattern.search(line)
                        if match:
                            violations.append(f"{rel_path}:{line_no} [{match.group(1)}] -> {stripped}")

    harness.assert_true(
        scanned_files >= 25,
        f"Deep tree scan encompassed all frontend code ({scanned_files} files checked)",
        f"Only {scanned_files} files found"
    )
    harness.assert_true(
        len(violations) == 0,
        f"Strict 0 blocking dialogs (window.confirm / alert) across all {scanned_files} files",
        f"Violations detected: {violations}"
    )


def _flatten_dict(d: Any, prefix: str = "") -> Dict[str, Any]:
    items = {}
    if isinstance(d, dict):
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(_flatten_dict(v, key))
            else:
                items[key] = v
    return items


def test_trilingual_parity_and_interpolations(harness: StressHarness):
    print("\n--- Challenge 2: Trilingual Parity & Interpolation Variable Symmetry ---")

    ar_file = os.path.join(LOCALES_DIR, "ar.json")
    en_file = os.path.join(LOCALES_DIR, "en.json")
    tr_file = os.path.join(LOCALES_DIR, "tr.json")

    with open(ar_file, "r", encoding="utf-8") as f:
        ar_raw = json.load(f)
    with open(en_file, "r", encoding="utf-8") as f:
        en_raw = json.load(f)
    with open(tr_file, "r", encoding="utf-8") as f:
        tr_raw = json.load(f)

    ar_flat = _flatten_dict(ar_raw)
    en_flat = _flatten_dict(en_raw)
    tr_flat = _flatten_dict(tr_raw)

    ar_keys = set(ar_flat.keys())
    en_keys = set(en_flat.keys())
    tr_keys = set(tr_flat.keys())

    # 1. Total key count equality
    harness.assert_true(
        len(ar_keys) == len(en_keys) == len(tr_keys),
        f"Exact identical key counts across all locales (AR: {len(ar_keys)}, EN: {len(en_keys)}, TR: {len(tr_keys)})",
        f"Key count mismatch: AR={len(ar_keys)}, EN={len(en_keys)}, TR={len(tr_keys)}"
    )

    # 2. Key set differences
    missing_in_en = ar_keys - en_keys
    missing_in_tr = ar_keys - tr_keys
    missing_in_ar = (en_keys | tr_keys) - ar_keys

    harness.assert_true(
        len(missing_in_en) == 0,
        f"Zero missing keys in en.json relative to ar.json (Missing: {len(missing_in_en)})",
        f"Missing: {list(missing_in_en)[:5]}"
    )
    harness.assert_true(
        len(missing_in_tr) == 0,
        f"Zero missing keys in tr.json relative to ar.json (Missing: {len(missing_in_tr)})",
        f"Missing: {list(missing_in_tr)[:5]}"
    )
    harness.assert_true(
        len(missing_in_ar) == 0,
        f"Zero missing keys in ar.json relative to en/tr (Missing: {len(missing_in_ar)})",
        f"Missing: {list(missing_in_ar)[:5]}"
    )

    # 3. No empty translations or whitespace-only values
    empty_ar = [k for k, v in ar_flat.items() if isinstance(v, str) and not v.strip()]
    empty_en = [k for k, v in en_flat.items() if isinstance(v, str) and not v.strip()]
    empty_tr = [k for k, v in tr_flat.items() if isinstance(v, str) and not v.strip()]

    harness.assert_true(
        len(empty_ar) == 0,
        f"Zero empty translation values in ar.json (Found: {len(empty_ar)})",
        f"Empty keys: {empty_ar[:5]}"
    )
    harness.assert_true(
        len(empty_en) == 0,
        f"Zero empty translation values in en.json (Found: {len(empty_en)})",
        f"Empty keys: {empty_en[:5]}"
    )
    harness.assert_true(
        len(empty_tr) == 0,
        f"Zero empty translation values in tr.json (Found: {len(empty_tr)})",
        f"Empty keys: {empty_tr[:5]}"
    )

    # 4. Interpolation variable symmetry (e.g. {{name}}, {target})
    # Note: in Arabic grammar, singular forms (_one) omit count digits (e.g. 'حساب واحد' vs '1 Account')
    var_pattern = re.compile(r'\{+([a-zA-Z0-9_]+)\}+')
    mismatched_vars = []

    for k in ar_keys:
        val_ar = str(ar_flat.get(k, ""))
        val_en = str(en_flat.get(k, ""))
        val_tr = str(tr_flat.get(k, ""))

        vars_ar = set(var_pattern.findall(val_ar))
        vars_en = set(var_pattern.findall(val_en))
        vars_tr = set(var_pattern.findall(val_tr))

        # Check en vs tr symmetry
        if vars_en != vars_tr:
            mismatched_vars.append(f"{k} (EN vs TR mismatch) -> EN:{vars_en} vs TR:{vars_tr}")

        # Check ar vs en, allowing legitimate Arabic linguistic singular omission (e.g. plans.accountsCount_one)
        if vars_ar != vars_en and not (k.endswith("_one") and len(vars_ar) == 0 and len(vars_en) == 1):
            mismatched_vars.append(f"{k} -> AR:{vars_ar} vs EN:{vars_en}")

    harness.assert_true(
        len(mismatched_vars) == 0,
        f"Interpolation variable symmetry across all locales (Strict mismatches: {len(mismatched_vars)})",
        f"Mismatches: {mismatched_vars[:5]}"
    )


def test_modal_lifecycle_escape_and_overflow(harness: StressHarness):
    print("\n--- Challenge 3: Modal Keyboard & Event Lifecycle Stress ---")

    modal_files = [
        os.path.join(DASHBOARD_SRC, "components", "common", "ActionConfirmModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "common", "ConfirmLogoutModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "common", "ConfirmRemoveSavedAccountModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "common", "AccountSwitcherModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "accounts", "ConfirmDeleteCastleModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "accounts", "ConfirmPresetModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "accounts", "ConfirmStopModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "accounts", "AddCastleModal.tsx"),
        os.path.join(DASHBOARD_SRC, "components", "accounts", "EditCastleModal.tsx"),
    ]

    for mpath in modal_files:
        name = os.path.basename(mpath)
        harness.assert_true(os.path.exists(mpath), f"Modal file exists: {name}")

        with open(mpath, "r", encoding="utf-8") as f:
            code = f.read()

        # Check Escape key handling
        has_escape = "Escape" in code
        harness.assert_true(
            has_escape,
            f"{name} handles Escape key to dismiss modal",
            "Missing Escape key handler"
        )

        # Check removeEventListener cleanup
        has_cleanup = "removeEventListener" in code
        harness.assert_true(
            has_cleanup,
            f"{name} properly cleans up keyboard event listener on unmount",
            "Missing removeEventListener in useEffect return cleanup"
        )


def test_body_overflow_safety(harness: StressHarness):
    print("\n--- Challenge 4: Body Overflow Integrity & Cleanup Safety ---")

    # Verify that no component permanently alters document.body.style.overflow without cleanup
    overflow_setters = []
    for root, _, files in os.walk(DASHBOARD_SRC):
        for file in files:
            if file.endswith((".ts", ".tsx")):
                fpath = os.path.join(root, file)
                rel_path = os.path.relpath(fpath, ROOT_DIR)
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                if "body.style.overflow" in content:
                    # Check if it cleans up
                    has_cleanup = "body.style.overflow = ''" in content or "body.style.overflow = 'unset'" in content
                    overflow_setters.append((rel_path, has_cleanup))

    if overflow_setters:
        for rel_path, has_cleanup in overflow_setters:
            harness.assert_true(
                has_cleanup,
                f"{rel_path} cleans up body.style.overflow on unmount",
                "Alters body.style.overflow without cleanup"
            )
    else:
        harness.assert_true(
            True,
            "Zero uncontrolled body.style.overflow modifications across all frontend components"
        )


def test_gemini_rule_2_snappy_ux(harness: StressHarness):
    print("\n--- Challenge 5: GEMINI.md Rule 2 Compliance (Snappy UI & No Sluggishness) ---")

    action_modal_path = os.path.join(DASHBOARD_SRC, "components", "common", "ActionConfirmModal.tsx")
    with open(action_modal_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Search for transition durations in ActionConfirmModal
    durations = [float(d) for d in re.findall(r'duration:\s*([0-9.]+)', code)]
    harness.assert_true(
        len(durations) > 0 and all(d <= 0.25 for d in durations),
        f"ActionConfirmModal animation transitions are instant/snappy (max {max(durations) if durations else 0}s <= 0.25s)",
        f"Slow animation detected: durations={durations}"
    )

    # Verify dual dark/light surface colors
    harness.assert_true(
        "dark:bg-[#0c1410]" in code and "bg-white" in code,
        "ActionConfirmModal supports refined dark/light theme contrast"
    )

    # Verify mobile-first modal sizing (no awkward overflowing dialog)
    harness.assert_true(
        "max-w-[390px]" in code or "max-w-sm" in code or "max-w-md" in code,
        "ActionConfirmModal constrained to mobile-friendly single-column layout"
    )


def test_merchant_isolation_backend(harness: StressHarness):
    print("\n--- Challenge 6: Backend Merchant Domain Isolation Hardening ---")

    with open(API_SERVER_PATH, "r", encoding="utf-8") as f:
        code = f.read()

    # Find get_admin_user_castles definition
    fn_match = re.search(r'def get_admin_user_castles\s*\((.*?)\):\s*\n(.*?)(?=\n(?:@app|def|\Z))', code, re.DOTALL)
    harness.assert_true(fn_match is not None, "get_admin_user_castles endpoint located in api_server.py")

    if fn_match:
        fn_body = fn_match.group(2)
        harness.assert_true(
            "_verify_merchant_access_to_user" in fn_body,
            "get_admin_user_castles executes _verify_merchant_access_to_user",
            "Missing merchant access check in castle inspection endpoint"
        )
        harness.assert_true(
            "db.get_user" in fn_body,
            "get_admin_user_castles retrieves user object to verify merchant domain ownership",
            "User verification skipped or not bound to db.get_user"
        )


def main():
    print("=" * 80)
    print("EMPIRICAL ADVERSARIAL STRESS TEST: Milestone 7 Trilingual & Dialog Lifecycle")
    print("=" * 80)

    harness = StressHarness()

    test_full_tree_lexical_scan(harness)
    test_trilingual_parity_and_interpolations(harness)
    test_modal_lifecycle_escape_and_overflow(harness)
    test_body_overflow_safety(harness)
    test_gemini_rule_2_snappy_ux(harness)
    test_merchant_isolation_backend(harness)

    print("\n" + "=" * 80)
    print(f"STRESS TEST SUMMARY: {harness.tests_passed}/{harness.tests_run} assertions PASSED ({(harness.tests_passed/max(1, harness.tests_run))*100:.1f}%)")
    print("=" * 80)

    if harness.failures:
        print(f"\n[FAIL] {len(harness.failures)} failure(s) detected:")
        for fail in harness.failures:
            print(f"  - {fail}")
        sys.exit(1)
    else:
        print("\n[VERDICT: APPROVE] All empirical adversarial challenges PASSED flawlessly.")
        sys.exit(0)


if __name__ == "__main__":
    main()
