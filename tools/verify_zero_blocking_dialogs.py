# -*- coding: utf-8 -*-
"""
tools/verify_zero_blocking_dialogs.py
Adversarial scan for blocking browser dialogs (confirm, alert, prompt, window.confirm, window.alert)
across the entire dashboard/src/ codebase.
"""
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DASHBOARD_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "src")

# Patterns to detect blocking dialogs
BLOCKING_PATTERNS = [
    (re.compile(r'\bwindow\.confirm\s*\('), "window.confirm(...)"),
    (re.compile(r'\bwindow\.alert\s*\('), "window.alert(...)"),
    (re.compile(r'\bwindow\.prompt\s*\('), "window.prompt(...)"),
    # Match confirm( or alert( when not preceded by '.' (e.g. not foo.alert or foo.confirm)
    (re.compile(r'(?<![.\w])confirm\s*\('), "confirm(...)"),
    (re.compile(r'(?<![.\w])alert\s*\('), "alert(...)"),
]

# Exceptions to ignore: comments, import statements, modal component names like ConfirmStopModal
IGNORE_PATTERNS = [
    re.compile(r'^\s*//'),                 # single line comment
    re.compile(r'^\s*\*'),                  # block comment continuation
    re.compile(r'/\*.*?\*/'),               # inline block comment
    re.compile(r'import\s+.*from'),         # import statements
    re.compile(r'interface\s+'),            # interface
    re.compile(r'type\s+'),                 # type declaration
]

def scan():
    violations = []
    total_files_scanned = 0

    valid_exts = ('.ts', '.tsx', '.js', '.jsx')

    for root, dirs, files in os.walk(DASHBOARD_SRC):
        for f in files:
            if not f.endswith(valid_exts):
                continue
            total_files_scanned += 1
            file_path = os.path.join(root, f)
            rel_path = os.path.relpath(file_path, DASHBOARD_SRC)

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as fp:
                lines = fp.readlines()

            for line_no, line in enumerate(lines, 1):
                clean_line = line.strip()
                # Check ignores
                if any(p.match(clean_line) for p in IGNORE_PATTERNS):
                    continue

                for pat, label in BLOCKING_PATTERNS:
                    if pat.search(line):
                        # Filter out false positives:
                        # e.g., AlertTriangle, showAlert state, alert( inside comment
                        # Check if it's really a call to alert(...) or confirm(...)
                        # If line has // before the match:
                        comment_pos = line.find('//')
                        match_pos = pat.search(line).start()
                        if comment_pos != -1 and comment_pos < match_pos:
                            continue
                        # If it's a function declaration like `function confirm(` or `confirm: () =>`
                        if re.search(r'\b(function|def|handleConfirm|onConfirm)\b', line):
                            # Check if the match is inside onConfirm(...)
                            if 'onConfirm' in line and not pat.search(line.replace('onConfirm', '')):
                                continue
                        violations.append((rel_path, line_no, label, clean_line))

    print(f"Scanned {total_files_scanned} files across {DASHBOARD_SRC}")
    if violations:
        print(f"❌ FOUND {len(violations)} BLOCKING DIALOG VIOLATIONS:")
        for rel_path, line_no, label, line in violations:
            print(f"  {rel_path}:{line_no} -> {label}")
            print(f"    Line: {line}")
        sys.exit(1)
    else:
        print("✅ CLEAN: 0 blocking dialogs (confirm/alert/prompt) found in dashboard/src/!")
        sys.exit(0)

if __name__ == '__main__':
    scan()
