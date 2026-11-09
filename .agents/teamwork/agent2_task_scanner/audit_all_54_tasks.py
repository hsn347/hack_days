import os
import re
import glob
import json

tasks_dir = r"e:\osmanli\tasks"
task_files = sorted(glob.glob(os.path.join(tasks_dir, "*.py")))

audit_results = {}

re_init = re.compile(r"(?:init_data|init)\.(?:get\(|\[\s*)['\"]([a-zA-Z0-9_]+)['\"]")
re_query = re.compile(r"(?:conn\.query|self\.query|conn\.send_nowait|self\.send_nowait)\s*\(\s*([^,\)]+)\s*,\s*([^,\)]+)")
re_task_name = re.compile(r"class\s+([A-Za-z0-9_]+)\s*\((?:BaseTask|[A-Za-z0-9_]*Task[A-Za-z0-9_]*)\)")
re_name_attr = re.compile(r"name\s*:\s*str\s*=\s*['\"]([^'\"]+)['\"]")

# Constants
re_const = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*['\"]?(\d+)['\"]?", re.MULTILINE)

for fpath in task_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        lines = content.splitlines()

    # Find class name
    c_match = re_task_name.search(content)
    class_name = c_match.group(1) if c_match else fname.replace(".py", "")

    # Find task name
    n_match = re_name_attr.search(content)
    task_name = n_match.group(1) if n_match else class_name

    # Find constants
    const_map = {m.group(1): m.group(2) for m in re_const.finditer(content)}

    # Controllers accessed
    ctrls = set()
    for m in re_init.finditer(content):
        c = m.group(1)
        if c not in ["base", "data", "retdata", "items", "configData"]:
            ctrls.add(c)

    # Check for direct occurrences of known Ctrl names
    for line in lines:
        for m in re.finditer(r"['\"]([a-zA-Z0-9_]+(?:Ctrl|AgCtrl|Mgr))['\"]", line):
            c = m.group(1)
            if any(k in line for k in ["init_data", "init", "conn", "controller", "check_and_merge"]):
                ctrls.add(c)

    # Commands sent
    cmds = set()
    for m in re_query.finditer(content):
        c1 = m.group(1).strip().strip("'\"").replace("self.", "").replace("cls.", "")
        c2 = m.group(2).strip().strip("'\"").replace("self.", "").replace("cls.", "")
        c1_res = const_map.get(c1, c1)
        c2_res = const_map.get(c2, c2)
        cmds.add(f"{c1_res}/{c2_res}")

    # Elf decoupling check:
    has_elf = "elf" in fname or "elf" in content.lower()
    has_march_mgr = "march_manager" in content.lower()

    audit_results[fname] = {
        "class_name": class_name,
        "task_name": task_name,
        "controllers": sorted(list(ctrls)),
        "commands": sorted(list(cmds)),
        "lines": len(lines),
        "elf_check": {
            "has_elf": has_elf,
            "has_march_mgr": has_march_mgr
        }
    }

with open(r"e:\osmanli\.agents\teamwork\agent2_task_scanner\tasks_detailed_audit.json", "w", encoding="utf-8") as out:
    json.dump(audit_results, out, indent=2)

print(f"Audited {len(audit_results)} task files.")
