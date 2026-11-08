import re

path = r"e:\osmanli\docs\reports\adversarial_march_audit.md"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

print("--- 20 ERROR CODES ANALYSIS ---")
error_codes = [
    "8004", "9007004", "8009", "8035", "8032",
    "10002", "10003", "9007020", "8014", "8015",
    "8027", "8037", "8041", "8042", "8046",
    "8060", "8062", "8063", "8095", "16001"
]
for c in error_codes:
    matches = len(re.findall(r"\b" + c + r"\b", text))
    print(f"Error {c:8s}: {matches:3d} matches")

print("\n--- 10 COORDINATOR PRIORITIES ---")
priorities = [
    "abra", "prestige_invaders", "prestige_stronghold", "prestige_gather",
    "transport", "ruins", "combat", "stronghold", "gold_gather", "gather"
]
for p in priorities:
    matches = len(re.findall(r"\b" + p + r"\b", text))
    print(f"Priority {p:20s}: {matches:3d} matches")

print("\n--- 5 STOP REASONS ---")
stop_reasons = [
    "WEAK_ARMY", "SUICIDE_RISK", "NPC_LEVEL_LOCKED",
    "REBEL_PREREQUISITE_FAILED", "CMD_OPTING"
]
for sr in stop_reasons:
    matches = len(re.findall(r"\b" + sr + r"\b", text))
    print(f"Stop Reason {sr:26s}: {matches:3d} matches")

print("\n--- PRESTIGE IDS ---")
for pid in ["4112019", "4112030", "4112001", "4112006", "4112004", "PRESTIGE_QUEST_IDS"]:
    matches = len(re.findall(pid, text))
    print(f"Prestige {pid:18s}: {matches:3d} matches")
