path = r"e:\osmanli\docs\reports\adversarial_march_audit.md"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

files = [
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

print("=== 10 FILES STRUCTURAL AUDIT ===")
for f in files:
    occ = text.count(f)
    has_critique = f"نقد الفريق الأحمر" in text[text.find(f):text.find(f)+8000] if f in text else False
    pos = text.find(f)
    print(f"File: {f:28s} | Count: {occ:3d} | Critique Present: {has_critique}")
