import os
import re
import sys

report_path = r"e:\osmanli\docs\reports\adversarial_march_audit.md"

if not os.path.exists(report_path):
    print(f"FAIL: Report file does not exist at {report_path}")
    sys.exit(1)

with open(report_path, "r", encoding="utf-8") as f:
    content = f.read()

line_count = len(content.splitlines())
char_count = len(content)

print(f"Report statistics: {line_count} lines, {char_count} characters.")

# 1. Check 10 files
files_to_check = [
    "tasks/base_task.py",
    "tasks/march_coordinator.py",
    "tasks/monster.py",
    "tasks/stronghold.py",
    "tasks/abra.py",
    "tasks/ruins.py",
    "tasks/gather.py",
    "tasks/gold_gather.py",
    "tasks/gather_boost.py",
    "tasks/transport.py"
]

missing_files = []
for f in files_to_check:
    if f not in content:
        missing_files.append(f)

# 2. Check 20 error codes
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

# 3. Check 10 coordinator priorities
priorities = [
    "abra", "prestige_invaders", "prestige_stronghold", "prestige_gather",
    "transport", "ruins", "combat", "stronghold", "gold_gather", "gather"
]

missing_priorities = []
for p in priorities:
    if p not in content:
        missing_priorities.append(p)

# 4. Check 5 critical stop reasons
stop_reasons = [
    "WEAK_ARMY", "SUICIDE_RISK", "NPC_LEVEL_LOCKED",
    "REBEL_PREREQUISITE_FAILED", "CMD_OPTING"
]

missing_reasons = []
for sr in stop_reasons:
    if sr not in content:
        missing_reasons.append(sr)

# 5. Check Prestige conflict resolution
prestige_checks = ["4112019", "4112030", "4112001", "PRESTIGE_QUEST_IDS"]
missing_prestige = []
for pc in prestige_checks:
    if pc not in content:
        missing_prestige.append(pc)

# 6. Check ExcludeManager confirm and release
exclude_ops = ["confirm", "release", "ExcludeManager"]
missing_exclude = []
for op in exclude_ops:
    if op not in content:
        missing_exclude.append(op)

# 7. Check architectural unification blueprint & Before/After maps
blueprint_checks = [
    "select_heroes_for_task",
    "select_best_pet",
    "build_march_army",
    "verify_target_safe_and_clear",
    "dispatch_march_with_retry"
]
missing_blueprint = []
for bp in blueprint_checks:
    if bp not in content:
        missing_blueprint.append(bp)

print("\n--- AUDIT VERIFICATION RESULTS ---")
print(f"Files Check (10/10): {'PASS' if not missing_files else 'FAIL: ' + str(missing_files)}")
print(f"Error Codes Check (20/20): {'PASS' if not missing_errors else 'FAIL: ' + str(missing_errors)}")
print(f"Coordinator Priorities Check (10/10): {'PASS' if not missing_priorities else 'FAIL: ' + str(missing_priorities)}")
print(f"Stop Reasons Check (5/5): {'PASS' if not missing_reasons else 'FAIL: ' + str(missing_reasons)}")
print(f"Prestige Conflict Resolution Check: {'PASS' if not missing_prestige else 'FAIL: ' + str(missing_prestige)}")
print(f"ExcludeManager Operations Check: {'PASS' if not missing_exclude else 'FAIL: ' + str(missing_exclude)}")
print(f"Unified Blueprint Architecture Check: {'PASS' if not missing_blueprint else 'FAIL: ' + str(missing_blueprint)}")

all_passed = (
    not missing_files and
    not missing_errors and
    not missing_priorities and
    not missing_reasons and
    not missing_prestige and
    not missing_exclude and
    not missing_blueprint
)

if all_passed:
    print("\n>>> OVERALL VERIFICATION: 100% CLEAN PASS! Master Report is fully compliant. <<<")
    sys.exit(0)
else:
    print("\n>>> OVERALL VERIFICATION: FAILED! <<<")
    sys.exit(1)
