import os
import re
import sys

report_path = r"e:\osmanli\docs\reports\adversarial_march_audit.md"

print("=" * 60)
print("INDEPENDENT FORENSIC INTEGRITY AUDIT")
print(f"Target: {report_path}")
print("=" * 60)

if not os.path.exists(report_path):
    print(f"CRITICAL VIOLATION: Report file does not exist at {report_path}")
    sys.exit(1)

with open(report_path, "r", encoding="utf-8") as f:
    content = f.read()

lines = content.splitlines()
total_lines = len(lines)
total_chars = len(content)
total_words = len(content.split())

print(f"Report Metrics: {total_lines} lines | {total_words} words | {total_chars} characters")

if total_lines < 500:
    print(f"CRITICAL VIOLATION: Report is suspiciously short ({total_lines} lines). Expected comprehensive report > 500 lines.")
    sys.exit(1)

violations = []

# 1. Check for Forbidden Shortcut Phrases
forbidden_phrases = [
    "إلخ",
    "بنفس الطريقة للملفات الأخرى",
    "باختصار",
]

found_forbidden = {}
for phrase in forbidden_phrases:
    matches = [i + 1 for i, line in enumerate(lines) if phrase in line]
    if matches:
        found_forbidden[phrase] = matches
        violations.append(f"Forbidden shortcut phrase '{phrase}' found at line(s): {matches[:5]}")

# 2. Check 10 Files Audited in Depth
files_to_check = [
    ("tasks/base_task.py", "BaseTask"),
    ("tasks/march_coordinator.py", "MarchCoordinator"),
    ("tasks/monster.py", "Monster"),
    ("tasks/stronghold.py", "Stronghold"),
    ("tasks/abra.py", "Abra"),
    ("tasks/ruins.py", "Ruins"),
    ("tasks/gather.py", "Gather"),
    ("tasks/gold_gather.py", "GoldGather"),
    ("tasks/gather_boost.py", "GatherBoost"),
    ("tasks/transport.py", "Transport")
]

missing_files = []
shallow_files = []
for file_str, name in files_to_check:
    if file_str not in content and name not in content:
        missing_files.append(file_str)
    else:
        # Check depth: count occurrences
        count = content.count(file_str) + content.count(name)
        if count < 3:
            shallow_files.append((file_str, count))

if missing_files:
    violations.append(f"Missing audited files: {missing_files}")
if shallow_files:
    violations.append(f"Shallow file audit detected: {shallow_files}")

# 3. Check 20 Error Codes Analyzed
error_codes = [
    "8004", "9007004", "8009", "8035", "8032",
    "10002", "10003", "9007020", "8014", "8015",
    "8027", "8037", "8041", "8042", "8046",
    "8060", "8062", "8063", "8095", "16001"
]

missing_errors = []
for err in error_codes:
    if err not in content:
        missing_errors.append(err)

if missing_errors:
    violations.append(f"Missing error codes in audit: {missing_errors}")

# 4. Check 10 Coordinator Priorities
priorities = [
    "abra", "prestige_invaders", "prestige_stronghold", "prestige_gather",
    "transport", "ruins", "combat", "stronghold", "gold_gather", "gather"
]

missing_priorities = []
for p in priorities:
    if p not in content:
        missing_priorities.append(p)

if missing_priorities:
    violations.append(f"Missing coordinator priorities: {missing_priorities}")

# 5. Check 5 Critical Stop Reasons
stop_reasons = [
    "WEAK_ARMY", "SUICIDE_RISK", "NPC_LEVEL_LOCKED",
    "REBEL_PREREQUISITE_FAILED", "CMD_OPTING"
]

missing_stop_reasons = []
for sr in stop_reasons:
    if sr not in content:
        missing_stop_reasons.append(sr)

if missing_stop_reasons:
    violations.append(f"Missing stop reasons: {missing_stop_reasons}")

# 6. Check Prestige Conflict Resolution
prestige_identifiers = ["4112019", "4112030", "4112001", "PRESTIGE_QUEST_IDS"]
missing_prestige = [pi for pi in prestige_identifiers if pi not in content]
if missing_prestige:
    violations.append(f"Missing prestige conflict elements: {missing_prestige}")

# 7. Check ExcludeManager Locking
exclude_terms = ["ExcludeManager", "confirm", "release"]
missing_exclude = [et for et in exclude_terms if et not in content]
if missing_exclude:
    violations.append(f"Missing ExcludeManager verification: {missing_exclude}")

# 8. Check BaseTask Unified Architecture & 5 core methods
core_methods = [
    "select_heroes_for_task",
    "select_best_pet",
    "build_march_army",
    "verify_target_safe_and_clear",
    "dispatch_march_with_retry"
]
missing_methods = [m for m in core_methods if m not in content]
if missing_methods:
    violations.append(f"Missing unified BaseTask core methods: {missing_methods}")

# 9. Check Before & After Refactoring Maps
refactoring_terms = ["Before", "After"]
if not all(term in content for term in refactoring_terms):
    violations.append("Missing Before & After refactoring architectural maps")

# Print Summary
print("-" * 60)
print(f"1. Forbidden shortcut phrases check: {'PASS (Clean)' if not found_forbidden else 'FAIL: ' + str(found_forbidden)}")
print(f"2. Audited files check (10/10): {'PASS' if not missing_files and not shallow_files else 'FAIL'}")
print(f"3. Error codes check (20/20): {'PASS' if not missing_errors else 'FAIL: ' + str(missing_errors)}")
print(f"4. Coordinator priorities check (10/10): {'PASS' if not missing_priorities else 'FAIL: ' + str(missing_priorities)}")
print(f"5. Stop reasons check (5/5): {'PASS' if not missing_stop_reasons else 'FAIL: ' + str(missing_stop_reasons)}")
print(f"6. Prestige quest resolution check: {'PASS' if not missing_prestige else 'FAIL: ' + str(missing_prestige)}")
print(f"7. ExcludeManager locking check: {'PASS' if not missing_exclude else 'FAIL: ' + str(missing_exclude)}")
print(f"8. Unified BaseTask blueprint check: {'PASS' if not missing_methods else 'FAIL: ' + str(missing_methods)}")
print(f"9. Before & After refactoring maps check: {'PASS' if 'Before' in content and 'After' in content else 'FAIL'}")
print("-" * 60)

if violations:
    print(f"\n[!] VERDICT: INTEGRITY VIOLATION ({len(violations)} issues found)")
    for v in violations:
        print(f"  - {v}")
    sys.exit(1)
else:
    print("\n[+] VERDICT: CLEAN - All forensic verification tests passed successfully!")
    sys.exit(0)
