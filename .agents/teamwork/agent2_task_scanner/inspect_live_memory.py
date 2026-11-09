import json
import os
import glob

live_files = glob.glob(r"e:\osmanli\docs\*live_memory*.json") + glob.glob(r"e:\osmanli\scratch\*live_memory*.json")

all_live_keys = {}

for lf in live_files:
    fname = os.path.basename(lf)
    try:
        with open(lf, "r", encoding="utf-8", errors="ignore") as f:
            d = json.load(f)
            # could be gate / init_data or direct
            if "init_data" in d:
                keys = list(d["init_data"].keys())
            else:
                keys = list(d.keys())
            all_live_keys[fname] = keys
            print(f"Loaded {fname}: {len(keys)} top-level keys")
    except Exception as ex:
        print(f"Error loading {fname}: {ex}")

# Union of all keys observed in real sessions
union_keys = set()
for keys in all_live_keys.values():
    union_keys.update(keys)

print(f"\nTotal distinct live memory keys across all dumps: {len(union_keys)}")

# Let's categorize them:
# 1. Used by tasks
with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\scan_results.json", "r", encoding="utf-8") as f:
    task_scan = json.load(f)

task_controllers = set(task_scan["controllers"].keys())

used_in_live = union_keys.intersection(task_controllers)
unused_in_live = union_keys - task_controllers
task_not_in_live = task_controllers - union_keys

print(f"\n--- Keys in live memory AND used by tasks ({len(used_in_live)}) ---")
for k in sorted(used_in_live):
    print(f"  + {k}")

print(f"\n--- Keys in live memory BUT NEVER accessed by any task (CANDIDATES FOR DROPPING) ({len(unused_in_live)}) ---")
for k in sorted(unused_in_live):
    print(f"  - {k}")

print(f"\n--- Controllers accessed by tasks BUT NOT in these specific dumps ({len(task_not_in_live)}) ---")
for k in sorted(task_not_in_live):
    print(f"  ? {k}")
