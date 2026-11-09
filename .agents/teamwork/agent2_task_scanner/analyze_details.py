import json

with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\scan_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("=== 45 IDENTIFIED CONTROLLERS ===")
for ctrl, cnt in sorted(data["controllers"].items(), key=lambda x: -x[1]):
    # find files
    using_files = [fname for fname, info in data["tasks_summary"].items() if ctrl in info["controllers"]]
    print(f"- `{ctrl}`: {cnt} references across {len(using_files)} files ({', '.join(using_files[:4])})")

print("\n=== COMMANDS SUMMARY ===")
for cmd, cnt in sorted(data["commands"].items(), key=lambda x: -x[1]):
    using_files = [fname for fname, info in data["tasks_summary"].items() if cmd in info["commands"]]
    print(f"- `{cmd}`: {cnt} calls in {', '.join(using_files[:3])}")
