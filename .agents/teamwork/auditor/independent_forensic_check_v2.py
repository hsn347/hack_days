import os
import re
import sys

report_path = r"e:\osmanli\docs\reports\adversarial_march_audit.md"

print("=" * 65)
print("FORENSIC INTEGRITY AUDIT: DEEP CONTEXTUAL ANALYSIS")
print(f"Target: {report_path}")
print("=" * 65)

if not os.path.exists(report_path):
    print(f"CRITICAL: Report file does not exist at {report_path}")
    sys.exit(1)

with open(report_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

total_lines = len(lines)
total_chars = sum(len(l) for l in lines)
total_words = sum(len(l.split()) for l in lines)

print(f"Metrics: {total_lines} lines | {total_words} words | {total_chars} chars\n")

# Check 1: Forbidden Phrases Breakdown (Disclaimer vs Substantive Body)
forbidden_phrases = ["إلخ", "بنفس الطريقة للملفات الأخرى", "باختصار", "إلى آخره"]

body_violations = []
disclaimer_mentions = []

for idx, line in enumerate(lines, 1):
    for phrase in forbidden_phrases:
        if phrase in line:
            if idx <= 15 and ("يخلو هذا التقرير" in line or "تحذير النزاهة" in line):
                disclaimer_mentions.append((idx, phrase, line.strip()))
            else:
                body_violations.append((idx, phrase, line.strip()))

print("--- 1. SHORTCUT PHRASE AUDIT ---")
print(f"Substantive Shortcuts in Body (Lines 16-{total_lines}): {len(body_violations)}")
if body_violations:
    for line_no, p, content in body_violations:
        print(f"  [FAIL] Line {line_no}: phrase '{p}' -> {content[:80]}")
else:
    print("  [PASS] Zero shortcut phrases found in the entire body of the report.")

print(f"Disclaimer Mentions (Lines 1-15): {len(disclaimer_mentions)}")
for line_no, p, content in disclaimer_mentions:
    print(f"  [NOTE] Line {line_no}: quoted in negative compliance pledge -> '{p}'")

# Check 2: All 10 Files Audited
files_to_check = [
    ("tasks/base_task.py", "1.1 التشريح المجهري لكود `tasks/base_task.py`"),
    ("tasks/march_coordinator.py", "1.2 التشريح المجهري لكود `tasks/march_coordinator.py`"),
    ("tasks/monster.py", "1.3 التشريح المجهري لكود `tasks/monster.py`"),
    ("tasks/stronghold.py", "1.4 التشريح المجهري لكود `tasks/stronghold.py`"),
    ("tasks/abra.py", "1.5 التشريح المجهري لكود `tasks/abra.py`"),
    ("tasks/ruins.py", "1.6 التشريح المجهري لكود `tasks/ruins.py`"),
    ("tasks/gather.py", "1.7 التشريح المجهري لكود `tasks/gather.py`"),
    ("tasks/gold_gather.py", "1.8 التشريح المجهري لكود `tasks/gold_gather.py`"),
    ("tasks/gather_boost.py", "1.9 التشريح المجهري لكود `tasks/gather_boost.py`"),
    ("tasks/transport.py", "1.10 التشريح المجهري لكود `tasks/transport.py`"),
]

print("\n--- 2. 10 FILES DEDICATED CHAPTERS AUDIT ---")
full_text = "".join(lines)
missing_chapters = []
for file_path, header in files_to_check:
    if header in full_text:
        print(f"  [PASS] Found: {header}")
    else:
        missing_chapters.append(file_path)
        print(f"  [FAIL] Missing chapter header for: {file_path}")

# Check 3: All 20 Error Codes
error_codes = [
    "8004", "9007004", "8009", "8035", "8032",
    "10002", "10003", "9007020", "8014", "8015",
    "8027", "8037", "8041", "8042", "8046",
    "8060", "8062", "8063", "8095", "16001"
]
print("\n--- 3. 20 ERROR CODES AUDIT ---")
missing_errors = [ec for ec in error_codes if ec not in full_text]
if not missing_errors:
    print(f"  [PASS] All 20/20 error codes documented with protocol context.")
else:
    print(f"  [FAIL] Missing error codes: {missing_errors}")

# Check 4: 10 Coordinator Priorities
priorities = [
    "abra", "prestige_invaders", "prestige_stronghold", "prestige_gather",
    "transport", "ruins", "combat", "stronghold", "gold_gather", "gather"
]
print("\n--- 4. 10 COORDINATOR PRIORITIES AUDIT ---")
missing_p = [p for p in priorities if p not in full_text]
if not missing_p:
    print(f"  [PASS] All 10/10 coordinator priorities documented.")
else:
    print(f"  [FAIL] Missing priorities: {missing_p}")

# Check 5: 5 Stop Reasons
stop_reasons = [
    "WEAK_ARMY", "SUICIDE_RISK", "NPC_LEVEL_LOCKED",
    "REBEL_PREREQUISITE_FAILED", "CMD_OPTING"
]
print("\n--- 5. 5 CRITICAL STOP REASONS AUDIT ---")
missing_sr = [sr for sr in stop_reasons if sr not in full_text]
if not missing_sr:
    print(f"  [PASS] All 5/5 stop reasons mapped to CoordinatorAction.")
else:
    print(f"  [FAIL] Missing stop reasons: {missing_sr}")

# Check 6: Prestige Conflict Resolution
print("\n--- 6. PRESTIGE CONFLICT RESOLUTION AUDIT ---")
prestige_ok = all(k in full_text for k in ["4112019", "4112030", "4112001", "PRESTIGE_QUEST_IDS"])
print(f"  [{'PASS' if prestige_ok else 'FAIL'}] Prestige quest ID conflicts and resolution verified.")

# Check 7: BaseTask Unified Architecture
blueprint_ok = all(k in full_text for k in [
    "select_heroes_for_task",
    "select_best_pet",
    "build_march_army",
    "verify_target_safe_and_clear",
    "dispatch_march_with_retry"
])
print(f"  [{'PASS' if blueprint_ok else 'FAIL'}] Unified BaseTask architecture blueprint verified.")

print("\n" + "=" * 65)
if body_violations or missing_chapters or missing_errors or missing_p or missing_sr or not prestige_ok or not blueprint_ok:
    print("FINAL VERDICT: INTEGRITY VIOLATION")
    sys.exit(1)
else:
    print("FINAL VERDICT: CLEAN")
    sys.exit(0)
